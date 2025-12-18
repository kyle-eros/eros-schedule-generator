"""Bundle Value Framing Validator for EROS Schedule Generator.

Validates that bundle captions include proper value anchoring per Gap 7.3.
Bundle captions must communicate value proposition using patterns like
"$500 worth for only $XX" to maximize conversion rates.

Wave 5 Task 5.9: Bundle Value Framing Validator
"""

from __future__ import annotations

import re

from python.logging_config import get_logger

logger = get_logger(__name__)

# Bundle send type keys that require value framing validation
BUNDLE_SEND_TYPES = frozenset({
    'bundle',
    'bundle_wall',
    'ppv_bundle',
    'flash_bundle',
    'snapchat_bundle',
})


def validate_bundle_value_framing(caption: str, price: float) -> dict:
    """Validate that a bundle caption includes proper value framing.

    Bundle captions should include both a value anchor (e.g., "$500 worth")
    and a price mention (e.g., "only $14.99") to communicate the value
    proposition effectively.

    Args:
        caption: The bundle caption text to validate.
        price: The bundle price in dollars.

    Returns:
        Validation result dict containing:
            - is_valid: True if both value anchor and price mention are present
            - has_value_anchor: Whether value anchor pattern was found
            - has_price_mention: Whether price mention pattern was found
            - extracted_value: The value amount extracted from caption (or None)
            - bundle_price: The price passed to the function
            - value_ratio: Ratio of extracted_value to bundle_price (or None)
            - severity: 'ERROR' if invalid, None if valid
            - message: Description of validation result
            - recommendation: Action to take if invalid (or None if valid)
            - note: Additional note if value ratio is exceptionally high
            - missing: List of missing elements (empty if valid)

    Examples:
        >>> result = validate_bundle_value_framing(
        ...     "Get $500 worth of my hottest content for only $14.99!",
        ...     14.99
        ... )
        >>> result['is_valid']
        True
        >>> result['value_ratio']
        33.36

        >>> result = validate_bundle_value_framing(
        ...     "Hot bundle available now!",
        ...     19.99
        ... )
        >>> result['is_valid']
        False
        >>> result['missing']
        ['value_anchor', 'price_mention']
    """
    logger.debug(f"Validating bundle value framing ({len(caption)} chars, ${price})")

    caption_lower = caption.lower()

    # Pattern for value anchor: $X worth, $X value, $X of content
    value_anchor_pattern = re.compile(
        r'\$[\d,]+(?:\.\d{2})?\s*(?:worth|value|of\s+content)',
        re.IGNORECASE
    )

    # Pattern for price mention: only $X, just $X, for $X
    price_mention_pattern = re.compile(
        r'(?:only|just|for)\s*\$\d+(?:\.\d{2})?',
        re.IGNORECASE
    )

    # Pattern to extract the value amount
    value_extract_pattern = re.compile(
        r'\$([\d,]+(?:\.\d{2})?)\s*(?:worth|value|of\s+content)',
        re.IGNORECASE
    )

    # Check for patterns
    has_value_anchor = bool(value_anchor_pattern.search(caption))
    has_price_mention = bool(price_mention_pattern.search(caption))

    # Extract value amount if present
    extracted_value: float | None = None
    value_match = value_extract_pattern.search(caption)
    if value_match:
        value_str = value_match.group(1).replace(',', '')
        try:
            extracted_value = float(value_str)
        except ValueError:
            extracted_value = None

    # Calculate value ratio if both values available
    value_ratio: float | None = None
    if extracted_value is not None and price > 0:
        value_ratio = round(extracted_value / price, 2)

    # Determine validity
    is_valid = has_value_anchor and has_price_mention

    # Build missing elements list
    missing: list[str] = []
    if not has_value_anchor:
        missing.append('value_anchor')
    if not has_price_mention:
        missing.append('price_mention')

    # Build result message
    if is_valid:
        message = 'Bundle caption includes proper value framing'
        recommendation = None
        severity = None
    else:
        missing_str = ' and '.join(missing)
        message = f'Bundle caption missing {missing_str}'
        recommendation = (
            'Add value framing like "$X worth for only $Y" to communicate '
            'the value proposition and improve conversion rates'
        )
        severity = 'ERROR'

    # Add note for exceptional value ratios
    note: str | None = None
    if value_ratio is not None and value_ratio >= 10:
        note = f'Excellent value ratio of {value_ratio}x (${extracted_value} value for ${price})'

    # Log validation results
    if is_valid:
        logger.debug(f"Bundle value framing valid (ratio: {value_ratio}x)")
    else:
        logger.warning(
            f"Bundle value framing invalid: missing {missing}",
            extra={'caption_preview': caption[:50], 'price': price}
        )

    return {
        'is_valid': is_valid,
        'has_value_anchor': has_value_anchor,
        'has_price_mention': has_price_mention,
        'extracted_value': extracted_value,
        'bundle_price': price,
        'value_ratio': value_ratio,
        'severity': severity,
        'message': message,
        'recommendation': recommendation,
        'note': note,
        'missing': missing,
    }


def validate_all_bundles_in_schedule(schedule: list[dict]) -> dict:
    """Validate all bundle items in a schedule for proper value framing.

    Filters the schedule to bundle send types and validates each one
    for proper value framing. Returns aggregate results.

    Args:
        schedule: List of schedule item dicts, each containing at minimum:
            - send_type_key: The send type identifier
            - caption: The caption text
            - price: The price amount (optional, defaults to 0)

    Returns:
        Validation result dict containing:
            - is_valid: True if all bundles pass validation (or no bundles)
            - bundles_checked: Total number of bundle items found
            - bundles_passed: Number of bundles that passed validation
            - bundles_failed: Number of bundles that failed validation
            - results: List of validation results for each bundle
            - failed_items: List of failed bundle items with their results
            - summary: Human-readable summary string

    Examples:
        >>> schedule = [
        ...     {'send_type_key': 'bundle', 'caption': '$500 worth for only $15!', 'price': 15.0},
        ...     {'send_type_key': 'ppv_unlock', 'caption': 'Hot content!', 'price': 9.99},
        ... ]
        >>> result = validate_all_bundles_in_schedule(schedule)
        >>> result['bundles_checked']
        1
        >>> result['is_valid']
        True
    """
    logger.debug(f"Validating bundles in schedule ({len(schedule)} items)")

    # Filter to bundle items only
    bundle_items = [
        item for item in schedule
        if item.get('send_type_key', '').lower() in BUNDLE_SEND_TYPES
    ]

    # Handle no bundles case
    if not bundle_items:
        logger.debug("No bundle items found in schedule")
        return {
            'is_valid': True,
            'bundles_checked': 0,
            'bundles_passed': 0,
            'bundles_failed': 0,
            'results': [],
            'failed_items': [],
            'summary': 'No bundle items in schedule',
        }

    # Validate each bundle
    results: list[dict] = []
    failed_items: list[dict] = []
    bundles_passed = 0
    bundles_failed = 0

    for item in bundle_items:
        caption = item.get('caption', '')
        price = item.get('price', 0.0)

        # Handle missing caption
        if not caption:
            validation_result = {
                'is_valid': False,
                'has_value_anchor': False,
                'has_price_mention': False,
                'extracted_value': None,
                'bundle_price': price,
                'value_ratio': None,
                'severity': 'ERROR',
                'message': 'Bundle item has no caption',
                'recommendation': 'Add a caption with value framing',
                'note': None,
                'missing': ['caption', 'value_anchor', 'price_mention'],
            }
        else:
            validation_result = validate_bundle_value_framing(caption, price)

        # Add item context to result
        validation_result['send_type_key'] = item.get('send_type_key')
        validation_result['item_index'] = schedule.index(item) if item in schedule else None

        results.append(validation_result)

        if validation_result['is_valid']:
            bundles_passed += 1
        else:
            bundles_failed += 1
            failed_items.append({
                'item': item,
                'validation': validation_result,
            })

    # Determine overall validity
    is_valid = bundles_failed == 0

    # Build summary string
    if is_valid:
        summary = f'All {bundles_passed} bundle(s) have proper value framing'
    else:
        summary = (
            f'{bundles_failed} of {len(bundle_items)} bundle(s) missing value framing'
        )

    # Log results
    if is_valid:
        logger.debug(f"All bundles valid: {bundles_passed}/{len(bundle_items)}")
    else:
        logger.warning(
            f"Bundle validation failed: {bundles_failed}/{len(bundle_items)} invalid",
            extra={'failed_types': [f['item'].get('send_type_key') for f in failed_items]}
        )

    return {
        'is_valid': is_valid,
        'bundles_checked': len(bundle_items),
        'bundles_passed': bundles_passed,
        'bundles_failed': bundles_failed,
        'results': results,
        'failed_items': failed_items,
        'summary': summary,
    }
