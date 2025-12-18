"""
Unit tests for Wave 3 Domain Models & Registry.

Tests the domain models, send type registry, and configuration management
implemented in Wave 3.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from python.models import (
    Creator,
    CreatorProfile,
    Caption,
    CaptionScore,
    ScheduleItem,
    ScheduleTemplate,
    SendType,
    SendTypeConfig,
    VolumeConfig,
    VolumeTier,
)
from python.registry import SendTypeRegistry
from python.config import Settings


# =============================================================================
# Domain Model Tests
# =============================================================================


class TestVolumeModels:
    """Test volume domain models."""

    def test_volume_config_creation(self):
        """Test VolumeConfig creation and properties."""
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=3,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        assert config.tier == VolumeTier.MID
        assert config.total_per_day == 9
        assert config.page_type == "paid"

    def test_volume_config_immutable(self):
        """Test VolumeConfig is frozen (immutable)."""
        config = VolumeConfig(
            tier=VolumeTier.LOW,
            revenue_per_day=3,
            engagement_per_day=3,
            retention_per_day=1,
            fan_count=500,
            page_type="paid",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            config.revenue_per_day = 5

    def test_volume_config_validation(self):
        """Test VolumeConfig validation."""
        # Invalid page type
        with pytest.raises(ValueError):
            VolumeConfig(
                tier=VolumeTier.LOW,
                revenue_per_day=3,
                engagement_per_day=3,
                retention_per_day=1,
                fan_count=500,
                page_type="invalid",
            )

        # Free page with retention
        with pytest.raises(ValueError):
            VolumeConfig(
                tier=VolumeTier.LOW,
                revenue_per_day=3,
                engagement_per_day=3,
                retention_per_day=1,
                fan_count=500,
                page_type="free",
            )


class TestCreatorModels:
    """Test creator domain models."""

    def test_creator_creation(self):
        """Test Creator creation."""
        creator = Creator(
            creator_id=1,
            username="alexia",
            page_type="paid",
            fan_count=5000,
        )

        assert creator.creator_id == 1
        assert creator.username == "alexia"
        assert creator.fan_count == 5000

    def test_creator_profile_to_creator(self):
        """Test CreatorProfile conversion to Creator."""
        profile = CreatorProfile(
            creator_id=1,
            username="alexia",
            page_type="paid",
            fan_count=5000,
            persona_archetype="girl_next_door",
            saturation_score=45.0,
        )

        creator = profile.to_creator()
        assert isinstance(creator, Creator)
        assert creator.creator_id == profile.creator_id
        assert creator.username == profile.username


class TestCaptionModels:
    """Test caption domain models."""

    def test_caption_freshness_days(self):
        """Test Caption freshness calculation."""
        caption = Caption(
            caption_id=1,
            caption_text="Test caption",
            send_type_key="ppv_video",
            last_used_date="2025-11-15",
        )

        freshness = caption.freshness_days
        assert freshness is not None
        assert freshness >= 30  # At least 30 days

    def test_caption_score_validation(self):
        """Test CaptionScore validates score ranges."""
        # Valid scores
        score = CaptionScore(
            caption_id=1,
            performance_score=80.0,
            freshness_score=90.0,
            type_priority_score=70.0,
            persona_match_score=85.0,
            diversity_score=75.0,
            composite_score=81.0,
        )
        assert score.composite_score == 81.0

        # Invalid score (out of range)
        with pytest.raises(ValueError):
            CaptionScore(
                caption_id=1,
                performance_score=150.0,  # Invalid
                freshness_score=90.0,
                type_priority_score=70.0,
                persona_match_score=85.0,
                diversity_score=75.0,
                composite_score=81.0,
            )


class TestScheduleModels:
    """Test schedule domain models."""

    def test_schedule_item_creation(self):
        """Test ScheduleItem creation and datetime parsing."""
        item = ScheduleItem(
            send_type_key="ppv_video",
            scheduled_date="2025-12-16",
            scheduled_time="19:00",
            category="revenue",
            priority=1,
        )

        assert item.send_type_key == "ppv_video"
        assert item.datetime_obj.hour == 19

    def test_schedule_item_validation(self):
        """Test ScheduleItem validates inputs."""
        # Invalid category
        with pytest.raises(ValueError):
            ScheduleItem(
                send_type_key="ppv_video",
                scheduled_date="2025-12-16",
                scheduled_time="19:00",
                category="invalid",
                priority=1,
            )

        # Invalid date format
        with pytest.raises(ValueError):
            ScheduleItem(
                send_type_key="ppv_video",
                scheduled_date="12/16/2025",  # Wrong format
                scheduled_time="19:00",
                category="revenue",
                priority=1,
            )


class TestSendTypeModels:
    """Test send type domain models."""

    def test_send_type_config_validation(self):
        """Test SendTypeConfig validates inputs."""
        # Valid config
        config = SendTypeConfig(
            key="ppv_video",
            name="PPV Video",
            category="revenue",
            page_type="both",
            timing_preferences={},
            caption_requirements=["length_long", "emoji_heavy"],
            max_per_day=4,
            max_per_week=None,
        )
        assert config.key == "ppv_video"

        # Invalid category
        with pytest.raises(ValueError):
            SendTypeConfig(
                key="test",
                name="Test",
                category="invalid",
                page_type="both",
                timing_preferences={},
                caption_requirements=[],
                max_per_day=None,
                max_per_week=None,
            )


# =============================================================================
# Registry Tests
# =============================================================================


class TestSendTypeRegistry:
    """Test SendTypeRegistry singleton and operations."""

    @pytest.fixture
    def test_db(self):
        """Create in-memory test database with send types."""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # Create send_types table
        cursor.execute("""
            CREATE TABLE send_types (
                send_type_id INTEGER PRIMARY KEY,
                send_type_key TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                purpose TEXT,
                strategy TEXT,
                requires_media INTEGER DEFAULT 1,
                requires_flyer INTEGER DEFAULT 0,
                requires_price INTEGER DEFAULT 0,
                requires_link INTEGER DEFAULT 0,
                has_expiration INTEGER DEFAULT 0,
                default_expiration_hours INTEGER,
                can_have_followup INTEGER DEFAULT 0,
                followup_delay_minutes INTEGER DEFAULT 20,
                page_type_restriction TEXT DEFAULT 'both',
                caption_length TEXT,
                emoji_recommendation TEXT,
                max_per_day INTEGER,
                max_per_week INTEGER,
                min_hours_between INTEGER DEFAULT 2,
                sort_order INTEGER DEFAULT 100,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO send_types (
                send_type_key, category, display_name,
                requires_media, requires_price, can_have_followup,
                page_type_restriction, caption_length, emoji_recommendation,
                max_per_day, sort_order
            ) VALUES
            ('ppv_video', 'revenue', 'PPV Video', 1, 1, 1, 'both', 'long', 'heavy', 4, 10),
            ('bump_normal', 'engagement', 'Normal Bump', 1, 0, 0, 'both', 'short', 'light', NULL, 20),
            ('renew_on_post', 'retention', 'Renew on Post', 1, 0, 0, 'paid', 'medium', 'moderate', NULL, 30)
        """)

        conn.commit()
        yield conn
        conn.close()

    def test_registry_singleton(self):
        """Test registry is a singleton."""
        registry1 = SendTypeRegistry()
        registry2 = SendTypeRegistry()
        assert registry1 is registry2

    def test_registry_load_from_database(self, test_db):
        """Test loading send types from database."""
        registry = SendTypeRegistry()
        registry.clear()  # Clear any existing data

        registry.load_from_database(test_db)

        assert len(registry) == 3
        assert "ppv_video" in registry
        assert "bump_normal" in registry
        assert "renew_on_post" in registry

    def test_registry_get_by_key(self, test_db):
        """Test retrieving send type by key."""
        registry = SendTypeRegistry()
        registry.clear()
        registry.load_from_database(test_db)

        ppv_config = registry.get("ppv_video")
        assert ppv_config.key == "ppv_video"
        assert ppv_config.category == "revenue"
        assert ppv_config.requires_media is True
        assert ppv_config.requires_price is True

    def test_registry_get_by_category(self, test_db):
        """Test retrieving send types by category."""
        registry = SendTypeRegistry()
        registry.clear()
        registry.load_from_database(test_db)

        revenue_types = registry.get_by_category("revenue")
        assert len(revenue_types) == 1
        assert revenue_types[0].key == "ppv_video"

        engagement_types = registry.get_by_category("engagement")
        assert len(engagement_types) == 1

    def test_registry_get_keys_by_category(self, test_db):
        """Test retrieving send type keys by category."""
        registry = SendTypeRegistry()
        registry.clear()
        registry.load_from_database(test_db)

        revenue_keys = registry.get_keys_by_category("revenue")
        assert revenue_keys == ["ppv_video"]

        retention_keys = registry.get_keys_by_category("retention")
        assert retention_keys == ["renew_on_post"]

    def test_registry_get_page_type_compatible(self, test_db):
        """Test filtering send types by page type."""
        registry = SendTypeRegistry()
        registry.clear()
        registry.load_from_database(test_db)

        # Both page types can use 'both' restriction
        paid_types = registry.get_page_type_compatible("paid")
        assert len(paid_types) == 3  # All types

        # Free pages cannot use 'paid' restriction
        free_types = registry.get_page_type_compatible("free")
        assert len(free_types) == 2  # Excludes renew_on_post


# =============================================================================
# Settings Tests
# =============================================================================


class TestSettings:
    """Test Settings singleton and configuration."""

    def test_settings_singleton(self):
        """Test settings is a singleton."""
        settings1 = Settings()
        settings2 = Settings()
        assert settings1 is settings2

    def test_settings_defaults(self):
        """Test default configuration values."""
        settings = Settings()

        # Scoring weights
        weights = settings.scoring_weights
        assert weights["performance"] == 0.35
        assert weights["freshness"] == 0.25
        assert sum(weights.values()) == pytest.approx(1.0)

        # Timing config
        timing = settings.timing_config
        assert 19 in timing["prime_hours"]
        assert 21 in timing["prime_hours"]

        # Volume tiers
        tiers = settings.volume_tiers
        assert tiers["MID"]["paid"]["revenue"] == 4
        assert tiers["HIGH"]["free"]["retention"] == 0

    def test_settings_get_method(self):
        """Test get method with dot notation."""
        settings = Settings()

        # Get nested value
        performance_weight = settings.get("scoring.weights.performance")
        assert performance_weight == 0.35

        # Get with default
        missing = settings.get("nonexistent.key", "default")
        assert missing == "default"

    def test_settings_volume_tiers(self):
        """Test volume tier configuration."""
        settings = Settings()

        tiers = settings.volume_tiers
        assert "LOW" in tiers
        assert "MID" in tiers
        assert "HIGH" in tiers
        assert "ULTRA" in tiers

        # Validate structure
        low_paid = tiers["LOW"]["paid"]
        assert "revenue" in low_paid
        assert "engagement" in low_paid
        assert "retention" in low_paid


# =============================================================================
# Integration Tests
# =============================================================================


class TestDomainModelsIntegration:
    """Test domain models work together correctly."""

    def test_volume_config_with_creator(self):
        """Test VolumeConfig creation from Creator."""
        creator = Creator(
            creator_id=1,
            username="alexia",
            page_type="paid",
            fan_count=2500,
        )

        # Determine tier from fan count
        if creator.fan_count < 1000:
            tier = VolumeTier.LOW
        elif creator.fan_count < 5000:
            tier = VolumeTier.MID
        elif creator.fan_count < 15000:
            tier = VolumeTier.HIGH
        else:
            tier = VolumeTier.ULTRA

        assert tier == VolumeTier.MID

        config = VolumeConfig(
            tier=tier,
            revenue_per_day=4,
            engagement_per_day=3,
            retention_per_day=2,
            fan_count=creator.fan_count,
            page_type=creator.page_type,
        )

        assert config.tier == VolumeTier.MID
        assert config.page_type == creator.page_type

    def test_schedule_item_with_caption(self):
        """Test ScheduleItem with Caption data."""
        caption = Caption(
            caption_id=123,
            caption_text="Check your DMs for something special",
            send_type_key="ppv_video",
            media_type="video",
            performance_score=85.0,
        )

        item = ScheduleItem(
            send_type_key=caption.send_type_key,
            scheduled_date="2025-12-16",
            scheduled_time="19:00",
            category="revenue",
            priority=1,
            caption_id=caption.caption_id,
            caption_text=caption.caption_text,
            media_type=caption.media_type,
        )

        assert item.caption_id == caption.caption_id
        assert item.send_type_key == caption.send_type_key
        assert item.media_type == "video"
