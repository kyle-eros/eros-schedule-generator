"""
Unit tests for multi-horizon score fusion.

Tests cover:
1. Divergence detection at various thresholds
2. Weight selection with all data available
3. Weight redistribution when periods missing
4. Score fusion calculation
5. Confidence scoring based on data quality
6. Edge cases (all periods missing, single period only)
7. Database fetch operations (mocked)
8. MultiHorizonAnalyzer class functionality

Use pytest parametrize for boundary testing.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.exceptions import DatabaseError
from python.volume.multi_horizon import (
    DEFAULT_WEIGHTS,
    DIVERGENCE_THRESHOLD,
    RAPID_CHANGE_WEIGHTS,
    VALID_PERIODS,
    FusedScores,
    HorizonScores,
    MultiHorizonAnalyzer,
    detect_divergence,
    fetch_horizon_scores,
    fuse_scores,
    select_weights,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def all_horizons_available() -> Dict[str, HorizonScores]:
    """All three horizons with data available and typical scores."""
    return {
        '7d': HorizonScores(
            period='7d',
            saturation_score=60.0,
            opportunity_score=55.0,
            message_count=20,
            avg_revenue_per_send=5.50,
            tracking_date="2025-12-15",
            is_available=True,
        ),
        '14d': HorizonScores(
            period='14d',
            saturation_score=55.0,
            opportunity_score=50.0,
            message_count=45,
            avg_revenue_per_send=5.25,
            tracking_date="2025-12-15",
            is_available=True,
        ),
        '30d': HorizonScores(
            period='30d',
            saturation_score=50.0,
            opportunity_score=45.0,
            message_count=100,
            avg_revenue_per_send=5.00,
            tracking_date="2025-12-15",
            is_available=True,
        ),
    }


@pytest.fixture
def divergent_horizons() -> Dict[str, HorizonScores]:
    """Horizons with significant 7d/30d divergence (>15 points)."""
    return {
        '7d': HorizonScores(
            period='7d',
            saturation_score=75.0,  # 20 points higher than 30d
            opportunity_score=60.0,
            message_count=15,
            avg_revenue_per_send=4.50,
            tracking_date="2025-12-15",
            is_available=True,
        ),
        '14d': HorizonScores(
            period='14d',
            saturation_score=65.0,
            opportunity_score=55.0,
            message_count=35,
            avg_revenue_per_send=4.75,
            tracking_date="2025-12-15",
            is_available=True,
        ),
        '30d': HorizonScores(
            period='30d',
            saturation_score=55.0,
            opportunity_score=50.0,
            message_count=80,
            avg_revenue_per_send=5.00,
            tracking_date="2025-12-15",
            is_available=True,
        ),
    }


@pytest.fixture
def only_14d_available() -> Dict[str, HorizonScores]:
    """Only 14d horizon with data available."""
    return {
        '7d': HorizonScores(period='7d', is_available=False),
        '14d': HorizonScores(
            period='14d',
            saturation_score=60.0,
            opportunity_score=55.0,
            message_count=40,
            is_available=True,
        ),
        '30d': HorizonScores(period='30d', is_available=False),
    }


@pytest.fixture
def no_horizons_available() -> Dict[str, HorizonScores]:
    """No horizons with data available."""
    return {
        '7d': HorizonScores(period='7d', is_available=False),
        '14d': HorizonScores(period='14d', is_available=False),
        '30d': HorizonScores(period='30d', is_available=False),
    }


@pytest.fixture
def low_message_count_horizons() -> Dict[str, HorizonScores]:
    """Horizons with very low message counts."""
    return {
        '7d': HorizonScores(
            period='7d',
            saturation_score=60.0,
            opportunity_score=55.0,
            message_count=2,
            is_available=True,
        ),
        '14d': HorizonScores(
            period='14d',
            saturation_score=55.0,
            opportunity_score=50.0,
            message_count=4,
            is_available=True,
        ),
        '30d': HorizonScores(
            period='30d',
            saturation_score=50.0,
            opportunity_score=45.0,
            message_count=3,
            is_available=True,
        ),
    }


# =============================================================================
# Test HorizonScores Dataclass
# =============================================================================


class TestHorizonScores:
    """Tests for HorizonScores dataclass."""

    def test_valid_period_7d(self) -> None:
        """7d is a valid period."""
        scores = HorizonScores(period='7d')
        assert scores.period == '7d'

    def test_valid_period_14d(self) -> None:
        """14d is a valid period."""
        scores = HorizonScores(period='14d')
        assert scores.period == '14d'

    def test_valid_period_30d(self) -> None:
        """30d is a valid period."""
        scores = HorizonScores(period='30d')
        assert scores.period == '30d'

    def test_invalid_period_raises(self) -> None:
        """Invalid period should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid period"):
            HorizonScores(period='10d')

    def test_default_values(self) -> None:
        """Default values should be sensible."""
        scores = HorizonScores(period='7d')
        assert scores.saturation_score == 50.0
        assert scores.opportunity_score == 50.0
        assert scores.message_count == 0
        assert scores.avg_revenue_per_send == 0.0
        assert scores.tracking_date == ""
        assert scores.is_available is False

    def test_custom_values(self) -> None:
        """Custom values should be preserved."""
        scores = HorizonScores(
            period='14d',
            saturation_score=75.0,
            opportunity_score=65.0,
            message_count=50,
            avg_revenue_per_send=6.50,
            tracking_date="2025-12-15",
            is_available=True,
        )
        assert scores.saturation_score == 75.0
        assert scores.opportunity_score == 65.0
        assert scores.message_count == 50
        assert scores.avg_revenue_per_send == 6.50
        assert scores.tracking_date == "2025-12-15"
        assert scores.is_available is True


# =============================================================================
# Test FusedScores Dataclass
# =============================================================================


class TestFusedScores:
    """Tests for FusedScores dataclass."""

    def test_is_reliable_with_high_confidence(self) -> None:
        """is_reliable should be True with high confidence and good quality."""
        fused = FusedScores(
            saturation_score=60.0,
            opportunity_score=55.0,
            weights_used={'7d': 0.3, '14d': 0.5, '30d': 0.2},
            confidence=0.8,
            data_quality="good",
        )
        assert fused.is_reliable is True

    def test_is_reliable_with_low_confidence(self) -> None:
        """is_reliable should be False with low confidence."""
        fused = FusedScores(
            saturation_score=60.0,
            opportunity_score=55.0,
            weights_used={'7d': 0.0, '14d': 1.0, '30d': 0.0},
            confidence=0.3,
            data_quality="limited",
        )
        assert fused.is_reliable is False

    def test_is_reliable_with_insufficient_quality(self) -> None:
        """is_reliable should be False with insufficient data quality."""
        fused = FusedScores(
            saturation_score=50.0,
            opportunity_score=50.0,
            weights_used={'7d': 0.0, '14d': 1.0, '30d': 0.0},
            confidence=0.6,
            data_quality="insufficient",
        )
        assert fused.is_reliable is False

    def test_is_reliable_boundary_confidence_0_5(self) -> None:
        """is_reliable should be True at confidence boundary 0.5."""
        fused = FusedScores(
            saturation_score=60.0,
            opportunity_score=55.0,
            weights_used={'7d': 0.3, '14d': 0.5, '30d': 0.2},
            confidence=0.5,
            data_quality="good",
        )
        assert fused.is_reliable is True

    def test_is_trending_up_decreasing_direction(self) -> None:
        """is_trending_up should be True when direction is decreasing."""
        fused = FusedScores(
            saturation_score=45.0,
            opportunity_score=60.0,
            weights_used={'7d': 0.3, '14d': 0.5, '30d': 0.2},
            divergence_detected=True,
            divergence_direction="decreasing",
            data_quality="good",
        )
        assert fused.is_trending_up is True
        assert fused.is_trending_down is False

    def test_is_trending_down_increasing_direction(self) -> None:
        """is_trending_down should be True when direction is increasing."""
        fused = FusedScores(
            saturation_score=70.0,
            opportunity_score=40.0,
            weights_used={'7d': 0.3, '14d': 0.5, '30d': 0.2},
            divergence_detected=True,
            divergence_direction="increasing",
            data_quality="good",
        )
        assert fused.is_trending_down is True
        assert fused.is_trending_up is False

    def test_stable_direction_neither_trending(self) -> None:
        """Stable direction should return False for both trend properties."""
        fused = FusedScores(
            saturation_score=50.0,
            opportunity_score=50.0,
            weights_used={'7d': 0.3, '14d': 0.5, '30d': 0.2},
            divergence_detected=False,
            divergence_direction="stable",
            data_quality="good",
        )
        assert fused.is_trending_up is False
        assert fused.is_trending_down is False


# =============================================================================
# Test Divergence Detection
# =============================================================================


class TestDetectDivergence:
    """Tests for detect_divergence function."""

    def test_no_divergence_within_threshold(self) -> None:
        """Scores within threshold should not trigger divergence."""
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=60.0,
            opportunity_score=55.0,
            is_available=True,
        )
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=50.0,  # 10 points difference < 15 threshold
            opportunity_score=45.0,  # 10 points difference
            is_available=True,
        )
        is_divergent, amount, direction = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is False
        assert amount == 10.0
        assert direction == "stable"

    def test_divergence_at_exact_threshold(self) -> None:
        """Divergence exactly at threshold should trigger."""
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=65.0,
            opportunity_score=50.0,
            is_available=True,
        )
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=50.0,  # Exactly 15 points difference
            opportunity_score=50.0,
            is_available=True,
        )
        is_divergent, amount, direction = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is True
        assert amount == 15.0
        assert direction == "increasing"  # 7d saturation > 30d

    def test_divergence_above_threshold(self) -> None:
        """Divergence above threshold should trigger."""
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=75.0,
            opportunity_score=60.0,
            is_available=True,
        )
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=50.0,  # 25 points difference
            opportunity_score=55.0,
            is_available=True,
        )
        is_divergent, amount, direction = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is True
        assert amount == 25.0
        assert direction == "increasing"  # 7d saturation > 30d

    def test_divergence_uses_max_of_sat_and_opp(self) -> None:
        """Should use maximum of saturation and opportunity divergence."""
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=55.0,  # 5 point difference
            opportunity_score=75.0,  # 20 point difference
            is_available=True,
        )
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=50.0,
            opportunity_score=55.0,
            is_available=True,
        )
        is_divergent, amount, direction = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is True
        assert amount == 20.0  # Max of (5, 20)
        assert direction == "increasing"  # 7d saturation > 30d (small positive diff)

    def test_no_divergence_when_7d_unavailable(self) -> None:
        """No divergence detection when 7d data unavailable."""
        scores_7d = HorizonScores(period='7d', is_available=False)
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=50.0,
            is_available=True,
        )
        is_divergent, amount, direction = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is False
        assert amount == 0.0
        assert direction == "stable"

    def test_no_divergence_when_30d_unavailable(self) -> None:
        """No divergence detection when 30d data unavailable."""
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=75.0,
            is_available=True,
        )
        scores_30d = HorizonScores(period='30d', is_available=False)
        is_divergent, amount, direction = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is False
        assert amount == 0.0
        assert direction == "stable"

    def test_custom_threshold(self) -> None:
        """Custom threshold should be respected."""
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=60.0,
            is_available=True,
        )
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=50.0,  # 10 point difference
            is_available=True,
        )
        # With default threshold (15), not divergent
        is_div_default, _, direction_default = detect_divergence(scores_7d, scores_30d)
        assert is_div_default is False
        assert direction_default == "stable"
        # With lower threshold (5), divergent
        is_div_low, _, direction_low = detect_divergence(scores_7d, scores_30d, threshold=5.0)
        assert is_div_low is True
        assert direction_low == "increasing"

    @pytest.mark.parametrize(
        "sat_7d,sat_30d,expected_divergent",
        [
            (50.0, 50.0, False),    # No difference
            (55.0, 50.0, False),    # 5 point difference
            (60.0, 50.0, False),    # 10 point difference
            (64.9, 50.0, False),    # Just under threshold
            (65.0, 50.0, True),     # Exactly at threshold
            (70.0, 50.0, True),     # Above threshold
            (100.0, 50.0, True),    # Maximum difference
            (50.0, 70.0, True),     # Reverse direction
        ],
    )
    def test_divergence_parametrized(
        self,
        sat_7d: float,
        sat_30d: float,
        expected_divergent: bool,
    ) -> None:
        """Parametrized boundary tests for divergence detection."""
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=sat_7d,
            opportunity_score=50.0,
            is_available=True,
        )
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=sat_30d,
            opportunity_score=50.0,
            is_available=True,
        )
        is_divergent, _, _ = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is expected_divergent


# =============================================================================
# Test Weight Selection
# =============================================================================


class TestSelectWeights:
    """Tests for select_weights function."""

    def test_default_weights_all_available(self) -> None:
        """All periods available, no divergence -> default weights."""
        data_availability = {'7d': True, '14d': True, '30d': True}
        weights = select_weights(divergence_detected=False, data_availability=data_availability)
        assert weights == DEFAULT_WEIGHTS

    def test_rapid_change_weights_on_divergence(self) -> None:
        """Divergence detected -> rapid change weights."""
        data_availability = {'7d': True, '14d': True, '30d': True}
        weights = select_weights(divergence_detected=True, data_availability=data_availability)
        assert weights == RAPID_CHANGE_WEIGHTS

    def test_redistribute_when_7d_missing(self) -> None:
        """Missing 7d should redistribute its weight to available periods."""
        data_availability = {'7d': False, '14d': True, '30d': True}
        weights = select_weights(divergence_detected=False, data_availability=data_availability)

        # 7d weight (0.30) should be redistributed to 14d and 30d
        assert weights['7d'] == 0.0
        assert weights['14d'] > DEFAULT_WEIGHTS['14d']
        assert weights['30d'] > DEFAULT_WEIGHTS['30d']
        # Should still sum to 1.0
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_redistribute_when_30d_missing(self) -> None:
        """Missing 30d should redistribute its weight."""
        data_availability = {'7d': True, '14d': True, '30d': False}
        weights = select_weights(divergence_detected=False, data_availability=data_availability)

        assert weights['30d'] == 0.0
        assert weights['7d'] > DEFAULT_WEIGHTS['7d']
        assert weights['14d'] > DEFAULT_WEIGHTS['14d']
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_only_14d_available(self) -> None:
        """Only 14d available -> 14d gets 100% weight."""
        data_availability = {'7d': False, '14d': True, '30d': False}
        weights = select_weights(divergence_detected=False, data_availability=data_availability)

        assert weights['7d'] == 0.0
        assert weights['14d'] == 1.0
        assert weights['30d'] == 0.0

    def test_only_7d_available(self) -> None:
        """Only 7d available -> 7d gets 100% weight."""
        data_availability = {'7d': True, '14d': False, '30d': False}
        weights = select_weights(divergence_detected=False, data_availability=data_availability)

        assert weights['7d'] == 1.0
        assert weights['14d'] == 0.0
        assert weights['30d'] == 0.0

    def test_no_data_available(self) -> None:
        """No data available -> 14d default fallback."""
        data_availability = {'7d': False, '14d': False, '30d': False}
        weights = select_weights(divergence_detected=False, data_availability=data_availability)

        assert weights == {'7d': 0.0, '14d': 1.0, '30d': 0.0}

    def test_weights_sum_to_one(self) -> None:
        """Weights should always sum to 1.0."""
        test_cases = [
            {'7d': True, '14d': True, '30d': True},
            {'7d': False, '14d': True, '30d': True},
            {'7d': True, '14d': False, '30d': True},
            {'7d': True, '14d': True, '30d': False},
            {'7d': False, '14d': False, '30d': True},
            {'7d': False, '14d': True, '30d': False},
            {'7d': True, '14d': False, '30d': False},
            {'7d': False, '14d': False, '30d': False},
        ]
        for data_availability in test_cases:
            for divergence in [True, False]:
                weights = select_weights(
                    divergence_detected=divergence,
                    data_availability=data_availability,
                )
                total = sum(weights.values())
                assert abs(total - 1.0) < 0.001, (
                    f"Weights sum to {total} for {data_availability}, divergence={divergence}"
                )


# =============================================================================
# Test Score Fusion
# =============================================================================


class TestFuseScores:
    """Tests for fuse_scores function."""

    def test_basic_fusion_all_available(
        self,
        all_horizons_available: Dict[str, HorizonScores],
    ) -> None:
        """Basic fusion with all horizons available."""
        result = fuse_scores(all_horizons_available)

        # Weighted average: 60*0.3 + 55*0.5 + 50*0.2 = 18 + 27.5 + 10 = 55.5
        assert result.saturation_score == 55.5
        # Weighted average: 55*0.3 + 50*0.5 + 45*0.2 = 16.5 + 25 + 9 = 50.5
        assert result.opportunity_score == 50.5
        assert result.divergence_detected is False
        assert result.confidence > 0.5
        assert result.data_quality == "excellent"

    def test_fusion_with_divergence(
        self,
        divergent_horizons: Dict[str, HorizonScores],
    ) -> None:
        """Fusion with divergent horizons should use rapid change weights."""
        result = fuse_scores(divergent_horizons)

        assert result.divergence_detected is True
        assert result.divergence_amount == 20.0  # 75 - 55
        # With rapid change weights: 7d gets 0.5, 14d gets 0.35, 30d gets 0.15
        assert result.weights_used == RAPID_CHANGE_WEIGHTS

    def test_fusion_single_horizon(
        self,
        only_14d_available: Dict[str, HorizonScores],
    ) -> None:
        """Fusion with single horizon should use that horizon's scores."""
        result = fuse_scores(only_14d_available)

        assert result.saturation_score == 60.0
        assert result.opportunity_score == 55.0
        assert result.weights_used['14d'] == 1.0
        assert result.data_quality in ["limited", "good"]

    def test_fusion_no_horizons(
        self,
        no_horizons_available: Dict[str, HorizonScores],
    ) -> None:
        """Fusion with no horizons should return defaults."""
        result = fuse_scores(no_horizons_available)

        assert result.saturation_score == 50.0
        assert result.opportunity_score == 50.0
        assert result.confidence < 0.5
        assert result.data_quality == "insufficient"
        assert result.is_reliable is False

    def test_fusion_low_message_count(
        self,
        low_message_count_horizons: Dict[str, HorizonScores],
    ) -> None:
        """Low message count should reduce confidence."""
        result = fuse_scores(low_message_count_horizons)

        # Total messages: 2 + 4 + 3 = 9 (< 10)
        # Confidence: 3 horizons available = 1.0, then * 0.5 for < 10 messages = 0.5
        assert result.confidence <= 0.5
        assert result.data_quality in ["limited", "insufficient"]

    def test_invalid_period_key_raises(self) -> None:
        """Invalid period key should raise ValueError."""
        invalid_horizons = {
            '10d': HorizonScores(period='7d'),  # Key doesn't match period
        }
        with pytest.raises(ValueError, match="Invalid period key"):
            fuse_scores(invalid_horizons)

    def test_data_quality_excellent(self) -> None:
        """Data quality should be excellent with all data and high message count."""
        horizons = {
            '7d': HorizonScores(period='7d', message_count=15, is_available=True),
            '14d': HorizonScores(period='14d', message_count=25, is_available=True),
            '30d': HorizonScores(period='30d', message_count=50, is_available=True),
        }
        result = fuse_scores(horizons)
        assert result.data_quality == "excellent"

    def test_data_quality_good(self) -> None:
        """Data quality should be good with 2+ horizons and 10+ messages."""
        horizons = {
            '7d': HorizonScores(period='7d', is_available=False),
            '14d': HorizonScores(period='14d', message_count=15, is_available=True),
            '30d': HorizonScores(period='30d', message_count=10, is_available=True),
        }
        result = fuse_scores(horizons)
        assert result.data_quality == "good"

    def test_data_quality_limited(self) -> None:
        """Data quality should be limited with 1 horizon and 5+ messages."""
        horizons = {
            '7d': HorizonScores(period='7d', is_available=False),
            '14d': HorizonScores(period='14d', message_count=8, is_available=True),
            '30d': HorizonScores(period='30d', is_available=False),
        }
        result = fuse_scores(horizons)
        assert result.data_quality == "limited"

    def test_data_quality_insufficient(self) -> None:
        """Data quality should be insufficient with no good data."""
        horizons = {
            '7d': HorizonScores(period='7d', is_available=False),
            '14d': HorizonScores(period='14d', message_count=2, is_available=True),
            '30d': HorizonScores(period='30d', is_available=False),
        }
        result = fuse_scores(horizons)
        assert result.data_quality in ["limited", "insufficient"]


# =============================================================================
# Test Database Fetch
# =============================================================================


class TestFetchHorizonScores:
    """Tests for fetch_horizon_scores function."""

    @pytest.fixture
    def mock_db_connection(self) -> MagicMock:
        """Mock database connection."""
        mock_conn = MagicMock(spec=sqlite3.Connection)
        return mock_conn

    def test_fetch_all_periods(self, mock_db_connection: MagicMock) -> None:
        """Should return scores for all periods when data exists."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('7d', 60.0, 55.0, 20, 5.50, '2025-12-15'),
            ('14d', 55.0, 50.0, 45, 5.25, '2025-12-15'),
            ('30d', 50.0, 45.0, 100, 5.00, '2025-12-15'),
        ]
        mock_db_connection.execute.return_value = mock_cursor

        result = fetch_horizon_scores(mock_db_connection, 'alexia')

        assert '7d' in result
        assert '14d' in result
        assert '30d' in result
        assert result['7d'].is_available is True
        assert result['7d'].saturation_score == 60.0
        assert result['14d'].is_available is True
        assert result['30d'].is_available is True

    def test_fetch_partial_periods(self, mock_db_connection: MagicMock) -> None:
        """Should handle partial data availability."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('14d', 55.0, 50.0, 45, 5.25, '2025-12-15'),
        ]
        mock_db_connection.execute.return_value = mock_cursor

        result = fetch_horizon_scores(mock_db_connection, 'alexia')

        assert result['14d'].is_available is True
        assert result['7d'].is_available is False
        assert result['30d'].is_available is False

    def test_fetch_no_data(self, mock_db_connection: MagicMock) -> None:
        """Should return default scores when no data exists."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db_connection.execute.return_value = mock_cursor

        result = fetch_horizon_scores(mock_db_connection, 'new_creator')

        assert result['7d'].is_available is False
        assert result['14d'].is_available is False
        assert result['30d'].is_available is False
        # Default scores should be 50
        assert result['14d'].saturation_score == 50.0

    def test_fetch_handles_null_values(self, mock_db_connection: MagicMock) -> None:
        """Should handle NULL values from database gracefully."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('14d', None, None, None, None, None),
        ]
        mock_db_connection.execute.return_value = mock_cursor

        result = fetch_horizon_scores(mock_db_connection, 'alexia')

        assert result['14d'].is_available is True
        assert result['14d'].saturation_score == 50.0
        assert result['14d'].opportunity_score == 50.0
        assert result['14d'].message_count == 0
        assert result['14d'].avg_revenue_per_send == 0.0
        assert result['14d'].tracking_date == ""

    def test_fetch_database_error(self, mock_db_connection: MagicMock) -> None:
        """Should raise DatabaseError on query failure."""
        mock_db_connection.execute.side_effect = sqlite3.Error("Connection failed")

        with pytest.raises(DatabaseError) as exc_info:
            fetch_horizon_scores(mock_db_connection, 'alexia')

        assert "Failed to fetch horizon scores" in str(exc_info.value)


# =============================================================================
# Test MultiHorizonAnalyzer
# =============================================================================


class TestMultiHorizonAnalyzer:
    """Tests for MultiHorizonAnalyzer class."""

    def test_init(self) -> None:
        """Analyzer should store db_path."""
        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        assert analyzer.db_path == "/path/to/db.sqlite"

    @patch('python.volume.multi_horizon.sqlite3.connect')
    @patch('python.volume.multi_horizon.fetch_horizon_scores')
    def test_analyze_returns_fused_scores(
        self,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        """analyze() should return FusedScores."""
        mock_fetch.return_value = {
            '7d': HorizonScores(period='7d', saturation_score=60, is_available=True),
            '14d': HorizonScores(period='14d', saturation_score=55, is_available=True),
            '30d': HorizonScores(period='30d', saturation_score=50, is_available=True),
        }

        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        result = analyzer.analyze("alexia")

        assert isinstance(result, FusedScores)
        mock_connect.assert_called_once_with("/path/to/db.sqlite")

    def test_get_recommendation_insufficient_data(self) -> None:
        """Should return default message for insufficient data."""
        fused = FusedScores(
            saturation_score=50.0,
            opportunity_score=50.0,
            weights_used={'7d': 0.0, '14d': 1.0, '30d': 0.0},
            data_quality="insufficient",
        )
        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        rec = analyzer.get_recommendation(fused)
        assert "Insufficient data" in rec

    def test_get_recommendation_rapid_saturation_increase(self) -> None:
        """Should detect rapid saturation increase."""
        fused = FusedScores(
            saturation_score=70.0,
            opportunity_score=50.0,
            weights_used=RAPID_CHANGE_WEIGHTS,
            divergence_detected=True,
            horizons={
                '7d': HorizonScores(period='7d', saturation_score=75, is_available=True),
                '30d': HorizonScores(period='30d', saturation_score=55, is_available=True),
            },
            data_quality="good",
        )
        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        rec = analyzer.get_recommendation(fused)
        assert "reducing volume" in rec.lower()

    def test_get_recommendation_recent_improvement(self) -> None:
        """Should detect recent improvement."""
        fused = FusedScores(
            saturation_score=45.0,
            opportunity_score=60.0,
            weights_used=RAPID_CHANGE_WEIGHTS,
            divergence_detected=True,
            horizons={
                '7d': HorizonScores(period='7d', saturation_score=40, is_available=True),
                '30d': HorizonScores(period='30d', saturation_score=60, is_available=True),
            },
            data_quality="good",
        )
        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        rec = analyzer.get_recommendation(fused)
        assert "increasing volume" in rec.lower()

    def test_get_recommendation_high_saturation(self) -> None:
        """Should recommend reducing volume for high saturation."""
        fused = FusedScores(
            saturation_score=75.0,
            opportunity_score=40.0,
            weights_used=DEFAULT_WEIGHTS,
            data_quality="good",
        )
        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        rec = analyzer.get_recommendation(fused)
        assert "reduce volume" in rec.lower()

    def test_get_recommendation_high_opportunity_low_saturation(self) -> None:
        """Should recommend increasing volume for high opportunity with low saturation."""
        fused = FusedScores(
            saturation_score=40.0,
            opportunity_score=75.0,
            weights_used=DEFAULT_WEIGHTS,
            data_quality="good",
        )
        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        rec = analyzer.get_recommendation(fused)
        assert "increase volume" in rec.lower()

    def test_get_recommendation_balanced(self) -> None:
        """Should recommend maintaining volume for balanced scores."""
        fused = FusedScores(
            saturation_score=50.0,
            opportunity_score=50.0,
            weights_used=DEFAULT_WEIGHTS,
            data_quality="good",
        )
        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        rec = analyzer.get_recommendation(fused)
        assert "maintain" in rec.lower()

    @patch('python.volume.multi_horizon.sqlite3.connect')
    @patch('python.volume.multi_horizon.fetch_horizon_scores')
    def test_analyze_with_recommendation(
        self,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        """analyze_with_recommendation() should return both."""
        mock_fetch.return_value = {
            '7d': HorizonScores(period='7d', saturation_score=50, is_available=True),
            '14d': HorizonScores(period='14d', saturation_score=50, is_available=True),
            '30d': HorizonScores(period='30d', saturation_score=50, is_available=True),
        }

        analyzer = MultiHorizonAnalyzer("/path/to/db.sqlite")
        fused, rec = analyzer.analyze_with_recommendation("alexia")

        assert isinstance(fused, FusedScores)
        assert isinstance(rec, str)
        assert len(rec) > 0


# =============================================================================
# Test Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_default_weights_sum_to_one(self) -> None:
        """Default weights should sum to 1.0."""
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.001

    def test_rapid_change_weights_sum_to_one(self) -> None:
        """Rapid change weights should sum to 1.0."""
        assert abs(sum(RAPID_CHANGE_WEIGHTS.values()) - 1.0) < 0.001

    def test_default_weights_structure(self) -> None:
        """Default weights should have expected structure."""
        assert '7d' in DEFAULT_WEIGHTS
        assert '14d' in DEFAULT_WEIGHTS
        assert '30d' in DEFAULT_WEIGHTS
        assert DEFAULT_WEIGHTS['14d'] > DEFAULT_WEIGHTS['7d']
        assert DEFAULT_WEIGHTS['14d'] > DEFAULT_WEIGHTS['30d']

    def test_rapid_change_weights_emphasize_recent(self) -> None:
        """Rapid change weights should emphasize 7d."""
        assert RAPID_CHANGE_WEIGHTS['7d'] > DEFAULT_WEIGHTS['7d']
        assert RAPID_CHANGE_WEIGHTS['7d'] >= RAPID_CHANGE_WEIGHTS['14d']
        assert RAPID_CHANGE_WEIGHTS['30d'] < DEFAULT_WEIGHTS['30d']

    def test_divergence_threshold_positive(self) -> None:
        """Divergence threshold should be positive."""
        assert DIVERGENCE_THRESHOLD > 0

    def test_valid_periods(self) -> None:
        """Valid periods should be the expected set."""
        assert VALID_PERIODS == ('7d', '14d', '30d')


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_extreme_scores_saturation_100(self) -> None:
        """Should handle saturation score of 100."""
        horizons = {
            '7d': HorizonScores(period='7d', saturation_score=100.0, is_available=True),
            '14d': HorizonScores(period='14d', saturation_score=100.0, is_available=True),
            '30d': HorizonScores(period='30d', saturation_score=100.0, is_available=True),
        }
        result = fuse_scores(horizons)
        assert result.saturation_score == 100.0

    def test_extreme_scores_saturation_0(self) -> None:
        """Should handle saturation score of 0."""
        horizons = {
            '7d': HorizonScores(period='7d', saturation_score=0.0, is_available=True),
            '14d': HorizonScores(period='14d', saturation_score=0.0, is_available=True),
            '30d': HorizonScores(period='30d', saturation_score=0.0, is_available=True),
        }
        result = fuse_scores(horizons)
        assert result.saturation_score == 0.0

    def test_divergence_at_boundary_14_99(self) -> None:
        """14.99 point difference should not trigger divergence."""
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=64.99,
            is_available=True,
        )
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=50.0,
            is_available=True,
        )
        is_divergent, amount, direction = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is False
        assert abs(amount - 14.99) < 0.01
        assert direction == "stable"

    def test_empty_horizons_dict(self) -> None:
        """Empty horizons dict should return default scores."""
        result = fuse_scores({})
        assert result.saturation_score == 50.0
        assert result.opportunity_score == 50.0
        assert result.data_quality == "insufficient"

    def test_partial_horizons_dict(self) -> None:
        """Partial horizons dict (missing some keys) should work."""
        horizons = {
            '14d': HorizonScores(
                period='14d',
                saturation_score=65.0,
                opportunity_score=60.0,
                message_count=30,
                is_available=True,
            ),
        }
        result = fuse_scores(horizons)
        assert result.saturation_score == 65.0
        assert result.opportunity_score == 60.0

    def test_high_message_count(self) -> None:
        """Should handle very high message counts."""
        horizons = {
            '7d': HorizonScores(period='7d', message_count=1000, is_available=True),
            '14d': HorizonScores(period='14d', message_count=2000, is_available=True),
            '30d': HorizonScores(period='30d', message_count=5000, is_available=True),
        }
        result = fuse_scores(horizons)
        assert result.data_quality == "excellent"
        assert result.confidence == 1.0

    def test_zero_message_count_all_horizons(self) -> None:
        """Zero message count on all horizons should give low confidence."""
        horizons = {
            '7d': HorizonScores(period='7d', message_count=0, is_available=True),
            '14d': HorizonScores(period='14d', message_count=0, is_available=True),
            '30d': HorizonScores(period='30d', message_count=0, is_available=True),
        }
        result = fuse_scores(horizons)
        assert result.confidence < 1.0

    def test_negative_divergence_direction(self) -> None:
        """Divergence should be detected regardless of direction."""
        # 7d lower than 30d (saturation decreasing = improving performance)
        scores_7d = HorizonScores(
            period='7d',
            saturation_score=40.0,
            is_available=True,
        )
        scores_30d = HorizonScores(
            period='30d',
            saturation_score=60.0,  # 20 points higher
            is_available=True,
        )
        is_divergent, amount, direction = detect_divergence(scores_7d, scores_30d)
        assert is_divergent is True
        assert amount == 20.0
        assert direction == "decreasing"  # 7d saturation < 30d = performance improving
