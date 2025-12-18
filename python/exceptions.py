"""
EROS Custom Exception Hierarchy.

Provides a structured exception hierarchy for the EROS scheduling system.
All exceptions inherit from EROSError to enable catching EROS-specific
exceptions while allowing standard Python exceptions to propagate.

Exception Hierarchy:
    EROSError (base)
    ├── CreatorNotFoundError
    ├── InsufficientCaptionsError
    ├── ValidationError
    │   ├── InvalidCreatorIdError
    │   ├── InvalidSendTypeError
    │   └── InvalidDateRangeError
    ├── DatabaseError
    │   ├── ConnectionError
    │   └── QueryError
    └── ConfigurationError
        └── MissingConfigError
"""

from typing import Any, Optional


class EROSError(Exception):
    """Base exception for all EROS system errors.

    Attributes:
        message: Human-readable error description
        code: Optional error code for programmatic handling
        details: Optional dictionary with additional context
    """

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize EROSError.

        Args:
            message: Human-readable error description
            code: Optional error code (e.g., 'E001')
            details: Optional dictionary with additional context
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        """Return formatted error string."""
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dictionary containing error information
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details
        }


# =============================================================================
# Creator-Related Exceptions
# =============================================================================


class CreatorNotFoundError(EROSError):
    """Raised when a creator lookup fails.

    This exception is raised when attempting to access a creator that does not
    exist in the database, or when the creator_id/page_name cannot be resolved.
    """

    def __init__(
        self,
        creator_id: str,
        message: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize CreatorNotFoundError.

        Args:
            creator_id: The creator_id or page_name that was not found
            message: Optional custom message (auto-generated if not provided)
            details: Optional dictionary with additional context
        """
        msg = message or f"Creator not found: {creator_id}"
        super().__init__(msg, code="E100", details=details)
        self.creator_id = creator_id


# =============================================================================
# Caption-Related Exceptions
# =============================================================================


class InsufficientCaptionsError(EROSError):
    """Raised when there are not enough captions available for scheduling.

    This exception is raised when the caption pool is exhausted or when
    there are not enough captions meeting the required criteria (performance,
    freshness, type match) to complete a schedule.
    """

    def __init__(
        self,
        required: int,
        available: int,
        send_type_key: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize InsufficientCaptionsError.

        Args:
            required: Number of captions required
            available: Number of captions available
            send_type_key: Optional send type that requires captions
            message: Optional custom message
            details: Optional dictionary with additional context
        """
        if message:
            msg = message
        elif send_type_key:
            msg = (
                f"Insufficient captions for '{send_type_key}': "
                f"required {required}, available {available}"
            )
        else:
            msg = f"Insufficient captions: required {required}, available {available}"

        super().__init__(msg, code="E200", details=details)
        self.required = required
        self.available = available
        self.send_type_key = send_type_key


# =============================================================================
# Validation Exceptions
# =============================================================================


class ValidationError(EROSError):
    """Raised when input validation fails.

    Base class for all validation-related errors. Can be used directly for
    general validation failures or subclassed for specific validation scenarios.
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize ValidationError.

        Args:
            message: Description of the validation failure
            field: Optional name of the field that failed validation
            value: Optional invalid value that was provided
            details: Optional dictionary with additional context
        """
        super().__init__(message, code="E300", details=details)
        self.field = field
        self.value = value


class InvalidCreatorIdError(ValidationError):
    """Raised when creator_id validation fails.

    This includes empty values, values exceeding length limits, or values
    containing invalid characters.
    """

    def __init__(
        self,
        creator_id: str,
        reason: str,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize InvalidCreatorIdError.

        Args:
            creator_id: The invalid creator_id value
            reason: Explanation of why validation failed
            details: Optional dictionary with additional context
        """
        message = f"Invalid creator_id '{creator_id}': {reason}"
        super().__init__(message, field="creator_id", value=creator_id, details=details)
        self.code = "E301"


class InvalidSendTypeError(ValidationError):
    """Raised when send_type_key validation fails.

    This includes unknown send types or send types that are not valid for
    the given context (e.g., retention types on free pages).
    """

    def __init__(
        self,
        send_type_key: str,
        reason: str,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize InvalidSendTypeError.

        Args:
            send_type_key: The invalid send type key
            reason: Explanation of why validation failed
            details: Optional dictionary with additional context
        """
        message = f"Invalid send_type_key '{send_type_key}': {reason}"
        super().__init__(message, field="send_type_key", value=send_type_key, details=details)
        self.code = "E302"


class InvalidDateRangeError(ValidationError):
    """Raised when date range validation fails.

    This includes invalid date formats, end date before start date,
    or date ranges outside acceptable bounds.
    """

    def __init__(
        self,
        start_date: str | None,
        end_date: str | None,
        reason: str,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize InvalidDateRangeError.

        Args:
            start_date: The start date value
            end_date: The end date value
            reason: Explanation of why validation failed
            details: Optional dictionary with additional context
        """
        message = f"Invalid date range ({start_date} to {end_date}): {reason}"
        super().__init__(
            message,
            field="date_range",
            value={"start_date": start_date, "end_date": end_date},
            details=details
        )
        self.code = "E303"
        self.start_date = start_date
        self.end_date = end_date


# =============================================================================
# Database Exceptions
# =============================================================================


class DatabaseError(EROSError):
    """Raised for database operation failures.

    Base class for database-related errors including connection failures,
    query errors, and transaction failures.
    """

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize DatabaseError.

        Args:
            message: Description of the database error
            operation: Optional name of the operation that failed
            details: Optional dictionary with additional context
        """
        super().__init__(message, code="E400", details=details)
        self.operation = operation


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails.

    This includes connection timeouts, file not found, and permission errors.
    """

    def __init__(
        self,
        message: str,
        db_path: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize DatabaseConnectionError.

        Args:
            message: Description of the connection error
            db_path: Optional path to the database file
            details: Optional dictionary with additional context
        """
        super().__init__(message, operation="connect", details=details)
        self.code = "E401"
        self.db_path = db_path


class QueryError(DatabaseError):
    """Raised when a database query fails.

    This includes SQL syntax errors, constraint violations, and query timeouts.
    """

    def __init__(
        self,
        message: str,
        query: str | None = None,
        params: list[Any] | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize QueryError.

        Args:
            message: Description of the query error
            query: Optional SQL query that failed (sanitized)
            params: Optional query parameters
            details: Optional dictionary with additional context
        """
        super().__init__(message, operation="query", details=details)
        self.code = "E402"
        # Store truncated query for debugging (avoid logging sensitive data)
        self.query = query[:200] if query else None
        self.params = params


# =============================================================================
# Configuration Exceptions
# =============================================================================


class ConfigurationError(EROSError):
    """Raised for configuration issues.

    Base class for configuration-related errors including missing config,
    invalid config values, and environment variable issues.
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize ConfigurationError.

        Args:
            message: Description of the configuration error
            config_key: Optional configuration key that caused the error
            details: Optional dictionary with additional context
        """
        super().__init__(message, code="E500", details=details)
        self.config_key = config_key


class MissingConfigError(ConfigurationError):
    """Raised when a required configuration value is missing.

    This includes missing environment variables, missing config file entries,
    or missing required function parameters.
    """

    def __init__(
        self,
        config_key: str,
        message: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize MissingConfigError.

        Args:
            config_key: The missing configuration key
            message: Optional custom message
            details: Optional dictionary with additional context
        """
        msg = message or f"Missing required configuration: {config_key}"
        super().__init__(msg, config_key=config_key, details=details)
        self.code = "E501"


# =============================================================================
# Data-Related Exceptions
# =============================================================================


class InsufficientDataError(EROSError):
    """Raised when there is not enough data for an operation.

    This includes missing performance data, insufficient history for trend
    calculations, or empty result sets where data is required.
    """

    def __init__(
        self,
        message: str,
        data_type: str | None = None,
        required: int | None = None,
        available: int | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize InsufficientDataError.

        Args:
            message: Description of the data insufficiency
            data_type: Type of data that was insufficient
            required: Minimum amount of data required
            available: Amount of data that was available
            details: Optional dictionary with additional context
        """
        super().__init__(message, code="E550", details=details)
        self.data_type = data_type
        self.required = required
        self.available = available


# =============================================================================
# Schedule-Related Exceptions
# =============================================================================


class ScheduleError(EROSError):
    """Raised for schedule generation errors.

    Base class for schedule-related errors including constraint violations,
    capacity exceeded, and timing conflicts.
    """

    def __init__(
        self,
        message: str,
        schedule_date: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize ScheduleError.

        Args:
            message: Description of the schedule error
            schedule_date: Optional date related to the error
            details: Optional dictionary with additional context
        """
        super().__init__(message, code="E600", details=details)
        self.schedule_date = schedule_date


class ScheduleCapacityError(ScheduleError):
    """Raised when schedule capacity limits are exceeded.

    This includes daily/weekly maximums for send types, followup limits,
    and total volume constraints.
    """

    def __init__(
        self,
        message: str,
        limit_type: str,
        limit_value: int,
        current_value: int,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize ScheduleCapacityError.

        Args:
            message: Description of the capacity error
            limit_type: Type of limit exceeded (e.g., 'daily_ppv', 'weekly_vip')
            limit_value: The maximum allowed value
            current_value: The current/attempted value
            details: Optional dictionary with additional context
        """
        super().__init__(message, details=details)
        self.code = "E601"
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.current_value = current_value


class TimingConflictError(ScheduleError):
    """Raised when schedule timing conflicts occur.

    This includes overlapping sends, insufficient spacing between sends,
    and conflicts with blackout periods.
    """

    def __init__(
        self,
        message: str,
        conflicting_times: list[str] | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize TimingConflictError.

        Args:
            message: Description of the timing conflict
            conflicting_times: List of conflicting time strings
            details: Optional dictionary with additional context
        """
        super().__init__(message, details=details)
        self.code = "E602"
        self.conflicting_times = conflicting_times or []


# =============================================================================
# Export all exceptions
# =============================================================================

__all__ = [
    # Base
    "EROSError",
    # Creator
    "CreatorNotFoundError",
    # Caption
    "InsufficientCaptionsError",
    # Validation
    "ValidationError",
    "InvalidCreatorIdError",
    "InvalidSendTypeError",
    "InvalidDateRangeError",
    # Database
    "DatabaseError",
    "DatabaseConnectionError",
    "QueryError",
    # Configuration
    "ConfigurationError",
    "MissingConfigError",
    # Data
    "InsufficientDataError",
    # Schedule
    "ScheduleError",
    "ScheduleCapacityError",
    "TimingConflictError",
]
