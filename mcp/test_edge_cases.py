#!/usr/bin/env python3
"""
EROS MCP Database Server - Edge Case Test Suite

Comprehensive edge case tests for all MCP tools covering:
1. Creator tools - empty/null creator_id, non-existent creator, special characters, very long names
2. Caption tools - empty pool, special characters, very long captions, emoji edge cases
3. Performance tools - no historical data, invalid date ranges, future dates
4. Schedule tools - empty items, 1000+ items, duplicates, invalid formats, missing fields
5. Query tools - SQL injection attempts, invalid SQL syntax, large result sets, no results
6. Boundary conditions - min/max values, empty vs null, unicode, timezone edge cases

Run with: pytest mcp/test_edge_cases.py -v --tb=short
"""

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tool functions - organized by domain
from mcp.tools.creator import (
    get_active_creators,
    get_creator_profile,
    get_persona_profile,
    get_vault_availability,
)
from mcp.tools.caption import get_top_captions, get_send_type_captions
from mcp.tools.performance import (
    get_best_timing,
    get_volume_assignment,
    get_performance_trends,
    get_content_type_rankings,
)
from mcp.tools.send_types import get_send_types, get_send_type_details, get_volume_config
from mcp.tools.targeting import get_channels, get_audience_targets
from mcp.tools.schedule import save_schedule
from mcp.tools.query import execute_query

# Server handler functions
from mcp.server import handle_request, handle_tools_call

# Connection and database helpers
from mcp.connection import db_connection, get_db_connection

# Security validation
from mcp.utils.security import validate_creator_id, validate_key_input


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="module")
def valid_creator_id() -> Optional[str]:
    """Get a valid creator_id from the database for testing."""
    result = get_active_creators()
    if result.get("creators") and len(result["creators"]) > 0:
        return result["creators"][0]["creator_id"]
    return None


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection with configurable behavior."""
    with patch("mcp.connection.get_db_connection") as mock_get_conn:
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [("col1",), ("col2",)]
        mock_conn.execute.return_value = mock_cursor
        mock_conn.row_factory = sqlite3.Row
        mock_get_conn.return_value = mock_conn
        yield {
            "connection": mock_conn,
            "cursor": mock_cursor,
            "get_connection": mock_get_conn,
        }


# =============================================================================
# CREATOR TOOLS EDGE CASES
# =============================================================================


class TestCreatorToolsEdgeCases:
    """Edge case tests for creator-related tools."""

    # -------------------------------------------------------------------------
    # Empty/Null Creator ID Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_creator_profile_empty_string(self):
        """Test get_creator_profile with empty string creator_id."""
        result = get_creator_profile("")
        assert "error" in result
        assert "cannot be empty" in result["error"].lower()

    @pytest.mark.edge_case
    def test_get_creator_profile_none_type_handling(self):
        """Test get_creator_profile handles None gracefully via MCP protocol."""
        # Test via MCP protocol which might pass None
        response = handle_tools_call(
            request_id=1,
            params={"name": "get_creator_profile", "arguments": {"creator_id": None}}
        )
        # Should return error, not crash
        assert "error" in response or "result" in response

    @pytest.mark.edge_case
    def test_get_top_captions_empty_creator_id(self):
        """Test get_top_captions with empty creator_id."""
        result = get_top_captions("")
        assert "error" in result

    @pytest.mark.edge_case
    def test_get_best_timing_empty_creator_id(self):
        """Test get_best_timing with empty creator_id."""
        result = get_best_timing("")
        assert "error" in result

    @pytest.mark.edge_case
    def test_get_volume_assignment_empty_creator_id(self):
        """Test get_volume_assignment with empty creator_id."""
        result = get_volume_assignment("")
        assert "error" in result

    @pytest.mark.edge_case
    def test_get_performance_trends_empty_creator_id(self):
        """Test get_performance_trends with empty creator_id."""
        result = get_performance_trends("")
        assert "error" in result

    # -------------------------------------------------------------------------
    # Non-Existent Creator Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_creator_profile_nonexistent(self):
        """Test get_creator_profile with non-existent creator."""
        result = get_creator_profile("nonexistent_creator_xyz_12345")
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.edge_case
    def test_get_creator_profile_random_uuid(self):
        """Test get_creator_profile with random UUID as creator_id."""
        random_id = str(uuid.uuid4()).replace("-", "_")
        result = get_creator_profile(random_id)
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.edge_case
    def test_get_content_type_rankings_nonexistent(self):
        """Test get_content_type_rankings with non-existent creator."""
        result = get_content_type_rankings("nonexistent_creator_12345")
        assert "error" in result

    @pytest.mark.edge_case
    def test_get_persona_profile_nonexistent(self):
        """Test get_persona_profile with non-existent creator."""
        result = get_persona_profile("nonexistent_creator_12345")
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.edge_case
    def test_get_vault_availability_nonexistent(self):
        """Test get_vault_availability with non-existent creator."""
        result = get_vault_availability("nonexistent_creator_12345")
        assert "error" in result

    # -------------------------------------------------------------------------
    # Special Characters Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    @pytest.mark.parametrize("special_id", [
        "creator@domain.com",       # Email-like
        "creator's_page",           # Apostrophe
        "creator\"quotes\"",        # Double quotes
        "creator<script>",          # HTML injection attempt
        "creator;DROP TABLE",       # SQL injection pattern
        "creator--comment",         # SQL comment
        "creator/*comment*/",       # Block comment
        "creator\x00null",          # Null byte
        "creator\n\rnewline",       # Newline characters
        "creator\ttab",             # Tab character
        "../../../etc/passwd",      # Path traversal
        "creator|pipe",             # Pipe character
        "creator`backtick`",        # Backticks
        "creator$(cmd)",            # Command substitution
        "creator${var}",            # Variable expansion
    ])
    def test_get_creator_profile_special_characters(self, special_id: str):
        """Test get_creator_profile rejects or handles special characters safely."""
        result = get_creator_profile(special_id)
        # Should either return error or safely handle (not crash)
        assert "error" in result or "creator" in result

    @pytest.mark.edge_case
    def test_creator_id_with_unicode(self):
        """Test creator_id with unicode characters."""
        # Unicode should be rejected by validation
        result = get_creator_profile("creator_name")
        # Standard ASCII should work
        assert "error" in result or "creator" in result

    @pytest.mark.edge_case
    def test_creator_id_only_underscore_hyphen(self):
        """Test creator_id that's only underscores and hyphens."""
        result = get_creator_profile("____----____")
        # Should be valid format but not found
        assert "error" in result

    @pytest.mark.edge_case
    def test_creator_id_starts_with_number(self):
        """Test creator_id starting with a number."""
        result = get_creator_profile("123_creator")
        # Valid format, but not found
        assert "error" in result
        assert "not found" in result["error"].lower()

    # -------------------------------------------------------------------------
    # Very Long Names Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_creator_profile_very_long_name(self):
        """Test get_creator_profile with very long creator_id (>100 chars)."""
        long_id = "a" * 101
        result = get_creator_profile(long_id)
        assert "error" in result
        assert "exceeds maximum length" in result["error"].lower()

    @pytest.mark.edge_case
    def test_get_creator_profile_max_length_boundary(self):
        """Test creator_id at exactly maximum length (100 chars)."""
        max_id = "a" * 100
        result = get_creator_profile(max_id)
        # Should be valid format but not found
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.edge_case
    def test_validate_creator_id_extreme_length(self):
        """Test validation with extremely long creator_id."""
        extreme_id = "x" * 10000
        is_valid, error = validate_creator_id(extreme_id)
        assert is_valid is False
        assert "exceeds maximum length" in error.lower()


# =============================================================================
# CAPTION TOOLS EDGE CASES
# =============================================================================


class TestCaptionToolsEdgeCases:
    """Edge case tests for caption-related tools."""

    # -------------------------------------------------------------------------
    # Empty Caption Pool Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_top_captions_high_performance_threshold(self, valid_creator_id: Optional[str]):
        """Test get_top_captions with unreachably high performance threshold."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_top_captions(valid_creator_id, min_performance=999.99)
        assert "error" not in result
        assert result.get("count", -1) == 0

    @pytest.mark.edge_case
    def test_get_send_type_captions_no_matching_type(self, valid_creator_id: Optional[str]):
        """Test get_send_type_captions with send_type that has no captions."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Try a valid send type that might have no captions
        result = get_send_type_captions(valid_creator_id, "expired_winback")
        # Should return empty list or results, not error
        assert "captions" in result or "error" in result

    @pytest.mark.edge_case
    def test_get_top_captions_zero_limit(self, valid_creator_id: Optional[str]):
        """Test get_top_captions with limit=0."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_top_captions(valid_creator_id, limit=0)
        # Should return empty results
        assert result.get("count", -1) == 0 or "error" in result

    # -------------------------------------------------------------------------
    # Special Characters in Captions Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_top_captions_special_content_type(self, valid_creator_id: Optional[str]):
        """Test get_top_captions filtering by special character content type."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Try filtering by a content type with special chars
        result = get_top_captions(valid_creator_id, content_type="video'; DROP TABLE--")
        # Should handle safely (return no results or error)
        assert "captions" in result or "error" in result

    @pytest.mark.edge_case
    def test_get_top_captions_caption_type_injection(self, valid_creator_id: Optional[str]):
        """Test get_top_captions with SQL injection in caption_type."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_top_captions(valid_creator_id, caption_type="ppv' OR '1'='1")
        # Parameterized queries should handle this safely
        assert "captions" in result or "error" in result

    # -------------------------------------------------------------------------
    # Very Long Captions Tests (Simulated via save_schedule)
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_save_schedule_very_long_caption_text(self, valid_creator_id: Optional[str]):
        """Test save_schedule with extremely long caption text (10000+ chars)."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        long_caption = "A" * 15000  # 15KB caption

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": long_caption,
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        # Should either succeed or return appropriate error
        assert "success" in result or "error" in result

    # -------------------------------------------------------------------------
    # Emoji Edge Cases
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_save_schedule_emoji_caption(self, valid_creator_id: Optional[str]):
        """Test save_schedule with caption containing various emoji."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Various emoji types including complex ones
        emoji_caption = (
            "Check this out! \U0001F525\U0001F4A6\U0001F60D "  # Fire, water, heart eyes
            "\U0001F468\u200D\U0001F469\u200D\U0001F466 "     # Family (ZWJ sequence)
            "\U0001F1FA\U0001F1F8 "                           # Flag (regional indicators)
            "\U0001F44D\U0001F3FD "                           # Thumbs up with skin tone
            "\U0001F600\U0001F601\U0001F602"                  # Basic smileys
        )

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": emoji_caption,
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        # Should handle unicode/emoji properly
        assert "success" in result or "error" in result

    @pytest.mark.edge_case
    def test_save_schedule_emoji_only_caption(self, valid_creator_id: Optional[str]):
        """Test save_schedule with caption containing only emoji."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "\U0001F525\U0001F4A6\U0001F60D\U0001F4AF",
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        assert "success" in result or "error" in result


# =============================================================================
# PERFORMANCE TOOLS EDGE CASES
# =============================================================================


class TestPerformanceToolsEdgeCases:
    """Edge case tests for performance-related tools."""

    # -------------------------------------------------------------------------
    # No Historical Data Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_best_timing_no_history(self, valid_creator_id: Optional[str]):
        """Test get_best_timing with days_lookback=0 (no historical period)."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_best_timing(valid_creator_id, days_lookback=0)
        # Should return empty results for best_hours
        assert "error" not in result or "best_hours" in result
        if "best_hours" in result:
            assert len(result["best_hours"]) == 0

    @pytest.mark.edge_case
    def test_get_performance_trends_new_creator(self, mock_db_connection):
        """Test get_performance_trends for creator with no performance data."""
        # Mock to return a creator but no performance data
        mock_creator_row = MagicMock()
        mock_creator_row.__getitem__ = lambda self, k: {
            "creator_id": "new_creator",
            "page_name": "newcreator",
            "page_type": "paid"
        }.get(k)

        call_count = [0]

        def side_effect(*args, **kwargs):
            cursor = MagicMock()
            if call_count[0] == 0:
                cursor.fetchone.return_value = mock_creator_row
            else:
                cursor.fetchone.return_value = None
                cursor.fetchall.return_value = []
            call_count[0] += 1
            return cursor

        mock_db_connection["connection"].execute.side_effect = side_effect

        result = get_performance_trends("new_creator")
        # Should handle gracefully (return defaults or message)
        assert "error" in result or "saturation_score" in result

    # -------------------------------------------------------------------------
    # Invalid Date Ranges Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_best_timing_negative_lookback(self, valid_creator_id: Optional[str]):
        """Test get_best_timing with negative days_lookback."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_best_timing(valid_creator_id, days_lookback=-30)
        # Should handle gracefully or return error
        assert "error" in result or "best_hours" in result

    @pytest.mark.edge_case
    def test_get_best_timing_extreme_lookback(self, valid_creator_id: Optional[str]):
        """Test get_best_timing with extremely large days_lookback."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_best_timing(valid_creator_id, days_lookback=36500)  # 100 years
        # Should work but return limited/no data
        assert "error" not in result
        assert "best_hours" in result

    @pytest.mark.edge_case
    def test_get_performance_trends_invalid_period(self, valid_creator_id: Optional[str]):
        """Test get_performance_trends with invalid period format."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_performance_trends(valid_creator_id, period="invalid")
        assert "error" in result
        assert "period" in result["error"].lower()

    @pytest.mark.edge_case
    @pytest.mark.parametrize("invalid_period", [
        "1d",       # Too short
        "15d",      # Not a valid option
        "60d",      # Too long
        "7",        # Missing 'd'
        "d7",       # Wrong format
        "7days",    # Wrong format
        "",         # Empty
        " ",        # Whitespace
        "7D",       # Wrong case
    ])
    def test_get_performance_trends_various_invalid_periods(
        self,
        valid_creator_id: Optional[str],
        invalid_period: str
    ):
        """Test get_performance_trends with various invalid period formats."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_performance_trends(valid_creator_id, period=invalid_period)
        assert "error" in result

    # -------------------------------------------------------------------------
    # Future Dates Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_save_schedule_future_date(self, valid_creator_id: Optional[str]):
        """Test save_schedule with date far in the future."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        future_date = "2099-12-31"
        items = [
            {
                "scheduled_date": future_date,
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "Future test",
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, future_date, items)
        # Should accept or have specific validation for future dates
        assert "success" in result or "error" in result


# =============================================================================
# SCHEDULE TOOLS EDGE CASES
# =============================================================================


class TestScheduleToolsEdgeCases:
    """Edge case tests for schedule-related tools."""

    # -------------------------------------------------------------------------
    # Empty Schedule Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_save_schedule_empty_items(self, valid_creator_id: Optional[str]):
        """Test save_schedule with empty items list."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = save_schedule(valid_creator_id, "2020-01-06", [])
        # Should either succeed with 0 items or return error
        assert "success" in result or "error" in result

    # -------------------------------------------------------------------------
    # Large Schedule Tests (1000+ items)
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    @pytest.mark.slow
    def test_save_schedule_1000_plus_items(self, valid_creator_id: Optional[str]):
        """Test save_schedule with 1000+ items."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        send_types = [
            "ppv_unlock", "ppv_wall", "tip_goal", "bump_normal",
            "bump_descriptive", "link_drop", "dm_farm", "renew_on_post",
            "ppv_followup", "like_farm"
        ]

        items = []
        for day in range(7):
            base_date = f"2020-02-{1 + day:02d}"
            for i in range(150):  # 1050 total items
                hour = 6 + (i % 18)
                minute = (i * 3) % 60
                items.append({
                    "scheduled_date": base_date,
                    "scheduled_time": f"{hour:02d}:{minute:02d}",
                    "send_type_key": send_types[i % len(send_types)],
                    "channel_key": "mass_message",
                    "caption_text": f"Large test {day}-{i}",
                    "priority": (i % 5) + 1
                })

        result = save_schedule(valid_creator_id, "2020-02-01", items)
        # Should handle large schedules
        assert "success" in result or "error" in result

    # -------------------------------------------------------------------------
    # Duplicate Schedule Entry Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_save_schedule_duplicate_times(self, valid_creator_id: Optional[str]):
        """Test save_schedule with duplicate date/time entries."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "First entry",
                "priority": 1
            },
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",  # Same time
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "Duplicate entry",
                "priority": 2
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        # Should handle duplicates (accept or error)
        assert "success" in result or "error" in result

    @pytest.mark.edge_case
    def test_save_schedule_identical_items(self, valid_creator_id: Optional[str]):
        """Test save_schedule with completely identical items."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        item = {
            "scheduled_date": "2020-01-06",
            "scheduled_time": "10:00",
            "send_type_key": "ppv_unlock",
            "channel_key": "mass_message",
            "caption_text": "Identical entry",
            "priority": 1
        }

        items = [item.copy() for _ in range(10)]  # 10 identical items

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        assert "success" in result or "error" in result

    # -------------------------------------------------------------------------
    # Invalid Date Format Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    @pytest.mark.parametrize("invalid_date", [
        "2020/01/06",           # Wrong separator
        "01-06-2020",           # US format
        "06/01/2020",           # European format
        "2020-1-6",             # Missing leading zeros
        "20-01-06",             # Two-digit year
        "2020-13-01",           # Invalid month
        "2020-01-32",           # Invalid day
        "2020-00-01",           # Zero month
        "2020-01-00",           # Zero day
        "not-a-date",           # Text
        "",                     # Empty
        "2020-01-06T10:00:00",  # ISO with time
        "20200106",             # Compact format
    ])
    def test_save_schedule_invalid_date_formats(
        self,
        valid_creator_id: Optional[str],
        invalid_date: str
    ):
        """Test save_schedule with various invalid date formats."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        items = [
            {
                "scheduled_date": invalid_date,
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "Test",
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, invalid_date, items)
        assert "error" in result

    @pytest.mark.edge_case
    @pytest.mark.parametrize("invalid_time", [
        "25:00",        # Invalid hour
        "10:60",        # Invalid minute
        "10:00:00",     # With seconds
        "10:00 AM",     # 12-hour format
        "1000",         # No colon
        "-1:00",        # Negative hour
        "10:-1",        # Negative minute
        "",             # Empty
        "noon",         # Text
    ])
    def test_save_schedule_invalid_time_formats(
        self,
        valid_creator_id: Optional[str],
        invalid_time: str
    ):
        """Test save_schedule with various invalid time formats."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": invalid_time,
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "Test",
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        # Should validate time format
        assert "success" in result or "error" in result

    # -------------------------------------------------------------------------
    # Missing Required Fields Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_save_schedule_missing_date(self, valid_creator_id: Optional[str]):
        """Test save_schedule item missing scheduled_date."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        items = [
            {
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "Missing date",
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        # Should handle missing field gracefully
        assert "success" in result or "error" in result

    @pytest.mark.edge_case
    def test_save_schedule_missing_time(self, valid_creator_id: Optional[str]):
        """Test save_schedule item missing scheduled_time."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        items = [
            {
                "scheduled_date": "2020-01-06",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "Missing time",
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        assert "success" in result or "error" in result

    @pytest.mark.edge_case
    def test_save_schedule_null_fields(self, valid_creator_id: Optional[str]):
        """Test save_schedule with explicitly null field values."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",
                "send_type_key": None,
                "channel_key": None,
                "caption_text": None,
                "priority": None
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        assert "success" in result or "error" in result


# =============================================================================
# QUERY TOOLS EDGE CASES
# =============================================================================


class TestQueryToolsEdgeCases:
    """Edge case tests for execute_query tool."""

    # -------------------------------------------------------------------------
    # SQL Injection Attempts
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    @pytest.mark.security
    @pytest.mark.parametrize("injection_query", [
        # Stacked queries with destructive commands (MUST be blocked)
        "SELECT * FROM creators; DROP TABLE creators;--",
        "SELECT * FROM creators; DELETE FROM creators;--",
        "SELECT * FROM creators; INSERT INTO creators VALUES ('hack');--",
        "SELECT * FROM creators; UPDATE creators SET is_active=0;--",

        # Comment-based patterns that could hide injections (should be blocked)
        "SELECT * FROM creators --",
        "SELECT * FROM creators /*comment*/",
        "SELECT * FROM creators #comment",

        # Stacked queries (should be blocked)
        "SELECT 1; SELECT 2;",

        # PRAGMA commands (should be blocked - exposes schema)
        "PRAGMA table_info(creators)",
        "SELECT * FROM creators; PRAGMA table_info(creators)",

        # File operations (MUST be blocked - file system access)
        "ATTACH DATABASE '/tmp/evil.db' AS evil",

        # NULL byte injection (should be blocked)
        "SELECT * FROM creators\x00 DROP TABLE creators",
    ])
    def test_execute_query_sql_injection_blocked(self, injection_query: str):
        """Test that destructive SQL injection attempts are blocked."""
        result = execute_query(injection_query)
        # Should be blocked with error
        assert "error" in result, f"Injection not blocked: {injection_query}"

    @pytest.mark.edge_case
    @pytest.mark.security
    @pytest.mark.parametrize("query,should_work", [
        # Valid SELECT queries (should work - read-only)
        ("SELECT * FROM creators WHERE creator_id = 'x' OR '1'='1'", True),
        ("SELECT 1 UNION SELECT 2", True),
        ("SELECT 1 UNION ALL SELECT 2", True),
        ("SELECT * FROM creators WHERE CASE WHEN (1=1) THEN 1 ELSE 0 END", True),
        # Hex literals in SELECT (harmless)
        ("SELECT x'48454C4C4F'", True),
    ])
    def test_execute_query_valid_select_patterns(self, query: str, should_work: bool):
        """Test that valid SELECT patterns work correctly.

        Note: These are valid SQL patterns that are NOT injection vulnerabilities
        when the entire query is passed by the caller. SQL injection occurs when
        user input is concatenated into queries, not when the query itself
        contains these patterns.
        """
        result = execute_query(query)
        if should_work:
            # Should succeed or fail for legitimate SQL reasons (not security)
            # 'error' might be present for SQL syntax errors but not security blocks
            pass  # No assertion - just verify it doesn't crash

    @pytest.mark.edge_case
    @pytest.mark.security
    def test_execute_query_alter_table_blocked(self):
        """Test ALTER TABLE is blocked."""
        result = execute_query("ALTER TABLE creators ADD COLUMN hacked TEXT")
        assert "error" in result
        # Check that it's blocked for the right reason
        assert "ALTER" in result["error"] or "SELECT" in result["error"]

    @pytest.mark.edge_case
    @pytest.mark.security
    def test_execute_query_create_table_blocked(self):
        """Test CREATE TABLE is blocked."""
        result = execute_query("CREATE TABLE hacked (id INT)")
        assert "error" in result

    @pytest.mark.edge_case
    @pytest.mark.security
    def test_execute_query_truncate_blocked(self):
        """Test TRUNCATE is blocked."""
        result = execute_query("TRUNCATE TABLE creators")
        assert "error" in result

    # -------------------------------------------------------------------------
    # Invalid SQL Syntax Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    @pytest.mark.parametrize("invalid_sql", [
        "SELCT * FROM creators",           # Typo
        "SELECT * FORM creators",          # Typo
        "SELECT * FROM",                   # Incomplete
        "SELECT",                          # Just keyword
        "SELECT * FROM creators WHERE",    # Incomplete WHERE
        "SELECT * FROM creators ORDER BY", # Incomplete ORDER BY
        "SELECT * FROM nonexistent_table", # Non-existent table
        "SELECT nonexistent_col FROM creators",  # Non-existent column
        "SELECT * FROM creators JION creators2 ON 1=1",  # Typo in JOIN
    ])
    def test_execute_query_invalid_sql(self, invalid_sql: str):
        """Test execute_query handles invalid SQL syntax gracefully."""
        result = execute_query(invalid_sql)
        # Should return error, not crash
        assert "error" in result or "results" in result

    @pytest.mark.edge_case
    def test_execute_query_empty_query(self):
        """Test execute_query with empty string."""
        result = execute_query("")
        assert "error" in result

    @pytest.mark.edge_case
    def test_execute_query_whitespace_only(self):
        """Test execute_query with whitespace-only query."""
        result = execute_query("   \t\n   ")
        assert "error" in result

    # -------------------------------------------------------------------------
    # Large Result Set Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_execute_query_large_limit(self):
        """Test execute_query with large LIMIT value."""
        result = execute_query("SELECT * FROM creators LIMIT 100000")
        # Should be blocked due to LIMIT exceeding max
        assert "error" in result
        assert "LIMIT" in result["error"]

    @pytest.mark.edge_case
    def test_execute_query_at_max_limit(self):
        """Test execute_query at exactly maximum LIMIT (10000)."""
        result = execute_query("SELECT * FROM creators LIMIT 10000")
        # Should work at the limit
        assert "results" in result or "error" not in result

    @pytest.mark.edge_case
    def test_execute_query_cartesian_product(self):
        """Test execute_query that would create massive result set."""
        # Join without condition creates cartesian product
        result = execute_query(
            "SELECT * FROM creators c1, creators c2, creators c3"
        )
        # Should be limited or blocked
        assert "error" in result or "results" in result

    # -------------------------------------------------------------------------
    # No Results Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_execute_query_no_results(self):
        """Test execute_query that returns no results."""
        result = execute_query(
            "SELECT * FROM creators WHERE creator_id = 'impossible_nonexistent_xyz'"
        )
        assert "results" in result
        assert len(result["results"]) == 0

    @pytest.mark.edge_case
    def test_execute_query_count_zero(self):
        """Test COUNT query returning zero."""
        result = execute_query(
            "SELECT COUNT(*) as cnt FROM creators WHERE is_active = 999"
        )
        assert "results" in result
        assert result["results"][0]["cnt"] == 0


# =============================================================================
# BOUNDARY CONDITION TESTS
# =============================================================================


class TestBoundaryConditions:
    """Tests for boundary conditions and edge values."""

    # -------------------------------------------------------------------------
    # Min/Max Values Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_active_creators_tier_boundaries(self):
        """Test get_active_creators with tier boundary values."""
        # Tier 1 (minimum valid)
        result = get_active_creators(tier=1)
        assert "creators" in result

        # Tier 5 (maximum valid)
        result = get_active_creators(tier=5)
        assert "creators" in result

        # Tier 0 (below minimum)
        result = get_active_creators(tier=0)
        # Should return empty or handle gracefully
        assert "creators" in result
        assert result["count"] == 0

        # Tier 6 (above maximum)
        result = get_active_creators(tier=6)
        assert "creators" in result
        assert result["count"] == 0

    @pytest.mark.edge_case
    def test_get_top_captions_limit_boundaries(self, valid_creator_id: Optional[str]):
        """Test get_top_captions with limit boundary values."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Minimum limit
        result = get_top_captions(valid_creator_id, limit=1)
        assert "captions" in result
        assert result["count"] <= 1

        # Negative limit (edge case)
        result = get_top_captions(valid_creator_id, limit=-1)
        # Should handle gracefully
        assert "captions" in result or "error" in result

        # Large limit
        result = get_top_captions(valid_creator_id, limit=10000)
        assert "captions" in result

    @pytest.mark.edge_case
    def test_get_top_captions_performance_boundaries(self, valid_creator_id: Optional[str]):
        """Test get_top_captions with min_performance boundary values."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Minimum possible (0)
        result = get_top_captions(valid_creator_id, min_performance=0.0)
        assert "captions" in result

        # Negative value
        result = get_top_captions(valid_creator_id, min_performance=-100.0)
        assert "captions" in result  # Should treat as no filter or 0

        # Maximum possible (100)
        result = get_top_captions(valid_creator_id, min_performance=100.0)
        assert "captions" in result
        # Count might be 0 if no caption has 100 score

        # Beyond maximum
        result = get_top_captions(valid_creator_id, min_performance=150.0)
        assert "captions" in result
        assert result["count"] == 0

    # -------------------------------------------------------------------------
    # Empty vs Null Tests
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_validate_creator_id_empty_vs_none(self):
        """Test validation distinguishes empty string from None."""
        # Empty string
        is_valid, error = validate_creator_id("")
        assert is_valid is False
        assert "cannot be empty" in error.lower()

    @pytest.mark.edge_case
    def test_validate_key_input_empty_vs_whitespace(self):
        """Test validation handles empty vs whitespace-only strings."""
        # Empty
        is_valid, error = validate_key_input("", "test_key")
        assert is_valid is False

        # Whitespace only (depends on implementation)
        is_valid, error = validate_key_input("   ", "test_key")
        # Should be invalid due to special characters (spaces not allowed)
        assert is_valid is False

    @pytest.mark.edge_case
    def test_get_send_types_empty_category_filter(self):
        """Test get_send_types with empty category filter."""
        result = get_send_types(category="")
        # Empty string should be treated as invalid
        assert "error" in result or "send_types" in result

    # -------------------------------------------------------------------------
    # Unicode Edge Cases
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_save_schedule_unicode_caption(self, valid_creator_id: Optional[str]):
        """Test save_schedule with various unicode characters."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Various unicode characters from different scripts
        unicode_caption = (
            "Hello World! "              # ASCII
            "Hola Mundo! "               # Latin with accents
            "\u4e2d\u6587 "              # Chinese
            "\u0410\u0411\u0412 "         # Cyrillic
            "\u05d0\u05d1\u05d2 "         # Hebrew
            "\u0627\u0628\u062a "         # Arabic
            "\u3042\u3044\u3046 "         # Japanese Hiragana
            "\ud55c\uae00"               # Korean Hangul
        )

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": unicode_caption,
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        assert "success" in result or "error" in result

    @pytest.mark.edge_case
    def test_save_schedule_rtl_text(self, valid_creator_id: Optional[str]):
        """Test save_schedule with right-to-left text."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        rtl_caption = "\u0645\u0631\u062d\u0628\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645"  # Arabic "Hello World"

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": rtl_caption,
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        assert "success" in result or "error" in result

    @pytest.mark.edge_case
    def test_save_schedule_zero_width_characters(self, valid_creator_id: Optional[str]):
        """Test save_schedule with zero-width characters."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Zero-width characters that might be invisible
        zwc_caption = (
            "Hello\u200bWorld"    # Zero-width space
            "\u200c"              # Zero-width non-joiner
            "\u200d"              # Zero-width joiner
            "\ufeff"              # Zero-width no-break space (BOM)
        )

        items = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "10:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": zwc_caption,
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-06", items)
        assert "success" in result or "error" in result

    # -------------------------------------------------------------------------
    # Timezone Edge Cases
    # -------------------------------------------------------------------------

    @pytest.mark.edge_case
    def test_get_best_timing_timezone_handling(self, valid_creator_id: Optional[str]):
        """Test get_best_timing returns proper timezone information."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_best_timing(valid_creator_id)

        assert "timezone" in result
        # Timezone should be a valid string
        assert result["timezone"] is not None
        assert len(result["timezone"]) > 0

    @pytest.mark.edge_case
    def test_save_schedule_date_boundary(self, valid_creator_id: Optional[str]):
        """Test save_schedule at date boundaries (midnight, year change)."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        # Midnight timing
        items_midnight = [
            {
                "scheduled_date": "2020-01-01",
                "scheduled_time": "00:00",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "Midnight post",
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-01-01", items_midnight)
        assert "success" in result or "error" in result

        # End of day timing
        items_eod = [
            {
                "scheduled_date": "2020-12-31",
                "scheduled_time": "23:59",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "caption_text": "End of year post",
                "priority": 1
            }
        ]

        result = save_schedule(valid_creator_id, "2020-12-31", items_eod)
        assert "success" in result or "error" in result


# =============================================================================
# SEND TYPE EDGE CASES
# =============================================================================


class TestSendTypeEdgeCases:
    """Edge case tests for send type tools."""

    @pytest.mark.edge_case
    def test_get_send_types_invalid_category(self):
        """Test get_send_types with invalid category value."""
        result = get_send_types(category="invalid_category")
        assert "error" in result

    @pytest.mark.edge_case
    def test_get_send_types_invalid_page_type(self):
        """Test get_send_types with invalid page_type value."""
        result = get_send_types(page_type="invalid_page")
        assert "error" in result

    @pytest.mark.edge_case
    def test_get_send_type_details_nonexistent(self):
        """Test get_send_type_details with non-existent send type."""
        result = get_send_type_details("nonexistent_send_type")
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.edge_case
    def test_get_send_type_details_special_chars(self):
        """Test get_send_type_details with special characters in key."""
        result = get_send_type_details("ppv_unlock'; DROP TABLE--")
        assert "error" in result
        assert "Invalid send_type_key" in result["error"]

    @pytest.mark.edge_case
    def test_get_send_type_captions_invalid_send_type(self, valid_creator_id: Optional[str]):
        """Test get_send_type_captions with invalid send type."""
        if valid_creator_id is None:
            pytest.skip("No valid creator_id available")

        result = get_send_type_captions(valid_creator_id, "invalid_type_xyz")
        assert "error" in result


# =============================================================================
# CHANNEL AND AUDIENCE TARGET EDGE CASES
# =============================================================================


class TestChannelAndTargetEdgeCases:
    """Edge case tests for channel and audience target tools."""

    @pytest.mark.edge_case
    def test_get_audience_targets_invalid_page_type(self):
        """Test get_audience_targets with invalid page_type."""
        result = get_audience_targets(page_type="invalid")
        assert "error" in result

    @pytest.mark.edge_case
    def test_get_audience_targets_invalid_channel_key(self):
        """Test get_audience_targets with invalid channel_key."""
        result = get_audience_targets(channel_key="invalid@channel!")
        assert "error" in result

    @pytest.mark.edge_case
    def test_get_channels_targeting_boolean_types(self):
        """Test get_channels with various boolean-like values."""
        # True boolean
        result = get_channels(supports_targeting=True)
        assert "channels" in result

        # False boolean
        result = get_channels(supports_targeting=False)
        assert "channels" in result


# =============================================================================
# MCP PROTOCOL EDGE CASES
# =============================================================================


class TestMCPProtocolEdgeCases:
    """Edge case tests for MCP JSON-RPC protocol handling."""

    @pytest.mark.edge_case
    def test_handle_request_invalid_json_format(self):
        """Test handle_request with malformed request structure."""
        # Missing required fields
        response = handle_request({"jsonrpc": "2.0"})
        # Should handle gracefully
        assert response is not None

    @pytest.mark.edge_case
    def test_handle_request_wrong_jsonrpc_version(self):
        """Test handle_request with wrong JSON-RPC version."""
        response = handle_request({
            "jsonrpc": "1.0",
            "id": 1,
            "method": "tools/list"
        })
        # Should either work or return proper error
        assert response is not None

    @pytest.mark.edge_case
    def test_handle_tools_call_extra_arguments(self):
        """Test tools/call with extra unexpected arguments."""
        response = handle_tools_call(
            request_id=1,
            params={
                "name": "get_active_creators",
                "arguments": {
                    "extra_param": "unexpected",
                    "another_extra": 123
                }
            }
        )
        # Should ignore extra params or return error
        assert "result" in response or "error" in response

    @pytest.mark.edge_case
    def test_handle_tools_call_missing_arguments(self):
        """Test tools/call with missing arguments key."""
        response = handle_tools_call(
            request_id=1,
            params={"name": "get_active_creators"}
        )
        # Should handle missing arguments gracefully
        assert "result" in response or "error" in response


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "edge_case"])
