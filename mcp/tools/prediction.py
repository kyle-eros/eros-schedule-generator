"""
EROS MCP Server Prediction Tools

Tools for ML-style caption performance prediction with self-improving feedback loops.
Part of Pipeline Supercharge v3.0.0.

Includes:
- get_caption_predictions: Get performance predictions for candidate captions
- save_caption_prediction: Save a prediction for outcome tracking
- record_prediction_outcome: Record actual performance for learning
- get_prediction_weights: Get current feature weights
- update_prediction_weights: Update weights based on outcomes

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

# Valid feature categories
VALID_FEATURE_CATEGORIES = frozenset({
    "structural",
    "performance",
    "temporal",
    "creator",
})

# Maximum limits for security
MAX_CAPTION_IDS = 100
MAX_FEATURES_JSON_LENGTH = 10000


@mcp_tool(
    name="get_caption_predictions",
    description="Get ML-style performance predictions for candidate captions. Returns predicted RPS, open rate, and conversion rate with confidence scores.",
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
                "description": "List of caption IDs to get predictions for"
            },
            "include_features": {
                "type": "boolean",
                "description": "Include feature breakdown in response (default false)"
            }
        },
        "required": ["creator_id", "caption_ids"]
    }
)
def get_caption_predictions(
    creator_id: str,
    caption_ids: list[int],
    include_features: bool = False
) -> dict[str, Any]:
    """
    Get ML-style performance predictions for candidate captions.

    Retrieves existing predictions from caption_predictions table or returns
    empty predictions for captions without stored predictions.

    Args:
        creator_id: The creator_id or page_name.
        caption_ids: List of caption IDs to get predictions for.
        include_features: Whether to include feature breakdown.

    Returns:
        Dictionary containing:
            - predictions: List of prediction objects with scores
            - count: Number of predictions returned
            - missing_ids: Caption IDs without predictions
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"get_caption_predictions: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if not caption_ids:
        return {"error": "caption_ids cannot be empty"}

    if len(caption_ids) > MAX_CAPTION_IDS:
        return {"error": f"caption_ids exceeds maximum of {MAX_CAPTION_IDS} items"}

    # Validate all IDs are positive integers
    for idx, cap_id in enumerate(caption_ids):
        if not isinstance(cap_id, int) or cap_id <= 0:
            return {"error": f"caption_ids[{idx}] must be a positive integer"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Build query for predictions
        placeholders = ",".join(["?" for _ in caption_ids])
        query = f"""
            SELECT
                prediction_id,
                caption_id,
                predicted_rps,
                predicted_open_rate,
                predicted_conversion_rate,
                confidence_score,
                prediction_score,
                {"features_json," if include_features else ""}
                model_version,
                predicted_at
            FROM caption_predictions
            WHERE creator_id = ?
            AND caption_id IN ({placeholders})
            ORDER BY prediction_score DESC
        """
        params = [resolved_creator_id] + caption_ids

        cursor = conn.execute(query, params)
        predictions = rows_to_list(cursor.fetchall())

        # Parse features_json if included
        if include_features:
            for pred in predictions:
                if pred.get("features_json"):
                    try:
                        pred["features"] = json.loads(pred["features_json"])
                    except json.JSONDecodeError:
                        pred["features"] = {}
                    del pred["features_json"]

        # Find missing caption IDs
        found_ids = {pred["caption_id"] for pred in predictions}
        missing_ids = [cap_id for cap_id in caption_ids if cap_id not in found_ids]

        return {
            "predictions": predictions,
            "count": len(predictions),
            "missing_ids": missing_ids,
            "creator_id": resolved_creator_id,
        }

    except sqlite3.Error as e:
        logger.error(f"get_caption_predictions: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


@mcp_tool(
    name="save_caption_prediction",
    description="Save a caption performance prediction for outcome tracking. Used by content-performance-predictor agent.",
    schema={
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "description": "The creator_id or page_name"
            },
            "caption_id": {
                "type": "integer",
                "description": "The caption ID being predicted"
            },
            "predicted_rps": {
                "type": "number",
                "description": "Predicted revenue per send"
            },
            "predicted_open_rate": {
                "type": "number",
                "description": "Predicted open rate (0.0-1.0)"
            },
            "predicted_conversion_rate": {
                "type": "number",
                "description": "Predicted conversion rate (0.0-1.0)"
            },
            "confidence_score": {
                "type": "number",
                "description": "Confidence in prediction (0.0-1.0)"
            },
            "prediction_score": {
                "type": "number",
                "description": "Composite prediction score (0-100)"
            },
            "features_json": {
                "type": "string",
                "description": "JSON string of feature values used"
            },
            "schedule_id": {
                "type": "integer",
                "description": "Optional schedule template ID if scheduled"
            }
        },
        "required": ["creator_id", "caption_id", "predicted_rps", "confidence_score", "prediction_score", "features_json"]
    }
)
def save_caption_prediction(
    creator_id: str,
    caption_id: int,
    predicted_rps: float,
    confidence_score: float,
    prediction_score: float,
    features_json: str,
    predicted_open_rate: Optional[float] = None,
    predicted_conversion_rate: Optional[float] = None,
    schedule_id: Optional[int] = None
) -> dict[str, Any]:
    """
    Save a caption performance prediction for outcome tracking.

    Creates a record in caption_predictions table for later comparison
    with actual performance to enable self-improving predictions.

    Args:
        creator_id: The creator_id or page_name.
        caption_id: The caption ID being predicted.
        predicted_rps: Predicted revenue per send.
        predicted_open_rate: Predicted open rate (optional).
        predicted_conversion_rate: Predicted conversion rate (optional).
        confidence_score: Confidence in prediction (0.0-1.0).
        prediction_score: Composite prediction score (0-100).
        features_json: JSON string of feature values used.
        schedule_id: Optional schedule template ID.

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - prediction_id: ID of created prediction record
    """
    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"save_caption_prediction: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    if not isinstance(caption_id, int) or caption_id <= 0:
        return {"error": "caption_id must be a positive integer"}

    if not isinstance(predicted_rps, (int, float)):
        return {"error": "predicted_rps must be a number"}

    if not 0.0 <= confidence_score <= 1.0:
        return {"error": "confidence_score must be between 0.0 and 1.0"}

    if not 0.0 <= prediction_score <= 100.0:
        return {"error": "prediction_score must be between 0 and 100"}

    if len(features_json) > MAX_FEATURES_JSON_LENGTH:
        return {"error": f"features_json exceeds maximum length of {MAX_FEATURES_JSON_LENGTH}"}

    # Validate features_json is valid JSON
    try:
        json.loads(features_json)
    except json.JSONDecodeError:
        return {"error": "features_json must be valid JSON"}

    conn = get_db_connection()
    try:
        # Resolve creator_id
        resolved_creator_id = resolve_creator_id(conn, creator_id)
        if not resolved_creator_id:
            return {"error": f"Creator not found: {creator_id}"}

        # Verify caption exists
        cursor = conn.execute(
            "SELECT caption_id FROM caption_bank WHERE caption_id = ?",
            (caption_id,)
        )
        if not cursor.fetchone():
            return {"error": f"Caption not found: {caption_id}"}

        # Insert prediction
        cursor = conn.execute(
            """
            INSERT INTO caption_predictions (
                creator_id, caption_id, predicted_rps,
                predicted_open_rate, predicted_conversion_rate,
                confidence_score, prediction_score, features_json,
                schedule_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_creator_id,
                caption_id,
                predicted_rps,
                predicted_open_rate,
                predicted_conversion_rate,
                confidence_score,
                prediction_score,
                features_json,
                schedule_id,
            )
        )
        conn.commit()

        prediction_id = cursor.lastrowid

        logger.info(
            f"save_caption_prediction: Saved prediction {prediction_id} "
            f"for caption {caption_id}, creator {resolved_creator_id}"
        )

        return {
            "success": True,
            "prediction_id": prediction_id,
            "caption_id": caption_id,
            "creator_id": resolved_creator_id,
        }

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"save_caption_prediction: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


@mcp_tool(
    name="record_prediction_outcome",
    description="Record actual performance vs predicted for feedback loop learning. Called after send completes.",
    schema={
        "type": "object",
        "properties": {
            "prediction_id": {
                "type": "integer",
                "description": "The prediction ID to record outcome for"
            },
            "actual_rps": {
                "type": "number",
                "description": "Actual revenue per send achieved"
            },
            "actual_open_rate": {
                "type": "number",
                "description": "Actual open rate achieved (0.0-1.0)"
            },
            "actual_conversion_rate": {
                "type": "number",
                "description": "Actual conversion rate achieved (0.0-1.0)"
            },
            "sent_at": {
                "type": "string",
                "description": "ISO timestamp when the send occurred"
            }
        },
        "required": ["prediction_id", "actual_rps", "sent_at"]
    }
)
def record_prediction_outcome(
    prediction_id: int,
    actual_rps: float,
    sent_at: str,
    actual_open_rate: Optional[float] = None,
    actual_conversion_rate: Optional[float] = None
) -> dict[str, Any]:
    """
    Record actual performance vs predicted for feedback loop learning.

    Compares actual performance with the prediction and calculates
    error metrics for model improvement.

    Args:
        prediction_id: The prediction ID to record outcome for.
        actual_rps: Actual revenue per send achieved.
        actual_open_rate: Actual open rate achieved.
        actual_conversion_rate: Actual conversion rate achieved.
        sent_at: ISO timestamp when the send occurred.

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - outcome_id: ID of created outcome record
            - rps_error: Difference between actual and predicted
            - rps_error_pct: Percentage error
    """
    if not isinstance(prediction_id, int) or prediction_id <= 0:
        return {"error": "prediction_id must be a positive integer"}

    if not isinstance(actual_rps, (int, float)):
        return {"error": "actual_rps must be a number"}

    # Validate sent_at format
    try:
        datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
    except ValueError:
        return {"error": "sent_at must be in ISO format"}

    conn = get_db_connection()
    try:
        # Get the original prediction
        cursor = conn.execute(
            """
            SELECT prediction_id, predicted_rps
            FROM caption_predictions
            WHERE prediction_id = ?
            """,
            (prediction_id,)
        )
        prediction = cursor.fetchone()
        if not prediction:
            return {"error": f"Prediction not found: {prediction_id}"}

        predicted_rps = prediction["predicted_rps"]

        # Calculate error metrics
        rps_error = actual_rps - predicted_rps
        rps_error_pct = None
        if predicted_rps != 0:
            rps_error_pct = (rps_error / predicted_rps) * 100

        # Insert outcome
        cursor = conn.execute(
            """
            INSERT INTO prediction_outcomes (
                prediction_id, actual_rps, actual_open_rate,
                actual_conversion_rate, rps_error, rps_error_pct, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prediction_id,
                actual_rps,
                actual_open_rate,
                actual_conversion_rate,
                rps_error,
                rps_error_pct,
                sent_at,
            )
        )
        conn.commit()

        outcome_id = cursor.lastrowid

        logger.info(
            f"record_prediction_outcome: Recorded outcome {outcome_id} "
            f"for prediction {prediction_id}, error: {rps_error:.2f}"
        )

        return {
            "success": True,
            "outcome_id": outcome_id,
            "prediction_id": prediction_id,
            "rps_error": round(rps_error, 2),
            "rps_error_pct": round(rps_error_pct, 2) if rps_error_pct is not None else None,
        }

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"record_prediction_outcome: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


@mcp_tool(
    name="get_prediction_weights",
    description="Get current feature weights for the prediction model. Used by content-performance-predictor for scoring.",
    schema={
        "type": "object",
        "properties": {
            "feature_category": {
                "type": "string",
                "enum": ["structural", "performance", "temporal", "creator"],
                "description": "Optional filter by feature category"
            },
            "active_only": {
                "type": "boolean",
                "description": "Only return active weights (default true)"
            }
        }
    }
)
def get_prediction_weights(
    feature_category: Optional[str] = None,
    active_only: bool = True
) -> dict[str, Any]:
    """
    Get current feature weights for the prediction model.

    Returns the weights used to calculate prediction scores,
    organized by feature category.

    Args:
        feature_category: Optional filter by category.
        active_only: Only return active weights.

    Returns:
        Dictionary containing:
            - weights: List of weight objects
            - count: Number of weights returned
            - categories: Summary by category
    """
    if feature_category and feature_category not in VALID_FEATURE_CATEGORIES:
        return {
            "error": f"Invalid feature_category. Must be one of: {', '.join(sorted(VALID_FEATURE_CATEGORIES))}"
        }

    conn = get_db_connection()
    try:
        # Build query
        query = """
            SELECT
                weight_id,
                feature_name,
                feature_category,
                current_weight,
                previous_weight,
                initial_weight,
                adjustment_count,
                last_adjustment,
                last_updated,
                min_weight,
                max_weight,
                is_active
            FROM prediction_weights
            WHERE 1=1
        """
        params: list[Any] = []

        if active_only:
            query += " AND is_active = 1"

        if feature_category:
            query += " AND feature_category = ?"
            params.append(feature_category)

        query += " ORDER BY feature_category, feature_name"

        cursor = conn.execute(query, params)
        weights = rows_to_list(cursor.fetchall())

        # Calculate category summaries
        categories: dict[str, dict[str, Any]] = {}
        for weight in weights:
            cat = weight["feature_category"]
            if cat not in categories:
                categories[cat] = {"count": 0, "avg_weight": 0.0, "features": []}
            categories[cat]["count"] += 1
            categories[cat]["avg_weight"] += weight["current_weight"]
            categories[cat]["features"].append(weight["feature_name"])

        # Calculate averages
        for cat in categories:
            if categories[cat]["count"] > 0:
                categories[cat]["avg_weight"] = round(
                    categories[cat]["avg_weight"] / categories[cat]["count"], 3
                )

        return {
            "weights": weights,
            "count": len(weights),
            "categories": categories,
        }

    except sqlite3.Error as e:
        logger.error(f"get_prediction_weights: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


@mcp_tool(
    name="update_prediction_weights",
    description="Update feature weights based on prediction outcomes. Called periodically to improve model accuracy.",
    schema={
        "type": "object",
        "properties": {
            "weight_updates": {
                "type": "array",
                "description": "List of weight updates to apply",
                "items": {
                    "type": "object",
                    "properties": {
                        "feature_name": {
                            "type": "string",
                            "description": "Name of the feature to update"
                        },
                        "new_weight": {
                            "type": "number",
                            "description": "New weight value"
                        }
                    },
                    "required": ["feature_name", "new_weight"]
                }
            }
        },
        "required": ["weight_updates"]
    }
)
def update_prediction_weights(
    weight_updates: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Update feature weights based on prediction outcomes.

    Updates weights within their min/max bounds and tracks
    adjustment history for model evolution.

    Args:
        weight_updates: List of dicts with feature_name and new_weight.

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - updated_count: Number of weights updated
            - skipped: List of features skipped (not found or out of bounds)
    """
    if not weight_updates:
        return {"error": "weight_updates cannot be empty"}

    if len(weight_updates) > 50:
        return {"error": "weight_updates exceeds maximum of 50 items"}

    conn = get_db_connection()
    try:
        updated_count = 0
        skipped: list[dict[str, Any]] = []

        for update in weight_updates:
            feature_name = update.get("feature_name")
            new_weight = update.get("new_weight")

            if not feature_name or new_weight is None:
                skipped.append({
                    "feature_name": feature_name,
                    "reason": "missing required fields"
                })
                continue

            # Get current weight and bounds
            cursor = conn.execute(
                """
                SELECT weight_id, current_weight, min_weight, max_weight, is_active
                FROM prediction_weights
                WHERE feature_name = ?
                """,
                (feature_name,)
            )
            existing = cursor.fetchone()

            if not existing:
                skipped.append({
                    "feature_name": feature_name,
                    "reason": "feature not found"
                })
                continue

            if not existing["is_active"]:
                skipped.append({
                    "feature_name": feature_name,
                    "reason": "feature is inactive"
                })
                continue

            # Clamp new_weight to bounds
            min_w = existing["min_weight"]
            max_w = existing["max_weight"]
            clamped_weight = max(min_w, min(max_w, new_weight))

            if clamped_weight != new_weight:
                logger.info(
                    f"update_prediction_weights: Clamped {feature_name} "
                    f"from {new_weight} to {clamped_weight}"
                )

            # Calculate adjustment
            current = existing["current_weight"]
            adjustment = clamped_weight - current

            # Update weight
            conn.execute(
                """
                UPDATE prediction_weights
                SET current_weight = ?,
                    previous_weight = ?,
                    adjustment_count = adjustment_count + 1,
                    last_adjustment = ?,
                    last_updated = datetime('now')
                WHERE feature_name = ?
                """,
                (clamped_weight, current, adjustment, feature_name)
            )
            updated_count += 1

        conn.commit()

        logger.info(
            f"update_prediction_weights: Updated {updated_count} weights, "
            f"skipped {len(skipped)}"
        )

        return {
            "success": True,
            "updated_count": updated_count,
            "skipped": skipped if skipped else None,
        }

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"update_prediction_weights: Database error - {e}")
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()
