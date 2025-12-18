"""Drip Outfit Coordination Validator for Schedule Quality Control.

Validates that all drip content from the same shoot uses matching outfits.
This ensures visual consistency across drip campaigns and prevents jarring
outfit changes within a coordinated content series.

Gap Reference: 6.1 - Drip outfit consistency validation
"""
from __future__ import annotations

from dataclasses import dataclass, field

from python.logging_config import get_logger

logger = get_logger(__name__)

# Send types that constitute drip content
DRIP_SEND_TYPES = frozenset({'bump_drip', 'drip_set', 'bump_normal'})


@dataclass(frozen=True, slots=True)
class DripOutfitValidationResult:
    """Immutable result of drip outfit validation."""

    is_valid: bool
    total_drip_items: int
    shoots_checked: int
    inconsistencies: tuple[dict, ...]
    recommendation: str | None


class DripOutfitValidator:
    """Validate drip content outfit consistency within shoots.

    Ensures all drip content items from the same photoshoot use matching
    outfits to maintain visual consistency across the drip campaign.

    Attributes:
        None - validator is stateless
    """

    def __init__(self) -> None:
        """Initialize the drip outfit validator.

        The validator is stateless and requires no configuration.
        """
        pass

    def validate_drip_outfit_consistency(
        self,
        drip_items: list[dict],
        content_metadata: dict,
    ) -> dict:
        """Validate outfit consistency across drip items within each shoot.

        Groups drip items by shoot_id and verifies all items in each shoot
        use the expected outfit from content metadata.

        Args:
            drip_items: List of drip content items, each containing:
                - id: Unique item identifier
                - shoot_id: ID of the photoshoot (optional)
                - outfit_id: ID of the outfit used (optional)
            content_metadata: Metadata dictionary containing shoot information:
                - shoots: Dict mapping shoot_id to shoot details including outfit_id

        Returns:
            Validation result dictionary with:
                - is_valid: True if no ERROR-level inconsistencies found
                - total_drip_items: Count of drip items validated
                - shoots_checked: Count of unique shoots validated
                - inconsistencies: List of inconsistency details
                - recommendation: Suggested action or None if valid

        Example:
            >>> validator = DripOutfitValidator()
            >>> drip_items = [
            ...     {'id': 1, 'shoot_id': 'S001', 'outfit_id': 'O1'},
            ...     {'id': 2, 'shoot_id': 'S001', 'outfit_id': 'O2'},  # Mismatch!
            ... ]
            >>> metadata = {'shoots': {'S001': {'outfit_id': 'O1'}}}
            >>> result = validator.validate_drip_outfit_consistency(drip_items, metadata)
            >>> result['is_valid']
            False
        """
        if not drip_items:
            return {
                'is_valid': True,
                'total_drip_items': 0,
                'shoots_checked': 0,
                'inconsistencies': [],
                'recommendation': None,
            }

        inconsistencies: list[dict] = []
        shoots_by_id: dict[str, list[dict]] = {}

        # Group items by shoot_id
        for item in drip_items:
            shoot_id = item.get('shoot_id')

            if shoot_id is None:
                # Missing shoot_id is a warning - cannot validate outfit
                inconsistencies.append({
                    'item_id': item.get('id'),
                    'shoot_id': None,
                    'expected_outfit': None,
                    'actual_outfit': item.get('outfit_id'),
                    'issue': 'Missing shoot_id - cannot validate outfit consistency',
                    'severity': 'WARNING',
                })
                logger.warning(
                    "Drip item %s missing shoot_id - skipping outfit validation",
                    item.get('id'),
                )
                continue

            if shoot_id not in shoots_by_id:
                shoots_by_id[shoot_id] = []
            shoots_by_id[shoot_id].append(item)

        # Extract shoots metadata safely
        shoots_metadata = content_metadata.get('shoots', {}) or {}

        # Validate outfit consistency within each shoot
        for shoot_id, items in shoots_by_id.items():
            shoot_info = shoots_metadata.get(shoot_id, {})
            expected_outfit = shoot_info.get('outfit_id') if shoot_info else None

            if expected_outfit is None:
                # Expected outfit not found in metadata
                for item in items:
                    inconsistencies.append({
                        'item_id': item.get('id'),
                        'shoot_id': shoot_id,
                        'expected_outfit': None,
                        'actual_outfit': item.get('outfit_id'),
                        'issue': f'No expected outfit defined for shoot {shoot_id}',
                        'severity': 'WARNING',
                    })
                logger.warning(
                    "Shoot %s has no expected outfit in content_metadata",
                    shoot_id,
                )
                continue

            # Check each item against expected outfit
            for item in items:
                item_outfit = item.get('outfit_id')

                if item_outfit != expected_outfit:
                    inconsistencies.append({
                        'item_id': item.get('id'),
                        'shoot_id': shoot_id,
                        'expected_outfit': expected_outfit,
                        'actual_outfit': item_outfit,
                        'issue': 'Outfit mismatch within shoot',
                        'severity': 'ERROR',
                    })
                    logger.error(
                        "Outfit mismatch: item %s has outfit %s, expected %s for shoot %s",
                        item.get('id'),
                        item_outfit,
                        expected_outfit,
                        shoot_id,
                    )

        # Determine overall validity (only ERRORs make it invalid)
        is_valid = not any(
            inc['severity'] == 'ERROR' for inc in inconsistencies
        )

        recommendation = self._generate_recommendation(inconsistencies)

        return {
            'is_valid': is_valid,
            'total_drip_items': len(drip_items),
            'shoots_checked': len(shoots_by_id),
            'inconsistencies': inconsistencies,
            'recommendation': recommendation,
        }

    def _generate_recommendation(
        self,
        inconsistencies: list[dict],
    ) -> str | None:
        """Generate a recommendation based on inconsistencies found.

        Args:
            inconsistencies: List of inconsistency dictionaries with severity levels

        Returns:
            Recommendation string describing suggested actions, or None if
            no inconsistencies were found.
        """
        if not inconsistencies:
            return None

        error_count = sum(
            1 for inc in inconsistencies if inc['severity'] == 'ERROR'
        )
        warning_count = sum(
            1 for inc in inconsistencies if inc['severity'] == 'WARNING'
        )

        parts: list[str] = []

        if error_count > 0:
            parts.append(
                f"Found {error_count} outfit mismatch(es) - update content "
                f"selection to use consistent outfits within each shoot"
            )

        if warning_count > 0:
            parts.append(
                f"Found {warning_count} warning(s) - review items with "
                f"missing shoot_id or undefined outfit metadata"
            )

        return "; ".join(parts) if parts else None


def validate_drip_schedule_outfits(
    schedule: list[dict],
    content_metadata: dict,
) -> dict:
    """Validate outfit consistency for all drip items in a schedule.

    Convenience function that filters a full schedule to drip items only
    and validates their outfit consistency.

    Args:
        schedule: Complete schedule list containing all send types.
            Each item should have a 'send_type' or 'send_type_key' field.
        content_metadata: Metadata dictionary containing shoot information:
            - shoots: Dict mapping shoot_id to shoot details including outfit_id

    Returns:
        Validation result dictionary with:
            - is_valid: True if no ERROR-level inconsistencies found
            - total_drip_items: Count of drip items found and validated
            - shoots_checked: Count of unique shoots validated
            - inconsistencies: List of inconsistency details
            - recommendation: Suggested action or None if valid
            - message: Success message if no drip items found

    Example:
        >>> schedule = [
        ...     {'id': 1, 'send_type_key': 'bump_drip', 'shoot_id': 'S1', 'outfit_id': 'O1'},
        ...     {'id': 2, 'send_type_key': 'ppv_unlock', 'shoot_id': 'S1', 'outfit_id': 'O2'},
        ...     {'id': 3, 'send_type_key': 'drip_set', 'shoot_id': 'S1', 'outfit_id': 'O1'},
        ... ]
        >>> metadata = {'shoots': {'S1': {'outfit_id': 'O1'}}}
        >>> result = validate_drip_schedule_outfits(schedule, metadata)
        >>> result['total_drip_items']
        2
    """
    # Filter to drip items only
    drip_items = [
        item for item in schedule
        if item.get('send_type_key') in DRIP_SEND_TYPES
        or item.get('send_type') in DRIP_SEND_TYPES
    ]

    if not drip_items:
        logger.info("No drip items found in schedule - skipping outfit validation")
        return {
            'is_valid': True,
            'total_drip_items': 0,
            'shoots_checked': 0,
            'inconsistencies': [],
            'recommendation': None,
            'message': 'No drip items in schedule - validation skipped',
        }

    validator = DripOutfitValidator()
    result = validator.validate_drip_outfit_consistency(drip_items, content_metadata)

    logger.info(
        "Drip outfit validation complete: %d items, %d shoots, valid=%s",
        result['total_drip_items'],
        result['shoots_checked'],
        result['is_valid'],
    )

    return result
