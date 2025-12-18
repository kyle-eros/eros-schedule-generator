"""
Unit tests for confidence-adjusted volume multipliers.

Tests cover:
- Confidence calculation at each tier boundary
- Multiplier dampening with various confidence levels
- Edge cases (0 messages, negative messages, exact boundaries)
- Integration with volume calculation
- Verification that high confidence doesn't change multipliers
- Verification that low confidence pulls toward neutral
"""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.volume.confidence import (
    CONFIDENCE_TIERS,
    NEUTRAL_MULTIPLIER,
    ConfidenceAdjustedVolume,
    ConfidenceResult,
    apply_confidence_to_multipliers,
    apply_confidence_to_content_multipliers,
    apply_confidence_to_dow_multipliers,
    calculate_confidence,
    calculate_confidence_adjusted_volume,
    dampen_multiplier,
    dampen_multiplier_dict,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def full_confidence_messages() -> int:
    """Message count that yields full confidence (200+)."""
    return 250


@pytest.fixture
def high_confidence_messages() -> int:
    """Message count that yields high confidence (100-199)."""
    return 150


@pytest.fixture
def medium_confidence_messages() -> int:
    """Message count that yields medium confidence (50-99)."""
    return 75


@pytest.fixture
def low_confidence_messages() -> int:
    """Message count that yields low confidence (20-49)."""
    return 35


@pytest.fixture
def very_low_confidence_messages() -> int:
    """Message count that yields very low confidence (0-19)."""
    return 10


# =============================================================================
# Test Classes
# =============================================================================


class TestConfidenceCalculation:
    """Tests for calculate_confidence function."""

    def test_full_confidence_at_200_messages(self) -> None:
        """200 messages should yield full confidence (1.0)."""
        result = calculate_confidence(200)
        assert result.confidence == 1.0
        assert result.tier_name == "full"
        assert result.dampen_factor == 0.0

    def test_full_confidence_above_200_messages(self) -> None:
        """Messages above 200 should yield full confidence."""
        for count in [201, 500, 1000, 10000]:
            result = calculate_confidence(count)
            assert result.confidence == 1.0
            assert result.tier_name == "full"

    def test_high_confidence_at_100_messages(self) -> None:
        """100 messages should yield high confidence (0.8)."""
        result = calculate_confidence(100)
        assert result.confidence == 0.8
        assert result.tier_name == "high"
        assert result.dampen_factor == pytest.approx(0.2)

    def test_high_confidence_at_199_messages(self) -> None:
        """199 messages should yield high confidence (0.8)."""
        result = calculate_confidence(199)
        assert result.confidence == 0.8
        assert result.tier_name == "high"

    def test_medium_confidence_at_50_messages(self) -> None:
        """50 messages should yield medium confidence (0.6)."""
        result = calculate_confidence(50)
        assert result.confidence == 0.6
        assert result.tier_name == "medium"
        assert result.dampen_factor == pytest.approx(0.4)

    def test_medium_confidence_at_99_messages(self) -> None:
        """99 messages should yield medium confidence (0.6)."""
        result = calculate_confidence(99)
        assert result.confidence == 0.6
        assert result.tier_name == "medium"

    def test_low_confidence_at_20_messages(self) -> None:
        """20 messages should yield low confidence (0.4)."""
        result = calculate_confidence(20)
        assert result.confidence == 0.4
        assert result.tier_name == "low"
        assert result.dampen_factor == pytest.approx(0.6)

    def test_low_confidence_at_49_messages(self) -> None:
        """49 messages should yield low confidence (0.4)."""
        result = calculate_confidence(49)
        assert result.confidence == 0.4
        assert result.tier_name == "low"

    def test_very_low_confidence_at_0_messages(self) -> None:
        """0 messages should yield very low confidence (0.2)."""
        result = calculate_confidence(0)
        assert result.confidence == 0.2
        assert result.tier_name == "very_low"
        assert result.dampen_factor == pytest.approx(0.8)

    def test_very_low_confidence_at_19_messages(self) -> None:
        """19 messages should yield very low confidence (0.2)."""
        result = calculate_confidence(19)
        assert result.confidence == 0.2
        assert result.tier_name == "very_low"

    def test_negative_messages_treated_as_zero(self) -> None:
        """Negative message count should be treated as 0."""
        result = calculate_confidence(-10)
        assert result.confidence == 0.2
        assert result.message_count == 0
        assert result.tier_name == "very_low"

    def test_message_count_preserved(self) -> None:
        """Message count should be preserved in result."""
        result = calculate_confidence(150)
        assert result.message_count == 150

    @pytest.mark.parametrize(
        "message_count,expected_confidence,expected_tier",
        [
            (0, 0.2, "very_low"),
            (10, 0.2, "very_low"),
            (19, 0.2, "very_low"),
            (20, 0.4, "low"),
            (35, 0.4, "low"),
            (49, 0.4, "low"),
            (50, 0.6, "medium"),
            (75, 0.6, "medium"),
            (99, 0.6, "medium"),
            (100, 0.8, "high"),
            (150, 0.8, "high"),
            (199, 0.8, "high"),
            (200, 1.0, "full"),
            (500, 1.0, "full"),
            (1000, 1.0, "full"),
        ],
    )
    def test_confidence_tiers_parametrized(
        self,
        message_count: int,
        expected_confidence: float,
        expected_tier: str,
    ) -> None:
        """Parametrized test for all confidence tier boundaries."""
        result = calculate_confidence(message_count)
        assert result.confidence == expected_confidence
        assert result.tier_name == expected_tier


class TestConfidenceResultProperties:
    """Tests for ConfidenceResult properties."""

    def test_is_low_confidence_below_0_6(self) -> None:
        """is_low_confidence should be True for confidence < 0.6."""
        # Very low (0.2)
        result = calculate_confidence(10)
        assert result.is_low_confidence is True

        # Low (0.4)
        result = calculate_confidence(30)
        assert result.is_low_confidence is True

    def test_is_low_confidence_at_0_6_or_above(self) -> None:
        """is_low_confidence should be False for confidence >= 0.6."""
        # Medium (0.6)
        result = calculate_confidence(75)
        assert result.is_low_confidence is False

        # High (0.8)
        result = calculate_confidence(150)
        assert result.is_low_confidence is False

        # Full (1.0)
        result = calculate_confidence(250)
        assert result.is_low_confidence is False

    def test_dampen_factor_is_complement(self) -> None:
        """dampen_factor should equal 1 - confidence."""
        for count in [0, 25, 75, 150, 250]:
            result = calculate_confidence(count)
            assert result.dampen_factor == pytest.approx(1.0 - result.confidence)


class TestDampenMultiplier:
    """Tests for dampen_multiplier function."""

    def test_full_confidence_no_change(self) -> None:
        """Multiplier should be unchanged at full confidence."""
        assert dampen_multiplier(0.7, 1.0) == 0.7
        assert dampen_multiplier(0.9, 1.0) == 0.9
        assert dampen_multiplier(1.2, 1.0) == 1.2

    def test_zero_confidence_returns_neutral(self) -> None:
        """Multiplier should become neutral at zero confidence."""
        assert dampen_multiplier(0.7, 0.0) == 1.0
        assert dampen_multiplier(0.5, 0.0) == 1.0
        assert dampen_multiplier(1.5, 0.0) == 1.0

    def test_half_confidence_halfway_to_neutral(self) -> None:
        """Half confidence should move multiplier halfway to neutral."""
        # 0.7 -> 1.0 at confidence 0.5: 1.0 + (0.7 - 1.0) * 0.5 = 0.85
        assert dampen_multiplier(0.7, 0.5) == pytest.approx(0.85)

        # 1.2 -> 1.0 at confidence 0.5: 1.0 + (1.2 - 1.0) * 0.5 = 1.1
        assert dampen_multiplier(1.2, 0.5) == pytest.approx(1.1)

    def test_low_confidence_mostly_neutral(self) -> None:
        """Low confidence should move multiplier mostly to neutral."""
        # 0.7 at confidence 0.2: 1.0 + (0.7 - 1.0) * 0.2 = 0.94
        assert dampen_multiplier(0.7, 0.2) == pytest.approx(0.94)

        # 1.2 at confidence 0.3: 1.0 + (1.2 - 1.0) * 0.3 = 1.06
        assert dampen_multiplier(1.2, 0.3) == pytest.approx(1.06)

    def test_custom_neutral_value(self) -> None:
        """Dampening should work with custom neutral value."""
        # Using neutral=0.8 instead of 1.0
        # 0.5 at confidence 0.5: 0.8 + (0.5 - 0.8) * 0.5 = 0.65
        assert dampen_multiplier(0.5, 0.5, neutral=0.8) == pytest.approx(0.65)

    def test_saturation_multiplier_dampening(self) -> None:
        """Test typical saturation multiplier dampening scenarios."""
        # High saturation (0.7) with low confidence (0.4)
        # 1.0 + (0.7 - 1.0) * 0.4 = 0.88
        result = dampen_multiplier(0.7, 0.4)
        assert result == pytest.approx(0.88)
        assert result > 0.7  # Dampened toward neutral

    def test_opportunity_multiplier_dampening(self) -> None:
        """Test typical opportunity multiplier dampening scenarios."""
        # High opportunity (1.2) with low confidence (0.4)
        # 1.0 + (1.2 - 1.0) * 0.4 = 1.08
        result = dampen_multiplier(1.2, 0.4)
        assert result == pytest.approx(1.08)
        assert result < 1.2  # Dampened toward neutral

    def test_neutral_multiplier_unchanged(self) -> None:
        """Neutral multiplier (1.0) should be unchanged at any confidence."""
        for conf in [0.0, 0.2, 0.5, 0.8, 1.0]:
            assert dampen_multiplier(1.0, conf) == pytest.approx(1.0)

    @pytest.mark.parametrize(
        "multiplier,confidence,expected",
        [
            (0.7, 1.0, 0.7),
            (0.7, 0.8, 0.76),
            (0.7, 0.6, 0.82),
            (0.7, 0.4, 0.88),
            (0.7, 0.2, 0.94),
            (0.7, 0.0, 1.0),
            (1.2, 1.0, 1.2),
            (1.2, 0.8, 1.16),
            (1.2, 0.6, 1.12),
            (1.2, 0.4, 1.08),
            (1.2, 0.2, 1.04),
            (1.2, 0.0, 1.0),
        ],
    )
    def test_dampen_multiplier_parametrized(
        self,
        multiplier: float,
        confidence: float,
        expected: float,
    ) -> None:
        """Parametrized test for multiplier dampening."""
        assert dampen_multiplier(multiplier, confidence) == pytest.approx(expected)


class TestApplyConfidenceToMultipliers:
    """Tests for apply_confidence_to_multipliers function."""

    def test_full_confidence_no_dampening(
        self, full_confidence_messages: int
    ) -> None:
        """Full confidence should not dampen multipliers."""
        sat, opp, conf = apply_confidence_to_multipliers(
            saturation_multiplier=0.7,
            opportunity_multiplier=1.2,
            message_count=full_confidence_messages,
        )
        assert sat == 0.7
        assert opp == 1.2
        assert conf.confidence == 1.0

    def test_high_confidence_slight_dampening(
        self, high_confidence_messages: int
    ) -> None:
        """High confidence should slightly dampen multipliers."""
        sat, opp, conf = apply_confidence_to_multipliers(
            saturation_multiplier=0.7,
            opportunity_multiplier=1.2,
            message_count=high_confidence_messages,
        )
        # At 0.8 confidence
        assert sat == pytest.approx(0.76)  # 1.0 + (0.7 - 1.0) * 0.8
        assert opp == pytest.approx(1.16)  # 1.0 + (1.2 - 1.0) * 0.8
        assert conf.confidence == 0.8

    def test_low_confidence_significant_dampening(
        self, low_confidence_messages: int
    ) -> None:
        """Low confidence should significantly dampen multipliers."""
        sat, opp, conf = apply_confidence_to_multipliers(
            saturation_multiplier=0.7,
            opportunity_multiplier=1.2,
            message_count=low_confidence_messages,
        )
        # At 0.4 confidence
        assert sat == pytest.approx(0.88)  # 1.0 + (0.7 - 1.0) * 0.4
        assert opp == pytest.approx(1.08)  # 1.0 + (1.2 - 1.0) * 0.4
        assert conf.confidence == 0.4
        assert conf.is_low_confidence is True

    def test_very_low_confidence_mostly_neutral(
        self, very_low_confidence_messages: int
    ) -> None:
        """Very low confidence should pull multipliers almost to neutral."""
        sat, opp, conf = apply_confidence_to_multipliers(
            saturation_multiplier=0.7,
            opportunity_multiplier=1.2,
            message_count=very_low_confidence_messages,
        )
        # At 0.2 confidence
        assert sat == pytest.approx(0.94)  # 1.0 + (0.7 - 1.0) * 0.2
        assert opp == pytest.approx(1.04)  # 1.0 + (1.2 - 1.0) * 0.2
        assert conf.confidence == 0.2

    def test_returns_confidence_result(self) -> None:
        """Should return valid ConfidenceResult."""
        sat, opp, conf = apply_confidence_to_multipliers(0.9, 1.1, 150)
        assert isinstance(conf, ConfidenceResult)
        assert conf.message_count == 150
        assert conf.tier_name == "high"


class TestCalculateConfidenceAdjustedVolume:
    """Tests for calculate_confidence_adjusted_volume function."""

    def test_full_confidence_volumes_unchanged(self) -> None:
        """Full confidence should apply multipliers without dampening."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=1.0,
            opportunity_multiplier=1.0,
            message_count=250,
            page_type="paid",
        )
        assert result.revenue_per_day == 5
        assert result.engagement_per_day == 4
        assert result.retention_per_day == 2
        assert result.adjustment_applied is False

    def test_high_saturation_with_full_confidence(self) -> None:
        """High saturation with full confidence should reduce volumes."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=0.7,  # High saturation
            opportunity_multiplier=1.0,
            message_count=250,
            page_type="paid",
        )
        # 0.7 * 5 = 3.5 -> 4
        assert result.revenue_per_day == 4
        # 0.7 * 4 = 2.8 -> 3
        assert result.engagement_per_day == 3
        # 0.7 * 2 = 1.4 -> 1
        assert result.retention_per_day == 1
        assert result.adjustment_applied is False

    def test_high_saturation_with_low_confidence(self) -> None:
        """High saturation should be dampened with low confidence."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=0.7,  # High saturation
            opportunity_multiplier=1.0,
            message_count=30,  # Low confidence (0.4)
            page_type="paid",
        )
        # Dampened sat mult: 1.0 + (0.7 - 1.0) * 0.4 = 0.88
        # 0.88 * 5 = 4.4 -> 4
        assert result.revenue_per_day == 4
        # 0.88 * 4 = 3.52 -> 4
        assert result.engagement_per_day == 4
        # 0.88 * 2 = 1.76 -> 2
        assert result.retention_per_day == 2
        assert result.adjustment_applied is True
        assert result.confidence.tier_name == "low"

    def test_high_opportunity_with_full_confidence(self) -> None:
        """High opportunity with full confidence should increase volumes."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=1.0,
            opportunity_multiplier=1.2,  # High opportunity
            message_count=250,
            page_type="paid",
        )
        # 1.2 * 5 = 6
        assert result.revenue_per_day == 6
        # 1.2 * 4 = 4.8 -> 5
        assert result.engagement_per_day == 5
        # Retention only uses saturation, not opportunity
        assert result.retention_per_day == 2

    def test_high_opportunity_with_low_confidence(self) -> None:
        """High opportunity should be dampened with low confidence."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=1.0,
            opportunity_multiplier=1.2,  # High opportunity
            message_count=30,  # Low confidence (0.4)
            page_type="paid",
        )
        # Dampened opp mult: 1.0 + (1.2 - 1.0) * 0.4 = 1.08
        # 1.08 * 5 = 5.4 -> 5
        assert result.revenue_per_day == 5
        # 1.08 * 4 = 4.32 -> 4
        assert result.engagement_per_day == 4
        assert result.adjustment_applied is True

    def test_free_page_zero_retention(self) -> None:
        """Free pages should always have 0 retention."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=6,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=1.0,
            opportunity_multiplier=1.0,
            message_count=250,
            page_type="free",
        )
        assert result.retention_per_day == 0

    def test_bounds_enforcement_minimum(self) -> None:
        """Volumes should not go below minimums."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=2,
            base_engagement=2,
            base_retention=1,
            saturation_multiplier=0.3,  # Very aggressive reduction
            opportunity_multiplier=0.5,  # Not realistic but tests bounds
            message_count=250,
            page_type="paid",
        )
        assert result.revenue_per_day >= 1
        assert result.engagement_per_day >= 1
        assert result.retention_per_day >= 0

    def test_bounds_enforcement_maximum(self) -> None:
        """Volumes should not exceed maximums."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=10,
            base_engagement=10,
            base_retention=5,
            saturation_multiplier=1.0,
            opportunity_multiplier=2.0,  # Not realistic but tests bounds
            message_count=250,
            page_type="paid",
        )
        assert result.revenue_per_day <= 8
        assert result.engagement_per_day <= 6
        assert result.retention_per_day <= 4

    def test_custom_bounds(self) -> None:
        """Custom bounds should be respected."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=1.0,
            opportunity_multiplier=1.0,
            message_count=250,
            page_type="paid",
            revenue_bounds=(2, 4),
            engagement_bounds=(1, 3),
            retention_bounds=(0, 1),
        )
        assert result.revenue_per_day <= 4
        assert result.engagement_per_day <= 3
        assert result.retention_per_day <= 1

    def test_original_multipliers_preserved(self) -> None:
        """Original multipliers should be preserved in result."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=0.7,
            opportunity_multiplier=1.2,
            message_count=30,
            page_type="paid",
        )
        assert result.original_multipliers == (0.7, 1.2)

    def test_adjusted_multipliers_different_from_original(self) -> None:
        """Adjusted multipliers should differ when dampening applied."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=0.7,
            opportunity_multiplier=1.2,
            message_count=30,  # Low confidence
            page_type="paid",
        )
        assert result.adjusted_multipliers != result.original_multipliers
        # Saturation should be pulled toward 1.0 (increased)
        assert result.adjusted_multipliers[0] > result.original_multipliers[0]
        # Opportunity should be pulled toward 1.0 (decreased)
        assert result.adjusted_multipliers[1] < result.original_multipliers[1]

    def test_total_per_day_property(self) -> None:
        """total_per_day should sum all categories."""
        result = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=1.0,
            opportunity_multiplier=1.0,
            message_count=250,
            page_type="paid",
        )
        expected = result.revenue_per_day + result.engagement_per_day + result.retention_per_day
        assert result.total_per_day == expected


class TestEdgeCases:
    """Edge case tests."""

    def test_zero_messages(self) -> None:
        """Zero messages should yield very low confidence."""
        result = calculate_confidence(0)
        assert result.confidence == 0.2
        assert result.tier_name == "very_low"

    def test_negative_messages_treated_as_zero(self) -> None:
        """Negative message count should be treated as 0."""
        result = calculate_confidence(-100)
        assert result.message_count == 0
        assert result.confidence == 0.2

    def test_exact_boundary_20_messages(self) -> None:
        """Exactly 20 messages should be low confidence."""
        result = calculate_confidence(20)
        assert result.confidence == 0.4
        assert result.tier_name == "low"

    def test_exact_boundary_50_messages(self) -> None:
        """Exactly 50 messages should be medium confidence."""
        result = calculate_confidence(50)
        assert result.confidence == 0.6
        assert result.tier_name == "medium"

    def test_exact_boundary_100_messages(self) -> None:
        """Exactly 100 messages should be high confidence."""
        result = calculate_confidence(100)
        assert result.confidence == 0.8
        assert result.tier_name == "high"

    def test_exact_boundary_200_messages(self) -> None:
        """Exactly 200 messages should be full confidence."""
        result = calculate_confidence(200)
        assert result.confidence == 1.0
        assert result.tier_name == "full"

    def test_confidence_just_below_boundaries(self) -> None:
        """Test values just below each boundary."""
        assert calculate_confidence(19).confidence == 0.2
        assert calculate_confidence(49).confidence == 0.4
        assert calculate_confidence(99).confidence == 0.6
        assert calculate_confidence(199).confidence == 0.8

    def test_multiplier_at_neutral(self) -> None:
        """Neutral multiplier should be unchanged regardless of confidence."""
        for conf in [0.0, 0.2, 0.5, 0.8, 1.0]:
            result = dampen_multiplier(1.0, conf)
            assert result == pytest.approx(1.0)

    def test_extreme_multiplier_values(self) -> None:
        """Test dampening with extreme multiplier values."""
        # Very low multiplier
        assert dampen_multiplier(0.1, 0.5) == pytest.approx(0.55)
        # Very high multiplier
        assert dampen_multiplier(2.0, 0.5) == pytest.approx(1.5)

    def test_confidence_above_1_treated_as_1(self) -> None:
        """Confidence values above 1.0 should be treated as 1.0."""
        result = dampen_multiplier(0.7, 1.5)
        assert result == 0.7

    def test_confidence_below_0_treated_as_0(self) -> None:
        """Confidence values below 0.0 should be treated as 0.0."""
        result = dampen_multiplier(0.7, -0.5)
        assert result == 1.0


class TestConfidenceIntegration:
    """Integration tests for confidence with volume calculation."""

    def test_new_creator_scenario(self) -> None:
        """New creator with 15 messages should have dampened multipliers."""
        # Scenario: New creator showing high saturation signal
        result = calculate_confidence_adjusted_volume(
            base_revenue=4,
            base_engagement=3,
            base_retention=2,
            saturation_multiplier=0.7,  # Data suggests high saturation
            opportunity_multiplier=1.0,
            message_count=15,  # But only 15 messages - not reliable
            page_type="paid",
        )
        # With very low confidence (0.2), saturation mult dampened to ~0.94
        # Volumes should be close to base, not aggressively reduced
        assert result.revenue_per_day >= 3
        assert result.engagement_per_day >= 3
        assert result.adjustment_applied is True
        assert result.confidence.tier_name == "very_low"

    def test_established_creator_scenario(self) -> None:
        """Established creator with 500 messages should have full multipliers."""
        # Scenario: Established creator with reliable saturation data
        result = calculate_confidence_adjusted_volume(
            base_revenue=4,
            base_engagement=3,
            base_retention=2,
            saturation_multiplier=0.7,  # Confident high saturation
            opportunity_multiplier=1.0,
            message_count=500,  # Lots of data
            page_type="paid",
        )
        # Full confidence - multipliers applied as-is
        assert result.revenue_per_day <= 3  # Reduced due to saturation
        assert result.adjustment_applied is False
        assert result.confidence.tier_name == "full"

    def test_volatile_signals_stabilized(self) -> None:
        """Aggressive signals should be stabilized for low data creators."""
        # Same base, same aggressive multipliers, different message counts
        low_data = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=0.7,
            opportunity_multiplier=1.2,
            message_count=25,
            page_type="paid",
        )

        high_data = calculate_confidence_adjusted_volume(
            base_revenue=5,
            base_engagement=4,
            base_retention=2,
            saturation_multiplier=0.7,
            opportunity_multiplier=1.2,
            message_count=300,
            page_type="paid",
        )

        # Low data result should be closer to base (5, 4, 2)
        # High data result should show full multiplier effect
        # Combined mult for high data: 0.7 * 1.2 = 0.84
        # Combined mult for low data (dampened): ~0.88 * ~1.08 = ~0.95

        assert low_data.revenue_per_day >= high_data.revenue_per_day
        assert low_data.adjustment_applied is True
        assert high_data.adjustment_applied is False


class TestDampenMultiplierDict:
    """Tests for dampen_multiplier_dict function."""

    def test_dampen_dict_with_int_keys(self) -> None:
        """Should dampen dict with integer keys (like DOW)."""
        dow_mults = {0: 0.8, 1: 1.0, 2: 1.2, 3: 1.0, 4: 1.1, 5: 1.2, 6: 1.1}
        dampened = dampen_multiplier_dict(dow_mults, 0.5)

        # At 0.5 confidence, values move halfway to 1.0
        assert dampened[0] == pytest.approx(0.9)  # 0.8 -> 0.9
        assert dampened[1] == pytest.approx(1.0)  # 1.0 -> 1.0 (neutral)
        assert dampened[2] == pytest.approx(1.1)  # 1.2 -> 1.1
        assert dampened[4] == pytest.approx(1.05)  # 1.1 -> 1.05
        assert dampened[6] == pytest.approx(1.05)  # 1.1 -> 1.05

    def test_dampen_dict_with_str_keys(self) -> None:
        """Should dampen dict with string keys (like content types)."""
        content_mults = {"ppv_unlock": 1.2, "bump_normal": 0.8, "link_drop": 0.7}
        dampened = dampen_multiplier_dict(content_mults, 0.4)

        # At 0.4 confidence
        assert dampened["ppv_unlock"] == pytest.approx(1.08)  # 1.0 + (1.2 - 1.0) * 0.4
        assert dampened["bump_normal"] == pytest.approx(0.92)  # 1.0 + (0.8 - 1.0) * 0.4
        assert dampened["link_drop"] == pytest.approx(0.88)  # 1.0 + (0.7 - 1.0) * 0.4

    def test_dampen_dict_full_confidence(self) -> None:
        """Full confidence should not change any values."""
        mults = {0: 0.7, 1: 1.2, 2: 0.8}
        dampened = dampen_multiplier_dict(mults, 1.0)

        assert dampened[0] == 0.7
        assert dampened[1] == 1.2
        assert dampened[2] == 0.8

    def test_dampen_dict_zero_confidence(self) -> None:
        """Zero confidence should return all neutral values."""
        mults = {0: 0.5, 1: 1.5, 2: 2.0}
        dampened = dampen_multiplier_dict(mults, 0.0)

        assert dampened[0] == pytest.approx(1.0)
        assert dampened[1] == pytest.approx(1.0)
        assert dampened[2] == pytest.approx(1.0)

    def test_dampen_dict_empty(self) -> None:
        """Should handle empty dict."""
        dampened = dampen_multiplier_dict({}, 0.5)
        assert dampened == {}

    def test_dampen_dict_custom_neutral(self) -> None:
        """Should work with custom neutral value."""
        mults = {0: 0.5, 1: 1.0}
        dampened = dampen_multiplier_dict(mults, 0.5, neutral=0.8)

        # At 0.5 confidence with neutral=0.8
        assert dampened[0] == pytest.approx(0.65)  # 0.8 + (0.5 - 0.8) * 0.5
        assert dampened[1] == pytest.approx(0.9)  # 0.8 + (1.0 - 0.8) * 0.5


class TestApplyConfidenceToDOWMultipliers:
    """Tests for apply_confidence_to_dow_multipliers function."""

    def test_full_confidence_no_dampening(self) -> None:
        """Full confidence should not dampen DOW multipliers."""
        dow_mults = {0: 0.8, 1: 0.9, 2: 1.0, 3: 1.0, 4: 1.1, 5: 1.2, 6: 1.15}
        dampened, conf = apply_confidence_to_dow_multipliers(dow_mults, 250)

        assert conf.confidence == 1.0
        assert conf.tier_name == "full"
        assert dampened[0] == 0.8
        assert dampened[5] == 1.2

    def test_medium_confidence_dampening(self) -> None:
        """Medium confidence should dampen DOW multipliers."""
        dow_mults = {0: 0.8, 1: 0.9, 2: 1.0, 3: 1.0, 4: 1.1, 5: 1.2, 6: 1.15}
        dampened, conf = apply_confidence_to_dow_multipliers(dow_mults, 75)

        assert conf.confidence == 0.6
        assert conf.tier_name == "medium"
        # 0.8 at 0.6 confidence: 1.0 + (0.8 - 1.0) * 0.6 = 0.88
        assert dampened[0] == pytest.approx(0.88)
        # 1.2 at 0.6 confidence: 1.0 + (1.2 - 1.0) * 0.6 = 1.12
        assert dampened[5] == pytest.approx(1.12)

    def test_low_confidence_significant_dampening(self) -> None:
        """Low confidence should significantly dampen DOW multipliers."""
        dow_mults = {0: 0.7, 1: 1.3, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0}
        dampened, conf = apply_confidence_to_dow_multipliers(dow_mults, 30)

        assert conf.confidence == 0.4
        assert conf.tier_name == "low"
        assert conf.is_low_confidence is True
        # Extreme values should be pulled much closer to 1.0
        assert dampened[0] == pytest.approx(0.88)  # 1.0 + (0.7 - 1.0) * 0.4
        assert dampened[1] == pytest.approx(1.12)  # 1.0 + (1.3 - 1.0) * 0.4

    def test_returns_confidence_result(self) -> None:
        """Should return valid ConfidenceResult."""
        dow_mults = {i: 1.0 for i in range(7)}
        dampened, conf = apply_confidence_to_dow_multipliers(dow_mults, 150)

        assert isinstance(conf, ConfidenceResult)
        assert conf.message_count == 150
        assert isinstance(dampened, dict)
        assert len(dampened) == 7


class TestApplyConfidenceToContentMultipliers:
    """Tests for apply_confidence_to_content_multipliers function."""

    def test_full_confidence_no_dampening(self) -> None:
        """Full confidence should not dampen content multipliers."""
        content_mults = {"ppv_unlock": 1.2, "bump_normal": 0.9, "link_drop": 0.7}
        dampened, conf = apply_confidence_to_content_multipliers(content_mults, 300)

        assert conf.confidence == 1.0
        assert dampened["ppv_unlock"] == 1.2
        assert dampened["bump_normal"] == 0.9
        assert dampened["link_drop"] == 0.7

    def test_low_confidence_dampening(self) -> None:
        """Low confidence should dampen content multipliers."""
        content_mults = {"ppv_unlock": 1.2, "bump_normal": 0.9, "link_drop": 0.7}
        dampened, conf = apply_confidence_to_content_multipliers(content_mults, 30)

        assert conf.confidence == 0.4
        assert conf.tier_name == "low"
        # All multipliers should be closer to 1.0
        assert dampened["ppv_unlock"] == pytest.approx(1.08)
        assert dampened["bump_normal"] == pytest.approx(0.96)
        assert dampened["link_drop"] == pytest.approx(0.88)

    def test_very_low_confidence_mostly_neutral(self) -> None:
        """Very low confidence should make multipliers mostly neutral."""
        content_mults = {"high_performer": 1.5, "low_performer": 0.5}
        dampened, conf = apply_confidence_to_content_multipliers(content_mults, 10)

        assert conf.confidence == 0.2
        assert conf.tier_name == "very_low"
        # At 0.2 confidence, multipliers should be 80% toward neutral
        assert dampened["high_performer"] == pytest.approx(1.1)  # 1.0 + (1.5 - 1.0) * 0.2
        assert dampened["low_performer"] == pytest.approx(0.9)  # 1.0 + (0.5 - 1.0) * 0.2

    def test_preserves_keys(self) -> None:
        """Should preserve all original keys in output."""
        content_mults = {
            "ppv_unlock": 1.2,
            "ppv_wall": 1.1,
            "bump_normal": 0.9,
            "bump_descriptive": 0.85,
        }
        dampened, conf = apply_confidence_to_content_multipliers(content_mults, 100)

        assert set(dampened.keys()) == set(content_mults.keys())


class TestConstants:
    """Tests for module constants."""

    def test_confidence_tiers_structure(self) -> None:
        """CONFIDENCE_TIERS should have correct structure."""
        assert len(CONFIDENCE_TIERS) == 5
        for tier in CONFIDENCE_TIERS:
            assert len(tier) == 3
            assert isinstance(tier[0], int)  # min
            assert tier[1] is None or isinstance(tier[1], int)  # max
            assert 0.0 <= tier[2] <= 1.0  # confidence

    def test_confidence_tiers_cover_all_ranges(self) -> None:
        """CONFIDENCE_TIERS should cover all message counts."""
        # First tier starts at 0
        assert CONFIDENCE_TIERS[-1][0] == 0
        # Last tier has no upper bound
        assert CONFIDENCE_TIERS[0][1] is None

    def test_confidence_tiers_ordered_descending(self) -> None:
        """CONFIDENCE_TIERS should be ordered by confidence descending."""
        confidences = [tier[2] for tier in CONFIDENCE_TIERS]
        assert confidences == sorted(confidences, reverse=True)

    def test_neutral_multiplier_is_one(self) -> None:
        """NEUTRAL_MULTIPLIER should be 1.0."""
        assert NEUTRAL_MULTIPLIER == 1.0


class TestDOWIntegration:
    """Integration tests for DOW multiplier dampening scenarios."""

    def test_new_creator_dow_stabilization(self) -> None:
        """New creator with extreme DOW variance should be stabilized."""
        # Scenario: Data suggests huge weekend boost, but only 15 messages
        extreme_dow = {
            0: 0.6,  # Monday very low
            1: 0.7,  # Tuesday low
            2: 0.8,  # Wednesday low-medium
            3: 0.9,  # Thursday medium
            4: 1.0,  # Friday normal
            5: 1.4,  # Saturday very high
            6: 1.3,  # Sunday high
        }
        dampened, conf = apply_confidence_to_dow_multipliers(extreme_dow, 15)

        assert conf.is_low_confidence is True
        # Extreme values should be pulled significantly toward 1.0
        assert dampened[0] > 0.6  # Monday pulled up from 0.6
        assert dampened[5] < 1.4  # Saturday pulled down from 1.4
        # All values should now be within a tighter range
        assert all(0.85 < v < 1.15 for v in dampened.values())

    def test_established_creator_dow_preserved(self) -> None:
        """Established creator with extreme DOW variance should be preserved."""
        # Same extreme DOW but with lots of data
        extreme_dow = {
            0: 0.6,
            1: 0.7,
            2: 0.8,
            3: 0.9,
            4: 1.0,
            5: 1.4,
            6: 1.3,
        }
        dampened, conf = apply_confidence_to_dow_multipliers(extreme_dow, 500)

        assert conf.confidence == 1.0
        # All values should be preserved exactly
        for day, mult in extreme_dow.items():
            assert dampened[day] == mult


class TestContentTypeIntegration:
    """Integration tests for content-type multiplier dampening."""

    def test_rank_multiplier_dampening(self) -> None:
        """Content rank multipliers should be dampened appropriately."""
        # Typical rank multipliers from content_weighting.py
        rank_mults = {
            "TOP": 1.2,
            "MID": 1.0,
            "LOW": 0.8,
            "AVOID": 0.6,
        }

        # Low data creator
        dampened, conf = apply_confidence_to_content_multipliers(rank_mults, 25)

        assert conf.is_low_confidence is True
        # TOP should be pulled toward 1.0
        assert dampened["TOP"] < 1.2
        assert dampened["TOP"] > 1.0
        # AVOID should be pulled toward 1.0
        assert dampened["AVOID"] > 0.6
        assert dampened["AVOID"] < 1.0

    def test_send_type_specific_dampening(self) -> None:
        """Per-send-type multipliers should be dampened."""
        send_type_mults = {
            "ppv_unlock": 1.25,
            "ppv_wall": 1.15,
            "bump_normal": 0.95,
            "link_drop": 0.75,
            "dm_farm": 0.65,
        }

        # Medium confidence
        dampened, conf = apply_confidence_to_content_multipliers(send_type_mults, 75)

        assert conf.confidence == 0.6
        # High performers dampened down
        assert dampened["ppv_unlock"] < 1.25
        # Low performers dampened up
        assert dampened["dm_farm"] > 0.65
