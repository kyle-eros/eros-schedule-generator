#!/usr/bin/env python3
"""
Select Captions - Caption selection using Vose Alias Method.

This script implements weighted random selection of captions using
the Vose Alias Method for O(1) selection time after O(n) preprocessing.

The selection weight combines:
- Performance score (60% weight)
- Freshness score (40% weight)
- Persona boost (1.0-1.4x multiplier)

Usage:
    python select_captions.py --creator missalexa --count 10
    python select_captions.py --creator-id abc123 --count 20 --content-type solo
    python select_captions.py --creator missalexa --count 5 --output captions.json
"""

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from utils import VoseAliasSelector

# Try to import quality scoring module
try:
    from quality_scoring import QualityScorer, CreatorProfile as QSCreatorProfile
    QUALITY_SCORING_AVAILABLE = True
except ImportError:
    QUALITY_SCORING_AVAILABLE = False

# Path resolution for database
SCRIPT_DIR = Path(__file__).parent

# Database path resolution with multiple candidate locations
# Standard order: 1) env var, 2) Developer, 3) Documents, 4) .eros fallback
HOME_DIR = Path.home()

# Build candidates list with env var first (if set)
_env_db_path = os.environ.get("EROS_DATABASE_PATH", "")
DB_PATH_CANDIDATES = [
    Path(_env_db_path) if _env_db_path else None,
    HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / ".eros" / "eros.db",
]
DB_PATH_CANDIDATES = [p for p in DB_PATH_CANDIDATES if p is not None]

DB_PATH = next((p for p in DB_PATH_CANDIDATES if p.exists()), DB_PATH_CANDIDATES[1] if len(DB_PATH_CANDIDATES) > 1 else DB_PATH_CANDIDATES[0])


@dataclass
class Caption:
    """Caption data for selection."""

    caption_id: int
    caption_text: str
    caption_type: str
    content_type_id: int | None
    content_type_name: str | None
    performance_score: float
    freshness_score: float
    tone: str | None
    emoji_style: str | None
    slang_level: str | None
    is_universal: bool
    combined_score: float = 0.0
    persona_boost: float = 1.0
    final_weight: float = 0.0


def calculate_persona_boost(caption: Caption, persona: dict[str, str]) -> float:
    """
    Calculate persona boost factor for a caption.

    Boost factors:
    - Primary tone match: 1.20x
    - Emoji frequency match: 1.10x (cumulative)
    - Slang level match: 1.10x (cumulative)
    - Maximum combined: 1.40x (capped)

    Args:
        caption: Caption to evaluate
        persona: Creator persona dict with primary_tone, emoji_frequency, slang_level

    Returns:
        Boost factor between 1.0 and 1.4
    """
    boost = 1.0

    # Primary tone match (1.20x)
    if caption.tone and persona.get("primary_tone"):
        if caption.tone.lower() == persona["primary_tone"].lower():
            boost *= 1.20

    # Emoji frequency match (1.10x)
    if caption.emoji_style and persona.get("emoji_frequency"):
        if caption.emoji_style.lower() == persona["emoji_frequency"].lower():
            boost *= 1.10

    # Slang level match (1.10x)
    if caption.slang_level and persona.get("slang_level"):
        if caption.slang_level.lower() == persona["slang_level"].lower():
            boost *= 1.10

    # Cap at 1.40x
    return min(boost, 1.40)


def calculate_weight(
    caption: Caption,
    performance_weight: float = 0.4,  # Changed from 0.6
    freshness_weight: float = 0.2,     # Changed from 0.4
    quality_weight: float = 0.4,       # NEW
    quality_score: float = 0.5         # NEW (default middle)
) -> float:
    """
    Calculate selection weight for a caption.

    NEW Formula: (perf * 0.4 + fresh * 0.2 + quality * 0.4) * persona_boost

    The updated formula incorporates LLM-based quality scoring for
    better caption selection. Quality score is optional and defaults
    to a neutral 0.5 (middle of 0-1 range) for backward compatibility.

    Args:
        caption: Caption to weight
        performance_weight: Weight for performance score (default 0.4)
        freshness_weight: Weight for freshness score (default 0.2)
        quality_weight: Weight for quality score (default 0.4)
        quality_score: Quality score 0-1 (default 0.5 = neutral)

    Returns:
        Final selection weight
    """
    # Quality score needs to be scaled to 0-100 to match performance/freshness
    quality_normalized = quality_score * 100

    base_weight = (
        (caption.performance_score * performance_weight) +
        (caption.freshness_score * freshness_weight) +
        (quality_normalized * quality_weight)
    )
    return base_weight * caption.persona_boost


def load_captions(
    conn: sqlite3.Connection,
    creator_id: str,
    min_freshness: float = 30.0,
    content_type: str | None = None
) -> list[Caption]:
    """
    Load eligible captions from database.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        min_freshness: Minimum freshness score
        content_type: Optional content type filter

    Returns:
        List of Caption objects
    """
    query = """
        SELECT
            cb.caption_id,
            cb.caption_text,
            cb.caption_type,
            cb.content_type_id,
            ct.type_name AS content_type_name,
            cb.performance_score,
            cb.freshness_score,
            cb.tone,
            cb.emoji_style,
            cb.slang_level,
            cb.is_universal
        FROM caption_bank cb
        LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
        LEFT JOIN vault_matrix vm ON cb.creator_id = vm.creator_id
            AND cb.content_type_id = vm.content_type_id
        WHERE cb.is_active = 1
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= ?
          AND (vm.has_content = 1 OR vm.vault_id IS NULL OR cb.content_type_id IS NULL)
    """

    params: list[Any] = [creator_id, min_freshness]

    if content_type:
        query += " AND ct.type_name = ?"
        params.append(content_type)

    query += " ORDER BY cb.performance_score DESC, cb.freshness_score DESC"

    cursor = conn.execute(query, params)

    captions = []
    for row in cursor.fetchall():
        captions.append(Caption(
            caption_id=row["caption_id"],
            caption_text=row["caption_text"],
            caption_type=row["caption_type"],
            content_type_id=row["content_type_id"],
            content_type_name=row["content_type_name"],
            performance_score=row["performance_score"] or 50.0,
            freshness_score=row["freshness_score"] or 100.0,
            tone=row["tone"],
            emoji_style=row["emoji_style"],
            slang_level=row["slang_level"],
            is_universal=bool(row["is_universal"])
        ))

    return captions


def load_persona(conn: sqlite3.Connection, creator_id: str) -> dict[str, str]:
    """Load creator persona from database."""
    query = """
        SELECT primary_tone, emoji_frequency, slang_level
        FROM creator_personas
        WHERE creator_id = ?
    """
    cursor = conn.execute(query, (creator_id,))
    row = cursor.fetchone()

    if row:
        return {
            "primary_tone": row["primary_tone"] or "",
            "emoji_frequency": row["emoji_frequency"] or "",
            "slang_level": row["slang_level"] or ""
        }

    return {}


def select_captions(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None,
    count: int = 10,
    min_freshness: float = 30.0,
    content_type: str | None = None,
    use_persona: bool = True,
    use_quality_scoring: bool = False  # NEW parameter
) -> list[Caption]:
    """
    Select captions using weighted random selection.

    Args:
        conn: Database connection
        creator_name: Creator page name (optional)
        creator_id: Creator UUID (optional)
        count: Number of captions to select
        min_freshness: Minimum freshness score
        content_type: Optional content type filter
        use_persona: Whether to apply persona boost
        use_quality_scoring: Enable LLM-based quality scoring (requires quality_scoring module)

    Returns:
        List of selected Caption objects
    """
    # Resolve creator ID
    if creator_name and not creator_id:
        cursor = conn.execute(
            "SELECT creator_id FROM creators WHERE page_name = ? OR display_name = ?",
            (creator_name, creator_name)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Creator not found: {creator_name}")
        creator_id = row["creator_id"]

    if not creator_id:
        raise ValueError("Must provide creator_name or creator_id")

    # Load captions
    captions = load_captions(conn, creator_id, min_freshness, content_type)

    if not captions:
        return []

    # Load persona and calculate boosts
    persona = {}
    if use_persona:
        persona = load_persona(conn, creator_id)

    # Load quality scores if enabled
    quality_scores: dict[int, Any] = {}
    if use_quality_scoring and QUALITY_SCORING_AVAILABLE:
        print("Loading quality scores...", file=sys.stderr)
        scorer = QualityScorer(conn)

        # Get creator profile for quality scoring context
        profile_query = """
            SELECT c.page_name, cp.primary_tone, cp.emoji_frequency, cp.slang_level
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.creator_id = ?
        """
        cursor = conn.execute(profile_query, (creator_id,))
        profile_row = cursor.fetchone()

        if profile_row:
            qs_profile = QSCreatorProfile(
                creator_id=creator_id,
                page_name=profile_row["page_name"] or "",
                primary_tone=profile_row["primary_tone"] or "playful",
                emoji_frequency=profile_row["emoji_frequency"] or "moderate",
                slang_level=profile_row["slang_level"] or "light",
            )

            quality_scores = scorer.score_caption_batch(
                [{"caption_id": c.caption_id, "caption_text": c.caption_text} for c in captions],
                qs_profile
            )
            print(f"Quality scored {len(quality_scores)} captions", file=sys.stderr)
    elif use_quality_scoring and not QUALITY_SCORING_AVAILABLE:
        print("Warning: Quality scoring requested but module not available", file=sys.stderr)

    for caption in captions:
        caption.persona_boost = calculate_persona_boost(caption, persona)

        # Get quality score if available (default 0.5 = neutral)
        quality_score = 0.5
        if caption.caption_id in quality_scores:
            quality_score = quality_scores[caption.caption_id].overall_score

        # Calculate combined score with quality-enhanced formula
        # NEW: (perf * 0.4 + fresh * 0.2 + quality * 0.4)
        caption.combined_score = (
            caption.performance_score * 0.4 +
            caption.freshness_score * 0.2 +
            (quality_score * 100) * 0.4  # Scale to 0-100
        )
        caption.final_weight = caption.combined_score * caption.persona_boost

    # Build selector
    try:
        selector = VoseAliasSelector(captions, lambda c: c.final_weight)
    except ValueError as e:
        print(f"Warning: {e}, returning top captions by score", file=sys.stderr)
        return sorted(captions, key=lambda c: c.final_weight, reverse=True)[:count]

    # Select captions (no duplicates)
    selected = selector.select_multiple(count, allow_duplicates=False)

    return selected


def format_markdown(captions: list[Caption]) -> str:
    """Format selected captions as Markdown."""
    lines = [
        "# Selected Captions",
        "",
        f"**Total Selected:** {len(captions)}",
        "",
        "| # | ID | Type | Perf | Fresh | Boost | Weight | Preview |",
        "|---|-----|------|------|-------|-------|--------|---------|"
    ]

    for i, c in enumerate(captions, 1):
        preview = c.caption_text[:50] + "..." if len(c.caption_text) > 50 else c.caption_text
        preview = preview.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {i} | {c.caption_id} | {c.content_type_name or 'N/A'} | "
            f"{c.performance_score:.1f} | {c.freshness_score:.1f} | "
            f"{c.persona_boost:.2f}x | {c.final_weight:.1f} | {preview} |"
        )

    lines.append("")
    return "\n".join(lines)


def format_json(captions: list[Caption]) -> str:
    """Format selected captions as JSON."""
    data = [
        {
            "caption_id": c.caption_id,
            "caption_text": c.caption_text,
            "caption_type": c.caption_type,
            "content_type_id": c.content_type_id,
            "content_type_name": c.content_type_name,
            "performance_score": round(c.performance_score, 2),
            "freshness_score": round(c.freshness_score, 2),
            "persona_boost": round(c.persona_boost, 2),
            "final_weight": round(c.final_weight, 2)
        }
        for c in captions
    ]
    return json.dumps(data, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Select captions using weighted random selection (Vose Alias Method).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python select_captions.py --creator missalexa --count 10
    python select_captions.py --creator-id abc123 --count 20 --content-type solo
    python select_captions.py --creator missalexa --count 5 --output captions.json --format json
    python select_captions.py --creator missalexa --count 10 --use-quality

Weight Formula (NEW with quality scoring):
    weight = (performance * 0.4 + freshness * 0.2 + quality * 0.4) * persona_boost

    Without --use-quality, quality score defaults to 0.5 (neutral).

Persona Boosts:
    - Primary tone match: 1.20x
    - Emoji frequency match: 1.10x
    - Slang level match: 1.10x
    - Maximum combined: 1.40x
        """
    )

    parser.add_argument(
        "--creator", "-c",
        help="Creator page name (e.g., missalexa)"
    )
    parser.add_argument(
        "--creator-id",
        help="Creator UUID"
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Number of captions to select (default: 10)"
    )
    parser.add_argument(
        "--content-type", "-t",
        help="Filter by content type (e.g., solo, bg)"
    )
    parser.add_argument(
        "--min-freshness",
        type=float,
        default=30.0,
        help="Minimum freshness score (default: 30)"
    )
    parser.add_argument(
        "--no-persona",
        action="store_true",
        help="Disable persona boost"
    )
    parser.add_argument(
        "--use-quality",
        action="store_true",
        help="Enable LLM-based quality scoring"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help=f"Database path (default: {DB_PATH})"
    )

    args = parser.parse_args()

    if not args.creator and not args.creator_id:
        parser.error("Must specify --creator or --creator-id")

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        captions = select_captions(
            conn,
            creator_name=args.creator,
            creator_id=args.creator_id,
            count=args.count,
            min_freshness=args.min_freshness,
            content_type=args.content_type,
            use_persona=not args.no_persona,
            use_quality_scoring=args.use_quality
        )

        if not captions:
            print("No eligible captions found", file=sys.stderr)
            sys.exit(1)

        if args.format == "json":
            output = format_json(captions)
        else:
            output = format_markdown(captions)

        if args.output:
            Path(args.output).write_text(output)
            print(f"Captions written to {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
