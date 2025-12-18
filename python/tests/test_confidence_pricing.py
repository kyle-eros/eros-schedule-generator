"""
Unit tests for confidence-based pricing adjustment module.

Tests cover:
- CONFIDENCE_PRICING_MULTIPLIERS threshold validation
- get_confidence_price_multiplier() tier mapping
- adjust_price_by_confidence() full integration
- Standard price point snapping behavior
- Edge cases at tier boundaries
- Error handling for invalid inputs
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.pricing.confidence_pricing import (
    CONFIDENCE_PRICING_MULTIPLIERS,
    STANDARD_PRICE_POINTS,
    _get_adjustment_reason,
    _get_confidence_tier,
    _round_to_price_point,
    adjust_price_by_confidence,
    get_confidence_price_multiplier,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def high_confidence() -> float:
    """Confidence score in the high tier (0.80-1.00)."""
    return 0.90


@pytest.fixture
def medium_confidence() -> float:
    """Confidence score in the medium tier (0.60-0.79)."""
    return 0.70


@pytest.fixture
def low_confidence() -> float:
    """Confidence score in the low tier (0.40-0.59)."""
    return 0.50


@pytest.fixture
def very_low_confidence() -> float:
    """Confidence score in the very_low tier (0.00-0.39)."""
    return 0.25


@pytest.fixture
def standard_base_price() -> float:
    """Standard base price for testing."""
    return 29.99


# =============================================================================
# Test Classes
# =============================================================================


class TestConfidencePricingMultipliers:
    """Tests for CONFIDENCE_PRICING_MULTIPLIERS constant structure."""

    def test_multipliers_has_four_tiers(self) -> None:
        """Should have exactly four confidence tiers."""
        assert len(CONFIDENCE_PRICING_MULTIPLIERS) == 4
        assert set(CONFIDENCE_PRICING_MULTIPLIERS.keys()) == {
            "high",
            "medium",
            "low",
            "very_low",
        }

    def test_each_tier_has_required_keys(self) -> None:
        """Each tier should have min, max, and multiplier keys."""
        for tier_name, tier_config in CONFIDENCE_PRICING_MULTIPLIERS.items():
            assert "min" in tier_config, f"Tier {tier_name} missing 'min'"
            assert "max" in tier_config, f"Tier {tier_name} missing 'max'"
            assert "multiplier" in tier_config, f"Tier {tier_name} missing 'multiplier'"

    def test_high_tier_values(self) -> None:
        """High tier should be 0.80-1.00 with multiplier 1.00."""
        tier = CONFIDENCE_PRICING_MULTIPLIERS["high"]
        assert tier["min"] == 0.80
        assert tier["max"] == 1.00
        assert tier["multiplier"] == 1.00

    def test_medium_tier_values(self) -> None:
        """Medium tier should be 0.60-0.79 with multiplier 0.85."""
        tier = CONFIDENCE_PRICING_MULTIPLIERS["medium"]
        assert tier["min"] == 0.60
        assert tier["max"] == 0.79
        assert tier["multiplier"] == 0.85

    def test_low_tier_values(self) -> None:
        """Low tier should be 0.40-0.59 with multiplier 0.70."""
        tier = CONFIDENCE_PRICING_MULTIPLIERS["low"]
        assert tier["min"] == 0.40
        assert tier["max"] == 0.59
        assert tier["multiplier"] == 0.70

    def test_very_low_tier_values(self) -> None:
        """Very low tier should be 0.00-0.39 with multiplier 0.60."""
        tier = CONFIDENCE_PRICING_MULTIPLIERS["very_low"]
        assert tier["min"] == 0.00
        assert tier["max"] == 0.39
        assert tier["multiplier"] == 0.60

    def test_multipliers_decrease_with_confidence(self) -> None:
        """Multipliers should decrease as confidence tiers decrease."""
        high = CONFIDENCE_PRICING_MULTIPLIERS["high"]["multiplier"]
        medium = CONFIDENCE_PRICING_MULTIPLIERS["medium"]["multiplier"]
        low = CONFIDENCE_PRICING_MULTIPLIERS["low"]["multiplier"]
        very_low = CONFIDENCE_PRICING_MULTIPLIERS["very_low"]["multiplier"]

        assert high > medium > low > very_low

    def test_all_multipliers_in_valid_range(self) -> None:
        """All multipliers should be between 0.0 and 1.0."""
        for tier_name, tier_config in CONFIDENCE_PRICING_MULTIPLIERS.items():
            multiplier = tier_config["multiplier"]
            assert 0.0 < multiplier <= 1.0, f"Tier {tier_name} has invalid multiplier"


class TestStandardPricePoints:
    """Tests for STANDARD_PRICE_POINTS constant."""

    def test_price_points_not_empty(self) -> None:
        """Should have at least one price point."""
        assert len(STANDARD_PRICE_POINTS) > 0

    def test_price_points_sorted_ascending(self) -> None:
        """Price points should be sorted in ascending order."""
        assert STANDARD_PRICE_POINTS == sorted(STANDARD_PRICE_POINTS)

    def test_price_points_all_positive(self) -> None:
        """All price points should be positive."""
        for price in STANDARD_PRICE_POINTS:
            assert price > 0

    def test_price_points_expected_values(self) -> None:
        """Price points should match expected standard values."""
        expected = [9.99, 14.99, 19.69, 24.99, 29.99, 34.99, 39.99]
        assert STANDARD_PRICE_POINTS == expected


class TestGetConfidencePriceMultiplier:
    """Tests for get_confidence_price_multiplier function."""

    def test_high_confidence_returns_1_0(self, high_confidence: float) -> None:
        """High confidence (0.80-1.00) should return multiplier 1.0."""
        assert get_confidence_price_multiplier(high_confidence) == 1.0

    def test_medium_confidence_returns_0_85(self, medium_confidence: float) -> None:
        """Medium confidence (0.60-0.79) should return multiplier 0.85."""
        assert get_confidence_price_multiplier(medium_confidence) == 0.85

    def test_low_confidence_returns_0_70(self, low_confidence: float) -> None:
        """Low confidence (0.40-0.59) should return multiplier 0.70."""
        assert get_confidence_price_multiplier(low_confidence) == 0.70

    def test_very_low_confidence_returns_0_60(
        self, very_low_confidence: float
    ) -> None:
        """Very low confidence (0.00-0.39) should return multiplier 0.60."""
        assert get_confidence_price_multiplier(very_low_confidence) == 0.60

    def test_exact_boundary_0_80(self) -> None:
        """Exactly 0.80 should be in high tier (multiplier 1.0)."""
        assert get_confidence_price_multiplier(0.80) == 1.0

    def test_exact_boundary_0_60(self) -> None:
        """Exactly 0.60 should be in medium tier (multiplier 0.85)."""
        assert get_confidence_price_multiplier(0.60) == 0.85

    def test_exact_boundary_0_40(self) -> None:
        """Exactly 0.40 should be in low tier (multiplier 0.70)."""
        assert get_confidence_price_multiplier(0.40) == 0.70

    def test_exact_boundary_0_00(self) -> None:
        """Exactly 0.00 should be in very_low tier (multiplier 0.60)."""
        assert get_confidence_price_multiplier(0.00) == 0.60

    def test_exact_boundary_1_00(self) -> None:
        """Exactly 1.00 should be in high tier (multiplier 1.0)."""
        assert get_confidence_price_multiplier(1.00) == 1.0

    def test_just_below_0_80(self) -> None:
        """0.79999... should be in medium tier (multiplier 0.85)."""
        assert get_confidence_price_multiplier(0.7999) == 0.85

    def test_just_below_0_60(self) -> None:
        """0.59999... should be in low tier (multiplier 0.70)."""
        assert get_confidence_price_multiplier(0.5999) == 0.70

    def test_just_below_0_40(self) -> None:
        """0.39999... should be in very_low tier (multiplier 0.60)."""
        assert get_confidence_price_multiplier(0.3999) == 0.60

    def test_raises_for_negative_confidence(self) -> None:
        """Should raise ValueError for negative confidence."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            get_confidence_price_multiplier(-0.1)

    def test_raises_for_confidence_above_1(self) -> None:
        """Should raise ValueError for confidence above 1.0."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            get_confidence_price_multiplier(1.1)

    @pytest.mark.parametrize(
        "confidence,expected_multiplier",
        [
            # High tier (0.80-1.00)
            (1.00, 1.0),
            (0.95, 1.0),
            (0.85, 1.0),
            (0.80, 1.0),
            # Medium tier (0.60-0.79)
            (0.79, 0.85),
            (0.75, 0.85),
            (0.65, 0.85),
            (0.60, 0.85),
            # Low tier (0.40-0.59)
            (0.59, 0.70),
            (0.55, 0.70),
            (0.45, 0.70),
            (0.40, 0.70),
            # Very low tier (0.00-0.39)
            (0.39, 0.60),
            (0.30, 0.60),
            (0.15, 0.60),
            (0.00, 0.60),
        ],
    )
    def test_multiplier_tiers_parametrized(
        self,
        confidence: float,
        expected_multiplier: float,
    ) -> None:
        """Parametrized test for all confidence tier boundaries."""
        assert get_confidence_price_multiplier(confidence) == expected_multiplier


class TestGetConfidenceTier:
    """Tests for _get_confidence_tier helper function."""

    def test_high_tier_at_0_80(self) -> None:
        """0.80 should return 'high' tier."""
        assert _get_confidence_tier(0.80) == "high"

    def test_high_tier_at_1_00(self) -> None:
        """1.00 should return 'high' tier."""
        assert _get_confidence_tier(1.00) == "high"

    def test_medium_tier_at_0_60(self) -> None:
        """0.60 should return 'medium' tier."""
        assert _get_confidence_tier(0.60) == "medium"

    def test_medium_tier_at_0_79(self) -> None:
        """0.79 should return 'medium' tier."""
        assert _get_confidence_tier(0.79) == "medium"

    def test_low_tier_at_0_40(self) -> None:
        """0.40 should return 'low' tier."""
        assert _get_confidence_tier(0.40) == "low"

    def test_low_tier_at_0_59(self) -> None:
        """0.59 should return 'low' tier."""
        assert _get_confidence_tier(0.59) == "low"

    def test_very_low_tier_at_0_00(self) -> None:
        """0.00 should return 'very_low' tier."""
        assert _get_confidence_tier(0.00) == "very_low"

    def test_very_low_tier_at_0_39(self) -> None:
        """0.39 should return 'very_low' tier."""
        assert _get_confidence_tier(0.39) == "very_low"

    @pytest.mark.parametrize(
        "confidence,expected_tier",
        [
            (1.0, "high"),
            (0.90, "high"),
            (0.80, "high"),
            (0.79, "medium"),
            (0.70, "medium"),
            (0.60, "medium"),
            (0.59, "low"),
            (0.50, "low"),
            (0.40, "low"),
            (0.39, "very_low"),
            (0.20, "very_low"),
            (0.0, "very_low"),
        ],
    )
    def test_tier_names_parametrized(
        self,
        confidence: float,
        expected_tier: str,
    ) -> None:
        """Parametrized test for tier name mapping."""
        assert _get_confidence_tier(confidence) == expected_tier


class TestRoundToPricePoint:
    """Tests for _round_to_price_point helper function."""

    def test_exact_price_point_unchanged(self) -> None:
        """Exact price points should remain unchanged."""
        for price in STANDARD_PRICE_POINTS:
            assert _round_to_price_point(price) == price

    def test_rounds_to_nearest_lower_point(self) -> None:
        """Prices slightly above a point should round to nearest."""
        # 28.50 is closer to 29.99 than 24.99
        assert _round_to_price_point(28.50) == 29.99

    def test_rounds_to_nearest_higher_point(self) -> None:
        """Prices between points should round to nearest."""
        # 12.00 is closer to 9.99 than 14.99
        assert _round_to_price_point(12.00) == 9.99

    def test_rounds_midpoint_to_nearest(self) -> None:
        """Midpoint between two prices should round to first nearest."""
        # Midpoint between 24.99 and 29.99 is exactly 27.49
        # At exact midpoint, min() returns first match (24.99)
        assert _round_to_price_point(27.49) == 24.99
        # Slightly above midpoint rounds to higher
        assert _round_to_price_point(27.50) == 29.99

    def test_below_lowest_price_point(self) -> None:
        """Price below lowest point should round to lowest."""
        assert _round_to_price_point(5.00) == 9.99

    def test_above_highest_price_point(self) -> None:
        """Price above highest point should round to highest."""
        assert _round_to_price_point(50.00) == 39.99

    def test_negative_price_rounds_to_lowest(self) -> None:
        """Negative prices should round to lowest standard point."""
        assert _round_to_price_point(-5.00) == 9.99

    def test_zero_price_rounds_to_lowest(self) -> None:
        """Zero price should round to lowest standard point."""
        assert _round_to_price_point(0.00) == 9.99

    @pytest.mark.parametrize(
        "price,expected",
        [
            (5.00, 9.99),    # Below range
            (9.99, 9.99),    # Exact match
            (12.00, 9.99),   # Between 9.99 and 14.99, closer to 9.99
            (12.50, 14.99),  # Between 9.99 and 14.99, closer to 14.99
            (14.99, 14.99),  # Exact match
            (17.00, 14.99),  # Between 14.99 and 19.69, closer to 14.99
            (19.69, 19.69),  # Exact match
            (22.00, 19.69),  # Between 19.69 and 24.99, closer to 19.69
            (24.99, 24.99),  # Exact match
            (27.00, 24.99),  # Between 24.99 and 29.99, closer to 24.99
            (29.99, 29.99),  # Exact match
            (32.00, 29.99),  # Between 29.99 and 34.99, closer to 29.99
            (34.99, 34.99),  # Exact match
            (37.00, 34.99),  # Between 34.99 and 39.99, closer to 34.99
            (39.99, 39.99),  # Exact match
            (45.00, 39.99),  # Above range
        ],
    )
    def test_rounding_parametrized(self, price: float, expected: float) -> None:
        """Parametrized test for price rounding behavior."""
        assert _round_to_price_point(price) == expected


class TestGetAdjustmentReason:
    """Tests for _get_adjustment_reason helper function."""

    def test_high_confidence_premium_pricing(self) -> None:
        """High confidence should indicate premium pricing maintained."""
        reason = _get_adjustment_reason(
            confidence=0.90,
            multiplier=1.0,
            base_price=29.99,
            suggested_price=29.99,
        )
        assert "Established creator" in reason
        assert "maintaining premium pricing" in reason

    def test_medium_confidence_discount_message(self) -> None:
        """Medium confidence should indicate 15% discount."""
        reason = _get_adjustment_reason(
            confidence=0.70,
            multiplier=0.85,
            base_price=29.99,
            suggested_price=24.99,
        )
        assert "Growing creator" in reason
        assert "15% discount" in reason
        assert "$29.99 -> $24.99" in reason

    def test_low_confidence_discount_message(self) -> None:
        """Low confidence should indicate 30% discount."""
        reason = _get_adjustment_reason(
            confidence=0.50,
            multiplier=0.70,
            base_price=29.99,
            suggested_price=19.69,
        )
        assert "Newer creator" in reason
        assert "30% discount" in reason

    def test_very_low_confidence_discount_message(self) -> None:
        """Very low confidence should indicate 40% discount."""
        reason = _get_adjustment_reason(
            confidence=0.20,
            multiplier=0.60,
            base_price=29.99,
            suggested_price=19.69,
        )
        assert "New creator" in reason
        assert "40% discount" in reason


class TestAdjustPriceByConfidence:
    """Tests for adjust_price_by_confidence function."""

    def test_returns_dict_with_required_keys(
        self, standard_base_price: float, high_confidence: float
    ) -> None:
        """Result should contain all required keys."""
        result = adjust_price_by_confidence(standard_base_price, high_confidence)

        required_keys = {
            "base_price",
            "confidence",
            "multiplier",
            "calculated_price",
            "suggested_price",
            "adjustment_reason",
        }
        assert set(result.keys()) == required_keys

    def test_high_confidence_no_discount(
        self, standard_base_price: float, high_confidence: float
    ) -> None:
        """High confidence should maintain base price."""
        result = adjust_price_by_confidence(standard_base_price, high_confidence)

        assert result["multiplier"] == 1.0
        assert result["calculated_price"] == standard_base_price
        assert result["suggested_price"] == standard_base_price

    def test_medium_confidence_15_percent_discount(
        self, standard_base_price: float, medium_confidence: float
    ) -> None:
        """Medium confidence should apply 15% discount."""
        result = adjust_price_by_confidence(standard_base_price, medium_confidence)

        assert result["multiplier"] == 0.85
        assert result["calculated_price"] == pytest.approx(25.49, rel=0.01)
        assert result["suggested_price"] == 24.99  # Snapped to price point

    def test_low_confidence_30_percent_discount(
        self, standard_base_price: float, low_confidence: float
    ) -> None:
        """Low confidence should apply 30% discount."""
        result = adjust_price_by_confidence(standard_base_price, low_confidence)

        assert result["multiplier"] == 0.70
        assert result["calculated_price"] == pytest.approx(20.99, rel=0.01)
        assert result["suggested_price"] == 19.69  # Snapped to price point

    def test_very_low_confidence_40_percent_discount(
        self, standard_base_price: float, very_low_confidence: float
    ) -> None:
        """Very low confidence should apply 40% discount."""
        result = adjust_price_by_confidence(standard_base_price, very_low_confidence)

        assert result["multiplier"] == 0.60
        assert result["calculated_price"] == pytest.approx(17.99, rel=0.01)
        assert result["suggested_price"] == 19.69  # Snapped to price point

    def test_preserves_base_price(
        self, standard_base_price: float, medium_confidence: float
    ) -> None:
        """Result should preserve original base price."""
        result = adjust_price_by_confidence(standard_base_price, medium_confidence)
        assert result["base_price"] == standard_base_price

    def test_preserves_confidence(
        self, standard_base_price: float, medium_confidence: float
    ) -> None:
        """Result should preserve input confidence."""
        result = adjust_price_by_confidence(standard_base_price, medium_confidence)
        assert result["confidence"] == medium_confidence

    def test_calculated_price_rounded(self) -> None:
        """Calculated price should be rounded to 2 decimal places."""
        result = adjust_price_by_confidence(29.99, 0.70)
        # 29.99 * 0.85 = 25.4915, should round to 25.49
        assert result["calculated_price"] == 25.49

    def test_raises_for_zero_base_price(self, high_confidence: float) -> None:
        """Should raise ValueError for zero base price."""
        with pytest.raises(ValueError, match="Base price must be positive"):
            adjust_price_by_confidence(0.0, high_confidence)

    def test_raises_for_negative_base_price(self, high_confidence: float) -> None:
        """Should raise ValueError for negative base price."""
        with pytest.raises(ValueError, match="Base price must be positive"):
            adjust_price_by_confidence(-10.00, high_confidence)

    def test_raises_for_invalid_confidence(self, standard_base_price: float) -> None:
        """Should raise ValueError for invalid confidence values."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            adjust_price_by_confidence(standard_base_price, 1.5)

        with pytest.raises(ValueError, match="Confidence must be between"):
            adjust_price_by_confidence(standard_base_price, -0.1)

    def test_has_adjustment_reason(
        self, standard_base_price: float, medium_confidence: float
    ) -> None:
        """Result should include human-readable adjustment reason."""
        result = adjust_price_by_confidence(standard_base_price, medium_confidence)
        assert isinstance(result["adjustment_reason"], str)
        assert len(result["adjustment_reason"]) > 0

    @pytest.mark.parametrize(
        "base_price,confidence,expected_multiplier,expected_suggested",
        [
            # High confidence - no discount
            (29.99, 0.85, 1.0, 29.99),
            (39.99, 0.95, 1.0, 39.99),
            # Medium confidence - 15% discount
            (29.99, 0.65, 0.85, 24.99),
            (39.99, 0.75, 0.85, 34.99),
            # Low confidence - 30% discount
            (29.99, 0.45, 0.70, 19.69),
            (39.99, 0.55, 0.70, 29.99),
            # Very low confidence - 40% discount
            (29.99, 0.30, 0.60, 19.69),
            (39.99, 0.20, 0.60, 24.99),
        ],
    )
    def test_price_adjustment_parametrized(
        self,
        base_price: float,
        confidence: float,
        expected_multiplier: float,
        expected_suggested: float,
    ) -> None:
        """Parametrized test for various price/confidence combinations."""
        result = adjust_price_by_confidence(base_price, confidence)
        assert result["multiplier"] == expected_multiplier
        assert result["suggested_price"] == expected_suggested


class TestEdgeCases:
    """Edge case tests for confidence pricing."""

    def test_exact_boundary_0_80(self) -> None:
        """Confidence exactly at 0.80 boundary should be high tier."""
        result = adjust_price_by_confidence(29.99, 0.80)
        assert result["multiplier"] == 1.0

    def test_exact_boundary_0_79(self) -> None:
        """Confidence exactly at 0.79 should be medium tier."""
        result = adjust_price_by_confidence(29.99, 0.79)
        assert result["multiplier"] == 0.85

    def test_exact_boundary_0_60(self) -> None:
        """Confidence exactly at 0.60 should be medium tier."""
        result = adjust_price_by_confidence(29.99, 0.60)
        assert result["multiplier"] == 0.85

    def test_exact_boundary_0_59(self) -> None:
        """Confidence exactly at 0.59 should be low tier."""
        result = adjust_price_by_confidence(29.99, 0.59)
        assert result["multiplier"] == 0.70

    def test_exact_boundary_0_40(self) -> None:
        """Confidence exactly at 0.40 should be low tier."""
        result = adjust_price_by_confidence(29.99, 0.40)
        assert result["multiplier"] == 0.70

    def test_exact_boundary_0_39(self) -> None:
        """Confidence exactly at 0.39 should be very_low tier."""
        result = adjust_price_by_confidence(29.99, 0.39)
        assert result["multiplier"] == 0.60

    def test_exact_boundary_0_00(self) -> None:
        """Confidence at 0.00 should be very_low tier."""
        result = adjust_price_by_confidence(29.99, 0.00)
        assert result["multiplier"] == 0.60

    def test_exact_boundary_1_00(self) -> None:
        """Confidence at 1.00 should be high tier."""
        result = adjust_price_by_confidence(29.99, 1.00)
        assert result["multiplier"] == 1.0

    def test_very_small_base_price(self) -> None:
        """Should handle very small positive base prices."""
        result = adjust_price_by_confidence(0.01, 0.50)
        assert result["multiplier"] == 0.70
        # 0.01 * 0.70 = 0.007, rounds to 9.99 (nearest standard point)
        assert result["suggested_price"] == 9.99

    def test_very_large_base_price(self) -> None:
        """Should handle very large base prices."""
        result = adjust_price_by_confidence(999.99, 0.50)
        assert result["multiplier"] == 0.70
        # 999.99 * 0.70 = 699.993, rounds to 39.99 (nearest standard point)
        assert result["suggested_price"] == 39.99

    def test_floating_point_precision(self) -> None:
        """Should handle floating point precision gracefully."""
        # Edge case that might cause floating point issues
        result = adjust_price_by_confidence(29.99, 0.85)
        assert result["calculated_price"] == 29.99

    def test_minimum_suggested_price(self) -> None:
        """Suggested price should never go below minimum standard point."""
        # With 60% multiplier on a low base price
        result = adjust_price_by_confidence(5.00, 0.10)
        # 5.00 * 0.60 = 3.00, should snap to 9.99 (lowest)
        assert result["suggested_price"] == 9.99

    def test_maximum_suggested_price(self) -> None:
        """Suggested price should never exceed maximum standard point."""
        # With full multiplier on high base price
        result = adjust_price_by_confidence(100.00, 0.95)
        # 100.00 * 1.0 = 100.00, should snap to 39.99 (highest)
        assert result["suggested_price"] == 39.99


class TestIntegration:
    """Integration tests for confidence pricing workflow."""

    def test_new_creator_pricing_scenario(self) -> None:
        """New creator with low confidence should get discounted pricing."""
        # Scenario: New creator, premium content at $39.99, low data confidence
        result = adjust_price_by_confidence(39.99, 0.25)

        assert result["multiplier"] == 0.60
        assert result["suggested_price"] < 39.99
        assert "New creator" in result["adjustment_reason"]
        assert "40% discount" in result["adjustment_reason"]

    def test_established_creator_pricing_scenario(self) -> None:
        """Established creator with high confidence should maintain premium."""
        # Scenario: Established creator with lots of data
        result = adjust_price_by_confidence(39.99, 0.92)

        assert result["multiplier"] == 1.0
        assert result["suggested_price"] == 39.99
        assert "premium pricing" in result["adjustment_reason"]

    def test_growing_creator_pricing_scenario(self) -> None:
        """Growing creator with medium confidence should get moderate discount."""
        # Scenario: Creator building audience, moderate data confidence
        result = adjust_price_by_confidence(29.99, 0.68)

        assert result["multiplier"] == 0.85
        assert result["suggested_price"] == 24.99
        assert "Growing creator" in result["adjustment_reason"]

    def test_multiple_price_points_consistency(self) -> None:
        """Same confidence should produce consistent relative discounts."""
        confidence = 0.50  # Low tier

        prices = [14.99, 24.99, 34.99]
        results = [adjust_price_by_confidence(p, confidence) for p in prices]

        # All should have same multiplier
        multipliers = [r["multiplier"] for r in results]
        assert all(m == 0.70 for m in multipliers)

    def test_price_snapping_preserves_relative_order(self) -> None:
        """Higher base prices should result in higher or equal suggested prices."""
        confidence = 0.50

        low_result = adjust_price_by_confidence(19.99, confidence)
        high_result = adjust_price_by_confidence(39.99, confidence)

        assert high_result["suggested_price"] >= low_result["suggested_price"]
