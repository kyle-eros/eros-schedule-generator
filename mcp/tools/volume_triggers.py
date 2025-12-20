"""
EROS MCP Server Volume Triggers Tools

Tools for saving and retrieving volume triggers that adjust content type allocations
based on performance signals (HIGH_PERFORMER, TRENDING_UP, SATURATING, etc.).

Version: 3.0.0
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import resolve_creator_id, rows_to_list
from mcp.utils.security import validate_creator_id, validate_key_input

logger = logging.getLogger("eros_db_server")

# Valid trigger types matching the database CHECK constraint
VALID_TRIGGER_TYPES = frozenset({
    "HIGH_PERFORMER",
    "TRENDING_UP",
    "EMERGING_WINNER",
    "SATURATING",
    "AUDIENCE_FATIGUE",
})

# Valid confidence levels
VALID_CONFIDENCE_LEVELS = frozenset({"low", "moderate", "high"})


@mcp_tool(
    name="save_volume_triggers",
    description="Save volume triggers detected by performance-analyst. Deactivates existing active triggers for creator before inserting new ones.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "triggers": {
                "type": "array",
                "description": "List of trigger dictionaries to save",
                "items": {
                    "type": "object",
                    "properties": {
                        "content_type": {
                            "type": "string",
                            "description": "Content type this trigger applies to (e.g., 'lingerie', 'b/g')"
                        },
                        "trigger_type": {
                            "type": "string",
                            "enum": ["HIGH_PERFORMER", "TRENDING_UP", "EMERGING_WINNER", "SATURATING", "AUDIENCE_FATIGUE"],
                            "description": "Type of performance signal detected"
                        },
                        "adjustment_multiplier": {
                            "type": "number",
                            "description": "Multiplier for volume adjustment (e.g., 1.20 for +20%, 0.80 for -20%)"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Human-readable reason for this trigger (e.g., 'RPS $245, conversion 7.2%')"
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "moderate", "high"],
                            "description": "Confidence level of the trigger detection (default: 'moderate')"
                        },
                        "metrics_json": {
                            "type": "string",
                            "description": "Optional JSON string with supporting metrics"
                        },
                        "expires_at": {
                            "type": "string",
                            "description": "ISO format date when trigger expires (YYYY-MM-DD)"
                        }
                    },
                    "required": ["content_type", "trigger_type", "adjustment_multiplier", "reason", "expires_at"]
                }
            }
        },
        "required": ["creator_id", "triggers"]
    }
)
def save_volume_triggers(
    creator_id: str,
    triggers: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Save volume triggers detected by performance analysis.

    Deactivates all existing active triggers for the creator before inserting
    new ones. This ensures a clean slate for each analysis run.

    Args:
        creator_id: The creator_id or page_name.
        triggers: List of trigger dictionaries, each containing:
            - content_type: Content type this trigger applies to (required)
            - trigger_type: One of HIGH_PERFORMER, TRENDING_UP, EMERGING_WINNER,
                          SATURATING, AUDIENCE_FATIGUE (required)
            - adjustment_multiplier: Volume adjustment factor (required)
            - reason: Human-readable explanation (required)
            - confidence: 'low', 'moderate', or 'high' (default: 'moderate')
            - metrics_json: Optional JSON string with supporting metrics
            - expires_at: ISO date string for expiration (required)

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - triggers_saved: Number of triggers inserted
            - triggers_deactivated: Number of previously active triggers deactivated
            - warnings: List of validation warnings (if any)

    Example:
        >>> save_volume_triggers("alexia", [
        ...     {
        ...         "content_type": "lingerie",
        ...         "trigger_type": "HIGH_PERFORMER",
        ...         "adjustment_multiplier": 1.20,
        ...         "reason": "RPS $245, conversion 7.2%",
        ...         "confidence": "high",
        ...         "expires_at": "2025-12-25"
        ...     }
        ... ])
        {'success': True, 'triggers_saved': 1, 'triggers_deactivated': 2}
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"save_volume_triggers: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if not triggers:
        return {"error": "triggers list cannot be empty"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        warnings: list[str] = []

        # Validate all triggers before making any changes
        validated_triggers: list[dict[str, Any]] = []
        for idx, trigger in enumerate(triggers):
            # Required fields
            content_type = trigger.get("content_type")
            trigger_type = trigger.get("trigger_type")
            adjustment_multiplier = trigger.get("adjustment_multiplier")
            reason = trigger.get("reason")
            expires_at = trigger.get("expires_at")

            # Validate required fields
            if not content_type:
                return {"error": f"Trigger {idx}: content_type is required"}
            if not trigger_type:
                return {"error": f"Trigger {idx}: trigger_type is required"}
            if adjustment_multiplier is None:
                return {"error": f"Trigger {idx}: adjustment_multiplier is required"}
            if not reason:
                return {"error": f"Trigger {idx}: reason is required"}
            if not expires_at:
                return {"error": f"Trigger {idx}: expires_at is required"}

            # Validate trigger_type
            if trigger_type not in VALID_TRIGGER_TYPES:
                return {
                    "error": f"Trigger {idx}: Invalid trigger_type '{trigger_type}'. "
                             f"Must be one of: {', '.join(sorted(VALID_TRIGGER_TYPES))}"
                }

            # Validate content_type format
            is_valid_key, key_error = validate_key_input(
                content_type.replace("/", "_").replace(" ", "_"),
                "content_type"
            )
            # Allow slashes and spaces in content_type (e.g., "b/g", "solo tease")
            if len(content_type) > 100:
                return {"error": f"Trigger {idx}: content_type exceeds maximum length of 100"}

            # Validate adjustment_multiplier range
            if not isinstance(adjustment_multiplier, (int, float)):
                return {"error": f"Trigger {idx}: adjustment_multiplier must be a number"}
            if adjustment_multiplier <= 0 or adjustment_multiplier > 3.0:
                warnings.append(
                    f"Trigger {idx}: adjustment_multiplier {adjustment_multiplier} is outside "
                    "typical range (0.5-2.0)"
                )

            # Validate confidence
            confidence = trigger.get("confidence", "moderate")
            if confidence not in VALID_CONFIDENCE_LEVELS:
                return {
                    "error": f"Trigger {idx}: Invalid confidence '{confidence}'. "
                             f"Must be one of: {', '.join(sorted(VALID_CONFIDENCE_LEVELS))}"
                }

            # Validate expires_at format
            try:
                datetime.strptime(expires_at, "%Y-%m-%d")
            except ValueError:
                return {"error": f"Trigger {idx}: expires_at must be in YYYY-MM-DD format"}

            # Validate metrics_json if provided
            metrics_json = trigger.get("metrics_json")
            if metrics_json:
                try:
                    # Verify it's valid JSON
                    json.loads(metrics_json)
                except json.JSONDecodeError:
                    return {"error": f"Trigger {idx}: metrics_json is not valid JSON"}

            validated_triggers.append({
                "content_type": content_type,
                "trigger_type": trigger_type,
                "adjustment_multiplier": adjustment_multiplier,
                "reason": reason,
                "confidence": confidence,
                "metrics_json": metrics_json,
                "expires_at": expires_at,
            })

        # Deactivate existing active triggers for this creator
        cursor = conn.execute(
            """
            UPDATE volume_triggers
            SET is_active = 0
            WHERE creator_id = ? AND is_active = 1
            """,
            (resolved_creator_id,)
        )
        triggers_deactivated = cursor.rowcount

        # Insert new triggers
        triggers_saved = 0
        for trigger in validated_triggers:
            conn.execute(
                """
                INSERT INTO volume_triggers (
                    creator_id, content_type, trigger_type,
                    adjustment_multiplier, reason, confidence,
                    metrics_json, expires_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    resolved_creator_id,
                    trigger["content_type"],
                    trigger["trigger_type"],
                    trigger["adjustment_multiplier"],
                    trigger["reason"],
                    trigger["confidence"],
                    trigger["metrics_json"],
                    trigger["expires_at"],
                )
            )
            triggers_saved += 1

        conn.commit()

        result: dict[str, Any] = {
            "success": True,
            "triggers_saved": triggers_saved,
            "triggers_deactivated": triggers_deactivated,
        }
        if warnings:
            result["warnings"] = warnings

        logger.info(
            f"save_volume_triggers: Saved {triggers_saved} triggers for {resolved_creator_id}, "
            f"deactivated {triggers_deactivated}"
        )
        return result

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"save_volume_triggers: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


@mcp_tool(
    name="get_active_volume_triggers",
    description="Get all active volume triggers for a creator. Automatically filters out expired triggers.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            }
        },
        "required": ["creator_id"]
    }
)
def get_active_volume_triggers(creator_id: str) -> dict[str, Any]:
    """
    Get all active volume triggers for a creator.

    Returns triggers that are both active (is_active = 1) and not expired
    (expires_at > current datetime). Used by send-type-allocator to adjust
    content type allocations based on performance signals.

    Args:
        creator_id: The creator_id or page_name to look up.

    Returns:
        Dictionary containing:
            - triggers: List of active trigger dictionaries, each with:
                - trigger_id: Unique identifier
                - content_type: Content type the trigger applies to
                - trigger_type: Type of signal (HIGH_PERFORMER, etc.)
                - adjustment_multiplier: Volume adjustment factor
                - reason: Human-readable explanation
                - confidence: Confidence level (low/moderate/high)
                - metrics_json: Supporting metrics (if provided)
                - detected_at: When the trigger was created
                - expires_at: When the trigger expires
                - applied_count: Number of times trigger has been applied
            - count: Number of active triggers
            - creator_id: Resolved creator_id

    Example:
        >>> result = get_active_volume_triggers("alexia")
        >>> for trigger in result["triggers"]:
        ...     if trigger["trigger_type"] == "HIGH_PERFORMER":
        ...         # Increase allocation for this content type
        ...         allocation *= trigger["adjustment_multiplier"]
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_active_volume_triggers: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Get active, non-expired triggers
        cursor = conn.execute(
            """
            SELECT
                trigger_id,
                content_type,
                trigger_type,
                adjustment_multiplier,
                reason,
                confidence,
                metrics_json,
                detected_at,
                expires_at,
                applied_count
            FROM volume_triggers
            WHERE creator_id = ?
              AND is_active = 1
              AND expires_at > datetime('now')
            ORDER BY detected_at DESC
            """,
            (resolved_creator_id,)
        )
        triggers = rows_to_list(cursor.fetchall())

        return {
            "triggers": triggers,
            "count": len(triggers),
            "creator_id": resolved_creator_id,
        }

    except sqlite3.Error as e:
        logger.error(f"get_active_volume_triggers: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()
