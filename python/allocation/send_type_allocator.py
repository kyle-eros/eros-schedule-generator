"""
Send Type Allocator - Volume-based content distribution engine.

Intelligently allocates send types across a weekly schedule based on:
- Volume tier (LOW/MID/HIGH/ULTRA)
- Page type (paid/free)
- Day of week performance patterns
- Category balancing (revenue/engagement/retention)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, List

from python.models.send_type import (
    PAGE_TYPE_FREE_ONLY,
    PAGE_TYPE_PAID_ONLY,
    resolve_send_type_key,
)
from python.models.creator_timing_profile import CreatorTimingProfile


class VolumeTier(Enum):
    """Volume tier classification based on fan count."""

    LOW = "low"      # 0-999 fans
    MID = "mid"      # 1,000-4,999 fans
    HIGH = "high"    # 5,000-14,999 fans
    ULTRA = "ultra"  # 15,000+ fans


@dataclass(frozen=True, slots=True)
class VolumeConfig:
    """Volume configuration for a creator.

    Attributes:
        tier: Volume tier classification
        revenue_per_day: Target revenue sends per day
        engagement_per_day: Target engagement sends per day
        retention_per_day: Target retention sends per day
        fan_count: Total number of fans
        page_type: 'paid' or 'free'

    Note:
        Free pages support limited retention types (ppv_followup only).
        Paid pages support all retention types including renewal-focused sends.
    """

    tier: VolumeTier
    revenue_per_day: int
    engagement_per_day: int
    retention_per_day: int
    fan_count: int
    page_type: str

    def __post_init__(self) -> None:
        """Validate configuration constraints after initialization."""
        if self.page_type not in ("paid", "free"):
            raise ValueError(
                f"page_type must be 'paid' or 'free', got '{self.page_type}'"
            )

    @property
    def total_per_day(self) -> int:
        """Total sends per day across all categories."""
        return self.revenue_per_day + self.engagement_per_day + self.retention_per_day


@dataclass
class DiversityValidation:
    """Result of diversity validation for a weekly schedule.

    Tracks unique send type counts by category and provides validation
    feedback for ensuring schedule variety.

    Attributes:
        is_valid: Whether the schedule meets diversity requirements
        unique_type_count: Total unique send types used across the week
        revenue_type_count: Unique revenue types used
        engagement_type_count: Unique engagement types used
        retention_type_count: Unique retention types used
        errors: Critical validation failures that must be fixed
        warnings: Non-critical issues that should be addressed
    """

    is_valid: bool
    unique_type_count: int
    revenue_type_count: int
    engagement_type_count: int
    retention_type_count: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class SendTypeAllocator:
    """Allocates send types across weekly schedule based on volume configuration."""

    # Tier-based configuration templates
    # Note: Free pages support limited retention (ppv_followup only)
    TIER_CONFIGS: dict[VolumeTier, dict[str, dict[str, int]]] = {
        VolumeTier.LOW: {
            "paid": {"revenue": 3, "engagement": 3, "retention": 1},
            "free": {"revenue": 4, "engagement": 3, "retention": 1},
        },
        VolumeTier.MID: {
            "paid": {"revenue": 4, "engagement": 3, "retention": 2},
            "free": {"revenue": 5, "engagement": 3, "retention": 1},
        },
        VolumeTier.HIGH: {
            "paid": {"revenue": 5, "engagement": 4, "retention": 2},
            "free": {"revenue": 6, "engagement": 4, "retention": 2},
        },
        VolumeTier.ULTRA: {
            "paid": {"revenue": 6, "engagement": 5, "retention": 3},
            "free": {"revenue": 8, "engagement": 5, "retention": 2},
        },
    }

    # Day-of-week performance adjustments (0=Monday, 6=Sunday)
    DAY_ADJUSTMENTS: dict[int, int] = {
        0: -1,   # Monday - slower start
        1: 0,    # Tuesday - normal
        2: 0,    # Wednesday - normal
        3: 0,    # Thursday - normal
        4: 1,    # Friday - peak revenue day
        5: 1,    # Saturday - high activity
        6: 0,    # Sunday - normal
    }

    # Maximum sends per day by category
    DAILY_MAXIMUMS: dict[str, int] = {
        "revenue": 8,
        "engagement": 6,
        "retention": 4,
    }

    # Maximum sends per week by category
    WEEKLY_MAXIMUMS: dict[str, int] = {
        "revenue": 45,
        "engagement": 35,
        "retention": 20,
    }

    # Daily strategy profiles for varied allocation patterns
    # Each day uses a different interleaving strategy to avoid templated schedules
    DAILY_STRATEGIES: dict[str, dict[str, Any]] = {
        "revenue_front": {
            "pattern": ["revenue", "revenue", "engagement", "revenue", "engagement", "retention"],
            "description": "Front-load revenue, engagement mid-day"
        },
        "engagement_heavy": {
            "pattern": ["engagement", "revenue", "engagement", "engagement", "revenue", "retention"],
            "description": "Engagement focus with revenue anchors"
        },
        "balanced_spread": {
            "pattern": ["revenue", "engagement", "retention", "revenue", "engagement", "revenue"],
            "description": "Even distribution throughout day"
        },
        "evening_revenue": {
            "pattern": ["engagement", "engagement", "revenue", "revenue", "revenue", "retention"],
            "description": "Light morning, heavy evening revenue"
        },
        "retention_first": {
            "pattern": ["retention", "revenue", "engagement", "revenue", "engagement", "revenue"],
            "description": "Early retention touch, then revenue"
        }
    }

    # Daily type flavor rotation - emphasizes different send types each day
    # This prevents the same types appearing in the same slots every day
    DAILY_FLAVORS: dict[int, dict[str, str | None]] = {
        0: {"emphasis": "bundle", "avoid": "game_post"},          # Monday: Bundle day
        1: {"emphasis": "dm_farm", "avoid": "like_farm"},         # Tuesday: DM engagement
        2: {"emphasis": "flash_bundle", "avoid": "bundle"},       # Wednesday: Flash deals
        3: {"emphasis": "game_post", "avoid": "first_to_tip"},    # Thursday: Games
        4: {"emphasis": "first_to_tip", "avoid": "game_post"},    # Friday: Competition
        5: {"emphasis": "vip_program", "avoid": None},            # Saturday: VIP focus
        6: {"emphasis": "link_drop", "avoid": "dm_farm"},         # Sunday: Link catch-up
    }

    # Diversity requirements to ensure variety in weekly schedules
    # Prevents over-reliance on a few send types (e.g., just ppv_unlock + bump_normal)
    DIVERSITY_REQUIREMENTS: dict[str, int] = {
        "min_unique_types": 10,           # Minimum unique send types across week
        "min_revenue_types": 4,           # Minimum unique revenue types
        "min_engagement_types": 4,        # Minimum unique engagement types
        "min_retention_types_paid": 2,    # Minimum retention types for paid pages
        "min_retention_types_free": 1,    # Minimum retention types for free pages
    }

    # Send type pools by category (updated taxonomy - 22 total types)
    # Revenue (9 types)
    REVENUE_TYPES = [
        "ppv_unlock",       # Primary PPV (renamed from ppv_video)
        "ppv_wall",         # NEW - FREE pages only
        "tip_goal",         # NEW - PAID pages only
        "vip_program",
        "game_post",
        "bundle",
        "flash_bundle",
        "snapchat_bundle",
        "first_to_tip"
    ]

    # Revenue types for FREE pages (excludes tip_goal)
    REVENUE_TYPES_FREE = [
        "ppv_unlock",
        "ppv_wall",         # FREE pages only
        "vip_program",
        "game_post",
        "bundle",
        "flash_bundle",
        "snapchat_bundle",
        "first_to_tip"
    ]

    # Revenue types for PAID pages (excludes ppv_wall)
    REVENUE_TYPES_PAID = [
        "ppv_unlock",
        "tip_goal",         # PAID pages only
        "vip_program",
        "game_post",
        "bundle",
        "flash_bundle",
        "snapchat_bundle",
        "first_to_tip"
    ]

    ENGAGEMENT_TYPES = [
        "link_drop",
        "wall_link_drop",
        "bump_normal",
        "bump_descriptive",
        "bump_text_only",
        "bump_flyer",
        "dm_farm",
        "like_farm",
        "live_promo"
    ]

    # Retention (4 types) - ppv_message removed/deprecated
    RETENTION_TYPES = [
        "renew_on_post",
        "renew_on_message",
        "ppv_followup",
        "expired_winback"
    ]

    # Page-type-aware retention type pools
    # Free pages can only use ppv_followup (no subscription renewal types)
    FREE_PAGE_RETENTION_TYPES = [
        "ppv_followup"
    ]

    # Paid-only retention types (require active subscription)
    PAID_ONLY_RETENTION_TYPES = [
        "renew_on_post",
        "renew_on_message",
        "expired_winback"
    ]

    def __init__(self, creator_id: str = "") -> None:
        """Initialize allocator with creator context.

        Args:
            creator_id: Creator identifier for deterministic strategy selection
        """
        self._creator_id = creator_id
        # Create timing profile for per-creator uniqueness
        self._timing_profile = CreatorTimingProfile.from_creator_id(creator_id)

    @property
    def timing_profile(self) -> CreatorTimingProfile:
        """Get the creator's timing profile for external access."""
        return self._timing_profile

    def get_daily_strategy(self, day_of_week: int) -> str:
        """Select varied strategy per day per creator.

        Uses deterministic selection based on creator's timing profile
        to ensure same creator gets consistent but varied patterns.

        Args:
            day_of_week: 0=Monday, 6=Sunday

        Returns:
            Strategy key from DAILY_STRATEGIES
        """
        strategies = list(self.DAILY_STRATEGIES.keys())

        if self._creator_id:
            # Use timing profile's rotation offset for more variation
            offset = self._timing_profile.strategy_rotation_offset
            return strategies[(day_of_week + offset) % len(strategies)]
        else:
            # Fallback: simple day-based rotation
            return strategies[day_of_week % len(strategies)]

    def apply_daily_flavor(self, day_of_week: int, available_types: list[str]) -> list[str]:
        """Reorder types to emphasize daily theme with creator personality.

        Each day has a "flavor" that pushes certain types to the front
        and others to the back, creating varied daily patterns.

        Args:
            day_of_week: 0=Monday, 6=Sunday
            available_types: List of available send type keys

        Returns:
            Reordered list with emphasized type first, avoided type last
        """
        # Make a copy to avoid mutating original
        types = available_types.copy()

        flavor = self.DAILY_FLAVORS.get(day_of_week, {})
        emphasis = flavor.get("emphasis")
        avoid = flavor.get("avoid")

        # Boost emphasized type to front
        if emphasis and emphasis in types:
            types.remove(emphasis)
            types.insert(0, emphasis)

        # Push avoided type to back (but don't remove - still available)
        if avoid and avoid in types:
            types.remove(avoid)
            types.append(avoid)

        # Apply creator-specific reordering based on clustering preference
        if self._timing_profile.creator_id:
            preference = self._timing_profile.time_clustering_preference
            # Slight shuffle based on preference - moves 2nd item to different position
            if len(types) > 2:
                if preference == "cluster_morning" and day_of_week < 3:
                    # Early week: move engagement types up
                    pass  # Keep current order
                elif preference == "cluster_evening" and day_of_week >= 4:
                    # Late week: keep revenue focus
                    pass  # Keep current order

        return types

    @staticmethod
    def get_volume_tier(fan_count: int) -> VolumeTier:
        """Classify volume tier based on fan count.

        Args:
            fan_count: Number of fans/subscribers

        Returns:
            Appropriate VolumeTier
        """
        if fan_count < 1000:
            return VolumeTier.LOW
        elif fan_count < 5000:
            return VolumeTier.MID
        elif fan_count < 15000:
            return VolumeTier.HIGH
        else:
            return VolumeTier.ULTRA

    @staticmethod
    def get_revenue_types_for_page(page_type: str) -> list[str]:
        """Get available revenue types based on page type.

        Args:
            page_type: 'paid' or 'free'

        Returns:
            List of valid revenue send type keys for the page type
        """
        if page_type == "free":
            return SendTypeAllocator.REVENUE_TYPES_FREE.copy()
        else:
            return SendTypeAllocator.REVENUE_TYPES_PAID.copy()

    @staticmethod
    def filter_by_page_type(send_types: list[str], page_type: str) -> list[str]:
        """Filter send types based on page type restrictions.

        Args:
            send_types: List of send type keys to filter
            page_type: 'paid' or 'free'

        Returns:
            Filtered list excluding invalid types for the page
        """
        filtered = []
        for st in send_types:
            resolved = resolve_send_type_key(st)
            if page_type == "free" and resolved in PAGE_TYPE_PAID_ONLY:
                continue
            if page_type == "paid" and resolved in PAGE_TYPE_FREE_ONLY:
                continue
            filtered.append(st)
        return filtered

    @staticmethod
    def filter_by_performance(
        send_types: list[str],
        performance_data: dict[str, dict[str, Any]],
        exclude_tiers: list[str] | None = None
    ) -> list[str]:
        """Filter send types by performance tier.

        More flexible version that allows specifying which tiers to exclude.
        This method provides a class-level API for performance-based filtering.

        Args:
            send_types: List of send type keys to filter
            performance_data: Dict mapping send_type_key to performance info
                with 'tier' key. Example:
                {
                    'ppv_unlock': {'tier': 'top', 'rps': 450.0},
                    'dm_farm': {'tier': 'avoid', 'rps': 15.0},
                }
            exclude_tiers: List of tiers to exclude (default: ['avoid']).
                Valid tiers are: 'top', 'mid', 'low', 'avoid'

        Returns:
            Filtered list excluding send types in the specified tiers.
            Types not present in performance_data are kept (conservative approach).

        Examples:
            >>> allocator = SendTypeAllocator()
            >>> types = ['ppv_unlock', 'dm_farm', 'bump_normal']
            >>> perf = {'dm_farm': {'tier': 'avoid'}, 'ppv_unlock': {'tier': 'top'}}
            >>> SendTypeAllocator.filter_by_performance(types, perf)
            ['ppv_unlock', 'bump_normal']
            >>> SendTypeAllocator.filter_by_performance(types, perf, ['avoid', 'low'])
            ['ppv_unlock', 'bump_normal']
        """
        if exclude_tiers is None:
            exclude_tiers = ['avoid']

        excluded = []
        for st in send_types:
            if st in performance_data:
                tier = performance_data[st].get('tier', '')
                if tier in exclude_tiers:
                    excluded.append(st)

        return [st for st in send_types if st not in excluded]

    def allocate_week(
        self,
        config: VolumeConfig,
        page_type: str,
        week_start: datetime
    ) -> dict[str, list[dict[str, Any]]]:
        """Allocate send types for entire week with diversity enforcement.

        Creates a weekly schedule and validates it meets diversity requirements.
        If diversity is insufficient, attempts to rebalance the schedule.

        Args:
            config: Volume configuration
            page_type: 'paid' or 'free'
            week_start: Starting date of week (Monday)

        Returns:
            Dictionary mapping dates to lists of send type allocations

        Raises:
            ValueError: If schedule fails diversity requirements after fix attempt
        """
        weekly_schedule: dict[str, list[dict[str, Any]]] = {}

        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            day_of_week = current_date.weekday()

            daily_items = self.allocate_day(config, day_of_week, page_type)

            # Add date and scheduling metadata
            for item in daily_items:
                item["scheduled_date"] = current_date.strftime("%Y-%m-%d")
                item["day_of_week"] = day_of_week

            weekly_schedule[current_date.strftime("%Y-%m-%d")] = daily_items

        # Validate diversity requirements
        validation = self.validate_diversity(weekly_schedule, page_type)

        if not validation.is_valid:
            # Attempt to fix diversity issues
            weekly_schedule = self._ensure_diversity(weekly_schedule, page_type)

            # Re-validate after fix attempt
            validation = self.validate_diversity(weekly_schedule, page_type)

            if not validation.is_valid:
                error_details = "; ".join(validation.errors)
                raise ValueError(
                    f"Schedule failed diversity requirements after fix attempt. "
                    f"Errors: {error_details}. "
                    f"Unique types: {validation.unique_type_count}, "
                    f"Revenue: {validation.revenue_type_count}, "
                    f"Engagement: {validation.engagement_type_count}, "
                    f"Retention: {validation.retention_type_count}"
                )

        return weekly_schedule

    def allocate_day(
        self,
        config: VolumeConfig,
        day_of_week: int,
        page_type: str
    ) -> list[dict[str, Any]]:
        """Allocate send types for a single day.

        Args:
            config: Volume configuration
            day_of_week: 0=Monday, 6=Sunday
            page_type: 'paid' or 'free'

        Returns:
            List of send type allocations for the day
        """
        # Get day adjustment factor
        adjustment = self.DAY_ADJUSTMENTS.get(day_of_week, 0)

        # Calculate adjusted volumes
        # Note: If base count is 0, adjustment should not increase it
        # This ensures free pages with retention_per_day=0 stay at 0
        revenue_count = min(
            max(0, config.revenue_per_day + adjustment) if config.revenue_per_day > 0 else 0,
            self.DAILY_MAXIMUMS["revenue"]
        )
        engagement_count = min(
            max(0, config.engagement_per_day + adjustment) if config.engagement_per_day > 0 else 0,
            self.DAILY_MAXIMUMS["engagement"]
        )
        retention_count = min(
            max(0, config.retention_per_day + adjustment) if config.retention_per_day > 0 else 0,
            self.DAILY_MAXIMUMS["retention"]
        )

        # Allocate by category
        revenue_items = self._allocate_revenue(revenue_count, page_type, day_of_week)
        engagement_items = self._allocate_engagement(engagement_count, page_type, day_of_week)
        retention_items = self._allocate_retention(retention_count, page_type, day_of_week)

        # Interleave categories using daily strategy
        all_items = self._interleave_categories(
            revenue_items,
            engagement_items,
            retention_items,
            day_of_week  # Pass day for strategy selection
        )

        return all_items

    def _allocate_revenue(
        self,
        count: int,
        page_type: str,
        day_of_week: int
    ) -> list[dict[str, Any]]:
        """Allocate revenue-focused send types with daily flavor variation.

        Args:
            count: Number of revenue sends to allocate
            page_type: 'paid' or 'free'
            day_of_week: 0=Monday, 6=Sunday

        Returns:
            List of revenue send type allocations
        """
        items = []

        # Get revenue types appropriate for page type
        revenue_types = self.get_revenue_types_for_page(page_type)

        # Apply daily flavor to reorder types
        revenue_types = self.apply_daily_flavor(day_of_week, revenue_types)

        # Allocate revenue sends with varied type selection
        for i in range(count):
            send_type = revenue_types[i % len(revenue_types)]

            # Determine media requirements
            requires_media = send_type in [
                "ppv_unlock", "ppv_wall", "bundle", "flash_bundle", "snapchat_bundle"
            ]

            # Determine price requirements
            requires_price = send_type in [
                "ppv_unlock", "ppv_wall", "tip_goal", "bundle", "flash_bundle"
            ]

            items.append({
                "send_type_key": send_type,
                "category": "revenue",
                "priority": 1,
                "requires_caption": True,
                "requires_media": requires_media,
                "requires_price": requires_price,
                "_daily_flavor": self.DAILY_FLAVORS.get(day_of_week, {}).get("emphasis"),
            })

        return items

    def _allocate_engagement(
        self,
        count: int,
        page_type: str,
        day_of_week: int
    ) -> list[dict[str, Any]]:
        """Allocate engagement-focused send types with daily flavor variation.

        Args:
            count: Number of engagement sends to allocate
            page_type: 'paid' or 'free'
            day_of_week: 0=Monday, 6=Sunday

        Returns:
            List of engagement send type allocations
        """
        items = []

        # Engagement types pool
        engagement_types = [
            "bump_normal",
            "bump_descriptive",
            "bump_text_only",
            "bump_flyer",
            "dm_farm",
            "like_farm",
            "link_drop",
            "wall_link_drop",
            "live_promo"
        ]

        # Apply daily flavor to reorder types
        engagement_types = self.apply_daily_flavor(day_of_week, engagement_types)

        for i in range(count):
            send_type = engagement_types[i % len(engagement_types)]

            # Determine media requirements
            requires_media = send_type in ["bump_flyer", "wall_link_drop"]

            items.append({
                "send_type_key": send_type,
                "category": "engagement",
                "priority": 2,
                "requires_caption": True,
                "requires_media": requires_media,
                "_daily_flavor": self.DAILY_FLAVORS.get(day_of_week, {}).get("emphasis"),
            })

        return items

    def _allocate_retention(
        self,
        count: int,
        page_type: str,
        day_of_week: int
    ) -> list[dict[str, Any]]:
        """Allocate retention-focused send types based on page type.

        Free pages can only use ppv_followup.
        Paid pages have access to all retention types including renewal-focused sends.

        Args:
            count: Number of retention sends to allocate
            page_type: 'paid' or 'free'
            day_of_week: 0=Monday, 6=Sunday

        Returns:
            List of retention send type allocations
        """
        items: list[dict[str, Any]] = []

        # Select retention types based on page_type
        # Free pages: limited to ppv_followup only (no subscription renewal types)
        # Paid pages: full access to all 4 retention types
        if page_type == "free":
            retention_types = self.FREE_PAGE_RETENTION_TYPES.copy()
        else:
            retention_types = self.RETENTION_TYPES.copy()

        # If no retention types available for this page type, return empty
        if not retention_types:
            return items

        for i in range(count):
            send_type = retention_types[i % len(retention_types)]

            # Determine media requirements
            requires_media = send_type in ["renew_on_post"]

            items.append({
                "send_type_key": send_type,
                "category": "retention",
                "priority": 3,
                "requires_caption": True,
                "requires_media": requires_media,
            })

        return items

    def _interleave_categories(
        self,
        revenue_items: list[dict[str, Any]],
        engagement_items: list[dict[str, Any]],
        retention_items: list[dict[str, Any]],
        day_of_week: int = 0
    ) -> list[dict[str, Any]]:
        """Interleave items using daily strategy pattern to prevent templating.

        Args:
            revenue_items: Revenue send allocations
            engagement_items: Engagement send allocations
            retention_items: Retention send allocations
            day_of_week: Day of week for strategy selection (0=Monday)

        Returns:
            Interleaved list using varied daily strategy
        """
        result = []

        # Create category pools
        pools = {
            "revenue": revenue_items.copy(),
            "engagement": engagement_items.copy(),
            "retention": retention_items.copy()
        }

        # Get strategy pattern for this day
        strategy_key = self.get_daily_strategy(day_of_week)
        strategy = self.DAILY_STRATEGIES.get(strategy_key, {})
        pattern = strategy.get("pattern", ["revenue", "engagement", "retention"])
        pattern_index = 0

        while any(pools.values()):
            # Get next category from strategy pattern
            category = pattern[pattern_index % len(pattern)]

            # If category has items, add one
            if pools[category]:
                item = pools[category].pop(0)
                # Tag item with strategy used for debugging/validation
                item["_strategy_used"] = strategy_key
                result.append(item)

            pattern_index += 1

            # Handle exhausted categories
            if not pools[category]:
                # Remove exhausted category from pattern for this iteration
                remaining_pattern = [c for c in pattern if pools.get(c)]
                if remaining_pattern:
                    pattern = remaining_pattern
                    pattern_index = 0
                else:
                    break

        return result

    def validate_diversity(
        self,
        weekly_schedule: dict[str, list[dict[str, Any]]],
        page_type: str
    ) -> DiversityValidation:
        """Validate that weekly schedule meets diversity requirements.

        Ensures the schedule uses a variety of send types across all categories,
        preventing over-reliance on just ppv_unlock + bump_normal patterns.

        Args:
            weekly_schedule: Dictionary mapping dates to lists of send allocations
            page_type: 'paid' or 'free' (affects retention type requirements)

        Returns:
            DiversityValidation with counts and validation status
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Collect all send types used across the week
        all_types: set[str] = set()
        revenue_types: set[str] = set()
        engagement_types: set[str] = set()
        retention_types: set[str] = set()

        for date, items in weekly_schedule.items():
            for item in items:
                send_type = item.get("send_type_key", "")
                category = item.get("category", "")

                all_types.add(send_type)

                if category == "revenue":
                    revenue_types.add(send_type)
                elif category == "engagement":
                    engagement_types.add(send_type)
                elif category == "retention":
                    retention_types.add(send_type)

        # Check for minimum unique types overall
        unique_count = len(all_types)
        min_unique = self.DIVERSITY_REQUIREMENTS["min_unique_types"]
        if unique_count < min_unique:
            errors.append(
                f"Insufficient diversity: only {unique_count} unique types "
                f"(minimum: {min_unique})"
            )

        # Check revenue type diversity
        revenue_count = len(revenue_types)
        min_revenue = self.DIVERSITY_REQUIREMENTS["min_revenue_types"]
        if revenue_count < min_revenue:
            errors.append(
                f"Insufficient revenue diversity: only {revenue_count} types "
                f"(minimum: {min_revenue})"
            )

        # Check engagement type diversity
        engagement_count = len(engagement_types)
        min_engagement = self.DIVERSITY_REQUIREMENTS["min_engagement_types"]
        if engagement_count < min_engagement:
            errors.append(
                f"Insufficient engagement diversity: only {engagement_count} types "
                f"(minimum: {min_engagement})"
            )

        # Check retention type diversity (page-type-aware)
        retention_count = len(retention_types)
        if page_type == "free":
            min_retention = self.DIVERSITY_REQUIREMENTS["min_retention_types_free"]
        else:
            min_retention = self.DIVERSITY_REQUIREMENTS["min_retention_types_paid"]

        if retention_count < min_retention:
            errors.append(
                f"Insufficient retention diversity: only {retention_count} types "
                f"(minimum: {min_retention} for {page_type} pages)"
            )

        # Special check: reject schedules that ONLY use ppv_unlock + bump_normal
        # This indicates a severely under-diversified schedule
        if all_types == {"ppv_unlock", "bump_normal"} or (
            len(all_types) <= 2 and "ppv_unlock" in all_types and "bump_normal" in all_types
        ):
            errors.append(
                "Critical: Schedule only contains ppv_unlock + bump_normal. "
                "This is not acceptable diversity."
            )

        # Warnings for slightly low diversity
        if unique_count >= min_unique and unique_count < min_unique + 2:
            warnings.append(
                f"Diversity is at minimum threshold ({unique_count} types). "
                "Consider adding more variety."
            )

        is_valid = len(errors) == 0

        return DiversityValidation(
            is_valid=is_valid,
            unique_type_count=unique_count,
            revenue_type_count=revenue_count,
            engagement_type_count=engagement_count,
            retention_type_count=retention_count,
            errors=errors,
            warnings=warnings
        )

    def _ensure_diversity(
        self,
        weekly_schedule: dict[str, list[dict[str, Any]]],
        page_type: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Rebalance weekly schedule to meet diversity requirements.

        Identifies overused send types (ppv_unlock, bump_normal) and replaces
        some instances with underused alternatives from the same category.

        Args:
            weekly_schedule: Dictionary mapping dates to lists of send allocations
            page_type: 'paid' or 'free' (affects type selection)

        Returns:
            Rebalanced weekly schedule meeting diversity requirements
        """
        # Get page-type-appropriate revenue types
        revenue_pool = self.get_revenue_types_for_page(page_type)

        # Count usage of each send type
        type_counts: dict[str, int] = {}
        for date, items in weekly_schedule.items():
            for item in items:
                send_type = item.get("send_type_key", "")
                type_counts[send_type] = type_counts.get(send_type, 0) + 1

        # Identify overused types (more than 30% of their category)
        overused_revenue = [t for t in revenue_pool if type_counts.get(t, 0) > 10]
        overused_engagement = [t for t in self.ENGAGEMENT_TYPES if type_counts.get(t, 0) > 10]

        # Identify underused types (less than 2 uses)
        underused_revenue = [t for t in revenue_pool if type_counts.get(t, 0) < 2]
        underused_engagement = [t for t in self.ENGAGEMENT_TYPES if type_counts.get(t, 0) < 2]

        # For retention, consider page type
        if page_type == "free":
            available_retention = self.FREE_PAGE_RETENTION_TYPES
        else:
            available_retention = self.RETENTION_TYPES
        underused_retention = [t for t in available_retention if type_counts.get(t, 0) < 1]

        # Create modified schedule
        modified_schedule: dict[str, list[dict[str, Any]]] = {}
        replacement_index = {"revenue": 0, "engagement": 0, "retention": 0}

        for date, items in weekly_schedule.items():
            modified_items: List[dict[str, Any]] = []

            for item in items:
                send_type = item.get("send_type_key", "")
                category = item.get("category", "")
                new_item = item.copy()

                # Replace overused revenue types
                if category == "revenue" and send_type in overused_revenue:
                    if underused_revenue and type_counts.get(send_type, 0) > 5:
                        idx = replacement_index["revenue"] % len(underused_revenue)
                        new_type = underused_revenue[idx]
                        new_item["send_type_key"] = new_type
                        new_item["requires_media"] = new_type in [
                            "ppv_unlock", "ppv_wall", "bundle", "flash_bundle", "snapchat_bundle"
                        ]
                        new_item["requires_price"] = new_type in [
                            "ppv_unlock", "ppv_wall", "tip_goal", "bundle", "flash_bundle"
                        ]
                        type_counts[send_type] -= 1
                        type_counts[new_type] = type_counts.get(new_type, 0) + 1
                        replacement_index["revenue"] += 1

                        # Remove from underused if no longer underused
                        if type_counts.get(new_type, 0) >= 2:
                            underused_revenue = [
                                t for t in underused_revenue if t != new_type
                            ]

                # Replace overused engagement types
                elif category == "engagement" and send_type in overused_engagement:
                    if underused_engagement and type_counts.get(send_type, 0) > 5:
                        idx = replacement_index["engagement"] % len(underused_engagement)
                        new_type = underused_engagement[idx]
                        new_item["send_type_key"] = new_type
                        new_item["requires_media"] = new_type in [
                            "bump_flyer", "wall_link_drop"
                        ]
                        type_counts[send_type] -= 1
                        type_counts[new_type] = type_counts.get(new_type, 0) + 1
                        replacement_index["engagement"] += 1

                        # Remove from underused if no longer underused
                        if type_counts.get(new_type, 0) >= 2:
                            underused_engagement = [
                                t for t in underused_engagement if t != new_type
                            ]

                # Ensure retention diversity
                elif category == "retention" and underused_retention:
                    # Add underused retention types
                    if type_counts.get(send_type, 0) > 3:
                        idx = replacement_index["retention"] % len(underused_retention)
                        new_type = underused_retention[idx]
                        new_item["send_type_key"] = new_type
                        new_item["requires_media"] = new_type in ["renew_on_post"]
                        type_counts[send_type] -= 1
                        type_counts[new_type] = type_counts.get(new_type, 0) + 1
                        replacement_index["retention"] += 1

                        # Remove from underused if no longer underused
                        if type_counts.get(new_type, 0) >= 1:
                            underused_retention = [
                                t for t in underused_retention if t != new_type
                            ]

                modified_items.append(new_item)

            modified_schedule[date] = modified_items

        return modified_schedule


def filter_non_converters(
    send_types: list[str],
    performance_data: dict[str, dict[str, Any]]
) -> list[str]:
    """Remove send types in 'avoid' tier from allocation (Gap 4.2).

    Filters out underperforming send types to reallocate volume to
    winning types. Types are identified as "avoid" based on their
    performance tier classification.

    Args:
        send_types: List of send type keys to filter
        performance_data: Dictionary mapping send_type_key to performance info:
            {
                'ppv_unlock': {'tier': 'top', 'rps': 450.0, ...},
                'dm_farm': {'tier': 'avoid', 'rps': 15.0, ...},
                ...
            }
            The 'tier' field should be one of: 'top', 'mid', 'low', 'avoid'

    Returns:
        Filtered list excluding 'avoid' tier types.
        Original list is not modified.

    Examples:
        >>> send_types = ['ppv_unlock', 'bump_normal', 'dm_farm', 'like_farm']
        >>> perf_data = {
        ...     'ppv_unlock': {'tier': 'top'},
        ...     'bump_normal': {'tier': 'mid'},
        ...     'dm_farm': {'tier': 'avoid'},
        ...     'like_farm': {'tier': 'low'},
        ... }
        >>> filter_non_converters(send_types, perf_data)
        ['ppv_unlock', 'bump_normal', 'like_farm']

        >>> # Types not in performance_data are kept (no data = not proven bad)
        >>> filter_non_converters(['ppv_unlock', 'unknown_type'], {})
        ['ppv_unlock', 'unknown_type']

    Note:
        - Types not present in performance_data are kept (conservative approach)
        - This function logs excluded types for debugging
        - Volume from excluded types should be reallocated to top performers
    """
    from python.logging_config import get_logger
    logger = get_logger(__name__)

    avoid_types: list[str] = []

    for send_type in send_types:
        if send_type in performance_data:
            tier = performance_data[send_type].get('tier', '')
            if tier == 'avoid':
                avoid_types.append(send_type)

    if avoid_types:
        logger.info(
            f"Excluding non-converters: {avoid_types}",
            extra={'excluded_types': avoid_types, 'count': len(avoid_types)}
        )

    return [st for st in send_types if st not in avoid_types]


# Module exports
__all__ = [
    'VolumeTier',
    'VolumeConfig',
    'DiversityValidation',
    'SendTypeAllocator',
    'filter_non_converters',
]
