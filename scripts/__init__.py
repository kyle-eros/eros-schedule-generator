"""EROS Schedule Generator - Public API.

This package provides automated PPV schedule generation for OnlyFans creators.

Quick Start:
    from scripts import ScheduleValidator, PersonaProfile, HookType
    from scripts import DB_PATH, get_database_path

    # Validate a schedule
    validator = ScheduleValidator()
    result = validator.validate(schedule_items)

Main Components:
    - generate_schedule: 9-step schedule generation pipeline (CLI script)
    - select_captions: Pool-based caption selection with Vose Alias
    - match_persona: Persona boost calculation for voice matching
    - validate_schedule: Business rule validation
    - weights: Weight calculation with payday awareness

Data Structures:
    - PersonaProfile: Creator voice/tone profile
    - StratifiedPools: Caption pools (proven, global_earner, discovery)
    - Caption: Individual caption with metadata
    - HookType: Opening hook categories

Database:
    - DB_PATH: Path to EROS database
    - get_database_path(): Resolve database location
    - get_database_connection(): Get cached connection
    - get_connection(): Thread-safe context manager

Note:
    The individual scripts (generate_schedule.py, select_captions.py, etc.)
    can be run standalone from the scripts directory. When importing as a
    package, use this __init__.py's public API.
"""

import sys
from pathlib import Path

# Version
__version__ = "2.1.0"

# Add scripts directory to path for internal imports
# This allows modules with non-relative imports to work when imported as a package
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# =============================================================================
# DATABASE
# =============================================================================

from .database import (  # noqa: E402
    DB_PATH,
    HOME_DIR,
    DatabaseNotFoundError,
    get_connection,
    get_database_connection,
    get_database_path,
)

# =============================================================================
# EXCEPTIONS
# =============================================================================
from .exceptions import (  # noqa: E402
    CaptionExhaustionError,
    ConfigurationError,
    CreatorNotFoundError,
    DatabaseError,
    ErosError,
    ValidationError,
    VaultEmptyError,
)

# =============================================================================
# HOOK DETECTION
# =============================================================================
from .hook_detection import (  # noqa: E402
    HOOK_PATTERNS,
    MIN_HOOK_DIVERSITY,
    SAME_HOOK_PENALTY,
    HookDetectionResult,
    HookType,
    detect_hook_type,
)

# =============================================================================
# LOGGING
# =============================================================================
from .logging_config import (  # noqa: E402
    configure_logging,
    get_logger,
    logger,
)

# =============================================================================
# PERSONA MATCHING
# =============================================================================
from .match_persona import (  # noqa: E402
    PersonaMatchResult,
    calculate_persona_boost,
    calculate_sentiment,
    detect_slang_level_from_text,
    detect_tone_from_text,
    get_persona_profile,
    match_captions_to_persona,
)

# =============================================================================
# CAPTION SELECTION
# =============================================================================
from .select_captions import (  # noqa: E402
    Caption,
    StratifiedPools,
    load_stratified_pools,
    select_captions,
    select_from_discovery_pool,
    select_from_proven_pool,
    select_from_standard_pools,
)

# =============================================================================
# DATA STRUCTURES (shared_context)
# =============================================================================
from .shared_context import (  # noqa: E402
    AgentInvokerMode,
    AgentRequest,
    AgentResponse,
    CreatorProfile,
    FollowUpSequence,
    PageTypeRules,
    PersonaProfile,
    PipelineState,
    PricingStrategy,
    RevenueProjection,
    RotationStrategy,
    ScheduleContext,
    TimingStrategy,
    ValidationResult,
)

# =============================================================================
# VALIDATION
# =============================================================================
from .validate_schedule import (  # noqa: E402
    ScheduleValidator,
    ValidationIssue,
    # ValidationResult imported from shared_context (canonical source)
)

# =============================================================================
# WEIGHTS
# =============================================================================
from .weights import (  # noqa: E402
    DISCOVERY_BONUS_WEIGHT,
    EARNINGS_WEIGHT,
    FRESHNESS_WEIGHT,
    PAYDAY_WEIGHT,
    PERSONA_WEIGHT,
    POOL_DISCOVERY,
    POOL_GLOBAL_EARNER,
    POOL_PROVEN,
    calculate_discovery_bonus,
    calculate_payday_multiplier,
    calculate_weight,
    determine_pool_type,
    get_effective_earnings_proxy,
    get_max_earnings,
    get_payday_score,
    is_high_payday_multiplier,
    is_mid_cycle,
)

# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Version
    "__version__",
    # Database
    "DB_PATH",
    "HOME_DIR",
    "get_database_path",
    "get_database_connection",
    "get_connection",
    "DatabaseNotFoundError",
    # Exceptions
    "ErosError",
    "DatabaseError",
    "CreatorNotFoundError",
    "CaptionExhaustionError",
    "VaultEmptyError",
    "ValidationError",
    "ConfigurationError",
    # Logging
    "configure_logging",
    "get_logger",
    "logger",
    # Data structures
    "ScheduleContext",
    "PersonaProfile",
    "CreatorProfile",
    "PricingStrategy",
    "TimingStrategy",
    "RotationStrategy",
    "FollowUpSequence",
    "RevenueProjection",
    "PageTypeRules",
    "ValidationResult",
    "AgentInvokerMode",
    "AgentRequest",
    "AgentResponse",
    "PipelineState",
    # Hook detection
    "HookType",
    "detect_hook_type",
    "HookDetectionResult",
    "SAME_HOOK_PENALTY",
    "MIN_HOOK_DIVERSITY",
    "HOOK_PATTERNS",
    # Weights
    "calculate_weight",
    "calculate_discovery_bonus",
    "calculate_payday_multiplier",
    "get_payday_score",
    "is_high_payday_multiplier",
    "is_mid_cycle",
    "get_effective_earnings_proxy",
    "get_max_earnings",
    "determine_pool_type",
    "POOL_PROVEN",
    "POOL_GLOBAL_EARNER",
    "POOL_DISCOVERY",
    "EARNINGS_WEIGHT",
    "FRESHNESS_WEIGHT",
    "PERSONA_WEIGHT",
    "DISCOVERY_BONUS_WEIGHT",
    "PAYDAY_WEIGHT",
    # Validation
    "ScheduleValidator",
    "ValidationIssue",
    # Caption selection
    "select_captions",
    "StratifiedPools",
    "Caption",
    "load_stratified_pools",
    "select_from_proven_pool",
    "select_from_standard_pools",
    "select_from_discovery_pool",
    # Persona matching
    "get_persona_profile",
    "calculate_persona_boost",
    "PersonaMatchResult",
    "match_captions_to_persona",
    "detect_tone_from_text",
    "detect_slang_level_from_text",
    "calculate_sentiment",
]
