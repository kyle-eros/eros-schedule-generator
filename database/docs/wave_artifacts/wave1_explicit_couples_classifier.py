#!/usr/bin/env python3
"""
Wave 1: Explicit Couples Content Classifier

Classifies captions with NULL content_type_id that match explicit couples content patterns.

Target content types:
- boy_girl (11)
- girl_girl (6)
- boy_girl_girl (4)
- girl_girl_girl (5)
- creampie (2)
- anal (1)
"""

import os
import sqlite3
import re
from pathlib import Path

# Database path
DB_PATH = os.environ.get(
    "EROS_DB_PATH",
    str(Path(__file__).parent / "eros_sd_main.db")
)

# Content type mappings
CONTENT_TYPES = {
    'boy_girl': 11,
    'girl_girl': 6,
    'boy_girl_girl': 4,
    'girl_girl_girl': 5,
    'creampie': 2,
    'anal': 1
}

# Keyword patterns for each content type (order matters - more specific first)
# Balanced patterns - specific enough to avoid false positives, broad enough to catch real matches
PATTERNS = {
    'boy_girl_girl': [
        r'\bthreesome\b',
        r'\bbgg\b',
        r'\b(two|2)\s+girls?\s+(and|with|&)\s+(a\s+)?(guy|man|boy|him)',
        r'\bffm\b',
    ],
    'girl_girl_girl': [
        r'\b(three|3)\s+girls?\b',
        r'\bggg\b',
        r'\bfff\b',
    ],
    'creampie': [
        r'\bcreampie\b',
        r'\bcream\s*pie\b',
        r'\bcum(ming)?\s+(in|inside)',
        r'\bfilled\s+(me|her|up)',
        r'\bbreed',  # Match any form of "breed"
        r'\bload\s+inside\b',
        r'\bfinish(ed|ing)?\s+inside\b',
    ],
    'anal': [
        r'\banal\s+(sex|fuck|play|vid|video|scene|pov)\b',
        r'\bass\s+(fuck(ed|ing)?|sex|pounding)\b',
        r'\bbackdoor\s+(fun|action|sex)\b',
        r'\bbutt\s+(fuck|sex)\b',
        r'\bin\s+(my|her)\s+ass\b',
        r'\bfuck(ed|ing)?\s+(my|her)\s+ass\b',
        r'\bup\s+(my|her|the)\s+ass\b',
    ],
    'girl_girl': [
        r'\bgirl\s+on\s+girl\b',
        r'\bg/g\s+(vid|video|sex|action)\b',
        r'\blesbian\s+(sex|vid|video|scene|action|porn)\b',
        r'\beating\s+(her|another\s+girl)',
        r'\blicking\s+(her|another\s+girl)',
        r'\b(she|her)\s+(licks|eats|fingers)\s+(me|my)',
        r'\b(me|i)\s+(lick|eat|finger)\s+her\b',
    ],
    'boy_girl': [
        r'\bboy\s+girl\s+(vid|video|sex|scene|porn)\b',
        r'\bb/g\s+(vid|video|sex|action)\b',
        r'\bhis\s+(cock|dick)',  # Any mention of "his cock/dick"
        r'\bhe\s+(fuck(s|ed|ing)?|pound(s|ed|ing)?|cum(s|med)?)',  # He [action]
        r'\bfuck(ed|ing)?\s+(by|with)\s+(a\s+)?(guy|man|boy|him|bf|boyfriend)\b',
        r'\bsex\s+(vid|video)(s)?\s+with.*(bf|boyfriend|guy|him)\b',
        r'\briding\s+his\s+(cock|dick)\b',
        r'\bsucking\s+his\s+(cock|dick)\b',
        r'\b(guy|man|boy|bf|boyfriend)\s+(fuck|fucking|pounds|pounding)',
        r'\bbent\s+over\s+and\s+fuck(ed|ing)\b',  # "bent over and fucked"
    ],
}


def classify_caption(caption_text: str) -> tuple[str | None, float, list[str]]:
    """
    Classify a caption based on keyword patterns.

    Args:
        caption_text: The caption text to classify.

    Returns:
        Tuple of (content_type_key, confidence, matched_patterns).
        Returns (None, 0.0, []) if no match found.
    """
    if not caption_text:
        return None, 0.0, []

    caption_lower = caption_text.lower()

    # Check patterns in order (more specific types first)
    for content_type_key in ['boy_girl_girl', 'girl_girl_girl', 'creampie', 'anal', 'girl_girl', 'boy_girl']:
        patterns = PATTERNS[content_type_key]
        matches = []

        for pattern in patterns:
            if re.search(pattern, caption_lower, re.IGNORECASE):
                matches.append(pattern)

        if matches:
            # Calculate confidence based on number of pattern matches
            # 1 match = 0.75, 2 matches = 0.85, 3+ matches = 0.95
            if len(matches) == 1:
                confidence = 0.75
            elif len(matches) == 2:
                confidence = 0.85
            else:
                confidence = 0.95

            return content_type_key, confidence, matches

    return None, 0.0, []


def main():
    """Main classification function."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 80)
    print("WAVE 1: EXPLICIT COUPLES CONTENT CLASSIFIER")
    print("=" * 80)
    print()

    # Query all captions with NULL content_type_id
    print("Querying captions with NULL content_type_id...")
    cursor.execute("""
        SELECT caption_id, caption_text
        FROM caption_bank
        WHERE content_type_id IS NULL
        ORDER BY caption_id
    """)

    captions = cursor.fetchall()
    total_captions = len(captions)
    print(f"Found {total_captions} captions with NULL content_type_id")
    print()

    # Classify each caption
    classifications = {
        'boy_girl': [],
        'girl_girl': [],
        'boy_girl_girl': [],
        'girl_girl_girl': [],
        'creampie': [],
        'anal': []
    }

    unclassified = []

    print("Classifying captions...")
    for row in captions:
        caption_id = row['caption_id']
        caption_text = row['caption_text']

        content_type_key, confidence, matched_patterns = classify_caption(caption_text)

        if content_type_key:
            classifications[content_type_key].append({
                'caption_id': caption_id,
                'caption_text': caption_text,
                'confidence': confidence,
                'matched_patterns': matched_patterns
            })
        else:
            unclassified.append(caption_id)

    # Print classification summary
    print()
    print("=" * 80)
    print("CLASSIFICATION SUMMARY")
    print("=" * 80)

    total_classified = 0
    for content_type_key, items in classifications.items():
        count = len(items)
        total_classified += count
        if count > 0:
            avg_confidence = sum(item['confidence'] for item in items) / count
            print(f"{content_type_key}: {count} captions (avg confidence: {avg_confidence:.2f})")

    print()
    print(f"Total classified: {total_classified}/{total_captions}")
    print(f"Total unclassified: {len(unclassified)}/{total_captions}")
    print()

    # Ask for confirmation before updating
    print("=" * 80)
    print("READY TO UPDATE DATABASE")
    print("=" * 80)
    response = input(f"\nUpdate {total_classified} captions in the database? (yes/no): ")

    if response.lower() != 'yes':
        print("Classification cancelled. No changes made to database.")
        conn.close()
        return

    # Perform updates
    print("\nUpdating database...")
    updated_count = 0

    for content_type_key, items in classifications.items():
        content_type_id = CONTENT_TYPES[content_type_key]

        for item in items:
            cursor.execute("""
                UPDATE caption_bank
                SET content_type_id = ?,
                    classification_confidence = ?,
                    classification_method = 'wave1_explicit_couples_classifier',
                    updated_at = datetime('now')
                WHERE caption_id = ?
            """, (content_type_id, item['confidence'], item['caption_id']))
            updated_count += 1

    conn.commit()
    print(f"Successfully updated {updated_count} captions")

    # Print detailed results by content type
    print()
    print("=" * 80)
    print("DETAILED RESULTS BY CONTENT TYPE")
    print("=" * 80)

    for content_type_key, items in classifications.items():
        if not items:
            continue

        print()
        print(f"\n{content_type_key.upper()} ({len(items)} captions)")
        print("-" * 80)

        # Group by confidence
        confidence_groups = {}
        for item in items:
            conf = item['confidence']
            if conf not in confidence_groups:
                confidence_groups[conf] = []
            confidence_groups[conf].append(item)

        for confidence in sorted(confidence_groups.keys(), reverse=True):
            group = confidence_groups[confidence]
            print(f"\nConfidence {confidence}: {len(group)} captions")

            # Show first 3 examples
            for i, item in enumerate(group[:3]):
                caption_preview = item['caption_text'][:100] + "..." if len(item['caption_text']) > 100 else item['caption_text']
                print(f"  - ID {item['caption_id']}: {caption_preview}")

    # Verification query
    print()
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)

    cursor.execute("""
        SELECT
            ct.type_name,
            COUNT(*) as count,
            AVG(cb.classification_confidence) as avg_confidence
        FROM caption_bank cb
        JOIN content_types ct ON cb.content_type_id = ct.content_type_id
        WHERE cb.classification_method = 'wave1_explicit_couples_classifier'
        GROUP BY ct.type_name
        ORDER BY count DESC
    """)

    print("\nCaptions classified by Wave 1:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} captions (avg confidence: {row[2]:.2f})")

    conn.close()
    print()
    print("Classification complete!")


if __name__ == "__main__":
    main()
