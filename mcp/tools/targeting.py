"""
EROS MCP Server Targeting Tools

Tools for retrieving channels.
"""

import json
import logging
from typing import Any, Optional

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import rows_to_list

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
