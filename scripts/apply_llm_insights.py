#!/usr/bin/env python3
"""
Apply LLM Insights - Apply Claude's semantic analysis to caption weights.

This script processes Claude's LLM analysis results and applies confidence-
adjusted boosts to caption weights for schedule generation.

The confidence adjustment algorithm:
- High confidence: Full boost applied (1.0x multiplier)
- Medium confidence: Dampened 25% toward 1.0 (0.75x multiplier)
- Low confidence: Dampened 50% toward 1.0 (0.5x multiplier)

Usage:
    cat claude_analysis.json | python apply_llm_insights.py
    python apply_llm_insights.py --input analysis.json --output enhanced_weights.json
    python apply_llm_insights.py --input analysis.json --pattern-boosts pattern.json
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

# Path resolution for database
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "database" / "eros_sd_main.db"


# Constants for validation and processing
VALID_CONFIDENCE_LEVELS = {"low", "medium", "high"}
BOOST_MIN_INPUT = 0.5
BOOST_MAX_INPUT = 1.5
BOOST_MIN_OUTPUT = 0.80
BOOST_MAX_OUTPUT = 1.40
REASONING_MAX_LENGTH = 200
BOOST_CHANGE_THRESHOLD = 0.05

# Confidence multipliers for dampening toward 1.0
CONFIDENCE_MULTIPLIERS = {
    "low": 0.5,
    "medium": 0.75,
    "high": 1.0,
}


@dataclass
class EnhancedCaption:
    """Enhanced caption with LLM-adjusted boost weights."""

    caption_id: int
    pattern_boost: float
    llm_boost: float
    final_boost: float
    llm_tone: str | None
    llm_confidence: str
    boost_change: float
    reasoning: str


def validate_llm_result(result: dict) -> tuple[bool, str]:
    """
    Validate a single LLM analysis result.

    Args:
        result: Dictionary containing LLM analysis for a caption.

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    # Check for required caption_id
    if "caption_id" not in result:
        return False, "Missing required field: caption_id"

    caption_id = result.get("caption_id")
    if not isinstance(caption_id, int):
        return False, f"caption_id must be an integer, got {type(caption_id).__name__}"

    # Validate boost is numeric and in range
    if "boost" not in result:
        return False, f"Missing required field: boost for caption_id {caption_id}"

    boost = result.get("boost")
    if not isinstance(boost, (int, float)):
        return False, f"boost must be numeric for caption_id {caption_id}, got {type(boost).__name__}"

    if not (BOOST_MIN_INPUT <= boost <= BOOST_MAX_INPUT):
        return False, (
            f"boost {boost} out of range [{BOOST_MIN_INPUT}, {BOOST_MAX_INPUT}] "
            f"for caption_id {caption_id}"
        )

    # Validate confidence level
    if "confidence" not in result:
        return False, f"Missing required field: confidence for caption_id {caption_id}"

    confidence = result.get("confidence")
    if not isinstance(confidence, str):
        return False, (
            f"confidence must be a string for caption_id {caption_id}, "
            f"got {type(confidence).__name__}"
        )

    confidence_lower = confidence.lower()
    if confidence_lower not in VALID_CONFIDENCE_LEVELS:
        return False, (
            f"confidence '{confidence}' not valid for caption_id {caption_id}. "
            f"Must be one of: {', '.join(sorted(VALID_CONFIDENCE_LEVELS))}"
        )

    return True, ""


def apply_confidence_adjustment(boost: float, confidence: str) -> float:
    """
    Apply confidence-based dampening to a boost value.

    The adjustment dampens the boost toward 1.0 based on confidence level:
    - Low confidence: 50% dampening -> 1.0 + (boost - 1.0) * 0.5
    - Medium confidence: 25% dampening -> 1.0 + (boost - 1.0) * 0.75
    - High confidence: No dampening -> full boost applied

    Args:
        boost: The raw LLM-suggested boost value.
        confidence: The confidence level ("low", "medium", or "high").

    Returns:
        The confidence-adjusted boost value.
    """
    confidence_lower = confidence.lower()
    multiplier = CONFIDENCE_MULTIPLIERS.get(confidence_lower, 0.5)

    # Dampen the deviation from 1.0 based on confidence
    adjusted = 1.0 + (boost - 1.0) * multiplier

    return adjusted


def process_llm_analysis(
    llm_results: list[dict],
    pattern_boosts: dict[int, float] | None = None,
) -> dict[str, Any]:
    """
    Process LLM analysis results and apply confidence adjustments.

    Args:
        llm_results: List of LLM analysis dictionaries for captions.
        pattern_boosts: Optional dictionary mapping caption_id to pattern-based boost.

    Returns:
        Dictionary containing:
        - summary: Processing statistics
        - enhanced_captions: List of EnhancedCaption dictionaries
        - processing_errors: List of error messages
    """
    if pattern_boosts is None:
        pattern_boosts = {}

    enhanced_captions: list[dict[str, Any]] = []
    processing_errors: list[str] = []

    # Statistics counters
    total_processed = 0
    errors_count = 0
    improved_count = 0
    unchanged_count = 0
    reduced_count = 0
    total_boost_change = 0.0

    for result in llm_results:
        # Validate the result
        is_valid, error_msg = validate_llm_result(result)

        if not is_valid:
            processing_errors.append(error_msg)
            errors_count += 1
            continue

        total_processed += 1

        caption_id = result["caption_id"]
        llm_boost = float(result["boost"])
        confidence = result["confidence"].lower()

        # Get pattern boost (default to 1.0 if not provided)
        pattern_boost = pattern_boosts.get(caption_id, 1.0)

        # Apply confidence adjustment
        adjusted_boost = apply_confidence_adjustment(llm_boost, confidence)

        # Clamp final boost to output range
        final_boost = max(BOOST_MIN_OUTPUT, min(BOOST_MAX_OUTPUT, adjusted_boost))

        # Calculate boost change from pattern boost
        boost_change = final_boost - pattern_boost

        # Categorize the change
        if boost_change > BOOST_CHANGE_THRESHOLD:
            improved_count += 1
        elif boost_change < -BOOST_CHANGE_THRESHOLD:
            reduced_count += 1
        else:
            unchanged_count += 1

        total_boost_change += abs(boost_change)

        # Extract optional fields
        llm_tone = result.get("semantic_tone")
        reasoning = result.get("reasoning", "")

        # Truncate reasoning to max length
        if len(reasoning) > REASONING_MAX_LENGTH:
            reasoning = reasoning[: REASONING_MAX_LENGTH - 3] + "..."

        # Create enhanced caption
        enhanced = EnhancedCaption(
            caption_id=caption_id,
            pattern_boost=round(pattern_boost, 4),
            llm_boost=round(llm_boost, 4),
            final_boost=round(final_boost, 4),
            llm_tone=llm_tone,
            llm_confidence=confidence,
            boost_change=round(boost_change, 4),
            reasoning=reasoning,
        )

        enhanced_captions.append(asdict(enhanced))

    # Calculate average boost change
    avg_boost_change = (
        round(total_boost_change / total_processed, 4) if total_processed > 0 else 0.0
    )

    # Build summary
    summary = {
        "total_processed": total_processed,
        "errors": errors_count,
        "improved_boost": improved_count,
        "unchanged_boost": unchanged_count,
        "reduced_boost": reduced_count,
        "avg_boost_change": avg_boost_change,
    }

    return {
        "summary": summary,
        "enhanced_captions": enhanced_captions,
        "processing_errors": processing_errors,
    }


def extract_results_list(data: Any) -> list[dict]:
    """
    Extract the results list from various input formats.

    Handles:
    - Direct list input: [...]
    - Wrapped dict with "results" key: {"results": [...]}
    - Wrapped dict with "captions" key: {"captions": [...]}

    Args:
        data: The parsed JSON data.

    Returns:
        List of result dictionaries.

    Raises:
        ValueError: If the input format is not recognized.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Check for common wrapper keys
        if "results" in data:
            results = data["results"]
            if isinstance(results, list):
                return results
            raise ValueError("'results' key must contain a list")

        if "captions" in data:
            captions = data["captions"]
            if isinstance(captions, list):
                return captions
            raise ValueError("'captions' key must contain a list")

        raise ValueError(
            "Dictionary input must have 'results' or 'captions' key containing a list"
        )

    raise ValueError(f"Unexpected input type: {type(data).__name__}")


def load_json_file(filepath: str) -> Any:
    """
    Load JSON data from a file.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Parsed JSON data.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_stdin() -> Any:
    """
    Load JSON data from stdin.

    Returns:
        Parsed JSON data.

    Raises:
        json.JSONDecodeError: If stdin contains invalid JSON.
    """
    return json.load(sys.stdin)


def write_output(data: dict[str, Any], output_path: str | None) -> None:
    """
    Write output data as JSON.

    Args:
        data: Dictionary to serialize as JSON.
        output_path: File path to write to, or None for stdout.
    """
    json_output = json.dumps(data, indent=2, ensure_ascii=False)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_output)
            f.write("\n")
    else:
        print(json_output)


# =============================================================================
# DATABASE PERSISTENCE FOR LLM INSIGHTS (Feedback Loop)
# =============================================================================

CREATE_INSIGHTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_caption_insights (
    insight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    caption_id INTEGER NOT NULL,
    creator_id TEXT,
    llm_boost REAL NOT NULL,
    llm_confidence TEXT NOT NULL,
    final_boost REAL NOT NULL,
    pattern_boost REAL DEFAULT 1.0,
    boost_change REAL,
    semantic_tone TEXT,
    reasoning TEXT,
    analysis_date TEXT NOT NULL,
    schedule_week TEXT,
    actual_revenue REAL,
    actual_purchase_rate REAL,
    prediction_accurate INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (caption_id) REFERENCES caption_bank(caption_id)
);

-- Index for fast lookups by caption and date
CREATE INDEX IF NOT EXISTS idx_llm_insights_caption_date
ON llm_caption_insights(caption_id, analysis_date);

-- Index for feedback loop queries (finding insights with actual results)
CREATE INDEX IF NOT EXISTS idx_llm_insights_feedback
ON llm_caption_insights(actual_revenue, prediction_accurate);
"""


def ensure_insights_table_exists(conn: sqlite3.Connection) -> None:
    """Create the llm_caption_insights table if it doesn't exist."""
    conn.executescript(CREATE_INSIGHTS_TABLE_SQL)
    conn.commit()


def persist_insights_to_database(
    enhanced_captions: list[dict[str, Any]],
    creator_id: str | None = None,
    schedule_week: str | None = None,
    db_path: Path | None = None
) -> int:
    """
    Persist LLM insights to database for feedback loop and learning.

    This enables:
    - Tracking which LLM boosts led to actual revenue
    - Learning from prediction accuracy over time
    - Building a corpus of validated semantic analyses

    Args:
        enhanced_captions: List of EnhancedCaption dictionaries from process_llm_analysis
        creator_id: Optional creator ID to associate with insights
        schedule_week: Optional week identifier (e.g., "2025-W01")
        db_path: Optional database path (defaults to standard location)

    Returns:
        Number of insights persisted
    """
    if db_path is None:
        db_path = DB_PATH

    if not db_path.exists():
        print(f"Warning: Database not found at {db_path}, skipping persistence", file=sys.stderr)
        return 0

    analysis_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persisted_count = 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Ensure table exists
        ensure_insights_table_exists(conn)

        # Insert insights
        insert_sql = """
            INSERT INTO llm_caption_insights (
                caption_id, creator_id, llm_boost, llm_confidence, final_boost,
                pattern_boost, boost_change, semantic_tone, reasoning,
                analysis_date, schedule_week
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for caption in enhanced_captions:
            try:
                conn.execute(insert_sql, (
                    caption["caption_id"],
                    creator_id,
                    caption["llm_boost"],
                    caption["llm_confidence"],
                    caption["final_boost"],
                    caption["pattern_boost"],
                    caption["boost_change"],
                    caption.get("llm_tone"),
                    caption.get("reasoning"),
                    analysis_date,
                    schedule_week
                ))
                persisted_count += 1
            except sqlite3.Error as e:
                print(f"Warning: Failed to persist caption {caption['caption_id']}: {e}", file=sys.stderr)

        conn.commit()

    finally:
        conn.close()

    return persisted_count


def update_insight_with_actual_results(
    caption_id: int,
    analysis_date: str,
    actual_revenue: float,
    actual_purchase_rate: float,
    db_path: Path | None = None
) -> bool:
    """
    Update an insight record with actual performance results.

    Called after a schedule has been executed to complete the feedback loop.

    Args:
        caption_id: The caption ID
        analysis_date: The analysis date to match
        actual_revenue: Actual revenue generated
        actual_purchase_rate: Actual purchase rate achieved
        db_path: Optional database path

    Returns:
        True if update succeeded, False otherwise
    """
    if db_path is None:
        db_path = DB_PATH

    if not db_path.exists():
        return False

    conn = sqlite3.connect(db_path)

    try:
        # Determine if prediction was accurate (within 20% of boost expectation)
        cursor = conn.execute(
            "SELECT final_boost FROM llm_caption_insights WHERE caption_id = ? AND analysis_date = ?",
            (caption_id, analysis_date)
        )
        row = cursor.fetchone()
        if not row:
            return False

        # Update with actual results
        conn.execute("""
            UPDATE llm_caption_insights
            SET actual_revenue = ?,
                actual_purchase_rate = ?,
                prediction_accurate = CASE
                    WHEN final_boost > 1.0 AND ? > 0 THEN 1
                    WHEN final_boost <= 1.0 AND ? = 0 THEN 1
                    ELSE 0
                END
            WHERE caption_id = ? AND analysis_date = ?
        """, (actual_revenue, actual_purchase_rate, actual_revenue, actual_revenue, caption_id, analysis_date))

        conn.commit()
        return True

    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Apply Claude's LLM semantic analysis to caption weights.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    cat claude_analysis.json | python apply_llm_insights.py
    python apply_llm_insights.py --input analysis.json --output enhanced_weights.json
    python apply_llm_insights.py --input analysis.json --persist --creator-id abc123
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="Input JSON file with LLM analysis results (default: stdin)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output JSON file for enhanced weights (default: stdout)",
    )

    parser.add_argument(
        "--pattern-boosts",
        type=str,
        default=None,
        help="JSON file with pattern-based boosts for comparison",
    )

    # Persistence options for feedback loop
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist LLM insights to database for feedback loop learning",
    )

    parser.add_argument(
        "--creator-id",
        type=str,
        default=None,
        help="Creator ID to associate with persisted insights",
    )

    parser.add_argument(
        "--week",
        type=str,
        default=None,
        help="Schedule week identifier (e.g., 2025-W01)",
    )

    parser.add_argument(
        "--db",
        type=str,
        default=str(DB_PATH),
        help=f"Database path (default: {DB_PATH})",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the script.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    args = parse_args()

    # Load input data
    try:
        if args.input:
            data = load_json_file(args.input)
        else:
            data = load_json_stdin()
    except FileNotFoundError:
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input: {e}", file=sys.stderr)
        return 1

    # Extract results list from input
    try:
        llm_results = extract_results_list(data)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Load pattern boosts if provided
    pattern_boosts: dict[int, float] | None = None
    if args.pattern_boosts:
        try:
            pattern_data = load_json_file(args.pattern_boosts)
            # Handle both dict format and list format
            if isinstance(pattern_data, dict):
                # Convert string keys to int if necessary
                pattern_boosts = {
                    int(k): float(v) for k, v in pattern_data.items()
                }
            elif isinstance(pattern_data, list):
                # Assume list of {caption_id, boost} objects
                pattern_boosts = {
                    int(item["caption_id"]): float(item.get("boost", item.get("pattern_boost", 1.0)))
                    for item in pattern_data
                    if "caption_id" in item
                }
            else:
                print(
                    f"Error: Pattern boosts file must contain dict or list",
                    file=sys.stderr,
                )
                return 1
        except FileNotFoundError:
            print(
                f"Error: Pattern boosts file not found: {args.pattern_boosts}",
                file=sys.stderr,
            )
            return 1
        except json.JSONDecodeError as e:
            print(
                f"Error: Invalid JSON in pattern boosts file: {e}",
                file=sys.stderr,
            )
            return 1
        except (KeyError, ValueError) as e:
            print(
                f"Error: Invalid format in pattern boosts file: {e}",
                file=sys.stderr,
            )
            return 1

    # Process the LLM analysis
    result = process_llm_analysis(llm_results, pattern_boosts)

    # Write output
    try:
        write_output(result, args.output)
    except OSError as e:
        print(f"Error: Failed to write output: {e}", file=sys.stderr)
        return 1

    # Persist to database if requested (feedback loop)
    if args.persist:
        db_path = Path(args.db)
        persisted = persist_insights_to_database(
            enhanced_captions=result["enhanced_captions"],
            creator_id=args.creator_id,
            schedule_week=args.week,
            db_path=db_path
        )
        if persisted > 0:
            print(f"Persisted {persisted} insights to database for feedback loop", file=sys.stderr)
        result["summary"]["persisted_to_database"] = persisted

    # Return non-zero if there were errors
    if result["summary"]["errors"] > 0:
        print(
            f"Warning: {result['summary']['errors']} processing errors occurred",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
