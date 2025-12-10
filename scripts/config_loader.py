#!/usr/bin/env python3
"""
Config Loader - Type-safe configuration management for EROS Schedule Generator.

This module provides centralized access to all business rules and configuration
values, with support for:
- YAML configuration file loading
- Environment variable overrides
- Type-safe access via dataclasses
- Caching for performance
- Validation of configuration values

Usage:
    from config_loader import get_config, BusinessRules

    config = get_config()
    min_spacing = config.ppv.min_spacing_hours

    # Or access specific sections
    from config_loader import get_ppv_config, get_freshness_config
    ppv = get_ppv_config()
    print(ppv.min_spacing_hours)

Environment Variables:
    EROS_CONFIG_PATH - Path to custom config file (default: config/business_rules.yaml)
    EROS_PPV_MIN_SPACING_HOURS - Override PPV minimum spacing
    EROS_FRESHNESS_MINIMUM_SCORE - Override freshness minimum
    ... (see BusinessRules for all options)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Path resolution
SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR.parent / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "business_rules.yaml"
SELECTION_CONFIG_PATH = CONFIG_DIR / "selection.yaml"


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        """Initialize with error message and optional list of validation errors.

        Args:
            message: Main error message
            errors: List of specific validation errors
        """
        super().__init__(message)
        self.errors = errors or []

    def __str__(self) -> str:
        if self.errors:
            error_list = "\n  - ".join(self.errors)
            return f"{super().__str__()}\nValidation errors:\n  - {error_list}"
        return super().__str__()


# =============================================================================
# TYPE-SAFE CONFIGURATION DATACLASSES
# =============================================================================


@dataclass(frozen=True, slots=True)
class PPVConfig:
    """PPV (Pay-Per-View) configuration."""

    min_spacing_hours: int = 3
    recommended_spacing_hours: int = 4
    max_per_day: int = 6
    max_per_week: int = 42


@dataclass(frozen=True, slots=True)
class FreshnessConfig:
    """Caption freshness configuration."""

    minimum_score: float = 30.0
    decay_days: int = 14
    selection_weight: float = 0.4


@dataclass(frozen=True, slots=True)
class FollowUpConfig:
    """Follow-up (bump) message configuration."""

    min_minutes: int = 15
    max_minutes: int = 45


@dataclass(frozen=True, slots=True)
class DripWindowConfig:
    """Drip window (no-PPV zone) configuration."""

    start_hour: int = 14
    end_hour: int = 22
    enabled_default: bool = False


@dataclass(frozen=True, slots=True)
class PaydayConfig:
    """Payday optimization configuration."""

    premium_boost: float = 1.2
    premium_penalty: float = 0.9
    days: tuple[int, ...] = (1, 15)


@dataclass(frozen=True, slots=True)
class VolumeTier:
    """Configuration for a single volume tier."""

    ppv_per_day: tuple[int, int]  # (min, max)
    bump_per_day: tuple[int, int]  # (min, max)
    fan_range: tuple[int, int | None]  # (min, max or None for no limit)


@dataclass(frozen=True, slots=True)
class VolumeTiersConfig:
    """Volume tiers configuration by fan count."""

    low: VolumeTier = field(
        default_factory=lambda: VolumeTier(
            ppv_per_day=(2, 3), bump_per_day=(2, 3), fan_range=(0, 999)
        )
    )
    mid: VolumeTier = field(
        default_factory=lambda: VolumeTier(
            ppv_per_day=(3, 4), bump_per_day=(2, 3), fan_range=(1000, 4999)
        )
    )
    high: VolumeTier = field(
        default_factory=lambda: VolumeTier(
            ppv_per_day=(4, 5), bump_per_day=(3, 4), fan_range=(5000, 14999)
        )
    )
    ultra: VolumeTier = field(
        default_factory=lambda: VolumeTier(
            ppv_per_day=(5, 6), bump_per_day=(4, 5), fan_range=(15000, None)
        )
    )

    def get_tier_for_fans(self, fan_count: int) -> tuple[str, VolumeTier]:
        """Get the appropriate tier for a given fan count.

        Args:
            fan_count: Number of active fans

        Returns:
            Tuple of (tier_name, VolumeTier)
        """
        tiers = [
            ("low", self.low),
            ("mid", self.mid),
            ("high", self.high),
            ("ultra", self.ultra),
        ]
        for name, tier in tiers:
            min_fans, max_fans = tier.fan_range
            if max_fans is None:
                if fan_count >= min_fans:
                    return name, tier
            elif min_fans <= fan_count <= max_fans:
                return name, tier
        return "low", self.low  # Fallback


@dataclass(frozen=True, slots=True)
class ContentTypesConfig:
    """Content type configuration."""

    premium: tuple[str, ...] = ("bundle", "sextape", "bg", "gg", "custom")
    rotation_order: tuple[str, ...] = (
        "solo",
        "bundle",
        "winner",
        "sextape",
        "bg",
        "gg",
        "toy_play",
        "custom",
        "dick_rate",
    )


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Validation rules configuration."""

    max_correction_passes: int = 2
    auto_correct_enabled: bool = True
    max_consecutive_same_type: int = 3


@dataclass(frozen=True, slots=True)
class SpacingConfig:
    """Content spacing rules configuration."""

    wall_post_min_hours: int = 1
    wall_post_recommended_hours: int = 2
    poll_min_days: int = 2
    vip_post_min_hours: int = 24
    link_drop_hours: int = 4
    bundle_min_hours: int = 24
    flash_bundle_min_hours: int = 48


@dataclass(frozen=True, slots=True)
class PreviewConfig:
    """Preview-PPV linkage configuration."""

    min_lead_hours: int = 1
    max_lead_hours: int = 3


@dataclass(frozen=True, slots=True)
class EngagementConfig:
    """Engagement content limits configuration."""

    daily_limit: int = 2
    weekly_limit: int = 10


@dataclass(frozen=True, slots=True)
class WeightsConfig:
    """Selection weight configuration."""

    performance_weight: float = 0.6
    freshness_weight: float = 0.4


@dataclass(frozen=True, slots=True)
class SelectionConfig:
    """Caption selection configuration for the redesigned selection system.

    This dataclass holds all configuration values for the pattern-based
    caption selection system that prioritizes fresh/unused captions guided
    by historical performance patterns.

    Attributes:
        exclusion_days: Hard exclusion window in days (30-120)
        exploration_ratio: Percentage of selections for random picks (0.05-0.25)
        min_pattern_samples: Minimum samples to establish a pattern
        pattern_lookback_days: Days to look back for pattern extraction
        pattern_cache_ttl_hours: Cache time-to-live in hours
        pattern_cache_max_size: Maximum cached patterns
        use_global_fallback: Use global patterns for new creators
        global_fallback_discount: Discount factor for global patterns (0.5-1.0)
        use_legacy_weights: Toggle for legacy selection algorithm

        Weight components (must sum to 1.0):
        weight_pattern_match: Weight for historical pattern matching
        weight_never_used_bonus: Weight for never-used captions
        weight_persona: Weight for persona matching
        weight_freshness_bonus: Weight for freshness scoring
        weight_exploration: Weight for random exploration

        Freshness multipliers:
        freshness_never_used_multiplier: Multiplier for never-used captions
        freshness_fresh_multiplier: Multiplier for fresh captions
    """

    # Core selection settings
    exclusion_days: int = 60
    exploration_ratio: float = 0.15
    min_pattern_samples: int = 3
    pattern_lookback_days: int = 90
    pattern_cache_ttl_hours: int = 24
    pattern_cache_max_size: int = 100
    use_global_fallback: bool = True
    global_fallback_discount: float = 0.7
    use_legacy_weights: bool = False

    # Weight components (must sum to 1.0)
    weight_pattern_match: float = 0.40
    weight_never_used_bonus: float = 0.25
    weight_persona: float = 0.15
    weight_freshness_bonus: float = 0.10
    weight_exploration: float = 0.10

    # Freshness tier multipliers
    freshness_never_used_multiplier: float = 1.5
    freshness_fresh_multiplier: float = 1.0

    def get_weights_sum(self) -> float:
        """Calculate the sum of all weight components.

        Returns:
            Sum of weight_pattern_match, weight_never_used_bonus,
            weight_persona, weight_freshness_bonus, and weight_exploration.
        """
        return (
            self.weight_pattern_match
            + self.weight_never_used_bonus
            + self.weight_persona
            + self.weight_freshness_bonus
            + self.weight_exploration
        )


@dataclass(frozen=True, slots=True)
class BusinessRules:
    """
    Complete business rules configuration.

    This is the main configuration object containing all business rules
    for the EROS Schedule Generator.

    Attributes:
        ppv: PPV spacing and limits
        freshness: Caption freshness rules
        follow_up: Follow-up timing rules
        drip_window: Drip window (no-PPV zones) rules
        payday: Payday optimization rules
        volume_tiers: Volume by fan count
        content_types: Content type configuration
        validation: Validation rules
        spacing: Content spacing rules
        preview: Preview-PPV linkage rules
        engagement: Engagement content limits
        weights: Selection weight factors
    """

    ppv: PPVConfig = field(default_factory=PPVConfig)
    freshness: FreshnessConfig = field(default_factory=FreshnessConfig)
    follow_up: FollowUpConfig = field(default_factory=FollowUpConfig)
    drip_window: DripWindowConfig = field(default_factory=DripWindowConfig)
    payday: PaydayConfig = field(default_factory=PaydayConfig)
    volume_tiers: VolumeTiersConfig = field(default_factory=VolumeTiersConfig)
    content_types: ContentTypesConfig = field(default_factory=ContentTypesConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    spacing: SpacingConfig = field(default_factory=SpacingConfig)
    preview: PreviewConfig = field(default_factory=PreviewConfig)
    engagement: EngagementConfig = field(default_factory=EngagementConfig)
    weights: WeightsConfig = field(default_factory=WeightsConfig)


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================


def _get_env_override(section: str, key: str, default: Any) -> Any:
    """Get environment variable override for a config value.

    Environment variables follow the pattern: EROS_<SECTION>_<KEY>
    For example: EROS_PPV_MIN_SPACING_HOURS

    Args:
        section: Configuration section name (e.g., "ppv")
        key: Configuration key name (e.g., "min_spacing_hours")
        default: Default value if env var not set

    Returns:
        Parsed value from environment or default
    """
    env_key = f"EROS_{section.upper()}_{key.upper()}"
    env_value = os.environ.get(env_key)

    if env_value is None:
        return default

    # Type coercion based on default type
    if isinstance(default, bool):
        return env_value.lower() in ("true", "1", "yes", "on")
    elif isinstance(default, int):
        try:
            return int(env_value)
        except ValueError:
            logger.warning(f"Invalid int value for {env_key}: {env_value}")
            return default
    elif isinstance(default, float):
        try:
            return float(env_value)
        except ValueError:
            logger.warning(f"Invalid float value for {env_key}: {env_value}")
            return default
    elif isinstance(default, (list, tuple)):
        # Handle comma-separated lists
        try:
            values = [v.strip() for v in env_value.split(",")]
            # Try to preserve original type
            if default and isinstance(default[0], int):
                return type(default)(int(v) for v in values)
            return type(default)(values)
        except (ValueError, TypeError):
            logger.warning(f"Invalid list value for {env_key}: {env_value}")
            return default
    else:
        return env_value


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary of configuration values

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
    """
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in config file: {e}")
        raise


def _build_ppv_config(yaml_data: dict[str, Any]) -> PPVConfig:
    """Build PPVConfig from YAML data with env overrides."""
    section = yaml_data.get("ppv", {})
    return PPVConfig(
        min_spacing_hours=_get_env_override(
            "ppv", "min_spacing_hours", section.get("min_spacing_hours", 3)
        ),
        recommended_spacing_hours=_get_env_override(
            "ppv", "recommended_spacing_hours", section.get("recommended_spacing_hours", 4)
        ),
        max_per_day=_get_env_override(
            "ppv", "max_per_day", section.get("max_per_day", 6)
        ),
        max_per_week=_get_env_override(
            "ppv", "max_per_week", section.get("max_per_week", 42)
        ),
    )


def _build_freshness_config(yaml_data: dict[str, Any]) -> FreshnessConfig:
    """Build FreshnessConfig from YAML data with env overrides."""
    section = yaml_data.get("freshness", {})
    return FreshnessConfig(
        minimum_score=_get_env_override(
            "freshness", "minimum_score", section.get("minimum_score", 30.0)
        ),
        decay_days=_get_env_override(
            "freshness", "decay_days", section.get("decay_days", 14)
        ),
        selection_weight=_get_env_override(
            "freshness", "selection_weight", section.get("selection_weight", 0.4)
        ),
    )


def _build_follow_up_config(yaml_data: dict[str, Any]) -> FollowUpConfig:
    """Build FollowUpConfig from YAML data with env overrides."""
    section = yaml_data.get("follow_up", {})
    return FollowUpConfig(
        min_minutes=_get_env_override(
            "follow_up", "min_minutes", section.get("min_minutes", 15)
        ),
        max_minutes=_get_env_override(
            "follow_up", "max_minutes", section.get("max_minutes", 45)
        ),
    )


def _build_drip_window_config(yaml_data: dict[str, Any]) -> DripWindowConfig:
    """Build DripWindowConfig from YAML data with env overrides."""
    section = yaml_data.get("drip_window", {})
    return DripWindowConfig(
        start_hour=_get_env_override(
            "drip_window", "start_hour", section.get("start_hour", 14)
        ),
        end_hour=_get_env_override(
            "drip_window", "end_hour", section.get("end_hour", 22)
        ),
        enabled_default=_get_env_override(
            "drip_window", "enabled_default", section.get("enabled_default", False)
        ),
    )


def _build_payday_config(yaml_data: dict[str, Any]) -> PaydayConfig:
    """Build PaydayConfig from YAML data with env overrides."""
    section = yaml_data.get("payday", {})
    days = section.get("days", [1, 15])
    return PaydayConfig(
        premium_boost=_get_env_override(
            "payday", "premium_boost", section.get("premium_boost", 1.2)
        ),
        premium_penalty=_get_env_override(
            "payday", "premium_penalty", section.get("premium_penalty", 0.9)
        ),
        days=tuple(_get_env_override("payday", "days", days)),
    )


def _build_volume_tier(tier_data: dict[str, Any]) -> VolumeTier:
    """Build a single VolumeTier from YAML data."""
    ppv = tier_data.get("ppv_per_day", [2, 3])
    bump = tier_data.get("bump_per_day", [2, 3])
    fan_range = tier_data.get("fan_range", [0, 999])

    return VolumeTier(
        ppv_per_day=(ppv[0], ppv[1]),
        bump_per_day=(bump[0], bump[1]),
        fan_range=(fan_range[0], fan_range[1] if fan_range[1] is not None else None),
    )


def _build_volume_tiers_config(yaml_data: dict[str, Any]) -> VolumeTiersConfig:
    """Build VolumeTiersConfig from YAML data."""
    section = yaml_data.get("volume_tiers", {})

    return VolumeTiersConfig(
        low=_build_volume_tier(section.get("low", {})),
        mid=_build_volume_tier(section.get("mid", {})),
        high=_build_volume_tier(section.get("high", {})),
        ultra=_build_volume_tier(section.get("ultra", {})),
    )


def _build_content_types_config(yaml_data: dict[str, Any]) -> ContentTypesConfig:
    """Build ContentTypesConfig from YAML data."""
    section = yaml_data.get("content_types", {})
    default_rotation = [
        "solo", "bundle", "winner", "sextape", "bg",
        "gg", "toy_play", "custom", "dick_rate",
    ]
    return ContentTypesConfig(
        premium=tuple(section.get("premium", ["bundle", "sextape", "bg", "gg", "custom"])),
        rotation_order=tuple(section.get("rotation_order", default_rotation)),
    )


def _build_validation_config(yaml_data: dict[str, Any]) -> ValidationConfig:
    """Build ValidationConfig from YAML data with env overrides."""
    section = yaml_data.get("validation", {})
    return ValidationConfig(
        max_correction_passes=_get_env_override(
            "validation", "max_correction_passes", section.get("max_correction_passes", 2)
        ),
        auto_correct_enabled=_get_env_override(
            "validation", "auto_correct_enabled", section.get("auto_correct_enabled", True)
        ),
        max_consecutive_same_type=_get_env_override(
            "validation", "max_consecutive_same_type", section.get("max_consecutive_same_type", 3)
        ),
    )


def _build_spacing_config(yaml_data: dict[str, Any]) -> SpacingConfig:
    """Build SpacingConfig from YAML data."""
    section = yaml_data.get("spacing", {})
    return SpacingConfig(
        wall_post_min_hours=section.get("wall_post_min_hours", 1),
        wall_post_recommended_hours=section.get("wall_post_recommended_hours", 2),
        poll_min_days=section.get("poll_min_days", 2),
        vip_post_min_hours=section.get("vip_post_min_hours", 24),
        link_drop_hours=section.get("link_drop_hours", 4),
        bundle_min_hours=section.get("bundle_min_hours", 24),
        flash_bundle_min_hours=section.get("flash_bundle_min_hours", 48),
    )


def _build_preview_config(yaml_data: dict[str, Any]) -> PreviewConfig:
    """Build PreviewConfig from YAML data."""
    section = yaml_data.get("preview", {})
    return PreviewConfig(
        min_lead_hours=section.get("min_lead_hours", 1),
        max_lead_hours=section.get("max_lead_hours", 3),
    )


def _build_engagement_config(yaml_data: dict[str, Any]) -> EngagementConfig:
    """Build EngagementConfig from YAML data."""
    section = yaml_data.get("engagement", {})
    return EngagementConfig(
        daily_limit=section.get("daily_limit", 2),
        weekly_limit=section.get("weekly_limit", 10),
    )


def _build_weights_config(yaml_data: dict[str, Any]) -> WeightsConfig:
    """Build WeightsConfig from YAML data with env overrides."""
    section = yaml_data.get("weights", {})
    return WeightsConfig(
        performance_weight=_get_env_override(
            "weights", "performance_weight", section.get("performance_weight", 0.6)
        ),
        freshness_weight=_get_env_override(
            "weights", "freshness_weight", section.get("freshness_weight", 0.4)
        ),
    )


# =============================================================================
# SELECTION CONFIG BUILDING
# =============================================================================


def _get_selection_env_override(key: str, default: Any) -> Any:
    """Get environment variable override for selection config.

    Environment variables follow the pattern: EROS_SELECTION_<KEY>
    For example: EROS_SELECTION_EXCLUSION_DAYS

    Args:
        key: Configuration key name (e.g., "exclusion_days")
        default: Default value if env var not set

    Returns:
        Parsed value from environment or default
    """
    env_key = f"EROS_SELECTION_{key.upper()}"
    env_value = os.environ.get(env_key)

    if env_value is None:
        return default

    # Log override
    logger.info(f"Environment override: {env_key}={env_value}")

    # Type coercion based on default type
    if isinstance(default, bool):
        return env_value.lower() in ("true", "1", "yes", "on")
    elif isinstance(default, int):
        try:
            return int(env_value)
        except ValueError:
            logger.warning(f"Invalid int value for {env_key}: {env_value}")
            return default
    elif isinstance(default, float):
        try:
            return float(env_value)
        except ValueError:
            logger.warning(f"Invalid float value for {env_key}: {env_value}")
            return default
    else:
        return env_value


def _build_selection_config(yaml_data: dict[str, Any]) -> SelectionConfig:
    """Build SelectionConfig from YAML data with environment overrides.

    Args:
        yaml_data: Parsed YAML configuration dictionary from selection.yaml

    Returns:
        Fully populated SelectionConfig instance
    """
    selection = yaml_data.get("selection", {})
    weights = yaml_data.get("weights", {})
    freshness_tiers = yaml_data.get("freshness_tiers", {})

    return SelectionConfig(
        # Core selection settings
        exclusion_days=_get_selection_env_override(
            "exclusion_days", selection.get("exclusion_days", 60)
        ),
        exploration_ratio=_get_selection_env_override(
            "exploration_ratio", selection.get("exploration_ratio", 0.15)
        ),
        min_pattern_samples=_get_selection_env_override(
            "min_pattern_samples", selection.get("min_pattern_samples", 3)
        ),
        pattern_lookback_days=_get_selection_env_override(
            "pattern_lookback_days", selection.get("pattern_lookback_days", 90)
        ),
        pattern_cache_ttl_hours=_get_selection_env_override(
            "pattern_cache_ttl_hours", selection.get("pattern_cache_ttl_hours", 24)
        ),
        pattern_cache_max_size=_get_selection_env_override(
            "pattern_cache_max_size", selection.get("pattern_cache_max_size", 100)
        ),
        use_global_fallback=_get_selection_env_override(
            "use_global_fallback", selection.get("use_global_fallback", True)
        ),
        global_fallback_discount=_get_selection_env_override(
            "global_fallback_discount", selection.get("global_fallback_discount", 0.7)
        ),
        use_legacy_weights=_get_selection_env_override(
            "use_legacy_weights", selection.get("use_legacy_weights", False)
        ),
        # Weight components
        weight_pattern_match=_get_selection_env_override(
            "weight_pattern_match", weights.get("pattern_match", 0.40)
        ),
        weight_never_used_bonus=_get_selection_env_override(
            "weight_never_used_bonus", weights.get("never_used_bonus", 0.25)
        ),
        weight_persona=_get_selection_env_override(
            "weight_persona", weights.get("persona", 0.15)
        ),
        weight_freshness_bonus=_get_selection_env_override(
            "weight_freshness_bonus", weights.get("freshness_bonus", 0.10)
        ),
        weight_exploration=_get_selection_env_override(
            "weight_exploration", weights.get("exploration", 0.10)
        ),
        # Freshness multipliers
        freshness_never_used_multiplier=_get_selection_env_override(
            "freshness_never_used_multiplier", freshness_tiers.get("never_used", 1.5)
        ),
        freshness_fresh_multiplier=_get_selection_env_override(
            "freshness_fresh_multiplier", freshness_tiers.get("fresh", 1.0)
        ),
    )


def validate_selection_config(config: SelectionConfig) -> list[str]:
    """Validate SelectionConfig values and return list of errors.

    Validates:
    - exclusion_days: Must be 30-120
    - exploration_ratio: Must be 0.05-0.25
    - global_fallback_discount: Must be 0.5-1.0
    - Weight components: Must sum to 1.0 (+/- 0.01 tolerance)
    - All numeric values must be positive

    Args:
        config: SelectionConfig instance to validate

    Returns:
        List of error messages (empty if valid)

    Example:
        >>> config = SelectionConfig(exclusion_days=200)
        >>> errors = validate_selection_config(config)
        >>> print(errors)
        ['exclusion_days must be between 30 and 120 (got 200)']
    """
    errors: list[str] = []

    # Validate exclusion_days (30-120)
    if not 30 <= config.exclusion_days <= 120:
        errors.append(
            f"exclusion_days must be between 30 and 120 (got {config.exclusion_days})"
        )

    # Validate exploration_ratio (0.05-0.25)
    if not 0.05 <= config.exploration_ratio <= 0.25:
        errors.append(
            f"exploration_ratio must be between 0.05 and 0.25 (got {config.exploration_ratio})"
        )

    # Validate global_fallback_discount (0.5-1.0)
    if not 0.5 <= config.global_fallback_discount <= 1.0:
        errors.append(
            f"global_fallback_discount must be between 0.5 and 1.0 "
            f"(got {config.global_fallback_discount})"
        )

    # Validate weights sum to 1.0 (+/- 0.01 tolerance)
    weights_sum = config.get_weights_sum()
    if not 0.99 <= weights_sum <= 1.01:
        errors.append(
            f"Weight components must sum to 1.0 (+/- 0.01), "
            f"got {weights_sum:.4f} "
            f"(pattern_match={config.weight_pattern_match}, "
            f"never_used_bonus={config.weight_never_used_bonus}, "
            f"persona={config.weight_persona}, "
            f"freshness_bonus={config.weight_freshness_bonus}, "
            f"exploration={config.weight_exploration})"
        )

    # Validate positive values
    if config.min_pattern_samples < 1:
        errors.append(
            f"min_pattern_samples must be at least 1 (got {config.min_pattern_samples})"
        )

    if config.pattern_lookback_days < 1:
        errors.append(
            f"pattern_lookback_days must be at least 1 (got {config.pattern_lookback_days})"
        )

    if config.pattern_cache_ttl_hours < 1:
        errors.append(
            f"pattern_cache_ttl_hours must be at least 1 (got {config.pattern_cache_ttl_hours})"
        )

    if config.pattern_cache_max_size < 1:
        errors.append(
            f"pattern_cache_max_size must be at least 1 (got {config.pattern_cache_max_size})"
        )

    # Validate multipliers are positive
    if config.freshness_never_used_multiplier <= 0:
        errors.append(
            f"freshness_never_used_multiplier must be positive "
            f"(got {config.freshness_never_used_multiplier})"
        )

    if config.freshness_fresh_multiplier <= 0:
        errors.append(
            f"freshness_fresh_multiplier must be positive "
            f"(got {config.freshness_fresh_multiplier})"
        )

    return errors


def _build_business_rules(yaml_data: dict[str, Any]) -> BusinessRules:
    """Build complete BusinessRules from YAML data.

    Args:
        yaml_data: Parsed YAML configuration dictionary

    Returns:
        Fully populated BusinessRules instance
    """
    return BusinessRules(
        ppv=_build_ppv_config(yaml_data),
        freshness=_build_freshness_config(yaml_data),
        follow_up=_build_follow_up_config(yaml_data),
        drip_window=_build_drip_window_config(yaml_data),
        payday=_build_payday_config(yaml_data),
        volume_tiers=_build_volume_tiers_config(yaml_data),
        content_types=_build_content_types_config(yaml_data),
        validation=_build_validation_config(yaml_data),
        spacing=_build_spacing_config(yaml_data),
        preview=_build_preview_config(yaml_data),
        engagement=_build_engagement_config(yaml_data),
        weights=_build_weights_config(yaml_data),
    )


# =============================================================================
# PUBLIC API
# =============================================================================


@lru_cache(maxsize=1)
def get_config(config_path: str | Path | None = None) -> BusinessRules:
    """
    Get the business rules configuration.

    This function loads configuration from:
    1. YAML file (config/business_rules.yaml or custom path)
    2. Environment variable overrides (EROS_* prefix)

    Results are cached after first load for performance.

    Args:
        config_path: Optional custom config file path.
                    If None, uses EROS_CONFIG_PATH env var or default.

    Returns:
        BusinessRules instance with all configuration values

    Example:
        >>> config = get_config()
        >>> config.ppv.min_spacing_hours
        3
        >>> config.freshness.minimum_score
        30.0
    """
    # Determine config path
    if config_path is None:
        env_path = os.environ.get("EROS_CONFIG_PATH")
        config_path = Path(env_path) if env_path else DEFAULT_CONFIG_PATH
    else:
        config_path = Path(config_path)

    # Load and build config
    yaml_data = _load_yaml_config(config_path)
    return _build_business_rules(yaml_data)


def reload_config(config_path: str | Path | None = None) -> BusinessRules:
    """
    Reload configuration, clearing the cache.

    Use this when configuration may have changed and you need fresh values.

    Args:
        config_path: Optional custom config file path

    Returns:
        Fresh BusinessRules instance
    """
    get_config.cache_clear()
    return get_config(config_path)


@lru_cache(maxsize=1)
def load_selection_config(
    config_path: str | Path | None = None,
    validate: bool = True,
) -> SelectionConfig:
    """
    Load the caption selection configuration.

    This function loads configuration from:
    1. YAML file (config/selection.yaml or custom path)
    2. Environment variable overrides (EROS_SELECTION_* prefix)

    Supported environment variable overrides:
        - EROS_SELECTION_EXCLUSION_DAYS: Override exclusion window (30-120)
        - EROS_SELECTION_EXPLORATION_RATIO: Override exploration ratio (0.05-0.25)
        - EROS_SELECTION_USE_LEGACY_WEIGHTS: Toggle legacy mode (true/false)

    Results are cached after first load for performance.

    Args:
        config_path: Optional custom config file path.
                    If None, uses config/selection.yaml
        validate: If True, validate config and raise ConfigurationError on failure.
                 Default is True.

    Returns:
        SelectionConfig instance with all configuration values

    Raises:
        ConfigurationError: If validate=True and configuration is invalid

    Example:
        >>> config = load_selection_config()
        >>> config.exclusion_days
        60
        >>> config.exploration_ratio
        0.15
        >>> config.get_weights_sum()
        1.0
    """
    # Determine config path
    if config_path is None:
        env_path = os.environ.get("EROS_SELECTION_CONFIG_PATH")
        config_path = Path(env_path) if env_path else SELECTION_CONFIG_PATH
    else:
        config_path = Path(config_path)

    # Load YAML and build config
    yaml_data = _load_yaml_config(config_path)
    config = _build_selection_config(yaml_data)

    # Validate if requested
    if validate:
        errors = validate_selection_config(config)
        if errors:
            raise ConfigurationError(
                f"Invalid selection configuration from {config_path}",
                errors=errors,
            )

    return config


def reload_selection_config(
    config_path: str | Path | None = None,
    validate: bool = True,
) -> SelectionConfig:
    """
    Reload selection configuration, clearing the cache.

    Use this when configuration may have changed and you need fresh values.

    Args:
        config_path: Optional custom config file path
        validate: If True, validate config and raise ConfigurationError on failure

    Returns:
        Fresh SelectionConfig instance

    Raises:
        ConfigurationError: If validate=True and configuration is invalid
    """
    load_selection_config.cache_clear()
    return load_selection_config(config_path, validate)


def get_selection_config() -> SelectionConfig:
    """
    Get the cached selection configuration.

    Convenience function that calls load_selection_config() with defaults.

    Returns:
        Cached SelectionConfig instance

    Raises:
        ConfigurationError: If configuration is invalid
    """
    return load_selection_config()


# =============================================================================
# CONVENIENCE ACCESSORS
# =============================================================================


def get_ppv_config() -> PPVConfig:
    """Get PPV configuration."""
    return get_config().ppv


def get_freshness_config() -> FreshnessConfig:
    """Get freshness configuration."""
    return get_config().freshness


def get_follow_up_config() -> FollowUpConfig:
    """Get follow-up configuration."""
    return get_config().follow_up


def get_drip_window_config() -> DripWindowConfig:
    """Get drip window configuration."""
    return get_config().drip_window


def get_payday_config() -> PaydayConfig:
    """Get payday configuration."""
    return get_config().payday


def get_volume_tiers_config() -> VolumeTiersConfig:
    """Get volume tiers configuration."""
    return get_config().volume_tiers


def get_content_types_config() -> ContentTypesConfig:
    """Get content types configuration."""
    return get_config().content_types


def get_validation_config() -> ValidationConfig:
    """Get validation configuration."""
    return get_config().validation


def get_spacing_config() -> SpacingConfig:
    """Get spacing configuration."""
    return get_config().spacing


# =============================================================================
# LEGACY COMPATIBILITY CONSTANTS
# =============================================================================
# These provide backward compatibility with code that imports constants directly.
# Usage: from config_loader import MIN_PPV_SPACING_HOURS


def _get_lazy_constant(attr: str) -> Any:
    """Lazy getter for backward compatibility constants."""
    config = get_config()

    mapping = {
        "MIN_PPV_SPACING_HOURS": config.ppv.min_spacing_hours,
        "RECOMMENDED_PPV_SPACING_HOURS": config.ppv.recommended_spacing_hours,
        "MIN_FRESHNESS_SCORE": config.freshness.minimum_score,
        "FOLLOW_UP_MIN_MINUTES": config.follow_up.min_minutes,
        "FOLLOW_UP_MAX_MINUTES": config.follow_up.max_minutes,
        "DRIP_WINDOW_START_HOUR": config.drip_window.start_hour,
        "DRIP_WINDOW_END_HOUR": config.drip_window.end_hour,
        "PAYDAY_PREMIUM_BOOST": config.payday.premium_boost,
        "PAYDAY_PREMIUM_PENALTY": config.payday.premium_penalty,
        "ROTATION_ORDER": list(config.content_types.rotation_order),
        "PREMIUM_CONTENT_TYPES": set(config.content_types.premium),
    }

    return mapping.get(attr)


# Backward compatibility - these are evaluated lazily on first access
class _LegacyConstants:
    """Lazy loader for legacy constants."""

    def __getattr__(self, name: str) -> Any:
        value = _get_lazy_constant(name)
        if value is not None:
            return value
        raise AttributeError(f"module has no attribute '{name}'")


# Create module-level access for legacy constants
_legacy = _LegacyConstants()

# Export legacy constants (evaluated on first use)
MIN_PPV_SPACING_HOURS: int
RECOMMENDED_PPV_SPACING_HOURS: int
MIN_FRESHNESS_SCORE: float
FOLLOW_UP_MIN_MINUTES: int
FOLLOW_UP_MAX_MINUTES: int
DRIP_WINDOW_START_HOUR: int
DRIP_WINDOW_END_HOUR: int
PAYDAY_PREMIUM_BOOST: float
PAYDAY_PREMIUM_PENALTY: float
ROTATION_ORDER: list[str]
PREMIUM_CONTENT_TYPES: set[str]


def __getattr__(name: str) -> Any:
    """Module-level __getattr__ for lazy constant loading."""
    value = _get_lazy_constant(name)
    if value is not None:
        return value
    raise AttributeError(f"module 'config_loader' has no attribute '{name}'")


# =============================================================================
# CLI INTERFACE
# =============================================================================


def main() -> None:
    """CLI for inspecting configuration."""
    import argparse
    import json
    from dataclasses import asdict

    parser = argparse.ArgumentParser(
        description="EROS Configuration Loader - View and validate configuration"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config file (default: config/business_rules.yaml)",
    )
    parser.add_argument(
        "--section",
        choices=[
            "ppv", "freshness", "follow_up", "drip_window", "payday",
            "volume_tiers", "content_types", "validation", "spacing",
            "preview", "engagement", "weights", "all"
        ],
        default="all",
        help="Section to display (default: all)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "yaml", "table"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and report issues",
    )

    args = parser.parse_args()

    try:
        config = get_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    if args.validate:
        print("Configuration validated successfully!")
        print(f"Config path: {args.config or DEFAULT_CONFIG_PATH}")
        return

    # Get section data
    if args.section == "all":
        data = {
            "ppv": asdict(config.ppv),
            "freshness": asdict(config.freshness),
            "follow_up": asdict(config.follow_up),
            "drip_window": asdict(config.drip_window),
            "payday": asdict(config.payday),
            "volume_tiers": {
                "low": asdict(config.volume_tiers.low),
                "mid": asdict(config.volume_tiers.mid),
                "high": asdict(config.volume_tiers.high),
                "ultra": asdict(config.volume_tiers.ultra),
            },
            "content_types": asdict(config.content_types),
            "validation": asdict(config.validation),
            "spacing": asdict(config.spacing),
            "preview": asdict(config.preview),
            "engagement": asdict(config.engagement),
            "weights": asdict(config.weights),
        }
    else:
        section_obj = getattr(config, args.section)
        if args.section == "volume_tiers":
            data = {
                "low": asdict(section_obj.low),
                "mid": asdict(section_obj.mid),
                "high": asdict(section_obj.high),
                "ultra": asdict(section_obj.ultra),
            }
        else:
            data = asdict(section_obj)

    # Output
    if args.format == "json":
        print(json.dumps(data, indent=2))
    elif args.format == "yaml":
        print(yaml.dump(data, default_flow_style=False))
    else:  # table
        def print_section(name: str, section_data: dict[str, Any], indent: int = 0) -> None:
            prefix = "  " * indent
            print(f"{prefix}{name}:")
            for key, value in section_data.items():
                if isinstance(value, dict):
                    print_section(key, value, indent + 1)
                else:
                    print(f"{prefix}  {key}: {value}")

        if isinstance(data, dict) and args.section == "all":
            for section_name, section_data in data.items():
                print_section(section_name, section_data)
                print()
        else:
            print_section(args.section, data)


if __name__ == "__main__":
    main()
