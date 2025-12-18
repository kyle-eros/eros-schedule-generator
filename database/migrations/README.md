# Database Migrations

> Migration system documentation for the EROS Schedule Generator database schema. All migrations are designed to be idempotent and can be safely run multiple times.

**Version:** 2.3.0 | **Updated:** 2025-12-18

---

## Overview

This directory contains SQL migration scripts that progressively build and enhance the EROS Schedule Generator database schema. Each migration is numbered sequentially and includes clear documentation of its purpose and effects.

## Migration Philosophy

- **Idempotent**: All migrations can be run multiple times without causing errors or data corruption
- **Reversible**: Rollback scripts provided where applicable
- **Documented**: Each migration includes purpose, dependencies, and tables affected
- **Safe**: Uses SQLite-safe operations (ADD COLUMN, CREATE IF NOT EXISTS)
- **Tracked**: Migration execution recorded in `schema_migrations` table

---

## Migration Inventory

### Core Schema Migrations

#### 002_volume_assignments.sql
**Purpose**: Volume assignment tracking with audit trail
**Created**: 2025-11-30
**Tables Added**:
- `volume_assignments` - Creator volume level assignments with history

**Key Features**:
- Fan-count-based automatic assignments
- Manual operator override support
- Full audit trail of changes
- Historical reporting capability

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/002_volume_assignments.sql
```

---

#### 003_volume_performance.sql
**Purpose**: Volume performance tracking for adaptive optimization
**Created**: 2025-11-30
**Tables Added**:
- `volume_performance_tracking` - Track saturation and opportunity scores

**Key Features**:
- Saturation score calculation (0-100)
- Opportunity score calculation (0-100)
- Revenue trend analysis
- Adaptive volume calibration signals

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/003_volume_performance.sql
```

---

#### 005_enhanced_personas.sql
**Purpose**: Enhanced creator persona profiles
**Created**: 2025-12-01
**Tables Added**:
- `creator_personas_enhanced` - Advanced persona attributes
- `creator_voice_samples` - Voice pattern examples

**Key Features**:
- Detailed tone and archetype definitions
- Emoji usage patterns
- Slang level configuration
- Voice authenticity samples

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/005_enhanced_personas.sql
```

---

#### 006_caption_type_taxonomy_migration.sql
**Purpose**: Caption type taxonomy and mapping system
**Created**: 2025-12-10
**Tables Added**:
- Enhanced caption_bank with caption_type column

**Key Features**:
- 9 standardized caption types
- Type-based caption selection
- Performance tracking by type

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/006_caption_type_taxonomy_migration.sql
```

---

#### 007_schedule_generator_enhancements.sql
**Purpose**: Schedule generator infrastructure and metadata
**Created**: 2025-12-15
**Tables Added**:
- `schedule_generation_queue` - Async schedule processing queue
- `schema_migrations` - Migration tracking

**Columns Added**:
- `schedule_templates.algorithm_params` - Algorithm configuration JSON
- `schedule_templates.agent_execution_log` - Agent workflow log
- `schedule_templates.quality_validation_score` - Quality metrics
- `caption_bank.freshness_score` - Usage decay tracking

**Views Added**:
- `v_schedule_ready_creators` - Creators ready for scheduling

**Key Features**:
- Algorithm version tracking
- Quality score validation
- Caption freshness decay
- Schedule generation queue
- Creator readiness assessment

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/007_schedule_generator_enhancements.sql
```

**Rollback**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/007_rollback.sql
```

---

### Send Type System Migrations (v2.0)

#### 008_send_types_foundation.sql
**Purpose**: Foundation tables for 21-type send system
**Created**: 2025-12-15
**Tables Added**:
- `send_types` - 21 distinct send type definitions
- `channels` - 5 distribution channels
- `audience_targets` - 10 targeting segments

**Key Features**:
- Complete send type taxonomy (Revenue/Engagement/Retention)
- Channel configuration with targeting support
- Audience segment definitions
- Page type restrictions (paid/free/both)
- Expiration and followup behavior

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/008_send_types_foundation.sql
```

---

#### 008_send_types_seed_data.sql
**Purpose**: Seed data for all 21 send types
**Created**: 2025-12-15
**Data Inserted**:
- 21 send type records with complete configuration
- 5 channel records
- 10 audience target records

**Dependencies**: Must run after `008_send_types_foundation.sql`

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/008_send_types_seed_data.sql
```

---

#### 008_mapping_tables.sql
**Purpose**: Caption type to send type mappings
**Created**: 2025-12-15
**Tables Added**:
- `send_type_caption_requirements` - Caption type mappings

**Data Inserted**:
- Mappings for all 21 send types to compatible caption types

**Dependencies**: Must run after `008_send_types_seed_data.sql`

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/008_mapping_tables.sql
```

---

#### 008_schedule_items_enhancement.sql
**Purpose**: Enhanced schedule_items for send type system
**Created**: 2025-12-15
**Columns Added** to `schedule_items`:
- `send_type_id` - Foreign key to send_types
- `channel_id` - Foreign key to channels
- `target_id` - Foreign key to audience_targets
- `linked_post_url` - For link_drop types
- `expires_at` - Expiration timestamp
- `parent_send_id` - Parent item reference
- `is_followup` - Followup flag
- `followup_delay_minutes` - Delay configuration
- `media_type` - Media format (none/picture/gif/video/flyer)
- `campaign_goal` - Tip goal for campaigns

**Dependencies**: Must run after `008_send_types_foundation.sql`

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/008_schedule_items_enhancement.sql
```

**Rollback**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/008_rollback.sql
```

---

### Wave 6+ Migrations

#### 009_caption_bank_missing_columns.sql
**Purpose**: Add missing caption_bank columns for send type system
**Created**: 2025-12-15
**Columns Added**:
- Additional metadata for caption type compatibility

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/009_caption_bank_missing_columns.sql
```

---

#### 010_wave6_update_confidence.sql
**Purpose**: Update confidence scores in volume performance tracking
**Created**: 2025-12-16
**Changes**: Algorithm refinements for confidence calculation

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/010_wave6_update_confidence.sql
```

---

#### wave6_fix_caption_requirements.sql
**Purpose**: Fix caption type requirement mappings
**Created**: 2025-12-16
**Changes**: Corrections to send type → caption type mappings

**Run Command**:
```bash
sqlite3 database/eros_sd_main.db < database/migrations/wave6_fix_caption_requirements.sql
```

---

## Execution Order

For a fresh database or complete rebuild, run migrations in this order:

```bash
# Core schema
sqlite3 database/eros_sd_main.db < database/migrations/002_volume_assignments.sql
sqlite3 database/eros_sd_main.db < database/migrations/003_volume_performance.sql
sqlite3 database/eros_sd_main.db < database/migrations/005_enhanced_personas.sql
sqlite3 database/eros_sd_main.db < database/migrations/006_caption_type_taxonomy_migration.sql
sqlite3 database/eros_sd_main.db < database/migrations/007_schedule_generator_enhancements.sql

# Send type system (Wave 3)
sqlite3 database/eros_sd_main.db < database/migrations/008_send_types_foundation.sql
sqlite3 database/eros_sd_main.db < database/migrations/008_send_types_seed_data.sql
sqlite3 database/eros_sd_main.db < database/migrations/008_mapping_tables.sql
sqlite3 database/eros_sd_main.db < database/migrations/008_schedule_items_enhancement.sql

# Wave 6 refinements
sqlite3 database/eros_sd_main.db < database/migrations/009_caption_bank_missing_columns.sql
sqlite3 database/eros_sd_main.db < database/migrations/010_wave6_update_confidence.sql
sqlite3 database/eros_sd_main.db < database/migrations/wave6_fix_caption_requirements.sql
```

### Single Command Execution

Run all migrations sequentially:

```bash
cd /Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT

for migration in \
  002_volume_assignments.sql \
  003_volume_performance.sql \
  005_enhanced_personas.sql \
  006_caption_type_taxonomy_migration.sql \
  007_schedule_generator_enhancements.sql \
  008_send_types_foundation.sql \
  008_send_types_seed_data.sql \
  008_mapping_tables.sql \
  008_schedule_items_enhancement.sql \
  009_caption_bank_missing_columns.sql \
  010_wave6_update_confidence.sql \
  wave6_fix_caption_requirements.sql
do
  echo "Running migration: $migration"
  sqlite3 database/eros_sd_main.db < database/migrations/$migration
  if [ $? -eq 0 ]; then
    echo "✓ $migration completed successfully"
  else
    echo "✗ $migration failed"
    exit 1
  fi
done

echo "All migrations completed successfully!"
```

---

## Rollback Procedures

### Available Rollbacks

Some migrations include rollback scripts:

- `007_rollback.sql` - Rollback schedule generator enhancements
- `008_rollback.sql` - Rollback send type system enhancements

### Rollback Execution

```bash
# Rollback migration 007
sqlite3 database/eros_sd_main.db < database/migrations/007_rollback.sql

# Rollback migration 008
sqlite3 database/eros_sd_main.db < database/migrations/008_rollback.sql
```

### Manual Rollback

For migrations without rollback scripts, manually drop added tables/columns:

```sql
-- Example: Manual rollback of table creation
DROP TABLE IF EXISTS table_name;

-- Note: SQLite does not support DROP COLUMN
-- To remove a column, you must recreate the table without it
```

---

## Backup Procedures

### Before Running Migrations

Always backup the database before applying migrations:

```bash
# Create timestamped backup
cp database/eros_sd_main.db database/backups/eros_sd_main_$(date +%Y%m%d_%H%M%S).db

# Verify backup
ls -lh database/backups/
```

### Restore from Backup

```bash
# Restore specific backup
cp database/backups/eros_sd_main_20251216_143000.db database/eros_sd_main.db

# Verify restoration
sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM creators;"
```

---

## Verification

### Check Applied Migrations

```sql
-- View migration history
SELECT version, applied_at, description
FROM schema_migrations
ORDER BY applied_at DESC;
```

### Verify Table Creation

```sql
-- List all tables
.tables

-- Check specific table schema
.schema send_types

-- Count records
SELECT COUNT(*) FROM send_types;  -- Should be 21
SELECT COUNT(*) FROM channels;    -- Should be 5
SELECT COUNT(*) FROM audience_targets;  -- Should be 10
```

### Validate Data Integrity

```bash
# Run PRAGMA checks
sqlite3 database/eros_sd_main.db << EOF
PRAGMA foreign_key_check;
PRAGMA integrity_check;
EOF
```

Expected output:
```
ok
```

---

## Troubleshooting

### Migration Already Applied

If a migration fails with "table already exists":
- This is expected behavior for idempotent migrations
- The migration uses `CREATE TABLE IF NOT EXISTS`
- No action needed

### Foreign Key Constraint Errors

```sql
-- Check foreign key constraints
PRAGMA foreign_keys = ON;
PRAGMA foreign_key_check;

-- Disable temporarily (not recommended for production)
PRAGMA foreign_keys = OFF;
```

### Rollback Issues

If rollback fails:
1. Check rollback script exists
2. Restore from backup
3. Manually review and drop affected objects

### Database Locked

If migration hangs with "database is locked":
1. Close all connections to database
2. Check for running MCP server: `ps aux | grep eros_db_server`
3. Kill processes if necessary
4. Retry migration

---

## Migration Development

### Creating New Migrations

Template for new migrations:

```sql
-- ============================================================================
-- Migration: XXX_migration_name.sql
-- Version: X.X.X
-- Created: YYYY-MM-DD
--
-- Purpose: Brief description of migration purpose
--
-- Tables Created/Modified:
--   - table_name: Description
--
-- Dependencies: List any prerequisite migrations
-- ============================================================================

-- Use IF NOT EXISTS for idempotency
CREATE TABLE IF NOT EXISTS new_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- columns...
);

-- Track migration
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('XXX', 'Migration description');
```

### Testing Migrations

1. **Test on backup database**:
   ```bash
   cp database/eros_sd_main.db database/test_eros_sd_main.db
   sqlite3 database/test_eros_sd_main.db < database/migrations/XXX_new_migration.sql
   ```

2. **Verify schema changes**:
   ```sql
   .schema new_table
   SELECT COUNT(*) FROM new_table;
   ```

3. **Test rollback** (if applicable):
   ```bash
   sqlite3 database/test_eros_sd_main.db < database/migrations/XXX_rollback.sql
   ```

---

## Related Documentation

- [Schedule Generator Blueprint](../docs/SCHEDULE_GENERATOR_BLUEPRINT.md) - System architecture
- [Enhanced Send Type Architecture](../docs/ENHANCED_SEND_TYPE_ARCHITECTURE.md) - Send type system design
- [Database Audit Report](../database/audit/) - Data quality assessment

---

*Version 2.3.0 | Last Updated: 2025-12-18*
