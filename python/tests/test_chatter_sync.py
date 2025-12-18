"""
Unit tests for chatter content sync tool.

Tests cover:
- CHATTER_CHANNELS and CHATTER_SEND_TYPES constants
- ChatterContentSync.generate_chatter_content_manifest() functionality
- _is_chatter_relevant() filtering logic
- _generate_chatter_notes() content generation
- _generate_chatter_instructions() output
- export_chatter_manifest_json() file operations
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.orchestration.chatter_sync import (
    CHATTER_CHANNELS,
    CHATTER_SEND_TYPES,
    ChatterContentSync,
    export_chatter_manifest_json,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def chatter_sync() -> ChatterContentSync:
    """Fresh ChatterContentSync instance for testing."""
    return ChatterContentSync()


@pytest.fixture
def sample_schedule() -> list[dict[str, Any]]:
    """Sample schedule with mixed chatter and non-chatter items."""
    return [
        {
            "schedule_date": "2025-12-16",
            "send_type": "ppv_unlock",
            "channel": "mass_message",
            "content_id": "content_001",
            "content_type": "video",
            "caption_text": "Check your DMs for something special!",
            "price": 15.00,
            "audience_target": "all",
            "label": "Monday PPV",
        },
        {
            "schedule_date": "2025-12-16",
            "send_type": "bump_normal",
            "channel": "wall_post",
            "content_id": "content_002",
            "content_type": "picture",
            "caption_text": "New pics just dropped!",
            "price": None,
            "audience_target": "all",
            "label": "Wall Bump",
        },
        {
            "schedule_date": "2025-12-17",
            "send_type": "dm_farm",
            "channel": "targeted_message",
            "content_id": None,
            "content_type": None,
            "caption_text": "Hey, how are you?",
            "price": None,
            "audience_target": "engaged_fans",
            "label": "DM Outreach",
        },
        {
            "schedule_date": "2025-12-17",
            "send_type": "vip_program",
            "channel": "mass_message",
            "content_id": "content_003",
            "content_type": "bundle",
            "caption_text": "Join my VIP tier!",
            "price": 50.00,
            "audience_target": "high_spenders",
            "label": "VIP Campaign",
        },
        {
            "schedule_date": "2025-12-18",
            "send_type": "link_drop",
            "channel": "story",
            "content_id": None,
            "content_type": None,
            "caption_text": "Link in bio!",
            "price": None,
            "audience_target": "all",
            "label": "Story Link",
        },
    ]


@pytest.fixture
def chatter_only_schedule() -> list[dict[str, Any]]:
    """Schedule containing only chatter-relevant items."""
    return [
        {
            "schedule_date": "2025-12-16",
            "send_type": "ppv_unlock",
            "channel": "mass_message",
            "content_id": "content_001",
            "content_type": "video",
            "caption_text": "Exclusive content!",
            "price": 20.00,
            "audience_target": "all",
            "label": "PPV Send",
        },
        {
            "schedule_date": "2025-12-16",
            "send_type": "expired_winback",
            "channel": "targeted_message",
            "content_id": None,
            "content_type": None,
            "caption_text": "We miss you!",
            "price": None,
            "audience_target": "expired_subs",
            "label": "Winback",
        },
    ]


@pytest.fixture
def non_chatter_schedule() -> list[dict[str, Any]]:
    """Schedule containing no chatter-relevant items."""
    return [
        {
            "schedule_date": "2025-12-16",
            "send_type": "bump_normal",
            "channel": "wall_post",
            "content_id": "content_001",
            "content_type": "picture",
            "caption_text": "New wall post!",
            "price": None,
            "audience_target": "all",
            "label": "Wall Bump",
        },
        {
            "schedule_date": "2025-12-16",
            "send_type": "link_drop",
            "channel": "story",
            "content_id": None,
            "content_type": None,
            "caption_text": "Check my story!",
            "price": None,
            "audience_target": "all",
            "label": "Story Link",
        },
    ]


@pytest.fixture
def first_to_tip_schedule() -> list[dict[str, Any]]:
    """Schedule containing first_to_tip send type."""
    return [
        {
            "schedule_date": "2025-12-16",
            "send_type": "first_to_tip",
            "channel": "mass_message",
            "content_id": "content_001",
            "content_type": "video",
            "caption_text": "First to tip wins!",
            "price": 25.00,
            "audience_target": "all",
            "label": "FTT Contest",
        },
    ]


@pytest.fixture
def high_spender_schedule() -> list[dict[str, Any]]:
    """Schedule with high_spenders audience target."""
    return [
        {
            "schedule_date": "2025-12-16",
            "send_type": "ppv_unlock",
            "channel": "targeted_message",
            "content_id": "content_001",
            "content_type": "video",
            "caption_text": "Special offer for you!",
            "price": 30.00,
            "audience_target": "high_spenders",
            "label": "VIP PPV",
        },
    ]


@pytest.fixture
def empty_schedule() -> list[dict[str, Any]]:
    """Empty schedule for edge case testing."""
    return []


# =============================================================================
# Test Constants
# =============================================================================


class TestChatterChannelsConstant:
    """Tests for CHATTER_CHANNELS constant."""

    def test_chatter_channels_is_frozenset(self) -> None:
        """CHATTER_CHANNELS should be a frozenset for immutability."""
        assert isinstance(CHATTER_CHANNELS, frozenset)

    def test_chatter_channels_contains_mass_message(self) -> None:
        """CHATTER_CHANNELS should contain 'mass_message'."""
        assert "mass_message" in CHATTER_CHANNELS

    def test_chatter_channels_contains_targeted_message(self) -> None:
        """CHATTER_CHANNELS should contain 'targeted_message'."""
        assert "targeted_message" in CHATTER_CHANNELS

    def test_chatter_channels_has_exactly_two_items(self) -> None:
        """CHATTER_CHANNELS should have exactly 2 channels."""
        assert len(CHATTER_CHANNELS) == 2

    def test_chatter_channels_excludes_wall_post(self) -> None:
        """CHATTER_CHANNELS should not contain 'wall_post'."""
        assert "wall_post" not in CHATTER_CHANNELS

    def test_chatter_channels_excludes_story(self) -> None:
        """CHATTER_CHANNELS should not contain 'story'."""
        assert "story" not in CHATTER_CHANNELS

    def test_chatter_channels_excludes_live(self) -> None:
        """CHATTER_CHANNELS should not contain 'live'."""
        assert "live" not in CHATTER_CHANNELS


class TestChatterSendTypesConstant:
    """Tests for CHATTER_SEND_TYPES constant."""

    def test_chatter_send_types_is_frozenset(self) -> None:
        """CHATTER_SEND_TYPES should be a frozenset for immutability."""
        assert isinstance(CHATTER_SEND_TYPES, frozenset)

    def test_chatter_send_types_contains_dm_farm(self) -> None:
        """CHATTER_SEND_TYPES should contain 'dm_farm'."""
        assert "dm_farm" in CHATTER_SEND_TYPES

    def test_chatter_send_types_contains_ppv_unlock(self) -> None:
        """CHATTER_SEND_TYPES should contain 'ppv_unlock'."""
        assert "ppv_unlock" in CHATTER_SEND_TYPES

    def test_chatter_send_types_contains_expired_winback(self) -> None:
        """CHATTER_SEND_TYPES should contain 'expired_winback'."""
        assert "expired_winback" in CHATTER_SEND_TYPES

    def test_chatter_send_types_contains_vip_program(self) -> None:
        """CHATTER_SEND_TYPES should contain 'vip_program'."""
        assert "vip_program" in CHATTER_SEND_TYPES

    def test_chatter_send_types_contains_first_to_tip(self) -> None:
        """CHATTER_SEND_TYPES should contain 'first_to_tip'."""
        assert "first_to_tip" in CHATTER_SEND_TYPES

    def test_chatter_send_types_has_exactly_five_items(self) -> None:
        """CHATTER_SEND_TYPES should have exactly 5 send types."""
        assert len(CHATTER_SEND_TYPES) == 5

    def test_chatter_send_types_excludes_bump_normal(self) -> None:
        """CHATTER_SEND_TYPES should not contain 'bump_normal'."""
        assert "bump_normal" not in CHATTER_SEND_TYPES

    def test_chatter_send_types_excludes_link_drop(self) -> None:
        """CHATTER_SEND_TYPES should not contain 'link_drop'."""
        assert "link_drop" not in CHATTER_SEND_TYPES


# =============================================================================
# Test ChatterContentSync._is_chatter_relevant()
# =============================================================================


class TestIsChatterRelevant:
    """Tests for _is_chatter_relevant() filtering logic."""

    def test_mass_message_channel_is_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """mass_message channel should be chatter-relevant."""
        assert chatter_sync._is_chatter_relevant("bump_normal", "mass_message") is True

    def test_targeted_message_channel_is_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """targeted_message channel should be chatter-relevant."""
        assert (
            chatter_sync._is_chatter_relevant("bump_normal", "targeted_message") is True
        )

    def test_dm_farm_send_type_is_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """dm_farm send type should be chatter-relevant regardless of channel."""
        assert chatter_sync._is_chatter_relevant("dm_farm", "wall_post") is True

    def test_ppv_unlock_send_type_is_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """ppv_unlock send type should be chatter-relevant regardless of channel."""
        assert chatter_sync._is_chatter_relevant("ppv_unlock", "story") is True

    def test_expired_winback_send_type_is_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """expired_winback send type should be chatter-relevant."""
        assert chatter_sync._is_chatter_relevant("expired_winback", "wall_post") is True

    def test_vip_program_send_type_is_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """vip_program send type should be chatter-relevant."""
        assert chatter_sync._is_chatter_relevant("vip_program", "wall_post") is True

    def test_first_to_tip_send_type_is_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """first_to_tip send type should be chatter-relevant."""
        assert chatter_sync._is_chatter_relevant("first_to_tip", "live") is True

    def test_wall_post_bump_is_not_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """bump_normal on wall_post should not be chatter-relevant."""
        assert chatter_sync._is_chatter_relevant("bump_normal", "wall_post") is False

    def test_story_link_drop_is_not_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """link_drop on story should not be chatter-relevant."""
        assert chatter_sync._is_chatter_relevant("link_drop", "story") is False

    def test_empty_strings_not_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """Empty send_type and channel should not be chatter-relevant."""
        assert chatter_sync._is_chatter_relevant("", "") is False

    def test_none_like_strings_not_relevant(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """Unknown values should not be chatter-relevant."""
        assert chatter_sync._is_chatter_relevant("unknown_type", "unknown_channel") is False

    @pytest.mark.parametrize(
        "send_type,channel,expected",
        [
            ("ppv_unlock", "mass_message", True),
            ("ppv_unlock", "wall_post", True),  # ppv_unlock is always relevant
            ("dm_farm", "targeted_message", True),
            ("bump_normal", "mass_message", True),  # channel makes it relevant
            ("bump_normal", "wall_post", False),
            ("link_drop", "story", False),
            ("vip_program", "story", True),  # send type makes it relevant
            ("expired_winback", "live", True),
            ("first_to_tip", "wall_post", True),
        ],
    )
    def test_is_chatter_relevant_parametrized(
        self,
        chatter_sync: ChatterContentSync,
        send_type: str,
        channel: str,
        expected: bool,
    ) -> None:
        """Parametrized test for chatter relevance logic."""
        assert chatter_sync._is_chatter_relevant(send_type, channel) is expected


# =============================================================================
# Test ChatterContentSync._generate_chatter_notes()
# =============================================================================


class TestGenerateChatterNotes:
    """Tests for _generate_chatter_notes() content generation."""

    def test_first_to_tip_with_price(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """first_to_tip should generate award note with price."""
        item = {"send_type": "first_to_tip", "price": 25.00, "audience_target": "all"}
        notes = chatter_sync._generate_chatter_notes(item)
        assert notes is not None
        assert "Monitor for first tipper" in notes
        assert "$25" in notes or "$25.0" in notes

    def test_first_to_tip_without_price(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """first_to_tip without price should show $XX placeholder."""
        item = {"send_type": "first_to_tip", "price": None, "audience_target": "all"}
        notes = chatter_sync._generate_chatter_notes(item)
        assert notes is not None
        assert "Monitor for first tipper" in notes
        assert "$XX" in notes

    def test_vip_program_note(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """vip_program should generate VIP campaign note."""
        item = {"send_type": "vip_program", "price": 50.00, "audience_target": "all"}
        notes = chatter_sync._generate_chatter_notes(item)
        assert notes is not None
        assert "VIP campaign" in notes
        assert "premium engagement" in notes

    def test_high_spenders_audience_note(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """high_spenders audience should generate personalized response note."""
        item = {"send_type": "ppv_unlock", "price": 20.00, "audience_target": "high_spenders"}
        notes = chatter_sync._generate_chatter_notes(item)
        assert notes is not None
        assert "High-value audience" in notes
        assert "personalized responses" in notes

    def test_expired_winback_note(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """expired_winback should generate extra engaging note."""
        item = {"send_type": "expired_winback", "price": None, "audience_target": "expired_subs"}
        notes = chatter_sync._generate_chatter_notes(item)
        assert notes is not None
        assert "Expired sub winback" in notes
        assert "extra engaging" in notes

    def test_no_special_notes_for_regular_item(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """Regular items without special attributes should return None."""
        item = {"send_type": "bump_normal", "price": None, "audience_target": "all"}
        notes = chatter_sync._generate_chatter_notes(item)
        assert notes is None

    def test_multiple_notes_concatenated_with_pipe(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """Multiple notes should be concatenated with ' | ' separator."""
        item = {
            "send_type": "vip_program",
            "price": 50.00,
            "audience_target": "high_spenders",
        }
        notes = chatter_sync._generate_chatter_notes(item)
        assert notes is not None
        assert " | " in notes
        assert "VIP campaign" in notes
        assert "High-value audience" in notes

    def test_first_to_tip_high_spenders_combined(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """first_to_tip with high_spenders should have both notes."""
        item = {
            "send_type": "first_to_tip",
            "price": 30.00,
            "audience_target": "high_spenders",
        }
        notes = chatter_sync._generate_chatter_notes(item)
        assert notes is not None
        assert "Monitor for first tipper" in notes
        assert "High-value audience" in notes

    def test_empty_item_returns_none(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """Empty item dict should return None."""
        notes = chatter_sync._generate_chatter_notes({})
        assert notes is None


# =============================================================================
# Test ChatterContentSync._generate_chatter_instructions()
# =============================================================================


class TestGenerateChatterInstructions:
    """Tests for _generate_chatter_instructions() output."""

    def test_base_instructions_always_present(
        self,
        chatter_sync: ChatterContentSync,
        non_chatter_schedule: list[dict[str, Any]],
    ) -> None:
        """Base instructions should always be present in output."""
        instructions = chatter_sync._generate_chatter_instructions(non_chatter_schedule)
        assert len(instructions) >= 4
        assert any("Review manifest items" in i for i in instructions)
        assert any("Match DM content" in i for i in instructions)
        assert any("Use provided captions" in i for i in instructions)
        assert any("Track first-to-tip" in i for i in instructions)

    def test_vip_instruction_added_for_vip_schedule(
        self,
        chatter_sync: ChatterContentSync,
        sample_schedule: list[dict[str, Any]],
    ) -> None:
        """VIP instruction should be added when vip_program is in schedule."""
        instructions = chatter_sync._generate_chatter_instructions(sample_schedule)
        assert any("VIP program sends" in i for i in instructions)
        assert any("priority attention" in i for i in instructions)

    def test_no_vip_instruction_without_vip_schedule(
        self,
        chatter_sync: ChatterContentSync,
        non_chatter_schedule: list[dict[str, Any]],
    ) -> None:
        """VIP instruction should not be added when vip_program is not present."""
        instructions = chatter_sync._generate_chatter_instructions(non_chatter_schedule)
        assert not any("VIP program sends" in i for i in instructions)

    def test_empty_schedule_returns_base_instructions(
        self,
        chatter_sync: ChatterContentSync,
        empty_schedule: list[dict[str, Any]],
    ) -> None:
        """Empty schedule should return only base instructions."""
        instructions = chatter_sync._generate_chatter_instructions(empty_schedule)
        assert len(instructions) == 4

    def test_instructions_are_strings(
        self,
        chatter_sync: ChatterContentSync,
        sample_schedule: list[dict[str, Any]],
    ) -> None:
        """All instructions should be strings."""
        instructions = chatter_sync._generate_chatter_instructions(sample_schedule)
        assert all(isinstance(i, str) for i in instructions)


# =============================================================================
# Test ChatterContentSync.generate_chatter_content_manifest()
# =============================================================================


class TestGenerateChatterContentManifest:
    """Tests for generate_chatter_content_manifest() functionality."""

    def test_manifest_contains_creator_id(
        self,
        chatter_sync: ChatterContentSync,
        sample_schedule: list[dict[str, Any]],
    ) -> None:
        """Manifest should include creator_id in output."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            sample_schedule, "creator_123"
        )
        assert manifest["creator_id"] == "creator_123"

    def test_manifest_contains_generated_at_timestamp(
        self,
        chatter_sync: ChatterContentSync,
        sample_schedule: list[dict[str, Any]],
    ) -> None:
        """Manifest should include ISO timestamp in generated_at."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            sample_schedule, "creator_123"
        )
        assert "generated_at" in manifest
        # Verify it's a valid ISO timestamp
        generated_at = manifest["generated_at"]
        datetime.fromisoformat(generated_at)  # Raises ValueError if invalid

    def test_manifest_filters_chatter_relevant_items(
        self,
        chatter_sync: ChatterContentSync,
        sample_schedule: list[dict[str, Any]],
    ) -> None:
        """Manifest should only include chatter-relevant items."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            sample_schedule, "creator_123"
        )
        # Original schedule has 5 items, 3 are chatter-relevant:
        # - ppv_unlock on mass_message
        # - dm_farm on targeted_message
        # - vip_program on mass_message
        assert manifest["total_items"] == 3

    def test_manifest_total_items_count(
        self,
        chatter_sync: ChatterContentSync,
        chatter_only_schedule: list[dict[str, Any]],
    ) -> None:
        """total_items should equal length of manifest_all."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            chatter_only_schedule, "creator_123"
        )
        assert manifest["total_items"] == len(manifest["manifest_all"])
        assert manifest["total_items"] == 2

    def test_manifest_groups_by_date(
        self,
        chatter_sync: ChatterContentSync,
        sample_schedule: list[dict[str, Any]],
    ) -> None:
        """manifest_by_date should group items by schedule_date."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            sample_schedule, "creator_123"
        )
        by_date = manifest["manifest_by_date"]
        # Should have 2 dates: 2025-12-16 (ppv_unlock) and 2025-12-17 (dm_farm, vip_program)
        assert "2025-12-16" in by_date
        assert "2025-12-17" in by_date
        assert len(by_date["2025-12-16"]) == 1
        assert len(by_date["2025-12-17"]) == 2

    def test_manifest_all_contains_flat_list(
        self,
        chatter_sync: ChatterContentSync,
        sample_schedule: list[dict[str, Any]],
    ) -> None:
        """manifest_all should be a flat list of all chatter items."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            sample_schedule, "creator_123"
        )
        assert isinstance(manifest["manifest_all"], list)
        assert len(manifest["manifest_all"]) == 3

    def test_manifest_item_structure(
        self,
        chatter_sync: ChatterContentSync,
        chatter_only_schedule: list[dict[str, Any]],
    ) -> None:
        """Each manifest item should have correct structure."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            chatter_only_schedule, "creator_123"
        )
        item = manifest["manifest_all"][0]
        expected_keys = {
            "schedule_date",
            "send_type",
            "channel",
            "content_id",
            "content_type",
            "caption_text",
            "price",
            "audience_target",
            "label",
            "special_notes",
        }
        assert set(item.keys()) == expected_keys

    def test_manifest_preserves_item_values(
        self,
        chatter_sync: ChatterContentSync,
        chatter_only_schedule: list[dict[str, Any]],
    ) -> None:
        """Manifest items should preserve original schedule values."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            chatter_only_schedule, "creator_123"
        )
        item = manifest["manifest_all"][0]
        assert item["schedule_date"] == "2025-12-16"
        assert item["send_type"] == "ppv_unlock"
        assert item["channel"] == "mass_message"
        assert item["price"] == 20.00

    def test_manifest_includes_chatter_instructions(
        self,
        chatter_sync: ChatterContentSync,
        sample_schedule: list[dict[str, Any]],
    ) -> None:
        """Manifest should include chatter_instructions list."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            sample_schedule, "creator_123"
        )
        assert "chatter_instructions" in manifest
        assert isinstance(manifest["chatter_instructions"], list)
        assert len(manifest["chatter_instructions"]) >= 4

    def test_manifest_with_non_chatter_schedule(
        self,
        chatter_sync: ChatterContentSync,
        non_chatter_schedule: list[dict[str, Any]],
    ) -> None:
        """Non-chatter schedule should produce manifest with zero items."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            non_chatter_schedule, "creator_123"
        )
        assert manifest["total_items"] == 0
        assert manifest["manifest_all"] == []
        assert manifest["manifest_by_date"] == {}

    def test_manifest_with_empty_schedule(
        self,
        chatter_sync: ChatterContentSync,
        empty_schedule: list[dict[str, Any]],
    ) -> None:
        """Empty schedule should produce manifest with zero items."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            empty_schedule, "creator_123"
        )
        assert manifest["total_items"] == 0
        assert manifest["manifest_all"] == []
        assert manifest["creator_id"] == "creator_123"

    def test_manifest_handles_missing_schedule_date(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """Items without schedule_date should be grouped under 'unscheduled'."""
        schedule = [
            {
                "send_type": "ppv_unlock",
                "channel": "mass_message",
                "content_id": "content_001",
                "content_type": "video",
                "caption_text": "Check this out!",
            },
        ]
        manifest = chatter_sync.generate_chatter_content_manifest(schedule, "creator_123")
        assert "unscheduled" in manifest["manifest_by_date"]
        assert len(manifest["manifest_by_date"]["unscheduled"]) == 1

    def test_manifest_special_notes_populated(
        self,
        chatter_sync: ChatterContentSync,
        first_to_tip_schedule: list[dict[str, Any]],
    ) -> None:
        """special_notes should be populated for relevant items."""
        manifest = chatter_sync.generate_chatter_content_manifest(
            first_to_tip_schedule, "creator_123"
        )
        item = manifest["manifest_all"][0]
        assert item["special_notes"] is not None
        assert "Monitor for first tipper" in item["special_notes"]

    def test_manifest_special_notes_none_for_regular_item(
        self, chatter_sync: ChatterContentSync
    ) -> None:
        """special_notes should be None for items without special handling."""
        schedule = [
            {
                "send_type": "ppv_unlock",
                "channel": "mass_message",
                "content_id": "content_001",
                "content_type": "video",
                "caption_text": "Regular PPV!",
                "price": 15.00,
                "audience_target": "all",
            },
        ]
        manifest = chatter_sync.generate_chatter_content_manifest(schedule, "creator_123")
        item = manifest["manifest_all"][0]
        assert item["special_notes"] is None


# =============================================================================
# Test export_chatter_manifest_json()
# =============================================================================


class TestExportChatterManifestJson:
    """Tests for export_chatter_manifest_json() file operations."""

    def test_creates_valid_json_file(
        self, tmp_path: Path, sample_schedule: list[dict[str, Any]]
    ) -> None:
        """Should create a valid JSON file at output_path."""
        output_file = tmp_path / "manifest.json"
        result = export_chatter_manifest_json(
            sample_schedule, "creator_123", str(output_file)
        )
        assert output_file.exists()
        # Verify JSON is valid
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "creator_id" in data

    def test_returns_output_path(
        self, tmp_path: Path, sample_schedule: list[dict[str, Any]]
    ) -> None:
        """Should return the output_path where manifest was written."""
        output_file = tmp_path / "manifest.json"
        result = export_chatter_manifest_json(
            sample_schedule, "creator_123", str(output_file)
        )
        assert result == str(output_file)

    def test_exported_manifest_structure(
        self, tmp_path: Path, sample_schedule: list[dict[str, Any]]
    ) -> None:
        """Exported manifest should have correct structure."""
        output_file = tmp_path / "manifest.json"
        export_chatter_manifest_json(sample_schedule, "creator_123", str(output_file))

        with open(output_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["creator_id"] == "creator_123"
        assert "generated_at" in manifest
        assert "total_items" in manifest
        assert "manifest_by_date" in manifest
        assert "manifest_all" in manifest
        assert "chatter_instructions" in manifest

    def test_exported_manifest_preserves_data(
        self, tmp_path: Path, chatter_only_schedule: list[dict[str, Any]]
    ) -> None:
        """Exported manifest should preserve all data correctly."""
        output_file = tmp_path / "manifest.json"
        export_chatter_manifest_json(
            chatter_only_schedule, "creator_456", str(output_file)
        )

        with open(output_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["total_items"] == 2
        assert len(manifest["manifest_all"]) == 2
        assert manifest["manifest_all"][0]["send_type"] == "ppv_unlock"

    def test_exported_json_is_indented(
        self, tmp_path: Path, sample_schedule: list[dict[str, Any]]
    ) -> None:
        """Exported JSON should be formatted with indentation."""
        output_file = tmp_path / "manifest.json"
        export_chatter_manifest_json(sample_schedule, "creator_123", str(output_file))

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for indentation (2 spaces based on indent=2 in source)
        assert "\n  " in content  # Indented lines present

    def test_exported_json_encoding_utf8(
        self, tmp_path: Path
    ) -> None:
        """Exported JSON should handle UTF-8 characters."""
        schedule = [
            {
                "send_type": "ppv_unlock",
                "channel": "mass_message",
                "caption_text": "Hey babe! Check your DMs...",
            },
        ]
        output_file = tmp_path / "manifest.json"
        export_chatter_manifest_json(schedule, "creator_123", str(output_file))

        with open(output_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "..." in manifest["manifest_all"][0]["caption_text"]

    def test_export_empty_schedule(
        self, tmp_path: Path, empty_schedule: list[dict[str, Any]]
    ) -> None:
        """Should handle empty schedule correctly."""
        output_file = tmp_path / "manifest.json"
        export_chatter_manifest_json(empty_schedule, "creator_123", str(output_file))

        with open(output_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["total_items"] == 0
        assert manifest["manifest_all"] == []

    def test_export_creates_nested_directories(
        self, tmp_path: Path, sample_schedule: list[dict[str, Any]]
    ) -> None:
        """Should work with nested output directories that exist."""
        nested_dir = tmp_path / "exports" / "chatter"
        nested_dir.mkdir(parents=True)
        output_file = nested_dir / "manifest.json"

        result = export_chatter_manifest_json(
            sample_schedule, "creator_123", str(output_file)
        )

        assert output_file.exists()
        assert result == str(output_file)

    def test_export_overwrites_existing_file(
        self, tmp_path: Path, sample_schedule: list[dict[str, Any]]
    ) -> None:
        """Should overwrite existing file at output_path."""
        output_file = tmp_path / "manifest.json"
        # Create initial file
        output_file.write_text('{"old": "data"}')

        export_chatter_manifest_json(sample_schedule, "creator_123", str(output_file))

        with open(output_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "old" not in manifest
        assert manifest["creator_id"] == "creator_123"


# =============================================================================
# Integration Tests
# =============================================================================


class TestChatterSyncIntegration:
    """Integration tests for complete chatter sync workflow."""

    def test_full_workflow_with_sample_schedule(
        self, tmp_path: Path, sample_schedule: list[dict[str, Any]]
    ) -> None:
        """Test complete workflow from schedule to exported file."""
        output_file = tmp_path / "chatter_manifest.json"

        # Export manifest
        result_path = export_chatter_manifest_json(
            sample_schedule, "alexia_123", str(output_file)
        )

        # Verify file was created
        assert Path(result_path).exists()

        # Load and verify content
        with open(result_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Verify structure
        assert manifest["creator_id"] == "alexia_123"
        assert manifest["total_items"] == 3  # 3 chatter-relevant items

        # Verify filtering worked correctly
        send_types = [item["send_type"] for item in manifest["manifest_all"]]
        assert "ppv_unlock" in send_types
        assert "dm_farm" in send_types
        assert "vip_program" in send_types
        assert "bump_normal" not in send_types  # wall_post channel
        assert "link_drop" not in send_types  # story channel

        # Verify VIP instruction present
        assert any(
            "VIP program sends" in i for i in manifest["chatter_instructions"]
        )

    def test_stateless_sync_multiple_calls(
        self, chatter_sync: ChatterContentSync, sample_schedule: list[dict[str, Any]]
    ) -> None:
        """ChatterContentSync should be stateless across multiple calls."""
        manifest1 = chatter_sync.generate_chatter_content_manifest(
            sample_schedule, "creator_1"
        )
        manifest2 = chatter_sync.generate_chatter_content_manifest(
            sample_schedule, "creator_2"
        )

        assert manifest1["creator_id"] == "creator_1"
        assert manifest2["creator_id"] == "creator_2"
        assert manifest1["total_items"] == manifest2["total_items"]

    def test_different_schedules_produce_different_manifests(
        self,
        chatter_sync: ChatterContentSync,
        chatter_only_schedule: list[dict[str, Any]],
        non_chatter_schedule: list[dict[str, Any]],
    ) -> None:
        """Different schedules should produce appropriately different manifests."""
        manifest_chatter = chatter_sync.generate_chatter_content_manifest(
            chatter_only_schedule, "creator_123"
        )
        manifest_non_chatter = chatter_sync.generate_chatter_content_manifest(
            non_chatter_schedule, "creator_123"
        )

        assert manifest_chatter["total_items"] == 2
        assert manifest_non_chatter["total_items"] == 0
