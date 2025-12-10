# EROS Schedule Generator Architecture Reference

## Overview

The EROS Schedule Generator is a 9-step pipeline that generates optimized weekly content schedules for OnlyFans creators. This document describes the architecture, data flow, and key components.

**Current Version:** v2.1 (2025-12-09)
**Pipeline:** 9 steps from analysis to validation
**Key Features:** Pool-based earnings selection, content type registry (20+ types), schedule uniqueness engine, hook diversity, auto-correction loop

---

## Modular Architecture Overview

The EROS Schedule Generator follows a **4-layer modular architecture** designed for separation of concerns, testability, and maintainability. Each layer has a clearly defined responsibility and interacts with adjacent layers through well-defined interfaces.

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: CLI Wrapper & Orchestration                            │
│ ├─ generate_schedule.py (main entry point)                      │
│ ├─ prepare_llm_context.py (full mode context preparation)       │
│ └─ agent_invoker.py (sub-agent delegation)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: Pipeline Core & Business Logic                         │
│ ├─ select_captions.py (pool-based selection engine)             │
│ ├─ content_type_registry.py (20+ content type metadata)         │
│ ├─ schedule_uniqueness.py (timing variance & fingerprinting)    │
│ ├─ content_type_loaders.py (content loaders per type)           │
│ ├─ content_type_schedulers.py (slot generators)                 │
│ └─ volume_optimizer.py (performance-based volume calculation)   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Enrichment & Validation                                │
│ ├─ validate_schedule.py (30 validation rules + auto-correction) │
│ ├─ match_persona.py (voice profile matching, 1.0-1.4x boost)    │
│ ├─ followup_generator.py (context-aware follow-ups)             │
│ ├─ semantic_analysis.py (tone detection framework)              │
│ └─ quality_scoring.py (LLM-based caption quality)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Data Access & Utilities                                │
│ ├─ assets/sql/*.sql (database query layer)                      │
│ ├─ shared_context.py (shared dataclasses)                       │
│ ├─ weights.py (canonical weight calculation)                    │
│ ├─ utils.py (VoseAliasSelector, helpers)                        │
│ └─ logging_config.py (centralized logging)                      │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**Layer 1 - CLI Wrapper & Orchestration:**
- Command-line argument parsing and validation
- Pipeline orchestration (9-step execution)
- Output formatting and file I/O
- Error handling and user feedback
- Sub-agent delegation for advanced tasks

**Layer 2 - Pipeline Core & Business Logic:**
- Pool-based caption selection with stratification
- Content type registry and metadata management
- Schedule uniqueness enforcement (timing variance, fingerprinting)
- Content loaders and slot generators for 20+ types
- Performance-based volume optimization

**Layer 3 - Enrichment & Validation:**
- 30 validation rules with self-healing auto-correction
- Persona matching and boost calculation
- Follow-up message generation
- Semantic tone analysis and quality scoring
- Hook detection and anti-detection patterns

**Layer 4 - Data Access & Utilities:**
- SQL query abstraction and database access
- Shared data structures and type definitions
- Weight calculation algorithms
- Vose Alias weighted random selection
- Logging and monitoring infrastructure

### Key Design Principles

1. **Separation of Concerns:** Each module has a single, well-defined responsibility
2. **Testability:** Modules can be tested in isolation with fixtures
3. **Reusability:** Core logic modules (Layer 2-3) can be imported and reused
4. **Maintainability:** Clear boundaries make changes predictable and safe
5. **Extensibility:** New content types, validation rules, or pools can be added modularly

### Test Architecture

The test suite mirrors the modular structure:

```
tests/
├── fixtures/                    # Shared test data
│   ├── creator_fixtures.py      # Mock creator profiles
│   ├── caption_fixtures.py      # Mock caption data
│   └── schedule_fixtures.py     # Mock schedule items
│
├── test_volume_optimizer.py    # Layer 2: Volume optimization (171 tests)
├── test_validation.py           # Layer 3: Validation rules
├── test_persona_matching.py    # Layer 3: Persona boost calculation
└── test_integration.py          # Full pipeline integration tests
```

**Test Coverage:**
- `test_volume_optimizer.py`: 95%+ coverage, 171 tests across 5 volume levels
- `test_validation.py`: 30 validation rules tested individually
- `test_integration.py`: End-to-end pipeline tests with real database

---

## Module Dependency Diagram

```
                                    ┌─────────────────────────┐
                                    │generate_schedule.py     │
                                    │  Main Entry Point       │
                                    │  - Orchestrates 9 steps │
                                    └───────────┬─────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
        │ContentTypeRegistry│       │ScheduleUniqueness │       │  ContentAssigner  │
        │ (20+ types)       │       │    Engine         │       │  (unified logic)  │
        │- SchedulableType  │       │- timing variance  │       │- multi-pool mgmt  │
        │- REGISTRY global  │       │- fingerprinting   │       │- 20+ type support │
        │- page filtering   │       │- deduplication    │       │- rotation control │
        └───────────────────┘       └───────────────────┘       └───────────────────┘
                    │                           │                           │
                    └───────────────────────────┼───────────────────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
        │ select_captions.py│       │hook_detection.py  │       │    weights.py     │
        │- StratifiedPools  │       │- 7 hook types     │       │- pool formulas    │
        │- PROVEN pool      │       │- pattern matching │       │- earnings weight  │
        │- GLOBAL_EARNER    │       │- rotation penalty │       │- freshness weight │
        │- DISCOVERY pool   │       │- diversity check  │       │- persona weight   │
        │- VoseAlias select │       └───────────────────┘       └───────────────────┘
        └───────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────────────────────────────────────────┐
        │                          validate_schedule.py                              │
        │  - ValidationRule enum (V001-V031)                                        │
        │  - Auto-correction system (move_slot, swap_caption, adjust_timing, etc.) │
        │  - Self-healing validation loop (max 2 passes)                            │
        │  - Extended content type rules (page type, spacing, limits)               │
        └───────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
                                    ┌─────────────────────────┐
                                    │   Database Layer        │
                                    │   SQLite (97 MB)        │
                                    │  - creators             │
                                    │  - caption_bank         │
                                    │  - mass_messages        │
                                    │  - vault_matrix         │
                                    │  - creator_personas     │
                                    │  - schedule_templates   │
                                    └─────────────────────────┘
```

---

## Content Type Registry Architecture

### Overview

The **Content Type Registry** (`content_type_registry.py`) provides a centralized, strongly-typed registry of all 20+ schedulable content types in the EROS system. This architecture ensures consistency, type safety, and easy extension of new content types.

### Core Data Structure

```python
@dataclass(frozen=True)
class SchedulableContentType:
    type_id: str                    # Unique identifier (e.g., "ppv", "vip_post")
    name: str                       # Display name
    channel: Channel                # "mass_message", "feed", "direct", "poll", "gamification"
    page_type_filter: PageTypeFilter  # "paid", "free", "both"
    priority_tier: int              # 1-5 (1=highest priority for slot allocation)
    min_spacing_hours: float        # Minimum hours between sends
    max_daily: int                  # Maximum sends per day
    max_weekly: int                 # Maximum sends per week
    requires_flyer: bool            # Whether content needs media attachment
    has_follow_up: bool             # Whether content can have follow-up bump
    description: str                # Short description
    theme_guidance: str             # Guidance for slots without captions
```

### Registry Singleton

```python
# Global registry instance pre-populated with 20 content types
REGISTRY = ContentTypeRegistry()

# Query methods
ppv_type = REGISTRY.get("ppv")
paid_types = REGISTRY.get_types_for_page("paid")
tier1_types = REGISTRY.get_types_by_priority(1)
is_valid = REGISTRY.validate_for_page("vip_post", "free")  # False - paid only
```

### Content Type Tiers

| Tier | Priority | Types | Purpose |
|------|----------|-------|---------|
| 1 | Direct Revenue | ppv, ppv_follow_up, bundle, flash_bundle, snapchat_bundle | Primary monetization |
| 2 | Feed/Wall | vip_post, first_to_tip, link_drop, normal_post_bump, renew_on_post, game_post, flyer_gif_bump, descriptive_bump, wall_link_drop, live_promo | Engagement & visibility |
| 3 | Engagement | dm_farm, like_farm, text_only_bump | Algorithmic boost |
| 4 | Retention | renew_on_mm, expired_subscriber | Subscriber retention |

### Page Type Restrictions

**Paid-Only Types:**
- `vip_post` - Exclusive VIP tier content
- `renew_on_post` - Subscription renewal reminder post
- `renew_on_mm` - Renewal reminder via mass message
- `expired_subscriber` - Win-back message for expired subs

**Both Pages:**
- All other types valid on both paid and free pages

### Integration with Generate Schedule

The registry is used throughout the pipeline:

1. **Step 4 (Build Structure):** Checks `min_spacing_hours`, `max_daily`, `max_weekly` to build valid slot structures
2. **Step 5 (Assign Captions):** Filters by `page_type_filter` and `channel`
3. **Step 6 (Follow-ups):** Uses `has_follow_up` flag to determine eligibility
4. **Step 9 (Validation):** Validates against `page_type_filter`, spacing rules, and volume limits

---

## Schedule Uniqueness Engine Architecture

### Overview

The **Schedule Uniqueness Engine** (`schedule_uniqueness.py`) ensures each creator receives a 100% unique schedule through timing variance, historical performance weighting, and fingerprint-based deduplication.

### Core Components

```python
class ScheduleUniquenessEngine:
    # Variance configuration
    TIMING_VARIANCE_MIN: int = -10  # minutes
    TIMING_VARIANCE_MAX: int = 10   # minutes
    VARIANCE_PROBABILITY: float = 0.85  # 85% of slots get variance

    # Historical weighting factors
    PERFORMANCE_WEIGHT: float = 0.6
    RECENCY_WEIGHT: float = 0.2
    DIVERSITY_WEIGHT: float = 0.2

    # Lookback periods
    RECENT_WEEKS_LOOKBACK: int = 4  # 28 days
    HISTORICAL_DAYS_LOOKBACK: int = 90  # 3 months
```

### Uniqueness Mechanisms

#### 1. Timing Variance (Organic Feel)

Applies random ±7-10 minute variance to 85% of slots:

```python
def apply_timing_variance(slots):
    for slot in slots:
        if random.random() < 0.85:
            variance_minutes = random.randint(-10, 10)
            new_time = slot.time + timedelta(minutes=variance_minutes)
            slot.time = new_time
            slot.timing_variance_applied = variance_minutes
    return slots
```

**Purpose:** Makes send patterns appear organic and unpredictable to avoid detection.

#### 2. Historical Performance Weighting

Weights content selection based on creator-specific historical success:

```python
def apply_historical_weighting(content_pool, slot):
    slot_hour = slot.hour
    slot_day = slot.day_of_week

    for content in content_pool:
        base_weight = content.performance_score / 100.0

        # Timing bonus from historical patterns
        timing_bonus = get_timing_bonus(slot_hour, slot_day)  # 0-0.5

        # Recency penalty for recently used
        recency_penalty = 0.3 if content.id in recent_used else 0.0

        # Diversity bonus for underused types
        diversity_bonus = 0.15 if content.type_count == 0 else 0.05

        # Final weight
        content.uniqueness_weight = (
            base_weight * 0.6 +
            timing_bonus * 0.2 +
            (1 - recency_penalty) * 0.2 +
            diversity_bonus
        )

    return content_pool
```

**Purpose:** Leverages creator-specific patterns while maintaining freshness.

#### 3. Schedule Fingerprinting

Generates SHA-256 hash of schedule structure for duplicate detection:

```python
def generate_fingerprint(slots):
    fingerprint_data = []

    for slot in sorted(slots, key=lambda s: (s.date, s.time)):
        slot_data = (
            str(slot.content_type),
            str(slot.content_id),
            str(slot.date),
            str(slot.time)
        )
        fingerprint_data.append("|".join(slot_data))

    fingerprint_string = "\n".join(fingerprint_data)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]
```

**Purpose:** Prevents identical schedules across weeks.

#### 4. Uniqueness Scoring

Calculates a 0-100 score based on multiple factors:

```python
def calculate_uniqueness_score(slots):
    score = 100.0

    # Penalty for cross-week caption duplicates (max -30)
    duplicate_ratio = len(duplicates) / len(total_captions)
    score -= duplicate_ratio * 30

    # Bonus for content type diversity (max +10)
    unique_types = len(set(content_types))
    score += min(10, unique_types * 2)

    # Penalty for insufficient timing variance (max -10)
    variance_ratio = variance_applied / total_slots
    if variance_ratio < 0.7:
        score -= (0.7 - variance_ratio) * 10

    return max(0, round(score, 1))
```

### UniquenessMetrics Output

```python
@dataclass
class UniquenessMetrics:
    fingerprint: str                        # 16-char SHA-256 hash
    uniqueness_score: float                 # 0-100
    timing_variance_applied: int            # Number of slots with variance
    historical_weight_factor: float         # Average historical weighting
    cross_week_duplicates: int              # Captions also used in recent weeks
    content_type_distribution: dict[str, int]  # Type -> count mapping
```

### Integration Flow

```
generate_schedule.py
    ↓
1. Build base slots (Step 4)
    ↓
2. Load historical patterns
    engine.load_historical_patterns()
    ↓
3. Apply historical weighting to content pools
    weighted_pool = engine.apply_historical_weighting(pool, slot)
    ↓
4. Assign captions with weighted selection (Step 5)
    ↓
5. Apply timing variance
    varied_slots = engine.apply_timing_variance(slots)
    ↓
6. Ensure uniqueness (re-shuffle if duplicate detected)
    unique_slots = engine.ensure_uniqueness(varied_slots, max_attempts=5)
    ↓
7. Generate metrics
    metrics = engine.get_metrics(unique_slots)
    ↓
8. Save fingerprint to database
    schedule_templates.fingerprint = metrics.fingerprint
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

### Step 5: ASSIGN CAPTIONS - Pool-Based Selection with Earnings

**Purpose:** Assign captions to slots using stratified pool-based selection with earnings optimization and hook diversity.

**Inputs:**
- Time slots from Step 4
- Stratified caption pools from database
- Creator persona profile

**Outputs:**
- Schedule items with assigned captions
- Pool distribution metrics (PROVEN/GLOBAL_EARNER/DISCOVERY)

**Pool Classification:**

Captions are stratified into 3 pools per content type:

```python
@dataclass
class StratifiedPools:
    content_type_id: int
    type_name: str
    proven: list[Caption]           # creator_times_used >= 3 AND creator_avg_earnings > 0
    global_earners: list[Caption]   # global_times_used >= 3 AND global_avg_earnings > 0
    discovery: list[Caption]        # All others (new imports, under-tested)
```

**Selection Strategy by Slot Type:**

| Slot Type | Pools Used | Use Case |
|-----------|------------|----------|
| **Premium** | PROVEN only | Prime time slots (6PM, 9PM) - highest earners |
| **Standard** | PROVEN + GLOBAL_EARNER | Normal PPV slots - proven performance |
| **Discovery** | DISCOVERY (prioritized) | Exploration slots - test new content |

**Weight Formula (v2.1):**

```python
def calculate_weight(caption, pool_type, content_type_avg_earnings, max_earnings, persona_boost):
    """
    Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery Bonus(10%)
    """

    # 1. Earnings component (60%) - pool-specific
    if pool_type == POOL_PROVEN:
        earnings_score = caption.creator_avg_earnings / max_earnings if max_earnings > 0 else 0.5
    elif pool_type == POOL_GLOBAL_EARNER:
        earnings_score = (caption.global_avg_earnings or 0) / max_earnings if max_earnings > 0 else 0.3
    else:  # DISCOVERY
        earnings_score = 0.1  # Base score for untested

    # 2. Freshness component (15%)
    freshness_score = caption.freshness_score / 100.0

    # 3. Persona component (15%)
    persona_score = (persona_boost - 0.95) / 0.45  # Normalize 0.95-1.4 to 0-1

    # 4. Discovery bonus (10%)
    discovery_bonus = 1.0
    if pool_type == POOL_DISCOVERY:
        # Prioritize recent imports
        if caption.source == "external_import" and caption.is_recent_import:
            discovery_bonus = 1.5
        # Boost high global earners
        elif caption.global_avg_earnings and caption.global_avg_earnings > content_type_avg_earnings:
            discovery_bonus = 1.3

    # Weighted sum
    weight = (
        earnings_score * 0.60 +
        freshness_score * 0.15 +
        persona_score * 0.15 +
        discovery_bonus * 0.10
    )

    return max(0.01, weight)
```

**Hook Detection & Rotation:**

To prevent detectable patterns, Step 5 detects and rotates hook types:

```python
HOOK_TYPES = ["curiosity", "personal", "exclusivity", "recency", "question", "direct", "teasing"]
SAME_HOOK_PENALTY = 0.70  # 30% penalty for consecutive same hook

hook_type, confidence = detect_hook_type(caption_text)
if last_hook_type is not None and hook_type == last_hook_type:
    caption.final_weight *= SAME_HOOK_PENALTY  # Reduce likelihood of selection
```

**ContentAssigner Integration:**

For 20+ content types, `ContentAssigner` provides unified assignment:

```python
class ContentAssigner:
    """Unified content assignment engine for all content types."""

    def __init__(self, conn, creator_id, page_type, persona):
        self.conn = conn
        self.creator_id = creator_id
        self.page_type = page_type
        self.persona = persona
        self._caption_pools = {}  # Stratified pools for PPV types
        self._content_pools = {}  # Content pools for other types

    def load_all_pools(self):
        """Pre-load pools for all valid content types."""
        valid_types = REGISTRY.get_types_for_page(self.page_type)
        for content_type in valid_types:
            if content_type.type_id in ("ppv", "ppv_follow_up"):
                # Use stratified pools
                self._caption_pools[content_type.type_id] = load_stratified_pools(...)
            else:
                # Use content loaders
                self._content_pools[content_type.type_id] = load_content_by_type(...)

    def assign_content_to_slot(self, slot):
        """Assign content to a slot, avoiding duplicates."""
        content_type = slot.get("content_type")

        if content_type in ("ppv", "ppv_follow_up"):
            return self._assign_ppv_content(slot)
        else:
            pool = self._content_pools.get(content_type, [])
            available = [c for c in pool if c.id not in self._used_content_ids]
            return self._weighted_select(available)

    def enforce_rotation(self, assigned_slots):
        """Ensure no 3x consecutive same content type."""
        # Checks recent_types and swaps if violation detected
        ...
```

**Selection Flow:**

```
1. Load stratified pools for all content types
   ↓
2. For each slot:
   a. Determine slot tier (premium/standard/discovery)
   b. Select appropriate pool(s)
   c. Apply historical weighting (uniqueness engine)
   d. Detect hook type
   e. Apply hook rotation penalty if needed
   f. Weight-based selection using Vose Alias
   g. Mark content as used
   ↓
3. Enforce rotation rules (no 3x consecutive same type)
   ↓
4. Return assigned slots with pool distribution metrics
```

**Vose Alias Method (O(1) selection):**

```python
class VoseAliasSelector:
    """Weighted random selection using Vose's Alias Method."""

    def __init__(self, items, weight_func):
        # Preprocessing: O(n)
        weights = [weight_func(item) for item in items]
        total = sum(weights)
        prob = [w * len(items) / total for w in weights]

        # Build alias table
        self.prob = [0.0] * len(items)
        self.alias = [0] * len(items)
        small, large = [], []
        for i, p in enumerate(prob):
            (small if p < 1.0 else large).append(i)

        while small and large:
            l, g = small.pop(), large.pop()
            self.prob[l] = prob[l]
            self.alias[l] = g
            prob[g] = (prob[g] + prob[l]) - 1.0
            (small if prob[g] < 1.0 else large).append(g)

        for g in large: self.prob[g] = 1.0
        for l in small: self.prob[l] = 1.0
        self.items = items

    def select(self):
        # Selection: O(1)
        i = random.randint(0, len(self.items) - 1)
        return self.items[i if random.random() < self.prob[i] else self.alias[i]]
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

### Step 9: VALIDATE & AUTO-CORRECT

**Purpose:** Run all validators to ensure schedule meets business rules with automatic correction loop.

**Inputs:**
- Complete schedule from previous steps
- Page type (paid/free)
- Week start date
- Volume targets
- Available caption pool (for swaps)

**Outputs:**
- `ValidationResult` with validated items and any remaining issues
- Auto-corrected schedule (if corrections applied)
- Correction summary

**Validation Rules (v2.1):**

#### Core Rules (V001-V019)

| Rule | Name | Severity | Auto-Correctable |
|------|------|----------|------------------|
| V001 | ppv_spacing | ERROR if <3hr, WARNING if <4hr | ✅ Move slot |
| V002 | freshness_minimum | ERROR if <25, WARNING if <30 | ✅ Swap caption |
| V003 | followup_timing | WARNING if outside 15-45min | ✅ Adjust timing |
| V004 | duplicate_captions | ERROR | ✅ Swap caption |
| V005 | vault_availability | WARNING | ❌ Manual review |
| V006 | volume_compliance | WARNING | ❌ Manual review |
| V008 | wall_post_spacing | ERROR if <1hr, WARNING if <2hr | ✅ Move slot |
| V009 | preview_ppv_linkage | ERROR if after PPV | ✅ Move slot |
| V010 | poll_spacing | ERROR if <1 day | ✅ Move slot |
| V011 | poll_duration | ERROR if not 24/48/72hr | ❌ Manual review |
| V012 | game_wheel_validity | WARNING | ❌ Manual review |
| V013 | wall_post_volume | WARNING if >4/day | ❌ Manual review |
| V014 | poll_volume | WARNING if >3/week | ❌ Manual review |
| V015 | hook_rotation | WARNING if consecutive same | ❌ Info only |
| V016 | hook_diversity | INFO if <4 types/week | ❌ Info only |
| V017 | content_rotation | INFO if 3+ consecutive | ❌ Info only |

#### Extended Content Type Rules (V020-V031)

| Rule | Name | Severity | Auto-Correctable |
|------|------|----------|------------------|
| V020 | page_type_violation | ERROR | ✅ Remove item |
| V021 | vip_post_spacing | ERROR if <24hr | ✅ Move slot |
| V022 | link_drop_spacing | WARNING if <4hr | ✅ Move slot |
| V023 | engagement_daily_limit | WARNING if >2/day | ✅ Move to next day |
| V024 | engagement_weekly_limit | WARNING if >10/week | ✅ Remove item |
| V025 | retention_timing | INFO if not days 5-7 | ❌ Info only |
| V026 | bundle_spacing | ERROR if <24hr | ✅ Move slot |
| V027 | flash_bundle_spacing | ERROR if <48hr | ✅ Move slot |
| V028 | game_post_weekly | WARNING if >1/week | ✅ Remove item |
| V029 | bump_variant_rotation | WARNING if 3x consecutive | ✅ Swap content type |
| V030 | content_type_rotation | INFO if 3x consecutive | ❌ Info only |
| V031 | placeholder_warning | INFO if no caption | ❌ Info only |

**Auto-Correction Actions:**

```python
class AutoCorrectionAction(Enum):
    MOVE_SLOT = "move_slot"              # Move item to new time slot
    SWAP_CAPTION = "swap_caption"        # Replace caption with another
    ADJUST_TIMING = "adjust_timing"      # Adjust follow-up timing
    REMOVE_ITEM = "remove_item"          # Remove item from schedule
    MOVE_TO_NEXT_DAY = "move_to_next_day"  # Move item to next day at same time
    SWAP_CONTENT_TYPE = "swap_content_type"  # Change content type to alternative
```

**Self-Healing Validation Loop:**

```python
def validate_with_corrections(
    items,
    volume_target=None,
    vault_types=None,
    page_type="free",
    week_start=None,
    max_passes=2,
    available_captions=None
):
    """
    Validate schedule with automatic correction loop.

    Process:
    1. Run validation (all rules V001-V031)
    2. Collect auto-correctable issues
    3. Apply corrections
    4. Re-validate
    5. Repeat until valid or max_passes reached

    Returns:
        ValidationResult with final state and correction summary
    """
    corrections_applied = []

    for pass_num in range(1, max_passes + 1):
        # Run full validation
        result = validator.validate(items, volume_target, vault_types, page_type, week_start)

        if result.is_valid or result.error_count == 0:
            # Add correction summary
            if corrections_applied:
                result.add_info("auto_corrections", f"Applied {len(corrections_applied)} corrections")
            return result

        # Collect auto-correctable issues
        auto_fixable = [issue for issue in result.issues if issue.auto_correctable]

        if not auto_fixable:
            return result  # No fixable issues, return current state

        # Apply corrections
        for issue in auto_fixable:
            if issue.correction_action == "move_slot":
                # Parse new_date and new_time from correction_value JSON
                new_slot = json.loads(issue.correction_value)
                item.scheduled_date = new_slot["new_date"]
                item.scheduled_time = new_slot["new_time"]
                corrections_applied.append(f"move_slot(item_{issue.item_ids[0]})")

            elif issue.correction_action == "swap_caption":
                # Find fresh caption of same content type
                if available_captions:
                    matching = [c for c in available_captions
                               if c.content_type_id == item.content_type_id
                               and c.caption_id not in used_ids
                               and c.freshness_score >= min_freshness]
                    if matching:
                        new_caption = matching[0]
                        item.caption_id = new_caption.caption_id
                        item.caption_text = new_caption.caption_text
                        item.freshness_score = new_caption.freshness_score
                        corrections_applied.append(f"swap_caption(item_{item.item_id})")

            elif issue.correction_action == "adjust_timing":
                # Adjust to target minutes (default 25) after parent
                target_minutes = int(issue.correction_value) if issue.correction_value else 25
                parent_dt = parse_datetime(parent_item)
                new_dt = parent_dt + timedelta(minutes=target_minutes)
                item.scheduled_time = new_dt.strftime("%H:%M")
                corrections_applied.append(f"adjust_timing(item_{item.item_id})")

            elif issue.correction_action == "remove_item":
                # Remove item from schedule
                items_to_remove.add(issue.item_ids[0])
                corrections_applied.append(f"remove_item(item_{issue.item_ids[0]})")

            elif issue.correction_action == "move_to_next_day":
                # Move to next day at same time
                current_date = datetime.strptime(item.scheduled_date, "%Y-%m-%d").date()
                next_date = current_date + timedelta(days=1)
                item.scheduled_date = next_date.strftime("%Y-%m-%d")
                corrections_applied.append(f"move_to_next_day(item_{item.item_id})")

            elif issue.correction_action == "swap_content_type":
                # Swap to alternative content type
                item.content_type_name = issue.correction_value
                corrections_applied.append(f"swap_content_type(item_{item.item_id})")

        # Apply removals
        items = [item for item in items if item.item_id not in items_to_remove]

        # Continue to next pass if not final
        if pass_num < max_passes:
            continue

    # Final validation after all passes
    final_result = validator.validate(items, volume_target, vault_types, page_type, week_start)
    if corrections_applied:
        final_result.add_info("auto_corrections",
                             f"Applied {len(corrections_applied)} corrections: {', '.join(corrections_applied)}")

    return final_result
```

**ValidationIssue Structure (v2.1):**

```python
@dataclass(frozen=True)
class ValidationIssue:
    rule_name: str
    severity: str                 # "error", "warning", "info"
    message: str
    item_ids: tuple[int, ...]
    # Auto-correction fields (new in v2.1)
    auto_correctable: bool = False
    correction_action: str = ""   # Action type (see AutoCorrectionAction)
    correction_value: str = ""    # JSON or string value for correction
```

**Validation Flow:**

```
1. Initial validation (all V001-V031 rules)
   ↓
2. Errors found?
   ├─ No → Return valid schedule
   └─ Yes → Check auto-correctable
       ↓
3. Collect auto-correctable issues
   ↓
4. Apply corrections (pass 1)
   ├─ move_slot
   ├─ swap_caption
   ├─ adjust_timing
   ├─ remove_item
   ├─ move_to_next_day
   └─ swap_content_type
   ↓
5. Re-validate (pass 2)
   ↓
6. Still errors?
   ├─ No → Return corrected schedule
   └─ Yes → Return with remaining issues
   ↓
7. Add correction summary to result
```

**Example Validation Output:**

```json
{
  "is_valid": true,
  "error_count": 0,
  "warning_count": 1,
  "info_count": 3,
  "issues": [
    {
      "rule_name": "hook_diversity",
      "severity": "info",
      "message": "Only 3 hook types used (curiosity, personal, direct). Target: 4+",
      "item_ids": [],
      "auto_correctable": false
    },
    {
      "rule_name": "auto_corrections",
      "severity": "info",
      "message": "Applied 2 corrections: move_slot(item_5), swap_caption(item_12->caption_847)",
      "item_ids": [],
      "auto_correctable": false
    }
  ]
}
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

- **Current Version:** EROS Schedule Generator v2.1
- **Pipeline Version:** 9-step (production implementation)
- **Database Schema:** v2.6 (28 tables, 20 views, 8 triggers, 84 indexes)
- **Key Modules:**
  - `content_type_registry.py` (730 lines) - Central registry of 20+ content types
  - `schedule_uniqueness.py` (775 lines) - Timing variance & fingerprinting
  - `select_captions.py` (1,934 lines) - Pool-based selection with ContentAssigner
  - `validate_schedule.py` (2,078 lines) - 31 validation rules with auto-correction
- **Last Updated:** 2025-12-09

### v2.1 Key Features

1. **Content Type Registry** - Centralized metadata for 20+ schedulable content types with page type filtering, spacing rules, and volume limits
2. **Schedule Uniqueness Engine** - Ensures 100% unique schedules through timing variance (±10min), historical weighting, and SHA-256 fingerprinting
3. **Pool-Based Earnings Selection** - Stratified pools (PROVEN, GLOBAL_EARNER, DISCOVERY) with 60% earnings weight, 15% freshness, 15% persona, 10% discovery bonus
4. **ContentAssigner** - Unified assignment engine for all 20+ content types with rotation enforcement and deduplication
5. **Hook Detection & Rotation** - Detects 7 hook types (curiosity, personal, exclusivity, recency, question, direct, teasing) and applies 30% penalty for consecutive duplicates
6. **Extended Validation Rules** - 31 total rules (V001-V031) including page type compliance, spacing rules, and volume limits
7. **Auto-Correction System** - Self-healing validation loop with 6 correction actions (move_slot, swap_caption, adjust_timing, remove_item, move_to_next_day, swap_content_type)
8. **Multi-Pass Validation** - Up to 2 validation passes with automatic corrections applied between passes

### v2.0 → v2.1 Migration

**Breaking Changes:**
- None - v2.1 is fully backward compatible with v2.0

**New Dependencies:**
- `content_type_registry.py` - Required for all schedule generation
- `schedule_uniqueness.py` - Required for uniqueness enforcement
- `hook_detection.py` - Required for hook rotation

**Database Updates:**
- `schedule_templates` table: Added `fingerprint` column (TEXT, 16 chars)
- No schema migrations required for existing data

**Configuration Updates:**
- None - all new features use sensible defaults
