"""
Creator domain models.

Defines creator profiles and metadata.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Creator:
    """Core creator entity.

    Minimal creator information for schedule generation.

    Attributes:
        creator_id: Database primary key
        username: Creator username/handle
        page_type: 'paid' or 'free'
        fan_count: Total number of fans/subscribers
        is_active: Whether creator is active (0/1)
    """

    creator_id: int
    username: str
    page_type: str
    fan_count: int
    is_active: int = 1

    def __post_init__(self) -> None:
        """Validate creator data on initialization."""
        if self.page_type not in ("paid", "free"):
            raise ValueError(f"Invalid page_type: {self.page_type}")
        if self.fan_count < 0:
            raise ValueError("Fan count must be non-negative")


@dataclass(frozen=True, slots=True)
class CreatorProfile:
    """Extended creator profile with persona and preferences.

    Comprehensive creator information including persona, voice, and
    performance characteristics for content curation.

    Attributes:
        creator_id: Database primary key
        username: Creator username/handle
        page_type: 'paid' or 'free'
        fan_count: Total number of fans/subscribers
        persona_archetype: Primary persona archetype
        voice_tone: Communication tone/style
        content_preferences: Preferred content types (JSON)
        performance_baseline: Historical performance baseline score
        saturation_score: Current content saturation score (0-100)
        opportunity_score: Revenue opportunity score (0-100)
        last_schedule_date: Date of last generated schedule
        is_active: Whether creator is active (0/1)
    """

    creator_id: int
    username: str
    page_type: str
    fan_count: int
    persona_archetype: str | None = None
    voice_tone: str | None = None
    content_preferences: str | None = None
    performance_baseline: float | None = None
    saturation_score: float | None = None
    opportunity_score: float | None = None
    last_schedule_date: str | None = None
    is_active: int = 1

    def to_creator(self) -> Creator:
        """Convert to minimal Creator object."""
        return Creator(
            creator_id=self.creator_id,
            username=self.username,
            page_type=self.page_type,
            fan_count=self.fan_count,
            is_active=self.is_active,
        )
