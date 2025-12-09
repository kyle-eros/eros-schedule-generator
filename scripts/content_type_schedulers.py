#!/usr/bin/env python3
"""
Content Type Schedulers - Schedule various content types.

This module provides scheduling logic for:
- Wall/Feed posts
- Free previews
- Polls
- Game wheel promotions

These functions take content pools and configuration,
returning ScheduleItem instances positioned appropriately.
"""

import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from generate_schedule import (
        CreatorProfile,
        GameWheelConfig,
        ScheduleConfig,
        ScheduleItem,
    )


def _get_schedule_item_class():
    """Lazy import to avoid circular dependency."""
    from generate_schedule import ScheduleItem

    return ScheduleItem


# =============================================================================
# WALL POST SCHEDULING
# =============================================================================


def select_wall_posts_for_slots(
    wall_captions: list,  # list[Caption]
    slots: list[dict],
    config: "ScheduleConfig",
    profile: "CreatorProfile",
    start_item_id: int = 1000,
) -> list:  # list[ScheduleItem]
    """
    Assign wall post captions to designated slots.

    Selection criteria:
    - Prefer high-hook captions (shorter, punchier)
    - Rotate content types (no same type consecutively)
    - Match persona tone
    - Consider time of day optimization

    Args:
        wall_captions: Pool of wall-eligible captions
        slots: List of slot dictionaries with date, time, type
        config: Schedule configuration
        profile: Creator profile for persona matching
        start_item_id: Starting ID for generated items

    Returns:
        List of ScheduleItem instances for wall posts
    """
    ScheduleItem = _get_schedule_item_class()

    if not wall_captions or not slots:
        return []

    items = []
    used_caption_ids: set[int] = set()
    previous_content_type: str | None = None
    item_id = start_item_id

    for slot in slots:
        if slot.get("type") != "wall_post":
            continue

        # Find best caption for this slot
        selected = None
        for caption in wall_captions:
            if caption.caption_id in used_caption_ids:
                continue
            # Avoid same content type consecutively
            if caption.content_type_name == previous_content_type and len(wall_captions) > 1:
                continue
            selected = caption
            break

        # Fall back to any unused caption
        if not selected:
            for caption in wall_captions:
                if caption.caption_id not in used_caption_ids:
                    selected = caption
                    break

        if selected:
            used_caption_ids.add(selected.caption_id)
            previous_content_type = selected.content_type_name

            items.append(
                ScheduleItem(
                    item_id=item_id,
                    creator_id=config.creator_id,
                    scheduled_date=slot["date"],
                    scheduled_time=slot["time"],
                    item_type="wall_post",
                    channel="feed",
                    caption_id=selected.caption_id,
                    caption_text=selected.caption_text,
                    content_type_id=selected.content_type_id,
                    content_type_name=selected.content_type_name,
                    freshness_score=selected.freshness_score,
                    performance_score=selected.performance_score,
                    priority=4,
                    notes=f"Wall post | Boost: {selected.persona_boost:.2f}x",
                )
            )
            item_id += 1

    return items


# =============================================================================
# FREE PREVIEW SCHEDULING
# =============================================================================


def select_previews_for_ppvs(
    previews: list,  # list[FreePreview]
    ppv_items: list,  # list[ScheduleItem]
    config: "ScheduleConfig",
    start_item_id: int = 2000,
) -> list:  # list[ScheduleItem]
    """
    Assign free previews before high-value PPVs.

    Strategy:
    - Only preview for PPVs with price >= $15
    - Match preview content_type to PPV content_type
    - Schedule preview 1-3 hours before PPV

    Args:
        previews: Pool of free preview content
        ppv_items: List of PPV ScheduleItems
        config: Schedule configuration
        start_item_id: Starting ID for generated items

    Returns:
        List of ScheduleItem instances for free previews
    """
    ScheduleItem = _get_schedule_item_class()

    if not previews or not ppv_items:
        return []

    items = []
    used_preview_ids: set[int] = set()
    previews_per_day: dict[str, int] = {}
    item_id = start_item_id

    lead_time_hours = (
        config.preview_lead_time_hours if hasattr(config, "preview_lead_time_hours") else 2
    )

    for ppv in ppv_items:
        # Only preview for high-value PPVs
        if (ppv.suggested_price or 0) < 15:
            continue

        # Limit one preview per day
        if previews_per_day.get(ppv.scheduled_date, 0) >= 1:
            continue

        # Find matching preview
        selected = None
        for preview in previews:
            if preview.preview_id in used_preview_ids:
                continue
            # Prefer matching content type
            if preview.linked_ppv_type and ppv.content_type_name:
                if preview.linked_ppv_type.lower() == ppv.content_type_name.lower():
                    selected = preview
                    break
            elif not selected:
                selected = preview

        if selected:
            used_preview_ids.add(selected.preview_id)
            previews_per_day[ppv.scheduled_date] = previews_per_day.get(ppv.scheduled_date, 0) + 1

            # Calculate preview time (lead_time hours before PPV)
            ppv_dt = datetime.strptime(
                f"{ppv.scheduled_date} {ppv.scheduled_time}", "%Y-%m-%d %H:%M"
            )
            preview_dt = ppv_dt - timedelta(hours=lead_time_hours)

            items.append(
                ScheduleItem(
                    item_id=item_id,
                    creator_id=ppv.creator_id,
                    scheduled_date=preview_dt.strftime("%Y-%m-%d"),
                    scheduled_time=preview_dt.strftime("%H:%M"),
                    item_type="free_preview",
                    channel="feed",
                    caption_text=selected.preview_text,
                    content_type_id=selected.content_type_id,
                    freshness_score=selected.freshness_score,
                    performance_score=selected.performance_score,
                    preview_type=selected.preview_type,
                    linked_ppv_id=ppv.item_id,
                    priority=3,
                    notes=f"Preview for PPV #{ppv.item_id} | Type: {selected.preview_type}",
                )
            )
            item_id += 1

    return items


# =============================================================================
# POLL SCHEDULING
# =============================================================================


def select_polls_for_week(
    polls: list,  # list[Poll]
    config: "ScheduleConfig",
    profile: "CreatorProfile",
    week_start: str,
    start_item_id: int = 3000,
) -> list:  # list[ScheduleItem]
    """
    Select and schedule polls for the week.

    Strategy:
    - Max 3 polls per week
    - Space polls 2+ days apart
    - Prefer high-engagement windows (evenings, weekends)
    - Match poll tone to creator persona

    Args:
        polls: Pool of available polls
        config: Schedule configuration
        profile: Creator profile for persona matching
        week_start: Week start date (YYYY-MM-DD)
        start_item_id: Starting ID for generated items

    Returns:
        List of ScheduleItem instances for polls
    """
    ScheduleItem = _get_schedule_item_class()

    if not polls:
        return []

    polls_per_week = getattr(config, "polls_per_week", 3)
    if polls_per_week <= 0:
        return []

    items = []
    item_id = start_item_id

    # Determine poll days (spread across week)
    start_date = datetime.strptime(week_start, "%Y-%m-%d")
    poll_days = []

    if polls_per_week == 1:
        poll_days = [start_date + timedelta(days=3)]  # Wednesday
    elif polls_per_week == 2:
        poll_days = [start_date + timedelta(days=1), start_date + timedelta(days=5)]  # Tue, Sat
    else:
        poll_days = [
            start_date + timedelta(days=1),  # Tuesday
            start_date + timedelta(days=3),  # Thursday
            start_date + timedelta(days=5),  # Saturday
        ]

    # High-engagement hours for polls
    poll_hours = [18, 19, 20]  # Evening hours

    # Sort polls by persona_boost (prefer matching tone)
    sorted_polls = sorted(polls, key=lambda p: getattr(p, "persona_boost", 1.0), reverse=True)

    for i, poll_date in enumerate(poll_days[:polls_per_week]):
        if i >= len(sorted_polls):
            break

        poll = sorted_polls[i]
        poll_hour = random.choice(poll_hours)
        poll_minute = random.choice([0, 15, 30])

        items.append(
            ScheduleItem(
                item_id=item_id,
                creator_id=config.creator_id,
                scheduled_date=poll_date.strftime("%Y-%m-%d"),
                scheduled_time=f"{poll_hour:02d}:{poll_minute:02d}",
                item_type="poll",
                channel="poll",
                caption_text=poll.question_text,
                poll_options=poll.options,
                poll_duration_hours=poll.duration_hours,
                priority=4,
                notes=f"Poll | Category: {poll.poll_category} | Duration: {poll.duration_hours}h",
            )
        )
        item_id += 1

    return items


# =============================================================================
# GAME WHEEL SCHEDULING
# =============================================================================


def create_game_wheel_schedule_item(
    wheel_config: "GameWheelConfig", config: "ScheduleConfig", week_start: str, item_id: int = 4000
) -> "ScheduleItem | None":
    """
    Generate game wheel schedule entry.

    Game wheel is a single promotional item for the week,
    typically posted mid-week to maximize engagement.

    Args:
        wheel_config: Game wheel configuration
        config: Schedule configuration
        week_start: Week start date (YYYY-MM-DD)
        item_id: ID for the schedule item

    Returns:
        ScheduleItem for game wheel or None if not configured
    """
    ScheduleItem = _get_schedule_item_class()

    if not wheel_config:
        return None

    # Schedule wheel promotion for Wednesday at 7 PM
    start_date = datetime.strptime(week_start, "%Y-%m-%d")
    wheel_date = start_date + timedelta(days=2)  # Wednesday

    promo_text = wheel_config.display_text or f"Spin the {wheel_config.wheel_name}!"

    return ScheduleItem(
        item_id=item_id,
        creator_id=config.creator_id,
        scheduled_date=wheel_date.strftime("%Y-%m-%d"),
        scheduled_time="19:00",
        item_type="game_wheel",
        channel="gamification",
        caption_text=promo_text,
        wheel_config_id=wheel_config.wheel_id,
        priority=4,
        notes=f"Game Wheel | Trigger: {wheel_config.spin_trigger} >= ${wheel_config.min_trigger_amount:.2f}",
    )


# =============================================================================
# SLOT GENERATION HELPERS
# =============================================================================


def generate_wall_post_slots(
    config: "ScheduleConfig", week_start: str, week_end: str, start_slot_id: int = 500
) -> list[dict[str, Any]]:
    """
    Generate wall post slots.

    Strategy:
    - 2-3 wall posts per day (configurable)
    - Stagger between PPV times
    - Prefer mid-day and early evening
    - Avoid within 1 hour of PPV

    Args:
        config: Schedule configuration
        week_start: Week start date (YYYY-MM-DD)
        week_end: Week end date (YYYY-MM-DD)
        start_slot_id: Starting ID for slots

    Returns:
        List of slot dictionaries
    """
    if not getattr(config, "enable_wall_posts", False):
        return []

    wall_hours = list(getattr(config, "wall_post_hours", (12, 16, 20)))
    posts_per_day = getattr(config, "wall_posts_per_day", 2)

    slots = []
    slot_id = start_slot_id

    current_date = datetime.strptime(week_start, "%Y-%m-%d")
    end_date = datetime.strptime(week_end, "%Y-%m-%d")

    while current_date <= end_date:
        day_name = current_date.strftime("%A")

        for i in range(min(posts_per_day, len(wall_hours))):
            hour = wall_hours[i % len(wall_hours)]
            minute = random.choice([0, 15, 30, 45])

            slots.append(
                {
                    "slot_id": slot_id,
                    "date": current_date.strftime("%Y-%m-%d"),
                    "day_name": day_name,
                    "time": f"{hour:02d}:{minute:02d}",
                    "hour": hour,
                    "type": "wall_post",
                    "priority": 4,
                }
            )
            slot_id += 1

        current_date += timedelta(days=1)

    return slots


def generate_poll_slots(
    config: "ScheduleConfig", week_start: str, start_slot_id: int = 600
) -> list[dict[str, Any]]:
    """
    Generate poll slots for the week.

    Strategy:
    - 2-3 polls per week
    - High engagement windows only
    - Space 2+ days apart

    Args:
        config: Schedule configuration
        week_start: Week start date (YYYY-MM-DD)
        start_slot_id: Starting ID for slots

    Returns:
        List of slot dictionaries
    """
    if not getattr(config, "enable_polls", False):
        return []

    polls_per_week = getattr(config, "polls_per_week", 3)
    if polls_per_week <= 0:
        return []

    slots = []
    slot_id = start_slot_id
    start_date = datetime.strptime(week_start, "%Y-%m-%d")

    # Poll days spread across week
    if polls_per_week == 1:
        poll_day_offsets = [3]  # Wednesday
    elif polls_per_week == 2:
        poll_day_offsets = [1, 5]  # Tue, Sat
    else:
        poll_day_offsets = [1, 3, 5]  # Tue, Thu, Sat

    for offset in poll_day_offsets[:polls_per_week]:
        poll_date = start_date + timedelta(days=offset)
        day_name = poll_date.strftime("%A")
        hour = random.choice([18, 19, 20])

        slots.append(
            {
                "slot_id": slot_id,
                "date": poll_date.strftime("%Y-%m-%d"),
                "day_name": day_name,
                "time": f"{hour:02d}:00",
                "hour": hour,
                "type": "poll",
                "priority": 4,
            }
        )
        slot_id += 1

    return slots


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "select_wall_posts_for_slots",
    "select_previews_for_ppvs",
    "select_polls_for_week",
    "create_game_wheel_schedule_item",
    "generate_wall_post_slots",
    "generate_poll_slots",
]
