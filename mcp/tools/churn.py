"""
EROS MCP Server Churn Tools

Tools for subscriber churn risk analysis and win-back candidate identification.
Part of Pipeline Supercharge v3.0.0.

Includes:
- get_churn_risk_scores: Get churn risk by subscriber segment
- get_win_back_candidates: Get eligible subscribers for win-back campaigns

Version: 3.0.0
"""

import logging
import sqlite3
from typing import Any, Optional

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import resolve_creator_id, rows_to_list
from mcp.utils.security import validate_creator_id

logger = logging.getLogger("eros_db_server")

# Valid risk tiers
VALID_RISK_TIERS = frozenset({"LOW", "MODERATE", "HIGH", "CRITICAL"})

# Valid campaign types
VALID_CAMPAIGN_TYPES = frozenset({"LAPSED", "DECLINED", "INACTIVE"})


@mcp_tool(
    name="get_churn_risk_scores",
    description="Get churn risk scores by subscriber segment for a creator. Used by retention-risk-analyzer agent.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "min_risk_tier": {
                "type": "string",
                "enum": ["LOW", "MODERATE", "HIGH", "CRITICAL"],
                "description": "Minimum risk tier to include (default: all)"
            },
            "include_recommendations": {
                "type": "boolean",
                "description": "Include retention strategy recommendations (default true)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of segments to return (default 20)"
            }
        },
        "required": ["creator_id"]
    }
)
def get_churn_risk_scores(
    creator_id: str,
    min_risk_tier: Optional[str] = None,
    include_recommendations: bool = True,
    limit: int = 20
) -> dict[str, Any]:
    """
    Get churn risk scores by subscriber segment for a creator.

    Returns segments ordered by risk score (highest first) with
    contributing factors and retention recommendations.

    Args:
        creator_id: The creator_id or page_name.
        min_risk_tier: Minimum risk tier to include.
        include_recommendations: Include strategy recommendations.
        limit: Maximum segments to return.

    Returns:
        Dictionary containing:
            - segments: List of segment risk assessments
            - count: Number of segments returned
            - summary: Overall risk summary
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_churn_risk_scores: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if min_risk_tier and min_risk_tier not in VALID_RISK_TIERS:
        return {
            "error": f"Invalid min_risk_tier. Must be one of: {', '.join(sorted(VALID_RISK_TIERS))}"
        }

    if limit < 1 or limit > 100:
        return {"error": "limit must be between 1 and 100"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Build query
        query = """
            SELECT
                risk_id,
                segment_name,
                segment_criteria_json,
                risk_score,
                risk_tier,
                subscriber_count,
                churn_factors_json,
                top_churn_reason,
                {"retention_strategy, recommended_actions_json," if include_recommendations else ""}
                analysis_date,
                expires_at
            FROM churn_risk_scores
            WHERE creator_id = ?
            AND expires_at > datetime('now')
        """.replace(
            '{"retention_strategy, recommended_actions_json," if include_recommendations else ""}',
            "retention_strategy, recommended_actions_json," if include_recommendations else ""
        )
        params: list[Any] = [resolved_creator_id]

        # Filter by minimum risk tier
        if min_risk_tier:
            tier_order = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}
            min_tier_value = tier_order[min_risk_tier]
            # Build tier filter
            valid_tiers = [t for t, v in tier_order.items() if v >= min_tier_value]
            placeholders = ",".join(["?" for _ in valid_tiers])
            query += f" AND risk_tier IN ({placeholders})"
            params.extend(valid_tiers)

        query += " ORDER BY risk_score DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        segments = rows_to_list(cursor.fetchall())

        # Calculate summary
        total_at_risk = sum(s["subscriber_count"] for s in segments if s["risk_tier"] in ("HIGH", "CRITICAL"))
        avg_risk_score = sum(s["risk_score"] for s in segments) / len(segments) if segments else 0

        tier_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
        for s in segments:
            tier_counts[s["risk_tier"]] += 1

        summary = {
            "total_segments": len(segments),
            "total_at_risk_subscribers": total_at_risk,
            "average_risk_score": round(avg_risk_score, 2),
            "tier_distribution": tier_counts,
            "highest_risk_segment": segments[0]["segment_name"] if segments else None,
        }

        return {
            "segments": segments,
            "count": len(segments),
            "summary": summary,
            "creator_id": resolved_creator_id,
        }

    except sqlite3.Error as e:
        logger.error(f"get_churn_risk_scores: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


@mcp_tool(
    name="get_win_back_candidates",
    description="Get eligible subscribers for win-back campaigns. Used by win-back-specialist agent.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "campaign_type": {
                "type": "string",
                "enum": ["LAPSED", "DECLINED", "INACTIVE"],
                "description": "Type of win-back campaign"
            },
            "min_previous_spend": {
                "type": "number",
                "description": "Minimum previous lifetime spend to qualify"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum candidates to return (default 50)"
            }
        },
        "required": ["creator_id", "campaign_type"]
    }
)
def get_win_back_candidates(
    creator_id: str,
    campaign_type: str,
    min_previous_spend: Optional[float] = None,
    limit: int = 50
) -> dict[str, Any]:
    """
    Get eligible subscribers for win-back campaigns.

    Returns candidates based on campaign type criteria:
    - LAPSED: 30+ days inactive
    - DECLINED: Subscription declined/cancelled
    - INACTIVE: 15-30 days inactive

    Note: This returns campaign configuration and existing campaign data.
    Actual subscriber data would require integration with subscriber tables.

    Args:
        creator_id: The creator_id or page_name.
        campaign_type: Type of win-back campaign.
        min_previous_spend: Minimum previous spend to qualify.
        limit: Maximum candidates to return.

    Returns:
        Dictionary containing:
            - campaigns: Existing campaigns of this type
            - campaign_type_info: Details about the campaign type
            - recommendations: Suggested campaign settings
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_win_back_candidates: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if campaign_type not in VALID_CAMPAIGN_TYPES:
        return {
            "error": f"Invalid campaign_type. Must be one of: {', '.join(sorted(VALID_CAMPAIGN_TYPES))}"
        }

    if limit < 1 or limit > 500:
        return {"error": "limit must be between 1 and 500"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Get existing campaigns of this type
        cursor = conn.execute(
            """
            SELECT
                campaign_id,
                campaign_name,
                campaign_type,
                discount_percent,
                bundle_offer_json,
                message_template,
                target_segment,
                target_count,
                status,
                sent_count,
                opened_count,
                converted_count,
                revenue_generated,
                scheduled_at,
                started_at,
                completed_at,
                created_at
            FROM win_back_campaigns
            WHERE creator_id = ?
            AND campaign_type = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (resolved_creator_id, campaign_type, limit)
        )
        campaigns = rows_to_list(cursor.fetchall())

        # Calculate campaign performance metrics
        total_sent = sum(c["sent_count"] or 0 for c in campaigns)
        total_converted = sum(c["converted_count"] or 0 for c in campaigns)
        total_revenue = sum(c["revenue_generated"] or 0 for c in campaigns)

        performance = {
            "total_campaigns": len(campaigns),
            "total_sent": total_sent,
            "total_converted": total_converted,
            "conversion_rate": round(total_converted / total_sent * 100, 2) if total_sent > 0 else 0,
            "total_revenue": round(total_revenue, 2),
        }

        # Campaign type specific recommendations
        recommendations = {
            "LAPSED": {
                "suggested_discount": 30,
                "message_tone": "We miss you",
                "timing": "Send mid-week (Tue-Thu)",
                "typical_conversion_rate": "10-15%",
            },
            "DECLINED": {
                "suggested_discount": 25,
                "message_tone": "See what you're missing",
                "timing": "Send within 48 hours of decline",
                "typical_conversion_rate": "5-10%",
            },
            "INACTIVE": {
                "suggested_discount": 0,
                "message_tone": "Exclusive preview",
                "timing": "Send before content goes public",
                "typical_conversion_rate": "15-25%",
            },
        }

        return {
            "campaigns": campaigns,
            "count": len(campaigns),
            "campaign_type": campaign_type,
            "performance": performance,
            "recommendations": recommendations.get(campaign_type, {}),
            "creator_id": resolved_creator_id,
            "note": "Actual subscriber candidates require integration with subscriber management system",
        }

    except sqlite3.Error as e:
        logger.error(f"get_win_back_candidates: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()
