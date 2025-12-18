"""
Weekly Limit Validator for Schedule Optimization.

This module enforces maximum weekly limits on specific send types to maintain
exclusivity perception and prevent audience fatigue. Certain high-value send
types like VIP programs and Snapchat bundles are limited to preserve their
premium positioning.

Key Features:
- VIP program limited to 1/week maximum (exclusivity preservation)
- Snapchat bundle limited to 1/week maximum (scarcity perception)
- Comprehensive validation with detailed violation reporting
- Flexible architecture for adding new weekly-limited send types

Wave 3 Specification Implementation:
- Rule: VIP program max 1/week
- Rule: Snapchat bundle max 1/week
- Reason: Maintain exclusivity perception
- Priority: P1 HIGH

Algorithm Details:
- Counts send types across all items in weekly schedule
- Compares against configurable weekly limits
- Reports violations with actionable context
- Supports both validation-only and enforcement modes

Usage:
    from python.orchestration.weekly_limits import (
        validate_weekly_limits,
        WEEKLY_LIMITS,
        get_weekly_limits,
        get_limited_send_types,
    )

    weekly_schedule = [
        {'send_type': 'vip_program', 'scheduled_date': '2025-01-13'},
        {'send_type': 'vip_program', 'scheduled_date': '2025-01-15'},
        {'send_type': 'ppv_unlock', 'scheduled_date': '2025-01-14'},
    ]
    result = validate_weekly_limits(weekly_schedule)
    if not result['is_valid']:
        for violation in result['violations']:
            print(f"[{violation['severity']}] {violation['send_type']}: {violation['message']}")
"""

from typing import Any, TypedDict


# =============================================================================
# Constants
# =============================================================================


# Weekly limits for specific send types
# Format: send_type_key -> maximum allowed per week
WEEKLY_LIMITS: dict[str, int] = {
    'vip_program': 1,       # Max 1 VIP program per week (exclusivity)
    'snapchat_bundle': 1,   # Max 1 Snapchat bundle per week (scarcity)
}

# Rationale mapping for validation messages
_LIMIT_RATIONALE: dict[str, str] = {
    'vip_program': 'VIP programs must maintain exclusivity perception',
    'snapchat_bundle': 'Snapchat bundles require scarcity to preserve value',
}

# Severity levels for violations
_VIOLATION_SEVERITY: dict[str, str] = {
    'vip_program': 'high',       # P1 HIGH priority
    'snapchat_bundle': 'high',   # P1 HIGH priority
}


# =============================================================================
# Type Definitions
# =============================================================================


class ViolationRecord(TypedDict):
    """Record of a single weekly limit violation.

    Attributes:
        send_type: The send type that exceeded its weekly limit.
        current_count: Number of occurrences in the schedule.
        max_allowed: Maximum allowed per week.
        excess_count: Number of items exceeding the limit.
        severity: Violation severity level ('high', 'medium', 'low').
        message: Human-readable violation description.
        rationale: Business rationale for the limit.
    """

    send_type: str
    current_count: int
    max_allowed: int
    excess_count: int
    severity: str
    message: str
    rationale: str


class WarningRecord(TypedDict):
    """Record of a non-blocking warning.

    Attributes:
        send_type: The send type the warning relates to.
        message: Human-readable warning description.
        severity: Warning severity level.
    """

    send_type: str
    message: str
    severity: str


class ValidationResult(TypedDict):
    """Result from weekly limit validation.

    Attributes:
        is_valid: Whether the schedule passes all weekly limit checks.
        violations: List of violation records for exceeded limits.
        warnings: List of warning records for informational alerts.
        send_type_counts: Dictionary of send_type to count in schedule.
        limited_types_found: List of limited send types present in schedule.
        total_items_checked: Total number of schedule items processed.
    """

    is_valid: bool
    violations: list[ViolationRecord]
    warnings: list[WarningRecord]
    send_type_counts: dict[str, int]
    limited_types_found: list[str]
    total_items_checked: int


class EnforcementResult(TypedDict):
    """Result from weekly limit enforcement (removal of excess items).

    Attributes:
        modified: Whether the schedule was modified.
        removed_count: Total number of items removed.
        removed_items: Details of each removed item.
        final_counts: Send type counts after enforcement.
    """

    modified: bool
    removed_count: int
    removed_items: list[dict[str, Any]]
    final_counts: dict[str, int]


# =============================================================================
# Private Functions
# =============================================================================


def _count_send_types(weekly_schedule: list[dict[str, Any]]) -> dict[str, int]:
    """Count occurrences of each send type in the schedule.

    Args:
        weekly_schedule: List of schedule item dictionaries.

    Returns:
        Dictionary mapping send_type to occurrence count.

    Examples:
        >>> schedule = [
        ...     {'send_type': 'ppv_unlock'},
        ...     {'send_type': 'vip_program'},
        ...     {'send_type': 'ppv_unlock'},
        ... ]
        >>> counts = _count_send_types(schedule)
        >>> counts['ppv_unlock']
        2
        >>> counts['vip_program']
        1
    """
    counts: dict[str, int] = {}

    for item in weekly_schedule:
        send_type = item.get('send_type')

        # Skip items without a send_type
        if send_type is None:
            continue

        # Normalize to string in case of unexpected types
        if not isinstance(send_type, str):
            send_type = str(send_type)

        # Increment count
        counts[send_type] = counts.get(send_type, 0) + 1

    return counts


def _check_limit_violation(
    send_type: str,
    current_count: int,
    max_allowed: int,
) -> ViolationRecord | None:
    """Check if a send type violates its weekly limit.

    Args:
        send_type: The send type to check.
        current_count: Number of occurrences in the schedule.
        max_allowed: Maximum allowed per week.

    Returns:
        ViolationRecord if limit exceeded, None otherwise.
    """
    if current_count <= max_allowed:
        return None

    excess_count = current_count - max_allowed
    severity = _VIOLATION_SEVERITY.get(send_type, 'medium')
    rationale = _LIMIT_RATIONALE.get(send_type, 'Weekly limit exceeded')

    return ViolationRecord(
        send_type=send_type,
        current_count=current_count,
        max_allowed=max_allowed,
        excess_count=excess_count,
        severity=severity,
        message=(
            f"{send_type} exceeds weekly limit: {current_count} scheduled "
            f"(max {max_allowed}/week, {excess_count} excess)"
        ),
        rationale=rationale,
    )


def _get_items_by_send_type(
    weekly_schedule: list[dict[str, Any]],
    send_type: str,
) -> list[tuple[int, dict[str, Any]]]:
    """Get all items of a specific send type with their indices.

    Args:
        weekly_schedule: List of schedule item dictionaries.
        send_type: The send type to filter for.

    Returns:
        List of (index, item) tuples for matching items.
    """
    return [
        (idx, item) for idx, item in enumerate(weekly_schedule)
        if item.get('send_type') == send_type
    ]


# =============================================================================
# Public Functions
# =============================================================================


def validate_weekly_limits(
    weekly_schedule: list[dict[str, Any]],
    limits: dict[str, int] | None = None,
) -> ValidationResult:
    """Validate that a weekly schedule respects all weekly send type limits.

    Analyzes the schedule to ensure no send type exceeds its configured
    weekly maximum. Currently enforces limits on:
    - vip_program: 1/week (exclusivity preservation)
    - snapchat_bundle: 1/week (scarcity perception)

    Args:
        weekly_schedule: List of schedule item dictionaries. Each item should
            contain a 'send_type' key with the send type identifier. Items
            without 'send_type' are skipped during validation.
        limits: Optional custom limits dictionary to override WEEKLY_LIMITS.
            If not provided, uses the module-level WEEKLY_LIMITS constant.

    Returns:
        ValidationResult dictionary containing:
        - is_valid: bool - True if no limits are exceeded
        - violations: list[ViolationRecord] - Details of exceeded limits
        - warnings: list[WarningRecord] - Informational warnings
        - send_type_counts: dict - Count of each send type in schedule
        - limited_types_found: list - Limited types present in schedule
        - total_items_checked: int - Total items processed

    Examples:
        >>> # Valid schedule within limits
        >>> schedule = [
        ...     {'send_type': 'vip_program', 'scheduled_date': '2025-01-13'},
        ...     {'send_type': 'ppv_unlock', 'scheduled_date': '2025-01-14'},
        ...     {'send_type': 'bump_normal', 'scheduled_date': '2025-01-15'},
        ... ]
        >>> result = validate_weekly_limits(schedule)
        >>> result['is_valid']
        True
        >>> result['violations']
        []

        >>> # Invalid schedule exceeding VIP limit
        >>> schedule = [
        ...     {'send_type': 'vip_program', 'scheduled_date': '2025-01-13'},
        ...     {'send_type': 'vip_program', 'scheduled_date': '2025-01-15'},
        ...     {'send_type': 'ppv_unlock', 'scheduled_date': '2025-01-14'},
        ... ]
        >>> result = validate_weekly_limits(schedule)
        >>> result['is_valid']
        False
        >>> len(result['violations'])
        1
        >>> result['violations'][0]['send_type']
        'vip_program'
        >>> result['violations'][0]['excess_count']
        1

        >>> # Empty schedule is valid
        >>> result = validate_weekly_limits([])
        >>> result['is_valid']
        True

        >>> # Custom limits override
        >>> schedule = [
        ...     {'send_type': 'vip_program'},
        ...     {'send_type': 'vip_program'},
        ...     {'send_type': 'vip_program'},
        ... ]
        >>> result = validate_weekly_limits(schedule, limits={'vip_program': 2})
        >>> result['is_valid']
        False
        >>> result['violations'][0]['excess_count']
        1

    Note:
        This function is read-only and does not modify the input schedule.
        Use enforce_weekly_limits() if you need to remove excess items.
    """
    # Use provided limits or default to module constant
    effective_limits = limits if limits is not None else WEEKLY_LIMITS

    # Handle empty schedule
    if not weekly_schedule:
        return ValidationResult(
            is_valid=True,
            violations=[],
            warnings=[],
            send_type_counts={},
            limited_types_found=[],
            total_items_checked=0,
        )

    # Count all send types in the schedule
    send_type_counts = _count_send_types(weekly_schedule)

    # Track violations and warnings
    violations: list[ViolationRecord] = []
    warnings: list[WarningRecord] = []
    limited_types_found: list[str] = []

    # Check each limited send type
    for send_type, max_allowed in effective_limits.items():
        current_count = send_type_counts.get(send_type, 0)

        # Track if this limited type is present
        if current_count > 0:
            limited_types_found.append(send_type)

        # Check for violation
        violation = _check_limit_violation(send_type, current_count, max_allowed)
        if violation is not None:
            violations.append(violation)

    # Generate informational warning if at limit (not over)
    for send_type, max_allowed in effective_limits.items():
        current_count = send_type_counts.get(send_type, 0)
        if current_count == max_allowed and current_count > 0:
            warnings.append(WarningRecord(
                send_type=send_type,
                message=f"{send_type} is at weekly limit ({current_count}/{max_allowed})",
                severity='info',
            ))

    return ValidationResult(
        is_valid=len(violations) == 0,
        violations=violations,
        warnings=warnings,
        send_type_counts=send_type_counts,
        limited_types_found=limited_types_found,
        total_items_checked=len(weekly_schedule),
    )


def enforce_weekly_limits(
    weekly_schedule: list[dict[str, Any]],
    limits: dict[str, int] | None = None,
) -> EnforcementResult:
    """Enforce weekly limits by removing excess items from the schedule.

    Modifies the schedule in-place by removing items that exceed weekly
    limits. When removing, keeps items that appear earlier in the schedule
    (preserving schedule order priority).

    Args:
        weekly_schedule: List of schedule item dictionaries. Modified in-place.
        limits: Optional custom limits dictionary to override WEEKLY_LIMITS.

    Returns:
        EnforcementResult dictionary containing:
        - modified: bool - Whether any items were removed
        - removed_count: int - Number of items removed
        - removed_items: list - Details of removed items
        - final_counts: dict - Send type counts after enforcement

    Examples:
        >>> schedule = [
        ...     {'send_type': 'vip_program', 'id': 1},
        ...     {'send_type': 'ppv_unlock', 'id': 2},
        ...     {'send_type': 'vip_program', 'id': 3},
        ...     {'send_type': 'vip_program', 'id': 4},
        ... ]
        >>> result = enforce_weekly_limits(schedule)
        >>> result['modified']
        True
        >>> result['removed_count']
        2
        >>> len(schedule)
        2
        >>> schedule[0]['id']
        1

    Note:
        This function modifies the input schedule in-place. Create a copy
        before calling if you need to preserve the original schedule.
    """
    # Use provided limits or default to module constant
    effective_limits = limits if limits is not None else WEEKLY_LIMITS

    # Track removed items
    removed_items: list[dict[str, Any]] = []
    indices_to_remove: list[int] = []

    # Process each limited send type
    for send_type, max_allowed in effective_limits.items():
        items_with_indices = _get_items_by_send_type(weekly_schedule, send_type)

        # If within limit, skip
        if len(items_with_indices) <= max_allowed:
            continue

        # Mark excess items for removal (keep first max_allowed)
        excess_items = items_with_indices[max_allowed:]
        for idx, item in excess_items:
            indices_to_remove.append(idx)
            removed_items.append({
                'index': idx,
                'send_type': send_type,
                'item': item.copy(),
                'reason': f'Exceeded weekly limit of {max_allowed}',
            })

    # Remove items in reverse order to preserve indices
    for idx in sorted(indices_to_remove, reverse=True):
        del weekly_schedule[idx]

    # Calculate final counts
    final_counts = _count_send_types(weekly_schedule)

    return EnforcementResult(
        modified=len(removed_items) > 0,
        removed_count=len(removed_items),
        removed_items=removed_items,
        final_counts=final_counts,
    )


def get_weekly_limits() -> dict[str, int]:
    """Get the current weekly limits configuration.

    Returns a copy of the WEEKLY_LIMITS dictionary to prevent
    accidental modification of the module-level constant.

    Returns:
        Dictionary mapping send_type to maximum weekly count.

    Examples:
        >>> limits = get_weekly_limits()
        >>> limits['vip_program']
        1
        >>> limits['snapchat_bundle']
        1
    """
    return WEEKLY_LIMITS.copy()


def get_limited_send_types() -> list[str]:
    """Get the list of send types that have weekly limits.

    Returns:
        List of send type keys that are subject to weekly limiting.

    Examples:
        >>> types = get_limited_send_types()
        >>> 'vip_program' in types
        True
        >>> 'snapchat_bundle' in types
        True
        >>> 'ppv_unlock' in types
        False
    """
    return list(WEEKLY_LIMITS.keys())


def get_limit_for_send_type(send_type: str) -> int | None:
    """Get the weekly limit for a specific send type.

    Args:
        send_type: The send type key to look up.

    Returns:
        Maximum weekly count if the type has a limit, None otherwise.

    Examples:
        >>> get_limit_for_send_type('vip_program')
        1
        >>> get_limit_for_send_type('ppv_unlock') is None
        True
    """
    return WEEKLY_LIMITS.get(send_type)


def is_limited_send_type(send_type: str) -> bool:
    """Check if a send type is subject to weekly limiting.

    Args:
        send_type: The send type key to check.

    Returns:
        True if the send type has a weekly limit, False otherwise.

    Examples:
        >>> is_limited_send_type('vip_program')
        True
        >>> is_limited_send_type('snapchat_bundle')
        True
        >>> is_limited_send_type('ppv_unlock')
        False
    """
    return send_type in WEEKLY_LIMITS


def count_limited_send_types(
    weekly_schedule: list[dict[str, Any]],
) -> dict[str, int]:
    """Count only the limited send types in a schedule.

    Useful for quick validation checks without full validation overhead.

    Args:
        weekly_schedule: List of schedule item dictionaries.

    Returns:
        Dictionary mapping limited send_type to occurrence count.
        Only includes send types that are in WEEKLY_LIMITS.

    Examples:
        >>> schedule = [
        ...     {'send_type': 'vip_program'},
        ...     {'send_type': 'ppv_unlock'},
        ...     {'send_type': 'vip_program'},
        ...     {'send_type': 'bump_normal'},
        ... ]
        >>> counts = count_limited_send_types(schedule)
        >>> counts
        {'vip_program': 2}
        >>> 'ppv_unlock' in counts
        False
    """
    all_counts = _count_send_types(weekly_schedule)
    return {
        send_type: count
        for send_type, count in all_counts.items()
        if send_type in WEEKLY_LIMITS
    }


def get_limit_rationale(send_type: str) -> str:
    """Get the business rationale for a send type's weekly limit.

    Args:
        send_type: The send type key to look up.

    Returns:
        Rationale string explaining why the limit exists.

    Examples:
        >>> get_limit_rationale('vip_program')
        'VIP programs must maintain exclusivity perception'
        >>> get_limit_rationale('unknown_type')
        'No weekly limit defined for this send type'
    """
    if send_type not in WEEKLY_LIMITS:
        return 'No weekly limit defined for this send type'
    return _LIMIT_RATIONALE.get(
        send_type,
        f'Weekly limit of {WEEKLY_LIMITS[send_type]} enforced',
    )


# =============================================================================
# Module Exports
# =============================================================================


__all__ = [
    # Constants
    'WEEKLY_LIMITS',
    # Type definitions
    'ViolationRecord',
    'WarningRecord',
    'ValidationResult',
    'EnforcementResult',
    # Main validation function
    'validate_weekly_limits',
    # Enforcement function
    'enforce_weekly_limits',
    # Helper functions
    'get_weekly_limits',
    'get_limited_send_types',
    'get_limit_for_send_type',
    'is_limited_send_type',
    'count_limited_send_types',
    'get_limit_rationale',
]
