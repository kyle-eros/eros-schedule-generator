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
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hook_detection import HookType, detect_hook_type

# Path resolution for database
SCRIPT_DIR = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """
    Represents a validation issue with optional auto-correction capability.

    Attributes:
        rule_name: The name of the validation rule that was violated.
        severity: The severity level - "error", "warning", or "info".
        message: Human-readable description of the issue.
        item_ids: Tuple of schedule item IDs affected by this issue.
        auto_correctable: Whether this issue can be automatically corrected.
        correction_action: The type of correction to apply:
            - "move_slot": Move item to a new time slot
            - "swap_caption": Replace caption with another
            - "adjust_timing": Adjust follow-up timing
        correction_value: The value to apply for correction (JSON or string).
            - For move_slot: JSON {"new_date": "YYYY-MM-DD", "new_time": "HH:MM"}
            - For swap_caption: new caption_id as string
            - For adjust_timing: new timing in minutes as string
    """

    rule_name: str
    severity: str  # error, warning, info
    message: str
    item_ids: tuple[int, ...] = ()
    # Auto-correction fields
    auto_correctable: bool = False
    correction_action: str = ""  # "move_slot", "swap_caption", "adjust_timing"
    correction_value: str = ""  # New value to apply (JSON or string)


@dataclass(slots=True)
class ValidationResult:
    """Result of validation."""

    is_valid: bool = True
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(
        self,
        rule: str,
        message: str,
        item_ids: list[int] | None = None,
        auto_correctable: bool = False,
        correction_action: str = "",
        correction_value: str = "",
    ):
        """Add an error issue with optional auto-correction data."""
        self.issues.append(
            ValidationIssue(
                rule_name=rule,
                severity="error",
                message=message,
                item_ids=tuple(item_ids) if item_ids else (),
                auto_correctable=auto_correctable,
                correction_action=correction_action,
                correction_value=correction_value,
            )
        )
        self.error_count += 1
        self.is_valid = False

    def add_warning(
        self,
        rule: str,
        message: str,
        item_ids: list[int] | None = None,
        auto_correctable: bool = False,
        correction_action: str = "",
        correction_value: str = "",
    ):
        """Add a warning issue with optional auto-correction data."""
        self.issues.append(
            ValidationIssue(
                rule_name=rule,
                severity="warning",
                message=message,
                item_ids=tuple(item_ids) if item_ids else (),
                auto_correctable=auto_correctable,
                correction_action=correction_action,
                correction_value=correction_value,
            )
        )
        self.warning_count += 1

    def add_info(
        self,
        rule: str,
        message: str,
        item_ids: list[int] | None = None,
        auto_correctable: bool = False,
        correction_action: str = "",
        correction_value: str = "",
    ):
        """Add an info issue with optional auto-correction data."""
        self.issues.append(
            ValidationIssue(
                rule_name=rule,
                severity="info",
                message=message,
                item_ids=tuple(item_ids) if item_ids else (),
                auto_correctable=auto_correctable,
                correction_action=correction_action,
                correction_value=correction_value,
            )
        )
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
        max_consecutive_same_type: int = 3,
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
        vault_types: list[int] | None = None,
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

        # Hook rotation for anti-detection (Phase 3)
        self._check_hook_rotation(items, result)

        return result

    def _parse_datetime(self, item: dict[str, Any]) -> datetime | None:
        """Parse scheduled datetime from item."""
        try:
            date_str = item.get("scheduled_date", "")
            time_str = item.get("scheduled_time", "00:00")
            return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return None

    def _check_ppv_spacing(self, items: list[dict[str, Any]], result: ValidationResult) -> None:
        """
        Rule: PPV messages must be at least 3 hours apart (4 hours recommended).

        Severity:
        - < 3 hours: ERROR (blocks schedule) - AUTO-CORRECTABLE
        - 3-4 hours: WARNING (flagged for review)
        """
        ppv_items = [item for item in items if item.get("item_type") == "ppv"]

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
                # Calculate correction: shift second item forward
                needed_shift = 3.0 - gap + 0.25  # Add 15 min buffer
                new_dt = curr_dt + timedelta(hours=needed_shift)
                correction_value = json.dumps(
                    {"new_date": new_dt.strftime("%Y-%m-%d"), "new_time": new_dt.strftime("%H:%M")}
                )

                result.add_error(
                    "ppv_spacing",
                    f"PPV spacing too close: {gap:.1f} hours between items "
                    f"{prev_item.get('item_id')} and {curr_item.get('item_id')} (minimum 3 hours)",
                    [prev_item.get("item_id"), curr_item.get("item_id")],
                    auto_correctable=True,
                    correction_action="move_slot",
                    correction_value=correction_value,
                )
            elif gap < self.min_ppv_spacing_hours:
                result.add_warning(
                    "ppv_spacing",
                    f"PPV spacing below recommended: {gap:.1f} hours between items "
                    f"{prev_item.get('item_id')} and {curr_item.get('item_id')} "
                    f"(recommended {self.min_ppv_spacing_hours} hours)",
                    [prev_item.get("item_id"), curr_item.get("item_id")],
                )

    def _check_followup_timing(self, items: list[dict[str, Any]], result: ValidationResult) -> None:
        """
        Rule: Follow-ups must be 15-45 minutes after parent PPV.

        AUTO-CORRECTABLE: Timing outside range adjusted to 25 minutes.
        """
        followups = [
            item for item in items if item.get("is_follow_up") and item.get("parent_item_id")
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
                    [followup.get("item_id")],
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
                    [followup.get("item_id"), parent_id],
                    auto_correctable=True,
                    correction_action="adjust_timing",
                    correction_value="25",  # Adjust to 25 minutes (middle of range)
                )
            elif gap_minutes > 45:
                result.add_warning(
                    "followup_timing",
                    f"Follow-up {followup.get('item_id')} too late after parent: "
                    f"{gap_minutes:.0f} minutes (maximum 45)",
                    [followup.get("item_id"), parent_id],
                    auto_correctable=True,
                    correction_action="adjust_timing",
                    correction_value="25",  # Adjust to 25 minutes (middle of range)
                )

    def _check_duplicate_captions(
        self, items: list[dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Rule: No duplicate captions in the same week.

        AUTO-CORRECTABLE: Duplicate items flagged for caption swap (requires caption pool).
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
                # Mark all but the first occurrence for swap
                # The first usage is valid, subsequent ones need replacement
                result.add_error(
                    "duplicate_captions",
                    f"Caption {caption_id} used multiple times in items: {item_ids}",
                    item_ids[1:],  # Only flag duplicates, not the original
                    auto_correctable=True,
                    correction_action="swap_caption",
                    correction_value="",  # Caption pool required from caller
                )

    def _check_content_rotation(
        self, items: list[dict[str, Any]], result: ValidationResult
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

        for _dt, item in items_with_dt:
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
                    [item.get("item_id")],
                )

    def _check_freshness_scores(
        self, items: list[dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Rule: All captions must have freshness >= 30.

        AUTO-CORRECTABLE: Items with freshness < 30 flagged for caption swap.
        """
        for item in items:
            freshness = item.get("freshness_score", 100.0)

            if freshness < 25:
                # Exhausted caption - needs swap
                result.add_error(
                    "freshness_threshold",
                    f"Item {item.get('item_id')} has exhausted caption "
                    f"(freshness {freshness:.1f} < 25)",
                    [item.get("item_id")],
                    auto_correctable=True,
                    correction_action="swap_caption",
                    correction_value="",  # Caption pool required from caller
                )
            elif freshness < self.min_freshness:
                # Stale caption - flagged but auto-correctable
                result.add_warning(
                    "freshness_threshold",
                    f"Item {item.get('item_id')} has stale caption "
                    f"(freshness {freshness:.1f} < {self.min_freshness})",
                    [item.get("item_id")],
                    auto_correctable=True,
                    correction_action="swap_caption",
                    correction_value="",  # Caption pool required from caller
                )

    def _check_volume_compliance(
        self, items: list[dict[str, Any]], daily_target: int, result: ValidationResult
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
                    [],
                )
            elif count > daily_target + 1:
                result.add_warning(
                    "volume_compliance",
                    f"Day {date_str} has {count} PPVs, above target of {daily_target}",
                    [],
                )

    def _check_vault_availability(
        self, items: list[dict[str, Any]], vault_types: list[int], result: ValidationResult
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
                    f"Item {item.get('item_id')} uses content type {content_type_id} not in vault",
                    [item.get("item_id")],
                )

    def _check_wall_post_spacing(
        self, items: list[dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Rule: Wall posts must be at least 2 hours apart.

        Severity:
        - < 1 hour: ERROR
        - 1-2 hours: WARNING
        """
        wall_posts = [item for item in items if item.get("item_type") == "wall_post"]

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
                    [prev_item.get("item_id"), curr_item.get("item_id")],
                )
            elif gap_hours < 2.0:
                result.add_warning(
                    "wall_post_spacing",
                    f"Wall post spacing below recommended: {gap_hours:.1f} hours between items "
                    f"{prev_item.get('item_id')} and {curr_item.get('item_id')} (recommended 2 hours)",
                    [prev_item.get("item_id"), curr_item.get("item_id")],
                )

    def _check_preview_ppv_linkage(
        self, items: list[dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Rule: Free previews must be scheduled 1-3 hours BEFORE linked PPV.

        Severity:
        - Preview after PPV: ERROR
        - Preview > 4 hours before: WARNING
        - No linked PPV found: WARNING
        """
        previews = [item for item in items if item.get("item_type") == "free_preview"]

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
                    [preview.get("item_id")],
                )
                continue

            linked_ppv = items_by_id.get(linked_ppv_id)
            if not linked_ppv:
                result.add_warning(
                    "preview_ppv_linkage",
                    f"Free preview {preview.get('item_id')} references missing PPV {linked_ppv_id}",
                    [preview.get("item_id")],
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
                    [preview.get("item_id"), linked_ppv_id],
                )
            elif gap_hours < 1.0:
                result.add_warning(
                    "preview_ppv_linkage",
                    f"Free preview {preview.get('item_id')} too close to PPV: {gap_hours:.1f} hours "
                    f"(recommended 1-3 hours before)",
                    [preview.get("item_id"), linked_ppv_id],
                )
            elif gap_hours > 4.0:
                result.add_warning(
                    "preview_ppv_linkage",
                    f"Free preview {preview.get('item_id')} too far from PPV: {gap_hours:.1f} hours "
                    f"(recommended 1-3 hours before)",
                    [preview.get("item_id"), linked_ppv_id],
                )

    def _check_poll_spacing(self, items: list[dict[str, Any]], result: ValidationResult) -> None:
        """
        Rule: Polls must be at least 2 days apart.

        Severity:
        - < 1 day: ERROR
        - 1-2 days: WARNING
        """
        polls = [item for item in items if item.get("item_type") == "poll"]

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
                    [prev_poll.get("item_id"), curr_poll.get("item_id")],
                )
            elif gap_days < 2:
                result.add_warning(
                    "poll_spacing",
                    f"Poll spacing below recommended: {gap_days} day(s) between items "
                    f"{prev_poll.get('item_id')} and {curr_poll.get('item_id')} (recommended 2 days)",
                    [prev_poll.get("item_id"), curr_poll.get("item_id")],
                )

    def _check_poll_duration(self, items: list[dict[str, Any]], result: ValidationResult) -> None:
        """
        Rule: Poll duration must be 24, 48, or 72 hours.
        """
        valid_durations = {24, 48, 72}

        polls = [item for item in items if item.get("item_type") == "poll"]

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
                    [poll.get("item_id")],
                )

    def _check_game_wheel_validity(
        self, items: list[dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Rule: Game wheel configuration must be valid.

        Checks:
        - wheel_config_id must reference valid config
        - Only one game wheel item per week
        """
        wheel_items = [item for item in items if item.get("item_type") == "game_wheel"]

        if not wheel_items:
            return

        # Check: only one wheel per week
        if len(wheel_items) > 1:
            result.add_warning(
                "game_wheel_validity",
                f"Multiple game wheel items in schedule: {[w.get('item_id') for w in wheel_items]} "
                f"(recommended: only one per week)",
                [w.get("item_id") for w in wheel_items],
            )

        # Check: each wheel has config reference
        for wheel in wheel_items:
            config_id = wheel.get("wheel_config_id")
            if config_id is None:
                result.add_warning(
                    "game_wheel_validity",
                    f"Game wheel {wheel.get('item_id')} has no configuration reference",
                    [wheel.get("item_id")],
                )

    def _check_daily_wall_post_limit(
        self, items: list[dict[str, Any]], result: ValidationResult, max_per_day: int = 4
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
                    item_ids,
                )

    def _check_weekly_poll_limit(
        self, items: list[dict[str, Any]], result: ValidationResult, max_per_week: int = 3
    ) -> None:
        """
        Rule: Maximum polls per week.
        """
        polls = [item for item in items if item.get("item_type") == "poll"]

        if len(polls) > max_per_week:
            result.add_warning(
                "poll_volume",
                f"Schedule has {len(polls)} polls, exceeds recommended {max_per_week} per week",
                [p.get("item_id") for p in polls],
            )

    def _check_hook_rotation(self, items: list[dict[str, Any]], result: ValidationResult) -> None:
        """
        Rule: Hook types should be rotated to prevent detectable patterns.

        This validation checks for:
        1. Consecutive identical hook types (WARNING if 2x same hook consecutively)
        2. Low hook diversity (INFO if fewer than 4 hook types used in full week)

        Hook detection is performed on caption_text using pattern matching.
        Only PPV items with caption_text are analyzed.

        Args:
            items: List of schedule item dicts
            result: ValidationResult to add issues to
        """
        # Filter to PPV items with caption text
        ppv_items = [
            item for item in items if item.get("item_type") == "ppv" and item.get("caption_text")
        ]

        if len(ppv_items) < 2:
            return

        # Sort by datetime
        items_with_dt: list[tuple[datetime, dict[str, Any]]] = []
        for item in ppv_items:
            dt = self._parse_datetime(item)
            if dt:
                items_with_dt.append((dt, item))

        items_with_dt.sort(key=lambda x: x[0])

        # Track hook types used
        hook_types_used: set[str] = set()
        last_hook_type: HookType | None = None
        consecutive_same_hook_items: list[int] = []

        for dt, item in items_with_dt:
            caption_text = item.get("caption_text", "")
            hook_type, confidence = detect_hook_type(caption_text)

            hook_types_used.add(hook_type.value)

            # Check for consecutive identical hook types
            if last_hook_type is not None and hook_type == last_hook_type:
                # This is a consecutive duplicate
                if not consecutive_same_hook_items:
                    # Add the previous item ID (first in the consecutive pair)
                    # Find the previous item
                    prev_idx = items_with_dt.index((dt, item)) - 1
                    if prev_idx >= 0:
                        prev_item = items_with_dt[prev_idx][1]
                        consecutive_same_hook_items.append(prev_item.get("item_id"))

                consecutive_same_hook_items.append(item.get("item_id"))

                result.add_warning(
                    "hook_rotation",
                    f"Consecutive '{hook_type.value}' hooks detected: items "
                    f"{consecutive_same_hook_items[-2]} and {consecutive_same_hook_items[-1]} "
                    f"(rotate hook types for authenticity)",
                    [consecutive_same_hook_items[-2], consecutive_same_hook_items[-1]],
                )
            else:
                consecutive_same_hook_items = []

            last_hook_type = hook_type

        # Check hook diversity (target: 4+ different hook types for a full week)
        min_hook_diversity = 4
        if len(hook_types_used) < min_hook_diversity and len(ppv_items) >= 7:
            result.add_info(
                "hook_diversity",
                f"Low hook diversity: only {len(hook_types_used)} hook types used "
                f"({', '.join(sorted(hook_types_used))}). Target: {min_hook_diversity}+ "
                f"for natural variation",
                [],
            )

    # =========================================================================
    # AUTO-CORRECTION METHODS (Phase 2 - Self-Healing Validation)
    # =========================================================================

    def _generate_correction(
        self,
        rule_name: str,
        item: dict[str, Any],
        related_items: list[dict[str, Any]] | None = None,
    ) -> ValidationIssue | None:
        """
        Generate a ValidationIssue with correction instructions for fixable issues.

        Args:
            rule_name: The validation rule that was violated.
            item: The primary schedule item involved.
            related_items: Optional list of related items (e.g., for spacing issues).

        Returns:
            ValidationIssue with correction data if auto-correctable, None otherwise.

        Auto-correctable rules:
            - ppv_spacing: Move second item to a valid time slot
            - duplicate_captions: Flag for caption swap (needs external pool)
            - freshness_threshold: Flag for caption swap (needs external pool)
            - followup_timing: Adjust to 25 minutes after parent

        Not auto-correctable:
            - content_rotation: Requires human judgment on content strategy
            - volume_compliance: Requires human judgment on volume targets
        """
        item_id = item.get("item_id")

        if rule_name == "ppv_spacing":
            # Calculate how much to shift the second item
            if related_items and len(related_items) >= 2:
                prev_item = related_items[0]
                curr_item = related_items[1]

                prev_dt = self._parse_datetime(prev_item)
                curr_dt = self._parse_datetime(curr_item)

                if prev_dt and curr_dt:
                    gap_hours = (curr_dt - prev_dt).total_seconds() / 3600
                    needed_shift = 3.0 - gap_hours + 0.25  # Add 15 min buffer

                    # Calculate new datetime
                    new_dt = curr_dt + timedelta(hours=needed_shift)
                    correction_value = json.dumps(
                        {
                            "new_date": new_dt.strftime("%Y-%m-%d"),
                            "new_time": new_dt.strftime("%H:%M"),
                        }
                    )

                    return ValidationIssue(
                        rule_name=rule_name,
                        severity="error",
                        message=f"PPV spacing too close: {gap_hours:.1f}h (need shift of {needed_shift:.1f}h)",
                        item_ids=(curr_item.get("item_id"),),
                        auto_correctable=True,
                        correction_action="move_slot",
                        correction_value=correction_value,
                    )

        elif rule_name == "duplicate_captions":
            # Flag for swap - actual caption selection requires external pool
            return ValidationIssue(
                rule_name=rule_name,
                severity="error",
                message=f"Duplicate caption detected for item {item_id}",
                item_ids=(item_id,) if item_id else (),
                auto_correctable=True,
                correction_action="swap_caption",
                correction_value="",  # Will be filled by apply_corrections with available pool
            )

        elif rule_name == "freshness_threshold":
            freshness = item.get("freshness_score", 0)
            return ValidationIssue(
                rule_name=rule_name,
                severity="error",
                message=f"Item {item_id} has low freshness: {freshness:.1f}",
                item_ids=(item_id,) if item_id else (),
                auto_correctable=True,
                correction_action="swap_caption",
                correction_value="",  # Will be filled by apply_corrections with available pool
            )

        elif rule_name == "followup_timing":
            # Adjust to 25 minutes (middle of 15-45 range)
            return ValidationIssue(
                rule_name=rule_name,
                severity="warning",
                message="Follow-up timing outside 15-45 minute range",
                item_ids=(item_id,) if item_id else (),
                auto_correctable=True,
                correction_action="adjust_timing",
                correction_value="25",  # Default to 25 minutes
            )

        # Not auto-correctable
        return None

    def _apply_corrections(
        self, items: list[dict[str, Any]], corrections: list[ValidationIssue]
    ) -> list[dict[str, Any]]:
        """
        Apply corrections to schedule items.

        Args:
            items: List of schedule item dicts (will be modified in place).
            corrections: List of ValidationIssue objects with correction data.

        Returns:
            Modified items list.

        Correction actions:
            - move_slot: Move item to new time (correction_value = JSON with new_date, new_time)
            - swap_caption: Placeholder - marks item for caption replacement
            - adjust_timing: Adjust follow-up timing relative to parent
        """
        # Build lookup tables
        items_by_id: dict[int, dict] = {item.get("item_id"): item for item in items}

        for correction in corrections:
            if not correction.auto_correctable:
                continue

            action = correction.correction_action
            value = correction.correction_value
            item_ids = correction.item_ids

            if not item_ids:
                continue

            if action == "move_slot":
                # Move item to new time slot
                item_id = item_ids[0]
                item = items_by_id.get(item_id)

                if item and value:
                    try:
                        new_slot = json.loads(value)
                        item["scheduled_date"] = new_slot.get(
                            "new_date", item.get("scheduled_date")
                        )
                        item["scheduled_time"] = new_slot.get(
                            "new_time", item.get("scheduled_time")
                        )
                    except json.JSONDecodeError:
                        pass  # Invalid correction value, skip

            elif action == "swap_caption":
                # Mark for swap - actual swap requires caption pool from caller
                # This is a placeholder that validates the item needs a new caption
                item_id = item_ids[0]
                item = items_by_id.get(item_id)

                if item:
                    # Mark the item as needing a caption swap
                    # The caller (validate_with_corrections) should provide the pool
                    item["_needs_caption_swap"] = True

            elif action == "adjust_timing":
                # Adjust follow-up timing to specified minutes after parent
                item_id = item_ids[0]
                item = items_by_id.get(item_id)

                if item and item.get("parent_item_id"):
                    parent = items_by_id.get(item.get("parent_item_id"))
                    if parent:
                        try:
                            target_minutes = int(value) if value else 25
                            parent_dt = self._parse_datetime(parent)
                            if parent_dt:
                                new_dt = parent_dt + timedelta(minutes=target_minutes)
                                item["scheduled_date"] = new_dt.strftime("%Y-%m-%d")
                                item["scheduled_time"] = new_dt.strftime("%H:%M")
                        except (ValueError, TypeError):
                            pass  # Invalid timing value, skip

        return items

    def validate_with_corrections(
        self,
        items: list[dict[str, Any]],
        volume_target: int | None = None,
        vault_types: list[int] | None = None,
        max_passes: int = 2,
        available_captions: list[dict[str, Any]] | None = None,
    ) -> ValidationResult:
        """
        Validate schedule with automatic correction loop.

        This is the self-healing validation entry point. It runs validation,
        collects auto-correctable issues, applies corrections, and re-validates
        until either the schedule is valid or max_passes is reached.

        Args:
            items: List of schedule item dicts.
            volume_target: Optional daily PPV target.
            vault_types: Optional list of available content_type_ids.
            max_passes: Maximum number of validation/correction passes (default: 2).
            available_captions: Optional pool of fresh captions for swap corrections.

        Returns:
            ValidationResult with final validation state and any remaining issues.

        Auto-correctable issues (limited set):
            1. PPV spacing violation (<3hr) -> Move to next valid slot
            2. Duplicate caption -> Swap with unused caption of same type
            3. Freshness below 30 -> Swap with fresher caption
            4. Follow-up timing outside 15-45min -> Adjust to 25 minutes

        NOT auto-correctable (require human judgment):
            - Content rotation patterns
            - Pricing decisions
            - Volume targets
        """
        corrections_applied: list[str] = []

        for pass_num in range(1, max_passes + 1):
            # Run standard validation
            result = self.validate(items, volume_target, vault_types)

            # Check if valid or no errors
            if result.is_valid or result.error_count == 0:
                # Add correction summary to result if any were applied
                if corrections_applied:
                    result.add_info(
                        "auto_corrections",
                        f"Applied {len(corrections_applied)} auto-corrections: {', '.join(corrections_applied)}",
                    )
                return result

            # Collect auto-correctable issues
            auto_fixable = [issue for issue in result.issues if issue.auto_correctable]

            if not auto_fixable:
                # No auto-fixable issues, return current result
                return result

            # Generate corrections for PPV spacing issues (need special handling)
            enhanced_corrections: list[ValidationIssue] = []
            items_by_id = {item.get("item_id"): item for item in items}

            for issue in auto_fixable:
                if issue.rule_name == "ppv_spacing" and len(issue.item_ids) >= 2:
                    # Get the two items involved
                    related = [
                        items_by_id.get(iid) for iid in issue.item_ids if items_by_id.get(iid)
                    ]
                    if len(related) >= 2:
                        correction = self._generate_correction(
                            "ppv_spacing",
                            related[1],  # Fix the second item
                            related_items=related,
                        )
                        if correction:
                            enhanced_corrections.append(correction)
                            corrections_applied.append(f"move_slot(item_{issue.item_ids[1]})")
                else:
                    # Use the issue as-is for other correction types
                    enhanced_corrections.append(issue)
                    if issue.correction_action:
                        corrections_applied.append(
                            f"{issue.correction_action}(item_{issue.item_ids[0] if issue.item_ids else 'unknown'})"
                        )

            # Handle caption swaps if pool is available
            if available_captions:
                used_ids = {item.get("caption_id") for item in items if item.get("caption_id")}
                fresh_pool = [
                    c
                    for c in available_captions
                    if c.get("caption_id") not in used_ids
                    and c.get("freshness_score", 0) >= self.min_freshness
                ]

                for correction in enhanced_corrections:
                    if correction.correction_action == "swap_caption" and correction.item_ids:
                        item_id = correction.item_ids[0]
                        item = items_by_id.get(item_id)
                        if item and fresh_pool:
                            # Find a caption of the same content type
                            item_content_type = item.get("content_type_id")
                            matching = [
                                c
                                for c in fresh_pool
                                if c.get("content_type_id") == item_content_type
                            ]
                            if matching:
                                new_caption = matching[0]
                                fresh_pool.remove(new_caption)  # Remove from pool
                                item["caption_id"] = new_caption.get("caption_id")
                                item["caption_text"] = new_caption.get("caption_text", "")
                                item["freshness_score"] = new_caption.get("freshness_score", 100)
                                corrections_applied.append(
                                    f"swap_caption(item_{item_id}->caption_{new_caption.get('caption_id')})"
                                )

            # Apply the corrections
            items = self._apply_corrections(items, enhanced_corrections)

            # If this isn't the last pass, continue the loop
            if pass_num < max_passes:
                continue

        # Final validation after all passes
        final_result = self.validate(items, volume_target, vault_types)

        # Add correction summary
        if corrections_applied:
            final_result.add_info(
                "auto_corrections",
                f"Applied {len(corrections_applied)} auto-corrections: {', '.join(corrections_applied)}",
            )

        return final_result


def format_markdown(result: ValidationResult, items: list[dict[str, Any]]) -> str:
    """Format validation result as Markdown."""
    status = "PASSED" if result.is_valid else "FAILED"

    lines = [
        "# Validation Report",
        "",
        f"**Status:** {status}",
        f"**Total Items:** {len(items)}",
        "",
        "## Summary",
        "",
        "| Level | Count |",
        "|-------|-------|",
        f"| Errors | {result.error_count} |",
        f"| Warnings | {result.warning_count} |",
        f"| Info | {result.info_count} |",
        "",
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
                "item_ids": issue.item_ids,
                "auto_correctable": issue.auto_correctable,
                "correction_action": issue.correction_action,
                "correction_value": issue.correction_value,
            }
            for issue in result.issues
        ],
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
    8. wall_post_spacing  - Wall posts must be 2+ hours apart
    9. preview_ppv_linkage - Previews must be 1-3h before linked PPV
    10. poll_spacing      - Polls must be 2+ days apart
    11. poll_duration     - Poll duration must be 24/48/72h
    12. game_wheel_validity - Only one game wheel per week
    13. wall_post_volume  - Max 4 wall posts per day
    14. poll_volume       - Max 3 polls per week
    15. hook_rotation     - Warn on consecutive same hook types (Phase 3)
    16. hook_diversity    - Info if < 4 hook types used in week (Phase 3)

Examples:
    python validate_schedule.py --input schedule.json
    python validate_schedule.py --input schedule.json --strict
    python validate_schedule.py --input schedule.json --volume-target 5
        """,
    )

    parser.add_argument("--input", "-i", required=True, help="Input schedule JSON file")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--volume-target", type=int, help="Expected daily PPV target")
    parser.add_argument(
        "--min-ppv-spacing",
        type=float,
        default=4.0,
        help="Recommended minimum hours between PPVs (default: 4)",
    )
    parser.add_argument(
        "--min-freshness", type=float, default=30.0, help="Minimum freshness score (default: 30)"
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
        min_ppv_spacing_hours=args.min_ppv_spacing, min_freshness=args.min_freshness
    )

    # Validate
    result = validator.validate(items, volume_target=args.volume_target)

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
