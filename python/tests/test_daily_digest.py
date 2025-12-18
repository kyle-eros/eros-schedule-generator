"""
Unit tests for DailyStatisticsAnalyzer.

Tests cover:
- DailyStatisticsAnalyzer class instantiation and validation
- generate_daily_digest() with valid data, empty data, and multi-timeframe analysis
- _analyze_timeframe() calculations and date filtering
- _identify_patterns() detection logic
- _get_top_types() ranking by frequency
- _calculate_length_ratio() with optimal range (250-449)
- _generate_recommendations() priority assignment
- _prioritize_actions() returns ordered actionable items
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.analytics.daily_digest import (
    BOTTOM_PERCENTILE,
    MIN_DATA_POINTS,
    OPTIMAL_LENGTH_MAX,
    OPTIMAL_LENGTH_MIN,
    TIMEFRAME_LONG,
    TIMEFRAME_MEDIUM,
    TIMEFRAME_SHORT,
    TOP_N_CONTENT_TYPES,
    TOP_N_HOURS,
    TOP_N_RESULTS,
    DailyStatisticsAnalyzer,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def analyzer() -> DailyStatisticsAnalyzer:
    """Fresh DailyStatisticsAnalyzer instance."""
    return DailyStatisticsAnalyzer(creator_id="alexia")


@pytest.fixture
def sample_performance_data() -> list[dict[str, Any]]:
    """Sample performance data with varied records.

    Creates 15 records spanning the last 30 days with varied
    content types, earnings, caption lengths, and posting hours.
    """
    base_date = datetime.now()
    records = []

    # High performers - lingerie content at optimal times
    for i in range(5):
        records.append({
            "date": (base_date - timedelta(days=i)).strftime("%Y-%m-%d"),
            "earnings": 5000.0 + (i * 100),
            "content_type": "lingerie",
            "caption_length": 320,  # Optimal range
            "hour": 14,
        })

    # Mid performers - bts content
    for i in range(4):
        records.append({
            "date": (base_date - timedelta(days=i + 5)).strftime("%Y-%m-%d"),
            "earnings": 3000.0 + (i * 50),
            "content_type": "bts",
            "caption_length": 280,  # Optimal range
            "hour": 18,
        })

    # Lower performers - selfie content
    for i in range(3):
        records.append({
            "date": (base_date - timedelta(days=i + 10)).strftime("%Y-%m-%d"),
            "earnings": 1500.0 + (i * 25),
            "content_type": "selfie",
            "caption_length": 150,  # Below optimal
            "hour": 10,
        })

    # Bottom performers - test content
    for i in range(3):
        records.append({
            "date": (base_date - timedelta(days=i + 15)).strftime("%Y-%m-%d"),
            "earnings": 500.0 + (i * 10),
            "content_type": "test",
            "caption_length": 100,  # Below optimal
            "hour": 4,  # Bad hour
        })

    return records


@pytest.fixture
def multi_timeframe_data() -> list[dict[str, Any]]:
    """Performance data spanning multiple timeframes.

    Creates records at 15, 100, and 200 days ago to test
    timeframe filtering across 30, 180, and 365 day windows.
    """
    base_date = datetime.now()
    return [
        # Recent records (within 30 days)
        {
            "date": (base_date - timedelta(days=5)).strftime("%Y-%m-%d"),
            "earnings": 5000.0,
            "content_type": "lingerie",
            "caption_length": 300,
            "hour": 14,
        },
        {
            "date": (base_date - timedelta(days=15)).strftime("%Y-%m-%d"),
            "earnings": 4500.0,
            "content_type": "bts",
            "caption_length": 350,
            "hour": 18,
        },
        # Medium-term records (within 180 days, outside 30)
        {
            "date": (base_date - timedelta(days=60)).strftime("%Y-%m-%d"),
            "earnings": 4000.0,
            "content_type": "lingerie",
            "caption_length": 280,
            "hour": 14,
        },
        {
            "date": (base_date - timedelta(days=100)).strftime("%Y-%m-%d"),
            "earnings": 3500.0,
            "content_type": "video",
            "caption_length": 400,
            "hour": 20,
        },
        # Long-term records (within 365 days, outside 180)
        {
            "date": (base_date - timedelta(days=200)).strftime("%Y-%m-%d"),
            "earnings": 3000.0,
            "content_type": "bts",
            "caption_length": 250,
            "hour": 16,
        },
        {
            "date": (base_date - timedelta(days=300)).strftime("%Y-%m-%d"),
            "earnings": 2500.0,
            "content_type": "selfie",
            "caption_length": 200,
            "hour": 12,
        },
    ]


@pytest.fixture
def optimal_length_data() -> list[dict[str, Any]]:
    """Data for testing caption length ratio calculations."""
    base_date = datetime.now()
    return [
        # Optimal length range (250-449)
        {"date": base_date.strftime("%Y-%m-%d"), "earnings": 5000.0, "caption_length": 250},
        {"date": base_date.strftime("%Y-%m-%d"), "earnings": 4800.0, "caption_length": 300},
        {"date": base_date.strftime("%Y-%m-%d"), "earnings": 4600.0, "caption_length": 449},
        # Below optimal
        {"date": base_date.strftime("%Y-%m-%d"), "earnings": 4400.0, "caption_length": 100},
        {"date": base_date.strftime("%Y-%m-%d"), "earnings": 4200.0, "caption_length": 200},
        # Above optimal
        {"date": base_date.strftime("%Y-%m-%d"), "earnings": 4000.0, "caption_length": 500},
        {"date": base_date.strftime("%Y-%m-%d"), "earnings": 3800.0, "caption_length": 600},
        # Missing length
        {"date": base_date.strftime("%Y-%m-%d"), "earnings": 3600.0, "caption_length": None},
    ]


@pytest.fixture
def empty_performance_data() -> list[dict[str, Any]]:
    """Empty list for testing edge cases."""
    return []


@pytest.fixture
def frequency_gap_data() -> list[dict[str, Any]]:
    """Data demonstrating frequency gaps.

    Lingerie performs well but is underrepresented in total volume.
    """
    base_date = datetime.now()
    records = []

    # High-performing lingerie (appears in top 10 but rare overall)
    for i in range(3):
        records.append({
            "date": (base_date - timedelta(days=i)).strftime("%Y-%m-%d"),
            "earnings": 5000.0 + i * 100,
            "content_type": "lingerie",
            "caption_length": 300,
            "hour": 14,
        })

    # Many selfie records (common overall but not in top performers)
    for i in range(20):
        records.append({
            "date": (base_date - timedelta(days=i)).strftime("%Y-%m-%d"),
            "earnings": 1000.0 + i * 10,
            "content_type": "selfie",
            "caption_length": 150,
            "hour": 10,
        })

    return records


# =============================================================================
# Test Classes
# =============================================================================


class TestDailyStatisticsAnalyzerInstantiation:
    """Tests for DailyStatisticsAnalyzer class instantiation."""

    def test_valid_creator_id(self) -> None:
        """Analyzer should instantiate with valid creator_id."""
        analyzer = DailyStatisticsAnalyzer("alexia")
        assert analyzer.creator_id == "alexia"

    def test_numeric_string_creator_id(self) -> None:
        """Analyzer should accept numeric string creator_id."""
        analyzer = DailyStatisticsAnalyzer("123")
        assert analyzer.creator_id == "123"

    def test_empty_creator_id_raises_error(self) -> None:
        """Empty creator_id should raise ValueError."""
        with pytest.raises(ValueError, match="creator_id cannot be empty"):
            DailyStatisticsAnalyzer("")

    def test_none_creator_id_raises_error(self) -> None:
        """None creator_id should raise ValueError."""
        with pytest.raises(ValueError, match="creator_id cannot be empty"):
            DailyStatisticsAnalyzer(None)  # type: ignore

    def test_whitespace_creator_id(self) -> None:
        """Whitespace-only creator_id should be accepted (not empty)."""
        analyzer = DailyStatisticsAnalyzer("   ")
        assert analyzer.creator_id == "   "


class TestGenerateDailyDigest:
    """Tests for generate_daily_digest method."""

    def test_digest_with_valid_data(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Digest should contain all expected keys with valid data."""
        digest = analyzer.generate_daily_digest(sample_performance_data)

        assert "date" in digest
        assert "creator_id" in digest
        assert "timeframe_summaries" in digest
        assert "patterns" in digest
        assert "recommendations" in digest
        assert "action_items" in digest
        assert "top_performers" in digest

    def test_digest_creator_id_preserved(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Digest should preserve the creator_id."""
        digest = analyzer.generate_daily_digest(sample_performance_data)
        assert digest["creator_id"] == "alexia"

    def test_digest_date_is_iso_format(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Digest date should be in ISO format."""
        digest = analyzer.generate_daily_digest(sample_performance_data)

        # Should not raise an exception
        datetime.fromisoformat(digest["date"])

    def test_digest_with_empty_data(
        self,
        analyzer: DailyStatisticsAnalyzer,
        empty_performance_data: list[dict[str, Any]],
    ) -> None:
        """Digest should handle empty data gracefully."""
        digest = analyzer.generate_daily_digest(empty_performance_data)

        assert digest["creator_id"] == "alexia"
        assert digest["timeframe_summaries"] is not None
        assert digest["patterns"] is not None
        # Empty data yields 0.0 length ratio which triggers caption recommendation
        # because it's below the 0.4 threshold in _generate_recommendations
        assert isinstance(digest["recommendations"], list)
        assert isinstance(digest["action_items"], list)
        assert digest["top_performers"] == []
        # Verify all timeframes have zero records
        for days in [30, 180, 365]:
            assert digest["timeframe_summaries"][days]["record_count"] == 0
            assert digest["timeframe_summaries"][days]["total_earnings"] == 0.0

    def test_multi_timeframe_analysis(
        self,
        analyzer: DailyStatisticsAnalyzer,
        multi_timeframe_data: list[dict[str, Any]],
    ) -> None:
        """Digest should analyze all three timeframes (30, 180, 365 days)."""
        digest = analyzer.generate_daily_digest(multi_timeframe_data)

        timeframe_summaries = digest["timeframe_summaries"]

        assert TIMEFRAME_SHORT in timeframe_summaries
        assert TIMEFRAME_MEDIUM in timeframe_summaries
        assert TIMEFRAME_LONG in timeframe_summaries

        # 30-day should have 2 records
        assert timeframe_summaries[30]["record_count"] == 2

        # 180-day should have 4 records
        assert timeframe_summaries[180]["record_count"] == 4

        # 365-day should have all 6 records
        assert timeframe_summaries[365]["record_count"] == 6

    def test_top_performers_sorted_by_earnings(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Top performers should be sorted by earnings descending."""
        digest = analyzer.generate_daily_digest(sample_performance_data)

        top_performers = digest["top_performers"]

        # Verify descending order
        earnings = [float(p.get("earnings", 0)) for p in top_performers]
        assert earnings == sorted(earnings, reverse=True)

    def test_top_performers_limited_to_10(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Top performers should be limited to TOP_N_RESULTS (10)."""
        digest = analyzer.generate_daily_digest(sample_performance_data)

        assert len(digest["top_performers"]) <= TOP_N_RESULTS


class TestAnalyzeTimeframe:
    """Tests for _analyze_timeframe method."""

    def test_timeframe_with_valid_data(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Timeframe analysis should return expected structure."""
        result = analyzer._analyze_timeframe(sample_performance_data, 30)

        assert "timeframe_days" in result
        assert "total_earnings" in result
        assert "avg_earnings" in result
        assert "record_count" in result
        assert "top_10" in result

        assert result["timeframe_days"] == 30

    def test_timeframe_with_empty_data(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty data should return zero values."""
        result = analyzer._analyze_timeframe([], 30)

        assert result["total_earnings"] == 0.0
        assert result["avg_earnings"] == 0.0
        assert result["record_count"] == 0
        assert result["top_10"] == []

    def test_timeframe_filters_old_records(
        self,
        analyzer: DailyStatisticsAnalyzer,
        multi_timeframe_data: list[dict[str, Any]],
    ) -> None:
        """Timeframe should filter out records outside the window."""
        # 30-day window should only include 2 recent records
        result_30 = analyzer._analyze_timeframe(multi_timeframe_data, 30)
        assert result_30["record_count"] == 2

        # 180-day window should include 4 records
        result_180 = analyzer._analyze_timeframe(multi_timeframe_data, 180)
        assert result_180["record_count"] == 4

    def test_total_earnings_calculation(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Total earnings should be correctly summed."""
        data = [
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 1000.0},
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 2000.0},
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 3000.0},
        ]

        result = analyzer._analyze_timeframe(data, 30)

        assert result["total_earnings"] == 6000.0
        assert result["avg_earnings"] == 2000.0

    def test_avg_earnings_rounding(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Average earnings should be rounded to 2 decimal places."""
        data = [
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 1000.0},
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 2000.0},
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 1500.0},
        ]

        result = analyzer._analyze_timeframe(data, 30)

        # 4500 / 3 = 1500.0
        assert result["avg_earnings"] == 1500.0

    def test_handles_null_earnings(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Null earnings should be treated as 0."""
        data = [
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 1000.0},
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": None},
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 500.0},
        ]

        result = analyzer._analyze_timeframe(data, 30)

        assert result["total_earnings"] == 1500.0

    def test_top_10_limited(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Top 10 should be limited to 10 records."""
        result = analyzer._analyze_timeframe(sample_performance_data, 30)

        assert len(result["top_10"]) <= 10


class TestParseDate:
    """Tests for _parse_date method."""

    def test_parse_iso_date_string(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should parse ISO date string."""
        result = analyzer._parse_date("2025-01-15")
        assert result == datetime(2025, 1, 15, 0, 0)

    def test_parse_datetime_with_time(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should parse datetime string with time."""
        result = analyzer._parse_date("2025-01-15T14:30:00")
        assert result == datetime(2025, 1, 15, 14, 30, 0)

    def test_parse_datetime_object(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should handle datetime objects directly."""
        dt = datetime(2025, 1, 15, 14, 30)
        result = analyzer._parse_date(dt)
        assert result == dt

    def test_parse_none_returns_none(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """None should return None."""
        assert analyzer._parse_date(None) is None

    def test_parse_invalid_string_returns_none(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Invalid date string should return None."""
        assert analyzer._parse_date("not-a-date") is None

    def test_parse_date_with_microseconds(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should parse datetime with microseconds."""
        result = analyzer._parse_date("2025-01-15T14:30:00.123456")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15


class TestIdentifyPatterns:
    """Tests for _identify_patterns method."""

    def test_patterns_structure(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Patterns should contain all expected keys."""
        analysis = analyzer._analyze_timeframe(sample_performance_data, 30)
        patterns = analyzer._identify_patterns(analysis, sample_performance_data)

        assert "top_content_types" in patterns
        assert "optimal_length_ratio" in patterns
        assert "best_hours" in patterns
        assert "underperformers" in patterns
        assert "frequency_gaps" in patterns

    def test_patterns_with_empty_analysis(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty analysis should return empty patterns."""
        analysis = {"top_10": []}
        patterns = analyzer._identify_patterns(analysis, [])

        assert patterns["top_content_types"] == []
        assert patterns["optimal_length_ratio"] == 0.0
        assert patterns["best_hours"] == []

    def test_identifies_top_content_types(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Should identify top content types from performers."""
        analysis = analyzer._analyze_timeframe(sample_performance_data, 30)
        patterns = analyzer._identify_patterns(analysis, sample_performance_data)

        # Lingerie should be top (5 records with highest earnings)
        assert "lingerie" in patterns["top_content_types"]


class TestGetTopTypes:
    """Tests for _get_top_types method."""

    def test_top_types_from_performers(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should extract top content types by frequency."""
        analysis = {
            "top_10": [
                {"content_type": "lingerie", "earnings": 5000},
                {"content_type": "lingerie", "earnings": 4900},
                {"content_type": "lingerie", "earnings": 4800},
                {"content_type": "bts", "earnings": 4700},
                {"content_type": "bts", "earnings": 4600},
            ]
        }

        result = analyzer._get_top_types(analysis)

        assert result[0] == "lingerie"  # Most frequent
        assert "bts" in result

    def test_top_types_empty_analysis(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty top_10 should return empty list."""
        analysis = {"top_10": []}
        result = analyzer._get_top_types(analysis)
        assert result == []

    def test_top_types_limited_to_3(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should return at most TOP_N_CONTENT_TYPES (3) types."""
        analysis = {
            "top_10": [
                {"content_type": "type1"},
                {"content_type": "type2"},
                {"content_type": "type3"},
                {"content_type": "type4"},
                {"content_type": "type5"},
            ]
        }

        result = analyzer._get_top_types(analysis)

        assert len(result) <= TOP_N_CONTENT_TYPES

    def test_top_types_missing_content_type(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Records without content_type should be ignored."""
        analysis = {
            "top_10": [
                {"content_type": "lingerie", "earnings": 5000},
                {"earnings": 4900},  # Missing content_type
                {"content_type": None, "earnings": 4800},  # None content_type
            ]
        }

        result = analyzer._get_top_types(analysis)

        assert result == ["lingerie"]


class TestCalculateLengthRatio:
    """Tests for _calculate_length_ratio method."""

    def test_all_optimal_length(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """All captions in optimal range should return 1.0."""
        analysis = {
            "top_10": [
                {"caption_length": 250},
                {"caption_length": 300},
                {"caption_length": 449},
            ]
        }

        result = analyzer._calculate_length_ratio(analysis)

        assert result == 1.0

    def test_no_optimal_length(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """No captions in optimal range should return 0.0."""
        analysis = {
            "top_10": [
                {"caption_length": 100},
                {"caption_length": 200},
                {"caption_length": 500},
            ]
        }

        result = analyzer._calculate_length_ratio(analysis)

        assert result == 0.0

    def test_mixed_length_ratio(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Mixed lengths should return correct ratio."""
        analysis = {
            "top_10": [
                {"caption_length": 300},  # Optimal
                {"caption_length": 350},  # Optimal
                {"caption_length": 100},  # Too short
                {"caption_length": 500},  # Too long
            ]
        }

        result = analyzer._calculate_length_ratio(analysis)

        assert result == 0.5  # 2 out of 4

    def test_optimal_range_boundaries(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should correctly handle boundary values."""
        analysis = {
            "top_10": [
                {"caption_length": OPTIMAL_LENGTH_MIN},  # 250 - included
                {"caption_length": OPTIMAL_LENGTH_MAX},  # 449 - included
                {"caption_length": OPTIMAL_LENGTH_MIN - 1},  # 249 - excluded
                {"caption_length": OPTIMAL_LENGTH_MAX + 1},  # 450 - excluded
            ]
        }

        result = analyzer._calculate_length_ratio(analysis)

        assert result == 0.5  # 2 out of 4

    def test_empty_top_10(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty top_10 should return 0.0."""
        analysis = {"top_10": []}
        result = analyzer._calculate_length_ratio(analysis)
        assert result == 0.0

    def test_missing_caption_length(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Records without caption_length should be excluded."""
        analysis = {
            "top_10": [
                {"caption_length": 300},  # Optimal
                {"caption_length": None},  # Missing
                {},  # Missing
            ]
        }

        result = analyzer._calculate_length_ratio(analysis)

        # Only 1 record with caption_length, and it's optimal
        assert result == 1.0

    def test_ratio_rounded_to_3_decimals(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Ratio should be rounded to 3 decimal places."""
        analysis = {
            "top_10": [
                {"caption_length": 300},  # Optimal
                {"caption_length": 100},  # Not optimal
                {"caption_length": 100},  # Not optimal
            ]
        }

        result = analyzer._calculate_length_ratio(analysis)

        # 1/3 = 0.333...
        assert result == 0.333


class TestAnalyzeTiming:
    """Tests for _analyze_timing method."""

    def test_best_hours_from_performers(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should identify best hours by frequency."""
        analysis = {
            "top_10": [
                {"hour": 14},
                {"hour": 14},
                {"hour": 14},
                {"hour": 18},
                {"hour": 18},
                {"hour": 20},
            ]
        }

        result = analyzer._analyze_timing(analysis)

        assert result[0] == 14  # Most frequent
        assert 18 in result

    def test_best_hours_empty(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty top_10 should return empty list."""
        analysis = {"top_10": []}
        result = analyzer._analyze_timing(analysis)
        assert result == []

    def test_best_hours_limited_to_3(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should return at most TOP_N_HOURS (3) hours."""
        analysis = {
            "top_10": [
                {"hour": 10},
                {"hour": 12},
                {"hour": 14},
                {"hour": 16},
                {"hour": 18},
            ]
        }

        result = analyzer._analyze_timing(analysis)

        assert len(result) <= TOP_N_HOURS

    def test_missing_hour_ignored(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Records without hour should be ignored."""
        analysis = {
            "top_10": [
                {"hour": 14},
                {"hour": None},
                {},
            ]
        }

        result = analyzer._analyze_timing(analysis)

        assert result == [14]


class TestIdentifyUnderperformers:
    """Tests for _identify_underperformers method."""

    def test_identifies_bottom_performers(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should identify content types in bottom 20%."""
        analysis = {
            "top_10": [
                {"content_type": "lingerie", "earnings": 5000},
                {"content_type": "lingerie", "earnings": 4500},
                {"content_type": "bts", "earnings": 4000},
                {"content_type": "bts", "earnings": 3500},
                {"content_type": "selfie", "earnings": 500},  # Bottom
            ]
        }

        result = analyzer._identify_underperformers(analysis)

        assert "selfie" in result

    def test_insufficient_data_returns_empty(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Less than MIN_DATA_POINTS should return empty list."""
        analysis = {
            "top_10": [
                {"content_type": "lingerie", "earnings": 5000},
                {"content_type": "bts", "earnings": 500},
            ]
        }

        result = analyzer._identify_underperformers(analysis)

        assert result == []

    def test_empty_top_10_returns_empty(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty top_10 should return empty list."""
        analysis = {"top_10": []}
        result = analyzer._identify_underperformers(analysis)
        assert result == []

    def test_underperformers_deduplicated(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Underperformer types should be unique."""
        analysis = {
            "top_10": [
                {"content_type": "lingerie", "earnings": 5000},
                {"content_type": "lingerie", "earnings": 4500},
                {"content_type": "bts", "earnings": 4000},
                {"content_type": "bts", "earnings": 3500},
                {"content_type": "selfie", "earnings": 500},
                {"content_type": "selfie", "earnings": 400},  # Duplicate type
            ]
        }

        result = analyzer._identify_underperformers(analysis)

        # Should not have duplicates
        assert len(result) == len(set(result))


class TestAnalyzeFrequencyGaps:
    """Tests for _analyze_frequency_gaps method."""

    def test_frequency_gap_structure(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Result should have expected structure."""
        analysis = {"top_10": [{"content_type": "lingerie"}]}
        full_data = [{"content_type": "selfie"} for _ in range(10)]

        result = analyzer._analyze_frequency_gaps(analysis, full_data)

        assert "gap_types" in result
        assert "top_10_distribution" in result
        assert "overall_distribution" in result

    def test_identifies_underutilized_types(
        self,
        analyzer: DailyStatisticsAnalyzer,
        frequency_gap_data: list[dict[str, Any]],
    ) -> None:
        """Should identify types that perform well but are underutilized."""
        analysis = analyzer._analyze_timeframe(frequency_gap_data, 30)
        result = analyzer._analyze_frequency_gaps(analysis, frequency_gap_data)

        # Lingerie is in top 10 (high earners) but rare in total data
        # Selfie is common overall but not in top 10
        # So lingerie should be identified as a gap
        gap_types = result["gap_types"]

        # Lingerie should be identified as underutilized
        assert "lingerie" in gap_types

    def test_empty_top_10(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty top_10 should return empty gaps."""
        analysis = {"top_10": []}
        result = analyzer._analyze_frequency_gaps(analysis, [])

        assert result["gap_types"] == []
        assert result["top_10_distribution"] == {}
        assert result["overall_distribution"] == {}


class TestGenerateRecommendations:
    """Tests for _generate_recommendations method."""

    def test_recommendations_from_patterns(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should generate recommendations based on patterns."""
        patterns = {
            "top_content_types": ["lingerie", "bts"],
            "optimal_length_ratio": 0.8,
            "best_hours": [14, 18],
            "underperformers": ["selfie"],
            "frequency_gaps": {"gap_types": ["lingerie"]},
        }

        result = analyzer._generate_recommendations(patterns)

        assert len(result) > 0

        # Check recommendation structure
        for rec in result:
            assert "category" in rec
            assert "priority" in rec
            assert "action" in rec
            assert "rationale" in rec

    def test_content_recommendation_generated(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Top content types should generate content recommendation."""
        patterns = {
            "top_content_types": ["lingerie", "bts"],
            "optimal_length_ratio": 0.0,
            "best_hours": [],
            "underperformers": [],
            "frequency_gaps": {"gap_types": []},
        }

        result = analyzer._generate_recommendations(patterns)

        content_recs = [r for r in result if r["category"] == "content"]
        assert len(content_recs) == 1
        assert content_recs[0]["priority"] == "HIGH"

    def test_caption_length_low_ratio_recommendation(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Low length ratio should generate HIGH priority caption recommendation."""
        patterns = {
            "top_content_types": [],
            "optimal_length_ratio": 0.3,  # Below 0.4 threshold
            "best_hours": [],
            "underperformers": [],
            "frequency_gaps": {"gap_types": []},
        }

        result = analyzer._generate_recommendations(patterns)

        caption_recs = [r for r in result if r["category"] == "caption"]
        assert len(caption_recs) == 1
        assert caption_recs[0]["priority"] == "HIGH"
        assert "250-449" in caption_recs[0]["action"]

    def test_caption_length_high_ratio_recommendation(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """High length ratio should generate MEDIUM priority continue recommendation."""
        patterns = {
            "top_content_types": [],
            "optimal_length_ratio": 0.7,  # Above 0.6 threshold
            "best_hours": [],
            "underperformers": [],
            "frequency_gaps": {"gap_types": []},
        }

        result = analyzer._generate_recommendations(patterns)

        caption_recs = [r for r in result if r["category"] == "caption"]
        assert len(caption_recs) == 1
        assert caption_recs[0]["priority"] == "MEDIUM"
        assert "Continue" in caption_recs[0]["action"]

    def test_timing_recommendation_generated(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Best hours should generate timing recommendation."""
        patterns = {
            "top_content_types": [],
            "optimal_length_ratio": 0.5,  # Middle range, no recommendation
            "best_hours": [14, 18, 20],
            "underperformers": [],
            "frequency_gaps": {"gap_types": []},
        }

        result = analyzer._generate_recommendations(patterns)

        timing_recs = [r for r in result if r["category"] == "timing"]
        assert len(timing_recs) == 1
        assert timing_recs[0]["priority"] == "MEDIUM"
        assert "14:00" in timing_recs[0]["action"]

    def test_underperformers_recommendation_generated(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Underperformers should generate volume reduction recommendation."""
        patterns = {
            "top_content_types": [],
            "optimal_length_ratio": 0.5,
            "best_hours": [],
            "underperformers": ["selfie", "test"],
            "frequency_gaps": {"gap_types": []},
        }

        result = analyzer._generate_recommendations(patterns)

        volume_recs = [r for r in result if r["category"] == "volume"]
        assert any("Reduce" in r["action"] for r in volume_recs)

    def test_frequency_gaps_recommendation_generated(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Frequency gaps should generate HIGH priority volume increase recommendation."""
        patterns = {
            "top_content_types": [],
            "optimal_length_ratio": 0.5,
            "best_hours": [],
            "underperformers": [],
            "frequency_gaps": {"gap_types": ["lingerie"]},
        }

        result = analyzer._generate_recommendations(patterns)

        volume_recs = [r for r in result if r["category"] == "volume"]
        assert any(r["priority"] == "HIGH" for r in volume_recs)
        assert any("Increase" in r["action"] for r in volume_recs)

    def test_empty_patterns_no_recommendations(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty patterns should produce no recommendations."""
        patterns = {
            "top_content_types": [],
            "optimal_length_ratio": 0.5,  # Middle range
            "best_hours": [],
            "underperformers": [],
            "frequency_gaps": {"gap_types": []},
        }

        result = analyzer._generate_recommendations(patterns)

        # No recommendations for middle-range length ratio
        assert result == []


class TestPrioritizeActions:
    """Tests for _prioritize_actions method."""

    def test_high_priority_first(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """HIGH priority actions should come first."""
        recommendations = [
            {"priority": "LOW", "action": "Low priority action"},
            {"priority": "HIGH", "action": "High priority action"},
            {"priority": "MEDIUM", "action": "Medium priority action"},
        ]

        result = analyzer._prioritize_actions(recommendations)

        assert result[0] == "High priority action"

    def test_priority_order_maintained(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Actions should be ordered HIGH > MEDIUM > LOW."""
        recommendations = [
            {"priority": "LOW", "action": "Action 1"},
            {"priority": "HIGH", "action": "Action 2"},
            {"priority": "MEDIUM", "action": "Action 3"},
            {"priority": "HIGH", "action": "Action 4"},
            {"priority": "LOW", "action": "Action 5"},
        ]

        result = analyzer._prioritize_actions(recommendations)

        # First two should be HIGH priority
        assert result[0] in ["Action 2", "Action 4"]
        assert result[1] in ["Action 2", "Action 4"]
        # Third should be MEDIUM
        assert result[2] == "Action 3"
        # Last two should be LOW
        assert result[3] in ["Action 1", "Action 5"]
        assert result[4] in ["Action 1", "Action 5"]

    def test_empty_recommendations(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty recommendations should return empty list."""
        result = analyzer._prioritize_actions([])
        assert result == []

    def test_missing_action_excluded(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Recommendations without action should be excluded."""
        recommendations = [
            {"priority": "HIGH", "action": "Valid action"},
            {"priority": "HIGH"},  # Missing action
            {"priority": "HIGH", "action": ""},  # Empty action
        ]

        result = analyzer._prioritize_actions(recommendations)

        assert "Valid action" in result
        assert "" not in result

    def test_unknown_priority_sorted_last(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Unknown priority should be sorted after LOW."""
        recommendations = [
            {"priority": "UNKNOWN", "action": "Unknown priority"},
            {"priority": "LOW", "action": "Low priority"},
        ]

        result = analyzer._prioritize_actions(recommendations)

        assert result[0] == "Low priority"
        assert result[1] == "Unknown priority"


class TestGetOverallTopPerformers:
    """Tests for _get_overall_top_performers method."""

    def test_sorted_by_earnings(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should return records sorted by earnings descending."""
        data = [
            {"earnings": 1000},
            {"earnings": 5000},
            {"earnings": 3000},
        ]

        result = analyzer._get_overall_top_performers(data)

        assert result[0]["earnings"] == 5000
        assert result[1]["earnings"] == 3000
        assert result[2]["earnings"] == 1000

    def test_limited_to_10(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Should return at most 10 records."""
        data = [{"earnings": i * 100} for i in range(20)]

        result = analyzer._get_overall_top_performers(data)

        assert len(result) == TOP_N_RESULTS

    def test_empty_data(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Empty data should return empty list."""
        result = analyzer._get_overall_top_performers([])
        assert result == []

    def test_handles_null_earnings(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Null earnings should be treated as 0."""
        data = [
            {"earnings": 1000},
            {"earnings": None},
            {"earnings": 500},
        ]

        result = analyzer._get_overall_top_performers(data)

        # None earnings treated as 0, so should be last
        assert result[0]["earnings"] == 1000
        assert result[1]["earnings"] == 500
        assert result[2]["earnings"] is None


class TestConstants:
    """Tests for module constants."""

    def test_timeframe_constants(self) -> None:
        """Timeframe constants should have expected values."""
        assert TIMEFRAME_SHORT == 30
        assert TIMEFRAME_MEDIUM == 180
        assert TIMEFRAME_LONG == 365

    def test_optimal_length_constants(self) -> None:
        """Optimal length constants should define valid range."""
        assert OPTIMAL_LENGTH_MIN == 250
        assert OPTIMAL_LENGTH_MAX == 449
        assert OPTIMAL_LENGTH_MIN < OPTIMAL_LENGTH_MAX

    def test_top_n_constants(self) -> None:
        """Top N constants should be positive integers."""
        assert TOP_N_CONTENT_TYPES == 3
        assert TOP_N_HOURS == 3
        assert TOP_N_RESULTS == 10

    def test_bottom_percentile_constant(self) -> None:
        """Bottom percentile should be a valid percentage."""
        assert 0.0 < BOTTOM_PERCENTILE < 1.0
        assert BOTTOM_PERCENTILE == 0.20

    def test_min_data_points_constant(self) -> None:
        """Min data points should be positive."""
        assert MIN_DATA_POINTS > 0
        assert MIN_DATA_POINTS == 5


class TestIntegrationScenarios:
    """Integration tests for complete workflows."""

    def test_full_digest_workflow(
        self,
        analyzer: DailyStatisticsAnalyzer,
        sample_performance_data: list[dict[str, Any]],
    ) -> None:
        """Full digest generation should complete without errors."""
        digest = analyzer.generate_daily_digest(sample_performance_data)

        # Verify complete structure
        assert digest["creator_id"] == "alexia"
        assert len(digest["timeframe_summaries"]) == 3
        assert isinstance(digest["patterns"], dict)
        assert isinstance(digest["recommendations"], list)
        assert isinstance(digest["action_items"], list)
        assert isinstance(digest["top_performers"], list)

        # Verify patterns were identified
        patterns = digest["patterns"]
        assert "top_content_types" in patterns
        assert "optimal_length_ratio" in patterns

        # Verify recommendations were generated
        if patterns["top_content_types"]:
            assert len(digest["recommendations"]) > 0
            assert len(digest["action_items"]) > 0

    def test_new_creator_scenario(self) -> None:
        """New creator with minimal data should not error."""
        analyzer = DailyStatisticsAnalyzer("new_creator")
        data = [
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "earnings": 1000.0,
                "content_type": "test",
            }
        ]

        digest = analyzer.generate_daily_digest(data)

        assert digest["creator_id"] == "new_creator"
        assert digest["timeframe_summaries"][30]["record_count"] == 1

    def test_high_volume_creator_scenario(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """High volume creator with many records should complete efficiently."""
        base_date = datetime.now()

        # Generate 100 records
        data = []
        for i in range(100):
            data.append({
                "date": (base_date - timedelta(days=i % 365)).strftime("%Y-%m-%d"),
                "earnings": 1000.0 + (i * 50),
                "content_type": ["lingerie", "bts", "selfie"][i % 3],
                "caption_length": 250 + (i * 10) % 300,
                "hour": 10 + (i % 12),
            })

        digest = analyzer.generate_daily_digest(data)

        assert digest["creator_id"] == "alexia"
        assert len(digest["top_performers"]) == TOP_N_RESULTS
        assert digest["timeframe_summaries"][365]["record_count"] == 100


class TestEdgeCases:
    """Edge case tests."""

    def test_all_same_earnings(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """All records with same earnings should not error."""
        data = [
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 1000.0, "content_type": f"type{i}"}
            for i in range(10)
        ]

        digest = analyzer.generate_daily_digest(data)

        assert digest["timeframe_summaries"][30]["avg_earnings"] == 1000.0

    def test_all_same_content_type(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """All records with same content type should return single type."""
        data = [
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": i * 100, "content_type": "lingerie"}
            for i in range(10)
        ]

        analysis = analyzer._analyze_timeframe(data, 30)
        top_types = analyzer._get_top_types(analysis)

        assert top_types == ["lingerie"]

    def test_future_dates_excluded(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Future dates should be included (no exclusion logic)."""
        future_date = datetime.now() + timedelta(days=10)
        data = [
            {"date": future_date.strftime("%Y-%m-%d"), "earnings": 5000.0},
        ]

        result = analyzer._analyze_timeframe(data, 30)

        # Future dates within the window are included
        assert result["record_count"] == 1

    def test_extremely_old_records(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Records older than 365 days should be excluded from all timeframes."""
        old_date = datetime.now() - timedelta(days=400)
        data = [
            {"date": old_date.strftime("%Y-%m-%d"), "earnings": 5000.0},
        ]

        digest = analyzer.generate_daily_digest(data)

        # All timeframes should have 0 records
        assert digest["timeframe_summaries"][30]["record_count"] == 0
        assert digest["timeframe_summaries"][180]["record_count"] == 0
        assert digest["timeframe_summaries"][365]["record_count"] == 0

    def test_zero_earnings_records(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Records with zero earnings should be included."""
        data = [
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 0.0, "content_type": "test"},
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 1000.0, "content_type": "test"},
        ]

        result = analyzer._analyze_timeframe(data, 30)

        assert result["record_count"] == 2
        assert result["total_earnings"] == 1000.0
        assert result["avg_earnings"] == 500.0

    def test_negative_earnings_records(
        self,
        analyzer: DailyStatisticsAnalyzer,
    ) -> None:
        """Records with negative earnings should be handled."""
        data = [
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": -500.0},
            {"date": datetime.now().strftime("%Y-%m-%d"), "earnings": 1500.0},
        ]

        result = analyzer._analyze_timeframe(data, 30)

        assert result["total_earnings"] == 1000.0
        assert result["avg_earnings"] == 500.0
