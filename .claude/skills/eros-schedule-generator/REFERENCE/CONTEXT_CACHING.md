# Context Caching Architecture
> CANONICAL REFERENCE - v1.1.0

## Overview

The Phase 0 Context Loader pre-fetches and caches frequently-used data at pipeline start,
eliminating redundant MCP calls across phases and reducing latency by ~50%.

## Pre-Cached Data

### Batch 1 (No Dependencies)
| Data | MCP Tool | Cached For | Consumers |
|------|----------|------------|-----------|
| creator_profile | get_creator_profile() | Full pipeline | Phases 0-9 |
| volume_config | get_volume_config() | Full pipeline | Phases 1-9 |
| performance_trends | get_performance_trends() | Full pipeline | Phases 1, 2, 8, 9 |

### Batch 2 (Depends on page_type from Batch 1)
| Data | MCP Tool | Cached For | Consumers |
|------|----------|------------|-----------|
| send_types | get_send_types() | Full pipeline | Phases 2, 4, 7.5 |
| vault_availability | get_vault_availability() | Full pipeline | Phases 0, 3, 9 |
| best_timing | get_best_timing() | Full pipeline | Phases 4, 5.5, 7.5 |

### Batch 3 (Depends on creator_id)
| Data | MCP Tool | Cached For | Consumers |
|------|----------|------------|-----------|
| persona_profile | get_persona_profile() | Full pipeline | Phases 3, 6, 9 |
| content_type_rankings | get_content_type_rankings() | Full pipeline | Phases 1, 3, 8, 9 |
| active_volume_triggers | get_active_volume_triggers() | 30 minutes | Phases 1, 2, 5 |

## PipelineContext Object

```typescript
interface PipelineContext {
  // Identity
  creator_id: string;
  week_start: string;
  cache_timestamp: string;

  // Batch 1 (pre-fetched immediately)
  creator_profile: CreatorProfile;
  volume_config: OptimizedVolumeResult;
  performance_trends: PerformanceTrends;

  // Batch 2 (pre-fetched after page_type known)
  send_types: SendType[];
  vault_availability: VaultEntry[];
  best_timing: TimingData;

  // Batch 3 (pre-fetched in parallel with Batch 2)
  persona_profile: PersonaProfile;
  content_type_rankings: ContentTypeRanking[];
  active_volume_triggers: VolumeTrigger[];

  // Cache metadata
  cache_valid_until: string;  // TTL = 2 hours
  cache_version: "1.0";
}
```

## Cache Invalidation

| Scenario | Action |
|----------|--------|
| Schedule generation complete | Clear cache |
| Cache age > 2 hours | Re-fetch all |
| Volume triggers expire | Re-fetch triggers only |
| Manual invalidation | Clear cache |

## Usage Pattern

### Phase 0 (Preflight Checker)
```python
# At pipeline start, create shared context
context = await create_pipeline_context(creator_id, week_start)

# Pass context to all downstream phases
preflight_result = await preflight_checker.execute(context)
if preflight_result.status == "BLOCK":
    return preflight_result

# Continue with cached context
performance_result = await performance_analyst.execute(context)
# ... all phases receive same context object
```

### Any Phase (Accessing Cached Data)
```python
def execute(self, context: PipelineContext):
    # Use cached data - NO MCP calls needed
    creator = context.creator_profile
    volume = context.volume_config
    rankings = context.content_type_rankings

    # Only call MCP for NEW data not in cache
    new_data = mcp.get_send_type_captions(...)
```

## Expected Impact

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| MCP calls per schedule | ~45 | ~20 | -55% |
| get_volume_config() calls | 5-7 | 1 | -86% |
| Pipeline latency | ~30s | ~18s | -40% |
| Token usage (context) | 8,000 | 4,500 | -44% |

## Implementation Status

- [x] REFERENCE documentation created
- [x] Update ORCHESTRATION.md with context passing pattern
- [x] Update agent files to reference context object (v3.0.0 - 2025-12-20)
- [x] Update SKILL.md with context initialization pattern (v3.0.0 - 2025-12-20)
- [ ] Implement context loader in Python orchestration layer (Future: Python runtime)

**Note**: All documentation-level implementation is complete. The Python runtime implementation will be added when the Python orchestration layer is built.
