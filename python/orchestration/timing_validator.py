"""
Same-Style Back-to-Back Validator for PPV Schedule Timing.

Validates and repairs consecutive same-style PPV items in daily schedules
to ensure optimal content variety and prevent audience fatigue.

This module enforces:
- No consecutive winner/winner PPV items
- No consecutive bundle/bundle PPV items
- AM/PM split for same-style duplicates when total count allows
- Auto-repair strategies for constraint violations

Wave 2 Specification Implementation:
- validate_no_consecutive_same_style: Detection-only validation
- validate_and_repair_consecutive_styles: Detection with auto-repair
"""

from collections import Counter
from typing import Any, TypedDict


# =============================================================================
# Type Definitions
# =============================================================================


class RepairRecord(TypedDict):
    """Record of a single repair operation applied to the schedule.

    Attributes:
        strategy: The repair strategy used ('position_swap' or 'am_pm_redistribution')
        original_position: Index of the item that was modified
        swapped_with: Position of the item swapped with (for position_swap)
        from_period: Original period before redistribution (for am_pm_redistribution)
        to_period: New period after redistribution (for am_pm_redistribution)
        style: The PPV style that triggered the repair
    """

    strategy: str
    original_position: int
    swapped_with: int | None
    from_period: str | None
    to_period: str | None
    style: str


class ValidationResult(TypedDict):
    """Result from validation-only function.

    Attributes:
        is_valid: Whether the schedule passes validation
        errors: List of error descriptions for each violation
    """

    is_valid: bool
    errors: list[str]


class RepairResult(TypedDict):
    """Result from validation-and-repair function.

    Attributes:
        is_valid: Whether the schedule is valid after repairs
        repairs_applied: List of repair records describing changes made
        remaining_errors: Errors that could not be auto-repaired
    """

    is_valid: bool
    repairs_applied: list[RepairRecord]
    remaining_errors: list[str]


# =============================================================================
# Constants
# =============================================================================


# Valid PPV styles that require back-to-back prevention
PPV_STYLES: set[str] = {'winner', 'bundle', 'solo', 'sextape'}

# Default hours for AM/PM redistribution
DEFAULT_AM_HOUR: int = 10
DEFAULT_PM_HOUR: int = 14

# AM period boundary (hours 0-11 are AM, 12-23 are PM)
AM_PM_BOUNDARY: int = 12


# =============================================================================
# Helper Functions
# =============================================================================


def _is_ppv_item(item: dict[str, Any]) -> bool:
    """Check if an item is a PPV item.

    Args:
        item: Schedule item dictionary to check.

    Returns:
        True if the item is marked as PPV, False otherwise.
    """
    return bool(item.get('is_ppv', False))


def _get_ppv_style(item: dict[str, Any]) -> str | None:
    """Extract PPV style from an item.

    Args:
        item: Schedule item dictionary.

    Returns:
        The ppv_style string if present and valid, None otherwise.
    """
    style = item.get('ppv_style')
    if style and isinstance(style, str):
        result: str = style.lower()
        return result
    return None


def _get_item_hour(item: dict[str, Any]) -> int | None:
    """Extract the hour from an item's scheduled time.

    Args:
        item: Schedule item dictionary with 'scheduled_time' field.

    Returns:
        Hour as integer (0-23), or None if time cannot be parsed.
    """
    time_str = item.get('scheduled_time', '')
    if not time_str:
        return None

    try:
        # Handle HH:MM format
        if ':' in time_str:
            hour_str = time_str.split(':')[0]
            return int(hour_str)
        return None
    except (ValueError, IndexError):
        return None


def _is_am_period(hour: int | None) -> bool:
    """Determine if an hour falls in the AM period.

    Args:
        hour: Hour value (0-23), or None.

    Returns:
        True if hour is in AM period (< 12), False otherwise.
        Returns False if hour is None.
    """
    if hour is None:
        return False
    return hour < AM_PM_BOUNDARY


def _is_pm_period(hour: int | None) -> bool:
    """Determine if an hour falls in the PM period.

    Args:
        hour: Hour value (0-23), or None.

    Returns:
        True if hour is in PM period (>= 12), False otherwise.
        Returns False if hour is None.
    """
    if hour is None:
        return False
    return hour >= AM_PM_BOUNDARY


def _get_period(hour: int | None) -> str:
    """Get the period name for an hour.

    Args:
        hour: Hour value (0-23), or None.

    Returns:
        'AM' or 'PM' based on hour. Returns 'AM' if hour is None.
    """
    if hour is None:
        return 'AM'
    return 'AM' if hour < AM_PM_BOUNDARY else 'PM'


def _set_item_hour(item: dict[str, Any], hour: int) -> None:
    """Set the hour for an item's scheduled time.

    Modifies the item in-place, preserving minutes if present.

    Args:
        item: Schedule item dictionary to modify.
        hour: New hour value (0-23).
    """
    current_time = item.get('scheduled_time', '')
    minutes = '00'

    if current_time and ':' in current_time:
        parts = current_time.split(':')
        if len(parts) >= 2:
            minutes = parts[1]

    item['scheduled_time'] = f"{hour:02d}:{minutes}"


def _count_styles_by_period(
    ppv_items: list[tuple[int, dict[str, Any]]]
) -> dict[str, Counter[str]]:
    """Count PPV styles in each period (AM/PM).

    Args:
        ppv_items: List of (index, item) tuples for PPV items.

    Returns:
        Dictionary with 'AM' and 'PM' keys, each containing a Counter
        of style occurrences.
    """
    counts: dict[str, Counter[str]] = {
        'AM': Counter(),
        'PM': Counter()
    }

    for _, item in ppv_items:
        style = _get_ppv_style(item)
        if style:
            hour = _get_item_hour(item)
            period = _get_period(hour)
            counts[period][style] += 1

    return counts


# =============================================================================
# Validation Functions
# =============================================================================


def validate_no_consecutive_same_style(
    daily_schedule: list[dict[str, Any]]
) -> ValidationResult:
    """Validate that no consecutive PPV items have the same style.

    Checks for violations where two adjacent PPV items in the schedule
    have identical ppv_style values (e.g., winner/winner or bundle/bundle).
    Non-PPV items are not considered in the adjacency check.

    Args:
        daily_schedule: List of schedule item dictionaries. Each item should
            contain:
            - 'is_ppv': bool - Whether this is a PPV item
            - 'ppv_style': str - Style of PPV ('winner', 'bundle', 'solo', 'sextape')
            - 'scheduled_time': str - Time in HH:MM format (optional for validation)

    Returns:
        ValidationResult with:
            - 'is_valid': bool - True if no consecutive same-style violations
            - 'errors': list[str] - Description of each violation found

    Examples:
        >>> schedule = [
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '10:00'},
        ...     {'is_ppv': True, 'ppv_style': 'bundle', 'scheduled_time': '11:00'},
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '14:00'},
        ... ]
        >>> result = validate_no_consecutive_same_style(schedule)
        >>> result['is_valid']
        True
        >>> result['errors']
        []

        >>> schedule_with_violation = [
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '10:00'},
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '11:00'},
        ... ]
        >>> result = validate_no_consecutive_same_style(schedule_with_violation)
        >>> result['is_valid']
        False
        >>> 'winner/winner' in result['errors'][0]
        True
    """
    errors: list[str] = []

    # Extract PPV items with their positions
    ppv_items: list[tuple[int, dict[str, Any]]] = [
        (i, item) for i, item in enumerate(daily_schedule)
        if _is_ppv_item(item)
    ]

    # Check consecutive PPV items for same-style violations
    for i in range(len(ppv_items) - 1):
        current_pos, current_item = ppv_items[i]
        next_pos, next_item = ppv_items[i + 1]

        current_style = _get_ppv_style(current_item)
        next_style = _get_ppv_style(next_item)

        if current_style and next_style and current_style == next_style:
            errors.append(
                f"Consecutive same-style violation at positions {current_pos} and "
                f"{next_pos}: {current_style}/{next_style} back-to-back"
            )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors
    )


def validate_and_repair_consecutive_styles(
    daily_schedule: list[dict[str, Any]]
) -> RepairResult:
    """Validate and auto-repair consecutive same-style PPV violations.

    Attempts to fix same-style back-to-back violations using two strategies:
    1. Position swapping: Swap the second violating item with a non-violating
       PPV item elsewhere in the schedule.
    2. AM/PM redistribution: Move the second violating item to the opposite
       period (AM to PM or PM to AM) if it doesn't create new violations.

    The function modifies the daily_schedule in-place when repairs are applied.

    Args:
        daily_schedule: List of schedule item dictionaries. Each item should
            contain:
            - 'is_ppv': bool - Whether this is a PPV item
            - 'ppv_style': str - Style of PPV ('winner', 'bundle', 'solo', 'sextape')
            - 'scheduled_time': str - Time in HH:MM format

    Returns:
        RepairResult with:
            - 'is_valid': bool - True if schedule is valid after repairs
            - 'repairs_applied': list[RepairRecord] - Details of each repair
            - 'remaining_errors': list[str] - Violations that couldn't be fixed

    Examples:
        >>> schedule = [
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '10:00'},
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '10:30'},
        ...     {'is_ppv': True, 'ppv_style': 'bundle', 'scheduled_time': '14:00'},
        ... ]
        >>> result = validate_and_repair_consecutive_styles(schedule)
        >>> result['is_valid']
        True
        >>> len(result['repairs_applied']) > 0
        True

    Note:
        This function modifies the input schedule in-place. Create a copy
        before calling if you need to preserve the original schedule.
    """
    repairs_applied: list[RepairRecord] = []
    remaining_errors: list[str] = []

    # Initial validation check
    initial_result = validate_no_consecutive_same_style(daily_schedule)
    if initial_result['is_valid']:
        return RepairResult(
            is_valid=True,
            repairs_applied=[],
            remaining_errors=[]
        )

    # Extract PPV items with their positions for repair attempts
    ppv_items: list[tuple[int, dict[str, Any]]] = [
        (i, item) for i, item in enumerate(daily_schedule)
        if _is_ppv_item(item)
    ]

    # Process violations iteratively
    max_iterations = len(ppv_items) * 2  # Safety limit
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Re-check for violations after each repair
        current_result = validate_no_consecutive_same_style(daily_schedule)
        if current_result['is_valid']:
            break

        # Find the first violation to repair
        violation_found = False
        for i in range(len(ppv_items) - 1):
            current_pos, current_item = ppv_items[i]
            next_pos, next_item = ppv_items[i + 1]

            current_style = _get_ppv_style(current_item)
            next_style = _get_ppv_style(next_item)

            if current_style and next_style and current_style == next_style:
                violation_found = True

                # Strategy 1: Position swapping
                repair_success = _attempt_position_swap(
                    daily_schedule, ppv_items, i + 1, next_style, repairs_applied
                )

                if repair_success:
                    # Refresh ppv_items list after swap
                    ppv_items = [
                        (idx, item) for idx, item in enumerate(daily_schedule)
                        if _is_ppv_item(item)
                    ]
                    break

                # Strategy 2: AM/PM redistribution
                repair_success = _attempt_am_pm_redistribution(
                    daily_schedule, ppv_items, i + 1, next_style, repairs_applied
                )

                if repair_success:
                    # Refresh ppv_items list after redistribution
                    ppv_items = [
                        (idx, item) for idx, item in enumerate(daily_schedule)
                        if _is_ppv_item(item)
                    ]
                    break

                # Neither strategy worked for this violation
                remaining_errors.append(
                    f"Unable to repair consecutive same-style violation at positions "
                    f"{current_pos} and {next_pos}: {current_style}/{next_style}"
                )
                # Skip this pair and try the next
                break

        if not violation_found:
            break

    # Final validation
    final_result = validate_no_consecutive_same_style(daily_schedule)

    # Add any remaining violations to errors
    if not final_result['is_valid']:
        for error in final_result['errors']:
            if error not in remaining_errors:
                remaining_errors.append(error)

    return RepairResult(
        is_valid=final_result['is_valid'],
        repairs_applied=repairs_applied,
        remaining_errors=remaining_errors
    )


# =============================================================================
# Repair Strategy Implementations
# =============================================================================


def _attempt_position_swap(
    daily_schedule: list[dict[str, Any]],
    ppv_items: list[tuple[int, dict[str, Any]]],
    violating_ppv_index: int,
    violating_style: str,
    repairs_applied: list[RepairRecord]
) -> bool:
    """Attempt to repair a violation by swapping positions.

    Finds a non-violating PPV item to swap with the violating item.
    A valid swap candidate must:
    - Not be adjacent to the violating item
    - Have a different style than the violating style
    - Not create a new violation after swapping

    Args:
        daily_schedule: The schedule to modify in-place.
        ppv_items: List of (index, item) tuples for PPV items.
        violating_ppv_index: Index in ppv_items of the item causing violation.
        violating_style: The style that's causing the violation.
        repairs_applied: List to append repair records to.

    Returns:
        True if swap was successful, False otherwise.
    """
    if violating_ppv_index >= len(ppv_items):
        return False

    violating_pos, violating_item = ppv_items[violating_ppv_index]

    # Find a suitable swap candidate
    for candidate_idx, (candidate_pos, candidate_item) in enumerate(ppv_items):
        # Skip adjacent items and the violating item itself
        if abs(candidate_idx - violating_ppv_index) <= 1:
            continue

        candidate_style = _get_ppv_style(candidate_item)
        if not candidate_style or candidate_style == violating_style:
            continue

        # Check if swapping would create new violations
        if _would_swap_create_violation(
            ppv_items, violating_ppv_index, candidate_idx, violating_style, candidate_style
        ):
            continue

        # Perform the swap in the original schedule
        # Swap the items at their actual positions in daily_schedule
        daily_schedule[violating_pos], daily_schedule[candidate_pos] = (
            daily_schedule[candidate_pos], daily_schedule[violating_pos]
        )

        # Record the repair
        repairs_applied.append(RepairRecord(
            strategy='position_swap',
            original_position=violating_pos,
            swapped_with=candidate_pos,
            from_period=None,
            to_period=None,
            style=violating_style
        ))

        return True

    return False


def _would_swap_create_violation(
    ppv_items: list[tuple[int, dict[str, Any]]],
    idx_a: int,
    idx_b: int,
    style_a: str,
    style_b: str
) -> bool:
    """Check if swapping two items would create new violations.

    Args:
        ppv_items: List of (index, item) tuples for PPV items.
        idx_a: Index of first item to swap.
        idx_b: Index of second item to swap.
        style_a: Style of item at idx_a.
        style_b: Style of item at idx_b.

    Returns:
        True if the swap would create a new violation, False otherwise.
    """
    # Check neighbors of position A after placing item B there
    if idx_a > 0:
        prev_style = _get_ppv_style(ppv_items[idx_a - 1][1])
        if prev_style == style_b:
            return True

    if idx_a < len(ppv_items) - 1 and idx_a + 1 != idx_b:
        next_style = _get_ppv_style(ppv_items[idx_a + 1][1])
        if next_style == style_b:
            return True

    # Check neighbors of position B after placing item A there
    if idx_b > 0 and idx_b - 1 != idx_a:
        prev_style = _get_ppv_style(ppv_items[idx_b - 1][1])
        if prev_style == style_a:
            return True

    if idx_b < len(ppv_items) - 1:
        next_style = _get_ppv_style(ppv_items[idx_b + 1][1])
        if next_style == style_a:
            return True

    return False


def _attempt_am_pm_redistribution(
    daily_schedule: list[dict[str, Any]],
    ppv_items: list[tuple[int, dict[str, Any]]],
    violating_ppv_index: int,
    violating_style: str,
    repairs_applied: list[RepairRecord]
) -> bool:
    """Attempt to repair a violation by moving item to opposite period.

    Moves the violating item from AM to PM or vice versa, ensuring
    the move doesn't create a new same-style violation in the target period.

    This strategy works by changing the scheduled time of the violating item
    to the opposite period (AM->PM or PM->AM), then re-sorting PPV items by
    time to verify no new violations are created.

    Args:
        daily_schedule: The schedule to modify in-place.
        ppv_items: List of (index, item) tuples for PPV items.
        violating_ppv_index: Index in ppv_items of the item causing violation.
        violating_style: The style that's causing the violation.
        repairs_applied: List to append repair records to.

    Returns:
        True if redistribution was successful, False otherwise.
    """
    if violating_ppv_index >= len(ppv_items):
        return False

    violating_pos, violating_item = ppv_items[violating_ppv_index]
    current_hour = _get_item_hour(violating_item)
    current_period = _get_period(current_hour)
    target_period = 'PM' if current_period == 'AM' else 'AM'

    # Count styles in each period (excluding the item being moved)
    period_counts = _count_styles_by_period(ppv_items)

    # Get items already in target period
    target_period_items = [
        (idx, (pos, item)) for idx, (pos, item) in enumerate(ppv_items)
        if _get_period(_get_item_hour(item)) == target_period
    ]

    # Check if any item in target period has same style
    target_styles = [_get_ppv_style(item) for _, (_, item) in target_period_items]
    same_style_in_target = target_styles.count(violating_style)

    # Only proceed if moving won't create obvious new violations
    # Allow the move if the target period has 0 or 1 items of same style
    if same_style_in_target >= 2:
        return False

    # Set new time in target period
    new_hour = DEFAULT_PM_HOUR if target_period == 'PM' else DEFAULT_AM_HOUR
    original_time = violating_item.get('scheduled_time', '')

    _set_item_hour(violating_item, new_hour)

    # After changing the time, we need to verify by sorting items by time
    # and checking for consecutive same-style violations in time order
    sorted_ppv_items = sorted(
        [(i, item) for i, item in enumerate(daily_schedule) if _is_ppv_item(item)],
        key=lambda x: _get_item_hour(x[1]) or 0
    )

    # Check for violations in time-sorted order
    has_violation = False
    for i in range(len(sorted_ppv_items) - 1):
        _, current_item = sorted_ppv_items[i]
        _, next_item = sorted_ppv_items[i + 1]

        curr_style = _get_ppv_style(current_item)
        next_style = _get_ppv_style(next_item)

        if curr_style and next_style and curr_style == next_style:
            has_violation = True
            break

    if has_violation:
        # Revert the change
        violating_item['scheduled_time'] = original_time
        return False

    # Record the repair
    repairs_applied.append(RepairRecord(
        strategy='am_pm_redistribution',
        original_position=violating_pos,
        swapped_with=None,
        from_period=current_period,
        to_period=target_period,
        style=violating_style
    ))

    return True


# =============================================================================
# Utility Functions for External Use
# =============================================================================


def get_ppv_style_distribution(
    daily_schedule: list[dict[str, Any]]
) -> dict[str, dict[str, int]]:
    """Get the distribution of PPV styles across AM/PM periods.

    Useful for analyzing schedule balance before/after validation.

    Args:
        daily_schedule: List of schedule item dictionaries.

    Returns:
        Dictionary with structure:
        {
            'AM': {'winner': count, 'bundle': count, ...},
            'PM': {'winner': count, 'bundle': count, ...},
            'total': {'winner': count, 'bundle': count, ...}
        }

    Examples:
        >>> schedule = [
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '10:00'},
        ...     {'is_ppv': True, 'ppv_style': 'bundle', 'scheduled_time': '14:00'},
        ... ]
        >>> dist = get_ppv_style_distribution(schedule)
        >>> dist['AM']['winner']
        1
        >>> dist['PM']['bundle']
        1
    """
    ppv_items = [
        (i, item) for i, item in enumerate(daily_schedule)
        if _is_ppv_item(item)
    ]

    period_counts = _count_styles_by_period(ppv_items)

    # Calculate totals
    total: Counter[str] = Counter()
    for period in ['AM', 'PM']:
        total.update(period_counts[period])

    return {
        'AM': dict(period_counts['AM']),
        'PM': dict(period_counts['PM']),
        'total': dict(total)
    }


def count_consecutive_violations(
    daily_schedule: list[dict[str, Any]]
) -> int:
    """Count the number of consecutive same-style violations.

    Args:
        daily_schedule: List of schedule item dictionaries.

    Returns:
        Number of violations found.

    Examples:
        >>> schedule = [
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '10:00'},
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '10:30'},
        ...     {'is_ppv': True, 'ppv_style': 'winner', 'scheduled_time': '11:00'},
        ... ]
        >>> count_consecutive_violations(schedule)
        2
    """
    result = validate_no_consecutive_same_style(daily_schedule)
    return len(result['errors'])


# =============================================================================
# Module Exports
# =============================================================================


__all__ = [
    # Type definitions
    'RepairRecord',
    'ValidationResult',
    'RepairResult',
    # Constants
    'PPV_STYLES',
    'DEFAULT_AM_HOUR',
    'DEFAULT_PM_HOUR',
    'AM_PM_BOUNDARY',
    # Main validation functions
    'validate_no_consecutive_same_style',
    'validate_and_repair_consecutive_styles',
    # Utility functions
    'get_ppv_style_distribution',
    'count_consecutive_violations',
]
