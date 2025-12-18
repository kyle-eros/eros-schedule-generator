"""
On-demand score calculation from raw mass_messages data.

Used when volume_performance_tracking has no recent data for a creator.
Calculates saturation_score and opportunity_score using the same algorithms
documented in migration 003_volume_performance.sql.

Algorithm Documentation (from migration 003):

Saturation Score (detects declining performance):
    - Base: 50/100
    - +20 if revenue_per_send declining > 15%
    - +15 if view_rate declining > 10%
    - +10 if purchase_rate declining > 10%
    - +15 if earnings volatility > 0.6

Opportunity Score (detects growth potential):
    - Base: 50/100
    - +20 if revenue_per_send > baseline * 1.15
    - +15 if view_rate growing > 5%
    - +10 if purchase_rate > 5%
    - +15 if fan_count growing > 10%
"""

import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from python.exceptions import DatabaseError, QueryError
from python.logging_config import get_logger, log_fallback

logger = get_logger(__name__)

# Character length performance data (from 160-caption analysis)
# Format: (min_chars, max_chars, performance_multiplier)
# Optimal zone (250-449) has baseline multiplier of 1.0 (405.54x avg RPS)
CHARACTER_LENGTH_RANGES = {
    'optimal': (250, 449, 1.0),        # 405.54x avg RPS (baseline)
    'medium_short': (150, 249, 0.755),  # -24.5% performance
    'short': (50, 149, 0.469),          # -53.1% performance
    'ultra_short': (0, 49, 0.220),      # -78.0% performance
    'medium_long': (450, 549, 0.372),   # -62.8% performance
    'long': (550, 749, 0.112),          # -88.8% performance
    'ultra_long': (750, float('inf'), 0.037),  # -96.3% performance
}


@dataclass
class PerformanceScores:
    """Result of on-demand score calculation.

    Attributes:
        saturation_score: Score indicating audience saturation (0-100).
            Higher scores suggest reducing volume.
        opportunity_score: Score indicating growth potential (0-100).
            Higher scores suggest increasing volume.
        avg_revenue_per_send: Average earnings per message sent.
        avg_view_rate: Average view rate (views / sent) as decimal.
        avg_purchase_rate: Average purchase rate (purchases / sent) as decimal.
        total_messages: Number of messages analyzed.
        calculation_date: ISO format date when scores were calculated.
        data_source: Indicates where data came from.
        period_days: Number of days in analysis period.
        earnings_volatility: Coefficient of variation of earnings (stdev/mean).
        breakdown: Detailed breakdown of score components.
    """

    saturation_score: float
    opportunity_score: float
    avg_revenue_per_send: float
    avg_view_rate: float
    avg_purchase_rate: float
    total_messages: int
    calculation_date: str
    data_source: str = "calculated_from_mass_messages"
    period_days: int = 14
    earnings_volatility: float = 0.0
    breakdown: dict = field(default_factory=dict)

    # Backwards compatibility alias
    @property
    def message_count(self) -> int:
        """Alias for total_messages (backwards compatibility)."""
        return self.total_messages


@dataclass
class PeriodMetrics:
    """Performance metrics for a single time period.

    Attributes:
        message_count: Number of PPV messages sent.
        avg_revenue_per_send: Average revenue per message.
        avg_view_rate: Average view rate (0-1).
        avg_purchase_rate: Average purchase rate (0-1).
        total_earnings: Sum of all earnings.
        earnings_list: Individual earnings for volatility calculation.
    """

    message_count: int = 0
    avg_revenue_per_send: float = 0.0
    avg_view_rate: float = 0.0
    avg_purchase_rate: float = 0.0
    total_earnings: float = 0.0
    earnings_list: list = field(default_factory=list)


def calculate_saturation_score(
    current_rps: float,
    previous_rps: float,
    current_view_rate: float,
    previous_view_rate: float,
    current_purchase_rate: float,
    previous_purchase_rate: float,
    earnings_volatility: float,
) -> tuple[float, dict]:
    """Calculate saturation score from performance metrics.

    Algorithm (from migration 003 notes):
    - Base: 50
    - +20 if revenue_per_send declining > 15%
    - +15 if view_rate declining > 10%
    - +10 if purchase_rate declining > 10%
    - +15 if earnings_volatility > 0.6

    Args:
        current_rps: Current period revenue per send.
        previous_rps: Previous period revenue per send.
        current_view_rate: Current period view rate (0-1).
        previous_view_rate: Previous period view rate (0-1).
        current_purchase_rate: Current period purchase rate (0-1).
        previous_purchase_rate: Previous period purchase rate (0-1).
        earnings_volatility: Standard deviation / mean of earnings (0-1+).

    Returns:
        Tuple of (saturation_score, breakdown_dict).
        Score is clamped to 0-100 range.
    """
    score = 50.0
    breakdown = {
        "base_score": 50.0,
        "rps_decline_points": 0.0,
        "view_rate_decline_points": 0.0,
        "purchase_rate_decline_points": 0.0,
        "volatility_points": 0.0,
        "rps_change_pct": 0.0,
        "view_rate_change_pct": 0.0,
        "purchase_rate_change_pct": 0.0,
    }

    # Revenue per send declining > 15%
    if previous_rps > 0:
        rps_change = (current_rps - previous_rps) / previous_rps * 100
        breakdown["rps_change_pct"] = round(rps_change, 2)
        if rps_change < -15:
            score += 20
            breakdown["rps_decline_points"] = 20.0

    # View rate declining > 10%
    if previous_view_rate > 0:
        vr_change = (current_view_rate - previous_view_rate) / previous_view_rate * 100
        breakdown["view_rate_change_pct"] = round(vr_change, 2)
        if vr_change < -10:
            score += 15
            breakdown["view_rate_decline_points"] = 15.0

    # Purchase rate declining > 10%
    if previous_purchase_rate > 0:
        pr_change = (
            (current_purchase_rate - previous_purchase_rate)
            / previous_purchase_rate
            * 100
        )
        breakdown["purchase_rate_change_pct"] = round(pr_change, 2)
        if pr_change < -10:
            score += 10
            breakdown["purchase_rate_decline_points"] = 10.0

    # High earnings volatility
    if earnings_volatility > 0.6:
        score += 15
        breakdown["volatility_points"] = 15.0

    final_score = min(100.0, max(0.0, score))
    breakdown["final_score"] = final_score

    return final_score, breakdown


def calculate_opportunity_score(
    current_rps: float,
    baseline_rps: float,
    current_view_rate: float,
    previous_view_rate: float,
    current_purchase_rate: float,
    fan_count_growth: float,
) -> tuple[float, dict]:
    """Calculate opportunity score from performance metrics.

    Algorithm (from migration 003 notes):
    - Base: 50
    - +20 if revenue_per_send > baseline * 1.15
    - +15 if view_rate growing > 5%
    - +10 if purchase_rate > 5%
    - +15 if fan_count growing > 10%

    Args:
        current_rps: Current period revenue per send.
        baseline_rps: Baseline revenue per send (historical average).
        current_view_rate: Current period view rate (0-1).
        previous_view_rate: Previous period view rate (0-1).
        current_purchase_rate: Current period purchase rate (0-1).
        fan_count_growth: % growth in fan count.

    Returns:
        Tuple of (opportunity_score, breakdown_dict).
        Score is clamped to 0-100 range.
    """
    score = 50.0
    breakdown = {
        "base_score": 50.0,
        "rps_above_baseline_points": 0.0,
        "view_rate_growth_points": 0.0,
        "purchase_rate_points": 0.0,
        "fan_growth_points": 0.0,
        "rps_vs_baseline_pct": 0.0,
        "view_rate_change_pct": 0.0,
    }

    # Revenue per send above baseline by 15%+
    if baseline_rps > 0:
        rps_ratio = current_rps / baseline_rps
        breakdown["rps_vs_baseline_pct"] = round((rps_ratio - 1.0) * 100, 2)
        if current_rps > baseline_rps * 1.15:
            score += 20
            breakdown["rps_above_baseline_points"] = 20.0

    # View rate growing > 5%
    if previous_view_rate > 0:
        vr_change = (current_view_rate - previous_view_rate) / previous_view_rate * 100
        breakdown["view_rate_change_pct"] = round(vr_change, 2)
        if vr_change > 5:
            score += 15
            breakdown["view_rate_growth_points"] = 15.0

    # Purchase rate > 5%
    if current_purchase_rate > 0.05:
        score += 10
        breakdown["purchase_rate_points"] = 10.0

    # Fan count growing > 10%
    if fan_count_growth > 10:
        score += 15
        breakdown["fan_growth_points"] = 15.0

    final_score = min(100.0, max(0.0, score))
    breakdown["final_score"] = final_score

    return final_score, breakdown


def _calculate_volatility(values: list[float]) -> float:
    """Calculate coefficient of variation (std dev / mean).

    Args:
        values: List of numeric values.

    Returns:
        Coefficient of variation, or 0.0 if insufficient data.
    """
    if len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0

    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std_dev = math.sqrt(variance)

    return std_dev / mean


def _fetch_period_metrics(
    conn: sqlite3.Connection,
    creator_id: str,
    start_date: str,
    end_date: str | None = None,
) -> PeriodMetrics:
    """Fetch performance metrics for a time period.

    Queries mass_messages table using the computed columns (view_rate,
    purchase_rate, revenue_per_send) already defined in the schema.

    Args:
        conn: SQLite database connection.
        creator_id: Creator identifier.
        start_date: Start of period (YYYY-MM-DD).
        end_date: End of period (YYYY-MM-DD), or None for open-ended.

    Returns:
        PeriodMetrics with aggregated data.
    """
    params: tuple[str, ...]
    if end_date:
        query = """
            SELECT
                COUNT(*) as message_count,
                AVG(revenue_per_send) as avg_rps,
                AVG(view_rate) as avg_view_rate,
                AVG(purchase_rate) as avg_purchase_rate,
                SUM(earnings) as total_earnings
            FROM mass_messages
            WHERE creator_id = ?
            AND message_type = 'ppv'
            AND sent_count > 0
            AND sending_time >= ?
            AND sending_time < ?
        """
        params = (creator_id, start_date, end_date)
    else:
        query = """
            SELECT
                COUNT(*) as message_count,
                AVG(revenue_per_send) as avg_rps,
                AVG(view_rate) as avg_view_rate,
                AVG(purchase_rate) as avg_purchase_rate,
                SUM(earnings) as total_earnings
            FROM mass_messages
            WHERE creator_id = ?
            AND message_type = 'ppv'
            AND sent_count > 0
            AND sending_time >= ?
        """
        params = (creator_id, start_date)

    try:
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
    except sqlite3.Error as e:
        raise QueryError(
            f"Failed to fetch period metrics: {e}",
            query=query,
            params=list(params),
        ) from e

    if not row or row[0] == 0:
        return PeriodMetrics()

    # Fetch individual earnings for volatility calculation
    earnings_query = """
        SELECT earnings
        FROM mass_messages
        WHERE creator_id = ?
        AND message_type = 'ppv'
        AND sent_count > 0
        AND sending_time >= ?
    """
    earnings_params: tuple[str, ...] = (creator_id, start_date)

    if end_date:
        earnings_query += " AND sending_time < ?"
        earnings_params = (creator_id, start_date, end_date)

    try:
        cursor = conn.execute(earnings_query, earnings_params)
        earnings_rows = cursor.fetchall()
        earnings_list = [r[0] for r in earnings_rows if r[0] is not None]
    except sqlite3.Error as e:
        logger.warning(
            "Failed to fetch earnings for volatility calculation",
            extra={"creator_id": creator_id, "error": str(e)},
        )
        earnings_list = []

    return PeriodMetrics(
        message_count=row[0] or 0,
        avg_revenue_per_send=row[1] or 0.0,
        avg_view_rate=row[2] or 0.0,
        avg_purchase_rate=row[3] or 0.0,
        total_earnings=row[4] or 0.0,
        earnings_list=earnings_list,
    )


def calculate_scores_from_db(
    conn: sqlite3.Connection,
    creator_id: str,
    period_days: int = 14,
    min_messages: int = 5,
) -> Optional[PerformanceScores]:
    """Calculate saturation and opportunity scores from raw mass_messages data.

    Queries mass_messages table to compute metrics for current and previous
    periods, then calculates scores using the standard algorithms documented
    in migration 003_volume_performance.sql.

    This function is used as a fallback when volume_performance_tracking
    has no recent data for a creator.

    Args:
        conn: SQLite database connection.
        creator_id: Creator identifier (creator_id or page_name).
        period_days: Number of days for analysis period (default 14).
        min_messages: Minimum messages required for calculation (default 5).

    Returns:
        PerformanceScores if sufficient data exists, None otherwise.

    Raises:
        QueryError: If database query fails.

    Example:
        >>> conn = sqlite3.connect("database/eros_sd_main.db")
        >>> scores = calculate_scores_from_db(conn, "alexia", period_days=14)
        >>> if scores:
        ...     print(f"Saturation: {scores.saturation_score}")
        ...     print(f"Opportunity: {scores.opportunity_score}")
    """
    today = datetime.now()
    current_start = (today - timedelta(days=period_days)).strftime("%Y-%m-%d")
    previous_start = (today - timedelta(days=period_days * 2)).strftime("%Y-%m-%d")
    previous_end = current_start

    logger.debug(
        "Calculating scores from mass_messages",
        extra={
            "creator_id": creator_id,
            "period_days": period_days,
            "current_start": current_start,
            "previous_start": previous_start,
        },
    )

    # Fetch current period metrics
    current = _fetch_period_metrics(conn, creator_id, current_start)

    if current.message_count < min_messages:
        log_fallback(
            logger,
            operation="score_calculation",
            fallback_reason=f"Insufficient messages ({current.message_count} < {min_messages})",
            fallback_action="returning None",
            creator_id=creator_id,
        )
        return None

    # Fetch previous period metrics for trend comparison
    previous = _fetch_period_metrics(conn, creator_id, previous_start, previous_end)

    # If no previous data, use current as baseline (no trend penalty)
    if previous.message_count == 0:
        log_fallback(
            logger,
            operation="score_calculation",
            fallback_reason="No previous period data for trend calculation",
            fallback_action="using current period as baseline",
            creator_id=creator_id,
        )
        previous = current

    # Calculate earnings volatility
    earnings_volatility = _calculate_volatility(current.earnings_list)

    # Calculate saturation score
    saturation, sat_breakdown = calculate_saturation_score(
        current_rps=current.avg_revenue_per_send,
        previous_rps=previous.avg_revenue_per_send,
        current_view_rate=current.avg_view_rate,
        previous_view_rate=previous.avg_view_rate,
        current_purchase_rate=current.avg_purchase_rate,
        previous_purchase_rate=previous.avg_purchase_rate,
        earnings_volatility=earnings_volatility,
    )

    # Calculate opportunity score
    # Note: fan_count_growth would require additional query or data source
    # For now, we default to 0.0 (no fan growth bonus)
    opportunity, opp_breakdown = calculate_opportunity_score(
        current_rps=current.avg_revenue_per_send,
        baseline_rps=previous.avg_revenue_per_send,
        current_view_rate=current.avg_view_rate,
        previous_view_rate=previous.avg_view_rate,
        current_purchase_rate=current.avg_purchase_rate,
        fan_count_growth=0.0,
    )

    logger.info(
        "Calculated performance scores",
        extra={
            "creator_id": creator_id,
            "saturation_score": saturation,
            "opportunity_score": opportunity,
            "message_count": current.message_count,
            "period_days": period_days,
        },
    )

    return PerformanceScores(
        saturation_score=round(saturation, 2),
        opportunity_score=round(opportunity, 2),
        avg_revenue_per_send=round(current.avg_revenue_per_send, 2),
        avg_view_rate=round(current.avg_view_rate, 4),
        avg_purchase_rate=round(current.avg_purchase_rate, 4),
        total_messages=current.message_count,
        calculation_date=today.strftime("%Y-%m-%d"),
        period_days=period_days,
        earnings_volatility=round(earnings_volatility, 4),
        breakdown={
            "saturation": sat_breakdown,
            "opportunity": opp_breakdown,
            "current_period": {
                "start": current_start,
                "message_count": current.message_count,
                "total_earnings": round(current.total_earnings, 2),
            },
            "previous_period": {
                "start": previous_start,
                "end": previous_end,
                "message_count": previous.message_count,
                "total_earnings": round(previous.total_earnings, 2),
            },
        },
    )


def calculate_character_length_multiplier(caption_text: str | None) -> float:
    """Calculate performance multiplier based on caption character length.

    Performance multiplier derived from 160-caption dataset analysis.
    The optimal zone (250-449 characters) achieved 405.54x average RPS
    and serves as the baseline (multiplier = 1.0).

    Args:
        caption_text: Caption text to evaluate. None or empty returns
            the minimum multiplier (0.037).

    Returns:
        Multiplier between 0.037 (worst case) and 1.0 (optimal zone).

    Raises:
        TypeError: If caption_text is not a string or None.

    Example:
        >>> calculate_character_length_multiplier("Short")
        0.22
        >>> calculate_character_length_multiplier("A" * 300)
        1.0
        >>> calculate_character_length_multiplier(None)
        0.037
    """
    if caption_text is None:
        return 0.037  # Treat None as worst case

    if not isinstance(caption_text, str):
        raise TypeError(f"Expected str, got {type(caption_text).__name__}")

    # Handle whitespace-only strings as empty
    stripped_text = caption_text.strip()
    char_count = len(stripped_text)

    if char_count == 0:
        return 0.037  # Empty or whitespace-only string is worst case

    # Determine multiplier based on character count ranges
    if 250 <= char_count <= 449:
        return 1.0      # OPTIMAL ZONE
    elif 150 <= char_count < 250:
        return 0.755    # -24.5% performance
    elif 50 <= char_count < 150:
        return 0.469    # -53.1% performance
    elif char_count < 50:
        return 0.220    # -78.0% performance
    elif 450 <= char_count < 550:
        return 0.372    # -62.8% performance
    elif 550 <= char_count < 750:
        return 0.112    # -88.8% performance
    else:  # 750+
        return 0.037    # -96.3% performance (ultra-long)


def calculate_enhanced_eros_score(
    caption_data: dict,
    rps_score: float | None = None,
    conversion_score: float | None = None,
    execution_score: float | None = None,
    diversity_score: float | None = None,
) -> float:
    """Calculate enhanced EROS score with character length optimization.

    EROS scoring operates at send/campaign level with component weights:
    - 40% RPS (revenue per send)
    - 30% conversion rate
    - 20% execution quality
    - 10% diversity bonus

    The base EROS score is then modulated by a character length multiplier
    with 40% weight, rewarding captions in the optimal 250-449 character range.

    Final formula: base_eros * (0.6 + 0.4 * length_multiplier)

    Args:
        caption_data: Dictionary containing at minimum:
            - 'text': Caption text string for length analysis
            - Optional: 'rps_score', 'conversion_score', 'execution_score',
              'diversity_score' (defaults to 0.0 if not provided)
        rps_score: Override RPS score (takes precedence over caption_data).
        conversion_score: Override conversion score.
        execution_score: Override execution score.
        diversity_score: Override diversity score.

    Returns:
        Enhanced EROS score between 0.0 and 1.0.

    Raises:
        TypeError: If caption_data is not a dictionary.

    Example:
        >>> caption = {'text': 'A' * 300, 'rps_score': 0.8, 'conversion_score': 0.7}
        >>> calculate_enhanced_eros_score(caption)
        0.41  # High score due to optimal length and good metrics
        >>> caption_short = {'text': 'Hi', 'rps_score': 0.8}
        >>> calculate_enhanced_eros_score(caption_short)
        0.22  # Penalized for ultra-short length
    """
    if not isinstance(caption_data, dict):
        raise TypeError(f"Expected dict, got {type(caption_data).__name__}")

    # Extract scores from caption_data or use overrides
    _rps = rps_score if rps_score is not None else caption_data.get('rps_score', 0.0)
    _conv = (
        conversion_score
        if conversion_score is not None
        else caption_data.get('conversion_score', 0.0)
    )
    _exec = (
        execution_score
        if execution_score is not None
        else caption_data.get('execution_score', 0.0)
    )
    _div = (
        diversity_score
        if diversity_score is not None
        else caption_data.get('diversity_score', 0.0)
    )

    # Base EROS calculation (send/campaign level weights)
    base_eros_score = (
        0.40 * _rps +
        0.30 * _conv +
        0.20 * _exec +
        0.10 * _div
    )

    # Apply character length multiplier
    length_multiplier = calculate_character_length_multiplier(caption_data.get('text'))

    # 40% weight to length optimization
    # Range: base_eros * 0.6 (worst length) to base_eros * 1.0 (optimal length)
    enhanced_score = base_eros_score * (0.6 + 0.4 * length_multiplier)

    return enhanced_score


class ScoreCalculator:
    """Calculator for on-demand performance score generation.

    This class provides a higher-level interface for score calculation
    with connection management and caching support.

    Attributes:
        db_path: Path to the SQLite database file.
        default_period_days: Default analysis period in days.
        min_messages: Minimum messages required for calculation.

    Example:
        >>> calc = ScoreCalculator("database/eros_sd_main.db")
        >>> scores = calc.calculate("alexia")
        >>> print(f"Saturation: {scores.saturation_score}")
    """

    def __init__(
        self,
        db_path: str,
        default_period_days: int = 14,
        min_messages: int = 5,
    ) -> None:
        """Initialize ScoreCalculator.

        Args:
            db_path: Path to SQLite database file.
            default_period_days: Default analysis period (days).
            min_messages: Minimum messages required for calculation.
        """
        self.db_path = db_path
        self.default_period_days = default_period_days
        self.min_messages = min_messages
        self._logger = get_logger(__name__)

    def calculate(
        self,
        creator_id: str,
        period_days: int | None = None,
    ) -> Optional[PerformanceScores]:
        """Calculate performance scores for a creator.

        Args:
            creator_id: Creator identifier.
            period_days: Analysis period (uses default if None).

        Returns:
            PerformanceScores if sufficient data, None otherwise.

        Raises:
            DatabaseError: If connection or query fails.
        """
        period = period_days or self.default_period_days

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return calculate_scores_from_db(
                conn,
                creator_id,
                period_days=period,
                min_messages=self.min_messages,
            )
        except sqlite3.Error as e:
            raise DatabaseError(
                f"Failed to connect to database: {e}",
                operation="score_calculation",
                details={"db_path": self.db_path, "creator_id": creator_id},
            ) from e
        finally:
            if "conn" in locals():
                conn.close()

    def calculate_batch(
        self,
        creator_ids: list[str],
        period_days: int | None = None,
    ) -> dict[str, Optional[PerformanceScores]]:
        """Calculate performance scores for multiple creators.

        Args:
            creator_ids: List of creator identifiers.
            period_days: Analysis period (uses default if None).

        Returns:
            Dictionary mapping creator_id to PerformanceScores (or None).
        """
        period = period_days or self.default_period_days
        results: dict[str, Optional[PerformanceScores]] = {}

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            for creator_id in creator_ids:
                try:
                    results[creator_id] = calculate_scores_from_db(
                        conn,
                        creator_id,
                        period_days=period,
                        min_messages=self.min_messages,
                    )
                except QueryError as e:
                    self._logger.warning(
                        f"Failed to calculate scores for {creator_id}: {e}",
                        extra={"creator_id": creator_id},
                    )
                    results[creator_id] = None

            return results
        except sqlite3.Error as e:
            raise DatabaseError(
                f"Failed to connect to database: {e}",
                operation="batch_score_calculation",
                details={"db_path": self.db_path},
            ) from e
        finally:
            if "conn" in locals():
                conn.close()


# Backwards compatibility export (renamed from CalculatedScores)
CalculatedScores = PerformanceScores

__all__ = [
    "PerformanceScores",
    "CalculatedScores",
    "PeriodMetrics",
    "ScoreCalculator",
    "calculate_saturation_score",
    "calculate_opportunity_score",
    "calculate_scores_from_db",
    "calculate_character_length_multiplier",
    "calculate_enhanced_eros_score",
    "CHARACTER_LENGTH_RANGES",
]
