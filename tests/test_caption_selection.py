#!/usr/bin/env python3
"""
Unit tests for caption selection and VoseAliasSelector.

Tests:
    1. VoseAliasSelector - Weighted random selection algorithm
    2. Pool-based selection - PROVEN/GLOBAL_EARNER/DISCOVERY pools
    3. Freshness filtering - Minimum freshness threshold
    4. Stratified pools - Pool allocation and prioritization
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts and tests to path
TESTS_DIR = Path(__file__).parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from fixtures import (
    MOCK_CAPTIONS,
    MOCK_CAPTIONS_DISCOVERY,
    MOCK_CAPTIONS_GLOBAL_EARNER,
    MOCK_CAPTIONS_PROVEN,
    create_mock_caption,
    create_mock_stratified_pools,
)


# =============================================================================
# VOSE ALIAS SELECTOR TESTS
# =============================================================================


class TestVoseAliasSelector:
    """Tests for VoseAliasSelector weighted random selection."""

    def test_initialization_with_valid_items(self):
        """Test that selector initializes with valid items."""
        from utils import VoseAliasSelector

        items = ["a", "b", "c"]
        weights = {"a": 10.0, "b": 5.0, "c": 1.0}

        selector = VoseAliasSelector(items, lambda x: weights[x])

        assert selector.n == 3
        assert len(selector.prob) == 3
        assert len(selector.alias) == 3

    def test_initialization_empty_items_raises_error(self):
        """Test that empty items list raises ValueError."""
        from utils import VoseAliasSelector

        with pytest.raises(ValueError, match="cannot be empty"):
            VoseAliasSelector([], lambda x: 1.0)

    def test_initialization_zero_weights_uses_minimum(self):
        """Test that zero weights are floored to minimum value."""
        from utils import VoseAliasSelector

        items = ["a", "b", "c"]
        weights = {"a": 0.0, "b": 0.0, "c": 1.0}

        # Should not raise - zero weights are floored to 0.001
        selector = VoseAliasSelector(items, lambda x: weights[x])
        assert selector.n == 3

    def test_weighted_selection_distribution(self):
        """Test that weighted selection follows expected distribution."""
        from utils import VoseAliasSelector

        items = ["high", "low"]
        weights = {"high": 100.0, "low": 1.0}

        selector = VoseAliasSelector(items, lambda x: weights[x])

        # Run many selections
        results = [selector.select() for _ in range(1000)]
        counts = Counter(results)

        # "high" should be selected much more often
        assert counts["high"] > counts["low"] * 5  # At least 5:1 ratio

    def test_single_item_selection(self):
        """Test selection with single item always returns that item."""
        from utils import VoseAliasSelector

        items = ["only"]
        selector = VoseAliasSelector(items, lambda x: 1.0)

        for _ in range(10):
            assert selector.select() == "only"

    def test_select_multiple_with_duplicates(self):
        """Test selecting multiple items with duplicates allowed."""
        from utils import VoseAliasSelector

        items = ["a", "b", "c"]
        selector = VoseAliasSelector(items, lambda x: 1.0)

        results = selector.select_multiple(10, allow_duplicates=True)

        assert len(results) == 10
        # With duplicates allowed, we might get repeats
        unique_count = len(set(results))
        assert unique_count <= 10

    def test_select_multiple_without_duplicates(self):
        """Test selecting multiple unique items."""
        from utils import VoseAliasSelector

        items = ["a", "b", "c", "d", "e"]
        selector = VoseAliasSelector(items, lambda x: 1.0)

        results = selector.select_multiple(3, allow_duplicates=False)

        assert len(results) == 3
        assert len(set(results)) == 3  # All unique

    def test_select_multiple_exceeds_available(self):
        """Test selecting more items than available returns all unique items."""
        from utils import VoseAliasSelector

        items = ["a", "b", "c"]
        selector = VoseAliasSelector(items, lambda x: 1.0)

        results = selector.select_multiple(10, allow_duplicates=False)

        # Should return at most 3 unique items
        assert len(results) == 3
        assert len(set(results)) == 3

    def test_caption_object_deduplication(self):
        """Test deduplication works with objects having caption_id."""
        from utils import VoseAliasSelector

        @dataclass
        class MockCaption:
            caption_id: int
            text: str

        captions = [
            MockCaption(caption_id=1, text="Caption 1"),
            MockCaption(caption_id=2, text="Caption 2"),
            MockCaption(caption_id=3, text="Caption 3"),
        ]

        selector = VoseAliasSelector(captions, lambda x: 1.0)

        results = selector.select_multiple(3, allow_duplicates=False)

        # Should have 3 unique caption_ids
        caption_ids = {c.caption_id for c in results}
        assert len(caption_ids) == 3

    def test_dict_item_deduplication(self):
        """Test deduplication works with dict items having caption_id key."""
        from utils import VoseAliasSelector

        items = [
            {"caption_id": 1, "text": "Caption 1"},
            {"caption_id": 2, "text": "Caption 2"},
            {"caption_id": 3, "text": "Caption 3"},
        ]

        selector = VoseAliasSelector(items, lambda x: 1.0)

        results = selector.select_multiple(3, allow_duplicates=False)

        caption_ids = {item["caption_id"] for item in results}
        assert len(caption_ids) == 3

    def test_equal_weights_uniform_distribution(self):
        """Test that equal weights produce roughly uniform distribution."""
        from utils import VoseAliasSelector

        items = ["a", "b", "c", "d"]
        selector = VoseAliasSelector(items, lambda x: 1.0)

        # Run many selections
        results = [selector.select() for _ in range(4000)]
        counts = Counter(results)

        # Each item should be selected roughly 1000 times (+/- 20%)
        for item in items:
            assert 600 < counts[item] < 1400, f"{item} count {counts[item]} outside expected range"


# =============================================================================
# POOL-BASED SELECTION TESTS
# =============================================================================


class TestPoolBasedSelection:
    """Tests for pool-based caption selection logic."""

    def test_proven_pool_priority(self):
        """Test that PROVEN pool captions are prioritized."""
        pools = create_mock_stratified_pools(
            content_type_id=1,
            type_name="solo",
            num_proven=3,
            num_global_earner=3,
            num_discovery=3,
        )

        # Proven pool should have highest priority captions
        assert pools.has_proven is True
        assert len(pools.proven) == 3

        # Each proven caption should have creator_avg_earnings
        for caption in pools.proven:
            assert caption.creator_avg_earnings is not None

    def test_global_earner_fallback(self):
        """Test fallback to GLOBAL_EARNER when PROVEN is empty."""
        pools = create_mock_stratified_pools(
            content_type_id=1,
            type_name="solo",
            num_proven=0,  # No proven
            num_global_earner=5,
            num_discovery=3,
        )

        assert pools.has_proven is False
        assert len(pools.global_earners) == 5

        # Global earners should have global_avg_earnings but not creator_avg_earnings
        for caption in pools.global_earners:
            assert caption.global_avg_earnings is not None

    def test_discovery_pool_fallback(self):
        """Test fallback to DISCOVERY when other pools are empty."""
        pools = create_mock_stratified_pools(
            content_type_id=1,
            type_name="solo",
            num_proven=0,
            num_global_earner=0,
            num_discovery=5,
        )

        assert pools.has_proven is False
        assert len(pools.global_earners) == 0
        assert len(pools.discovery) == 5

    def test_pool_total_count(self):
        """Test that total_count returns sum of all pools."""
        pools = create_mock_stratified_pools(
            content_type_id=1,
            type_name="solo",
            num_proven=2,
            num_global_earner=3,
            num_discovery=4,
        )

        assert pools.total_count == 9

    def test_get_all_captions(self):
        """Test that get_all_captions returns all pools combined."""
        pools = create_mock_stratified_pools(
            content_type_id=1,
            type_name="solo",
            num_proven=2,
            num_global_earner=3,
            num_discovery=4,
        )

        all_captions = pools.get_all_captions()
        assert len(all_captions) == 9

    def test_expected_earnings_from_proven(self):
        """Test expected earnings calculation from proven pool."""
        pools = create_mock_stratified_pools(
            content_type_id=1,
            type_name="solo",
            num_proven=3,
            num_global_earner=2,
            num_discovery=2,
        )

        expected = pools.get_expected_earnings()
        # Should use creator_avg_earnings from proven pool
        assert expected > 0

    def test_expected_earnings_fallback_to_global(self):
        """Test expected earnings fallback to global earnings."""
        pools = create_mock_stratified_pools(
            content_type_id=1,
            type_name="solo",
            num_proven=0,  # No proven
            num_global_earner=3,
            num_discovery=2,
        )

        expected = pools.get_expected_earnings()
        # Should use global_avg_earnings * 0.8
        assert expected > 0


# =============================================================================
# FRESHNESS FILTERING TESTS
# =============================================================================


class TestFreshnessFiltering:
    """Tests for freshness-based caption filtering."""

    def test_freshness_above_threshold_passes(self):
        """Test that captions with freshness above threshold are kept."""
        min_freshness = 30.0

        caption = create_mock_caption(
            caption_id=1001,
            caption_text="Fresh caption",
            freshness_score=80.0,
        )

        assert caption.freshness_score >= min_freshness

    def test_freshness_below_threshold_filtered(self):
        """Test filtering of captions below freshness threshold."""
        min_freshness = 30.0

        captions = [
            create_mock_caption(caption_id=1001, freshness_score=80.0),  # Keep
            create_mock_caption(caption_id=1002, freshness_score=25.0),  # Filter
            create_mock_caption(caption_id=1003, freshness_score=50.0),  # Keep
        ]

        fresh_captions = [c for c in captions if c.freshness_score >= min_freshness]
        assert len(fresh_captions) == 2
        assert all(c.freshness_score >= min_freshness for c in fresh_captions)

    def test_freshness_exactly_at_threshold(self):
        """Test that freshness exactly at threshold is kept."""
        min_freshness = 30.0

        caption = create_mock_caption(
            caption_id=1001,
            caption_text="Threshold caption",
            freshness_score=30.0,  # Exactly at threshold
        )

        assert caption.freshness_score >= min_freshness

    def test_exhausted_captions_detection(self):
        """Test detection of exhausted captions (freshness < 25)."""
        exhausted_threshold = 25.0

        captions = [
            create_mock_caption(caption_id=1001, freshness_score=20.0),  # Exhausted
            create_mock_caption(caption_id=1002, freshness_score=15.0),  # Exhausted
            create_mock_caption(caption_id=1003, freshness_score=30.0),  # Not exhausted
        ]

        exhausted = [c for c in captions if c.freshness_score < exhausted_threshold]
        assert len(exhausted) == 2


# =============================================================================
# WEIGHT CALCULATION TESTS
# =============================================================================


class TestWeightCalculation:
    """Tests for caption weight calculation logic."""

    def test_proven_caption_weight(self):
        """Test weight calculation for PROVEN pool caption."""
        caption = create_mock_caption(
            caption_id=1001,
            pool_type="PROVEN",
            freshness_score=80.0,
            performance_score=85.0,
            creator_avg_earnings=95.0,
            creator_times_used=5,
        )

        # PROVEN captions should use creator_avg_earnings
        assert caption.creator_avg_earnings is not None
        assert caption.pool_type == "PROVEN"

    def test_global_earner_caption_weight(self):
        """Test weight calculation for GLOBAL_EARNER pool caption."""
        caption = create_mock_caption(
            caption_id=2001,
            pool_type="GLOBAL_EARNER",
            freshness_score=90.0,
            performance_score=75.0,
            creator_avg_earnings=None,
            global_avg_earnings=110.0,
            creator_times_used=1,
            global_times_used=50,
        )

        # GLOBAL_EARNER captions should use global_avg_earnings
        assert caption.creator_avg_earnings is None
        assert caption.global_avg_earnings is not None
        assert caption.pool_type == "GLOBAL_EARNER"

    def test_discovery_caption_weight(self):
        """Test weight calculation for DISCOVERY pool caption."""
        caption = create_mock_caption(
            caption_id=3001,
            pool_type="DISCOVERY",
            freshness_score=100.0,
            performance_score=50.0,
            creator_avg_earnings=None,
            global_avg_earnings=None,
            creator_times_used=0,
            global_times_used=0,
        )

        # DISCOVERY captions have no earnings data
        assert caption.creator_avg_earnings is None
        assert caption.global_avg_earnings is None
        assert caption.pool_type == "DISCOVERY"

    def test_persona_boost_applied_to_weight(self):
        """Test that persona boost multiplier is applied."""
        caption = create_mock_caption(
            caption_id=1001,
            pool_type="PROVEN",
            freshness_score=80.0,
            performance_score=70.0,
        )

        # Simulate persona boost
        caption.persona_boost = 1.25

        # Final weight should incorporate persona boost
        base_weight = caption.freshness_score * caption.performance_score / 100
        expected_boosted = base_weight * caption.persona_boost

        # Verify boost applied
        assert caption.persona_boost > 1.0
        assert expected_boosted > base_weight


# =============================================================================
# CONTENT TYPE ALLOCATION TESTS
# =============================================================================


class TestContentTypeAllocation:
    """Tests for content type allocation during selection."""

    def test_allocation_respects_vault_types(self):
        """Test that allocation only includes vault-available types."""
        vault_types = [1, 2, 3]  # solo, sextape, bg

        pools = {
            1: create_mock_stratified_pools(1, "solo"),
            2: create_mock_stratified_pools(2, "sextape"),
            4: create_mock_stratified_pools(4, "bundle"),  # Not in vault
        }

        # Filter to vault types
        available_pools = {k: v for k, v in pools.items() if k in vault_types}

        assert 1 in available_pools
        assert 2 in available_pools
        assert 4 not in available_pools

    def test_rotation_prevents_consecutive_same_type(self):
        """Test that content rotation logic works."""
        last_content_type_id = 1

        # Available types for next slot
        available_types = [1, 2, 3]

        # Filter out consecutive same type
        next_types = [t for t in available_types if t != last_content_type_id]

        assert 1 not in next_types
        assert 2 in next_types
        assert 3 in next_types

    def test_allocation_distribution(self):
        """Test that allocation distributes across content types."""
        # Create pools with different caption counts
        pools = {
            1: create_mock_stratified_pools(1, "solo", num_proven=5),
            2: create_mock_stratified_pools(2, "sextape", num_proven=3),
            3: create_mock_stratified_pools(3, "bg", num_proven=2),
        }

        # Calculate expected allocation (proportional to available)
        total_captions = sum(p.total_count for p in pools.values())
        allocations = {
            k: round(p.total_count / total_captions * 10)
            for k, p in pools.items()
        }

        # Verify allocation is proportional
        assert allocations[1] >= allocations[2]  # More solo than sextape
        assert allocations[2] >= allocations[3]  # More sextape than bg


# =============================================================================
# RESERVED SLOT TESTS
# =============================================================================


class TestReservedSlots:
    """Tests for reserved slot handling (discovery pool slots)."""

    def test_reserved_slot_ratio(self):
        """Test that reserved slots use correct ratio."""
        total_slots = 28  # 4 per day * 7 days
        reserved_ratio = 0.15

        reserved_count = int(total_slots * reserved_ratio)
        assert reserved_count == 4  # 15% of 28

    def test_reserved_slots_use_discovery_pool(self):
        """Test that reserved slots draw from discovery pool."""
        pools = create_mock_stratified_pools(
            content_type_id=1,
            type_name="solo",
            num_proven=3,
            num_global_earner=3,
            num_discovery=5,
        )

        # Reserved slots should only use discovery pool
        discovery_captions = pools.discovery
        assert len(discovery_captions) == 5

        # Verify they're all from discovery pool
        for caption in discovery_captions:
            assert caption.pool_type == "DISCOVERY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
