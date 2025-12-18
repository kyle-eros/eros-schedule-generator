"""
Matching module for EROS Schedule Generator.

Handles intelligent caption selection and matching based on:
- Performance scoring
- Freshness tracking
- Type priority alignment
- Persona compatibility
- Diversity requirements
"""

from python.matching.caption_matcher import (
    CaptionMatcher,
    Caption,
    CaptionScore,
)

__all__ = [
    "CaptionMatcher",
    "Caption",
    "CaptionScore",
]
