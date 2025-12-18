"""
Tests for daily flavor rotation system.

Covers:
1. DAILY_FLAVORS dictionary structure and completeness
2. FlavorProfile dataclass immutability
3. get_daily_flavor() function with all days of week
4. weight_send_types_by_flavor() with boost and non-boost types
5. get_daily_caption_filter() return structure
6. get_flavor_for_week() weekly iteration
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from python.orchestration.daily_flavor import (
    DAILY_FLAVORS,
    FlavorBoosts,
    FlavorProfile,
    get_daily_caption_filter,
    get_daily_flavor,
    get_flavor_for_week,
    weight_send_types_by_flavor,
)

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def monday_date() -> datetime:
    """Monday date for testing (2025-12-15).

    Returns:
        datetime: A Monday in December 2025.
    """
    return datetime(2025, 12, 15)


@pytest.fixture
def tuesday_date() -> datetime:
    """Tuesday date for testing (2025-12-16).

    Returns:
        datetime: A Tuesday in December 2025.
    """
    return datetime(2025, 12, 16)


@pytest.fixture
def wednesday_date() -> datetime:
    """Wednesday date for testing (2025-12-17).

    Returns:
        datetime: A Wednesday in December 2025.
    """
    return datetime(2025, 12, 17)


@pytest.fixture
def thursday_date() -> datetime:
    """Thursday date for testing (2025-12-18).

    Returns:
        datetime: A Thursday in December 2025.
    """
    return datetime(2025, 12, 18)


@pytest.fixture
def friday_date() -> datetime:
    """Friday date for testing (2025-12-19).

    Returns:
        datetime: A Friday in December 2025.
    """
    return datetime(2025, 12, 19)


@pytest.fixture
def saturday_date() -> datetime:
    """Saturday date for testing (2025-12-20).

    Returns:
        datetime: A Saturday in December 2025.
    """
    return datetime(2025, 12, 20)


@pytest.fixture
def sunday_date() -> datetime:
    """Sunday date for testing (2025-12-21).

    Returns:
        datetime: A Sunday in December 2025.
    """
    return datetime(2025, 12, 21)


@pytest.fixture
def sample_allocation() -> dict[str, float]:
    """Sample send type allocation for testing.

    Returns:
        dict[str, float]: Allocation mapping send types to values.
    """
    return {
        "game_post": 2.0,
        "ppv_unlock": 3.0,
        "bump_normal": 1.0,
        "game_wheel": 1.5,
        "first_to_tip": 0.5,
    }


@pytest.fixture
def allocation_with_no_boosts() -> dict[str, float]:
    """Allocation with send types that won't be boosted on Monday.

    Returns:
        dict[str, float]: Allocation with only non-boost types for Monday.
    """
    return {
        "ppv_unlock": 3.0,
        "bump_normal": 2.0,
        "ppv_followup": 1.0,
    }


# =============================================================================
# DAILY_FLAVORS Structure Tests
# =============================================================================


class TestDailyFlavorsStructure:
    """Tests for DAILY_FLAVORS dictionary completeness."""

    def test_daily_flavors_has_all_seven_days(self) -> None:
        """DAILY_FLAVORS should contain entries for all 7 days (0-6)."""
        assert len(DAILY_FLAVORS) == 7
        for day_index in range(7):
            assert day_index in DAILY_FLAVORS

    def test_daily_flavors_keys_are_integers(self) -> None:
        """All keys in DAILY_FLAVORS should be integers."""
        for key in DAILY_FLAVORS.keys():
            assert isinstance(key, int)

    def test_daily_flavors_values_are_flavor_profiles(self) -> None:
        """All values in DAILY_FLAVORS should be FlavorProfile instances."""
        for value in DAILY_FLAVORS.values():
            assert isinstance(value, FlavorProfile)

    def test_daily_flavors_day_zero_is_monday(self) -> None:
        """Day 0 should be Monday (Playful flavor)."""
        assert DAILY_FLAVORS[0].name == "Playful"

    def test_daily_flavors_day_six_is_sunday(self) -> None:
        """Day 6 should be Sunday (Self-Care flavor)."""
        assert DAILY_FLAVORS[6].name == "Self-Care"

    def test_all_flavors_have_unique_names(self) -> None:
        """Each day should have a unique flavor name."""
        names = [profile.name for profile in DAILY_FLAVORS.values()]
        assert len(names) == len(set(names))

    def test_all_flavors_have_non_empty_boost_types(self) -> None:
        """Each flavor should have at least one boost type."""
        for day_index, profile in DAILY_FLAVORS.items():
            assert len(profile.boost_types) > 0, f"Day {day_index} has no boost types"

    def test_all_flavors_have_positive_multipliers(self) -> None:
        """Each flavor should have a boost multiplier > 1.0."""
        for day_index, profile in DAILY_FLAVORS.items():
            assert profile.boost_multiplier > 1.0, (
                f"Day {day_index} has non-positive multiplier"
            )

    def test_all_flavors_have_non_empty_emphasis(self) -> None:
        """Each flavor should have a non-empty emphasis."""
        for day_index, profile in DAILY_FLAVORS.items():
            assert profile.emphasis, f"Day {day_index} has empty emphasis"


# =============================================================================
# FlavorProfile Dataclass Tests
# =============================================================================


class TestFlavorProfileDataclass:
    """Tests for FlavorProfile dataclass behavior."""

    def test_flavor_profile_is_frozen(self) -> None:
        """FlavorProfile should be immutable (frozen dataclass)."""
        profile = FlavorProfile(
            name="Test",
            emphasis="testing",
            boost_types=["test_type"],
            boost_multiplier=1.5,
            preferred_tone="neutral",
            boost_categories=["test"],
        )
        with pytest.raises(FrozenInstanceError):
            profile.name = "Modified"  # type: ignore[misc]

    def test_flavor_profile_default_values(self) -> None:
        """FlavorProfile should have correct default values."""
        profile = FlavorProfile(name="Test", emphasis="testing")

        assert profile.boost_types == []
        assert profile.boost_multiplier == 1.0
        assert profile.preferred_tone == "neutral"
        assert profile.boost_categories == []

    def test_flavor_profile_equality(self) -> None:
        """FlavorProfiles with same values should be equal."""
        profile1 = FlavorProfile(
            name="Test",
            emphasis="testing",
            boost_types=["type1"],
            boost_multiplier=1.5,
        )
        profile2 = FlavorProfile(
            name="Test",
            emphasis="testing",
            boost_types=["type1"],
            boost_multiplier=1.5,
        )
        assert profile1 == profile2

    def test_flavor_profile_not_hashable_with_list_fields(self) -> None:
        """FlavorProfile with list fields is not hashable due to mutable defaults.

        Note: Although FlavorProfile is a frozen dataclass, it contains list
        fields (boost_types, boost_categories) which are mutable and thus
        make the object unhashable. This is expected behavior.
        """
        profile = FlavorProfile(name="Test", emphasis="testing")
        # Lists are mutable, so frozen dataclass with list fields is not hashable
        with pytest.raises(TypeError, match="unhashable type"):
            hash(profile)

    def test_flavor_profile_all_attributes_stored(self) -> None:
        """FlavorProfile should store all provided attributes."""
        profile = FlavorProfile(
            name="Playful",
            emphasis="games",
            boost_types=["game_post", "first_to_tip"],
            boost_multiplier=1.5,
            preferred_tone="playful",
            boost_categories=["interactive", "games"],
        )

        assert profile.name == "Playful"
        assert profile.emphasis == "games"
        assert profile.boost_types == ["game_post", "first_to_tip"]
        assert profile.boost_multiplier == 1.5
        assert profile.preferred_tone == "playful"
        assert profile.boost_categories == ["interactive", "games"]


# =============================================================================
# get_daily_flavor() Tests
# =============================================================================


class TestGetDailyFlavor:
    """Tests for get_daily_flavor() function."""

    def test_get_daily_flavor_monday(self, monday_date: datetime) -> None:
        """Monday (day 0) should return Playful flavor."""
        flavor = get_daily_flavor(monday_date)

        assert flavor["name"] == "Playful"
        assert flavor["emphasis"] == "games"
        assert flavor["day_of_week"] == 0
        assert flavor["boost_multiplier"] == 1.5
        assert flavor["preferred_tone"] == "playful"

    def test_get_daily_flavor_tuesday(self, tuesday_date: datetime) -> None:
        """Tuesday (day 1) should return Seductive flavor."""
        flavor = get_daily_flavor(tuesday_date)

        assert flavor["name"] == "Seductive"
        assert flavor["emphasis"] == "solo"
        assert flavor["day_of_week"] == 1
        assert flavor["boost_multiplier"] == 1.4
        assert flavor["preferred_tone"] == "seductive"

    def test_get_daily_flavor_wednesday(self, wednesday_date: datetime) -> None:
        """Wednesday (day 2) should return Wild flavor."""
        flavor = get_daily_flavor(wednesday_date)

        assert flavor["name"] == "Wild"
        assert flavor["emphasis"] == "explicit"
        assert flavor["day_of_week"] == 2
        assert flavor["boost_multiplier"] == 1.4
        assert flavor["preferred_tone"] == "explicit"

    def test_get_daily_flavor_thursday(self, thursday_date: datetime) -> None:
        """Thursday (day 3) should return Throwback flavor."""
        flavor = get_daily_flavor(thursday_date)

        assert flavor["name"] == "Throwback"
        assert flavor["emphasis"] == "bundles"
        assert flavor["day_of_week"] == 3
        assert flavor["boost_multiplier"] == 1.5
        assert flavor["preferred_tone"] == "nostalgic"

    def test_get_daily_flavor_friday(self, friday_date: datetime) -> None:
        """Friday (day 4) should return Freaky flavor."""
        flavor = get_daily_flavor(friday_date)

        assert flavor["name"] == "Freaky"
        assert flavor["emphasis"] == "fetish"
        assert flavor["day_of_week"] == 4
        assert flavor["boost_multiplier"] == 1.3
        assert flavor["preferred_tone"] == "adventurous"

    def test_get_daily_flavor_saturday(self, saturday_date: datetime) -> None:
        """Saturday (day 5) should return Sext flavor."""
        flavor = get_daily_flavor(saturday_date)

        assert flavor["name"] == "Sext"
        assert flavor["emphasis"] == "drip"
        assert flavor["day_of_week"] == 5
        assert flavor["boost_multiplier"] == 1.5
        assert flavor["preferred_tone"] == "flirty"

    def test_get_daily_flavor_sunday(self, sunday_date: datetime) -> None:
        """Sunday (day 6) should return Self-Care flavor."""
        flavor = get_daily_flavor(sunday_date)

        assert flavor["name"] == "Self-Care"
        assert flavor["emphasis"] == "gfe"
        assert flavor["day_of_week"] == 6
        assert flavor["boost_multiplier"] == 1.4
        assert flavor["preferred_tone"] == "intimate"

    def test_get_daily_flavor_returns_dict(self, monday_date: datetime) -> None:
        """get_daily_flavor should return a dictionary."""
        flavor = get_daily_flavor(monday_date)
        assert isinstance(flavor, dict)

    def test_get_daily_flavor_has_all_expected_keys(
        self, monday_date: datetime
    ) -> None:
        """Returned dict should have all expected keys."""
        flavor = get_daily_flavor(monday_date)
        expected_keys = {
            "name",
            "emphasis",
            "boost_types",
            "boost_multiplier",
            "preferred_tone",
            "boost_categories",
            "day_of_week",
        }
        assert set(flavor.keys()) == expected_keys

    def test_get_daily_flavor_boost_types_is_list(
        self, monday_date: datetime
    ) -> None:
        """boost_types should be a list (not the original tuple)."""
        flavor = get_daily_flavor(monday_date)
        assert isinstance(flavor["boost_types"], list)

    def test_get_daily_flavor_boost_categories_is_list(
        self, monday_date: datetime
    ) -> None:
        """boost_categories should be a list."""
        flavor = get_daily_flavor(monday_date)
        assert isinstance(flavor["boost_categories"], list)

    def test_get_daily_flavor_same_date_different_times(self) -> None:
        """Same date with different times should return same flavor."""
        morning = datetime(2025, 12, 15, 8, 0, 0)
        evening = datetime(2025, 12, 15, 20, 0, 0)

        flavor_morning = get_daily_flavor(morning)
        flavor_evening = get_daily_flavor(evening)

        assert flavor_morning == flavor_evening

    def test_get_daily_flavor_week_cycle(self, monday_date: datetime) -> None:
        """Flavor should cycle correctly over a full week."""
        expected_names = [
            "Playful",
            "Seductive",
            "Wild",
            "Throwback",
            "Freaky",
            "Sext",
            "Self-Care",
        ]

        for day_offset, expected_name in enumerate(expected_names):
            date = monday_date + timedelta(days=day_offset)
            flavor = get_daily_flavor(date)
            assert flavor["name"] == expected_name, (
                f"Day offset {day_offset} expected {expected_name}"
            )


# =============================================================================
# weight_send_types_by_flavor() Tests
# =============================================================================


class TestWeightSendTypesByFlavor:
    """Tests for weight_send_types_by_flavor() function."""

    def test_weight_boost_types_get_multiplier_applied(
        self, sample_allocation: dict[str, float], monday_date: datetime
    ) -> None:
        """Boost types should receive the flavor multiplier."""
        weighted = weight_send_types_by_flavor(sample_allocation, monday_date)

        # Monday boosts: game_wheel, game_post, first_to_tip (1.5x)
        # After normalization, boosted types should have higher relative weight
        original_total = sum(sample_allocation.values())
        weighted_total = sum(weighted.values())

        # Total should be preserved
        assert abs(weighted_total - original_total) < 0.001

        # Calculate original and weighted ratios for a boosted type
        original_game_post_ratio = (
            sample_allocation["game_post"] / original_total
        )
        weighted_game_post_ratio = weighted["game_post"] / weighted_total

        # Boosted type should have higher relative share
        assert weighted_game_post_ratio > original_game_post_ratio

    def test_weight_non_boost_types_remain_relatively_unchanged(
        self, sample_allocation: dict[str, float], monday_date: datetime
    ) -> None:
        """Non-boost types should have lower relative share after weighting."""
        weighted = weight_send_types_by_flavor(sample_allocation, monday_date)

        original_total = sum(sample_allocation.values())
        weighted_total = sum(weighted.values())

        # ppv_unlock and bump_normal are not Monday boost types
        original_ppv_ratio = sample_allocation["ppv_unlock"] / original_total
        weighted_ppv_ratio = weighted["ppv_unlock"] / weighted_total

        # Non-boosted type should have lower relative share
        assert weighted_ppv_ratio < original_ppv_ratio

    def test_weight_preserves_total_allocation(
        self, sample_allocation: dict[str, float], monday_date: datetime
    ) -> None:
        """Total allocation should be preserved after weighting."""
        weighted = weight_send_types_by_flavor(sample_allocation, monday_date)

        original_total = sum(sample_allocation.values())
        weighted_total = sum(weighted.values())

        assert abs(weighted_total - original_total) < 0.001

    def test_weight_empty_allocation_returns_empty(
        self, monday_date: datetime
    ) -> None:
        """Empty allocation should return empty dict."""
        result = weight_send_types_by_flavor({}, monday_date)
        assert result == {}

    def test_weight_zero_total_allocation_returns_copy(
        self, monday_date: datetime
    ) -> None:
        """Allocation with zero total should return copy unchanged."""
        allocation = {"game_post": 0.0, "ppv_unlock": 0.0}
        result = weight_send_types_by_flavor(allocation, monday_date)

        assert result == allocation

    def test_weight_no_matching_boost_types(
        self, allocation_with_no_boosts: dict[str, float], monday_date: datetime
    ) -> None:
        """Allocation with no matching boost types should remain unchanged."""
        weighted = weight_send_types_by_flavor(
            allocation_with_no_boosts, monday_date
        )

        # Should be approximately equal since no boosts apply
        for key in allocation_with_no_boosts:
            assert abs(weighted[key] - allocation_with_no_boosts[key]) < 0.001

    def test_weight_all_boost_types_preserves_ratios(
        self, monday_date: datetime
    ) -> None:
        """When all types are boost types, ratios should be preserved."""
        # Only Monday boost types
        allocation = {
            "game_wheel": 2.0,
            "game_post": 3.0,
            "first_to_tip": 1.0,
        }

        weighted = weight_send_types_by_flavor(allocation, monday_date)

        # All types boosted equally, so ratios should be preserved
        original_ratio = (
            allocation["game_post"] / allocation["game_wheel"]
        )
        weighted_ratio = weighted["game_post"] / weighted["game_wheel"]

        assert abs(weighted_ratio - original_ratio) < 0.001

    def test_weight_different_days_apply_different_boosts(
        self,
        sample_allocation: dict[str, float],
        monday_date: datetime,
        tuesday_date: datetime,
    ) -> None:
        """Different days should apply different boost profiles."""
        monday_weighted = weight_send_types_by_flavor(
            sample_allocation, monday_date
        )
        tuesday_weighted = weight_send_types_by_flavor(
            sample_allocation, tuesday_date
        )

        # Results should differ since different types are boosted
        assert monday_weighted != tuesday_weighted

    def test_weight_returns_new_dict(
        self, sample_allocation: dict[str, float], monday_date: datetime
    ) -> None:
        """Function should return a new dict, not modify input."""
        original_values = dict(sample_allocation)
        weighted = weight_send_types_by_flavor(sample_allocation, monday_date)

        # Original should be unchanged
        assert sample_allocation == original_values
        # Result should be different object
        assert weighted is not sample_allocation


# =============================================================================
# get_daily_caption_filter() Tests
# =============================================================================


class TestGetDailyCaptionFilter:
    """Tests for get_daily_caption_filter() function."""

    def test_get_caption_filter_returns_dict(
        self, monday_date: datetime
    ) -> None:
        """get_daily_caption_filter should return a dictionary."""
        result = get_daily_caption_filter(monday_date)
        assert isinstance(result, dict)

    def test_get_caption_filter_has_required_keys(
        self, monday_date: datetime
    ) -> None:
        """Result should have all required filter keys."""
        result = get_daily_caption_filter(monday_date)
        expected_keys = {
            "flavor_name",
            "preferred_tone",
            "boost_categories",
            "emphasis",
        }
        assert set(result.keys()) == expected_keys

    def test_get_caption_filter_monday_values(
        self, monday_date: datetime
    ) -> None:
        """Monday filter should have Playful values."""
        result = get_daily_caption_filter(monday_date)

        assert result["flavor_name"] == "Playful"
        assert result["preferred_tone"] == "playful"
        assert result["emphasis"] == "games"
        assert "interactive" in result["boost_categories"]
        assert "games" in result["boost_categories"]

    def test_get_caption_filter_tuesday_values(
        self, tuesday_date: datetime
    ) -> None:
        """Tuesday filter should have Seductive values."""
        result = get_daily_caption_filter(tuesday_date)

        assert result["flavor_name"] == "Seductive"
        assert result["preferred_tone"] == "seductive"
        assert result["emphasis"] == "solo"

    def test_get_caption_filter_boost_categories_is_list(
        self, monday_date: datetime
    ) -> None:
        """boost_categories should be a list."""
        result = get_daily_caption_filter(monday_date)
        assert isinstance(result["boost_categories"], list)

    def test_get_caption_filter_all_days(self, monday_date: datetime) -> None:
        """All days should return valid filter structures."""
        for day_offset in range(7):
            date = monday_date + timedelta(days=day_offset)
            result = get_daily_caption_filter(date)

            assert "flavor_name" in result
            assert "preferred_tone" in result
            assert "boost_categories" in result
            assert "emphasis" in result
            assert result["flavor_name"]  # Non-empty
            assert result["preferred_tone"]  # Non-empty


# =============================================================================
# get_flavor_for_week() Tests
# =============================================================================


class TestGetFlavorForWeek:
    """Tests for get_flavor_for_week() function."""

    def test_get_flavor_for_week_returns_seven_days(
        self, monday_date: datetime
    ) -> None:
        """get_flavor_for_week should return exactly 7 days."""
        result = get_flavor_for_week(monday_date)
        assert len(result) == 7

    def test_get_flavor_for_week_returns_list(
        self, monday_date: datetime
    ) -> None:
        """get_flavor_for_week should return a list."""
        result = get_flavor_for_week(monday_date)
        assert isinstance(result, list)

    def test_get_flavor_for_week_elements_are_dicts(
        self, monday_date: datetime
    ) -> None:
        """Each element should be a dictionary."""
        result = get_flavor_for_week(monday_date)
        for day_flavor in result:
            assert isinstance(day_flavor, dict)

    def test_get_flavor_for_week_starting_monday(
        self, monday_date: datetime
    ) -> None:
        """Week starting Monday should have correct sequence."""
        result = get_flavor_for_week(monday_date)

        expected_names = [
            "Playful",
            "Seductive",
            "Wild",
            "Throwback",
            "Freaky",
            "Sext",
            "Self-Care",
        ]

        for i, expected_name in enumerate(expected_names):
            assert result[i]["name"] == expected_name

    def test_get_flavor_for_week_starting_wednesday(
        self, wednesday_date: datetime
    ) -> None:
        """Week starting Wednesday should have rotated sequence."""
        result = get_flavor_for_week(wednesday_date)

        # Wednesday is day 2, so sequence starts mid-week
        expected_names = [
            "Wild",  # Wednesday
            "Throwback",  # Thursday
            "Freaky",  # Friday
            "Sext",  # Saturday
            "Self-Care",  # Sunday
            "Playful",  # Monday
            "Seductive",  # Tuesday
        ]

        for i, expected_name in enumerate(expected_names):
            assert result[i]["name"] == expected_name

    def test_get_flavor_for_week_correct_day_indices(
        self, monday_date: datetime
    ) -> None:
        """Each day should have correct day_of_week index."""
        result = get_flavor_for_week(monday_date)

        for i, day_flavor in enumerate(result):
            expected_dow = (monday_date + timedelta(days=i)).weekday()
            assert day_flavor["day_of_week"] == expected_dow

    def test_get_flavor_for_week_all_days_have_required_keys(
        self, monday_date: datetime
    ) -> None:
        """All days should have required keys."""
        result = get_flavor_for_week(monday_date)
        expected_keys = {
            "name",
            "emphasis",
            "boost_types",
            "boost_multiplier",
            "preferred_tone",
            "boost_categories",
            "day_of_week",
        }

        for day_flavor in result:
            assert set(day_flavor.keys()) == expected_keys

    def test_get_flavor_for_week_different_start_dates(self) -> None:
        """Different start dates should produce different week sequences."""
        monday = datetime(2025, 12, 15)
        tuesday = datetime(2025, 12, 16)

        monday_week = get_flavor_for_week(monday)
        tuesday_week = get_flavor_for_week(tuesday)

        # First days should differ
        assert monday_week[0]["name"] != tuesday_week[0]["name"]
        # But both should have 7 days
        assert len(monday_week) == 7
        assert len(tuesday_week) == 7


# =============================================================================
# FlavorBoosts TypedDict Tests
# =============================================================================


class TestFlavorBoostsTypedDict:
    """Tests for FlavorBoosts TypedDict structure."""

    def test_flavor_boosts_valid_structure(self) -> None:
        """FlavorBoosts should accept valid structure."""
        boosts: FlavorBoosts = {
            "boost_types": ["game_post", "first_to_tip"],
            "boost_multiplier": 1.5,
        }
        assert boosts["boost_types"] == ["game_post", "first_to_tip"]
        assert boosts["boost_multiplier"] == 1.5


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for daily flavor system."""

    def test_flavor_profile_with_empty_boost_types(self) -> None:
        """FlavorProfile should handle empty boost_types list."""
        profile = FlavorProfile(
            name="Empty",
            emphasis="test",
            boost_types=[],
            boost_multiplier=1.0,
        )
        assert profile.boost_types == []

    def test_weight_single_send_type(self, monday_date: datetime) -> None:
        """Weighting single send type should preserve value."""
        allocation = {"game_post": 5.0}
        weighted = weight_send_types_by_flavor(allocation, monday_date)

        assert abs(weighted["game_post"] - 5.0) < 0.001

    def test_weight_very_small_values(self, monday_date: datetime) -> None:
        """Weighting should handle very small allocation values."""
        allocation = {
            "game_post": 0.001,
            "ppv_unlock": 0.001,
        }
        weighted = weight_send_types_by_flavor(allocation, monday_date)

        # Total should be preserved
        original_total = sum(allocation.values())
        weighted_total = sum(weighted.values())
        assert abs(weighted_total - original_total) < 0.0001

    def test_weight_very_large_values(self, monday_date: datetime) -> None:
        """Weighting should handle large allocation values."""
        allocation = {
            "game_post": 1000000.0,
            "ppv_unlock": 1000000.0,
        }
        weighted = weight_send_types_by_flavor(allocation, monday_date)

        # Total should be preserved
        original_total = sum(allocation.values())
        weighted_total = sum(weighted.values())
        assert abs(weighted_total - original_total) < 1.0

    def test_get_daily_flavor_year_boundary(self) -> None:
        """get_daily_flavor should work across year boundaries."""
        new_years = datetime(2026, 1, 1)  # Thursday
        flavor = get_daily_flavor(new_years)

        assert flavor["day_of_week"] == 3  # Thursday
        assert flavor["name"] == "Throwback"

    def test_get_flavor_for_week_across_year_boundary(self) -> None:
        """get_flavor_for_week should work across year boundaries."""
        dec_29 = datetime(2025, 12, 29)  # Monday
        week = get_flavor_for_week(dec_29)

        assert len(week) == 7
        assert week[0]["name"] == "Playful"  # Monday
        # Week spans into 2026

    def test_flavor_consistency_across_years(self) -> None:
        """Same day of week should have same flavor regardless of year."""
        monday_2025 = datetime(2025, 12, 15)
        monday_2026 = datetime(2026, 1, 5)

        flavor_2025 = get_daily_flavor(monday_2025)
        flavor_2026 = get_daily_flavor(monday_2026)

        assert flavor_2025["name"] == flavor_2026["name"]
        assert flavor_2025["emphasis"] == flavor_2026["emphasis"]


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_week_weight_calculation(
        self, monday_date: datetime, sample_allocation: dict[str, float]
    ) -> None:
        """Test weighting across a full week of flavors."""
        original_total = sum(sample_allocation.values())

        for day_offset in range(7):
            date = monday_date + timedelta(days=day_offset)
            weighted = weight_send_types_by_flavor(sample_allocation, date)

            # Total should always be preserved
            weighted_total = sum(weighted.values())
            assert abs(weighted_total - original_total) < 0.001

    def test_caption_filter_matches_flavor(
        self, monday_date: datetime
    ) -> None:
        """Caption filter should match the corresponding flavor."""
        for day_offset in range(7):
            date = monday_date + timedelta(days=day_offset)
            flavor = get_daily_flavor(date)
            caption_filter = get_daily_caption_filter(date)

            assert caption_filter["flavor_name"] == flavor["name"]
            assert caption_filter["preferred_tone"] == flavor["preferred_tone"]
            assert caption_filter["emphasis"] == flavor["emphasis"]
            assert caption_filter["boost_categories"] == flavor["boost_categories"]

    def test_week_preview_matches_daily_calls(
        self, monday_date: datetime
    ) -> None:
        """get_flavor_for_week should match individual get_daily_flavor calls."""
        week = get_flavor_for_week(monday_date)

        for day_offset in range(7):
            date = monday_date + timedelta(days=day_offset)
            daily = get_daily_flavor(date)

            assert week[day_offset] == daily
