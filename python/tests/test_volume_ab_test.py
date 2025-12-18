"""
Tests for Volume A/B Testing Framework.

Comprehensive test coverage for the volume_ab_test module including:
- Power analysis calculations
- Sample size validation
- Test lifecycle management
- Pre-configured test specifications
"""

from datetime import date

import pytest

from python.analytics.volume_ab_test import (
    DEFAULT_CONFIDENCE_LEVEL,
    DEFAULT_DURATION_DAYS,
    DEFAULT_MDE,
    DEFAULT_SIGMA,
    DEFAULT_STATISTICAL_POWER,
    MESSAGE_OPEN_RATE,
    PPV_UNLOCK_RATE,
    REVENUE_PER_SUBSCRIBER,
    SUBSCRIBER_CHURN_RATE,
    TIP_RATE,
    VOLUME_AB_TESTS,
    Metric,
    MetricType,
    TestStatus,
    VolumeABTest,
    VolumeConfig,
    _calculate_min_sample_size,
    calculate_achieved_power,
    create_custom_test,
    get_test_by_id,
    list_available_tests,
    validate_test_completion,
)

# =============================================================================
# VolumeConfig Tests
# =============================================================================


class TestVolumeConfig:
    """Tests for VolumeConfig dataclass."""

    def test_default_values(self) -> None:
        """Test VolumeConfig default values."""
        config = VolumeConfig()
        assert config.ppv_per_day == 3.0
        assert config.bump_per_day == 2.0
        assert config.retention_per_day == 1.0
        assert config.engagement_per_day == 2.0
        assert config.description == ""

    def test_custom_values(self) -> None:
        """Test VolumeConfig with custom values."""
        config = VolumeConfig(
            ppv_per_day=5.0,
            bump_per_day=4.0,
            retention_per_day=2.0,
            engagement_per_day=3.0,
            description="High volume test",
        )
        assert config.ppv_per_day == 5.0
        assert config.bump_per_day == 4.0
        assert config.retention_per_day == 2.0
        assert config.engagement_per_day == 3.0
        assert config.description == "High volume test"

    def test_to_dict(self) -> None:
        """Test VolumeConfig serialization."""
        config = VolumeConfig(ppv_per_day=4.0, description="Test config")
        result = config.to_dict()
        assert result["ppv_per_day"] == 4.0
        assert result["bump_per_day"] == 2.0
        assert result["description"] == "Test config"

    def test_frozen(self) -> None:
        """Test that VolumeConfig is immutable."""
        config = VolumeConfig()
        with pytest.raises(AttributeError):
            config.ppv_per_day = 10.0  # type: ignore


# =============================================================================
# Metric Tests
# =============================================================================


class TestMetric:
    """Tests for Metric dataclass."""

    def test_default_values(self) -> None:
        """Test Metric default values."""
        metric = Metric(name="test_metric", metric_type=MetricType.REVENUE)
        assert metric.name == "test_metric"
        assert metric.metric_type == MetricType.REVENUE
        assert metric.description == ""
        assert metric.unit == ""
        assert metric.higher_is_better is True

    def test_custom_values(self) -> None:
        """Test Metric with custom values."""
        metric = Metric(
            name="churn_rate",
            metric_type=MetricType.RETENTION,
            description="Monthly subscriber churn",
            unit="percent",
            higher_is_better=False,
        )
        assert metric.name == "churn_rate"
        assert metric.metric_type == MetricType.RETENTION
        assert metric.description == "Monthly subscriber churn"
        assert metric.unit == "percent"
        assert metric.higher_is_better is False


# =============================================================================
# Power Analysis Tests
# =============================================================================


class TestPowerAnalysis:
    """Tests for statistical power analysis functions."""

    def test_sample_size_calculation_standard(self) -> None:
        """Test sample size calculation with standard parameters."""
        n = _calculate_min_sample_size(alpha=0.05, power=0.80, mde=0.10, sigma=1.0)
        # Expected: ~1570 based on formula n = 2 * ((z_alpha + z_beta) / d)^2
        assert n == 1570

    def test_sample_size_calculation_high_power(self) -> None:
        """Test sample size with higher power requirement."""
        n_standard = _calculate_min_sample_size(alpha=0.05, power=0.80, mde=0.10)
        n_high = _calculate_min_sample_size(alpha=0.05, power=0.90, mde=0.10)
        # Higher power requires larger sample
        assert n_high > n_standard

    def test_sample_size_calculation_stricter_alpha(self) -> None:
        """Test sample size with stricter alpha."""
        n_standard = _calculate_min_sample_size(alpha=0.05, power=0.80, mde=0.10)
        n_strict = _calculate_min_sample_size(alpha=0.01, power=0.80, mde=0.10)
        # Stricter alpha requires larger sample
        assert n_strict > n_standard

    def test_sample_size_calculation_larger_effect(self) -> None:
        """Test sample size with larger expected effect."""
        n_small_effect = _calculate_min_sample_size(alpha=0.05, power=0.80, mde=0.10)
        n_large_effect = _calculate_min_sample_size(alpha=0.05, power=0.80, mde=0.20)
        # Larger effect requires smaller sample
        assert n_large_effect < n_small_effect

    def test_sample_size_invalid_alpha(self) -> None:
        """Test that invalid alpha raises ValueError."""
        with pytest.raises(ValueError, match="alpha must be between"):
            _calculate_min_sample_size(alpha=0.0, power=0.80, mde=0.10)
        with pytest.raises(ValueError, match="alpha must be between"):
            _calculate_min_sample_size(alpha=1.0, power=0.80, mde=0.10)

    def test_sample_size_invalid_power(self) -> None:
        """Test that invalid power raises ValueError."""
        with pytest.raises(ValueError, match="power must be between"):
            _calculate_min_sample_size(alpha=0.05, power=0.0, mde=0.10)
        with pytest.raises(ValueError, match="power must be between"):
            _calculate_min_sample_size(alpha=0.05, power=1.0, mde=0.10)

    def test_sample_size_invalid_mde(self) -> None:
        """Test that invalid MDE raises ValueError."""
        with pytest.raises(ValueError, match="mde must be positive"):
            _calculate_min_sample_size(alpha=0.05, power=0.80, mde=0.0)
        with pytest.raises(ValueError, match="mde must be positive"):
            _calculate_min_sample_size(alpha=0.05, power=0.80, mde=-0.10)

    def test_achieved_power_standard(self) -> None:
        """Test achieved power calculation."""
        power = calculate_achieved_power(
            control_n=1570, treatment_n=1570, alpha=0.05, mde=0.10
        )
        # Should be approximately 0.80 (the target power)
        assert 0.78 <= power <= 0.82

    def test_achieved_power_small_sample(self) -> None:
        """Test achieved power with small samples."""
        power = calculate_achieved_power(
            control_n=100, treatment_n=100, alpha=0.05, mde=0.10
        )
        # Small sample should have low power
        assert power < 0.50

    def test_achieved_power_unequal_samples(self) -> None:
        """Test achieved power with unequal sample sizes."""
        power_equal = calculate_achieved_power(control_n=500, treatment_n=500)
        power_unequal = calculate_achieved_power(control_n=300, treatment_n=700)
        # Unequal samples should have lower power (harmonic mean effect)
        assert power_unequal < power_equal

    def test_achieved_power_invalid_samples(self) -> None:
        """Test that invalid sample sizes raise ValueError."""
        with pytest.raises(ValueError, match="Sample sizes must be positive"):
            calculate_achieved_power(control_n=0, treatment_n=100)
        with pytest.raises(ValueError, match="Sample sizes must be positive"):
            calculate_achieved_power(control_n=-10, treatment_n=100)


# =============================================================================
# VolumeABTest Tests
# =============================================================================


class TestVolumeABTest:
    """Tests for VolumeABTest dataclass."""

    @pytest.fixture
    def basic_test(self) -> VolumeABTest:
        """Create a basic test fixture."""
        return VolumeABTest(
            test_id="test_001",
            hypothesis="Test hypothesis",
            control_config=VolumeConfig(bump_per_day=2.0),
            treatment_config=VolumeConfig(bump_per_day=3.0),
            primary_metric=REVENUE_PER_SUBSCRIBER,
        )

    def test_initialization_defaults(self, basic_test: VolumeABTest) -> None:
        """Test VolumeABTest initialization with defaults."""
        assert basic_test.test_id == "test_001"
        assert basic_test.hypothesis == "Test hypothesis"
        assert basic_test.duration_days == DEFAULT_DURATION_DAYS
        assert basic_test.confidence_level == DEFAULT_CONFIDENCE_LEVEL
        assert basic_test.statistical_power == DEFAULT_STATISTICAL_POWER
        assert basic_test.minimum_detectable_effect == DEFAULT_MDE
        assert basic_test.status == TestStatus.DRAFT
        assert basic_test.start_date is None
        assert basic_test.end_date is None

    def test_sample_size_auto_calculation(self, basic_test: VolumeABTest) -> None:
        """Test that min_sample_size is automatically calculated."""
        # Should match _calculate_min_sample_size output
        expected_n = _calculate_min_sample_size(
            alpha=1.0 - basic_test.confidence_level,
            power=basic_test.statistical_power,
            mde=basic_test.minimum_detectable_effect,
            sigma=DEFAULT_SIGMA,
        )
        assert basic_test.min_sample_size == expected_n

    def test_sample_size_varies_with_mde(self) -> None:
        """Test that sample size changes with different MDE."""
        test_small_mde = VolumeABTest(
            test_id="small_mde",
            hypothesis="Test",
            control_config=VolumeConfig(),
            treatment_config=VolumeConfig(),
            primary_metric=REVENUE_PER_SUBSCRIBER,
            minimum_detectable_effect=0.05,
        )
        test_large_mde = VolumeABTest(
            test_id="large_mde",
            hypothesis="Test",
            control_config=VolumeConfig(),
            treatment_config=VolumeConfig(),
            primary_metric=REVENUE_PER_SUBSCRIBER,
            minimum_detectable_effect=0.20,
        )
        # Smaller MDE requires larger sample
        assert test_small_mde.min_sample_size > test_large_mde.min_sample_size

    def test_invalid_confidence_level(self) -> None:
        """Test that invalid confidence level raises ValueError."""
        with pytest.raises(ValueError, match="confidence_level must be between"):
            VolumeABTest(
                test_id="test",
                hypothesis="Test",
                control_config=VolumeConfig(),
                treatment_config=VolumeConfig(),
                primary_metric=REVENUE_PER_SUBSCRIBER,
                confidence_level=1.0,
            )

    def test_invalid_statistical_power(self) -> None:
        """Test that invalid power raises ValueError."""
        with pytest.raises(ValueError, match="statistical_power must be between"):
            VolumeABTest(
                test_id="test",
                hypothesis="Test",
                control_config=VolumeConfig(),
                treatment_config=VolumeConfig(),
                primary_metric=REVENUE_PER_SUBSCRIBER,
                statistical_power=0.0,
            )

    def test_invalid_mde(self) -> None:
        """Test that invalid MDE raises ValueError."""
        with pytest.raises(ValueError, match="minimum_detectable_effect must be"):
            VolumeABTest(
                test_id="test",
                hypothesis="Test",
                control_config=VolumeConfig(),
                treatment_config=VolumeConfig(),
                primary_metric=REVENUE_PER_SUBSCRIBER,
                minimum_detectable_effect=-0.10,
            )

    def test_invalid_duration(self) -> None:
        """Test that invalid duration raises ValueError."""
        with pytest.raises(ValueError, match="duration_days must be positive"):
            VolumeABTest(
                test_id="test",
                hypothesis="Test",
                control_config=VolumeConfig(),
                treatment_config=VolumeConfig(),
                primary_metric=REVENUE_PER_SUBSCRIBER,
                duration_days=0,
            )

    def test_to_dict(self, basic_test: VolumeABTest) -> None:
        """Test serialization to dictionary."""
        result = basic_test.to_dict()
        assert result["test_id"] == "test_001"
        assert result["hypothesis"] == "Test hypothesis"
        assert "control_config" in result
        assert "treatment_config" in result
        assert "primary_metric" in result
        assert result["min_sample_size"] == basic_test.min_sample_size
        assert result["status"] == "draft"


# =============================================================================
# Test Lifecycle Tests
# =============================================================================


class TestTestLifecycle:
    """Tests for VolumeABTest lifecycle management."""

    @pytest.fixture
    def draft_test(self) -> VolumeABTest:
        """Create a draft test fixture."""
        return VolumeABTest(
            test_id="lifecycle_test",
            hypothesis="Test lifecycle",
            control_config=VolumeConfig(),
            treatment_config=VolumeConfig(),
            primary_metric=REVENUE_PER_SUBSCRIBER,
        )

    def test_start_from_draft(self, draft_test: VolumeABTest) -> None:
        """Test starting a test from draft status."""
        assert draft_test.status == TestStatus.DRAFT
        draft_test.start()
        assert draft_test.status == TestStatus.RUNNING
        assert draft_test.start_date == date.today()

    def test_start_with_custom_date(self, draft_test: VolumeABTest) -> None:
        """Test starting a test with a specific date."""
        start = date(2025, 1, 15)
        draft_test.start(start_date=start)
        assert draft_test.start_date == start

    def test_start_from_paused(self, draft_test: VolumeABTest) -> None:
        """Test restarting a paused test."""
        draft_test.start()
        draft_test.pause()
        assert draft_test.status == TestStatus.PAUSED
        draft_test.start()
        assert draft_test.status == TestStatus.RUNNING

    def test_start_from_running_raises(self, draft_test: VolumeABTest) -> None:
        """Test that starting a running test raises error."""
        draft_test.start()
        with pytest.raises(ValueError, match="Cannot start test in running status"):
            draft_test.start()

    def test_start_from_completed_raises(self, draft_test: VolumeABTest) -> None:
        """Test that starting a completed test raises error."""
        draft_test.start()
        draft_test.complete()
        with pytest.raises(ValueError, match="Cannot start test in completed status"):
            draft_test.start()

    def test_pause_running(self, draft_test: VolumeABTest) -> None:
        """Test pausing a running test."""
        draft_test.start()
        draft_test.pause()
        assert draft_test.status == TestStatus.PAUSED

    def test_pause_from_draft_raises(self, draft_test: VolumeABTest) -> None:
        """Test that pausing a draft test raises error."""
        with pytest.raises(ValueError, match="Cannot pause test in draft status"):
            draft_test.pause()

    def test_complete_running(self, draft_test: VolumeABTest) -> None:
        """Test completing a running test."""
        draft_test.start()
        draft_test.complete()
        assert draft_test.status == TestStatus.COMPLETED
        assert draft_test.end_date == date.today()

    def test_complete_with_custom_date(self, draft_test: VolumeABTest) -> None:
        """Test completing with a specific end date."""
        draft_test.start()
        end = date(2025, 1, 30)
        draft_test.complete(end_date=end)
        assert draft_test.end_date == end

    def test_complete_from_draft_raises(self, draft_test: VolumeABTest) -> None:
        """Test that completing a draft test raises error."""
        with pytest.raises(ValueError, match="Cannot complete test in draft status"):
            draft_test.complete()

    def test_cancel_draft(self, draft_test: VolumeABTest) -> None:
        """Test cancelling a draft test."""
        draft_test.cancel(reason="No longer needed")
        assert draft_test.status == TestStatus.CANCELLED
        assert "No longer needed" in draft_test.notes

    def test_cancel_running(self, draft_test: VolumeABTest) -> None:
        """Test cancelling a running test."""
        draft_test.start()
        draft_test.cancel(reason="Early termination")
        assert draft_test.status == TestStatus.CANCELLED

    def test_cancel_completed_raises(self, draft_test: VolumeABTest) -> None:
        """Test that cancelling a completed test raises error."""
        draft_test.start()
        draft_test.complete()
        with pytest.raises(ValueError, match="Cannot cancel a completed test"):
            draft_test.cancel()


# =============================================================================
# Test Validation Tests
# =============================================================================


class TestValidation:
    """Tests for test completion validation."""

    @pytest.fixture
    def test_spec(self) -> VolumeABTest:
        """Create a test specification fixture."""
        return VolumeABTest(
            test_id="validation_test",
            hypothesis="Test validation",
            control_config=VolumeConfig(),
            treatment_config=VolumeConfig(),
            primary_metric=REVENUE_PER_SUBSCRIBER,
            minimum_detectable_effect=0.20,  # 393 samples per arm
        )

    def test_validation_incomplete(self, test_spec: VolumeABTest) -> None:
        """Test validation with insufficient samples."""
        result = validate_test_completion(test_spec, control_n=100, treatment_n=100)
        assert result["is_complete"] is False
        assert result["control_progress"] < 1.0
        assert result["treatment_progress"] < 1.0
        assert result["samples_needed_control"] > 0

    def test_validation_complete(self, test_spec: VolumeABTest) -> None:
        """Test validation with sufficient samples."""
        min_n = test_spec.min_sample_size
        result = validate_test_completion(test_spec, control_n=min_n, treatment_n=min_n)
        assert result["is_complete"] is True
        assert result["control_progress"] >= 1.0
        assert result["treatment_progress"] >= 1.0
        assert result["samples_needed_control"] == 0
        assert result["samples_needed_treatment"] == 0

    def test_validation_power_calculation(self, test_spec: VolumeABTest) -> None:
        """Test that achieved power is calculated correctly."""
        min_n = test_spec.min_sample_size
        result = validate_test_completion(test_spec, control_n=min_n, treatment_n=min_n)
        # Achieved power should be close to target
        assert result["actual_power"] >= 0.78

    def test_validation_unequal_samples(self, test_spec: VolumeABTest) -> None:
        """Test validation with unequal sample sizes."""
        min_n = test_spec.min_sample_size
        result = validate_test_completion(
            test_spec, control_n=min_n, treatment_n=min_n // 2
        )
        assert result["is_complete"] is False
        assert result["control_progress"] >= 1.0
        assert result["treatment_progress"] < 1.0
        # Overall progress is minimum of both
        assert result["overall_progress"] == result["treatment_progress"]

    def test_validation_recommendation_complete(self, test_spec: VolumeABTest) -> None:
        """Test recommendation for complete test."""
        min_n = test_spec.min_sample_size
        result = validate_test_completion(
            test_spec, control_n=min_n + 50, treatment_n=min_n + 50
        )
        assert "Ready for statistical analysis" in result["recommendation"]

    def test_validation_recommendation_in_progress(
        self, test_spec: VolumeABTest
    ) -> None:
        """Test recommendation for in-progress test."""
        min_n = test_spec.min_sample_size
        result = validate_test_completion(
            test_spec, control_n=int(min_n * 0.5), treatment_n=int(min_n * 0.5)
        )
        assert "complete" in result["recommendation"].lower()
        assert "Continue" in result["recommendation"] or "samples needed" in result["recommendation"]

    def test_validation_negative_samples_raises(
        self, test_spec: VolumeABTest
    ) -> None:
        """Test that negative sample counts raise ValueError."""
        with pytest.raises(ValueError, match="Sample counts cannot be negative"):
            validate_test_completion(test_spec, control_n=-10, treatment_n=100)


# =============================================================================
# Pre-configured Tests
# =============================================================================


class TestPreConfiguredTests:
    """Tests for pre-configured test specifications."""

    def test_volume_ab_tests_not_empty(self) -> None:
        """Test that VOLUME_AB_TESTS contains tests."""
        assert len(VOLUME_AB_TESTS) >= 3

    def test_bump_ratio_test_exists(self) -> None:
        """Test bump ratio test is available."""
        assert "bump_ratio_2x_vs_3x" in VOLUME_AB_TESTS

    def test_dow_distribution_test_exists(self) -> None:
        """Test DOW distribution test is available."""
        assert "dow_distribution_uniform_vs_weighted" in VOLUME_AB_TESTS

    def test_campaign_frequency_test_exists(self) -> None:
        """Test campaign frequency test is available."""
        assert "campaign_frequency_high_vs_standard" in VOLUME_AB_TESTS

    def test_get_test_by_id_valid(self) -> None:
        """Test retrieving a valid test by ID."""
        test = get_test_by_id("bump_ratio_2x_vs_3x")
        assert test.test_id == "bump_ratio_2x_vs_3x"
        assert test.status == TestStatus.DRAFT

    def test_get_test_by_id_returns_copy(self) -> None:
        """Test that get_test_by_id returns a copy."""
        test1 = get_test_by_id("bump_ratio_2x_vs_3x")
        test2 = get_test_by_id("bump_ratio_2x_vs_3x")
        # Should be different objects
        assert test1 is not test2
        # But with same content
        assert test1.test_id == test2.test_id

    def test_get_test_by_id_invalid_raises(self) -> None:
        """Test that invalid test ID raises KeyError."""
        with pytest.raises(KeyError, match="Test 'nonexistent' not found"):
            get_test_by_id("nonexistent")

    def test_list_available_tests(self) -> None:
        """Test listing available tests."""
        tests = list_available_tests()
        assert len(tests) >= 3
        test_ids = [t["test_id"] for t in tests]
        assert "bump_ratio_2x_vs_3x" in test_ids

    def test_list_available_tests_format(self) -> None:
        """Test that list contains expected keys."""
        tests = list_available_tests()
        for test in tests:
            assert "test_id" in test
            assert "hypothesis" in test
            assert "min_sample_size" in test
            assert "duration_days" in test
            assert "primary_metric" in test
            assert "mde" in test


# =============================================================================
# Custom Test Creation Tests
# =============================================================================


class TestCustomTestCreation:
    """Tests for custom test creation."""

    def test_create_custom_test_basic(self) -> None:
        """Test creating a basic custom test."""
        test = create_custom_test(
            test_id="custom_test_001",
            hypothesis="Custom hypothesis",
            control_config=VolumeConfig(ppv_per_day=2.0),
            treatment_config=VolumeConfig(ppv_per_day=4.0),
            primary_metric=REVENUE_PER_SUBSCRIBER,
        )
        assert test.test_id == "custom_test_001"
        assert test.hypothesis == "Custom hypothesis"
        assert test.status == TestStatus.DRAFT

    def test_create_custom_test_with_all_params(self) -> None:
        """Test creating a custom test with all parameters."""
        test = create_custom_test(
            test_id="custom_full",
            hypothesis="Full custom test",
            control_config=VolumeConfig(ppv_per_day=2.0),
            treatment_config=VolumeConfig(ppv_per_day=4.0),
            primary_metric=REVENUE_PER_SUBSCRIBER,
            secondary_metrics=[PPV_UNLOCK_RATE, SUBSCRIBER_CHURN_RATE],
            duration_days=21,
            confidence_level=0.99,
            statistical_power=0.90,
            minimum_detectable_effect=0.15,
            notes="Full test notes",
        )
        assert test.duration_days == 21
        assert test.confidence_level == 0.99
        assert test.statistical_power == 0.90
        assert len(test.secondary_metrics) == 2
        assert test.notes == "Full test notes"


# =============================================================================
# Common Metrics Tests
# =============================================================================


class TestCommonMetrics:
    """Tests for pre-defined common metrics."""

    def test_revenue_per_subscriber(self) -> None:
        """Test REVENUE_PER_SUBSCRIBER metric."""
        assert REVENUE_PER_SUBSCRIBER.name == "revenue_per_subscriber"
        assert REVENUE_PER_SUBSCRIBER.metric_type == MetricType.REVENUE
        assert REVENUE_PER_SUBSCRIBER.higher_is_better is True

    def test_ppv_unlock_rate(self) -> None:
        """Test PPV_UNLOCK_RATE metric."""
        assert PPV_UNLOCK_RATE.name == "ppv_unlock_rate"
        assert PPV_UNLOCK_RATE.metric_type == MetricType.CONVERSION
        assert PPV_UNLOCK_RATE.higher_is_better is True

    def test_subscriber_churn_rate(self) -> None:
        """Test SUBSCRIBER_CHURN_RATE metric."""
        assert SUBSCRIBER_CHURN_RATE.name == "subscriber_churn_rate"
        assert SUBSCRIBER_CHURN_RATE.metric_type == MetricType.RETENTION
        assert SUBSCRIBER_CHURN_RATE.higher_is_better is False  # Lower churn is better

    def test_message_open_rate(self) -> None:
        """Test MESSAGE_OPEN_RATE metric."""
        assert MESSAGE_OPEN_RATE.name == "message_open_rate"
        assert MESSAGE_OPEN_RATE.metric_type == MetricType.ENGAGEMENT

    def test_tip_rate(self) -> None:
        """Test TIP_RATE metric."""
        assert TIP_RATE.name == "tip_rate"
        assert TIP_RATE.metric_type == MetricType.CONVERSION


# =============================================================================
# Enums Tests
# =============================================================================


class TestEnums:
    """Tests for enums."""

    def test_test_status_values(self) -> None:
        """Test TestStatus enum values."""
        assert TestStatus.DRAFT.value == "draft"
        assert TestStatus.RUNNING.value == "running"
        assert TestStatus.PAUSED.value == "paused"
        assert TestStatus.COMPLETED.value == "completed"
        assert TestStatus.CANCELLED.value == "cancelled"

    def test_metric_type_values(self) -> None:
        """Test MetricType enum values."""
        assert MetricType.REVENUE.value == "revenue"
        assert MetricType.CONVERSION.value == "conversion"
        assert MetricType.ENGAGEMENT.value == "engagement"
        assert MetricType.RETENTION.value == "retention"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the A/B testing framework."""

    def test_full_test_workflow(self) -> None:
        """Test complete workflow from creation to completion."""
        # 1. Get pre-configured test
        test = get_test_by_id("bump_ratio_2x_vs_3x")
        assert test.status == TestStatus.DRAFT

        # 2. Start the test
        test.start(start_date=date(2025, 1, 1))
        assert test.status == TestStatus.RUNNING
        assert test.start_date == date(2025, 1, 1)

        # 3. Validate mid-test (insufficient samples)
        min_n = test.min_sample_size
        partial_n = min_n // 2
        result = validate_test_completion(test, control_n=partial_n, treatment_n=partial_n)
        assert result["is_complete"] is False
        assert result["overall_progress"] < 1.0

        # 4. Validate with sufficient samples
        result = validate_test_completion(test, control_n=min_n, treatment_n=min_n)
        assert result["is_complete"] is True

        # 5. Complete the test
        test.complete(end_date=date(2025, 1, 15))
        assert test.status == TestStatus.COMPLETED
        assert test.end_date == date(2025, 1, 15)

    def test_pause_resume_workflow(self) -> None:
        """Test pausing and resuming a test."""
        test = get_test_by_id("campaign_frequency_high_vs_standard")

        # Start
        test.start()
        assert test.status == TestStatus.RUNNING

        # Pause
        test.pause()
        assert test.status == TestStatus.PAUSED

        # Resume
        test.start()
        assert test.status == TestStatus.RUNNING

        # Complete
        test.complete()
        assert test.status == TestStatus.COMPLETED

    def test_cancellation_workflow(self) -> None:
        """Test cancelling a test mid-experiment."""
        test = get_test_by_id("dow_distribution_uniform_vs_weighted")

        test.start()
        test.cancel(reason="Budget constraints")

        assert test.status == TestStatus.CANCELLED
        assert "Budget constraints" in test.notes
