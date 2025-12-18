"""
Schedule Optimizer - Timing and revenue optimization engine.

Optimizes schedule timing through:
- Prime time identification
- Send type timing preferences
- Saturation-based volume adjustment
- Revenue opportunity maximization
- Conflict prevention
"""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
import random

from python.logging_config import get_logger, log_fallback
from python.models.creator_timing_profile import CreatorTimingProfile

# Module logger
logger = get_logger(__name__)

# =============================================================================
# Timing Score Constants
# =============================================================================

# Base score for time slot calculations
SLOT_SCORE_BASE = 50.0
SLOT_SCORE_MIN = 0.0
SLOT_SCORE_MAX = 100.0

# Preferred hours bonus scoring
PREFERRED_HOURS_MAX_BONUS = 30
PREFERRED_HOURS_POSITION_DECAY = 5

# Preferred days bonus
PREFERRED_DAYS_BONUS = 20

# Avoid hours penalty
AVOID_HOURS_PENALTY = 40

# Prime time bonuses
PRIME_TIME_BONUS = 15
PRIME_DAY_BONUS = 10
PPV_PRIME_TIME_BONUS = 10
PPV_PRIME_HOURS = [19, 21, 22]

# Historical performance normalization
HISTORICAL_PERFORMANCE_MAX_BONUS = 20
HISTORICAL_PERFORMANCE_SCALE = 100

# Saturation thresholds
SATURATION_LOW_THRESHOLD = 30
SATURATION_MODERATE_THRESHOLD = 50
SATURATION_HIGH_THRESHOLD = 70

# Saturation adjustment multipliers
SATURATION_LOW_MULTIPLIER = 1.2
SATURATION_MODERATE_MULTIPLIER = 1.0
SATURATION_HIGH_MULTIPLIER = 0.9
SATURATION_VERY_HIGH_MULTIPLIER = 0.7

# Jitter configuration for organic time variation
JITTER_CONFIG = {
    "min_jitter_minutes": -7,
    "max_jitter_minutes": 8,
    "avoid_round_numbers": True,  # Avoid :00, :15, :30, :45
    "per_creator_seed": True      # Consistent jitter per creator
}


def apply_time_jitter(base_time: time, creator_id: str, day_offset: int) -> time:
    """Apply organic minute jitter to make times feel natural.

    Creates deterministic but varied timing that:
    - Avoids round numbers (:00, :15, :30, :45)
    - Is consistent per creator+day combination
    - Adds -7 to +8 minute variation

    Args:
        base_time: Base time slot
        creator_id: Creator identifier for seeding
        day_offset: Day offset for variation

    Returns:
        Time with jitter applied
    """
    import hashlib

    # Create deterministic but varied seed per creator+day+time
    seed_str = f"{creator_id}:{day_offset}:{base_time.hour}:{base_time.minute}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    random.seed(seed)

    jitter = random.randint(
        JITTER_CONFIG["min_jitter_minutes"],
        JITTER_CONFIG["max_jitter_minutes"]
    )

    new_minute = base_time.minute + jitter

    # Avoid landing on round numbers if configured
    if JITTER_CONFIG["avoid_round_numbers"] and new_minute in [0, 15, 30, 45]:
        new_minute += random.choice([-2, -1, 1, 2, 3])

    # Handle overflow/underflow
    new_hour = base_time.hour
    if new_minute < 0:
        new_minute += 60
        new_hour = max(0, new_hour - 1)
    elif new_minute >= 60:
        new_minute -= 60
        new_hour = min(23, new_hour + 1)

    new_minute = max(0, min(59, new_minute))

    return time(new_hour, new_minute)


@dataclass(slots=True)
class ScheduleItem:
    """Schedule item with timing and metadata.

    Attributes:
        send_type_key: Send type identifier
        scheduled_date: Date for send (YYYY-MM-DD)
        scheduled_time: Time for send (HH:MM)
        category: 'revenue', 'engagement', or 'retention'
        priority: Priority level (1=highest, 3=lowest)
        caption_id: Associated caption ID
        caption_text: Caption text content
        requires_media: Whether media is required
        media_type: Type of media ('picture', 'video', 'gif', 'flyer', 'none')
        content_type_id: Content type identifier
        suggested_price: Suggested PPV price
        target_key: Audience target key
        channel_key: Distribution channel key
    """

    send_type_key: str
    scheduled_date: str
    scheduled_time: str
    category: str
    priority: int
    caption_id: int | None = None
    caption_text: str = ""
    requires_media: bool = False
    media_type: str = "none"
    content_type_id: int | None = None
    suggested_price: float | None = None
    target_key: str = "all_fans"
    channel_key: str = "mass_message"

    @property
    def datetime_obj(self) -> datetime:
        """Get combined datetime object."""
        date_obj = datetime.strptime(self.scheduled_date, "%Y-%m-%d")
        time_obj = datetime.strptime(self.scheduled_time, "%H:%M").time()
        return datetime.combine(date_obj.date(), time_obj)


class ScheduleOptimizer:
    """Optimizes schedule timing and revenue potential."""

    # Prime hours for maximum engagement (24-hour format)
    # Note: Use get_prime_hours_for_day() for daily-varied prime hours
    PRIME_HOURS = [10, 14, 19, 21]

    # Rotating prime hours per day - prevents same "optimal" times every day
    # Each day has slightly different peak engagement windows
    DAILY_PRIME_HOURS: dict[int, list[int]] = {
        0: [9, 13, 19, 21],    # Monday: Earlier start
        1: [10, 15, 20, 22],   # Tuesday: Later peaks
        2: [11, 14, 19, 21],   # Wednesday: Late morning focus
        3: [10, 14, 18, 21],   # Thursday: Earlier evening
        4: [9, 14, 20, 22],    # Friday: Extended evening
        5: [11, 15, 20, 22],   # Saturday: Later overall
        6: [10, 13, 19, 20]    # Sunday: Earlier wrap-up
    }

    # Prime days of week (0=Monday, 6=Sunday)
    PRIME_DAYS = [4, 5, 6]  # Friday, Saturday, Sunday

    # Hours to avoid (late night/early morning)
    AVOID_HOURS = list(range(3, 8))  # 3 AM - 7 AM

    # Minimum spacing between sends (minutes)
    MIN_SPACING_MINUTES = 45

    # Daily time rotation offsets - shifts morning/evening focus per day
    # This prevents same timing patterns every day
    DAILY_TIME_OFFSETS: dict[int, dict[str, int]] = {
        0: {"morning_shift": -1, "evening_shift": 0},   # Monday: Earlier morning
        1: {"morning_shift": 0, "evening_shift": 1},    # Tuesday: Later evening
        2: {"morning_shift": 1, "evening_shift": 0},    # Wednesday: Later morning
        3: {"morning_shift": 0, "evening_shift": -1},   # Thursday: Earlier evening
        4: {"morning_shift": -1, "evening_shift": 1},   # Friday: Mixed
        5: {"morning_shift": 1, "evening_shift": 1},    # Saturday: Later overall
        6: {"morning_shift": 0, "evening_shift": -1}    # Sunday: Earlier evening
    }

    # Timing preferences by send type - 21 database send types
    TIMING_PREFERENCES: dict[str, dict[str, Any]] = {
        # Revenue send types (7)
        "ppv_video": {
            "preferred_hours": [19, 21],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 8],
            "min_spacing": 90,
            "boost": 1.3,
        },
        "vip_program": {
            "preferred_hours": [14, 19],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7],
            "min_spacing": 120,
            "boost": 1.2,
        },
        "game_post": {
            "preferred_hours": [19, 21],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 8],
            "min_spacing": 180,
            "boost": 1.2,
        },
        "bundle": {
            "preferred_hours": [14, 19],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7],
            "min_spacing": 120,
            "boost": 1.2,
        },
        "flash_bundle": {
            "preferred_hours": [19, 21],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 8],
            "min_spacing": 240,
            "boost": 1.4,
        },
        "snapchat_bundle": {
            "preferred_hours": [14, 19],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7],
            "min_spacing": 120,
            "boost": 1.2,
        },
        "first_to_tip": {
            "preferred_hours": [19, 21],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 8],
            "min_spacing": 180,
            "boost": 1.3,
        },

        # Engagement send types (9)
        "link_drop": {
            "preferred_hours": [10, 14, 19],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7],
            "min_spacing": 180,
            "boost": 1.0,
            "offset_from_parent": 180,  # 3 hours after parent
        },
        "wall_link_drop": {
            "preferred_hours": [10, 14, 19],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7],
            "min_spacing": 180,
            "boost": 1.0,
        },
        "bump_normal": {
            "preferred_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 23, 0, 1, 2],
            "min_spacing": 60,
            "boost": 1.0,
        },
        "bump_descriptive": {
            "preferred_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 23, 0, 1, 2],
            "min_spacing": 60,
            "boost": 1.0,
        },
        "bump_text_only": {
            "preferred_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 23, 0, 1, 2],
            "min_spacing": 45,
            "boost": 1.0,
        },
        "bump_flyer": {
            "preferred_hours": [10, 14, 19],
            "preferred_days": [3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7],
            "min_spacing": 120,
            "boost": 1.1,
        },
        "dm_farm": {
            "preferred_hours": [10, 14, 19],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 22, 23, 0, 1, 2],
            "min_spacing": 240,
            "boost": 1.0,
        },
        "like_farm": {
            "preferred_hours": [10, 14, 19],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 22, 23, 0, 1, 2],
            "min_spacing": 240,
            "boost": 1.0,
        },
        "live_promo": {
            "preferred_hours": [19, 21],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 8],
            "min_spacing": 300,
            "boost": 1.2,
        },

        # Retention send types (5)
        "renew_on_post": {
            "preferred_hours": [10, 14, 19],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 22, 23, 0, 1, 2],
            "min_spacing": 180,
            "boost": 1.0,
        },
        "renew_on_message": {
            "preferred_hours": [10, 14, 19],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 22, 23, 0, 1, 2],
            "min_spacing": 180,
            "boost": 1.0,
        },
        # DEPRECATED: ppv_message merged into ppv_unlock
        # Remove this entire configuration block after 2025-01-16 transition period
        "ppv_message": {
            "preferred_hours": [19, 21],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 8],
            "min_spacing": 90,
            "boost": 1.1,
        },
        "ppv_followup": {
            "preferred_hours": [10, 14, 19, 21],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7],
            "min_spacing": 60,
            "boost": 1.0,
            "offset_from_parent": 20,  # 20 minutes after parent
        },
        "expired_winback": {
            "preferred_hours": [12],
            "preferred_days": [0, 1, 2, 3, 4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7, 22, 23, 0, 1, 2],
            "min_spacing": 240,
            "boost": 1.0,
        },
    }

    def __init__(self, creator_id: str = "") -> None:
        """Initialize optimizer with tracking state and creator profile.

        Args:
            creator_id: Creator identifier for deterministic timing variation
        """
        self._assigned_times: dict[str, list[time]] = {}
        self._creator_id = creator_id
        # Create timing profile for per-creator uniqueness
        self._timing_profile = CreatorTimingProfile.from_creator_id(creator_id)

    def get_adjusted_preferred_hours(
        self,
        base_hours: list[int],
        day_of_week: int
    ) -> list[int]:
        """Shift preferred hours based on day for variation.

        Applies morning/evening shifts to create daily variation in optimal
        posting times. Morning hours (<12) get morning_shift, evening hours
        (>=12) get evening_shift.

        Args:
            base_hours: Base preferred hours list
            day_of_week: 0=Monday, 6=Sunday

        Returns:
            Adjusted hours list with shifts applied
        """
        offsets = self.DAILY_TIME_OFFSETS.get(
            day_of_week,
            {"morning_shift": 0, "evening_shift": 0}
        )

        adjusted = []
        for hour in base_hours:
            if hour < 12:  # Morning hours
                new_hour = hour + offsets["morning_shift"]
            else:  # Afternoon/evening hours
                new_hour = hour + offsets["evening_shift"]

            # Clamp to valid range (6 AM - 11 PM)
            new_hour = max(6, min(23, new_hour))
            adjusted.append(new_hour)

        return adjusted

    def get_prime_hours_for_day(self, day_of_week: int) -> list[int]:
        """Get varied prime hours for each day with creator adjustment.

        Returns daily-rotated prime hours, further adjusted by creator's
        unique timing profile for maximum variation.

        Args:
            day_of_week: 0=Monday, 6=Sunday

        Returns:
            List of prime hours adjusted for day and creator
        """
        # Get base daily prime hours
        daily_prime = self.DAILY_PRIME_HOURS.get(day_of_week, self.PRIME_HOURS)

        # Apply creator-specific shift
        if self._timing_profile.creator_id:
            return self._timing_profile.get_adjusted_prime_hours(daily_prime)

        return daily_prime

    def optimize_timing(
        self,
        items: list[ScheduleItem],
        timing_data: dict[int, list[int]] | None = None
    ) -> list[ScheduleItem]:
        """Optimize timing for all schedule items.

        Args:
            items: List of schedule items to optimize
            timing_data: Optional historical timing data (hour -> performance list)

        Returns:
            Optimized schedule items with assigned times
        """
        # Group items by date
        items_by_date: dict[str, list[ScheduleItem]] = {}
        for item in items:
            if item.scheduled_date not in items_by_date:
                items_by_date[item.scheduled_date] = []
            items_by_date[item.scheduled_date].append(item)

        # Process each day
        optimized_items = []
        for date_str, daily_items in items_by_date.items():
            # Sort by priority (1=highest)
            daily_items.sort(key=lambda x: x.priority)

            # Get available time slots for the day
            available_slots = self._generate_time_slots(date_str)

            # Assign optimal time slots
            for item in daily_items:
                assigned_time = self.assign_time_slot(
                    item,
                    available_slots,
                    timing_data
                )

                if assigned_time:
                    # Apply final jitter for organic feel
                    date_obj = datetime.strptime(item.scheduled_date, "%Y-%m-%d")
                    if self._creator_id:
                        # Apply jitter with creator-specific bias
                        final_time = apply_time_jitter(
                            assigned_time, self._creator_id, date_obj.weekday()
                        )
                        # Apply additional creator bias to the result
                        if self._timing_profile.base_jitter_offset != 0:
                            biased_minute = final_time.minute + self._timing_profile.base_jitter_offset
                            biased_minute = max(0, min(59, biased_minute))
                            final_time = time(final_time.hour, biased_minute)
                    else:
                        final_time = assigned_time
                    item.scheduled_time = final_time.strftime("%H:%M")
                    # Remove used slot and nearby slots (spacing)
                    available_slots = self._remove_nearby_slots(
                        available_slots,
                        assigned_time,
                        item.send_type_key
                    )
                else:
                    # Fallback to any available slot
                    if available_slots:
                        log_fallback(
                            logger,
                            operation="assign_time_slot",
                            fallback_reason="No optimal time slot found",
                            fallback_action="Using first available slot",
                            send_type_key=item.send_type_key,
                            scheduled_date=item.scheduled_date,
                            priority=item.priority
                        )
                        item.scheduled_time = available_slots[0].strftime("%H:%M")
                        available_slots = available_slots[1:]
                    else:
                        # Last resort - assign to random hour
                        random_hour = random.randint(9, 22)
                        log_fallback(
                            logger,
                            operation="assign_time_slot",
                            fallback_reason="No available slots remaining",
                            fallback_action=f"Assigned random hour {random_hour}:00",
                            send_type_key=item.send_type_key,
                            scheduled_date=item.scheduled_date,
                            priority=item.priority,
                            severity="high"
                        )
                        item.scheduled_time = f"{random_hour:02d}:00"

                optimized_items.append(item)

        return optimized_items

    def assign_time_slot(
        self,
        item: ScheduleItem,
        available_slots: list[time],
        timing_data: dict[int, list[int]] | None = None
    ) -> time | None:
        """Assign optimal time slot for item.

        Args:
            item: Schedule item to assign
            available_slots: Available time slots
            timing_data: Historical timing performance data

        Returns:
            Assigned time or None if no suitable slot
        """
        if not available_slots:
            logger.debug(
                "No available slots for assignment",
                extra={
                    "send_type_key": item.send_type_key,
                    "scheduled_date": item.scheduled_date
                }
            )
            return None

        # Get timing preferences for send type
        preferences = self.TIMING_PREFERENCES.get(
            item.send_type_key,
            {
                "preferred_hours": self.PRIME_HOURS,
                "preferred_days": self.PRIME_DAYS,
                "avoid_hours": self.AVOID_HOURS,
                "min_spacing": self.MIN_SPACING_MINUTES,
            }
        )

        # Score each available slot
        scored_slots = []
        date_obj = datetime.strptime(item.scheduled_date, "%Y-%m-%d")
        day_of_week = date_obj.weekday()

        for slot in available_slots:
            score = self.calculate_slot_score(
                slot.hour,
                day_of_week,
                item.send_type_key,
                preferences,
                timing_data
            )
            scored_slots.append((slot, score))

        # Sort by score descending
        scored_slots.sort(key=lambda x: x[1], reverse=True)

        # Return highest scoring slot
        return scored_slots[0][0] if scored_slots else None

    def calculate_slot_score(
        self,
        hour: int,
        day_of_week: int,
        send_type_key: str,
        preferences: dict[str, Any],
        timing_data: dict[int, list[int]] | None = None
    ) -> float:
        """Calculate score for time slot.

        Args:
            hour: Hour of day (0-23)
            day_of_week: Day of week (0=Monday)
            send_type_key: Send type key
            preferences: Timing preferences
            timing_data: Historical performance data

        Returns:
            Score from 0-100
        """
        score = SLOT_SCORE_BASE

        # Get base preferred hours and apply daily adjustment
        base_preferred = preferences.get("preferred_hours", [])
        preferred_hours = self.get_adjusted_preferred_hours(base_preferred, day_of_week)

        # Preferred hours bonus (using adjusted hours)
        if hour in preferred_hours:
            position = preferred_hours.index(hour)
            score += PREFERRED_HOURS_MAX_BONUS - (position * PREFERRED_HOURS_POSITION_DECAY)

        # Preferred days bonus
        if day_of_week in preferences.get("preferred_days", []):
            score += PREFERRED_DAYS_BONUS

        # Avoid hours penalty
        if hour in preferences.get("avoid_hours", []):
            score -= AVOID_HOURS_PENALTY

        # Prime time bonus (using daily-rotated prime hours)
        daily_prime_hours = self.get_prime_hours_for_day(day_of_week)
        if hour in daily_prime_hours:
            score += PRIME_TIME_BONUS

        # Prime day bonus
        if day_of_week in self.PRIME_DAYS:
            score += PRIME_DAY_BONUS

        # Historical performance bonus
        if timing_data and hour in timing_data:
            hour_performance = timing_data[hour]
            if hour_performance:
                avg_performance = sum(hour_performance) / len(hour_performance)
                score += (avg_performance / HISTORICAL_PERFORMANCE_SCALE) * HISTORICAL_PERFORMANCE_MAX_BONUS

        # Revenue category gets prime time priority
        if send_type_key.startswith("ppv_") and hour in PPV_PRIME_HOURS:
            score += PPV_PRIME_TIME_BONUS

        # Creator clustering preference bonus
        if self._timing_profile.creator_id and self._timing_profile.should_cluster_at_time(hour):
            score += 5  # Small bonus for matching creator's natural rhythm

        return max(SLOT_SCORE_MIN, min(SLOT_SCORE_MAX, score))

    def apply_saturation_adjustment(
        self,
        base_volume: int,
        saturation_score: float
    ) -> int:
        """Adjust volume based on saturation metrics.

        Args:
            base_volume: Base send volume
            saturation_score: Saturation score (0-100, higher = more saturated)

        Returns:
            Adjusted volume
        """
        if saturation_score < SATURATION_LOW_THRESHOLD:
            # Low saturation - can increase volume
            return int(base_volume * SATURATION_LOW_MULTIPLIER)
        elif saturation_score < SATURATION_MODERATE_THRESHOLD:
            # Moderate saturation - maintain volume
            return int(base_volume * SATURATION_MODERATE_MULTIPLIER)
        elif saturation_score < SATURATION_HIGH_THRESHOLD:
            # High saturation - reduce volume slightly
            return int(base_volume * SATURATION_HIGH_MULTIPLIER)
        else:
            # Very high saturation - reduce significantly
            return int(base_volume * SATURATION_VERY_HIGH_MULTIPLIER)

    def _generate_time_slots(self, date_str: str) -> list[time]:
        """Generate available time slots for a day with organic variation.

        Args:
            date_str: Date string (YYYY-MM-DD)

        Returns:
            List of available time objects with natural minute variations
        """
        slots = []

        # Parse date for day-based variation
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_offset = date_obj.weekday()

        # Generate slots from 8 AM to 11 PM
        for hour in range(8, 24):
            if hour in self.AVOID_HOURS:
                continue

            # Use varied minute intervals instead of fixed [0, 15, 30, 45]
            base_minutes = [0, 15, 30, 45]
            for minute in base_minutes:
                base_slot = time(hour, minute)

                # Apply jitter if creator_id is set
                if self._creator_id:
                    jittered_slot = apply_time_jitter(base_slot, self._creator_id, day_offset)
                    slots.append(jittered_slot)
                else:
                    slots.append(base_slot)

        # Shuffle to add randomness while maintaining preferences
        random.shuffle(slots)

        return slots

    def _remove_nearby_slots(
        self,
        slots: list[time],
        assigned_time: time,
        send_type_key: str
    ) -> list[time]:
        """Remove slots too close to assigned time based on spacing rules.

        Args:
            slots: Available time slots
            assigned_time: Time just assigned
            send_type_key: Send type key for spacing rules

        Returns:
            Filtered slot list
        """
        # Get minimum spacing for send type
        preferences = self.TIMING_PREFERENCES.get(send_type_key, {})
        min_spacing = preferences.get("min_spacing", self.MIN_SPACING_MINUTES)

        # Convert assigned time to minutes since midnight
        assigned_minutes = assigned_time.hour * 60 + assigned_time.minute

        # Filter out slots within spacing window
        filtered_slots = []
        for slot in slots:
            slot_minutes = slot.hour * 60 + slot.minute
            if abs(slot_minutes - assigned_minutes) >= min_spacing:
                filtered_slots.append(slot)

        return filtered_slots

    def reset_tracking(self) -> None:
        """Reset timing tracking for new schedule generation."""
        self._assigned_times.clear()

    def get_timing_stats(self) -> dict[str, Any]:
        """Get timing distribution statistics.

        Returns:
            Dictionary with timing metrics
        """
        all_times = []
        for times in self._assigned_times.values():
            all_times.extend(times)

        if not all_times:
            logger.debug("No timing data available for statistics")
            return {
                "total_assigned": 0,
                "hour_distribution": {},
                "prime_time_percentage": 0,
            }

        # Calculate hour distribution
        hour_dist: dict[int, int] = {}
        for t in all_times:
            hour_dist[t.hour] = hour_dist.get(t.hour, 0) + 1

        # Calculate prime time percentage
        prime_count = sum(1 for t in all_times if t.hour in self.PRIME_HOURS)
        prime_pct = (prime_count / len(all_times)) * 100 if all_times else 0

        return {
            "total_assigned": len(all_times),
            "hour_distribution": hour_dist,
            "prime_time_percentage": prime_pct,
        }

    @property
    def timing_profile(self) -> CreatorTimingProfile:
        """Get the creator's timing profile for external access."""
        return self._timing_profile
