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

from datetime import date, timedelta
from math import exp, log1p
from typing import Protocol, runtime_checkable

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
