# EROS Schedule Generator - Examples

Practical examples for common use cases with the EROS Schedule Generator.

## Table of Contents
- [Quick Schedule Generation](#quick-schedule-generation)
- [Full Semantic Analysis Mode](#full-semantic-analysis-mode)
- [Batch Processing](#batch-processing)
- [Python API Usage](#python-api-usage)
- [Caption Selection Examples](#caption-selection-examples)
- [Validation Examples](#validation-examples)
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
