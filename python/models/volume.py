"""
Volume domain models.

Defines volume tiers and configuration for creator send allocation.
"""

from dataclasses import dataclass
from enum import Enum


class VolumeTier(Enum):
    """Volume tier classification based on fan count.

    Tiers determine the base send volume and frequency for schedule generation.
    """

    LOW = "low"      # 0-999 fans
    MID = "mid"      # 1,000-4,999 fans
    HIGH = "high"    # 5,000-14,999 fans
    ULTRA = "ultra"  # 15,000+ fans


@dataclass(frozen=True, slots=True)
class VolumeConfig:
    """Volume configuration for a creator.

    Immutable configuration defining target send volumes per category.
    Used by SendTypeAllocator to distribute content across a schedule.

    Attributes:
        tier: Volume tier classification
        revenue_per_day: Target revenue sends per day
        engagement_per_day: Target engagement sends per day
        retention_per_day: Target retention sends per day (0 for free pages)
        fan_count: Total number of fans/subscribers
        page_type: 'paid' or 'free'
    """

    tier: VolumeTier
    revenue_per_day: int
    engagement_per_day: int
    retention_per_day: int
    fan_count: int
    page_type: str

    @property
    def total_per_day(self) -> int:
        """Total sends per day across all categories."""
        return self.revenue_per_day + self.engagement_per_day + self.retention_per_day

    def __post_init__(self) -> None:
        """Validate configuration on initialization."""
        if self.page_type not in ("paid", "free"):
            raise ValueError(f"Invalid page_type: {self.page_type}")
        if self.page_type == "free" and self.retention_per_day > 0:
            raise ValueError("Free pages cannot have retention sends")
        if self.revenue_per_day < 0 or self.engagement_per_day < 0 or self.retention_per_day < 0:
            raise ValueError("Volume counts must be non-negative")
