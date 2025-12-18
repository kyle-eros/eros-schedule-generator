"""
Performance benchmark tests for EROS Schedule Generator.

Uses pytest-benchmark to measure and track performance of critical paths.
Run with: pytest python/tests/test_benchmarks.py -v --benchmark-only

Performance Targets:
    - caption_matcher.match_captions(): < 100ms for 1000 captions
    - send_type_allocator.allocate(): < 50ms
    - dynamic_calculator.calculate(): < 200ms
    - timing_optimizer.optimize_times(): < 100ms

These benchmarks establish performance baselines and detect regressions.
The targets are based on acceptable latency for real-time schedule generation.

Note: When running with --benchmark-disable, performance assertions are skipped
since benchmark.stats is None in that mode.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


def assert_benchmark_under(benchmark: Any, max_seconds: float, message: str = "") -> None:
    """Assert benchmark mean is under threshold, skipping if disabled.

    Args:
        benchmark: The pytest-benchmark fixture
        max_seconds: Maximum acceptable mean time in seconds
        message: Optional error message
    """
    if benchmark.stats is not None:
        assert benchmark.stats["mean"] < max_seconds, (
            message or f"Benchmark exceeded {max_seconds*1000:.0f}ms"
        )

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.allocation.send_type_allocator import (
    SendTypeAllocator,
    VolumeConfig,
)
from python.models.volume import VolumeTier
from python.matching.caption_matcher import Caption, CaptionMatcher
from python.optimization.schedule_optimizer import ScheduleItem, ScheduleOptimizer
from python.orchestration.timing_optimizer import apply_time_jitter
from python.volume.dynamic_calculator import (
    PerformanceContext,
    calculate_dynamic_volume,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def large_caption_pool() -> list[Caption]:
    """Generate a large pool of 1000 captions for benchmark testing.

    Creates diverse captions with varied:
    - Performance scores (50-100)
    - Freshness scores (20-100)
    - Types (8 different types)
    - Content types (video, picture, none)
    - Tones (5 different tones)
    """
    captions = []
    types = [
        "ppv_unlock", "ppv_teaser", "exclusive", "urgent",
        "flirty_opener", "check_in", "renewal_pitch", "casual",
    ]
    tones = ["playful", "flirty", "seductive", "friendly", "professional"]
    content_types = ["video", "picture", "none"]

    for i in range(1000):
        captions.append(Caption(
            id=i + 1,
            text=f"Benchmark caption {i + 1} - varied content for performance testing",
            type=types[i % len(types)],
            performance_score=50.0 + (i % 50),
            freshness_score=20.0 + (i % 80),
            content_type=content_types[i % len(content_types)],
            emoji_level=1 + (i % 5),
            slang_level=1 + (i % 5),
            tone=tones[i % len(tones)],
        ))

    return captions


@pytest.fixture
def medium_caption_pool() -> list[Caption]:
    """Generate a medium pool of 100 captions for baseline testing."""
    captions = []
    types = ["ppv_unlock", "exclusive", "flirty_opener", "casual"]

    for i in range(100):
        captions.append(Caption(
            id=i + 1,
            text=f"Medium pool caption {i + 1}",
            type=types[i % len(types)],
            performance_score=60.0 + (i % 40),
            freshness_score=40.0 + (i % 60),
        ))

    return captions


@pytest.fixture
def sample_schedule_items() -> list[ScheduleItem]:
    """Generate sample schedule items for timing optimization benchmarks."""
    items = []
    send_types = [
        "ppv_unlock", "bump_normal", "bump_descriptive",
        "dm_farm", "renew_on_message", "game_post",
    ]
    categories = {
        "ppv_unlock": "revenue",
        "bump_normal": "engagement",
        "bump_descriptive": "engagement",
        "dm_farm": "engagement",
        "renew_on_message": "retention",
        "game_post": "revenue",
    }

    for i in range(20):
        send_type = send_types[i % len(send_types)]
        items.append(ScheduleItem(
            send_type_key=send_type,
            scheduled_date="2025-12-20",
            scheduled_time="00:00",
            category=categories[send_type],
            priority=1 if categories[send_type] == "revenue" else 2,
        ))

    return items


# =============================================================================
# Caption Matcher Benchmarks
# =============================================================================


class TestCaptionMatcherBenchmarks:
    """Benchmark tests for caption matching performance.

    Target: < 100ms for 1000 captions
    """

    @pytest.mark.benchmark(
        group="caption_matcher",
        min_rounds=10,
        warmup=True,
        warmup_iterations=3,
    )
    def test_match_captions_1000_pool(self, benchmark, large_caption_pool):
        """Benchmark caption selection from 1000-caption pool.

        Performance Target: < 100ms (0.1s)
        Baseline: ~50ms typical

        This tests the complete caption selection including:
        - Filtering by type requirements
        - Scoring all candidates
        - Selecting best match
        """
        matcher = CaptionMatcher()

        def run_match():
            matcher.reset_usage_tracking()
            result = matcher.select_caption(
                creator_id="benchmark_test",
                send_type_key="ppv_unlock",
                available_captions=large_caption_pool,
                persona="playful",
            )
            return result

        result = benchmark(run_match)

        # Verify correctness
        assert result is not None
        assert result.caption_score is not None

        # Performance assertion (100ms = 0.1s)
        assert_benchmark_under(benchmark, 0.1, "Caption matching exceeded 100ms target")

    @pytest.mark.benchmark(
        group="caption_matcher",
        min_rounds=20,
        warmup=True,
    )
    def test_match_captions_100_pool(self, benchmark, medium_caption_pool):
        """Benchmark caption selection from 100-caption pool.

        Performance Target: < 20ms
        Baseline: ~5ms typical
        """
        matcher = CaptionMatcher()

        def run_match():
            matcher.reset_usage_tracking()
            return matcher.select_caption(
                creator_id="benchmark_test",
                send_type_key="bump_normal",
                available_captions=medium_caption_pool,
            )

        result = benchmark(run_match)
        assert result is not None

        # 20ms target
        assert_benchmark_under(benchmark, 0.02)

    @pytest.mark.benchmark(
        group="caption_matcher",
        min_rounds=10,
    )
    def test_match_captions_multiple_selections(self, benchmark, large_caption_pool):
        """Benchmark multiple sequential caption selections.

        Performance Target: < 500ms for 10 selections from 1000 pool
        Tests diversity tracking overhead across selections.
        """
        matcher = CaptionMatcher()
        send_types = ["ppv_unlock", "bump_normal", "bump_descriptive", "dm_farm"]

        def run_multiple():
            matcher.reset_usage_tracking()
            results = []
            for i in range(10):
                result = matcher.select_caption(
                    creator_id="benchmark_test",
                    send_type_key=send_types[i % len(send_types)],
                    available_captions=large_caption_pool,
                )
                results.append(result)
            return results

        results = benchmark(run_multiple)

        # Verify all selections succeeded
        assert len(results) == 10
        assert all(r.caption_score is not None for r in results)

        # 500ms for 10 selections
        assert_benchmark_under(benchmark, 0.5)

    @pytest.mark.benchmark(
        group="caption_matcher",
        min_rounds=20,
    )
    def test_calculate_score_single(self, benchmark, large_caption_pool):
        """Benchmark individual caption scoring.

        Performance Target: < 1ms per caption
        Baseline: ~0.1ms typical
        """
        matcher = CaptionMatcher()
        caption = large_caption_pool[0]

        def run_score():
            return matcher.calculate_score(caption, "ppv_unlock", "playful")

        result = benchmark(run_score)

        assert result.total_score > 0
        assert_benchmark_under(benchmark, 0.001)  # 1ms


# =============================================================================
# Send Type Allocator Benchmarks
# =============================================================================


class TestSendTypeAllocatorBenchmarks:
    """Benchmark tests for send type allocation performance.

    Target: < 50ms for daily allocation
    """

    @pytest.mark.benchmark(
        group="allocator",
        min_rounds=20,
        warmup=True,
    )
    def test_allocate_day_mid_tier(self, benchmark):
        """Benchmark daily allocation for MID tier.

        Performance Target: < 50ms
        Baseline: ~10ms typical
        """
        allocator = SendTypeAllocator(creator_id="benchmark_test")
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        def run_allocate():
            return allocator.allocate_day(config, day_of_week=5, page_type="paid")

        result = benchmark(run_allocate)

        assert len(result) > 0
        assert_benchmark_under(benchmark, 0.05)  # 50ms

    @pytest.mark.benchmark(
        group="allocator",
        min_rounds=20,
    )
    def test_allocate_day_ultra_tier(self, benchmark):
        """Benchmark daily allocation for ULTRA tier (highest volume).

        Performance Target: < 50ms
        Tests maximum load scenario.
        """
        allocator = SendTypeAllocator(creator_id="ultra_benchmark")
        config = VolumeConfig(
            tier=VolumeTier.ULTRA,
            revenue_per_day=8,
            engagement_per_day=6,
            retention_per_day=3,
            fan_count=50000,
            page_type="paid",
        )

        def run_allocate():
            return allocator.allocate_day(config, day_of_week=5, page_type="paid")

        result = benchmark(run_allocate)

        assert len(result) > 0
        assert_benchmark_under(benchmark, 0.05)  # 50ms

    @pytest.mark.benchmark(
        group="allocator",
        min_rounds=10,
    )
    def test_allocate_week_full(self, benchmark):
        """Benchmark full weekly allocation.

        Performance Target: < 500ms for 7 days
        Baseline: ~100ms typical
        """
        allocator = SendTypeAllocator(creator_id="weekly_benchmark")
        config = VolumeConfig(
            tier=VolumeTier.HIGH,
            revenue_per_day=5,
            engagement_per_day=4,
            retention_per_day=2,
            fan_count=10000,
            page_type="paid",
        )
        week_start = datetime(2025, 12, 15)

        def run_weekly():
            return allocator.allocate_week(config, "paid", week_start)

        result = benchmark(run_weekly)

        assert len(result) == 7
        assert_benchmark_under(benchmark, 0.5)  # 500ms

    @pytest.mark.benchmark(
        group="allocator",
        min_rounds=50,
    )
    def test_get_volume_tier(self, benchmark):
        """Benchmark volume tier classification.

        Performance Target: < 1ms
        Should be nearly instant.
        """
        allocator = SendTypeAllocator()

        def run_classify():
            return allocator.get_volume_tier(12500)

        result = benchmark(run_classify)

        assert result.value == "high"  # VolumeTier.HIGH
        assert_benchmark_under(benchmark, 0.001)  # 1ms


# =============================================================================
# Dynamic Calculator Benchmarks
# =============================================================================


class TestDynamicCalculatorBenchmarks:
    """Benchmark tests for dynamic volume calculation.

    Target: < 200ms for full calculation
    """

    @pytest.mark.benchmark(
        group="calculator",
        min_rounds=20,
        warmup=True,
    )
    def test_calculate_dynamic_volume_basic(self, benchmark):
        """Benchmark basic dynamic volume calculation.

        Performance Target: < 200ms
        Baseline: ~5ms typical (without DB calls)
        """
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=45.0,
            opportunity_score=65.0,
            revenue_trend=5.0,
        )

        def run_calculate():
            return calculate_dynamic_volume(context)

        result = benchmark(run_calculate)

        assert result.tier == VolumeTier.HIGH
        assert result.revenue_per_day > 0
        assert_benchmark_under(benchmark, 0.2)  # 200ms

    @pytest.mark.benchmark(
        group="calculator",
        min_rounds=20,
    )
    def test_calculate_with_smooth_interpolation(self, benchmark):
        """Benchmark calculation with smooth interpolation enabled.

        Performance Target: < 200ms
        Tests the more computationally intensive smooth mode.
        """
        context = PerformanceContext(
            fan_count=10000,
            page_type="paid",
            saturation_score=55.0,
            opportunity_score=70.0,
        )

        def run_calculate():
            return calculate_dynamic_volume(context, use_smooth_interpolation=True)

        result = benchmark(run_calculate)

        assert result is not None
        assert_benchmark_under(benchmark, 0.2)  # 200ms

    @pytest.mark.benchmark(
        group="calculator",
        min_rounds=20,
    )
    def test_calculate_without_smooth_interpolation(self, benchmark):
        """Benchmark calculation with legacy step function.

        Performance Target: < 100ms
        Legacy mode should be faster.
        """
        context = PerformanceContext(
            fan_count=10000,
            page_type="paid",
            saturation_score=55.0,
            opportunity_score=70.0,
        )

        def run_calculate():
            return calculate_dynamic_volume(context, use_smooth_interpolation=False)

        result = benchmark(run_calculate)

        assert result is not None
        assert_benchmark_under(benchmark, 0.1)  # 100ms

    @pytest.mark.benchmark(
        group="calculator",
        min_rounds=10,
    )
    def test_calculate_multiple_creators(self, benchmark):
        """Benchmark calculating volumes for multiple creators.

        Performance Target: < 1s for 10 creators
        Simulates batch schedule generation.
        """
        contexts = [
            PerformanceContext(
                fan_count=1000 * (i + 1),
                page_type="paid" if i % 2 == 0 else "free",
                saturation_score=30.0 + (i * 5),
                opportunity_score=50.0 + (i * 3),
            )
            for i in range(10)
        ]

        def run_batch():
            results = []
            for ctx in contexts:
                results.append(calculate_dynamic_volume(ctx))
            return results

        results = benchmark(run_batch)

        assert len(results) == 10
        assert_benchmark_under(benchmark, 1.0)  # 1 second


# =============================================================================
# Timing Optimizer Benchmarks
# =============================================================================


class TestTimingOptimizerBenchmarks:
    """Benchmark tests for timing optimization.

    Target: < 100ms for typical daily schedule
    """

    @pytest.mark.benchmark(
        group="timing",
        min_rounds=20,
        warmup=True,
    )
    def test_optimize_timing_10_items(self, benchmark):
        """Benchmark timing optimization for 10 items.

        Performance Target: < 100ms
        Baseline: ~20ms typical
        """
        optimizer = ScheduleOptimizer()
        items = [
            ScheduleItem(
                send_type_key="ppv_unlock" if i % 3 == 0 else "bump_normal",
                scheduled_date="2025-12-20",
                scheduled_time="00:00",
                category="revenue" if i % 3 == 0 else "engagement",
                priority=1,
            )
            for i in range(10)
        ]

        def run_optimize():
            optimizer.reset_tracking()
            return optimizer.optimize_timing(items)

        result = benchmark(run_optimize)

        assert len(result) == 10
        assert all(item.scheduled_time != "00:00" for item in result)
        assert_benchmark_under(benchmark, 0.1)  # 100ms

    @pytest.mark.benchmark(
        group="timing",
        min_rounds=20,
    )
    def test_optimize_timing_20_items(self, benchmark, sample_schedule_items):
        """Benchmark timing optimization for 20 items (heavy day).

        Performance Target: < 100ms
        Tests maximum realistic daily load.
        """
        optimizer = ScheduleOptimizer()

        def run_optimize():
            optimizer.reset_tracking()
            return optimizer.optimize_timing(sample_schedule_items)

        result = benchmark(run_optimize)

        assert len(result) == 20
        assert_benchmark_under(benchmark, 0.1)  # 100ms

    @pytest.mark.benchmark(
        group="timing",
        min_rounds=50,
    )
    def test_time_jitter_application(self, benchmark):
        """Benchmark time jitter function.

        Performance Target: < 5ms
        Should be very fast (hash + random selection).
        """
        base_time = datetime(2025, 12, 20, 14, 30)

        def run_jitter():
            return apply_time_jitter(base_time, "benchmark_creator")

        result = benchmark(run_jitter)

        assert result.minute not in {0, 15, 30, 45}
        assert_benchmark_under(benchmark, 0.005)  # 5ms

    @pytest.mark.benchmark(
        group="timing",
        min_rounds=20,
    )
    def test_calculate_slot_score(self, benchmark):
        """Benchmark individual slot scoring.

        Performance Target: < 1ms per slot
        Called many times during optimization.
        """
        optimizer = ScheduleOptimizer()
        prefs = optimizer.TIMING_PREFERENCES["ppv_video"]  # Use ppv_video key

        def run_score():
            return optimizer.calculate_slot_score(19, 5, "ppv_video", prefs)

        result = benchmark(run_score)

        assert result >= 0
        assert_benchmark_under(benchmark, 0.001)  # 1ms


# =============================================================================
# Full Pipeline Benchmarks
# =============================================================================


class TestFullPipelineBenchmarks:
    """Benchmark tests for complete pipeline execution.

    Target: < 2s for full daily schedule generation
    """

    @pytest.mark.benchmark(
        group="pipeline",
        min_rounds=5,
        warmup=True,
    )
    def test_full_daily_pipeline(self, benchmark, large_caption_pool):
        """Benchmark complete daily schedule generation pipeline.

        Performance Target: < 2s
        Baseline: ~500ms typical

        Full pipeline includes:
        1. Volume calculation
        2. Send type allocation
        3. Timing optimization
        4. Caption selection for all items
        """
        def run_pipeline():
            # Phase 1: Calculate volume
            context = PerformanceContext(
                fan_count=5000,
                page_type="paid",
                saturation_score=45.0,
                opportunity_score=65.0,
            )
            volume = calculate_dynamic_volume(context)

            # Phase 2: Allocate send types
            allocator = SendTypeAllocator(creator_id="pipeline_bench")
            config = VolumeConfig(
                tier=volume.tier,
                revenue_per_day=volume.revenue_per_day,
                engagement_per_day=volume.engagement_per_day,
                retention_per_day=volume.retention_per_day,
                fan_count=volume.fan_count,
                page_type=volume.page_type,
            )
            allocations = allocator.allocate_day(config, 5, "paid")

            # Phase 3: Create schedule items
            items = [
                ScheduleItem(
                    send_type_key=a["send_type_key"],
                    scheduled_date="2025-12-20",
                    scheduled_time="00:00",
                    category=a["category"],
                    priority=a["priority"],
                )
                for a in allocations
            ]

            # Phase 4: Optimize timing
            optimizer = ScheduleOptimizer()
            optimizer.reset_tracking()
            optimized = optimizer.optimize_timing(items)

            # Phase 5: Select captions
            matcher = CaptionMatcher()
            matcher.reset_usage_tracking()
            final_schedule = []
            for item in optimized:
                result = matcher.select_caption(
                    creator_id="pipeline_bench",
                    send_type_key=item.send_type_key,
                    available_captions=large_caption_pool,
                )
                final_schedule.append({
                    "item": item,
                    "caption": result,
                })

            return final_schedule

        result = benchmark(run_pipeline)

        assert len(result) > 0
        assert_benchmark_under(benchmark, 2.0)  # 2 seconds

    @pytest.mark.benchmark(
        group="pipeline",
        min_rounds=3,
    )
    def test_full_weekly_pipeline(self, benchmark, medium_caption_pool):
        """Benchmark complete weekly schedule generation.

        Performance Target: < 10s for full week
        Uses medium caption pool to keep test time reasonable.
        """
        def run_weekly_pipeline():
            # Calculate volume
            context = PerformanceContext(
                fan_count=3000,
                page_type="paid",
                saturation_score=50.0,
                opportunity_score=60.0,
            )
            volume = calculate_dynamic_volume(context)

            # Allocate for week
            allocator = SendTypeAllocator(creator_id="weekly_bench")
            config = VolumeConfig(
                tier=volume.tier,
                revenue_per_day=volume.revenue_per_day,
                engagement_per_day=volume.engagement_per_day,
                retention_per_day=volume.retention_per_day,
                fan_count=volume.fan_count,
                page_type=volume.page_type,
            )
            week_start = datetime(2025, 12, 15)
            weekly = allocator.allocate_week(config, "paid", week_start)

            # Process each day
            optimizer = ScheduleOptimizer()
            matcher = CaptionMatcher()
            weekly_schedule = {}

            for date_str, allocations in weekly.items():
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

                optimizer.reset_tracking()
                optimized = optimizer.optimize_timing(items)

                day_schedule = []
                for item in optimized:
                    result = matcher.select_caption(
                        creator_id="weekly_bench",
                        send_type_key=item.send_type_key,
                        available_captions=medium_caption_pool,
                    )
                    day_schedule.append({"item": item, "caption": result})

                weekly_schedule[date_str] = day_schedule

            return weekly_schedule

        result = benchmark(run_weekly_pipeline)

        assert len(result) == 7
        assert_benchmark_under(benchmark, 10.0)  # 10 seconds


# =============================================================================
# Memory Usage Benchmarks
# =============================================================================


class TestMemoryBenchmarks:
    """Memory-focused benchmark tests.

    These tests focus on memory efficiency rather than pure speed.
    """

    @pytest.mark.benchmark(
        group="memory",
        min_rounds=5,
    )
    def test_large_caption_pool_memory(self, benchmark):
        """Test memory handling with large caption pools.

        Verifies that processing large pools doesn't cause
        excessive memory allocation.
        """
        def create_and_process():
            # Create large pool
            captions = [
                Caption(
                    id=i,
                    text=f"Caption {i} " * 10,  # ~100 chars each
                    type="ppv_unlock",
                    performance_score=75.0,
                    freshness_score=85.0,
                )
                for i in range(5000)
            ]

            # Process through matcher
            matcher = CaptionMatcher()
            matcher.reset_usage_tracking()
            results = []
            for _ in range(5):
                result = matcher.select_caption(
                    "memory_test",
                    "ppv_unlock",
                    captions,
                )
                results.append(result)

            return results

        results = benchmark(create_and_process)

        assert len(results) == 5
        # Main concern is it completes without OOM

    @pytest.mark.benchmark(
        group="memory",
        min_rounds=10,
    )
    def test_matcher_reset_memory(self, benchmark, medium_caption_pool):
        """Test that matcher reset properly clears memory.

        Verifies no memory leaks from repeated reset cycles.
        """
        matcher = CaptionMatcher()

        def reset_cycle():
            for _ in range(100):
                matcher.select_caption(
                    "reset_test",
                    "ppv_unlock",
                    medium_caption_pool,
                )
            matcher.reset_usage_tracking()
            return matcher.get_usage_stats()

        stats = benchmark(reset_cycle)

        assert stats["total_used"] == 0  # Reset worked


# =============================================================================
# Regression Benchmarks
# =============================================================================


class TestRegressionBenchmarks:
    """Benchmarks to detect performance regressions.

    These establish baseline performance that should not regress.
    """

    @pytest.mark.benchmark(
        group="regression",
        min_rounds=30,
    )
    def test_caption_scoring_regression(self, benchmark):
        """Baseline for caption scoring performance.

        Any significant increase indicates a regression.
        Baseline: ~0.05ms per score
        """
        matcher = CaptionMatcher()
        caption = Caption(
            id=1,
            text="Test caption",
            type="ppv_unlock",
            performance_score=80.0,
            freshness_score=90.0,
        )

        result = benchmark(lambda: matcher.calculate_score(caption, "ppv_unlock", "playful"))

        assert result.total_score > 0
        # Should be sub-millisecond
        assert_benchmark_under(benchmark, 0.0005)

    @pytest.mark.benchmark(
        group="regression",
        min_rounds=30,
    )
    def test_volume_tier_regression(self, benchmark):
        """Baseline for volume tier classification.

        Simple lookup should be nearly instant.
        Baseline: ~0.001ms
        """
        from python.volume.dynamic_calculator import get_volume_tier

        result = benchmark(lambda: get_volume_tier(7500))

        assert result == VolumeTier.HIGH
        # Should be microseconds
        assert_benchmark_under(benchmark, 0.0001)

    @pytest.mark.benchmark(
        group="regression",
        min_rounds=30,
    )
    def test_jitter_regression(self, benchmark):
        """Baseline for time jitter calculation.

        Hash-based should be very fast.
        Baseline: ~0.1ms
        """
        base_time = datetime(2025, 12, 20, 15, 0)

        result = benchmark(lambda: apply_time_jitter(base_time, "regression_test"))

        assert result.minute not in {0, 15, 30, 45}
        # Should be sub-millisecond
        assert_benchmark_under(benchmark, 0.001)
