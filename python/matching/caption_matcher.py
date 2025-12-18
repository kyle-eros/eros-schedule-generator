"""
Caption Matcher - Intelligent caption selection engine.

Selects optimal captions for send types using multi-factor scoring:
- Freshness since last use (40%) - PRIORITIZED
- Performance history (35%)
- Type priority alignment (15%)
- Diversity requirements (5%)
- Persona fit (5%) - tie-breaker only

Implements 5-level fallback strategy for caption availability.
"""

from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import Any, Optional

from python.logging_config import get_logger, log_fallback, log_operation_start, log_operation_end
from python.models.send_type import SEND_TYPE_ALIASES, resolve_send_type_key
from python.observability.metrics import get_metrics, timed

# Module logger
logger = get_logger(__name__)

# =============================================================================
# Scoring Constants
# =============================================================================

# Selection threshold scores (Level 1 - exact match with high scores)
LEVEL1_PERFORMANCE_THRESHOLD = 70.0
LEVEL1_FRESHNESS_THRESHOLD = 60.0

# Selection threshold scores (Level 2 - compatible type with good scores)
LEVEL2_PERFORMANCE_THRESHOLD = 50.0
LEVEL2_FRESHNESS_THRESHOLD = 40.0

# Selection threshold scores (Level 3-4 - acceptable/reusable)
LEVEL3_PERFORMANCE_THRESHOLD = 40.0
LEVEL4_PERFORMANCE_THRESHOLD = 60.0

# Type priority scoring
TYPE_PRIORITY_NEUTRAL_SCORE = 50.0
TYPE_PRIORITY_NON_MATCH_SCORE = 30.0
TYPE_PRIORITY_MAX_SCORE = 100.0
TYPE_PRIORITY_SCORE_RANGE = 40.0  # Score drop from first to last position

# Persona fit scoring
PERSONA_FIT_NEUTRAL_SCORE = 50.0
PERSONA_FIT_EXACT_MATCH_SCORE = 100.0
PERSONA_FIT_TONE_MATCH_SCORE = 75.0
PERSONA_FIT_DEFAULT_SCORE = 40.0

# Diversity scoring
DIVERSITY_MAX_SCORE = 100.0
DIVERSITY_MIN_SCORE = 20.0
DIVERSITY_INITIAL_PENALTY_PER_USE = 10
DIVERSITY_CONTINUED_PENALTY_PER_USE = 8
DIVERSITY_PENALTY_THRESHOLD = 5  # Switch to continued penalty after this many uses


@dataclass(frozen=True, slots=True)
class Caption:
    """Caption with performance and metadata.

    Attributes:
        id: Unique caption identifier
        text: Caption text content
        type: Caption type (e.g., 'flirty', 'urgent', 'appreciation')
        performance_score: Historical performance (0-100)
        freshness_score: Days since last use converted to score (0-100)
        last_used_date: Date caption was last used
        content_type: Associated content type
        emoji_level: Emoji usage intensity (1-5)
        slang_level: Slang usage intensity (1-5)
        tone: Overall tone (e.g., 'playful', 'seductive', 'grateful')
    """

    id: int
    text: str
    type: str
    performance_score: float
    freshness_score: float
    last_used_date: datetime | None = None
    content_type: str | None = None
    emoji_level: int = 3
    slang_level: int = 3
    tone: str = "neutral"


@dataclass(frozen=True, slots=True)
class CaptionScore:
    """Scored caption with component breakdown.

    Attributes:
        caption: The caption being scored
        total_score: Final weighted score (0-100)
        components: Score breakdown by component
    """

    caption: Caption
    total_score: float
    components: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CaptionResult:
    """Result of caption selection with manual fallback handling.

    Encapsulates the outcome of caption selection, indicating whether
    an automated caption was found or if manual entry is required.

    Attributes:
        caption_score: The selected caption with scoring, or None if manual needed
        needs_manual: True if no automated caption could be found
        reason: Explanation of selection or why manual is needed
        fallback_level: 1-5 for automated fallback levels, 6 for manual
    """

    caption_score: Optional[CaptionScore]
    needs_manual: bool
    reason: str
    fallback_level: int


class CaptionMatcher:
    """Matches captions to send types using intelligent scoring."""

    # Scoring weights (sum to 1.0)
    WEIGHTS: dict[str, float] = {
        "freshness": 0.40,      # FRESHNESS FIRST - prioritize unused captions
        "performance": 0.35,    # Then highest earning
        "type_priority": 0.15,  # Type alignment
        "diversity": 0.05,      # Variety bonus
        "persona": 0.05,        # Minor tie-breaker only
    }

    # Caption type requirements by send type (priority order)
    # Updated for new PPV taxonomy (22 active types + deprecated aliases)
    TYPE_REQUIREMENTS: dict[str, list[str]] = {
        # Revenue send types (9 active)
        "ppv_unlock": ["ppv_unlock", "ppv_teaser", "exclusive", "urgent"],
        "ppv_wall": ["ppv_unlock", "ppv_teaser", "wall_post", "exclusive"],
        "tip_goal": ["tip_request", "goal_pitch", "exclusive", "competitive"],
        "vip_program": ["vip_pitch", "exclusive", "special", "valuable"],
        "game_post": ["interactive", "playful", "game", "fun"],
        "bundle": ["bundle_pitch", "exclusive", "special", "valuable"],
        "flash_bundle": ["urgent", "fomo", "flash_sale", "exclusive"],
        "snapchat_bundle": ["bundle_pitch", "special", "exclusive", "urgent"],
        "first_to_tip": ["tip_request", "competitive", "urgent", "playful"],

        # Engagement send types (9)
        "link_drop": ["teasing", "flirty", "mysterious", "exclusive"],
        "wall_link_drop": ["casual", "update", "playful", "personal"],
        "bump_normal": ["flirty_opener", "check_in", "casual", "friendly"],
        "bump_descriptive": ["story_caption", "scenario", "descriptive", "seductive"],
        "bump_text_only": ["flirty_opener", "casual", "playful", "friendly"],
        "bump_flyer": ["promotional", "attention", "special", "exclusive"],
        "dm_farm": ["question", "interactive", "engaging", "personal"],
        "like_farm": ["appreciation", "grateful", "engaging", "friendly"],
        "live_promo": ["urgent", "fomo", "live_event", "special"],

        # Retention send types (4 active)
        "renew_on_post": ["renewal_pitch", "appreciative", "exclusive", "valuable"],
        "renew_on_message": ["renewal_pitch", "personal", "appreciative", "grateful"],
        "ppv_followup": ["ppv_followup", "reminder", "urgent", "fomo"],
        "expired_winback": ["renewal_pitch", "winback", "special", "exclusive"],

        # DEPRECATED: Aliases for backward compatibility during transition
        # These map to the new ppv_unlock requirements
        "ppv_video": ["ppv_unlock", "ppv_teaser", "exclusive", "urgent"],
        "ppv_message": ["ppv_unlock", "ppv_teaser", "exclusive", "seductive"],  # DEPRECATED: ppv_message merged into ppv_unlock, remove after 2025-01-16
    }

    # Deprecated send types - log warning when used
    DEPRECATED_TYPES: set[str] = {"ppv_video", "ppv_message"}

    # Persona compatibility matrix
    PERSONA_COMPATIBILITY: dict[str, list[str]] = {
        "girl_next_door": ["friendly", "casual", "playful", "warm"],
        "seductress": ["seductive", "flirty", "teasing", "mysterious"],
        "professional": ["professional", "friendly", "accommodating", "update"],
        "playful": ["playful", "fun", "interactive", "casual"],
        "grateful": ["appreciative", "grateful", "warm", "personal"],
    }

    def __init__(self) -> None:
        """Initialize caption matcher with tracking state."""
        self._used_captions: set[int] = set()
        self._type_usage_count: dict[str, int] = {}

    def _record_selection_metrics(
        self,
        start_time: float,
        result: CaptionResult,
        send_type_key: str,
    ) -> None:
        """Record metrics for caption selection operation.

        Args:
            start_time: perf_counter start time for duration calculation
            result: The CaptionResult being returned
            send_type_key: The send type key being selected for
        """
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metrics = get_metrics()

        # Record timing
        metrics.record_timing(
            "caption.selection",
            elapsed_ms,
            tags={
                "fallback_level": result.fallback_level,
                "needs_manual": result.needs_manual,
            }
        )

        # Record fallback level distribution
        metrics.increment(
            f"caption.fallback_level_{result.fallback_level}",
            tags={"send_type": send_type_key}
        )

        if result.needs_manual:
            metrics.increment("caption.manual_required")

        # Log operation end
        log_operation_end(
            logger,
            "select_caption",
            duration_ms=elapsed_ms,
            fallback_level=result.fallback_level,
            needs_manual=result.needs_manual,
            send_type_key=send_type_key,
        )

    def _resolve_send_type(self, send_type_key: str) -> str:
        """Resolve send type key, handling deprecated aliases.

        Args:
            send_type_key: The send type key to resolve.

        Returns:
            The canonical send type key.
        """
        if send_type_key in self.DEPRECATED_TYPES:
            logger.warning(
                f"Deprecated send type '{send_type_key}' used. "
                f"Consider updating to '{resolve_send_type_key(send_type_key)}'."
            )
        return resolve_send_type_key(send_type_key)

    def select_caption(
        self,
        creator_id: str,
        send_type_key: str,
        available_captions: list[Caption],
        persona: str = "playful",
        exclude_ids: set[int] | None = None
    ) -> CaptionResult:
        """Select optimal caption for send type.

        Implements 5-level fallback strategy:
        1. Exact type match with high scores
        2. Compatible type with good scores
        3. Any usable type with acceptable scores
        4. Recently used but high-performing
        5. Any caption available
        6. Manual caption required (when all levels exhausted)

        Args:
            creator_id: Creator identifier
            send_type_key: Send type key
            available_captions: Pool of available captions
            persona: Creator persona type
            exclude_ids: Caption IDs to exclude

        Returns:
            CaptionResult with selected caption or manual fallback indication
        """
        start_time = time.perf_counter()
        metrics = get_metrics()

        log_operation_start(
            logger,
            "select_caption",
            creator_id=creator_id,
            send_type_key=send_type_key,
            pool_size=len(available_captions),
            persona=persona,
        )

        # Resolve deprecated send types
        resolved_type = self._resolve_send_type(send_type_key)

        if not available_captions:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_timing("caption.selection", elapsed_ms, tags={"result": "empty_pool"})
            metrics.increment("caption.empty_pool")
            return CaptionResult(
                caption_score=None,
                needs_manual=True,
                reason=f"No captions available for send_type={send_type_key}, creator={creator_id}. Caption pool is empty.",
                fallback_level=6
            )

        exclude_ids = exclude_ids or set()

        # Get required caption types for this send type (use original key for lookup
        # to support deprecated types during transition)
        required_types = self.TYPE_REQUIREMENTS.get(
            send_type_key,
            self.TYPE_REQUIREMENTS.get(resolved_type, ["casual"])
        )

        # Level 1: Exact type match with high scores
        level1_candidates = [
            cap for cap in available_captions
            if cap.type in required_types[:2]
            and cap.performance_score > LEVEL1_PERFORMANCE_THRESHOLD
            and cap.freshness_score > LEVEL1_FRESHNESS_THRESHOLD
            and cap.id not in exclude_ids
            and cap.id not in self._used_captions
        ]

        if level1_candidates:
            logger.debug(
                "Caption selection at Level 1",
                extra={
                    "send_type_key": send_type_key,
                    "candidates": len(level1_candidates),
                    "level": 1
                }
            )
            selected = self._select_best_caption(
                level1_candidates,
                send_type_key,
                persona
            )
            if selected:
                result = CaptionResult(
                    caption_score=selected,
                    needs_manual=False,
                    reason="Selected via fallback level 1 (exact type match with high scores)",
                    fallback_level=1
                )
                self._record_selection_metrics(start_time, result, send_type_key)
                return result

        # Level 2: Compatible type with good scores
        level2_candidates = [
            cap for cap in available_captions
            if cap.type in required_types
            and cap.performance_score > LEVEL2_PERFORMANCE_THRESHOLD
            and cap.freshness_score > LEVEL2_FRESHNESS_THRESHOLD
            and cap.id not in exclude_ids
            and cap.id not in self._used_captions
        ]

        if level2_candidates:
            log_fallback(
                logger,
                operation="select_caption",
                fallback_reason="No Level 1 candidates (exact type + high scores)",
                fallback_action="Using Level 2 candidates (compatible type + good scores)",
                send_type_key=send_type_key,
                candidates=len(level2_candidates),
                level=2
            )
            selected = self._select_best_caption(
                level2_candidates,
                send_type_key,
                persona
            )
            if selected:
                result = CaptionResult(
                    caption_score=selected,
                    needs_manual=False,
                    reason="Selected via fallback level 2 (compatible type with good scores)",
                    fallback_level=2
                )
                self._record_selection_metrics(start_time, result, send_type_key)
                return result

        # Level 3: Any usable type with acceptable scores
        level3_candidates = [
            cap for cap in available_captions
            if cap.performance_score > LEVEL3_PERFORMANCE_THRESHOLD
            and cap.id not in exclude_ids
            and cap.id not in self._used_captions
        ]

        if level3_candidates:
            log_fallback(
                logger,
                operation="select_caption",
                fallback_reason="No Level 1-2 candidates (type match requirements)",
                fallback_action="Using Level 3 candidates (any usable type, acceptable scores)",
                send_type_key=send_type_key,
                candidates=len(level3_candidates),
                level=3
            )
            selected = self._select_best_caption(
                level3_candidates,
                send_type_key,
                persona
            )
            if selected:
                result = CaptionResult(
                    caption_score=selected,
                    needs_manual=False,
                    reason="Selected via fallback level 3 (any usable type with acceptable scores)",
                    fallback_level=3
                )
                self._record_selection_metrics(start_time, result, send_type_key)
                return result

        # Level 4: Recently used but high-performing (allow reuse)
        level4_candidates = [
            cap for cap in available_captions
            if cap.performance_score > LEVEL4_PERFORMANCE_THRESHOLD
            and cap.id not in exclude_ids
        ]

        if level4_candidates:
            log_fallback(
                logger,
                operation="select_caption",
                fallback_reason="No unused candidates meeting criteria",
                fallback_action="Reusing high-performing caption",
                send_type_key=send_type_key,
                candidates=len(level4_candidates),
                level=4
            )
            selected = self._select_best_caption(
                level4_candidates,
                send_type_key,
                persona
            )
            # Mark as used again
            if selected:
                self._used_captions.add(selected.caption.id)
                result = CaptionResult(
                    caption_score=selected,
                    needs_manual=False,
                    reason="Selected via fallback level 4 (recently used but high-performing)",
                    fallback_level=4
                )
                self._record_selection_metrics(start_time, result, send_type_key)
                return result

        # Level 5: Any caption available (last resort)
        level5_candidates = [
            cap for cap in available_captions
            if cap.id not in exclude_ids
        ]

        if level5_candidates:
            log_fallback(
                logger,
                operation="select_caption",
                fallback_reason="Caption pool nearly exhausted",
                fallback_action="Using any available caption (last resort)",
                send_type_key=send_type_key,
                candidates=len(level5_candidates),
                level=5,
                severity="high"
            )
            selected = self._select_best_caption(
                level5_candidates,
                send_type_key,
                persona
            )
            if selected:
                result = CaptionResult(
                    caption_score=selected,
                    needs_manual=False,
                    reason="Selected via fallback level 5 (any caption available - last resort)",
                    fallback_level=5
                )
                self._record_selection_metrics(start_time, result, send_type_key)
                return result

        # Level 6: Manual caption required (all automated levels exhausted)
        logger.error(
            "No captions available after all fallback levels - manual caption required",
            extra={
                "send_type_key": send_type_key,
                "creator_id": creator_id,
                "total_available": len(available_captions),
                "excluded": len(exclude_ids) if exclude_ids else 0
            }
        )
        result = CaptionResult(
            caption_score=None,
            needs_manual=True,
            reason=f"No captions available for send_type={send_type_key}, creator={creator_id}. All 5 fallback levels exhausted.",
            fallback_level=6
        )
        self._record_selection_metrics(start_time, result, send_type_key)
        return result

    def _select_best_caption(
        self,
        candidates: list[Caption],
        send_type_key: str,
        persona: str
    ) -> CaptionScore | None:
        """Select best caption from candidates using scoring.

        Args:
            candidates: List of candidate captions
            send_type_key: Send type key
            persona: Creator persona

        Returns:
            Highest scoring caption or None
        """
        if not candidates:
            return None

        scored_captions = [
            self.calculate_score(cap, send_type_key, persona)
            for cap in candidates
        ]

        # Sort by total score descending
        scored_captions.sort(key=lambda x: x.total_score, reverse=True)

        best_caption = scored_captions[0]

        # Track usage
        self._used_captions.add(best_caption.caption.id)
        caption_type = best_caption.caption.type
        self._type_usage_count[caption_type] = (
            self._type_usage_count.get(caption_type, 0) + 1
        )

        return best_caption

    def calculate_score(
        self,
        caption: Caption,
        send_type_key: str,
        persona: str = "playful"
    ) -> CaptionScore:
        """Calculate comprehensive score for caption.

        Args:
            caption: Caption to score
            send_type_key: Send type key
            persona: Creator persona

        Returns:
            CaptionScore with total and component breakdown
        """
        components = {}

        # Freshness score (40%) - PRIORITIZED
        components["freshness"] = caption.freshness_score * self.WEIGHTS["freshness"]

        # Performance score (35%)
        components["performance"] = caption.performance_score * self.WEIGHTS["performance"]

        # Type priority score (15%)
        type_score = self._calculate_type_priority(caption.type, send_type_key)
        components["type_priority"] = type_score * self.WEIGHTS["type_priority"]

        # Diversity score (5%)
        diversity_score = self._calculate_diversity_score(caption.type)
        components["diversity"] = diversity_score * self.WEIGHTS["diversity"]

        # Persona fit score (5%) - tie-breaker only
        persona_score = self._calculate_persona_fit(caption, persona)
        components["persona"] = persona_score * self.WEIGHTS["persona"]

        # Calculate total
        total_score = sum(components.values())

        return CaptionScore(
            caption=caption,
            total_score=total_score,
            components=components
        )

    def _calculate_type_priority(
        self,
        caption_type: str,
        send_type_key: str
    ) -> float:
        """Calculate type priority score based on position in requirements.

        Args:
            caption_type: Caption type
            send_type_key: Send type key

        Returns:
            Score from 0-100 based on priority position
        """
        # Also check resolved type for deprecated send types
        resolved_type = self._resolve_send_type(send_type_key)
        required_types = self.TYPE_REQUIREMENTS.get(
            send_type_key,
            self.TYPE_REQUIREMENTS.get(resolved_type, [])
        )

        if not required_types:
            return TYPE_PRIORITY_NEUTRAL_SCORE

        if caption_type not in required_types:
            return TYPE_PRIORITY_NON_MATCH_SCORE

        # Higher score for higher priority (earlier in list)
        position = required_types.index(caption_type)
        max_position = len(required_types) - 1

        # Convert position to score (first position = max, last = max - range)
        score = TYPE_PRIORITY_MAX_SCORE - (position / max(max_position, 1)) * TYPE_PRIORITY_SCORE_RANGE

        return score

    def _calculate_persona_fit(
        self,
        caption: Caption,
        persona: str
    ) -> float:
        """Calculate persona compatibility score.

        Args:
            caption: Caption to evaluate
            persona: Creator persona

        Returns:
            Score from 0-100 based on persona fit
        """
        compatible_types = self.PERSONA_COMPATIBILITY.get(persona, [])

        if not compatible_types:
            return PERSONA_FIT_NEUTRAL_SCORE

        # Check if caption type matches persona
        if caption.type in compatible_types:
            return PERSONA_FIT_EXACT_MATCH_SCORE

        # Check if tone matches persona
        if caption.tone in compatible_types:
            return PERSONA_FIT_TONE_MATCH_SCORE

        # Default moderate score
        return PERSONA_FIT_DEFAULT_SCORE

    def _calculate_diversity_score(self, caption_type: str) -> float:
        """Calculate diversity score to prevent overuse of same type.

        Args:
            caption_type: Caption type

        Returns:
            Score from 0-100 (higher for less-used types)
        """
        usage_count = self._type_usage_count.get(caption_type, 0)

        # Penalize frequently used types
        if usage_count == 0:
            return DIVERSITY_MAX_SCORE
        elif usage_count < DIVERSITY_PENALTY_THRESHOLD:
            return DIVERSITY_MAX_SCORE - (usage_count * DIVERSITY_INITIAL_PENALTY_PER_USE)
        else:
            return max(
                DIVERSITY_MIN_SCORE,
                DIVERSITY_MAX_SCORE - (usage_count * DIVERSITY_CONTINUED_PENALTY_PER_USE)
            )

    def reset_usage_tracking(self) -> None:
        """Reset usage tracking for new schedule generation."""
        self._used_captions.clear()
        self._type_usage_count.clear()

    def get_usage_stats(self) -> dict[str, Any]:
        """Get current usage statistics.

        Returns:
            Dictionary with usage metrics
        """
        return {
            "total_used": len(self._used_captions),
            "type_distribution": dict(self._type_usage_count),
            "unique_types": len(self._type_usage_count),
        }
