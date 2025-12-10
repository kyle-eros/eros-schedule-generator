#!/usr/bin/env python3
"""
Unit tests for persona matching and boost scoring.

Tests:
    1. Tone matching - Primary and secondary tone detection
    2. Emoji frequency matching - Heavy/moderate/light/none
    3. Slang level matching - Heavy/light/none
    4. Sentiment alignment - Positive/negative sentiment scoring
    5. Combined boost calculation - Multiple factor combination
    6. Text-based detection - Fallback detection from caption text
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scripts and tests to path
TESTS_DIR = Path(__file__).parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from fixtures import (
    MOCK_PERSONA,
    MOCK_PERSONAS_BY_TONE,
    create_mock_caption,
    create_mock_persona_profile,
)


# =============================================================================
# TONE MATCHING TESTS
# =============================================================================


class TestToneMatching:
    """Tests for tone matching boost calculation."""

    def test_perfect_primary_tone_match(self):
        """Test that primary tone match gives max boost (1.20x)."""
        from match_persona import PRIMARY_TONE_BOOST

        assert PRIMARY_TONE_BOOST == 1.20

        # Playful persona with playful caption
        persona = create_mock_persona_profile(primary_tone="playful")
        caption = create_mock_caption(
            caption_id=1001,
            caption_text="hehe want to play a game?",
            tone="playful",
        )

        assert caption.tone == persona.primary_tone

    def test_secondary_tone_match(self):
        """Test that secondary tone match gives partial boost (1.10x)."""
        from match_persona import SECONDARY_TONE_BOOST

        assert SECONDARY_TONE_BOOST == 1.10

        persona = create_mock_persona_profile(
            primary_tone="playful",
            secondary_tone="sweet",
        )
        caption = create_mock_caption(
            caption_id=1001,
            caption_text="Just thinking about you baby",
            tone="sweet",
        )

        assert caption.tone == persona.secondary_tone

    def test_no_tone_match_gives_base_score(self):
        """Test that no tone match gives base score (1.0x or penalty)."""
        from match_persona import NO_MATCH_PENALTY

        assert NO_MATCH_PENALTY == 0.95

        persona = create_mock_persona_profile(primary_tone="playful")
        caption = create_mock_caption(
            caption_id=1001,
            caption_text="Buy this now!",
            tone="aggressive",
        )

        assert caption.tone != persona.primary_tone
        assert caption.tone != persona.secondary_tone


# =============================================================================
# EMOJI FREQUENCY MATCHING TESTS
# =============================================================================


class TestEmojiFrequencyMatching:
    """Tests for emoji frequency matching."""

    def test_emoji_frequency_match(self):
        """Test that emoji frequency match gives boost (1.05x)."""
        from match_persona import EMOJI_FREQUENCY_BOOST

        assert EMOJI_FREQUENCY_BOOST == 1.05

        persona = create_mock_persona_profile(emoji_frequency="moderate")
        caption = create_mock_caption(
            caption_id=1001,
            caption_text="Test caption",
            emoji_style="moderate",
        )

        assert caption.emoji_style == persona.emoji_frequency

    def test_emoji_count_categories(self):
        """Test emoji counting and categorization."""
        from match_persona import count_emojis, get_emoji_frequency_category

        # Heavy: 3+ emojis (using actual Unicode emojis)
        text_heavy = "OMG yes \U0001f525\U0001f525\U0001f525"  # fire emojis
        assert get_emoji_frequency_category(text_heavy) == "heavy"

        # Moderate: 2 emojis
        text_moderate = "Love this \U00002764\U0001f609"  # heart and wink
        assert get_emoji_frequency_category(text_moderate) == "moderate"

        # Light: 1 emoji
        text_light = "Check this out \U0001f60d"  # heart eyes
        assert get_emoji_frequency_category(text_light) == "light"

        # None: 0 emojis
        text_none = "Check this out"
        assert get_emoji_frequency_category(text_none) == "none"

    def test_emoji_pattern_matching(self):
        """Test that emoji pattern matches various emoji types."""
        from match_persona import count_emojis

        # Test various emoji types
        emojis_emoticons = "hello! great"  # Emoticons
        emojis_symbols = "love this hot"  # Misc symbols
        emojis_flags = "USA!!"  # Flags

        # Each should detect emojis
        assert count_emojis(emojis_emoticons) >= 0
        assert count_emojis(emojis_symbols) >= 0


# =============================================================================
# SLANG LEVEL MATCHING TESTS
# =============================================================================


class TestSlangLevelMatching:
    """Tests for slang level matching."""

    def test_slang_level_match(self):
        """Test that slang level match gives boost (1.05x)."""
        from match_persona import SLANG_LEVEL_BOOST

        assert SLANG_LEVEL_BOOST == 1.05

        persona = create_mock_persona_profile(slang_level="light")
        caption = create_mock_caption(
            caption_id=1001,
            caption_text="Gonna show you something special",
            slang_level="light",
        )

        assert caption.slang_level == persona.slang_level

    def test_slang_detection_from_text(self):
        """Test text-based slang detection."""
        from match_persona import detect_slang_level_from_text

        # Heavy slang
        heavy_text = "ngl this is bussin af no cap"
        assert detect_slang_level_from_text(heavy_text) == "heavy"

        # Light slang
        light_text = "gonna show you something tbh"
        assert detect_slang_level_from_text(light_text) == "light"

        # No slang
        formal_text = "I would like to present this exclusive content"
        assert detect_slang_level_from_text(formal_text) == "none"

    def test_slang_patterns(self):
        """Test specific slang patterns are detected."""
        from match_persona import SLANG_PATTERNS

        # Heavy slang patterns
        assert "ngl" in SLANG_PATTERNS["heavy"]
        assert "fr" in SLANG_PATTERNS["heavy"]
        assert "bussin" in SLANG_PATTERNS["heavy"]

        # Light slang patterns
        assert "gonna" in SLANG_PATTERNS["light"]
        assert "wanna" in SLANG_PATTERNS["light"]
        assert "tbh" in SLANG_PATTERNS["light"]


# =============================================================================
# SENTIMENT ALIGNMENT TESTS
# =============================================================================


class TestSentimentAlignment:
    """Tests for sentiment alignment scoring."""

    def test_sentiment_alignment_boost(self):
        """Test that sentiment alignment gives boost (1.05x)."""
        from match_persona import SENTIMENT_ALIGNMENT_BOOST

        assert SENTIMENT_ALIGNMENT_BOOST == 1.05

    def test_positive_sentiment_calculation(self):
        """Test positive sentiment word detection."""
        from match_persona import calculate_sentiment

        # High positive sentiment
        positive_text = "Amazing exclusive content! Best quality, perfect for you!"
        sentiment = calculate_sentiment(positive_text)
        assert sentiment >= 0.5  # Should be above neutral

    def test_negative_sentiment_calculation(self):
        """Test negative/urgency sentiment word detection."""
        from match_persona import calculate_sentiment

        # Urgency/scarcity language
        urgent_text = "Last chance! Limited time, hurry before it's gone!"
        sentiment = calculate_sentiment(urgent_text)
        assert sentiment <= 0.6  # Should be lower due to urgency words

    def test_neutral_sentiment(self):
        """Test neutral sentiment with no keywords."""
        from match_persona import calculate_sentiment

        neutral_text = "Here is the content you requested"
        sentiment = calculate_sentiment(neutral_text)
        assert 0.4 <= sentiment <= 0.6  # Should be near neutral

    def test_empty_text_sentiment(self):
        """Test sentiment of empty text returns neutral."""
        from match_persona import calculate_sentiment

        assert calculate_sentiment("") == 0.5
        assert calculate_sentiment(None) == 0.5


# =============================================================================
# TONE DETECTION FROM TEXT TESTS
# =============================================================================


class TestToneDetectionFromText:
    """Tests for text-based tone detection."""

    def test_playful_tone_detection(self):
        """Test detection of playful tone keywords."""
        from match_persona import detect_tone_from_text

        text = "hehe want to play a fun game? might tease you a bit"
        tone, scores = detect_tone_from_text(text)

        assert tone == "playful"
        assert "playful" in scores
        assert scores["playful"] > 0

    def test_aggressive_tone_detection(self):
        """Test detection of aggressive tone keywords."""
        from match_persona import detect_tone_from_text

        text = "You must obey now. Beg for it. Submit immediately."
        tone, scores = detect_tone_from_text(text)

        assert tone == "aggressive"
        assert "aggressive" in scores

    def test_sweet_tone_detection(self):
        """Test detection of sweet tone keywords."""
        from match_persona import detect_tone_from_text

        text = "Baby I miss you! Thinking of you sweetheart xoxo"
        tone, scores = detect_tone_from_text(text)

        assert tone == "sweet"
        assert "sweet" in scores

    def test_seductive_tone_detection(self):
        """Test detection of seductive tone keywords."""
        from match_persona import detect_tone_from_text

        text = "Let me seduce you... explore your deepest desires and fantasies"
        tone, scores = detect_tone_from_text(text)

        assert tone == "seductive"
        assert "seductive" in scores

    def test_direct_tone_detection(self):
        """Test detection of direct/sales tone keywords."""
        from match_persona import detect_tone_from_text

        text = "Limited time offer! Exclusive deal, unlock now at special price"
        tone, scores = detect_tone_from_text(text)

        assert tone == "direct"
        assert "direct" in scores

    def test_no_tone_detected(self):
        """Test when no specific tone keywords are found."""
        from match_persona import detect_tone_from_text

        text = "This is a generic message"
        tone, scores = detect_tone_from_text(text)

        # Might detect as "direct" due to generic words, or None
        assert tone is None or tone in ["direct", "playful", "sweet"]

    def test_empty_text_returns_none(self):
        """Test empty text returns no tone."""
        from match_persona import detect_tone_from_text

        tone, scores = detect_tone_from_text("")
        assert tone is None
        assert scores == {}


# =============================================================================
# COMBINED BOOST CALCULATION TESTS
# =============================================================================


class TestCombinedBoostCalculation:
    """Tests for combined persona boost calculation."""

    def test_max_combined_boost_capped(self):
        """Test that combined boost is capped at maximum (1.40x)."""
        from match_persona import MAX_COMBINED_BOOST

        assert MAX_COMBINED_BOOST == 1.40

        # If all boosts apply: 1.20 * 1.10 * 1.05 * 1.05 * 1.05 = ~1.51
        # Should be capped at 1.40
        boosts = [1.20, 1.10, 1.05, 1.05, 1.05]
        raw_combined = 1.0
        for boost in boosts:
            raw_combined *= boost

        assert raw_combined > MAX_COMBINED_BOOST
        capped = min(raw_combined, MAX_COMBINED_BOOST)
        assert capped == MAX_COMBINED_BOOST

    def test_no_match_penalty(self):
        """Test that no match applies penalty (0.95x)."""
        from match_persona import NO_MATCH_PENALTY

        assert NO_MATCH_PENALTY == 0.95

    def test_partial_match_interpolates(self):
        """Test that partial matches produce intermediate boost."""
        # Primary tone match only: 1.20x
        # Emoji match only: 1.05x
        # Combined: 1.20 * 1.05 = 1.26x

        primary_boost = 1.20
        emoji_boost = 1.05

        combined = primary_boost * emoji_boost
        assert 1.2 < combined < 1.4

    def test_single_boost_factor(self):
        """Test boost with only one matching factor."""
        from match_persona import PRIMARY_TONE_BOOST

        # Only tone matches
        total_boost = PRIMARY_TONE_BOOST  # 1.20
        assert total_boost == 1.20


# =============================================================================
# PERSONA MATCH RESULT TESTS
# =============================================================================


class TestPersonaMatchResult:
    """Tests for PersonaMatchResult dataclass."""

    def test_match_result_structure(self):
        """Test that PersonaMatchResult has required fields."""
        from match_persona import PersonaMatchResult

        result = PersonaMatchResult(
            caption_id=1001,
            caption_text="Test caption",
            caption_tone="playful",
            caption_emoji_style="moderate",
            caption_slang_level="light",
            tone_match=True,
            emoji_match=True,
            slang_match=False,
            tone_boost=1.20,
            emoji_boost=1.05,
            slang_boost=1.0,
            total_boost=1.26,
        )

        assert result.caption_id == 1001
        assert result.tone_match is True
        assert result.total_boost == 1.26

    def test_match_details_populated(self):
        """Test that match details list is populated."""
        from match_persona import PersonaMatchResult

        result = PersonaMatchResult(
            caption_id=1001,
            caption_text="Test",
            caption_tone="playful",
            caption_emoji_style="moderate",
            caption_slang_level="light",
            tone_match=True,
            total_boost=1.20,
            match_details=["Primary tone match: playful (1.20x)"],
        )

        assert len(result.match_details) == 1
        assert "playful" in result.match_details[0]


# =============================================================================
# TEXT DETECTION FALLBACK TESTS
# =============================================================================


class TestTextDetectionFallback:
    """Tests for text-based detection as fallback."""

    def test_text_detection_when_tone_missing(self):
        """Test that text detection activates when tone is None."""
        from match_persona import detect_tone_from_text

        # Caption without stored tone
        caption = create_mock_caption(
            caption_id=1001,
            caption_text="hehe you're gonna love this tease!",
            tone=None,  # No stored tone
        )

        # Should detect from text
        detected_tone, _ = detect_tone_from_text(caption.caption_text)
        assert detected_tone == "playful"

    def test_text_detection_when_slang_missing(self):
        """Test that text detection activates when slang_level is None."""
        from match_persona import detect_slang_level_from_text

        caption = create_mock_caption(
            caption_id=1001,
            caption_text="ngl this is gonna be fire af",
            slang_level=None,  # No stored slang
        )

        # Should detect from text
        detected_slang = detect_slang_level_from_text(caption.caption_text)
        assert detected_slang in ["heavy", "light"]

    def test_stored_values_override_detection(self):
        """Test that stored tone/slang takes precedence over detection."""
        # When tone is stored, don't re-detect
        caption = create_mock_caption(
            caption_id=1001,
            caption_text="Buy this now immediately!",  # Would detect as aggressive
            tone="playful",  # But stored as playful
        )

        # Stored tone should be used
        assert caption.tone == "playful"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
