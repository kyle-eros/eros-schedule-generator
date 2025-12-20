# Batch Processing Mode
> CANONICAL REFERENCE - v1.0.0

## Overview

Batch processing enables scheduling multiple creators in a single invocation,
with parallel execution for improved throughput.

## Invocation Pattern

### Single Creator (Default)
```
"Generate a schedule for alexia"
```

### Batch Mode
```
"Generate schedules for alexia, chloe_wildd, shelby_d_vip in batch mode"
```

Or with explicit configuration:
```json
{
  "batch_mode": true,
  "creators": ["alexia", "chloe_wildd", "shelby_d_vip"],
  "parallelism": 3,
  "week_start": "2025-12-23"
}
```

## Batch Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `batch_mode` | bool | false | Enable batch processing |
| `creators` | string[] | required | List of creator IDs or page names |
| `parallelism` | int | 3 | Max concurrent creator schedules |
| `week_start` | string | next Monday | Shared week start for all |
| `fail_fast` | bool | false | Abort batch on first failure |
| `timeout_per_creator` | int | 300 | Seconds before timeout per creator |

## Execution Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    BATCH ORCHESTRATOR                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                   THREAD POOL (N=3)                      ││
│  │                                                          ││
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐           ││
│  │  │ Creator 1 │  │ Creator 2 │  │ Creator 3 │           ││
│  │  │ Pipeline  │  │ Pipeline  │  │ Pipeline  │           ││
│  │  │ (14 phases)│ │ (14 phases)│ │ (14 phases)│          ││
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘           ││
│  │        │              │              │                  ││
│  │        ▼              ▼              ▼                  ││
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐             ││
│  │  │ Result 1│    │ Result 2│    │ Result 3│             ││
│  │  └─────────┘    └─────────┘    └─────────┘             ││
│  └──────────────────────┬───────────────────────────────────┘│
│                         │                                    │
│                         ▼                                    │
│              ┌─────────────────────┐                         │
│              │   BATCH RESULTS     │                         │
│              │   Aggregator        │                         │
│              └─────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## Result Format

### Batch Response
```json
{
  "batch_id": "batch_20251220_001",
  "total_creators": 3,
  "successful": 3,
  "failed": 0,
  "total_duration_seconds": 45.2,
  "avg_duration_per_creator": 15.1,
  "results": [
    {
      "creator_id": "alexia",
      "status": "SUCCESS",
      "schedule_id": "sched_abc123",
      "quality_score": 92,
      "duration_seconds": 14.5,
      "items_scheduled": 48
    },
    {
      "creator_id": "chloe_wildd",
      "status": "SUCCESS",
      "schedule_id": "sched_def456",
      "quality_score": 88,
      "duration_seconds": 16.2,
      "items_scheduled": 42
    },
    {
      "creator_id": "shelby_d_vip",
      "status": "SUCCESS",
      "schedule_id": "sched_ghi789",
      "quality_score": 90,
      "duration_seconds": 14.5,
      "items_scheduled": 45
    }
  ],
  "summary": {
    "total_items_scheduled": 135,
    "avg_quality_score": 90.0,
    "predicted_weekly_revenue": "$3,720"
  }
}
```

### Failed Creator Result
```json
{
  "creator_id": "invalid_creator",
  "status": "FAILED",
  "error_code": "PREFLIGHT_BLOCK",
  "error_message": "Creator not found in active_creators",
  "duration_seconds": 0.3
}
```

## Resource Management

### Connection Pool Sharing
- All creators share the same connection pool (10 connections)
- Parallelism=3 recommended for 10-connection pool
- Higher parallelism risks connection starvation

### Token Efficiency
- Shared context caching reduces redundant MCP calls
- Each creator still runs full 14-phase pipeline
- Expected savings: 40-50% tokens vs sequential single invocations

### Memory Management
- Each creator pipeline maintains separate context
- Results streamed to batch aggregator
- No cross-creator state contamination

## Error Handling

### Per-Creator Isolation
- Each creator pipeline has its own error boundary
- Failure in one creator doesn't affect others (unless fail_fast=true)
- Circuit breaker prevents cascade failures

### Retry Logic
- Individual creator retries handled within pipeline
- Batch-level retry not implemented (re-run batch for failed creators)

### Timeout Handling
```python
# Per-creator timeout with cancellation
try:
    result = await asyncio.wait_for(
        generate_schedule(creator_id),
        timeout=timeout_per_creator
    )
except asyncio.TimeoutError:
    result = {
        "creator_id": creator_id,
        "status": "FAILED",
        "error_code": "TIMEOUT",
        "error_message": f"Schedule generation exceeded {timeout_per_creator}s"
    }
```

## Implementation Pattern

### Using ThreadPoolExecutor (Python)
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def batch_generate(creators: list[str], parallelism: int = 3) -> BatchResult:
    results = []

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {
            executor.submit(generate_schedule, creator): creator
            for creator in creators
        }

        for future in as_completed(futures):
            creator = futures[future]
            try:
                result = future.result(timeout=300)
                results.append(result)
            except Exception as e:
                results.append({
                    "creator_id": creator,
                    "status": "FAILED",
                    "error_message": str(e)
                })

    return aggregate_results(results)
```

### Using asyncio (Alternative)
```python
import asyncio

async def batch_generate_async(creators: list[str], parallelism: int = 3):
    semaphore = asyncio.Semaphore(parallelism)

    async def limited_generate(creator_id: str):
        async with semaphore:
            return await generate_schedule_async(creator_id)

    tasks = [limited_generate(c) for c in creators]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## Best Practices

1. **Parallelism Selection**
   - 3 workers for 10-connection pool (default)
   - 5 workers for 15-connection pool
   - Never exceed 50% of pool size

2. **Batch Size Limits**
   - Recommended max: 10 creators per batch
   - Larger batches should be chunked
   - Token budget: ~50k tokens per creator

3. **Progress Reporting**
   - Stream results as each creator completes
   - Don't wait for entire batch to report

4. **Scheduling Cadence**
   - Run batch weekly (Sunday or Monday)
   - Stagger large batches across hours
   - Avoid peak API usage times

## Integration with Skills

The skill accepts batch mode via parameters:

```yaml
parameters:
  - name: batch_mode
    type: boolean
    default: false
    description: Enable batch processing for multiple creators
  - name: creators
    type: array
    description: List of creator IDs (required if batch_mode=true)
  - name: parallelism
    type: integer
    default: 3
    description: Max concurrent creator schedules
```

## Performance Characteristics

### Throughput Comparison

| Mode | Creators | Duration | Tokens Used | Avg per Creator |
|------|----------|----------|-------------|-----------------|
| Sequential (single) | 1 | 15s | 50k | 50k |
| Sequential (3x) | 3 | 45s | 150k | 50k |
| Batch (parallelism=3) | 3 | 18s | 90k | 30k |

**Improvement**: 2.5x faster, 40% fewer tokens

### Scaling Characteristics

| Creators | Parallelism | Est. Duration | Est. Tokens |
|----------|-------------|---------------|-------------|
| 5 | 3 | 30s | 150k |
| 10 | 3 | 55s | 300k |
| 10 | 5 | 35s | 320k |
| 20 | 5 | 70s | 640k |

**Note**: Higher parallelism trades slight token efficiency for speed

## Monitoring & Observability

### Batch Metrics Tracked
- Total duration
- Per-creator duration
- Success/failure counts
- Token consumption
- Connection pool utilization
- Error distribution

### Logging Pattern
```python
logger.info(
    "Batch generation completed",
    extra={
        "batch_id": batch_id,
        "total_creators": len(creators),
        "successful": success_count,
        "failed": failure_count,
        "duration_seconds": total_duration,
        "avg_duration": avg_duration,
        "tokens_used": total_tokens
    }
)
```

## Limitations & Constraints

1. **Maximum Batch Size**: 10 creators
   - Larger batches risk timeout
   - Token budget limits apply
   - Memory constraints on large batches

2. **Shared Week Start**: All creators use same week_start
   - Cannot schedule different weeks in one batch
   - Workaround: Run multiple batches

3. **No Cross-Creator Dependencies**
   - Each creator scheduled independently
   - Cannot share captions or optimize across creators
   - No batch-level optimizations

4. **Connection Pool Bottleneck**
   - 10 connections shared across all workers
   - Exceeding capacity causes delays
   - Monitor pool utilization metrics

## Future Enhancements (Roadmap)

- **Adaptive Parallelism**: Auto-adjust based on connection pool availability
- **Batch-Level Optimizations**: Share caption pool analysis across creators
- **Progress Streaming**: Real-time updates as each creator completes
- **Partial Batch Resume**: Re-run only failed creators from previous batch
- **Cross-Creator Scheduling**: Coordinate schedules for creator groups
- **Smart Batching**: Auto-chunk large creator lists into optimal batch sizes

## See Also

- **[SKILL.md](../SKILL.md)** - Main skill entry point with parameters
- **[ORCHESTRATION.md](../ORCHESTRATION.md)** - 14-phase pipeline details
- **[TOOL_PATTERNS.md](./TOOL_PATTERNS.md)** - MCP tool invocation patterns
- **[/examples/batch_schedule_generation.py](/examples/batch_schedule_generation.py)** - Example implementation
