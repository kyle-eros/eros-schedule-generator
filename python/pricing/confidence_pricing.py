"""Confidence-based pricing adjustment module.

This module provides pricing adjustments based on confidence scores from
the volume optimization system. New creators with lower confidence scores
receive discounted prices to optimize conversion rates, while established
creators with higher confidence can maintain premium pricing.

Example:
    >>> from python.pricing.confidence_pricing import adjust_price_by_confidence
    >>> result = adjust_price_by_confidence(base_price=29.99, confidence=0.75)
    >>> print(result['suggested_price'])
    24.99
"""

from __future__ import annotations


# Confidence tier multipliers for pricing adjustments
# Higher confidence = more established creator = maintain premium pricing
# Lower confidence = newer creator = discount to optimize conversion
CONFIDENCE_PRICING_MULTIPLIERS: dict[str, dict[str, float]] = {
    "high": {"min": 0.80, "max": 1.00, "multiplier": 1.00},
    "medium": {"min": 0.60, "max": 0.79, "multiplier": 0.85},
    "low": {"min": 0.40, "max": 0.59, "multiplier": 0.70},
    "very_low": {"min": 0.00, "max": 0.39, "multiplier": 0.60},
}

# Standard price points for rounding
STANDARD_PRICE_POINTS: list[float] = [
    9.99,
    14.99,
    19.69,
    24.99,
    29.99,
    34.99,
    39.99,
]


def get_confidence_price_multiplier(confidence: float) -> float:
    """Get the pricing multiplier based on confidence score.

    Maps confidence scores to pricing multipliers using defined tiers.
    Uses >= for lower bounds to avoid boundary gaps between tiers.

    Args:
        confidence: Confidence score from 0.0 to 1.0.

    Returns:
        Pricing multiplier between 0.6 and 1.0.

    Raises:
        ValueError: If confidence is outside valid range [0.0, 1.0].

    Examples:
        >>> get_confidence_price_multiplier(0.95)
        1.0
        >>> get_confidence_price_multiplier(0.65)
        0.85
        >>> get_confidence_price_multiplier(0.45)
        0.7
        >>> get_confidence_price_multiplier(0.25)
        0.6
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(
            f"Confidence must be between 0.0 and 1.0, got {confidence}"
        )

    # Check tiers from highest to lowest using >= for lower bounds
    if confidence >= 0.80:
        return CONFIDENCE_PRICING_MULTIPLIERS["high"]["multiplier"]
    elif confidence >= 0.60:
        return CONFIDENCE_PRICING_MULTIPLIERS["medium"]["multiplier"]
    elif confidence >= 0.40:
        return CONFIDENCE_PRICING_MULTIPLIERS["low"]["multiplier"]
    else:
        return CONFIDENCE_PRICING_MULTIPLIERS["very_low"]["multiplier"]


def _get_confidence_tier(confidence: float) -> str:
    """Get the confidence tier name for a given confidence score.

    Args:
        confidence: Confidence score from 0.0 to 1.0.

    Returns:
        Tier name: 'high', 'medium', 'low', or 'very_low'.
    """
    if confidence >= 0.80:
        return "high"
    elif confidence >= 0.60:
        return "medium"
    elif confidence >= 0.40:
        return "low"
    else:
        return "very_low"


def _round_to_price_point(price: float) -> float:
    """Round a price to the nearest standard price point.

    Finds the closest standard price point to the given price.
    If price is above or below all standard points, returns the
    nearest boundary point.

    Args:
        price: The calculated price to round.

    Returns:
        The nearest standard price point.

    Examples:
        >>> _round_to_price_point(28.50)
        29.99
        >>> _round_to_price_point(12.00)
        9.99
        >>> _round_to_price_point(22.00)
        19.69
    """
    if not STANDARD_PRICE_POINTS:
        return price

    # Find the closest price point by minimum absolute difference
    closest = min(STANDARD_PRICE_POINTS, key=lambda p: abs(p - price))
    return closest


def _get_adjustment_reason(
    confidence: float,
    multiplier: float,
    base_price: float,
    suggested_price: float,
) -> str:
    """Generate a human-readable adjustment reason.

    Args:
        confidence: The confidence score used.
        multiplier: The multiplier applied.
        base_price: Original price before adjustment.
        suggested_price: Final suggested price.

    Returns:
        Descriptive reason for the price adjustment.
    """
    tier = _get_confidence_tier(confidence)
    discount_pct = int((1 - multiplier) * 100)

    tier_descriptions = {
        "high": "Established creator with high prediction confidence",
        "medium": "Growing creator with moderate prediction confidence",
        "low": "Newer creator with limited historical data",
        "very_low": "New creator optimizing for conversion",
    }

    description = tier_descriptions[tier]

    if multiplier == 1.0:
        return f"{description} - maintaining premium pricing"
    else:
        return (
            f"{description} - {discount_pct}% discount applied "
            f"(${base_price:.2f} -> ${suggested_price:.2f})"
        )


def adjust_price_by_confidence(
    base_price: float,
    confidence: float,
) -> dict[str, float | str]:
    """Adjust a base price based on confidence score.

    Applies confidence-based pricing multipliers and rounds to standard
    price points for optimal conversion. New creators with lower confidence
    scores receive discounted prices, while established creators maintain
    premium pricing.

    Args:
        base_price: The original price before adjustment.
        confidence: Confidence score from 0.0 to 1.0.

    Returns:
        Dictionary containing:
            - base_price: Original price
            - confidence: Input confidence score
            - multiplier: Applied pricing multiplier
            - calculated_price: Price after multiplier (before rounding)
            - suggested_price: Final price rounded to standard point
            - adjustment_reason: Human-readable explanation

    Raises:
        ValueError: If confidence is outside [0.0, 1.0] or base_price <= 0.

    Examples:
        >>> result = adjust_price_by_confidence(29.99, 0.85)
        >>> result['multiplier']
        1.0
        >>> result['suggested_price']
        29.99

        >>> result = adjust_price_by_confidence(29.99, 0.65)
        >>> result['multiplier']
        0.85
        >>> result['suggested_price']
        24.99

        >>> result = adjust_price_by_confidence(39.99, 0.30)
        >>> result['multiplier']
        0.6
        >>> result['suggested_price']
        24.99
    """
    if base_price <= 0:
        raise ValueError(f"Base price must be positive, got {base_price}")

    multiplier = get_confidence_price_multiplier(confidence)
    calculated_price = base_price * multiplier
    suggested_price = _round_to_price_point(calculated_price)

    adjustment_reason = _get_adjustment_reason(
        confidence=confidence,
        multiplier=multiplier,
        base_price=base_price,
        suggested_price=suggested_price,
    )

    return {
        "base_price": base_price,
        "confidence": confidence,
        "multiplier": multiplier,
        "calculated_price": round(calculated_price, 2),
        "suggested_price": suggested_price,
        "adjustment_reason": adjustment_reason,
    }
