#!/usr/bin/env python3
"""
Content Type Registry - Single source of truth for schedulable content type metadata.

This module provides a centralized registry of all content types that can be scheduled
in the EROS Schedule Generator. Each content type has defined metadata including:
- Channel (mass_message, feed, direct, poll, gamification)
- Page type restrictions (paid, free, both)
- Priority tier for slot allocation
- Spacing and volume constraints
- Follow-up capabilities
- Theme guidance for slots without captions

Usage:
    from content_type_registry import REGISTRY, get_registry, SchedulableContentType

    # Get a specific content type
    ppv = REGISTRY.get("ppv")
    logger.info(f"PPV min spacing: {ppv.min_spacing_hours} hours")

    # Get all types for a page type
    paid_types = REGISTRY.get_types_for_page("paid")

    # Validate content type for page
    if REGISTRY.validate_for_page("vip_post", "free"):
        logger.warning("Invalid - VIP posts are paid-only")

Content Type Tiers:
    Tier 1 - Direct Revenue: ppv, ppv_follow_up, bundle, flash_bundle, snapchat_bundle
    Tier 2 - Feed/Wall: vip_post, first_to_tip, link_drop, normal_post_bump, etc.
    Tier 3 - Engagement: dm_farm, like_farm, text_only_bump
    Tier 4 - Retention: renew_on_mm, expired_subscriber
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

# Configure module logger
logger = logging.getLogger(__name__)

__all__ = [
    "SchedulableContentType",
    "ContentTypeRegistry",
    "REGISTRY",
    "get_registry",
    "Channel",
    "PageTypeFilter",
    "normalize_content_type",
    "get_display_name",
    "get_pricing_category",
    "get_item_type_for_content_type",
    "load_content_type_mapping",
]


# =============================================================================
# TYPE ALIASES
# =============================================================================

Channel = Literal["mass_message", "feed", "direct", "poll", "gamification"]
PageTypeFilter = Literal["paid", "free", "both"]


# =============================================================================
# CONTENT TYPE MAPPING (Lazy-loaded from YAML config)
# =============================================================================

# Path to the content type mapping configuration file
_MAPPING_FILE = Path(__file__).parent.parent / "config" / "content_type_mapping.yaml"

# Module-level cache for mapping data (lazy-loaded)
_content_type_mapping: dict[str, str] = {}
_display_names: dict[str, str] = {}
_pricing_categories: dict[str, str | None] = {}
_mapping_loaded: bool = False

# Hardcoded fallback mapping if YAML file is missing
_FALLBACK_MAPPING: dict[str, str] = {
    "bundle_offer": "bundle",
    "flash_sale": "flash_bundle",
    "shower_bath": "solo",
    "exclusive_content": "ppv",
    "tip_request": "first_to_tip",
    "blowjob_dildo": "solo",
    "deepthroat_dildo": "solo",
    "tits_play": "solo",
    "pussy_play": "solo",
    "toy_play": "solo",
    "boy_girl": "bg",
    "girl_girl": "bg",
    "dick_rating": "dick_rating",
    "joi": "custom",
    "gfe": "custom",
    "default": "ppv",
}

_FALLBACK_DISPLAY_NAMES: dict[str, str] = {
    "ppv": "PPV",
    "ppv_follow_up": "PPV Follow-up",
    "bundle": "Bundle",
    "flash_bundle": "Flash Bundle",
    "solo": "Solo",
    "sextape": "Sextape",
    "bg": "B/G",
    "custom": "Custom",
    "dick_rating": "Dick Rating",
    "first_to_tip": "First to Tip",
    "dm_farm": "DM Farm",
    "normal_post_bump": "Post Bump",
}

# Channel to item_type mapping for deriving schedule item types from registry channels
_CHANNEL_TO_ITEM_TYPE: dict[str, str] = {
    "mass_message": "ppv",
    "feed": "wall_post",
    "direct": "ppv",
    "poll": "poll",
    "gamification": "game_wheel",
}


def load_content_type_mapping() -> None:
    """
    Load content type mapping from YAML configuration file.

    This function loads the mapping lazily on first use and caches the results.
    If the YAML file is missing or invalid, falls back to hardcoded defaults.
    """
    global _content_type_mapping, _display_names, _pricing_categories, _mapping_loaded

    if _mapping_loaded:
        return

    if _MAPPING_FILE.exists():
        try:
            with open(_MAPPING_FILE) as f:
                data = yaml.safe_load(f)

            _content_type_mapping = data.get("content_type_mapping", {})
            _display_names = data.get("display_names", {})
            _pricing_categories = data.get("pricing_categories", {})
            _mapping_loaded = True
            logger.debug(
                f"Loaded content type mapping from {_MAPPING_FILE}: "
                f"{len(_content_type_mapping)} mappings, {len(_display_names)} display names"
            )
        except (yaml.YAMLError, OSError) as e:
            logger.warning(f"Failed to load content type mapping from {_MAPPING_FILE}: {e}")
            logger.info("Using fallback hardcoded mapping")
            _content_type_mapping = _FALLBACK_MAPPING.copy()
            _display_names = _FALLBACK_DISPLAY_NAMES.copy()
            _pricing_categories = {}
            _mapping_loaded = True
    else:
        logger.info(f"Content type mapping file not found: {_MAPPING_FILE}")
        logger.info("Using fallback hardcoded mapping")
        _content_type_mapping = _FALLBACK_MAPPING.copy()
        _display_names = _FALLBACK_DISPLAY_NAMES.copy()
        _pricing_categories = {}
        _mapping_loaded = True


def normalize_content_type(db_type: str | None) -> str:
    """
    Normalize a database content type to a registry type.

    This function maps various database content type names (e.g., 'bundle_offer',
    'shower_bath', 'exclusive_content') to their normalized registry type IDs
    (e.g., 'bundle', 'solo', 'ppv').

    Args:
        db_type: Content type name from database (can be None)

    Returns:
        Normalized registry type name (e.g., 'ppv', 'bundle', 'solo')

    Example:
        >>> normalize_content_type("bundle_offer")
        'bundle'
        >>> normalize_content_type("shower_bath")
        'solo'
        >>> normalize_content_type(None)
        'ppv'
    """
    if not _mapping_loaded:
        load_content_type_mapping()

    if not db_type:
        return _content_type_mapping.get("default", "ppv")

    # Normalize to lowercase for matching
    db_type_lower = db_type.lower().strip()

    # Direct lookup
    if db_type_lower in _content_type_mapping:
        return _content_type_mapping[db_type_lower]

    # Check for partial matches (contains key terms)
    if "bundle" in db_type_lower or "flash" in db_type_lower:
        return "bundle"
    if "solo" in db_type_lower or "selfie" in db_type_lower:
        return "solo"
    if "sextape" in db_type_lower or "video" in db_type_lower:
        return "sextape"
    if "b/g" in db_type_lower or "bg" in db_type_lower or "couple" in db_type_lower:
        return "bg"
    if "custom" in db_type_lower or "personalized" in db_type_lower:
        return "custom"
    if "dick" in db_type_lower or "rating" in db_type_lower:
        return "dick_rating"

    # Return default
    return _content_type_mapping.get("default", "ppv")


def get_display_name(registry_type: str | None) -> str:
    """
    Get the human-readable display name for a registry content type.

    Args:
        registry_type: Normalized registry type ID (e.g., 'ppv', 'bundle')

    Returns:
        Human-readable display name (e.g., 'PPV', 'Bundle')

    Example:
        >>> get_display_name("ppv")
        'PPV'
        >>> get_display_name("flash_bundle")
        'Flash Bundle'
    """
    if not _mapping_loaded:
        load_content_type_mapping()

    if not registry_type:
        return "PPV"

    return _display_names.get(registry_type, registry_type.replace("_", " ").title())


def get_pricing_category(registry_type: str | None) -> str:
    """
    Get the pricing category for a registry content type.

    This maps registry types to their pricing categories for price calculation.
    Pricing categories align with CLAUDE.md 2025 Market Rates.

    Args:
        registry_type: Normalized registry type ID

    Returns:
        Pricing category name (solo, bundle, sextape, bg, custom, dick_rating)
        or 'default' if no specific category applies

    Example:
        >>> get_pricing_category("ppv")
        'solo'
        >>> get_pricing_category("flash_bundle")
        'bundle'
    """
    if not _mapping_loaded:
        load_content_type_mapping()

    if not registry_type:
        return "default"

    # Check explicit pricing category mapping
    if registry_type in _pricing_categories:
        category = _pricing_categories[registry_type]
        return category if category else "default"

    # If registry type is already a pricing category, return it
    if registry_type in ("solo", "bundle", "sextape", "bg", "custom", "dick_rating"):
        return registry_type

    return "default"


def get_item_type_for_content_type(content_type_name: str | None) -> str:
    """
    Derive the schedule item_type from a content type's registry channel.

    This function maps the content type registry's `channel` field to the
    appropriate `item_type` for ScheduleItem creation. It ensures that
    content types like tip_request (first_to_tip) with channel="feed"
    are correctly classified as wall_post instead of ppv.

    Args:
        content_type_name: Content type name (e.g., 'first_to_tip', 'ppv').
            Can be None, in which case defaults to "ppv".

    Returns:
        The appropriate item_type string:
        - "ppv" for mass_message channel (default)
        - "wall_post" for feed channel
        - "poll" for poll channel
        - "game_wheel" for gamification channel
        - "ppv" for direct channel (DM-based content)
        - "ppv" for unknown content types (safe default)

    Example:
        >>> get_item_type_for_content_type("first_to_tip")
        'wall_post'
        >>> get_item_type_for_content_type("ppv")
        'ppv'
        >>> get_item_type_for_content_type(None)
        'ppv'
    """
    # Default for None or empty
    if not content_type_name:
        return "ppv"

    # Ensure mapping is loaded
    if not _mapping_loaded:
        load_content_type_mapping()

    try:
        type_id = content_type_name.lower().strip()

        # First, try direct lookup in the global REGISTRY
        # (REGISTRY is defined later in this module, imported at module level)
        if type_id in REGISTRY._types:
            content_type = REGISTRY.get(type_id)
            return _CHANNEL_TO_ITEM_TYPE.get(content_type.channel, "ppv")

        # Try normalizing from database type name
        normalized = normalize_content_type(type_id)
        if normalized in REGISTRY._types:
            content_type = REGISTRY.get(normalized)
            return _CHANNEL_TO_ITEM_TYPE.get(content_type.channel, "ppv")

    except (KeyError, ValueError, AttributeError):
        pass

    # Safe default
    return "ppv"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class SchedulableContentType:
    """
    Represents a schedulable content type with all metadata.

    This dataclass defines the complete specification for a content type
    that can be scheduled in the EROS system. It includes constraints,
    channel information, and guidance for schedule generation.

    Attributes:
        type_id: Unique identifier (e.g., "ppv", "vip_post", "dm_farm")
        name: Human-readable display name
        channel: Distribution channel for the content
        page_type_filter: Which page types can use this content type
        priority_tier: Priority for slot allocation (1=highest, 5=lowest)
        min_spacing_hours: Minimum hours between sends of this type
        max_daily: Maximum sends per day
        max_weekly: Maximum sends per week
        requires_flyer: Whether content needs attached media/flyer
        has_follow_up: Whether content can have a follow-up bump
        description: Short description for template guidance
        theme_guidance: Guidance text for slots without captions
    """

    type_id: str
    name: str
    channel: Channel
    page_type_filter: PageTypeFilter
    priority_tier: int
    min_spacing_hours: float
    max_daily: int
    max_weekly: int
    requires_flyer: bool = True
    has_follow_up: bool = False
    description: str = ""
    theme_guidance: str = ""

    def __post_init__(self) -> None:
        """Validate content type parameters after initialization."""
        if self.priority_tier < 1 or self.priority_tier > 5:
            raise ValueError(f"priority_tier must be 1-5, got {self.priority_tier}")
        if self.min_spacing_hours < 0:
            raise ValueError(f"min_spacing_hours must be >= 0, got {self.min_spacing_hours}")
        if self.max_daily < 0:
            raise ValueError(f"max_daily must be >= 0, got {self.max_daily}")
        if self.max_weekly < 0:
            raise ValueError(f"max_weekly must be >= 0, got {self.max_weekly}")
        if self.max_weekly < self.max_daily:
            raise ValueError(
                f"max_weekly ({self.max_weekly}) cannot be less than max_daily ({self.max_daily})"
            )

    def is_valid_for_page(self, page_type: str) -> bool:
        """
        Check if this content type is valid for a given page type.

        Args:
            page_type: The page type to check ("paid" or "free")

        Returns:
            True if content type can be used on this page type
        """
        if self.page_type_filter == "both":
            return True
        return self.page_type_filter == page_type.lower()


# =============================================================================
# CONTENT TYPE REGISTRY CLASS
# =============================================================================


class ContentTypeRegistry:
    """
    Registry for managing schedulable content types.

    This class provides a centralized store for all content type definitions
    with methods to query, filter, and validate content types.

    Example:
        >>> registry = ContentTypeRegistry()
        >>> registry.register(ppv_type)
        >>> ppv = registry.get("ppv")
        >>> paid_types = registry.get_types_for_page("paid")
    """

    def __init__(self) -> None:
        """Initialize an empty content type registry."""
        self._types: dict[str, SchedulableContentType] = {}

    def register(self, content_type: SchedulableContentType) -> None:
        """
        Register a content type in the registry.

        Args:
            content_type: The content type to register

        Raises:
            ValueError: If a content type with the same ID already exists
        """
        if content_type.type_id in self._types:
            raise ValueError(f"Content type '{content_type.type_id}' is already registered")
        self._types[content_type.type_id] = content_type

    def get(self, type_id: str) -> SchedulableContentType:
        """
        Get a content type by its ID.

        Args:
            type_id: The unique identifier of the content type

        Returns:
            The SchedulableContentType with the given ID

        Raises:
            KeyError: If no content type with the given ID exists
        """
        if type_id not in self._types:
            raise KeyError(f"Content type '{type_id}' not found in registry")
        return self._types[type_id]

    def get_all(self) -> list[SchedulableContentType]:
        """
        Get all registered content types.

        Returns:
            List of all SchedulableContentType objects sorted by priority_tier
        """
        return sorted(self._types.values(), key=lambda ct: (ct.priority_tier, ct.type_id))

    def get_types_for_page(self, page_type: str) -> list[SchedulableContentType]:
        """
        Get content types valid for a specific page type.

        Args:
            page_type: The page type to filter by ("paid" or "free")

        Returns:
            List of content types valid for the given page type
        """
        page_type = page_type.lower()
        return [ct for ct in self.get_all() if ct.is_valid_for_page(page_type)]

    def get_types_by_channel(self, channel: str) -> list[SchedulableContentType]:
        """
        Get content types for a specific channel.

        Args:
            channel: The channel to filter by (e.g., "mass_message", "feed")

        Returns:
            List of content types for the given channel
        """
        channel = channel.lower()
        return [ct for ct in self.get_all() if ct.channel == channel]

    def get_types_by_priority(self, tier: int) -> list[SchedulableContentType]:
        """
        Get content types with a specific priority tier.

        Args:
            tier: The priority tier to filter by (1-5)

        Returns:
            List of content types with the given priority tier
        """
        return [ct for ct in self.get_all() if ct.priority_tier == tier]

    def validate_for_page(self, type_id: str, page_type: str) -> bool:
        """
        Check if a content type is valid for a page type.

        Args:
            type_id: The content type ID to check
            page_type: The page type to validate against

        Returns:
            True if the content type is valid for the page type

        Raises:
            KeyError: If the content type ID is not found
        """
        content_type = self.get(type_id)
        return content_type.is_valid_for_page(page_type)

    def list_ids(self) -> list[str]:
        """
        Get a list of all registered content type IDs.

        Returns:
            List of content type IDs sorted alphabetically
        """
        return sorted(self._types.keys())

    def __len__(self) -> int:
        """Return the number of registered content types."""
        return len(self._types)

    def __contains__(self, type_id: str) -> bool:
        """Check if a content type ID is registered."""
        return type_id in self._types


# =============================================================================
# PRE-REGISTERED CONTENT TYPES
# =============================================================================

# Create the singleton registry
REGISTRY = ContentTypeRegistry()


# -----------------------------------------------------------------------------
# TIER 1 - DIRECT REVENUE (priority=1)
# -----------------------------------------------------------------------------

REGISTRY.register(
    SchedulableContentType(
        type_id="ppv",
        name="PPV Message",
        channel="mass_message",
        page_type_filter="both",
        priority_tier=1,
        min_spacing_hours=3.0,
        max_daily=5,
        max_weekly=35,
        requires_flyer=True,
        has_follow_up=True,
        description="Pay-per-view mass message with locked content",
        theme_guidance="High-value content tease, create urgency and desire",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="ppv_follow_up",
        name="PPV Follow-up",
        channel="mass_message",
        page_type_filter="both",
        priority_tier=1,
        min_spacing_hours=0.25,  # 15 minutes after PPV
        max_daily=5,  # 1 per PPV
        max_weekly=35,
        requires_flyer=False,
        has_follow_up=False,
        description="Bump message sent 15-45 min after PPV",
        theme_guidance="Reminder about locked content, create FOMO",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="bundle",
        name="Content Bundle",
        channel="mass_message",
        page_type_filter="both",
        priority_tier=1,
        min_spacing_hours=24.0,
        max_daily=1,
        max_weekly=3,
        requires_flyer=True,
        has_follow_up=True,
        description="Multi-piece content bundle at discount",
        theme_guidance="Value-focused bundle promotion, emphasize savings",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="flash_bundle",
        name="Flash Bundle Sale",
        channel="mass_message",
        page_type_filter="both",
        priority_tier=1,
        min_spacing_hours=48.0,
        max_daily=1,
        max_weekly=2,
        requires_flyer=True,
        has_follow_up=True,
        description="Limited-time bundle with urgency",
        theme_guidance="Time-limited offer, strong urgency and scarcity",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="snapchat_bundle",
        name="Snapchat Bundle",
        channel="mass_message",
        page_type_filter="both",
        priority_tier=1,
        min_spacing_hours=48.0,
        max_daily=1,
        max_weekly=2,
        requires_flyer=True,
        has_follow_up=True,
        description="Premium Snapchat access bundle",
        theme_guidance="Exclusive Snapchat access, behind-the-scenes content",
    )
)


# -----------------------------------------------------------------------------
# TIER 2 - FEED/WALL (priority=2)
# -----------------------------------------------------------------------------

REGISTRY.register(
    SchedulableContentType(
        type_id="vip_post",
        name="VIP Post",
        channel="feed",
        page_type_filter="paid",  # PAID ONLY
        priority_tier=2,
        min_spacing_hours=24.0,
        max_daily=1,
        max_weekly=3,
        requires_flyer=True,
        has_follow_up=False,
        description="Exclusive VIP tier content post",
        theme_guidance="Exclusive tier promotion, emphasize $200+ VIP value and premium benefits",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="first_to_tip",
        name="First to Tip",
        channel="feed",
        page_type_filter="both",
        priority_tier=2,
        min_spacing_hours=12.0,
        max_daily=1,
        max_weekly=3,
        requires_flyer=True,
        has_follow_up=False,
        description="Campaign with specific tip goal",
        theme_guidance="Campaign with specific tip goal, urgency-driven competition",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="link_drop",
        name="Link Drop",
        channel="feed",
        page_type_filter="both",
        priority_tier=2,
        min_spacing_hours=4.0,
        max_daily=3,
        max_weekly=21,
        requires_flyer=False,
        has_follow_up=False,
        description="Link to external content or promotion",
        theme_guidance="Casual link share, drive traffic to other platforms",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="normal_post_bump",
        name="Normal Post Bump",
        channel="feed",
        page_type_filter="both",
        priority_tier=2,
        min_spacing_hours=2.0,
        max_daily=4,
        max_weekly=28,
        requires_flyer=True,
        has_follow_up=False,
        description="Regular feed post with engagement focus",
        theme_guidance="Casual engagement post, encourage likes and comments",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="renew_on_post",
        name="Renew On Post",
        channel="feed",
        page_type_filter="paid",  # PAID ONLY
        priority_tier=2,
        min_spacing_hours=24.0,
        max_daily=1,
        max_weekly=2,
        requires_flyer=True,
        has_follow_up=False,
        description="Subscription renewal reminder post",
        theme_guidance="Subscription value reminder, upcoming content tease",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="game_post",
        name="Game Post",
        channel="feed",
        page_type_filter="both",
        priority_tier=2,
        min_spacing_hours=168.0,  # 7 days
        max_daily=1,
        max_weekly=1,
        requires_flyer=True,
        has_follow_up=False,
        description="Interactive game or contest post",
        theme_guidance="Spin the wheel, chance to win prizes, gamification and fun",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="flyer_gif_bump",
        name="Flyer/GIF Bump",
        channel="feed",
        page_type_filter="both",
        priority_tier=2,
        min_spacing_hours=4.0,
        max_daily=2,
        max_weekly=14,
        requires_flyer=True,
        has_follow_up=False,
        description="Visual bump with flyer or GIF",
        theme_guidance="Eye-catching visual content, quick engagement grab",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="descriptive_bump",
        name="Descriptive Bump",
        channel="feed",
        page_type_filter="both",
        priority_tier=2,
        min_spacing_hours=4.0,
        max_daily=2,
        max_weekly=14,
        requires_flyer=True,
        has_follow_up=False,
        description="Detailed content description post",
        theme_guidance="Detailed content preview, build anticipation with description",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="wall_link_drop",
        name="Wall Link Drop",
        channel="feed",
        page_type_filter="both",
        priority_tier=2,
        min_spacing_hours=4.0,
        max_daily=2,
        max_weekly=14,
        requires_flyer=False,
        has_follow_up=False,
        description="Link drop directly on feed wall",
        theme_guidance="Quick link share on wall, casual promotion",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="live_promo",
        name="Live Promo",
        channel="feed",
        page_type_filter="both",
        priority_tier=2,
        min_spacing_hours=24.0,
        max_daily=1,
        max_weekly=3,
        requires_flyer=True,
        has_follow_up=False,
        description="Promotion for upcoming live stream",
        theme_guidance="Live stream announcement, time and date, exclusive preview",
    )
)


# -----------------------------------------------------------------------------
# TIER 3 - ENGAGEMENT (priority=3)
# -----------------------------------------------------------------------------

REGISTRY.register(
    SchedulableContentType(
        type_id="dm_farm",
        name="DM Farm",
        channel="direct",
        page_type_filter="both",
        priority_tier=3,
        min_spacing_hours=12.0,
        max_daily=2,
        max_weekly=10,
        requires_flyer=False,
        has_follow_up=False,
        description="Direct message to encourage engagement",
        theme_guidance="DM me for surprise, encourage 1-on-1 engagement and conversation",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="like_farm",
        name="Like Farm",
        channel="feed",
        page_type_filter="both",
        priority_tier=3,
        min_spacing_hours=12.0,
        max_daily=2,
        max_weekly=10,
        requires_flyer=True,
        has_follow_up=False,
        description="Post designed to maximize likes",
        theme_guidance="Like this post for a reward, engagement boost campaign",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="text_only_bump",
        name="Text-Only Bump",
        channel="mass_message",
        page_type_filter="both",
        priority_tier=3,
        min_spacing_hours=4.0,
        max_daily=2,
        max_weekly=14,
        requires_flyer=False,
        has_follow_up=False,
        description="Text-only mass message bump",
        theme_guidance="Personal message tone, casual check-in or tease",
    )
)


# -----------------------------------------------------------------------------
# TIER 4 - RETENTION (priority=4)
# -----------------------------------------------------------------------------

REGISTRY.register(
    SchedulableContentType(
        type_id="renew_on_mm",
        name="Renew On Mass Message",
        channel="mass_message",
        page_type_filter="paid",  # PAID ONLY
        priority_tier=4,
        min_spacing_hours=24.0,
        max_daily=1,
        max_weekly=2,
        requires_flyer=True,
        has_follow_up=False,
        description="Renewal reminder via mass message",
        theme_guidance="Subscription expiring soon, exclusive content preview to retain",
    )
)

REGISTRY.register(
    SchedulableContentType(
        type_id="expired_subscriber",
        name="Expired Subscriber",
        channel="direct",
        page_type_filter="paid",  # PAID ONLY
        priority_tier=4,
        min_spacing_hours=72.0,
        max_daily=1,
        max_weekly=2,
        requires_flyer=True,
        has_follow_up=False,
        description="Win-back message for expired subscribers",
        theme_guidance="Miss you message, highlight what they are missing, special offer to return",
    )
)


# =============================================================================
# MODULE-LEVEL HELPER FUNCTION
# =============================================================================


def get_registry() -> ContentTypeRegistry:
    """
    Get the singleton content type registry.

    This function provides access to the pre-populated registry
    containing all standard EROS content types.

    Returns:
        The global ContentTypeRegistry instance

    Example:
        >>> registry = get_registry()
        >>> ppv = registry.get("ppv")
    """
    return REGISTRY


# =============================================================================
# MAIN (FOR TESTING)
# =============================================================================


def main() -> None:
    """Test the content type registry module.

    This function uses print() for CLI output since it's intended for
    direct user interaction when the module is run standalone.
    """
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("=" * 70)
    print("EROS Content Type Registry")
    print("=" * 70)
    print()

    registry = get_registry()

    print(f"Total registered content types: {len(registry)}")
    print()

    # Display by tier
    for tier in range(1, 5):
        tier_types = registry.get_types_by_priority(tier)
        tier_names = {1: "Direct Revenue", 2: "Feed/Wall", 3: "Engagement", 4: "Retention"}
        print(f"Tier {tier} - {tier_names.get(tier, 'Unknown')} ({len(tier_types)} types)")
        print("-" * 70)

        for ct in tier_types:
            page_filter = (
                f"[{ct.page_type_filter.upper()}]" if ct.page_type_filter != "both" else ""
            )
            print(
                f"  {ct.type_id:<20} | {ct.channel:<14} | "
                f"Spacing: {ct.min_spacing_hours:>5}h | "
                f"Max: {ct.max_daily}/day, {ct.max_weekly}/wk {page_filter}"
            )

        print()

    # Display by channel
    print("Content Types by Channel:")
    print("-" * 70)

    for channel in ["mass_message", "feed", "direct", "poll", "gamification"]:
        channel_types = registry.get_types_by_channel(channel)
        if channel_types:
            type_ids = [ct.type_id for ct in channel_types]
            print(f"  {channel:<15}: {', '.join(type_ids)}")

    print()

    # Display page type restrictions
    print("Page Type Restrictions:")
    print("-" * 70)

    paid_only = [ct.type_id for ct in registry.get_all() if ct.page_type_filter == "paid"]
    free_only = [ct.type_id for ct in registry.get_all() if ct.page_type_filter == "free"]
    both = [ct.type_id for ct in registry.get_all() if ct.page_type_filter == "both"]

    print(f"  Paid Only:  {', '.join(paid_only)}")
    print(f"  Free Only:  {', '.join(free_only) if free_only else 'None'}")
    print(f"  Both:       {', '.join(both)}")

    print()

    # Validate example
    print("Validation Examples:")
    print("-" * 70)
    print(f"  vip_post valid for 'paid': {registry.validate_for_page('vip_post', 'paid')}")
    print(f"  vip_post valid for 'free': {registry.validate_for_page('vip_post', 'free')}")
    print(f"  ppv valid for 'free': {registry.validate_for_page('ppv', 'free')}")
    print()

    # Content Type Mapping Examples
    print("Content Type Mapping (Database -> Registry):")
    print("-" * 70)
    test_mappings = [
        "bundle_offer",
        "shower_bath",
        "exclusive_content",
        "flash_sale",
        "tip_request",
        "blowjob_dildo",
        "boy_girl",
        "solo",
        "ppv",
        "unknown_type",
        None,
    ]
    for db_type in test_mappings:
        registry_type = normalize_content_type(db_type)
        display = get_display_name(registry_type)
        pricing = get_pricing_category(registry_type)
        print(f"  {str(db_type):<20} -> {registry_type:<15} | Display: {display:<15} | Pricing: {pricing}")
    print()

    print("=" * 70)


if __name__ == "__main__":
    main()
