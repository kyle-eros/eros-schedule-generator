"""
Optimization module for EROS Schedule Generator.

Handles schedule timing optimization, saturation adjustment,
and revenue maximization through intelligent time slot assignment.
"""

from python.optimization.schedule_optimizer import (
    ScheduleOptimizer,
    ScheduleItem,
)

__all__ = [
    "ScheduleOptimizer",
    "ScheduleItem",
]
