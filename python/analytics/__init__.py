"""
Analytics module for performance-based optimization.

Provides statistical analysis tools for detecting patterns in top performer
data and generating data-driven volume recommendations. The module implements
hypothesis testing to ensure recommendations are statistically significant.

Submodules:
    - trait_detector: Detects shared traits among top performers
    - volume_ab_test: A/B testing framework for volume experiments
    - game_tracker: Bayesian performance tracking for game sub-types
    - daily_digest: Automated daily statistics review and recommendations

Usage:
    from python.analytics import (
        # Trait detection
        TraitAnalysisResult,
        TraitRecommendation,
        analyze_top_performer_traits,
        apply_volume_increases,
        # A/B testing
        VolumeABTest,
        VOLUME_AB_TESTS,
        validate_test_completion,
        get_test_by_id,
        # Game tracking
        GameTypeTracker,
        GAME_BENCHMARKS,
        get_game_frequency,
        # Daily digest
        DailyStatisticsAnalyzer,
    )

    # Analyze top performer traits
    result = analyze_top_performer_traits(performance_data, top_n=10)

    if result['has_recommendations']:
        for rec in result['recommendations']:
            print(f"Trait: {rec['trait']}, Multiplier: {rec['multiplier']}")

    # Apply recommendations to allocation
    adjusted = apply_volume_increases(allocation, result['recommendations'])

    # A/B testing for volume optimization
    test = get_test_by_id('bump_ratio_2x_vs_3x')
    result = validate_test_completion(test, control_n=400, treatment_n=400)

    # Track game performance with Bayesian updating
    tracker = GameTypeTracker("alexia")
    tracker.record_performance("spin_the_wheel", 5200.0, "2025-01-15")
    recs = tracker.get_recommendations()
    print(f"Best game: {recs['best_game_type']}")

    # Generate daily statistics digest
    analyzer = DailyStatisticsAnalyzer("alexia")
    digest = analyzer.generate_daily_digest(performance_data)
    print(f"Action items: {digest['action_items']}")

Statistical Methods:
    - Chi-square test for large samples (n >= 5 in all cells)
    - Fisher's exact test for small samples
    - Bonferroni correction for multiple comparisons
    - 60% threshold for trait significance
    - Power analysis for A/B test sample sizing
    - Normal-Inverse-Gamma Bayesian updating for game tracking
"""

from python.analytics.trait_detector import (
    # Type definitions
    TraitAnalysisResult,
    TraitRecommendation,
    SharedTraitInfo,
    # Constants
    DEFAULT_TOP_N,
    DEFAULT_THRESHOLD_PERCENT,
    MIN_SAMPLE_FOR_CONFIDENCE,
    DEFAULT_ALPHA,
    OPTIMAL_LENGTH_MIN,
    OPTIMAL_LENGTH_MAX,
    # Main analysis function
    analyze_top_performer_traits,
    # Application function
    apply_volume_increases,
    # Helper functions
    chi_square_test,
    is_optimal_length,
)

from python.analytics.volume_ab_test import (
    # Enums
    TestStatus,
    MetricType,
    # Data classes
    VolumeConfig,
    Metric,
    VolumeABTest,
    # Pre-configured tests
    VOLUME_AB_TESTS,
    # Common metrics
    REVENUE_PER_SUBSCRIBER,
    PPV_UNLOCK_RATE,
    SUBSCRIBER_CHURN_RATE,
    MESSAGE_OPEN_RATE,
    TIP_RATE,
    # Constants
    DEFAULT_CONFIDENCE_LEVEL,
    DEFAULT_STATISTICAL_POWER,
    DEFAULT_MDE,
    DEFAULT_DURATION_DAYS,
    # Statistical functions
    calculate_achieved_power,
    # Validation functions
    validate_test_completion,
    # Helper functions
    get_test_by_id,
    list_available_tests,
    create_custom_test,
)

from python.analytics.game_tracker import (
    # Data classes
    GamePerformance,
    GameBenchmark,
    # Type definitions
    BayesianEstimate,
    GameRecommendation,
    RecommendationResult,
    # Constants
    GAME_BENCHMARKS,
    MIN_OBSERVATIONS_HIGH_CONFIDENCE,
    MIN_OBSERVATIONS_FOR_OVERRIDE,
    AVOID_THRESHOLD_RATIO,
    RECOMMENDED_THRESHOLD_RATIO,
    PRIOR_STRENGTH,
    CREDIBLE_INTERVAL_PROB,
    # Main tracker class
    GameTypeTracker,
    # Utility functions
    get_game_frequency,
    create_tracker_from_history,
)

from python.analytics.daily_digest import (
    # Main class
    DailyStatisticsAnalyzer,
    # Constants
    TIMEFRAME_SHORT,
    TIMEFRAME_MEDIUM,
    TIMEFRAME_LONG,
    OPTIMAL_LENGTH_MIN as DIGEST_OPTIMAL_LENGTH_MIN,
    OPTIMAL_LENGTH_MAX as DIGEST_OPTIMAL_LENGTH_MAX,
    TOP_N_CONTENT_TYPES,
    TOP_N_HOURS,
    TOP_N_RESULTS,
    BOTTOM_PERCENTILE,
    MIN_DATA_POINTS,
)

__all__ = [
    # === Trait Detector ===
    # Type definitions
    "TraitAnalysisResult",
    "TraitRecommendation",
    "SharedTraitInfo",
    # Constants
    "DEFAULT_TOP_N",
    "DEFAULT_THRESHOLD_PERCENT",
    "MIN_SAMPLE_FOR_CONFIDENCE",
    "DEFAULT_ALPHA",
    "OPTIMAL_LENGTH_MIN",
    "OPTIMAL_LENGTH_MAX",
    # Main analysis function
    "analyze_top_performer_traits",
    # Application function
    "apply_volume_increases",
    # Helper functions (exposed for testing)
    "chi_square_test",
    "is_optimal_length",
    # === Volume A/B Testing ===
    # Enums
    "TestStatus",
    "MetricType",
    # Data classes
    "VolumeConfig",
    "Metric",
    "VolumeABTest",
    # Pre-configured tests
    "VOLUME_AB_TESTS",
    # Common metrics
    "REVENUE_PER_SUBSCRIBER",
    "PPV_UNLOCK_RATE",
    "SUBSCRIBER_CHURN_RATE",
    "MESSAGE_OPEN_RATE",
    "TIP_RATE",
    # Constants
    "DEFAULT_CONFIDENCE_LEVEL",
    "DEFAULT_STATISTICAL_POWER",
    "DEFAULT_MDE",
    "DEFAULT_DURATION_DAYS",
    # Statistical functions
    "calculate_achieved_power",
    # Validation functions
    "validate_test_completion",
    # Helper functions
    "get_test_by_id",
    "list_available_tests",
    "create_custom_test",
    # === Game Tracker ===
    # Data classes
    "GamePerformance",
    "GameBenchmark",
    # Type definitions
    "BayesianEstimate",
    "GameRecommendation",
    "RecommendationResult",
    # Constants
    "GAME_BENCHMARKS",
    "MIN_OBSERVATIONS_HIGH_CONFIDENCE",
    "MIN_OBSERVATIONS_FOR_OVERRIDE",
    "AVOID_THRESHOLD_RATIO",
    "RECOMMENDED_THRESHOLD_RATIO",
    "PRIOR_STRENGTH",
    "CREDIBLE_INTERVAL_PROB",
    # Main class
    "GameTypeTracker",
    # Utility functions
    "get_game_frequency",
    "create_tracker_from_history",
    # === Daily Digest ===
    # Main class
    "DailyStatisticsAnalyzer",
    # Constants
    "TIMEFRAME_SHORT",
    "TIMEFRAME_MEDIUM",
    "TIMEFRAME_LONG",
    "DIGEST_OPTIMAL_LENGTH_MIN",
    "DIGEST_OPTIMAL_LENGTH_MAX",
    "TOP_N_CONTENT_TYPES",
    "TOP_N_HOURS",
    "TOP_N_RESULTS",
    "BOTTOM_PERCENTILE",
    "MIN_DATA_POINTS",
]
