"""
Domain models package for EROS Schedule Generator.

This package contains canonical domain models using frozen, slotted dataclasses
for type safety and immutability. These models represent the core business
entities used throughout the schedule generation pipeline.

All models use modern Python 3.11+ type hints and are designed for high
performance with minimal memory overhead.
"""

from .creator import Creator, CreatorProfile
from .creator_timing_profile import CreatorTimingProfile
from .caption import Caption, CaptionScore
from .schedule import ScheduleItem, ScheduleTemplate
from .schedule_item import (
    ScheduleItemWithExpiration,
    create_link_drop,
    create_wall_link_drop,
    LINK_DROP_TYPES,
    DEFAULT_LINK_DROP_EXPIRATION_HOURS,
)
from .send_type import (
    SendType,
    SendTypeConfig,
    TipGoalMode,
    # Constants
    PPV_TYPES,
    PPV_REVENUE_TYPES,
    DEPRECATED_SEND_TYPES,
    SEND_TYPE_ALIASES,
    PAGE_TYPE_FREE_ONLY,
    PAGE_TYPE_PAID_ONLY,
    REVENUE_TYPES,
    ENGAGEMENT_TYPES,
    RETENTION_TYPES,
    # Functions
    resolve_send_type_key,
    is_valid_for_page_type,
)
from .volume import VolumeConfig, VolumeTier

__all__ = [
    # Domain Models
    "Creator",
    "CreatorProfile",
    "CreatorTimingProfile",
    "Caption",
    "CaptionScore",
    "ScheduleItem",
    "ScheduleTemplate",
    "ScheduleItemWithExpiration",
    "SendType",
    "SendTypeConfig",
    "VolumeConfig",
    "VolumeTier",
    # Enums
    "TipGoalMode",
    # Send Type Constants
    "PPV_TYPES",
    "PPV_REVENUE_TYPES",
    "DEPRECATED_SEND_TYPES",
    "SEND_TYPE_ALIASES",
    "PAGE_TYPE_FREE_ONLY",
    "PAGE_TYPE_PAID_ONLY",
    "REVENUE_TYPES",
    "ENGAGEMENT_TYPES",
    "RETENTION_TYPES",
    # Link Drop Constants
    "LINK_DROP_TYPES",
    "DEFAULT_LINK_DROP_EXPIRATION_HOURS",
    # Send Type Functions
    "resolve_send_type_key",
    "is_valid_for_page_type",
    # Link Drop Factory Functions
    "create_link_drop",
    "create_wall_link_drop",
]
