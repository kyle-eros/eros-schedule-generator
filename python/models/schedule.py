"""
Schedule domain models.

Defines schedule items and templates for schedule generation.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ScheduleItem:
    """Schedule item with timing and metadata.

    Represents a single scheduled send with all required information
    for execution and tracking.

    Attributes:
        send_type_key: Send type identifier (e.g., 'ppv_unlock')
        scheduled_date: Date for send (YYYY-MM-DD)
        scheduled_time: Time for send (HH:MM)
        category: 'revenue', 'engagement', or 'retention'
        priority: Priority level (1=highest, 3=lowest)
        caption_id: Associated caption ID
        caption_text: Caption text content
        requires_media: Whether media is required
        media_type: Type of media ('picture', 'video', 'gif', 'flyer', 'none')
        content_type_id: Content type identifier
        suggested_price: Suggested PPV price
        target_key: Audience target key
        channel_key: Distribution channel key
        parent_item_id: Parent schedule item (for followups)
        needs_manual_caption: Flag indicating manual caption entry required
        caption_warning: Explanation of why manual caption is needed
    """

    send_type_key: str
    scheduled_date: str
    scheduled_time: str
    category: str
    priority: int
    caption_id: int | None = None
    caption_text: str = ""
    requires_media: bool = False
    media_type: str = "none"
    content_type_id: int | None = None
    suggested_price: float | None = None
    target_key: str = "all_fans"
    channel_key: str = "mass_message"
    parent_item_id: int | None = None
    needs_manual_caption: bool = False
    caption_warning: str = ""

    @property
    def datetime_obj(self) -> datetime:
        """Get combined datetime object."""
        date_obj = datetime.strptime(self.scheduled_date, "%Y-%m-%d")
        time_obj = datetime.strptime(self.scheduled_time, "%H:%M").time()
        return datetime.combine(date_obj.date(), time_obj)

    def __post_init__(self) -> None:
        """Validate schedule item on initialization."""
        if self.category not in ("revenue", "engagement", "retention"):
            raise ValueError(f"Invalid category: {self.category}")
        if self.priority < 1 or self.priority > 3:
            raise ValueError(f"Priority must be 1-3, got {self.priority}")
        if self.media_type not in ("picture", "video", "gif", "flyer", "none"):
            raise ValueError(f"Invalid media_type: {self.media_type}")

        # Validate date format
        try:
            datetime.strptime(self.scheduled_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid scheduled_date format (expected YYYY-MM-DD): {e}")

        # Validate time format
        try:
            datetime.strptime(self.scheduled_time, "%H:%M")
        except ValueError as e:
            raise ValueError(f"Invalid scheduled_time format (expected HH:MM): {e}")


@dataclass(frozen=True, slots=True)
class ScheduleTemplate:
    """Schedule template configuration.

    Defines a reusable schedule template with volume and timing preferences.

    Attributes:
        template_id: Database primary key
        template_name: Human-readable name
        creator_id: Associated creator (None if generic)
        page_type: 'paid' or 'free'
        volume_tier: 'low', 'mid', 'high', or 'ultra'
        revenue_per_day: Target revenue sends per day
        engagement_per_day: Target engagement sends per day
        retention_per_day: Target retention sends per day
        timing_strategy: 'prime_time', 'balanced', or 'distributed'
        is_active: Whether template is active (0/1)
    """

    template_id: int
    template_name: str
    page_type: str
    volume_tier: str
    revenue_per_day: int
    engagement_per_day: int
    retention_per_day: int
    creator_id: int | None = None
    timing_strategy: str = "balanced"
    is_active: int = 1

    @property
    def total_per_day(self) -> int:
        """Total sends per day across all categories."""
        return self.revenue_per_day + self.engagement_per_day + self.retention_per_day

    def __post_init__(self) -> None:
        """Validate template configuration."""
        if self.page_type not in ("paid", "free"):
            raise ValueError(f"Invalid page_type: {self.page_type}")
        if self.volume_tier not in ("low", "mid", "high", "ultra"):
            raise ValueError(f"Invalid volume_tier: {self.volume_tier}")
        if self.timing_strategy not in ("prime_time", "balanced", "distributed"):
            raise ValueError(f"Invalid timing_strategy: {self.timing_strategy}")
        # Note: Free pages CAN have retention sends (ppv_message, ppv_followup)
        # Only paid-only types (renew_on_post, renew_on_message, expired_winback)
        # are restricted. Type-level validation is handled by SendTypeAllocator.
