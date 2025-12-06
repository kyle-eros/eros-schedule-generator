# EROS Schedule Generator Architecture Reference

## Overview

The EROS Schedule Generator is a 9-step pipeline that generates optimized weekly content schedules for OnlyFans creators. This document describes the architecture, data flow, and key components for extraction into a skills package.

---

## Module Dependency Diagram

```
                                    ┌─────────────────────────┐
                                    │     CLI Layer           │
                                    │   cli/schedule.py       │
                                    └───────────┬─────────────┘
                                                │
                                                ▼
                                    ┌─────────────────────────┐
                                    │    Service Layer        │
                                    │ schedule_service.py     │
                                    │  - orchestrates flow    │
                                    │  - progress reporting   │
                                    │  - error handling       │
                                    └───────────┬─────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
        │  FeatureFlagMgr   │       │    Scheduler      │       │   AI Client       │
        │  config/features  │       │  core/scheduler   │       │   ai/client.py    │
        │ - per-creator     │       │ - 9-step pipeline │       │ - intelligence    │
        │   overrides       │       │ - main engine     │       │   briefs          │
        └───────────────────┘       └───────────┬───────┘       └───────────────────┘
                                                │
        ┌───────────────────────────────────────┼───────────────────────────────────────┐
        │                   │                   │                   │                   │
        ▼                   ▼                   ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│CaptionSelector│   │  Freshness    │   │PersonaMatcher │   │FollowupGen    │   │ DripManager   │
│caption_selector│  │  freshness.py │   │persona_matcher│   │followup_gen   │   │ drip_manager  │
│- VoseAlias    │   │- 14-day decay │   │- tone match   │   │- bump timing  │   │- window rules │
│- weighted     │   │- half-life    │   │- persona      │   │- follow-ups   │   │- PPV blocking │
└───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │                   │                   │
        └───────────────────┴───────────────────┴───────────────────┴───────────────────┘
                                                │
                                                ▼
                                    ┌─────────────────────────┐
                                    │   Validators            │
                                    │  core/validators/       │
                                    │  - CompositeValidator   │
                                    │  - SpacingValidator     │
                                    │  - FreshnessValidator   │
                                    │  - ContentValidator     │
                                    └───────────┬─────────────┘
                                                │
                                                ▼
                                    ┌─────────────────────────┐
                                    │   Repository Layer      │
                                    │ data/repositories/      │
                                    │  - CreatorRepository    │
                                    │  - CaptionRepository    │
                                    │  - AnalyticsRepository  │
                                    │  - VaultRepository      │
                                    │  - PersonaRepository    │
                                    └───────────┬─────────────┘
                                                │
                                                ▼
                                    ┌─────────────────────────┐
                                    │   Database Layer        │
                                    │   SQLite (97 MB)        │
                                    │  - 22 tables            │
                                    │  - 17 views             │
                                    │  - 8 triggers           │
                                    └─────────────────────────┘
```

---

## The 9-Step Scheduler Pipeline

### Pipeline Overview

```
Input: creator_id, week_start_date
                    │
                    ▼
    ┌───────────────────────────────────┐
    │ Step 1: ANALYZE                   │
    │ Load creator analytics & profile  │
    └───────────────────┬───────────────┘
                        │
                        ▼
    ┌───────────────────────────────────┐
    │ Step 2: MATCH CONTENT             │
    │ Filter by vault availability      │
    └───────────────────┬───────────────┘
                        │
                        ▼
    ┌───────────────────────────────────┐
    │ Step 3: MATCH PERSONA             │
    │ Score by voice profile            │
    └───────────────────┬───────────────┘
                        │
                        ▼
    ┌───────────────────────────────────┐
    │ Step 4: BUILD STRUCTURE           │
    │ Create weekly time slots          │
    └───────────────────┬───────────────┘
                        │
                        ▼
    ┌───────────────────────────────────┐
    │ Step 5: ASSIGN CAPTIONS           │
    │ Weighted selection (Vose Alias)   │
    └───────────────────┬───────────────┘
                        │
                        ▼
    ┌───────────────────────────────────┐
    │ Step 6: GENERATE FOLLOW-UPS       │  [Feature Flag: enable_follow_ups]
    │ Create follow-up bump messages    │
    └───────────────────┬───────────────┘
                        │
                        ▼
    ┌───────────────────────────────────┐
    │ Step 7: APPLY DRIP WINDOWS        │  [Feature Flag: enable_drip_windows]
    │ Enforce 4-8hr no-PPV zones        │
    └───────────────────┬───────────────┘
                        │
                        ▼
    ┌───────────────────────────────────┐
    │ Step 8: APPLY PAGE TYPE RULES     │  [Feature Flag: enable_page_type_rules]
    │ Filter by paid vs free            │
    └───────────────────┬───────────────┘
                        │
                        ▼
    ┌───────────────────────────────────┐
    │ Step 9: VALIDATE & RETURN         │
    │ Check all business rules          │
    └───────────────────┬───────────────┘
                        │
                        ▼
Output: ScheduleResult (list of ScheduleItem)
```

---

## Step-by-Step Pipeline Detail

### Step 1: ANALYZE - Load Creator Analytics & Profile

**Purpose:** Initialize the scheduling context with creator data and historical analytics.

**Inputs:**
- `creator_id` (str) - Unique identifier for the creator
- `week_start_date` (str) - ISO date format "YYYY-MM-DD"

**Outputs:**
- `CreatorContext` object containing:
  - Creator profile (page_name, page_type, timezone, performance_tier)
  - Analytics summary (best_hours, best_days, best_content_types)
  - Current metrics (active_fans, earnings, contribution_pct)

**Database Tables Accessed:**
- `creators` - Basic creator profile
- `creator_analytics_summary` - Pre-aggregated performance data
- `creator_personas` - Voice profile (tone, emoji style, slang level)

**Key Queries:**
```sql
-- Get creator profile
SELECT * FROM creators WHERE creator_id = ?

-- Get analytics summary (30-day default)
SELECT * FROM creator_analytics_summary
WHERE creator_id = ? AND period_type = '30d'

-- Get persona profile
SELECT * FROM creator_personas WHERE creator_id = ?
```

---

### Step 2: MATCH CONTENT - Filter by Vault Availability

**Purpose:** Filter captions to only include content types the creator actually has in their vault.

**Inputs:**
- `CreatorContext` from Step 1
- All available captions from caption_bank

**Outputs:**
- Filtered list of captions matching creator's vault content

**Database Tables Accessed:**
- `vault_matrix` - What content types creator has
- `caption_bank` - All available captions
- `content_types` - Content type definitions

**Key Queries:**
```sql
-- Get creator's available content types
SELECT ct.type_name, ct.content_type_id
FROM vault_matrix vm
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE vm.creator_id = ? AND vm.has_content = 1

-- Get matching captions
SELECT * FROM caption_bank
WHERE is_active = 1
  AND (content_type_id IN (SELECT content_type_id FROM vault_matrix
       WHERE creator_id = ? AND has_content = 1)
       OR content_type_id IS NULL)
```

**Algorithm:**
1. Query vault_matrix for creator's available content types
2. Filter caption_bank to include only matching content types
3. Include "universal" captions that work for any content type

---

### Step 3: MATCH PERSONA - Score by Voice Profile

**Purpose:** Score and rank captions based on how well they match the creator's voice persona.

**Inputs:**
- Filtered captions from Step 2
- Creator's persona profile (tone, emoji_frequency, slang_level)

**Outputs:**
- Captions with `persona_score` attribute (0.0 - 1.4 boost factor)

**Database Tables Accessed:**
- `creator_personas` - Voice characteristics

**Algorithm (PersonaMatcher):**
```python
def calculate_persona_boost(caption, persona):
    boost = 1.0

    # Primary tone match (1.20x boost)
    if caption.tone == persona.primary_tone:
        boost *= 1.20

    # Emoji frequency match (up to 1.10x)
    if caption.emoji_style == persona.emoji_frequency:
        boost *= 1.10

    # Slang level match (up to 1.10x)
    if caption.slang_level == persona.slang_level:
        boost *= 1.10

    # Maximum combined boost: 1.40x
    return min(boost, 1.40)
```

**Persona Attributes:**
| Attribute | Possible Values |
|-----------|-----------------|
| primary_tone | playful, aggressive, sweet, dominant, bratty, seductive |
| emoji_frequency | heavy, moderate, light, none |
| slang_level | none, light, heavy |

---

### Step 4: BUILD STRUCTURE - Create Weekly Time Slots

**Purpose:** Generate the weekly slot structure based on volume assignment and best hours analytics.

**Inputs:**
- Creator's volume assignment (PPV/day, bump/day)
- Best performing hours from analytics
- Week start date

**Outputs:**
- List of `TimeSlot` objects for the week

**Database Tables Accessed:**
- `volume_assignments` - Daily targets per creator
- `creator_analytics_summary` - Optimal hours/days

**Volume Level Brackets:**
| Level | Fan Count | PPV/Day | Bump/Day |
|-------|-----------|---------|----------|
| Low | < 1,000 | 2-3 | 2-3 |
| Mid | 1,000-5,000 | 4-5 | 4-5 |
| High | 5,000-15,000 | 6-8 | 6-8 |
| Ultra | 15,000+ | 8-10 | 8-10 |

**Algorithm:**
1. Query volume assignment for creator
2. Extract best hours from analytics (JSON: `best_mm_hours`)
3. For each day in week:
   - Generate PPV slots at optimal hours
   - Generate bump slots following PPV timing rules
4. Return sorted list of time slots

---

### Step 5: ASSIGN CAPTIONS - Weighted Selection (Vose Alias)

**Purpose:** Assign captions to slots using weighted random selection that balances performance and freshness.

**Inputs:**
- Time slots from Step 4
- Scored captions from Step 3

**Outputs:**
- Schedule items with assigned captions

**Algorithm (Vose Alias Method):**

The Vose Alias method provides O(1) sampling from a weighted distribution after O(n) preprocessing:

```python
class VoseAliasSelector:
    """Weighted random selection using Vose's Alias Method.

    Weight Formula:
    weight = (performance_score * 0.6) + (freshness_score * 0.4)
           + persona_boost_factor
    """

    def __init__(self, items, weight_func):
        self.items = items
        self.n = len(items)

        # Compute normalized probabilities
        weights = [weight_func(item) for item in items]
        total = sum(weights)
        prob = [w * self.n / total for w in weights]

        # Build alias table
        self.prob = [0.0] * self.n
        self.alias = [0] * self.n

        small = []
        large = []
        for i, p in enumerate(prob):
            (small if p < 1.0 else large).append(i)

        while small and large:
            l = small.pop()
            g = large.pop()
            self.prob[l] = prob[l]
            self.alias[l] = g
            prob[g] = (prob[g] + prob[l]) - 1.0
            (small if prob[g] < 1.0 else large).append(g)

        for g in large:
            self.prob[g] = 1.0
        for l in small:
            self.prob[l] = 1.0

    def select(self):
        i = random.randint(0, self.n - 1)
        return self.items[i if random.random() < self.prob[i] else self.alias[i]]
```

**Weight Calculation:**
```python
def calculate_weight(caption):
    # Base weights from config (defaults shown)
    PERFORMANCE_WEIGHT = 0.6  # EROS_PERFORMANCE_WEIGHT
    FRESHNESS_WEIGHT = 0.4    # EROS_FRESHNESS_WEIGHT

    base_weight = (
        (caption.performance_score * PERFORMANCE_WEIGHT) +
        (caption.freshness_score * FRESHNESS_WEIGHT)
    )

    # Apply persona boost (1.0 - 1.4x)
    return base_weight * caption.persona_boost
```

---

### Step 6: GENERATE FOLLOW-UPS (Feature Flag: enable_follow_ups)

**Purpose:** Create follow-up bump messages after PPV content.

**Inputs:**
- Schedule items with PPV messages
- Feature flag state

**Outputs:**
- Additional bump schedule items

**Algorithm (FollowupGenerator):**
```python
def generate_followups(ppv_items):
    followups = []
    for ppv in ppv_items:
        # Only generate for high performers
        if ppv.caption.performance_score >= 60:
            # Random delay: 15-45 minutes after PPV
            delay_minutes = random.randint(15, 45)
            followup_time = ppv.scheduled_time + timedelta(minutes=delay_minutes)

            followups.append(ScheduleItem(
                item_type='bump',
                scheduled_time=followup_time,
                parent_item_id=ppv.item_id,
                is_follow_up=True
            ))
    return followups
```

**Business Rules:**
- Follow-ups only for captions with performance_score >= 60
- Delay: 15-45 minutes after PPV
- Maximum 1 follow-up per PPV
- Follow-ups reference parent PPV item

---

### Step 7: APPLY DRIP WINDOWS (Feature Flag: enable_drip_windows)

**Purpose:** Enforce no-PPV zones after drip content to prevent subscriber fatigue.

**Inputs:**
- All schedule items
- Drip content identification

**Outputs:**
- Modified schedule with drip windows enforced

**Algorithm (DripManager):**
```python
def apply_drip_windows(items):
    """
    Drip Window Rule: 4-8 hours after drip content, NO PPVs allowed.
    """
    DRIP_WINDOW_MIN_HOURS = 4
    DRIP_WINDOW_MAX_HOURS = 8

    drip_items = [i for i in items if i.is_drip_content]

    for drip in drip_items:
        window_start = drip.scheduled_time
        window_end = window_start + timedelta(hours=DRIP_WINDOW_MAX_HOURS)

        for item in items:
            if item.item_type == 'ppv' and window_start < item.scheduled_time < window_end:
                # Reschedule PPV to after window
                item.scheduled_time = window_end + timedelta(minutes=30)
                item.rescheduled_reason = 'drip_window_conflict'

    return items
```

**Business Rules:**
- Drip window: 4-8 hours (configurable)
- PPVs within window are rescheduled
- Bumps are allowed within drip windows
- Window calculated from drip content send time

---

### Step 8: APPLY PAGE TYPE RULES (Feature Flag: enable_page_type_rules)

**Purpose:** Apply page-type-specific posting rules for paid vs free pages.

**Inputs:**
- Schedule items
- Creator's page_type ('paid' or 'free')

**Outputs:**
- Filtered/adjusted schedule items

**Business Rules:**

| Rule | Paid Pages | Free Pages |
|------|------------|------------|
| PPV Pricing | $5 - $50 | $3 - $25 |
| Daily PPV Limit | Based on volume | +20% volume |
| Bump Frequency | Standard | Higher frequency |
| Wall Posts | Mix of paid/free | Mostly free teasers |

**Algorithm:**
```python
def apply_page_type_rules(items, page_type):
    if page_type == 'free':
        # Free pages get more bumps, fewer high-priced PPVs
        for item in items:
            if item.item_type == 'ppv' and item.suggested_price > 25:
                item.suggested_price = min(item.suggested_price * 0.7, 25)

    return items
```

---

### Step 9: VALIDATE & RETURN

**Purpose:** Run all validators to ensure schedule meets business rules.

**Inputs:**
- Complete schedule from previous steps

**Outputs:**
- `ScheduleResult` with validated items and any validation issues

**Validators (CompositeValidator pattern):**

1. **SpacingValidator**
   - Minimum 3-4 hours between PPVs
   - Configurable via `EROS_MIN_PPV_SPACING_HOURS`

2. **FreshnessValidator**
   - Minimum freshness_score >= 30
   - Configurable via `EROS_FRESHNESS_MINIMUM_SCORE`

3. **ContentValidator**
   - Ensures caption content_type matches vault availability
   - Validates required content tags

4. **TimingValidator**
   - Validates times are within allowed hours
   - Checks timezone correctness

**Validator Protocol:**
```python
@runtime_checkable
class Validator(Protocol):
    @property
    def rule_name(self) -> str: ...

    def validate(self, items: list, context: ValidationContext) -> ValidationResult: ...

class CompositeValidator:
    def __init__(self, validators: list[Validator]):
        self.validators = validators

    def validate(self, items, context):
        result = ValidationResult()
        for validator in self.validators:
            sub_result = validator.validate(items, context)
            result.merge(sub_result)
        return result
```

**ValidationResult Structure:**
```python
@dataclass
class ValidationIssue:
    rule_name: str
    severity: str  # 'error', 'warning', 'info'
    message: str
    item_ids: list[int]

@dataclass
class ValidationResult:
    issues: list[ValidationIssue]
    is_valid: bool  # True if no errors (warnings OK)
```

---

## Feature Flags

All feature flags are managed by `FeatureFlagManager` with per-creator override support.

| Flag | Default | Description |
|------|---------|-------------|
| enable_follow_ups | False | Generate follow-up bumps |
| enable_drip_windows | False | Enforce drip windows |
| enable_type_rotation | False | Rotate content types |
| enable_am_pm_split | False | Separate AM/PM strategies |
| enable_page_type_rules | False | Apply page type rules |
| enable_scheduler_targets | False | Use target-based quotas |
| enable_volume_strategy | False | Volume-based scheduling |
| enable_analytics_slots | False | Analytics-driven slots |
| enable_ai_intelligence | False | AI intelligence briefs |
| enable_ai_scoring | False | AI caption scoring |
| enable_ai_optimization | False | AI schedule optimization |

**Usage Pattern:**
```python
from eros_cli.config.features import get_feature_manager

manager = get_feature_manager()

# Always pass creator_id to get per-creator overrides
if manager.is_enabled("enable_follow_ups", creator_id="creator_123"):
    followups = generate_followups(ppv_items)
```

---

## Database Entity Relationships

```
┌─────────────────┐     1:N     ┌─────────────────┐
│   creators      │─────────────│  mass_messages  │
│   (TEXT PK)     │             │  (performance)  │
└────────┬────────┘             └────────┬────────┘
         │                               │
         │ 1:N                           │ N:1
         │                               │
         ▼                               ▼
┌─────────────────┐             ┌─────────────────┐
│ creator_personas│             │  caption_bank   │
│  (voice profile)│             │  (19,590 rows)  │
└─────────────────┘             └────────┬────────┘
         │                               │
         │ 1:1                           │ N:M
         │                               │
         ▼                               ▼
┌─────────────────┐             ┌─────────────────┐
│creator_analytics│             │caption_creator_ │
│   _summary      │             │  performance    │
└─────────────────┘             └─────────────────┘

┌─────────────────┐     1:N     ┌─────────────────┐
│   creators      │─────────────│  vault_matrix   │
└─────────────────┘             └────────┬────────┘
                                         │ N:1
                                         ▼
                                ┌─────────────────┐
                                │  content_types  │
                                │   (33 types)    │
                                └─────────────────┘
```

---

## Key Data Structures

### ScheduleItem (Output)
```python
@dataclass
class ScheduleItem:
    item_id: int
    creator_id: str
    scheduled_date: str      # "YYYY-MM-DD"
    scheduled_time: str      # "HH:MM"
    item_type: str           # "ppv", "bump", "wall_post"
    channel: str             # "mass_message", "wall_post"
    caption_id: int
    caption_text: str
    suggested_price: float
    content_type_id: int
    flyer_required: bool
    is_follow_up: bool
    parent_item_id: int | None
    status: str              # "pending", "queued", "sent"
    priority: int            # 1-10 (1 = highest)
```

### CreatorContext (Internal)
```python
@dataclass
class CreatorContext:
    creator_id: str
    page_name: str
    page_type: str           # "paid" or "free"
    timezone: str
    performance_tier: int    # 1, 2, or 3
    active_fans: int
    total_earnings: float
    best_hours: list[int]    # [21, 14, 10] etc.
    best_days: list[int]     # [5, 6, 0] (Fri, Sat, Sun)
    persona: PersonaProfile
    vault_content_types: list[int]
```

---

## Performance Considerations

### Database Indexes Used
```sql
-- Critical for caption selection
CREATE INDEX idx_caption_selection
ON caption_bank(is_active, content_type_id, caption_type, freshness_score DESC, performance_score DESC);

-- Critical for analytics queries
CREATE INDEX idx_mm_creator_type_analytics
ON mass_messages(creator_id, message_type, sending_hour, sending_day_of_week);

-- Vault content lookup
CREATE INDEX idx_vault_has_content ON vault_matrix(creator_id, has_content);
```

### Caching
- AI intelligence briefs cached for 7 days (TTL)
- Analytics summaries pre-computed in `creator_analytics_summary` table
- Freshness scores calculated on-demand with 14-day half-life

### Batch Operations
- Use batch freshness updates: `repo.batch_update_freshness(updates)`
- Validator runs on complete schedule (not per-item)
- Database triggers auto-update caption statistics

---

## Error Handling

All services use `@BaseService.handle_errors()` decorator:

```python
class ScheduleService(BaseService):
    @BaseService.handle_errors("Schedule generation failed")
    def generate_schedule(self, creator_id: str, week: str) -> ScheduleResult:
        self._report_progress("Loading creator data", 0.1)
        # ... implementation ...
        return result
```

**Error Categories:**
- `CreatorNotFoundError` - Invalid creator_id
- `VaultEmptyError` - No content in vault
- `CaptionExhaustionError` - All captions below freshness threshold
- `ValidationError` - Schedule fails validation rules

---

## Version Information

- **Current Version:** EROS CLI v1.0
- **Pipeline Version:** 9-step (as documented in CLAUDE.md)
- **Database Schema:** v2.4 (22 tables, 17 views, 8 triggers)
- **Last Updated:** 2025-12-02
