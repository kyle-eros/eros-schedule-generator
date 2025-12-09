#!/usr/bin/env python3
"""
Volume Optimizer - Multi-factor volume optimization for OnlyFans creators.

This module implements a sophisticated volume optimization algorithm that
considers multiple factors to determine optimal PPV and bump message volumes
for each creator in the EROS portfolio.

UPDATED 2025-12-06: New volume strategy with performance-based tier progression.

Usage:
    python volume_optimizer.py --creator missalexa
    python volume_optimizer.py --all --format table
    python volume_optimizer.py --populate --dry-run
    python volume_optimizer.py --creator missalexa --fan-count 5000

Factors Considered:
    1. Fan count brackets (base volume)
    2. Performance tier (revenue contribution)
    3. Conversion rate and dollars per PPV (NEW: volume tier)
    4. Niche/persona type
    5. Subscription price
    6. Account age
    7. Day-of-week optimization (NEW)

Volume Tiers (Performance-Based):
    - Base:   2 PPV/day (14/week) - All creators (minimum floor)
    - Growth: 3 PPV/day (21/week) - Conv >0.10% OR $/PPV >$40
    - Scale:  4 PPV/day (28/week) - Conv >0.25% AND $/PPV >$50
    - High:   5 PPV/day (35/week) - Conv >0.35% AND $/PPV >$65
    - Ultra:  6 PPV/day (42/week) - Conv >0.40% AND $/PPV >$75 AND >$75K rev

Hard Caps:
    - Paid pages: MIN 14, MAX 42 PPV per WEEK (2-6 per day)
    - Free pages: MIN 2, MAX 6 PPV per DAY
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

# Path resolution for database
SCRIPT_DIR = Path(__file__).parent

from database import DB_PATH  # noqa: E402

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Volume configuration by page type and fan count
# Format: (min_fans, max_fans): (level_name, ppv_per_day, bump_per_day)
# NEW STRATEGY (2025-12-06): Minimum 2 PPV/day for ALL creators, max 6 for high performers
# Base volumes are floors; actual volume determined by get_volume_tier() based on performance
PAID_PAGE_CONFIG: dict[tuple[int, int | None], tuple[str, int, int]] = {
    (0, 999): ("Base", 2, 2),  # Base tier: 2 PPV/day minimum (14/week)
    (1000, 4999): ("Growth", 3, 2),  # Growth tier: 3 PPV/day (21/week)
    (5000, 14999): ("Scale", 4, 3),  # Scale tier: 4 PPV/day (28/week)
    (15000, None): ("High", 5, 4),  # High tier: 5 PPV/day (35/week)
}

# FREE pages use same minimum floor but can scale higher
FREE_PAGE_CONFIG: dict[tuple[int, int | None], tuple[str, int, int]] = {
    (0, 999): ("Base", 2, 2),  # Base tier: 2 PPV/day minimum (14/week)
    (1000, 4999): ("Growth", 3, 2),  # Growth tier: 3 PPV/day (21/week)
    (5000, 19999): ("Scale", 4, 3),  # Scale tier: 4 PPV/day (28/week)
    (20000, None): ("High", 5, 4),  # High tier: 5 PPV/day (35/week)
}

# Performance tier multipliers (1 = top tier, 3 = bottom tier)
TIER_FACTORS: dict[int, float] = {
    1: 1.15,  # Top performers get 15% more volume
    2: 1.00,  # Mid performers stay at baseline
    3: 0.85,  # Lower performers get reduced volume
}

# Conversion rate factors
# Format: (min_rate, max_rate, factor)
CONVERSION_FACTORS: list[tuple[float, float, float]] = [
    (0.20, 1.00, 1.15),  # 20%+ conversion: +15%
    (0.15, 0.20, 1.10),  # 15-20% conversion: +10%
    (0.10, 0.15, 1.00),  # 10-15% conversion: baseline
    (0.05, 0.10, 0.90),  # 5-10% conversion: -10%
    (0.00, 0.05, 0.85),  # <5% conversion: -15%
]

# Niche/persona type factors
NICHE_FACTORS: dict[str, float] = {
    # High engagement niches
    "fetish": 1.20,
    "kink": 1.20,
    "bdsm": 1.15,
    # Standard niches
    "explicit": 1.00,
    "hardcore": 1.00,
    "cosplay": 1.00,
    "fantasy": 1.00,
    # Lower engagement niches
    "softcore": 0.85,
    "tease": 0.85,
    # Relationship-focused (lower volume, higher quality)
    "fitness": 0.80,
    "lifestyle": 0.80,
    "gfe": 0.70,
    "girlfriend": 0.70,
}

# Subscription price factors (higher price = lower PPV tolerance)
# Format: (min_price, max_price, factor)
SUB_PRICE_FACTORS: list[tuple[float, float, float]] = [
    (0.00, 0.00, 1.10),  # Free pages: +10%
    (0.01, 9.99, 1.05),  # Low price: +5%
    (10.00, 14.99, 1.00),  # Standard price: baseline
    (15.00, 24.99, 0.85),  # Premium price: -15%
    (25.00, 50.00, 0.70),  # Ultra premium: -30%
]

# Account age factors (newer accounts need time to build)
# Format: (min_days, max_days, factor)
ACCOUNT_AGE_FACTORS: list[tuple[int, int | None, float]] = [
    (0, 30, 0.60),  # First month: 60%
    (31, 60, 0.75),  # Second month: 75%
    (61, 90, 0.85),  # Third month: 85%
    (91, 180, 0.95),  # 3-6 months: 95%
    (181, None, 1.00),  # 6+ months: full volume
]

# Page type volume efficiency factors (UPDATED 2025-12-06)
# Softened penalties to support new 2-6 PPV/day strategy
# These apply a final adjustment based on calculated weekly volume
FREE_PAGE_VOLUME_EFFICIENCY: list[tuple[int, int | None, float]] = [
    (0, 21, 1.00),  # 0-21 PPV/week (up to 3/day): no penalty
    (22, 35, 0.90),  # 22-35 PPV/week (3-5/day): 10% reduction
    (36, 42, 0.80),  # 36-42 PPV/week (5-6/day): 20% reduction
    (43, None, 0.70),  # 42+ PPV/week: efficiency protection
]

PAID_PAGE_VOLUME_TOLERANCE: list[tuple[int, int | None, float]] = [
    (0, 21, 1.00),  # 0-21 PPV/week (up to 3/day): no penalty
    (22, 35, 0.90),  # 22-35 PPV/week (3-5/day): 10% reduction
    (36, 42, 0.80),  # 36-42 PPV/week (5-6/day): 20% reduction
    (43, None, 0.70),  # 42+ PPV/week: efficiency protection
]

# Sweet spot targeting (UPDATED 2025-12-06)
# New range: 14-35 PPV/week (matches 2-5 PPV/day target range)
SWEET_SPOT_MIN = 14
SWEET_SPOT_MAX = 35

# Thresholds for proven performers who can exceed sweet spot
PROVEN_PERFORMER_MIN_REV_PER_SEND = 100.0  # $100+ per send
PROVEN_PERFORMER_MIN_PURCHASE_RATE = 0.005  # 0.5%+ purchase rate

# Hard caps (UPDATED 2025-12-06 for new volume strategy)
# New: 2 PPV/day minimum, 6 PPV/day maximum for high performers
PAID_PAGE_MIN_PPV_WEEK = 14  # 2 PPV/day * 7 = 14/week minimum
PAID_PAGE_MAX_PPV_WEEK = 42  # 6 PPV/day * 7 = 42/week maximum
FREE_PAGE_MIN_PPV_DAY = 2  # Minimum 2 PPV/day for ALL creators
FREE_PAGE_MAX_PPV_DAY = 6  # Maximum 6 PPV/day for high performers

# Bump strategy
MIN_BUMP_PER_DAY = 1
MAX_BUMP_PER_DAY = 4

# Optimal scheduling days
OPTIMAL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Bump delay ranges (minutes)
BUMP_DELAY_RANGES = {
    "High": (15, 30),
    "Ultra": (15, 25),
    "Mid": (20, 40),
    "Low": (25, 45),
    "Base": (25, 45),  # Added for new Base tier
    "Growth": (20, 40),  # Added for new Growth tier
    "Scale": (15, 35),  # Added for new Scale tier
}

# Day-of-week volume modifiers (from VOLUME_STRATEGY_FINAL_REPORT.md)
# Based on analysis showing Thursday has best $/PPV ($137)
DAY_OF_WEEK_MODIFIERS: dict[str, float] = {
    "Thursday": 1.3,  # Best $/PPV ($137)
    "Wednesday": 1.2,  # Peak efficiency
    "Friday": 1.2,  # Strong performer
    "Tuesday": 1.1,  # Good engagement
    "Monday": 1.0,  # Baseline
    "Sunday": 0.9,  # Recovery day
    "Saturday": 0.8,  # Lower value
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def get_niche_factor(persona_type: str) -> float:
    """
    Get the volume factor for a given niche/persona type.

    Args:
        persona_type: The creator's primary tone or persona type

    Returns:
        Multiplier factor (default 1.0 if unknown)
    """
    if not persona_type:
        return 1.0

    # Normalize and check for partial matches
    normalized = persona_type.lower().strip()

    # Direct match
    if normalized in NICHE_FACTORS:
        return NICHE_FACTORS[normalized]

    # Partial match (check if any key is in the persona type)
    for key, factor in NICHE_FACTORS.items():
        if key in normalized:
            return factor

    return 1.0


def get_subscription_price_factor(sub_price: float, is_free_page: bool) -> float:
    """
    Get the volume factor based on subscription price.

    Args:
        sub_price: Subscription price in dollars
        is_free_page: Whether this is a free page

    Returns:
        Multiplier factor
    """
    if is_free_page or sub_price == 0:
        return SUB_PRICE_FACTORS[0][2]  # Free page factor

    for min_price, max_price, factor in SUB_PRICE_FACTORS:
        if min_price <= sub_price <= max_price:
            return factor

    # If above max range, use lowest factor
    return SUB_PRICE_FACTORS[-1][2]


def get_account_age_factor(account_age_days: int) -> float:
    """
    Get the volume factor based on account age.

    Args:
        account_age_days: Number of days since account creation

    Returns:
        Multiplier factor
    """
    if account_age_days < 0:
        return 1.0

    for min_days, max_days, factor in ACCOUNT_AGE_FACTORS:
        if max_days is None:
            if account_age_days >= min_days:
                return factor
        elif min_days <= account_age_days <= max_days:
            return factor

    return 1.0


def get_page_type_volume_factor(weekly_ppv: int, is_free_page: bool) -> float:
    """
    Get the volume efficiency factor based on page type and calculated weekly volume.

    This applies final adjustments based on analysis showing:
    - Free pages: Peak efficiency at <5/week
    - Paid pages: Can sustain 10-20/week

    Args:
        weekly_ppv: Calculated weekly PPV volume
        is_free_page: Whether this is a free page

    Returns:
        Multiplier factor (0.35 to 1.0)
    """
    factors = FREE_PAGE_VOLUME_EFFICIENCY if is_free_page else PAID_PAGE_VOLUME_TOLERANCE

    for min_vol, max_vol, factor in factors:
        if max_vol is None:
            if weekly_ppv >= min_vol:
                return factor
        elif min_vol <= weekly_ppv <= max_vol:
            return factor

    return 1.0  # Default if no match


def get_conversion_factor(conversion_rate: float) -> float:
    """
    Get the volume factor based on conversion rate.

    Args:
        conversion_rate: Purchase rate as decimal (0.0 to 1.0)

    Returns:
        Multiplier factor
    """
    if conversion_rate < 0:
        conversion_rate = 0.0
    elif conversion_rate > 1:
        conversion_rate = 1.0

    for min_rate, max_rate, factor in CONVERSION_FACTORS:
        if min_rate <= conversion_rate < max_rate:
            return factor

    # Exact max match
    if conversion_rate >= CONVERSION_FACTORS[0][1]:
        return CONVERSION_FACTORS[0][2]

    return 1.0


def get_volume_tier(
    conv_rate: float, dollars_per_ppv: float, total_revenue: float
) -> tuple[str, int]:
    """
    Determine volume tier based on performance metrics.

    This function implements the new performance-based tier progression:
    - Base: 2 PPV/day (all creators - the new minimum floor)
    - Growth: 3 PPV/day (conv >0.10% OR $/PPV >$40)
    - Scale: 4 PPV/day (conv >0.25% AND $/PPV >$50)
    - High: 5 PPV/day (conv >0.35% AND $/PPV >$65)
    - Ultra: 6 PPV/day (conv >0.40% AND $/PPV >$75 AND >$75K revenue)

    Args:
        conv_rate: Conversion rate as decimal (e.g., 0.004 = 0.4%)
        dollars_per_ppv: Average revenue per PPV send in dollars
        total_revenue: Total lifetime revenue in dollars

    Returns:
        Tuple of (tier_name, ppv_per_day)

    Examples:
        >>> get_volume_tier(0.005, 80, 100000)  # High performer
        ('Ultra', 6)
        >>> get_volume_tier(0.001, 30, 5000)    # New creator
        ('Base', 2)
    """
    # Convert percentage to decimal if needed (handle both 0.4 and 0.004 formats)
    # If conv_rate > 1, assume it's a percentage and convert
    if conv_rate > 1:
        conv_rate = conv_rate / 100.0

    # Ultra: Conv >0.40% AND $/PPV >$75 AND >$75K rev
    if conv_rate > 0.0040 and dollars_per_ppv > 75 and total_revenue > 75000:
        return ("Ultra", 6)

    # High: Conv >0.35% AND $/PPV >$65
    if conv_rate > 0.0035 and dollars_per_ppv > 65:
        return ("High", 5)

    # Scale: Conv >0.25% AND $/PPV >$50
    if conv_rate > 0.0025 and dollars_per_ppv > 50:
        return ("Scale", 4)

    # Growth: Conv >0.10% OR $/PPV >$40
    if conv_rate > 0.0010 or dollars_per_ppv > 40:
        return ("Growth", 3)

    # Base: Everyone else (the new minimum floor)
    return ("Base", 2)


def get_day_of_week_modifier(day_name: str) -> float:
    """
    Get the volume modifier for a given day of the week.

    Based on analysis showing performance varies by day:
    - Thursday: Best $/PPV ($137) - 1.3x modifier
    - Wednesday/Friday: Strong performers - 1.2x modifier
    - Saturday: Lower value - 0.8x modifier

    Args:
        day_name: Name of the day (e.g., "Monday", "Thursday")

    Returns:
        Multiplier factor (0.8 to 1.3)
    """
    return DAY_OF_WEEK_MODIFIERS.get(day_name, 1.0)


def get_weekly_day_distribution(base_ppv_per_day: int) -> dict[str, int]:
    """
    Calculate optimal PPV distribution across week days.

    Applies day-of-week modifiers to concentrate volume on better-performing days.

    Args:
        base_ppv_per_day: Base number of PPVs per day before day optimization

    Returns:
        Dictionary mapping day names to recommended PPV count

    Example:
        >>> get_weekly_day_distribution(3)
        {'Monday': 3, 'Tuesday': 3, 'Wednesday': 4, 'Thursday': 4, 'Friday': 4, 'Saturday': 2, 'Sunday': 3}
    """
    distribution = {}
    for day, modifier in DAY_OF_WEEK_MODIFIERS.items():
        # Apply modifier and round, but ensure at least 1 PPV per day
        adjusted = max(1, round(base_ppv_per_day * modifier))
        distribution[day] = adjusted
    return distribution


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass(frozen=True)
class CreatorMetrics:
    """Input data class containing all creator metrics for volume calculation."""

    creator_id: str
    page_name: str
    display_name: str
    page_type: str  # 'paid' or 'free'

    # Core metrics
    active_fans: int = 0
    subscription_price: float = 0.0
    performance_tier: int = 3

    # Conversion metrics
    avg_purchase_rate: float = 0.0
    avg_view_rate: float = 0.0

    # Persona data
    primary_tone: str | None = None

    # Account data
    account_age_days: int = 365
    first_seen_at: str | None = None

    # Revenue data
    total_earnings: float = 0.0
    message_net: float = 0.0
    avg_revenue_per_send: float = 0.0  # For sweet spot proven performer check

    # Optional override
    fan_count_override: int | None = None

    @property
    def data_completeness(self) -> float:
        """
        Calculate how complete the creator's data is.

        Returns:
            Completeness score from 0.0 to 1.0
        """
        fields_checked = [
            self.active_fans > 0,
            self.subscription_price >= 0,
            self.performance_tier in [1, 2, 3],
            self.avg_purchase_rate >= 0,
            self.primary_tone is not None and len(self.primary_tone) > 0,
            self.account_age_days > 0,
            self.total_earnings >= 0,
        ]

        return sum(fields_checked) / len(fields_checked)


@dataclass(frozen=True)
class VolumeStrategy:
    """Output data class containing volume recommendations."""

    creator_id: str
    page_name: str
    display_name: str
    page_type: str

    # Volume recommendations
    volume_level: str
    ppv_per_day: int
    ppv_per_week: int
    bump_per_day: int
    bump_per_week: int

    # Factor breakdown
    base_volume: int = 0
    tier_factor: float = 1.0
    conversion_factor: float = 1.0
    niche_factor: float = 1.0
    price_factor: float = 1.0
    age_factor: float = 1.0
    combined_factor: float = 1.0

    # Calculated values
    raw_daily_volume: float = 0.0
    capped_daily_volume: int = 0

    # Metadata
    fan_count: int = 0
    data_completeness: float = 1.0
    calculation_notes: list[str] = field(default_factory=list)

    # Scheduling hints
    optimal_days: list[str] = field(default_factory=list)
    bump_delay_min: int = 15
    bump_delay_max: int = 45

    # Timestamps
    calculated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert strategy to dictionary for JSON serialization."""
        return asdict(self)


# ==============================================================================
# MAIN OPTIMIZER CLASS
# ==============================================================================


class MultiFactorVolumeOptimizer:
    """
    Multi-factor volume optimizer for OnlyFans creators.

    This class implements a sophisticated algorithm that considers multiple
    factors to determine optimal PPV and bump message volumes.
    """

    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize the optimizer with a database connection.

        Args:
            conn: SQLite database connection
        """
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def calculate_optimal_volume(
        self, creator_id: str, fan_count: int | None = None
    ) -> VolumeStrategy:
        """
        Calculate optimal volume for a creator.

        Args:
            creator_id: Creator UUID or page_name
            fan_count: Optional fan count override

        Returns:
            VolumeStrategy with recommendations
        """
        # Load creator metrics
        metrics = self._load_creator_metrics(creator_id)

        # CHECK FOR MANUAL OVERRIDE FIRST
        override = self._check_volume_override(metrics.creator_id)
        if override is not None:
            return override

        if fan_count is not None:
            metrics = replace(metrics, fan_count_override=fan_count)

        # Detect page type
        is_free_page = self._detect_page_type(metrics)

        # Get base volume from fan count brackets
        effective_fans = metrics.fan_count_override or metrics.active_fans
        base_level, base_ppv, base_bump = self._get_base_volume(effective_fans, is_free_page)

        # Calculate individual factors
        tier_factor = self._get_tier_factor(metrics.performance_tier)
        conversion_factor = self._get_conversion_factor(metrics.avg_purchase_rate)
        niche_factor = self._get_niche_factor(metrics.primary_tone)
        price_factor = self._get_price_factor(metrics.subscription_price, is_free_page)
        age_factor = self._get_age_factor(metrics.account_age_days)

        # Calculate combined factor
        combined_factor = tier_factor * conversion_factor * niche_factor * price_factor * age_factor

        # Calculate raw volume
        raw_daily_volume = base_ppv * combined_factor

        # Build calculation notes (initialized early for page type factor)
        notes = []

        # NEW: Apply performance-based volume tier
        # This determines the maximum PPV/day based on conversion and revenue metrics
        tier_name, tier_ppv_per_day = get_volume_tier(
            conv_rate=metrics.avg_purchase_rate,
            dollars_per_ppv=metrics.avg_revenue_per_send,
            total_revenue=metrics.total_earnings,
        )
        notes.append(f"Volume tier: {tier_name} (max {tier_ppv_per_day}/day)")

        # Apply hard caps with new minimums and tier-based maximum
        if is_free_page:
            # FREE pages: minimum 2/day, maximum from tier (up to 6/day)
            capped_daily_ppv = max(
                FREE_PAGE_MIN_PPV_DAY,  # 2 PPV/day minimum
                min(tier_ppv_per_day, FREE_PAGE_MAX_PPV_DAY, round(raw_daily_volume)),
            )
            capped_weekly_ppv = capped_daily_ppv * 7
        else:
            # PAID pages: weekly caps with tier-based maximum
            raw_weekly_volume = raw_daily_volume * 7
            tier_weekly_max = tier_ppv_per_day * 7
            capped_weekly_ppv = max(
                PAID_PAGE_MIN_PPV_WEEK,  # 14 PPV/week minimum (2/day)
                min(tier_weekly_max, PAID_PAGE_MAX_PPV_WEEK, round(raw_weekly_volume)),
            )
            capped_daily_ppv = max(2, round(capped_weekly_ppv / 7))  # Enforce 2/day floor

        # Apply page type volume efficiency factor
        page_type_factor = get_page_type_volume_factor(capped_weekly_ppv, is_free_page)
        if page_type_factor < 1.0:
            # Apply efficiency penalty but ALWAYS enforce 2/day minimum floor
            adjusted_weekly = max(14, int(capped_weekly_ppv * page_type_factor))  # 14 = 2/day * 7
            capped_weekly_ppv = adjusted_weekly
            capped_daily_ppv = max(2, capped_weekly_ppv // 7)  # Enforce 2/day floor
            notes.append(f"Page type efficiency factor: {page_type_factor:.2f}")

        # Apply sweet spot gravity (14-35 PPV/week optimal per new strategy)
        final_weekly_ppv = self._apply_sweet_spot_gravity(capped_weekly_ppv, metrics, notes)

        # CRITICAL: Enforce final 2 PPV/day floor after all adjustments
        # This is non-negotiable per user requirements
        final_daily_ppv = max(2, final_weekly_ppv // 7)
        final_weekly_ppv = max(14, final_weekly_ppv)  # Ensure weekly matches daily floor

        # Cap at tier maximum
        final_daily_ppv = min(final_daily_ppv, tier_ppv_per_day)
        final_weekly_ppv = min(final_weekly_ppv, tier_ppv_per_day * 7)

        # Calculate bump count (scaled with PPV volume)
        bump_per_day = self._get_bump_count(final_daily_ppv, is_free_page)
        bump_per_week = bump_per_day * 7

        # Get optimal days and bump delays
        optimal_days = self._get_optimal_days(is_free_page)
        bump_delay_min, bump_delay_max = self._get_bump_delays(tier_name)  # Use tier_name

        # Use tier name as volume level (new naming convention)
        volume_level = tier_name

        # Add remaining calculation notes
        if metrics.data_completeness < 0.8:
            notes.append(f"Low data completeness ({metrics.data_completeness:.0%})")
        if metrics.fan_count_override:
            notes.append(f"Fan count override: {metrics.fan_count_override}")
        if combined_factor > 1.1:
            notes.append("High combined factor - increased volume")
        if combined_factor < 0.9:
            notes.append("Low combined factor - reduced volume")

        return VolumeStrategy(
            creator_id=metrics.creator_id,
            page_name=metrics.page_name,
            display_name=metrics.display_name,
            page_type=metrics.page_type,
            volume_level=volume_level,
            ppv_per_day=final_daily_ppv,
            ppv_per_week=final_weekly_ppv if not is_free_page else final_daily_ppv * 7,
            bump_per_day=bump_per_day,
            bump_per_week=bump_per_week,
            base_volume=base_ppv,
            tier_factor=round(tier_factor, 3),
            conversion_factor=round(conversion_factor, 3),
            niche_factor=round(niche_factor, 3),
            price_factor=round(price_factor, 3),
            age_factor=round(age_factor, 3),
            combined_factor=round(combined_factor, 3),
            raw_daily_volume=round(raw_daily_volume, 2),
            capped_daily_volume=final_daily_ppv,
            fan_count=effective_fans,
            data_completeness=round(metrics.data_completeness, 2),
            calculation_notes=notes,
            optimal_days=optimal_days,
            bump_delay_min=bump_delay_min,
            bump_delay_max=bump_delay_max,
            calculated_at=datetime.now().isoformat(),
        )

    def _load_creator_metrics(self, creator_id: str) -> CreatorMetrics:
        """
        Load creator metrics from database.

        Args:
            creator_id: Creator UUID or page_name

        Returns:
            CreatorMetrics populated from database

        Raises:
            ValueError: If creator not found or creator_id is invalid
            TypeError: If creator_id is not a string
        """
        # Input validation
        if not creator_id:
            raise ValueError("creator_id cannot be empty or None")
        if not isinstance(creator_id, str):
            raise TypeError(f"creator_id must be str, got {type(creator_id).__name__}")
        creator_id = creator_id.strip()
        if len(creator_id) > 255:
            raise ValueError("creator_id exceeds maximum length of 255 characters")

        query = """
            SELECT
                c.creator_id,
                c.page_name,
                c.display_name,
                c.page_type,
                c.current_active_fans,
                c.subscription_price,
                c.performance_tier,
                c.current_total_earnings,
                c.current_message_net,
                c.first_seen_at,
                cp.primary_tone,
                cp.avg_sentiment
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.creator_id = ?
               OR c.page_name = ?
               OR c.display_name = ?
            LIMIT 1
        """

        cursor = self.conn.execute(query, (creator_id, creator_id, creator_id))
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Creator not found: {creator_id}")

        # Calculate account age
        account_age_days = 365  # Default
        if row["first_seen_at"]:
            try:
                first_seen = datetime.fromisoformat(row["first_seen_at"].replace("Z", "+00:00"))
                account_age_days = (datetime.now() - first_seen.replace(tzinfo=None)).days
            except (ValueError, TypeError):
                pass

        # Get average purchase rate and revenue per PPV message from mass_messages
        metrics_query = """
            SELECT
                AVG(CAST(purchased_count AS FLOAT) / NULLIF(sent_count, 0)) as avg_rate,
                SUM(earnings) as total_net,
                COUNT(*) as message_count
            FROM mass_messages
            WHERE creator_id = ? AND sent_count > 0 AND message_type = 'ppv'
        """
        metrics_cursor = self.conn.execute(metrics_query, (row["creator_id"],))
        metrics_row = metrics_cursor.fetchone()
        avg_purchase_rate = (
            metrics_row["avg_rate"] if metrics_row and metrics_row["avg_rate"] else 0.0
        )

        # Calculate average revenue per PPV message (not per fan send)
        avg_revenue_per_send = 0.0
        if metrics_row and metrics_row["message_count"] and metrics_row["total_net"]:
            avg_revenue_per_send = metrics_row["total_net"] / metrics_row["message_count"]

        return CreatorMetrics(
            creator_id=row["creator_id"],
            page_name=row["page_name"],
            display_name=row["display_name"],
            page_type=row["page_type"],
            active_fans=row["current_active_fans"] or 0,
            subscription_price=row["subscription_price"] or 0.0,
            performance_tier=row["performance_tier"] or 3,
            avg_purchase_rate=avg_purchase_rate,
            avg_revenue_per_send=avg_revenue_per_send,
            primary_tone=row["primary_tone"],
            account_age_days=account_age_days,
            first_seen_at=row["first_seen_at"],
            total_earnings=row["current_total_earnings"] or 0.0,
            message_net=row["current_message_net"] or 0.0,
        )

    def _check_volume_override(self, creator_id: str) -> VolumeStrategy | None:
        """
        Check for a manual volume override in the database.

        Overrides take precedence over calculated volume and are used for:
        - Creators with proven high-efficiency that can exceed sweet spot
        - Creators needing reduced volume due to over-saturation
        - Protected scarcity strategies

        Args:
            creator_id: The creator's unique identifier

        Returns:
            VolumeStrategy if an active override exists, None otherwise
        """
        query = """
            SELECT
                vo.target_weekly_ppv,
                vo.target_weekly_bump,
                vo.override_reason,
                c.page_type,
                c.page_name,
                c.display_name,
                c.current_active_fans
            FROM volume_overrides vo
            JOIN creators c ON vo.creator_id = c.creator_id
            WHERE vo.creator_id = ?
              AND vo.is_active = 1
              AND (vo.expires_at IS NULL OR vo.expires_at > datetime('now'))
        """

        try:
            cursor = self.conn.execute(query, (creator_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            weekly_ppv = row["target_weekly_ppv"]
            weekly_bump = row["target_weekly_bump"]
            reason = row["override_reason"]
            page_type = row["page_type"]
            page_name = row["page_name"]
            display_name = row["display_name"]
            fan_count = row["current_active_fans"] or 0

            # Calculate daily values from weekly
            ppv_per_day = max(1, weekly_ppv // 7)
            bump_per_day = max(1, weekly_bump // 7)

            # Determine volume level from weekly PPV
            if weekly_ppv <= 7:
                level = "Low"
            elif weekly_ppv <= 14:
                level = "Mid"
            elif weekly_ppv <= 21:
                level = "High"
            else:
                level = "Ultra"

            # Get bump delays based on level
            bump_delay_min, bump_delay_max = self._get_bump_delays(level)

            return VolumeStrategy(
                creator_id=creator_id,
                page_name=page_name,
                display_name=display_name,
                page_type=page_type,
                volume_level=level,
                ppv_per_day=ppv_per_day,
                ppv_per_week=weekly_ppv,
                bump_per_day=bump_per_day,
                bump_per_week=weekly_bump,
                fan_count=fan_count,
                calculation_notes=[f"OVERRIDE: {reason}"],
                optimal_days=OPTIMAL_DAYS.copy(),
                bump_delay_min=bump_delay_min,
                bump_delay_max=bump_delay_max,
                calculated_at=datetime.now().isoformat(),
            )

        except sqlite3.Error as e:
            # Log but don't fail - fall back to calculated volume
            print(f"Warning: Could not check volume override: {e}")
            return None

    def _can_exceed_sweet_spot(self, metrics: CreatorMetrics) -> bool:
        """
        Determine if a creator has proven performance metrics allowing them
        to exceed the 8-12 PPV/week sweet spot.

        Criteria (from analysis):
        - Revenue per send >= $100
        - Purchase rate >= 0.5%

        Args:
            metrics: The creator's performance metrics

        Returns:
            True if the creator can exceed sweet spot limits
        """
        return (
            metrics.avg_revenue_per_send >= PROVEN_PERFORMER_MIN_REV_PER_SEND
            and metrics.avg_purchase_rate >= PROVEN_PERFORMER_MIN_PURCHASE_RATE
        )

    def _apply_sweet_spot_gravity(
        self, weekly_ppv: int, metrics: CreatorMetrics, notes: list[str]
    ) -> int:
        """
        Apply sweet spot gravity to pull volume toward 14-35 PPV/week.

        The sweet spot (14-35 PPV/week, matching 2-5 PPV/day) delivers the
        best balance of total revenue and efficiency per the 2025 analysis.

        This method:
        - Enforces minimum 14/week (2/day) for all creators
        - Allows volumes above sweet spot for proven performers (up to 42/week)
        - Caps standard creators at sweet spot max + 7 (42/week)

        Args:
            weekly_ppv: Calculated weekly PPV volume
            metrics: Creator metrics for performance check
            notes: List to append notes about adjustments

        Returns:
            Adjusted weekly PPV volume
        """
        if weekly_ppv < SWEET_SPOT_MIN:
            # Below sweet spot: enforce minimum 14/week (2/day floor)
            adjusted = SWEET_SPOT_MIN  # Always at least 14/week
            if adjusted != weekly_ppv:
                notes.append(f"Sweet spot gravity: {weekly_ppv} -> {adjusted} (2/day floor)")
            return adjusted

        elif weekly_ppv > SWEET_SPOT_MAX:
            # Above sweet spot: cap based on performer status
            if self._can_exceed_sweet_spot(metrics):
                # Proven performers can reach Ultra tier (42/week = 6/day)
                max_allowed = 42  # 6 PPV/day * 7 days
                adjusted = min(weekly_ppv, max_allowed)
                if adjusted != weekly_ppv:
                    notes.append(f"Proven performer cap: {weekly_ppv} -> {adjusted}")
                return adjusted
            else:
                # Standard creators capped at sweet spot max + 7 (42/week max)
                adjusted = min(weekly_ppv, SWEET_SPOT_MAX + 7)  # 42/week
                if adjusted != weekly_ppv:
                    notes.append(f"Sweet spot gravity: {weekly_ppv} -> {adjusted} (max cap)")
                return adjusted

        # Within sweet spot (14-35/week): no change
        return weekly_ppv

    def _detect_page_type(self, metrics: CreatorMetrics) -> bool:
        """
        Detect if this is a free page using priority logic.

        Priority:
        1. Explicit page_type field
        2. Subscription price = 0
        3. Default to paid

        Args:
            metrics: Creator metrics

        Returns:
            True if free page, False if paid
        """
        # Priority 1: Explicit page type
        if metrics.page_type == "free":
            return True
        if metrics.page_type == "paid":
            return False

        # Priority 2: Subscription price
        if metrics.subscription_price == 0:
            return True

        # Default to paid
        return False

    def _get_base_volume(self, fan_count: int, is_free_page: bool) -> tuple[str, int, int]:
        """
        Get base volume from fan count brackets.

        Args:
            fan_count: Number of active fans
            is_free_page: Whether this is a free page

        Returns:
            Tuple of (level_name, ppv_per_day, bump_per_day)
        """
        config = FREE_PAGE_CONFIG if is_free_page else PAID_PAGE_CONFIG

        for (min_fans, max_fans), (level, ppv, bump) in config.items():
            if max_fans is None:
                if fan_count >= min_fans:
                    return (level, ppv, bump)
            elif min_fans <= fan_count <= max_fans:
                return (level, ppv, bump)

        # Default to lowest tier
        first_key = list(config.keys())[0]
        return config[first_key]

    def _get_tier_factor(self, performance_tier: int) -> float:
        """Get multiplier based on performance tier."""
        return TIER_FACTORS.get(performance_tier, 1.0)

    def _get_conversion_factor(self, avg_purchase_rate: float) -> float:
        """Get multiplier based on conversion rate."""
        return get_conversion_factor(avg_purchase_rate)

    def _get_niche_factor(self, primary_tone: str | None) -> float:
        """Get multiplier based on niche/persona type."""
        return get_niche_factor(primary_tone or "")

    def _get_price_factor(self, subscription_price: float, is_free_page: bool) -> float:
        """Get multiplier based on subscription price."""
        return get_subscription_price_factor(subscription_price, is_free_page)

    def _get_age_factor(self, account_age_days: int) -> float:
        """Get multiplier based on account age."""
        return get_account_age_factor(account_age_days)

    def _get_bump_count(self, ppv_per_day: int, is_free_page: bool) -> int:
        """
        Calculate bump message count based on PPV volume.

        Args:
            ppv_per_day: Number of PPV messages per day
            is_free_page: Whether this is a free page

        Returns:
            Number of bump messages per day
        """
        # Bump count scales with PPV but has different ratios
        if is_free_page:
            # Free pages: roughly 1:1 bump to PPV ratio
            bump_count = ppv_per_day
        else:
            # Paid pages: more conservative, 1-2 bumps per week
            bump_count = min(2, max(1, ppv_per_day))

        return max(MIN_BUMP_PER_DAY, min(MAX_BUMP_PER_DAY, bump_count))

    def _get_optimal_days(self, is_free_page: bool) -> list[str]:
        """
        Get optimal scheduling days.

        Args:
            is_free_page: Whether this is a free page

        Returns:
            List of optimal day names
        """
        if is_free_page:
            # Free pages: all days are optimal
            return OPTIMAL_DAYS.copy()
        else:
            # Paid pages: focus on high-engagement days
            return ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    def _get_bump_delays(self, volume_level: str) -> tuple[int, int]:
        """
        Get bump delay range based on volume level.

        Args:
            volume_level: Volume level name

        Returns:
            Tuple of (min_delay_minutes, max_delay_minutes)
        """
        return BUMP_DELAY_RANGES.get(volume_level, (20, 40))

    def _get_volume_level_name(self, ppv_per_day: int, is_free_page: bool) -> str:
        """
        Determine volume level name from daily PPV count.

        Uses the new 2025 tier naming convention:
        - Base: 2 PPV/day
        - Growth: 3 PPV/day
        - Scale: 4 PPV/day
        - High: 5 PPV/day
        - Ultra: 6 PPV/day

        Args:
            ppv_per_day: Number of PPV messages per day
            is_free_page: Whether this is a free page

        Returns:
            Volume level name (Base, Growth, Scale, High, or Ultra)
        """
        # Same thresholds for both page types in new strategy
        if ppv_per_day <= 2:
            return "Base"
        elif ppv_per_day <= 3:
            return "Growth"
        elif ppv_per_day <= 4:
            return "Scale"
        elif ppv_per_day <= 5:
            return "High"
        else:
            return "Ultra"

    def populate_volume_assignments(self, dry_run: bool = True) -> list[dict[str, Any]]:
        """
        Populate volume assignments for all active creators.

        Args:
            dry_run: If True, don't write to database

        Returns:
            List of assignment dictionaries
        """
        # Get all active creators
        query = """
            SELECT creator_id, page_name
            FROM creators
            WHERE is_active = 1
            ORDER BY current_total_earnings DESC
        """

        cursor = self.conn.execute(query)
        creators = cursor.fetchall()

        assignments = []

        for row in creators:
            try:
                strategy = self.calculate_optimal_volume(row["creator_id"])

                assignment = {
                    "creator_id": strategy.creator_id,
                    "page_name": strategy.page_name,
                    "volume_level": strategy.volume_level,
                    "ppv_per_day": strategy.ppv_per_day,
                    "bump_per_day": strategy.bump_per_day,
                    "assigned_reason": "fan_count_bracket",
                    "notes": f"Multi-factor optimization: combined_factor={strategy.combined_factor}",
                }

                assignments.append(assignment)

                if not dry_run:
                    # Deactivate existing assignments
                    self.conn.execute(
                        """
                        UPDATE volume_assignments
                        SET is_active = 0
                        WHERE creator_id = ? AND is_active = 1
                        """,
                        (strategy.creator_id,),
                    )

                    # Insert new assignment
                    self.conn.execute(
                        """
                        INSERT INTO volume_assignments (
                            creator_id, volume_level, ppv_per_day, bump_per_day,
                            assigned_by, assigned_reason, notes
                        ) VALUES (?, ?, ?, ?, 'volume_optimizer', ?, ?)
                        """,
                        (
                            strategy.creator_id,
                            strategy.volume_level,
                            strategy.ppv_per_day,
                            strategy.bump_per_day,
                            "fan_count_bracket",
                            assignment["notes"],
                        ),
                    )

            except (ValueError, KeyError, sqlite3.Error) as e:
                assignments.append(
                    {
                        "creator_id": row["creator_id"],
                        "page_name": row["page_name"],
                        "error": str(e),
                    }
                )

        if not dry_run:
            self.conn.commit()

        return assignments


# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================


def validate_volume_strategy(strategy: VolumeStrategy) -> list[str]:
    """
    Validate volume strategy against hard caps.

    Args:
        strategy: Volume strategy to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if strategy.page_type == "free":
        if strategy.ppv_per_day < FREE_PAGE_MIN_PPV_DAY:
            errors.append(
                f"PPV per day ({strategy.ppv_per_day}) below free page minimum ({FREE_PAGE_MIN_PPV_DAY})"
            )
        if strategy.ppv_per_day > FREE_PAGE_MAX_PPV_DAY:
            errors.append(
                f"PPV per day ({strategy.ppv_per_day}) exceeds free page maximum ({FREE_PAGE_MAX_PPV_DAY})"
            )
    else:
        if strategy.ppv_per_week < PAID_PAGE_MIN_PPV_WEEK:
            errors.append(
                f"PPV per week ({strategy.ppv_per_week}) below paid page minimum ({PAID_PAGE_MIN_PPV_WEEK})"
            )
        if strategy.ppv_per_week > PAID_PAGE_MAX_PPV_WEEK:
            errors.append(
                f"PPV per week ({strategy.ppv_per_week}) exceeds paid page maximum ({PAID_PAGE_MAX_PPV_WEEK})"
            )

    if strategy.bump_per_day < MIN_BUMP_PER_DAY:
        errors.append(f"Bump per day ({strategy.bump_per_day}) below minimum ({MIN_BUMP_PER_DAY})")
    if strategy.bump_per_day > MAX_BUMP_PER_DAY:
        errors.append(
            f"Bump per day ({strategy.bump_per_day}) exceeds maximum ({MAX_BUMP_PER_DAY})"
        )

    return errors


def get_volume_warnings(strategy: VolumeStrategy) -> list[str]:
    """
    Get soft warnings for volume strategy.

    Args:
        strategy: Volume strategy to check

    Returns:
        List of warning messages
    """
    warnings = []

    if strategy.data_completeness < 0.5:
        warnings.append("Very low data completeness - results may be unreliable")
    elif strategy.data_completeness < 0.8:
        warnings.append("Moderate data completeness - some factors may be estimated")

    if strategy.combined_factor > 1.3:
        warnings.append("Very high combined factor - verify volume is appropriate")
    if strategy.combined_factor < 0.7:
        warnings.append("Very low combined factor - volume may be too conservative")

    if strategy.fan_count == 0:
        warnings.append("Fan count is zero - using minimum volume")

    if strategy.age_factor < 0.8:
        warnings.append("New account - volume reduced for audience building phase")

    return warnings


# ==============================================================================
# OUTPUT FORMATTING
# ==============================================================================


def format_strategy_table(strategies: list[VolumeStrategy]) -> str:
    """
    Format strategies as a text table.

    Args:
        strategies: List of volume strategies

    Returns:
        Formatted table string
    """
    lines = []
    lines.append("-" * 120)
    lines.append(
        f"{'Creator':<20} {'Type':<6} {'Level':<6} {'PPV/Day':<8} {'PPV/Wk':<8} "
        f"{'Bump/Day':<9} {'Factor':<8} {'Fans':<10} {'Complete':<10}"
    )
    lines.append("-" * 120)

    for s in strategies:
        lines.append(
            f"{s.page_name[:20]:<20} {s.page_type:<6} {s.volume_level:<6} "
            f"{s.ppv_per_day:<8} {s.ppv_per_week:<8} {s.bump_per_day:<9} "
            f"{s.combined_factor:<8.2f} {s.fan_count:<10,} {s.data_completeness:<10.0%}"
        )

    lines.append("-" * 120)
    lines.append(f"Total creators: {len(strategies)}")

    return "\n".join(lines)


def format_strategy_detail(strategy: VolumeStrategy) -> str:
    """
    Format a single strategy with full details.

    Args:
        strategy: Volume strategy to format

    Returns:
        Formatted detail string
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"VOLUME STRATEGY: {strategy.display_name}")
    lines.append("=" * 60)
    lines.append("")

    lines.append("CREATOR INFO")
    lines.append("-" * 40)
    lines.append(f"  Page Name:      {strategy.page_name}")
    lines.append(f"  Page Type:      {strategy.page_type}")
    lines.append(f"  Active Fans:    {strategy.fan_count:,}")
    lines.append(f"  Data Quality:   {strategy.data_completeness:.0%}")
    lines.append("")

    lines.append("VOLUME RECOMMENDATIONS")
    lines.append("-" * 40)
    lines.append(f"  Volume Level:   {strategy.volume_level}")
    lines.append(f"  PPV per Day:    {strategy.ppv_per_day}")
    lines.append(f"  PPV per Week:   {strategy.ppv_per_week}")
    lines.append(f"  Bump per Day:   {strategy.bump_per_day}")
    lines.append(f"  Bump per Week:  {strategy.bump_per_week}")
    lines.append("")

    lines.append("FACTOR BREAKDOWN")
    lines.append("-" * 40)
    lines.append(f"  Base Volume:       {strategy.base_volume}")
    lines.append(f"  Tier Factor:       {strategy.tier_factor:.3f}")
    lines.append(f"  Conversion Factor: {strategy.conversion_factor:.3f}")
    lines.append(f"  Niche Factor:      {strategy.niche_factor:.3f}")
    lines.append(f"  Price Factor:      {strategy.price_factor:.3f}")
    lines.append(f"  Age Factor:        {strategy.age_factor:.3f}")
    lines.append("  --------------------------------")
    lines.append(f"  Combined Factor:   {strategy.combined_factor:.3f}")
    lines.append(f"  Raw Daily Volume:  {strategy.raw_daily_volume:.2f}")
    lines.append(f"  Capped Daily:      {strategy.capped_daily_volume}")
    lines.append("")

    lines.append("SCHEDULING HINTS")
    lines.append("-" * 40)
    lines.append(f"  Optimal Days:   {', '.join(strategy.optimal_days)}")
    lines.append(f"  Bump Delay:     {strategy.bump_delay_min}-{strategy.bump_delay_max} minutes")
    lines.append("")

    # Validation
    errors = validate_volume_strategy(strategy)
    warnings = get_volume_warnings(strategy)

    if errors:
        lines.append("ERRORS")
        lines.append("-" * 40)
        for err in errors:
            lines.append(f"  [ERROR] {err}")
        lines.append("")

    if warnings:
        lines.append("WARNINGS")
        lines.append("-" * 40)
        for warn in warnings:
            lines.append(f"  [WARN] {warn}")
        lines.append("")

    if strategy.calculation_notes:
        lines.append("NOTES")
        lines.append("-" * 40)
        for note in strategy.calculation_notes:
            lines.append(f"  - {note}")
        lines.append("")

    lines.append(f"Calculated at: {strategy.calculated_at}")
    lines.append("=" * 60)

    return "\n".join(lines)


# ==============================================================================
# CLI INTERFACE
# ==============================================================================


def get_db_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get database connection with row factory."""
    path = db_path or DB_PATH

    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Multi-factor volume optimization for OnlyFans creators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Calculate volume for single creator
    python volume_optimizer.py --creator missalexa

    # Calculate with fan count override
    python volume_optimizer.py --creator missalexa --fan-count 5000

    # Calculate for all creators (table format)
    python volume_optimizer.py --all --format table

    # Preview database population
    python volume_optimizer.py --populate --dry-run

    # Write to database
    python volume_optimizer.py --populate
        """,
    )

    # Creator selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--creator", help="Creator page_name or creator_id")
    group.add_argument("-a", "--all", action="store_true", help="Calculate for all active creators")
    group.add_argument("--populate", action="store_true", help="Populate volume_assignments table")

    # Options
    parser.add_argument("--fan-count", type=int, help="Override fan count for calculation")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing to database"
    )
    parser.add_argument(
        "--format",
        choices=["json", "table", "detail"],
        default="detail",
        help="Output format (default: detail)",
    )
    parser.add_argument("--db", type=Path, help=f"Database path (default: {DB_PATH})")

    args = parser.parse_args()

    try:
        conn = get_db_connection(args.db)
        optimizer = MultiFactorVolumeOptimizer(conn)

        if args.creator:
            # Single creator calculation
            strategy = optimizer.calculate_optimal_volume(args.creator, fan_count=args.fan_count)

            if args.format == "json":
                print(json.dumps(strategy.to_dict(), indent=2))
            elif args.format == "table":
                print(format_strategy_table([strategy]))
            else:
                print(format_strategy_detail(strategy))

        elif args.all:
            # All creators
            query = "SELECT creator_id FROM creators WHERE is_active = 1"
            cursor = conn.execute(query)

            strategies = []
            for row in cursor.fetchall():
                try:
                    strategy = optimizer.calculate_optimal_volume(row["creator_id"])
                    strategies.append(strategy)
                except (ValueError, KeyError, sqlite3.Error) as e:
                    print(f"Error processing {row['creator_id']}: {e}", file=sys.stderr)

            if args.format == "json":
                print(json.dumps([s.to_dict() for s in strategies], indent=2))
            elif args.format == "table":
                print(format_strategy_table(strategies))
            else:
                for strategy in strategies:
                    print(format_strategy_detail(strategy))
                    print("\n")

        elif args.populate:
            # Populate volume_assignments
            assignments = optimizer.populate_volume_assignments(dry_run=args.dry_run)

            if args.dry_run:
                print("DRY RUN - No changes written to database\n")
            else:
                print("Volume assignments updated\n")

            if args.format == "json":
                print(json.dumps(assignments, indent=2))
            else:
                print("-" * 80)
                print(
                    f"{'Creator':<25} {'Level':<8} {'PPV/Day':<10} {'Bump/Day':<10} {'Status':<15}"
                )
                print("-" * 80)

                for a in assignments:
                    if "error" in a:
                        status = f"ERROR: {a['error'][:20]}"
                    else:
                        status = "OK"

                    print(
                        f"{a.get('page_name', a['creator_id'])[:25]:<25} "
                        f"{a.get('volume_level', 'N/A'):<8} "
                        f"{a.get('ppv_per_day', 'N/A'):<10} "
                        f"{a.get('bump_per_day', 'N/A'):<10} "
                        f"{status:<15}"
                    )

                print("-" * 80)
                print(f"Total: {len(assignments)} creators processed")

        conn.close()
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
