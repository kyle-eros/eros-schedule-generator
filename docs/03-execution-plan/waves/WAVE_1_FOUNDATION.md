# WAVE 1: FOUNDATION & CRITICAL SCORING

**Status:** Ready for Execution
**Duration:** Weeks 1-2
**Priority:** P0 CRITICAL
**Expected Impact:** +107.6% RPS improvement on caption selection

---

## WAVE ENTRY GATE

### Prerequisites
- [ ] Access to EROS scheduling codebase
- [ ] 160-caption performance dataset available
- [ ] Database write access for schema changes
- [ ] Test environment configured

### Dependencies
- None (first wave)

---

## OBJECTIVE

Implement the highest-impact performance optimizations that directly affect revenue per send (RPS) and caption selection quality. This wave establishes the foundation for all subsequent enhancements.

---

## GAPS ADDRESSED

### Gap 2.1: Character Length Optimization (P0 CRITICAL)

**Current State:** No character length weighting in caption selection
**Target State:** 250-449 char captions prioritized with 1.0x multiplier

**Performance Data:**
```
Character Range    | Avg RPS   | Performance vs Optimal
-------------------|-----------|------------------------
250-449 chars      | 405.54x   | BASELINE (1.0x)
150-249 chars      | 306.29x   | -24.5% (0.755x)
50-149 chars       | 190.15x   | -53.1% (0.469x)
0-49 chars         | 89.39x    | -78.0% (0.220x)
450-549 chars      | 150.74x   | -62.8% (0.372x)
550-749 chars      | 45.28x    | -88.8% (0.112x)
750+ chars         | 15.02x    | -96.3% (0.037x)
```

**Business Impact:** +107.6% RPS by prioritizing 250-449 chars vs medium-length

---

### Gap 10.15: Confidence-Based Revenue Allocation (P0 CRITICAL)

**Current State:** Partial confidence dampening
**Target State:** Full alignment with reference table

**Reference Table:**
| Confidence Range | Revenue Allocation | Freshness Days | Followup Multiplier |
|------------------|-------------------|----------------|---------------------|
| 0.8-1.0 | Full tier volume | 30 days | 100% aggressive |
| 0.6-0.79 | Standard volume | 30 days | Standard |
| 0.4-0.59 | Tier minimum only | 20 days | 50% reduced |
| <0.4 | Conservative -30% | 15 days | 30% minimal |

---

### Gap 3.3: Send Type Diversity Minimum (P0 CRITICAL)

**Current State:** No validation of unique types per week
**Target State:** 10+ unique send types enforced

**Required Types Pool (from 22-type taxonomy):**

*Revenue Types:*
- `ppv_unlock`, `ppv_wall`, `tip_goal`, `bundle`, `flash_bundle`
- `game_post`, `first_to_tip`, `vip_program`, `snapchat_bundle`

*Engagement Types:*
- `link_drop`, `wall_link_drop`, `bump_normal`, `bump_descriptive`
- `bump_text_only`, `bump_flyer`, `dm_farm`, `like_farm`, `live_promo`

*Retention Types (PAID pages only):*
- `renew_on_post`, `renew_on_message`, `ppv_followup`, `expired_winback`

---

### Gap 8.1: Channel Assignment Accuracy (P0 CRITICAL)

**Reference Mapping:**
| Send Type | Primary Channel | Secondary | Page Restriction |
|-----------|-----------------|-----------|------------------|
| ppv_unlock | mass_message | - | Any |
| ppv_wall | wall_post | - | FREE only |
| bump_normal | wall_post | mass_message | Any |
| renew_on | mass_message | - | PAID only |

---

### Gap 9.1: Retention Types ONLY on PAID Pages (P0 CRITICAL)

**Rule:** `renew_on`, `expired_winback` ONLY on PAID pages
**Implementation:** Page type filter in Phase 2 allocator

---

### Gap 4.2: Consistent Non-Converter Elimination (P0 CRITICAL)

**Rule:** Filter out send types in "avoid" tier
**Impact:** Reallocate volume to winning types

---

## AGENT DEPLOYMENT

### Group A (Parallel Execution)

| Agent | Task | Complexity |
|-------|------|------------|
| `data-analyst` | Design character length multiplier algorithm | MEDIUM |
| `python-pro` | Build `calculate_character_length_multiplier()` | MEDIUM |
| `python-pro` | Update EROS scoring formula | LOW |

### Group B (Parallel with Group A)

| Agent | Task | Complexity |
|-------|------|------------|
| `database-optimizer` | Add `caption_char_count` indexing | LOW |
| `python-pro` | Implement confidence alignment | LOW |
| `python-pro` | Build diversity validator | LOW |

### Sequential (After Groups A+B)

| Agent | Task | Complexity |
|-------|------|------------|
| `code-reviewer` | Review all scoring changes | MEDIUM |

---

## IMPLEMENTATION TASKS

### Task 1.1: Character Length Scoring Multiplier

**Agent:** data-analyst, python-pro
**Complexity:** MEDIUM
**File:** `/python/volume/score_calculator.py` (NEW FILE - extends existing scoring infrastructure)

> **Note:** This is a NEW file to create. The existing `/python/volume/confidence.py` handles confidence dampening. This new module handles EROS scoring with character length optimization.

**Public API Exports:**
```python
__all__ = [
    'calculate_character_length_multiplier',
    'calculate_enhanced_eros_score',
    'CHARACTER_LENGTH_RANGES',
]

# Character length performance data for reference/testing
CHARACTER_LENGTH_RANGES = {
    'optimal': (250, 449, 1.0),       # 405.54x avg RPS
    'medium_short': (150, 249, 0.755), # -24.5%
    'short': (50, 149, 0.469),         # -53.1%
    'ultra_short': (0, 49, 0.220),     # -78.0%
    'medium_long': (450, 549, 0.372),  # -62.8%
    'long': (550, 749, 0.112),         # -88.8%
    'ultra_long': (750, float('inf'), 0.037),  # -96.3%
}
```

```python
def calculate_character_length_multiplier(caption_text: str | None) -> float:
    """
    Performance multiplier based on 160-caption dataset analysis.
    250-449 chars = 405.54x avg RPS (optimal baseline = 1.0)

    Args:
        caption_text: Caption text to evaluate. None or empty returns minimum multiplier.

    Returns:
        Multiplier between 0.037 (worst) and 1.0 (optimal).
    """
    if caption_text is None:
        return 0.037  # Treat None as worst case

    if not isinstance(caption_text, str):
        raise TypeError(f"Expected str, got {type(caption_text).__name__}")

    # Handle whitespace-only strings as empty
    stripped_text = caption_text.strip()
    char_count = len(stripped_text)

    if char_count == 0:
        return 0.037  # Empty or whitespace-only string is worst case

    if 250 <= char_count <= 449:
        return 1.0  # OPTIMAL ZONE
    elif 150 <= char_count < 250:
        return 0.755  # -24.5% performance
    elif 50 <= char_count < 150:
        return 0.469  # -53.1% performance
    elif char_count < 50:
        return 0.220  # -78.0% performance
    elif 450 <= char_count < 550:
        return 0.372  # -62.8% performance
    elif 550 <= char_count < 750:
        return 0.112  # -88.8% performance
    else:  # 750+
        return 0.037  # -96.3% performance (ultra-long)
```

**Test File:** `/python/tests/test_wave1_scoring.py`

**Test Framework:** pytest with fixtures

**Required Fixtures:**
```python
@pytest.fixture
def sample_captions() -> list[dict]:
    """Sample captions across all character ranges."""
    return [
        {'text': 'x' * 300, 'expected_mult': 1.0},      # Optimal
        {'text': 'x' * 200, 'expected_mult': 0.755},    # Medium-short
        {'text': 'x' * 100, 'expected_mult': 0.469},    # Short
        {'text': 'x' * 25, 'expected_mult': 0.220},     # Ultra-short
        {'text': 'x' * 500, 'expected_mult': 0.372},    # Medium-long
        {'text': 'x' * 600, 'expected_mult': 0.112},    # Long
        {'text': 'x' * 800, 'expected_mult': 0.037},    # Ultra-long
    ]

@pytest.fixture
def boundary_values() -> list[tuple[int, float]]:
    """Boundary test cases: (char_count, expected_multiplier)."""
    return [
        (0, 0.037), (49, 0.220), (50, 0.469), (149, 0.469),
        (150, 0.755), (249, 0.755), (250, 1.0), (449, 1.0),
        (450, 0.372), (549, 0.372), (550, 0.112), (749, 0.112), (750, 0.037)
    ]
```

**Performance Benchmark:** <5ms per scoring call (target: 1000 captions/second)

**Tests Required:**
- [ ] Test each character range returns correct multiplier
- [ ] Test boundary values (0, 49, 50, 149, 150, 249, 250, 449, 450, 549, 550, 749, 750)
- [ ] Test empty string handling (returns 0.037)
- [ ] Test whitespace-only string handling (returns 0.037)
- [ ] Test None input handling (returns 0.037)
- [ ] Test non-string input raises TypeError
- [ ] Test unicode/emoji character counting
- [ ] Performance test: 1000 iterations < 5 seconds

---

### Task 1.2: Enhanced EROS Score Integration

**Agent:** python-pro
**Complexity:** LOW
**Dependencies:** Task 1.1
**File:** `/python/volume/score_calculator.py` (same file as Task 1.1)

**IMPORTANT: Scoring System Clarification**

This EROS scoring (40/30/20/10 for RPS, conversion, execution, diversity) operates at the **send/campaign level** and is COMPLEMENTARY to the existing caption selection scoring in `/python/caption/caption_matcher.py`:

| System | Level | Weights | Purpose |
|--------|-------|---------|---------|
| EROS Score | Send/Campaign | 40% RPS, 30% conversion, 20% execution, 10% diversity | Evaluates overall send effectiveness |
| Caption Matcher | Caption Selection | 40% freshness, 35% performance, 15% type_priority, 5% diversity, 5% persona | Selects best caption for a send |

These systems work together: EROS scoring determines *which sends to prioritize*, caption_matcher determines *which caption to use* for each send.

```python
def calculate_enhanced_eros_score(
    caption_data: dict,
    rps_score: float | None = None,
    conversion_score: float | None = None,
    execution_score: float | None = None,
    diversity_score: float | None = None
) -> float:
    """
    Enhanced EROS score incorporating character length optimization.

    Args:
        caption_data: Dictionary containing at minimum:
            - 'text': Caption text string
            - 'rps_score': Revenue per send score (0-1), optional if passed separately
            - 'conversion_score': Conversion rate score (0-1), optional if passed separately
            - 'execution_score': Execution quality score (0-1), optional if passed separately
            - 'diversity_score': Type diversity score (0-1), optional if passed separately
        rps_score: Override RPS score (takes precedence over caption_data)
        conversion_score: Override conversion score
        execution_score: Override execution score
        diversity_score: Override diversity score

    Returns:
        Enhanced EROS score between 0.0 and 1.0.

    Raises:
        KeyError: If 'text' not in caption_data and no scores provided
        TypeError: If caption_data is not a dict
    """
    if not isinstance(caption_data, dict):
        raise TypeError(f"Expected dict, got {type(caption_data).__name__}")

    # Extract scores from caption_data or use overrides
    _rps = rps_score if rps_score is not None else caption_data.get('rps_score', 0.0)
    _conv = conversion_score if conversion_score is not None else caption_data.get('conversion_score', 0.0)
    _exec = execution_score if execution_score is not None else caption_data.get('execution_score', 0.0)
    _div = diversity_score if diversity_score is not None else caption_data.get('diversity_score', 0.0)

    # Existing EROS calculation (send/campaign level)
    base_eros_score = (
        0.40 * _rps +
        0.30 * _conv +
        0.20 * _exec +
        0.10 * _div
    )

    # NEW: Apply length multiplier
    length_multiplier = calculate_character_length_multiplier(caption_data.get('text'))

    # 40% weight to length optimization
    enhanced_score = base_eros_score * (0.6 + 0.4 * length_multiplier)

    return enhanced_score
```

**Tests Required:**
- [ ] Test score increases for optimal-length captions
- [ ] Test score decreases for non-optimal lengths
- [ ] Test integration with existing EROS pipeline

---

### Task 1.3: Confidence-Based Revenue Allocation Alignment

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/volume/confidence.py` (EXTEND existing implementation)

> **Integration Note:** Confidence dampening already exists in `/python/volume/confidence.py` with `calculate_confidence()` function. This task should EXTEND the existing implementation, not duplicate it. Review the existing `calculate_confidence()` function and add/update `get_confidence_adjustments()` to align with the reference table.

```python
from typing import TypedDict

class ConfidenceAdjustments(TypedDict):
    volume_mult: float
    freshness_days: int
    followup_mult: float
    tier: str  # "full", "standard", "minimum", "conservative"

def get_confidence_adjustments(confidence: float) -> ConfidenceAdjustments:
    """
    Get volume, freshness, and followup multipliers for confidence level.

    Uses exclusive upper bounds to avoid boundary gaps.
    Confidence must be 0.0-1.0.
    """
    if not isinstance(confidence, (int, float)):
        raise TypeError(f"Expected numeric, got {type(confidence).__name__}")

    if confidence < 0 or confidence > 1:
        raise ValueError(f"Confidence must be 0-1, got {confidence}")

    # Use >= for lower bounds to avoid boundary gaps
    # Each tier has DISTINCT values to differentiate behavior
    if confidence >= 0.8:  # 0.8-1.0: Full tier volume (most aggressive)
        return ConfidenceAdjustments(volume_mult=1.0, freshness_days=30, followup_mult=1.0, tier="full")
    elif confidence >= 0.6:  # 0.6-0.799: Standard volume (slight followup reduction)
        return ConfidenceAdjustments(volume_mult=1.0, freshness_days=30, followup_mult=0.8, tier="standard")
    elif confidence >= 0.4:  # 0.4-0.599: Tier minimum (moderate reductions)
        return ConfidenceAdjustments(volume_mult=0.85, freshness_days=20, followup_mult=0.5, tier="minimum")
    else:  # 0.0-0.399: Conservative -30% (most conservative)
        return ConfidenceAdjustments(volume_mult=0.7, freshness_days=15, followup_mult=0.3, tier="conservative")
```

---

### Task 1.4: Send Type Diversity Validator

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/orchestration/quality_validator.py`

```python
def validate_send_type_diversity(weekly_schedule: list) -> dict:
    """
    Validate schedule contains 10+ unique send types.
    """
    unique_types = set(item['send_type'] for item in weekly_schedule)

    MINIMUM_TYPES = 10

    if len(unique_types) < MINIMUM_TYPES:
        # Provide recommendations for missing types (using correct 22-type taxonomy)
        standard_types = {
            # Revenue types
            'ppv_unlock', 'ppv_wall', 'tip_goal', 'bundle', 'flash_bundle',
            'game_post', 'first_to_tip', 'vip_program', 'snapchat_bundle',
            # Engagement types
            'link_drop', 'wall_link_drop', 'bump_normal', 'bump_descriptive',
            'bump_text_only', 'bump_flyer', 'dm_farm', 'like_farm', 'live_promo',
            # Retention types (only valid for paid pages)
            'renew_on_post', 'renew_on_message', 'ppv_followup', 'expired_winback'
        }
        missing = standard_types - unique_types

        return {
            'is_valid': False,
            'current_count': len(unique_types),
            'minimum_required': MINIMUM_TYPES,
            'missing_suggestions': list(missing)[:3],
            'error': f"Only {len(unique_types)} unique types (min: {MINIMUM_TYPES})"
        }

    return {'is_valid': True, 'current_count': len(unique_types)}
```

---

### Task 1.5: Channel Assignment Validator

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/orchestration/quality_validator.py`

```python
# Complete channel mapping for all 22 send types
CHANNEL_MAPPING = {
    # Revenue types (9)
    'ppv_unlock': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'ppv_wall': {'primary': 'wall_post', 'secondary': None, 'page_restriction': 'free'},
    'tip_goal': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'bundle': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'flash_bundle': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'game_post': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'first_to_tip': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'vip_program': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'snapchat_bundle': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    # Engagement types (9)
    'link_drop': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'wall_link_drop': {'primary': 'wall_post', 'secondary': None, 'page_restriction': None},
    'bump_normal': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'bump_descriptive': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'bump_text_only': {'primary': 'wall_post', 'secondary': 'mass_message', 'page_restriction': None},
    'bump_flyer': {'primary': 'wall_post', 'secondary': None, 'page_restriction': None},
    'dm_farm': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'like_farm': {'primary': 'wall_post', 'secondary': None, 'page_restriction': None},
    'live_promo': {'primary': 'wall_post', 'secondary': 'story', 'page_restriction': None},
    # Retention types (4) - PAID pages only
    'renew_on_post': {'primary': 'wall_post', 'secondary': None, 'page_restriction': 'paid'},
    'renew_on_message': {'primary': 'mass_message', 'secondary': None, 'page_restriction': 'paid'},
    'ppv_followup': {'primary': 'mass_message', 'secondary': None, 'page_restriction': None},
    'expired_winback': {'primary': 'mass_message', 'secondary': None, 'page_restriction': 'paid'},
}

def validate_channel_assignment(item: dict, page_type: str) -> dict:
    """Validate send type is assigned to correct channel for page type."""
    send_type = item['send_type']
    channel = item['channel']

    if send_type not in CHANNEL_MAPPING:
        return {'is_valid': True}  # Unknown type, skip validation

    mapping = CHANNEL_MAPPING[send_type]

    # Check channel correctness
    valid_channels = [mapping['primary']]
    if mapping['secondary']:
        valid_channels.append(mapping['secondary'])

    if channel not in valid_channels:
        return {
            'is_valid': False,
            'error': f"{send_type} should use {mapping['primary']}, not {channel}"
        }

    # Check page restriction
    if mapping['page_restriction']:
        if mapping['page_restriction'] == 'paid' and page_type == 'free':
            return {
                'is_valid': False,
                'error': f"{send_type} is only valid for PAID pages"
            }
        if mapping['page_restriction'] == 'free' and page_type == 'paid':
            return {
                'is_valid': False,
                'error': f"{send_type} is only valid for FREE pages"
            }

    return {'is_valid': True}
```

---

### Task 1.6: Non-Converter Elimination Filter

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/orchestration/send_type_allocator.py`

```python
def filter_non_converters(send_types: list, performance_data: dict) -> list:
    """
    Remove send types in 'avoid' tier from allocation.
    Reallocates volume to winning types.
    """
    avoid_types = []

    for send_type in send_types:
        if send_type in performance_data:
            if performance_data[send_type].get('tier') == 'avoid':
                avoid_types.append(send_type)

    if avoid_types:
        print(f"Excluding non-converters: {avoid_types}")

    return [st for st in send_types if st not in avoid_types]
```

---

## SUCCESS CRITERIA

### Must Pass Before Wave Exit

- [ ] **Character Length Integration**
  - `calculate_character_length_multiplier()` returns correct values
  - EROS score boosts optimal-length captions
  - 60%+ of selected captions are 250-449 chars in test runs

- [ ] **Confidence Alignment**
  - Low-confidence creators get reduced volume
  - Freshness thresholds adjust by confidence
  - Followup multipliers apply correctly

- [ ] **Diversity Enforcement**
  - Validator rejects <10 unique types
  - Suggestions provided for missing types
  - All test schedules pass diversity check

- [ ] **Channel Validation**
  - Page type restrictions enforced
  - Wrong channel assignments flagged
  - 100% of generated items pass validation

- [ ] **Non-Converter Filter**
  - AVOID tier types excluded
  - Volume reallocated to top performers
  - Performance data integration working

---

## QUALITY GATES

### 1. Unit Test Coverage
- [ ] All new functions have 90%+ test coverage
- [ ] Edge cases covered (empty strings, boundary values)

### 2. Performance Test
- [ ] Character length scoring adds <5ms to selection
- [ ] Full validation suite completes in <1s

### 3. Validation Test
- [ ] Generate 10 test schedules
- [ ] Verify all pass diversity minimum
- [ ] Verify 60%+ optimal-length caption selection

### 4. Regression Test
- [ ] Existing schedules maintain quality baseline
- [ ] No performance degradation

---

## WAVE EXIT CHECKLIST

Before proceeding to Wave 2:

- [ ] All 6 gaps implemented
- [ ] All tasks have code committed
- [ ] All unit tests passing
- [ ] Code review completed and approved
- [ ] Quality gates verified
- [ ] Documentation updated

---

## ROLLBACK PROCEDURE

If Wave 1 needs to be rolled back:

1. Revert EROS scoring formula to remove length multiplier
2. Remove confidence adjustment changes
3. Disable diversity validator
4. Restore original channel validation
5. Remove non-converter filter

All changes can be reverted independently if needed.

---

**Wave 1 Ready for Execution**
