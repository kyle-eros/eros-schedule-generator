"""
Send Type Registry - Singleton configuration cache.

Provides centralized access to send type configuration loaded from the database.
Eliminates hardcoded taxonomy lists and provides consistent timing/caption
requirements across the application.
"""

import sqlite3
from typing import ClassVar, Any

from python.models.send_type import SendType, SendTypeConfig
from python.logging_config import get_logger

logger = get_logger(__name__)


class SendTypeRegistry:
    """Singleton registry for send type configuration.

    Loads send type data from the database once and caches it for fast
    runtime lookups. Provides methods to query send types by key, category,
    and other attributes.

    Usage:
        registry = SendTypeRegistry()
        registry.load_from_database(conn)
        ppv_config = registry.get("ppv_unlock")
        revenue_types = registry.get_by_category("revenue")
    """

    _instance: ClassVar["SendTypeRegistry | None"] = None
    _initialized: bool = False

    def __new__(cls) -> "SendTypeRegistry":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize registry storage (only once)."""
        if not self._initialized:
            self._types: dict[str, SendTypeConfig] = {}
            self._raw_types: dict[str, SendType] = {}
            self._by_category: dict[str, list[str]] = {
                "revenue": [],
                "engagement": [],
                "retention": [],
            }
            self._initialized = True

    def load_from_database(self, conn: sqlite3.Connection) -> None:
        """Load all send type configuration from database.

        Args:
            conn: SQLite database connection

        Raises:
            sqlite3.Error: If database query fails
        """
        logger.info("Loading send type registry from database")

        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                send_type_id,
                send_type_key,
                category,
                display_name,
                description,
                purpose,
                strategy,
                requires_media,
                requires_flyer,
                requires_price,
                requires_link,
                has_expiration,
                default_expiration_hours,
                can_have_followup,
                followup_delay_minutes,
                page_type_restriction,
                caption_length,
                emoji_recommendation,
                max_per_day,
                max_per_week,
                min_hours_between,
                sort_order,
                is_active
            FROM send_types
            WHERE is_active = 1
            ORDER BY category, sort_order
        """)

        rows = cursor.fetchall()
        logger.info(f"Loaded {len(rows)} active send types")

        for row in rows:
            # Create raw SendType model
            send_type = SendType(
                send_type_id=row[0],
                send_type_key=row[1],
                category=row[2],
                display_name=row[3],
                description=row[4],
                purpose=row[5],
                strategy=row[6],
                requires_media=row[7],
                requires_flyer=row[8],
                requires_price=row[9],
                requires_link=row[10],
                has_expiration=row[11],
                default_expiration_hours=row[12],
                can_have_followup=row[13],
                followup_delay_minutes=row[14],
                page_type_restriction=row[15],
                caption_length=row[16],
                emoji_recommendation=row[17],
                max_per_day=row[18],
                max_per_week=row[19],
                min_hours_between=row[20],
                sort_order=row[21],
                is_active=row[22],
            )

            # Create runtime config
            config = self._build_config(send_type)

            # Store both forms
            self._raw_types[send_type.send_type_key] = send_type
            self._types[send_type.send_type_key] = config
            self._by_category[send_type.category].append(send_type.send_type_key)

            logger.debug(
                f"Registered send type: {send_type.send_type_key} ({send_type.category})"
            )

    def _build_config(self, send_type: SendType) -> SendTypeConfig:
        """Build runtime configuration from database send type.

        Args:
            send_type: Raw send type from database

        Returns:
            Runtime-optimized configuration
        """
        # Build timing preferences
        timing_preferences = self._build_timing_preferences(send_type)

        # Build caption requirements
        caption_requirements = self._build_caption_requirements(send_type)

        return SendTypeConfig(
            key=send_type.send_type_key,
            name=send_type.display_name,
            category=send_type.category,
            page_type=send_type.page_type_restriction,
            timing_preferences=timing_preferences,
            caption_requirements=caption_requirements,
            max_per_day=send_type.max_per_day,
            max_per_week=send_type.max_per_week,
            requires_media=bool(send_type.requires_media),
            requires_price=bool(send_type.requires_price),
            can_have_followup=bool(send_type.can_have_followup),
            followup_delay_minutes=send_type.followup_delay_minutes,
        )

    def _build_timing_preferences(self, send_type: SendType) -> dict[str, Any]:
        """Build timing preferences from send type data.

        Args:
            send_type: Raw send type

        Returns:
            Timing configuration dictionary
        """
        # Timing preferences are defined by category with type-specific overrides.
        # Category defaults provide sensible timing for revenue (evening peaks),
        # engagement (spread throughout day), and retention (business hours).
        # Creator-specific optimal times come from get_best_timing() historical analysis.
        preferences: dict[str, Any] = {
            "min_spacing": send_type.min_hours_between * 60,  # Convert to minutes
            "boost": 1.0,
        }

        # Category-specific defaults
        if send_type.category == "revenue":
            preferences["preferred_hours"] = [19, 21]
            preferences["preferred_days"] = [4, 5, 6]  # Fri, Sat, Sun
            preferences["avoid_hours"] = [3, 4, 5, 6, 7]
            preferences["boost"] = 1.2
        elif send_type.category == "engagement":
            preferences["preferred_hours"] = [10, 14, 19]
            preferences["preferred_days"] = [0, 1, 2, 3, 4, 5, 6]  # All days
            preferences["avoid_hours"] = [3, 4, 5, 6, 7]
            preferences["boost"] = 1.0
        elif send_type.category == "retention":
            preferences["preferred_hours"] = [10, 14, 19]
            preferences["preferred_days"] = [0, 1, 2, 3, 4, 5, 6]  # All days
            preferences["avoid_hours"] = [3, 4, 5, 6, 7, 22, 23, 0, 1, 2]
            preferences["boost"] = 1.0

        # Type-specific overrides
        if send_type.send_type_key == "ppv_unlock":
            preferences["preferred_hours"] = [19, 21]
            preferences["boost"] = 1.3
        elif send_type.send_type_key == "vip_program":
            preferences["min_spacing"] = 120
            preferences["boost"] = 1.2
        elif send_type.send_type_key == "ppv_followup":
            preferences["offset_from_parent"] = send_type.followup_delay_minutes

        return preferences

    def _build_caption_requirements(self, send_type: SendType) -> list[str]:
        """Build caption requirements list from send type data.

        Args:
            send_type: Raw send type

        Returns:
            List of requirement strings
        """
        requirements = []

        if send_type.caption_length:
            requirements.append(f"length_{send_type.caption_length}")

        if send_type.emoji_recommendation:
            requirements.append(f"emoji_{send_type.emoji_recommendation}")

        if send_type.requires_media:
            requirements.append("requires_media")

        if send_type.requires_price:
            requirements.append("requires_price")

        if send_type.requires_link:
            requirements.append("requires_link")

        return requirements

    def get(self, key: str) -> SendTypeConfig:
        """Get send type configuration by key.

        Args:
            key: Send type key (e.g., 'ppv_unlock')

        Returns:
            Send type configuration

        Raises:
            KeyError: If send type not found
        """
        if key not in self._types:
            raise KeyError(f"Send type not found: {key}")
        return self._types[key]

    def get_raw(self, key: str) -> SendType:
        """Get raw send type model by key.

        Args:
            key: Send type key

        Returns:
            Raw send type from database

        Raises:
            KeyError: If send type not found
        """
        if key not in self._raw_types:
            raise KeyError(f"Send type not found: {key}")
        return self._raw_types[key]

    def get_by_category(self, category: str) -> list[SendTypeConfig]:
        """Get all send types in a category.

        Args:
            category: 'revenue', 'engagement', or 'retention'

        Returns:
            List of send type configurations

        Raises:
            ValueError: If invalid category
        """
        if category not in self._by_category:
            raise ValueError(f"Invalid category: {category}")

        return [self._types[key] for key in self._by_category[category]]

    def get_keys_by_category(self, category: str) -> list[str]:
        """Get send type keys for a category.

        Args:
            category: 'revenue', 'engagement', or 'retention'

        Returns:
            List of send type keys

        Raises:
            ValueError: If invalid category
        """
        if category not in self._by_category:
            raise ValueError(f"Invalid category: {category}")

        return self._by_category[category].copy()

    def get_timing_preferences(self, key: str) -> dict[str, Any]:
        """Get timing preferences for a send type.

        Args:
            key: Send type key

        Returns:
            Timing preferences dictionary

        Raises:
            KeyError: If send type not found
        """
        config = self.get(key)
        return config.timing_preferences

    def get_all_keys(self) -> list[str]:
        """Get all send type keys.

        Returns:
            List of all send type keys
        """
        return list(self._types.keys())

    def is_valid_key(self, key: str) -> bool:
        """Check if send type key is valid.

        Args:
            key: Send type key to check

        Returns:
            True if key exists in registry
        """
        return key in self._types

    def get_page_type_compatible(self, page_type: str) -> list[SendTypeConfig]:
        """Get send types compatible with a page type.

        Args:
            page_type: 'paid' or 'free'

        Returns:
            List of compatible send type configurations
        """
        compatible = []
        for config in self._types.values():
            if config.page_type == "both" or config.page_type == page_type:
                compatible.append(config)
        return compatible

    def clear(self) -> None:
        """Clear all cached data (for testing)."""
        self._types.clear()
        self._raw_types.clear()
        for category in self._by_category:
            self._by_category[category].clear()
        logger.info("Send type registry cleared")

    def __len__(self) -> int:
        """Get number of registered send types."""
        return len(self._types)

    def __contains__(self, key: str) -> bool:
        """Check if send type key exists."""
        return key in self._types

    def __repr__(self) -> str:
        """String representation."""
        return f"SendTypeRegistry({len(self._types)} types loaded)"
