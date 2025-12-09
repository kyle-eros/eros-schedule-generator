# EROS Schedule Generator - Troubleshooting Guide

Solutions for common issues when using the EROS Schedule Generator.

## Table of Contents
- [Database Issues](#database-issues)
- [Caption Issues](#caption-issues)
- [Validation Failures](#validation-failures)
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

| Error | Quick Fix |
|-------|-----------|
| `DatabaseNotFoundError` | Set `EROS_DATABASE_PATH` environment variable |
| `CreatorNotFoundError` | Check creator exists and `is_active = 1` |
| `CaptionExhaustionError` | Wait 7-14 days or add new captions |
| `VaultEmptyError` | Update `vault_matrix` table |
| `ValidationIssue: spacing` | Use `--auto-fix` flag |
| `ValidationIssue: rotation` | Add more content variety |
| `ModuleNotFoundError` | Add skill directory to `PYTHONPATH` |
| `ImportError: circular` | Use specific imports, not wildcard |

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

**Version:** 2.0.0
**Last Updated:** 2025-12-09
