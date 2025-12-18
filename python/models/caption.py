"""
Caption domain models.

Defines captions and their performance scores.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Caption:
    """Caption entity for schedule generation.

    Represents a caption with its metadata and requirements.

    Attributes:
        caption_id: Database primary key
        caption_text: The actual caption text
        send_type_key: Associated send type (e.g., 'ppv_unlock')
        content_type_id: Content type identifier
        media_type: 'picture', 'video', 'gif', 'flyer', 'none'
        length_category: 'short', 'medium', 'long'
        emoji_level: 'none', 'light', 'moderate', 'heavy'
        performance_score: Historical performance score (0-100)
        last_used_date: Date caption was last used (YYYY-MM-DD)
        use_count: Number of times caption has been used
        creator_id: Associated creator (None if generic)
        is_active: Whether caption is active (0/1)
    """

    caption_id: int
    caption_text: str
    send_type_key: str
    content_type_id: int | None = None
    media_type: str = "none"
    length_category: str | None = None
    emoji_level: str | None = None
    performance_score: float | None = None
    last_used_date: str | None = None
    use_count: int = 0
    creator_id: int | None = None
    is_active: int = 1

    @property
    def freshness_days(self) -> int | None:
        """Calculate days since last use.

        Returns:
            Days since last use, or None if never used
        """
        if not self.last_used_date:
            return None

        from datetime import datetime
        last_used = datetime.strptime(self.last_used_date, "%Y-%m-%d")
        today = datetime.now()
        return (today - last_used).days


@dataclass(frozen=True, slots=True)
class CaptionScore:
    """Composite score for caption selection.

    Combines multiple scoring factors for caption ranking and selection.

    Attributes:
        caption_id: Caption identifier
        performance_score: Historical performance (0-100)
        freshness_score: Freshness/recency score (0-100)
        type_priority_score: Send type priority score (0-100)
        persona_match_score: Persona alignment score (0-100)
        diversity_score: Content diversity score (0-100)
        composite_score: Weighted composite of all scores (0-100)
        ranking: Relative ranking (1=best)
    """

    caption_id: int
    performance_score: float
    freshness_score: float
    type_priority_score: float
    persona_match_score: float
    diversity_score: float
    composite_score: float
    ranking: int = 0

    def __post_init__(self) -> None:
        """Validate scores are in valid range."""
        scores = [
            self.performance_score,
            self.freshness_score,
            self.type_priority_score,
            self.persona_match_score,
            self.diversity_score,
            self.composite_score,
        ]
        for score in scores:
            if not 0 <= score <= 100:
                raise ValueError(f"Score must be between 0 and 100, got {score}")
