"""
Shared context dataclass for inter-agent communication in EROS Schedule Generator.

This module provides backward-compatible imports for the ScheduleContext and related
dataclasses. All models are now centralized in models.py.

NOTE: This module re-exports from models.py for backward compatibility.
New code should import directly from models.py.

Also includes data structures for hybrid agent invocation (Phase 2).
"""

# =============================================================================
# BACKWARD COMPATIBILITY IMPORTS
# =============================================================================
# All models are now centralized in models.py
# This module re-exports them for backward compatibility

from models import (
    # Enums
    AgentInvokerMode,
    # Agent/Pipeline Dataclasses
    AgentRequest,
    AgentResponse,
    FollowUpSequence,
    PageTypeRules,
    PersonaProfile,
    PipelineState,
    PricingStrategy,
    RevenueProjection,
    RotationStrategy,
    ScheduleContext,
    TimingStrategy,
)

# Note: CreatorProfile in shared_context.py had different fields than in generate_schedule.py
# The models.py version uses the generate_schedule.py definition (more complete)
# For backward compatibility with code expecting the old shared_context CreatorProfile,
# we provide an alias that maps to the models version
from models import CreatorProfile

# ValidationResult in shared_context.py was for agent output, which differs from
# the ValidationResult in validate_schedule.py. We keep the models.py version
# which has the add_error/add_warning/add_info methods.
# Note: The agent ValidationResult was slightly different (had schedule_id, errors list)
# Code using the old agent-style ValidationResult should be updated.

# For agent-style validation result, we provide a legacy alias
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=False)
class AgentValidationResult:
    """
    Legacy: Output from validation-guardian agent.

    NOTE: This is kept for backward compatibility with agent code.
    For schedule validation, use models.ValidationResult instead.
    """

    schedule_id: str = ""
    validation_passed: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    auto_fixes_available: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""


# Alias for backward compatibility (some code may import ValidationResult from here)
ValidationResult = AgentValidationResult


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "AgentInvokerMode",
    # Agent/Pipeline Dataclasses
    "AgentRequest",
    "AgentResponse",
    "PipelineState",
    "CreatorProfile",
    "PersonaProfile",
    "PricingStrategy",
    "TimingStrategy",
    "RotationStrategy",
    "FollowUpSequence",
    "RevenueProjection",
    "PageTypeRules",
    "ValidationResult",  # Legacy agent-style
    "AgentValidationResult",  # Explicit legacy name
    "ScheduleContext",
]
