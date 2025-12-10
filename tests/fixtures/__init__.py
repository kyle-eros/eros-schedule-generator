"""
Test fixtures for EROS Schedule Generator tests.

This package provides mock data for unit tests, allowing tests to run
without database connections.
"""

from .mock_captions import (
    MOCK_CAPTIONS,
    MOCK_CAPTIONS_DISCOVERY,
    MOCK_CAPTIONS_GLOBAL_EARNER,
    MOCK_CAPTIONS_PROVEN,
    create_mock_caption,
    create_mock_stratified_pools,
)
from .mock_creators import (
    MOCK_CREATOR_FREE,
    MOCK_CREATOR_PAID,
    MOCK_PERSONA,
    MOCK_PERSONAS_BY_TONE,
    create_mock_creator_profile,
    create_mock_persona_profile,
)
from .mock_schedule import (
    MOCK_SCHEDULE_ITEMS,
    MOCK_SCHEDULE_RESULT,
    create_mock_schedule_config,
    create_mock_schedule_item,
    create_ppv_spacing_violation_items,
    create_duplicate_caption_items,
    create_low_freshness_items,
    create_content_rotation_violation_items,
    create_follow_up_timing_violation_items,
    create_wall_post_items,
    create_poll_items,
    create_page_type_violation_items,
    create_valid_week_items,
)

__all__ = [
    # Captions
    "MOCK_CAPTIONS",
    "MOCK_CAPTIONS_PROVEN",
    "MOCK_CAPTIONS_GLOBAL_EARNER",
    "MOCK_CAPTIONS_DISCOVERY",
    "create_mock_caption",
    "create_mock_stratified_pools",
    # Creators
    "MOCK_CREATOR_PAID",
    "MOCK_CREATOR_FREE",
    "MOCK_PERSONA",
    "MOCK_PERSONAS_BY_TONE",
    "create_mock_creator_profile",
    "create_mock_persona_profile",
    # Schedule
    "MOCK_SCHEDULE_ITEMS",
    "MOCK_SCHEDULE_RESULT",
    "create_mock_schedule_config",
    "create_mock_schedule_item",
    # Validation test helpers
    "create_ppv_spacing_violation_items",
    "create_duplicate_caption_items",
    "create_low_freshness_items",
    "create_content_rotation_violation_items",
    "create_follow_up_timing_violation_items",
    "create_wall_post_items",
    "create_poll_items",
    "create_page_type_violation_items",
    "create_valid_week_items",
]
