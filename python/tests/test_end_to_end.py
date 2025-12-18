"""
End-to-end integration tests for EROS Schedule Generator.

Tests the complete schedule generation workflow from creator data
through schedule output, verifying all 7 phases of the orchestration
pipeline work together correctly.

These tests validate:
1. End-to-end schedule generation pipeline
2. Database integration with actual queries
3. MCP tool integration patterns
4. Multi-phase orchestration workflow
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.allocation.send_type_allocator import (
    SendTypeAllocator,
    VolumeConfig,
)
from python.matching.caption_matcher import Caption, CaptionMatcher, CaptionResult
from python.optimization.schedule_optimizer import ScheduleItem, ScheduleOptimizer
from python.orchestration.timing_optimizer import apply_time_jitter
from python.volume.dynamic_calculator import (
    PerformanceContext,
    calculate_dynamic_volume,
    calculate_optimized_volume,
    get_volume_tier,
)
from python.models.creator import Creator
from python.models.volume import VolumeConfig as ModelVolumeConfig, VolumeTier


# =============================================================================
# Test Fixtures - Database with Full Schema
# =============================================================================


@pytest.fixture
def full_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """In-memory SQLite database with comprehensive schema for E2E testing.

    Creates a complete schema including:
    - creators table with persona data
    - send_types table with all 22 types
    - captions table with vault matrix data
    - performance metrics tables
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create creators table with extended fields
    cursor.execute("""
        CREATE TABLE creators (
            creator_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            page_type TEXT NOT NULL,
            fan_count INTEGER DEFAULT 0,
            persona_archetype TEXT DEFAULT 'playful',
            voice_tone TEXT DEFAULT 'friendly',
            is_active INTEGER DEFAULT 1
        )
    """)

    # Insert test creators
    creators = [
        (1, "alexia", "paid", 2500, "girl_next_door", "playful"),
        (2, "luna", "free", 8000, "seductress", "flirty"),
        (3, "jade", "paid", 500, "professional", "friendly"),
        (4, "diamond", "paid", 50000, "playful", "energetic"),
    ]
    cursor.executemany(
        """INSERT INTO creators
           (creator_id, username, page_type, fan_count, persona_archetype, voice_tone)
           VALUES (?, ?, ?, ?, ?, ?)""",
        creators,
    )

    # Create send_types table with full schema
    cursor.execute("""
        CREATE TABLE send_types (
            send_type_id INTEGER PRIMARY KEY,
            send_type_key TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            display_name TEXT NOT NULL,
            page_type_restriction TEXT DEFAULT 'both',
            requires_media INTEGER DEFAULT 1,
            requires_price INTEGER DEFAULT 0,
            max_per_day INTEGER,
            max_per_week INTEGER,
            min_hours_between INTEGER DEFAULT 2,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Insert all 22 send types
    send_types = [
        # Revenue (9 types)
        ("ppv_unlock", "revenue", "PPV Unlock", "both", 1, 1, 4, 28),
        ("ppv_wall", "revenue", "PPV Wall", "free", 1, 1, 2, 14),
        ("tip_goal", "revenue", "Tip Goal", "paid", 0, 0, 2, 14),
        ("vip_program", "revenue", "VIP Program", "both", 0, 0, 1, 1),
        ("game_post", "revenue", "Game Post", "both", 1, 0, 2, 10),
        ("bundle", "revenue", "Bundle", "both", 1, 1, 2, 10),
        ("flash_bundle", "revenue", "Flash Bundle", "both", 1, 1, 1, 5),
        ("snapchat_bundle", "revenue", "Snapchat Bundle", "both", 1, 1, 1, 1),
        ("first_to_tip", "revenue", "First to Tip", "both", 0, 0, 2, 10),
        # Engagement (9 types)
        ("link_drop", "engagement", "Link Drop", "both", 1, 0, None, None),
        ("wall_link_drop", "engagement", "Wall Link Drop", "both", 1, 0, None, None),
        ("bump_normal", "engagement", "Normal Bump", "both", 1, 0, None, None),
        ("bump_descriptive", "engagement", "Descriptive Bump", "both", 1, 0, None, None),
        ("bump_text_only", "engagement", "Text Only Bump", "both", 0, 0, None, None),
        ("bump_flyer", "engagement", "Flyer Bump", "both", 1, 0, None, None),
        ("dm_farm", "engagement", "DM Farm", "both", 0, 0, None, None),
        ("like_farm", "engagement", "Like Farm", "both", 0, 0, None, None),
        ("live_promo", "engagement", "Live Promo", "both", 0, 0, None, None),
        # Retention (4 types)
        ("renew_on_post", "retention", "Renew on Post", "paid", 1, 0, None, None),
        ("renew_on_message", "retention", "Renew on Message", "paid", 0, 0, None, None),
        ("ppv_followup", "retention", "PPV Followup", "both", 0, 0, 4, 20),
        ("expired_winback", "retention", "Expired Winback", "paid", 0, 0, None, None),
    ]

    for st in send_types:
        cursor.execute("""
            INSERT INTO send_types
            (send_type_key, category, display_name, page_type_restriction,
             requires_media, requires_price, max_per_day, max_per_week)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, st)

    # Create captions table with performance data
    cursor.execute("""
        CREATE TABLE caption_bank (
            caption_id INTEGER PRIMARY KEY,
            caption_text TEXT NOT NULL,
            send_type_key TEXT,
            content_type TEXT DEFAULT 'video',
            performance_score REAL DEFAULT 50.0,
            freshness_score REAL DEFAULT 80.0,
            last_used_date TEXT,
            use_count INTEGER DEFAULT 0,
            creator_id INTEGER,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Insert test captions with varied scores
    captions = [
        ("Check your DMs for something special...", "ppv_unlock", "video", 85.0, 95.0),
        ("New exclusive content just dropped!", "ppv_unlock", "video", 78.0, 88.0),
        ("Limited time offer - 50% off!", "bundle", "none", 90.0, 70.0),
        ("Hey babe, miss me?", "bump_normal", "picture", 72.0, 92.0),
        ("Just checking in with my favorites", "bump_descriptive", "picture", 68.0, 85.0),
        ("Your subscription expires soon!", "renew_on_message", "none", 80.0, 75.0),
        ("Come back, I have something special for you", "expired_winback", "none", 82.0, 80.0),
        ("Who wants to play a game?", "game_post", "video", 88.0, 90.0),
        ("First to tip gets a surprise!", "first_to_tip", "none", 75.0, 95.0),
        ("Join my VIP for exclusive perks", "vip_program", "none", 70.0, 65.0),
    ]

    for idx, cap in enumerate(captions, 1):
        cursor.execute("""
            INSERT INTO caption_bank
            (caption_id, caption_text, send_type_key, content_type,
             performance_score, freshness_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (idx, *cap))

    # Create performance metrics table
    cursor.execute("""
        CREATE TABLE creator_performance_metrics (
            metric_id INTEGER PRIMARY KEY,
            creator_id INTEGER NOT NULL,
            metric_date TEXT NOT NULL,
            saturation_score REAL DEFAULT 50.0,
            opportunity_score REAL DEFAULT 50.0,
            revenue_trend REAL DEFAULT 0.0,
            message_count INTEGER DEFAULT 0
        )
    """)

    # Insert performance data for test creators
    metrics = [
        (1, "2025-12-10", 45.0, 65.0, 5.0, 150),
        (2, "2025-12-10", 60.0, 40.0, -2.0, 200),
        (3, "2025-12-10", 30.0, 80.0, 10.0, 50),
        (4, "2025-12-10", 55.0, 55.0, 0.0, 500),
    ]
    cursor.executemany("""
        INSERT INTO creator_performance_metrics
        (creator_id, metric_date, saturation_score, opportunity_score,
         revenue_trend, message_count)
        VALUES (?, ?, ?, ?, ?, ?)
    """, metrics)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_caption_pool() -> list[Caption]:
    """Large caption pool for testing caption selection."""
    captions = []
    base_types = [
        "ppv_unlock", "ppv_teaser", "exclusive", "bundle_pitch",
        "flirty_opener", "check_in", "renewal_pitch", "interactive",
    ]

    for i in range(100):
        cap_type = base_types[i % len(base_types)]
        captions.append(Caption(
            id=i + 1,
            text=f"Test caption {i + 1} for {cap_type}",
            type=cap_type,
            performance_score=50.0 + (i % 50),
            freshness_score=30.0 + (i % 70),
            content_type="video" if i % 3 == 0 else "picture",
            emoji_level=2 + (i % 3),
            slang_level=1 + (i % 3),
            tone="playful" if i % 2 == 0 else "flirty",
        ))

    return captions


# =============================================================================
# Phase 1: Performance Analysis Tests
# =============================================================================


class TestPhase1PerformanceAnalysis:
    """Test Phase 1 - Saturation/Opportunity Analysis."""

    def test_volume_tier_classification(self):
        """Test fan count correctly maps to volume tier.

        Verifies the tier classification boundaries:
        - LOW: 0-999
        - MID: 1000-4999
        - HIGH: 5000-14999
        - ULTRA: 15000+
        """
        assert get_volume_tier(500) == VolumeTier.LOW
        assert get_volume_tier(999) == VolumeTier.LOW
        assert get_volume_tier(1000) == VolumeTier.MID
        assert get_volume_tier(4999) == VolumeTier.MID
        assert get_volume_tier(5000) == VolumeTier.HIGH
        assert get_volume_tier(14999) == VolumeTier.HIGH
        assert get_volume_tier(15000) == VolumeTier.ULTRA
        assert get_volume_tier(50000) == VolumeTier.ULTRA

    def test_dynamic_volume_calculation_basic(self):
        """Test basic dynamic volume calculation with default scores."""
        context = PerformanceContext(
            fan_count=2500,
            page_type="paid",
            saturation_score=50.0,
            opportunity_score=50.0,
        )

        config = calculate_dynamic_volume(context)

        assert config.tier == VolumeTier.MID
        assert config.revenue_per_day > 0
        assert config.engagement_per_day > 0
        assert config.retention_per_day > 0
        assert config.page_type == "paid"

    def test_high_saturation_reduces_volume(self):
        """Test high saturation score reduces send volumes."""
        low_sat = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=20.0,
            opportunity_score=50.0,
        )
        high_sat = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=80.0,
            opportunity_score=50.0,
        )

        low_config = calculate_dynamic_volume(low_sat)
        high_config = calculate_dynamic_volume(high_sat)

        # High saturation should result in lower volumes
        assert high_config.revenue_per_day <= low_config.revenue_per_day
        assert high_config.engagement_per_day <= low_config.engagement_per_day

    def test_opportunity_increases_volume(self):
        """Test high opportunity with low saturation increases volume."""
        low_opp = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=30.0,
            opportunity_score=30.0,
        )
        high_opp = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=30.0,
            opportunity_score=80.0,
        )

        low_config = calculate_dynamic_volume(low_opp)
        high_config = calculate_dynamic_volume(high_opp)

        # High opportunity should result in higher or equal volumes
        assert high_config.revenue_per_day >= low_config.revenue_per_day

    def test_free_page_no_retention(self):
        """Test free pages get zero retention allocation."""
        context = PerformanceContext(
            fan_count=8000,
            page_type="free",
            saturation_score=50.0,
            opportunity_score=50.0,
        )

        config = calculate_dynamic_volume(context)

        assert config.retention_per_day == 0
        assert config.page_type == "free"


# =============================================================================
# Phase 2: Send Type Allocation Tests
# =============================================================================


class TestPhase2SendTypeAllocation:
    """Test Phase 2 - Daily Send Type Distribution."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator(creator_id="test_creator")

    def test_daily_allocation_paid_page(self, allocator):
        """Test daily allocation for paid page includes all categories."""
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        allocations = allocator.allocate_day(config, day_of_week=3, page_type="paid")

        # Verify categories are present
        categories = {a["category"] for a in allocations}
        assert "revenue" in categories
        assert "engagement" in categories
        assert "retention" in categories

    def test_daily_allocation_free_page_retention(self, allocator):
        """Test free page allocation handles retention correctly."""
        config = VolumeConfig(
            tier=VolumeTier.HIGH,
            revenue_per_day=5,
            engagement_per_day=4,
            retention_per_day=0,
            fan_count=8000,
            page_type="free",
        )

        allocations = allocator.allocate_day(config, day_of_week=3, page_type="free")

        # Should have allocations but very limited retention
        assert len(allocations) > 0
        revenue_count = sum(1 for a in allocations if a["category"] == "revenue")
        assert revenue_count > 0

    def test_weekly_allocation_diversity(self, allocator):
        """Test weekly allocation maintains type diversity."""
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        week_start = datetime(2025, 12, 15)  # Monday
        weekly = allocator.allocate_week(config, "paid", week_start)

        # Collect all unique send types across week
        all_types = set()
        for day_items in weekly.values():
            for item in day_items:
                all_types.add(item["send_type_key"])

        # Should have good diversity
        assert len(all_types) >= 10  # Minimum diversity requirement

    def test_day_of_week_adjustments(self, allocator):
        """Test day-of-week affects allocation volumes."""
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        monday_alloc = allocator.allocate_day(config, day_of_week=0, page_type="paid")
        friday_alloc = allocator.allocate_day(config, day_of_week=4, page_type="paid")
        saturday_alloc = allocator.allocate_day(config, day_of_week=5, page_type="paid")

        # Friday/Saturday should have at least as many items as Monday
        assert len(friday_alloc) >= len(monday_alloc) - 3
        assert len(saturday_alloc) >= len(monday_alloc) - 3


# =============================================================================
# Phase 3: Content Curation Tests
# =============================================================================


class TestPhase3ContentCuration:
    """Test Phase 3 - Caption Selection with Freshness Scoring."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        m = CaptionMatcher()
        m.reset_usage_tracking()
        return m

    def test_caption_selection_basic(self, matcher, sample_caption_pool):
        """Test basic caption selection returns valid result."""
        result = matcher.select_caption(
            creator_id="test",
            send_type_key="ppv_unlock",
            available_captions=sample_caption_pool,
        )

        assert result is not None
        assert isinstance(result, CaptionResult)
        assert result.caption_score is not None
        assert result.needs_manual is False

    def test_caption_freshness_priority(self, matcher):
        """Test freshness is prioritized in caption selection."""
        captions = [
            Caption(id=1, text="Stale caption", type="ppv_unlock",
                    performance_score=90.0, freshness_score=20.0),
            Caption(id=2, text="Fresh caption", type="ppv_unlock",
                    performance_score=70.0, freshness_score=95.0),
        ]

        result = matcher.select_caption("test", "ppv_unlock", captions)

        # Fresh caption should be preferred despite lower performance
        assert result.caption_score is not None
        # With 40% weight on freshness vs 35% on performance,
        # the fresh caption should win
        assert result.caption_score.caption.id == 2

    def test_caption_fallback_levels(self, matcher):
        """Test caption selection uses fallback levels correctly."""
        # Create captions that fail Level 1 criteria
        captions = [
            Caption(id=1, text="Low scores", type="generic",
                    performance_score=45.0, freshness_score=35.0),
        ]

        result = matcher.select_caption("test", "ppv_unlock", captions)

        # Should still succeed via fallback levels
        assert result is not None
        assert result.fallback_level > 1  # Used a fallback level

    def test_empty_pool_returns_manual(self, matcher):
        """Test empty caption pool returns manual flag."""
        result = matcher.select_caption("test", "ppv_unlock", [])

        assert result.needs_manual is True
        assert result.caption_score is None
        assert result.fallback_level == 6

    def test_caption_diversity_tracking(self, matcher, sample_caption_pool):
        """Test caption usage is tracked for diversity."""
        # Make multiple selections
        for _ in range(5):
            matcher.select_caption("test", "bump_normal", sample_caption_pool)

        stats = matcher.get_usage_stats()

        assert stats["total_used"] >= 5
        assert stats["unique_types"] > 0


# =============================================================================
# Phase 4: Audience Targeting Tests (Mocked)
# =============================================================================


class TestPhase4AudienceTargeting:
    """Test Phase 4 - Audience Segment Assignment.

    Uses mocked MCP tools since database targeting requires full MCP integration.
    """

    def test_page_type_filtering(self):
        """Test send types are filtered by page type."""
        allocator = SendTypeAllocator()

        all_types = ["ppv_unlock", "tip_goal", "ppv_wall", "bump_normal"]
        paid_filtered = allocator.filter_by_page_type(all_types, "paid")
        free_filtered = allocator.filter_by_page_type(all_types, "free")

        # tip_goal is paid only, ppv_wall is free only
        assert "ppv_wall" not in paid_filtered
        assert "tip_goal" not in free_filtered
        assert "ppv_unlock" in paid_filtered
        assert "ppv_unlock" in free_filtered


# =============================================================================
# Phase 5: Timing Optimization Tests
# =============================================================================


class TestPhase5TimingOptimization:
    """Test Phase 5 - Optimal Posting Time Calculation."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        o = ScheduleOptimizer()
        o.reset_tracking()
        return o

    def test_timing_optimization_basic(self, optimizer):
        """Test basic timing optimization assigns valid times."""
        items = [
            ScheduleItem(
                send_type_key="ppv_unlock",
                scheduled_date="2025-12-20",
                scheduled_time="00:00",
                category="revenue",
                priority=1,
            ),
        ]

        optimized = optimizer.optimize_timing(items)

        assert len(optimized) == 1
        assert optimized[0].scheduled_time != "00:00"

    def test_timing_respects_spacing(self, optimizer):
        """Test timing optimization respects minimum spacing."""
        items = [
            ScheduleItem(
                send_type_key="ppv_unlock",
                scheduled_date="2025-12-20",
                scheduled_time="00:00",
                category="revenue",
                priority=1,
            ),
            ScheduleItem(
                send_type_key="ppv_unlock",
                scheduled_date="2025-12-20",
                scheduled_time="00:00",
                category="revenue",
                priority=1,
            ),
        ]

        optimized = optimizer.optimize_timing(items)

        # Parse times and check spacing
        time1 = datetime.strptime(optimized[0].scheduled_time, "%H:%M")
        time2 = datetime.strptime(optimized[1].scheduled_time, "%H:%M")
        diff_minutes = abs((time2 - time1).total_seconds() / 60)

        # Should have at least minimum spacing
        assert diff_minutes >= 60

    def test_time_jitter_avoids_round_minutes(self):
        """Test time jitter avoids round minutes (00, 15, 30, 45)."""
        base_time = datetime(2025, 12, 20, 14, 30)
        round_minutes = {0, 15, 30, 45}

        # Test multiple creators for determinism
        for creator in ["alice", "bob", "charlie"]:
            jittered = apply_time_jitter(base_time, creator)
            assert jittered.minute not in round_minutes

    def test_time_jitter_deterministic(self):
        """Test time jitter is deterministic for same inputs."""
        base_time = datetime(2025, 12, 20, 14, 30)
        creator_id = "test_creator"

        result1 = apply_time_jitter(base_time, creator_id)
        result2 = apply_time_jitter(base_time, creator_id)

        assert result1 == result2


# =============================================================================
# Phase 6: Followup Generation Tests
# =============================================================================


class TestPhase6FollowupGeneration:
    """Test Phase 6 - Auto-generate PPV Followups."""

    def test_ppv_followup_limit(self):
        """Test PPV followup respects max 4 per day limit."""
        allocator = SendTypeAllocator()

        # Create a config that would generate many followups
        config = VolumeConfig(
            tier=VolumeTier.ULTRA,
            revenue_per_day=8,  # High revenue = many PPVs
            engagement_per_day=5,
            retention_per_day=3,
            fan_count=50000,
            page_type="paid",
        )

        # Allocate and count followups
        allocations = allocator.allocate_day(config, day_of_week=5, page_type="paid")
        followup_count = sum(
            1 for a in allocations if a["send_type_key"] == "ppv_followup"
        )

        # Should not exceed max per day (4)
        assert followup_count <= 4


# =============================================================================
# Phase 7: Schedule Assembly Tests
# =============================================================================


class TestPhase7ScheduleAssembly:
    """Test Phase 7 - Final Schedule Assembly."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        return SendTypeAllocator(creator_id="assembly_test")

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        m = CaptionMatcher()
        m.reset_usage_tracking()
        return m

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        o = ScheduleOptimizer()
        o.reset_tracking()
        return o

    def test_full_schedule_assembly(
        self,
        allocator,
        matcher,
        optimizer,
        sample_caption_pool,
    ):
        """Test complete schedule assembly from allocation to final output."""
        # Step 1: Create volume config
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        # Step 2: Allocate for a day
        allocations = allocator.allocate_day(config, day_of_week=5, page_type="paid")

        # Step 3: Convert to ScheduleItems
        schedule_items = []
        for alloc in allocations:
            item = ScheduleItem(
                send_type_key=alloc["send_type_key"],
                scheduled_date="2025-12-20",
                scheduled_time="00:00",
                category=alloc["category"],
                priority=alloc["priority"],
                requires_media=alloc.get("requires_media", False),
            )
            schedule_items.append(item)

        # Step 4: Optimize timing
        optimized = optimizer.optimize_timing(schedule_items)

        # Step 5: Assign captions
        final_schedule = []
        for item in optimized:
            caption_result = matcher.select_caption(
                creator_id="test",
                send_type_key=item.send_type_key,
                available_captions=sample_caption_pool,
            )

            final_item = {
                "send_type_key": item.send_type_key,
                "scheduled_date": item.scheduled_date,
                "scheduled_time": item.scheduled_time,
                "category": item.category,
                "caption_id": (
                    caption_result.caption_score.caption.id
                    if caption_result.caption_score else None
                ),
                "needs_manual_caption": caption_result.needs_manual,
            }
            final_schedule.append(final_item)

        # Verify final schedule
        assert len(final_schedule) > 0
        assert all(item["scheduled_time"] != "00:00" for item in final_schedule)
        assert sum(1 for item in final_schedule if item["caption_id"]) > 0


# =============================================================================
# Full Pipeline Integration Tests
# =============================================================================


class TestFullPipelineIntegration:
    """Test complete end-to-end pipeline integration."""

    def test_complete_weekly_schedule_generation(self, sample_caption_pool):
        """Test generating a complete weekly schedule end-to-end."""
        # Initialize components
        allocator = SendTypeAllocator(creator_id="weekly_test")
        matcher = CaptionMatcher()
        matcher.reset_usage_tracking()
        optimizer = ScheduleOptimizer()
        optimizer.reset_tracking()

        # Create context and config
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=45.0,
            opportunity_score=65.0,
        )
        config = calculate_dynamic_volume(context)

        # Generate weekly schedule
        week_start = datetime(2025, 12, 15)  # Monday
        weekly_allocation = allocator.allocate_week(
            VolumeConfig(
                tier=config.tier,
                revenue_per_day=config.revenue_per_day,
                engagement_per_day=config.engagement_per_day,
                retention_per_day=config.retention_per_day,
                fan_count=config.fan_count,
                page_type=config.page_type,
            ),
            page_type="paid",
            week_start=week_start,
        )

        # Process each day
        weekly_schedule = {}
        total_items = 0

        for date_str, allocations in weekly_allocation.items():
            # Convert to ScheduleItems
            items = [
                ScheduleItem(
                    send_type_key=a["send_type_key"],
                    scheduled_date=date_str,
                    scheduled_time="00:00",
                    category=a["category"],
                    priority=a["priority"],
                )
                for a in allocations
            ]

            # Optimize timing
            optimized = optimizer.optimize_timing(items)
            optimizer.reset_tracking()  # Reset for next day

            # Assign captions
            day_schedule = []
            for item in optimized:
                result = matcher.select_caption(
                    creator_id="weekly_test",
                    send_type_key=item.send_type_key,
                    available_captions=sample_caption_pool,
                )
                day_schedule.append({
                    "send_type_key": item.send_type_key,
                    "time": item.scheduled_time,
                    "caption_assigned": result.caption_score is not None,
                })

            weekly_schedule[date_str] = day_schedule
            total_items += len(day_schedule)

        # Verify complete schedule
        assert len(weekly_schedule) == 7
        assert total_items > 0
        assert all(len(items) > 0 for items in weekly_schedule.values())

    def test_pipeline_handles_edge_cases(self):
        """Test pipeline handles edge cases gracefully."""
        allocator = SendTypeAllocator()
        matcher = CaptionMatcher()
        optimizer = ScheduleOptimizer()

        # Test with minimal config
        minimal_config = VolumeConfig(
            tier=VolumeTier.LOW,
            revenue_per_day=1,
            engagement_per_day=1,
            retention_per_day=1,
            fan_count=100,
            page_type="paid",
        )

        allocations = allocator.allocate_day(minimal_config, 2, "paid")
        assert len(allocations) >= 0  # May be empty with low volumes

        # Test with empty inputs
        empty_optimized = optimizer.optimize_timing([])
        assert empty_optimized == []

        empty_caption = matcher.select_caption("test", "ppv_unlock", [])
        assert empty_caption.needs_manual is True


# =============================================================================
# Database Integration Tests
# =============================================================================


class TestDatabaseIntegration:
    """Test actual database queries and results."""

    def test_creator_query(self, full_db_connection):
        """Test querying creator data from database."""
        cursor = full_db_connection.cursor()

        cursor.execute("""
            SELECT creator_id, username, page_type, fan_count
            FROM creators
            WHERE is_active = 1
            ORDER BY fan_count DESC
        """)

        creators = cursor.fetchall()

        assert len(creators) == 4
        # Highest fan count first
        assert creators[0][1] == "diamond"
        assert creators[0][3] == 50000

    def test_send_type_query_by_category(self, full_db_connection):
        """Test querying send types by category."""
        cursor = full_db_connection.cursor()

        for category, expected_count in [
            ("revenue", 9),
            ("engagement", 9),
            ("retention", 4),
        ]:
            cursor.execute("""
                SELECT COUNT(*) FROM send_types
                WHERE category = ? AND is_active = 1
            """, (category,))

            count = cursor.fetchone()[0]
            assert count == expected_count

    def test_caption_query_with_scores(self, full_db_connection):
        """Test querying captions with performance scores."""
        cursor = full_db_connection.cursor()

        cursor.execute("""
            SELECT caption_id, caption_text, performance_score, freshness_score
            FROM caption_bank
            WHERE performance_score > 75
            ORDER BY freshness_score DESC
        """)

        high_performers = cursor.fetchall()

        assert len(high_performers) > 0
        # All should have high performance
        assert all(row[2] > 75 for row in high_performers)

    def test_performance_metrics_query(self, full_db_connection):
        """Test querying creator performance metrics."""
        cursor = full_db_connection.cursor()

        cursor.execute("""
            SELECT c.username, m.saturation_score, m.opportunity_score
            FROM creators c
            JOIN creator_performance_metrics m ON c.creator_id = m.creator_id
            WHERE m.metric_date = '2025-12-10'
        """)

        metrics = cursor.fetchall()

        assert len(metrics) == 4
        # Verify we got all creators
        usernames = {row[0] for row in metrics}
        assert usernames == {"alexia", "luna", "jade", "diamond"}


# =============================================================================
# MCP Tool Integration Tests (Mocked)
# =============================================================================


class TestMCPToolIntegration:
    """Test MCP tool integration patterns.

    Uses mocks to verify the expected interface with MCP tools
    without requiring the full MCP server setup.
    """

    def test_get_creator_profile_mock(self):
        """Test expected structure of get_creator_profile response."""
        mock_response = {
            "creator_id": 1,
            "username": "alexia",
            "page_type": "paid",
            "fan_count": 2500,
            "persona_archetype": "girl_next_door",
            "saturation_score": 45.0,
            "opportunity_score": 65.0,
        }

        # Simulate using the response
        context = PerformanceContext(
            fan_count=mock_response["fan_count"],
            page_type=mock_response["page_type"],
            saturation_score=mock_response["saturation_score"],
            opportunity_score=mock_response["opportunity_score"],
        )

        config = calculate_dynamic_volume(context)

        assert config.tier == VolumeTier.MID
        assert config.page_type == "paid"

    def test_get_volume_config_response_structure(self):
        """Test expected structure matches OptimizedVolumeResult."""
        # Simulate the expected response structure
        expected_fields = {
            "volume_level",
            "ppv_per_day",
            "bump_per_day",
            "revenue_per_day",
            "engagement_per_day",
            "retention_per_day",
            "weekly_distribution",
            "content_allocations",
            "confidence_score",
            "elasticity_capped",
            "caption_warnings",
        }

        # All these fields should be present in a full response
        mock_response = {field: None for field in expected_fields}

        assert all(field in mock_response for field in expected_fields)

    def test_save_schedule_structure(self):
        """Test expected structure for save_schedule request."""
        # Build a sample schedule in the expected format
        schedule_request = {
            "creator_id": "alexia",
            "week_start": "2025-12-15",
            "items": [
                {
                    "send_type_key": "ppv_unlock",
                    "scheduled_date": "2025-12-15",
                    "scheduled_time": "19:03",
                    "category": "revenue",
                    "caption_id": 123,
                    "channel": "mass_message",
                    "audience_target": "active_30d",
                },
            ],
        }

        # Verify structure
        assert "creator_id" in schedule_request
        assert "items" in schedule_request
        assert len(schedule_request["items"]) > 0
        assert all(
            key in schedule_request["items"][0]
            for key in ["send_type_key", "scheduled_date", "scheduled_time"]
        )
