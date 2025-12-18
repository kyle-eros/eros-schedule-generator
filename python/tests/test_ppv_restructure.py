"""
Comprehensive tests for PPV Send Type Restructure (v2.1.0).

This module tests all aspects of the PPV restructure:
- ppv_video → ppv_unlock rename
- ppv_wall (FREE pages only)
- tip_goal (PAID pages only, 3 modes)
- ppv_message deprecation (merged into ppv_unlock)
- Backward compatibility via SEND_TYPE_ALIASES
- Category counts (9 revenue, 9 engagement, 4 retention = 22 total)

Created: 2025-12-16
"""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.models.send_type import (
    PPV_TYPES,
    PPV_REVENUE_TYPES,
    TipGoalMode,
    PAGE_TYPE_FREE_ONLY,
    PAGE_TYPE_PAID_ONLY,
    REVENUE_TYPES,
    ENGAGEMENT_TYPES,
    RETENTION_TYPES,
    SEND_TYPE_ALIASES,
    resolve_send_type_key,
    is_valid_for_page_type,
)
from python.validators import VALID_SEND_TYPE_KEYS
from python.validation.vault_validator import VaultValidator, ContentTypePreference


class TestSendTypeConstants:
    """Tests for send type constant definitions."""

    def test_ppv_types_includes_unlock_wall_followup(self):
        """Test PPV_TYPES contains all PPV types."""
        assert "ppv_unlock" in PPV_TYPES
        assert "ppv_wall" in PPV_TYPES
        assert "ppv_followup" in PPV_TYPES

    def test_ppv_revenue_types_includes_unlock_wall_tipgoal(self):
        """Test PPV_REVENUE_TYPES contains revenue-generating PPV types."""
        assert "ppv_unlock" in PPV_REVENUE_TYPES
        assert "ppv_wall" in PPV_REVENUE_TYPES
        assert "tip_goal" in PPV_REVENUE_TYPES

    def test_revenue_types_count_is_9(self):
        """Test there are exactly 9 revenue types."""
        assert len(REVENUE_TYPES) == 9

    def test_engagement_types_count_is_9(self):
        """Test there are exactly 9 engagement types."""
        assert len(ENGAGEMENT_TYPES) == 9

    def test_retention_types_count_is_4(self):
        """Test there are exactly 4 retention types."""
        assert len(RETENTION_TYPES) == 4

    def test_total_types_is_22(self):
        """Test total active types is 22."""
        total = len(REVENUE_TYPES) + len(ENGAGEMENT_TYPES) + len(RETENTION_TYPES)
        assert total == 22

    def test_page_type_free_only_contains_ppv_wall(self):
        """Test ppv_wall is the only FREE-only type."""
        assert "ppv_wall" in PAGE_TYPE_FREE_ONLY
        assert len(PAGE_TYPE_FREE_ONLY) == 1

    def test_page_type_paid_only_contains_correct_types(self):
        """Test PAID-only types are correct."""
        expected = {"tip_goal", "renew_on_post", "renew_on_message", "expired_winback"}
        assert PAGE_TYPE_PAID_ONLY == expected


class TestTipGoalMode:
    """Tests for TipGoalMode enum."""

    def test_goal_based_mode(self):
        """Test goal_based mode exists."""
        assert TipGoalMode.GOAL_BASED.value == "goal_based"

    def test_individual_mode(self):
        """Test individual mode exists."""
        assert TipGoalMode.INDIVIDUAL.value == "individual"

    def test_competitive_mode(self):
        """Test competitive mode exists."""
        assert TipGoalMode.COMPETITIVE.value == "competitive"

    def test_enum_has_three_modes(self):
        """Test there are exactly 3 tip goal modes."""
        assert len(TipGoalMode) == 3


class TestSendTypeAliases:
    """Tests for backward compatibility aliases."""

    def test_ppv_video_alias_exists(self):
        """Test ppv_video alias maps to ppv_unlock."""
        assert "ppv_video" in SEND_TYPE_ALIASES
        assert SEND_TYPE_ALIASES["ppv_video"] == "ppv_unlock"

    def test_ppv_message_alias_exists(self):
        """Test ppv_message alias maps to ppv_unlock."""
        assert "ppv_message" in SEND_TYPE_ALIASES
        assert SEND_TYPE_ALIASES["ppv_message"] == "ppv_unlock"

    def test_resolve_ppv_video(self):
        """Test resolve_send_type_key handles ppv_video."""
        assert resolve_send_type_key("ppv_video") == "ppv_unlock"

    def test_resolve_ppv_message(self):
        """Test resolve_send_type_key handles ppv_message."""
        assert resolve_send_type_key("ppv_message") == "ppv_unlock"

    def test_resolve_ppv_unlock_unchanged(self):
        """Test resolve_send_type_key returns ppv_unlock unchanged."""
        assert resolve_send_type_key("ppv_unlock") == "ppv_unlock"

    def test_resolve_non_aliased_unchanged(self):
        """Test resolve_send_type_key returns non-aliased types unchanged."""
        assert resolve_send_type_key("bump_normal") == "bump_normal"
        assert resolve_send_type_key("tip_goal") == "tip_goal"


class TestPageTypeValidation:
    """Tests for page type validation."""

    def test_ppv_wall_valid_for_free(self):
        """Test ppv_wall is valid for FREE pages."""
        assert is_valid_for_page_type("ppv_wall", "free") is True

    def test_ppv_wall_invalid_for_paid(self):
        """Test ppv_wall is invalid for PAID pages."""
        assert is_valid_for_page_type("ppv_wall", "paid") is False

    def test_tip_goal_valid_for_paid(self):
        """Test tip_goal is valid for PAID pages."""
        assert is_valid_for_page_type("tip_goal", "paid") is True

    def test_tip_goal_invalid_for_free(self):
        """Test tip_goal is invalid for FREE pages."""
        assert is_valid_for_page_type("tip_goal", "free") is False

    def test_ppv_unlock_valid_for_both(self):
        """Test ppv_unlock is valid for both page types."""
        assert is_valid_for_page_type("ppv_unlock", "paid") is True
        assert is_valid_for_page_type("ppv_unlock", "free") is True

    def test_retention_types_invalid_for_free(self):
        """Test retention types (except ppv_followup) are invalid for FREE pages."""
        assert is_valid_for_page_type("renew_on_post", "free") is False
        assert is_valid_for_page_type("renew_on_message", "free") is False
        assert is_valid_for_page_type("expired_winback", "free") is False

    def test_ppv_followup_valid_for_both(self):
        """Test ppv_followup is valid for both page types."""
        assert is_valid_for_page_type("ppv_followup", "paid") is True
        assert is_valid_for_page_type("ppv_followup", "free") is True

    def test_deprecated_alias_resolves_correctly(self):
        """Test deprecated aliases resolve before validation."""
        # ppv_video should resolve to ppv_unlock
        assert is_valid_for_page_type("ppv_video", "paid") is True
        assert is_valid_for_page_type("ppv_video", "free") is True


class TestValidatorsSendTypeKeys:
    """Tests for VALID_SEND_TYPE_KEYS in validators."""

    def test_ppv_unlock_in_valid_keys(self):
        """Test ppv_unlock is in VALID_SEND_TYPE_KEYS."""
        assert "ppv_unlock" in VALID_SEND_TYPE_KEYS

    def test_ppv_wall_in_valid_keys(self):
        """Test ppv_wall is in VALID_SEND_TYPE_KEYS."""
        assert "ppv_wall" in VALID_SEND_TYPE_KEYS

    def test_tip_goal_in_valid_keys(self):
        """Test tip_goal is in VALID_SEND_TYPE_KEYS."""
        assert "tip_goal" in VALID_SEND_TYPE_KEYS

    def test_deprecated_ppv_video_still_valid(self):
        """Test deprecated ppv_video is still in VALID_SEND_TYPE_KEYS for backward compat."""
        assert "ppv_video" in VALID_SEND_TYPE_KEYS

    def test_deprecated_ppv_message_still_valid(self):
        """Test deprecated ppv_message is still in VALID_SEND_TYPE_KEYS for backward compat."""
        assert "ppv_message" in VALID_SEND_TYPE_KEYS

    def test_all_22_active_types_valid(self):
        """Test all 22 active types are in VALID_SEND_TYPE_KEYS."""
        all_active = REVENUE_TYPES | ENGAGEMENT_TYPES | RETENTION_TYPES
        for send_type in all_active:
            assert send_type in VALID_SEND_TYPE_KEYS, f"{send_type} not in VALID_SEND_TYPE_KEYS"


class TestVaultValidator:
    """Tests for VaultValidator with new PPV types."""

    @pytest.fixture
    def validator(self) -> VaultValidator:
        return VaultValidator()

    def test_ppv_unlock_preferences_exist(self, validator):
        """Test ppv_unlock has content type preferences."""
        assert "ppv_unlock" in validator.DEFAULT_PREFERENCES

    def test_ppv_wall_preferences_exist(self, validator):
        """Test ppv_wall has content type preferences."""
        assert "ppv_wall" in validator.DEFAULT_PREFERENCES

    def test_tip_goal_preferences_exist(self, validator):
        """Test tip_goal has content type preferences."""
        assert "tip_goal" in validator.DEFAULT_PREFERENCES

    def test_ppv_unlock_prefers_video(self, validator):
        """Test ppv_unlock prefers video content."""
        prefs = validator.DEFAULT_PREFERENCES["ppv_unlock"]
        first_pref = prefs[0]
        assert first_pref.content_type == "video"
        assert first_pref.priority == 1

    def test_validate_with_video_available(self, validator):
        """Test validation succeeds when video is available."""
        vault = {"video": True, "photo": True, "photo_set": True}
        result = validator.validate_content_for_send_type("ppv_unlock", vault)
        assert result.valid is True
        assert result.selected_type == "video"

    def test_validate_with_fallback(self, validator):
        """Test validation falls back to lower priority content."""
        vault = {"video": False, "photo": True, "photo_set": True}
        result = validator.validate_content_for_send_type("ppv_unlock", vault)
        assert result.valid is True
        # Should select photo_set or photo as fallback
        assert result.selected_type in ["photo_set", "photo"]

    def test_validate_with_no_content(self, validator):
        """Test validation fails when no content available."""
        vault = {"video": False, "photo": False, "photo_set": False}
        result = validator.validate_content_for_send_type("ppv_unlock", vault)
        assert result.valid is False


class TestCategoryDistribution:
    """Tests for correct category distribution."""

    def test_revenue_category_members(self):
        """Test all revenue types are correct."""
        expected = {
            "ppv_unlock", "ppv_wall", "tip_goal", "vip_program", "game_post",
            "bundle", "flash_bundle", "snapchat_bundle", "first_to_tip"
        }
        assert REVENUE_TYPES == expected

    def test_engagement_category_members(self):
        """Test all engagement types are correct."""
        expected = {
            "link_drop", "wall_link_drop", "bump_normal", "bump_descriptive",
            "bump_text_only", "bump_flyer", "dm_farm", "like_farm", "live_promo"
        }
        assert ENGAGEMENT_TYPES == expected

    def test_retention_category_members(self):
        """Test all retention types are correct."""
        expected = {
            "renew_on_post", "renew_on_message", "ppv_followup", "expired_winback"
        }
        assert RETENTION_TYPES == expected

    def test_no_category_overlap(self):
        """Test no types appear in multiple categories."""
        all_types = list(REVENUE_TYPES) + list(ENGAGEMENT_TYPES) + list(RETENTION_TYPES)
        assert len(all_types) == len(set(all_types)), "Duplicate type found across categories"


class TestDeprecationTransition:
    """Tests for deprecation transition period handling."""

    def test_ppv_video_resolves_correctly(self):
        """Test ppv_video still works during transition."""
        resolved = resolve_send_type_key("ppv_video")
        assert resolved == "ppv_unlock"

    def test_ppv_message_resolves_correctly(self):
        """Test ppv_message still works during transition."""
        resolved = resolve_send_type_key("ppv_message")
        assert resolved == "ppv_unlock"

    def test_new_types_dont_need_resolution(self):
        """Test new types don't get modified."""
        assert resolve_send_type_key("ppv_unlock") == "ppv_unlock"
        assert resolve_send_type_key("ppv_wall") == "ppv_wall"
        assert resolve_send_type_key("tip_goal") == "tip_goal"

    def test_engagement_types_unchanged(self):
        """Test engagement types are not affected by aliases."""
        for send_type in ENGAGEMENT_TYPES:
            assert resolve_send_type_key(send_type) == send_type

    def test_retention_types_unchanged(self):
        """Test retention types are not affected by aliases."""
        for send_type in RETENTION_TYPES:
            assert resolve_send_type_key(send_type) == send_type
