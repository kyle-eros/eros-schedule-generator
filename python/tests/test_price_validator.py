"""Unit tests for EROS price-length validation system.

Tests the price_validator module which ensures PPV pricing aligns with
caption length for maximum Revenue Per Send (RPS). Based on Gap 10.11 & 10.12
analysis showing critical RPS loss from price-length mismatches.

Version: 1.0.0
Wave 5 Task 5.1 Tests
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.exceptions import ValidationError
from python.quality.price_validator import (
    MISMATCH_PENALTIES,
    PRICE_LENGTH_MATRIX,
    SORTED_PRICES,
    _suggest_alternative_prices,
    calculate_rps_impact,
    get_optimal_price_for_length,
    validate_batch,
    validate_price_length_match,
)


# =============================================================================
# Test PRICE_LENGTH_MATRIX Constants
# =============================================================================


class TestPriceLengthMatrixConstants:
    """Tests for PRICE_LENGTH_MATRIX configuration validity."""

    def test_matrix_has_four_tiers(self) -> None:
        """Verify matrix contains exactly 4 price tiers."""
        assert len(PRICE_LENGTH_MATRIX) == 4

    def test_all_expected_prices_present(self) -> None:
        """Verify all expected price points are configured."""
        expected_prices = {14.99, 19.69, 24.99, 29.99}
        actual_prices = set(PRICE_LENGTH_MATRIX.keys())
        assert actual_prices == expected_prices

    def test_sorted_prices_ascending(self) -> None:
        """Verify SORTED_PRICES is in ascending order."""
        assert SORTED_PRICES == [14.99, 19.69, 24.99, 29.99]

    @pytest.mark.parametrize(
        "price,expected_tier",
        [
            (14.99, "impulse"),
            (19.69, "optimal"),
            (24.99, "premium"),
            (29.99, "high_premium"),
        ],
    )
    def test_tier_names_correct(self, price: float, expected_tier: str) -> None:
        """Verify tier names are correctly assigned."""
        assert PRICE_LENGTH_MATRIX[price]["tier_name"] == expected_tier

    @pytest.mark.parametrize(
        "price,min_chars,max_chars",
        [
            (14.99, 0, 249),
            (19.69, 250, 449),
            (24.99, 450, 599),
            (29.99, 600, 749),
        ],
    )
    def test_character_ranges_configured(
        self, price: float, min_chars: int, max_chars: int
    ) -> None:
        """Verify character ranges are correctly configured for each tier."""
        config = PRICE_LENGTH_MATRIX[price]
        assert config["min_chars"] == min_chars
        assert config["max_chars"] == max_chars
        assert config["optimal_range"] == (min_chars, max_chars)

    @pytest.mark.parametrize(
        "price,expected_rps",
        [
            (14.99, 469),
            (19.69, 716),
            (24.99, 565),
            (29.99, 278),
        ],
    )
    def test_expected_rps_values(self, price: float, expected_rps: int) -> None:
        """Verify expected RPS values are set correctly."""
        assert PRICE_LENGTH_MATRIX[price]["expected_rps"] == expected_rps

    def test_ranges_are_contiguous(self) -> None:
        """Verify character ranges are contiguous without gaps."""
        ranges = [
            (PRICE_LENGTH_MATRIX[p]["min_chars"], PRICE_LENGTH_MATRIX[p]["max_chars"])
            for p in SORTED_PRICES
        ]
        for i in range(len(ranges) - 1):
            current_max = ranges[i][1]
            next_min = ranges[i + 1][0]
            assert next_min == current_max + 1, (
                f"Gap between ranges: {current_max} to {next_min}"
            )

    def test_each_tier_has_required_keys(self) -> None:
        """Verify each tier config has all required keys."""
        required_keys = {
            "min_chars",
            "max_chars",
            "tier_name",
            "expected_rps",
            "description",
            "optimal_range",
        }
        for price, config in PRICE_LENGTH_MATRIX.items():
            assert required_keys.issubset(config.keys()), (
                f"Price {price} missing keys: {required_keys - set(config.keys())}"
            )


class TestMismatchPenaltiesConstants:
    """Tests for MISMATCH_PENALTIES configuration validity."""

    def test_penalties_defined_for_all_prices(self) -> None:
        """Verify penalties are defined for all price points."""
        for price in SORTED_PRICES:
            assert price in MISMATCH_PENALTIES

    def test_penalty_has_required_keys(self) -> None:
        """Verify each penalty config has required keys."""
        required_keys = {"penalty_multiplier", "rps_loss_pct", "severity", "reason"}
        for price, directions in MISMATCH_PENALTIES.items():
            for direction, penalty in directions.items():
                assert required_keys.issubset(penalty.keys()), (
                    f"Penalty for {price}/{direction} missing keys"
                )

    def test_critical_1969_too_short_penalty(self) -> None:
        """Verify $19.69 too_short has CRITICAL severity (82% RPS loss)."""
        penalty = MISMATCH_PENALTIES[19.69]["too_short"]
        assert penalty["severity"] == "CRITICAL"
        assert penalty["rps_loss_pct"] == 82
        assert penalty["penalty_multiplier"] == 0.18

    def test_penalty_multipliers_in_range(self) -> None:
        """Verify penalty multipliers are between 0 and 1."""
        for price, directions in MISMATCH_PENALTIES.items():
            for direction, penalty in directions.items():
                mult = penalty["penalty_multiplier"]
                assert 0 <= mult <= 1, (
                    f"Invalid multiplier {mult} for {price}/{direction}"
                )

    def test_rps_loss_percentages_valid(self) -> None:
        """Verify RPS loss percentages are between 0 and 100."""
        for price, directions in MISMATCH_PENALTIES.items():
            for direction, penalty in directions.items():
                loss = penalty["rps_loss_pct"]
                assert 0 <= loss <= 100, (
                    f"Invalid RPS loss {loss}% for {price}/{direction}"
                )


# =============================================================================
# Test validate_price_length_match()
# =============================================================================


class TestValidatePriceLengthMatchValid:
    """Tests for valid price-length combinations."""

    @pytest.mark.parametrize(
        "char_count,price",
        [
            # $14.99 impulse tier (0-249 chars)
            # Note: 0 chars (empty caption) is rejected by input validation
            (1, 14.99),
            (100, 14.99),
            (249, 14.99),
            # $19.69 optimal tier (250-449 chars)
            (250, 19.69),
            (350, 19.69),
            (449, 19.69),
            # $24.99 premium tier (450-599 chars)
            (450, 24.99),
            (525, 24.99),
            (599, 24.99),
            # $29.99 high_premium tier (600-749 chars)
            (600, 29.99),
            (675, 29.99),
            (749, 29.99),
        ],
    )
    def test_valid_combinations(self, char_count: int, price: float) -> None:
        """Test valid price-length combinations return is_valid=True."""
        caption = "A" * char_count
        result = validate_price_length_match(caption, price)

        assert result["is_valid"] is True
        assert result["price"] == price
        assert result["char_count"] == char_count
        assert result["mismatch_type"] is None
        assert result["expected_rps_loss"] is None
        assert result["severity"] is None
        assert result["alternative_prices"] == []

    def test_valid_result_has_correct_tier_info(self) -> None:
        """Test valid result includes correct tier information."""
        caption = "A" * 300
        result = validate_price_length_match(caption, 19.69)

        assert result["tier_name"] == "optimal"
        assert result["optimal_range"] == (250, 449)
        assert result["expected_rps"] == 716

    def test_valid_result_message_format(self) -> None:
        """Test valid result message contains expected elements."""
        caption = "A" * 300
        result = validate_price_length_match(caption, 19.69)

        assert "300 chars" in result["message"]
        assert "optimal" in result["message"]
        assert "$19.69" in result["message"]

    def test_valid_result_recommendation(self) -> None:
        """Test valid result recommendation mentions no changes needed."""
        caption = "A" * 300
        result = validate_price_length_match(caption, 19.69)

        assert "No changes needed" in result["recommendation"]
        assert "716" in result["recommendation"]


class TestValidatePriceLengthMatchInvalid:
    """Tests for invalid price-length combinations."""

    @pytest.mark.parametrize(
        "char_count,price,expected_mismatch",
        [
            # Too short for tier
            (100, 19.69, "too_short"),
            (200, 24.99, "too_short"),
            (400, 29.99, "too_short"),
            # Too long for tier
            (300, 14.99, "too_long"),
            (500, 19.69, "too_long"),
            (650, 24.99, "too_long"),
        ],
    )
    def test_invalid_combinations_type(
        self, char_count: int, price: float, expected_mismatch: str
    ) -> None:
        """Test invalid combinations return correct mismatch type."""
        caption = "A" * char_count
        result = validate_price_length_match(caption, price)

        assert result["is_valid"] is False
        assert result["mismatch_type"] == expected_mismatch

    def test_invalid_result_has_severity(self) -> None:
        """Test invalid result includes severity level."""
        caption = "A" * 100  # Too short for $19.69
        result = validate_price_length_match(caption, 19.69)

        assert result["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")

    def test_invalid_result_has_rps_loss(self) -> None:
        """Test invalid result includes RPS loss percentage."""
        caption = "A" * 100
        result = validate_price_length_match(caption, 19.69)

        assert result["expected_rps_loss"] is not None
        assert result["expected_rps_loss"].endswith("%")

    def test_invalid_result_has_alternatives(self) -> None:
        """Test invalid result suggests alternative prices when available."""
        caption = "A" * 100  # Valid for $14.99
        result = validate_price_length_match(caption, 19.69)

        assert len(result["alternative_prices"]) > 0
        assert result["alternative_prices"][0]["price"] == 14.99


class TestValidatePriceLengthMatchCriticalScenario:
    """Tests for the critical $19.69 mismatch scenario."""

    def test_1969_too_short_is_critical(self) -> None:
        """Test $19.69 with too-short caption returns CRITICAL severity."""
        caption = "Short caption that is under 250 characters"
        result = validate_price_length_match(caption, 19.69)

        assert result["is_valid"] is False
        assert result["severity"] == "CRITICAL"
        assert result["expected_rps_loss"] == "82%"

    def test_1969_critical_message_format(self) -> None:
        """Test CRITICAL severity message starts with 'CRITICAL:'."""
        caption = "Short caption"
        result = validate_price_length_match(caption, 19.69)

        assert result["message"].startswith("CRITICAL:")

    def test_1969_with_exact_249_chars(self) -> None:
        """Test exactly 249 chars at $19.69 is too short (CRITICAL)."""
        caption = "A" * 249
        result = validate_price_length_match(caption, 19.69)

        assert result["is_valid"] is False
        assert result["mismatch_type"] == "too_short"
        assert result["severity"] == "CRITICAL"

    def test_1969_with_exact_250_chars(self) -> None:
        """Test exactly 250 chars at $19.69 is valid (boundary)."""
        caption = "A" * 250
        result = validate_price_length_match(caption, 19.69)

        assert result["is_valid"] is True

    def test_1969_with_exact_449_chars(self) -> None:
        """Test exactly 449 chars at $19.69 is valid (upper boundary)."""
        caption = "A" * 449
        result = validate_price_length_match(caption, 19.69)

        assert result["is_valid"] is True

    def test_1969_with_exact_450_chars(self) -> None:
        """Test exactly 450 chars at $19.69 is too long."""
        caption = "A" * 450
        result = validate_price_length_match(caption, 19.69)

        assert result["is_valid"] is False
        assert result["mismatch_type"] == "too_long"
        assert result["severity"] == "HIGH"


class TestValidatePriceLengthMatchBoundaries:
    """Tests for tier boundary edge cases."""

    @pytest.mark.parametrize(
        "char_count,price,expected_valid",
        [
            # $14.99 boundaries
            # Note: 0 chars (empty caption) is rejected by input validation
            (1, 14.99, True),
            (249, 14.99, True),
            (250, 14.99, False),
            # $19.69 boundaries
            (249, 19.69, False),
            (250, 19.69, True),
            (449, 19.69, True),
            (450, 19.69, False),
            # $24.99 boundaries
            (449, 24.99, False),
            (450, 24.99, True),
            (599, 24.99, True),
            (600, 24.99, False),
            # $29.99 boundaries
            (599, 29.99, False),
            (600, 29.99, True),
            (749, 29.99, True),
            (750, 29.99, False),
        ],
    )
    def test_boundary_validation(
        self, char_count: int, price: float, expected_valid: bool
    ) -> None:
        """Test validation at tier boundaries."""
        caption = "A" * char_count
        result = validate_price_length_match(caption, price)
        assert result["is_valid"] is expected_valid


class TestValidatePriceLengthMatchInputValidation:
    """Tests for input validation and error handling."""

    def test_empty_caption_raises_validation_error(self) -> None:
        """Test empty caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price_length_match("", 19.69)

        assert exc_info.value.field == "caption"
        assert "empty" in str(exc_info.value).lower()

    def test_zero_length_caption_rejected_even_for_impulse_tier(self) -> None:
        """Test that 0-length captions are rejected even though min_chars=0 for $14.99.

        The PRICE_LENGTH_MATRIX allows min_chars=0 for the impulse tier, but the
        validate_price_length_match function correctly rejects empty captions as
        invalid input since a PPV send requires actual caption content.
        """
        with pytest.raises(ValidationError) as exc_info:
            validate_price_length_match("", 14.99)

        assert exc_info.value.field == "caption"

    def test_none_caption_raises_validation_error(self) -> None:
        """Test None caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price_length_match(None, 19.69)  # type: ignore

        assert exc_info.value.field == "caption"

    def test_unsupported_price_raises_validation_error(self) -> None:
        """Test unsupported price point raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price_length_match("A" * 300, 15.99)

        assert exc_info.value.field == "price"
        assert "15.99" in str(exc_info.value)

    def test_unsupported_price_suggests_nearest(self) -> None:
        """Test unsupported price error message suggests nearest valid price."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price_length_match("A" * 300, 15.00)

        assert "14.99" in str(exc_info.value) or exc_info.value.details is not None

    def test_non_string_caption_raises_validation_error(self) -> None:
        """Test non-string caption (e.g., int, list) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price_length_match(12345, 19.69)  # type: ignore

        assert exc_info.value.field == "caption"
        assert "string" in str(exc_info.value).lower()

    def test_list_caption_raises_validation_error(self) -> None:
        """Test list as caption raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price_length_match(["not", "a", "string"], 19.69)  # type: ignore

        assert exc_info.value.field == "caption"


# =============================================================================
# Test _suggest_alternative_prices()
# =============================================================================


class TestSuggestAlternativePrices:
    """Tests for _suggest_alternative_prices() internal function."""

    def test_returns_list(self) -> None:
        """Test function returns a list."""
        result = _suggest_alternative_prices(100)
        assert isinstance(result, list)

    def test_impulse_tier_suggestions(self) -> None:
        """Test suggestions for impulse tier character count (0-249)."""
        result = _suggest_alternative_prices(100)

        assert len(result) == 1
        assert result[0]["price"] == 14.99
        assert result[0]["tier_name"] == "impulse"

    def test_optimal_tier_suggestions(self) -> None:
        """Test suggestions for optimal tier character count (250-449)."""
        result = _suggest_alternative_prices(350)

        assert len(result) == 1
        assert result[0]["price"] == 19.69
        assert result[0]["tier_name"] == "optimal"

    def test_premium_tier_suggestions(self) -> None:
        """Test suggestions for premium tier character count (450-599)."""
        result = _suggest_alternative_prices(500)

        assert len(result) == 1
        assert result[0]["price"] == 24.99

    def test_high_premium_tier_suggestions(self) -> None:
        """Test suggestions for high_premium tier character count (600-749)."""
        result = _suggest_alternative_prices(650)

        assert len(result) == 1
        assert result[0]["price"] == 29.99

    def test_out_of_range_returns_empty(self) -> None:
        """Test character count outside all ranges returns empty list."""
        result = _suggest_alternative_prices(800)
        assert result == []

    def test_suggestions_sorted_by_rps(self) -> None:
        """Test suggestions are sorted by expected RPS (highest first)."""
        # Use boundary that might match multiple tiers if ranges overlapped
        # Since ranges are contiguous, test with in-range value
        result = _suggest_alternative_prices(300)

        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i]["expected_rps"] >= result[i + 1]["expected_rps"]

    def test_suggestion_has_required_keys(self) -> None:
        """Test each suggestion has all required keys."""
        result = _suggest_alternative_prices(300)
        required_keys = {"price", "tier_name", "expected_rps", "optimal_range", "reason"}

        for suggestion in result:
            assert required_keys.issubset(suggestion.keys())

    def test_suggestion_reason_contains_char_count(self) -> None:
        """Test suggestion reason includes character count."""
        char_count = 300
        result = _suggest_alternative_prices(char_count)

        assert len(result) > 0
        assert str(char_count) in result[0]["reason"]


# =============================================================================
# Test get_optimal_price_for_length()
# =============================================================================


class TestGetOptimalPriceForLength:
    """Tests for get_optimal_price_for_length() function."""

    @pytest.mark.parametrize(
        "char_count,expected_price,expected_tier",
        [
            (100, 14.99, "impulse"),
            (300, 19.69, "optimal"),
            (500, 24.99, "premium"),
            (650, 29.99, "high_premium"),
        ],
    )
    def test_optimal_price_selection(
        self, char_count: int, expected_price: float, expected_tier: str
    ) -> None:
        """Test optimal price is correctly selected for various lengths."""
        result = get_optimal_price_for_length(char_count)

        assert result["price"] == expected_price
        assert result["tier_name"] == expected_tier
        assert result["in_range"] is True

    def test_in_range_true_for_valid_length(self) -> None:
        """Test in_range is True when length falls within a tier."""
        result = get_optimal_price_for_length(300)
        assert result["in_range"] is True

    def test_in_range_false_for_out_of_range(self) -> None:
        """Test in_range is False when length exceeds all tiers."""
        result = get_optimal_price_for_length(800)
        assert result["in_range"] is False

    def test_recommendation_for_valid_length(self) -> None:
        """Test recommendation mentions optimal pricing for valid length."""
        result = get_optimal_price_for_length(300)

        assert "Set price" in result["recommendation"]
        assert "$19.69" in result["recommendation"]
        assert "716" in result["recommendation"]

    def test_recommendation_for_exceeding_length(self) -> None:
        """Test recommendation for length exceeding max tier."""
        result = get_optimal_price_for_length(800)

        assert result["in_range"] is False
        assert result["price"] == 29.99
        assert "exceeds" in result["recommendation"].lower()

    def test_result_has_required_keys(self) -> None:
        """Test result contains all required keys."""
        result = get_optimal_price_for_length(300)
        required_keys = {
            "price",
            "tier_name",
            "expected_rps",
            "optimal_range",
            "in_range",
            "recommendation",
        }

        assert required_keys.issubset(result.keys())

    @pytest.mark.parametrize(
        "char_count",
        [0, 249, 250, 449, 450, 599, 600, 749],
    )
    def test_boundary_lengths_in_range(self, char_count: int) -> None:
        """Test boundary character counts are within range."""
        result = get_optimal_price_for_length(char_count)
        assert result["in_range"] is True

    def test_length_750_out_of_range(self) -> None:
        """Test 750 chars is out of range (max tier is 749)."""
        result = get_optimal_price_for_length(750)
        assert result["in_range"] is False


# =============================================================================
# Test calculate_rps_impact()
# =============================================================================


class TestCalculateRpsImpact:
    """Tests for calculate_rps_impact() function."""

    def test_returns_dict_with_required_keys(self) -> None:
        """Test function returns dict with all required keys."""
        result = calculate_rps_impact("A" * 300, 19.69)
        required_keys = {
            "current_state",
            "optimal_price",
            "effective_current_rps",
            "potential_optimal_rps",
            "rps_improvement",
            "improvement_percentage",
        }

        assert required_keys.issubset(result.keys())

    def test_valid_match_no_improvement(self) -> None:
        """Test valid price-length match shows no RPS improvement."""
        result = calculate_rps_impact("A" * 300, 19.69)

        assert result["current_state"]["is_valid"] is True
        assert result["rps_improvement"] == 0
        assert result["improvement_percentage"] == 0

    def test_invalid_match_shows_improvement(self) -> None:
        """Test invalid match shows potential RPS improvement."""
        # 100 chars at $19.69 is too short (should use $14.99)
        result = calculate_rps_impact("A" * 100, 19.69)

        assert result["current_state"]["is_valid"] is False
        assert result["rps_improvement"] > 0

    def test_effective_rps_calculation_with_penalty(self) -> None:
        """Test effective RPS applies penalty multiplier for mismatches."""
        result = calculate_rps_impact("A" * 100, 19.69)

        # $19.69 has 716 RPS, with 82% penalty (0.18 multiplier)
        # effective_rps should be approximately 716 * 0.18 = 129
        assert result["effective_current_rps"] < result["current_state"]["expected_rps"]

    def test_optimal_price_recommendation(self) -> None:
        """Test optimal price is recommended for current length."""
        result = calculate_rps_impact("A" * 100, 19.69)

        # 100 chars optimal for $14.99
        assert result["optimal_price"]["price"] == 14.99

    def test_target_price_analysis(self) -> None:
        """Test target_price parameter triggers target analysis."""
        result = calculate_rps_impact("A" * 300, 19.69, target_price=24.99)

        assert "target_analysis" in result
        assert result["target_analysis"]["price"] == 24.99
        assert result["target_analysis"]["is_valid"] is False  # 300 chars too short for $24.99

    def test_empty_caption_raises_validation_error(self) -> None:
        """Test empty caption raises ValidationError."""
        with pytest.raises(ValidationError):
            calculate_rps_impact("", 19.69)

    def test_improvement_percentage_calculation(self) -> None:
        """Test improvement percentage is calculated correctly."""
        result = calculate_rps_impact("A" * 100, 19.69)

        if result["effective_current_rps"] > 0:
            expected_pct = round(
                (result["rps_improvement"] / result["effective_current_rps"]) * 100, 1
            )
            assert result["improvement_percentage"] == expected_pct

    def test_critical_mismatch_impact(self) -> None:
        """Test impact analysis for CRITICAL $19.69 mismatch scenario."""
        result = calculate_rps_impact("Short", 19.69)

        assert result["current_state"]["severity"] == "CRITICAL"
        assert result["current_state"]["expected_rps_loss"] == "82%"
        # Should recommend $14.99 for short captions
        assert result["optimal_price"]["price"] == 14.99


# =============================================================================
# Test validate_batch()
# =============================================================================


class TestValidateBatch:
    """Tests for validate_batch() function."""

    def test_empty_batch_returns_empty_results(self) -> None:
        """Test empty batch returns empty results."""
        result = validate_batch([])

        assert result["results"] == []
        assert result["summary"]["total"] == 0
        assert result["critical_count"] == 0

    def test_all_valid_batch(self) -> None:
        """Test batch with all valid items."""
        items = [
            {"caption": "A" * 100, "price": 14.99},
            {"caption": "A" * 300, "price": 19.69},
            {"caption": "A" * 500, "price": 24.99},
        ]
        result = validate_batch(items)

        assert result["summary"]["total"] == 3
        assert result["summary"]["valid_count"] == 3
        assert result["summary"]["invalid_count"] == 0
        assert result["critical_count"] == 0

    def test_all_invalid_batch(self) -> None:
        """Test batch with all invalid items."""
        items = [
            {"caption": "Short", "price": 19.69},  # Too short - CRITICAL
            {"caption": "A" * 300, "price": 14.99},  # Too long
            {"caption": "A" * 200, "price": 24.99},  # Too short
        ]
        result = validate_batch(items)

        assert result["summary"]["valid_count"] == 0
        assert result["summary"]["invalid_count"] == 3

    def test_mixed_batch(self) -> None:
        """Test batch with mixed valid and invalid items."""
        items = [
            {"caption": "Short", "price": 19.69},  # Invalid - CRITICAL
            {"caption": "A" * 300, "price": 19.69},  # Valid
            {"caption": "A" * 100, "price": 14.99},  # Valid
        ]
        result = validate_batch(items)

        assert result["summary"]["valid_count"] == 2
        assert result["summary"]["invalid_count"] == 1
        assert result["critical_count"] == 1

    def test_results_have_index(self) -> None:
        """Test each result includes its index."""
        items = [
            {"caption": "A" * 100, "price": 14.99},
            {"caption": "A" * 300, "price": 19.69},
        ]
        result = validate_batch(items)

        for i, item_result in enumerate(result["results"]):
            assert item_result["index"] == i

    def test_critical_count_accurate(self) -> None:
        """Test critical_count accurately counts CRITICAL mismatches."""
        items = [
            {"caption": "Short1", "price": 19.69},  # CRITICAL
            {"caption": "Short2", "price": 19.69},  # CRITICAL
            {"caption": "A" * 300, "price": 19.69},  # Valid
        ]
        result = validate_batch(items)

        assert result["critical_count"] == 2

    def test_high_count_tracked(self) -> None:
        """Test high_count tracks HIGH severity mismatches."""
        items = [
            {"caption": "A" * 500, "price": 19.69},  # Too long - HIGH severity
        ]
        result = validate_batch(items)

        assert result["high_count"] == 1

    def test_rps_at_risk_calculation(self) -> None:
        """Test total_rps_at_risk is calculated for CRITICAL and HIGH mismatches."""
        items = [
            {"caption": "Short", "price": 19.69},  # CRITICAL - 82% of 716 at risk
        ]
        result = validate_batch(items)

        # 82% of 716 = 587 (approximately)
        assert result["total_rps_at_risk"] > 0

    def test_handles_invalid_items_gracefully(self) -> None:
        """Test batch handles invalid items (empty caption) gracefully."""
        items = [
            {"caption": "", "price": 19.69},  # Invalid - empty caption
            {"caption": "A" * 300, "price": 19.69},  # Valid
        ]
        result = validate_batch(items)

        assert result["summary"]["total"] == 2
        assert result["summary"]["invalid_count"] == 1
        assert result["results"][0]["error"] is not None

    def test_valid_percentage_calculation(self) -> None:
        """Test valid_percentage is calculated correctly."""
        items = [
            {"caption": "A" * 300, "price": 19.69},  # Valid
            {"caption": "Short", "price": 19.69},  # Invalid
        ]
        result = validate_batch(items)

        assert result["summary"]["valid_percentage"] == 50.0

    def test_summary_structure(self) -> None:
        """Test summary has correct structure."""
        items = [{"caption": "A" * 300, "price": 19.69}]
        result = validate_batch(items)

        summary = result["summary"]
        assert "total" in summary
        assert "valid_count" in summary
        assert "invalid_count" in summary
        assert "valid_percentage" in summary

    @pytest.mark.parametrize(
        "price,caption_len,expected_severity",
        [
            (19.69, 100, "CRITICAL"),  # Too short for $19.69
            (29.99, 200, "CRITICAL"),  # Too short for $29.99
            (19.69, 500, "HIGH"),  # Too long for $19.69
            (24.99, 200, "HIGH"),  # Too short for $24.99
        ],
    )
    def test_severity_levels_in_batch(
        self, price: float, caption_len: int, expected_severity: str
    ) -> None:
        """Test batch correctly identifies severity levels."""
        items = [{"caption": "A" * caption_len, "price": price}]
        result = validate_batch(items)

        assert result["results"][0]["severity"] == expected_severity


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_full_validation_workflow(self) -> None:
        """Test complete validation workflow from input to recommendations."""
        # Scenario: Creator has a 300-char caption priced at $14.99
        caption = "A" * 300
        current_price = 14.99

        # Validate current state
        validation = validate_price_length_match(caption, current_price)
        assert validation["is_valid"] is False  # Too long for $14.99

        # Get optimal price recommendation
        optimal = get_optimal_price_for_length(len(caption))
        assert optimal["price"] == 19.69  # Should recommend optimal tier

        # Calculate RPS impact
        impact = calculate_rps_impact(caption, current_price)
        assert impact["rps_improvement"] > 0  # Should show improvement potential

    def test_schedule_batch_validation(self) -> None:
        """Test validating a day's worth of scheduled PPV sends."""
        daily_schedule = [
            {"caption": "A" * 280, "price": 19.69},  # Valid
            {"caption": "A" * 350, "price": 19.69},  # Valid
            {"caption": "A" * 150, "price": 14.99},  # Valid
            {"caption": "A" * 500, "price": 24.99},  # Valid
        ]

        result = validate_batch(daily_schedule)

        assert result["summary"]["valid_percentage"] == 100.0
        assert result["critical_count"] == 0
        assert result["total_rps_at_risk"] == 0

    def test_problematic_schedule_identification(self) -> None:
        """Test identifying problematic sends in a schedule."""
        problematic_schedule = [
            {"caption": "Short PPV", "price": 19.69},  # CRITICAL
            {"caption": "A" * 300, "price": 19.69},  # Valid
            {"caption": "A" * 600, "price": 19.69},  # Invalid - too long
        ]

        result = validate_batch(problematic_schedule)

        assert result["critical_count"] == 1
        assert result["summary"]["invalid_count"] == 2

        # Find problematic items
        problematic = [r for r in result["results"] if not r.get("is_valid", True)]
        assert len(problematic) == 2
