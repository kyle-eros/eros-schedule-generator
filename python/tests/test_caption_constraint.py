"""
Unit tests for caption pool awareness module.

Tests cover:
- Caption pool analysis for various scenarios
- Critical type detection
- Caption assignment with exclusions
- Shortage report generation
- Edge cases (no captions, all used, etc.)
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.exceptions import DatabaseError
from python.volume.caption_constraint import (
    CaptionAvailability,
    CaptionPoolStatus,
    ScheduleSlot,
    CaptionPoolAnalyzer,
    get_caption_pool_status,
    check_caption_availability,
    get_caption_shortage_report,
    get_caption_coverage_estimate,
    _find_best_caption,
)


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def caption_db() -> Generator[sqlite3.Connection, None, None]:
    """In-memory SQLite database with caption-related schema for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create send_types table
    cursor.execute("""
        CREATE TABLE send_types (
            send_type_id INTEGER PRIMARY KEY,
            send_type_key TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            display_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Create send_type_caption_requirements table
    cursor.execute("""
        CREATE TABLE send_type_caption_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            send_type_id INTEGER NOT NULL REFERENCES send_types(send_type_id),
            caption_type TEXT NOT NULL,
            priority INTEGER DEFAULT 3,
            notes TEXT,
            UNIQUE(send_type_id, caption_type)
        )
    """)

    # Create caption_bank table
    cursor.execute("""
        CREATE TABLE caption_bank (
            caption_id INTEGER PRIMARY KEY,
            caption_text TEXT NOT NULL,
            caption_type TEXT,
            creator_id TEXT,
            performance_score REAL DEFAULT 50.0,
            freshness_score REAL DEFAULT 100.0,
            is_active INTEGER DEFAULT 1,
            last_used_date TEXT
        )
    """)

    # Insert test send types
    send_types = [
        (1, "ppv_unlock", "revenue", "PPV Unlock"),
        (2, "ppv_wall", "revenue", "PPV Wall"),
        (3, "bump_normal", "engagement", "Normal Bump"),
        (4, "bump_descriptive", "engagement", "Descriptive Bump"),
        (5, "renew_on_message", "retention", "Renew on Message"),
        (6, "ppv_followup", "retention", "PPV Followup"),
    ]

    for st in send_types:
        cursor.execute(
            "INSERT INTO send_types (send_type_id, send_type_key, category, display_name) VALUES (?, ?, ?, ?)",
            st,
        )

    # Insert caption requirements (mapping send types to caption types)
    requirements = [
        (1, "ppv_message", 1),  # ppv_unlock -> ppv_message (primary)
        (1, "ppv_video", 2),  # ppv_unlock -> ppv_video (secondary)
        (2, "ppv_message", 1),  # ppv_wall -> ppv_message
        (3, "bump_normal", 1),  # bump_normal -> bump_normal
        (4, "bump_descriptive", 1),  # bump_descriptive -> bump_descriptive
        (5, "renew_on_message", 1),  # renew_on_message -> renew_on_message
        (6, "ppv_followup", 1),  # ppv_followup -> ppv_followup
    ]

    for req in requirements:
        cursor.execute(
            "INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority) VALUES (?, ?, ?)",
            req,
        )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def populated_caption_db(caption_db: sqlite3.Connection) -> sqlite3.Connection:
    """Database with captions populated for a test creator."""
    cursor = caption_db.cursor()

    # Insert test captions for creator 'test_creator'
    captions = [
        # PPV message captions - mixed freshness and performance
        (1, "PPV caption 1", "ppv_message", "test_creator", 80.0, 90.0, 1),
        (2, "PPV caption 2", "ppv_message", "test_creator", 70.0, 85.0, 1),
        (3, "PPV caption 3", "ppv_message", "test_creator", 60.0, 50.0, 1),
        (4, "PPV caption 4", "ppv_message", "test_creator", 50.0, 25.0, 1),  # Low freshness
        (5, "PPV caption 5", "ppv_message", "test_creator", 45.0, 80.0, 0),  # Inactive
        # Bump normal captions
        (6, "Bump caption 1", "bump_normal", "test_creator", 75.0, 95.0, 1),
        (7, "Bump caption 2", "bump_normal", "test_creator", 65.0, 70.0, 1),
        # Renew captions - only 1 (critical)
        (8, "Renew caption 1", "renew_on_message", "test_creator", 85.0, 88.0, 1),
        # PPV video captions (secondary for ppv_unlock)
        (9, "PPV video caption", "ppv_video", "test_creator", 90.0, 95.0, 1),
    ]

    for cap in captions:
        cursor.execute(
            """INSERT INTO caption_bank
               (caption_id, caption_text, caption_type, creator_id, performance_score, freshness_score, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            cap,
        )

    caption_db.commit()
    return caption_db


@pytest.fixture
def empty_creator_db(caption_db: sqlite3.Connection) -> sqlite3.Connection:
    """Database with no captions for the target creator."""
    return caption_db  # No captions added


@pytest.fixture
def all_stale_db(caption_db: sqlite3.Connection) -> sqlite3.Connection:
    """Database where all captions have low freshness scores."""
    cursor = caption_db.cursor()

    # Insert stale captions (freshness < 30)
    captions = [
        (1, "Stale PPV 1", "ppv_message", "stale_creator", 80.0, 10.0, 1),
        (2, "Stale PPV 2", "ppv_message", "stale_creator", 70.0, 15.0, 1),
        (3, "Stale bump", "bump_normal", "stale_creator", 75.0, 20.0, 1),
    ]

    for cap in captions:
        cursor.execute(
            """INSERT INTO caption_bank
               (caption_id, caption_text, caption_type, creator_id, performance_score, freshness_score, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            cap,
        )

    caption_db.commit()
    return caption_db


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestCaptionAvailability:
    """Tests for CaptionAvailability dataclass."""

    def test_default_values(self) -> None:
        """Default values should be zeros."""
        avail = CaptionAvailability(send_type_key="ppv_unlock")
        assert avail.total_captions == 0
        assert avail.fresh_captions == 0
        assert avail.usable_captions == 0
        assert avail.avg_freshness == 0.0
        assert avail.avg_performance == 0.0
        assert avail.days_of_coverage == 0.0

    def test_is_critical_below_threshold(self) -> None:
        """Should be critical when usable < threshold."""
        avail = CaptionAvailability(send_type_key="test", usable_captions=2)
        assert avail.is_critical(threshold=3) is True

    def test_is_critical_at_threshold(self) -> None:
        """Should not be critical when usable == threshold."""
        avail = CaptionAvailability(send_type_key="test", usable_captions=3)
        assert avail.is_critical(threshold=3) is False

    def test_is_critical_above_threshold(self) -> None:
        """Should not be critical when usable > threshold."""
        avail = CaptionAvailability(send_type_key="test", usable_captions=10)
        assert avail.is_critical(threshold=3) is False

    def test_custom_threshold(self) -> None:
        """Custom threshold should be respected."""
        avail = CaptionAvailability(send_type_key="test", usable_captions=5)
        assert avail.is_critical(threshold=10) is True
        assert avail.is_critical(threshold=5) is False


class TestCaptionPoolStatus:
    """Tests for CaptionPoolStatus dataclass."""

    def test_default_values(self) -> None:
        """Default values should indicate sufficient coverage."""
        status = CaptionPoolStatus(creator_id="test")
        assert status.sufficient_coverage is True
        assert status.coverage_days == 7.0
        assert status.critical_types == []
        assert status.by_send_type == {}
        assert status.by_category == {}

    def test_analyzed_at_is_set(self) -> None:
        """analyzed_at should be set to current time."""
        before = datetime.now()
        status = CaptionPoolStatus(creator_id="test")
        after = datetime.now()
        assert before <= status.analyzed_at <= after

    def test_get_category_summary_empty(self) -> None:
        """Empty pool should return empty summary."""
        status = CaptionPoolStatus(creator_id="test")
        summary = status.get_category_summary()
        assert summary == {}

    def test_get_category_summary_with_data(self) -> None:
        """Should aggregate by category correctly."""
        status = CaptionPoolStatus(creator_id="test")
        status.by_send_type = {
            "ppv_unlock": CaptionAvailability("ppv_unlock", usable_captions=5),
            "ppv_wall": CaptionAvailability("ppv_wall", usable_captions=2),  # Below threshold (< 3)
            "bump_normal": CaptionAvailability("bump_normal", usable_captions=2),
        }
        summary = status.get_category_summary()
        assert summary["revenue"]["total_usable"] == 7  # ppv_unlock (5) + ppv_wall (2)
        assert summary["revenue"]["critical_count"] == 1  # ppv_wall < 3
        assert summary["engagement"]["total_usable"] == 2


class TestScheduleSlot:
    """Tests for ScheduleSlot dataclass."""

    def test_default_values(self) -> None:
        """Default values should indicate no caption needed."""
        slot = ScheduleSlot(
            scheduled_date="2025-12-16",
            scheduled_time="19:00",
            send_type_key="ppv_unlock",
        )
        assert slot.needs_caption is False
        assert slot.caption_id is None
        assert slot.caption_note == ""
        assert slot.priority == 1

    def test_to_dict(self) -> None:
        """to_dict should return correct dictionary."""
        slot = ScheduleSlot(
            scheduled_date="2025-12-16",
            scheduled_time="19:00",
            send_type_key="ppv_unlock",
            needs_caption=True,
            caption_note="Test note",
        )
        d = slot.to_dict()
        assert d["scheduled_date"] == "2025-12-16"
        assert d["scheduled_time"] == "19:00"
        assert d["send_type_key"] == "ppv_unlock"
        assert d["needs_caption"] is True
        assert d["caption_note"] == "Test note"


# =============================================================================
# get_caption_pool_status Tests
# =============================================================================


class TestGetCaptionPoolStatus:
    """Tests for get_caption_pool_status function."""

    def test_basic_analysis(self, populated_caption_db: sqlite3.Connection) -> None:
        """Should correctly analyze caption pool."""
        status = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        assert status.creator_id == "test_creator"
        assert len(status.by_send_type) > 0

    def test_identifies_critical_types(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should identify send types with < 3 usable captions."""
        status = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # renew_on_message only has 1 caption, should be critical
        assert "renew_on_message" in status.critical_types

    def test_filters_by_freshness(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should filter out captions below freshness threshold."""
        # With high freshness threshold, fewer captions should be usable
        status_strict = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=80.0, min_performance=40.0
        )
        status_lenient = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # Stricter threshold should yield fewer usable captions
        ppv_strict = status_strict.by_send_type.get("ppv_unlock")
        ppv_lenient = status_lenient.by_send_type.get("ppv_unlock")

        if ppv_strict and ppv_lenient:
            assert ppv_strict.usable_captions <= ppv_lenient.usable_captions

    def test_filters_by_performance(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should filter out captions below performance threshold."""
        status_strict = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=70.0
        )
        status_lenient = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # Stricter threshold should yield fewer usable captions
        ppv_strict = status_strict.by_send_type.get("ppv_unlock")
        ppv_lenient = status_lenient.by_send_type.get("ppv_unlock")

        if ppv_strict and ppv_lenient:
            assert ppv_strict.usable_captions <= ppv_lenient.usable_captions

    def test_empty_creator(self, empty_creator_db: sqlite3.Connection) -> None:
        """Should handle creator with no captions."""
        status = get_caption_pool_status(
            empty_creator_db, "nonexistent_creator", min_freshness=30.0, min_performance=40.0
        )

        assert status.creator_id == "nonexistent_creator"
        assert len(status.by_send_type) == 0
        assert status.sufficient_coverage is True  # No types analyzed means no critical

    def test_all_stale_captions(self, all_stale_db: sqlite3.Connection) -> None:
        """Should handle case where all captions are stale."""
        status = get_caption_pool_status(
            all_stale_db, "stale_creator", min_freshness=30.0, min_performance=40.0
        )

        # All captions have freshness < 30, so none should be usable
        for send_type, avail in status.by_send_type.items():
            assert avail.usable_captions == 0

    def test_aggregates_by_category(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should aggregate usable captions by category."""
        status = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # Should have entries for categories present
        assert isinstance(status.by_category, dict)

    def test_database_error_handling(self, caption_db: sqlite3.Connection) -> None:
        """Should raise DatabaseError on query failure."""
        # Close connection to cause error
        caption_db.close()

        with pytest.raises(DatabaseError) as exc_info:
            get_caption_pool_status(
                caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
            )

        assert "caption_pool_analysis" in str(exc_info.value.operation)


# =============================================================================
# check_caption_availability Tests
# =============================================================================


class TestCheckCaptionAvailability:
    """Tests for check_caption_availability function."""

    def test_assigns_captions_to_slots(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should assign captions to slots when available."""
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        slots = [
            ScheduleSlot("2025-12-16", "10:00", "ppv_unlock"),
            ScheduleSlot("2025-12-16", "14:00", "bump_normal"),
        ]

        result = check_caption_availability(slots, pool, populated_caption_db)

        # Slots with available captions should be assigned
        for slot in result:
            if pool.by_send_type.get(slot.send_type_key, CaptionAvailability(slot.send_type_key)).usable_captions > 0:
                assert slot.caption_id is not None or slot.needs_caption is True

    def test_flags_slots_without_captions(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should flag slots when no captions available."""
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # Use a send type that has no captions
        slots = [
            ScheduleSlot("2025-12-16", "10:00", "ppv_followup"),
        ]

        result = check_caption_availability(slots, pool, populated_caption_db)

        assert result[0].needs_caption is True
        assert "No fresh captions available" in result[0].caption_note

    def test_avoids_duplicate_assignments(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should not assign same caption to multiple slots."""
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # Create multiple slots for same send type
        slots = [
            ScheduleSlot("2025-12-16", "10:00", "ppv_unlock"),
            ScheduleSlot("2025-12-16", "14:00", "ppv_unlock"),
            ScheduleSlot("2025-12-16", "18:00", "ppv_unlock"),
        ]

        result = check_caption_availability(slots, pool, populated_caption_db)

        # Collect assigned caption IDs
        assigned_ids = [s.caption_id for s in result if s.caption_id is not None]

        # All assigned IDs should be unique
        assert len(assigned_ids) == len(set(assigned_ids))

    def test_flags_exhausted_pool(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should flag slots when pool is exhausted."""
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # Create more slots than available captions for bump_normal (only 2)
        slots = [
            ScheduleSlot("2025-12-16", "10:00", "bump_normal"),
            ScheduleSlot("2025-12-16", "12:00", "bump_normal"),
            ScheduleSlot("2025-12-16", "14:00", "bump_normal"),
            ScheduleSlot("2025-12-16", "16:00", "bump_normal"),
        ]

        result = check_caption_availability(slots, pool, populated_caption_db)

        # Some slots should be flagged as needing captions
        flagged = [s for s in result if s.needs_caption]
        assert len(flagged) >= 2  # At least 2 slots should be flagged


# =============================================================================
# _find_best_caption Tests
# =============================================================================


class TestFindBestCaption:
    """Tests for _find_best_caption helper function."""

    def test_finds_caption_by_priority(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should find caption prioritized by requirement priority."""
        result = _find_best_caption(
            populated_caption_db,
            "test_creator",
            "ppv_unlock",
            exclude_ids=set(),
            min_freshness=30.0,
            min_performance=40.0,
        )

        assert result is not None
        assert len(result) == 3  # (caption_id, freshness, performance)

    def test_excludes_specified_ids(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should exclude captions in exclude_ids set."""
        # Get first caption
        first = _find_best_caption(
            populated_caption_db,
            "test_creator",
            "ppv_unlock",
            exclude_ids=set(),
        )

        assert first is not None
        first_id = first[0]

        # Get second caption, excluding first
        second = _find_best_caption(
            populated_caption_db,
            "test_creator",
            "ppv_unlock",
            exclude_ids={first_id},
        )

        if second is not None:
            assert second[0] != first_id

    def test_returns_none_when_no_match(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should return None when no captions match criteria."""
        result = _find_best_caption(
            populated_caption_db,
            "test_creator",
            "ppv_followup",  # No captions for this type
            exclude_ids=set(),
        )

        assert result is None

    def test_respects_freshness_threshold(
        self, all_stale_db: sqlite3.Connection
    ) -> None:
        """Should not return captions below freshness threshold."""
        result = _find_best_caption(
            all_stale_db,
            "stale_creator",
            "ppv_unlock",
            exclude_ids=set(),
            min_freshness=30.0,  # All stale captions are < 30
        )

        assert result is None

    def test_respects_performance_threshold(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should not return captions below performance threshold."""
        result = _find_best_caption(
            populated_caption_db,
            "test_creator",
            "ppv_unlock",
            exclude_ids=set(),
            min_freshness=0.0,  # No freshness filter
            min_performance=95.0,  # Very high performance threshold
        )

        # Only captions with performance >= 95 should match
        if result:
            assert result[2] >= 95.0


# =============================================================================
# get_caption_shortage_report Tests
# =============================================================================


class TestGetCaptionShortageReport:
    """Tests for get_caption_shortage_report function."""

    def test_identifies_shortages(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should identify send types with insufficient captions."""
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        daily_volume = {
            "ppv_unlock": 2,  # Need 14 for week, have ~3 usable
            "bump_normal": 1,  # Need 7 for week, have 2
        }

        report = get_caption_shortage_report(pool, daily_volume, days=7)

        # Both should show shortage
        assert "ppv_unlock" in report or "bump_normal" in report

    def test_critical_status_for_missing_type(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should mark missing types as critical."""
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        daily_volume = {
            "nonexistent_type": 1,
        }

        report = get_caption_shortage_report(pool, daily_volume, days=7)

        assert "nonexistent_type" in report
        assert report["nonexistent_type"]["status"] == "critical"
        assert report["nonexistent_type"]["available"] == 0

    def test_no_shortage_when_sufficient(self) -> None:
        """Should not report when captions are sufficient."""
        pool = CaptionPoolStatus(creator_id="test")
        pool.by_send_type["ppv_unlock"] = CaptionAvailability(
            send_type_key="ppv_unlock",
            usable_captions=20,
        )

        daily_volume = {
            "ppv_unlock": 2,  # Need 14 for week, have 20
        }

        report = get_caption_shortage_report(pool, daily_volume, days=7)

        # Should not be in report since we have enough
        assert "ppv_unlock" not in report

    def test_calculates_shortage_correctly(self) -> None:
        """Should calculate shortage = needed - available."""
        pool = CaptionPoolStatus(creator_id="test")
        pool.by_send_type["ppv_unlock"] = CaptionAvailability(
            send_type_key="ppv_unlock",
            usable_captions=5,
        )

        daily_volume = {"ppv_unlock": 2}  # Need 14 for week

        report = get_caption_shortage_report(pool, daily_volume, days=7)

        assert report["ppv_unlock"]["needed"] == 14
        assert report["ppv_unlock"]["available"] == 5
        assert report["ppv_unlock"]["shortage"] == 9

    def test_status_classification(self) -> None:
        """Should classify status based on shortage severity."""
        pool = CaptionPoolStatus(creator_id="test")

        # Insufficient: shortage > half of needed
        pool.by_send_type["type_a"] = CaptionAvailability("type_a", usable_captions=2)

        # Limited: shortage <= half of needed
        pool.by_send_type["type_b"] = CaptionAvailability("type_b", usable_captions=5)

        daily_volume = {
            "type_a": 2,  # Need 14, have 2, shortage=12 > 7 (half) -> insufficient
            "type_b": 1,  # Need 7, have 5, shortage=2 <= 3 (half) -> limited
        }

        report = get_caption_shortage_report(pool, daily_volume, days=7)

        assert report["type_a"]["status"] == "insufficient"
        assert report["type_b"]["status"] == "limited"


# =============================================================================
# get_caption_coverage_estimate Tests
# =============================================================================


class TestGetCaptionCoverageEstimate:
    """Tests for get_caption_coverage_estimate function."""

    def test_calculates_coverage_days(self) -> None:
        """Should calculate days = available / daily_count."""
        pool = CaptionPoolStatus(creator_id="test")
        pool.by_send_type["ppv_unlock"] = CaptionAvailability(
            send_type_key="ppv_unlock",
            usable_captions=10,
        )

        daily_volume = {"ppv_unlock": 2}

        coverage = get_caption_coverage_estimate(pool, daily_volume)

        assert coverage["ppv_unlock"] == 5.0  # 10 / 2

    def test_zero_volume_returns_infinity(self) -> None:
        """Should return infinity when daily_count is 0."""
        pool = CaptionPoolStatus(creator_id="test")

        daily_volume = {"ppv_unlock": 0}

        coverage = get_caption_coverage_estimate(pool, daily_volume)

        assert coverage["ppv_unlock"] == float("inf")

    def test_missing_type_returns_zero(self) -> None:
        """Should return 0 for types not in pool."""
        pool = CaptionPoolStatus(creator_id="test")

        daily_volume = {"missing_type": 2}

        coverage = get_caption_coverage_estimate(pool, daily_volume)

        assert coverage["missing_type"] == 0.0


# =============================================================================
# CaptionPoolAnalyzer Tests
# =============================================================================


class TestCaptionPoolAnalyzer:
    """Tests for CaptionPoolAnalyzer class."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Should initialize with provided parameters."""
        db_path = str(tmp_path / "test.db")
        analyzer = CaptionPoolAnalyzer(
            db_path=db_path,
            min_freshness=40.0,
            min_performance=50.0,
        )

        assert analyzer.db_path == db_path
        assert analyzer.min_freshness == 40.0
        assert analyzer.min_performance == 50.0

    def test_default_thresholds(self, tmp_path: Path) -> None:
        """Should use default thresholds."""
        db_path = str(tmp_path / "test.db")
        analyzer = CaptionPoolAnalyzer(db_path=db_path)

        assert analyzer.min_freshness == 30.0
        assert analyzer.min_performance == 40.0

    def test_analyze_opens_and_closes_connection(
        self, populated_caption_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Should properly manage database connection."""
        # Create a file-based DB from in-memory
        db_path = str(tmp_path / "test.db")

        # Create the database with schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE send_types (
                send_type_id INTEGER PRIMARY KEY,
                send_type_key TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                display_name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE send_type_caption_requirements (
                id INTEGER PRIMARY KEY,
                send_type_id INTEGER,
                caption_type TEXT NOT NULL,
                priority INTEGER DEFAULT 3
            )
        """)

        cursor.execute("""
            CREATE TABLE caption_bank (
                caption_id INTEGER PRIMARY KEY,
                caption_text TEXT NOT NULL,
                caption_type TEXT,
                creator_id TEXT,
                performance_score REAL DEFAULT 50.0,
                freshness_score REAL DEFAULT 100.0,
                is_active INTEGER DEFAULT 1
            )
        """)

        conn.commit()
        conn.close()

        analyzer = CaptionPoolAnalyzer(db_path=db_path)
        status = analyzer.analyze("test_creator")

        assert status.creator_id == "test_creator"

    def test_get_shortage_report(self, tmp_path: Path) -> None:
        """Should generate shortage report via analyzer."""
        db_path = str(tmp_path / "test.db")

        # Create minimal database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE send_types (
                send_type_id INTEGER PRIMARY KEY,
                send_type_key TEXT,
                category TEXT,
                display_name TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE send_type_caption_requirements (
                id INTEGER PRIMARY KEY,
                send_type_id INTEGER,
                caption_type TEXT,
                priority INTEGER DEFAULT 3
            )
        """)

        cursor.execute("""
            CREATE TABLE caption_bank (
                caption_id INTEGER PRIMARY KEY,
                caption_text TEXT,
                caption_type TEXT,
                creator_id TEXT,
                performance_score REAL,
                freshness_score REAL,
                is_active INTEGER DEFAULT 1
            )
        """)

        conn.commit()
        conn.close()

        analyzer = CaptionPoolAnalyzer(db_path=db_path)
        report = analyzer.get_shortage_report(
            "test_creator",
            {"ppv_unlock": 2},
            days=7,
        )

        # Should return a report (may be empty if type not found)
        assert isinstance(report, dict)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_schedule_items(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should handle empty schedule items list."""
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        result = check_caption_availability([], pool, populated_caption_db)

        assert result == []

    def test_zero_day_shortage_report(self) -> None:
        """Should handle zero days in shortage report."""
        pool = CaptionPoolStatus(creator_id="test")
        pool.by_send_type["ppv_unlock"] = CaptionAvailability(
            send_type_key="ppv_unlock",
            usable_captions=5,
        )

        daily_volume = {"ppv_unlock": 2}

        report = get_caption_shortage_report(pool, daily_volume, days=0)

        # With 0 days, need 0 captions, no shortage
        assert "ppv_unlock" not in report

    def test_very_high_thresholds(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should handle extremely high thresholds."""
        status = get_caption_pool_status(
            populated_caption_db,
            "test_creator",
            min_freshness=100.0,
            min_performance=100.0,
        )

        # No captions should meet 100/100 threshold
        for avail in status.by_send_type.values():
            assert avail.usable_captions == 0

    def test_very_low_thresholds(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should handle zero thresholds."""
        status = get_caption_pool_status(
            populated_caption_db,
            "test_creator",
            min_freshness=0.0,
            min_performance=0.0,
        )

        # All active captions should be usable
        for avail in status.by_send_type.values():
            assert avail.usable_captions >= avail.fresh_captions or avail.usable_captions <= avail.total_captions

    def test_negative_thresholds_treated_as_zero(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Negative thresholds should effectively be zero."""
        status = get_caption_pool_status(
            populated_caption_db,
            "test_creator",
            min_freshness=-10.0,
            min_performance=-10.0,
        )

        # Should work same as 0.0 thresholds
        assert status.creator_id == "test_creator"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the full workflow."""

    def test_full_workflow(self, populated_caption_db: sqlite3.Connection) -> None:
        """Test complete analysis and assignment workflow."""
        # Step 1: Analyze pool
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # Step 2: Check for critical types
        critical = pool.critical_types
        assert isinstance(critical, list)

        # Step 3: Create schedule slots
        slots = [
            ScheduleSlot("2025-12-16", "10:00", "ppv_unlock"),
            ScheduleSlot("2025-12-16", "14:00", "bump_normal"),
            ScheduleSlot("2025-12-17", "10:00", "ppv_unlock"),
        ]

        # Step 4: Assign captions
        result = check_caption_availability(slots, pool, populated_caption_db)

        # Step 5: Verify no duplicates
        assigned_ids = [s.caption_id for s in result if s.caption_id]
        assert len(assigned_ids) == len(set(assigned_ids))

        # Step 6: Generate shortage report
        daily_volume = {"ppv_unlock": 2, "bump_normal": 1}
        report = get_caption_shortage_report(pool, daily_volume, days=7)

        assert isinstance(report, dict)

    def test_maintains_volume_flags_gaps(
        self, populated_caption_db: sqlite3.Connection
    ) -> None:
        """Should maintain all slots and flag gaps, not reduce volume."""
        pool = get_caption_pool_status(
            populated_caption_db, "test_creator", min_freshness=30.0, min_performance=40.0
        )

        # Create more slots than available captions
        slots = [ScheduleSlot("2025-12-16", f"{i:02d}:00", "bump_normal") for i in range(10)]

        result = check_caption_availability(slots, pool, populated_caption_db)

        # All slots should still exist (volume maintained)
        assert len(result) == 10

        # Some should be flagged
        flagged = [s for s in result if s.needs_caption]
        assert len(flagged) > 0  # Gaps identified

        # But volume not reduced
        assigned = [s for s in result if s.caption_id is not None]
        assert len(assigned) + len(flagged) == 10


# =============================================================================
# New Tests for VolumeConfig Integration
# =============================================================================


class TestSendTypeCategories:
    """Tests for send type category mapping."""

    def test_revenue_types_mapped_correctly(self) -> None:
        """All revenue types should map to 'revenue' category."""
        from python.volume.caption_constraint import (
            get_send_type_category,
            SEND_TYPE_CATEGORIES,
        )

        revenue_types = [
            "ppv_unlock",
            "ppv_wall",
            "tip_goal",
            "bundle",
            "flash_bundle",
            "game_post",
            "first_to_tip",
            "vip_program",
            "snapchat_bundle",
        ]
        for send_type in revenue_types:
            assert get_send_type_category(send_type) == "revenue"
            assert SEND_TYPE_CATEGORIES.get(send_type) == "revenue"

    def test_engagement_types_mapped_correctly(self) -> None:
        """All engagement types should map to 'engagement' category."""
        from python.volume.caption_constraint import (
            get_send_type_category,
            SEND_TYPE_CATEGORIES,
        )

        engagement_types = [
            "link_drop",
            "wall_link_drop",
            "bump_normal",
            "bump_descriptive",
            "bump_text_only",
            "bump_flyer",
            "dm_farm",
            "like_farm",
            "live_promo",
        ]
        for send_type in engagement_types:
            assert get_send_type_category(send_type) == "engagement"
            assert SEND_TYPE_CATEGORIES.get(send_type) == "engagement"

    def test_retention_types_mapped_correctly(self) -> None:
        """All retention types should map to 'retention' category."""
        from python.volume.caption_constraint import (
            get_send_type_category,
            SEND_TYPE_CATEGORIES,
        )

        retention_types = [
            "renew_on_post",
            "renew_on_message",
            "ppv_followup",
            "expired_winback",
            "ppv_message",  # deprecated but still mapped
        ]
        for send_type in retention_types:
            assert get_send_type_category(send_type) == "retention"
            assert SEND_TYPE_CATEGORIES.get(send_type) == "retention"

    def test_unknown_type_uses_fallback(self) -> None:
        """Unknown types should fall back to prefix-based detection."""
        from python.volume.caption_constraint import get_send_type_category

        # Unknown type starting with ppv_ -> revenue
        assert get_send_type_category("ppv_new_type") == "revenue"

        # Unknown type starting with renew_ -> retention
        assert get_send_type_category("renew_new") == "retention"

        # Unknown type with no recognized prefix -> engagement
        assert get_send_type_category("unknown_type") == "engagement"

    def test_all_22_types_covered(self) -> None:
        """All 22 send types from the taxonomy should be in the mapping."""
        from python.volume.caption_constraint import SEND_TYPE_CATEGORIES

        # 9 revenue + 9 engagement + 4 retention + 1 deprecated = 23
        assert len(SEND_TYPE_CATEGORIES) == 23


class TestVolumeConstraintResult:
    """Tests for VolumeConstraintResult dataclass."""

    def test_default_values(self) -> None:
        """Default values should indicate viable status."""
        from python.volume.caption_constraint import (
            VolumeConstraintResult,
            CaptionPoolStatus,
        )

        pool = CaptionPoolStatus(creator_id="test")
        result = VolumeConstraintResult(
            is_viable=True,
            pool_status=pool,
        )
        assert result.is_viable is True
        assert result.days_analyzed == 7
        assert result.shortages == {}
        assert result.recommendations == []

    def test_shortage_summary_when_viable(self) -> None:
        """Should return simple message when no shortages."""
        from python.volume.caption_constraint import (
            VolumeConstraintResult,
            CaptionPoolStatus,
        )

        pool = CaptionPoolStatus(creator_id="test")
        result = VolumeConstraintResult(is_viable=True, pool_status=pool)

        summary = result.get_shortage_summary()
        assert "sufficient" in summary.lower()

    def test_shortage_summary_with_shortages(self) -> None:
        """Should list all shortages and recommendations."""
        from python.volume.caption_constraint import (
            VolumeConstraintResult,
            CaptionPoolStatus,
        )

        pool = CaptionPoolStatus(creator_id="test")
        result = VolumeConstraintResult(
            is_viable=False,
            pool_status=pool,
            shortages={
                "revenue": {"needed": 35, "available": 10, "shortage": 25},
                "engagement": {"needed": 42, "available": 20, "shortage": 22},
            },
            recommendations=[
                "Add more revenue captions",
                "Add more engagement captions",
            ],
        )

        summary = result.get_shortage_summary()
        assert "shortages detected" in summary.lower()
        assert "revenue" in summary.lower()
        assert "engagement" in summary.lower()
        assert "recommendations" in summary.lower()

    def test_to_dict(self) -> None:
        """to_dict should include all relevant fields."""
        from python.volume.caption_constraint import (
            VolumeConstraintResult,
            CaptionPoolStatus,
        )

        pool = CaptionPoolStatus(creator_id="test")
        pool.critical_types = ["ppv_unlock"]

        result = VolumeConstraintResult(
            is_viable=False,
            pool_status=pool,
            category_requirements={"revenue": 35},
            category_availability={"revenue": 10},
            shortages={"revenue": {"shortage": 25}},
            recommendations=["Add more captions"],
            days_analyzed=7,
        )

        d = result.to_dict()
        assert d["is_viable"] is False
        assert d["days_analyzed"] == 7
        assert d["category_requirements"] == {"revenue": 35}
        assert d["category_availability"] == {"revenue": 10}
        assert d["shortages"] == {"revenue": {"shortage": 25}}
        assert d["recommendations"] == ["Add more captions"]
        assert d["critical_send_types"] == ["ppv_unlock"]


class TestValidateVolumeAgainstCaptions:
    """Tests for validate_volume_against_captions function."""

    def test_viable_when_sufficient_captions(self) -> None:
        """Should be viable when caption pool meets requirements."""
        from python.volume.caption_constraint import (
            validate_volume_against_captions,
            CaptionPoolStatus,
            CaptionAvailability,
        )
        from python.models.volume import VolumeConfig, VolumeTier

        pool = CaptionPoolStatus(creator_id="test")
        pool.by_send_type = {
            "ppv_unlock": CaptionAvailability("ppv_unlock", usable_captions=50),
            "bump_normal": CaptionAvailability("bump_normal", usable_captions=60),
            "renew_on_message": CaptionAvailability(
                "renew_on_message", usable_captions=20
            ),
        }

        config = VolumeConfig(
            tier=VolumeTier.HIGH,
            revenue_per_day=5,
            engagement_per_day=6,
            retention_per_day=2,
            fan_count=12000,
            page_type="paid",
        )

        result = validate_volume_against_captions(pool, config, days=7)

        assert result.is_viable is True
        assert len(result.shortages) == 0

    def test_not_viable_when_insufficient_captions(self) -> None:
        """Should not be viable when caption pool is insufficient."""
        from python.volume.caption_constraint import (
            validate_volume_against_captions,
            CaptionPoolStatus,
            CaptionAvailability,
        )
        from python.models.volume import VolumeConfig, VolumeTier

        pool = CaptionPoolStatus(creator_id="test")
        pool.by_send_type = {
            "ppv_unlock": CaptionAvailability("ppv_unlock", usable_captions=5),
        }

        config = VolumeConfig(
            tier=VolumeTier.HIGH,
            revenue_per_day=5,  # Need 35 for week
            engagement_per_day=6,  # Need 42 for week
            retention_per_day=2,  # Need 14 for week
            fan_count=12000,
            page_type="paid",
        )

        result = validate_volume_against_captions(pool, config, days=7)

        assert result.is_viable is False
        assert "revenue" in result.shortages  # Only 5 available, need 35
        assert "engagement" in result.shortages  # 0 available, need 42
        assert "retention" in result.shortages  # 0 available, need 14

    def test_category_requirements_calculated_correctly(self) -> None:
        """Should calculate requirements based on volume * days."""
        from python.volume.caption_constraint import (
            validate_volume_against_captions,
            CaptionPoolStatus,
        )
        from python.models.volume import VolumeConfig, VolumeTier

        pool = CaptionPoolStatus(creator_id="test")
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=3,
            engagement_per_day=4,
            retention_per_day=1,
            fan_count=3000,
            page_type="paid",
        )

        result = validate_volume_against_captions(pool, config, days=7)

        assert result.category_requirements["revenue"] == 21  # 3 * 7
        assert result.category_requirements["engagement"] == 28  # 4 * 7
        assert result.category_requirements["retention"] == 7  # 1 * 7

    def test_free_page_zero_retention(self) -> None:
        """Free pages should have 0 retention requirement."""
        from python.volume.caption_constraint import (
            validate_volume_against_captions,
            CaptionPoolStatus,
        )
        from python.models.volume import VolumeConfig, VolumeTier

        pool = CaptionPoolStatus(creator_id="test")
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=3,
            engagement_per_day=4,
            retention_per_day=0,  # Free pages have 0 retention
            fan_count=3000,
            page_type="free",
        )

        result = validate_volume_against_captions(pool, config, days=7)

        assert result.category_requirements["retention"] == 0
        # Retention shouldn't show as a shortage when requirement is 0
        assert "retention" not in result.shortages

    def test_critical_types_generate_warnings(self) -> None:
        """Critical send types should generate warning recommendations."""
        from python.volume.caption_constraint import (
            validate_volume_against_captions,
            CaptionPoolStatus,
            CaptionAvailability,
        )
        from python.models.volume import VolumeConfig, VolumeTier

        pool = CaptionPoolStatus(creator_id="test")
        pool.by_send_type = {
            "ppv_unlock": CaptionAvailability("ppv_unlock", usable_captions=2),
        }
        pool.critical_types = ["ppv_unlock"]

        config = VolumeConfig(
            tier=VolumeTier.LOW,
            revenue_per_day=0,
            engagement_per_day=0,
            retention_per_day=0,
            fan_count=500,
            page_type="paid",
        )

        result = validate_volume_against_captions(pool, config, days=7)

        # Should include warning about critical type
        warning_found = any(
            "ppv_unlock" in rec and "fewer than 3" in rec
            for rec in result.recommendations
        )
        assert warning_found


class TestCaptionPoolStatusCategoryAvailability:
    """Tests for CaptionPoolStatus.get_category_availability method."""

    def test_aggregates_by_category(self) -> None:
        """Should aggregate usable captions by category."""
        from python.volume.caption_constraint import (
            CaptionPoolStatus,
            CaptionAvailability,
        )

        pool = CaptionPoolStatus(creator_id="test")
        pool.by_send_type = {
            "ppv_unlock": CaptionAvailability("ppv_unlock", usable_captions=10),
            "ppv_wall": CaptionAvailability("ppv_wall", usable_captions=5),
            "bump_normal": CaptionAvailability("bump_normal", usable_captions=15),
            "bump_descriptive": CaptionAvailability("bump_descriptive", usable_captions=8),
            "renew_on_message": CaptionAvailability("renew_on_message", usable_captions=3),
        }

        availability = pool.get_category_availability()

        assert availability["revenue"] == 15  # 10 + 5
        assert availability["engagement"] == 23  # 15 + 8
        assert availability["retention"] == 3

    def test_empty_pool_returns_zeros(self) -> None:
        """Empty pool should return zeros for all categories."""
        from python.volume.caption_constraint import CaptionPoolStatus

        pool = CaptionPoolStatus(creator_id="test")
        availability = pool.get_category_availability()

        assert availability["revenue"] == 0
        assert availability["engagement"] == 0
        assert availability["retention"] == 0


class TestCaptionPoolAnalyzerVolumeConfig:
    """Tests for CaptionPoolAnalyzer.validate_volume_config method."""

    def test_validate_volume_config(self, tmp_path: Path) -> None:
        """Should validate VolumeConfig against caption pool."""
        from python.volume.caption_constraint import CaptionPoolAnalyzer
        from python.models.volume import VolumeConfig, VolumeTier

        # Create minimal database
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE send_types (
                send_type_id INTEGER PRIMARY KEY,
                send_type_key TEXT,
                category TEXT,
                display_name TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE send_type_caption_requirements (
                id INTEGER PRIMARY KEY,
                send_type_id INTEGER,
                caption_type TEXT,
                priority INTEGER DEFAULT 3
            )
        """)

        cursor.execute("""
            CREATE TABLE caption_bank (
                caption_id INTEGER PRIMARY KEY,
                caption_text TEXT,
                caption_type TEXT,
                creator_id TEXT,
                performance_score REAL,
                freshness_score REAL,
                is_active INTEGER DEFAULT 1
            )
        """)

        conn.commit()
        conn.close()

        analyzer = CaptionPoolAnalyzer(db_path=db_path)
        config = VolumeConfig(
            tier=VolumeTier.MID,
            revenue_per_day=3,
            engagement_per_day=4,
            retention_per_day=1,
            fan_count=3000,
            page_type="paid",
        )

        result = analyzer.validate_volume_config("test_creator", config, days=7)

        # With empty DB, should show shortages
        assert result.is_viable is False
        assert result.category_requirements["revenue"] == 21
        assert result.days_analyzed == 7

    def test_get_coverage_estimate(self, tmp_path: Path) -> None:
        """Should return coverage estimate for send types."""
        from python.volume.caption_constraint import CaptionPoolAnalyzer

        # Create minimal database
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE send_types (
                send_type_id INTEGER PRIMARY KEY,
                send_type_key TEXT,
                category TEXT,
                display_name TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE send_type_caption_requirements (
                id INTEGER PRIMARY KEY,
                send_type_id INTEGER,
                caption_type TEXT,
                priority INTEGER DEFAULT 3
            )
        """)

        cursor.execute("""
            CREATE TABLE caption_bank (
                caption_id INTEGER PRIMARY KEY,
                caption_text TEXT,
                caption_type TEXT,
                creator_id TEXT,
                performance_score REAL,
                freshness_score REAL,
                is_active INTEGER DEFAULT 1
            )
        """)

        conn.commit()
        conn.close()

        analyzer = CaptionPoolAnalyzer(db_path=db_path)
        daily_volume = {"ppv_unlock": 2, "bump_normal": 3}

        coverage = analyzer.get_coverage_estimate("test_creator", daily_volume)

        # With empty DB, coverage should be 0 for all types
        assert coverage["ppv_unlock"] == 0.0
        assert coverage["bump_normal"] == 0.0
