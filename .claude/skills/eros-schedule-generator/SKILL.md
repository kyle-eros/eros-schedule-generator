---
name: eros-schedule-generator
description: Generate optimized weekly schedules for OnlyFans creators. Use PROACTIVELY when user mentions scheduling, generating schedules, content planning, PPV optimization, or revenue maximization. Automatically invoked for schedule-related requests.
version: 3.0.0
model: sonnet
triggers:
  - generate a schedule
  - create weekly schedule
  - schedule for
  - PPV schedule
  - content schedule
  - revenue optimization
  - engagement schedule
  - retention schedule
---

# EROS Schedule Generator

Orchestrates the 22-type schedule generation system for OnlyFans creators, producing optimized weekly schedules that balance revenue generation, audience engagement, and subscriber retention through a **14-phase pipeline with 24 specialized agents**.

## Parameters

### Core Parameters

| Parameter | Required | Type | Default | Description |
|-----------|----------|------|---------|-------------|
| `creator_id` | Yes | string | - | Creator identifier or page_name (e.g., "alexia", "creator_123") |
| `week_start` | No | string (ISO date) | Next Monday | Schedule start date in YYYY-MM-DD format |
| `send_types` | No | array[string] | All applicable | Specific send_type_keys to include (e.g., ["ppv_unlock", "bump_normal"]) |
| `include_retention` | No | boolean | true (paid pages) | Include retention category items |
| `include_followups` | No | boolean | true | Auto-generate followup items for PPV sends |
| `category_focus` | No | string | balanced | Primary category: "revenue", "engagement", "retention", or "balanced" |

### Batch Mode Parameters (v3.0 NEW)

| Parameter | Required | Type | Default | Description |
|-----------|----------|------|---------|-------------|
| `batch_mode` | No | boolean | false | Enable batch processing for multiple creators |
| `creators` | Conditional | string[] | - | List of creator IDs (required if batch_mode=true) |
| `parallelism` | No | integer | 3 | Max concurrent creator schedules (1-5) |
| `fail_fast` | No | boolean | false | Abort batch on first failure |
| `timeout_per_creator` | No | integer | 300 | Seconds before timeout per creator |

**Batch Mode Examples:**

```
# Batch mode via natural language
"Generate schedules for alexia, chloe_wildd, and shelby in batch"

# Batch mode with explicit parameters
{
  "batch_mode": true,
  "creators": ["alexia", "chloe_wildd", "shelby_d_vip"],
  "parallelism": 4,
  "week_start": "2025-12-23"
}
```

**Batch Mode Constraints:**
- Maximum 10 creators per batch
- Parallelism should not exceed 50% of connection pool size (recommended max: 5)
- All creators use the same `week_start` date
- Each creator runs the full 14-phase pipeline independently

## Agent Loading & Discovery

The skill orchestrates **24 specialized agents** across **14 phases**. Agents are loaded from `.claude/agents/` and executed in phase order.

### Agent Inventory

| Phase | Agent | Model | Role | Key Responsibility |
|-------|-------|-------|------|-------------------|
| 0 | preflight-checker | haiku | Validation | BLOCK if creator data missing |
| 0.5 | retention-risk-analyzer | opus | Analysis | Churn risk by subscriber segment |
| 1 | performance-analyst | opus | Analysis | Saturation/opportunity, volume triggers |
| 2 | send-type-allocator | sonnet | Allocation | Daily 22-type distribution with DOW |
| 2.5 | variety-enforcer | sonnet | Enforcement | 12+ unique types, diversity score |
| 2.75 | content-performance-predictor | opus | Prediction | ML-style RPS/conversion predictions |
| 3 | caption-selection-pro | sonnet | Selection | PPV-first, vault-compliant, AVOID exclusion |
| 3 | attention-quality-scorer | sonnet | Scoring | Hook strength, CTA effectiveness (parallel) |
| 4 | timing-optimizer | sonnet | Timing | Optimal hours with jitter, spacing |
| 5 | followup-generator | haiku | Generation | Auto PPV followups (80% rate) |
| 5.5 | followup-timing-optimizer | haiku | Timing | Dynamic followup delay (20-60 min) |
| 6 | authenticity-engine | sonnet | Validation | Structure variation (NO caption mods) |
| 7 | schedule-assembler | haiku | Assembly | Final schedule structure |
| 7.5 | funnel-flow-optimizer | sonnet | Optimization | Engagement → conversion flow |
| 8 | revenue-optimizer | sonnet | Pricing | Tier multipliers, positioning |
| 8.5 | ppv-price-optimizer | opus | Pricing | Dynamic PPV with predictions |
| 8.5 | schedule-critic | opus | Review | Strategic issues, BLOCK authority |
| 9 | quality-validator | opus | Validation | FINAL GATE, Four-Layer Defense |
| 9 | quality-validator-expert | opus | Validation | EXPERT consensus parallel with quality-validator |
| 9.5 | anomaly-detector | haiku | Detection | Statistical anomaly flagging |
| ∥ | ab-testing-orchestrator | opus | Experiments | A/B test management (parallel) |
| ⟳ | win-back-specialist | sonnet | Retention | Lapsed subscriber campaigns (async) |
| ◎ | caption-optimizer | sonnet | Utility | On-demand caption improvement |

### Model Distribution

| Model | Count | Purpose |
|-------|-------|---------|
| **haiku** | 6 | Fast, lightweight on-path agents |
| **sonnet** | 10 | Complex logic, validation, optimization |
| **opus** | 8 | Strategic decisions, predictions, critique |

### BLOCKING Agents

Three agents can halt pipeline execution:

| Agent | Phase | Blocks When | Action Required |
|-------|-------|-------------|-----------------|
| preflight-checker | 0 | Creator data missing/invalid | Fix data, re-run |
| schedule-critic | 8.5 | Strategic issues detected | Manual review |
| quality-validator | 9 | Vault/AVOID violations | Fix violations |

### Agent File Requirements

Each agent file in `.claude/agents/` must include:

```yaml
---
name: agent-name
description: Clear single-line description
model: haiku|sonnet|opus
tools:
  - mcp__eros-db__tool_name
---
```

### Execution Patterns (v3.0)

- **Sequential**: Most agents run in phase order (Phases 1-7)
- **Parallel Phase 0+0.5**: preflight-checker and retention-risk-analyzer run simultaneously (IMPLEMENTED)
- **Parallel Phase 3**: attention-quality-scorer runs alongside caption-selection-pro (IMPLEMENTED)
- **Parallel Phase 8-8.5**: revenue-optimizer and ppv-price-optimizer run in parallel, then schedule-critic reviews (IMPLEMENTED)
- **Parallel Phase 9+9.5**: quality-validator and anomaly-detector run simultaneously (IMPLEMENTED)
- **Async**: win-back-specialist runs independently during Phase 6
- **Conditional**: ab-testing-orchestrator only runs when experiments are active

#### Phase 8-8.5 Three-Way Parallel Pattern
```
┌─────────────────────────────────────────────────────────────┐
│ Phase 8-8.5: PARALLEL PRICING + SEQUENTIAL REVIEW           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐     ┌─────────────────┐               │
│  │ revenue-        │     │ ppv-price-      │  ←─ PARALLEL  │
│  │ optimizer       │     │ optimizer       │               │
│  │ (sonnet)        │     │ (opus)          │               │
│  └────────┬────────┘     └────────┬────────┘               │
│           │                       │                         │
│           └───────────┬───────────┘                        │
│                       ▼                                     │
│             ┌─────────────────┐                             │
│             │ schedule-critic │  ←─ SEQUENTIAL (reviews    │
│             │ (opus) [BLOCK]  │      combined output)       │
│             └─────────────────┘                             │
└─────────────────────────────────────────────────────────────┘
Expected Savings: ~15-20% Phase 8 latency
```

#### Phase 9+9.5 Parallel Validation Pattern
```
┌─────────────────────────────────────────────────────────────┐
│ Phase 9+9.5: PARALLEL VALIDATION                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐     ┌─────────────────────┐       │
│  │ quality-validator   │     │ anomaly-detector    │       │
│  │ (opus) [FINAL GATE] │     │ (haiku)             │       │
│  └──────────┬──────────┘     └──────────┬──────────┘       │
│             │                           │                   │
│             └───────────┬───────────────┘                  │
│                         ▼                                   │
│               ┌─────────────────┐                           │
│               │  Merge Results  │                           │
│               │ ValidationCert  │                           │
│               │ + AnomalyReport │                           │
│               └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
Expected Savings: ~10% Phase 9 latency
```

## Context Caching Architecture (v3.0)

At pipeline start, Phase 0 pre-fetches and caches frequently-used data to eliminate redundant MCP calls across phases.

### PipelineContext Initialization

```python
# At pipeline start (before Phase 0)
context = await create_pipeline_context(creator_id, week_start)

# All downstream phases receive the shared context
preflight_result = await preflight_checker.execute(context)
performance_result = await performance_analyst.execute(context)
# ... all phases use same context object
```

### Pre-Cached Data (3 Batches)

| Batch | Data | MCP Tool | Consumers |
|-------|------|----------|-----------|
| 1 | creator_profile | get_creator_profile() | All phases |
| 1 | volume_config | get_volume_config() | Phases 1-9 |
| 1 | performance_trends | get_performance_trends() | Phases 1, 2, 8, 9 |
| 2 | send_types | get_send_types() | Phases 2, 4, 7.5 |
| 2 | vault_availability | get_vault_availability() | Phases 0, 3, 9 |
| 2 | best_timing | get_best_timing() | Phases 4, 5.5, 7.5 |
| 3 | persona_profile | get_persona_profile() | Phases 3, 6, 9 |
| 3 | content_type_rankings | get_content_type_rankings() | Phases 1, 3, 8, 9 |
| 3 | active_volume_triggers | get_active_volume_triggers() | Phases 1, 2, 5 |

**Expected Impact**: 55% reduction in MCP calls, 40% latency improvement

See: [REFERENCE/CONTEXT_CACHING.md](./REFERENCE/CONTEXT_CACHING.md)

## Quick-Start Walkthrough

### Minimal Schedule Generation

**Step 1**: Invoke the skill
```
"Generate a schedule for alexia"
```

**Step 2**: Pipeline executes automatically
```
Phase 0:   preflight-checker validates creator exists
Phase 1:   performance-analyst loads volume configuration
Phase 2:   send-type-allocator distributes 22 types across 7 days
Phase 2.5: variety-enforcer ensures 12+ unique types
Phase 3:   caption-selection-pro assigns vault-compliant captions
Phase 4:   timing-optimizer calculates optimal posting times
Phase 5:   followup-generator creates PPV followups (80% rate)
Phase 6:   authenticity-engine adds organic variation
Phase 7:   schedule-assembler merges all components
Phase 8:   revenue-optimizer applies pricing
Phase 9:   quality-validator performs final gate validation
```

**Step 3**: Review output
```json
{
  "status": "APPROVED",
  "quality_score": 92,
  "total_items": 78,
  "unique_send_types": 15,
  "template_id": 456,
  "validation_certificate": {...}
}
```

### Custom Focus Options

```
"Generate a revenue-focused schedule for alexia starting 2025-12-23"
```

Adjusts category allocation:
- Revenue focus: 60% revenue, 25% engagement, 15% retention
- Engagement focus: 30% revenue, 55% engagement, 15% retention
- Retention focus: 25% revenue, 35% engagement, 40% retention
```

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Creator not found" | Invalid creator_id | Run `get_active_creators()` to list valid IDs |
| "Preflight blocked" | Missing vault_matrix | Sync vault via `vault_matrix_sync.py` |
| "Low caption coverage" | Freshness shortage | Wait 30 days or import new captions |
| "Diversity failed" | <12 unique types | Review allocation rules, expand send type variety |
| "Schedule rejected" | quality_score < 70 | Check quality-validator output for specific violations |
| "AVOID violation" | Content in AVOID tier | Exclude content type, update rankings |

## Validation Certificates

After Phase 9, quality-validator produces a `ValidationCertificate`:

```json
{
  "certificate_version": "3.1",
  "creator_id": "alexia",
  "validation_timestamp": "2025-12-20T10:00:00Z",
  "validation_status": "APPROVED",
  "quality_score": 92,
  "items_validated": 78,
  "violations_found": {
    "vault_violations": 0,
    "avoid_violations": 0,
    "soft_warnings": 2
  },
  "checks_performed": {
    "vault_compliance": true,
    "avoid_exclusion": true,
    "freshness_check": true,
    "diversity_check": true
  },
  "certificate_signature": "sha256:abc123..."
}
```

### Certificate Status Meanings

| Status | Action | Can Save |
|--------|--------|----------|
| `APPROVED` | Proceed immediately | YES |
| `NEEDS_REVIEW` | Manual review recommended | YES (with warning) |
| `REJECTED` | Fix violations first | NO |

## 14-Phase Pipeline

### Pre-Pipeline Validation (BLOCKING)
- **Phase 0: preflight-checker** (haiku) - Verify creator readiness, BLOCK if critical data missing
- **Phase 0.5: retention-risk-analyzer** (opus) - Churn risk analysis, retention strategy recommendations

### Core Pipeline
1. **Phase 1: performance-analyst** (opus) - Analyze trends, detect volume triggers, save performance signals
2. **Phase 2: send-type-allocator** (sonnet) - Distribute 22 send types across daily slots with variety
3. **Phase 2.5: variety-enforcer** (sonnet) - Validate 12+ unique types, enforce diversity rules
4. **Phase 2.75: content-performance-predictor** (opus) - ML-style RPS/conversion predictions
5. **Phase 3: caption-selection-pro** (sonnet) - PPV-first, earnings-based selection with vault compliance
6. **Phase 4: timing-optimizer** (sonnet) - Optimal posting times with jitter and type-specific rules
7. **Phase 5: followup-generator** (haiku) - Auto-generate PPV followups (80% rate, max 5/day)
8. **Phase 5.5: followup-timing-optimizer** (haiku) - Dynamic followup delay optimization (20-60 min)
9. **Phase 6: authenticity-engine** (sonnet) - Validate structure for organic variation (ZERO caption modification)
10. **Phase 7: schedule-assembler** (haiku) - Merge upstream outputs into final schedule structure
11. **Phase 7.5: funnel-flow-optimizer** (sonnet) - Engagement-to-conversion flow optimization
12. **Phase 8: revenue-optimizer** (sonnet) - Price/positioning optimization with tier multipliers
13. **Phase 8.5: ppv-price-optimizer** (opus) - Dynamic PPV pricing using predictions
14. **Phase 8.5: schedule-critic** (opus) - Strategic review with BLOCK authority (CRITICAL)
15. **Phase 9: quality-validator** (opus) - Four-Layer Defense FINAL GATE with HARD rejection
16. **Phase 9.5: anomaly-detector** (haiku) - Statistical anomaly detection before save

### Parallel/Async Agents
- **ab-testing-orchestrator** (opus) - A/B experiment management (runs in parallel)
- **win-back-specialist** (sonnet) - Win-back campaign generation (async, Phase 6)
- **attention-quality-scorer** (sonnet) - Caption attention scoring (Phase 3 parallel)
- **caption-optimizer** (sonnet) - On-demand caption optimization (utility)

## Critical Requirements

- **MCP Tool Invocation**: Every data point MUST originate from MCP tool responses (no hallucinated data)
- **Vault Matrix Compliance**: Only captions matching creator's `vault_matrix` content types allowed (HARD GATE)
- **AVOID Tier Exclusion**: Content types in AVOID tier are NEVER scheduled (HARD GATE)
- **Send Type Diversity**: Minimum 12 unique send_type_keys required across weekly schedule (enforced by variety-enforcer)
- **Page Type Restrictions**: Retention types only for `paid` pages, type-specific exclusions enforced
- **PPV Unlock Limits**: Maximum 4 `ppv_unlock` sends per day (primary revenue driver)
- **PPV Followup Limits**: Maximum 5 `ppv_followup` sends per day (scales at 80% of PPV count)
- **Weekly Caps**: VIP program and Snapchat bundle limited to 1 per week
- **Caption Freshness**: Minimum 30-day threshold for caption reuse (can relax to 20 days if pool limited)
- **Four-Layer Defense**: All schedules pass vault/AVOID validation at MCP, caption-selection-pro, quality-validator, and save_schedule levels

## MCP Tool Requirements by Phase

| Phase | Agent | Required Tools |
|-------|-------|----------------|
| 0 | preflight-checker | `get_creator_profile`, `get_vault_availability`, `get_persona_profile`, `get_top_captions`, `execute_query` |
| 0.5 | retention-risk-analyzer | `get_creator_profile`, `get_performance_trends`, `get_churn_risk_scores`, `get_content_type_rankings` |
| 1 | performance-analyst | `get_creator_profile`, `get_performance_trends`, `get_content_type_rankings`, `get_volume_config`, `get_active_volume_triggers`, `save_volume_triggers` |
| 2 | send-type-allocator | `get_volume_config`, `get_send_types`, `get_creator_profile` |
| 2.5 | variety-enforcer | `get_send_types`, `get_content_type_rankings`, `get_volume_config` |
| 2.75 | content-performance-predictor | `get_caption_predictions`, `save_caption_prediction`, `get_prediction_weights`, `get_content_type_rankings` |
| 3 | caption-selection-pro | `get_vault_availability`, `get_content_type_rankings`, `get_content_type_earnings_ranking`, `get_top_captions_by_earnings`, `get_persona_profile` |
| 4 | timing-optimizer | `get_best_timing`, `get_send_type_details` |
| 5 | followup-generator | `get_volume_config`, `get_send_type_details`, `get_send_type_captions` |
| 5.5 | followup-timing-optimizer | `get_best_timing`, `get_performance_trends` |
| 6 | authenticity-engine | `get_persona_profile` |
| 7 | schedule-assembler | `save_schedule` |
| 7.5 | funnel-flow-optimizer | `get_send_types`, `get_best_timing`, `get_volume_config` |
| 8 | revenue-optimizer | `get_creator_profile`, `get_performance_trends`, `get_content_type_rankings` |
| 8.5a | ppv-price-optimizer | `get_creator_profile`, `get_content_type_rankings`, `get_caption_predictions`, `get_performance_trends` |
| 8.5b | schedule-critic | `get_creator_profile`, `get_performance_trends`, `get_content_type_rankings`, `get_volume_config`, `get_active_experiments` |
| 9 | quality-validator | `get_vault_availability`, `get_content_type_rankings`, `get_creator_profile`, `get_persona_profile`, `get_volume_config` |
| 9.5 | anomaly-detector | `get_performance_trends`, `get_volume_config` |
| - | ab-testing-orchestrator | `get_active_experiments`, `save_experiment_results`, `update_experiment_allocation` |
| - | win-back-specialist | `get_win_back_candidates`, `get_churn_risk_scores`, `get_persona_profile` |
| - | attention-quality-scorer | `get_caption_attention_scores`, `get_attention_metrics`, `get_top_captions` |

## Volume Optimization v3.0

Dynamic volume calculation integrates 10 optimization modules:

1. **Base Tier Calculation** - Fan count-based foundation volumes
2. **Multi-Horizon Fusion** - 7d/14d/30d saturation/opportunity analysis
3. **Confidence Dampening** - Reduce volumes when confidence is low (<0.6)
4. **DOW Distribution** - Day-of-week adjustments via `weekly_distribution` field
5. **Elasticity Bounds** - Prevent extreme fluctuations
6. **Content Weighting** - Performance-based content type allocation
7. **Caption Pool Check** - Verify sufficient captions available
8. **Prediction Tracking** - Audit trail for predictions
9. **Bump Multiplier** - Content category-based engagement scaling (lifestyle 1.0x, softcore 1.5x, amateur 2.0x, explicit 2.67x)
10. **Followup Scaling** - PPV-proportional followup calculation (80% rate, max 5/day)

**Key Fields**: `revenue_per_day`, `engagement_per_day`, `retention_per_day`, `weekly_distribution`, `content_allocations`, `confidence_score`, `bump_multiplier`, `followup_volume_scaled`

## Volume Triggers

Performance-based triggers automatically adjust content type allocations:

| Trigger Type | Detection Criteria | Adjustment |
|--------------|-------------------|------------|
| HIGH_PERFORMER | RPS > $200, conversion > 6% | +20% |
| TRENDING_UP | WoW RPS increase > 15% | +10% |
| EMERGING_WINNER | RPS > $150, used < 3x in 30d | +30% |
| SATURATING | Declining engagement 3+ days | -15% |
| AUDIENCE_FATIGUE | Open rate decline > 10% over 7d | -25% |

**Lifecycle**: Detected by performance-analyst → Saved via `save_volume_triggers()` → Applied during `get_volume_config()` → Auto-expire when `expires_at` passes

## Confidence-Based Behavior

`confidence_score` (0.0-1.0) from `get_volume_config()` adjusts validation and allocation:

| Level | Range | Action |
|-------|-------|--------|
| VERY_LOW | 0.0-0.39 | Flag for manual review, use fallback defaults |
| LOW | 0.4-0.59 | Apply conservative adjustments, add warnings |
| MODERATE | 0.6-0.79 | Standard allocation, proceed with validation |
| HIGH | 0.8-1.0 | Full optimization applied confidently |

**Adjustments**: Lower confidence = relaxed freshness thresholds, reduced type diversity requirements, conservative volume multipliers

## Error Handling

**Common Issues**:
- **No captions available**: Relax `min_freshness` threshold from 30 → 20 days, fallback to `get_top_captions()`
- **Volume exceeded**: Reduce category focus intensity, apply conservative multipliers
- **Timing conflict**: Increase minimum spacing, spread items to adjacent days
- **Missing content type**: Flag for content creation, skip items requiring unavailable media
- **Low confidence (<0.4)**: Flag schedule for manual review, use tier-based fallback defaults

**Graceful Degradation**: If caption freshness low, use top performers with warning. If vault incomplete, skip items requiring unavailable content. If timing constrained, spread items to adjacent days.

## Validation Checkpoints

Before finalizing schedule:
- All items have valid `send_type_key` from 22-type taxonomy
- Caption types match send type requirements
- Timing respects spacing rules (min 30 min between sends)
- Daily item counts within `volume_config` limits
- Revenue items placed at peak performance times
- Follow-ups generated for all eligible PPV sends
- No duplicate captions within same week
- Vault contains required content types
- **ZERO vault or AVOID tier violations** (HARD GATE)
- Minimum 12 unique send_type_keys achieved (variety-enforcer)
- No send type exceeds 20% of weekly total (variety-enforcer)
- No content type exceeds 25% of PPV slots (variety-enforcer)
- Funnel flow optimization verified (funnel-flow-optimizer)
- Schedule-critic APPROVE status (no BLOCK)
- Anomaly detection passes (no ERROR-level anomalies)

## Output Format

**Schedule Summary**:
```json
{
  "template_id": 456,
  "creator_id": "alexia",
  "week_start": "2025-01-20",
  "total_items": 42,
  "breakdown": {
    "revenue": 14,
    "engagement": 21,
    "retention": 7
  },
  "daily_counts": {
    "2025-01-20": 6,
    "2025-01-21": 7,
    "...": "..."
  },
  "validation": {
    "status": "APPROVED",
    "quality_score": 92,
    "warnings": [],
    "recommendations": []
  }
}
```

## See Also

- **[ORCHESTRATION.md](./ORCHESTRATION.md)** - Complete 14-phase pipeline execution flow with 22-agent coordination
- **[REFERENCE/SEND_TYPE_TAXONOMY.md](./REFERENCE/SEND_TYPE_TAXONOMY.md)** - 22 send types with constraints and usage rules
- **[REFERENCE/VALIDATION_RULES.md](./REFERENCE/VALIDATION_RULES.md)** - Four-Layer Defense architecture and rejection criteria
- **[REFERENCE/CONFIDENCE_LEVELS.md](./REFERENCE/CONFIDENCE_LEVELS.md)** - Standardized confidence thresholds and behavior adjustments
- **[REFERENCE/TOOL_PATTERNS.md](./REFERENCE/TOOL_PATTERNS.md)** - MCP tool invocation patterns and common sequences
- **[REFERENCE/BATCH_PROCESSING.md](./REFERENCE/BATCH_PROCESSING.md)** - Batch mode for multi-creator scheduling with parallel execution
- **[REFERENCE/CONTEXT_CACHING.md](./REFERENCE/CONTEXT_CACHING.md)** - Pipeline context caching architecture and pre-fetch batching
- **[/docs/SCHEDULE_GENERATOR_BLUEPRINT.md](../../../docs/SCHEDULE_GENERATOR_BLUEPRINT.md)** - Full system architecture
- **[/docs/SEND_TYPE_REFERENCE.md](../../../docs/SEND_TYPE_REFERENCE.md)** - Detailed send type profiles
