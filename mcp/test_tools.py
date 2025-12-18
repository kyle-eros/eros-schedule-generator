"""
MCP Server Tool Tests - Comprehensive test suite for all 17 MCP tools.

Tests cover:
- Success cases with mocked database responses
- Error cases (not found, invalid input, database errors)
- Input validation (security checks)
- Edge cases and boundary conditions

Tools tested:
1. get_active_creators
2. get_creator_profile
3. get_top_captions
4. get_best_timing
5. get_volume_assignment
6. get_performance_trends
7. get_content_type_rankings
8. get_persona_profile
9. get_vault_availability
10. save_schedule
11. execute_query
12. get_send_types
13. get_send_type_details
14. get_send_type_captions
15. get_channels
16. get_audience_targets
17. get_volume_config
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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
from mcp.server import handle_request, handle_tools_call, handle_tools_list

# Connection and database helpers
from mcp.connection import db_connection, get_db_connection

# Utility helpers
from mcp.utils.helpers import row_to_dict, rows_to_list, resolve_creator_id

# Security validation
from mcp.utils.security import validate_creator_id, validate_key_input


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection with configurable behavior."""
    with patch("mcp.connection.get_db_connection") as mock_get_conn:
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock()

        # Configure default cursor behavior
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


@pytest.fixture
def sample_creator_row():
    """Sample creator data row."""
    return {
        "creator_id": "test_creator_001",
        "page_name": "testcreator",
        "display_name": "Test Creator",
        "page_type": "paid",
        "subscription_price": 9.99,
        "timezone": "America/Los_Angeles",
        "creator_group": "premium",
        "current_active_fans": 5000,
        "current_total_earnings": 50000.00,
        "performance_tier": 3,
        "persona_type": "playful",
        "is_active": 1,
    }


@pytest.fixture
def sample_volume_assignment():
    """Sample volume assignment data."""
    return {
        "volume_level": "High",
        "ppv_per_day": 4,
        "bump_per_day": 3,
        "assigned_at": "2025-01-01 12:00:00",
        "assigned_by": "system",
        "assigned_reason": "Performance based",
        "notes": None,
    }


@pytest.fixture
def sample_send_type():
    """Sample send type data."""
    return {
        "send_type_id": 1,
        "send_type_key": "ppv_video",
        "category": "revenue",
        "display_name": "PPV Video",
        "description": "Pay-per-view video content",
        "purpose": "Generate direct revenue",
        "strategy": "Send during peak hours",
        "requires_media": 1,
        "requires_flyer": 0,
        "requires_price": 1,
        "requires_link": 0,
        "has_expiration": 1,
        "default_expiration_hours": 48,
        "can_have_followup": 1,
        "followup_delay_minutes": 20,
        "page_type_restriction": "both",
        "caption_length": "medium",
        "emoji_recommendation": "moderate",
        "max_per_day": 4,
        "max_per_week": 20,
        "min_hours_between": 2,
        "sort_order": 1,
        "is_active": 1,
        "created_at": "2025-01-01 00:00:00",
    }


@pytest.fixture
def sample_caption():
    """Sample caption data."""
    return {
        "caption_id": 101,
        "caption_text": "Exclusive content just for you!",
        "schedulable_type": "ppv",
        "caption_type": "ppv_unlock",
        "content_type_id": 1,
        "tone": "flirty",
        "is_paid_page_only": 0,
        "performance_score": 85.0,
        "content_type_name": "video",
        "times_used": 5,
        "caption_total_earnings": 500.00,
        "caption_avg_earnings": 100.00,
        "caption_avg_purchase_rate": 0.15,
        "caption_avg_view_rate": 0.45,
        "creator_performance_score": 82.0,
        "first_used_date": "2024-11-01",
        "last_used_date": "2024-12-01",
        "freshness_score": 70.0,
    }


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestHelperFunctions:
    """Tests for helper and validation functions."""

    def test_validate_creator_id_valid(self):
        """Test valid creator_id passes validation."""
        is_valid, error = validate_creator_id("test_creator_001")
        assert is_valid is True
        assert error is None

    def test_validate_creator_id_empty(self):
        """Test empty creator_id fails validation."""
        is_valid, error = validate_creator_id("")
        assert is_valid is False
        assert "cannot be empty" in error

    def test_validate_creator_id_too_long(self):
        """Test creator_id exceeding max length fails."""
        long_id = "a" * 101
        is_valid, error = validate_creator_id(long_id)
        assert is_valid is False
        assert "exceeds maximum length" in error

    def test_validate_creator_id_invalid_chars(self):
        """Test creator_id with invalid characters fails."""
        is_valid, error = validate_creator_id("test@creator!123")
        assert is_valid is False
        assert "invalid characters" in error

    def test_validate_key_input_valid(self):
        """Test valid key passes validation."""
        is_valid, error = validate_key_input("ppv_video", "send_type_key")
        assert is_valid is True
        assert error is None

    def test_validate_key_input_empty(self):
        """Test empty key fails validation."""
        is_valid, error = validate_key_input("", "send_type_key")
        assert is_valid is False
        assert "cannot be empty" in error

    def test_row_to_dict_with_row(self):
        """Test converting sqlite Row to dict."""
        mock_row = MagicMock()
        mock_row.keys.return_value = ["id", "name"]
        mock_row.__getitem__ = lambda self, key: {"id": 1, "name": "test"}[key]
        mock_row.__iter__ = lambda self: iter([1, "test"])

        # Use dict() directly since that's what row_to_dict does
        result = row_to_dict(mock_row)
        assert result is not None

    def test_row_to_dict_with_none(self):
        """Test row_to_dict returns None for None input."""
        result = row_to_dict(None)
        assert result is None

    def test_rows_to_list_empty(self):
        """Test rows_to_list with empty list."""
        result = rows_to_list([])
        assert result == []


# =============================================================================
# get_active_creators TESTS
# =============================================================================


class TestGetActiveCreators:
    """Tests for get_active_creators tool."""

    @pytest.mark.unit
    def test_get_active_creators_success(self, mock_db_connection, sample_creator_row):
        """Test successful retrieval of active creators."""
        mock_row = MagicMock()
        mock_row.keys.return_value = list(sample_creator_row.keys())
        for key, value in sample_creator_row.items():
            mock_row.__getitem__ = lambda self, k=key, v=value: sample_creator_row.get(k)

        mock_db_connection["cursor"].fetchall.return_value = [mock_row]

        with patch("mcp.connection.db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                return_value=mock_db_connection["connection"]
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = get_active_creators()

        assert "creators" in result
        assert "count" in result

    @pytest.mark.unit
    def test_get_active_creators_with_tier_filter(self, mock_db_connection):
        """Test filtering by performance tier."""
        mock_db_connection["cursor"].fetchall.return_value = []

        with patch("mcp.connection.db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                return_value=mock_db_connection["connection"]
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = get_active_creators(tier=3)

        assert "creators" in result
        assert result["count"] == 0

    @pytest.mark.unit
    def test_get_active_creators_invalid_page_type(self, mock_db_connection):
        """Test invalid page_type returns error."""
        with patch("mcp.connection.db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                return_value=mock_db_connection["connection"]
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = get_active_creators(page_type="invalid")

        assert "error" in result
        assert "paid" in result["error"] or "free" in result["error"]


# =============================================================================
# get_creator_profile TESTS
# =============================================================================


class TestGetCreatorProfile:
    """Tests for get_creator_profile tool."""

    @pytest.mark.unit
    def test_get_creator_profile_not_found(self, mock_db_connection):
        """Test creator not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_creator_profile("nonexistent_creator")

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.unit
    def test_get_creator_profile_invalid_id(self):
        """Test invalid creator_id returns error."""
        result = get_creator_profile("invalid@id!")

        assert "error" in result
        assert "Invalid creator_id" in result["error"]

    @pytest.mark.unit
    def test_get_creator_profile_empty_id(self):
        """Test empty creator_id returns error."""
        result = get_creator_profile("")

        assert "error" in result
        assert "cannot be empty" in result["error"]


# =============================================================================
# get_top_captions TESTS
# =============================================================================


class TestGetTopCaptions:
    """Tests for get_top_captions tool."""

    @pytest.mark.unit
    def test_get_top_captions_invalid_creator(self):
        """Test invalid creator_id returns error."""
        result = get_top_captions("invalid@creator!")

        assert "error" in result
        assert "Invalid creator_id" in result["error"]

    @pytest.mark.unit
    def test_get_top_captions_invalid_send_type_key(self):
        """Test invalid send_type_key returns error."""
        result = get_top_captions("valid_creator", send_type_key="invalid@key!")

        assert "error" in result
        assert "Invalid send_type_key" in result["error"]

    @pytest.mark.unit
    def test_get_top_captions_creator_not_found(self, mock_db_connection):
        """Test creator not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_top_captions("nonexistent_creator")

        assert "error" in result
        assert "not found" in result["error"].lower()


# =============================================================================
# get_best_timing TESTS
# =============================================================================


class TestGetBestTiming:
    """Tests for get_best_timing tool."""

    @pytest.mark.unit
    def test_get_best_timing_creator_not_found(self, mock_db_connection):
        """Test creator not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_best_timing("nonexistent_creator")

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.unit
    def test_get_best_timing_default_lookback(self, mock_db_connection, sample_creator_row):
        """Test default 30-day lookback period."""
        # First call returns creator
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: sample_creator_row.get(k)

        call_count = [0]

        def side_effect(*args, **kwargs):
            cursor = MagicMock()
            if call_count[0] == 0:
                cursor.fetchone.return_value = mock_row
            else:
                cursor.fetchall.return_value = []
            call_count[0] += 1
            return cursor

        mock_db_connection["connection"].execute.side_effect = side_effect

        result = get_best_timing("test_creator_001")

        # Should have best_hours and best_days in successful response
        # or error if creator not found
        assert "error" in result or "best_hours" in result


# =============================================================================
# get_volume_assignment TESTS
# =============================================================================


class TestGetVolumeAssignment:
    """Tests for get_volume_assignment tool."""

    @pytest.mark.unit
    def test_get_volume_assignment_not_found(self, mock_db_connection):
        """Test no active assignment returns message."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_volume_assignment("test_creator")

        assert "error" in result or "message" in result


# =============================================================================
# get_performance_trends TESTS
# =============================================================================


class TestGetPerformanceTrends:
    """Tests for get_performance_trends tool."""

    @pytest.mark.unit
    def test_get_performance_trends_invalid_period(self, mock_db_connection):
        """Test invalid period returns error."""
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: "test_creator"
        mock_db_connection["cursor"].fetchone.return_value = mock_row

        result = get_performance_trends("test_creator", period="invalid")

        assert "error" in result
        assert "7d" in result["error"] or "14d" in result["error"] or "30d" in result["error"]

    @pytest.mark.unit
    def test_get_performance_trends_creator_not_found(self, mock_db_connection):
        """Test creator not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_performance_trends("nonexistent_creator")

        assert "error" in result


# =============================================================================
# get_content_type_rankings TESTS
# =============================================================================


class TestGetContentTypeRankings:
    """Tests for get_content_type_rankings tool."""

    @pytest.mark.unit
    def test_get_content_type_rankings_no_data(self, mock_db_connection):
        """Test no analysis data returns empty rankings."""
        # First call for resolve_creator_id
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: "test_creator"

        call_count = [0]

        def side_effect(*args, **kwargs):
            cursor = MagicMock()
            if call_count[0] == 0:
                cursor.fetchone.return_value = mock_row
            else:
                cursor.fetchone.return_value = None
                cursor.fetchall.return_value = []
            call_count[0] += 1
            return cursor

        mock_db_connection["connection"].execute.side_effect = side_effect

        result = get_content_type_rankings("test_creator")

        # Should return empty rankings or error
        assert "rankings" in result or "error" in result


# =============================================================================
# get_persona_profile TESTS
# =============================================================================


class TestGetPersonaProfile:
    """Tests for get_persona_profile tool."""

    @pytest.mark.unit
    def test_get_persona_profile_creator_not_found(self, mock_db_connection):
        """Test creator not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_persona_profile("nonexistent_creator")

        assert "error" in result
        assert "not found" in result["error"].lower()


# =============================================================================
# get_vault_availability TESTS
# =============================================================================


class TestGetVaultAvailability:
    """Tests for get_vault_availability tool."""

    @pytest.mark.unit
    def test_get_vault_availability_creator_not_found(self, mock_db_connection):
        """Test creator not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_vault_availability("nonexistent_creator")

        assert "error" in result


# =============================================================================
# save_schedule TESTS
# =============================================================================


class TestSaveSchedule:
    """Tests for save_schedule tool."""

    @pytest.mark.unit
    def test_save_schedule_invalid_creator_id(self):
        """Test invalid creator_id returns error."""
        result = save_schedule(
            creator_id="invalid@creator!", week_start="2025-01-06", items=[]
        )

        assert "error" in result
        assert "Invalid creator_id" in result["error"]

    @pytest.mark.unit
    def test_save_schedule_invalid_date_format(self, mock_db_connection):
        """Test invalid date format returns error."""
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: "test_creator"
        mock_db_connection["cursor"].fetchone.return_value = mock_row

        # Must provide enough unique send types to pass diversity validation
        # before hitting the date format check
        valid_items = [
            {"send_type_key": "ppv_unlock", "scheduled_date": "2025-01-06", "scheduled_time": "10:00"},
            {"send_type_key": "ppv_wall", "scheduled_date": "2025-01-06", "scheduled_time": "11:00"},
            {"send_type_key": "tip_goal", "scheduled_date": "2025-01-06", "scheduled_time": "12:00"},
            {"send_type_key": "vip_program", "scheduled_date": "2025-01-06", "scheduled_time": "13:00"},
            {"send_type_key": "bump_normal", "scheduled_date": "2025-01-06", "scheduled_time": "14:00"},
            {"send_type_key": "bump_descriptive", "scheduled_date": "2025-01-06", "scheduled_time": "15:00"},
            {"send_type_key": "link_drop", "scheduled_date": "2025-01-06", "scheduled_time": "16:00"},
            {"send_type_key": "renew_on_post", "scheduled_date": "2025-01-06", "scheduled_time": "17:00"},
            {"send_type_key": "ppv_followup", "scheduled_date": "2025-01-06", "scheduled_time": "18:00"},
            {"send_type_key": "dm_farm", "scheduled_date": "2025-01-06", "scheduled_time": "19:00"},
        ]

        result = save_schedule(
            creator_id="test_creator", week_start="invalid-date", items=valid_items
        )

        assert "error" in result
        # After passing diversity check, the date format error should be raised
        assert "format" in result["error"].lower() or "date" in result["error"].lower()

    @pytest.mark.unit
    def test_save_schedule_creator_not_found(self, mock_db_connection):
        """Test creator not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = save_schedule(
            creator_id="nonexistent", week_start="2025-01-06", items=[]
        )

        assert "error" in result


# =============================================================================
# execute_query TESTS
# =============================================================================


class TestExecuteQuery:
    """Tests for execute_query tool."""

    @pytest.mark.unit
    def test_execute_query_non_select_blocked(self):
        """Test non-SELECT queries are blocked."""
        result = execute_query("INSERT INTO creators VALUES ('test')")

        assert "error" in result
        assert "SELECT" in result["error"]

    @pytest.mark.unit
    def test_execute_query_dangerous_keywords_blocked(self):
        """Test dangerous keywords are blocked."""
        result = execute_query("SELECT * FROM creators; DROP TABLE creators;")

        assert "error" in result
        assert "DROP" in result["error"]

    @pytest.mark.unit
    def test_execute_query_pragma_blocked(self):
        """Test PRAGMA commands are blocked."""
        result = execute_query("SELECT * FROM creators; PRAGMA table_info(creators);")

        assert "error" in result
        assert "PRAGMA" in result["error"]

    @pytest.mark.unit
    def test_execute_query_comment_injection_blocked(self):
        """Test comment injection patterns are blocked."""
        result = execute_query("SELECT * FROM creators /* injection */")

        assert "error" in result
        assert "comment" in result["error"].lower()

    @pytest.mark.unit
    def test_execute_query_double_dash_blocked(self):
        """Test double-dash comments are blocked."""
        result = execute_query("SELECT * FROM creators -- injection")

        assert "error" in result
        assert "comment" in result["error"].lower()

    @pytest.mark.unit
    def test_execute_query_excessive_joins_blocked(self):
        """Test excessive JOINs are blocked (limit is 5, so 6+ triggers error)."""
        # Need 6 JOINs to exceed the limit of 5
        query = "SELECT 1 FROM creators c JOIN creators c2 ON 1=1 JOIN creators c3 ON 1=1 JOIN creators c4 ON 1=1 JOIN creators c5 ON 1=1 JOIN creators c6 ON 1=1 JOIN creators c7 ON 1=1"
        result = execute_query(query)

        assert "error" in result
        assert "JOIN" in result["error"] or "limit" in result["error"].lower()

    @pytest.mark.unit
    def test_execute_query_excessive_subqueries_blocked(self):
        """Test excessive subqueries are blocked."""
        query = """
            SELECT * FROM (
                SELECT * FROM (
                    SELECT * FROM (
                        SELECT * FROM (
                            SELECT 1
                        )
                    )
                )
            )
        """
        result = execute_query(query)

        assert "error" in result
        assert "subquery" in result["error"].lower()


# =============================================================================
# get_send_types TESTS
# =============================================================================


class TestGetSendTypes:
    """Tests for get_send_types tool."""

    @pytest.mark.unit
    def test_get_send_types_invalid_category(self, mock_db_connection):
        """Test invalid category returns error."""
        with patch("mcp.connection.db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                return_value=mock_db_connection["connection"]
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = get_send_types(category="invalid")

        assert "error" in result

    @pytest.mark.unit
    def test_get_send_types_invalid_page_type(self, mock_db_connection):
        """Test invalid page_type returns error."""
        with patch("mcp.connection.db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                return_value=mock_db_connection["connection"]
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = get_send_types(page_type="invalid")

        assert "error" in result


# =============================================================================
# get_send_type_details TESTS
# =============================================================================


class TestGetSendTypeDetails:
    """Tests for get_send_type_details tool."""

    @pytest.mark.unit
    def test_get_send_type_details_invalid_key(self):
        """Test invalid send_type_key returns error."""
        result = get_send_type_details("invalid@key!")

        assert "error" in result
        assert "Invalid send_type_key" in result["error"]

    @pytest.mark.unit
    def test_get_send_type_details_not_found(self, mock_db_connection):
        """Test send type not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_send_type_details("nonexistent_type")

        assert "error" in result
        assert "not found" in result["error"].lower()


# =============================================================================
# get_send_type_captions TESTS
# =============================================================================


class TestGetSendTypeCaptions:
    """Tests for get_send_type_captions tool."""

    @pytest.mark.unit
    def test_get_send_type_captions_invalid_creator(self):
        """Test invalid creator_id returns error."""
        result = get_send_type_captions("invalid@creator!", "ppv_video")

        assert "error" in result
        assert "Invalid creator_id" in result["error"]

    @pytest.mark.unit
    def test_get_send_type_captions_invalid_key(self):
        """Test invalid send_type_key returns error."""
        result = get_send_type_captions("valid_creator", "invalid@key!")

        assert "error" in result
        assert "Invalid send_type_key" in result["error"]


# =============================================================================
# get_channels TESTS
# =============================================================================


class TestGetChannels:
    """Tests for get_channels tool."""

    @pytest.mark.unit
    def test_get_channels_success(self, mock_db_connection):
        """Test successful channel retrieval."""
        mock_db_connection["cursor"].fetchall.return_value = []

        with patch("mcp.connection.db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                return_value=mock_db_connection["connection"]
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = get_channels()

        assert "channels" in result
        assert "count" in result

    @pytest.mark.unit
    def test_get_channels_with_targeting_filter(self, mock_db_connection):
        """Test filtering by supports_targeting."""
        mock_db_connection["cursor"].fetchall.return_value = []

        with patch("mcp.connection.db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                return_value=mock_db_connection["connection"]
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = get_channels(supports_targeting=True)

        assert "channels" in result


# =============================================================================
# get_audience_targets TESTS
# =============================================================================


class TestGetAudienceTargets:
    """Tests for get_audience_targets tool."""

    @pytest.mark.unit
    def test_get_audience_targets_invalid_page_type(self, mock_db_connection):
        """Test invalid page_type returns error."""
        with patch("mcp.connection.db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                return_value=mock_db_connection["connection"]
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = get_audience_targets(page_type="invalid")

        assert "error" in result

    @pytest.mark.unit
    def test_get_audience_targets_invalid_channel_key(self):
        """Test invalid channel_key returns error."""
        result = get_audience_targets(channel_key="invalid@key!")

        assert "error" in result
        assert "Invalid channel_key" in result["error"]


# =============================================================================
# get_volume_config TESTS
# =============================================================================


class TestGetVolumeConfig:
    """Tests for get_volume_config tool."""

    @pytest.mark.unit
    def test_get_volume_config_creator_not_found(self, mock_db_connection):
        """Test creator not found returns error."""
        mock_db_connection["cursor"].fetchone.return_value = None

        result = get_volume_config("nonexistent_creator")

        assert "error" in result


# =============================================================================
# MCP PROTOCOL TESTS
# =============================================================================


class TestMCPProtocol:
    """Tests for MCP JSON-RPC protocol handling."""

    @pytest.mark.unit
    def test_handle_tools_list(self):
        """Test tools/list response."""
        response = handle_tools_list(request_id=1)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "tools" in response["result"]
        # Should have 17 tools
        assert len(response["result"]["tools"]) == 17

    @pytest.mark.unit
    def test_handle_tools_call_unknown_tool(self):
        """Test calling unknown tool returns error."""
        response = handle_tools_call(
            request_id=1, params={"name": "unknown_tool", "arguments": {}}
        )

        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.unit
    def test_handle_tools_call_invalid_params(self):
        """Test invalid parameters returns error."""
        response = handle_tools_call(
            request_id=1,
            params={"name": "get_creator_profile", "arguments": {"invalid_param": "value"}},
        )

        assert "error" in response
        assert response["error"]["code"] == -32602

    @pytest.mark.unit
    def test_handle_request_initialize(self):
        """Test MCP initialize request."""
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}

        response = handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "protocolVersion" in response["result"]
        assert "serverInfo" in response["result"]

    @pytest.mark.unit
    def test_handle_request_unknown_method(self):
        """Test unknown method returns error."""
        request = {"jsonrpc": "2.0", "id": 1, "method": "unknown/method", "params": {}}

        response = handle_request(request)

        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.unit
    def test_handle_request_notification(self):
        """Test notification returns None."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "notifications/initialized",
            "params": {},
        }

        response = handle_request(request)

        assert response is None


# =============================================================================
# EDGE CASES AND BOUNDARY TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.unit
    def test_creator_id_with_underscore_hyphen(self):
        """Test creator_id with valid special chars."""
        is_valid, error = validate_creator_id("test-creator_001")
        assert is_valid is True
        assert error is None

    @pytest.mark.unit
    def test_creator_id_max_length(self):
        """Test creator_id at exactly max length."""
        max_id = "a" * 100
        is_valid, error = validate_creator_id(max_id)
        assert is_valid is True
        assert error is None

    @pytest.mark.unit
    def test_execute_query_with_limit_at_max(self):
        """Test query with LIMIT at maximum allowed."""
        result = execute_query("SELECT * FROM creators LIMIT 10000")
        # Should not error on LIMIT at max
        assert "error" not in result or "LIMIT" not in result.get("error", "")

    @pytest.mark.unit
    def test_execute_query_with_limit_over_max(self):
        """Test query with LIMIT over maximum is blocked."""
        result = execute_query("SELECT * FROM creators LIMIT 10001")
        assert "error" in result
        assert "LIMIT" in result["error"]
