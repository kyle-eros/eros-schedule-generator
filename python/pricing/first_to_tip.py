"""
First To Tip Price Rotator for EROS Schedule Generator.

This module implements price rotation logic for first-to-tip send types
to prevent predictability and maintain subscriber engagement through
varied pricing strategies.
"""

from __future__ import annotations

import random


class FirstToTipPriceRotator:
    """Rotates first-to-tip prices through a varied pool to prevent predictability.

    The rotator maintains a history of recently used prices and excludes them
    from selection to ensure variety. This prevents subscribers from anticipating
    pricing patterns and maintains engagement.

    Attributes:
        PRICE_POOL: Class-level list of available price points.
        creator_id: The creator this rotator is associated with.
        last_prices: History of recently selected prices.

    Example:
        >>> rotator = FirstToTipPriceRotator("creator_123")
        >>> price = rotator.get_next_price()
        >>> context = rotator.get_price_with_context()
        >>> print(context["price"], context["variation_note"])
    """

    PRICE_POOL: list[int] = [20, 25, 30, 35, 40, 50, 60]

    def __init__(self, creator_id: str) -> None:
        """Initialize the price rotator for a specific creator.

        Args:
            creator_id: Unique identifier for the creator. Used for tracking
                and potential future personalization of pricing strategies.
        """
        self.creator_id = creator_id
        self.last_prices: list[int] = []

    def get_next_price(self) -> int:
        """Select the next price from the pool, excluding recent selections.

        The algorithm excludes the last 2 prices used from the available pool
        to ensure variety. If exclusion leaves no available prices, the pool
        resets to include all options.

        Returns:
            The selected price as an integer.

        Example:
            >>> rotator = FirstToTipPriceRotator("creator_123")
            >>> price1 = rotator.get_next_price()
            >>> price2 = rotator.get_next_price()
            >>> # price2 will not equal price1 or the price before it
        """
        # Determine prices to exclude (last 2 used)
        excluded_prices = set(self.last_prices[-2:]) if len(self.last_prices) >= 2 else set(self.last_prices)

        # Filter available prices
        available_prices = [p for p in self.PRICE_POOL if p not in excluded_prices]

        # Reset to full pool if no prices available after exclusion
        if not available_prices:
            available_prices = self.PRICE_POOL.copy()

        # Select randomly from available prices
        selected_price = random.choice(available_prices)

        # Track in history, keeping only last 5 prices
        self.last_prices.append(selected_price)
        if len(self.last_prices) > 5:
            self.last_prices = self.last_prices[-5:]

        return selected_price

    def get_price_with_context(self) -> dict[str, int | list[int] | str]:
        """Get the next price along with contextual information.

        Provides the selected price with additional metadata including
        recent price history and a variation note describing the selection
        strategy.

        Returns:
            A dictionary containing:
                - price: The selected price as an integer.
                - recent_prices: List of the last 3 prices used (may be fewer
                    if history is short).
                - variation_note: A string describing the variation strategy.

        Example:
            >>> rotator = FirstToTipPriceRotator("creator_123")
            >>> context = rotator.get_price_with_context()
            >>> print(context)
            {'price': 35, 'recent_prices': [35], 'variation_note': 'Price rotated...'}
        """
        selected_price = self.get_next_price()

        # Get last 3 prices for context (includes the just-selected price)
        recent_prices = self.last_prices[-3:] if len(self.last_prices) >= 3 else self.last_prices.copy()

        # Generate variation note based on context
        excluded_count = min(2, len(self.last_prices) - 1)
        if excluded_count > 0:
            variation_note = (
                f"Price rotated from pool of {len(self.PRICE_POOL)} options, "
                f"excluding last {excluded_count} price(s) to prevent predictability."
            )
        else:
            variation_note = (
                f"Price selected from full pool of {len(self.PRICE_POOL)} options."
            )

        return {
            "price": selected_price,
            "recent_prices": recent_prices,
            "variation_note": variation_note,
        }


__all__ = ["FirstToTipPriceRotator"]
