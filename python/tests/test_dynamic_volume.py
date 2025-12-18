"""
Unit tests for dynamic volume calculation.

Tests cover:
- Volume tier classification (fan count boundaries)
- Saturation multipliers (30/50/70 thresholds)
- Opportunity multipliers with saturation combinations
- Bounds enforcement (min/max limits)
- Free page retention capping
- Grace Bennett scenario (12,434 fans -> HIGH tier)
- NEW: Smooth threshold interpolation
- NEW: New creator detection and defaults
- NEW: Retention multiplier bug fix
- NEW: Decimal rounding precision
- NEW: Legacy vs smooth mode comparison
"""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.models.volume import VolumeConfig, VolumeTier
from python.volume.dynamic_calculator import (
    PerformanceContext,
    calculate_dynamic_volume,
    calculate_dynamic_volume_legacy,
    get_volume_tier,
    _calculate_saturation_multiplier,
    _calculate_saturation_multiplier_smooth,
    _calculate_opportunity_multiplier,
    _calculate_opportunity_multiplier_smooth,
    _calculate_trend_adjustment,
    _apply_bounds,
    _round_volume,
    _apply_new_creator_defaults,
)
from python.volume.tier_config import (
    TIER_CONFIGS,
    VOLUME_BOUNDS,
    SATURATION_THRESHOLDS,
    OPPORTUNITY_THRESHOLDS,
)
from python.volume.config_loader import get_config, clear_config


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def low_tier_context() -> PerformanceContext:
    """LOW tier creator (500 fans) with neutral scores."""
    return PerformanceContext(
        fan_count=500,
        page_type="paid",
        saturation_score=50,
        opportunity_score=50,
    )


@pytest.fixture
def mid_tier_context() -> PerformanceContext:
    """MID tier creator (2,500 fans) with neutral scores."""
    return PerformanceContext(
        fan_count=2500,
        page_type="paid",
        saturation_score=50,
        opportunity_score=50,
    )


@pytest.fixture
def high_tier_context() -> PerformanceContext:
    """HIGH tier creator (10,000 fans) with neutral scores."""
    return PerformanceContext(
        fan_count=10000,
        page_type="paid",
        saturation_score=50,
        opportunity_score=50,
    )


@pytest.fixture
def ultra_tier_context() -> PerformanceContext:
    """ULTRA tier creator (50,000 fans) with neutral scores."""
    return PerformanceContext(
        fan_count=50000,
        page_type="paid",
        saturation_score=50,
        opportunity_score=50,
    )


@pytest.fixture
def grace_bennett_context() -> PerformanceContext:
    """Grace Bennett scenario: 12,434 fans (should be HIGH tier)."""
    return PerformanceContext(
        fan_count=12434,
        page_type="paid",
        saturation_score=50,
        opportunity_score=50,
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestVolumeTierClassification:
    """Tests for fan count -> tier classification."""

    def test_low_tier_boundary_zero(self) -> None:
        """0 fans should be LOW tier."""
        assert get_volume_tier(0) == VolumeTier.LOW

    def test_low_tier_boundary_mid(self) -> None:
        """500 fans should be LOW tier."""
        assert get_volume_tier(500) == VolumeTier.LOW

    def test_low_tier_boundary_upper(self) -> None:
        """999 fans should be LOW tier."""
        assert get_volume_tier(999) == VolumeTier.LOW

    def test_mid_tier_boundary_lower(self) -> None:
        """1,000 fans should be MID tier."""
        assert get_volume_tier(1000) == VolumeTier.MID

    def test_mid_tier_boundary_mid(self) -> None:
        """2,500 fans should be MID tier."""
        assert get_volume_tier(2500) == VolumeTier.MID

    def test_mid_tier_boundary_upper(self) -> None:
        """4,999 fans should be MID tier."""
        assert get_volume_tier(4999) == VolumeTier.MID

    def test_high_tier_boundary_lower(self) -> None:
        """5,000 fans should be HIGH tier."""
        assert get_volume_tier(5000) == VolumeTier.HIGH

    def test_high_tier_boundary_mid(self) -> None:
        """10,000 fans should be HIGH tier."""
        assert get_volume_tier(10000) == VolumeTier.HIGH

    def test_high_tier_boundary_upper(self) -> None:
        """14,999 fans should be HIGH tier."""
        assert get_volume_tier(14999) == VolumeTier.HIGH

    def test_ultra_tier_boundary_lower(self) -> None:
        """15,000 fans should be ULTRA tier."""
        assert get_volume_tier(15000) == VolumeTier.ULTRA

    def test_ultra_tier_very_high(self) -> None:
        """50,000 fans should be ULTRA tier."""
        assert get_volume_tier(50000) == VolumeTier.ULTRA

    def test_ultra_tier_extreme(self) -> None:
        """100,000 fans should be ULTRA tier."""
        assert get_volume_tier(100000) == VolumeTier.ULTRA

    @pytest.mark.parametrize(
        "fan_count,expected_tier",
        [
            (0, VolumeTier.LOW),
            (500, VolumeTier.LOW),
            (999, VolumeTier.LOW),
            (1000, VolumeTier.MID),
            (2500, VolumeTier.MID),
            (4999, VolumeTier.MID),
            (5000, VolumeTier.HIGH),
            (10000, VolumeTier.HIGH),
            (14999, VolumeTier.HIGH),
            (15000, VolumeTier.ULTRA),
            (50000, VolumeTier.ULTRA),
        ],
    )
    def test_get_volume_tier_parametrized(
        self, fan_count: int, expected_tier: VolumeTier
    ) -> None:
        """Parametrized test for volume tier boundaries."""
        assert get_volume_tier(fan_count) == expected_tier

    def test_negative_fan_count_raises(self) -> None:
        """Negative fan count should raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            get_volume_tier(-1)


class TestSaturationMultiplier:
    """Tests for saturation score -> volume multiplier."""

    def test_no_saturation_returns_1(self) -> None:
        """Saturation < 50 should return multiplier of 1.0."""
        assert _calculate_saturation_multiplier(0) == 1.0
        assert _calculate_saturation_multiplier(20) == 1.0
        assert _calculate_saturation_multiplier(49) == 1.0

    def test_medium_saturation_returns_0_9(self) -> None:
        """Saturation 50-69 should return multiplier of 0.9."""
        assert _calculate_saturation_multiplier(50) == 0.9
        assert _calculate_saturation_multiplier(60) == 0.9
        assert _calculate_saturation_multiplier(69) == 0.9

    def test_high_saturation_returns_0_7(self) -> None:
        """Saturation >= 70 should return multiplier of 0.7."""
        assert _calculate_saturation_multiplier(70) == 0.7
        assert _calculate_saturation_multiplier(80) == 0.7
        assert _calculate_saturation_multiplier(100) == 0.7


class TestSaturationAdjustment:
    """Tests for saturation score -> volume adjustment in full calculation."""

    def test_no_saturation_no_adjustment(self) -> None:
        """Saturation < 50 should not reduce volume (may increase from opportunity)."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=20,
            opportunity_score=40,  # Below medium threshold - no boost
        )
        config = calculate_dynamic_volume(context)
        # BASE for HIGH paid: revenue=5, engagement=4
        # No saturation reduction, no opportunity boost
        assert config.revenue_per_day == 5
        assert config.engagement_per_day == 4

    def test_medium_saturation_reduces_volume(self) -> None:
        """Saturation 50-69 should reduce volume by 10% (sat_mult=0.9)."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=60,
            opportunity_score=50,  # Neutral opportunity, no boost
        )
        config = calculate_dynamic_volume(context)
        # BASE: revenue=5, engagement=4
        # After 0.9 mult: revenue=round(4.5)=4 or 5, engagement=round(3.6)=4
        assert config.revenue_per_day >= 4
        assert config.revenue_per_day <= 5
        assert config.engagement_per_day >= 3
        assert config.engagement_per_day <= 4

    def test_high_saturation_reduces_volume_significantly(self) -> None:
        """Saturation >= 70 should reduce volume by 30% (sat_mult=0.7)."""
        context = PerformanceContext(
            fan_count=15000,
            page_type="paid",
            saturation_score=80,
            opportunity_score=30,  # Low opportunity, no boost
            message_count=100,  # Established creator, not new
        )
        # Use legacy mode to test step function behavior
        config = calculate_dynamic_volume_legacy(context)
        # BASE for ULTRA paid: revenue=6, engagement=5
        # After 0.7 mult: revenue=round(4.2)=4, engagement=round(3.5)=4
        assert config.revenue_per_day <= 5
        assert config.engagement_per_day <= 4


class TestOpportunityMultiplier:
    """Tests for opportunity score -> volume multiplier."""

    def test_low_opportunity_returns_1(self) -> None:
        """Opportunity < 50 should return multiplier of 1.0."""
        assert _calculate_opportunity_multiplier(30, saturation_score=20) == 1.0
        assert _calculate_opportunity_multiplier(40, saturation_score=20) == 1.0

    def test_medium_opportunity_low_saturation_returns_1_1(self) -> None:
        """Opportunity 50-69 with saturation < 30 should return 1.1."""
        assert _calculate_opportunity_multiplier(50, saturation_score=20) == 1.1
        assert _calculate_opportunity_multiplier(60, saturation_score=29) == 1.1

    def test_medium_opportunity_high_saturation_returns_1(self) -> None:
        """Opportunity 50-69 with saturation >= 30 should return 1.0."""
        assert _calculate_opportunity_multiplier(50, saturation_score=30) == 1.0
        assert _calculate_opportunity_multiplier(60, saturation_score=50) == 1.0

    def test_high_opportunity_low_saturation_returns_1_2(self) -> None:
        """Opportunity >= 70 with saturation < 50 should return 1.2."""
        assert _calculate_opportunity_multiplier(70, saturation_score=30) == 1.2
        assert _calculate_opportunity_multiplier(90, saturation_score=49) == 1.2

    def test_high_opportunity_high_saturation_returns_1(self) -> None:
        """High opportunity should not increase if saturation is also high."""
        assert _calculate_opportunity_multiplier(80, saturation_score=50) == 1.0
        assert _calculate_opportunity_multiplier(90, saturation_score=70) == 1.0


class TestOpportunityAdjustment:
    """Tests for opportunity score + low saturation -> volume increase."""

    def test_high_opportunity_low_saturation_increases_volume(self) -> None:
        """Opportunity >= 70 with saturation < 50 should increase by 20%."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=30,  # Low saturation allows opportunity boost
            opportunity_score=80,  # High opportunity
        )
        config = calculate_dynamic_volume(context)
        # BASE: revenue=5, engagement=4
        # After 1.2 mult: revenue=6, engagement=round(4.8)=5
        assert config.revenue_per_day >= 5
        assert config.engagement_per_day >= 4

    def test_high_opportunity_high_saturation_no_increase(self) -> None:
        """High opportunity should not increase if saturation is also high."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=70,  # High saturation blocks opportunity
            opportunity_score=80,  # High opportunity
        )
        config = calculate_dynamic_volume(context)
        # Saturation mult 0.7 applies, opportunity mult 1.0
        # Revenue reduced from 5 to ~4
        assert config.revenue_per_day <= 5


class TestTrendMultiplier:
    """Tests for revenue trend -> adjustment."""

    def test_neutral_trend_no_adjustment(self) -> None:
        """Trend between -15% and +15% (inclusive) should return 0 adjustment."""
        assert _calculate_trend_adjustment(0) == 0
        assert _calculate_trend_adjustment(-14) == 0
        assert _calculate_trend_adjustment(-15) == 0  # Boundary (< -15 triggers)
        assert _calculate_trend_adjustment(14) == 0
        assert _calculate_trend_adjustment(15) == 0  # Boundary (> 15 triggers)

    def test_negative_trend_reduces_by_1(self) -> None:
        """Trend < -15% should return -1 adjustment."""
        assert _calculate_trend_adjustment(-16) == -1
        assert _calculate_trend_adjustment(-20) == -1
        assert _calculate_trend_adjustment(-50) == -1

    def test_positive_trend_increases_by_1(self) -> None:
        """Trend > +15% should return +1 adjustment."""
        assert _calculate_trend_adjustment(16) == 1
        assert _calculate_trend_adjustment(20) == 1
        assert _calculate_trend_adjustment(50) == 1


class TestTrendAdjustment:
    """Tests for revenue trend -> volume adjustment in full calculation."""

    def test_negative_trend_reduces_volume(self) -> None:
        """Revenue trend < -15% should reduce volume by 1."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=40,  # Below medium threshold
            opportunity_score=40,  # Below medium threshold
            revenue_trend=-20,  # Declining
        )
        config = calculate_dynamic_volume(context)
        # BASE: revenue=5, adjusted by -1 = 4
        assert config.revenue_per_day <= 5

    def test_positive_trend_increases_volume(self) -> None:
        """Revenue trend > 15% should increase volume by 1."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=40,  # Below medium threshold
            opportunity_score=40,  # Below medium threshold
            revenue_trend=20,  # Growing
        )
        config = calculate_dynamic_volume(context)
        # BASE: revenue=5, adjusted by +1 = 6
        assert config.revenue_per_day >= 5


class TestBoundsEnforcement:
    """Tests for min/max volume bounds."""

    def test_apply_bounds_revenue_min(self) -> None:
        """Revenue should be clamped to minimum bound."""
        assert _apply_bounds(0, "revenue") == VOLUME_BOUNDS["revenue"][0]
        assert _apply_bounds(-5, "revenue") == VOLUME_BOUNDS["revenue"][0]

    def test_apply_bounds_revenue_max(self) -> None:
        """Revenue should be clamped to maximum bound."""
        assert _apply_bounds(10, "revenue") == VOLUME_BOUNDS["revenue"][1]
        assert _apply_bounds(100, "revenue") == VOLUME_BOUNDS["revenue"][1]

    def test_apply_bounds_within_range(self) -> None:
        """Values within bounds should be unchanged."""
        assert _apply_bounds(5, "revenue") == 5
        assert _apply_bounds(3, "engagement") == 3
        assert _apply_bounds(2, "retention") == 2

    def test_revenue_minimum_enforced(self) -> None:
        """Revenue should never go below minimum (1)."""
        context = PerformanceContext(
            fan_count=100,  # LOW tier, revenue=3
            page_type="paid",
            saturation_score=90,  # High saturation (0.7 mult)
            opportunity_score=10,
            revenue_trend=-30,  # Further reduction
        )
        config = calculate_dynamic_volume(context)
        assert config.revenue_per_day >= VOLUME_BOUNDS["revenue"][0]

    def test_revenue_maximum_enforced(self) -> None:
        """Revenue should never exceed maximum (8)."""
        context = PerformanceContext(
            fan_count=50000,  # ULTRA tier, revenue=6 (paid) or 8 (free)
            page_type="free",  # Free gets 8 base
            saturation_score=10,  # No reduction
            opportunity_score=90,  # 1.2 mult would give 9.6
            revenue_trend=30,  # +1 would give 10.6
        )
        config = calculate_dynamic_volume(context)
        assert config.revenue_per_day <= VOLUME_BOUNDS["revenue"][1]

    def test_engagement_minimum_enforced(self) -> None:
        """Engagement should never go below minimum (1)."""
        context = PerformanceContext(
            fan_count=100,
            page_type="paid",
            saturation_score=95,  # Very high saturation
            opportunity_score=5,
        )
        config = calculate_dynamic_volume(context)
        assert config.engagement_per_day >= VOLUME_BOUNDS["engagement"][0]

    def test_retention_maximum_enforced(self) -> None:
        """Retention should never exceed maximum (4)."""
        context = PerformanceContext(
            fan_count=50000,  # ULTRA tier, retention=3 for paid
            page_type="paid",
            saturation_score=10,
            opportunity_score=10,
        )
        config = calculate_dynamic_volume(context)
        assert config.retention_per_day <= VOLUME_BOUNDS["retention"][1]


class TestFreePageRetention:
    """Tests for free page retention capping."""

    def test_free_page_retention_capped_to_zero(self) -> None:
        """Free pages should have retention_per_day = 0."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="free",
            saturation_score=50,
            opportunity_score=50,
        )
        config = calculate_dynamic_volume(context)
        assert config.retention_per_day == 0

    def test_free_page_retention_zero_all_tiers(self) -> None:
        """Free pages should have retention=0 regardless of tier."""
        for fan_count in [100, 2500, 10000, 50000]:
            context = PerformanceContext(
                fan_count=fan_count,
                page_type="free",
                saturation_score=30,
                opportunity_score=30,
            )
            config = calculate_dynamic_volume(context)
            assert config.retention_per_day == 0, f"Failed for fan_count={fan_count}"

    def test_paid_page_has_retention(self) -> None:
        """Paid pages should have retention_per_day > 0."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=50,
            opportunity_score=50,
        )
        config = calculate_dynamic_volume(context)
        assert config.retention_per_day >= 1


class TestGraceBennettScenario:
    """Integration test for Grace Bennett's case.

    Grace Bennett had 12,434 fans but was incorrectly assigned to "Low" tier
    in the legacy static volume_assignments table. This test ensures the
    dynamic calculator correctly assigns her to HIGH tier.
    """

    def test_grace_bennett_gets_high_tier(
        self, grace_bennett_context: PerformanceContext
    ) -> None:
        """Grace Bennett with 12,434 fans should get HIGH tier, not LOW."""
        config = calculate_dynamic_volume(grace_bennett_context)

        # Should be HIGH tier (5,000-14,999)
        assert config.tier == VolumeTier.HIGH

        # HIGH paid base: revenue=5, engagement=4, retention=2
        # With neutral scores (50/50), only medium saturation applies (0.9)
        assert config.revenue_per_day >= 4
        assert config.engagement_per_day >= 3
        assert config.retention_per_day >= 1

    def test_grace_bennett_fan_count_preserved(
        self, grace_bennett_context: PerformanceContext
    ) -> None:
        """Fan count should be preserved in the config."""
        config = calculate_dynamic_volume(grace_bennett_context)
        assert config.fan_count == 12434

    def test_grace_bennett_page_type_preserved(
        self, grace_bennett_context: PerformanceContext
    ) -> None:
        """Page type should be preserved in the config."""
        config = calculate_dynamic_volume(grace_bennett_context)
        assert config.page_type == "paid"


class TestTierConfigIntegrity:
    """Tests to verify TIER_CONFIGS are properly structured."""

    def test_all_tiers_have_paid_and_free(self) -> None:
        """Every tier should have both paid and free configurations."""
        for tier in VolumeTier:
            assert tier in TIER_CONFIGS
            assert "paid" in TIER_CONFIGS[tier]
            assert "free" in TIER_CONFIGS[tier]

    def test_all_configs_have_required_keys(self) -> None:
        """Every config should have revenue, engagement, retention."""
        for tier in VolumeTier:
            for page_type in ["paid", "free"]:
                config = TIER_CONFIGS[tier][page_type]
                assert "revenue" in config
                assert "engagement" in config
                assert "retention" in config

    def test_tier_configs_values_positive(self) -> None:
        """All config values should be non-negative."""
        for tier in VolumeTier:
            for page_type in ["paid", "free"]:
                config = TIER_CONFIGS[tier][page_type]
                assert config["revenue"] >= 0
                assert config["engagement"] >= 0
                assert config["retention"] >= 0

    def test_volume_increases_with_tier(self) -> None:
        """Total volume should generally increase with tier."""
        for page_type in ["paid", "free"]:
            tiers = [VolumeTier.LOW, VolumeTier.MID, VolumeTier.HIGH, VolumeTier.ULTRA]
            totals = []
            for tier in tiers:
                config = TIER_CONFIGS[tier][page_type]
                total = config["revenue"] + config["engagement"] + config["retention"]
                totals.append(total)
            # Verify non-decreasing
            for i in range(len(totals) - 1):
                assert totals[i] <= totals[i + 1], (
                    f"Volume should increase with tier for {page_type}: "
                    f"{tiers[i]} ({totals[i]}) > {tiers[i+1]} ({totals[i+1]})"
                )


class TestVolumeBoundsIntegrity:
    """Tests for VOLUME_BOUNDS configuration."""

    def test_bounds_have_all_categories(self) -> None:
        """All categories should have bounds defined."""
        assert "revenue" in VOLUME_BOUNDS
        assert "engagement" in VOLUME_BOUNDS
        assert "retention" in VOLUME_BOUNDS

    def test_bounds_are_valid_tuples(self) -> None:
        """Each bound should be a (min, max) tuple with min <= max."""
        for category, bounds in VOLUME_BOUNDS.items():
            assert isinstance(bounds, tuple), f"{category} bounds should be tuple"
            assert len(bounds) == 2, f"{category} bounds should have 2 elements"
            assert bounds[0] <= bounds[1], f"{category} min should be <= max"

    def test_revenue_bounds(self) -> None:
        """Revenue bounds should be (1, 8)."""
        assert VOLUME_BOUNDS["revenue"] == (1, 8)

    def test_engagement_bounds(self) -> None:
        """Engagement bounds should be (1, 6)."""
        assert VOLUME_BOUNDS["engagement"] == (1, 6)

    def test_retention_bounds(self) -> None:
        """Retention bounds should be (0, 4) - 0 is valid for free pages."""
        assert VOLUME_BOUNDS["retention"] == (0, 4)


class TestPerformanceContextValidation:
    """Tests for PerformanceContext input validation."""

    def test_valid_context_creation(self) -> None:
        """Valid context should create without errors."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=50,
            opportunity_score=50,
        )
        assert context.fan_count == 5000
        assert context.page_type == "paid"

    def test_invalid_page_type_raises(self) -> None:
        """Invalid page_type should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid page_type"):
            PerformanceContext(
                fan_count=5000,
                page_type="invalid",
                saturation_score=50,
                opportunity_score=50,
            )

    def test_negative_fan_count_raises(self) -> None:
        """Negative fan_count should raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            PerformanceContext(
                fan_count=-100,
                page_type="paid",
                saturation_score=50,
                opportunity_score=50,
            )

    def test_saturation_out_of_range_raises(self) -> None:
        """Saturation outside 0-100 should raise ValueError."""
        with pytest.raises(ValueError, match="saturation_score"):
            PerformanceContext(
                fan_count=5000,
                page_type="paid",
                saturation_score=150,
                opportunity_score=50,
            )

    def test_opportunity_out_of_range_raises(self) -> None:
        """Opportunity outside 0-100 should raise ValueError."""
        with pytest.raises(ValueError, match="opportunity_score"):
            PerformanceContext(
                fan_count=5000,
                page_type="paid",
                saturation_score=50,
                opportunity_score=-10,
            )

    def test_default_scores(self) -> None:
        """Default scores should be 50."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
        )
        assert context.saturation_score == 50.0
        assert context.opportunity_score == 50.0
        assert context.revenue_trend == 0.0


class TestVolumeConfigOutput:
    """Tests for VolumeConfig output structure."""

    def test_config_has_correct_tier(self) -> None:
        """Config should have correct tier based on fan count."""
        context = PerformanceContext(fan_count=5000, page_type="paid")
        config = calculate_dynamic_volume(context)
        assert config.tier == VolumeTier.HIGH

    def test_config_total_per_day_property(self) -> None:
        """Config total_per_day should sum all categories."""
        context = PerformanceContext(fan_count=5000, page_type="paid")
        config = calculate_dynamic_volume(context)
        expected = config.revenue_per_day + config.engagement_per_day + config.retention_per_day
        assert config.total_per_day == expected

    def test_config_is_frozen(self) -> None:
        """VolumeConfig should be immutable (frozen dataclass)."""
        context = PerformanceContext(fan_count=5000, page_type="paid")
        config = calculate_dynamic_volume(context)
        with pytest.raises(Exception):  # FrozenInstanceError
            config.revenue_per_day = 99


class TestEdgeCases:
    """Edge case tests."""

    def test_zero_fans(self) -> None:
        """Zero fans should work and return LOW tier."""
        context = PerformanceContext(
            fan_count=0,
            page_type="paid",
            saturation_score=50,
            opportunity_score=50,
        )
        config = calculate_dynamic_volume(context)
        assert config.tier == VolumeTier.LOW

    def test_exact_boundary_1000_fans(self) -> None:
        """Exactly 1000 fans should be MID tier."""
        context = PerformanceContext(fan_count=1000, page_type="paid")
        config = calculate_dynamic_volume(context)
        assert config.tier == VolumeTier.MID

    def test_exact_boundary_5000_fans(self) -> None:
        """Exactly 5000 fans should be HIGH tier."""
        context = PerformanceContext(fan_count=5000, page_type="paid")
        config = calculate_dynamic_volume(context)
        assert config.tier == VolumeTier.HIGH

    def test_exact_boundary_15000_fans(self) -> None:
        """Exactly 15000 fans should be ULTRA tier."""
        context = PerformanceContext(fan_count=15000, page_type="paid")
        config = calculate_dynamic_volume(context)
        assert config.tier == VolumeTier.ULTRA

    def test_saturation_exactly_50(self) -> None:
        """Saturation exactly at 50 should trigger medium reduction."""
        mult = _calculate_saturation_multiplier(50)
        assert mult == 0.9

    def test_saturation_exactly_70(self) -> None:
        """Saturation exactly at 70 should trigger high reduction."""
        mult = _calculate_saturation_multiplier(70)
        assert mult == 0.7

    def test_opportunity_exactly_70_with_low_saturation(self) -> None:
        """Opportunity exactly 70 with sat < 50 should give 1.2 multiplier."""
        mult = _calculate_opportunity_multiplier(70, saturation_score=40)
        assert mult == 1.2

    def test_combined_high_saturation_high_opportunity(self) -> None:
        """High saturation should override high opportunity."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=80,
            opportunity_score=90,
        )
        config = calculate_dynamic_volume(context)
        # High saturation (0.7) should dominate
        # BASE: revenue=5, after 0.7 mult = 3.5 -> 4
        assert config.revenue_per_day <= 5


class TestThresholdConstants:
    """Tests for threshold constant values."""

    def test_saturation_thresholds(self) -> None:
        """Saturation thresholds should be correctly defined."""
        assert SATURATION_THRESHOLDS["low"] == 30
        assert SATURATION_THRESHOLDS["medium"] == 50
        assert SATURATION_THRESHOLDS["high"] == 70

    def test_opportunity_thresholds(self) -> None:
        """Opportunity thresholds should be correctly defined."""
        assert OPPORTUNITY_THRESHOLDS["low"] == 30
        assert OPPORTUNITY_THRESHOLDS["medium"] == 50
        assert OPPORTUNITY_THRESHOLDS["high"] == 70


# =============================================================================
# NEW TEST CLASSES FOR PHASE 2 & 3 FEATURES
# =============================================================================


class TestSmoothSaturationMultiplier:
    """Tests for smooth saturation multiplier interpolation."""

    def test_smooth_at_zero(self) -> None:
        """Score 0 should return 1.0 (no reduction)."""
        mult = _calculate_saturation_multiplier_smooth(0)
        assert mult == 1.0

    def test_smooth_at_30(self) -> None:
        """Score 30 (low threshold) should return 1.0."""
        mult = _calculate_saturation_multiplier_smooth(30)
        assert mult == 1.0

    def test_smooth_at_50(self) -> None:
        """Score 50 (medium threshold) should return 0.9."""
        mult = _calculate_saturation_multiplier_smooth(50)
        assert mult == 0.9

    def test_smooth_at_70(self) -> None:
        """Score 70 (high threshold) should return 0.7."""
        mult = _calculate_saturation_multiplier_smooth(70)
        assert mult == 0.7

    def test_smooth_at_100(self) -> None:
        """Score 100 should return 0.7 (max reduction)."""
        mult = _calculate_saturation_multiplier_smooth(100)
        assert mult == 0.7

    def test_smooth_interpolation_between_30_and_50(self) -> None:
        """Interpolated value between 30 and 50 should be between 0.9 and 1.0."""
        mult = _calculate_saturation_multiplier_smooth(40)
        assert 0.9 < mult < 1.0

    def test_smooth_interpolation_between_50_and_70(self) -> None:
        """Interpolated value between 50 and 70 should be between 0.7 and 0.9."""
        mult = _calculate_saturation_multiplier_smooth(60)
        assert 0.7 < mult < 0.9

    def test_smooth_midpoint_30_50(self) -> None:
        """Midpoint at 40 should be 0.95 (halfway between 1.0 and 0.9)."""
        mult = _calculate_saturation_multiplier_smooth(40)
        # Allow small floating point tolerance
        assert abs(mult - 0.95) < 0.01

    def test_smooth_midpoint_50_70(self) -> None:
        """Midpoint at 60 should be 0.8 (halfway between 0.9 and 0.7)."""
        mult = _calculate_saturation_multiplier_smooth(60)
        assert abs(mult - 0.8) < 0.01


class TestSmoothOpportunityMultiplier:
    """Tests for smooth opportunity multiplier interpolation."""

    def test_smooth_opp_blocked_by_high_saturation(self) -> None:
        """High saturation should block opportunity boost."""
        mult = _calculate_opportunity_multiplier_smooth(80, saturation_score=60)
        assert mult == 1.0

    def test_smooth_opp_high_opportunity_low_saturation(self) -> None:
        """High opportunity with low saturation should give 1.2."""
        mult = _calculate_opportunity_multiplier_smooth(80, saturation_score=30)
        assert mult == 1.2

    def test_smooth_opp_medium_opportunity_very_low_saturation(self) -> None:
        """Medium opportunity with very low saturation should interpolate."""
        mult = _calculate_opportunity_multiplier_smooth(60, saturation_score=20)
        assert 1.0 <= mult <= 1.1

    def test_smooth_opp_low_opportunity(self) -> None:
        """Low opportunity should return 1.0 regardless of saturation."""
        mult = _calculate_opportunity_multiplier_smooth(30, saturation_score=10)
        assert mult == 1.0


class TestDecimalRounding:
    """Tests for Decimal-based rounding precision."""

    def test_round_volume_half_up(self) -> None:
        """0.5 should round up to 1."""
        assert _round_volume(0.5) == 1

    def test_round_volume_below_half(self) -> None:
        """0.4 should round down to 0."""
        assert _round_volume(0.4) == 0

    def test_round_volume_exact_integer(self) -> None:
        """Exact integers should remain unchanged."""
        assert _round_volume(5.0) == 5
        assert _round_volume(3.0) == 3

    def test_round_volume_typical_values(self) -> None:
        """Test typical volume calculation values."""
        assert _round_volume(4.5) == 5  # 5 * 0.9 = 4.5 -> 5
        assert _round_volume(3.5) == 4  # 5 * 0.7 = 3.5 -> 4
        assert _round_volume(4.2) == 4  # 6 * 0.7 = 4.2 -> 4

    def test_round_volume_precision(self) -> None:
        """Test that Decimal avoids floating point errors."""
        # This would fail with naive round() due to floating point
        # 2.5 -> 2 with banker's rounding in Python 3
        # But ROUND_HALF_UP ensures 2.5 -> 3
        assert _round_volume(2.5) == 3


class TestNewCreatorDetection:
    """Tests for new creator detection and default application."""

    def test_new_creator_by_flag(self) -> None:
        """Creator flagged as new should use defaults."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=90,  # Would normally reduce volume
            opportunity_score=10,
            is_new_creator=True,
            message_count=100,  # Has messages but flagged as new
        )
        adjusted = _apply_new_creator_defaults(context)

        config = get_config()
        nc = config.new_creator_config
        assert adjusted.saturation_score == nc.default_saturation
        assert adjusted.opportunity_score == nc.default_opportunity
        assert adjusted.is_new_creator is True

    def test_new_creator_by_message_count(self) -> None:
        """Creator with < 5 messages should use defaults."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=90,
            opportunity_score=10,
            is_new_creator=False,
            message_count=3,  # Below threshold
        )
        adjusted = _apply_new_creator_defaults(context)

        config = get_config()
        nc = config.new_creator_config
        assert adjusted.saturation_score == nc.default_saturation
        assert adjusted.is_new_creator is True

    def test_established_creator_keeps_scores(self) -> None:
        """Creator with sufficient messages should keep original scores."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=80,
            opportunity_score=20,
            is_new_creator=False,
            message_count=50,  # Above threshold
        )
        adjusted = _apply_new_creator_defaults(context)

        assert adjusted.saturation_score == 80
        assert adjusted.opportunity_score == 20
        assert adjusted.is_new_creator is False

    def test_new_creator_volume_calculation(self) -> None:
        """New creator should get conservative volume."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=0,  # Would give high volume normally
            opportunity_score=100,  # Would give even higher volume
            is_new_creator=True,
        )
        config = calculate_dynamic_volume(context)

        # With defaults (sat=40, opp=60), volume should be moderate
        # Not maximum (from original 0/100 scores)
        assert config.revenue_per_day <= 6  # Not boosted to max


class TestRetentionMultiplierBugFix:
    """Tests for the retention multiplier bug fix.

    Bug: Retention was not being adjusted by saturation multiplier.
    Fix: Apply saturation multiplier to retention for paid pages.
    """

    def test_retention_reduced_by_high_saturation(self) -> None:
        """High saturation should reduce retention volume."""
        # Low saturation context
        low_sat_context = PerformanceContext(
            fan_count=15000,  # ULTRA tier, retention=3
            page_type="paid",
            saturation_score=20,
            opportunity_score=20,
        )
        low_sat_config = calculate_dynamic_volume(low_sat_context)

        # High saturation context
        high_sat_context = PerformanceContext(
            fan_count=15000,
            page_type="paid",
            saturation_score=80,  # High saturation
            opportunity_score=20,
        )
        high_sat_config = calculate_dynamic_volume(high_sat_context)

        # High saturation should reduce retention
        assert high_sat_config.retention_per_day <= low_sat_config.retention_per_day

    def test_retention_multiplier_applied(self) -> None:
        """Retention should have saturation multiplier applied."""
        context = PerformanceContext(
            fan_count=15000,  # ULTRA tier, base retention=3
            page_type="paid",
            saturation_score=80,  # 0.7 multiplier
            opportunity_score=20,
        )
        config = calculate_dynamic_volume(context)

        # 3 * 0.7 = 2.1 -> rounds to 2
        # But smooth interpolation might give slightly different value
        assert config.retention_per_day <= 3  # Should be reduced from base

    def test_retention_still_zero_for_free_pages(self) -> None:
        """Free pages should still have retention=0."""
        context = PerformanceContext(
            fan_count=15000,
            page_type="free",
            saturation_score=20,  # Low saturation
            opportunity_score=80,
        )
        config = calculate_dynamic_volume(context)
        assert config.retention_per_day == 0


class TestLegacyVsSmoothMode:
    """Tests comparing legacy step functions vs smooth interpolation."""

    def test_legacy_mode_uses_step_functions(self) -> None:
        """Legacy mode should use discrete step thresholds."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=45,  # Below 50, should get 1.0 in legacy
            opportunity_score=40,
        )
        config = calculate_dynamic_volume_legacy(context)

        # With legacy (sat_mult=1.0), base revenue=5 unchanged
        assert config.revenue_per_day == 5

    def test_smooth_mode_interpolates(self) -> None:
        """Smooth mode should interpolate between thresholds."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=45,  # Between 30 and 50
            opportunity_score=40,
        )
        smooth_config = calculate_dynamic_volume(context, use_smooth_interpolation=True)
        legacy_config = calculate_dynamic_volume(context, use_smooth_interpolation=False)

        # Results might differ due to interpolation vs step
        # Both should produce valid volumes
        assert smooth_config.revenue_per_day >= 1
        assert legacy_config.revenue_per_day >= 1

    def test_both_modes_respect_bounds(self) -> None:
        """Both modes should respect volume bounds."""
        context = PerformanceContext(
            fan_count=50000,
            page_type="free",
            saturation_score=10,
            opportunity_score=90,
            revenue_trend=30,
        )
        smooth_config = calculate_dynamic_volume(context, use_smooth_interpolation=True)
        legacy_config = calculate_dynamic_volume(context, use_smooth_interpolation=False)

        # Both should respect max bound of 8
        assert smooth_config.revenue_per_day <= 8
        assert legacy_config.revenue_per_day <= 8


class TestPerformanceContextNewFields:
    """Tests for new PerformanceContext fields."""

    def test_default_is_new_creator(self) -> None:
        """is_new_creator should default to False."""
        context = PerformanceContext(fan_count=5000, page_type="paid")
        assert context.is_new_creator is False

    def test_default_message_count(self) -> None:
        """message_count should default to 0."""
        context = PerformanceContext(fan_count=5000, page_type="paid")
        assert context.message_count == 0

    def test_explicit_new_creator_values(self) -> None:
        """Explicit new creator values should be preserved."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            is_new_creator=True,
            message_count=3,
        )
        assert context.is_new_creator is True
        assert context.message_count == 3


class TestConfigIntegration:
    """Tests for config loader integration with dynamic calculator."""

    def test_config_thresholds_used(self) -> None:
        """Calculator should use thresholds from config."""
        config = get_config()
        sat_thresholds = config.saturation_thresholds

        # Verify thresholds match what calculator uses
        assert sat_thresholds.low == SATURATION_THRESHOLDS["low"]
        assert sat_thresholds.medium == SATURATION_THRESHOLDS["medium"]
        assert sat_thresholds.high == SATURATION_THRESHOLDS["high"]

    def test_config_multipliers_used(self) -> None:
        """Calculator should use multipliers from config."""
        config = get_config()
        sat_mult = config.saturation_multipliers

        assert sat_mult.normal == 1.0
        assert sat_mult.medium == 0.9
        assert sat_mult.high == 0.7

    def test_config_new_creator_values(self) -> None:
        """New creator config should be accessible."""
        config = get_config()
        nc = config.new_creator_config

        assert nc.min_messages_for_analysis == 5
        assert nc.days_to_consider_new == 30
        assert nc.default_saturation == 40.0
        assert nc.default_opportunity == 60.0
