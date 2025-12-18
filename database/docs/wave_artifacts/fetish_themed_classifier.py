#!/usr/bin/env python3
"""
Wave 1 Fetish-Themed Caption Classifier
Classifies captions with NULL content_type_id into fetish/themed categories
"""

import os
import sqlite3
import re
from pathlib import Path
from dataclasses import dataclass

DB_PATH = os.environ.get(
    "EROS_DB_PATH",
    str(Path(__file__).parent / "eros_sd_main.db")
)

@dataclass(frozen=True, slots=True)
class ContentType:
    """Content type definition with keywords."""

    id: int
    name: str
    keywords: tuple[str, ...]

FETISH_THEMED_TYPES = [
    ContentType(
        id=14,
        name="dom_sub",
        keywords=("dom", "sub", "domination", "submission", "master", "slave",
                 "control", "obey", "command", "worship", "mistress", "goddess",
                 "owned", "servant", "kneel", "beg", "punish")
    ),
    ContentType(
        id=13,
        name="feet",
        keywords=("feet", "foot", "toes", "soles", "arches", "footjob",
                 "ankle", "heel")
    ),
    ContentType(
        id=22,
        name="lingerie",
        keywords=("lingerie", "lace", "panties", "bra", "stockings", "garter",
                 "thong", "underwear", "negligee", "teddy", "corset", "bodystocking")
    ),
    ContentType(
        id=20,
        name="shower_bath",
        keywords=("shower", "bath", "wet", "water", "soap", "steam", "washing",
                 "bathtub", "soapy", "dripping wet", "soaking")
    ),
    ContentType(
        id=21,
        name="pool_outdoor",
        keywords=("pool", "outdoor", "outside", "beach", "sun", "nature",
                 "public", "sunshine", "poolside", "sunbathe")
    ),
    ContentType(
        id=24,
        name="pov",
        keywords=("pov", "point of view", "your view", "look down",
                 "perspective", "your eyes", "looking up at you", "from your angle")
    ),
    ContentType(
        id=23,
        name="story_roleplay",
        keywords=("roleplay", "role play", "pretend", "scenario", "story",
                 "fantasy", "imagine", "act out", "playing", "character")
    )
]


def analyze_caption(caption_text: str) -> tuple[int, float, str] | None:
    """
    Analyze caption text for fetish/themed content patterns.

    Args:
        caption_text: The caption text to analyze

    Returns:
        Tuple of (content_type_id, confidence, content_type_name) or None if no match
    """
    caption_lower = caption_text.lower()

    best_match = None
    best_score = 0
    best_confidence = 0.0

    for content_type in FETISH_THEMED_TYPES:
        # Count keyword matches
        matches = 0
        matched_keywords = []

        for keyword in content_type.keywords:
            # Use word boundaries for single words, substring for phrases
            if len(keyword.split()) > 1:
                # Multi-word phrase - use substring match
                if keyword in caption_lower:
                    matches += 1
                    matched_keywords.append(keyword)
            else:
                # Single word - use word boundary match
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, caption_lower):
                    matches += 1
                    matched_keywords.append(keyword)

        if matches > 0:
            # Calculate confidence based on number of matches
            # 1 match = 0.7, 2 matches = 0.8, 3+ matches = 0.9-1.0
            if matches == 1:
                confidence = 0.70
            elif matches == 2:
                confidence = 0.85
            else:
                confidence = min(0.90 + (matches - 3) * 0.02, 1.0)

            # Track best match (highest score)
            if matches > best_score or (matches == best_score and confidence > best_confidence):
                best_score = matches
                best_confidence = confidence
                best_match = (content_type.id, confidence, content_type.name)

    return best_match

def classify_captions():
    """Main classification function"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all captions with NULL content_type_id
    cursor.execute("""
        SELECT caption_id, caption_text
        FROM caption_bank
        WHERE content_type_id IS NULL
    """)

    captions = cursor.fetchall()
    print(f"Processing {len(captions)} captions with NULL content_type_id...")

    # Track statistics
    stats = {
        'total_processed': len(captions),
        'total_classified': 0,
        'by_type': {},
        'by_confidence': {
            '0.70-0.79': 0,
            '0.80-0.89': 0,
            '0.90-1.00': 0
        }
    }

    # Initialize type counters
    for ct in FETISH_THEMED_TYPES:
        stats['by_type'][ct.name] = 0

    # Process each caption
    updates = []
    for caption_id, caption_text in captions:
        result = analyze_caption(caption_text)

        if result:
            content_type_id, confidence, content_type_name = result
            updates.append((content_type_id, confidence, caption_id))

            # Update stats
            stats['total_classified'] += 1
            stats['by_type'][content_type_name] += 1

            if confidence < 0.80:
                stats['by_confidence']['0.70-0.79'] += 1
            elif confidence < 0.90:
                stats['by_confidence']['0.80-0.89'] += 1
            else:
                stats['by_confidence']['0.90-1.00'] += 1

    # Execute batch updates
    if updates:
        print(f"\nUpdating {len(updates)} captions...")
        cursor.executemany("""
            UPDATE caption_bank
            SET content_type_id = ?,
                classification_confidence = ?,
                classification_method = 'wave1_fetish_themed_classifier',
                updated_at = datetime('now')
            WHERE caption_id = ?
        """, updates)

        conn.commit()
        print("Updates committed successfully!")

    # Print statistics
    print("\n" + "="*60)
    print("FETISH-THEMED CLASSIFIER - WAVE 1 RESULTS")
    print("="*60)
    print(f"Total captions processed: {stats['total_processed']}")
    print(f"Total captions classified: {stats['total_classified']}")
    print(f"Classification rate: {stats['total_classified']/stats['total_processed']*100:.1f}%")

    print("\n--- BY CONTENT TYPE ---")
    for type_name, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {type_name}: {count}")

    print("\n--- BY CONFIDENCE LEVEL ---")
    for range_name, count in stats['by_confidence'].items():
        print(f"  {range_name}: {count}")

    print("\n" + "="*60)

    # Verify updates
    cursor.execute("""
        SELECT COUNT(*)
        FROM caption_bank
        WHERE classification_method = 'wave1_fetish_themed_classifier'
    """)
    verified_count = cursor.fetchone()[0]
    print(f"Verified: {verified_count} captions now have wave1_fetish_themed_classifier method")

    conn.close()

if __name__ == "__main__":
    classify_captions()
