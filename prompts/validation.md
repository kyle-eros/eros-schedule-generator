# EROS Schedule Validation Prompt
# Version: 2.1.0
# Purpose: Guide LLM reasoning for schedule validation and auto-correction

---

## OBJECTIVE

Validate generated schedules against 30 business rules, identifying violations and applying automatic corrections where possible. Ensure all schedules meet quality standards before delivery.

---

## VALIDATION PHILOSOPHY

### Severity Hierarchy

| Severity | Behavior | Schedule Impact |
|----------|----------|-----------------|
| **ERROR** | Blocks output if not corrected | Cannot deliver |
| **WARNING** | Allows output but flags review | Delivered with caveats |
| **INFO** | Informational only | No action required |

### Auto-Correction Principle

Auto-correct issues when:
1. Correction is deterministic (clear right answer)
2. Correction doesn't require human judgment
3. Correction maintains schedule integrity
4. Maximum 2 correction passes allowed

Do NOT auto-correct when:
1. Multiple valid corrections exist (requires human choice)
2. Correction would significantly alter strategy
3. Issue is informational (INFO severity)

---

## VALIDATION RULES REFERENCE

### Core Rules (V001-V018)

#### V001: PPV_SPACING
```
Rule: PPVs must be spaced at least 3 hours apart
Recommended: 4 hours minimum spacing
Severity: ERROR if < 3h, WARNING if < 4h
Auto-Correctable: Yes (move_slot)

Correction Logic:
1. Identify PPV with spacing < 3h from previous
2. Calculate minimum valid time (previous + 4h)
3. Move slot to minimum valid time
4. Re-validate chain effect
```

#### V002: FRESHNESS_MINIMUM
```
Rule: All captions must have freshness >= 30
Severity: ERROR if < 25, WARNING if < 30
Auto-Correctable: Yes (swap_caption)

Correction Logic:
1. Find caption with freshness < 30
2. Query alternative captions (same content_type, freshness >= 30)
3. Select highest-weight alternative
4. Swap caption_id in slot
```

#### V003: FOLLOW_UP_TIMING
```
Rule: Follow-ups must be 15-45 minutes after parent PPV
Severity: WARNING
Auto-Correctable: Yes (adjust_timing)

Correction Logic:
1. Calculate delay from parent PPV
2. If delay < 15: set to 15 + random(0-10)
3. If delay > 45: set to 25 (default)
4. Update scheduled_time
```

#### V004: DUPLICATE_CAPTIONS
```
Rule: No duplicate caption_ids in same week
Severity: ERROR
Auto-Correctable: Yes (swap_caption)

Correction Logic:
1. Find duplicate caption_id usage
2. Keep first occurrence
3. Find alternative caption for subsequent occurrences
4. Swap with highest-weight fresh caption
```

#### V015: HOOK_ROTATION
```
Rule: Warn on 2+ consecutive same hook types
Severity: WARNING
Auto-Correctable: No (informational)

Report: Include hook sequence in warning message
Recommendation: Manual review for hook diversity
```

#### V016: HOOK_DIVERSITY
```
Rule: Target 4+ unique hook types per week
Severity: INFO
Auto-Correctable: No (informational)

Report: Count unique hooks, list missing types
Recommendation: Consider diversifying hook strategy
```

#### V017: CONTENT_ROTATION
```
Rule: No 3+ consecutive same content type
Severity: INFO
Auto-Correctable: No (informational)

Report: Identify consecutive sequence
Recommendation: Consider reordering content
```

#### V018: EMPTY_SCHEDULE
```
Rule: Schedule must have at least 1 item
Severity: WARNING
Auto-Correctable: No (requires investigation)

Report: Alert if schedule is empty
Action: Check caption pools, freshness thresholds
```

---

### Extended Rules (V020-V031)

#### V020: PAGE_TYPE_VIOLATION
```
Rule: Paid-only content types cannot appear on free pages
Paid-Only Types: vip_post, renew_on_post, renew_on_mm, expired_subscriber
Severity: ERROR
Auto-Correctable: Yes (remove_item)

Correction Logic:
1. Check page_type from creator profile
2. If page_type == "free" AND content_type in paid_only:
3. Remove item from schedule
4. Log removal with reason
```

#### V021: VIP_POST_SPACING
```
Rule: VIP posts must be at least 24 hours apart
Severity: ERROR
Auto-Correctable: Yes (move_slot)

Correction Logic:
1. Identify VIP posts within 24h of each other
2. Keep first chronologically
3. Move subsequent to 24h + 15min after first
4. Validate no cascade conflicts
```

#### V022: LINK_DROP_SPACING
```
Rule: Link drops must be at least 4 hours apart
Severity: WARNING
Auto-Correctable: Yes (move_slot)

Correction Logic:
1. Identify link_drop or wall_link_drop within 4h
2. Move to 4h + 15min after previous
```

#### V023: ENGAGEMENT_DAILY_LIMIT
```
Rule: Maximum 2 engagement posts (dm_farm, like_farm) per day
Severity: WARNING
Auto-Correctable: Yes (move_to_next_day)

Correction Logic:
1. Count engagement posts per day
2. If > 2: move excess to next available day
3. Distribute evenly across week
```

#### V024: ENGAGEMENT_WEEKLY_LIMIT
```
Rule: Maximum 10 engagement posts per week
Severity: WARNING
Auto-Correctable: Yes (remove_item)

Correction Logic:
1. Count total engagement posts
2. If > 10: remove lowest-priority items
3. Keep first 10 chronologically
```

#### V025: RETENTION_TIMING
```
Rule: Retention content (renew_on_*) should be on days 5-7
Severity: INFO
Auto-Correctable: No (recommendation only)

Report: Flag retention content on days 1-4
Recommendation: Move to end of week for best impact
```

#### V026: BUNDLE_SPACING
```
Rule: Regular bundles must be at least 24 hours apart
Severity: ERROR
Auto-Correctable: Yes (move_slot)

Correction Logic:
1. Sort bundles chronologically
2. Move any within 24h to 24h + 15min
3. Validate cascade effect
```

#### V027: FLASH_BUNDLE_SPACING
```
Rule: Flash bundles must be at least 48 hours apart
Severity: ERROR
Auto-Correctable: Yes (move_slot)

Correction Logic:
1. Sort flash_bundle items chronologically
2. Move any within 48h to 48h + 15min
3. Validate cascade effect
```

#### V028: GAME_POST_WEEKLY
```
Rule: Maximum 1 game_post per week
Severity: WARNING
Auto-Correctable: Yes (remove_item)

Correction Logic:
1. Count game_post items
2. If > 1: remove all but first chronologically
```

#### V029: BUMP_VARIANT_ROTATION
```
Rule: No 3+ consecutive same bump type
Bump Types: flyer_gif_bump, descriptive_bump, text_only_bump, normal_post_bump
Severity: WARNING
Auto-Correctable: Yes (swap_content_type)

Correction Logic:
1. Find sequence of 3+ same bump type
2. Swap third item to alternative bump type
3. Prefer type not used in last 2 slots
```

#### V030: CONTENT_TYPE_ROTATION
```
Rule: No 3+ consecutive same content type (any type)
Severity: INFO
Auto-Correctable: No (recommendation only)

Report: Identify consecutive sequences
Recommendation: Consider reordering for variety
```

#### V031: PLACEHOLDER_WARNING
```
Rule: Flag slots without assigned captions
Indicators: has_caption = False OR caption_id = None
Severity: INFO
Auto-Correctable: No (requires manual entry)

Report: List placeholder slots with theme_guidance
Action: Manual caption creation required
```

---

## VALIDATION EXECUTION FLOW

```
START VALIDATION
      |
      v
Load schedule items
      |
      v
+---------------------+
| Pass 1: Detection   |
| - Run all validators|
| - Collect issues    |
+---------------------+
      |
      v
Any ERRORS with auto-correct?
      |
      +-- Yes --> Apply corrections
      |           |
      |           v
      |    +---------------------+
      |    | Pass 2: Re-validate |
      |    | - Run all validators|
      |    | - Collect issues    |
      |    +---------------------+
      |           |
      |           v
      |    Still ERRORS?
      |           |
      |           +-- Yes --> FAIL (max passes reached)
      |           |
      |           +-- No --> Continue
      |
      +-- No --> Continue
      |
      v
Compile final report
      |
      v
+---------------------+
| Output:             |
| - is_valid: bool    |
| - error_count: int  |
| - warning_count: int|
| - issues: list      |
| - corrections: list |
+---------------------+
```

---

## AUTO-CORRECTION ALGORITHMS

### Move Slot Algorithm
```python
def move_slot(item, min_time_after):
    """
    Move item to minimum valid time.
    Preserves follow-up relationships.
    """
    # Calculate new time
    new_time = min_time_after + timedelta(minutes=15)

    # Check for cascade conflicts
    if conflicts_with_existing(new_time):
        new_time = find_next_available_slot(new_time)

    # Update item
    item.scheduled_time = new_time

    # Update linked follow-ups
    if item.has_follow_up:
        update_follow_up_time(item)

    return item
```

### Swap Caption Algorithm
```python
def swap_caption(slot, reason):
    """
    Replace caption with best alternative.
    Maintains content_type and slot timing.
    """
    # Query alternatives
    alternatives = query_captions(
        content_type=slot.content_type,
        min_freshness=30,
        exclude_ids=used_caption_ids
    )

    if not alternatives:
        raise CaptionExhaustionError()

    # Select by weight
    best = max(alternatives, key=lambda c: c.weight)

    # Swap
    slot.caption_id = best.caption_id
    slot.caption_text = best.caption_text
    slot.freshness_score = best.freshness_score

    return slot
```

### Remove Item Algorithm
```python
def remove_item(item, reason):
    """
    Remove item from schedule.
    Handles linked items (follow-ups).
    """
    # Remove follow-ups first
    if item.message_type == "ppv":
        follow_ups = find_follow_ups(item.item_id)
        for fu in follow_ups:
            schedule.remove(fu)

    # Remove item
    schedule.remove(item)

    # Re-index remaining items
    reindex_schedule()

    return removed_count
```

---

## VALIDATION REPORT FORMAT

### JSON Structure
```json
{
  "validation": {
    "passed": true,
    "is_valid": true,
    "error_count": 0,
    "warning_count": 2,
    "info_count": 3,
    "corrections_applied": 1,
    "issues": [
      {
        "rule_name": "V001",
        "rule_description": "PPV_SPACING",
        "severity": "error",
        "message": "PPV spacing too close: 2.5 hours between items 3 and 4",
        "item_ids": [3, 4],
        "auto_correctable": true,
        "correction_action": "move_slot",
        "correction_applied": true
      },
      {
        "rule_name": "V015",
        "rule_description": "HOOK_ROTATION",
        "severity": "warning",
        "message": "Consecutive urgency hooks at items 5 and 6",
        "item_ids": [5, 6],
        "auto_correctable": false
      }
    ],
    "auto_corrections": [
      {
        "rule_name": "V001",
        "action": "move_slot",
        "item_id": 4,
        "original_time": "13:30",
        "corrected_time": "14:15",
        "reason": "PPV spacing violation - moved to maintain 4h minimum"
      }
    ]
  }
}
```

---

## VALIDATION REASONING EXAMPLES

### Example 1: PPV Spacing Violation

**Input:**
```
Item 3: PPV at 10:00
Item 4: PPV at 12:30 (2.5 hours after)
```

**Reasoning:**
```
V001 Check:
- Item 4 scheduled 2.5 hours after Item 3
- Minimum required: 3 hours (ERROR threshold)
- Recommended: 4 hours (WARNING threshold)
- Status: ERROR - violates hard minimum

Auto-Correction:
- Action: move_slot
- Calculate: 10:00 + 4h = 14:00
- Add buffer: 14:00 + 15min = 14:15
- New time for Item 4: 14:15
- Check cascades: No conflicts
- Apply correction
```

### Example 2: Hook Rotation Warning

**Input:**
```
Item 5: hook_type = "urgency"
Item 6: hook_type = "urgency"
Item 7: hook_type = "curiosity"
```

**Reasoning:**
```
V015 Check:
- Items 5 and 6 have consecutive same hook type
- Rule: Warn on 2+ consecutive same hooks
- Status: WARNING - consecutive urgency hooks

Auto-Correction:
- Action: None (not auto-correctable)
- Reason: Hook selection involves persona matching
- Recommendation: Manual review for diversity
```

### Example 3: Page Type Violation

**Input:**
```
Creator: page_type = "free"
Item 8: content_type = "vip_post"
```

**Reasoning:**
```
V020 Check:
- vip_post is in paid_only list
- Creator page_type is "free"
- Status: ERROR - paid-only content on free page

Auto-Correction:
- Action: remove_item
- Reason: Cannot schedule VIP content on free page
- Item removed: 8
- Update: Reindex remaining items
```

---

## SPECIAL VALIDATION SCENARIOS

### Cascade Corrections
When one correction affects other items:
1. Apply primary correction
2. Re-run affected validators
3. Apply secondary corrections
4. Maximum depth: 3 levels

### Cross-Day Validation
When items span multiple days:
1. Validate per-day constraints first
2. Validate cross-day constraints second
3. Apply corrections chronologically

### Follow-Up Chain Integrity
When parent PPV is corrected:
1. Maintain parent-child relationship
2. Recalculate follow-up timing
3. Ensure follow-up moves with parent

---

## REMEMBER

Validation is automated via `validate_schedule.py`. This prompt guides the **reasoning** behind validation decisions.

The script handles:
- Rule evaluation
- Issue detection
- Auto-correction execution
- Report generation

Your role is to understand and explain validation logic, not execute it manually.
