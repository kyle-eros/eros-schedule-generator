"""
Quality validators for schedule generation.

Validates schedule items against diversity requirements, channel assignments,
and page type restrictions to ensure generated schedules meet quality standards.

This module enforces:
- Gap 3.3: Minimum 10 unique send types per week
- Gap 8.1: Correct channel assignments for each send type
- Gap 9.1: Retention types only on PAID pages
"""

from typing import Any

# Complete channel mapping for all 22 send types
CHANNEL_MAPPING: dict[str, dict[str, Any]] = {
    # Revenue types (9)
    'ppv_unlock': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'ppv_wall': {'primary': 'wall_post', 'secondary': None, 'page_restriction': 'free'},
    'tip_goal': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'bundle': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'flash_bundle': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'game_post': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'first_to_tip': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'vip_program': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'snapchat_bundle': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    # Engagement types (9)
    'link_drop': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'wall_link_drop': {'primary': 'wall_post', 'secondary': None, 'page_restriction': None},
    'bump_normal': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'bump_descriptive': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'bump_text_only': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'bump_flyer': {'primary': 'wall_post', 'secondary': None, 'page_restriction': None},
    'dm_farm': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'like_farm': {'primary': 'wall_post', 'secondary': None, 'page_restriction': None},
    'live_promo': {'primary': 'wall_post', 'secondary': 'story', 'page_restriction': None},
    # Retention types (4) - PAID pages only (except ppv_followup)
    'renew_on_post': {'primary': 'wall_post', 'secondary': None, 'page_restriction': 'paid'},
    'renew_on_message': {'primary': 'mass_message', 'secondary': None, 'page_restriction': 'paid'},
    'ppv_followup': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'expired_winback': {'primary': 'mass_message', 'secondary': None, 'page_restriction': 'paid'},
}

# Standard send types for diversity suggestions (all 22 types)
STANDARD_SEND_TYPES: set[str] = {
    # Revenue types
    'ppv_unlock', 'ppv_wall', 'tip_goal', 'bundle', 'flash_bundle',
    'game_post', 'first_to_tip', 'vip_program', 'snapchat_bundle',
    # Engagement types
    'link_drop', 'wall_link_drop', 'bump_normal', 'bump_descriptive',
    'bump_text_only', 'bump_flyer', 'dm_farm', 'like_farm', 'live_promo',
    # Retention types (only valid for paid pages)
    'renew_on_post', 'renew_on_message', 'ppv_followup', 'expired_winback'
}

# Minimum required unique send types per week
MINIMUM_UNIQUE_TYPES: int = 10


def validate_send_type_diversity(weekly_schedule: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Validate schedule contains 10+ unique send types (Gap 3.3).

    Ensures the weekly schedule has sufficient variety across send types
    to prevent audience fatigue and maintain engagement.

    Args:
        weekly_schedule: List of schedule items, each containing at minimum:
            - 'send_type' or 'send_type_key': The send type identifier

    Returns:
        Dictionary with validation result:
            - 'is_valid': bool - Whether diversity requirement is met
            - 'current_count': int - Number of unique types found
            - 'minimum_required': int - Required minimum (10)
            - 'missing_suggestions': list[str] - Up to 3 suggested types to add (if invalid)
            - 'error': str - Error message (if invalid)
            - 'unique_types': set[str] - The unique types found (for debugging)

    Examples:
        >>> schedule = [{'send_type': 'ppv_unlock'}, {'send_type': 'bump_normal'}]
        >>> result = validate_send_type_diversity(schedule)
        >>> result['is_valid']
        False
        >>> result['current_count']
        2

        >>> # With 10+ types
        >>> diverse_schedule = [{'send_type': t} for t in list(STANDARD_SEND_TYPES)[:12]]
        >>> validate_send_type_diversity(diverse_schedule)['is_valid']
        True
    """
    # Extract unique send types from schedule
    unique_types: set[str] = set()
    for item in weekly_schedule:
        # Support both 'send_type' and 'send_type_key' field names
        send_type = item.get('send_type') or item.get('send_type_key', '')
        if send_type:
            unique_types.add(send_type)

    current_count = len(unique_types)

    if current_count < MINIMUM_UNIQUE_TYPES:
        # Calculate missing types for suggestions
        missing = STANDARD_SEND_TYPES - unique_types
        # Sort for deterministic output
        missing_suggestions = sorted(list(missing))[:3]

        return {
            'is_valid': False,
            'current_count': current_count,
            'minimum_required': MINIMUM_UNIQUE_TYPES,
            'missing_suggestions': missing_suggestions,
            'error': f"Only {current_count} unique types (min: {MINIMUM_UNIQUE_TYPES})",
            'unique_types': unique_types
        }

    return {
        'is_valid': True,
        'current_count': current_count,
        'minimum_required': MINIMUM_UNIQUE_TYPES,
        'unique_types': unique_types
    }


def validate_channel_assignment(item: dict[str, Any], page_type: str) -> dict[str, Any]:
    """
    Validate send type is assigned to correct channel for page type (Gaps 8.1, 9.1).

    Ensures each schedule item uses the appropriate channel for its send type
    and respects page type restrictions (e.g., retention types on PAID only).

    Args:
        item: Schedule item dictionary containing:
            - 'send_type' or 'send_type_key': The send type identifier
            - 'channel' or 'channel_key': The assigned channel
        page_type: 'paid' or 'free'

    Returns:
        Dictionary with validation result:
            - 'is_valid': bool - Whether assignment is valid
            - 'error': str - Error message (if invalid)
            - 'expected_channels': list[str] - Valid channels for this type (if invalid)

    Examples:
        >>> item = {'send_type': 'ppv_unlock', 'channel': 'mass_message'}
        >>> validate_channel_assignment(item, 'paid')['is_valid']
        True

        >>> item = {'send_type': 'ppv_unlock', 'channel': 'wall_post'}
        >>> result = validate_channel_assignment(item, 'paid')
        >>> result['is_valid']
        False
        >>> result['error']
        "ppv_unlock should use mass_message, not wall_post"

        >>> # Retention type on FREE page (invalid)
        >>> item = {'send_type': 'renew_on_message', 'channel': 'mass_message'}
        >>> validate_channel_assignment(item, 'free')['is_valid']
        False
    """
    # Extract send type and channel (support both field naming conventions)
    send_type = item.get('send_type') or item.get('send_type_key', '')
    channel = item.get('channel') or item.get('channel_key', '')

    # Unknown send type - skip validation (allow custom types)
    if send_type not in CHANNEL_MAPPING:
        return {'is_valid': True}

    mapping = CHANNEL_MAPPING[send_type]

    # Build list of valid channels
    valid_channels = [mapping['primary']]
    if mapping['secondary']:
        valid_channels.append(mapping['secondary'])

    # Check page type restrictions (Gap 9.1) - check this FIRST
    page_restriction = mapping['page_restriction']
    if page_restriction:
        if page_restriction == 'paid' and page_type == 'free':
            return {
                'is_valid': False,
                'error': f"{send_type} is only valid for PAID pages",
                'expected_channels': valid_channels
            }
        if page_restriction == 'free' and page_type == 'paid':
            return {
                'is_valid': False,
                'error': f"{send_type} is only valid for FREE pages",
                'expected_channels': valid_channels
            }

    # Check channel correctness
    if channel and channel not in valid_channels:
        return {
            'is_valid': False,
            'error': f"{send_type} should use {mapping['primary']}, not {channel}",
            'expected_channels': valid_channels
        }

    return {'is_valid': True}


def validate_schedule_quality(
    weekly_schedule: list[dict[str, Any]],
    page_type: str
) -> dict[str, Any]:
    """
    Run all quality validations on a weekly schedule.

    Combines diversity and channel validation for comprehensive quality check.

    Args:
        weekly_schedule: List of schedule items
        page_type: 'paid' or 'free'

    Returns:
        Dictionary with combined validation results:
            - 'is_valid': bool - Whether ALL validations pass
            - 'diversity_check': dict - Result from validate_send_type_diversity
            - 'channel_errors': list[dict] - All channel validation errors
            - 'total_items': int - Number of items validated
            - 'error_count': int - Total number of errors
    """
    # Run diversity validation
    diversity_result = validate_send_type_diversity(weekly_schedule)

    # Run channel validation on each item
    channel_errors: list[dict[str, Any]] = []
    for i, item in enumerate(weekly_schedule):
        channel_result = validate_channel_assignment(item, page_type)
        if not channel_result['is_valid']:
            channel_errors.append({
                'item_index': i,
                'send_type': item.get('send_type') or item.get('send_type_key'),
                'channel': item.get('channel') or item.get('channel_key'),
                **channel_result
            })

    is_valid = diversity_result['is_valid'] and len(channel_errors) == 0

    return {
        'is_valid': is_valid,
        'diversity_check': diversity_result,
        'channel_errors': channel_errors,
        'total_items': len(weekly_schedule),
        'error_count': (0 if diversity_result['is_valid'] else 1) + len(channel_errors)
    }


__all__ = [
    # Constants
    'CHANNEL_MAPPING',
    'STANDARD_SEND_TYPES',
    'MINIMUM_UNIQUE_TYPES',
    # Validation functions
    'validate_send_type_diversity',
    'validate_channel_assignment',
    'validate_schedule_quality',
]
