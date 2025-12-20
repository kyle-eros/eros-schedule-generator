"""
EROS MCP Server Performance Tools

Tools for retrieving performance trends, optimal timing, content type rankings,
and volume assignments.

Version: 3.0.0
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import row_to_dict, rows_to_list, resolve_creator_id

logger = logging.getLogger("eros_db_server")


@mcp_tool(
    name="get_best_timing",
    description="Get optimal posting times based on historical mass_messages performance.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "days_lookback": {
                "type": "integer",
                "description": "Number of days to analyze (default 30)"
            }
        },
        "required": ["creator_id"]
    }
)
def get_best_timing(
    creator_id: str,
    days_lookback: int = 30
) -> dict[str, Any]:
    """
    Get optimal posting times based on historical mass_messages performance.

    Analyzes mass message earnings by hour and day of week to identify
    the best times for this creator.

    Args:
        creator_id: The creator_id or page_name.
        days_lookback: Number of days to analyze (default 30).

    Returns:
        Dictionary containing:
            - timezone: Creator's timezone
            - best_hours: List of {hour, avg_earnings, message_count} sorted by earnings
            - best_days: List of {day_of_week, day_name, avg_earnings, message_count}
    """
    conn = get_db_connection()
    try:
        # Resolve creator_id and get timezone
        cursor = conn.execute(
            """
            SELECT creator_id, page_name, timezone FROM creators
            WHERE creator_id = ? OR page_name = ?
            """,
            (creator_id, creator_id)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Creator not found: {creator_id}")

        resolved_creator_id = row["creator_id"]
        timezone = row["timezone"] or "America/Los_Angeles"

        cutoff_date = (datetime.now() - timedelta(days=days_lookback)).strftime("%Y-%m-%d")

        # Best hours
        cursor = conn.execute(
            """
            SELECT
                sending_hour AS hour,
                AVG(earnings) AS avg_earnings,
                COUNT(*) AS message_count,
                SUM(earnings) AS total_earnings
            FROM mass_messages
            WHERE creator_id = ?
            AND message_type = 'ppv'
            AND sending_time >= ?
            AND earnings > 0
            GROUP BY sending_hour
            ORDER BY avg_earnings DESC
            """,
            (resolved_creator_id, cutoff_date)
        )
        best_hours = rows_to_list(cursor.fetchall())

        # Best days of week
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        cursor = conn.execute(
            """
            SELECT
                sending_day_of_week AS day_of_week,
                AVG(earnings) AS avg_earnings,
                COUNT(*) AS message_count,
                SUM(earnings) AS total_earnings
            FROM mass_messages
            WHERE creator_id = ?
            AND message_type = 'ppv'
            AND sending_time >= ?
            AND earnings > 0
            GROUP BY sending_day_of_week
            ORDER BY avg_earnings DESC
            """,
            (resolved_creator_id, cutoff_date)
        )
        best_days_raw = rows_to_list(cursor.fetchall())

        # Add day names
        best_days = []
        for day in best_days_raw:
            day["day_name"] = day_names[day["day_of_week"]] if day["day_of_week"] is not None else "Unknown"
            best_days.append(day)

        return {
            "timezone": timezone,
            "best_hours": best_hours,
            "best_days": best_days,
            "analysis_period_days": days_lookback
        }
    finally:
        conn.close()


@mcp_tool(
    name="get_volume_assignment",
    description="[DEPRECATED] Get current volume assignment for a creator (volume_level, ppv_per_day, bump_per_day). Use get_volume_config() instead.",
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
def get_volume_assignment(creator_id: str) -> dict[str, Any]:
    """
    Get current volume assignment for a creator.

    DEPRECATED: This function now uses dynamic calculation instead of
    static volume_assignments table. Use get_volume_config() for full details.

    Args:
        creator_id: The creator_id or page_name.

    Returns:
        Dictionary with volume assignment (dynamically calculated).
    """
    logger.warning(
        f"get_volume_assignment() is deprecated as of v3.0.0 and will be removed in v4.0.0. "
        f"Use get_volume_config() instead for dynamic calculation with full metadata."
    )

    # Import here to avoid circular imports
    from mcp.tools.send_types import get_volume_config

    result = get_volume_config(creator_id)

    if "error" in result:
        return result

    # Add deprecation notice
    return {
        "volume_level": result.get("volume_level"),
        "ppv_per_day": result.get("ppv_per_day"),
        "bump_per_day": result.get("bump_per_day"),
        "assigned_at": result.get("tracking_date"),
        "assigned_by": "dynamic_calculation",
        "assigned_reason": "fan_count_bracket",
        "_deprecated": True,
        "_deprecation_version": "3.0.0",
        "_removal_version": "4.0.0",
        "_message": "get_volume_assignment is deprecated. Use get_volume_config() for dynamic calculation with full metadata."
    }


@mcp_tool(
    name="get_performance_trends",
    description="Get saturation/opportunity scores and performance trends from volume_performance_tracking.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "period": {
                "type": "string",
                "enum": ["7d", "14d", "30d"],
                "description": "Tracking period (default '14d')"
            }
        },
        "required": ["creator_id"]
    }
)
def get_performance_trends(
    creator_id: str,
    period: str = "14d"
) -> dict[str, Any]:
    """
    Get saturation/opportunity scores from volume_performance_tracking.

    Retrieves performance trends and market analysis for a creator over a
    specified period. Includes saturation scores (indicating if audience is
    oversaturated), opportunity scores (indicating growth potential), and
    trend analysis for key metrics.

    Saturation Score Interpretation:
        0-30: Low saturation, can safely increase volume
        31-60: Moderate saturation, maintain current volume
        61-100: High saturation, should reduce volume or improve content

    Opportunity Score Interpretation:
        0-30: Low opportunity, content/targeting needs improvement
        31-60: Moderate opportunity, standard performance
        61-100: High opportunity, excellent time to expand

    Args:
        creator_id: The creator_id or page_name to look up.
        period: Tracking period for analysis. Must be one of:
            - '7d': 7-day rolling window (short-term trends)
            - '14d': 14-day rolling window (recommended, balanced view)
            - '30d': 30-day rolling window (long-term trends)

    Returns:
        Dictionary containing:
            - tracking_date: Date of the analysis
            - tracking_period: Echo of period parameter
            - avg_daily_volume: Average messages sent per day
            - total_messages_sent: Total messages in period
            - avg_revenue_per_send: Average $ earned per message
            - avg_view_rate: Fraction of messages viewed (0-1)
            - avg_purchase_rate: Fraction of views that purchased (0-1)
            - total_earnings: Total $ earned in period
            - revenue_per_send_trend: "increasing" | "stable" | "declining"
            - view_rate_trend: "increasing" | "stable" | "declining"
            - purchase_rate_trend: "increasing" | "stable" | "declining"
            - earnings_volatility: Coefficient of variation (higher = more volatile)
            - saturation_score: 0-100 saturation indicator
            - opportunity_score: 0-100 opportunity indicator
            - recommended_volume_delta: Suggested change (+/- messages per day)
            - calculated_at: Timestamp of calculation

    Raises:
        ValueError: If period is not '7d', '14d', or '30d'.
        DatabaseError: If database query fails.

    Example:
        >>> trends = get_performance_trends("alexia", period="14d")
        >>> print(f"Saturation: {trends['saturation_score']}/100")
        >>> print(f"Opportunity: {trends['opportunity_score']}/100")
        >>> if trends['saturation_score'] > 60:
        ...     print("Warning: High saturation detected")
    """
    conn = get_db_connection()
    try:
        if period not in ("7d", "14d", "30d"):
            return {"error": "period must be '7d', '14d', or '30d'"}

        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        cursor = conn.execute(
            """
            SELECT
                tracking_date,
                tracking_period,
                avg_daily_volume,
                total_messages_sent,
                avg_revenue_per_send,
                avg_view_rate,
                avg_purchase_rate,
                total_earnings,
                revenue_per_send_trend,
                view_rate_trend,
                purchase_rate_trend,
                earnings_volatility,
                saturation_score,
                opportunity_score,
                recommended_volume_delta,
                calculated_at
            FROM volume_performance_tracking
            WHERE creator_id = ? AND tracking_period = ?
            ORDER BY tracking_date DESC
            LIMIT 1
            """,
            (resolved_creator_id, period)
        )
        tracking = row_to_dict(cursor.fetchone())

        if not tracking:
            return {
                "saturation_score": None,
                "opportunity_score": None,
                "message": f"No performance tracking data found for period {period}"
            }

        return tracking
    finally:
        conn.close()


@mcp_tool(
    name="get_content_type_rankings",
    description="Get ranked content types (TOP/MID/LOW/AVOID) from top_content_types analysis.",
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
def get_content_type_rankings(creator_id: str) -> dict[str, Any]:
    """
    Get ranked content types (TOP/MID/LOW/AVOID) from top_content_types.

    Args:
        creator_id: The creator_id or page_name.

    Returns:
        Dictionary containing:
            - rankings: Full list of content type rankings
            - top_types: List of content types with 'TOP' tier
            - mid_types: List of content types with 'MID' tier
            - low_types: List of content types with 'LOW' tier
            - avoid_types: List of content types with 'AVOID' tier
            - analysis_date: Date of the analysis
    """
    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Get most recent analysis date for this creator
        cursor = conn.execute(
            """
            SELECT MAX(analysis_date) AS latest_date
            FROM top_content_types
            WHERE creator_id = ?
            """,
            (resolved_creator_id,)
        )
        date_row = cursor.fetchone()
        latest_date = date_row["latest_date"] if date_row else None

        if not latest_date:
            return {
                "rankings": [],
                "top_types": [],
                "mid_types": [],
                "low_types": [],
                "avoid_types": [],
                "message": "No content type analysis found"
            }

        cursor = conn.execute(
            """
            SELECT
                content_type,
                rank,
                send_count,
                total_earnings,
                avg_earnings,
                avg_purchase_rate,
                avg_rps,
                performance_tier,
                recommendation,
                confidence_score
            FROM top_content_types
            WHERE creator_id = ? AND analysis_date = ?
            ORDER BY rank ASC
            """,
            (resolved_creator_id, latest_date)
        )
        rankings = rows_to_list(cursor.fetchall())

        # Categorize by tier
        top_types = [r["content_type"] for r in rankings if r["performance_tier"] == "TOP"]
        mid_types = [r["content_type"] for r in rankings if r["performance_tier"] == "MID"]
        low_types = [r["content_type"] for r in rankings if r["performance_tier"] == "LOW"]
        avoid_types = [r["content_type"] for r in rankings if r["performance_tier"] == "AVOID"]

        return {
            "rankings": rankings,
            "top_types": top_types,
            "mid_types": mid_types,
            "low_types": low_types,
            "avoid_types": avoid_types,
            "analysis_date": latest_date
        }
    finally:
        conn.close()
