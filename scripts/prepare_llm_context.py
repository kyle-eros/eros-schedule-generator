#!/usr/bin/env python3
"""
Prepare LLM Context - Unified context generator for native Claude processing.

This script prepares structured output that Claude processes natively during
skill execution. Unlike API-based approaches, this leverages Claude Code's
built-in intelligence by outputting markdown that becomes part of the conversation.

The workflow:
1. User invokes skill: "generate schedule for missalexa"
2. This script runs and outputs structured context + data
3. Claude reads the output and applies semantic analysis
4. Claude produces the enhanced schedule directly

Output Format:
    The script outputs a structured markdown document containing:
    - Creator profile and persona
    - Captions needing semantic analysis (with pattern-based preliminary scores)
    - Clear instructions for Claude to apply semantic reasoning
    - Expected output format for the enhanced schedule

Usage:
    python prepare_llm_context.py --creator missalexa --week 2025-W01
    python prepare_llm_context.py --creator missalexa --week 2025-W01 --mode full
    python prepare_llm_context.py --creator missalexa --week 2025-W01 --mode quick

Modes:
    quick - Pattern matching only, no LLM semantic analysis (fast)
    full  - Full semantic analysis with Claude reasoning (recommended)
"""

import argparse
import difflib
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Configure logging for this module
logger = logging.getLogger(__name__)

# Import from existing scripts
from match_persona import (  # noqa: E402
    PersonaProfile,
    calculate_persona_boost,
    calculate_sentiment,
    detect_slang_level_from_text,
    detect_tone_from_text,
)
from models import PatternProfile, ScoredCaption, SelectionPool  # noqa: E402
from volume_optimizer import MultiFactorVolumeOptimizer  # noqa: E402


def load_creator_content_notes(conn: sqlite3.Connection, creator_id: str) -> dict | None:
    """Load and parse content notes from creators.notes JSON field."""
    query = "SELECT notes FROM creators WHERE creator_id = ?"
    row = conn.execute(query, (creator_id,)).fetchone()

    if not row or not row["notes"]:
        return None

    try:
        return json.loads(row["notes"])
    except json.JSONDecodeError:
        # If notes is plain text (legacy), return as page_strategy
        return {"page_strategy": row["notes"]}


def format_notes_for_llm(notes: dict) -> str:
    """Format content notes as readable text for LLM context."""
    lines = []

    if notes.get("page_strategy"):
        lines.append(f"**Page Strategy**: {notes['page_strategy']}")
        lines.append("")

    if notes.get("content_restrictions"):
        lines.append("**Content Restrictions**:")
        for r in notes["content_restrictions"]:
            lines.append(f"- {r['content_type']}: {r['description']}")
        lines.append("")

    if notes.get("pricing_guidance"):
        lines.append("**Pricing Guidance**:")
        for p in notes["pricing_guidance"]:
            ct = p.get("content_type") or "all content"
            mod = p.get("price_modifier", 1.0)
            lines.append(f"- {ct}: {p['description']} (modifier: {mod}x)")
        lines.append("")

    if notes.get("caption_filters", {}).get("exclude_keywords"):
        lines.append(
            f"**Excluded Keywords**: {', '.join(notes['caption_filters']['exclude_keywords'])}"
        )

    return "\n".join(lines)


# Path resolution for database
SCRIPT_DIR = Path(__file__).parent

from database import DB_PATH, HOME_DIR  # noqa: E402


def get_all_creator_names(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Get all active creator page names and display names for fuzzy matching."""
    cursor = conn.execute(
        "SELECT page_name, display_name FROM creators WHERE is_active = 1 ORDER BY page_name"
    )
    return [(row["page_name"], row["display_name"] or row["page_name"]) for row in cursor]


def find_closest_creators(
    input_name: str, conn: sqlite3.Connection, threshold: float = 0.6
) -> list[tuple[str, str, float]]:
    """
    Find closest matching creator names using fuzzy matching.

    Returns list of (page_name, display_name, similarity_score) tuples,
    sorted by similarity descending.
    """
    all_creators = get_all_creator_names(conn)
    matches = []

    input_lower = input_name.lower().replace("_", "").replace("-", "").replace(" ", "")

    for page_name, display_name in all_creators:
        # Check against page_name
        page_lower = page_name.lower().replace("_", "").replace("-", "").replace(" ", "")
        page_similarity = difflib.SequenceMatcher(None, input_lower, page_lower).ratio()

        # Check against display_name
        display_lower = display_name.lower().replace("_", "").replace("-", "").replace(" ", "")
        display_similarity = difflib.SequenceMatcher(None, input_lower, display_lower).ratio()

        # Use the higher similarity
        best_similarity = max(page_similarity, display_similarity)

        if best_similarity >= threshold:
            matches.append((page_name, display_name, best_similarity))

    # Sort by similarity descending
    matches.sort(key=lambda x: x[2], reverse=True)
    return matches[:5]  # Return top 5 matches


# Default output directory for schedules/context
_env_schedules_path = os.environ.get("EROS_SCHEDULES_PATH", "")
DEFAULT_SCHEDULES_DIR = (
    Path(_env_schedules_path)
    if _env_schedules_path
    else HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "schedules"
)

# Old schedules directory (for migration notice)
OLD_SCHEDULES_DIR = HOME_DIR / ".eros" / "schedules"


def format_week_string(week_start: date) -> str:
    """Format date as ISO week string (YYYY-Www)."""
    iso_year, iso_week, _ = week_start.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


# Analysis thresholds
LOW_CONFIDENCE_THRESHOLD = 0.6
VERY_LOW_CONFIDENCE_THRESHOLD = 0.4
HIGH_VALUE_PERFORMANCE_THRESHOLD = 70
MAX_CAPTIONS_FOR_CONTEXT = 40
MAX_CAPTION_TEXT_LENGTH = 400


@dataclass(frozen=True, slots=True)
class SemanticBoostResult:
    """
    Result of Claude's semantic analysis for a single caption.

    This structure is filled in by Claude during semantic analysis and
    read by generate_schedule.py to apply enhanced persona boosts.

    Attributes:
        caption_id: Unique caption identifier.
        detected_tone: Claude's detected tone (e.g., "bratty", "playful").
        persona_boost: Final persona boost multiplier (1.0-1.4).
        quality_score: Content quality score (0.0-1.0).
        reasoning: Brief explanation of the analysis.
    """

    caption_id: int
    detected_tone: str
    persona_boost: float
    quality_score: float
    reasoning: str


@dataclass(frozen=True, slots=True)
class SemanticCaptionEntry:
    """
    A single caption entry in the semantic analysis template.

    Contains all data needed for Claude to perform semantic analysis
    on a caption and determine appropriate persona boosts.

    Attributes:
        caption_id: Unique caption identifier.
        caption_text: The actual caption text.
        content_type: Content type name (e.g., "sextape", "solo").
        performance_score: Historical performance score (0-100).
        freshness_score: Current freshness score (0-100).
        pattern_tone: Pattern-detected tone (may be inaccurate).
        pattern_boost: Pattern-calculated boost (preliminary).
        needs_analysis: Whether Claude should analyze this caption.
        analysis_reason: Why this caption needs analysis.
    """

    caption_id: int
    caption_text: str
    content_type: str | None
    performance_score: float
    freshness_score: float
    pattern_tone: str | None
    pattern_boost: float
    needs_analysis: bool
    analysis_reason: str


@dataclass(frozen=True, slots=True)
class CaptionContext:
    """Caption with full context for Claude's semantic analysis."""

    caption_id: int
    caption_text: str
    content_type: str | None
    performance_score: float
    freshness_score: float
    pattern_tone: str | None
    pattern_slang: str | None
    pattern_sentiment: float
    pattern_confidence: float
    pattern_boost: float
    needs_semantic_analysis: bool
    analysis_reason: str


@dataclass(frozen=True, slots=True)
class CreatorContext:
    """Full creator context for schedule generation."""

    creator_id: str
    page_name: str
    display_name: str
    page_type: str
    active_fans: int
    volume_level: str
    ppv_per_day: int
    primary_tone: str
    secondary_tone: str | None
    emoji_frequency: str
    slang_level: str
    avg_sentiment: float
    best_hours: tuple[int, ...]
    vault_types: tuple[str, ...]
    volume_fallback_used: bool = False  # True if multi-factor optimizer failed
    content_notes: dict | None = None


@dataclass(frozen=True, slots=True)
class ScheduleContext:
    """Complete context for Claude to generate an enhanced schedule."""

    creator: CreatorContext
    week_start: str
    week_end: str
    total_captions_available: int
    captions_for_analysis: tuple[CaptionContext, ...]
    performance_summary: dict[str, Any]
    mode: str  # 'quick' or 'full'


def parse_iso_week(week_str: str) -> tuple[date, date]:
    """Parse ISO week string to start and end dates."""
    year, week = week_str.split("-W")
    year = int(year)
    week = int(week)

    jan1 = date(year, 1, 1)
    jan1_weekday = jan1.weekday()

    if jan1_weekday <= 3:
        week1_monday = jan1 - timedelta(days=jan1_weekday)
    else:
        week1_monday = jan1 + timedelta(days=7 - jan1_weekday)

    monday = week1_monday + timedelta(weeks=week - 1)
    sunday = monday + timedelta(days=6)

    return monday, sunday


def get_volume_level(active_fans: int) -> tuple[str, int]:
    """
    Determine volume level and PPV count based on fan count.

    DEPRECATED: Use prepare_volume_context() for multi-factor optimization.

    Volume Tiers (from CLAUDE.md):
        - Low (<1,000 fans): 3 PPV/day = 21/week (target: 14-21)
        - Mid (1,000-5,000): 4 PPV/day = 28/week (target: 21-28)
        - High (5,000-15,000): 5 PPV/day = 35/week (target: 28-35)
        - Ultra (15,000+): 6 PPV/day = 42/week (target: 35-42)
    """
    # Legacy fallback for simple fan-count based volume
    if active_fans < 1000:
        return ("Low", 3)
    elif active_fans < 5000:
        return ("Mid", 4)
    elif active_fans < 15000:
        return ("High", 5)
    else:
        return ("Ultra", 6)


def prepare_volume_context(creator_id: str, conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Prepare volume context for LLM using multi-factor optimizer.

    This function uses the centralized MultiFactorVolumeOptimizer which
    considers multiple factors beyond just fan count:
    - Fan count brackets (base volume)
    - Performance tier (revenue contribution)
    - Conversion rate
    - Niche/persona type
    - Subscription price
    - Account age

    Args:
        creator_id: Creator UUID or page_name
        conn: Database connection

    Returns:
        Dictionary with volume strategy data for LLM context
    """
    optimizer = MultiFactorVolumeOptimizer(conn)
    strategy = optimizer.calculate_optimal_volume(creator_id)
    return strategy.to_dict()


def calculate_pattern_confidence(
    text: str, tone_scores: dict[str, int], detected_tone: str | None
) -> tuple[float, str]:
    """
    Calculate confidence level of pattern-based tone detection.

    Returns confidence score (0.0-1.0) and reason string.
    """
    if not text:
        return 0.0, "empty_text"

    if not tone_scores:
        return 0.3, "no_pattern_match"

    # Check for competing signals
    sorted_scores = sorted(tone_scores.values(), reverse=True)
    if len(sorted_scores) >= 2:
        top_score = sorted_scores[0]
        second_score = sorted_scores[1]

        if top_score > 0 and second_score / top_score > 0.6:
            return 0.35, "competing_signals"

    # Check signal strength
    if detected_tone and tone_scores.get(detected_tone, 0) >= 3:
        return 0.9, "strong_signal"
    elif detected_tone and tone_scores.get(detected_tone, 0) >= 2:
        return 0.75, "moderate_signal"
    elif detected_tone:
        return 0.55, "weak_signal"

    return 0.4, "ambiguous"


def load_creator_context(
    conn: sqlite3.Connection, creator_name: str | None = None, creator_id: str | None = None
) -> CreatorContext | None:
    """Load complete creator context."""
    if creator_name:
        query = """
            SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                   c.current_active_fans,
                   cp.primary_tone, cp.secondary_tone, cp.emoji_frequency,
                   cp.slang_level, cp.avg_sentiment
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.page_name = ? OR c.display_name = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_name, creator_name))
    else:
        query = """
            SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                   c.current_active_fans,
                   cp.primary_tone, cp.secondary_tone, cp.emoji_frequency,
                   cp.slang_level, cp.avg_sentiment
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.creator_id = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_id,))

    row = cursor.fetchone()
    if not row:
        return None

    active_fans = row["current_active_fans"] or 0

    # Get volume using multi-factor optimizer
    volume_fallback_used = False
    try:
        volume_context = prepare_volume_context(row["creator_id"], conn)
        volume_level = volume_context["volume_level"]
        ppv_per_day = volume_context["ppv_per_day"]
    except Exception as e:
        # Fallback to legacy simple volume calculation if optimizer fails
        volume_fallback_used = True
        logger.warning(
            "Volume optimization failed for creator '%s' (id=%s): %s. "
            "Using legacy fan-count based calculation.",
            row["page_name"],
            row["creator_id"],
            str(e),
        )
        volume_level, ppv_per_day = get_volume_level(active_fans)

    # Load best hours
    hours_query = """
        SELECT sending_hour, AVG(earnings) as avg_earnings
        FROM mass_messages
        WHERE creator_id = ? AND message_type = 'ppv' AND earnings IS NOT NULL
          AND sending_time >= datetime('now', '-90 days')
        GROUP BY sending_hour
        HAVING COUNT(*) >= 3
        ORDER BY avg_earnings DESC
        LIMIT 8
    """
    cursor = conn.execute(hours_query, (row["creator_id"],))
    best_hours = tuple(r["sending_hour"] for r in cursor.fetchall())
    if not best_hours:
        best_hours = (10, 14, 18, 20, 21)

    # Load vault types
    vault_query = """
        SELECT ct.type_name
        FROM vault_matrix vm
        JOIN content_types ct ON vm.content_type_id = ct.content_type_id
        WHERE vm.creator_id = ? AND vm.has_content = 1
    """
    cursor = conn.execute(vault_query, (row["creator_id"],))
    vault_types = tuple(r["type_name"] for r in cursor.fetchall())

    # Load content notes
    content_notes = load_creator_content_notes(conn, row["creator_id"])

    return CreatorContext(
        creator_id=row["creator_id"],
        page_name=row["page_name"],
        display_name=row["display_name"] or row["page_name"],
        page_type=row["page_type"] or "paid",
        active_fans=active_fans,
        volume_level=volume_level,
        ppv_per_day=ppv_per_day,
        primary_tone=row["primary_tone"] or "playful",
        secondary_tone=row["secondary_tone"],  # Query from database
        emoji_frequency=row["emoji_frequency"] or "moderate",
        slang_level=row["slang_level"] or "light",
        avg_sentiment=row["avg_sentiment"] or 0.5,
        best_hours=best_hours,
        vault_types=vault_types,
        volume_fallback_used=volume_fallback_used,
        content_notes=content_notes,
    )


def load_other_creator_names(conn: sqlite3.Connection, exclude_page_name: str) -> set[str]:
    """
    Load all creator names except the target creator to detect cross-contamination.

    Returns a set of lowercase names that should NOT appear in captions
    for the target creator (unless it's their own name).
    """
    cursor = conn.execute(
        "SELECT page_name, display_name FROM creators WHERE is_active = 1"
    )
    names = set()
    target_lower = exclude_page_name.lower().replace("_", " ")

    for row in cursor:
        page_name = (row["page_name"] or "").lower().replace("_", " ")
        display_name = (row["display_name"] or "").lower()

        # Skip short names (< 4 chars) to avoid false positives
        if len(page_name) >= 4 and page_name != target_lower:
            names.add(page_name)
        if len(display_name) >= 4 and display_name.lower() != target_lower:
            names.add(display_name)

    # Also remove any name that's part of the target name
    target_parts = set(target_lower.split())
    names = {n for n in names if n not in target_parts}

    return names


def validate_caption_ownership(
    caption_text: str, other_creator_names: set[str]
) -> tuple[bool, str | None]:
    """
    Check if a caption references other creators (data quality issue).

    Args:
        caption_text: The caption text to validate
        other_creator_names: Set of other creator names to check against

    Returns:
        Tuple of (is_valid, detected_name_if_invalid)
    """
    text_lower = caption_text.lower()

    for name in other_creator_names:
        if name in text_lower:
            return False, name

    return True, None


def load_captions_for_context(
    conn: sqlite3.Connection, creator: CreatorContext, limit: int = 100
) -> tuple[list[CaptionContext], dict[str, Any]]:
    """
    Load captions and prepare them for Claude's analysis.

    Returns captions prioritized by:
    1. Those needing semantic analysis (low confidence)
    2. High-value captions (performance >= 70)
    3. Fresh captions (freshness >= 30)
    """
    query = """
        SELECT
            cb.caption_id,
            cb.caption_text,
            cb.caption_type,
            ct.type_name as content_type,
            cb.performance_score,
            cb.freshness_score,
            cb.tone,
            cb.slang_level
        FROM caption_bank cb
        LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
        WHERE cb.is_active = 1
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= 30
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT ?
    """

    cursor = conn.execute(query, (creator.creator_id, limit))
    rows = cursor.fetchall()

    # Load other creator names for cross-contamination detection
    other_creator_names = load_other_creator_names(conn, creator.page_name)
    filtered_count = 0

    # Build persona for boost calculation
    persona = PersonaProfile(
        creator_id=creator.creator_id,
        page_name=creator.page_name,
        primary_tone=creator.primary_tone,
        secondary_tone=creator.secondary_tone,
        emoji_frequency=creator.emoji_frequency,
        slang_level=creator.slang_level,
        avg_sentiment=creator.avg_sentiment,
    )

    captions = []
    stats = {
        "total_evaluated": 0,
        "needs_analysis": 0,
        "high_confidence": 0,
        "low_confidence": 0,
        "high_value": 0,
        "avg_performance": 0.0,
        "avg_freshness": 0.0,
    }

    total_perf = 0.0
    total_fresh = 0.0

    for row in rows:
        text = row["caption_text"] or ""

        # Validate caption doesn't reference other creators
        is_valid, detected_name = validate_caption_ownership(text, other_creator_names)
        if not is_valid:
            filtered_count += 1
            logger.warning(
                f"Filtered caption {row['caption_id']}: references other creator '{detected_name}'"
            )
            continue  # Skip this caption

        stats["total_evaluated"] += 1

        perf = row["performance_score"] or 50.0
        fresh = row["freshness_score"] or 100.0

        total_perf += perf
        total_fresh += fresh

        if perf >= HIGH_VALUE_PERFORMANCE_THRESHOLD:
            stats["high_value"] += 1

        # Run pattern detection
        detected_tone, tone_scores = detect_tone_from_text(text)
        detected_slang = detect_slang_level_from_text(text)
        sentiment = calculate_sentiment(text)

        # Calculate confidence
        confidence, conf_reason = calculate_pattern_confidence(text, tone_scores, detected_tone)

        if confidence >= 0.7:
            stats["high_confidence"] += 1
        else:
            stats["low_confidence"] += 1

        # Calculate pattern boost using full persona matching
        match_result = calculate_persona_boost(
            caption_tone=row["tone"] or detected_tone,
            caption_emoji_style=None,
            caption_slang_level=row["slang_level"] or detected_slang,
            persona=persona,
            caption_text=text,
            use_text_detection=True,
        )

        # Determine if semantic analysis needed
        needs_analysis = False
        analysis_reason = ""

        if not row["tone"] and confidence < LOW_CONFIDENCE_THRESHOLD:
            needs_analysis = True
            analysis_reason = f"No stored tone, pattern confidence {confidence:.0%}"
        elif confidence < VERY_LOW_CONFIDENCE_THRESHOLD:
            needs_analysis = True
            analysis_reason = f"Very low confidence ({confidence:.0%})"
        elif conf_reason == "competing_signals":
            needs_analysis = True
            analysis_reason = "Multiple competing tone signals"
        elif perf >= HIGH_VALUE_PERFORMANCE_THRESHOLD and match_result.total_boost < 1.10:
            needs_analysis = True
            analysis_reason = "High performer with low persona match"

        if needs_analysis:
            stats["needs_analysis"] += 1

        # Truncate text for context efficiency
        display_text = text[:MAX_CAPTION_TEXT_LENGTH]
        if len(text) > MAX_CAPTION_TEXT_LENGTH:
            display_text += "..."

        captions.append(
            CaptionContext(
                caption_id=row["caption_id"],
                caption_text=display_text,
                content_type=row["content_type"],
                performance_score=round(perf, 1),
                freshness_score=round(fresh, 1),
                pattern_tone=detected_tone,
                pattern_slang=detected_slang,
                pattern_sentiment=round(sentiment, 2),
                pattern_confidence=round(confidence, 2),
                pattern_boost=round(match_result.total_boost, 2),
                needs_semantic_analysis=needs_analysis,
                analysis_reason=analysis_reason,
            )
        )

    if stats["total_evaluated"] > 0:
        stats["avg_performance"] = round(total_perf / stats["total_evaluated"], 1)
        stats["avg_freshness"] = round(total_fresh / stats["total_evaluated"], 1)

    # Track filtered captions (cross-creator contamination)
    stats["filtered_cross_creator"] = filtered_count
    if filtered_count > 0:
        logger.info(
            f"Filtered {filtered_count} captions referencing other creators"
        )

    # Sort: needs_analysis first, then by performance
    captions.sort(key=lambda c: (not c.needs_semantic_analysis, -c.performance_score))

    return captions, stats


# =============================================================================
# NEW PATTERN-BASED SELECTION CONTEXT FORMATTERS
# =============================================================================


def format_pattern_profile_section(profile: PatternProfile | None) -> str:
    """
    Format pattern profile for LLM context.

    Returns markdown section showing:
    - Sample count and confidence level
    - Top performing content types (by avg earnings)
    - Top performing tones
    - Whether using global fallback

    Args:
        profile: PatternProfile from select_captions module, or None.

    Returns:
        Formatted markdown string for LLM context.
    """
    if profile is None:
        return """
## Pattern Profile
*No pattern profile available. Using discovery-only selection.*
"""

    section = f"""
## Pattern Profile

**Data Confidence:** {profile.confidence:.0%} ({profile.sample_count} samples analyzed)
{"[!] Using global portfolio patterns (new/sparse creator)" if profile.is_global_fallback else "[OK] Using creator-specific patterns"}

### Top Performing Content Types
| Content Type | Avg Earnings | Sample Count | Score |
|--------------|-------------|--------------|-------|
"""

    # Sort by normalized_score
    top_content = sorted(
        profile.content_type_patterns.items(),
        key=lambda x: x[1].normalized_score,
        reverse=True,
    )[:5]

    for ct_name, stats in top_content:
        section += (
            f"| {ct_name} | ${stats.avg_earnings:.2f} | "
            f"{stats.sample_count} | {stats.normalized_score:.0f} |\n"
        )

    section += """
### Top Performing Tones
| Tone | Avg Earnings | Sample Count | Score |
|------|-------------|--------------|-------|
"""

    top_tones = sorted(
        profile.tone_patterns.items(),
        key=lambda x: x[1].normalized_score,
        reverse=True,
    )[:5]

    for tone, stats in top_tones:
        section += (
            f"| {tone} | ${stats.avg_earnings:.2f} | "
            f"{stats.sample_count} | {stats.normalized_score:.0f} |\n"
        )

    return section


def format_pool_analysis_section(pool: SelectionPool | None) -> str:
    """
    Format caption pool analysis for LLM context.

    Shows:
    - Total captions available
    - Freshness tier distribution
    - Content type distribution
    - Exploration candidates count

    Args:
        pool: SelectionPool containing scored captions.

    Returns:
        Formatted markdown string for LLM context.
    """
    if pool is None or not pool.captions:
        return """
## Caption Pool Analysis
*No selection pool available.*
"""

    section = f"""
## Caption Pool Analysis

**Pool Size:** {len(pool.captions)} fresh captions available

### Freshness Distribution
| Tier | Count | Description |
|------|-------|-------------|
| Never Used | {pool.never_used_count} | First time for this creator |
| Fresh | {pool.fresh_count} | Not used in 60+ days |

**Reuse Rate:** {(pool.fresh_count / len(pool.captions) * 100) if pool.captions else 0:.1f}% are reusable captions

### Content Type Distribution
| Content Type | Count |
|--------------|-------|
"""

    # Count by content type
    ct_counts: dict[str, int] = {}
    for caption in pool.captions:
        ct = caption.content_type_name or "Unknown"
        ct_counts[ct] = ct_counts.get(ct, 0) + 1

    for ct, count in sorted(ct_counts.items(), key=lambda x: x[1], reverse=True):
        section += f"| {ct} | {count} |\n"

    # Count exploration candidates (never_used + low pattern score)
    exploration_candidates = sum(
        1 for c in pool.captions if c.never_used_on_page or c.pattern_score < 30
    )

    section += f"""
### Exploration Potential
**{exploration_candidates}** captions identified as exploration candidates (testing new patterns)
"""

    return section


def get_selection_instructions() -> str:
    """
    Return instructions explaining the fresh-focused selection system.

    These instructions help Claude understand the new selection logic
    when reviewing or adjusting schedules.

    Returns:
        Formatted markdown string with selection logic explanation.
    """
    return """
## Selection Logic (Fresh-Focused v2.0)

The caption selection uses a **fresh-first approach** optimized for novelty:

### Weight Formula
```
PatternMatch (40%) + NeverUsedBonus (25%) + Persona (15%) + FreshnessBonus (10%) + Exploration (10%)
```

### Key Behaviors:
1. **Hard 60-Day Exclusion**: Captions used in the last 60 days are NEVER selected
2. **Never-Used Priority**: First-time captions get 1.5x weight multiplier
3. **Pattern Matching**: Historical success patterns guide selection (not reuse proven winners)
4. **Exploration Slots**: 10-15% of slots test low-pattern-score captions for discovery

### Freshness Tiers:
- **Never Used** (1.5x): Caption has never been sent to this creator's fans
- **Fresh** (1.0x): Last sent 60+ days ago, safe to reuse
- **Excluded** (filtered): Used recently, completely blocked

### When reviewing captions:
- Prioritize **never_used** tier for maximum novelty
- Consider **pattern_score** as guidance, not guarantee
- Exploration slots intentionally break patterns to discover new winners
"""


def format_selection_summary(
    slots: list[Any],
    pool: SelectionPool | None,
) -> str:
    """
    Format summary of selection results.

    Provides a quick overview of selection outcomes including
    exploration slot ratio and pool utilization.

    Args:
        slots: List of scheduled slots with caption assignments.
        pool: SelectionPool used for selection.

    Returns:
        Formatted markdown summary table.
    """
    if not slots or pool is None or not pool.captions:
        return """
## Selection Summary
*No selection data available.*
"""

    exploration_count = sum(1 for s in slots if getattr(s, "is_exploration", False))
    never_used_count = sum(
        1
        for s in slots
        if hasattr(s, "caption")
        and s.caption
        and getattr(s.caption, "freshness_tier", None) == "never_used"
    )

    return f"""
## Selection Summary

| Metric | Value |
|--------|-------|
| Total Slots | {len(slots)} |
| Exploration Slots | {exploration_count} ({exploration_count / len(slots) * 100:.0f}%) |
| Never-Used Captions | {never_used_count} ({never_used_count / len(slots) * 100:.0f}%) |
| Pool Utilization | {len(slots) / len(pool.captions) * 100:.1f}% of available pool |
"""


def prepare_full_context(
    conn: sqlite3.Connection,
    creator_id: str,
    week: str,
    pattern_profile: PatternProfile | None = None,
    pool: SelectionPool | None = None,
    include_selection_guide: bool = True,
) -> str:
    """
    Prepare comprehensive LLM context for schedule generation.

    This function assembles all context sections needed for Claude to
    understand and reason about the caption selection. It integrates
    the new pattern-based selection system with existing creator context.

    Sections:
    1. Creator Profile (existing)
    2. Pattern Profile (NEW)
    3. Caption Pool Analysis (UPDATED)
    4. Selection Instructions (NEW)
    5. Schedule Structure (existing)
    6. Business Rules (existing)

    Args:
        conn: Database connection.
        creator_id: Creator UUID or page_name.
        week: Week string in ISO format (YYYY-Www).
        pattern_profile: PatternProfile from select_captions module.
        pool: SelectionPool containing scored captions.
        include_selection_guide: Whether to include selection instructions.

    Returns:
        Complete markdown context string for LLM processing.
    """
    from datetime import date

    context_parts = []

    # Header
    context_parts.append("# EROS Schedule Generation Context (v2.0)\n")
    context_parts.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    context_parts.append(f"**Week**: {week}")
    context_parts.append(f"**Selection System**: Fresh-Focused Pattern Matching\n")
    context_parts.append("---\n")

    # 1. Creator Profile (using existing function)
    creator = load_creator_context(conn, creator_id=creator_id)
    if creator:
        context_parts.append("## Creator Profile\n")
        context_parts.append(f"**{creator.display_name}** (@{creator.page_name})")
        context_parts.append(f"- Page Type: {creator.page_type}")
        context_parts.append(f"- Active Fans: {creator.active_fans:,}")
        context_parts.append(f"- Volume: {creator.volume_level} ({creator.ppv_per_day} PPV/day)")
        context_parts.append(f"- Primary Tone: {creator.primary_tone}")
        context_parts.append(f"- Slang Level: {creator.slang_level}")
        context_parts.append(f"- Best Hours: {', '.join(f'{h:02d}:00' for h in creator.best_hours[:6])}\n")

    # 2. Pattern Profile (NEW)
    if pattern_profile:
        context_parts.append(format_pattern_profile_section(pattern_profile))

    # 3. Pool Analysis (UPDATED with freshness tiers)
    if pool:
        context_parts.append(format_pool_analysis_section(pool))

    # 4. Selection Instructions (NEW)
    if include_selection_guide:
        context_parts.append(get_selection_instructions())

    # 5. Business Rules Summary
    context_parts.append("""
## Business Rules

| Rule | Requirement |
|------|-------------|
| PPV Spacing | Minimum 3 hours between PPVs |
| Content Rotation | No same content type 3x consecutive |
| Freshness Threshold | All captions must score >= 30 |
| Daily Volume | Follow volume level guidelines |
| Persona Match | Prioritize tone-matched captions |
""")

    return "\n".join(context_parts)


def format_context_for_claude(context: ScheduleContext, week_arg: str | None = None) -> str:
    """
    Format the complete context as markdown for Claude to process.

    This is the KEY integration point - the output becomes part of Claude's
    conversation context, and Claude applies its semantic reasoning directly.

    Args:
        context: The ScheduleContext containing creator and caption data
        week_arg: The original week argument (e.g., '2025-W50') for the footer command
    """
    c = context.creator

    lines = [
        "# EROS Schedule Generation Context",
        "",
        f"**Mode**: {context.mode.upper()}",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## Creator Profile",
        "",
        "| Attribute | Value |",
        "|-----------|-------|",
        f"| Creator | **{c.display_name}** (@{c.page_name}) |",
        f"| Page Type | {c.page_type} |",
        f"| Active Fans | {c.active_fans:,} |",
        f"| Volume Level | {c.volume_level} ({c.ppv_per_day} PPV/day){' [LEGACY FALLBACK]' if c.volume_fallback_used else ''} |",
        "",
        "### Persona Profile",
        "",
        "| Attribute | Value |",
        "|-----------|-------|",
        f"| Primary Tone | **{c.primary_tone}** |",
        f"| Secondary Tone | {c.secondary_tone or 'N/A'} |",
        f"| Emoji Usage | {c.emoji_frequency} |",
        f"| Slang Level | {c.slang_level} |",
        f"| Avg Sentiment | {c.avg_sentiment:.2f} |",
        "",
        f"**Best Hours**: {', '.join(f'{h:02d}:00' for h in c.best_hours[:6])}",
        f"**Vault Content**: {', '.join(c.vault_types[:8]) if c.vault_types else 'N/A'}",
        "",
    ]

    # Add content notes section if available
    if c.content_notes:
        lines.extend(
            [
                "### Creator Content Notes",
                "",
                format_notes_for_llm(c.content_notes),
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "## Schedule Period",
            "",
            f"- **Start**: {context.week_start}",
            f"- **End**: {context.week_end}",
            f"- **Total PPVs to Schedule**: {c.ppv_per_day * 7}",
            "",
            "---",
            "",
            "## Caption Pool Analysis",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Available | {context.total_captions_available} |",
            f"| Needs Semantic Analysis | {context.performance_summary['needs_analysis']} |",
            f"| High Confidence | {context.performance_summary['high_confidence']} |",
            f"| High Value (perf >= 70) | {context.performance_summary['high_value']} |",
            f"| Avg Performance | {context.performance_summary['avg_performance']} |",
            f"| Avg Freshness | {context.performance_summary['avg_freshness']} |",
            "",
        ]
    )

    if context.mode == "full":
        # Include captions for semantic analysis
        needs_analysis = [
            cap for cap in context.captions_for_analysis if cap.needs_semantic_analysis
        ]
        high_confidence = [
            cap for cap in context.captions_for_analysis if not cap.needs_semantic_analysis
        ]

        lines.extend(
            [
                "---",
                "",
                "## Captions Requiring Semantic Analysis",
                "",
                "These captions have low pattern-matching confidence and need your semantic reasoning.",
                "",
            ]
        )

        for i, cap in enumerate(needs_analysis[:MAX_CAPTIONS_FOR_CONTEXT], 1):
            lines.extend(
                [
                    f"### Caption #{i} (ID: {cap.caption_id})",
                    "",
                    f'**Text**: "{cap.caption_text}"',
                    "",
                    f"- Content Type: {cap.content_type or 'N/A'}",
                    f"- Performance: {cap.performance_score} | Freshness: {cap.freshness_score}",
                    f"- Pattern Detection: tone=`{cap.pattern_tone}`, slang=`{cap.pattern_slang}`, confidence={cap.pattern_confidence:.0%}",
                    f"- Current Boost: {cap.pattern_boost}x",
                    f"- **Analysis Reason**: {cap.analysis_reason}",
                    "",
                ]
            )

        if len(needs_analysis) > MAX_CAPTIONS_FOR_CONTEXT:
            lines.append(
                f"*({len(needs_analysis) - MAX_CAPTIONS_FOR_CONTEXT} more captions need analysis)*"
            )
            lines.append("")

        lines.extend(
            [
                "---",
                "",
                "## High-Confidence Captions (Pre-Scored)",
                "",
                "These captions have high pattern-matching confidence. Review briefly for accuracy.",
                "",
                "| ID | Type | Perf | Fresh | Tone | Boost |",
                "|----|------|------|-------|------|-------|",
            ]
        )

        for cap in high_confidence[:20]:
            lines.append(
                f"| {cap.caption_id} | {cap.content_type or 'N/A'} | {cap.performance_score} | "
                f"{cap.freshness_score} | {cap.pattern_tone or '-'} | {cap.pattern_boost}x |"
            )

        if len(high_confidence) > 20:
            lines.append(f"| ... | ... | ... | ... | ... | ({len(high_confidence) - 20} more) |")

        lines.extend(
            [
                "",
                "---",
                "",
                "## Claude Analysis Instructions",
                "",
                "For each caption in the 'Requiring Semantic Analysis' section, evaluate and score:",
                "",
                "### 1. Persona Match Score (0.0 - 1.0)",
                "",
                "Calculate persona match by checking these factors:",
                "",
                "| Factor | Match Condition | Boost |",
                "|--------|----------------|-------|",
                f"| Primary Tone | Matches **{c.primary_tone}** | +0.20 |",
                f"| Secondary Tone | Matches **{c.secondary_tone or 'N/A'}** | +0.10 |",
                f"| Emoji Usage | Matches **{c.emoji_frequency}** frequency | +0.05 |",
                f"| Slang Level | Matches **{c.slang_level}** level | +0.05 |",
                "",
                "Base score is 1.0. Add matching boosts (max combined: 1.40x).",
                "",
                "### 2. Content Quality Score (0.0 - 1.0)",
                "",
                "Evaluate these elements:",
                "",
                "| Element | What to Look For | Weight |",
                "|---------|-----------------|--------|",
                "| Hook Strength | First line engagement, attention-grabbing | 0.30 |",
                "| Urgency/Scarcity | Time-limited offers, exclusive language | 0.20 |",
                "| Call-to-Action | Clear next step, compelling reason to act | 0.30 |",
                "| Emotional Resonance | Connects with audience, authentic voice | 0.20 |",
                "",
                "### 3. Freshness Score",
                "",
                "Already provided in caption data. Use as-is.",
                "",
                "### Output Format for Each Caption",
                "",
                "Return analysis as JSON for each caption requiring semantic analysis:",
                "",
                "```json",
                "{",
                '  "caption_id": "12345",',
                '  "persona_match": 0.85,',
                '  "quality_score": 0.75,',
                '  "recommended_boost": 1.15,',
                '  "detected_tone": "bratty",',
                '  "reasoning": "Strong primary tone match with bratty undertones, good CTA"',
                "}",
                "```",
                "",
                "---",
                "",
                "## Tone Detection Tips",
                "",
                "| Indicator | What It Really Means |",
                "|-----------|---------------------|",
                "| eye-roll + positive words | Bratty/playful, NOT sincere |",
                '| "I guess" + generous offer | Bratty teasing |',
                '| "Fine..." + gift | Playfully reluctant |',
                "| Exaggerated compliance | Bratty |",
                '| "Right now" | Could be aggressive OR playfully demanding |',
                "| Direct pricing language | Direct tone (even if dressed up) |",
                '| "babe/baby" + offer | Sweet/seductive, relationship-building |',
                "| Commands without softeners | Dominant or aggressive |",
                "| Questions + teasing | Playful engagement |",
                "",
                "---",
                "",
                "## Your Analysis Task",
                "",
                "1. **Analyze Each Low-Confidence Caption**:",
                "   - Determine true tone beyond keyword matching",
                "   - Score persona match using the factors above",
                "   - Score content quality",
                "   - Provide JSON output for each",
                "",
                "2. **Generate Enhanced Weekly Schedule**:",
                f"   - Create a complete {c.ppv_per_day * 7}-PPV weekly schedule",
                "   - Select best-matching captions for each time slot",
                "   - Maintain 4+ hour spacing between PPVs",
                "   - Ensure content type rotation (no consecutive same type)",
                "   - Prioritize high-performance + high-boost captions",
                "",
                "## Schedule Output Format",
                "",
                "```markdown",
                f"# Enhanced Schedule: {c.display_name}",
                f"## Week: {context.week_start} - {context.week_end}",
                "",
                "### Caption Analysis Results",
                "",
                "| ID | Detected Tone | Persona Match | Quality | Final Boost | Reasoning |",
                "|----|--------------|---------------|---------|-------------|-----------|",
                "| 12345 | bratty | 0.85 | 0.80 | 1.25x | Strong tone match, good hook |",
                "",
                "### Monday [Date]",
                "| Time | Type | Caption ID | Content | Price | Boost | Notes |",
                "|------|------|------------|---------|-------|-------|-------|",
                "| 10:00 | PPV | 12345 | solo | $14.99 | 1.35x | Perfect bratty tone |",
                "| 14:00 | PPV | 23456 | bundle | $19.99 | 1.25x | Good match |",
                "...",
                "",
                "### Weekly Summary",
                f"- Total PPVs: {c.ppv_per_day * 7}",
                "- Avg Boost: X.XX",
                "- Captions Enhanced: X of Y",
                "- Primary Tone Matches: X",
                "- Secondary Tone Matches: X",
                "```",
                "",
                "---",
                "",
                "## SAVE YOUR SEMANTIC ANALYSIS (CRITICAL)",
                "",
                "After analyzing the captions above, **you MUST save your semantic analysis**.",
                "Without saving, your analysis will be lost and persona boost coverage will be 0%.",
                "",
                f"**Save to**: `~/.eros/schedules/semantic/{c.page_name}/{week_arg or context.week_start}_semantic.json`",
                "",
                "**Option 1: Use the Write tool to create the JSON file directly:**",
                "",
                "```json",
                "{",
                f'  "creator_name": "{c.page_name}",',
                f'  "week": "{week_arg or context.week_start}",',
                '  "generated_at": "' + datetime.now().isoformat() + '",',
                '  "semantic_results": [',
                '    {',
                '      "caption_id": 12345,',
                '      "detected_tone": "bratty",',
                '      "persona_boost": 1.25,',
                '      "quality_score": 0.80,',
                '      "reasoning": "Strong bratty undertones with playful hook"',
                '    }',
                '  ]',
                "}",
                "```",
                "",
                "**Option 2: Use Python to save via SemanticBoostCache:**",
                "",
                "```python",
                "from semantic_boost_cache import SemanticBoostCache",
                "",
                "cache = SemanticBoostCache()",
                "results = [",
                '    {"caption_id": 12345, "detected_tone": "bratty", "persona_boost": 1.25, "quality_score": 0.80, "reasoning": "..."},',
                "    # ... more results",
                "]",
                f'cache.save("{c.page_name}", "{week_arg or context.week_start}", results)',
                "```",
                "",
                "**After saving, the pipeline will auto-load your analysis when you run:**",
                f"```bash",
                f"python3 scripts/generate_schedule.py --creator {c.page_name} --week {week_arg or context.week_start}",
                "```",
                "",
                "Your persona boost scores will be applied automatically in Step 3 (MATCH PERSONA).",
                "",
            ]
        )

    else:  # quick mode
        lines.extend(
            [
                "---",
                "",
                "## Quick Mode - Pattern-Based Schedule",
                "",
                "Using pattern matching only (no semantic analysis).",
                "Run with `--mode full` for enhanced quality.",
                "",
                "### Available Captions by Boost",
                "",
                "| ID | Type | Perf | Fresh | Tone | Boost |",
                "|----|------|------|-------|------|-------|",
            ]
        )

        for cap in context.captions_for_analysis[:30]:
            lines.append(
                f"| {cap.caption_id} | {cap.content_type or 'N/A'} | {cap.performance_score} | "
                f"{cap.freshness_score} | {cap.pattern_tone or '-'} | {cap.pattern_boost}x |"
            )

        lines.extend(
            [
                "",
                f"Generate a {c.ppv_per_day * 7}-PPV schedule using these pre-scored captions.",
                "",
            ]
        )

    # Add workflow footer with required next step
    # Use week_arg if provided, otherwise construct from week_start date
    if week_arg:
        week_for_command = week_arg
    else:
        # Construct week string from context.week_start (ISO date format: YYYY-MM-DD)
        week_date = date.fromisoformat(context.week_start)
        iso_year, iso_week, _ = week_date.isocalendar()
        week_for_command = f"{iso_year}-W{iso_week:02d}"

    lines.extend(
        [
            "---",
            "",
            "═══════════════════════════════════════════════════════════════════",
            "REQUIRED NEXT STEP - DO NOT SKIP",
            "",
            f"Run: python3 scripts/generate_schedule.py --creator {c.page_name} --week {week_for_command}",
            "",
            "This runs the full 9-step pipeline with:",
            "- Pool-based caption selection (PROVEN/GLOBAL_EARNER/DISCOVERY)",
            "- Vault matrix content filtering",
            "- Content restriction enforcement",
            "- Real validation (not manual claims)",
            "- Output saved to schedules directory",
            "═══════════════════════════════════════════════════════════════════",
            "",
        ]
    )

    return "\n".join(lines)


def save_semantic_template(
    context: ScheduleContext,
    output_path: Path,
    week: str,
) -> dict[str, Any]:
    """
    Save a semantic analysis template as JSON for Claude to fill in.

    This function generates a structured JSON template containing captions
    that need semantic analysis. Claude reads this template, performs
    semantic analysis on each caption, and saves the results to the
    specified output path.

    The template includes:
    - Creator persona context for tone matching
    - Captions with pattern-based preliminary scores
    - Clear instructions for the expected output format
    - Path where Claude should save the completed analysis

    Args:
        context: The ScheduleContext containing creator and caption data.
        output_path: Path where the template should be saved.
        week: Week string in ISO format (YYYY-Www).

    Returns:
        Dictionary representation of the saved template.

    Example:
        >>> template = save_semantic_template(context, Path("template.json"), "2025-W50")
        >>> print(template["output_path"])
        ~/.eros/schedules/semantic/grace_bennett/2025-W50_semantic.json
    """
    c = context.creator

    # Build caption entries for template
    captions_for_template = []
    for cap in context.captions_for_analysis:
        captions_for_template.append({
            "caption_id": cap.caption_id,
            "caption_text": cap.caption_text,
            "content_type": cap.content_type,
            "performance_score": cap.performance_score,
            "freshness_score": cap.freshness_score,
            "pattern_tone": cap.pattern_tone,
            "pattern_boost": cap.pattern_boost,
            "needs_analysis": cap.needs_semantic_analysis,
            "analysis_reason": cap.analysis_reason,
        })

    # Build expected output path for semantic results
    results_dir = HOME_DIR / ".eros" / "schedules" / "semantic" / c.page_name
    results_path = results_dir / f"{week}_semantic.json"

    template: dict[str, Any] = {
        "creator_id": c.creator_id,
        "creator_name": c.page_name,
        "display_name": c.display_name,
        "week": week,
        "week_start": context.week_start,
        "week_end": context.week_end,
        "semantic_template": captions_for_template,
        "output_path": str(results_path),
        "persona_context": {
            "primary_tone": c.primary_tone,
            "secondary_tone": c.secondary_tone,
            "emoji_frequency": c.emoji_frequency,
            "slang_level": c.slang_level,
            "avg_sentiment": c.avg_sentiment,
        },
        "instructions": {
            "task": "Analyze captions where needs_analysis=true and fill in semantic_results array",
            "output_format": {
                "caption_id": "int - must match source caption_id",
                "detected_tone": "str - your detected tone (e.g., bratty, playful, seductive, direct)",
                "persona_boost": "float - 1.0 to 1.4 based on persona match",
                "quality_score": "float - 0.0 to 1.0 based on hook strength, CTA, urgency",
                "reasoning": "str - brief explanation of your analysis",
            },
            "persona_matching_guide": {
                "primary_tone_match": "+0.20 boost if caption matches primary_tone",
                "secondary_tone_match": "+0.10 boost if caption matches secondary_tone",
                "emoji_match": "+0.05 boost if emoji usage matches emoji_frequency",
                "slang_match": "+0.05 boost if slang level matches slang_level",
                "base_boost": "1.0 (no penalties, only additions up to 1.4 max)",
            },
            "save_to": str(results_path),
            "expected_output_structure": {
                "creator_name": c.page_name,
                "week": week,
                "analyzed_at": "ISO timestamp",
                "semantic_results": [
                    {
                        "caption_id": "int",
                        "detected_tone": "str",
                        "persona_boost": "float",
                        "quality_score": "float",
                        "reasoning": "str",
                    }
                ],
            },
        },
        "statistics": {
            "total_captions": len(captions_for_template),
            "needs_analysis_count": sum(1 for c in captions_for_template if c["needs_analysis"]),
            "high_confidence_count": sum(1 for c in captions_for_template if not c["needs_analysis"]),
        },
        "generated_at": datetime.now().isoformat(),
    }

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(template, indent=2))

    return template


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Prepare context for native Claude LLM schedule generation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script outputs structured context that Claude processes natively.
Unlike API-based approaches, this leverages Claude Code's built-in intelligence.

Modes:
    quick - Pattern matching only, fast generation
    full  - Full semantic analysis with Claude reasoning (recommended)

Examples:
    python prepare_llm_context.py --creator missalexa --week 2025-W01
    python prepare_llm_context.py --creator missalexa --week 2025-W01 --mode full
    python prepare_llm_context.py --creator missalexa --week 2025-W01 --mode quick
        """,
    )

    parser.add_argument("--creator", "-c", help="Creator page name (e.g., missalexa)")
    parser.add_argument("--creator-id", help="Creator UUID")
    parser.add_argument(
        "--week", "-w", required=True, help="Week in ISO format (YYYY-Www, e.g., 2025-W01)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use quick mode (minimal context). Default is full mode.",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["quick", "full"],
        default="full",
        help="Context preparation mode: quick (minimal) or full (semantic analysis). Default: full",
    )
    parser.add_argument("--output", "-o", help="Output file path (overrides auto-save location)")
    parser.add_argument(
        "--stdout",
        "--print",
        action="store_true",
        dest="stdout",
        help="Print to console instead of auto-saving to file",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--db", default=str(DB_PATH), help=f"Database path (default: {DB_PATH})")
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Auto-select closest matching creator if similarity > 80%%",
    )
    parser.add_argument(
        "--chain",
        action="store_true",
        help="After outputting context, automatically run generate_schedule.py with same args",
    )
    parser.add_argument(
        "--output-semantic-template",
        action="store_true",
        help="Output a JSON template for semantic analysis that Claude can fill in",
    )
    parser.add_argument(
        "--semantic-output-dir",
        type=str,
        default=None,
        help="Directory for semantic analysis output (default: ~/.eros/schedules/semantic/{creator})",
    )

    args = parser.parse_args()

    # Handle --quick flag override
    if args.quick:
        args.mode = "quick"

    if not args.creator and not args.creator_id:
        parser.error("Must specify --creator or --creator-id")

    # Parse week
    try:
        week_start, week_end = parse_iso_week(args.week)
    except Exception as e:
        parser.error(f"Invalid week format: {e}")

    # Check for old schedules directory and show migration notice
    if OLD_SCHEDULES_DIR.exists():
        logger.info(
            f"Note: Old schedules directory found at {OLD_SCHEDULES_DIR}. "
            f"New schedules will be saved to {DEFAULT_SCHEDULES_DIR}. "
            f"Set EROS_SCHEDULES_PATH to customize."
        )

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Load creator context
        creator = load_creator_context(conn, creator_name=args.creator, creator_id=args.creator_id)

        if not creator:
            # Creator not found - try fuzzy matching
            if args.creator:
                matches = find_closest_creators(args.creator, conn, threshold=0.5)

                if matches:
                    top_match = matches[0]
                    page_name, display_name, similarity = top_match

                    if args.fuzzy and similarity > 0.8:
                        # Auto-select with fuzzy flag and high similarity
                        print(
                            f"Fuzzy match: '{args.creator}' -> '{page_name}' "
                            f"({similarity:.0%} similarity)",
                            file=sys.stderr,
                        )
                        creator = load_creator_context(conn, creator_name=page_name)
                    else:
                        # Show suggestions and exit
                        print(f"Error: Creator '{args.creator}' not found.", file=sys.stderr)
                        print("", file=sys.stderr)
                        print("Did you mean:", file=sys.stderr)
                        for pname, dname, sim in matches[:3]:
                            print(f"  - {pname} ({dname}) - {sim:.0%} match", file=sys.stderr)
                        print("", file=sys.stderr)
                        print("Use --fuzzy to auto-select when similarity > 80%", file=sys.stderr)
                        sys.exit(1)
                else:
                    print(f"Error: Creator '{args.creator}' not found and no similar names.", file=sys.stderr)
                    sys.exit(1)
            else:
                print("Error: Creator not found", file=sys.stderr)
                sys.exit(1)

        if not creator:
            print("Error: Creator not found", file=sys.stderr)
            sys.exit(1)

        # Load captions
        captions, stats = load_captions_for_context(conn, creator)

        if not captions:
            print("Error: No eligible captions found", file=sys.stderr)
            sys.exit(1)

        # Build context
        context = ScheduleContext(
            creator=creator,
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            total_captions_available=len(captions),
            captions_for_analysis=tuple(captions),
            performance_summary=stats,
            mode=args.mode,
        )

        # Handle semantic template output
        if args.output_semantic_template:
            # Determine output directory
            if args.semantic_output_dir:
                semantic_dir = Path(args.semantic_output_dir).expanduser()
            else:
                semantic_dir = HOME_DIR / ".eros" / "schedules" / "semantic" / creator.page_name

            semantic_dir.mkdir(parents=True, exist_ok=True)
            template_path = semantic_dir / f"{args.week}_template.json"
            results_path = semantic_dir / f"{args.week}_semantic.json"

            # Save the template
            template = save_semantic_template(context, template_path, args.week)

            # Print summary to stderr
            print(f"Semantic template saved to: {template_path}", file=sys.stderr)
            print(f"  Creator: {creator.display_name}", file=sys.stderr)
            print(f"  Week: {args.week}", file=sys.stderr)
            print(
                f"  Captions needing analysis: {template['statistics']['needs_analysis_count']}",
                file=sys.stderr,
            )
            print(f"  Total captions: {template['statistics']['total_captions']}", file=sys.stderr)
            print("", file=sys.stderr)
            print(f"Claude should save results to: {results_path}", file=sys.stderr)

            # If stdout mode, also print the template JSON
            if args.stdout:
                print(json.dumps(template, indent=2))

            # If chain mode, continue to generate_schedule.py
            # Otherwise exit here
            if not args.chain:
                sys.exit(0)

        # Format output
        if args.format == "json":
            # JSON format for programmatic use
            output = json.dumps(
                {
                    "creator": asdict(context.creator),
                    "week_start": context.week_start,
                    "week_end": context.week_end,
                    "total_captions": context.total_captions_available,
                    "performance_summary": context.performance_summary,
                    "captions": [asdict(c) for c in context.captions_for_analysis],
                    "mode": context.mode,
                },
                indent=2,
            )
        else:
            # Markdown format for Claude's native processing
            output = format_context_for_claude(context, week_arg=args.week)

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output)
            print(f"Context saved to {output_path}", file=sys.stderr)
            print(f"  Creator: {creator.display_name}", file=sys.stderr)
            print(f"  Week: {week_start} - {week_end}", file=sys.stderr)
            print(f"  Mode: {args.mode}", file=sys.stderr)
            print(
                f"  Captions: {len(captions)} ({stats['needs_analysis']} need analysis)",
                file=sys.stderr,
            )
        elif args.stdout:
            print(output)
        else:
            # Default: auto-save to standard location
            ext = ".json" if args.format == "json" else ".md"
            week_str = format_week_string(week_start)
            # Sanitize creator name for safe filesystem usage
            safe_page_name = re.sub(r"[^\w\-_]", "_", creator.page_name)
            context_dir = DEFAULT_SCHEDULES_DIR / "context" / safe_page_name
            try:
                context_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                print(f"Error: Cannot create output directory {context_dir}: {e}", file=sys.stderr)
                print(
                    "Use --stdout to print to console, or set EROS_SCHEDULES_PATH to a writable location.",
                    file=sys.stderr,
                )
                sys.exit(1)
            output_path = context_dir / f"{week_str}_context{ext}"
            output_path.write_text(output)
            print(f"Context saved to {output_path}", file=sys.stderr)
            print(f"  Creator: {creator.display_name}", file=sys.stderr)
            print(f"  Week: {week_start} - {week_end}", file=sys.stderr)
            print(f"  Mode: {args.mode}", file=sys.stderr)
            print(
                f"  Captions: {len(captions)} ({stats['needs_analysis']} need analysis)",
                file=sys.stderr,
            )

        # Chain to generate_schedule.py if --chain flag is set
        if args.chain:
            print("", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            print("CHAINING: Running generate_schedule.py", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            print("", file=sys.stderr)

            # Build the command to run generate_schedule.py
            generate_script = SCRIPT_DIR / "generate_schedule.py"
            cmd = [
                sys.executable,
                str(generate_script),
                "--creator",
                creator.page_name,
                "--week",
                args.week,
            ]

            # Pass through the database path if specified
            if args.db != str(DB_PATH):
                cmd.extend(["--db", args.db])

            try:
                result = subprocess.run(cmd, check=False)
                sys.exit(result.returncode)
            except FileNotFoundError:
                print(f"Error: generate_schedule.py not found at {generate_script}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error running generate_schedule.py: {e}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
