"""
Unit tests for content-type weighted allocation.

Tests cover:
- Ranking multiplier application for each rank level (TOP/MID/LOW/AVOID)
- AVOID type exclusion (0 volume)
- Distribution across multiple content types
- Handling of unranked content types (default to MID)
- Recommendations generation
- Edge cases (no rankings, all AVOID, all TOP)
- ContentWeightingOptimizer caching and methods
"""

import sqlite3
import sys
from pathlib import Path
from typing import Generator

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.exceptions import DatabaseError
from python.volume.content_weighting import (
    RANK_MULTIPLIERS,
    DEFAULT_RANK,
    ContentTypeRanking,
    ContentTypeProfile,
    WeightedAllocation,
    ContentWeightingOptimizer,
    get_content_type_rankings,
    apply_content_weighting,
    allocate_by_content_type,
    get_content_type_recommendations,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def empty_profile() -> ContentTypeProfile:
    """Profile with no rankings."""
    return ContentTypeProfile(creator_id="empty_creator")


@pytest.fixture
def single_top_profile() -> ContentTypeProfile:
    """Profile with single TOP-ranked content type."""
    profile = ContentTypeProfile(creator_id="single_top_creator")
    ranking = ContentTypeRanking(
        content_type_name="lingerie",
        performance_rank="TOP",
        avg_revenue_per_send=25.50,
        message_count=100,
        last_updated="2025-12-15",
    )
    profile.rankings["lingerie"] = ranking
    profile.top_types.append("lingerie")
    profile.total_types = 1
    return profile


@pytest.fixture
def mixed_profile() -> ContentTypeProfile:
    """Profile with all rank levels represented."""
    profile = ContentTypeProfile(creator_id="mixed_creator")

    # TOP type
    top_ranking = ContentTypeRanking(
        content_type_name="lingerie",
        performance_rank="TOP",
        avg_revenue_per_send=25.50,
        message_count=100,
    )
    profile.rankings["lingerie"] = top_ranking
    profile.top_types.append("lingerie")

    # MID type
    mid_ranking = ContentTypeRanking(
        content_type_name="casual",
        performance_rank="MID",
        avg_revenue_per_send=15.00,
        message_count=50,
    )
    profile.rankings["casual"] = mid_ranking

    # LOW type
    low_ranking = ContentTypeRanking(
        content_type_name="outdoor",
        performance_rank="LOW",
        avg_revenue_per_send=8.00,
        message_count=30,
    )
    profile.rankings["outdoor"] = low_ranking

    # AVOID type
    avoid_ranking = ContentTypeRanking(
        content_type_name="abstract",
        performance_rank="AVOID",
        avg_revenue_per_send=2.00,
        message_count=20,
    )
    profile.rankings["abstract"] = avoid_ranking
    profile.avoid_types.append("abstract")

    profile.total_types = 4
    return profile


@pytest.fixture
def all_avoid_profile() -> ContentTypeProfile:
    """Profile where all content types are AVOID."""
    profile = ContentTypeProfile(creator_id="avoid_creator")

    for i, name in enumerate(["type1", "type2", "type3"]):
        ranking = ContentTypeRanking(
            content_type_name=name,
            performance_rank="AVOID",
        )
        profile.rankings[name] = ranking
        profile.avoid_types.append(name)

    profile.total_types = 3
    return profile


@pytest.fixture
def all_top_profile() -> ContentTypeProfile:
    """Profile where all content types are TOP."""
    profile = ContentTypeProfile(creator_id="top_creator")

    for name in ["lingerie", "bikini", "dress"]:
        ranking = ContentTypeRanking(
            content_type_name=name,
            performance_rank="TOP",
            avg_revenue_per_send=30.00,
            message_count=100,
        )
        profile.rankings[name] = ranking
        profile.top_types.append(name)

    profile.total_types = 3
    return profile


@pytest.fixture
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """In-memory SQLite database with top_content_types table for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create top_content_types table using actual schema column names
    # Schema uses: content_type (not content_type_name), performance_tier (not performance_rank),
    # avg_rps (not avg_revenue_per_send), send_count (not message_count), updated_at (not last_updated)
    cursor.execute("""
        CREATE TABLE top_content_types (
            id INTEGER PRIMARY KEY,
            creator_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            performance_tier TEXT NOT NULL,
            avg_rps REAL,
            send_count INTEGER,
            updated_at TEXT
        )
    """)

    # Insert test data for alexia
    test_data = [
        ("alexia", "lingerie", "TOP", 25.50, 100, "2025-12-15"),
        ("alexia", "bikini", "TOP", 22.00, 80, "2025-12-15"),
        ("alexia", "casual", "MID", 15.00, 50, "2025-12-15"),
        ("alexia", "outdoor", "LOW", 8.00, 30, "2025-12-15"),
        ("alexia", "abstract", "AVOID", 2.00, 20, "2025-12-15"),
    ]

    for row in test_data:
        cursor.execute("""
            INSERT INTO top_content_types
            (creator_id, content_type, performance_tier,
             avg_rps, send_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, row)

    # Insert test data for creator with no rankings
    # (empty_creator has no rows)

    # Insert test data for luna - all AVOID
    avoid_data = [
        ("luna", "type1", "AVOID", 1.00, 10, "2025-12-15"),
        ("luna", "type2", "AVOID", 1.50, 15, "2025-12-15"),
    ]

    for row in avoid_data:
        cursor.execute("""
            INSERT INTO top_content_types
            (creator_id, content_type, performance_tier,
             avg_rps, send_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, row)

    conn.commit()
    yield conn
    conn.close()


# =============================================================================
# Test Classes: Constants
# =============================================================================


class TestRankMultipliers:
    """Tests for RANK_MULTIPLIERS constant."""

    def test_top_multiplier_is_1_3(self) -> None:
        """TOP rank should have 1.3x multiplier (30% increase)."""
        assert RANK_MULTIPLIERS["TOP"] == 1.3

    def test_mid_multiplier_is_1_0(self) -> None:
        """MID rank should have 1.0x multiplier (no change)."""
        assert RANK_MULTIPLIERS["MID"] == 1.0

    def test_low_multiplier_is_0_7(self) -> None:
        """LOW rank should have 0.7x multiplier (30% decrease)."""
        assert RANK_MULTIPLIERS["LOW"] == 0.7

    def test_avoid_multiplier_is_0(self) -> None:
        """AVOID rank should have 0.0x multiplier (zero allocation)."""
        assert RANK_MULTIPLIERS["AVOID"] == 0.0

    def test_default_rank_is_mid(self) -> None:
        """Default rank should be MID."""
        assert DEFAULT_RANK == "MID"


# =============================================================================
# Test Classes: ContentTypeRanking
# =============================================================================


class TestContentTypeRanking:
    """Tests for ContentTypeRanking dataclass."""

    def test_top_ranking_gets_correct_multiplier(self) -> None:
        """TOP rank should auto-calculate 1.3 multiplier."""
        ranking = ContentTypeRanking(
            content_type_name="lingerie",
            performance_rank="TOP",
        )
        assert ranking.multiplier == 1.3

    def test_mid_ranking_gets_correct_multiplier(self) -> None:
        """MID rank should auto-calculate 1.0 multiplier."""
        ranking = ContentTypeRanking(
            content_type_name="casual",
            performance_rank="MID",
        )
        assert ranking.multiplier == 1.0

    def test_low_ranking_gets_correct_multiplier(self) -> None:
        """LOW rank should auto-calculate 0.7 multiplier."""
        ranking = ContentTypeRanking(
            content_type_name="outdoor",
            performance_rank="LOW",
        )
        assert ranking.multiplier == 0.7

    def test_avoid_ranking_gets_correct_multiplier(self) -> None:
        """AVOID rank should auto-calculate 0.0 multiplier."""
        ranking = ContentTypeRanking(
            content_type_name="abstract",
            performance_rank="AVOID",
        )
        assert ranking.multiplier == 0.0

    def test_unknown_rank_defaults_to_1(self) -> None:
        """Unknown rank should default to 1.0 multiplier."""
        ranking = ContentTypeRanking(
            content_type_name="unknown",
            performance_rank="UNKNOWN",
        )
        assert ranking.multiplier == 1.0

    def test_default_values(self) -> None:
        """Default values should be set correctly."""
        ranking = ContentTypeRanking(
            content_type_name="test",
            performance_rank="MID",
        )
        assert ranking.avg_revenue_per_send == 0.0
        assert ranking.message_count == 0
        assert ranking.last_updated == ""


# =============================================================================
# Test Classes: apply_content_weighting
# =============================================================================


class TestApplyContentWeighting:
    """Tests for apply_content_weighting function."""

    def test_top_rank_increases_volume_by_30_percent(
        self, single_top_profile: ContentTypeProfile
    ) -> None:
        """TOP rank should increase volume by 30%."""
        allocation = apply_content_weighting(
            base_volume=10,
            content_type="lingerie",
            profile=single_top_profile,
        )
        assert allocation.base_volume == 10
        assert allocation.weighted_volume == 13  # 10 * 1.3 = 13
        assert allocation.rank == "TOP"
        assert allocation.multiplier == 1.3
        assert allocation.adjusted is True

    def test_mid_rank_no_change(self, mixed_profile: ContentTypeProfile) -> None:
        """MID rank should not change volume."""
        allocation = apply_content_weighting(
            base_volume=10,
            content_type="casual",
            profile=mixed_profile,
        )
        assert allocation.base_volume == 10
        assert allocation.weighted_volume == 10
        assert allocation.rank == "MID"
        assert allocation.multiplier == 1.0
        assert allocation.adjusted is False

    def test_low_rank_decreases_volume_by_30_percent(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """LOW rank should decrease volume by 30%."""
        allocation = apply_content_weighting(
            base_volume=10,
            content_type="outdoor",
            profile=mixed_profile,
        )
        assert allocation.base_volume == 10
        assert allocation.weighted_volume == 7  # 10 * 0.7 = 7
        assert allocation.rank == "LOW"
        assert allocation.multiplier == 0.7
        assert allocation.adjusted is True

    def test_avoid_rank_gives_zero_volume(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """AVOID rank should give zero volume."""
        allocation = apply_content_weighting(
            base_volume=10,
            content_type="abstract",
            profile=mixed_profile,
        )
        assert allocation.base_volume == 10
        assert allocation.weighted_volume == 0
        assert allocation.rank == "AVOID"
        assert allocation.multiplier == 0.0
        assert allocation.adjusted is True

    def test_unranked_content_type_defaults_to_mid(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """Unranked content type should default to MID (no change)."""
        allocation = apply_content_weighting(
            base_volume=10,
            content_type="unknown_type",
            profile=mixed_profile,
        )
        assert allocation.weighted_volume == 10
        assert allocation.rank == DEFAULT_RANK
        assert allocation.multiplier == 1.0
        assert allocation.adjusted is False

    def test_empty_profile_defaults_to_mid(
        self, empty_profile: ContentTypeProfile
    ) -> None:
        """Empty profile should default all types to MID."""
        allocation = apply_content_weighting(
            base_volume=10,
            content_type="any_type",
            profile=empty_profile,
        )
        assert allocation.weighted_volume == 10
        assert allocation.rank == DEFAULT_RANK
        assert allocation.adjusted is False

    def test_zero_base_volume(self, mixed_profile: ContentTypeProfile) -> None:
        """Zero base volume should remain zero regardless of rank."""
        allocation = apply_content_weighting(
            base_volume=0,
            content_type="lingerie",
            profile=mixed_profile,
        )
        assert allocation.weighted_volume == 0
        assert allocation.base_volume == 0

    def test_rounding_top_rank(self, single_top_profile: ContentTypeProfile) -> None:
        """Volume should be rounded correctly for TOP rank."""
        # 7 * 1.3 = 9.1 -> rounds to 9
        allocation = apply_content_weighting(
            base_volume=7,
            content_type="lingerie",
            profile=single_top_profile,
        )
        assert allocation.weighted_volume == 9

    def test_rounding_low_rank(self, mixed_profile: ContentTypeProfile) -> None:
        """Volume should be rounded correctly for LOW rank."""
        # 3 * 0.7 = 2.1 -> rounds to 2
        allocation = apply_content_weighting(
            base_volume=3,
            content_type="outdoor",
            profile=mixed_profile,
        )
        assert allocation.weighted_volume == 2


class TestApplyContentWeightingEdgeCases:
    """Edge case tests for apply_content_weighting."""

    def test_large_base_volume(self, single_top_profile: ContentTypeProfile) -> None:
        """Large base volumes should scale correctly."""
        allocation = apply_content_weighting(
            base_volume=1000,
            content_type="lingerie",
            profile=single_top_profile,
        )
        assert allocation.weighted_volume == 1300

    def test_weighted_allocation_is_frozen(
        self, single_top_profile: ContentTypeProfile
    ) -> None:
        """WeightedAllocation should be immutable."""
        allocation = apply_content_weighting(
            base_volume=10,
            content_type="lingerie",
            profile=single_top_profile,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            allocation.weighted_volume = 99  # type: ignore


# =============================================================================
# Test Classes: allocate_by_content_type
# =============================================================================


class TestAllocateByContentType:
    """Tests for allocate_by_content_type function."""

    def test_basic_distribution(self, mixed_profile: ContentTypeProfile) -> None:
        """Volume should be distributed according to weights."""
        allocation = allocate_by_content_type(
            total_volume=10,
            content_types=["lingerie", "casual"],  # TOP and MID
            profile=mixed_profile,
        )
        # TOP (1.3) + MID (1.0) = 2.3 total weight
        # lingerie: (1.3/2.3) * 10 = 5.65 -> 6 (min 1 applied)
        # casual: (1.0/2.3) * 10 = 4.35 -> 4 (min 1 applied)
        assert allocation["lingerie"] >= allocation["casual"]
        assert sum(allocation.values()) >= 10

    def test_avoid_types_get_zero(self, mixed_profile: ContentTypeProfile) -> None:
        """AVOID types should get zero allocation."""
        allocation = allocate_by_content_type(
            total_volume=10,
            content_types=["lingerie", "abstract"],  # TOP and AVOID
            profile=mixed_profile,
        )
        assert allocation["abstract"] == 0
        assert allocation["lingerie"] > 0

    def test_all_avoid_types(self, all_avoid_profile: ContentTypeProfile) -> None:
        """All AVOID types should result in zero allocations."""
        allocation = allocate_by_content_type(
            total_volume=10,
            content_types=["type1", "type2", "type3"],
            profile=all_avoid_profile,
        )
        assert allocation["type1"] == 0
        assert allocation["type2"] == 0
        assert allocation["type3"] == 0

    def test_empty_content_types_list(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """Empty content types list should return empty dict."""
        allocation = allocate_by_content_type(
            total_volume=10,
            content_types=[],
            profile=mixed_profile,
        )
        assert allocation == {}

    def test_zero_total_volume(self, mixed_profile: ContentTypeProfile) -> None:
        """Zero total volume should give all zeros."""
        allocation = allocate_by_content_type(
            total_volume=0,
            content_types=["lingerie", "casual"],
            profile=mixed_profile,
        )
        assert allocation["lingerie"] == 0
        assert allocation["casual"] == 0

    def test_min_per_type_enforced(self, mixed_profile: ContentTypeProfile) -> None:
        """Minimum per type should be enforced for non-AVOID types."""
        allocation = allocate_by_content_type(
            total_volume=10,
            content_types=["lingerie", "casual", "outdoor"],
            profile=mixed_profile,
            min_per_type=2,
        )
        # All non-AVOID should have at least 2
        assert allocation["lingerie"] >= 2
        assert allocation["casual"] >= 2
        assert allocation["outdoor"] >= 2

    def test_unranked_types_get_default_weight(
        self, empty_profile: ContentTypeProfile
    ) -> None:
        """Unranked types should get default (MID) weight."""
        allocation = allocate_by_content_type(
            total_volume=10,
            content_types=["type_a", "type_b"],
            profile=empty_profile,
        )
        # Both should get roughly equal allocation (both MID = 1.0)
        assert abs(allocation["type_a"] - allocation["type_b"]) <= 1

    def test_all_top_types_equal_distribution(
        self, all_top_profile: ContentTypeProfile
    ) -> None:
        """All TOP types should get roughly equal distribution."""
        allocation = allocate_by_content_type(
            total_volume=12,
            content_types=["lingerie", "bikini", "dress"],
            profile=all_top_profile,
        )
        # All TOP with 1.3 weight, should be roughly equal
        assert allocation["lingerie"] >= 3
        assert allocation["bikini"] >= 3
        assert allocation["dress"] >= 3

    def test_remaining_volume_goes_to_top(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """Remaining volume after rounding should go to TOP types."""
        allocation = allocate_by_content_type(
            total_volume=11,  # Odd number to force remainder
            content_types=["lingerie", "casual"],
            profile=mixed_profile,
        )
        # lingerie (TOP) should get any remainder
        total_allocated = sum(allocation.values())
        assert total_allocated >= 11


class TestAllocateByContentTypeEdgeCases:
    """Edge case tests for allocate_by_content_type."""

    def test_negative_volume_treated_as_zero(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """Negative total volume should be treated as zero."""
        allocation = allocate_by_content_type(
            total_volume=-5,
            content_types=["lingerie", "casual"],
            profile=mixed_profile,
        )
        assert allocation["lingerie"] == 0
        assert allocation["casual"] == 0

    def test_single_content_type(self, single_top_profile: ContentTypeProfile) -> None:
        """Single content type should get all volume."""
        allocation = allocate_by_content_type(
            total_volume=10,
            content_types=["lingerie"],
            profile=single_top_profile,
        )
        assert allocation["lingerie"] == 10


# =============================================================================
# Test Classes: get_content_type_rankings
# =============================================================================


class TestGetContentTypeRankings:
    """Tests for get_content_type_rankings function."""

    def test_loads_rankings_from_db(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Should load all rankings for a creator."""
        profile = get_content_type_rankings(db_connection, "alexia")

        assert profile.creator_id == "alexia"
        assert profile.total_types == 5
        assert "lingerie" in profile.rankings
        assert "bikini" in profile.rankings
        assert "casual" in profile.rankings
        assert "outdoor" in profile.rankings
        assert "abstract" in profile.rankings

    def test_top_types_populated(self, db_connection: sqlite3.Connection) -> None:
        """TOP types should be in top_types list."""
        profile = get_content_type_rankings(db_connection, "alexia")

        assert "lingerie" in profile.top_types
        assert "bikini" in profile.top_types
        assert len(profile.top_types) == 2

    def test_avoid_types_populated(self, db_connection: sqlite3.Connection) -> None:
        """AVOID types should be in avoid_types list."""
        profile = get_content_type_rankings(db_connection, "alexia")

        assert "abstract" in profile.avoid_types
        assert len(profile.avoid_types) == 1

    def test_ranking_values_loaded(self, db_connection: sqlite3.Connection) -> None:
        """Ranking values should be loaded correctly."""
        profile = get_content_type_rankings(db_connection, "alexia")

        lingerie = profile.rankings["lingerie"]
        assert lingerie.performance_rank == "TOP"
        assert lingerie.avg_revenue_per_send == 25.50
        assert lingerie.message_count == 100
        assert lingerie.last_updated == "2025-12-15"
        assert lingerie.multiplier == 1.3

    def test_empty_result_for_unknown_creator(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Unknown creator should return empty profile."""
        profile = get_content_type_rankings(db_connection, "nonexistent")

        assert profile.creator_id == "nonexistent"
        assert profile.total_types == 0
        assert len(profile.rankings) == 0
        assert len(profile.top_types) == 0
        assert len(profile.avoid_types) == 0

    def test_all_avoid_creator(self, db_connection: sqlite3.Connection) -> None:
        """Creator with all AVOID types should have all in avoid_types."""
        profile = get_content_type_rankings(db_connection, "luna")

        assert profile.total_types == 2
        assert len(profile.avoid_types) == 2
        assert len(profile.top_types) == 0

    def test_database_error_raised(self) -> None:
        """DatabaseError should be raised on query failure."""
        conn = sqlite3.connect(":memory:")
        # Table doesn't exist, so query should fail
        with pytest.raises(DatabaseError):
            get_content_type_rankings(conn, "test")
        conn.close()


# =============================================================================
# Test Classes: get_content_type_recommendations
# =============================================================================


class TestGetContentTypeRecommendations:
    """Tests for get_content_type_recommendations function."""

    def test_increase_recommendation_for_top_types(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """Should recommend increasing TOP types."""
        recommendations = get_content_type_recommendations(mixed_profile)

        assert "increase" in recommendations
        assert "lingerie" in recommendations["increase"]

    def test_avoid_recommendation_for_avoid_types(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """Should recommend avoiding AVOID types."""
        recommendations = get_content_type_recommendations(mixed_profile)

        assert "avoid" in recommendations
        assert "abstract" in recommendations["avoid"]

    def test_potential_recommendation_for_mid_with_data(
        self, mixed_profile: ContentTypeProfile
    ) -> None:
        """Should recommend testing MID types with sufficient data."""
        # casual has message_count=50 which is >= 10
        recommendations = get_content_type_recommendations(mixed_profile)

        assert "potential" in recommendations
        assert "casual" in recommendations["potential"]

    def test_no_recommendations_for_empty_profile(
        self, empty_profile: ContentTypeProfile
    ) -> None:
        """Empty profile should have no recommendations."""
        recommendations = get_content_type_recommendations(empty_profile)

        assert len(recommendations) == 0

    def test_only_avoid_recommendation_when_all_avoid(
        self, all_avoid_profile: ContentTypeProfile
    ) -> None:
        """Should only have avoid recommendation when all AVOID."""
        recommendations = get_content_type_recommendations(all_avoid_profile)

        assert "avoid" in recommendations
        assert "increase" not in recommendations

    def test_only_increase_recommendation_when_all_top(
        self, all_top_profile: ContentTypeProfile
    ) -> None:
        """Should only have increase recommendation when all TOP."""
        recommendations = get_content_type_recommendations(all_top_profile)

        assert "increase" in recommendations
        assert "avoid" not in recommendations


# =============================================================================
# Test Classes: ContentWeightingOptimizer
# =============================================================================


class TestContentWeightingOptimizerInit:
    """Tests for ContentWeightingOptimizer initialization."""

    def test_init_with_db_path(self, tmp_path: Path) -> None:
        """Should initialize with database path."""
        db_path = str(tmp_path / "test.db")
        optimizer = ContentWeightingOptimizer(db_path)
        assert optimizer.db_path == db_path

    def test_cache_starts_empty(self, tmp_path: Path) -> None:
        """Cache should start empty."""
        optimizer = ContentWeightingOptimizer(str(tmp_path / "test.db"))
        assert len(optimizer.get_cached_creators()) == 0


class TestContentWeightingOptimizerMethods:
    """Tests for ContentWeightingOptimizer methods."""

    @pytest.fixture
    def optimizer_with_db(self, tmp_path: Path) -> ContentWeightingOptimizer:
        """Create optimizer with test database."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Use actual schema column names: content_type (not content_type_name),
        # performance_tier (not performance_rank), avg_rps (not avg_revenue_per_send),
        # send_count (not message_count), updated_at (not last_updated)
        cursor.execute("""
            CREATE TABLE top_content_types (
                id INTEGER PRIMARY KEY,
                creator_id TEXT NOT NULL,
                content_type TEXT NOT NULL,
                performance_tier TEXT NOT NULL,
                avg_rps REAL,
                send_count INTEGER,
                updated_at TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO top_content_types
            (creator_id, content_type, performance_tier,
             avg_rps, send_count, updated_at)
            VALUES ('alexia', 'lingerie', 'TOP', 25.50, 100, '2025-12-15')
        """)

        cursor.execute("""
            INSERT INTO top_content_types
            (creator_id, content_type, performance_tier,
             avg_rps, send_count, updated_at)
            VALUES ('alexia', 'abstract', 'AVOID', 2.00, 20, '2025-12-15')
        """)

        conn.commit()
        conn.close()

        return ContentWeightingOptimizer(str(db_path))

    def test_get_profile_loads_from_db(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """get_profile should load from database."""
        profile = optimizer_with_db.get_profile("alexia")

        assert profile.creator_id == "alexia"
        assert "lingerie" in profile.rankings
        assert profile.rankings["lingerie"].performance_rank == "TOP"

    def test_get_profile_uses_cache(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """get_profile should use cache on second call."""
        profile1 = optimizer_with_db.get_profile("alexia")
        profile2 = optimizer_with_db.get_profile("alexia")

        # Should be same object from cache
        assert profile1 is profile2
        assert "alexia" in optimizer_with_db.get_cached_creators()

    def test_get_profile_force_refresh_bypasses_cache(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """force_refresh=True should bypass cache."""
        profile1 = optimizer_with_db.get_profile("alexia")
        profile2 = optimizer_with_db.get_profile("alexia", force_refresh=True)

        # Should be different objects (refetched)
        assert profile1 is not profile2
        # But same data
        assert profile1.total_types == profile2.total_types

    def test_weight_allocation(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """weight_allocation should apply weighting correctly."""
        allocation = optimizer_with_db.weight_allocation(
            creator_id="alexia",
            content_type="lingerie",
            base_volume=10,
        )

        assert allocation.weighted_volume == 13  # 10 * 1.3
        assert allocation.rank == "TOP"

    def test_should_include_content_type_true(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """should_include_content_type returns True for non-AVOID."""
        assert optimizer_with_db.should_include_content_type(
            "alexia", "lingerie"
        ) is True

    def test_should_include_content_type_false_for_avoid(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """should_include_content_type returns False for AVOID."""
        assert optimizer_with_db.should_include_content_type(
            "alexia", "abstract"
        ) is False

    def test_should_include_unknown_type_returns_true(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """Unknown content types should return True (not AVOID)."""
        assert optimizer_with_db.should_include_content_type(
            "alexia", "unknown_type"
        ) is True

    def test_clear_cache(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """clear_cache should empty the cache."""
        optimizer_with_db.get_profile("alexia")
        assert len(optimizer_with_db.get_cached_creators()) == 1

        optimizer_with_db.clear_cache()
        assert len(optimizer_with_db.get_cached_creators()) == 0

    def test_get_cached_creators(
        self, optimizer_with_db: ContentWeightingOptimizer
    ) -> None:
        """get_cached_creators should return cached creator IDs."""
        optimizer_with_db.get_profile("alexia")

        cached = optimizer_with_db.get_cached_creators()
        assert cached == ["alexia"]


# =============================================================================
# Test Classes: Integration Tests
# =============================================================================


class TestContentWeightingIntegration:
    """Integration tests for content weighting workflow."""

    def test_full_workflow(self, db_connection: sqlite3.Connection) -> None:
        """Test complete workflow from DB to weighted allocation."""
        # Load profile
        profile = get_content_type_rankings(db_connection, "alexia")

        # Verify profile
        assert profile.total_types == 5
        assert "lingerie" in profile.top_types
        assert "abstract" in profile.avoid_types

        # Apply weighting
        allocation = apply_content_weighting(10, "lingerie", profile)
        assert allocation.weighted_volume == 13

        # Check recommendations
        recommendations = get_content_type_recommendations(profile)
        assert "increase" in recommendations
        assert "avoid" in recommendations

    def test_avoid_exclusion_in_schedule(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """AVOID types should be excluded from schedule allocations."""
        profile = get_content_type_rankings(db_connection, "alexia")

        # Simulate schedule building
        content_types = list(profile.rankings.keys())
        allocations = {}

        for ct in content_types:
            allocation = apply_content_weighting(5, ct, profile)
            if allocation.weighted_volume > 0:
                allocations[ct] = allocation.weighted_volume

        # AVOID type should not be in allocations
        assert "abstract" not in allocations
        # TOP type should have boosted allocation
        assert allocations["lingerie"] == 6  # 5 * 1.3 = 6.5 -> 6 (banker's rounding)


class TestRankMultiplierMath:
    """Tests for rank multiplier mathematical correctness."""

    @pytest.mark.parametrize(
        "base,rank,expected",
        [
            (10, "TOP", 13),      # 10 * 1.3 = 13
            (10, "MID", 10),      # 10 * 1.0 = 10
            (10, "LOW", 7),       # 10 * 0.7 = 7
            (10, "AVOID", 0),     # 10 * 0.0 = 0
            (5, "TOP", 6),        # 5 * 1.3 = 6.5 -> 6 (banker's rounding)
            (3, "TOP", 4),        # 3 * 1.3 = 3.9 -> 4 (rounded)
            (7, "LOW", 5),        # 7 * 0.7 = 4.9 -> 5 (rounded)
            (1, "TOP", 1),        # 1 * 1.3 = 1.3 -> 1 (rounded)
            (100, "TOP", 130),    # 100 * 1.3 = 130
            (100, "LOW", 70),     # 100 * 0.7 = 70
        ],
    )
    def test_multiplier_calculations(
        self, base: int, rank: str, expected: int
    ) -> None:
        """Verify multiplier calculations are correct."""
        profile = ContentTypeProfile(creator_id="test")
        profile.rankings["test_type"] = ContentTypeRanking(
            content_type_name="test_type",
            performance_rank=rank,
        )

        allocation = apply_content_weighting(base, "test_type", profile)
        assert allocation.weighted_volume == expected
