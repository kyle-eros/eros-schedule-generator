"""
Revenue elasticity model for volume optimization.

Models diminishing returns using exponential decay to identify
optimal volume levels where marginal revenue remains efficient.
"""

import math
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from python.exceptions import DatabaseError, InsufficientDataError
from python.logging_config import get_logger

logger = get_logger(__name__)


# Default decay rate when insufficient data for fitting
DEFAULT_DECAY_RATE = 0.08

# Minimum marginal RPS to consider efficient
DEFAULT_MIN_MARGINAL_RPS = 0.05

# Volume at which to evaluate marginal returns
VOLUME_EVALUATION_POINTS = [3, 5, 7, 10, 12, 15]


@dataclass
class ElasticityParameters:
    """Parameters for the elasticity model.

    Attributes:
        base_rps: Revenue per send at volume=0 (intercept).
        decay_rate: Rate of diminishing returns (higher = faster decay).
        min_marginal_rps: Threshold for efficient marginal revenue.
        optimal_volume: Volume where MR equals threshold.
        fit_quality: R-squared of model fit (0-1).
    """
    base_rps: float
    decay_rate: float
    min_marginal_rps: float = DEFAULT_MIN_MARGINAL_RPS
    optimal_volume: int = 7
    fit_quality: float = 0.0

    @property
    def is_reliable(self) -> bool:
        """Returns True if model fit is acceptable (R-squared > 0.5)."""
        return self.fit_quality > 0.5


@dataclass
class VolumePoint:
    """Performance at a specific volume level.

    Attributes:
        daily_volume: Number of sends per day.
        sample_count: Number of days at this volume level.
        avg_rps: Average revenue per send.
        total_revenue: Total revenue at this volume.
        marginal_rps: Estimated marginal RPS (change from previous).
    """
    daily_volume: int
    sample_count: int
    avg_rps: float
    total_revenue: float
    marginal_rps: float = 0.0


@dataclass
class ElasticityProfile:
    """Complete elasticity analysis for a creator.

    Attributes:
        creator_id: Creator identifier.
        parameters: Fitted elasticity parameters.
        volume_points: Historical data points used for fitting.
        recommendations: Volume recommendations based on model.
        current_efficiency: Efficiency at current volume.
        has_sufficient_data: Whether data supports reliable model.
    """
    creator_id: str
    parameters: ElasticityParameters = field(default_factory=lambda: ElasticityParameters(
        base_rps=0.15,
        decay_rate=DEFAULT_DECAY_RATE,
    ))
    volume_points: List[VolumePoint] = field(default_factory=list)
    recommendations: Dict[str, str] = field(default_factory=dict)
    current_efficiency: float = 1.0
    has_sufficient_data: bool = False


class ElasticityModel:
    """Exponential decay model for revenue elasticity.

    Models marginal revenue as: MR(v) = base_rps * exp(-decay_rate * v)

    This captures diminishing returns where each additional send
    generates less revenue than the previous one.
    """

    def __init__(
        self,
        base_rps: float,
        decay_rate: float,
        min_marginal_rps: float = DEFAULT_MIN_MARGINAL_RPS,
    ):
        """Initialize elasticity model.

        Args:
            base_rps: Revenue per send at volume=0.
            decay_rate: Decay rate for diminishing returns.
            min_marginal_rps: Minimum efficient marginal RPS.
        """
        self.base_rps = max(0.01, base_rps)
        self.decay_rate = max(0.001, decay_rate)
        self.min_marginal_rps = min_marginal_rps

    def marginal_revenue(self, volume: int) -> float:
        """Calculate marginal revenue at given volume.

        Args:
            volume: Daily send volume.

        Returns:
            Marginal revenue per additional send.
        """
        if volume < 0:
            return self.base_rps
        return self.base_rps * math.exp(-self.decay_rate * volume)

    def total_revenue(self, volume: int) -> float:
        """Calculate total expected revenue at given volume.

        Integral of marginal revenue from 0 to volume.

        Args:
            volume: Daily send volume.

        Returns:
            Total expected revenue.
        """
        if volume <= 0:
            return 0.0

        # Integral of base * exp(-rate * v) = -base/rate * (exp(-rate*v) - 1)
        return (self.base_rps / self.decay_rate) * (1 - math.exp(-self.decay_rate * volume))

    def optimal_volume(self) -> int:
        """Find volume where marginal revenue equals threshold.

        Solves: base_rps * exp(-decay_rate * v) = min_marginal_rps
        v = -ln(min_marginal_rps / base_rps) / decay_rate

        Returns:
            Optimal volume (rounded down).
        """
        if self.min_marginal_rps >= self.base_rps:
            return 1

        ratio = self.min_marginal_rps / self.base_rps
        if ratio <= 0:
            return 20  # Cap at reasonable maximum

        volume = -math.log(ratio) / self.decay_rate
        return max(1, min(20, int(volume)))

    def efficiency_at_volume(self, volume: int) -> float:
        """Calculate efficiency ratio at given volume.

        Efficiency = marginal_revenue / base_rps
        1.0 = fully efficient, 0.0 = exhausted returns

        Args:
            volume: Daily send volume.

        Returns:
            Efficiency ratio (0-1).
        """
        mr = self.marginal_revenue(volume)
        return mr / self.base_rps if self.base_rps > 0 else 0.0

    def volume_curve(
        self,
        max_volume: int = 15,
    ) -> List[Tuple[int, float, float]]:
        """Generate volume-revenue curve.

        Args:
            max_volume: Maximum volume to evaluate.

        Returns:
            List of (volume, marginal_revenue, total_revenue) tuples.
        """
        curve = []
        for v in range(max_volume + 1):
            curve.append((v, self.marginal_revenue(v), self.total_revenue(v)))
        return curve


def fit_elasticity_model(
    volume_points: List[VolumePoint],
) -> ElasticityParameters:
    """Fit elasticity model to historical volume-performance data.

    Uses simple least-squares fitting of exponential decay.

    Args:
        volume_points: Historical data points.

    Returns:
        Fitted ElasticityParameters.
    """
    if not volume_points or len(volume_points) < 3:
        logger.warning("Insufficient data points for elasticity fitting")
        return ElasticityParameters(
            base_rps=0.15,
            decay_rate=DEFAULT_DECAY_RATE,
            fit_quality=0.0,
        )

    # Sort by volume
    points = sorted(volume_points, key=lambda p: p.daily_volume)

    # Extract data
    volumes = [p.daily_volume for p in points]
    rps_values = [p.avg_rps for p in points]

    # Use log-linear regression for exponential fit
    # ln(RPS) = ln(base) - decay * volume
    try:
        log_rps = [math.log(max(0.001, r)) for r in rps_values]

        n = len(volumes)
        sum_v = sum(volumes)
        sum_log = sum(log_rps)
        sum_v_log = sum(v * lr for v, lr in zip(volumes, log_rps))
        sum_v2 = sum(v * v for v in volumes)

        # Linear regression coefficients
        denom = n * sum_v2 - sum_v * sum_v
        if abs(denom) < 1e-10:
            raise ValueError("Singular matrix")

        slope = (n * sum_v_log - sum_v * sum_log) / denom
        intercept = (sum_log - slope * sum_v) / n

        base_rps = math.exp(intercept)
        decay_rate = -slope

        # Ensure positive decay rate
        if decay_rate <= 0:
            decay_rate = DEFAULT_DECAY_RATE

        # Calculate R-squared
        mean_log = sum_log / n
        ss_tot = sum((lr - mean_log) ** 2 for lr in log_rps)
        ss_res = sum((lr - (intercept + slope * v)) ** 2 for lr, v in zip(log_rps, volumes))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        model = ElasticityModel(base_rps, decay_rate)
        optimal = model.optimal_volume()

        return ElasticityParameters(
            base_rps=round(base_rps, 4),
            decay_rate=round(decay_rate, 4),
            optimal_volume=optimal,
            fit_quality=round(max(0, r_squared), 3),
        )

    except (ValueError, ZeroDivisionError) as e:
        logger.warning(f"Elasticity fitting failed: {e}")
        return ElasticityParameters(
            base_rps=max(rps_values) if rps_values else 0.15,
            decay_rate=DEFAULT_DECAY_RATE,
            fit_quality=0.0,
        )


def fetch_volume_performance_data(
    conn: sqlite3.Connection,
    creator_id: str,
    lookback_days: int = 90,
) -> List[VolumePoint]:
    """Fetch historical volume-performance data for elasticity fitting.

    Groups messages by daily volume and calculates average RPS
    at each volume level.

    Args:
        conn: Database connection.
        creator_id: Creator to analyze.
        lookback_days: Days of history to analyze.

    Returns:
        List of VolumePoint data.

    Raises:
        DatabaseError: If query fails.
    """
    query = """
        WITH daily_stats AS (
            SELECT
                date(sending_time) as send_date,
                COUNT(*) as daily_volume,
                AVG(revenue_per_send) as avg_rps,
                SUM(earnings) as total_revenue
            FROM mass_messages
            WHERE creator_id = ?
              AND sending_time >= datetime('now', ?)
              AND message_type = 'ppv'
              AND sent_count > 0
            GROUP BY send_date
        )
        SELECT
            daily_volume,
            COUNT(*) as sample_count,
            AVG(avg_rps) as avg_rps,
            AVG(total_revenue) as avg_total_revenue
        FROM daily_stats
        GROUP BY daily_volume
        HAVING sample_count >= 3
        ORDER BY daily_volume
    """

    lookback_param = f"-{lookback_days} days"

    try:
        cursor = conn.execute(query, (creator_id, lookback_param))
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to fetch volume performance data: {e}",
            operation="fetch_volume_performance_data",
            details={"creator_id": creator_id}
        )

    points = []
    prev_rps = None

    for row in rows:
        volume, count, rps, total_rev = row

        # Calculate marginal RPS
        marginal = 0.0
        if prev_rps is not None and rps is not None:
            marginal = rps - prev_rps
        prev_rps = rps

        points.append(VolumePoint(
            daily_volume=volume,
            sample_count=count,
            avg_rps=round(rps or 0.0, 4),
            total_revenue=round(total_rev or 0.0, 2),
            marginal_rps=round(marginal, 4),
        ))

    return points


def calculate_elasticity_profile(
    conn: sqlite3.Connection,
    creator_id: str,
    lookback_days: int = 90,
) -> ElasticityProfile:
    """Calculate complete elasticity profile for a creator.

    Args:
        conn: Database connection.
        creator_id: Creator to analyze.
        lookback_days: Days of history.

    Returns:
        ElasticityProfile with fitted model and recommendations.
    """
    profile = ElasticityProfile(creator_id=creator_id)

    # Fetch volume-performance data
    profile.volume_points = fetch_volume_performance_data(
        conn, creator_id, lookback_days
    )

    # Check for sufficient data
    profile.has_sufficient_data = len(profile.volume_points) >= 3

    if not profile.has_sufficient_data:
        profile.recommendations["data"] = (
            "Insufficient data for elasticity analysis. "
            "Need at least 3 different volume levels with 3+ samples each."
        )
        return profile

    # Fit model
    profile.parameters = fit_elasticity_model(profile.volume_points)

    # Generate recommendations
    if profile.parameters.is_reliable:
        optimal = profile.parameters.optimal_volume
        model = ElasticityModel(
            profile.parameters.base_rps,
            profile.parameters.decay_rate,
        )

        profile.recommendations["optimal"] = (
            f"Optimal daily volume: {optimal} sends "
            f"(marginal revenue stays above ${profile.parameters.min_marginal_rps:.2f})"
        )

        if optimal < 5:
            profile.recommendations["warning"] = (
                "Low optimal volume indicates high saturation or "
                "diminishing returns. Consider content refresh."
            )
        elif optimal > 10:
            profile.recommendations["opportunity"] = (
                "High optimal volume indicates growth opportunity. "
                "Consider increasing send frequency."
            )
    else:
        profile.recommendations["fit_quality"] = (
            f"Model fit quality is low (R-squared={profile.parameters.fit_quality:.2f}). "
            "Results should be used with caution."
        )

    return profile


def should_cap_volume(
    model: ElasticityModel,
    proposed_volume: int,
    min_efficiency: float = 0.3,
) -> Tuple[bool, int, str]:
    """Determine if proposed volume should be capped based on elasticity.

    Args:
        model: Fitted ElasticityModel.
        proposed_volume: Proposed daily volume.
        min_efficiency: Minimum efficiency ratio to maintain.

    Returns:
        Tuple of (should_cap, recommended_volume, reason).
    """
    efficiency = model.efficiency_at_volume(proposed_volume)

    if efficiency >= min_efficiency:
        return False, proposed_volume, "Volume is efficient"

    # Find volume where efficiency is at threshold
    optimal = model.optimal_volume()

    return True, optimal, (
        f"Volume {proposed_volume} has only {efficiency:.0%} efficiency. "
        f"Recommend capping at {optimal} for better returns."
    )


class ElasticityOptimizer:
    """High-level optimizer using elasticity model.

    Provides convenient interface for elasticity-based volume optimization.
    """

    def __init__(self, db_path: str, lookback_days: int = 90):
        """Initialize optimizer.

        Args:
            db_path: Path to SQLite database.
            lookback_days: Days of history to analyze.
        """
        self.db_path = db_path
        self.lookback_days = lookback_days
        self._cache: Dict[str, ElasticityProfile] = {}

    def get_profile(
        self,
        creator_id: str,
        force_refresh: bool = False,
    ) -> ElasticityProfile:
        """Get or calculate elasticity profile for a creator.

        Args:
            creator_id: Creator to analyze.
            force_refresh: Force recalculation even if cached.

        Returns:
            ElasticityProfile for the creator.
        """
        if not force_refresh and creator_id in self._cache:
            return self._cache[creator_id]

        conn = sqlite3.connect(self.db_path)
        try:
            profile = calculate_elasticity_profile(
                conn, creator_id, self.lookback_days
            )
            self._cache[creator_id] = profile
            return profile
        finally:
            conn.close()

    def optimize_volume(
        self,
        creator_id: str,
        proposed_volume: int,
    ) -> Tuple[int, str]:
        """Optimize proposed volume using elasticity model.

        Args:
            creator_id: Creator for elasticity lookup.
            proposed_volume: Initial proposed volume.

        Returns:
            Tuple of (optimized_volume, reason).
        """
        profile = self.get_profile(creator_id)

        if not profile.has_sufficient_data or not profile.parameters.is_reliable:
            return proposed_volume, "Insufficient data for elasticity optimization"

        model = ElasticityModel(
            profile.parameters.base_rps,
            profile.parameters.decay_rate,
        )

        should_cap, optimal, reason = should_cap_volume(model, proposed_volume)

        if should_cap:
            return optimal, reason
        return proposed_volume, reason


__all__ = [
    "ElasticityParameters",
    "VolumePoint",
    "ElasticityProfile",
    "ElasticityModel",
    "ElasticityOptimizer",
    "fit_elasticity_model",
    "fetch_volume_performance_data",
    "calculate_elasticity_profile",
    "should_cap_volume",
    "DEFAULT_DECAY_RATE",
    "DEFAULT_MIN_MARGINAL_RPS",
    "VOLUME_EVALUATION_POINTS",
]
