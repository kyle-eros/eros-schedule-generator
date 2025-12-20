# Confidence Levels Reference

Standardized confidence thresholds for volume optimization predictions across the EROS schedule generator system.

## Purpose

The `confidence_score` (0.0-1.0) indicates prediction reliability based on historical data quality and quantity. All agents use consistent thresholds to adjust behavior when data is limited.

---

## Threshold Definitions

| Level | Range | Meaning | Recommended Action |
|-------|-------|---------|-------------------|
| **VERY_LOW** | 0.0 - 0.39 | Insufficient data | Flag for manual review, use fallback defaults |
| **LOW** | 0.4 - 0.59 | Limited data | Apply conservative adjustments, add warnings |
| **MODERATE** | 0.6 - 0.79 | Good history | Standard allocation, proceed with validation |
| **HIGH** | 0.8 - 1.0 | Strong data | Full optimization applied confidently |

---

## Application Rules

### Volume Calculation
- **VERY_LOW** (<0.4): Use tier-based fallback defaults, flag schedule for review
- **LOW** (0.4-0.59): Apply conservative volume multipliers, reduce elasticity range
- **MODERATE** (0.6-0.79): Standard multi-horizon fusion, normal elasticity bounds
- **HIGH** (>=0.8): Full optimization pipeline, aggressive elasticity exploration

### Allocation Behavior
- **VERY_LOW**: Narrow send type distribution, avoid experimental types
- **LOW**: Conservative type selection, prioritize proven performers
- **MODERATE**: Balanced type variety, standard content weighting
- **HIGH**: Full type diversity, content-aware weighting enabled

### Validation Thresholds
Confidence adjusts validation strictness (lower confidence = more lenient):

| Metric | HIGH (>=0.8) | MODERATE (0.6-0.79) | LOW (0.4-0.59) | VERY_LOW (<0.4) |
|--------|--------------|---------------------|----------------|-----------------|
| Min freshness | 30 days | 25 days | 20 days | 15 days |
| Min performance | 40 | 35 | 30 | 25 |
| Diversity min | 10 types | 9 types | 8 types | 8 types |
| Spacing tolerance | 0 min | 5 min | 10 min | 15 min |
| Caption coverage | 95% | 90% | 85% | 80% |
| Status threshold (APPROVED) | >=85 | >=80 | >=75 | >=70 |
| Status threshold (REJECTED) | <70 | <65 | <60 | <55 |

---

## Agent-Specific Usage

### performance-analyst
```python
if confidence_score < 0.4:
    # VERY LOW: Flag for manual review
    recommendations.append({
        "type": "very_low_confidence_warning",
        "action": "Flag for manual review, use fallback defaults",
        "reason": f"Algorithm confidence is {confidence_score:.0%}",
        "impact": "high"
    })
elif confidence_score < 0.6:
    # LOW: Apply conservative adjustments
    recommendations.append({
        "type": "low_confidence_warning",
        "action": "Apply conservative adjustments, add warnings",
        "reason": f"Algorithm confidence is {confidence_score:.0%}",
        "impact": "medium"
    })
```

**Output**: Includes `confidence_status` field ("very_low" | "low" | "moderate" | "high")

### send-type-allocator
```python
def apply_confidence_adjustments(allocation, confidence_score):
    confidence_metadata = {
        "score": confidence_score,
        "level": get_confidence_level(confidence_score),
        "notes": [],
        "recommendation": None
    }

    if confidence_score < 0.4:
        confidence_metadata["recommendation"] = "fallback_defaults"
    elif confidence_score < 0.6:
        confidence_metadata["recommendation"] = "conservative"
    elif confidence_score < 0.8:
        confidence_metadata["recommendation"] = "standard"
    else:
        confidence_metadata["recommendation"] = "optimized"

    return {**allocation, "confidence_metadata": confidence_metadata}
```

**Output**: Includes `confidence_metadata` with level, recommendation, and notes

### quality-validator
```python
# Confidence-adjusted status thresholds
if confidence_score >= 0.8:
    thresholds = {"APPROVED": 85, "REJECTED": 70}  # HIGH
elif confidence_score >= 0.6:
    thresholds = {"APPROVED": 80, "REJECTED": 65}  # MODERATE
elif confidence_score >= 0.4:
    thresholds = {"APPROVED": 75, "REJECTED": 60}  # LOW
else:
    thresholds = {"APPROVED": 70, "REJECTED": 55}  # VERY_LOW

# Apply penalty
if confidence_score < 0.4:
    score -= 10  # VERY LOW penalty
elif confidence_score < 0.6:
    score -= 5   # LOW penalty
```

**Output**: Adjusted validation thresholds and quality score penalties

---

## Classification Function

```python
def get_confidence_level(confidence_score: float) -> str:
    """
    Map confidence score to standardized level.

    Args:
        confidence_score: 0.0-1.0 prediction reliability

    Returns:
        "VERY_LOW" | "LOW" | "MODERATE" | "HIGH"
    """
    if confidence_score < 0.4:
        return "VERY_LOW"
    elif confidence_score < 0.6:
        return "LOW"
    elif confidence_score < 0.8:
        return "MODERATE"
    else:
        return "HIGH"
```

---

## Confidence Score Calculation

Confidence is computed by `python/volume/dynamic_calculator.py` based on:

| Factor | Weight | Measurement |
|--------|--------|-------------|
| Message count | 40% | `min(message_count / 50, 1.0)` |
| Data age | 20% | `1.0 - (days_since_last / 30)` |
| Multi-horizon divergence | 20% | `1.0 - abs(7d - 30d) / 100` |
| Caption pool depth | 20% | `available_captions / required_captions` |

**Example**:
- New creator, 8 messages, 5 days old: `confidence_score = 0.25` (VERY_LOW)
- Established creator, 45 messages, recent data: `confidence_score = 0.78` (MODERATE)
- Mature creator, 120+ messages, stable trends: `confidence_score = 0.92` (HIGH)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-19 | Initial canonical reference |

**Source Files**:
- `.claude/agents/performance-analyst.md` (lines 120-138)
- `.claude/agents/send-type-allocator.md` (lines 706-795)
- `.claude/agents/quality-validator.md` (lines 370-382, 641-649, 1015-1019, 1138-1183)
