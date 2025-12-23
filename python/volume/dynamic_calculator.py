"""
Dynamic volume calculation engine.

Calculates optimal send volumes based on real-time performance metrics
rather than static tier assignments. This replaces the legacy static
volume_assignments table with intelligent, adaptive volume allocation.

Key Features:
    - Fan count-based tier classification
    - Saturation-aware volume reduction (smooth interpolation)
    - Opportunity-based volume increase (when saturation allows)
    - Revenue trend adjustments
    - New creator detection with conservative defaults
    - Decimal precision for consistent rounding

Usage:
    from python.volume.dynamic_calculator import (
        PerformanceContext,
        calculate_dynamic_volume,
    )

    context = PerformanceContext(
        fan_count=12434,
        page_type="paid",
        saturation_score=45,
        opportunity_score=65,
    )
    config = calculate_dynamic_volume(context)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
import os
import sqlite3
import time
from typing import Optional

from python.exceptions import InsufficientDataError
from python.logging_config import get_logger, log_operation_start, log_operation_end
from python.models.volume import VolumeConfig, VolumeTier
from python.observability.metrics import get_metrics, timed, with_error_tracking
from python.volume.config_loader import get_config
from python.volume.tier_config import (
    TIER_CONFIGS,
    VOLUME_BOUNDS,
    SATURATION_THRESHOLDS,
    OPPORTUNITY_THRESHOLDS,
)
from python.volume.bump_multiplier import (
    BumpMultiplierResult,
    FollowupVolumeResult,
    calculate_bump_multiplier,
    calculate_followup_volume,
    get_creator_content_category,
    apply_bump_to_engagement,
    BUMP_MULTIPLIERS,
    DEFAULT_CONTENT_CATEGORY,
)

# Module logger with structured output
logger = get_logger(__name__)


@dataclass
class PerformanceContext:
    """Input context for dynamic volume calculation.

    Aggregates all metrics needed to calculate optimal send volumes
    for a creator. Provides sensible defaults for optional metrics.

    Attributes:
        fan_count: Number of fans/subscribers (required).
        page_type: 'paid' or 'free' page classification (required).
        saturation_score: Audience fatigue indicator (0-100, default 50).
            Higher values indicate audience is receiving too many messages.
        opportunity_score: Growth potential indicator (0-100, default 50).
            Higher values indicate untapped audience engagement potential.
        revenue_trend: Revenue change percentage over period (default 0).
            Negative values indicate declining revenue.
        view_rate_trend: View rate change percentage (default 0).
            Measures content consumption velocity changes.
        purchase_rate_trend: Purchase rate change percentage (default 0).
            Measures conversion rate changes.
        is_new_creator: Whether this is a new creator with limited data.
        message_count: Number of messages analyzed for this creator.
    """

    fan_count: int
    page_type: str  # 'paid' or 'free'
    saturation_score: float = 50.0  # 0-100
    opportunity_score: float = 50.0  # 0-100
    revenue_trend: float = 0.0  # % change
    view_rate_trend: float = 0.0  # % change
    purchase_rate_trend: float = 0.0  # % change
    is_new_creator: bool = False
    message_count: int = 0

    def __post_init__(self) -> None:
        """Validate context on initialization."""
        if self.page_type not in ("paid", "free"):
            raise ValueError(f"Invalid page_type: {self.page_type}")
        if self.fan_count < 0:
            raise ValueError(f"fan_count must be non-negative: {self.fan_count}")
        if not 0 <= self.saturation_score <= 100:
            raise ValueError(
                f"saturation_score must be 0-100: {self.saturation_score}"
            )
        if not 0 <= self.opportunity_score <= 100:
            raise ValueError(
                f"opportunity_score must be 0-100: {self.opportunity_score}"
            )


def get_volume_tier(fan_count: int) -> VolumeTier:
    """Classify volume tier based on fan count.

    Uses fan count thresholds to determine appropriate volume tier:
    - LOW: 0-999 fans
    - MID: 1,000-4,999 fans
    - HIGH: 5,000-14,999 fans
    - ULTRA: 15,000+ fans

    Args:
        fan_count: Number of fans/subscribers.

    Returns:
        VolumeTier enum value corresponding to fan count range.

    Raises:
        ValueError: If fan_count is negative.
    """
    if fan_count < 0:
        raise ValueError(f"fan_count must be non-negative: {fan_count}")

    if fan_count < 1000:
        return VolumeTier.LOW
    elif fan_count < 5000:
        return VolumeTier.MID
    elif fan_count < 15000:
        return VolumeTier.HIGH
    else:
        return VolumeTier.ULTRA


def _round_volume(value: float) -> int:
    """Round volume using banker's rounding for consistency.

    Uses Decimal for precise intermediate calculations to avoid
    floating point errors that could cause inconsistent rounding.

    Args:
        value: Float value to round.

    Returns:
        Rounded integer value.
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _calculate_saturation_multiplier(saturation_score: float) -> float:
    """Calculate volume multiplier based on saturation level (step function).

    High saturation reduces volume to prevent audience fatigue.
    This is the legacy step function - prefer _calculate_saturation_multiplier_smooth
    for more gradual adjustments.

    Args:
        saturation_score: Audience saturation score (0-100).

    Returns:
        Multiplier between 0.7 and 1.0.
    """
    if saturation_score >= SATURATION_THRESHOLDS["high"]:  # 70
        return 0.7
    elif saturation_score >= SATURATION_THRESHOLDS["medium"]:  # 50
        return 0.9
    return 1.0


def _calculate_saturation_multiplier_smooth(saturation_score: float) -> float:
    """Calculate volume multiplier with smooth interpolation.

    Instead of hard thresholds (0.7, 0.9, 1.0), uses linear interpolation:
    - 0-30: 1.0 (no reduction)
    - 30-50: 1.0 -> 0.9 (gradual reduction)
    - 50-70: 0.9 -> 0.7 (accelerating reduction)
    - 70-100: 0.7 (max reduction)

    Args:
        saturation_score: Audience saturation score (0-100).

    Returns:
        Smoothly interpolated multiplier between 0.7 and 1.0.
    """
    config = get_config()

    # Use config-based interpolation if available
    if config.smooth_interpolation.enabled:
        return config.smooth_interpolation.interpolate_saturation(saturation_score)

    # Fallback to manual interpolation
    thresholds = config.saturation_thresholds
    multipliers = config.saturation_multipliers

    if saturation_score <= thresholds.low:
        return multipliers.normal  # 1.0

    elif saturation_score <= thresholds.medium:
        # Linear interpolation from normal (1.0) to medium (0.9)
        t = (saturation_score - thresholds.low) / (thresholds.medium - thresholds.low)
        return multipliers.normal - (multipliers.normal - multipliers.medium) * t

    elif saturation_score <= thresholds.high:
        # Linear interpolation from medium (0.9) to high (0.7)
        t = (saturation_score - thresholds.medium) / (thresholds.high - thresholds.medium)
        return multipliers.medium - (multipliers.medium - multipliers.high) * t

    else:
        return multipliers.high  # 0.7


def _calculate_opportunity_multiplier(
    opportunity_score: float,
    saturation_score: float,
) -> float:
    """Calculate volume multiplier based on opportunity level (step function).

    High opportunity with low saturation allows volume increase.
    This prevents increasing volume when audience is already saturated.

    Args:
        opportunity_score: Growth opportunity score (0-100).
        saturation_score: Audience saturation score (0-100).

    Returns:
        Multiplier between 1.0 and 1.2.
    """
    if (
        opportunity_score >= OPPORTUNITY_THRESHOLDS["high"]
        and saturation_score < SATURATION_THRESHOLDS["medium"]
    ):
        return 1.2
    elif (
        opportunity_score >= OPPORTUNITY_THRESHOLDS["medium"]
        and saturation_score < SATURATION_THRESHOLDS["low"]
    ):
        return 1.1
    return 1.0


def _calculate_opportunity_multiplier_smooth(
    opportunity_score: float,
    saturation_score: float,
) -> float:
    """Calculate opportunity multiplier with smooth interpolation.

    Opportunity boost is only applied when saturation is below threshold.
    Uses linear interpolation for gradual adjustments:
    - 0-30: 1.0 (no boost, regardless of saturation)
    - 30-50: 1.0 -> 1.1 (if saturation < 30)
    - 50-70: 1.0 -> 1.1 (if saturation < 50) or 1.1 -> 1.2 (if saturation < 30)
    - 70-100: 1.2 (max boost, if saturation < 50)

    Args:
        opportunity_score: Growth opportunity score (0-100).
        saturation_score: Audience saturation score (0-100).

    Returns:
        Smoothly interpolated multiplier between 1.0 and 1.2.
    """
    config = get_config()
    thresholds = config.opportunity_thresholds
    sat_thresholds = config.saturation_thresholds
    multipliers = config.opportunity_multipliers

    # No opportunity boost if saturation is too high
    if saturation_score >= sat_thresholds.medium:
        return multipliers.normal  # 1.0

    # High opportunity (>= 70) with low-medium saturation (< 50)
    if opportunity_score >= thresholds.high:
        if saturation_score < sat_thresholds.medium:
            return multipliers.high  # 1.2
        return multipliers.normal

    # Medium opportunity (50-70)
    if opportunity_score >= thresholds.medium:
        # Only boost if saturation is very low
        if saturation_score < sat_thresholds.low:
            # Interpolate from normal to medium
            t = (opportunity_score - thresholds.medium) / (thresholds.high - thresholds.medium)
            return multipliers.normal + (multipliers.medium - multipliers.normal) * t
        return multipliers.normal

    # Low opportunity (< 50)
    return multipliers.normal


def _calculate_trend_adjustment(revenue_trend: float) -> int:
    """Calculate discrete volume adjustment based on revenue trend.

    Strong positive trends earn +1, strong negative trends incur -1.

    Args:
        revenue_trend: Revenue change percentage.

    Returns:
        Integer adjustment (-1, 0, or +1).
    """
    config = get_config()
    negative_threshold, positive_threshold = config.trend_thresholds

    if revenue_trend < negative_threshold:
        return -1
    elif revenue_trend > positive_threshold:
        return 1
    return 0


def _apply_bounds(value: int, category: str) -> int:
    """Clamp value to configured bounds for category.

    Args:
        value: Raw calculated value.
        category: Category key ('revenue', 'engagement', 'retention').

    Returns:
        Value clamped to category bounds.
    """
    min_val, max_val = VOLUME_BOUNDS[category]
    return max(min_val, min(max_val, value))


def _apply_new_creator_defaults(context: PerformanceContext) -> PerformanceContext:
    """Apply conservative defaults for new creators.

    New creators (< 5 messages or flagged as new) get conservative
    default scores instead of calculated values to prevent over-sending.

    Args:
        context: Original performance context.

    Returns:
        Modified context with default scores if applicable.
    """
    config = get_config()
    nc_config = config.new_creator_config

    # Check if this is a new creator
    is_new = (
        context.is_new_creator
        or context.message_count < nc_config.min_messages_for_analysis
    )

    if not is_new:
        return context

    # Return new context with conservative defaults
    return PerformanceContext(
        fan_count=context.fan_count,
        page_type=context.page_type,
        saturation_score=nc_config.default_saturation,
        opportunity_score=nc_config.default_opportunity,
        revenue_trend=0.0,  # No trend data for new creators
        view_rate_trend=0.0,
        purchase_rate_trend=0.0,
        is_new_creator=True,
        message_count=context.message_count,
    )


@timed("volume.calculate_dynamic", log_slow_threshold_ms=200)
def calculate_dynamic_volume(
    context: PerformanceContext,
    use_smooth_interpolation: bool = True,
) -> VolumeConfig:
    """Calculate optimal volume configuration dynamically.

    Uses a multi-step algorithm to determine optimal send volumes:

    1. **New creator check**: Apply conservative defaults if insufficient data.
    2. **Base tier**: Determines starting volumes from fan count tier.
    3. **Saturation adjustment**: Reduces volume if audience is saturated.
    4. **Opportunity adjustment**: Increases volume if opportunity exists
       and saturation is low (prevents increasing when already fatigued).
    5. **Trend adjustment**: Fine-tunes based on revenue performance trend.
    6. **Bounds enforcement**: Ensures final values are within safe limits.

    This replaces static volume_assignments with adaptive calculation,
    fixing issues like Grace Bennett (12,434 fans) being incorrectly
    assigned to "Low" tier.

    Args:
        context: PerformanceContext with creator metrics.
        use_smooth_interpolation: If True, use smooth threshold interpolation
            instead of step functions (default True).

    Returns:
        VolumeConfig with dynamically calculated volume values.

    Example:
        >>> context = PerformanceContext(
        ...     fan_count=12434,
        ...     page_type="paid",
        ...     saturation_score=45,
        ...     opportunity_score=65,
        ...     revenue_trend=10
        ... )
        >>> config = calculate_dynamic_volume(context)
        >>> config.tier
        <VolumeTier.HIGH: 'high'>
        >>> config.revenue_per_day
        5
    """
    log_operation_start(
        logger,
        "calculate_dynamic_volume",
        fan_count=context.fan_count,
        page_type=context.page_type,
        saturation_score=context.saturation_score,
        opportunity_score=context.opportunity_score,
    )
    start_time = time.perf_counter()

    # Step 0: Apply new creator defaults if needed
    context = _apply_new_creator_defaults(context)

    # Step 1: Base tier from fan count
    tier = get_volume_tier(context.fan_count)
    base = TIER_CONFIGS[tier][context.page_type]

    logger.debug(
        "Determined volume tier",
        extra={
            "tier": tier.value,
            "base_revenue": base["revenue"],
            "base_engagement": base["engagement"],
            "base_retention": base["retention"],
        }
    )

    # Step 2: Saturation adjustment (reduce if saturated)
    if use_smooth_interpolation:
        sat_mult = _calculate_saturation_multiplier_smooth(context.saturation_score)
    else:
        sat_mult = _calculate_saturation_multiplier(context.saturation_score)

    # Step 3: Opportunity adjustment (increase if opportunity + low saturation)
    if use_smooth_interpolation:
        opp_mult = _calculate_opportunity_multiplier_smooth(
            context.opportunity_score,
            context.saturation_score,
        )
    else:
        opp_mult = _calculate_opportunity_multiplier(
            context.opportunity_score,
            context.saturation_score,
        )

    logger.debug(
        "Calculated multipliers",
        extra={
            "saturation_multiplier": round(sat_mult, 3),
            "opportunity_multiplier": round(opp_mult, 3),
            "use_smooth_interpolation": use_smooth_interpolation,
        }
    )

    # Step 4: Trend adjustment
    trend_adj = _calculate_trend_adjustment(context.revenue_trend)

    # Step 5: Calculate final values with bounds
    # Apply multipliers and trend adjustment to revenue
    revenue_raw = _round_volume(base["revenue"] * sat_mult * opp_mult) + trend_adj
    revenue = _apply_bounds(revenue_raw, "revenue")

    # Engagement uses multipliers but not trend adjustment
    engagement_raw = _round_volume(base["engagement"] * sat_mult * opp_mult)
    engagement = _apply_bounds(engagement_raw, "engagement")

    # Retention: free pages must have 0, paid pages use adjusted value
    # BUG FIX: Apply saturation multiplier to retention as well
    if context.page_type == "free":
        retention = 0
    else:
        # Apply saturation multiplier only (not opportunity - retention is defensive)
        retention_raw = _round_volume(base["retention"] * sat_mult)
        retention = _apply_bounds(retention_raw, "retention")

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    log_operation_end(
        logger,
        "calculate_dynamic_volume",
        duration_ms=elapsed_ms,
        tier=tier.value,
        revenue_per_day=revenue,
        engagement_per_day=engagement,
        retention_per_day=retention,
    )

    # Record metrics
    get_metrics().increment("volume.calculations", tags={"tier": tier.value})

    return VolumeConfig(
        tier=tier,
        revenue_per_day=revenue,
        engagement_per_day=engagement,
        retention_per_day=retention,
        fan_count=context.fan_count,
        page_type=context.page_type,
    )


def calculate_dynamic_volume_legacy(context: PerformanceContext) -> VolumeConfig:
    """Calculate volume using legacy step-function thresholds.

    This function maintains backwards compatibility with the original
    algorithm that uses step functions instead of smooth interpolation.

    Args:
        context: PerformanceContext with creator metrics.

    Returns:
        VolumeConfig with calculated volume values.
    """
    return calculate_dynamic_volume(context, use_smooth_interpolation=False)


# =============================================================================
# Optimized Volume Result and Unified Pipeline
# =============================================================================


@dataclass
class OptimizedVolumeResult:
    """Complete volume calculation result with all adjustments applied.

    This dataclass represents the output of the fully optimized volume
    calculation pipeline, including all module adjustments, weekly
    distribution, and metadata about what was applied.

    Attributes:
        base_config: VolumeConfig from initial tier calculation.
        final_config: VolumeConfig after all adjustments.
        weekly_distribution: Dict mapping day index (0-6) to adjusted volume.
        content_allocations: Dict mapping content type to allocated volume.
        adjustments_applied: List of adjustment names that were applied.
        confidence_score: Overall confidence in the calculation (0.0-1.0).
        elasticity_capped: Whether diminishing returns capping was applied.
        caption_warnings: List of caption shortage warnings.
        prediction_id: Database ID for tracking prediction accuracy.
        fused_saturation: Saturation score after multi-horizon fusion.
        fused_opportunity: Opportunity score after multi-horizon fusion.
        divergence_detected: Whether multi-horizon divergence was detected.
        dow_multipliers_used: Day-of-week multipliers applied.
        message_count: Total messages analyzed for confidence.
    """

    base_config: VolumeConfig
    final_config: VolumeConfig
    weekly_distribution: dict[int, int] = field(default_factory=dict)
    content_allocations: dict[str, int] = field(default_factory=dict)
    adjustments_applied: list[str] = field(default_factory=list)
    confidence_score: float = 1.0
    elasticity_capped: bool = False
    caption_warnings: list[str] = field(default_factory=list)
    prediction_id: Optional[int] = None
    fused_saturation: float = 50.0
    fused_opportunity: float = 50.0
    divergence_detected: bool = False
    dow_multipliers_used: dict[int, float] = field(default_factory=dict)
    message_count: int = 0
    # Bump multiplier fields (Volume Optimization v3.0)
    bump_multiplier: float = 1.0
    bump_adjusted_engagement: int = 0
    content_category: str = "softcore"
    bump_capped: bool = False
    # Followup scaling fields
    followup_volume_scaled: int = 0
    followup_rate_used: float = 0.80

    @property
    def total_weekly_volume(self) -> int:
        """Total weekly volume across all days."""
        return sum(self.weekly_distribution.values())

    @property
    def has_warnings(self) -> bool:
        """Whether any caption warnings exist."""
        return len(self.caption_warnings) > 0

    @property
    def is_high_confidence(self) -> bool:
        """Whether confidence score indicates reliable results."""
        return self.confidence_score >= 0.6


def calculate_optimized_volume(
    context: PerformanceContext,
    creator_id: str,
    db_path: Optional[str] = None,
    week_start: Optional[str] = None,
    track_prediction: bool = True,
) -> OptimizedVolumeResult:
    """Calculate fully optimized volume using all integrated modules.

    This is the unified pipeline function that orchestrates all volume
    optimization modules to produce a complete, optimized volume result.

    The pipeline executes in the following order:
    1. Base calculation from fan count tier
    2. Apply saturation/opportunity multipliers (smooth interpolation)
    3. Apply multi-horizon score fusion (7d/14d/30d)
    4. Apply DOW multipliers for weekly distribution
    5. Apply content-type weighting
    6. Apply confidence adjustment (dampen with low data)
    7. Check elasticity bounds (diminishing returns cap)
    8. Verify caption pool can support volume
    9. Track prediction for later accuracy measurement

    Args:
        context: PerformanceContext with creator metrics.
        creator_id: Creator identifier for database lookups.
        db_path: Path to SQLite database. Uses EROS_DB_PATH env var if not provided.
        week_start: Week start date (YYYY-MM-DD). Defaults to next Monday.
        track_prediction: Whether to save prediction for accuracy tracking.

    Returns:
        OptimizedVolumeResult with all adjustments and metadata.

    Raises:
        InsufficientDataError: If critical data is missing and cannot proceed.

    Example:
        >>> context = PerformanceContext(
        ...     fan_count=12434,
        ...     page_type="paid",
        ...     saturation_score=45,
        ...     opportunity_score=65,
        ... )
        >>> result = calculate_optimized_volume(
        ...     context,
        ...     creator_id="alexia",
        ...     week_start="2025-12-16"
        ... )
        >>> print(f"Final revenue: {result.final_config.revenue_per_day}")
        >>> print(f"Confidence: {result.confidence_score}")
    """
    # Resolve database path
    if db_path is None:
        db_path = os.environ.get(
            "EROS_DB_PATH",
            "./database/eros_sd_main.db"
        )

    # Resolve week start date
    if week_start is None:
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        week_start = (today + timedelta(days=days_until_monday)).isoformat()

    adjustments_applied: list[str] = []

    # -------------------------------------------------------------------------
    # Step 1: Base calculation from tier
    # -------------------------------------------------------------------------
    logger.info(
        "Starting optimized volume calculation",
        extra={
            "creator_id": creator_id,
            "fan_count": context.fan_count,
            "page_type": context.page_type,
        }
    )

    base_config = calculate_dynamic_volume(context, use_smooth_interpolation=True)
    adjustments_applied.append("base_tier_calculation")

    # -------------------------------------------------------------------------
    # Step 2: Multi-horizon score fusion (7d/14d/30d)
    # -------------------------------------------------------------------------
    fused_saturation = context.saturation_score
    fused_opportunity = context.opportunity_score
    divergence_detected = False
    message_count = context.message_count

    try:
        from python.volume.multi_horizon import (
            MultiHorizonAnalyzer,
            HorizonScores,
            fuse_scores,
            fetch_horizon_scores,
        )

        conn = sqlite3.connect(db_path)
        try:
            horizons = fetch_horizon_scores(conn, creator_id)
            fused = fuse_scores(horizons)

            if fused.is_reliable:
                fused_saturation = fused.saturation_score
                fused_opportunity = fused.opportunity_score
                divergence_detected = fused.divergence_detected
                adjustments_applied.append("multi_horizon_fusion")

                # Sum message counts from all horizons
                for h in fused.horizons.values():
                    if h.is_available:
                        message_count = max(message_count, h.message_count)

                logger.info(
                    "Applied multi-horizon fusion",
                    extra={
                        "fused_saturation": fused_saturation,
                        "fused_opportunity": fused_opportunity,
                        "divergence_detected": divergence_detected,
                    }
                )
        finally:
            conn.close()

    except sqlite3.OperationalError as db_error:
        logger.error(
            f"Database error in multi-horizon fusion: {db_error}",
            extra={"creator_id": creator_id, "db_path": db_path}
        )
    except (ValueError, TypeError) as validation_error:
        logger.warning(
            f"Validation error in multi-horizon fusion: {validation_error}",
            extra={"creator_id": creator_id}
        )
    except ImportError as import_error:
        logger.warning(
            f"Import error in multi-horizon fusion (module not available): {import_error}"
        )
    except Exception as unexpected:
        logger.exception(
            f"Unexpected error in multi-horizon fusion, using context scores: {unexpected}"
        )

    # Update context with fused scores for recalculation
    fused_context = PerformanceContext(
        fan_count=context.fan_count,
        page_type=context.page_type,
        saturation_score=fused_saturation,
        opportunity_score=fused_opportunity,
        revenue_trend=context.revenue_trend,
        view_rate_trend=context.view_rate_trend,
        purchase_rate_trend=context.purchase_rate_trend,
        is_new_creator=context.is_new_creator,
        message_count=message_count,
    )

    # Recalculate with fused scores
    fused_config = calculate_dynamic_volume(fused_context, use_smooth_interpolation=True)

    # -------------------------------------------------------------------------
    # Step 3: Confidence adjustment (dampen with low data)
    # -------------------------------------------------------------------------
    confidence_score = 1.0

    try:
        from python.volume.confidence import (
            calculate_confidence,
            apply_confidence_to_multipliers,
            ConfidenceAdjustedVolume,
            calculate_confidence_adjusted_volume,
        )

        confidence_result = calculate_confidence(message_count)
        confidence_score = confidence_result.confidence

        if confidence_result.is_low_confidence:
            # Calculate saturation and opportunity multipliers
            sat_mult = _calculate_saturation_multiplier_smooth(fused_saturation)
            opp_mult = _calculate_opportunity_multiplier_smooth(
                fused_opportunity,
                fused_saturation,
            )

            # Dampen multipliers toward neutral
            adj_sat, adj_opp, _ = apply_confidence_to_multipliers(
                sat_mult,
                opp_mult,
                message_count,
            )

            # Get base tier values
            tier = get_volume_tier(context.fan_count)
            base_values = TIER_CONFIGS[tier][context.page_type]

            # Calculate adjusted volumes with dampened multipliers
            combined_mult = adj_sat * adj_opp
            revenue_adj = _round_volume(base_values["revenue"] * combined_mult)
            engagement_adj = _round_volume(base_values["engagement"] * combined_mult)

            if context.page_type == "free":
                retention_adj = 0
            else:
                retention_adj = _round_volume(base_values["retention"] * adj_sat)

            # Apply bounds
            revenue_adj = _apply_bounds(revenue_adj, "revenue")
            engagement_adj = _apply_bounds(engagement_adj, "engagement")
            retention_adj = _apply_bounds(retention_adj, "retention")

            # Create new config with dampened values
            fused_config = VolumeConfig(
                tier=fused_config.tier,
                revenue_per_day=revenue_adj,
                engagement_per_day=engagement_adj,
                retention_per_day=retention_adj,
                fan_count=context.fan_count,
                page_type=context.page_type,
            )

            adjustments_applied.append("confidence_dampening")
            logger.info(
                "Applied confidence dampening",
                extra={
                    "confidence": confidence_score,
                    "tier_name": confidence_result.tier_name,
                    "message_count": message_count,
                }
            )

    except (ValueError, TypeError) as validation_error:
        logger.warning(
            f"Validation error in confidence adjustment: {validation_error}",
            extra={"message_count": message_count}
        )
    except ImportError as import_error:
        logger.warning(
            f"Import error in confidence adjustment (module not available): {import_error}"
        )
    except Exception as unexpected:
        logger.exception(
            f"Unexpected error in confidence adjustment: {unexpected}"
        )

    # -------------------------------------------------------------------------
    # Step 3.5: Bump multiplier for engagement (Volume Optimization v3.0)
    # -------------------------------------------------------------------------
    bump_multiplier = 1.0
    bump_adjusted_engagement = fused_config.engagement_per_day
    content_category = DEFAULT_CONTENT_CATEGORY
    bump_capped = False

    try:
        # Get content category from database
        conn = sqlite3.connect(db_path)
        try:
            content_category = get_creator_content_category(conn, creator_id)
        finally:
            conn.close()

        # Calculate bump multiplier
        bump_result = calculate_bump_multiplier(
            content_category=content_category,
            tier=fused_config.tier,
            page_type=context.page_type,
        )

        bump_multiplier = bump_result.multiplier
        bump_capped = bump_result.capped

        # Apply bump to engagement
        bump_adjusted_engagement = apply_bump_to_engagement(
            base_engagement=fused_config.engagement_per_day,
            bump_multiplier=bump_multiplier,
        )

        # Update fused_config with adjusted engagement
        if bump_adjusted_engagement != fused_config.engagement_per_day:
            fused_config = VolumeConfig(
                tier=fused_config.tier,
                revenue_per_day=fused_config.revenue_per_day,
                engagement_per_day=bump_adjusted_engagement,
                retention_per_day=fused_config.retention_per_day,
                fan_count=context.fan_count,
                page_type=context.page_type,
            )
            adjustments_applied.append("bump_multiplier")
            logger.info(
                "Applied bump multiplier",
                extra={
                    "content_category": content_category,
                    "bump_multiplier": bump_multiplier,
                    "original_engagement": fused_config.engagement_per_day,
                    "adjusted_engagement": bump_adjusted_engagement,
                    "bump_capped": bump_capped,
                }
            )

    except sqlite3.OperationalError as db_error:
        logger.error(
            f"Database error in bump multiplier calculation: {db_error}",
            extra={"creator_id": creator_id, "db_path": db_path}
        )
    except (ValueError, TypeError) as validation_error:
        logger.warning(
            f"Validation error in bump multiplier calculation: {validation_error}",
            extra={"creator_id": creator_id, "content_category": content_category}
        )
    except Exception as unexpected:
        logger.exception(
            f"Unexpected error in bump multiplier calculation: {unexpected}"
        )

    # -------------------------------------------------------------------------
    # Step 3.6: Followup volume scaling (Volume Optimization v3.0)
    # -------------------------------------------------------------------------
    followup_volume_scaled = 0
    followup_rate_used = 0.80

    try:
        # Estimate PPV count from revenue allocation
        estimated_ppv_count = fused_config.revenue_per_day

        # Calculate scaled followup volume
        followup_result = calculate_followup_volume(
            ppv_count=estimated_ppv_count,
            tier_max=5,  # Hard cap from send_type constraint
            confidence_score=confidence_score,
        )

        followup_volume_scaled = followup_result.followup_count
        followup_rate_used = followup_result.followup_rate

        adjustments_applied.append("followup_scaling")
        logger.info(
            "Calculated scaled followup volume",
            extra={
                "ppv_count": estimated_ppv_count,
                "followup_volume": followup_volume_scaled,
                "rate_used": followup_rate_used,
            }
        )

    except (ValueError, TypeError) as validation_error:
        logger.warning(
            f"Validation error in followup volume calculation: {validation_error}",
            extra={"ppv_count": estimated_ppv_count, "confidence_score": confidence_score}
        )
        followup_volume_scaled = min(fused_config.revenue_per_day, 4)  # Fallback
    except Exception as unexpected:
        logger.exception(
            f"Unexpected error in followup volume calculation: {unexpected}"
        )
        followup_volume_scaled = min(fused_config.revenue_per_day, 4)  # Fallback

    # -------------------------------------------------------------------------
    # Step 4: Day-of-week multipliers
    # -------------------------------------------------------------------------
    weekly_distribution: dict[int, int] = {}
    dow_multipliers: dict[int, float] = {}

    try:
        from python.volume.day_of_week import (
            calculate_dow_multipliers,
            DOWMultipliers,
            apply_dow_modulation,
            DEFAULT_MULTIPLIERS,
        )

        dow_result = calculate_dow_multipliers(
            creator_id,
            db_path,
            use_defaults_on_insufficient=True,
        )

        dow_multipliers = dow_result.multipliers.copy()

        # Apply confidence dampening to DOW multipliers if low confidence
        if confidence_score < 0.6:
            from python.volume.confidence import dampen_multiplier_dict
            dow_multipliers = dampen_multiplier_dict(
                dow_multipliers,
                confidence_score,
            )

        # Calculate weekly distribution
        base_daily = fused_config.total_per_day
        weekly_distribution = dow_result.get_weekly_distribution(base_daily)

        if not dow_result.is_default:
            adjustments_applied.append("dow_multipliers")
            logger.info(
                "Applied DOW multipliers",
                extra={
                    "dow_confidence": dow_result.confidence,
                    "total_messages_analyzed": dow_result.total_messages,
                }
            )

    except sqlite3.OperationalError as db_error:
        logger.error(
            f"Database error in DOW multipliers calculation: {db_error}",
            extra={"creator_id": creator_id, "db_path": db_path}
        )
        # Fallback to uniform distribution
        base_daily = fused_config.total_per_day
        for day in range(7):
            weekly_distribution[day] = base_daily
            dow_multipliers[day] = 1.0
    except (ValueError, TypeError) as validation_error:
        logger.warning(
            f"Validation error in DOW multipliers calculation: {validation_error}",
            extra={"creator_id": creator_id}
        )
        # Fallback to uniform distribution
        base_daily = fused_config.total_per_day
        for day in range(7):
            weekly_distribution[day] = base_daily
            dow_multipliers[day] = 1.0
    except ImportError as import_error:
        logger.warning(
            f"Import error in DOW multipliers (module not available): {import_error}"
        )
        # Fallback to uniform distribution
        base_daily = fused_config.total_per_day
        for day in range(7):
            weekly_distribution[day] = base_daily
            dow_multipliers[day] = 1.0
    except Exception as unexpected:
        logger.exception(
            f"Unexpected error in DOW multipliers, using uniform distribution: {unexpected}"
        )
        # Fallback to uniform distribution
        base_daily = fused_config.total_per_day
        for day in range(7):
            weekly_distribution[day] = base_daily
            dow_multipliers[day] = 1.0

    # -------------------------------------------------------------------------
    # Step 5: Elasticity bounds check (diminishing returns)
    # -------------------------------------------------------------------------
    elasticity_capped = False

    try:
        from python.volume.elasticity import (
            ElasticityOptimizer,
            ElasticityModel,
            should_cap_volume,
        )

        optimizer = ElasticityOptimizer(db_path)
        profile = optimizer.get_profile(creator_id)

        if profile.has_sufficient_data and profile.parameters.is_reliable:
            optimal_volume, reason = optimizer.optimize_volume(
                creator_id,
                fused_config.revenue_per_day,
            )

            if optimal_volume < fused_config.revenue_per_day:
                elasticity_capped = True
                # Cap revenue volume
                fused_config = VolumeConfig(
                    tier=fused_config.tier,
                    revenue_per_day=optimal_volume,
                    engagement_per_day=fused_config.engagement_per_day,
                    retention_per_day=fused_config.retention_per_day,
                    fan_count=context.fan_count,
                    page_type=context.page_type,
                )
                adjustments_applied.append("elasticity_cap")
                logger.info(
                    "Applied elasticity cap",
                    extra={
                        "original_revenue": fused_config.revenue_per_day,
                        "capped_revenue": optimal_volume,
                        "reason": reason,
                    }
                )

    except sqlite3.OperationalError as db_error:
        logger.error(
            f"Database error in elasticity check: {db_error}",
            extra={"creator_id": creator_id, "db_path": db_path}
        )
    except (ValueError, TypeError) as validation_error:
        logger.warning(
            f"Validation error in elasticity check: {validation_error}",
            extra={"creator_id": creator_id}
        )
    except ImportError as import_error:
        logger.warning(
            f"Import error in elasticity check (module not available): {import_error}"
        )
    except Exception as unexpected:
        logger.exception(
            f"Unexpected error in elasticity check: {unexpected}"
        )

    # -------------------------------------------------------------------------
    # Step 6: Content-type weighting
    # -------------------------------------------------------------------------
    content_allocations: dict[str, int] = {}

    try:
        from python.volume.content_weighting import (
            ContentWeightingOptimizer,
            get_content_type_rankings,
        )

        content_optimizer = ContentWeightingOptimizer(db_path)
        content_profile = content_optimizer.get_profile(creator_id)

        if content_profile.total_types > 0:
            # Calculate allocations for top types
            for type_name, ranking in content_profile.rankings.items():
                base_allocation = fused_config.revenue_per_day
                weighted = content_optimizer.weight_allocation(
                    creator_id,
                    type_name,
                    base_allocation,
                )
                if weighted.weighted_volume > 0:
                    content_allocations[type_name] = weighted.weighted_volume

            if content_allocations:
                adjustments_applied.append("content_weighting")
                logger.info(
                    "Applied content weighting",
                    extra={
                        "top_types": content_profile.top_types,
                        "avoid_types": content_profile.avoid_types,
                    }
                )

    except sqlite3.OperationalError as db_error:
        logger.error(
            f"Database error in content weighting: {db_error}",
            extra={"creator_id": creator_id, "db_path": db_path}
        )
    except (ValueError, TypeError) as validation_error:
        logger.warning(
            f"Validation error in content weighting: {validation_error}",
            extra={"creator_id": creator_id}
        )
    except ImportError as import_error:
        logger.warning(
            f"Import error in content weighting (module not available): {import_error}"
        )
    except Exception as unexpected:
        logger.exception(
            f"Unexpected error in content weighting: {unexpected}"
        )

    # -------------------------------------------------------------------------
    # Step 7: Caption pool verification
    # -------------------------------------------------------------------------
    caption_warnings: list[str] = []

    try:
        from python.volume.caption_constraint import (
            CaptionPoolAnalyzer,
            get_caption_shortage_report,
        )

        analyzer = CaptionPoolAnalyzer(db_path)
        pool_status = analyzer.analyze(creator_id)

        if not pool_status.sufficient_coverage:
            for critical_type in pool_status.critical_types:
                caption_warnings.append(
                    f"Low captions for {critical_type}: "
                    f"<3 usable captions available"
                )
            adjustments_applied.append("caption_pool_check")
            logger.warning(
                "Caption pool has critical shortages",
                extra={
                    "critical_types": pool_status.critical_types,
                    "creator_id": creator_id,
                }
            )

        # Generate detailed shortage report
        daily_volume = {
            "ppv_unlock": fused_config.revenue_per_day // 2,
            "bump_normal": fused_config.engagement_per_day // 2,
            "bump_descriptive": fused_config.engagement_per_day // 2,
        }
        shortage_report = get_caption_shortage_report(pool_status, daily_volume)

        for send_type, shortage in shortage_report.items():
            if shortage["status"] in ("critical", "insufficient"):
                caption_warnings.append(shortage["message"])

    except sqlite3.OperationalError as db_error:
        logger.error(
            f"Database error in caption pool check: {db_error}",
            extra={"creator_id": creator_id, "db_path": db_path}
        )
    except (ValueError, TypeError) as validation_error:
        logger.warning(
            f"Validation error in caption pool check: {validation_error}",
            extra={"creator_id": creator_id}
        )
    except ImportError as import_error:
        logger.warning(
            f"Import error in caption pool check (module not available): {import_error}"
        )
    except Exception as unexpected:
        logger.exception(
            f"Unexpected error in caption pool check: {unexpected}"
        )

    # -------------------------------------------------------------------------
    # Step 8: Track prediction for accuracy measurement
    # -------------------------------------------------------------------------
    prediction_id: Optional[int] = None

    if track_prediction:
        try:
            from python.volume.prediction_tracker import (
                VolumePrediction,
                PredictionTracker,
                estimate_weekly_revenue,
                estimate_weekly_messages,
            )

            # Estimate weekly metrics
            avg_rps = 0.10  # Default, could fetch from DB
            weekly_revenue = estimate_weekly_revenue(
                fused_config.revenue_per_day,
                fused_config.engagement_per_day,
                fused_config.retention_per_day,
                avg_rps,
            )
            weekly_messages = estimate_weekly_messages(
                fused_config.revenue_per_day,
                fused_config.engagement_per_day,
                fused_config.retention_per_day,
            )

            prediction = VolumePrediction(
                creator_id=creator_id,
                input_fan_count=context.fan_count,
                input_page_type=context.page_type,
                input_saturation=fused_saturation,
                input_opportunity=fused_opportunity,
                predicted_tier=fused_config.tier.value,
                predicted_revenue_per_day=fused_config.revenue_per_day,
                predicted_engagement_per_day=fused_config.engagement_per_day,
                predicted_retention_per_day=fused_config.retention_per_day,
                predicted_weekly_revenue=weekly_revenue,
                predicted_weekly_messages=weekly_messages,
            )

            tracker = PredictionTracker(db_path)
            prediction_id = tracker.track_prediction(
                prediction,
                week_start_date=week_start,
            )
            adjustments_applied.append("prediction_tracked")
            logger.info(
                "Prediction tracked for accuracy measurement",
                extra={"prediction_id": prediction_id}
            )

        except sqlite3.OperationalError as db_error:
            logger.error(
                f"Database error in prediction tracking: {db_error}",
                extra={"creator_id": creator_id, "db_path": db_path, "week_start": week_start}
            )
        except (ValueError, TypeError) as validation_error:
            logger.warning(
                f"Validation error in prediction tracking: {validation_error}",
                extra={"creator_id": creator_id, "week_start": week_start}
            )
        except ImportError as import_error:
            logger.warning(
                f"Import error in prediction tracking (module not available): {import_error}"
            )
        except Exception as unexpected:
            logger.exception(
                f"Unexpected error in prediction tracking: {unexpected}"
            )

    # -------------------------------------------------------------------------
    # Build final result
    # -------------------------------------------------------------------------
    result = OptimizedVolumeResult(
        base_config=base_config,
        final_config=fused_config,
        weekly_distribution=weekly_distribution,
        content_allocations=content_allocations,
        adjustments_applied=adjustments_applied,
        confidence_score=confidence_score,
        elasticity_capped=elasticity_capped,
        caption_warnings=caption_warnings,
        prediction_id=prediction_id,
        fused_saturation=fused_saturation,
        fused_opportunity=fused_opportunity,
        divergence_detected=divergence_detected,
        dow_multipliers_used=dow_multipliers,
        message_count=message_count,
        # New fields for Volume Optimization v3.0
        bump_multiplier=bump_multiplier,
        bump_adjusted_engagement=bump_adjusted_engagement,
        content_category=content_category,
        bump_capped=bump_capped,
        followup_volume_scaled=followup_volume_scaled,
        followup_rate_used=followup_rate_used,
    )

    logger.info(
        "Optimized volume calculation complete",
        extra={
            "creator_id": creator_id,
            "final_revenue": fused_config.revenue_per_day,
            "final_engagement": fused_config.engagement_per_day,
            "final_retention": fused_config.retention_per_day,
            "adjustments": adjustments_applied,
            "confidence": confidence_score,
        }
    )

    return result


__all__ = [
    # Main dataclasses
    "PerformanceContext",
    "OptimizedVolumeResult",
    # Main functions
    "calculate_dynamic_volume",
    "calculate_dynamic_volume_legacy",
    "calculate_optimized_volume",
    "get_volume_tier",
    # Internal functions exposed for testing
    "_calculate_saturation_multiplier",
    "_calculate_saturation_multiplier_smooth",
    "_calculate_opportunity_multiplier",
    "_calculate_opportunity_multiplier_smooth",
    "_calculate_trend_adjustment",
    "_apply_bounds",
    "_round_volume",
    "_apply_new_creator_defaults",
    # Bump multiplier integration (Volume Optimization v3.0)
    "BumpMultiplierResult",
    "FollowupVolumeResult",
]
