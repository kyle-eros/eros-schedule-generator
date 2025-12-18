"""
Tests for day-of-week volume modulation module.

Covers:
1. DOW multiplier calculation with various data distributions
2. Handling of insufficient data (fallback to defaults)
3. Confidence calculation based on message counts
4. Multiplier bounds enforcement
5. Weekly volume distribution calculation
6. SQLite dow conversion (0=Sunday vs 0=Monday)
"""

import sqlite3
import pytest
from unittest.mock import patch, MagicMock

from python.volume.day_of_week import (
    # Data classes
    DayPerformance,
    DOWMultipliers,
    DOWAnalysis,
    # Constants
    DEFAULT_MULTIPLIERS,
    DAY_NAMES,
    MULTIPLIER_MIN,
    MULTIPLIER_MAX,
    MIN_MESSAGES_PER_DAY,
    MIN_TOTAL_MESSAGES,
    SQLITE_TO_PYTHON_DOW,
    PYTHON_TO_SQLITE_DOW,
    # Conversion functions
    convert_sqlite_dow_to_python,
    convert_python_dow_to_sqlite,
    # Main functions
    fetch_dow_performance,
    calculate_dow_multipliers,
    analyze_dow_patterns,
    apply_dow_modulation,
    get_weekly_volume_distribution,
    # Internal functions
    _calculate_day_confidence,
    _calculate_overall_confidence,
    _clamp_multiplier,
    _round_volume,
)
from python.exceptions import InsufficientDataError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db_path(tmp_path):
    """Create a temporary SQLite database with test data."""
    db_path = tmp_path / "test_eros.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create creators table
    cursor.execute("""
        CREATE TABLE creators (
            creator_id INTEGER PRIMARY KEY,
            page_name TEXT UNIQUE
        )
    """)
    cursor.execute("INSERT INTO creators (creator_id, page_name) VALUES (1, 'test_creator')")

    # Create mass_messages table with actual schema column names
    # Implementation expects: sending_time (not sent_at), sending_day_of_week, earnings (not revenue)
    cursor.execute("""
        CREATE TABLE mass_messages (
            id INTEGER PRIMARY KEY,
            creator_id INTEGER,
            sending_time TEXT,
            sending_day_of_week INTEGER,
            earnings REAL,
            view_rate REAL,
            purchase_rate REAL
        )
    """)

    conn.commit()
    conn.close()

    return str(db_path)


@pytest.fixture
def populated_db(mock_db_path):
    """Populate the test database with DOW performance data."""
    conn = sqlite3.connect(mock_db_path)
    cursor = conn.cursor()

    # Insert messages across different days
    # Using dates that span various days of week
    # Format: (creator_id, sending_time, sending_day_of_week (sqlite: 0=Sun), earnings, view_rate, purchase_rate)
    messages = [
        # Monday (2025-12-15) - sqlite dow = 1
        (1, "2025-12-15 10:00:00", 1, 50.0, 0.8, 0.1),
        (1, "2025-12-15 14:00:00", 1, 75.0, 0.85, 0.12),
        (1, "2025-12-15 18:00:00", 1, 60.0, 0.75, 0.09),
        (1, "2025-12-15 20:00:00", 1, 45.0, 0.7, 0.08),
        (1, "2025-12-15 22:00:00", 1, 55.0, 0.78, 0.11),
        (1, "2025-12-08 10:00:00", 1, 48.0, 0.77, 0.10),
        # Tuesday (2025-12-16) - sqlite dow = 2
        (1, "2025-12-16 12:00:00", 2, 40.0, 0.65, 0.07),
        (1, "2025-12-16 16:00:00", 2, 35.0, 0.6, 0.06),
        (1, "2025-12-16 20:00:00", 2, 42.0, 0.68, 0.08),
        (1, "2025-12-09 12:00:00", 2, 38.0, 0.62, 0.07),
        (1, "2025-12-09 16:00:00", 2, 44.0, 0.7, 0.09),
        # Wednesday (2025-12-17) - sqlite dow = 3
        (1, "2025-12-17 10:00:00", 3, 55.0, 0.72, 0.09),
        (1, "2025-12-17 15:00:00", 3, 62.0, 0.8, 0.11),
        (1, "2025-12-17 19:00:00", 3, 58.0, 0.76, 0.10),
        (1, "2025-12-10 10:00:00", 3, 52.0, 0.74, 0.09),
        (1, "2025-12-10 15:00:00", 3, 60.0, 0.78, 0.10),
        # Thursday (2025-12-18) - sqlite dow = 4
        (1, "2025-12-18 11:00:00", 4, 65.0, 0.82, 0.12),
        (1, "2025-12-18 17:00:00", 4, 70.0, 0.85, 0.13),
        (1, "2025-12-18 21:00:00", 4, 68.0, 0.84, 0.12),
        (1, "2025-12-11 11:00:00", 4, 63.0, 0.8, 0.11),
        (1, "2025-12-11 17:00:00", 4, 72.0, 0.86, 0.14),
        # Friday (2025-12-19) - sqlite dow = 5
        (1, "2025-12-19 12:00:00", 5, 80.0, 0.88, 0.15),
        (1, "2025-12-19 18:00:00", 5, 95.0, 0.92, 0.18),
        (1, "2025-12-19 22:00:00", 5, 85.0, 0.9, 0.16),
        (1, "2025-12-12 12:00:00", 5, 78.0, 0.87, 0.14),
        (1, "2025-12-12 18:00:00", 5, 92.0, 0.91, 0.17),
        # Saturday (2025-12-20) - sqlite dow = 6
        (1, "2025-12-20 10:00:00", 6, 120.0, 0.95, 0.22),
        (1, "2025-12-20 14:00:00", 6, 135.0, 0.97, 0.25),
        (1, "2025-12-20 19:00:00", 6, 140.0, 0.98, 0.26),
        (1, "2025-12-20 22:00:00", 6, 125.0, 0.96, 0.23),
        (1, "2025-12-13 10:00:00", 6, 118.0, 0.94, 0.21),
        (1, "2025-12-13 14:00:00", 6, 130.0, 0.96, 0.24),
        # Sunday (2025-12-21) - sqlite dow = 0
        (1, "2025-12-21 11:00:00", 0, 100.0, 0.9, 0.18),
        (1, "2025-12-21 15:00:00", 0, 110.0, 0.93, 0.2),
        (1, "2025-12-21 20:00:00", 0, 105.0, 0.91, 0.19),
        (1, "2025-12-14 11:00:00", 0, 98.0, 0.89, 0.17),
        (1, "2025-12-14 15:00:00", 0, 108.0, 0.92, 0.19),
    ]

    for msg in messages:
        cursor.execute("""
            INSERT INTO mass_messages (creator_id, sending_time, sending_day_of_week, earnings, view_rate, purchase_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        """, msg)

    conn.commit()
    conn.close()

    return mock_db_path


@pytest.fixture
def sparse_db(mock_db_path):
    """Database with insufficient data for DOW analysis."""
    conn = sqlite3.connect(mock_db_path)
    cursor = conn.cursor()

    # Only insert a few messages (insufficient for DOW analysis)
    # Format: (creator_id, sending_time, sending_day_of_week, earnings, view_rate, purchase_rate)
    messages = [
        (1, "2025-12-15 10:00:00", 1, 50.0, 0.8, 0.1),   # Monday
        (1, "2025-12-16 12:00:00", 2, 40.0, 0.65, 0.07),  # Tuesday
        (1, "2025-12-17 10:00:00", 3, 55.0, 0.72, 0.09),  # Wednesday
    ]

    for msg in messages:
        cursor.execute("""
            INSERT INTO mass_messages (creator_id, sending_time, sending_day_of_week, earnings, view_rate, purchase_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        """, msg)

    conn.commit()
    conn.close()

    return mock_db_path


@pytest.fixture
def sample_dow_multipliers():
    """Sample DOWMultipliers for testing."""
    return DOWMultipliers(
        multipliers={
            0: 0.95,  # Monday
            1: 0.9,   # Tuesday
            2: 1.0,   # Wednesday
            3: 1.05,  # Thursday
            4: 1.1,   # Friday
            5: 1.2,   # Saturday
            6: 1.15,  # Sunday
        },
        confidence=0.85,
        day_confidences={i: 0.8 + i * 0.02 for i in range(7)},
        total_messages=100,
        is_default=False,
        creator_id="test_creator",
    )


# =============================================================================
# SQLite DOW Conversion Tests
# =============================================================================

class TestSQLiteDOWConversion:
    """Tests for SQLite to Python day-of-week conversion."""

    def test_sqlite_to_python_sunday(self):
        """SQLite 0 (Sunday) should map to Python 6."""
        assert convert_sqlite_dow_to_python(0) == 6

    def test_sqlite_to_python_monday(self):
        """SQLite 1 (Monday) should map to Python 0."""
        assert convert_sqlite_dow_to_python(1) == 0

    def test_sqlite_to_python_saturday(self):
        """SQLite 6 (Saturday) should map to Python 5."""
        assert convert_sqlite_dow_to_python(6) == 5

    def test_sqlite_to_python_all_days(self):
        """Verify all SQLite to Python mappings."""
        expected = {
            0: 6,  # Sunday
            1: 0,  # Monday
            2: 1,  # Tuesday
            3: 2,  # Wednesday
            4: 3,  # Thursday
            5: 4,  # Friday
            6: 5,  # Saturday
        }
        for sqlite_dow, python_dow in expected.items():
            assert convert_sqlite_dow_to_python(sqlite_dow) == python_dow

    def test_python_to_sqlite_monday(self):
        """Python 0 (Monday) should map to SQLite 1."""
        assert convert_python_dow_to_sqlite(0) == 1

    def test_python_to_sqlite_sunday(self):
        """Python 6 (Sunday) should map to SQLite 0."""
        assert convert_python_dow_to_sqlite(6) == 0

    def test_python_to_sqlite_all_days(self):
        """Verify all Python to SQLite mappings."""
        expected = {
            0: 1,  # Monday
            1: 2,  # Tuesday
            2: 3,  # Wednesday
            3: 4,  # Thursday
            4: 5,  # Friday
            5: 6,  # Saturday
            6: 0,  # Sunday
        }
        for python_dow, sqlite_dow in expected.items():
            assert convert_python_dow_to_sqlite(python_dow) == sqlite_dow

    def test_roundtrip_conversion(self):
        """Converting back and forth should return original value."""
        for sqlite_dow in range(7):
            python_dow = convert_sqlite_dow_to_python(sqlite_dow)
            back_to_sqlite = convert_python_dow_to_sqlite(python_dow)
            assert back_to_sqlite == sqlite_dow

    def test_invalid_sqlite_dow_negative(self):
        """Negative SQLite DOW should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid SQLite DOW"):
            convert_sqlite_dow_to_python(-1)

    def test_invalid_sqlite_dow_too_high(self):
        """SQLite DOW > 6 should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid SQLite DOW"):
            convert_sqlite_dow_to_python(7)

    def test_invalid_python_dow_negative(self):
        """Negative Python DOW should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Python DOW"):
            convert_python_dow_to_sqlite(-1)

    def test_invalid_python_dow_too_high(self):
        """Python DOW > 6 should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Python DOW"):
            convert_python_dow_to_sqlite(7)


# =============================================================================
# Confidence Calculation Tests
# =============================================================================

class TestConfidenceCalculation:
    """Tests for confidence score calculation."""

    def test_day_confidence_zero_messages(self):
        """Zero messages should return 0.0 confidence."""
        assert _calculate_day_confidence(0) == 0.0

    def test_day_confidence_below_minimum(self):
        """Messages below MIN_MESSAGES_PER_DAY should return 0.0."""
        assert _calculate_day_confidence(MIN_MESSAGES_PER_DAY - 1) == 0.0

    def test_day_confidence_at_minimum(self):
        """Messages at MIN_MESSAGES_PER_DAY should return > 0.0."""
        confidence = _calculate_day_confidence(MIN_MESSAGES_PER_DAY)
        assert confidence > 0.0
        assert confidence < 0.5  # Still low confidence

    def test_day_confidence_medium_messages(self):
        """10-20 messages should give medium confidence."""
        confidence = _calculate_day_confidence(15)
        assert 0.5 <= confidence <= 0.8

    def test_day_confidence_high_messages(self):
        """50+ messages should give high confidence (>= 0.9)."""
        confidence = _calculate_day_confidence(50)
        assert confidence >= 0.9

    def test_day_confidence_saturates(self):
        """Very high message counts should saturate at 1.0."""
        confidence = _calculate_day_confidence(1000)
        assert confidence <= 1.0

    def test_day_confidence_monotonic_increase(self):
        """Confidence should increase with message count."""
        prev_confidence = 0.0
        for count in [5, 10, 20, 50, 100]:
            confidence = _calculate_day_confidence(count)
            assert confidence >= prev_confidence
            prev_confidence = confidence

    def test_overall_confidence_insufficient_total(self):
        """Insufficient total messages should return 0.0."""
        day_confidences = {i: 0.5 for i in range(7)}
        assert _calculate_overall_confidence(day_confidences, MIN_TOTAL_MESSAGES - 1) == 0.0

    def test_overall_confidence_all_zero_days(self):
        """All zero-confidence days should return 0.0."""
        day_confidences = {i: 0.0 for i in range(7)}
        assert _calculate_overall_confidence(day_confidences, 100) == 0.0

    def test_overall_confidence_full_coverage(self):
        """Full week coverage with good per-day confidence."""
        day_confidences = {i: 0.8 for i in range(7)}
        confidence = _calculate_overall_confidence(day_confidences, 100)
        assert confidence >= 0.7  # High confidence with full coverage

    def test_overall_confidence_partial_coverage(self):
        """Partial coverage should reduce overall confidence."""
        # Only 4 days with data
        day_confidences = {
            0: 0.8, 1: 0.8, 2: 0.8, 3: 0.8,
            4: 0.0, 5: 0.0, 6: 0.0
        }
        confidence = _calculate_overall_confidence(day_confidences, 100)
        # Coverage penalty: 4/7 ≈ 0.57
        assert confidence < 0.6


# =============================================================================
# Multiplier Bounds Tests
# =============================================================================

class TestMultiplierBounds:
    """Tests for multiplier bounds enforcement."""

    def test_clamp_within_bounds(self):
        """Values within bounds should pass through unchanged."""
        assert _clamp_multiplier(1.0) == 1.0
        assert _clamp_multiplier(0.9) == 0.9
        assert _clamp_multiplier(1.2) == 1.2

    def test_clamp_at_minimum(self):
        """Values at MULTIPLIER_MIN should be unchanged."""
        assert _clamp_multiplier(MULTIPLIER_MIN) == MULTIPLIER_MIN

    def test_clamp_below_minimum(self):
        """Values below MULTIPLIER_MIN should be clamped."""
        assert _clamp_multiplier(0.5) == MULTIPLIER_MIN
        assert _clamp_multiplier(0.0) == MULTIPLIER_MIN
        assert _clamp_multiplier(-1.0) == MULTIPLIER_MIN

    def test_clamp_at_maximum(self):
        """Values at MULTIPLIER_MAX should be unchanged."""
        assert _clamp_multiplier(MULTIPLIER_MAX) == MULTIPLIER_MAX

    def test_clamp_above_maximum(self):
        """Values above MULTIPLIER_MAX should be clamped."""
        assert _clamp_multiplier(1.5) == MULTIPLIER_MAX
        assert _clamp_multiplier(2.0) == MULTIPLIER_MAX
        assert _clamp_multiplier(10.0) == MULTIPLIER_MAX


# =============================================================================
# Volume Rounding Tests
# =============================================================================

class TestVolumeRounding:
    """Tests for volume rounding behavior."""

    def test_round_exact_integer(self):
        """Exact integers should remain unchanged."""
        assert _round_volume(5.0) == 5
        assert _round_volume(10.0) == 10

    def test_round_up_at_half(self):
        """Banker's rounding: 0.5 rounds to nearest even."""
        # ROUND_HALF_UP: 0.5 always rounds up
        assert _round_volume(2.5) == 3
        assert _round_volume(3.5) == 4

    def test_round_down_below_half(self):
        """Values below 0.5 round down."""
        assert _round_volume(2.4) == 2
        assert _round_volume(2.1) == 2

    def test_round_up_above_half(self):
        """Values above 0.5 round up."""
        assert _round_volume(2.6) == 3
        assert _round_volume(2.9) == 3


# =============================================================================
# DOWMultipliers Data Class Tests
# =============================================================================

class TestDOWMultipliers:
    """Tests for DOWMultipliers data class methods."""

    def test_get_multiplier_existing_day(self, sample_dow_multipliers):
        """Get multiplier for an existing day."""
        assert sample_dow_multipliers.get_multiplier(0) == 0.95  # Monday
        assert sample_dow_multipliers.get_multiplier(5) == 1.2   # Saturday

    def test_get_multiplier_default_fallback(self):
        """Missing day should return 1.0."""
        mults = DOWMultipliers(
            multipliers={0: 1.1},  # Only Monday
            confidence=0.5,
            day_confidences={},
            total_messages=50,
            is_default=False,
        )
        assert mults.get_multiplier(1) == 1.0  # Tuesday missing, default to 1.0

    def test_weekly_distribution_base_volume(self, sample_dow_multipliers):
        """Weekly distribution should preserve total weekly volume."""
        base_volume = 5
        distribution = sample_dow_multipliers.get_weekly_distribution(base_volume)

        # Should have all 7 days
        assert len(distribution) == 7

        # Total should equal base * 7 (within rounding)
        total = sum(distribution.values())
        assert abs(total - base_volume * 7) <= 2  # Allow small rounding error

    def test_weekly_distribution_applies_multipliers(self, sample_dow_multipliers):
        """Higher multiplier days should get more volume."""
        distribution = sample_dow_multipliers.get_weekly_distribution(10)

        # Saturday (1.2 mult) should be higher than Tuesday (0.9 mult)
        assert distribution[5] > distribution[1]

    def test_weekly_distribution_zero_base(self, sample_dow_multipliers):
        """Zero base volume should return zeros."""
        distribution = sample_dow_multipliers.get_weekly_distribution(0)
        assert all(v == 0 for v in distribution.values())


# =============================================================================
# Insufficient Data Handling Tests
# =============================================================================

class TestInsufficientDataHandling:
    """Tests for handling insufficient data scenarios."""

    def test_calculate_multipliers_sparse_data_uses_defaults(self, sparse_db):
        """Sparse data should fall back to default multipliers."""
        mults = calculate_dow_multipliers("test_creator", sparse_db, use_defaults_on_insufficient=True)

        assert mults.is_default
        assert mults.confidence == 0.0
        assert mults.multipliers == DEFAULT_MULTIPLIERS

    def test_calculate_multipliers_sparse_data_raises_error(self, sparse_db):
        """Sparse data should raise error when use_defaults_on_insufficient=False."""
        with pytest.raises(InsufficientDataError):
            calculate_dow_multipliers(
                "test_creator",
                sparse_db,
                use_defaults_on_insufficient=False
            )

    def test_calculate_multipliers_nonexistent_creator(self, mock_db_path):
        """Non-existent creator should use defaults."""
        mults = calculate_dow_multipliers(
            "nonexistent_creator",
            mock_db_path,
            use_defaults_on_insufficient=True
        )

        assert mults.is_default
        assert mults.multipliers == DEFAULT_MULTIPLIERS

    def test_calculate_multipliers_nonexistent_creator_raises(self, mock_db_path):
        """Non-existent creator should raise error when not using defaults."""
        with pytest.raises(InsufficientDataError):
            calculate_dow_multipliers(
                "nonexistent_creator",
                mock_db_path,
                use_defaults_on_insufficient=False
            )


# =============================================================================
# DOW Multiplier Calculation Tests
# =============================================================================

class TestDOWMultiplierCalculation:
    """Tests for DOW multiplier calculation logic."""

    def test_calculate_multipliers_populated_data(self, populated_db):
        """Calculate multipliers from well-populated database."""
        mults = calculate_dow_multipliers("test_creator", populated_db)

        assert not mults.is_default
        # Confidence depends on messages per day (5-6 per day in test data = ~0.3 confidence)
        assert mults.confidence > 0.2
        assert mults.total_messages > MIN_TOTAL_MESSAGES

        # All multipliers should be within bounds
        for mult in mults.multipliers.values():
            assert MULTIPLIER_MIN <= mult <= MULTIPLIER_MAX

    def test_weekend_higher_multipliers(self, populated_db):
        """Weekend days should have higher multipliers (more revenue)."""
        mults = calculate_dow_multipliers("test_creator", populated_db)

        # Saturday (5) and Sunday (6) should be higher than Tuesday (1)
        saturday_mult = mults.get_multiplier(5)
        sunday_mult = mults.get_multiplier(6)
        tuesday_mult = mults.get_multiplier(1)

        assert saturday_mult > tuesday_mult
        assert sunday_mult > tuesday_mult

    def test_multipliers_normalized_around_one(self, populated_db):
        """Average multiplier should be close to 1.0."""
        mults = calculate_dow_multipliers("test_creator", populated_db)

        avg_mult = sum(mults.multipliers.values()) / 7
        assert 0.9 <= avg_mult <= 1.1  # Close to 1.0


# =============================================================================
# Apply DOW Modulation Tests
# =============================================================================

class TestApplyDOWModulation:
    """Tests for applying DOW modulation to volumes."""

    def test_apply_modulation_increases_volume(self, sample_dow_multipliers):
        """Multiplier > 1.0 should increase volume."""
        # Saturday has 1.2 multiplier
        base = 10
        adjusted = apply_dow_modulation(base, 5, sample_dow_multipliers)
        assert adjusted > base

    def test_apply_modulation_decreases_volume(self, sample_dow_multipliers):
        """Multiplier < 1.0 should decrease volume."""
        # Tuesday has 0.9 multiplier
        base = 10
        adjusted = apply_dow_modulation(base, 1, sample_dow_multipliers)
        assert adjusted < base

    def test_apply_modulation_neutral(self):
        """Multiplier of 1.0 should preserve volume."""
        mults = DOWMultipliers(
            multipliers={0: 1.0},
            confidence=0.5,
            day_confidences={0: 0.5},
            total_messages=50,
            is_default=False,
        )
        assert apply_dow_modulation(10, 0, mults) == 10


# =============================================================================
# Day Performance Tests
# =============================================================================

class TestDayPerformance:
    """Tests for DayPerformance data class."""

    def test_day_performance_defaults(self):
        """DayPerformance should have sensible defaults."""
        perf = DayPerformance(day_index=0, day_name="Monday")

        assert perf.message_count == 0
        assert perf.total_revenue == 0.0
        assert perf.avg_revenue == 0.0
        assert perf.avg_view_rate == 0.0
        assert perf.avg_purchase_rate == 0.0

    def test_day_performance_with_data(self):
        """DayPerformance should store provided values."""
        perf = DayPerformance(
            day_index=5,
            day_name="Saturday",
            message_count=25,
            total_revenue=500.0,
            avg_revenue=20.0,
            avg_view_rate=0.85,
            avg_purchase_rate=0.15,
        )

        assert perf.day_index == 5
        assert perf.day_name == "Saturday"
        assert perf.message_count == 25
        assert perf.total_revenue == 500.0


# =============================================================================
# Fetch DOW Performance Tests
# =============================================================================

class TestFetchDOWPerformance:
    """Tests for fetching DOW performance from database."""

    def test_fetch_returns_all_days(self, populated_db):
        """Fetch should return performance for all 7 days."""
        performance = fetch_dow_performance("test_creator", populated_db)

        assert len(performance) == 7
        assert all(isinstance(p, DayPerformance) for p in performance)

    def test_fetch_correct_day_mapping(self, populated_db):
        """Day indices should match Python convention (0=Monday)."""
        performance = fetch_dow_performance("test_creator", populated_db)

        for perf in performance:
            assert 0 <= perf.day_index <= 6
            assert perf.day_name == DAY_NAMES[perf.day_index]

    def test_fetch_aggregates_revenue(self, populated_db):
        """Revenue should be aggregated by day."""
        performance = fetch_dow_performance("test_creator", populated_db)

        # Saturday should have highest revenue based on test data
        saturday_perf = next(p for p in performance if p.day_index == 5)
        tuesday_perf = next(p for p in performance if p.day_index == 1)

        assert saturday_perf.total_revenue > tuesday_perf.total_revenue


# =============================================================================
# Analyze DOW Patterns Tests
# =============================================================================

class TestAnalyzeDOWPatterns:
    """Tests for full DOW pattern analysis."""

    def test_analyze_returns_complete_analysis(self, populated_db):
        """Analysis should include all components."""
        analysis = analyze_dow_patterns("test_creator", populated_db)

        assert isinstance(analysis.multipliers, DOWMultipliers)
        assert len(analysis.day_performance) == 7
        assert analysis.analysis_period_days > 0
        assert 0 <= analysis.data_quality_score <= 100

    def test_data_quality_score_populated(self, populated_db):
        """Well-populated data should have high quality score."""
        analysis = analyze_dow_patterns("test_creator", populated_db)

        assert analysis.data_quality_score >= 50


# =============================================================================
# Weekly Volume Distribution Tests
# =============================================================================

class TestWeeklyVolumeDistribution:
    """Tests for get_weekly_volume_distribution convenience function."""

    def test_returns_dict_with_day_names(self, populated_db):
        """Should return dict with day names as keys."""
        distribution = get_weekly_volume_distribution(5, "test_creator", populated_db)

        assert all(day in distribution for day in DAY_NAMES)
        assert all(isinstance(v, int) for v in distribution.values())

    def test_preserves_weekly_total(self, populated_db):
        """Total weekly volume should be preserved (≈ base * 7)."""
        base = 5
        distribution = get_weekly_volume_distribution(base, "test_creator", populated_db)

        total = sum(distribution.values())
        assert abs(total - base * 7) <= 2  # Allow small rounding error


# =============================================================================
# Default Multipliers Tests
# =============================================================================

class TestDefaultMultipliers:
    """Tests for default multiplier values."""

    def test_default_multipliers_all_days(self):
        """Default multipliers should exist for all days."""
        assert len(DEFAULT_MULTIPLIERS) == 7
        assert all(i in DEFAULT_MULTIPLIERS for i in range(7))

    def test_default_multipliers_weekend_boost(self):
        """Default multipliers should boost weekends."""
        # Friday (4), Saturday (5), Sunday (6) should be >= 1.0
        assert DEFAULT_MULTIPLIERS[4] >= 1.0  # Friday
        assert DEFAULT_MULTIPLIERS[5] >= 1.0  # Saturday
        assert DEFAULT_MULTIPLIERS[6] >= 1.0  # Sunday

    def test_default_multipliers_within_bounds(self):
        """Default multipliers should be within bounds."""
        for mult in DEFAULT_MULTIPLIERS.values():
            assert MULTIPLIER_MIN <= mult <= MULTIPLIER_MAX

    def test_default_multipliers_average_near_one(self):
        """Average of default multipliers should be close to 1.0."""
        avg = sum(DEFAULT_MULTIPLIERS.values()) / 7
        assert 0.95 <= avg <= 1.05


# =============================================================================
# DAY_NAMES Tests
# =============================================================================

class TestDayNames:
    """Tests for DAY_NAMES constant."""

    def test_day_names_length(self):
        """Should have exactly 7 day names."""
        assert len(DAY_NAMES) == 7

    def test_day_names_starts_with_monday(self):
        """First day should be Monday (Python convention)."""
        assert DAY_NAMES[0] == "Monday"

    def test_day_names_ends_with_sunday(self):
        """Last day should be Sunday."""
        assert DAY_NAMES[6] == "Sunday"

    def test_day_names_all_present(self):
        """All day names should be present."""
        expected = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        assert DAY_NAMES == expected


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_end_to_end_volume_modulation(self, populated_db):
        """Full workflow: calculate multipliers -> apply to weekly schedule."""
        # Calculate multipliers
        mults = calculate_dow_multipliers("test_creator", populated_db)

        # Apply to base daily volumes
        base_volume = 5
        weekly_volumes = {}

        for day_idx in range(7):
            adjusted = apply_dow_modulation(base_volume, day_idx, mults)
            weekly_volumes[DAY_NAMES[day_idx]] = adjusted

        # Verify reasonable distribution
        assert all(v >= 1 for v in weekly_volumes.values())  # Minimum 1 per day
        assert all(v <= 10 for v in weekly_volumes.values())  # Reasonable maximum

    def test_sparse_to_populated_transition(self, mock_db_path):
        """System should handle transition from sparse to populated data."""
        # Start with defaults (no data)
        mults1 = calculate_dow_multipliers("test_creator", mock_db_path)
        assert mults1.is_default

        # Add some data
        conn = sqlite3.connect(mock_db_path)
        cursor = conn.cursor()

        # Add enough messages to trigger calculation
        # Use actual schema columns: sending_time, sending_day_of_week, earnings
        for day_offset in range(30):
            # Calculate day of week (SQLite format: 0=Sunday)
            sqlite_dow = day_offset % 7
            cursor.execute("""
                INSERT INTO mass_messages (creator_id, sending_time, sending_day_of_week, earnings, view_rate, purchase_rate)
                VALUES (1, date('2025-12-01', ? || ' days') || ' 12:00:00', ?, ?, 0.8, 0.1)
            """, (day_offset, sqlite_dow, 50.0 + day_offset))

        conn.commit()
        conn.close()

        # Now should calculate real multipliers
        mults2 = calculate_dow_multipliers("test_creator", mock_db_path)
        assert not mults2.is_default
        assert mults2.confidence > 0
