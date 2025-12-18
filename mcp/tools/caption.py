"""
EROS MCP Server Caption Tools

Tools for retrieving captions with performance and freshness scoring.
"""

import logging
from typing import Any, Optional

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import rows_to_list, resolve_creator_id
from mcp.utils.security import validate_creator_id, validate_key_input

logger = logging.getLogger("eros_db_server")


@mcp_tool(
    name="get_top_captions",
    description="Get top-performing captions for a creator with freshness scoring based on last usage. Optionally filter by send_type_key for compatible caption types.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "caption_type": {
                "type": "string",
                "description": "Optional filter by caption_type"
            },
            "content_type": {
                "type": "string",
                "description": "Optional filter by content type name"
            },
            "min_performance": {
                "type": "number",
                "description": "Minimum performance_score threshold (default 40)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of captions to return (default 20)"
            },
            "send_type_key": {
                "type": "string",
                "description": "Optional send type key to filter by compatible caption types and order by priority"
            }
        },
        "required": ["creator_id"]
    }
)
def get_top_captions(
    creator_id: str,
    caption_type: Optional[str] = None,
    content_type: Optional[str] = None,
    min_performance: float = 40.0,
    limit: int = 20,
    send_type_key: Optional[str] = None
) -> dict[str, Any]:
    """
    Get top-performing captions for a creator with freshness scoring.

    Freshness is calculated as: 100 - (days_since_last_use * 2), capped at 0-100.
    Captions not used recently get higher freshness scores.

    When send_type_key is provided, filters by compatible caption types from
    send_type_caption_requirements and orders by priority.

    Args:
        creator_id: The creator_id or page_name.
        caption_type: Optional filter by caption_type.
        content_type: Optional filter by content type name.
        min_performance: Minimum performance_score threshold (default 40).
        limit: Maximum number of captions to return (default 20).
        send_type_key: Optional send type to filter by compatible caption types.

    Returns:
        Dictionary containing:
            - captions: List of captions with performance and freshness scores
            - count: Number of captions returned
            - send_type_key: The send_type_key if provided (for reference)
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_top_captions: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if send_type_key is not None:
        is_valid, error_msg = validate_key_input(send_type_key, "send_type_key")
        if not is_valid:
            logger.warning(f"get_top_captions: Invalid send_type_key - {error_msg}")
            return {"error": f"Invalid send_type_key: {error_msg}"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # If send_type_key is provided, validate it exists
        send_type_id = None
        if send_type_key is not None:
            cursor = conn.execute(
                "SELECT send_type_id FROM send_types WHERE send_type_key = ?",
                (send_type_key,)
            )
            row = cursor.fetchone()
            if not row:
                return {"error": f"Send type not found: {send_type_key}"}
            send_type_id = row["send_type_id"]

        # Build query based on whether send_type_key is provided
        if send_type_id is not None:
            # Join with send_type_caption_requirements for priority ordering
            query = """
                SELECT
                    cb.caption_id,
                    cb.caption_text,
                    cb.schedulable_type,
                    cb.caption_type,
                    cb.content_type_id,
                    cb.tone,
                    cb.is_paid_page_only,
                    cb.performance_score,
                    ct.type_name AS content_type_name,
                    ccp.times_used,
                    ccp.total_earnings AS caption_total_earnings,
                    ccp.avg_earnings AS caption_avg_earnings,
                    ccp.avg_purchase_rate AS caption_avg_purchase_rate,
                    ccp.avg_view_rate AS caption_avg_view_rate,
                    ccp.performance_score AS creator_performance_score,
                    ccp.first_used_date,
                    ccp.last_used_date,
                    stcr.priority AS send_type_priority,
                    CASE
                        WHEN ccp.last_used_date IS NULL THEN 100
                        ELSE MAX(0, MIN(100, 100 - (julianday('now') - julianday(ccp.last_used_date)) * 2))
                    END AS freshness_score
                FROM caption_bank cb
                INNER JOIN send_type_caption_requirements stcr
                    ON cb.caption_type = stcr.caption_type
                    AND stcr.send_type_id = ?
                LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
                LEFT JOIN caption_creator_performance ccp
                    ON cb.caption_id = ccp.caption_id
                    AND ccp.creator_id = ?
                WHERE cb.is_active = 1
                AND cb.performance_score >= ?
                AND (cb.creator_id IS NULL OR cb.creator_id = ?)
            """
            params: list[Any] = [send_type_id, resolved_creator_id, min_performance, resolved_creator_id]
        else:
            query = """
                SELECT
                    cb.caption_id,
                    cb.caption_text,
                    cb.schedulable_type,
                    cb.caption_type,
                    cb.content_type_id,
                    cb.tone,
                    cb.is_paid_page_only,
                    cb.performance_score,
                    ct.type_name AS content_type_name,
                    ccp.times_used,
                    ccp.total_earnings AS caption_total_earnings,
                    ccp.avg_earnings AS caption_avg_earnings,
                    ccp.avg_purchase_rate AS caption_avg_purchase_rate,
                    ccp.avg_view_rate AS caption_avg_view_rate,
                    ccp.performance_score AS creator_performance_score,
                    ccp.first_used_date,
                    ccp.last_used_date,
                    CASE
                        WHEN ccp.last_used_date IS NULL THEN 100
                        ELSE MAX(0, MIN(100, 100 - (julianday('now') - julianday(ccp.last_used_date)) * 2))
                    END AS freshness_score
                FROM caption_bank cb
                LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
                LEFT JOIN caption_creator_performance ccp
                    ON cb.caption_id = ccp.caption_id
                    AND ccp.creator_id = ?
                WHERE cb.is_active = 1
                AND cb.performance_score >= ?
                AND (cb.creator_id IS NULL OR cb.creator_id = ?)
            """
            params = [resolved_creator_id, min_performance, resolved_creator_id]

        if caption_type is not None:
            query += " AND cb.caption_type = ?"
            params.append(caption_type)

        if content_type is not None:
            query += " AND ct.type_name = ?"
            params.append(content_type)

        # Order by priority (if send_type provided), then freshness, then performance
        if send_type_id is not None:
            query += """
                ORDER BY stcr.priority ASC, freshness_score DESC, cb.performance_score DESC
                LIMIT ?
            """
        else:
            query += """
                ORDER BY freshness_score DESC, cb.performance_score DESC
                LIMIT ?
            """
        params.append(limit)

        cursor = conn.execute(query, params)
        captions = rows_to_list(cursor.fetchall())

        result: dict[str, Any] = {
            "captions": captions,
            "count": len(captions)
        }
        if send_type_key is not None:
            result["send_type_key"] = send_type_key

        return result
    finally:
        conn.close()


@mcp_tool(
    name="get_send_type_captions",
    description="Get captions compatible with a specific send type for a creator. Orders by priority from send_type_caption_requirements, then by performance.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "send_type_key": {
                "type": "string",
                "description": "The send type key to find compatible captions for"
            },
            "min_freshness": {
                "type": "number",
                "description": "Minimum freshness score threshold (default 30)"
            },
            "min_performance": {
                "type": "number",
                "description": "Minimum performance_score threshold (default 40)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of captions to return (default 10)"
            }
        },
        "required": ["creator_id", "send_type_key"]
    }
)
def get_send_type_captions(
    creator_id: str,
    send_type_key: str,
    min_freshness: float = 30.0,
    min_performance: float = 40.0,
    limit: int = 10
) -> dict[str, Any]:
    """
    Get captions compatible with a specific send type for a creator.

    Joins caption_bank with send_type_caption_requirements to find captions
    that match the send type's caption requirements. Orders by priority (from
    mapping table) first, then by performance score.

    Freshness is calculated as: 100 - (days_since_last_use * 2), capped at 0-100.

    Args:
        creator_id: The creator_id or page_name.
        send_type_key: The send type key to find compatible captions for.
        min_freshness: Minimum freshness score threshold (default 30).
        min_performance: Minimum performance_score threshold (default 40).
        limit: Maximum number of captions to return (default 10).

    Returns:
        Dictionary containing:
            - captions: List of captions with performance, freshness scores, and priority
            - count: Number of captions returned
            - send_type_key: The send type key for reference
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_send_type_captions: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    is_valid, error_msg = validate_key_input(send_type_key, "send_type_key")
    if not is_valid:
        logger.warning(f"get_send_type_captions: Invalid send_type_key - {error_msg}")
        return {"error": f"Invalid send_type_key: {error_msg}"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Validate send_type_key exists
        cursor = conn.execute(
            "SELECT send_type_id FROM send_types WHERE send_type_key = ?",
            (send_type_key,)
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"Send type not found: {send_type_key}"}
        send_type_id = row["send_type_id"]

        # Query captions joined with send_type_caption_requirements
        query = """
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.schedulable_type,
                cb.caption_type,
                cb.content_type_id,
                cb.tone,
                cb.is_paid_page_only,
                cb.performance_score,
                ct.type_name AS content_type_name,
                ccp.times_used,
                ccp.total_earnings AS caption_total_earnings,
                ccp.avg_earnings AS caption_avg_earnings,
                ccp.avg_purchase_rate AS caption_avg_purchase_rate,
                ccp.avg_view_rate AS caption_avg_view_rate,
                ccp.performance_score AS creator_performance_score,
                ccp.first_used_date,
                ccp.last_used_date,
                stcr.priority AS send_type_priority,
                CASE
                    WHEN ccp.last_used_date IS NULL THEN 100
                    ELSE MAX(0, MIN(100, 100 - (julianday('now') - julianday(ccp.last_used_date)) * 2))
                END AS freshness_score
            FROM caption_bank cb
            INNER JOIN send_type_caption_requirements stcr
                ON cb.caption_type = stcr.caption_type
                AND stcr.send_type_id = ?
            LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
            WHERE cb.is_active = 1
            AND cb.performance_score >= ?
            AND (cb.creator_id IS NULL OR cb.creator_id = ?)
            AND (
                CASE
                    WHEN ccp.last_used_date IS NULL THEN 100
                    ELSE MAX(0, MIN(100, 100 - (julianday('now') - julianday(ccp.last_used_date)) * 2))
                END
            ) >= ?
            ORDER BY stcr.priority ASC, cb.performance_score DESC
            LIMIT ?
        """
        params: list[Any] = [
            send_type_id,
            resolved_creator_id,
            min_performance,
            resolved_creator_id,
            min_freshness,
            limit
        ]

        cursor = conn.execute(query, params)
        captions = rows_to_list(cursor.fetchall())

        return {
            "captions": captions,
            "count": len(captions),
            "send_type_key": send_type_key
        }
    finally:
        conn.close()
