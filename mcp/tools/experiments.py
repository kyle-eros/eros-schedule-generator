"""
EROS MCP Server Experiments Tools

Tools for A/B testing orchestration and experiment management.
Part of Pipeline Supercharge v3.0.0.

Includes:
- get_active_experiments: Get active experiments for a creator
- save_experiment_results: Save A/B test results
- update_experiment_allocation: Update experiment traffic allocation

Version: 3.0.0
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Optional

from mcp.connection import get_db_connection
from mcp.tools.base import mcp_tool
from mcp.utils.helpers import resolve_creator_id, rows_to_list, row_to_dict
from mcp.utils.security import validate_creator_id

logger = logging.getLogger("eros_db_server")

# Valid experiment types
VALID_EXPERIMENT_TYPES = frozenset({
    "caption_style",
    "timing_slots",
    "price_points",
    "content_order",
    "followup_delay",
})

# Valid experiment statuses
VALID_EXPERIMENT_STATUSES = frozenset({
    "DRAFT",
    "RUNNING",
    "PAUSED",
    "COMPLETED",
    "CANCELLED",
})


@mcp_tool(
    name="get_active_experiments",
    description="Get active A/B experiments for a creator. Used by ab-testing-orchestrator agent.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "experiment_type": {
                "type": "string",
                "enum": ["caption_style", "timing_slots", "price_points", "content_order", "followup_delay"],
                "description": "Optional filter by experiment type"
            },
            "include_variants": {
                "type": "boolean",
                "description": "Include variant details (default true)"
            },
            "include_results": {
                "type": "boolean",
                "description": "Include latest results (default false)"
            }
        },
        "required": ["creator_id"]
    }
)
def get_active_experiments(
    creator_id: str,
    experiment_type: Optional[str] = None,
    include_variants: bool = True,
    include_results: bool = False
) -> dict[str, Any]:
    """
    Get active A/B experiments for a creator.

    Returns experiments with status 'RUNNING' or 'PAUSED',
    optionally including variants and latest results.

    Args:
        creator_id: The creator_id or page_name.
        experiment_type: Optional filter by type.
        include_variants: Include variant configurations.
        include_results: Include latest measurement results.

    Returns:
        Dictionary containing:
            - experiments: List of experiment objects
            - count: Number of experiments
            - summary: Experiment counts by type and status
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_active_experiments: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if experiment_type and experiment_type not in VALID_EXPERIMENT_TYPES:
        return {
            "error": f"Invalid experiment_type. Must be one of: {', '.join(sorted(VALID_EXPERIMENT_TYPES))}"
        }

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Build experiments query
        query = """
            SELECT
                experiment_id,
                experiment_name,
                experiment_type,
                hypothesis,
                traffic_allocation,
                min_sample_size,
                significance_level,
                minimum_detectable_effect,
                status,
                winning_variant_id,
                winner_confidence,
                start_date,
                end_date,
                created_at,
                updated_at
            FROM ab_experiments
            WHERE creator_id = ?
            AND status IN ('RUNNING', 'PAUSED')
        """
        params: list[Any] = [resolved_creator_id]

        if experiment_type:
            query += " AND experiment_type = ?"
            params.append(experiment_type)

        query += " ORDER BY start_date DESC"

        cursor = conn.execute(query, params)
        experiments = rows_to_list(cursor.fetchall())

        # Add variants if requested
        if include_variants:
            for exp in experiments:
                cursor = conn.execute(
                    """
                    SELECT
                        variant_id,
                        variant_name,
                        variant_description,
                        is_control,
                        variant_config_json,
                        allocation_percent,
                        sample_count,
                        conversions,
                        total_revenue,
                        is_active
                    FROM experiment_variants
                    WHERE experiment_id = ?
                    AND is_active = 1
                    ORDER BY is_control DESC, variant_name
                    """,
                    (exp["experiment_id"],)
                )
                exp["variants"] = rows_to_list(cursor.fetchall())

                # Parse variant_config_json
                for variant in exp["variants"]:
                    if variant.get("variant_config_json"):
                        try:
                            variant["config"] = json.loads(variant["variant_config_json"])
                        except json.JSONDecodeError:
                            variant["config"] = {}
                        del variant["variant_config_json"]

        # Add results if requested
        if include_results:
            for exp in experiments:
                cursor = conn.execute(
                    """
                    SELECT
                        result_id,
                        variant_id,
                        metric_name,
                        metric_value,
                        sample_size,
                        vs_control_lift,
                        vs_control_p_value,
                        is_significant,
                        measurement_date
                    FROM experiment_results
                    WHERE experiment_id = ?
                    AND measurement_date = (
                        SELECT MAX(measurement_date)
                        FROM experiment_results
                        WHERE experiment_id = ?
                    )
                    ORDER BY variant_id, metric_name
                    """,
                    (exp["experiment_id"], exp["experiment_id"])
                )
                exp["latest_results"] = rows_to_list(cursor.fetchall())

        # Build summary
        type_counts: dict[str, int] = {}
        status_counts = {"RUNNING": 0, "PAUSED": 0}
        for exp in experiments:
            exp_type = exp["experiment_type"]
            type_counts[exp_type] = type_counts.get(exp_type, 0) + 1
            status_counts[exp["status"]] += 1

        summary = {
            "total_active": len(experiments),
            "by_type": type_counts,
            "by_status": status_counts,
        }

        return {
            "experiments": experiments,
            "count": len(experiments),
            "summary": summary,
            "creator_id": resolved_creator_id,
        }

    except sqlite3.Error as e:
        logger.error(f"get_active_experiments: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


@mcp_tool(
    name="save_experiment_results",
    description="Save A/B test results for a specific measurement period. Used by ab-testing-orchestrator agent.",
    schema={
        "type": "object",
        "properties": {
            "experiment_id": {
                "type": "integer",
                "description": "The experiment ID"
            },
            "results": {
                "type": "array",
                "description": "List of result measurements",
                "items": {
                    "type": "object",
                    "properties": {
                        "variant_id": {
                            "type": "integer",
                            "description": "The variant ID"
                        },
                        "metric_name": {
                            "type": "string",
                            "description": "Name of the metric (e.g., 'conversion_rate', 'rps')"
                        },
                        "metric_value": {
                            "type": "number",
                            "description": "Measured value"
                        },
                        "sample_size": {
                            "type": "integer",
                            "description": "Sample size for this measurement"
                        },
                        "standard_error": {
                            "type": "number",
                            "description": "Standard error of the measurement"
                        },
                        "vs_control_lift": {
                            "type": "number",
                            "description": "Percentage lift vs control variant"
                        },
                        "vs_control_p_value": {
                            "type": "number",
                            "description": "P-value for significance test"
                        }
                    },
                    "required": ["variant_id", "metric_name", "metric_value", "sample_size"]
                }
            },
            "measurement_date": {
                "type": "string",
                "description": "Date of measurement (YYYY-MM-DD format)"
            }
        },
        "required": ["experiment_id", "results"]
    }
)
def save_experiment_results(
    experiment_id: int,
    results: list[dict[str, Any]],
    measurement_date: Optional[str] = None
) -> dict[str, Any]:
    """
    Save A/B test results for a specific measurement period.

    Records metrics for each variant with statistical analysis
    against the control variant.

    Args:
        experiment_id: The experiment ID.
        results: List of result measurements.
        measurement_date: Date of measurement (defaults to today).

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - results_saved: Number of results saved
            - significant_findings: List of statistically significant results
    """
    if not isinstance(experiment_id, int) or experiment_id <= 0:
        return {"error": "experiment_id must be a positive integer"}

    if not results:
        return {"error": "results cannot be empty"}

    if len(results) > 100:
        return {"error": "results exceeds maximum of 100 items"}

    # Validate measurement_date
    if measurement_date:
        try:
            datetime.strptime(measurement_date, "%Y-%m-%d")
        except ValueError:
            return {"error": "measurement_date must be in YYYY-MM-DD format"}
    else:
        measurement_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    try:
        # Verify experiment exists and is active
        cursor = conn.execute(
            """
            SELECT experiment_id, significance_level, status
            FROM ab_experiments
            WHERE experiment_id = ?
            """,
            (experiment_id,)
        )
        experiment = cursor.fetchone()
        if not experiment:
            return {"error": f"Experiment not found: {experiment_id}"}

        if experiment["status"] not in ("RUNNING", "PAUSED"):
            return {"error": f"Experiment is not active (status: {experiment['status']})"}

        significance_level = experiment["significance_level"]

        # Get valid variant IDs for this experiment
        cursor = conn.execute(
            "SELECT variant_id FROM experiment_variants WHERE experiment_id = ?",
            (experiment_id,)
        )
        valid_variant_ids = {row["variant_id"] for row in cursor.fetchall()}

        results_saved = 0
        significant_findings: list[dict[str, Any]] = []

        for result in results:
            variant_id = result.get("variant_id")
            metric_name = result.get("metric_name")
            metric_value = result.get("metric_value")
            sample_size = result.get("sample_size")

            # Validate required fields
            if not variant_id or not metric_name or metric_value is None or sample_size is None:
                continue

            if variant_id not in valid_variant_ids:
                continue

            # Calculate if significant
            p_value = result.get("vs_control_p_value")
            is_significant = 1 if p_value is not None and p_value < significance_level else 0

            # Calculate confidence intervals if standard error provided
            se = result.get("standard_error")
            ci_low = None
            ci_high = None
            if se is not None:
                # 95% CI approximation
                ci_low = metric_value - (1.96 * se)
                ci_high = metric_value + (1.96 * se)

            # Insert result
            conn.execute(
                """
                INSERT INTO experiment_results (
                    experiment_id, variant_id, metric_name, metric_value,
                    sample_size, standard_error, confidence_interval_low,
                    confidence_interval_high, vs_control_lift, vs_control_p_value,
                    is_significant, measurement_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    variant_id,
                    metric_name,
                    metric_value,
                    sample_size,
                    se,
                    ci_low,
                    ci_high,
                    result.get("vs_control_lift"),
                    p_value,
                    is_significant,
                    measurement_date,
                )
            )
            results_saved += 1

            # Track significant findings
            if is_significant:
                significant_findings.append({
                    "variant_id": variant_id,
                    "metric_name": metric_name,
                    "lift": result.get("vs_control_lift"),
                    "p_value": p_value,
                })

            # Update variant sample_count and conversions
            if metric_name == "conversions":
                conn.execute(
                    """
                    UPDATE experiment_variants
                    SET sample_count = sample_count + ?,
                        conversions = conversions + ?
                    WHERE variant_id = ?
                    """,
                    (sample_size, int(metric_value), variant_id)
                )

        conn.commit()

        logger.info(
            f"save_experiment_results: Saved {results_saved} results "
            f"for experiment {experiment_id}, {len(significant_findings)} significant"
        )

        return {
            "success": True,
            "results_saved": results_saved,
            "measurement_date": measurement_date,
            "significant_findings": significant_findings if significant_findings else None,
        }

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"save_experiment_results: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


@mcp_tool(
    name="update_experiment_allocation",
    description="Update experiment traffic allocation or status. Used by ab-testing-orchestrator agent.",
    schema={
        "type": "object",
        "properties": {
            "experiment_id": {
                "type": "integer",
                "description": "The experiment ID"
            },
            "traffic_allocation": {
                "type": "number",
                "description": "New overall traffic allocation (0.0-1.0)"
            },
            "variant_allocations": {
                "type": "array",
                "description": "List of variant allocation updates",
                "items": {
                    "type": "object",
                    "properties": {
                        "variant_id": {
                            "type": "integer",
                            "description": "The variant ID"
                        },
                        "allocation_percent": {
                            "type": "number",
                            "description": "New allocation percentage for this variant"
                        }
                    },
                    "required": ["variant_id", "allocation_percent"]
                }
            },
            "new_status": {
                "type": "string",
                "enum": ["RUNNING", "PAUSED", "COMPLETED", "CANCELLED"],
                "description": "New experiment status"
            },
            "winning_variant_id": {
                "type": "integer",
                "description": "Variant ID to declare as winner (when completing)"
            },
            "winner_confidence": {
                "type": "number",
                "description": "Confidence level of winner determination"
            }
        },
        "required": ["experiment_id"]
    }
)
def update_experiment_allocation(
    experiment_id: int,
    traffic_allocation: Optional[float] = None,
    variant_allocations: Optional[list[dict[str, Any]]] = None,
    new_status: Optional[str] = None,
    winning_variant_id: Optional[int] = None,
    winner_confidence: Optional[float] = None
) -> dict[str, Any]:
    """
    Update experiment traffic allocation or status.

    Can update overall traffic allocation, individual variant
    allocations, experiment status, and declare a winner.

    Args:
        experiment_id: The experiment ID.
        traffic_allocation: New overall traffic allocation.
        variant_allocations: List of variant allocation updates.
        new_status: New experiment status.
        winning_variant_id: Variant to declare as winner.
        winner_confidence: Confidence level of winner.

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - updates_applied: List of updates made
    """
    if not isinstance(experiment_id, int) or experiment_id <= 0:
        return {"error": "experiment_id must be a positive integer"}

    if traffic_allocation is not None and not (0.0 < traffic_allocation <= 1.0):
        return {"error": "traffic_allocation must be between 0.0 and 1.0"}

    if new_status and new_status not in VALID_EXPERIMENT_STATUSES:
        return {
            "error": f"Invalid new_status. Must be one of: {', '.join(sorted(VALID_EXPERIMENT_STATUSES))}"
        }

    conn = get_db_connection()
    try:
        # Verify experiment exists
        cursor = conn.execute(
            "SELECT experiment_id, status FROM ab_experiments WHERE experiment_id = ?",
            (experiment_id,)
        )
        experiment = cursor.fetchone()
        if not experiment:
            return {"error": f"Experiment not found: {experiment_id}"}

        updates_applied: list[str] = []

        # Update traffic allocation
        if traffic_allocation is not None:
            conn.execute(
                """
                UPDATE ab_experiments
                SET traffic_allocation = ?, updated_at = datetime('now')
                WHERE experiment_id = ?
                """,
                (traffic_allocation, experiment_id)
            )
            updates_applied.append(f"traffic_allocation set to {traffic_allocation}")

        # Update variant allocations
        if variant_allocations:
            for va in variant_allocations:
                variant_id = va.get("variant_id")
                alloc_pct = va.get("allocation_percent")

                if not variant_id or alloc_pct is None:
                    continue

                if not (0.0 <= alloc_pct <= 100.0):
                    continue

                cursor = conn.execute(
                    """
                    UPDATE experiment_variants
                    SET allocation_percent = ?
                    WHERE variant_id = ? AND experiment_id = ?
                    """,
                    (alloc_pct, variant_id, experiment_id)
                )
                if cursor.rowcount > 0:
                    updates_applied.append(f"variant {variant_id} allocation set to {alloc_pct}%")

        # Update status
        if new_status:
            update_fields = ["status = ?", "updated_at = datetime('now')"]
            update_params: list[Any] = [new_status]

            if new_status == "COMPLETED":
                update_fields.append("end_date = date('now')")
                if winning_variant_id is not None:
                    update_fields.append("winning_variant_id = ?")
                    update_params.append(winning_variant_id)
                if winner_confidence is not None:
                    update_fields.append("winner_confidence = ?")
                    update_params.append(winner_confidence)

            update_params.append(experiment_id)
            conn.execute(
                f"UPDATE ab_experiments SET {', '.join(update_fields)} WHERE experiment_id = ?",
                update_params
            )
            updates_applied.append(f"status changed to {new_status}")

            if winning_variant_id is not None:
                updates_applied.append(f"winner declared: variant {winning_variant_id}")

        conn.commit()

        logger.info(
            f"update_experiment_allocation: Updated experiment {experiment_id}, "
            f"{len(updates_applied)} changes"
        )

        return {
            "success": True,
            "experiment_id": experiment_id,
            "updates_applied": updates_applied,
        }

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"update_experiment_allocation: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()
