#!/usr/bin/env python3
"""
Content Type Schedulers - Schedule various content types.

This module provides scheduling logic for all 20+ OnlyFans content types:
- PPV and follow-ups (Tier 1 - Direct Revenue)
- Wall/Feed posts, VIP posts, link drops (Tier 2 - Feed/Wall)
- DM farm, like farm, engagement posts (Tier 3 - Engagement)
- Renew on, expired subscriber (Tier 4 - Retention)
- Polls, game wheels, live promos

These functions take content pools and configuration,
returning ScheduleItem instances positioned appropriately.

Slot Generation Functions:
    Each content type has a dedicated slot generator that determines
    WHEN content is sent based on business rules, page type, and volume level.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from generate_schedule import (
        CreatorProfile,
        GameWheelConfig,
        ScheduleConfig,
        ScheduleItem,
    )

# Import SlotConfig from centralized models
# Note: We extend the base SlotConfig with a more detailed to_dict method
from models import SlotConfig as BaseSlotConfig


# =============================================================================
# TIMING CONSTANTS
# =============================================================================

# Peak hours for content scheduling (best engagement windows)
PEAK_HOURS: set[int] = {10, 14, 18, 21, 23}

# Premium hours (highest engagement - use for high-value content)
PREMIUM_HOURS: set[int] = {18, 21}

# Engagement hours (optimal for DM farm, like farm)
ENGAGEMENT_HOURS: set[int] = {10, 14, 20}

# Retention hours (optimal for renew on, expired subscriber)
RETENTION_HOURS: set[int] = {11, 17}

# Link drop hours (good for traffic distribution)
LINK_DROP_HOURS: tuple[int, ...] = (12, 16, 20)

# Bump variant hours (flyers, descriptive, text-only)
BUMP_HOURS: tuple[int, ...] = (11, 15, 19, 22)

# Default timing variance range (minutes) for authenticity
TIMING_VARIANCE_RANGE: tuple[int, int] = (-10, 10)


# =============================================================================
# SLOT CONFIG - Extended from models.py
# =============================================================================
# SlotConfig is now centralized in models.py
# We extend it here with a more detailed to_dict method for backward compatibility


@dataclass
class SlotConfig(BaseSlotConfig):
    """
    Configuration for a scheduled content slot.

    Extended from models.SlotConfig with additional to_dict output fields
    for backward compatibility with content_type_schedulers consumers.
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert slot to dictionary format for compatibility."""
        return {
            "slot_id": self.slot_id,
            "date": self.day.isoformat() if isinstance(self.day, date) else self.day,
            "day_name": self.day.strftime("%A") if isinstance(self.day, date) else "",
            "time": self.time.strftime("%H:%M") if isinstance(self.time, time) else self.time,
            "hour": (
                self.time.hour if isinstance(self.time, time)
                else int(str(self.time).split(":")[0])
            ),
            "type": self.content_type,
            "channel": self.channel,
            "priority": self.slot_priority,
            "is_follow_up": self.is_follow_up,
            "parent_slot_id": self.parent_slot_id,
            "theme_guidance": self.theme_guidance,
            "payday_multiplier": self.payday_multiplier,
            "is_payday_optimal": self.is_payday_optimal,
            "is_mid_cycle": self.is_mid_cycle,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _add_timing_variance(
    base_time: time, variance_range: tuple[int, int] = TIMING_VARIANCE_RANGE
) -> time:
    """
    Add random timing variance to make schedules appear more organic.

    Args:
        base_time: The original scheduled time
        variance_range: Tuple of (min, max) minutes to add

    Returns:
        New time with variance applied
    """
    variance_minutes = random.randint(*variance_range)
    base_dt = datetime.combine(date.today(), base_time)
    adjusted_dt = base_dt + timedelta(minutes=variance_minutes)
    return adjusted_dt.time()


def _get_volume_multiplier(volume_level: str) -> tuple[int, int]:
    """
    Get volume multipliers for daily/weekly counts based on volume level.

    Args:
        volume_level: One of "Low", "Mid", "High", "Ultra"

    Returns:
        Tuple of (daily_base, weekly_multiplier)
    """
    multipliers = {
        "Low": (1, 1),
        "Mid": (2, 2),
        "High": (3, 3),
        "Ultra": (4, 4),
    }
    return multipliers.get(volume_level, (2, 2))


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
        notes=(
            f"Game Wheel | Trigger: {wheel_config.spin_trigger} "
            f">= ${wheel_config.min_trigger_amount:.2f}"
        ),
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
# NEW SLOT GENERATORS (Phase 3A - 20+ Content Types)
# =============================================================================


def generate_vip_post_slots(
    week_start: date | str,
    creator_id: str,
    page_type: str,
    start_slot_id: int = 700,
) -> list[SlotConfig]:
    """
    Generate VIP post slots for paid pages only.

    Strategy:
    - Paid pages only (return [] for free pages)
    - 1-2 per week at prime time (18:00, 21:00)
    - 24 hour minimum spacing between VIP posts

    Args:
        week_start: Week start date
        creator_id: Creator identifier
        page_type: Page type ("paid" or "free")
        start_slot_id: Starting ID for slots

    Returns:
        List of SlotConfig instances for VIP posts
    """
    # VIP posts are paid page only
    if page_type.lower() != "paid":
        return []

    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    slots: list[SlotConfig] = []
    slot_id = start_slot_id

    # Schedule 1-2 VIP posts per week
    # Place on Tuesday and Friday (days 1 and 4) at prime hours
    vip_days = [1, 4]  # Tuesday, Friday
    vip_hours = list(PREMIUM_HOURS)  # 18:00, 21:00

    for i, day_offset in enumerate(vip_days[:2]):
        vip_date = week_start + timedelta(days=day_offset)
        base_hour = vip_hours[i % len(vip_hours)]
        base_time = time(hour=base_hour, minute=0)
        varied_time = _add_timing_variance(base_time)

        slots.append(
            SlotConfig(
                day=vip_date,
                time=varied_time,
                content_type="vip_post",
                channel="feed",
                slot_priority=2,
                is_follow_up=False,
                theme_guidance=(
                    "Exclusive VIP tier content, emphasize $200+ value and premium benefits"
                ),
                creator_id=creator_id,
                slot_id=slot_id,
            )
        )
        slot_id += 1

    return slots


def generate_tip_incentive_slots(
    week_start: date | str,
    volume_level: str,
    creator_id: str | None = None,
    start_slot_id: int = 800,
) -> list[SlotConfig]:
    """
    Generate tip incentive (first_to_tip) slots.

    Strategy:
    - 2-3 per week based on volume level
    - Low/Mid: 2 slots, High/Ultra: 3 slots
    - Distribute evenly across week
    - Avoid first day (need engagement buildup)

    Args:
        week_start: Week start date
        volume_level: Volume level ("Low", "Mid", "High", "Ultra")
        creator_id: Optional creator identifier
        start_slot_id: Starting ID for slots

    Returns:
        List of SlotConfig instances for tip incentives
    """
    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    slots: list[SlotConfig] = []
    slot_id = start_slot_id

    # Determine count based on volume level
    if volume_level in ("High", "Ultra"):
        tip_count = 3
        tip_day_offsets = [1, 3, 5]  # Tue, Thu, Sat
    else:
        tip_count = 2
        tip_day_offsets = [2, 5]  # Wed, Sat

    tip_hours = [14, 18, 20]  # Afternoon/evening for engagement

    for i, day_offset in enumerate(tip_day_offsets[:tip_count]):
        tip_date = week_start + timedelta(days=day_offset)
        base_hour = tip_hours[i % len(tip_hours)]
        base_time = time(hour=base_hour, minute=0)
        varied_time = _add_timing_variance(base_time)

        slots.append(
            SlotConfig(
                day=tip_date,
                time=varied_time,
                content_type="first_to_tip",
                channel="feed",
                slot_priority=2,
                is_follow_up=False,
                theme_guidance="Tip campaign with specific goal, urgency-driven competition",
                creator_id=creator_id,
                slot_id=slot_id,
            )
        )
        slot_id += 1

    return slots


def generate_link_drop_slots(
    week_start: date | str,
    volume_level: str,
    creator_id: str | None = None,
    start_slot_id: int = 900,
) -> list[SlotConfig]:
    """
    Generate link drop slots.

    Strategy:
    - 1-2 per day based on volume level
    - Low/Mid: 1/day, High/Ultra: 2/day
    - 4 hour minimum spacing from PPV times
    - Peak hours: 12:00, 16:00, 20:00

    Args:
        week_start: Week start date
        volume_level: Volume level
        creator_id: Optional creator identifier
        start_slot_id: Starting ID for slots

    Returns:
        List of SlotConfig instances for link drops
    """
    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    slots: list[SlotConfig] = []
    slot_id = start_slot_id

    # Determine daily count based on volume
    daily_base, _ = _get_volume_multiplier(volume_level)
    links_per_day = min(daily_base, 2)  # Max 2 per day

    for day_offset in range(7):  # Full week
        current_date = week_start + timedelta(days=day_offset)

        for i in range(links_per_day):
            base_hour = LINK_DROP_HOURS[i % len(LINK_DROP_HOURS)]
            base_time = time(hour=base_hour, minute=0)
            varied_time = _add_timing_variance(base_time)

            slots.append(
                SlotConfig(
                    day=current_date,
                    time=varied_time,
                    content_type="link_drop",
                    channel="feed",
                    slot_priority=2,
                    is_follow_up=False,
                    theme_guidance="Casual link share, drive traffic to other platforms",
                    creator_id=creator_id,
                    slot_id=slot_id,
                )
            )
            slot_id += 1

    return slots


def generate_engagement_slots(
    week_start: date | str,
    volume_level: str,
    creator_id: str | None = None,
    start_slot_id: int = 1000,
) -> list[SlotConfig]:
    """
    Generate engagement slots (DM farm and like farm).

    Strategy:
    - DM Farm: Morning (10:00) and evening (20:00) split
    - Like Farm: Afternoon (14:00)
    - Max 2 per day, 10 per week
    - Scales with volume level

    Args:
        week_start: Week start date
        volume_level: Volume level
        creator_id: Optional creator identifier
        start_slot_id: Starting ID for slots

    Returns:
        List of SlotConfig instances for engagement content
    """
    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    slots: list[SlotConfig] = []
    slot_id = start_slot_id

    # Volume-based scaling
    daily_base, _ = _get_volume_multiplier(volume_level)
    engagement_per_day = min(daily_base, 2)  # Max 2 per day

    # Alternate between DM farm and like farm throughout week
    engagement_schedule = [
        ("dm_farm", 10, "DM me for surprise, encourage 1-on-1 engagement"),
        ("like_farm", 14, "Like this post for a reward, engagement boost campaign"),
        ("dm_farm", 20, "Personal check-in, build relationship"),
    ]

    weekly_count = 0
    max_weekly = 10

    for day_offset in range(7):
        current_date = week_start + timedelta(days=day_offset)

        for i in range(engagement_per_day):
            if weekly_count >= max_weekly:
                break

            content_type, base_hour, guidance = engagement_schedule[
                (day_offset + i) % len(engagement_schedule)
            ]
            base_time = time(hour=base_hour, minute=0)
            varied_time = _add_timing_variance(base_time)

            # Determine channel based on content type
            channel = "direct" if content_type == "dm_farm" else "feed"

            slots.append(
                SlotConfig(
                    day=current_date,
                    time=varied_time,
                    content_type=content_type,
                    channel=channel,
                    slot_priority=3,
                    is_follow_up=False,
                    theme_guidance=guidance,
                    creator_id=creator_id,
                    slot_id=slot_id,
                )
            )
            slot_id += 1
            weekly_count += 1

    return slots


def generate_retention_slots(
    week_start: date | str,
    page_type: str,
    creator_id: str | None = None,
    start_slot_id: int = 1100,
) -> list[SlotConfig]:
    """
    Generate retention slots (renew_on_mm and expired_subscriber).

    Strategy:
    - Paid pages only
    - Renew On: Days 5-7 of week (before billing cycle)
    - Expired Subscriber: Day 1 and Day 4 (win-back timing)
    - Uses retention-optimized hours (11:00, 17:00)

    Args:
        week_start: Week start date
        page_type: Page type ("paid" or "free")
        creator_id: Optional creator identifier
        start_slot_id: Starting ID for slots

    Returns:
        List of SlotConfig instances for retention content
    """
    # Retention content is paid page only
    if page_type.lower() != "paid":
        return []

    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    slots: list[SlotConfig] = []
    slot_id = start_slot_id
    retention_hours = list(RETENTION_HOURS)

    # Renew On Mass Message: Days 5-7 (Fri, Sat, Sun)
    for i, day_offset in enumerate([4, 5, 6]):
        if i >= 2:  # Max 2 per week
            break
        renew_date = week_start + timedelta(days=day_offset)
        base_hour = retention_hours[i % len(retention_hours)]
        base_time = time(hour=base_hour, minute=0)
        varied_time = _add_timing_variance(base_time)

        slots.append(
            SlotConfig(
                day=renew_date,
                time=varied_time,
                content_type="renew_on_mm",
                channel="mass_message",
                slot_priority=4,
                is_follow_up=False,
                theme_guidance="Subscription expiring soon, exclusive content preview to retain",
                creator_id=creator_id,
                slot_id=slot_id,
            )
        )
        slot_id += 1

    # Expired Subscriber: Day 1 and Day 4 (Mon, Thu)
    for i, day_offset in enumerate([0, 3]):
        expired_date = week_start + timedelta(days=day_offset)
        base_hour = retention_hours[i % len(retention_hours)]
        base_time = time(hour=base_hour, minute=0)
        varied_time = _add_timing_variance(base_time)

        slots.append(
            SlotConfig(
                day=expired_date,
                time=varied_time,
                content_type="expired_subscriber",
                channel="direct",
                slot_priority=4,
                is_follow_up=False,
                theme_guidance=(
                    "Miss you message, highlight what they are missing, special offer to return"
                ),
                creator_id=creator_id,
                slot_id=slot_id,
            )
        )
        slot_id += 1

    return slots


def generate_bump_variant_slots(
    week_start: date | str,
    volume_level: str,
    creator_id: str | None = None,
    start_slot_id: int = 1200,
) -> list[SlotConfig]:
    """
    Generate bump variant slots (flyer/GIF, descriptive, text-only).

    Strategy:
    - Flyer/GIF bumps: 2 per day, 4 hour spacing
    - Descriptive bumps: 1-2 per day based on volume
    - Text-only bumps: Fill remaining engagement slots
    - Total scales with volume level

    Args:
        week_start: Week start date
        volume_level: Volume level
        creator_id: Optional creator identifier
        start_slot_id: Starting ID for slots

    Returns:
        List of SlotConfig instances for bump variants
    """
    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    slots: list[SlotConfig] = []
    slot_id = start_slot_id

    daily_base, _ = _get_volume_multiplier(volume_level)

    # Bump type rotation with hours
    bump_types = [
        ("flyer_gif_bump", 11, "Eye-catching visual content, quick engagement grab"),
        ("descriptive_bump", 15, "Detailed content preview, build anticipation"),
        ("flyer_gif_bump", 19, "Evening visual bump, catch after-work crowd"),
        ("text_only_bump", 22, "Personal message tone, casual check-in or tease"),
    ]

    for day_offset in range(7):
        current_date = week_start + timedelta(days=day_offset)
        bumps_today = min(daily_base, 2)  # Max 2 bumps per day

        for i in range(bumps_today):
            content_type, base_hour, guidance = bump_types[
                (day_offset + i) % len(bump_types)
            ]
            base_time = time(hour=base_hour, minute=0)
            varied_time = _add_timing_variance(base_time)

            # Text-only goes to mass_message, others to feed
            channel = "mass_message" if content_type == "text_only_bump" else "feed"

            slots.append(
                SlotConfig(
                    day=current_date,
                    time=varied_time,
                    content_type=content_type,
                    channel=channel,
                    slot_priority=2 if content_type != "text_only_bump" else 3,
                    is_follow_up=False,
                    theme_guidance=guidance,
                    creator_id=creator_id,
                    slot_id=slot_id,
                )
            )
            slot_id += 1

    return slots


def generate_game_post_slots(
    week_start: date | str,
    creator_id: str | None = None,
    start_slot_id: int = 1300,
) -> list[SlotConfig]:
    """
    Generate game post slot (spin the wheel, contests).

    Strategy:
    - 1 per week maximum
    - Saturday evening (prime engagement window)
    - 7 PM for maximum participation

    Args:
        week_start: Week start date
        creator_id: Optional creator identifier
        start_slot_id: Starting ID for slots

    Returns:
        List with single SlotConfig for game post
    """
    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    # Saturday is day 5 (0=Monday)
    game_date = week_start + timedelta(days=5)
    base_time = time(hour=19, minute=0)  # 7 PM
    varied_time = _add_timing_variance(base_time)

    return [
        SlotConfig(
            day=game_date,
            time=varied_time,
            content_type="game_post",
            channel="feed",
            slot_priority=2,
            is_follow_up=False,
            theme_guidance="Spin the wheel, chance to win prizes, gamification and fun",
            creator_id=creator_id,
            slot_id=start_slot_id,
        )
    ]


def generate_live_promo_slots(
    week_start: date | str,
    live_schedule: list[datetime] | None = None,
    creator_id: str | None = None,
    start_slot_id: int = 1400,
) -> list[SlotConfig]:
    """
    Generate live stream promotion slots.

    Strategy:
    - 2-4 hours before each scheduled live session
    - If no schedule provided, skip (return empty list)
    - Creates anticipation and maximizes live attendance

    Args:
        week_start: Week start date
        live_schedule: List of datetime for upcoming lives (optional)
        creator_id: Optional creator identifier
        start_slot_id: Starting ID for slots

    Returns:
        List of SlotConfig instances for live promos
    """
    if not live_schedule:
        return []

    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    week_end = week_start + timedelta(days=6)

    slots: list[SlotConfig] = []
    slot_id = start_slot_id

    for live_dt in live_schedule:
        # Only process lives within this week
        if isinstance(live_dt, datetime):
            live_date = live_dt.date()
        else:
            continue

        if not (week_start <= live_date <= week_end):
            continue

        # Schedule promo 2-4 hours before live
        promo_lead_hours = random.choice([2, 3, 4])
        promo_dt = live_dt - timedelta(hours=promo_lead_hours)
        promo_time = _add_timing_variance(promo_dt.time())

        slots.append(
            SlotConfig(
                day=promo_dt.date(),
                time=promo_time,
                content_type="live_promo",
                channel="feed",
                slot_priority=2,
                is_follow_up=False,
                theme_guidance=(
                    f"Live stream in {promo_lead_hours} hours! "
                    "Time and date announcement, exclusive preview"
                ),
                creator_id=creator_id,
                slot_id=slot_id,
            )
        )
        slot_id += 1

    return slots


# =============================================================================
# UNIFIED SLOT BUILDER
# =============================================================================


def resolve_slot_conflicts(slots: list[SlotConfig]) -> list[SlotConfig]:
    """
    Resolve conflicts when multiple slots are at the same time.

    Strategy:
    - Group slots by (day, time)
    - For each group, keep slot with lowest priority_tier (highest priority)
    - Move lower priority slots to next available time (15-30 min offset)

    Args:
        slots: List of SlotConfig instances

    Returns:
        List of SlotConfig with conflicts resolved
    """
    if not slots:
        return []

    # Group by (day, time hour)
    time_groups: dict[tuple[date, int], list[SlotConfig]] = {}
    for slot in slots:
        key = (slot.day, slot.time.hour)
        if key not in time_groups:
            time_groups[key] = []
        time_groups[key].append(slot)

    resolved: list[SlotConfig] = []

    for (day, hour), group in time_groups.items():
        if len(group) == 1:
            resolved.append(group[0])
            continue

        # Sort by priority (lower number = higher priority)
        group.sort(key=lambda s: s.slot_priority)

        # Keep highest priority slot as-is
        resolved.append(group[0])

        # Offset lower priority slots by 15-30 minutes each
        for i, slot in enumerate(group[1:], 1):
            offset_minutes = 15 * i
            new_dt = datetime.combine(day, slot.time) + timedelta(minutes=offset_minutes)

            # Create new slot with adjusted time
            resolved.append(
                SlotConfig(
                    day=slot.day,
                    time=new_dt.time(),
                    content_type=slot.content_type,
                    channel=slot.channel,
                    slot_priority=slot.slot_priority,
                    is_follow_up=slot.is_follow_up,
                    parent_slot_id=slot.parent_slot_id,
                    theme_guidance=slot.theme_guidance,
                    creator_id=slot.creator_id,
                    payday_multiplier=slot.payday_multiplier,
                    is_payday_optimal=slot.is_payday_optimal,
                    is_mid_cycle=slot.is_mid_cycle,
                    slot_id=slot.slot_id,
                )
            )

    # Sort by datetime
    resolved.sort(key=lambda s: (s.day, s.time))
    return resolved


def build_all_content_slots(
    week_start: date | str,
    creator_profile: dict[str, Any],
    enabled_types: set[str] | None = None,
    live_schedule: list[datetime] | None = None,
    start_slot_id: int = 700,
) -> list[SlotConfig]:
    """
    Build weekly slots for all enabled content types.

    This is the unified slot builder that calls individual slot generators
    based on page type and enabled content types.

    Args:
        week_start: Week start date
        creator_profile: Creator profile dict with keys:
            - creator_id: Creator identifier
            - page_type: "paid" or "free"
            - volume_level: "Low", "Mid", "High", "Ultra"
        enabled_types: Set of content type IDs to generate (None = all valid)
        live_schedule: Optional list of datetime for live streams
        start_slot_id: Starting ID for slots

    Returns:
        List of SlotConfig instances sorted by datetime with conflicts resolved
    """
    if isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    creator_id = creator_profile.get("creator_id", "")
    page_type = creator_profile.get("page_type", "free")
    volume_level = creator_profile.get("volume_level", "Mid")

    all_slots: list[SlotConfig] = []
    slot_id = start_slot_id

    # Import registry for validation
    try:
        from content_type_registry import REGISTRY
        registry_available = True
    except ImportError:
        registry_available = False
        REGISTRY = None

    # Define slot generators and their content types
    generators: list[tuple[str, callable, dict]] = [
        # (content_type, generator_func, kwargs)
        ("vip_post", generate_vip_post_slots, {
            "week_start": week_start,
            "creator_id": creator_id,
            "page_type": page_type,
            "start_slot_id": slot_id,
        }),
        ("first_to_tip", generate_tip_incentive_slots, {
            "week_start": week_start,
            "volume_level": volume_level,
            "creator_id": creator_id,
            "start_slot_id": slot_id + 100,
        }),
        ("link_drop", generate_link_drop_slots, {
            "week_start": week_start,
            "volume_level": volume_level,
            "creator_id": creator_id,
            "start_slot_id": slot_id + 200,
        }),
        ("dm_farm", generate_engagement_slots, {
            "week_start": week_start,
            "volume_level": volume_level,
            "creator_id": creator_id,
            "start_slot_id": slot_id + 300,
        }),
        ("renew_on_mm", generate_retention_slots, {
            "week_start": week_start,
            "page_type": page_type,
            "creator_id": creator_id,
            "start_slot_id": slot_id + 400,
        }),
        ("flyer_gif_bump", generate_bump_variant_slots, {
            "week_start": week_start,
            "volume_level": volume_level,
            "creator_id": creator_id,
            "start_slot_id": slot_id + 500,
        }),
        ("game_post", generate_game_post_slots, {
            "week_start": week_start,
            "creator_id": creator_id,
            "start_slot_id": slot_id + 600,
        }),
        ("live_promo", generate_live_promo_slots, {
            "week_start": week_start,
            "live_schedule": live_schedule,
            "creator_id": creator_id,
            "start_slot_id": slot_id + 700,
        }),
    ]

    for content_type, generator_func, kwargs in generators:
        # Skip if content type is not enabled
        if enabled_types is not None and content_type not in enabled_types:
            continue

        # Validate content type for page type if registry available
        if registry_available and REGISTRY is not None:
            try:
                if not REGISTRY.validate_for_page(content_type, page_type):
                    continue
            except KeyError:
                # Content type not in registry, skip validation
                pass

        # Generate slots for this content type
        try:
            slots = generator_func(**kwargs)
            all_slots.extend(slots)
        except Exception:
            # Log but don't fail on individual generator errors
            continue

    # Sort by datetime and priority
    all_slots.sort(key=lambda s: (s.day, s.time, s.slot_priority))

    # Resolve any conflicts
    resolved = resolve_slot_conflicts(all_slots)

    return resolved


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Existing exports
    "select_wall_posts_for_slots",
    "select_previews_for_ppvs",
    "select_polls_for_week",
    "create_game_wheel_schedule_item",
    "generate_wall_post_slots",
    "generate_poll_slots",
    # New slot config
    "SlotConfig",
    # Timing constants
    "PEAK_HOURS",
    "PREMIUM_HOURS",
    "ENGAGEMENT_HOURS",
    "RETENTION_HOURS",
    "LINK_DROP_HOURS",
    "BUMP_HOURS",
    "TIMING_VARIANCE_RANGE",
    # New slot generators
    "generate_vip_post_slots",
    "generate_tip_incentive_slots",
    "generate_link_drop_slots",
    "generate_engagement_slots",
    "generate_retention_slots",
    "generate_bump_variant_slots",
    "generate_game_post_slots",
    "generate_live_promo_slots",
    # Unified builders
    "build_all_content_slots",
    "resolve_slot_conflicts",
]
