"""
Security Test Suite for Wave 4 Content Authenticity Validators.

SECURITY CRITICAL: These tests verify that Unicode homoglyph attacks and
character substitution bypasses are properly blocked by the scam prevention
system. All tests MUST pass before Wave 4 exit.

Test Coverage:
    - Unicode bypass prevention (10 attack vectors)
    - Input validation (3 edge cases)
    - Text normalization (5 transformations)
    - Blocking severity verification

Usage:
    pytest python/quality/tests/test_security.py -v
"""

import pytest
from python.quality.scam_prevention import (
    ContentAuthenticityValidator,
    normalize_text,
    BLOCKING_SEVERITIES
)
from python.exceptions import ValidationError


class TestUnicodeBypassPrevention:
    """SECURITY: Ensure Unicode homoglyph attacks are blocked."""

    @pytest.fixture
    def validator(self):
        return ContentAuthenticityValidator()

    @pytest.fixture
    def empty_vault(self):
        return set()

    def test_direct_keyword_match(self, validator, empty_vault):
        """Direct keyword should be detected."""
        result = validator.validate("anal content here", empty_vault)
        assert result.blocked
        assert len(result.scam_risks) > 0

    def test_leet_speak_at_symbol(self, validator, empty_vault):
        """Leet-speak @ for 'a' should be detected."""
        result = validator.validate("an@l content", empty_vault)
        assert result.blocked, "Failed to block 'an@l' bypass"

    def test_space_insertion(self, validator, empty_vault):
        """Space insertion bypass should be detected."""
        result = validator.validate("a n a l content", empty_vault)
        assert result.blocked, "Failed to block 'a n a l' bypass"

    def test_cyrillic_lookalike(self, validator, empty_vault):
        """Cyrillic а (U+0430) lookalike should be detected."""
        # Using Cyrillic 'а' which looks identical to ASCII 'a'
        result = validator.validate("аnаl content", empty_vault)  # Cyrillic а
        assert result.blocked, "Failed to block Cyrillic lookalike bypass"

    def test_zero_width_space(self, validator, empty_vault):
        """Zero-width space insertion should be detected."""
        result = validator.validate("a\u200bnal content", empty_vault)
        assert result.blocked, "Failed to block zero-width space bypass"

    def test_zero_width_non_joiner(self, validator, empty_vault):
        """Zero-width non-joiner should be detected."""
        result = validator.validate("a\u200cnal content", empty_vault)
        assert result.blocked, "Failed to block ZWNJ bypass"

    def test_zero_width_joiner(self, validator, empty_vault):
        """Zero-width joiner should be detected."""
        result = validator.validate("a\u200dnal content", empty_vault)
        assert result.blocked, "Failed to block ZWJ bypass"

    def test_leet_numbers(self, validator, empty_vault):
        """Leet-speak number substitutions should be detected."""
        result = validator.validate("4n4l content", empty_vault)
        assert result.blocked, "Failed to block '4n4l' bypass"

    def test_mixed_leet(self, validator, empty_vault):
        """Mixed leet-speak should be detected."""
        result = validator.validate("an@1 content", empty_vault)
        assert result.blocked, "Failed to block mixed leet bypass"

    def test_combining_characters(self, validator, empty_vault):
        """Combining diacritical marks should be stripped."""
        # a with combining acute accent
        result = validator.validate("a\u0301nal content", empty_vault)
        assert result.blocked, "Failed to block combining character bypass"


class TestInputValidation:
    """Ensure input validation rejects invalid inputs."""

    @pytest.fixture
    def validator(self):
        return ContentAuthenticityValidator()

    def test_empty_caption_raises(self, validator):
        """Empty caption should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("", set())
        assert exc_info.value.field == "caption"

    def test_none_caption_raises(self, validator):
        """None caption should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(None, set())  # type: ignore
        assert exc_info.value.field == "caption"

    def test_non_string_caption_raises(self, validator):
        """Non-string caption should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(123, set())  # type: ignore
        assert exc_info.value.field == "caption"


class TestNormalizeText:
    """Test the normalize_text utility function."""

    def test_lowercase(self):
        """Should convert to lowercase."""
        assert normalize_text("ANAL") == "anal"

    def test_strip_spaces(self):
        """Should collapse all whitespace."""
        assert normalize_text("a n a l") == "anal"

    def test_leet_substitutions(self):
        """Should convert leet-speak."""
        assert normalize_text("4n4l") == "anal"
        assert normalize_text("@nal") == "anal"
        assert normalize_text("an@1") == "anal"  # 1 -> l

    def test_zero_width_removal(self):
        """Should remove zero-width characters."""
        assert normalize_text("a\u200bnal") == "anal"
        assert normalize_text("a\u200cnal") == "anal"
        assert normalize_text("a\u200dnal") == "anal"

    def test_cyrillic_to_ascii(self):
        """Should convert Cyrillic lookalikes."""
        # Cyrillic а (U+0430) looks like ASCII a
        result = normalize_text("аnаl")  # Cyrillic
        # After lookalike conversion, should become "anal"
        assert result == "anal"


class TestBlockingSeverities:
    """Test severity level constants."""

    def test_blocking_severities_exist(self):
        """BLOCKING_SEVERITIES should contain expected levels."""
        assert 'MEDIUM' in BLOCKING_SEVERITIES
        assert 'HIGH' in BLOCKING_SEVERITIES
        assert 'CRITICAL' in BLOCKING_SEVERITIES

    def test_low_not_blocking(self):
        """LOW severity should not be in blocking set."""
        assert 'LOW' not in BLOCKING_SEVERITIES
