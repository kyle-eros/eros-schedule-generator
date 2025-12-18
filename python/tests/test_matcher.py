"""
Unit tests for CaptionMatcher.

Tests caption selection, freshness scoring, performance scoring,
and persona matching.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.matching.caption_matcher import (
    Caption,
    CaptionMatcher,
    CaptionScore,
    LEVEL1_PERFORMANCE_THRESHOLD,
    LEVEL1_FRESHNESS_THRESHOLD,
    LEVEL2_PERFORMANCE_THRESHOLD,
    LEVEL2_FRESHNESS_THRESHOLD,
    TYPE_PRIORITY_NEUTRAL_SCORE,
    TYPE_PRIORITY_NON_MATCH_SCORE,
    TYPE_PRIORITY_MAX_SCORE,
    PERSONA_FIT_NEUTRAL_SCORE,
    PERSONA_FIT_EXACT_MATCH_SCORE,
    DIVERSITY_MAX_SCORE,
    DIVERSITY_MIN_SCORE,
)


class TestCaptionModel:
    """Tests for Caption dataclass."""

    def test_caption_creation_minimal(self):
        """Test Caption creation with minimal fields."""
        caption = Caption(
            id=1,
            text="Test caption",
            type="ppv_unlock",
            performance_score=80.0,
            freshness_score=90.0,
        )

        assert caption.id == 1
        assert caption.text == "Test caption"
        assert caption.type == "ppv_unlock"

    def test_caption_creation_full(self):
        """Test Caption creation with all fields."""
        caption = Caption(
            id=1,
            text="Full caption",
            type="ppv_unlock",
            performance_score=85.0,
            freshness_score=90.0,
            last_used_date=datetime(2025, 11, 1),
            content_type="video",
            emoji_level=3,
            slang_level=2,
            tone="flirty",
        )

        assert caption.emoji_level == 3
        assert caption.slang_level == 2
        assert caption.tone == "flirty"

    def test_caption_immutable(self):
        """Test Caption is immutable (frozen)."""
        caption = Caption(
            id=1,
            text="Test",
            type="casual",
            performance_score=50.0,
            freshness_score=50.0,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            caption.text = "Modified"


class TestCaptionSelection:
    """Tests for caption selection logic."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        """Fresh matcher with reset tracking."""
        m = CaptionMatcher()
        m.reset_usage_tracking()
        return m

    def test_select_caption_returns_caption_score(self, matcher, sample_captions):
        """Test select_caption returns CaptionResult with CaptionScore."""
        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_unlock",
            available_captions=sample_captions,
        )

        # select_caption returns CaptionResult, not CaptionScore directly
        assert result is not None
        assert result.needs_manual is False
        assert result.caption_score is not None
        assert isinstance(result.caption_score, CaptionScore)
        assert result.caption_score.caption is not None
        assert result.caption_score.total_score > 0

    def test_select_caption_empty_list_returns_manual_fallback(self, matcher):
        """Test select_caption returns manual fallback for empty list."""
        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_unlock",
            available_captions=[],
        )

        # Empty caption list returns CaptionResult with needs_manual=True
        assert result is not None
        assert result.needs_manual is True
        assert result.caption_score is None
        assert result.fallback_level == 6

    def test_select_caption_tracks_usage(self, matcher, sample_captions):
        """Test selected caption is tracked as used."""
        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_unlock",
            available_captions=sample_captions,
        )

        assert result.caption_score.caption.id in matcher._used_captions

    def test_select_caption_excludes_specified_ids(self, matcher, sample_captions):
        """Test exclude_ids parameter works."""
        # Exclude first caption
        exclude_ids = {sample_captions[0].id}

        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_unlock",
            available_captions=sample_captions,
            exclude_ids=exclude_ids,
        )

        assert result.caption_score.caption.id not in exclude_ids

    def test_select_caption_prefers_high_scores(self, matcher):
        """Test selection prefers higher scoring captions."""
        captions = [
            Caption(id=1, text="Low score", type="ppv_unlock",
                    performance_score=30.0, freshness_score=30.0),
            Caption(id=2, text="High score", type="ppv_unlock",
                    performance_score=95.0, freshness_score=95.0),
        ]

        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_unlock",
            available_captions=captions,
        )

        # Should select the higher scoring caption
        assert result.caption_score.caption.id == 2

    def test_select_caption_fallback_levels(self, matcher):
        """Test fallback through selection levels."""
        # Create captions that fail Level 1 criteria
        captions = [
            Caption(id=1, text="Level 3 caption", type="generic",
                    performance_score=45.0, freshness_score=45.0),
        ]

        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_unlock",
            available_captions=captions,
        )

        # Should still return a caption (via fallback)
        assert result is not None


class TestTypePriorityScoring:
    """Tests for type priority scoring."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        return CaptionMatcher()

    def test_type_priority_first_in_list(self, matcher):
        """Test first type in requirements gets max score."""
        # ppv_unlock is first in ppv_unlock requirements
        score = matcher._calculate_type_priority("ppv_unlock", "ppv_unlock")
        assert score == TYPE_PRIORITY_MAX_SCORE

    def test_type_priority_last_in_list(self, matcher):
        """Test last type in requirements gets lower score."""
        # urgent is last in ppv_unlock requirements
        score = matcher._calculate_type_priority("urgent", "ppv_unlock")
        assert score < TYPE_PRIORITY_MAX_SCORE
        assert score > TYPE_PRIORITY_NON_MATCH_SCORE

    def test_type_priority_not_in_list(self, matcher):
        """Test type not in requirements gets low score."""
        score = matcher._calculate_type_priority("unrelated_type", "ppv_unlock")
        assert score == TYPE_PRIORITY_NON_MATCH_SCORE

    def test_type_priority_unknown_send_type(self, matcher):
        """Test unknown send_type returns neutral score."""
        score = matcher._calculate_type_priority("any_type", "unknown_send_type")
        assert score == TYPE_PRIORITY_NEUTRAL_SCORE

    @pytest.mark.parametrize("send_type_key", [
        # Revenue (9 types)
        "ppv_unlock", "ppv_wall", "tip_goal", "vip_program", "game_post",
        "bundle", "flash_bundle", "snapchat_bundle", "first_to_tip",
        # Engagement (9 types)
        "link_drop", "wall_link_drop", "bump_normal", "bump_descriptive",
        "bump_text_only", "bump_flyer", "dm_farm", "like_farm", "live_promo",
        # Retention (4 types)
        "renew_on_post", "renew_on_message", "ppv_followup", "expired_winback",
    ])
    def test_type_requirements_exist_for_all_22(self, matcher, send_type_key):
        """Test type requirements exist for all 22 send types."""
        assert send_type_key in matcher.TYPE_REQUIREMENTS


class TestPersonaFitScoring:
    """Tests for persona fit scoring."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        return CaptionMatcher()

    def test_persona_exact_match(self, matcher):
        """Test exact persona type match gets high score."""
        caption = Caption(
            id=1, text="Test", type="seductive",
            performance_score=80.0, freshness_score=80.0,
            tone="neutral",
        )

        score = matcher._calculate_persona_fit(caption, "seductress")
        assert score == PERSONA_FIT_EXACT_MATCH_SCORE

    def test_persona_tone_match(self, matcher):
        """Test tone match gets good score."""
        caption = Caption(
            id=1, text="Test", type="generic",
            performance_score=80.0, freshness_score=80.0,
            tone="seductive",
        )

        score = matcher._calculate_persona_fit(caption, "seductress")
        assert score >= 75.0

    def test_persona_no_match(self, matcher):
        """Test no match gets lower score."""
        caption = Caption(
            id=1, text="Test", type="formal",
            performance_score=80.0, freshness_score=80.0,
            tone="business",
        )

        score = matcher._calculate_persona_fit(caption, "seductress")
        assert score < PERSONA_FIT_EXACT_MATCH_SCORE

    def test_persona_unknown_returns_neutral(self, matcher):
        """Test unknown persona returns neutral score."""
        caption = Caption(
            id=1, text="Test", type="casual",
            performance_score=80.0, freshness_score=80.0,
        )

        score = matcher._calculate_persona_fit(caption, "unknown_persona")
        assert score == PERSONA_FIT_NEUTRAL_SCORE

    @pytest.mark.parametrize("persona", [
        "girl_next_door", "seductress", "professional", "playful", "grateful",
    ])
    def test_all_personas_have_compatibility(self, matcher, persona):
        """Test all defined personas have compatibility entries."""
        assert persona in matcher.PERSONA_COMPATIBILITY


class TestDiversityScoring:
    """Tests for diversity scoring."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        m = CaptionMatcher()
        m.reset_usage_tracking()
        return m

    def test_diversity_unused_type_max(self, matcher):
        """Test unused type gets max diversity score."""
        score = matcher._calculate_diversity_score("new_type")
        assert score == DIVERSITY_MAX_SCORE

    def test_diversity_decreases_with_usage(self, matcher):
        """Test diversity score decreases with usage."""
        matcher._type_usage_count["test_type"] = 0
        score_0 = matcher._calculate_diversity_score("test_type")

        matcher._type_usage_count["test_type"] = 3
        score_3 = matcher._calculate_diversity_score("test_type")

        matcher._type_usage_count["test_type"] = 6
        score_6 = matcher._calculate_diversity_score("test_type")

        assert score_0 > score_3 > score_6

    def test_diversity_minimum_floor(self, matcher):
        """Test diversity score has minimum floor."""
        matcher._type_usage_count["overused"] = 100
        score = matcher._calculate_diversity_score("overused")

        assert score >= DIVERSITY_MIN_SCORE


class TestCalculateScore:
    """Tests for composite score calculation."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        m = CaptionMatcher()
        m.reset_usage_tracking()
        return m

    def test_calculate_score_returns_caption_score(self, matcher):
        """Test calculate_score returns CaptionScore."""
        caption = Caption(
            id=1, text="Test", type="ppv_unlock",
            performance_score=80.0, freshness_score=80.0,
        )

        result = matcher.calculate_score(caption, "ppv_unlock")
        assert isinstance(result, CaptionScore)

    def test_calculate_score_has_all_components(self, matcher):
        """Test CaptionScore has all component scores."""
        caption = Caption(
            id=1, text="Test", type="ppv_unlock",
            performance_score=80.0, freshness_score=80.0,
        )

        result = matcher.calculate_score(caption, "ppv_unlock")

        assert "performance" in result.components
        assert "freshness" in result.components
        assert "type_priority" in result.components
        assert "persona" in result.components
        assert "diversity" in result.components

    def test_calculate_score_weights_sum_to_one(self, matcher):
        """Test scoring weights sum to 1.0."""
        total_weight = sum(matcher.WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_calculate_score_total_reasonable(self, matcher):
        """Test total score is in reasonable range."""
        caption = Caption(
            id=1, text="Test", type="ppv_unlock",
            performance_score=80.0, freshness_score=80.0,
        )

        result = matcher.calculate_score(caption, "ppv_unlock")

        # Total should be between 0 and 100
        assert 0 <= result.total_score <= 100


class TestUsageTracking:
    """Tests for usage tracking."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        return CaptionMatcher()

    def test_reset_clears_used_captions(self, matcher):
        """Test reset clears used captions set."""
        matcher._used_captions.add(1)
        matcher._used_captions.add(2)

        matcher.reset_usage_tracking()

        assert len(matcher._used_captions) == 0

    def test_reset_clears_type_usage(self, matcher):
        """Test reset clears type usage count."""
        matcher._type_usage_count["test"] = 5

        matcher.reset_usage_tracking()

        assert len(matcher._type_usage_count) == 0

    def test_get_usage_stats_structure(self, matcher):
        """Test usage stats has expected structure."""
        stats = matcher.get_usage_stats()

        assert "total_used" in stats
        assert "type_distribution" in stats
        assert "unique_types" in stats

    def test_get_usage_stats_accurate(self, matcher):
        """Test usage stats are accurate."""
        matcher._used_captions.update({1, 2, 3})
        matcher._type_usage_count["ppv_unlock"] = 2
        matcher._type_usage_count["casual"] = 1

        stats = matcher.get_usage_stats()

        assert stats["total_used"] == 3
        assert stats["unique_types"] == 2
        assert stats["type_distribution"]["ppv_unlock"] == 2


class TestFallbackLevels:
    """Tests for 5-level fallback strategy."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        m = CaptionMatcher()
        m.reset_usage_tracking()
        return m

    def test_level1_exact_type_high_scores(self, matcher):
        """Test Level 1 selects exact type with high scores."""
        captions = [
            Caption(id=1, text="Level 1 match", type="ppv_unlock",
                    performance_score=LEVEL1_PERFORMANCE_THRESHOLD + 10,
                    freshness_score=LEVEL1_FRESHNESS_THRESHOLD + 10),
            Caption(id=2, text="Lower score", type="ppv_unlock",
                    performance_score=40.0, freshness_score=40.0),
        ]

        result = matcher.select_caption("test", "ppv_unlock", captions)
        assert result.caption_score.caption.id == 1

    def test_level5_any_caption(self, matcher):
        """Test Level 5 uses any available caption."""
        # Create a caption that fails all higher levels
        captions = [
            Caption(id=99, text="Last resort", type="completely_unrelated",
                    performance_score=10.0, freshness_score=10.0),
        ]

        result = matcher.select_caption("test", "ppv_unlock", captions)
        # Should still return something
        assert result is not None
        assert result.caption_score.caption.id == 99


class TestScoringThresholds:
    """Tests for scoring threshold constants."""

    def test_level1_thresholds(self):
        """Test Level 1 threshold values."""
        assert LEVEL1_PERFORMANCE_THRESHOLD == 70.0
        assert LEVEL1_FRESHNESS_THRESHOLD == 60.0

    def test_level2_thresholds(self):
        """Test Level 2 threshold values."""
        assert LEVEL2_PERFORMANCE_THRESHOLD == 50.0
        assert LEVEL2_FRESHNESS_THRESHOLD == 40.0

    def test_type_priority_scores(self):
        """Test type priority score constants."""
        assert TYPE_PRIORITY_NEUTRAL_SCORE == 50.0
        assert TYPE_PRIORITY_NON_MATCH_SCORE == 30.0
        assert TYPE_PRIORITY_MAX_SCORE == 100.0


class TestEdgeCases:
    """Edge case tests for matcher."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        m = CaptionMatcher()
        m.reset_usage_tracking()
        return m

    def test_single_caption_selection(self, matcher):
        """Test selection with only one caption."""
        captions = [
            Caption(id=1, text="Only caption", type="casual",
                    performance_score=50.0, freshness_score=50.0),
        ]

        result = matcher.select_caption("test", "bump_normal", captions)
        assert result is not None
        assert result.caption_score.caption.id == 1

    def test_all_captions_excluded(self, matcher, sample_captions):
        """Test all captions excluded returns manual fallback."""
        exclude_ids = {cap.id for cap in sample_captions}

        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_unlock",
            available_captions=sample_captions,
            exclude_ids=exclude_ids,
        )

        # When all captions are excluded, returns CaptionResult with needs_manual=True
        assert result is not None
        assert result.needs_manual is True
        assert result.caption_score is None
        assert result.fallback_level == 6

    def test_zero_score_captions(self, matcher):
        """Test handling of zero score captions."""
        captions = [
            Caption(id=1, text="Zero scores", type="casual",
                    performance_score=0.0, freshness_score=0.0),
        ]

        result = matcher.select_caption("test", "bump_normal", captions)
        # Should still work with zero scores
        assert result is not None

    def test_very_long_caption_text(self, matcher):
        """Test handling of very long caption text."""
        long_text = "x" * 10000
        captions = [
            Caption(id=1, text=long_text, type="ppv_unlock",
                    performance_score=80.0, freshness_score=80.0),
        ]

        result = matcher.select_caption("test", "ppv_unlock", captions)
        assert result is not None
        assert len(result.caption_score.caption.text) == 10000
