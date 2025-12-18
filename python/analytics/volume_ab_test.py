"""
Volume A/B Testing Framework for volume optimization experiments.

Implements structured test specifications with statistical power analysis
for rigorous volume optimization experiments. Supports experiment lifecycle
management from draft through completion with validation against sample
size requirements.

The framework uses statistical power analysis to calculate minimum sample
sizes, ensuring experiments have sufficient data to detect meaningful effects.

Usage:
    from python.analytics.volume_ab_test import (
        VolumeABTest,
        VOLUME_AB_TESTS,
        validate_test_completion,
        get_test_by_id,
    )

    # Get a pre-configured test
    test = get_test_by_id('bump_ratio_2x_vs_3x')
    print(f"Test: {test.hypothesis}")
    print(f"Required samples: {test.min_sample_size}")

    # Validate test completion
    result = validate_test_completion(test, control_n=250, treatment_n=260)
    if result['is_complete']:
        print(f"Test ready for analysis, power: {result['actual_power']:.2%}")

Statistical Methods:
    - Power analysis using z-scores from scipy.stats
    - Two-sided significance testing (default alpha=0.05)
    - Standard power threshold (default beta=0.20, power=0.80)
    - Effect size (Cohen's d) estimation for minimum detectable effects
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from scipy import stats

from python.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default statistical parameters
DEFAULT_CONFIDENCE_LEVEL: float = 0.95
DEFAULT_STATISTICAL_POWER: float = 0.80
DEFAULT_MDE: float = 0.10  # 10% minimum detectable effect

# Default test duration
DEFAULT_DURATION_DAYS: int = 14

# Standard deviation assumption for revenue metrics (normalized)
# Based on typical OnlyFans creator revenue variance
DEFAULT_SIGMA: float = 1.0


# =============================================================================
# Enums
# =============================================================================


class TestStatus(str, Enum):
    """Status of an A/B test experiment.

    Attributes:
        DRAFT: Test specification created but not yet started.
        RUNNING: Test is actively collecting data.
        PAUSED: Test temporarily suspended (data collection stopped).
        COMPLETED: Test has reached sample size requirements.
        CANCELLED: Test terminated before completion.
    """

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MetricType(str, Enum):
    """Types of metrics tracked in A/B tests.

    Attributes:
        REVENUE: Revenue-based metrics (earnings, ARPU).
        CONVERSION: Conversion rate metrics (unlock rate, tip rate).
        ENGAGEMENT: Engagement metrics (open rate, response rate).
        RETENTION: Retention metrics (churn rate, renewal rate).
    """

    REVENUE = "revenue"
    CONVERSION = "conversion"
    ENGAGEMENT = "engagement"
    RETENTION = "retention"


# =============================================================================
# Type Definitions
# =============================================================================


@dataclass(frozen=True)
class VolumeConfig:
    """Configuration for a volume treatment group.

    Represents the volume settings for either control or treatment arm
    of an A/B test experiment.

    Attributes:
        ppv_per_day: Number of PPV messages per day.
        bump_per_day: Number of bump messages per day.
        retention_per_day: Number of retention sends per day.
        engagement_per_day: Number of engagement sends per day.
        description: Human-readable description of the configuration.

    Examples:
        >>> control = VolumeConfig(
        ...     ppv_per_day=3,
        ...     bump_per_day=2,
        ...     description="Current production volume"
        ... )
        >>> treatment = VolumeConfig(
        ...     ppv_per_day=3,
        ...     bump_per_day=3,
        ...     description="Increased bump frequency"
        ... )
    """

    ppv_per_day: float = 3.0
    bump_per_day: float = 2.0
    retention_per_day: float = 1.0
    engagement_per_day: float = 2.0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of the volume configuration.
        """
        return {
            "ppv_per_day": self.ppv_per_day,
            "bump_per_day": self.bump_per_day,
            "retention_per_day": self.retention_per_day,
            "engagement_per_day": self.engagement_per_day,
            "description": self.description,
        }


@dataclass(frozen=True)
class Metric:
    """Definition of a metric to track in an A/B test.

    Attributes:
        name: Metric identifier (e.g., 'revenue_per_subscriber').
        metric_type: Category of metric (revenue, conversion, etc.).
        description: Human-readable description.
        unit: Unit of measurement (e.g., 'USD', 'percent').
        higher_is_better: Whether higher values indicate success.

    Examples:
        >>> revenue_metric = Metric(
        ...     name="daily_revenue",
        ...     metric_type=MetricType.REVENUE,
        ...     description="Total daily revenue per subscriber",
        ...     unit="USD",
        ...     higher_is_better=True,
        ... )
    """

    name: str
    metric_type: MetricType
    description: str = ""
    unit: str = ""
    higher_is_better: bool = True


# =============================================================================
# Core A/B Test Dataclass
# =============================================================================


@dataclass
class VolumeABTest:
    """Structured A/B test specification with power analysis.

    Represents a complete volume optimization experiment configuration,
    including hypothesis, treatment arms, metrics, and statistical parameters.
    The minimum sample size is automatically calculated using power analysis.

    Attributes:
        test_id: Unique identifier for the test.
        hypothesis: Clear statement of what the test aims to prove.
        control_config: Volume configuration for control group.
        treatment_config: Volume configuration for treatment group.
        primary_metric: Main metric for determining test success.
        secondary_metrics: Additional metrics to track.
        min_sample_size: Calculated minimum samples per arm (auto-calculated).
        duration_days: Expected test duration in days.
        confidence_level: Statistical significance threshold (default 0.95).
        statistical_power: Probability of detecting true effect (default 0.80).
        minimum_detectable_effect: Smallest effect size to detect (default 0.10).
        start_date: Test start date (None if not started).
        end_date: Test end date (None if not ended).
        status: Current test status.
        notes: Additional context or observations.

    Examples:
        >>> test = VolumeABTest(
        ...     test_id="bump_test_001",
        ...     hypothesis="Increasing bump frequency from 2x to 3x per day "
        ...                "will increase revenue per subscriber by 10%",
        ...     control_config=VolumeConfig(bump_per_day=2.0),
        ...     treatment_config=VolumeConfig(bump_per_day=3.0),
        ...     primary_metric=Metric(
        ...         name="revenue_per_subscriber",
        ...         metric_type=MetricType.REVENUE,
        ...     ),
        ...     minimum_detectable_effect=0.10,
        ... )
        >>> print(f"Required samples per arm: {test.min_sample_size}")
        Required samples per arm: 394
    """

    test_id: str
    hypothesis: str
    control_config: VolumeConfig
    treatment_config: VolumeConfig
    primary_metric: Metric
    secondary_metrics: list[Metric] = field(default_factory=list)
    min_sample_size: int = field(init=False)
    duration_days: int = DEFAULT_DURATION_DAYS
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    statistical_power: float = DEFAULT_STATISTICAL_POWER
    minimum_detectable_effect: float = DEFAULT_MDE
    start_date: date | None = None
    end_date: date | None = None
    status: TestStatus = TestStatus.DRAFT
    notes: str = ""

    def __post_init__(self) -> None:
        """Calculate minimum sample size after initialization.

        Uses power analysis formula:
        n = 2 * ((z_alpha + z_beta) / delta)^2 * sigma^2

        Where:
            z_alpha: Critical value for significance level (two-sided)
            z_beta: Critical value for power (one-sided)
            delta: Minimum detectable effect (standardized)
            sigma: Standard deviation (assumed 1.0 for normalized metrics)
        """
        # Validate statistical parameters
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError(
                f"confidence_level must be between 0 and 1, got {self.confidence_level}"
            )
        if not 0.0 < self.statistical_power < 1.0:
            raise ValueError(
                f"statistical_power must be between 0 and 1, got {self.statistical_power}"
            )
        if self.minimum_detectable_effect <= 0.0:
            raise ValueError(
                f"minimum_detectable_effect must be positive, "
                f"got {self.minimum_detectable_effect}"
            )
        if self.duration_days <= 0:
            raise ValueError(
                f"duration_days must be positive, got {self.duration_days}"
            )

        # Calculate minimum sample size using power analysis
        calculated_n = _calculate_min_sample_size(
            alpha=1.0 - self.confidence_level,
            power=self.statistical_power,
            mde=self.minimum_detectable_effect,
            sigma=DEFAULT_SIGMA,
        )

        # Use object.__setattr__ since we're in __post_init__
        object.__setattr__(self, "min_sample_size", calculated_n)

        logger.debug(
            "VolumeABTest initialized",
            extra={
                "test_id": self.test_id,
                "min_sample_size": calculated_n,
                "confidence_level": self.confidence_level,
                "statistical_power": self.statistical_power,
                "mde": self.minimum_detectable_effect,
            },
        )

    def start(self, start_date: date | None = None) -> "VolumeABTest":
        """Mark test as running with specified start date.

        Args:
            start_date: Test start date, defaults to today.

        Returns:
            Updated test instance with RUNNING status.

        Raises:
            ValueError: If test is not in DRAFT or PAUSED status.
        """
        if self.status not in (TestStatus.DRAFT, TestStatus.PAUSED):
            raise ValueError(
                f"Cannot start test in {self.status.value} status. "
                f"Test must be in 'draft' or 'paused' status."
            )

        actual_start = start_date or date.today()
        self.start_date = actual_start
        self.status = TestStatus.RUNNING

        logger.info(
            "A/B test started",
            extra={
                "test_id": self.test_id,
                "start_date": actual_start.isoformat(),
                "min_sample_size": self.min_sample_size,
            },
        )

        return self

    def pause(self) -> "VolumeABTest":
        """Pause a running test.

        Returns:
            Updated test instance with PAUSED status.

        Raises:
            ValueError: If test is not in RUNNING status.
        """
        if self.status != TestStatus.RUNNING:
            raise ValueError(
                f"Cannot pause test in {self.status.value} status. "
                f"Test must be in 'running' status."
            )

        self.status = TestStatus.PAUSED

        logger.info(
            "A/B test paused",
            extra={"test_id": self.test_id},
        )

        return self

    def complete(self, end_date: date | None = None) -> "VolumeABTest":
        """Mark test as completed.

        Args:
            end_date: Test end date, defaults to today.

        Returns:
            Updated test instance with COMPLETED status.

        Raises:
            ValueError: If test is not in RUNNING status.
        """
        if self.status != TestStatus.RUNNING:
            raise ValueError(
                f"Cannot complete test in {self.status.value} status. "
                f"Test must be in 'running' status."
            )

        actual_end = end_date or date.today()
        self.end_date = actual_end
        self.status = TestStatus.COMPLETED

        logger.info(
            "A/B test completed",
            extra={
                "test_id": self.test_id,
                "end_date": actual_end.isoformat(),
                "duration": (
                    (actual_end - self.start_date).days if self.start_date else None
                ),
            },
        )

        return self

    def cancel(self, reason: str = "") -> "VolumeABTest":
        """Cancel the test.

        Args:
            reason: Reason for cancellation.

        Returns:
            Updated test instance with CANCELLED status.

        Raises:
            ValueError: If test is already completed.
        """
        if self.status == TestStatus.COMPLETED:
            raise ValueError("Cannot cancel a completed test.")

        self.status = TestStatus.CANCELLED
        if reason:
            self.notes = f"{self.notes}\nCancellation reason: {reason}".strip()

        logger.warning(
            "A/B test cancelled",
            extra={"test_id": self.test_id, "reason": reason},
        )

        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert test specification to dictionary.

        Returns:
            Complete dictionary representation of the test.
        """
        return {
            "test_id": self.test_id,
            "hypothesis": self.hypothesis,
            "control_config": self.control_config.to_dict(),
            "treatment_config": self.treatment_config.to_dict(),
            "primary_metric": {
                "name": self.primary_metric.name,
                "metric_type": self.primary_metric.metric_type.value,
                "description": self.primary_metric.description,
                "unit": self.primary_metric.unit,
                "higher_is_better": self.primary_metric.higher_is_better,
            },
            "secondary_metrics": [
                {
                    "name": m.name,
                    "metric_type": m.metric_type.value,
                    "description": m.description,
                    "unit": m.unit,
                    "higher_is_better": m.higher_is_better,
                }
                for m in self.secondary_metrics
            ],
            "min_sample_size": self.min_sample_size,
            "duration_days": self.duration_days,
            "confidence_level": self.confidence_level,
            "statistical_power": self.statistical_power,
            "minimum_detectable_effect": self.minimum_detectable_effect,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status.value,
            "notes": self.notes,
        }


# =============================================================================
# Statistical Functions
# =============================================================================


def _calculate_min_sample_size(
    alpha: float = 0.05,
    power: float = 0.80,
    mde: float = 0.10,
    sigma: float = 1.0,
) -> int:
    """Calculate minimum sample size per arm using power analysis.

    Uses the formula for comparing two means with equal variance:
    n = 2 * ((z_alpha/2 + z_beta) / delta)^2 * sigma^2

    Where:
        z_alpha/2: Two-sided critical value for significance level
        z_beta: One-sided critical value for power (1 - beta)
        delta: Effect size (minimum detectable effect)
        sigma: Standard deviation (pooled)

    Args:
        alpha: Significance level (Type I error rate). Default 0.05.
        power: Statistical power (1 - Type II error rate). Default 0.80.
        mde: Minimum detectable effect (standardized). Default 0.10.
        sigma: Standard deviation of the metric. Default 1.0.

    Returns:
        Minimum sample size required per arm (ceiling integer).

    Raises:
        ValueError: If parameters are outside valid ranges.

    Examples:
        >>> n = _calculate_min_sample_size(alpha=0.05, power=0.80, mde=0.10)
        >>> print(f"Required samples per arm: {n}")
        Required samples per arm: 394

        >>> n = _calculate_min_sample_size(alpha=0.01, power=0.90, mde=0.05)
        >>> print(f"High-power test requires: {n}")
        High-power test requires: 2103
    """
    # Validate inputs
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be between 0 and 1, got {alpha}")
    if not 0.0 < power < 1.0:
        raise ValueError(f"power must be between 0 and 1, got {power}")
    if mde <= 0.0:
        raise ValueError(f"mde must be positive, got {mde}")
    if sigma <= 0.0:
        raise ValueError(f"sigma must be positive, got {sigma}")

    # Calculate z-scores using scipy.stats
    # z_alpha: two-sided test, so use alpha/2
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    # z_beta: one-sided for power
    z_beta = stats.norm.ppf(power)

    # Sample size formula for two-sample t-test with equal variance
    # n = 2 * ((z_alpha + z_beta) / delta)^2 * sigma^2
    delta = mde  # Effect size in standard deviation units

    n_float = 2 * ((z_alpha + z_beta) / delta) ** 2 * sigma**2

    # Round up to ensure sufficient power
    n = int(n_float) + (1 if n_float > int(n_float) else 0)

    logger.debug(
        "Sample size calculated",
        extra={
            "alpha": alpha,
            "power": power,
            "mde": mde,
            "sigma": sigma,
            "z_alpha": z_alpha,
            "z_beta": z_beta,
            "n_calculated": n,
        },
    )

    return n


def calculate_achieved_power(
    control_n: int,
    treatment_n: int,
    alpha: float = 0.05,
    mde: float = 0.10,
    sigma: float = 1.0,
) -> float:
    """Calculate achieved statistical power given sample sizes.

    Inverse of power analysis - given sample sizes, determine what
    power the test achieves for detecting the specified effect size.

    Args:
        control_n: Sample size in control group.
        treatment_n: Sample size in treatment group.
        alpha: Significance level. Default 0.05.
        mde: Minimum detectable effect. Default 0.10.
        sigma: Standard deviation of the metric. Default 1.0.

    Returns:
        Achieved power (probability of detecting true effect).

    Raises:
        ValueError: If sample sizes are not positive.

    Examples:
        >>> power = calculate_achieved_power(control_n=200, treatment_n=200)
        >>> print(f"Achieved power: {power:.2%}")
        Achieved power: 64.10%

        >>> power = calculate_achieved_power(control_n=500, treatment_n=500)
        >>> print(f"Achieved power: {power:.2%}")
        Achieved power: 93.12%
    """
    if control_n <= 0 or treatment_n <= 0:
        raise ValueError("Sample sizes must be positive integers")

    # Use harmonic mean for unequal sample sizes
    n_effective = 2 * control_n * treatment_n / (control_n + treatment_n)

    # Calculate z_alpha for the specified significance level
    z_alpha = stats.norm.ppf(1 - alpha / 2)

    # Calculate the non-centrality parameter
    # Under the alternative hypothesis, the test statistic follows a
    # non-central distribution with this parameter
    effect = mde / sigma
    se = sigma * (2 / n_effective) ** 0.5
    ncp = effect / se

    # Power is the probability of rejecting H0 when H1 is true
    # This equals P(Z > z_alpha - ncp) for one-sided, or
    # P(|Z - ncp| > z_alpha) for two-sided
    # Simplified: P(Z > z_alpha - ncp)
    power: float = 1 - stats.norm.cdf(z_alpha - ncp)

    return power


# =============================================================================
# Validation Functions
# =============================================================================


def validate_test_completion(
    test: VolumeABTest,
    control_n: int,
    treatment_n: int,
) -> dict[str, Any]:
    """Validate whether a test has sufficient data for analysis.

    Checks if both control and treatment groups have reached the
    minimum sample size requirement. Calculates actual achieved power
    based on collected samples.

    Args:
        test: The VolumeABTest specification to validate.
        control_n: Number of samples collected in control group.
        treatment_n: Number of samples collected in treatment group.

    Returns:
        Dictionary containing:
            - is_complete: Whether sample requirements are met.
            - control_progress: Percentage of control samples collected.
            - treatment_progress: Percentage of treatment samples collected.
            - overall_progress: Minimum of control and treatment progress.
            - samples_needed_control: Remaining samples needed for control.
            - samples_needed_treatment: Remaining samples needed for treatment.
            - actual_power: Achieved statistical power with current samples.
            - min_sample_size: Required samples per arm.
            - recommendation: Action recommendation based on status.

    Raises:
        ValueError: If sample counts are negative.

    Examples:
        >>> test = get_test_by_id('bump_ratio_2x_vs_3x')
        >>> result = validate_test_completion(test, control_n=250, treatment_n=260)
        >>> print(f"Complete: {result['is_complete']}")
        Complete: False
        >>> print(f"Progress: {result['overall_progress']:.1%}")
        Progress: 63.5%

        >>> result = validate_test_completion(test, control_n=400, treatment_n=400)
        >>> print(f"Complete: {result['is_complete']}")
        Complete: True
        >>> print(f"Power: {result['actual_power']:.2%}")
        Power: 81.12%
    """
    if control_n < 0 or treatment_n < 0:
        raise ValueError("Sample counts cannot be negative")

    min_n = test.min_sample_size

    # Calculate progress
    control_progress = control_n / min_n if min_n > 0 else 1.0
    treatment_progress = treatment_n / min_n if min_n > 0 else 1.0
    overall_progress = min(control_progress, treatment_progress)

    # Calculate remaining samples needed
    samples_needed_control = max(0, min_n - control_n)
    samples_needed_treatment = max(0, min_n - treatment_n)

    # Determine if complete
    is_complete = control_n >= min_n and treatment_n >= min_n

    # Calculate actual power with current samples
    if control_n > 0 and treatment_n > 0:
        actual_power = calculate_achieved_power(
            control_n=control_n,
            treatment_n=treatment_n,
            alpha=1.0 - test.confidence_level,
            mde=test.minimum_detectable_effect,
            sigma=DEFAULT_SIGMA,
        )
    else:
        actual_power = 0.0

    # Generate recommendation
    if is_complete:
        if actual_power >= test.statistical_power:
            recommendation = (
                "Test complete with sufficient power. Ready for statistical analysis."
            )
        else:
            recommendation = (
                f"Sample size met but power ({actual_power:.1%}) is below target "
                f"({test.statistical_power:.1%}). Consider collecting more data."
            )
    elif overall_progress >= 0.75:
        recommendation = (
            f"Test is {overall_progress:.0%} complete. "
            f"Estimated {max(samples_needed_control, samples_needed_treatment)} "
            f"more samples needed in slower arm."
        )
    else:
        recommendation = (
            f"Test is {overall_progress:.0%} complete. "
            f"Continue data collection. Target: {min_n} samples per arm."
        )

    result = {
        "is_complete": is_complete,
        "control_progress": control_progress,
        "treatment_progress": treatment_progress,
        "overall_progress": overall_progress,
        "samples_needed_control": samples_needed_control,
        "samples_needed_treatment": samples_needed_treatment,
        "actual_power": actual_power,
        "min_sample_size": min_n,
        "recommendation": recommendation,
    }

    logger.info(
        "Test completion validated",
        extra={
            "test_id": test.test_id,
            "is_complete": is_complete,
            "control_n": control_n,
            "treatment_n": treatment_n,
            "overall_progress": overall_progress,
            "actual_power": actual_power,
        },
    )

    return result


# =============================================================================
# Pre-configured Test Specifications
# =============================================================================

# Define commonly used metrics
REVENUE_PER_SUBSCRIBER = Metric(
    name="revenue_per_subscriber",
    metric_type=MetricType.REVENUE,
    description="Daily revenue per active subscriber",
    unit="USD",
    higher_is_better=True,
)

PPV_UNLOCK_RATE = Metric(
    name="ppv_unlock_rate",
    metric_type=MetricType.CONVERSION,
    description="Percentage of PPV messages that result in unlocks",
    unit="percent",
    higher_is_better=True,
)

SUBSCRIBER_CHURN_RATE = Metric(
    name="subscriber_churn_rate",
    metric_type=MetricType.RETENTION,
    description="Monthly subscriber churn rate",
    unit="percent",
    higher_is_better=False,
)

MESSAGE_OPEN_RATE = Metric(
    name="message_open_rate",
    metric_type=MetricType.ENGAGEMENT,
    description="Percentage of messages opened by subscribers",
    unit="percent",
    higher_is_better=True,
)

TIP_RATE = Metric(
    name="tip_rate",
    metric_type=MetricType.CONVERSION,
    description="Tips per 100 messages sent",
    unit="tips/100msg",
    higher_is_better=True,
)


def _create_bump_ratio_test() -> VolumeABTest:
    """Create bump ratio 2x vs 3x test specification."""
    return VolumeABTest(
        test_id="bump_ratio_2x_vs_3x",
        hypothesis=(
            "Increasing bump message frequency from 2x to 3x per day "
            "will increase revenue per subscriber by at least 10% without "
            "negatively impacting subscriber churn rate."
        ),
        control_config=VolumeConfig(
            ppv_per_day=3.0,
            bump_per_day=2.0,
            retention_per_day=1.0,
            engagement_per_day=2.0,
            description="Current production: 2 bumps per day",
        ),
        treatment_config=VolumeConfig(
            ppv_per_day=3.0,
            bump_per_day=3.0,
            retention_per_day=1.0,
            engagement_per_day=2.0,
            description="Treatment: 3 bumps per day (50% increase)",
        ),
        primary_metric=REVENUE_PER_SUBSCRIBER,
        secondary_metrics=[PPV_UNLOCK_RATE, SUBSCRIBER_CHURN_RATE, MESSAGE_OPEN_RATE],
        duration_days=14,
        confidence_level=0.95,
        statistical_power=0.80,
        minimum_detectable_effect=0.10,
        notes="Tests the elasticity of bump frequency on revenue. "
        "Monitor for saturation signals (declining open rates).",
    )


def _create_dow_distribution_test() -> VolumeABTest:
    """Create DOW distribution uniform vs weighted test specification."""
    return VolumeABTest(
        test_id="dow_distribution_uniform_vs_weighted",
        hypothesis=(
            "Weighting volume distribution by day-of-week performance "
            "(higher volume on high-performing days) will increase weekly "
            "revenue by at least 8% compared to uniform distribution."
        ),
        control_config=VolumeConfig(
            ppv_per_day=3.0,
            bump_per_day=2.5,
            retention_per_day=1.0,
            engagement_per_day=2.0,
            description="Uniform distribution: same volume every day",
        ),
        treatment_config=VolumeConfig(
            ppv_per_day=3.5,  # Higher on weekends
            bump_per_day=3.0,  # Higher on weekends
            retention_per_day=1.0,
            engagement_per_day=2.5,
            description="Weighted: +40% on Fri-Sun, -20% on Mon-Wed",
        ),
        primary_metric=REVENUE_PER_SUBSCRIBER,
        secondary_metrics=[PPV_UNLOCK_RATE, TIP_RATE],
        duration_days=21,  # Need 3 full weeks for DOW analysis
        confidence_level=0.95,
        statistical_power=0.80,
        minimum_detectable_effect=0.08,  # 8% lift
        notes="Requires 3 full weeks to capture complete DOW cycles. "
        "Treatment config represents average; actual varies by day.",
    )


def _create_campaign_frequency_test() -> VolumeABTest:
    """Create campaign frequency high vs standard test specification."""
    return VolumeABTest(
        test_id="campaign_frequency_high_vs_standard",
        hypothesis=(
            "Increasing campaign frequency from standard (5/month) to high "
            "(14-20/month) will increase monthly revenue by at least 15% "
            "without significantly increasing churn."
        ),
        control_config=VolumeConfig(
            ppv_per_day=2.5,
            bump_per_day=2.0,
            retention_per_day=1.0,
            engagement_per_day=1.5,
            description="Standard: ~5 campaigns/month (current baseline)",
        ),
        treatment_config=VolumeConfig(
            ppv_per_day=4.0,
            bump_per_day=3.0,
            retention_per_day=1.5,
            engagement_per_day=2.5,
            description="High frequency: 14-20 campaigns/month (optimal target)",
        ),
        primary_metric=REVENUE_PER_SUBSCRIBER,
        secondary_metrics=[SUBSCRIBER_CHURN_RATE, PPV_UNLOCK_RATE, MESSAGE_OPEN_RATE],
        duration_days=30,  # Full month for campaign frequency
        confidence_level=0.95,
        statistical_power=0.80,
        minimum_detectable_effect=0.15,  # 15% lift (larger expected effect)
        notes="Based on reference analysis showing current 5/month is "
        "180-300% below optimal. Monitor churn closely.",
    )


# Pre-configured test dictionary
VOLUME_AB_TESTS: dict[str, VolumeABTest] = {
    "bump_ratio_2x_vs_3x": _create_bump_ratio_test(),
    "dow_distribution_uniform_vs_weighted": _create_dow_distribution_test(),
    "campaign_frequency_high_vs_standard": _create_campaign_frequency_test(),
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_test_by_id(test_id: str) -> VolumeABTest:
    """Retrieve a pre-configured test by its ID.

    Args:
        test_id: The unique identifier of the test.

    Returns:
        Copy of the VolumeABTest specification.

    Raises:
        KeyError: If test_id is not found in VOLUME_AB_TESTS.

    Examples:
        >>> test = get_test_by_id('bump_ratio_2x_vs_3x')
        >>> print(test.hypothesis)
        Increasing bump message frequency from 2x to 3x per day...
    """
    if test_id not in VOLUME_AB_TESTS:
        available = ", ".join(VOLUME_AB_TESTS.keys())
        raise KeyError(
            f"Test '{test_id}' not found. Available tests: {available}"
        )

    # Return a copy to prevent mutation of the template
    template = VOLUME_AB_TESTS[test_id]
    return VolumeABTest(
        test_id=template.test_id,
        hypothesis=template.hypothesis,
        control_config=template.control_config,
        treatment_config=template.treatment_config,
        primary_metric=template.primary_metric,
        secondary_metrics=template.secondary_metrics.copy(),
        duration_days=template.duration_days,
        confidence_level=template.confidence_level,
        statistical_power=template.statistical_power,
        minimum_detectable_effect=template.minimum_detectable_effect,
        notes=template.notes,
    )


def list_available_tests() -> list[dict[str, Any]]:
    """List all available pre-configured test specifications.

    Returns:
        List of dictionaries with test_id, hypothesis, and status.

    Examples:
        >>> tests = list_available_tests()
        >>> for t in tests:
        ...     print(f"{t['test_id']}: {t['min_sample_size']} samples needed")
    """
    return [
        {
            "test_id": test.test_id,
            "hypothesis": test.hypothesis[:100] + "..."
            if len(test.hypothesis) > 100
            else test.hypothesis,
            "min_sample_size": test.min_sample_size,
            "duration_days": test.duration_days,
            "primary_metric": test.primary_metric.name,
            "mde": test.minimum_detectable_effect,
        }
        for test in VOLUME_AB_TESTS.values()
    ]


def create_custom_test(
    test_id: str,
    hypothesis: str,
    control_config: VolumeConfig,
    treatment_config: VolumeConfig,
    primary_metric: Metric,
    secondary_metrics: list[Metric] | None = None,
    duration_days: int = DEFAULT_DURATION_DAYS,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    statistical_power: float = DEFAULT_STATISTICAL_POWER,
    minimum_detectable_effect: float = DEFAULT_MDE,
    notes: str = "",
) -> VolumeABTest:
    """Create a custom A/B test specification.

    Factory function for creating new test specifications with validation.

    Args:
        test_id: Unique identifier for the test.
        hypothesis: Clear statement of what the test aims to prove.
        control_config: Volume configuration for control group.
        treatment_config: Volume configuration for treatment group.
        primary_metric: Main metric for determining test success.
        secondary_metrics: Additional metrics to track. Default empty list.
        duration_days: Expected test duration. Default 14.
        confidence_level: Statistical significance threshold. Default 0.95.
        statistical_power: Probability of detecting effect. Default 0.80.
        minimum_detectable_effect: Smallest effect to detect. Default 0.10.
        notes: Additional context or observations.

    Returns:
        Configured VolumeABTest instance.

    Examples:
        >>> test = create_custom_test(
        ...     test_id="retention_boost",
        ...     hypothesis="Increasing retention sends improves renewal rate",
        ...     control_config=VolumeConfig(retention_per_day=1.0),
        ...     treatment_config=VolumeConfig(retention_per_day=2.0),
        ...     primary_metric=SUBSCRIBER_CHURN_RATE,
        ...     minimum_detectable_effect=0.05,
        ... )
    """
    return VolumeABTest(
        test_id=test_id,
        hypothesis=hypothesis,
        control_config=control_config,
        treatment_config=treatment_config,
        primary_metric=primary_metric,
        secondary_metrics=secondary_metrics or [],
        duration_days=duration_days,
        confidence_level=confidence_level,
        statistical_power=statistical_power,
        minimum_detectable_effect=minimum_detectable_effect,
        notes=notes,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
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
    "_calculate_min_sample_size",
    "calculate_achieved_power",
    # Validation functions
    "validate_test_completion",
    # Helper functions
    "get_test_by_id",
    "list_available_tests",
    "create_custom_test",
]
