"""
Schedule item models with expiration support.

Extends the base ScheduleItem with link drop expiration handling and
factory methods for creating schedule items with automatic expiration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

# Link drop types that require 24-hour expiration
LINK_DROP_TYPES = frozenset({"link_drop", "wall_link_drop"})

# Default expiration for link drop types
DEFAULT_LINK_DROP_EXPIRATION_HOURS = 24


@dataclass(slots=True)
class ScheduleItemWithExpiration:
    """Schedule item with expiration support for time-sensitive content.

    Enhanced schedule item that tracks expiration times for link drops
    and other time-limited content. Automatically applies 24-hour expiration
    for link_drop and wall_link_drop send types.

    Attributes:
        send_type: Send type key (e.g., 'link_drop', 'ppv_wall')
        scheduled_time: Datetime when the item should be sent
        channel: Distribution channel (e.g., 'wall_post', 'mass_message')
        caption_id: Optional caption identifier for the associated caption
        price: Optional price for PPV content (None for free content)
        parent_id: Optional parent item ID for followups and linked campaigns
        expiration_time: Optional datetime when the item expires
        item_id: Unique identifier for this schedule item

    Example:
        >>> from datetime import datetime
        >>> item = ScheduleItemWithExpiration(
        ...     send_type="link_drop",
        ...     scheduled_time=datetime(2025, 12, 17, 14, 0),
        ...     channel="mass_message"
        ... )
        >>> item.expiration_time is not None  # Auto-set for link_drop
        True
        >>> item.is_expired(datetime(2025, 12, 18, 15, 0))
        True
    """

    send_type: str
    scheduled_time: datetime
    channel: str
    caption_id: Optional[str] = None
    price: Optional[float] = None
    parent_id: Optional[str] = None
    expiration_time: Optional[datetime] = None
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        """Auto-set 24-hour expiration for link drop types.

        If the send_type is a link drop type and no expiration_time is set,
        automatically calculates and sets the expiration to 24 hours after
        the scheduled time.
        """
        if self.send_type in LINK_DROP_TYPES and self.expiration_time is None:
            self.expiration_time = self.scheduled_time + timedelta(
                hours=DEFAULT_LINK_DROP_EXPIRATION_HOURS
            )

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the schedule item has expired.

        Args:
            current_time: Time to check against. Defaults to current datetime.

        Returns:
            True if the item has an expiration time and it has passed.
        """
        if self.expiration_time is None:
            return False
        check_time = current_time or datetime.now()
        return check_time > self.expiration_time

    def time_until_expiration(self, current_time: Optional[datetime] = None) -> Optional[timedelta]:
        """Calculate time remaining until expiration.

        Args:
            current_time: Time to calculate from. Defaults to current datetime.

        Returns:
            Timedelta until expiration, None if no expiration set,
            or negative timedelta if already expired.
        """
        if self.expiration_time is None:
            return None
        check_time = current_time or datetime.now()
        return self.expiration_time - check_time

    @property
    def is_link_drop(self) -> bool:
        """Check if this is a link drop type item."""
        return self.send_type in LINK_DROP_TYPES

    @property
    def has_expiration(self) -> bool:
        """Check if this item has an expiration time set."""
        return self.expiration_time is not None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the schedule item.
        """
        return {
            "item_id": self.item_id,
            "send_type": self.send_type,
            "scheduled_time": self.scheduled_time.isoformat(),
            "channel": self.channel,
            "caption_id": self.caption_id,
            "price": self.price,
            "parent_id": self.parent_id,
            "expiration_time": (
                self.expiration_time.isoformat() if self.expiration_time else None
            ),
        }


def create_link_drop(
    parent_campaign: ScheduleItemWithExpiration,
    scheduled_time: datetime,
    caption_id: Optional[str] = None,
    send_type: str = "link_drop",
) -> ScheduleItemWithExpiration:
    """Create a link drop item linked to a parent campaign.

    Factory function for creating link drop schedule items that are
    associated with a parent campaign (e.g., PPV content). The link drop
    automatically gets 24-hour expiration from its scheduled time.

    Args:
        parent_campaign: The parent schedule item this link drop promotes
        scheduled_time: When to send the link drop
        caption_id: Optional caption ID for the link drop message
        send_type: Type of link drop ('link_drop' or 'wall_link_drop')

    Returns:
        ScheduleItemWithExpiration configured as a link drop with parent reference

    Raises:
        ValueError: If send_type is not a valid link drop type

    Example:
        >>> from datetime import datetime
        >>> parent = ScheduleItemWithExpiration(
        ...     send_type="ppv_wall",
        ...     scheduled_time=datetime(2025, 12, 17, 10, 0),
        ...     channel="wall_post",
        ...     price=9.99
        ... )
        >>> link_drop = create_link_drop(
        ...     parent_campaign=parent,
        ...     scheduled_time=datetime(2025, 12, 17, 14, 0)
        ... )
        >>> link_drop.parent_id == parent.item_id
        True
        >>> link_drop.expiration_time is not None
        True
    """
    if send_type not in LINK_DROP_TYPES:
        raise ValueError(
            f"Invalid link drop type: {send_type}. "
            f"Must be one of: {', '.join(sorted(LINK_DROP_TYPES))}"
        )

    return ScheduleItemWithExpiration(
        send_type=send_type,
        scheduled_time=scheduled_time,
        channel=parent_campaign.channel,
        caption_id=caption_id,
        price=None,  # Link drops don't have prices
        parent_id=parent_campaign.item_id,
        # expiration_time auto-set by __post_init__
    )


def create_wall_link_drop(
    parent_campaign: ScheduleItemWithExpiration,
    scheduled_time: datetime,
    caption_id: Optional[str] = None,
) -> ScheduleItemWithExpiration:
    """Create a wall link drop item linked to a parent campaign.

    Convenience function specifically for wall link drops. These are
    typically used to promote wall content on free pages.

    Args:
        parent_campaign: The parent schedule item this link drop promotes
        scheduled_time: When to send the wall link drop
        caption_id: Optional caption ID for the link drop message

    Returns:
        ScheduleItemWithExpiration configured as a wall link drop

    Example:
        >>> from datetime import datetime
        >>> parent = ScheduleItemWithExpiration(
        ...     send_type="ppv_wall",
        ...     scheduled_time=datetime(2025, 12, 17, 10, 0),
        ...     channel="wall_post",
        ...     price=9.99
        ... )
        >>> wall_drop = create_wall_link_drop(
        ...     parent_campaign=parent,
        ...     scheduled_time=datetime(2025, 12, 17, 16, 0)
        ... )
        >>> wall_drop.send_type
        'wall_link_drop'
    """
    return create_link_drop(
        parent_campaign=parent_campaign,
        scheduled_time=scheduled_time,
        caption_id=caption_id,
        send_type="wall_link_drop",
    )


__all__ = [
    "ScheduleItemWithExpiration",
    "create_link_drop",
    "create_wall_link_drop",
    "LINK_DROP_TYPES",
    "DEFAULT_LINK_DROP_EXPIRATION_HOURS",
]
