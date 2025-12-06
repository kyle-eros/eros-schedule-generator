#!/usr/bin/env python3
"""
Validate Schedule - Validate schedule against business rules.

This script validates a generated schedule against all EROS business rules:
1. PPV Spacing - Minimum 3-4 hours between PPVs
2. Follow-up Timing - 15-45 minutes after parent PPV
3. Duplicate Captions - No duplicate captions in same week
4. Content Rotation - Variety in content types
5. Freshness Scores - Minimum freshness threshold
6. Volume Compliance - Match daily targets
7. Vault Availability - Content types in vault

Usage:
    python validate_schedule.py --input schedule.json
    python validate_schedule.py --input schedule.json --strict
    python validate_schedule.py --input schedule.json --output report.md
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Represents a validation issue."""

    rule_name: str
    severity: str  # error, warning, info
    message: str
    item_ids: tuple[int, ...] = ()


@dataclass
class ValidationResult:
    """Result of validation."""

    is_valid: bool = True
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, rule: str, message: str, item_ids: list[int] | None = None):
        """Add an error issue."""
        self.issues.append(ValidationIssue(
            rule_name=rule,
            severity="error",
            message=message,
            item_ids=tuple(item_ids) if item_ids else ()
        ))
        self.error_count += 1
        self.is_valid = False

    def add_warning(self, rule: str, message: str, item_ids: list[int] | None = None):
        """Add a warning issue."""
        self.issues.append(ValidationIssue(
            rule_name=rule,
            severity="warning",
            message=message,
            item_ids=tuple(item_ids) if item_ids else ()
        ))
        self.warning_count += 1

    def add_info(self, rule: str, message: str, item_ids: list[int] | None = None):
        """Add an info issue."""
        self.issues.append(ValidationIssue(
            rule_name=rule,
            severity="info",
            message=message,
            item_ids=tuple(item_ids) if item_ids else ()
        ))
        self.info_count += 1


class ScheduleValidator:
    """
    Validates schedule items against business rules.

    Rules:
    1. ppv_spacing - PPVs must be 3+ hours apart (error if < 3, warning if < 4)
    2. followup_timing - Follow-ups must be 15-45 min after parent
    3. duplicate_captions - No duplicate caption_ids in same week
    4. content_rotation - Warn if same content type > 3x consecutively
    5. freshness_threshold - All captions must have freshness >= 30
    6. volume_compliance - Daily PPV count should match target
    7. vault_availability - Content types should be in vault
    8. wall_post_spacing - Wall posts must be 2+ hours apart (NEW)
    9. preview_ppv_linkage - Free previews must precede linked PPV by 1-3 hours (NEW)
    10. poll_spacing - Polls must be 2+ days apart (NEW)
    11. poll_duration - Poll duration must be 24, 48, or 72 hours (NEW)
    12. game_wheel_validity - Game wheel config must be valid (NEW)
    """

    def __init__(
        self,
        min_ppv_spacing_hours: float = 4.0,
        min_freshness: float = 30.0,
        max_consecutive_same_type: int = 3
    ):
        """
        Initialize validator with thresholds.

        Args:
            min_ppv_spacing_hours: Recommended minimum hours between PPVs
            min_freshness: Minimum freshness score for captions
            max_consecutive_same_type: Max consecutive items of same content type
        """
        self.min_ppv_spacing_hours = min_ppv_spacing_hours
        self.min_freshness = min_freshness
        self.max_consecutive_same_type = max_consecutive_same_type

    def validate(
        self,
        items: list[dict[str, Any]],
        volume_target: int | None = None,
        vault_types: list[int] | None = None
    ) -> ValidationResult:
        """
        Validate schedule items against all rules.

        Args:
            items: List of schedule item dicts
            volume_target: Optional daily PPV target
            vault_types: Optional list of available content_type_ids

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult()

        if not items:
            result.add_warning("empty_schedule", "Schedule has no items")
            return result

        # Run all validations
        self._check_ppv_spacing(items, result)
        self._check_followup_timing(items, result)
        self._check_duplicate_captions(items, result)
        self._check_content_rotation(items, result)
        self._check_freshness_scores(items, result)

        if volume_target:
            self._check_volume_compliance(items, volume_target, result)

        if vault_types:
            self._check_vault_availability(items, vault_types, result)

        # NEW: Check expanded content type rules
        self._check_wall_post_spacing(items, result)
        self._check_preview_ppv_linkage(items, result)
        self._check_poll_spacing(items, result)
        self._check_poll_duration(items, result)
        self._check_game_wheel_validity(items, result)
        self._check_daily_wall_post_limit(items, result)
        self._check_weekly_poll_limit(items, result)

        return result

    def _parse_datetime(self, item: dict[str, Any]) -> datetime | None:
        """Parse scheduled datetime from item."""
        try:
            date_str = item.get("scheduled_date", "")
            time_str = item.get("scheduled_time", "00:00")
            return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return None

    def _check_ppv_spacing(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: PPV messages must be at least 3 hours apart (4 hours recommended).

        Severity:
        - < 3 hours: ERROR (blocks schedule)
        - 3-4 hours: WARNING (flagged for review)
        """
        ppv_items = [
            item for item in items
            if item.get("item_type") == "ppv"
        ]

        if len(ppv_items) < 2:
            return

        # Sort by datetime
        ppv_with_dt = []
        for item in ppv_items:
            dt = self._parse_datetime(item)
            if dt:
                ppv_with_dt.append((dt, item))

        ppv_with_dt.sort(key=lambda x: x[0])

        # Check spacing between consecutive PPVs
        for i in range(1, len(ppv_with_dt)):
            prev_dt, prev_item = ppv_with_dt[i - 1]
            curr_dt, curr_item = ppv_with_dt[i]

            gap = (curr_dt - prev_dt).total_seconds() / 3600

            if gap < 3.0:
                result.add_error(
                    "ppv_spacing",
                    f"PPV spacing too close: {gap:.1f} hours between items "
                    f"{prev_item.get('item_id')} and {curr_item.get('item_id')} (minimum 3 hours)",
                    [prev_item.get("item_id"), curr_item.get("item_id")]
                )
            elif gap < self.min_ppv_spacing_hours:
                result.add_warning(
                    "ppv_spacing",
                    f"PPV spacing below recommended: {gap:.1f} hours between items "
                    f"{prev_item.get('item_id')} and {curr_item.get('item_id')} "
                    f"(recommended {self.min_ppv_spacing_hours} hours)",
                    [prev_item.get("item_id"), curr_item.get("item_id")]
                )

    def _check_followup_timing(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: Follow-ups must be 15-45 minutes after parent PPV.
        """
        followups = [
            item for item in items
            if item.get("is_follow_up") and item.get("parent_item_id")
        ]

        if not followups:
            return

        # Build lookup for parent items
        items_by_id = {item.get("item_id"): item for item in items}

        for followup in followups:
            parent_id = followup.get("parent_item_id")
            parent = items_by_id.get(parent_id)

            if not parent:
                result.add_warning(
                    "followup_timing",
                    f"Follow-up {followup.get('item_id')} references missing parent {parent_id}",
                    [followup.get("item_id")]
                )
                continue

            followup_dt = self._parse_datetime(followup)
            parent_dt = self._parse_datetime(parent)

            if not followup_dt or not parent_dt:
                continue

            gap_minutes = (followup_dt - parent_dt).total_seconds() / 60

            if gap_minutes < 15:
                result.add_warning(
                    "followup_timing",
                    f"Follow-up {followup.get('item_id')} too soon after parent: "
                    f"{gap_minutes:.0f} minutes (minimum 15)",
                    [followup.get("item_id"), parent_id]
                )
            elif gap_minutes > 45:
                result.add_warning(
                    "followup_timing",
                    f"Follow-up {followup.get('item_id')} too late after parent: "
                    f"{gap_minutes:.0f} minutes (maximum 45)",
                    [followup.get("item_id"), parent_id]
                )

    def _check_duplicate_captions(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: No duplicate captions in the same week.
        """
        caption_ids: dict[int, list[int]] = {}

        for item in items:
            caption_id = item.get("caption_id")
            if caption_id is not None:
                if caption_id not in caption_ids:
                    caption_ids[caption_id] = []
                caption_ids[caption_id].append(item.get("item_id"))

        for caption_id, item_ids in caption_ids.items():
            if len(item_ids) > 1:
                result.add_error(
                    "duplicate_captions",
                    f"Caption {caption_id} used multiple times in items: {item_ids}",
                    item_ids
                )

    def _check_content_rotation(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: Warn if same content type appears more than 3 times consecutively.
        """
        # Sort by datetime
        items_with_dt = []
        for item in items:
            dt = self._parse_datetime(item)
            if dt:
                items_with_dt.append((dt, item))

        items_with_dt.sort(key=lambda x: x[0])

        consecutive_count = 1
        last_content_type = None

        for dt, item in items_with_dt:
            content_type = item.get("content_type_id") or item.get("content_type_name")

            if content_type == last_content_type:
                consecutive_count += 1
            else:
                consecutive_count = 1
                last_content_type = content_type

            if consecutive_count > self.max_consecutive_same_type:
                result.add_info(
                    "content_rotation",
                    f"Content type '{content_type}' appears {consecutive_count} times consecutively",
                    [item.get("item_id")]
                )

    def _check_freshness_scores(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: All captions must have freshness >= 30.
        """
        for item in items:
            freshness = item.get("freshness_score", 100.0)

            if freshness < 25:
                result.add_error(
                    "freshness_threshold",
                    f"Item {item.get('item_id')} has exhausted caption "
                    f"(freshness {freshness:.1f} < 25)",
                    [item.get("item_id")]
                )
            elif freshness < self.min_freshness:
                result.add_warning(
                    "freshness_threshold",
                    f"Item {item.get('item_id')} has stale caption "
                    f"(freshness {freshness:.1f} < {self.min_freshness})",
                    [item.get("item_id")]
                )

    def _check_volume_compliance(
        self,
        items: list[dict[str, Any]],
        daily_target: int,
        result: ValidationResult
    ) -> None:
        """
        Rule: Daily PPV count should match target (+/- 1).
        """
        ppv_by_date: dict[str, int] = {}

        for item in items:
            if item.get("item_type") == "ppv":
                date_str = item.get("scheduled_date", "")
                ppv_by_date[date_str] = ppv_by_date.get(date_str, 0) + 1

        for date_str, count in ppv_by_date.items():
            if count < daily_target - 1:
                result.add_warning(
                    "volume_compliance",
                    f"Day {date_str} has {count} PPVs, below target of {daily_target}",
                    []
                )
            elif count > daily_target + 1:
                result.add_warning(
                    "volume_compliance",
                    f"Day {date_str} has {count} PPVs, above target of {daily_target}",
                    []
                )

    def _check_vault_availability(
        self,
        items: list[dict[str, Any]],
        vault_types: list[int],
        result: ValidationResult
    ) -> None:
        """
        Rule: Content types should be available in vault.
        """
        vault_set = set(vault_types)

        for item in items:
            content_type_id = item.get("content_type_id")
            if content_type_id and content_type_id not in vault_set:
                result.add_warning(
                    "vault_availability",
                    f"Item {item.get('item_id')} uses content type {content_type_id} "
                    f"not in vault",
                    [item.get("item_id")]
                )

    def _check_wall_post_spacing(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: Wall posts must be at least 2 hours apart.

        Severity:
        - < 1 hour: ERROR
        - 1-2 hours: WARNING
        """
        wall_posts = [
            item for item in items
            if item.get("item_type") == "wall_post"
        ]

        if len(wall_posts) < 2:
            return

        # Sort by datetime
        posts_with_dt = []
        for item in wall_posts:
            dt = self._parse_datetime(item)
            if dt:
                posts_with_dt.append((dt, item))

        posts_with_dt.sort(key=lambda x: x[0])

        # Check spacing between consecutive wall posts
        for i in range(1, len(posts_with_dt)):
            prev_dt, prev_item = posts_with_dt[i - 1]
            curr_dt, curr_item = posts_with_dt[i]

            gap_hours = (curr_dt - prev_dt).total_seconds() / 3600

            if gap_hours < 1.0:
                result.add_error(
                    "wall_post_spacing",
                    f"Wall post spacing too close: {gap_hours:.1f} hours between items "
                    f"{prev_item.get('item_id')} and {curr_item.get('item_id')} (minimum 1 hour)",
                    [prev_item.get("item_id"), curr_item.get("item_id")]
                )
            elif gap_hours < 2.0:
                result.add_warning(
                    "wall_post_spacing",
                    f"Wall post spacing below recommended: {gap_hours:.1f} hours between items "
                    f"{prev_item.get('item_id')} and {curr_item.get('item_id')} (recommended 2 hours)",
                    [prev_item.get("item_id"), curr_item.get("item_id")]
                )

    def _check_preview_ppv_linkage(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: Free previews must be scheduled 1-3 hours BEFORE linked PPV.

        Severity:
        - Preview after PPV: ERROR
        - Preview > 4 hours before: WARNING
        - No linked PPV found: WARNING
        """
        previews = [
            item for item in items
            if item.get("item_type") == "free_preview"
        ]

        if not previews:
            return

        # Build lookup for all items by ID
        items_by_id = {item.get("item_id"): item for item in items}

        for preview in previews:
            linked_ppv_id = preview.get("linked_ppv_id")

            if not linked_ppv_id:
                result.add_info(
                    "preview_ppv_linkage",
                    f"Free preview {preview.get('item_id')} has no linked PPV",
                    [preview.get("item_id")]
                )
                continue

            linked_ppv = items_by_id.get(linked_ppv_id)
            if not linked_ppv:
                result.add_warning(
                    "preview_ppv_linkage",
                    f"Free preview {preview.get('item_id')} references missing PPV {linked_ppv_id}",
                    [preview.get("item_id")]
                )
                continue

            preview_dt = self._parse_datetime(preview)
            ppv_dt = self._parse_datetime(linked_ppv)

            if not preview_dt or not ppv_dt:
                continue

            gap_hours = (ppv_dt - preview_dt).total_seconds() / 3600

            if gap_hours < 0:
                result.add_error(
                    "preview_ppv_linkage",
                    f"Free preview {preview.get('item_id')} scheduled AFTER linked PPV {linked_ppv_id} "
                    f"(preview must come before PPV)",
                    [preview.get("item_id"), linked_ppv_id]
                )
            elif gap_hours < 1.0:
                result.add_warning(
                    "preview_ppv_linkage",
                    f"Free preview {preview.get('item_id')} too close to PPV: {gap_hours:.1f} hours "
                    f"(recommended 1-3 hours before)",
                    [preview.get("item_id"), linked_ppv_id]
                )
            elif gap_hours > 4.0:
                result.add_warning(
                    "preview_ppv_linkage",
                    f"Free preview {preview.get('item_id')} too far from PPV: {gap_hours:.1f} hours "
                    f"(recommended 1-3 hours before)",
                    [preview.get("item_id"), linked_ppv_id]
                )

    def _check_poll_spacing(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: Polls must be at least 2 days apart.

        Severity:
        - < 1 day: ERROR
        - 1-2 days: WARNING
        """
        polls = [
            item for item in items
            if item.get("item_type") == "poll"
        ]

        if len(polls) < 2:
            return

        # Sort by date (polls don't need time precision)
        polls_by_date = []
        for poll in polls:
            date_str = poll.get("scheduled_date", "")
            if date_str:
                try:
                    poll_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    polls_by_date.append((poll_date, poll))
                except ValueError:
                    pass

        polls_by_date.sort(key=lambda x: x[0])

        # Check spacing between consecutive polls
        for i in range(1, len(polls_by_date)):
            prev_date, prev_poll = polls_by_date[i - 1]
            curr_date, curr_poll = polls_by_date[i]

            gap_days = (curr_date - prev_date).days

            if gap_days < 1:
                result.add_error(
                    "poll_spacing",
                    f"Multiple polls on same day: items {prev_poll.get('item_id')} and "
                    f"{curr_poll.get('item_id')} (only one poll per day allowed)",
                    [prev_poll.get("item_id"), curr_poll.get("item_id")]
                )
            elif gap_days < 2:
                result.add_warning(
                    "poll_spacing",
                    f"Poll spacing below recommended: {gap_days} day(s) between items "
                    f"{prev_poll.get('item_id')} and {curr_poll.get('item_id')} (recommended 2 days)",
                    [prev_poll.get("item_id"), curr_poll.get("item_id")]
                )

    def _check_poll_duration(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: Poll duration must be 24, 48, or 72 hours.
        """
        valid_durations = {24, 48, 72}

        polls = [
            item for item in items
            if item.get("item_type") == "poll"
        ]

        for poll in polls:
            duration = poll.get("poll_duration_hours")

            if duration is None:
                # Default to 24 if not specified (acceptable)
                continue

            if duration not in valid_durations:
                result.add_error(
                    "poll_duration",
                    f"Poll {poll.get('item_id')} has invalid duration: {duration} hours "
                    f"(must be 24, 48, or 72 hours)",
                    [poll.get("item_id")]
                )

    def _check_game_wheel_validity(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """
        Rule: Game wheel configuration must be valid.

        Checks:
        - wheel_config_id must reference valid config
        - Only one game wheel item per week
        """
        wheel_items = [
            item for item in items
            if item.get("item_type") == "game_wheel"
        ]

        if not wheel_items:
            return

        # Check: only one wheel per week
        if len(wheel_items) > 1:
            result.add_warning(
                "game_wheel_validity",
                f"Multiple game wheel items in schedule: {[w.get('item_id') for w in wheel_items]} "
                f"(recommended: only one per week)",
                [w.get("item_id") for w in wheel_items]
            )

        # Check: each wheel has config reference
        for wheel in wheel_items:
            config_id = wheel.get("wheel_config_id")
            if config_id is None:
                result.add_warning(
                    "game_wheel_validity",
                    f"Game wheel {wheel.get('item_id')} has no configuration reference",
                    [wheel.get("item_id")]
                )

    def _check_daily_wall_post_limit(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult,
        max_per_day: int = 4
    ) -> None:
        """
        Rule: Maximum wall posts per day.
        """
        wall_posts_by_date: dict[str, list[int]] = {}

        for item in items:
            if item.get("item_type") == "wall_post":
                date_str = item.get("scheduled_date", "")
                if date_str not in wall_posts_by_date:
                    wall_posts_by_date[date_str] = []
                wall_posts_by_date[date_str].append(item.get("item_id"))

        for date_str, item_ids in wall_posts_by_date.items():
            if len(item_ids) > max_per_day:
                result.add_warning(
                    "wall_post_volume",
                    f"Day {date_str} has {len(item_ids)} wall posts, exceeds recommended {max_per_day}",
                    item_ids
                )

    def _check_weekly_poll_limit(
        self,
        items: list[dict[str, Any]],
        result: ValidationResult,
        max_per_week: int = 3
    ) -> None:
        """
        Rule: Maximum polls per week.
        """
        polls = [
            item for item in items
            if item.get("item_type") == "poll"
        ]

        if len(polls) > max_per_week:
            result.add_warning(
                "poll_volume",
                f"Schedule has {len(polls)} polls, exceeds recommended {max_per_week} per week",
                [p.get("item_id") for p in polls]
            )


def format_markdown(result: ValidationResult, items: list[dict[str, Any]]) -> str:
    """Format validation result as Markdown."""
    status = "PASSED" if result.is_valid else "FAILED"
    status_emoji = "" if result.is_valid else ""

    lines = [
        f"# Validation Report",
        "",
        f"**Status:** {status}",
        f"**Total Items:** {len(items)}",
        "",
        "## Summary",
        "",
        f"| Level | Count |",
        f"|-------|-------|",
        f"| Errors | {result.error_count} |",
        f"| Warnings | {result.warning_count} |",
        f"| Info | {result.info_count} |",
        ""
    ]

    if result.issues:
        # Group issues by severity
        errors = [i for i in result.issues if i.severity == "error"]
        warnings = [i for i in result.issues if i.severity == "warning"]
        infos = [i for i in result.issues if i.severity == "info"]

        if errors:
            lines.append("## Errors")
            lines.append("")
            for issue in errors:
                items_str = f" (items: {issue.item_ids})" if issue.item_ids else ""
                lines.append(f"- **{issue.rule_name}**: {issue.message}{items_str}")
            lines.append("")

        if warnings:
            lines.append("## Warnings")
            lines.append("")
            for issue in warnings:
                items_str = f" (items: {issue.item_ids})" if issue.item_ids else ""
                lines.append(f"- **{issue.rule_name}**: {issue.message}{items_str}")
            lines.append("")

        if infos:
            lines.append("## Info")
            lines.append("")
            for issue in infos:
                items_str = f" (items: {issue.item_ids})" if issue.item_ids else ""
                lines.append(f"- **{issue.rule_name}**: {issue.message}{items_str}")
            lines.append("")
    else:
        lines.append("No issues found.")
        lines.append("")

    return "\n".join(lines)


def format_json(result: ValidationResult) -> str:
    """Format validation result as JSON."""
    data = {
        "is_valid": result.is_valid,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "info_count": result.info_count,
        "issues": [
            {
                "rule_name": issue.rule_name,
                "severity": issue.severity,
                "message": issue.message,
                "item_ids": issue.item_ids
            }
            for issue in result.issues
        ]
    }
    return json.dumps(data, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate schedule against business rules.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Validation Rules:
    1. ppv_spacing        - PPVs must be 3+ hours apart (4 recommended)
    2. followup_timing    - Follow-ups must be 15-45 min after parent
    3. duplicate_captions - No duplicate captions in same week
    4. content_rotation   - Warn on 3+ consecutive same content type
    5. freshness_threshold - All captions must have freshness >= 30
    6. volume_compliance  - Daily PPV count should match target
    7. vault_availability - Content types should be in vault
    8. wall_post_spacing  - Wall posts must be 2+ hours apart (NEW)
    9. preview_ppv_linkage - Previews must be 1-3h before linked PPV (NEW)
    10. poll_spacing      - Polls must be 2+ days apart (NEW)
    11. poll_duration     - Poll duration must be 24/48/72h (NEW)
    12. game_wheel_validity - Only one game wheel per week (NEW)
    13. wall_post_volume  - Max 4 wall posts per day (NEW)
    14. poll_volume       - Max 3 polls per week (NEW)

Examples:
    python validate_schedule.py --input schedule.json
    python validate_schedule.py --input schedule.json --strict
    python validate_schedule.py --input schedule.json --volume-target 5
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input schedule JSON file"
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
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--volume-target",
        type=int,
        help="Expected daily PPV target"
    )
    parser.add_argument(
        "--min-ppv-spacing",
        type=float,
        default=4.0,
        help="Recommended minimum hours between PPVs (default: 4)"
    )
    parser.add_argument(
        "--min-freshness",
        type=float,
        default=30.0,
        help="Minimum freshness score (default: 30)"
    )

    args = parser.parse_args()

    # Load schedule
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(input_path.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract items from schedule
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "items" in data:
        items = data["items"]
    else:
        print("Error: Cannot find items in schedule", file=sys.stderr)
        sys.exit(1)

    # Create validator
    validator = ScheduleValidator(
        min_ppv_spacing_hours=args.min_ppv_spacing,
        min_freshness=args.min_freshness
    )

    # Validate
    result = validator.validate(
        items,
        volume_target=args.volume_target
    )

    # In strict mode, treat warnings as errors
    if args.strict and result.warning_count > 0:
        result.is_valid = False

    # Format output
    if args.format == "json":
        output = format_json(result)
    else:
        output = format_markdown(result, items)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Exit with error code if validation failed
    sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
