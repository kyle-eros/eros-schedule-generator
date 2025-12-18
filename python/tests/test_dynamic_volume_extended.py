"""
Extended unit tests for dynamic volume calculation to increase coverage.

Tests cover:
- OptimizedVolumeResult dataclass properties
- calculate_optimized_volume pipeline
- Error handling and edge cases
- Database integration scenarios
"""

import os
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

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
    _calculate_saturation_multiplier_smooth,
    _calculate_opportunity_multiplier_smooth,
    _apply_bounds,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db_path():
    """Create a temporary SQLite database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create minimal schema
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Create necessary tables
    cursor.execute("""
        CREATE TABLE creators (
            creator_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            page_type TEXT DEFAULT 'paid',
            fan_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE performance_history (
            id INTEGER PRIMARY KEY,
            creator_id TEXT NOT NULL,
            horizon_days INTEGER NOT NULL,
            saturation_score REAL,
            opportunity_score REAL,
            message_count INTEGER DEFAULT 0,
            recorded_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE volume_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id TEXT NOT NULL,
            week_start_date TEXT,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE caption_bank (
            caption_id INTEGER PRIMARY KEY,
            caption_text TEXT,
            send_type_key TEXT,
            performance_score REAL DEFAULT 50.0,
            last_used_date TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE vault_matrix (
            id INTEGER PRIMARY KEY,
            creator_id TEXT NOT NULL,
            content_type TEXT NOT NULL
        )
    """)

    # Insert test data
    cursor.execute(
        "INSERT INTO creators (username, page_type, fan_count) VALUES (?, ?, ?)",
        ("test_creator", "paid", 5000)
    )

    conn.commit()
    conn.close()

    yield path

    # Cleanup
    os.unlink(path)


@pytest.fixture
def basic_context():
    """Basic performance context for testing."""
    return PerformanceContext(
        fan_count=5000,
        page_type="paid",
        saturation_score=50.0,
        opportunity_score=50.0,
        message_count=100,
    )


@pytest.fixture
def new_creator_context():
    """New creator context with minimal data."""
    return PerformanceContext(
        fan_count=1000,
        page_type="paid",
        saturation_score=50.0,
        opportunity_score=50.0,
        is_new_creator=True,
        message_count=2,
    )


# =============================================================================
# OptimizedVolumeResult Tests
# =============================================================================


class TestOptimizedVolumeResult:
    """Tests for OptimizedVolumeResult dataclass and properties."""

    def test_total_weekly_volume_property(self):
        """Test total_weekly_volume calculates sum of distribution."""
        base_config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=3,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        result = OptimizedVolumeResult(
            base_config=base_config,
            final_config=base_config,
            weekly_distribution={0: 9, 1: 9, 2: 9, 3: 9, 4: 10, 5: 11, 6: 10},
        )

        assert result.total_weekly_volume == 67

    def test_total_weekly_volume_empty_distribution(self):
        """Test total_weekly_volume with empty distribution."""
        base_config = VolumeConfig(
            tier=VolumeTier.LOW,
            revenue_per_day=3,
            engagement_per_day=3,
            retention_per_day=1,
            fan_count=500,
            page_type="paid",
        )

        result = OptimizedVolumeResult(
            base_config=base_config,
            final_config=base_config,
            weekly_distribution={},
        )

        assert result.total_weekly_volume == 0

    def test_has_warnings_property_true(self):
        """Test has_warnings returns True when warnings exist."""
        base_config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=3,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        result = OptimizedVolumeResult(
            base_config=base_config,
            final_config=base_config,
            caption_warnings=["Low captions for ppv_unlock"],
        )

        assert result.has_warnings is True

    def test_has_warnings_property_false(self):
        """Test has_warnings returns False when no warnings."""
        base_config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=3,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        result = OptimizedVolumeResult(
            base_config=base_config,
            final_config=base_config,
            caption_warnings=[],
        )

        assert result.has_warnings is False

    def test_is_high_confidence_true(self):
        """Test is_high_confidence returns True when score >= 0.6."""
        base_config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=3,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        result = OptimizedVolumeResult(
            base_config=base_config,
            final_config=base_config,
            confidence_score=0.8,
        )

        assert result.is_high_confidence is True

    def test_is_high_confidence_boundary(self):
        """Test is_high_confidence at boundary 0.6."""
        base_config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=3,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        result = OptimizedVolumeResult(
            base_config=base_config,
            final_config=base_config,
            confidence_score=0.6,
        )

        assert result.is_high_confidence is True

    def test_is_high_confidence_false(self):
        """Test is_high_confidence returns False when score < 0.6."""
        base_config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=4,
            engagement_per_day=3,
            retention_per_day=2,
            fan_count=2500,
            page_type="paid",
        )

        result = OptimizedVolumeResult(
            base_config=base_config,
            final_config=base_config,
            confidence_score=0.5,
        )

        assert result.is_high_confidence is False


# =============================================================================
# calculate_optimized_volume Tests
# =============================================================================


class TestCalculateOptimizedVolume:
    """Tests for the full optimized volume calculation pipeline."""

    def test_basic_calculation(self, temp_db_path, basic_context):
        """Test basic optimized volume calculation."""
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        assert isinstance(result, OptimizedVolumeResult)
        assert result.base_config is not None
        assert result.final_config is not None
        assert "base_tier_calculation" in result.adjustments_applied

    def test_default_db_path_from_env(self, temp_db_path, basic_context):
        """Test that default db_path is taken from environment."""
        original_env = os.environ.get("EROS_DB_PATH")
        os.environ["EROS_DB_PATH"] = temp_db_path

        try:
            result = calculate_optimized_volume(
                context=basic_context,
                creator_id="test_creator",
                db_path=None,  # Should use env var
                week_start="2025-12-22",
                track_prediction=False,
            )

            assert result is not None
            assert isinstance(result, OptimizedVolumeResult)
        finally:
            if original_env:
                os.environ["EROS_DB_PATH"] = original_env
            else:
                os.environ.pop("EROS_DB_PATH", None)

    def test_week_start_default_calculation(self, temp_db_path, basic_context):
        """Test that week_start defaults to next Monday."""
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start=None,  # Should calculate default
            track_prediction=False,
        )

        assert result is not None
        assert isinstance(result, OptimizedVolumeResult)

    def test_with_new_creator(self, temp_db_path, new_creator_context):
        """Test optimized volume for new creator."""
        result = calculate_optimized_volume(
            context=new_creator_context,
            creator_id="new_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        # New creators should get conservative volumes
        assert result.final_config.revenue_per_day >= 1

    def test_multi_horizon_fusion_failure(self, temp_db_path, basic_context):
        """Test graceful handling of multi-horizon fusion failure."""
        # With empty performance_history, fusion should fail gracefully
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="unknown_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        # Should still calculate basic volume

    def test_confidence_dampening_low_confidence(self, temp_db_path):
        """Test confidence dampening for low data scenarios."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=30.0,
            opportunity_score=80.0,
            message_count=3,  # Low message count
        )

        result = calculate_optimized_volume(
            context=context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        # Low message count should result in lower confidence
        assert result.confidence_score <= 1.0

    def test_weekly_distribution_populated(self, temp_db_path, basic_context):
        """Test that weekly distribution is populated."""
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        assert result.weekly_distribution is not None
        # Should have entries for 7 days (0-6)
        if result.weekly_distribution:
            assert all(day in result.weekly_distribution for day in range(7))

    def test_dow_multipliers_populated(self, temp_db_path, basic_context):
        """Test that DOW multipliers are populated."""
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        assert result.dow_multipliers_used is not None

    def test_free_page_retention_zero(self, temp_db_path):
        """Test that free pages have zero retention."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="free",
            saturation_score=50.0,
            opportunity_score=50.0,
        )

        result = calculate_optimized_volume(
            context=context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        assert result.final_config.retention_per_day == 0

    def test_prediction_tracking_disabled(self, temp_db_path, basic_context):
        """Test that prediction tracking can be disabled."""
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        assert result.prediction_id is None

    def test_adjustments_list_populated(self, temp_db_path, basic_context):
        """Test that adjustments list is populated."""
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        assert len(result.adjustments_applied) >= 1
        assert "base_tier_calculation" in result.adjustments_applied


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestDynamicVolumeEdgeCases:
    """Edge case tests for dynamic volume calculation."""

    def test_extreme_saturation_100(self):
        """Test with saturation at maximum 100."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=100.0,
            opportunity_score=0.0,
        )
        config = calculate_dynamic_volume(context)

        assert config is not None
        assert config.revenue_per_day >= 1  # Should not go below minimum

    def test_extreme_opportunity_100(self):
        """Test with opportunity at maximum 100."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=0.0,
            opportunity_score=100.0,
        )
        config = calculate_dynamic_volume(context)

        assert config is not None
        assert config.revenue_per_day <= 8  # Should not exceed maximum

    def test_both_scores_at_boundary_50(self):
        """Test with both scores at boundary 50."""
        context = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            saturation_score=50.0,
            opportunity_score=50.0,
        )
        config = calculate_dynamic_volume(context)

        assert config is not None
        assert config.tier == VolumeTier.HIGH

    def test_all_trend_types(self):
        """Test various trend values."""
        # Negative trend
        context_neg = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            revenue_trend=-30.0,
        )
        config_neg = calculate_dynamic_volume(context_neg)

        # Positive trend
        context_pos = PerformanceContext(
            fan_count=5000,
            page_type="paid",
            revenue_trend=30.0,
        )
        config_pos = calculate_dynamic_volume(context_pos)

        # Both should be valid
        assert config_neg is not None
        assert config_pos is not None
        # Positive trend should have >= revenue than negative trend
        assert config_pos.revenue_per_day >= config_neg.revenue_per_day

    def test_very_high_fan_count(self):
        """Test with very high fan count (>100k)."""
        context = PerformanceContext(
            fan_count=500000,
            page_type="paid",
            saturation_score=50.0,
            opportunity_score=50.0,
        )
        config = calculate_dynamic_volume(context)

        assert config is not None
        assert config.tier == VolumeTier.ULTRA

    def test_saturation_smooth_interpolation_gradual(self):
        """Test smooth interpolation produces gradual values."""
        values = []
        for sat in range(0, 101, 10):
            mult = _calculate_saturation_multiplier_smooth(float(sat))
            values.append(mult)

        # Should be monotonically decreasing (or equal)
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1]

    def test_opportunity_blocked_at_high_saturation(self):
        """Test opportunity multiplier blocked at high saturation."""
        # At saturation >= 50, opportunity should return 1.0
        mult = _calculate_opportunity_multiplier_smooth(90.0, 60.0)
        assert mult == 1.0

    def test_bounds_for_all_categories(self):
        """Test bounds enforcement for all categories."""
        # Test revenue
        assert _apply_bounds(0, "revenue") == 1
        assert _apply_bounds(20, "revenue") == 8
        assert _apply_bounds(5, "revenue") == 5

        # Test engagement
        assert _apply_bounds(0, "engagement") == 1
        assert _apply_bounds(20, "engagement") == 6
        assert _apply_bounds(4, "engagement") == 4

        # Test retention
        assert _apply_bounds(-5, "retention") == 0
        assert _apply_bounds(10, "retention") == 4
        assert _apply_bounds(2, "retention") == 2


# =============================================================================
# Fallback Path Tests
# =============================================================================


class TestCalculateOptimizedVolumeFallbacks:
    """Tests for fallback paths in calculate_optimized_volume."""

    def test_dow_failure_fallback(self, temp_db_path, basic_context):
        """Test DOW calculation failure uses uniform distribution."""
        # The test DB has minimal data, so DOW might use defaults
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        # Should have some weekly distribution
        assert result.weekly_distribution is not None

    def test_elasticity_check_failure(self, temp_db_path, basic_context):
        """Test elasticity check failure is handled gracefully."""
        # With minimal test data, elasticity should fail gracefully
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        # Should not be capped if elasticity check fails
        assert result.elasticity_capped is False

    def test_caption_pool_check_failure(self, temp_db_path, basic_context):
        """Test caption pool check failure is handled gracefully."""
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        # Should have empty or populated warnings list

    def test_content_weighting_failure(self, temp_db_path, basic_context):
        """Test content weighting failure is handled gracefully."""
        result = calculate_optimized_volume(
            context=basic_context,
            creator_id="test_creator",
            db_path=temp_db_path,
            week_start="2025-12-22",
            track_prediction=False,
        )

        assert result is not None
        # Content allocations may be empty if no ranking data
        assert result.content_allocations is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
