"""
EROS MCP Server Utilities

Helper functions for database operations and security validation.
"""

from mcp.utils.helpers import row_to_dict, rows_to_list, resolve_creator_id
from mcp.utils.security import (
    validate_creator_id,
    validate_key_input,
    validate_string_length,
    MAX_INPUT_LENGTH_CREATOR_ID,
    MAX_INPUT_LENGTH_KEY,
    MAX_QUERY_JOINS,
    MAX_QUERY_SUBQUERIES,
    MAX_QUERY_RESULT_ROWS,
)

__all__ = [
    # Helpers
    "row_to_dict",
    "rows_to_list",
    "resolve_creator_id",
    # Security
    "validate_creator_id",
    "validate_key_input",
    "validate_string_length",
    "MAX_INPUT_LENGTH_CREATOR_ID",
    "MAX_INPUT_LENGTH_KEY",
    "MAX_QUERY_JOINS",
    "MAX_QUERY_SUBQUERIES",
    "MAX_QUERY_RESULT_ROWS",
]
