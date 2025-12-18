#!/usr/bin/env python3
"""
EROS Database MCP Server

A Model Context Protocol (MCP) server providing database access tools for the
EROS schedule generation system. Implements JSON-RPC 2.0 protocol over stdin/stdout.

This server exposes 17 tools for:
- Creator profile and performance data retrieval
- Caption selection with freshness scoring
- Optimal timing analysis
- Volume assignment management
- Content type rankings
- Send type configuration
- Channel and audience target management
- Schedule persistence

Author: EROS Development Team
Version: 2.2.0
"""

import json
import logging
import os
import re
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Optional

# Add project root to sys.path for imports from python.* modules
# This enables tools to import from python.volume, python.models, etc.
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Configure security logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("eros_db_server")


# Database path configuration - Dynamic path resolution for portability
# Note: Path is already imported above for sys.path configuration
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_DB_PATH = str(PROJECT_ROOT / "database" / "eros_sd_main.db")
DB_PATH = os.environ.get("EROS_DB_PATH", DEFAULT_DB_PATH)

# Security configuration constants
MAX_INPUT_LENGTH_CREATOR_ID = 100
MAX_INPUT_LENGTH_KEY = 50
MAX_QUERY_JOINS = 5
MAX_QUERY_SUBQUERIES = 3
MAX_QUERY_RESULT_ROWS = 10000
DB_CONNECTION_TIMEOUT = 30.0
DB_BUSY_TIMEOUT = 5000  # milliseconds


def get_db_connection() -> sqlite3.Connection:
    """
    Create a database connection with row factory for dict-like access.
    Implements security hardening with connection timeout, secure_delete pragma,
    and busy timeout for concurrent access.

    Returns:
        sqlite3.Connection: Connection with row factory and security settings configured.

    Raises:
        sqlite3.Error: If database connection fails.

    Note:
        For new code, prefer using the db_connection() context manager instead,
        which automatically handles connection cleanup.
    """
    # Create connection with timeout
    conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECTION_TIMEOUT)
    conn.row_factory = sqlite3.Row

    # Security and integrity pragmas
    conn.execute("PRAGMA foreign_keys = ON")  # Enable referential integrity enforcement
    conn.execute("PRAGMA secure_delete = ON")  # Overwrite deleted data
    conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT}")  # Wait for locks

    # Validate connection
    try:
        conn.execute("SELECT 1").fetchone()
    except sqlite3.Error as e:
        conn.close()
        raise sqlite3.Error(f"Database connection validation failed: {str(e)}")

    logger.debug("Database connection established with security settings")
    return conn


@contextmanager
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections with automatic cleanup.

    Provides a connection that is automatically closed when the context exits,
    even if an exception occurs. This is the preferred way to obtain database
    connections in new code.

    Yields:
        sqlite3.Connection: Connection with row factory and security settings configured.

    Raises:
        sqlite3.Error: If database connection fails.

    Example:
        with db_connection() as conn:
            cursor = conn.execute("SELECT * FROM creators WHERE creator_id = ?", (cid,))
            row = cursor.fetchone()
        # Connection is automatically closed here

    Example with transaction:
        with db_connection() as conn:
            conn.execute("INSERT INTO ...")
            conn.execute("UPDATE ...")
            conn.commit()
        # Connection is closed, changes are committed
    """
    conn = None
    try:
        conn = get_db_connection()
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {str(e)}")
        if conn:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass  # Ignore rollback errors
        raise
    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Database connection closed")
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {str(e)}")


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    """
    Convert a sqlite3.Row to a dictionary.

    Args:
        row: A sqlite3.Row object or None.

    Returns:
        Dictionary representation of the row, or None if row is None.
    """
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """
    Convert a list of sqlite3.Row objects to a list of dictionaries.

    Args:
        rows: List of sqlite3.Row objects.

    Returns:
        List of dictionaries.
    """
    return [dict(row) for row in rows]


# =============================================================================
# SECURITY VALIDATION HELPERS
# =============================================================================


def validate_creator_id(creator_id: str) -> tuple[bool, Optional[str]]:
    """
    Validate creator_id format and length for security.

    Args:
        creator_id: The creator_id to validate.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if not creator_id:
        return False, "creator_id cannot be empty"

    if len(creator_id) > MAX_INPUT_LENGTH_CREATOR_ID:
        return False, f"creator_id exceeds maximum length of {MAX_INPUT_LENGTH_CREATOR_ID}"

    # Allow alphanumeric, underscore, and hyphen (common in creator IDs)
    if not re.match(r'^[a-zA-Z0-9_-]+$', creator_id):
        return False, "creator_id contains invalid characters (only alphanumeric, underscore, and hyphen allowed)"

    return True, None


def validate_key_input(key: str, key_name: str = "key") -> tuple[bool, Optional[str]]:
    """
    Validate generic key inputs (send_type_key, channel_key, target_key, etc.).

    Args:
        key: The key to validate.
        key_name: Name of the key for error messages.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if not key:
        return False, f"{key_name} cannot be empty"

    if len(key) > MAX_INPUT_LENGTH_KEY:
        return False, f"{key_name} exceeds maximum length of {MAX_INPUT_LENGTH_KEY}"

    # Allow alphanumeric, underscore, and hyphen (common in keys)
    if not re.match(r'^[a-zA-Z0-9_-]+$', key):
        return False, f"{key_name} contains invalid characters (only alphanumeric, underscore, and hyphen allowed)"

    return True, None


def validate_string_length(value: str, max_length: int, field_name: str = "field") -> tuple[bool, Optional[str]]:
    """
    Validate string length for security.

    Args:
        value: The string to validate.
        max_length: Maximum allowed length.
        field_name: Name of the field for error messages.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if len(value) > max_length:
        return False, f"{field_name} exceeds maximum length of {max_length}"

    return True, None


def resolve_creator_id(conn: sqlite3.Connection, creator_id: str) -> Optional[str]:
    """
    Resolve a creator_id or page_name to the actual creator_id.

    Args:
        conn: Database connection.
        creator_id: The creator_id or page_name to look up.

    Returns:
        The resolved creator_id, or None if not found.
    """
    cursor = conn.execute(
        """
        SELECT creator_id FROM creators
        WHERE creator_id = ? OR page_name = ?
        """,
        (creator_id, creator_id)
    )
    row = cursor.fetchone()
    return row["creator_id"] if row else None


# =============================================================================
# VARIATION ANALYSIS HELPERS
# =============================================================================


def analyze_time_distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    """
    Analyze how scheduled times are distributed across hour ranges.

    Categorizes scheduled times into morning (6-11), afternoon (12-17),
    and evening (18-23) periods, plus early morning (0-5).

    Args:
        items: List of schedule items with 'scheduled_time' field (HH:MM format).

    Returns:
        Dictionary with counts per time range:
            - early_morning: 0-5 AM
            - morning: 6-11 AM
            - afternoon: 12-5 PM
            - evening: 6-11 PM
    """
    distribution = {
        "early_morning": 0,  # 0-5
        "morning": 0,        # 6-11
        "afternoon": 0,      # 12-17
        "evening": 0         # 18-23
    }

    for item in items:
        scheduled_time = item.get("scheduled_time", "")
        if not scheduled_time:
            continue

        try:
            # Parse hour from HH:MM format
            hour = int(scheduled_time.split(":")[0])

            if 0 <= hour < 6:
                distribution["early_morning"] += 1
            elif 6 <= hour < 12:
                distribution["morning"] += 1
            elif 12 <= hour < 18:
                distribution["afternoon"] += 1
            elif 18 <= hour < 24:
                distribution["evening"] += 1
        except (ValueError, IndexError):
            # Skip items with invalid time format
            continue

    return distribution


def extract_strategies(items: list[dict[str, Any]]) -> dict[str, str]:
    """
    Extract daily strategy metadata from schedule items.

    Looks for 'strategy' or 'daily_strategy' metadata fields in items
    and maps them to their scheduled dates.

    Args:
        items: List of schedule items with optional strategy metadata.

    Returns:
        Dictionary mapping date strings to strategy names.
        Example: {"2025-12-16": "aggressive_morning", "2025-12-17": "balanced_spread"}
    """
    strategies: dict[str, str] = {}

    for item in items:
        scheduled_date = item.get("scheduled_date", "")
        if not scheduled_date:
            continue

        # Check for strategy in various metadata locations
        strategy = item.get("strategy") or item.get("daily_strategy")

        # Also check nested metadata dict if present
        metadata = item.get("metadata", {})
        if isinstance(metadata, dict):
            strategy = strategy or metadata.get("strategy") or metadata.get("daily_strategy")

        if strategy and scheduled_date not in strategies:
            strategies[scheduled_date] = str(strategy)

    return strategies


def calculate_anti_pattern_score(items: list[dict[str, Any]]) -> int:
    """
    Score how well the schedule avoids templated/repetitive patterns.

    Scoring criteria (0-100):
        - Time uniqueness: No repeated exact times (0-40 points)
        - Minute variation: Not all :00/:15/:30/:45 (0-30 points)
        - Daily pattern diversity: Different time distributions per day (0-30 points)

    Higher scores indicate more authentic, less templated schedules.

    Args:
        items: List of schedule items with 'scheduled_time' and 'scheduled_date' fields.

    Returns:
        Integer score from 0-100 indicating anti-pattern quality.
    """
    if not items:
        return 100  # Empty schedule has no patterns

    score = 0.0

    # === Criterion 1: Time Uniqueness (0-40 points) ===
    # Penalize repeated exact times
    all_times = [item.get("scheduled_time", "") for item in items if item.get("scheduled_time")]
    unique_times = set(all_times)

    if len(all_times) > 0:
        uniqueness_ratio = len(unique_times) / len(all_times)
        score += uniqueness_ratio * 40

    # === Criterion 2: Minute Variation (0-30 points) ===
    # Penalize if all times are on standard intervals (:00, :15, :30, :45)
    standard_minutes = {"00", "15", "30", "45"}
    minutes_used: set[str] = set()

    for time_str in all_times:
        if time_str and ":" in time_str:
            try:
                minute = time_str.split(":")[1][:2]  # Get first 2 chars after colon
                minutes_used.add(minute)
            except IndexError:
                continue

    if minutes_used:
        # Count how many non-standard minutes are used
        non_standard_minutes = minutes_used - standard_minutes
        # Give points for using non-standard minutes
        if len(non_standard_minutes) > 0:
            # More non-standard minutes = more points (up to 30)
            variation_ratio = min(1.0, len(non_standard_minutes) / 4)  # Cap at 4+ non-standard
            score += variation_ratio * 30
        else:
            # All standard minutes - check if at least using variety
            score += (len(minutes_used) / 4) * 15  # Half points for standard variety

    # === Criterion 3: Daily Pattern Diversity (0-30 points) ===
    # Check if time patterns vary across days
    daily_times: dict[str, list[int]] = {}

    for item in items:
        date = item.get("scheduled_date", "")
        time_str = item.get("scheduled_time", "")
        if date and time_str:
            try:
                hour = int(time_str.split(":")[0])
                if date not in daily_times:
                    daily_times[date] = []
                daily_times[date].append(hour)
            except (ValueError, IndexError):
                continue

    if len(daily_times) >= 2:
        # Calculate average hour per day and check for variation
        daily_averages = []
        for hours in daily_times.values():
            if hours:
                daily_averages.append(sum(hours) / len(hours))

        if len(daily_averages) >= 2:
            # Standard deviation of daily averages
            mean_avg = sum(daily_averages) / len(daily_averages)
            variance = sum((x - mean_avg) ** 2 for x in daily_averages) / len(daily_averages)
            std_dev = variance ** 0.5

            # Higher std_dev = more daily variation = better
            # Normalize: std_dev of ~2 hours is good variety
            variation_score = min(1.0, std_dev / 2.0)
            score += variation_score * 30
        else:
            score += 15  # Only one day's worth of data
    else:
        score += 15  # Single day or no data - partial credit

    return int(round(score))


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================


def get_active_creators(
    tier: Optional[int] = None,
    page_type: Optional[str] = None
) -> dict[str, Any]:
    """
    Get all active creators with performance metrics, volume assignments, and tier classification.

    Args:
        tier: Optional filter by performance_tier (1-5).
        page_type: Optional filter by page_type ('paid' or 'free').

    Returns:
        Dictionary containing:
            - creators: List of creator records with joined volume/persona data
            - count: Total number of creators returned
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
                va.volume_level,
                va.ppv_per_day,
                va.bump_per_day,
                cp.primary_tone,
                cp.emoji_frequency,
                cp.slang_level
            FROM creators c
            LEFT JOIN volume_assignments va
                ON c.creator_id = va.creator_id AND va.is_active = 1
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


def get_creator_profile(creator_id: str) -> dict[str, Any]:
    """
    Get comprehensive profile for a single creator.

    Args:
        creator_id: The creator_id or page_name to look up.

    Returns:
        Dictionary containing:
            - creator: Basic creator information
            - analytics_summary: 30-day analytics summary
            - volume_assignment: Current volume assignment
            - top_content_types: Ranked content types for the creator
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
        page_name = row["page_name"]

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

        # Get current volume assignment
        cursor = conn.execute(
            """
            SELECT * FROM volume_assignments
            WHERE creator_id = ? AND is_active = 1
            ORDER BY assigned_at DESC
            LIMIT 1
            """,
            (resolved_creator_id,)
        )
        volume_assignment = row_to_dict(cursor.fetchone())

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

        return {
            "creator": creator,
            "analytics_summary": analytics_summary,
            "volume_assignment": volume_assignment,
            "top_content_types": top_content_types
        }
    finally:
        conn.close()


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
                INNER JOIN vault_matrix vm
                    ON cb.content_type_id = vm.content_type_id
                    AND vm.creator_id = ?
                    AND vm.has_content = 1
                LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
                LEFT JOIN caption_creator_performance ccp
                    ON cb.caption_id = ccp.caption_id
                    AND ccp.creator_id = ?
                WHERE cb.is_active = 1
                AND cb.performance_score >= ?
            """
            params: list[Any] = [send_type_id, resolved_creator_id, resolved_creator_id, min_performance]
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
                INNER JOIN vault_matrix vm
                    ON cb.content_type_id = vm.content_type_id
                    AND vm.creator_id = ?
                    AND vm.has_content = 1
                LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
                LEFT JOIN caption_creator_performance ccp
                    ON cb.caption_id = ccp.caption_id
                    AND ccp.creator_id = ?
                WHERE cb.is_active = 1
                AND cb.performance_score >= ?
            """
            params = [resolved_creator_id, resolved_creator_id, min_performance]

        if caption_type is not None:
            query += " AND cb.caption_type = ?"
            params.append(caption_type)

        if content_type is not None:
            query += " AND ct.type_name = ?"
            params.append(content_type)

        # Order by priority (if send_type provided), then freshness, then performance
        if send_type_id is not None:
            query += """
                ORDER BY freshness_score DESC, stcr.priority ASC, cb.performance_score DESC
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
            return {"error": f"Creator not found: {creator_id}"}

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


def get_volume_assignment(creator_id: str) -> dict[str, Any]:
    """
    Get current volume assignment for a creator.

    Args:
        creator_id: The creator_id or page_name.

    Returns:
        Dictionary containing:
            - volume_level: 'Low', 'Mid', 'High', or 'Ultra'
            - ppv_per_day: Number of PPVs per day
            - bump_per_day: Number of bumps per day
            - assigned_at: When the assignment was made
            - assigned_reason: Why this volume was assigned
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
                volume_level,
                ppv_per_day,
                bump_per_day,
                assigned_at,
                assigned_by,
                assigned_reason,
                notes
            FROM volume_assignments
            WHERE creator_id = ? AND is_active = 1
            ORDER BY assigned_at DESC
            LIMIT 1
            """,
            (resolved_creator_id,)
        )
        assignment = row_to_dict(cursor.fetchone())

        if not assignment:
            return {
                "volume_level": None,
                "ppv_per_day": None,
                "bump_per_day": None,
                "message": "No active volume assignment found"
            }

        return assignment
    finally:
        conn.close()


def get_performance_trends(
    creator_id: str,
    period: str = "14d"
) -> dict[str, Any]:
    """
    Get saturation/opportunity scores from volume_performance_tracking.

    Args:
        creator_id: The creator_id or page_name.
        period: Tracking period ('7d', '14d', or '30d'). Default '14d'.

    Returns:
        Dictionary containing:
            - saturation_score: 0-100 score indicating market saturation
            - opportunity_score: 0-100 score indicating growth opportunity
            - avg_revenue_per_send: Average revenue per message sent
            - view_rate_trend: Trend in view rates
            - purchase_rate_trend: Trend in purchase rates
            - recommended_volume_delta: Suggested change to volume
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


def get_persona_profile(creator_id: str) -> dict[str, Any]:
    """
    Get creator persona (tone, archetype, emoji style).

    Args:
        creator_id: The creator_id or page_name.

    Returns:
        Dictionary containing:
            - creator: Basic creator info
            - persona: Persona data from creator_personas table
            - voice_samples: Empty dict (table doesn't exist)
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


def get_vault_availability(creator_id: str) -> dict[str, Any]:
    """
    Get what content types are available in creator's vault.

    Args:
        creator_id: The creator_id or page_name.

    Returns:
        Dictionary containing:
            - available_content: List of vault entries with content type info
            - content_types: Simple list of available content type names
            - total_items: Total quantity available across all types
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


def save_schedule(
    creator_id: str,
    week_start: str,
    items: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Save generated schedule to database.

    Creates a schedule_template record and inserts all schedule_items.
    Supports both legacy item_type/channel format and new send_type_key/channel_key format.

    Args:
        creator_id: The creator_id for the schedule.
        week_start: ISO format date for week start (YYYY-MM-DD).
        items: List of schedule items, each containing:
            - scheduled_date: ISO date string (required)
            - scheduled_time: Time string HH:MM (required)
            - item_type: Legacy type of item (e.g., 'ppv', 'bump')
            - channel: Legacy 'mass_message' or 'wall_post'
            - send_type_key: New send type key (resolves to send_type_id)
            - channel_key: New channel key (resolves to channel_id)
            - target_key: Audience target key (resolves to target_id)
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

    Returns:
        Dictionary containing:
            - success: Boolean indicating success
            - template_id: ID of created template
            - items_created: Number of items inserted
            - warnings: List of validation warnings (if any)
    """
    # DEFENSIVE: Handle items as JSON string (MCP transport may serialize arrays)
    if isinstance(items, str):
        try:
            items = json.loads(items)
            logger.info(f"save_schedule: Parsed items from JSON string ({len(items)} items)")
        except json.JSONDecodeError as e:
            logger.error(f"save_schedule: Failed to parse items JSON string: {e}")
            return {"error": f"Invalid items format: expected JSON array, parse error: {str(e)}"}

    if not isinstance(items, list):
        return {"error": f"Invalid items format: expected list, got {type(items).__name__}"}

    # Validate each item is a dict
    for idx, item in enumerate(items):
        if isinstance(item, str):
            try:
                items[idx] = json.loads(item)
            except json.JSONDecodeError:
                return {"error": f"Item {idx}: expected object, got unparseable string"}
        elif not isinstance(item, dict):
            return {"error": f"Item {idx}: expected object, got {type(item).__name__}"}

    # Input validation
    is_valid, error_msg = validate_creator_id(creator_id)
    if not is_valid:
        logger.warning(f"save_schedule: Invalid creator_id - {error_msg}")
        return {"error": f"Invalid creator_id: {error_msg}"}

    # === PRE-SAVE DIVERSITY VALIDATION GATE ===

    # Backward compatibility: resolve deprecated send types
    SEND_TYPE_ALIASES = {
        "ppv_video": "ppv_unlock",
        "ppv_message": "ppv_unlock",
    }

    def resolve_send_type(send_type_key: str) -> str:
        """Resolve deprecated send type aliases."""
        resolved = SEND_TYPE_ALIASES.get(send_type_key, send_type_key)
        if send_type_key in SEND_TYPE_ALIASES:
            logger.info(f"Resolved deprecated {send_type_key} to {resolved}")
        return resolved

    # Define the 22-type taxonomy by category
    REVENUE_TYPES = {
        "ppv_unlock",       # Primary PPV (renamed from ppv_video)
        "ppv_wall",         # NEW - FREE pages only
        "tip_goal",         # NEW - PAID pages only
        "vip_program", "game_post", "bundle",
        "flash_bundle", "snapchat_bundle", "first_to_tip"
    }
    ENGAGEMENT_TYPES = {
        "link_drop", "wall_link_drop", "bump_normal", "bump_descriptive",
        "bump_text_only", "bump_flyer", "dm_farm", "like_farm", "live_promo"
    }
    RETENTION_TYPES = {
        "renew_on_post", "renew_on_message",
        "ppv_followup", "expired_winback"
    }
    # Note: ppv_message is deprecated, kept in database for transition

    # Extract unique send types from items (with backward compatibility resolution)
    unique_types: set[str] = set()
    for item in items:
        send_type_key = item.get("send_type_key")
        if send_type_key:
            # Resolve deprecated aliases for validation
            unique_types.add(resolve_send_type(send_type_key))

    # Validation 1: Minimum unique types (at least 10)
    if len(unique_types) < 10:
        logger.warning(
            f"save_schedule REJECTED: Only {len(unique_types)} unique send types for creator={creator_id}. "
            f"Types found: {sorted(unique_types)}"
        )
        return {
            "success": False,
            "error": f"REJECTED: Schedule contains only {len(unique_types)} unique send types. "
                     f"Minimum required: 10. Types found: {sorted(unique_types)}"
        }

    # Validation 2: Reject schedules with only ppv_unlock and/or bump_normal
    if unique_types <= {"ppv_unlock", "bump_normal"}:
        logger.warning(
            f"save_schedule REJECTED: Schedule contains only ppv_unlock/bump_normal for creator={creator_id}"
        )
        return {
            "success": False,
            "error": "REJECTED: Schedule contains only ppv_unlock and/or bump_normal. "
                     "Must use the full 22-type taxonomy for variety."
        }

    # Validation 3: Check category coverage
    revenue_count = len(unique_types & REVENUE_TYPES)
    engagement_count = len(unique_types & ENGAGEMENT_TYPES)
    retention_count = len(unique_types & RETENTION_TYPES)

    if revenue_count < 4:
        logger.warning(
            f"save_schedule REJECTED: Only {revenue_count} revenue types for creator={creator_id}. "
            f"Found: {sorted(unique_types & REVENUE_TYPES)}"
        )
        return {
            "success": False,
            "error": f"REJECTED: Only {revenue_count} revenue types used. Minimum: 4. "
                     f"Available: {sorted(REVENUE_TYPES)}"
        }

    if engagement_count < 4:
        logger.warning(
            f"save_schedule REJECTED: Only {engagement_count} engagement types for creator={creator_id}. "
            f"Found: {sorted(unique_types & ENGAGEMENT_TYPES)}"
        )
        return {
            "success": False,
            "error": f"REJECTED: Only {engagement_count} engagement types used. Minimum: 4. "
                     f"Available: {sorted(ENGAGEMENT_TYPES)}"
        }

    # Validation 4: Count items needing manual captions
    manual_caption_items = [i for i in items if i.get("needs_manual_caption")]
    manual_caption_warning = None
    if manual_caption_items:
        manual_caption_warning = f"WARNING: {len(manual_caption_items)} items require manual caption entry."
        logger.info(f"save_schedule: {manual_caption_warning} for creator={creator_id}")

    # Store diversity stats for response
    diversity_stats = {
        "unique_types": len(unique_types),
        "revenue_types": revenue_count,
        "engagement_types": engagement_count,
        "retention_types": retention_count,
        "types_used": sorted(unique_types)
    }

    logger.info(
        f"save_schedule: Diversity validation PASSED for creator={creator_id}. "
        f"Stats: {diversity_stats}"
    )

    # === PROCEED WITH SAVE IF VALIDATION PASSES ===

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

        cursor = conn.execute("SELECT target_id, target_key FROM audience_targets")
        targets_map = {row["target_key"]: row["target_id"] for row in cursor.fetchall()}

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
            # Resolve send_type_key to send_type_id (with backward compatibility)
            send_type_id = None
            send_type_key = item.get("send_type_key")
            if send_type_key:
                # Apply backward compatibility alias resolution
                original_key = send_type_key
                send_type_key = resolve_send_type(send_type_key)
                if original_key != send_type_key:
                    # Update the item with resolved key for consistency
                    item["send_type_key"] = send_type_key

                if send_type_key in send_types_map:
                    send_type_info = send_types_map[send_type_key]
                    send_type_id = send_type_info["id"]
                    # Validate flyer requirement
                    if send_type_info["requires_flyer"] == 1 and item.get("flyer_required", 0) == 0:
                        warnings.append(f"Item {idx}: send_type '{send_type_key}' requires flyer but flyer_required=0")
                else:
                    warnings.append(f"Item {idx}: Unknown send_type_key '{send_type_key}'")

            # Handle tip_goal specific fields
            if item.get("send_type_key") == "tip_goal":
                tip_goal_mode = item.get("tip_goal_mode")
                if tip_goal_mode and tip_goal_mode not in ("goal_based", "individual", "competitive"):
                    warnings.append(f"Item {idx}: Invalid tip_goal_mode '{tip_goal_mode}' (must be goal_based, individual, or competitive)")

            # Resolve channel_key to channel_id
            channel_id = None
            channel_key = item.get("channel_key")
            if channel_key:
                if channel_key in channels_map:
                    channel_id = channels_map[channel_key]
                else:
                    warnings.append(f"Item {idx}: Unknown channel_key '{channel_key}'")

            # Resolve target_key to target_id
            target_id = None
            target_key = item.get("target_key")
            if target_key:
                if target_key in targets_map:
                    target_id = targets_map[target_key]
                else:
                    warnings.append(f"Item {idx}: Unknown target_key '{target_key}'")

            # Determine is_follow_up based on parent_item_id
            parent_item_id = item.get("parent_item_id")
            is_follow_up = 1 if parent_item_id is not None else 0

            conn.execute(
                """
                INSERT INTO schedule_items (
                    template_id, creator_id, scheduled_date, scheduled_time,
                    item_type, channel, caption_id, caption_text,
                    suggested_price, content_type_id, flyer_required, priority, status,
                    send_type_id, channel_id, target_id,
                    linked_post_url, expires_at, followup_delay_minutes,
                    media_type, campaign_goal, parent_item_id, is_follow_up
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    target_id,
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

        # === CALCULATE VARIATION STATS ===
        # Analyze the schedule for authentic variation patterns
        all_times = [
            item.get("scheduled_time", "")
            for item in items
            if item.get("scheduled_time")
        ]

        variation_stats: dict[str, Any] = {
            "unique_times": len(set(all_times)),
            "total_times": len(all_times),
            "time_distribution": analyze_time_distribution(items),
            "strategy_per_day": extract_strategies(items),
            "jitter_applied": True,  # Indicates variation system is active
            "anti_pattern_score": calculate_anti_pattern_score(items)
        }

        logger.info(
            f"save_schedule: Variation stats for creator={creator_id}: "
            f"unique_times={variation_stats['unique_times']}/{variation_stats['total_times']}, "
            f"anti_pattern_score={variation_stats['anti_pattern_score']}"
        )

        result: dict[str, Any] = {
            "success": True,
            "template_id": template_id,
            "items_created": items_created,
            "week_start": week_start,
            "week_end": week_end,
            "diversity_stats": diversity_stats,
            "variation_stats": variation_stats
        }
        if warnings:
            result["warnings"] = warnings
        if manual_caption_warning:
            result["manual_caption_warning"] = manual_caption_warning

        return result
    except sqlite3.Error as e:
        conn.rollback()
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()


def execute_query(
    query: str,
    params: Optional[list[Any]] = None
) -> dict[str, Any]:
    """
    Execute a read-only SQL query for custom analysis.

    SECURITY: Only SELECT queries are allowed with comprehensive SQL injection protection.
    - Blocks dangerous keywords and PRAGMA commands
    - Detects comment injection attempts
    - Enforces query complexity limits
    - Limits result set size

    Args:
        query: SQL query string (must be SELECT).
        params: Optional list of parameters for the query.

    Returns:
        Dictionary containing:
            - results: List of result rows as dictionaries
            - count: Number of rows returned
            - columns: List of column names
    """
    # Log query attempt (sanitized)
    query_preview = query[:100].replace('\n', ' ').replace('\r', '')
    logger.info(f"execute_query called: {query_preview}...")

    # Security check: only allow SELECT queries
    normalized_query = query.strip().upper()
    if not normalized_query.startswith("SELECT"):
        logger.warning(f"Blocked non-SELECT query: {query_preview}")
        return {"error": "Only SELECT queries are allowed for security reasons"}

    # Enhanced security: block dangerous keywords
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "GRANT", "REVOKE", "ATTACH", "DETACH",
        "PRAGMA", "VACUUM", "REINDEX", "ANALYZE"
    ]
    for keyword in dangerous_keywords:
        if keyword in normalized_query:
            logger.warning(f"Blocked query with dangerous keyword '{keyword}': {query_preview}")
            return {"error": f"Query contains disallowed keyword: {keyword}"}

    # Detect comment injection patterns
    if "/*" in query or "*/" in query or "--" in query:
        logger.warning(f"Blocked query with comment injection pattern: {query_preview}")
        return {"error": "Query contains disallowed comment syntax (/* */ or --)"}

    # Enforce query complexity limits
    join_count = normalized_query.count(" JOIN ")
    if join_count > MAX_QUERY_JOINS:
        logger.warning(f"Blocked query exceeding JOIN limit ({join_count} > {MAX_QUERY_JOINS}): {query_preview}")
        return {"error": f"Query exceeds maximum JOIN limit of {MAX_QUERY_JOINS} (found {join_count})"}

    # Count subqueries (simplified detection)
    subquery_count = normalized_query.count("SELECT") - 1  # Subtract main SELECT
    if subquery_count > MAX_QUERY_SUBQUERIES:
        logger.warning(f"Blocked query exceeding subquery limit ({subquery_count} > {MAX_QUERY_SUBQUERIES}): {query_preview}")
        return {"error": f"Query exceeds maximum subquery limit of {MAX_QUERY_SUBQUERIES} (found {subquery_count})"}

    # Inject LIMIT clause if not present to prevent massive result sets
    if "LIMIT" not in normalized_query:
        query = f"{query.rstrip(';')} LIMIT {MAX_QUERY_RESULT_ROWS}"
        logger.info(f"Injected LIMIT {MAX_QUERY_RESULT_ROWS} to protect against large result sets")
    else:
        # Validate existing LIMIT doesn't exceed maximum
        limit_match = re.search(r'LIMIT\s+(\d+)', normalized_query)
        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > MAX_QUERY_RESULT_ROWS:
                logger.warning(f"Blocked query with excessive LIMIT ({limit_value} > {MAX_QUERY_RESULT_ROWS}): {query_preview}")
                return {"error": f"Query LIMIT exceeds maximum of {MAX_QUERY_RESULT_ROWS} (requested {limit_value})"}

    conn = get_db_connection()
    try:
        params = params or []
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        # Get column names
        columns = [description[0] for description in cursor.description] if cursor.description else []

        results = rows_to_list(rows)

        logger.info(f"execute_query successful: returned {len(results)} rows")
        return {
            "results": results,
            "count": len(results),
            "columns": columns
        }
    except sqlite3.Error as e:
        logger.error(f"Query execution error: {str(e)} for query: {query_preview}")
        return {"error": f"Query execution error: {str(e)}"}
    finally:
        conn.close()


# =============================================================================
# WAVE 2: NEW TOOL IMPLEMENTATIONS
# =============================================================================


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
    conn = get_db_connection()
    try:
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
    finally:
        conn.close()


def get_send_type_details(send_type_key: str) -> dict[str, Any]:
    """
    Get complete details for a single send type by key.

    Args:
        send_type_key: The unique key for the send type (e.g., 'ppv_video', 'bump_normal').

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
            INNER JOIN vault_matrix vm
                ON cb.content_type_id = vm.content_type_id
                AND vm.creator_id = ?
                AND vm.has_content = 1
            LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
            WHERE cb.is_active = 1
            AND cb.performance_score >= ?
            AND (
                CASE
                    WHEN ccp.last_used_date IS NULL THEN 100
                    ELSE MAX(0, MIN(100, 100 - (julianday('now') - julianday(ccp.last_used_date)) * 2))
                END
            ) >= ?
            ORDER BY freshness_score DESC, stcr.priority ASC, cb.performance_score DESC
            LIMIT ?
        """
        params: list[Any] = [
            send_type_id,
            resolved_creator_id,
            resolved_creator_id,
            min_performance,
            min_freshness,
            limit
        ]

        cursor = conn.execute(query, params)
        captions = rows_to_list(cursor.fetchall())

        # Determine if manual caption entry is needed
        needs_manual_caption = len(captions) == 0
        manual_caption_reason = None
        if needs_manual_caption:
            manual_caption_reason = f"No captions available for send_type={send_type_key}"
            logger.info(f"get_send_type_captions: No captions found for creator={creator_id}, send_type={send_type_key}")

        return {
            "captions": captions,
            "count": len(captions),
            "send_type_key": send_type_key,
            "creator_id": resolved_creator_id,
            "needs_manual_caption": needs_manual_caption,
            "manual_caption_reason": manual_caption_reason
        }
    finally:
        conn.close()


def get_channels(
    supports_targeting: Optional[bool] = None
) -> dict[str, Any]:
    """
    Get all channels with optional filtering by targeting support.

    Args:
        supports_targeting: Optional filter by targeting support (True/False).

    Returns:
        Dictionary containing:
            - channels: List of all channel records
            - count: Total number of channels returned
    """
    conn = get_db_connection()
    try:
        query = """
            SELECT
                channel_id,
                channel_key,
                display_name,
                description,
                supports_targeting,
                targeting_options,
                platform_feature,
                requires_manual_send,
                is_active,
                created_at
            FROM channels
            WHERE is_active = 1
        """
        params: list[Any] = []

        if supports_targeting is not None:
            query += " AND supports_targeting = ?"
            params.append(1 if supports_targeting else 0)

        query += " ORDER BY channel_id ASC"

        cursor = conn.execute(query, params)
        channels = rows_to_list(cursor.fetchall())

        # Parse JSON targeting_options for each channel
        for channel in channels:
            if channel.get("targeting_options"):
                try:
                    channel["targeting_options"] = json.loads(channel["targeting_options"])
                except json.JSONDecodeError:
                    pass  # Keep as string if not valid JSON

        return {
            "channels": channels,
            "count": len(channels)
        }
    finally:
        conn.close()


def get_audience_targets(
    page_type: Optional[str] = None,
    channel_key: Optional[str] = None
) -> dict[str, Any]:
    """
    Get audience targets filtered by page_type and/or channel.

    Uses JSON array matching for applicable_page_types and applicable_channels columns.

    Args:
        page_type: Optional filter by page_type ('paid' or 'free').
                   Matches targets where page_type is in applicable_page_types JSON array.
        channel_key: Optional filter by channel key.
                     Matches targets where channel_key is in applicable_channels JSON array.

    Returns:
        Dictionary containing:
            - targets: List of audience target records
            - count: Total number of targets returned
    """
    # Input validation
    if channel_key is not None:
        is_valid, error_msg = validate_key_input(channel_key, "channel_key")
        if not is_valid:
            logger.warning(f"get_audience_targets: Invalid channel_key - {error_msg}")
            return {"error": f"Invalid channel_key: {error_msg}"}

    conn = get_db_connection()
    try:
        query = """
            SELECT
                target_id,
                target_key,
                display_name,
                description,
                filter_type,
                filter_criteria,
                applicable_page_types,
                applicable_channels,
                typical_reach_percentage,
                is_active,
                created_at
            FROM audience_targets
            WHERE is_active = 1
        """
        params: list[Any] = []

        if page_type is not None:
            if page_type not in ("paid", "free"):
                return {"error": "page_type must be 'paid' or 'free'"}
            # Match page_type in JSON array using LIKE for SQLite compatibility
            query += " AND (applicable_page_types LIKE ? OR applicable_page_types LIKE ?)"
            params.append(f'%"{page_type}"%')
            params.append(f"%'{page_type}'%")

        if channel_key is not None:
            # Match channel_key in JSON array using LIKE
            query += " AND (applicable_channels LIKE ? OR applicable_channels LIKE ?)"
            params.append(f'%"{channel_key}"%')
            params.append(f"%'{channel_key}'%")

        query += " ORDER BY target_id ASC"

        cursor = conn.execute(query, params)
        targets = rows_to_list(cursor.fetchall())

        # Parse JSON fields for each target
        for target in targets:
            if target.get("filter_criteria"):
                try:
                    target["filter_criteria"] = json.loads(target["filter_criteria"])
                except json.JSONDecodeError:
                    pass
            if target.get("applicable_page_types"):
                try:
                    target["applicable_page_types"] = json.loads(target["applicable_page_types"])
                except json.JSONDecodeError:
                    pass
            if target.get("applicable_channels"):
                try:
                    target["applicable_channels"] = json.loads(target["applicable_channels"])
                except json.JSONDecodeError:
                    pass

        return {
            "targets": targets,
            "count": len(targets)
        }
    finally:
        conn.close()


def get_volume_config(creator_id: str) -> dict[str, Any]:
    """
    Get extended volume configuration for a creator using dynamic calculation.

    Calculates volume based on fan count, saturation/opportunity scores,
    and performance trends instead of static assignments.

    Args:
        creator_id: The creator_id or page_name.

    Returns:
        Dictionary containing volume configuration with calculation metadata.
    """
    # Import here to avoid circular imports
    from python.volume.dynamic_calculator import (
        calculate_dynamic_volume,
        PerformanceContext,
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

        # Calculate dynamic volume
        context = PerformanceContext(
            fan_count=fan_count,
            page_type=page_type,
            saturation_score=saturation_score,
            opportunity_score=opportunity_score,
            revenue_trend=revenue_trend
        )
        config = calculate_dynamic_volume(context)

        # Calculate type-specific limits based on tier
        tier_str = config.tier.value.title()  # 'high' -> 'High'
        bundle_per_week = {"Low": 1, "Mid": 2, "High": 3, "Ultra": 4}.get(tier_str, 1)
        game_per_week = {"Low": 1, "Mid": 2, "High": 2, "Ultra": 3}.get(tier_str, 1)
        followup_per_day = min(config.revenue_per_day, {"Low": 2, "Mid": 3, "High": 4, "Ultra": 5}.get(tier_str, 2))

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

            # New dynamic calculation metadata
            "calculation_source": "dynamic",
            "fan_count": fan_count,
            "page_type": page_type,
            "saturation_score": saturation_score,
            "opportunity_score": opportunity_score,
            "revenue_trend": revenue_trend,
            "data_source": data_source,
            "tracking_date": tracking_date
        }
    finally:
        conn.close()


# =============================================================================
# MCP PROTOCOL IMPLEMENTATION
# =============================================================================


# Tool definitions for tools/list response
TOOLS = [
    {
        "name": "get_active_creators",
        "description": "Get all active creators with performance metrics, volume assignments, and tier classification.",
        "inputSchema": {
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
    },
    {
        "name": "get_creator_profile",
        "description": "Get comprehensive profile for a single creator including analytics, volume assignment, and top content types.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {
                    "type": "string",
                    "description": "The creator_id or page_name to look up"
                }
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_top_captions",
        "description": "Get top-performing captions for a creator with freshness scoring based on last usage. Optionally filter by send_type_key for compatible caption types.",
        "inputSchema": {
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
    },
    {
        "name": "get_best_timing",
        "description": "Get optimal posting times based on historical mass_messages performance.",
        "inputSchema": {
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
    },
    {
        "name": "get_volume_assignment",
        "description": "Get current volume assignment for a creator (volume_level, ppv_per_day, bump_per_day).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {
                    "type": "string",
                    "description": "The creator_id or page_name"
                }
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_performance_trends",
        "description": "Get saturation/opportunity scores and performance trends from volume_performance_tracking.",
        "inputSchema": {
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
    },
    {
        "name": "get_content_type_rankings",
        "description": "Get ranked content types (TOP/MID/LOW/AVOID) from top_content_types analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {
                    "type": "string",
                    "description": "The creator_id or page_name"
                }
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_persona_profile",
        "description": "Get creator persona including tone, emoji style, and slang level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {
                    "type": "string",
                    "description": "The creator_id or page_name"
                }
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "get_vault_availability",
        "description": "Get what content types are available in creator's vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {
                    "type": "string",
                    "description": "The creator_id or page_name"
                }
            },
            "required": ["creator_id"]
        }
    },
    {
        "name": "save_schedule",
        "description": "Save generated schedule to database (creates template and items). Supports both legacy format and new send_type_key/channel_key/target_key fields.",
        "inputSchema": {
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
                            "target_key": {"type": "string", "description": "Audience target key (resolves to target_id)"},
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
                }
            },
            "required": ["creator_id", "week_start", "items"]
        }
    },
    {
        "name": "execute_query",
        "description": "Execute a read-only SQL SELECT query for custom analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query to execute"
                },
                "params": {
                    "type": "array",
                    "description": "Optional list of parameters for the query",
                    "items": {}
                }
            },
            "required": ["query"]
        }
    },
    # WAVE 2: New Tools
    {
        "name": "get_send_types",
        "description": "Get all send types with optional filtering by category and page_type. Returns complete send type configuration.",
        "inputSchema": {
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
    },
    {
        "name": "get_send_type_details",
        "description": "Get complete details for a single send type by key, including related caption type requirements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "send_type_key": {
                    "type": "string",
                    "description": "The unique key for the send type (e.g., 'ppv_unlock', 'bump_normal')"
                }
            },
            "required": ["send_type_key"]
        }
    },
    {
        "name": "get_send_type_captions",
        "description": "Get captions compatible with a specific send type for a creator. Orders by priority from send_type_caption_requirements, then by performance.",
        "inputSchema": {
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
    },
    {
        "name": "get_channels",
        "description": "Get all channels with optional filtering by targeting support.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "supports_targeting": {
                    "type": "boolean",
                    "description": "Optional filter by targeting support (true/false)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_audience_targets",
        "description": "Get audience targets filtered by page_type and/or channel_key using JSON array matching.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_type": {
                    "type": "string",
                    "enum": ["paid", "free"],
                    "description": "Optional filter by page_type (matches in applicable_page_types JSON array)"
                },
                "channel_key": {
                    "type": "string",
                    "description": "Optional filter by channel key (matches in applicable_channels JSON array)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_volume_config",
        "description": "Get extended volume configuration including category breakdowns (revenue/engagement/retention items per day) and type-specific limits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_id": {
                    "type": "string",
                    "description": "The creator_id or page_name"
                }
            },
            "required": ["creator_id"]
        }
    }
]


def handle_tools_list(request_id: Any) -> dict[str, Any]:
    """
    Handle the tools/list MCP method.

    Args:
        request_id: The JSON-RPC request ID.

    Returns:
        JSON-RPC response with list of available tools.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": TOOLS
        }
    }


def handle_tools_call(request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the tools/call MCP method.

    Args:
        request_id: The JSON-RPC request ID.
        params: The call parameters including 'name' and 'arguments'.

    Returns:
        JSON-RPC response with tool execution result.
    """
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    # Map tool names to functions (17 total: 11 original + 6 new)
    tool_handlers = {
        # Original 11 tools
        "get_active_creators": get_active_creators,
        "get_creator_profile": get_creator_profile,
        "get_top_captions": get_top_captions,
        "get_best_timing": get_best_timing,
        "get_volume_assignment": get_volume_assignment,
        "get_performance_trends": get_performance_trends,
        "get_content_type_rankings": get_content_type_rankings,
        "get_persona_profile": get_persona_profile,
        "get_vault_availability": get_vault_availability,
        "save_schedule": save_schedule,
        "execute_query": execute_query,
        # Wave 2: 6 new tools
        "get_send_types": get_send_types,
        "get_send_type_details": get_send_type_details,
        "get_send_type_captions": get_send_type_captions,
        "get_channels": get_channels,
        "get_audience_targets": get_audience_targets,
        "get_volume_config": get_volume_config
    }

    if tool_name not in tool_handlers:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Unknown tool: {tool_name}"
            }
        }

    try:
        handler = tool_handlers[tool_name]
        result = handler(**arguments)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2, default=str)
                    }
                ]
            }
        }
    except TypeError as e:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32602,
                "message": f"Invalid parameters: {str(e)}"
            }
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32000,
                "message": f"Tool execution error: {str(e)}"
            }
        }


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """
    Route incoming JSON-RPC request to appropriate handler.

    Args:
        request: The JSON-RPC request object.

    Returns:
        JSON-RPC response object.
    """
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})

    if method == "tools/list":
        return handle_tools_list(request_id)
    elif method == "tools/call":
        return handle_tools_call(request_id, params)
    elif method == "initialize":
        # Handle MCP initialization
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "eros-db-server",
                    "version": "2.0.0"
                }
            }
        }
    elif method == "notifications/initialized":
        # Notification, no response needed but return empty for consistency
        return None
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


def main() -> None:
    """
    Main entry point for the MCP server.

    Reads JSON-RPC requests from stdin (one per line) and writes responses to stdout.
    """
    # Disable output buffering for immediate responses
    sys.stdout.reconfigure(line_buffering=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)

            # Only output if there's a response (notifications don't get responses)
            if response is not None:
                print(json.dumps(response), flush=True)

        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
