"""
EROS MCP Server Security Utilities

Input validation and sanitization functions for security hardening.
All user inputs must pass through validation before database operations.
"""

import re
from typing import Optional

# Security configuration constants
MAX_INPUT_LENGTH_CREATOR_ID = 100
MAX_INPUT_LENGTH_KEY = 50
MAX_QUERY_JOINS = 5
MAX_QUERY_SUBQUERIES = 3
MAX_QUERY_RESULT_ROWS = 10000


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


def validate_string_length(
    value: str,
    max_length: int,
    field_name: str = "field"
) -> tuple[bool, Optional[str]]:
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
