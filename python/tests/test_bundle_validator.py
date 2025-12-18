"""Unit tests for bundle value framing validator.

Tests the BUNDLE_SEND_TYPES frozenset, validate_bundle_value_framing(),
and validate_all_bundles_in_schedule() functions per Gap 7.3 requirements.

Wave 5 Task 5.9: Bundle Value Framing Validator Tests
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.quality.bundle_validator import (
    BUNDLE_SEND_TYPES,
    validate_all_bundles_in_schedule,
    validate_bundle_value_framing,
)


# =============================================================================
# BUNDLE_SEND_TYPES Tests
# =============================================================================


class TestBundleSendTypes:
    """Tests for BUNDLE_SEND_TYPES frozenset contents."""

    def test_is_frozenset(self) -> None:
        """Test BUNDLE_SEND_TYPES is a frozenset (immutable)."""
        assert isinstance(BUNDLE_SEND_TYPES, frozenset)

    def test_contains_bundle(self) -> None:
        """Test bundle send type is included."""
        assert "bundle" in BUNDLE_SEND_TYPES

    def test_contains_bundle_wall(self) -> None:
        """Test bundle_wall send type is included."""
        assert "bundle_wall" in BUNDLE_SEND_TYPES

    def test_contains_ppv_bundle(self) -> None:
        """Test ppv_bundle send type is included."""
        assert "ppv_bundle" in BUNDLE_SEND_TYPES

    def test_contains_flash_bundle(self) -> None:
        """Test flash_bundle send type is included."""
        assert "flash_bundle" in BUNDLE_SEND_TYPES

    def test_contains_snapchat_bundle(self) -> None:
        """Test snapchat_bundle send type is included."""
        assert "snapchat_bundle" in BUNDLE_SEND_TYPES

    def test_exact_count(self) -> None:
        """Test BUNDLE_SEND_TYPES contains exactly 5 types."""
        assert len(BUNDLE_SEND_TYPES) == 5

    def test_expected_contents(self) -> None:
        """Test BUNDLE_SEND_TYPES contains exactly expected types."""
        expected = {
            "bundle",
            "bundle_wall",
            "ppv_bundle",
            "flash_bundle",
            "snapchat_bundle",
        }
        assert BUNDLE_SEND_TYPES == expected

    def test_does_not_contain_ppv_unlock(self) -> None:
        """Test non-bundle types are not included."""
        assert "ppv_unlock" not in BUNDLE_SEND_TYPES

    def test_does_not_contain_bump_normal(self) -> None:
        """Test engagement types are not included."""
        assert "bump_normal" not in BUNDLE_SEND_TYPES


# =============================================================================
# validate_bundle_value_framing() Tests - Valid Patterns
# =============================================================================


class TestValidateBundleValueFramingValidPatterns:
    """Tests for valid bundle caption patterns."""

    @pytest.mark.parametrize(
        "caption,price,expected_value,expected_ratio",
        [
            # Standard "$X worth for only $Y" pattern
            (
                "Get $500 worth of my hottest content for only $14.99!",
                14.99,
                500.0,
                33.36,
            ),
            # Variation with "just" instead of "only"
            (
                "$300 worth of exclusive content just $9.99!",
                9.99,
                300.0,
                30.03,
            ),
            # Variation with "for" only
            (
                "$200 value for $19.99 this weekend only!",
                19.99,
                200.0,
                10.01,
            ),
            # Large values with commas
            (
                "Over $1,000 worth of content for only $49.99",
                49.99,
                1000.0,
                20.0,
            ),
            # "of content" pattern
            (
                "$750 of content for just $24.99",
                24.99,
                750.0,
                30.01,
            ),
        ],
        ids=[
            "standard_pattern",
            "just_variant",
            "value_keyword",
            "comma_large_value",
            "of_content_pattern",
        ],
    )
    def test_valid_patterns_pass(
        self,
        caption: str,
        price: float,
        expected_value: float,
        expected_ratio: float,
    ) -> None:
        """Test valid value framing patterns pass validation."""
        result = validate_bundle_value_framing(caption, price)

        assert result["is_valid"] is True
        assert result["has_value_anchor"] is True
        assert result["has_price_mention"] is True
        assert result["extracted_value"] == expected_value
        assert result["bundle_price"] == price
        assert result["value_ratio"] == expected_ratio
        assert result["severity"] is None
        assert result["recommendation"] is None
        assert result["missing"] == []

    @pytest.mark.parametrize(
        "caption,price",
        [
            ("$100 worth only $5", 5.0),
            ("$50 value just $10", 10.0),
            ("$999 of content for $25", 25.0),
        ],
        ids=["worth_only", "value_just", "of_content_for"],
    )
    def test_minimal_valid_patterns(self, caption: str, price: float) -> None:
        """Test minimal but valid patterns pass."""
        result = validate_bundle_value_framing(caption, price)
        assert result["is_valid"] is True

    def test_valid_pattern_message(self) -> None:
        """Test valid pattern returns correct message."""
        result = validate_bundle_value_framing(
            "$500 worth for only $15", 15.0
        )
        assert result["message"] == "Bundle caption includes proper value framing"


# =============================================================================
# validate_bundle_value_framing() Tests - Invalid/Missing Patterns
# =============================================================================


class TestValidateBundleValueFramingInvalidPatterns:
    """Tests for invalid or missing bundle caption patterns."""

    @pytest.mark.parametrize(
        "caption,price,expected_missing",
        [
            # Missing both value anchor and price mention
            (
                "Hot bundle available now!",
                19.99,
                ["value_anchor", "price_mention"],
            ),
            # Missing value anchor only
            (
                "Get this exclusive content for only $15!",
                15.0,
                ["value_anchor"],
            ),
            # Missing price mention only
            (
                "$500 worth of amazing content!",
                25.0,
                ["price_mention"],
            ),
            # Generic promotional text
            (
                "Check out my new bundle deal",
                10.0,
                ["value_anchor", "price_mention"],
            ),
            # Emoji-heavy without patterns
            (
                "Amazing deal!! Best bundle ever!!",
                20.0,
                ["value_anchor", "price_mention"],
            ),
        ],
        ids=[
            "missing_both",
            "missing_value_anchor",
            "missing_price_mention",
            "generic_promo",
            "emoji_heavy_no_patterns",
        ],
    )
    def test_invalid_patterns_fail(
        self,
        caption: str,
        price: float,
        expected_missing: list[str],
    ) -> None:
        """Test invalid patterns fail validation with correct missing elements."""
        result = validate_bundle_value_framing(caption, price)

        assert result["is_valid"] is False
        assert result["severity"] == "ERROR"
        assert result["missing"] == expected_missing
        assert result["recommendation"] is not None
        assert "value framing" in result["recommendation"]

    def test_missing_value_anchor_flags(self) -> None:
        """Test missing value anchor sets correct flag."""
        result = validate_bundle_value_framing(
            "Get this for only $15!", 15.0
        )
        assert result["has_value_anchor"] is False
        assert result["has_price_mention"] is True

    def test_missing_price_mention_flags(self) -> None:
        """Test missing price mention sets correct flag."""
        result = validate_bundle_value_framing(
            "$500 worth of content here!", 25.0
        )
        assert result["has_value_anchor"] is True
        assert result["has_price_mention"] is False

    def test_missing_both_message_format(self) -> None:
        """Test missing both elements formats message correctly."""
        result = validate_bundle_value_framing(
            "Amazing bundle!", 15.0
        )
        assert "value_anchor and price_mention" in result["message"]


# =============================================================================
# validate_bundle_value_framing() Tests - Price Format Handling
# =============================================================================


class TestValidateBundleValueFramingPriceFormats:
    """Tests for various price format handling."""

    @pytest.mark.parametrize(
        "caption,price",
        [
            # Integer prices
            ("$500 worth for only $10", 10.0),
            ("$100 worth for just $5", 5.0),
            # Decimal prices with cents
            ("$500 worth for only $14.99", 14.99),
            ("$300 worth for just $9.95", 9.95),
            # Single digit prices
            ("$200 worth for only $5", 5.0),
            # Double digit prices
            ("$1000 worth for only $99", 99.0),
        ],
        ids=[
            "integer_10",
            "integer_5",
            "decimal_14.99",
            "decimal_9.95",
            "single_digit",
            "double_digit",
        ],
    )
    def test_various_price_formats_pass(self, caption: str, price: float) -> None:
        """Test various price formats are recognized."""
        result = validate_bundle_value_framing(caption, price)
        assert result["is_valid"] is True
        assert result["has_price_mention"] is True

    @pytest.mark.parametrize(
        "caption,expected_value",
        [
            ("$500 worth for only $15", 500.0),
            ("$1,000 worth for only $25", 1000.0),
            ("$2,500 worth for only $50", 2500.0),
            ("$10,000 value for only $99", 10000.0),
            ("$500.00 worth for only $15", 500.0),
        ],
        ids=[
            "no_comma",
            "one_comma",
            "two_comma_segments",
            "five_digits",
            "with_cents",
        ],
    )
    def test_value_extraction_formats(
        self, caption: str, expected_value: float
    ) -> None:
        """Test value extraction handles various formats."""
        result = validate_bundle_value_framing(caption, 15.0)
        assert result["extracted_value"] == expected_value


# =============================================================================
# validate_bundle_value_framing() Tests - Edge Cases
# =============================================================================


class TestValidateBundleValueFramingEdgeCases:
    """Tests for edge cases and malformed captions."""

    def test_empty_caption(self) -> None:
        """Test empty caption fails validation."""
        result = validate_bundle_value_framing("", 15.0)
        assert result["is_valid"] is False
        assert result["has_value_anchor"] is False
        assert result["has_price_mention"] is False

    def test_whitespace_only_caption(self) -> None:
        """Test whitespace-only caption fails validation."""
        result = validate_bundle_value_framing("   \n\t  ", 15.0)
        assert result["is_valid"] is False

    def test_zero_price(self) -> None:
        """Test zero price does not cause division error."""
        result = validate_bundle_value_framing(
            "$500 worth for only $0", 0.0
        )
        # Value ratio should be None when price is 0
        assert result["value_ratio"] is None

    def test_negative_price(self) -> None:
        """Test negative price does not cause division issues.

        Per source code: ratio only calculated when price > 0.
        Negative prices result in None ratio (defensive behavior).
        """
        result = validate_bundle_value_framing(
            "$500 worth for only $15", -15.0
        )
        # Negative price <= 0, so no ratio calculated (defensive)
        assert result["value_ratio"] is None
        assert result["bundle_price"] == -15.0

    def test_very_long_caption(self) -> None:
        """Test very long caption is handled."""
        long_text = "x" * 1000
        caption = f"$500 worth {long_text} for only $15"
        result = validate_bundle_value_framing(caption, 15.0)
        assert result["is_valid"] is True

    def test_case_insensitivity_worth(self) -> None:
        """Test patterns are case insensitive for value anchor."""
        result = validate_bundle_value_framing(
            "$500 WORTH for only $15", 15.0
        )
        assert result["has_value_anchor"] is True

    def test_case_insensitivity_only(self) -> None:
        """Test patterns are case insensitive for price mention."""
        result = validate_bundle_value_framing(
            "$500 worth for ONLY $15", 15.0
        )
        assert result["has_price_mention"] is True

    def test_mixed_case(self) -> None:
        """Test mixed case patterns work."""
        result = validate_bundle_value_framing(
            "$500 WoRtH for OnLy $15", 15.0
        )
        assert result["is_valid"] is True

    def test_multiple_dollar_amounts(self) -> None:
        """Test caption with multiple dollar amounts extracts value correctly."""
        result = validate_bundle_value_framing(
            "$500 worth of content, $300 bonus, for only $25", 25.0
        )
        # Should extract first value anchor
        assert result["extracted_value"] == 500.0

    def test_unicode_in_caption(self) -> None:
        """Test unicode characters in caption are handled."""
        result = validate_bundle_value_framing(
            "$500 worth for only $15!", 15.0
        )
        assert result["is_valid"] is True


# =============================================================================
# validate_bundle_value_framing() Tests - Value Ratio and Notes
# =============================================================================


class TestValidateBundleValueFramingValueRatio:
    """Tests for value ratio calculation and notes."""

    def test_high_value_ratio_note(self) -> None:
        """Test excellent value ratio adds note."""
        result = validate_bundle_value_framing(
            "$500 worth for only $10", 10.0
        )
        assert result["value_ratio"] == 50.0
        assert result["note"] is not None
        assert "Excellent value ratio" in result["note"]
        assert "50.0x" in result["note"]

    def test_value_ratio_boundary_10x(self) -> None:
        """Test value ratio at exactly 10x threshold."""
        result = validate_bundle_value_framing(
            "$100 worth for only $10", 10.0
        )
        assert result["value_ratio"] == 10.0
        assert result["note"] is not None

    def test_value_ratio_below_threshold(self) -> None:
        """Test value ratio below 10x does not add note."""
        result = validate_bundle_value_framing(
            "$90 worth for only $10", 10.0
        )
        assert result["value_ratio"] == 9.0
        assert result["note"] is None

    def test_value_ratio_rounding(self) -> None:
        """Test value ratio is rounded to 2 decimal places."""
        result = validate_bundle_value_framing(
            "$500 worth for only $14.99", 14.99
        )
        # 500 / 14.99 = 33.3555... should round to 33.36
        assert result["value_ratio"] == 33.36

    def test_no_value_extraction_no_ratio(self) -> None:
        """Test no value extraction results in no ratio."""
        result = validate_bundle_value_framing(
            "Amazing deal for only $15!", 15.0
        )
        assert result["extracted_value"] is None
        assert result["value_ratio"] is None


# =============================================================================
# validate_all_bundles_in_schedule() Tests - Filtering
# =============================================================================


class TestValidateAllBundlesFiltering:
    """Tests for schedule filtering to bundle types only."""

    def test_filters_bundle_types(self) -> None:
        """Test only bundle send types are validated."""
        schedule = [
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
            {"send_type_key": "ppv_unlock", "caption": "Hot content!", "price": 9.99},
            {"send_type_key": "bump_normal", "caption": "Hey!", "price": 0},
        ]
        result = validate_all_bundles_in_schedule(schedule)
        assert result["bundles_checked"] == 1

    def test_filters_all_bundle_types(self) -> None:
        """Test all bundle send types are included."""
        schedule = [
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
            {"send_type_key": "bundle_wall", "caption": "$300 worth for only $10!", "price": 10.0},
            {"send_type_key": "ppv_bundle", "caption": "$400 worth for only $20!", "price": 20.0},
            {"send_type_key": "flash_bundle", "caption": "$200 worth for only $5!", "price": 5.0},
            {"send_type_key": "snapchat_bundle", "caption": "$150 worth for only $8!", "price": 8.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)
        assert result["bundles_checked"] == 5
        assert result["bundles_passed"] == 5

    def test_case_insensitive_send_type_key(self) -> None:
        """Test send_type_key matching is case insensitive."""
        schedule = [
            {"send_type_key": "BUNDLE", "caption": "$500 worth for only $15!", "price": 15.0},
            {"send_type_key": "Bundle", "caption": "$300 worth for only $10!", "price": 10.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)
        assert result["bundles_checked"] == 2


# =============================================================================
# validate_all_bundles_in_schedule() Tests - Summary and Counts
# =============================================================================


class TestValidateAllBundlesSummary:
    """Tests for summary and count results."""

    def test_all_pass_summary(self) -> None:
        """Test summary when all bundles pass."""
        schedule = [
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
            {"send_type_key": "flash_bundle", "caption": "$200 worth for only $5!", "price": 5.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert result["is_valid"] is True
        assert result["bundles_checked"] == 2
        assert result["bundles_passed"] == 2
        assert result["bundles_failed"] == 0
        assert result["summary"] == "All 2 bundle(s) have proper value framing"
        assert result["failed_items"] == []

    def test_mixed_pass_fail_summary(self) -> None:
        """Test summary with mixed pass/fail results."""
        schedule = [
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
            {"send_type_key": "flash_bundle", "caption": "Hot deal!", "price": 5.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert result["is_valid"] is False
        assert result["bundles_checked"] == 2
        assert result["bundles_passed"] == 1
        assert result["bundles_failed"] == 1
        assert "1 of 2 bundle(s)" in result["summary"]

    def test_all_fail_summary(self) -> None:
        """Test summary when all bundles fail."""
        schedule = [
            {"send_type_key": "bundle", "caption": "Hot deal!", "price": 15.0},
            {"send_type_key": "flash_bundle", "caption": "Amazing offer!", "price": 5.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert result["is_valid"] is False
        assert result["bundles_passed"] == 0
        assert result["bundles_failed"] == 2
        assert "2 of 2 bundle(s)" in result["summary"]

    def test_failed_items_contains_item_and_validation(self) -> None:
        """Test failed_items includes original item and validation result."""
        schedule = [
            {"send_type_key": "bundle", "caption": "Bad caption", "price": 15.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert len(result["failed_items"]) == 1
        failed = result["failed_items"][0]
        assert "item" in failed
        assert "validation" in failed
        assert failed["item"]["caption"] == "Bad caption"
        assert failed["validation"]["is_valid"] is False


# =============================================================================
# validate_all_bundles_in_schedule() Tests - No Bundles
# =============================================================================


class TestValidateAllBundlesNoBundles:
    """Tests for schedules with no bundle items."""

    def test_empty_schedule(self) -> None:
        """Test empty schedule returns valid with zero counts."""
        result = validate_all_bundles_in_schedule([])

        assert result["is_valid"] is True
        assert result["bundles_checked"] == 0
        assert result["bundles_passed"] == 0
        assert result["bundles_failed"] == 0
        assert result["summary"] == "No bundle items in schedule"
        assert result["results"] == []
        assert result["failed_items"] == []

    def test_schedule_with_no_bundles(self) -> None:
        """Test schedule with non-bundle types returns valid."""
        schedule = [
            {"send_type_key": "ppv_unlock", "caption": "Hot content!", "price": 9.99},
            {"send_type_key": "bump_normal", "caption": "Hey!", "price": 0},
            {"send_type_key": "renew_on_message", "caption": "Miss me?", "price": 0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert result["is_valid"] is True
        assert result["bundles_checked"] == 0
        assert result["summary"] == "No bundle items in schedule"


# =============================================================================
# validate_all_bundles_in_schedule() Tests - Edge Cases
# =============================================================================


class TestValidateAllBundlesEdgeCases:
    """Tests for edge cases in schedule validation."""

    def test_missing_send_type_key(self) -> None:
        """Test items without send_type_key are skipped."""
        schedule = [
            {"caption": "No type key", "price": 15.0},
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)
        assert result["bundles_checked"] == 1

    def test_missing_caption(self) -> None:
        """Test bundle item with missing caption fails with special message."""
        schedule = [
            {"send_type_key": "bundle", "price": 15.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert result["is_valid"] is False
        assert result["bundles_failed"] == 1
        assert result["results"][0]["message"] == "Bundle item has no caption"
        assert "caption" in result["results"][0]["missing"]

    def test_empty_caption(self) -> None:
        """Test bundle item with empty caption fails."""
        schedule = [
            {"send_type_key": "bundle", "caption": "", "price": 15.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert result["is_valid"] is False
        assert result["bundles_failed"] == 1

    def test_missing_price_defaults_to_zero(self) -> None:
        """Test missing price defaults to 0.0."""
        schedule = [
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!"},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert result["results"][0]["bundle_price"] == 0.0

    def test_results_include_send_type_key(self) -> None:
        """Test validation results include send_type_key."""
        schedule = [
            {"send_type_key": "flash_bundle", "caption": "$200 worth for only $5!", "price": 5.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert result["results"][0]["send_type_key"] == "flash_bundle"

    def test_results_include_item_index(self) -> None:
        """Test validation results include item_index from original schedule."""
        schedule = [
            {"send_type_key": "ppv_unlock", "caption": "PPV content", "price": 10.0},
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
            {"send_type_key": "bump_normal", "caption": "Hey!", "price": 0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        # Bundle is at index 1 in the original schedule
        assert result["results"][0]["item_index"] == 1

    def test_large_schedule(self) -> None:
        """Test large schedule with many items is handled."""
        schedule = []
        for i in range(100):
            if i % 10 == 0:
                schedule.append({
                    "send_type_key": "bundle",
                    "caption": f"${500 + i} worth for only ${15 + i}!",
                    "price": 15.0 + i,
                })
            else:
                schedule.append({
                    "send_type_key": "ppv_unlock",
                    "caption": f"Content {i}",
                    "price": 9.99,
                })

        result = validate_all_bundles_in_schedule(schedule)

        assert result["bundles_checked"] == 10
        assert result["bundles_passed"] == 10


# =============================================================================
# validate_all_bundles_in_schedule() Tests - Results Structure
# =============================================================================


class TestValidateAllBundlesResultsStructure:
    """Tests for the structure of validation results."""

    def test_results_list_length_matches_bundles_checked(self) -> None:
        """Test results list has one entry per bundle checked."""
        schedule = [
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
            {"send_type_key": "bundle_wall", "caption": "Bad caption", "price": 10.0},
            {"send_type_key": "flash_bundle", "caption": "$200 worth for only $5!", "price": 5.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        assert len(result["results"]) == result["bundles_checked"]
        assert len(result["results"]) == 3

    def test_result_dict_keys(self) -> None:
        """Test result dict contains all expected keys."""
        schedule = [
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        expected_keys = {
            "is_valid",
            "bundles_checked",
            "bundles_passed",
            "bundles_failed",
            "results",
            "failed_items",
            "summary",
        }
        assert set(result.keys()) == expected_keys

    def test_individual_result_keys(self) -> None:
        """Test individual validation result contains expected keys."""
        schedule = [
            {"send_type_key": "bundle", "caption": "$500 worth for only $15!", "price": 15.0},
        ]
        result = validate_all_bundles_in_schedule(schedule)

        individual = result["results"][0]
        expected_keys = {
            "is_valid",
            "has_value_anchor",
            "has_price_mention",
            "extracted_value",
            "bundle_price",
            "value_ratio",
            "severity",
            "message",
            "recommendation",
            "note",
            "missing",
            "send_type_key",
            "item_index",
        }
        assert set(individual.keys()) == expected_keys
