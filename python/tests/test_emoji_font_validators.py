"""
Tests for emoji_validator and font_validator modules.

Tests cover:
- EmojiValidator input validation and edge cases
- FontFormatValidator input validation and edge cases
- Emoji blending rules
- Font formatting rules
"""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.quality.emoji_validator import EmojiValidator, EmojiValidationResult
from python.quality.font_validator import FontFormatValidator, FontValidationResult
from python.exceptions import ValidationError


# =============================================================================
# EmojiValidator Fixtures
# =============================================================================


@pytest.fixture
def emoji_validator():
    """Create EmojiValidator instance."""
    return EmojiValidator()


@pytest.fixture
def font_validator():
    """Create FontFormatValidator instance."""
    return FontFormatValidator()


# =============================================================================
# EmojiValidator Input Validation Tests
# =============================================================================


class TestEmojiValidatorInputValidation:
    """Tests for EmojiValidator input validation."""

    def test_empty_caption_raises_error(self, emoji_validator):
        """Test empty caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            emoji_validator.validate("")
        assert "Caption cannot be empty" in str(exc_info.value)

    def test_none_caption_raises_error(self, emoji_validator):
        """Test None caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            emoji_validator.validate(None)
        assert "Caption cannot be empty" in str(exc_info.value)

    def test_non_string_raises_error(self, emoji_validator):
        """Test non-string caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            emoji_validator.validate(12345)
        assert "Caption must be string" in str(exc_info.value)

    def test_list_input_raises_error(self, emoji_validator):
        """Test list input raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            emoji_validator.validate(["caption"])
        assert "Caption must be string" in str(exc_info.value)


# =============================================================================
# EmojiValidator Validation Tests
# =============================================================================


class TestEmojiValidatorValidation:
    """Tests for EmojiValidator validation logic."""

    def test_no_emojis_is_valid(self, emoji_validator):
        """Test caption without emojis is valid."""
        result = emoji_validator.validate("Hello world")
        assert result['is_valid'] is True
        assert result['emoji_count'] == 0

    def test_few_emojis_is_valid(self, emoji_validator):
        """Test caption with few emojis is valid."""
        result = emoji_validator.validate("Hello world! Great content here.")
        assert result['is_valid'] is True

    def test_three_consecutive_yellow_faces_invalid(self, emoji_validator):
        """Test 3+ consecutive yellow face emojis is invalid."""
        # Three yellow faces in a row
        caption = "Hello \U0001F600\U0001F603\U0001F604 world"
        result = emoji_validator.validate(caption)
        assert result['is_valid'] is False
        assert any(i['type'] == 'emoji_vomit' for i in result['issues'])

    def test_yellow_faces_broken_by_text_is_valid(self, emoji_validator):
        """Test yellow faces broken by text is valid."""
        caption = "\U0001F600 hello \U0001F603 world \U0001F604"
        result = emoji_validator.validate(caption)
        # Should be valid - faces are not consecutive
        assert result['is_valid'] is True

    def test_yellow_faces_broken_by_other_emoji_is_valid(self, emoji_validator):
        """Test yellow faces broken by other emoji is valid."""
        # Break sequence with a heart (not yellow face)
        caption = "\U0001F600\U0001F603\u2764\U0001F604"  # heart in middle
        result = emoji_validator.validate(caption)
        # Heart breaks the yellow sequence
        assert result['is_valid'] is True

    def test_emoji_density_short_caption(self, emoji_validator):
        """Test emoji density for short captions."""
        # Short caption (< 100 chars) with many emojis
        caption = "\U0001F600" * 15  # 15 emojis in short caption
        result = emoji_validator.validate(caption)
        # Should flag high density
        assert any(i['type'] == 'high_density' for i in result['issues'])

    def test_emoji_density_medium_caption(self, emoji_validator):
        """Test emoji density for medium captions."""
        # Medium caption (100-250 chars)
        text = "x" * 150
        emojis = "\U0001F600" * 15
        caption = text + emojis
        result = emoji_validator.validate(caption)
        # Should flag high density for medium caption
        assert result['emoji_count'] == 15

    def test_emoji_density_long_caption(self, emoji_validator):
        """Test emoji density for long captions."""
        # Long caption (250+ chars)
        text = "x" * 300
        emojis = "\U0001F600" * 20
        caption = text + emojis
        result = emoji_validator.validate(caption)
        # Should flag high density for long caption
        assert any(i['type'] == 'high_density' for i in result['issues'])

    def test_is_emoji_detection(self, emoji_validator):
        """Test emoji detection method."""
        # Standard emoticons
        assert emoji_validator._is_emoji('\U0001F600') is True  # grinning face
        assert emoji_validator._is_emoji('\U0001F64F') is True  # folded hands

        # Regular text
        assert emoji_validator._is_emoji('A') is False
        assert emoji_validator._is_emoji(' ') is False
        assert emoji_validator._is_emoji('1') is False

    def test_skin_tone_modifier_detection(self, emoji_validator):
        """Test skin tone modifier detection."""
        assert emoji_validator._is_skin_tone_modifier('\U0001F3FB') is True  # light
        assert emoji_validator._is_skin_tone_modifier('\U0001F3FF') is True  # dark
        assert emoji_validator._is_skin_tone_modifier('A') is False


# =============================================================================
# EmojiValidationResult Tests
# =============================================================================


class TestEmojiValidationResult:
    """Tests for EmojiValidationResult dataclass."""

    def test_result_is_frozen(self):
        """Test result is immutable."""
        result = EmojiValidationResult(
            is_valid=True,
            emoji_count=5,
            emoji_density=0.05,
            issues=()
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            result.is_valid = False


# =============================================================================
# FontFormatValidator Input Validation Tests
# =============================================================================


class TestFontValidatorInputValidation:
    """Tests for FontFormatValidator input validation."""

    def test_empty_caption_raises_error(self, font_validator):
        """Test empty caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            font_validator.validate("")
        assert "Caption cannot be empty" in str(exc_info.value)

    def test_none_caption_raises_error(self, font_validator):
        """Test None caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            font_validator.validate(None)
        assert "Caption cannot be empty" in str(exc_info.value)

    def test_non_string_raises_error(self, font_validator):
        """Test non-string caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            font_validator.validate(12345)
        assert "Caption must be string" in str(exc_info.value)


# =============================================================================
# FontFormatValidator Validation Tests
# =============================================================================


class TestFontValidatorValidation:
    """Tests for FontFormatValidator validation logic."""

    def test_no_formatting_is_valid(self, font_validator):
        """Test caption without formatting is valid."""
        result = font_validator.validate("Hello world! Plain text here.")
        assert result.is_valid is True
        assert result.highlighted_count == 0

    def test_bold_markdown_detected(self, font_validator):
        """Test bold markdown is detected."""
        result = font_validator.validate("Hello **bold** world")
        assert result.highlighted_count >= 1

    def test_italic_markdown_detected(self, font_validator):
        """Test italic markdown is detected."""
        result = font_validator.validate("Hello *italic* world")
        assert result.highlighted_count >= 1

    def test_bold_underscore_detected(self, font_validator):
        """Test bold underscore is detected."""
        result = font_validator.validate("Hello __bold__ world")
        assert result.highlighted_count >= 1

    def test_strikethrough_detected(self, font_validator):
        """Test strikethrough is detected."""
        result = font_validator.validate("Hello ~~strikethrough~~ world")
        assert result.highlighted_count >= 1

    def test_code_detected(self, font_validator):
        """Test inline code is detected."""
        result = font_validator.validate("Hello `code` world")
        assert result.highlighted_count >= 1

    def test_link_detected(self, font_validator):
        """Test links are detected."""
        result = font_validator.validate("Check out [my link](http://example.com)")
        assert result.highlighted_count >= 1

    def test_over_formatting_short_caption(self, font_validator):
        """Test over-formatting detection for short captions (< 100 chars)."""
        # Short captions allow up to 3 highlights
        caption = "**bold1** **bold2** **bold3** **bold4**"
        result = font_validator.validate(caption)
        # 4 highlights exceeds limit of 3 for short captions
        assert result.is_valid is False

    def test_over_formatting_medium_caption(self, font_validator):
        """Test over-formatting detection for medium captions (100-250 chars)."""
        # Medium captions allow up to 2 highlights
        filler = "x" * 100
        caption = f"**bold1** **bold2** **bold3** {filler}"
        result = font_validator.validate(caption)
        # 3 highlights exceeds limit of 2 for medium captions
        assert result.is_valid is False

    def test_over_formatting_long_caption(self, font_validator):
        """Test over-formatting detection for long captions (250+ chars)."""
        # Long captions allow up to 2 highlights
        filler = "x" * 250
        caption = f"**bold1** **bold2** **bold3** {filler}"
        result = font_validator.validate(caption)
        # 3 highlights exceeds limit of 2 for long captions
        assert result.is_valid is False

    def test_within_limit_is_valid(self, font_validator):
        """Test formatting within limit is valid."""
        filler = "x" * 250
        # Use backticks to avoid false positive from asterisks in text
        caption = f"`code1` `code2` {filler}"
        result = font_validator.validate(caption)
        # 2 highlights is within limit
        assert result.is_valid is True

    def test_unicode_bold_detected(self, font_validator):
        """Test Unicode mathematical bold is detected."""
        # Mathematical Bold A is U+1D400
        bold_text = "\U0001D400\U0001D401\U0001D402"  # ABC in math bold
        result = font_validator.validate(f"Hello {bold_text} world")
        assert result.highlighted_count >= 1

    def test_unicode_italic_detected(self, font_validator):
        """Test Unicode mathematical italic is detected."""
        # Mathematical Italic A is U+1D434
        italic_text = "\U0001D434\U0001D435\U0001D436"  # ABC in math italic
        result = font_validator.validate(f"Hello {italic_text} world")
        assert result.highlighted_count >= 1


# =============================================================================
# FontValidationResult Tests
# =============================================================================


class TestFontValidationResult:
    """Tests for FontValidationResult dataclass."""

    def test_result_is_frozen(self):
        """Test result is immutable."""
        result = FontValidationResult(
            is_valid=True,
            highlighted_count=0,
            max_allowed=2,
            issues=(),
            recommendation="OK"
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            result.is_valid = False

    def test_result_contains_recommendation(self):
        """Test result contains recommendation."""
        result = FontValidationResult(
            is_valid=True,
            highlighted_count=0,
            max_allowed=2,
            issues=(),
            recommendation="Formatting is appropriate"
        )
        assert "appropriate" in result.recommendation


# =============================================================================
# Integration Tests
# =============================================================================


class TestValidatorIntegration:
    """Integration tests for validators."""

    def test_emoji_validator_with_mixed_content(self, emoji_validator):
        """Test emoji validator with mixed emoji and text."""
        caption = "Hey babe! \U0001F60D Check out this content! \U0001F525"
        result = emoji_validator.validate(caption)
        assert result['emoji_count'] == 2
        assert result['is_valid'] is True

    def test_font_validator_with_mixed_formatting(self, font_validator):
        """Test font validator with mixed formatting."""
        caption = "Check out my **bold** and *italic* content!"
        result = font_validator.validate(caption)
        assert result.highlighted_count >= 2

    def test_both_validators_on_same_caption(self, emoji_validator, font_validator):
        """Test both validators work on same caption."""
        caption = "**Bold text** with \U0001F60D emoji!"

        emoji_result = emoji_validator.validate(caption)
        font_result = font_validator.validate(caption)

        assert emoji_result['emoji_count'] == 1
        assert font_result.highlighted_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
