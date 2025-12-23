#!/usr/bin/env python3
"""
Extract Qualifying Captions from Mass Messages

Extracts qualifying PPV and FREE captions from mass_messages table into a staging
table for further classification and processing.

Usage:
    python extract_qualifying_captions.py

    # Preview without changes
    python extract_qualifying_captions.py --dry-run

    # Custom database path
    python extract_qualifying_captions.py --db-path /path/to/database.db

Qualification Criteria:
    PPV: price > 0, sent_count >= 500, earnings >= 100, length >= 50 chars
    FREE: sent_count >= 500, view_rate >= 0.25, length >= 50 chars

Performance Tiers:
    PPV: tier 1 (earnings >= 500), tier 2 (>= 200), tier 3 (>= 100)
    FREE: tier 1 (view_rate >= 0.40), tier 2 (>= 0.30), tier 3 (>= 0.25)
"""

import os
import sys
import sqlite3
import hashlib
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from collections import defaultdict

# Database path
DB_PATH = os.getenv(
    'EROS_DB_PATH',
    '/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db'
)

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)


class CaptionExtractor:
    """Extracts qualifying captions from mass_messages into staging table."""

    # Qualification thresholds
    PPV_MIN_PRICE = 0
    PPV_MIN_SENT_COUNT = 500
    PPV_MIN_EARNINGS = 100
    FREE_MIN_SENT_COUNT = 500
    FREE_MIN_VIEW_RATE = 0.25
    MIN_CONTENT_LENGTH = 50

    # Performance tier thresholds
    PPV_TIER_THRESHOLDS = {
        1: 500,   # tier 1: earnings >= 500
        2: 200,   # tier 2: earnings >= 200
        3: 100,   # tier 3: earnings >= 100
    }
    FREE_TIER_THRESHOLDS = {
        1: 0.40,  # tier 1: view_rate >= 0.40
        2: 0.30,  # tier 2: view_rate >= 0.30
        3: 0.25,  # tier 3: view_rate >= 0.25
    }

    def __init__(self, db_path: str, dry_run: bool = False):
        self.db_path = db_path
        self.dry_run = dry_run
        self.log_file = LOG_DIR / f"caption_extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.stats = {
            'ppv_extracted': 0,
            'free_extracted': 0,
            'duplicates_found': 0,
            'tier_distribution': {'ppv': defaultdict(int), 'free': defaultdict(int)},
            'content_type_distribution': defaultdict(int),
        }

    def _log(self, message: str, level: str = "INFO"):
        """Log message to file and console."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        with open(self.log_file, 'a') as f:
            f.write(log_entry + '\n')

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for hash calculation.

        - Strip leading/trailing whitespace
        - Collapse multiple spaces to single space
        - Lowercase for consistent hashing
        """
        if not text:
            return ""
        # Strip whitespace
        normalized = text.strip()
        # Collapse multiple whitespace characters to single space
        normalized = re.sub(r'\s+', ' ', normalized)
        # Lowercase for hash consistency
        normalized = normalized.lower()
        return normalized

    def calculate_hash(self, text: str) -> str:
        """
        Calculate SHA256 hash of normalized text.

        Args:
            text: Original text content

        Returns:
            SHA256 hex digest of normalized text
        """
        normalized = self.normalize_text(text)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def calculate_ppv_tier(self, total_earnings: float) -> int:
        """
        Calculate performance tier for PPV caption.

        Args:
            total_earnings: Total earnings across all uses

        Returns:
            Tier number (1=best, 3=baseline)
        """
        for tier, threshold in sorted(self.PPV_TIER_THRESHOLDS.items()):
            if total_earnings >= threshold:
                return tier
        return 3  # Default to lowest tier

    def calculate_free_tier(self, avg_view_rate: float) -> int:
        """
        Calculate performance tier for FREE caption.

        Args:
            avg_view_rate: Average view rate across all uses

        Returns:
            Tier number (1=best, 3=baseline)
        """
        for tier, threshold in sorted(self.FREE_TIER_THRESHOLDS.items()):
            if avg_view_rate >= threshold:
                return tier
        return 3  # Default to lowest tier

    def create_staging_table(self, conn: sqlite3.Connection) -> bool:
        """
        Create the caption_staging table if it doesn't exist.

        Args:
            conn: Database connection

        Returns:
            True if successful
        """
        create_sql = """
        CREATE TABLE IF NOT EXISTS caption_staging (
            staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_content TEXT NOT NULL,
            caption_hash TEXT NOT NULL,
            message_type TEXT,  -- 'ppv' or 'free'
            price REAL,
            total_earnings REAL,
            total_sends INTEGER,
            avg_view_rate REAL,
            avg_purchase_rate REAL,
            source_message_ids TEXT,  -- JSON array of message_ids that use this caption
            content_type_id INTEGER,  -- From mass_messages if available
            is_duplicate INTEGER DEFAULT 0,
            content_type_classified INTEGER,  -- Will be filled by classifier
            content_type_confidence REAL,
            send_type_classified TEXT,
            send_type_confidence REAL,
            performance_tier INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """

        index_sql = [
            "CREATE INDEX IF NOT EXISTS idx_staging_hash ON caption_staging(caption_hash);",
            "CREATE INDEX IF NOT EXISTS idx_staging_type ON caption_staging(message_type);",
            "CREATE INDEX IF NOT EXISTS idx_staging_tier ON caption_staging(performance_tier);",
            "CREATE INDEX IF NOT EXISTS idx_staging_content_type ON caption_staging(content_type_id);",
            "CREATE INDEX IF NOT EXISTS idx_staging_duplicate ON caption_staging(is_duplicate);",
        ]

        try:
            cursor = conn.cursor()
            cursor.execute(create_sql)
            for idx_sql in index_sql:
                cursor.execute(idx_sql)
            conn.commit()
            self._log("Created caption_staging table and indexes")
            return True
        except sqlite3.Error as e:
            self._log(f"Failed to create staging table: {e}", "ERROR")
            return False

    def clear_staging_table(self, conn: sqlite3.Connection) -> bool:
        """
        Clear existing data from staging table.

        Args:
            conn: Database connection

        Returns:
            True if successful
        """
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM caption_staging")
            conn.commit()
            self._log("Cleared existing staging table data")
            return True
        except sqlite3.Error as e:
            self._log(f"Failed to clear staging table: {e}", "ERROR")
            return False

    def extract_ppv_captions(self, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """
        Extract qualifying PPV captions from mass_messages.

        Returns:
            List of caption dictionaries ready for staging
        """
        query = """
        SELECT
            message_content,
            GROUP_CONCAT(message_id) as message_ids,
            MAX(price) as max_price,
            AVG(price) as avg_price,
            SUM(earnings) as total_earnings,
            SUM(sent_count) as total_sends,
            AVG(view_rate) as avg_view_rate,
            AVG(purchase_rate) as avg_purchase_rate,
            MAX(content_type_id) as content_type_id
        FROM mass_messages
        WHERE message_type = 'ppv'
          AND price > ?
          AND sent_count >= ?
          AND earnings >= ?
          AND LENGTH(message_content) >= ?
          AND message_content IS NOT NULL
        GROUP BY message_content
        """

        cursor = conn.cursor()
        cursor.execute(query, (
            self.PPV_MIN_PRICE,
            self.PPV_MIN_SENT_COUNT,
            self.PPV_MIN_EARNINGS,
            self.MIN_CONTENT_LENGTH
        ))

        captions = []
        for row in cursor.fetchall():
            message_ids = row['message_ids'].split(',') if row['message_ids'] else []
            caption_hash = self.calculate_hash(row['message_content'])
            tier = self.calculate_ppv_tier(row['total_earnings'] or 0)

            captions.append({
                'message_content': row['message_content'],
                'caption_hash': caption_hash,
                'message_type': 'ppv',
                'price': row['max_price'],
                'total_earnings': row['total_earnings'],
                'total_sends': row['total_sends'],
                'avg_view_rate': row['avg_view_rate'],
                'avg_purchase_rate': row['avg_purchase_rate'],
                'source_message_ids': json.dumps(message_ids),
                'content_type_id': row['content_type_id'],
                'performance_tier': tier,
            })

            # Track stats
            self.stats['ppv_extracted'] += 1
            self.stats['tier_distribution']['ppv'][tier] += 1
            if row['content_type_id']:
                self.stats['content_type_distribution'][row['content_type_id']] += 1

        self._log(f"Extracted {len(captions)} PPV captions")
        return captions

    def extract_free_captions(self, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """
        Extract qualifying FREE captions from mass_messages.

        Returns:
            List of caption dictionaries ready for staging
        """
        query = """
        SELECT
            message_content,
            GROUP_CONCAT(message_id) as message_ids,
            0 as max_price,
            0 as avg_price,
            0 as total_earnings,
            SUM(sent_count) as total_sends,
            AVG(view_rate) as avg_view_rate,
            0 as avg_purchase_rate,
            MAX(content_type_id) as content_type_id
        FROM mass_messages
        WHERE message_type = 'free'
          AND sent_count >= ?
          AND view_rate >= ?
          AND LENGTH(message_content) >= ?
          AND message_content IS NOT NULL
        GROUP BY message_content
        """

        cursor = conn.cursor()
        cursor.execute(query, (
            self.FREE_MIN_SENT_COUNT,
            self.FREE_MIN_VIEW_RATE,
            self.MIN_CONTENT_LENGTH
        ))

        captions = []
        for row in cursor.fetchall():
            message_ids = row['message_ids'].split(',') if row['message_ids'] else []
            caption_hash = self.calculate_hash(row['message_content'])
            tier = self.calculate_free_tier(row['avg_view_rate'] or 0)

            captions.append({
                'message_content': row['message_content'],
                'caption_hash': caption_hash,
                'message_type': 'free',
                'price': 0,
                'total_earnings': 0,
                'total_sends': row['total_sends'],
                'avg_view_rate': row['avg_view_rate'],
                'avg_purchase_rate': 0,
                'source_message_ids': json.dumps(message_ids),
                'content_type_id': row['content_type_id'],
                'performance_tier': tier,
            })

            # Track stats
            self.stats['free_extracted'] += 1
            self.stats['tier_distribution']['free'][tier] += 1
            if row['content_type_id']:
                self.stats['content_type_distribution'][row['content_type_id']] += 1

        self._log(f"Extracted {len(captions)} FREE captions")
        return captions

    def mark_duplicates(self, captions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Mark duplicate captions based on caption_hash.

        Duplicates are captions that appear in both PPV and FREE pools,
        or have the same normalized content.

        Args:
            captions: List of all extracted captions

        Returns:
            Updated caption list with is_duplicate flags
        """
        hash_counts = defaultdict(int)
        hash_first_seen = {}

        # Count occurrences of each hash
        for caption in captions:
            h = caption['caption_hash']
            hash_counts[h] += 1
            if h not in hash_first_seen:
                hash_first_seen[h] = caption

        # Mark duplicates (keep first occurrence as non-duplicate)
        duplicates_found = 0
        for caption in captions:
            h = caption['caption_hash']
            if hash_counts[h] > 1:
                # Only mark as duplicate if not the first occurrence
                if caption is not hash_first_seen[h]:
                    caption['is_duplicate'] = 1
                    duplicates_found += 1
                else:
                    caption['is_duplicate'] = 0
            else:
                caption['is_duplicate'] = 0

        self.stats['duplicates_found'] = duplicates_found
        self._log(f"Found {duplicates_found} duplicate captions")
        return captions

    def insert_captions(self, conn: sqlite3.Connection, captions: List[Dict[str, Any]]) -> int:
        """
        Insert captions into staging table.

        Args:
            conn: Database connection
            captions: List of caption dictionaries

        Returns:
            Number of captions inserted
        """
        insert_sql = """
        INSERT INTO caption_staging (
            message_content,
            caption_hash,
            message_type,
            price,
            total_earnings,
            total_sends,
            avg_view_rate,
            avg_purchase_rate,
            source_message_ids,
            content_type_id,
            is_duplicate,
            performance_tier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor = conn.cursor()
        inserted = 0

        for caption in captions:
            try:
                cursor.execute(insert_sql, (
                    caption['message_content'],
                    caption['caption_hash'],
                    caption['message_type'],
                    caption['price'],
                    caption['total_earnings'],
                    caption['total_sends'],
                    caption['avg_view_rate'],
                    caption['avg_purchase_rate'],
                    caption['source_message_ids'],
                    caption['content_type_id'],
                    caption.get('is_duplicate', 0),
                    caption['performance_tier'],
                ))
                inserted += 1
            except sqlite3.Error as e:
                self._log(f"Failed to insert caption: {e}", "WARNING")

        conn.commit()
        return inserted

    def get_content_type_names(self, conn: sqlite3.Connection) -> Dict[int, str]:
        """
        Get mapping of content_type_id to type_name.

        Args:
            conn: Database connection

        Returns:
            Dictionary mapping content_type_id to type_name
        """
        cursor = conn.cursor()
        cursor.execute("SELECT content_type_id, type_name FROM content_types")
        return {row['content_type_id']: row['type_name'] for row in cursor.fetchall()}

    def print_statistics(self, conn: sqlite3.Connection):
        """Print extraction statistics."""
        content_type_names = self.get_content_type_names(conn)

        self._log("\n" + "=" * 60)
        self._log("EXTRACTION STATISTICS")
        self._log("=" * 60)

        # Totals
        total = self.stats['ppv_extracted'] + self.stats['free_extracted']
        self._log(f"\nTotal captions extracted: {total}")
        self._log(f"  - PPV captions: {self.stats['ppv_extracted']}")
        self._log(f"  - FREE captions: {self.stats['free_extracted']}")
        self._log(f"  - Duplicates found: {self.stats['duplicates_found']}")

        # Tier distribution
        self._log("\nPPV Tier Distribution:")
        for tier in sorted(self.stats['tier_distribution']['ppv'].keys()):
            count = self.stats['tier_distribution']['ppv'][tier]
            threshold = self.PPV_TIER_THRESHOLDS.get(tier, 0)
            self._log(f"  Tier {tier} (earnings >= ${threshold}): {count}")

        self._log("\nFREE Tier Distribution:")
        for tier in sorted(self.stats['tier_distribution']['free'].keys()):
            count = self.stats['tier_distribution']['free'][tier]
            threshold = self.FREE_TIER_THRESHOLDS.get(tier, 0)
            self._log(f"  Tier {tier} (view_rate >= {threshold:.0%}): {count}")

        # Content type distribution
        self._log("\nContent Type Distribution (top 20):")
        sorted_ct = sorted(
            self.stats['content_type_distribution'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        for ct_id, count in sorted_ct:
            ct_name = content_type_names.get(ct_id, f"ID:{ct_id}")
            self._log(f"  {ct_name}: {count}")

        # Count NULL content types
        null_count = total - sum(self.stats['content_type_distribution'].values())
        if null_count > 0:
            self._log(f"  (no content_type): {null_count}")

        self._log("\n" + "=" * 60)

    def run(self) -> bool:
        """
        Run the extraction process.

        Returns:
            True if successful
        """
        self._log(f"Starting caption extraction (dry_run={self.dry_run})")
        self._log(f"Database: {self.db_path}")

        try:
            conn = self._get_connection()

            # Create staging table
            if not self.create_staging_table(conn):
                return False

            # Clear existing data (unless dry run)
            if not self.dry_run:
                if not self.clear_staging_table(conn):
                    return False

            # Extract PPV captions
            self._log("\nExtracting PPV captions...")
            ppv_captions = self.extract_ppv_captions(conn)

            # Extract FREE captions
            self._log("\nExtracting FREE captions...")
            free_captions = self.extract_free_captions(conn)

            # Combine and mark duplicates
            all_captions = ppv_captions + free_captions
            self._log("\nMarking duplicates...")
            all_captions = self.mark_duplicates(all_captions)

            # Insert into staging table
            if not self.dry_run:
                self._log("\nInserting captions into staging table...")
                inserted = self.insert_captions(conn, all_captions)
                self._log(f"Inserted {inserted} captions into caption_staging")
            else:
                self._log("\n[DRY RUN] Would insert {} captions".format(len(all_captions)))

            # Print statistics
            self.print_statistics(conn)

            conn.close()
            self._log("\nExtraction completed successfully")
            return True

        except Exception as e:
            self._log(f"Extraction failed: {e}", "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Extract qualifying captions from mass_messages into staging table'
    )
    parser.add_argument(
        '--db-path',
        default=DB_PATH,
        help=f'Path to SQLite database (default: {DB_PATH})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview extraction without making changes'
    )

    args = parser.parse_args()

    # Validate database exists
    if not os.path.exists(args.db_path):
        print(f"ERROR: Database not found: {args.db_path}")
        sys.exit(1)

    extractor = CaptionExtractor(args.db_path, dry_run=args.dry_run)
    success = extractor.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
