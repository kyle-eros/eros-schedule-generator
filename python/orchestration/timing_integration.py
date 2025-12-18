"""
Timing Profile Integration for Schedule Generation - Wave 2.

Integrates CreatorTimingProfile with the scheduling pipeline to provide
creator-specific timing optimizations. This module bridges the gap between
the timing profile data model and the orchestration layer.

The integration provides:
- Lazy-loaded creator profiles for efficient resource usage
- Optimal follow-up window calculations based on engagement patterns
- AM/PM preference detection from peak engagement hours
- Creator-specific jitter adjustments for natural timing variation
- Multi-timezone audience support for follow-up scheduling
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from python.models.creator_timing_profile import CreatorTimingProfile


class TimingProfileIntegration:
    """Integrates CreatorTimingProfile with scheduling orchestration.

    Provides timing-related utilities for schedule generation by wrapping
    CreatorTimingProfile and exposing scheduling-specific methods. The profile
    is lazy-loaded on first access to minimize startup overhead.

    Attributes:
        creator_id: The creator identifier for profile lookup.

    Example:
        >>> integration = TimingProfileIntegration("creator_123")
        >>> min_offset, max_offset = integration.get_optimal_followup_window()
        >>> adjusted_jitter = integration.adjust_jitter_for_creator(5)
    """

    __slots__ = ("_creator_id", "_profile")

    def __init__(self, creator_id: str) -> None:
        """Initialize timing integration for a specific creator.

        Args:
            creator_id: The creator identifier used for profile lookup.
                       Profile is not loaded until first access.
        """
        self._creator_id = creator_id
        self._profile: Optional[CreatorTimingProfile] = None

    @property
    def profile(self) -> CreatorTimingProfile:
        """Lazy-load and return the creator's timing profile.

        The profile is loaded on first access using CreatorTimingProfile.from_creator_id()
        and cached for subsequent accesses.

        Returns:
            CreatorTimingProfile: The creator's timing profile with all
                deterministically-generated timing characteristics.
        """
        if self._profile is None:
            self._profile = CreatorTimingProfile.from_creator_id(self._creator_id)
        return self._profile

    def get_optimal_followup_window(self) -> tuple[int, int]:
        """Calculate optimal follow-up timing window based on engagement patterns.

        Uses the creator's average response time to determine when follow-ups
        are most likely to be effective. If no engagement data is available,
        returns conservative defaults.

        The calculation uses:
        - min_offset = max(15, int(avg_response_minutes * 0.6))
        - max_offset = min(45, int(avg_response_minutes * 1.5))

        Returns:
            tuple[int, int]: A tuple of (min_offset, max_offset) in minutes.
                Default is (15, 45) when no engagement data is available.

        Example:
            >>> integration = TimingProfileIntegration("creator_123")
            >>> min_wait, max_wait = integration.get_optimal_followup_window()
            >>> # Schedule follow-up between min_wait and max_wait minutes
        """
        # Default follow-up window
        default_min = 15
        default_max = 45

        # Check if profile has engagement_patterns with avg_response_minutes
        # CreatorTimingProfile is a simple dataclass without engagement_patterns
        # This would come from an extended profile or database query
        engagement_patterns = getattr(self.profile, "engagement_patterns", None)

        if engagement_patterns is None:
            return (default_min, default_max)

        avg_response = getattr(engagement_patterns, "avg_response_minutes", None)

        if avg_response is None or avg_response <= 0:
            return (default_min, default_max)

        # Calculate adjusted window based on average response time
        min_offset = max(default_min, int(avg_response * 0.6))
        max_offset = min(default_max, int(avg_response * 1.5))

        # Ensure min is always less than max
        if min_offset >= max_offset:
            min_offset = max(default_min, max_offset - 10)

        return (min_offset, max_offset)

    def should_allow_next_day_followup(self) -> bool:
        """Determine if next-day follow-ups are appropriate for this creator.

        Creators with multi-timezone audiences may benefit from next-day
        follow-ups to reach subscribers in different time zones.

        Returns:
            bool: True if the creator has a multi-timezone audience and
                  next-day follow-ups are recommended. False otherwise.

        Example:
            >>> integration = TimingProfileIntegration("creator_123")
            >>> if integration.should_allow_next_day_followup():
            ...     # Include next-day follow-up in schedule
        """
        # Check for timezone_info.multi_timezone_audience attribute
        # This would come from an extended profile or database query
        timezone_info = getattr(self.profile, "timezone_info", None)

        if timezone_info is None:
            return False

        return bool(getattr(timezone_info, "multi_timezone_audience", False))

    def get_am_pm_preference(self) -> Optional[str]:
        """Get the creator's AM/PM preference based on peak engagement hours.

        Analyzes the creator's peak engagement hour to determine whether
        they perform better in morning or afternoon/evening slots.

        Returns:
            Optional[str]: "AM" if peak hour is before noon (0-11),
                          "PM" if peak hour is noon or later (12-23),
                          None if no preference data is available.

        Example:
            >>> integration = TimingProfileIntegration("creator_123")
            >>> preference = integration.get_am_pm_preference()
            >>> if preference == "AM":
            ...     # Prioritize morning slots
        """
        # Check for preferred_windows.peak_engagement_hour attribute
        # This would come from an extended profile or database query
        preferred_windows = getattr(self.profile, "preferred_windows", None)

        if preferred_windows is None:
            return None

        peak_hour = getattr(preferred_windows, "peak_engagement_hour", None)

        if peak_hour is None:
            return None

        # Validate peak_hour is a valid hour value
        if not isinstance(peak_hour, (int, float)) or peak_hour < 0 or peak_hour > 23:
            return None

        peak_hour = int(peak_hour)

        # AM is before noon (0-11), PM is noon and after (12-23)
        return "AM" if peak_hour < 12 else "PM"

    def adjust_jitter_for_creator(self, base_jitter: int) -> int:
        """Adjust jitter value based on creator's timing variation preference.

        Some creators benefit from more predictable posting times (low variation),
        while others perform better with more randomized timing (high variation).

        The adjustment is based on activity_indicators.timing_variation:
        - "low": Reduces jitter by half (base_jitter // 2)
        - "high": Doubles the jitter (base_jitter * 2)
        - Any other value or missing: Returns base_jitter unchanged

        Args:
            base_jitter: The default jitter value in minutes.

        Returns:
            int: Adjusted jitter value based on creator's timing variation setting.
                 Returns base_jitter if no preference is found.

        Example:
            >>> integration = TimingProfileIntegration("creator_123")
            >>> base = 5
            >>> adjusted = integration.adjust_jitter_for_creator(base)
            >>> # adjusted may be 2, 5, or 10 depending on timing_variation
        """
        # Check for activity_indicators.timing_variation attribute
        # This would come from an extended profile or database query
        activity_indicators = getattr(self.profile, "activity_indicators", None)

        if activity_indicators is None:
            return base_jitter

        timing_variation = getattr(activity_indicators, "timing_variation", None)

        if timing_variation is None:
            return base_jitter

        # Normalize to lowercase for comparison
        variation_str = str(timing_variation).lower().strip()

        if variation_str == "low":
            return base_jitter // 2
        elif variation_str == "high":
            return base_jitter * 2
        else:
            return base_jitter

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        profile_loaded = "loaded" if self._profile is not None else "not loaded"
        return f"TimingProfileIntegration('{self._creator_id}', profile={profile_loaded})"


@lru_cache(maxsize=128)
def get_timing_integration(creator_id: str) -> TimingProfileIntegration:
    """Factory function to get a TimingProfileIntegration instance.

    Uses LRU caching to avoid creating duplicate integration instances
    for the same creator. The cache holds up to 128 entries.

    Args:
        creator_id: The creator identifier for profile lookup.

    Returns:
        TimingProfileIntegration: Cached or new integration instance.

    Example:
        >>> integration = get_timing_integration("creator_123")
        >>> # Subsequent calls with same ID return cached instance
        >>> same_integration = get_timing_integration("creator_123")
        >>> integration is same_integration
        True
    """
    return TimingProfileIntegration(creator_id)


def clear_timing_integration_cache() -> None:
    """Clear the timing integration cache.

    Useful for testing or when creator profile data has been updated
    and cached instances need to be refreshed.
    """
    get_timing_integration.cache_clear()


__all__ = [
    "TimingProfileIntegration",
    "get_timing_integration",
    "clear_timing_integration_cache",
]
