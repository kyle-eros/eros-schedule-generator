"""
Confidence-adjusted multipliers for volume calculation.

Dampens aggressive adjustments for creators with limited performance data,
preventing volatile recommendations when confidence is low.

The problem: A creator with 20 messages gets the same aggressive multipliers
as one with 2,000 messages, leading to volatile recommendations for
new/low-activity creators.

The solution: Dampen multipliers toward neutral (1.0) based on message count
confidence, ensuring stable recommendations until sufficient data exists.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, TypedDict, TypeVar, Union

from python.logging_config import get_logger

# TypeVar for generic dictionary key types in dampen_multiplier_dict
K = TypeVar("K", int, str)

logger = get_logger(__name__)


# Message count thresholds for confidence scoring
# (min_messages, max_messages, confidence)
# Higher message counts indicate more reliable performance data
CONFIDENCE_TIERS: list[Tuple[int, Optional[int], float]] = [
    (200, None, 1.0),    # Full confidence - aggressive multipliers allowed
    (100, 199, 0.8),     # High confidence - slight dampening
    (50, 99, 0.6),       # Medium confidence - moderate dampening
    (20, 49, 0.4),       # Low confidence - significant dampening
    (0, 19, 0.2),        # Very low confidence - mostly neutral multipliers
]

# Neutral multiplier (target for dampening)
# All multipliers are pulled toward this value based on confidence
NEUTRAL_MULTIPLIER: float = 1.0


class ConfidenceAdjustments(TypedDict):
    """Adjustments based on confidence level for volume, freshness, and followups.

    Provides tier-specific parameters that align revenue allocation, caption
    freshness thresholds, and followup send multipliers based on confidence
    level. Used by the volume optimization pipeline to adjust behavior when
    data reliability is uncertain.

    Attributes:
        volume_mult: Multiplier for volume (0.7-1.0). Applied to base tier
            volumes to scale sends based on confidence.
        freshness_days: Caption freshness threshold in days (15-30). Lower
            confidence uses stricter (shorter) freshness windows.
        followup_mult: Multiplier for followup sends (0.3-1.0). Reduces
            followup aggressiveness when confidence is low.
        tier: Tier name ("full", "standard", "minimum", "conservative").
            Human-readable label for the confidence tier.
    """

    volume_mult: float
    freshness_days: int
    followup_mult: float
    tier: str


@dataclass
class ConfidenceResult:
    """Result of confidence calculation.

    Attributes:
        confidence: Confidence score (0.0-1.0). Higher means more reliable data.
        message_count: Number of messages analyzed.
        tier_name: Human-readable confidence tier name.
        dampen_factor: How much to dampen multipliers (1 - confidence).
    """
    confidence: float
    message_count: int
    tier_name: str
    dampen_factor: float  # 1 - confidence

    @property
    def is_low_confidence(self) -> bool:
        """Returns True if confidence is below 0.6 (medium threshold).

        Low confidence indicates multipliers should be significantly
        dampened toward neutral to avoid volatile recommendations.
        """
        return self.confidence < 0.6


def calculate_confidence(message_count: int) -> ConfidenceResult:
    """Calculate confidence score based on message count.

    Higher message counts indicate more reliable performance data
    and allow more aggressive volume adjustments. Lower counts
    require dampening to prevent volatile recommendations.

    Args:
        message_count: Number of messages in analysis period.

    Returns:
        ConfidenceResult with confidence score and metadata.

    Examples:
        >>> result = calculate_confidence(250)
        >>> result.confidence
        1.0
        >>> result.tier_name
        'full'

        >>> result = calculate_confidence(15)
        >>> result.confidence
        0.2
        >>> result.is_low_confidence
        True
    """
    if message_count < 0:
        message_count = 0

    confidence = 0.2  # Default to minimum
    tier_name = "very_low"

    for min_msgs, max_msgs, conf in CONFIDENCE_TIERS:
        if max_msgs is None:
            # Unbounded upper tier (200+)
            if message_count >= min_msgs:
                confidence = conf
                tier_name = "full" if conf >= 1.0 else "high"
                break
        elif min_msgs <= message_count <= max_msgs:
            confidence = conf
            if conf >= 0.8:
                tier_name = "high"
            elif conf >= 0.6:
                tier_name = "medium"
            elif conf >= 0.4:
                tier_name = "low"
            else:
                tier_name = "very_low"
            break

    return ConfidenceResult(
        confidence=confidence,
        message_count=message_count,
        tier_name=tier_name,
        dampen_factor=1.0 - confidence,
    )


def get_confidence_adjustments(confidence: float) -> ConfidenceAdjustments:
    """Get volume, freshness, and followup multipliers for confidence level.

    Returns tier-specific adjustments that align revenue allocation, caption
    freshness thresholds, and followup send behavior based on confidence score.
    Uses exclusive upper bounds to avoid boundary gaps between tiers.

    Tier Definitions (from Gap 10.15 reference table):
        - full (0.8-1.0): Full tier volume, 30-day freshness, 100% followups
        - standard (0.6-0.79): Standard volume, 30-day freshness, 80% followups
        - minimum (0.4-0.59): Tier minimum volume, 20-day freshness, 50% followups
        - conservative (<0.4): Conservative -30%, 15-day freshness, 30% followups

    Args:
        confidence: Confidence score between 0.0 and 1.0. Typically calculated
            from message count via calculate_confidence().

    Returns:
        ConfidenceAdjustments TypedDict with:
            - volume_mult: Volume multiplier (0.7-1.0)
            - freshness_days: Caption freshness threshold (15-30 days)
            - followup_mult: Followup sends multiplier (0.3-1.0)
            - tier: Tier name string

    Raises:
        TypeError: If confidence is not a numeric type (int or float).
        ValueError: If confidence is outside the valid 0-1 range.

    Examples:
        >>> get_confidence_adjustments(0.9)
        {'volume_mult': 1.0, 'freshness_days': 30, 'followup_mult': 1.0, 'tier': 'full'}

        >>> get_confidence_adjustments(0.65)
        {'volume_mult': 1.0, 'freshness_days': 30, 'followup_mult': 0.8, 'tier': 'standard'}

        >>> get_confidence_adjustments(0.45)
        {'volume_mult': 0.85, 'freshness_days': 20, 'followup_mult': 0.5, 'tier': 'minimum'}

        >>> get_confidence_adjustments(0.3)
        {'volume_mult': 0.7, 'freshness_days': 15, 'followup_mult': 0.3, 'tier': 'conservative'}
    """
    if not isinstance(confidence, (int, float)):
        raise TypeError(f"Expected numeric, got {type(confidence).__name__}")

    if confidence < 0 or confidence > 1:
        raise ValueError(f"Confidence must be 0-1, got {confidence}")

    # Use >= for lower bounds to avoid boundary gaps
    # Each tier has DISTINCT values to differentiate behavior
    if confidence >= 0.8:  # 0.8-1.0: Full tier volume (most aggressive)
        return ConfidenceAdjustments(
            volume_mult=1.0,
            freshness_days=30,
            followup_mult=1.0,
            tier="full",
        )
    elif confidence >= 0.6:  # 0.6-0.799: Standard volume (slight followup reduction)
        return ConfidenceAdjustments(
            volume_mult=1.0,
            freshness_days=30,
            followup_mult=0.8,
            tier="standard",
        )
    elif confidence >= 0.4:  # 0.4-0.599: Tier minimum (moderate reductions)
        return ConfidenceAdjustments(
            volume_mult=0.85,
            freshness_days=20,
            followup_mult=0.5,
            tier="minimum",
        )
    else:  # 0.0-0.399: Conservative -30% (most conservative)
        return ConfidenceAdjustments(
            volume_mult=0.7,
            freshness_days=15,
            followup_mult=0.3,
            tier="conservative",
        )


def dampen_multiplier(
    multiplier: float,
    confidence: float,
    neutral: float = NEUTRAL_MULTIPLIER,
) -> float:
    """Dampen a multiplier toward neutral based on confidence.

    Uses linear interpolation to pull the multiplier toward the neutral
    value. At confidence=1.0, returns the original multiplier unchanged.
    At confidence=0.0, returns the neutral value.

    Formula: result = neutral + (multiplier - neutral) * confidence

    This ensures:
    - High confidence creators get full multiplier effect
    - Low confidence creators get dampened (safer) multipliers
    - Very low confidence creators stay near neutral

    Args:
        multiplier: Original multiplier value (e.g., 0.7 for saturation).
        confidence: Confidence score (0.0-1.0).
        neutral: Target neutral value (default 1.0).

    Returns:
        Dampened multiplier value.

    Examples:
        >>> dampen_multiplier(0.7, 1.0)  # Full confidence
        0.7
        >>> dampen_multiplier(0.7, 0.5)  # Half confidence
        0.85
        >>> dampen_multiplier(0.7, 0.0)  # No confidence
        1.0
        >>> dampen_multiplier(1.2, 0.3)  # Low confidence, boost multiplier
        1.06
    """
    if confidence >= 1.0:
        return multiplier
    if confidence <= 0.0:
        return neutral

    # Linear interpolation toward neutral
    dampened = neutral + (multiplier - neutral) * confidence

    logger.debug(
        "Dampened multiplier",
        extra={
            "original": multiplier,
            "confidence": confidence,
            "dampened": dampened,
        }
    )

    return dampened


def apply_confidence_to_multipliers(
    saturation_multiplier: float,
    opportunity_multiplier: float,
    message_count: int,
) -> Tuple[float, float, ConfidenceResult]:
    """Apply confidence dampening to both multipliers.

    Convenience function that calculates confidence and applies
    dampening to both saturation and opportunity multipliers in one call.

    Args:
        saturation_multiplier: Original saturation multiplier (0.7-1.0).
        opportunity_multiplier: Original opportunity multiplier (1.0-1.2).
        message_count: Number of messages for confidence calculation.

    Returns:
        Tuple of (dampened_sat_mult, dampened_opp_mult, confidence_result).

    Example:
        >>> sat, opp, conf = apply_confidence_to_multipliers(0.7, 1.2, 150)
        >>> conf.tier_name
        'high'
        >>> sat  # Dampened from 0.7 toward 1.0
        0.76
        >>> opp  # Dampened from 1.2 toward 1.0
        1.16
    """
    confidence = calculate_confidence(message_count)

    dampened_sat = dampen_multiplier(
        saturation_multiplier,
        confidence.confidence,
    )
    dampened_opp = dampen_multiplier(
        opportunity_multiplier,
        confidence.confidence,
    )

    if confidence.is_low_confidence:
        logger.info(
            "Low confidence dampening applied",
            extra={
                "message_count": message_count,
                "confidence": confidence.confidence,
                "tier_name": confidence.tier_name,
                "sat_mult_original": saturation_multiplier,
                "sat_mult_dampened": dampened_sat,
                "opp_mult_original": opportunity_multiplier,
                "opp_mult_dampened": dampened_opp,
            }
        )

    return dampened_sat, dampened_opp, confidence


def dampen_multiplier_dict(
    multipliers: dict[K, float],
    confidence: float,
    neutral: float = NEUTRAL_MULTIPLIER,
) -> dict[K, float]:
    """Dampen a dictionary of multipliers toward neutral based on confidence.

    Useful for dampening day-of-week multipliers, content-type multipliers,
    or any other collection of multipliers that should be adjusted based
    on data confidence.

    Args:
        multipliers: Dict mapping keys (int or str) to multiplier values.
        confidence: Confidence score (0.0-1.0).
        neutral: Target neutral value (default 1.0).

    Returns:
        New dict with dampened multiplier values.

    Examples:
        >>> dow_mults = {0: 0.8, 1: 1.0, 2: 1.2, 3: 1.0, 4: 1.1, 5: 1.2, 6: 1.1}
        >>> dampened = dampen_multiplier_dict(dow_mults, 0.5)
        >>> dampened[0]  # 0.8 -> 0.9 (halfway to 1.0)
        0.9
        >>> dampened[2]  # 1.2 -> 1.1 (halfway to 1.0)
        1.1

        >>> content_mults = {"ppv_unlock": 1.2, "bump_normal": 0.8}
        >>> dampened = dampen_multiplier_dict(content_mults, 0.4)
        >>> dampened["ppv_unlock"]  # Dampened toward 1.0
        1.08
    """
    return {
        key: dampen_multiplier(mult, confidence, neutral)
        for key, mult in multipliers.items()
    }


def apply_confidence_to_dow_multipliers(
    dow_multipliers: Dict[int, float],
    message_count: int,
) -> Tuple[Dict[int, float], ConfidenceResult]:
    """Apply confidence dampening to day-of-week multipliers.

    Convenience function that calculates confidence from message count
    and applies dampening to all 7 day-of-week multipliers.

    Args:
        dow_multipliers: Dict mapping day index (0-6) to multiplier.
        message_count: Number of messages for confidence calculation.

    Returns:
        Tuple of (dampened_dow_multipliers, confidence_result).

    Example:
        >>> dow_mults = {0: 0.8, 1: 0.9, 2: 1.0, 3: 1.0, 4: 1.1, 5: 1.2, 6: 1.15}
        >>> dampened, conf = apply_confidence_to_dow_multipliers(dow_mults, 75)
        >>> conf.tier_name
        'medium'
        >>> dampened[0]  # 0.8 dampened at 0.6 confidence
        0.88
        >>> dampened[5]  # 1.2 dampened at 0.6 confidence
        1.12
    """
    confidence = calculate_confidence(message_count)

    dampened = dampen_multiplier_dict(
        dow_multipliers,
        confidence.confidence,
    )

    if confidence.is_low_confidence:
        logger.info(
            "Low confidence dampening applied to DOW multipliers",
            extra={
                "message_count": message_count,
                "confidence": confidence.confidence,
                "tier_name": confidence.tier_name,
                "original_multipliers": dow_multipliers,
                "dampened_multipliers": dampened,
            }
        )

    return dampened, confidence


def apply_confidence_to_content_multipliers(
    content_multipliers: Dict[str, float],
    message_count: int,
) -> Tuple[Dict[str, float], ConfidenceResult]:
    """Apply confidence dampening to content-type multipliers.

    Convenience function that calculates confidence from message count
    and applies dampening to content-type based multipliers (e.g., from
    content_weighting.py RANK_MULTIPLIERS).

    Args:
        content_multipliers: Dict mapping send_type_key to multiplier.
        message_count: Number of messages for confidence calculation.

    Returns:
        Tuple of (dampened_content_multipliers, confidence_result).

    Example:
        >>> content_mults = {"ppv_unlock": 1.2, "bump_normal": 0.9, "link_drop": 0.7}
        >>> dampened, conf = apply_confidence_to_content_multipliers(content_mults, 30)
        >>> conf.tier_name
        'low'
        >>> dampened["ppv_unlock"]  # Dampened toward 1.0 at 0.4 confidence
        1.08
        >>> dampened["link_drop"]  # Dampened toward 1.0 at 0.4 confidence
        0.88
    """
    confidence = calculate_confidence(message_count)

    dampened = dampen_multiplier_dict(
        content_multipliers,
        confidence.confidence,
    )

    if confidence.is_low_confidence:
        logger.info(
            "Low confidence dampening applied to content-type multipliers",
            extra={
                "message_count": message_count,
                "confidence": confidence.confidence,
                "tier_name": confidence.tier_name,
                "send_types_dampened": list(content_multipliers.keys()),
            }
        )

    return dampened, confidence


@dataclass
class ConfidenceAdjustedVolume:
    """Volume calculation with confidence adjustment applied.

    Contains final volume values along with metadata about the
    confidence adjustment that was applied.

    Attributes:
        revenue_per_day: Final revenue sends per day after adjustment.
        engagement_per_day: Final engagement sends per day after adjustment.
        retention_per_day: Final retention sends per day after adjustment.
        confidence: ConfidenceResult with confidence metadata.
        original_multipliers: Original (saturation_mult, opportunity_mult) tuple.
        adjusted_multipliers: Dampened multipliers after confidence adjustment.
        adjustment_applied: Whether any dampening was applied (confidence < 1.0).
    """
    revenue_per_day: int
    engagement_per_day: int
    retention_per_day: int
    confidence: ConfidenceResult
    original_multipliers: Tuple[float, float]
    adjusted_multipliers: Tuple[float, float]
    adjustment_applied: bool

    @property
    def total_per_day(self) -> int:
        """Total sends per day across all categories."""
        return self.revenue_per_day + self.engagement_per_day + self.retention_per_day


def calculate_confidence_adjusted_volume(
    base_revenue: int,
    base_engagement: int,
    base_retention: int,
    saturation_multiplier: float,
    opportunity_multiplier: float,
    message_count: int,
    page_type: str,
    revenue_bounds: Tuple[int, int] = (1, 8),
    engagement_bounds: Tuple[int, int] = (1, 6),
    retention_bounds: Tuple[int, int] = (0, 4),
) -> ConfidenceAdjustedVolume:
    """Calculate volume with confidence-adjusted multipliers.

    Full calculation pipeline that:
    1. Calculates confidence from message count
    2. Dampens multipliers based on confidence
    3. Applies multipliers to base volumes
    4. Enforces bounds

    This prevents volatile volume recommendations for creators with
    limited performance data by dampening aggressive multipliers.

    Args:
        base_revenue: Base revenue sends from tier configuration.
        base_engagement: Base engagement sends from tier configuration.
        base_retention: Base retention sends from tier configuration.
        saturation_multiplier: Original saturation multiplier (0.7-1.0).
        opportunity_multiplier: Original opportunity multiplier (1.0-1.2).
        message_count: Messages for confidence calculation.
        page_type: 'paid' or 'free' (affects retention).
        revenue_bounds: (min, max) bounds for revenue sends.
        engagement_bounds: (min, max) bounds for engagement sends.
        retention_bounds: (min, max) bounds for retention sends.

    Returns:
        ConfidenceAdjustedVolume with final values and metadata.

    Example:
        >>> result = calculate_confidence_adjusted_volume(
        ...     base_revenue=5,
        ...     base_engagement=4,
        ...     base_retention=2,
        ...     saturation_multiplier=0.7,
        ...     opportunity_multiplier=1.0,
        ...     message_count=30,  # Low confidence
        ...     page_type="paid",
        ... )
        >>> result.adjustment_applied
        True
        >>> result.confidence.tier_name
        'low'
    """
    # Apply confidence dampening
    adj_sat, adj_opp, confidence = apply_confidence_to_multipliers(
        saturation_multiplier,
        opportunity_multiplier,
        message_count,
    )

    # Combined multiplier for revenue and engagement
    combined_mult = adj_sat * adj_opp

    # Calculate adjusted volumes
    revenue_raw = round(base_revenue * combined_mult)
    engagement_raw = round(base_engagement * combined_mult)

    # Retention only applies saturation (not opportunity)
    # Free pages get 0 retention regardless
    if page_type == "free":
        retention_raw = 0
    else:
        retention_raw = round(base_retention * adj_sat)

    # Apply bounds (clamp to min/max)
    def clamp(val: int, bounds: Tuple[int, int]) -> int:
        return max(bounds[0], min(bounds[1], val))

    return ConfidenceAdjustedVolume(
        revenue_per_day=clamp(revenue_raw, revenue_bounds),
        engagement_per_day=clamp(engagement_raw, engagement_bounds),
        retention_per_day=clamp(retention_raw, retention_bounds),
        confidence=confidence,
        original_multipliers=(saturation_multiplier, opportunity_multiplier),
        adjusted_multipliers=(adj_sat, adj_opp),
        adjustment_applied=confidence.confidence < 1.0,
    )


__all__ = [
    # Type definitions
    "ConfidenceAdjustments",
    # Data classes
    "ConfidenceResult",
    "ConfidenceAdjustedVolume",
    # Core functions
    "calculate_confidence",
    "get_confidence_adjustments",
    "dampen_multiplier",
    "dampen_multiplier_dict",
    # Application functions for different multiplier types
    "apply_confidence_to_multipliers",
    "apply_confidence_to_dow_multipliers",
    "apply_confidence_to_content_multipliers",
    # Full volume calculation
    "calculate_confidence_adjusted_volume",
    # Constants
    "CONFIDENCE_TIERS",
    "NEUTRAL_MULTIPLIER",
]
