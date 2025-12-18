"""
Data-driven volume triggers through trait detection.

Implements statistical analysis to detect shared traits among top performers
and generate volume increase recommendations. Based on the rule:
"If 60%+ of top 10 share a trait -> increase that type by 20-30%"

This module uses hypothesis testing to ensure recommendations are
statistically significant, not just coincidental patterns.

Usage:
    from python.analytics.trait_detector import (
        analyze_top_performer_traits,
        apply_volume_increases,
    )

    # Analyze performance data
    result = analyze_top_performer_traits(
        performance_data=performance_records,
        top_n=10,
        min_sample_for_confidence=50,
        alpha=0.05,
    )

    # Check for recommendations
    if result['has_recommendations']:
        for rec in result['recommendations']:
            print(f"{rec['trait']}: +{(rec['multiplier']-1)*100:.0f}%")

    # Apply to allocation
    adjusted = apply_volume_increases(allocation, result['recommendations'])

Statistical Methods:
    - Chi-square test (when all expected counts >= 5)
    - Fisher's exact test (for small samples)
    - Bonferroni correction (alpha / num_traits_tested)
"""

import warnings
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import numpy as np
from scipy import stats

from python.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default number of top performers to analyze
DEFAULT_TOP_N: int = 10

# Threshold: 60% of top performers must share a trait
DEFAULT_THRESHOLD_PERCENT: float = 0.60

# Minimum total sample size for statistical confidence
MIN_SAMPLE_FOR_CONFIDENCE: int = 50

# Default significance level
DEFAULT_ALPHA: float = 0.05

# Optimal caption length range (sweet spot based on performance data)
OPTIMAL_LENGTH_MIN: int = 250
OPTIMAL_LENGTH_MAX: int = 449

# Volume increase range for significant traits
MULTIPLIER_MIN: float = 1.20  # +20%
MULTIPLIER_MAX: float = 1.30  # +30%


# =============================================================================
# Type Definitions
# =============================================================================


class SharedTraitInfo(TypedDict, total=False):
    """Information about a shared trait detected in top performers.

    Attributes:
        count: Number of top performers with this trait.
        percentage: Proportion of top performers with trait (0.0-1.0).
        p_value: P-value from statistical test.
        is_significant: Whether the trait passes significance test.
        recommendation: Human-readable recommendation string.
        type: For categorical traits, the specific value (e.g., 'ppv_unlock').
        tone: For tone traits, the specific tone value.
        price: For price traits, the specific price point.
    """

    count: int
    percentage: float
    p_value: float
    is_significant: bool
    recommendation: str
    type: str
    tone: str
    price: float


class TraitRecommendation(TypedDict):
    """A recommendation to adjust volume based on detected trait.

    Attributes:
        trait: Name of the trait (e.g., 'optimal_length', 'content_type').
        action: Action to take ('increase_weight').
        multiplier: Volume multiplier to apply (1.20-1.30).
        p_value: Statistical p-value supporting this recommendation.
        trait_value: Specific value for categorical traits (optional).
    """

    trait: str
    action: str
    multiplier: float
    p_value: float
    trait_value: Optional[str]


class TraitAnalysisResult(TypedDict):
    """Complete result of trait analysis.

    Attributes:
        has_recommendations: Whether any significant traits were found.
        shared_traits: Dict of trait name to SharedTraitInfo.
        recommendations: List of TraitRecommendation for significant traits.
        analyzed_count: Number of top performers analyzed.
        statistical_confidence: 'HIGH' if sample >= min threshold, else 'LOW'.
        bonferroni_alpha: Adjusted significance level after Bonferroni correction.
        warning: Optional warning message for low sample sizes.
    """

    has_recommendations: bool
    shared_traits: Dict[str, SharedTraitInfo]
    recommendations: List[TraitRecommendation]
    analyzed_count: int
    statistical_confidence: str
    bonferroni_alpha: float
    warning: Optional[str]


# =============================================================================
# Statistical Testing Functions
# =============================================================================


def chi_square_test(
    top_count: int,
    top_total: int,
    non_top_count: int,
    non_top_total: int,
) -> Tuple[float, str]:
    """Perform chi-square or Fisher's exact test for trait comparison.

    Compares the proportion of a trait in top performers vs non-top performers
    to determine if the difference is statistically significant.

    Uses Fisher's exact test when any expected cell count is < 5,
    otherwise uses chi-square test for computational efficiency.

    Args:
        top_count: Number of top performers with the trait.
        top_total: Total number of top performers.
        non_top_count: Number of non-top performers with the trait.
        non_top_total: Total number of non-top performers.

    Returns:
        Tuple of (p_value, test_type) where test_type is 'fisher' or 'chi2'.

    Raises:
        ValueError: If any count is negative or totals are zero.

    Examples:
        >>> p_value, test = chi_square_test(8, 10, 30, 90)
        >>> print(f"Test: {test}, p={p_value:.4f}")
        Test: chi2, p=0.0234

        >>> p_value, test = chi_square_test(3, 5, 2, 8)
        >>> print(f"Test: {test}")  # Small sample uses Fisher's
        Test: fisher
    """
    # Validate inputs
    if top_total <= 0 or non_top_total <= 0:
        raise ValueError("Total counts must be positive")
    if top_count < 0 or non_top_count < 0:
        raise ValueError("Counts cannot be negative")
    if top_count > top_total or non_top_count > non_top_total:
        raise ValueError("Counts cannot exceed totals")

    # Build 2x2 contingency table
    # Rows: [top performers, non-top performers]
    # Cols: [has trait, does not have trait]
    observed = np.array([
        [top_count, top_total - top_count],
        [non_top_count, non_top_total - non_top_count]
    ])

    # Check if any cell is too small for chi-square
    # Rule of thumb: chi-square unreliable if expected count < 5 in any cell
    row_totals = observed.sum(axis=1)
    col_totals = observed.sum(axis=0)
    total = observed.sum()

    if total == 0:
        return 1.0, "none"

    # Calculate expected values
    expected = np.outer(row_totals, col_totals) / total

    if expected.min() < 5:
        # Use Fisher's exact test for small samples
        _, p_value = stats.fisher_exact(observed)
        test_type = "fisher"
    else:
        # Use chi-square test for larger samples
        chi2, p_value, dof, expected_freq = stats.chi2_contingency(observed)
        test_type = "chi2"

    logger.debug(
        "Statistical test performed",
        extra={
            "test_type": test_type,
            "p_value": p_value,
            "observed": observed.tolist(),
            "top_percentage": top_count / top_total if top_total > 0 else 0,
            "non_top_percentage": (
                non_top_count / non_top_total if non_top_total > 0 else 0
            ),
        }
    )

    return p_value, test_type


def is_optimal_length(text: str) -> bool:
    """Check if caption text is within optimal length range.

    The optimal length range (250-449 characters) was determined from
    performance analysis showing highest earnings in this range.

    Args:
        text: Caption text to measure.

    Returns:
        True if text length is within optimal range (250-449 chars).

    Examples:
        >>> is_optimal_length("Short caption")  # 13 chars
        False
        >>> is_optimal_length("A" * 300)  # 300 chars
        True
        >>> is_optimal_length("A" * 500)  # 500 chars
        False
    """
    if not text:
        return False
    length = len(text)
    return OPTIMAL_LENGTH_MIN <= length <= OPTIMAL_LENGTH_MAX


def _calculate_multiplier(percentage: float) -> float:
    """Calculate volume multiplier based on trait prevalence.

    Higher prevalence among top performers yields higher multiplier,
    scaled linearly between MULTIPLIER_MIN and MULTIPLIER_MAX.

    Args:
        percentage: Proportion of top performers with trait (0.6-1.0).

    Returns:
        Multiplier between 1.20 and 1.30.

    Examples:
        >>> _calculate_multiplier(0.60)  # 60% = +20%
        1.2
        >>> _calculate_multiplier(1.0)   # 100% = +30%
        1.3
        >>> _calculate_multiplier(0.80)  # 80% = +25%
        1.25
    """
    # Scale from 60% (1.20) to 100% (1.30)
    # percentage: 0.6 -> 1.0 maps to multiplier: 1.20 -> 1.30
    if percentage <= DEFAULT_THRESHOLD_PERCENT:
        return MULTIPLIER_MIN

    # Linear interpolation
    scale = (percentage - DEFAULT_THRESHOLD_PERCENT) / (1.0 - DEFAULT_THRESHOLD_PERCENT)
    return MULTIPLIER_MIN + scale * (MULTIPLIER_MAX - MULTIPLIER_MIN)


def _get_most_common(items: List[Any]) -> Tuple[Any, int]:
    """Get the most common item and its count.

    Args:
        items: List of items to count.

    Returns:
        Tuple of (most_common_item, count). Returns (None, 0) if list is empty.
    """
    if not items:
        return None, 0

    counter = Counter(items)
    most_common = counter.most_common(1)
    if most_common:
        return most_common[0]
    return None, 0


# =============================================================================
# Main Analysis Function
# =============================================================================


def analyze_top_performer_traits(
    performance_data: List[Dict[str, Any]],
    top_n: int = DEFAULT_TOP_N,
    min_sample_for_confidence: int = MIN_SAMPLE_FOR_CONFIDENCE,
    alpha: float = DEFAULT_ALPHA,
) -> TraitAnalysisResult:
    """Analyze shared traits among top performers.

    Identifies traits that are significantly more prevalent in top performers
    compared to the rest of the population. Uses statistical testing with
    Bonferroni correction to control for multiple comparisons.

    Rule: "If 60%+ of top 10 share a trait -> increase that type by 20-30%"

    Args:
        performance_data: List of performance records, each containing:
            - earnings (float): Revenue generated (required for sorting)
            - caption_text (str): Caption text for length analysis
            - content_type (str): Content type classification
            - detected_tone (str): Tone/style classification
            - price (float): Price point
        top_n: Number of top performers to analyze (default 10).
        min_sample_for_confidence: Minimum total sample size for HIGH
            confidence classification (default 50).
        alpha: Base significance level before Bonferroni correction (default 0.05).

    Returns:
        TraitAnalysisResult containing:
            - has_recommendations: True if any significant traits found
            - shared_traits: Dict of trait analysis results
            - recommendations: List of actionable recommendations
            - analyzed_count: Actual number of top performers analyzed
            - statistical_confidence: 'HIGH' or 'LOW'
            - bonferroni_alpha: Adjusted significance level
            - warning: Optional warning message

    Raises:
        ValueError: If performance_data is not a list.

    Examples:
        >>> data = [
        ...     {'earnings': 100, 'content_type': 'lingerie', 'detected_tone': 'playful', 'price': 10, 'caption_text': 'A' * 300},
        ...     {'earnings': 90, 'content_type': 'lingerie', 'detected_tone': 'playful', 'price': 10, 'caption_text': 'B' * 350},
        ...     # ... more records
        ... ]
        >>> result = analyze_top_performer_traits(data, top_n=10)
        >>> if result['has_recommendations']:
        ...     print(f"Found {len(result['recommendations'])} recommendations")
    """
    if not isinstance(performance_data, list):
        raise ValueError("performance_data must be a list")

    # Initialize result structure
    result: TraitAnalysisResult = {
        "has_recommendations": False,
        "shared_traits": {},
        "recommendations": [],
        "analyzed_count": 0,
        "statistical_confidence": "LOW",
        "bonferroni_alpha": alpha,
        "warning": None,
    }

    # Handle empty or insufficient data
    total_records = len(performance_data)
    if total_records == 0:
        result["warning"] = "No performance data provided"
        logger.warning("Trait analysis skipped: no performance data")
        return result

    if total_records < top_n:
        result["warning"] = (
            f"Insufficient data: {total_records} records, need at least {top_n}"
        )
        logger.warning(
            "Trait analysis with reduced sample",
            extra={"total_records": total_records, "requested_top_n": top_n}
        )
        top_n = total_records

    # Check statistical confidence
    if total_records < min_sample_for_confidence:
        result["statistical_confidence"] = "LOW"
        warnings.warn(
            f"Low sample size ({total_records} < {min_sample_for_confidence}): "
            "results may not be statistically reliable",
            UserWarning,
            stacklevel=2,
        )
        logger.warning(
            "Low sample size for trait analysis",
            extra={
                "total_records": total_records,
                "min_for_confidence": min_sample_for_confidence,
            }
        )
    else:
        result["statistical_confidence"] = "HIGH"

    # Sort by earnings (descending) and split into top/non-top
    sorted_data = sorted(
        performance_data,
        key=lambda x: x.get("earnings", 0) or 0,
        reverse=True,
    )

    top_performers = sorted_data[:top_n]
    non_top_performers = sorted_data[top_n:]

    result["analyzed_count"] = len(top_performers)
    non_top_count = len(non_top_performers)

    # Cannot do comparison if no non-top performers
    if non_top_count == 0:
        result["warning"] = "No comparison group available (all records are top performers)"
        logger.warning("Trait analysis: no non-top performers for comparison")
        return result

    # Number of traits we're testing (for Bonferroni correction)
    num_traits_tested = 4  # optimal_length, content_type, tone, price
    bonferroni_alpha = alpha / num_traits_tested
    result["bonferroni_alpha"] = bonferroni_alpha

    logger.info(
        "Starting trait analysis",
        extra={
            "total_records": total_records,
            "top_n": top_n,
            "non_top_count": non_top_count,
            "bonferroni_alpha": bonferroni_alpha,
        }
    )

    # =================================================================
    # Trait 1: Optimal Length (250-449 characters)
    # =================================================================
    top_optimal_length = sum(
        1 for r in top_performers
        if is_optimal_length(r.get("caption_text", ""))
    )
    non_top_optimal_length = sum(
        1 for r in non_top_performers
        if is_optimal_length(r.get("caption_text", ""))
    )

    top_len_pct = top_optimal_length / top_n if top_n > 0 else 0
    p_value_len, test_type_len = chi_square_test(
        top_optimal_length, top_n,
        non_top_optimal_length, non_top_count,
    )

    is_significant_len = (
        top_len_pct >= DEFAULT_THRESHOLD_PERCENT and
        p_value_len < bonferroni_alpha
    )

    result["shared_traits"]["optimal_length"] = SharedTraitInfo(
        count=top_optimal_length,
        percentage=top_len_pct,
        p_value=p_value_len,
        is_significant=is_significant_len,
        recommendation=(
            f"Increase descriptive captions (250-449 chars) by "
            f"{int((_calculate_multiplier(top_len_pct) - 1) * 100)}%"
            if is_significant_len else ""
        ),
    )

    if is_significant_len:
        result["recommendations"].append(TraitRecommendation(
            trait="optimal_length",
            action="increase_weight",
            multiplier=_calculate_multiplier(top_len_pct),
            p_value=p_value_len,
            trait_value=f"{OPTIMAL_LENGTH_MIN}-{OPTIMAL_LENGTH_MAX}",
        ))

    # =================================================================
    # Trait 2: Dominant Content Type
    # =================================================================
    top_content_types = [
        r.get("content_type") for r in top_performers
        if r.get("content_type")
    ]
    dominant_type, type_count = _get_most_common(top_content_types)

    if dominant_type and top_n > 0:
        type_pct = type_count / top_n
        non_top_type_count = sum(
            1 for r in non_top_performers
            if r.get("content_type") == dominant_type
        )

        p_value_type, test_type_type = chi_square_test(
            type_count, top_n,
            non_top_type_count, non_top_count,
        )

        is_significant_type = (
            type_pct >= DEFAULT_THRESHOLD_PERCENT and
            p_value_type < bonferroni_alpha
        )

        result["shared_traits"]["dominant_content_type"] = SharedTraitInfo(
            type=dominant_type,
            count=type_count,
            percentage=type_pct,
            p_value=p_value_type,
            is_significant=is_significant_type,
            recommendation=(
                f"Increase '{dominant_type}' content by "
                f"{int((_calculate_multiplier(type_pct) - 1) * 100)}%"
                if is_significant_type else ""
            ),
        )

        if is_significant_type:
            result["recommendations"].append(TraitRecommendation(
                trait="content_type",
                action="increase_weight",
                multiplier=_calculate_multiplier(type_pct),
                p_value=p_value_type,
                trait_value=dominant_type,
            ))

    # =================================================================
    # Trait 3: Dominant Tone/Style
    # =================================================================
    top_tones = [
        r.get("detected_tone") for r in top_performers
        if r.get("detected_tone")
    ]
    dominant_tone, tone_count = _get_most_common(top_tones)

    if dominant_tone and top_n > 0:
        tone_pct = tone_count / top_n
        non_top_tone_count = sum(
            1 for r in non_top_performers
            if r.get("detected_tone") == dominant_tone
        )

        p_value_tone, test_type_tone = chi_square_test(
            tone_count, top_n,
            non_top_tone_count, non_top_count,
        )

        is_significant_tone = (
            tone_pct >= DEFAULT_THRESHOLD_PERCENT and
            p_value_tone < bonferroni_alpha
        )

        result["shared_traits"]["dominant_tone"] = SharedTraitInfo(
            tone=dominant_tone,
            count=tone_count,
            percentage=tone_pct,
            p_value=p_value_tone,
            is_significant=is_significant_tone,
            recommendation=(
                f"Increase '{dominant_tone}' tone captions by "
                f"{int((_calculate_multiplier(tone_pct) - 1) * 100)}%"
                if is_significant_tone else ""
            ),
        )

        if is_significant_tone:
            result["recommendations"].append(TraitRecommendation(
                trait="tone",
                action="increase_weight",
                multiplier=_calculate_multiplier(tone_pct),
                p_value=p_value_tone,
                trait_value=dominant_tone,
            ))

    # =================================================================
    # Trait 4: Dominant Price Point
    # =================================================================
    top_prices = [
        r.get("price") for r in top_performers
        if r.get("price") is not None
    ]
    dominant_price, price_count = _get_most_common(top_prices)

    if dominant_price is not None and top_n > 0:
        price_pct = price_count / top_n
        non_top_price_count = sum(
            1 for r in non_top_performers
            if r.get("price") == dominant_price
        )

        p_value_price, test_type_price = chi_square_test(
            price_count, top_n,
            non_top_price_count, non_top_count,
        )

        is_significant_price = (
            price_pct >= DEFAULT_THRESHOLD_PERCENT and
            p_value_price < bonferroni_alpha
        )

        result["shared_traits"]["dominant_price"] = SharedTraitInfo(
            price=dominant_price,
            count=price_count,
            percentage=price_pct,
            p_value=p_value_price,
            is_significant=is_significant_price,
            recommendation=(
                f"Increase price point ${dominant_price} usage by "
                f"{int((_calculate_multiplier(price_pct) - 1) * 100)}%"
                if is_significant_price else ""
            ),
        )

        if is_significant_price:
            result["recommendations"].append(TraitRecommendation(
                trait="price",
                action="increase_weight",
                multiplier=_calculate_multiplier(price_pct),
                p_value=p_value_price,
                trait_value=str(dominant_price),
            ))

    # =================================================================
    # Final Summary
    # =================================================================
    result["has_recommendations"] = len(result["recommendations"]) > 0

    logger.info(
        "Trait analysis complete",
        extra={
            "has_recommendations": result["has_recommendations"],
            "recommendation_count": len(result["recommendations"]),
            "significant_traits": [r["trait"] for r in result["recommendations"]],
            "statistical_confidence": result["statistical_confidence"],
        }
    )

    return result


# =============================================================================
# Volume Application Function
# =============================================================================


def apply_volume_increases(
    allocation: Dict[str, float],
    recommendations: List[TraitRecommendation],
) -> Dict[str, float]:
    """Apply trait-based volume increases to allocation.

    Takes current allocation dictionary and applies multipliers from
    recommendations. Handles both general allocations and trait-specific
    keys.

    Args:
        allocation: Current allocation dict with keys like 'descriptive',
            'content_type:lingerie', 'tone:playful', or send type keys.
        recommendations: List of TraitRecommendation from analyze_top_performer_traits.

    Returns:
        New allocation dict with multipliers applied. Original allocation
        is not modified.

    Examples:
        >>> allocation = {
        ...     'ppv_unlock': 5.0,
        ...     'bump_normal': 3.0,
        ...     'descriptive': 4.0,
        ... }
        >>> recommendations = [
        ...     {'trait': 'optimal_length', 'action': 'increase_weight',
        ...      'multiplier': 1.25, 'p_value': 0.01, 'trait_value': '250-449'},
        ... ]
        >>> adjusted = apply_volume_increases(allocation, recommendations)
        >>> adjusted['descriptive']
        5.0  # 4.0 * 1.25
    """
    if not allocation:
        return {}

    if not recommendations:
        return allocation.copy()

    # Create working copy
    adjusted = allocation.copy()

    for rec in recommendations:
        trait = rec.get("trait", "")
        action = rec.get("action", "")
        multiplier = rec.get("multiplier", 1.0)
        trait_value = rec.get("trait_value")

        if action != "increase_weight":
            continue

        # Apply multiplier based on trait type
        if trait == "optimal_length":
            # Apply to descriptive/long caption allocations
            for key in ["descriptive", "long", "detailed"]:
                if key in adjusted:
                    adjusted[key] = adjusted[key] * multiplier

        elif trait == "content_type" and trait_value:
            # Apply to specific content type
            # Check both direct key and prefixed key
            for key in [trait_value, f"content_type:{trait_value}"]:
                if key in adjusted:
                    adjusted[key] = adjusted[key] * multiplier

        elif trait == "tone" and trait_value:
            # Apply to specific tone
            for key in [trait_value, f"tone:{trait_value}"]:
                if key in adjusted:
                    adjusted[key] = adjusted[key] * multiplier

        elif trait == "price" and trait_value:
            # Apply to specific price point
            for key in [f"price:{trait_value}", f"${trait_value}"]:
                if key in adjusted:
                    adjusted[key] = adjusted[key] * multiplier

        logger.debug(
            "Volume adjustment applied",
            extra={
                "trait": trait,
                "trait_value": trait_value,
                "multiplier": multiplier,
            }
        )

    return adjusted


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Type definitions
    "TraitAnalysisResult",
    "TraitRecommendation",
    "SharedTraitInfo",
    # Constants
    "DEFAULT_TOP_N",
    "DEFAULT_THRESHOLD_PERCENT",
    "MIN_SAMPLE_FOR_CONFIDENCE",
    "DEFAULT_ALPHA",
    "OPTIMAL_LENGTH_MIN",
    "OPTIMAL_LENGTH_MAX",
    # Main analysis function
    "analyze_top_performer_traits",
    # Application function
    "apply_volume_increases",
    # Helper functions (exposed for testing)
    "chi_square_test",
    "is_optimal_length",
]
