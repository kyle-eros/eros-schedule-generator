"""
EROS MCP Server Send Types Tools

Tools for retrieving send type definitions and volume configuration.

Version: 3.0.0
"""

import logging
from typing import Any, Optional

from mcp.connection import db_connection, get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import row_to_dict, rows_to_list, resolve_creator_id
from mcp.utils.security import validate_key_input

logger = logging.getLogger("eros_db_server")


@mcp_tool(
    name="get_send_types",
    description="Get all send types with optional filtering by category and page_type. Returns complete send type configuration.",
    schema={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["revenue", "engagement", "retention"],
                "description": "Optional filter by category"
            },
            "page_type": {
                "type": "string",
                "enum": ["paid", "free"],
                "description": "Optional filter by page_type (matches 'both' or exact match)"
            }
        },
        "required": []
    }
)
def get_send_types(
    category: Optional[str] = None,
    page_type: Optional[str] = None
) -> dict[str, Any]:
    """
    Get all send types with optional filtering.

    Args:
        category: Optional filter by category ('revenue', 'engagement', 'retention').
        page_type: Optional filter by page_type ('paid' or 'free').
                   Filters to send types where page_type_restriction matches or is 'both'.

    Returns:
        Dictionary containing:
            - send_types: List of all send type records with all columns
            - count: Total number of send types returned
    """
    with db_connection() as conn:
        query = """
            SELECT
                send_type_id,
                send_type_key,
                category,
                display_name,
                description,
                purpose,
                strategy,
                requires_media,
                requires_flyer,
                requires_price,
                requires_link,
                has_expiration,
                default_expiration_hours,
                can_have_followup,
                followup_delay_minutes,
                page_type_restriction,
                caption_length,
                emoji_recommendation,
                max_per_day,
                max_per_week,
                min_hours_between,
                sort_order,
                is_active,
                created_at
            FROM send_types
            WHERE is_active = 1
        """
        params: list[Any] = []

        if category is not None:
            if category not in ("revenue", "engagement", "retention"):
                return {"error": "category must be 'revenue', 'engagement', or 'retention'"}
            query += " AND category = ?"
            params.append(category)

        if page_type is not None:
            if page_type not in ("paid", "free"):
                return {"error": "page_type must be 'paid' or 'free'"}
            query += " AND (page_type_restriction = ? OR page_type_restriction = 'both')"
            params.append(page_type)

        query += " ORDER BY sort_order ASC"

        cursor = conn.execute(query, params)
        send_types = rows_to_list(cursor.fetchall())

        return {
            "send_types": send_types,
            "count": len(send_types)
        }


@mcp_tool(
    name="get_send_type_details",
    description="Get complete details for a single send type by key, including related caption type requirements.",
    schema={
        "type": "object",
        "properties": {
            "send_type_key": {
                "type": "string",
                "description": "The unique key for the send type (e.g., 'ppv_unlock', 'bump_normal')"
            }
        },
        "required": ["send_type_key"]
    }
)
def get_send_type_details(send_type_key: str) -> dict[str, Any]:
    """
    Get complete details for a single send type by key.

    Args:
        send_type_key: The unique key for the send type (e.g., 'ppv_unlock', 'bump_normal').

    Returns:
        Dictionary containing:
            - send_type: Full send type record with all columns
            - caption_requirements: List of related caption type requirements with priority

    Raises:
        Error if send_type_key not found.
    """
    # Input validation
    is_valid, error_msg = validate_key_input(send_type_key, "send_type_key")
    if not is_valid:
        logger.warning(f"get_send_type_details: Invalid send_type_key - {error_msg}")
        return {"error": f"Invalid send_type_key: {error_msg}"}

    conn = get_db_connection()
    try:
        # Get send type record
        cursor = conn.execute(
            """
            SELECT
                send_type_id,
                send_type_key,
                category,
                display_name,
                description,
                purpose,
                strategy,
                requires_media,
                requires_flyer,
                requires_price,
                requires_link,
                has_expiration,
                default_expiration_hours,
                can_have_followup,
                followup_delay_minutes,
                page_type_restriction,
                caption_length,
                emoji_recommendation,
                max_per_day,
                max_per_week,
                min_hours_between,
                sort_order,
                is_active,
                created_at
            FROM send_types
            WHERE send_type_key = ?
            """,
            (send_type_key,)
        )
        send_type = row_to_dict(cursor.fetchone())

        if not send_type:
            return {"error": f"Send type not found: {send_type_key}"}

        # Get caption requirements
        cursor = conn.execute(
            """
            SELECT
                caption_type,
                priority,
                notes
            FROM send_type_caption_requirements
            WHERE send_type_id = ?
            ORDER BY priority ASC
            """,
            (send_type["send_type_id"],)
        )
        caption_requirements = rows_to_list(cursor.fetchall())

        return {
            "send_type": send_type,
            "caption_requirements": caption_requirements
        }
    finally:
        conn.close()


@mcp_tool(
    name="get_volume_config",
    description="Get extended volume configuration including category breakdowns (revenue/engagement/retention items per day) and type-specific limits.",
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
def get_volume_config(creator_id: str) -> dict[str, Any]:
    """
    Get extended volume configuration for a creator using dynamic calculation.

    Calculates volume based on fan count, saturation/opportunity scores,
    and performance trends instead of static assignments. Includes Volume
    Optimization v3.0 Wave 2 fields for bump multipliers and followup scaling.

    Args:
        creator_id: The creator_id or page_name.

    Returns:
        Dictionary containing volume configuration with calculation metadata:
            - volume_level: Tier classification (Low/Mid/High/Ultra)
            - ppv_per_day: Legacy field (revenue items per day)
            - bump_per_day: Legacy field (engagement items per day)
            - revenue_items_per_day: Revenue sends per day
            - engagement_items_per_day: Engagement sends per day
            - retention_items_per_day: Retention sends per day
            - bundle_per_week: Bundle sends per week
            - game_per_week: Game sends per week
            - followup_per_day: Followup sends per day (tier-based cap)
            - weekly_distribution: Dict mapping day index (0-6) to volume
            - content_allocations: Dict mapping content type to volume
            - confidence_score: Calculation confidence (0.0-1.0)
            - elasticity_capped: Whether elasticity cap was applied
            - caption_warnings: List of caption shortage warnings
            - dow_multipliers_used: Day-of-week multipliers applied
            - adjustments_applied: List of adjustment names applied
            - fused_saturation: Saturation after multi-horizon fusion
            - fused_opportunity: Opportunity after multi-horizon fusion
            - prediction_id: Database ID for prediction tracking
            - divergence_detected: Multi-horizon divergence flag
            - message_count: Messages analyzed for confidence
            - total_weekly_volume: Sum of weekly distribution
            - has_warnings: Whether caption warnings exist
            - is_high_confidence: Whether confidence >= 0.6
            - bump_multiplier: Content category multiplier (1.0-2.67x)
            - bump_adjusted_engagement: Engagement after bump applied
            - content_category: lifestyle/softcore/amateur/explicit
            - bump_capped: Whether multiplier was tier-capped
            - followup_volume_scaled: Scaled followup count
            - followup_rate_used: Rate applied (default 0.80)
            - calculation_source: "optimized" or "dynamic" (fallback)
            - fan_count: Creator's fan count
            - page_type: "paid" or "free"
            - saturation_score: Original saturation (before fusion)
            - opportunity_score: Original opportunity (before fusion)
            - revenue_trend: Revenue trend percentage
            - data_source: Source of performance data
            - tracking_date: Date of performance tracking
    """
    # Import here to avoid circular imports
    from python.volume.dynamic_calculator import (
        calculate_dynamic_volume,
        calculate_optimized_volume,
        PerformanceContext,
        OptimizedVolumeResult,
    )
    from python.volume.score_calculator import calculate_scores_from_db

    conn = get_db_connection()
    try:
        # Resolve creator_id and get basic info
        cursor = conn.execute(
            """
            SELECT creator_id, page_name, page_type, current_active_fans
            FROM creators
            WHERE creator_id = ? OR page_name = ?
            """,
            (creator_id, creator_id)
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"Creator not found: {creator_id}"}

        resolved_creator_id = row["creator_id"]
        page_type = row["page_type"]
        fan_count = row["current_active_fans"] or 0

        # Try to get scores from volume_performance_tracking first
        cursor = conn.execute(
            """
            SELECT saturation_score, opportunity_score, revenue_per_send_trend,
                   tracking_date
            FROM volume_performance_tracking
            WHERE creator_id = ? AND tracking_period = '14d'
            ORDER BY tracking_date DESC
            LIMIT 1
            """,
            (resolved_creator_id,)
        )
        tracking = cursor.fetchone()

        if tracking and tracking["saturation_score"] is not None:
            saturation_score = tracking["saturation_score"]
            opportunity_score = tracking["opportunity_score"]
            revenue_trend = tracking["revenue_per_send_trend"] or 0.0
            tracking_date = tracking["tracking_date"]
            data_source = "volume_performance_tracking"
        else:
            # Calculate scores on-demand from mass_messages
            calculated = calculate_scores_from_db(conn, resolved_creator_id)
            if calculated:
                saturation_score = calculated.saturation_score
                opportunity_score = calculated.opportunity_score
                revenue_trend = 0.0  # Not available from on-demand calc
                tracking_date = calculated.calculation_date
                data_source = "calculated_on_demand"
            else:
                # Default to neutral scores if no data
                saturation_score = 50.0
                opportunity_score = 50.0
                revenue_trend = 0.0
                tracking_date = None
                data_source = "default_values"

        # Build performance context
        context = PerformanceContext(
            fan_count=fan_count,
            page_type=page_type,
            saturation_score=saturation_score,
            opportunity_score=opportunity_score,
            revenue_trend=revenue_trend
        )

        # Try optimized volume calculation (full pipeline)
        try:
            logger.info(
                f"Calculating optimized volume for creator {resolved_creator_id}"
            )
            result = calculate_optimized_volume(
                context,
                creator_id=resolved_creator_id,
                db_path=None,  # Uses EROS_DB_PATH env var
                week_start=None,  # Defaults to next Monday
                track_prediction=True,
            )

            # Calculate type-specific limits from final_config tier
            tier_str = result.final_config.tier.value.title()  # 'high' -> 'High'
            bundle_per_week = {"Low": 1, "Mid": 2, "High": 3, "Ultra": 4}.get(tier_str, 1)
            game_per_week = {"Low": 1, "Mid": 2, "High": 2, "Ultra": 3}.get(tier_str, 1)
            followup_per_day = min(
                result.final_config.revenue_per_day,
                {"Low": 2, "Mid": 3, "High": 4, "Ultra": 5}.get(tier_str, 2)
            )

            return {
                # Legacy fields (backward compatible) - use result.final_config
                "volume_level": tier_str,
                "ppv_per_day": result.final_config.revenue_per_day,  # Legacy field
                "bump_per_day": result.final_config.engagement_per_day,  # Legacy field

                # Standard category fields - from final_config
                "revenue_items_per_day": result.final_config.revenue_per_day,
                "engagement_items_per_day": result.final_config.engagement_per_day,
                "retention_items_per_day": result.final_config.retention_per_day,

                # Type-specific limits (calculate from tier)
                "bundle_per_week": bundle_per_week,
                "game_per_week": game_per_week,
                "followup_per_day": followup_per_day,

                # Full OptimizedVolumeResult fields
                "weekly_distribution": result.weekly_distribution,
                "content_allocations": result.content_allocations,
                "confidence_score": result.confidence_score,
                "elasticity_capped": result.elasticity_capped,
                "caption_warnings": result.caption_warnings,
                "dow_multipliers_used": result.dow_multipliers_used,
                "adjustments_applied": result.adjustments_applied,
                "fused_saturation": result.fused_saturation,
                "fused_opportunity": result.fused_opportunity,
                "prediction_id": result.prediction_id,
                "divergence_detected": result.divergence_detected,
                "message_count": result.message_count,
                "total_weekly_volume": result.total_weekly_volume,
                "has_warnings": result.has_warnings,
                "is_high_confidence": result.is_high_confidence,

                # Volume Optimization v3.0 Wave 2 fields
                "bump_multiplier": result.bump_multiplier,
                "bump_adjusted_engagement": result.bump_adjusted_engagement,
                "content_category": result.content_category,
                "bump_capped": result.bump_capped,
                "followup_volume_scaled": result.followup_volume_scaled,
                "followup_rate_used": result.followup_rate_used,

                # Metadata
                "calculation_source": "optimized",
                "fan_count": fan_count,
                "page_type": page_type,
                "saturation_score": saturation_score,  # Original score before fusion
                "opportunity_score": opportunity_score,  # Original score before fusion
                "revenue_trend": revenue_trend,
                "data_source": data_source,
                "tracking_date": tracking_date,
            }

        except Exception as e:
            # Fall back to basic dynamic calculation if optimized fails
            logger.warning(
                f"Optimized volume calculation failed, falling back to dynamic: {e}"
            )
            config = calculate_dynamic_volume(context)

            # Calculate type-specific limits based on tier
            tier_str = config.tier.value.title()  # 'high' -> 'High'
            bundle_per_week = {"Low": 1, "Mid": 2, "High": 3, "Ultra": 4}.get(tier_str, 1)
            game_per_week = {"Low": 1, "Mid": 2, "High": 2, "Ultra": 3}.get(tier_str, 1)
            followup_per_day = min(
                config.revenue_per_day,
                {"Low": 2, "Mid": 3, "High": 4, "Ultra": 5}.get(tier_str, 2)
            )

            return {
                # Standard fields (backward compatible)
                "volume_level": tier_str,
                "ppv_per_day": config.revenue_per_day,  # Legacy field
                "bump_per_day": config.engagement_per_day,  # Legacy field
                "revenue_items_per_day": config.revenue_per_day,
                "engagement_items_per_day": config.engagement_per_day,
                "retention_items_per_day": config.retention_per_day,
                "bundle_per_week": bundle_per_week,
                "game_per_week": game_per_week,
                "followup_per_day": followup_per_day,

                # Fallback metadata (limited fields)
                "calculation_source": "dynamic",  # Indicates fallback was used
                "fan_count": fan_count,
                "page_type": page_type,
                "saturation_score": saturation_score,
                "opportunity_score": opportunity_score,
                "revenue_trend": revenue_trend,
                "data_source": data_source,
                "tracking_date": tracking_date,
                "fallback_reason": str(e),
            }
    finally:
        conn.close()
