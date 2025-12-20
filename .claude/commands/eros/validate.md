---
name: eros-validate
model: sonnet
description: Validate captions for character length, PPV structure, emoji blending, and price-length interaction. Use when reviewing caption quality after schedule generation.
allowed-tools:
  - mcp__eros-db__get_top_captions
  - mcp__eros-db__get_persona_profile
  - mcp__eros-db__get_send_type_details
  - mcp__eros-db__execute_query
argument-hint: <creator_id_or_name> [validation_type] (e.g., "grace_bennett", "all", "ppv_structure")
---

# Validate Captions Command

Validate caption quality and schedule item compliance against EROS quality criteria.

## Arguments

### Required Parameters

- `$1`: **creator_id_or_name** (required) - Creator identifier or page_name
  - Accepts: numeric ID (`123`), string ID (`creator_123`), or page_name (`grace_bennett`)
  - Case-insensitive for page_name lookups

### Optional Parameters

- `$2`: **validation_type** - Specific validation to run
  - Valid values: `caption_quality`, `ppv_structure`, `emoji_blending`, `persona_match`, `freshness`, `all`
  - Default: `all`

## Validation Rules

| Parameter | Type | Required | Validation |
|-----------|------|----------|------------|
| creator_id_or_name | string/int | Yes | Must exist in creators table |
| validation_type | enum | No | Must be one of: `caption_quality`, `ppv_structure`, `emoji_blending`, `persona_match`, `freshness`, `all` |

## Validation Types

### caption_quality
Character length and structural formatting validation.

| Send Category | Min Chars | Max Chars | Notes |
|---------------|-----------|-----------|-------|
| PPV (ppv_unlock, ppv_wall, bundle) | 200 | 400 | Must include value proposition |
| Bumps (bump_normal, bump_descriptive) | 50 | 150 | Concise urgency messaging |
| Text-only bumps (bump_text_only) | 30 | 100 | No media reference |
| Retention (renew_on_post, renew_on_message, expired_winback) | 100 | 250 | Personal tone required |
| Engagement (link_drop, dm_farm, like_farm) | 50 | 200 | Clear call-to-action |

### ppv_structure
PPV-specific caption requirements for revenue-generating send types.

- **Price mention**: Must reference unlock price or value
- **Content preview**: Describe what subscriber receives
- **Urgency element**: Time-limited or scarcity language
- **Call-to-action**: Clear unlock instruction
- **No spoilers**: Don't reveal content fully

Applies to: `ppv_unlock`, `ppv_wall`, `bundle`, `flash_bundle`, `tip_goal`

### emoji_blending
Emoji density and placement analysis.

| Send Type | Min Emojis | Max Emojis | Placement Rules |
|-----------|------------|------------|-----------------|
| PPV sends | 3 | 5 | Opener, mid-point, closer |
| Bumps | 2 | 4 | Bookend style preferred |
| Retention | 2 | 3 | Warm/personal emojis only |
| Engagement | 2 | 5 | Action-oriented emojis |

**Flags**:
- CRITICAL: 0 emojis (feels robotic)
- WARNING: 6+ emojis (overwhelming)
- INFO: Mismatched emoji tone

### persona_match
Tone alignment with creator persona profile.

Validates against:
- **Slang level** (1-5): Caption vocabulary matches
- **Emoji style**: Preferred emoji categories used
- **Tone archetype**: Matches creator voice (playful, seductive, dominant, etc.)
- **Signature phrases**: Creator-specific expressions present

### freshness
Caption reuse and freshness score analysis.

- **CRITICAL**: Used within 7 days (score < 86)
- **WARNING**: Used within 14 days (score 86-92)
- **INFO**: Used within 30 days (score 93-99)
- **PASS**: Never used or 30+ days ago (score = 100)

Freshness calculation: `100 - (days_since_last_use * 2)` (7 days = 86, 14 days = 72)

## Output Format

```json
{
  "validation_id": "val_20251217_grace_bennett",
  "creator_id": "creator_123",
  "page_name": "grace_bennett",
  "validation_type": "all",
  "validation_timestamp": "2025-12-17T10:30:00Z",

  "summary": {
    "captions_analyzed": 45,
    "overall_score": 87,
    "rating": "Good",
    "pass_fail": "PASS",
    "critical_count": 0,
    "warning_count": 3,
    "info_count": 5
  },

  "component_scores": {
    "caption_quality": {"score": 92, "rating": "Excellent"},
    "ppv_structure": {"score": 88, "rating": "Good"},
    "emoji_blending": {"score": 85, "rating": "Good"},
    "persona_match": {"score": 82, "rating": "Good"},
    "freshness": {"score": 89, "rating": "Good"}
  },

  "issues": {
    "critical": [],
    "warnings": [
      {
        "code": "W001",
        "caption_id": 2345,
        "message": "Used 12 days ago (freshness: 76)",
        "send_type": "bump_normal",
        "resolution": "Consider substituting with fresher caption"
      },
      {
        "code": "W002",
        "caption_id": 3456,
        "message": "Slang level 4 mismatches creator profile (level 2)",
        "send_type": "ppv_unlock",
        "resolution": "Adjust vocabulary to match creator persona"
      },
      {
        "code": "W003",
        "caption_id": 4567,
        "message": "Emoji count 6 exceeds maximum 5 for PPV",
        "send_type": "ppv_unlock",
        "resolution": "Remove 1-2 emojis for cleaner presentation"
      }
    ],
    "info": [
      {
        "code": "I001",
        "caption_id": 5678,
        "message": "Consider adding urgency element",
        "send_type": "bundle",
        "suggestion": "Add time-limited language like 'only today' or 'limited time'"
      },
      {
        "code": "I002",
        "caption_id": 6789,
        "message": "Emoji placement could be improved",
        "send_type": "bump_descriptive",
        "suggestion": "Move opener emoji to start of message"
      }
    ]
  },

  "recommendations": [
    "Refresh 3 captions used within 14 days",
    "Add emojis to 2 robotic-sounding captions",
    "Adjust slang level on 1 mismatched caption"
  ],

  "caption_breakdown": {
    "by_send_type": {
      "ppv_unlock": {"count": 12, "avg_score": 88},
      "bundle": {"count": 5, "avg_score": 85},
      "bump_normal": {"count": 15, "avg_score": 91},
      "bump_descriptive": {"count": 8, "avg_score": 86},
      "renew_on_message": {"count": 5, "avg_score": 84}
    },
    "by_freshness": {
      "never_used": 18,
      "30_plus_days": 12,
      "14_30_days": 8,
      "7_14_days": 5,
      "under_7_days": 2
    }
  }
}
```

### Text Report Format

```
VALIDATION REPORT: grace_bennett
Validation Type: all
Captions Analyzed: 45
Overall Score: 87/100 [Good]

CRITICAL ISSUES (0):
(none)

WARNINGS (3):
- [W001] Caption #2345: Used 12 days ago (freshness: 76)
- [W002] Caption #3456: Slang level 4 mismatches creator profile (level 2)
- [W003] Caption #4567: Emoji count 6 exceeds maximum 5 for PPV

INFO (5):
- [I001] Caption #5678: Consider adding urgency element
- [I002] Caption #6789: Emoji placement could be improved
- [I003] Caption #7890: Structure improvement possible
- [I004] Caption #8901: Tone refinement available
- [I005] Caption #9012: Optimization opportunity

RECOMMENDATIONS:
1. Refresh 3 captions used within 14 days
2. Add emojis to 2 robotic-sounding captions
3. Adjust slang level on 1 mismatched caption

PASS/FAIL: PASS
```

## Validation Scoring

Each validation produces a score from 0-100:

| Score Range | Rating | Meaning |
|-------------|--------|---------|
| 90-100 | Excellent | No issues, ready for production |
| 75-89 | Good | Minor improvements suggested |
| 50-74 | Needs Work | Multiple warnings, review recommended |
| 25-49 | Poor | Critical issues present |
| 0-24 | Fail | Cannot be used without revision |

## Issue Codes

### Critical (Cxxx)
- C001: Character length out of bounds
- C002: Zero emojis (robotic)
- C003: Missing required PPV elements
- C004: Freshness below 7-day threshold
- C005: Severe persona mismatch

### Warning (Wxxx)
- W001: Freshness 7-30 days
- W002: Slang level mismatch
- W003: Emoji count outside range
- W004: Missing call-to-action
- W005: Weak urgency element

### Info (Ixxx)
- I001: Optimization opportunity
- I002: Emoji placement suggestion
- I003: Tone refinement available
- I004: Structure improvement possible

## Price-Length Interaction

Higher-priced PPV requires longer, more detailed descriptions:

| Price Range | Min Chars | Recommendation |
|-------------|-----------|----------------|
| $5-15 | 150 | Brief, enticing |
| $16-30 | 200 | Moderate detail |
| $31-50 | 250 | Detailed preview |
| $51+ | 300 | Premium description with value justification |

## Examples

### Basic Usage - Full Validation
```
/eros:validate grace_bennett
```
Runs all validation types on grace_bennett's captions.

### Specific Validation Type
```
/eros:validate creator_123 ppv_structure
```
Validates only PPV structure requirements for creator_123.

```
/eros:validate alexia freshness
```
Checks only caption freshness for alexia.

```
/eros:validate grace_bennett emoji_blending
```
Validates emoji density and placement only.

### Pre-Schedule Quality Check
```
/eros:validate grace_bennett caption_quality
# Review length and structure issues
# Then generate schedule:
/eros:generate grace_bennett 2025-12-23
```

### Post-Schedule Deep Validation
```
/eros:generate grace_bennett 2025-12-23
# Schedule generated successfully
/eros:validate grace_bennett all
# Deep validation of all caption quality aspects
```

### New Creator Validation
```
/eros:validate new_creator_456 persona_match
```
For new creators, persona_match validation helps ensure captions align with their defined voice profile before scheduling.

### Fixing Failed Validation
```
/eros:validate grace_bennett all
# Result: FAIL with 2 critical issues
# Fix captions in database
/eros:validate grace_bennett all
# Re-run to confirm fixes
```

## Execution Steps

1. Fetch creator's persona profile for baseline comparison
2. Retrieve top captions matching validation scope
3. For each caption, run applicable validation checks
4. Calculate component scores and aggregate
5. Generate issue list with severity classification
6. Produce actionable recommendations
7. Return structured validation report

## Error Handling

### Invalid Creator ID
```
ERROR: Creator not found
Code: CREATOR_NOT_FOUND
Message: No creator found matching "invalid_name".
Resolution: Run /eros:creators to see available creators.
```

### Invalid Validation Type
```
ERROR: Invalid validation type
Code: INVALID_VALIDATION_TYPE
Message: Validation type "spelling" is not valid.
Valid types: caption_quality, ppv_structure, emoji_blending, persona_match, freshness, all
Resolution: Use one of the valid validation types.
```

### Database Connection Failure
```
ERROR: Database connection failed
Code: DB_CONNECTION_ERROR
Message: Unable to connect to eros_sd_main.db
Resolution:
  1. Verify database file exists at ./database/eros_sd_main.db
  2. Check EROS_DB_PATH environment variable
  3. Ensure MCP eros-db server is running
```

### MCP Tool Timeout
```
ERROR: MCP tool timeout
Code: MCP_TIMEOUT
Message: get_top_captions timed out after 30s
Resolution:
  1. Retry the command
  2. Try validating fewer captions with specific type
  3. Verify MCP server health
```

### No Captions Found
```
WARNING: No captions to validate
Code: NO_CAPTIONS
Message: No captions found for creator matching vault matrix.
Resolution:
  1. Verify creator has vault_matrix entries
  2. Check caption_bank for compatible captions
  3. Add captions before validation
```

### Missing Persona Profile
```
WARNING: No persona profile defined
Code: NO_PERSONA
Message: Creator has no persona profile. Skipping persona_match validation.
Resolution: Define persona profile for complete validation coverage.
```

## Performance Expectations

| Metric | Typical Value | Notes |
|--------|---------------|-------|
| Execution Time | 3-8 seconds | Depends on validation type and caption count |
| Database Queries | 3-6 | Persona, captions, send type details |
| Memory Usage | Low-Moderate | Caches validation results |

### Performance by Validation Type

| Type | Typical Time | Database Load |
|------|--------------|---------------|
| caption_quality | 1-2 seconds | Low |
| ppv_structure | 1-2 seconds | Low |
| emoji_blending | 1-2 seconds | Low |
| persona_match | 2-3 seconds | Moderate |
| freshness | 2-3 seconds | Moderate |
| all | 5-8 seconds | Moderate |

### Performance Factors

- **Caption count** directly impacts duration
- **all validation** runs 5 checks per caption
- **Specific type** faster than full validation
- **Persona match** requires additional persona lookup

## Related Commands

| Command | Relationship |
|---------|--------------|
| `/eros:analyze` | Run before validate to understand performance context |
| `/eros:generate` | Run validate AFTER generate to verify caption quality |
| `/eros:creators` | Use to find valid creator IDs |

### Typical Workflow

1. `/eros:creators` - Find creator to work with
2. `/eros:analyze grace_bennett` - Understand performance state
3. `/eros:generate grace_bennett 2025-12-23` - Generate schedule
4. `/eros:validate grace_bennett all` - Deep validation of schedule quality
5. Fix any critical issues identified
6. `/eros:validate grace_bennett all` - Confirm fixes

### Quality Assurance Workflow

```
# Pre-schedule validation
/eros:validate grace_bennett caption_quality
/eros:validate grace_bennett freshness

# Generate schedule
/eros:generate grace_bennett 2025-12-23

# Post-schedule full validation
/eros:validate grace_bennett all
```

$ARGUMENTS
