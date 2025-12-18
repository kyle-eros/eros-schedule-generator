"""
Label Assignment System for Campaign Feed Organization.

This module assigns labels to schedule items based on their send type to enable
proper campaign organization in the feed. All campaigns must be labeled for
feed organization per Gap 10.10 requirements.

Key Features:
- Maps 22+ send types to 7 standardized campaign labels
- Universal label assignment for schedule items
- Summary statistics for label distribution analysis
- Supports both labeled and unlabeled item tracking

Label Categories:
- GAMES: Game-based engagement sends (game_post, spin_the_wheel, etc.)
- BUNDLES: Content bundle offerings (bundle, bundle_wall, ppv_bundle)
- FIRST TO TIP: Tip-based incentive sends
- PPV: Pay-per-view content sends
- RENEW ON: Renewal reminder sends
- RETENTION: Subscriber retention sends (expired_winback)
- VIP: Premium program sends (vip_program, snapchat_bundle)

Usage:
    from python.orchestration.label_manager import (
        assign_label,
        apply_labels_to_schedule,
        get_label_summary,
        SEND_TYPE_LABELS,
    )

    schedule = [
        {'send_type': 'game_post', 'scheduled_time': '10:00'},
        {'send_type': 'ppv_unlock', 'scheduled_time': '14:00'},
        {'send_type': 'bump_normal', 'scheduled_time': '16:00'},
    ]
    labeled_schedule = apply_labels_to_schedule(schedule)
    summary = get_label_summary(labeled_schedule)
"""

from __future__ import annotations

from collections import Counter
from typing import Any


# =============================================================================
# Constants
# =============================================================================


# Mapping of send types to campaign labels for feed organization
# Format: send_type_key -> label string
SEND_TYPE_LABELS: dict[str, str] = {
    # GAMES label - game-based engagement sends
    'game_post': 'GAMES',
    'game_wheel': 'GAMES',
    'spin_the_wheel': 'GAMES',
    'card_game': 'GAMES',
    'prize_wheel': 'GAMES',
    'mystery_box': 'GAMES',
    'scratch_off': 'GAMES',
    # BUNDLES label - content bundle offerings
    'bundle': 'BUNDLES',
    'bundle_wall': 'BUNDLES',
    'ppv_bundle': 'BUNDLES',
    # FIRST TO TIP label - tip-based incentive sends
    'first_to_tip': 'FIRST TO TIP',
    # PPV label - pay-per-view content sends
    'ppv': 'PPV',
    'ppv_unlock': 'PPV',
    'ppv_wall': 'PPV',
    'ppv_winner': 'PPV',
    'ppv_solo': 'PPV',
    'ppv_sextape': 'PPV',
    # RENEW ON label - renewal reminder sends
    'renew_on': 'RENEW ON',
    # RETENTION label - subscriber retention sends
    'expired_winback': 'RETENTION',
    # VIP label - premium program sends
    'vip_program': 'VIP',
    'snapchat_bundle': 'VIP',
}

# All available labels for reference
AVAILABLE_LABELS: tuple[str, ...] = (
    'GAMES',
    'BUNDLES',
    'FIRST TO TIP',
    'PPV',
    'RENEW ON',
    'RETENTION',
    'VIP',
)


# =============================================================================
# Public Functions
# =============================================================================


def assign_label(schedule_item: dict[str, Any]) -> str | None:
    """Assign a campaign label to a schedule item based on its send type.

    Looks up the send_type from the schedule item and returns the corresponding
    campaign label for feed organization. Returns None if the send type is not
    found in the label mapping.

    Args:
        schedule_item: A schedule item dictionary containing at minimum a
            'send_type' key. Other keys are ignored.

    Returns:
        The campaign label string if the send_type has a mapping, None otherwise.

    Examples:
        >>> assign_label({'send_type': 'game_post', 'time': '10:00'})
        'GAMES'
        >>> assign_label({'send_type': 'ppv_unlock', 'price': 15.00})
        'PPV'
        >>> assign_label({'send_type': 'vip_program'})
        'VIP'
        >>> assign_label({'send_type': 'bump_normal'}) is None
        True
        >>> assign_label({}) is None
        True

    Note:
        Send types not in SEND_TYPE_LABELS will return None. This includes
        engagement types like bump_normal, dm_farm, like_farm, etc.
    """
    send_type = schedule_item.get('send_type')

    if send_type is None:
        return None

    # Normalize to string in case of unexpected types
    if not isinstance(send_type, str):
        send_type = str(send_type)

    return SEND_TYPE_LABELS.get(send_type)


def apply_labels_to_schedule(schedule: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply campaign labels to all items in a schedule.

    Iterates through each schedule item and assigns the appropriate campaign
    label based on its send_type. Items that do not match any label mapping
    will have their 'label' key set to None.

    Args:
        schedule: List of schedule item dictionaries. Each item should contain
            at minimum a 'send_type' key.

    Returns:
        The same schedule list with each item modified to include a 'label' key.
        Items are modified in-place and the original list is returned.

    Examples:
        >>> schedule = [
        ...     {'send_type': 'game_post', 'time': '10:00'},
        ...     {'send_type': 'ppv_unlock', 'time': '14:00'},
        ...     {'send_type': 'bump_normal', 'time': '16:00'},
        ... ]
        >>> result = apply_labels_to_schedule(schedule)
        >>> result[0]['label']
        'GAMES'
        >>> result[1]['label']
        'PPV'
        >>> result[2]['label'] is None
        True
        >>> result is schedule  # Modified in-place
        True

        >>> # Empty schedule returns empty list
        >>> apply_labels_to_schedule([])
        []

    Note:
        This function modifies the input schedule in-place. Create a copy
        using list comprehension or copy.deepcopy() before calling if you
        need to preserve the original schedule.
    """
    for item in schedule:
        item['label'] = assign_label(item)

    return schedule


def get_label_summary(schedule: list[dict[str, Any]]) -> dict[str, int]:
    """Generate a summary count of items by their campaign label.

    Analyzes the schedule to count how many items are assigned to each
    campaign label. Items without a label (None or missing 'label' key)
    are counted under 'UNLABELED'.

    Args:
        schedule: List of schedule item dictionaries. Each item may contain
            a 'label' key (typically set by apply_labels_to_schedule).

    Returns:
        Dictionary mapping label strings to occurrence counts. Includes
        'UNLABELED' for items without labels. Only labels with count > 0
        are included.

    Examples:
        >>> schedule = [
        ...     {'send_type': 'game_post', 'label': 'GAMES'},
        ...     {'send_type': 'ppv_unlock', 'label': 'PPV'},
        ...     {'send_type': 'ppv_wall', 'label': 'PPV'},
        ...     {'send_type': 'bump_normal', 'label': None},
        ...     {'send_type': 'dm_farm'},  # No label key
        ... ]
        >>> summary = get_label_summary(schedule)
        >>> summary['GAMES']
        1
        >>> summary['PPV']
        2
        >>> summary['UNLABELED']
        2

        >>> # Empty schedule returns empty dict
        >>> get_label_summary([])
        {}

        >>> # Schedule with only unlabeled items
        >>> schedule = [{'send_type': 'bump_normal', 'label': None}]
        >>> get_label_summary(schedule)
        {'UNLABELED': 1}

    Note:
        This function reads the 'label' key from each item. If items have not
        been processed by apply_labels_to_schedule(), the function will still
        work but may report more 'UNLABELED' items than expected.
    """
    if not schedule:
        return {}

    # Extract labels, treating None and missing as 'UNLABELED'
    labels: list[str] = [
        str(item.get('label')) if item.get('label') is not None else 'UNLABELED'
        for item in schedule
    ]

    # Count using Counter and convert to regular dict
    counter: Counter[str] = Counter(labels)
    return dict(counter)


def get_available_labels() -> list[str]:
    """Get the list of all available campaign labels.

    Returns:
        List of all defined campaign label strings.

    Examples:
        >>> labels = get_available_labels()
        >>> 'GAMES' in labels
        True
        >>> 'PPV' in labels
        True
        >>> len(labels)
        7
    """
    return list(AVAILABLE_LABELS)


def get_send_types_for_label(label: str) -> list[str]:
    """Get all send types that map to a specific label.

    Args:
        label: The campaign label to look up.

    Returns:
        List of send type keys that map to the given label.
        Empty list if the label is not found.

    Examples:
        >>> types = get_send_types_for_label('GAMES')
        >>> 'game_post' in types
        True
        >>> 'spin_the_wheel' in types
        True
        >>> len(get_send_types_for_label('FIRST TO TIP'))
        1
        >>> get_send_types_for_label('INVALID')
        []
    """
    return [
        send_type
        for send_type, mapped_label in SEND_TYPE_LABELS.items()
        if mapped_label == label
    ]


# =============================================================================
# Module Exports
# =============================================================================


__all__ = [
    # Constants
    'SEND_TYPE_LABELS',
    'AVAILABLE_LABELS',
    # Main functions
    'assign_label',
    'apply_labels_to_schedule',
    'get_label_summary',
    # Helper functions
    'get_available_labels',
    'get_send_types_for_label',
]
