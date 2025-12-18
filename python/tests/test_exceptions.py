"""
Unit tests for EROS exception hierarchy.

Tests exception inheritance, error codes, and message formatting.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.exceptions import (
    # Base
    EROSError,
    # Creator
    CreatorNotFoundError,
    # Caption
    InsufficientCaptionsError,
    # Validation
    ValidationError,
    InvalidCreatorIdError,
    InvalidSendTypeError,
    InvalidDateRangeError,
    # Database
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    # Configuration
    ConfigurationError,
    MissingConfigError,
    # Schedule
    ScheduleError,
    ScheduleCapacityError,
    TimingConflictError,
)


class TestEROSErrorBase:
    """Tests for base EROSError."""

    def test_creation_message_only(self):
        """Test creating with message only."""
        error = EROSError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"

    def test_creation_with_code(self):
        """Test creating with error code."""
        error = EROSError("Test error", code="E001")
        assert str(error) == "[E001] Test error"
        assert error.code == "E001"

    def test_creation_with_details(self):
        """Test creating with details dict."""
        details = {"key": "value", "count": 42}
        error = EROSError("Test error", details=details)
        assert error.details == details

    def test_to_dict(self):
        """Test to_dict serialization."""
        error = EROSError("Test error", code="E001", details={"key": "value"})
        result = error.to_dict()

        assert result["error"] == "EROSError"
        assert result["message"] == "Test error"
        assert result["code"] == "E001"
        assert result["details"] == {"key": "value"}

    def test_is_exception(self):
        """Test EROSError is an Exception."""
        error = EROSError("Test")
        assert isinstance(error, Exception)

    def test_can_be_raised(self):
        """Test EROSError can be raised and caught."""
        with pytest.raises(EROSError) as exc_info:
            raise EROSError("Test error")

        assert "Test error" in str(exc_info.value)


class TestCreatorNotFoundError:
    """Tests for CreatorNotFoundError."""

    def test_creation_with_creator_id(self):
        """Test creating with creator_id."""
        error = CreatorNotFoundError("alexia")
        assert error.creator_id == "alexia"
        assert "alexia" in error.message

    def test_default_message(self):
        """Test default message generation."""
        error = CreatorNotFoundError("test_user")
        assert error.message == "Creator not found: test_user"

    def test_custom_message(self):
        """Test custom message override."""
        error = CreatorNotFoundError("test_user", message="Custom message")
        assert error.message == "Custom message"

    def test_error_code(self):
        """Test error code is E100."""
        error = CreatorNotFoundError("test")
        assert error.code == "E100"

    def test_inherits_from_eros_error(self):
        """Test inheritance from EROSError."""
        error = CreatorNotFoundError("test")
        assert isinstance(error, EROSError)


class TestInsufficientCaptionsError:
    """Tests for InsufficientCaptionsError."""

    def test_creation_basic(self):
        """Test creating with required and available counts."""
        error = InsufficientCaptionsError(required=10, available=3)
        assert error.required == 10
        assert error.available == 3

    def test_default_message(self):
        """Test default message format."""
        error = InsufficientCaptionsError(required=10, available=3)
        assert "10" in error.message
        assert "3" in error.message

    def test_with_send_type(self):
        """Test message includes send type when provided."""
        error = InsufficientCaptionsError(
            required=5,
            available=2,
            send_type_key="ppv_video",
        )
        assert "ppv_video" in error.message
        assert error.send_type_key == "ppv_video"

    def test_error_code(self):
        """Test error code is E200."""
        error = InsufficientCaptionsError(required=5, available=2)
        assert error.code == "E200"


class TestValidationError:
    """Tests for ValidationError base class."""

    def test_creation_basic(self):
        """Test creating with message only."""
        error = ValidationError("Validation failed")
        assert error.message == "Validation failed"

    def test_creation_with_field(self):
        """Test creating with field name."""
        error = ValidationError("Invalid value", field="username")
        assert error.field == "username"

    def test_creation_with_value(self):
        """Test creating with invalid value."""
        error = ValidationError("Invalid", field="count", value=-1)
        assert error.value == -1

    def test_error_code(self):
        """Test error code is E300."""
        error = ValidationError("Invalid")
        assert error.code == "E300"

    def test_inherits_from_eros_error(self):
        """Test inheritance from EROSError."""
        error = ValidationError("Invalid")
        assert isinstance(error, EROSError)


class TestInvalidCreatorIdError:
    """Tests for InvalidCreatorIdError."""

    def test_creation(self):
        """Test creating with creator_id and reason."""
        error = InvalidCreatorIdError(
            creator_id="bad@id",
            reason="contains invalid characters",
        )
        assert "bad@id" in error.message
        assert "contains invalid characters" in error.message

    def test_error_code(self):
        """Test error code is E301."""
        error = InvalidCreatorIdError("id", "reason")
        assert error.code == "E301"

    def test_inherits_from_validation_error(self):
        """Test inheritance from ValidationError."""
        error = InvalidCreatorIdError("id", "reason")
        assert isinstance(error, ValidationError)

    def test_field_is_creator_id(self):
        """Test field is set to creator_id."""
        error = InvalidCreatorIdError("id", "reason")
        assert error.field == "creator_id"


class TestInvalidSendTypeError:
    """Tests for InvalidSendTypeError."""

    def test_creation(self):
        """Test creating with send_type_key and reason."""
        error = InvalidSendTypeError(
            send_type_key="unknown_type",
            reason="not found in registry",
        )
        assert "unknown_type" in error.message
        assert "not found in registry" in error.message

    def test_error_code(self):
        """Test error code is E302."""
        error = InvalidSendTypeError("key", "reason")
        assert error.code == "E302"

    def test_inherits_from_validation_error(self):
        """Test inheritance from ValidationError."""
        error = InvalidSendTypeError("key", "reason")
        assert isinstance(error, ValidationError)

    def test_field_is_send_type_key(self):
        """Test field is set to send_type_key."""
        error = InvalidSendTypeError("key", "reason")
        assert error.field == "send_type_key"


class TestInvalidDateRangeError:
    """Tests for InvalidDateRangeError."""

    def test_creation(self):
        """Test creating with start and end dates."""
        error = InvalidDateRangeError(
            start_date="2025-01-15",
            end_date="2025-01-10",
            reason="end_date cannot be before start_date",
        )
        assert "2025-01-15" in error.message
        assert "2025-01-10" in error.message
        assert error.start_date == "2025-01-15"
        assert error.end_date == "2025-01-10"

    def test_error_code(self):
        """Test error code is E303."""
        error = InvalidDateRangeError("start", "end", "reason")
        assert error.code == "E303"

    def test_value_is_dict(self):
        """Test value contains date range dict."""
        error = InvalidDateRangeError("2025-01-15", "2025-01-10", "reason")
        assert error.value == {
            "start_date": "2025-01-15",
            "end_date": "2025-01-10",
        }


class TestDatabaseError:
    """Tests for DatabaseError base class."""

    def test_creation_basic(self):
        """Test creating with message only."""
        error = DatabaseError("Database operation failed")
        assert error.message == "Database operation failed"

    def test_creation_with_operation(self):
        """Test creating with operation name."""
        error = DatabaseError("Failed", operation="insert")
        assert error.operation == "insert"

    def test_error_code(self):
        """Test error code is E400."""
        error = DatabaseError("Failed")
        assert error.code == "E400"


class TestDatabaseConnectionError:
    """Tests for DatabaseConnectionError."""

    def test_creation(self):
        """Test creating with db_path."""
        error = DatabaseConnectionError(
            "Cannot connect",
            db_path="/path/to/db.sqlite",
        )
        assert error.db_path == "/path/to/db.sqlite"

    def test_error_code(self):
        """Test error code is E401."""
        error = DatabaseConnectionError("Cannot connect")
        assert error.code == "E401"

    def test_operation_is_connect(self):
        """Test operation is set to connect."""
        error = DatabaseConnectionError("Cannot connect")
        assert error.operation == "connect"

    def test_inherits_from_database_error(self):
        """Test inheritance from DatabaseError."""
        error = DatabaseConnectionError("Cannot connect")
        assert isinstance(error, DatabaseError)


class TestQueryError:
    """Tests for QueryError."""

    def test_creation_basic(self):
        """Test creating with message only."""
        error = QueryError("Query failed")
        assert error.message == "Query failed"

    def test_creation_with_query(self):
        """Test creating with query string."""
        error = QueryError(
            "Syntax error",
            query="SELECT * FROM invalid_table",
        )
        assert error.query is not None

    def test_query_truncated(self):
        """Test long query is truncated."""
        long_query = "SELECT " + "x" * 500
        error = QueryError("Error", query=long_query)
        assert len(error.query) <= 200

    def test_error_code(self):
        """Test error code is E402."""
        error = QueryError("Failed")
        assert error.code == "E402"

    def test_operation_is_query(self):
        """Test operation is set to query."""
        error = QueryError("Failed")
        assert error.operation == "query"


class TestConfigurationError:
    """Tests for ConfigurationError base class."""

    def test_creation_basic(self):
        """Test creating with message only."""
        error = ConfigurationError("Config error")
        assert error.message == "Config error"

    def test_creation_with_config_key(self):
        """Test creating with config_key."""
        error = ConfigurationError("Missing", config_key="database.host")
        assert error.config_key == "database.host"

    def test_error_code(self):
        """Test error code is E500."""
        error = ConfigurationError("Error")
        assert error.code == "E500"


class TestMissingConfigError:
    """Tests for MissingConfigError."""

    def test_creation(self):
        """Test creating with config_key."""
        error = MissingConfigError("EROS_DB_PATH")
        assert error.config_key == "EROS_DB_PATH"
        assert "EROS_DB_PATH" in error.message

    def test_custom_message(self):
        """Test custom message override."""
        error = MissingConfigError("key", message="Custom message")
        assert error.message == "Custom message"

    def test_error_code(self):
        """Test error code is E501."""
        error = MissingConfigError("key")
        assert error.code == "E501"

    def test_inherits_from_configuration_error(self):
        """Test inheritance from ConfigurationError."""
        error = MissingConfigError("key")
        assert isinstance(error, ConfigurationError)


class TestScheduleError:
    """Tests for ScheduleError base class."""

    def test_creation_basic(self):
        """Test creating with message only."""
        error = ScheduleError("Schedule error")
        assert error.message == "Schedule error"

    def test_creation_with_date(self):
        """Test creating with schedule_date."""
        error = ScheduleError("Error", schedule_date="2025-12-16")
        assert error.schedule_date == "2025-12-16"

    def test_error_code(self):
        """Test error code is E600."""
        error = ScheduleError("Error")
        assert error.code == "E600"


class TestScheduleCapacityError:
    """Tests for ScheduleCapacityError."""

    def test_creation(self):
        """Test creating with limit details."""
        error = ScheduleCapacityError(
            message="Daily limit exceeded",
            limit_type="daily_ppv",
            limit_value=4,
            current_value=5,
        )
        assert error.limit_type == "daily_ppv"
        assert error.limit_value == 4
        assert error.current_value == 5

    def test_error_code(self):
        """Test error code is E601."""
        error = ScheduleCapacityError("Error", "type", 5, 6)
        assert error.code == "E601"

    def test_inherits_from_schedule_error(self):
        """Test inheritance from ScheduleError."""
        error = ScheduleCapacityError("Error", "type", 5, 6)
        assert isinstance(error, ScheduleError)


class TestTimingConflictError:
    """Tests for TimingConflictError."""

    def test_creation_basic(self):
        """Test creating with message only."""
        error = TimingConflictError("Timing conflict")
        assert error.message == "Timing conflict"

    def test_creation_with_times(self):
        """Test creating with conflicting times."""
        error = TimingConflictError(
            "Overlap detected",
            conflicting_times=["19:00", "19:15"],
        )
        assert error.conflicting_times == ["19:00", "19:15"]

    def test_error_code(self):
        """Test error code is E602."""
        error = TimingConflictError("Conflict")
        assert error.code == "E602"

    def test_inherits_from_schedule_error(self):
        """Test inheritance from ScheduleError."""
        error = TimingConflictError("Conflict")
        assert isinstance(error, ScheduleError)


class TestExceptionHierarchy:
    """Tests for exception hierarchy structure."""

    def test_creator_error_caught_by_eros_error(self):
        """Test CreatorNotFoundError can be caught by EROSError."""
        with pytest.raises(EROSError):
            raise CreatorNotFoundError("test")

    def test_validation_error_caught_by_eros_error(self):
        """Test ValidationError can be caught by EROSError."""
        with pytest.raises(EROSError):
            raise InvalidCreatorIdError("id", "reason")

    def test_database_error_caught_by_eros_error(self):
        """Test DatabaseError can be caught by EROSError."""
        with pytest.raises(EROSError):
            raise DatabaseConnectionError("error")

    def test_schedule_error_caught_by_eros_error(self):
        """Test ScheduleError can be caught by EROSError."""
        with pytest.raises(EROSError):
            raise TimingConflictError("conflict")

    def test_invalid_creator_id_caught_by_validation_error(self):
        """Test InvalidCreatorIdError can be caught by ValidationError."""
        with pytest.raises(ValidationError):
            raise InvalidCreatorIdError("id", "reason")

    def test_query_error_caught_by_database_error(self):
        """Test QueryError can be caught by DatabaseError."""
        with pytest.raises(DatabaseError):
            raise QueryError("error")
