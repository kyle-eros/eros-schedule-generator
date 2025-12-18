# WAVE 3: CONTENT MIX & VOLUME OPTIMIZATION

**Status:** Ready for Execution (after Wave 2)
**Duration:** Weeks 5-6
**Priority:** P0/P1
**Expected Impact:** +180-300% campaign volume, +25-33% bumps

---

## WAVE ENTRY GATE

### Prerequisites
- [ ] Wave 2 completed and validated
- [ ] All timing validators passing
- [ ] Database schema supports rotation state

### Dependencies
- Wave 1: Foundation & Critical Scoring (COMPLETE)
- Wave 2: Timing & Scheduling Precision (COMPLETE)

---

## OBJECTIVE

Implement page-type-specific volume rules, campaign frequency enforcement, and data-driven volume triggers. This wave transforms the volume calculation from generic fan-count-based tiers to a sophisticated page-type-aware system.

---

## GAPS ADDRESSED

### Gap 3.1: 60/40 PPV/Engagement Mix Validation (P0 CRITICAL)

**Current State:** Volume calculator has categories but no ratio enforcement
**Target State:** Tier-specific validation matching reference table

**Reference Ratios:**
```
Low volume (2-3 PPVs/day):  60% revenue drivers / 40% engagement
Mid/High/Ultra volume:      50% revenue drivers / 50% engagement
```

---

### Gap 3.2: Page Type-Specific Bump Ratios (P1 HIGH)

**Current State:** Only fan_count determines volume
**Target State:** Volume = f(fan_count, page_type, sub_type)

**Volume Matrix:**
```
Page Type    | Sub-Type    | Low (2-3)  | Mid (4-6)  | High (7-9) | Ultra (10-12)
-------------|-------------|------------|------------|------------|---------------
Nude         | GFE         | 2-3 + 4-6  | 4-6 + 4-6  | 7-9 + 7-9  | 10-12 + 10-12
Nude         | Commercial  | 2-3 + 5-6  | 4-6 + 4-6  | 7-9 + 7-9  | 10-12 + 10-12
Porno        | GFE         | 2-3 + 5-7  | 4-6 + 4-6  | 7-9 + 7-9  | 10-12 + 10-12
Porno        | Commercial  | 2-3 + 5-8  | 4-6 + 4-6  | 7-9 + 7-9  | 10-12 + 10-12
                            ↑ 1.67x-4.0x bump ratio range for Porno Commercial at low volume (~2.7x average; arithmetic mean of corner cases: 2.50, 4.00, 1.67, 2.67)
```

---

### Gap 4.1: Data-Driven Volume Increase Triggers (P0 CRITICAL)

**Reference Rule:** "If 60%+ of top 10 share a trait -> increase that type by 20-30%"

**Example:** If 8 of top 10 are long descriptive captions -> +25% descriptive allocation

---

### Gap 4.3: Low Frequency on Winners Detection (P1 HIGH)

**Reference Finding:**
```
Wall Campaigns Analysis:
- Only 5 campaigns in 30 days = UNDERPERFORMING
- Top 2 earned $404.98 and $274.89
- Recommendation: 10-15 descriptive + 4-5 games = 14-20/month
- Current system: ~5-10/month (180-300% BELOW optimal)
```

---

### Gap 5.1: Max 4 Followups/Day Limit (P1 HIGH)

**Rule:** Maximum 4 followups per day to prevent saturation
**Prioritization:** By parent PPV estimated revenue

---

### Gap 7.1: VIP Program 1/Week Limit (P1 HIGH)

**Rule:** VIP program and Snapchat bundle limited to 1/week
**Reason:** Maintain exclusivity perception

---

### Gap 7.2: Game Type Success Tracking (P1 HIGH)

**Current State:** `game_post` with no sub-type tracking
**Target State:** Performance tracked by game type

**Game Types:**
- spin_the_wheel: $5,178 avg (highest) -> weekly
- card_game: $500 avg (low) -> bi-weekly or stop
- prize_wheel: $2,500 avg -> weekly
- scratch_off: $1,200 avg -> weekly

---

## AGENT DEPLOYMENT

### Group A (Parallel Execution)

| Agent | Task | Complexity |
|-------|------|------------|
| `python-pro` | Implement page type volume matrix | MEDIUM |
| `data-analyst` | Build trait detection algorithm | MEDIUM |
| `database-optimizer` | Add page_type, sub_type to schema | MEDIUM |

### Group B (Parallel with Group A)

| Agent | Task | Complexity |
|-------|------|------------|
| `python-pro` | Campaign frequency validator | MEDIUM |
| `python-pro` | Followup limit enforcer | LOW |
| `python-pro` | Weekly limit validator | LOW |

### Sequential (After Groups A+B)

| Agent | Task | Complexity |
|-------|------|------------|
| `code-reviewer` | Review volume logic | MEDIUM |

---

## IMPLEMENTATION TASKS

### Task 3.1: Page Type Volume Matrix

**Agent:** python-pro, database-optimizer
**Complexity:** MEDIUM
**File:** `/python/volume/page_type_calculator.py`

```python
from dataclasses import dataclass
from typing import Literal, Tuple

@dataclass
class CreatorConfig:
    """Extended creator configuration with page type."""
    creator_id: str
    fan_count: int
    page_type: Literal['nude', 'non_nude', 'porno']
    sub_type: Literal['gfe', 'commercial', 'personalized']
    is_paid_page: bool
    confidence: float = 0.5

@dataclass
class VolumeTargets:
    """Calculated volume targets."""
    tier: str
    mmppvs_per_day: Tuple[int, int]
    bumps_per_day: Tuple[int, int]
    bump_to_ppv_ratio: float
    total_messages_per_day: Tuple[int, int]


# Volume matrix from reference documentation
BUMP_MATRIX = {
    # (page_type, sub_type): {tier: (min_bumps, max_bumps)}
    ('nude', 'gfe'): {
        'low': (4, 6), 'mid': (4, 6), 'high': (7, 9), 'ultra': (10, 12)
    },
    ('nude', 'commercial'): {
        'low': (5, 6), 'mid': (4, 6), 'high': (7, 9), 'ultra': (10, 12)
    },
    ('non_nude', 'gfe'): {
        'low': (4, 6), 'mid': (4, 6), 'high': (7, 9), 'ultra': (10, 12)
    },
    ('non_nude', 'commercial'): {
        'low': (5, 6), 'mid': (4, 6), 'high': (7, 9), 'ultra': (10, 12)
    },
    ('porno', 'gfe'): {
        'low': (5, 7), 'mid': (4, 6), 'high': (7, 9), 'ultra': (10, 12)
    },
    ('porno', 'commercial'): {
        'low': (5, 8), 'mid': (4, 6), 'high': (7, 9), 'ultra': (10, 12)  # 2.67x ratio!
    },
}

TIER_PPVS = {
    'low': (2, 3),
    'mid': (4, 6),
    'high': (7, 9),
    'ultra': (10, 12)
}


def get_volume_tier(fan_count: int) -> str:
    """Determine volume tier from fan count.

    PRODUCTION THRESHOLDS (aligned with python/volume/tier_config.py):
    - LOW: 0-999 fans
    - MID: 1,000-4,999 fans
    - HIGH: 5,000-14,999 fans
    - ULTRA: 15,000+ fans
    """
    if fan_count >= 15000:
        return 'ultra'
    elif fan_count >= 5000:
        return 'high'
    elif fan_count >= 1000:
        return 'mid'
    else:
        return 'low'


def calculate_volume_targets(config: CreatorConfig) -> VolumeTargets:
    """
    Calculate MMPPV + bump targets based on page type matrix.
    """
    tier = get_volume_tier(config.fan_count)

    # Get MMPPVs for tier
    mmppvs = TIER_PPVS[tier]

    # Get bumps based on page type and sub-type
    page_key = (config.page_type, config.sub_type)

    # Fall back to 'gfe' if personalized or unknown
    if page_key not in BUMP_MATRIX:
        page_key = (config.page_type, 'gfe')
    if page_key not in BUMP_MATRIX:
        page_key = ('nude', 'gfe')  # Default fallback

    bumps = BUMP_MATRIX[page_key][tier]

    # Calculate bump ratio
    bump_ratio = bumps[0] / mmppvs[0]

    # Calculate totals
    total_min = mmppvs[0] + bumps[0]
    total_max = mmppvs[1] + bumps[1]

    return VolumeTargets(
        tier=tier,
        mmppvs_per_day=mmppvs,
        bumps_per_day=bumps,
        bump_to_ppv_ratio=bump_ratio,
        total_messages_per_day=(total_min, total_max)
    )


def validate_bump_ratio(
    schedule: list,
    config: CreatorConfig
) -> dict:
    """Validate schedule bump:PPV ratio matches page type expectations."""
    targets = calculate_volume_targets(config)

    ppv_count = sum(1 for item in schedule if item.get('is_ppv', False))
    bump_count = sum(1 for item in schedule if item.get('is_bump', False))

    if ppv_count == 0 and bump_count == 0:
        return {'is_valid': True, 'warning': 'No PPVs or bumps in schedule - empty schedule?'}
    elif ppv_count == 0:
        return {'is_valid': False, 'error': f'Found {bump_count} bumps but no PPVs - invalid ratio'}
    elif bump_count == 0:
        return {'is_valid': False, 'error': 'No bumps scheduled - add engagement content'}

    actual_ratio = bump_count / ppv_count
    expected_min = targets.bumps_per_day[0] / targets.mmppvs_per_day[1]  # Conservative
    expected_max = targets.bumps_per_day[1] / targets.mmppvs_per_day[0]  # Aggressive

    if actual_ratio < expected_min * 0.8:  # 20% tolerance
        bumps_needed = int(expected_min * ppv_count - bump_count)
        return {
            'is_valid': False,
            'actual_ratio': actual_ratio,
            'expected_range': (expected_min, expected_max),
            'error': f"Bump ratio too low ({actual_ratio:.2f}x). Add {bumps_needed} bumps."
        }

    if actual_ratio > expected_max * 1.2:  # 20% tolerance
        return {
            'is_valid': False,
            'actual_ratio': actual_ratio,
            'expected_range': (expected_min, expected_max),
            'warning': f"Bump ratio high ({actual_ratio:.2f}x). Risk of inbox fatigue."
        }

    return {
        'is_valid': True,
        'actual_ratio': actual_ratio,
        'expected_range': (expected_min, expected_max)
    }
```

---

### Task 3.2: Campaign Frequency Enforcement

**Agent:** python-pro
**Complexity:** MEDIUM
**File:** `/python/volume/campaign_frequency.py`

```python
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict

# Campaign frequency rules from reference documentation
CAMPAIGN_FREQUENCY_RULES = {
    'descriptive_wall_campaign': {
        'min_days_between': 2,
        'max_days_between': 3,
        'monthly_target': (10, 15),
        'rationale': 'Top converters (8 of top 10 in 365-day analysis)'
    },
    'spin_the_wheel_game': {
        'frequency': 'weekly',
        'min_days_between': 7,
        'max_days_between': 7,
        'monthly_target': (4, 5),
        'rationale': 'High single performance ($5,178 reference), weekly cadence'
    },
    'bundle_wall_campaign': {
        'min_days_between': 5,
        'max_days_between': 7,
        'monthly_target': (4, 6),
        'rationale': 'Value-focused, needs spacing for scarcity'
    },
    'game_other': {
        'min_days_between': 7,
        'max_days_between': 14,
        'monthly_target': (2, 4),
        'rationale': 'Lower-performing game types'
    },
}


def validate_campaign_frequency(
    schedule: List[dict],
    lookback_days: int = 30
) -> Dict:
    """
    Validate campaign types are scheduled at optimal frequencies.
    Target: 14-20 campaigns/month (vs current ~5/month)
    """
    warnings = []
    recommendations = []

    # Collect campaign dates by type
    campaign_dates = defaultdict(list)
    for item in schedule:
        campaign_type = item.get('campaign_type')
        if campaign_type and campaign_type in CAMPAIGN_FREQUENCY_RULES:
            scheduled_time = item.get('scheduled_time')
            if scheduled_time:
                campaign_dates[campaign_type].append(scheduled_time)

    # Validate each campaign type
    for campaign_type, rules in CAMPAIGN_FREQUENCY_RULES.items():
        dates = sorted(campaign_dates.get(campaign_type, []))

        if not dates:
            if 'monthly_target' in rules:
                min_target, max_target = rules['monthly_target']
                recommendations.append({
                    'type': campaign_type,
                    'message': f"No {campaign_type} scheduled. Add {min_target}-{max_target}/month.",
                    'rationale': rules['rationale']
                })
            continue

        # Check spacing between campaigns
        if len(dates) > 1 and 'min_days_between' in rules:
            for i in range(len(dates) - 1):
                days_apart = (dates[i+1] - dates[i]).days

                # Handle same-day campaigns (days_apart == 0)
                if days_apart == 0:
                    warnings.append({
                        'type': campaign_type,
                        'message': f"{campaign_type} scheduled multiple times on {dates[i+1].date()}. Consider spreading across days.",
                        'severity': 'critical'
                    })
                elif days_apart < rules['min_days_between']:
                    warnings.append({
                        'type': campaign_type,
                        'message': f"{campaign_type} on {dates[i+1]} is only {days_apart} days after previous (min: {rules['min_days_between']})",
                        'severity': 'high'
                    })
                elif days_apart > rules.get('max_days_between', 999):
                    warnings.append({
                        'type': campaign_type,
                        'message': f"{campaign_type} gap of {days_apart} days exceeds max ({rules['max_days_between']}). Opportunity loss.",
                        'severity': 'medium'
                    })

        # Check monthly volume
        if 'monthly_target' in rules:
            # Calculate schedule_days dynamically from actual schedule data
            if schedule:
                all_times = [item.get('scheduled_time') for item in schedule if item.get('scheduled_time')]
                if all_times:
                    first_date = min(all_times)
                    last_date = max(all_times)
                    schedule_days = max(1, (last_date - first_date).days + 1)
                else:
                    schedule_days = 7  # Default fallback
            else:
                schedule_days = 7  # Default fallback
            monthly_projection = len(dates) * (30 / schedule_days)

            min_target, max_target = rules['monthly_target']

            if monthly_projection < min_target:
                shortfall = min_target - monthly_projection
                warnings.append({
                    'type': campaign_type,
                    'message': f"{campaign_type} under-scheduled: {monthly_projection:.0f}/month projected (target: {min_target}-{max_target}). Add ~{shortfall:.0f} more.",
                    'severity': 'high',
                    'rationale': rules['rationale']
                })

    # Overall campaign frequency check
    total_campaigns = sum(len(dates) for dates in campaign_dates.values())
    schedule_days = 7
    monthly_projection = total_campaigns * (30 / schedule_days)

    if monthly_projection < 14:
        warnings.append({
            'type': 'overall',
            'message': f"Total campaign volume too low: {monthly_projection:.0f}/month (target: 14-20)",
            'severity': 'critical'
        })

    return {
        'is_valid': len([w for w in warnings if w.get('severity') == 'critical']) == 0,
        'warnings': warnings,
        'recommendations': recommendations,
        'total_monthly_projection': monthly_projection
    }
```

---

### Task 3.3: Data-Driven Volume Triggers

**Agent:** data-analyst, python-pro
**Complexity:** MEDIUM
**File:** `/python/analytics/trait_detector.py`

```python
from collections import Counter
from typing import List, Dict, Any

def analyze_top_performer_traits(
    performance_data: List[Dict],
    top_n: int = 10,
    min_sample_for_confidence: int = 50,
    alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Detect shared traits in top performers for volume increase recommendations.
    Rule: If 60%+ share a trait AND statistically significant, increase that type by 20-30%

    Uses chi-square test with Bonferroni correction to ensure statistical significance
    before making recommendations.

    Args:
        performance_data: List of performance records
        top_n: Number of top performers to analyze
        min_sample_for_confidence: Minimum sample size for statistical confidence
        alpha: Significance level for hypothesis testing (default 0.05)
    """
    from scipy import stats
    import numpy as np

    if len(performance_data) < top_n:
        return {'has_recommendations': False, 'reason': 'Insufficient data'}

    # Add statistical significance warning
    statistical_confidence = 'HIGH' if len(performance_data) >= min_sample_for_confidence else 'LOW'
    if statistical_confidence == 'LOW':
        print(f"Warning: Sample size {len(performance_data)} may not be statistically significant (recommend {min_sample_for_confidence}+)")

    # Sort by earnings and take top N
    top_performers = sorted(
        performance_data,
        key=lambda x: x.get('earnings', 0),
        reverse=True
    )[:top_n]

    # Get non-top performers for comparison
    non_top_performers = sorted(
        performance_data,
        key=lambda x: x.get('earnings', 0),
        reverse=True
    )[top_n:]

    shared_traits = {}
    recommendations = []
    threshold = 0.6  # 60% must share trait

    # Bonferroni correction for multiple comparisons
    num_traits_tested = 4  # length, content_type, tone, price
    adjusted_alpha = alpha / num_traits_tested

    def chi_square_test(top_count: int, top_total: int, non_top_count: int, non_top_total: int) -> float:
        """Perform chi-square test and return p-value."""
        # Contingency table: [[top_with_trait, top_without], [non_top_with, non_top_without]]
        observed = np.array([
            [top_count, top_total - top_count],
            [non_top_count, non_top_total - non_top_count]
        ])
        # Add small constant to avoid division by zero
        if observed.min() < 5:
            # Use Fisher's exact test for small samples
            _, p_value = stats.fisher_exact(observed)
        else:
            chi2, p_value, _, _ = stats.chi2_contingency(observed)
        return p_value

    # 1. Analyze character length
    optimal_length_count = sum(
        1 for p in top_performers
        if 250 <= len(p.get('caption_text', '')) <= 449
    )
    non_top_optimal_count = sum(
        1 for p in non_top_performers
        if 250 <= len(p.get('caption_text', '')) <= 449
    ) if non_top_performers else 0

    if optimal_length_count >= top_n * threshold:
        p_value = chi_square_test(
            optimal_length_count, top_n,
            non_top_optimal_count, len(non_top_performers)
        ) if non_top_performers else 1.0

        shared_traits['optimal_length'] = {
            'count': optimal_length_count,
            'percentage': optimal_length_count / top_n,
            'p_value': p_value,
            'is_significant': p_value < adjusted_alpha,
            'recommendation': 'Prioritize 250-449 char captions (+25% weight)'
        }
        if p_value < adjusted_alpha:
            recommendations.append({
                'trait': 'optimal_length',
                'action': 'increase_weight',
                'multiplier': 1.25,
                'p_value': p_value
            })

    # 2. Analyze content type
    type_counts = Counter(p.get('content_type', 'unknown') for p in top_performers)
    dominant_type, count = type_counts.most_common(1)[0]

    non_top_type_count = sum(
        1 for p in non_top_performers
        if p.get('content_type', 'unknown') == dominant_type
    ) if non_top_performers else 0

    if count >= top_n * threshold:
        p_value = chi_square_test(
            count, top_n,
            non_top_type_count, len(non_top_performers)
        ) if non_top_performers else 1.0

        shared_traits['dominant_content_type'] = {
            'type': dominant_type,
            'count': count,
            'percentage': count / top_n,
            'p_value': p_value,
            'is_significant': p_value < adjusted_alpha,
            'recommendation': f'Increase {dominant_type} allocation by 25%'
        }
        if p_value < adjusted_alpha:
            recommendations.append({
                'trait': 'content_type',
                'type': dominant_type,
                'action': 'increase_allocation',
                'multiplier': 1.25,
                'p_value': p_value
            })

    # 3. Analyze tone/style
    tone_counts = Counter(p.get('detected_tone', 'neutral') for p in top_performers)
    dominant_tone, tone_count = tone_counts.most_common(1)[0]

    non_top_tone_count = sum(
        1 for p in non_top_performers
        if p.get('detected_tone', 'neutral') == dominant_tone
    ) if non_top_performers else 0

    if tone_count >= top_n * threshold:
        p_value = chi_square_test(
            tone_count, top_n,
            non_top_tone_count, len(non_top_performers)
        ) if non_top_performers else 1.0

        shared_traits['dominant_tone'] = {
            'tone': dominant_tone,
            'count': tone_count,
            'percentage': tone_count / top_n,
            'p_value': p_value,
            'is_significant': p_value < adjusted_alpha,
            'recommendation': f'Prioritize {dominant_tone} captions (+20% weight)'
        }
        if p_value < adjusted_alpha:
            recommendations.append({
                'trait': 'tone',
                'tone': dominant_tone,
                'action': 'increase_weight',
                'multiplier': 1.20,
                'p_value': p_value
            })

    # 4. Analyze price point
    price_counts = Counter(p.get('price', 0) for p in top_performers)
    dominant_price, price_count = price_counts.most_common(1)[0]

    non_top_price_count = sum(
        1 for p in non_top_performers
        if p.get('price', 0) == dominant_price
    ) if non_top_performers else 0

    if price_count >= top_n * threshold:
        p_value = chi_square_test(
            price_count, top_n,
            non_top_price_count, len(non_top_performers)
        ) if non_top_performers else 1.0

        shared_traits['dominant_price'] = {
            'price': dominant_price,
            'count': price_count,
            'percentage': price_count / top_n,
            'p_value': p_value,
            'is_significant': p_value < adjusted_alpha,
            'recommendation': f'Use ${dominant_price} pricing more frequently'
        }

    return {
        'has_recommendations': len(recommendations) > 0,
        'shared_traits': shared_traits,
        'recommendations': recommendations,
        'analyzed_count': top_n,
        'statistical_confidence': statistical_confidence,
        'bonferroni_alpha': adjusted_alpha
    }


def apply_volume_increases(
    allocation: Dict[str, float],
    recommendations: List[Dict]
) -> Dict[str, float]:
    """
    Apply volume increases based on detected traits.
    """
    adjusted_allocation = allocation.copy()

    for rec in recommendations:
        if rec['action'] == 'increase_weight' and rec['trait'] == 'optimal_length':
            adjusted_allocation['optimal_length_bonus'] = rec['multiplier']

        elif rec['action'] == 'increase_allocation' and 'type' in rec:
            content_type = rec['type']
            if content_type in adjusted_allocation:
                adjusted_allocation[content_type] *= rec['multiplier']

    return adjusted_allocation
```

---

### Task 3.4: Daily Followup Limit Enforcer

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/orchestration/followup_limiter.py`

```python
from typing import List, Dict

MAX_FOLLOWUPS_PER_DAY = 4

# Multi-factor weights for followup prioritization
FOLLOWUP_WEIGHTS = {
    'REVENUE': 0.50,    # Parent PPV revenue importance
    'RECENCY': 0.30,    # How recently the parent PPV was sent
    'ENGAGEMENT': 0.20  # Historical engagement rate
}


def _calculate_followup_priority(followup: Dict, reference_time: datetime = None) -> float:
    """
    Calculate multi-factor priority score for a followup.

    Priority = REVENUE_WEIGHT * normalized_revenue +
               RECENCY_WEIGHT * recency_score +
               ENGAGEMENT_WEIGHT * engagement_score

    Args:
        followup: Followup item with parent_estimated_revenue, parent_sent_time, etc.
        reference_time: Reference time for recency calculation (default: now)

    Returns:
        Priority score between 0 and 1
    """
    if reference_time is None:
        reference_time = datetime.now()

    # 1. Revenue score (normalized to 0-1, assuming max revenue of $1000)
    revenue = followup.get('parent_estimated_revenue', 0)
    normalized_revenue = min(revenue / 1000.0, 1.0)

    # 2. Recency score (higher for more recent parent PPVs)
    parent_sent_time = followup.get('parent_sent_time')
    if parent_sent_time:
        hours_since_parent = (reference_time - parent_sent_time).total_seconds() / 3600
        # Score decays from 1.0 to 0.0 over 24 hours
        recency_score = max(0.0, 1.0 - (hours_since_parent / 24.0))
    else:
        recency_score = 0.5  # Default if no timestamp

    # 3. Engagement score (historical engagement rate)
    engagement_rate = followup.get('parent_engagement_rate', 0.0)
    # Normalize assuming 20% is excellent engagement
    engagement_score = min(engagement_rate / 0.20, 1.0)

    # Calculate weighted priority
    priority = (
        FOLLOWUP_WEIGHTS['REVENUE'] * normalized_revenue +
        FOLLOWUP_WEIGHTS['RECENCY'] * recency_score +
        FOLLOWUP_WEIGHTS['ENGAGEMENT'] * engagement_score
    )

    return priority


def enforce_daily_followup_limit(
    daily_schedule: List[Dict],
    max_followups: int = MAX_FOLLOWUPS_PER_DAY
) -> Dict:
    """
    Enforce maximum 4 followups per day.
    Prioritizes using multi-factor scoring (revenue, recency, engagement).
    """
    followups = [
        item for item in daily_schedule
        if item.get('send_type') == 'ppv_followup'
    ]

    if len(followups) <= max_followups:
        return {
            'modified': False,
            'followup_count': len(followups)
        }

    # Sort by multi-factor priority score (highest first)
    reference_time = datetime.now()
    followups.sort(
        key=lambda x: _calculate_followup_priority(x, reference_time),
        reverse=True
    )

    # Keep top N, remove rest
    to_keep = followups[:max_followups]
    to_remove = followups[max_followups:]

    for item in to_remove:
        daily_schedule.remove(item)

    return {
        'modified': True,
        'followup_count': max_followups,
        'removed_count': len(to_remove),
        'removed_items': [
            {
                'id': item.get('id'),
                'parent_revenue': item.get('parent_estimated_revenue', 0)
            }
            for item in to_remove
        ]
    }
```

---

### Task 3.5: Weekly Limit Validator

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/orchestration/weekly_limits.py`

```python
from typing import List, Dict
from collections import Counter

WEEKLY_LIMITS = {
    'vip_program': 1,
    'snapchat_bundle': 1,
}

def validate_weekly_limits(weekly_schedule: List[Dict]) -> Dict:
    """
    Enforce weekly limits for exclusive send types.
    VIP and Snapchat bundles limited to 1/week for exclusivity.
    """
    warnings = []

    type_counts = Counter(item.get('send_type') for item in weekly_schedule)

    for send_type, max_count in WEEKLY_LIMITS.items():
        actual_count = type_counts.get(send_type, 0)

        if actual_count > max_count:
            warnings.append({
                'send_type': send_type,
                'actual': actual_count,
                'limit': max_count,
                'message': f"{send_type} over-scheduled: {actual_count}x this week (max: {max_count})"
            })

    return {
        'is_valid': len(warnings) == 0,
        'warnings': warnings
    }
```

---

### Task 3.6: Game Type Success Tracker

**Agent:** python-pro, database-optimizer
**Complexity:** MEDIUM
**File:** `/python/analytics/game_tracker.py`

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
from collections import defaultdict

@dataclass
class GamePerformance:
    game_type: str
    earnings: float
    date: str
    creator_id: str

# Reference performance benchmarks with statistical metadata
GAME_BENCHMARKS = {
    'spin_the_wheel': {
        'avg_earnings': 5178.50,
        'std_dev': 2500.00,
        'sample_size': 45,
        'ci_95_lower': 4432.0,
        'ci_95_upper': 5925.0,
        'recommended_frequency': 'weekly',
        'performance_tier': 'top'
    },
    'prize_wheel': {
        'avg_earnings': 2500.00,
        'std_dev': 1200.00,
        'sample_size': 38,
        'ci_95_lower': 2110.0,
        'ci_95_upper': 2890.0,
        'recommended_frequency': 'weekly',
        'performance_tier': 'mid'
    },
    'mystery_box': {
        'avg_earnings': 3000.00,
        'std_dev': 1400.00,
        'sample_size': 32,
        'ci_95_lower': 2502.0,
        'ci_95_upper': 3498.0,
        'recommended_frequency': 'weekly',
        'performance_tier': 'mid'
    },
    'scratch_off': {
        'avg_earnings': 1200.00,
        'std_dev': 600.00,
        'sample_size': 28,
        'ci_95_lower': 970.0,
        'ci_95_upper': 1430.0,
        'recommended_frequency': 'weekly',
        'performance_tier': 'low'
    },
    'card_game': {
        'avg_earnings': 500.00,
        'std_dev': 300.00,
        'sample_size': 22,
        'ci_95_lower': 370.0,
        'ci_95_upper': 630.0,
        'recommended_frequency': 'bi-weekly_or_stop',
        'performance_tier': 'avoid'
    },
}


class GameTypeTracker:
    """Track game performance by sub-type for optimization."""

    def __init__(self, creator_id: str):
        self.creator_id = creator_id
        self.performance_history: List[GamePerformance] = []

    def record_performance(self, game_type: str, earnings: float, date: str):
        """Record game performance."""
        self.performance_history.append(GamePerformance(
            game_type=game_type,
            earnings=earnings,
            date=date,
            creator_id=self.creator_id
        ))

    def get_recommendations(self) -> Dict:
        """Get recommendations based on performance history with Bayesian updating.

        Uses Bayesian updating to combine creator-specific history with
        population benchmarks. This provides better estimates for game types
        with limited creator-specific data.
        """
        import math

        def bayesian_update(
            prior_mean: float,
            prior_std: float,
            prior_n: int,
            observed_mean: float,
            observed_n: int
        ) -> tuple:
            """
            Perform Bayesian update using conjugate normal prior.

            Returns posterior mean and effective sample size.
            """
            # Weight prior by its sample size
            total_n = prior_n + observed_n
            posterior_mean = (
                (prior_mean * prior_n + observed_mean * observed_n) / total_n
            )
            return posterior_mean, total_n

        if not self.performance_history:
            # No history, use benchmarks
            return {
                'recommended': 'spin_the_wheel',
                'reason': 'Highest benchmark earnings ($5,178)',
                'avoid': ['card_game'],
                'source': 'benchmark'
            }

        # Calculate average by type
        type_earnings = defaultdict(list)
        for game in self.performance_history:
            type_earnings[game.game_type].append(game.earnings)

        type_averages = {
            game_type: sum(earnings) / len(earnings)
            for game_type, earnings in type_earnings.items()
        }

        # Apply Bayesian updating with benchmark priors
        bayesian_estimates = {}
        for game_type, earnings_list in type_earnings.items():
            observed_mean = sum(earnings_list) / len(earnings_list)
            observed_n = len(earnings_list)

            if game_type in GAME_BENCHMARKS:
                benchmark = GAME_BENCHMARKS[game_type]
                prior_mean = benchmark['avg_earnings']
                prior_n = benchmark['sample_size']

                posterior_mean, effective_n = bayesian_update(
                    prior_mean, 0, prior_n,  # std not used in simplified version
                    observed_mean, observed_n
                )
                bayesian_estimates[game_type] = {
                    'posterior_mean': posterior_mean,
                    'effective_n': effective_n,
                    'creator_weight': observed_n / effective_n,
                    'benchmark_weight': prior_n / effective_n
                }
            else:
                # No benchmark, use creator data only
                bayesian_estimates[game_type] = {
                    'posterior_mean': observed_mean,
                    'effective_n': observed_n,
                    'creator_weight': 1.0,
                    'benchmark_weight': 0.0
                }

        # Find best performer using Bayesian estimates
        if bayesian_estimates:
            best_type = max(
                bayesian_estimates.keys(),
                key=lambda t: bayesian_estimates[t]['posterior_mean']
            )
            worst_type = min(
                bayesian_estimates.keys(),
                key=lambda t: bayesian_estimates[t]['posterior_mean']
            )

            avoid_list = [
                game_type for game_type, est in bayesian_estimates.items()
                if est['posterior_mean'] < 1000  # Below $1000 threshold
            ]

            return {
                'recommended': best_type,
                'reason': f"Best performer (${bayesian_estimates[best_type]['posterior_mean']:.2f} Bayesian avg)",
                'avoid': avoid_list,
                'worst': worst_type,
                'source': 'bayesian_updated',
                'raw_averages': type_averages,
                'bayesian_estimates': bayesian_estimates
            }

        return {
            'recommended': 'spin_the_wheel',
            'reason': 'Default recommendation',
            'source': 'default'
        }


def get_game_frequency(game_type: str) -> str:
    """Get recommended frequency for game type."""
    if game_type in GAME_BENCHMARKS:
        return GAME_BENCHMARKS[game_type]['recommended_frequency']
    return 'weekly'  # Default
```

---

## INTEGRATION WITH EXISTING INFRASTRUCTURE

### Important: Extend, Don't Replace

**CRITICAL**: The production codebase already implements most volume optimization logic in `python/volume/dynamic_calculator.py`. Wave 3 implementations should **EXTEND** existing code rather than creating parallel implementations.

### Existing Infrastructure Reference

| Module | Location | Purpose |
|--------|----------|---------|
| `dynamic_calculator.py` | `/python/volume/` | Core volume calculation engine |
| `tier_config.py` | `/python/volume/` | Production tier thresholds (use these!) |
| `config_loader.py` | `/python/volume/` | YAML-based configuration loading |
| `multi_horizon.py` | `/python/volume/` | 7d/14d/30d score fusion |
| `confidence.py` | `/python/volume/` | Confidence dampening for low data |
| `day_of_week.py` | `/python/volume/` | DOW multiplier calculation |
| `elasticity.py` | `/python/volume/` | Diminishing returns detection |
| `content_weighting.py` | `/python/volume/` | Content type performance weighting |
| `caption_constraint.py` | `/python/volume/` | Caption pool verification |
| `prediction_tracker.py` | `/python/volume/` | Accuracy tracking |

### OptimizedVolumeResult Dataclass

The `OptimizedVolumeResult` dataclass in `dynamic_calculator.py` already provides:

```python
@dataclass
class OptimizedVolumeResult:
    """Complete volume calculation result with all adjustments applied."""
    base_config: VolumeConfig           # Initial tier calculation
    final_config: VolumeConfig          # After all adjustments
    weekly_distribution: dict[int, int] # DOW-adjusted volumes
    content_allocations: dict[str, int] # Performance-weighted by type
    adjustments_applied: list[str]      # Audit trail
    confidence_score: float             # 0.0-1.0
    elasticity_capped: bool             # Diminishing returns applied?
    caption_warnings: list[str]         # Pool shortage warnings
    prediction_id: Optional[int]        # For accuracy tracking
    fused_saturation: float             # Multi-horizon fused
    fused_opportunity: float            # Multi-horizon fused
    divergence_detected: bool           # Horizon divergence flag
    dow_multipliers_used: dict[int, float]
    message_count: int
```

### Integration Guidelines

1. **Page Type Volume Matrix** (Task 3.1):
   - Add page_type/sub_type columns to `TIER_CONFIGS` in `tier_config.py`
   - Extend `calculate_dynamic_volume()` to accept page type parameters

2. **Campaign Frequency** (Task 3.2):
   - Create new module `python/volume/campaign_frequency.py`
   - Integrate with `calculate_optimized_volume()` pipeline

3. **Trait Detection** (Task 3.3):
   - Create new module `python/analytics/trait_detector.py`
   - Call from schedule generation, not volume calculation

4. **Followup Limits** (Task 3.4):
   - Integrate with existing orchestration pipeline
   - Use `OptimizedVolumeResult.caption_warnings` for limit warnings

---

## A/B TEST SPECIFICATIONS

### Task 3.7: Volume A/B Testing Framework

**Agent:** python-pro, data-analyst
**Complexity:** MEDIUM
**File:** `/python/analytics/volume_ab_test.py`

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Literal
from datetime import date
import math

@dataclass
class VolumeABTest:
    """A/B test configuration for volume optimization experiments.

    Provides structured test specification with power analysis
    for determining minimum sample sizes.
    """
    test_id: str
    hypothesis: str
    control_config: Dict[str, any]
    treatment_config: Dict[str, any]
    primary_metric: str
    secondary_metrics: List[str] = field(default_factory=list)
    min_sample_size: int = 0  # Calculated via power analysis
    duration_days: int = 14
    confidence_level: float = 0.95
    statistical_power: float = 0.80
    minimum_detectable_effect: float = 0.10  # 10% lift
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Literal['draft', 'running', 'completed', 'paused'] = 'draft'

    def __post_init__(self):
        """Calculate minimum sample size using power analysis."""
        if self.min_sample_size == 0:
            self.min_sample_size = self._calculate_min_sample_size()

    def _calculate_min_sample_size(self) -> int:
        """
        Calculate minimum sample size per group using power analysis.

        Uses formula: n = 2 * ((z_alpha + z_beta) / delta)^2 * sigma^2

        Where:
        - z_alpha: Z-score for confidence level (e.g., 1.96 for 95%)
        - z_beta: Z-score for statistical power (e.g., 0.84 for 80%)
        - delta: Minimum detectable effect size
        - sigma: Standard deviation (assumed normalized to 1)
        """
        from scipy import stats

        alpha = 1 - self.confidence_level
        z_alpha = stats.norm.ppf(1 - alpha / 2)  # Two-tailed
        z_beta = stats.norm.ppf(self.statistical_power)

        # Assuming unit variance for normalized metrics
        sigma = 1.0
        delta = self.minimum_detectable_effect

        n = 2 * ((z_alpha + z_beta) ** 2) * (sigma ** 2) / (delta ** 2)

        return math.ceil(n)


# Example test configurations
VOLUME_AB_TESTS = {
    'bump_ratio_2x_vs_3x': VolumeABTest(
        test_id='bump_ratio_2x_vs_3x',
        hypothesis='3x bump ratio increases daily revenue by 10% compared to 2x',
        control_config={'bump_to_ppv_ratio': 2.0},
        treatment_config={'bump_to_ppv_ratio': 3.0},
        primary_metric='daily_revenue',
        secondary_metrics=['view_rate', 'unsubscribe_rate', 'engagement_rate'],
        minimum_detectable_effect=0.10,
        duration_days=14
    ),
    'dow_distribution_uniform_vs_weighted': VolumeABTest(
        test_id='dow_distribution_uniform_vs_weighted',
        hypothesis='DOW-weighted distribution improves weekly revenue by 15%',
        control_config={'dow_weighting': 'uniform'},
        treatment_config={'dow_weighting': 'performance_based'},
        primary_metric='weekly_revenue',
        secondary_metrics=['message_fatigue_score', 'weekend_engagement'],
        minimum_detectable_effect=0.15,
        duration_days=21
    ),
    'campaign_frequency_high_vs_standard': VolumeABTest(
        test_id='campaign_frequency_high_vs_standard',
        hypothesis='Increasing campaigns from 5/month to 15/month improves revenue by 25%',
        control_config={'monthly_campaigns': 5},
        treatment_config={'monthly_campaigns': 15},
        primary_metric='monthly_revenue',
        secondary_metrics=['campaign_fatigue', 'unsubscribe_rate'],
        minimum_detectable_effect=0.25,
        duration_days=30
    ),
}


def validate_test_completion(test: VolumeABTest, control_n: int, treatment_n: int) -> Dict:
    """
    Validate if A/B test has sufficient data for statistical analysis.

    Args:
        test: VolumeABTest configuration
        control_n: Number of observations in control group
        treatment_n: Number of observations in treatment group

    Returns:
        Dict with validation status and recommendations
    """
    min_n = test.min_sample_size

    control_sufficient = control_n >= min_n
    treatment_sufficient = treatment_n >= min_n

    if control_sufficient and treatment_sufficient:
        return {
            'is_sufficient': True,
            'message': f'Test has sufficient data (control: {control_n}, treatment: {treatment_n}, min: {min_n})',
            'recommendation': 'Proceed with statistical analysis'
        }

    shortfall_control = max(0, min_n - control_n)
    shortfall_treatment = max(0, min_n - treatment_n)

    return {
        'is_sufficient': False,
        'control_n': control_n,
        'treatment_n': treatment_n,
        'min_required': min_n,
        'shortfall_control': shortfall_control,
        'shortfall_treatment': shortfall_treatment,
        'message': f'Insufficient data. Need {shortfall_control + shortfall_treatment} more observations.',
        'recommendation': f'Continue test for ~{max(shortfall_control, shortfall_treatment) // 10 + 1} more days'
    }
```

---

## DASHBOARD KPI DEFINITIONS

### Task 3.8: Volume Optimization Dashboard Metrics

**Agent:** data-analyst
**Complexity:** LOW
**File:** `/docs/metrics/VOLUME_DASHBOARD_KPIS.md` (and SQL views)

| Metric | Definition | Formula | Target | Alert Threshold |
|--------|------------|---------|--------|-----------------|
| `campaign_frequency_adherence` | % of campaigns meeting frequency rules | `(compliant_campaigns / total_campaigns) * 100` | >= 90% | < 75% |
| `bump_ratio_compliance` | % of days with bump:PPV ratio in expected range | `(compliant_days / total_days) * 100` | >= 85% | < 70% |
| `volume_prediction_mape` | Mean Absolute Percentage Error of volume predictions | `AVG(ABS(predicted - actual) / actual) * 100` | < 15% | > 25% |
| `trait_recommendation_lift` | Revenue lift from trait-based recommendations | `(trait_revenue - baseline_revenue) / baseline_revenue * 100` | > 20% | < 5% |
| `followup_limit_utilization` | % of daily followup capacity used | `AVG(daily_followups / 4) * 100` | 75-100% | < 50% |
| `weekly_limit_violations` | Count of VIP/Snapchat weekly limit violations | `COUNT(violations)` | 0 | > 0 |
| `game_type_revenue_variance` | Coefficient of variation in game type earnings | `STDDEV(earnings) / AVG(earnings)` | < 0.50 | > 0.75 |
| `bayesian_estimate_accuracy` | Accuracy of Bayesian game estimates vs actuals | `1 - AVG(ABS(estimate - actual) / actual)` | > 85% | < 70% |

### SQL View Definitions

```sql
-- Campaign Frequency Adherence
CREATE VIEW v_campaign_frequency_adherence AS
SELECT
    creator_id,
    campaign_type,
    COUNT(*) as total_campaigns,
    SUM(CASE WHEN is_compliant = 1 THEN 1 ELSE 0 END) as compliant_campaigns,
    ROUND(SUM(CASE WHEN is_compliant = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as adherence_pct
FROM campaign_frequency_audit
WHERE created_at >= DATE('now', '-30 days')
GROUP BY creator_id, campaign_type;

-- Volume Prediction MAPE
CREATE VIEW v_volume_prediction_accuracy AS
SELECT
    creator_id,
    week_start,
    predicted_revenue_per_day,
    actual_revenue_per_day,
    ABS(predicted_revenue_per_day - actual_revenue_per_day) * 100.0 /
        NULLIF(actual_revenue_per_day, 0) as absolute_percentage_error
FROM volume_predictions vp
JOIN weekly_actuals wa ON vp.prediction_id = wa.prediction_id
WHERE wa.is_complete = 1;

-- Bump Ratio Compliance
CREATE VIEW v_bump_ratio_compliance AS
SELECT
    creator_id,
    schedule_date,
    ppv_count,
    bump_count,
    CASE
        WHEN ppv_count = 0 THEN NULL
        ELSE bump_count * 1.0 / ppv_count
    END as actual_ratio,
    expected_min_ratio,
    expected_max_ratio,
    CASE
        WHEN ppv_count = 0 THEN 0
        WHEN (bump_count * 1.0 / ppv_count) BETWEEN expected_min_ratio AND expected_max_ratio THEN 1
        ELSE 0
    END as is_compliant
FROM daily_schedule_audit;
```

---

## SUCCESS CRITERIA

### Must Pass Before Wave Exit

- [ ] **Page Type Volume Matrix**
  - Porno Commercial at low tier receives 5-8 bumps (1.67x-4.0x ratio range, avg 2.67x)
  - All 6 page type combinations produce correct targets
  - Bump ratio validation working

- [ ] **Campaign Frequency**
  - Validator detects under-scheduling
  - 14-20 campaigns/month target enforced
  - Spacing rules validated

- [ ] **Data-Driven Triggers**
  - Trait detection identifies shared characteristics
  - Volume increases applied for 60%+ shared traits
  - Recommendations generated with multipliers

- [ ] **Followup Limits**
  - 4/day max enforced
  - Priority-based removal working
  - Low-priority followups removed first

- [ ] **Weekly Limits**
  - VIP limited to 1/week
  - Snapchat bundle limited to 1/week
  - Warnings generated for violations

- [ ] **Game Tracking**
  - Performance recorded by sub-type
  - Recommendations based on history
  - Low performers identified for avoidance

---

## QUALITY GATES

### 1. Unit Test Coverage
- [ ] All volume calculations tested
- [ ] All edge cases covered (0 fans, max fans)
- [ ] Campaign frequency tests for various schedules

### 2. Integration Test
- [ ] Generate schedules for all 6 page types
- [ ] Verify correct bump ratios
- [ ] Verify campaign frequency targets met

### 3. Performance Test
- [ ] Volume calculation <20ms
- [ ] Trait detection <100ms for 1000 items

---

## WAVE EXIT CHECKLIST

Before proceeding to Wave 4:

- [ ] All 7 gaps implemented
- [ ] All tasks have code committed
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Code review completed
- [ ] Database migrations applied
- [ ] Documentation updated

---

**Wave 3 Ready for Execution (after Wave 2)**
