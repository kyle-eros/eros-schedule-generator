"""
Page type volume matrix calculator.

Extends the dynamic volume calculation system with page-type-aware volume
calculations. This module provides volume targets based on creator page type
(nude, non_nude, porno) and sub-type (gfe, commercial, personalized), applying
the appropriate bump ratios from the volume matrix.

The volume matrix defines PPV and bump targets per day based on:
- Volume tier (determined by fan count)
- Page type (nude, non_nude, porno)
- Sub-type (gfe, commercial, personalized)

Usage:
    from python.volume.page_type_calculator import (
        CreatorConfig,
        VolumeTargets,
        calculate_volume_targets,
        validate_bump_ratio,
    )

    # Create creator configuration
    config = CreatorConfig(
        creator_id="alexia",
        fan_count=12434,
        page_type="nude",
        sub_type="gfe",
        is_paid_page=True,
    )

    # Calculate volume targets
    targets = calculate_volume_targets(config)
    print(f"Tier: {targets.tier}")
    print(f"PPVs/day: {targets.mmppvs_per_day}")
    print(f"Bumps/day: {targets.bumps_per_day}")
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Tuple

from python.models.volume import VolumeTier
from python.volume.dynamic_calculator import get_volume_tier as _get_volume_tier_enum


# =============================================================================
# Type Definitions
# =============================================================================

PageType = Literal["nude", "non_nude", "porno"]
SubType = Literal["gfe", "commercial", "personalized"]
TierName = Literal["low", "mid", "high", "ultra"]


# =============================================================================
# Volume Matrix Constants
# =============================================================================

# PPV ranges per volume tier (min, max) per day
TIER_PPVS: Dict[TierName, Tuple[int, int]] = {
    "low": (2, 3),
    "mid": (4, 6),
    "high": (7, 9),
    "ultra": (10, 12),
}

# Bump matrix: page type and sub-type specific bump ratios
# Key: (page_type, sub_type)
# Value: Dict mapping tier to (min_bumps, max_bumps) per day
BUMP_MATRIX: Dict[Tuple[PageType, SubType], Dict[TierName, Tuple[int, int]]] = {
    ("nude", "gfe"): {
        "low": (4, 6),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
    ("nude", "commercial"): {
        "low": (5, 6),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
    ("nude", "personalized"): {
        "low": (4, 6),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
    ("non_nude", "gfe"): {
        "low": (4, 6),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
    ("non_nude", "commercial"): {
        "low": (5, 6),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
    ("non_nude", "personalized"): {
        "low": (4, 6),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
    ("porno", "gfe"): {
        "low": (5, 7),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
    ("porno", "commercial"): {
        "low": (5, 8),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
    ("porno", "personalized"): {
        "low": (5, 7),
        "mid": (4, 6),
        "high": (7, 9),
        "ultra": (10, 12),
    },
}

# Valid page types and sub-types for validation
VALID_PAGE_TYPES: Tuple[PageType, ...] = ("nude", "non_nude", "porno")
VALID_SUB_TYPES: Tuple[SubType, ...] = ("gfe", "commercial", "personalized")

# Validation tolerance for bump ratio checking (20%)
BUMP_RATIO_TOLERANCE: float = 0.20


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class CreatorConfig:
    """Extended creator configuration with page type information.

    Represents the complete configuration needed to calculate page-type-aware
    volume targets for a creator.

    Attributes:
        creator_id: Unique identifier for the creator.
        fan_count: Number of fans/subscribers (determines volume tier).
        page_type: Type of content page ('nude', 'non_nude', 'porno').
        sub_type: Sub-classification ('gfe', 'commercial', 'personalized').
        is_paid_page: Whether the page is a paid subscription page.
        confidence: Confidence score for the configuration (0.0-1.0).
            Lower confidence may result in more conservative targets.

    Raises:
        ValueError: If page_type or sub_type are invalid.
        ValueError: If fan_count is negative.
        ValueError: If confidence is outside 0.0-1.0 range.
    """

    creator_id: str
    fan_count: int
    page_type: PageType
    sub_type: SubType
    is_paid_page: bool
    confidence: float = 0.5

    def __post_init__(self) -> None:
        """Validate configuration on initialization."""
        if self.page_type not in VALID_PAGE_TYPES:
            raise ValueError(
                f"Invalid page_type: {self.page_type}. "
                f"Must be one of {VALID_PAGE_TYPES}"
            )
        if self.sub_type not in VALID_SUB_TYPES:
            raise ValueError(
                f"Invalid sub_type: {self.sub_type}. "
                f"Must be one of {VALID_SUB_TYPES}"
            )
        if self.fan_count < 0:
            raise ValueError(f"fan_count must be non-negative: {self.fan_count}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0: {self.confidence}"
            )


@dataclass(frozen=True, slots=True)
class VolumeTargets:
    """Calculated volume targets based on page type and tier.

    Immutable dataclass containing the calculated PPV and bump targets
    for a creator based on their page type, sub-type, and volume tier.

    Attributes:
        tier: Volume tier name ('low', 'mid', 'high', 'ultra').
        mmppvs_per_day: Tuple of (min, max) PPV messages per day.
        bumps_per_day: Tuple of (min, max) bump messages per day.
        bump_to_ppv_ratio: Calculated ratio of bumps to PPVs (average).
        total_messages_per_day: Tuple of (min, max) total messages per day.
    """

    tier: TierName
    mmppvs_per_day: Tuple[int, int]
    bumps_per_day: Tuple[int, int]
    bump_to_ppv_ratio: float
    total_messages_per_day: Tuple[int, int]

    @property
    def avg_ppvs(self) -> float:
        """Average PPVs per day (midpoint of range)."""
        return (self.mmppvs_per_day[0] + self.mmppvs_per_day[1]) / 2.0

    @property
    def avg_bumps(self) -> float:
        """Average bumps per day (midpoint of range)."""
        return (self.bumps_per_day[0] + self.bumps_per_day[1]) / 2.0

    @property
    def avg_total(self) -> float:
        """Average total messages per day."""
        return self.avg_ppvs + self.avg_bumps


# =============================================================================
# Functions
# =============================================================================


def get_volume_tier(fan_count: int) -> TierName:
    """Classify volume tier based on fan count.

    Wrapper around the existing volume tier classification that returns
    the tier name as a string for use with the page type matrix.

    Uses fan count thresholds:
    - LOW: 0-999 fans
    - MID: 1,000-4,999 fans
    - HIGH: 5,000-14,999 fans
    - ULTRA: 15,000+ fans

    Args:
        fan_count: Number of fans/subscribers.

    Returns:
        Tier name string ('low', 'mid', 'high', 'ultra').

    Raises:
        ValueError: If fan_count is negative.
    """
    if fan_count < 0:
        raise ValueError(f"fan_count must be non-negative: {fan_count}")

    tier_enum = _get_volume_tier_enum(fan_count)
    return tier_enum.value


def _get_bump_range(
    page_type: PageType,
    sub_type: SubType,
    tier: TierName,
) -> Tuple[int, int]:
    """Get bump range for a specific page type, sub-type, and tier.

    Internal function to look up bump ranges from the BUMP_MATRIX.

    Args:
        page_type: Creator's page type.
        sub_type: Creator's sub-type classification.
        tier: Volume tier name.

    Returns:
        Tuple of (min_bumps, max_bumps) per day.

    Raises:
        KeyError: If page_type/sub_type combination is not in matrix.
    """
    key = (page_type, sub_type)
    if key not in BUMP_MATRIX:
        raise KeyError(
            f"Unknown page_type/sub_type combination: {page_type}/{sub_type}"
        )
    return BUMP_MATRIX[key][tier]


def _calculate_bump_ratio(
    ppv_range: Tuple[int, int],
    bump_range: Tuple[int, int],
) -> float:
    """Calculate the bump-to-PPV ratio from ranges.

    Uses the midpoint of each range to calculate the ratio.

    Args:
        ppv_range: Tuple of (min, max) PPVs per day.
        bump_range: Tuple of (min, max) bumps per day.

    Returns:
        Ratio of average bumps to average PPVs.
    """
    avg_ppvs = (ppv_range[0] + ppv_range[1]) / 2.0
    avg_bumps = (bump_range[0] + bump_range[1]) / 2.0

    if avg_ppvs == 0:
        return 0.0

    return avg_bumps / avg_ppvs


def calculate_volume_targets(config: CreatorConfig) -> VolumeTargets:
    """Calculate volume targets based on creator configuration.

    Determines the appropriate PPV and bump volumes based on the creator's
    fan count (tier), page type, and sub-type. Uses the BUMP_MATRIX to
    apply page-type-specific bump ratios.

    Args:
        config: Creator configuration with page type and fan count.

    Returns:
        VolumeTargets with calculated PPV and bump ranges.

    Example:
        >>> config = CreatorConfig(
        ...     creator_id="alexia",
        ...     fan_count=12434,
        ...     page_type="nude",
        ...     sub_type="gfe",
        ...     is_paid_page=True,
        ... )
        >>> targets = calculate_volume_targets(config)
        >>> targets.tier
        'high'
        >>> targets.mmppvs_per_day
        (7, 9)
        >>> targets.bumps_per_day
        (7, 9)
    """
    # Determine tier from fan count
    tier = get_volume_tier(config.fan_count)

    # Get PPV range from tier
    ppv_range = TIER_PPVS[tier]

    # Get bump range from matrix based on page type and sub-type
    bump_range = _get_bump_range(config.page_type, config.sub_type, tier)

    # Calculate bump-to-PPV ratio
    bump_ratio = _calculate_bump_ratio(ppv_range, bump_range)

    # Calculate total messages per day
    total_min = ppv_range[0] + bump_range[0]
    total_max = ppv_range[1] + bump_range[1]

    return VolumeTargets(
        tier=tier,
        mmppvs_per_day=ppv_range,
        bumps_per_day=bump_range,
        bump_to_ppv_ratio=bump_ratio,
        total_messages_per_day=(total_min, total_max),
    )


def validate_bump_ratio(
    schedule: List[Dict[str, Any]],
    config: CreatorConfig,
) -> Dict[str, Any]:
    """Validate that a schedule's bump:PPV ratio matches page type expectations.

    Analyzes a schedule to count PPV and bump messages, then validates
    that the actual ratio falls within the expected range (with tolerance).

    Args:
        schedule: List of schedule entries, each containing at least a
            'send_type_key' field. PPV types should contain 'ppv' in the key,
            bump types should contain 'bump' in the key.
        config: Creator configuration to determine expected ratios.

    Returns:
        Dictionary containing:
            - is_valid: bool - Whether ratio is within acceptable range
            - actual_ratio: float - The actual bump:PPV ratio
            - expected_ratio: float - The expected ratio (midpoint)
            - expected_range: Tuple[float, float] - Min/max expected ratios
            - ppv_count: int - Number of PPV messages in schedule
            - bump_count: int - Number of bump messages in schedule
            - tolerance: float - The tolerance percentage used
            - message: str - Descriptive message about validation result
            - warnings: List[str] - Any warning messages

    Example:
        >>> schedule = [
        ...     {"send_type_key": "ppv_unlock", "time": "10:00"},
        ...     {"send_type_key": "bump_normal", "time": "12:00"},
        ...     {"send_type_key": "bump_descriptive", "time": "14:00"},
        ... ]
        >>> config = CreatorConfig(
        ...     creator_id="alexia",
        ...     fan_count=500,  # LOW tier
        ...     page_type="nude",
        ...     sub_type="gfe",
        ...     is_paid_page=True,
        ... )
        >>> result = validate_bump_ratio(schedule, config)
        >>> result["is_valid"]
        True
    """
    # Count PPVs and bumps in schedule
    ppv_count = 0
    bump_count = 0

    for entry in schedule:
        send_type_key = entry.get("send_type_key", "").lower()
        if "ppv" in send_type_key:
            ppv_count += 1
        elif "bump" in send_type_key:
            bump_count += 1

    # Calculate actual ratio
    if ppv_count == 0:
        actual_ratio = float("inf") if bump_count > 0 else 0.0
    else:
        actual_ratio = bump_count / ppv_count

    # Get expected targets
    targets = calculate_volume_targets(config)

    # Calculate expected ratio range with tolerance
    expected_ratio = targets.bump_to_ppv_ratio

    # Calculate min/max expected ratios from ranges
    if targets.mmppvs_per_day[1] > 0:
        min_expected_ratio = targets.bumps_per_day[0] / targets.mmppvs_per_day[1]
    else:
        min_expected_ratio = 0.0

    if targets.mmppvs_per_day[0] > 0:
        max_expected_ratio = targets.bumps_per_day[1] / targets.mmppvs_per_day[0]
    else:
        max_expected_ratio = float("inf")

    # Apply tolerance
    tolerance_factor = 1 + BUMP_RATIO_TOLERANCE
    min_acceptable = min_expected_ratio / tolerance_factor
    max_acceptable = max_expected_ratio * tolerance_factor

    # Determine if valid
    warnings: List[str] = []

    if ppv_count == 0 and bump_count == 0:
        is_valid = True
        message = "Empty schedule - no PPVs or bumps to validate"
    elif ppv_count == 0:
        is_valid = False
        message = f"No PPV messages found but {bump_count} bump messages present"
        warnings.append("Schedule has bumps without any PPV messages")
    elif actual_ratio < min_acceptable:
        is_valid = False
        message = (
            f"Bump ratio {actual_ratio:.2f} is below minimum "
            f"{min_acceptable:.2f} (expected {expected_ratio:.2f})"
        )
        warnings.append(
            f"Consider adding more bump messages for {config.page_type}/{config.sub_type}"
        )
    elif actual_ratio > max_acceptable:
        is_valid = False
        message = (
            f"Bump ratio {actual_ratio:.2f} exceeds maximum "
            f"{max_acceptable:.2f} (expected {expected_ratio:.2f})"
        )
        warnings.append(
            f"Consider reducing bump messages or adding more PPVs for "
            f"{config.page_type}/{config.sub_type}"
        )
    else:
        is_valid = True
        message = (
            f"Bump ratio {actual_ratio:.2f} is within acceptable range "
            f"[{min_acceptable:.2f}, {max_acceptable:.2f}]"
        )

    return {
        "is_valid": is_valid,
        "actual_ratio": actual_ratio,
        "expected_ratio": expected_ratio,
        "expected_range": (min_expected_ratio, max_expected_ratio),
        "ppv_count": ppv_count,
        "bump_count": bump_count,
        "tolerance": BUMP_RATIO_TOLERANCE,
        "message": message,
        "warnings": warnings,
    }


def get_tier_for_fan_count(fan_count: int) -> Dict[str, Any]:
    """Get complete tier information for a given fan count.

    Utility function to retrieve tier details including name, enum value,
    and the applicable PPV range.

    Args:
        fan_count: Number of fans/subscribers.

    Returns:
        Dictionary containing:
            - tier_name: str - Tier name ('low', 'mid', 'high', 'ultra')
            - tier_enum: VolumeTier - The VolumeTier enum value
            - ppv_range: Tuple[int, int] - PPV range for this tier
            - fan_count_range: str - Human-readable fan count range

    Example:
        >>> info = get_tier_for_fan_count(7500)
        >>> info["tier_name"]
        'high'
        >>> info["fan_count_range"]
        '5,000 - 14,999'
    """
    tier_name = get_volume_tier(fan_count)
    tier_enum = _get_volume_tier_enum(fan_count)

    fan_ranges = {
        "low": "0 - 999",
        "mid": "1,000 - 4,999",
        "high": "5,000 - 14,999",
        "ultra": "15,000+",
    }

    return {
        "tier_name": tier_name,
        "tier_enum": tier_enum,
        "ppv_range": TIER_PPVS[tier_name],
        "fan_count_range": fan_ranges[tier_name],
    }


def get_all_bump_ranges(
    page_type: PageType,
    sub_type: SubType,
) -> Dict[TierName, Tuple[int, int]]:
    """Get bump ranges for all tiers for a given page type and sub-type.

    Utility function to retrieve the complete bump matrix for a specific
    page type and sub-type combination.

    Args:
        page_type: Creator's page type.
        sub_type: Creator's sub-type classification.

    Returns:
        Dictionary mapping tier names to bump ranges.

    Raises:
        KeyError: If page_type/sub_type combination is not in matrix.

    Example:
        >>> ranges = get_all_bump_ranges("porno", "commercial")
        >>> ranges["low"]
        (5, 8)
        >>> ranges["ultra"]
        (10, 12)
    """
    key = (page_type, sub_type)
    if key not in BUMP_MATRIX:
        raise KeyError(
            f"Unknown page_type/sub_type combination: {page_type}/{sub_type}"
        )
    return BUMP_MATRIX[key].copy()


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Data classes
    "CreatorConfig",
    "VolumeTargets",
    # Constants
    "TIER_PPVS",
    "BUMP_MATRIX",
    "VALID_PAGE_TYPES",
    "VALID_SUB_TYPES",
    "BUMP_RATIO_TOLERANCE",
    # Type aliases
    "PageType",
    "SubType",
    "TierName",
    # Main functions
    "get_volume_tier",
    "calculate_volume_targets",
    "validate_bump_ratio",
    # Utility functions
    "get_tier_for_fan_count",
    "get_all_bump_ranges",
]
