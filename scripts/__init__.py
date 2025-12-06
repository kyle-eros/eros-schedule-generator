"""EROS Schedule Generator - Core Scripts Package.

This package provides the main functionality for generating optimized
weekly PPV schedules for OnlyFans creators.

Main Components:
    - generate_schedule: 9-step schedule generation pipeline
    - prepare_llm_context: Native LLM integration for semantic analysis
    - volume_optimizer: Multi-factor volume optimization
    - match_persona: Persona boost calculation for caption matching

Usage:
    from scripts import generate_schedule, prepare_llm_context
    from scripts import MultiFactorVolumeOptimizer, get_volume_tier
    from scripts import calculate_persona_boost, get_persona_profile
"""

# Note: Imports are deferred to avoid circular dependencies
# and to allow individual scripts to be run standalone.
# Use explicit imports when needed:
#
#   from scripts.generate_schedule import main as generate_schedule
#   from scripts.volume_optimizer import MultiFactorVolumeOptimizer
#   from scripts.match_persona import calculate_persona_boost

__all__ = [
    "generate_schedule",
    "prepare_llm_context",
    "volume_optimizer",
    "match_persona",
    "utils",
]

__version__ = "2.0.0"
