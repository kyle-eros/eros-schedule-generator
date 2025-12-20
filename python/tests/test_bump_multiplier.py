"""
Unit tests for bump_multiplier module.

Tests the bump multiplier calculation system that scales engagement volume
based on creator content category and volume tier. Covers:
- calculate_bump_multiplier(): Tier-based multiplier calculation with capping
- calculate_followup_volume(): PPV followup scaling with confidence adjustment
- apply_bump_to_engagement(): Multiplier application with max clamping
- get_bump_multiplier_for_category(): Raw multiplier lookup
- calculate_effective_engagement(): Convenience function combining all steps
"""

import pytest

from python.models.volume import VolumeTier
from python.volume.bump_multiplier import (
    BUMP_MULTIPLIERS,
    DEFAULT_CONTENT_CATEGORY,
    FOLLOWUP_BASE_RATE,
    FREE_PAGE_BUMP_BONUS,
    HIGH_TIER_MULTIPLIER_CAP,
    MAX_FOLLOWUPS_PER_DAY,
    BumpMultiplierResult,
    FollowupVolumeResult,
    apply_bump_to_engagement,
    calculate_bump_multiplier,
    calculate_effective_engagement,
    calculate_followup_volume,
    get_all_content_categories,
    get_bump_multiplier_for_category,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def all_tiers() -> list[VolumeTier]:
    """All volume tiers for parametrized tests."""
    return [VolumeTier.LOW, VolumeTier.MID, VolumeTier.HIGH, VolumeTier.ULTRA]


@pytest.fixture
def non_low_tiers() -> list[VolumeTier]:
    """Non-LOW tiers that trigger capping behavior."""
    return [VolumeTier.MID, VolumeTier.HIGH, VolumeTier.ULTRA]


@pytest.fixture
def all_categories() -> list[str]:
    """All valid content categories."""
    return list(BUMP_MULTIPLIERS.keys())


# =============================================================================
# Tests: Constants Verification
# =============================================================================


class TestConstants:
    """Verify module constants are correctly defined."""

    def test_bump_multipliers_structure(self) -> None:
        """BUMP_MULTIPLIERS contains expected categories with correct values."""
        assert BUMP_MULTIPLIERS == {
            "lifestyle": 1.0,
            "softcore": 1.5,
            "amateur": 2.0,
            "explicit": 2.67,
        }

    def test_default_content_category_is_softcore(self) -> None:
        """Default content category is softcore."""
        assert DEFAULT_CONTENT_CATEGORY == "softcore"

    def test_followup_base_rate_is_80_percent(self) -> None:
        """Followup base rate is 80%."""
        assert FOLLOWUP_BASE_RATE == 0.80

    def test_max_followups_per_day_is_5(self) -> None:
        """Maximum followups per day is 5."""
        assert MAX_FOLLOWUPS_PER_DAY == 5

    def test_high_tier_multiplier_cap_is_1_5(self) -> None:
        """High tier multiplier cap is 1.5x."""
        assert HIGH_TIER_MULTIPLIER_CAP == 1.5

    def test_free_page_bump_bonus_is_0_1(self) -> None:
        """Free page bump bonus is 0.1."""
        assert FREE_PAGE_BUMP_BONUS == 0.1


# =============================================================================
# Tests: calculate_bump_multiplier
# =============================================================================


class TestCalculateBumpMultiplier:
    """Tests for calculate_bump_multiplier function."""

    def test_bump_multiplier_explicit_low_tier(self) -> None:
        """Explicit content at LOW tier gets full 2.67x multiplier."""
        result = calculate_bump_multiplier("explicit", VolumeTier.LOW, "paid")
        assert result.multiplier == 2.67
        assert result.capped is False
        assert result.content_category == "explicit"
        assert result.tier == VolumeTier.LOW

    def test_bump_multiplier_explicit_high_tier(self) -> None:
        """Explicit content at HIGH tier is capped at 1.5x."""
        result = calculate_bump_multiplier("explicit", VolumeTier.HIGH, "paid")
        assert result.multiplier == 1.5
        assert result.capped is True
        assert result.original_multiplier == 2.67

    def test_bump_multiplier_lifestyle_any_tier(self) -> None:
        """Lifestyle content always gets 1.0x (no capping needed)."""
        result = calculate_bump_multiplier("lifestyle", VolumeTier.ULTRA, "paid")
        assert result.multiplier == 1.0
        assert result.capped is False

    def test_bump_multiplier_free_page_boost(self) -> None:
        """Free pages get slight boost (FREE_PAGE_BUMP_BONUS)."""
        result_paid = calculate_bump_multiplier("softcore", VolumeTier.LOW, "paid")
        result_free = calculate_bump_multiplier("softcore", VolumeTier.LOW, "free")
        assert result_free.multiplier > result_paid.multiplier
        assert result_free.multiplier == result_paid.multiplier + FREE_PAGE_BUMP_BONUS

    def test_bump_multiplier_unknown_category_defaults(self) -> None:
        """Unknown category defaults to softcore."""
        result = calculate_bump_multiplier("unknown", VolumeTier.LOW, "paid")
        assert result.multiplier == 1.5  # softcore default
        assert result.source == "default"
        assert result.content_category == "softcore"

    def test_bump_multiplier_empty_category_defaults(self) -> None:
        """Empty string category defaults to softcore."""
        result = calculate_bump_multiplier("", VolumeTier.LOW, "paid")
        assert result.multiplier == 1.5
        assert result.source == "default"

    def test_bump_multiplier_none_category_defaults(self) -> None:
        """None category defaults to softcore."""
        result = calculate_bump_multiplier(None, VolumeTier.LOW, "paid")  # type: ignore[arg-type]
        assert result.multiplier == 1.5
        assert result.source == "default"

    @pytest.mark.parametrize("category,expected_multiplier", [
        ("lifestyle", 1.0),
        ("softcore", 1.5),
        ("amateur", 2.0),
        ("explicit", 2.67),
    ])
    def test_bump_multiplier_all_categories_low_tier(
        self, category: str, expected_multiplier: float
    ) -> None:
        """Each category gets correct multiplier at LOW tier."""
        result = calculate_bump_multiplier(category, VolumeTier.LOW, "paid")
        assert result.multiplier == expected_multiplier
        assert result.capped is False

    @pytest.mark.parametrize("tier", [VolumeTier.MID, VolumeTier.HIGH, VolumeTier.ULTRA])
    def test_bump_multiplier_explicit_capped_at_non_low_tiers(
        self, tier: VolumeTier
    ) -> None:
        """Explicit content is capped at 1.5x for all non-LOW tiers."""
        result = calculate_bump_multiplier("explicit", tier, "paid")
        assert result.multiplier == HIGH_TIER_MULTIPLIER_CAP
        assert result.capped is True

    @pytest.mark.parametrize("tier", [VolumeTier.MID, VolumeTier.HIGH, VolumeTier.ULTRA])
    def test_bump_multiplier_amateur_capped_at_non_low_tiers(
        self, tier: VolumeTier
    ) -> None:
        """Amateur content (2.0x) is capped at 1.5x for non-LOW tiers."""
        result = calculate_bump_multiplier("amateur", tier, "paid")
        assert result.multiplier == HIGH_TIER_MULTIPLIER_CAP
        assert result.capped is True
        assert result.original_multiplier == 2.0

    @pytest.mark.parametrize("tier", [VolumeTier.MID, VolumeTier.HIGH, VolumeTier.ULTRA])
    def test_bump_multiplier_lifestyle_not_capped(self, tier: VolumeTier) -> None:
        """Lifestyle content (1.0x) is never capped as it's below cap."""
        result = calculate_bump_multiplier("lifestyle", tier, "paid")
        assert result.multiplier == 1.0
        assert result.capped is False

    @pytest.mark.parametrize("tier", [VolumeTier.MID, VolumeTier.HIGH, VolumeTier.ULTRA])
    def test_bump_multiplier_softcore_not_capped(self, tier: VolumeTier) -> None:
        """Softcore content (1.5x) equals cap so technically not capped."""
        result = calculate_bump_multiplier("softcore", tier, "paid")
        # 1.5 == HIGH_TIER_MULTIPLIER_CAP, but > check means not capped
        assert result.multiplier == 1.5
        assert result.capped is False

    def test_bump_multiplier_case_insensitive(self) -> None:
        """Content category matching is case-insensitive."""
        result_upper = calculate_bump_multiplier("EXPLICIT", VolumeTier.LOW, "paid")
        result_lower = calculate_bump_multiplier("explicit", VolumeTier.LOW, "paid")
        result_mixed = calculate_bump_multiplier("ExPlIcIt", VolumeTier.LOW, "paid")
        assert result_upper.multiplier == result_lower.multiplier == result_mixed.multiplier

    def test_bump_multiplier_strips_whitespace(self) -> None:
        """Content category matching strips whitespace."""
        result = calculate_bump_multiplier("  explicit  ", VolumeTier.LOW, "paid")
        assert result.multiplier == 2.67
        assert result.content_category == "explicit"

    def test_bump_multiplier_source_database_for_valid_category(self) -> None:
        """Valid categories have 'database' source."""
        result = calculate_bump_multiplier("amateur", VolumeTier.LOW, "paid")
        assert result.source == "database"

    def test_bump_multiplier_source_page_type_fallback_for_free(self) -> None:
        """Free pages with valid category get 'page_type_fallback' source."""
        result = calculate_bump_multiplier("amateur", VolumeTier.LOW, "free")
        assert result.source == "page_type_fallback"

    def test_bump_multiplier_free_page_with_high_multiplier_still_capped(self) -> None:
        """Free page boost doesn't bypass tier capping."""
        result = calculate_bump_multiplier("explicit", VolumeTier.HIGH, "free")
        # Would be 2.67 + 0.1 = 2.77, but capped at 1.5
        assert result.multiplier == HIGH_TIER_MULTIPLIER_CAP
        assert result.capped is True


class TestBumpMultiplierResultDataclass:
    """Tests for BumpMultiplierResult dataclass properties."""

    def test_was_modified_true_when_capped(self) -> None:
        """was_modified returns True when multiplier was capped."""
        result = calculate_bump_multiplier("explicit", VolumeTier.HIGH, "paid")
        assert result.was_modified is True

    def test_was_modified_false_when_not_capped(self) -> None:
        """was_modified returns False when multiplier unchanged."""
        result = calculate_bump_multiplier("lifestyle", VolumeTier.LOW, "paid")
        assert result.was_modified is False

    def test_result_contains_all_expected_fields(self) -> None:
        """Result contains all expected fields."""
        result = calculate_bump_multiplier("amateur", VolumeTier.MID, "paid")
        assert hasattr(result, "multiplier")
        assert hasattr(result, "content_category")
        assert hasattr(result, "tier")
        assert hasattr(result, "source")
        assert hasattr(result, "capped")
        assert hasattr(result, "original_multiplier")


# =============================================================================
# Tests: calculate_followup_volume
# =============================================================================


class TestCalculateFollowupVolume:
    """Tests for calculate_followup_volume function."""

    def test_followup_volume_80_percent_rate(self) -> None:
        """80% of PPVs get followups."""
        result = calculate_followup_volume(5, tier_max=5, confidence_score=1.0)
        assert result.followup_count == 4  # 5 * 0.80 = 4

    def test_followup_volume_rounds_correctly(self) -> None:
        """Followup count rounds to nearest integer."""
        # 3 * 0.80 = 2.4 -> rounds to 2
        result = calculate_followup_volume(3, tier_max=5, confidence_score=1.0)
        assert result.followup_count == 2

        # 4 * 0.80 = 3.2 -> rounds to 3
        result = calculate_followup_volume(4, tier_max=5, confidence_score=1.0)
        assert result.followup_count == 3

    def test_followup_volume_capped_at_tier_max(self) -> None:
        """Followups capped at tier max."""
        result = calculate_followup_volume(10, tier_max=5, confidence_score=1.0)
        assert result.followup_count == 5
        assert result.limited_by_cap is True

    def test_followup_volume_capped_at_5(self) -> None:
        """Followups hard capped at MAX_FOLLOWUPS_PER_DAY (5)."""
        result = calculate_followup_volume(10, tier_max=10, confidence_score=1.0)
        assert result.followup_count == 5
        assert result.limited_by_cap is True

    def test_followup_volume_low_confidence_reduces(self) -> None:
        """Low confidence reduces followup count."""
        high_conf = calculate_followup_volume(5, tier_max=5, confidence_score=0.9)
        low_conf = calculate_followup_volume(5, tier_max=5, confidence_score=0.3)
        assert low_conf.followup_count < high_conf.followup_count
        assert low_conf.confidence_adjusted is True

    def test_followup_volume_zero_ppv_returns_zero(self) -> None:
        """Zero PPV count returns zero followups."""
        result = calculate_followup_volume(0, tier_max=5, confidence_score=1.0)
        assert result.followup_count == 0
        assert result.ppv_count == 0

    def test_followup_volume_negative_ppv_returns_zero(self) -> None:
        """Negative PPV count returns zero followups."""
        result = calculate_followup_volume(-5, tier_max=5, confidence_score=1.0)
        assert result.followup_count == 0
        assert result.ppv_count == 0

    def test_followup_volume_confidence_score_clamped_high(self) -> None:
        """Confidence score above 1.0 is clamped to 1.0."""
        result = calculate_followup_volume(5, tier_max=5, confidence_score=1.5)
        assert result.followup_count == 4  # Same as 1.0

    def test_followup_volume_confidence_score_clamped_low(self) -> None:
        """Confidence score below 0.0 is clamped to 0.0."""
        result = calculate_followup_volume(5, tier_max=5, confidence_score=-0.5)
        assert result.followup_count == 0
        assert result.confidence_adjusted is True

    def test_followup_volume_single_ppv(self) -> None:
        """Single PPV gets 1 followup (1 * 0.80 = 0.8 -> rounds to 1)."""
        result = calculate_followup_volume(1, tier_max=5, confidence_score=1.0)
        assert result.followup_count == 1

    @pytest.mark.parametrize("ppv_count,expected", [
        (1, 1),   # 0.80 -> 1
        (2, 2),   # 1.60 -> 2
        (3, 2),   # 2.40 -> 2
        (4, 3),   # 3.20 -> 3
        (5, 4),   # 4.00 -> 4
        (6, 5),   # 4.80 -> 5 (capped)
    ])
    def test_followup_volume_scaling(self, ppv_count: int, expected: int) -> None:
        """Followup count scales correctly with PPV count."""
        result = calculate_followup_volume(ppv_count, tier_max=5, confidence_score=1.0)
        assert result.followup_count == expected

    def test_followup_volume_tier_max_less_than_global_max(self) -> None:
        """Tier max below global max still limits correctly."""
        result = calculate_followup_volume(5, tier_max=2, confidence_score=1.0)
        assert result.followup_count == 2
        assert result.limited_by_cap is True

    def test_followup_volume_half_confidence(self) -> None:
        """Half confidence halves the followup count."""
        # 5 * 0.80 = 4, then 4 * 0.5 = 2
        result = calculate_followup_volume(5, tier_max=5, confidence_score=0.5)
        assert result.followup_count == 2
        assert result.confidence_adjusted is True


class TestFollowupVolumeResultDataclass:
    """Tests for FollowupVolumeResult dataclass properties."""

    def test_actual_rate_calculation(self) -> None:
        """actual_rate property calculates correctly."""
        result = calculate_followup_volume(5, tier_max=5, confidence_score=1.0)
        assert result.actual_rate == 4 / 5  # 0.8

    def test_actual_rate_zero_ppv(self) -> None:
        """actual_rate returns 0 when ppv_count is 0."""
        result = calculate_followup_volume(0, tier_max=5, confidence_score=1.0)
        assert result.actual_rate == 0.0

    def test_result_contains_all_expected_fields(self) -> None:
        """Result contains all expected fields."""
        result = calculate_followup_volume(5, tier_max=5, confidence_score=1.0)
        assert hasattr(result, "followup_count")
        assert hasattr(result, "ppv_count")
        assert hasattr(result, "followup_rate")
        assert hasattr(result, "limited_by_cap")
        assert hasattr(result, "confidence_adjusted")

    def test_followup_rate_stored_correctly(self) -> None:
        """followup_rate stores FOLLOWUP_BASE_RATE."""
        result = calculate_followup_volume(5, tier_max=5, confidence_score=1.0)
        assert result.followup_rate == FOLLOWUP_BASE_RATE


# =============================================================================
# Tests: apply_bump_to_engagement
# =============================================================================


class TestApplyBumpToEngagement:
    """Tests for apply_bump_to_engagement function."""

    def test_apply_bump_basic(self) -> None:
        """Basic bump application."""
        result = apply_bump_to_engagement(3, 2.67)
        assert result == 8  # 3 * 2.67 = 8.01 -> rounds to 8

    def test_apply_bump_capped_at_max(self) -> None:
        """Engagement capped at max_engagement."""
        result = apply_bump_to_engagement(10, 2.67, max_engagement=12)
        assert result == 12

    def test_apply_bump_no_change(self) -> None:
        """1.0x multiplier doesn't change value."""
        result = apply_bump_to_engagement(4, 1.0)
        assert result == 4

    def test_apply_bump_default_max_is_12(self) -> None:
        """Default max_engagement is 12."""
        result = apply_bump_to_engagement(10, 2.0)
        assert result == 12  # 10 * 2.0 = 20, capped at 12

    def test_apply_bump_zero_base_returns_zero(self) -> None:
        """Zero base engagement returns zero."""
        result = apply_bump_to_engagement(0, 2.0)
        assert result == 0

    def test_apply_bump_negative_base_returns_zero(self) -> None:
        """Negative base engagement returns zero."""
        result = apply_bump_to_engagement(-5, 2.0)
        assert result == 0

    def test_apply_bump_zero_multiplier_returns_zero(self) -> None:
        """Zero multiplier returns zero."""
        result = apply_bump_to_engagement(5, 0.0)
        assert result == 0

    def test_apply_bump_negative_multiplier_returns_zero(self) -> None:
        """Negative multiplier returns zero."""
        result = apply_bump_to_engagement(5, -1.0)
        assert result == 0

    @pytest.mark.parametrize("base,multiplier,expected", [
        (4, 1.0, 4),     # No change
        (4, 1.5, 6),     # 4 * 1.5 = 6
        (4, 2.0, 8),     # 4 * 2.0 = 8
        (4, 2.67, 11),   # 4 * 2.67 = 10.68 -> 11
        (3, 2.67, 8),    # 3 * 2.67 = 8.01 -> 8
        (5, 2.67, 12),   # 5 * 2.67 = 13.35 -> 12 (capped)
    ])
    def test_apply_bump_various_combinations(
        self, base: int, multiplier: float, expected: int
    ) -> None:
        """Various base/multiplier combinations produce expected results."""
        result = apply_bump_to_engagement(base, multiplier, max_engagement=12)
        assert result == expected

    def test_apply_bump_custom_max_engagement(self) -> None:
        """Custom max_engagement is respected."""
        result = apply_bump_to_engagement(5, 2.0, max_engagement=8)
        assert result == 8  # 10 -> capped at 8

    def test_apply_bump_rounds_half_up(self) -> None:
        """Rounding follows standard rules (half rounds to nearest even)."""
        # Python's round() uses banker's rounding
        # 2.5 -> 2, 3.5 -> 4, etc.
        result = apply_bump_to_engagement(5, 0.5)  # 2.5
        assert result == 2  # Banker's rounding


# =============================================================================
# Tests: get_bump_multiplier_for_category
# =============================================================================


class TestGetBumpMultiplierForCategory:
    """Tests for get_bump_multiplier_for_category function."""

    def test_get_multiplier_explicit(self) -> None:
        """Explicit category returns 2.67."""
        assert get_bump_multiplier_for_category("explicit") == 2.67

    def test_get_multiplier_amateur(self) -> None:
        """Amateur category returns 2.0."""
        assert get_bump_multiplier_for_category("amateur") == 2.0

    def test_get_multiplier_softcore(self) -> None:
        """Softcore category returns 1.5."""
        assert get_bump_multiplier_for_category("softcore") == 1.5

    def test_get_multiplier_lifestyle(self) -> None:
        """Lifestyle category returns 1.0."""
        assert get_bump_multiplier_for_category("lifestyle") == 1.0

    def test_get_multiplier_unknown_defaults_to_softcore(self) -> None:
        """Unknown category defaults to softcore (1.5)."""
        assert get_bump_multiplier_for_category("unknown") == 1.5

    def test_get_multiplier_empty_defaults_to_softcore(self) -> None:
        """Empty string defaults to softcore (1.5)."""
        assert get_bump_multiplier_for_category("") == 1.5

    def test_get_multiplier_none_defaults_to_softcore(self) -> None:
        """None defaults to softcore (1.5)."""
        assert get_bump_multiplier_for_category(None) == 1.5  # type: ignore[arg-type]

    def test_get_multiplier_case_insensitive(self) -> None:
        """Category matching is case-insensitive."""
        assert get_bump_multiplier_for_category("EXPLICIT") == 2.67
        assert get_bump_multiplier_for_category("Explicit") == 2.67

    def test_get_multiplier_strips_whitespace(self) -> None:
        """Category matching strips whitespace."""
        assert get_bump_multiplier_for_category("  explicit  ") == 2.67


# =============================================================================
# Tests: calculate_effective_engagement
# =============================================================================


class TestCalculateEffectiveEngagement:
    """Tests for calculate_effective_engagement convenience function."""

    def test_effective_engagement_basic(self) -> None:
        """Basic effective engagement calculation."""
        engagement, result = calculate_effective_engagement(
            base_engagement=4,
            content_category="amateur",
            tier=VolumeTier.LOW,
            page_type="paid",
        )
        assert engagement == 8  # 4 * 2.0 = 8
        assert result.multiplier == 2.0

    def test_effective_engagement_with_capping(self) -> None:
        """Effective engagement respects tier capping."""
        engagement, result = calculate_effective_engagement(
            base_engagement=4,
            content_category="explicit",
            tier=VolumeTier.HIGH,
            page_type="paid",
        )
        assert engagement == 6  # 4 * 1.5 (capped) = 6
        assert result.multiplier == 1.5
        assert result.capped is True

    def test_effective_engagement_with_max_limit(self) -> None:
        """Effective engagement respects max_engagement limit."""
        engagement, result = calculate_effective_engagement(
            base_engagement=6,
            content_category="explicit",
            tier=VolumeTier.LOW,
            page_type="paid",
            max_engagement=10,
        )
        assert engagement == 10  # 6 * 2.67 = 16.02, capped at 10
        assert result.multiplier == 2.67

    def test_effective_engagement_free_page_boost(self) -> None:
        """Effective engagement includes free page boost."""
        engagement_paid, _ = calculate_effective_engagement(
            base_engagement=4,
            content_category="softcore",
            tier=VolumeTier.LOW,
            page_type="paid",
        )
        engagement_free, result = calculate_effective_engagement(
            base_engagement=4,
            content_category="softcore",
            tier=VolumeTier.LOW,
            page_type="free",
        )
        # 4 * (1.5 + 0.1) = 6.4 -> 6
        assert engagement_free >= engagement_paid
        assert result.multiplier == 1.5 + FREE_PAGE_BUMP_BONUS

    def test_effective_engagement_returns_tuple(self) -> None:
        """Function returns tuple of (int, BumpMultiplierResult)."""
        result = calculate_effective_engagement(
            base_engagement=4,
            content_category="softcore",
            tier=VolumeTier.LOW,
            page_type="paid",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], BumpMultiplierResult)


# =============================================================================
# Tests: get_all_content_categories
# =============================================================================


class TestGetAllContentCategories:
    """Tests for get_all_content_categories function."""

    def test_returns_all_categories(self) -> None:
        """Returns all defined content categories."""
        categories = get_all_content_categories()
        assert "lifestyle" in categories
        assert "softcore" in categories
        assert "amateur" in categories
        assert "explicit" in categories
        assert len(categories) == 4

    def test_sorted_by_multiplier_value(self) -> None:
        """Categories are sorted by multiplier value (ascending)."""
        categories = get_all_content_categories()
        assert categories == ["lifestyle", "softcore", "amateur", "explicit"]


# =============================================================================
# Tests: Edge Cases and Integration
# =============================================================================


class TestEdgeCases:
    """Edge case and integration tests."""

    def test_full_workflow_low_tier_explicit(self) -> None:
        """Full workflow: LOW tier explicit creator gets maximum engagement."""
        # Step 1: Calculate multiplier
        bump_result = calculate_bump_multiplier("explicit", VolumeTier.LOW, "paid")
        assert bump_result.multiplier == 2.67
        assert bump_result.capped is False

        # Step 2: Apply to base engagement
        base_engagement = 4
        adjusted = apply_bump_to_engagement(base_engagement, bump_result.multiplier)
        assert adjusted == 11  # 4 * 2.67 = 10.68 -> 11

    def test_full_workflow_high_tier_explicit(self) -> None:
        """Full workflow: HIGH tier explicit creator gets capped engagement."""
        # Step 1: Calculate multiplier (should be capped)
        bump_result = calculate_bump_multiplier("explicit", VolumeTier.HIGH, "paid")
        assert bump_result.multiplier == 1.5
        assert bump_result.capped is True

        # Step 2: Apply to base engagement
        base_engagement = 6
        adjusted = apply_bump_to_engagement(base_engagement, bump_result.multiplier)
        assert adjusted == 9  # 6 * 1.5 = 9

    def test_full_workflow_with_followups(self) -> None:
        """Full workflow including followup calculation."""
        ppv_count = 4
        followup_result = calculate_followup_volume(
            ppv_count, tier_max=5, confidence_score=0.8
        )
        # 4 * 0.80 = 3.2 -> 3, then 3 * 0.8 = 2.4 -> 2
        assert followup_result.followup_count == 2
        assert followup_result.confidence_adjusted is True

    def test_extreme_low_base_engagement(self) -> None:
        """Extreme case: Very low base engagement still works."""
        result = apply_bump_to_engagement(1, 2.67)
        assert result == 3  # 1 * 2.67 = 2.67 -> 3

    def test_extreme_high_multiplier(self) -> None:
        """Extreme case: Very high multiplier respects max cap."""
        result = apply_bump_to_engagement(10, 100.0, max_engagement=12)
        assert result == 12


class TestTypeHints:
    """Verify type hints are correct at runtime."""

    def test_bump_multiplier_result_is_dataclass(self) -> None:
        """BumpMultiplierResult is a proper dataclass."""
        result = calculate_bump_multiplier("explicit", VolumeTier.LOW, "paid")
        assert isinstance(result, BumpMultiplierResult)

    def test_followup_volume_result_is_dataclass(self) -> None:
        """FollowupVolumeResult is a proper dataclass."""
        result = calculate_followup_volume(5, tier_max=5, confidence_score=1.0)
        assert isinstance(result, FollowupVolumeResult)

    def test_apply_bump_returns_int(self) -> None:
        """apply_bump_to_engagement returns int."""
        result = apply_bump_to_engagement(4, 2.67)
        assert isinstance(result, int)

    def test_get_multiplier_returns_float(self) -> None:
        """get_bump_multiplier_for_category returns float."""
        result = get_bump_multiplier_for_category("explicit")
        assert isinstance(result, float)
