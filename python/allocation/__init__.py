"""
Allocation module for EROS Schedule Generator.

Handles volume tier classification and send type allocation across
the weekly schedule based on fan count, page type, and performance metrics.
"""

from python.allocation.send_type_allocator import (
    SendTypeAllocator,
    VolumeTier,
    VolumeConfig,
)

__all__ = [
    "SendTypeAllocator",
    "VolumeTier",
    "VolumeConfig",
]
