#!/usr/bin/env python3
"""
Content Type Strategy - Earnings-weighted slot allocation by content type.

This module handles the strategic allocation of schedule slots to different
content types based on their expected earnings performance. It ensures that
higher-earning content types receive proportionally more slots while maintaining
variety constraints.

Key Features:
- Earnings-weighted slot allocation using creator-specific or global fallbacks
- Minimum slot guarantees per content type (variety floor)
- Maximum slot caps per content type (variety ceiling at 40%)
- Premium hour identification for highest-earning content types
- Integration with vault_matrix for content availability filtering

Usage:
    from content_type_strategy import ContentTypeStrategy, allocate_slots_weighted

    strategy = ContentTypeStrategy(conn, creator_id)
    slot_allocation = strategy.allocate_slots_by_content_type(total_slots=28)
    premium_types = strategy.get_premium_content_types(top_n=3)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ContentTypePool",
    "ContentTypeStrategy",
    "get_content_type_earnings",
    "allocate_slots_weighted",
    "get_premium_content_types",
    "PREMIUM_HOURS",
]


# =============================================================================
# CONSTANTS
# =============================================================================

# Peak engagement hours (6pm and 9pm EST) for premium content placement
PREMIUM_HOURS: set[int] = {18, 21}

# Default expected earnings when no data is available
DEFAULT_EXPECTED_EARNINGS: float = 50.0

# Slot allocation constraints
MIN_SLOTS_PER_TYPE: int = 1  # Variety floor - every type gets at least 1 slot
MAX_SLOT_RATIO: float = 0.40  # Variety ceiling - no type exceeds 40% of slots


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ContentTypePool:
    """
    Represents a content type's pool for slot allocation.

    Attributes:
        content_type_id: Database ID of the content type
        type_name: Human-readable name (e.g., "solo", "bg", "anal")
        priority_tier: Content priority tier (1=highest, 3=lowest)
        creator_avg_earnings: Creator-specific average earnings (None if no data)
        global_avg_earnings: Global average earnings across all creators
        expected_earnings: Calculated expected value for this creator
        caption_count: Number of available captions for this type
        slot_weight: Percentage of slots to allocate (0.0-1.0)
    """

    content_type_id: int
    type_name: str
    priority_tier: int
    creator_avg_earnings: float | None
    global_avg_earnings: float
    expected_earnings: float
    caption_count: int = 0
    slot_weight: float = 0.0

    def get_effective_earnings(self) -> float:
        """Return the best available earnings estimate."""
        if self.creator_avg_earnings is not None and self.creator_avg_earnings > 0:
            return self.creator_avg_earnings
        if self.global_avg_earnings > 0:
            return self.global_avg_earnings
        return DEFAULT_EXPECTED_EARNINGS


# =============================================================================
# CONTENT TYPE STRATEGY CLASS
# =============================================================================

class ContentTypeStrategy:
    """
    Strategy manager for content type slot allocation.

    This class encapsulates the logic for determining how many schedule slots
    each content type should receive based on earnings performance data.

    Example:
        >>> strategy = ContentTypeStrategy(conn, "creator-uuid-123")
        >>> allowed_types = strategy.get_allowed_content_types()
        >>> allocation = strategy.allocate_slots_by_content_type(28)
        >>> print(allocation)  # {'solo': 8, 'bg': 11, 'anal': 6, 'custom': 3}
    """

    def __init__(self, conn: sqlite3.Connection, creator_id: str) -> None:
        """
        Initialize the content type strategy.

        Args:
            conn: SQLite database connection with row_factory set
            creator_id: UUID of the creator
        """
        self.conn = conn
        self.creator_id = creator_id
        self._content_types: list[ContentTypePool] | None = None
        self._earnings_cache: dict[str, float] | None = None

    def get_allowed_content_types(self) -> list[ContentTypePool]:
        """
        Get content types from vault_matrix where has_content=1.

        Returns content types that the creator has available in their vault,
        with earnings data populated using the fallback chain:
        1. Creator-specific from caption_creator_performance
        2. Global from caption_bank
        3. Default fallback value

        Returns:
            List of ContentTypePool objects sorted by expected earnings (descending)
        """
        if self._content_types is not None:
            return self._content_types

        query = """
            SELECT
                ct.content_type_id,
                ct.type_name,
                ct.priority_tier,
                (SELECT AVG(ccp.avg_earnings)
                 FROM caption_creator_performance ccp
                 JOIN caption_bank cb ON ccp.caption_id = cb.caption_id
                 WHERE ccp.creator_id = ? AND cb.content_type_id = ct.content_type_id
                ) AS creator_avg_earnings,
                (SELECT AVG(cb.avg_earnings)
                 FROM caption_bank cb
                 WHERE cb.content_type_id = ct.content_type_id AND cb.is_active = 1
                ) AS global_avg_earnings,
                (SELECT COUNT(*)
                 FROM caption_bank cb
                 WHERE cb.content_type_id = ct.content_type_id
                   AND cb.is_active = 1
                   AND (cb.creator_id = ? OR cb.is_universal = 1)
                   AND cb.freshness_score >= 30
                ) AS caption_count
            FROM content_types ct
            JOIN vault_matrix vm ON ct.content_type_id = vm.content_type_id
            WHERE vm.creator_id = ? AND vm.has_content = 1
            ORDER BY creator_avg_earnings DESC NULLS LAST, global_avg_earnings DESC NULLS LAST
        """

        cursor = self.conn.execute(
            query, (self.creator_id, self.creator_id, self.creator_id)
        )

        content_types = []
        for row in cursor.fetchall():
            creator_avg = row["creator_avg_earnings"]
            global_avg = row["global_avg_earnings"] or DEFAULT_EXPECTED_EARNINGS

            # Calculate expected earnings using fallback chain
            if creator_avg is not None and creator_avg > 0:
                expected = creator_avg
            elif global_avg > 0:
                expected = global_avg
            else:
                expected = DEFAULT_EXPECTED_EARNINGS

            content_types.append(ContentTypePool(
                content_type_id=row["content_type_id"],
                type_name=row["type_name"],
                priority_tier=row["priority_tier"] or 2,
                creator_avg_earnings=creator_avg,
                global_avg_earnings=global_avg,
                expected_earnings=expected,
                caption_count=row["caption_count"] or 0,
            ))

        # Sort by expected earnings descending
        content_types.sort(key=lambda x: x.expected_earnings, reverse=True)

        self._content_types = content_types
        return content_types

    def calculate_slot_weights(self) -> dict[str, float]:
        """
        Calculate what percentage of slots each content type should get.

        Based on expected_earnings with:
        - Minimum 1 slot per content type per week (variety floor)
        - Maximum 40% slots for any single type (variety ceiling)

        Returns:
            Dict mapping content type name to weight (0.0-1.0)
            Example: {'solo': 0.25, 'bg': 0.40, 'anal': 0.35}
        """
        content_types = self.get_allowed_content_types()

        if not content_types:
            return {}

        # Calculate total expected earnings
        total_earnings = sum(ct.expected_earnings for ct in content_types)

        if total_earnings <= 0:
            # Equal distribution if no earnings data
            equal_weight = 1.0 / len(content_types)
            return {ct.type_name: equal_weight for ct in content_types}

        # Calculate raw weights based on earnings proportion
        weights: dict[str, float] = {}
        for ct in content_types:
            raw_weight = ct.expected_earnings / total_earnings
            # Apply ceiling cap
            capped_weight = min(raw_weight, MAX_SLOT_RATIO)
            weights[ct.type_name] = capped_weight
            ct.slot_weight = capped_weight

        # Redistribute excess from capped types
        total_weight = sum(weights.values())
        if total_weight < 1.0:
            # Find uncapped types to receive redistribution
            uncapped = [
                name for name, w in weights.items()
                if w < MAX_SLOT_RATIO
            ]
            if uncapped:
                excess = 1.0 - total_weight
                per_type_boost = excess / len(uncapped)
                for name in uncapped:
                    new_weight = min(weights[name] + per_type_boost, MAX_SLOT_RATIO)
                    weights[name] = new_weight

        # Normalize to ensure weights sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {name: w / total_weight for name, w in weights.items()}

        return weights

    def allocate_slots_by_content_type(
        self,
        total_slots: int,
        min_per_type: int | None = None,
        max_ratio: float | None = None
    ) -> dict[str, int]:
        """
        Allocate total slots across content types based on earnings weights.

        Args:
            total_slots: Total number of slots to allocate
            min_per_type: Minimum slots per type (default: MIN_SLOTS_PER_TYPE)
            max_ratio: Maximum ratio for any type (default: MAX_SLOT_RATIO)

        Returns:
            Dict mapping content type name to number of slots
            Example: {'solo': 8, 'bg': 11, 'anal': 6, 'custom': 3}
        """
        if min_per_type is None:
            min_per_type = MIN_SLOTS_PER_TYPE
        if max_ratio is None:
            max_ratio = MAX_SLOT_RATIO

        content_types = self.get_allowed_content_types()

        if not content_types:
            return {}

        # Use the dedicated allocation function
        earnings_dict = {ct.type_name: ct.expected_earnings for ct in content_types}

        return allocate_slots_weighted(
            content_type_earnings=earnings_dict,
            total_slots=total_slots,
            min_per_type=min_per_type,
            max_ratio=max_ratio
        )

    def get_premium_content_types(self, top_n: int = 3) -> list[str]:
        """
        Get the top N highest-earning content types for premium slots.

        Premium slots are at peak engagement hours (6pm, 9pm) where we want
        to place our highest-performing content.

        Args:
            top_n: Number of top types to return

        Returns:
            List of content type names sorted by expected earnings (descending)
        """
        content_types = self.get_allowed_content_types()

        if not content_types:
            return []

        # Already sorted by expected_earnings descending
        return [ct.type_name for ct in content_types[:top_n]]

    def get_caption_counts_by_type(self) -> dict[str, int]:
        """
        Get available caption counts for each content type.

        Returns:
            Dict mapping content type name to caption count
        """
        content_types = self.get_allowed_content_types()
        return {ct.type_name: ct.caption_count for ct in content_types}


# =============================================================================
# STANDALONE FUNCTIONS
# =============================================================================

def get_content_type_earnings(
    conn: sqlite3.Connection,
    creator_id: str
) -> dict[str, float]:
    """
    Get average earnings per content type for a creator.

    Priority chain:
    1. Creator-specific from caption_creator_performance
    2. Global from caption_bank
    3. Default fallback (50.0)

    Args:
        conn: Database connection with row_factory set
        creator_id: Creator UUID

    Returns:
        Dict mapping type name to expected earnings
        Example: {"solo": 150.0, "bg": 300.0, "anal": 200.0}
    """
    query = """
        SELECT
            ct.type_name,
            COALESCE(
                (SELECT AVG(ccp.avg_earnings)
                 FROM caption_creator_performance ccp
                 JOIN caption_bank cb ON ccp.caption_id = cb.caption_id
                 WHERE ccp.creator_id = ? AND cb.content_type_id = ct.content_type_id),
                (SELECT AVG(cb.avg_earnings)
                 FROM caption_bank cb
                 WHERE cb.content_type_id = ct.content_type_id AND cb.is_active = 1),
                ?
            ) as expected_earnings
        FROM content_types ct
        JOIN vault_matrix vm ON ct.content_type_id = vm.content_type_id
        WHERE vm.creator_id = ? AND vm.has_content = 1
        ORDER BY expected_earnings DESC
    """

    cursor = conn.execute(query, (creator_id, DEFAULT_EXPECTED_EARNINGS, creator_id))

    return {
        row["type_name"]: row["expected_earnings"] or DEFAULT_EXPECTED_EARNINGS
        for row in cursor.fetchall()
    }


def allocate_slots_weighted(
    content_type_earnings: dict[str, float],
    total_slots: int,
    min_per_type: int = MIN_SLOTS_PER_TYPE,
    max_ratio: float = MAX_SLOT_RATIO
) -> dict[str, int]:
    """
    Allocate slots proportional to earnings with constraints.

    Algorithm:
    1. Calculate raw slot allocation based on earnings proportion
    2. Apply minimum floor (variety guarantee)
    3. Apply maximum ceiling (variety cap at 40%)
    4. Redistribute remainder to maintain total slot count

    Example for 28 slots with earnings {solo: 100, bg: 300, anal: 200}:
    - Total earnings = 600
    - Raw weights: solo=16.7%, bg=50%, anal=33.3%
    - After max_ratio=40% cap: solo=16.7%, bg=40%, anal=33.3%, remainder distributed
    - After min_per_type: each gets at least 1
    - Final: solo=5, bg=11, anal=9, remainder=3 distributed

    Args:
        content_type_earnings: Dict mapping content type to expected earnings
        total_slots: Total number of slots to allocate
        min_per_type: Minimum slots per content type (default: 1)
        max_ratio: Maximum ratio any single type can have (default: 0.40)

    Returns:
        Dict mapping content type name to slot count
    """
    if not content_type_earnings:
        return {}

    num_types = len(content_type_earnings)

    # Check if we have enough slots for minimum allocation
    min_total = min_per_type * num_types
    if total_slots < min_total:
        # Not enough slots - distribute evenly what we have
        base_slots = total_slots // num_types
        remainder = total_slots % num_types

        allocation = {}
        for i, type_name in enumerate(
            sorted(content_type_earnings.keys(), key=lambda x: -content_type_earnings[x])
        ):
            allocation[type_name] = base_slots + (1 if i < remainder else 0)
        return allocation

    # Calculate total earnings
    total_earnings = sum(content_type_earnings.values())

    if total_earnings <= 0:
        # Equal distribution if no earnings
        slots_per_type = total_slots // num_types
        remainder = total_slots % num_types

        allocation = {}
        for i, type_name in enumerate(content_type_earnings.keys()):
            allocation[type_name] = slots_per_type + (1 if i < remainder else 0)
        return allocation

    # Calculate max slots per type based on ceiling
    max_slots = int(total_slots * max_ratio)

    # Step 1: Calculate raw allocation based on earnings proportion
    raw_allocation: dict[str, float] = {}
    for type_name, earnings in content_type_earnings.items():
        raw_slots = (earnings / total_earnings) * total_slots
        raw_allocation[type_name] = raw_slots

    # Step 2: Apply constraints and convert to integers
    allocation: dict[str, int] = {}
    excess: float = 0.0
    capped_types: set[str] = set()

    # First pass: apply min/max constraints
    for type_name, raw_slots in raw_allocation.items():
        # Apply minimum floor
        slots = max(raw_slots, min_per_type)

        # Apply maximum ceiling
        if slots > max_slots:
            excess += slots - max_slots
            slots = max_slots
            capped_types.add(type_name)

        allocation[type_name] = int(slots)

    # Step 3: Redistribute excess to uncapped types
    uncapped_types = [
        name for name in allocation.keys()
        if name not in capped_types and allocation[name] < max_slots
    ]

    if uncapped_types and excess > 0:
        # Sort by earnings to prioritize higher earners
        uncapped_types.sort(key=lambda x: -content_type_earnings[x])

        remaining_excess = int(excess)
        while remaining_excess > 0 and uncapped_types:
            for type_name in uncapped_types:
                if remaining_excess <= 0:
                    break
                if allocation[type_name] < max_slots:
                    allocation[type_name] += 1
                    remaining_excess -= 1

            # Remove types that hit the cap
            uncapped_types = [
                name for name in uncapped_types
                if allocation[name] < max_slots
            ]

    # Step 4: Ensure total matches exactly
    current_total = sum(allocation.values())
    difference = total_slots - current_total

    if difference > 0:
        # Add remaining slots to highest earners
        sorted_types = sorted(
            allocation.keys(),
            key=lambda x: -content_type_earnings[x]
        )
        for type_name in sorted_types:
            if difference <= 0:
                break
            if allocation[type_name] < max_slots:
                allocation[type_name] += 1
                difference -= 1

    elif difference < 0:
        # Remove excess slots from lowest earners
        sorted_types = sorted(
            allocation.keys(),
            key=lambda x: content_type_earnings[x]
        )
        for type_name in sorted_types:
            if difference >= 0:
                break
            if allocation[type_name] > min_per_type:
                allocation[type_name] -= 1
                difference += 1

    return allocation


def get_premium_content_types(
    content_type_earnings: dict[str, float],
    top_n: int = 3
) -> list[str]:
    """
    Return top N earning content types for premium slots.

    Premium slots occur at peak engagement hours (6pm, 9pm EST) where
    we want to place our highest-performing content types.

    Args:
        content_type_earnings: Dict mapping type name to expected earnings
        top_n: Number of top types to return

    Returns:
        List of content type names sorted by earnings (descending)
    """
    if not content_type_earnings:
        return []

    sorted_types = sorted(
        content_type_earnings.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return [type_name for type_name, _ in sorted_types[:top_n]]


# =============================================================================
# MAIN (FOR TESTING)
# =============================================================================

def main() -> None:
    """Test the content type strategy module."""
    import os
    from pathlib import Path

    # Database path resolution
    home = Path.home()
    db_candidates = [
        Path(os.environ.get("EROS_DATABASE_PATH", "")),
        home / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
        home / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    ]
    db_path = next((p for p in db_candidates if p.exists()), None)

    if not db_path:
        print("Error: Database not found")
        return

    print(f"Using database: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Get a sample creator
        cursor = conn.execute(
            "SELECT creator_id, page_name FROM creators WHERE is_active = 1 LIMIT 1"
        )
        row = cursor.fetchone()

        if not row:
            print("No active creators found")
            return

        creator_id = row["creator_id"]
        page_name = row["page_name"]
        print(f"\nTesting with creator: {page_name}")
        print("=" * 60)

        # Test ContentTypeStrategy
        strategy = ContentTypeStrategy(conn, creator_id)

        print("\n1. Allowed Content Types:")
        for ct in strategy.get_allowed_content_types():
            print(f"   {ct.type_name}: ${ct.expected_earnings:.2f} "
                  f"(creator: ${ct.creator_avg_earnings or 0:.2f}, "
                  f"global: ${ct.global_avg_earnings:.2f}, "
                  f"captions: {ct.caption_count})")

        print("\n2. Slot Weights:")
        weights = strategy.calculate_slot_weights()
        for type_name, weight in weights.items():
            print(f"   {type_name}: {weight:.1%}")

        print("\n3. Slot Allocation (28 slots/week):")
        allocation = strategy.allocate_slots_by_content_type(28)
        for type_name, slots in allocation.items():
            print(f"   {type_name}: {slots} slots")
        print(f"   Total: {sum(allocation.values())} slots")

        print("\n4. Premium Content Types (top 3):")
        premium = strategy.get_premium_content_types(3)
        for i, type_name in enumerate(premium, 1):
            print(f"   {i}. {type_name}")

        print("\n5. Standalone Function Test:")
        earnings = get_content_type_earnings(conn, creator_id)
        print(f"   Earnings: {earnings}")

        standalone_allocation = allocate_slots_weighted(earnings, 28)
        print(f"   Allocation: {standalone_allocation}")


if __name__ == "__main__":
    main()
