"""
EROS MCP Server Helper Utilities

Database row conversion and creator ID resolution functions.
"""

import sqlite3
from typing import Any, Optional


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
