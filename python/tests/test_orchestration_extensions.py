"""
Extended unit tests for EROS orchestration modules.

Tests additional orchestration components including:
- Drip set coordinator
- Label manager
- Weekly limits validator
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.orchestration.drip_coordinator import (
    DripWindow,
    DripSetCoordinator,
)
from python.orchestration.label_manager import (
    SEND_TYPE_LABELS,
    AVAILABLE_LABELS,
    assign_label,
    apply_labels_to_schedule,
    get_label_summary,
    get_available_labels,
    get_send_types_for_label,
)
from python.orchestration.weekly_limits import (
    WEEKLY_LIMITS,
    validate_weekly_limits,
    enforce_weekly_limits,
    get_weekly_limits,
    get_limited_send_types,
    get_limit_for_send_type,
    is_limited_send_type,
    count_limited_send_types,
    get_limit_rationale,
)


# =============================================================================
# Drip Window Tests
# =============================================================================


class TestDripWindow:
    """Test DripWindow dataclass."""

    def test_drip_window_immutable(self):
        """Test DripWindow is frozen (immutable)."""
        window = DripWindow(
            start_hour=14,
            end_hour=18,
            outfit_id="outfit_123",
            allowed_types=("bump_normal", "bump_descriptive"),
            blocked_types=("ppv_unlock",),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            window.start_hour = 15

    def test_drip_window_tuples_for_types(self):
        """Test DripWindow uses tuples for type lists."""
        window = DripWindow(
            start_hour=14,
            end_hour=18,
            outfit_id="outfit_123",
            allowed_types=("bump_normal",),
            blocked_types=("ppv_unlock", "ppv_wall"),
        )

        assert isinstance(window.allowed_types, tuple)
        assert isinstance(window.blocked_types, tuple)


class TestDripSetCoordinator:
    """Test DripSetCoordinator class."""

    @pytest.fixture
    def coordinator(self) -> DripSetCoordinator:
        """Create coordinator for testing."""
        return DripSetCoordinator("test_creator")

    def test_init_sets_creator_id(self, coordinator):
        """Test init stores creator_id."""
        assert coordinator.creator_id == "test_creator"

    def test_plan_drip_window_returns_window(self, coordinator):
        """Test plan_drip_window returns DripWindow."""
        schedule = []
        window = coordinator.plan_drip_window(schedule)

        assert isinstance(window, DripWindow)
        assert window.start_hour >= 0
        assert window.end_hour <= 24
        assert window.end_hour > window.start_hour

    def test_plan_drip_window_respects_preferred_start(self, coordinator):
        """Test plan_drip_window uses preferred start hour."""
        window = coordinator.plan_drip_window([], preferred_start_hour=16)

        assert window.start_hour == 16

    def test_plan_drip_window_duration_4_to_8_hours(self, coordinator):
        """Test drip window duration is between 4-8 hours."""
        for _ in range(20):  # Test multiple times due to randomization
            window = coordinator.plan_drip_window([])
            duration = window.end_hour - window.start_hour
            assert 4 <= duration <= 8

    def test_plan_drip_window_does_not_exceed_midnight(self, coordinator):
        """Test drip window doesn't go past 24:00."""
        window = coordinator.plan_drip_window([], preferred_start_hour=22)

        assert window.end_hour <= 24

    def test_allowed_types_constant(self, coordinator):
        """Test ALLOWED_DURING_DRIP contains expected types."""
        allowed = coordinator.ALLOWED_DURING_DRIP

        assert "bump_normal" in allowed
        assert "bump_descriptive" in allowed
        assert "dm_farm" in allowed
        assert "ppv_unlock" not in allowed

    def test_blocked_types_constant(self, coordinator):
        """Test BLOCKED_DURING_DRIP contains expected types."""
        blocked = coordinator.BLOCKED_DURING_DRIP

        assert "ppv_unlock" in blocked
        assert "ppv_wall" in blocked
        assert "bundle" in blocked
        assert "renew_on_message" in blocked
        assert "bump_normal" not in blocked

    def test_validate_drip_window_valid_schedule(self, coordinator):
        """Test validation passes for valid schedule."""
        window = DripWindow(
            start_hour=14,
            end_hour=18,
            outfit_id="outfit_123",
            allowed_types=coordinator.ALLOWED_DURING_DRIP,
            blocked_types=coordinator.BLOCKED_DURING_DRIP,
        )

        # Only engagement types during drip window
        schedule = [
            {"send_type": "bump_normal", "hour": 14},
            {"send_type": "bump_normal", "hour": 15},
            {"send_type": "dm_farm", "hour": 16},
            {"send_type": "ppv_unlock", "hour": 19},  # Outside window
        ]

        result = coordinator.validate_drip_window(schedule, window)

        assert result["is_valid"] is True
        assert "violations" not in result or len(result.get("violations", [])) == 0

    def test_validate_drip_window_detects_violations(self, coordinator):
        """Test validation detects PPV during drip window."""
        window = DripWindow(
            start_hour=14,
            end_hour=18,
            outfit_id="outfit_123",
            allowed_types=coordinator.ALLOWED_DURING_DRIP,
            blocked_types=coordinator.BLOCKED_DURING_DRIP,
        )

        # PPV during drip window - violation
        schedule = [
            {"send_type": "bump_normal", "hour": 14},
            {"send_type": "ppv_unlock", "hour": 15},  # VIOLATION
            {"send_type": "bundle", "hour": 16},  # VIOLATION
        ]

        result = coordinator.validate_drip_window(schedule, window)

        assert result["is_valid"] is False
        assert len(result["violations"]) == 2

    def test_extract_hour_from_hour_field(self, coordinator):
        """Test _extract_hour handles 'hour' field."""
        item = {"hour": 14}
        assert coordinator._extract_hour(item) == 14

    def test_extract_hour_from_scheduled_time_hhmm(self, coordinator):
        """Test _extract_hour handles HH:MM format."""
        item = {"scheduled_time": "14:30:00"}
        assert coordinator._extract_hour(item) == 14

    def test_extract_hour_from_scheduled_time_iso(self, coordinator):
        """Test _extract_hour handles ISO format."""
        item = {"scheduled_time": "2025-01-15T14:30:00"}
        assert coordinator._extract_hour(item) == 14

    def test_extract_hour_missing_fields_returns_0(self, coordinator):
        """Test _extract_hour returns 0 when no time field found."""
        item = {"send_type": "ppv_unlock"}
        assert coordinator._extract_hour(item) == 0

    def test_generate_drip_bumps_creates_bumps(self, coordinator):
        """Test generate_drip_bumps creates bump schedule."""
        window = DripWindow(
            start_hour=14,
            end_hour=18,
            outfit_id="outfit_123",
            allowed_types=coordinator.ALLOWED_DURING_DRIP,
            blocked_types=coordinator.BLOCKED_DURING_DRIP,
        )

        bumps = coordinator.generate_drip_bumps(window)

        assert len(bumps) > 0
        for bump in bumps:
            assert bump["send_type"] == "bump_drip"
            assert bump["outfit_id"] == "outfit_123"
            assert bump["drip_window"] is True

    def test_validate_ppv_followup_allowed_during_drip(self, coordinator):
        """Test ppv_followup is allowed during drip (doesn't break immersion)."""
        window = DripWindow(
            start_hour=14,
            end_hour=18,
            outfit_id="outfit_123",
            allowed_types=coordinator.ALLOWED_DURING_DRIP,
            blocked_types=coordinator.BLOCKED_DURING_DRIP,
        )

        schedule = [
            {"send_type": "ppv_followup", "hour": 15},  # Should be allowed
        ]

        result = coordinator.validate_drip_window(schedule, window)

        # ppv_followup is in ALLOWED_PPV_DURING_DRIP
        assert result["is_valid"] is True


# =============================================================================
# Label Manager Tests
# =============================================================================


class TestLabelManagerConstants:
    """Test label manager constants."""

    def test_available_labels_count(self):
        """Test correct number of available labels."""
        assert len(AVAILABLE_LABELS) == 7

    def test_all_labels_in_tuple(self):
        """Test expected labels exist."""
        expected = ["GAMES", "BUNDLES", "FIRST TO TIP", "PPV", "RENEW ON", "RETENTION", "VIP"]
        for label in expected:
            assert label in AVAILABLE_LABELS

    def test_send_type_labels_mapping(self):
        """Test key send type mappings."""
        assert SEND_TYPE_LABELS["game_post"] == "GAMES"
        assert SEND_TYPE_LABELS["bundle"] == "BUNDLES"
        assert SEND_TYPE_LABELS["ppv_unlock"] == "PPV"
        assert SEND_TYPE_LABELS["vip_program"] == "VIP"


class TestAssignLabel:
    """Test assign_label function."""

    def test_assign_label_game_post(self):
        """Test game_post gets GAMES label."""
        item = {"send_type": "game_post", "time": "10:00"}
        assert assign_label(item) == "GAMES"

    def test_assign_label_ppv(self):
        """Test PPV types get PPV label."""
        assert assign_label({"send_type": "ppv_unlock"}) == "PPV"
        assert assign_label({"send_type": "ppv_wall"}) == "PPV"

    def test_assign_label_vip(self):
        """Test VIP types get VIP label."""
        assert assign_label({"send_type": "vip_program"}) == "VIP"
        assert assign_label({"send_type": "snapchat_bundle"}) == "VIP"

    def test_assign_label_unlabeled_type(self):
        """Test unlabeled type returns None."""
        assert assign_label({"send_type": "bump_normal"}) is None
        assert assign_label({"send_type": "dm_farm"}) is None

    def test_assign_label_missing_send_type(self):
        """Test missing send_type returns None."""
        assert assign_label({}) is None
        assert assign_label({"time": "10:00"}) is None

    def test_assign_label_non_string_send_type(self):
        """Test non-string send_type is converted."""
        # Edge case: numeric send_type (shouldn't happen but handle gracefully)
        item = {"send_type": 123}
        result = assign_label(item)
        # Should not raise, returns None since "123" is not in mapping
        assert result is None


class TestApplyLabelsToSchedule:
    """Test apply_labels_to_schedule function."""

    def test_apply_labels_adds_label_key(self):
        """Test function adds 'label' key to items."""
        schedule = [
            {"send_type": "game_post", "time": "10:00"},
            {"send_type": "ppv_unlock", "time": "14:00"},
        ]

        result = apply_labels_to_schedule(schedule)

        assert result[0]["label"] == "GAMES"
        assert result[1]["label"] == "PPV"

    def test_apply_labels_modifies_in_place(self):
        """Test function modifies schedule in place."""
        schedule = [{"send_type": "bundle"}]
        result = apply_labels_to_schedule(schedule)

        assert result is schedule
        assert schedule[0]["label"] == "BUNDLES"

    def test_apply_labels_sets_none_for_unlabeled(self):
        """Test unlabeled types get label=None."""
        schedule = [{"send_type": "bump_normal"}]
        result = apply_labels_to_schedule(schedule)

        assert result[0]["label"] is None

    def test_apply_labels_empty_schedule(self):
        """Test empty schedule returns empty list."""
        assert apply_labels_to_schedule([]) == []


class TestGetLabelSummary:
    """Test get_label_summary function."""

    def test_summary_counts_labels(self):
        """Test summary counts each label correctly."""
        schedule = [
            {"send_type": "game_post", "label": "GAMES"},
            {"send_type": "ppv_unlock", "label": "PPV"},
            {"send_type": "ppv_wall", "label": "PPV"},
        ]

        summary = get_label_summary(schedule)

        assert summary["GAMES"] == 1
        assert summary["PPV"] == 2

    def test_summary_counts_unlabeled(self):
        """Test UNLABELED is counted."""
        schedule = [
            {"send_type": "bump_normal", "label": None},
            {"send_type": "dm_farm"},  # No label key
        ]

        summary = get_label_summary(schedule)

        assert summary["UNLABELED"] == 2

    def test_summary_empty_schedule(self):
        """Test empty schedule returns empty dict."""
        assert get_label_summary([]) == {}


class TestGetAvailableLabels:
    """Test get_available_labels function."""

    def test_returns_list(self):
        """Test returns a list."""
        labels = get_available_labels()
        assert isinstance(labels, list)

    def test_contains_all_labels(self):
        """Test contains all expected labels."""
        labels = get_available_labels()
        assert len(labels) == 7
        assert "GAMES" in labels
        assert "PPV" in labels


class TestGetSendTypesForLabel:
    """Test get_send_types_for_label function."""

    def test_games_label_types(self):
        """Test GAMES label returns game types."""
        types = get_send_types_for_label("GAMES")
        assert "game_post" in types
        assert "spin_the_wheel" in types

    def test_ppv_label_types(self):
        """Test PPV label returns PPV types."""
        types = get_send_types_for_label("PPV")
        assert "ppv_unlock" in types
        assert "ppv_wall" in types

    def test_invalid_label_returns_empty(self):
        """Test invalid label returns empty list."""
        types = get_send_types_for_label("INVALID")
        assert types == []


# =============================================================================
# Weekly Limits Tests
# =============================================================================


class TestWeeklyLimitsConstants:
    """Test weekly limits constants."""

    def test_vip_program_limit(self):
        """Test VIP program limit is 1."""
        assert WEEKLY_LIMITS["vip_program"] == 1

    def test_snapchat_bundle_limit(self):
        """Test Snapchat bundle limit is 1."""
        assert WEEKLY_LIMITS["snapchat_bundle"] == 1

    def test_ppv_unlock_not_limited(self):
        """Test ppv_unlock has no weekly limit."""
        assert "ppv_unlock" not in WEEKLY_LIMITS


class TestValidateWeeklyLimits:
    """Test validate_weekly_limits function."""

    def test_valid_schedule_passes(self):
        """Test schedule within limits passes."""
        schedule = [
            {"send_type": "vip_program", "scheduled_date": "2025-01-13"},
            {"send_type": "ppv_unlock", "scheduled_date": "2025-01-14"},
            {"send_type": "ppv_unlock", "scheduled_date": "2025-01-15"},
        ]

        result = validate_weekly_limits(schedule)

        assert result["is_valid"] is True
        assert len(result["violations"]) == 0

    def test_vip_violation_detected(self):
        """Test VIP program violation is detected."""
        schedule = [
            {"send_type": "vip_program", "scheduled_date": "2025-01-13"},
            {"send_type": "vip_program", "scheduled_date": "2025-01-15"},
        ]

        result = validate_weekly_limits(schedule)

        assert result["is_valid"] is False
        assert len(result["violations"]) == 1
        assert result["violations"][0]["send_type"] == "vip_program"
        assert result["violations"][0]["excess_count"] == 1

    def test_snapchat_violation_detected(self):
        """Test Snapchat bundle violation is detected."""
        schedule = [
            {"send_type": "snapchat_bundle"},
            {"send_type": "snapchat_bundle"},
            {"send_type": "snapchat_bundle"},
        ]

        result = validate_weekly_limits(schedule)

        assert result["is_valid"] is False
        violation = result["violations"][0]
        assert violation["send_type"] == "snapchat_bundle"
        assert violation["excess_count"] == 2

    def test_empty_schedule_valid(self):
        """Test empty schedule is valid."""
        result = validate_weekly_limits([])

        assert result["is_valid"] is True
        assert result["total_items_checked"] == 0

    def test_custom_limits_override(self):
        """Test custom limits override defaults."""
        schedule = [
            {"send_type": "vip_program"},
            {"send_type": "vip_program"},
        ]

        # Custom limit of 2 should pass
        result = validate_weekly_limits(schedule, limits={"vip_program": 2})
        assert result["is_valid"] is True

    def test_warnings_at_limit(self):
        """Test warnings generated when at limit."""
        schedule = [{"send_type": "vip_program"}]

        result = validate_weekly_limits(schedule)

        assert result["is_valid"] is True
        # Should have an info warning
        assert len(result["warnings"]) > 0
        assert result["warnings"][0]["severity"] == "info"

    def test_send_type_counts_populated(self):
        """Test send_type_counts is populated correctly."""
        schedule = [
            {"send_type": "ppv_unlock"},
            {"send_type": "ppv_unlock"},
            {"send_type": "vip_program"},
        ]

        result = validate_weekly_limits(schedule)

        assert result["send_type_counts"]["ppv_unlock"] == 2
        assert result["send_type_counts"]["vip_program"] == 1

    def test_limited_types_found_populated(self):
        """Test limited_types_found lists limited types present."""
        schedule = [
            {"send_type": "vip_program"},
            {"send_type": "ppv_unlock"},
        ]

        result = validate_weekly_limits(schedule)

        assert "vip_program" in result["limited_types_found"]
        assert "ppv_unlock" not in result["limited_types_found"]


class TestEnforceWeeklyLimits:
    """Test enforce_weekly_limits function."""

    def test_removes_excess_items(self):
        """Test excess items are removed."""
        schedule = [
            {"send_type": "vip_program", "id": 1},
            {"send_type": "ppv_unlock", "id": 2},
            {"send_type": "vip_program", "id": 3},
            {"send_type": "vip_program", "id": 4},
        ]

        result = enforce_weekly_limits(schedule)

        assert result["modified"] is True
        assert result["removed_count"] == 2
        assert len(schedule) == 2
        # First vip_program should be kept
        assert schedule[0]["id"] == 1
        # ppv_unlock should be kept
        assert schedule[1]["id"] == 2

    def test_no_modification_when_valid(self):
        """Test no modification when within limits."""
        schedule = [
            {"send_type": "vip_program", "id": 1},
            {"send_type": "ppv_unlock", "id": 2},
        ]

        result = enforce_weekly_limits(schedule)

        assert result["modified"] is False
        assert result["removed_count"] == 0
        assert len(schedule) == 2

    def test_removed_items_tracked(self):
        """Test removed items are tracked in result."""
        schedule = [
            {"send_type": "vip_program", "id": 1},
            {"send_type": "vip_program", "id": 2},
        ]

        result = enforce_weekly_limits(schedule)

        assert len(result["removed_items"]) == 1
        removed = result["removed_items"][0]
        assert removed["send_type"] == "vip_program"
        assert removed["index"] == 1  # Second item removed


class TestWeeklyLimitsHelpers:
    """Test weekly limits helper functions."""

    def test_get_weekly_limits_returns_copy(self):
        """Test get_weekly_limits returns a copy."""
        limits1 = get_weekly_limits()
        limits1["test"] = 99

        limits2 = get_weekly_limits()
        assert "test" not in limits2

    def test_get_limited_send_types(self):
        """Test get_limited_send_types returns list."""
        types = get_limited_send_types()

        assert "vip_program" in types
        assert "snapchat_bundle" in types

    def test_get_limit_for_send_type_exists(self):
        """Test get_limit_for_send_type returns limit."""
        assert get_limit_for_send_type("vip_program") == 1

    def test_get_limit_for_send_type_not_exists(self):
        """Test get_limit_for_send_type returns None."""
        assert get_limit_for_send_type("ppv_unlock") is None

    def test_is_limited_send_type_true(self):
        """Test is_limited_send_type returns True."""
        assert is_limited_send_type("vip_program") is True

    def test_is_limited_send_type_false(self):
        """Test is_limited_send_type returns False."""
        assert is_limited_send_type("ppv_unlock") is False

    def test_count_limited_send_types(self):
        """Test count_limited_send_types filters correctly."""
        schedule = [
            {"send_type": "vip_program"},
            {"send_type": "ppv_unlock"},
            {"send_type": "vip_program"},
        ]

        counts = count_limited_send_types(schedule)

        assert counts == {"vip_program": 2}
        assert "ppv_unlock" not in counts

    def test_get_limit_rationale_exists(self):
        """Test get_limit_rationale returns rationale."""
        rationale = get_limit_rationale("vip_program")

        assert "exclusivity" in rationale.lower()

    def test_get_limit_rationale_not_exists(self):
        """Test get_limit_rationale returns default."""
        rationale = get_limit_rationale("ppv_unlock")

        assert "no weekly limit" in rationale.lower()
