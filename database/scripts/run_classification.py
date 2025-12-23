#!/usr/bin/env python3
"""
Run Classification Pipeline
Classifies all staged captions and inserts into caption_bank_v2.

Usage:
    python3 run_classification.py
"""

import hashlib
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database.scripts.classify_content_types import ContentTypeClassifier
from database.scripts.classify_send_types import SendTypeClassifier, ClassificationResult as SendTypeResult

DB_PATH = project_root / "database" / "eros_sd_main.db"


def create_caption_hash(text: str) -> str:
    """Create SHA256 hash of normalized caption text."""
    normalized = text.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def determine_schedulable_type(send_type: str, price: float | None) -> str | None:
    """Determine schedulable_type based on send_type and price."""
    ppv_types = {
        "ppv_unlock", "ppv_wall", "bundle", "flash_bundle",
        "tip_goal", "game_post", "first_to_tip", "vip_program", "snapchat_bundle"
    }
    bump_types = {
        "bump_normal", "bump_descriptive", "bump_text_only", "bump_flyer"
    }
    wall_types = {
        "link_drop", "wall_link_drop", "live_promo",
        "renew_on_post", "renew_on_message"
    }

    if send_type in ppv_types or (price and price > 0):
        return "ppv"
    elif send_type in bump_types:
        return "ppv_bump"
    elif send_type in wall_types:
        return "wall"
    return None


def run_classification():
    """Run classification on all staged captions."""
    print("=" * 70)
    print("CAPTION CLASSIFICATION PIPELINE")
    print("=" * 70)

    # Initialize classifiers
    print("\n[1/5] Initializing classifiers...")
    content_classifier = ContentTypeClassifier()
    send_classifier = SendTypeClassifier()
    print("  ✓ Content type classifier ready (37 types)")
    print("  ✓ Send type classifier ready (22 types)")

    # Connect to database
    print("\n[2/5] Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Load staged captions
    print("\n[3/5] Loading staged captions...")
    cursor.execute("""
        SELECT
            staging_id,
            message_content,
            message_type,
            performance_tier,
            total_earnings,
            price,
            total_sends,
            avg_view_rate,
            avg_purchase_rate,
            is_duplicate,
            content_type_id
        FROM caption_staging
        WHERE is_duplicate = 0
        ORDER BY staging_id
    """)
    staged_captions = cursor.fetchall()
    print(f"  ✓ Loaded {len(staged_captions)} non-duplicate captions")

    # Classify captions
    print("\n[4/5] Classifying captions...")
    results = []

    # Track statistics
    stats = {
        "total": 0,
        "content_classified": 0,
        "content_high_conf": 0,
        "content_low_conf": 0,
        "content_no_match": 0,
        "send_classified": 0,
        "send_high_conf": 0,
        "send_low_conf": 0,
    }

    for i, row in enumerate(staged_captions):
        stats["total"] += 1

        text = row["message_content"]
        message_type = row["message_type"]  # 'ppv' or 'free'
        price = row["price"]

        # Classify content type
        content_result = content_classifier.classify_detailed(text)
        if content_result:
            stats["content_classified"] += 1
            content_type_id = content_result.content_type_id
            content_confidence = content_result.confidence
            content_method = "keyword"
            if content_confidence >= 0.70:
                stats["content_high_conf"] += 1
            else:
                stats["content_low_conf"] += 1
        else:
            stats["content_no_match"] += 1
            content_type_id = 19  # Default to "solo"
            content_confidence = 0.30
            content_method = "default"

        # Classify send type
        has_link = "http" in text.lower() or "link" in text.lower()
        send_result = send_classifier.classify_detailed(text, price, has_link)
        stats["send_classified"] += 1

        send_type_key = send_result.send_type_key
        send_confidence = send_result.confidence
        caption_type_from_send = send_result.caption_type

        if send_confidence >= 0.70:
            stats["send_high_conf"] += 1
        else:
            stats["send_low_conf"] += 1

        # Use send_type's caption_type
        final_caption_type = caption_type_from_send

        # Determine schedulable_type
        schedulable_type = determine_schedulable_type(send_type_key, price)

        # Combine confidences
        combined_confidence = min((content_confidence + send_confidence) / 2, 1.0)
        classification_method = f"{content_method}+structural"

        # Prepare result
        results.append({
            "staging_id": row["staging_id"],
            "caption_text": text,
            "caption_hash": create_caption_hash(text),
            "caption_type": final_caption_type,
            "content_type_id": content_type_id,
            "schedulable_type": schedulable_type,
            "is_paid_page_only": 1 if send_type_key in ("renew_on_message", "renew_on_post", "ppv_followup", "expired_winback") else 0,
            "is_active": 1,
            "performance_tier": row["performance_tier"] or 3,
            "suggested_price": price,
            "price_range_min": price if price else None,
            "price_range_max": price if price else None,
            "classification_confidence": round(combined_confidence, 4),
            "classification_method": classification_method,
            "total_earnings": row["total_earnings"] or 0.0,
            "total_sends": row["total_sends"] or 0,
            "avg_view_rate": row["avg_view_rate"] or 0.0,
            "avg_purchase_rate": row["avg_purchase_rate"] or 0.0,
        })

        # Progress update
        if (i + 1) % 1000 == 0:
            print(f"  Processed {i + 1}/{len(staged_captions)} captions...")

    print(f"  ✓ Classified {stats['total']} captions")
    print(f"\n  Content Type Classification:")
    print(f"    - High confidence (>=0.70): {stats['content_high_conf']}")
    print(f"    - Low confidence (<0.70): {stats['content_low_conf']}")
    print(f"    - No match (default): {stats['content_no_match']}")
    print(f"\n  Send Type Classification:")
    print(f"    - High confidence (>=0.70): {stats['send_high_conf']}")
    print(f"    - Low confidence (<0.70): {stats['send_low_conf']}")

    # Insert into caption_bank_v2
    print("\n[5/5] Inserting into caption_bank_v2...")

    insert_sql = """
        INSERT INTO caption_bank_v2 (
            caption_text,
            caption_hash,
            caption_type,
            content_type_id,
            schedulable_type,
            is_paid_page_only,
            is_active,
            performance_tier,
            suggested_price,
            price_range_min,
            price_range_max,
            classification_confidence,
            classification_method,
            total_earnings,
            total_sends,
            avg_view_rate,
            avg_purchase_rate,
            source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'mass_messages_rebuild')
    """

    inserted = 0
    skipped = 0

    for result in results:
        try:
            cursor.execute(insert_sql, (
                result["caption_text"],
                result["caption_hash"],
                result["caption_type"],
                result["content_type_id"],
                result["schedulable_type"],
                result["is_paid_page_only"],
                result["is_active"],
                result["performance_tier"],
                result["suggested_price"],
                result["price_range_min"],
                result["price_range_max"],
                result["classification_confidence"],
                result["classification_method"],
                result["total_earnings"],
                result["total_sends"],
                result["avg_view_rate"],
                result["avg_purchase_rate"],
            ))
            inserted += 1
        except sqlite3.IntegrityError as e:
            # Duplicate hash
            skipped += 1

    conn.commit()
    print(f"  ✓ Inserted {inserted} captions")
    print(f"  ✓ Skipped {skipped} duplicates")

    # Final summary
    print("\n" + "=" * 70)
    print("CLASSIFICATION COMPLETE")
    print("=" * 70)

    # Get final counts
    cursor.execute("SELECT COUNT(*) FROM caption_bank_v2")
    total_v2 = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM caption_bank_v2 WHERE classification_confidence >= 0.70")
    high_conf = cursor.fetchone()[0]

    cursor.execute("""
        SELECT performance_tier, COUNT(*)
        FROM caption_bank_v2
        GROUP BY performance_tier
        ORDER BY performance_tier
    """)
    tier_dist = cursor.fetchall()

    cursor.execute("""
        SELECT schedulable_type, COUNT(*)
        FROM caption_bank_v2
        GROUP BY schedulable_type
    """)
    sched_dist = cursor.fetchall()

    print(f"\nCaption Bank v2 Summary:")
    print(f"  Total captions: {total_v2}")
    print(f"  High confidence (>=0.70): {high_conf} ({high_conf/total_v2*100:.1f}%)")
    print(f"  Low confidence (<0.70): {total_v2 - high_conf} ({(total_v2 - high_conf)/total_v2*100:.1f}%)")

    print(f"\n  Performance Tier Distribution:")
    for tier, count in tier_dist:
        print(f"    Tier {tier}: {count}")

    print(f"\n  Schedulable Type Distribution:")
    for stype, count in sched_dist:
        print(f"    {stype or 'None'}: {count}")

    conn.close()

    return inserted, skipped


if __name__ == "__main__":
    inserted, skipped = run_classification()
    print(f"\n✅ Done! {inserted} captions ready for use.")
