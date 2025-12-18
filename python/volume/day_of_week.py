"""
Day-of-Week volume modulation for EROS Schedule Generator.

Calculates optimal volume multipliers for each day of the week based on
historical performance data. Adjusts daily send volumes to match audience
engagement patterns (e.g., higher volume on weekends when engagement peaks).

Key Features:
    - DOW multiplier calculation from historical mass_messages data
    - Confidence-based dampening for insufficient data
    - SQLite day-of-week conversion (strftime %w: 0=Sunday, Python: 0=Monday)
    - Fallback to configurable defaults when data is insufficient
    - Bounds enforcement to prevent extreme adjustments

Usage:
    from python.volume.day_of_week import (
        DOWMultipliers,
        calculate_dow_multipliers,
        apply_dow_modulation,
    )

    # Calculate multipliers from historical data
    multipliers = calculate_dow_multipliers(creator_id, db_path)

    # Apply to base volume for a specific day
    monday_volume = apply_dow_modulation(base_volume=5, day_index=0, multipliers=multipliers)

SQLite Day-of-Week Convention:
    SQLite strftime('%w', date) returns: 0=Sunday, 1=Monday, ..., 6=Saturday
    Python datetime.weekday() returns: 0=Monday, 1=Tuesday, ..., 6=Sunday

    This module uses Python convention (0=Monday) internally and converts
    when querying SQLite.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional
import sqlite3
import os

from python.exceptions import InsufficientDataError


# =============================================================================
# Constants
# =============================================================================

# Minimum messages required per day for reliable statistics
MIN_MESSAGES_PER_DAY = 5

# Minimum total messages across all days for any analysis
MIN_TOTAL_MESSAGES = 20

# Multiplier bounds to prevent extreme adjustments
MULTIPLIER_MIN = 0.7
MULTIPLIER_MAX = 1.3

# Default multipliers when insufficient data (neutral = 1.0)
DEFAULT_MULTIPLIERS: dict[int, float] = {
    0: 1.0,  # Monday
    1: 1.0,  # Tuesday
    2: 1.0,  # Wednesday
    3: 1.0,  # Thursday
    4: 1.05, # Friday (slight boost)
    5: 1.1,  # Saturday (weekend boost)
    6: 1.1,  # Sunday (weekend boost)
}

# Day names for logging/display
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# SQLite to Python weekday mapping
# SQLite: 0=Sunday, 1=Monday, ..., 6=Saturday
# Python: 0=Monday, 1=Tuesday, ..., 6=Sunday
SQLITE_TO_PYTHON_DOW = {
    0: 6,  # Sunday -> 6
    1: 0,  # Monday -> 0
    2: 1,  # Tuesday -> 1
    3: 2,  # Wednesday -> 2
    4: 3,  # Thursday -> 3
    5: 4,  # Friday -> 4
    6: 5,  # Saturday -> 5
}

PYTHON_TO_SQLITE_DOW = {v: k for k, v in SQLITE_TO_PYTHON_DOW.items()}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DayPerformance:
    """Performance metrics for a single day of the week.

    Attributes:
        day_index: Python weekday index (0=Monday, 6=Sunday).
        day_name: Human-readable day name.
        message_count: Number of messages sent on this day.
        total_revenue: Total revenue generated from this day's messages.
        avg_revenue: Average revenue per message.
        avg_view_rate: Average view rate for this day.
        avg_purchase_rate: Average purchase rate for this day.
    """
    day_index: int
    day_name: str
    message_count: int = 0
    total_revenue: float = 0.0
    avg_revenue: float = 0.0
    avg_view_rate: float = 0.0
    avg_purchase_rate: float = 0.0


@dataclass
class DOWMultipliers:
    """Day-of-week volume multipliers with confidence metadata.

    Attributes:
        multipliers: Dict mapping day index (0-6) to multiplier (0.7-1.3).
        confidence: Overall confidence in the multipliers (0.0-1.0).
        day_confidences: Per-day confidence scores.
        total_messages: Total messages analyzed.
        is_default: True if using default multipliers due to insufficient data.
        creator_id: Creator these multipliers were calculated for.
    """
    multipliers: dict[int, float]
    confidence: float
    day_confidences: dict[int, float]
    total_messages: int
    is_default: bool
    creator_id: str = ""

    def get_multiplier(self, day_index: int) -> float:
        """Get multiplier for a specific day.

        Args:
            day_index: Python weekday index (0=Monday, 6=Sunday).

        Returns:
            Volume multiplier for the day.
        """
        return self.multipliers.get(day_index, 1.0)

    def get_weekly_distribution(self, base_daily_volume: int) -> dict[int, int]:
        """Calculate weekly volume distribution.

        Applies multipliers to base volume for each day, ensuring
        the total weekly volume is preserved (sum = 7 * base).

        Args:
            base_daily_volume: Base volume per day before modulation.

        Returns:
            Dict mapping day index to adjusted volume.
        """
        # Calculate raw adjusted volumes
        raw_volumes = {
            day: base_daily_volume * mult
            for day, mult in self.multipliers.items()
        }

        # Calculate total to normalize
        raw_total = sum(raw_volumes.values())
        target_total = base_daily_volume * 7

        # Normalize to preserve weekly total
        if raw_total > 0:
            scale_factor = target_total / raw_total
            adjusted_volumes = {
                day: _round_volume(vol * scale_factor)
                for day, vol in raw_volumes.items()
            }
        else:
            adjusted_volumes = {day: base_daily_volume for day in range(7)}

        return adjusted_volumes


@dataclass
class DOWAnalysis:
    """Complete day-of-week analysis results.

    Attributes:
        multipliers: Calculated DOW multipliers.
        day_performance: Performance breakdown by day.
        analysis_period_days: Number of days analyzed.
        data_quality_score: Quality score for the underlying data (0-100).
    """
    multipliers: DOWMultipliers
    day_performance: list[DayPerformance]
    analysis_period_days: int
    data_quality_score: float


# =============================================================================
# Helper Functions
# =============================================================================

def _round_volume(value: float) -> int:
    """Round volume using banker's rounding for consistency.

    Args:
        value: Float value to round.

    Returns:
        Rounded integer value.
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def convert_sqlite_dow_to_python(sqlite_dow: int) -> int:
    """Convert SQLite day-of-week to Python weekday.

    Args:
        sqlite_dow: SQLite strftime %w value (0=Sunday, 6=Saturday).

    Returns:
        Python weekday (0=Monday, 6=Sunday).

    Raises:
        ValueError: If sqlite_dow is not 0-6.
    """
    if not 0 <= sqlite_dow <= 6:
        raise ValueError(f"Invalid SQLite DOW: {sqlite_dow}, must be 0-6")
    return SQLITE_TO_PYTHON_DOW[sqlite_dow]


def convert_python_dow_to_sqlite(python_dow: int) -> int:
    """Convert Python weekday to SQLite day-of-week.

    Args:
        python_dow: Python weekday (0=Monday, 6=Sunday).

    Returns:
        SQLite strftime %w value (0=Sunday, 6=Saturday).

    Raises:
        ValueError: If python_dow is not 0-6.
    """
    if not 0 <= python_dow <= 6:
        raise ValueError(f"Invalid Python DOW: {python_dow}, must be 0-6")
    return PYTHON_TO_SQLITE_DOW[python_dow]


def _clamp_multiplier(value: float) -> float:
    """Clamp multiplier to configured bounds.

    Args:
        value: Raw multiplier value.

    Returns:
        Multiplier clamped to [MULTIPLIER_MIN, MULTIPLIER_MAX].
    """
    return max(MULTIPLIER_MIN, min(MULTIPLIER_MAX, value))


def _calculate_day_confidence(message_count: int) -> float:
    """Calculate confidence score for a single day based on message count.

    Uses a logarithmic scale that saturates around 50 messages:
    - 0-4 messages: 0.0 (insufficient)
    - 5-9 messages: 0.3-0.5 (low confidence)
    - 10-19 messages: 0.5-0.7 (medium confidence)
    - 20-49 messages: 0.7-0.9 (good confidence)
    - 50+ messages: 0.9-1.0 (high confidence)

    Args:
        message_count: Number of messages for this day.

    Returns:
        Confidence score (0.0-1.0).
    """
    if message_count < MIN_MESSAGES_PER_DAY:
        return 0.0

    # Logarithmic scaling with saturation
    import math
    # Scale: log(count/5) / log(10) gives ~0.3 at 10, ~0.7 at 25, ~1.0 at 50
    raw_confidence = math.log(message_count / MIN_MESSAGES_PER_DAY + 1) / math.log(11)
    return min(1.0, raw_confidence)


def _calculate_overall_confidence(
    day_confidences: dict[int, float],
    total_messages: int,
) -> float:
    """Calculate overall confidence from per-day confidences.

    Uses weighted average of day confidences, with penalty for
    missing or low-confidence days.

    Args:
        day_confidences: Per-day confidence scores (0=Monday, 6=Sunday).
        total_messages: Total messages across all days.

    Returns:
        Overall confidence score (0.0-1.0).
    """
    if total_messages < MIN_TOTAL_MESSAGES:
        return 0.0

    # Average of day confidences
    valid_confidences = [c for c in day_confidences.values() if c > 0]
    if not valid_confidences:
        return 0.0

    avg_confidence = sum(valid_confidences) / len(valid_confidences)

    # Penalty for missing days (days with 0 confidence)
    coverage_ratio = len(valid_confidences) / 7

    return avg_confidence * coverage_ratio


# =============================================================================
# Main Functions
# =============================================================================

def fetch_dow_performance(
    creator_id: str,
    db_path: Optional[str] = None,
    days_lookback: int = 60,
) -> list[DayPerformance]:
    """Fetch day-of-week performance data from database.

    Queries mass_messages table to aggregate performance metrics
    by day of week.

    Args:
        creator_id: Creator ID or page name.
        db_path: Path to SQLite database. Uses EROS_DB_PATH env var if not provided.
        days_lookback: Number of days to analyze (default 60).

    Returns:
        List of DayPerformance objects, one per day of week.

    Raises:
        InsufficientDataError: If no messages found for creator.
    """
    if db_path is None:
        db_path = os.environ.get(
            "EROS_DB_PATH",
            "./database/eros_sd_main.db"
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get creator_id if page_name provided
        cursor.execute("""
            SELECT creator_id FROM creators
            WHERE creator_id = ? OR page_name = ?
        """, (creator_id, creator_id))

        row = cursor.fetchone()
        if not row:
            raise InsufficientDataError(
                f"Creator not found: {creator_id}",
                data_type="creator",
                required=1,
                available=0,
            )

        actual_creator_id = row["creator_id"]

        # Query aggregated performance by day of week
        # SQLite strftime %w: 0=Sunday, 1=Monday, ..., 6=Saturday
        # Note: mass_messages uses 'sending_time' column (not 'sent_at')
        #       and 'earnings' column (not 'revenue')
        cursor.execute("""
            SELECT
                sending_day_of_week as sqlite_dow,
                COUNT(*) as message_count,
                COALESCE(SUM(earnings), 0) as total_revenue,
                COALESCE(AVG(earnings), 0) as avg_revenue,
                COALESCE(AVG(view_rate), 0) as avg_view_rate,
                COALESCE(AVG(purchase_rate), 0) as avg_purchase_rate
            FROM mass_messages
            WHERE creator_id = ?
              AND sending_time >= date('now', ? || ' days')
              AND sending_time IS NOT NULL
            GROUP BY sending_day_of_week
            ORDER BY sqlite_dow
        """, (actual_creator_id, -days_lookback))

        rows = cursor.fetchall()

        # Convert to DayPerformance objects with Python DOW
        performance_by_day: dict[int, DayPerformance] = {}

        for row in rows:
            python_dow = convert_sqlite_dow_to_python(row["sqlite_dow"])
            performance_by_day[python_dow] = DayPerformance(
                day_index=python_dow,
                day_name=DAY_NAMES[python_dow],
                message_count=row["message_count"],
                total_revenue=row["total_revenue"],
                avg_revenue=row["avg_revenue"],
                avg_view_rate=row["avg_view_rate"],
                avg_purchase_rate=row["avg_purchase_rate"],
            )

        # Fill in missing days with empty performance
        result = []
        for day_idx in range(7):
            if day_idx in performance_by_day:
                result.append(performance_by_day[day_idx])
            else:
                result.append(DayPerformance(
                    day_index=day_idx,
                    day_name=DAY_NAMES[day_idx],
                ))

        return result

    finally:
        conn.close()


def calculate_dow_multipliers(
    creator_id: str,
    db_path: Optional[str] = None,
    days_lookback: int = 60,
    use_defaults_on_insufficient: bool = True,
) -> DOWMultipliers:
    """Calculate day-of-week volume multipliers from historical data.

    Analyzes historical message performance by day of week to determine
    optimal volume distribution. Higher-performing days get higher
    multipliers (more messages), lower-performing days get lower
    multipliers.

    Args:
        creator_id: Creator ID or page name.
        db_path: Path to SQLite database.
        days_lookback: Number of days to analyze (default 60).
        use_defaults_on_insufficient: If True, return default multipliers
            when data is insufficient. If False, raise InsufficientDataError.

    Returns:
        DOWMultipliers with calculated or default values.

    Raises:
        InsufficientDataError: If data is insufficient and use_defaults_on_insufficient=False.
    """
    try:
        day_performance = fetch_dow_performance(creator_id, db_path, days_lookback)
    except InsufficientDataError:
        if use_defaults_on_insufficient:
            return DOWMultipliers(
                multipliers=DEFAULT_MULTIPLIERS.copy(),
                confidence=0.0,
                day_confidences={i: 0.0 for i in range(7)},
                total_messages=0,
                is_default=True,
                creator_id=creator_id,
            )
        raise

    # Calculate per-day confidence
    day_confidences = {
        perf.day_index: _calculate_day_confidence(perf.message_count)
        for perf in day_performance
    }

    total_messages = sum(perf.message_count for perf in day_performance)

    # Check if we have enough data
    if total_messages < MIN_TOTAL_MESSAGES:
        if use_defaults_on_insufficient:
            return DOWMultipliers(
                multipliers=DEFAULT_MULTIPLIERS.copy(),
                confidence=0.0,
                day_confidences=day_confidences,
                total_messages=total_messages,
                is_default=True,
                creator_id=creator_id,
            )
        raise InsufficientDataError(
            f"Insufficient messages for DOW analysis: {total_messages} < {MIN_TOTAL_MESSAGES}",
            data_type="messages",
            required=MIN_TOTAL_MESSAGES,
            available=total_messages,
        )

    # Calculate average revenue across all days
    total_revenue = sum(perf.total_revenue for perf in day_performance)
    avg_daily_revenue = total_revenue / 7 if total_revenue > 0 else 1.0

    # Calculate multipliers based on revenue performance
    # Higher revenue days get higher multipliers
    multipliers: dict[int, float] = {}

    for perf in day_performance:
        if perf.message_count >= MIN_MESSAGES_PER_DAY and avg_daily_revenue > 0:
            # Revenue-based multiplier
            raw_multiplier = perf.total_revenue / avg_daily_revenue

            # Dampen based on confidence
            confidence = day_confidences[perf.day_index]
            dampened_multiplier = 1.0 + (raw_multiplier - 1.0) * confidence

            # Clamp to bounds
            multipliers[perf.day_index] = _clamp_multiplier(dampened_multiplier)
        else:
            # Use default for low-data days
            multipliers[perf.day_index] = DEFAULT_MULTIPLIERS[perf.day_index]

    # Calculate overall confidence
    overall_confidence = _calculate_overall_confidence(day_confidences, total_messages)

    return DOWMultipliers(
        multipliers=multipliers,
        confidence=overall_confidence,
        day_confidences=day_confidences,
        total_messages=total_messages,
        is_default=False,
        creator_id=creator_id,
    )


def analyze_dow_patterns(
    creator_id: str,
    db_path: Optional[str] = None,
    days_lookback: int = 60,
) -> DOWAnalysis:
    """Perform complete day-of-week analysis for a creator.

    Combines multiplier calculation with detailed performance breakdown.

    Args:
        creator_id: Creator ID or page name.
        db_path: Path to SQLite database.
        days_lookback: Number of days to analyze.

    Returns:
        Complete DOWAnalysis with multipliers and performance data.
    """
    day_performance = fetch_dow_performance(creator_id, db_path, days_lookback)
    multipliers = calculate_dow_multipliers(creator_id, db_path, days_lookback)

    total_messages = sum(p.message_count for p in day_performance)

    # Calculate data quality score (0-100)
    # Based on: coverage, message volume, and variance
    coverage = sum(1 for p in day_performance if p.message_count >= MIN_MESSAGES_PER_DAY) / 7
    volume_score = min(1.0, total_messages / 100)  # Saturates at 100 messages

    data_quality = (coverage * 0.6 + volume_score * 0.4) * 100

    return DOWAnalysis(
        multipliers=multipliers,
        day_performance=day_performance,
        analysis_period_days=days_lookback,
        data_quality_score=data_quality,
    )


def apply_dow_modulation(
    base_volume: int,
    day_index: int,
    multipliers: DOWMultipliers,
) -> int:
    """Apply day-of-week modulation to a base volume.

    Args:
        base_volume: Base daily volume before modulation.
        day_index: Python weekday index (0=Monday, 6=Sunday).
        multipliers: DOW multipliers to apply.

    Returns:
        Adjusted volume for the specified day.
    """
    mult = multipliers.get_multiplier(day_index)
    return _round_volume(base_volume * mult)


def get_weekly_volume_distribution(
    base_daily_volume: int,
    creator_id: str,
    db_path: Optional[str] = None,
) -> dict[str, int]:
    """Get volume distribution for entire week.

    Convenience function that calculates multipliers and applies
    them to get per-day volumes.

    Args:
        base_daily_volume: Base volume per day.
        creator_id: Creator ID or page name.
        db_path: Path to SQLite database.

    Returns:
        Dict mapping day names to adjusted volumes.
    """
    multipliers = calculate_dow_multipliers(creator_id, db_path)
    distribution = multipliers.get_weekly_distribution(base_daily_volume)

    return {DAY_NAMES[day]: vol for day, vol in distribution.items()}


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Data classes
    "DayPerformance",
    "DOWMultipliers",
    "DOWAnalysis",
    # Constants
    "DEFAULT_MULTIPLIERS",
    "DAY_NAMES",
    "MULTIPLIER_MIN",
    "MULTIPLIER_MAX",
    "MIN_MESSAGES_PER_DAY",
    "MIN_TOTAL_MESSAGES",
    # Conversion functions
    "convert_sqlite_dow_to_python",
    "convert_python_dow_to_sqlite",
    # Main functions
    "fetch_dow_performance",
    "calculate_dow_multipliers",
    "analyze_dow_patterns",
    "apply_dow_modulation",
    "get_weekly_volume_distribution",
    # Internal (for testing)
    "_calculate_day_confidence",
    "_calculate_overall_confidence",
    "_clamp_multiplier",
    "_round_volume",
]
