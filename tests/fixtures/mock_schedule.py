"""
Mock schedule data for testing.

Provides sample schedule items, schedule configs, and schedule results
for testing the pipeline and validation.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Add scripts to path for imports
TESTS_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# =============================================================================
# SCHEDULE CONFIG MOCK
# =============================================================================


@dataclass(frozen=True, slots=True)
class MockScheduleConfig:
    """Mock schedule config for testing (mirrors models.ScheduleConfig)."""

    creator_id: str
    creator_name: str
    page_type: str
    week_start: date
    week_end: date
    volume_level: str = "Mid"
    ppv_per_day: int = 4
    bump_per_day: int = 4
    min_freshness: float = 30.0
    performance_weight: float = 0.6
    freshness_weight: float = 0.4
    min_ppv_spacing_hours: int = 3
    enable_follow_ups: bool = True
    enable_drip_windows: bool = False
    enable_page_type_rules: bool = True
    mode: str = "full"
    use_agents: bool = False


# =============================================================================
# SCHEDULE ITEM MOCK (as dict for validator compatibility)
# =============================================================================


def create_mock_schedule_item(
    item_id: int,
    scheduled_date: str,
    scheduled_time: str,
    item_type: str = "ppv",
    caption_id: int | None = None,
    caption_text: str | None = None,
    content_type_id: int | None = 1,
    content_type_name: str | None = "solo",
    freshness_score: float = 80.0,
    performance_score: float = 70.0,
    is_follow_up: bool = False,
    parent_item_id: int | None = None,
    has_caption: bool = True,
) -> dict[str, Any]:
    """Create a mock schedule item as dict (for validator compatibility)."""
    return {
        "item_id": item_id,
        "creator_id": "test-creator",
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time,
        "item_type": item_type,
        "channel": "mass_message",
        "caption_id": caption_id or item_id,
        "caption_text": caption_text or f"Caption for item {item_id}",
        "content_type_id": content_type_id,
        "content_type_name": content_type_name,
        "suggested_price": 15.00,
        "freshness_score": freshness_score,
        "performance_score": performance_score,
        "is_follow_up": is_follow_up,
        "parent_item_id": parent_item_id,
        "status": "pending",
        "priority": 5,
        "has_caption": has_caption,
    }


# =============================================================================
# SAMPLE SCHEDULE ITEMS
# =============================================================================

# A week's worth of schedule items (Monday-Sunday)
MOCK_SCHEDULE_ITEMS: list[dict[str, Any]] = [
    # Monday
    create_mock_schedule_item(1, "2025-01-06", "10:00", caption_id=1001),
    create_mock_schedule_item(2, "2025-01-06", "14:00", caption_id=1002),
    create_mock_schedule_item(3, "2025-01-06", "18:00", caption_id=1003),
    create_mock_schedule_item(4, "2025-01-06", "21:00", caption_id=1004),
    # Tuesday
    create_mock_schedule_item(5, "2025-01-07", "10:00", caption_id=2001),
    create_mock_schedule_item(6, "2025-01-07", "14:00", caption_id=2002),
    create_mock_schedule_item(7, "2025-01-07", "18:00", caption_id=2003),
    create_mock_schedule_item(8, "2025-01-07", "21:00", caption_id=2004),
    # Wednesday
    create_mock_schedule_item(9, "2025-01-08", "10:00", caption_id=3001),
    create_mock_schedule_item(10, "2025-01-08", "14:00", caption_id=3002),
    create_mock_schedule_item(11, "2025-01-08", "18:00", caption_id=3003),
    create_mock_schedule_item(12, "2025-01-08", "21:00", caption_id=3004),
]


# =============================================================================
# VALIDATION TEST ITEMS
# =============================================================================


def create_ppv_spacing_violation_items() -> list[dict[str, Any]]:
    """Create items with PPV spacing violation (< 3 hours)."""
    return [
        create_mock_schedule_item(1, "2025-01-06", "10:00", caption_id=1001),
        create_mock_schedule_item(
            2, "2025-01-06", "12:00", caption_id=1002
        ),  # Only 2 hours!
    ]


def create_duplicate_caption_items() -> list[dict[str, Any]]:
    """Create items with duplicate caption IDs."""
    return [
        create_mock_schedule_item(1, "2025-01-06", "10:00", caption_id=1001),
        create_mock_schedule_item(2, "2025-01-07", "14:00", caption_id=1001),  # Duplicate!
    ]


def create_low_freshness_items() -> list[dict[str, Any]]:
    """Create items with freshness below threshold."""
    return [
        create_mock_schedule_item(
            1, "2025-01-06", "10:00", freshness_score=80.0, caption_id=1001
        ),
        create_mock_schedule_item(
            2, "2025-01-06", "14:00", freshness_score=25.0, caption_id=1002
        ),  # Too low!
    ]


def create_content_rotation_violation_items() -> list[dict[str, Any]]:
    """Create items with same content type 4+ times consecutively."""
    return [
        create_mock_schedule_item(
            1, "2025-01-06", "10:00", content_type_id=1, content_type_name="solo"
        ),
        create_mock_schedule_item(
            2, "2025-01-06", "14:00", content_type_id=1, content_type_name="solo"
        ),
        create_mock_schedule_item(
            3, "2025-01-06", "18:00", content_type_id=1, content_type_name="solo"
        ),
        create_mock_schedule_item(
            4, "2025-01-06", "22:00", content_type_id=1, content_type_name="solo"
        ),  # 4th consecutive!
    ]


def create_follow_up_timing_violation_items() -> list[dict[str, Any]]:
    """Create follow-up with incorrect timing (too soon)."""
    return [
        create_mock_schedule_item(1, "2025-01-06", "10:00", caption_id=1001),
        create_mock_schedule_item(
            2,
            "2025-01-06",
            "10:05",
            caption_id=1002,
            is_follow_up=True,
            parent_item_id=1,
        ),  # Only 5 min!
    ]


def create_wall_post_items() -> list[dict[str, Any]]:
    """Create wall post items for testing."""
    return [
        {
            "item_id": 1,
            "item_type": "wall_post",
            "scheduled_date": "2025-01-06",
            "scheduled_time": "12:00",
            "caption_id": 5001,
            "caption_text": "Check out my new content!",
        },
        {
            "item_id": 2,
            "item_type": "wall_post",
            "scheduled_date": "2025-01-06",
            "scheduled_time": "16:00",
            "caption_id": 5002,
            "caption_text": "More coming soon!",
        },
    ]


def create_poll_items() -> list[dict[str, Any]]:
    """Create poll items for testing."""
    return [
        {
            "item_id": 1,
            "item_type": "poll",
            "scheduled_date": "2025-01-06",
            "scheduled_time": "12:00",
            "poll_duration_hours": 24,
            "caption_text": "What should I post next?",
        },
        {
            "item_id": 2,
            "item_type": "poll",
            "scheduled_date": "2025-01-08",
            "scheduled_time": "12:00",
            "poll_duration_hours": 48,
            "caption_text": "Pick your favorite!",
        },
    ]


def create_page_type_violation_items() -> list[dict[str, Any]]:
    """Create items with paid-only content on free page."""
    return [
        create_mock_schedule_item(1, "2025-01-06", "10:00", content_type_name="solo"),
        {
            "item_id": 2,
            "item_type": "ppv",
            "scheduled_date": "2025-01-06",
            "scheduled_time": "14:00",
            "content_type_name": "vip_post",  # Paid-only!
            "has_caption": True,
        },
    ]


# =============================================================================
# SCHEDULE RESULT MOCK
# =============================================================================


@dataclass(slots=True)
class MockScheduleResult:
    """Mock schedule result for testing."""

    schedule_id: str
    creator_id: str
    creator_name: str
    display_name: str
    page_type: str
    week_start: str
    week_end: str
    volume_level: str
    items: list[dict[str, Any]] = field(default_factory=list)
    total_ppvs: int = 0
    total_bumps: int = 0
    total_follow_ups: int = 0
    total_drip: int = 0
    unique_captions: int = 0
    avg_freshness: float = 0.0
    avg_performance: float = 0.0
    validation_passed: bool = True
    validation_issues: list[Any] = field(default_factory=list)
    generated_at: str = ""
    best_hours: list[int] = field(default_factory=list)
    vault_types: list[str] = field(default_factory=list)


MOCK_SCHEDULE_RESULT = MockScheduleResult(
    schedule_id="test-schedule-001",
    creator_id="test-creator-001",
    creator_name="testcreator",
    display_name="Test Creator",
    page_type="paid",
    week_start="2025-01-06",
    week_end="2025-01-12",
    volume_level="Mid",
    items=MOCK_SCHEDULE_ITEMS,
    total_ppvs=12,
    total_bumps=0,
    total_follow_ups=0,
    total_drip=0,
    unique_captions=12,
    avg_freshness=80.0,
    avg_performance=70.0,
    validation_passed=True,
    validation_issues=[],
    generated_at="2025-01-05T10:00:00",
    best_hours=[10, 14, 18, 21],
    vault_types=["solo", "sextape", "bg"],
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_mock_schedule_config(
    creator_id: str = "test-creator",
    creator_name: str = "testcreator",
    page_type: str = "paid",
    week_start: date | None = None,
    week_end: date | None = None,
    volume_level: str = "Mid",
    ppv_per_day: int = 4,
    mode: str = "full",
) -> MockScheduleConfig:
    """Create a mock schedule config with specified attributes."""
    if week_start is None:
        week_start = date(2025, 1, 6)  # Monday
    if week_end is None:
        week_end = week_start + timedelta(days=6)

    return MockScheduleConfig(
        creator_id=creator_id,
        creator_name=creator_name,
        page_type=page_type,
        week_start=week_start,
        week_end=week_end,
        volume_level=volume_level,
        ppv_per_day=ppv_per_day,
        mode=mode,
    )


def create_valid_week_items(
    week_start: str = "2025-01-06",
    ppv_per_day: int = 4,
    hours: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Create a full week of valid schedule items."""
    if hours is None:
        hours = [10, 14, 18, 21]

    items = []
    item_id = 1
    start_date = date.fromisoformat(week_start)

    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.isoformat()

        for hour in hours[:ppv_per_day]:
            items.append(
                create_mock_schedule_item(
                    item_id=item_id,
                    scheduled_date=date_str,
                    scheduled_time=f"{hour:02d}:00",
                    caption_id=item_id,
                )
            )
            item_id += 1

    return items
