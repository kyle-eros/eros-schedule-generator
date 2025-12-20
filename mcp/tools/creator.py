"""
EROS MCP Server Creator Tools

Tools for retrieving creator profiles, active creators, persona profiles,
and vault availability information.

Version: 3.0.0
"""

import logging
from typing import Any, Optional

from mcp.connection import db_connection, get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import row_to_dict, rows_to_list, resolve_creator_id
from mcp.utils.security import validate_creator_id

logger = logging.getLogger("eros_db_server")


@mcp_tool(
    name="get_active_creators",
    description="Get all active creators with performance metrics, volume assignments, and tier classification.",
    schema={
        "type": "object",
        "properties": {
            "tier": {
                "type": "integer",
                "description": "Optional filter by performance_tier (1-5)"
            },
            "page_type": {
                "type": "string",
                "enum": ["paid", "free"],
                "description": "Optional filter by page_type"
            }
        },
        "required": []
    }
)
def get_active_creators(
    tier: Optional[int] = None,
    page_type: Optional[str] = None
) -> dict[str, Any]:
    """
    Get all active creators with performance metrics, volume assignments, and tier classification.

    Retrieves all active creators from the database with optional filtering by
    performance tier and page type. Results are enriched with persona data and
    ordered by total earnings.

    Args:
        tier: Optional filter by performance_tier (1-5). Higher tiers indicate
            better performance. Tier 1 = top performers, Tier 5 = lowest performers.
        page_type: Optional filter by page_type ('paid' or 'free'). 'paid' pages
            have subscription fees, 'free' pages rely on PPV revenue.

    Returns:
        Dictionary containing:
            - creators: List of creator records with complete profile data including:
                - Basic info (creator_id, page_name, display_name)
                - Business metrics (page_type, subscription_price, current_active_fans)
                - Performance (performance_tier, current_total_earnings)
                - Persona (primary_tone, emoji_frequency, slang_level)
            - count: Total number of creators returned

    Raises:
        DatabaseError: If database query fails.

    Example:
        >>> result = get_active_creators(tier=1, page_type="paid")
        >>> print(f"Found {result['count']} top-tier paid creators")
        >>> for creator in result['creators']:
        ...     print(f"{creator['display_name']}: ${creator['current_total_earnings']}")
    """
    with db_connection() as conn:
        query = """
            SELECT
                c.creator_id,
                c.page_name,
                c.display_name,
                c.page_type,
                c.subscription_price,
                c.timezone,
                c.creator_group,
                c.current_active_fans,
                c.current_total_earnings,
                c.performance_tier,
                c.persona_type,
                cp.primary_tone,
                cp.emoji_frequency,
                cp.slang_level
            FROM creators c
            LEFT JOIN creator_personas cp
                ON c.creator_id = cp.creator_id
            WHERE c.is_active = 1
        """
        params: list[Any] = []

        if tier is not None:
            query += " AND c.performance_tier = ?"
            params.append(tier)

        if page_type is not None:
            if page_type not in ("paid", "free"):
                return {"error": "page_type must be 'paid' or 'free'"}
            query += " AND c.page_type = ?"
            params.append(page_type)

        query += " ORDER BY c.current_total_earnings DESC"

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        creators = rows_to_list(rows)

        return {
            "creators": creators,
            "count": len(creators)
        }


@mcp_tool(
    name="get_creator_profile",
    description="Get comprehensive profile for a single creator including analytics, volume assignment, and top content types.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name to look up"
            }
        },
        "required": ["creator_id"]
    }
)
def get_creator_profile(creator_id: str) -> dict[str, Any]:
    """
    Get comprehensive profile for a single creator.

    Retrieves complete creator profile including basic information, 30-day
    analytics summary, dynamic volume configuration, and top-performing content
    types. This is the primary tool for getting detailed creator data.

    The function accepts either creator_id or page_name as input and resolves
    it to the actual creator_id. Volume configuration is calculated dynamically
    using the optimized volume pipeline.

    Args:
        creator_id: The creator_id or page_name to look up. Can be either the
            internal creator_id (e.g., "alexia") or the public page_name
            (e.g., "alexia"). Validation: alphanumeric, underscore, hyphen only;
            max 100 characters.

    Returns:
        Dictionary containing:
            - creator: Complete creator record from creators table including:
                - creator_id, page_name, display_name
                - page_type, subscription_price, timezone
                - current_active_fans, current_total_earnings
                - performance_tier, persona_type, is_active
            - analytics_summary: 30-day analytics from creator_analytics_summary:
                - total_sends, total_earnings, avg_earnings_per_send
                - avg_purchase_rate, avg_view_rate
            - volume_assignment: Dynamic volume configuration from get_volume_config:
                - volume_level, revenue/engagement/retention items per day
                - bundle_per_week, game_per_week, followup_per_day
                - weekly_distribution, content_allocations (if optimized)
            - top_content_types: Most recent content type rankings:
                - content_type, rank, send_count, total_earnings
                - performance_tier (TOP/MID/LOW/AVOID), recommendation

    Raises:
        ValueError: If creator_id validation fails (invalid format).
        DatabaseError: If database query fails.

    Example:
        >>> profile = get_creator_profile("alexia")
        >>> print(f"Creator: {profile['creator']['display_name']}")
        >>> print(f"Tier: {profile['creator']['performance_tier']}")
        >>> print(f"Volume Level: {profile['volume_assignment']['volume_level']}")
        >>> print(f"Top Content: {profile['top_content_types'][0]['content_type']}")
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_creator_profile: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    conn = get_db_connection()
    try:
        # First, resolve creator_id (could be page_name)
        cursor = conn.execute(
            """
            SELECT creator_id, page_name FROM creators
            WHERE creator_id = ? OR page_name = ?
            """,
            (creator_id, creator_id)
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"Creator not found: {creator_id}"}

        resolved_creator_id = row["creator_id"]

        # Get full creator record
        cursor = conn.execute(
            """
            SELECT * FROM creators WHERE creator_id = ?
            """,
            (resolved_creator_id,)
        )
        creator = row_to_dict(cursor.fetchone())

        # Get 30-day analytics summary
        cursor = conn.execute(
            """
            SELECT * FROM creator_analytics_summary
            WHERE creator_id = ? AND period_type = '30d'
            """,
            (resolved_creator_id,)
        )
        analytics_summary = row_to_dict(cursor.fetchone())

        # Get top content types (most recent analysis)
        cursor = conn.execute(
            """
            SELECT * FROM top_content_types
            WHERE creator_id = ?
            AND analysis_date = (
                SELECT MAX(analysis_date) FROM top_content_types
                WHERE creator_id = ?
            )
            ORDER BY rank ASC
            """,
            (resolved_creator_id, resolved_creator_id)
        )
        top_content_types = rows_to_list(cursor.fetchall())

    finally:
        conn.close()

    # Get dynamic volume configuration (import here to avoid circular imports)
    # Called outside the try-finally block since get_volume_config manages its own connection
    from mcp.tools.send_types import get_volume_config
    volume_assignment = get_volume_config(resolved_creator_id)

    return {
        "creator": creator,
        "analytics_summary": analytics_summary,
        "volume_assignment": volume_assignment,
        "top_content_types": top_content_types
    }


@mcp_tool(
    name="get_persona_profile",
    description="Get creator persona including tone, emoji style, and slang level.",
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
def get_persona_profile(creator_id: str) -> dict[str, Any]:
    """
    Get creator persona (tone, archetype, emoji style).

    Retrieves creator persona profile including communication style, tone,
    emoji usage patterns, and slang level. This data is used for caption
    matching and content personalization.

    Args:
        creator_id: The creator_id or page_name to look up. Accepts both
            internal creator_id and public page_name formats.

    Returns:
        Dictionary containing:
            - creator: Basic creator info including:
                - creator_id, page_name, display_name, persona_type
            - persona: Persona data from creator_personas table including:
                - persona_id: Primary key
                - primary_tone: Main communication tone (e.g., "playful", "seductive")
                - secondary_tone: Secondary tone if applicable
                - emoji_frequency: "low", "medium", or "high"
                - favorite_emojis: String of commonly used emojis
                - slang_level: "low", "medium", or "high"
                - avg_sentiment: Sentiment score 0-1 (higher = more positive)
                - avg_caption_length: Average character count in captions
                - last_analyzed: Timestamp of last persona analysis
            - voice_samples: Reserved for future use (currently empty dict)

    Raises:
        DatabaseError: If database query fails.

    Example:
        >>> persona = get_persona_profile("alexia")
        >>> print(f"Tone: {persona['persona']['primary_tone']}")
        >>> print(f"Emoji Frequency: {persona['persona']['emoji_frequency']}")
        >>> print(f"Favorites: {persona['persona']['favorite_emojis']}")
    """
    conn = get_db_connection()
    try:
        # Resolve creator_id and get basic info
        cursor = conn.execute(
            """
            SELECT creator_id, page_name, display_name, persona_type
            FROM creators
            WHERE creator_id = ? OR page_name = ?
            """,
            (creator_id, creator_id)
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"Creator not found: {creator_id}"}

        resolved_creator_id = row["creator_id"]
        creator_info = row_to_dict(row)

        # Get persona data
        cursor = conn.execute(
            """
            SELECT
                persona_id,
                primary_tone,
                secondary_tone,
                emoji_frequency,
                favorite_emojis,
                slang_level,
                avg_sentiment,
                avg_caption_length,
                last_analyzed,
                created_at,
                updated_at
            FROM creator_personas
            WHERE creator_id = ?
            """,
            (resolved_creator_id,)
        )
        persona = row_to_dict(cursor.fetchone())

        return {
            "creator": creator_info,
            "persona": persona,
            "voice_samples": {}  # Table doesn't exist
        }
    finally:
        conn.close()


@mcp_tool(
    name="get_vault_availability",
    description="Get what content types are available in creator's vault.",
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
def get_vault_availability(creator_id: str) -> dict[str, Any]:
    """
    Get what content types are available in creator's vault.

    Retrieves inventory of content types available in the creator's vault,
    including quantities, quality ratings, and content type metadata. This
    is used for content allocation in schedule generation.

    The vault_matrix tracks what content types the creator has available,
    how much of each type, and the quality rating. Only content types with
    has_content=1 are returned.

    Args:
        creator_id: The creator_id or page_name to look up. Accepts both
            internal creator_id and public page_name formats.

    Returns:
        Dictionary containing:
            - available_content: List of vault entries with detailed info:
                - vault_id: Vault entry ID
                - content_type_id: Content type identifier
                - has_content: Always 1 (filtered)
                - quantity_available: Number of items available
                - quality_rating: Quality score (1.0-5.0)
                - notes: Internal notes about content
                - updated_at: Last update timestamp
                - type_name: Content type name (e.g., "B/G", "Solo")
                - type_category: Category (e.g., "explicit", "teasing")
                - description: Content type description
                - priority_tier: Priority ranking (1 = highest)
                - is_explicit: 1 if explicit, 0 if not
            - content_types: Simple list of available content type names
            - total_items: Total quantity available across all types

    Raises:
        DatabaseError: If database query fails.

    Example:
        >>> vault = get_vault_availability("alexia")
        >>> print(f"Available types: {', '.join(vault['content_types'])}")
        >>> print(f"Total items: {vault['total_items']}")
        >>> for item in vault['available_content']:
        ...     print(f"{item['type_name']}: {item['quantity_available']} items")
    """
    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        cursor = conn.execute(
            """
            SELECT
                vm.vault_id,
                vm.content_type_id,
                vm.has_content,
                vm.quantity_available,
                vm.quality_rating,
                vm.notes,
                vm.updated_at,
                ct.type_name,
                ct.type_category,
                ct.description,
                ct.priority_tier,
                ct.is_explicit
            FROM vault_matrix vm
            JOIN content_types ct ON vm.content_type_id = ct.content_type_id
            WHERE vm.creator_id = ? AND vm.has_content = 1
            ORDER BY ct.priority_tier ASC, vm.quantity_available DESC
            """,
            (resolved_creator_id,)
        )
        available_content = rows_to_list(cursor.fetchall())

        # Extract simple list of content type names
        content_types = [item["type_name"] for item in available_content]

        # Calculate total items
        total_items = sum(item["quantity_available"] or 0 for item in available_content)

        return {
            "available_content": available_content,
            "content_types": content_types,
            "total_items": total_items
        }
    finally:
        conn.close()
