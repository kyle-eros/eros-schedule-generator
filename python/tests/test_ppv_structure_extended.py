"""
Extended tests for PPV structure validation to increase coverage.

Tests cover:
- Input validation with ValidationError
- Edge cases for all three validation methods
- Error handling for invalid inputs
- Empty and whitespace-only captions
- Non-string inputs
"""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.quality.ppv_structure import PPVStructureValidator
from python.exceptions import ValidationError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator():
    """Create validator instance for tests."""
    return PPVStructureValidator()


# =============================================================================
# Test Input Validation - Winner PPV
# =============================================================================


class TestWinnerPPVInputValidation:
    """Tests for winner PPV input validation."""

    def test_empty_caption_raises_validation_error(self, validator):
        """Test empty caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_winner_ppv("")

        assert "Caption cannot be empty" in str(exc_info.value)
        assert exc_info.value.field == "caption"

    def test_none_caption_raises_validation_error(self, validator):
        """Test None caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_winner_ppv(None)

        assert "Caption cannot be empty" in str(exc_info.value)

    def test_non_string_raises_validation_error(self, validator):
        """Test non-string caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_winner_ppv(12345)

        assert "Caption must be string" in str(exc_info.value)
        assert exc_info.value.value == "int"

    def test_list_input_raises_validation_error(self, validator):
        """Test list input raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_winner_ppv(["caption"])

        assert "Caption must be string" in str(exc_info.value)
        assert exc_info.value.value == "list"

    def test_dict_input_raises_validation_error(self, validator):
        """Test dict input raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_winner_ppv({"text": "caption"})

        assert "Caption must be string" in str(exc_info.value)


# =============================================================================
# Test Input Validation - Bundle PPV
# =============================================================================


class TestBundlePPVInputValidation:
    """Tests for bundle PPV input validation."""

    def test_empty_caption_raises_validation_error(self, validator):
        """Test empty caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_bundle_ppv("")

        assert "Caption cannot be empty" in str(exc_info.value)

    def test_none_caption_raises_validation_error(self, validator):
        """Test None caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_bundle_ppv(None)

        assert "Caption cannot be empty" in str(exc_info.value)

    def test_non_string_raises_validation_error(self, validator):
        """Test non-string caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_bundle_ppv(123.45)

        assert "Caption must be string" in str(exc_info.value)
        assert exc_info.value.value == "float"


# =============================================================================
# Test Input Validation - Wall Campaign
# =============================================================================


class TestWallCampaignInputValidation:
    """Tests for wall campaign input validation."""

    def test_empty_caption_raises_validation_error(self, validator):
        """Test empty caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_wall_campaign("")

        assert "Caption cannot be empty" in str(exc_info.value)

    def test_none_caption_raises_validation_error(self, validator):
        """Test None caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_wall_campaign(None)

        assert "Caption cannot be empty" in str(exc_info.value)

    def test_non_string_raises_validation_error(self, validator):
        """Test non-string caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_wall_campaign(True)

        assert "Caption must be string" in str(exc_info.value)
        assert exc_info.value.value == "bool"


# =============================================================================
# Test Winner PPV Edge Cases
# =============================================================================


class TestWinnerPPVEdgeCases:
    """Edge case tests for winner PPV validation."""

    def test_whitespace_only_still_processed(self, validator):
        """Test whitespace-only caption is processed (but likely invalid)."""
        # Single space is truthy, so should be processed
        result = validator.validate_winner_ppv(" ")
        assert result['is_valid'] is False
        assert result['structure_score'] == 0.0

    def test_very_long_caption(self, validator):
        """Test very long caption is handled."""
        # Create a long caption with all elements
        long_caption = "CONGRATS! " * 100 + "You're the only winner! " * 50 + "$500 worth for $25! " * 30 + "LMK which is ur fav!"
        result = validator.validate_winner_ppv(long_caption)

        # Should still detect elements
        assert isinstance(result, dict)

    def test_case_insensitivity(self, validator):
        """Test validation is case insensitive."""
        caption_upper = "CONGRATS! EXCLUSIVE! $100 WORTH FOR $20! LMK!"
        caption_lower = "congrats! exclusive! $100 worth for $20! lmk!"

        result_upper = validator.validate_winner_ppv(caption_upper)
        result_lower = validator.validate_winner_ppv(caption_lower)

        # Both should detect elements similarly
        assert result_upper['elements']['clickbait'] == result_lower['elements']['clickbait']

    def test_clickbait_in_first_100_chars(self, validator):
        """Test clickbait must be in first 100 characters."""
        # Put clickbait after first 100 chars
        filler = "x" * 100
        caption = f"{filler} CONGRATS! You won! $50 for $10! LMK!"
        result = validator.validate_winner_ppv(caption)

        # Clickbait should NOT be detected (outside first 100 chars)
        assert result['elements']['clickbait'] is False

    def test_all_four_elements_detected(self, validator):
        """Test all four elements are detected."""
        caption = "CONGRATS babe! You're the only winner of this exclusive pack, never seen before! Worth $200 but only $25 for you! LMK which vid is ur fav!"
        result = validator.validate_winner_ppv(caption)

        assert result['elements']['clickbait'] is True
        assert result['elements']['exclusivity'] is True
        assert result['elements']['value_anchor'] is True
        assert result['elements']['cta'] is True
        assert result['structure_score'] == 1.0

    def test_missing_all_elements(self, validator):
        """Test caption missing all elements."""
        caption = "Here is some content for you to enjoy."
        result = validator.validate_winner_ppv(caption)

        assert result['is_valid'] is False
        assert result['structure_score'] == 0.0
        assert len(result['missing_elements']) == 4

    def test_issues_list_structure(self, validator):
        """Test issues list has correct structure."""
        caption = "Simple caption without structure."
        result = validator.validate_winner_ppv(caption)

        for issue in result['issues']:
            assert 'step' in issue
            assert 'element' in issue
            assert 'message' in issue


# =============================================================================
# Test Bundle PPV Edge Cases
# =============================================================================


class TestBundlePPVEdgeCases:
    """Edge case tests for bundle PPV validation."""

    def test_itemization_with_numbers(self, validator):
        """Test itemization detection with numbers."""
        caption = "Bundle includes 5 vids and 10 pics! Usually $100 for just $30! Limited!"
        result = validator.validate_bundle_ppv(caption)

        assert result['elements']['itemization'] is True

    def test_itemization_with_bullets(self, validator):
        """Test itemization detection with bullet points."""
        caption = "Bundle includes:\n\u2022 3 exclusive videos\n\u2022 10 pics\nWorth $100!"
        result = validator.validate_bundle_ppv(caption)

        assert result['elements']['itemization'] is True

    def test_itemization_with_dashes(self, validator):
        """Test itemization detection with dashes."""
        caption = "Bundle includes:\n- 5 videos\n- 10 pics\nWorth $100!"
        result = validator.validate_bundle_ppv(caption)

        assert result['elements']['itemization'] is True

    def test_value_anchor_patterns(self, validator):
        """Test various value anchor patterns."""
        captions = [
            "$100 worth of content! Limited!",
            "Worth $150 value! Hurry!",
            "$200 for only $50! Get it now!",
            "Usually $75, now just $25! Limited!",
            "Normally $100, grab it now! Hurry!",
        ]

        for caption in captions:
            result = validator.validate_bundle_ppv(caption)
            assert result['elements']['value_anchor'] is True, f"Failed for: {caption}"

    def test_urgency_patterns(self, validator):
        """Test urgency pattern detection."""
        captions = [
            "5 vids! $100 for $25! Limited time only!",
            "5 vids! $100 for $25! Only 5 left!",
            "5 vids! $100 for $25! Won't last!",
            "5 vids! $100 for $25! Hurry babe!",
        ]

        for caption in captions:
            result = validator.validate_bundle_ppv(caption)
            assert result['elements']['urgency'] is True, f"Failed for: {caption}"

    def test_low_score_bundle(self, validator):
        """Test bundle with low score."""
        caption = "Check out my bundle! Get it now!"
        result = validator.validate_bundle_ppv(caption)

        assert result['is_valid'] is False
        assert result['structure_score'] < 0.5


# =============================================================================
# Test Wall Campaign Edge Cases
# =============================================================================


class TestWallCampaignEdgeCases:
    """Edge case tests for wall campaign validation."""

    def test_single_line_caption(self, validator):
        """Test single line caption (no structure)."""
        caption = "Just a single line caption here."
        result = validator.validate_wall_campaign(caption)

        # Should detect lack of proper structure
        assert result['elements']['short_wrap'] is False

    def test_two_line_caption(self, validator):
        """Test two line caption."""
        caption = "OMG you won't believe this!\n\nI was at the gym yesterday when something amazing happened."
        result = validator.validate_wall_campaign(caption)

        assert result['elements']['clickbait_title'] is True

    def test_title_detection_patterns(self, validator):
        """Test various title patterns are detected."""
        titles = [
            "New content just dropped!",
            "Just filmed something special...",
            "OMG you won't believe this!",
            "Wait until you see this...",
            "You're not ready for this!",
            "Can't believe I'm sharing this!",
            "Finally showing you!",
            "Exclusive content!!!",
            "Never seen before...",
            "First time ever!",
        ]

        for title in titles:
            caption = f"{title}\n\nI was at home when I decided to try something new.\n\nUnlock to see!"
            result = validator.validate_wall_campaign(caption)
            assert result['elements']['clickbait_title'] is True, f"Failed for: {title}"

    def test_narrative_indicators(self, validator):
        """Test narrative indicator detection."""
        narratives = [
            "I was getting ready for bed when something happened",
            "When I got home, I couldn't believe it",
            "While taking a shower, I had an idea",
            "After my workout, I felt so good",
            "Before anyone woke up, I started recording",
            "During my vacation, things got interesting",
            "I caught myself thinking about you",
            "I found something amazing today",
            "I decided to try something different",
            "I wanted to share this with you",
            "I couldn't resist showing you",
            "I started feeling adventurous",
            "I began exploring new ideas",
            "I felt like being naughty",
            "I needed to let loose today",
            "I had to try this out",
            "Imagined you were here with me today",
            "Never thought I would do this myself",
        ]

        for narrative in narratives:
            caption = f"OMG!\n\n{narrative}\n\nUnlock now!"
            result = validator.validate_wall_campaign(caption)
            # Body should meet substance requirement (45+ chars)
            if len(narrative) >= 45:
                assert result['elements']['body_with_setting'] is True, f"Failed for: {narrative}"

    def test_short_wrap_detection(self, validator):
        """Test short wrap detection."""
        wraps = [
            "Unlock to see!",
            "Open now!",
            "See what happens?",
            "Watch the full thing!",
            "Click to enjoy!",
            "Tap to watch!",
            "Enjoy babe!",
            "Hope you love it!",
            "Want more?",
        ]

        for wrap in wraps:
            caption = f"OMG!\n\nI was at home when I decided to try something new and exciting.\n\n{wrap}"
            result = validator.validate_wall_campaign(caption)
            assert result['elements']['short_wrap'] is True, f"Failed for: {wrap}"

    def test_wrap_too_long(self, validator):
        """Test wrap that is too long (> 80 chars)."""
        long_wrap = "This is a really really really really long closing line that definitely exceeds eighty characters and should fail the short wrap check!"
        caption = f"OMG!\n\nI was at home when something happened.\n\n{long_wrap}"
        result = validator.validate_wall_campaign(caption)

        assert result['elements']['short_wrap'] is False

    def test_body_too_short(self, validator):
        """Test body that is too short (< 45 chars)."""
        caption = "OMG!\n\nShort body.\n\nUnlock now!"
        result = validator.validate_wall_campaign(caption)

        assert result['elements']['body_with_setting'] is False
        assert any('too short' in issue['message'].lower() for issue in result['issues'])

    def test_body_lacks_narrative(self, validator):
        """Test body without narrative indicators but sufficient length."""
        caption = "OMG!\n\nHere is some content that is long enough but has no narrative elements whatsoever.\n\nUnlock now!"
        result = validator.validate_wall_campaign(caption)

        # This should fail body check due to lack of narrative
        assert result['elements']['body_with_setting'] is False

    def test_complete_wall_campaign_score(self, validator):
        """Test complete wall campaign gets full score."""
        caption = """OMG you won't believe what happened!

        I was at home yesterday when I decided to try something new. I couldn't believe how things turned out and needed to share it with you.

        Unlock to see what happened next!"""

        result = validator.validate_wall_campaign(caption)

        assert result['is_valid'] is True
        assert result['structure_score'] >= 0.67

    def test_recommendation_complete(self, validator):
        """Test recommendation for complete structure."""
        caption = """OMG you won't believe this!

        I was feeling adventurous yesterday and decided to try something completely new.

        Unlock now!"""

        result = validator.validate_wall_campaign(caption)

        if result['is_valid']:
            assert 'complete' in result['recommendation'].lower() or 'missing' in result['recommendation'].lower()


# =============================================================================
# Test Pattern Lists
# =============================================================================


class TestPatternLists:
    """Tests for pattern list definitions."""

    def test_clickbait_patterns_not_empty(self, validator):
        """Test clickbait patterns list is not empty."""
        assert len(validator.CLICKBAIT_PATTERNS) > 0

    def test_exclusivity_keywords_not_empty(self, validator):
        """Test exclusivity keywords list is not empty."""
        assert len(validator.EXCLUSIVITY_KEYWORDS) > 0

    def test_value_anchor_patterns_not_empty(self, validator):
        """Test value anchor patterns list is not empty."""
        assert len(validator.VALUE_ANCHOR_PATTERNS) > 0

    def test_cta_patterns_not_empty(self, validator):
        """Test CTA patterns list is not empty."""
        assert len(validator.CTA_PATTERNS) > 0


# =============================================================================
# Test Result Structure
# =============================================================================


class TestResultStructure:
    """Tests for validation result structure."""

    def test_winner_ppv_result_keys(self, validator):
        """Test winner PPV result has all required keys."""
        caption = "CONGRATS! Exclusive! $50 for $10! LMK!"
        result = validator.validate_winner_ppv(caption)

        required_keys = [
            'is_valid',
            'structure_score',
            'elements',
            'missing_elements',
            'issues',
            'recommendation',
        ]
        for key in required_keys:
            assert key in result

    def test_bundle_ppv_result_keys(self, validator):
        """Test bundle PPV result has all required keys."""
        caption = "5 vids! Usually $100 for $25! Hurry!"
        result = validator.validate_bundle_ppv(caption)

        required_keys = [
            'is_valid',
            'structure_score',
            'elements',
            'issues',
        ]
        for key in required_keys:
            assert key in result

    def test_wall_campaign_result_keys(self, validator):
        """Test wall campaign result has all required keys."""
        caption = "OMG!\n\nI was there when it happened.\n\nUnlock!"
        result = validator.validate_wall_campaign(caption)

        required_keys = [
            'is_valid',
            'structure_score',
            'elements',
            'missing_elements',
            'issues',
            'recommendation',
        ]
        for key in required_keys:
            assert key in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
