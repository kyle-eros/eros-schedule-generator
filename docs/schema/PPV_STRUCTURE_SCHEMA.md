# PPV Structure and Advanced Schema Reference

Version: 1.0.0
Last Updated: 2025-12-17

## Overview

This document details the advanced database tables supporting PPV structure validation, rotation state management, circuit breaker patterns, volume prediction/learning, and operational tracking within the EROS Schedule Generator system.

---

## Table of Contents

1. [PPV Structure Validation](#ppv-structure-validation)
2. [Rotation State Management](#rotation-state-management)
3. [Circuit Breaker Pattern](#circuit-breaker-pattern)
4. [Volume Prediction System](#volume-prediction-system)
5. [Operational Tracking Tables](#operational-tracking-tables)
6. [Views Reference](#views-reference)

---

## PPV Structure Validation

The PPV Structure Validator (`python/quality/ppv_structure.py`) enforces proven high-converting caption structures. While there is no dedicated `ppv_structure_rotation_state` table, the validation patterns are tracked through related tables.

### PPV Caption Structure Requirements

The validator enforces three distinct structures:

| Structure Type | Elements Required | Minimum Score |
|---------------|-------------------|---------------|
| Winner PPV | Clickbait, Exclusivity, Value Anchor, CTA | 3/4 (75%) |
| Bundle PPV | Itemization, Value Anchor, Urgency | 2/3 (50%) |
| Wall Campaign | Clickbait Title, Body with Setting, Short Wrap | 2/3 (67%) |

### Related Table: `ppv_followup_tracking`

Tracks PPV followup message timing to ensure optimal re-engagement windows.

```sql
CREATE TABLE ppv_followup_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    parent_ppv_id TEXT NOT NULL,
    parent_time TEXT NOT NULL,                -- ISO 8601 datetime
    followup_time TEXT NOT NULL,              -- ISO 8601 datetime
    gap_minutes REAL NOT NULL,
    ppv_type TEXT NOT NULL,
    is_optimal_window INTEGER DEFAULT 0,      -- 1 if 15-45 min
    created_at TEXT DEFAULT (datetime('now'))
);
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `creator_id` | TEXT | Creator identifier |
| `parent_ppv_id` | TEXT | Reference to original PPV message |
| `parent_time` | TEXT | When the original PPV was sent |
| `followup_time` | TEXT | When the followup was scheduled |
| `gap_minutes` | REAL | Minutes between parent and followup |
| `ppv_type` | TEXT | Type of PPV (winner, bundle, etc.) |
| `is_optimal_window` | INTEGER | 1 if gap is in optimal 15-45 minute range |
| `created_at` | TEXT | Record creation timestamp |

**Indexes:**
- `idx_followup_creator` - Lookup by creator
- `idx_followup_gap` - Analysis by gap timing

**Optimal Window**: The system targets a 15-45 minute delay between PPV and followup for maximum conversion.

---

## Rotation State Management

### `creator_rotation_state`

Manages per-creator content rotation patterns to prevent subscriber fatigue and maintain engagement variety.

```sql
CREATE TABLE creator_rotation_state (
    creator_id TEXT PRIMARY KEY,
    rotation_pattern TEXT NOT NULL,           -- JSON stored as TEXT
    pattern_start_date TEXT NOT NULL,         -- ISO 8601 datetime
    days_on_pattern INTEGER DEFAULT 0,
    current_state TEXT DEFAULT 'initializing', -- RotationState enum
    updated_at TEXT DEFAULT (datetime('now'))
);
```

| Column | Type | Description |
|--------|------|-------------|
| `creator_id` | TEXT | Primary key, links to creators table |
| `rotation_pattern` | TEXT | JSON object defining content rotation rules |
| `pattern_start_date` | TEXT | When the current pattern began |
| `days_on_pattern` | INTEGER | Days since pattern started |
| `current_state` | TEXT | Current rotation state (initializing, active, paused, rotating) |
| `updated_at` | TEXT | Last modification timestamp |

**Indexes:**
- `idx_rotation_state_updated` - For finding stale patterns
- `idx_rotation_current_state` - Filter by state

**Rotation Pattern JSON Structure:**
```json
{
  "content_types": ["b_g", "solo", "toy"],
  "sequence_type": "weighted_random",
  "weights": {"b_g": 0.5, "solo": 0.3, "toy": 0.2},
  "cycle_length_days": 7,
  "avoid_repeat_within": 2
}
```

**Valid States:**
- `initializing` - Pattern being set up
- `active` - Pattern in use
- `paused` - Temporarily suspended
- `rotating` - Transitioning to new pattern

---

## Circuit Breaker Pattern

### `circuit_breaker_state`

Implements the circuit breaker reliability pattern for external service calls and critical operations.

```sql
CREATE TABLE circuit_breaker_state (
    name TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'closed',     -- closed, open, half_open
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    last_failure_time TEXT,                   -- ISO 8601 datetime
    last_success_time TEXT,                   -- ISO 8601 datetime
    last_state_change TEXT,                   -- ISO 8601 datetime
    updated_at TEXT DEFAULT (datetime('now'))
);
```

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT | Circuit breaker identifier (primary key) |
| `state` | TEXT | Current state: closed, open, or half_open |
| `failure_count` | INTEGER | Consecutive failures since last success |
| `success_count` | INTEGER | Consecutive successes (for half_open testing) |
| `last_failure_time` | TEXT | Timestamp of most recent failure |
| `last_success_time` | TEXT | Timestamp of most recent success |
| `last_state_change` | TEXT | When state last transitioned |
| `updated_at` | TEXT | Last record modification |

**Circuit Breaker States:**

| State | Behavior |
|-------|----------|
| `closed` | Normal operation, requests pass through |
| `open` | Failures exceeded threshold, requests fail fast |
| `half_open` | Testing recovery, limited requests allowed |

**Usage Example:**
```python
# Check if operation should proceed
if get_circuit_state("caption_fetch") == "open":
    return fallback_caption()

# After successful operation
record_circuit_success("caption_fetch")

# After failed operation
record_circuit_failure("caption_fetch")
```

---

## Volume Prediction System

### `volume_predictions`

Stores volume assignment predictions with actual outcome tracking for continuous learning.

```sql
CREATE TABLE volume_predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    predicted_at TEXT DEFAULT (datetime('now')),

    -- Prediction inputs
    input_fan_count INTEGER,
    input_page_type TEXT,
    input_saturation REAL,
    input_opportunity REAL,

    -- Predictions
    predicted_tier TEXT,
    predicted_revenue_per_day INTEGER,
    predicted_engagement_per_day INTEGER,
    predicted_retention_per_day INTEGER,
    predicted_weekly_revenue REAL,
    predicted_weekly_messages INTEGER,

    -- Linked schedule
    schedule_template_id INTEGER,
    week_start_date TEXT,

    -- Actual outcomes (filled after execution)
    actual_total_revenue REAL,
    actual_messages_sent INTEGER,
    actual_avg_rps REAL,
    outcome_measured INTEGER DEFAULT 0,
    outcome_measured_at TEXT,

    -- Prediction accuracy
    revenue_prediction_error_pct REAL,
    volume_prediction_error_pct REAL,

    algorithm_version TEXT DEFAULT '2.0',

    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,
    FOREIGN KEY (schedule_template_id) REFERENCES schedule_templates(template_id) ON DELETE SET NULL
);
```

**Key Indexes:**
- `idx_vp_unmeasured` - Find predictions needing outcome measurement
- `idx_vp_creator_accuracy` - Analyze per-creator prediction accuracy
- `idx_vp_schedule_template` - Link predictions to schedules
- `idx_vp_week_start` - Query by schedule week

### `volume_calculation_log`

Detailed audit log of every volume calculation performed.

```sql
CREATE TABLE volume_calculation_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    calculated_at TEXT DEFAULT (datetime('now')),

    -- Input metrics
    fan_count INTEGER,
    page_type TEXT CHECK (page_type IN ('paid', 'free')),
    saturation_score REAL,
    opportunity_score REAL,

    -- Calculated outputs
    tier TEXT CHECK (tier IN ('low', 'mid', 'high', 'ultra')),
    revenue_per_day INTEGER,
    engagement_per_day INTEGER,
    retention_per_day INTEGER,

    schedule_template_id INTEGER,

    -- Algorithm metadata
    data_source TEXT DEFAULT 'dynamic',
    calculation_version TEXT DEFAULT '1.0',
    confidence_score REAL,
    caption_constrained INTEGER DEFAULT 0,
    message_count_analyzed INTEGER,
    multi_horizon_used INTEGER DEFAULT 0,
    dow_adjusted INTEGER DEFAULT 0,
    elasticity_capped INTEGER DEFAULT 0,
    notes TEXT,

    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,
    FOREIGN KEY (schedule_template_id) REFERENCES schedule_templates(template_id) ON DELETE SET NULL
);
```

| Column | Description |
|--------|-------------|
| `data_source` | Where data came from: dynamic, cached_tracking, calculated_on_demand, fallback |
| `confidence_score` | Algorithm confidence (0.0-1.0) |
| `caption_constrained` | Was volume reduced due to limited captions? |
| `multi_horizon_used` | Used 7d/14d/30d fusion? |
| `dow_adjusted` | Applied day-of-week multipliers? |
| `elasticity_capped` | Hit elasticity bounds? |

### `volume_adjustment_outcomes`

Records actual performance outcomes to enable learning from predictions.

```sql
CREATE TABLE volume_adjustment_outcomes (
    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id INTEGER NOT NULL,
    creator_id TEXT NOT NULL,
    measured_at TEXT DEFAULT (datetime('now')),
    measurement_period TEXT DEFAULT '14d',

    -- Input metrics at calculation time
    input_saturation_score REAL,
    input_opportunity_score REAL,
    input_tier TEXT,
    input_revenue_per_day INTEGER,
    input_engagement_per_day INTEGER,
    input_retention_per_day INTEGER,

    -- Outcome metrics after execution
    outcome_saturation_score REAL,
    outcome_opportunity_score REAL,
    outcome_revenue_per_send REAL,
    outcome_total_revenue REAL,
    outcome_view_rate REAL,
    outcome_purchase_rate REAL,
    outcome_messages_sent INTEGER,

    -- Deltas
    saturation_delta REAL,
    opportunity_delta REAL,
    revenue_per_send_change_pct REAL,

    -- Classification
    outcome_classification TEXT,  -- improved, degraded, neutral
    learning_signal REAL,         -- -1.0 to 1.0

    applied_to_learning INTEGER DEFAULT 0,
    applied_at TEXT,

    FOREIGN KEY (log_id) REFERENCES volume_calculation_log(log_id) ON DELETE CASCADE,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);
```

**Learning Signal Values:**
- `-1.0` to `-0.5`: Strong signal to reduce volume
- `-0.5` to `0.0`: Slight reduction suggested
- `0.0`: Neutral, maintain current approach
- `0.0` to `0.5`: Slight increase suggested
- `0.5` to `1.0`: Strong signal to increase volume

---

## Operational Tracking Tables

### `saga_execution_log`

Tracks distributed transaction (saga) execution for complex multi-step operations.

```sql
CREATE TABLE saga_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saga_id TEXT NOT NULL,                    -- UUID for saga instance
    creator_id TEXT NOT NULL,
    status TEXT NOT NULL,                     -- pending, in_progress, completed, compensating, failed, rolled_back
    steps_completed TEXT,                     -- JSON array
    failed_step TEXT,
    error_message TEXT,
    compensation_errors TEXT,                 -- JSON array
    execution_time_ms REAL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

**Saga Statuses:**
| Status | Description |
|--------|-------------|
| `pending` | Saga created, not yet started |
| `in_progress` | Steps being executed |
| `completed` | All steps succeeded |
| `compensating` | Failure occurred, running compensations |
| `failed` | Compensation completed after failure |
| `rolled_back` | Manual rollback performed |

### `timing_idempotency`

Ensures timing operations are idempotent (safe to retry).

```sql
CREATE TABLE timing_idempotency (
    operation_key TEXT PRIMARY KEY,
    operation_name TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    result TEXT,                              -- JSON stored as TEXT
    executed_at TEXT NOT NULL,                -- ISO 8601 datetime
    expires_at TEXT NOT NULL                  -- ISO 8601 datetime
);
```

**Purpose:** Prevents duplicate schedule generation for the same creator/date combination. Before executing a timing operation, the system checks if an identical operation was recently completed.

### `timing_operation_log`

Audit trail of all timing-related operations.

---

## Views Reference

### `v_circuit_breaker_health`

Monitoring view for circuit breaker status with health metrics.

```sql
CREATE VIEW v_circuit_breaker_health AS
SELECT
    name,
    state,
    failure_count,
    success_count,
    CASE
        WHEN failure_count + success_count > 0
        THEN ROUND(CAST(success_count AS REAL) / (failure_count + success_count) * 100, 2)
        ELSE 100.0
    END as success_rate_pct,
    last_failure_time,
    last_success_time,
    CAST((julianday('now') - julianday(last_state_change)) * 24 * 60 AS INTEGER) as minutes_in_state
FROM circuit_breaker_state;
```

**Usage:**
```sql
SELECT * FROM v_circuit_breaker_health
WHERE state != 'closed' OR success_rate_pct < 95;
```

### `v_prediction_accuracy`

Analyzes prediction accuracy across creators and time periods.

### `v_active_rotation_states`

Shows currently active rotation patterns.

---

## Foreign Key Relationships

```
creators
    |
    +-- creator_rotation_state (creator_id)
    +-- ppv_followup_tracking (creator_id)
    +-- volume_predictions (creator_id)
    +-- volume_calculation_log (creator_id)
    +-- volume_adjustment_outcomes (creator_id)
    +-- saga_execution_log (creator_id)

schedule_templates
    |
    +-- volume_predictions (schedule_template_id)
    +-- volume_calculation_log (schedule_template_id)

volume_calculation_log
    |
    +-- volume_adjustment_outcomes (log_id)
```

---

## Best Practices

### Querying PPV Followup Data

```sql
-- Find creators with suboptimal followup timing
SELECT
    creator_id,
    AVG(gap_minutes) as avg_gap,
    SUM(CASE WHEN is_optimal_window = 0 THEN 1 ELSE 0 END) as suboptimal_count
FROM ppv_followup_tracking
WHERE created_at >= date('now', '-7 days')
GROUP BY creator_id
HAVING suboptimal_count > 5;
```

### Monitoring Volume Prediction Accuracy

```sql
-- Creators where predictions consistently miss
SELECT
    creator_id,
    AVG(ABS(revenue_prediction_error_pct)) as avg_error,
    COUNT(*) as predictions
FROM volume_predictions
WHERE outcome_measured = 1
GROUP BY creator_id
HAVING avg_error > 25 AND predictions >= 3;
```

### Circuit Breaker Health Check

```sql
-- All unhealthy circuit breakers
SELECT * FROM v_circuit_breaker_health
WHERE state = 'open'
   OR (state = 'half_open' AND minutes_in_state > 30)
   OR success_rate_pct < 80;
```

---

## Related Documentation

- `python/quality/ppv_structure.py` - PPV Structure Validator implementation
- `docs/SCHEDULE_GENERATOR_BLUEPRINT.md` - Full system architecture
- `docs/DYNAMIC_VOLUME_MIGRATION.md` - Volume system details
- `mcp/eros_db_server.py` - MCP database tools
