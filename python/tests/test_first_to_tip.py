"""
Unit tests for FirstToTipPriceRotator.

Tests the price rotation logic for first-to-tip send types, ensuring:
- Price pool contains expected values
- Rotation excludes recently used prices
- Context information is accurate
- Rotation prevents predictability over multiple calls

Run with: pytest python/tests/test_first_to_tip.py -v
"""

from __future__ import annotations

from collections import Counter
from typing import Final

import pytest

from ..pricing.first_to_tip import FirstToTipPriceRotator


# =============================================================================
# CONSTANTS
# =============================================================================

EXPECTED_PRICE_POOL: Final[list[int]] = [20, 25, 30, 35, 40, 50, 60]
EXPECTED_POOL_SIZE: Final[int] = 7
EXCLUSION_COUNT: Final[int] = 2


# =============================================================================
# TEST CLASS: PRICE POOL CONFIGURATION
# =============================================================================


class TestPricePoolConfiguration:
    """
    Verify PRICE_POOL class attribute contains expected values.

    Tests ensure that the price pool is correctly configured with
    the expected price points for first-to-tip sends.
    """

    def test_price_pool_contains_expected_values(self) -> None:
        """
        Verify PRICE_POOL contains all expected price points.

        The price pool should contain exactly [20, 25, 30, 35, 40, 50, 60]
        as the valid price points for first-to-tip pricing.
        """
        assert FirstToTipPriceRotator.PRICE_POOL == EXPECTED_PRICE_POOL, (
            f"Expected price pool {EXPECTED_PRICE_POOL}, "
            f"got {FirstToTipPriceRotator.PRICE_POOL}"
        )

    def test_price_pool_size(self) -> None:
        """
        Verify PRICE_POOL has expected number of elements.

        The pool should contain exactly 7 price options.
        """
        assert len(FirstToTipPriceRotator.PRICE_POOL) == EXPECTED_POOL_SIZE, (
            f"Expected {EXPECTED_POOL_SIZE} prices in pool, "
            f"got {len(FirstToTipPriceRotator.PRICE_POOL)}"
        )

    def test_price_pool_is_sorted(self) -> None:
        """
        Verify PRICE_POOL is in ascending order.

        Prices should be sorted for predictable configuration.
        """
        pool = FirstToTipPriceRotator.PRICE_POOL
        assert pool == sorted(pool), (
            f"Price pool should be sorted ascending, got {pool}"
        )

    def test_price_pool_contains_only_positive_integers(self) -> None:
        """
        Verify all prices in pool are positive integers.

        Each price must be a positive integer for valid pricing.
        """
        for price in FirstToTipPriceRotator.PRICE_POOL:
            assert isinstance(price, int), (
                f"Price {price} should be an integer, got {type(price)}"
            )
            assert price > 0, f"Price {price} should be positive"

    def test_price_pool_has_no_duplicates(self) -> None:
        """
        Verify PRICE_POOL contains no duplicate values.

        Each price point should be unique.
        """
        pool = FirstToTipPriceRotator.PRICE_POOL
        assert len(pool) == len(set(pool)), (
            f"Price pool contains duplicates: {pool}"
        )


# =============================================================================
# TEST CLASS: GET_NEXT_PRICE METHOD
# =============================================================================


class TestGetNextPrice:
    """
    Verify get_next_price() returns valid prices with proper rotation.

    Tests ensure that:
    - Returned prices are from the pool
    - Recent prices are excluded from selection
    - Rotation handles full pool exhaustion gracefully
    """

    def test_returns_valid_price_from_pool(self) -> None:
        """
        Verify get_next_price returns a price that exists in PRICE_POOL.

        Each call should return a valid price from the configured pool.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        price = rotator.get_next_price()

        assert price in EXPECTED_PRICE_POOL, (
            f"Price {price} is not in expected pool {EXPECTED_PRICE_POOL}"
        )

    def test_returns_integer(self) -> None:
        """
        Verify get_next_price returns an integer type.

        Prices must be integers for proper handling.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        price = rotator.get_next_price()

        assert isinstance(price, int), (
            f"Expected int, got {type(price)}"
        )

    def test_excludes_last_price_on_second_call(self) -> None:
        """
        Verify the immediately previous price is excluded from selection.

        After one price is selected, it should not be selected on
        the next call (assuming pool has more than one option).
        """
        # Run multiple times to account for randomness
        for _ in range(50):
            rotator = FirstToTipPriceRotator("test_creator")
            first_price = rotator.get_next_price()
            second_price = rotator.get_next_price()

            assert first_price != second_price, (
                f"Second price {second_price} should not equal "
                f"first price {first_price}"
            )

    def test_excludes_last_two_prices_on_third_call(self) -> None:
        """
        Verify the last 2 prices are excluded from selection on third call.

        After two prices are selected, neither should be selected
        on the third call.
        """
        # Run multiple times to account for randomness
        for _ in range(50):
            rotator = FirstToTipPriceRotator("test_creator")
            first_price = rotator.get_next_price()
            second_price = rotator.get_next_price()
            third_price = rotator.get_next_price()

            excluded = {first_price, second_price}
            assert third_price not in excluded, (
                f"Third price {third_price} should not be in "
                f"excluded set {excluded}"
            )

    def test_maintains_history_limit(self) -> None:
        """
        Verify last_prices history is limited to 5 entries.

        The rotator should only keep track of the last 5 prices
        to prevent unbounded memory growth.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        # Make 10 price selections
        for _ in range(10):
            rotator.get_next_price()

        assert len(rotator.last_prices) == 5, (
            f"Expected history of 5, got {len(rotator.last_prices)}"
        )

    def test_tracks_prices_in_history(self) -> None:
        """
        Verify selected prices are added to last_prices history.

        Each call to get_next_price should append the selected
        price to the history.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        price1 = rotator.get_next_price()
        assert rotator.last_prices == [price1], (
            f"History should contain [{price1}], got {rotator.last_prices}"
        )

        price2 = rotator.get_next_price()
        assert rotator.last_prices == [price1, price2], (
            f"History should contain [{price1}, {price2}], "
            f"got {rotator.last_prices}"
        )

    def test_rotation_through_entire_pool(self) -> None:
        """
        Verify rotation can cycle through all prices in the pool.

        Over many selections, all prices should eventually be selected.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        seen_prices: set[int] = set()

        # Make enough selections to see all prices
        # With 7 prices and excluding 2, we need at least 7 calls
        for _ in range(100):
            price = rotator.get_next_price()
            seen_prices.add(price)

        assert seen_prices == set(EXPECTED_PRICE_POOL), (
            f"Expected to see all prices {set(EXPECTED_PRICE_POOL)}, "
            f"only saw {seen_prices}"
        )

    @pytest.mark.parametrize("creator_id", [
        "creator_1",
        "creator_2",
        "creator_long_name_test_123",
        "",
        "special!@#$%chars",
    ])
    def test_works_with_various_creator_ids(self, creator_id: str) -> None:
        """
        Verify get_next_price works with various creator ID formats.

        Args:
            creator_id: The creator identifier to test.

        The rotator should function correctly regardless of
        the creator ID format.
        """
        rotator = FirstToTipPriceRotator(creator_id)
        price = rotator.get_next_price()

        assert price in EXPECTED_PRICE_POOL, (
            f"Price {price} not in pool for creator '{creator_id}'"
        )


# =============================================================================
# TEST CLASS: GET_PRICE_WITH_CONTEXT METHOD
# =============================================================================


class TestGetPriceWithContext:
    """
    Verify get_price_with_context() returns accurate context information.

    Tests ensure the returned dictionary contains:
    - Valid price from pool
    - Accurate recent_prices list
    - Informative variation_note
    """

    def test_returns_dict_with_required_keys(self) -> None:
        """
        Verify returned dict contains price, recent_prices, variation_note.

        The context dictionary must have all expected keys.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        context = rotator.get_price_with_context()

        expected_keys = {"price", "recent_prices", "variation_note"}
        assert set(context.keys()) == expected_keys, (
            f"Expected keys {expected_keys}, got {set(context.keys())}"
        )

    def test_price_is_valid_integer(self) -> None:
        """
        Verify context price is a valid integer from the pool.

        The price value should be an integer from PRICE_POOL.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        context = rotator.get_price_with_context()

        assert isinstance(context["price"], int), (
            f"Price should be int, got {type(context['price'])}"
        )
        assert context["price"] in EXPECTED_PRICE_POOL, (
            f"Price {context['price']} not in pool"
        )

    def test_recent_prices_is_list(self) -> None:
        """
        Verify recent_prices is a list.

        The recent_prices value should be a list type.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        context = rotator.get_price_with_context()

        assert isinstance(context["recent_prices"], list), (
            f"recent_prices should be list, got {type(context['recent_prices'])}"
        )

    def test_recent_prices_contains_current_selection(self) -> None:
        """
        Verify recent_prices includes the just-selected price.

        The most recent price in the list should match the price key.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        context = rotator.get_price_with_context()

        assert context["price"] in context["recent_prices"], (
            f"Price {context['price']} should be in "
            f"recent_prices {context['recent_prices']}"
        )

    def test_recent_prices_max_three_entries(self) -> None:
        """
        Verify recent_prices contains at most 3 entries.

        The context should only show the last 3 prices for brevity.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        # Make 5 selections
        for _ in range(4):
            rotator.get_next_price()

        context = rotator.get_price_with_context()

        assert len(context["recent_prices"]) <= 3, (
            f"recent_prices should have max 3 entries, "
            f"got {len(context['recent_prices'])}"
        )

    def test_variation_note_is_string(self) -> None:
        """
        Verify variation_note is a string.

        The note should provide human-readable context.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        context = rotator.get_price_with_context()

        assert isinstance(context["variation_note"], str), (
            f"variation_note should be str, got {type(context['variation_note'])}"
        )

    def test_variation_note_mentions_pool_size(self) -> None:
        """
        Verify variation_note mentions the pool size.

        The note should include the number of options in the pool.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        context = rotator.get_price_with_context()

        assert str(EXPECTED_POOL_SIZE) in context["variation_note"], (
            f"Expected pool size {EXPECTED_POOL_SIZE} in note: "
            f"{context['variation_note']}"
        )

    def test_first_call_shows_full_pool_note(self) -> None:
        """
        Verify first call variation_note indicates full pool selection.

        On first call with no history, the note should indicate
        selection from the full pool.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        context = rotator.get_price_with_context()

        assert "full pool" in context["variation_note"].lower(), (
            f"First call should mention 'full pool': {context['variation_note']}"
        )

    def test_subsequent_calls_show_exclusion_in_note(self) -> None:
        """
        Verify subsequent calls mention exclusion in variation_note.

        After multiple calls, the note should indicate prices
        were excluded to prevent predictability.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        # First call to build history
        rotator.get_next_price()
        rotator.get_next_price()

        # Third call should show exclusion
        context = rotator.get_price_with_context()

        assert "excluding" in context["variation_note"].lower(), (
            f"Should mention exclusion: {context['variation_note']}"
        )

    def test_context_values_are_accurate_after_multiple_calls(self) -> None:
        """
        Verify context accuracy after multiple price selections.

        All context values should accurately reflect the current state.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        prices = []
        for _ in range(3):
            prices.append(rotator.get_next_price())

        context = rotator.get_price_with_context()
        prices.append(context["price"])

        # Verify price is valid
        assert context["price"] in EXPECTED_PRICE_POOL

        # Verify recent_prices matches last 3 selections
        assert context["recent_prices"] == prices[-3:], (
            f"Expected {prices[-3:]}, got {context['recent_prices']}"
        )


# =============================================================================
# TEST CLASS: ROTATION PREVENTS PREDICTABILITY
# =============================================================================


class TestRotationPreventsPredictability:
    """
    Verify price rotation prevents predictable patterns.

    Tests ensure that:
    - Price distribution is reasonably uniform over many calls
    - No single price dominates selections
    - Consecutive prices are never the same
    """

    def test_distribution_is_reasonably_uniform(self) -> None:
        """
        Verify price selection is reasonably uniform over many calls.

        Each price should be selected roughly equally, accounting
        for the exclusion logic which may slightly favor some prices.
        """
        rotator = FirstToTipPriceRotator("distribution_test")
        counts: Counter[int] = Counter()

        # Make 700 selections (100 per price expected)
        for _ in range(700):
            price = rotator.get_next_price()
            counts[price] += 1

        # Each price should be selected at least 50 times (50% of expected)
        # and at most 200 times (200% of expected)
        for price in EXPECTED_PRICE_POOL:
            assert 50 <= counts[price] <= 200, (
                f"Price {price} selected {counts[price]} times, "
                f"expected between 50 and 200. Distribution: {dict(counts)}"
            )

    def test_no_consecutive_repeats_over_many_calls(self) -> None:
        """
        Verify no price is ever selected consecutively.

        With 7 prices and 2 exclusions, consecutive repeats
        should never occur.
        """
        rotator = FirstToTipPriceRotator("consecutive_test")

        previous_price = rotator.get_next_price()

        for i in range(500):
            current_price = rotator.get_next_price()
            assert current_price != previous_price, (
                f"Consecutive repeat at iteration {i}: {current_price}"
            )
            previous_price = current_price

    def test_three_consecutive_prices_are_all_different(self) -> None:
        """
        Verify any three consecutive prices are all different.

        With 2 exclusions, we guarantee 3 different prices in a row.
        """
        rotator = FirstToTipPriceRotator("three_consecutive_test")

        for _ in range(100):
            # Get three consecutive prices
            p1 = rotator.get_next_price()
            p2 = rotator.get_next_price()
            p3 = rotator.get_next_price()

            three_prices = [p1, p2, p3]
            assert len(set(three_prices)) == 3, (
                f"Three consecutive prices should all differ: {three_prices}"
            )

    def test_different_creators_get_different_sequences(self) -> None:
        """
        Verify different creators get different price sequences.

        Random selection should produce different patterns for
        different creator IDs over many iterations.
        """
        rotator1 = FirstToTipPriceRotator("creator_a")
        rotator2 = FirstToTipPriceRotator("creator_b")

        sequence1 = [rotator1.get_next_price() for _ in range(20)]
        sequence2 = [rotator2.get_next_price() for _ in range(20)]

        # Sequences should differ in at least some positions
        # (extremely unlikely to be identical by chance)
        differences = sum(1 for a, b in zip(sequence1, sequence2) if a != b)

        assert differences > 0, (
            f"Different creators should have different sequences. "
            f"Both got: {sequence1}"
        )

    def test_same_creator_fresh_instance_different_sequence(self) -> None:
        """
        Verify fresh instances may produce different sequences.

        Due to randomness, a new rotator instance for the same
        creator should likely produce a different sequence.
        """
        sequences = []

        for _ in range(5):
            rotator = FirstToTipPriceRotator("same_creator")
            sequence = tuple(rotator.get_next_price() for _ in range(10))
            sequences.append(sequence)

        # At least 2 different sequences should exist
        unique_sequences = set(sequences)
        assert len(unique_sequences) >= 2, (
            f"Expected different sequences across instances, "
            f"only got {len(unique_sequences)} unique sequence(s)"
        )


# =============================================================================
# TEST CLASS: EDGE CASES
# =============================================================================


class TestEdgeCases:
    """
    Verify edge case handling in the price rotator.

    Tests cover boundary conditions and unusual scenarios.
    """

    def test_empty_creator_id(self) -> None:
        """
        Verify rotator works with empty creator ID.

        Empty string should be valid for creator_id.
        """
        rotator = FirstToTipPriceRotator("")
        price = rotator.get_next_price()

        assert price in EXPECTED_PRICE_POOL

    def test_creator_id_stored_correctly(self) -> None:
        """
        Verify creator_id is stored as instance attribute.

        The creator_id should be accessible after initialization.
        """
        creator_id = "test_creator_123"
        rotator = FirstToTipPriceRotator(creator_id)

        assert rotator.creator_id == creator_id

    def test_initial_last_prices_is_empty(self) -> None:
        """
        Verify last_prices starts empty.

        A fresh rotator should have no price history.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        assert rotator.last_prices == []

    def test_single_call_history(self) -> None:
        """
        Verify single call adds one entry to history.

        After one call, history should contain exactly one price.
        """
        rotator = FirstToTipPriceRotator("test_creator")
        price = rotator.get_next_price()

        assert len(rotator.last_prices) == 1
        assert rotator.last_prices[0] == price

    def test_history_sliding_window(self) -> None:
        """
        Verify history maintains sliding window of 5 prices.

        After more than 5 calls, oldest prices should be dropped.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        all_prices = []
        for _ in range(7):
            price = rotator.get_next_price()
            all_prices.append(price)

        # Should only keep last 5
        assert rotator.last_prices == all_prices[-5:], (
            f"Expected last 5 prices {all_prices[-5:]}, "
            f"got {rotator.last_prices}"
        )


# =============================================================================
# TEST CLASS: STATEFUL BEHAVIOR
# =============================================================================


class TestStatefulBehavior:
    """
    Verify stateful behavior across multiple operations.

    Tests that the rotator correctly maintains and uses state.
    """

    def test_state_persists_across_calls(self) -> None:
        """
        Verify state is maintained across multiple method calls.

        History should accumulate with each get_next_price call.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        for i in range(5):
            rotator.get_next_price()
            assert len(rotator.last_prices) == i + 1

    def test_context_call_affects_state(self) -> None:
        """
        Verify get_price_with_context affects internal state.

        The context method should also update the history.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        context = rotator.get_price_with_context()

        assert len(rotator.last_prices) == 1
        assert rotator.last_prices[0] == context["price"]

    def test_mixed_calls_maintain_consistent_state(self) -> None:
        """
        Verify mixed get_next_price and get_price_with_context calls.

        Both methods should update the same shared state.
        """
        rotator = FirstToTipPriceRotator("test_creator")

        p1 = rotator.get_next_price()
        ctx1 = rotator.get_price_with_context()
        p2 = rotator.get_next_price()
        ctx2 = rotator.get_price_with_context()

        expected_history = [p1, ctx1["price"], p2, ctx2["price"]]
        assert rotator.last_prices == expected_history


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
