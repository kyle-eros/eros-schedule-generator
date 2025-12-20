"""
Bump multiplier calculation for engagement volume optimization.

Calculates bump multipliers based on creator's content category to optimize
engagement volume. Different content categories attract different audience
engagement levels, requiring scaled bump frequencies.

Business Rules:
    - LOW tier (0-999 fans): Full bump multiplier applied to drive conversions
    - MID/HIGH/ULTRA tiers: Multiplier capped at 1.5x to prevent over-engagement
    - Followup volume: 80% of PPVs get followups, max 5/day

Content Categories:
    - lifestyle: 1.0x (baseline - GFE, personal connection focus)
    - softcore: 1.5x (suggestive content - moderate engagement)
    - amateur: 2.0x (authentic appeal - higher engagement)
    - explicit: 2.67x (commercial explicit - maximum engagement)

Usage:
    from python.volume.bump_multiplier import (
        calculate_bump_multiplier,
        calculate_followup_volume,
        apply_bump_to_engagement,
    )

    # Calculate bump multiplier for a creator
    result = calculate_bump_multiplier(
        content_category="amateur",
        tier=VolumeTier.LOW,
        page_type="paid"
    )
    print(f"Multiplier: {result.multiplier}")  # 2.0

    # Apply to engagement volume
    adjusted = apply_bump_to_engagement(
        base_engagement=4,
        bump_multiplier=result.multiplier,
        max_engagement=12
    )
    print(f"Adjusted engagement: {adjusted}")  # 8
"""

import sqlite3
from dataclasses import dataclass
from typing import Optional

from python.logging_config import get_logger
from python.models.volume import VolumeTier

logger = get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Bump multipliers by content category
# Higher multipliers indicate content types that benefit from more frequent bumps
BUMP_MULTIPLIERS: dict[str, float] = {
    "lifestyle": 1.0,   # GFE, personal connection focus - baseline
    "softcore": 1.5,    # Suggestive content - moderate engagement
    "amateur": 2.0,     # Authentic appeal - higher engagement
    "explicit": 2.67,   # Commercial explicit - maximum engagement
}

# Default content category when not specified or not found
DEFAULT_CONTENT_CATEGORY: str = "softcore"

# Base followup rate (80% of PPVs get followups)
FOLLOWUP_BASE_RATE: float = 0.80

# Maximum followups allowed per day (hard cap)
MAX_FOLLOWUPS_PER_DAY: int = 5

# Multiplier cap for higher tiers to prevent over-engagement
HIGH_TIER_MULTIPLIER_CAP: float = 1.5

# Page type bonus for free pages (slight engagement boost)
FREE_PAGE_BUMP_BONUS: float = 0.1


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BumpMultiplierResult:
    """Result of bump multiplier calculation.

    Contains the calculated multiplier along with metadata about
    how it was determined and whether any capping was applied.

    Attributes:
        multiplier: Final bump multiplier to apply (after capping if needed).
        content_category: Content category used for calculation.
        tier: Volume tier that influenced capping behavior.
        source: How the content category was determined:
            - 'database': Retrieved from creators table
            - 'default': Used default value (softcore)
            - 'page_type_fallback': Fallback with page type adjustment
        capped: True if multiplier was capped for higher tiers.
        original_multiplier: Multiplier value before any capping was applied.
    """

    multiplier: float
    content_category: str
    tier: VolumeTier
    source: str
    capped: bool = False
    original_multiplier: float = 1.0

    @property
    def was_modified(self) -> bool:
        """Returns True if multiplier differs from original."""
        return abs(self.multiplier - self.original_multiplier) > 0.001


@dataclass
class FollowupVolumeResult:
    """Result of followup volume calculation.

    Contains the calculated number of followups along with metadata
    about the calculation and any limits that were applied.

    Attributes:
        followup_count: Number of followups to schedule.
        ppv_count: Number of PPV sends the followups are based on.
        followup_rate: Rate used for calculation (default 0.80).
        limited_by_cap: True if result was limited by MAX_FOLLOWUPS_PER_DAY.
        confidence_adjusted: True if confidence score reduced the count.
    """

    followup_count: int
    ppv_count: int
    followup_rate: float
    limited_by_cap: bool = False
    confidence_adjusted: bool = False

    @property
    def actual_rate(self) -> float:
        """Calculate the actual followup rate achieved."""
        if self.ppv_count == 0:
            return 0.0
        return self.followup_count / self.ppv_count


# =============================================================================
# Core Functions
# =============================================================================

def calculate_bump_multiplier(
    content_category: str,
    tier: VolumeTier,
    page_type: str = "paid",
) -> BumpMultiplierResult:
    """Calculate bump multiplier based on content category and tier.

    The bump multiplier scales engagement volume based on the creator's
    content category. Different content types attract different audience
    engagement levels, requiring adjusted bump frequencies.

    At LOW tier, the full multiplier is applied to drive conversions.
    At higher tiers, the multiplier is capped at 1.5x to prevent
    over-engagement that could lead to subscriber fatigue.

    Args:
        content_category: One of 'lifestyle', 'softcore', 'amateur', 'explicit'.
            Invalid categories fall back to DEFAULT_CONTENT_CATEGORY.
        tier: VolumeTier enum (LOW, MID, HIGH, ULTRA).
        page_type: 'paid' or 'free'. Free pages get a slight bonus.

    Returns:
        BumpMultiplierResult with multiplier and calculation metadata.

    Examples:
        >>> result = calculate_bump_multiplier("amateur", VolumeTier.LOW, "paid")
        >>> result.multiplier
        2.0
        >>> result.capped
        False

        >>> result = calculate_bump_multiplier("explicit", VolumeTier.HIGH, "paid")
        >>> result.multiplier
        1.5
        >>> result.capped
        True
        >>> result.original_multiplier
        2.67
    """
    # Normalize and validate content category
    normalized_category = content_category.lower().strip() if content_category else ""
    source = "database"

    if normalized_category not in BUMP_MULTIPLIERS:
        logger.warning(
            "Unknown content category, using default",
            extra={
                "provided_category": content_category,
                "default_category": DEFAULT_CONTENT_CATEGORY,
            }
        )
        normalized_category = DEFAULT_CONTENT_CATEGORY
        source = "default"

    # Get base multiplier for content category
    original_multiplier = BUMP_MULTIPLIERS[normalized_category]
    multiplier = original_multiplier

    # Apply page type bonus for free pages
    if page_type == "free":
        multiplier += FREE_PAGE_BUMP_BONUS
        if source == "database":
            source = "page_type_fallback"

    # Apply tier-based capping
    capped = False
    if tier != VolumeTier.LOW and multiplier > HIGH_TIER_MULTIPLIER_CAP:
        logger.debug(
            "Capping bump multiplier for non-LOW tier",
            extra={
                "original_multiplier": multiplier,
                "capped_multiplier": HIGH_TIER_MULTIPLIER_CAP,
                "tier": tier.value,
                "content_category": normalized_category,
            }
        )
        multiplier = HIGH_TIER_MULTIPLIER_CAP
        capped = True

    return BumpMultiplierResult(
        multiplier=multiplier,
        content_category=normalized_category,
        tier=tier,
        source=source,
        capped=capped,
        original_multiplier=original_multiplier,
    )


def calculate_followup_volume(
    ppv_count: int,
    tier_max: int = 5,
    confidence_score: float = 1.0,
) -> FollowupVolumeResult:
    """Scale followup volume with actual PPV count.

    Calculates the number of followup messages to schedule based on
    the number of PPV sends. The base rate is 80% (4 followups per 5 PPVs),
    with caps applied for tier limits and daily maximums.

    Formula: min(round(ppv_count * 0.80), tier_max, MAX_FOLLOWUPS_PER_DAY)

    Low confidence scores reduce followup volume proportionally to
    prevent aggressive followup behavior when data reliability is low.

    Args:
        ppv_count: Number of PPV sends scheduled for the day.
        tier_max: Maximum followups allowed by the volume tier (default 5).
        confidence_score: Data confidence (0.0-1.0). Lower values reduce
            followup count proportionally.

    Returns:
        FollowupVolumeResult with followup_count and calculation metadata.

    Examples:
        >>> result = calculate_followup_volume(4, tier_max=5, confidence_score=1.0)
        >>> result.followup_count
        3
        >>> result.followup_rate
        0.8

        >>> result = calculate_followup_volume(10, tier_max=5, confidence_score=1.0)
        >>> result.followup_count
        5
        >>> result.limited_by_cap
        True

        >>> result = calculate_followup_volume(4, tier_max=5, confidence_score=0.5)
        >>> result.followup_count
        2
        >>> result.confidence_adjusted
        True
    """
    if ppv_count <= 0:
        return FollowupVolumeResult(
            followup_count=0,
            ppv_count=0,
            followup_rate=FOLLOWUP_BASE_RATE,
            limited_by_cap=False,
            confidence_adjusted=False,
        )

    # Clamp confidence score to valid range
    confidence_score = max(0.0, min(1.0, confidence_score))

    # Calculate base followup count
    base_count = round(ppv_count * FOLLOWUP_BASE_RATE)

    # Apply confidence adjustment
    confidence_adjusted = False
    if confidence_score < 1.0:
        adjusted_count = round(base_count * confidence_score)
        if adjusted_count < base_count:
            confidence_adjusted = True
            base_count = adjusted_count

    # Apply caps
    effective_cap = min(tier_max, MAX_FOLLOWUPS_PER_DAY)
    limited_by_cap = base_count > effective_cap
    final_count = min(base_count, effective_cap)

    logger.debug(
        "Calculated followup volume",
        extra={
            "ppv_count": ppv_count,
            "base_count": round(ppv_count * FOLLOWUP_BASE_RATE),
            "confidence_score": confidence_score,
            "confidence_adjusted": confidence_adjusted,
            "final_count": final_count,
            "limited_by_cap": limited_by_cap,
        }
    )

    return FollowupVolumeResult(
        followup_count=final_count,
        ppv_count=ppv_count,
        followup_rate=FOLLOWUP_BASE_RATE,
        limited_by_cap=limited_by_cap,
        confidence_adjusted=confidence_adjusted,
    )


def get_creator_content_category(
    conn: sqlite3.Connection,
    creator_id: str,
) -> str:
    """Fetch content_category from creators table.

    Retrieves the content_category for a creator from the database.
    Falls back to DEFAULT_CONTENT_CATEGORY ('softcore') if the creator
    is not found or the category is NULL.

    Args:
        conn: SQLite database connection.
        creator_id: The creator_id or page_name to look up.

    Returns:
        Content category string ('lifestyle', 'softcore', 'amateur', 'explicit').
        Returns DEFAULT_CONTENT_CATEGORY if not found.

    Raises:
        sqlite3.Error: If database query fails (logged but re-raised).

    Examples:
        >>> conn = sqlite3.connect("database/eros_sd_main.db")
        >>> category = get_creator_content_category(conn, "creator_123")
        >>> category
        'amateur'
    """
    query = """
        SELECT content_category
        FROM creators
        WHERE creator_id = ? OR page_name = ?
        LIMIT 1
    """

    try:
        cursor = conn.execute(query, (creator_id, creator_id))
        row = cursor.fetchone()

        if row is None or row[0] is None:
            logger.info(
                "Content category not found, using default",
                extra={
                    "creator_id": creator_id,
                    "default_category": DEFAULT_CONTENT_CATEGORY,
                }
            )
            return DEFAULT_CONTENT_CATEGORY

        category = row[0].lower().strip()

        # Validate category is known
        if category not in BUMP_MULTIPLIERS:
            logger.warning(
                "Unknown content category in database, using default",
                extra={
                    "creator_id": creator_id,
                    "database_category": row[0],
                    "default_category": DEFAULT_CONTENT_CATEGORY,
                }
            )
            return DEFAULT_CONTENT_CATEGORY

        return category

    except sqlite3.Error as e:
        logger.error(
            "Failed to fetch content category from database",
            extra={
                "creator_id": creator_id,
                "error": str(e),
            }
        )
        raise


def apply_bump_to_engagement(
    base_engagement: int,
    bump_multiplier: float,
    max_engagement: int = 12,
) -> int:
    """Apply bump multiplier to base engagement volume.

    Scales the base engagement volume by the bump multiplier and
    clamps the result to the maximum allowed engagement.

    Args:
        base_engagement: Base engagement sends per day from tier config.
        bump_multiplier: Multiplier from calculate_bump_multiplier().
        max_engagement: Maximum engagement sends allowed (default 12).

    Returns:
        Adjusted engagement volume, clamped to max_engagement.

    Examples:
        >>> apply_bump_to_engagement(4, 2.0, max_engagement=12)
        8

        >>> apply_bump_to_engagement(6, 2.67, max_engagement=12)
        12

        >>> apply_bump_to_engagement(3, 1.5, max_engagement=12)
        5
    """
    if base_engagement <= 0 or bump_multiplier <= 0:
        return 0

    adjusted = round(base_engagement * bump_multiplier)
    result = min(adjusted, max_engagement)

    if adjusted > max_engagement:
        logger.debug(
            "Engagement clamped to maximum",
            extra={
                "base_engagement": base_engagement,
                "bump_multiplier": bump_multiplier,
                "calculated": adjusted,
                "clamped_to": max_engagement,
            }
        )

    return result


def get_bump_multiplier_for_category(content_category: str) -> float:
    """Get the raw bump multiplier for a content category.

    Simple lookup function that returns the multiplier without
    any tier-based capping. Useful for display or configuration.

    Args:
        content_category: One of 'lifestyle', 'softcore', 'amateur', 'explicit'.

    Returns:
        Bump multiplier value. Returns 1.5 (softcore) for unknown categories.

    Examples:
        >>> get_bump_multiplier_for_category("explicit")
        2.67
        >>> get_bump_multiplier_for_category("unknown")
        1.5
    """
    normalized = content_category.lower().strip() if content_category else ""
    return BUMP_MULTIPLIERS.get(normalized, BUMP_MULTIPLIERS[DEFAULT_CONTENT_CATEGORY])


def get_all_content_categories() -> list[str]:
    """Get list of all valid content categories.

    Returns:
        List of content category names in order of multiplier value.

    Examples:
        >>> get_all_content_categories()
        ['lifestyle', 'softcore', 'amateur', 'explicit']
    """
    return sorted(BUMP_MULTIPLIERS.keys(), key=lambda k: BUMP_MULTIPLIERS[k])


def calculate_effective_engagement(
    base_engagement: int,
    content_category: str,
    tier: VolumeTier,
    page_type: str = "paid",
    max_engagement: int = 12,
) -> tuple[int, BumpMultiplierResult]:
    """Calculate effective engagement volume with full context.

    Convenience function that combines bump multiplier calculation
    and application in a single call.

    Args:
        base_engagement: Base engagement sends per day from tier config.
        content_category: One of 'lifestyle', 'softcore', 'amateur', 'explicit'.
        tier: VolumeTier enum (LOW, MID, HIGH, ULTRA).
        page_type: 'paid' or 'free'.
        max_engagement: Maximum engagement sends allowed (default 12).

    Returns:
        Tuple of (effective_engagement, BumpMultiplierResult).

    Examples:
        >>> engagement, result = calculate_effective_engagement(
        ...     base_engagement=4,
        ...     content_category="amateur",
        ...     tier=VolumeTier.LOW,
        ...     page_type="paid"
        ... )
        >>> engagement
        8
        >>> result.multiplier
        2.0
    """
    bump_result = calculate_bump_multiplier(
        content_category=content_category,
        tier=tier,
        page_type=page_type,
    )

    effective = apply_bump_to_engagement(
        base_engagement=base_engagement,
        bump_multiplier=bump_result.multiplier,
        max_engagement=max_engagement,
    )

    return effective, bump_result


# =============================================================================
# Export
# =============================================================================

__all__ = [
    # Constants
    "BUMP_MULTIPLIERS",
    "DEFAULT_CONTENT_CATEGORY",
    "FOLLOWUP_BASE_RATE",
    "MAX_FOLLOWUPS_PER_DAY",
    "HIGH_TIER_MULTIPLIER_CAP",
    "FREE_PAGE_BUMP_BONUS",
    # Data classes
    "BumpMultiplierResult",
    "FollowupVolumeResult",
    # Core functions
    "calculate_bump_multiplier",
    "calculate_followup_volume",
    "get_creator_content_category",
    "apply_bump_to_engagement",
    # Utility functions
    "get_bump_multiplier_for_category",
    "get_all_content_categories",
    "calculate_effective_engagement",
]
