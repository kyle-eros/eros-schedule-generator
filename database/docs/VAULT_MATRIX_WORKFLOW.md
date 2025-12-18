# Vault Matrix Workflow Guide

## Overview

The vault_matrix table controls which content types are allowed for each creator. It acts as a hard filter in the schedule generation pipeline, ensuring only captions matching a creator's available content are selected.

**Architecture**: Hybrid approach
- **User Interface**: Google Sheets (wide format - easy to visualize and edit)
- **Database Storage**: Normalized table (optimized for MCP queries)
- **Bridge**: Python import/export script (`vault_matrix_sync.py`)

## Quick Start

### 1. Export Current Vault Matrix

Export the current database state to a CSV file for editing:

```bash
cd database/scripts
python3 vault_matrix_sync.py export --output vault_matrix.csv
```

This creates a CSV file with:
- One row per creator (page_name)
- One column per content type (37 columns)
- Values: `1` (allowed) or `0` (not allowed)
- Last column: `vault_notes` for per-creator notes

### 2. Edit in Google Sheets

1. Upload `vault_matrix.csv` to Google Sheets
2. Edit permissions:
   - `1` = Creator has this content type (allowed in captions)
   - `0` = Creator does NOT have this content type (blocked)
3. Edit `vault_notes` column with creator-specific restrictions
4. Download as CSV when done

### 3. Import Back to Database

**Dry-run first** (preview changes without applying):
```bash
python3 vault_matrix_sync.py import-csv --input vault_matrix_edited.csv --dry-run
```

**Apply changes** (after reviewing dry-run):
```bash
python3 vault_matrix_sync.py import-csv --input vault_matrix_edited.csv
```

## CSV Format Specification

### Header Row

```
page_name,anal,behind_scenes,blowjob,...,vault_notes
```

**Required columns**:
- `page_name` (must match creators.page_name exactly)

**Optional columns**:
- Content type columns (must match content_types.type_name)
- `vault_notes` (per-creator notes)

### Data Rows

```
alexia,1,0,1,0,1,0,1,...,"Prohibited: Face closeups. Prefers: Solo on Mon/Tue"
chloe_wildd,0,1,1,1,0,1,0,...,"Use flirty tone, avoid explicit language in teasers"
```

**Values**:
- `1` = Allowed (creator has this content)
- `0` = Not allowed (creator doesn't have this content)
- Blank = Defaults to `0`
- Any positive number = Coerced to `1`
- Negative numbers = Coerced to `0`

### Vault Notes Examples

**Prohibited content**:
```
"Prohibited: Face closeups due to privacy preference"
"No anal or rough content - per creator request"
```

**Scheduling preferences**:
```
"Prefers: Solo content on Mondays, B/G content Wed-Fri"
"Peak engagement: Evening posts (8pm-10pm PST)"
```

**Tone/voice guidelines**:
```
"Use flirty tone, avoid explicit language in teasers"
"Keep captions short and playful - matches TikTok style"
```

**Special notes**:
```
"Hiatus: Jan 15-30 - pre-schedule lighter volume"
"New content: POV videos coming Feb 1st - update vault matrix"
```

## Content Type Reference

Current content types (37 total):

### Explicit (15 types)
- `anal`, `boy_girl`, `boy_girl_girl`, `blowjob`, `blowjob_dildo`
- `creampie`, `deepthroat`, `deepthroat_dildo`, `girl_girl`, `girl_girl_girl`
- `pussy_play`, `squirt`, `tits_play`, `toy_play`, `dom_sub`

### Softcore/Implied (7 types)
- `implied_pussy_play`, `implied_solo`, `implied_tits_play`, `implied_toy_play`
- `joi`, `lingerie`, `teasing`

### Specialty (8 types)
- `pov`, `gfe`, `feet`, `pool_outdoor`, `shower_bath`
- `behind_scenes`, `live_stream`, `story_roleplay`

### Revenue/Meta (7 types)
- `bundle_offer`, `exclusive_content`, `flash_sale`, `dick_rating`
- `renewal_retention`, `solo`, `tip_request`

## Integration with Schedule Generation

### How Vault Filtering Works

When the schedule generation pipeline selects captions:

```
1. Agent requests: get_send_type_captions(creator_id='alexia', send_type_key='ppv_unlock')
2. MCP query: SELECT FROM caption_bank
              INNER JOIN vault_matrix ON content_type_id
              WHERE creator_id='alexia' AND has_content=1
3. Result: Only captions with content_types where vault_matrix.has_content=1
```

**Example**:
- Creator: alexia
- Vault matrix: `solo=1`, `boy_girl=1`, `anal=0`
- Caption pool: 59,405 total captions
- Filtered pool: Only captions tagged as `solo` or `boy_girl` (anal blocked)

### Phase 3: Content Curator

The content-curator agent relies on vault_matrix filtering:

```python
# Agent doesn't manually filter - MCP handles it
captions = get_send_type_captions(
    creator_id='alexia',
    send_type_key='ppv_unlock',
    min_performance=40,
    min_freshness=30
)
# Returns: Already filtered to vault-approved content types
```

## Common Workflows

### Adding a New Creator

1. Export current vault matrix:
   ```bash
   python3 vault_matrix_sync.py export --output vault_matrix.csv
   ```

2. Add new row in Google Sheets:
   ```
   page_name: new_creator_name
   Set 1/0 for each content type
   vault_notes: "Initial setup - verify with creator"
   ```

3. Import updated CSV:
   ```bash
   python3 vault_matrix_sync.py import-csv --input vault_matrix.csv
   ```

### Adding a New Content Type

**Database update needed** (one-time):
```sql
INSERT INTO content_types (type_name, type_category, description, priority_tier)
VALUES ('cosplay', 'specialty', 'Cosplay content', 2);
```

**Vault matrix update**:
1. Export vault matrix (new column auto-appears)
2. Set 1/0 for all creators for the new content type
3. Import back to database

### Bulk Update (e.g., "Enable POV for all Tier 1 creators")

1. Export to CSV
2. In Google Sheets:
   - Filter by performance tier (if tracking externally)
   - Set `pov=1` for selected creators
3. Import back to database

### Creator Content Refresh

When a creator shoots new content:

1. Export vault matrix
2. Update their row:
   - `anal=0` → `anal=1` (if new anal content available)
   - `vault_notes`: "New anal content added Dec 2025"
3. Import back to database
4. Next schedule generation automatically includes anal captions

## Validation & Error Handling

### Import Validation

The import script validates:

1. **Content type names**: Must match `content_types.type_name`
   - Error example: `"Invalid content types: ['xxx', 'yyy']"`
   - Fix: Check header row matches database content types

2. **Page names**: Must match `creators.page_name`
   - Warning: `"Unknown creators (will skip): ['creator_123']"`
   - Fix: Verify page_name spelling, check creator is active

3. **Values**: Coerced to 0/1
   - `2`, `5`, `"yes"` → `1`
   - `-1`, `0`, `""` → `0`

### Dry-Run Mode

Always use `--dry-run` first:

```bash
python3 vault_matrix_sync.py import-csv --input vault.csv --dry-run
```

Shows:
- Total updates that will be applied
- Sample of changes (first 10 rows)
- Validation errors/warnings
- Does NOT modify database

## Logging

All operations are logged to:
```
database/logs/vault_sync_YYYYMMDD_HHMMSS.log
```

Log includes:
- Timestamp for each operation
- Rows loaded, updated, skipped
- Validation errors
- Success/failure status

View latest log:
```bash
ls -t database/logs/vault_sync_*.log | head -1 | xargs cat
```

## Troubleshooting

### "Invalid content types found"

**Cause**: CSV header contains content type name not in database

**Fix**:
1. Check available content types:
   ```sql
   SELECT type_name FROM content_types ORDER BY type_name;
   ```
2. Update CSV header to match exactly (case-sensitive)

### "Unknown creators (will skip)"

**Cause**: page_name in CSV doesn't match database

**Fix**:
1. Check active creators:
   ```sql
   SELECT page_name FROM creators WHERE is_active=1 ORDER BY page_name;
   ```
2. Update CSV page_name to match exactly

### Export shows fewer creators than expected

**Cause**: Some creators have no vault_matrix entries

**Fix**:
1. Check which creators are missing:
   ```sql
   SELECT c.page_name
   FROM creators c
   LEFT JOIN vault_matrix vm ON c.creator_id = vm.creator_id
   WHERE vm.vault_id IS NULL;
   ```
2. Add entries for missing creators

### Import changes not reflected in schedule generation

**Cause**: Cache or MCP server not reloaded

**Fix**:
1. Restart MCP server (if running)
2. Verify changes applied:
   ```sql
   SELECT has_content FROM vault_matrix
   WHERE creator_id='...' AND content_type_id=...;
   ```

## Best Practices

### 1. Always Use Dry-Run First

```bash
# ✓ Good
python3 vault_matrix_sync.py import-csv --input vault.csv --dry-run
python3 vault_matrix_sync.py import-csv --input vault.csv

# ✗ Bad (no preview)
python3 vault_matrix_sync.py import-csv --input vault.csv
```

### 2. Keep Backup CSVs

```bash
# Export with timestamp
python3 vault_matrix_sync.py export --output "vault_backup_$(date +%Y%m%d).csv"
```

### 3. Document Major Changes in vault_notes

```
vault_notes: "Dec 2025: Added anal, creampie content. Removed feet per creator request."
```

### 4. Verify After Import

```sql
-- Check specific creator's permissions
SELECT ct.type_name, vm.has_content
FROM vault_matrix vm
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE vm.creator_id = (SELECT creator_id FROM creators WHERE page_name='alexia')
AND vm.has_content = 1
ORDER BY ct.type_name;
```

### 5. Periodic Audits

Monthly review:
1. Export vault matrix
2. Verify each creator's permissions match actual vault inventory
3. Update vault_notes with content refresh dates
4. Archive old backup CSVs

## Advanced Usage

### Export Only Active Creators

Modify the export query in `vault_matrix_sync.py`:

```python
query = """
SELECT c.page_name, ct.type_name as content_type, vm.has_content, c.vault_notes
FROM vault_matrix vm
JOIN creators c ON vm.creator_id = c.creator_id
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE c.is_active = 1  -- Add this filter
ORDER BY c.page_name, ct.priority_tier, ct.type_name
"""
```

### Export Specific Content Type Categories

Filter to explicit content only:

```python
WHERE ct.type_category = 'explicit'
```

### Programmatic Updates

Use the script as a module:

```python
from vault_matrix_sync import VaultMatrixSync

syncer = VaultMatrixSync('/path/to/eros_sd_main.db')

# Export
syncer.export_to_csv('vault.csv')

# Import
syncer.import_from_csv('vault_edited.csv', dry_run=False)
```

## Related Documentation

- `CLAUDE.md` - Main project documentation
- `database/migrations/013_vault_notes.sql` - Migration that added vault_notes column
- `mcp/eros_db_server.py` - MCP queries that use vault_matrix filtering
- `.claude/agents/content-curator.md` - Agent that relies on vault filtering

## Support

For issues or questions:
1. Check logs: `database/logs/vault_sync_*.log`
2. Review this guide's Troubleshooting section
3. Verify database schema: `sqlite3 eros_sd_main.db ".schema vault_matrix"`
