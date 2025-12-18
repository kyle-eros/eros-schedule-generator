"""
EROS MCP Server Schedule Tools

Tools for saving generated schedules to the database.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import resolve_creator_id
from mcp.utils.security import validate_creator_id

logger = logging.getLogger("eros_db_server")


@mcp_tool(
    name="save_schedule",
    description="Save generated schedule to database (creates template and items). Supports both legacy format and new send_type_key/channel_key/target_key fields.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id for the schedule"
            },
            "week_start": {
                "type": "string",
                "description": "ISO format date for week start (YYYY-MM-DD)"
            },
            "items": {
                "type": "array",
                "description": "List of schedule items",
                "items": {
                    "type": "object",
                    "properties": {
                        "scheduled_date": {"type": "string"},
                        "scheduled_time": {"type": "string"},
                        "item_type": {"type": "string"},
                        "channel": {"type": "string"},
                        "send_type_key": {"type": "string", "description": "Send type key (resolves to send_type_id)"},
                        "channel_key": {"type": "string", "description": "Channel key (resolves to channel_id)"},
                        "target_key": {"type": "string", "description": "Audience target key (resolves to target_id)"},
                        "caption_id": {"type": "integer"},
                        "caption_text": {"type": "string"},
                        "suggested_price": {"type": "number"},
                        "content_type_id": {"type": "integer"},
                        "flyer_required": {"type": "integer"},
                        "priority": {"type": "integer"},
                        "linked_post_url": {"type": "string"},
                        "expires_at": {"type": "string"},
                        "followup_delay_minutes": {"type": "integer"},
                        "media_type": {"type": "string", "enum": ["none", "picture", "gif", "video", "flyer"]},
                        "campaign_goal": {"type": "number"},
                        "parent_item_id": {"type": "integer", "description": "Parent item ID for followups (auto-sets is_follow_up=1)"}
                    },
                    "required": ["scheduled_date", "scheduled_time", "item_type", "channel"]
                }
            }
        },
        "required": ["creator_id", "week_start", "items"]
    }
)
def save_schedule(
    creator_id: str,
    week_start: str,
    items: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Save generated schedule to database.

    Creates a schedule_template record and inserts all schedule_items.
    Supports both legacy item_type/channel format and new send_type_key/channel_key format.

    Args:
        creator_id: The creator_id for the schedule.
        week_start: ISO format date for week start (YYYY-MM-DD).
        items: List of schedule items, each containing:
            - scheduled_date: ISO date string (required)
            - scheduled_time: Time string HH:MM (required)
            - item_type: Legacy type of item (e.g., 'ppv', 'bump')
            - channel: Legacy 'mass_message' or 'wall_post'
            - send_type_key: New send type key (resolves to send_type_id)
            - channel_key: New channel key (resolves to channel_id)
            - target_key: Audience target key (resolves to target_id)
            - caption_id: Optional caption ID
            - caption_text: Optional caption text
            - suggested_price: Optional price
            - content_type_id: Optional content type ID
            - flyer_required: Optional 0/1
            - priority: Optional priority (default 5)
            - linked_post_url: URL for linked wall post
            - expires_at: Expiration datetime
            - followup_delay_minutes: Minutes to wait for followup
            - media_type: 'none', 'picture', 'gif', 'video', 'flyer'
            - campaign_goal: Revenue goal for the item
            - parent_item_id: Parent item ID for followups

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - template_id: ID of created template
            - items_created: Number of items inserted
            - warnings: List of validation warnings (if any)
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"save_schedule: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    conn = get_db_connection()
    try:
        # Validate creator exists
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Calculate week_end (7 days after week_start)
        try:
            week_start_dt = datetime.strptime(week_start, "%Y-%m-%d")
            week_end = (week_start_dt + timedelta(days=6)).strftime("%Y-%m-%d")
        except ValueError:
            return {"error": "week_start must be in YYYY-MM-DD format"}

        # Pre-load lookup tables for key resolution
        cursor = conn.execute("SELECT send_type_id, send_type_key, requires_flyer FROM send_types")
        send_types_map = {row["send_type_key"]: {"id": row["send_type_id"], "requires_flyer": row["requires_flyer"]} for row in cursor.fetchall()}

        cursor = conn.execute("SELECT channel_id, channel_key FROM channels")
        channels_map = {row["channel_key"]: row["channel_id"] for row in cursor.fetchall()}

        cursor = conn.execute("SELECT target_id, target_key FROM audience_targets")
        targets_map = {row["target_key"]: row["target_id"] for row in cursor.fetchall()}

        # Count PPVs and bumps
        total_ppvs = sum(1 for item in items if item.get("item_type") == "ppv" or (item.get("send_type_key") or "").startswith("ppv"))
        total_bumps = sum(1 for item in items if item.get("item_type") in ("bump", "ppv_bump") or (item.get("send_type_key") or "").startswith("bump"))

        # Insert template
        cursor = conn.execute(
            """
            INSERT INTO schedule_templates (
                creator_id, week_start, week_end, generated_at,
                generated_by, algorithm_version, total_items,
                total_ppvs, total_bumps, status
            ) VALUES (?, ?, ?, datetime('now'), 'mcp_server', '2.0', ?, ?, ?, 'draft')
            ON CONFLICT(creator_id, week_start) DO UPDATE SET
                week_end = excluded.week_end,
                generated_at = datetime('now'),
                total_items = excluded.total_items,
                total_ppvs = excluded.total_ppvs,
                total_bumps = excluded.total_bumps,
                status = 'draft'
            """,
            (resolved_creator_id, week_start, week_end, len(items), total_ppvs, total_bumps)
        )

        # Get the template_id
        cursor = conn.execute(
            """
            SELECT template_id FROM schedule_templates
            WHERE creator_id = ? AND week_start = ?
            """,
            (resolved_creator_id, week_start)
        )
        template_row = cursor.fetchone()
        template_id = template_row["template_id"]

        # Delete existing items for this template (in case of update)
        conn.execute(
            "DELETE FROM schedule_items WHERE template_id = ?",
            (template_id,)
        )

        # Insert schedule items
        items_created = 0
        warnings: list[str] = []

        for idx, item in enumerate(items):
            # Resolve send_type_key to send_type_id
            send_type_id = None
            send_type_key = item.get("send_type_key")
            if send_type_key:
                if send_type_key in send_types_map:
                    send_type_info = send_types_map[send_type_key]
                    send_type_id = send_type_info["id"]
                    # Validate flyer requirement
                    if send_type_info["requires_flyer"] == 1 and item.get("flyer_required", 0) == 0:
                        warnings.append(f"Item {idx}: send_type '{send_type_key}' requires flyer but flyer_required=0")
                else:
                    warnings.append(f"Item {idx}: Unknown send_type_key '{send_type_key}'")

            # Resolve channel_key to channel_id
            channel_id = None
            channel_key = item.get("channel_key")
            if channel_key:
                if channel_key in channels_map:
                    channel_id = channels_map[channel_key]
                else:
                    warnings.append(f"Item {idx}: Unknown channel_key '{channel_key}'")

            # Resolve target_key to target_id
            target_id = None
            target_key = item.get("target_key")
            if target_key:
                if target_key in targets_map:
                    target_id = targets_map[target_key]
                else:
                    warnings.append(f"Item {idx}: Unknown target_key '{target_key}'")

            # Determine is_follow_up based on parent_item_id
            parent_item_id = item.get("parent_item_id")
            is_follow_up = 1 if parent_item_id is not None else 0

            conn.execute(
                """
                INSERT INTO schedule_items (
                    template_id, creator_id, scheduled_date, scheduled_time,
                    item_type, channel, caption_id, caption_text,
                    suggested_price, content_type_id, flyer_required, priority, status,
                    send_type_id, channel_id, target_id,
                    linked_post_url, expires_at, followup_delay_minutes,
                    media_type, campaign_goal, parent_item_id, is_follow_up
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template_id,
                    resolved_creator_id,
                    item.get("scheduled_date"),
                    item.get("scheduled_time"),
                    item.get("item_type"),
                    item.get("channel", "mass_message"),
                    item.get("caption_id"),
                    item.get("caption_text"),
                    item.get("suggested_price"),
                    item.get("content_type_id"),
                    item.get("flyer_required", 0),
                    item.get("priority", 5),
                    send_type_id,
                    channel_id,
                    target_id,
                    item.get("linked_post_url"),
                    item.get("expires_at"),
                    item.get("followup_delay_minutes"),
                    item.get("media_type"),
                    item.get("campaign_goal"),
                    parent_item_id,
                    is_follow_up
                )
            )
            items_created += 1

        conn.commit()

        result: dict[str, Any] = {
            "success": True,
            "template_id": template_id,
            "items_created": items_created,
            "week_start": week_start,
            "week_end": week_end
        }
        if warnings:
            result["warnings"] = warnings

        return result
    except sqlite3.Error as e:
        conn.rollback()
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()
