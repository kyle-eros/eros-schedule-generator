"""
Multi-horizon score fusion for volume calculation.

Combines performance scores from multiple time periods (7d, 14d, 30d)
with intelligent weighting based on divergence detection.

The multi-horizon approach addresses limitations of single-period scoring:
- 7d data: Captures rapid changes and recent trends
- 14d data: Provides a balanced view (primary signal)
- 30d data: Establishes a stable baseline for comparison

When short-term (7d) scores diverge significantly from long-term (30d),
the system shifts weights to emphasize recent data, enabling faster
response to trend changes.

Usage:
    from python.volume.multi_horizon import (
        MultiHorizonAnalyzer,
        fuse_scores,
        HorizonScores,
        FusedScores,
    )

    # High-level interface
    analyzer = MultiHorizonAnalyzer("database/eros_sd_main.db")
    result = analyzer.analyze("alexia")
    print(f"Fused saturation: {result.saturation_score}")
    print(f"Divergence detected: {result.divergence_detected}")
    print(f"Recommendation: {analyzer.get_recommendation(result)}")

    # Low-level function-based interface
    horizons = {
        '7d': HorizonScores(period='7d', saturation_score=75, ...),
        '14d': HorizonScores(period='14d', saturation_score=60, ...),
        '30d': HorizonScores(period='30d', saturation_score=55, ...),
    }
    fused = fuse_scores(horizons)
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Dict, Tuple

from python.exceptions import DatabaseError, InsufficientDataError
from python.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default weights for score fusion
DEFAULT_WEIGHTS: Dict[str, float] = {
    '7d': 0.30,   # Recent signal - captures rapid changes
    '14d': 0.50,  # Primary signal - balanced view
    '30d': 0.20,  # Baseline signal - stability anchor
}

# Weights when rapid change detected (7d diverges significantly from 30d)
RAPID_CHANGE_WEIGHTS: Dict[str, float] = {
    '7d': 0.50,   # Emphasize recent changes
    '14d': 0.35,  # Still consider medium term
    '30d': 0.15,  # Reduce baseline influence
}

# Divergence threshold (points difference between 7d and 30d scores)
DIVERGENCE_THRESHOLD: float = 15.0

# Valid tracking periods
VALID_PERIODS: tuple[str, ...] = ('7d', '14d', '30d')


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class HorizonScores:
    """Performance scores for a single time horizon.

    Attributes:
        period: Time period ('7d', '14d', '30d').
        saturation_score: Saturation score for this period (0-100).
            Higher values indicate audience fatigue.
        opportunity_score: Opportunity score for this period (0-100).
            Higher values indicate growth potential.
        message_count: Number of messages sent in this period.
        avg_revenue_per_send: Average revenue per send for this period.
        tracking_date: ISO date string when scores were calculated.
        is_available: Whether data exists for this period.
    """

    period: str
    saturation_score: float = 50.0
    opportunity_score: float = 50.0
    message_count: int = 0
    avg_revenue_per_send: float = 0.0
    tracking_date: str = ""
    is_available: bool = False

    def __post_init__(self) -> None:
        """Validate period value."""
        if self.period not in VALID_PERIODS:
            raise ValueError(
                f"Invalid period '{self.period}'. "
                f"Must be one of: {', '.join(VALID_PERIODS)}"
            )


@dataclass
class FusedScores:
    """Result of multi-horizon score fusion.

    Attributes:
        saturation_score: Weighted saturation score (0-100).
        opportunity_score: Weighted opportunity score (0-100).
        weights_used: Weights applied to each horizon.
        divergence_detected: Whether 7d/30d divergence triggered weight shift.
        divergence_amount: Size of divergence in points.
        divergence_direction: Direction of change ('increasing', 'decreasing', 'stable').
        horizons: Individual horizon scores used in fusion.
        confidence: Confidence in fusion result (0.0-1.0) based on data quality.
        data_quality: Human-readable description of data availability.
    """

    saturation_score: float
    opportunity_score: float
    weights_used: Dict[str, float]
    divergence_detected: bool = False
    divergence_amount: float = 0.0
    divergence_direction: str = "stable"
    horizons: Dict[str, HorizonScores] = field(default_factory=dict)
    confidence: float = 1.0
    data_quality: str = "good"

    @property
    def is_reliable(self) -> bool:
        """Check if the fusion result is reliable enough for decisions."""
        return self.confidence >= 0.5 and self.data_quality != "insufficient"

    @property
    def is_trending_up(self) -> bool:
        """Check if performance is trending upward (saturation decreasing)."""
        return self.divergence_direction == "decreasing"

    @property
    def is_trending_down(self) -> bool:
        """Check if performance is trending downward (saturation increasing)."""
        return self.divergence_direction == "increasing"


# =============================================================================
# Core Functions
# =============================================================================


def detect_divergence(
    scores_7d: HorizonScores,
    scores_30d: HorizonScores,
    threshold: float = DIVERGENCE_THRESHOLD,
) -> Tuple[bool, float, str]:
    """Detect if short-term scores diverge significantly from long-term.

    Divergence indicates a trend change that should be weighted more heavily
    toward recent data. Both saturation and opportunity scores are checked,
    and the maximum divergence is used.

    Args:
        scores_7d: 7-day horizon scores.
        scores_30d: 30-day horizon scores.
        threshold: Point difference to consider divergent (default 15.0).

    Returns:
        Tuple of (is_divergent, divergence_amount, direction).
        - is_divergent: True if max divergence >= threshold
        - divergence_amount: Maximum divergence in points
        - direction: 'increasing' if 7d saturation > 30d (getting worse),
                     'decreasing' if 7d saturation < 30d (improving),
                     'stable' if no divergence

    Example:
        >>> s7 = HorizonScores(period='7d', saturation_score=75, is_available=True)
        >>> s30 = HorizonScores(period='30d', saturation_score=55, is_available=True)
        >>> is_div, amount, direction = detect_divergence(s7, s30)
        >>> print(f"Divergent: {is_div}, Amount: {amount}, Direction: {direction}")
        # Divergent: True, Amount: 20.0, Direction: increasing
    """
    if not scores_7d.is_available or not scores_30d.is_available:
        return False, 0.0, "stable"

    # Calculate divergence for both score types
    sat_divergence = abs(scores_7d.saturation_score - scores_30d.saturation_score)
    opp_divergence = abs(scores_7d.opportunity_score - scores_30d.opportunity_score)

    max_divergence = max(sat_divergence, opp_divergence)
    is_divergent = max_divergence >= threshold

    # Determine direction based on saturation trend (primary signal)
    # Increasing saturation = performance declining (audience fatigue)
    # Decreasing saturation = performance improving
    if is_divergent:
        sat_diff = scores_7d.saturation_score - scores_30d.saturation_score
        if sat_diff > 0:
            direction = "increasing"  # Saturation rising = performance declining
        elif sat_diff < 0:
            direction = "decreasing"  # Saturation falling = performance improving
        else:
            # Saturation unchanged, check opportunity
            opp_diff = scores_7d.opportunity_score - scores_30d.opportunity_score
            direction = "increasing" if opp_diff < 0 else "decreasing" if opp_diff > 0 else "stable"

        logger.info(
            "Divergence detected between 7d and 30d horizons",
            extra={
                "sat_divergence": round(sat_divergence, 2),
                "opp_divergence": round(opp_divergence, 2),
                "max_divergence": round(max_divergence, 2),
                "threshold": threshold,
                "direction": direction,
            }
        )
    else:
        direction = "stable"

    return is_divergent, max_divergence, direction


def select_weights(
    divergence_detected: bool,
    data_availability: Dict[str, bool],
) -> Dict[str, float]:
    """Select appropriate weights based on divergence and data availability.

    The function performs the following logic:
    1. Choose base weights (RAPID_CHANGE if divergent, DEFAULT otherwise)
    2. Redistribute weights from unavailable periods to available ones
    3. Normalize weights to ensure they sum to 1.0

    Args:
        divergence_detected: Whether 7d/30d divergence was detected.
        data_availability: Dict mapping period -> is_available.

    Returns:
        Weight dict with values summing to 1.0.

    Example:
        >>> weights = select_weights(
        ...     divergence_detected=True,
        ...     data_availability={'7d': True, '14d': True, '30d': False}
        ... )
        >>> print(weights)  # {'7d': 0.59, '14d': 0.41, '30d': 0.0}
    """
    # Start with appropriate base weights
    if divergence_detected:
        weights = RAPID_CHANGE_WEIGHTS.copy()
    else:
        weights = DEFAULT_WEIGHTS.copy()

    # Get list of available periods
    available_periods = [p for p, avail in data_availability.items() if avail]

    if len(available_periods) == 0:
        # No data at all - return 14d-only weights (will use defaults in fusion)
        logger.warning("No horizon data available, defaulting to 14d-only weights")
        return {'7d': 0.0, '14d': 1.0, '30d': 0.0}

    if len(available_periods) < 3:
        # Redistribute weights from missing periods to available ones
        missing_weight = sum(
            weights[p] for p in weights
            if not data_availability.get(p, False)
        )

        if missing_weight > 0 and len(available_periods) > 0:
            weight_per_available = missing_weight / len(available_periods)
            for period in available_periods:
                weights[period] += weight_per_available
            for period in weights:
                if not data_availability.get(period, False):
                    weights[period] = 0.0

    # Normalize to ensure sum is exactly 1.0 (handle floating point)
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    return weights


def fuse_scores(horizons: Dict[str, HorizonScores]) -> FusedScores:
    """Fuse scores from multiple horizons into single weighted result.

    Algorithm:
    1. Check for divergence between 7d and 30d periods
    2. Select weights based on divergence and data availability
    3. Calculate weighted average of saturation and opportunity scores
    4. Calculate confidence based on data quality and message count

    Args:
        horizons: Dict mapping period ('7d', '14d', '30d') to HorizonScores.

    Returns:
        FusedScores with weighted combination and metadata.

    Raises:
        ValueError: If horizons dict contains invalid period keys.

    Example:
        >>> horizons = {
        ...     '7d': HorizonScores(period='7d', saturation_score=70,
        ...                         opportunity_score=60, is_available=True),
        ...     '14d': HorizonScores(period='14d', saturation_score=65,
        ...                          opportunity_score=55, is_available=True),
        ...     '30d': HorizonScores(period='30d', saturation_score=60,
        ...                          opportunity_score=50, is_available=True),
        ... }
        >>> result = fuse_scores(horizons)
        >>> print(f"Saturation: {result.saturation_score}")
    """
    # Validate input periods
    for period in horizons:
        if period not in VALID_PERIODS:
            raise ValueError(
                f"Invalid period key '{period}'. "
                f"Must be one of: {', '.join(VALID_PERIODS)}"
            )

    # Extract data availability
    data_availability = {
        period: horizons.get(period, HorizonScores(period=period)).is_available
        for period in VALID_PERIODS
    }

    # Check divergence between 7d and 30d
    scores_7d = horizons.get('7d', HorizonScores(period='7d'))
    scores_30d = horizons.get('30d', HorizonScores(period='30d'))
    divergence_detected, divergence_amount, divergence_direction = detect_divergence(
        scores_7d, scores_30d
    )

    # Select weights
    weights = select_weights(divergence_detected, data_availability)

    # Calculate weighted scores
    weighted_saturation = 0.0
    weighted_opportunity = 0.0
    total_messages = 0

    for period, weight in weights.items():
        if weight > 0 and period in horizons and horizons[period].is_available:
            h = horizons[period]
            weighted_saturation += h.saturation_score * weight
            weighted_opportunity += h.opportunity_score * weight
            total_messages += h.message_count

    # If no available data produced scores, use neutral defaults
    if sum(1 for avail in data_availability.values() if avail) == 0:
        weighted_saturation = 50.0
        weighted_opportunity = 50.0

    # Clamp scores to valid 0-100 range (handles floating point edge cases)
    weighted_saturation = max(0.0, min(100.0, weighted_saturation))
    weighted_opportunity = max(0.0, min(100.0, weighted_opportunity))

    # Calculate confidence based on data quality
    available_count = sum(1 for avail in data_availability.values() if avail)
    confidence = available_count / 3.0  # Base: 0.33 to 1.0

    # Adjust confidence based on message count
    if total_messages < 10:
        confidence *= 0.5
    elif total_messages < 30:
        confidence *= 0.8

    # Determine data quality description
    if available_count == 3 and total_messages >= 30:
        data_quality = "excellent"
    elif available_count >= 2 and total_messages >= 10:
        data_quality = "good"
    elif available_count >= 1 and total_messages >= 5:
        data_quality = "limited"
    else:
        data_quality = "insufficient"

    return FusedScores(
        saturation_score=round(weighted_saturation, 2),
        opportunity_score=round(weighted_opportunity, 2),
        weights_used=weights,
        divergence_detected=divergence_detected,
        divergence_amount=round(divergence_amount, 2),
        divergence_direction=divergence_direction,
        horizons=horizons,
        confidence=round(confidence, 2),
        data_quality=data_quality,
    )


def fetch_horizon_scores(
    conn: sqlite3.Connection,
    creator_id: str,
) -> Dict[str, HorizonScores]:
    """Fetch performance scores for all horizons from database.

    Queries volume_performance_tracking for the most recent scores
    for each tracking period (7d, 14d, 30d).

    Args:
        conn: SQLite database connection.
        creator_id: Creator ID or username to fetch scores for.

    Returns:
        Dict mapping period to HorizonScores. All periods are included,
        with is_available=False for missing data.

    Raises:
        DatabaseError: If database query fails.

    Example:
        >>> conn = sqlite3.connect("database/eros_sd_main.db")
        >>> horizons = fetch_horizon_scores(conn, "alexia")
        >>> for period, scores in horizons.items():
        ...     print(f"{period}: sat={scores.saturation_score}, avail={scores.is_available}")
    """
    query = """
        SELECT
            vpt.tracking_period,
            vpt.saturation_score,
            vpt.opportunity_score,
            vpt.total_messages_sent,
            vpt.avg_revenue_per_send,
            vpt.tracking_date
        FROM volume_performance_tracking vpt
        WHERE vpt.creator_id = ?
          AND vpt.tracking_date = (
              SELECT MAX(tracking_date)
              FROM volume_performance_tracking
              WHERE creator_id = vpt.creator_id
                AND tracking_period = vpt.tracking_period
          )
        ORDER BY vpt.tracking_period
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to fetch horizon scores: {e}",
            operation="fetch_horizon_scores",
            details={"creator_id": creator_id}
        )

    # Initialize with defaults for all periods
    horizons: Dict[str, HorizonScores] = {
        '7d': HorizonScores(period='7d'),
        '14d': HorizonScores(period='14d'),
        '30d': HorizonScores(period='30d'),
    }

    for row in rows:
        period, sat, opp, msgs, rps, date = row
        if period in horizons:
            horizons[period] = HorizonScores(
                period=period,
                saturation_score=sat if sat is not None else 50.0,
                opportunity_score=opp if opp is not None else 50.0,
                message_count=msgs if msgs is not None else 0,
                avg_revenue_per_send=rps if rps is not None else 0.0,
                tracking_date=date if date is not None else "",
                is_available=True,
            )

    logger.debug(
        "Fetched horizon scores",
        extra={
            "creator_id": creator_id,
            "periods_available": [p for p, h in horizons.items() if h.is_available],
        }
    )

    return horizons


# =============================================================================
# High-Level Interface
# =============================================================================


class MultiHorizonAnalyzer:
    """High-level analyzer for multi-horizon score fusion.

    Provides convenient interface for fetching and fusing scores
    across multiple time periods (7d, 14d, 30d).

    Attributes:
        db_path: Path to the SQLite database file.

    Example:
        >>> analyzer = MultiHorizonAnalyzer("database/eros_sd_main.db")
        >>> result = analyzer.analyze("alexia")
        >>> print(f"Fused saturation: {result.saturation_score}")
        >>> print(f"Confidence: {result.confidence}")
        >>> print(analyzer.get_recommendation(result))
    """

    def __init__(self, db_path: str) -> None:
        """Initialize MultiHorizonAnalyzer.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    def analyze(self, creator_id: str) -> FusedScores:
        """Analyze and fuse scores for a creator.

        Fetches horizon scores from the database and fuses them
        using the multi-horizon algorithm.

        Args:
            creator_id: Creator ID or username to analyze.

        Returns:
            FusedScores with weighted combination from all horizons.

        Raises:
            DatabaseError: If database connection or query fails.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            horizons = fetch_horizon_scores(conn, creator_id)
            return fuse_scores(horizons)
        finally:
            conn.close()

    def get_recommendation(self, fused: FusedScores) -> str:
        """Get human-readable recommendation based on fused scores.

        Analyzes the fused scores and divergence data to provide
        actionable recommendations for volume adjustment.

        Args:
            fused: FusedScores result from analyze().

        Returns:
            Recommendation string describing suggested action.
        """
        if fused.data_quality == "insufficient":
            return "Insufficient data - use default volume settings"

        if fused.divergence_detected:
            scores_7d = fused.horizons.get('7d', HorizonScores(period='7d'))
            scores_30d = fused.horizons.get('30d', HorizonScores(period='30d'))

            if scores_7d.saturation_score > scores_30d.saturation_score:
                return "Rapid saturation increase detected - consider reducing volume"
            else:
                return "Recent improvement detected - consider increasing volume"

        if fused.saturation_score >= 70:
            return "High saturation - reduce volume to prevent burnout"
        elif fused.opportunity_score >= 70 and fused.saturation_score < 50:
            return "High opportunity with low saturation - increase volume"
        else:
            return "Balanced performance - maintain current volume"

    def analyze_with_recommendation(
        self,
        creator_id: str,
    ) -> Tuple[FusedScores, str]:
        """Convenience method to get both analysis and recommendation.

        Args:
            creator_id: Creator ID or username to analyze.

        Returns:
            Tuple of (FusedScores, recommendation_string).
        """
        fused = self.analyze(creator_id)
        recommendation = self.get_recommendation(fused)
        return fused, recommendation


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Data classes
    "HorizonScores",
    "FusedScores",
    # High-level interface
    "MultiHorizonAnalyzer",
    # Core functions
    "detect_divergence",
    "select_weights",
    "fuse_scores",
    "fetch_horizon_scores",
    # Constants
    "DEFAULT_WEIGHTS",
    "RAPID_CHANGE_WEIGHTS",
    "DIVERGENCE_THRESHOLD",
    "VALID_PERIODS",
]
