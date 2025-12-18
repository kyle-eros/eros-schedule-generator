"""
EROS MCP Server Targeting Tools

Tools for retrieving channels and audience targeting options.
"""

import json
import logging
from typing import Any, Optional

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import rows_to_list
from mcp.utils.security import validate_key_input

logger = logging.getLogger("eros_db_server")


@mcp_tool(
    name="get_channels",
    description="Get all channels with optional filtering by targeting support.",
    schema={
        "type": "object",
        "properties": {
            "supports_targeting": {
                "type": "boolean",
                "description": "Optional filter by targeting support (true/false)"
            }
        },
        "required": []
    }
)
def get_channels(
    supports_targeting: Optional[bool] = None
) -> dict[str, Any]:
    """
    Get all channels with optional filtering by targeting support.

    Args:
        supports_targeting: Optional filter by targeting support (True/False).

    Returns:
        Dictionary containing:
            - channels: List of all channel records
            - count: Total number of channels returned
    """
    conn = get_db_connection()
    try:
        query = """
            SELECT
                channel_id,
                channel_key,
                display_name,
                description,
                supports_targeting,
                targeting_options,
                platform_feature,
                requires_manual_send,
                is_active,
                created_at
            FROM channels
            WHERE is_active = 1
        """
        params: list[Any] = []

        if supports_targeting is not None:
            query += " AND supports_targeting = ?"
            params.append(1 if supports_targeting else 0)

        query += " ORDER BY channel_id ASC"

        cursor = conn.execute(query, params)
        channels = rows_to_list(cursor.fetchall())

        # Parse JSON targeting_options for each channel
        for channel in channels:
            if channel.get("targeting_options"):
                try:
                    channel["targeting_options"] = json.loads(channel["targeting_options"])
                except json.JSONDecodeError:
                    pass  # Keep as string if not valid JSON

        return {
            "channels": channels,
            "count": len(channels)
        }
    finally:
        conn.close()


@mcp_tool(
    name="get_audience_targets",
    description="Get audience targets filtered by page_type and/or channel_key using JSON array matching.",
    schema={
        "type": "object",
        "properties": {
            "page_type": {
                "type": "string",
                "enum": ["paid", "free"],
                "description": "Optional filter by page_type (matches in applicable_page_types JSON array)"
            },
            "channel_key": {
                "type": "string",
                "description": "Optional filter by channel key (matches in applicable_channels JSON array)"
            }
        },
        "required": []
    }
)
def get_audience_targets(
    page_type: Optional[str] = None,
    channel_key: Optional[str] = None
) -> dict[str, Any]:
    """
    Get audience targets filtered by page_type and/or channel.

    Uses JSON array matching for applicable_page_types and applicable_channels columns.

    Args:
        page_type: Optional filter by page_type ('paid' or 'free').
                   Matches targets where page_type is in applicable_page_types JSON array.
        channel_key: Optional filter by channel key.
                     Matches targets where channel_key is in applicable_channels JSON array.

    Returns:
        Dictionary containing:
            - targets: List of audience target records
            - count: Total number of targets returned
    """
    # Input validation
    if channel_key is not None:
        is_valid, error_msg = validate_key_input(channel_key, "channel_key")
        if not is_valid:
            logger.warning(f"get_audience_targets: Invalid channel_key - {error_msg}")
            return {"error": f"Invalid channel_key: {error_msg}"}

    conn = get_db_connection()
    try:
        query = """
            SELECT
                target_id,
                target_key,
                display_name,
                description,
                filter_type,
                filter_criteria,
                applicable_page_types,
                applicable_channels,
                typical_reach_percentage,
                is_active,
                created_at
            FROM audience_targets
            WHERE is_active = 1
        """
        params: list[Any] = []

        if page_type is not None:
            if page_type not in ("paid", "free"):
                return {"error": "page_type must be 'paid' or 'free'"}
            # Match page_type in JSON array using LIKE for SQLite compatibility
            query += " AND (applicable_page_types LIKE ? OR applicable_page_types LIKE ?)"
            params.append(f'%"{page_type}"%')
            params.append(f"%'{page_type}'%")

        if channel_key is not None:
            # Match channel_key in JSON array using LIKE
            query += " AND (applicable_channels LIKE ? OR applicable_channels LIKE ?)"
            params.append(f'%"{channel_key}"%')
            params.append(f"%'{channel_key}'%")

        query += " ORDER BY target_id ASC"

        cursor = conn.execute(query, params)
        targets = rows_to_list(cursor.fetchall())

        # Parse JSON fields for each target
        for target in targets:
            if target.get("filter_criteria"):
                try:
                    target["filter_criteria"] = json.loads(target["filter_criteria"])
                except json.JSONDecodeError:
                    pass
            if target.get("applicable_page_types"):
                try:
                    target["applicable_page_types"] = json.loads(target["applicable_page_types"])
                except json.JSONDecodeError:
                    pass
            if target.get("applicable_channels"):
                try:
                    target["applicable_channels"] = json.loads(target["applicable_channels"])
                except json.JSONDecodeError:
                    pass

        return {
            "targets": targets,
            "count": len(targets)
        }
    finally:
        conn.close()
