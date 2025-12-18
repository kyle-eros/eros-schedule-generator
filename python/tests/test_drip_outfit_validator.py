"""
Comprehensive test suite for Drip Outfit Validation (Gap 6.1).

Tests the DripOutfitValidator class and related functions for ensuring
outfit consistency across drip content campaigns.

Run with: pytest python/tests/test_drip_outfit_validator.py -v
"""
from __future__ import annotations

from typing import Any

import pytest

from python.quality.drip_outfit_validator import (
    DRIP_SEND_TYPES,
    DripOutfitValidationResult,
    DripOutfitValidator,
    validate_drip_schedule_outfits,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def validator() -> DripOutfitValidator:
    """Fresh DripOutfitValidator instance."""
    return DripOutfitValidator()


@pytest.fixture
def consistent_drip_items() -> list[dict[str, Any]]:
    """Drip items with consistent outfits within each shoot."""
    return [
        {"id": 1, "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 2, "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 3, "shoot_id": "S002", "outfit_id": "O2"},
        {"id": 4, "shoot_id": "S002", "outfit_id": "O2"},
    ]


@pytest.fixture
def inconsistent_drip_items() -> list[dict[str, Any]]:
    """Drip items with inconsistent outfits within a shoot."""
    return [
        {"id": 1, "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 2, "shoot_id": "S001", "outfit_id": "O2"},  # Mismatch!
        {"id": 3, "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 4, "shoot_id": "S002", "outfit_id": "O3"},
    ]


@pytest.fixture
def items_missing_shoot_id() -> list[dict[str, Any]]:
    """Drip items with missing shoot_id fields."""
    return [
        {"id": 1, "outfit_id": "O1"},  # No shoot_id
        {"id": 2, "shoot_id": None, "outfit_id": "O2"},  # Explicit None
        {"id": 3, "shoot_id": "S001", "outfit_id": "O1"},
    ]


@pytest.fixture
def content_metadata_complete() -> dict[str, Any]:
    """Content metadata with complete shoot information."""
    return {
        "shoots": {
            "S001": {"outfit_id": "O1", "name": "Beach Set"},
            "S002": {"outfit_id": "O2", "name": "Bedroom Set"},
            "S003": {"outfit_id": "O3", "name": "Outdoor Set"},
        }
    }


@pytest.fixture
def content_metadata_missing_shoots() -> dict[str, Any]:
    """Content metadata with missing shoot information."""
    return {
        "shoots": {
            "S001": {"outfit_id": "O1"},
            # S002 missing entirely
        }
    }


@pytest.fixture
def content_metadata_empty() -> dict[str, Any]:
    """Content metadata with empty shoots dict."""
    return {"shoots": {}}


@pytest.fixture
def content_metadata_no_shoots_key() -> dict[str, Any]:
    """Content metadata without shoots key."""
    return {"other_key": "value"}


@pytest.fixture
def full_schedule_with_drip() -> list[dict[str, Any]]:
    """Complete schedule with mixed send types including drip."""
    return [
        {"id": 1, "send_type_key": "bump_drip", "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 2, "send_type_key": "ppv_unlock", "shoot_id": "S001", "outfit_id": "O2"},  # Non-drip
        {"id": 3, "send_type_key": "drip_set", "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 4, "send_type_key": "bump_normal", "shoot_id": "S001", "outfit_id": "O1"},  # Drip
        {"id": 5, "send_type_key": "tip_goal", "shoot_id": "S002", "outfit_id": "O3"},  # Non-drip
        {"id": 6, "send_type_key": "bump_drip", "shoot_id": "S002", "outfit_id": "O2"},
    ]


@pytest.fixture
def schedule_no_drip() -> list[dict[str, Any]]:
    """Schedule with no drip content."""
    return [
        {"id": 1, "send_type_key": "ppv_unlock", "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 2, "send_type_key": "tip_goal", "shoot_id": "S001", "outfit_id": "O2"},
        {"id": 3, "send_type_key": "bundle", "shoot_id": "S002", "outfit_id": "O1"},
    ]


@pytest.fixture
def schedule_with_send_type_field() -> list[dict[str, Any]]:
    """Schedule using 'send_type' field instead of 'send_type_key'."""
    return [
        {"id": 1, "send_type": "bump_drip", "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 2, "send_type": "drip_set", "shoot_id": "S001", "outfit_id": "O1"},
        {"id": 3, "send_type": "ppv_unlock", "shoot_id": "S001", "outfit_id": "O2"},
    ]


# =============================================================================
# TEST DRIP_SEND_TYPES CONSTANT
# =============================================================================


class TestDripSendTypes:
    """Tests for DRIP_SEND_TYPES frozenset."""

    def test_is_frozenset(self) -> None:
        """Verify DRIP_SEND_TYPES is a frozenset (immutable)."""
        assert isinstance(DRIP_SEND_TYPES, frozenset)

    def test_contains_expected_types(self) -> None:
        """Verify DRIP_SEND_TYPES contains all expected drip send types."""
        expected = {"bump_drip", "drip_set", "bump_normal"}
        assert DRIP_SEND_TYPES == expected

    def test_bump_drip_in_set(self) -> None:
        """Verify bump_drip is in DRIP_SEND_TYPES."""
        assert "bump_drip" in DRIP_SEND_TYPES

    def test_drip_set_in_set(self) -> None:
        """Verify drip_set is in DRIP_SEND_TYPES."""
        assert "drip_set" in DRIP_SEND_TYPES

    def test_bump_normal_in_set(self) -> None:
        """Verify bump_normal is in DRIP_SEND_TYPES."""
        assert "bump_normal" in DRIP_SEND_TYPES

    def test_non_drip_types_not_in_set(self) -> None:
        """Verify non-drip types are not in DRIP_SEND_TYPES."""
        non_drip_types = [
            "ppv_unlock",
            "tip_goal",
            "bundle",
            "flash_bundle",
            "dm_farm",
            "renew_on_post",
        ]
        for send_type in non_drip_types:
            assert send_type not in DRIP_SEND_TYPES

    def test_count_of_drip_types(self) -> None:
        """Verify there are exactly 3 drip send types."""
        assert len(DRIP_SEND_TYPES) == 3


# =============================================================================
# TEST DripOutfitValidationResult DATACLASS
# =============================================================================


class TestDripOutfitValidationResult:
    """Tests for DripOutfitValidationResult dataclass."""

    def test_dataclass_creation(self) -> None:
        """Test DripOutfitValidationResult can be instantiated with all fields."""
        result = DripOutfitValidationResult(
            is_valid=True,
            total_drip_items=5,
            shoots_checked=2,
            inconsistencies=(),
            recommendation=None,
        )

        assert result.is_valid is True
        assert result.total_drip_items == 5
        assert result.shoots_checked == 2
        assert result.inconsistencies == ()
        assert result.recommendation is None

    def test_dataclass_is_frozen(self) -> None:
        """Verify DripOutfitValidationResult is immutable (frozen=True)."""
        result = DripOutfitValidationResult(
            is_valid=True,
            total_drip_items=5,
            shoots_checked=2,
            inconsistencies=(),
            recommendation=None,
        )

        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore[misc]

    def test_dataclass_with_inconsistencies(self) -> None:
        """Test DripOutfitValidationResult with inconsistency tuple."""
        inconsistencies = (
            {"item_id": 1, "issue": "Outfit mismatch"},
            {"item_id": 2, "issue": "Missing shoot_id"},
        )

        result = DripOutfitValidationResult(
            is_valid=False,
            total_drip_items=3,
            shoots_checked=1,
            inconsistencies=inconsistencies,
            recommendation="Update outfit assignments",
        )

        assert result.is_valid is False
        assert len(result.inconsistencies) == 2
        assert result.recommendation == "Update outfit assignments"

    def test_dataclass_has_slots(self) -> None:
        """Verify DripOutfitValidationResult uses slots for memory efficiency."""
        result = DripOutfitValidationResult(
            is_valid=True,
            total_drip_items=0,
            shoots_checked=0,
            inconsistencies=(),
            recommendation=None,
        )

        # Slots-based classes don't have __dict__
        assert not hasattr(result, "__dict__")

    def test_dataclass_equality(self) -> None:
        """Test DripOutfitValidationResult equality comparison."""
        result1 = DripOutfitValidationResult(
            is_valid=True,
            total_drip_items=5,
            shoots_checked=2,
            inconsistencies=(),
            recommendation=None,
        )

        result2 = DripOutfitValidationResult(
            is_valid=True,
            total_drip_items=5,
            shoots_checked=2,
            inconsistencies=(),
            recommendation=None,
        )

        assert result1 == result2


# =============================================================================
# TEST DripOutfitValidator.validate_drip_outfit_consistency()
# =============================================================================


class TestValidateDripOutfitConsistency:
    """Tests for DripOutfitValidator.validate_drip_outfit_consistency method."""

    def test_consistent_outfits_pass_validation(
        self,
        validator: DripOutfitValidator,
        consistent_drip_items: list[dict[str, Any]],
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Test that items with consistent outfits pass validation."""
        result = validator.validate_drip_outfit_consistency(
            consistent_drip_items, content_metadata_complete
        )

        assert result["is_valid"] is True
        assert result["total_drip_items"] == 4
        assert result["shoots_checked"] == 2
        assert len(result["inconsistencies"]) == 0
        assert result["recommendation"] is None

    def test_inconsistent_outfits_fail_validation(
        self,
        validator: DripOutfitValidator,
        inconsistent_drip_items: list[dict[str, Any]],
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Test that items with inconsistent outfits fail validation."""
        result = validator.validate_drip_outfit_consistency(
            inconsistent_drip_items, content_metadata_complete
        )

        assert result["is_valid"] is False
        assert result["total_drip_items"] == 4
        assert len(result["inconsistencies"]) > 0

        # Find the error inconsistency
        errors = [i for i in result["inconsistencies"] if i["severity"] == "ERROR"]
        assert len(errors) >= 1
        assert errors[0]["issue"] == "Outfit mismatch within shoot"

    def test_inconsistency_details_are_complete(
        self,
        validator: DripOutfitValidator,
        inconsistent_drip_items: list[dict[str, Any]],
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Test that inconsistency details contain all required fields."""
        result = validator.validate_drip_outfit_consistency(
            inconsistent_drip_items, content_metadata_complete
        )

        for inconsistency in result["inconsistencies"]:
            assert "item_id" in inconsistency
            assert "shoot_id" in inconsistency
            assert "expected_outfit" in inconsistency
            assert "actual_outfit" in inconsistency
            assert "issue" in inconsistency
            assert "severity" in inconsistency
            assert inconsistency["severity"] in ("ERROR", "WARNING")

    def test_empty_drip_items_handling(
        self,
        validator: DripOutfitValidator,
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Test handling of empty drip items list."""
        result = validator.validate_drip_outfit_consistency(
            [], content_metadata_complete
        )

        assert result["is_valid"] is True
        assert result["total_drip_items"] == 0
        assert result["shoots_checked"] == 0
        assert result["inconsistencies"] == []
        assert result["recommendation"] is None

    def test_missing_shoot_id_generates_warning(
        self,
        validator: DripOutfitValidator,
        items_missing_shoot_id: list[dict[str, Any]],
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Test that missing shoot_id generates WARNING not ERROR."""
        result = validator.validate_drip_outfit_consistency(
            items_missing_shoot_id, content_metadata_complete
        )

        # Should still be valid (warnings don't invalidate)
        assert result["is_valid"] is True

        warnings = [i for i in result["inconsistencies"] if i["severity"] == "WARNING"]
        assert len(warnings) >= 2  # Two items missing shoot_id

        for warning in warnings:
            assert "Missing shoot_id" in warning["issue"]

    def test_missing_shoot_in_metadata_generates_warning(
        self,
        validator: DripOutfitValidator,
        content_metadata_missing_shoots: dict[str, Any],
    ) -> None:
        """Test that missing shoot in metadata generates WARNING."""
        drip_items = [
            {"id": 1, "shoot_id": "S002", "outfit_id": "O2"},  # S002 not in metadata
        ]

        result = validator.validate_drip_outfit_consistency(
            drip_items, content_metadata_missing_shoots
        )

        # Should still be valid (warnings don't invalidate)
        assert result["is_valid"] is True

        warnings = [i for i in result["inconsistencies"] if i["severity"] == "WARNING"]
        assert len(warnings) == 1
        assert "No expected outfit defined for shoot S002" in warnings[0]["issue"]

    def test_empty_shoots_metadata(
        self,
        validator: DripOutfitValidator,
        consistent_drip_items: list[dict[str, Any]],
        content_metadata_empty: dict[str, Any],
    ) -> None:
        """Test handling when shoots metadata is empty dict."""
        result = validator.validate_drip_outfit_consistency(
            consistent_drip_items, content_metadata_empty
        )

        # Should be valid but with warnings
        assert result["is_valid"] is True

        warnings = [i for i in result["inconsistencies"] if i["severity"] == "WARNING"]
        assert len(warnings) == 4  # All items generate warnings

    def test_no_shoots_key_in_metadata(
        self,
        validator: DripOutfitValidator,
        consistent_drip_items: list[dict[str, Any]],
        content_metadata_no_shoots_key: dict[str, Any],
    ) -> None:
        """Test handling when metadata has no 'shoots' key."""
        result = validator.validate_drip_outfit_consistency(
            consistent_drip_items, content_metadata_no_shoots_key
        )

        # Should be valid but with warnings
        assert result["is_valid"] is True

        warnings = [i for i in result["inconsistencies"] if i["severity"] == "WARNING"]
        assert len(warnings) == 4

    def test_none_shoots_in_metadata(
        self,
        validator: DripOutfitValidator,
        consistent_drip_items: list[dict[str, Any]],
    ) -> None:
        """Test handling when shoots is explicitly None in metadata."""
        content_metadata = {"shoots": None}

        result = validator.validate_drip_outfit_consistency(
            consistent_drip_items, content_metadata
        )

        assert result["is_valid"] is True
        warnings = [i for i in result["inconsistencies"] if i["severity"] == "WARNING"]
        assert len(warnings) == 4

    def test_mixed_valid_and_invalid_items(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test schedule with mix of valid and invalid items."""
        drip_items = [
            {"id": 1, "shoot_id": "S001", "outfit_id": "O1"},  # Valid
            {"id": 2, "shoot_id": "S001", "outfit_id": "O2"},  # Mismatch (ERROR)
            {"id": 3, "outfit_id": "O1"},  # Missing shoot_id (WARNING)
            {"id": 4, "shoot_id": "S002", "outfit_id": "O2"},  # Valid
        ]
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
                "S002": {"outfit_id": "O2"},
            }
        }

        result = validator.validate_drip_outfit_consistency(
            drip_items, content_metadata
        )

        assert result["is_valid"] is False  # Has ERROR
        assert result["total_drip_items"] == 4
        assert result["shoots_checked"] == 2

        errors = [i for i in result["inconsistencies"] if i["severity"] == "ERROR"]
        warnings = [i for i in result["inconsistencies"] if i["severity"] == "WARNING"]

        assert len(errors) == 1
        assert len(warnings) == 1

    def test_multiple_shoots_with_multiple_errors(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test multiple shoots each with outfit mismatches."""
        drip_items = [
            {"id": 1, "shoot_id": "S001", "outfit_id": "O1"},
            {"id": 2, "shoot_id": "S001", "outfit_id": "O2"},  # ERROR
            {"id": 3, "shoot_id": "S002", "outfit_id": "O3"},
            {"id": 4, "shoot_id": "S002", "outfit_id": "O4"},  # ERROR
        ]
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
                "S002": {"outfit_id": "O3"},
            }
        }

        result = validator.validate_drip_outfit_consistency(
            drip_items, content_metadata
        )

        assert result["is_valid"] is False
        errors = [i for i in result["inconsistencies"] if i["severity"] == "ERROR"]
        assert len(errors) == 2

    def test_item_with_none_outfit_id(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test item with None outfit_id."""
        drip_items = [
            {"id": 1, "shoot_id": "S001", "outfit_id": None},  # None outfit
        ]
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
            }
        }

        result = validator.validate_drip_outfit_consistency(
            drip_items, content_metadata
        )

        # None != "O1" so should be error
        assert result["is_valid"] is False
        errors = [i for i in result["inconsistencies"] if i["severity"] == "ERROR"]
        assert len(errors) == 1
        assert errors[0]["actual_outfit"] is None

    def test_returns_dict_not_dataclass(
        self,
        validator: DripOutfitValidator,
        consistent_drip_items: list[dict[str, Any]],
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Verify method returns dict (not DripOutfitValidationResult)."""
        result = validator.validate_drip_outfit_consistency(
            consistent_drip_items, content_metadata_complete
        )

        assert isinstance(result, dict)


# =============================================================================
# TEST DripOutfitValidator._generate_recommendation()
# =============================================================================


class TestGenerateRecommendation:
    """Tests for DripOutfitValidator._generate_recommendation method."""

    def test_no_inconsistencies_returns_none(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test that no inconsistencies returns None."""
        result = validator._generate_recommendation([])
        assert result is None

    def test_errors_only_recommendation(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test recommendation with only ERROR inconsistencies."""
        inconsistencies = [
            {"severity": "ERROR", "item_id": 1},
            {"severity": "ERROR", "item_id": 2},
        ]

        result = validator._generate_recommendation(inconsistencies)

        assert result is not None
        assert "2 outfit mismatch(es)" in result
        assert "update content selection" in result.lower()

    def test_warnings_only_recommendation(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test recommendation with only WARNING inconsistencies."""
        inconsistencies = [
            {"severity": "WARNING", "item_id": 1},
            {"severity": "WARNING", "item_id": 2},
            {"severity": "WARNING", "item_id": 3},
        ]

        result = validator._generate_recommendation(inconsistencies)

        assert result is not None
        assert "3 warning(s)" in result
        assert "review items" in result.lower()

    def test_mixed_errors_and_warnings_recommendation(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test recommendation with both ERRORs and WARNINGs."""
        inconsistencies = [
            {"severity": "ERROR", "item_id": 1},
            {"severity": "WARNING", "item_id": 2},
            {"severity": "ERROR", "item_id": 3},
            {"severity": "WARNING", "item_id": 4},
        ]

        result = validator._generate_recommendation(inconsistencies)

        assert result is not None
        assert "2 outfit mismatch(es)" in result
        assert "2 warning(s)" in result
        assert "; " in result  # Parts joined by semicolon

    def test_single_error_grammar(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test grammatical correctness with single error."""
        inconsistencies = [{"severity": "ERROR", "item_id": 1}]

        result = validator._generate_recommendation(inconsistencies)

        assert result is not None
        assert "1 outfit mismatch(es)" in result

    def test_single_warning_grammar(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test grammatical correctness with single warning."""
        inconsistencies = [{"severity": "WARNING", "item_id": 1}]

        result = validator._generate_recommendation(inconsistencies)

        assert result is not None
        assert "1 warning(s)" in result


# =============================================================================
# TEST validate_drip_schedule_outfits() FUNCTION
# =============================================================================


class TestValidateDripScheduleOutfits:
    """Tests for validate_drip_schedule_outfits convenience function."""

    def test_filters_only_drip_send_types(
        self,
        full_schedule_with_drip: list[dict[str, Any]],
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Test that only drip send types are included in validation."""
        # Manually add metadata for shoots used in fixture
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
                "S002": {"outfit_id": "O2"},
            }
        }

        result = validate_drip_schedule_outfits(
            full_schedule_with_drip, content_metadata
        )

        # Schedule has 6 items, but only 4 are drip types
        # (bump_drip x2, drip_set x1, bump_normal x1)
        assert result["total_drip_items"] == 4

    def test_returns_comprehensive_validation_results(
        self,
        full_schedule_with_drip: list[dict[str, Any]],
    ) -> None:
        """Test that result contains all expected keys."""
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
                "S002": {"outfit_id": "O2"},
            }
        }

        result = validate_drip_schedule_outfits(
            full_schedule_with_drip, content_metadata
        )

        required_keys = {
            "is_valid",
            "total_drip_items",
            "shoots_checked",
            "inconsistencies",
            "recommendation",
        }
        assert required_keys.issubset(result.keys())

    def test_handles_schedules_with_no_drip_content(
        self,
        schedule_no_drip: list[dict[str, Any]],
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Test handling of schedules with no drip content."""
        result = validate_drip_schedule_outfits(
            schedule_no_drip, content_metadata_complete
        )

        assert result["is_valid"] is True
        assert result["total_drip_items"] == 0
        assert result["shoots_checked"] == 0
        assert result["inconsistencies"] == []
        assert result["recommendation"] is None
        assert "message" in result
        assert "No drip items" in result["message"]

    def test_empty_schedule(
        self,
        content_metadata_complete: dict[str, Any],
    ) -> None:
        """Test handling of empty schedule."""
        result = validate_drip_schedule_outfits([], content_metadata_complete)

        assert result["is_valid"] is True
        assert result["total_drip_items"] == 0
        assert "message" in result

    def test_accepts_send_type_field(
        self,
        schedule_with_send_type_field: list[dict[str, Any]],
    ) -> None:
        """Test that 'send_type' field is recognized in addition to 'send_type_key'."""
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
            }
        }

        result = validate_drip_schedule_outfits(
            schedule_with_send_type_field, content_metadata
        )

        # 2 drip items (bump_drip, drip_set)
        assert result["total_drip_items"] == 2

    def test_mixed_field_names_in_same_schedule(self) -> None:
        """Test schedule with mixed send_type and send_type_key fields."""
        schedule = [
            {"id": 1, "send_type_key": "bump_drip", "shoot_id": "S001", "outfit_id": "O1"},
            {"id": 2, "send_type": "drip_set", "shoot_id": "S001", "outfit_id": "O1"},
            {"id": 3, "send_type_key": "ppv_unlock", "shoot_id": "S001", "outfit_id": "O2"},
            {"id": 4, "send_type": "bump_normal", "shoot_id": "S001", "outfit_id": "O1"},
        ]
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
            }
        }

        result = validate_drip_schedule_outfits(schedule, content_metadata)

        # 3 drip items (bump_drip, drip_set, bump_normal)
        assert result["total_drip_items"] == 3
        assert result["is_valid"] is True

    def test_validates_outfit_consistency(self) -> None:
        """Test that outfit consistency validation is performed on drip items."""
        schedule = [
            {"id": 1, "send_type_key": "bump_drip", "shoot_id": "S001", "outfit_id": "O1"},
            {"id": 2, "send_type_key": "drip_set", "shoot_id": "S001", "outfit_id": "O2"},  # Mismatch!
        ]
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
            }
        }

        result = validate_drip_schedule_outfits(schedule, content_metadata)

        assert result["is_valid"] is False
        assert len(result["inconsistencies"]) == 1
        assert result["inconsistencies"][0]["severity"] == "ERROR"

    def test_no_message_key_when_drip_items_present(self) -> None:
        """Test that 'message' key is only present when no drip items."""
        schedule = [
            {"id": 1, "send_type_key": "bump_drip", "shoot_id": "S001", "outfit_id": "O1"},
        ]
        content_metadata = {
            "shoots": {
                "S001": {"outfit_id": "O1"},
            }
        }

        result = validate_drip_schedule_outfits(schedule, content_metadata)

        # 'message' key should not be present when drip items exist
        assert "message" not in result


# =============================================================================
# EDGE CASE AND INTEGRATION TESTS
# =============================================================================


class TestEdgeCases:
    """Edge case tests for drip outfit validation."""

    def test_validator_is_stateless(self) -> None:
        """Test that validator maintains no state between calls."""
        validator = DripOutfitValidator()

        items1 = [{"id": 1, "shoot_id": "S001", "outfit_id": "O1"}]
        items2 = [{"id": 2, "shoot_id": "S002", "outfit_id": "O2"}]
        metadata1 = {"shoots": {"S001": {"outfit_id": "O1"}}}
        metadata2 = {"shoots": {"S002": {"outfit_id": "O2"}}}

        result1 = validator.validate_drip_outfit_consistency(items1, metadata1)
        result2 = validator.validate_drip_outfit_consistency(items2, metadata2)

        assert result1["shoots_checked"] == 1
        assert result2["shoots_checked"] == 1
        # Each call should be independent
        assert result1["is_valid"] is True
        assert result2["is_valid"] is True

    def test_large_number_of_items(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test validation with large number of drip items."""
        # Create 1000 items across 100 shoots
        drip_items = []
        shoots_metadata = {}

        for shoot_num in range(100):
            shoot_id = f"S{shoot_num:03d}"
            outfit_id = f"O{shoot_num:03d}"
            shoots_metadata[shoot_id] = {"outfit_id": outfit_id}

            for item_num in range(10):
                drip_items.append({
                    "id": shoot_num * 10 + item_num,
                    "shoot_id": shoot_id,
                    "outfit_id": outfit_id,
                })

        content_metadata = {"shoots": shoots_metadata}

        result = validator.validate_drip_outfit_consistency(
            drip_items, content_metadata
        )

        assert result["is_valid"] is True
        assert result["total_drip_items"] == 1000
        assert result["shoots_checked"] == 100
        assert len(result["inconsistencies"]) == 0

    def test_special_characters_in_ids(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test handling of special characters in shoot_id and outfit_id."""
        drip_items = [
            {"id": 1, "shoot_id": "shoot-123_abc", "outfit_id": "outfit.v2"},
            {"id": 2, "shoot_id": "shoot-123_abc", "outfit_id": "outfit.v2"},
        ]
        content_metadata = {
            "shoots": {
                "shoot-123_abc": {"outfit_id": "outfit.v2"},
            }
        }

        result = validator.validate_drip_outfit_consistency(
            drip_items, content_metadata
        )

        assert result["is_valid"] is True

    def test_unicode_in_ids(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test handling of unicode characters in IDs."""
        drip_items = [
            {"id": 1, "shoot_id": "shoot_beach", "outfit_id": "bikini_red"},
        ]
        content_metadata = {
            "shoots": {
                "shoot_beach": {"outfit_id": "bikini_red"},
            }
        }

        result = validator.validate_drip_outfit_consistency(
            drip_items, content_metadata
        )

        assert result["is_valid"] is True

    def test_empty_string_ids(
        self,
        validator: DripOutfitValidator,
    ) -> None:
        """Test handling of empty string IDs."""
        drip_items = [
            {"id": 1, "shoot_id": "", "outfit_id": "O1"},
        ]
        content_metadata = {
            "shoots": {
                "": {"outfit_id": "O1"},
            }
        }

        result = validator.validate_drip_outfit_consistency(
            drip_items, content_metadata
        )

        # Empty string is still a valid key
        assert result["is_valid"] is True
        assert result["shoots_checked"] == 1


class TestIntegration:
    """Integration tests for drip outfit validation."""

    def test_full_validation_workflow(self) -> None:
        """Test complete validation workflow from schedule to result."""
        # Simulate a real schedule with mixed content
        schedule = [
            # Monday - drip campaign starts
            {"id": 1, "send_type_key": "bump_drip", "shoot_id": "beach_2024", "outfit_id": "red_bikini", "day": "Monday"},
            {"id": 2, "send_type_key": "ppv_unlock", "shoot_id": "beach_2024", "outfit_id": "blue_dress", "day": "Monday"},
            # Tuesday - drip continues
            {"id": 3, "send_type_key": "drip_set", "shoot_id": "beach_2024", "outfit_id": "red_bikini", "day": "Tuesday"},
            {"id": 4, "send_type_key": "bump_normal", "shoot_id": "beach_2024", "outfit_id": "red_bikini", "day": "Tuesday"},
            # Wednesday - new shoot
            {"id": 5, "send_type_key": "bump_drip", "shoot_id": "bedroom_2024", "outfit_id": "lace_set", "day": "Wednesday"},
            {"id": 6, "send_type_key": "tip_goal", "shoot_id": "bedroom_2024", "outfit_id": "casual", "day": "Wednesday"},
        ]

        content_metadata = {
            "shoots": {
                "beach_2024": {"outfit_id": "red_bikini", "location": "Miami Beach"},
                "bedroom_2024": {"outfit_id": "lace_set", "location": "Studio"},
            }
        }

        result = validate_drip_schedule_outfits(schedule, content_metadata)

        assert result["is_valid"] is True
        assert result["total_drip_items"] == 4  # 2 bump_drip + 1 drip_set + 1 bump_normal
        assert result["shoots_checked"] == 2
        assert len(result["inconsistencies"]) == 0

    def test_validation_catches_accidental_outfit_swap(self) -> None:
        """Test that validation catches when outfits are accidentally swapped."""
        schedule = [
            {"id": 1, "send_type_key": "bump_drip", "shoot_id": "S1", "outfit_id": "outfit_A"},
            {"id": 2, "send_type_key": "drip_set", "shoot_id": "S1", "outfit_id": "outfit_B"},  # Swapped!
            {"id": 3, "send_type_key": "bump_drip", "shoot_id": "S2", "outfit_id": "outfit_B"},
            {"id": 4, "send_type_key": "drip_set", "shoot_id": "S2", "outfit_id": "outfit_A"},  # Swapped!
        ]

        content_metadata = {
            "shoots": {
                "S1": {"outfit_id": "outfit_A"},
                "S2": {"outfit_id": "outfit_B"},
            }
        }

        result = validate_drip_schedule_outfits(schedule, content_metadata)

        assert result["is_valid"] is False
        errors = [i for i in result["inconsistencies"] if i["severity"] == "ERROR"]
        assert len(errors) == 2  # Both swapped items detected

        # Check recommendation mentions the issues
        assert result["recommendation"] is not None
        assert "2 outfit mismatch(es)" in result["recommendation"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
