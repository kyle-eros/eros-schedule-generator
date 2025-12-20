"""
Dynamic volume calculation module.

Provides intelligent, performance-based volume calculation that replaces
static volume_assignments table lookups. The module calculates optimal
send volumes based on fan count, saturation/opportunity scores, and
performance trends.

Usage:
    from python.volume import (
        PerformanceContext,
        calculate_dynamic_volume,
        get_volume_tier,
    )

    # Create performance context from creator metrics
    context = PerformanceContext(
        fan_count=12434,
        page_type="paid",
        saturation_score=45,
        opportunity_score=65,
        revenue_trend=10
    )

    # Calculate dynamic volume
    config = calculate_dynamic_volume(context)
    print(f"Tier: {config.tier}")  # HIGH (5000-14999 fans)
    print(f"Revenue/day: {config.revenue_per_day}")  # 5-6

Configuration:
    The module uses tier-based configurations with performance adjustments:
    - Base volumes from TIER_CONFIGS by fan count tier
    - Saturation multiplier (0.7-1.0) reduces volume for fatigued audiences
    - Opportunity multiplier (1.0-1.2) increases volume when growth potential exists
    - Trend adjustment (-1/0/+1) fine-tunes based on revenue performance
"""

from python.models.volume import VolumeConfig, VolumeTier
from python.volume.dynamic_calculator import (
    PerformanceContext,
    OptimizedVolumeResult,
    calculate_dynamic_volume,
    calculate_optimized_volume,
    get_volume_tier,
)
from python.volume.tier_config import (
    TIER_CONFIGS,
    VOLUME_BOUNDS,
    FAN_COUNT_THRESHOLDS,
    SATURATION_THRESHOLDS,
    OPPORTUNITY_THRESHOLDS,
)
from python.volume.score_calculator import (
    CalculatedScores,
    PerformanceScores,
    PeriodMetrics,
    ScoreCalculator,
    calculate_opportunity_score,
    calculate_saturation_score,
    calculate_scores_from_db,
)
from python.volume.caption_constraint import (
    CaptionAvailability,
    CaptionPoolStatus,
    ScheduleSlot,
    VolumeConstraintResult,
    CaptionPoolAnalyzer,
    get_caption_pool_status,
    check_caption_availability,
    get_caption_shortage_report,
    get_caption_coverage_estimate,
    validate_volume_against_captions,
    SEND_TYPE_CATEGORIES,
    get_send_type_category,
)
from python.volume.elasticity import (
    ElasticityParameters,
    VolumePoint,
    ElasticityProfile,
    ElasticityModel,
    ElasticityOptimizer,
    fit_elasticity_model,
    fetch_volume_performance_data,
    calculate_elasticity_profile,
    should_cap_volume,
    DEFAULT_DECAY_RATE,
    DEFAULT_MIN_MARGINAL_RPS,
    VOLUME_EVALUATION_POINTS,
)
from python.volume.confidence import (
    ConfidenceResult,
    ConfidenceAdjustedVolume,
    calculate_confidence,
    dampen_multiplier,
    dampen_multiplier_dict,
    apply_confidence_to_multipliers,
    apply_confidence_to_dow_multipliers,
    apply_confidence_to_content_multipliers,
    calculate_confidence_adjusted_volume,
    CONFIDENCE_TIERS,
    NEUTRAL_MULTIPLIER,
)
from python.volume.content_weighting import (
    ContentTypeRanking,
    ContentTypeProfile,
    WeightedAllocation,
    ContentWeightingOptimizer,
    get_content_type_rankings,
    apply_content_weighting,
    allocate_by_content_type,
    get_content_type_recommendations,
    RANK_MULTIPLIERS,
    DEFAULT_RANK,
)
from python.volume.prediction_tracker import (
    VolumePrediction,
    PredictionOutcome,
    PredictionAccuracy,
    PredictionTracker,
    save_prediction,
    measure_prediction_outcome,
    get_prediction_accuracy,
    find_unmeasured_predictions,
    batch_measure_predictions,
    calculate_mape,
    get_accuracy_by_algorithm_version,
    estimate_weekly_revenue,
    estimate_weekly_messages,
    CURRENT_ALGORITHM_VERSION,
)
from python.volume.multi_horizon import (
    DEFAULT_WEIGHTS,
    DIVERGENCE_THRESHOLD,
    RAPID_CHANGE_WEIGHTS,
    VALID_PERIODS,
    FusedScores,
    HorizonScores,
    MultiHorizonAnalyzer,
    detect_divergence,
    fetch_horizon_scores,
    fuse_scores,
    select_weights,
)
from python.volume.day_of_week import (
    DayPerformance,
    DOWMultipliers,
    DOWAnalysis,
    DEFAULT_MULTIPLIERS as DOW_DEFAULT_MULTIPLIERS,
    DAY_NAMES,
    MULTIPLIER_MIN as DOW_MULTIPLIER_MIN,
    MULTIPLIER_MAX as DOW_MULTIPLIER_MAX,
    MIN_MESSAGES_PER_DAY as DOW_MIN_MESSAGES_PER_DAY,
    MIN_TOTAL_MESSAGES as DOW_MIN_TOTAL_MESSAGES,
    convert_sqlite_dow_to_python,
    convert_python_dow_to_sqlite,
    fetch_dow_performance,
    calculate_dow_multipliers,
    analyze_dow_patterns,
    apply_dow_modulation,
    get_weekly_volume_distribution,
)
from python.volume.page_type_calculator import (
    CreatorConfig,
    VolumeTargets,
    PageType,
    SubType,
    TierName,
    TIER_PPVS,
    BUMP_MATRIX,
    VALID_PAGE_TYPES,
    VALID_SUB_TYPES,
    BUMP_RATIO_TOLERANCE,
    get_volume_tier as get_volume_tier_name,
    calculate_volume_targets,
    validate_bump_ratio,
    get_tier_for_fan_count,
    get_all_bump_ranges,
)
from python.volume.campaign_frequency import (
    CAMPAIGN_FREQUENCY_RULES,
    MINIMUM_MONTHLY_CAMPAIGNS,
    OPTIMAL_MONTHLY_CAMPAIGNS,
    CRITICALLY_LOW_THRESHOLD,
    validate_campaign_frequency,
    get_frequency_rules,
    get_campaign_types,
    get_monthly_targets,
)
from python.volume.bump_multiplier import (
    BumpMultiplierResult,
    FollowupVolumeResult,
    BUMP_MULTIPLIERS,
    DEFAULT_CONTENT_CATEGORY,
    FOLLOWUP_BASE_RATE,
    MAX_FOLLOWUPS_PER_DAY,
    HIGH_TIER_MULTIPLIER_CAP,
    FREE_PAGE_BUMP_BONUS,
    calculate_bump_multiplier,
    calculate_followup_volume,
    get_creator_content_category,
    apply_bump_to_engagement,
    get_bump_multiplier_for_category,
    get_all_content_categories,
    calculate_effective_engagement,
)

__all__ = [
    # Domain models (re-exported from python.models.volume)
    "VolumeConfig",
    "VolumeTier",
    # Context and result dataclasses
    "PerformanceContext",
    "OptimizedVolumeResult",
    # Main calculation functions
    "calculate_dynamic_volume",
    "calculate_optimized_volume",
    "get_volume_tier",
    # Configuration constants
    "TIER_CONFIGS",
    "VOLUME_BOUNDS",
    "FAN_COUNT_THRESHOLDS",
    "SATURATION_THRESHOLDS",
    "OPPORTUNITY_THRESHOLDS",
    # Score calculation (fallback when volume_performance_tracking is stale)
    "ScoreCalculator",
    "PerformanceScores",
    "PeriodMetrics",
    "calculate_scores_from_db",
    "calculate_saturation_score",
    "calculate_opportunity_score",
    # Backwards compatibility
    "CalculatedScores",
    # Caption constraint module
    "CaptionAvailability",
    "CaptionPoolStatus",
    "ScheduleSlot",
    "VolumeConstraintResult",
    "CaptionPoolAnalyzer",
    "get_caption_pool_status",
    "check_caption_availability",
    "get_caption_shortage_report",
    "get_caption_coverage_estimate",
    "validate_volume_against_captions",
    "SEND_TYPE_CATEGORIES",
    "get_send_type_category",
    # Elasticity model for diminishing returns analysis
    "ElasticityParameters",
    "VolumePoint",
    "ElasticityProfile",
    "ElasticityModel",
    "ElasticityOptimizer",
    "fit_elasticity_model",
    "fetch_volume_performance_data",
    "calculate_elasticity_profile",
    "should_cap_volume",
    "DEFAULT_DECAY_RATE",
    "DEFAULT_MIN_MARGINAL_RPS",
    "VOLUME_EVALUATION_POINTS",
    # Confidence-adjusted multipliers
    "ConfidenceResult",
    "ConfidenceAdjustedVolume",
    "calculate_confidence",
    "dampen_multiplier",
    "dampen_multiplier_dict",
    "apply_confidence_to_multipliers",
    "apply_confidence_to_dow_multipliers",
    "apply_confidence_to_content_multipliers",
    "calculate_confidence_adjusted_volume",
    "CONFIDENCE_TIERS",
    "NEUTRAL_MULTIPLIER",
    # Content-type weighted allocation
    "ContentTypeRanking",
    "ContentTypeProfile",
    "WeightedAllocation",
    "ContentWeightingOptimizer",
    "get_content_type_rankings",
    "apply_content_weighting",
    "allocate_by_content_type",
    "get_content_type_recommendations",
    "RANK_MULTIPLIERS",
    "DEFAULT_RANK",
    # Prediction tracking for algorithm accuracy measurement
    "VolumePrediction",
    "PredictionOutcome",
    "PredictionAccuracy",
    "PredictionTracker",
    "save_prediction",
    "measure_prediction_outcome",
    "get_prediction_accuracy",
    "find_unmeasured_predictions",
    "batch_measure_predictions",
    "calculate_mape",
    "get_accuracy_by_algorithm_version",
    "estimate_weekly_revenue",
    "estimate_weekly_messages",
    "CURRENT_ALGORITHM_VERSION",
    # Multi-horizon score fusion
    "MultiHorizonAnalyzer",
    "HorizonScores",
    "FusedScores",
    "fuse_scores",
    "fetch_horizon_scores",
    "detect_divergence",
    "select_weights",
    "DEFAULT_WEIGHTS",
    "RAPID_CHANGE_WEIGHTS",
    "DIVERGENCE_THRESHOLD",
    "VALID_PERIODS",
    # Day-of-week volume modulation
    "DayPerformance",
    "DOWMultipliers",
    "DOWAnalysis",
    "DOW_DEFAULT_MULTIPLIERS",
    "DAY_NAMES",
    "DOW_MULTIPLIER_MIN",
    "DOW_MULTIPLIER_MAX",
    "DOW_MIN_MESSAGES_PER_DAY",
    "DOW_MIN_TOTAL_MESSAGES",
    "convert_sqlite_dow_to_python",
    "convert_python_dow_to_sqlite",
    "fetch_dow_performance",
    "calculate_dow_multipliers",
    "analyze_dow_patterns",
    "apply_dow_modulation",
    "get_weekly_volume_distribution",
    # Page type volume matrix calculator
    "CreatorConfig",
    "VolumeTargets",
    "PageType",
    "SubType",
    "TierName",
    "TIER_PPVS",
    "BUMP_MATRIX",
    "VALID_PAGE_TYPES",
    "VALID_SUB_TYPES",
    "BUMP_RATIO_TOLERANCE",
    "get_volume_tier_name",
    "calculate_volume_targets",
    "validate_bump_ratio",
    "get_tier_for_fan_count",
    "get_all_bump_ranges",
    # Campaign frequency enforcement
    "CAMPAIGN_FREQUENCY_RULES",
    "MINIMUM_MONTHLY_CAMPAIGNS",
    "OPTIMAL_MONTHLY_CAMPAIGNS",
    "CRITICALLY_LOW_THRESHOLD",
    "validate_campaign_frequency",
    "get_frequency_rules",
    "get_campaign_types",
    "get_monthly_targets",
    # Bump multiplier for engagement volume optimization
    "BumpMultiplierResult",
    "FollowupVolumeResult",
    "BUMP_MULTIPLIERS",
    "DEFAULT_CONTENT_CATEGORY",
    "FOLLOWUP_BASE_RATE",
    "MAX_FOLLOWUPS_PER_DAY",
    "HIGH_TIER_MULTIPLIER_CAP",
    "FREE_PAGE_BUMP_BONUS",
    "calculate_bump_multiplier",
    "calculate_followup_volume",
    "get_creator_content_category",
    "apply_bump_to_engagement",
    "get_bump_multiplier_for_category",
    "get_all_content_categories",
    "calculate_effective_engagement",
]
