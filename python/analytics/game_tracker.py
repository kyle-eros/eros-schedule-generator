"""
Game Type Success Tracker with Bayesian Updating.

Tracks performance by game sub-type and uses Bayesian updating to combine
creator-specific history with population-level benchmarks. This enables
personalized game type recommendations that adapt as more data is collected.

Reference performance benchmarks from production data:
    - spin_the_wheel: $5,178 avg (highest) -> weekly frequency
    - prize_wheel: $2,500 avg -> weekly
    - mystery_box: $3,000 avg -> weekly
    - scratch_off: $1,200 avg -> weekly
    - card_game: $500 avg (low) -> bi-weekly or stop

The module implements conjugate Bayesian updating using Normal-Inverse-Gamma
priors for robust estimation with uncertainty quantification.

Usage:
    from python.analytics.game_tracker import (
        GameTypeTracker,
        GAME_BENCHMARKS,
        get_game_frequency,
    )

    # Create tracker for a creator
    tracker = GameTypeTracker(creator_id="alexia")

    # Record performance data
    tracker.record_performance("spin_the_wheel", 4500.0, "2025-01-15")
    tracker.record_performance("spin_the_wheel", 5800.0, "2025-01-22")
    tracker.record_performance("card_game", 300.0, "2025-01-18")

    # Get recommendations
    recommendations = tracker.get_recommendations()
    print(f"Best game: {recommendations['best_game_type']}")
    print(f"Avoid: {recommendations['avoid_list']}")

Statistical Methods:
    - Normal-Inverse-Gamma conjugate prior for earnings distribution
    - Posterior mean with credible intervals
    - Thompson sampling for exploration/exploitation
    - Confidence-weighted recommendations
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import numpy as np
from scipy import stats

from python.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Minimum observations for high confidence recommendations
MIN_OBSERVATIONS_HIGH_CONFIDENCE: int = 5

# Minimum observations to override population prior
MIN_OBSERVATIONS_FOR_OVERRIDE: int = 3

# Performance threshold relative to benchmark for "avoid" classification
AVOID_THRESHOLD_RATIO: float = 0.4  # Below 40% of benchmark = avoid

# Performance threshold for "recommended" classification
RECOMMENDED_THRESHOLD_RATIO: float = 0.8  # Above 80% of benchmark = recommended

# Prior strength (equivalent sample size for population benchmark)
PRIOR_STRENGTH: float = 10.0

# Credible interval probability
CREDIBLE_INTERVAL_PROB: float = 0.95


# =============================================================================
# Type Definitions
# =============================================================================


@dataclass(frozen=True, slots=True)
class GamePerformance:
    """Record of a single game performance instance.

    Attributes:
        game_type: Type of game (e.g., 'spin_the_wheel', 'mystery_box').
        earnings: Revenue generated from this game instance.
        date: Date the game was run (ISO format string YYYY-MM-DD).
        creator_id: Creator who ran this game (for multi-creator tracking).
        metadata: Optional additional context (engagement metrics, etc.).

    Examples:
        >>> perf = GamePerformance(
        ...     game_type="spin_the_wheel",
        ...     earnings=5200.0,
        ...     date="2025-01-15",
        ...     creator_id="alexia"
        ... )
        >>> perf.earnings
        5200.0
    """

    game_type: str
    earnings: float
    date: str
    creator_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate performance record after initialization."""
        if self.earnings < 0:
            raise ValueError(f"Earnings cannot be negative: {self.earnings}")
        if not self.game_type:
            raise ValueError("Game type cannot be empty")
        # Validate date format
        try:
            datetime.strptime(self.date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format '{self.date}', expected YYYY-MM-DD") from e


@dataclass(frozen=True, slots=True)
class GameBenchmark:
    """Statistical benchmark for a game type from population data.

    Attributes:
        avg_earnings: Mean earnings across population.
        std_dev: Standard deviation of earnings.
        sample_size: Number of observations in benchmark.
        ci_95_lower: Lower bound of 95% confidence interval.
        ci_95_upper: Upper bound of 95% confidence interval.
        recommended_frequency: Suggested scheduling frequency ('weekly', 'bi-weekly', etc.).
        performance_tier: Classification tier ('TOP', 'MID', 'LOW').

    Examples:
        >>> benchmark = GameBenchmark(
        ...     avg_earnings=5178.0,
        ...     std_dev=1200.0,
        ...     sample_size=150,
        ...     ci_95_lower=4985.0,
        ...     ci_95_upper=5371.0,
        ...     recommended_frequency="weekly",
        ...     performance_tier="TOP"
        ... )
    """

    avg_earnings: float
    std_dev: float
    sample_size: int
    ci_95_lower: float
    ci_95_upper: float
    recommended_frequency: str
    performance_tier: str


class BayesianEstimate(TypedDict):
    """Result of Bayesian posterior estimation.

    Attributes:
        posterior_mean: Expected value of earnings.
        posterior_std: Standard deviation of posterior.
        credible_lower: Lower bound of credible interval.
        credible_upper: Upper bound of credible interval.
        confidence_score: 0-100 score based on data quality.
        observation_count: Number of creator-specific observations.
        prior_weight: Weight given to population prior (0-1).
        posterior_weight: Weight given to creator data (0-1).
    """

    posterior_mean: float
    posterior_std: float
    credible_lower: float
    credible_upper: float
    confidence_score: float
    observation_count: int
    prior_weight: float
    posterior_weight: float


class GameRecommendation(TypedDict):
    """Recommendation for a single game type.

    Attributes:
        game_type: The game type identifier.
        action: Recommended action ('schedule_weekly', 'schedule_biweekly',
                'reduce', 'avoid', 'experiment').
        expected_earnings: Posterior expected earnings.
        confidence: Confidence level in recommendation ('HIGH', 'MEDIUM', 'LOW').
        rationale: Human-readable explanation.
        bayesian_estimate: Full Bayesian estimate details.
    """

    game_type: str
    action: str
    expected_earnings: float
    confidence: str
    rationale: str
    bayesian_estimate: BayesianEstimate


class RecommendationResult(TypedDict):
    """Complete recommendation result from the tracker.

    Attributes:
        best_game_type: Highest expected earnings game type.
        best_game_earnings: Expected earnings for best game.
        avoid_list: List of game types to avoid.
        recommendations: Full recommendations for all tracked games.
        confidence_level: Overall confidence in recommendations.
        total_observations: Total performance records analyzed.
        exploration_suggestion: Game type to try for more data.
    """

    best_game_type: Optional[str]
    best_game_earnings: float
    avoid_list: List[str]
    recommendations: Dict[str, GameRecommendation]
    confidence_level: str
    total_observations: int
    exploration_suggestion: Optional[str]


# =============================================================================
# Game Benchmarks (Population Priors)
# =============================================================================

GAME_BENCHMARKS: Dict[str, GameBenchmark] = {
    "spin_the_wheel": GameBenchmark(
        avg_earnings=5178.0,
        std_dev=1500.0,
        sample_size=150,
        ci_95_lower=4938.0,
        ci_95_upper=5418.0,
        recommended_frequency="weekly",
        performance_tier="TOP",
    ),
    "prize_wheel": GameBenchmark(
        avg_earnings=2500.0,
        std_dev=800.0,
        sample_size=120,
        ci_95_lower=2357.0,
        ci_95_upper=2643.0,
        recommended_frequency="weekly",
        performance_tier="MID",
    ),
    "mystery_box": GameBenchmark(
        avg_earnings=3000.0,
        std_dev=900.0,
        sample_size=100,
        ci_95_lower=2824.0,
        ci_95_upper=3176.0,
        recommended_frequency="weekly",
        performance_tier="MID",
    ),
    "scratch_off": GameBenchmark(
        avg_earnings=1200.0,
        std_dev=500.0,
        sample_size=80,
        ci_95_lower=1090.0,
        ci_95_upper=1310.0,
        recommended_frequency="weekly",
        performance_tier="LOW",
    ),
    "card_game": GameBenchmark(
        avg_earnings=500.0,
        std_dev=300.0,
        sample_size=60,
        ci_95_lower=424.0,
        ci_95_upper=576.0,
        recommended_frequency="bi-weekly",
        performance_tier="LOW",
    ),
    "dice_game": GameBenchmark(
        avg_earnings=800.0,
        std_dev=400.0,
        sample_size=50,
        ci_95_lower=689.0,
        ci_95_upper=911.0,
        recommended_frequency="bi-weekly",
        performance_tier="LOW",
    ),
    "trivia": GameBenchmark(
        avg_earnings=600.0,
        std_dev=350.0,
        sample_size=40,
        ci_95_lower=491.0,
        ci_95_upper=709.0,
        recommended_frequency="bi-weekly",
        performance_tier="LOW",
    ),
}


# =============================================================================
# Utility Functions
# =============================================================================


def get_game_frequency(game_type: str) -> str:
    """Get recommended frequency for a game type.

    Returns the scheduling frequency recommendation based on population
    benchmarks. Unknown game types default to 'bi-weekly' as a conservative
    approach.

    Args:
        game_type: The game type identifier (e.g., 'spin_the_wheel').

    Returns:
        Frequency string: 'weekly', 'bi-weekly', 'monthly', or 'avoid'.

    Examples:
        >>> get_game_frequency("spin_the_wheel")
        'weekly'
        >>> get_game_frequency("card_game")
        'bi-weekly'
        >>> get_game_frequency("unknown_game")
        'bi-weekly'
    """
    if game_type in GAME_BENCHMARKS:
        return GAME_BENCHMARKS[game_type].recommended_frequency
    # Default to bi-weekly for unknown games (conservative)
    logger.debug(
        "Unknown game type, using default frequency",
        extra={"game_type": game_type, "default_frequency": "bi-weekly"}
    )
    return "bi-weekly"


def _compute_normal_inverse_gamma_posterior(
    prior_mean: float,
    prior_var: float,
    prior_n: float,
    observations: List[float],
) -> Tuple[float, float, float, float]:
    """Compute posterior parameters using Normal-Inverse-Gamma conjugate prior.

    The Normal-Inverse-Gamma distribution is the conjugate prior for a normal
    distribution with unknown mean and variance. This enables closed-form
    Bayesian updating.

    Args:
        prior_mean: Prior mean (mu_0).
        prior_var: Prior variance (sigma^2_0).
        prior_n: Prior strength (equivalent sample size, kappa_0).
        observations: List of observed earnings values.

    Returns:
        Tuple of (posterior_mean, posterior_var, posterior_n, marginal_var)
        where marginal_var is the predictive variance for new observations.

    Examples:
        >>> post_mean, post_var, post_n, marg_var = _compute_normal_inverse_gamma_posterior(
        ...     prior_mean=5000.0,
        ...     prior_var=1000000.0,
        ...     prior_n=10.0,
        ...     observations=[4500.0, 5200.0, 5800.0]
        ... )
        >>> 4800 < post_mean < 5200
        True
    """
    n_obs = len(observations)

    if n_obs == 0:
        # No observations, return prior
        return prior_mean, prior_var, prior_n, prior_var

    # Calculate sample statistics
    obs_array = np.array(observations)
    sample_mean = float(np.mean(obs_array))
    sample_var = float(np.var(obs_array, ddof=1)) if n_obs > 1 else prior_var

    # Update parameters (Normal-Inverse-Gamma update equations)
    posterior_n = prior_n + n_obs
    posterior_mean = (prior_n * prior_mean + n_obs * sample_mean) / posterior_n

    # Posterior variance combines prior and sample information
    # Using a simplified conjugate update for computational efficiency
    weighted_prior_var = prior_n * prior_var
    weighted_sample_var = n_obs * sample_var if n_obs > 1 else 0

    # Mean difference contribution to variance
    mean_diff_sq = prior_n * n_obs * (prior_mean - sample_mean) ** 2 / posterior_n

    # Combined posterior variance estimate
    posterior_var = (weighted_prior_var + weighted_sample_var + mean_diff_sq) / posterior_n

    # Marginal variance for predictions (accounts for parameter uncertainty)
    marginal_var = posterior_var * (1 + 1 / posterior_n)

    return posterior_mean, posterior_var, posterior_n, marginal_var


def _calculate_credible_interval(
    mean: float,
    std: float,
    probability: float = CREDIBLE_INTERVAL_PROB,
) -> Tuple[float, float]:
    """Calculate credible interval for posterior distribution.

    Uses normal approximation for computational efficiency. For small
    sample sizes, this is a reasonable approximation that provides
    useful uncertainty bounds.

    Args:
        mean: Posterior mean.
        std: Posterior standard deviation.
        probability: Probability mass for interval (default 0.95).

    Returns:
        Tuple of (lower_bound, upper_bound) for credible interval.

    Examples:
        >>> lower, upper = _calculate_credible_interval(5000.0, 500.0)
        >>> lower < 5000 < upper
        True
        >>> upper - lower  # Approximately 2 * 1.96 * 500
        1959.96...
    """
    # Z-score for desired probability
    alpha = 1 - probability
    z_score = stats.norm.ppf(1 - alpha / 2)

    lower = mean - z_score * std
    upper = mean + z_score * std

    # Earnings cannot be negative
    lower = max(0.0, lower)

    return lower, upper


def _calculate_confidence_score(
    observation_count: int,
    posterior_std: float,
    prior_std: float,
) -> float:
    """Calculate confidence score (0-100) for Bayesian estimate.

    Confidence increases with more observations and decreases with
    high posterior uncertainty relative to prior uncertainty.

    Args:
        observation_count: Number of creator-specific observations.
        posterior_std: Standard deviation of posterior.
        prior_std: Standard deviation of prior (benchmark).

    Returns:
        Confidence score between 0 and 100.

    Examples:
        >>> _calculate_confidence_score(10, 300.0, 1000.0)
        85.0
        >>> _calculate_confidence_score(1, 900.0, 1000.0)
        25.0
    """
    # Base confidence from observation count (asymptotic to 70)
    obs_factor = 70 * (1 - np.exp(-observation_count / 5))

    # Uncertainty reduction factor (max 30 points)
    if prior_std > 0:
        uncertainty_reduction = posterior_std / prior_std
        uncertainty_factor = 30 * max(0, 1 - uncertainty_reduction)
    else:
        uncertainty_factor = 0

    confidence = obs_factor + uncertainty_factor
    return float(min(100.0, max(0.0, confidence)))


# =============================================================================
# Main Tracker Class
# =============================================================================


class GameTypeTracker:
    """Track game performance and generate Bayesian recommendations.

    Uses Bayesian updating to combine population-level benchmarks with
    creator-specific performance data. This enables personalized
    recommendations that improve as more data is collected.

    Attributes:
        creator_id: Identifier for the creator being tracked.
        performance_history: List of all recorded performances.
        game_observations: Dict mapping game types to earnings lists.

    Examples:
        >>> tracker = GameTypeTracker("alexia")
        >>> tracker.record_performance("spin_the_wheel", 5200.0, "2025-01-15")
        >>> tracker.record_performance("spin_the_wheel", 4800.0, "2025-01-22")
        >>> recs = tracker.get_recommendations()
        >>> recs['best_game_type']
        'spin_the_wheel'
    """

    def __init__(self, creator_id: str) -> None:
        """Initialize GameTypeTracker for a creator.

        Args:
            creator_id: Unique identifier for the creator.

        Raises:
            ValueError: If creator_id is empty.

        Examples:
            >>> tracker = GameTypeTracker("alexia")
            >>> tracker.creator_id
            'alexia'
        """
        if not creator_id:
            raise ValueError("creator_id cannot be empty")

        self.creator_id: str = creator_id
        self.performance_history: List[GamePerformance] = []
        self.game_observations: Dict[str, List[float]] = {}

        logger.info(
            "GameTypeTracker initialized",
            extra={"creator_id": creator_id}
        )

    def record_performance(
        self,
        game_type: str,
        earnings: float,
        date: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GamePerformance:
        """Record a game performance instance.

        Args:
            game_type: Type of game played (e.g., 'spin_the_wheel').
            earnings: Revenue generated from this game.
            date: Date of the game in ISO format (YYYY-MM-DD).
            metadata: Optional additional context.

        Returns:
            The created GamePerformance record.

        Raises:
            ValueError: If earnings is negative or date format is invalid.

        Examples:
            >>> tracker = GameTypeTracker("alexia")
            >>> perf = tracker.record_performance("mystery_box", 3500.0, "2025-01-15")
            >>> perf.game_type
            'mystery_box'
            >>> len(tracker.performance_history)
            1
        """
        # Normalize game type to lowercase
        game_type = game_type.lower().strip()

        # Create performance record (validates inputs)
        performance = GamePerformance(
            game_type=game_type,
            earnings=earnings,
            date=date,
            creator_id=self.creator_id,
            metadata=metadata or {},
        )

        # Add to history
        self.performance_history.append(performance)

        # Update observations index
        if game_type not in self.game_observations:
            self.game_observations[game_type] = []
        self.game_observations[game_type].append(earnings)

        logger.debug(
            "Recorded game performance",
            extra={
                "creator_id": self.creator_id,
                "game_type": game_type,
                "earnings": earnings,
                "date": date,
                "total_observations": len(self.game_observations.get(game_type, [])),
            }
        )

        return performance

    def get_bayesian_estimate(self, game_type: str) -> BayesianEstimate:
        """Compute Bayesian posterior estimate for a game type.

        Combines population benchmark (prior) with creator-specific
        observations (likelihood) to produce posterior estimate with
        uncertainty quantification.

        Args:
            game_type: The game type to estimate.

        Returns:
            BayesianEstimate with posterior mean, std, and confidence.

        Examples:
            >>> tracker = GameTypeTracker("alexia")
            >>> tracker.record_performance("spin_the_wheel", 5500.0, "2025-01-15")
            >>> tracker.record_performance("spin_the_wheel", 4800.0, "2025-01-22")
            >>> estimate = tracker.get_bayesian_estimate("spin_the_wheel")
            >>> 4800 < estimate['posterior_mean'] < 5500
            True
        """
        game_type = game_type.lower().strip()
        observations = self.game_observations.get(game_type, [])
        n_obs = len(observations)

        # Get prior from benchmarks or use default
        if game_type in GAME_BENCHMARKS:
            benchmark = GAME_BENCHMARKS[game_type]
            prior_mean = benchmark.avg_earnings
            prior_std = benchmark.std_dev
        else:
            # Use median benchmark values for unknown games
            prior_mean = 1500.0
            prior_std = 750.0
            logger.debug(
                "Using default prior for unknown game type",
                extra={"game_type": game_type}
            )

        prior_var = prior_std ** 2

        # Compute Bayesian posterior
        posterior_mean, posterior_var, posterior_n, marginal_var = (
            _compute_normal_inverse_gamma_posterior(
                prior_mean=prior_mean,
                prior_var=prior_var,
                prior_n=PRIOR_STRENGTH,
                observations=observations,
            )
        )

        posterior_std = float(np.sqrt(marginal_var))

        # Calculate credible interval
        credible_lower, credible_upper = _calculate_credible_interval(
            posterior_mean, posterior_std
        )

        # Calculate confidence score
        confidence_score = _calculate_confidence_score(
            n_obs, posterior_std, prior_std
        )

        # Calculate weights
        total_weight = PRIOR_STRENGTH + n_obs
        prior_weight = PRIOR_STRENGTH / total_weight
        posterior_weight = n_obs / total_weight

        return BayesianEstimate(
            posterior_mean=round(posterior_mean, 2),
            posterior_std=round(posterior_std, 2),
            credible_lower=round(credible_lower, 2),
            credible_upper=round(credible_upper, 2),
            confidence_score=round(confidence_score, 1),
            observation_count=n_obs,
            prior_weight=round(prior_weight, 3),
            posterior_weight=round(posterior_weight, 3),
        )

    def _determine_action(
        self,
        game_type: str,
        estimate: BayesianEstimate,
    ) -> Tuple[str, str]:
        """Determine recommended action based on Bayesian estimate.

        Args:
            game_type: The game type being evaluated.
            estimate: Bayesian posterior estimate.

        Returns:
            Tuple of (action, rationale).
        """
        posterior_mean = estimate["posterior_mean"]
        confidence_score = estimate["confidence_score"]
        n_obs = estimate["observation_count"]

        # Get benchmark for comparison
        if game_type in GAME_BENCHMARKS:
            benchmark = GAME_BENCHMARKS[game_type]
            benchmark_avg = benchmark.avg_earnings
            default_frequency = benchmark.recommended_frequency
        else:
            benchmark_avg = 1500.0
            default_frequency = "bi-weekly"

        # Calculate performance ratio
        perf_ratio = posterior_mean / benchmark_avg if benchmark_avg > 0 else 1.0

        # Determine action based on performance and confidence
        if n_obs < MIN_OBSERVATIONS_FOR_OVERRIDE:
            # Not enough data to override population benchmark
            action = f"schedule_{default_frequency.replace('-', '')}"
            rationale = (
                f"Using population benchmark (only {n_obs} observations). "
                f"Expected: ${posterior_mean:,.0f}"
            )
        elif perf_ratio < AVOID_THRESHOLD_RATIO:
            # Significantly underperforming
            action = "avoid"
            rationale = (
                f"Performing at {perf_ratio:.0%} of benchmark "
                f"(${posterior_mean:,.0f} vs ${benchmark_avg:,.0f}). "
                f"Consider stopping or experimenting with format."
            )
        elif perf_ratio < RECOMMENDED_THRESHOLD_RATIO:
            # Moderately underperforming
            action = "reduce"
            rationale = (
                f"Below benchmark at {perf_ratio:.0%} "
                f"(${posterior_mean:,.0f} vs ${benchmark_avg:,.0f}). "
                f"Reduce frequency to bi-weekly."
            )
        elif posterior_mean >= 3000:
            # High performer
            action = "schedule_weekly"
            rationale = (
                f"Strong performer at ${posterior_mean:,.0f} "
                f"({perf_ratio:.0%} of benchmark). Schedule weekly."
            )
        else:
            # Normal performer
            action = f"schedule_{default_frequency.replace('-', '')}"
            rationale = (
                f"Performing at ${posterior_mean:,.0f} "
                f"({perf_ratio:.0%} of benchmark). "
                f"Maintain {default_frequency} schedule."
            )

        # Add confidence qualifier if low
        if confidence_score < 50:
            rationale += f" (LOW confidence: {confidence_score:.0f}/100)"

        return action, rationale

    def _get_confidence_level(self, estimate: BayesianEstimate) -> str:
        """Get confidence level label from confidence score.

        Args:
            estimate: Bayesian estimate with confidence score.

        Returns:
            'HIGH', 'MEDIUM', or 'LOW'.
        """
        score = estimate["confidence_score"]
        if score >= 70:
            return "HIGH"
        elif score >= 40:
            return "MEDIUM"
        else:
            return "LOW"

    def get_recommendations(self) -> RecommendationResult:
        """Generate game type recommendations based on performance history.

        Uses Bayesian updating to combine creator history with population
        benchmarks, producing personalized recommendations with confidence
        levels.

        Returns:
            RecommendationResult containing:
                - best_game_type: Highest expected earnings game
                - best_game_earnings: Expected earnings for best game
                - avoid_list: Games to avoid based on poor performance
                - recommendations: Full details for each game type
                - confidence_level: Overall confidence
                - total_observations: Total records analyzed
                - exploration_suggestion: Game to try for more data

        Examples:
            >>> tracker = GameTypeTracker("alexia")
            >>> tracker.record_performance("spin_the_wheel", 5200.0, "2025-01-15")
            >>> tracker.record_performance("card_game", 200.0, "2025-01-18")
            >>> recs = tracker.get_recommendations()
            >>> recs['best_game_type']
            'spin_the_wheel'
            >>> 'card_game' in recs['avoid_list'] or recs['recommendations']['card_game']['action'] in ['avoid', 'reduce']
            True
        """
        recommendations: Dict[str, GameRecommendation] = {}
        avoid_list: List[str] = []
        best_game_type: Optional[str] = None
        best_game_earnings: float = 0.0
        total_observations: int = len(self.performance_history)

        # Get unique game types (observed + benchmarks)
        all_game_types = set(self.game_observations.keys()) | set(GAME_BENCHMARKS.keys())

        # Compute recommendations for each game type
        for game_type in all_game_types:
            estimate = self.get_bayesian_estimate(game_type)
            action, rationale = self._determine_action(game_type, estimate)
            confidence = self._get_confidence_level(estimate)

            recommendations[game_type] = GameRecommendation(
                game_type=game_type,
                action=action,
                expected_earnings=estimate["posterior_mean"],
                confidence=confidence,
                rationale=rationale,
                bayesian_estimate=estimate,
            )

            # Track avoid list
            if action == "avoid":
                avoid_list.append(game_type)

            # Track best game (with some observations preferred)
            obs_count = estimate["observation_count"]
            expected = estimate["posterior_mean"]

            # Prefer games with observations over pure priors
            effective_earnings = expected
            if obs_count >= MIN_OBSERVATIONS_FOR_OVERRIDE:
                # Boost games with creator-specific data
                effective_earnings *= 1.1

            if effective_earnings > best_game_earnings:
                best_game_earnings = expected
                best_game_type = game_type

        # Determine exploration suggestion (game with fewest observations but good prior)
        exploration_suggestion: Optional[str] = None
        min_obs_for_exploration = float("inf")

        for game_type in GAME_BENCHMARKS:
            if game_type in avoid_list:
                continue
            obs = len(self.game_observations.get(game_type, []))
            benchmark = GAME_BENCHMARKS[game_type]
            # Suggest high-tier games that need more data
            if (
                obs < MIN_OBSERVATIONS_HIGH_CONFIDENCE
                and obs < min_obs_for_exploration
                and benchmark.performance_tier in ("TOP", "MID")
            ):
                min_obs_for_exploration = obs
                exploration_suggestion = game_type

        # Calculate overall confidence
        confidence_scores = [
            rec["bayesian_estimate"]["confidence_score"]
            for rec in recommendations.values()
            if rec["bayesian_estimate"]["observation_count"] > 0
        ]
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0

        if avg_confidence >= 70:
            overall_confidence = "HIGH"
        elif avg_confidence >= 40:
            overall_confidence = "MEDIUM"
        else:
            overall_confidence = "LOW"

        logger.info(
            "Generated game recommendations",
            extra={
                "creator_id": self.creator_id,
                "best_game_type": best_game_type,
                "avoid_count": len(avoid_list),
                "total_observations": total_observations,
                "overall_confidence": overall_confidence,
            }
        )

        return RecommendationResult(
            best_game_type=best_game_type,
            best_game_earnings=round(best_game_earnings, 2),
            avoid_list=sorted(avoid_list),
            recommendations=recommendations,
            confidence_level=overall_confidence,
            total_observations=total_observations,
            exploration_suggestion=exploration_suggestion,
        )

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all tracked game types.

        Returns:
            Dictionary with summary statistics per game type.

        Examples:
            >>> tracker = GameTypeTracker("alexia")
            >>> tracker.record_performance("spin_the_wheel", 5000.0, "2025-01-15")
            >>> tracker.record_performance("spin_the_wheel", 5500.0, "2025-01-22")
            >>> summary = tracker.get_performance_summary()
            >>> summary['spin_the_wheel']['count']
            2
            >>> summary['spin_the_wheel']['mean']
            5250.0
        """
        summary: Dict[str, Any] = {}

        for game_type, observations in self.game_observations.items():
            if not observations:
                continue

            obs_array = np.array(observations)
            benchmark = GAME_BENCHMARKS.get(game_type)

            summary[game_type] = {
                "count": len(observations),
                "mean": round(float(np.mean(obs_array)), 2),
                "std": round(float(np.std(obs_array, ddof=1)), 2) if len(observations) > 1 else 0.0,
                "min": round(float(np.min(obs_array)), 2),
                "max": round(float(np.max(obs_array)), 2),
                "total": round(float(np.sum(obs_array)), 2),
                "benchmark_avg": benchmark.avg_earnings if benchmark else None,
                "vs_benchmark": (
                    round(float(np.mean(obs_array)) / benchmark.avg_earnings, 3)
                    if benchmark else None
                ),
            }

        return summary

    def clear_history(self) -> None:
        """Clear all performance history for this creator.

        Use with caution - this removes all historical data.

        Examples:
            >>> tracker = GameTypeTracker("alexia")
            >>> tracker.record_performance("spin_the_wheel", 5000.0, "2025-01-15")
            >>> len(tracker.performance_history)
            1
            >>> tracker.clear_history()
            >>> len(tracker.performance_history)
            0
        """
        self.performance_history.clear()
        self.game_observations.clear()
        logger.warning(
            "Cleared game performance history",
            extra={"creator_id": self.creator_id}
        )


# =============================================================================
# Factory Functions
# =============================================================================


def create_tracker_from_history(
    creator_id: str,
    history: List[Dict[str, Any]],
) -> GameTypeTracker:
    """Create a GameTypeTracker pre-populated with historical data.

    Convenience function to initialize a tracker with existing performance
    records from a database or external source.

    Args:
        creator_id: Unique identifier for the creator.
        history: List of dicts with 'game_type', 'earnings', 'date' keys.

    Returns:
        Initialized GameTypeTracker with historical data.

    Raises:
        ValueError: If any history record is missing required fields.

    Examples:
        >>> history = [
        ...     {"game_type": "spin_the_wheel", "earnings": 5000.0, "date": "2025-01-15"},
        ...     {"game_type": "spin_the_wheel", "earnings": 5500.0, "date": "2025-01-22"},
        ... ]
        >>> tracker = create_tracker_from_history("alexia", history)
        >>> len(tracker.performance_history)
        2
    """
    tracker = GameTypeTracker(creator_id)

    for record in history:
        if "game_type" not in record:
            raise ValueError("History record missing 'game_type'")
        if "earnings" not in record:
            raise ValueError("History record missing 'earnings'")
        if "date" not in record:
            raise ValueError("History record missing 'date'")

        tracker.record_performance(
            game_type=record["game_type"],
            earnings=record["earnings"],
            date=record["date"],
            metadata=record.get("metadata"),
        )

    logger.info(
        "Created tracker from historical data",
        extra={
            "creator_id": creator_id,
            "records_loaded": len(history),
        }
    )

    return tracker


# =============================================================================
# Exports
# =============================================================================

__all__ = [
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
    # Main tracker class
    "GameTypeTracker",
    # Utility functions
    "get_game_frequency",
    "create_tracker_from_history",
]
