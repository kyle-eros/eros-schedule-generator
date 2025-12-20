"""
EROS Schedule Generator - OnlyFans Content Scheduling Optimization System.

A production-grade scheduling system for OnlyFans creators that optimizes
content distribution, timing, and revenue generation through data-driven
algorithms and machine learning.
"""

__version__ = "3.0.0"
__author__ = "EROS Team"

# Domain model exports (Wave 3)
from python.models import (
    Creator,
    CreatorProfile,
    Caption,
    CaptionScore,
    ScheduleItem,
    ScheduleTemplate,
    SendType,
    SendTypeConfig,
    VolumeConfig,
    VolumeTier,
    # PPV restructuring additions
    TipGoalMode,
    PPV_TYPES,
    PPV_REVENUE_TYPES,
    DEPRECATED_SEND_TYPES,
    SEND_TYPE_ALIASES,
    PAGE_TYPE_FREE_ONLY,
    PAGE_TYPE_PAID_ONLY,
    REVENUE_TYPES,
    ENGAGEMENT_TYPES,
    RETENTION_TYPES,
    resolve_send_type_key,
    is_valid_for_page_type,
)

# Registry exports (Wave 3)
from python.registry import SendTypeRegistry

# Configuration exports (Wave 3)
from python.config import Settings

# Core allocation exports
from python.allocation import SendTypeAllocator

# Caption matching exports
from python.matching import CaptionMatcher

# Optimization exports
from python.optimization import ScheduleOptimizer

# Validation exports
from python.validation import (
    VaultValidator,
    VaultValidationResult,
    ContentTypePreference,
)

# Exception exports
from python.exceptions import (
    EROSError,
    CreatorNotFoundError,
    InsufficientCaptionsError,
    ValidationError,
    InvalidCreatorIdError,
    InvalidSendTypeError,
    InvalidDateRangeError,
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ConfigurationError,
    MissingConfigError,
    ScheduleError,
    ScheduleCapacityError,
    TimingConflictError,
)

# Logging exports
from python.logging_config import (
    configure_logging,
    get_logger,
    get_context_logger,
    log_fallback,
)

# Validator exports
from python.validators import (
    validate_creator_id,
    validate_send_type_key,
    validate_date_range,
    validate_page_type,
    validate_category,
    is_valid_creator_id,
    is_valid_send_type_key,
    VALID_SEND_TYPE_KEYS,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Domain Models (Wave 3)
    "Creator",
    "CreatorProfile",
    "Caption",
    "CaptionScore",
    "ScheduleItem",
    "ScheduleTemplate",
    "SendType",
    "SendTypeConfig",
    "VolumeConfig",
    "VolumeTier",
    # PPV Restructuring
    "TipGoalMode",
    "PPV_TYPES",
    "PPV_REVENUE_TYPES",
    "DEPRECATED_SEND_TYPES",
    "SEND_TYPE_ALIASES",
    "PAGE_TYPE_FREE_ONLY",
    "PAGE_TYPE_PAID_ONLY",
    "REVENUE_TYPES",
    "ENGAGEMENT_TYPES",
    "RETENTION_TYPES",
    "resolve_send_type_key",
    "is_valid_for_page_type",
    # Registry (Wave 3)
    "SendTypeRegistry",
    # Configuration (Wave 3)
    "Settings",
    # Allocation
    "SendTypeAllocator",
    # Matching
    "CaptionMatcher",
    # Optimization
    "ScheduleOptimizer",
    # Validation
    "VaultValidator",
    "VaultValidationResult",
    "ContentTypePreference",
    # Exceptions
    "EROSError",
    "CreatorNotFoundError",
    "InsufficientCaptionsError",
    "ValidationError",
    "InvalidCreatorIdError",
    "InvalidSendTypeError",
    "InvalidDateRangeError",
    "DatabaseError",
    "DatabaseConnectionError",
    "QueryError",
    "ConfigurationError",
    "MissingConfigError",
    "ScheduleError",
    "ScheduleCapacityError",
    "TimingConflictError",
    # Logging
    "configure_logging",
    "get_logger",
    "get_context_logger",
    "log_fallback",
    # Validators
    "validate_creator_id",
    "validate_send_type_key",
    "validate_date_range",
    "validate_page_type",
    "validate_category",
    "is_valid_creator_id",
    "is_valid_send_type_key",
    "VALID_SEND_TYPE_KEYS",
]
