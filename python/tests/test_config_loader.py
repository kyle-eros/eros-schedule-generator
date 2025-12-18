"""
Unit tests for algorithm configuration loader.

Tests cover:
- Configuration loading from YAML
- Validation of required sections
- Dataclass property access
- Error handling for missing/invalid config
- Singleton pattern and reload functionality
- Smooth interpolation configuration
- New creator configuration
"""

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.exceptions import ConfigurationError
from python.volume.config_loader import (
    AlgorithmConfig,
    InterpolationBreakpoint,
    MultiplierConfig,
    NewCreatorConfig,
    RoundingConfig,
    SmoothInterpolationConfig,
    ThresholdConfig,
    TierBounds,
    TrendConfig,
    clear_config,
    get_config,
    reload_config,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_config_dict() -> Dict[str, Any]:
    """Return a valid configuration dictionary."""
    return {
        "volume": {
            "fan_thresholds": {
                "LOW": {"min": 0, "max": 999},
                "MID": {"min": 1000, "max": 4999},
                "HIGH": {"min": 5000, "max": 14999},
                "ULTRA": {"min": 15000, "max": None},
            },
            "tier_configs": {
                "LOW": {
                    "paid": {"revenue": 3, "engagement": 3, "retention": 1},
                    "free": {"revenue": 4, "engagement": 3, "retention": 1},
                },
                "MID": {
                    "paid": {"revenue": 4, "engagement": 3, "retention": 2},
                    "free": {"revenue": 5, "engagement": 3, "retention": 1},
                },
                "HIGH": {
                    "paid": {"revenue": 5, "engagement": 4, "retention": 2},
                    "free": {"revenue": 6, "engagement": 4, "retention": 2},
                },
                "ULTRA": {
                    "paid": {"revenue": 6, "engagement": 5, "retention": 3},
                    "free": {"revenue": 8, "engagement": 5, "retention": 2},
                },
            },
            "bounds": {
                "revenue": {"min": 1, "max": 8},
                "engagement": {"min": 1, "max": 6},
                "retention": {"min": 0, "max": 4},
            },
        },
        "performance": {
            "saturation": {"low": 30, "medium": 50, "high": 70},
            "opportunity": {"low": 30, "medium": 50, "high": 70},
        },
        "multipliers": {
            "saturation": {"high": 0.7, "medium": 0.9, "normal": 1.0},
            "opportunity": {"high": 1.2, "medium": 1.1, "normal": 1.0},
            "smooth_interpolation": {
                "enabled": True,
                "saturation_breakpoints": [
                    {"score": 0, "multiplier": 1.0},
                    {"score": 30, "multiplier": 1.0},
                    {"score": 50, "multiplier": 0.9},
                    {"score": 70, "multiplier": 0.7},
                    {"score": 100, "multiplier": 0.7},
                ],
                "opportunity_breakpoints": [
                    {"score": 0, "multiplier": 1.0},
                    {"score": 30, "multiplier": 1.0},
                    {"score": 50, "multiplier": 1.1},
                    {"score": 70, "multiplier": 1.2},
                    {"score": 100, "multiplier": 1.2},
                ],
            },
        },
        "trends": {
            "revenue_threshold_negative": -15,
            "revenue_threshold_positive": 15,
        },
        "new_creator": {
            "min_messages_for_analysis": 5,
            "days_to_consider_new": 30,
            "default_saturation": 40.0,
            "default_opportunity": 60.0,
        },
        "rounding": {
            "use_decimal": True,
            "method": "ROUND_HALF_UP",
            "precision": 4,
        },
    }


@pytest.fixture
def temp_config_file(valid_config_dict: Dict[str, Any]) -> str:
    """Create a temporary config file and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(valid_config_dict, f)
        return f.name


@pytest.fixture(autouse=True)
def reset_config():
    """Reset the global config singleton before and after each test."""
    clear_config()
    yield
    clear_config()


# =============================================================================
# Test Classes
# =============================================================================


class TestAlgorithmConfigLoading:
    """Tests for AlgorithmConfig initialization and loading."""

    def test_load_default_config(self) -> None:
        """Default config should load without errors."""
        config = get_config()
        assert config is not None
        assert config.config_path.endswith("algorithm_config.yaml")

    def test_load_custom_config(self, temp_config_file: str) -> None:
        """Custom config file should load correctly."""
        config = AlgorithmConfig(temp_config_file)
        assert config.config_path == temp_config_file

    def test_missing_config_raises_error(self) -> None:
        """Missing config file should raise ConfigurationError."""
        with pytest.raises(ConfigurationError, match="not found"):
            AlgorithmConfig("/nonexistent/path/config.yaml")

    def test_invalid_yaml_raises_error(self) -> None:
        """Invalid YAML should raise ConfigurationError."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            with pytest.raises(ConfigurationError, match="Invalid YAML"):
                AlgorithmConfig(f.name)

    def test_missing_section_raises_error(
        self, valid_config_dict: Dict[str, Any]
    ) -> None:
        """Missing required section should raise ConfigurationError."""
        del valid_config_dict["volume"]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(valid_config_dict, f)
            f.flush()
            with pytest.raises(ConfigurationError, match="Missing required"):
                AlgorithmConfig(f.name)


class TestSingletonPattern:
    """Tests for singleton pattern and config management."""

    def test_get_config_returns_same_instance(self) -> None:
        """get_config should return the same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config_creates_new_instance(self) -> None:
        """reload_config should create a new instance."""
        config1 = get_config()
        config2 = reload_config()
        assert config1 is not config2

    def test_clear_config_allows_fresh_load(self) -> None:
        """clear_config should allow fresh config loading."""
        config1 = get_config()
        clear_config()
        config2 = get_config()
        # Different instances but same content
        assert config1 is not config2


class TestFanThresholds:
    """Tests for fan threshold configuration."""

    def test_fan_thresholds_structure(self, temp_config_file: str) -> None:
        """Fan thresholds should have correct structure."""
        config = AlgorithmConfig(temp_config_file)
        thresholds = config.fan_thresholds

        assert "LOW" in thresholds
        assert "MID" in thresholds
        assert "HIGH" in thresholds
        assert "ULTRA" in thresholds

    def test_fan_thresholds_values(self, temp_config_file: str) -> None:
        """Fan thresholds should have correct values."""
        config = AlgorithmConfig(temp_config_file)
        thresholds = config.fan_thresholds

        assert thresholds["LOW"] == (0, 999)
        assert thresholds["MID"] == (1000, 4999)
        assert thresholds["HIGH"] == (5000, 14999)
        assert thresholds["ULTRA"] == (15000, None)


class TestTierConfigs:
    """Tests for tier configuration."""

    def test_tier_configs_structure(self, temp_config_file: str) -> None:
        """Tier configs should have correct nested structure."""
        config = AlgorithmConfig(temp_config_file)
        tier_configs = config.tier_configs

        for tier in ["LOW", "MID", "HIGH", "ULTRA"]:
            assert tier in tier_configs
            assert "paid" in tier_configs[tier]
            assert "free" in tier_configs[tier]
            for page_type in ["paid", "free"]:
                assert "revenue" in tier_configs[tier][page_type]
                assert "engagement" in tier_configs[tier][page_type]
                assert "retention" in tier_configs[tier][page_type]

    def test_tier_configs_values(self, temp_config_file: str) -> None:
        """Tier config values should be correct."""
        config = AlgorithmConfig(temp_config_file)
        tier_configs = config.tier_configs

        # Check HIGH tier paid values
        assert tier_configs["HIGH"]["paid"]["revenue"] == 5
        assert tier_configs["HIGH"]["paid"]["engagement"] == 4
        assert tier_configs["HIGH"]["paid"]["retention"] == 2


class TestBounds:
    """Tests for volume bounds configuration."""

    def test_bounds_structure(self, temp_config_file: str) -> None:
        """Bounds should have TierBounds instances."""
        config = AlgorithmConfig(temp_config_file)
        bounds = config.bounds

        assert "revenue" in bounds
        assert "engagement" in bounds
        assert "retention" in bounds
        assert isinstance(bounds["revenue"], TierBounds)

    def test_bounds_values(self, temp_config_file: str) -> None:
        """Bounds should have correct min/max values."""
        config = AlgorithmConfig(temp_config_file)
        bounds = config.bounds

        assert bounds["revenue"].min_value == 1
        assert bounds["revenue"].max_value == 8
        assert bounds["engagement"].min_value == 1
        assert bounds["engagement"].max_value == 6
        assert bounds["retention"].min_value == 0
        assert bounds["retention"].max_value == 4

    def test_bounds_clamp(self) -> None:
        """TierBounds.clamp should correctly clamp values."""
        bounds = TierBounds(min_value=1, max_value=8)

        assert bounds.clamp(0) == 1  # Below min
        assert bounds.clamp(5) == 5  # Within range
        assert bounds.clamp(10) == 8  # Above max


class TestThresholdConfig:
    """Tests for ThresholdConfig dataclass."""

    def test_threshold_config_creation(self) -> None:
        """ThresholdConfig should be created with valid values."""
        config = ThresholdConfig(low=30, medium=50, high=70)
        assert config.low == 30
        assert config.medium == 50
        assert config.high == 70

    def test_threshold_config_ordering_validation(self) -> None:
        """ThresholdConfig should validate ordering."""
        with pytest.raises(ConfigurationError):
            ThresholdConfig(low=50, medium=30, high=70)  # Invalid: low > medium

    def test_saturation_thresholds(self, temp_config_file: str) -> None:
        """Saturation thresholds should be correct."""
        config = AlgorithmConfig(temp_config_file)
        sat = config.saturation_thresholds

        assert isinstance(sat, ThresholdConfig)
        assert sat.low == 30
        assert sat.medium == 50
        assert sat.high == 70

    def test_opportunity_thresholds(self, temp_config_file: str) -> None:
        """Opportunity thresholds should be correct."""
        config = AlgorithmConfig(temp_config_file)
        opp = config.opportunity_thresholds

        assert isinstance(opp, ThresholdConfig)
        assert opp.low == 30
        assert opp.medium == 50
        assert opp.high == 70


class TestMultiplierConfig:
    """Tests for MultiplierConfig dataclass."""

    def test_multiplier_config_creation(self) -> None:
        """MultiplierConfig should be created with values."""
        config = MultiplierConfig(high=0.7, medium=0.9, normal=1.0)
        assert config.high == 0.7
        assert config.medium == 0.9
        assert config.normal == 1.0

    def test_saturation_multipliers(self, temp_config_file: str) -> None:
        """Saturation multipliers should be correct."""
        config = AlgorithmConfig(temp_config_file)
        mult = config.saturation_multipliers

        assert isinstance(mult, MultiplierConfig)
        assert mult.high == 0.7
        assert mult.medium == 0.9
        assert mult.normal == 1.0

    def test_opportunity_multipliers(self, temp_config_file: str) -> None:
        """Opportunity multipliers should be correct."""
        config = AlgorithmConfig(temp_config_file)
        mult = config.opportunity_multipliers

        assert isinstance(mult, MultiplierConfig)
        assert mult.high == 1.2
        assert mult.medium == 1.1
        assert mult.normal == 1.0


class TestSmoothInterpolation:
    """Tests for smooth interpolation configuration."""

    def test_smooth_interpolation_enabled(self, temp_config_file: str) -> None:
        """Smooth interpolation should be enabled."""
        config = AlgorithmConfig(temp_config_file)
        smooth = config.smooth_interpolation

        assert isinstance(smooth, SmoothInterpolationConfig)
        assert smooth.enabled is True

    def test_saturation_breakpoints(self, temp_config_file: str) -> None:
        """Saturation breakpoints should be correct."""
        config = AlgorithmConfig(temp_config_file)
        smooth = config.smooth_interpolation

        assert len(smooth.saturation_breakpoints) == 5
        assert smooth.saturation_breakpoints[0].score == 0
        assert smooth.saturation_breakpoints[0].multiplier == 1.0
        assert smooth.saturation_breakpoints[3].score == 70
        assert smooth.saturation_breakpoints[3].multiplier == 0.7

    def test_saturation_interpolation(self, temp_config_file: str) -> None:
        """Saturation interpolation should produce correct values."""
        config = AlgorithmConfig(temp_config_file)
        smooth = config.smooth_interpolation

        # Test edge values
        assert smooth.interpolate_saturation(0) == 1.0
        assert smooth.interpolate_saturation(30) == 1.0
        assert smooth.interpolate_saturation(50) == 0.9
        assert smooth.interpolate_saturation(70) == 0.7
        assert smooth.interpolate_saturation(100) == 0.7

        # Test interpolated value
        mid_value = smooth.interpolate_saturation(40)
        assert 0.9 < mid_value < 1.0  # Between 30 and 50 breakpoints

    def test_opportunity_interpolation(self, temp_config_file: str) -> None:
        """Opportunity interpolation should produce correct values."""
        config = AlgorithmConfig(temp_config_file)
        smooth = config.smooth_interpolation

        # Test edge values
        assert smooth.interpolate_opportunity(0) == 1.0
        assert smooth.interpolate_opportunity(30) == 1.0
        assert smooth.interpolate_opportunity(50) == 1.1
        assert smooth.interpolate_opportunity(70) == 1.2
        assert smooth.interpolate_opportunity(100) == 1.2


class TestTrendConfig:
    """Tests for trend configuration."""

    def test_trend_thresholds_tuple(self, temp_config_file: str) -> None:
        """Trend thresholds should return tuple."""
        config = AlgorithmConfig(temp_config_file)
        negative, positive = config.trend_thresholds

        assert negative == -15
        assert positive == 15

    def test_trend_config_dataclass(self, temp_config_file: str) -> None:
        """Trend config should return TrendConfig."""
        config = AlgorithmConfig(temp_config_file)
        trend = config.trend_config

        assert isinstance(trend, TrendConfig)
        assert trend.negative_threshold == -15
        assert trend.positive_threshold == 15


class TestNewCreatorConfig:
    """Tests for new creator configuration."""

    def test_new_creator_config(self, temp_config_file: str) -> None:
        """New creator config should be correct."""
        config = AlgorithmConfig(temp_config_file)
        nc = config.new_creator_config

        assert isinstance(nc, NewCreatorConfig)
        assert nc.min_messages_for_analysis == 5
        assert nc.days_to_consider_new == 30
        assert nc.default_saturation == 40.0
        assert nc.default_opportunity == 60.0


class TestRoundingConfig:
    """Tests for rounding configuration."""

    def test_rounding_config(self, temp_config_file: str) -> None:
        """Rounding config should be correct."""
        config = AlgorithmConfig(temp_config_file)
        rounding = config.rounding_config

        assert isinstance(rounding, RoundingConfig)
        assert rounding.use_decimal is True
        assert rounding.method == "ROUND_HALF_UP"
        assert rounding.precision == 4

    def test_rounding_volume(self) -> None:
        """RoundingConfig.round_volume should work correctly."""
        config = RoundingConfig(use_decimal=True, method="ROUND_HALF_UP", precision=4)

        assert config.round_volume(4.5) == 5  # Round up
        assert config.round_volume(4.4) == 4  # Round down
        assert config.round_volume(4.0) == 4  # Exact
        assert config.round_volume(3.5) == 4  # Banker's rounding


class TestInterpolationBreakpoint:
    """Tests for InterpolationBreakpoint dataclass."""

    def test_breakpoint_creation(self) -> None:
        """Breakpoint should be created with values."""
        bp = InterpolationBreakpoint(score=50.0, multiplier=0.9)
        assert bp.score == 50.0
        assert bp.multiplier == 0.9

    def test_breakpoint_frozen(self) -> None:
        """Breakpoint should be immutable."""
        bp = InterpolationBreakpoint(score=50.0, multiplier=0.9)
        with pytest.raises(Exception):  # FrozenInstanceError
            bp.score = 60.0


class TestSmoothInterpolationManual:
    """Tests for manual smooth interpolation calculations."""

    def test_interpolate_below_first_breakpoint(self) -> None:
        """Values below first breakpoint should use first multiplier."""
        breakpoints = (
            InterpolationBreakpoint(30, 1.0),
            InterpolationBreakpoint(70, 0.7),
        )
        config = SmoothInterpolationConfig(
            enabled=True,
            saturation_breakpoints=breakpoints,
            opportunity_breakpoints=(),
        )
        assert config.interpolate_saturation(10) == 1.0

    def test_interpolate_above_last_breakpoint(self) -> None:
        """Values above last breakpoint should use last multiplier."""
        breakpoints = (
            InterpolationBreakpoint(30, 1.0),
            InterpolationBreakpoint(70, 0.7),
        )
        config = SmoothInterpolationConfig(
            enabled=True,
            saturation_breakpoints=breakpoints,
            opportunity_breakpoints=(),
        )
        assert config.interpolate_saturation(90) == 0.7

    def test_interpolate_midpoint(self) -> None:
        """Midpoint should be average of surrounding multipliers."""
        breakpoints = (
            InterpolationBreakpoint(0, 1.0),
            InterpolationBreakpoint(100, 0.0),
        )
        config = SmoothInterpolationConfig(
            enabled=True,
            saturation_breakpoints=breakpoints,
            opportunity_breakpoints=(),
        )
        # At score 50, should be 0.5 (midpoint between 1.0 and 0.0)
        assert config.interpolate_saturation(50) == 0.5

    def test_interpolate_empty_breakpoints(self) -> None:
        """Empty breakpoints should return 1.0."""
        config = SmoothInterpolationConfig(
            enabled=True,
            saturation_breakpoints=(),
            opportunity_breakpoints=(),
        )
        assert config.interpolate_saturation(50) == 1.0


class TestDataclassImmutability:
    """Tests for dataclass immutability (frozen=True)."""

    def test_tier_bounds_frozen(self) -> None:
        """TierBounds should be immutable."""
        bounds = TierBounds(min_value=1, max_value=8)
        with pytest.raises(Exception):
            bounds.min_value = 0

    def test_threshold_config_frozen(self) -> None:
        """ThresholdConfig should be immutable."""
        config = ThresholdConfig(low=30, medium=50, high=70)
        with pytest.raises(Exception):
            config.low = 20

    def test_multiplier_config_frozen(self) -> None:
        """MultiplierConfig should be immutable."""
        config = MultiplierConfig(high=0.7, medium=0.9, normal=1.0)
        with pytest.raises(Exception):
            config.high = 0.6

    def test_new_creator_config_frozen(self) -> None:
        """NewCreatorConfig should be immutable."""
        config = NewCreatorConfig(
            min_messages_for_analysis=5,
            days_to_consider_new=30,
            default_saturation=40.0,
            default_opportunity=60.0,
        )
        with pytest.raises(Exception):
            config.min_messages_for_analysis = 10
