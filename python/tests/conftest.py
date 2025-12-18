"""
Pytest fixtures for EROS Schedule Generator tests.

Provides shared fixtures for database connections, sample data,
and mocked components used across the test suite.
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.allocation.send_type_allocator import (
    SendTypeAllocator,
    VolumeConfig,
    VolumeTier,
)
from python.matching.caption_matcher import Caption, CaptionMatcher
from python.optimization.schedule_optimizer import ScheduleItem, ScheduleOptimizer
from python.models.creator import Creator, CreatorProfile
from python.models.schedule import ScheduleItem as ModelScheduleItem
from python.registry.send_type_registry import SendTypeRegistry


# =============================================================================
# Creator Fixtures
# =============================================================================


@pytest.fixture
def sample_creator() -> Creator:
    """Sample creator for testing - paid page with MID tier fans."""
    return Creator(
        creator_id=1,
        username="alexia",
        page_type="paid",
        fan_count=2500,
        is_active=1,
    )


@pytest.fixture
def sample_creator_free() -> Creator:
    """Sample creator for testing - free page."""
    return Creator(
        creator_id=2,
        username="luna",
        page_type="free",
        fan_count=8000,
        is_active=1,
    )


@pytest.fixture
def sample_creator_profile() -> CreatorProfile:
    """Sample creator profile with extended metadata."""
    return CreatorProfile(
        creator_id=1,
        username="alexia",
        page_type="paid",
        fan_count=2500,
        persona_archetype="girl_next_door",
        voice_tone="playful",
        saturation_score=45.0,
        opportunity_score=75.0,
        is_active=1,
    )


@pytest.fixture
def low_tier_creator() -> Creator:
    """Creator with LOW volume tier (< 1000 fans)."""
    return Creator(
        creator_id=3,
        username="jade",
        page_type="paid",
        fan_count=500,
        is_active=1,
    )


@pytest.fixture
def ultra_tier_creator() -> Creator:
    """Creator with ULTRA volume tier (15000+ fans)."""
    return Creator(
        creator_id=4,
        username="diamond",
        page_type="paid",
        fan_count=50000,
        is_active=1,
    )


# =============================================================================
# Volume Configuration Fixtures
# =============================================================================


@pytest.fixture
def sample_volume_config() -> VolumeConfig:
    """Sample volume configuration for MID tier paid page."""
    return VolumeConfig(
        tier=VolumeTier.MID,
        revenue_per_day=4,
        engagement_per_day=4,
        retention_per_day=2,
        fan_count=2500,
        page_type="paid",
    )


@pytest.fixture
def free_page_volume_config() -> VolumeConfig:
    """Volume configuration for free page (no retention)."""
    return VolumeConfig(
        tier=VolumeTier.HIGH,
        revenue_per_day=6,
        engagement_per_day=5,
        retention_per_day=0,  # Free pages cannot have retention
        fan_count=8000,
        page_type="free",
    )


@pytest.fixture
def low_tier_volume_config() -> VolumeConfig:
    """Volume configuration for LOW tier."""
    return VolumeConfig(
        tier=VolumeTier.LOW,
        revenue_per_day=3,
        engagement_per_day=3,
        retention_per_day=1,
        fan_count=500,
        page_type="paid",
    )


@pytest.fixture
def ultra_tier_volume_config() -> VolumeConfig:
    """Volume configuration for ULTRA tier."""
    return VolumeConfig(
        tier=VolumeTier.ULTRA,
        revenue_per_day=8,
        engagement_per_day=6,
        retention_per_day=3,
        fan_count=50000,
        page_type="paid",
    )


# =============================================================================
# Caption Fixtures
# =============================================================================


@pytest.fixture
def sample_captions() -> list[Caption]:
    """List of sample captions with varied scores and types."""
    return [
        Caption(
            id=1,
            text="Hey babe, check your DMs for something special...",
            type="ppv_unlock",
            performance_score=85.0,
            freshness_score=95.0,
            content_type="video",
            emoji_level=3,
            slang_level=2,
            tone="flirty",
        ),
        Caption(
            id=2,
            text="New exclusive content just for you!",
            type="exclusive",
            performance_score=75.0,
            freshness_score=80.0,
            content_type="video",
            emoji_level=2,
            slang_level=1,
            tone="playful",
        ),
        Caption(
            id=3,
            text="Limited time offer - 50% off my VIP tier!",
            type="vip_pitch",
            performance_score=90.0,
            freshness_score=70.0,
            content_type="none",
            emoji_level=4,
            slang_level=2,
            tone="urgent",
        ),
        Caption(
            id=4,
            text="Hey there! Just checking in...",
            type="flirty_opener",
            performance_score=65.0,
            freshness_score=85.0,
            content_type="none",
            emoji_level=2,
            slang_level=1,
            tone="friendly",
        ),
        Caption(
            id=5,
            text="Miss me? I've got something special for you...",
            type="renewal_pitch",
            performance_score=80.0,
            freshness_score=60.0,
            content_type="none",
            emoji_level=3,
            slang_level=2,
            tone="seductive",
        ),
    ]


@pytest.fixture
def high_performance_captions() -> list[Caption]:
    """Captions with high performance scores (> 80)."""
    return [
        Caption(
            id=10,
            text="Top performer caption 1",
            type="ppv_unlock",
            performance_score=95.0,
            freshness_score=90.0,
        ),
        Caption(
            id=11,
            text="Top performer caption 2",
            type="exclusive",
            performance_score=92.0,
            freshness_score=85.0,
        ),
        Caption(
            id=12,
            text="Top performer caption 3",
            type="urgent",
            performance_score=88.0,
            freshness_score=95.0,
        ),
    ]


@pytest.fixture
def stale_captions() -> list[Caption]:
    """Captions with low freshness scores (used recently)."""
    return [
        Caption(
            id=20,
            text="Stale caption 1",
            type="ppv_unlock",
            performance_score=85.0,
            freshness_score=10.0,
            last_used_date=datetime.now(),
        ),
        Caption(
            id=21,
            text="Stale caption 2",
            type="exclusive",
            performance_score=80.0,
            freshness_score=15.0,
            last_used_date=datetime.now() - timedelta(days=5),
        ),
    ]


@pytest.fixture
def empty_caption_list() -> list[Caption]:
    """Empty caption list for edge case testing."""
    return []


# =============================================================================
# Schedule Item Fixtures
# =============================================================================


@pytest.fixture
def sample_schedule_items() -> list[ScheduleItem]:
    """Sample schedule items across categories."""
    return [
        ScheduleItem(
            send_type_key="ppv_video",
            scheduled_date="2025-12-16",
            scheduled_time="19:00",
            category="revenue",
            priority=1,
            caption_id=1,
            caption_text="Check your DMs!",
            requires_media=True,
            media_type="video",
        ),
        ScheduleItem(
            send_type_key="bump_normal",
            scheduled_date="2025-12-16",
            scheduled_time="14:00",
            category="engagement",
            priority=2,
            caption_id=4,
            caption_text="Hey there!",
            requires_media=True,
            media_type="picture",
        ),
        ScheduleItem(
            send_type_key="renew_on_message",
            scheduled_date="2025-12-16",
            scheduled_time="10:00",
            category="retention",
            priority=3,
            caption_id=5,
            caption_text="Miss me?",
            requires_media=False,
        ),
    ]


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """In-memory SQLite database with schema for testing."""
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

    # Insert test send types (all 21)
    send_types = [
        # Revenue (7)
        ("ppv_video", "revenue", "PPV Video", 1, 1, 1, "both", "long", "heavy", 4, 10),
        ("vip_program", "revenue", "VIP Program", 0, 1, 0, "both", "medium", "moderate", 1, 15),
        ("game_post", "revenue", "Game Post", 1, 0, 0, "both", "short", "heavy", None, 20),
        ("bundle", "revenue", "Bundle", 1, 1, 0, "both", "long", "moderate", 2, 25),
        ("flash_bundle", "revenue", "Flash Bundle", 1, 1, 0, "both", "short", "heavy", 1, 30),
        ("snapchat_bundle", "revenue", "Snapchat Bundle", 1, 1, 0, "both", "medium", "moderate", 1, 35),
        ("first_to_tip", "revenue", "First to Tip", 0, 0, 0, "both", "short", "heavy", None, 40),
        # Engagement (9)
        ("link_drop", "engagement", "Link Drop", 1, 0, 0, "both", "short", "light", None, 50),
        ("wall_link_drop", "engagement", "Wall Link Drop", 1, 0, 0, "both", "short", "light", None, 55),
        ("bump_normal", "engagement", "Normal Bump", 1, 0, 0, "both", "short", "light", None, 60),
        ("bump_descriptive", "engagement", "Descriptive Bump", 1, 0, 0, "both", "long", "moderate", None, 65),
        ("bump_text_only", "engagement", "Text Only Bump", 0, 0, 0, "both", "medium", "light", None, 70),
        ("bump_flyer", "engagement", "Flyer Bump", 1, 0, 0, "both", "short", "heavy", None, 75),
        ("dm_farm", "engagement", "DM Farm", 0, 0, 0, "both", "short", "light", None, 80),
        ("like_farm", "engagement", "Like Farm", 0, 0, 0, "both", "short", "light", None, 85),
        ("live_promo", "engagement", "Live Promo", 0, 0, 0, "both", "short", "heavy", None, 90),
        # Retention (5)
        ("renew_on_post", "retention", "Renew on Post", 1, 0, 0, "paid", "medium", "moderate", None, 100),
        ("renew_on_message", "retention", "Renew on Message", 0, 0, 0, "paid", "medium", "light", None, 105),
        ("ppv_message", "retention", "PPV Message", 1, 1, 0, "paid", "long", "moderate", None, 110),
        ("ppv_followup", "retention", "PPV Followup", 0, 0, 0, "both", "short", "light", 4, 115),
        ("expired_winback", "retention", "Expired Winback", 0, 0, 0, "paid", "medium", "moderate", None, 120),
    ]

    for st in send_types:
        cursor.execute("""
            INSERT INTO send_types (
                send_type_key, category, display_name,
                requires_media, requires_price, can_have_followup,
                page_type_restriction, caption_length, emoji_recommendation,
                max_per_day, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, st)

    # Create creators table
    cursor.execute("""
        CREATE TABLE creators (
            creator_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            page_type TEXT NOT NULL,
            fan_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Insert test creators
    creators = [
        ("alexia", "paid", 2500),
        ("luna", "free", 8000),
        ("jade", "paid", 500),
        ("diamond", "paid", 50000),
    ]

    for c in creators:
        cursor.execute(
            "INSERT INTO creators (username, page_type, fan_count) VALUES (?, ?, ?)",
            c,
        )

    # Create captions table
    cursor.execute("""
        CREATE TABLE captions (
            caption_id INTEGER PRIMARY KEY,
            caption_text TEXT NOT NULL,
            send_type_key TEXT NOT NULL,
            content_type_id INTEGER,
            media_type TEXT DEFAULT 'none',
            length_category TEXT,
            emoji_level TEXT,
            performance_score REAL,
            last_used_date TEXT,
            use_count INTEGER DEFAULT 0,
            creator_id INTEGER,
            is_active INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    yield conn
    conn.close()


# =============================================================================
# Component Fixtures
# =============================================================================


@pytest.fixture
def allocator() -> SendTypeAllocator:
    """Fresh SendTypeAllocator instance."""
    return SendTypeAllocator()


@pytest.fixture
def caption_matcher() -> CaptionMatcher:
    """Fresh CaptionMatcher instance with reset tracking."""
    matcher = CaptionMatcher()
    matcher.reset_usage_tracking()
    return matcher


@pytest.fixture
def optimizer() -> ScheduleOptimizer:
    """Fresh ScheduleOptimizer instance with reset tracking."""
    opt = ScheduleOptimizer()
    opt.reset_tracking()
    return opt


@pytest.fixture
def mock_registry(mocker) -> MagicMock:
    """Mocked SendTypeRegistry for isolated testing."""
    mock = mocker.MagicMock(spec=SendTypeRegistry)

    # Configure common return values
    mock.is_valid_key.return_value = True
    mock.get_keys_by_category.return_value = ["ppv_video", "bundle"]

    return mock


# =============================================================================
# Date and Time Fixtures
# =============================================================================


@pytest.fixture
def monday_week_start() -> datetime:
    """Monday start date for weekly schedule testing."""
    return datetime(2025, 12, 15)  # A Monday


@pytest.fixture
def saturday_date() -> str:
    """Saturday date string for peak day testing."""
    return "2025-12-20"


@pytest.fixture
def prime_time_hour() -> int:
    """Prime time hour for timing optimization testing."""
    return 19  # 7 PM


@pytest.fixture
def avoid_hour() -> int:
    """Avoid hour for timing penalty testing."""
    return 4  # 4 AM


# =============================================================================
# Edge Case Fixtures
# =============================================================================


@pytest.fixture
def boundary_fan_count_999() -> int:
    """Boundary fan count at LOW tier max."""
    return 999


@pytest.fixture
def boundary_fan_count_1000() -> int:
    """Boundary fan count at MID tier min."""
    return 1000


@pytest.fixture
def boundary_fan_count_4999() -> int:
    """Boundary fan count at MID tier max."""
    return 4999


@pytest.fixture
def boundary_fan_count_5000() -> int:
    """Boundary fan count at HIGH tier min."""
    return 5000


@pytest.fixture
def boundary_fan_count_14999() -> int:
    """Boundary fan count at HIGH tier max."""
    return 14999


@pytest.fixture
def boundary_fan_count_15000() -> int:
    """Boundary fan count at ULTRA tier min."""
    return 15000
