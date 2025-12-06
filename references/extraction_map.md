# EROS Skills Package Extraction Map

## Overview

This document maps existing EROS CLI modules to their target standalone scripts in the skills package. Each script will be self-contained with embedded SQL queries and minimal dependencies.

---

## Module-to-Script Mapping

### Core Pipeline Scripts

| Existing Module | Target Script | Description |
|-----------------|---------------|-------------|
| `core/scheduler.py` | `generate_schedule.py` | Main 9-step pipeline orchestrator |
| `core/caption_selector.py` | `select_captions.py` | Vose Alias weighted selection |
| `core/freshness.py` | `calculate_freshness.py` | 14-day half-life decay scoring |
| `core/persona_matcher.py` | `match_persona.py` | Voice profile matching |
| `core/validators/` | `validate_schedule.py` | Composite validation rules |
| `core/followup_generator.py` | `generate_followups.py` | Follow-up bump generation |
| `core/drip_manager.py` | `apply_drip_windows.py` | Drip window enforcement |

### Data Access Scripts

| Existing Module | Target Script | Description |
|-----------------|---------------|-------------|
| `data/repositories/creators.py` | `query_creators.py` | Creator data queries |
| `data/repositories/captions.py` | `query_captions.py` | Caption data queries |
| `data/repositories/analytics.py` | `query_analytics.py` | Analytics summary queries |
| `data/repositories/vault.py` | `query_vault.py` | Vault matrix queries |
| `data/repositories/personas.py` | `query_personas.py` | Persona profile queries |

### Utility Scripts

| Existing Module | Target Script | Description |
|-----------------|---------------|-------------|
| `config/features.py` | `check_features.py` | Feature flag resolution |
| `domain/scoring.py` | `calculate_scores.py` | Performance/freshness scoring |
| `services/schedule_service.py` | `orchestrate_schedule.py` | High-level orchestration |

---

## Detailed Function Extraction

### 1. generate_schedule.py

**Source:** `src/eros_cli/core/scheduler.py`

**Key Functions to Extract:**
```python
# From scheduler.py
def generate() -> ScheduleResult
def _load_creator_context(creator_id: str) -> CreatorContext
def _build_weekly_slots(context: CreatorContext, week_start: str) -> list[TimeSlot]
def _apply_pipeline_steps(slots: list[TimeSlot], context: CreatorContext) -> list[ScheduleItem]
```

**Dependencies:**
- CaptionSelector (select_captions.py)
- FreshnessCalculator (calculate_freshness.py)
- PersonaMatcher (match_persona.py)
- Validators (validate_schedule.py)

**SQL Queries to Embed:**
```sql
-- Get creator by ID
SELECT * FROM creators WHERE creator_id = ?;

-- Get volume assignment
SELECT * FROM volume_assignments
WHERE creator_id = ? AND is_active = 1;

-- Get best hours from analytics
SELECT best_mm_hours, best_days, best_content_types
FROM creator_analytics_summary
WHERE creator_id = ? AND period_type = '30d';
```

---

### 2. select_captions.py

**Source:** `src/eros_cli/core/caption_selector.py`

**Key Functions to Extract:**
```python
# VoseAliasSelector class
class VoseAliasSelector:
    def __init__(self, items: list, weight_func: Callable)
    def select(self) -> Any
    def select_batch(self, count: int, allow_duplicates: bool = False) -> list

# Weight calculation
def calculate_caption_weight(caption: Caption) -> float
def get_weighted_captions(captions: list[Caption], persona: PersonaProfile) -> list[tuple[Caption, float]]
```

**SQL Queries to Embed:**
```sql
-- Get active captions for selection
SELECT cb.*, ct.type_name
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
WHERE cb.is_active = 1
  AND cb.freshness_score >= ?
ORDER BY cb.performance_score DESC, cb.freshness_score DESC;

-- Get creator-specific caption performance
SELECT ccp.*, cb.caption_text
FROM caption_creator_performance ccp
JOIN caption_bank cb ON ccp.caption_id = cb.caption_id
WHERE ccp.creator_id = ?
ORDER BY ccp.performance_score DESC;
```

**Configuration Constants:**
```python
PERFORMANCE_WEIGHT = 0.6  # env: EROS_PERFORMANCE_WEIGHT
FRESHNESS_WEIGHT = 0.4    # env: EROS_FRESHNESS_WEIGHT
MIN_FRESHNESS_THRESHOLD = 30.0  # env: EROS_FRESHNESS_MINIMUM_SCORE
```

---

### 3. calculate_freshness.py

**Source:** `src/eros_cli/core/freshness.py`

**Key Functions to Extract:**
```python
# Freshness calculation with 14-day half-life
def calculate_freshness_score(
    last_used_date: str | None,
    times_used: int,
    reference_date: str | None = None
) -> float

def calculate_days_decay(days_since_used: float, half_life: float = 14.0) -> float

def batch_calculate_freshness(captions: list[dict]) -> list[tuple[int, float]]

def get_exhausted_captions(threshold: float = 25.0) -> list[int]
```

**Algorithm:**
```python
def calculate_freshness_score(last_used_date, times_used, reference_date=None):
    """
    Freshness decay formula:
    freshness = 100 * (0.5 ^ (days_since_used / half_life))

    Half-life: 14 days (configurable via EROS_FRESHNESS_HALF_LIFE_DAYS)
    Exhaustion threshold: 25 (configurable via EROS_FRESHNESS_EXHAUSTION_THRESHOLD)
    """
    if last_used_date is None:
        return 100.0  # Never used = maximum freshness

    half_life = float(os.environ.get('EROS_FRESHNESS_HALF_LIFE_DAYS', '14.0'))

    days_since = (reference_date - last_used_date).days
    decay_factor = 0.5 ** (days_since / half_life)

    return round(100.0 * decay_factor, 2)
```

**SQL Queries to Embed:**
```sql
-- Get captions needing freshness update
SELECT caption_id, last_used_date, times_used
FROM caption_bank
WHERE is_active = 1;

-- Batch update freshness scores
UPDATE caption_bank
SET freshness_score = ?, updated_at = datetime('now')
WHERE caption_id = ?;

-- Get exhausted captions (below threshold)
SELECT caption_id, caption_text, freshness_score
FROM caption_bank
WHERE is_active = 1 AND freshness_score < ?;
```

---

### 4. match_persona.py

**Source:** `src/eros_cli/core/persona_matcher.py`

**Key Functions to Extract:**
```python
# Persona matching
def get_persona_profile(creator_id: str) -> PersonaProfile | None
def calculate_persona_boost(caption: Caption, persona: PersonaProfile) -> float
def score_captions_for_persona(captions: list[Caption], persona: PersonaProfile) -> list[ScoredCaption]
```

**Boost Calculation:**
```python
def calculate_persona_boost(caption, persona):
    """
    Persona boost factors:
    - Primary tone match: 1.20x
    - Emoji frequency match: 1.10x
    - Slang level match: 1.10x
    - Maximum combined: 1.40x
    """
    boost = 1.0

    if caption.tone == persona.primary_tone:
        boost *= 1.20

    if caption.emoji_style == persona.emoji_frequency:
        boost *= 1.10

    if caption.slang_level == persona.slang_level:
        boost *= 1.10

    return min(boost, 1.40)
```

**SQL Queries to Embed:**
```sql
-- Get persona profile
SELECT
    primary_tone,
    emoji_frequency,
    favorite_emojis,
    slang_level,
    avg_sentiment,
    avg_caption_length
FROM creator_personas
WHERE creator_id = ?;

-- Get caption style attributes
SELECT caption_id, tone, emoji_style, slang_level
FROM caption_bank
WHERE is_active = 1;
```

---

### 5. validate_schedule.py

**Source:** `src/eros_cli/core/validators/`

**Key Classes to Extract:**
```python
# Base validator protocol
class Validator(Protocol):
    @property
    def rule_name(self) -> str: ...
    def validate(self, items: list, context: ValidationContext) -> ValidationResult: ...

# Composite validator
class CompositeValidator:
    def __init__(self, validators: list[Validator])
    def validate(self, items: list, context: ValidationContext) -> ValidationResult

# Individual validators
class SpacingValidator:
    """Minimum 3-4 hours between PPVs"""
    min_hours: int = 4

class FreshnessValidator:
    """Minimum freshness score threshold"""
    min_score: float = 30.0

class ContentValidator:
    """Content type matches vault availability"""

class TimingValidator:
    """Schedule times within allowed hours"""
```

**Validation Rules:**
| Validator | Rule | Severity |
|-----------|------|----------|
| SpacingValidator | PPV spacing >= 3 hours | error |
| SpacingValidator | PPV spacing >= 4 hours | warning |
| FreshnessValidator | freshness_score >= 30 | error |
| FreshnessValidator | freshness_score >= 50 | warning |
| ContentValidator | content_type in vault | error |
| TimingValidator | hour in best_hours | info |

---

### 6. generate_followups.py

**Source:** `src/eros_cli/core/followup_generator.py`

**Key Functions to Extract:**
```python
def generate_followups(ppv_items: list[ScheduleItem]) -> list[ScheduleItem]
def calculate_followup_delay() -> int  # 15-45 minutes
def should_generate_followup(ppv_item: ScheduleItem) -> bool
```

**Business Rules:**
```python
# Follow-up generation rules
MIN_PERFORMANCE_FOR_FOLLOWUP = 60  # Only high performers
FOLLOWUP_DELAY_MIN_MINUTES = 15
FOLLOWUP_DELAY_MAX_MINUTES = 45
MAX_FOLLOWUPS_PER_PPV = 1
```

---

### 7. apply_drip_windows.py

**Source:** `src/eros_cli/core/drip_manager.py`

**Key Functions to Extract:**
```python
def identify_drip_content(items: list[ScheduleItem]) -> list[ScheduleItem]
def calculate_drip_window(drip_item: ScheduleItem) -> tuple[datetime, datetime]
def apply_drip_windows(items: list[ScheduleItem]) -> list[ScheduleItem]
def reschedule_conflicting_ppvs(items: list[ScheduleItem], windows: list[DripWindow]) -> list[ScheduleItem]
```

**Configuration:**
```python
DRIP_WINDOW_MIN_HOURS = 4
DRIP_WINDOW_MAX_HOURS = 8
RESCHEDULE_BUFFER_MINUTES = 30
```

---

## Query Scripts Extraction

### 8. query_creators.py

**Source:** `src/eros_cli/data/repositories/creators.py`

**Functions:**
```python
def get_creator_by_id(creator_id: str) -> dict | None
def get_creator_by_name(page_name: str) -> dict | None
def get_all_active_creators() -> list[dict]
def get_schedulable_creators() -> list[dict]
def get_creators_by_tier(tier: int) -> list[dict]
def get_portfolio_summary() -> dict
```

**SQL Queries:**
```sql
-- Get creator by ID
SELECT * FROM creators WHERE creator_id = ?;

-- Get active creators
SELECT * FROM creators WHERE is_active = 1 ORDER BY page_name;

-- Get schedulable (uses view)
SELECT * FROM v_schedulable_creators ORDER BY page_name;

-- Portfolio summary (uses view)
SELECT * FROM v_portfolio_summary;
```

---

### 9. query_captions.py

**Source:** `src/eros_cli/data/repositories/captions.py`

**Functions:**
```python
def get_caption_by_id(caption_id: int) -> dict | None
def get_fresh_captions(min_freshness: float = 30.0) -> list[dict]
def get_captions_by_content_type(content_type_id: int) -> list[dict]
def get_captions_for_creator(creator_id: str, include_universal: bool = True) -> list[dict]
def get_top_performers(limit: int = 100) -> list[dict]
def get_stale_captions(threshold: float = 30.0) -> list[dict]
def update_freshness(caption_id: int, score: float) -> bool
def increment_usage(caption_id: int) -> bool
```

**SQL Queries:**
```sql
-- Get fresh captions
SELECT * FROM caption_bank
WHERE is_active = 1 AND freshness_score >= ?
ORDER BY freshness_score DESC, performance_score DESC;

-- Get captions for creator (including universal)
SELECT * FROM caption_bank
WHERE is_active = 1 AND (creator_id = ? OR is_universal = 1)
ORDER BY performance_score DESC;

-- Get top performers (uses view)
SELECT * FROM v_top_captions LIMIT ?;

-- Get stale captions (uses view)
SELECT * FROM v_stale_captions WHERE freshness_score < ?;
```

---

### 10. query_vault.py

**Source:** `src/eros_cli/data/repositories/vault.py`

**Functions:**
```python
def get_vault_for_creator(creator_id: str) -> list[dict]
def get_available_content_types(creator_id: str) -> list[int]
def has_content_type(creator_id: str, content_type_id: int) -> bool
def get_vault_summary(creator_id: str) -> dict
```

**SQL Queries:**
```sql
-- Get vault contents
SELECT vm.*, ct.type_name, ct.type_category
FROM vault_matrix vm
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE vm.creator_id = ?;

-- Get available content type IDs
SELECT content_type_id FROM vault_matrix
WHERE creator_id = ? AND has_content = 1;

-- Check specific content type
SELECT 1 FROM vault_matrix
WHERE creator_id = ? AND content_type_id = ? AND has_content = 1;
```

---

## Script Dependencies Matrix

| Script | Requires |
|--------|----------|
| generate_schedule.py | select_captions, calculate_freshness, match_persona, validate_schedule, generate_followups, apply_drip_windows |
| select_captions.py | calculate_freshness |
| calculate_freshness.py | (standalone) |
| match_persona.py | query_personas |
| validate_schedule.py | (standalone) |
| generate_followups.py | (standalone) |
| apply_drip_windows.py | (standalone) |
| query_creators.py | (standalone) |
| query_captions.py | (standalone) |
| query_vault.py | (standalone) |
| query_personas.py | (standalone) |
| query_analytics.py | (standalone) |

---

## Environment Variables

All scripts should support these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `EROS_DATABASE_PATH` | `database/eros_sd_main.db` | Database file path |
| `EROS_PERFORMANCE_WEIGHT` | `0.6` | Weight for performance in selection |
| `EROS_FRESHNESS_WEIGHT` | `0.4` | Weight for freshness in selection |
| `EROS_FRESHNESS_HALF_LIFE_DAYS` | `14.0` | Freshness decay half-life |
| `EROS_FRESHNESS_EXHAUSTION_THRESHOLD` | `25` | Below this = exhausted |
| `EROS_FRESHNESS_MINIMUM_SCORE` | `30.0` | Minimum for scheduling |
| `EROS_MIN_PPV_SPACING_HOURS` | `4` | Minimum hours between PPVs |
| `EROS_TIMEZONE` | `America/Los_Angeles` | Default timezone |

---

## Output Format Standards

All scripts should output JSON-compatible structures:

### Schedule Output
```json
{
  "creator_id": "creator_123",
  "week_start": "2025-01-06",
  "generated_at": "2025-01-05T10:30:00",
  "items": [
    {
      "item_id": 1,
      "scheduled_date": "2025-01-06",
      "scheduled_time": "14:00",
      "item_type": "ppv",
      "caption_id": 456,
      "caption_text": "...",
      "suggested_price": 15.00,
      "content_type": "solo"
    }
  ],
  "validation": {
    "is_valid": true,
    "warnings": [],
    "errors": []
  }
}
```

### Query Output
```json
{
  "query": "get_schedulable_creators",
  "count": 36,
  "results": [
    {"creator_id": "...", "page_name": "...", ...}
  ]
}
```

---

## Migration Notes

### Code Patterns to Preserve

1. **Frozen Dataclasses** - Use `@dataclass(frozen=True, slots=True)` for immutable data
2. **Repository Pattern** - Keep query/write separation
3. **Validator Protocol** - Maintain `rule_name` property and `validate()` method
4. **Feature Flag Checks** - Always pass `creator_id` for per-creator overrides

### Code Patterns to Simplify

1. **Remove Service Layer** - Direct function calls in scripts
2. **Remove ViewModel Layer** - Scripts output raw data
3. **Inline SQL** - No ORM, embed queries directly
4. **Minimal Dependencies** - Standard library + sqlite3 only

---

## File Locations Summary

```
.claude/skills/eros-schedule-generator/
├── SKILL.md
├── scripts/
│   ├── generate_schedule.py      # Main pipeline
│   ├── select_captions.py        # Vose Alias selection
│   ├── calculate_freshness.py    # Freshness scoring
│   ├── match_persona.py          # Persona matching
│   ├── validate_schedule.py      # Validation rules
│   ├── generate_followups.py     # Follow-up generation
│   ├── apply_drip_windows.py     # Drip window rules
│   ├── query_creators.py         # Creator queries
│   ├── query_captions.py         # Caption queries
│   ├── query_vault.py            # Vault queries
│   ├── query_personas.py         # Persona queries
│   └── query_analytics.py        # Analytics queries
├── references/
│   ├── architecture.md           # This file
│   ├── extraction_map.md         # Module mapping
│   └── scheduling_rules.md       # Business rules
└── examples/
    ├── schedule_output.json
    └── validation_report.json
```

---

## Version

- **Document Version:** 1.0
- **Created:** 2025-12-02
- **Source Codebase:** EROS CLI v1.0
