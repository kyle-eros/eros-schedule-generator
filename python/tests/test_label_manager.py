"""
Unit tests for EROS Label Manager.

Tests label assignment, schedule labeling, and label summary functionality
for campaign feed organization per Gap 10.10 requirements.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.orchestration.label_manager import (
    AVAILABLE_LABELS,
    SEND_TYPE_LABELS,
    apply_labels_to_schedule,
    assign_label,
    get_available_labels,
    get_label_summary,
    get_send_types_for_label,
)


# =============================================================================
# Test Constants: SEND_TYPE_LABELS
# =============================================================================


class TestSendTypeLabelsConstant:
    """Tests for the SEND_TYPE_LABELS constant mapping."""

    def test_send_type_labels_is_dict(self) -> None:
        """Test SEND_TYPE_LABELS is a dictionary."""
        assert isinstance(SEND_TYPE_LABELS, dict)

    def test_send_type_labels_not_empty(self) -> None:
        """Test SEND_TYPE_LABELS contains entries."""
        assert len(SEND_TYPE_LABELS) > 0

    def test_all_keys_are_strings(self) -> None:
        """Test all keys in SEND_TYPE_LABELS are strings."""
        for key in SEND_TYPE_LABELS.keys():
            assert isinstance(key, str), f"Key {key!r} is not a string"

    def test_all_values_are_strings(self) -> None:
        """Test all values in SEND_TYPE_LABELS are strings."""
        for key, value in SEND_TYPE_LABELS.items():
            assert isinstance(value, str), f"Value for {key!r} is not a string"

    def test_all_values_in_available_labels(self) -> None:
        """Test all label values are in AVAILABLE_LABELS."""
        for key, value in SEND_TYPE_LABELS.items():
            assert value in AVAILABLE_LABELS, (
                f"Label {value!r} for {key!r} not in AVAILABLE_LABELS"
            )


# Expected mappings for GAMES label
GAMES_SEND_TYPES = [
    ("game_post", "GAMES"),
    ("game_wheel", "GAMES"),
    ("spin_the_wheel", "GAMES"),
    ("card_game", "GAMES"),
    ("prize_wheel", "GAMES"),
    ("mystery_box", "GAMES"),
    ("scratch_off", "GAMES"),
]


@pytest.mark.parametrize("send_type,expected_label", GAMES_SEND_TYPES)
def test_games_label_mappings(send_type: str, expected_label: str) -> None:
    """Test GAMES label mappings for game-based send types.

    Args:
        send_type: The send type key to check.
        expected_label: The expected label value.
    """
    assert SEND_TYPE_LABELS.get(send_type) == expected_label


# Expected mappings for BUNDLES label
BUNDLES_SEND_TYPES = [
    ("bundle", "BUNDLES"),
    ("bundle_wall", "BUNDLES"),
    ("ppv_bundle", "BUNDLES"),
]


@pytest.mark.parametrize("send_type,expected_label", BUNDLES_SEND_TYPES)
def test_bundles_label_mappings(send_type: str, expected_label: str) -> None:
    """Test BUNDLES label mappings for bundle offerings.

    Args:
        send_type: The send type key to check.
        expected_label: The expected label value.
    """
    assert SEND_TYPE_LABELS.get(send_type) == expected_label


# Expected mappings for PPV label
PPV_SEND_TYPES = [
    ("ppv", "PPV"),
    ("ppv_unlock", "PPV"),
    ("ppv_wall", "PPV"),
    ("ppv_winner", "PPV"),
    ("ppv_solo", "PPV"),
    ("ppv_sextape", "PPV"),
]


@pytest.mark.parametrize("send_type,expected_label", PPV_SEND_TYPES)
def test_ppv_label_mappings(send_type: str, expected_label: str) -> None:
    """Test PPV label mappings for pay-per-view send types.

    Args:
        send_type: The send type key to check.
        expected_label: The expected label value.
    """
    assert SEND_TYPE_LABELS.get(send_type) == expected_label


# Expected mappings for VIP label
VIP_SEND_TYPES = [
    ("vip_program", "VIP"),
    ("snapchat_bundle", "VIP"),
]


@pytest.mark.parametrize("send_type,expected_label", VIP_SEND_TYPES)
def test_vip_label_mappings(send_type: str, expected_label: str) -> None:
    """Test VIP label mappings for premium program sends.

    Args:
        send_type: The send type key to check.
        expected_label: The expected label value.
    """
    assert SEND_TYPE_LABELS.get(send_type) == expected_label


# Expected mappings for single-send-type labels
SINGLE_SEND_TYPE_LABELS = [
    ("first_to_tip", "FIRST TO TIP"),
    ("renew_on", "RENEW ON"),
    ("expired_winback", "RETENTION"),
]


@pytest.mark.parametrize("send_type,expected_label", SINGLE_SEND_TYPE_LABELS)
def test_single_send_type_label_mappings(
    send_type: str, expected_label: str
) -> None:
    """Test label mappings for send types with unique labels.

    Args:
        send_type: The send type key to check.
        expected_label: The expected label value.
    """
    assert SEND_TYPE_LABELS.get(send_type) == expected_label


# =============================================================================
# Test Constants: AVAILABLE_LABELS
# =============================================================================


class TestAvailableLabelsConstant:
    """Tests for the AVAILABLE_LABELS constant."""

    def test_available_labels_is_tuple(self) -> None:
        """Test AVAILABLE_LABELS is a tuple (immutable)."""
        assert isinstance(AVAILABLE_LABELS, tuple)

    def test_available_labels_count(self) -> None:
        """Test AVAILABLE_LABELS contains expected number of labels."""
        assert len(AVAILABLE_LABELS) == 7

    def test_available_labels_contains_games(self) -> None:
        """Test AVAILABLE_LABELS contains GAMES."""
        assert "GAMES" in AVAILABLE_LABELS

    def test_available_labels_contains_bundles(self) -> None:
        """Test AVAILABLE_LABELS contains BUNDLES."""
        assert "BUNDLES" in AVAILABLE_LABELS

    def test_available_labels_contains_first_to_tip(self) -> None:
        """Test AVAILABLE_LABELS contains FIRST TO TIP."""
        assert "FIRST TO TIP" in AVAILABLE_LABELS

    def test_available_labels_contains_ppv(self) -> None:
        """Test AVAILABLE_LABELS contains PPV."""
        assert "PPV" in AVAILABLE_LABELS

    def test_available_labels_contains_renew_on(self) -> None:
        """Test AVAILABLE_LABELS contains RENEW ON."""
        assert "RENEW ON" in AVAILABLE_LABELS

    def test_available_labels_contains_retention(self) -> None:
        """Test AVAILABLE_LABELS contains RETENTION."""
        assert "RETENTION" in AVAILABLE_LABELS

    def test_available_labels_contains_vip(self) -> None:
        """Test AVAILABLE_LABELS contains VIP."""
        assert "VIP" in AVAILABLE_LABELS

    def test_no_duplicate_labels(self) -> None:
        """Test AVAILABLE_LABELS has no duplicates."""
        assert len(AVAILABLE_LABELS) == len(set(AVAILABLE_LABELS))


# =============================================================================
# Test assign_label()
# =============================================================================


class TestAssignLabel:
    """Tests for the assign_label() function."""

    def test_returns_label_for_known_send_type(self) -> None:
        """Test returns correct label for known send type."""
        item = {"send_type": "game_post"}
        result = assign_label(item)
        assert result == "GAMES"

    def test_returns_none_for_unknown_send_type(self) -> None:
        """Test returns None for unknown send type."""
        item = {"send_type": "bump_normal"}
        result = assign_label(item)
        assert result is None

    def test_returns_none_for_missing_send_type_key(self) -> None:
        """Test returns None when send_type key is missing."""
        item = {"time": "10:00", "channel": "mass_message"}
        result = assign_label(item)
        assert result is None

    def test_returns_none_for_empty_dict(self) -> None:
        """Test returns None for empty dictionary."""
        item: dict[str, Any] = {}
        result = assign_label(item)
        assert result is None

    def test_returns_none_for_none_send_type_value(self) -> None:
        """Test returns None when send_type value is None."""
        item = {"send_type": None}
        result = assign_label(item)
        assert result is None

    def test_handles_non_string_send_type(self) -> None:
        """Test handles non-string send_type by converting to string."""
        # Note: This tests the defensive str() conversion in the code
        item = {"send_type": 123}  # Not a string
        result = assign_label(item)
        # Should return None since "123" is not in SEND_TYPE_LABELS
        assert result is None

    def test_preserves_original_item(self) -> None:
        """Test assign_label does not modify the original item."""
        item = {"send_type": "game_post", "time": "10:00"}
        original_keys = set(item.keys())
        assign_label(item)
        assert set(item.keys()) == original_keys


# Parametrized tests for all send types in SEND_TYPE_LABELS
ALL_SEND_TYPE_MAPPINGS = list(SEND_TYPE_LABELS.items())


@pytest.mark.parametrize("send_type,expected_label", ALL_SEND_TYPE_MAPPINGS)
def test_assign_label_returns_correct_label_for_all_types(
    send_type: str, expected_label: str
) -> None:
    """Test assign_label returns correct label for every mapped send type.

    Args:
        send_type: The send type key to test.
        expected_label: The expected label to be returned.
    """
    item = {"send_type": send_type}
    result = assign_label(item)
    assert result == expected_label


# Send types that should return None (not in SEND_TYPE_LABELS)
UNLABELED_SEND_TYPES = [
    "bump_normal",
    "bump_descriptive",
    "bump_text_only",
    "bump_flyer",
    "link_drop",
    "wall_link_drop",
    "dm_farm",
    "like_farm",
    "live_promo",
    "ppv_followup",
    "renew_on_post",
    "renew_on_message",
    "unknown_type",
    "",
]


@pytest.mark.parametrize("send_type", UNLABELED_SEND_TYPES)
def test_assign_label_returns_none_for_unlabeled_types(send_type: str) -> None:
    """Test assign_label returns None for send types not in the mapping.

    Args:
        send_type: The send type key expected to return None.
    """
    item = {"send_type": send_type}
    result = assign_label(item)
    assert result is None


# =============================================================================
# Test apply_labels_to_schedule()
# =============================================================================


class TestApplyLabelsToSchedule:
    """Tests for the apply_labels_to_schedule() function."""

    def test_adds_label_field_to_items(self) -> None:
        """Test adds 'label' key to each schedule item."""
        schedule = [
            {"send_type": "game_post", "time": "10:00"},
            {"send_type": "ppv_unlock", "time": "14:00"},
        ]
        result = apply_labels_to_schedule(schedule)
        for item in result:
            assert "label" in item

    def test_assigns_correct_labels(self) -> None:
        """Test assigns correct labels based on send_type."""
        schedule = [
            {"send_type": "game_post"},
            {"send_type": "ppv_unlock"},
            {"send_type": "vip_program"},
        ]
        result = apply_labels_to_schedule(schedule)
        assert result[0]["label"] == "GAMES"
        assert result[1]["label"] == "PPV"
        assert result[2]["label"] == "VIP"

    def test_assigns_none_for_unlabeled_types(self) -> None:
        """Test assigns None label for send types not in mapping."""
        schedule = [
            {"send_type": "bump_normal"},
            {"send_type": "dm_farm"},
        ]
        result = apply_labels_to_schedule(schedule)
        assert result[0]["label"] is None
        assert result[1]["label"] is None

    def test_handles_items_without_send_type(self) -> None:
        """Test handles items missing send_type key."""
        schedule = [
            {"time": "10:00", "channel": "mass_message"},
            {"caption_id": 123},
        ]
        result = apply_labels_to_schedule(schedule)
        assert result[0]["label"] is None
        assert result[1]["label"] is None

    def test_handles_empty_schedule(self) -> None:
        """Test handles empty schedule list."""
        schedule: list[dict[str, Any]] = []
        result = apply_labels_to_schedule(schedule)
        assert result == []

    def test_modifies_schedule_in_place(self) -> None:
        """Test modifies the original schedule in place."""
        schedule = [{"send_type": "game_post"}]
        result = apply_labels_to_schedule(schedule)
        assert result is schedule  # Same object
        assert schedule[0]["label"] == "GAMES"

    def test_preserves_existing_fields(self) -> None:
        """Test preserves all existing fields in items."""
        schedule = [
            {
                "send_type": "ppv_unlock",
                "time": "14:00",
                "channel": "mass_message",
                "caption_id": 42,
                "price": 15.00,
            }
        ]
        result = apply_labels_to_schedule(schedule)
        assert result[0]["time"] == "14:00"
        assert result[0]["channel"] == "mass_message"
        assert result[0]["caption_id"] == 42
        assert result[0]["price"] == 15.00
        assert result[0]["label"] == "PPV"

    def test_handles_mixed_labeled_and_unlabeled(self) -> None:
        """Test handles mix of labeled and unlabeled send types."""
        schedule = [
            {"send_type": "game_post"},
            {"send_type": "bump_normal"},
            {"send_type": "ppv_unlock"},
            {"send_type": "dm_farm"},
            {"send_type": "vip_program"},
        ]
        result = apply_labels_to_schedule(schedule)
        assert result[0]["label"] == "GAMES"
        assert result[1]["label"] is None
        assert result[2]["label"] == "PPV"
        assert result[3]["label"] is None
        assert result[4]["label"] == "VIP"

    def test_deep_copy_preserves_original(self) -> None:
        """Test deep copy can preserve original schedule."""
        original = [{"send_type": "game_post", "time": "10:00"}]
        schedule_copy = copy.deepcopy(original)
        apply_labels_to_schedule(schedule_copy)
        # Original should not have label key
        assert "label" not in original[0]
        # Copy should have label key
        assert schedule_copy[0]["label"] == "GAMES"


# =============================================================================
# Test get_label_summary()
# =============================================================================


class TestGetLabelSummary:
    """Tests for the get_label_summary() function."""

    def test_returns_dict(self) -> None:
        """Test returns a dictionary."""
        schedule = [{"label": "GAMES"}]
        result = get_label_summary(schedule)
        assert isinstance(result, dict)

    def test_counts_single_label(self) -> None:
        """Test counts single label correctly."""
        schedule = [
            {"label": "GAMES"},
            {"label": "GAMES"},
            {"label": "GAMES"},
        ]
        result = get_label_summary(schedule)
        assert result["GAMES"] == 3

    def test_counts_multiple_labels(self) -> None:
        """Test counts multiple different labels correctly."""
        schedule = [
            {"label": "GAMES"},
            {"label": "PPV"},
            {"label": "PPV"},
            {"label": "VIP"},
        ]
        result = get_label_summary(schedule)
        assert result["GAMES"] == 1
        assert result["PPV"] == 2
        assert result["VIP"] == 1

    def test_counts_none_as_unlabeled(self) -> None:
        """Test counts None labels as UNLABELED."""
        schedule = [
            {"label": None},
            {"label": None},
        ]
        result = get_label_summary(schedule)
        assert result["UNLABELED"] == 2

    def test_counts_missing_label_key_as_unlabeled(self) -> None:
        """Test counts missing label key as UNLABELED."""
        schedule = [
            {"send_type": "bump_normal"},  # No label key
            {"send_type": "dm_farm"},  # No label key
        ]
        result = get_label_summary(schedule)
        assert result["UNLABELED"] == 2

    def test_handles_empty_schedule(self) -> None:
        """Test returns empty dict for empty schedule."""
        schedule: list[dict[str, Any]] = []
        result = get_label_summary(schedule)
        assert result == {}

    def test_returns_regular_dict_not_counter(self) -> None:
        """Test returns regular dict, not Counter object."""
        schedule = [{"label": "GAMES"}]
        result = get_label_summary(schedule)
        assert type(result) is dict

    def test_mixed_labeled_and_unlabeled(self) -> None:
        """Test handles mix of labeled and unlabeled items."""
        schedule = [
            {"label": "GAMES"},
            {"label": "GAMES"},
            {"label": None},
            {"label": "PPV"},
            {"send_type": "bump"},  # No label key
        ]
        result = get_label_summary(schedule)
        assert result["GAMES"] == 2
        assert result["PPV"] == 1
        assert result["UNLABELED"] == 2

    def test_all_labels_represented(self) -> None:
        """Test summary includes all labels present in schedule."""
        schedule = [
            {"label": "GAMES"},
            {"label": "BUNDLES"},
            {"label": "FIRST TO TIP"},
            {"label": "PPV"},
            {"label": "RENEW ON"},
            {"label": "RETENTION"},
            {"label": "VIP"},
        ]
        result = get_label_summary(schedule)
        assert len(result) == 7
        for label in AVAILABLE_LABELS:
            assert result[label] == 1

    def test_only_includes_present_labels(self) -> None:
        """Test summary only includes labels that are present."""
        schedule = [
            {"label": "GAMES"},
            {"label": "PPV"},
        ]
        result = get_label_summary(schedule)
        assert "GAMES" in result
        assert "PPV" in result
        assert "BUNDLES" not in result
        assert "VIP" not in result


# =============================================================================
# Test get_available_labels()
# =============================================================================


class TestGetAvailableLabels:
    """Tests for the get_available_labels() function."""

    def test_returns_list(self) -> None:
        """Test returns a list."""
        result = get_available_labels()
        assert isinstance(result, list)

    def test_returns_seven_labels(self) -> None:
        """Test returns exactly 7 labels."""
        result = get_available_labels()
        assert len(result) == 7

    def test_contains_all_expected_labels(self) -> None:
        """Test contains all expected label strings."""
        result = get_available_labels()
        expected = ["GAMES", "BUNDLES", "FIRST TO TIP", "PPV", "RENEW ON", "RETENTION", "VIP"]
        for label in expected:
            assert label in result

    def test_returns_copy_not_reference(self) -> None:
        """Test returns a new list, not a reference to AVAILABLE_LABELS."""
        result = get_available_labels()
        # Modifying result should not affect AVAILABLE_LABELS
        result.append("NEW_LABEL")
        assert "NEW_LABEL" not in AVAILABLE_LABELS

    def test_matches_available_labels_constant(self) -> None:
        """Test returns same values as AVAILABLE_LABELS constant."""
        result = get_available_labels()
        assert set(result) == set(AVAILABLE_LABELS)


# =============================================================================
# Test get_send_types_for_label()
# =============================================================================


class TestGetSendTypesForLabel:
    """Tests for the get_send_types_for_label() function."""

    def test_returns_list(self) -> None:
        """Test returns a list."""
        result = get_send_types_for_label("GAMES")
        assert isinstance(result, list)

    def test_returns_empty_list_for_invalid_label(self) -> None:
        """Test returns empty list for non-existent label."""
        result = get_send_types_for_label("INVALID_LABEL")
        assert result == []

    def test_returns_empty_list_for_empty_string(self) -> None:
        """Test returns empty list for empty string label."""
        result = get_send_types_for_label("")
        assert result == []

    def test_games_label_returns_game_types(self) -> None:
        """Test GAMES label returns all game-related send types."""
        result = get_send_types_for_label("GAMES")
        assert "game_post" in result
        assert "spin_the_wheel" in result
        assert "mystery_box" in result

    def test_bundles_label_returns_bundle_types(self) -> None:
        """Test BUNDLES label returns all bundle-related send types."""
        result = get_send_types_for_label("BUNDLES")
        assert "bundle" in result
        assert "bundle_wall" in result
        assert "ppv_bundle" in result

    def test_ppv_label_returns_ppv_types(self) -> None:
        """Test PPV label returns all PPV-related send types."""
        result = get_send_types_for_label("PPV")
        assert "ppv" in result
        assert "ppv_unlock" in result
        assert "ppv_wall" in result

    def test_vip_label_returns_vip_types(self) -> None:
        """Test VIP label returns VIP and premium send types."""
        result = get_send_types_for_label("VIP")
        assert "vip_program" in result
        assert "snapchat_bundle" in result
        assert len(result) == 2

    def test_first_to_tip_returns_single_type(self) -> None:
        """Test FIRST TO TIP label returns only first_to_tip."""
        result = get_send_types_for_label("FIRST TO TIP")
        assert result == ["first_to_tip"]

    def test_renew_on_returns_single_type(self) -> None:
        """Test RENEW ON label returns only renew_on."""
        result = get_send_types_for_label("RENEW ON")
        assert result == ["renew_on"]

    def test_retention_returns_single_type(self) -> None:
        """Test RETENTION label returns only expired_winback."""
        result = get_send_types_for_label("RETENTION")
        assert result == ["expired_winback"]

    def test_case_sensitive(self) -> None:
        """Test label lookup is case sensitive."""
        result_upper = get_send_types_for_label("GAMES")
        result_lower = get_send_types_for_label("games")
        result_mixed = get_send_types_for_label("Games")

        assert len(result_upper) > 0
        assert result_lower == []
        assert result_mixed == []


# Parametrized test for each label
LABEL_EXPECTED_COUNTS = [
    ("GAMES", 7),  # game_post, game_wheel, spin_the_wheel, card_game, prize_wheel, mystery_box, scratch_off
    ("BUNDLES", 3),  # bundle, bundle_wall, ppv_bundle
    ("FIRST TO TIP", 1),  # first_to_tip
    ("PPV", 6),  # ppv, ppv_unlock, ppv_wall, ppv_winner, ppv_solo, ppv_sextape
    ("RENEW ON", 1),  # renew_on
    ("RETENTION", 1),  # expired_winback
    ("VIP", 2),  # vip_program, snapchat_bundle
]


@pytest.mark.parametrize("label,expected_count", LABEL_EXPECTED_COUNTS)
def test_get_send_types_for_label_count(label: str, expected_count: int) -> None:
    """Test get_send_types_for_label returns expected number of types.

    Args:
        label: The label to look up.
        expected_count: Expected number of send types for this label.
    """
    result = get_send_types_for_label(label)
    assert len(result) == expected_count


# =============================================================================
# Integration Tests
# =============================================================================


class TestLabelManagerIntegration:
    """Integration tests for label manager workflow."""

    def test_full_workflow_label_apply_and_summarize(self) -> None:
        """Test complete workflow: apply labels then get summary."""
        schedule = [
            {"send_type": "game_post", "time": "10:00"},
            {"send_type": "game_wheel", "time": "11:00"},
            {"send_type": "ppv_unlock", "time": "14:00"},
            {"send_type": "ppv_wall", "time": "15:00"},
            {"send_type": "bump_normal", "time": "16:00"},
            {"send_type": "vip_program", "time": "19:00"},
        ]

        # Apply labels
        labeled_schedule = apply_labels_to_schedule(schedule)

        # Get summary
        summary = get_label_summary(labeled_schedule)

        # Verify
        assert summary["GAMES"] == 2
        assert summary["PPV"] == 2
        assert summary["VIP"] == 1
        assert summary["UNLABELED"] == 1  # bump_normal

    def test_round_trip_label_to_send_types(self) -> None:
        """Test round trip: label -> send_types -> label."""
        for label in AVAILABLE_LABELS:
            send_types = get_send_types_for_label(label)
            for send_type in send_types:
                item = {"send_type": send_type}
                assigned_label = assign_label(item)
                assert assigned_label == label

    def test_all_send_types_covered_by_labels(self) -> None:
        """Test every send type in SEND_TYPE_LABELS has corresponding label lookup."""
        for send_type, expected_label in SEND_TYPE_LABELS.items():
            send_types_for_label = get_send_types_for_label(expected_label)
            assert send_type in send_types_for_label, (
                f"Send type {send_type!r} not found in get_send_types_for_label({expected_label!r})"
            )

    def test_available_labels_matches_used_labels(self) -> None:
        """Test all labels in SEND_TYPE_LABELS values are in AVAILABLE_LABELS."""
        used_labels = set(SEND_TYPE_LABELS.values())
        available = set(AVAILABLE_LABELS)
        assert used_labels == available


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestLabelManagerEdgeCases:
    """Edge case tests for label manager."""

    def test_assign_label_with_extra_fields(self) -> None:
        """Test assign_label ignores extra fields in item."""
        item = {
            "send_type": "game_post",
            "time": "10:00",
            "channel": "mass_message",
            "audience": "all",
            "nested": {"key": "value"},
            "list_field": [1, 2, 3],
        }
        result = assign_label(item)
        assert result == "GAMES"

    def test_apply_labels_large_schedule(self) -> None:
        """Test apply_labels handles large schedules efficiently."""
        schedule = [{"send_type": "game_post"} for _ in range(1000)]
        result = apply_labels_to_schedule(schedule)
        assert len(result) == 1000
        assert all(item["label"] == "GAMES" for item in result)

    def test_label_summary_all_same_label(self) -> None:
        """Test summary with all items having same label."""
        schedule = [{"label": "PPV"} for _ in range(50)]
        result = get_label_summary(schedule)
        assert result == {"PPV": 50}

    def test_label_summary_all_unlabeled(self) -> None:
        """Test summary with all items unlabeled."""
        schedule = [{"label": None} for _ in range(25)]
        result = get_label_summary(schedule)
        assert result == {"UNLABELED": 25}

    def test_send_type_with_whitespace(self) -> None:
        """Test send types with leading/trailing whitespace are not matched."""
        item = {"send_type": " game_post "}
        result = assign_label(item)
        # Should not match due to whitespace
        assert result is None

    def test_send_type_different_case(self) -> None:
        """Test send types are case-sensitive."""
        item_upper = {"send_type": "GAME_POST"}
        item_mixed = {"send_type": "Game_Post"}
        assert assign_label(item_upper) is None
        assert assign_label(item_mixed) is None
