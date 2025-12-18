"""
Extended tests for caption_matcher module to increase coverage.

Tests cover:
- Edge cases for fallback levels 3-6
- _record_selection_metrics (missing coverage)
- Deprecated send type handling
- Empty candidate lists
- Usage tracking edge cases
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.matching.caption_matcher import (
    Caption,
    CaptionMatcher,
    CaptionResult,
    CaptionScore,
    LEVEL1_PERFORMANCE_THRESHOLD,
    LEVEL1_FRESHNESS_THRESHOLD,
    LEVEL2_PERFORMANCE_THRESHOLD,
    LEVEL2_FRESHNESS_THRESHOLD,
    LEVEL3_PERFORMANCE_THRESHOLD,
    LEVEL4_PERFORMANCE_THRESHOLD,
    TYPE_PRIORITY_NEUTRAL_SCORE,
    TYPE_PRIORITY_NON_MATCH_SCORE,
    PERSONA_FIT_EXACT_MATCH_SCORE,
    PERSONA_FIT_TONE_MATCH_SCORE,
    PERSONA_FIT_DEFAULT_SCORE,
    PERSONA_FIT_NEUTRAL_SCORE,
    DIVERSITY_MAX_SCORE,
    DIVERSITY_MIN_SCORE,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def matcher():
    """Create CaptionMatcher instance."""
    return CaptionMatcher()


@pytest.fixture
def high_score_caption():
    """Caption with high scores for Level 1."""
    return Caption(
        id=1,
        text="CONGRATS! Exclusive content just for you!",
        type="ppv_unlock",
        performance_score=85.0,
        freshness_score=90.0,
        content_type="video",
        tone="flirty",
    )


@pytest.fixture
def medium_score_caption():
    """Caption with medium scores for Level 2."""
    return Caption(
        id=2,
        text="Check out this special content!",
        type="exclusive",
        performance_score=60.0,
        freshness_score=50.0,
        content_type="video",
        tone="playful",
    )


@pytest.fixture
def low_score_caption():
    """Caption with low scores for Level 3-4."""
    return Caption(
        id=3,
        text="Hey there!",
        type="casual",
        performance_score=45.0,
        freshness_score=30.0,
        content_type="none",
        tone="friendly",
    )


@pytest.fixture
def very_low_score_caption():
    """Caption with very low scores for Level 5."""
    return Caption(
        id=4,
        text="Simple message",
        type="unknown",
        performance_score=20.0,
        freshness_score=10.0,
        content_type="none",
        tone="neutral",
    )


# =============================================================================
# Caption Dataclass Tests
# =============================================================================


class TestCaptionDataclass:
    """Tests for Caption dataclass."""

    def test_caption_defaults(self):
        """Test Caption default values."""
        caption = Caption(
            id=1,
            text="Test",
            type="test",
            performance_score=50.0,
            freshness_score=50.0,
        )
        assert caption.emoji_level == 3
        assert caption.slang_level == 3
        assert caption.tone == "neutral"
        assert caption.last_used_date is None
        assert caption.content_type is None

    def test_caption_is_frozen(self):
        """Test Caption is immutable."""
        caption = Caption(
            id=1,
            text="Test",
            type="test",
            performance_score=50.0,
            freshness_score=50.0,
        )
        with pytest.raises(Exception):
            caption.text = "Modified"


# =============================================================================
# CaptionResult Dataclass Tests
# =============================================================================


class TestCaptionResultDataclass:
    """Tests for CaptionResult dataclass."""

    def test_caption_result_needs_manual(self):
        """Test CaptionResult for manual fallback."""
        result = CaptionResult(
            caption_score=None,
            needs_manual=True,
            reason="No captions available",
            fallback_level=6,
        )
        assert result.needs_manual is True
        assert result.caption_score is None
        assert result.fallback_level == 6


# =============================================================================
# Fallback Level Tests
# =============================================================================


class TestFallbackLevels:
    """Tests for fallback level progression."""

    def test_level1_exact_match_high_scores(self, matcher, high_score_caption):
        """Test Level 1 selection with exact type match and high scores."""
        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[high_score_caption],
            persona="playful",
        )

        assert result.fallback_level == 1
        assert result.needs_manual is False
        assert "level 1" in result.reason.lower()

    def test_level2_compatible_type_good_scores(self, matcher, medium_score_caption):
        """Test Level 2 selection with compatible type and good scores."""
        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[medium_score_caption],
            persona="playful",
        )

        assert result.fallback_level == 2
        assert result.needs_manual is False

    def test_level3_any_usable_type(self, matcher, low_score_caption):
        """Test Level 3 selection with any usable type."""
        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[low_score_caption],
            persona="playful",
        )

        assert result.fallback_level == 3
        assert result.needs_manual is False

    def test_level4_recently_used_high_performing(self, matcher):
        """Test Level 4 selection with recently used high-performing caption."""
        # Create a caption that fails Level 3 threshold but passes Level 4
        caption = Caption(
            id=100,
            text="High performer but recently used",
            type="unknown",
            performance_score=65.0,  # Above LEVEL4 threshold (60)
            freshness_score=5.0,     # Very low freshness (recently used)
        )

        # Mark caption as used so Level 3 doesn't select it
        matcher._used_captions.add(100)

        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[caption],
            persona="playful",
        )

        assert result.fallback_level == 4
        assert result.needs_manual is False

    def test_level5_any_caption_available(self, matcher, very_low_score_caption):
        """Test Level 5 selection as last resort."""
        # Mark caption as used
        matcher._used_captions.add(very_low_score_caption.id)

        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[very_low_score_caption],
            persona="playful",
        )

        assert result.fallback_level == 5
        assert result.needs_manual is False

    def test_level6_manual_required_empty_pool(self, matcher):
        """Test Level 6 manual required with empty pool."""
        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[],
            persona="playful",
        )

        assert result.fallback_level == 6
        assert result.needs_manual is True
        assert result.caption_score is None

    def test_level6_manual_required_all_excluded(self, matcher, high_score_caption):
        """Test Level 6 manual required when all captions excluded."""
        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[high_score_caption],
            exclude_ids={high_score_caption.id},
            persona="playful",
        )

        assert result.fallback_level == 6
        assert result.needs_manual is True


# =============================================================================
# Deprecated Send Type Tests
# =============================================================================


class TestDeprecatedSendTypes:
    """Tests for deprecated send type handling."""

    def test_ppv_video_deprecated(self, matcher, high_score_caption):
        """Test ppv_video is handled as deprecated."""
        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_video",
            available_captions=[high_score_caption],
            persona="playful",
        )

        assert result.needs_manual is False
        # Should still work via ppv_unlock requirements

    def test_ppv_message_deprecated(self, matcher, high_score_caption):
        """Test ppv_message is handled as deprecated."""
        result = matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_message",
            available_captions=[high_score_caption],
            persona="playful",
        )

        assert result.needs_manual is False

    def test_resolve_send_type(self, matcher):
        """Test _resolve_send_type handles deprecated types."""
        resolved = matcher._resolve_send_type("ppv_video")
        assert resolved == "ppv_unlock"

        resolved = matcher._resolve_send_type("ppv_message")
        assert resolved == "ppv_unlock"

        resolved = matcher._resolve_send_type("ppv_unlock")
        assert resolved == "ppv_unlock"


# =============================================================================
# Type Priority Tests
# =============================================================================


class TestTypePriority:
    """Tests for type priority calculation."""

    def test_first_priority_highest_score(self, matcher):
        """Test first position type gets highest score."""
        # ppv_unlock is first in ppv_unlock requirements
        score = matcher._calculate_type_priority("ppv_unlock", "ppv_unlock")
        assert score == 100.0  # TYPE_PRIORITY_MAX_SCORE

    def test_lower_priority_lower_score(self, matcher):
        """Test lower position types get lower scores."""
        # exclusive is 3rd in ppv_unlock requirements
        score = matcher._calculate_type_priority("exclusive", "ppv_unlock")
        assert 60.0 <= score <= 80.0  # Somewhere below max

    def test_non_match_gets_low_score(self, matcher):
        """Test non-matching type gets low score."""
        score = matcher._calculate_type_priority("random_type", "ppv_unlock")
        assert score == TYPE_PRIORITY_NON_MATCH_SCORE

    def test_unknown_send_type_neutral_score(self, matcher):
        """Test unknown send type returns neutral score."""
        score = matcher._calculate_type_priority("any_type", "unknown_send_type")
        assert score == TYPE_PRIORITY_NEUTRAL_SCORE


# =============================================================================
# Persona Fit Tests
# =============================================================================


class TestPersonaFit:
    """Tests for persona fit calculation."""

    def test_exact_type_match(self, matcher):
        """Test exact type match gives max score."""
        caption = Caption(
            id=1,
            text="Test",
            type="friendly",  # Matches girl_next_door
            performance_score=50.0,
            freshness_score=50.0,
            tone="neutral",
        )
        score = matcher._calculate_persona_fit(caption, "girl_next_door")
        assert score == PERSONA_FIT_EXACT_MATCH_SCORE

    def test_tone_match(self, matcher):
        """Test tone match gives high score."""
        caption = Caption(
            id=1,
            text="Test",
            type="unknown",
            performance_score=50.0,
            freshness_score=50.0,
            tone="playful",  # Matches girl_next_door tones
        )
        score = matcher._calculate_persona_fit(caption, "girl_next_door")
        assert score == PERSONA_FIT_TONE_MATCH_SCORE

    def test_no_match_default_score(self, matcher):
        """Test no match gives default score."""
        caption = Caption(
            id=1,
            text="Test",
            type="unknown",
            performance_score=50.0,
            freshness_score=50.0,
            tone="weird",
        )
        score = matcher._calculate_persona_fit(caption, "girl_next_door")
        assert score == PERSONA_FIT_DEFAULT_SCORE

    def test_unknown_persona_neutral_score(self, matcher):
        """Test unknown persona returns neutral score."""
        caption = Caption(
            id=1,
            text="Test",
            type="any",
            performance_score=50.0,
            freshness_score=50.0,
        )
        score = matcher._calculate_persona_fit(caption, "unknown_persona")
        assert score == PERSONA_FIT_NEUTRAL_SCORE


# =============================================================================
# Diversity Score Tests
# =============================================================================


class TestDiversityScore:
    """Tests for diversity score calculation."""

    def test_unused_type_max_score(self, matcher):
        """Test unused type gets max diversity score."""
        score = matcher._calculate_diversity_score("never_used_type")
        assert score == DIVERSITY_MAX_SCORE

    def test_used_once_penalty(self, matcher):
        """Test used once applies initial penalty."""
        matcher._type_usage_count["used_type"] = 1
        score = matcher._calculate_diversity_score("used_type")
        assert score == DIVERSITY_MAX_SCORE - 10  # DIVERSITY_INITIAL_PENALTY_PER_USE

    def test_heavy_usage_continued_penalty(self, matcher):
        """Test heavy usage applies continued penalty."""
        matcher._type_usage_count["heavy_type"] = 10
        score = matcher._calculate_diversity_score("heavy_type")
        # Should be near minimum
        assert score <= DIVERSITY_MAX_SCORE - 50
        assert score >= DIVERSITY_MIN_SCORE

    def test_minimum_score_floor(self, matcher):
        """Test diversity score has minimum floor."""
        matcher._type_usage_count["overused_type"] = 100
        score = matcher._calculate_diversity_score("overused_type")
        assert score == DIVERSITY_MIN_SCORE


# =============================================================================
# Usage Tracking Tests
# =============================================================================


class TestUsageTracking:
    """Tests for usage tracking functionality."""

    def test_reset_clears_tracking(self, matcher, high_score_caption):
        """Test reset clears all tracking."""
        # Use some captions
        matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[high_score_caption],
            persona="playful",
        )

        # Verify something was tracked
        stats = matcher.get_usage_stats()
        assert stats["total_used"] > 0

        # Reset
        matcher.reset_usage_tracking()

        # Verify cleared
        stats = matcher.get_usage_stats()
        assert stats["total_used"] == 0
        assert stats["unique_types"] == 0

    def test_get_usage_stats_structure(self, matcher, high_score_caption):
        """Test usage stats structure."""
        matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[high_score_caption],
            persona="playful",
        )

        stats = matcher.get_usage_stats()
        assert "total_used" in stats
        assert "type_distribution" in stats
        assert "unique_types" in stats

    def test_type_distribution_tracked(self, matcher, high_score_caption):
        """Test type distribution is tracked correctly."""
        matcher.select_caption(
            creator_id="creator_123",
            send_type_key="ppv_unlock",
            available_captions=[high_score_caption],
            persona="playful",
        )

        stats = matcher.get_usage_stats()
        assert high_score_caption.type in stats["type_distribution"]


# =============================================================================
# Calculate Score Tests
# =============================================================================


class TestCalculateScore:
    """Tests for score calculation."""

    def test_score_components_present(self, matcher, high_score_caption):
        """Test score has all components."""
        score = matcher.calculate_score(high_score_caption, "ppv_unlock", "playful")

        assert "freshness" in score.components
        assert "performance" in score.components
        assert "type_priority" in score.components
        assert "diversity" in score.components
        assert "persona" in score.components

    def test_total_score_is_sum(self, matcher, high_score_caption):
        """Test total score is sum of components."""
        score = matcher.calculate_score(high_score_caption, "ppv_unlock", "playful")

        expected_total = sum(score.components.values())
        assert abs(score.total_score - expected_total) < 0.01

    def test_weights_sum_to_one(self, matcher):
        """Test scoring weights sum to 1.0."""
        total_weight = sum(matcher.WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.01


# =============================================================================
# Select Best Caption Tests
# =============================================================================


class TestSelectBestCaption:
    """Tests for _select_best_caption method."""

    def test_empty_candidates_returns_none(self, matcher):
        """Test empty candidates returns None."""
        result = matcher._select_best_caption([], "ppv_unlock", "playful")
        assert result is None

    def test_selects_highest_scoring(self, matcher, high_score_caption, low_score_caption):
        """Test selects highest scoring caption."""
        result = matcher._select_best_caption(
            [low_score_caption, high_score_caption],
            "ppv_unlock",
            "playful"
        )

        assert result is not None
        assert result.caption.id == high_score_caption.id

    def test_tracks_usage_after_selection(self, matcher, high_score_caption):
        """Test tracks usage after selection."""
        assert high_score_caption.id not in matcher._used_captions

        matcher._select_best_caption(
            [high_score_caption],
            "ppv_unlock",
            "playful"
        )

        assert high_score_caption.id in matcher._used_captions


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_level_thresholds_descending(self):
        """Test level thresholds descend appropriately."""
        assert LEVEL1_PERFORMANCE_THRESHOLD > LEVEL2_PERFORMANCE_THRESHOLD
        assert LEVEL2_PERFORMANCE_THRESHOLD > LEVEL3_PERFORMANCE_THRESHOLD
        assert LEVEL1_FRESHNESS_THRESHOLD > LEVEL2_FRESHNESS_THRESHOLD

    def test_type_requirements_cover_all_send_types(self, matcher):
        """Test TYPE_REQUIREMENTS covers all main send types."""
        required_types = [
            "ppv_unlock", "ppv_wall", "tip_goal", "vip_program",
            "game_post", "bundle", "flash_bundle", "snapchat_bundle",
            "first_to_tip", "link_drop", "wall_link_drop",
            "bump_normal", "bump_descriptive", "bump_text_only",
            "bump_flyer", "dm_farm", "like_farm", "live_promo",
            "renew_on_post", "renew_on_message", "ppv_followup",
            "expired_winback",
        ]

        for send_type in required_types:
            assert send_type in matcher.TYPE_REQUIREMENTS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
