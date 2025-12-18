#!/usr/bin/env python3
"""
Wave 1 Engagement Classifier
Classifies captions with NULL content_type_id into engagement content types.
"""

import os
import sqlite3
import re
from pathlib import Path

DB_PATH = os.environ.get(
    "EROS_DB_PATH",
    str(Path(__file__).parent / "eros_sd_main.db")
)

# Content type mappings
CONTENT_TYPES = {
    'tip_request': 32,
    'renewal_retention': 33
}

# Keyword patterns for classification
# Balanced patterns to catch real engagement content without false positives
PATTERNS = {
    'tip_request': [
        # Direct tip requests
        r'\btip\s+me\b', r'\bsend\s+(?:a\s+)?tip\b', r'\btip\s+\$\d+',
        r'\$\d+.*\btip\b', r'\bshow\s+(?:me\s+)?love\b', r'\bspoil\s+me\b',
        # Tip incentives
        r'\btip\s+\d+.*(?:get|receive|unlock)', r'(?:first|anyone).*tip.*get',
        r'\btip.*(?:bundle|content|video)', r'\bsend.*gift\b',
        r'\bdonate\b', r'\bsupport\s+me\b'
    ],
    'renewal_retention': [
        # Explicit renewal language
        r'\brenew\b', r'\brenewal\b', r'\brebill\b', r'\bauto[- ]renew\b',
        r'\benable.*renew\b', r'\bturn.*renew\s+on\b', r'\brenew\s+on\b',
        # Subscription retention
        r'\bsubscription\b', r'\bstay\s+subscribed\b', r'\bkeep.*subscri',
        # Free trial/year with renewal
        r'\bfree\s+(?:trial|year|month).*renew\b',
        # Leaving/missing language (strong indicators)
        r'\bdon\'t\s+(?:leave|go|unsubscribe)\b', r'\bmiss\s+you\b.*(?:sub|back)',
        r'\bcome\s+back\b.*(?:sub|renew)', r'\bexpired\b.*(?:renew|sub)',
        # Winback language
        r'\bwin.*back\b', r'\breturn.*(?:sub|renew)\b'
    ]
}


def classify_caption(caption_text: str) -> tuple[str | None, float]:
    """
    Classify a caption based on keyword patterns.

    Args:
        caption_text: The caption text to classify.

    Returns:
        Tuple of (content_type_key, confidence_score).
        Returns (None, 0.0) if no match found.
    """
    caption_lower = caption_text.lower()

    best_match = None
    best_confidence = 0.0

    for content_type, patterns in PATTERNS.items():
        match_count = 0
        for pattern in patterns:
            if re.search(pattern, caption_lower):
                match_count += 1

        if match_count > 0:
            # Calculate confidence based on number of matches
            # Base confidence + bonus for multiple matches
            confidence = 0.7 + min(match_count * 0.05, 0.3)

            if confidence > best_confidence:
                best_confidence = confidence
                best_match = content_type

    return (best_match, best_confidence)


def process_captions():
    """Main processing function."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch all captions with NULL content_type_id
    print("Fetching captions with NULL content_type_id...")
    cursor.execute("""
        SELECT caption_id, caption_text
        FROM caption_bank
        WHERE content_type_id IS NULL
        ORDER BY caption_id
    """)

    captions = cursor.fetchall()
    print(f"Found {len(captions)} captions to analyze\n")

    # Classification results
    classifications = {
        'tip_request': [],
        'renewal_retention': []
    }

    # Process each caption
    for caption_id, caption_text in captions:
        content_type, confidence = classify_caption(caption_text)

        if content_type:
            classifications[content_type].append({
                'caption_id': caption_id,
                'confidence': confidence,
                'text': caption_text[:100]  # First 100 chars for review
            })

    # Display results before updating
    print("=" * 80)
    print("CLASSIFICATION RESULTS")
    print("=" * 80)

    for content_type, matches in classifications.items():
        print(f"\n{content_type.upper()} ({CONTENT_TYPES[content_type]}): {len(matches)} matches")
        print("-" * 80)

        if matches:
            # Show confidence distribution
            confidences = [m['confidence'] for m in matches]
            avg_conf = sum(confidences) / len(confidences)
            min_conf = min(confidences)
            max_conf = max(confidences)

            print(f"Confidence - Avg: {avg_conf:.3f}, Min: {min_conf:.3f}, Max: {max_conf:.3f}")

            # Show first 5 examples
            print("\nFirst 5 examples:")
            for i, match in enumerate(matches[:5], 1):
                print(f"  {i}. ID {match['caption_id']} (conf: {match['confidence']:.2f})")
                print(f"     {match['text']}...")

    # Summary
    total_classified = sum(len(matches) for matches in classifications.values())
    print("\n" + "=" * 80)
    print(f"TOTAL CLASSIFIED: {total_classified} out of {len(captions)} captions")
    print(f"UNCLASSIFIED: {len(captions) - total_classified}")
    print("=" * 80)

    # Ask for confirmation before updating
    print("\nProceed with database updates? (yes/no): ", end="")
    response = input().strip().lower()

    if response != 'yes':
        print("Aborted - no database changes made")
        conn.close()
        return

    # Perform updates
    print("\nUpdating database...")
    update_count = 0

    for content_type, matches in classifications.items():
        content_type_id = CONTENT_TYPES[content_type]

        for match in matches:
            cursor.execute("""
                UPDATE caption_bank
                SET content_type_id = ?,
                    classification_confidence = ?,
                    classification_method = 'wave1_engagement_classifier',
                    updated_at = datetime('now')
                WHERE caption_id = ?
            """, (content_type_id, match['confidence'], match['caption_id']))
            update_count += 1

    conn.commit()
    print(f"Successfully updated {update_count} captions")

    # Verify updates
    cursor.execute("""
        SELECT COUNT(*)
        FROM caption_bank
        WHERE classification_method = 'wave1_engagement_classifier'
    """)
    verified_count = cursor.fetchone()[0]
    print(f"Verified {verified_count} captions with wave1_engagement_classifier method")

    conn.close()
    print("\nClassification complete!")


if __name__ == "__main__":
    process_captions()
