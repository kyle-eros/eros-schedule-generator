#!/usr/bin/env python3
"""
Calculate Freshness - Freshness score calculation with exponential decay.

This script calculates freshness scores for captions using an exponential
decay formula with adjustments for usage patterns and performance.

Formula:
    base_freshness = 100 * (1 - e^(-days_since_use / half_life))

Adjustments:
    - Heavy use penalty: -10 per use above 5 uses
    - Winner bonus: +15 for performance >= 80
    - New caption boost: +20 if never used

Usage:
    python calculate_freshness.py --batch
    python calculate_freshness.py --caption-id 12345
    python calculate_freshness.py --creator missalexa --update
"""

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Path resolution for database
SCRIPT_DIR = Path(__file__).parent

from database import DB_PATH  # noqa: E402

# Default configuration
DEFAULT_HALF_LIFE_DAYS = 14.0
DEFAULT_MIN_FRESHNESS = 30.0
DEFAULT_EXHAUSTION_THRESHOLD = 25.0
HEAVY_USE_THRESHOLD = 5
HEAVY_USE_PENALTY = 10.0
WINNER_THRESHOLD = 80.0
WINNER_BONUS = 15.0
NEW_CAPTION_BOOST = 20.0


@dataclass
class FreshnessResult:
    """Result of freshness calculation."""

    caption_id: int
    caption_text: str | None
    current_freshness: float
    new_freshness: float
    days_since_used: int | None
    times_used: int
    performance_score: float
    adjustments: list[str]


def calculate_freshness(
    last_used_date: date | str | None,
    reference_date: date | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    times_used: int = 0,
    performance_score: float = 50.0,
) -> tuple[float, int | None, list[str]]:
    """
    Calculate freshness score using exponential decay with adjustments.

    Formula:
        base_freshness = 100 * (1 - e^(-days_since_use / half_life))

    Adjustments:
        - Never used: +20 boost (starts at 100 + boost)
        - Heavy use (>5): -10 per use above 5
        - Winner (perf >= 80): +15 bonus

    Args:
        last_used_date: Date caption was last used (None if never used)
        reference_date: Date to calculate from (default: today)
        half_life_days: Number of days for 50% decay (default: 14)
        times_used: Total number of times caption has been used
        performance_score: Caption's performance score (0-100)

    Returns:
        Tuple of (freshness_score, days_since_used, adjustments_list)

    Examples:
        >>> calculate_freshness(None)  # Never used
        (100.0, None, ['New caption boost: +20'])

        >>> calculate_freshness(date(2025, 1, 1), date(2025, 1, 15))  # 14 days ago
        (50.0, 14, [])

        >>> calculate_freshness(date(2025, 1, 1), date(2025, 1, 8))  # 7 days ago
        (70.7, 7, [])
    """
    if reference_date is None:
        reference_date = date.today()

    adjustments: list[str] = []

    # Handle never-used captions
    if last_used_date is None:
        freshness = 100.0
        adjustments.append(f"New caption boost: +{NEW_CAPTION_BOOST}")
        freshness = min(freshness + NEW_CAPTION_BOOST, 100.0)  # Cap at 100

        # Still apply winner bonus
        if performance_score >= WINNER_THRESHOLD:
            # Winner bonus for new captions with proven performance elsewhere
            pass  # No additional boost for new captions

        return (freshness, None, adjustments)

    # Parse date if string
    if isinstance(last_used_date, str):
        try:
            last_used_date = datetime.strptime(last_used_date, "%Y-%m-%d").date()
        except ValueError:
            # Try ISO format with time
            try:
                last_used_date = datetime.fromisoformat(last_used_date).date()
            except ValueError:
                return (100.0, None, ["Could not parse last_used_date"])

    # Calculate days since use
    days_since = (reference_date - last_used_date).days

    if days_since < 0:
        # Future date - treat as fresh
        return (100.0, days_since, ["Future last_used_date"])

    # Base exponential decay formula
    # freshness = 100 * (1 - e^(-days / half_life))
    # This gives:
    # - 0 days: 0% fresh (just used)
    # - 7 days: ~39.3% fresh
    # - 14 days: ~63.2% fresh
    # - 28 days: ~86.5% fresh
    # - 42 days: ~95.0% fresh

    # Alternative interpretation: decay FROM 100
    # freshness = 100 * e^(-days * ln(2) / half_life)
    # This gives:
    # - 0 days: 100% fresh
    # - 7 days: ~70.7% fresh (half-life / 2)
    # - 14 days: ~50.0% fresh (half-life)
    # - 28 days: ~25.0% fresh
    # - 42 days: ~12.5% fresh

    # Using the decay interpretation (starts at 100, decays down)
    decay_rate = math.log(2) / half_life_days
    freshness = 100.0 * math.exp(-decay_rate * days_since)

    # Apply heavy use penalty
    if times_used > HEAVY_USE_THRESHOLD:
        excess_uses = times_used - HEAVY_USE_THRESHOLD
        penalty = excess_uses * HEAVY_USE_PENALTY
        freshness -= penalty
        adjustments.append(
            f"Heavy use penalty: -{penalty:.1f} ({excess_uses} uses above {HEAVY_USE_THRESHOLD})"
        )

    # Apply winner bonus
    if performance_score >= WINNER_THRESHOLD:
        freshness += WINNER_BONUS
        adjustments.append(f"Winner bonus: +{WINNER_BONUS} (perf >= {WINNER_THRESHOLD})")

    # Clamp to valid range
    freshness = max(0.0, min(100.0, freshness))

    return (round(freshness, 2), days_since, adjustments)


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_caption_freshness(
    conn: sqlite3.Connection, caption_id: int
) -> FreshnessResult | None:
    """
    Calculate freshness for a single caption.

    Args:
        conn: Database connection
        caption_id: Caption ID to calculate

    Returns:
        FreshnessResult or None if caption not found
    """
    query = """
        SELECT
            caption_id,
            caption_text,
            freshness_score,
            last_used_date,
            times_used,
            performance_score
        FROM caption_bank
        WHERE caption_id = ?
    """

    cursor = conn.execute(query, (caption_id,))
    row = cursor.fetchone()

    if not row:
        return None

    new_freshness, days_since, adjustments = calculate_freshness(
        last_used_date=row["last_used_date"],
        times_used=row["times_used"] or 0,
        performance_score=row["performance_score"] or 50.0,
    )

    return FreshnessResult(
        caption_id=row["caption_id"],
        caption_text=row["caption_text"],
        current_freshness=row["freshness_score"] or 100.0,
        new_freshness=new_freshness,
        days_since_used=days_since,
        times_used=row["times_used"] or 0,
        performance_score=row["performance_score"] or 50.0,
        adjustments=adjustments,
    )


def update_all_freshness_scores(
    conn: sqlite3.Connection, dry_run: bool = True, creator_id: str | None = None
) -> list[FreshnessResult]:
    """
    Calculate and optionally update freshness for all captions.

    Args:
        conn: Database connection
        dry_run: If True, only calculate without updating
        creator_id: Optional filter by creator

    Returns:
        List of FreshnessResult for all processed captions
    """
    query = """
        SELECT
            caption_id,
            caption_text,
            freshness_score,
            last_used_date,
            times_used,
            performance_score,
            creator_id
        FROM caption_bank
        WHERE is_active = 1
    """

    params: list[Any] = []
    if creator_id:
        query += " AND (creator_id = ? OR is_universal = 1)"
        params.append(creator_id)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    results = []
    updates = []

    for row in rows:
        new_freshness, days_since, adjustments = calculate_freshness(
            last_used_date=row["last_used_date"],
            times_used=row["times_used"] or 0,
            performance_score=row["performance_score"] or 50.0,
        )

        result = FreshnessResult(
            caption_id=row["caption_id"],
            caption_text=row["caption_text"][:100] + "..."
            if row["caption_text"] and len(row["caption_text"]) > 100
            else row["caption_text"],
            current_freshness=row["freshness_score"] or 100.0,
            new_freshness=new_freshness,
            days_since_used=days_since,
            times_used=row["times_used"] or 0,
            performance_score=row["performance_score"] or 50.0,
            adjustments=adjustments,
        )
        results.append(result)

        # Track if update is needed
        if abs(result.new_freshness - result.current_freshness) > 0.01:
            updates.append((new_freshness, row["caption_id"]))

    # Perform updates if not dry run
    if not dry_run and updates:
        conn.executemany(
            "UPDATE caption_bank SET freshness_score = ?, updated_at = datetime('now') WHERE caption_id = ?",
            updates,
        )
        conn.commit()

    return results


def format_markdown(results: list[FreshnessResult], updated: bool = False) -> str:
    """Format results as Markdown."""
    action = "Updated" if updated else "Calculated"

    lines = [
        f"# Freshness Score {action}",
        "",
        f"**Total Captions:** {len(results)}",
        f"**Formula:** `freshness = 100 * e^(-days * ln(2) / {DEFAULT_HALF_LIFE_DAYS})`",
        "",
        "## Results",
        "",
        "| ID | Days Since | Times Used | Perf | Current | New | Change | Adjustments |",
        "|----|------------|------------|------|---------|-----|--------|-------------|",
    ]

    # Sort by change magnitude
    results_sorted = sorted(
        results, key=lambda r: abs(r.new_freshness - r.current_freshness), reverse=True
    )

    for r in results_sorted[:50]:  # Limit to top 50
        days_str = str(r.days_since_used) if r.days_since_used is not None else "Never"
        change = r.new_freshness - r.current_freshness
        change_str = f"+{change:.1f}" if change >= 0 else f"{change:.1f}"
        adjustments_str = "; ".join(r.adjustments) if r.adjustments else "-"

        lines.append(
            f"| {r.caption_id} | {days_str} | {r.times_used} | "
            f"{r.performance_score:.0f} | {r.current_freshness:.1f} | "
            f"{r.new_freshness:.1f} | {change_str} | {adjustments_str} |"
        )

    if len(results) > 50:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | ({len(results) - 50} more) |")

    lines.append("")

    # Summary statistics
    avg_current = sum(r.current_freshness for r in results) / len(results) if results else 0
    avg_new = sum(r.new_freshness for r in results) / len(results) if results else 0
    exhausted = sum(1 for r in results if r.new_freshness < DEFAULT_EXHAUSTION_THRESHOLD)
    stale = sum(
        1
        for r in results
        if DEFAULT_EXHAUSTION_THRESHOLD <= r.new_freshness < DEFAULT_MIN_FRESHNESS
    )
    fresh = sum(1 for r in results if r.new_freshness >= DEFAULT_MIN_FRESHNESS)

    lines.extend(
        [
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Average Current | {avg_current:.1f} |",
            f"| Average New | {avg_new:.1f} |",
            f"| Fresh (>= {DEFAULT_MIN_FRESHNESS}) | {fresh} |",
            f"| Stale ({DEFAULT_EXHAUSTION_THRESHOLD}-{DEFAULT_MIN_FRESHNESS}) | {stale} |",
            f"| Exhausted (< {DEFAULT_EXHAUSTION_THRESHOLD}) | {exhausted} |",
            "",
        ]
    )

    return "\n".join(lines)


def format_json(results: list[FreshnessResult]) -> str:
    """Format results as JSON."""
    data = [
        {
            "caption_id": r.caption_id,
            "current_freshness": r.current_freshness,
            "new_freshness": r.new_freshness,
            "days_since_used": r.days_since_used,
            "times_used": r.times_used,
            "performance_score": r.performance_score,
            "adjustments": r.adjustments,
        }
        for r in results
    ]
    return json.dumps(data, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Calculate freshness scores with exponential decay.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Freshness Formula:
    freshness = 100 * e^(-days * ln(2) / half_life)

    With 14-day half-life:
    - 0 days: 100% fresh
    - 7 days: ~70.7% fresh
    - 14 days: ~50.0% fresh
    - 28 days: ~25.0% fresh

Adjustments:
    - New caption (never used): +20 boost
    - Heavy use (>5 times): -10 per excess use
    - Winner (perf >= 80): +15 bonus

Examples:
    python calculate_freshness.py --batch
    python calculate_freshness.py --caption-id 12345
    python calculate_freshness.py --creator missalexa --update
        """,
    )

    parser.add_argument("--batch", "-b", action="store_true", help="Process all active captions")
    parser.add_argument("--caption-id", type=int, help="Calculate for specific caption ID")
    parser.add_argument("--creator", "-c", help="Filter by creator page name")
    parser.add_argument(
        "--update",
        "-u",
        action="store_true",
        help="Update database with new scores (default: dry run)",
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--half-life",
        type=float,
        default=DEFAULT_HALF_LIFE_DAYS,
        help=f"Half-life in days (default: {DEFAULT_HALF_LIFE_DAYS})",
    )
    parser.add_argument("--db", default=str(DB_PATH), help=f"Database path (default: {DB_PATH})")

    args = parser.parse_args()

    if not args.batch and not args.caption_id:
        parser.error("Must specify --batch or --caption-id")

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        if args.caption_id:
            # Single caption
            result = calculate_caption_freshness(conn, args.caption_id)
            if not result:
                print(f"Error: Caption {args.caption_id} not found", file=sys.stderr)
                sys.exit(1)

            results = [result]

            if args.update:
                conn.execute(
                    "UPDATE caption_bank SET freshness_score = ?, updated_at = datetime('now') WHERE caption_id = ?",
                    (result.new_freshness, result.caption_id),
                )
                conn.commit()
        else:
            # Batch processing
            creator_id = None
            if args.creator:
                cursor = conn.execute(
                    "SELECT creator_id FROM creators WHERE page_name = ? OR display_name = ?",
                    (args.creator, args.creator),
                )
                row = cursor.fetchone()
                if row:
                    creator_id = row["creator_id"]

            results = update_all_freshness_scores(
                conn, dry_run=not args.update, creator_id=creator_id
            )

        # Format output
        if args.format == "json":
            output = format_json(results)
        else:
            output = format_markdown(results, updated=args.update)

        if args.output:
            Path(args.output).write_text(output)
            print(f"Results written to {args.output}")
        else:
            print(output)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
