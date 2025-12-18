"""
Settings manager for EROS Schedule Generator.

Provides centralized configuration management with YAML-based defaults
and environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    import json  # Fallback to JSON if YAML not available

from python.logging_config import get_logger

logger = get_logger(__name__)


class Settings:
    """Singleton settings manager.

    Loads configuration from YAML file with environment variable overrides.
    Falls back to sensible defaults if configuration file is missing.

    Usage:
        settings = Settings()
        weights = settings.scoring_weights
        prime_hours = settings.timing_config["prime_hours"]
    """

    _instance = None
    _initialized: bool = False

    def __new__(cls) -> "Settings":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize settings manager (only once)."""
        if not self._initialized:
            self._config: dict[str, Any] = {}
            self._load()
            self._initialized = True

    def _load(self) -> None:
        """Load configuration from file or use defaults."""
        config_path = self._get_config_path()

        if config_path.exists():
            try:
                self._config = self._load_from_file(config_path)
                logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}, using defaults")
                self._config = self._defaults()
        else:
            logger.info("Config file not found, using defaults")
            self._config = self._defaults()

        # Apply environment variable overrides
        self._apply_env_overrides()

    def _get_config_path(self) -> Path:
        """Get configuration file path.

        Checks environment variable first, then default location.

        Returns:
            Path to configuration file
        """
        # Check environment variable
        env_path = os.getenv("EROS_CONFIG_PATH")
        if env_path:
            return Path(env_path)

        # Default location
        return Path(__file__).parent / "scheduling.yaml"

    def _load_from_file(self, path: Path) -> dict[str, Any]:
        """Load configuration from YAML or JSON file.

        Args:
            path: Path to configuration file

        Returns:
            Configuration dictionary
        """
        with open(path, "r") as f:
            if YAML_AVAILABLE and path.suffix in (".yaml", ".yml"):
                result = yaml.safe_load(f)
                return dict(result) if result else {}
            else:
                # Fallback to JSON
                result = json.load(f)
                return dict(result) if result else {}

    def _defaults(self) -> dict[str, Any]:
        """Return default configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "scoring": {
                "weights": {
                    "performance": 0.35,
                    "freshness": 0.25,
                    "type_priority": 0.20,
                    "persona_match": 0.10,
                    "diversity": 0.10,
                },
                "thresholds": {
                    "min_performance": 40,
                    "min_freshness": 30,
                    "reuse_days": 30,
                },
            },
            "timing": {
                "prime_hours": [10, 14, 19, 21],
                "prime_days": [4, 5, 6],  # Friday, Saturday, Sunday
                "avoid_hours": [3, 4, 5, 6, 7],
                "min_spacing_minutes": 45,
                "max_per_hour": 2,
            },
            "volume": {
                "tiers": {
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
                "daily_maximums": {
                    "revenue": 8,
                    "engagement": 6,
                    "retention": 4,
                },
                "weekly_maximums": {
                    "revenue": 45,
                    "engagement": 35,
                    "retention": 20,
                },
            },
            "allocation": {
                "day_adjustments": {
                    "0": -1,  # Monday - slower start
                    "1": 0,   # Tuesday - normal
                    "2": 0,   # Wednesday - normal
                    "3": 0,   # Thursday - normal
                    "4": 1,   # Friday - peak revenue day
                    "5": 1,   # Saturday - high activity
                    "6": 0,   # Sunday - normal
                },
            },
            "followup": {
                "max_per_day": 4,
                "min_delay_minutes": 20,
                "enabled_types": ["ppv_video", "ppv_message", "bundle"],  # DEPRECATED: ppv_video→ppv_unlock, ppv_message→ppv_unlock, remove after 2025-01-16
            },
        }

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        # Scoring weight overrides
        if env_val := os.getenv("EROS_WEIGHT_PERFORMANCE"):
            self._config["scoring"]["weights"]["performance"] = float(env_val)
        if env_val := os.getenv("EROS_WEIGHT_FRESHNESS"):
            self._config["scoring"]["weights"]["freshness"] = float(env_val)
        if env_val := os.getenv("EROS_WEIGHT_TYPE_PRIORITY"):
            self._config["scoring"]["weights"]["type_priority"] = float(env_val)

        # Timing overrides
        if env_val := os.getenv("EROS_MIN_SPACING_MINUTES"):
            self._config["timing"]["min_spacing_minutes"] = int(env_val)
        if env_val := os.getenv("EROS_MAX_PER_HOUR"):
            self._config["timing"]["max_per_hour"] = int(env_val)

        # Threshold overrides
        if env_val := os.getenv("EROS_MIN_PERFORMANCE"):
            self._config["scoring"]["thresholds"]["min_performance"] = int(env_val)
        if env_val := os.getenv("EROS_REUSE_DAYS"):
            self._config["scoring"]["thresholds"]["reuse_days"] = int(env_val)

    @property
    def scoring_weights(self) -> dict[str, float]:
        """Get scoring weights configuration.

        Returns:
            Dictionary of weight names to float values (must sum to 1.0)
        """
        result: dict[str, float] = self._config["scoring"]["weights"]
        return result

    @property
    def scoring_thresholds(self) -> dict[str, int]:
        """Get scoring thresholds configuration.

        Returns:
            Dictionary of threshold names to integer values
        """
        result: dict[str, int] = self._config["scoring"]["thresholds"]
        return result

    @property
    def timing_config(self) -> dict[str, Any]:
        """Get timing configuration.

        Returns:
            Dictionary with prime_hours, prime_days, avoid_hours, etc.
        """
        result: dict[str, Any] = self._config["timing"]
        return result

    @property
    def volume_tiers(self) -> dict[str, dict[str, dict[str, int]]]:
        """Get volume tier configurations.

        Returns:
            Nested dictionary: tier -> page_type -> category -> count
        """
        result: dict[str, dict[str, dict[str, int]]] = self._config["volume"]["tiers"]
        return result

    @property
    def volume_daily_maximums(self) -> dict[str, int]:
        """Get daily maximum sends by category.

        Returns:
            Dictionary mapping category to maximum daily count
        """
        result: dict[str, int] = self._config["volume"]["daily_maximums"]
        return result

    @property
    def volume_weekly_maximums(self) -> dict[str, int]:
        """Get weekly maximum sends by category.

        Returns:
            Dictionary mapping category to maximum weekly count
        """
        result: dict[str, int] = self._config["volume"]["weekly_maximums"]
        return result

    @property
    def day_adjustments(self) -> dict[str, int]:
        """Get day-of-week volume adjustments.

        Returns:
            Dictionary mapping day (0-6) to adjustment (-1, 0, +1)
        """
        result: dict[str, int] = self._config["allocation"]["day_adjustments"]
        return result

    @property
    def followup_config(self) -> dict[str, Any]:
        """Get followup generation configuration.

        Returns:
            Dictionary with max_per_day, min_delay_minutes, enabled_types
        """
        result: dict[str, Any] = self._config["followup"]
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'scoring.weights.performance')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        parts = key.split(".")
        value = self._config

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def reload(self) -> None:
        """Reload configuration from file (for testing)."""
        self._load()
        logger.info("Configuration reloaded")

    def __repr__(self) -> str:
        """String representation."""
        return f"Settings(loaded={bool(self._config)})"
