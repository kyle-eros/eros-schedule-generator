#!/usr/bin/env python3
"""
Generate Schedule - Main entry point for EROS schedule generation.

This script implements the 9-step schedule generation pipeline for
creating optimized weekly content schedules for OnlyFans creators.

Usage:
    python generate_schedule.py --creator missalexa --week 2025-W01
    python generate_schedule.py --creator-id abc123 --week 2025-W01 --output schedule.md
    python generate_schedule.py --batch --week 2025-W01 --format json

Pipeline Steps:
    1. ANALYZE - Load creator profile and analytics
    2. MATCH CONTENT - Filter by vault availability
    3. MATCH PERSONA - Score by voice profile
    4. BUILD STRUCTURE - Create weekly time slots
    5. ASSIGN CAPTIONS - Weighted selection (Vose Alias)
    6. GENERATE FOLLOW-UPS - Create follow-ups (if enabled)
    7. APPLY DRIP WINDOWS - Enforce no-PPV zones (if enabled)
    8. APPLY PAGE TYPE RULES - Paid vs Free rules (if enabled)
    9. VALIDATE & RETURN - Check business rules

Critical Business Rules:
    - PPV Spacing: MINIMUM 3 hours between PPV messages
    - Follow-ups: 15-45 minutes after each PPV (randomized)
    - Drip Windows: 4-8 hours, NO buying opportunities during window
    - Freshness: ALL captions must have freshness >= 30
    - Rotation: NEVER same content type consecutively
    - Vault: ALL content types must exist in creator's vault

Architecture:
    This module is the CLI entry point. Business logic is delegated to:
    - pipeline.py: 9-step orchestration
    - schedule_builder.py: Steps 1-4 (analyze, match content, persona, structure)
    - enrichment.py: Steps 6-8 (follow-ups, drip windows, page rules)
    - output_formatter.py: Markdown/JSON/CSV formatting
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from models import (
    Caption,
    CreatorProfile,
    ScheduleConfig,
    ScheduleItem,
    ScheduleResult,
    ValidationIssue,
)

# Configure module logger
logger = logging.getLogger(__name__)

# Re-export constants for backward compatibility with tests
from enrichment import MAX_VALIDATION_PASSES, MIN_FRESHNESS_SCORE, MIN_PPV_SPACING_HOURS


# =============================================================================
# DATABASE AND PATH CONFIGURATION
# =============================================================================

# Default database path from environment
DB_PATH = Path(
    os.environ.get(
        "EROS_DATABASE_PATH",
        os.path.expanduser("~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"),
    )
)

# Default schedules output directory
DEFAULT_SCHEDULES_DIR = Path(
    os.environ.get(
        "EROS_SCHEDULES_PATH",
        os.path.expanduser("~/.eros/schedules"),
    )
)


# =============================================================================
# OPTIONAL MODULE IMPORTS
# =============================================================================

# Volume optimizer
try:
    from volume_optimizer import MultiFactorVolumeOptimizer, VolumeStrategy

    VOLUME_OPTIMIZER_AVAILABLE = True
except ImportError:
    VOLUME_OPTIMIZER_AVAILABLE = False
    logger.debug("volume_optimizer module not available")

# Fuzzy matching for creator name suggestions
try:
    from prepare_llm_context import find_closest_creators

    FUZZY_MATCHING_AVAILABLE = True
except ImportError:
    FUZZY_MATCHING_AVAILABLE = False
    logger.debug("fuzzy matching not available")

# Content type registry for listing
try:
    from content_type_registry import REGISTRY

    CONTENT_TYPE_REGISTRY_AVAILABLE = True
except ImportError:
    CONTENT_TYPE_REGISTRY_AVAILABLE = False
    logger.debug("content_type_registry not available")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def parse_iso_week(week_str: str) -> tuple[date, date]:
    """
    Parse ISO week string (YYYY-Www) to start and end dates.

    Args:
        week_str: Week in ISO format, e.g., "2025-W01"

    Returns:
        Tuple of (week_start Monday, week_end Sunday)

    Example:
        >>> start, end = parse_iso_week("2025-W01")
        >>> start.isoformat()
        '2024-12-30'
    """
    try:
        week_start = datetime.strptime(week_str + "-1", "%G-W%V-%u").date()
    except ValueError:
        # Try alternate format
        parts = week_str.upper().split("W")
        if len(parts) == 2:
            year = int(parts[0].rstrip("-"))
            week = int(parts[1])
            week_start = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u").date()
        else:
            raise ValueError(f"Invalid week format: {week_str}")

    week_end = week_start + __import__("datetime").timedelta(days=6)
    return week_start, week_end


def format_week_string(d: date) -> str:
    """
    Format date as ISO week string.

    Args:
        d: Date to format

    Returns:
        ISO week string, e.g., "2025-W01"
    """
    return d.strftime("%G-W%V")


def get_volume_level(active_fans: int) -> tuple[str, int, int]:
    """
    Determine volume level from fan count (legacy fallback).

    Args:
        active_fans: Current active fan count

    Returns:
        Tuple of (volume_level, ppv_per_day, bump_per_day)
    """
    if active_fans < 1000:
        return ("Low", 2, 2)
    elif active_fans < 5000:
        return ("Mid", 3, 3)
    elif active_fans < 15000:
        return ("High", 4, 4)
    else:
        return ("Ultra", 5, 5)


def add_timing_variance(original_time: "datetime.time", is_weekend: bool = False) -> "datetime.time":
    """
    Add natural variance to a time to prevent robotic patterns.

    This function is kept for backward compatibility with tests.
    Business logic is now in schedule_builder.ScheduleBuilder._apply_timing_variance.

    Args:
        original_time: Original time object
        is_weekend: If True, allows wider variance (+/-10 min vs +/-7 min)

    Returns:
        New time object with variance applied
    """
    import random
    from datetime import time

    variance_minutes = 10 if is_weekend else 7
    variance = random.randint(-variance_minutes, variance_minutes)

    total_minutes = original_time.hour * 60 + original_time.minute + variance
    total_minutes = max(0, min(23 * 60 + 59, total_minutes))

    new_hour = total_minutes // 60
    new_minute = total_minutes % 60

    return time(hour=new_hour, minute=new_minute)


# =============================================================================
# PROFILE LOADING (for CLI)
# =============================================================================


def load_creator_profile(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None,
) -> CreatorProfile | None:
    """
    Load creator profile from database.

    Args:
        conn: Database connection with row_factory set
        creator_name: Creator's page_name or display_name
        creator_id: Creator's UUID

    Returns:
        CreatorProfile or None if not found
    """
    from schedule_builder import ScheduleBuilder, parse_content_notes, extract_filter_keywords, extract_price_modifiers

    if creator_name:
        query = """
            SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                   c.current_active_fans, c.notes,
                   cp.primary_tone, cp.emoji_frequency, cp.slang_level, cp.avg_sentiment
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.page_name = ? OR c.display_name = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_name, creator_name))
    elif creator_id:
        query = """
            SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                   c.current_active_fans, c.notes,
                   cp.primary_tone, cp.emoji_frequency, cp.slang_level, cp.avg_sentiment
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.creator_id = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_id,))
    else:
        return None

    row = cursor.fetchone()
    if not row:
        return None

    active_fans = row["current_active_fans"] or 0
    volume_level, _, _ = get_volume_level(active_fans)

    # Load best hours
    hours_query = """
        SELECT sending_hour
        FROM mass_messages
        WHERE creator_id = ? AND message_type = 'ppv' AND earnings IS NOT NULL
        GROUP BY sending_hour
        ORDER BY AVG(earnings) DESC
        LIMIT 10
    """
    hours_cursor = conn.execute(hours_query, (row["creator_id"],))
    best_hours = [r["sending_hour"] for r in hours_cursor.fetchall()]
    if not best_hours:
        best_hours = [10, 14, 18, 20, 21]

    # Load vault types
    vault_query = """
        SELECT content_type_id
        FROM vault_matrix
        WHERE creator_id = ? AND has_content = 1
    """
    vault_cursor = conn.execute(vault_query, (row["creator_id"],))
    vault_types = [r["content_type_id"] for r in vault_cursor.fetchall()]

    # Parse content notes
    content_notes = parse_content_notes(row["notes"])
    filter_keywords = extract_filter_keywords(content_notes)
    price_modifiers = extract_price_modifiers(content_notes)

    return CreatorProfile(
        creator_id=row["creator_id"],
        page_name=row["page_name"],
        display_name=row["display_name"] or row["page_name"],
        page_type=row["page_type"] or "paid",
        active_fans=active_fans,
        volume_level=volume_level,
        primary_tone=row["primary_tone"] or "playful",
        emoji_frequency=row["emoji_frequency"] or "moderate",
        slang_level=row["slang_level"] or "light",
        avg_sentiment=row["avg_sentiment"] or 0.5,
        best_hours=best_hours,
        vault_types=vault_types,
        content_notes=content_notes,
        filter_keywords=filter_keywords,
        price_modifiers=price_modifiers,
    )


# =============================================================================
# MAIN PIPELINE FUNCTION
# =============================================================================


def generate_schedule(config: ScheduleConfig, conn: sqlite3.Connection) -> ScheduleResult:
    """
    Generate a weekly schedule using the 9-step pipeline.

    This function delegates to the SchedulePipeline class which orchestrates
    all pipeline steps through the focused modules (schedule_builder, enrichment).

    Args:
        config: Schedule generation configuration
        conn: Database connection with row_factory set

    Returns:
        ScheduleResult with items, validation, and metadata

    Pipeline Steps:
        1. ANALYZE - Load creator profile and analytics
        2. MATCH CONTENT - Filter by vault availability
        3. MATCH PERSONA - Score by voice profile
        4. BUILD STRUCTURE - Create weekly time slots
        5. ASSIGN CAPTIONS - Weighted selection (Vose Alias)
        6. GENERATE FOLLOW-UPS - Create follow-ups (if enabled)
        7. APPLY DRIP WINDOWS - Enforce no-PPV zones (if enabled)
        8. APPLY PAGE TYPE RULES - Paid vs Free rules (if enabled)
        9. VALIDATE - Check business rules with auto-correction
    """
    from pipeline import SchedulePipeline

    pipeline = SchedulePipeline(config, conn, mode=config.mode)
    return pipeline.run()


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================


def format_markdown(result: ScheduleResult) -> str:
    """
    Format schedule result as professional Markdown.

    Args:
        result: The ScheduleResult object to format

    Returns:
        Formatted Markdown string
    """
    # Build mode indicator
    mode_indicator = f"Mode: {result.agent_mode.upper()}"
    if result.agent_mode == "enabled":
        mode_indicator = f"Mode: Agent-Assisted ({len(result.agents_used)}/{len(result.agents_used) + len(result.agents_fallback)} agents)"
    elif result.agent_mode == "partial":
        mode_indicator = f"Mode: Agent-Assisted (Partial)"

    lines = [
        f"# Weekly Schedule: {result.display_name}",
        f"## Week: {result.week_start} - {result.week_end}",
        f"## Volume: {result.volume_level} | Page Type: {result.page_type.upper()} | {mode_indicator}",
        "",
        "---",
        "",
        "### Creator Intelligence Brief",
        "",
        f"- **Best Hours**: {', '.join(f'{h:02d}:00' for h in result.best_hours[:5])}",
        f"- **Vault Types**: {', '.join(result.vault_types[:8]) if result.vault_types else 'N/A'}",
        "",
    ]

    # Group items by date
    items_by_date: dict[str, list[ScheduleItem]] = {}
    for item in result.items:
        if item.scheduled_date not in items_by_date:
            items_by_date[item.scheduled_date] = []
        items_by_date[item.scheduled_date].append(item)

    # Daily schedules
    for date_str in sorted(items_by_date.keys()):
        day_items = items_by_date[date_str]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = dt.strftime("%A")

        lines.append(f"### {day_name} {date_str}")
        lines.append("")
        lines.append("| Time | Type | Content | Price | Score | Fresh | Notes |")
        lines.append("|------|------|---------|-------|-------|-------|-------|")

        ppv_count = 0
        bump_count = 0

        for item in sorted(day_items, key=lambda x: x.scheduled_time):
            if item.item_type == "ppv":
                ppv_count += 1
                caption_preview = item.caption_text or "[No caption]"
                caption_preview = caption_preview.replace("|", "/").replace("\n", " ")
                if len(caption_preview) > 50:
                    caption_preview = caption_preview[:50] + "..."

                price_str = f"${item.suggested_price:.2f}" if item.suggested_price else "-"
                lines.append(
                    f"| {item.scheduled_time} | PPV | {item.content_type_name or 'N/A'} | "
                    f"{price_str} | {item.performance_score:.0f} | {item.freshness_score:.0f} | - |"
                )
            elif item.item_type == "bump":
                bump_count += 1
                caption_preview = item.caption_text or "(follow-up)"
                if len(caption_preview) > 50:
                    caption_preview = caption_preview[:50] + "..."
                lines.append(
                    f"| {item.scheduled_time} | Bump | - | - | - | - | - |"
                )
            elif item.item_type == "drip":
                lines.append(
                    f"| {item.scheduled_time} | Drip | - | - | - | - | Drip window |"
                )

        lines.append("")
        lines.append(f"**Daily Summary**: {ppv_count} PPVs | {bump_count} Bumps")
        lines.append("")

    # Weekly summary
    lines.extend([
        "---",
        "",
        "### Weekly Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total PPVs | {result.total_ppvs} |",
        f"| Total Follow-ups | {result.total_follow_ups} |",
        f"| Unique Captions | {result.unique_captions} |",
        f"| Avg Caption Score | {result.avg_performance:.1f} |",
        f"| Avg Freshness | {result.avg_freshness:.1f} |",
        "",
    ])

    # Validation status
    lines.extend(["### Validation Status", ""])

    error_rules = {i.rule_name for i in result.validation_issues if i.severity == "error"}
    warning_rules = {i.rule_name for i in result.validation_issues if i.severity == "warning"}

    checks = [
        ("ppv_spacing", "PPV Spacing (>= 3h)"),
        ("duplicate_captions", "No Duplicate Captions"),
        ("freshness_threshold", "Freshness Compliance (>= 30)"),
        ("content_rotation", "Content Rotation"),
        ("followup_timing", "Follow-up Timing (15-45 min)"),
    ]

    for rule, label in checks:
        if rule in error_rules:
            lines.append(f"- FAILED: {label}")
        elif rule in warning_rules:
            lines.append(f"- WARNING: {label}")
        else:
            lines.append(f"- PASSED: {label}")

    lines.append("")
    lines.append(f"**Status:** {'PASSED' if result.validation_passed else 'FAILED'}")
    lines.append("")

    if result.validation_issues:
        lines.append("### Issues Found")
        lines.append("")
        for issue in result.validation_issues[:10]:
            severity_marker = "[ERROR]" if issue.severity == "error" else "[WARN]"
            lines.append(f"- {severity_marker} **{issue.rule_name}**: {issue.message}")
        lines.append("")

    lines.extend([
        "---",
        f"Generated: {result.generated_at} | Schedule ID: {result.schedule_id}",
        f"EROS Schedule Generator v3.1",
        "",
    ])

    return "\n".join(lines)


def format_json(result: ScheduleResult) -> str:
    """
    Format schedule result as JSON.

    Args:
        result: The ScheduleResult object to format

    Returns:
        Formatted JSON string with 2-space indentation
    """
    data = {
        "metadata": {
            "version": "3.1",
            "schedule_id": result.schedule_id,
            "creator_id": result.creator_id,
            "creator_name": result.creator_name,
            "display_name": result.display_name,
            "page_type": result.page_type,
            "volume_level": result.volume_level,
            "week_start": result.week_start,
            "week_end": result.week_end,
            "generated_at": result.generated_at,
        },
        "schedule": [],
        "summary": {
            "total_items": len(result.items),
            "total_ppvs": result.total_ppvs,
            "total_bumps": result.total_bumps,
            "total_follow_ups": result.total_follow_ups,
            "unique_captions": result.unique_captions,
            "avg_freshness": round(result.avg_freshness, 2),
            "avg_performance": round(result.avg_performance, 2),
        },
        "agent_system": {
            "mode": result.agent_mode,
            "agents_used": result.agents_used,
            "agents_fallback": result.agents_fallback,
        },
        "validation": {
            "passed": result.validation_passed,
            "errors": sum(1 for i in result.validation_issues if i.severity == "error"),
            "warnings": sum(1 for i in result.validation_issues if i.severity == "warning"),
            "issues": [
                {
                    "rule_name": issue.rule_name,
                    "severity": issue.severity,
                    "message": issue.message,
                    "item_ids": list(issue.item_ids),
                    "auto_correctable": issue.auto_correctable,
                }
                for issue in result.validation_issues
            ],
        },
        "best_hours": result.best_hours,
        "vault_types": result.vault_types,
    }

    # Build schedule items
    for item in result.items:
        item_dict = {
            "item_id": item.item_id,
            "scheduled_date": item.scheduled_date,
            "scheduled_time": item.scheduled_time,
            "item_type": item.item_type,
            "content_type_id": item.content_type_id,
            "content_type_name": item.content_type_name,
            "caption_id": item.caption_id,
            "caption_preview": (
                item.caption_text[:100] + "..."
                if item.caption_text and len(item.caption_text) > 100
                else item.caption_text
            ),
            "suggested_price": item.suggested_price,
            "freshness_score": round(item.freshness_score, 2),
            "performance_score": round(item.performance_score, 2),
            "is_follow_up": item.is_follow_up,
            "parent_item_id": item.parent_item_id,
            "status": item.status,
            "priority": item.priority,
        }
        data["schedule"].append(item_dict)

    return json.dumps(data, indent=2, default=str)


def format_csv(result: ScheduleResult) -> str:
    """
    Format schedule result as CSV for spreadsheet export.

    Args:
        result: The ScheduleResult object to format

    Returns:
        Formatted CSV string
    """
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Day",
        "Time",
        "Item Type",
        "Content Type",
        "Caption ID",
        "Caption Preview",
        "Price",
        "Performance Score",
        "Freshness Score",
        "Is Follow-up",
        "Parent Item ID",
    ])

    # Data rows
    for item in result.items:
        preview = ""
        if item.caption_text:
            preview = item.caption_text[:100].replace("\n", " ")
            if len(item.caption_text) > 100:
                preview += "..."

        writer.writerow([
            item.scheduled_date,
            item.scheduled_time,
            item.item_type or "",
            item.content_type_name or "",
            item.caption_id or "",
            preview,
            f"{item.suggested_price:.2f}" if item.suggested_price else "",
            f"{item.performance_score:.1f}",
            f"{item.freshness_score:.1f}",
            "Yes" if item.is_follow_up else "No",
            item.parent_item_id or "",
        ])

    return output.getvalue()


# =============================================================================
# BATCH MODE
# =============================================================================


def generate_batch_schedules(
    conn: sqlite3.Connection,
    week_start: date,
    week_end: date,
    output_dir: Path | None = None,
) -> list[ScheduleResult]:
    """
    Generate schedules for all active creators.

    Args:
        conn: Database connection
        week_start: Week start date
        week_end: Week end date
        output_dir: Optional output directory

    Returns:
        List of ScheduleResult objects
    """
    cursor = conn.execute(
        "SELECT creator_id, page_name, page_type, current_active_fans FROM creators WHERE is_active = 1"
    )
    creators = cursor.fetchall()

    results = []
    total = len(creators)

    for i, creator in enumerate(creators, 1):
        page_name = creator["page_name"]
        print(f"[{i}/{total}] Generating schedule for {page_name}...", file=sys.stderr)

        # Determine volume level
        volume_level, ppv_per_day, bump_per_day = get_volume_level(
            creator["current_active_fans"] or 0
        )

        config = ScheduleConfig(
            creator_id=creator["creator_id"],
            creator_name=creator["page_name"],
            page_type=creator["page_type"] or "paid",
            week_start=week_start,
            week_end=week_end,
            volume_level=volume_level,
            ppv_per_day=ppv_per_day,
            bump_per_day=bump_per_day,
            enable_follow_ups=True,
        )

        result = generate_schedule(config, conn)
        results.append(result)

        # Save individual file if output_dir specified
        if output_dir:
            safe_page_name = re.sub(r"[^\w\-_]", "_", page_name)
            creator_dir = output_dir / safe_page_name
            try:
                creator_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                logger.error(f"Cannot create {creator_dir}: {e}")
                continue
            week_str = format_week_string(week_start)
            output_file = creator_dir / f"{week_str}.md"
            output_file.write_text(format_markdown(result))
            print(f"    Saved to {output_file}", file=sys.stderr)

    return results


# =============================================================================
# CONTENT TYPE LISTING
# =============================================================================


def list_content_types(page_type: str | None = None) -> None:
    """
    Print all available content types with their metadata.

    Args:
        page_type: If specified, only show types valid for this page type
    """
    if not CONTENT_TYPE_REGISTRY_AVAILABLE:
        print("Content type registry not available", file=sys.stderr)
        return

    print("\n" + "=" * 70)
    print("EROS Content Type Registry")
    print("=" * 70 + "\n")

    if page_type:
        types = REGISTRY.get_types_for_page(page_type)
        print(f"Content types for {page_type.upper()} pages:\n")
    else:
        types = REGISTRY.get_all()
        print("All content types:\n")

    # Group by priority tier
    by_tier: dict[int, list] = defaultdict(list)
    for t in types:
        by_tier[t.priority_tier].append(t)

    tier_names = {
        1: "Tier 1 - Direct Revenue",
        2: "Tier 2 - Feed/Wall",
        3: "Tier 3 - Engagement",
        4: "Tier 4 - Retention",
    }

    for tier in sorted(by_tier.keys()):
        print(f"\n{tier_names.get(tier, f'Tier {tier}')}:")
        print("-" * 70)
        for t in by_tier[tier]:
            page_note = " [PAID ONLY]" if t.page_type_filter == "paid" else ""
            print(f"  {t.type_id:<20} {t.name}{page_note}")
            print(
                f"      Max: {t.max_daily}/day, {t.max_weekly}/week | "
                f"Spacing: {t.min_spacing_hours}h | "
                f"Channel: {t.channel}"
            )

    print("\n" + "=" * 70)
    print(f"Total: {len(types)} content types")
    print("=" * 70 + "\n")


# =============================================================================
# SCHEDULE SUMMARY
# =============================================================================


def print_schedule_summary(result: ScheduleResult) -> None:
    """
    Print a summary of the generated schedule to stderr.

    Args:
        result: The ScheduleResult to summarize
    """
    print("\n" + "=" * 50, file=sys.stderr)
    print(f"Schedule Summary: {result.creator_name}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print(f"  Week: {result.week_start} to {result.week_end}", file=sys.stderr)
    print(f"  Volume Level: {result.volume_level}", file=sys.stderr)
    print(f"  Page Type: {result.page_type}", file=sys.stderr)
    print(f"  Total Items: {len(result.items)}", file=sys.stderr)
    print(f"  PPVs: {result.total_ppvs}", file=sys.stderr)
    print(f"  Follow-ups: {result.total_follow_ups}", file=sys.stderr)
    print(f"  Unique Captions: {result.unique_captions}", file=sys.stderr)
    print(f"  Avg Freshness: {result.avg_freshness:.1f}", file=sys.stderr)
    print(f"  Avg Performance: {result.avg_performance:.1f}", file=sys.stderr)

    if result.validation_passed:
        print("  Validation: PASSED", file=sys.stderr)
    else:
        error_count = sum(1 for i in result.validation_issues if i.severity == "error")
        warning_count = sum(1 for i in result.validation_issues if i.severity == "warning")
        print(
            f"  Validation: FAILED ({error_count} errors, {warning_count} warnings)",
            file=sys.stderr,
        )

    print("=" * 50 + "\n", file=sys.stderr)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate optimized weekly content schedules for OnlyFans creators.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_schedule.py --creator missalexa --week 2025-W01
    python generate_schedule.py --creator-id abc123 --week 2025-W01 --output schedule.md
    python generate_schedule.py --batch --week 2025-W01 --output-dir schedules/

Business Rules Enforced:
    - PPV Spacing: MINIMUM 3 hours between PPV messages
    - Follow-ups: 15-45 minutes after each PPV
    - Freshness: ALL captions must have freshness >= 30
    - Rotation: NEVER same content type consecutively
        """,
    )

    parser.add_argument("--creator", "-c", help="Creator page name (e.g., missalexa)")
    parser.add_argument("--creator-id", help="Creator UUID")
    parser.add_argument(
        "--week", "-w", required=True, help="Week in ISO format (YYYY-Www, e.g., 2025-W01)"
    )
    parser.add_argument(
        "--batch", "-b", action="store_true", help="Generate schedules for all active creators"
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--output-dir", help="Output directory for batch mode")
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
        choices=["markdown", "json", "csv"],
        default="markdown",
        help="Output format: markdown (default), json, or csv",
    )
    parser.add_argument(
        "--no-follow-ups", action="store_true", help="Disable follow-up bump generation"
    )
    parser.add_argument(
        "--enable-drip", action="store_true", help="Enable drip window enforcement"
    )
    parser.add_argument("--db", default=str(DB_PATH), help=f"Database path (default: {DB_PATH})")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use quick mode (pattern-based, no semantic analysis)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["quick", "full"],
        default="full",
        help="Generation mode: quick or full (default)",
    )
    parser.add_argument(
        "--use-agents",
        action="store_true",
        help="Enable sub-agent delegation for enhanced optimization",
    )
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Auto-select closest matching creator if similarity > 80%%",
    )
    parser.add_argument(
        "--page-type",
        type=str,
        choices=["paid", "free"],
        help="Override page type (usually auto-detected)",
    )
    parser.add_argument(
        "--volume",
        type=str,
        choices=["Low", "Mid", "High", "Ultra"],
        help="Override volume level (usually auto-calculated)",
    )
    parser.add_argument(
        "--list-content-types",
        action="store_true",
        help="List all available content types and exit",
    )

    args = parser.parse_args()

    # Handle --list-content-types early exit
    if args.list_content_types:
        list_content_types(args.page_type)
        return

    # Handle --quick flag override
    if args.quick:
        args.mode = "quick"
        logger.info("Running in quick mode (pattern-based, no semantic analysis)")

    if not args.batch and not args.creator and not args.creator_id:
        parser.error("Must specify --creator, --creator-id, or --batch")

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

        if args.batch:
            # Generate for all active creators
            if args.output_dir:
                output_dir = Path(args.output_dir)
            elif not args.stdout:
                output_dir = DEFAULT_SCHEDULES_DIR
            else:
                output_dir = None

            results = generate_batch_schedules(conn, week_start, week_end, output_dir)

            if not output_dir:
                if args.format == "json":
                    output = json.dumps(
                        [json.loads(format_json(r)) for r in results], indent=2
                    )
                elif args.format == "csv":
                    csv_outputs = [format_csv(r) for r in results]
                    if csv_outputs:
                        lines = [csv_outputs[0]]
                        for csv_out in csv_outputs[1:]:
                            csv_lines = csv_out.split("\n", 1)
                            if len(csv_lines) > 1:
                                lines.append(csv_lines[1])
                        output = "\n".join(lines)
                    else:
                        output = ""
                else:
                    output = "\n\n---\n\n".join(format_markdown(r) for r in results)

                if args.output:
                    Path(args.output).write_text(output)
                    print(f"Batch schedule written to {args.output}")
                else:
                    print(output)

            passed = sum(1 for r in results if r.validation_passed)
            print(
                f"\nBatch complete: {passed}/{len(results)} schedules passed validation",
                file=sys.stderr,
            )

        else:
            # Generate for single creator
            profile = load_creator_profile(
                conn, creator_name=args.creator, creator_id=args.creator_id
            )

            if not profile:
                # Try fuzzy matching
                if args.creator and FUZZY_MATCHING_AVAILABLE:
                    matches = find_closest_creators(args.creator, conn, threshold=0.5)

                    if matches:
                        top_match = matches[0]
                        page_name, display_name, similarity = top_match

                        if args.fuzzy and similarity > 0.8:
                            print(
                                f"Fuzzy match: '{args.creator}' -> '{page_name}' "
                                f"({similarity:.0%} similarity)",
                                file=sys.stderr,
                            )
                            profile = load_creator_profile(conn, creator_name=page_name)
                        else:
                            print(f"Error: Creator '{args.creator}' not found.", file=sys.stderr)
                            print("", file=sys.stderr)
                            print("Did you mean:", file=sys.stderr)
                            for pname, dname, sim in matches[:3]:
                                print(f"  - {pname} ({dname}) - {sim:.0%} match", file=sys.stderr)
                            print("", file=sys.stderr)
                            print("Use --fuzzy to auto-select when similarity > 80%", file=sys.stderr)
                            sys.exit(1)
                    else:
                        print(
                            f"Error: Creator '{args.creator}' not found and no similar names.",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                else:
                    print("Error: Creator not found", file=sys.stderr)
                    sys.exit(1)

            if not profile:
                print("Error: Creator not found", file=sys.stderr)
                sys.exit(1)

            # Determine volume level
            volume_level, ppv_per_day, bump_per_day = get_volume_level(profile.active_fans)

            # Apply overrides
            effective_page_type = args.page_type if args.page_type else profile.page_type
            effective_volume = args.volume if args.volume else volume_level

            config = ScheduleConfig(
                creator_id=profile.creator_id,
                creator_name=profile.page_name,
                page_type=effective_page_type,
                week_start=week_start,
                week_end=week_end,
                volume_level=effective_volume,
                ppv_per_day=ppv_per_day,
                bump_per_day=bump_per_day,
                enable_follow_ups=not args.no_follow_ups,
                enable_drip_windows=args.enable_drip,
                mode=args.mode,
                use_agents=args.use_agents,
            )

            # Display mode information
            if args.mode == "full":
                print(f"[FULL MODE] Running with semantic analysis", file=sys.stderr)

            result = generate_schedule(config, conn)

            # Print summary
            print_schedule_summary(result)

            if args.format == "json":
                output = format_json(result)
                ext = ".json"
            elif args.format == "csv":
                output = format_csv(result)
                ext = ".csv"
            else:
                output = format_markdown(result)
                ext = ".md"

            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(output)
                print(f"Schedule saved to {output_path}", file=sys.stderr)
            elif args.stdout:
                print(output)
            else:
                week_str = format_week_string(week_start)
                safe_creator_name = re.sub(r"[^\w\-_]", "_", config.creator_name)
                creator_dir = DEFAULT_SCHEDULES_DIR / safe_creator_name
                try:
                    creator_dir.mkdir(parents=True, exist_ok=True)
                except PermissionError as e:
                    print(
                        f"Error: Cannot create output directory {creator_dir}: {e}",
                        file=sys.stderr,
                    )
                    print(
                        "Use --stdout to print to console, or set EROS_SCHEDULES_PATH to a writable location.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                output_path = creator_dir / f"{week_str}{ext}"
                output_path.write_text(output)
                print(f"Schedule saved to {output_path}", file=sys.stderr)

            # Exit code based on validation
            if not result.validation_passed:
                print("\nWarning: Schedule has validation errors", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
