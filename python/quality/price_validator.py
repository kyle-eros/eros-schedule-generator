"""Optimal Price Point Validator for EROS Schedule Generator.

Validates that PPV pricing aligns with caption length for maximum Revenue Per Send (RPS).
Based on Gap 10.11 & 10.12 analysis showing $19.69 appears in 75% of top 20 earners
and REQUIRES 250-449 character captions. Wrong length = 82% RPS loss (CRITICAL).

Version: 1.0.0
Wave 5 Task 5.1

Research-backed price tiers:
    - $14.99: 0-249 chars (impulse buy, 469 RPS avg)
    - $19.69: 250-449 chars (OPTIMAL, 716 RPS avg)
    - $24.99: 450-599 chars (premium, 565 RPS avg)
    - $29.99: 600-749 chars (high premium, 278 RPS avg)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from python.logging_config import get_logger
from python.exceptions import ValidationError

logger = get_logger(__name__)


# =============================================================================
# Price-Length Configuration Matrix
# =============================================================================

PRICE_LENGTH_MATRIX: dict[float, dict[str, Any]] = {
    14.99: {
        "min_chars": 0,
        "max_chars": 249,
        "tier_name": "impulse",
        "expected_rps": 469,
        "description": "Quick impulse buy - short, punchy captions",
        "optimal_range": (0, 249),
    },
    19.69: {
        "min_chars": 250,
        "max_chars": 449,
        "tier_name": "optimal",
        "expected_rps": 716,
        "description": "Sweet spot - balanced value perception",
        "optimal_range": (250, 449),
    },
    24.99: {
        "min_chars": 450,
        "max_chars": 599,
        "tier_name": "premium",
        "expected_rps": 565,
        "description": "Premium tier - detailed narrative required",
        "optimal_range": (450, 599),
    },
    29.99: {
        "min_chars": 600,
        "max_chars": 749,
        "tier_name": "high_premium",
        "expected_rps": 278,
        "description": "High premium - extensive content description needed",
        "optimal_range": (600, 749),
    },
}

# Sorted prices for lookup operations
SORTED_PRICES = sorted(PRICE_LENGTH_MATRIX.keys())


# =============================================================================
# Mismatch Penalty Configuration
# =============================================================================

MISMATCH_PENALTIES: dict[float, dict[str, dict[str, Any]]] = {
    14.99: {
        "too_long": {
            "penalty_multiplier": 0.65,
            "rps_loss_pct": 35,
            "severity": "MEDIUM",
            "reason": "Over-explanation reduces impulse conversion",
        },
    },
    19.69: {
        "too_short": {
            "penalty_multiplier": 0.18,
            "rps_loss_pct": 82,
            "severity": "CRITICAL",
            "reason": "Insufficient value justification for price point",
        },
        "too_long": {
            "penalty_multiplier": 0.55,
            "rps_loss_pct": 45,
            "severity": "HIGH",
            "reason": "Diminishing returns - buyer fatigue sets in",
        },
    },
    24.99: {
        "too_short": {
            "penalty_multiplier": 0.40,
            "rps_loss_pct": 60,
            "severity": "HIGH",
            "reason": "Premium price requires premium narrative",
        },
        "too_long": {
            "penalty_multiplier": 0.75,
            "rps_loss_pct": 25,
            "severity": "MEDIUM",
            "reason": "Slight over-description acceptable at premium tier",
        },
    },
    29.99: {
        "too_short": {
            "penalty_multiplier": 0.30,
            "rps_loss_pct": 70,
            "severity": "CRITICAL",
            "reason": "High premium price demands extensive value communication",
        },
        "too_long": {
            "penalty_multiplier": 0.85,
            "rps_loss_pct": 15,
            "severity": "LOW",
            "reason": "Extra detail tolerated at highest tier",
        },
    },
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class PriceValidationResult:
    """Immutable result of price-length validation.

    Attributes:
        is_valid: Whether the caption length matches the price point.
        price: The price being validated.
        char_count: Number of characters in the caption.
        optimal_range: Tuple of (min_chars, max_chars) for this price.
        tier_name: Name of the price tier (impulse, optimal, premium, high_premium).
        expected_rps: Expected RPS for optimal match.
        mismatch_type: Type of mismatch if invalid (too_short, too_long, or None).
        expected_rps_loss: Percentage of RPS loss due to mismatch (e.g., '82%').
        severity: Severity level if mismatched (CRITICAL, HIGH, MEDIUM, LOW, or None).
        message: Human-readable validation message.
        recommendation: Actionable recommendation for fixing the mismatch.
        alternative_prices: List of better price alternatives for current length.
    """

    is_valid: bool
    price: float
    char_count: int
    optimal_range: tuple[int, int]
    tier_name: str
    expected_rps: int
    mismatch_type: str | None
    expected_rps_loss: str | None
    severity: str | None
    message: str
    recommendation: str
    alternative_prices: tuple[dict[str, Any], ...]


# =============================================================================
# Validation Functions
# =============================================================================


def validate_price_length_match(caption: str, price: float) -> dict[str, Any]:
    """Validate that caption length matches optimal range for price point.

    This is a CRITICAL validation. Research shows $19.69 with wrong caption length
    results in 82% RPS loss. The price-length relationship is the single most
    important factor in PPV conversion optimization.

    Args:
        caption: The PPV caption text to validate.
        price: The PPV price point (e.g., 14.99, 19.69, 24.99, 29.99).

    Returns:
        Dictionary containing validation result with keys:
            - is_valid: bool - True if length matches price optimal range
            - price: float - The validated price
            - char_count: int - Caption character count
            - optimal_range: tuple[int, int] - (min, max) chars for this price
            - tier_name: str - Price tier name
            - expected_rps: int - Expected RPS for optimal match
            - mismatch_type: str | None - 'too_short', 'too_long', or None
            - expected_rps_loss: str | None - Percentage loss (e.g., '82%')
            - severity: str | None - CRITICAL, HIGH, MEDIUM, LOW, or None
            - message: str - Human-readable result message
            - recommendation: str - Actionable fix recommendation
            - alternative_prices: list[dict] - Better prices for current length

    Raises:
        ValidationError: If caption is empty/invalid or price is not supported.

    Examples:
        >>> result = validate_price_length_match("Short caption here", 19.69)
        >>> result['is_valid']
        False
        >>> result['severity']
        'CRITICAL'
        >>> result['expected_rps_loss']
        '82%'

        >>> result = validate_price_length_match("A" * 300, 19.69)
        >>> result['is_valid']
        True
        >>> result['severity'] is None
        True
    """
    # Input validation
    if not caption:
        raise ValidationError(
            message="Caption cannot be empty",
            field="caption",
            value=caption,
        )
    if not isinstance(caption, str):
        raise ValidationError(
            message="Caption must be a string",
            field="caption",
            value=type(caption).__name__,
        )

    # Validate price is supported
    price_config = PRICE_LENGTH_MATRIX.get(price)
    if price_config is None:
        # Find nearest supported price for better error message
        nearest = min(SORTED_PRICES, key=lambda p: abs(p - price))
        raise ValidationError(
            message=f"Unsupported price point: ${price:.2f}. Nearest supported: ${nearest:.2f}",
            field="price",
            value=price,
            details={"supported_prices": SORTED_PRICES},
        )

    char_count = len(caption)
    min_chars = price_config["min_chars"]
    max_chars = price_config["max_chars"]
    optimal_range = price_config["optimal_range"]
    tier_name = price_config["tier_name"]
    expected_rps = price_config["expected_rps"]

    logger.debug(
        f"Validating price-length match: {char_count} chars at ${price:.2f}",
        extra={"char_count": char_count, "price": price, "tier": tier_name},
    )

    # Check if within optimal range
    is_valid = min_chars <= char_count <= max_chars

    if is_valid:
        # Perfect match
        logger.info(
            f"Price-length match valid: {char_count} chars optimal for ${price:.2f}",
            extra={"char_count": char_count, "price": price, "rps": expected_rps},
        )
        return {
            "is_valid": True,
            "price": price,
            "char_count": char_count,
            "optimal_range": optimal_range,
            "tier_name": tier_name,
            "expected_rps": expected_rps,
            "mismatch_type": None,
            "expected_rps_loss": None,
            "severity": None,
            "message": f"Caption length ({char_count} chars) is optimal for ${price:.2f} ({tier_name} tier)",
            "recommendation": f"No changes needed. Expected RPS: {expected_rps}",
            "alternative_prices": [],
        }

    # Determine mismatch type and get penalty config
    if char_count < min_chars:
        mismatch_type = "too_short"
        chars_diff = min_chars - char_count
        direction_msg = f"Add {chars_diff} more characters"
    else:
        mismatch_type = "too_long"
        chars_diff = char_count - max_chars
        direction_msg = f"Remove {chars_diff} characters"

    # Get penalty details for this price/mismatch combo
    penalty_config = MISMATCH_PENALTIES.get(price, {}).get(mismatch_type)

    if penalty_config:
        rps_loss_pct = penalty_config["rps_loss_pct"]
        severity = penalty_config["severity"]
        reason = penalty_config["reason"]
    else:
        # Fallback for edge cases
        rps_loss_pct = 30
        severity = "MEDIUM"
        reason = "Caption length outside optimal range"

    # Get alternative price suggestions
    alternative_prices = _suggest_alternative_prices(char_count)

    # Build detailed message based on severity
    if severity == "CRITICAL":
        message = (
            f"CRITICAL: Price-length mismatch at ${price:.2f}! "
            f"Caption has {char_count} chars but optimal range is {min_chars}-{max_chars}. "
            f"Expected {rps_loss_pct}% RPS loss. {reason}."
        )
    else:
        message = (
            f"Price-length mismatch at ${price:.2f}: "
            f"Caption has {char_count} chars (optimal: {min_chars}-{max_chars}). "
            f"Expected {rps_loss_pct}% RPS loss."
        )

    # Build actionable recommendation
    if alternative_prices:
        best_alt = alternative_prices[0]
        recommendation = (
            f"{direction_msg} to reach optimal range ({min_chars}-{max_chars}), "
            f"OR adjust price to ${best_alt['price']:.2f} ({best_alt['tier_name']} tier) "
            f"for optimal RPS."
        )
    else:
        recommendation = f"{direction_msg} to reach optimal range ({min_chars}-{max_chars})."

    # Log warning for mismatches
    log_level = logger.error if severity == "CRITICAL" else logger.warning
    log_level(
        f"Price-length mismatch: {char_count} chars at ${price:.2f}",
        extra={
            "char_count": char_count,
            "price": price,
            "mismatch_type": mismatch_type,
            "rps_loss_pct": rps_loss_pct,
            "severity": severity,
        },
    )

    return {
        "is_valid": False,
        "price": price,
        "char_count": char_count,
        "optimal_range": optimal_range,
        "tier_name": tier_name,
        "expected_rps": expected_rps,
        "mismatch_type": mismatch_type,
        "expected_rps_loss": f"{rps_loss_pct}%",
        "severity": severity,
        "message": message,
        "recommendation": recommendation,
        "alternative_prices": alternative_prices,
    }


def _suggest_alternative_prices(char_count: int) -> list[dict[str, Any]]:
    """Suggest alternative price points that better match the caption length.

    Analyzes the caption character count and returns price points where
    the length falls within optimal range, sorted by expected RPS (highest first).

    Args:
        char_count: Number of characters in the caption.

    Returns:
        List of dictionaries containing alternative price suggestions, each with:
            - price: float - The suggested price point
            - tier_name: str - Name of the price tier
            - expected_rps: int - Expected RPS at this price
            - optimal_range: tuple[int, int] - Character range for this tier
            - reason: str - Why this price is recommended

    Examples:
        >>> alternatives = _suggest_alternative_prices(180)
        >>> alternatives[0]['price']
        14.99
        >>> alternatives[0]['tier_name']
        'impulse'

        >>> alternatives = _suggest_alternative_prices(350)
        >>> alternatives[0]['price']
        19.69
        >>> alternatives[0]['expected_rps']
        716
    """
    alternatives: list[dict[str, Any]] = []

    for price, config in PRICE_LENGTH_MATRIX.items():
        min_chars = config["min_chars"]
        max_chars = config["max_chars"]

        # Check if char_count falls within this tier's optimal range
        if min_chars <= char_count <= max_chars:
            alternatives.append({
                "price": price,
                "tier_name": config["tier_name"],
                "expected_rps": config["expected_rps"],
                "optimal_range": config["optimal_range"],
                "reason": (
                    f"Caption length ({char_count} chars) is optimal for "
                    f"${price:.2f} ({config['tier_name']} tier)"
                ),
            })

    # Sort by expected RPS (highest first) for best recommendations
    alternatives.sort(key=lambda x: x["expected_rps"], reverse=True)

    return alternatives


def get_optimal_price_for_length(char_count: int) -> dict[str, Any]:
    """Get the optimal price point for a given caption length.

    This is a convenience function for determining what price to set
    based on an existing caption's length.

    Args:
        char_count: Number of characters in the caption.

    Returns:
        Dictionary containing optimal price recommendation:
            - price: float - The optimal price point
            - tier_name: str - Name of the price tier
            - expected_rps: int - Expected RPS at this price
            - optimal_range: tuple[int, int] - Full range for the tier
            - in_range: bool - Whether char_count is within any tier
            - recommendation: str - Pricing recommendation

    Examples:
        >>> result = get_optimal_price_for_length(300)
        >>> result['price']
        19.69
        >>> result['expected_rps']
        716

        >>> result = get_optimal_price_for_length(800)
        >>> result['in_range']
        False
    """
    alternatives = _suggest_alternative_prices(char_count)

    if alternatives:
        best = alternatives[0]
        return {
            "price": best["price"],
            "tier_name": best["tier_name"],
            "expected_rps": best["expected_rps"],
            "optimal_range": best["optimal_range"],
            "in_range": True,
            "recommendation": (
                f"Set price to ${best['price']:.2f} for optimal RPS ({best['expected_rps']})"
            ),
        }

    # Char count outside all ranges - find nearest tier
    if char_count < PRICE_LENGTH_MATRIX[14.99]["min_chars"]:
        # Below minimum (shouldn't happen with min=0)
        nearest_price = 14.99
        recommendation = "Extremely short caption - consider expanding for better conversion"
    elif char_count > PRICE_LENGTH_MATRIX[29.99]["max_chars"]:
        # Above maximum range
        nearest_price = 29.99
        excess = char_count - PRICE_LENGTH_MATRIX[29.99]["max_chars"]
        recommendation = (
            f"Caption exceeds optimal range by {excess} chars. "
            f"Consider trimming to 600-749 chars for ${29.99:.2f}, "
            f"or proceed with ${29.99:.2f} accepting reduced RPS"
        )
    else:
        # In a gap between tiers (shouldn't happen with contiguous ranges)
        nearest_price = min(
            SORTED_PRICES,
            key=lambda p: min(
                abs(char_count - PRICE_LENGTH_MATRIX[p]["min_chars"]),
                abs(char_count - PRICE_LENGTH_MATRIX[p]["max_chars"]),
            ),
        )
        recommendation = f"Adjust length to match ${nearest_price:.2f} tier"

    config = PRICE_LENGTH_MATRIX[nearest_price]
    return {
        "price": nearest_price,
        "tier_name": config["tier_name"],
        "expected_rps": config["expected_rps"],
        "optimal_range": config["optimal_range"],
        "in_range": False,
        "recommendation": recommendation,
    }


def calculate_rps_impact(
    caption: str,
    current_price: float,
    target_price: float | None = None,
) -> dict[str, Any]:
    """Calculate the RPS impact of price-length alignment.

    Provides detailed analysis of current state and potential improvement
    by adjusting either price or caption length.

    Args:
        caption: The PPV caption text.
        current_price: Current price point.
        target_price: Optional target price to analyze adjustment to.

    Returns:
        Dictionary containing RPS impact analysis:
            - current_state: Validation result for current price
            - optimal_price: Best price for current caption length
            - rps_improvement: Potential RPS gain with optimal pricing
            - target_analysis: Validation for target_price if provided

    Raises:
        ValidationError: If caption is empty/invalid or prices not supported.

    Examples:
        >>> impact = calculate_rps_impact("Short text", 19.69)
        >>> impact['rps_improvement'] > 0
        True
    """
    if not caption:
        raise ValidationError(
            message="Caption cannot be empty",
            field="caption",
            value=caption,
        )

    char_count = len(caption)

    # Get current state
    current_state = validate_price_length_match(caption, current_price)

    # Get optimal price for this length
    optimal_result = get_optimal_price_for_length(char_count)

    # Calculate potential improvement
    current_rps = current_state["expected_rps"]
    if not current_state["is_valid"]:
        # Apply penalty to current RPS
        penalty_config = MISMATCH_PENALTIES.get(current_price, {}).get(
            current_state["mismatch_type"], {}
        )
        penalty_mult = penalty_config.get("penalty_multiplier", 0.7)
        effective_current_rps = int(current_rps * penalty_mult)
    else:
        effective_current_rps = current_rps

    optimal_rps = optimal_result["expected_rps"] if optimal_result["in_range"] else 0
    rps_improvement = max(0, optimal_rps - effective_current_rps)

    result = {
        "current_state": current_state,
        "optimal_price": optimal_result,
        "effective_current_rps": effective_current_rps,
        "potential_optimal_rps": optimal_rps,
        "rps_improvement": rps_improvement,
        "improvement_percentage": (
            round((rps_improvement / effective_current_rps) * 100, 1)
            if effective_current_rps > 0
            else 0
        ),
    }

    # Analyze target price if provided
    if target_price is not None:
        target_analysis = validate_price_length_match(caption, target_price)
        result["target_analysis"] = target_analysis

    logger.info(
        f"RPS impact analysis: current ${current_price:.2f} ({effective_current_rps} RPS) "
        f"-> optimal ${optimal_result['price']:.2f} ({optimal_rps} RPS), "
        f"+{rps_improvement} RPS potential",
        extra={
            "char_count": char_count,
            "current_price": current_price,
            "optimal_price": optimal_result["price"],
            "rps_improvement": rps_improvement,
        },
    )

    return result


# =============================================================================
# Batch Validation
# =============================================================================


def validate_batch(
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate multiple caption-price pairs in batch.

    Efficiently validates a list of caption-price pairs and provides
    aggregate statistics on mismatches.

    Args:
        items: List of dictionaries with 'caption' and 'price' keys.

    Returns:
        Dictionary containing:
            - results: List of individual validation results
            - summary: Aggregate statistics
            - critical_count: Number of CRITICAL severity mismatches
            - total_rps_at_risk: Estimated total RPS loss from mismatches

    Examples:
        >>> items = [
        ...     {"caption": "Short", "price": 19.69},
        ...     {"caption": "A" * 300, "price": 19.69},
        ... ]
        >>> batch_result = validate_batch(items)
        >>> batch_result['summary']['valid_count']
        1
        >>> batch_result['critical_count']
        1
    """
    results: list[dict[str, Any]] = []
    valid_count = 0
    invalid_count = 0
    critical_count = 0
    high_count = 0
    total_rps_at_risk = 0

    for idx, item in enumerate(items):
        caption = item.get("caption", "")
        price = item.get("price", 0.0)

        try:
            result = validate_price_length_match(caption, price)
            result["index"] = idx
            results.append(result)

            if result["is_valid"]:
                valid_count += 1
            else:
                invalid_count += 1
                if result["severity"] == "CRITICAL":
                    critical_count += 1
                    # Calculate RPS at risk
                    base_rps = result["expected_rps"]
                    loss_pct = int(result["expected_rps_loss"].rstrip("%"))
                    total_rps_at_risk += int(base_rps * loss_pct / 100)
                elif result["severity"] == "HIGH":
                    high_count += 1
                    base_rps = result["expected_rps"]
                    loss_pct = int(result["expected_rps_loss"].rstrip("%"))
                    total_rps_at_risk += int(base_rps * loss_pct / 100)

        except ValidationError as e:
            results.append({
                "index": idx,
                "is_valid": False,
                "error": str(e),
                "severity": "ERROR",
            })
            invalid_count += 1

    summary = {
        "total": len(items),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "valid_percentage": round((valid_count / len(items)) * 100, 1) if items else 0,
    }

    logger.info(
        f"Batch validation complete: {valid_count}/{len(items)} valid, "
        f"{critical_count} critical mismatches, {total_rps_at_risk} RPS at risk",
        extra=summary,
    )

    return {
        "results": results,
        "summary": summary,
        "critical_count": critical_count,
        "high_count": high_count,
        "total_rps_at_risk": total_rps_at_risk,
    }


# =============================================================================
# Export Public API
# =============================================================================

__all__ = [
    # Configuration
    "PRICE_LENGTH_MATRIX",
    "MISMATCH_PENALTIES",
    "SORTED_PRICES",
    # Data classes
    "PriceValidationResult",
    # Main validation functions
    "validate_price_length_match",
    "get_optimal_price_for_length",
    "calculate_rps_impact",
    "validate_batch",
    # Internal (exported for testing)
    "_suggest_alternative_prices",
]
