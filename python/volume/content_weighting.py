"""
Content-type weighted allocation for volume optimization.

Weights volume allocation based on content type performance rankings
(TOP/MID/LOW/AVOID) to maximize revenue per send. This module integrates
with the top_content_types table to apply performance-based multipliers
to base volume allocations.

Usage:
    from python.volume.content_weighting import (
        ContentWeightingOptimizer,
        get_content_type_rankings,
        apply_content_weighting,
    )

    # Using the high-level optimizer
    optimizer = ContentWeightingOptimizer(db_path="database/eros_sd_main.db")
    profile = optimizer.get_profile(creator_id="alexia")

    # Apply weighting to a single allocation
    allocation = optimizer.weight_allocation(
        creator_id="alexia",
        content_type="lingerie",
        base_volume=5,
    )
    print(f"Weighted volume: {allocation.weighted_volume}")

    # Check if a content type should be included
    should_include = optimizer.should_include_content_type("alexia", "lingerie")

Configuration:
    Performance rank multipliers:
    - TOP: 1.3x (30% more slots for top performers)
    - MID: 1.0x (normal allocation)
    - LOW: 0.7x (30% fewer slots)
    - AVOID: 0.0x (no slots for content to avoid)
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from python.exceptions import DatabaseError
from python.logging_config import get_logger

logger = get_logger(__name__)


# Performance rank multipliers
RANK_MULTIPLIERS: Dict[str, float] = {
    "TOP": 1.3,     # 30% more slots for top performers
    "MID": 1.0,     # Normal allocation
    "LOW": 0.7,     # 30% fewer slots
    "AVOID": 0.0,   # No slots for content to avoid
}

# Default rank when content type not in rankings
DEFAULT_RANK: str = "MID"


@dataclass
class ContentTypeRanking:
    """Ranking data for a single content type.

    Represents the performance classification and associated multiplier
    for a specific content type within a creator's profile.

    Attributes:
        content_type_name: Name of the content type.
        performance_rank: Rank category (TOP/MID/LOW/AVOID).
        multiplier: Volume multiplier for this rank (auto-calculated).
        avg_revenue_per_send: Historical RPS for this type.
        message_count: Number of messages analyzed for this ranking.
        last_updated: Timestamp when ranking was last calculated.
    """

    content_type_name: str
    performance_rank: str
    multiplier: float = 1.0
    avg_revenue_per_send: float = 0.0
    message_count: int = 0
    last_updated: str = ""

    def __post_init__(self) -> None:
        """Calculate multiplier from performance rank after initialization."""
        self.multiplier = RANK_MULTIPLIERS.get(self.performance_rank, 1.0)


@dataclass
class ContentTypeProfile:
    """Complete content type ranking profile for a creator.

    Aggregates all content type rankings for a creator, providing
    convenient access to TOP and AVOID types for quick filtering.

    Attributes:
        creator_id: Creator identifier.
        rankings: Dict mapping content type name to ranking.
        top_types: List of TOP-ranked content types.
        avoid_types: List of AVOID-ranked content types.
        total_types: Total number of ranked content types.
    """

    creator_id: str
    rankings: Dict[str, ContentTypeRanking] = field(default_factory=dict)
    top_types: List[str] = field(default_factory=list)
    avoid_types: List[str] = field(default_factory=list)
    total_types: int = 0


@dataclass(frozen=True)
class WeightedAllocation:
    """Result of content-weighted volume allocation.

    Immutable record of a volume allocation after applying content type
    weighting. The weighted_volume field contains the adjusted allocation.

    Attributes:
        base_volume: Original volume before weighting.
        weighted_volume: Volume after content type weighting.
        content_type: Content type this allocation is for.
        rank: Performance rank of this content type.
        multiplier: Multiplier that was applied.
        adjusted: Whether any adjustment was made (multiplier != 1.0).
    """

    base_volume: int
    weighted_volume: int
    content_type: str
    rank: str
    multiplier: float
    adjusted: bool


def get_content_type_rankings(
    conn: sqlite3.Connection,
    creator_id: str,
) -> ContentTypeProfile:
    """Fetch content type rankings for a creator from the database.

    Queries the top_content_types table for performance rankings
    by content type, ordered by rank priority.

    Args:
        conn: SQLite database connection.
        creator_id: Creator identifier to fetch rankings for.

    Returns:
        ContentTypeProfile with all rankings for the creator.

    Raises:
        DatabaseError: If the query fails.

    Example:
        >>> conn = sqlite3.connect("database/eros_sd_main.db")
        >>> profile = get_content_type_rankings(conn, "alexia")
        >>> print(f"Found {profile.total_types} content types")
        >>> print(f"Top performers: {profile.top_types}")
    """
    # Note: Schema uses content_type (not content_type_name), performance_tier (not performance_rank),
    #       avg_rps (not avg_revenue_per_send), send_count (not message_count), updated_at (not last_updated)
    query = """
        SELECT
            content_type,
            performance_tier,
            avg_rps,
            send_count,
            updated_at
        FROM top_content_types
        WHERE creator_id = ?
        ORDER BY
            CASE performance_tier
                WHEN 'TOP' THEN 1
                WHEN 'MID' THEN 2
                WHEN 'LOW' THEN 3
                WHEN 'AVOID' THEN 4
            END
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to fetch content type rankings: {e}",
            operation="get_content_type_rankings",
            details={"creator_id": creator_id},
        )

    profile = ContentTypeProfile(creator_id=creator_id)

    for row in rows:
        name, rank, rps, count, updated = row

        ranking = ContentTypeRanking(
            content_type_name=name,
            performance_rank=rank or DEFAULT_RANK,
            avg_revenue_per_send=rps or 0.0,
            message_count=count or 0,
            last_updated=updated or "",
        )

        profile.rankings[name] = ranking

        if rank == "TOP":
            profile.top_types.append(name)
        elif rank == "AVOID":
            profile.avoid_types.append(name)

    profile.total_types = len(profile.rankings)

    logger.debug(
        "Content type rankings loaded",
        extra={
            "creator_id": creator_id,
            "total_types": profile.total_types,
            "top_types": len(profile.top_types),
            "avoid_types": len(profile.avoid_types),
        },
    )

    return profile


def apply_content_weighting(
    base_volume: int,
    content_type: str,
    profile: ContentTypeProfile,
) -> WeightedAllocation:
    """Apply content type weighting to a base volume.

    Looks up the content type's performance rank and applies the
    corresponding multiplier to the base volume.

    Args:
        base_volume: Volume before weighting (must be non-negative).
        content_type: Content type to get multiplier for.
        profile: ContentTypeProfile with rankings.

    Returns:
        WeightedAllocation with adjusted volume.

    Example:
        >>> profile = ContentTypeProfile(creator_id="alexia")
        >>> profile.rankings["lingerie"] = ContentTypeRanking(
        ...     content_type_name="lingerie",
        ...     performance_rank="TOP",
        ... )
        >>> allocation = apply_content_weighting(10, "lingerie", profile)
        >>> print(allocation.weighted_volume)  # 13 (10 * 1.3)
    """
    ranking = profile.rankings.get(content_type)

    if not ranking:
        # Content type not in rankings - use default (MID)
        return WeightedAllocation(
            base_volume=base_volume,
            weighted_volume=base_volume,
            content_type=content_type,
            rank=DEFAULT_RANK,
            multiplier=1.0,
            adjusted=False,
        )

    weighted = round(base_volume * ranking.multiplier)

    # Ensure at least 0 (AVOID types get 0)
    weighted = max(0, weighted)

    return WeightedAllocation(
        base_volume=base_volume,
        weighted_volume=weighted,
        content_type=content_type,
        rank=ranking.performance_rank,
        multiplier=ranking.multiplier,
        adjusted=ranking.multiplier != 1.0,
    )


def allocate_by_content_type(
    total_volume: int,
    content_types: List[str],
    profile: ContentTypeProfile,
    min_per_type: int = 1,
) -> Dict[str, int]:
    """Distribute total volume across content types based on rankings.

    Uses performance rankings to weight allocation toward high-performing
    content types while respecting minimum allocations for non-AVOID types.

    Args:
        total_volume: Total volume to distribute (must be positive).
        content_types: List of content types to allocate to.
        profile: ContentTypeProfile with rankings.
        min_per_type: Minimum allocation per non-AVOID type (default 1).

    Returns:
        Dict mapping content type to allocated volume.

    Example:
        >>> profile = ContentTypeProfile(creator_id="alexia")
        >>> profile.rankings["lingerie"] = ContentTypeRanking(
        ...     content_type_name="lingerie", performance_rank="TOP"
        ... )
        >>> profile.rankings["outdoor"] = ContentTypeRanking(
        ...     content_type_name="outdoor", performance_rank="LOW"
        ... )
        >>> allocation = allocate_by_content_type(
        ...     total_volume=10,
        ...     content_types=["lingerie", "outdoor"],
        ...     profile=profile,
        ... )
        >>> # lingerie gets more due to TOP rank
    """
    if not content_types:
        return {}

    if total_volume <= 0:
        return {ct: 0 for ct in content_types}

    # Calculate weighted shares
    type_weights: Dict[str, float] = {}
    total_weight = 0.0

    for ct in content_types:
        ranking = profile.rankings.get(ct)
        multiplier = ranking.multiplier if ranking else 1.0

        # AVOID types get 0 weight
        if multiplier == 0.0:
            type_weights[ct] = 0.0
        else:
            type_weights[ct] = multiplier
            total_weight += multiplier

    # Allocate based on weighted shares
    allocation: Dict[str, int] = {}
    remaining = total_volume

    for ct in content_types:
        if total_weight > 0 and type_weights[ct] > 0:
            share = (type_weights[ct] / total_weight) * total_volume
            allocated = max(min_per_type, round(share))
            allocation[ct] = allocated
            remaining -= allocated
        else:
            allocation[ct] = 0

    # Distribute any remaining volume to TOP types first
    if remaining > 0 and profile.top_types:
        for top_type in profile.top_types:
            if top_type in allocation and allocation[top_type] > 0:
                allocation[top_type] += remaining
                remaining = 0
                break

    # If still remaining and no TOP types available, give to first non-AVOID
    if remaining > 0:
        for ct in content_types:
            if allocation.get(ct, 0) > 0:
                allocation[ct] += remaining
                break

    return allocation


def get_content_type_recommendations(
    profile: ContentTypeProfile,
) -> Dict[str, str]:
    """Get actionable recommendations based on content rankings.

    Analyzes the profile and generates scheduling recommendations
    to maximize performance.

    Args:
        profile: ContentTypeProfile with rankings.

    Returns:
        Dict mapping recommendation type to message.

    Example:
        >>> recommendations = get_content_type_recommendations(profile)
        >>> if "increase" in recommendations:
        ...     print(recommendations["increase"])
    """
    recommendations: Dict[str, str] = {}

    if profile.top_types:
        recommendations["increase"] = (
            f"Increase volume for TOP types: {', '.join(profile.top_types)}"
        )

    if profile.avoid_types:
        recommendations["avoid"] = (
            f"Do not schedule AVOID types: {', '.join(profile.avoid_types)}"
        )

    # Find types that might be promoted based on message count
    mid_types_with_data = [
        name
        for name, ranking in profile.rankings.items()
        if ranking.performance_rank == "MID" and ranking.message_count >= 10
    ]
    if mid_types_with_data:
        recommendations["potential"] = (
            f"MID types with potential (test for promotion): "
            f"{', '.join(mid_types_with_data[:3])}"
        )

    return recommendations


class ContentWeightingOptimizer:
    """High-level optimizer for content-type weighted allocation.

    Provides a convenient interface for applying content type weighting
    to volume allocations, with caching for repeated lookups.

    Attributes:
        db_path: Path to the SQLite database.

    Example:
        >>> optimizer = ContentWeightingOptimizer("database/eros_sd_main.db")
        >>> profile = optimizer.get_profile("alexia")
        >>> allocation = optimizer.weight_allocation("alexia", "lingerie", 5)
        >>> print(f"Adjusted: {allocation.weighted_volume}")
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the optimizer with database path.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._cache: Dict[str, ContentTypeProfile] = {}

    def get_profile(
        self,
        creator_id: str,
        force_refresh: bool = False,
    ) -> ContentTypeProfile:
        """Get or fetch content type profile for a creator.

        Uses internal cache to avoid repeated database queries.
        Use force_refresh=True to bypass cache.

        Args:
            creator_id: Creator to get profile for.
            force_refresh: If True, refetch even if cached.

        Returns:
            ContentTypeProfile with rankings.
        """
        if not force_refresh and creator_id in self._cache:
            return self._cache[creator_id]

        conn = sqlite3.connect(self.db_path)
        try:
            profile = get_content_type_rankings(conn, creator_id)
            self._cache[creator_id] = profile
            return profile
        finally:
            conn.close()

    def weight_allocation(
        self,
        creator_id: str,
        content_type: str,
        base_volume: int,
    ) -> WeightedAllocation:
        """Apply content weighting to a single allocation.

        Args:
            creator_id: Creator for ranking lookup.
            content_type: Content type to weight.
            base_volume: Base volume before weighting.

        Returns:
            WeightedAllocation with adjusted volume.
        """
        profile = self.get_profile(creator_id)
        return apply_content_weighting(base_volume, content_type, profile)

    def should_include_content_type(
        self,
        creator_id: str,
        content_type: str,
    ) -> bool:
        """Check if a content type should be included in schedule.

        Returns False for AVOID-ranked content types to prevent
        scheduling underperforming content.

        Args:
            creator_id: Creator for ranking lookup.
            content_type: Content type to check.

        Returns:
            False if content type is ranked AVOID, True otherwise.
        """
        profile = self.get_profile(creator_id)
        return content_type not in profile.avoid_types

    def clear_cache(self) -> None:
        """Clear the internal profile cache."""
        self._cache.clear()

    def get_cached_creators(self) -> List[str]:
        """Get list of creator IDs currently in cache.

        Returns:
            List of cached creator IDs.
        """
        return list(self._cache.keys())


__all__ = [
    # Constants
    "RANK_MULTIPLIERS",
    "DEFAULT_RANK",
    # Data classes
    "ContentTypeRanking",
    "ContentTypeProfile",
    "WeightedAllocation",
    # Functions
    "get_content_type_rankings",
    "apply_content_weighting",
    "allocate_by_content_type",
    "get_content_type_recommendations",
    # Main class
    "ContentWeightingOptimizer",
]
