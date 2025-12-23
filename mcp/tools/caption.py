"""
EROS MCP Server Caption Tools

Tools for retrieving captions with performance and freshness scoring.

Includes:
- get_top_captions: Performance-ranked captions with freshness scoring
- get_send_type_captions: Captions compatible with specific send types
- get_content_type_earnings_ranking: Content types ranked by total earnings (PPV-first selection)
- get_top_captions_by_earnings: Top captions for a content type ranked by earnings
- validate_caption_structure: Caption validation with anti-patterization checks

Version: 3.0.0
"""

import difflib
import logging
import re
import sqlite3
from datetime import datetime
from typing import Any, Optional

# Optional emoji library for enhanced emoji detection
try:
    import emoji
    EMOJI_AVAILABLE = True
except ImportError:
    EMOJI_AVAILABLE = False

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import rows_to_list, resolve_creator_id
from mcp.utils.security import validate_creator_id, validate_key_input, validate_string_length

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
                "type": "integer",
                "description": "Maximum performance_tier to include (1=ELITE, 2=PROVEN, 3=STANDARD, 4=UNPROVEN). Default 3 includes all but UNPROVEN."
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
    min_performance: int = 3,
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
        min_performance: Maximum performance_tier to include (1=ELITE, 2=PROVEN,
            3=STANDARD, 4=UNPROVEN). Default 3 includes tiers 1-3.
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
        # CRITICAL: vault_matrix INNER JOIN filters to only allowed content types
        # CRITICAL: top_content_types LEFT JOIN filters out AVOID tier content types
        if send_type_id is not None:
            # Join with send_type_caption_requirements for priority ordering
            query = """
                SELECT
                    cb.caption_id,
                    cb.caption_text,
                    cb.schedulable_type,
                    cb.caption_type,
                    cb.content_type_id,
                    cb.is_paid_page_only,
                    cb.performance_tier,
                    cb.classification_confidence,
                    cb.total_earnings AS cb_total_earnings,
                    cb.total_sends AS cb_total_sends,
                    cb.avg_view_rate AS cb_avg_view_rate,
                    cb.avg_purchase_rate AS cb_avg_purchase_rate,
                    cb.suggested_price,
                    cb.char_length,
                    ct.type_name AS content_type_name,
                    vm.has_content AS vault_allowed,
                    tct.performance_tier AS content_performance_tier,
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
                INNER JOIN vault_matrix vm
                    ON cb.content_type_id = vm.content_type_id
                    AND vm.creator_id = ?
                    AND vm.has_content = 1
                INNER JOIN send_type_caption_requirements stcr
                    ON cb.caption_type = stcr.caption_type
                    AND stcr.send_type_id = ?
                LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
                LEFT JOIN top_content_types tct
                    ON ct.type_name = tct.content_type
                    AND tct.creator_id = ?
                    AND tct.analysis_date = (
                        SELECT MAX(analysis_date)
                        FROM top_content_types
                        WHERE creator_id = ?
                    )
                LEFT JOIN caption_creator_performance ccp
                    ON cb.caption_id = ccp.caption_id
                    AND ccp.creator_id = ?
                WHERE cb.is_active = 1
                AND cb.performance_tier <= ?
                AND (tct.performance_tier IS NULL OR tct.performance_tier != 'AVOID')
            """
            params: list[Any] = [resolved_creator_id, send_type_id, resolved_creator_id, resolved_creator_id, resolved_creator_id, min_performance, resolved_creator_id]
        else:
            query = """
                SELECT
                    cb.caption_id,
                    cb.caption_text,
                    cb.schedulable_type,
                    cb.caption_type,
                    cb.content_type_id,
                    cb.is_paid_page_only,
                    cb.performance_tier,
                    cb.classification_confidence,
                    cb.total_earnings AS cb_total_earnings,
                    cb.total_sends AS cb_total_sends,
                    cb.avg_view_rate AS cb_avg_view_rate,
                    cb.avg_purchase_rate AS cb_avg_purchase_rate,
                    cb.suggested_price,
                    cb.char_length,
                    ct.type_name AS content_type_name,
                    vm.has_content AS vault_allowed,
                    tct.performance_tier AS content_performance_tier,
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
                INNER JOIN vault_matrix vm
                    ON cb.content_type_id = vm.content_type_id
                    AND vm.creator_id = ?
                    AND vm.has_content = 1
                LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
                LEFT JOIN top_content_types tct
                    ON ct.type_name = tct.content_type
                    AND tct.creator_id = ?
                    AND tct.analysis_date = (
                        SELECT MAX(analysis_date)
                        FROM top_content_types
                        WHERE creator_id = ?
                    )
                LEFT JOIN caption_creator_performance ccp
                    ON cb.caption_id = ccp.caption_id
                    AND ccp.creator_id = ?
                WHERE cb.is_active = 1
                AND cb.performance_tier <= ?
                AND (tct.performance_tier IS NULL OR tct.performance_tier != 'AVOID')
            """
            params = [resolved_creator_id, resolved_creator_id, resolved_creator_id, resolved_creator_id, min_performance]

        if caption_type is not None:
            query += " AND cb.caption_type = ?"
            params.append(caption_type)

        if content_type is not None:
            query += " AND ct.type_name = ?"
            params.append(content_type)

        # Order by priority (if send_type provided), then freshness, then performance tier (lower is better)
        if send_type_id is not None:
            query += """
                ORDER BY stcr.priority ASC, freshness_score DESC, cb.performance_tier ASC
                LIMIT ?
            """
        else:
            query += """
                ORDER BY freshness_score DESC, cb.performance_tier ASC
                LIMIT ?
            """
        params.append(limit)

        cursor = conn.execute(query, params)
        captions = rows_to_list(cursor.fetchall())

        # Get AVOID tier filtering metadata for audit trail
        avoid_cursor = conn.execute("""
            SELECT content_type, analysis_date
            FROM top_content_types
            WHERE creator_id = ? AND performance_tier = 'AVOID'
            AND analysis_date = (SELECT MAX(analysis_date) FROM top_content_types WHERE creator_id = ?)
        """, (resolved_creator_id, resolved_creator_id))
        avoid_types = [row["content_type"] for row in avoid_cursor.fetchall()]

        result: dict[str, Any] = {
            "captions": captions,
            "count": len(captions),
            "filters_applied": {
                "vault_compliance": True,
                "avoid_tier_exclusion": True,
                "avoid_types_excluded": avoid_types
            }
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
                "type": "integer",
                "description": "Maximum performance_tier to include (1=ELITE, 2=PROVEN, 3=STANDARD, 4=UNPROVEN). Default 3 includes all but UNPROVEN."
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
    min_performance: int = 3,
    limit: int = 10
) -> dict[str, Any]:
    """
    Get captions compatible with a specific send type for a creator.

    Joins caption_bank with send_type_caption_requirements to find captions
    that match the send type's caption requirements. Orders by priority (from
    mapping table) first, then by performance tier.

    Freshness is calculated as: 100 - (days_since_last_use * 2), capped at 0-100.

    Args:
        creator_id: The creator_id or page_name.
        send_type_key: The send type key to find compatible captions for.
        min_freshness: Minimum freshness score threshold (default 30).
        min_performance: Maximum performance_tier to include (1=ELITE, 2=PROVEN,
            3=STANDARD, 4=UNPROVEN). Default 3 includes tiers 1-3.
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
        # CRITICAL: vault_matrix INNER JOIN filters to only allowed content types
        # CRITICAL: top_content_types LEFT JOIN filters out AVOID tier content types
        query = """
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.schedulable_type,
                cb.caption_type,
                cb.content_type_id,
                cb.is_paid_page_only,
                cb.performance_tier,
                cb.classification_confidence,
                cb.total_earnings AS cb_total_earnings,
                cb.total_sends AS cb_total_sends,
                cb.avg_view_rate AS cb_avg_view_rate,
                cb.avg_purchase_rate AS cb_avg_purchase_rate,
                cb.suggested_price,
                cb.char_length,
                ct.type_name AS content_type_name,
                vm.has_content AS vault_allowed,
                tct.performance_tier AS content_performance_tier,
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
            INNER JOIN vault_matrix vm
                ON cb.content_type_id = vm.content_type_id
                AND vm.creator_id = ?
                AND vm.has_content = 1
            INNER JOIN send_type_caption_requirements stcr
                ON cb.caption_type = stcr.caption_type
                AND stcr.send_type_id = ?
            LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
            LEFT JOIN top_content_types tct
                ON ct.type_name = tct.content_type
                AND tct.creator_id = ?
                AND tct.analysis_date = (
                    SELECT MAX(analysis_date)
                    FROM top_content_types
                    WHERE creator_id = ?
                )
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
            WHERE cb.is_active = 1
            AND cb.performance_tier <= ?
            AND (tct.performance_tier IS NULL OR tct.performance_tier != 'AVOID')
            AND (
                CASE
                    WHEN ccp.last_used_date IS NULL THEN 100
                    ELSE MAX(0, MIN(100, 100 - (julianday('now') - julianday(ccp.last_used_date)) * 2))
                END
            ) >= ?
            ORDER BY stcr.priority ASC, cb.performance_tier ASC
            LIMIT ?
        """
        params: list[Any] = [
            resolved_creator_id,  # For vault_matrix join
            send_type_id,         # For send_type_caption_requirements join
            resolved_creator_id,  # For top_content_types join
            resolved_creator_id,  # For top_content_types subquery
            resolved_creator_id,  # For caption_creator_performance join
            min_performance,
            min_freshness,
            limit
        ]

        cursor = conn.execute(query, params)
        captions = rows_to_list(cursor.fetchall())

        # Get AVOID tier filtering metadata for audit trail
        avoid_cursor = conn.execute("""
            SELECT content_type, analysis_date
            FROM top_content_types
            WHERE creator_id = ? AND performance_tier = 'AVOID'
            AND analysis_date = (SELECT MAX(analysis_date) FROM top_content_types WHERE creator_id = ?)
        """, (resolved_creator_id, resolved_creator_id))
        avoid_types = [row["content_type"] for row in avoid_cursor.fetchall()]

        return {
            "captions": captions,
            "count": len(captions),
            "send_type_key": send_type_key,
            "filters_applied": {
                "vault_compliance": True,
                "avoid_tier_exclusion": True,
                "avoid_types_excluded": avoid_types
            }
        }
    finally:
        conn.close()


@mcp_tool(
    name="get_content_type_earnings_ranking",
    description="Get content types ranked by total earnings for a creator, filtered by vault availability and excluding AVOID tier. Used for PPV-first caption selection.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "min_sends": {
                "type": "integer",
                "description": "Minimum send count to include content type (default 5)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of content types to return (default 15)"
            }
        },
        "required": ["creator_id"]
    }
)
def get_content_type_earnings_ranking(
    creator_id: str,
    min_sends: int = 5,
    limit: int = 15
) -> dict[str, Any]:
    """
    Get content types ranked by total earnings for a creator.

    Filters by:
    - Vault matrix: Only content types the creator has available
    - AVOID tier: Excludes content types in AVOID performance tier
    - Minimum sends: Excludes content types with insufficient data

    Used for PPV-first caption selection to prioritize highest-earning content types.

    Args:
        creator_id: The creator_id or page_name.
        min_sends: Minimum send count threshold to include (default 5).
        limit: Maximum number of content types to return (default 15).

    Returns:
        Dictionary containing:
            - content_types: List of content types with earnings data
            - count: Number of content types returned
            - filters_applied: Filter metadata for audit trail
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_content_type_earnings_ranking: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Query content types ranked by total earnings from top_content_types
        # CRITICAL: Filter by vault_matrix (INNER JOIN) and exclude AVOID tier
        query = """
            SELECT
                tct.content_type,
                tct.rank AS original_rank,
                tct.send_count,
                tct.total_earnings,
                tct.avg_earnings,
                tct.avg_purchase_rate,
                tct.avg_rps,
                tct.performance_tier,
                tct.confidence_score,
                tct.recommendation,
                ct.content_type_id,
                ct.type_category,
                ct.is_explicit,
                vm.quantity_available AS vault_quantity,
                vm.quality_rating AS vault_quality,
                ROW_NUMBER() OVER (ORDER BY tct.total_earnings DESC) AS earnings_rank
            FROM top_content_types tct
            INNER JOIN content_types ct ON tct.content_type = ct.type_name
            INNER JOIN vault_matrix vm
                ON ct.content_type_id = vm.content_type_id
                AND vm.creator_id = ?
                AND vm.has_content = 1
            WHERE tct.creator_id = ?
            AND tct.analysis_date = (
                SELECT MAX(analysis_date)
                FROM top_content_types
                WHERE creator_id = ?
            )
            AND tct.send_count >= ?
            AND (tct.performance_tier IS NULL OR tct.performance_tier != 'AVOID')
            ORDER BY tct.total_earnings DESC
            LIMIT ?
        """
        params: list[Any] = [
            resolved_creator_id,  # For vault_matrix join
            resolved_creator_id,  # For top_content_types WHERE
            resolved_creator_id,  # For analysis_date subquery
            min_sends,
            limit
        ]

        cursor = conn.execute(query, params)
        content_types = rows_to_list(cursor.fetchall())

        # Get AVOID tier filtering metadata for audit trail
        avoid_cursor = conn.execute("""
            SELECT content_type, total_earnings, send_count
            FROM top_content_types
            WHERE creator_id = ? AND performance_tier = 'AVOID'
            AND analysis_date = (SELECT MAX(analysis_date) FROM top_content_types WHERE creator_id = ?)
        """, (resolved_creator_id, resolved_creator_id))
        avoid_types = [
            {"content_type": row["content_type"], "total_earnings": row["total_earnings"], "send_count": row["send_count"]}
            for row in avoid_cursor.fetchall()
        ]

        # Get vault compliance metadata
        vault_cursor = conn.execute("""
            SELECT ct.type_name AS content_type
            FROM content_types ct
            WHERE ct.content_type_id NOT IN (
                SELECT vm.content_type_id
                FROM vault_matrix vm
                WHERE vm.creator_id = ? AND vm.has_content = 1
            )
        """, (resolved_creator_id,))
        non_vault_types = [row["content_type"] for row in vault_cursor.fetchall()]

        return {
            "content_types": content_types,
            "count": len(content_types),
            "creator_id": resolved_creator_id,
            "filters_applied": {
                "min_sends": min_sends,
                "vault_compliance": True,
                "avoid_tier_exclusion": True,
                "avoid_types_excluded": avoid_types,
                "non_vault_types_excluded": non_vault_types
            }
        }
    finally:
        conn.close()


@mcp_tool(
    name="get_top_captions_by_earnings",
    description="Get top-performing captions for a specific content type ranked by total earnings. Supports exclude_caption_ids for rotation enforcement.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "content_type": {
                "type": "string",
                "description": "The content type to filter by (e.g., 'solo', 'b/g', 'lingerie')"
            },
            "send_type_key": {
                "type": "string",
                "description": "Optional send type key to filter by compatible caption types"
            },
            "exclude_caption_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of caption IDs to exclude (for rotation enforcement)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of captions to return (default 5)"
            },
            "min_freshness": {
                "type": "number",
                "description": "Minimum freshness score threshold (default 30.0)"
            },
            "min_performance": {
                "type": "integer",
                "description": "Maximum performance_tier to include (1=ELITE, 2=PROVEN, 3=STANDARD, 4=UNPROVEN). Default 3 includes all but UNPROVEN."
            }
        },
        "required": ["creator_id", "content_type"]
    }
)
def get_top_captions_by_earnings(
    creator_id: str,
    content_type: str,
    send_type_key: Optional[str] = None,
    exclude_caption_ids: Optional[list[int]] = None,
    limit: int = 5,
    min_freshness: float = 30.0,
    min_performance: int = 3
) -> dict[str, Any]:
    """
    Get top-performing captions for a specific content type ranked by total earnings.

    Unlike get_top_captions which prioritizes freshness, this function prioritizes
    EARNINGS HISTORY for PPV-first selection strategy. Supports exclude_caption_ids
    for content type rotation enforcement.

    Filters by:
    - Vault matrix: Only captions with vault-available content types
    - AVOID tier: Excludes captions with AVOID performance tier content types
    - Performance tier: Only includes captions at or above tier threshold
    - Content type: Required filter for specific content type
    - Send type: Optional filter by compatible caption types
    - Exclusion list: Optional exclude_caption_ids for rotation

    Args:
        creator_id: The creator_id or page_name.
        content_type: The content type to filter by (required).
        send_type_key: Optional send type key to filter by compatible caption types.
        exclude_caption_ids: List of caption IDs to exclude (for rotation).
        limit: Maximum number of captions to return (default 5).
        min_freshness: Minimum freshness score threshold (default 30.0).
        min_performance: Maximum performance_tier to include (1=ELITE, 2=PROVEN,
            3=STANDARD, 4=UNPROVEN). Default 3 includes tiers 1-3.

    Returns:
        Dictionary containing:
            - captions: List of captions with full metadata for LLM selection
            - count: Number of captions returned
            - content_type: The content type filter applied
            - filters_applied: Filter metadata for audit trail
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_top_captions_by_earnings: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if send_type_key is not None:
        is_valid, error_msg = validate_key_input(send_type_key, "send_type_key")
        if not is_valid:
            logger.warning(f"get_top_captions_by_earnings: Invalid send_type_key - {error_msg}")
            return {"error": f"Invalid send_type_key: {error_msg}"}

    # Validate content_type length (security)
    is_valid, error_msg = validate_string_length(content_type, 100, "content_type")
    if not is_valid:
        logger.warning(f"get_top_captions_by_earnings: Invalid content_type - {error_msg}")
        return {"error": f"Invalid content_type: {error_msg}"}

    # Validate exclude_caption_ids if provided (security + performance)
    if exclude_caption_ids is not None:
        MAX_EXCLUDE_IDS = 500  # Prevent DoS with excessive exclusion list
        if len(exclude_caption_ids) > MAX_EXCLUDE_IDS:
            logger.warning(f"get_top_captions_by_earnings: exclude_caption_ids exceeds limit of {MAX_EXCLUDE_IDS}")
            return {"error": f"exclude_caption_ids exceeds maximum of {MAX_EXCLUDE_IDS} items"}

        for idx, cap_id in enumerate(exclude_caption_ids):
            if not isinstance(cap_id, int) or cap_id <= 0:
                logger.warning(f"get_top_captions_by_earnings: Invalid caption ID at index {idx}")
                return {"error": f"exclude_caption_ids[{idx}] must be a positive integer"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Validate content_type exists
        ct_cursor = conn.execute(
            "SELECT content_type_id FROM content_types WHERE type_name = ?",
            (content_type,)
        )
        ct_row = ct_cursor.fetchone()
        if not ct_row:
            return {"error": f"Content type not found: {content_type}"}
        content_type_id = ct_row["content_type_id"]

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

        # Build the base query
        # CRITICAL: vault_matrix INNER JOIN filters to only allowed content types
        # CRITICAL: top_content_types LEFT JOIN filters out AVOID tier
        # PRIMARY SORT: total_earnings DESC (not freshness)
        base_select = """
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.schedulable_type,
                cb.caption_type,
                cb.content_type_id,
                cb.is_paid_page_only,
                cb.performance_tier,
                cb.classification_confidence,
                cb.total_earnings AS cb_total_earnings,
                cb.total_sends AS cb_total_sends,
                cb.avg_view_rate AS cb_avg_view_rate,
                cb.avg_purchase_rate AS cb_avg_purchase_rate,
                cb.suggested_price,
                cb.char_length,
                ct.type_name AS content_type_name,
                vm.has_content AS vault_allowed,
                vm.quantity_available AS vault_quantity,
                tct.performance_tier AS content_performance_tier,
                tct.total_earnings AS content_type_total_earnings,
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
            INNER JOIN vault_matrix vm
                ON cb.content_type_id = vm.content_type_id
                AND vm.creator_id = ?
                AND vm.has_content = 1
            LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
            LEFT JOIN top_content_types tct
                ON ct.type_name = tct.content_type
                AND tct.creator_id = ?
                AND tct.analysis_date = (
                    SELECT MAX(analysis_date)
                    FROM top_content_types
                    WHERE creator_id = ?
                )
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
        """

        # Add send_type join if provided
        if send_type_id is not None:
            base_select += """
            INNER JOIN send_type_caption_requirements stcr
                ON cb.caption_type = stcr.caption_type
                AND stcr.send_type_id = ?
            """

        # Build WHERE clause
        where_clause = """
            WHERE cb.is_active = 1
            AND cb.content_type_id = ?
            AND cb.performance_tier <= ?
            AND (tct.performance_tier IS NULL OR tct.performance_tier != 'AVOID')
            AND (
                CASE
                    WHEN ccp.last_used_date IS NULL THEN 100
                    ELSE MAX(0, MIN(100, 100 - (julianday('now') - julianday(ccp.last_used_date)) * 2))
                END
            ) >= ?
        """

        # Handle exclude_caption_ids
        exclude_clause = ""
        if exclude_caption_ids and len(exclude_caption_ids) > 0:
            placeholders = ",".join(["?" for _ in exclude_caption_ids])
            exclude_clause = f" AND cb.caption_id NOT IN ({placeholders})"

        # Order by EARNINGS (primary), then freshness (secondary), then performance tier (tertiary, lower is better)
        order_clause = """
            ORDER BY
                COALESCE(ccp.total_earnings, 0) DESC,
                freshness_score DESC,
                cb.performance_tier ASC
            LIMIT ?
        """

        # Combine query parts
        query = base_select + where_clause + exclude_clause + order_clause

        # Build params list
        params: list[Any] = [
            resolved_creator_id,  # For vault_matrix join
            resolved_creator_id,  # For top_content_types join
            resolved_creator_id,  # For top_content_types subquery
            resolved_creator_id,  # For caption_creator_performance join
        ]

        if send_type_id is not None:
            params.append(send_type_id)  # For send_type_caption_requirements join

        params.extend([
            content_type_id,      # For content_type_id filter
            min_performance,      # For performance_tier filter
            min_freshness,        # For freshness threshold
        ])

        if exclude_caption_ids and len(exclude_caption_ids) > 0:
            params.extend(exclude_caption_ids)

        params.append(limit)

        cursor = conn.execute(query, params)
        captions = rows_to_list(cursor.fetchall())

        # Get AVOID tier filtering metadata for audit trail
        avoid_cursor = conn.execute("""
            SELECT content_type, analysis_date
            FROM top_content_types
            WHERE creator_id = ? AND performance_tier = 'AVOID'
            AND analysis_date = (SELECT MAX(analysis_date) FROM top_content_types WHERE creator_id = ?)
        """, (resolved_creator_id, resolved_creator_id))
        avoid_types = [row["content_type"] for row in avoid_cursor.fetchall()]

        result: dict[str, Any] = {
            "captions": captions,
            "count": len(captions),
            "content_type": content_type,
            "creator_id": resolved_creator_id,
            "selection_method": "earnings_ranked_llm_curated",
            "filters_applied": {
                "vault_compliance": True,
                "avoid_tier_exclusion": True,
                "avoid_types_excluded": avoid_types,
                "min_freshness": min_freshness,
                "excluded_caption_ids": exclude_caption_ids or []
            }
        }

        if send_type_key is not None:
            result["send_type_key"] = send_type_key

        return result
    finally:
        conn.close()


# =============================================================================
# Caption Structure Validation Tool
# =============================================================================

# Validation thresholds (defined as constants for maintainability)
EMOJI_RATIO_WARNING_THRESHOLD = 0.15
EMOJI_RATIO_REJECTION_THRESHOLD = 0.25
SIMILARITY_REJECTION_THRESHOLD = 0.60
SIMILARITY_WARNING_THRESHOLD = 0.45
MAX_CONSECUTIVE_SAME_COLOR_EMOJI = 3
MAX_AI_PATTERNS_BEFORE_WARNING = 3
MAX_CAPTION_LENGTH = 5000
MAX_SCHEDULED_CAPTIONS = 100
MAX_SCHEDULED_CAPTION_LENGTH = 5000
PPV_MISSING_ELEMENT_PENALTY = 6.25

# Optimal character length ranges by send_type_key (from implementation plan)
OPTIMAL_LENGTH_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "ppv_unlock": {"optimal": (250, 449), "acceptable": (150, 600)},
    "ppv_wall": {"optimal": (200, 400), "acceptable": (100, 550)},
    "bundle": {"optimal": (300, 500), "acceptable": (200, 650)},
    "flash_bundle": {"optimal": (200, 400), "acceptable": (100, 550)},
    "bump_normal": {"optimal": (100, 250), "acceptable": (50, 350)},
    "bump_descriptive": {"optimal": (150, 300), "acceptable": (75, 400)},
    "bump_text_only": {"optimal": (80, 200), "acceptable": (40, 300)},
    "bump_flyer": {"optimal": (50, 150), "acceptable": (25, 250)},
    "tip_goal": {"optimal": (150, 350), "acceptable": (75, 450)},
    "game_post": {"optimal": (100, 300), "acceptable": (50, 400)},
    "first_to_tip": {"optimal": (100, 250), "acceptable": (50, 350)},
    "link_drop": {"optimal": (100, 250), "acceptable": (50, 350)},
    "wall_link_drop": {"optimal": (100, 250), "acceptable": (50, 350)},
    "dm_farm": {"optimal": (50, 150), "acceptable": (25, 250)},
    "like_farm": {"optimal": (50, 150), "acceptable": (25, 250)},
    "live_promo": {"optimal": (100, 250), "acceptable": (50, 350)},
    "renew_on_post": {"optimal": (150, 350), "acceptable": (75, 450)},
    "renew_on_message": {"optimal": (150, 350), "acceptable": (75, 450)},
    "ppv_followup": {"optimal": (100, 250), "acceptable": (50, 350)},
    "expired_winback": {"optimal": (200, 400), "acceptable": (100, 550)},
    "vip_program": {"optimal": (250, 500), "acceptable": (150, 650)},
    "snapchat_bundle": {"optimal": (200, 400), "acceptable": (100, 550)},
}

# Default range for unknown send types
DEFAULT_LENGTH_RANGE: dict[str, tuple[int, int]] = {
    "optimal": (150, 400),
    "acceptable": (50, 600)
}


# Emoji color classifications for spam detection
EMOJI_COLOR_GROUPS: dict[str, list[str]] = {
    "yellow_faces": [
        "grinning", "grin", "joy", "smiley", "smile", "sweat_smile", "laughing",
        "wink", "blush", "yum", "heart_eyes", "sunglasses", "smirk", "relaxed",
        "stuck_out_tongue", "stuck_out_tongue_winking_eye", "stuck_out_tongue_closed_eyes",
        "disappointed", "worried", "angry", "rage", "cry", "sob", "scream",
        "flushed", "tired_face", "sleepy", "dizzy_face", "zipper_mouth_face",
        "money_mouth_face", "nerd_face", "thinking", "face_with_raised_eyebrow",
        "star_struck", "zany_face", "shushing_face", "face_with_hand_over_mouth",
        "face_vomiting", "hot_face", "cold_face", "woozy_face", "pleading_face"
    ],
    "red_hearts": [
        "heart", "hearts", "sparkling_heart", "heartpulse", "heartbeat",
        "revolving_hearts", "two_hearts", "heart_decoration", "heavy_heart_exclamation"
    ],
    "fire": ["fire"],
    "stars": ["star", "star2", "stars", "sparkles", "dizzy"],
    "peach_eggplant": ["peach", "eggplant"],
}


def _extract_emojis(text: str) -> list[str]:
    """
    Extract all emojis from text.

    Args:
        text: The text to extract emojis from.

    Returns:
        List of emoji characters found in the text.
    """
    if not EMOJI_AVAILABLE:
        # Fallback regex for common emoji ranges
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"  # chess symbols
            "\U0001FA70-\U0001FAFF"  # symbols & pictographs extended-A
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.findall(text)

    return [char for char in text if emoji.is_emoji(char)]


def _get_emoji_color_group(emoji_char: str) -> Optional[str]:
    """
    Get the color group for an emoji character.

    Args:
        emoji_char: Single emoji character.

    Returns:
        Color group name or None if not classified.
    """
    if not EMOJI_AVAILABLE:
        return None

    try:
        emoji_name = emoji.demojize(emoji_char).strip(":").lower().replace("_", " ")
        # Check against color groups
        for group_name, group_emojis in EMOJI_COLOR_GROUPS.items():
            for group_emoji in group_emojis:
                if group_emoji.replace("_", " ") in emoji_name:
                    return group_name
        return None
    except Exception:
        return None


def _check_emoji_blending(caption_text: str) -> dict[str, Any]:
    """
    Check for emoji color patterns and spam detection.

    Detects consecutive same-color emojis and calculates emoji-to-text ratio
    to identify spammy or AI-generated patterns.

    Args:
        caption_text: The caption text to analyze.

    Returns:
        Dictionary containing:
            - emoji_count: Total number of emojis found
            - consecutive_same_color: Max consecutive same-color emojis
            - emoji_to_text_ratio: Ratio of emojis to total text length
            - compliant: Boolean indicating if emoji usage is compliant
            - color_groups_found: List of color groups detected
            - issues: List of specific issues found
    """
    emojis = _extract_emojis(caption_text)
    emoji_count = len(emojis)
    text_length = len(caption_text.strip())

    # Calculate emoji-to-text ratio
    emoji_to_text_ratio = emoji_count / max(text_length, 1)

    # Track consecutive same-color emojis
    max_consecutive = 0
    current_consecutive = 1
    last_color_group: Optional[str] = None
    color_groups_found: set[str] = set()

    for emoji_char in emojis:
        color_group = _get_emoji_color_group(emoji_char)
        if color_group:
            color_groups_found.add(color_group)

            if color_group == last_color_group:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
                last_color_group = color_group
        else:
            current_consecutive = 1
            last_color_group = None

    # Determine compliance
    issues: list[str] = []
    compliant = True

    # HARD RULE: 3+ consecutive same-color emojis = rejection
    if max_consecutive >= MAX_CONSECUTIVE_SAME_COLOR_EMOJI:
        compliant = False
        issues.append(f"Consecutive same-color emojis detected: {max_consecutive}")

    # WARNING: High emoji ratio (>0.15 = roughly 1 emoji per 6-7 chars)
    if emoji_to_text_ratio > EMOJI_RATIO_WARNING_THRESHOLD:
        issues.append(f"High emoji-to-text ratio: {emoji_to_text_ratio:.2f}")
        # Only reject if extremely high (>0.25)
        if emoji_to_text_ratio > EMOJI_RATIO_REJECTION_THRESHOLD:
            compliant = False

    return {
        "emoji_count": emoji_count,
        "consecutive_same_color": max_consecutive,
        "emoji_to_text_ratio": round(emoji_to_text_ratio, 4),
        "compliant": compliant,
        "color_groups_found": list(color_groups_found),
        "issues": issues
    }


def _check_ppv_structure(caption_text: str, creator_id: str) -> dict[str, Any]:
    """
    Check for four-element PPV structure using pattern detection.

    PPV captions should contain four elements:
    1. Clickbait opener - Attention-grabbing opening (questions, exclamations)
    2. Make special - Personal/exclusive angle
    3. Value proposition - What the viewer gets
    4. Call to action - Clear purchase instruction

    Args:
        caption_text: The caption text to analyze.
        creator_id: The creator_id for context.

    Returns:
        Dictionary containing:
            - elements_present: Number of elements detected (0-4)
            - element_details: Dict with each element and detection status
            - missing_elements: List of missing element names
            - structure_complete: Boolean if all 4 elements present
            - structure_score: Score 0-100 based on structure completeness
    """
    text_lower = caption_text.lower()

    # Element detection patterns (pattern-based, not hardcoded keywords)
    elements = {
        "clickbait_opener": False,
        "make_special": False,
        "value_proposition": False,
        "call_to_action": False
    }
    element_details: dict[str, dict[str, Any]] = {}

    # 1. Clickbait opener - Questions, exclamations, "what if", "imagine", etc.
    opener_patterns = [
        r"^[!?]",  # Starts with exclamation/question
        r"^(omg|oh my|wow|guess what|what if|imagine|pov|breaking)",
        r"^.{0,30}[!?]",  # Short opener with punctuation
        r"(wanna|want to|ready to|can you|would you|do you|did you)",
        r"(secret|exclusive|private|special|just for|only for)",
        r"(never before|first time|finally|just dropped)",
    ]
    for pattern in opener_patterns:
        if re.search(pattern, text_lower):
            elements["clickbait_opener"] = True
            element_details["clickbait_opener"] = {"detected": True, "pattern": pattern}
            break
    if not elements["clickbait_opener"]:
        element_details["clickbait_opener"] = {"detected": False}

    # 2. Make special - Personal connection, exclusivity, intimacy
    special_patterns = [
        r"(just for you|only you|you're the|you are the)",
        r"(my favorite|i love|i want you|i need you)",
        r"(personal|intimate|private|exclusive|vip)",
        r"(between us|our secret|just us|only us)",
        r"(specially|especially|particularly) for",
        r"(miss you|thinking of you|been waiting)",
    ]
    for pattern in special_patterns:
        if re.search(pattern, text_lower):
            elements["make_special"] = True
            element_details["make_special"] = {"detected": True, "pattern": pattern}
            break
    if not elements["make_special"]:
        element_details["make_special"] = {"detected": False}

    # 3. Value proposition - What they get, duration, quality descriptors
    value_patterns = [
        r"(\d+\s*(min|minute|sec|second|hour|vid|video|pic|photo|image))",
        r"(full (video|length|clip)|hd|4k|uncensored|uncut)",
        r"(you (get|see|watch|receive)|includes|featuring|with)",
        r"(never (seen|shown|posted)|exclusive (content|video|clip))",
        r"(orgasm|climax|cum|explicit|xxx|x-rated)",
        r"(shower|bath|bed|outdoor|public|pov)",
    ]
    for pattern in value_patterns:
        if re.search(pattern, text_lower):
            elements["value_proposition"] = True
            element_details["value_proposition"] = {"detected": True, "pattern": pattern}
            break
    if not elements["value_proposition"]:
        element_details["value_proposition"] = {"detected": False}

    # 4. Call to action - Unlock, purchase, tip instructions
    cta_patterns = [
        r"(unlock|tip|purchase|buy|get it|grab it)",
        r"(send|dm|message) (me|to unlock)",
        r"(click|tap|press) (to|and|below)",
        r"(available now|get yours|claim|access)",
        r"(don't miss|limited time|hurry|act now|before)",
        r"\$\d+",  # Price mention
    ]
    for pattern in cta_patterns:
        if re.search(pattern, text_lower):
            elements["call_to_action"] = True
            element_details["call_to_action"] = {"detected": True, "pattern": pattern}
            break
    if not elements["call_to_action"]:
        element_details["call_to_action"] = {"detected": False}

    # Calculate results
    elements_present = sum(elements.values())
    missing_elements = [elem for elem, present in elements.items() if not present]
    structure_complete = elements_present == 4

    # Score: Each element worth 25 points
    structure_score = elements_present * 25

    return {
        "elements_present": elements_present,
        "element_details": element_details,
        "missing_elements": missing_elements,
        "structure_complete": structure_complete,
        "structure_score": structure_score
    }


def _check_length_optimization(caption_text: str, send_type_key: str) -> dict[str, Any]:
    """
    Check if caption length is within optimal range for the send type.

    Args:
        caption_text: The caption text to analyze.
        send_type_key: The send type key to get optimal ranges for.

    Returns:
        Dictionary containing:
            - actual: Actual character count
            - optimal_range: Tuple of (min, max) optimal length
            - acceptable_range: Tuple of (min, max) acceptable length
            - within_optimal: Boolean if within optimal range
            - within_tolerance: Boolean if within acceptable range
            - deviation_penalty: Score penalty for length deviation (0-30)
    """
    actual_length = len(caption_text.strip())

    # Get ranges for send type or use defaults
    ranges = OPTIMAL_LENGTH_RANGES.get(send_type_key, DEFAULT_LENGTH_RANGE)
    optimal_range = ranges["optimal"]
    acceptable_range = ranges["acceptable"]

    # Check if within ranges
    within_optimal = optimal_range[0] <= actual_length <= optimal_range[1]
    within_tolerance = acceptable_range[0] <= actual_length <= acceptable_range[1]

    # Calculate deviation penalty
    deviation_penalty = 0.0
    if not within_optimal:
        if within_tolerance:
            # Moderate penalty for being outside optimal but within acceptable
            if actual_length < optimal_range[0]:
                # Too short
                deviation = optimal_range[0] - actual_length
                max_deviation = optimal_range[0] - acceptable_range[0]
            else:
                # Too long
                deviation = actual_length - optimal_range[1]
                max_deviation = acceptable_range[1] - optimal_range[1]

            # Penalty scales from 0-15 based on how far outside optimal
            deviation_penalty = min(15, (deviation / max(max_deviation, 1)) * 15)
        else:
            # Outside acceptable range - heavy penalty
            if actual_length < acceptable_range[0]:
                # Way too short
                deviation_penalty = 25 + min(5, (acceptable_range[0] - actual_length) / 10)
            else:
                # Way too long
                deviation_penalty = 25 + min(5, (actual_length - acceptable_range[1]) / 50)

    return {
        "actual": actual_length,
        "optimal_range": optimal_range,
        "acceptable_range": acceptable_range,
        "within_optimal": within_optimal,
        "within_tolerance": within_tolerance,
        "deviation_penalty": round(deviation_penalty, 2)
    }


def _check_diversity(
    caption_text: str,
    scheduled_captions: list[dict[str, Any]],
    creator_id: str
) -> dict[str, Any]:
    """
    Check caption diversity against already-scheduled items.

    Uses difflib.SequenceMatcher for similarity calculation to detect
    repetitive or near-duplicate captions.

    Args:
        caption_text: The caption text to check.
        scheduled_captions: List of already-scheduled caption dicts with 'caption_text' key.
        creator_id: The creator_id for context.

    Returns:
        Dictionary containing:
            - max_similarity: Highest similarity score found (0.0-1.0)
            - most_similar_to: Caption text that is most similar (if any)
            - diversity_compliant: Boolean if diversity is acceptable
            - similarity_warning: Boolean if close to rejection threshold
            - comparisons_made: Number of comparisons performed
    """
    if not scheduled_captions:
        return {
            "max_similarity": 0.0,
            "most_similar_to": None,
            "diversity_compliant": True,
            "similarity_warning": False,
            "comparisons_made": 0
        }

    max_similarity = 0.0
    most_similar_to: Optional[str] = None
    caption_text_clean = caption_text.strip().lower()

    for scheduled in scheduled_captions:
        scheduled_text = scheduled.get("caption_text", "")
        if not scheduled_text:
            continue

        scheduled_text_clean = scheduled_text.strip().lower()

        # Calculate similarity using SequenceMatcher
        similarity = difflib.SequenceMatcher(
            None,
            caption_text_clean,
            scheduled_text_clean
        ).ratio()

        if similarity > max_similarity:
            max_similarity = similarity
            most_similar_to = scheduled_text[:100] + "..." if len(scheduled_text) > 100 else scheduled_text

    # Thresholds: >0.60 = rejection, >0.45 = warning
    diversity_compliant = max_similarity <= SIMILARITY_REJECTION_THRESHOLD
    similarity_warning = SIMILARITY_WARNING_THRESHOLD < max_similarity <= SIMILARITY_REJECTION_THRESHOLD

    return {
        "max_similarity": round(max_similarity, 4),
        "most_similar_to": most_similar_to,
        "diversity_compliant": diversity_compliant,
        "similarity_warning": similarity_warning,
        "comparisons_made": len(scheduled_captions)
    }


def _check_anti_patterization(
    caption_text: str,
    creator_id: str,
    check_global: bool
) -> dict[str, Any]:
    """
    Detect AI-generated patterns and check for overuse.

    Identifies common AI-generated patterns that reduce authenticity:
    - Alert emoji opener (starts with warning/alert emoji)
    - Superlative caps (ALL CAPS words like "AMAZING", "INCREDIBLE")
    - Climax language (overused terms like "explosive", "mind-blowing")
    - Duration specific (very specific times like "8:42 minutes")
    - Content enumeration (numbered lists of content)

    Args:
        caption_text: The caption text to analyze.
        creator_id: The creator_id for context.
        check_global: Whether to check global saturation (placeholder).

    Returns:
        Dictionary containing:
            - patterns_detected: List of AI patterns detected
            - pattern_count: Number of patterns detected
            - temporal_decay: Placeholder score (would query DB for recent usage)
            - global_usage_count: Placeholder count (cross-creator usage)
            - anti_pattern_compliant: Boolean if patterns are acceptable
            - pattern_penalty: Score penalty based on patterns found
    """
    patterns_detected: list[str] = []
    text_lower = caption_text.lower()

    # Pattern 1: Alert emoji opener - check for actual alert emojis at start
    alert_emoji_chars = ["\u26a0", "\u2757", "\u2755", "\u203c", "\u2049",
                         "\U0001F6A8", "\U0001F514", "\U0001F4E2", "\U0001F4E3"]
    caption_stripped = caption_text.strip()
    for alert_char in alert_emoji_chars:
        if caption_stripped.startswith(alert_char):
            patterns_detected.append("alert_emoji_opener")
            break

    # Pattern 2: Superlative caps - ALL CAPS words > 4 chars
    caps_pattern = re.findall(r'\b[A-Z]{5,}\b', caption_text)
    superlative_caps = [
        word for word in caps_pattern
        if word in ["AMAZING", "INCREDIBLE", "EXCLUSIVE", "INSANE", "HOTTEST",
                    "SEXIEST", "NAUGHTIEST", "WILDEST", "CRAZIEST", "INTENSE",
                    "EXPLOSIVE", "ULTIMATE", "SPECIAL", "LIMITED", "PRIVATE"]
    ]
    if superlative_caps:
        patterns_detected.append(f"superlative_caps:{','.join(superlative_caps[:3])}")

    # Pattern 3: Climax language - overused terms
    climax_terms = [
        r"mind.?blow", r"earth.?shatter", r"jaw.?drop", r"breath.?tak",
        r"game.?chang", r"life.?chang", r"explosive", r"insane",
        r"absolutely (wild|crazy|insane|incredible)", r"literally (the best|dying)"
    ]
    for term in climax_terms:
        if re.search(term, text_lower):
            patterns_detected.append(f"climax_language:{term}")
            break

    # Pattern 4: Duration specific - very specific times (e.g., 8:42 min)
    duration_pattern = re.search(r'(\d+):(\d{2})\s*(min|minute|sec)', text_lower)
    if duration_pattern:
        patterns_detected.append("duration_specific")

    # Pattern 5: Content enumeration - numbered lists
    # Use non-greedy quantifiers with length limits to prevent ReDoS
    enumeration_pattern = re.search(r'(1[\.\)]\s*.{1,100}?\n?\s*2[\.\)]\s*.{1,100}?)', caption_text)
    if enumeration_pattern:
        patterns_detected.append("content_enumeration")

    # Also check for repeated emoji sequences (fire, peach, eggplant pattern)
    emoji_seq_pattern = re.search(
        r'(\U0001F525.*\U0001F351.*\U0001F346)|'  # fire, peach, eggplant
        r'(\U0001F351.*\U0001F525.*\U0001F346)|'  # peach, fire, eggplant
        r'(\U0001F525{2,})|(\U0001F351{2,})|(\U0001F346{2,})',  # repeated same emoji
        caption_text
    )
    if emoji_seq_pattern:
        patterns_detected.append("emoji_enumeration")

    # Calculate pattern penalty
    pattern_count = len(patterns_detected)
    pattern_penalty = min(30, pattern_count * 10)  # 10 points per pattern, max 30

    # Temporal decay - placeholder (would query DB for recent usage)
    # In real implementation, would check caption_creator_performance.last_used_date
    temporal_decay = 0.0

    # Global usage count - placeholder (cross-creator usage)
    # In real implementation, would query caption_bank for usage counts
    global_usage_count = 0

    # Compliance: Allow up to 2 patterns, reject if 3+
    anti_pattern_compliant = pattern_count < MAX_AI_PATTERNS_BEFORE_WARNING

    return {
        "patterns_detected": patterns_detected,
        "pattern_count": pattern_count,
        "temporal_decay": temporal_decay,
        "global_usage_count": global_usage_count,
        "anti_pattern_compliant": anti_pattern_compliant,
        "pattern_penalty": pattern_penalty
    }


@mcp_tool(
    name="validate_caption_structure",
    description="Validate caption against structural rules, emoji compliance, and diversity thresholds. Returns validation report with anti-patterization checks.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "caption_text": {
                "type": "string",
                "description": "The caption text to validate"
            },
            "send_type_key": {
                "type": "string",
                "description": "The send type key for context-specific validation"
            },
            "scheduled_captions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "caption_text": {"type": "string"},
                        "caption_id": {"type": "integer"},
                        "send_type_key": {"type": "string"}
                    }
                },
                "description": "Other captions already scheduled (for diversity check)"
            },
            "check_global_saturation": {
                "type": "boolean",
                "description": "Whether to check global caption saturation across creators (default true)"
            }
        },
        "required": ["creator_id", "caption_text", "send_type_key"]
    }
)
def validate_caption_structure(
    creator_id: str,
    caption_text: str,
    send_type_key: str,
    scheduled_captions: Optional[list[dict[str, Any]]] = None,
    check_global_saturation: bool = True
) -> dict[str, Any]:
    """
    Validate caption structure for selection eligibility with anti-patterization safeguards.

    Performs five validation checks:
    1. Emoji Blending Compliance - Detects emoji spam and color patterns (HARD RULE)
    2. Four-Element PPV Structure - Checks PPV caption structure (scoring only)
    3. Length Optimization - Validates caption length for send type (warnings/penalties)
    4. Diversity Check - Compares against scheduled captions (HARD RULE if >0.60 similarity)
    5. Anti-Patterization - Detects AI-generated patterns (penalties)

    Args:
        creator_id: The creator_id or page_name.
        caption_text: The caption text to validate.
        send_type_key: The send type key for context-specific validation.
        scheduled_captions: List of already-scheduled caption dicts for diversity check.
        check_global_saturation: Whether to check global caption saturation.

    Returns:
        Dictionary containing:
            - valid: Boolean indicating if caption passes all hard rules
            - score: Validation score 0-100 (after penalties)
            - checks: Dict with results from all five checks
            - warnings: List of warning messages
            - rejections: List of rejection reasons (if any)
            - validation_timestamp: ISO timestamp of validation
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"validate_caption_structure: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    is_valid, error_msg = validate_key_input(send_type_key, "send_type_key")
    if not is_valid:
        logger.warning(f"validate_caption_structure: Invalid send_type_key - {error_msg}")
        return {"error": f"Invalid send_type_key: {error_msg}"}

    # Validate caption_text
    is_valid, error_msg = validate_string_length(caption_text, MAX_CAPTION_LENGTH, "caption_text")
    if not is_valid:
        logger.warning(f"validate_caption_structure: Invalid caption_text - {error_msg}")
        return {"error": f"Invalid caption_text: {error_msg}"}

    if not caption_text.strip():
        return {"error": "caption_text cannot be empty"}

    # Validate scheduled_captions if provided (security + performance)
    if scheduled_captions:
        if len(scheduled_captions) > MAX_SCHEDULED_CAPTIONS:
            return {"error": f"scheduled_captions exceeds maximum of {MAX_SCHEDULED_CAPTIONS} items"}

        for i, scheduled in enumerate(scheduled_captions):
            if not isinstance(scheduled, dict):
                return {"error": f"scheduled_captions[{i}] must be a dictionary"}
            sched_caption_text = scheduled.get("caption_text", "")
            if len(sched_caption_text) > MAX_SCHEDULED_CAPTION_LENGTH:
                return {"error": f"scheduled_captions[{i}].caption_text exceeds maximum length of {MAX_SCHEDULED_CAPTION_LENGTH}"}

    # Initialize result containers
    warnings: list[str] = []
    rejections: list[str] = []
    base_score = 100.0

    # CHECK 1: Emoji Blending Compliance (HARD RULE)
    emoji_check = _check_emoji_blending(caption_text)
    if not emoji_check["compliant"]:
        rejections.append(f"Emoji compliance failed: {'; '.join(emoji_check['issues'])}")
    elif emoji_check["issues"]:
        warnings.extend(emoji_check["issues"])

    # CHECK 2: Four-Element PPV Structure (scoring only, for PPV types)
    ppv_types = ["ppv_unlock", "ppv_wall", "bundle", "flash_bundle"]
    if send_type_key in ppv_types:
        ppv_check = _check_ppv_structure(caption_text, creator_id)
        if not ppv_check["structure_complete"]:
            # Penalty based on missing elements (up to 25 points)
            missing_penalty = (4 - ppv_check["elements_present"]) * PPV_MISSING_ELEMENT_PENALTY
            base_score -= missing_penalty
            if ppv_check["missing_elements"]:
                warnings.append(
                    f"PPV structure incomplete - missing: {', '.join(ppv_check['missing_elements'])}"
                )
    else:
        ppv_check = {
            "elements_present": None,
            "element_details": None,
            "missing_elements": None,
            "structure_complete": None,
            "structure_score": None,
            "skipped": True,
            "reason": f"Not a PPV send type ({send_type_key})"
        }

    # CHECK 3: Length Optimization (warnings and penalties)
    length_check = _check_length_optimization(caption_text, send_type_key)
    if not length_check["within_tolerance"]:
        warnings.append(
            f"Caption length ({length_check['actual']}) outside acceptable range "
            f"({length_check['acceptable_range'][0]}-{length_check['acceptable_range'][1]})"
        )
    elif not length_check["within_optimal"]:
        warnings.append(
            f"Caption length ({length_check['actual']}) outside optimal range "
            f"({length_check['optimal_range'][0]}-{length_check['optimal_range'][1]})"
        )
    base_score -= length_check["deviation_penalty"]

    # CHECK 4: Diversity Check (HARD RULE if >0.60 similarity)
    if scheduled_captions:
        diversity_check = _check_diversity(caption_text, scheduled_captions, creator_id)
        if not diversity_check["diversity_compliant"]:
            rejections.append(
                f"Caption too similar to scheduled caption "
                f"(similarity: {diversity_check['max_similarity']:.2%})"
            )
        elif diversity_check["similarity_warning"]:
            warnings.append(
                f"Caption similar to scheduled caption "
                f"(similarity: {diversity_check['max_similarity']:.2%})"
            )
    else:
        diversity_check = {
            "max_similarity": 0.0,
            "most_similar_to": None,
            "diversity_compliant": True,
            "similarity_warning": False,
            "comparisons_made": 0,
            "skipped": True,
            "reason": "No scheduled_captions provided"
        }

    # CHECK 5: Anti-Patterization (penalties)
    anti_pattern_check = _check_anti_patterization(
        caption_text, creator_id, check_global_saturation
    )
    if not anti_pattern_check["anti_pattern_compliant"]:
        warnings.append(
            f"Multiple AI patterns detected: {', '.join(anti_pattern_check['patterns_detected'][:3])}"
        )
    elif anti_pattern_check["pattern_count"] > 0:
        warnings.append(
            f"AI pattern detected: {', '.join(anti_pattern_check['patterns_detected'])}"
        )
    base_score -= anti_pattern_check["pattern_penalty"]

    # Calculate final score (clamp to 0-100)
    final_score = max(0.0, min(100.0, base_score))

    # Determine overall validity (no rejections)
    is_valid_result = len(rejections) == 0

    return {
        "valid": is_valid_result,
        "score": round(final_score, 2),
        "checks": {
            "emoji_blending": emoji_check,
            "ppv_structure": ppv_check,
            "length_optimization": length_check,
            "diversity": diversity_check,
            "anti_patterization": anti_pattern_check
        },
        "warnings": warnings,
        "rejections": rejections,
        "validation_timestamp": datetime.utcnow().isoformat() + "Z",
        "creator_id": creator_id,
        "send_type_key": send_type_key
    }


# =============================================================================
# Caption Attention Scoring Tools (Pipeline Supercharge v3.0.0)
# =============================================================================

# Attention quality tier thresholds
ATTENTION_TIER_THRESHOLDS = {
    "EXCEPTIONAL": 85,
    "HIGH": 70,
    "MEDIUM": 50,
    "LOW": 0,
}


def _calculate_attention_score(
    hook_score: float,
    depth_score: float,
    cta_score: float,
    emotion_score: float
) -> float:
    """
    Calculate composite attention score using weighted formula.

    Formula: (hook * 0.35) + (depth * 0.25) + (cta * 0.25) + (emotion * 0.15)

    Args:
        hook_score: Hook strength score (0-100).
        depth_score: Content depth score (0-100).
        cta_score: Call-to-action score (0-100).
        emotion_score: Emotional engagement score (0-100).

    Returns:
        Composite attention score (0-100).
    """
    return (hook_score * 0.35) + (depth_score * 0.25) + (cta_score * 0.25) + (emotion_score * 0.15)


def _get_quality_tier(attention_score: float) -> str:
    """
    Determine quality tier based on attention score.

    Args:
        attention_score: Composite attention score (0-100).

    Returns:
        Quality tier: EXCEPTIONAL, HIGH, MEDIUM, or LOW.
    """
    if attention_score >= ATTENTION_TIER_THRESHOLDS["EXCEPTIONAL"]:
        return "EXCEPTIONAL"
    elif attention_score >= ATTENTION_TIER_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif attention_score >= ATTENTION_TIER_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    else:
        return "LOW"


@mcp_tool(
    name="get_attention_metrics",
    description="Get raw attention engagement metrics for caption analysis. Returns hook strength, depth, CTA, and emotion indicators.",
    schema={
        "type": "object",
        "properties": {
            "caption_text": {
                "type": "string",
                "description": "The caption text to analyze"
            },
            "creator_id": {
                "type": "string",
                "description": "Optional creator_id for persona context"
            }
        },
        "required": ["caption_text"]
    }
)
def get_attention_metrics(
    caption_text: str,
    creator_id: Optional[str] = None
) -> dict[str, Any]:
    """
    Get raw attention engagement metrics for caption analysis.

    Analyzes caption text to extract attention quality indicators:
    - Hook strength: Opening sentence impact
    - Depth: Content substance and detail
    - CTA: Call-to-action clarity
    - Emotion: Emotional engagement potential

    Args:
        caption_text: The caption text to analyze.
        creator_id: Optional creator_id for persona context.

    Returns:
        Dictionary containing:
            - metrics: Raw metric values
            - indicators: Specific patterns detected
            - text_stats: Basic text statistics
    """
    if not caption_text or not caption_text.strip():
        return {"error": "caption_text cannot be empty"}

    if len(caption_text) > MAX_CAPTION_LENGTH:
        return {"error": f"caption_text exceeds maximum length of {MAX_CAPTION_LENGTH}"}

    text = caption_text.strip()
    text_lower = text.lower()

    # Text statistics
    words = text.split()
    word_count = len(words)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentence_count = len(sentences)
    avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

    # HOOK STRENGTH (0-100)
    hook_indicators = []
    hook_score = 50  # Base score

    # First sentence analysis
    first_sentence = sentences[0] if sentences else text[:100]

    # Strong opener patterns
    if re.match(r'^(omg|oh my|wow|guess what|pov|imagine|what if|breaking)', first_sentence.lower()):
        hook_indicators.append("strong_opener")
        hook_score += 15

    # Question hook
    if first_sentence.endswith('?'):
        hook_indicators.append("question_hook")
        hook_score += 10

    # Exclamation hook
    if first_sentence.endswith('!'):
        hook_indicators.append("exclamation_hook")
        hook_score += 5

    # Emoji hook
    first_emojis = _extract_emojis(first_sentence[:30])
    if first_emojis:
        hook_indicators.append("emoji_hook")
        hook_score += 5

    # Direct address
    if re.search(r'\b(you|your|babe|baby|daddy)\b', first_sentence.lower()):
        hook_indicators.append("direct_address")
        hook_score += 10

    # Short punchy hook (< 50 chars)
    if len(first_sentence) < 50:
        hook_indicators.append("short_punchy")
        hook_score += 5

    # DEPTH SCORE (0-100)
    depth_indicators = []
    depth_score = 50  # Base score

    # Specific details
    if re.search(r'\d+\s*(min|minute|sec|second|hour|vid|video|pic|photo)', text_lower):
        depth_indicators.append("specific_duration")
        depth_score += 15

    # Description richness
    descriptive_words = len(re.findall(
        r'\b(new|exclusive|private|personal|special|rare|limited|unique|custom|just)\b',
        text_lower
    ))
    if descriptive_words >= 3:
        depth_indicators.append("rich_description")
        depth_score += 10
    elif descriptive_words >= 1:
        depth_indicators.append("some_description")
        depth_score += 5

    # Content enumeration
    if re.search(r'(1\.|2\.|•|includes|featuring|with:)', text_lower):
        depth_indicators.append("content_list")
        depth_score += 10

    # Adequate length
    if 150 <= len(text) <= 400:
        depth_indicators.append("optimal_length")
        depth_score += 10
    elif len(text) < 100:
        depth_score -= 10

    # CTA SCORE (0-100)
    cta_indicators = []
    cta_score = 50  # Base score

    # Explicit CTA
    cta_patterns = [
        (r'(unlock|tip|purchase|buy|get it|grab it)', "purchase_cta", 20),
        (r'(click|tap|press)', "click_cta", 15),
        (r'(available now|get yours|claim)', "availability_cta", 15),
        (r'(don\'t miss|limited time|hurry)', "urgency_cta", 15),
        (r'\$\d+', "price_anchor", 10),
        (r'(dm me|message me|send me)', "message_cta", 10),
    ]

    for pattern, indicator, bonus in cta_patterns:
        if re.search(pattern, text_lower):
            cta_indicators.append(indicator)
            cta_score += bonus
            break  # Only count strongest CTA

    # CTA position (end of caption is best)
    last_50_chars = text[-50:].lower()
    if any(cta in last_50_chars for cta in ["unlock", "tip", "buy", "get", "dm"]):
        cta_indicators.append("cta_at_end")
        cta_score += 10

    # EMOTION SCORE (0-100)
    emotion_indicators = []
    emotion_score = 50  # Base score

    # Emotional language
    emotion_patterns = [
        (r'\b(love|miss|want|need|crave)\b', "desire_language", 15),
        (r'\b(excited|thrilled|can\'t wait)\b', "excitement_language", 12),
        (r'\b(naughty|dirty|bad|wild)\b', "playful_language", 10),
        (r'\b(special|personal|intimate|private)\b', "intimacy_language", 12),
    ]

    for pattern, indicator, bonus in emotion_patterns:
        if re.search(pattern, text_lower):
            emotion_indicators.append(indicator)
            emotion_score += bonus

    # Emoji emotional amplification
    emojis = _extract_emojis(text)
    if len(emojis) >= 2:
        emotion_indicators.append("emoji_emotion")
        emotion_score += 8

    # Personal pronouns (connection)
    pronoun_count = len(re.findall(r'\b(i|me|my|you|your|we|us)\b', text_lower))
    if pronoun_count >= 5:
        emotion_indicators.append("high_pronouns")
        emotion_score += 10
    elif pronoun_count >= 2:
        emotion_indicators.append("some_pronouns")
        emotion_score += 5

    # Clamp scores to 0-100
    hook_score = max(0, min(100, hook_score))
    depth_score = max(0, min(100, depth_score))
    cta_score = max(0, min(100, cta_score))
    emotion_score = max(0, min(100, emotion_score))

    return {
        "metrics": {
            "hook_score": round(hook_score, 2),
            "depth_score": round(depth_score, 2),
            "cta_score": round(cta_score, 2),
            "emotion_score": round(emotion_score, 2),
        },
        "indicators": {
            "hook": hook_indicators,
            "depth": depth_indicators,
            "cta": cta_indicators,
            "emotion": emotion_indicators,
        },
        "text_stats": {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_sentence_length": round(avg_sentence_length, 2),
            "character_count": len(text),
            "emoji_count": len(emojis),
        },
    }


@mcp_tool(
    name="get_caption_attention_scores",
    description="Get pre-computed attention scores for captions. Returns composite attention scores with quality tier classification.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "caption_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of caption IDs to get scores for"
            },
            "min_attention_score": {
                "type": "number",
                "description": "Minimum attention score threshold (default 0)"
            },
            "quality_tier": {
                "type": "string",
                "enum": ["LOW", "MEDIUM", "HIGH", "EXCEPTIONAL"],
                "description": "Filter by quality tier"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum scores to return (default 50)"
            }
        },
        "required": ["creator_id"]
    }
)
def get_caption_attention_scores(
    creator_id: str,
    caption_ids: Optional[list[int]] = None,
    min_attention_score: float = 0.0,
    quality_tier: Optional[str] = None,
    limit: int = 50
) -> dict[str, Any]:
    """
    Get pre-computed attention scores for captions.

    Returns stored attention quality scores from caption_attention_scores
    table, or empty results for captions without stored scores.

    Args:
        creator_id: The creator_id or page_name.
        caption_ids: Optional list of caption IDs to filter.
        min_attention_score: Minimum score threshold.
        quality_tier: Filter by specific quality tier.
        limit: Maximum results to return.

    Returns:
        Dictionary containing:
            - scores: List of attention score objects
            - count: Number of scores returned
            - tier_distribution: Count by quality tier
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_caption_attention_scores: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if quality_tier and quality_tier not in ("LOW", "MEDIUM", "HIGH", "EXCEPTIONAL"):
        return {"error": "quality_tier must be one of: LOW, MEDIUM, HIGH, EXCEPTIONAL"}

    if caption_ids:
        if len(caption_ids) > 500:
            return {"error": "caption_ids exceeds maximum of 500 items"}
        for idx, cap_id in enumerate(caption_ids):
            if not isinstance(cap_id, int) or cap_id <= 0:
                return {"error": f"caption_ids[{idx}] must be a positive integer"}

    if limit < 1 or limit > 500:
        return {"error": "limit must be between 1 and 500"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Build query
        query = """
            SELECT
                cas.attention_id,
                cas.caption_id,
                cas.hook_score,
                cas.depth_score,
                cas.cta_score,
                cas.emotion_score,
                cas.attention_score,
                cas.quality_tier,
                cas.analysis_version,
                cas.analyzed_at,
                cas.word_count,
                cas.sentence_count,
                cas.avg_sentence_length,
                cb.caption_text,
                cb.caption_type
            FROM caption_attention_scores cas
            JOIN caption_bank cb ON cas.caption_id = cb.caption_id
            WHERE cas.creator_id = ?
            AND cas.attention_score >= ?
        """
        params: list[Any] = [resolved_creator_id, min_attention_score]

        if caption_ids:
            placeholders = ",".join(["?" for _ in caption_ids])
            query += f" AND cas.caption_id IN ({placeholders})"
            params.extend(caption_ids)

        if quality_tier:
            query += " AND cas.quality_tier = ?"
            params.append(quality_tier)

        query += " ORDER BY cas.attention_score DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        scores = rows_to_list(cursor.fetchall())

        # Calculate tier distribution
        tier_cursor = conn.execute(
            """
            SELECT quality_tier, COUNT(*) as count
            FROM caption_attention_scores
            WHERE creator_id = ?
            GROUP BY quality_tier
            """,
            (resolved_creator_id,)
        )
        tier_distribution = {row["quality_tier"]: row["count"] for row in tier_cursor.fetchall()}

        # Find missing caption IDs if specific IDs were requested
        missing_ids = []
        if caption_ids:
            found_ids = {s["caption_id"] for s in scores}
            missing_ids = [cap_id for cap_id in caption_ids if cap_id not in found_ids]

        return {
            "scores": scores,
            "count": len(scores),
            "tier_distribution": tier_distribution,
            "missing_ids": missing_ids if missing_ids else None,
            "creator_id": resolved_creator_id,
        }

    except sqlite3.Error as e:
        logger.error(f"get_caption_attention_scores: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()