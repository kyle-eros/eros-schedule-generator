"""
EROS Input Validation Decorators.

Provides reusable validation decorators for function inputs.
All decorators raise ValidationError subclasses from the exceptions module.

Usage:
    from python.validators import validate_creator_id, validate_send_type_key

    @validate_creator_id
    def get_creator_data(creator_id: str) -> dict:
        # creator_id is guaranteed to be valid here
        ...

    @validate_send_type_key
    def process_send_type(send_type_key: str, data: dict) -> None:
        # send_type_key is guaranteed to be valid here
        ...

    # Combine multiple validators
    @validate_creator_id
    @validate_date_range
    def generate_report(creator_id: str, start_date: str, end_date: str) -> Report:
        ...
"""

import re
from datetime import datetime
from functools import wraps
from typing import Any, Callable, TypeVar

from python.exceptions import (
    InvalidCreatorIdError,
    InvalidDateRangeError,
    InvalidSendTypeError,
    ValidationError,
)
from python.logging_config import get_logger

# Module logger
logger = get_logger(__name__)

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])

# =============================================================================
# Validation Constants
# =============================================================================

# Creator ID validation
MAX_CREATOR_ID_LENGTH = 100
CREATOR_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# Send type key validation
MAX_SEND_TYPE_KEY_LENGTH = 50
SEND_TYPE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# Valid send type keys (22 active types + 2 deprecated aliases)
VALID_SEND_TYPE_KEYS = frozenset([
    # Revenue (9 active)
    "ppv_unlock",       # Primary PPV (renamed from ppv_video)
    "ppv_wall",         # NEW - FREE pages only
    "tip_goal",         # NEW - PAID pages only
    "vip_program",
    "game_post",
    "bundle",
    "flash_bundle",
    "snapchat_bundle",
    "first_to_tip",
    # Engagement (9)
    "link_drop",
    "wall_link_drop",
    "bump_normal",
    "bump_descriptive",
    "bump_text_only",
    "bump_flyer",
    "dm_farm",
    "like_farm",
    "live_promo",
    # Retention (4 active)
    "renew_on_post",
    "renew_on_message",
    "ppv_followup",
    "expired_winback",
    # DEPRECATED (kept for backward compatibility during transition)
    "ppv_video",        # -> ppv_unlock
    "ppv_message",      # -> ppv_unlock (merged)
])

# Valid page types
VALID_PAGE_TYPES = frozenset(["paid", "free"])

# Valid categories
VALID_CATEGORIES = frozenset(["revenue", "engagement", "retention"])

# Date format
DATE_FORMAT = "%Y-%m-%d"


# =============================================================================
# Validation Helper Functions
# =============================================================================


def _validate_creator_id_value(creator_id: str) -> None:
    """Validate a creator_id value.

    Args:
        creator_id: The creator ID to validate.

    Raises:
        InvalidCreatorIdError: If validation fails.
    """
    if not creator_id:
        raise InvalidCreatorIdError(
            creator_id=str(creator_id),
            reason="cannot be empty"
        )

    if not isinstance(creator_id, str):
        raise InvalidCreatorIdError(
            creator_id=str(creator_id),
            reason="must be a string"
        )

    creator_id = creator_id.strip()

    if not creator_id:
        raise InvalidCreatorIdError(
            creator_id=creator_id,
            reason="cannot be whitespace only"
        )

    if len(creator_id) > MAX_CREATOR_ID_LENGTH:
        raise InvalidCreatorIdError(
            creator_id=creator_id[:50] + "...",
            reason=f"exceeds maximum length of {MAX_CREATOR_ID_LENGTH}"
        )

    if not CREATOR_ID_PATTERN.match(creator_id):
        raise InvalidCreatorIdError(
            creator_id=creator_id,
            reason="contains invalid characters (only alphanumeric, underscore, and hyphen allowed)"
        )


def _validate_send_type_key_value(
    send_type_key: str,
    strict: bool = True
) -> None:
    """Validate a send_type_key value.

    Args:
        send_type_key: The send type key to validate.
        strict: If True, key must be in VALID_SEND_TYPE_KEYS.

    Raises:
        InvalidSendTypeError: If validation fails.
    """
    if not send_type_key:
        raise InvalidSendTypeError(
            send_type_key=str(send_type_key),
            reason="cannot be empty"
        )

    if not isinstance(send_type_key, str):
        raise InvalidSendTypeError(
            send_type_key=str(send_type_key),
            reason="must be a string"
        )

    send_type_key = send_type_key.strip()

    if not send_type_key:
        raise InvalidSendTypeError(
            send_type_key=send_type_key,
            reason="cannot be whitespace only"
        )

    if len(send_type_key) > MAX_SEND_TYPE_KEY_LENGTH:
        raise InvalidSendTypeError(
            send_type_key=send_type_key[:30] + "...",
            reason=f"exceeds maximum length of {MAX_SEND_TYPE_KEY_LENGTH}"
        )

    if not SEND_TYPE_KEY_PATTERN.match(send_type_key):
        raise InvalidSendTypeError(
            send_type_key=send_type_key,
            reason="must be lowercase with underscores, starting with a letter"
        )

    if strict and send_type_key not in VALID_SEND_TYPE_KEYS:
        raise InvalidSendTypeError(
            send_type_key=send_type_key,
            reason=f"unknown send type (valid types: {', '.join(sorted(VALID_SEND_TYPE_KEYS)[:5])}...)"
        )


def _validate_date_string(date_str: str, field_name: str = "date") -> datetime:
    """Validate and parse a date string.

    Args:
        date_str: Date string in YYYY-MM-DD format.
        field_name: Name of the field for error messages.

    Returns:
        Parsed datetime object.

    Raises:
        ValidationError: If the date string is invalid.
    """
    if not date_str:
        raise ValidationError(
            message=f"{field_name} cannot be empty",
            field=field_name,
            value=date_str
        )

    if not isinstance(date_str, str):
        raise ValidationError(
            message=f"{field_name} must be a string",
            field=field_name,
            value=date_str
        )

    try:
        return datetime.strptime(date_str.strip(), DATE_FORMAT)
    except ValueError:
        raise ValidationError(
            message=f"{field_name} must be in YYYY-MM-DD format",
            field=field_name,
            value=date_str
        )


# =============================================================================
# Validation Decorators
# =============================================================================


def validate_creator_id(func: F) -> F:
    """Decorator to validate creator_id parameter.

    Validates that the first positional argument or 'creator_id' keyword
    argument is a valid creator ID.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with validation.

    Raises:
        InvalidCreatorIdError: If creator_id is invalid.

    Example:
        @validate_creator_id
        def get_profile(creator_id: str) -> dict:
            ...
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Try to get creator_id from kwargs first, then from args
        creator_id = kwargs.get("creator_id")
        if creator_id is None and args:
            creator_id = args[0]

        if creator_id is not None:
            _validate_creator_id_value(creator_id)
            logger.debug(f"Validated creator_id: {creator_id}")

        return func(*args, **kwargs)

    return wrapper  # type: ignore


def validate_send_type_key(func: F) -> F:
    """Decorator to validate send_type_key parameter.

    Validates that the 'send_type_key' keyword argument or second positional
    argument is a valid send type key.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with validation.

    Raises:
        InvalidSendTypeError: If send_type_key is invalid.

    Example:
        @validate_send_type_key
        def process_send(creator_id: str, send_type_key: str) -> None:
            ...
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Try to get send_type_key from kwargs first, then from args
        send_type_key = kwargs.get("send_type_key")
        if send_type_key is None and len(args) > 1:
            send_type_key = args[1]

        if send_type_key is not None:
            _validate_send_type_key_value(send_type_key)
            logger.debug(f"Validated send_type_key: {send_type_key}")

        return func(*args, **kwargs)

    return wrapper  # type: ignore


def validate_send_type_key_loose(func: F) -> F:
    """Decorator to validate send_type_key with loose validation.

    Like validate_send_type_key but doesn't require the key to be in the
    known list. Useful for functions that might accept new send types.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with validation.

    Raises:
        InvalidSendTypeError: If send_type_key format is invalid.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        send_type_key = kwargs.get("send_type_key")
        if send_type_key is None and len(args) > 1:
            send_type_key = args[1]

        if send_type_key is not None:
            _validate_send_type_key_value(send_type_key, strict=False)

        return func(*args, **kwargs)

    return wrapper  # type: ignore


def validate_date_range(func: F) -> F:
    """Decorator to validate date range parameters.

    Validates 'start_date' and 'end_date' keyword arguments or positional
    arguments are valid dates and that end_date >= start_date.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with validation.

    Raises:
        InvalidDateRangeError: If date range is invalid.

    Example:
        @validate_date_range
        def get_report(start_date: str, end_date: str) -> Report:
            ...
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Try to get dates from kwargs or args
        start_date = kwargs.get("start_date") or kwargs.get("week_start")
        end_date = kwargs.get("end_date") or kwargs.get("week_end")

        # Check positional args if not in kwargs
        if start_date is None and args:
            # Look for first string argument that looks like a date
            for arg in args:
                if isinstance(arg, str) and len(arg) == 10 and "-" in arg:
                    if start_date is None:
                        start_date = arg
                    elif end_date is None:
                        end_date = arg
                        break

        # Validate dates if present
        start_dt = None
        end_dt = None

        if start_date is not None:
            start_dt = _validate_date_string(start_date, "start_date")

        if end_date is not None:
            end_dt = _validate_date_string(end_date, "end_date")

        # Validate range if both dates present
        if start_dt and end_dt and end_dt < start_dt:
            raise InvalidDateRangeError(
                start_date=start_date,
                end_date=end_date,
                reason="end_date cannot be before start_date"
            )

        return func(*args, **kwargs)

    return wrapper  # type: ignore


def validate_page_type(func: F) -> F:
    """Decorator to validate page_type parameter.

    Validates that 'page_type' is either 'paid' or 'free'.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with validation.

    Raises:
        ValidationError: If page_type is invalid.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        page_type = kwargs.get("page_type")

        if page_type is not None and page_type not in VALID_PAGE_TYPES:
            raise ValidationError(
                message=f"page_type must be 'paid' or 'free', got '{page_type}'",
                field="page_type",
                value=page_type
            )

        return func(*args, **kwargs)

    return wrapper  # type: ignore


def validate_category(func: F) -> F:
    """Decorator to validate category parameter.

    Validates that 'category' is 'revenue', 'engagement', or 'retention'.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with validation.

    Raises:
        ValidationError: If category is invalid.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        category = kwargs.get("category")

        if category is not None and category not in VALID_CATEGORIES:
            raise ValidationError(
                message=f"category must be 'revenue', 'engagement', or 'retention', got '{category}'",
                field="category",
                value=category
            )

        return func(*args, **kwargs)

    return wrapper  # type: ignore


def validate_positive_int(param_name: str) -> Callable[[F], F]:
    """Factory for decorator to validate positive integer parameters.

    Args:
        param_name: Name of the parameter to validate.

    Returns:
        Decorator function.

    Example:
        @validate_positive_int("limit")
        def get_items(limit: int) -> list:
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            value = kwargs.get(param_name)

            if value is not None:
                if not isinstance(value, int):
                    raise ValidationError(
                        message=f"{param_name} must be an integer",
                        field=param_name,
                        value=value
                    )
                if value <= 0:
                    raise ValidationError(
                        message=f"{param_name} must be positive",
                        field=param_name,
                        value=value
                    )

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def validate_range(
    param_name: str,
    min_value: float | None = None,
    max_value: float | None = None
) -> Callable[[F], F]:
    """Factory for decorator to validate numeric range.

    Args:
        param_name: Name of the parameter to validate.
        min_value: Minimum allowed value (inclusive).
        max_value: Maximum allowed value (inclusive).

    Returns:
        Decorator function.

    Example:
        @validate_range("score", min_value=0, max_value=100)
        def update_score(score: float) -> None:
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            value = kwargs.get(param_name)

            if value is not None:
                if not isinstance(value, (int, float)):
                    raise ValidationError(
                        message=f"{param_name} must be a number",
                        field=param_name,
                        value=value
                    )

                if min_value is not None and value < min_value:
                    raise ValidationError(
                        message=f"{param_name} must be at least {min_value}",
                        field=param_name,
                        value=value
                    )

                if max_value is not None and value > max_value:
                    raise ValidationError(
                        message=f"{param_name} must be at most {max_value}",
                        field=param_name,
                        value=value
                    )

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# Standalone Validation Functions (for non-decorator use)
# =============================================================================


def is_valid_creator_id(creator_id: str) -> bool:
    """Check if creator_id is valid without raising exception.

    Args:
        creator_id: The creator ID to check.

    Returns:
        True if valid, False otherwise.
    """
    try:
        _validate_creator_id_value(creator_id)
        return True
    except InvalidCreatorIdError:
        return False


def is_valid_send_type_key(send_type_key: str, strict: bool = True) -> bool:
    """Check if send_type_key is valid without raising exception.

    Args:
        send_type_key: The send type key to check.
        strict: If True, key must be in VALID_SEND_TYPE_KEYS.

    Returns:
        True if valid, False otherwise.
    """
    try:
        _validate_send_type_key_value(send_type_key, strict=strict)
        return True
    except InvalidSendTypeError:
        return False


def parse_date(date_str: str) -> datetime | None:
    """Parse a date string, returning None on failure.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        Parsed datetime or None if invalid.
    """
    try:
        return _validate_date_string(date_str)
    except ValidationError:
        return None


# =============================================================================
# Export public API
# =============================================================================

__all__ = [
    # Decorators
    "validate_creator_id",
    "validate_send_type_key",
    "validate_send_type_key_loose",
    "validate_date_range",
    "validate_page_type",
    "validate_category",
    "validate_positive_int",
    "validate_range",
    # Standalone functions
    "is_valid_creator_id",
    "is_valid_send_type_key",
    "parse_date",
    # Constants
    "VALID_SEND_TYPE_KEYS",
    "VALID_PAGE_TYPES",
    "VALID_CATEGORIES",
]
