#!/usr/bin/env python3
"""
Custom Exceptions for EROS Schedule Generator.

This module provides a unified exception hierarchy for all EROS-related errors.
All custom exceptions inherit from ErosError for easy catching.

Usage:
    from exceptions import CreatorNotFoundError, CaptionExhaustionError

    try:
        creator = get_creator(creator_id)
    except CreatorNotFoundError as e:
        logger.error(f"Creator not found: {e.identifier}")

Exception Hierarchy:
    ErosError (base)
    ├── DatabaseError
    │   └── DatabaseNotFoundError
    ├── CreatorNotFoundError
    ├── CaptionExhaustionError
    ├── VaultEmptyError
    ├── ValidationError
    └── ConfigurationError
"""

from typing import Any

__all__ = [
    "ErosError",
    "DatabaseError",
    "DatabaseNotFoundError",
    "CreatorNotFoundError",
    "CaptionExhaustionError",
    "VaultEmptyError",
    "ValidationError",
    "ConfigurationError",
]


class ErosError(Exception):
    """Base exception for all EROS errors.

    All custom EROS exceptions inherit from this class,
    allowing easy catching of any EROS-related error.
    """

    pass


class DatabaseError(ErosError):
    """Database-related errors."""

    pass


class DatabaseNotFoundError(DatabaseError):
    """Database file not found at expected locations.

    Attributes:
        searched_paths: List of paths that were searched.
    """

    def __init__(self, searched_paths: list[str] | None = None, message: str | None = None) -> None:
        self.searched_paths = searched_paths or []
        if message:
            super().__init__(message)
        else:
            paths_str = "\n  - ".join(str(p) for p in self.searched_paths)
            super().__init__(
                f"EROS database not found. Searched:\n  - {paths_str}\n\n"
                "Set EROS_DATABASE_PATH environment variable or place database "
                "in a standard location."
            )


class CreatorNotFoundError(ErosError):
    """Creator not found in database.

    Attributes:
        identifier: The creator identifier (page_name or creator_id) that was not found.
    """

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Creator not found: {identifier}")


class CaptionExhaustionError(ErosError):
    """Not enough fresh captions available for scheduling.

    Attributes:
        creator_id: The creator who has exhausted captions.
        available: Number of captions available.
        required: Number of captions required.
        content_type: Optional specific content type that is exhausted.
    """

    def __init__(
        self,
        creator_id: str,
        available: int,
        required: int,
        content_type: str | None = None,
    ) -> None:
        self.creator_id = creator_id
        self.available = available
        self.required = required
        self.content_type = content_type

        msg = f"Caption exhaustion for {creator_id}: {available} available, {required} required"
        if content_type:
            msg += f" (content type: {content_type})"
        super().__init__(msg)


class VaultEmptyError(ErosError):
    """No content available in creator's vault.

    Attributes:
        creator_id: The creator with empty vault.
        content_type: Optional specific content type that is empty.
    """

    def __init__(self, creator_id: str, content_type: str | None = None) -> None:
        self.creator_id = creator_id
        self.content_type = content_type

        msg = f"Empty vault for {creator_id}"
        if content_type:
            msg += f" (content type: {content_type})"
        super().__init__(msg)


class ValidationError(ErosError):
    """Schedule validation failed.

    Attributes:
        issues: List of validation issues found.
        schedule_id: Optional ID of the schedule that failed validation.
    """

    def __init__(
        self,
        issues: list[str],
        message: str = "Validation failed",
        schedule_id: str | None = None,
    ) -> None:
        self.issues = issues
        self.schedule_id = schedule_id
        super().__init__(f"{message}: {len(issues)} issues found")


class ConfigurationError(ErosError):
    """Invalid configuration or settings.

    Attributes:
        setting: The configuration setting that is invalid.
        value: The invalid value.
        expected: Description of expected value.
    """

    def __init__(
        self,
        setting: str,
        value: Any = None,
        expected: str | None = None,
    ) -> None:
        self.setting = setting
        self.value = value
        self.expected = expected

        msg = f"Invalid configuration: {setting}"
        if value is not None:
            msg += f" = {value!r}"
        if expected:
            msg += f" (expected: {expected})"
        super().__init__(msg)
