"""
EROS MCP Server Schedule Tools

Tools for saving generated schedules to the database.

Version: 3.0.0
- Added optional validation_certificate parameter for Four-Layer Defense (v3.1)
- Phase 1: Certificate is optional with warning logging
- Phase 2 (future): Certificate will be required
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import resolve_creator_id
from mcp.utils.security import validate_creator_id

logger = logging.getLogger("eros_db_server")


def _validate_certificate(
    certificate: Optional[dict[str, Any]],
    items: list[dict[str, Any]],
    creator_id: str
) -> dict[str, Any]:
    """
    Validate a ValidationCertificate from quality-validator.

    Phase 1 (Current): Returns validation result but doesn't block.
    Phase 2 (Future): Will return errors that block save.

    Args:
        certificate: ValidationCertificate from quality-validator
        items: Schedule items to validate against
        creator_id: Creator ID for verification

    Returns:
        Dict with:
            - valid: Whether certificate is valid
            - warnings: List of warning messages
            - errors: List of error messages (Phase 2)
    """
    warnings: list[str] = []
    errors: list[str] = []

    # 1. Certificate presence check
    if not certificate:
        warnings.append("CERTIFICATE_MISSING: No validation_certificate provided. "
                       "Schedule will be saved but validation cannot be verified. "
                       "(Phase 1: Warning only)")
        return {"valid": True, "warnings": warnings, "errors": errors}

    # 2. Certificate freshness (< 5 minutes)
    try:
        cert_timestamp = certificate.get("validation_timestamp")
        if cert_timestamp:
            # Handle both formats: with and without timezone
            if cert_timestamp.endswith("Z"):
                cert_timestamp = cert_timestamp[:-1]  # Remove Z suffix
            cert_time = datetime.fromisoformat(cert_timestamp)
            age_seconds = (datetime.now() - cert_time).total_seconds()
            if age_seconds > 300:  # 5 minutes
                warnings.append(f"STALE_CERTIFICATE: Certificate is {age_seconds/60:.1f} minutes old. "
                               "Validation may be outdated.")
    except (ValueError, TypeError) as e:
        warnings.append(f"INVALID_TIMESTAMP: Could not parse validation_timestamp: {e}")

    # 3. Validation status check
    status = certificate.get("validation_status")
    if status not in ("APPROVED", "NEEDS_REVIEW"):
        warnings.append(f"INVALID_STATUS: Certificate status '{status}' is not APPROVED or NEEDS_REVIEW")

    # 4. Creator ID match
    cert_creator = certificate.get("creator_id")
    if cert_creator and cert_creator != creator_id:
        warnings.append(f"CREATOR_MISMATCH: Certificate creator '{cert_creator}' != '{creator_id}'")

    # 5. Item count verification
    cert_items = certificate.get("items_validated", 0)
    if cert_items != len(items):
        warnings.append(f"ITEM_COUNT_MISMATCH: Certificate validated {cert_items} items, "
                       f"but saving {len(items)} items")

    # 6. Violations check
    violations = certificate.get("violations_found", {})
    vault_violations = violations.get("vault", 0)
    avoid_violations = violations.get("avoid_tier", 0)

    if vault_violations > 0:
        warnings.append(f"VAULT_VIOLATIONS_IN_CERT: Certificate reports {vault_violations} vault violations")

    if avoid_violations > 0:
        warnings.append(f"AVOID_VIOLATIONS_IN_CERT: Certificate reports {avoid_violations} AVOID tier violations")

    # Log certificate info
    if certificate:
        signature = certificate.get("certificate_signature", "unknown")
        quality_score = certificate.get("quality_score", "unknown")
        logger.info(f"save_schedule: Certificate received - signature={signature}, "
                   f"score={quality_score}, status={status}")

    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "certificate_signature": certificate.get("certificate_signature")
    }


# Maximum schedule items to prevent resource exhaustion
MAX_SCHEDULE_ITEMS = 100


@mcp_tool(
    name="save_schedule",
    description="Save generated schedule to database (creates template and items). Supports both legacy format and new send_type_key/channel_key fields.",
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
            },
            "validation_certificate": {
                "type": "object",
                "description": "Optional ValidationCertificate from quality-validator (Four-Layer Defense v3.1). Phase 1: Optional with warning. Phase 2: Will be required.",
                "properties": {
                    "certificate_version": {"type": "string"},
                    "creator_id": {"type": "string"},
                    "validation_timestamp": {"type": "string"},
                    "schedule_hash": {"type": "string"},
                    "avoid_types_hash": {"type": "string"},
                    "vault_types_hash": {"type": "string"},
                    "items_validated": {"type": "integer"},
                    "quality_score": {"type": "number"},
                    "validation_status": {"type": "string", "enum": ["APPROVED", "NEEDS_REVIEW", "REJECTED"]},
                    "checks_performed": {"type": "object"},
                    "violations_found": {"type": "object"},
                    "upstream_proof_verified": {"type": "boolean"},
                    "certificate_signature": {"type": "string"}
                }
            }
        },
        "required": ["creator_id", "week_start", "items"]
    }
)
def save_schedule(
    creator_id: str,
    week_start: str,
    items: list[dict[str, Any]],
    validation_certificate: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Save generated schedule to database.

    Creates a schedule_template record and inserts all schedule_items.
    Supports both legacy item_type/channel format and new send_type_key/channel_key format.

    Four-Layer Defense (v3.1):
        - Layer 4 (this function) validates the ValidationCertificate from quality-validator
        - Phase 1 (current): Certificate is optional, warnings logged if missing
        - Phase 2 (future): Certificate will be required, save blocked if invalid

    Args:
        creator_id: The creator_id for the schedule.
        week_start: ISO format date for week start (YYYY-MM-DD).
        items: List of schedule items (max 100), each containing:
            - scheduled_date: ISO date string (required)
            - scheduled_time: Time string HH:MM (required)
            - item_type: Legacy type of item (e.g., 'ppv', 'bump')
            - channel: Legacy 'mass_message' or 'wall_post'
            - send_type_key: New send type key (resolves to send_type_id)
            - channel_key: New channel key (resolves to channel_id)
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
        validation_certificate: Optional ValidationCertificate from quality-validator.
            Contains validation proof including vault compliance, AVOID tier exclusion,
            and quality score. Phase 1: Optional with warning. Phase 2: Required.

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - template_id: ID of created template
            - items_created: Number of items inserted
            - warnings: List of validation warnings (if any)
            - certificate_validation: Certificate validation result (if provided)
    """
    # Payload size validation (prevent resource exhaustion)
    if len(items) > MAX_SCHEDULE_ITEMS:
        logger.warning(f"save_schedule: Payload exceeds maximum. Received {len(items)} items, max is {MAX_SCHEDULE_ITEMS}")
        return {"error": f"Schedule exceeds maximum of {MAX_SCHEDULE_ITEMS} items. Received: {len(items)}"}

    # Validate certificate (Phase 1: warnings only)
    cert_validation = _validate_certificate(validation_certificate, items, creator_id)
    if cert_validation["warnings"]:
        for warning in cert_validation["warnings"]:
            logger.warning(f"save_schedule certificate: {warning}")

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

            # Determine is_follow_up based on parent_item_id
            parent_item_id = item.get("parent_item_id")
            is_follow_up = 1 if parent_item_id is not None else 0

            conn.execute(
                """
                INSERT INTO schedule_items (
                    template_id, creator_id, scheduled_date, scheduled_time,
                    item_type, channel, caption_id, caption_text,
                    suggested_price, content_type_id, flyer_required, priority, status,
                    send_type_id, channel_id,
                    linked_post_url, expires_at, followup_delay_minutes,
                    media_type, campaign_goal, parent_item_id, is_follow_up
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        # Combine item warnings with certificate warnings
        all_warnings = warnings + cert_validation.get("warnings", [])

        result: dict[str, Any] = {
            "success": True,
            "template_id": template_id,
            "items_created": items_created,
            "week_start": week_start,
            "week_end": week_end
        }
        if all_warnings:
            result["warnings"] = all_warnings

        # Include certificate validation info if certificate was provided
        if validation_certificate:
            result["certificate_validation"] = {
                "valid": cert_validation["valid"],
                "signature": cert_validation.get("certificate_signature"),
                "quality_score": validation_certificate.get("quality_score"),
                "status": validation_certificate.get("validation_status")
            }
        else:
            result["certificate_validation"] = {
                "valid": True,  # Phase 1: No certificate is valid (with warning)
                "phase_1_warning": "No certificate provided - schedule saved without validation proof"
            }

        return result
    except sqlite3.Error as e:
        conn.rollback()
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()
