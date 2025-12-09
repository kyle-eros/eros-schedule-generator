"""
EROS Schedule Generator - Shared Utilities

Common utility classes and functions used across the schedule generation pipeline.

This module provides:
- VoseAliasSelector: O(1) weighted random selection using Vose's Alias Method
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any, Generic, TypeVar

__all__ = ["VoseAliasSelector"]

T = TypeVar("T")


class VoseAliasSelector(Generic[T]):
    """
    Weighted random selection using Vose's Alias Method.

    This algorithm provides O(1) selection time after O(n) preprocessing.
    It's ideal for weighted caption selection where we need to sample
    many times from a fixed distribution.

    Algorithm Overview:
        1. Normalize weights to probabilities (multiply by n, divide by sum)
        2. Partition items into "small" (prob < 1) and "large" (prob >= 1)
        3. Build alias table by pairing small items with large items
        4. Selection: pick random index, flip biased coin to choose original or alias

    Reference: https://www.keithschwarz.com/darts-dice-coins/

    Example:
        >>> items = ["a", "b", "c"]
        >>> weights = {"a": 10, "b": 5, "c": 1}
        >>> selector = VoseAliasSelector(items, lambda x: weights[x])
        >>> selected = selector.select()  # O(1) weighted random selection
        >>> batch = selector.select_multiple(5, allow_duplicates=False)
    """

    def __init__(self, items: list[T], weight_func: Callable[[T], float]) -> None:
        """
        Initialize the Vose Alias table.

        Args:
            items: List of items to select from
            weight_func: Function that returns weight for each item

        Raises:
            ValueError: If items is empty or all weights are zero/negative
        """
        if not items:
            raise ValueError("Items list cannot be empty")

        self.items = items
        self.n = len(items)

        # Compute weights with minimum floor to avoid zero-weight issues
        weights = [max(weight_func(item), 0.001) for item in items]
        total = sum(weights)

        if total <= 0:
            raise ValueError("Total weight must be positive")

        # Normalize to probabilities scaled by n
        # If all weights are equal, each prob will be 1.0
        prob = [w * self.n / total for w in weights]

        # Initialize alias table
        self.prob: list[float] = [0.0] * self.n
        self.alias: list[int] = [0] * self.n

        # Partition into small (< 1) and large (>= 1)
        small: list[int] = []
        large: list[int] = []

        for i, p in enumerate(prob):
            if p < 1.0:
                small.append(i)
            else:
                large.append(i)

        # Build the alias table
        while small and large:
            l_idx = small.pop()
            g_idx = large.pop()

            self.prob[l_idx] = prob[l_idx]
            self.alias[l_idx] = g_idx

            # Transfer excess probability from large to small
            prob[g_idx] = (prob[g_idx] + prob[l_idx]) - 1.0

            if prob[g_idx] < 1.0:
                small.append(g_idx)
            else:
                large.append(g_idx)

        # Handle remaining items (due to floating point errors)
        for g in large:
            self.prob[g] = 1.0
        for s_idx in small:
            self.prob[s_idx] = 1.0

    def select(self) -> T:
        """
        Select a random item according to the weight distribution.

        Returns:
            A randomly selected item

        Time Complexity: O(1)
        """
        # Pick a random index
        i = random.randint(0, self.n - 1)

        # Flip a biased coin
        if random.random() < self.prob[i]:
            return self.items[i]
        else:
            return self.items[self.alias[i]]

    def select_multiple(self, count: int, allow_duplicates: bool = False) -> list[T]:
        """
        Select multiple items.

        Args:
            count: Number of items to select
            allow_duplicates: Whether to allow same item multiple times

        Returns:
            List of selected items. If allow_duplicates=False and fewer
            unique items are available than requested, returns all available.

        Note:
            When allow_duplicates=False, items are identified by:
            1. caption_id attribute (for Caption objects)
            2. "caption_id" key (for dicts)
            3. Python object id (fallback)
        """
        if allow_duplicates:
            return [self.select() for _ in range(count)]

        # No duplicates - track selected items
        selected: list[T] = []
        selected_ids: set[Any] = set()

        # Use higher retry count to ensure we can find unique items
        max_attempts = count * 20

        for _ in range(max_attempts):
            if len(selected) >= count:
                break

            item = self.select()

            # Get unique identifier for the item
            item_id = self._get_item_id(item)

            if item_id not in selected_ids:
                selected.append(item)
                selected_ids.add(item_id)

        return selected

    @staticmethod
    def _get_item_id(item: Any) -> Any:
        """
        Get a unique identifier for an item.

        Supports Caption objects, dicts with caption_id, and fallback to id().
        """
        # Try object attribute first (Caption dataclass)
        if hasattr(item, "caption_id"):
            return item.caption_id
        # Try dict key (JSON-like structures)
        if isinstance(item, dict) and "caption_id" in item:
            return item["caption_id"]
        # Fallback to Python object identity
        return id(item)
