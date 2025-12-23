#!/usr/bin/env python3
"""
Caption Bank Rebuild - Master Orchestration Script

This script orchestrates the complete rebuild of caption_bank from mass_messages.
It coordinates the extraction, classification, and migration process.

Usage:
    python rebuild_caption_bank.py [--dry-run] [--skip-extraction] [--skip-classification]

Created: 2025-12-22
"""

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'rebuild_caption_bank_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / 'eros_sd_main.db'

# Thresholds (confirmed by user)
PPV_MIN_EARNINGS = 100.0
PPV_MIN_SENT = 500
FREE_MIN_VIEW_RATE = 0.25
FREE_MIN_SENT = 500
MIN_CHAR_LENGTH = 50
MAX_CHAR_LENGTH_PPV = 1000
MAX_CHAR_LENGTH_FREE = 800


def normalize_text(text: str) -> str:
    """Normalize text for hashing and comparison."""
    if not text:
        return ""
    # Strip whitespace
    text = text.strip()
    # Collapse multiple spaces
    import re
    text = re.sub(r'\s+', ' ', text)
    return text


def compute_hash(text: str) -> str:
    """Compute SHA256 hash of normalized text."""
    normalized = normalize_text(text).lower()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def calculate_tier(is_ppv: bool, earnings: float = 0, view_rate: float = 0) -> int:
    """Calculate performance tier based on metrics."""
    if is_ppv:
        if earnings >= 500:
            return 1  # ELITE
        elif earnings >= 200:
            return 2  # PROVEN
        else:
            return 3  # STANDARD
    else:
        if view_rate >= 0.40:
            return 1  # ELITE
        elif view_rate >= 0.30:
            return 2  # PROVEN
        else:
            return 3  # STANDARD


class CaptionBankRebuilder:
    """Main orchestrator for caption bank rebuild."""

    def __init__(self, db_path: Path, dry_run: bool = False):
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = None
        self.stats = {
            'ppv_extracted': 0,
            'free_extracted': 0,
            'duplicates_removed': 0,
            'classified_keyword': 0,
            'classified_llm': 0,
            'tier_1': 0,
            'tier_2': 0,
            'tier_3': 0,
            'final_count': 0
        }

    def connect(self):
        """Connect to database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def run_migration(self):
        """Execute the schema migration."""
        logger.info("Running schema migration...")

        migration_path = Path(__file__).parent.parent / 'migrations' / '019_caption_bank_rebuild.sql'

        if not migration_path.exists():
            logger.error(f"Migration file not found: {migration_path}")
            return False

        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        if self.dry_run:
            logger.info("[DRY RUN] Would execute migration SQL")
            return True

        try:
            self.conn.executescript(migration_sql)
            self.conn.commit()
            logger.info("Migration executed successfully")

            # Verify table exists
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='caption_bank_v2'"
            )
            if cursor.fetchone():
                logger.info("caption_bank_v2 table created successfully")
                return True
            else:
                logger.error("caption_bank_v2 table not found after migration")
                return False

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    def create_staging_table(self):
        """Create staging table for caption extraction."""
        logger.info("Creating staging table...")

        sql = """
        DROP TABLE IF EXISTS caption_staging;

        CREATE TABLE caption_staging (
            staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_content TEXT NOT NULL,
            caption_hash TEXT NOT NULL,
            message_type TEXT,
            price REAL,
            total_earnings REAL,
            total_sends INTEGER,
            avg_view_rate REAL,
            avg_purchase_rate REAL,
            source_message_ids TEXT,
            content_type_id INTEGER,
            is_duplicate INTEGER DEFAULT 0,
            content_type_classified INTEGER,
            content_type_confidence REAL,
            send_type_classified TEXT,
            send_type_confidence REAL,
            performance_tier INTEGER,
            char_length INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX idx_staging_hash ON caption_staging(caption_hash);
        CREATE INDEX idx_staging_type ON caption_staging(message_type);
        CREATE INDEX idx_staging_tier ON caption_staging(performance_tier);
        """

        if self.dry_run:
            logger.info("[DRY RUN] Would create staging table")
            return True

        try:
            self.conn.executescript(sql)
            self.conn.commit()
            logger.info("Staging table created")
            return True
        except Exception as e:
            logger.error(f"Failed to create staging table: {e}")
            return False

    def extract_ppv_captions(self):
        """Extract qualifying PPV captions from mass_messages."""
        logger.info(f"Extracting PPV captions (earnings >= ${PPV_MIN_EARNINGS}, sent >= {PPV_MIN_SENT})...")

        sql = f"""
        INSERT INTO caption_staging (
            message_content, caption_hash, message_type, price, total_earnings,
            total_sends, avg_view_rate, avg_purchase_rate, source_message_ids,
            content_type_id, performance_tier, char_length
        )
        SELECT
            message_content,
            '', -- Will be computed in Python
            'ppv',
            AVG(price),
            SUM(earnings),
            SUM(sent_count),
            AVG(view_rate),
            AVG(purchase_rate),
            GROUP_CONCAT(message_id),
            MAX(content_type_id),
            CASE
                WHEN SUM(earnings) >= 500 THEN 1
                WHEN SUM(earnings) >= 200 THEN 2
                ELSE 3
            END,
            LENGTH(message_content)
        FROM mass_messages
        WHERE message_type = 'ppv'
          AND price > 0
          AND sent_count >= {PPV_MIN_SENT}
          AND earnings >= {PPV_MIN_EARNINGS}
          AND LENGTH(message_content) >= {MIN_CHAR_LENGTH}
          AND LENGTH(message_content) <= {MAX_CHAR_LENGTH_PPV}
          AND message_content IS NOT NULL
          AND TRIM(message_content) != ''
        GROUP BY message_content
        """

        if self.dry_run:
            # Count what would be extracted
            count_sql = f"""
            SELECT COUNT(DISTINCT message_content) as cnt
            FROM mass_messages
            WHERE message_type = 'ppv'
              AND price > 0
              AND sent_count >= {PPV_MIN_SENT}
              AND earnings >= {PPV_MIN_EARNINGS}
              AND LENGTH(message_content) >= {MIN_CHAR_LENGTH}
              AND LENGTH(message_content) <= {MAX_CHAR_LENGTH_PPV}
              AND message_content IS NOT NULL
            """
            cursor = self.conn.execute(count_sql)
            count = cursor.fetchone()[0]
            logger.info(f"[DRY RUN] Would extract {count} PPV captions")
            self.stats['ppv_extracted'] = count
            return True

        try:
            cursor = self.conn.execute(sql)
            self.conn.commit()
            count = cursor.rowcount
            self.stats['ppv_extracted'] = count
            logger.info(f"Extracted {count} PPV captions")
            return True
        except Exception as e:
            logger.error(f"Failed to extract PPV captions: {e}")
            return False

    def extract_free_captions(self):
        """Extract qualifying free captions from mass_messages."""
        logger.info(f"Extracting free captions (view_rate >= {FREE_MIN_VIEW_RATE}, sent >= {FREE_MIN_SENT})...")

        sql = f"""
        INSERT INTO caption_staging (
            message_content, caption_hash, message_type, price, total_earnings,
            total_sends, avg_view_rate, avg_purchase_rate, source_message_ids,
            content_type_id, performance_tier, char_length
        )
        SELECT
            message_content,
            '', -- Will be computed in Python
            'free',
            0,
            0,
            SUM(sent_count),
            AVG(view_rate),
            0,
            GROUP_CONCAT(message_id),
            MAX(content_type_id),
            CASE
                WHEN AVG(view_rate) >= 0.40 THEN 1
                WHEN AVG(view_rate) >= 0.30 THEN 2
                ELSE 3
            END,
            LENGTH(message_content)
        FROM mass_messages
        WHERE message_type = 'free'
          AND sent_count >= {FREE_MIN_SENT}
          AND view_rate >= {FREE_MIN_VIEW_RATE}
          AND LENGTH(message_content) >= {MIN_CHAR_LENGTH}
          AND LENGTH(message_content) <= {MAX_CHAR_LENGTH_FREE}
          AND message_content IS NOT NULL
          AND TRIM(message_content) != ''
        GROUP BY message_content
        """

        if self.dry_run:
            # Count what would be extracted
            count_sql = f"""
            SELECT COUNT(DISTINCT message_content) as cnt
            FROM mass_messages
            WHERE message_type = 'free'
              AND sent_count >= {FREE_MIN_SENT}
              AND view_rate >= {FREE_MIN_VIEW_RATE}
              AND LENGTH(message_content) >= {MIN_CHAR_LENGTH}
              AND LENGTH(message_content) <= {MAX_CHAR_LENGTH_FREE}
              AND message_content IS NOT NULL
            """
            cursor = self.conn.execute(count_sql)
            count = cursor.fetchone()[0]
            logger.info(f"[DRY RUN] Would extract {count} free captions")
            self.stats['free_extracted'] = count
            return True

        try:
            cursor = self.conn.execute(sql)
            self.conn.commit()
            count = cursor.rowcount
            self.stats['free_extracted'] = count
            logger.info(f"Extracted {count} free captions")
            return True
        except Exception as e:
            logger.error(f"Failed to extract free captions: {e}")
            return False

    def compute_hashes(self):
        """Compute caption hashes for all staged captions."""
        logger.info("Computing caption hashes...")

        if self.dry_run:
            logger.info("[DRY RUN] Would compute hashes")
            return True

        cursor = self.conn.execute(
            "SELECT staging_id, message_content FROM caption_staging WHERE caption_hash = ''"
        )
        rows = cursor.fetchall()

        for row in rows:
            caption_hash = compute_hash(row['message_content'])
            self.conn.execute(
                "UPDATE caption_staging SET caption_hash = ? WHERE staging_id = ?",
                (caption_hash, row['staging_id'])
            )

        self.conn.commit()
        logger.info(f"Computed hashes for {len(rows)} captions")
        return True

    def mark_duplicates(self):
        """Mark duplicate captions based on hash."""
        logger.info("Marking duplicates...")

        if self.dry_run:
            logger.info("[DRY RUN] Would mark duplicates")
            return True

        # Find duplicate hashes and mark all but the best performer
        sql = """
        WITH RankedCaptions AS (
            SELECT
                staging_id,
                caption_hash,
                ROW_NUMBER() OVER (
                    PARTITION BY caption_hash
                    ORDER BY total_earnings DESC, avg_view_rate DESC
                ) as rn
            FROM caption_staging
        )
        UPDATE caption_staging
        SET is_duplicate = 1
        WHERE staging_id IN (
            SELECT staging_id FROM RankedCaptions WHERE rn > 1
        )
        """

        try:
            cursor = self.conn.execute(sql)
            self.conn.commit()

            # Count duplicates
            cursor = self.conn.execute("SELECT COUNT(*) FROM caption_staging WHERE is_duplicate = 1")
            dup_count = cursor.fetchone()[0]
            self.stats['duplicates_removed'] = dup_count
            logger.info(f"Marked {dup_count} duplicates")
            return True
        except Exception as e:
            logger.error(f"Failed to mark duplicates: {e}")
            return False

    def run_classification(self):
        """Run content type and send type classification."""
        logger.info("Running classification...")

        # Import classifiers
        try:
            from classify_content_types import ContentTypeClassifier
            from classify_send_types import SendTypeClassifier
        except ImportError:
            logger.warning("Classifiers not yet available, skipping classification step")
            return True

        if self.dry_run:
            logger.info("[DRY RUN] Would run classification")
            return True

        content_classifier = ContentTypeClassifier()
        send_classifier = SendTypeClassifier()

        cursor = self.conn.execute("""
            SELECT staging_id, message_content, price
            FROM caption_staging
            WHERE is_duplicate = 0 AND content_type_classified IS NULL
        """)
        rows = cursor.fetchall()

        for row in rows:
            # Classify content type
            content_type_id, content_conf = content_classifier.classify(row['message_content'])

            # Classify send type
            send_type, send_conf = send_classifier.classify(
                row['message_content'],
                price=row['price']
            )

            self.conn.execute("""
                UPDATE caption_staging
                SET content_type_classified = ?,
                    content_type_confidence = ?,
                    send_type_classified = ?,
                    send_type_confidence = ?
                WHERE staging_id = ?
            """, (content_type_id, content_conf, send_type, send_conf, row['staging_id']))

            if content_conf >= 0.70:
                self.stats['classified_keyword'] += 1

        self.conn.commit()
        logger.info(f"Classified {len(rows)} captions")
        return True

    def migrate_to_v2(self):
        """Migrate classified captions from staging to caption_bank_v2."""
        logger.info("Migrating to caption_bank_v2...")

        if self.dry_run:
            logger.info("[DRY RUN] Would migrate to caption_bank_v2")
            return True

        sql = """
        INSERT INTO caption_bank_v2 (
            caption_text, caption_hash, caption_type, content_type_id,
            schedulable_type, is_paid_page_only, is_active, performance_tier,
            suggested_price, price_range_min, price_range_max,
            classification_confidence, classification_method,
            global_times_used, total_earnings, total_sends,
            avg_view_rate, avg_purchase_rate, source
        )
        SELECT
            s.message_content,
            s.caption_hash,
            COALESCE(s.send_type_classified,
                CASE s.message_type
                    WHEN 'ppv' THEN 'ppv_message'
                    ELSE 'bump_normal'
                END
            ),
            COALESCE(s.content_type_classified, s.content_type_id, 31), -- Default to teasing
            CASE
                WHEN s.message_type = 'ppv' THEN 'ppv'
                ELSE 'ppv_bump'
            END,
            CASE WHEN s.send_type_classified IN ('renew_on_post', 'renew_on_message', 'expired_winback') THEN 1 ELSE 0 END,
            1,
            s.performance_tier,
            s.price,
            s.price,
            s.price,
            COALESCE(s.content_type_confidence, 0.5),
            CASE
                WHEN s.content_type_confidence >= 0.70 THEN 'keyword'
                WHEN s.content_type_confidence >= 0.50 THEN 'llm'
                ELSE 'imported'
            END,
            0,
            COALESCE(s.total_earnings, 0),
            COALESCE(s.total_sends, 0),
            COALESCE(s.avg_view_rate, 0),
            COALESCE(s.avg_purchase_rate, 0),
            'mass_messages_rebuild'
        FROM caption_staging s
        WHERE s.is_duplicate = 0
        """

        try:
            cursor = self.conn.execute(sql)
            self.conn.commit()

            # Get final count
            cursor = self.conn.execute("SELECT COUNT(*) FROM caption_bank_v2")
            self.stats['final_count'] = cursor.fetchone()[0]

            # Get tier distribution
            cursor = self.conn.execute("""
                SELECT performance_tier, COUNT(*) as cnt
                FROM caption_bank_v2
                GROUP BY performance_tier
            """)
            for row in cursor.fetchall():
                tier = row['performance_tier']
                self.stats[f'tier_{tier}'] = row['cnt']

            logger.info(f"Migrated {self.stats['final_count']} captions to caption_bank_v2")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    def print_summary(self):
        """Print rebuild summary."""
        logger.info("=" * 60)
        logger.info("CAPTION BANK REBUILD SUMMARY")
        logger.info("=" * 60)
        logger.info(f"PPV captions extracted:     {self.stats['ppv_extracted']:,}")
        logger.info(f"Free captions extracted:    {self.stats['free_extracted']:,}")
        logger.info(f"Duplicates removed:         {self.stats['duplicates_removed']:,}")
        logger.info(f"Classified (keyword):       {self.stats['classified_keyword']:,}")
        logger.info(f"Classified (LLM):           {self.stats['classified_llm']:,}")
        logger.info("-" * 60)
        logger.info(f"TIER 1 (ELITE):             {self.stats['tier_1']:,}")
        logger.info(f"TIER 2 (PROVEN):            {self.stats['tier_2']:,}")
        logger.info(f"TIER 3 (STANDARD):          {self.stats['tier_3']:,}")
        logger.info("-" * 60)
        logger.info(f"FINAL CAPTION COUNT:        {self.stats['final_count']:,}")
        logger.info("=" * 60)

    def run(self, skip_extraction: bool = False, skip_classification: bool = False):
        """Run the complete rebuild process."""
        logger.info("Starting Caption Bank Rebuild...")
        logger.info(f"Dry run: {self.dry_run}")

        self.connect()

        try:
            # Step 1: Run migration
            if not self.run_migration():
                return False

            if not skip_extraction:
                # Step 2: Create staging table
                if not self.create_staging_table():
                    return False

                # Step 3: Extract PPV captions
                if not self.extract_ppv_captions():
                    return False

                # Step 4: Extract free captions
                if not self.extract_free_captions():
                    return False

                # Step 5: Compute hashes
                if not self.compute_hashes():
                    return False

                # Step 6: Mark duplicates
                if not self.mark_duplicates():
                    return False

            if not skip_classification:
                # Step 7: Run classification
                if not self.run_classification():
                    return False

            # Step 8: Migrate to v2
            if not self.migrate_to_v2():
                return False

            # Print summary
            self.print_summary()

            logger.info("Caption Bank Rebuild completed successfully!")
            return True

        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description='Rebuild Caption Bank from mass_messages')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without executing')
    parser.add_argument('--skip-extraction', action='store_true', help='Skip extraction step')
    parser.add_argument('--skip-classification', action='store_true', help='Skip classification step')
    parser.add_argument('--db-path', type=str, help='Path to database file')

    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else DB_PATH

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    rebuilder = CaptionBankRebuilder(db_path, dry_run=args.dry_run)
    success = rebuilder.run(
        skip_extraction=args.skip_extraction,
        skip_classification=args.skip_classification
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
