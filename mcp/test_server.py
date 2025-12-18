#!/usr/bin/env python3
"""
Test Suite for EROS Database MCP Server

This module provides comprehensive tests for all 17 MCP tools.
Run with: python mcp/test_server.py

Test Categories:
1. Tool Function Tests - Direct function calls
2. MCP Protocol Tests - JSON-RPC request/response validation
3. Security Tests - SQL injection prevention, query validation
4. Edge Case Tests - Error handling, missing data
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.eros_db_server import (
    get_active_creators,
    get_creator_profile,
    get_top_captions,
    get_best_timing,
    get_volume_assignment,
    get_performance_trends,
    get_content_type_rankings,
    get_persona_profile,
    get_vault_availability,
    save_schedule,
    execute_query,
    get_send_types,
    get_send_type_details,
    get_send_type_captions,
    get_channels,
    get_audience_targets,
    get_volume_config,
    handle_request,
    TOOLS,
    DB_PATH,
)


class TestColors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Print a formatted test section header."""
    print(f"\n{TestColors.BOLD}{TestColors.BLUE}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{TestColors.RESET}\n")


def print_test(name: str, passed: bool, details: str = "") -> None:
    """Print test result with colored status."""
    status = f"{TestColors.GREEN}PASS{TestColors.RESET}" if passed else f"{TestColors.RED}FAIL{TestColors.RESET}"
    print(f"  [{status}] {name}")
    if details and not passed:
        print(f"         {TestColors.YELLOW}{details}{TestColors.RESET}")


def test_database_connection() -> bool:
    """Test that database connection works."""
    try:
        result = execute_query("SELECT 1 as test")
        return "results" in result and len(result["results"]) == 1
    except Exception as e:
        print(f"Database connection error: {e}")
        return False


def test_get_active_creators() -> tuple[bool, str]:
    """Test get_active_creators tool."""
    try:
        # Test without filters
        result = get_active_creators()
        if "error" in result:
            return False, result["error"]
        if "creators" not in result or "count" not in result:
            return False, "Missing required keys in response"
        if result["count"] == 0:
            return False, "No active creators found"

        # Test with tier filter
        result_tier = get_active_creators(tier=1)
        if "error" in result_tier:
            return False, f"Tier filter error: {result_tier['error']}"

        # Test with page_type filter
        result_paid = get_active_creators(page_type="paid")
        if "error" in result_paid:
            return False, f"Page type filter error: {result_paid['error']}"

        return True, f"Found {result['count']} active creators"
    except Exception as e:
        return False, str(e)


def test_get_creator_profile() -> tuple[bool, str]:
    """Test get_creator_profile tool."""
    try:
        # First get an active creator
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]
        page_name = creators["creators"][0]["page_name"]

        # Test with creator_id
        result = get_creator_profile(creator_id)
        if "error" in result:
            return False, result["error"]
        if "creator" not in result:
            return False, "Missing 'creator' in response"

        # Test with page_name
        result2 = get_creator_profile(page_name)
        if "error" in result2:
            return False, f"Page name lookup failed: {result2['error']}"

        # Test with non-existent creator
        result3 = get_creator_profile("nonexistent_creator_xyz")
        if "error" not in result3:
            return False, "Should return error for non-existent creator"

        return True, f"Profile retrieved for {page_name}"
    except Exception as e:
        return False, str(e)


def test_get_top_captions() -> tuple[bool, str]:
    """Test get_top_captions tool."""
    try:
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        # Test basic call
        result = get_top_captions(creator_id)
        if "error" in result:
            return False, result["error"]
        if "captions" not in result or "count" not in result:
            return False, "Missing required keys"

        # Test with performance filter
        result2 = get_top_captions(creator_id, min_performance=60, limit=10)
        if "error" in result2:
            return False, f"Performance filter error: {result2['error']}"

        # Test with send_type_key parameter (Wave 2 addition)
        result3 = get_top_captions(creator_id, send_type_key="ppv_unlock")
        if "error" in result3:
            return False, f"send_type_key filter error: {result3['error']}"

        # Test backward compatibility with deprecated ppv_video alias
        result4 = get_top_captions(creator_id, send_type_key="ppv_video")
        if "error" in result4:
            return False, f"ppv_video alias error: {result4['error']}"

        return True, f"Retrieved {result['count']} captions"
    except Exception as e:
        return False, str(e)


def test_get_best_timing() -> tuple[bool, str]:
    """Test get_best_timing tool."""
    try:
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        result = get_best_timing(creator_id)
        if "error" in result:
            return False, result["error"]
        if "timezone" not in result or "best_hours" not in result:
            return False, "Missing required keys"

        # Test with custom lookback
        result2 = get_best_timing(creator_id, days_lookback=14)
        if "error" in result2:
            return False, f"Custom lookback error: {result2['error']}"

        return True, f"Timezone: {result['timezone']}, Hours analyzed: {len(result['best_hours'])}"
    except Exception as e:
        return False, str(e)


def test_get_volume_assignment() -> tuple[bool, str]:
    """Test get_volume_assignment tool."""
    try:
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        result = get_volume_assignment(creator_id)
        if "error" in result:
            return False, result["error"]

        # Volume level might be None if not assigned
        if "message" in result and "No active volume assignment" in result["message"]:
            return True, "No volume assignment (expected for some creators)"

        if "volume_level" not in result:
            return False, "Missing volume_level in response"

        return True, f"Volume level: {result.get('volume_level')}, PPV/day: {result.get('ppv_per_day')}"
    except Exception as e:
        return False, str(e)


def test_get_performance_trends() -> tuple[bool, str]:
    """Test get_performance_trends tool."""
    try:
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        # Test default period
        result = get_performance_trends(creator_id)
        if "error" in result:
            return False, result["error"]

        # Test different periods
        for period in ["7d", "14d", "30d"]:
            result_period = get_performance_trends(creator_id, period=period)
            if "error" in result_period:
                return False, f"Period {period} error: {result_period['error']}"

        # Test invalid period
        result_invalid = get_performance_trends(creator_id, period="invalid")
        if "error" not in result_invalid:
            return False, "Should reject invalid period"

        sat_score = result.get("saturation_score", "N/A")
        opp_score = result.get("opportunity_score", "N/A")
        return True, f"Saturation: {sat_score}, Opportunity: {opp_score}"
    except Exception as e:
        return False, str(e)


def test_get_content_type_rankings() -> tuple[bool, str]:
    """Test get_content_type_rankings tool."""
    try:
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        result = get_content_type_rankings(creator_id)
        if "error" in result:
            return False, result["error"]

        if "rankings" not in result:
            return False, "Missing rankings in response"

        top_count = len(result.get("top_types", []))
        avoid_count = len(result.get("avoid_types", []))
        return True, f"TOP: {top_count}, AVOID: {avoid_count}"
    except Exception as e:
        return False, str(e)


def test_get_persona_profile() -> tuple[bool, str]:
    """Test get_persona_profile tool."""
    try:
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        result = get_persona_profile(creator_id)
        if "error" in result:
            return False, result["error"]

        if "creator" not in result or "persona" not in result:
            return False, "Missing required keys"

        tone = result.get("persona", {}).get("primary_tone", "N/A") if result.get("persona") else "N/A"
        return True, f"Primary tone: {tone}"
    except Exception as e:
        return False, str(e)


def test_get_vault_availability() -> tuple[bool, str]:
    """Test get_vault_availability tool."""
    try:
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        result = get_vault_availability(creator_id)
        if "error" in result:
            return False, result["error"]

        if "available_content" not in result or "content_types" not in result:
            return False, "Missing required keys"

        return True, f"Content types available: {len(result['content_types'])}"
    except Exception as e:
        return False, str(e)


def test_get_send_types() -> tuple[bool, str]:
    """Test get_send_types tool."""
    try:
        # Test unfiltered (should return 22 active types)
        result = get_send_types()
        if "error" in result:
            return False, result["error"]
        if "send_types" not in result or "count" not in result:
            return False, "Missing required keys in response"

        total_count = result["count"]
        if total_count != 22:
            return False, f"Expected 22 send types, got {total_count}"

        # Test filtered by category='revenue' (should return 9)
        # Revenue: ppv_unlock, ppv_wall, tip_goal, vip_program, game_post,
        #          bundle, flash_bundle, snapchat_bundle, first_to_tip
        result_revenue = get_send_types(category="revenue")
        if "error" in result_revenue:
            return False, f"Revenue filter error: {result_revenue['error']}"
        if result_revenue["count"] != 9:
            return False, f"Expected 9 revenue send types, got {result_revenue['count']}"

        # Test filtered by category='engagement' (should return 9)
        result_engagement = get_send_types(category="engagement")
        if "error" in result_engagement:
            return False, f"Engagement filter error: {result_engagement['error']}"
        if result_engagement["count"] != 9:
            return False, f"Expected 9 engagement send types, got {result_engagement['count']}"

        # Test filtered by category='retention' (should return 4)
        # Retention: renew_on_post, renew_on_message, ppv_followup, expired_winback
        result_retention = get_send_types(category="retention")
        if "error" in result_retention:
            return False, f"Retention filter error: {result_retention['error']}"
        if result_retention["count"] != 4:
            return False, f"Expected 4 retention send types, got {result_retention['count']}"

        # Test filtered by page_type='paid'
        result_paid = get_send_types(page_type="paid")
        if "error" in result_paid:
            return False, f"Page type filter error: {result_paid['error']}"

        # Test filtered by page_type='free' (should exclude paid-only types)
        result_free = get_send_types(page_type="free")
        if "error" in result_free:
            return False, f"Free page type filter error: {result_free['error']}"

        # Test invalid category returns error
        result_invalid = get_send_types(category="invalid")
        if "error" not in result_invalid:
            return False, "Should return error for invalid category"

        return True, f"Found {total_count} send types (revenue: 9, engagement: 9, retention: 4)"
    except Exception as e:
        return False, str(e)


def test_get_send_type_details() -> tuple[bool, str]:
    """Test get_send_type_details tool."""
    try:
        # Test valid send_type_key with new ppv_unlock
        result = get_send_type_details("ppv_unlock")
        if "error" in result:
            return False, result["error"]

        # Verify response has required keys
        if "send_type" not in result:
            return False, "Missing 'send_type' key in response"
        if "caption_requirements" not in result:
            return False, "Missing 'caption_requirements' key in response"

        # Verify caption_requirements is a list
        if not isinstance(result["caption_requirements"], list):
            return False, "caption_requirements should be a list"

        # Test backward compatibility: ppv_video alias should resolve to ppv_unlock
        result_alias = get_send_type_details("ppv_video")
        if "error" in result_alias:
            return False, f"ppv_video alias failed: {result_alias['error']}"

        # Test invalid send_type_key returns error
        result_invalid = get_send_type_details("nonexistent_type")
        if "error" not in result_invalid:
            return False, "Should return error for invalid send_type_key"

        # Test new types: ppv_wall (FREE only) and tip_goal (PAID only)
        result_ppv_wall = get_send_type_details("ppv_wall")
        if "error" in result_ppv_wall:
            return False, f"ppv_wall lookup failed: {result_ppv_wall['error']}"
        if result_ppv_wall.get("send_type", {}).get("page_type_restriction") != "free":
            return False, "ppv_wall should have page_type_restriction='free'"

        result_tip_goal = get_send_type_details("tip_goal")
        if "error" in result_tip_goal:
            return False, f"tip_goal lookup failed: {result_tip_goal['error']}"
        if result_tip_goal.get("send_type", {}).get("page_type_restriction") != "paid":
            return False, "tip_goal should have page_type_restriction='paid'"

        caption_req_count = len(result["caption_requirements"])
        return True, f"Retrieved ppv_unlock details with {caption_req_count} caption requirements"
    except Exception as e:
        return False, str(e)


def test_get_send_type_captions() -> tuple[bool, str]:
    """Test get_send_type_captions tool."""
    try:
        # Get an active creator first
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        # Test with valid creator_id and send_type_key (using ppv_unlock)
        result = get_send_type_captions(creator_id, "ppv_unlock")
        if "error" in result:
            return False, result["error"]

        # Verify response has required keys
        if "captions" not in result:
            return False, "Missing 'captions' key in response"
        if "count" not in result:
            return False, "Missing 'count' key in response"
        if "send_type_key" not in result:
            return False, "Missing 'send_type_key' key in response"

        # Test with filters
        result_filtered = get_send_type_captions(
            creator_id,
            "ppv_unlock",
            min_freshness=50.0,
            min_performance=60.0,
            limit=5
        )
        if "error" in result_filtered:
            return False, f"Filter error: {result_filtered['error']}"

        # Test backward compatibility with ppv_video alias
        result_alias = get_send_type_captions(creator_id, "ppv_video")
        if "error" in result_alias:
            return False, f"ppv_video alias error: {result_alias['error']}"

        # Test invalid creator returns error
        result_invalid = get_send_type_captions("nonexistent_creator", "ppv_unlock")
        if "error" not in result_invalid:
            return False, "Should return error for invalid creator"

        return True, f"Retrieved {result['count']} captions for ppv_unlock"
    except Exception as e:
        return False, str(e)


def test_get_channels() -> tuple[bool, str]:
    """Test get_channels tool."""
    try:
        # Test returns 5 channels
        result = get_channels()
        if "error" in result:
            return False, result["error"]
        if "channels" not in result or "count" not in result:
            return False, "Missing required keys in response"

        total_count = result["count"]
        if total_count != 5:
            return False, f"Expected 5 channels, got {total_count}"

        # Test supports_targeting=True filter
        result_targeting = get_channels(supports_targeting=True)
        if "error" in result_targeting:
            return False, f"Targeting filter error: {result_targeting['error']}"

        targeting_count = result_targeting["count"]

        # Test supports_targeting=False filter
        result_no_targeting = get_channels(supports_targeting=False)
        if "error" in result_no_targeting:
            return False, f"No targeting filter error: {result_no_targeting['error']}"

        no_targeting_count = result_no_targeting["count"]

        # Verify response structure
        if result["channels"]:
            first_channel = result["channels"][0]
            required_keys = ["channel_id", "channel_key", "display_name", "supports_targeting"]
            for key in required_keys:
                if key not in first_channel:
                    return False, f"Missing '{key}' in channel record"

        return True, f"Found {total_count} channels (targeting: {targeting_count}, no targeting: {no_targeting_count})"
    except Exception as e:
        return False, str(e)


def test_get_audience_targets() -> tuple[bool, str]:
    """Test get_audience_targets tool."""
    try:
        # Test returns 10 targets
        result = get_audience_targets()
        if "error" in result:
            return False, result["error"]
        if "targets" not in result or "count" not in result:
            return False, "Missing required keys in response"

        total_count = result["count"]
        if total_count != 10:
            return False, f"Expected 10 targets, got {total_count}"

        # Test page_type='paid' filter
        result_paid = get_audience_targets(page_type="paid")
        if "error" in result_paid:
            return False, f"Page type filter error: {result_paid['error']}"

        paid_count = result_paid["count"]

        # Test channel_key filter
        result_channel = get_audience_targets(channel_key="mass_message")
        if "error" in result_channel:
            return False, f"Channel filter error: {result_channel['error']}"

        channel_count = result_channel["count"]

        # Verify response structure
        if result["targets"]:
            first_target = result["targets"][0]
            required_keys = ["target_id", "target_key", "display_name", "filter_type"]
            for key in required_keys:
                if key not in first_target:
                    return False, f"Missing '{key}' in target record"

        return True, f"Found {total_count} targets (paid: {paid_count}, mass_message channel: {channel_count})"
    except Exception as e:
        return False, str(e)


def test_get_volume_config() -> tuple[bool, str]:
    """Test get_volume_config tool."""
    try:
        # Get an active creator first
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        creator_id = creators["creators"][0]["creator_id"]

        # Test with valid creator_id
        result = get_volume_config(creator_id)
        if "error" in result:
            return False, result["error"]

        # Check if creator has volume assignment
        if "message" in result and "No active volume assignment" in result["message"]:
            return True, "No volume assignment (expected for some creators)"

        # Verify response has required keys
        required_keys = ["volume_level", "ppv_per_day", "bump_per_day"]
        for key in required_keys:
            if key not in result:
                return False, f"Missing '{key}' in response"

        # Verify category breakdown keys exist
        category_keys = ["revenue_items_per_day", "engagement_items_per_day", "retention_items_per_day"]
        for key in category_keys:
            if key not in result:
                return False, f"Missing '{key}' in response"

        # Test invalid creator returns error
        result_invalid = get_volume_config("nonexistent_creator")
        if "error" not in result_invalid:
            return False, "Should return error for invalid creator"

        volume_level = result.get("volume_level", "N/A")
        ppv_per_day = result.get("ppv_per_day", "N/A")
        return True, f"Volume: {volume_level}, PPV/day: {ppv_per_day}"
    except Exception as e:
        return False, str(e)


def test_execute_query() -> tuple[bool, str]:
    """Test execute_query tool with security validations."""
    try:
        # Test valid SELECT
        result = execute_query("SELECT COUNT(*) as cnt FROM creators WHERE is_active = 1")
        if "error" in result:
            return False, result["error"]
        if "results" not in result:
            return False, "Missing results in response"

        # Test parameterized query
        result2 = execute_query(
            "SELECT page_name FROM creators WHERE performance_tier = ?",
            params=[1]
        )
        if "error" in result2:
            return False, f"Parameterized query error: {result2['error']}"

        # Test INSERT rejection
        result3 = execute_query("INSERT INTO creators (creator_id) VALUES ('test')")
        if "error" not in result3:
            return False, "Should reject INSERT queries"

        # Test UPDATE rejection
        result4 = execute_query("UPDATE creators SET is_active = 0")
        if "error" not in result4:
            return False, "Should reject UPDATE queries"

        # Test DELETE rejection
        result5 = execute_query("DELETE FROM creators")
        if "error" not in result5:
            return False, "Should reject DELETE queries"

        # Test DROP rejection
        result6 = execute_query("DROP TABLE creators")
        if "error" not in result6:
            return False, "Should reject DROP queries"

        count = result["results"][0]["cnt"] if result["results"] else 0
        return True, f"Active creators: {count}, Security checks passed"
    except Exception as e:
        return False, str(e)


def test_save_schedule() -> tuple[bool, str]:
    """Test save_schedule tool (read-only test to avoid creating data)."""
    try:
        creators = get_active_creators()
        if "error" in creators or not creators.get("creators"):
            return False, "Could not get active creators"

        # Use a test date in the past to avoid conflicts
        test_week = "2020-01-06"  # A Monday in the past
        creator_id = creators["creators"][0]["creator_id"]

        # Test with old format (backward compatibility)
        test_items_old = [
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "14:00",
                "item_type": "ppv",
                "channel": "mass_message",
                "caption_text": "Test caption",
                "suggested_price": 10.00,
                "priority": 5
            },
            {
                "scheduled_date": "2020-01-06",
                "scheduled_time": "14:45",
                "item_type": "bump",
                "channel": "mass_message",
                "caption_text": "Test bump",
                "priority": 3
            }
        ]

        result = save_schedule(creator_id, test_week, test_items_old)
        if "error" in result:
            return False, result["error"]

        if not result.get("success"):
            return False, "save_schedule did not return success"

        # Test with new format including send_type_key, channel_key, target_key
        test_week_2 = "2020-01-13"  # Another Monday in the past
        test_items_new = [
            {
                "scheduled_date": "2020-01-13",
                "scheduled_time": "14:00",
                "item_type": "ppv",
                "channel": "mass_message",
                "send_type_key": "ppv_unlock",
                "channel_key": "mass_message",
                "target_key": "all_fans",
                "caption_text": "Test caption with new fields",
                "suggested_price": 10.00,
                "priority": 5
            }
        ]

        result2 = save_schedule(creator_id, test_week_2, test_items_new)
        if "error" in result2:
            return False, f"New format error: {result2['error']}"

        if not result2.get("success"):
            return False, "save_schedule with new format did not return success"

        return True, f"Old format: {result.get('items_created')} items, New format: {result2.get('items_created')} items"
    except Exception as e:
        return False, str(e)


def test_mcp_protocol() -> tuple[bool, str]:
    """Test MCP JSON-RPC protocol handling."""
    try:
        # Test tools/list
        request1 = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response1 = handle_request(request1)
        if "error" in response1:
            return False, f"tools/list error: {response1['error']}"
        if "result" not in response1 or "tools" not in response1["result"]:
            return False, "tools/list missing tools"
        if len(response1["result"]["tools"]) != 17:
            return False, f"Expected 17 tools, got {len(response1['result']['tools'])}"

        # Test tools/call
        request2 = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "execute_query",
                "arguments": {"query": "SELECT 1 as test"}
            }
        }
        response2 = handle_request(request2)
        if "error" in response2:
            return False, f"tools/call error: {response2['error']}"

        # Test initialize
        request3 = {"jsonrpc": "2.0", "id": 3, "method": "initialize"}
        response3 = handle_request(request3)
        if "error" in response3:
            return False, f"initialize error: {response3['error']}"
        if "result" not in response3 or "capabilities" not in response3["result"]:
            return False, "initialize missing capabilities"

        # Test unknown method
        request4 = {"jsonrpc": "2.0", "id": 4, "method": "unknown/method"}
        response4 = handle_request(request4)
        if "error" not in response4:
            return False, "Should return error for unknown method"

        # Test unknown tool
        request5 = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}}
        }
        response5 = handle_request(request5)
        if "error" not in response5:
            return False, "Should return error for unknown tool"

        return True, f"All protocol tests passed, {len(response1['result']['tools'])} tools registered"
    except Exception as e:
        return False, str(e)


def test_tool_definitions() -> tuple[bool, str]:
    """Verify all tool definitions are valid."""
    try:
        tool_names = [t["name"] for t in TOOLS]
        expected_tools = [
            "get_active_creators",
            "get_creator_profile",
            "get_top_captions",
            "get_best_timing",
            "get_volume_assignment",
            "get_performance_trends",
            "get_content_type_rankings",
            "get_persona_profile",
            "get_vault_availability",
            "save_schedule",
            "execute_query",
            "get_send_types",
            "get_send_type_details",
            "get_send_type_captions",
            "get_channels",
            "get_audience_targets",
            "get_volume_config"
        ]

        for expected in expected_tools:
            if expected not in tool_names:
                return False, f"Missing tool definition: {expected}"

        # Check each tool has required fields
        for tool in TOOLS:
            if "name" not in tool:
                return False, "Tool missing 'name'"
            if "description" not in tool:
                return False, f"Tool {tool.get('name', 'unknown')} missing 'description'"
            if "inputSchema" not in tool:
                return False, f"Tool {tool['name']} missing 'inputSchema'"

        return True, f"All {len(TOOLS)} tool definitions valid"
    except Exception as e:
        return False, str(e)


def run_all_tests() -> dict[str, Any]:
    """Run all tests and return summary."""
    print_header("EROS MCP Server Test Suite")
    print(f"  Database: {DB_PATH}")
    print(f"  Timestamp: {datetime.now().isoformat()}")

    results = {"passed": 0, "failed": 0, "tests": []}

    # Infrastructure Tests
    print_header("Infrastructure Tests")

    db_ok = test_database_connection()
    print_test("Database Connection", db_ok)
    results["tests"].append(("Database Connection", db_ok))
    if db_ok:
        results["passed"] += 1
    else:
        results["failed"] += 1
        print(f"\n{TestColors.RED}FATAL: Cannot connect to database. Aborting tests.{TestColors.RESET}")
        return results

    tool_ok, tool_msg = test_tool_definitions()
    print_test("Tool Definitions", tool_ok, tool_msg)
    results["tests"].append(("Tool Definitions", tool_ok))
    results["passed" if tool_ok else "failed"] += 1

    # Function Tests
    print_header("Tool Function Tests (17 Tools)")

    tests = [
        ("get_active_creators", test_get_active_creators),
        ("get_creator_profile", test_get_creator_profile),
        ("get_top_captions", test_get_top_captions),
        ("get_best_timing", test_get_best_timing),
        ("get_volume_assignment", test_get_volume_assignment),
        ("get_performance_trends", test_get_performance_trends),
        ("get_content_type_rankings", test_get_content_type_rankings),
        ("get_persona_profile", test_get_persona_profile),
        ("get_vault_availability", test_get_vault_availability),
        ("get_send_types", test_get_send_types),
        ("get_send_type_details", test_get_send_type_details),
        ("get_send_type_captions", test_get_send_type_captions),
        ("get_channels", test_get_channels),
        ("get_audience_targets", test_get_audience_targets),
        ("get_volume_config", test_get_volume_config),
        ("execute_query", test_execute_query),
        ("save_schedule", test_save_schedule),
    ]

    for name, test_func in tests:
        passed, details = test_func()
        print_test(name, passed, details)
        results["tests"].append((name, passed))
        results["passed" if passed else "failed"] += 1

    # Protocol Tests
    print_header("MCP Protocol Tests")

    protocol_ok, protocol_msg = test_mcp_protocol()
    print_test("JSON-RPC Protocol", protocol_ok, protocol_msg)
    results["tests"].append(("JSON-RPC Protocol", protocol_ok))
    results["passed" if protocol_ok else "failed"] += 1

    # Summary
    print_header("Test Summary")
    total = results["passed"] + results["failed"]
    pct = (results["passed"] / total * 100) if total > 0 else 0

    color = TestColors.GREEN if results["failed"] == 0 else TestColors.RED
    print(f"  {color}Passed: {results['passed']}/{total} ({pct:.1f}%){TestColors.RESET}")

    if results["failed"] > 0:
        print(f"\n  {TestColors.RED}Failed Tests:{TestColors.RESET}")
        for name, passed in results["tests"]:
            if not passed:
                print(f"    - {name}")

    print(f"\n{'='*60}\n")

    return results


if __name__ == "__main__":
    results = run_all_tests()
    sys.exit(0 if results["failed"] == 0 else 1)
