"""Pricing module for EROS schedule generator.

This module provides confidence-based pricing adjustments to optimize
conversion rates based on creator maturity and prediction confidence.

Exports:
    CONFIDENCE_PRICING_MULTIPLIERS: Tier-based multiplier configuration.
    STANDARD_PRICE_POINTS: Common price points for rounding.
    get_confidence_price_multiplier: Get multiplier for confidence score.
    adjust_price_by_confidence: Full price adjustment with metadata.
    FirstToTipPriceRotator: Price rotation for first-to-tip send types.
"""

from __future__ import annotations

from python.pricing.confidence_pricing import (
    CONFIDENCE_PRICING_MULTIPLIERS,
    STANDARD_PRICE_POINTS,
    adjust_price_by_confidence,
    get_confidence_price_multiplier,
)
from python.pricing.first_to_tip import FirstToTipPriceRotator

__all__ = [
    "CONFIDENCE_PRICING_MULTIPLIERS",
    "STANDARD_PRICE_POINTS",
    "adjust_price_by_confidence",
    "get_confidence_price_multiplier",
    "FirstToTipPriceRotator",
]
