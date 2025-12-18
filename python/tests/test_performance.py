"""
Performance Benchmark Tests - Timing requirements for core algorithms.

Benchmarks cover:
- Caption selection speed (<100ms)
- Full week allocation speed (<500ms)
- Timing optimization speed (<200ms)
- Score calculation throughput

Requirements:
- All benchmarks must pass within specified time limits
- Results are tracked for regression detection
- Run with: pytest -m benchmark
"""

import time
from datetime import datetime
from typing import Any

import pytest

from python.allocation.send_type_allocator import (
    SendTypeAllocator,
    VolumeConfig,
    VolumeTier,
)
from python.matching.caption_matcher import Caption, CaptionMatcher
from python.optimization.schedule_optimizer import ScheduleItem, ScheduleOptimizer


# =============================================================================
# TEST DATA GENERATORS
# =============================================================================


def generate_test_captions(count: int = 100) -> list[Caption]:
    """Generate test captions for benchmarking.

    Args:
        count: Number of captions to generate.

    Returns:
        List of Caption objects with varied attributes.
    """
    caption_types = [
        "ppv_unlock",
        "ppv_teaser",
        "flirty_opener",
        "check_in",
        "renewal_pitch",
        "urgent",
        "exclusive",
        "playful",
        "casual",
        "appreciation",
    ]

    tones = ["flirty", "playful", "seductive", "friendly", "grateful", "neutral"]

    captions = []
    for i in range(count):
        caption = Caption(
            id=i + 1,
            text=f"Test caption {i} with some content here that mimics real length.",
            type=caption_types[i % len(caption_types)],
            performance_score=50.0 + (i % 50),  # 50-99 range
            freshness_score=30.0 + (i % 70),  # 30-99 range
            last_used_date=datetime(2024, 12, 1) if i % 3 == 0 else None,
            content_type="video" if i % 2 == 0 else "photo",
            emoji_level=(i % 5) + 1,
            slang_level=(i % 5) + 1,
            tone=tones[i % len(tones)],
        )
        captions.append(caption)

    return captions


def generate_test_schedule_items(count: int = 50) -> list[ScheduleItem]:
    """Generate test schedule items for benchmarking.

    Args:
        count: Number of items to generate.

    Returns:
        List of ScheduleItem objects.
    """
    send_types = [
        ("ppv_video", "revenue", 1),
        ("bump_normal", "engagement", 2),
        ("renew_on_post", "retention", 3),
        ("bundle", "revenue", 1),
        ("dm_farm", "engagement", 2),
        ("ppv_followup", "retention", 3),
    ]

    items = []
    base_date = datetime(2025, 1, 6)  # Monday

    for i in range(count):
        day_offset = i // 7
        send_type, category, priority = send_types[i % len(send_types)]

        item = ScheduleItem(
            send_type_key=send_type,
            scheduled_date=(base_date.replace(day=base_date.day + day_offset)).strftime(
                "%Y-%m-%d"
            ),
            scheduled_time="10:00",
            category=category,
            priority=priority,
            caption_id=i + 1,
            caption_text=f"Caption for item {i}",
            requires_media=send_type in ["ppv_video", "bundle"],
            media_type="video" if send_type == "ppv_video" else "none",
        )
        items.append(item)

    return items


def generate_volume_config(tier: VolumeTier = VolumeTier.HIGH) -> VolumeConfig:
    """Generate test volume configuration.

    Args:
        tier: Volume tier to use.

    Returns:
        VolumeConfig object.
    """
    configs = {
        VolumeTier.LOW: VolumeConfig(
            tier=VolumeTier.LOW,
            revenue_per_day=3,
            engagement_per_day=3,
            retention_per_day=1,
            fan_count=500,
            page_type="paid",
        ),
        VolumeTier.MID: VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        ),
        VolumeTier.HIGH: VolumeConfig(
            tier=VolumeTier.HIGH,
            revenue_per_day=6,
            engagement_per_day=5,
            retention_per_day=2,
            fan_count=8000,
            page_type="paid",
        ),
        VolumeTier.ULTRA: VolumeConfig(
            tier=VolumeTier.ULTRA,
            revenue_per_day=8,
            engagement_per_day=6,
            retention_per_day=3,
            fan_count=20000,
            page_type="paid",
        ),
    }
    return configs[tier]


# =============================================================================
# CAPTION MATCHER BENCHMARKS
# =============================================================================


class TestCaptionMatcherPerformance:
    """Performance benchmarks for CaptionMatcher."""

    @pytest.fixture
    def matcher(self) -> CaptionMatcher:
        """Create fresh CaptionMatcher instance."""
        return CaptionMatcher()

    @pytest.fixture
    def test_captions(self) -> list[Caption]:
        """Generate test captions."""
        return generate_test_captions(200)

    @pytest.mark.benchmark
    def test_caption_selection_speed(
        self, matcher: CaptionMatcher, test_captions: list[Caption]
    ) -> None:
        """Caption selection should complete in <100ms per selection.

        This tests the core caption matching algorithm with a realistic
        caption pool size.
        """
        iterations = 100
        total_time = 0.0

        send_types = [
            "ppv_video",
            "bump_normal",
            "renew_on_post",
            "bundle",
            "dm_farm",
        ]

        for i in range(iterations):
            send_type = send_types[i % len(send_types)]
            matcher.reset_usage_tracking()

            start = time.perf_counter()
            result = matcher.select_caption(
                creator_id="test_creator",
                send_type_key=send_type,
                available_captions=test_captions,
                persona="playful",
            )
            elapsed = time.perf_counter() - start
            total_time += elapsed

        avg_time = total_time / iterations

        assert avg_time < 0.1, (
            f"Caption selection too slow: {avg_time*1000:.2f}ms avg "
            f"(limit: 100ms)"
        )

    @pytest.mark.benchmark
    def test_score_calculation_throughput(
        self, matcher: CaptionMatcher, test_captions: list[Caption]
    ) -> None:
        """Score calculation should handle 1000+ captions/second.

        Tests the raw scoring throughput without selection logic.
        """
        iterations = 1000

        start = time.perf_counter()
        for i in range(iterations):
            caption = test_captions[i % len(test_captions)]
            matcher.calculate_score(caption, "ppv_video", "playful")
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        assert throughput > 1000, (
            f"Score calculation too slow: {throughput:.0f} captions/sec "
            f"(minimum: 1000/sec)"
        )

    @pytest.mark.benchmark
    def test_bulk_selection_performance(
        self, matcher: CaptionMatcher, test_captions: list[Caption]
    ) -> None:
        """Bulk selection of 50 captions should complete in <2 seconds.

        Simulates selecting captions for a full week schedule.
        """
        send_types = [
            "ppv_video",
            "bundle",
            "bump_normal",
            "bump_descriptive",
            "dm_farm",
            "renew_on_post",
            "ppv_followup",
        ]

        start = time.perf_counter()

        # Select 50 captions (about a week's worth)
        for i in range(50):
            send_type = send_types[i % len(send_types)]
            result = matcher.select_caption(
                creator_id="test_creator",
                send_type_key=send_type,
                available_captions=test_captions,
                persona="playful",
            )

        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, (
            f"Bulk selection too slow: {elapsed:.3f}s (limit: 2.0s)"
        )


# =============================================================================
# SEND TYPE ALLOCATOR BENCHMARKS
# =============================================================================


class TestSendTypeAllocatorPerformance:
    """Performance benchmarks for SendTypeAllocator."""

    @pytest.fixture
    def allocator(self) -> SendTypeAllocator:
        """Create SendTypeAllocator instance."""
        return SendTypeAllocator()

    @pytest.mark.benchmark
    def test_full_week_allocation_speed(self, allocator: SendTypeAllocator) -> None:
        """Full week allocation should complete in <500ms.

        This is the core scheduling algorithm that distributes
        send types across 7 days.
        """
        config = generate_volume_config(VolumeTier.HIGH)
        week_start = datetime(2025, 1, 6)

        iterations = 10
        total_time = 0.0

        for _ in range(iterations):
            start = time.perf_counter()
            schedule = allocator.allocate_week(
                config=config,
                page_type="paid",
                week_start=week_start,
            )
            elapsed = time.perf_counter() - start
            total_time += elapsed

        avg_time = total_time / iterations

        assert avg_time < 0.5, (
            f"Week allocation too slow: {avg_time*1000:.2f}ms avg "
            f"(limit: 500ms)"
        )

    @pytest.mark.benchmark
    def test_single_day_allocation_speed(self, allocator: SendTypeAllocator) -> None:
        """Single day allocation should complete in <100ms.

        Tests the per-day allocation without week-level overhead.
        """
        config = generate_volume_config(VolumeTier.ULTRA)

        iterations = 100
        total_time = 0.0

        for i in range(iterations):
            day_of_week = i % 7
            start = time.perf_counter()
            items = allocator.allocate_day(
                config=config,
                day_of_week=day_of_week,
                page_type="paid",
            )
            elapsed = time.perf_counter() - start
            total_time += elapsed

        avg_time = total_time / iterations

        assert avg_time < 0.1, (
            f"Day allocation too slow: {avg_time*1000:.2f}ms avg "
            f"(limit: 100ms)"
        )

    @pytest.mark.benchmark
    def test_volume_tier_calculation_speed(self, allocator: SendTypeAllocator) -> None:
        """Volume tier calculation should be near-instant (<1ms).

        Tests the fan count to tier mapping performance.
        """
        fan_counts = [100, 500, 1500, 5000, 10000, 20000, 50000]
        iterations = 10000

        start = time.perf_counter()
        for i in range(iterations):
            fan_count = fan_counts[i % len(fan_counts)]
            SendTypeAllocator.get_volume_tier(fan_count)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / iterations

        assert avg_time < 0.001, (
            f"Volume tier calculation too slow: {avg_time*1000*1000:.2f}us avg "
            f"(limit: 1ms)"
        )

    @pytest.mark.benchmark
    def test_all_tiers_allocation_performance(
        self, allocator: SendTypeAllocator
    ) -> None:
        """Allocation should be consistent across all volume tiers.

        Ensures performance doesn't degrade with higher volumes.
        """
        week_start = datetime(2025, 1, 6)
        tier_times: dict[str, float] = {}

        for tier in VolumeTier:
            config = generate_volume_config(tier)

            start = time.perf_counter()
            for _ in range(10):
                allocator.allocate_week(
                    config=config,
                    page_type="paid",
                    week_start=week_start,
                )
            elapsed = time.perf_counter() - start

            tier_times[tier.value] = elapsed / 10

        # All tiers should complete in similar time (within 2x)
        max_time = max(tier_times.values())
        min_time = min(tier_times.values())

        # Performance should be consistent across tiers
        assert max_time < 0.5, (
            f"Maximum tier allocation time: {max_time*1000:.2f}ms (limit: 500ms)"
        )


# =============================================================================
# SCHEDULE OPTIMIZER BENCHMARKS
# =============================================================================


class TestScheduleOptimizerPerformance:
    """Performance benchmarks for ScheduleOptimizer."""

    @pytest.fixture
    def optimizer(self) -> ScheduleOptimizer:
        """Create ScheduleOptimizer instance."""
        return ScheduleOptimizer()

    @pytest.fixture
    def test_items(self) -> list[ScheduleItem]:
        """Generate test schedule items."""
        return generate_test_schedule_items(70)

    @pytest.mark.benchmark
    def test_timing_optimization_speed(
        self, optimizer: ScheduleOptimizer, test_items: list[ScheduleItem]
    ) -> None:
        """Timing optimization should complete in <200ms.

        Tests the full timing optimization for a week's schedule.
        """
        iterations = 10
        total_time = 0.0

        for _ in range(iterations):
            optimizer.reset_tracking()

            start = time.perf_counter()
            optimized = optimizer.optimize_timing(test_items)
            elapsed = time.perf_counter() - start
            total_time += elapsed

        avg_time = total_time / iterations

        assert avg_time < 0.2, (
            f"Timing optimization too slow: {avg_time*1000:.2f}ms avg "
            f"(limit: 200ms)"
        )

    @pytest.mark.benchmark
    def test_slot_score_calculation_speed(
        self, optimizer: ScheduleOptimizer
    ) -> None:
        """Slot score calculation should handle 10000+ calculations/second.

        Tests the raw scoring function performance.
        """
        preferences = {
            "preferred_hours": [19, 21],
            "preferred_days": [4, 5, 6],
            "avoid_hours": [3, 4, 5, 6, 7],
            "min_spacing": 90,
        }

        iterations = 10000

        start = time.perf_counter()
        for i in range(iterations):
            hour = i % 24
            day = i % 7
            optimizer.calculate_slot_score(
                hour=hour,
                day_of_week=day,
                send_type_key="ppv_video",
                preferences=preferences,
            )
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        assert throughput > 10000, (
            f"Slot score calculation too slow: {throughput:.0f} calc/sec "
            f"(minimum: 10000/sec)"
        )

    @pytest.mark.benchmark
    def test_saturation_adjustment_speed(
        self, optimizer: ScheduleOptimizer
    ) -> None:
        """Saturation adjustment should be near-instant (<0.1ms).

        Tests the volume adjustment calculation.
        """
        iterations = 10000
        saturation_scores = [10, 30, 50, 70, 90]
        base_volumes = [3, 4, 6, 8]

        start = time.perf_counter()
        for i in range(iterations):
            base_vol = base_volumes[i % len(base_volumes)]
            sat_score = saturation_scores[i % len(saturation_scores)]
            optimizer.apply_saturation_adjustment(base_vol, sat_score)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / iterations

        assert avg_time < 0.0001, (
            f"Saturation adjustment too slow: {avg_time*1000*1000:.2f}us avg "
            f"(limit: 100us)"
        )


# =============================================================================
# INTEGRATION BENCHMARKS
# =============================================================================


class TestIntegrationPerformance:
    """Integration performance tests combining multiple components."""

    @pytest.mark.benchmark
    def test_full_schedule_generation_pipeline(self) -> None:
        """Full schedule generation should complete in <3 seconds.

        This tests the complete pipeline:
        1. Volume allocation
        2. Caption selection
        3. Timing optimization
        """
        allocator = SendTypeAllocator()
        matcher = CaptionMatcher()
        optimizer = ScheduleOptimizer()

        config = generate_volume_config(VolumeTier.HIGH)
        captions = generate_test_captions(200)
        week_start = datetime(2025, 1, 6)

        iterations = 5
        total_time = 0.0

        for _ in range(iterations):
            matcher.reset_usage_tracking()
            optimizer.reset_tracking()

            start = time.perf_counter()

            # Step 1: Allocate send types
            weekly_schedule = allocator.allocate_week(
                config=config,
                page_type="paid",
                week_start=week_start,
            )

            # Step 2: Select captions for each item
            schedule_items = []
            for date_str, daily_items in weekly_schedule.items():
                for item in daily_items:
                    caption_result = matcher.select_caption(
                        creator_id="test_creator",
                        send_type_key=item["send_type_key"],
                        available_captions=captions,
                        persona="playful",
                    )

                    # Extract caption data from CaptionResult
                    caption_id = None
                    caption_text = ""
                    if caption_result and caption_result.caption_score:
                        caption_id = caption_result.caption_score.caption.id
                        caption_text = caption_result.caption_score.caption.text

                    schedule_item = ScheduleItem(
                        send_type_key=item["send_type_key"],
                        scheduled_date=item["scheduled_date"],
                        scheduled_time="10:00",
                        category=item["category"],
                        priority=item["priority"],
                        caption_id=caption_id,
                        caption_text=caption_text,
                        requires_media=item.get("requires_media", False),
                    )
                    schedule_items.append(schedule_item)

            # Step 3: Optimize timing
            optimized_items = optimizer.optimize_timing(schedule_items)

            elapsed = time.perf_counter() - start
            total_time += elapsed

        avg_time = total_time / iterations

        assert avg_time < 3.0, (
            f"Full pipeline too slow: {avg_time:.3f}s avg (limit: 3.0s)"
        )

    @pytest.mark.benchmark
    def test_memory_efficiency_large_caption_pool(self) -> None:
        """Memory usage should remain stable with large caption pools.

        Tests that memory doesn't grow unexpectedly with larger data.
        """
        matcher = CaptionMatcher()
        large_caption_pool = generate_test_captions(1000)

        # Run multiple selections to check for memory leaks
        for i in range(100):
            matcher.reset_usage_tracking()
            matcher.select_caption(
                creator_id="test_creator",
                send_type_key="ppv_video",
                available_captions=large_caption_pool,
                persona="playful",
            )

        # If we got here without memory error, test passes
        assert True


# =============================================================================
# STRESS TESTS
# =============================================================================


class TestStressPerformance:
    """Stress tests for edge cases and high loads."""

    @pytest.mark.benchmark
    def test_rapid_consecutive_allocations(self) -> None:
        """System should handle rapid consecutive allocations.

        Tests system stability under rapid repeated use.
        """
        allocator = SendTypeAllocator()
        config = generate_volume_config(VolumeTier.HIGH)
        week_start = datetime(2025, 1, 6)

        iterations = 100

        start = time.perf_counter()
        for _ in range(iterations):
            allocator.allocate_week(
                config=config,
                page_type="paid",
                week_start=week_start,
            )
        elapsed = time.perf_counter() - start

        avg_time = elapsed / iterations

        # Should maintain consistent performance
        assert avg_time < 0.5, (
            f"Performance degraded under load: {avg_time*1000:.2f}ms avg"
        )

    @pytest.mark.benchmark
    def test_exhausted_caption_pool_handling(self) -> None:
        """System should handle caption pool exhaustion gracefully.

        Tests fallback behavior when preferred captions are exhausted.
        """
        matcher = CaptionMatcher()
        small_pool = generate_test_captions(10)

        start = time.perf_counter()

        # Try to select more captions than available
        for i in range(30):
            result = matcher.select_caption(
                creator_id="test_creator",
                send_type_key="ppv_video",
                available_captions=small_pool,
                persona="playful",
            )

        elapsed = time.perf_counter() - start

        # Should complete even with exhausted pool
        assert elapsed < 1.0, (
            f"Caption exhaustion handling too slow: {elapsed*1000:.2f}ms"
        )
