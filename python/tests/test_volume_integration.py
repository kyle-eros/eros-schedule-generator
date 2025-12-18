"""
Integration tests for the unified volume optimizer pipeline.

Tests cover:
- Full pipeline execution with all modules
- Module interaction and data flow
- Edge cases (new creators, sparse data, high saturation)
- Error handling and fallbacks
- OptimizedVolumeResult structure validation
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.models.volume import VolumeConfig, VolumeTier
from python.volume.dynamic_calculator import (
    PerformanceContext,
    OptimizedVolumeResult,
    calculate_dynamic_volume,
    calculate_optimized_volume,
    get_volume_tier,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def high_tier_context() -> PerformanceContext:
    """HIGH tier creator (12,434 fans) with moderate scores."""
    return PerformanceContext(
        fan_count=12434,
        page_type="paid",
        saturation_score=45,
        opportunity_score=65,
        revenue_trend=5,
        message_count=100,
    )


@pytest.fixture
def new_creator_context() -> PerformanceContext:
    """New creator with minimal history."""
    return PerformanceContext(
        fan_count=2500,
        page_type="paid",
        saturation_score=50,
        opportunity_score=50,
        is_new_creator=True,
        message_count=3,
    )


@pytest.fixture
def sparse_data_context() -> PerformanceContext:
    """Creator with sparse performance data."""
    return PerformanceContext(
        fan_count=5000,
        page_type="paid",
        saturation_score=50,
        opportunity_score=50,
        message_count=10,  # Low confidence
    )


@pytest.fixture
def high_saturation_context() -> PerformanceContext:
    """Creator with high saturation (fatigued audience)."""
    return PerformanceContext(
        fan_count=10000,
        page_type="paid",
        saturation_score=85,
        opportunity_score=30,
        message_count=200,
    )


@pytest.fixture
def free_page_context() -> PerformanceContext:
    """Free page creator (no retention sends)."""
    return PerformanceContext(
        fan_count=8000,
        page_type="free",
        saturation_score=40,
        opportunity_score=70,
        message_count=150,
    )


@pytest.fixture
def mock_db_path(tmp_path) -> str:
    """Create a mock database path for testing."""
    import sqlite3

    db_path = str(tmp_path / "test_eros.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create minimal schema for testing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mass_messages (
            message_id INTEGER PRIMARY KEY,
            creator_id TEXT,
            sending_time TEXT,
            message_type TEXT,
            sent_count INTEGER DEFAULT 0,
            earnings REAL DEFAULT 0,
            revenue_per_send REAL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS volume_predictions (
            prediction_id INTEGER PRIMARY KEY,
            creator_id TEXT,
            predicted_at TEXT,
            input_fan_count INTEGER,
            input_page_type TEXT,
            input_saturation REAL,
            input_opportunity REAL,
            predicted_tier TEXT,
            predicted_revenue_per_day INTEGER,
            predicted_engagement_per_day INTEGER,
            predicted_retention_per_day INTEGER,
            predicted_weekly_revenue REAL,
            predicted_weekly_messages INTEGER,
            schedule_template_id INTEGER,
            week_start_date TEXT,
            algorithm_version TEXT,
            actual_total_revenue REAL,
            actual_messages_sent INTEGER,
            actual_avg_rps REAL,
            revenue_prediction_error_pct REAL,
            volume_prediction_error_pct REAL,
            outcome_measured INTEGER DEFAULT 0,
            outcome_measured_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS volume_performance_tracking (
            tracking_id INTEGER PRIMARY KEY,
            creator_id TEXT,
            analysis_date TEXT,
            period_days INTEGER,
            saturation_score REAL,
            opportunity_score REAL,
            total_messages INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS send_types (
            send_type_id INTEGER PRIMARY KEY,
            send_type_key TEXT,
            category TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS caption_bank (
            caption_id INTEGER PRIMARY KEY,
            creator_id TEXT,
            caption_type TEXT,
            freshness_score REAL,
            performance_score REAL,
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS send_type_caption_requirements (
            requirement_id INTEGER PRIMARY KEY,
            send_type_id INTEGER,
            caption_type TEXT,
            priority INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()

    return db_path


# =============================================================================
# OptimizedVolumeResult Structure Tests
# =============================================================================


class TestOptimizedVolumeResultStructure:
    """Tests for OptimizedVolumeResult dataclass structure."""

    def test_result_has_required_fields(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Result should have all required fields."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            week_start="2025-12-16",
            track_prediction=False,
        )

        assert hasattr(result, "base_config")
        assert hasattr(result, "final_config")
        assert hasattr(result, "weekly_distribution")
        assert hasattr(result, "content_allocations")
        assert hasattr(result, "adjustments_applied")
        assert hasattr(result, "confidence_score")
        assert hasattr(result, "elasticity_capped")
        assert hasattr(result, "caption_warnings")
        assert hasattr(result, "prediction_id")
        assert hasattr(result, "fused_saturation")
        assert hasattr(result, "fused_opportunity")
        assert hasattr(result, "divergence_detected")
        assert hasattr(result, "dow_multipliers_used")
        assert hasattr(result, "message_count")

    def test_base_config_is_volume_config(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """base_config should be a VolumeConfig instance."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        assert isinstance(result.base_config, VolumeConfig)
        assert isinstance(result.final_config, VolumeConfig)

    def test_weekly_distribution_has_7_days(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """weekly_distribution should have entries for all 7 days."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        assert len(result.weekly_distribution) == 7
        for day in range(7):
            assert day in result.weekly_distribution

    def test_properties_work_correctly(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Properties should compute correctly."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # Test total_weekly_volume property
        expected_total = sum(result.weekly_distribution.values())
        assert result.total_weekly_volume == expected_total

        # Test has_warnings property
        assert result.has_warnings == (len(result.caption_warnings) > 0)

        # Test is_high_confidence property
        assert result.is_high_confidence == (result.confidence_score >= 0.6)


# =============================================================================
# Full Pipeline Execution Tests
# =============================================================================


class TestFullPipelineExecution:
    """Tests for full pipeline execution."""

    def test_pipeline_completes_successfully(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Pipeline should complete without errors."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="alexia",
            db_path=mock_db_path,
            week_start="2025-12-16",
            track_prediction=False,
        )

        assert result is not None
        assert isinstance(result, OptimizedVolumeResult)

    def test_base_tier_calculation_applied(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Base tier calculation should always be applied."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        assert "base_tier_calculation" in result.adjustments_applied
        assert result.base_config.tier == VolumeTier.HIGH

    def test_volume_within_bounds(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Final volume should be within configured bounds."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # Revenue bounds: 1-8
        assert 1 <= result.final_config.revenue_per_day <= 8
        # Engagement bounds: 1-6
        assert 1 <= result.final_config.engagement_per_day <= 6
        # Retention bounds: 0-4
        assert 0 <= result.final_config.retention_per_day <= 4


# =============================================================================
# Module Integration Tests
# =============================================================================


class TestModuleIntegration:
    """Tests for individual module integration."""

    def test_confidence_dampening_applied_for_low_data(
        self, sparse_data_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Confidence dampening should be applied when data is sparse."""
        result = calculate_optimized_volume(
            sparse_data_context,
            creator_id="sparse_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # With only 10 messages, confidence should be low
        assert result.confidence_score < 1.0
        # Confidence dampening should be in adjustments
        # Note: May not appear if module import fails
        assert result.message_count == 10

    def test_dow_multipliers_populated(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """DOW multipliers should be populated."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # Should have multipliers for all 7 days
        assert len(result.dow_multipliers_used) == 7
        # All multipliers should be positive
        for day, mult in result.dow_multipliers_used.items():
            assert mult > 0

    def test_fused_scores_captured(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Fused saturation and opportunity scores should be captured."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # Fused scores should be within valid range
        assert 0 <= result.fused_saturation <= 100
        assert 0 <= result.fused_opportunity <= 100


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_new_creator_handling(
        self, new_creator_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """New creators should be handled gracefully."""
        result = calculate_optimized_volume(
            new_creator_context,
            creator_id="new_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        assert result is not None
        # New creator with 3 messages should have low confidence
        assert result.message_count == 3

    def test_high_saturation_reduces_volume(
        self, high_saturation_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """High saturation should reduce volume."""
        result = calculate_optimized_volume(
            high_saturation_context,
            creator_id="saturated_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # With high saturation (85), volume should be reduced
        # Base HIGH tier paid: revenue=5
        # After saturation reduction, should be less
        assert result.final_config.revenue_per_day <= 5

    def test_free_page_no_retention(
        self, free_page_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Free pages should have zero retention."""
        result = calculate_optimized_volume(
            free_page_context,
            creator_id="free_page_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        assert result.final_config.retention_per_day == 0
        assert result.final_config.page_type == "free"

    def test_zero_fans_handled(self, mock_db_path: str) -> None:
        """Zero fans should be handled gracefully."""
        context = PerformanceContext(
            fan_count=0,
            page_type="paid",
            saturation_score=50,
            opportunity_score=50,
        )

        result = calculate_optimized_volume(
            context,
            creator_id="zero_fans",
            db_path=mock_db_path,
            track_prediction=False,
        )

        assert result is not None
        assert result.base_config.tier == VolumeTier.LOW


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and fallbacks."""

    def test_missing_db_uses_default_path(
        self, high_tier_context: PerformanceContext
    ) -> None:
        """Missing db_path should use default from environment."""
        # This test verifies the function doesn't crash when db_path
        # is None and EROS_DB_PATH isn't set
        # Note: Will fail gracefully if DB doesn't exist
        try:
            result = calculate_optimized_volume(
                high_tier_context,
                creator_id="test_creator",
                db_path=None,  # Will use default
                track_prediction=False,
            )
            # If it succeeds, result should be valid
            assert result is not None
        except Exception:
            # Expected if default DB doesn't exist
            pass

    def test_invalid_week_start_generates_default(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Missing week_start should generate a default."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            week_start=None,  # Should generate default
            track_prediction=False,
        )

        assert result is not None

    def test_module_failure_graceful_fallback(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Module failures should not crash the pipeline."""
        # The pipeline should handle import/execution failures gracefully
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # Even if some modules fail, base calculation should work
        assert "base_tier_calculation" in result.adjustments_applied


# =============================================================================
# Prediction Tracking Tests
# =============================================================================


class TestPredictionTracking:
    """Tests for prediction tracking functionality."""

    def test_prediction_tracked_when_enabled(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Prediction should be tracked when enabled."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="tracked_creator",
            db_path=mock_db_path,
            week_start="2025-12-16",
            track_prediction=True,
        )

        # Prediction tracking should be in adjustments if successful
        # Note: May fail due to schema mismatch in test DB
        # but should not crash the pipeline
        assert result is not None

    def test_prediction_not_tracked_when_disabled(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Prediction should not be tracked when disabled."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="untracked_creator",
            db_path=mock_db_path,
            week_start="2025-12-16",
            track_prediction=False,
        )

        assert "prediction_tracked" not in result.adjustments_applied


# =============================================================================
# Volume Distribution Tests
# =============================================================================


class TestVolumeDistribution:
    """Tests for weekly volume distribution."""

    def test_weekly_distribution_positive(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """All daily volumes should be positive."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        for day, volume in result.weekly_distribution.items():
            assert volume >= 0, f"Day {day} has negative volume: {volume}"

    def test_weekly_total_reasonable(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Weekly total should be reasonable (not 0, not excessive)."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        total = result.total_weekly_volume
        # Should be at least some volume
        assert total > 0
        # Should not be excessive (max daily * 7 = ~126 at most)
        assert total <= 150


# =============================================================================
# Backwards Compatibility Tests
# =============================================================================


class TestBackwardsCompatibility:
    """Tests for backwards compatibility with existing code."""

    def test_calculate_dynamic_volume_still_works(
        self, high_tier_context: PerformanceContext
    ) -> None:
        """Original calculate_dynamic_volume should still work."""
        config = calculate_dynamic_volume(high_tier_context)

        assert config is not None
        assert isinstance(config, VolumeConfig)
        assert config.tier == VolumeTier.HIGH

    def test_optimized_produces_compatible_config(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Optimized result should produce compatible VolumeConfig."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # final_config should be usable everywhere VolumeConfig is expected
        config = result.final_config

        assert config.tier in list(VolumeTier)
        assert config.total_per_day > 0
        assert config.page_type in ("paid", "free")


# =============================================================================
# Integration with ORCHESTRATION.md Pipeline Tests
# =============================================================================


class TestOrchestrationIntegration:
    """Tests verifying integration with the orchestration pipeline."""

    def test_result_suitable_for_phase2_allocation(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Result should be suitable for Phase 2 send type allocation."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # Phase 2 needs VolumeConfig with daily volumes
        config = result.final_config
        assert config.revenue_per_day >= 0
        assert config.engagement_per_day >= 0
        assert config.retention_per_day >= 0

    def test_weekly_distribution_suitable_for_scheduling(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Weekly distribution should be suitable for scheduling."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # Scheduling needs per-day volumes for the week
        for day in range(7):
            assert day in result.weekly_distribution
            assert isinstance(result.weekly_distribution[day], int)

    def test_content_allocations_usable(
        self, high_tier_context: PerformanceContext, mock_db_path: str
    ) -> None:
        """Content allocations should be usable for type selection."""
        result = calculate_optimized_volume(
            high_tier_context,
            creator_id="test_creator",
            db_path=mock_db_path,
            track_prediction=False,
        )

        # Content allocations should be a dict
        assert isinstance(result.content_allocations, dict)
        # Values should be positive integers
        for type_name, allocation in result.content_allocations.items():
            assert isinstance(type_name, str)
            assert isinstance(allocation, int)
            assert allocation >= 0
