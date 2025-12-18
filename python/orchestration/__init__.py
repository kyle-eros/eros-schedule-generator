"""
Orchestration module for schedule generation workflow.

Provides quality validators, idempotency guards, timing integrations,
and workflow coordination for the multi-agent schedule generation pipeline.
"""

from python.orchestration.quality_validator import (
    CHANNEL_MAPPING,
    STANDARD_SEND_TYPES,
    MINIMUM_UNIQUE_TYPES,
    validate_send_type_diversity,
    validate_channel_assignment,
    validate_schedule_quality,
)

from python.orchestration.idempotency import (
    IdempotencyRecord,
    IdempotencyGuard,
    idempotent,
    get_timing_guard,
    reset_timing_guard,
    _timing_guard,
)

from python.orchestration.timing_integration import (
    TimingProfileIntegration,
    get_timing_integration,
    clear_timing_integration_cache,
)

from python.orchestration.timing_optimizer import (
    ROUND_MINUTES,
    JITTER_MIN,
    JITTER_MAX,
    apply_time_jitter,
    validate_jitter_result,
    get_jitter_stats,
)

from python.orchestration.timing_metrics import (
    TimingEvent,
    TimingMetrics,
)

from python.orchestration.followup_generator import (
    OPTIMAL_FOLLOWUP_MINUTES,
    DEFAULT_STD_DEV,
    DEFAULT_MIN_OFFSET,
    DEFAULT_MAX_OFFSET,
    MAX_REJECTION_ATTEMPTS,
    schedule_ppv_followup,
    validate_followup_window,
)

from python.orchestration.rotation_tracker import (
    InvalidTransitionError,
    RotationState,
    VALID_TRANSITIONS,
    validate_transition,
    transition_to,
    RotationStateData,
    db_get_creator_rotation_state,
    db_save_creator_rotation_state,
    PPVRotationTracker,
)

from python.orchestration.timing_saga import (
    SagaStatus,
    SagaStep,
    SagaResult,
    SagaStepError,
    Wave2TimingSaga,
)

from python.orchestration.pinned_post_manager import (
    PinItem,
    PinnedPostManager,
    PINNABLE_SEND_TYPES,
    SEND_TYPE_PRIORITY,
)

from python.orchestration.circuit_breaker import (
    CircuitState,
    CircuitStats,
    CircuitOpenError,
    CircuitBreaker,
    circuit_protected,
    rotation_state_circuit,
    timing_validation_circuit,
)

from python.orchestration.timing_validator import (
    # Type definitions
    RepairRecord,
    ValidationResult,
    RepairResult,
    # Constants
    PPV_STYLES,
    DEFAULT_AM_HOUR,
    DEFAULT_PM_HOUR,
    AM_PM_BOUNDARY,
    # Main validation functions
    validate_no_consecutive_same_style,
    validate_and_repair_consecutive_styles,
    # Utility functions
    get_ppv_style_distribution,
    count_consecutive_violations,
)

from python.orchestration.followup_limiter import (
    # Constants
    MAX_FOLLOWUPS_PER_DAY,
    FOLLOWUP_WEIGHTS,
    # Type definitions
    RemovedItemRecord,
    EnforcementResult,
    # Main functions
    enforce_daily_followup_limit,
    # Utility functions
    get_followup_priority_breakdown,
    count_followups,
)

from python.orchestration.weekly_limits import (
    # Constants
    WEEKLY_LIMITS,
    # Type definitions
    ViolationRecord,
    ValidationResult as WeeklyValidationResult,
    EnforcementResult as WeeklyEnforcementResult,
    WarningRecord,
    # Main functions
    validate_weekly_limits,
    enforce_weekly_limits,
    # Helper functions
    get_weekly_limits,
    get_limited_send_types,
    get_limit_for_send_type,
    is_limited_send_type,
    count_limited_send_types,
    get_limit_rationale,
)

from python.orchestration.daily_flavor import (
    # Type definitions
    FlavorProfile,
    # Constants
    DAILY_FLAVORS,
    # Main functions
    get_daily_flavor,
    weight_send_types_by_flavor,
    get_daily_caption_filter,
    # Utility functions
    get_flavor_for_week,
)

from python.orchestration.label_manager import (
    # Constants
    SEND_TYPE_LABELS,
    AVAILABLE_LABELS,
    # Main functions
    assign_label,
    apply_labels_to_schedule,
    get_label_summary,
    # Helper functions
    get_available_labels,
    get_send_types_for_label,
)

from python.orchestration.chatter_sync import (
    # Constants
    CHATTER_CHANNELS,
    CHATTER_SEND_TYPES,
    # Class
    ChatterContentSync,
    # Module-level function
    export_chatter_manifest_json,
)

__all__ = [
    # Quality validation
    'CHANNEL_MAPPING',
    'STANDARD_SEND_TYPES',
    'MINIMUM_UNIQUE_TYPES',
    'validate_send_type_diversity',
    'validate_channel_assignment',
    'validate_schedule_quality',
    # Idempotency
    'IdempotencyRecord',
    'IdempotencyGuard',
    'idempotent',
    'get_timing_guard',
    'reset_timing_guard',
    '_timing_guard',
    # Timing Integration (Wave 2)
    'TimingProfileIntegration',
    'get_timing_integration',
    'clear_timing_integration_cache',
    # Time Jitter (Wave 2)
    'ROUND_MINUTES',
    'JITTER_MIN',
    'JITTER_MAX',
    'apply_time_jitter',
    'validate_jitter_result',
    'get_jitter_stats',
    # Timing Metrics (Wave 2)
    'TimingEvent',
    'TimingMetrics',
    # Followup Generator (Wave 2)
    'OPTIMAL_FOLLOWUP_MINUTES',
    'DEFAULT_STD_DEV',
    'DEFAULT_MIN_OFFSET',
    'DEFAULT_MAX_OFFSET',
    'MAX_REJECTION_ATTEMPTS',
    'schedule_ppv_followup',
    'validate_followup_window',
    # Rotation Tracker (Wave 2)
    'InvalidTransitionError',
    'RotationState',
    'VALID_TRANSITIONS',
    'validate_transition',
    'transition_to',
    'RotationStateData',
    'db_get_creator_rotation_state',
    'db_save_creator_rotation_state',
    'PPVRotationTracker',
    # Timing Saga (Wave 2)
    'SagaStatus',
    'SagaStep',
    'SagaResult',
    'SagaStepError',
    'Wave2TimingSaga',
    # Pinned Post Management (Wave 2)
    'PinItem',
    'PinnedPostManager',
    'PINNABLE_SEND_TYPES',
    'SEND_TYPE_PRIORITY',
    # Circuit Breaker (Wave 2)
    'CircuitState',
    'CircuitStats',
    'CircuitOpenError',
    'CircuitBreaker',
    'circuit_protected',
    'rotation_state_circuit',
    'timing_validation_circuit',
    # Timing Validator (Wave 2) - Same-Style Back-to-Back Prevention
    'RepairRecord',
    'ValidationResult',
    'RepairResult',
    'PPV_STYLES',
    'DEFAULT_AM_HOUR',
    'DEFAULT_PM_HOUR',
    'AM_PM_BOUNDARY',
    'validate_no_consecutive_same_style',
    'validate_and_repair_consecutive_styles',
    'get_ppv_style_distribution',
    'count_consecutive_violations',
    # Followup Limiter (Wave 3) - Daily Followup Limit Enforcement
    'MAX_FOLLOWUPS_PER_DAY',
    'FOLLOWUP_WEIGHTS',
    'RemovedItemRecord',
    'EnforcementResult',
    'enforce_daily_followup_limit',
    'get_followup_priority_breakdown',
    'count_followups',
    # Weekly Limits (Wave 3) - Weekly Send Type Limit Enforcement
    'WEEKLY_LIMITS',
    'ViolationRecord',
    'WeeklyValidationResult',
    'WeeklyEnforcementResult',
    'WarningRecord',
    'validate_weekly_limits',
    'enforce_weekly_limits',
    'get_weekly_limits',
    'get_limited_send_types',
    'get_limit_for_send_type',
    'is_limited_send_type',
    'count_limited_send_types',
    'get_limit_rationale',
    # Daily Flavor Rotation (Gap 3.4) - Day-of-Week Thematic Variation
    'FlavorProfile',
    'DAILY_FLAVORS',
    'get_daily_flavor',
    'weight_send_types_by_flavor',
    'get_daily_caption_filter',
    'get_flavor_for_week',
    # Label Manager (Gap 10.10) - Campaign Label Assignment
    'SEND_TYPE_LABELS',
    'AVAILABLE_LABELS',
    'assign_label',
    'apply_labels_to_schedule',
    'get_label_summary',
    'get_available_labels',
    'get_send_types_for_label',
    # Chatter Sync (Gap 6.3) - Chatter Team Content Manifest
    'CHATTER_CHANNELS',
    'CHATTER_SEND_TYPES',
    'ChatterContentSync',
    'export_chatter_manifest_json',
]
