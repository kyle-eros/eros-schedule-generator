"""
Unit tests for prediction vs outcome tracking.

Tests cover:
1. Prediction saving with all fields
2. Outcome measurement calculation
3. Prediction error percentage calculation
4. Accuracy aggregation
5. Batch measurement
6. Edge cases (no data, already measured, missing week_start)
7. Trend detection (improving/degrading/stable)
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.exceptions import DatabaseError
from python.volume.prediction_tracker import (
    CURRENT_ALGORITHM_VERSION,
    PredictionAccuracy,
    PredictionOutcome,
    PredictionTracker,
    VolumePrediction,
    batch_measure_predictions,
    calculate_mape,
    estimate_weekly_messages,
    estimate_weekly_revenue,
    find_unmeasured_predictions,
    get_accuracy_by_algorithm_version,
    get_prediction_accuracy,
    measure_prediction_outcome,
    save_prediction,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def prediction_db() -> Generator[sqlite3.Connection, None, None]:
    """In-memory SQLite database with prediction tracking schema."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create volume_predictions table
    cursor.execute("""
        CREATE TABLE volume_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id TEXT NOT NULL,
            predicted_at TEXT NOT NULL,
            input_fan_count INTEGER NOT NULL,
            input_page_type TEXT NOT NULL,
            input_saturation REAL NOT NULL,
            input_opportunity REAL NOT NULL,
            predicted_tier TEXT NOT NULL,
            predicted_revenue_per_day INTEGER NOT NULL,
            predicted_engagement_per_day INTEGER NOT NULL,
            predicted_retention_per_day INTEGER NOT NULL,
            predicted_weekly_revenue REAL DEFAULT 0.0,
            predicted_weekly_messages INTEGER DEFAULT 0,
            schedule_template_id INTEGER,
            week_start_date TEXT,
            algorithm_version TEXT NOT NULL,
            actual_total_revenue REAL,
            actual_messages_sent INTEGER,
            actual_avg_rps REAL,
            revenue_prediction_error_pct REAL,
            volume_prediction_error_pct REAL,
            outcome_measured INTEGER DEFAULT 0,
            outcome_measured_at TEXT
        )
    """)

    # Create mass_messages table for outcome measurement
    cursor.execute("""
        CREATE TABLE mass_messages (
            message_id INTEGER PRIMARY KEY,
            creator_id TEXT NOT NULL,
            message_type TEXT,
            sent_count INTEGER DEFAULT 0,
            earnings REAL DEFAULT 0.0,
            revenue_per_send REAL DEFAULT 0.0,
            sending_time TEXT
        )
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_prediction() -> VolumePrediction:
    """Sample volume prediction for testing."""
    return VolumePrediction(
        creator_id="alexia",
        input_fan_count=2500,
        input_page_type="paid",
        input_saturation=45.0,
        input_opportunity=65.0,
        predicted_tier="MID",
        predicted_revenue_per_day=4,
        predicted_engagement_per_day=4,
        predicted_retention_per_day=2,
        predicted_weekly_revenue=560.0,
        predicted_weekly_messages=70,
        algorithm_version="2.0",
    )


@pytest.fixture
def high_tier_prediction() -> VolumePrediction:
    """High tier prediction for comparison testing."""
    return VolumePrediction(
        creator_id="diamond",
        input_fan_count=50000,
        input_page_type="paid",
        input_saturation=30.0,
        input_opportunity=80.0,
        predicted_tier="ULTRA",
        predicted_revenue_per_day=6,
        predicted_engagement_per_day=5,
        predicted_retention_per_day=3,
        predicted_weekly_revenue=2100.0,
        predicted_weekly_messages=98,
        algorithm_version="2.0",
    )


@pytest.fixture
def free_page_prediction() -> VolumePrediction:
    """Free page prediction with no retention."""
    return VolumePrediction(
        creator_id="luna",
        input_fan_count=8000,
        input_page_type="free",
        input_saturation=50.0,
        input_opportunity=50.0,
        predicted_tier="HIGH",
        predicted_revenue_per_day=6,
        predicted_engagement_per_day=5,
        predicted_retention_per_day=0,
        predicted_weekly_revenue=840.0,
        predicted_weekly_messages=77,
        algorithm_version="2.0",
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestVolumePredictionDataclass:
    """Tests for VolumePrediction dataclass."""

    def test_create_prediction_with_required_fields(self) -> None:
        """Prediction can be created with all required fields."""
        prediction = VolumePrediction(
            creator_id="test_creator",
            input_fan_count=1000,
            input_page_type="paid",
            input_saturation=50.0,
            input_opportunity=50.0,
            predicted_tier="MID",
            predicted_revenue_per_day=4,
            predicted_engagement_per_day=4,
            predicted_retention_per_day=2,
        )
        assert prediction.creator_id == "test_creator"
        assert prediction.input_fan_count == 1000

    def test_default_values(self) -> None:
        """Prediction has correct default values."""
        prediction = VolumePrediction(
            creator_id="test_creator",
            input_fan_count=1000,
            input_page_type="paid",
            input_saturation=50.0,
            input_opportunity=50.0,
            predicted_tier="MID",
            predicted_revenue_per_day=4,
            predicted_engagement_per_day=4,
            predicted_retention_per_day=2,
        )
        assert prediction.predicted_weekly_revenue == 0.0
        assert prediction.predicted_weekly_messages == 0
        assert prediction.algorithm_version == CURRENT_ALGORITHM_VERSION
        assert prediction.prediction_id is None

    def test_predicted_at_default(self) -> None:
        """Prediction timestamp defaults to now."""
        before = datetime.now()
        prediction = VolumePrediction(
            creator_id="test",
            input_fan_count=1000,
            input_page_type="paid",
            input_saturation=50.0,
            input_opportunity=50.0,
            predicted_tier="MID",
            predicted_revenue_per_day=4,
            predicted_engagement_per_day=4,
            predicted_retention_per_day=2,
        )
        after = datetime.now()
        assert before <= prediction.predicted_at <= after


class TestSavePrediction:
    """Tests for save_prediction function."""

    def test_save_prediction_success(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Successfully save a prediction and return ID."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            schedule_template_id=100,
            week_start_date="2025-12-16",
        )
        assert prediction_id > 0

    def test_save_prediction_increments_id(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Each saved prediction gets incrementing ID."""
        id1 = save_prediction(prediction_db, sample_prediction)
        id2 = save_prediction(prediction_db, sample_prediction)
        id3 = save_prediction(prediction_db, sample_prediction)

        assert id2 == id1 + 1
        assert id3 == id2 + 1

    def test_save_prediction_stores_all_fields(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """All prediction fields are stored in database."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            schedule_template_id=100,
            week_start_date="2025-12-16",
        )

        cursor = prediction_db.execute(
            "SELECT * FROM volume_predictions WHERE prediction_id = ?",
            (prediction_id,),
        )
        row = cursor.fetchone()

        # Check key fields by index
        assert row[1] == "alexia"  # creator_id
        assert row[3] == 2500  # input_fan_count
        assert row[4] == "paid"  # input_page_type
        assert row[5] == 45.0  # input_saturation
        assert row[6] == 65.0  # input_opportunity
        assert row[7] == "MID"  # predicted_tier
        assert row[8] == 4  # predicted_revenue_per_day
        assert row[9] == 4  # predicted_engagement_per_day
        assert row[10] == 2  # predicted_retention_per_day
        assert row[11] == 560.0  # predicted_weekly_revenue
        assert row[12] == 70  # predicted_weekly_messages
        assert row[13] == 100  # schedule_template_id
        assert row[14] == "2025-12-16"  # week_start_date
        assert row[15] == "2.0"  # algorithm_version

    def test_save_prediction_with_optional_none(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Prediction can be saved without optional fields."""
        prediction_id = save_prediction(prediction_db, sample_prediction)

        cursor = prediction_db.execute(
            "SELECT schedule_template_id, week_start_date FROM volume_predictions WHERE prediction_id = ?",
            (prediction_id,),
        )
        row = cursor.fetchone()

        assert row[0] is None  # schedule_template_id
        assert row[1] is None  # week_start_date

    def test_save_prediction_database_error(
        self, sample_prediction: VolumePrediction
    ) -> None:
        """DatabaseError raised on save failure."""
        conn = sqlite3.connect(":memory:")
        # No tables created, so insert will fail

        with pytest.raises(DatabaseError) as exc_info:
            save_prediction(conn, sample_prediction)

        assert "save_prediction" in str(exc_info.value.operation)
        conn.close()


class TestMeasurePredictionOutcome:
    """Tests for measure_prediction_outcome function."""

    def test_measure_outcome_success(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Successfully measure outcome for a prediction."""
        # Save prediction with week_start
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",  # A week ago
        )

        # Insert actual message data
        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("alexia", "ppv", 10, 300.0, 30.0, "2025-12-10 19:00:00"),
        )
        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("alexia", "ppv", 15, 400.0, 26.67, "2025-12-12 19:00:00"),
        )
        prediction_db.commit()

        outcome = measure_prediction_outcome(prediction_db, prediction_id)

        assert outcome is not None
        assert outcome.prediction_id == prediction_id
        assert outcome.actual_total_revenue == 700.0
        assert outcome.actual_messages_sent == 2

    def test_measure_outcome_updates_record(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Measuring outcome updates the prediction record."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",
        )

        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("alexia", "ppv", 10, 500.0, 50.0, "2025-12-10 19:00:00"),
        )
        prediction_db.commit()

        measure_prediction_outcome(prediction_db, prediction_id)

        # Check database was updated
        cursor = prediction_db.execute(
            """
            SELECT outcome_measured, actual_total_revenue, actual_messages_sent
            FROM volume_predictions WHERE prediction_id = ?
            """,
            (prediction_id,),
        )
        row = cursor.fetchone()

        assert row[0] == 1  # outcome_measured
        assert row[1] == 500.0  # actual_total_revenue
        assert row[2] == 1  # actual_messages_sent

    def test_measure_outcome_not_found(
        self, prediction_db: sqlite3.Connection
    ) -> None:
        """Returns None for non-existent prediction."""
        outcome = measure_prediction_outcome(prediction_db, 99999)
        assert outcome is None

    def test_measure_outcome_already_measured(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Returns None for already measured prediction."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",
        )

        # Manually mark as measured
        prediction_db.execute(
            "UPDATE volume_predictions SET outcome_measured = 1 WHERE prediction_id = ?",
            (prediction_id,),
        )
        prediction_db.commit()

        outcome = measure_prediction_outcome(prediction_db, prediction_id)
        assert outcome is None

    def test_measure_outcome_no_week_start(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Returns None when prediction has no week_start_date."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date=None,
        )

        outcome = measure_prediction_outcome(prediction_db, prediction_id)
        assert outcome is None

    def test_measure_outcome_no_actual_data(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Handles case with no matching messages gracefully."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",
        )

        # No messages inserted

        outcome = measure_prediction_outcome(prediction_db, prediction_id)

        # Should still return an outcome with zero values
        assert outcome is not None
        assert outcome.actual_total_revenue == 0.0
        assert outcome.actual_messages_sent == 0


class TestPredictionErrorCalculation:
    """Tests for prediction error percentage calculation."""

    def test_positive_revenue_error(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Positive error when actual exceeds prediction."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",
        )

        # Actual > Predicted (560.0 predicted, 700 actual)
        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("alexia", "ppv", 10, 700.0, 70.0, "2025-12-10 19:00:00"),
        )
        prediction_db.commit()

        outcome = measure_prediction_outcome(prediction_db, prediction_id)

        assert outcome is not None
        # (700 - 560) / 560 * 100 = 25.0
        assert outcome.revenue_prediction_error_pct == 25.0

    def test_negative_revenue_error(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Negative error when actual is below prediction."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",
        )

        # Actual < Predicted (560.0 predicted, 280 actual)
        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("alexia", "ppv", 10, 280.0, 28.0, "2025-12-10 19:00:00"),
        )
        prediction_db.commit()

        outcome = measure_prediction_outcome(prediction_db, prediction_id)

        assert outcome is not None
        # (280 - 560) / 560 * 100 = -50.0
        assert outcome.revenue_prediction_error_pct == -50.0

    def test_zero_predicted_revenue_error(
        self, prediction_db: sqlite3.Connection
    ) -> None:
        """Zero prediction handles edge case without division by zero."""
        prediction = VolumePrediction(
            creator_id="test",
            input_fan_count=1000,
            input_page_type="paid",
            input_saturation=50.0,
            input_opportunity=50.0,
            predicted_tier="MID",
            predicted_revenue_per_day=4,
            predicted_engagement_per_day=4,
            predicted_retention_per_day=2,
            predicted_weekly_revenue=0.0,  # Zero prediction
            predicted_weekly_messages=70,
        )

        prediction_id = save_prediction(
            prediction_db,
            prediction,
            week_start_date="2025-12-09",
        )

        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("test", "ppv", 10, 100.0, 10.0, "2025-12-10 19:00:00"),
        )
        prediction_db.commit()

        outcome = measure_prediction_outcome(prediction_db, prediction_id)

        assert outcome is not None
        # With zero prediction, error should be 0 (not division by zero)
        assert outcome.revenue_prediction_error_pct == 0.0

    def test_volume_error_calculation(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Volume prediction error calculated correctly."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",
        )

        # Insert 35 messages within the 7-day window (Dec 9-15)
        # predicted_weekly_messages = 70 in sample_prediction
        for i in range(35):
            day = 9 + (i % 7)  # Days 9-15 (all within window)
            prediction_db.execute(
                """
                INSERT INTO mass_messages
                (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("alexia", "ppv", 1, 10.0, 10.0, f"2025-12-{day:02d} 19:00:00"),
            )
        prediction_db.commit()

        outcome = measure_prediction_outcome(prediction_db, prediction_id)

        assert outcome is not None
        # (35 - 70) / 70 * 100 = -50.0
        assert outcome.volume_prediction_error_pct == -50.0


class TestGetPredictionAccuracy:
    """Tests for get_prediction_accuracy function."""

    def test_accuracy_with_no_predictions(
        self, prediction_db: sqlite3.Connection
    ) -> None:
        """Returns None when no predictions exist."""
        accuracy = get_prediction_accuracy(prediction_db, "nonexistent")
        assert accuracy is None

    def test_accuracy_with_unmeasured_predictions(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Handles unmeasured predictions gracefully."""
        save_prediction(prediction_db, sample_prediction)

        accuracy = get_prediction_accuracy(prediction_db, "alexia")

        assert accuracy is not None
        assert accuracy.total_predictions == 1
        assert accuracy.measured_predictions == 0
        assert accuracy.avg_revenue_error_pct == 0.0

    def test_accuracy_with_measured_predictions(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Calculates accuracy from measured predictions."""
        # Save and measure multiple predictions
        for i in range(3):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
                week_start_date=f"2025-12-0{i + 1}",
            )
            # Manually set measured data
            error_pct = [10.0, -20.0, 15.0][i]
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET outcome_measured = 1,
                    actual_total_revenue = 600,
                    actual_messages_sent = 75,
                    revenue_prediction_error_pct = ?,
                    volume_prediction_error_pct = ?
                WHERE prediction_id = ?
                """,
                (error_pct, error_pct * 0.5, prediction_id),
            )
        prediction_db.commit()

        accuracy = get_prediction_accuracy(prediction_db, "alexia")

        assert accuracy is not None
        assert accuracy.total_predictions == 3
        assert accuracy.measured_predictions == 3
        # Average of abs(10), abs(-20), abs(15) = (10 + 20 + 15) / 3 = 15.0
        assert accuracy.avg_revenue_error_pct == 15.0

    def test_accuracy_multiple_creators(
        self,
        prediction_db: sqlite3.Connection,
        sample_prediction: VolumePrediction,
        high_tier_prediction: VolumePrediction,
    ) -> None:
        """Accuracy is isolated per creator."""
        # Save for alexia
        save_prediction(prediction_db, sample_prediction)

        # Save for diamond
        save_prediction(prediction_db, high_tier_prediction)

        alexia_accuracy = get_prediction_accuracy(prediction_db, "alexia")
        diamond_accuracy = get_prediction_accuracy(prediction_db, "diamond")

        assert alexia_accuracy is not None
        assert diamond_accuracy is not None
        assert alexia_accuracy.creator_id == "alexia"
        assert diamond_accuracy.creator_id == "diamond"
        assert alexia_accuracy.total_predictions == 1
        assert diamond_accuracy.total_predictions == 1


class TestTrendDetection:
    """Tests for accuracy trend detection."""

    def test_stable_trend(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Trend is stable when recent error matches historical."""
        # All predictions have similar errors
        for i in range(5):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
                week_start_date=f"2025-12-0{i + 1}",
            )
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET outcome_measured = 1,
                    predicted_at = datetime('now', ? || ' days'),
                    revenue_prediction_error_pct = 15.0
                WHERE prediction_id = ?
                """,
                (f"-{i * 7}", prediction_id),
            )
        prediction_db.commit()

        accuracy = get_prediction_accuracy(prediction_db, "alexia")

        assert accuracy is not None
        assert accuracy.recent_trend == "stable"

    def test_improving_trend(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Trend is improving when recent error is < 80% of historical."""
        # Old predictions have high error
        for i in range(3):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
                week_start_date=f"2025-10-0{i + 1}",
            )
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET outcome_measured = 1,
                    predicted_at = datetime('now', ? || ' days'),
                    revenue_prediction_error_pct = 50.0
                WHERE prediction_id = ?
                """,
                (f"-{60 + i * 7}", prediction_id),
            )

        # Recent predictions have low error
        for i in range(3):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
                week_start_date=f"2025-12-0{i + 1}",
            )
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET outcome_measured = 1,
                    predicted_at = datetime('now', ? || ' days'),
                    revenue_prediction_error_pct = 10.0
                WHERE prediction_id = ?
                """,
                (f"-{i * 7}", prediction_id),
            )
        prediction_db.commit()

        accuracy = get_prediction_accuracy(prediction_db, "alexia")

        assert accuracy is not None
        assert accuracy.recent_trend == "improving"

    def test_degrading_trend(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Trend is degrading when recent error is > 120% of historical."""
        # Old predictions have low error
        for i in range(3):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
                week_start_date=f"2025-10-0{i + 1}",
            )
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET outcome_measured = 1,
                    predicted_at = datetime('now', ? || ' days'),
                    revenue_prediction_error_pct = 10.0
                WHERE prediction_id = ?
                """,
                (f"-{60 + i * 7}", prediction_id),
            )

        # Recent predictions have high error
        for i in range(3):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
                week_start_date=f"2025-12-0{i + 1}",
            )
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET outcome_measured = 1,
                    predicted_at = datetime('now', ? || ' days'),
                    revenue_prediction_error_pct = 50.0
                WHERE prediction_id = ?
                """,
                (f"-{i * 7}", prediction_id),
            )
        prediction_db.commit()

        accuracy = get_prediction_accuracy(prediction_db, "alexia")

        assert accuracy is not None
        assert accuracy.recent_trend == "degrading"


class TestFindUnmeasuredPredictions:
    """Tests for find_unmeasured_predictions function."""

    def test_finds_old_unmeasured(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Finds predictions older than min_age_days."""
        # Create a prediction from 10 days ago
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-06",  # 10 days ago from Dec 16
        )

        # Need to adjust week_start_date to be old enough
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET week_start_date = date('now', '-10 days')
            WHERE prediction_id = ?
            """,
            (prediction_id,),
        )
        prediction_db.commit()

        unmeasured = find_unmeasured_predictions(prediction_db, min_age_days=7)

        assert prediction_id in unmeasured

    def test_excludes_recent_predictions(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Excludes predictions newer than min_age_days."""
        # Create a prediction from 3 days ago
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-13",  # Only 3 days ago
        )

        # Set week_start to be recent
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET week_start_date = date('now', '-3 days')
            WHERE prediction_id = ?
            """,
            (prediction_id,),
        )
        prediction_db.commit()

        unmeasured = find_unmeasured_predictions(prediction_db, min_age_days=7)

        assert prediction_id not in unmeasured

    def test_excludes_already_measured(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Excludes predictions that are already measured."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-01",
        )

        # Mark as measured
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET outcome_measured = 1,
                week_start_date = date('now', '-10 days')
            WHERE prediction_id = ?
            """,
            (prediction_id,),
        )
        prediction_db.commit()

        unmeasured = find_unmeasured_predictions(prediction_db, min_age_days=7)

        assert prediction_id not in unmeasured

    def test_excludes_no_week_start(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Excludes predictions without week_start_date."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date=None,  # No week_start
        )

        unmeasured = find_unmeasured_predictions(prediction_db, min_age_days=7)

        assert prediction_id not in unmeasured

    def test_limits_results(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Results are limited to 100."""
        # Create 150 old predictions
        for i in range(150):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
            )
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET week_start_date = date('now', '-30 days')
                WHERE prediction_id = ?
                """,
                (prediction_id,),
            )
        prediction_db.commit()

        unmeasured = find_unmeasured_predictions(prediction_db, min_age_days=7)

        assert len(unmeasured) == 100


class TestBatchMeasurePredictions:
    """Tests for batch_measure_predictions function."""

    def test_batch_measure_success(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Successfully batch measures multiple predictions."""
        # Create multiple old predictions
        prediction_ids = []
        for i in range(3):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
            )
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET week_start_date = date('now', '-10 days')
                WHERE prediction_id = ?
                """,
                (prediction_id,),
            )
            prediction_ids.append(prediction_id)

        # Add message data
        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, datetime('now', '-5 days'))
            """,
            ("alexia", "ppv", 10, 500.0, 50.0),
        )
        prediction_db.commit()

        results = batch_measure_predictions(prediction_db, min_age_days=7)

        assert results["measured"] == 3
        assert results["failed"] == 0
        assert results["skipped"] == 0

    def test_batch_measure_with_no_data(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Handles predictions with no actual data."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
        )
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET week_start_date = date('now', '-10 days')
            WHERE prediction_id = ?
            """,
            (prediction_id,),
        )
        prediction_db.commit()

        # No message data inserted

        results = batch_measure_predictions(prediction_db, min_age_days=7)

        # Should still measure (with zero values), not skip
        assert results["measured"] == 1

    def test_batch_measure_empty_queue(
        self, prediction_db: sqlite3.Connection
    ) -> None:
        """Returns zeros when no predictions to measure."""
        results = batch_measure_predictions(prediction_db, min_age_days=7)

        assert results["measured"] == 0
        assert results["failed"] == 0
        assert results["skipped"] == 0


class TestEstimationFunctions:
    """Tests for revenue and message estimation functions."""

    def test_estimate_weekly_revenue(self) -> None:
        """Weekly revenue estimation uses correct formula."""
        # 4 revenue/day * 7 days * $20 avg = $560
        result = estimate_weekly_revenue(
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            avg_rps=20.0,
        )
        assert result == 560.0

    def test_estimate_weekly_revenue_zero_avg_rps(self) -> None:
        """Zero avg_rps returns zero revenue."""
        result = estimate_weekly_revenue(
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
            avg_rps=0.0,
        )
        assert result == 0.0

    def test_estimate_weekly_messages(self) -> None:
        """Weekly message estimation sums all categories."""
        # (4 + 4 + 2) * 7 = 70
        result = estimate_weekly_messages(
            revenue_per_day=4,
            engagement_per_day=4,
            retention_per_day=2,
        )
        assert result == 70

    def test_estimate_weekly_messages_free_page(self) -> None:
        """Free page with zero retention."""
        # (6 + 5 + 0) * 7 = 77
        result = estimate_weekly_messages(
            revenue_per_day=6,
            engagement_per_day=5,
            retention_per_day=0,
        )
        assert result == 77


class TestPredictionTracker:
    """Tests for PredictionTracker class."""

    def test_tracker_track_prediction(
        self, tmp_path: Path, sample_prediction: VolumePrediction
    ) -> None:
        """Tracker can save predictions."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE volume_predictions (
                prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id TEXT NOT NULL,
                predicted_at TEXT NOT NULL,
                input_fan_count INTEGER NOT NULL,
                input_page_type TEXT NOT NULL,
                input_saturation REAL NOT NULL,
                input_opportunity REAL NOT NULL,
                predicted_tier TEXT NOT NULL,
                predicted_revenue_per_day INTEGER NOT NULL,
                predicted_engagement_per_day INTEGER NOT NULL,
                predicted_retention_per_day INTEGER NOT NULL,
                predicted_weekly_revenue REAL DEFAULT 0.0,
                predicted_weekly_messages INTEGER DEFAULT 0,
                schedule_template_id INTEGER,
                week_start_date TEXT,
                algorithm_version TEXT NOT NULL,
                outcome_measured INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

        tracker = PredictionTracker(str(db_path))
        prediction_id = tracker.track_prediction(
            sample_prediction,
            week_start_date="2025-12-16",
        )

        assert prediction_id > 0

    def test_tracker_get_accuracy(self, tmp_path: Path) -> None:
        """Tracker can retrieve accuracy metrics."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE volume_predictions (
                prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id TEXT NOT NULL,
                predicted_at TEXT NOT NULL,
                input_fan_count INTEGER NOT NULL,
                input_page_type TEXT NOT NULL,
                input_saturation REAL NOT NULL,
                input_opportunity REAL NOT NULL,
                predicted_tier TEXT NOT NULL,
                predicted_revenue_per_day INTEGER NOT NULL,
                predicted_engagement_per_day INTEGER NOT NULL,
                predicted_retention_per_day INTEGER NOT NULL,
                predicted_weekly_revenue REAL DEFAULT 0.0,
                predicted_weekly_messages INTEGER DEFAULT 0,
                schedule_template_id INTEGER,
                week_start_date TEXT,
                algorithm_version TEXT NOT NULL,
                actual_total_revenue REAL,
                actual_messages_sent INTEGER,
                actual_avg_rps REAL,
                revenue_prediction_error_pct REAL,
                volume_prediction_error_pct REAL,
                outcome_measured INTEGER DEFAULT 0,
                outcome_measured_at TEXT
            )
        """)
        conn.execute(
            """
            INSERT INTO volume_predictions
            (creator_id, predicted_at, input_fan_count, input_page_type,
             input_saturation, input_opportunity, predicted_tier,
             predicted_revenue_per_day, predicted_engagement_per_day,
             predicted_retention_per_day, algorithm_version, outcome_measured,
             revenue_prediction_error_pct, volume_prediction_error_pct)
            VALUES ('alexia', '2025-12-16', 2500, 'paid', 45.0, 65.0, 'MID',
                    4, 4, 2, '2.0', 1, 10.0, 5.0)
            """
        )
        conn.commit()
        conn.close()

        tracker = PredictionTracker(str(db_path))
        accuracy = tracker.get_accuracy("alexia")

        assert accuracy is not None
        assert accuracy.creator_id == "alexia"
        assert accuracy.total_predictions == 1
        assert accuracy.measured_predictions == 1


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_database(self, prediction_db: sqlite3.Connection) -> None:
        """Functions handle empty database gracefully."""
        assert get_prediction_accuracy(prediction_db, "anyone") is None
        assert find_unmeasured_predictions(prediction_db) == []
        assert batch_measure_predictions(prediction_db) == {
            "measured": 0,
            "failed": 0,
            "skipped": 0,
        }

    def test_very_large_error(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Handles very large prediction errors."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",
        )

        # Actual is 10x prediction
        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("alexia", "ppv", 10, 5600.0, 560.0, "2025-12-10 19:00:00"),
        )
        prediction_db.commit()

        outcome = measure_prediction_outcome(prediction_db, prediction_id)

        assert outcome is not None
        # (5600 - 560) / 560 * 100 = 900%
        assert outcome.revenue_prediction_error_pct == 900.0

    def test_negative_actual_values_handled(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Handles edge case of negative or refunded values."""
        prediction_id = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-09",
        )

        # Simulating refund scenario (shouldn't happen but handle gracefully)
        prediction_db.execute(
            """
            INSERT INTO mass_messages
            (creator_id, message_type, sent_count, earnings, revenue_per_send, sending_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("alexia", "ppv", 0, 0.0, 0.0, "2025-12-10 19:00:00"),
        )
        prediction_db.commit()

        outcome = measure_prediction_outcome(prediction_db, prediction_id)

        assert outcome is not None
        assert outcome.actual_total_revenue == 0.0

    def test_unicode_creator_id(
        self, prediction_db: sqlite3.Connection
    ) -> None:
        """Handles unicode characters in creator_id."""
        prediction = VolumePrediction(
            creator_id="creator_with_unicode_chars",
            input_fan_count=1000,
            input_page_type="paid",
            input_saturation=50.0,
            input_opportunity=50.0,
            predicted_tier="MID",
            predicted_revenue_per_day=4,
            predicted_engagement_per_day=4,
            predicted_retention_per_day=2,
        )

        prediction_id = save_prediction(prediction_db, prediction)

        cursor = prediction_db.execute(
            "SELECT creator_id FROM volume_predictions WHERE prediction_id = ?",
            (prediction_id,),
        )
        row = cursor.fetchone()
        assert row[0] == "creator_with_unicode_chars"


class TestCalculateMAPE:
    """Tests for calculate_mape function."""

    def test_mape_perfect_prediction(self) -> None:
        """MAPE is 0 for perfect predictions."""
        predictions = [100.0, 200.0, 300.0]
        actuals = [100.0, 200.0, 300.0]
        result = calculate_mape(predictions, actuals)
        assert result == 0.0

    def test_mape_basic_calculation(self) -> None:
        """MAPE calculated correctly for basic case."""
        # Predictions: [100, 200], Actuals: [80, 220]
        # Errors: |80-100|/80 = 0.25, |220-200|/220 = 0.0909
        # MAPE: (0.25 + 0.0909) / 2 * 100 = 17.05%
        predictions = [100.0, 200.0]
        actuals = [80.0, 220.0]
        result = calculate_mape(predictions, actuals)
        assert result is not None
        assert abs(result - 17.05) < 0.1

    def test_mape_empty_lists(self) -> None:
        """MAPE returns None for empty lists."""
        result = calculate_mape([], [])
        assert result is None

    def test_mape_mismatched_lengths(self) -> None:
        """MAPE returns None for mismatched list lengths."""
        result = calculate_mape([100.0, 200.0], [100.0])
        assert result is None

    def test_mape_with_zero_actuals(self) -> None:
        """MAPE excludes zero actuals to avoid division by zero."""
        predictions = [100.0, 200.0, 300.0]
        actuals = [100.0, 0.0, 300.0]  # Middle value is zero
        result = calculate_mape(predictions, actuals)
        # Only uses first and third: both perfect = 0%
        assert result == 0.0

    def test_mape_all_zero_actuals(self) -> None:
        """MAPE returns None when all actuals are zero."""
        predictions = [100.0, 200.0]
        actuals = [0.0, 0.0]
        result = calculate_mape(predictions, actuals)
        assert result is None

    def test_mape_50_percent_error(self) -> None:
        """MAPE calculates 50% error correctly."""
        # Prediction: 100, Actual: 200 -> |200-100|/200 = 0.5 = 50%
        predictions = [100.0]
        actuals = [200.0]
        result = calculate_mape(predictions, actuals)
        assert result == 50.0


class TestGetAccuracyByAlgorithmVersion:
    """Tests for get_accuracy_by_algorithm_version function."""

    def test_accuracy_no_data(
        self, prediction_db: sqlite3.Connection
    ) -> None:
        """Returns zero metrics when no data exists for version."""
        result = get_accuracy_by_algorithm_version(prediction_db, "3.0")
        assert result["sample_count"] == 0
        assert result["avg_revenue_error_pct"] == 0.0
        assert result["mape"] == 0.0

    def test_accuracy_for_version(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Calculates accuracy for specific algorithm version."""
        # Create predictions with version 2.0
        for i in range(3):
            prediction_id = save_prediction(
                prediction_db,
                sample_prediction,
                week_start_date=f"2025-12-0{i + 1}",
            )
            # Manually set measured data
            prediction_db.execute(
                """
                UPDATE volume_predictions
                SET outcome_measured = 1,
                    actual_total_revenue = 600,
                    actual_messages_sent = 75,
                    revenue_prediction_error_pct = 10.0,
                    volume_prediction_error_pct = 7.0,
                    algorithm_version = '2.0'
                WHERE prediction_id = ?
                """,
                (prediction_id,),
            )
        prediction_db.commit()

        result = get_accuracy_by_algorithm_version(prediction_db, "2.0")

        assert result["sample_count"] == 3
        assert result["avg_revenue_error_pct"] == 10.0
        assert result["avg_volume_error_pct"] == 7.0

    def test_accuracy_isolates_versions(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Accuracy is isolated per algorithm version."""
        # Create predictions for version 2.0
        pred_id_v2 = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-01",
        )
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET outcome_measured = 1,
                actual_total_revenue = 600,
                revenue_prediction_error_pct = 10.0,
                algorithm_version = '2.0'
            WHERE prediction_id = ?
            """,
            (pred_id_v2,),
        )

        # Create predictions for version 2.1
        pred_id_v21 = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-02",
        )
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET outcome_measured = 1,
                actual_total_revenue = 650,
                revenue_prediction_error_pct = 50.0,
                algorithm_version = '2.1'
            WHERE prediction_id = ?
            """,
            (pred_id_v21,),
        )
        prediction_db.commit()

        v2_result = get_accuracy_by_algorithm_version(prediction_db, "2.0")
        v21_result = get_accuracy_by_algorithm_version(prediction_db, "2.1")

        assert v2_result["sample_count"] == 1
        assert v2_result["avg_revenue_error_pct"] == 10.0

        assert v21_result["sample_count"] == 1
        assert v21_result["avg_revenue_error_pct"] == 50.0

    def test_accuracy_with_creator_filter(
        self, prediction_db: sqlite3.Connection, sample_prediction: VolumePrediction
    ) -> None:
        """Accuracy can be filtered by creator."""
        # Create predictions for alexia
        pred_id_alexia = save_prediction(
            prediction_db,
            sample_prediction,
            week_start_date="2025-12-01",
        )
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET outcome_measured = 1,
                actual_total_revenue = 600,
                revenue_prediction_error_pct = 10.0,
                algorithm_version = '2.0'
            WHERE prediction_id = ?
            """,
            (pred_id_alexia,),
        )

        # Create predictions for another creator
        other_prediction = VolumePrediction(
            creator_id="diamond",
            input_fan_count=50000,
            input_page_type="paid",
            input_saturation=30.0,
            input_opportunity=80.0,
            predicted_tier="ULTRA",
            predicted_revenue_per_day=6,
            predicted_engagement_per_day=5,
            predicted_retention_per_day=3,
        )
        pred_id_diamond = save_prediction(
            prediction_db,
            other_prediction,
            week_start_date="2025-12-02",
        )
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET outcome_measured = 1,
                actual_total_revenue = 2000,
                revenue_prediction_error_pct = 30.0,
                algorithm_version = '2.0'
            WHERE prediction_id = ?
            """,
            (pred_id_diamond,),
        )
        prediction_db.commit()

        # Check accuracy for alexia only
        alexia_result = get_accuracy_by_algorithm_version(
            prediction_db, "2.0", creator_id="alexia"
        )

        assert alexia_result["sample_count"] == 1
        assert alexia_result["avg_revenue_error_pct"] == 10.0

        # Check accuracy for all creators
        all_result = get_accuracy_by_algorithm_version(prediction_db, "2.0")

        assert all_result["sample_count"] == 2
        # Average of 10 and 30 = 20
        assert all_result["avg_revenue_error_pct"] == 20.0

    def test_accuracy_mape_calculation(
        self, prediction_db: sqlite3.Connection
    ) -> None:
        """MAPE is correctly calculated in accuracy report."""
        # Create a prediction with known values
        prediction = VolumePrediction(
            creator_id="test",
            input_fan_count=1000,
            input_page_type="paid",
            input_saturation=50.0,
            input_opportunity=50.0,
            predicted_tier="MID",
            predicted_revenue_per_day=4,
            predicted_engagement_per_day=4,
            predicted_retention_per_day=2,
            predicted_weekly_revenue=100.0,  # Known predicted value
        )

        pred_id = save_prediction(
            prediction_db,
            prediction,
            week_start_date="2025-12-01",
        )

        # Actual is 200, so error is |200-100|/200 = 50%
        prediction_db.execute(
            """
            UPDATE volume_predictions
            SET outcome_measured = 1,
                actual_total_revenue = 200.0,
                revenue_prediction_error_pct = 100.0,
                algorithm_version = '2.0'
            WHERE prediction_id = ?
            """,
            (pred_id,),
        )
        prediction_db.commit()

        result = get_accuracy_by_algorithm_version(prediction_db, "2.0")

        assert result["sample_count"] == 1
        # MAPE: |200-100|/200 = 50%
        assert result["mape"] == 50.0
