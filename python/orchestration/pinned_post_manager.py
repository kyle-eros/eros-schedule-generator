"""
Pinned post management for OnlyFans wall content.

Manages the rotation and lifecycle of pinned posts on creator profiles,
enforcing maximum pin limits and automatic expiration based on priority.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from python.models.schedule_item import ScheduleItemWithExpiration

logger = logging.getLogger(__name__)

# Send types that should be pinned
PINNABLE_SEND_TYPES = frozenset({"ppv_wall", "game_post"})

# Priority mapping for send types (higher = more important)
SEND_TYPE_PRIORITY: dict[str, int] = {
    "ppv_wall": 10,      # Highest priority - revenue generating
    "game_post": 8,      # High priority - engagement + revenue
    "tip_goal": 7,       # Revenue generating
    "bundle": 6,         # Revenue generating
    "flash_bundle": 6,   # Revenue generating
    "vip_program": 5,    # Lower priority promotional
}


@dataclass(slots=True)
class PinItem:
    """Represents a pinned post with lifecycle information.

    Tracks the pinning state of a wall post including when it was pinned,
    when it should be unpinned, and its priority for rotation decisions.

    Attributes:
        post_id: Unique identifier for the pinned post
        pin_start: Datetime when the post was pinned
        pin_end: Datetime when the post should be unpinned
        priority: Priority level for rotation (higher = keep longer)
        pin_id: Unique identifier for this pin record

    Example:
        >>> from datetime import datetime
        >>> pin = PinItem(
        ...     post_id="post_123",
        ...     pin_start=datetime(2025, 12, 17, 10, 0),
        ...     pin_end=datetime(2025, 12, 20, 10, 0),
        ...     priority=10
        ... )
        >>> pin.is_expired(datetime(2025, 12, 21, 0, 0))
        True
    """

    post_id: str
    pin_start: datetime
    pin_end: datetime
    priority: int
    pin_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the pin has expired.

        Args:
            current_time: Time to check against. Defaults to current datetime.

        Returns:
            True if the pin_end time has passed.
        """
        check_time = current_time or datetime.now()
        return check_time > self.pin_end

    def time_remaining(self, current_time: Optional[datetime] = None) -> timedelta:
        """Calculate time remaining until pin expires.

        Args:
            current_time: Time to calculate from. Defaults to current datetime.

        Returns:
            Timedelta until expiration (negative if already expired).
        """
        check_time = current_time or datetime.now()
        return self.pin_end - check_time

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the pin item.
        """
        return {
            "pin_id": self.pin_id,
            "post_id": self.post_id,
            "pin_start": self.pin_start.isoformat(),
            "pin_end": self.pin_end.isoformat(),
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PinItem:
        """Create PinItem from dictionary.

        Args:
            data: Dictionary containing pin item data.

        Returns:
            PinItem instance.
        """
        return cls(
            pin_id=data.get("pin_id", str(uuid.uuid4())),
            post_id=data["post_id"],
            pin_start=datetime.fromisoformat(data["pin_start"]),
            pin_end=datetime.fromisoformat(data["pin_end"]),
            priority=data["priority"],
        )


class PinnedPostManager:
    """Manages pinned posts for a creator's wall.

    Handles the lifecycle of pinned posts including scheduling new pins,
    rotating out lower priority pins when at capacity, and tracking
    expiration for automatic unpinning.

    OnlyFans allows a maximum of 5 pinned posts. This manager enforces
    that limit and implements intelligent rotation based on priority.

    Attributes:
        MAX_PINNED: Maximum number of concurrent pinned posts (5)
        PIN_DURATION_HOURS: Default pin duration in hours (72)

    Example:
        >>> manager = PinnedPostManager(creator_id="creator_123")
        >>> from datetime import datetime
        >>> from python.models.schedule_item import ScheduleItemWithExpiration
        >>> item = ScheduleItemWithExpiration(
        ...     send_type="ppv_wall",
        ...     scheduled_time=datetime(2025, 12, 17, 10, 0),
        ...     channel="wall_post"
        ... )
        >>> if manager.should_pin(item):
        ...     pin = manager.schedule_pin(item)
    """

    MAX_PINNED: int = 5
    PIN_DURATION_HOURS: int = 72

    def __init__(
        self,
        creator_id: str,
        storage_path: Optional[str] = None,
    ) -> None:
        """Initialize the pinned post manager.

        Args:
            creator_id: Unique identifier for the creator
            storage_path: Optional path for pin data storage.
                         Defaults to ~/.eros/pins/{creator_id}.json
        """
        self.creator_id = creator_id
        self._storage_path = self._resolve_storage_path(storage_path)
        self._active_pins: list[PinItem] = []
        self._load_active_pins()

    def _resolve_storage_path(self, storage_path: Optional[str]) -> Path:
        """Resolve the storage path for pin data.

        Args:
            storage_path: Optional custom storage path.

        Returns:
            Path object for pin data storage.
        """
        if storage_path:
            return Path(storage_path)

        # Default to ~/.eros/pins/{creator_id}.json
        base_dir = Path.home() / ".eros" / "pins"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / f"{self.creator_id}.json"

    def _load_active_pins(self) -> list[PinItem]:
        """Load and filter active pins from storage.

        Loads pin data from storage and filters out any expired pins.
        Expired pins are automatically removed from storage.

        Returns:
            List of currently active (non-expired) pins.
        """
        self._active_pins = []

        if not self._storage_path.exists():
            logger.debug(f"No pin data found for creator {self.creator_id}")
            return self._active_pins

        try:
            with open(self._storage_path, "r") as f:
                data = json.load(f)

            current_time = datetime.now()
            all_pins = [PinItem.from_dict(p) for p in data.get("pins", [])]

            # Filter out expired pins
            self._active_pins = [
                pin for pin in all_pins if not pin.is_expired(current_time)
            ]

            # Save if we filtered any expired pins
            if len(self._active_pins) < len(all_pins):
                expired_count = len(all_pins) - len(self._active_pins)
                logger.info(
                    f"Removed {expired_count} expired pins for creator {self.creator_id}"
                )
                self._persist_pins()

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(
                f"Error loading pin data for creator {self.creator_id}: {e}"
            )
            self._active_pins = []

        return self._active_pins

    def _persist_pins(self) -> None:
        """Persist current pins to storage."""
        data = {
            "creator_id": self.creator_id,
            "updated_at": datetime.now().isoformat(),
            "pins": [pin.to_dict() for pin in self._active_pins],
        }

        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to persist pins for creator {self.creator_id}: {e}")

    @property
    def active_pins(self) -> list[PinItem]:
        """Get list of currently active pins.

        Returns:
            Copy of the active pins list.
        """
        return self._active_pins.copy()

    @property
    def pin_count(self) -> int:
        """Get count of currently active pins.

        Returns:
            Number of active pins.
        """
        return len(self._active_pins)

    @property
    def has_capacity(self) -> bool:
        """Check if there's room for another pin.

        Returns:
            True if fewer than MAX_PINNED pins are active.
        """
        return self.pin_count < self.MAX_PINNED

    def should_pin(self, schedule_item: ScheduleItemWithExpiration) -> bool:
        """Determine if a schedule item should be pinned.

        Checks if the send type is one that should be pinned (ppv_wall, game_post).

        Args:
            schedule_item: The schedule item to evaluate.

        Returns:
            True if the item's send type is in PINNABLE_SEND_TYPES.
        """
        return schedule_item.send_type in PINNABLE_SEND_TYPES

    def _get_priority(self, send_type: str) -> int:
        """Get priority for a send type.

        Args:
            send_type: The send type key.

        Returns:
            Priority value (default 1 if not in mapping).
        """
        return SEND_TYPE_PRIORITY.get(send_type, 1)

    def _find_lowest_priority_pin(self) -> Optional[PinItem]:
        """Find the pin with lowest priority.

        Returns:
            The lowest priority pin, or None if no pins exist.
        """
        if not self._active_pins:
            return None
        return min(self._active_pins, key=lambda p: p.priority)

    def schedule_pin(
        self,
        schedule_item: ScheduleItemWithExpiration,
        pin_start: Optional[datetime] = None,
        duration_hours: Optional[int] = None,
    ) -> Optional[PinItem]:
        """Schedule a post to be pinned.

        Creates a pin for the schedule item. If at MAX_PINNED capacity,
        will replace the lowest priority pin if the new item has higher
        priority.

        Args:
            schedule_item: The schedule item to pin.
            pin_start: When to start the pin. Defaults to scheduled_time.
            duration_hours: How long to pin. Defaults to PIN_DURATION_HOURS.

        Returns:
            PinItem if successfully scheduled, None if:
            - Item shouldn't be pinned (not a pinnable type)
            - At capacity and new item has lower/equal priority
        """
        if not self.should_pin(schedule_item):
            logger.debug(
                f"Send type {schedule_item.send_type} is not pinnable"
            )
            return None

        new_priority = self._get_priority(schedule_item.send_type)
        start_time = pin_start or schedule_item.scheduled_time
        duration = duration_hours or self.PIN_DURATION_HOURS
        end_time = start_time + timedelta(hours=duration)

        # Check capacity and handle rotation
        if not self.has_capacity:
            lowest_pin = self._find_lowest_priority_pin()

            if lowest_pin is None:
                logger.error("No pins found but at capacity - inconsistent state")
                return None

            if new_priority <= lowest_pin.priority:
                logger.info(
                    f"Cannot pin {schedule_item.send_type} (priority {new_priority}): "
                    f"at capacity and lowest pin has priority {lowest_pin.priority}"
                )
                return None

            # Replace lowest priority pin
            logger.info(
                f"Replacing pin {lowest_pin.post_id} (priority {lowest_pin.priority}) "
                f"with new pin (priority {new_priority})"
            )
            self._unpin(lowest_pin)

        # Create and save new pin
        new_pin = PinItem(
            post_id=schedule_item.item_id,
            pin_start=start_time,
            pin_end=end_time,
            priority=new_priority,
        )

        self._save_pin(new_pin)
        return new_pin

    def _unpin(self, pin_item: PinItem) -> bool:
        """Remove a pin from active pins.

        Args:
            pin_item: The pin to remove.

        Returns:
            True if the pin was found and removed.
        """
        try:
            self._active_pins = [
                p for p in self._active_pins if p.pin_id != pin_item.pin_id
            ]
            self._persist_pins()
            logger.info(f"Unpinned post {pin_item.post_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unpin post {pin_item.post_id}: {e}")
            return False

    def _save_pin(self, pin_item: PinItem) -> bool:
        """Add a pin to active pins and persist.

        Args:
            pin_item: The pin to save.

        Returns:
            True if successfully saved.
        """
        try:
            self._active_pins.append(pin_item)
            self._persist_pins()
            logger.info(
                f"Pinned post {pin_item.post_id} until {pin_item.pin_end.isoformat()}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save pin for post {pin_item.post_id}: {e}")
            # Remove from in-memory list if persist failed
            self._active_pins = [
                p for p in self._active_pins if p.pin_id != pin_item.pin_id
            ]
            return False

    def get_pins_to_remove(
        self,
        current_time: Optional[datetime] = None,
    ) -> list[PinItem]:
        """Get list of pins that should be removed.

        Returns pins that have passed their expiration time and should
        be unpinned from the creator's wall.

        Args:
            current_time: Time to check against. Defaults to current datetime.

        Returns:
            List of expired PinItem objects.
        """
        check_time = current_time or datetime.now()
        return [pin for pin in self._active_pins if pin.is_expired(check_time)]

    def cleanup_expired(
        self,
        current_time: Optional[datetime] = None,
    ) -> list[PinItem]:
        """Remove all expired pins.

        Convenience method to get expired pins and remove them in one call.

        Args:
            current_time: Time to check against. Defaults to current datetime.

        Returns:
            List of pins that were removed.
        """
        expired = self.get_pins_to_remove(current_time)
        for pin in expired:
            self._unpin(pin)
        return expired

    def unpin_by_post_id(self, post_id: str) -> bool:
        """Manually unpin a post by its ID.

        Args:
            post_id: The post ID to unpin.

        Returns:
            True if the post was found and unpinned.
        """
        pin = next(
            (p for p in self._active_pins if p.post_id == post_id),
            None
        )
        if pin:
            return self._unpin(pin)
        logger.warning(f"No active pin found for post {post_id}")
        return False

    def get_pin_status(self) -> dict:
        """Get current pin status summary.

        Returns:
            Dictionary with pin status information.
        """
        current_time = datetime.now()
        return {
            "creator_id": self.creator_id,
            "active_pin_count": self.pin_count,
            "max_pins": self.MAX_PINNED,
            "has_capacity": self.has_capacity,
            "pins": [
                {
                    **pin.to_dict(),
                    "time_remaining_hours": round(
                        pin.time_remaining(current_time).total_seconds() / 3600, 1
                    ),
                }
                for pin in self._active_pins
            ],
            "expires_soon": [
                pin.post_id
                for pin in self._active_pins
                if pin.time_remaining(current_time).total_seconds() < 3600 * 6
            ],
        }


__all__ = [
    "PinItem",
    "PinnedPostManager",
    "PINNABLE_SEND_TYPES",
    "SEND_TYPE_PRIORITY",
]
