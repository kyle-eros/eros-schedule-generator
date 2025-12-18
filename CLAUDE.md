# EROS Schedule Generator

## Project Overview

AI-powered multi-agent schedule generation system for OnlyFans creators using a 22-type send taxonomy. The system orchestrates 9 specialized agents across 9 phases to produce optimized weekly schedules that balance revenue generation, audience engagement, and subscriber retention.

**Version**: 2.3.0
**Database**: SQLite (250MB, 59 tables, 37 active creators)
**Architecture**: Multi-agent pipeline with MCP database integration

## Quick Start

```
# Generate schedule for a creator
"Generate a schedule for alexia"

# Generate with specific focus
"Generate a revenue-focused schedule for creator_123 starting 2025-12-16"

# Analyze performance before scheduling
"Analyze performance trends for alexia"
```

## Key Files

| Location | Purpose |
|----------|---------|
| `.claude/skills/eros-schedule-generator/SKILL.md` | Main skill entry point |
| `.claude/skills/eros-schedule-generator/ORCHESTRATION.md` | 9-phase pipeline documentation |
| `.claude/agents/` | 9 specialized agent definitions |
| `mcp/eros_db_server.py` | MCP database server (16 tools) |
| `python/` | Core Python algorithms |
| `database/eros_sd_main.db` | Production SQLite database |
| `docs/` | Comprehensive documentation (240KB+) |

## 9 Specialized Agents

1. **performance-analyst** - Saturation/opportunity analysis
2. **send-type-allocator** - Daily send type distribution
3. **content-curator** - Caption selection with freshness scoring
4. **timing-optimizer** - Optimal posting time calculation
5. **followup-generator** - Auto-generate PPV followups
6. **authenticity-engine** - Anti-AI humanization [NEW]
7. **schedule-assembler** - Final schedule assembly
8. **revenue-optimizer** - Price/positioning optimization [NEW]
9. **quality-validator** - Final validation gate

## MCP Tools Available

All database operations use the `eros-db` MCP server (16 tools):

### Creator Data (3 tools)
- **`get_creator_profile`** - Comprehensive creator data including analytics, persona, top content types, and volume configuration
- **`get_active_creators`** - List all active creators with performance metrics and tier classification
- **`get_persona_profile`** - Creator tone, archetype, emoji style, slang level, and voice samples

### Performance & Analytics (3 tools)
- **`get_performance_trends`** - Saturation/opportunity scores with multi-horizon analysis (7d/14d/30d)
- **`get_content_type_rankings`** - TOP/MID/LOW/AVOID classifications based on performance tiers
- **`get_best_timing`** - Optimal posting times by hour and day from historical performance

### Content & Captions (3 tools)
- **`get_top_captions`** - Performance-ranked captions with freshness scoring and send type compatibility
- **`get_send_type_captions`** - Captions compatible with specific send types via caption type mappings
- **`get_vault_availability`** - Available content types in creator's vault inventory

### Send Type Configuration (3 tools)
- **`get_send_types`** - Full 22-type taxonomy filtered by category and page type
- **`get_send_type_details`** - Complete configuration for single send type including timing rules and constraints
- **`get_volume_config`** - **[CRITICAL]** Optimized volume configuration with full `OptimizedVolumeResult`:
  - Legacy fields: `volume_level`, `ppv_per_day`, `bump_per_day` (backward compatible)
  - Category volumes: `revenue_per_day`, `engagement_per_day`, `retention_per_day`
  - Weekly distribution: `weekly_distribution` (DOW-adjusted, day 0-6 mapping)
  - Content strategy: `content_allocations` (performance-weighted by content type)
  - Optimization metadata: `confidence_score`, `elasticity_capped`, `caption_warnings`
  - Multi-horizon fusion: `fused_saturation`, `fused_opportunity`, `divergence_detected`
  - DOW multipliers: `dow_multipliers_used` (per-day adjustment factors)
  - Tracking: `prediction_id`, `message_count`, `adjustments_applied` (audit trail)
  - 8 integrated modules: Base Tier, Multi-Horizon Fusion, Confidence Dampening, DOW Distribution, Elasticity Bounds, Content Weighting, Caption Pool Check, Prediction Tracking

### Channels (1 tool)
- **`get_channels`** - Distribution channels (wall_post, mass_message, story, live)

### Schedule Operations (2 tools)
- **`save_schedule`** - Persist generated schedule to database with send types and channels
- **`execute_query`** - Execute read-only SQL queries for custom analysis and diagnostics

### Tool Count Verification
- Creator Data: 3 tools
- Performance & Analytics: 3 tools
- Content & Captions: 3 tools
- Send Type Configuration: 3 tools
- Channels: 1 tool
- Schedule Operations: 2 tools
- Deprecated (still functional): 1 tool (`get_volume_assignment`)
**Total: 16 tools**

**Deprecation Notice**: `get_volume_assignment` remains available for backward compatibility but returns a deprecation warning. New implementations should use `get_volume_config()` which provides dynamic calculation with full `OptimizedVolumeResult` metadata instead of static assignments.

## 22 Send Types (v2.1)

### Revenue (9 types)
`ppv_unlock`, `ppv_wall`, `tip_goal`, `bundle`, `flash_bundle`, `game_post`, `first_to_tip`, `vip_program`, `snapchat_bundle`

### Engagement (9 types)
`link_drop`, `wall_link_drop`, `bump_normal`, `bump_descriptive`, `bump_text_only`, `bump_flyer`, `dm_farm`, `like_farm`, `live_promo`

### Retention (4 types)
`renew_on_post`, `renew_on_message`, `ppv_followup`, `expired_winback`

**Note**: `ppv_message` has been deprecated and merged into `ppv_unlock`. Transition period ends 2025-01-16.

## Critical Constraints

- **Retention types**: Only for `paid` page types
- **PPV unlocks** (`ppv_unlock`): Max 4 per day - primary revenue sends
- **PPV followups** (`ppv_followup`): Max 5 per day - auto-generated 20-60 min after parent PPV
  - Note: PPV followups are separate from PPV unlocks (different send types)
  - Example: 4 ppv_unlock sends → up to 4 ppv_followup sends (within daily limit of 5)
- **VIP program**: Max 1 per week
- **Snapchat bundle**: Max 1 per week
- **Caption freshness**: Minimum 30-day threshold for reuse

## Caption Selection Algorithm (v2.1)

The caption selection system uses a universal pool with vault-based filtering:

### Universal Caption Access
- All **59,405 captions** are accessible to any creator
- `caption_bank.creator_id` is ignored in selection queries
- Historical creator assignments preserved for analytics only

### Vault Matrix Filtering (HARD FILTER)
- Only captions matching creator's `vault_matrix` content types are returned
- Content type validation happens at the database level via INNER JOIN
- Creators must have vault_matrix entries to receive captions

### Scoring Weights
| Component | Weight | Purpose |
|-----------|--------|---------|
| Freshness | 40% | Prioritize unused captions |
| Performance | 35% | Prefer high-earning captions |
| Type Priority | 15% | Send type compatibility |
| Diversity | 5% | Prevent repetition |
| Persona | 5% | Minor tone alignment |

### Freshness Calculation
```
freshness_score = 100 - (days_since_last_use * 2)
```
- Never used: 100 (maximum freshness)
- Used 30 days ago: 40
- Minimum: 0

### Caption Pool Hierarchy
1. **Primary**: MCP tool returns vault-filtered, freshness-sorted captions
2. **Fallback**: Expand to lower performance thresholds if needed
3. **Manual**: Flag for manual selection if all fallbacks exhausted

## Vault Matrix Management

### Overview

The `vault_matrix` table controls which content types each creator can use. It acts as a hard filter during caption selection to ensure only appropriate content is scheduled.

**Architecture**: Hybrid UX approach
- **User Interface**: Google Sheets (wide format - easy to visualize and bulk edit)
- **Database Storage**: Normalized table (optimized for MCP queries)
- **Bridge**: Python import/export script (`database/scripts/vault_matrix_sync.py`)

### Creator Vault Notes

Each creator has a `vault_notes` field for vault-specific restrictions and preferences:

**Examples**:
- `"Prohibited: Face closeups due to privacy preference"`
- `"Prefers: Solo content on Mondays, B/G content Wed-Fri"`
- `"Use flirty tone, avoid explicit language in teasers"`
- `"New content: POV videos coming Feb 1st - update vault matrix"`

**Access**: Available in `get_creator_profile()` response

### Import/Export Workflow

**Export vault matrix to CSV**:
```bash
cd database/scripts
python3 vault_matrix_sync.py export --output vault_matrix.csv
```

**Edit in Google Sheets**:
- Upload CSV to Google Sheets
- Modify permissions: `1` (allowed), `0` (not allowed)
- Update `vault_notes` column with creator-specific notes
- Download as CSV when done

**Import back to database**:
```bash
# Dry-run first (preview changes)
python3 vault_matrix_sync.py import-csv --input vault_matrix_edited.csv --dry-run

# Apply changes
python3 vault_matrix_sync.py import-csv --input vault_matrix_edited.csv
```

**Documentation**: See `database/docs/VAULT_MATRIX_WORKFLOW.md` for complete guide

## Coding Standards

- Use `send_type_key` consistently (never raw `send_type_id` in logic)
- Always validate `page_type` before including retention sends
- Parameterized queries for all database operations
- Type hints required for all Python functions
- Docstrings in Google style format

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `EROS_DB_PATH` | Database file location | `./database/eros_sd_main.db` |

## Related Documentation

- `docs/SCHEDULE_GENERATOR_BLUEPRINT.md` - Full architecture
- `docs/USER_GUIDE.md` - End-user documentation
- `docs/SEND_TYPE_REFERENCE.md` - Complete send type details
- `database/docs/VAULT_MATRIX_WORKFLOW.md` - Vault matrix import/export guide
- `database/audit/` - Database quality reports (93/100 score)
