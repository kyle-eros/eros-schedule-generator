"""
Daily Followup Limit Enforcer for PPV Schedule Optimization.

This module enforces the maximum daily followup limit using multi-factor
prioritization to prevent audience saturation while maximizing revenue potential.

Key Features:
- Maximum followups per day (default 4, dynamic via MCP) to prevent subscriber fatigue
- Multi-factor prioritization based on revenue, recency, and engagement
- In-place schedule modification with detailed audit trail
- Graceful handling of missing data with sensible defaults

Wave 3 Specification Implementation:
- Rule: Maximum followups per day to prevent saturation (dynamic via MCP)
- Prioritization: By parent PPV estimated revenue (and other factors)

Algorithm Details:
- Revenue weight (50%): Prioritizes high-value parent PPVs
- Recency weight (30%): Favors recently sent parent PPVs
- Engagement weight (20%): Considers historical engagement rates

DEPRECATION NOTICE (v3.0):
The fixed MAX_FOLLOWUPS_PER_DAY constant (4) is maintained for backward compatibility
but should be replaced with dynamic values from get_volume_config() MCP tool.
Use volume_config.followup_volume_scaled for the dynamically calculated limit.
Hard cap of 5 followups/day is enforced in bump_multiplier.py.
"""

from datetime import datetime
from typing import Any, TypedDict


# =============================================================================
# Constants
# =============================================================================


# DEPRECATED (v3.0): Use volume_config.followup_volume_scaled from MCP instead
# This constant is maintained for backward compatibility only.
# Dynamic limit from get_volume_config() should be preferred.
# Hard cap of 5 followups/day is enforced in bump_multiplier.py.
MAX_FOLLOWUPS_PER_DAY: int = 4  # Legacy default, prefer MCP dynamic value

# Multi-factor weights for followup prioritization
FOLLOWUP_WEIGHTS: dict[str, float] = {
    'REVENUE': 0.50,    # Parent PPV revenue importance
    'RECENCY': 0.30,    # How recently the parent PPV was sent
    'ENGAGEMENT': 0.20  # Historical engagement rate
}

# Normalization constants
MAX_EXPECTED_REVENUE: float = 1000.0  # Maximum revenue for normalization
EXCELLENT_ENGAGEMENT_RATE: float = 0.20  # 20% considered excellent
RECENCY_DECAY_HOURS: float = 24.0  # Hours over which recency score decays to 0


# =============================================================================
# Type Definitions
# =============================================================================


class RemovedItemRecord(TypedDict):
    """Record of a single removed followup item.

    Attributes:
        id: Identifier of the removed item (if present).
        parent_revenue: Estimated revenue of the parent PPV.
    """

    id: Any
    parent_revenue: float


class EnforcementResult(TypedDict):
    """Result from the daily followup limit enforcement.

    Attributes:
        modified: Whether the schedule was modified.
        followup_count: Final count of followups after enforcement.
        removed_count: Number of followups removed.
        removed_items: Details of each removed item.
    """

    modified: bool
    followup_count: int
    removed_count: int
    removed_items: list[RemovedItemRecord]


# =============================================================================
# Private Functions
# =============================================================================


def _calculate_followup_priority(
    followup: dict[str, Any],
    reference_time: datetime | None = None
) -> float:
    """Calculate multi-factor priority score for a followup item.

    Computes a weighted priority score based on three factors:
    - Revenue (50%): Normalized parent PPV estimated revenue
    - Recency (30%): Time decay score from parent send time
    - Engagement (20%): Historical engagement rate performance

    Args:
        followup: Dictionary containing followup item data with expected keys:
            - parent_estimated_revenue: float - Revenue estimate for parent PPV
            - parent_sent_time: datetime (optional) - When parent PPV was sent
            - parent_engagement_rate: float (optional) - Historical engagement
        reference_time: Reference datetime for recency calculations.
            Defaults to datetime.now() if not provided.

    Returns:
        Float priority score between 0.0 and 1.0, where higher is better.

    Examples:
        >>> from datetime import datetime, timedelta
        >>> followup = {
        ...     'parent_estimated_revenue': 500.0,
        ...     'parent_sent_time': datetime.now(),
        ...     'parent_engagement_rate': 0.15
        ... }
        >>> score = _calculate_followup_priority(followup)
        >>> 0.0 <= score <= 1.0
        True

        >>> # High revenue followup should score higher
        >>> high_rev = {'parent_estimated_revenue': 1000.0}
        >>> low_rev = {'parent_estimated_revenue': 50.0}
        >>> _calculate_followup_priority(high_rev) > _calculate_followup_priority(low_rev)
        True
    """
    if reference_time is None:
        reference_time = datetime.now()

    # Calculate revenue score (normalized to 0-1)
    parent_revenue = followup.get('parent_estimated_revenue', 0.0)
    if not isinstance(parent_revenue, (int, float)):
        parent_revenue = 0.0
    revenue_score = min(float(parent_revenue) / MAX_EXPECTED_REVENUE, 1.0)

    # Calculate recency score (decays from 1.0 to 0.0 over 24 hours)
    parent_sent_time = followup.get('parent_sent_time')
    if parent_sent_time is not None and isinstance(parent_sent_time, datetime):
        delta = reference_time - parent_sent_time
        hours_since_parent = delta.total_seconds() / 3600.0
        recency_score = max(0.0, 1.0 - (hours_since_parent / RECENCY_DECAY_HOURS))
    else:
        # Default to middle score if no timestamp available
        recency_score = 0.5

    # Calculate engagement score (normalized with 20% as excellent)
    engagement_rate = followup.get('parent_engagement_rate', 0.0)
    if not isinstance(engagement_rate, (int, float)):
        engagement_rate = 0.0
    engagement_score = min(float(engagement_rate) / EXCELLENT_ENGAGEMENT_RATE, 1.0)

    # Compute weighted priority score
    priority: float = (
        FOLLOWUP_WEIGHTS['REVENUE'] * revenue_score +
        FOLLOWUP_WEIGHTS['RECENCY'] * recency_score +
        FOLLOWUP_WEIGHTS['ENGAGEMENT'] * engagement_score
    )

    return priority


def _is_followup_item(item: dict[str, Any]) -> bool:
    """Check if a schedule item is a PPV followup.

    Args:
        item: Schedule item dictionary to check.

    Returns:
        True if the item's send_type is 'ppv_followup', False otherwise.
    """
    return item.get('send_type') == 'ppv_followup'


# =============================================================================
# Public Functions
# =============================================================================


def enforce_daily_followup_limit(
    daily_schedule: list[dict[str, Any]],
    max_followups: int = MAX_FOLLOWUPS_PER_DAY
) -> EnforcementResult:
    """Enforce the daily followup limit on a schedule.

    Filters a daily schedule to ensure no more than max_followups PPV
    followup items are present. Uses multi-factor prioritization to
    determine which followups to keep when the limit is exceeded.

    The function modifies the daily_schedule in-place by removing
    low-priority followup items.

    Prioritization factors:
    - Revenue (50%): Parent PPV estimated revenue (max $1000)
    - Recency (30%): Hours since parent PPV was sent (24h decay)
    - Engagement (20%): Historical engagement rate (20% = excellent)

    Args:
        daily_schedule: List of schedule item dictionaries. Items with
            send_type='ppv_followup' are subject to limiting. Expected
            followup item keys:
            - send_type: str - Must be 'ppv_followup' for this filter
            - id: Any - Identifier for tracking removed items
            - parent_estimated_revenue: float - Revenue estimate
            - parent_sent_time: datetime (optional) - Parent PPV time
            - parent_engagement_rate: float (optional) - Engagement rate
        max_followups: Maximum number of followups allowed per day.
            Defaults to MAX_FOLLOWUPS_PER_DAY (4).

    Returns:
        EnforcementResult dictionary containing:
        - modified: bool - Whether any changes were made
        - followup_count: int - Final number of followups
        - removed_count: int - Number of followups removed
        - removed_items: list - Details of removed items

    Examples:
        >>> from datetime import datetime
        >>> schedule = [
        ...     {'send_type': 'ppv_followup', 'id': 1, 'parent_estimated_revenue': 100},
        ...     {'send_type': 'ppv_followup', 'id': 2, 'parent_estimated_revenue': 500},
        ...     {'send_type': 'ppv_followup', 'id': 3, 'parent_estimated_revenue': 200},
        ...     {'send_type': 'ppv_followup', 'id': 4, 'parent_estimated_revenue': 50},
        ...     {'send_type': 'ppv_followup', 'id': 5, 'parent_estimated_revenue': 300},
        ...     {'send_type': 'ppv_unlock', 'id': 6, 'estimated_revenue': 1000},
        ... ]
        >>> result = enforce_daily_followup_limit(schedule)
        >>> result['modified']
        True
        >>> result['followup_count']
        4
        >>> result['removed_count']
        1

        >>> # Schedule within limit should not be modified
        >>> small_schedule = [
        ...     {'send_type': 'ppv_followup', 'id': 1, 'parent_estimated_revenue': 100},
        ...     {'send_type': 'ppv_unlock', 'id': 2, 'estimated_revenue': 500},
        ... ]
        >>> result = enforce_daily_followup_limit(small_schedule)
        >>> result['modified']
        False

    Note:
        This function modifies the input schedule in-place. Create a copy
        before calling if you need to preserve the original schedule.
    """
    # Use current time for recency calculations
    reference_time = datetime.now()

    # Extract followup items with their indices for tracking
    followup_items: list[tuple[int, dict[str, Any]]] = [
        (idx, item) for idx, item in enumerate(daily_schedule)
        if _is_followup_item(item)
    ]

    current_count = len(followup_items)

    # Check if enforcement is needed
    if current_count <= max_followups:
        return EnforcementResult(
            modified=False,
            followup_count=current_count,
            removed_count=0,
            removed_items=[]
        )

    # Calculate priority scores for each followup
    scored_followups: list[tuple[int, dict[str, Any], float]] = [
        (idx, item, _calculate_followup_priority(item, reference_time))
        for idx, item in followup_items
    ]

    # Sort by priority score (highest first)
    scored_followups.sort(key=lambda x: x[2], reverse=True)

    # Identify items to keep and remove
    items_to_keep = scored_followups[:max_followups]
    items_to_remove = scored_followups[max_followups:]

    # Build removed items record for audit trail
    removed_items: list[RemovedItemRecord] = [
        RemovedItemRecord(
            id=item.get('id'),
            parent_revenue=item.get('parent_estimated_revenue', 0.0)
        )
        for _, item, _ in items_to_remove
    ]

    # Get indices to remove (in reverse order to maintain validity)
    indices_to_remove = sorted(
        [idx for idx, _, _ in items_to_remove],
        reverse=True
    )

    # Remove items from schedule in-place (reverse order preserves indices)
    for idx in indices_to_remove:
        del daily_schedule[idx]

    return EnforcementResult(
        modified=True,
        followup_count=max_followups,
        removed_count=len(items_to_remove),
        removed_items=removed_items
    )


def get_followup_priority_breakdown(
    followup: dict[str, Any],
    reference_time: datetime | None = None
) -> dict[str, float]:
    """Get detailed breakdown of priority score components.

    Useful for debugging and understanding why certain followups
    were prioritized over others.

    Args:
        followup: Dictionary containing followup item data.
        reference_time: Reference datetime for recency calculations.

    Returns:
        Dictionary with individual component scores and total:
        - revenue_score: Normalized revenue component
        - recency_score: Time decay component
        - engagement_score: Engagement rate component
        - total_priority: Final weighted score

    Examples:
        >>> followup = {
        ...     'parent_estimated_revenue': 500.0,
        ...     'parent_engagement_rate': 0.10
        ... }
        >>> breakdown = get_followup_priority_breakdown(followup)
        >>> 'revenue_score' in breakdown
        True
        >>> 'total_priority' in breakdown
        True
    """
    if reference_time is None:
        reference_time = datetime.now()

    # Calculate revenue score
    parent_revenue = followup.get('parent_estimated_revenue', 0.0)
    if not isinstance(parent_revenue, (int, float)):
        parent_revenue = 0.0
    revenue_score = min(float(parent_revenue) / MAX_EXPECTED_REVENUE, 1.0)

    # Calculate recency score
    parent_sent_time = followup.get('parent_sent_time')
    if parent_sent_time is not None and isinstance(parent_sent_time, datetime):
        delta = reference_time - parent_sent_time
        hours_since_parent = delta.total_seconds() / 3600.0
        recency_score = max(0.0, 1.0 - (hours_since_parent / RECENCY_DECAY_HOURS))
    else:
        recency_score = 0.5

    # Calculate engagement score
    engagement_rate = followup.get('parent_engagement_rate', 0.0)
    if not isinstance(engagement_rate, (int, float)):
        engagement_rate = 0.0
    engagement_score = min(float(engagement_rate) / EXCELLENT_ENGAGEMENT_RATE, 1.0)

    # Compute total
    total_priority = (
        FOLLOWUP_WEIGHTS['REVENUE'] * revenue_score +
        FOLLOWUP_WEIGHTS['RECENCY'] * recency_score +
        FOLLOWUP_WEIGHTS['ENGAGEMENT'] * engagement_score
    )

    return {
        'revenue_score': revenue_score,
        'recency_score': recency_score,
        'engagement_score': engagement_score,
        'total_priority': total_priority
    }


def count_followups(daily_schedule: list[dict[str, Any]]) -> int:
    """Count the number of PPV followup items in a schedule.

    Args:
        daily_schedule: List of schedule item dictionaries.

    Returns:
        Number of items with send_type='ppv_followup'.

    Examples:
        >>> schedule = [
        ...     {'send_type': 'ppv_followup', 'id': 1},
        ...     {'send_type': 'ppv_unlock', 'id': 2},
        ...     {'send_type': 'ppv_followup', 'id': 3},
        ... ]
        >>> count_followups(schedule)
        2
    """
    return sum(1 for item in daily_schedule if _is_followup_item(item))


# =============================================================================
# Module Exports
# =============================================================================


__all__ = [
    # Constants
    'MAX_FOLLOWUPS_PER_DAY',
    'FOLLOWUP_WEIGHTS',
    # Type definitions
    'RemovedItemRecord',
    'EnforcementResult',
    # Main functions
    'enforce_daily_followup_limit',
    # Utility functions
    'get_followup_priority_breakdown',
    'count_followups',
    # Private function (exposed for testing)
    '_calculate_followup_priority',
]
