"""Caption selection and management for EROS scheduling system."""

from python.caption.followup_selector import (
    FOLLOWUP_TEMPLATES,
    select_followup_caption,
    get_followup_for_schedule_item,
)

__all__ = [
    "FOLLOWUP_TEMPLATES",
    "select_followup_caption",
    "get_followup_for_schedule_item",
]
