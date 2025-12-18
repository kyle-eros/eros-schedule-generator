"""
Volume tier configuration constants.

Defines tier-based volume configurations, fan count thresholds,
and performance-related threshold constants for dynamic volume calculation.

This module now loads configuration from algorithm_config.yaml while
maintaining backwards compatibility with existing code that imports
the constants directly.

Usage:
    # Direct import (backwards compatible)
    from python.volume.tier_config import TIER_CONFIGS, VOLUME_BOUNDS

    # Using config loader (recommended for new code)
    from python.volume.config_loader import get_config
    config = get_config()
    bounds = config.bounds
"""

from typing import Dict, Tuple

from python.models.volume import VolumeTier

# =============================================================================
# Lazy Configuration Loading
# =============================================================================

# We use a lazy loading pattern to avoid circular imports and to allow
# the config to be loaded only when needed. The constants below are
# populated on first access.

_config_loaded = False


def _ensure_config_loaded() -> None:
    """Ensure configuration is loaded from YAML.

    This function is called lazily when any constant is accessed.
    It populates the module-level constants from the config loader.
    """
    global _config_loaded
    global TIER_CONFIGS, FAN_COUNT_THRESHOLDS, SATURATION_THRESHOLDS
    global OPPORTUNITY_THRESHOLDS, VOLUME_BOUNDS

    if _config_loaded:
        return

    try:
        from python.volume.config_loader import get_config

        config = get_config()

        # Load tier configs - need to convert string keys to VolumeTier enum
        tier_configs_raw = config.tier_configs
        TIER_CONFIGS = {
            VolumeTier[tier_name]: page_configs
            for tier_name, page_configs in tier_configs_raw.items()
        }

        # Load fan count thresholds
        fan_thresholds = config.fan_thresholds
        FAN_COUNT_THRESHOLDS = {
            tier: (cfg[0], float("inf") if cfg[1] is None else cfg[1])
            for tier, cfg in fan_thresholds.items()
        }

        # Load saturation thresholds
        sat = config.saturation_thresholds
        SATURATION_THRESHOLDS = {
            "low": sat.low,
            "medium": sat.medium,
            "high": sat.high,
        }

        # Load opportunity thresholds
        opp = config.opportunity_thresholds
        OPPORTUNITY_THRESHOLDS = {
            "low": opp.low,
            "medium": opp.medium,
            "high": opp.high,
        }

        # Load volume bounds
        bounds = config.bounds
        VOLUME_BOUNDS = {
            cat: (b.min_value, b.max_value) for cat, b in bounds.items()
        }

        _config_loaded = True

    except Exception:
        # Fallback to hardcoded defaults if config loading fails
        # This maintains backwards compatibility
        _load_hardcoded_defaults()
        _config_loaded = True


def _load_hardcoded_defaults() -> None:
    """Load hardcoded default values as fallback.

    This ensures the module works even if the config file is missing.
    """
    global TIER_CONFIGS, FAN_COUNT_THRESHOLDS, SATURATION_THRESHOLDS
    global OPPORTUNITY_THRESHOLDS, VOLUME_BOUNDS

    TIER_CONFIGS = {
        VolumeTier.LOW: {
            "paid": {"revenue": 3, "engagement": 3, "retention": 1},
            "free": {"revenue": 4, "engagement": 3, "retention": 1},
        },
        VolumeTier.MID: {
            "paid": {"revenue": 4, "engagement": 3, "retention": 2},
            "free": {"revenue": 5, "engagement": 3, "retention": 1},
        },
        VolumeTier.HIGH: {
            "paid": {"revenue": 5, "engagement": 4, "retention": 2},
            "free": {"revenue": 6, "engagement": 4, "retention": 2},
        },
        VolumeTier.ULTRA: {
            "paid": {"revenue": 6, "engagement": 5, "retention": 3},
            "free": {"revenue": 8, "engagement": 5, "retention": 2},
        },
    }

    FAN_COUNT_THRESHOLDS = {
        "LOW": (0, 999),
        "MID": (1000, 4999),
        "HIGH": (5000, 14999),
        "ULTRA": (15000, float("inf")),
    }

    SATURATION_THRESHOLDS = {
        "low": 30,
        "medium": 50,
        "high": 70,
    }

    OPPORTUNITY_THRESHOLDS = {
        "low": 30,
        "medium": 50,
        "high": 70,
    }

    VOLUME_BOUNDS = {
        "revenue": (1, 8),
        "engagement": (1, 6),
        "retention": (0, 4),
    }


# =============================================================================
# Module-level Constants (Lazy Loaded)
# =============================================================================

# These are placeholder values that get populated on first access
# via the _ensure_config_loaded() function.

# Tier-based configuration templates
# Maps volume tiers to page-type-specific category limits
TIER_CONFIGS: Dict[VolumeTier, Dict[str, Dict[str, int]]] = {}

# Fan count thresholds for tier classification
# Maps tier names to (min_fans, max_fans) tuples
FAN_COUNT_THRESHOLDS: Dict[str, Tuple[int, float]] = {}

# Saturation score thresholds (0-100 scale)
SATURATION_THRESHOLDS: Dict[str, int] = {}

# Opportunity score thresholds (0-100 scale)
OPPORTUNITY_THRESHOLDS: Dict[str, int] = {}

# Volume bounds per category (min, max)
VOLUME_BOUNDS: Dict[str, Tuple[int, int]] = {}


# =============================================================================
# Accessor Functions (Preferred API)
# =============================================================================


def get_tier_configs() -> Dict[VolumeTier, Dict[str, Dict[str, int]]]:
    """Get tier configurations.

    Returns:
        Dictionary mapping VolumeTier to page-type configurations.
    """
    _ensure_config_loaded()
    return TIER_CONFIGS


def get_fan_count_thresholds() -> Dict[str, Tuple[int, float]]:
    """Get fan count thresholds per tier.

    Returns:
        Dictionary mapping tier name to (min, max) tuple.
    """
    _ensure_config_loaded()
    return FAN_COUNT_THRESHOLDS


def get_saturation_thresholds() -> Dict[str, int]:
    """Get saturation score thresholds.

    Returns:
        Dictionary with low, medium, high thresholds.
    """
    _ensure_config_loaded()
    return SATURATION_THRESHOLDS


def get_opportunity_thresholds() -> Dict[str, int]:
    """Get opportunity score thresholds.

    Returns:
        Dictionary with low, medium, high thresholds.
    """
    _ensure_config_loaded()
    return OPPORTUNITY_THRESHOLDS


def get_volume_bounds() -> Dict[str, Tuple[int, int]]:
    """Get volume bounds per category.

    Returns:
        Dictionary mapping category to (min, max) bounds.
    """
    _ensure_config_loaded()
    return VOLUME_BOUNDS


# =============================================================================
# Module Initialization Hook
# =============================================================================

# Ensure config is loaded when module constants are accessed
# This is done via __getattr__ for Python 3.7+


def __getattr__(name: str):
    """Lazy load configuration on first attribute access.

    This hook is called when a module-level attribute is not found.
    We use it to trigger config loading when constants are accessed.
    """
    if name in (
        "TIER_CONFIGS",
        "FAN_COUNT_THRESHOLDS",
        "SATURATION_THRESHOLDS",
        "OPPORTUNITY_THRESHOLDS",
        "VOLUME_BOUNDS",
    ):
        _ensure_config_loaded()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Trigger immediate loading for backwards compatibility
# This ensures the constants are available as soon as the module is imported
_ensure_config_loaded()
