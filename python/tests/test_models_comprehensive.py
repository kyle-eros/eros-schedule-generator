"""
Comprehensive unit tests for EROS domain models.

Tests all domain models in python/models/ with focus on:
- Edge cases and boundary conditions
- Validation logic
- Property methods
- Serialization/deserialization
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.models.volume import VolumeConfig, VolumeTier
from python.models.creator import Creator, CreatorProfile
from python.models.caption import Caption, CaptionScore
from python.models.schedule import ScheduleItem, ScheduleTemplate
from python.models.send_type import (
    SendType,
    SendTypeConfig,
    TipGoalMode,
    PPV_TYPES,
    PPV_REVENUE_TYPES,
    DEPRECATED_SEND_TYPES,
    SEND_TYPE_ALIASES,
    PAGE_TYPE_FREE_ONLY,
    PAGE_TYPE_PAID_ONLY,
    REVENUE_TYPES,
    ENGAGEMENT_TYPES,
    RETENTION_TYPES,
    resolve_send_type_key,
    is_valid_for_page_type,
)
from python.models.schedule_item import (
    ScheduleItemWithExpiration,
    create_link_drop,
    create_wall_link_drop,
    LINK_DROP_TYPES,
    DEFAULT_LINK_DROP_EXPIRATION_HOURS,
)
from python.models.creator_timing_profile import CreatorTimingProfile


# =============================================================================
# Volume Model Tests
# =============================================================================


class TestVolumeTier:
    """Test VolumeTier enum."""

    def test_all_tiers_exist(self):
        """Test all expected tiers exist."""
        assert VolumeTier.LOW.value == "low"
        assert VolumeTier.MID.value == "mid"
        assert VolumeTier.HIGH.value == "high"
        assert VolumeTier.ULTRA.value == "ultra"

    def test_tier_count(self):
        """Test correct number of tiers."""
        assert len(VolumeTier) == 4


class TestVolumeConfigEdgeCases:
    """Edge case tests for VolumeConfig."""

    def test_zero_volumes_valid(self):
        """Test zero volumes are valid."""
        config = VolumeConfig(
            tier=VolumeTier.LOW,
            revenue_per_day=0,
            engagement_per_day=0,
            retention_per_day=0,
            fan_count=100,
            page_type="paid",
        )
        assert config.total_per_day == 0

    def test_negative_revenue_invalid(self):
        """Test negative revenue is invalid."""
        with pytest.raises(ValueError, match="non-negative"):
            VolumeConfig(
                tier=VolumeTier.LOW,
                revenue_per_day=-1,
                engagement_per_day=3,
                retention_per_day=1,
                fan_count=500,
                page_type="paid",
            )

    def test_negative_engagement_invalid(self):
        """Test negative engagement is invalid."""
        with pytest.raises(ValueError, match="non-negative"):
            VolumeConfig(
                tier=VolumeTier.LOW,
                revenue_per_day=3,
                engagement_per_day=-1,
                retention_per_day=1,
                fan_count=500,
                page_type="paid",
            )

    def test_negative_retention_invalid(self):
        """Test negative retention is invalid."""
        with pytest.raises(ValueError, match="non-negative"):
            VolumeConfig(
                tier=VolumeTier.LOW,
                revenue_per_day=3,
                engagement_per_day=3,
                retention_per_day=-1,
                fan_count=500,
                page_type="paid",
            )

    def test_free_page_zero_retention_valid(self):
        """Test free page with zero retention is valid."""
        config = VolumeConfig(
            tier=VolumeTier.HIGH,
            revenue_per_day=6,
            engagement_per_day=5,
            retention_per_day=0,
            fan_count=8000,
            page_type="free",
        )
        assert config.retention_per_day == 0

    def test_large_volumes(self):
        """Test large volume values."""
        config = VolumeConfig(
            tier=VolumeTier.ULTRA,
            revenue_per_day=100,
            engagement_per_day=100,
            retention_per_day=50,
            fan_count=500000,
            page_type="paid",
        )
        assert config.total_per_day == 250


# =============================================================================
# Creator Model Tests
# =============================================================================


class TestCreatorValidation:
    """Test Creator validation."""

    def test_negative_fan_count_invalid(self):
        """Test negative fan count is invalid."""
        with pytest.raises(ValueError, match="non-negative"):
            Creator(
                creator_id=1,
                username="test",
                page_type="paid",
                fan_count=-100,
            )

    def test_zero_fan_count_valid(self):
        """Test zero fan count is valid (new creator)."""
        creator = Creator(
            creator_id=1,
            username="new_creator",
            page_type="paid",
            fan_count=0,
        )
        assert creator.fan_count == 0

    def test_default_is_active(self):
        """Test default is_active is 1."""
        creator = Creator(
            creator_id=1,
            username="test",
            page_type="paid",
            fan_count=1000,
        )
        assert creator.is_active == 1

    def test_inactive_creator(self):
        """Test inactive creator."""
        creator = Creator(
            creator_id=1,
            username="test",
            page_type="paid",
            fan_count=1000,
            is_active=0,
        )
        assert creator.is_active == 0


class TestCreatorProfileConversion:
    """Test CreatorProfile methods."""

    def test_to_creator_preserves_fields(self):
        """Test to_creator preserves all required fields."""
        profile = CreatorProfile(
            creator_id=42,
            username="alexia",
            page_type="paid",
            fan_count=5000,
            persona_archetype="seductress",
            voice_tone="flirty",
            saturation_score=45.0,
            opportunity_score=75.0,
            is_active=1,
        )

        creator = profile.to_creator()

        assert creator.creator_id == 42
        assert creator.username == "alexia"
        assert creator.page_type == "paid"
        assert creator.fan_count == 5000
        assert creator.is_active == 1

    def test_profile_optional_fields_none(self):
        """Test profile with all optional fields None."""
        profile = CreatorProfile(
            creator_id=1,
            username="minimal",
            page_type="free",
            fan_count=100,
        )

        assert profile.persona_archetype is None
        assert profile.voice_tone is None
        assert profile.saturation_score is None


# =============================================================================
# Caption Model Tests
# =============================================================================


class TestCaptionFreshness:
    """Test Caption freshness calculations."""

    def test_freshness_never_used(self):
        """Test freshness when never used."""
        caption = Caption(
            caption_id=1,
            caption_text="Test",
            send_type_key="ppv_unlock",
            last_used_date=None,
        )
        assert caption.freshness_days is None

    def test_freshness_used_today(self):
        """Test freshness when used today."""
        today = datetime.now().strftime("%Y-%m-%d")
        caption = Caption(
            caption_id=1,
            caption_text="Test",
            send_type_key="ppv_unlock",
            last_used_date=today,
        )
        assert caption.freshness_days == 0

    def test_freshness_used_yesterday(self):
        """Test freshness when used yesterday."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        caption = Caption(
            caption_id=1,
            caption_text="Test",
            send_type_key="ppv_unlock",
            last_used_date=yesterday,
        )
        assert caption.freshness_days == 1


class TestCaptionScoreValidation:
    """Test CaptionScore validation."""

    def test_negative_score_invalid(self):
        """Test negative scores are invalid."""
        with pytest.raises(ValueError, match="between 0 and 100"):
            CaptionScore(
                caption_id=1,
                performance_score=-10.0,
                freshness_score=50.0,
                type_priority_score=50.0,
                persona_match_score=50.0,
                diversity_score=50.0,
                composite_score=50.0,
            )

    def test_score_over_100_invalid(self):
        """Test scores over 100 are invalid."""
        with pytest.raises(ValueError, match="between 0 and 100"):
            CaptionScore(
                caption_id=1,
                performance_score=50.0,
                freshness_score=101.0,
                type_priority_score=50.0,
                persona_match_score=50.0,
                diversity_score=50.0,
                composite_score=50.0,
            )

    def test_boundary_scores_valid(self):
        """Test boundary scores (0 and 100) are valid."""
        score = CaptionScore(
            caption_id=1,
            performance_score=0.0,
            freshness_score=100.0,
            type_priority_score=0.0,
            persona_match_score=100.0,
            diversity_score=50.0,
            composite_score=50.0,
        )
        assert score.performance_score == 0.0
        assert score.freshness_score == 100.0

    def test_ranking_default(self):
        """Test ranking defaults to 0."""
        score = CaptionScore(
            caption_id=1,
            performance_score=50.0,
            freshness_score=50.0,
            type_priority_score=50.0,
            persona_match_score=50.0,
            diversity_score=50.0,
            composite_score=50.0,
        )
        assert score.ranking == 0


# =============================================================================
# Schedule Item Tests
# =============================================================================


class TestScheduleItemValidation:
    """Test ScheduleItem validation."""

    def test_invalid_priority_too_low(self):
        """Test priority < 1 is invalid."""
        with pytest.raises(ValueError, match="Priority must be 1-3"):
            ScheduleItem(
                send_type_key="ppv_unlock",
                scheduled_date="2025-12-16",
                scheduled_time="19:00",
                category="revenue",
                priority=0,
            )

    def test_invalid_priority_too_high(self):
        """Test priority > 3 is invalid."""
        with pytest.raises(ValueError, match="Priority must be 1-3"):
            ScheduleItem(
                send_type_key="ppv_unlock",
                scheduled_date="2025-12-16",
                scheduled_time="19:00",
                category="revenue",
                priority=4,
            )

    def test_invalid_media_type(self):
        """Test invalid media_type is rejected."""
        with pytest.raises(ValueError, match="Invalid media_type"):
            ScheduleItem(
                send_type_key="ppv_unlock",
                scheduled_date="2025-12-16",
                scheduled_time="19:00",
                category="revenue",
                priority=1,
                media_type="audio",
            )

    def test_invalid_time_format(self):
        """Test invalid time format is rejected."""
        with pytest.raises(ValueError, match="Invalid scheduled_time format"):
            ScheduleItem(
                send_type_key="ppv_unlock",
                scheduled_date="2025-12-16",
                scheduled_time="7:00 PM",
                category="revenue",
                priority=1,
            )

    def test_datetime_obj_property(self):
        """Test datetime_obj property combines date and time."""
        item = ScheduleItem(
            send_type_key="ppv_unlock",
            scheduled_date="2025-12-16",
            scheduled_time="19:30",
            category="revenue",
            priority=1,
        )
        dt = item.datetime_obj
        assert dt.year == 2025
        assert dt.month == 12
        assert dt.day == 16
        assert dt.hour == 19
        assert dt.minute == 30

    def test_all_valid_media_types(self):
        """Test all valid media types."""
        for media_type in ["picture", "video", "gif", "flyer", "none"]:
            item = ScheduleItem(
                send_type_key="ppv_unlock",
                scheduled_date="2025-12-16",
                scheduled_time="19:00",
                category="revenue",
                priority=1,
                media_type=media_type,
            )
            assert item.media_type == media_type


class TestScheduleTemplate:
    """Test ScheduleTemplate validation."""

    def test_invalid_volume_tier(self):
        """Test invalid volume_tier is rejected."""
        with pytest.raises(ValueError, match="Invalid volume_tier"):
            ScheduleTemplate(
                template_id=1,
                template_name="Test",
                page_type="paid",
                volume_tier="mega",
                revenue_per_day=5,
                engagement_per_day=4,
                retention_per_day=2,
            )

    def test_invalid_timing_strategy(self):
        """Test invalid timing_strategy is rejected."""
        with pytest.raises(ValueError, match="Invalid timing_strategy"):
            ScheduleTemplate(
                template_id=1,
                template_name="Test",
                page_type="paid",
                volume_tier="mid",
                revenue_per_day=5,
                engagement_per_day=4,
                retention_per_day=2,
                timing_strategy="aggressive",
            )

    def test_total_per_day_property(self):
        """Test total_per_day property calculation."""
        template = ScheduleTemplate(
            template_id=1,
            template_name="Test",
            page_type="paid",
            volume_tier="mid",
            revenue_per_day=5,
            engagement_per_day=4,
            retention_per_day=2,
        )
        assert template.total_per_day == 11


# =============================================================================
# Send Type Tests
# =============================================================================


class TestSendTypeConstants:
    """Test send type constants."""

    def test_ppv_types_frozen(self):
        """Test PPV_TYPES is immutable frozenset."""
        assert isinstance(PPV_TYPES, frozenset)
        assert "ppv_unlock" in PPV_TYPES
        assert "ppv_wall" in PPV_TYPES

    def test_deprecated_send_types(self):
        """Test deprecated send types are tracked."""
        assert "ppv_video" in DEPRECATED_SEND_TYPES
        assert "ppv_message" in DEPRECATED_SEND_TYPES

    def test_send_type_aliases(self):
        """Test send type aliases map correctly."""
        assert SEND_TYPE_ALIASES["ppv_video"] == "ppv_unlock"
        assert SEND_TYPE_ALIASES["ppv_message"] == "ppv_unlock"

    def test_category_type_counts(self):
        """Test category type counts match expected."""
        assert len(REVENUE_TYPES) == 9
        assert len(ENGAGEMENT_TYPES) == 9
        assert len(RETENTION_TYPES) == 4


class TestResolveSendTypeKey:
    """Test resolve_send_type_key function."""

    def test_resolve_deprecated_ppv_video(self):
        """Test deprecated ppv_video resolves to ppv_unlock."""
        assert resolve_send_type_key("ppv_video") == "ppv_unlock"

    def test_resolve_deprecated_ppv_message(self):
        """Test deprecated ppv_message resolves to ppv_unlock."""
        assert resolve_send_type_key("ppv_message") == "ppv_unlock"

    def test_resolve_canonical_unchanged(self):
        """Test canonical types are unchanged."""
        assert resolve_send_type_key("ppv_unlock") == "ppv_unlock"
        assert resolve_send_type_key("bump_normal") == "bump_normal"

    def test_resolve_unknown_unchanged(self):
        """Test unknown types are unchanged."""
        assert resolve_send_type_key("custom_type") == "custom_type"


class TestIsValidForPageType:
    """Test is_valid_for_page_type function."""

    def test_ppv_wall_free_only(self):
        """Test ppv_wall is free-only."""
        assert is_valid_for_page_type("ppv_wall", "free") is True
        assert is_valid_for_page_type("ppv_wall", "paid") is False

    def test_retention_paid_only(self):
        """Test retention types are paid-only."""
        for send_type in ["renew_on_post", "renew_on_message", "expired_winback"]:
            assert is_valid_for_page_type(send_type, "paid") is True
            assert is_valid_for_page_type(send_type, "free") is False

    def test_tip_goal_paid_only(self):
        """Test tip_goal is paid-only."""
        assert is_valid_for_page_type("tip_goal", "paid") is True
        assert is_valid_for_page_type("tip_goal", "free") is False

    def test_universal_types(self):
        """Test universal types work on both page types."""
        for send_type in ["ppv_unlock", "bump_normal", "bundle"]:
            assert is_valid_for_page_type(send_type, "paid") is True
            assert is_valid_for_page_type(send_type, "free") is True

    def test_deprecated_type_resolution(self):
        """Test deprecated types resolve before checking."""
        # ppv_video -> ppv_unlock (universal)
        assert is_valid_for_page_type("ppv_video", "paid") is True
        assert is_valid_for_page_type("ppv_video", "free") is True


class TestSendTypeConfig:
    """Test SendTypeConfig validation."""

    def test_valid_categories(self):
        """Test valid categories are accepted."""
        for category in ["revenue", "engagement", "retention"]:
            config = SendTypeConfig(
                key="test",
                name="Test",
                category=category,
                page_type="both",
                timing_preferences={},
                caption_requirements=[],
                max_per_day=None,
                max_per_week=None,
            )
            assert config.category == category

    def test_valid_page_types(self):
        """Test valid page types are accepted."""
        for page_type in ["paid", "free", "both"]:
            config = SendTypeConfig(
                key="test",
                name="Test",
                category="revenue",
                page_type=page_type,
                timing_preferences={},
                caption_requirements=[],
                max_per_day=None,
                max_per_week=None,
            )
            assert config.page_type == page_type


class TestTipGoalMode:
    """Test TipGoalMode enum."""

    def test_all_modes_exist(self):
        """Test all tip goal modes exist."""
        assert TipGoalMode.GOAL_BASED.value == "goal_based"
        assert TipGoalMode.INDIVIDUAL.value == "individual"
        assert TipGoalMode.COMPETITIVE.value == "competitive"


# =============================================================================
# Schedule Item With Expiration Tests
# =============================================================================


class TestScheduleItemWithExpiration:
    """Test ScheduleItemWithExpiration."""

    def test_link_drop_auto_expiration(self):
        """Test link_drop auto-sets 24h expiration."""
        scheduled = datetime(2025, 12, 17, 14, 0)
        item = ScheduleItemWithExpiration(
            send_type="link_drop",
            scheduled_time=scheduled,
            channel="mass_message",
        )
        assert item.expiration_time is not None
        expected_expiration = scheduled + timedelta(hours=24)
        assert item.expiration_time == expected_expiration

    def test_wall_link_drop_auto_expiration(self):
        """Test wall_link_drop auto-sets 24h expiration."""
        scheduled = datetime(2025, 12, 17, 14, 0)
        item = ScheduleItemWithExpiration(
            send_type="wall_link_drop",
            scheduled_time=scheduled,
            channel="wall_post",
        )
        assert item.expiration_time is not None

    def test_non_link_drop_no_auto_expiration(self):
        """Test non-link-drop types don't auto-expire."""
        item = ScheduleItemWithExpiration(
            send_type="ppv_unlock",
            scheduled_time=datetime(2025, 12, 17, 14, 0),
            channel="mass_message",
        )
        assert item.expiration_time is None

    def test_is_expired_before_expiration(self):
        """Test is_expired returns False before expiration."""
        scheduled = datetime(2025, 12, 17, 14, 0)
        item = ScheduleItemWithExpiration(
            send_type="link_drop",
            scheduled_time=scheduled,
            channel="mass_message",
        )
        check_time = scheduled + timedelta(hours=12)
        assert item.is_expired(check_time) is False

    def test_is_expired_after_expiration(self):
        """Test is_expired returns True after expiration."""
        scheduled = datetime(2025, 12, 17, 14, 0)
        item = ScheduleItemWithExpiration(
            send_type="link_drop",
            scheduled_time=scheduled,
            channel="mass_message",
        )
        check_time = scheduled + timedelta(hours=25)
        assert item.is_expired(check_time) is True

    def test_is_expired_no_expiration(self):
        """Test is_expired returns False when no expiration set."""
        item = ScheduleItemWithExpiration(
            send_type="ppv_unlock",
            scheduled_time=datetime(2025, 12, 17, 14, 0),
            channel="mass_message",
        )
        assert item.is_expired() is False

    def test_time_until_expiration(self):
        """Test time_until_expiration calculation."""
        scheduled = datetime(2025, 12, 17, 14, 0)
        item = ScheduleItemWithExpiration(
            send_type="link_drop",
            scheduled_time=scheduled,
            channel="mass_message",
        )
        check_time = scheduled + timedelta(hours=12)
        remaining = item.time_until_expiration(check_time)
        assert remaining is not None
        assert remaining.total_seconds() == 12 * 3600

    def test_is_link_drop_property(self):
        """Test is_link_drop property."""
        link_drop = ScheduleItemWithExpiration(
            send_type="link_drop",
            scheduled_time=datetime.now(),
            channel="mass_message",
        )
        ppv = ScheduleItemWithExpiration(
            send_type="ppv_unlock",
            scheduled_time=datetime.now(),
            channel="mass_message",
        )
        assert link_drop.is_link_drop is True
        assert ppv.is_link_drop is False

    def test_to_dict_serialization(self):
        """Test to_dict produces valid dictionary."""
        scheduled = datetime(2025, 12, 17, 14, 0)
        item = ScheduleItemWithExpiration(
            send_type="link_drop",
            scheduled_time=scheduled,
            channel="mass_message",
            caption_id="cap_123",
            price=None,
        )
        data = item.to_dict()
        assert data["send_type"] == "link_drop"
        assert data["scheduled_time"] == scheduled.isoformat()
        assert data["channel"] == "mass_message"
        assert data["caption_id"] == "cap_123"
        assert "expiration_time" in data


class TestCreateLinkDrop:
    """Test create_link_drop factory function."""

    def test_creates_linked_item(self):
        """Test creates item linked to parent."""
        parent = ScheduleItemWithExpiration(
            send_type="ppv_wall",
            scheduled_time=datetime(2025, 12, 17, 10, 0),
            channel="wall_post",
            price=9.99,
        )
        link_drop = create_link_drop(
            parent_campaign=parent,
            scheduled_time=datetime(2025, 12, 17, 14, 0),
        )
        assert link_drop.parent_id == parent.item_id
        assert link_drop.send_type == "link_drop"

    def test_invalid_send_type_raises(self):
        """Test invalid send_type raises ValueError."""
        parent = ScheduleItemWithExpiration(
            send_type="ppv_wall",
            scheduled_time=datetime(2025, 12, 17, 10, 0),
            channel="wall_post",
        )
        with pytest.raises(ValueError, match="Invalid link drop type"):
            create_link_drop(
                parent_campaign=parent,
                scheduled_time=datetime(2025, 12, 17, 14, 0),
                send_type="bump_normal",
            )


class TestCreateWallLinkDrop:
    """Test create_wall_link_drop convenience function."""

    def test_creates_wall_link_drop(self):
        """Test creates wall_link_drop type."""
        parent = ScheduleItemWithExpiration(
            send_type="ppv_wall",
            scheduled_time=datetime(2025, 12, 17, 10, 0),
            channel="wall_post",
        )
        wall_drop = create_wall_link_drop(
            parent_campaign=parent,
            scheduled_time=datetime(2025, 12, 17, 16, 0),
        )
        assert wall_drop.send_type == "wall_link_drop"


# =============================================================================
# Creator Timing Profile Tests
# =============================================================================


class TestCreatorTimingProfile:
    """Test CreatorTimingProfile generation and methods."""

    def test_from_creator_id_deterministic(self):
        """Test profile generation is deterministic."""
        profile1 = CreatorTimingProfile.from_creator_id("creator_123")
        profile2 = CreatorTimingProfile.from_creator_id("creator_123")

        assert profile1.seed == profile2.seed
        assert profile1.base_jitter_offset == profile2.base_jitter_offset
        assert profile1.preferred_start_hour == profile2.preferred_start_hour

    def test_different_creators_different_profiles(self):
        """Test different creators get different profiles."""
        profile1 = CreatorTimingProfile.from_creator_id("alice")
        profile2 = CreatorTimingProfile.from_creator_id("bob")

        # At least one attribute should differ
        attrs_differ = (
            profile1.seed != profile2.seed
            or profile1.base_jitter_offset != profile2.base_jitter_offset
            or profile1.time_clustering_preference != profile2.time_clustering_preference
        )
        assert attrs_differ

    def test_empty_creator_id_defaults(self):
        """Test empty creator_id returns default profile."""
        profile = CreatorTimingProfile.from_creator_id("")

        assert profile.seed == 0
        assert profile.base_jitter_offset == 0
        assert profile.preferred_start_hour == 8
        assert profile.preferred_end_hour == 22
        assert profile.time_clustering_preference == "balanced"

    def test_jitter_offset_range(self):
        """Test jitter offset is in expected range."""
        # Test multiple creators to verify range
        for i in range(100):
            profile = CreatorTimingProfile.from_creator_id(f"creator_{i}")
            assert -5 <= profile.base_jitter_offset <= 5

    def test_preferred_start_hour_range(self):
        """Test preferred start hour is in expected range."""
        for i in range(100):
            profile = CreatorTimingProfile.from_creator_id(f"creator_{i}")
            assert 7 <= profile.preferred_start_hour <= 10

    def test_preferred_end_hour_range(self):
        """Test preferred end hour is in expected range."""
        for i in range(100):
            profile = CreatorTimingProfile.from_creator_id(f"creator_{i}")
            assert 21 <= profile.preferred_end_hour <= 23

    def test_apply_jitter_bias(self):
        """Test apply_jitter_bias applies creator bias."""
        profile = CreatorTimingProfile.from_creator_id("test")
        base_jitter = 3
        biased = profile.apply_jitter_bias(base_jitter)

        # Result should be base + offset, clamped to range
        expected = max(-10, min(10, base_jitter + profile.base_jitter_offset))
        assert biased == expected

    def test_apply_jitter_bias_clamping(self):
        """Test apply_jitter_bias clamps to range."""
        # Create profile manually to control offset
        profile = CreatorTimingProfile(
            creator_id="test",
            seed=0,
            base_jitter_offset=5,
            preferred_start_hour=8,
            preferred_end_hour=22,
            strategy_rotation_offset=0,
            time_clustering_preference="balanced",
            prime_hour_shift=0,
        )
        # 8 + 5 = 13, should clamp to 10
        assert profile.apply_jitter_bias(8) == 10
        # -8 + 5 = -3, no clamping needed
        assert profile.apply_jitter_bias(-8) == -3

    def test_adjust_hour_for_preference(self):
        """Test adjust_hour_for_preference clamps to window."""
        profile = CreatorTimingProfile(
            creator_id="test",
            seed=0,
            base_jitter_offset=0,
            preferred_start_hour=9,
            preferred_end_hour=21,
            strategy_rotation_offset=0,
            time_clustering_preference="balanced",
            prime_hour_shift=0,
        )
        # Before window
        assert profile.adjust_hour_for_preference(6) == 9
        # After window
        assert profile.adjust_hour_for_preference(23) == 21
        # Within window
        assert profile.adjust_hour_for_preference(15) == 15

    def test_should_cluster_morning(self):
        """Test cluster_morning preference."""
        profile = CreatorTimingProfile(
            creator_id="test",
            seed=0,
            base_jitter_offset=0,
            preferred_start_hour=8,
            preferred_end_hour=22,
            strategy_rotation_offset=0,
            time_clustering_preference="cluster_morning",
            prime_hour_shift=0,
        )
        assert profile.should_cluster_at_time(10) is True
        assert profile.should_cluster_at_time(20) is False

    def test_should_cluster_evening(self):
        """Test cluster_evening preference."""
        profile = CreatorTimingProfile(
            creator_id="test",
            seed=0,
            base_jitter_offset=0,
            preferred_start_hour=8,
            preferred_end_hour=22,
            strategy_rotation_offset=0,
            time_clustering_preference="cluster_evening",
            prime_hour_shift=0,
        )
        assert profile.should_cluster_at_time(10) is False
        assert profile.should_cluster_at_time(20) is True

    def test_get_adjusted_prime_hours(self):
        """Test get_adjusted_prime_hours applies shift."""
        profile = CreatorTimingProfile(
            creator_id="test",
            seed=0,
            base_jitter_offset=0,
            preferred_start_hour=8,
            preferred_end_hour=22,
            strategy_rotation_offset=0,
            time_clustering_preference="balanced",
            prime_hour_shift=1,
        )
        base_hours = [19, 20, 21]
        adjusted = profile.get_adjusted_prime_hours(base_hours)
        assert adjusted == [20, 21, 22]

    def test_repr_format(self):
        """Test __repr__ produces readable output."""
        profile = CreatorTimingProfile.from_creator_id("test")
        repr_str = repr(profile)
        assert "CreatorTimingProfile" in repr_str
        assert "test" in repr_str


# =============================================================================
# Link Drop Constants Tests
# =============================================================================


class TestLinkDropConstants:
    """Test link drop related constants."""

    def test_link_drop_types_frozenset(self):
        """Test LINK_DROP_TYPES is a frozenset."""
        assert isinstance(LINK_DROP_TYPES, frozenset)
        assert "link_drop" in LINK_DROP_TYPES
        assert "wall_link_drop" in LINK_DROP_TYPES
        assert len(LINK_DROP_TYPES) == 2

    def test_default_expiration_hours(self):
        """Test default expiration is 24 hours."""
        assert DEFAULT_LINK_DROP_EXPIRATION_HOURS == 24
