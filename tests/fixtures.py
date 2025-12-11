#!/usr/bin/env python3
"""
EROS Schedule Generator - Test Fixtures

Shared test fixtures and helper functions for the test suite.
Provides mock data generators for schedule items, captions, and validation scenarios.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def create_mock_schedule_item(
    item_id: int,
    scheduled_date: str,
    scheduled_time: str,
    item_type: str = "ppv",
    caption_id: int | None = None,
    caption_text: str | None = None,
    content_type_id: int | None = None,
    content_type_name: str | None = None,
    freshness_score: float = 80.0,
    performance_score: float = 75.0,
    suggested_price: float | None = None,
    is_follow_up: bool = False,
    parent_item_id: int | None = None,
    has_caption: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Create a mock schedule item dict for testing.

    Args:
        item_id: Unique identifier for the schedule item
        scheduled_date: Date in YYYY-MM-DD format
        scheduled_time: Time in HH:MM format
        item_type: Type of item (ppv, bump, wall_post, etc.)
        caption_id: Optional caption ID
        caption_text: Optional caption text
        content_type_id: Optional content type ID
        content_type_name: Optional content type name
        freshness_score: Freshness score (0-100)
        performance_score: Performance score (0-100)
        suggested_price: Optional suggested price
        is_follow_up: Whether this is a follow-up message
        parent_item_id: Parent item ID if follow-up
        has_caption: Whether to include caption fields
        **kwargs: Additional fields to include

    Returns:
        Dictionary representing a schedule item
    """
    item: dict[str, Any] = {
        "item_id": item_id,
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time,
        "item_type": item_type,
        "freshness_score": freshness_score,
        "performance_score": performance_score,
        "is_follow_up": is_follow_up,
    }

    if has_caption:
        item["caption_id"] = caption_id if caption_id is not None else item_id + 1000
        item["caption_text"] = (
            caption_text
            if caption_text is not None
            else f"Test caption {item_id}"
        )
    else:
        item["caption_id"] = None
        item["caption_text"] = None

    if content_type_id is not None:
        item["content_type_id"] = content_type_id
    if content_type_name is not None:
        item["content_type_name"] = content_type_name
    if suggested_price is not None:
        item["suggested_price"] = suggested_price
    if parent_item_id is not None:
        item["parent_item_id"] = parent_item_id

    item.update(kwargs)
    return item


def create_ppv_spacing_violation_items() -> list[dict[str, Any]]:
    """Create items with PPV spacing violation (< 3 hours)."""
    return [
        create_mock_schedule_item(1, "2025-01-06", "10:00"),
        create_mock_schedule_item(2, "2025-01-06", "11:30"),  # 1.5 hours - violation
        create_mock_schedule_item(3, "2025-01-06", "15:00"),  # OK from item 2
    ]


def create_duplicate_caption_items() -> list[dict[str, Any]]:
    """Create items with duplicate caption IDs."""
    return [
        create_mock_schedule_item(1, "2025-01-06", "10:00", caption_id=1001),
        create_mock_schedule_item(2, "2025-01-06", "14:00", caption_id=1001),  # Duplicate
        create_mock_schedule_item(3, "2025-01-06", "18:00", caption_id=1002),
    ]


def create_low_freshness_items() -> list[dict[str, Any]]:
    """Create items with low freshness scores."""
    return [
        create_mock_schedule_item(1, "2025-01-06", "10:00", freshness_score=20.0),  # Error
        create_mock_schedule_item(2, "2025-01-06", "14:00", freshness_score=28.0),  # Warning
        create_mock_schedule_item(3, "2025-01-06", "18:00", freshness_score=80.0),  # OK
    ]


def create_content_rotation_violation_items() -> list[dict[str, Any]]:
    """Create items with content rotation violation (4+ consecutive same type)."""
    return [
        create_mock_schedule_item(
            i, "2025-01-06", f"{10 + i}:00",
            content_type_id=1, content_type_name="solo"
        )
        for i in range(1, 5)  # 4 consecutive solo items
    ]


def create_follow_up_timing_violation_items() -> list[dict[str, Any]]:
    """Create items with follow-up timing violation."""
    return [
        create_mock_schedule_item(1, "2025-01-06", "10:00"),
        create_mock_schedule_item(
            2, "2025-01-06", "10:05",  # 5 minutes - too soon
            is_follow_up=True,
            parent_item_id=1,
        ),
    ]


def create_wall_post_items(count: int = 2, spacing_minutes: int = 120) -> list[dict[str, Any]]:
    """Create wall post items with specified spacing."""
    items = []
    base_dt = datetime(2025, 1, 6, 12, 0)

    for i in range(count):
        dt = base_dt + timedelta(minutes=i * spacing_minutes)
        items.append({
            "item_id": i + 1,
            "item_type": "wall_post",
            "scheduled_date": dt.strftime("%Y-%m-%d"),
            "scheduled_time": dt.strftime("%H:%M"),
        })

    return items


def create_poll_items(count: int = 2, spacing_days: int = 1) -> list[dict[str, Any]]:
    """Create poll items with specified spacing."""
    items = []
    base_date = date(2025, 1, 6)

    for i in range(count):
        poll_date = base_date + timedelta(days=i * spacing_days)
        items.append({
            "item_id": i + 1,
            "item_type": "poll",
            "scheduled_date": poll_date.strftime("%Y-%m-%d"),
            "scheduled_time": "12:00",
            "poll_duration_hours": 24,
        })

    return items


def create_page_type_violation_items() -> list[dict[str, Any]]:
    """Create items with paid-only content for free page testing."""
    return [
        {
            "item_id": 1,
            "item_type": "ppv",
            "scheduled_date": "2025-01-06",
            "scheduled_time": "10:00",
            "content_type_name": "vip_post",  # Paid-only content
        },
    ]


def create_valid_week_items(
    ppv_per_day: int = 4,
    start_date: date | None = None,
    days: int = 7,
) -> list[dict[str, Any]]:
    """
    Create a valid week of schedule items with proper spacing.

    Args:
        ppv_per_day: Number of PPV items per day
        start_date: Start date (defaults to 2025-01-06)
        days: Number of days to generate

    Returns:
        List of schedule items with proper spacing
    """
    if start_date is None:
        start_date = date(2025, 1, 6)

    items = []
    item_id = 0

    # Hours with 4-hour spacing to ensure compliance
    hours = [8, 12, 16, 20, 23][:ppv_per_day]

    for day in range(days):
        current_date = start_date + timedelta(days=day)

        for i, hour in enumerate(hours):
            item_id += 1
            items.append(
                create_mock_schedule_item(
                    item_id=item_id,
                    scheduled_date=current_date.strftime("%Y-%m-%d"),
                    scheduled_time=f"{hour:02d}:00",
                    content_type_id=(i % 3) + 1,  # Rotate content types
                    content_type_name=["solo", "bundle", "sextape"][i % 3],
                )
            )

    return items


def create_mock_caption(
    caption_id: int,
    caption_text: str = "",
    content_type_id: int = 1,
    content_type_name: str = "solo",
    freshness_score: float = 80.0,
    performance_score: float = 75.0,
    tone: str = "playful",
    hook_type: str = "question",
    times_used_on_page: int = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Create a mock caption dict for testing.

    Args:
        caption_id: Unique caption identifier
        caption_text: Caption text content
        content_type_id: Content type ID
        content_type_name: Content type name
        freshness_score: Freshness score (0-100)
        performance_score: Performance score (0-100)
        tone: Caption tone
        hook_type: Hook type
        times_used_on_page: Number of times used on this page
        **kwargs: Additional fields

    Returns:
        Dictionary representing a caption
    """
    caption = {
        "caption_id": caption_id,
        "caption_text": caption_text or f"Test caption text {caption_id}",
        "caption_type": "ppv",
        "content_type_id": content_type_id,
        "content_type_name": content_type_name,
        "freshness_score": freshness_score,
        "performance_score": performance_score,
        "tone": tone,
        "hook_type": hook_type,
        "times_used_on_page": times_used_on_page,
        "freshness_tier": "never_used" if times_used_on_page == 0 else "fresh",
    }
    caption.update(kwargs)
    return caption


def create_mock_selection_pool(
    creator_id: str = "test_creator",
    caption_count: int = 10,
    never_used_ratio: float = 0.5,
) -> dict[str, Any]:
    """
    Create a mock selection pool for testing.

    Args:
        creator_id: Creator identifier
        caption_count: Total number of captions
        never_used_ratio: Ratio of never-used captions (0-1)

    Returns:
        Dictionary representing a selection pool
    """
    captions = []
    never_used_count = int(caption_count * never_used_ratio)

    for i in range(caption_count):
        is_never_used = i < never_used_count
        captions.append(
            create_mock_caption(
                caption_id=i + 1,
                times_used_on_page=0 if is_never_used else 3,
                freshness_score=100.0 if is_never_used else 65.0,
            )
        )

    return {
        "creator_id": creator_id,
        "captions": captions,
        "never_used_count": never_used_count,
        "fresh_count": caption_count - never_used_count,
        "total_weight": sum(c["freshness_score"] for c in captions),
        "content_types": ["solo", "bundle", "sextape"],
    }


__all__ = [
    "create_mock_schedule_item",
    "create_ppv_spacing_violation_items",
    "create_duplicate_caption_items",
    "create_low_freshness_items",
    "create_content_rotation_violation_items",
    "create_follow_up_timing_violation_items",
    "create_wall_post_items",
    "create_poll_items",
    "create_page_type_violation_items",
    "create_valid_week_items",
    "create_mock_caption",
    "create_mock_selection_pool",
]
