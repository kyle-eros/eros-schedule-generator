"""
Prediction vs outcome tracking for algorithm accuracy measurement.

Stores predictions when volume is calculated, links to schedule executions,
and measures actual outcomes to calculate prediction accuracy.

This module enables continuous improvement of the volume calculation
algorithm by tracking:
1. Predictions made at schedule time
2. Actual outcomes after execution
3. Prediction error metrics
4. A/B testing of algorithm variations
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from python.exceptions import DatabaseError
from python.logging_config import get_logger

logger = get_logger(__name__)


# Algorithm version for tracking
CURRENT_ALGORITHM_VERSION = "2.0"


@dataclass
class VolumePrediction:
    """A volume prediction to be tracked.

    Attributes:
        creator_id: Creator this prediction is for.
        input_fan_count: Fan count at prediction time.
        input_page_type: Page type at prediction time.
        input_saturation: Saturation score used.
        input_opportunity: Opportunity score used.
        predicted_tier: Predicted volume tier.
        predicted_revenue_per_day: Predicted revenue sends per day.
        predicted_engagement_per_day: Predicted engagement sends per day.
        predicted_retention_per_day: Predicted retention sends per day.
        predicted_weekly_revenue: Estimated weekly revenue.
        predicted_weekly_messages: Estimated weekly message count.
        algorithm_version: Version of algorithm making prediction.
        prediction_id: Database ID after saving.
        predicted_at: Timestamp of prediction.
    """

    creator_id: str
    input_fan_count: int
    input_page_type: str
    input_saturation: float
    input_opportunity: float
    predicted_tier: str
    predicted_revenue_per_day: int
    predicted_engagement_per_day: int
    predicted_retention_per_day: int
    predicted_weekly_revenue: float = 0.0
    predicted_weekly_messages: int = 0
    algorithm_version: str = CURRENT_ALGORITHM_VERSION
    prediction_id: Optional[int] = None
    predicted_at: datetime = field(default_factory=datetime.now)


@dataclass
class PredictionOutcome:
    """Actual outcome after schedule execution.

    Attributes:
        prediction_id: ID of the prediction being measured.
        actual_total_revenue: Actual revenue generated.
        actual_messages_sent: Actual messages sent.
        actual_avg_rps: Actual average revenue per send.
        revenue_prediction_error_pct: Percent error in revenue prediction.
        volume_prediction_error_pct: Percent error in message count prediction.
        measured_at: When outcome was measured.
    """

    prediction_id: int
    actual_total_revenue: float
    actual_messages_sent: int
    actual_avg_rps: float
    revenue_prediction_error_pct: float
    volume_prediction_error_pct: float
    measured_at: datetime = field(default_factory=datetime.now)


@dataclass
class PredictionAccuracy:
    """Aggregate accuracy metrics for predictions.

    Attributes:
        creator_id: Creator these metrics are for.
        total_predictions: Total predictions made.
        measured_predictions: Predictions with outcomes measured.
        avg_revenue_error_pct: Average absolute revenue prediction error.
        avg_volume_error_pct: Average absolute volume prediction error.
        directional_accuracy_pct: Percent of predictions with correct direction.
        recent_trend: Trend in recent prediction accuracy.
    """

    creator_id: str
    total_predictions: int
    measured_predictions: int
    avg_revenue_error_pct: float
    avg_volume_error_pct: float
    directional_accuracy_pct: float
    recent_trend: str = "stable"


def save_prediction(
    conn: sqlite3.Connection,
    prediction: VolumePrediction,
    schedule_template_id: Optional[int] = None,
    week_start_date: Optional[str] = None,
) -> int:
    """Save a volume prediction to the database.

    Args:
        conn: Database connection.
        prediction: VolumePrediction to save.
        schedule_template_id: Optional linked schedule ID.
        week_start_date: Optional week start date.

    Returns:
        ID of the saved prediction.

    Raises:
        DatabaseError: If save fails.
    """
    query = """
        INSERT INTO volume_predictions (
            creator_id,
            predicted_at,
            input_fan_count,
            input_page_type,
            input_saturation,
            input_opportunity,
            predicted_tier,
            predicted_revenue_per_day,
            predicted_engagement_per_day,
            predicted_retention_per_day,
            predicted_weekly_revenue,
            predicted_weekly_messages,
            schedule_template_id,
            week_start_date,
            algorithm_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        prediction.creator_id,
        prediction.predicted_at.isoformat(),
        prediction.input_fan_count,
        prediction.input_page_type,
        prediction.input_saturation,
        prediction.input_opportunity,
        prediction.predicted_tier,
        prediction.predicted_revenue_per_day,
        prediction.predicted_engagement_per_day,
        prediction.predicted_retention_per_day,
        prediction.predicted_weekly_revenue,
        prediction.predicted_weekly_messages,
        schedule_template_id,
        week_start_date,
        prediction.algorithm_version,
    )

    try:
        cursor = conn.execute(query, params)
        conn.commit()
        prediction_id = cursor.lastrowid

        if prediction_id is None:
            raise DatabaseError(
                "Failed to get prediction ID after insert",
                operation="save_prediction",
                details={"creator_id": prediction.creator_id},
            )

        logger.info(
            "Saved volume prediction",
            extra={
                "prediction_id": prediction_id,
                "creator_id": prediction.creator_id,
                "predicted_tier": prediction.predicted_tier,
                "algorithm_version": prediction.algorithm_version,
            },
        )

        return prediction_id

    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to save prediction: {e}",
            operation="save_prediction",
            details={"creator_id": prediction.creator_id},
        )


def measure_prediction_outcome(
    conn: sqlite3.Connection,
    prediction_id: int,
    lookback_days: int = 7,
) -> Optional[PredictionOutcome]:
    """Measure actual outcome for a prediction.

    Calculates actual performance metrics from mass_messages
    and compares to prediction.

    Args:
        conn: Database connection.
        prediction_id: ID of prediction to measure.
        lookback_days: Days after week_start to analyze.

    Returns:
        PredictionOutcome if measurement successful, None otherwise.

    Raises:
        DatabaseError: If query fails.
    """
    # First, fetch the prediction
    fetch_query = """
        SELECT
            creator_id,
            week_start_date,
            predicted_weekly_revenue,
            predicted_weekly_messages
        FROM volume_predictions
        WHERE prediction_id = ?
          AND outcome_measured = 0
    """

    try:
        cursor = conn.execute(fetch_query, (prediction_id,))
        row = cursor.fetchone()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to fetch prediction: {e}",
            operation="measure_prediction_outcome",
            details={"prediction_id": prediction_id},
        )

    if not row:
        logger.warning(f"Prediction {prediction_id} not found or already measured")
        return None

    creator_id, week_start, predicted_revenue, predicted_messages = row

    if not week_start:
        logger.warning(f"Prediction {prediction_id} has no week_start_date")
        return None

    # Calculate actual performance
    actual_query = """
        SELECT
            COALESCE(SUM(earnings), 0) as total_revenue,
            COUNT(*) as message_count,
            COALESCE(AVG(revenue_per_send), 0) as avg_rps
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND sent_count > 0
          AND sending_time >= ?
          AND sending_time < datetime(?, '+7 days')
    """

    try:
        cursor = conn.execute(actual_query, (creator_id, week_start, week_start))
        actual_row = cursor.fetchone()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to fetch actual performance: {e}",
            operation="measure_prediction_outcome",
            details={"creator_id": creator_id, "week_start": week_start},
        )

    if not actual_row:
        logger.warning(f"No actual data found for prediction {prediction_id}")
        return None

    actual_revenue, actual_messages, actual_rps = actual_row
    actual_revenue = actual_revenue or 0.0
    actual_messages = actual_messages or 0
    actual_rps = actual_rps or 0.0

    # Calculate prediction errors
    revenue_error = 0.0
    if predicted_revenue and predicted_revenue > 0:
        revenue_error = ((actual_revenue - predicted_revenue) / predicted_revenue) * 100

    volume_error = 0.0
    if predicted_messages and predicted_messages > 0:
        volume_error = ((actual_messages - predicted_messages) / predicted_messages) * 100

    # Update prediction record
    update_query = """
        UPDATE volume_predictions
        SET actual_total_revenue = ?,
            actual_messages_sent = ?,
            actual_avg_rps = ?,
            revenue_prediction_error_pct = ?,
            volume_prediction_error_pct = ?,
            outcome_measured = 1,
            outcome_measured_at = datetime('now')
        WHERE prediction_id = ?
    """

    try:
        conn.execute(
            update_query,
            (
                actual_revenue,
                actual_messages,
                actual_rps,
                revenue_error,
                volume_error,
                prediction_id,
            ),
        )
        conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to update prediction outcome: {e}",
            operation="measure_prediction_outcome",
            details={"prediction_id": prediction_id},
        )

    logger.info(
        "Measured prediction outcome",
        extra={
            "prediction_id": prediction_id,
            "creator_id": creator_id,
            "predicted_revenue": predicted_revenue,
            "actual_revenue": actual_revenue,
            "revenue_error_pct": revenue_error,
        },
    )

    return PredictionOutcome(
        prediction_id=prediction_id,
        actual_total_revenue=actual_revenue,
        actual_messages_sent=actual_messages,
        actual_avg_rps=actual_rps,
        revenue_prediction_error_pct=round(revenue_error, 2),
        volume_prediction_error_pct=round(volume_error, 2),
    )


def get_prediction_accuracy(
    conn: sqlite3.Connection,
    creator_id: str,
) -> Optional[PredictionAccuracy]:
    """Get aggregate prediction accuracy metrics for a creator.

    Args:
        conn: Database connection.
        creator_id: Creator to get accuracy for.

    Returns:
        PredictionAccuracy if data exists, None otherwise.

    Raises:
        DatabaseError: If query fails.
    """
    query = """
        SELECT
            COUNT(*) as total_predictions,
            SUM(CASE WHEN outcome_measured = 1 THEN 1 ELSE 0 END) as measured,
            AVG(CASE WHEN outcome_measured = 1
                THEN ABS(revenue_prediction_error_pct) END) as avg_rev_err,
            AVG(CASE WHEN outcome_measured = 1
                THEN ABS(volume_prediction_error_pct) END) as avg_vol_err,
            AVG(CASE
                WHEN outcome_measured = 1
                    AND predicted_weekly_revenue > 0
                    AND actual_total_revenue > 0
                    AND (
                        (actual_total_revenue >= predicted_weekly_revenue
                         AND predicted_weekly_revenue >= 0)
                        OR
                        (actual_total_revenue < predicted_weekly_revenue
                         AND predicted_weekly_revenue < 0)
                    )
                THEN 1.0 ELSE 0.0
            END) * 100 as directional_accuracy
        FROM volume_predictions
        WHERE creator_id = ?
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        row = cursor.fetchone()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to get prediction accuracy: {e}",
            operation="get_prediction_accuracy",
            details={"creator_id": creator_id},
        )

    if not row or row[0] == 0:
        return None

    total, measured, avg_rev_err, avg_vol_err, dir_accuracy = row

    # Check recent trend
    recent_query = """
        SELECT AVG(ABS(revenue_prediction_error_pct))
        FROM volume_predictions
        WHERE creator_id = ?
          AND outcome_measured = 1
          AND predicted_at >= datetime('now', '-30 days')
    """

    try:
        cursor = conn.execute(recent_query, (creator_id,))
        recent_row = cursor.fetchone()
        recent_error = recent_row[0] if recent_row else None
    except sqlite3.Error:
        recent_error = None

    # Determine trend
    trend = "stable"
    if recent_error is not None and avg_rev_err is not None:
        if recent_error < avg_rev_err * 0.8:
            trend = "improving"
        elif recent_error > avg_rev_err * 1.2:
            trend = "degrading"

    return PredictionAccuracy(
        creator_id=creator_id,
        total_predictions=total or 0,
        measured_predictions=measured or 0,
        avg_revenue_error_pct=round(avg_rev_err or 0, 2),
        avg_volume_error_pct=round(avg_vol_err or 0, 2),
        directional_accuracy_pct=round(dir_accuracy or 0, 2),
        recent_trend=trend,
    )


def find_unmeasured_predictions(
    conn: sqlite3.Connection,
    min_age_days: int = 7,
) -> List[int]:
    """Find predictions that are old enough to measure but haven't been.

    Args:
        conn: Database connection.
        min_age_days: Minimum days since week_start before measuring.

    Returns:
        List of prediction IDs ready to measure.
    """
    query = """
        SELECT prediction_id
        FROM volume_predictions
        WHERE outcome_measured = 0
          AND week_start_date IS NOT NULL
          AND datetime(week_start_date, ? || ' days') < datetime('now')
        ORDER BY predicted_at
        LIMIT 100
    """

    try:
        cursor = conn.execute(query, (f"+{min_age_days}",))
        rows = cursor.fetchall()
        return [row[0] for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Failed to find unmeasured predictions: {e}")
        return []


def batch_measure_predictions(
    conn: sqlite3.Connection,
    min_age_days: int = 7,
) -> Dict[str, int]:
    """Batch measure all predictions that are ready.

    Args:
        conn: Database connection.
        min_age_days: Minimum days since week_start before measuring.

    Returns:
        Dict with counts of measured, failed, skipped.
    """
    prediction_ids = find_unmeasured_predictions(conn, min_age_days)

    results: Dict[str, int] = {"measured": 0, "failed": 0, "skipped": 0}

    for pred_id in prediction_ids:
        try:
            outcome = measure_prediction_outcome(conn, pred_id)
            if outcome:
                results["measured"] += 1
            else:
                results["skipped"] += 1
        except DatabaseError as e:
            logger.warning(f"Failed to measure prediction {pred_id}: {e}")
            results["failed"] += 1

    logger.info("Batch prediction measurement complete", extra=results)

    return results


def calculate_mape(
    predictions: List[float],
    actuals: List[float],
) -> Optional[float]:
    """Calculate Mean Absolute Percentage Error (MAPE).

    MAPE is a standard metric for prediction accuracy measurement.
    Formula: (1/n) * sum(|actual - predicted| / |actual|) * 100

    Args:
        predictions: List of predicted values.
        actuals: List of actual values (must be same length as predictions).

    Returns:
        MAPE as a percentage, or None if calculation not possible.

    Note:
        Values where actual is zero are excluded from calculation
        to avoid division by zero.
    """
    if len(predictions) != len(actuals) or len(predictions) == 0:
        return None

    valid_errors: List[float] = []
    for pred, actual in zip(predictions, actuals):
        if actual != 0:
            error = abs(actual - pred) / abs(actual)
            valid_errors.append(error)

    if not valid_errors:
        return None

    return (sum(valid_errors) / len(valid_errors)) * 100


def get_accuracy_by_algorithm_version(
    conn: sqlite3.Connection,
    algorithm_version: str,
    creator_id: Optional[str] = None,
) -> Dict[str, float]:
    """Get accuracy metrics for a specific algorithm version.

    Useful for A/B testing different algorithm versions.

    Args:
        conn: Database connection.
        algorithm_version: Version to filter by (e.g., "2.0", "2.1").
        creator_id: Optional creator to filter by.

    Returns:
        Dict with accuracy metrics including mape, avg_error, sample_count.

    Raises:
        DatabaseError: If query fails.
    """
    base_query = """
        SELECT
            COUNT(*) as sample_count,
            AVG(ABS(revenue_prediction_error_pct)) as avg_revenue_error,
            AVG(ABS(volume_prediction_error_pct)) as avg_volume_error,
            predicted_weekly_revenue,
            actual_total_revenue
        FROM volume_predictions
        WHERE outcome_measured = 1
          AND algorithm_version = ?
    """

    params: List[str] = [algorithm_version]

    if creator_id:
        base_query += " AND creator_id = ?"
        params.append(creator_id)

    try:
        cursor = conn.execute(base_query, tuple(params))
        row = cursor.fetchone()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to get accuracy by version: {e}",
            operation="get_accuracy_by_algorithm_version",
            details={"algorithm_version": algorithm_version},
        )

    if not row or row[0] == 0:
        return {
            "sample_count": 0,
            "avg_revenue_error_pct": 0.0,
            "avg_volume_error_pct": 0.0,
            "mape": 0.0,
        }

    sample_count, avg_rev_err, avg_vol_err, _, _ = row

    # Fetch all predictions/actuals for MAPE calculation
    mape_query = """
        SELECT predicted_weekly_revenue, actual_total_revenue
        FROM volume_predictions
        WHERE outcome_measured = 1
          AND algorithm_version = ?
          AND predicted_weekly_revenue IS NOT NULL
          AND actual_total_revenue IS NOT NULL
    """

    mape_params: List[str] = [algorithm_version]
    if creator_id:
        mape_query += " AND creator_id = ?"
        mape_params.append(creator_id)

    try:
        cursor = conn.execute(mape_query, tuple(mape_params))
        rows = cursor.fetchall()
    except sqlite3.Error:
        rows = []

    predictions = [r[0] for r in rows]
    actuals = [r[1] for r in rows]
    mape = calculate_mape(predictions, actuals)

    return {
        "sample_count": sample_count or 0,
        "avg_revenue_error_pct": round(avg_rev_err or 0, 2),
        "avg_volume_error_pct": round(avg_vol_err or 0, 2),
        "mape": round(mape or 0, 2),
    }


def estimate_weekly_revenue(
    revenue_per_day: int,
    engagement_per_day: int,
    retention_per_day: int,
    avg_rps: float,
) -> float:
    """Estimate weekly revenue from volume configuration.

    Simple estimation: (revenue_sends * 7) * avg_rps.

    Args:
        revenue_per_day: Revenue sends per day.
        engagement_per_day: Engagement sends per day (non-revenue).
        retention_per_day: Retention sends per day (non-revenue).
        avg_rps: Historical average revenue per send.

    Returns:
        Estimated weekly revenue.
    """
    # Only revenue sends generate direct revenue
    weekly_revenue_sends = revenue_per_day * 7
    return weekly_revenue_sends * avg_rps


def estimate_weekly_messages(
    revenue_per_day: int,
    engagement_per_day: int,
    retention_per_day: int,
) -> int:
    """Estimate total weekly messages from volume configuration.

    Args:
        revenue_per_day: Revenue sends per day.
        engagement_per_day: Engagement sends per day.
        retention_per_day: Retention sends per day.

    Returns:
        Estimated weekly message count.
    """
    total_per_day = revenue_per_day + engagement_per_day + retention_per_day
    return total_per_day * 7


class PredictionTracker:
    """High-level tracker for prediction accuracy.

    Provides convenient interface for tracking predictions
    and measuring outcomes.

    Example:
        >>> tracker = PredictionTracker("./database/eros_sd_main.db")
        >>> prediction = VolumePrediction(
        ...     creator_id="alexia",
        ...     input_fan_count=2500,
        ...     input_page_type="paid",
        ...     input_saturation=45.0,
        ...     input_opportunity=65.0,
        ...     predicted_tier="MID",
        ...     predicted_revenue_per_day=4,
        ...     predicted_engagement_per_day=4,
        ...     predicted_retention_per_day=2,
        ...     predicted_weekly_revenue=560.0,
        ...     predicted_weekly_messages=70,
        ... )
        >>> pred_id = tracker.track_prediction(
        ...     prediction,
        ...     week_start_date="2025-12-16",
        ... )
        >>> # After 7 days...
        >>> results = tracker.measure_outcomes()
        >>> accuracy = tracker.get_accuracy("alexia")
    """

    def __init__(self, db_path: str) -> None:
        """Initialize PredictionTracker.

        Args:
            db_path: Path to SQLite database.
        """
        self.db_path = db_path

    def track_prediction(
        self,
        prediction: VolumePrediction,
        schedule_template_id: Optional[int] = None,
        week_start_date: Optional[str] = None,
    ) -> int:
        """Save a prediction for tracking.

        Args:
            prediction: VolumePrediction to track.
            schedule_template_id: Optional linked schedule.
            week_start_date: Week start for outcome measurement.

        Returns:
            Prediction ID.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            return save_prediction(
                conn, prediction, schedule_template_id, week_start_date
            )
        finally:
            conn.close()

    def measure_outcomes(self, min_age_days: int = 7) -> Dict[str, int]:
        """Measure all ready predictions.

        Args:
            min_age_days: Minimum days before measuring.

        Returns:
            Results dict with counts.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            return batch_measure_predictions(conn, min_age_days)
        finally:
            conn.close()

    def get_accuracy(self, creator_id: str) -> Optional[PredictionAccuracy]:
        """Get prediction accuracy for a creator.

        Args:
            creator_id: Creator to get accuracy for.

        Returns:
            PredictionAccuracy if data exists.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            return get_prediction_accuracy(conn, creator_id)
        finally:
            conn.close()

    def get_accuracy_report(self) -> List[PredictionAccuracy]:
        """Get accuracy report for all creators with predictions.

        Returns:
            List of PredictionAccuracy for all creators, sorted by error.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Get all creators with predictions
            cursor = conn.execute(
                "SELECT DISTINCT creator_id FROM volume_predictions"
            )
            creator_ids = [row[0] for row in cursor.fetchall()]

            report: List[PredictionAccuracy] = []
            for creator_id in creator_ids:
                accuracy = get_prediction_accuracy(conn, creator_id)
                if accuracy:
                    report.append(accuracy)

            # Sort by average error (best first)
            report.sort(key=lambda a: a.avg_revenue_error_pct)
            return report

        finally:
            conn.close()


__all__ = [
    # Dataclasses
    "VolumePrediction",
    "PredictionOutcome",
    "PredictionAccuracy",
    # High-level tracker class
    "PredictionTracker",
    # Core prediction functions
    "save_prediction",
    "measure_prediction_outcome",
    "get_prediction_accuracy",
    "find_unmeasured_predictions",
    "batch_measure_predictions",
    # Accuracy metrics
    "calculate_mape",
    "get_accuracy_by_algorithm_version",
    # Estimation functions
    "estimate_weekly_revenue",
    "estimate_weekly_messages",
    # Constants
    "CURRENT_ALGORITHM_VERSION",
]
