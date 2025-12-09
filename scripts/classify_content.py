#!/usr/bin/env python3
"""
EROS Content Classification Script
Classifies OnlyFans captions as EXPLICIT or IMPLIED using Claude API.

Usage:
    python classify_content.py --creator missalexa --dry-run
    python classify_content.py --creator all --batch-size 50
    python classify_content.py --caption-ids 1234,5678,9012
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any

# Classification prompt templates
CLASSIFICATION_SYSTEM_PROMPT = """
You are a content classification specialist for an OnlyFans management platform. Your task is to classify captions as either EXPLICIT (showing/revealing content) or IMPLIED (teasing/suggesting content).

## CLASSIFICATION RULES

### EXPLICIT Content Indicators (keep original content_type_id)
Content is EXPLICIT when it describes or shows:
- Direct anatomy presentation: "here's my...", "look at my...", "showing you my..."
- Active physical actions: "spreading", "fucking", "cumming", "bouncing", "riding"
- Bodily fluids: "dripping", "creamy", "wet [body part]", "soaked", "cum"
- Close-up/POV descriptions: "POV", "close up", "up close", "zoom in"
- Post-reveal states: "freshly shaved", "smooth", "bare", "naked"
- Explicit anatomical terms used directly (not as euphemisms)
- First-person present tense showing: "I'm touching...", "Watch me..."

### IMPLIED Content Indicators (reclassify to implied_* type)
Content is IMPLIED when it:
- Offers to show: "wanna see?", "do you want to see?", "should I show you?"
- Describes hidden/covered states: "underneath", "hidden", "covered", "peek", "barely covered"
- Uses euphemisms for anatomy: "cherry", "kitty", "flower", "cookie", "peach"
- Describes pre-reveal actions: "strip tease", "slowly slide off", "about to remove"
- Frames as questions or possibilities: "what if I...", "imagine if..."
- Suggests without confirming: "guess what's under...", "you'll never guess..."
- Uses future tense promises: "I'll show you...", "I'm going to..."

## SAFETY PROTOCOL

**CRITICAL: When classification is uncertain, ALWAYS choose EXPLICIT.**

Confidence Scoring:
- 0.95-1.00: Very confident
- 0.80-0.94: Confident
- 0.65-0.79: Moderate confidence
- 0.50-0.64: Low confidence, defaulting to EXPLICIT
- Below 0.50: Flag for human review, classify as EXPLICIT

Edge Cases - Always classify as EXPLICIT:
- Mixed signals (both explicit and implied indicators present)
- Unrecognized slang or regional terms
- Emoji-only or emoji-heavy with minimal text
- Very short captions (<10 words) unless clearly teasing
- Non-English text

## CONTENT TYPE MAPPING

When classifying as IMPLIED:
- pussy_play (16) --> implied_pussy_play (34)
- solo (19) --> implied_solo (35)
- tits_play (18) --> implied_tits_play (36)
- toy_play (17) --> implied_toy_play (37)

## EXAMPLES

### EXPLICIT Examples:
1. "Look at my pretty pink pussy dripping for you baby" -> EXPLICIT (direct anatomy + fluid)
2. "Spreading my legs so you can see everything" -> EXPLICIT (action + showing)
3. "POV: you're watching me play with my wet pussy" -> EXPLICIT (POV + anatomy + action)
4. "Just shaved my pussy smooth" -> EXPLICIT (post-reveal state)

### IMPLIED Examples:
1. "Do you wanna see what's hiding under these panties?" -> IMPLIED (question + hidden)
2. "My little kitty is so wet... wanna come play?" -> IMPLIED (euphemism + question)
3. "I'll show you my secret if you tip" -> IMPLIED (future tense promise)
4. "Watch me slowly slide off this dress... what's underneath?" -> IMPLIED (pre-reveal + question)

### EDGE CASE (Mixed -> EXPLICIT):
"Wanna see my pussy? Here it is baby, all creamy" -> EXPLICIT (delivers content despite question start)

## OUTPUT FORMAT

Return valid JSON only:
{
  "classifications": [
    {
      "caption_id": <int>,
      "classification": "EXPLICIT" | "IMPLIED",
      "new_content_type_id": <int>,
      "confidence": <float>,
      "reasoning": "<max 50 words>",
      "indicators_found": ["<indicator>", ...]
    }
  ],
  "batch_summary": {
    "total": <int>,
    "explicit_count": <int>,
    "implied_count": <int>,
    "low_confidence_count": <int>,
    "flagged_for_review": [<caption_ids with confidence < 0.65>]
  }
}
"""

# Content type ID mappings
CONTENT_TYPE_MAPPING = {
    16: 34,  # pussy_play -> implied_pussy_play
    17: 37,  # toy_play -> implied_toy_play
    18: 36,  # tits_play -> implied_tits_play
    19: 35,  # solo -> implied_solo
}

ELIGIBLE_CONTENT_TYPES = list(CONTENT_TYPE_MAPPING.keys())


def get_database_path() -> str:
    """Get database path from environment or default location."""
    return os.environ.get(
        "EROS_DATABASE_PATH",
        os.path.expanduser("~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"),
    )


def fetch_captions_for_classification(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    caption_ids: list[int] | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Fetch captions eligible for classification."""

    query = """
        SELECT
            c.caption_id,
            c.caption_text,
            c.content_type_id,
            ct.type_name as content_type_name,
            c.page_name
        FROM caption_bank c
        JOIN content_types ct ON c.content_type_id = ct.content_type_id
        WHERE c.content_type_id IN ({})
    """.format(",".join("?" * len(ELIGIBLE_CONTENT_TYPES)))

    params: list[Any] = list(ELIGIBLE_CONTENT_TYPES)

    if creator_name and creator_name.lower() != "all":
        query += " AND LOWER(c.page_name) = LOWER(?)"
        params.append(creator_name)

    if caption_ids:
        query += " AND c.caption_id IN ({})".format(",".join("?" * len(caption_ids)))
        params.extend(caption_ids)

    query += f" LIMIT {limit}"

    cursor = conn.execute(query, params)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def prepare_batch_for_classification(captions: list[dict]) -> str:
    """Prepare captions as JSON for the classification prompt."""
    batch = [
        {
            "caption_id": c["caption_id"],
            "current_content_type_id": c["content_type_id"],
            "caption_text": c["caption_text"],
        }
        for c in captions
    ]
    return json.dumps(batch, indent=2)


def build_user_prompt(captions_json: str, batch_size: int) -> str:
    """Build the user prompt with the captions batch."""
    return f"""
## CAPTIONS TO CLASSIFY

Process this batch of {batch_size} captions:

---BEGIN BATCH---
{captions_json}
---END BATCH---

Classify each caption following the rules in your instructions. Return only valid JSON.
"""


def validate_classification_response(response: dict) -> tuple[bool, str]:
    """Validate the structure of the classification response."""

    if "classifications" not in response:
        return False, "Missing 'classifications' key"

    if not isinstance(response["classifications"], list):
        return False, "'classifications' must be a list"

    required_fields = ["caption_id", "classification", "new_content_type_id", "confidence"]

    for i, item in enumerate(response["classifications"]):
        for field in required_fields:
            if field not in item:
                return False, f"Classification {i} missing '{field}'"

        if item["classification"] not in ["EXPLICIT", "IMPLIED"]:
            return False, f"Classification {i} has invalid classification value"

        if not 0 <= item["confidence"] <= 1:
            return False, f"Classification {i} has invalid confidence score"

    return True, "Valid"


def apply_classifications(
    conn: sqlite3.Connection, classifications: list[dict], dry_run: bool = True
) -> dict[str, Any]:
    """Apply classifications to the database."""

    results = {"updated": 0, "skipped": 0, "errors": [], "details": []}

    for item in classifications:
        caption_id = item["caption_id"]
        classification = item["classification"]
        new_type_id = item["new_content_type_id"]
        confidence = item["confidence"]

        if classification == "EXPLICIT":
            results["skipped"] += 1
            results["details"].append(
                {
                    "caption_id": caption_id,
                    "action": "SKIPPED",
                    "reason": "Classified as EXPLICIT, keeping original type",
                }
            )
            continue

        if confidence < 0.65:
            results["skipped"] += 1
            results["details"].append(
                {
                    "caption_id": caption_id,
                    "action": "SKIPPED",
                    "reason": f"Low confidence ({confidence:.2f}), needs human review",
                }
            )
            continue

        if not dry_run:
            try:
                conn.execute(
                    "UPDATE captions SET content_type_id = ? WHERE caption_id = ?",
                    (new_type_id, caption_id),
                )
                results["updated"] += 1
                results["details"].append(
                    {"caption_id": caption_id, "action": "UPDATED", "new_type_id": new_type_id}
                )
            except Exception as e:
                results["errors"].append({"caption_id": caption_id, "error": str(e)})
        else:
            results["updated"] += 1
            results["details"].append(
                {"caption_id": caption_id, "action": "WOULD_UPDATE", "new_type_id": new_type_id}
            )

    if not dry_run:
        conn.commit()

    return results


def generate_report(
    captions: list[dict], classifications: dict, results: dict, dry_run: bool
) -> str:
    """Generate a classification report."""

    report_lines = [
        "=" * 60,
        "EROS CONTENT CLASSIFICATION REPORT",
        f"Generated: {datetime.now().isoformat()}",
        f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}",
        "=" * 60,
        "",
        "BATCH SUMMARY",
        "-" * 40,
    ]

    if "batch_summary" in classifications:
        summary = classifications["batch_summary"]
        report_lines.extend(
            [
                f"Total Captions: {summary.get('total', len(captions))}",
                f"Classified EXPLICIT: {summary.get('explicit_count', 'N/A')}",
                f"Classified IMPLIED: {summary.get('implied_count', 'N/A')}",
                f"Low Confidence: {summary.get('low_confidence_count', 'N/A')}",
                f"Flagged for Review: {summary.get('flagged_for_review', [])}",
            ]
        )

    report_lines.extend(
        [
            "",
            "UPDATE RESULTS",
            "-" * 40,
            f"Updated: {results['updated']}",
            f"Skipped: {results['skipped']}",
            f"Errors: {len(results['errors'])}",
            "",
        ]
    )

    if results["errors"]:
        report_lines.append("ERRORS:")
        for err in results["errors"]:
            report_lines.append(f"  - Caption {err['caption_id']}: {err['error']}")
        report_lines.append("")

    # Low confidence items
    low_conf = [
        c for c in classifications.get("classifications", []) if c.get("confidence", 1.0) < 0.65
    ]
    if low_conf:
        report_lines.extend(["LOW CONFIDENCE ITEMS (Needs Human Review)", "-" * 40])
        for item in low_conf:
            report_lines.append(
                f"  Caption {item['caption_id']}: {item['classification']} "
                f"(conf: {item['confidence']:.2f}) - {item.get('reasoning', 'No reason provided')}"
            )
        report_lines.append("")

    report_lines.append("=" * 60)

    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Classify OnlyFans captions as EXPLICIT or IMPLIED"
    )
    parser.add_argument(
        "--creator", type=str, default="all", help="Creator page name or 'all' for all creators"
    )
    parser.add_argument(
        "--caption-ids", type=str, help="Comma-separated list of specific caption IDs to classify"
    )
    parser.add_argument(
        "--batch-size", type=int, default=50, help="Number of captions per batch (default: 50)"
    )
    parser.add_argument(
        "--limit", type=int, default=1000, help="Maximum total captions to process (default: 1000)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without updating database"
    )
    parser.add_argument(
        "--db", type=str, help="Path to EROS database (overrides EROS_DATABASE_PATH)"
    )
    parser.add_argument(
        "--output-prompts",
        action="store_true",
        help="Output the prompts for manual testing (no API calls)",
    )

    args = parser.parse_args()

    # Get database path
    db_path = args.db or get_database_path()

    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # Parse caption IDs if provided
    caption_ids = None
    if args.caption_ids:
        caption_ids = [int(x.strip()) for x in args.caption_ids.split(",")]

    # Connect to database
    conn = sqlite3.connect(db_path)

    try:
        # Fetch captions
        print(f"Fetching captions from {db_path}...")
        captions = fetch_captions_for_classification(
            conn, creator_name=args.creator, caption_ids=caption_ids, limit=args.limit
        )

        if not captions:
            print("No captions found matching criteria.")
            sys.exit(0)

        print(f"Found {len(captions)} captions to classify")

        # Output prompts mode (for testing)
        if args.output_prompts:
            batch = captions[: args.batch_size]
            captions_json = prepare_batch_for_classification(batch)
            user_prompt = build_user_prompt(captions_json, len(batch))

            print("\n" + "=" * 60)
            print("SYSTEM PROMPT")
            print("=" * 60)
            print(CLASSIFICATION_SYSTEM_PROMPT)
            print("\n" + "=" * 60)
            print("USER PROMPT")
            print("=" * 60)
            print(user_prompt)
            sys.exit(0)

        # TODO: Implement actual Claude API call here
        # For now, this is a placeholder that shows the structure
        print("\n" + "=" * 60)
        print("IMPLEMENTATION NOTE")
        print("=" * 60)
        print("This script prepares the prompts and handles the database updates.")
        print("To run actual classifications, integrate with Claude API:")
        print("")
        print("1. Use CLASSIFICATION_SYSTEM_PROMPT as the system message")
        print("2. Use build_user_prompt() output as the user message")
        print("3. Parse JSON response and call apply_classifications()")
        print("")
        print("Run with --output-prompts to see the exact prompts for testing.")
        print("=" * 60)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
