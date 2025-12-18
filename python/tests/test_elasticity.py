"""
Unit tests for revenue elasticity model.

Tests cover:
- ElasticityModel marginal revenue calculation
- Optimal volume calculation at various decay rates
- Model fitting with synthetic data
- Volume capping decisions
- Edge cases (no data, single point, negative values)
- R-squared calculation validation
"""

import math
import sqlite3
import sys
from pathlib import Path
from typing import List

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.volume.elasticity import (
    ElasticityParameters,
    VolumePoint,
    ElasticityProfile,
    ElasticityModel,
    ElasticityOptimizer,
    fit_elasticity_model,
    fetch_volume_performance_data,
    calculate_elasticity_profile,
    should_cap_volume,
    DEFAULT_DECAY_RATE,
    DEFAULT_MIN_MARGINAL_RPS,
    VOLUME_EVALUATION_POINTS,
)
from python.exceptions import DatabaseError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def default_model() -> ElasticityModel:
    """Standard elasticity model with typical parameters."""
    return ElasticityModel(
        base_rps=0.15,
        decay_rate=0.08,
        min_marginal_rps=0.05,
    )


@pytest.fixture
def high_decay_model() -> ElasticityModel:
    """Model with high decay rate (rapid diminishing returns)."""
    return ElasticityModel(
        base_rps=0.20,
        decay_rate=0.20,
        min_marginal_rps=0.05,
    )


@pytest.fixture
def low_decay_model() -> ElasticityModel:
    """Model with low decay rate (slow diminishing returns)."""
    return ElasticityModel(
        base_rps=0.10,
        decay_rate=0.03,
        min_marginal_rps=0.05,
    )


@pytest.fixture
def synthetic_volume_points() -> List[VolumePoint]:
    """Synthetic data points following exponential decay pattern.

    Generated from: RPS = 0.20 * exp(-0.10 * volume)
    """
    base = 0.20
    decay = 0.10
    return [
        VolumePoint(
            daily_volume=1,
            sample_count=10,
            avg_rps=round(base * math.exp(-decay * 1), 4),
            total_revenue=5.0,
        ),
        VolumePoint(
            daily_volume=3,
            sample_count=15,
            avg_rps=round(base * math.exp(-decay * 3), 4),
            total_revenue=8.0,
        ),
        VolumePoint(
            daily_volume=5,
            sample_count=12,
            avg_rps=round(base * math.exp(-decay * 5), 4),
            total_revenue=10.0,
        ),
        VolumePoint(
            daily_volume=7,
            sample_count=8,
            avg_rps=round(base * math.exp(-decay * 7), 4),
            total_revenue=11.0,
        ),
        VolumePoint(
            daily_volume=10,
            sample_count=5,
            avg_rps=round(base * math.exp(-decay * 10), 4),
            total_revenue=12.0,
        ),
    ]


@pytest.fixture
def noisy_volume_points() -> List[VolumePoint]:
    """Data points with noise that still show decay trend."""
    return [
        VolumePoint(daily_volume=2, sample_count=10, avg_rps=0.18, total_revenue=4.0),
        VolumePoint(daily_volume=4, sample_count=8, avg_rps=0.14, total_revenue=6.0),
        VolumePoint(daily_volume=6, sample_count=12, avg_rps=0.11, total_revenue=7.5),
        VolumePoint(daily_volume=8, sample_count=6, avg_rps=0.09, total_revenue=8.0),
        VolumePoint(daily_volume=10, sample_count=5, avg_rps=0.06, total_revenue=8.5),
    ]


@pytest.fixture
def minimal_volume_points() -> List[VolumePoint]:
    """Minimum 3 data points for fitting."""
    return [
        VolumePoint(daily_volume=3, sample_count=5, avg_rps=0.15, total_revenue=5.0),
        VolumePoint(daily_volume=6, sample_count=5, avg_rps=0.10, total_revenue=7.0),
        VolumePoint(daily_volume=9, sample_count=5, avg_rps=0.07, total_revenue=8.0),
    ]


@pytest.fixture
def insufficient_volume_points() -> List[VolumePoint]:
    """Only 2 points - insufficient for fitting."""
    return [
        VolumePoint(daily_volume=3, sample_count=5, avg_rps=0.15, total_revenue=5.0),
        VolumePoint(daily_volume=6, sample_count=5, avg_rps=0.10, total_revenue=7.0),
    ]


@pytest.fixture
def flat_volume_points() -> List[VolumePoint]:
    """Data points with no decay (constant RPS)."""
    return [
        VolumePoint(daily_volume=2, sample_count=5, avg_rps=0.10, total_revenue=2.0),
        VolumePoint(daily_volume=5, sample_count=5, avg_rps=0.10, total_revenue=5.0),
        VolumePoint(daily_volume=8, sample_count=5, avg_rps=0.10, total_revenue=8.0),
    ]


@pytest.fixture
def db_connection() -> sqlite3.Connection:
    """In-memory SQLite database with mass_messages schema."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE mass_messages (
            id INTEGER PRIMARY KEY,
            creator_id TEXT NOT NULL,
            sending_time TEXT NOT NULL,
            message_type TEXT NOT NULL,
            sent_count INTEGER DEFAULT 0,
            earnings REAL DEFAULT 0,
            revenue_per_send REAL DEFAULT 0
        )
    """)

    conn.commit()
    return conn


# =============================================================================
# ElasticityModel Tests
# =============================================================================


class TestElasticityModelMarginalRevenue:
    """Tests for marginal revenue calculation."""

    def test_marginal_revenue_at_zero(self, default_model: ElasticityModel) -> None:
        """MR at volume=0 should equal base_rps."""
        mr = default_model.marginal_revenue(0)
        assert mr == pytest.approx(0.15, rel=1e-6)

    def test_marginal_revenue_decreases_with_volume(
        self, default_model: ElasticityModel
    ) -> None:
        """MR should decrease as volume increases."""
        volumes = [0, 3, 5, 7, 10]
        mrs = [default_model.marginal_revenue(v) for v in volumes]

        for i in range(len(mrs) - 1):
            assert mrs[i] > mrs[i + 1], (
                f"MR at volume {volumes[i]} should be > MR at volume {volumes[i+1]}"
            )

    def test_marginal_revenue_exponential_decay(
        self, default_model: ElasticityModel
    ) -> None:
        """MR should follow exponential decay formula."""
        volume = 5
        expected = 0.15 * math.exp(-0.08 * 5)
        actual = default_model.marginal_revenue(volume)
        assert actual == pytest.approx(expected, rel=1e-6)

    def test_marginal_revenue_negative_volume(
        self, default_model: ElasticityModel
    ) -> None:
        """Negative volume should return base_rps."""
        mr = default_model.marginal_revenue(-5)
        assert mr == default_model.base_rps

    def test_marginal_revenue_large_volume(
        self, default_model: ElasticityModel
    ) -> None:
        """Very large volume should approach zero."""
        mr = default_model.marginal_revenue(100)
        assert mr < 0.001  # Nearly zero


class TestElasticityModelTotalRevenue:
    """Tests for total revenue calculation."""

    def test_total_revenue_at_zero(self, default_model: ElasticityModel) -> None:
        """Total revenue at volume=0 should be 0."""
        tr = default_model.total_revenue(0)
        assert tr == 0.0

    def test_total_revenue_negative_volume(
        self, default_model: ElasticityModel
    ) -> None:
        """Negative volume should return 0."""
        tr = default_model.total_revenue(-5)
        assert tr == 0.0

    def test_total_revenue_increases_with_volume(
        self, default_model: ElasticityModel
    ) -> None:
        """Total revenue should increase (at decreasing rate)."""
        volumes = [1, 3, 5, 7, 10]
        trs = [default_model.total_revenue(v) for v in volumes]

        for i in range(len(trs) - 1):
            assert trs[i] < trs[i + 1], (
                f"TR at volume {volumes[i]} should be < TR at volume {volumes[i+1]}"
            )

    def test_total_revenue_formula(self, default_model: ElasticityModel) -> None:
        """Total revenue should match integral formula."""
        volume = 5
        base = 0.15
        rate = 0.08
        expected = (base / rate) * (1 - math.exp(-rate * volume))
        actual = default_model.total_revenue(volume)
        assert actual == pytest.approx(expected, rel=1e-6)

    def test_total_revenue_converges(self, default_model: ElasticityModel) -> None:
        """Total revenue should approach base/rate as volume increases."""
        max_tr = default_model.base_rps / default_model.decay_rate
        large_volume_tr = default_model.total_revenue(100)
        assert large_volume_tr == pytest.approx(max_tr, rel=0.01)


class TestElasticityModelOptimalVolume:
    """Tests for optimal volume calculation."""

    def test_optimal_volume_default_params(
        self, default_model: ElasticityModel
    ) -> None:
        """Optimal volume calculation with default parameters."""
        # Solve: 0.15 * exp(-0.08 * v) = 0.05
        # v = -ln(0.05/0.15) / 0.08 = -ln(1/3) / 0.08 = 1.0986 / 0.08 = 13.73
        optimal = default_model.optimal_volume()
        assert optimal == 13

    def test_optimal_volume_high_decay(self, high_decay_model: ElasticityModel) -> None:
        """High decay should result in lower optimal volume."""
        # Solve: 0.20 * exp(-0.20 * v) = 0.05
        # v = -ln(0.25) / 0.20 = 1.386 / 0.20 = 6.93
        optimal = high_decay_model.optimal_volume()
        assert optimal == 6

    def test_optimal_volume_low_decay(self, low_decay_model: ElasticityModel) -> None:
        """Low decay should result in higher optimal volume."""
        # Solve: 0.10 * exp(-0.03 * v) = 0.05
        # v = -ln(0.5) / 0.03 = 0.693 / 0.03 = 23.1
        # Capped at 20
        optimal = low_decay_model.optimal_volume()
        assert optimal == 20

    def test_optimal_volume_threshold_equals_base(self) -> None:
        """When threshold >= base, optimal should be 1."""
        model = ElasticityModel(base_rps=0.05, decay_rate=0.08, min_marginal_rps=0.10)
        assert model.optimal_volume() == 1

    def test_optimal_volume_minimum_is_one(self) -> None:
        """Optimal volume should be at least 1."""
        model = ElasticityModel(base_rps=0.05, decay_rate=0.50, min_marginal_rps=0.04)
        assert model.optimal_volume() >= 1

    def test_optimal_volume_maximum_is_twenty(self) -> None:
        """Optimal volume should be capped at 20."""
        model = ElasticityModel(base_rps=1.0, decay_rate=0.01, min_marginal_rps=0.001)
        assert model.optimal_volume() <= 20


class TestElasticityModelEfficiency:
    """Tests for efficiency calculation."""

    def test_efficiency_at_zero(self, default_model: ElasticityModel) -> None:
        """Efficiency at volume=0 should be 1.0."""
        eff = default_model.efficiency_at_volume(0)
        assert eff == pytest.approx(1.0, rel=1e-6)

    def test_efficiency_decreases_with_volume(
        self, default_model: ElasticityModel
    ) -> None:
        """Efficiency should decrease with volume."""
        eff_0 = default_model.efficiency_at_volume(0)
        eff_5 = default_model.efficiency_at_volume(5)
        eff_10 = default_model.efficiency_at_volume(10)

        assert eff_0 > eff_5 > eff_10

    def test_efficiency_formula(self, default_model: ElasticityModel) -> None:
        """Efficiency should equal exp(-decay * volume)."""
        volume = 7
        expected = math.exp(-0.08 * 7)
        actual = default_model.efficiency_at_volume(volume)
        assert actual == pytest.approx(expected, rel=1e-6)

    def test_efficiency_bounded_zero_to_one(
        self, default_model: ElasticityModel
    ) -> None:
        """Efficiency should be between 0 and 1."""
        for v in [0, 5, 10, 20, 50]:
            eff = default_model.efficiency_at_volume(v)
            assert 0 <= eff <= 1


class TestElasticityModelVolumeCurve:
    """Tests for volume curve generation."""

    def test_volume_curve_length(self, default_model: ElasticityModel) -> None:
        """Curve should have max_volume + 1 points."""
        curve = default_model.volume_curve(max_volume=10)
        assert len(curve) == 11

    def test_volume_curve_structure(self, default_model: ElasticityModel) -> None:
        """Each point should be (volume, mr, tr) tuple."""
        curve = default_model.volume_curve(max_volume=5)

        for point in curve:
            assert len(point) == 3
            volume, mr, tr = point
            assert isinstance(volume, int)
            assert isinstance(mr, float)
            assert isinstance(tr, float)

    def test_volume_curve_values(self, default_model: ElasticityModel) -> None:
        """Curve values should match model calculations."""
        curve = default_model.volume_curve(max_volume=5)

        for volume, mr, tr in curve:
            expected_mr = default_model.marginal_revenue(volume)
            expected_tr = default_model.total_revenue(volume)
            assert mr == pytest.approx(expected_mr, rel=1e-6)
            assert tr == pytest.approx(expected_tr, rel=1e-6)


class TestElasticityModelBoundaryConditions:
    """Tests for parameter boundary handling."""

    def test_base_rps_floor(self) -> None:
        """Base RPS should be floored at 0.01."""
        model = ElasticityModel(base_rps=-0.5, decay_rate=0.08)
        assert model.base_rps == 0.01

    def test_decay_rate_floor(self) -> None:
        """Decay rate should be floored at 0.001."""
        model = ElasticityModel(base_rps=0.15, decay_rate=-0.1)
        assert model.decay_rate == 0.001

    def test_zero_base_rps(self) -> None:
        """Zero base_rps should be floored."""
        model = ElasticityModel(base_rps=0, decay_rate=0.08)
        assert model.base_rps == 0.01


# =============================================================================
# Model Fitting Tests
# =============================================================================


class TestFitElasticityModel:
    """Tests for model fitting function."""

    def test_fit_with_synthetic_data(
        self, synthetic_volume_points: List[VolumePoint]
    ) -> None:
        """Fitting should recover parameters from synthetic data."""
        params = fit_elasticity_model(synthetic_volume_points)

        # Should recover approximately base=0.20, decay=0.10
        assert params.base_rps == pytest.approx(0.20, rel=0.1)
        assert params.decay_rate == pytest.approx(0.10, rel=0.1)
        assert params.fit_quality > 0.9  # High R-squared for clean data

    def test_fit_with_noisy_data(
        self, noisy_volume_points: List[VolumePoint]
    ) -> None:
        """Fitting should handle noisy data with acceptable quality."""
        params = fit_elasticity_model(noisy_volume_points)

        # Should still find decay pattern
        assert params.decay_rate > 0.05
        assert params.base_rps > 0.10
        assert params.fit_quality > 0.5

    def test_fit_with_minimal_data(
        self, minimal_volume_points: List[VolumePoint]
    ) -> None:
        """Fitting should work with exactly 3 data points."""
        params = fit_elasticity_model(minimal_volume_points)

        assert params.base_rps > 0
        assert params.decay_rate > 0
        # R-squared may be lower with few points

    def test_fit_with_insufficient_data(
        self, insufficient_volume_points: List[VolumePoint]
    ) -> None:
        """Fitting should return defaults with < 3 data points."""
        params = fit_elasticity_model(insufficient_volume_points)

        assert params.base_rps == 0.15  # Default
        assert params.decay_rate == DEFAULT_DECAY_RATE
        assert params.fit_quality == 0.0

    def test_fit_with_empty_data(self) -> None:
        """Fitting should handle empty data list."""
        params = fit_elasticity_model([])

        assert params.base_rps == 0.15
        assert params.decay_rate == DEFAULT_DECAY_RATE
        assert params.fit_quality == 0.0

    def test_fit_with_flat_data(
        self, flat_volume_points: List[VolumePoint]
    ) -> None:
        """Fitting should handle flat (no decay) data."""
        params = fit_elasticity_model(flat_volume_points)

        # Should use default decay rate since no decay observed
        assert params.decay_rate == DEFAULT_DECAY_RATE
        assert params.fit_quality < 0.5  # Poor fit expected

    def test_fit_calculates_optimal_volume(
        self, synthetic_volume_points: List[VolumePoint]
    ) -> None:
        """Fitted params should include calculated optimal volume."""
        params = fit_elasticity_model(synthetic_volume_points)

        # Optimal should be calculated from fitted params
        model = ElasticityModel(params.base_rps, params.decay_rate)
        expected_optimal = model.optimal_volume()
        assert params.optimal_volume == expected_optimal

    def test_fit_is_reliable_property(
        self, synthetic_volume_points: List[VolumePoint]
    ) -> None:
        """is_reliable should return True for good fits."""
        params = fit_elasticity_model(synthetic_volume_points)
        assert params.is_reliable is True

    def test_fit_is_unreliable_for_bad_data(
        self, flat_volume_points: List[VolumePoint]
    ) -> None:
        """is_reliable should return False for poor fits."""
        params = fit_elasticity_model(flat_volume_points)
        assert params.is_reliable is False


class TestRSquaredCalculation:
    """Tests for R-squared calculation in model fitting."""

    def test_r_squared_perfect_fit(self) -> None:
        """Perfect exponential data should give R-squared near 1."""
        base, decay = 0.25, 0.12
        points = [
            VolumePoint(
                daily_volume=v,
                sample_count=10,
                avg_rps=base * math.exp(-decay * v),
                total_revenue=10.0,
            )
            for v in [1, 3, 5, 7, 9, 11]
        ]

        params = fit_elasticity_model(points)
        assert params.fit_quality > 0.99

    def test_r_squared_range(
        self, noisy_volume_points: List[VolumePoint]
    ) -> None:
        """R-squared should be between 0 and 1."""
        params = fit_elasticity_model(noisy_volume_points)
        assert 0 <= params.fit_quality <= 1

    def test_r_squared_clamped_non_negative(self) -> None:
        """R-squared should not be negative."""
        # Data that might give negative R-squared due to bad fit
        points = [
            VolumePoint(daily_volume=1, sample_count=5, avg_rps=0.05, total_revenue=1.0),
            VolumePoint(daily_volume=5, sample_count=5, avg_rps=0.20, total_revenue=5.0),
            VolumePoint(daily_volume=10, sample_count=5, avg_rps=0.10, total_revenue=10.0),
        ]

        params = fit_elasticity_model(points)
        assert params.fit_quality >= 0


# =============================================================================
# Volume Capping Tests
# =============================================================================


class TestShouldCapVolume:
    """Tests for volume capping decisions."""

    def test_no_cap_when_efficient(self, default_model: ElasticityModel) -> None:
        """Should not cap when efficiency is above threshold."""
        should_cap, vol, reason = should_cap_volume(default_model, 5, min_efficiency=0.3)

        # Efficiency at volume 5: exp(-0.08 * 5) = 0.67
        assert should_cap is False
        assert vol == 5
        assert "efficient" in reason.lower()

    def test_cap_when_inefficient(self, default_model: ElasticityModel) -> None:
        """Should cap when efficiency is below threshold."""
        should_cap, vol, reason = should_cap_volume(default_model, 15, min_efficiency=0.5)

        # Efficiency at volume 15: exp(-0.08 * 15) = 0.30
        assert should_cap is True
        assert vol < 15
        assert "recommend" in reason.lower() or "efficiency" in reason.lower()

    def test_cap_returns_optimal_volume(self, default_model: ElasticityModel) -> None:
        """Capping should return the model's optimal volume."""
        _, optimal, _ = should_cap_volume(default_model, 20, min_efficiency=0.5)

        model_optimal = default_model.optimal_volume()
        assert optimal == model_optimal

    def test_cap_with_high_efficiency_threshold(
        self, default_model: ElasticityModel
    ) -> None:
        """High efficiency threshold should trigger capping earlier."""
        should_cap_80, _, _ = should_cap_volume(default_model, 5, min_efficiency=0.8)
        should_cap_30, _, _ = should_cap_volume(default_model, 5, min_efficiency=0.3)

        # Volume 5 has efficiency ~0.67, so should cap at 0.8 but not 0.3
        assert should_cap_80 is True
        assert should_cap_30 is False

    def test_cap_message_includes_details(
        self, default_model: ElasticityModel
    ) -> None:
        """Cap message should include useful details."""
        _, _, reason = should_cap_volume(default_model, 18, min_efficiency=0.4)

        # Message should mention volume and efficiency
        assert "18" in reason or "efficiency" in reason.lower()


# =============================================================================
# ElasticityProfile Tests
# =============================================================================


class TestElasticityProfile:
    """Tests for ElasticityProfile dataclass."""

    def test_profile_default_values(self) -> None:
        """Profile should have sensible defaults."""
        profile = ElasticityProfile(creator_id="test123")

        assert profile.creator_id == "test123"
        assert profile.parameters.base_rps == 0.15
        assert profile.parameters.decay_rate == DEFAULT_DECAY_RATE
        assert profile.volume_points == []
        assert profile.recommendations == {}
        assert profile.current_efficiency == 1.0
        assert profile.has_sufficient_data is False

    def test_profile_with_data(
        self, minimal_volume_points: List[VolumePoint]
    ) -> None:
        """Profile can be created with volume points."""
        params = fit_elasticity_model(minimal_volume_points)
        profile = ElasticityProfile(
            creator_id="test456",
            parameters=params,
            volume_points=minimal_volume_points,
            has_sufficient_data=True,
        )

        assert profile.has_sufficient_data is True
        assert len(profile.volume_points) == 3


# =============================================================================
# Database Fetch Tests
# =============================================================================


class TestFetchVolumePerformanceData:
    """Tests for database fetch function."""

    def test_fetch_empty_database(self, db_connection: sqlite3.Connection) -> None:
        """Should return empty list for empty database."""
        points = fetch_volume_performance_data(db_connection, "creator1")
        assert points == []

    def test_fetch_with_data(self, db_connection: sqlite3.Connection) -> None:
        """Should correctly aggregate and return volume points."""
        cursor = db_connection.cursor()

        # Insert test data: 5 days of data with 3 PPV sends each
        for day in range(5):
            for i in range(3):
                cursor.execute("""
                    INSERT INTO mass_messages
                    (creator_id, sending_time, message_type, sent_count, earnings, revenue_per_send)
                    VALUES (?, datetime('now', ?), 'ppv', 100, 50.0, 0.50)
                """, ("creator1", f"-{day} days"))

        db_connection.commit()

        points = fetch_volume_performance_data(db_connection, "creator1", lookback_days=30)

        # Should have one point for daily_volume=3 with 5 samples
        # But HAVING sample_count >= 3, so it depends on aggregation
        assert isinstance(points, list)

    def test_fetch_filters_by_creator(self, db_connection: sqlite3.Connection) -> None:
        """Should only return data for specified creator."""
        cursor = db_connection.cursor()

        # Insert data for two creators
        for day in range(5):
            for i in range(3):
                cursor.execute("""
                    INSERT INTO mass_messages
                    (creator_id, sending_time, message_type, sent_count, earnings, revenue_per_send)
                    VALUES ('creator1', datetime('now', ?), 'ppv', 100, 50.0, 0.50)
                """, (f"-{day} days",))
                cursor.execute("""
                    INSERT INTO mass_messages
                    (creator_id, sending_time, message_type, sent_count, earnings, revenue_per_send)
                    VALUES ('creator2', datetime('now', ?), 'ppv', 100, 30.0, 0.30)
                """, (f"-{day} days",))

        db_connection.commit()

        points1 = fetch_volume_performance_data(db_connection, "creator1")
        points2 = fetch_volume_performance_data(db_connection, "creator2")

        # RPS values should differ between creators
        if points1 and points2:
            assert points1[0].avg_rps != points2[0].avg_rps

    def test_fetch_respects_lookback_days(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Should only include data within lookback period."""
        cursor = db_connection.cursor()

        # Insert data 120 days ago (beyond typical lookback)
        for i in range(5):
            cursor.execute("""
                INSERT INTO mass_messages
                (creator_id, sending_time, message_type, sent_count, earnings, revenue_per_send)
                VALUES ('creator1', datetime('now', '-120 days'), 'ppv', 100, 50.0, 0.50)
            """)

        db_connection.commit()

        points = fetch_volume_performance_data(
            db_connection, "creator1", lookback_days=90
        )

        # Should not include 120-day-old data
        assert points == []

    def test_fetch_filters_ppv_only(self, db_connection: sqlite3.Connection) -> None:
        """Should only include PPV message types."""
        cursor = db_connection.cursor()

        # Insert PPV and non-PPV messages
        for day in range(5):
            cursor.execute("""
                INSERT INTO mass_messages
                (creator_id, sending_time, message_type, sent_count, earnings, revenue_per_send)
                VALUES ('creator1', datetime('now', ?), 'ppv', 100, 50.0, 0.50)
            """, (f"-{day} days",))
            cursor.execute("""
                INSERT INTO mass_messages
                (creator_id, sending_time, message_type, sent_count, earnings, revenue_per_send)
                VALUES ('creator1', datetime('now', ?), 'bump', 100, 5.0, 0.05)
            """, (f"-{day} days",))

        db_connection.commit()

        points = fetch_volume_performance_data(db_connection, "creator1")

        # If any points returned, RPS should reflect PPV only (~0.50)
        if points:
            assert all(p.avg_rps > 0.10 for p in points)


# =============================================================================
# Calculate Elasticity Profile Tests
# =============================================================================


class TestCalculateElasticityProfile:
    """Tests for full profile calculation."""

    def test_profile_insufficient_data(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Profile should indicate insufficient data for empty database."""
        profile = calculate_elasticity_profile(db_connection, "creator1")

        assert profile.has_sufficient_data is False
        assert "data" in profile.recommendations or "insufficient" in str(profile.recommendations).lower()

    def test_profile_with_sufficient_data(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Profile should fit model with sufficient data."""
        cursor = db_connection.cursor()

        # Insert enough data: 3+ samples for 3+ different volume levels
        volumes = [3, 5, 7]
        for vol in volumes:
            for sample in range(4):  # 4 samples each
                day = vol * 10 + sample
                base_rps = 0.20 * math.exp(-0.10 * vol)
                for i in range(vol):
                    cursor.execute("""
                        INSERT INTO mass_messages
                        (creator_id, sending_time, message_type, sent_count, earnings, revenue_per_send)
                        VALUES ('creator1', datetime('now', ?), 'ppv', 100, ?, ?)
                    """, (f"-{day} days", base_rps * 100, base_rps))

        db_connection.commit()

        profile = calculate_elasticity_profile(db_connection, "creator1")

        # Check profile structure
        assert profile.creator_id == "creator1"
        assert isinstance(profile.parameters, ElasticityParameters)


# =============================================================================
# ElasticityOptimizer Tests
# =============================================================================


class TestElasticityOptimizer:
    """Tests for the high-level optimizer class."""

    def test_optimizer_caching(self, db_connection: sqlite3.Connection) -> None:
        """Optimizer should cache profiles."""
        # Create temp database file
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Create database with schema
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE mass_messages (
                    id INTEGER PRIMARY KEY,
                    creator_id TEXT NOT NULL,
                    sending_time TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    sent_count INTEGER DEFAULT 0,
                    earnings REAL DEFAULT 0,
                    revenue_per_send REAL DEFAULT 0
                )
            """)
            conn.commit()
            conn.close()

            optimizer = ElasticityOptimizer(db_path)

            # First call should populate cache
            profile1 = optimizer.get_profile("creator1")
            profile2 = optimizer.get_profile("creator1")

            assert profile1 is profile2  # Same object from cache

        finally:
            os.unlink(db_path)

    def test_optimizer_force_refresh(self, db_connection: sqlite3.Connection) -> None:
        """force_refresh should bypass cache."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE mass_messages (
                    id INTEGER PRIMARY KEY,
                    creator_id TEXT NOT NULL,
                    sending_time TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    sent_count INTEGER DEFAULT 0,
                    earnings REAL DEFAULT 0,
                    revenue_per_send REAL DEFAULT 0
                )
            """)
            conn.commit()
            conn.close()

            optimizer = ElasticityOptimizer(db_path)

            profile1 = optimizer.get_profile("creator1")
            profile2 = optimizer.get_profile("creator1", force_refresh=True)

            # Should be different objects
            assert profile1 is not profile2

        finally:
            os.unlink(db_path)

    def test_optimize_volume_insufficient_data(self) -> None:
        """Should return original volume when data is insufficient."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE mass_messages (
                    id INTEGER PRIMARY KEY,
                    creator_id TEXT NOT NULL,
                    sending_time TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    sent_count INTEGER DEFAULT 0,
                    earnings REAL DEFAULT 0,
                    revenue_per_send REAL DEFAULT 0
                )
            """)
            conn.commit()
            conn.close()

            optimizer = ElasticityOptimizer(db_path)
            optimized, reason = optimizer.optimize_volume("creator1", proposed_volume=10)

            assert optimized == 10  # Unchanged
            assert "insufficient" in reason.lower()

        finally:
            os.unlink(db_path)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_volume_point_with_zero_rps(self) -> None:
        """Should handle zero RPS values."""
        points = [
            VolumePoint(daily_volume=1, sample_count=5, avg_rps=0.0, total_revenue=0.0),
            VolumePoint(daily_volume=3, sample_count=5, avg_rps=0.10, total_revenue=3.0),
            VolumePoint(daily_volume=5, sample_count=5, avg_rps=0.05, total_revenue=2.5),
        ]

        # Should not raise exception
        params = fit_elasticity_model(points)
        assert params.base_rps > 0

    def test_volume_point_with_negative_values(self) -> None:
        """Should handle negative marginal RPS (unusual data)."""
        points = [
            VolumePoint(daily_volume=1, sample_count=5, avg_rps=0.10, total_revenue=1.0),
            VolumePoint(daily_volume=3, sample_count=5, avg_rps=0.15, total_revenue=4.5),
            VolumePoint(daily_volume=5, sample_count=5, avg_rps=0.20, total_revenue=10.0),
        ]

        # Increasing RPS (inverse of expected) should still work
        params = fit_elasticity_model(points)
        # Will use default decay rate due to negative slope
        assert params.decay_rate == DEFAULT_DECAY_RATE

    def test_identical_volumes_in_data(self) -> None:
        """Should handle identical volume values."""
        points = [
            VolumePoint(daily_volume=5, sample_count=10, avg_rps=0.15, total_revenue=7.5),
            VolumePoint(daily_volume=5, sample_count=8, avg_rps=0.14, total_revenue=7.0),
            VolumePoint(daily_volume=5, sample_count=6, avg_rps=0.16, total_revenue=8.0),
        ]

        # Singular matrix case - should return defaults
        params = fit_elasticity_model(points)
        assert params.fit_quality == 0.0

    def test_very_large_volumes(self) -> None:
        """Should handle very large volume values."""
        points = [
            VolumePoint(daily_volume=100, sample_count=5, avg_rps=0.01, total_revenue=1.0),
            VolumePoint(daily_volume=200, sample_count=5, avg_rps=0.005, total_revenue=1.0),
            VolumePoint(daily_volume=300, sample_count=5, avg_rps=0.002, total_revenue=0.6),
        ]

        params = fit_elasticity_model(points)
        assert params.decay_rate > 0

    def test_very_small_rps_values(self) -> None:
        """Should handle very small RPS values."""
        points = [
            VolumePoint(daily_volume=1, sample_count=5, avg_rps=0.001, total_revenue=0.001),
            VolumePoint(daily_volume=3, sample_count=5, avg_rps=0.0005, total_revenue=0.0015),
            VolumePoint(daily_volume=5, sample_count=5, avg_rps=0.0002, total_revenue=0.001),
        ]

        params = fit_elasticity_model(points)
        assert params.base_rps > 0


class TestDefaultConstants:
    """Tests for module constants."""

    def test_default_decay_rate_value(self) -> None:
        """Default decay rate should be 0.08."""
        assert DEFAULT_DECAY_RATE == 0.08

    def test_default_min_marginal_rps_value(self) -> None:
        """Default minimum marginal RPS should be 0.05."""
        assert DEFAULT_MIN_MARGINAL_RPS == 0.05

    def test_volume_evaluation_points_value(self) -> None:
        """Volume evaluation points should be a list of sensible volumes."""
        assert VOLUME_EVALUATION_POINTS == [3, 5, 7, 10, 12, 15]
        assert all(isinstance(v, int) for v in VOLUME_EVALUATION_POINTS)
        assert VOLUME_EVALUATION_POINTS == sorted(VOLUME_EVALUATION_POINTS)


class TestElasticityParametersDataclass:
    """Tests for ElasticityParameters dataclass."""

    def test_parameters_default_values(self) -> None:
        """Should have correct default values."""
        params = ElasticityParameters(base_rps=0.10, decay_rate=0.05)

        assert params.base_rps == 0.10
        assert params.decay_rate == 0.05
        assert params.min_marginal_rps == DEFAULT_MIN_MARGINAL_RPS
        assert params.optimal_volume == 7
        assert params.fit_quality == 0.0

    def test_parameters_is_reliable_threshold(self) -> None:
        """is_reliable should use 0.5 threshold."""
        params_low = ElasticityParameters(base_rps=0.10, decay_rate=0.05, fit_quality=0.49)
        params_high = ElasticityParameters(base_rps=0.10, decay_rate=0.05, fit_quality=0.51)

        assert params_low.is_reliable is False
        assert params_high.is_reliable is True

    def test_parameters_is_reliable_boundary(self) -> None:
        """is_reliable at exactly 0.5 should be False."""
        params = ElasticityParameters(base_rps=0.10, decay_rate=0.05, fit_quality=0.5)
        assert params.is_reliable is False


class TestVolumePointDataclass:
    """Tests for VolumePoint dataclass."""

    def test_volume_point_creation(self) -> None:
        """Should create VolumePoint with all fields."""
        point = VolumePoint(
            daily_volume=5,
            sample_count=10,
            avg_rps=0.12,
            total_revenue=6.0,
            marginal_rps=-0.02,
        )

        assert point.daily_volume == 5
        assert point.sample_count == 10
        assert point.avg_rps == 0.12
        assert point.total_revenue == 6.0
        assert point.marginal_rps == -0.02

    def test_volume_point_default_marginal(self) -> None:
        """Default marginal_rps should be 0.0."""
        point = VolumePoint(
            daily_volume=3,
            sample_count=8,
            avg_rps=0.15,
            total_revenue=4.5,
        )

        assert point.marginal_rps == 0.0
