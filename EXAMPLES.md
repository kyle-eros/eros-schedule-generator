# EROS Schedule Generator v2.1 - Examples

Practical examples for common use cases with the EROS Schedule Generator v2.1.

## Table of Contents
- [Quick Schedule Generation](#quick-schedule-generation)
- [Full Semantic Analysis Mode](#full-semantic-analysis-mode)
- [Batch Processing](#batch-processing)
- [Python API Usage](#python-api-usage)
- [Content Type Registry Examples](#content-type-registry-examples)
- [Schedule Uniqueness Engine Examples](#schedule-uniqueness-engine-examples)
- [ContentAssigner Examples](#contentassigner-examples)
- [Caption Selection Examples](#caption-selection-examples)
- [Pool-Based Caption Selection Examples](#pool-based-caption-selection-examples)
- [Validation Examples](#validation-examples)
- [Extended Validation Examples (V020-V031)](#extended-validation-examples-v020-v031)
- [Hook Detection Examples](#hook-detection-examples)
- [Volume Optimization](#volume-optimization)
- [Content Strategy](#content-strategy)
- [Error Handling](#error-handling)

---

## Quick Schedule Generation

### Basic Usage (CLI)
Generate a 7-day schedule for a creator:

```bash
# Auto-saves to ~/Developer/EROS-SD-MAIN-PROJECT/schedules/missalexa/2025-W02.md
python scripts/generate_schedule.py --creator missalexa --week 2025-W02
```

### v2.1 CLI Examples

#### Generate with Specific Content Types
```bash
# Generate schedule with only PPV and bundles (v2.1)
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 \
    --content-types "ppv bundle"

# Include VIP posts and engagement content
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 \
    --content-types "ppv vip_post dm_farm like_farm"
```

#### List Available Content Types
```bash
# List all 20+ content types (v2.1)
python scripts/generate_schedule.py --list-content-types

# Output shows:
# - Content type ID
# - Channel (mass_message, feed, direct)
# - Page type restrictions (paid/free/both)
# - Min spacing, max daily/weekly limits
```

#### Page Type Specification
```bash
# Generate for paid page (enables paid-only content types like vip_post) (v2.1)
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 \
    --page-type paid

# Generate for free page (excludes vip_post, renew_on_post, etc.) (v2.1)
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 \
    --page-type free
```

#### Quick Mode vs Full Mode
```bash
# Quick mode - pattern-based, no semantic analysis (faster)
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 --quick

# Full mode - with LLM semantic analysis (default in v2.1)
python scripts/generate_schedule.py --creator missalexa --week 2025-W02

# Explicit full mode
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 --mode full
```

### Print to Console
```bash
# Print to stdout instead of saving
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 --stdout
```

### Using Creator ID
```bash
# Use creator_id instead of page name
python scripts/generate_schedule.py --creator-id abc123-def456 --week 2025-W02
```

### Custom Output Location
```bash
# Save to specific file
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 \
    --output ~/custom/path/schedule.md
```

### Skip Placeholders
```bash
# Skip slots without captions instead of generating placeholders (v2.1)
python scripts/generate_schedule.py --creator missalexa --week 2025-W02 \
    --no-placeholders

# Useful when caption pools are limited
```

### Output Example
```json
{
  "schedule": [
    {
      "item_id": 1,
      "slot_id": "mon-ppv-1",
      "scheduled_date": "2025-01-06",
      "scheduled_time": "10:07",
      "message_type": "ppv",
      "caption_id": 4521,
      "caption_text": "guess what I just filmed for you baby...",
      "content_type": "bundle",
      "price": 18.00,
      "persona_boost": 1.25,
      "freshness_score": 87.3,
      "hook_type": "curiosity",
      "pool": "proven",
      "payday_multiplier": 1.0
    },
    {
      "item_id": 2,
      "slot_id": "mon-bump-1",
      "scheduled_date": "2025-01-06",
      "scheduled_time": "10:33",
      "message_type": "bump",
      "caption_id": 4521,
      "caption_text": "only 2 hours left to grab this...",
      "content_type": "bundle",
      "price": 18.00,
      "persona_boost": 1.35,
      "freshness_score": 87.3,
      "hook_type": "urgency",
      "pool": "proven",
      "payday_multiplier": 1.0
    }
  ],
  "summary": {
    "total_items": 28,
    "ppv_count": 14,
    "bump_count": 14,
    "validation_passed": true,
    "corrections_applied": 2
  },
  "metadata": {
    "creator_name": "missalexa",
    "week": "2025-W02",
    "generated_at": "2025-01-06T09:32:17Z"
  }
}
```

---

## Full Semantic Analysis Mode

### With LLM Enhancement
Enable Claude's semantic analysis for persona matching:

```bash
# Auto-saves to ~/Developer/EROS-SD-MAIN-PROJECT/schedules/context/missalexa/2025-W02_context.md
python scripts/prepare_llm_context.py --creator missalexa --week 2025-W02 --mode full
```

### Print to Console
```bash
# Print to stdout for review
python scripts/prepare_llm_context.py --creator missalexa --week 2025-W02 \
    --mode full --stdout
```

### Workflow
1. `prepare_llm_context.py` creates structured context
2. Claude reads the context and applies semantic reasoning
3. Claude identifies captions needing persona boost adjustments
4. Schedule is generated with enhanced persona matching

### What Full Mode Provides
- Semantic tone detection (sarcasm, subtext, emotion)
- Context-aware persona boost scoring (1.00-1.40x)
- Hook diversity analysis across the week
- Cultural moment awareness for timing optimization

---

## Batch Processing

### Generate for Multiple Creators
```bash
# Generate schedules for all active creators
python scripts/generate_schedule.py --batch --week 2025-W02 \
    --output-dir ~/Developer/EROS-SD-MAIN-PROJECT/schedules/batch/
```

### Validate All Schedules
```bash
# Validate all schedules in directory
for f in ~/Developer/EROS-SD-MAIN-PROJECT/schedules/*/2025-W02.json; do
    python scripts/validate_schedule.py --input "$f"
done
```

### Batch with Custom Filters
```python
# Python script for batch generation with filters
from scripts.generate_schedule import generate_schedule_for_creator
from scripts.database import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all Tier 1 creators
cursor.execute("""
    SELECT creator_id, page_name
    FROM creators
    WHERE is_active = 1 AND performance_tier = 1
""")

for creator_id, page_name in cursor.fetchall():
    print(f"Generating schedule for {page_name}...")
    result = generate_schedule_for_creator(
        creator_name=page_name,
        week="2025-W02",
        mode="quick"
    )
    print(f"  ✓ {result.total_items} items generated")
```

---

## Python API Usage

### Generate Schedule Programmatically
```python
from scripts.generate_schedule import generate_schedule_for_creator
from scripts.shared_context import PersonaProfile
from scripts.database import DB_PATH

# Generate schedule
result = generate_schedule_for_creator(
    creator_name="missalexa",
    week="2025-W02",
    mode="quick"
)

# Access results
print(f"Total items: {result.total_items}")
print(f"PPV count: {result.ppv_count}")
print(f"Validation passed: {result.validation_passed}")

# Iterate schedule items
for item in result.schedule_items:
    print(f"{item.scheduled_time}: {item.caption_text[:50]}...")
    print(f"  Content: {item.content_type}, Price: ${item.price}")
    print(f"  Persona boost: {item.persona_boost:.2f}x")
```

### Load Creator Profile
```python
import sqlite3
from scripts.database import DB_PATH
from scripts.shared_context import CreatorProfile

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Load creator profile
cursor.execute("""
    SELECT creator_id, page_name, display_name, page_type,
           subscription_price, current_active_fans, performance_tier,
           current_total_earnings, current_avg_spend_per_txn,
           current_avg_earnings_per_fan
    FROM creators
    WHERE page_name = ?
""", ("missalexa",))

row = cursor.fetchone()
profile = CreatorProfile(
    creator_id=row[0],
    page_name=row[1],
    display_name=row[2],
    page_type=row[3],
    subscription_price=row[4],
    current_active_fans=row[5],
    performance_tier=row[6],
    current_total_earnings=row[7],
    current_avg_spend_per_txn=row[8],
    current_avg_earnings_per_fan=row[9]
)

print(f"Creator: {profile.display_name}")
print(f"Fans: {profile.current_active_fans:,}")
print(f"Tier: {profile.performance_tier}")
```

---

## Content Type Registry Examples

The Content Type Registry provides centralized metadata for all 20+ schedulable content types in v2.1.

### Get Content Type Metadata
```python
from content_type_registry import REGISTRY, get_registry

# Get all content types
all_types = REGISTRY.get_all()
print(f"Total types: {len(all_types)}")  # 20

# Get content type by ID
ppv = REGISTRY.get("ppv")
print(f"PPV min spacing: {ppv.min_spacing_hours}h")  # 3.0h
print(f"PPV max daily: {ppv.max_daily}")  # 5
print(f"PPV channel: {ppv.channel}")  # mass_message
print(f"PPV priority tier: {ppv.priority_tier}")  # 1

# Get VIP post (paid-only)
vip = REGISTRY.get("vip_post")
print(f"VIP page filter: {vip.page_type_filter}")  # paid
print(f"VIP valid for free page: {vip.is_valid_for_page('free')}")  # False
```

### Filter Content Types
```python
from content_type_registry import REGISTRY

# Get types valid for paid page
paid_types = REGISTRY.get_types_for_page("paid")
print(f"Paid page types: {len(paid_types)}")  # 20 (all types)

# Get types valid for free page
free_types = REGISTRY.get_types_for_page("free")
print(f"Free page types: {len(free_types)}")  # 16 (excludes paid-only)

# Validate content type for page
is_valid = REGISTRY.validate_for_page("vip_post", "free")  # False
is_valid = REGISTRY.validate_for_page("ppv", "free")  # True

# Get types by channel
mass_message_types = REGISTRY.get_types_by_channel("mass_message")
print(f"Mass message types: {[t.type_id for t in mass_message_types]}")
# ['ppv', 'ppv_follow_up', 'bundle', 'flash_bundle', 'snapchat_bundle',
#  'renew_on_mm', 'text_only_bump']

feed_types = REGISTRY.get_types_by_channel("feed")
print(f"Feed types: {[t.type_id for t in feed_types]}")
# ['vip_post', 'first_to_tip', 'link_drop', 'normal_post_bump', ...]

# Get types by priority tier
tier1_types = REGISTRY.get_types_by_priority(1)  # Direct Revenue types
print(f"Tier 1 (Direct Revenue): {[t.type_id for t in tier1_types]}")
# ['ppv', 'ppv_follow_up', 'bundle', 'flash_bundle', 'snapchat_bundle']

tier2_types = REGISTRY.get_types_by_priority(2)  # Feed/Wall types
print(f"Tier 2 (Feed/Wall): {[t.type_id for t in tier2_types]}")
# ['vip_post', 'first_to_tip', 'link_drop', ...]
```

### Check Content Type Properties
```python
from content_type_registry import REGISTRY

# Iterate all content types
for content_type in REGISTRY.get_all():
    print(f"{content_type.type_id:20} | Channel: {content_type.channel:14} | "
          f"Spacing: {content_type.min_spacing_hours:>5}h | "
          f"Max: {content_type.max_daily}/day")

    if content_type.page_type_filter != "both":
        print(f"  -> Page restriction: {content_type.page_type_filter.upper()}")

    if content_type.theme_guidance:
        print(f"  -> Theme: {content_type.theme_guidance}")

# Check if content type exists
if "bundle" in REGISTRY:
    bundle = REGISTRY.get("bundle")
    print(f"Bundle requires flyer: {bundle.requires_flyer}")  # True
    print(f"Bundle has follow-up: {bundle.has_follow_up}")  # True
```

---

## Schedule Uniqueness Engine Examples

The Schedule Uniqueness Engine ensures each creator receives a 100% unique schedule through timing variance, historical weighting, and cross-week deduplication.

### Apply Timing Variance
```python
from schedule_uniqueness import ScheduleUniquenessEngine
import sqlite3

# Initialize engine
conn = sqlite3.connect("database.db")
conn.row_factory = sqlite3.Row
engine = ScheduleUniquenessEngine(conn, creator_id="abc123-def456")

# Load historical patterns from database
engine.load_historical_patterns()

# Apply 7-10 minute variance to slots
slots = [
    {"time": "10:00", "date": "2025-01-06", "content_type": "ppv"},
    {"time": "14:00", "date": "2025-01-06", "content_type": "bundle"},
    {"time": "18:00", "date": "2025-01-06", "content_type": "ppv"},
]

varied_slots = engine.apply_timing_variance(slots)

# Check which slots got variance
for slot in varied_slots:
    variance = slot.get('timing_variance_applied', 0)
    if variance != 0:
        print(f"Slot at {slot['time']} shifted by {variance} minutes")
        print(f"  New time: {slot['scheduled_time']}")
```

### Apply Historical Weighting
```python
from schedule_uniqueness import ScheduleUniquenessEngine

engine = ScheduleUniquenessEngine(conn, creator_id)
engine.load_historical_patterns()

# Weight caption pool based on creator's historical performance
caption_pool = [
    {"caption_id": 1, "performance_score": 85, "content_type": "ppv"},
    {"caption_id": 2, "performance_score": 72, "content_type": "bundle"},
    {"caption_id": 3, "performance_score": 90, "content_type": "ppv"},
]

slot = {"time": "18:00", "date": "2025-01-06", "day_of_week": 0}  # Monday

# Apply historical weighting
weighted_pool = engine.apply_historical_weighting(caption_pool, slot)

# Check uniqueness weights
for item in weighted_pool:
    weight = item.get('uniqueness_weight', 1.0)
    print(f"Caption {item['caption_id']}: weight = {weight:.3f}")
```

### Generate Schedule Fingerprint
```python
from schedule_uniqueness import ScheduleUniquenessEngine

engine = ScheduleUniquenessEngine(conn, creator_id)
engine.load_historical_patterns()

# Generate fingerprint for schedule
slots = [
    {"content_type": "ppv", "content_id": 123, "scheduled_date": "2025-01-06", "time": "10:07"},
    {"content_type": "bundle", "content_id": 456, "scheduled_date": "2025-01-06", "time": "14:12"},
    {"content_type": "ppv", "content_id": 789, "scheduled_date": "2025-01-06", "time": "18:03"},
]

fingerprint = engine.generate_fingerprint(slots)
print(f"Schedule fingerprint: {fingerprint}")  # e.g., "a8b2c3d4e5f6g7h8"

# Check for duplicates against recent schedules
is_duplicate = engine.check_duplicate(fingerprint)
if is_duplicate:
    print("WARNING: This schedule matches a recent week!")
else:
    print("Schedule is unique!")
```

### Calculate Uniqueness Score
```python
from schedule_uniqueness import ScheduleUniquenessEngine

engine = ScheduleUniquenessEngine(conn, creator_id)
engine.load_historical_patterns()

# Calculate uniqueness score (0-100)
score = engine.calculate_uniqueness_score(slots)
print(f"Uniqueness score: {score}%")

# Breakdown:
# - Penalty for cross-week caption duplicates (max -30 points)
# - Bonus for content type diversity (max +10 points)
# - Penalty for slots without timing variance (max -10 points)

if score >= 85:
    print("Excellent uniqueness!")
elif score >= 70:
    print("Good uniqueness")
else:
    print("Consider refreshing caption pool")
```

### Get Comprehensive Metrics
```python
from schedule_uniqueness import ScheduleUniquenessEngine, UniquenessMetrics

engine = ScheduleUniquenessEngine(conn, creator_id)
engine.load_historical_patterns()

# Get full metrics
metrics = engine.get_metrics(slots)

print(f"Fingerprint: {metrics.fingerprint}")
print(f"Uniqueness Score: {metrics.uniqueness_score}%")
print(f"Timing Variance Applied: {metrics.timing_variance_applied} slots")
print(f"Historical Weight Factor: {metrics.historical_weight_factor:.3f}")
print(f"Cross-Week Duplicates: {metrics.cross_week_duplicates}")
print(f"Content Type Distribution:")
for content_type, count in metrics.content_type_distribution.items():
    print(f"  {content_type}: {count}")

# Convert to dict for JSON serialization
metrics_dict = metrics.to_dict()
import json
print(json.dumps(metrics_dict, indent=2))
```

### Ensure Uniqueness with Retries
```python
from schedule_uniqueness import ScheduleUniquenessEngine

engine = ScheduleUniquenessEngine(conn, creator_id)
engine.load_historical_patterns()

# Ensure uniqueness (with up to 5 retry attempts)
unique_slots = engine.ensure_uniqueness(slots, max_attempts=5)

# This will:
# 1. Generate fingerprint
# 2. Check against recent schedules
# 3. If duplicate, re-apply timing variance with new seed
# 4. Repeat up to max_attempts times
# 5. Return unique schedule or original if uniqueness can't be achieved

fingerprint = engine.generate_fingerprint(unique_slots)
print(f"Final fingerprint: {fingerprint}")
```

### Convenience Function
```python
from schedule_uniqueness import apply_uniqueness
import sqlite3

# One-line uniqueness application
conn = sqlite3.connect("database.db")
conn.row_factory = sqlite3.Row

slots = [...]  # Your schedule slots
creator_id = "abc123-def456"

# Apply all uniqueness operations
unique_slots, metrics = apply_uniqueness(slots, conn, creator_id)

print(f"Uniqueness Score: {metrics.uniqueness_score}%")
print(f"Fingerprint: {metrics.fingerprint}")
print(f"Variance Applied: {metrics.timing_variance_applied} slots")
```

---

## ContentAssigner Examples

The ContentAssigner provides unified content assignment for all 20+ content types with cross-type deduplication and rotation enforcement.

### Basic Content Assignment
```python
from select_captions import ContentAssigner
import sqlite3

# Initialize ContentAssigner
conn = sqlite3.connect("database.db")
conn.row_factory = sqlite3.Row

persona = {
    "primary_tone": "playful",
    "emoji_frequency": "moderate",
    "slang_level": "light"
}

assigner = ContentAssigner(
    conn=conn,
    creator_id="abc123-def456",
    page_type="paid",
    persona=persona,
    min_freshness=30.0
)

# Load all content pools (PPV + 19 other types)
assigner.load_all_pools()

# Assign content to each slot
schedule_slots = [
    {"slot_id": 1, "content_type": "ppv", "hour": 10, "date": "2025-01-06"},
    {"slot_id": 2, "content_type": "vip_post", "hour": 14, "date": "2025-01-06"},
    {"slot_id": 3, "content_type": "bundle", "hour": 18, "date": "2025-01-06"},
]

assigned_slots = []
for slot in schedule_slots:
    content = assigner.assign_content_to_slot(slot)
    if content:
        assigned_slots.append(content)
        if content.get('has_caption'):
            print(f"Assigned {content['content_type']}: {content.get('content_text', '')[:50]}...")
        else:
            print(f"Placeholder for {content['content_type']}: {content.get('theme_guidance', '')}")
    else:
        print(f"Failed to assign content for slot {slot['slot_id']}")
```

### Get Assignment Statistics
```python
from select_captions import ContentAssigner

# After assigning content to all slots
stats = assigner.get_assignment_stats()

print(f"Total Assigned: {stats['total_assigned']}")
print(f"Unique Content Used: {stats['unique_content_used']}")
print(f"\nBy Content Type:")
for content_type, count in stats['by_content_type'].items():
    print(f"  {content_type}: {count}")

print(f"\nCaption Pools Loaded: {stats['caption_pools_loaded']}")
print(f"Content Pools Loaded: {stats['content_pools_loaded']}")
```

### Ensure No Duplicates
```python
from select_captions import ContentAssigner

# Deduplicate assigned slots (prevents same caption used twice)
assigned_slots = [...]  # Assigned slots from previous step

deduplicated_slots = assigner.ensure_no_duplicates(assigned_slots)

# Check for changes
original_ids = {s.get('content_id') for s in assigned_slots if s.get('content_id')}
final_ids = {s.get('content_id') for s in deduplicated_slots if s.get('content_id')}

duplicates_replaced = len(original_ids) - len(final_ids)
print(f"Duplicates replaced: {duplicates_replaced}")
```

### Enforce Content Rotation
```python
from select_captions import ContentAssigner

# Ensure no 3x consecutive same content type
assigned_slots = [...]  # Assigned slots

rotated_slots = assigner.enforce_rotation(assigned_slots)

# Rotation rules:
# - If same content type appears 3x in a row
# - Swap the 3rd occurrence with a different type
# - Maintains engagement variety
```

### Handle Placeholders
```python
from select_captions import ContentAssigner

# When pools are exhausted, ContentAssigner creates placeholders
assigned_slots = [...]

placeholders = [s for s in assigned_slots if not s.get('has_caption', True)]

print(f"Placeholders: {len(placeholders)}")
for slot in placeholders:
    print(f"  Slot {slot.get('slot_id')}: {slot.get('content_type')}")
    print(f"    Theme: {slot.get('theme_guidance', 'No guidance')}")
    print(f"    Manual caption needed")
```

---

## Caption Selection Examples

### Select Captions with CLI
```bash
# Select 10 captions for a creator
python scripts/select_captions.py --creator missalexa --count 10

# Select premium captions (proven pool only)
python scripts/select_captions.py --creator missalexa --count 5 --slot-type premium

# Select for specific content type
python scripts/select_captions.py --creator missalexa --count 8 \
    --content-type solo --output captions.json
```

### Caption Selection API
```python
from scripts.select_captions import (
    load_stratified_pools,
    select_from_proven_pool,
    select_from_global_earner_pool,
    select_from_discovery_pool,
    StratifiedPools
)
from scripts.shared_context import PersonaProfile
from scripts.database import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)

# Load pools for a creator and content type
pools = load_stratified_pools(
    conn=conn,
    creator_id="abc123-def456",
    content_type="solo"
)

print(f"Pool sizes:")
print(f"  Proven: {len(pools.proven)}")
print(f"  Global Earners: {len(pools.global_earners)}")
print(f"  Discovery: {len(pools.discovery)}")

# Load persona profile
persona = PersonaProfile(
    creator_id="abc123-def456",
    page_name="missalexa",
    primary_tone="playful",
    secondary_tone="seductive",
    emoji_frequency="moderate",
    favorite_emojis=("💕", "😘", "🔥"),
    slang_level="light",
    avg_sentiment=0.72,
    avg_caption_length=145
)

# Select caption from proven pool
caption = select_from_proven_pool(
    pools=pools,
    persona=persona,
    slot_type="premium"
)

if caption:
    print(f"\nSelected caption:")
    print(f"  ID: {caption.caption_id}")
    print(f"  Text: {caption.caption_text[:80]}...")
    print(f"  Persona boost: {caption.persona_boost:.2f}x")
    print(f"  Pool: {caption.pool_type}")
    print(f"  Earnings: ${caption.creator_avg_earnings:.2f}")
```

### Hook Type Detection
```python
from scripts.hook_detection import detect_hook_type, HookType

# Detect hook type in caption
caption_text = "Guess what I just filmed for you baby..."
hook_type, confidence = detect_hook_type(caption_text)

print(f"Hook type: {hook_type.value}")  # "curiosity"
print(f"Confidence: {confidence:.2f}")  # 0.60

# Check for specific hook types
if hook_type == HookType.CURIOSITY:
    print("This caption uses a curiosity hook!")
elif hook_type == HookType.QUESTION:
    print("This caption asks a question!")
```

### Calculate Persona Boost
```python
from scripts.match_persona import calculate_persona_boost
from scripts.shared_context import PersonaProfile

# Create persona profile
persona = PersonaProfile(
    creator_id="abc123",
    page_name="missalexa",
    primary_tone="playful",
    secondary_tone="seductive",
    emoji_frequency="moderate",
    favorite_emojis=("💕", "😘", "🔥"),
    slang_level="light",
    avg_sentiment=0.72,
    avg_caption_length=145
)

# Caption to analyze
caption_text = "hehe guess what I filmed for you today babe 💕"

# Calculate boost
boost = calculate_persona_boost(
    caption_text=caption_text,
    persona=persona
)

print(f"Persona boost: {boost:.2f}x")  # 1.28x (strong match)
```

---

## Pool-Based Caption Selection Examples

EROS v2.1 uses a three-pool stratification system for intelligent caption selection based on earnings performance.

### Classify Caption Into Pool
```python
from select_captions import classify_pool, POOL_PROVEN, POOL_GLOBAL_EARNER, POOL_DISCOVERY

# Classify a single caption
caption = {
    "creator_times_used": 5,
    "creator_avg_earnings": 82.50,
    "global_times_used": 15,
    "global_avg_earnings": 65.00
}

pool = classify_pool(caption)
print(f"Pool: {pool}")  # "PROVEN" (creator-tested, earns well)

# Pool classification rules:
# PROVEN: creator_times_used >= 3 AND creator_avg_earnings > 0
# GLOBAL_EARNER: creator_times_used < 3 AND global_times_used >= 3 AND global_avg_earnings > 0
# DISCOVERY: All others (new imports, under-tested)
```

### Load Stratified Pools
```python
from select_captions import StratifiedPools, load_stratified_pools
import sqlite3

conn = sqlite3.connect("database.db")
conn.row_factory = sqlite3.Row

# Load pools for all content types
pools_by_id = load_stratified_pools(
    conn=conn,
    creator_id="abc123-def456",
    allowed_content_types=None,  # All types from vault_matrix
    min_freshness=30.0
)

# Iterate pools
for content_type_id, pool in pools_by_id.items():
    print(f"\nContent Type: {pool.type_name}")
    print(f"  PROVEN: {len(pool.proven)} captions")
    print(f"  GLOBAL_EARNER: {len(pool.global_earners)} captions")
    print(f"  DISCOVERY: {len(pool.discovery)} captions")
    print(f"  Total: {pool.total_count}")
    print(f"  Has proven performers: {pool.has_proven}")

    # Get expected earnings
    expected = pool.get_expected_earnings()
    print(f"  Expected earnings: ${expected:.2f}")
```

### Select from PROVEN Pool
```python
from select_captions import select_from_proven_pool

# Premium slots use PROVEN pool (highest earners only)
persona = {
    "primary_tone": "playful",
    "emoji_frequency": "moderate",
    "slang_level": "light"
}

exclude_ids = set()  # Already selected caption IDs

caption = select_from_proven_pool(
    pools=pools_by_id,
    persona=persona,
    exclude_ids=exclude_ids,
    exclude_content_type=None,  # Optional: exclude to promote variety
    last_hook_type=None  # Optional: for hook rotation penalty
)

if caption:
    print(f"Selected PROVEN caption:")
    print(f"  ID: {caption.caption_id}")
    print(f"  Text: {caption.caption_text[:60]}...")
    print(f"  Creator earnings: ${caption.creator_avg_earnings:.2f}")
    print(f"  Times used: {caption.creator_times_used}")
    print(f"  Persona boost: {caption.persona_boost:.2f}x")
    print(f"  Final weight: {caption.final_weight:.2f}")
```

### Select from GLOBAL_EARNER Pool
```python
from select_captions import select_from_standard_pools

# Standard slots use PROVEN + GLOBAL_EARNER pools
caption = select_from_standard_pools(
    pools=pools_by_id,
    persona=persona,
    exclude_ids=exclude_ids,
    exclude_content_type="ppv",  # Promote variety
)

if caption:
    print(f"Selected caption from {caption.pool_type} pool")
    if caption.pool_type == "PROVEN":
        print(f"  Creator earnings: ${caption.creator_avg_earnings:.2f}")
    elif caption.pool_type == "GLOBAL_EARNER":
        print(f"  Global earnings: ${caption.global_avg_earnings:.2f}")
        print(f"  Untested for this creator - discovery opportunity!")
```

### Select from DISCOVERY Pool
```python
from select_captions import select_from_discovery_pool

# Discovery slots prioritize new imports and under-tested captions
caption = select_from_discovery_pool(
    pools=pools_by_id,
    persona=persona,
    exclude_ids=exclude_ids,
    prioritize_recent_imports=True,  # Boost recent imports
)

if caption:
    print(f"Selected DISCOVERY caption:")
    print(f"  ID: {caption.caption_id}")
    print(f"  Source: {caption.source}")  # "internal" or "external_import"
    if caption.imported_at:
        print(f"  Imported: {caption.imported_at}")
    print(f"  Times used (creator): {caption.creator_times_used}")
    print(f"  Times used (global): {caption.global_times_used}")

    # Discovery bonuses applied:
    # - Recent imports (< 30 days): 1.5x boost
    # - External imports: 1.2x boost
    # - High global earners: 1.3x boost
```

### Weight Calculation Example
```python
from weights import calculate_weight, get_max_earnings

# Get max earnings for normalization
proven_captions = pool.proven
max_earnings = get_max_earnings(proven_captions, pool_type="PROVEN")

# Calculate weight for a caption
caption = proven_captions[0]
persona_boost = 1.25  # From persona matching

weight = calculate_weight(
    caption=caption,
    pool_type="PROVEN",
    content_type_avg_earnings=50.0,
    max_earnings=max_earnings,
    persona_boost=persona_boost
)

print(f"Weight calculation:")
print(f"  Earnings: ${caption.creator_avg_earnings:.2f}")
print(f"  Max earnings: ${max_earnings:.2f}")
print(f"  Freshness: {caption.freshness_score:.1f}")
print(f"  Persona boost: {persona_boost:.2f}x")
print(f"  Final weight: {weight:.2f}")

# Weight formula:
# Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery Bonus(10%)
```

### Hook Rotation Penalty
```python
from select_captions import select_from_proven_pool, SAME_HOOK_PENALTY
from hook_detection import HookType

# Track last hook type to prevent consecutive duplicates
last_hook_type = HookType.CURIOSITY

# Selection with hook rotation penalty
caption = select_from_proven_pool(
    pools=pools_by_id,
    persona=persona,
    exclude_ids=exclude_ids,
    last_hook_type=last_hook_type  # Apply 0.7x penalty to same hook
)

if caption:
    print(f"Hook type: {caption.hook_type.value}")
    print(f"Hook confidence: {caption.hook_confidence:.2f}")

    if caption.hook_type == last_hook_type:
        print(f"WARNING: Same hook penalty ({SAME_HOOK_PENALTY}x) applied")
    else:
        print(f"Good variation: {last_hook_type.value} -> {caption.hook_type.value}")
```

---

## Hook Detection Examples

EROS v2.1 includes hook type detection for anti-detection rotation and authenticity scoring.

### Detect Hook Type
```python
from hook_detection import detect_hook_type, HookType

# Detect hook type from caption text
captions = [
    "Guess what I just filmed for you baby... 🔥",
    "I miss you so much 💕 been thinking about you all day",
    "EXCLUSIVE content just for my VIPs 🔒 don't miss this",
    "Just posted something new! Check it now before it's gone",
    "What would you do if you saw me like this? 😏",
    "Hey babe, slide into my DMs 💌",
    "You're gonna love what I have for you... trust me 😈"
]

for caption_text in captions:
    hook_type, confidence = detect_hook_type(caption_text)
    print(f"Caption: {caption_text[:50]}...")
    print(f"  Hook: {hook_type.value}")
    print(f"  Confidence: {confidence:.2f}")
    print()

# Hook types detected:
# - curiosity: "Guess what...", "You won't believe..."
# - personal: "I miss you", "thinking about you"
# - exclusivity: "EXCLUSIVE", "VIPs only", "just for you"
# - recency: "just posted", "new content"
# - question: "What would you do?", "Should I...?"
# - direct: "DM me", "check this out"
# - teasing: "trust me", "you're gonna love"
```

### All Hook Types
```python
from hook_detection import HOOK_TYPES, HookType

# List all available hook types
print("Available hook types:")
for hook in HOOK_TYPES:
    print(f"  - {hook}")

# Output:
# - curiosity
# - personal
# - exclusivity
# - recency
# - question
# - direct
# - teasing
```

### Use in Caption Selection
```python
from select_captions import select_from_proven_pool
from hook_detection import HookType

# Track hook diversity across selections
selected_hooks = []
selected_captions = []

for i in range(5):
    # Get last hook for rotation penalty
    last_hook = selected_hooks[-1] if selected_hooks else None

    caption = select_from_proven_pool(
        pools=pools_by_id,
        persona=persona,
        exclude_ids={c.caption_id for c in selected_captions},
        last_hook_type=last_hook
    )

    if caption:
        selected_captions.append(caption)
        selected_hooks.append(caption.hook_type)
        print(f"Caption {i+1}: {caption.hook_type.value} hook")

# Check diversity
unique_hooks = len(set(selected_hooks))
print(f"\nHook diversity: {unique_hooks}/5 unique hooks")
if unique_hooks >= 4:
    print("Excellent hook diversity!")
elif unique_hooks >= 3:
    print("Good hook diversity")
else:
    print("Low hook diversity - may appear repetitive")
```

---

## Extended Validation Examples (V020-V031)

EROS v2.1 adds 12 new validation rules (V020-V031) for the 20+ content type system.

### Page Type Validation (V020)
```python
from validate_schedule import ScheduleValidator

validator = ScheduleValidator()

# Validate with page type
items = [
    {"item_id": 1, "content_type_name": "ppv", "scheduled_date": "2025-01-06", "scheduled_time": "10:00"},
    {"item_id": 2, "content_type_name": "vip_post", "scheduled_date": "2025-01-06", "scheduled_time": "14:00"},
]

# Free page validation (vip_post is paid-only)
result = validator.validate(items, page_type="free")

# Check for V020 violations
v020_issues = [i for i in result.issues if i.rule_name == "V020"]
if v020_issues:
    print("Page type violations found:")
    for issue in v020_issues:
        print(f"  {issue.message}")
        print(f"  Auto-correctable: {issue.auto_correctable}")
        print(f"  Action: {issue.correction_action}")

# Paid page validation (all types valid)
result = validator.validate(items, page_type="paid")
assert result.is_valid  # No violations
```

### VIP Post Spacing (V021)
```python
# V021: Minimum 24 hours between VIP posts
items = [
    {"item_id": 1, "content_type_name": "vip_post", "scheduled_date": "2025-01-06", "scheduled_time": "10:00"},
    {"item_id": 2, "content_type_name": "vip_post", "scheduled_date": "2025-01-06", "scheduled_time": "20:00"},
]

result = validator.validate(items, page_type="paid")

v021_issues = [i for i in result.issues if i.rule_name == "V021"]
if v021_issues:
    print("VIP post spacing violation:")
    for issue in v021_issues:
        print(f"  {issue.message}")
        # Auto-correctable: moves second VIP post to next day
```

### Engagement Limits (V023/V024)
```python
from datetime import date

# V023: Max 2 engagement posts per day
# V024: Max 10 engagement posts per week
items = [
    {"item_id": 1, "content_type_name": "dm_farm", "scheduled_date": "2025-01-06", "scheduled_time": "10:00"},
    {"item_id": 2, "content_type_name": "like_farm", "scheduled_date": "2025-01-06", "scheduled_time": "14:00"},
    {"item_id": 3, "content_type_name": "dm_farm", "scheduled_date": "2025-01-06", "scheduled_time": "18:00"},
]

result = validator.validate(items, page_type="paid")

# Check V023 (daily limit)
v023_issues = [i for i in result.issues if i.rule_name == "V023"]
if v023_issues:
    print(f"Daily engagement limit exceeded:")
    for issue in v023_issues:
        print(f"  {issue.message}")
        # Auto-correctable: moves excess to next day
```

### Retention Timing (V025)
```python
# V025: Retention content should be on days 5-7 (Fri-Sun)
week_start = date(2025, 1, 6)  # Monday

items = [
    {"item_id": 1, "content_type_name": "renew_on_post", "scheduled_date": "2025-01-07", "scheduled_time": "10:00"},  # Tuesday (day 2)
    {"item_id": 2, "content_type_name": "renew_on_mm", "scheduled_date": "2025-01-10", "scheduled_time": "14:00"},  # Friday (day 5)
]

result = validator.validate(items, page_type="paid", week_start=week_start)

v025_issues = [i for i in result.issues if i.rule_name == "V025"]
if v025_issues:
    print("Retention timing suggestions:")
    for issue in v025_issues:
        print(f"  {issue.message}")
        # Info only - recommends days 5-7 for best impact
```

### Bundle Spacing (V026/V027)
```python
# V026: Min 24h between regular bundles
# V027: Min 48h between flash bundles
items = [
    {"item_id": 1, "content_type_name": "bundle", "scheduled_date": "2025-01-06", "scheduled_time": "10:00"},
    {"item_id": 2, "content_type_name": "bundle", "scheduled_date": "2025-01-06", "scheduled_time": "20:00"},
    {"item_id": 3, "content_type_name": "flash_bundle", "scheduled_date": "2025-01-07", "scheduled_time": "10:00"},
    {"item_id": 4, "content_type_name": "flash_bundle", "scheduled_date": "2025-01-08", "scheduled_time": "10:00"},
]

result = validator.validate(items, page_type="paid")

# Check V026 (bundle spacing)
v026_issues = [i for i in result.issues if i.rule_name == "V026"]
if v026_issues:
    print("Bundle spacing violations:")
    for issue in v026_issues:
        print(f"  {issue.message}")
        # Auto-correctable: moves to next valid slot

# Check V027 (flash bundle spacing)
v027_issues = [i for i in result.issues if i.rule_name == "V027"]
if v027_issues:
    print("Flash bundle spacing violations:")
    for issue in v027_issues:
        print(f"  {issue.message}")
        # Auto-correctable: moves to 48h+ after previous
```

### Placeholder Warnings (V031)
```python
# V031: Warn when slots have no caption (placeholder)
items = [
    {"item_id": 1, "content_type_name": "ppv", "has_caption": True, "caption_id": 123},
    {"item_id": 2, "content_type_name": "vip_post", "has_caption": False, "caption_id": None},
    {"item_id": 3, "content_type_name": "bundle", "caption_id": None, "caption_text": ""},
]

result = validator.validate(items, page_type="paid")

v031_issues = [i for i in result.issues if i.rule_name == "V031"]
if v031_issues:
    print(f"Placeholders found: {len(v031_issues)}")
    for issue in v031_issues:
        print(f"  {issue.message}")
        # Info severity - manual caption entry required
```

### Auto-Correction Example
```python
from validate_schedule import ScheduleValidator

validator = ScheduleValidator()

# Schedule with violations
items = [
    {"item_id": 1, "content_type_name": "ppv", "scheduled_date": "2025-01-06", "scheduled_time": "10:00"},
    {"item_id": 2, "content_type_name": "ppv", "scheduled_date": "2025-01-06", "scheduled_time": "11:00"},  # Too close
    {"item_id": 3, "content_type_name": "vip_post", "scheduled_date": "2025-01-06", "scheduled_time": "14:00"},
    {"item_id": 4, "content_type_name": "vip_post", "scheduled_date": "2025-01-06", "scheduled_time": "20:00"},  # < 24h
]

# Validate with auto-correction (max 2 passes)
result = validator.validate_with_corrections(
    items=items,
    page_type="paid",
    max_passes=2
)

print(f"Validation result: {'PASSED' if result.is_valid else 'FAILED'}")
print(f"Errors: {result.error_count}")
print(f"Warnings: {result.warning_count}")
print(f"Corrections applied: {sum(1 for i in result.issues if 'auto_corrections' in i.rule_name)}")

# Auto-correctable issues are fixed automatically:
# - PPV spacing < 3h -> moved to next valid slot
# - VIP post spacing < 24h -> moved to next day
# - Engagement limit exceeded -> redistributed or removed
```

---

## Validation Examples

### Validate Schedule (CLI)
```bash
# Validate schedule file
python scripts/validate_schedule.py --input schedule.json

# Strict validation (warnings treated as errors)
python scripts/validate_schedule.py --input schedule.json --strict

# Save validation report
python scripts/validate_schedule.py --input schedule.json --output report.md
```

### Validation API
```python
from scripts.validate_schedule import (
    ScheduleValidator,
    ValidationIssue,
    ValidationResult
)

# Create validator
validator = ScheduleValidator(
    min_ppv_spacing_hours=4,
    min_freshness_score=30.0
)

# Validate schedule items
result = validator.validate(schedule_items)

if result.is_valid:
    print("✓ Schedule is valid!")
else:
    print(f"✗ Validation failed")
    print(f"  Errors: {result.error_count}")
    print(f"  Warnings: {result.warning_count}")

    # Print issues
    for issue in result.issues:
        print(f"\n[{issue.severity.upper()}] {issue.rule_name}")
        print(f"  {issue.message}")
        if issue.auto_correctable:
            print(f"  Auto-correction available: {issue.correction_action}")
```

### Custom Validation Rules
```python
from scripts.validate_schedule import ScheduleValidator, ValidationResult
from datetime import datetime, timedelta

class CustomValidator(ScheduleValidator):
    """Extended validator with custom business rules."""

    def validate_weekend_volume(self, items: list) -> ValidationResult:
        """Ensure weekends have reduced volume."""
        result = ValidationResult()

        weekend_items = [
            item for item in items
            if datetime.strptime(item.scheduled_date, "%Y-%m-%d").weekday() >= 5
        ]

        if len(weekend_items) > 10:
            result.add_warning(
                rule="weekend_volume",
                message=f"Weekend has {len(weekend_items)} items (recommended: ≤10)",
                item_ids=[item.item_id for item in weekend_items]
            )

        return result

# Use custom validator
validator = CustomValidator()
result = validator.validate(schedule_items)
weekend_result = validator.validate_weekend_volume(schedule_items)
```

---

## Volume Optimization

### Calculate Optimal Volume (CLI)
```bash
# Calculate volume for creator
python scripts/volume_optimizer.py --creator missalexa

# Calculate for all creators
python scripts/volume_optimizer.py --all --format table

# Override fan count for simulation
python scripts/volume_optimizer.py --creator missalexa --fan-count 10000
```

### Volume Optimization API
```python
from scripts.volume_optimizer import MultiFactorVolumeOptimizer, VolumeStrategy
from scripts.database import DB_PATH

# Create optimizer
optimizer = MultiFactorVolumeOptimizer(db_path=DB_PATH)

# Calculate optimal volume
strategy = optimizer.calculate_optimal_volume(creator_id="abc123-def456")

print(f"Volume Strategy:")
print(f"  Tier: {strategy.volume_tier}")
print(f"  PPV/day: {strategy.ppv_per_day}")
print(f"  Bump/day: {strategy.bump_per_day}")
print(f"  Weekly total: {strategy.ppv_per_day * 7} PPVs")
print(f"  Fan count: {strategy.fan_count:,}")
print(f"  Performance tier: {strategy.performance_tier}")
```

### Volume Tier Logic
```python
from scripts.volume_optimizer import get_volume_tier

# Check volume tier based on performance
tier = get_volume_tier(
    conversion_rate=0.0028,  # 0.28%
    dollars_per_ppv=62.00,
    total_revenue=45000.00
)

print(f"Volume tier: {tier}")  # "Scale" (4 PPV/day)

# Volume tiers:
# - Base:   2 PPV/day (all creators minimum)
# - Growth: 3 PPV/day (conv >0.10% OR $/PPV >$40)
# - Scale:  4 PPV/day (conv >0.25% AND $/PPV >$50)
# - High:   5 PPV/day (conv >0.35% AND $/PPV >$65)
# - Ultra:  6 PPV/day (conv >0.40% AND $/PPV >$75 AND >$75K rev)
```

---

## Content Strategy

### Check Vault Availability
```python
from scripts.content_type_strategy import get_content_type_earnings
from scripts.database import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get available content types for creator
cursor.execute("""
    SELECT ct.type_name, vm.quantity
    FROM vault_matrix vm
    JOIN content_types ct ON vm.content_type_id = ct.content_type_id
    WHERE vm.creator_id = ?
    ORDER BY vm.quantity DESC
""", ("abc123-def456",))

print("Available content types:")
for type_name, quantity in cursor.fetchall():
    print(f"  {type_name}: {quantity} items")
```

### Allocate Slots by Earnings
```python
from scripts.content_type_strategy import (
    ContentTypeStrategy,
    allocate_slots_weighted,
    get_content_type_earnings
)
from scripts.database import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)

# Get earnings data
earnings = get_content_type_earnings(
    conn=conn,
    creator_id="abc123-def456"
)

print("Content type earnings:")
for content_type, avg_earnings in earnings.items():
    print(f"  {content_type}: ${avg_earnings:.2f}")

# Allocate 14 slots based on earnings
slots = allocate_slots_weighted(
    content_types=list(earnings.keys()),
    total_slots=14,
    earnings_data=earnings
)

print("\nSlot allocation:")
for content_type, slot_count in slots.items():
    print(f"  {content_type}: {slot_count} slots")
```

### Identify Premium Content
```python
from scripts.content_type_strategy import ContentTypeStrategy, PREMIUM_HOURS
from scripts.database import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)

# Create strategy
strategy = ContentTypeStrategy(
    conn=conn,
    creator_id="abc123-def456"
)

# Get premium content types (top earners)
premium_types = strategy.get_premium_content_types(top_n=3)

print("Premium content types for peak hours:")
for content_type in premium_types:
    print(f"  {content_type}")

print(f"\nPeak hours: {sorted(PREMIUM_HOURS)}")  # [18, 21]
```

---

## Error Handling

### Common Errors
```python
from scripts.generate_schedule import (
    CreatorNotFoundError,
    CaptionExhaustionError,
    DatabaseNotFoundError,
    VaultEmptyError,
    ValidationError
)

try:
    result = generate_schedule_for_creator(
        creator_name="unknown_creator",
        week="2025-W02"
    )
except CreatorNotFoundError as e:
    print(f"Creator not found: {e.identifier}")
    print(f"Searched in: {e.table_name}")

except CaptionExhaustionError as e:
    print(f"Not enough fresh captions!")
    print(f"  Required: {e.required}")
    print(f"  Available: {e.available}")
    print(f"  Content type: {e.content_type}")
    print(f"Solution: Wait {e.days_until_recovery} days for freshness recovery")

except VaultEmptyError as e:
    print(f"Vault is empty for content type: {e.content_type}")
    print(f"Solution: Update vault_matrix table")

except DatabaseNotFoundError as e:
    print(f"Database not found!")
    print(f"Searched paths: {e.searched_paths}")
    print(f"Solution: Set EROS_DATABASE_PATH environment variable")

except ValidationError as e:
    print(f"Schedule validation failed!")
    print(f"Errors: {len(e.issues)}")
    for issue in e.issues:
        print(f"  - {issue.message}")
```

### Graceful Degradation
```python
from scripts.select_captions import select_from_proven_pool
from scripts.shared_context import PersonaProfile

def safe_caption_selection(pools, persona):
    """Select caption with fallback logic."""

    # Try proven pool first
    caption = select_from_proven_pool(pools, persona, slot_type="premium")
    if caption:
        return caption, "proven"

    # Fallback to global earners
    caption = select_from_global_earner_pool(pools, persona, slot_type="standard")
    if caption:
        return caption, "global"

    # Last resort: discovery pool
    caption = select_from_discovery_pool(pools, persona, slot_type="discovery")
    if caption:
        return caption, "discovery"

    # No captions available
    raise CaptionExhaustionError(
        required=1,
        available=0,
        content_type=pools.type_name
    )

# Use safe selection
try:
    caption, pool = safe_caption_selection(pools, persona)
    print(f"Selected from {pool} pool: {caption.caption_text[:50]}...")
except CaptionExhaustionError as e:
    print(f"No captions available for {e.content_type}")
```

---

## Logging Configuration

### Enable Debug Logging
```python
import logging
from scripts.generate_schedule import generate_schedule_for_creator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Generate schedule with debug output
result = generate_schedule_for_creator(
    creator_name="missalexa",
    week="2025-W02",
    mode="quick"
)
```

### Custom Logger
```python
import logging

# Create module-specific logger
logger = logging.getLogger("eros.custom_module")
logger.setLevel(logging.INFO)

# Add file handler
handler = logging.FileHandler("schedule_generation.log")
handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(handler)

# Use logger
logger.info("Starting schedule generation")
logger.debug(f"Creator: {creator_name}, Week: {week}")
logger.warning("Low caption count detected")
logger.error("Validation failed")
```

---

## Environment Variables

### Set Environment Variables
```bash
# Add to ~/.zshrc or ~/.bashrc
export EROS_DATABASE_PATH="$HOME/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
export EROS_SCHEDULES_PATH="$HOME/Developer/EROS-SD-MAIN-PROJECT/schedules"
export EROS_MIN_PPV_SPACING_HOURS="4"
export EROS_FRESHNESS_HALF_LIFE_DAYS="14.0"
export EROS_FRESHNESS_MINIMUM_SCORE="30.0"
```

### Check Environment
```python
import os
from scripts.database import DB_PATH, HOME_DIR

print("Environment Configuration:")
print(f"  Database: {DB_PATH}")
print(f"  Home: {HOME_DIR}")
print(f"  Schedules: {os.getenv('EROS_SCHEDULES_PATH', 'not set')}")
print(f"  PPV Spacing: {os.getenv('EROS_MIN_PPV_SPACING_HOURS', '4')} hours")
print(f"  Freshness Half-life: {os.getenv('EROS_FRESHNESS_HALF_LIFE_DAYS', '14')} days")
```

---

## Testing Examples

### Unit Test for Caption Selection
```python
import unittest
from scripts.select_captions import calculate_weight
from scripts.shared_context import PersonaProfile

class TestCaptionSelection(unittest.TestCase):
    def test_weight_calculation(self):
        """Test weight calculation with known values."""
        weight = calculate_weight(
            earnings=100.0,
            max_earnings=200.0,
            freshness_score=80.0,
            persona_boost=1.25,
            discovery_bonus=0.0,
            payday_multiplier=1.0
        )

        # Verify weight is within expected range
        self.assertGreater(weight, 0)
        self.assertLess(weight, 100)

    def test_persona_boost_range(self):
        """Test persona boost stays within valid range."""
        from scripts.match_persona import calculate_persona_boost

        persona = PersonaProfile(
            creator_id="test",
            page_name="test",
            primary_tone="playful",
            secondary_tone=None,
            emoji_frequency="moderate",
            favorite_emojis=("💕",),
            slang_level="light",
            avg_sentiment=0.7,
            avg_caption_length=150
        )

        boost = calculate_persona_boost("test caption", persona)

        # Boost should be between 1.0 and 1.4
        self.assertGreaterEqual(boost, 1.0)
        self.assertLessEqual(boost, 1.4)

if __name__ == "__main__":
    unittest.main()
```

### Integration Test
```python
import unittest
from scripts.generate_schedule import generate_schedule_for_creator
from scripts.database import DB_PATH

class TestScheduleGeneration(unittest.TestCase):
    def test_full_pipeline(self):
        """Test complete schedule generation pipeline."""
        result = generate_schedule_for_creator(
            creator_name="missalexa",
            week="2025-W02",
            mode="quick"
        )

        # Verify structure
        self.assertIsNotNone(result)
        self.assertGreater(result.total_items, 0)
        self.assertTrue(result.validation_passed)

        # Verify PPV spacing
        ppv_items = [item for item in result.schedule_items if item.message_type == "ppv"]
        for i in range(1, len(ppv_items)):
            prev_time = ppv_items[i-1].scheduled_datetime
            curr_time = ppv_items[i].scheduled_datetime
            delta = (curr_time - prev_time).total_seconds() / 3600
            self.assertGreaterEqual(delta, 3.0, "PPV spacing must be >= 3 hours")

if __name__ == "__main__":
    unittest.main()
```

---

## Performance Profiling

### Profile Schedule Generation
```python
import cProfile
import pstats
from scripts.generate_schedule import generate_schedule_for_creator

# Profile schedule generation
profiler = cProfile.Profile()
profiler.enable()

result = generate_schedule_for_creator(
    creator_name="missalexa",
    week="2025-W02",
    mode="quick"
)

profiler.disable()

# Print stats
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Timing Benchmarks
```python
import time
from scripts.generate_schedule import generate_schedule_for_creator

# Benchmark schedule generation
start = time.time()
result = generate_schedule_for_creator(
    creator_name="missalexa",
    week="2025-W02",
    mode="quick"
)
elapsed = time.time() - start

print(f"Schedule generated in {elapsed:.2f} seconds")
print(f"  Items: {result.total_items}")
print(f"  Speed: {result.total_items / elapsed:.1f} items/sec")

# Expected performance targets:
# - Quick mode: < 5 seconds
# - Full mode: < 30 seconds
# - Batch mode: < 2 minutes for 36 creators
```

---

For more information, see:
- [SKILL.md](./SKILL.md) - Skill definition and usage
- [references/architecture.md](./references/architecture.md) - System architecture
- [references/scheduling_rules.md](./references/scheduling_rules.md) - Business rules
- [references/database-schema.md](./references/database-schema.md) - Database structure
