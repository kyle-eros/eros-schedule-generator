#!/usr/bin/env python3
"""
Weight Calculation Module - Pool-based earnings-first weight calculation with payday awareness.

This module provides the canonical implementation of the pool-based
weight calculation formula used throughout the EROS Schedule Generator.

Formula:
    Weight = Earnings(55%) + Freshness(15%) + Persona(15%) + Discovery(10%) + Payday(5%)

The weight calculation varies by pool type:
    - PROVEN: Uses creator_avg_earnings at full weight (proven performers)
    - GLOBAL_EARNER: Uses global_avg_earnings with 20% discount (untested for creator)
    - DISCOVERY: Uses content type average with performance proxy and discovery bonus

This tiered approach ensures:
    1. Proven performers for the creator get priority
    2. Global earners are given reasonable weight with appropriate discounting
    3. Discovery slots encourage testing new captions with potential

Usage:
    from weights import (
        calculate_weight,
        calculate_discovery_bonus,
        calculate_payday_multiplier,
        get_payday_score,
        is_high_payday_multiplier,
        is_mid_cycle,
        get_effective_earnings_proxy,
        EARNINGS_WEIGHT,
        FRESHNESS_WEIGHT,
        PERSONA_WEIGHT,
        DISCOVERY_BONUS_WEIGHT,
        PAYDAY_WEIGHT,
    )

    weight = calculate_weight(
        caption,
        pool_type='PROVEN',
        content_type_avg_earnings=45.0,
        max_earnings=500.0,
        persona_boost=1.2,
        target_date=date(2025, 1, 15),  # Optional payday awareness
    )
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta
from math import exp, log1p
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from models import PatternProfile, ScoredCaption

# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# WEIGHT CONSTANTS
# =============================================================================

# Primary weight distribution (updated formula with payday factor)
EARNINGS_WEIGHT: float = 0.55
"""
Earnings component weight (55% of total).

This is the primary factor in caption selection. The earnings value used
depends on the pool type:
- PROVEN: creator_avg_earnings at full value
- GLOBAL_EARNER: global_avg_earnings * 0.80 (20% discount)
- DISCOVERY: content_type_avg_earnings * performance_percentile * 0.70
"""

FRESHNESS_WEIGHT: float = 0.15
"""
Freshness component weight (15% of total).

Freshness score (0-100) measures how recently a caption was used.
Higher freshness means the caption hasn't been used recently and
won't fatigue the audience.
"""

PERSONA_WEIGHT: float = 0.15
"""
Persona matching component weight (15% of total).

Persona boost (1.0-1.4) indicates how well the caption matches
the creator's voice profile. Converted to 0-6 point range.
1.0 = no match (0 points), 1.4 = full match (6 points)
"""

DISCOVERY_BONUS_WEIGHT: float = 0.10
"""
Discovery bonus weight (10% of total).

Only applies to DISCOVERY pool captions. Rewards:
- High global earners untested for this creator (up to +5 points)
- Universal captions (+1.5 points)
- High performance score (>=70: +1.0, >=50: +0.5)
"""

PAYDAY_WEIGHT: float = 0.05
"""
Payday proximity weight (5% of total).

Revenue-optimized multiplier based on proximity to paydays (1st and 15th).
- Payday itself: 1.35x multiplier
- Day before/after: 1.25-1.30x
- 2 days away: 1.15x
- Mid-cycle (5+ days away): 0.90x

Uses exponential decay from nearest payday for smooth weighting.
"""

# Payday multiplier constants
PAYDAY_MULTIPLIER_MAX: float = 1.35
"""Maximum multiplier on payday itself."""

PAYDAY_MULTIPLIER_MIN: float = 0.90
"""Minimum multiplier at mid-cycle (furthest from paydays)."""

PAYDAY_DECAY_RATE: float = 0.35
"""Exponential decay rate - higher = faster drop-off from payday."""

# Pool type constants
POOL_PROVEN: str = "PROVEN"
"""Captions with creator-specific earnings data (proven performers)."""

POOL_GLOBAL_EARNER: str = "GLOBAL_EARNER"
"""Captions with global earnings but no creator-specific data."""

POOL_DISCOVERY: str = "DISCOVERY"
"""Captions with no earnings data - discovery candidates."""

# Discount factors for different pool types
GLOBAL_EARNER_DISCOUNT: float = 0.80
"""
Discount factor for global earners (20% penalty).

Global earnings are discounted because they don't reflect
this specific creator's audience preferences.
"""

DISCOVERY_DISCOUNT: float = 0.70
"""
Discount factor for discovery pool (30% penalty).

Discovery captions use proxy earnings with higher uncertainty,
so they receive a larger discount.
"""

DISCOVERY_EFFECTIVE_EARNINGS_BASE: float = 0.50
"""
Base multiplier for discovery effective earnings calculation.

Used in: content_type_avg * (0.5 + performance_score/200) * 0.70
"""

DISCOVERY_EFFECTIVE_EARNINGS_SCALE: float = 200.0
"""
Scale factor for performance score in discovery earnings calculation.

Dividing by 200 maps 0-100 performance score to 0-0.5 additional multiplier.
"""

# Discovery bonus points
DISCOVERY_BONUS_MAX_GLOBAL_POINTS: float = 5.0
"""Maximum bonus points for high global earners in discovery pool."""

DISCOVERY_BONUS_UNIVERSAL_POINTS: float = 1.5
"""Bonus points for universal captions (work across creators)."""

DISCOVERY_BONUS_HIGH_PERF_POINTS: float = 1.0
"""Bonus points for captions with performance_score >= 70."""

DISCOVERY_BONUS_MED_PERF_POINTS: float = 0.5
"""Bonus points for captions with performance_score >= 50."""

DISCOVERY_BONUS_HIGH_PERF_THRESHOLD: float = 70.0
"""Performance score threshold for high performance bonus."""

DISCOVERY_BONUS_MED_PERF_THRESHOLD: float = 50.0
"""Performance score threshold for medium performance bonus."""

# Minimum weight to ensure all captions have non-zero probability
MIN_WEIGHT: float = 0.001
"""Minimum weight to ensure non-zero selection probability in Vose Alias."""

# Persona boost range
PERSONA_BOOST_MIN: float = 1.0
"""Minimum persona boost (no match)."""

PERSONA_BOOST_MAX: float = 1.4
"""Maximum persona boost (full match: tone + emoji + slang)."""

PERSONA_SCALE_FACTOR: float = 100.0
"""Scale factor to convert persona boost (0-0.4) to points (0-40 before weight)."""


# =============================================================================
# PATTERN-BASED WEIGHT CONSTANTS (New Weight System)
# =============================================================================

# New weight formula constants (must sum to 1.0)
PATTERN_WEIGHT: float = 0.40
"""
Pattern score component weight (40% of total).

Pattern scores predict caption performance based on historical data
for similar content_type + tone + hook_type combinations.
"""

NEVER_USED_WEIGHT: float = 0.25
"""
Never-used bonus component weight (25% of total).

Heavily rewards captions that have never been used for this creator,
ensuring fresh content gets priority in selection.
"""

NEW_PERSONA_WEIGHT: float = 0.15
"""
Persona matching component weight (15% of total) in new formula.

Same as existing PERSONA_WEIGHT but explicitly named for new system.
Rewards captions that match the creator's voice profile.
"""

FRESHNESS_BONUS_WEIGHT: float = 0.10
"""
Freshness bonus component weight (10% of total).

Additional bonus for fresh captions beyond the never-used tier.
Rewards captions with high freshness scores.
"""

EXPLORATION_WEIGHT: float = 0.10
"""
Exploration component weight (10% of total).

Promotes diversity by boosting captions with unused attributes
(hook_type, tone, content_type) within the current schedule.
"""

# Pattern scoring constants
BASE_PATTERN_SCORE: float = 30.0
"""Default pattern score when no pattern data is available."""

MAX_PATTERN_SCORE: float = 100.0
"""Maximum possible pattern score."""

# Freshness tier multipliers
FRESHNESS_MULTIPLIERS: dict[str, float] = {
    "never_used": 1.5,
    "fresh": 1.0,
    "excluded": 0.0,
}
"""
Multipliers for freshness tiers in caption selection.

- never_used: 1.5x bonus for captions never used on this page
- fresh: 1.0x standard weight for fresh captions
- excluded: 0.0x (should be filtered out before selection)
"""

# Exploration bonus constants
EXPLORATION_HOOK_TYPE_BONUS: float = 20.0
"""Points added when hook_type is unused in current schedule."""

EXPLORATION_TONE_BONUS: float = 15.0
"""Points added when tone is unused in current schedule."""

EXPLORATION_CONTENT_TYPE_BONUS: float = 10.0
"""Points added when content_type is under-represented in schedule."""

EXPLORATION_BASE_INVERSE: float = 50.0
"""Base value for inverse pattern score calculation in exploration."""

MAX_EXPLORATION_SCORE: float = 100.0
"""Maximum exploration weight value."""


# =============================================================================
# CAPTION PROTOCOL
# =============================================================================


@runtime_checkable
class CaptionLike(Protocol):
    """
    Protocol defining the required attributes for weight calculation.

    This allows calculate_weight to work with Caption classes from both
    generate_schedule.py and select_captions.py without circular imports.

    All attributes are required for the new pool-based weight system.
    """

    @property
    def creator_avg_earnings(self) -> float | None:
        """
        Creator-specific average earnings for this caption.

        Source: caption_creator_performance.avg_earnings
        Used for PROVEN pool captions at full weight.
        """
        ...

    @property
    def global_avg_earnings(self) -> float | None:
        """
        Global (cross-creator) average earnings for this caption.

        Source: caption_bank.avg_earnings
        Used for GLOBAL_EARNER pool with 20% discount.
        """
        ...

    @property
    def performance_score(self) -> float:
        """
        Performance score (0-100) used for discovery pool calculations.

        Source: caption_bank.performance_score
        Higher scores indicate better expected performance.
        """
        ...

    @property
    def freshness_score(self) -> float:
        """
        Freshness score (0-100) indicating recency of use.

        Source: caption_bank.freshness_score
        Higher scores mean less recent use (more fresh).
        """
        ...

    @property
    def is_universal(self) -> bool:
        """
        Whether this is a universal caption that works across creators.

        Source: caption_bank.is_universal
        Universal captions get bonus points in discovery pool.
        """
        ...


# =============================================================================
# EARNINGS PROXY CALCULATION
# =============================================================================


def get_effective_earnings_proxy(
    caption: CaptionLike,
    pool_type: str,
    content_type_avg_earnings: float,
) -> float:
    """
    Calculate effective earnings proxy based on pool type.

    This function returns the earnings value to use for weight calculation,
    applying appropriate discounts based on data certainty.

    Args:
        caption: Caption-like object with earnings attributes.
        pool_type: One of 'PROVEN', 'GLOBAL_EARNER', or 'DISCOVERY'.
        content_type_avg_earnings: Average earnings for this content type.
            Used as baseline for DISCOVERY pool calculations.

    Returns:
        Effective earnings value (discounted as appropriate for pool type).

    Raises:
        ValueError: If pool_type is not one of 'PROVEN', 'GLOBAL_EARNER', or 'DISCOVERY'.

    Calculation by pool type:
        - PROVEN: creator_avg_earnings directly (no discount)
        - GLOBAL_EARNER: global_avg_earnings * 0.80 (20% discount)
        - DISCOVERY: content_type_avg * (0.5 + performance_score/200) * 0.70

    Example:
        >>> proxy = get_effective_earnings_proxy(
        ...     caption, 'GLOBAL_EARNER', content_type_avg_earnings=50.0
        ... )
        >>> # Returns global_avg_earnings * 0.80
    """
    if pool_type == POOL_PROVEN:
        # PROVEN pool: use creator-specific earnings at full weight
        earnings = caption.creator_avg_earnings
        return earnings if earnings is not None and earnings > 0 else 0.0

    elif pool_type == POOL_GLOBAL_EARNER:
        # GLOBAL_EARNER pool: use global earnings with 20% discount
        earnings = caption.global_avg_earnings
        if earnings is not None and earnings > 0:
            return earnings * GLOBAL_EARNER_DISCOUNT
        return 0.0

    elif pool_type == POOL_DISCOVERY:
        # DISCOVERY pool: use content type average with performance scaling
        # Formula: content_type_avg * (0.5 + performance_score/200) * 0.70
        performance_multiplier = (
            DISCOVERY_EFFECTIVE_EARNINGS_BASE
            + caption.performance_score / DISCOVERY_EFFECTIVE_EARNINGS_SCALE
        )
        return content_type_avg_earnings * performance_multiplier * DISCOVERY_DISCOUNT

    else:
        raise ValueError(
            f"Unknown pool_type: {pool_type}. "
            f"Must be one of: {POOL_PROVEN}, {POOL_GLOBAL_EARNER}, {POOL_DISCOVERY}"
        )


# =============================================================================
# DISCOVERY BONUS CALCULATION
# =============================================================================


def calculate_discovery_bonus(
    caption: CaptionLike,
    max_global_earnings: float,
) -> float:
    """
    Calculate discovery bonus for DISCOVERY pool captions.

    This bonus rewards captions that have potential but haven't been
    tested for this creator. It encourages exploration of new content.

    Args:
        caption: Caption-like object with performance attributes.
        max_global_earnings: Maximum global earnings in the dataset.
            Used to calculate percentile for global earner bonus.

    Returns:
        Discovery bonus points (0-7.5 range typically).

    Bonus components:
        1. High global earners untested for this creator: up to +5 points
           (based on global_avg_earnings percentile)
        2. Universal captions: +1.5 points
        3. High performance score (>=70): +1.0 points
        4. Medium performance score (>=50): +0.5 points

    Example:
        >>> bonus = calculate_discovery_bonus(caption, max_global_earnings=500.0)
        >>> # Returns sum of applicable bonus points
    """
    bonus = 0.0

    # Component 1: Global earner bonus (up to 5 points based on percentile)
    global_earnings = caption.global_avg_earnings
    if global_earnings is not None and global_earnings > 0 and max_global_earnings > 0:
        # Calculate percentile using log scale for better distribution
        earnings_percentile = log1p(global_earnings) / log1p(max_global_earnings)
        bonus += earnings_percentile * DISCOVERY_BONUS_MAX_GLOBAL_POINTS

    # Component 2: Universal caption bonus
    if caption.is_universal:
        bonus += DISCOVERY_BONUS_UNIVERSAL_POINTS

    # Component 3: Performance score bonus (mutually exclusive tiers)
    if caption.performance_score >= DISCOVERY_BONUS_HIGH_PERF_THRESHOLD:
        bonus += DISCOVERY_BONUS_HIGH_PERF_POINTS
    elif caption.performance_score >= DISCOVERY_BONUS_MED_PERF_THRESHOLD:
        bonus += DISCOVERY_BONUS_MED_PERF_POINTS

    return bonus


# =============================================================================
# PAYDAY PROXIMITY CALCULATION
# =============================================================================


def calculate_payday_multiplier(target_date: date) -> float:
    """
    Calculate revenue multiplier based on proximity to paydays (1st and 15th).

    Paydays are when fans receive income and are more likely to spend on PPV.
    This function returns a multiplier to boost content scheduling weight
    on and around paydays.

    Args:
        target_date: The date to calculate the multiplier for.

    Returns:
        Revenue multiplier (0.90 to 1.35):
        - 1.35x on payday itself (1st or 15th)
        - 1.25-1.30x day before/after payday
        - 1.15x 2 days from payday
        - 0.90x at mid-cycle (5+ days from nearest payday)

    Uses exponential decay from nearest payday for smooth weighting.
    The formula: multiplier = min + (max - min) * exp(-decay_rate * days_away)

    Examples:
        >>> from datetime import date
        >>> calculate_payday_multiplier(date(2025, 1, 1))   # Payday
        1.35
        >>> calculate_payday_multiplier(date(2025, 1, 2))   # Day after
        1.2459...  # ~1.25
        >>> calculate_payday_multiplier(date(2025, 1, 8))   # Mid-cycle
        0.9034...  # ~0.90
        >>> calculate_payday_multiplier(date(2025, 1, 15))  # Payday
        1.35
    """
    day = target_date.day
    days_in_month = _get_days_in_month(target_date)

    # Calculate distance to nearest payday (1st or 15th)
    # Distance to 1st (can be forward or backward depending on day)
    distance_to_1st = min(day - 1, days_in_month - day + 1)

    # Distance to 15th
    distance_to_15th = abs(day - 15)

    # Use the nearest payday
    days_from_payday = min(distance_to_1st, distance_to_15th)

    # Apply exponential decay: multiplier = min + (max - min) * e^(-rate * days)
    # This creates smooth curve from 1.35 (payday) to 0.90 (mid-cycle)
    multiplier = PAYDAY_MULTIPLIER_MIN + (PAYDAY_MULTIPLIER_MAX - PAYDAY_MULTIPLIER_MIN) * exp(
        -PAYDAY_DECAY_RATE * days_from_payday
    )

    return multiplier


def _get_days_in_month(d: date) -> int:
    """Get number of days in the month for the given date."""
    # Move to next month, then back one day
    if d.month == 12:
        next_month = date(d.year + 1, 1, 1)
    else:
        next_month = date(d.year, d.month + 1, 1)
    last_day = next_month - timedelta(days=1)
    return last_day.day


def get_payday_score(target_date: date) -> float:
    """
    Convert payday multiplier to a 0-100 score for weight calculation.

    This normalizes the multiplier range (0.90-1.35) to a 0-100 scale
    suitable for use in the weight formula.

    Args:
        target_date: The date to score.

    Returns:
        Payday score (0-100):
        - 100 on payday itself
        - 78 one day from payday
        - 56 two days from payday
        - 0 at mid-cycle

    Example:
        >>> get_payday_score(date(2025, 1, 1))  # Payday
        100.0
        >>> get_payday_score(date(2025, 1, 8))  # Mid-cycle
        0.76...  # Nearly 0
    """
    multiplier = calculate_payday_multiplier(target_date)

    # Normalize to 0-100 scale
    # (multiplier - min) / (max - min) * 100
    score = (
        (multiplier - PAYDAY_MULTIPLIER_MIN) / (PAYDAY_MULTIPLIER_MAX - PAYDAY_MULTIPLIER_MIN) * 100
    )

    return max(0.0, min(100.0, score))


def is_high_payday_multiplier(target_date: date, threshold: float = 1.15) -> bool:
    """
    Check if the date has a high payday multiplier.

    Useful for determining if premium content should be prioritized.

    Args:
        target_date: The date to check.
        threshold: Multiplier threshold (default 1.15).

    Returns:
        True if multiplier >= threshold.

    Example:
        >>> is_high_payday_multiplier(date(2025, 1, 1))  # Payday
        True
        >>> is_high_payday_multiplier(date(2025, 1, 8))  # Mid-cycle
        False
    """
    return calculate_payday_multiplier(target_date) >= threshold


def is_mid_cycle(target_date: date, threshold: float = 0.95) -> bool:
    """
    Check if the date is in mid-cycle (far from paydays).

    Useful for determining if premium content should be deprioritized.

    Args:
        target_date: The date to check.
        threshold: Multiplier threshold (default 0.95).

    Returns:
        True if multiplier <= threshold.

    Example:
        >>> is_mid_cycle(date(2025, 1, 1))  # Payday
        False
        >>> is_mid_cycle(date(2025, 1, 8))  # Mid-cycle
        True
    """
    return calculate_payday_multiplier(target_date) <= threshold


# =============================================================================
# WEIGHT CALCULATION
# =============================================================================


def calculate_weight(
    caption: CaptionLike,
    pool_type: str,
    content_type_avg_earnings: float,
    max_earnings: float,
    persona_boost: float = 1.0,
    target_date: date | None = None,
) -> float:
    """
    Calculate weight using pool-based earnings methodology with payday awareness.

    This is the canonical weight calculation formula for the EROS Schedule
    Generator. It uses different earnings sources based on pool type and
    applies appropriate discounts for data uncertainty.

    Formula:
        Weight = Earnings(55%) + Freshness(15%) + Persona(15%) + Discovery(10%) + Payday(5%)

    Args:
        caption: Caption-like object with required earnings/performance attributes.
            Must have: creator_avg_earnings, global_avg_earnings,
            performance_score, freshness_score, is_universal
        pool_type: One of 'PROVEN', 'GLOBAL_EARNER', or 'DISCOVERY'.
            Determines which earnings source and discount to use.
        content_type_avg_earnings: Expected earnings for this content type.
            Used as baseline for DISCOVERY pool calculations.
        max_earnings: Maximum earnings in dataset for normalization.
            Should be pre-calculated from all eligible captions.
        persona_boost: Persona match boost factor (1.0-1.4).
            1.0 = no match, 1.4 = full match (tone + emoji + slang)
        target_date: Optional date for payday proximity scoring.
            If None, payday component is set to 0 (backwards compatible).

    Returns:
        Final selection weight (minimum 0.001 to ensure non-zero probability).

    Earnings Component (55%):
        - PROVEN: creator_avg_earnings at full weight
        - GLOBAL_EARNER: global_avg_earnings * 0.80 (20% discount)
        - DISCOVERY: content_type_avg * performance_percentile * 0.70

    Freshness Component (15%):
        freshness_score * 0.15 (0-15 point range)

    Persona Component (15%):
        (persona_boost - 1.0) * 100 * 0.15 (0-6 point range)

    Discovery Bonus (10%):
        Only for DISCOVERY pool - see calculate_discovery_bonus()

    Payday Component (5%):
        payday_score * 0.05 (0-5 point range)
        Higher on/near 1st and 15th of month, lower mid-cycle.

    Example:
        >>> from datetime import date
        >>> caption = SomeCaption(
        ...     creator_avg_earnings=150.0,
        ...     global_avg_earnings=75.0,
        ...     performance_score=80.0,
        ...     freshness_score=90.0,
        ...     is_universal=False,
        ... )
        >>> weight = calculate_weight(
        ...     caption,
        ...     pool_type='PROVEN',
        ...     content_type_avg_earnings=50.0,
        ...     max_earnings=500.0,
        ...     persona_boost=1.2,
        ...     target_date=date(2025, 1, 15),  # Payday!
        ... )
        >>> print(f"Weight: {weight:.2f}")
    """
    # Step 1: Get effective earnings based on pool type
    effective_earnings = _get_pool_earnings(caption, pool_type, content_type_avg_earnings)

    # Step 2: Normalize earnings to 0-100 scale using log scale
    # Log scale handles outliers gracefully (e.g., $20,733 max vs $38 median)
    if max_earnings > 0 and effective_earnings > 0:
        earnings_normalized = min(100, (log1p(effective_earnings) / log1p(max_earnings)) * 100)
    else:
        earnings_normalized = 0.0

    # Step 3: Calculate weighted components
    earnings_component = earnings_normalized * EARNINGS_WEIGHT
    freshness_component = caption.freshness_score * FRESHNESS_WEIGHT
    persona_component = (persona_boost - PERSONA_BOOST_MIN) * PERSONA_SCALE_FACTOR * PERSONA_WEIGHT

    # Step 4: Calculate discovery bonus (only for DISCOVERY pool)
    if pool_type == POOL_DISCOVERY:
        discovery_bonus = calculate_discovery_bonus(caption, max_earnings)
        discovery_component = discovery_bonus * DISCOVERY_BONUS_WEIGHT
    else:
        discovery_component = 0.0

    # Step 5: Calculate payday component (if date provided)
    if target_date is not None:
        payday_score = get_payday_score(target_date)
        payday_component = payday_score * PAYDAY_WEIGHT
    else:
        payday_component = 0.0

    # Step 6: Sum all components
    final_weight = (
        earnings_component
        + freshness_component
        + persona_component
        + discovery_component
        + payday_component
    )

    # Ensure minimum weight for non-zero selection probability
    return max(MIN_WEIGHT, final_weight)


def _get_pool_earnings(
    caption: CaptionLike,
    pool_type: str,
    content_type_avg_earnings: float,
) -> float:
    """
    Get effective earnings for weight calculation based on pool type.

    This is an internal helper that applies pool-specific discounts
    for the weight calculation (different from get_effective_earnings_proxy
    which is for external use).

    Args:
        caption: Caption-like object with earnings attributes.
        pool_type: One of 'PROVEN', 'GLOBAL_EARNER', or 'DISCOVERY'.
        content_type_avg_earnings: Average earnings for this content type.

    Returns:
        Effective earnings for weight calculation (with discounts applied).

    Raises:
        ValueError: If pool_type is not one of 'PROVEN', 'GLOBAL_EARNER', or 'DISCOVERY'.
    """
    if pool_type == POOL_PROVEN:
        # PROVEN: Use creator-specific earnings at full weight
        earnings = caption.creator_avg_earnings
        return earnings if earnings is not None and earnings > 0 else 0.0

    elif pool_type == POOL_GLOBAL_EARNER:
        # GLOBAL_EARNER: Use global earnings with 20% discount
        earnings = caption.global_avg_earnings
        if earnings is not None and earnings > 0:
            return earnings * GLOBAL_EARNER_DISCOUNT
        return 0.0

    elif pool_type == POOL_DISCOVERY:
        # DISCOVERY: Use content type average with performance scaling
        performance_percentile = caption.performance_score / 100.0
        return content_type_avg_earnings * performance_percentile * DISCOVERY_DISCOUNT

    else:
        raise ValueError(
            f"Unknown pool_type: {pool_type}. "
            f"Must be one of: {POOL_PROVEN}, {POOL_GLOBAL_EARNER}, {POOL_DISCOVERY}"
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_max_earnings(captions: list, pool_type: str | None = None) -> float:
    """
    Calculate maximum earnings from a list of captions for normalization.

    This helper extracts the max earnings value needed for weight calculation.
    The earnings source depends on the pool type if specified.

    Args:
        captions: List of Caption-like objects.
        pool_type: Optional pool type to use specific earnings source.
            If None, uses fallback logic (creator -> global).

    Returns:
        Maximum earnings value, or 100.0 if no earnings data found.

    Example:
        >>> max_e = get_max_earnings(captions, pool_type='PROVEN')
        >>> # Returns max creator_avg_earnings from the list
    """
    all_earnings = []

    for caption in captions:
        if pool_type == POOL_PROVEN:
            earnings = getattr(caption, "creator_avg_earnings", None)
        elif pool_type == POOL_GLOBAL_EARNER:
            earnings = getattr(caption, "global_avg_earnings", None)
        elif pool_type == POOL_DISCOVERY:
            earnings = getattr(caption, "global_avg_earnings", None)
        else:
            # Fallback: try creator first, then global
            earnings = getattr(caption, "creator_avg_earnings", None)
            if earnings is None or earnings <= 0:
                earnings = getattr(caption, "global_avg_earnings", None)

        if earnings is not None and earnings > 0:
            all_earnings.append(earnings)

    return max(all_earnings) if all_earnings else 100.0


def determine_pool_type(caption: CaptionLike) -> str:
    """
    Determine the appropriate pool type for a caption based on available data.

    This helper inspects the caption's earnings data to classify it into
    the correct pool for weight calculation.

    Args:
        caption: Caption-like object with earnings attributes.

    Returns:
        Pool type string: 'PROVEN', 'GLOBAL_EARNER', or 'DISCOVERY'.

    Classification logic:
        - PROVEN: Has creator_avg_earnings > 0
        - GLOBAL_EARNER: Has global_avg_earnings > 0 (but no creator earnings)
        - DISCOVERY: No earnings data available

    Example:
        >>> pool = determine_pool_type(caption)
        >>> weight = calculate_weight(caption, pool, ...)
    """
    creator_earnings = caption.creator_avg_earnings
    if creator_earnings is not None and creator_earnings > 0:
        return POOL_PROVEN

    global_earnings = caption.global_avg_earnings
    if global_earnings is not None and global_earnings > 0:
        return POOL_GLOBAL_EARNER

    return POOL_DISCOVERY


# =============================================================================
# PATTERN-BASED SCORING FUNCTIONS
# =============================================================================


def calculate_pattern_score(
    caption: dict[str, Any] | "ScoredCaption",
    pattern_profile: "PatternProfile",
) -> float:
    """
    Calculate pattern match score for a caption based on historical performance.

    Score lookup order:
    1. Check combined pattern first: "content_type|tone|hook_type"
    2. Fall back to individual attributes (average of available)
    3. Return BASE_PATTERN_SCORE (30.0) when no pattern data

    The final score is multiplied by the profile's confidence to account
    for data quality. Lower confidence profiles produce more conservative scores.

    Args:
        caption: Caption dict with keys: content_type_name, tone, hook_type (emoji_style)
                 OR a ScoredCaption object with corresponding attributes.
        pattern_profile: PatternProfile with historical patterns from pattern_extraction.

    Returns:
        float: Pattern score 0-100 (higher = better match to successful patterns).
               Score is adjusted by profile confidence.

    Example:
        >>> from pattern_extraction import build_pattern_profile
        >>> profile = build_pattern_profile(conn, creator_id)
        >>> caption = {"content_type_name": "sextape", "tone": "playful", "hook_type": "question"}
        >>> score = calculate_pattern_score(caption, profile)
        >>> print(f"Pattern score: {score:.1f}")
        Pattern score: 72.5
    """
    # Handle None pattern_profile
    if pattern_profile is None:
        logger.debug("No pattern profile provided, returning BASE_PATTERN_SCORE")
        return BASE_PATTERN_SCORE

    # Extract attributes from caption (support both dict and object)
    if isinstance(caption, dict):
        content_type = caption.get("content_type_name") or caption.get("content_type") or ""
        tone = caption.get("tone") or ""
        hook_type = caption.get("hook_type") or caption.get("emoji_style") or ""
    else:
        # ScoredCaption or similar object
        content_type = getattr(caption, "content_type_name", None) or ""
        tone = getattr(caption, "tone", None) or ""
        hook_type = getattr(caption, "hook_type", None) or getattr(caption, "emoji_style", None) or ""

    # Normalize to strings
    content_type = str(content_type) if content_type else ""
    tone = str(tone) if tone else ""
    hook_type = str(hook_type) if hook_type else ""

    # Build combined key for Tier 1 lookup
    combined_key = f"{content_type}|{tone}|{hook_type}"

    # Try combined pattern first (Tier 1 - most specific)
    if combined_key in pattern_profile.combined_patterns:
        raw_score = pattern_profile.combined_patterns[combined_key].normalized_score
        adjusted_score = raw_score * pattern_profile.confidence
        logger.debug(
            f"Pattern score for {combined_key}: {raw_score:.1f} "
            f"(confidence-adjusted: {adjusted_score:.1f})"
        )
        return min(MAX_PATTERN_SCORE, adjusted_score)

    # Fall back to individual patterns (Tier 2)
    scores: list[float] = []

    if content_type and content_type in pattern_profile.content_type_patterns:
        scores.append(pattern_profile.content_type_patterns[content_type].normalized_score)

    if tone and tone in pattern_profile.tone_patterns:
        scores.append(pattern_profile.tone_patterns[tone].normalized_score)

    if hook_type and hook_type in pattern_profile.hook_patterns:
        scores.append(pattern_profile.hook_patterns[hook_type].normalized_score)

    # Calculate average of available individual pattern scores
    if scores:
        raw_score = sum(scores) / len(scores)
        adjusted_score = raw_score * pattern_profile.confidence
        logger.debug(
            f"Pattern score (fallback) for {combined_key}: {raw_score:.1f} "
            f"from {len(scores)} attributes (confidence-adjusted: {adjusted_score:.1f})"
        )
        return min(MAX_PATTERN_SCORE, adjusted_score)

    # No pattern data available - return base score
    logger.debug(f"No pattern data for {combined_key}, returning BASE_PATTERN_SCORE")
    return BASE_PATTERN_SCORE


def calculate_never_used_bonus(
    caption: dict[str, Any] | "ScoredCaption",
    creator_id: str,
    conn: sqlite3.Connection | None = None,
) -> float:
    """
    Calculate bonus multiplier for captions not recently used.

    This function determines the freshness tier of a caption and returns
    the appropriate multiplier. Captions that have never been used for
    this creator receive a significant bonus to prioritize fresh content.

    Args:
        caption: Caption dict or ScoredCaption object.
            If dict, can contain 'freshness_tier' key for direct lookup.
            Otherwise, uses 'times_used_on_page' or queries database.
        creator_id: Creator UUID for database lookup if needed.
        conn: Optional database connection for querying usage history.
            Only needed if freshness_tier is not already set on caption.

    Returns:
        float: Multiplier value:
            - 1.5 for 'never_used' tier (caption never used for this creator)
            - 1.0 for 'fresh' tier (used but above freshness threshold)
            - 0.0 for 'excluded' tier (below freshness threshold)

    Example:
        >>> caption = {"freshness_tier": "never_used"}
        >>> bonus = calculate_never_used_bonus(caption, "creator_123")
        >>> print(f"Never-used bonus: {bonus}")
        Never-used bonus: 1.5

        >>> # With database lookup
        >>> with get_connection() as conn:
        ...     bonus = calculate_never_used_bonus(
        ...         {"caption_id": 12345, "freshness_score": 85},
        ...         "creator_123",
        ...         conn
        ...     )
    """
    # Check if caption already has freshness_tier
    if isinstance(caption, dict):
        freshness_tier = caption.get("freshness_tier")
        caption_id = caption.get("caption_id")
        times_used = caption.get("times_used_on_page", 0)
        freshness_score = caption.get("freshness_score", 100.0)
    else:
        # ScoredCaption or similar object
        freshness_tier = getattr(caption, "freshness_tier", None)
        caption_id = getattr(caption, "caption_id", None)
        times_used = getattr(caption, "times_used_on_page", 0)
        freshness_score = getattr(caption, "freshness_score", 100.0)

    # If freshness_tier is already set, use it directly
    if freshness_tier is not None:
        multiplier = FRESHNESS_MULTIPLIERS.get(freshness_tier, 1.0)
        logger.debug(f"Caption {caption_id} freshness_tier={freshness_tier}, multiplier={multiplier}")
        return multiplier

    # Check times_used_on_page if available
    if times_used is not None and times_used == 0:
        logger.debug(f"Caption {caption_id} has times_used_on_page=0, returning never_used multiplier")
        return FRESHNESS_MULTIPLIERS["never_used"]

    # Query database if connection provided and caption_id available
    if conn is not None and caption_id is not None:
        try:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as usage_count
                FROM mass_messages
                WHERE caption_id = :caption_id
                  AND creator_id = :creator_id
                """,
                {"caption_id": caption_id, "creator_id": creator_id},
            )
            row = cursor.fetchone()
            usage_count = row["usage_count"] if row else 0

            if usage_count == 0:
                logger.debug(f"Caption {caption_id} never used by {creator_id}, returning never_used multiplier")
                return FRESHNESS_MULTIPLIERS["never_used"]
        except Exception as e:
            logger.warning(f"Database query failed for caption {caption_id}: {e}")

    # Determine tier based on freshness_score
    if freshness_score is not None and freshness_score >= 30.0:
        logger.debug(f"Caption {caption_id} is fresh (score={freshness_score}), returning fresh multiplier")
        return FRESHNESS_MULTIPLIERS["fresh"]
    elif freshness_score is not None and freshness_score < 30.0:
        logger.debug(f"Caption {caption_id} is excluded (score={freshness_score}), returning 0.0")
        return FRESHNESS_MULTIPLIERS["excluded"]

    # Default to fresh tier
    logger.debug(f"Caption {caption_id} defaulting to fresh multiplier")
    return FRESHNESS_MULTIPLIERS["fresh"]


def calculate_exploration_weight(
    caption: dict[str, Any] | "ScoredCaption",
    schedule_context: dict[str, Any],
) -> float:
    """
    Calculate exploration weight for diversity in selection.

    Promotes captions with attributes not yet used in the current schedule.
    This ensures variety in content types, tones, and hook styles throughout
    the week, preventing repetitive patterns.

    Low pattern scores also receive a boost to encourage testing of new
    patterns that may perform well.

    Args:
        caption: Caption dict or ScoredCaption object with attributes:
            - content_type_name: Content type (e.g., "sextape", "solo")
            - tone: Caption tone (e.g., "playful", "seductive")
            - hook_type: Hook type (e.g., "question", "urgency")
            - pattern_score: Optional pre-calculated pattern score
        schedule_context: Dictionary with schedule state:
            - used_hook_types: set[str] - Hook types already in schedule
            - used_tones: set[str] - Tones already in schedule
            - content_type_counts: dict[str, int] - Count per content type
            - target_content_distribution: dict[str, int] - Target counts

    Returns:
        float: Exploration weight 0-100 (higher = more exploration value).

    Bonus components:
        - Inverse pattern score: max(0, 50 - pattern_score)
        - Unused hook_type: +20 points
        - Unused tone: +15 points
        - Under-represented content_type: +10 points

    Example:
        >>> context = {
        ...     "used_hook_types": {"question", "urgency"},
        ...     "used_tones": {"playful"},
        ...     "content_type_counts": {"sextape": 5, "solo": 2},
        ...     "target_content_distribution": {"sextape": 5, "solo": 5}
        ... }
        >>> caption = {
        ...     "content_type_name": "solo",
        ...     "tone": "seductive",  # Not in used_tones
        ...     "hook_type": "curiosity",  # Not in used_hook_types
        ...     "pattern_score": 25.0  # Low pattern score
        ... }
        >>> weight = calculate_exploration_weight(caption, context)
        >>> print(f"Exploration weight: {weight:.1f}")
        Exploration weight: 70.0  # 25 (inverse) + 20 (hook) + 15 (tone) + 10 (content)
    """
    # Handle None or empty context
    if not schedule_context:
        logger.debug("No schedule context provided, returning 0 exploration weight")
        return 0.0

    # Extract caption attributes
    if isinstance(caption, dict):
        content_type = caption.get("content_type_name") or caption.get("content_type") or ""
        tone = caption.get("tone") or ""
        hook_type = caption.get("hook_type") or caption.get("emoji_style") or ""
        pattern_score = caption.get("pattern_score", BASE_PATTERN_SCORE)
    else:
        content_type = getattr(caption, "content_type_name", None) or ""
        tone = getattr(caption, "tone", None) or ""
        hook_type = getattr(caption, "hook_type", None) or getattr(caption, "emoji_style", None) or ""
        pattern_score = getattr(caption, "pattern_score", BASE_PATTERN_SCORE)

    # Normalize to strings
    content_type = str(content_type) if content_type else ""
    tone = str(tone) if tone else ""
    hook_type = str(hook_type) if hook_type else ""

    # Ensure pattern_score is numeric
    if pattern_score is None:
        pattern_score = BASE_PATTERN_SCORE

    # Start with inverse pattern score (rewards low pattern scores for exploration)
    exploration_weight = max(0.0, EXPLORATION_BASE_INVERSE - pattern_score)

    # Extract context sets/dicts with defaults
    used_hook_types: set[str] = schedule_context.get("used_hook_types", set())
    used_tones: set[str] = schedule_context.get("used_tones", set())
    content_type_counts: dict[str, int] = schedule_context.get("content_type_counts", {})
    target_distribution: dict[str, int] = schedule_context.get("target_content_distribution", {})

    # Bonus for unused hook_type
    if hook_type and hook_type not in used_hook_types:
        exploration_weight += EXPLORATION_HOOK_TYPE_BONUS
        logger.debug(f"Hook type '{hook_type}' unused in schedule, +{EXPLORATION_HOOK_TYPE_BONUS}")

    # Bonus for unused tone
    if tone and tone not in used_tones:
        exploration_weight += EXPLORATION_TONE_BONUS
        logger.debug(f"Tone '{tone}' unused in schedule, +{EXPLORATION_TONE_BONUS}")

    # Bonus for under-represented content type
    if content_type and content_type in target_distribution:
        target_count = target_distribution.get(content_type, 0)
        current_count = content_type_counts.get(content_type, 0)
        if current_count < target_count:
            exploration_weight += EXPLORATION_CONTENT_TYPE_BONUS
            logger.debug(
                f"Content type '{content_type}' under-represented "
                f"({current_count}/{target_count}), +{EXPLORATION_CONTENT_TYPE_BONUS}"
            )

    # Cap at maximum exploration score
    final_weight = min(MAX_EXPLORATION_SCORE, exploration_weight)

    logger.debug(
        f"Exploration weight for ({content_type}|{tone}|{hook_type}): {final_weight:.1f} "
        f"(pattern={pattern_score:.1f})"
    )

    return final_weight


# =============================================================================
# UNIFIED WEIGHT CALCULATION (Phase 3B)
# =============================================================================


def calculate_fresh_weight(
    caption: dict[str, Any] | "ScoredCaption",
    pattern_profile: "PatternProfile",
    persona_score: float,
    schedule_context: dict[str, Any],
    conn: sqlite3.Connection | None = None,
    creator_id: str | None = None,
) -> tuple[float, dict[str, Any]]:
    """
    Calculate selection weight using the new fresh-focused formula.

    Formula:
        PatternMatch(40%) + NeverUsedBonus(25%) + Persona(15%) +
        FreshnessBonus(10%) + Exploration(10%)

    This formula prioritizes fresh content guided by historical patterns
    rather than directly reusing proven winners. It combines:
    - Pattern matching: Predicted performance based on historical data
    - Never-used bonus: Priority for untested captions
    - Persona matching: Voice consistency with creator
    - Freshness bonus: Reward for high freshness scores
    - Exploration: Diversity promotion for schedule variety

    Args:
        caption: Caption dict or ScoredCaption with attributes:
            - freshness_score: Caption freshness (0-100)
            - freshness_tier: 'never_used', 'fresh', or 'excluded'
            - content_type_name: Content type name
            - tone: Caption tone
            - hook_type/emoji_style: Hook type
            - caption_id: For database lookups
        pattern_profile: PatternProfile with historical patterns
        persona_score: Pre-calculated persona match score (0-100)
        schedule_context: Context dict for exploration scoring:
            - used_hook_types: set of hook types in schedule
            - used_tones: set of tones in schedule
            - content_type_counts: dict of content_type -> count
            - target_content_distribution: target counts per type
        conn: Database connection (optional, for never_used lookup)
        creator_id: Creator ID (required if conn provided)

    Returns:
        tuple: (final_weight, breakdown_dict)
            - final_weight: float 0-100 (minimum MIN_WEIGHT)
            - breakdown_dict: Component values for debugging

    Example:
        >>> weight, breakdown = calculate_fresh_weight(
        ...     caption, profile, persona_score=75.0,
        ...     schedule_context={"used_hook_types": set()},
        ...     conn=conn, creator_id="abc123"
        ... )
        >>> print(f"Total weight: {weight:.1f}")
        >>> print(f"Pattern component: {breakdown['pattern_match']:.1f}")
    """
    # Calculate pattern match score
    pattern_score = calculate_pattern_score(caption, pattern_profile)

    # Calculate never-used bonus multiplier
    never_used_multiplier = calculate_never_used_bonus(
        caption, creator_id or "", conn
    )

    # Get freshness score and tier from caption
    if isinstance(caption, dict):
        freshness_score = caption.get("freshness_score", 50.0)
        freshness_tier = caption.get("freshness_tier", "unknown")
        caption_id = caption.get("caption_id", "unknown")
    else:
        freshness_score = getattr(caption, "freshness_score", 50.0)
        freshness_tier = getattr(caption, "freshness_tier", "unknown")
        caption_id = getattr(caption, "caption_id", "unknown")

    # Calculate exploration weight
    exploration_score = calculate_exploration_weight(caption, schedule_context)

    # Apply freshness tier multiplier to base value for never_used component
    # never_used: 50 * 1.5 = 75 points (before weighting)
    # fresh: 50 * 1.0 = 50 points (before weighting)
    base_with_tier = 50.0 * never_used_multiplier

    # Calculate weighted components
    weighted_pattern = pattern_score * PATTERN_WEIGHT
    weighted_never_used = base_with_tier * NEVER_USED_WEIGHT
    weighted_persona = persona_score * NEW_PERSONA_WEIGHT
    weighted_freshness = freshness_score * FRESHNESS_BONUS_WEIGHT
    weighted_exploration = exploration_score * EXPLORATION_WEIGHT

    # Sum all components
    final_weight = (
        weighted_pattern
        + weighted_never_used
        + weighted_persona
        + weighted_freshness
        + weighted_exploration
    )

    # Build breakdown dict for debugging and logging
    breakdown: dict[str, Any] = {
        "pattern_match": weighted_pattern,
        "never_used_bonus": weighted_never_used,
        "persona": weighted_persona,
        "freshness_bonus": weighted_freshness,
        "exploration": weighted_exploration,
        "total": final_weight,
        "mode": "fresh",
        "tier": freshness_tier,
        # Raw scores for detailed analysis
        "raw_pattern_score": pattern_score,
        "raw_persona_score": persona_score,
        "raw_freshness_score": freshness_score,
        "raw_exploration_score": exploration_score,
        "never_used_multiplier": never_used_multiplier,
    }

    logger.debug(
        f"Fresh weight for caption {caption_id}: "
        f"pattern={weighted_pattern:.1f} "
        f"never_used={weighted_never_used:.1f} "
        f"persona={weighted_persona:.1f} "
        f"freshness={weighted_freshness:.1f} "
        f"exploration={weighted_exploration:.1f} "
        f"TOTAL={final_weight:.1f} "
        f"tier={freshness_tier}"
    )

    return max(MIN_WEIGHT, final_weight), breakdown


def calculate_fallback_weight(
    caption: dict[str, Any] | "ScoredCaption",
    persona_score: float = 50.0,
) -> tuple[float, dict[str, Any]]:
    """
    Fallback weight calculation when pattern profile is unavailable.

    Uses a simplified formula when historical pattern data is not available:
        Freshness(40%) + Persona(30%) + Performance(30%)

    This provides reasonable selection weights for new creators or when
    the pattern extraction system is unavailable.

    Args:
        caption: Caption dict or ScoredCaption with:
            - freshness_score: Caption freshness (0-100)
            - performance_score: Historical performance (0-100)
        persona_score: Pre-calculated persona score (0-100), defaults to 50.0

    Returns:
        tuple: (final_weight, breakdown_dict)
            - final_weight: float 0-100
            - breakdown_dict: Component values with mode='fallback'

    Example:
        >>> weight, breakdown = calculate_fallback_weight(caption, persona_score=65.0)
        >>> print(f"Fallback weight: {weight:.1f}")
        >>> print(breakdown['mode'])
        'fallback'
    """
    # Extract scores from caption
    if isinstance(caption, dict):
        freshness_score = caption.get("freshness_score", 50.0)
        performance_score = caption.get("performance_score", 50.0)
        caption_id = caption.get("caption_id", "unknown")
    else:
        freshness_score = getattr(caption, "freshness_score", 50.0)
        performance_score = getattr(caption, "performance_score", 50.0)
        caption_id = getattr(caption, "caption_id", "unknown")

    # Fallback weights
    fallback_freshness_weight = 0.40
    fallback_persona_weight = 0.30
    fallback_performance_weight = 0.30

    # Calculate weighted components
    weighted_freshness = freshness_score * fallback_freshness_weight
    weighted_persona = persona_score * fallback_persona_weight
    weighted_performance = performance_score * fallback_performance_weight

    final_weight = weighted_freshness + weighted_persona + weighted_performance

    breakdown: dict[str, Any] = {
        "freshness": weighted_freshness,
        "persona": weighted_persona,
        "performance": weighted_performance,
        "total": final_weight,
        "mode": "fallback",
        "raw_freshness_score": freshness_score,
        "raw_persona_score": persona_score,
        "raw_performance_score": performance_score,
    }

    logger.debug(
        f"Fallback weight for caption {caption_id}: "
        f"freshness={weighted_freshness:.1f} "
        f"persona={weighted_persona:.1f} "
        f"performance={weighted_performance:.1f} "
        f"TOTAL={final_weight:.1f}"
    )

    return max(MIN_WEIGHT, final_weight), breakdown


def calculate_legacy_weight(
    caption: dict[str, Any] | CaptionLike,
    pool_type: str = "DISCOVERY",
    content_type_avg_earnings: float = 50.0,
    max_earnings: float = 500.0,
    persona_boost: float = 1.0,
    target_date: date | None = None,
) -> tuple[float, dict[str, Any]]:
    """
    Calculate weight using the legacy pool-based formula with breakdown.

    Wrapper around the original calculate_weight() function that returns
    a breakdown dict for consistency with the new weight functions.

    Legacy Formula:
        Earnings(55%) + Freshness(15%) + Persona(15%) + Discovery(10%) + Payday(5%)

    Args:
        caption: Caption dict or CaptionLike object with earnings attributes
        pool_type: Pool type for earnings calculation ('PROVEN', 'GLOBAL_EARNER', 'DISCOVERY')
        content_type_avg_earnings: Average earnings for content type
        max_earnings: Maximum earnings for normalization
        persona_boost: Persona boost factor (1.0-1.4)
        target_date: Optional date for payday scoring

    Returns:
        tuple: (final_weight, breakdown_dict)
            - final_weight: Calculated weight
            - breakdown_dict: Contains mode='legacy' and pool_type

    Example:
        >>> weight, breakdown = calculate_legacy_weight(
        ...     caption, pool_type="PROVEN",
        ...     max_earnings=500.0, persona_boost=1.2
        ... )
    """
    # Create a wrapper class to satisfy CaptionLike if caption is a dict
    if isinstance(caption, dict):
        class _DictCaptionWrapper:
            """Wrapper to make dict satisfy CaptionLike protocol."""

            def __init__(self, d: dict[str, Any]) -> None:
                self._d = d

            @property
            def creator_avg_earnings(self) -> float | None:
                return self._d.get("creator_avg_earnings")

            @property
            def global_avg_earnings(self) -> float | None:
                return self._d.get("global_avg_earnings")

            @property
            def performance_score(self) -> float:
                return self._d.get("performance_score", 50.0)

            @property
            def freshness_score(self) -> float:
                return self._d.get("freshness_score", 50.0)

            @property
            def is_universal(self) -> bool:
                return self._d.get("is_universal", False)

        caption_wrapper = _DictCaptionWrapper(caption)
        caption_id = caption.get("caption_id", "unknown")
    else:
        caption_wrapper = caption
        caption_id = getattr(caption, "caption_id", "unknown")

    # Call the original calculate_weight function
    weight = calculate_weight(
        caption_wrapper,
        pool_type,
        content_type_avg_earnings,
        max_earnings,
        persona_boost,
        target_date,
    )

    breakdown: dict[str, Any] = {
        "total": weight,
        "mode": "legacy",
        "pool_type": pool_type,
        "persona_boost": persona_boost,
    }

    logger.debug(
        f"Legacy weight for caption {caption_id}: "
        f"pool={pool_type} "
        f"TOTAL={weight:.1f}"
    )

    return weight, breakdown


def calculate_unified_weight(
    caption: dict[str, Any] | "ScoredCaption",
    pattern_profile: "PatternProfile | None" = None,
    persona_score: float = 50.0,
    schedule_context: dict[str, Any] | None = None,
    conn: sqlite3.Connection | None = None,
    creator_id: str | None = None,
    use_legacy: bool = False,
    # Legacy mode parameters
    pool_type: str = "DISCOVERY",
    content_type_avg_earnings: float = 50.0,
    max_earnings: float = 500.0,
    persona_boost: float = 1.0,
    target_date: date | None = None,
) -> tuple[float, dict[str, Any]]:
    """
    Unified weight calculation with automatic formula selection.

    This is the primary entry point for weight calculation. It automatically
    selects between the new fresh-focused formula and legacy pool-based
    formula based on configuration or explicit flag.

    Selection logic:
    1. If use_legacy=True, use legacy pool-based formula
    2. If pattern_profile is None, use fallback formula
    3. Otherwise, use new fresh-focused formula

    Args:
        caption: Caption dict or ScoredCaption object
        pattern_profile: PatternProfile (required for new formula)
        persona_score: Pre-calculated persona score (0-100)
        schedule_context: Context dict for exploration scoring
        conn: Database connection (optional)
        creator_id: Creator ID (optional)
        use_legacy: If True, force legacy formula for A/B testing

        Legacy mode parameters (only used when use_legacy=True):
        pool_type: Pool type for earnings calculation
        content_type_avg_earnings: Average for content type
        max_earnings: Maximum earnings for normalization
        persona_boost: Persona boost factor (1.0-1.4)
        target_date: Date for payday scoring

    Returns:
        tuple: (final_weight, breakdown_dict)
            - breakdown includes 'mode': 'fresh'|'fallback'|'legacy'

    Example:
        >>> # New formula with pattern profile
        >>> weight, breakdown = calculate_unified_weight(
        ...     caption, pattern_profile=profile, persona_score=75.0,
        ...     schedule_context={"used_hook_types": set()}
        ... )
        >>> print(f"Mode: {breakdown['mode']}, Weight: {weight:.1f}")

        >>> # Legacy formula for A/B testing
        >>> weight, breakdown = calculate_unified_weight(
        ...     caption, use_legacy=True, pool_type="PROVEN",
        ...     max_earnings=500.0
        ... )
        >>> print(f"Mode: {breakdown['mode']}")
        'legacy'

        >>> # Automatic fallback when no pattern profile
        >>> weight, breakdown = calculate_unified_weight(
        ...     caption, pattern_profile=None, persona_score=60.0
        ... )
        >>> print(f"Mode: {breakdown['mode']}")
        'fallback'
    """
    # Check configuration for legacy mode if not explicitly set
    if not use_legacy:
        try:
            from config_loader import load_selection_config
            selection_config = load_selection_config(validate=False)
            use_legacy = selection_config.use_legacy_weights
        except (ImportError, Exception) as e:
            logger.debug(f"Could not load selection config: {e}")

    # Use legacy formula if requested
    if use_legacy:
        return calculate_legacy_weight(
            caption,
            pool_type,
            content_type_avg_earnings,
            max_earnings,
            persona_boost,
            target_date,
        )

    # Use fallback if no pattern profile available
    if pattern_profile is None:
        return calculate_fallback_weight(caption, persona_score)

    # Use new fresh-focused formula
    return calculate_fresh_weight(
        caption,
        pattern_profile,
        persona_score,
        schedule_context or {},
        conn,
        creator_id,
    )


# =============================================================================
# LOGGING AND DIAGNOSTICS
# =============================================================================


def log_weight_breakdown(
    caption_id: int | str,
    breakdown: dict[str, Any],
    level: str = "DEBUG",
) -> None:
    """
    Log weight breakdown for debugging and analysis.

    Formats the breakdown dict into a human-readable log message with
    appropriate formatting based on the calculation mode.

    Args:
        caption_id: Caption identifier for the log message
        breakdown: Weight breakdown dict from calculate_*_weight() functions
        level: Logging level string ("DEBUG", "INFO", "WARNING")

    Example:
        >>> weight, breakdown = calculate_fresh_weight(...)
        >>> log_weight_breakdown(caption.caption_id, breakdown, "INFO")
        # Logs: Caption 12345 weights [fresh]: pattern=32.0 never_used=18.8 ...
    """
    log_level = getattr(logging, level.upper(), logging.DEBUG)
    mode = breakdown.get("mode", "unknown")

    if mode == "fresh":
        logger.log(
            log_level,
            f"Caption {caption_id} weights [fresh]: "
            f"pattern={breakdown.get('pattern_match', 0):.1f} "
            f"never_used={breakdown.get('never_used_bonus', 0):.1f} "
            f"persona={breakdown.get('persona', 0):.1f} "
            f"freshness={breakdown.get('freshness_bonus', 0):.1f} "
            f"exploration={breakdown.get('exploration', 0):.1f} "
            f"TOTAL={breakdown.get('total', 0):.1f} "
            f"tier={breakdown.get('tier', 'unknown')}"
        )
    elif mode == "fallback":
        logger.log(
            log_level,
            f"Caption {caption_id} weights [fallback]: "
            f"freshness={breakdown.get('freshness', 0):.1f} "
            f"persona={breakdown.get('persona', 0):.1f} "
            f"performance={breakdown.get('performance', 0):.1f} "
            f"TOTAL={breakdown.get('total', 0):.1f}"
        )
    elif mode == "legacy":
        logger.log(
            log_level,
            f"Caption {caption_id} weights [legacy]: "
            f"pool={breakdown.get('pool_type', 'unknown')} "
            f"TOTAL={breakdown.get('total', 0):.1f}"
        )
    else:
        logger.log(
            log_level,
            f"Caption {caption_id} weights [unknown mode]: "
            f"TOTAL={breakdown.get('total', 0):.1f}"
        )


def get_weight_config() -> dict[str, Any]:
    """
    Return current weight formula configuration.

    Useful for logging, debugging, A/B test tracking, and understanding
    the active weight calculation settings.

    Returns:
        dict: Configuration including:
            - formula: 'fresh' or 'legacy'
            - weights: Component weight values
            - total: Sum of weights (should be 1.0)
            - freshness_multipliers: Tier multipliers (for fresh formula)

    Example:
        >>> config = get_weight_config()
        >>> print(f"Formula: {config['formula']}")
        >>> print(f"Weights sum: {config['total']}")
    """
    # Check configuration for legacy mode
    use_legacy = False
    try:
        from config_loader import load_selection_config
        selection_config = load_selection_config(validate=False)
        use_legacy = selection_config.use_legacy_weights
    except (ImportError, Exception):
        pass

    if use_legacy:
        return {
            "formula": "legacy",
            "weights": {
                "earnings": EARNINGS_WEIGHT,
                "freshness": FRESHNESS_WEIGHT,
                "persona": PERSONA_WEIGHT,
                "discovery_bonus": DISCOVERY_BONUS_WEIGHT,
                "payday": PAYDAY_WEIGHT,
            },
            "total": (
                EARNINGS_WEIGHT + FRESHNESS_WEIGHT + PERSONA_WEIGHT +
                DISCOVERY_BONUS_WEIGHT + PAYDAY_WEIGHT
            ),
        }
    else:
        return {
            "formula": "fresh",
            "weights": {
                "pattern_match": PATTERN_WEIGHT,
                "never_used_bonus": NEVER_USED_WEIGHT,
                "persona": NEW_PERSONA_WEIGHT,
                "freshness_bonus": FRESHNESS_BONUS_WEIGHT,
                "exploration": EXPLORATION_WEIGHT,
            },
            "total": (
                PATTERN_WEIGHT + NEVER_USED_WEIGHT + NEW_PERSONA_WEIGHT +
                FRESHNESS_BONUS_WEIGHT + EXPLORATION_WEIGHT
            ),
            "freshness_multipliers": FRESHNESS_MULTIPLIERS,
            "exploration_bonuses": {
                "hook_type": EXPLORATION_HOOK_TYPE_BONUS,
                "tone": EXPLORATION_TONE_BONUS,
                "content_type": EXPLORATION_CONTENT_TYPE_BONUS,
            },
        }
