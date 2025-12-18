"""
Configuration loader for volume algorithm.

Loads tier configs, thresholds, and multipliers from YAML with validation.
Provides type-safe access to all algorithm configuration values.

Usage:
    from python.volume.config_loader import get_config, reload_config

    config = get_config()
    thresholds = config.saturation_thresholds
    print(f"High saturation threshold: {thresholds.high}")

Environment Variables:
    EROS_ALGORITHM_CONFIG_PATH: Override default config file location
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from python.exceptions import ConfigurationError
from python.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Configuration Dataclasses
# =============================================================================


@dataclass(frozen=True)
class TierBounds:
    """Volume bounds for a category.

    Attributes:
        min_value: Minimum allowed volume for this category.
        max_value: Maximum allowed volume for this category.
    """

    min_value: int
    max_value: int

    def clamp(self, value: int) -> int:
        """Clamp a value to these bounds.

        Args:
            value: The value to clamp.

        Returns:
            Value clamped to [min_value, max_value].
        """
        return max(self.min_value, min(self.max_value, value))


@dataclass(frozen=True)
class ThresholdConfig:
    """Threshold configuration for saturation/opportunity scores.

    Attributes:
        low: Low threshold value.
        medium: Medium threshold value.
        high: High threshold value.
    """

    low: int
    medium: int
    high: int

    def __post_init__(self) -> None:
        """Validate threshold ordering."""
        if not (self.low <= self.medium <= self.high):
            raise ConfigurationError(
                f"Thresholds must be ordered: low <= medium <= high, "
                f"got low={self.low}, medium={self.medium}, high={self.high}",
                config_key="thresholds",
            )


@dataclass(frozen=True)
class MultiplierConfig:
    """Multiplier values for volume adjustments.

    Attributes:
        high: Multiplier for high threshold.
        medium: Multiplier for medium threshold.
        normal: Multiplier for normal/default state.
    """

    high: float
    medium: float
    normal: float


@dataclass(frozen=True)
class InterpolationBreakpoint:
    """Single breakpoint for smooth interpolation.

    Attributes:
        score: Score value at this breakpoint.
        multiplier: Multiplier value at this breakpoint.
    """

    score: float
    multiplier: float


@dataclass(frozen=True)
class SmoothInterpolationConfig:
    """Configuration for smooth threshold interpolation.

    Attributes:
        enabled: Whether smooth interpolation is enabled.
        saturation_breakpoints: Breakpoints for saturation interpolation.
        opportunity_breakpoints: Breakpoints for opportunity interpolation.
    """

    enabled: bool
    saturation_breakpoints: Tuple[InterpolationBreakpoint, ...]
    opportunity_breakpoints: Tuple[InterpolationBreakpoint, ...]

    def interpolate_saturation(self, score: float) -> float:
        """Interpolate saturation multiplier for given score.

        Uses linear interpolation between breakpoints.

        Args:
            score: Saturation score (0-100).

        Returns:
            Interpolated multiplier value.
        """
        return self._interpolate(score, self.saturation_breakpoints)

    def interpolate_opportunity(self, score: float) -> float:
        """Interpolate opportunity multiplier for given score.

        Uses linear interpolation between breakpoints.

        Args:
            score: Opportunity score (0-100).

        Returns:
            Interpolated multiplier value.
        """
        return self._interpolate(score, self.opportunity_breakpoints)

    @staticmethod
    def _interpolate(
        score: float, breakpoints: Tuple[InterpolationBreakpoint, ...]
    ) -> float:
        """Perform linear interpolation between breakpoints.

        Args:
            score: Score value to interpolate.
            breakpoints: Sorted breakpoints for interpolation.

        Returns:
            Interpolated multiplier value.
        """
        if not breakpoints:
            return 1.0

        # Handle edge cases
        if score <= breakpoints[0].score:
            return breakpoints[0].multiplier
        if score >= breakpoints[-1].score:
            return breakpoints[-1].multiplier

        # Find surrounding breakpoints
        for i in range(len(breakpoints) - 1):
            lower = breakpoints[i]
            upper = breakpoints[i + 1]
            if lower.score <= score <= upper.score:
                # Linear interpolation
                if upper.score == lower.score:
                    return lower.multiplier
                t = (score - lower.score) / (upper.score - lower.score)
                return lower.multiplier + t * (upper.multiplier - lower.multiplier)

        return 1.0


@dataclass(frozen=True)
class NewCreatorConfig:
    """Configuration for new creator handling.

    Attributes:
        min_messages_for_analysis: Minimum messages before using performance data.
        days_to_consider_new: Days after first message to consider "new".
        default_saturation: Default saturation score for new creators.
        default_opportunity: Default opportunity score for new creators.
    """

    min_messages_for_analysis: int
    days_to_consider_new: int
    default_saturation: float
    default_opportunity: float


@dataclass(frozen=True)
class RoundingConfig:
    """Configuration for rounding behavior.

    Attributes:
        use_decimal: Whether to use Decimal for calculations.
        method: Rounding method name.
        precision: Decimal places for intermediate calculations.
    """

    use_decimal: bool
    method: str
    precision: int

    def round_volume(self, value: float) -> int:
        """Round a volume value according to configuration.

        Args:
            value: Float value to round.

        Returns:
            Rounded integer value.
        """
        if self.use_decimal:
            return int(
                Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        return round(value)


@dataclass(frozen=True)
class TrendConfig:
    """Configuration for trend thresholds.

    Attributes:
        negative_threshold: Threshold for negative trend adjustment.
        positive_threshold: Threshold for positive trend adjustment.
    """

    negative_threshold: float
    positive_threshold: float


# =============================================================================
# Main Configuration Class
# =============================================================================


class AlgorithmConfig:
    """Validated algorithm configuration loaded from YAML.

    Provides type-safe access to all configuration values with validation
    on load. Configuration is immutable after initialization.

    Attributes:
        config_path: Path to the configuration file.

    Example:
        config = AlgorithmConfig()
        thresholds = config.saturation_thresholds
        bounds = config.bounds
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize AlgorithmConfig.

        Args:
            config_path: Path to YAML config file. If not provided,
                         uses default location.

        Raises:
            ConfigurationError: If config file not found or invalid.
        """
        self._config_path = config_path or self._default_path()
        self._raw_config = self._load_config()
        self._validate_config()
        self._parse_config()

    @staticmethod
    def _default_path() -> str:
        """Get default configuration file path.

        Returns:
            Absolute path to default config file.
        """
        return str(Path(__file__).parent.parent / "config" / "algorithm_config.yaml")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file.

        Returns:
            Parsed YAML as dictionary.

        Raises:
            ConfigurationError: If file not found or invalid YAML.
        """
        try:
            with open(self._config_path, "r") as f:
                config = yaml.safe_load(f)
                logger.debug(
                    "Loaded algorithm config",
                    extra={"config_path": self._config_path},
                )
                result: dict[str, Any] = dict(config) if config else {}
                return result
        except FileNotFoundError as e:
            raise ConfigurationError(
                f"Algorithm config not found: {self._config_path}",
                config_key="config_path",
            ) from e
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML in algorithm config: {e}",
                config_key="yaml_syntax",
            ) from e

    def _validate_config(self) -> None:
        """Validate all required sections exist.

        Raises:
            ConfigurationError: If required section is missing.
        """
        required_sections = ["volume", "performance", "multipliers", "trends", "new_creator"]
        for section in required_sections:
            if section not in self._raw_config:
                raise ConfigurationError(
                    f"Missing required config section: {section}",
                    config_key=section,
                )

    def _parse_config(self) -> None:
        """Parse raw config into typed dataclasses."""
        # Parse bounds
        bounds_raw = self._raw_config["volume"]["bounds"]
        self._bounds = {
            cat: TierBounds(cfg["min"], cfg["max"]) for cat, cfg in bounds_raw.items()
        }

        # Parse thresholds
        sat_raw = self._raw_config["performance"]["saturation"]
        self._saturation_thresholds = ThresholdConfig(
            sat_raw["low"], sat_raw["medium"], sat_raw["high"]
        )

        opp_raw = self._raw_config["performance"]["opportunity"]
        self._opportunity_thresholds = ThresholdConfig(
            opp_raw["low"], opp_raw["medium"], opp_raw["high"]
        )

        # Parse multipliers
        sat_mult = self._raw_config["multipliers"]["saturation"]
        self._saturation_multipliers = MultiplierConfig(
            sat_mult["high"], sat_mult["medium"], sat_mult["normal"]
        )

        opp_mult = self._raw_config["multipliers"]["opportunity"]
        self._opportunity_multipliers = MultiplierConfig(
            opp_mult["high"], opp_mult["medium"], opp_mult["normal"]
        )

        # Parse smooth interpolation config
        smooth_raw = self._raw_config["multipliers"].get("smooth_interpolation", {})
        if smooth_raw.get("enabled", False):
            sat_bp = tuple(
                InterpolationBreakpoint(bp["score"], bp["multiplier"])
                for bp in smooth_raw.get("saturation_breakpoints", [])
            )
            opp_bp = tuple(
                InterpolationBreakpoint(bp["score"], bp["multiplier"])
                for bp in smooth_raw.get("opportunity_breakpoints", [])
            )
            self._smooth_interpolation = SmoothInterpolationConfig(
                enabled=True,
                saturation_breakpoints=sat_bp,
                opportunity_breakpoints=opp_bp,
            )
        else:
            self._smooth_interpolation = SmoothInterpolationConfig(
                enabled=False,
                saturation_breakpoints=(),
                opportunity_breakpoints=(),
            )

        # Parse trend config
        trends_raw = self._raw_config["trends"]
        self._trend_config = TrendConfig(
            negative_threshold=trends_raw["revenue_threshold_negative"],
            positive_threshold=trends_raw["revenue_threshold_positive"],
        )

        # Parse new creator config
        nc_raw = self._raw_config["new_creator"]
        self._new_creator_config = NewCreatorConfig(
            min_messages_for_analysis=nc_raw["min_messages_for_analysis"],
            days_to_consider_new=nc_raw["days_to_consider_new"],
            default_saturation=nc_raw["default_saturation"],
            default_opportunity=nc_raw["default_opportunity"],
        )

        # Parse rounding config
        rounding_raw = self._raw_config.get("rounding", {})
        self._rounding_config = RoundingConfig(
            use_decimal=rounding_raw.get("use_decimal", True),
            method=rounding_raw.get("method", "ROUND_HALF_UP"),
            precision=rounding_raw.get("precision", 4),
        )

    # =========================================================================
    # Properties for accessing validated config values
    # =========================================================================

    @property
    def config_path(self) -> str:
        """Get the configuration file path."""
        return self._config_path

    @property
    def fan_thresholds(self) -> Dict[str, Tuple[int, Optional[int]]]:
        """Get fan count thresholds per tier.

        Returns:
            Dictionary mapping tier name to (min_fans, max_fans) tuple.
            max_fans is None for the highest tier (no upper bound).
        """
        thresholds = self._raw_config["volume"]["fan_thresholds"]
        return {
            tier: (cfg["min"], cfg["max"]) for tier, cfg in thresholds.items()
        }

    @property
    def tier_configs(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Get tier configurations for paid/free pages.

        Returns:
            Nested dictionary: tier -> page_type -> category -> volume.
        """
        result: Dict[str, Dict[str, Dict[str, int]]] = self._raw_config["volume"]["tier_configs"]
        return result

    @property
    def bounds(self) -> Dict[str, TierBounds]:
        """Get volume bounds per category.

        Returns:
            Dictionary mapping category name to TierBounds.
        """
        return self._bounds

    @property
    def saturation_thresholds(self) -> ThresholdConfig:
        """Get saturation score thresholds.

        Returns:
            ThresholdConfig with low, medium, high values.
        """
        return self._saturation_thresholds

    @property
    def opportunity_thresholds(self) -> ThresholdConfig:
        """Get opportunity score thresholds.

        Returns:
            ThresholdConfig with low, medium, high values.
        """
        return self._opportunity_thresholds

    @property
    def saturation_multipliers(self) -> MultiplierConfig:
        """Get saturation multipliers.

        Returns:
            MultiplierConfig with high, medium, normal values.
        """
        return self._saturation_multipliers

    @property
    def opportunity_multipliers(self) -> MultiplierConfig:
        """Get opportunity multipliers.

        Returns:
            MultiplierConfig with high, medium, normal values.
        """
        return self._opportunity_multipliers

    @property
    def smooth_interpolation(self) -> SmoothInterpolationConfig:
        """Get smooth interpolation configuration.

        Returns:
            SmoothInterpolationConfig with breakpoints.
        """
        return self._smooth_interpolation

    @property
    def trend_thresholds(self) -> Tuple[float, float]:
        """Get trend thresholds (negative, positive).

        Returns:
            Tuple of (negative_threshold, positive_threshold).
        """
        return (
            self._trend_config.negative_threshold,
            self._trend_config.positive_threshold,
        )

    @property
    def trend_config(self) -> TrendConfig:
        """Get full trend configuration.

        Returns:
            TrendConfig dataclass.
        """
        return self._trend_config

    @property
    def new_creator_config(self) -> NewCreatorConfig:
        """Get new creator handling configuration.

        Returns:
            NewCreatorConfig dataclass.
        """
        return self._new_creator_config

    @property
    def rounding_config(self) -> RoundingConfig:
        """Get rounding configuration.

        Returns:
            RoundingConfig dataclass.
        """
        return self._rounding_config


# =============================================================================
# Global Singleton Management
# =============================================================================

_config_instance: Optional[AlgorithmConfig] = None


def get_config() -> AlgorithmConfig:
    """Get or create the global config instance.

    Returns:
        The singleton AlgorithmConfig instance.

    Example:
        config = get_config()
        print(config.saturation_thresholds.high)
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = AlgorithmConfig()
    return _config_instance


def reload_config(config_path: Optional[str] = None) -> AlgorithmConfig:
    """Reload configuration (useful for testing).

    Args:
        config_path: Optional path to config file.

    Returns:
        Newly loaded AlgorithmConfig instance.

    Example:
        # In tests
        config = reload_config("/path/to/test_config.yaml")
    """
    global _config_instance
    _config_instance = AlgorithmConfig(config_path)
    logger.info(
        "Reloaded algorithm config",
        extra={"config_path": config_path or "default"},
    )
    return _config_instance


def clear_config() -> None:
    """Clear the global config instance.

    Useful for testing to ensure fresh config loads.
    """
    global _config_instance
    _config_instance = None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Dataclasses
    "TierBounds",
    "ThresholdConfig",
    "MultiplierConfig",
    "InterpolationBreakpoint",
    "SmoothInterpolationConfig",
    "NewCreatorConfig",
    "RoundingConfig",
    "TrendConfig",
    # Main class
    "AlgorithmConfig",
    # Functions
    "get_config",
    "reload_config",
    "clear_config",
]
