# EROS Pipeline Migration: v2.2.0 to v2.3.0

**Migration Date**: 2025-12-18
**Previous Version**: 2.2.0
**Target Version**: 2.3.0
**Status**: In Progress

## Executive Summary

This migration transitions the EROS Schedule Generator from a 9-agent/9-phase architecture to a 22-agent/14-phase architecture. The primary changes are:

1. **Removal**: `audience-targeter` agent (Phase 4) - targeting now done manually in OnlyFans
2. **Addition**: `authenticity-engine` agent - persona-driven caption adaptation
3. **Addition**: `revenue-optimizer` agent - revenue maximization strategies

## Current State Snapshot (v2.2.0)

### Architecture
- **Agents**: 22 specialized agents
- **Phases**: 14-phase pipeline
- **Database**: SQLite (297MB, 59 tables, 37 active creators)
- **Send Types**: 22-type taxonomy

### Agent Roster (v2.2.0)
| Phase | Agent | Purpose |
|-------|-------|---------|
| 1 | performance-analyst | Saturation/opportunity analysis |
| 2 | send-type-allocator | Daily send type distribution |
| 3 | caption-selection-pro | Caption selection with freshness scoring |
| 4 | audience-targeter | Audience segment assignment |
| 5 | timing-optimizer | Optimal posting time calculation |
| 6 | followup-generator | Auto-generate PPV followups |
| 7 | schedule-assembler | Final schedule assembly |
| - | quality-validator | Requirements validation (cross-cutting) |

### Database Tables Affected
- `audience_targets` - To be dropped
- `schedule_items.target_id` - Column to be removed
- `v_schedule_items_full` - View to be recreated without audience joins

## Target State (v2.3.0)

### Architecture
- **Agents**: 22 specialized agents
- **Phases**: 14-phase pipeline
- **Database**: SQLite (reduced after audience_targets removal)
- **Send Types**: 22-type taxonomy (unchanged)

### Agent Roster (v2.3.0)
| Phase | Agent | Purpose |
|-------|-------|---------|
| 1 | performance-analyst | Saturation/opportunity analysis |
| 2 | send-type-allocator | Daily send type distribution |
| 3 | caption-selection-pro | Caption selection with freshness scoring |
| 4 | authenticity-engine | Persona-driven caption adaptation |
| 5 | timing-optimizer | Optimal posting time calculation |
| 6 | followup-generator | Auto-generate PPV followups |
| 7 | revenue-optimizer | Revenue maximization strategies |
| 8 | schedule-assembler | Final schedule assembly |
| 9 | quality-validator | Requirements validation (final phase) |

### Changes Summary

#### Removed Components
- `audience-targeter` agent and documentation
- `audience_targets` database table
- `target_id` column from `schedule_items`
- `get_audience_targets` MCP tool
- Audience-related views and indexes

#### Added Components
- `authenticity-engine` agent (Phase 4)
- `revenue-optimizer` agent (Phase 7)
- New agent documentation files
- Updated orchestration flow

## Migration Steps

### Wave 1: Infrastructure Preparation (This Document)
1. [x] Create database backup
2. [x] Create migration documentation
3. [x] Create migration SQL script

### Wave 2: Database Migration
1. [ ] Execute `015_remove_audience_targeting.sql`
2. [ ] Verify table structure changes
3. [ ] Update indexes and views

### Wave 3: Agent Architecture Updates
1. [ ] Remove `audience-targeter` agent files
2. [ ] Create `authenticity-engine` agent
3. [ ] Create `revenue-optimizer` agent
4. [ ] Update orchestration documentation

### Wave 4: MCP Tool Updates
1. [ ] Remove `get_audience_targets` tool
2. [ ] Update `save_schedule` to not require target_id
3. [ ] Update tool documentation

### Wave 5: Testing & Validation
1. [ ] Run full pipeline test
2. [ ] Verify schedule generation
3. [ ] Performance baseline comparison

## Database Migration Details

### Migration Script
File: `database/migrations/015_remove_audience_targeting.sql`

**Actions**:
1. Recreate `schedule_items` table without `target_id` column
2. Drop `audience_targets` table and related indexes
3. Recreate `v_schedule_items_full` view without audience joins

### Affected Indexes
- `idx_audience_targets_active` - Dropped
- `idx_audience_targets_page_type` - Dropped
- `idx_schedule_items_target` - Removed (not recreated)

## Rollback Instructions

### Prerequisites
- Backup file: `database/backups/eros_sd_main_v2.2.0_backup.db`
- Original agent files preserved in git history

### Database Rollback
```bash
# Stop any running MCP server
pkill -f eros_db_server

# Restore database from backup
cp database/backups/eros_sd_main_v2.2.0_backup.db database/eros_sd_main.db

# Verify restoration
sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM audience_targets;"
```

### Code Rollback
```bash
# Revert to v2.2.0 tag (if created)
git checkout v2.2.0

# Or revert specific commits
git revert --no-commit HEAD~N..HEAD
git commit -m "Rollback to v2.2.0"
```

### Verification After Rollback
1. Verify `audience_targets` table exists
2. Verify `schedule_items.target_id` column exists
3. Verify `v_schedule_items_full` includes audience data
4. Run test schedule generation

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data loss during migration | Low | High | Full backup created |
| Agent dependency issues | Medium | Medium | Phased rollout |
| MCP tool compatibility | Medium | Medium | Version pinning |
| Performance regression | Low | Medium | Baseline comparison |

## Validation Checklist

### Pre-Migration
- [x] Database backup created and verified
- [x] Migration documentation complete
- [x] Migration script created and reviewed
- [ ] Git commit for v2.2.0 state

### Post-Migration
- [ ] Database schema updated
- [ ] All MCP tools functional
- [ ] Schedule generation works
- [ ] No orphaned references
- [ ] Performance acceptable

## Contact

For issues during migration, check:
1. `database/logs/` for migration logs
2. Git history for code changes
3. Backup restoration instructions above

---

**Document Version**: 1.0
**Last Updated**: 2025-12-18
**Author**: EROS DevOps Pipeline
