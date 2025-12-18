"""
Followup timing window generator for PPV sends.

This module implements intelligent timing calculations for PPV followup messages
using truncated normal distributions to achieve optimal engagement timing while
respecting day boundary constraints.

Key Features:
- Truncated normal distribution centered at 28-minute sweet spot
- Deterministic seeding for reproducible results per creator/time combination
- Day boundary handling with configurable next-day allowance
- Validation utilities for window verification

Algorithm Details:
- Uses Box-Muller transform for normal distribution sampling
- Rejection sampling with fallback to uniform distribution
- Default window: 15-45 minutes, mean at 28 minutes, std_dev of 8
"""

import hashlib
import math
import random
from datetime import datetime, timedelta
from typing import Any


# Optimal timing constants based on engagement analysis
OPTIMAL_FOLLOWUP_MINUTES: int = 28
DEFAULT_STD_DEV: float = 8.0
DEFAULT_MIN_OFFSET: int = 15
DEFAULT_MAX_OFFSET: int = 45
MAX_REJECTION_ATTEMPTS: int = 100


def _truncated_normal_sample(
    rng: random.Random,
    mean: float,
    std_dev: float,
    min_val: float,
    max_val: float,
    max_attempts: int = MAX_REJECTION_ATTEMPTS
) -> float:
    """
    Sample from a truncated normal distribution using rejection sampling.

    Uses the Box-Muller transform to generate normally distributed values,
    then applies rejection sampling to enforce bounds. Falls back to uniform
    distribution if rejection sampling fails after max_attempts.

    Args:
        rng: Seeded random.Random instance for deterministic sampling
        mean: Center of the normal distribution
        std_dev: Standard deviation of the distribution
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        max_attempts: Maximum rejection attempts before uniform fallback

    Returns:
        A float value within [min_val, max_val] following truncated normal
        distribution (or uniform if rejection sampling exhausted)

    Examples:
        >>> rng = random.Random(42)
        >>> sample = _truncated_normal_sample(rng, 28.0, 8.0, 15.0, 45.0)
        >>> 15.0 <= sample <= 45.0
        True
    """
    for _ in range(max_attempts):
        # Box-Muller transform: generate two uniform samples
        u1 = rng.random()
        u2 = rng.random()

        # Avoid log(0) edge case
        if u1 == 0.0:
            u1 = 1e-10

        # Box-Muller formula for standard normal
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

        # Scale to desired mean and standard deviation
        sample = mean + z * std_dev

        # Accept if within bounds (rejection sampling)
        if min_val <= sample <= max_val:
            return sample

    # Fallback: uniform distribution if rejection sampling exhausted
    return rng.uniform(min_val, max_val)


def _create_deterministic_seed(creator_id: str, parent_time: datetime) -> int:
    """
    Create a deterministic seed from creator_id and parent PPV time.

    Generates a reproducible integer seed that ensures the same creator
    and parent time combination always produces the same followup offset.
    This enables schedule reproducibility while maintaining statistical
    distribution properties.

    Args:
        creator_id: Unique identifier for the creator
        parent_time: Datetime of the parent PPV send

    Returns:
        Integer seed derived from SHA-256 hash of combined inputs

    Examples:
        >>> seed1 = _create_deterministic_seed("creator_123", datetime(2025, 1, 15, 14, 30))
        >>> seed2 = _create_deterministic_seed("creator_123", datetime(2025, 1, 15, 14, 30))
        >>> seed1 == seed2
        True
    """
    # Format: creator_id:YYYY-MM-DD:HH:MM
    seed_string = f"{creator_id}:{parent_time.strftime('%Y-%m-%d:%H:%M')}"

    # SHA-256 hash for uniform distribution of seed values
    hash_bytes = hashlib.sha256(seed_string.encode('utf-8')).digest()

    # Convert first 8 bytes to integer for seeding
    seed_int = int.from_bytes(hash_bytes[:8], byteorder='big')

    return seed_int


def schedule_ppv_followup(
    parent_ppv_time: datetime,
    creator_id: str,
    min_offset: int = DEFAULT_MIN_OFFSET,
    max_offset: int = DEFAULT_MAX_OFFSET,
    allow_next_day: bool = False
) -> datetime:
    """
    Calculate optimal followup time for a PPV send using truncated normal distribution.

    Generates a followup datetime that is statistically likely to fall near the
    28-minute optimal engagement window while providing variety across the
    specified range. The algorithm is deterministic given the same inputs.

    Day Boundary Handling:
    - If followup would cross midnight and allow_next_day=False:
      - Clamps followup to 23:59:00 of the same day
      - Raises ValueError if clamped time is < min_offset from parent

    Args:
        parent_ppv_time: Datetime of the parent PPV send
        creator_id: Unique identifier for the creator (used for deterministic seeding)
        min_offset: Minimum minutes after parent (default: 15)
        max_offset: Maximum minutes after parent (default: 45)
        allow_next_day: Whether followup can be scheduled after midnight (default: False)

    Returns:
        Datetime for the followup send within the specified window

    Raises:
        ValueError: If the gap would be less than min_offset after day boundary clamping

    Examples:
        >>> parent = datetime(2025, 1, 15, 14, 30, 0)
        >>> followup = schedule_ppv_followup(parent, "creator_123")
        >>> isinstance(followup, datetime)
        True
        >>> 15 <= (followup - parent).total_seconds() / 60 <= 45
        True

        >>> # Late night parent - will clamp to 23:59
        >>> late_parent = datetime(2025, 1, 15, 23, 50, 0)
        >>> followup = schedule_ppv_followup(late_parent, "creator_123")
        >>> followup.hour == 23 and followup.minute == 59
        True
    """
    # Create deterministic RNG from creator and time
    seed = _create_deterministic_seed(creator_id, parent_ppv_time)
    rng = random.Random(seed)

    # Sample offset using truncated normal distribution
    offset_minutes = _truncated_normal_sample(
        rng=rng,
        mean=float(OPTIMAL_FOLLOWUP_MINUTES),
        std_dev=DEFAULT_STD_DEV,
        min_val=float(min_offset),
        max_val=float(max_offset)
    )

    # Calculate raw followup time
    followup_time = parent_ppv_time + timedelta(minutes=offset_minutes)

    # Handle day boundary crossing
    if not allow_next_day and followup_time.date() > parent_ppv_time.date():
        # Clamp to 23:59:00 of the parent day
        end_of_day = parent_ppv_time.replace(hour=23, minute=59, second=0, microsecond=0)
        followup_time = end_of_day

        # Validate minimum gap is still achievable
        actual_gap_minutes = (followup_time - parent_ppv_time).total_seconds() / 60

        if actual_gap_minutes < min_offset:
            raise ValueError(
                f"Cannot schedule followup: gap of {actual_gap_minutes:.1f} minutes "
                f"is less than minimum required {min_offset} minutes after "
                f"clamping to day boundary (23:59). Parent time: {parent_ppv_time.isoformat()}"
            )

    return followup_time


def validate_followup_window(
    parent_time: datetime,
    followup_time: datetime,
    min_offset: int = DEFAULT_MIN_OFFSET,
    max_offset: int = DEFAULT_MAX_OFFSET
) -> dict[str, Any]:
    """
    Validate that a followup time falls within the acceptable window.

    Checks whether the gap between parent and followup times meets the
    configured timing constraints. Returns detailed validation results
    including the actual gap and any constraint violations.

    Args:
        parent_time: Datetime of the parent PPV send
        followup_time: Datetime of the proposed followup
        min_offset: Minimum acceptable gap in minutes (default: 15)
        max_offset: Maximum acceptable gap in minutes (default: 45)

    Returns:
        Dictionary with validation result:
            - 'is_valid': bool - Whether the followup timing is valid
            - 'gap_minutes': float - Actual gap between parent and followup
            - 'error': str - Error message (only present if invalid)

    Examples:
        >>> parent = datetime(2025, 1, 15, 14, 30, 0)
        >>> valid_followup = datetime(2025, 1, 15, 15, 0, 0)  # 30 min gap
        >>> result = validate_followup_window(parent, valid_followup)
        >>> result['is_valid']
        True
        >>> result['gap_minutes']
        30.0

        >>> early_followup = datetime(2025, 1, 15, 14, 40, 0)  # 10 min gap
        >>> result = validate_followup_window(parent, early_followup)
        >>> result['is_valid']
        False
        >>> 'error' in result
        True
    """
    # Calculate gap in minutes
    delta = followup_time - parent_time
    gap_minutes = delta.total_seconds() / 60

    # Check for followup before parent (negative gap)
    if gap_minutes < 0:
        return {
            'is_valid': False,
            'gap_minutes': gap_minutes,
            'error': f"Followup time ({followup_time.isoformat()}) is before "
                     f"parent time ({parent_time.isoformat()})"
        }

    # Check minimum offset constraint
    if gap_minutes < min_offset:
        return {
            'is_valid': False,
            'gap_minutes': gap_minutes,
            'error': f"Gap of {gap_minutes:.1f} minutes is less than minimum "
                     f"required {min_offset} minutes"
        }

    # Check maximum offset constraint
    if gap_minutes > max_offset:
        return {
            'is_valid': False,
            'gap_minutes': gap_minutes,
            'error': f"Gap of {gap_minutes:.1f} minutes exceeds maximum "
                     f"allowed {max_offset} minutes"
        }

    # All validations passed
    return {
        'is_valid': True,
        'gap_minutes': gap_minutes
    }


__all__ = [
    # Constants
    'OPTIMAL_FOLLOWUP_MINUTES',
    'DEFAULT_STD_DEV',
    'DEFAULT_MIN_OFFSET',
    'DEFAULT_MAX_OFFSET',
    'MAX_REJECTION_ATTEMPTS',
    # Main functions
    'schedule_ppv_followup',
    'validate_followup_window',
    # Helper functions (exposed for testing)
    '_truncated_normal_sample',
    '_create_deterministic_seed',
]
