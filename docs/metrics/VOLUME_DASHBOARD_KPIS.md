# Volume Optimization Dashboard KPIs

## Overview

This document defines the Key Performance Indicators (KPIs) for monitoring the EROS Schedule Generator's volume optimization system. These metrics track algorithm accuracy, constraint compliance, and revenue impact across the 22-type send taxonomy.

**Version**: 1.0.0
**Last Updated**: 2025-12-17
**Owner**: EROS Analytics Team

---

## KPI Definitions

| Metric Name | Definition | Formula | Target | Alert Threshold |
|-------------|------------|---------|--------|-----------------|
| `campaign_frequency_adherence` | Percentage of scheduled campaigns that comply with send type frequency rules (max_per_day, max_per_week, min_hours_between) | `(compliant_campaigns / total_campaigns) * 100` | >= 90% | < 75% |
| `bump_ratio_compliance` | Percentage of scheduled days where the bump-to-PPV ratio falls within acceptable bounds (1:1 to 2:1) | `(compliant_days / total_scheduled_days) * 100` | >= 85% | < 70% |
| `volume_prediction_mape` | Mean Absolute Percentage Error between predicted weekly revenue and actual revenue outcomes | `AVG(ABS(actual - predicted) / actual) * 100` | < 15% | > 25% |
| `trait_recommendation_lift` | Revenue lift achieved by following content type recommendations from top_content_types analysis | `((recommended_revenue - baseline_revenue) / baseline_revenue) * 100` | > 20% | < 5% |
| `followup_limit_utilization` | Percentage of daily PPV followup capacity (max 4) actually scheduled and executed | `(actual_followups / max_followups) * 100` | 75-100% | < 50% |
| `weekly_limit_violations` | Count of VIP program and Snapchat bundle sends exceeding the 1-per-week limit | `COUNT(violations)` | 0 | > 0 |
| `game_type_revenue_variance` | Coefficient of Variation in earnings across different game post types, measuring consistency | `STDDEV(earnings) / AVG(earnings)` | < 0.50 | > 0.75 |
| `bayesian_estimate_accuracy` | Accuracy of Bayesian performance estimates compared to actual observed outcomes | `1 - AVG(ABS(estimate - actual) / actual)` | > 85% | < 70% |

---

## Detailed Metric Specifications

### 1. Campaign Frequency Adherence

**Purpose**: Ensures the schedule generator respects send type constraints defined in the `send_types` table.

**Business Impact**: Violating frequency rules can lead to subscriber fatigue, increased unsubscribe rates, and platform policy violations.

**Calculation Logic**:
- For each send type, check `max_per_day`, `max_per_week`, and `min_hours_between` constraints
- A campaign is compliant if ALL applicable constraints are satisfied
- Excludes draft schedules; only measures approved/queued/completed schedules

**Data Sources**:
- `schedule_items` - Scheduled send instances
- `send_types` - Frequency constraints per send type
- `schedule_templates` - Schedule metadata and status

**Refresh Frequency**: Daily

---

### 2. Bump Ratio Compliance

**Purpose**: Validates that engagement (bump) sends maintain proper proportion to revenue (PPV) sends.

**Business Impact**: Imbalanced ratios can either over-monetize (causing subscriber churn) or under-monetize (leaving revenue on the table).

**Calculation Logic**:
- For each creator-day combination, calculate total bumps and total PPVs
- Compliant if ratio is between 1.0 and 2.0 (inclusive)
- Days with zero PPVs are excluded from calculation

**Acceptable Ratio Range**: 1:1 to 2:1 (bumps:PPVs)

**Data Sources**:
- `schedule_items` - Daily send counts by type
- `send_types` - Category classification (revenue vs engagement)

**Refresh Frequency**: Daily

---

### 3. Volume Prediction MAPE

**Purpose**: Measures the accuracy of the volume optimization algorithm's revenue predictions.

**Business Impact**: Accurate predictions enable better resource allocation, realistic goal setting, and improved scheduling decisions.

**Calculation Logic**:
```
MAPE = (1/n) * SUM(|Actual - Predicted| / Actual) * 100
```

**Exclusions**:
- Predictions where `outcome_measured = 0` (not yet evaluated)
- Predictions older than 90 days
- Predictions with zero actual revenue (division by zero)

**Data Sources**:
- `volume_predictions` - Predicted and actual revenue values

**Refresh Frequency**: Weekly (after outcome measurement)

---

### 4. Trait Recommendation Lift

**Purpose**: Quantifies the revenue benefit of using TOP-tier content types vs. baseline performance.

**Business Impact**: Validates the effectiveness of the content type ranking system and guides content strategy.

**Calculation Logic**:
```
Lift = ((Revenue from TOP content) - (Baseline Revenue)) / (Baseline Revenue) * 100
```

**Baseline Definition**: Average revenue per send across all content types for the creator

**Data Sources**:
- `top_content_types` - Performance tier classifications
- `mass_messages` - Actual earnings by content type
- `schedule_items` - Scheduled content type assignments

**Refresh Frequency**: Weekly

---

### 5. Followup Limit Utilization

**Purpose**: Tracks whether the system is fully leveraging the 4-per-day PPV followup opportunity.

**Business Impact**: PPV followups have high conversion rates; underutilization represents missed revenue.

**Calculation Logic**:
```
Utilization = (Actual Followups Sent / 4) * 100
```

**Constraints**:
- Maximum 4 PPV followups per day per creator
- Minimum 20-minute delay after parent PPV
- Only counts `ppv_followup` send type

**Data Sources**:
- `schedule_items` - Followup sends (where `send_type_key = 'ppv_followup'`)
- `ppv_followup_tracking` - Actual followup execution data

**Refresh Frequency**: Daily

---

### 6. Weekly Limit Violations

**Purpose**: Detects any breach of the strict weekly limits on VIP program and Snapchat bundle sends.

**Business Impact**: These are premium send types that lose effectiveness with overuse; violations indicate algorithm bugs.

**Calculation Logic**:
```
Violations = COUNT of weeks where:
  - vip_program sends > 1, OR
  - snapchat_bundle sends > 1
```

**Zero Tolerance**: Any violation requires immediate investigation and remediation.

**Data Sources**:
- `schedule_items` - Weekly send counts by type
- `send_types` - `max_per_week` constraints

**Refresh Frequency**: Daily (rolling 7-day window)

---

### 7. Game Type Revenue Variance

**Purpose**: Measures consistency in earnings across different game post configurations.

**Business Impact**: High variance suggests some game types significantly outperform others, indicating optimization opportunities.

**Calculation Logic**:
```
CV = Standard Deviation(earnings) / Mean(earnings)
```

**Interpretation**:
- CV < 0.50: Consistent performance across game types
- CV 0.50-0.75: Moderate variance, review underperformers
- CV > 0.75: High variance, investigate root causes

**Data Sources**:
- `mass_messages` - Earnings where content involves game posts
- `game_wheel_configs` - Game type configurations

**Refresh Frequency**: Weekly

---

### 8. Bayesian Estimate Accuracy

**Purpose**: Validates the accuracy of Bayesian performance estimates used in caption and content selection.

**Business Impact**: Bayesian estimates drive content prioritization; inaccuracy degrades recommendation quality.

**Calculation Logic**:
```
Accuracy = 1 - MAPE(bayesian_estimate, actual_performance)
```

Where MAPE is calculated over all captions/content with sufficient observations (n >= 5).

**Data Sources**:
- `caption_bank` - Performance scores (Bayesian estimates)
- `caption_creator_performance` - Actual performance outcomes
- `mass_messages` - Ground truth earnings data

**Refresh Frequency**: Weekly

---

## SQL View Definitions

The following views support dashboard metric calculation. Full SQL implementations are available in:

```
sql/views/volume_dashboard_views.sql
```

### v_campaign_frequency_adherence

Calculates per-creator, per-send-type compliance with frequency rules.

```sql
-- See sql/views/volume_dashboard_views.sql for full implementation
-- Returns: creator_id, send_type_key, total_sends, violations, compliance_rate
```

### v_volume_prediction_accuracy

Aggregates prediction accuracy metrics from the volume_predictions table.

```sql
-- See sql/views/volume_dashboard_views.sql for full implementation
-- Returns: creator_id, predictions_count, avg_mape, accuracy_trend
```

### v_bump_ratio_compliance

Evaluates daily bump-to-PPV ratios against acceptable thresholds.

```sql
-- See sql/views/volume_dashboard_views.sql for full implementation
-- Returns: creator_id, scheduled_date, bump_count, ppv_count, ratio, is_compliant
```

---

## Dashboard Integration

### Recommended Visualization Layout

| Section | Metrics | Chart Type |
|---------|---------|------------|
| Compliance Overview | campaign_frequency_adherence, bump_ratio_compliance, weekly_limit_violations | Gauge + Alert Cards |
| Prediction Accuracy | volume_prediction_mape, bayesian_estimate_accuracy | Time Series Line Chart |
| Revenue Impact | trait_recommendation_lift, game_type_revenue_variance | Bar Chart + Trend |
| Utilization | followup_limit_utilization | Stacked Area Chart |

### Alert Configuration

| Metric | Warning Level | Critical Level | Notification Channel |
|--------|---------------|----------------|---------------------|
| campaign_frequency_adherence | < 85% | < 75% | Slack #eros-alerts |
| bump_ratio_compliance | < 80% | < 70% | Slack #eros-alerts |
| volume_prediction_mape | > 20% | > 25% | Email + Slack |
| trait_recommendation_lift | < 10% | < 5% | Weekly Report |
| followup_limit_utilization | < 60% | < 50% | Slack #eros-alerts |
| weekly_limit_violations | > 0 | > 0 | Immediate Page |
| game_type_revenue_variance | > 0.60 | > 0.75 | Weekly Report |
| bayesian_estimate_accuracy | < 80% | < 70% | Email + Slack |

---

## Data Quality Requirements

### Minimum Data Thresholds

For reliable metric calculation, ensure the following minimums:

| Metric | Minimum Sample Size | Lookback Period |
|--------|---------------------|-----------------|
| campaign_frequency_adherence | 50 scheduled items | 7 days |
| bump_ratio_compliance | 7 creator-days | 7 days |
| volume_prediction_mape | 10 measured predictions | 30 days |
| trait_recommendation_lift | 100 sends per tier | 30 days |
| followup_limit_utilization | 14 days of data | 14 days |
| weekly_limit_violations | 1 complete week | 7 days |
| game_type_revenue_variance | 20 game posts | 30 days |
| bayesian_estimate_accuracy | 50 captions with n>=5 | 30 days |

### Data Freshness Requirements

| Data Source | Maximum Staleness | Refresh Trigger |
|-------------|-------------------|-----------------|
| schedule_items | 1 hour | On schedule generation |
| volume_predictions | 24 hours | Daily batch |
| mass_messages | 6 hours | API sync |
| top_content_types | 7 days | Weekly analysis |

---

## Metric Relationships

### Leading Indicators
- `campaign_frequency_adherence` - Predicts subscriber satisfaction
- `bayesian_estimate_accuracy` - Predicts recommendation quality

### Lagging Indicators
- `volume_prediction_mape` - Confirms algorithm effectiveness
- `trait_recommendation_lift` - Confirms content strategy value

### Diagnostic Indicators
- `weekly_limit_violations` - Identifies system bugs
- `game_type_revenue_variance` - Identifies optimization opportunities

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **MAPE** | Mean Absolute Percentage Error - average of absolute percentage errors |
| **CV** | Coefficient of Variation - ratio of standard deviation to mean |
| **Bump** | Engagement-focused message designed to drive interaction |
| **PPV** | Pay-Per-View content requiring purchase to unlock |
| **Bayesian Estimate** | Statistical estimate incorporating prior beliefs with observed data |
| **Send Type** | One of 22 categorized message types in the EROS taxonomy |

---

## Appendix B: Related Documentation

- [Send Type Reference](../SEND_TYPE_REFERENCE.md) - Complete send type taxonomy
- [Schedule Generator Blueprint](../SCHEDULE_GENERATOR_BLUEPRINT.md) - System architecture
- [Volume Optimization Algorithm](../algorithms/VOLUME_OPTIMIZATION.md) - Algorithm details

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-17 | EROS Team | Initial release with 8 core KPIs |
