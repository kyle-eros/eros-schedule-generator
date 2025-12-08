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
import json
import logging
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Configure logging for this module
logger = logging.getLogger(__name__)

# Import from existing scripts
from match_persona import (
    PersonaProfile,
    get_persona_profile,
    detect_tone_from_text,
    detect_slang_level_from_text,
    calculate_sentiment,
    get_emoji_frequency_category,
    calculate_persona_boost,
    TONE_KEYWORDS,
)
from volume_optimizer import MultiFactorVolumeOptimizer, VolumeStrategy


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
            ct = p.get('content_type') or 'all content'
            mod = p.get('price_modifier', 1.0)
            lines.append(f"- {ct}: {p['description']} (modifier: {mod}x)")
        lines.append("")

    if notes.get("caption_filters", {}).get("exclude_keywords"):
        lines.append(f"**Excluded Keywords**: {', '.join(notes['caption_filters']['exclude_keywords'])}")

    return "\n".join(lines)


# Path resolution - check multiple possible database locations
# Standard order: 1) env var, 2) Developer, 3) Documents, 4) .eros fallback
SCRIPT_DIR = Path(__file__).parent
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

# Default output directory for schedules/context
_env_schedules_path = os.environ.get("EROS_SCHEDULES_PATH", "")
DEFAULT_SCHEDULES_DIR = (
    Path(_env_schedules_path) if _env_schedules_path
    else HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "schedules"
)


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
    """
    # Legacy fallback for simple fan-count based volume
    if active_fans < 1000:
        return ("Low", 2)
    elif active_fans < 5000:
        return ("Mid", 3)
    elif active_fans < 15000:
        return ("High", 4)
    else:
        return ("Ultra", 5)


def prepare_volume_context(
    creator_id: str,
    conn: sqlite3.Connection
) -> dict[str, Any]:
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
    text: str,
    tone_scores: dict[str, int],
    detected_tone: str | None
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
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None
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
            str(e)
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
        content_notes=content_notes
    )


def load_captions_for_context(
    conn: sqlite3.Connection,
    creator: CreatorContext,
    limit: int = 100
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

    # Build persona for boost calculation
    persona = PersonaProfile(
        creator_id=creator.creator_id,
        page_name=creator.page_name,
        primary_tone=creator.primary_tone,
        secondary_tone=creator.secondary_tone,
        emoji_frequency=creator.emoji_frequency,
        slang_level=creator.slang_level,
        avg_sentiment=creator.avg_sentiment
    )

    captions = []
    stats = {
        "total_evaluated": 0,
        "needs_analysis": 0,
        "high_confidence": 0,
        "low_confidence": 0,
        "high_value": 0,
        "avg_performance": 0.0,
        "avg_freshness": 0.0
    }

    total_perf = 0.0
    total_fresh = 0.0

    for row in rows:
        stats["total_evaluated"] += 1

        text = row["caption_text"] or ""
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
            use_text_detection=True
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

        captions.append(CaptionContext(
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
            analysis_reason=analysis_reason
        ))

    if stats["total_evaluated"] > 0:
        stats["avg_performance"] = round(total_perf / stats["total_evaluated"], 1)
        stats["avg_freshness"] = round(total_fresh / stats["total_evaluated"], 1)

    # Sort: needs_analysis first, then by performance
    captions.sort(key=lambda c: (not c.needs_semantic_analysis, -c.performance_score))

    return captions, stats


def format_context_for_claude(context: ScheduleContext) -> str:
    """
    Format the complete context as markdown for Claude to process.

    This is the KEY integration point - the output becomes part of Claude's
    conversation context, and Claude applies its semantic reasoning directly.
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
        f"| Attribute | Value |",
        f"|-----------|-------|",
        f"| Creator | **{c.display_name}** (@{c.page_name}) |",
        f"| Page Type | {c.page_type} |",
        f"| Active Fans | {c.active_fans:,} |",
        f"| Volume Level | {c.volume_level} ({c.ppv_per_day} PPV/day){' [LEGACY FALLBACK]' if c.volume_fallback_used else ''} |",
        "",
        "### Persona Profile",
        "",
        f"| Attribute | Value |",
        f"|-----------|-------|",
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
        lines.extend([
            "### Creator Content Notes",
            "",
            format_notes_for_llm(c.content_notes),
            "",
        ])

    lines.extend([
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
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Available | {context.total_captions_available} |",
        f"| Needs Semantic Analysis | {context.performance_summary['needs_analysis']} |",
        f"| High Confidence | {context.performance_summary['high_confidence']} |",
        f"| High Value (perf >= 70) | {context.performance_summary['high_value']} |",
        f"| Avg Performance | {context.performance_summary['avg_performance']} |",
        f"| Avg Freshness | {context.performance_summary['avg_freshness']} |",
        "",
    ])

    if context.mode == "full":
        # Include captions for semantic analysis
        needs_analysis = [cap for cap in context.captions_for_analysis if cap.needs_semantic_analysis]
        high_confidence = [cap for cap in context.captions_for_analysis if not cap.needs_semantic_analysis]

        lines.extend([
            "---",
            "",
            "## Captions Requiring Semantic Analysis",
            "",
            "These captions have low pattern-matching confidence and need your semantic reasoning.",
            "",
        ])

        for i, cap in enumerate(needs_analysis[:MAX_CAPTIONS_FOR_CONTEXT], 1):
            lines.extend([
                f"### Caption #{i} (ID: {cap.caption_id})",
                "",
                f"**Text**: \"{cap.caption_text}\"",
                "",
                f"- Content Type: {cap.content_type or 'N/A'}",
                f"- Performance: {cap.performance_score} | Freshness: {cap.freshness_score}",
                f"- Pattern Detection: tone=`{cap.pattern_tone}`, slang=`{cap.pattern_slang}`, confidence={cap.pattern_confidence:.0%}",
                f"- Current Boost: {cap.pattern_boost}x",
                f"- **Analysis Reason**: {cap.analysis_reason}",
                "",
            ])

        if len(needs_analysis) > MAX_CAPTIONS_FOR_CONTEXT:
            lines.append(f"*({len(needs_analysis) - MAX_CAPTIONS_FOR_CONTEXT} more captions need analysis)*")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## High-Confidence Captions (Pre-Scored)",
            "",
            "These captions have high pattern-matching confidence. Review briefly for accuracy.",
            "",
            "| ID | Type | Perf | Fresh | Tone | Boost |",
            "|----|------|------|-------|------|-------|",
        ])

        for cap in high_confidence[:20]:
            lines.append(
                f"| {cap.caption_id} | {cap.content_type or 'N/A'} | {cap.performance_score} | "
                f"{cap.freshness_score} | {cap.pattern_tone or '-'} | {cap.pattern_boost}x |"
            )

        if len(high_confidence) > 20:
            lines.append(f"| ... | ... | ... | ... | ... | ({len(high_confidence) - 20} more) |")

        lines.extend([
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
            f"| Factor | Match Condition | Boost |",
            f"|--------|----------------|-------|",
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
            "| \"I guess\" + generous offer | Bratty teasing |",
            "| \"Fine...\" + gift | Playfully reluctant |",
            "| Exaggerated compliance | Bratty |",
            "| \"Right now\" | Could be aggressive OR playfully demanding |",
            "| Direct pricing language | Direct tone (even if dressed up) |",
            "| \"babe/baby\" + offer | Sweet/seductive, relationship-building |",
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
        ])

    else:  # quick mode
        lines.extend([
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
        ])

        for cap in context.captions_for_analysis[:30]:
            lines.append(
                f"| {cap.caption_id} | {cap.content_type or 'N/A'} | {cap.performance_score} | "
                f"{cap.freshness_score} | {cap.pattern_tone or '-'} | {cap.pattern_boost}x |"
            )

        lines.extend([
            "",
            f"Generate a {c.ppv_per_day * 7}-PPV schedule using these pre-scored captions.",
            "",
        ])

    return "\n".join(lines)


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
        "--week", "-w",
        required=True,
        help="Week in ISO format (YYYY-Www, e.g., 2025-W01)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["quick", "full"],
        default="full",
        help="Generation mode: quick (pattern only) or full (semantic analysis)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (overrides auto-save location)"
    )
    parser.add_argument(
        "--stdout", "--print",
        action="store_true",
        dest="stdout",
        help="Print to console instead of auto-saving to file"
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

    # Parse week
    try:
        week_start, week_end = parse_iso_week(args.week)
    except Exception as e:
        parser.error(f"Invalid week format: {e}")

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Load creator context
        creator = load_creator_context(
            conn,
            creator_name=args.creator,
            creator_id=args.creator_id
        )

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
            mode=args.mode
        )

        # Format output
        if args.format == "json":
            # JSON format for programmatic use
            output = json.dumps({
                "creator": asdict(context.creator),
                "week_start": context.week_start,
                "week_end": context.week_end,
                "total_captions": context.total_captions_available,
                "performance_summary": context.performance_summary,
                "captions": [asdict(c) for c in context.captions_for_analysis],
                "mode": context.mode
            }, indent=2)
        else:
            # Markdown format for Claude's native processing
            output = format_context_for_claude(context)

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output)
            print(f"Context saved to {output_path}", file=sys.stderr)
            print(f"  Creator: {creator.display_name}", file=sys.stderr)
            print(f"  Week: {week_start} - {week_end}", file=sys.stderr)
            print(f"  Mode: {args.mode}", file=sys.stderr)
            print(f"  Captions: {len(captions)} ({stats['needs_analysis']} need analysis)", file=sys.stderr)
        elif args.stdout:
            print(output)
        else:
            # Default: auto-save to standard location
            ext = ".json" if args.format == "json" else ".md"
            week_str = format_week_string(week_start)
            # Sanitize creator name for safe filesystem usage
            safe_page_name = re.sub(r'[^\w\-_]', '_', creator.page_name)
            context_dir = DEFAULT_SCHEDULES_DIR / "context" / safe_page_name
            try:
                context_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                print(f"Error: Cannot create output directory {context_dir}: {e}", file=sys.stderr)
                print("Use --stdout to print to console, or set EROS_SCHEDULES_PATH to a writable location.", file=sys.stderr)
                sys.exit(1)
            output_path = context_dir / f"{week_str}_context{ext}"
            output_path.write_text(output)
            print(f"Context saved to {output_path}", file=sys.stderr)
            print(f"  Creator: {creator.display_name}", file=sys.stderr)
            print(f"  Week: {week_start} - {week_end}", file=sys.stderr)
            print(f"  Mode: {args.mode}", file=sys.stderr)
            print(f"  Captions: {len(captions)} ({stats['needs_analysis']} need analysis)", file=sys.stderr)


if __name__ == "__main__":
    main()
