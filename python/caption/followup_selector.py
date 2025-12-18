"""
Type-Specific Followup Caption Selector.

Provides deterministic and random selection of followup captions based on parent PPV type.
This module addresses Wave 4 Gap 2.4 by ensuring followup messages maintain authentic tone
that matches the original PPV content type.

Key Features:
- Type-specific templates (winner, bundle, solo, sextape)
- Deterministic seeding for reproducible schedule generation
- Fallback to default templates for unknown types
- Integration with schedule generation pipeline

Usage:
    from python.caption.followup_selector import select_followup_caption

    # Deterministic selection for schedule generation
    caption = select_followup_caption(
        parent_ppv_type='bundle',
        creator_id='creator_123',
        schedule_date=date(2025, 12, 16)
    )

    # Random selection for ad-hoc usage
    caption = select_followup_caption(parent_ppv_type='solo')
"""

import random
from datetime import date
from typing import Optional

from python.logging_config import get_logger

logger = get_logger(__name__)

# Followup templates by parent PPV type
# Each type has authentic, creator-voice messages that match the original content's tone
FOLLOWUP_TEMPLATES = {
    'winner': [
        "im so fucking excited that you are my one and only winner bby 🥰",
        "omg cant believe u actually won! wait till u see whats next 😈",
        "you're literally the luckiest person ever rn, open it already 🙈",
        "bby you won something crazy... dont make me wait to hear what u think 💕",
    ],
    'bundle': [
        "HOLY SHIT I FUCKED UP that bundle is suppose to be $100 😭",
        "OF glitched and sent that for way too cheap, grab it before i fix it 😳",
        "omg i didnt mean to price it that low... whatever just take it 🙈",
        "babe that bundle should NOT be that cheap, get it now before i change it 💀",
    ],
    'solo': [
        "you must be likin dick or somthin bc you dont even wanna see this 🙄",
        "u weird as hell for not wanting to see my pussy squirt everywhere 💦",
        "babe... you really dont wanna see what i did?? your loss ig 😒",
        "okay so ur just not gonna open it and see me cum?? mkay 🤷‍♀️",
    ],
    'sextape': [
        "bby you have to see this... its literally the best vid ive ever made 🥵",
        "this tape is actually crazy... i cant believe i did that on camera 😳",
        "you havent opened it yet?? trust me its worth every penny 💦",
        "im literally still shaking from this video... open it NOW 🙈",
    ],
    'default': [
        "hey babe did you see what i sent? 👀",
        "you havent opened my message yet... everything ok? 💕",
        "bby im waiting for you to open it 🥺",
        "dont leave me on read... open it already 😘",
    ]
}


def select_followup_caption(
    parent_ppv_type: str,
    creator_id: str | None = None,
    schedule_date: date | None = None,
    creator_tone: Optional[str] = None
) -> str:
    """
    Select followup caption matching parent PPV type.

    Uses deterministic seeding when creator_id and schedule_date are provided
    to ensure reproducible schedule generation for testing and debugging.

    Args:
        parent_ppv_type: Type of parent PPV (winner, bundle, solo, sextape)
        creator_id: Creator ID for deterministic seeding
        schedule_date: Schedule date for deterministic seeding
        creator_tone: Optional tone preference (not used yet, for future)

    Returns:
        Selected followup caption text

    Examples:
        >>> # Deterministic selection
        >>> caption = select_followup_caption(
        ...     'bundle',
        ...     creator_id='creator_123',
        ...     schedule_date=date(2025, 12, 16)
        ... )
        >>> # Will always return same caption for same inputs

        >>> # Random selection
        >>> caption = select_followup_caption('solo')
        >>> # Returns random caption from solo templates
    """
    # Get templates for parent type
    templates = FOLLOWUP_TEMPLATES.get(
        parent_ppv_type.lower(),
        FOLLOWUP_TEMPLATES['default']
    )

    # Use deterministic seeding for reproducibility when IDs provided
    if creator_id and schedule_date:
        seed = hash(f"{creator_id}:{schedule_date.isoformat()}:{parent_ppv_type}")
        rng = random.Random(seed)
        logger.debug(
            f"Using seeded RNG for followup selection: creator={creator_id}, date={schedule_date}",
            extra={
                "creator_id": creator_id,
                "schedule_date": schedule_date.isoformat(),
                "parent_ppv_type": parent_ppv_type,
                "seed": seed
            }
        )
        return rng.choice(templates)

    # Fallback to random selection if no seeding info provided
    logger.debug(
        f"Using random selection for followup: parent_type={parent_ppv_type}",
        extra={"parent_ppv_type": parent_ppv_type}
    )
    return random.choice(templates)


def get_followup_for_schedule_item(
    schedule_item: dict,
    creator_id: str | None = None,
    schedule_date: date | None = None
) -> str:
    """
    Get appropriate followup caption for a schedule item.

    This is a convenience wrapper around select_followup_caption that extracts
    the PPV type from a schedule item dictionary.

    Args:
        schedule_item: Schedule item dict with ppv_style field
        creator_id: Creator ID for deterministic seeding
        schedule_date: Schedule date for deterministic seeding

    Returns:
        Selected followup caption text

    Examples:
        >>> item = {'ppv_style': 'bundle', 'price': 25.00}
        >>> caption = get_followup_for_schedule_item(
        ...     item,
        ...     creator_id='creator_123',
        ...     schedule_date=date(2025, 12, 16)
        ... )
        >>> # Returns bundle-specific followup caption
    """
    parent_type = schedule_item.get('ppv_style', 'default')
    logger.debug(
        f"Getting followup for schedule item",
        extra={
            "parent_ppv_type": parent_type,
            "creator_id": creator_id,
            "schedule_date": schedule_date.isoformat() if schedule_date else None
        }
    )
    return select_followup_caption(
        parent_ppv_type=parent_type,
        creator_id=creator_id,
        schedule_date=schedule_date
    )
