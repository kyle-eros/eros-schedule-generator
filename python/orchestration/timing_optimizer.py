"""
Time jitter optimization for schedule generation.

Implements deterministic time jitter with round minute avoidance to create
more natural-looking post schedules. Round minutes (00, 15, 30, 45) are
avoided as they appear automated and may negatively impact engagement.

This module enforces:
- Deterministic jitter: Same inputs always produce the same output
- Round minute avoidance: Final times never land on :00, :15, :30, :45
- Bounded jitter: Offsets range from -7 to +8 minutes

Algorithm Overview:
    1. Create deterministic seed from creator_id and base_time
    2. Generate list of valid offsets that avoid round minutes
    3. Use seeded RNG to select offset from valid options
    4. Apply offset to base_time and return adjusted datetime

Example:
    >>> from datetime import datetime
    >>> base = datetime(2025, 1, 15, 14, 30)  # 2:30 PM (round minute)
    >>> result = apply_time_jitter(base, "creator_123")
    >>> result.minute  # Will NOT be 0, 15, 30, or 45
    33
"""

from __future__ import annotations

import hashlib
import random
import time
from datetime import datetime, timedelta
from typing import Final

from python.logging_config import get_logger, log_operation_start, log_operation_end
from python.observability.metrics import get_metrics, timed

# Module logger
logger = get_logger(__name__)

# Round minutes to avoid - these look automated
ROUND_MINUTES: Final[frozenset[int]] = frozenset({0, 15, 30, 45})

# Jitter bounds (inclusive)
JITTER_MIN: Final[int] = -7
JITTER_MAX: Final[int] = 8

# Fallback offsets when all normal offsets would land on round minutes
# This is mathematically rare but possible when base minute is certain values
FALLBACK_OFFSETS: Final[tuple[int, ...]] = (1, 2, -1, -2, 3, -3)


def _create_deterministic_seed(creator_id: str, base_time: datetime) -> int:
    """
    Create a deterministic seed from creator_id and base_time.

    The seed ensures that the same creator and time always produce the same
    jitter offset, making schedule generation reproducible.

    Args:
        creator_id: Unique identifier for the creator.
        base_time: The base datetime to apply jitter to.

    Returns:
        An integer seed derived from MD5 hash of the combined string.

    Examples:
        >>> from datetime import datetime
        >>> seed1 = _create_deterministic_seed("alice", datetime(2025, 1, 15, 14, 30))
        >>> seed2 = _create_deterministic_seed("alice", datetime(2025, 1, 15, 14, 30))
        >>> seed1 == seed2
        True
        >>> seed3 = _create_deterministic_seed("bob", datetime(2025, 1, 15, 14, 30))
        >>> seed1 == seed3
        False
    """
    seed_string = f"{creator_id}:{base_time.strftime('%Y-%m-%d:%H:%M')}"
    hash_hex = hashlib.md5(seed_string.encode()).hexdigest()[:8]
    return int(hash_hex, 16)


def _get_valid_offsets(base_minute: int) -> list[int]:
    """
    Get list of valid jitter offsets that avoid round minutes.

    Calculates which offsets in the range [JITTER_MIN, JITTER_MAX] will
    result in a non-round minute when added to base_minute.

    Args:
        base_minute: The minute component (0-59) of the base time.

    Returns:
        List of valid offset integers. May be empty if all offsets
        would land on round minutes (edge case).

    Examples:
        >>> offsets = _get_valid_offsets(30)  # Starting at :30
        >>> 0 not in offsets  # 30 + 0 = 30 (round)
        True
        >>> -15 not in offsets  # -15 not in range anyway
        True
        >>> 3 in offsets  # 30 + 3 = 33 (valid)
        True

        >>> offsets = _get_valid_offsets(14)  # Starting at :14
        >>> 1 in offsets  # 14 + 1 = 15 (round, invalid)
        False
        >>> 2 in offsets  # 14 + 2 = 16 (valid)
        True
    """
    valid_offsets: list[int] = []

    for offset in range(JITTER_MIN, JITTER_MAX + 1):
        resulting_minute = (base_minute + offset) % 60
        if resulting_minute not in ROUND_MINUTES:
            valid_offsets.append(offset)

    return valid_offsets


def _get_fallback_offset(base_minute: int) -> int:
    """
    Get a fallback offset when standard range yields no valid options.

    This handles the edge case where all offsets in [-7, +8] would land
    on round minutes. This is mathematically rare but we handle it for
    robustness.

    Args:
        base_minute: The minute component (0-59) of the base time.

    Returns:
        A valid offset that avoids round minutes.

    Raises:
        RuntimeError: If no valid fallback exists (should be impossible
            given the math, but included for safety).

    Examples:
        >>> offset = _get_fallback_offset(44)
        >>> (44 + offset) % 60 not in {0, 15, 30, 45}
        True
    """
    for offset in FALLBACK_OFFSETS:
        resulting_minute = (base_minute + offset) % 60
        if resulting_minute not in ROUND_MINUTES:
            return offset

    # This should be mathematically impossible, but defensive programming
    raise RuntimeError(
        f"No valid fallback offset found for minute {base_minute}. "
        "This indicates a bug in the algorithm."
    )


@timed("timing.apply_jitter", log_slow_threshold_ms=10)
def apply_time_jitter(base_time: datetime, creator_id: str) -> datetime:
    """
    Apply deterministic time jitter to a base time, avoiding round minutes.

    This function adds a small offset (-7 to +8 minutes) to the base time
    to make posting schedules appear more natural. The offset is deterministic,
    meaning the same creator_id and base_time will always produce the same
    result.

    Round minutes (00, 15, 30, 45) are avoided as they appear automated
    and may negatively impact engagement.

    Args:
        base_time: The original scheduled datetime.
        creator_id: Unique identifier for the creator. Used to seed the
            random number generator for deterministic results.

    Returns:
        A datetime with jitter applied. The minute component will never
        be 0, 15, 30, or 45.

    Invariants:
        - Deterministic: Same inputs always produce the same output
        - Round minute avoidance: result.minute not in {0, 15, 30, 45}
        - Bounded offset: Offset is typically in range [-7, +8] minutes

    Edge Cases:
        - base_time at :00, :15, :30, :45: Will be shifted away
        - base_time at :59: May wrap to next hour
        - base_time at :07 or :52: May have limited valid offsets

    Examples:
        >>> from datetime import datetime

        >>> # Basic usage
        >>> base = datetime(2025, 1, 15, 14, 30)
        >>> result = apply_time_jitter(base, "creator_123")
        >>> result.minute not in {0, 15, 30, 45}
        True

        >>> # Determinism - same inputs = same output
        >>> result1 = apply_time_jitter(base, "creator_123")
        >>> result2 = apply_time_jitter(base, "creator_123")
        >>> result1 == result2
        True

        >>> # Different creators get different jitter
        >>> result_a = apply_time_jitter(base, "alice")
        >>> result_b = apply_time_jitter(base, "bob")
        >>> # Results may differ (not guaranteed, but highly likely)

        >>> # Edge case - time at :59 may wrap to next hour
        >>> late = datetime(2025, 1, 15, 14, 59)
        >>> result = apply_time_jitter(late, "creator_123")
        >>> result.minute not in {0, 15, 30, 45}
        True
    """
    # Create deterministic seed
    seed = _create_deterministic_seed(creator_id, base_time)
    rng = random.Random(seed)

    # Get valid offsets for this base minute
    base_minute = base_time.minute
    valid_offsets = _get_valid_offsets(base_minute)

    # Handle edge case where all standard offsets land on round minutes
    if not valid_offsets:
        offset = _get_fallback_offset(base_minute)
        logger.debug(
            "Using fallback offset for jitter",
            extra={
                "base_minute": base_minute,
                "offset": offset,
                "creator_id": creator_id,
            }
        )
    else:
        offset = rng.choice(valid_offsets)

    result = base_time + timedelta(minutes=offset)

    logger.debug(
        "Applied time jitter",
        extra={
            "creator_id": creator_id,
            "base_time": base_time.isoformat(),
            "result_time": result.isoformat(),
            "offset_minutes": offset,
            "valid_offset_count": len(valid_offsets) if valid_offsets else 0,
        }
    )

    # Apply offset and return
    return result


def validate_jitter_result(jittered_time: datetime) -> bool:
    """
    Validate that a jittered time does not fall on a round minute.

    Utility function for testing and validation.

    Args:
        jittered_time: A datetime that has had jitter applied.

    Returns:
        True if the time is valid (not on a round minute), False otherwise.

    Examples:
        >>> from datetime import datetime
        >>> validate_jitter_result(datetime(2025, 1, 15, 14, 33))
        True
        >>> validate_jitter_result(datetime(2025, 1, 15, 14, 30))
        False
    """
    return jittered_time.minute not in ROUND_MINUTES


def get_jitter_stats(base_time: datetime, creator_id: str) -> dict[str, int | datetime]:
    """
    Get detailed statistics about the jitter applied to a time.

    Useful for debugging and understanding jitter behavior.

    Args:
        base_time: The original scheduled datetime.
        creator_id: Unique identifier for the creator.

    Returns:
        Dictionary containing:
            - 'base_time': Original datetime
            - 'jittered_time': Datetime with jitter applied
            - 'offset_minutes': The offset that was applied
            - 'base_minute': Original minute component
            - 'result_minute': Final minute component
            - 'valid_offset_count': How many valid offsets were available

    Examples:
        >>> from datetime import datetime
        >>> stats = get_jitter_stats(datetime(2025, 1, 15, 14, 30), "creator_123")
        >>> stats['base_minute']
        30
        >>> stats['result_minute'] not in {0, 15, 30, 45}
        True
    """
    jittered = apply_time_jitter(base_time, creator_id)
    offset = int((jittered - base_time).total_seconds() / 60)
    valid_offsets = _get_valid_offsets(base_time.minute)

    return {
        'base_time': base_time,
        'jittered_time': jittered,
        'offset_minutes': offset,
        'base_minute': base_time.minute,
        'result_minute': jittered.minute,
        'valid_offset_count': len(valid_offsets) if valid_offsets else 0,
    }


__all__ = [
    # Constants
    'ROUND_MINUTES',
    'JITTER_MIN',
    'JITTER_MAX',
    # Main function
    'apply_time_jitter',
    # Utilities
    'validate_jitter_result',
    'get_jitter_stats',
]
