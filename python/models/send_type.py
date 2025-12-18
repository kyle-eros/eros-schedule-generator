"""
Send type domain models.

Defines send types and their configuration requirements.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


# =============================================================================
# PPV and Page Type Constants
# =============================================================================

# PPV-related constants
PPV_TYPES = frozenset({"ppv_unlock", "ppv_wall", "ppv_followup"})
PPV_REVENUE_TYPES = frozenset({"ppv_unlock", "ppv_wall", "tip_goal"})

# Deprecated send types (kept for backward compatibility during transition)
DEPRECATED_SEND_TYPES = frozenset({"ppv_video", "ppv_message"})

# Send type aliases for backward compatibility
SEND_TYPE_ALIASES: dict[str, str] = {
    "ppv_video": "ppv_unlock",  # ppv_video -> ppv_unlock (renamed)
    "ppv_message": "ppv_unlock",  # ppv_message -> ppv_unlock (merged)
}


class TipGoalMode(str, Enum):
    """Tip goal content unlock modes.

    Defines how tip goals work for paid page content monetization.

    Attributes:
        GOAL_BASED: Fans tip toward collective goal, content unlocks for all tippers
        INDIVIDUAL: Each fan tips to unlock for themselves
        COMPETITIVE: First N tippers get exclusive access
    """
    GOAL_BASED = "goal_based"
    INDIVIDUAL = "individual"
    COMPETITIVE = "competitive"


# Page type restrictions
PAGE_TYPE_FREE_ONLY = frozenset({"ppv_wall"})
PAGE_TYPE_PAID_ONLY = frozenset({
    "tip_goal",
    "renew_on_post",
    "renew_on_message",
    "expired_winback"
})

# Category-based send type groupings (updated taxonomy)
REVENUE_TYPES = frozenset({
    "ppv_unlock",      # Primary PPV (renamed from ppv_video)
    "ppv_wall",        # NEW - FREE pages only
    "tip_goal",        # NEW - PAID pages only
    "bundle",
    "flash_bundle",
    "game_post",
    "first_to_tip",
    "vip_program",
    "snapchat_bundle",
})

ENGAGEMENT_TYPES = frozenset({
    "link_drop",
    "wall_link_drop",
    "bump_normal",
    "bump_descriptive",
    "bump_text_only",
    "bump_flyer",
    "dm_farm",
    "like_farm",
    "live_promo",
})

RETENTION_TYPES = frozenset({
    "renew_on_post",
    "renew_on_message",
    "ppv_followup",
    "expired_winback",
})


def resolve_send_type_key(send_type_key: str) -> str:
    """Resolve a send type key, handling aliases for deprecated types.

    Args:
        send_type_key: The send type key to resolve.

    Returns:
        The canonical send type key (resolves aliases to new names).
    """
    return SEND_TYPE_ALIASES.get(send_type_key, send_type_key)


def is_valid_for_page_type(send_type_key: str, page_type: str) -> bool:
    """Check if a send type is valid for a given page type.

    Args:
        send_type_key: The send type key to check.
        page_type: The page type ('paid' or 'free').

    Returns:
        True if the send type can be used with the page type.
    """
    resolved_key = resolve_send_type_key(send_type_key)

    if page_type == "free":
        return resolved_key not in PAGE_TYPE_PAID_ONLY
    elif page_type == "paid":
        return resolved_key not in PAGE_TYPE_FREE_ONLY
    else:
        return True  # 'both' or unknown page type


@dataclass(frozen=True, slots=True)
class SendType:
    """Send type definition from database.

    Represents a single send type with all its database attributes.

    Attributes:
        send_type_id: Database primary key
        send_type_key: Unique identifier (e.g., 'ppv_unlock')
        category: 'revenue', 'engagement', or 'retention'
        display_name: Human-readable name
        description: Detailed description
        purpose: Business purpose
        strategy: Recommended usage strategy
        requires_media: Whether media is required (0/1)
        requires_flyer: Whether flyer is required (0/1)
        requires_price: Whether price is required (0/1)
        requires_link: Whether link is required (0/1)
        has_expiration: Whether send expires (0/1)
        default_expiration_hours: Default expiration time
        can_have_followup: Whether followups are allowed (0/1)
        followup_delay_minutes: Minimum delay before followup
        page_type_restriction: 'paid', 'free', or 'both'
        caption_length: 'short', 'medium', or 'long'
        emoji_recommendation: 'none', 'light', 'moderate', or 'heavy'
        max_per_day: Maximum sends per day (None = unlimited)
        max_per_week: Maximum sends per week (None = unlimited)
        min_hours_between: Minimum hours between sends
        sort_order: Display sort order
        is_active: Whether send type is active (0/1)
    """

    send_type_id: int
    send_type_key: str
    category: str
    display_name: str
    description: str | None = None
    purpose: str | None = None
    strategy: str | None = None
    requires_media: int = 1
    requires_flyer: int = 0
    requires_price: int = 0
    requires_link: int = 0
    has_expiration: int = 0
    default_expiration_hours: int | None = None
    can_have_followup: int = 0
    followup_delay_minutes: int = 20
    page_type_restriction: str = "both"
    caption_length: str | None = None
    emoji_recommendation: str | None = None
    max_per_day: int | None = None
    max_per_week: int | None = None
    min_hours_between: int = 2
    sort_order: int = 100
    is_active: int = 1


@dataclass(frozen=True, slots=True)
class SendTypeConfig:
    """Runtime configuration for a send type.

    Optimized configuration object used by the registry and allocation engine.
    Contains processed, runtime-friendly versions of database fields.

    Attributes:
        key: Send type key (e.g., 'ppv_unlock')
        name: Display name
        category: 'revenue', 'engagement', or 'retention'
        page_type: 'paid', 'free', or 'both'
        timing_preferences: Timing configuration (preferred hours, days, spacing)
        caption_requirements: List of caption requirements (length, emoji, etc.)
        max_per_day: Maximum sends per day (None = unlimited)
        max_per_week: Maximum sends per week (None = unlimited)
        requires_media: Whether media is required
        requires_price: Whether price is required
        can_have_followup: Whether followups are allowed
        followup_delay_minutes: Minimum delay before followup
    """

    key: str
    name: str
    category: str
    page_type: str
    timing_preferences: dict[str, Any]
    caption_requirements: list[str]
    max_per_day: int | None
    max_per_week: int | None
    requires_media: bool = False
    requires_price: bool = False
    can_have_followup: bool = False
    followup_delay_minutes: int = 20

    def __post_init__(self) -> None:
        """Validate configuration on initialization."""
        if self.category not in ("revenue", "engagement", "retention"):
            raise ValueError(f"Invalid category: {self.category}")
        if self.page_type not in ("paid", "free", "both"):
            raise ValueError(f"Invalid page_type: {self.page_type}")
