# EROS Schedule Generator - Troubleshooting Guide

Solutions for common issues when using the EROS Schedule Generator v2.1.

## Table of Contents
- [Database Issues](#database-issues)
- [Caption Issues](#caption-issues)
- [Validation Failures](#validation-failures)
  - [Page Type Violation Errors (V020)](#page-type-violation-errors-v020)
  - [Content Type Spacing Errors (V021-V027)](#content-type-spacing-errors-v021-v027)
  - [Engagement Limit Warnings (V023-V024)](#engagement-limit-warnings-v023-v024)
  - [Hook Rotation Warnings (V015-V016)](#hook-rotation-warnings-v015-v016)
- [Schedule Uniqueness Issues](#schedule-uniqueness-issues)
- [Content Type Issues](#content-type-issues)
- [Auto-Correction Issues](#auto-correction-issues)
- [Performance Issues](#performance-issues)
- [Import Errors](#import-errors)

---

## Database Issues

### Database Not Found

**Symptom:**
```
DatabaseNotFoundError: EROS database not found. Searched:
  - /path/to/db1
  - /path/to/db2
```

**Cause:** The database file doesn't exist at any of the standard locations.

**Solutions:**

1. **Set environment variable:**
   ```bash
   export EROS_DATABASE_PATH="/path/to/your/eros_sd_main.db"
   ```

2. **Place database in standard location:**
   ```bash
   # Option 1: Developer folder
   mkdir -p ~/Developer/EROS-SD-MAIN-PROJECT/database/
   cp your_db.db ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db

   # Option 2: Documents folder
   mkdir -p ~/Documents/EROS-SD-MAIN-PROJECT/database/
   cp your_db.db ~/Documents/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db
   ```

3. **Check file exists:**
   ```bash
   ls -la $EROS_DATABASE_PATH
   ```

---

### Creator Not Found

**Symptom:**
```
CreatorNotFoundError: Creator not found: missalexa
```

**Cause:** The creator doesn't exist or is inactive in the database.

**Solutions:**

1. **Check creator exists:**
   ```bash
   sqlite3 $EROS_DATABASE_PATH "SELECT page_name, is_active FROM creators WHERE page_name LIKE '%alexa%'"
   ```

2. **Check is_active flag:**
   ```bash
   sqlite3 $EROS_DATABASE_PATH "UPDATE creators SET is_active = 1 WHERE page_name = 'missalexa'"
   ```

3. **List all active creators:**
   ```bash
   sqlite3 $EROS_DATABASE_PATH "SELECT page_name FROM creators WHERE is_active = 1"
   ```

---

## Caption Issues

### CaptionExhaustionError

**Symptom:**
```
CaptionExhaustionError: Caption exhaustion for abc123: 5 available, 14 required
```

**Cause:** Not enough fresh captions available for the schedule.

**Solutions:**

1. **Wait for freshness recovery (7-14 days)**
   Captions recover freshness over time based on exponential decay.

2. **Check freshness scores:**
   ```bash
   python scripts/calculate_freshness.py --creator missalexa --update
   ```

3. **Import new captions:**
   Add new captions to the `caption_bank` table.

4. **Lower freshness threshold temporarily:**
   ```python
   # In generate_schedule.py, adjust MIN_FRESHNESS
   MIN_FRESHNESS = 20  # Default is 30
   ```

5. **Check caption usage:**
   ```sql
   SELECT caption_id, freshness_score, last_used_at, times_used
   FROM caption_bank
   WHERE creator_id = 'abc123'
   ORDER BY freshness_score DESC
   LIMIT 20;
   ```

---

### Low Persona Boost Rates

**Symptom:** Most captions showing `persona_boost: 1.0` instead of higher values.

**Cause:** Missing tone/slang/emoji data for captions, or missing persona profile.

**Solutions:**

1. **Check persona exists:**
   ```sql
   SELECT * FROM creator_personas WHERE creator_id = 'abc123';
   ```

2. **Enable text detection (always on by default):**
   Text-based tone detection automatically fills in missing metadata.

3. **Verify caption metadata:**
   ```sql
   SELECT caption_id, tone, slang_level, emoji_style
   FROM caption_bank
   WHERE creator_id = 'abc123' AND tone IS NOT NULL
   LIMIT 10;
   ```

4. **Run persona matching manually:**
   ```bash
   python scripts/match_persona.py --creator missalexa --verbose
   ```

---

### VaultEmptyError

**Symptom:**
```
VaultEmptyError: Empty vault for abc123 (content type: bg)
```

**Cause:** No content of the requested type is available in the vault.

**Solutions:**

1. **Check vault_matrix:**
   ```sql
   SELECT * FROM vault_matrix WHERE creator_id = 'abc123';
   ```

2. **Update vault availability:**
   ```sql
   INSERT INTO vault_matrix (creator_id, content_type_id, has_content, last_checked)
   VALUES ('abc123', 2, 1, datetime('now'));
   ```

3. **Exclude unavailable content types:**
   The scheduler automatically skips content types with `has_content = 0`.

---

## Validation Failures

### Page Type Violation Errors (V020)

**Symptom:**
```
ValidationError: V020 - Content type 'vip_post' requires paid page
ValidationError: V020 - Content type 'renew_on_post' requires paid page
```

**Cause:** Paid-only content types scheduled on free pages.

**Paid-only content types:**
- `vip_post` - VIP tier exclusive content
- `renew_on_post` - Subscription renewal reminder (feed)
- `renew_on_mm` - Subscription renewal reminder (mass message)
- `expired_subscriber` - Win-back messages for expired subscribers

**Solutions:**

1. **Remove paid-only content from free page schedules:**
   ```bash
   # This will auto-correct by removing invalid items
   python scripts/validate_schedule.py --input schedule.json --page-type free --auto-fix
   ```

2. **Switch page type to "paid" if creator has paid subscription:**
   ```bash
   # Generate schedule for paid page
   python scripts/generate_schedule.py --creator missalexa --week 2025-W01 --page-type paid
   ```

3. **Check content type before scheduling:**
   ```python
   from content_type_registry import REGISTRY

   # Validate before adding to schedule
   if not REGISTRY.validate_for_page("vip_post", "free"):
       print("ERROR: VIP posts require paid page")
   ```

---

### Content Type Spacing Errors (V021-V027)

#### V021 - VIP Post Spacing (24h minimum)

**Symptom:**
```
ValidationError: V021 - VIP post spacing 18.5h < 24h minimum between items 5 and 8
```

**Cause:** VIP posts scheduled less than 24 hours apart.

**Solutions:**

1. **Auto-correction moves second VIP post:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix
   ```

2. **Manual adjustment:**
   - Limit to 1 VIP post per day
   - Space VIP posts at least 24 hours apart
   - Recommended: 2-3 VIP posts per week maximum

#### V022 - Link Drop Spacing (4h minimum)

**Symptom:**
```
ValidationWarning: V022 - Link drop spacing 2.3h < 4h recommended between items 12 and 15
```

**Cause:** Link drops (external promotions) scheduled too close together.

**Solutions:**

1. **Auto-fix spacing:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix
   ```

2. **Best practices:**
   - Space link drops at least 4 hours apart
   - Maximum 3 link drops per day
   - Use both `link_drop` and `wall_link_drop` types for variety

#### V026 - Bundle Spacing (24h minimum)

**Symptom:**
```
ValidationError: V026 - Bundle spacing 16.2h < 24h minimum between items 3 and 9
```

**Cause:** Regular bundles scheduled less than 24 hours apart.

**Solutions:**

1. **Limit bundles:**
   - Maximum 1 bundle per day
   - Recommended: 2-3 bundles per week

2. **Auto-correction:**
   The validator will move the second bundle to the next day automatically.

#### V027 - Flash Bundle Spacing (48h minimum)

**Symptom:**
```
ValidationError: V027 - Flash bundle spacing 28.5h < 48h minimum between items 4 and 11
```

**Cause:** Flash bundles (urgent, time-limited offers) scheduled too close together.

**Solutions:**

1. **Space flash bundles properly:**
   - Minimum 48 hours (2 days) between flash bundles
   - Maximum 1 flash bundle per 2 days
   - Recommended: 1-2 flash bundles per week

2. **Auto-correction moves to valid slot:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix
   ```

---

### Engagement Limit Warnings (V023-V024)

#### V023 - Daily Engagement Limit (2/day max)

**Symptom:**
```
ValidationWarning: V023 - Engagement posts exceed daily limit (3/day, max 2)
ValidationWarning: V023 - Item 15 should be moved to another day
```

**Cause:** Too many engagement posts (dm_farm, like_farm) on a single day.

**Engagement content types:**
- `dm_farm` - DM me for surprise
- `like_farm` - Like this post for reward

**Solutions:**

1. **Auto-correction moves excess to next day:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix
   ```

2. **Manual distribution:**
   - Limit to 2 engagement posts per day
   - Spread across the week
   - Avoid clustering on high-PPV days

#### V024 - Weekly Engagement Limit (10/week max)

**Symptom:**
```
ValidationWarning: V024 - Engagement posts exceed weekly limit (12/week, max 10)
```

**Cause:** Too many engagement posts across the entire week.

**Solutions:**

1. **Remove excess engagement posts:**
   Auto-correction will flag items 11-12 for removal.

2. **Best practices:**
   - Maximum 10 engagement posts per week
   - Average 1-2 per day maximum
   - Use strategically on low-content days

---

### Hook Rotation Warnings (V015-V016)

#### V015 - Hook Rotation (Consecutive same hook type)

**Symptom:**
```
ValidationWarning: V015 - 3+ consecutive captions use 'curiosity' hook type
ValidationWarning: V015 - Consecutive 'curiosity' hooks detected: items 5 and 6
```

**Cause:** Same psychological hook type used repeatedly, creating detectable patterns.

**Hook types:**
- `curiosity` - "Can you handle this?", "Guess what I did..."
- `urgency` - "Only 2 hours left!", "Last chance..."
- `exclusivity` - "VIP only", "You won't see this anywhere else"
- `social_proof` - "Everyone is asking for...", "Most requested"
- `personal` - "I made this for you", "Missing you"
- `playful` - "Wanna play?", "Let's have some fun"

**Solutions:**

1. **Diversify caption selection:**
   The scheduler automatically applies a 0.7x penalty to consecutive same-hook captions.

2. **Add variety to caption pool:**
   ```sql
   -- Check hook diversity in caption bank
   SELECT
       hook_type,
       COUNT(*) as count
   FROM caption_bank
   WHERE creator_id = 'abc123'
   GROUP BY hook_type;
   ```

3. **Manual hook balancing:**
   Aim for 4+ different hook types per week for natural variation.

#### V016 - Hook Diversity (Target: 4+ hook types)

**Symptom:**
```
ValidationInfo: V016 - Only 2 hook types used in schedule (target: 4+)
ValidationInfo: V016 - Hook types: curiosity, urgency (need 2 more for diversity)
```

**Cause:** Limited variety in psychological hooks, reducing authenticity.

**Solutions:**

1. **Add captions with varied hooks:**
   ```sql
   -- Find which hooks are missing
   SELECT DISTINCT hook_type
   FROM caption_bank
   WHERE creator_id = 'abc123'
   ORDER BY hook_type;
   ```

2. **Target distribution for 7-day schedule:**
   - Curiosity: 20-30%
   - Urgency: 20-30%
   - Exclusivity: 15-20%
   - Personal: 15-20%
   - Playful: 10-15%
   - Social Proof: 5-10%

---

### PPV Spacing Violations

**Symptom:**
```
ValidationIssue: PPV spacing < 3 hours between items #5 and #6
```

**Cause:** PPVs scheduled too close together.

**Solutions:**

1. **Enable auto-correction:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix
   ```

2. **Reduce PPV volume:**
   ```python
   strategy.ppv_per_day = 3  # Instead of 5
   ```

3. **Check timing in schedule:**
   PPVs should be at least 3 hours apart (recommended: 4+ hours).

---

### Content Rotation Violations

**Symptom:**
```
ValidationIssue: Same content type 'solo' used 3x consecutively
```

**Cause:** Lack of content variety in scheduling.

**Solutions:**

1. **Diversify vault content:** Add more content types.

2. **Check content type distribution:**
   ```sql
   SELECT content_type_id, COUNT(*) as count
   FROM caption_bank
   WHERE creator_id = 'abc123'
   GROUP BY content_type_id;
   ```

3. **The scheduler enforces max 2 consecutive same-type automatically.**

---

### Bump Variant Rotation (V029)

**Symptom:**
```
ValidationWarning: V029 - 3 consecutive 'flyer_gif_bump' bumps detected
ValidationWarning: V029 - Consider varying bump types for authenticity
```

**Cause:** Same bump content type used 3+ times consecutively.

**Bump content types:**
- `flyer_gif_bump` - Visual bump with flyer or GIF
- `descriptive_bump` - Detailed content description
- `text_only_bump` - Text-only mass message bump
- `normal_post_bump` - Regular feed engagement post

**Solutions:**

1. **Auto-correction swaps bump type:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix
   ```
   The validator will automatically swap the 3rd consecutive bump to an alternative type.

2. **Manual bump rotation:**
   Rotate bump types in a pattern, e.g.:
   - Monday: `flyer_gif_bump`
   - Tuesday: `descriptive_bump`
   - Wednesday: `text_only_bump`
   - Thursday: `flyer_gif_bump`

3. **Best practices:**
   - Use each bump type no more than 2x consecutively
   - Mix visual and text bumps throughout the week
   - Prioritize `flyer_gif_bump` and `descriptive_bump` for high-value PPVs

---

### Game Post Weekly Limit (V028)

**Symptom:**
```
ValidationWarning: V028 - Only 1 game post per week recommended
ValidationWarning: V028 - Item 18 should be removed (excess game post)
```

**Cause:** More than 1 game post scheduled in a single week.

**Why the limit:**
- Game posts (spin the wheel, contests) lose their special nature if overused
- Subscribers experience gamification fatigue
- Best results when treated as exclusive weekly event

**Solutions:**

1. **Auto-correction removes excess:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix
   ```
   Keeps the first game post, removes subsequent ones.

2. **Schedule game posts strategically:**
   - Maximum 1 per week (168h spacing minimum)
   - Place on highest-traffic day (typically Friday or Saturday)
   - Use for special occasions or milestones

3. **Game post configuration:**
   ```python
   # Ensure wheel_config_id is set
   game_item = {
       "item_type": "game_post",
       "content_type_name": "game_post",
       "wheel_config_id": 5,  # Reference to prize configuration
       "scheduled_date": "2025-01-10",
       "scheduled_time": "21:00"
   }
   ```

---

### Retention Timing (V025)

**Symptom:**
```
ValidationInfo: V025 - Retention content 'renew_on_post' on day 2 of week
ValidationInfo: V025 - Recommend days 5-7 (Fri-Sun) for maximum renewal impact
```

**Cause:** Renewal messages scheduled too early in the week.

**Why timing matters:**
- Subscribers are closer to renewal dates at week's end
- Higher conversion when renewal reminder is 24-48h before expiration
- Creates urgency without appearing desperate

**Retention content types:**
- `renew_on_post` - Renewal reminder on feed (paid only)
- `renew_on_mm` - Renewal reminder mass message (paid only)
- `expired_subscriber` - Win-back for expired subs (paid only)

**Solutions:**

1. **Schedule retention content on days 5-7:**
   - Day 5 (Friday): `renew_on_post` on feed
   - Day 6 (Saturday): `renew_on_mm` mass message
   - Day 7 (Sunday): Final reminder or `expired_subscriber` if needed

2. **Best practices:**
   - Combine renewal reminder with exclusive content preview
   - Emphasize value received during current subscription
   - Create FOMO about upcoming week's content

3. **Note:** This is INFO level - not an error, just a recommendation.

---

### Follow-up Timing Issues

**Symptom:**
```
ValidationIssue: Follow-up timing outside 15-45 minute window
```

**Cause:** Bump messages scheduled too early or too late after PPV.

**Solutions:**

1. **Auto-correction adjusts timing automatically.**

2. **Valid timing windows:**
   - Evening (6-11 PM): 15-25 minutes
   - Afternoon (2-5 PM): 20-30 minutes
   - Morning (9-1 PM): 30-45 minutes

---

## Schedule Uniqueness Issues

**Symptom:**
```
WARNING: Could not generate unique schedule after 5 attempts
WARNING: Schedule fingerprint abc123def456 found in recent schedules
INFO: Uniqueness rate: 78.5% (target: 85%+)
```

**Cause:** Schedule pattern too similar to recent weeks, creating detectable patterns.

**Why this matters:**
- OnlyFans algorithm may detect repetitive patterns
- Subscribers notice predictable scheduling
- Reduces perceived authenticity and spontaneity

**What creates the fingerprint:**
- Timing patterns (e.g., always PPV at 9 PM on Mondays)
- Content type sequences (e.g., always PPV → Bundle → PPV)
- Pricing patterns (e.g., always $15, $22, $28)
- Day-of-week distributions

**Solutions:**

1. **Add caption pool variety:**
   ```sql
   -- Check caption pool size
   SELECT
       content_type_id,
       COUNT(*) as available_captions
   FROM caption_bank
   WHERE creator_id = 'abc123' AND freshness_score >= 30
   GROUP BY content_type_id;
   ```

   If any content type has < 10 fresh captions, add more to increase variety.

2. **Wait for historical pattern accumulation:**
   The uniqueness check requires 90+ days of scheduling history to detect patterns accurately.
   ```bash
   # Check schedule history
   sqlite3 $EROS_DATABASE_PATH "SELECT COUNT(*) FROM schedule_history WHERE creator_id = 'abc123'"
   ```

3. **Increase timing variance:**
   ```python
   # In generate_schedule.py or template
   timing_variance_range = 45  # Increase from default 30 minutes
   ```

4. **Override uniqueness check (use sparingly):**
   ```bash
   # Force generation even if not unique
   python scripts/generate_schedule.py --creator missalexa --week 2025-W01 --force
   ```

5. **Manual timing adjustments:**
   After generation, manually adjust 1-2 PPV times by 30-60 minutes to break patterns.

**Target metrics:**
- Uniqueness rate: 85%+ (excellent)
- Timing variance: 30-45 minutes from template
- Caption rotation: No caption reused within 30 days
- Fingerprint collision: 0 exact matches in last 4 weeks

---

## Content Type Issues

### Content Type Not Found

**Symptom:**
```
ContentTypeNotFoundError: Content type 'unknown_type' not registered
KeyError: Content type 'solo' not found in registry
```

**Cause:** Invalid or outdated content type name used in scheduling.

**Valid content types (20 total):**

**Tier 1 - Direct Revenue (priority=1):**
- `ppv` - Pay-per-view mass message
- `ppv_follow_up` - Bump message 15-45 min after PPV
- `bundle` - Multi-piece content bundle
- `flash_bundle` - Limited-time flash sale bundle
- `snapchat_bundle` - Premium Snapchat access bundle

**Tier 2 - Feed/Wall (priority=2):**
- `vip_post` - VIP tier exclusive content (paid only)
- `first_to_tip` - Tip goal campaign
- `link_drop` - External link share
- `normal_post_bump` - Regular feed engagement post
- `renew_on_post` - Subscription renewal reminder (paid only)
- `game_post` - Interactive game/contest (max 1/week)
- `flyer_gif_bump` - Visual bump with flyer/GIF
- `descriptive_bump` - Detailed content preview
- `wall_link_drop` - Link drop directly on wall
- `live_promo` - Upcoming live stream promotion

**Tier 3 - Engagement (priority=3):**
- `dm_farm` - Direct message engagement (max 2/day, 10/week)
- `like_farm` - Like-for-reward post (max 2/day, 10/week)
- `text_only_bump` - Text-only mass message bump

**Tier 4 - Retention (priority=4):**
- `renew_on_mm` - Renewal reminder mass message (paid only)
- `expired_subscriber` - Win-back message for expired subs (paid only)

**Solutions:**

1. **List all valid content types:**
   ```bash
   python scripts/content_type_registry.py
   ```

2. **Check if content type exists:**
   ```python
   from content_type_registry import REGISTRY

   if "vip_post" in REGISTRY:
       vip = REGISTRY.get("vip_post")
       print(f"Min spacing: {vip.min_spacing_hours}h")
   ```

3. **Update old content type references:**
   - Old database may have `solo`, `bg`, `group` → use `ppv` with content_subtype
   - Old `sextape` → use `ppv` with appropriate pricing
   - Old `custom` → use `ppv` or `bundle` depending on context

---

### Placeholder Content Warnings (V031)

**Symptom:**
```
ValidationInfo: V031 - Slot at 2025-01-06 14:00 has placeholder content (needs manual entry)
ValidationInfo: V031 - Slot 15 uses placeholder - no caption available for content type 'vip_post'
```

**Cause:** No captions available in the pool for the requested content type.

**Why placeholders exist:**
- Template requires a content type but caption bank is empty
- Vault shows `has_content = 1` but no matching captions in caption_bank
- Freshness threshold too high for available captions

**Solutions:**

1. **Add captions for the content type:**
   ```sql
   INSERT INTO caption_bank (
       creator_id, content_type_id, caption_text, freshness_score
   ) VALUES (
       'abc123', 6, 'VIP exclusive content caption here...', 100.0
   );
   ```

2. **Update vault availability:**
   ```sql
   -- Mark content type as unavailable if truly not available
   UPDATE vault_matrix
   SET has_content = 0
   WHERE creator_id = 'abc123' AND content_type_id = 6;
   ```

3. **Manual caption entry before execution:**
   Placeholders are INFO level - they don't block schedule generation but need attention before sending.

4. **Check caption pool status:**
   ```bash
   python scripts/calculate_freshness.py --creator missalexa --report
   ```

5. **Lower freshness threshold temporarily:**
   ```python
   # In generate_schedule.py
   MIN_FRESHNESS = 20  # Instead of default 30
   ```

---

## Auto-Correction Issues

### Auto-Correction Loop Reached Maximum Passes

**Symptom:**
```
WARNING: Auto-correction reached maximum passes (2). Some issues remain.
INFO: Applied 15 auto-corrections: move_slot(item_5), move_slot(item_8), swap_caption(item_12)...
```

**Cause:** Too many conflicting constraints or issues that can't be resolved in 2 validation passes.

**What auto-correction fixes:**
1. PPV spacing violations (<3hr) → Move to next valid slot
2. Duplicate captions → Swap with unused caption
3. Freshness below 30 → Swap with fresher caption
4. Follow-up timing outside 15-45min → Adjust to 25 minutes
5. Page type violations → Remove paid-only content from free page
6. VIP post spacing → Move to valid 24h+ slot
7. Engagement limits → Move to next day or remove excess
8. Bundle/flash bundle spacing → Move to valid slot
9. Game post exceeded → Remove excess (max 1/week)
10. Bump variant rotation → Swap content type

**What auto-correction CANNOT fix:**
- Content rotation patterns (requires human judgment)
- Pricing decisions
- Volume target mismatches
- Vault availability issues
- Caption pool exhaustion

**Solutions:**

1. **Review remaining issues manually:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --format json > issues.json
   ```

2. **Fix root causes:**
   - If PPV spacing keeps failing: Reduce daily PPV target
   - If caption swaps keep failing: Add more captions to pool
   - If timing conflicts persist: Extend scheduling window

3. **Reduce schedule complexity:**
   ```python
   # Reduce volume for difficult weeks
   strategy.ppv_per_day = 3  # Instead of 5
   strategy.bumps_per_day = 2  # Instead of 4
   ```

4. **Increase max correction passes (advanced):**
   ```python
   # In validate_schedule.py
   result = validator.validate_with_corrections(
       items, max_passes=3  # Increase from default 2
   )
   ```

5. **Check for conflicting constraints:**
   Example: If you require 5 PPVs/day but only have 8 hours of available time slots,
   the spacing rules make this impossible. Reduce volume or extend time window.

---

## Performance Issues

### Slow Schedule Generation

**Symptom:** Generation takes > 30 seconds for quick mode.

**Solutions:**

1. **Check database indices:**
   ```sql
   SELECT name FROM sqlite_master WHERE type='index';
   ```

2. **Add recommended indices:**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_captions_creator
   ON caption_bank(creator_id, freshness_score);
   ```

3. **Use connection pooling (enabled by default):**
   ```python
   from scripts import get_connection
   with get_connection() as conn:
       # Reuses connection
   ```

---

### Memory Issues with Large Batches

**Symptom:** High memory usage during batch processing.

**Solutions:**

1. **Process in smaller batches:**
   ```bash
   # Instead of all at once
   for creator in $(cat tier1_creators.txt); do
       python scripts/generate_schedule.py --creator "$creator"
   done
   ```

2. **Clear connection pool:**
   ```python
   from scripts.database import close_all_connections
   close_all_connections()
   ```

---

## Import Errors

### ModuleNotFoundError

**Symptom:**
```
ModuleNotFoundError: No module named 'scripts.database'
```

**Solutions:**

1. **Add to Python path:**
   ```bash
   export PYTHONPATH="${PYTHONPATH}:~/.claude/skills/eros-schedule-generator"
   ```

2. **Install as package:**
   ```bash
   cd ~/.claude/skills/eros-schedule-generator
   pip install -e .
   ```

3. **Use relative imports from scripts directory:**
   ```bash
   cd ~/.claude/skills/eros-schedule-generator
   python -m scripts.generate_schedule --creator missalexa
   ```

---

### Circular Import Errors

**Symptom:**
```
ImportError: cannot import name 'X' from partially initialized module
```

**Solutions:**

1. **Use lazy imports:**
   The package uses deferred imports to avoid circular dependencies.

2. **Import specific modules:**
   ```python
   # Instead of: from scripts import everything
   from scripts.database import DB_PATH
   from scripts.hook_detection import HookType
   ```

---

## Getting Help

1. **Check logs:**
   ```python
   from scripts import configure_logging
   configure_logging(level="DEBUG")
   ```

2. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

3. **Database health check:**
   ```bash
   sqlite3 $EROS_DATABASE_PATH "PRAGMA integrity_check"
   ```

4. **Verify deployment:**
   ```bash
   python scripts/verify_deployment.py
   ```

---

## Quick Reference: Error Messages

| Error Code | Error | Quick Fix |
|------------|-------|-----------|
| - | `DatabaseNotFoundError` | Set `EROS_DATABASE_PATH` environment variable |
| - | `CreatorNotFoundError` | Check creator exists and `is_active = 1` |
| - | `CaptionExhaustionError` | Wait 7-14 days or add new captions |
| - | `VaultEmptyError` | Update `vault_matrix` table |
| - | `ContentTypeNotFoundError` | Use valid content type from registry (20 types) |
| V001 | PPV spacing < 3 hours | Use `--auto-fix` flag, moves to next valid slot |
| V002 | Freshness below 30 | Use `--auto-fix` flag, swaps caption |
| V003 | Follow-up timing outside 15-45min | Use `--auto-fix` flag, adjusts to 25min |
| V004 | Duplicate captions | Use `--auto-fix` flag, swaps duplicate |
| V015 | Hook rotation (consecutive same hook) | Diversify caption pool, 0.7x penalty applied |
| V016 | Hook diversity < 4 types | Add captions with varied hook types |
| V020 | Page type violation (paid content on free) | Remove item or change page type to "paid" |
| V021 | VIP post spacing < 24h | Use `--auto-fix`, max 1 VIP post per day |
| V022 | Link drop spacing < 4h | Use `--auto-fix`, space 4+ hours apart |
| V023 | Engagement daily limit > 2/day | Use `--auto-fix`, moves to next day |
| V024 | Engagement weekly limit > 10/week | Use `--auto-fix`, removes excess |
| V026 | Bundle spacing < 24h | Use `--auto-fix`, max 1 bundle per day |
| V027 | Flash bundle spacing < 48h | Use `--auto-fix`, max 1 flash bundle per 2 days |
| V028 | Game post > 1/week | Use `--auto-fix`, removes excess |
| V029 | Bump variant rotation (3x consecutive) | Use `--auto-fix`, swaps content type |
| V031 | Placeholder content (no caption) | Add captions or update vault_matrix |
| - | Schedule uniqueness < 85% | Add caption variety, wait for history, or use `--force` |
| - | Auto-correction max passes reached | Fix root causes, reduce complexity, or increase max_passes |
| - | `ModuleNotFoundError` | Add skill directory to `PYTHONPATH` |
| - | `ImportError: circular` | Use specific imports, not wildcard |

---

## Troubleshooting Workflows

### Workflow 1: New Schedule Generation Failing

**Scenario:** Schedule generation fails or produces many validation errors.

**Step-by-step diagnosis:**

1. **Check database connection:**
   ```bash
   ls -la $EROS_DATABASE_PATH
   sqlite3 $EROS_DATABASE_PATH "PRAGMA integrity_check"
   ```

2. **Verify creator exists and is active:**
   ```bash
   sqlite3 $EROS_DATABASE_PATH "SELECT page_name, is_active, page_type FROM creators WHERE page_name = 'missalexa'"
   ```

3. **Check caption pool availability:**
   ```bash
   python scripts/calculate_freshness.py --creator missalexa --report
   ```
   **Target:** 50+ captions with freshness >= 30 per content type

4. **Verify vault matrix:**
   ```sql
   SELECT content_type_id, has_content, last_checked
   FROM vault_matrix
   WHERE creator_id = 'abc123' AND has_content = 1;
   ```
   **Expected:** At least 5-7 content types available

5. **Generate with validation:**
   ```bash
   python scripts/generate_schedule.py --creator missalexa --week 2025-W01 --page-type free --validate
   ```

6. **If validation fails, use auto-fix:**
   ```bash
   python scripts/validate_schedule.py --input output/schedule.json --auto-fix --page-type free
   ```

7. **Check remaining issues:**
   If errors persist after auto-fix, review the validation report for non-fixable issues.

---

### Workflow 2: Schedule Keeps Failing Uniqueness Check

**Scenario:** Warning "Could not generate unique schedule after 5 attempts".

**Step-by-step diagnosis:**

1. **Check historical schedule count:**
   ```bash
   sqlite3 $EROS_DATABASE_PATH "SELECT COUNT(*) FROM schedule_history WHERE creator_id = 'abc123'"
   ```
   **Minimum needed:** 12 weeks (90 days) of history

2. **Check caption pool diversity:**
   ```sql
   SELECT content_type_id, COUNT(*) as count
   FROM caption_bank
   WHERE creator_id = 'abc123' AND freshness_score >= 30
   GROUP BY content_type_id;
   ```
   **Target:** 10+ captions per content type

3. **Review recent fingerprints:**
   ```sql
   SELECT week_start, schedule_fingerprint, uniqueness_score
   FROM schedule_history
   WHERE creator_id = 'abc123'
   ORDER BY week_start DESC
   LIMIT 4;
   ```

4. **Solutions (pick one):**
   - **Option A:** Add more caption variety to the pool
   - **Option B:** Wait 1-2 weeks for pattern history to accumulate
   - **Option C:** Force generation with `--force` flag (use sparingly)
   - **Option D:** Manually adjust 2-3 timing slots by 30-60 minutes after generation

---

### Workflow 3: Too Many Auto-Correction Warnings

**Scenario:** Auto-correction applies 10+ fixes but issues remain.

**Step-by-step diagnosis:**

1. **Review what's being fixed:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix 2>&1 | grep "Applied"
   ```
   Look for patterns (e.g., "move_slot" appearing 8+ times)

2. **Identify root cause:**
   - **Many move_slot:** Volume too high for available time slots
   - **Many swap_caption:** Caption pool depleted or freshness too low
   - **Many remove_item:** Page type violations or limit exceeded

3. **Fix root causes:**

   **If PPV spacing keeps failing:**
   ```python
   # Reduce daily PPV target
   strategy.ppv_per_day = 3  # Instead of 5
   ```

   **If caption swaps keep failing:**
   ```bash
   # Check available fresh captions
   python scripts/calculate_freshness.py --creator missalexa --update
   ```

   **If page type violations:**
   ```bash
   # Generate with correct page type
   python scripts/generate_schedule.py --creator missalexa --week 2025-W01 --page-type paid
   ```

4. **Regenerate after fixing root cause:**
   Once the underlying issue is fixed, regenerate the schedule from scratch.

---

### Workflow 4: Placeholder Content Warnings

**Scenario:** Multiple V031 warnings about placeholder content.

**Step-by-step diagnosis:**

1. **Identify which content types have placeholders:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --format json | jq '.issues[] | select(.rule_name == "V031")'
   ```

2. **Check caption availability for that type:**
   ```sql
   SELECT COUNT(*) as available_captions
   FROM caption_bank
   WHERE creator_id = 'abc123'
     AND content_type_id = 6  -- VIP post
     AND freshness_score >= 30;
   ```

3. **Solutions (pick appropriate one):**

   **If 0 captions available:**
   ```sql
   -- Add captions for this content type
   INSERT INTO caption_bank (creator_id, content_type_id, caption_text, freshness_score)
   VALUES ('abc123', 6, 'VIP exclusive content...', 100.0);
   ```

   **If content type not actually available:**
   ```sql
   -- Mark as unavailable in vault
   UPDATE vault_matrix SET has_content = 0
   WHERE creator_id = 'abc123' AND content_type_id = 6;
   ```

   **If captions exist but freshness too low:**
   ```bash
   # Wait for freshness recovery or lower threshold temporarily
   python scripts/generate_schedule.py --creator missalexa --min-freshness 20
   ```

---

### Workflow 5: Engagement Limit Exceeded

**Scenario:** V023/V024 warnings about too many engagement posts.

**Step-by-step diagnosis:**

1. **Count current engagement posts:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --format json | jq '.issues[] | select(.rule_name | startswith("V02"))'
   ```

2. **Review distribution by day:**
   ```sql
   SELECT scheduled_date, COUNT(*) as engagement_count
   FROM schedule_items
   WHERE content_type_name IN ('dm_farm', 'like_farm')
   GROUP BY scheduled_date;
   ```

3. **Solutions:**

   **Auto-correction handles it:**
   ```bash
   python scripts/validate_schedule.py --input schedule.json --auto-fix
   ```
   Moves excess to next day or removes if weekly limit exceeded.

   **Manual rebalancing:**
   - Limit to 2 engagement posts per day
   - Spread across 5-7 days (not all 7)
   - Use strategically on low-PPV days

4. **Best practices:**
   - Use dm_farm for direct 1-on-1 engagement
   - Use like_farm for algorithm boost
   - Don't use both on the same day

---

## Advanced Debugging

### Enable Verbose Logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Inspect Generated Schedule

```python
import json

with open('output/schedule.json', 'r') as f:
    schedule = json.load(f)

print(f"Total items: {len(schedule['items'])}")
print(f"PPVs: {sum(1 for i in schedule['items'] if i['type'] == 'ppv')}")
print(f"Bumps: {sum(1 for i in schedule['items'] if i['type'] == 'bump')}")
```

### Database Query Examples

```sql
-- Check caption pool size per content type
SELECT
    ct.type_name,
    COUNT(*) as caption_count,
    AVG(cb.freshness_score) as avg_freshness
FROM caption_bank cb
JOIN content_types ct ON cb.content_type_id = ct.content_type_id
WHERE cb.creator_id = 'abc123'
GROUP BY ct.type_name;

-- Find recently used captions
SELECT
    caption_text,
    times_used,
    last_used_at,
    freshness_score
FROM caption_bank
WHERE creator_id = 'abc123'
ORDER BY last_used_at DESC
LIMIT 10;

-- Check persona boost distribution
SELECT
    ROUND(persona_boost, 1) as boost_level,
    COUNT(*) as count
FROM caption_bank
WHERE creator_id = 'abc123'
GROUP BY ROUND(persona_boost, 1)
ORDER BY boost_level;
```

---

## Contact & Support

For issues not covered in this guide:

1. Check the main [README.md](README.md) for usage examples
2. Review [ARCHITECTURE.md](references/architecture.md) for system design
3. Examine [database-schema.md](references/database-schema.md) for data structure
4. Run the test suite to verify installation: `pytest tests/ -v`

**Version:** 2.1.0
**Last Updated:** 2025-12-09

---

## Version 2.1 New Features

This troubleshooting guide covers v2.1 enhancements:

**20 Content Types** - Expanded from 7 to 20 schedulable content types with tier-based priority
**Page Type Validation** - Enforces paid-only content restrictions (V020)
**Advanced Spacing Rules** - Content-specific spacing (VIP posts 24h, flash bundles 48h, etc.)
**Engagement Limits** - Daily (2/day) and weekly (10/week) limits for dm_farm/like_farm
**Hook Rotation** - Anti-detection pattern analysis with 6 psychological hook types
**Schedule Uniqueness** - Fingerprint-based uniqueness scoring to prevent detectable patterns
**Auto-Correction** - Self-healing validation with 10 auto-fixable issue types
**Pool-Based Earnings** - Caption selection weighted by historical conversion performance

For the complete feature list, see [CHANGELOG.md](CHANGELOG.md)
