"""
Wave 2 Timing Test Suite - Jitter Avoidance Verification.

Tests the apply_time_jitter function to ensure:
- Round minutes (00, 15, 30, 45) are never produced
- Jitter is deterministic for same inputs
- Jitter offset stays within bounds (-7 to +8 minutes)

Run with: pytest python/tests/test_timing.py -v
"""

import pytest
from datetime import datetime, timedelta
from typing import Final

from ..orchestration.timing_optimizer import apply_time_jitter


# =============================================================================
# CONSTANTS
# =============================================================================

ROUND_MINUTES: Final[list[int]] = [0, 15, 30, 45]


# =============================================================================
# TEST CLASS: JITTER AVOIDANCE
# =============================================================================


class TestJitterAvoidance:
    """
    Verify jitter never lands on round minutes.

    Tests ensure that apply_time_jitter() produces timestamps that:
    1. Avoid automation-looking round minutes (:00, :15, :30, :45)
    2. Are deterministic (same inputs = same output)
    3. Stay within the defined jitter range (-7 to +8 minutes)
    """

    @pytest.mark.parametrize("creator_id", ['test_1', 'test_2', 'test_3', 'test_4', 'test_5'])
    @pytest.mark.parametrize("hour", range(24))
    def test_jitter_avoids_round_minutes(self, creator_id: str, hour: int) -> None:
        """
        Test jitter across multiple creators and hours.

        Verifies that for any creator_id and hour combination, the resulting
        jittered time never falls on a round minute (:00, :15, :30, :45).

        Args:
            creator_id: Unique identifier for the creator.
            hour: Hour of the day (0-23).

        Note:
            This parameterized test creates 120 test cases (5 creators x 24 hours).
        """
        base_time = datetime(2025, 1, 15, hour, 30)  # Start at :30
        jittered = apply_time_jitter(base_time, creator_id)

        assert jittered.minute not in ROUND_MINUTES, (
            f"Jitter landed on round minute: {jittered.minute} "
            f"for creator '{creator_id}' at hour {hour}"
        )

    def test_jitter_is_deterministic(self) -> None:
        """
        Same creator_id + same time = same jitter output.

        Verifies that calling apply_time_jitter with identical inputs
        produces identical outputs, ensuring reproducible schedules.
        """
        base_time = datetime(2025, 1, 15, 14, 30)
        creator_id = 'determinism_test'

        result1 = apply_time_jitter(base_time, creator_id)
        result2 = apply_time_jitter(base_time, creator_id)

        assert result1 == result2, (
            f"Jitter should be deterministic for same inputs. "
            f"Got {result1} and {result2}"
        )

    def test_jitter_range(self) -> None:
        """
        Test 100 different creator IDs to verify jitter offset bounds.

        Verifies that the jitter offset applied to the base time stays
        within the acceptable range of -7 to +8 minutes.
        """
        base_time = datetime(2025, 1, 15, 14, 30)

        for i in range(100):
            creator_id = f'range_test_{i}'
            jittered = apply_time_jitter(base_time, creator_id)

            diff_minutes = (jittered - base_time).total_seconds() / 60

            assert -7 <= diff_minutes <= 8, (
                f"Jitter out of range for creator '{creator_id}': "
                f"{diff_minutes} minutes (expected -7 to +8)"
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
