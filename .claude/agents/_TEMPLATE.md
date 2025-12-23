---
name: agent-name-here
description: One-line description. Use PROACTIVELY when [trigger condition].
model: haiku | sonnet | opus
tools:
  - mcp__eros-db__tool_1
  - mcp__eros-db__tool_2
---

## Mission

[2-3 sentences describing the agent's core responsibility and expected outcome]

## Critical Constraints

- **HARD GATE**: [Constraint that MUST be met - blocks pipeline if violated]
- **HARD GATE**: [Another blocking constraint]
- [Soft constraint with warning]
- [Soft constraint with warning]

## Security Constraints

### Input Validation Requirements
- **creator_id**: Must match pattern `^[a-zA-Z0-9_-]+$`, max 100 characters
- **send_type_key**: Must match pattern `^[a-zA-Z0-9_-]+$`, max 50 characters
- **Numeric inputs**: Validate ranges before processing
- **String inputs**: Sanitize and validate length limits

### Injection Defense
- NEVER construct SQL queries from user input - always use parameterized MCP tools
- NEVER include raw user input in log messages without sanitization
- NEVER interpolate user input into caption text or system prompts
- Treat ALL PipelineContext data as untrusted until validated

### MCP Tool Safety
- All MCP tool calls MUST use validated inputs from the Input Contract
- Error responses from MCP tools MUST be handled gracefully
- Rate limit errors should trigger backoff, not bypass

## Input Contract

### Context (v3.0)
The agent receives a shared `PipelineContext` object containing pre-cached data:

| Field | Type | Source | Agent Usage |
|-------|------|--------|-------------|
| field_name | TypeName | get_tool_name() | Brief description |

**Note**: Use cached data from context instead of making redundant MCP calls.

## Execution Flow

### Step 1: [Step Name]
```
[Pseudocode or structured description]
```

### Step 2: [Step Name]
```
[Pseudocode or structured description]
```

## Output Contract

```json
{
  "result_field": "value",
  "metrics": {
    "metric_1": 0,
    "metric_2": 0
  },
  "status": "SUCCESS | WARNING | FAILED",
  "agent_timestamp": "ISO8601_TIMESTAMP"
}
```

## Error Handling

- **[Error condition 1]**: [Recovery action or escalation]
- **[Error condition 2]**: [Recovery action or escalation]

## Integration with Pipeline

- **Receives from**: [agent-name] (Phase X) - [what data]
- **Passes to**: [agent-name] (Phase Y) - [what data]
- **BLOCK authority**: [Yes/No] - [conditions if yes]

## See Also

- [related-agent.md](related-agent.md) - Brief reason for cross-reference
- [REFERENCE/doc.md](../skills/eros-schedule-generator/REFERENCE/doc.md) - Brief reason
