# EROS Ultimate Schedule Generator
## Perfected Master Enhancement Plan

**Created:** 2025-12-15
**Status:** READY FOR EXECUTION
**Execution Model:** Wave-Based Multi-Agent Orchestration

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Assessment](#2-current-state-assessment)
3. [Target State Vision](#3-target-state-vision)
4. [Gap Analysis](#4-gap-analysis)
5. [Wave Execution Framework](#5-wave-execution-framework)
6. [Wave 1: Database Foundation](#wave-1-database-foundation)
7. [Wave 2: MCP Server Enhancement](#wave-2-mcp-server-enhancement)
8. [Wave 3: Skill & Agent Architecture](#wave-3-skill--agent-architecture)
9. [Wave 4: Pipeline Intelligence](#wave-4-pipeline-intelligence)
10. [Wave 5: Integration & Perfection](#wave-5-integration--perfection)
11. [File Inventory](#6-complete-file-inventory)
12. [Success Criteria](#7-success-criteria)
13. [Risk Mitigation](#8-risk-mitigation)

---

## 1. Executive Summary

### Mission Statement

Transform the EROS Schedule Generator from a **simplified 2-type system** (`ppv`/`bump`) into a **comprehensive 21-type professional scheduling platform** that accurately models all OnlyFans content operations, featuring intelligent caption matching, audience targeting, automatic follow-up generation, and adaptive volume optimization.

### Key Deliverables

| Deliverable | Current | Target |
|-------------|---------|--------|
| Send Types | 2 | **21** |
| Channels | 2 | **5** |
| Audience Targets | 0 | **10** |
| Caption Matching | Generic | **Type-Specific** |
| Follow-up Generation | None | **Automatic** |
| Page Type Rules | Ignored | **Enforced** |
| Expiration Handling | None | **Automatic** |

### Execution Timeline

```
WAVE 1 ────► WAVE 2 ────► WAVE 3 ────► WAVE 4 ────► WAVE 5
Database    MCP Server   Skill &      Pipeline     Integration
Foundation  Enhancement  Agents       Intelligence & Perfection
   │            │            │            │            │
   ▼            ▼            ▼            ▼            ▼
sql-pro     python-pro   command-     llm-         code-reviewer
database-   code-        architect    architect    debugger
optimizer   reviewer                  prompt-      quality-
                                      engineer     validator
```

---

## 2. Current State Assessment

### Existing Infrastructure

```
EROS-SD-MAIN-PROJECT/
├── database/
│   └── eros_sd_main.db          # 53 tables, 70K+ messages
├── mcp/
│   └── eros_db_server.py        # 11 MCP tools (basic)
├── docs/
│   └── SCHEDULE_GENERATOR_BLUEPRINT.md
└── combined_content_library.json # 21 send types defined
```

### Current Schedule Items Schema

```sql
-- CURRENT: Only supports 2 item types
schedule_items (
    item_type TEXT,              -- Only 'ppv' or 'bump'
    channel TEXT,                -- Only 'mass_message' or 'wall_post'
    -- Missing: send_type_id, target_id, expires_at, parent_send_id, etc.
)
```

### Current MCP Tools

| Tool | Status | Gap |
|------|--------|-----|
| `get_active_creators` | Working | None |
| `get_creator_profile` | Working | None |
| `get_top_captions` | Working | No send type filtering |
| `get_best_timing` | Working | No send type timing |
| `get_performance_trends` | Working | None |
| `get_content_type_rankings` | Working | None |
| `get_persona_profile` | Working | None |
| `get_vault_availability` | Working | None |
| `save_schedule` | Working | Missing new fields |
| `execute_query` | Working | None |
| **get_send_types** | **MISSING** | **NEW REQUIRED** |
| **get_send_type_captions** | **MISSING** | **NEW REQUIRED** |
| **get_audience_targets** | **MISSING** | **NEW REQUIRED** |
| **get_channels** | **MISSING** | **NEW REQUIRED** |

---

## 3. Target State Vision

### Complete Send Type Taxonomy

```
SEND_TYPES (21 Total)
│
├── REVENUE (7 types)
│   ├── ppv_video          # Standard PPV video sale
│   ├── vip_program        # VIP tier promotion ($200 tip)
│   ├── game_post          # Spin-the-wheel, contests
│   ├── bundle             # Content bundle at set price
│   ├── flash_bundle       # Limited-quantity urgency bundle
│   ├── snapchat_bundle    # Throwback Snapchat content
│   └── first_to_tip       # Gamified tip race
│
├── ENGAGEMENT (9 types)
│   ├── link_drop          # Repost previous campaign link
│   ├── wall_link_drop     # Wall post campaign promotion
│   ├── bump_normal        # Short flirty bump with media
│   ├── bump_descriptive   # Story-driven bump (longer)
│   ├── bump_text_only     # No media, just text
│   ├── bump_flyer         # Designed flyer/GIF bump
│   ├── dm_farm            # "DM me" engagement driver
│   ├── like_farm          # "Like all posts" engagement
│   └── live_promo         # Livestream announcement
│
└── RETENTION (5 types)
    ├── renew_on_post      # Auto-renew promotion (wall)
    ├── renew_on_message   # Auto-renew targeted message
    ├── ppv_message        # Mass message PPV unlock
    ├── ppv_followup       # PPV close-the-sale followup
    └── expired_winback    # Former subscriber outreach
```

### Enhanced Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ENHANCED SCHEDULE GENERATOR v2.0                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│  SEND TYPE    │          │   CONTENT     │          │   AUDIENCE    │
│  ALLOCATOR    │          │   MATCHER     │          │   TARGETER    │
│               │          │               │          │               │
│ • Category    │          │ • Type-aware  │          │ • Segment     │
│   distribution│          │   caption     │          │   selection   │
│ • Page type   │          │   matching    │          │ • Filter      │
│   rules       │          │ • Vault cross-│          │   criteria    │
│ • Volume      │          │   reference   │          │ • Reach       │
│   constraints │          │ • Freshness   │          │   estimation  │
└───────┬───────┘          └───────┬───────┘          └───────┬───────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   ▼
                    ┌─────────────────────────┐
                    │    TIMING OPTIMIZER     │
                    │                         │
                    │ • Send type timing rules│
                    │ • Follow-up scheduling  │
                    │ • Expiration handling   │
                    │ • Conflict avoidance    │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FOLLOW-UP GENERATOR   │
                    │                         │
                    │ • Auto-generate PPV     │
                    │   follow-ups            │
                    │ • Link parent items     │
                    │ • Target non-purchasers │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   QUALITY VALIDATOR     │
                    │                         │
                    │ • Requirements check    │
                    │ • Authenticity verify   │
                    │ • Completeness audit    │
                    │ • Final approval        │
                    └─────────────────────────┘
```

---

## 4. Gap Analysis

### Send Type Coverage Gap

| Category | Library Types | Currently Supported | Gap |
|----------|---------------|---------------------|-----|
| Revenue & Sales | 7 | 1 (ppv only) | **6 missing** |
| Engagement (Bumps) | 9 | 1 (generic bump) | **8 missing** |
| Retention (Backend) | 5 | 1 (partial ppv) | **4 missing** |
| **TOTAL** | **21** | **~3** | **~18 missing** |

### Feature Gap Matrix

| Feature | Current | Required | Priority |
|---------|---------|----------|----------|
| Send type taxonomy | None | Full 21-type system | **P0** |
| Channel selection | Hardcoded | Dynamic 5-channel | **P0** |
| Audience targeting | None | 10 segment targets | **P0** |
| Caption-to-type matching | None | Type-specific queries | **P0** |
| Follow-up generation | Manual | Automatic | **P1** |
| Expiration handling | None | Automatic | **P1** |
| Page type enforcement | None | Strict | **P1** |
| Media requirements | Implicit | Explicit flags | **P2** |
| Flyer requirements | Implicit | Explicit flags | **P2** |

---

## 5. Wave Execution Framework

### Execution Protocol

```
┌─────────────────────────────────────────────────────────────────────┐
│                     WAVE EXECUTION PROTOCOL                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. ANNOUNCE WAVE                                                    │
│     └─► State wave number, objectives, assigned agents               │
│                                                                      │
│  2. SPAWN PRIMARY AGENTS (Parallel)                                  │
│     └─► Use Task tool with specified subagent_type                   │
│     └─► Provide complete context in prompt                           │
│     └─► Set appropriate model (opus/sonnet/haiku)                    │
│                                                                      │
│  3. VERIFICATION GATE                                                │
│     └─► Spawn verification agent                                     │
│     └─► Run quality checks                                           │
│     └─► Document any issues                                          │
│                                                                      │
│  4. QUALITY GATE                                                     │
│     └─► Execute test commands                                        │
│     └─► Verify all checklist items                                   │
│     └─► MUST PASS before next wave                                   │
│                                                                      │
│  5. TRANSITION                                                       │
│     └─► Mark wave complete                                           │
│     └─► Update progress tracking                                     │
│     └─► Begin next wave                                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent-to-Wave Mapping

| Wave | Primary Agent(s) | Verification Agent | Model |
|------|------------------|-------------------|-------|
| 1 | `sql-pro`, `database-optimizer` | `code-reviewer` | Sonnet |
| 2 | `python-pro` | `code-reviewer` | Sonnet |
| 3 | `command-architect` | `code-reviewer` | Sonnet |
| 4 | `llm-architect`, `prompt-engineer` | `code-reviewer` | Opus |
| 5 | `code-reviewer`, `debugger` | `quality-validator` | Opus |

---

## WAVE 1: Database Foundation

### Objective
Create the complete database schema for send types, channels, audience targets, and all supporting tables with proper indexes, constraints, and seed data.

### Assigned Agents

| Role | Agent | Model | Tools |
|------|-------|-------|-------|
| **Primary** | `sql-pro` | Sonnet | All |
| **Optimization** | `database-optimizer` | Sonnet | All |
| **Verification** | `code-reviewer` | Sonnet | All |

### Files to Create/Edit

```
database/migrations/
├── 008_send_types_foundation.sql       # NEW - Core tables
├── 008_send_types_seed_data.sql        # NEW - All 21 types + channels + targets
├── 008_schedule_items_enhancement.sql  # NEW - Add columns to schedule_items
├── 008_mapping_tables.sql              # NEW - Caption/content compatibility
└── 008_rollback.sql                    # NEW - Safe rollback script
```

### Task 1.1: Core Tables Creation

**Agent:** `sql-pro`

**Prompt:**
```
Create the database migration file `008_send_types_foundation.sql` with the following tables:

1. `send_types` table:
   - send_type_id (PK)
   - send_type_key (UNIQUE, e.g., 'ppv_video', 'bump_normal')
   - category (CHECK: 'revenue', 'engagement', 'retention')
   - display_name, description, purpose, strategy
   - Requirements: requires_media, requires_flyer, requires_price, requires_link
   - Behavior: has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes
   - page_type_restriction (CHECK: 'paid', 'free', 'both')
   - Caption guidance: caption_length, emoji_recommendation
   - Constraints: max_per_day, max_per_week, min_hours_between
   - Metadata: sort_order, is_active, created_at

2. `channels` table:
   - channel_id (PK)
   - channel_key (UNIQUE, e.g., 'mass_message', 'wall_post', 'targeted_message')
   - display_name, description
   - supports_targeting, targeting_options (JSON)
   - platform_feature, requires_manual_send
   - is_active, created_at

3. `audience_targets` table:
   - target_id (PK)
   - target_key (UNIQUE, e.g., 'all_active', 'renew_off', 'expired_recent')
   - display_name, description
   - filter_type, filter_criteria (JSON)
   - applicable_page_types, applicable_channels (JSON)
   - typical_reach_percentage
   - is_active, created_at

Include proper indexes for all foreign key columns and frequently queried fields.
Follow SQLite best practices for CHECK constraints and generated columns.
```

### Task 1.2: Seed Data Population

**Agent:** `sql-pro`

**Prompt:**
```
Create `008_send_types_seed_data.sql` with INSERT statements for:

SEND TYPES (21 total):
Reference the combined_content_library.json for accurate purpose/strategy text.

REVENUE (7):
- ppv_video: Long caption, heavy emoji, requires media+flyer+price, can have followup
- vip_program: Medium caption, one-time post, campaign goal instead of price
- game_post: GIF required, has 24h expiration, campaign price
- bundle: Medium caption, deal-focused, requires flyer
- flash_bundle: Urgency messaging, 24h expiration, limited quantity
- snapchat_bundle: Throwback theme, high conversion, Snapchat-style flyer
- first_to_tip: 24h expiration, tip goal, gamified

ENGAGEMENT (9):
- link_drop: Short caption, no media (auto-preview), 24h expiration
- wall_link_drop: Requires manual GIF/picture, promotes wall campaigns
- bump_normal: Short flirty, media required, no flyer
- bump_descriptive: Long storytelling caption, media required
- bump_text_only: No media at all, short text only
- bump_flyer: Long caption + designed flyer/GIF
- dm_farm: "DM me" style, emoji heavy, engagement driver
- like_farm: Like incentive, engagement metrics boost
- live_promo: Livestream flyer required, event announcement

RETENTION (5):
- renew_on_post: Paid pages only, auto-renew link, wall post
- renew_on_message: Paid pages only, targets renew_off segment
- ppv_message: Mass message version of PPV, adjustable pricing
- ppv_followup: 15-30 min after PPV, close-the-sale, targets non-purchasers
- expired_winback: Paid pages only, daily, matches current campaign

CHANNELS (5):
- wall_post, mass_message, targeted_message, story, live

AUDIENCE TARGETS (10):
- all_active, renew_off, renew_on, expired_recent, expired_all
- never_purchased, recent_purchasers, high_spenders, inactive_7d, ppv_non_purchasers
```

### Task 1.3: Schedule Items Enhancement

**Agent:** `sql-pro`

**Prompt:**
```
Create `008_schedule_items_enhancement.sql` to add columns to schedule_items:

New columns:
- send_type_id INTEGER REFERENCES send_types(send_type_id)
- channel_id INTEGER REFERENCES channels(channel_id)
- target_id INTEGER REFERENCES audience_targets(target_id)
- linked_post_url TEXT (for link_drop types)
- expires_at TEXT (ISO datetime for expiring items)
- parent_send_id INTEGER REFERENCES schedule_items(item_id) (for followups)
- is_followup INTEGER DEFAULT 0
- followup_delay_minutes INTEGER
- media_type TEXT CHECK (media_type IN ('none', 'picture', 'gif', 'video', 'flyer'))
- campaign_goal REAL (for tip-based campaigns)

Create indexes:
- idx_schedule_items_send_type
- idx_schedule_items_channel
- idx_schedule_items_target
- idx_schedule_items_parent_send

Create view: v_schedule_items_full (joins all related tables for easy querying)
```

### Task 1.4: Mapping Tables

**Agent:** `sql-pro`

**Prompt:**
```
Create `008_mapping_tables.sql` with:

1. send_type_caption_requirements:
   - Maps which caption_types work best for each send_type
   - Columns: send_type_id, caption_type, priority (1=primary, 5=secondary), notes
   - Populate with mappings for all 21 send types

2. send_type_content_compatibility:
   - Maps which content_types are compatible with each send_type
   - Columns: send_type_id, content_type_id, compatibility (required/recommended/allowed/discouraged/forbidden)
   - Most send types allow all content types
   - Some have restrictions (e.g., snapchat_bundle prefers throwback content)
```

### Task 1.5: Optimization & Indexes

**Agent:** `database-optimizer`

**Prompt:**
```
Review all Wave 1 migration files and optimize:

1. Index Strategy:
   - Ensure all foreign keys have indexes
   - Add composite indexes for common query patterns
   - Consider partial indexes where appropriate

2. Query Performance:
   - Create optimized views for common join patterns
   - Ensure v_schedule_items_full is performant

3. Constraint Validation:
   - Verify all CHECK constraints are correct
   - Ensure referential integrity is maintained
   - Add triggers if needed for complex validation

4. Storage Efficiency:
   - Review column types for appropriate sizing
   - Consider STRICT tables where applicable (SQLite 3.37+)
```

### Quality Gate 1

**Verification Agent:** `code-reviewer`

**Checklist:**
- [ ] All 4 migration files created and syntactically valid
- [ ] All 21 send types inserted with complete data
- [ ] All 5 channels inserted
- [ ] All 10 audience targets inserted
- [ ] Foreign key relationships correct
- [ ] Indexes created for all FK columns
- [ ] CHECK constraints properly defined
- [ ] Rollback script tested

**Test Commands:**
```bash
# Backup database first
cp database/eros_sd_main.db database/eros_sd_main.db.backup

# Apply migrations
sqlite3 database/eros_sd_main.db < database/migrations/008_send_types_foundation.sql
sqlite3 database/eros_sd_main.db < database/migrations/008_send_types_seed_data.sql
sqlite3 database/eros_sd_main.db < database/migrations/008_schedule_items_enhancement.sql
sqlite3 database/eros_sd_main.db < database/migrations/008_mapping_tables.sql

# Verify
sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM send_types"  # Should be 21
sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM channels"    # Should be 5
sqlite3 database/eros_sd_main.db "SELECT COUNT(*) FROM audience_targets"  # Should be 10
sqlite3 database/eros_sd_main.db "PRAGMA foreign_key_check"  # Should be empty
```

---

## WAVE 2: MCP Server Enhancement

### Objective
Extend the MCP database server with new tools for send types, channels, audience targets, and enhanced caption matching with full type safety and comprehensive error handling.

### Assigned Agents

| Role | Agent | Model | Tools |
|------|-------|-------|-------|
| **Primary** | `python-pro` | Sonnet | All |
| **Verification** | `code-reviewer` | Sonnet | All |

### Files to Edit

```
mcp/
├── eros_db_server.py    # EDIT - Add 6 new tools, enhance 2 existing
└── test_server.py       # EDIT - Add tests for new tools
```

### Task 2.1: New MCP Tools

**Agent:** `python-pro`

**Prompt:**
```
Edit mcp/eros_db_server.py to add these new tools:

1. get_send_types(category: str = None, page_type: str = None) -> dict
   - Returns all send types, optionally filtered
   - Include all columns from send_types table
   - Sort by sort_order

2. get_send_type_details(send_type_key: str) -> dict
   - Returns complete details for a single send type
   - Include related caption_type requirements
   - Include content_type compatibility

3. get_send_type_captions(
       creator_id: str,
       send_type_key: str,
       min_freshness: float = 30,
       min_performance: float = 40,
       limit: int = 10
   ) -> dict
   - Join caption_bank with send_type_caption_requirements
   - Filter by creator and send type compatibility
   - Order by priority ASC, performance_score DESC
   - Return captions appropriate for the specific send type

4. get_channels(supports_targeting: bool = None) -> dict
   - Returns all channels
   - Optionally filter by targeting support

5. get_audience_targets(
       page_type: str = None,
       channel_key: str = None
   ) -> dict
   - Returns audience targets applicable to page type and channel
   - Filter by applicable_page_types and applicable_channels

6. get_volume_config(creator_id: str) -> dict
   - Returns volume configuration including new category breakdowns
   - Include: revenue_items_per_day, engagement_items_per_day, retention_items_per_day
   - Include type-specific limits: ppv_per_day, bundle_per_week, bump_per_day, etc.

Follow these patterns:
- Use type hints for all parameters
- Include docstrings with parameter descriptions
- Handle creator lookup by both creator_id and page_name
- Return structured dicts with clear keys
- Include error handling with descriptive messages
```

### Task 2.2: Enhanced Existing Tools

**Agent:** `python-pro`

**Prompt:**
```
Edit mcp/eros_db_server.py to enhance these existing tools:

1. get_top_captions - Add send_type_key parameter:
   - When provided, filter by send_type_caption_requirements
   - Join with send_types table to get type-appropriate captions
   - Maintain backward compatibility (parameter is optional)

2. save_schedule - Support new fields:
   - Accept send_type_key (resolve to send_type_id)
   - Accept channel_key (resolve to channel_id)
   - Accept target_key (resolve to target_id)
   - Accept linked_post_url for link_drop types
   - Accept expires_at for expiring types
   - Accept parent_item_id for followup types
   - Accept media_type, campaign_goal
   - Validate send_type requirements (e.g., if requires_flyer=1, warn if no flyer)
   - Auto-set is_followup=1 when parent_item_id is provided
   - Maintain backward compatibility with old item_type/channel format
```

### Task 2.3: Tool Registration

**Agent:** `python-pro`

**Prompt:**
```
Update the TOOLS list and handlers dict in eros_db_server.py:

1. Add tool definitions to TOOLS list:
   - Include complete inputSchema for each new tool
   - Document all parameters with descriptions
   - Mark required vs optional parameters

2. Update handlers dict:
   - Map all 6 new tool names to their functions
   - Ensure consistent error handling

3. Update tools/list response:
   - Should now return 17 tools total (11 existing + 6 new)
```

### Task 2.4: Test Suite Update

**Agent:** `python-pro`

**Prompt:**
```
Edit mcp/test_server.py to add comprehensive tests:

1. Test get_send_types:
   - Test unfiltered (should return 21)
   - Test filtered by category='revenue' (should return 7)
   - Test filtered by page_type='paid'

2. Test get_send_type_details:
   - Test valid send_type_key
   - Test invalid send_type_key (error handling)

3. Test get_send_type_captions:
   - Test with valid creator and send_type
   - Verify captions match type requirements

4. Test get_channels:
   - Test returns 5 channels
   - Test supports_targeting filter

5. Test get_audience_targets:
   - Test page_type filter
   - Test channel filter

6. Test enhanced save_schedule:
   - Test with new fields
   - Test backward compatibility with old format
```

### Quality Gate 2

**Verification Agent:** `code-reviewer`

**Checklist:**
- [ ] All 6 new tools implemented
- [ ] 2 existing tools enhanced
- [ ] TOOLS list updated with 17 tools
- [ ] handlers dict updated
- [ ] All type hints present
- [ ] All docstrings complete
- [ ] Error handling comprehensive
- [ ] Test suite passes
- [ ] No SQL injection vulnerabilities
- [ ] Backward compatibility maintained

**Test Commands:**
```bash
# Run test suite
python3 mcp/test_server.py

# Manual verification
python3 -c "
import json
import sys
sys.path.insert(0, 'mcp')
from eros_db_server import get_send_types, get_channels, get_audience_targets

# Test new tools
result = get_send_types()
print(f'Send types: {len(result.get(\"send_types\", []))}')  # Should be 21

result = get_channels()
print(f'Channels: {len(result.get(\"channels\", []))}')  # Should be 5

result = get_audience_targets()
print(f'Targets: {len(result.get(\"targets\", []))}')  # Should be 10
"
```

---

## WAVE 3: Skill & Agent Architecture

### Objective
Update the EROS Schedule Generator skill and all specialized subagents to use the new send type system, following 2025 Claude Code best practices for skills and agent definitions.

### Assigned Agents

| Role | Agent | Model | Tools |
|------|-------|-------|-------|
| **Primary** | `command-architect` | Sonnet | All |
| **Verification** | `code-reviewer` | Sonnet | All |

### Files to Create/Edit

```
.claude/skills/eros-schedule-generator/
├── SKILL.md                    # EDIT - Update for 21 send types
├── SEND_TYPES.md               # NEW - Send type reference
├── ALLOCATION_RULES.md         # NEW - Category distribution rules
├── TARGETING_GUIDE.md          # NEW - Audience targeting guide
└── FOLLOWUP_PATTERNS.md        # NEW - Follow-up generation patterns

.claude/agents/
├── send-type-allocator.md      # NEW - Allocates types to slots
├── content-curator.md          # EDIT - Type-aware caption matching
├── audience-targeter.md        # NEW - Target selection agent
├── followup-generator.md       # NEW - Auto-generates followups
├── timing-optimizer.md         # EDIT - Type-specific timing
├── schedule-assembler.md       # EDIT - Handle new fields
└── quality-validator.md        # EDIT - Validate new requirements
```

### Task 3.1: Enhanced Skill Definition

**Agent:** `command-architect`

**Prompt:**
```
Edit .claude/skills/eros-schedule-generator/SKILL.md:

Update the skill to orchestrate the enhanced 21-type system:

1. Update description to mention all send type categories
2. Update invocation patterns to include type-specific requests
3. Update Multi-Agent Workflow section:
   - Add Send Type Allocator agent (new)
   - Add Audience Targeter agent (new)
   - Add Follow-up Generator agent (new)
   - Update existing agent descriptions

4. Update Parameters section:
   - Add send_types filter parameter
   - Add include_retention parameter (for paid pages)
   - Add include_followups parameter

5. Update Execution Flow:
   Phase 1: Context + Send Type Loading
   Phase 2: Send Type Allocation
   Phase 3: Content Matching (type-aware)
   Phase 4: Audience Targeting
   Phase 5: Timing + Follow-up Generation
   Phase 6: Assembly
   Phase 7: Validation

6. Update Output Format to include:
   - send_type with key, category, display_name
   - channel with key and display_name
   - target with key and display_name
   - followups array
   - expires_at where applicable

Follow 2025 Claude Code skill best practices:
- Clear frontmatter with name and description
- Comprehensive parameter documentation
- Detailed execution flow
- Example invocations
```

### Task 3.2: Supporting Skill Documentation

**Agent:** `command-architect`

**Prompt:**
```
Create these new skill documentation files:

1. SEND_TYPES.md:
   - Complete reference for all 21 send types
   - Organized by category (Revenue, Engagement, Retention)
   - Include for each: key, purpose, strategy, requirements, constraints
   - Include caption type mappings
   - Include content type compatibility

2. ALLOCATION_RULES.md:
   - Distribution formulas by volume tier
   - Category balance rules (revenue:engagement:retention ratios)
   - Page type restrictions
   - Daily/weekly caps
   - Example allocations for Low/Mid/High/Ultra tiers

3. TARGETING_GUIDE.md:
   - All 10 audience targets explained
   - Which send types use which targets
   - Channel compatibility
   - Reach estimation guidelines

4. FOLLOWUP_PATTERNS.md:
   - Which send types generate followups
   - Timing rules (15-30 min delays)
   - Follow-up caption type selection
   - Non-purchaser targeting logic
```

### Task 3.3: New Agent Definitions

**Agent:** `command-architect`

**Prompt:**
```
Create these new agent definition files in .claude/agents/:

1. send-type-allocator.md:
---
name: send-type-allocator
description: Allocate send types to schedule slots based on volume assignment, page type, and business rules. Use when building daily/weekly content distribution.
tools: mcp__eros-db__get_send_types, mcp__eros-db__get_volume_config, mcp__eros-db__get_creator_profile
model: sonnet
---

Mission: Determine which send types to schedule for each day
Algorithm:
  1. Load creator's volume config and page type
  2. Filter send types by page_type_restriction
  3. Allocate revenue items (prioritize ppv_video, add variety)
  4. Allocate engagement items (mix bump types)
  5. Allocate retention items (if paid page)
  6. Respect max_per_day and max_per_week limits
  7. Return allocation matrix by day

2. audience-targeter.md:
---
name: audience-targeter
description: Select appropriate audience targets for each scheduled item based on send type and channel. Use when assigning targeting to schedule items.
tools: mcp__eros-db__get_audience_targets, mcp__eros-db__get_send_type_details
model: haiku
---

Mission: Assign correct audience target to each item
Logic:
  - Revenue items → all_active (unless specific targeting needed)
  - renew_on_message → renew_off
  - expired_winback → expired_recent
  - ppv_followup → ppv_non_purchasers
  - Standard bumps → all_active

3. followup-generator.md:
---
name: followup-generator
description: Automatically generate follow-up items for PPV and bundle sends. Use after main schedule items are created.
tools: mcp__eros-db__get_send_type_details, mcp__eros-db__get_send_type_captions
model: haiku
---

Mission: Create follow-up items for sends that support them
Algorithm:
  1. Identify items where can_have_followup=1
  2. For each, create ppv_followup item
  3. Set parent_send_id to original item
  4. Calculate timing (+15-30 min)
  5. Select follow-up caption
  6. Target ppv_non_purchasers
```

### Task 3.4: Updated Agent Definitions

**Agent:** `command-architect`

**Prompt:**
```
Update these existing agent files in .claude/agents/:

1. content-curator.md:
   - Update to use get_send_type_captions tool
   - Match captions by send_type_key instead of generic type
   - Consider send type requirements (caption_length, emoji_recommendation)
   - Check media/flyer requirements

2. timing-optimizer.md:
   - Add send type timing rules
   - Revenue items: Prime hours (7pm, 9pm, 10am, 2pm)
   - Engagement: Distributed throughout day
   - Retention: Off-peak hours
   - Follow-ups: +15-30 min after parent
   - Link drops: +2-4 hours after original post
   - Respect min_hours_between per send type

3. schedule-assembler.md:
   - Accept new fields in assembly
   - Call save_schedule with send_type_key, channel_key, target_key
   - Include linked_post_url, expires_at, parent_item_id
   - Generate summary by send_type category

4. quality-validator.md:
   - Validate media requirements per send type
   - Validate flyer requirements
   - Validate page type restrictions
   - Validate expiration is set for expiring types
   - Validate follow-ups have parent_send_id
   - Check send type constraints (max_per_day, etc.)
```

### Quality Gate 3

**Verification Agent:** `code-reviewer`

**Checklist:**
- [ ] SKILL.md updated with complete 21-type system
- [ ] All 4 new supporting docs created
- [ ] 3 new agent definitions created
- [ ] 4 existing agent definitions updated
- [ ] All frontmatter valid (name, description, tools, model)
- [ ] All agents have clear mission statements
- [ ] Tool access properly scoped
- [ ] Model selection appropriate
- [ ] Follows 2025 Claude Code best practices

**Verification:**
```bash
# Check skill files exist
ls -la .claude/skills/eros-schedule-generator/

# Check agent files exist
ls -la .claude/agents/

# Validate frontmatter (check first 10 lines of each agent)
head -10 .claude/agents/*.md
```

---

## WAVE 4: Pipeline Intelligence

### Objective
Implement the intelligent orchestration logic that ties everything together - the allocation algorithms, matching heuristics, and optimization patterns that make the schedule generator produce high-quality, revenue-optimized schedules.

### Assigned Agents

| Role | Agent | Model | Tools |
|------|-------|-------|-------|
| **Primary** | `llm-architect` | Opus | All |
| **Prompts** | `prompt-engineer` | Sonnet | All |
| **Verification** | `code-reviewer` | Sonnet | All |

### Files to Create

```
.claude/skills/eros-schedule-generator/
├── ORCHESTRATION.md            # NEW - Master orchestration logic
├── ALLOCATION_ALGORITHM.md     # NEW - Detailed allocation algorithm
├── MATCHING_HEURISTICS.md      # NEW - Caption matching logic
└── OPTIMIZATION_WEIGHTS.md     # NEW - Scoring and weighting

python/
├── __init__.py                 # NEW - Package init
├── allocation/
│   ├── __init__.py
│   └── send_type_allocator.py  # NEW - Allocation algorithm
├── matching/
│   ├── __init__.py
│   └── caption_matcher.py      # NEW - Type-aware matching
└── optimization/
    ├── __init__.py
    └── schedule_optimizer.py   # NEW - Optimization logic
```

### Task 4.1: Orchestration Logic

**Agent:** `llm-architect`

**Prompt:**
```
Create ORCHESTRATION.md documenting the complete pipeline orchestration:

1. Pipeline Phases (detailed):

   PHASE 1: INITIALIZATION
   - Load creator profile via get_creator_profile
   - Load send types via get_send_types (filtered by page_type)
   - Load volume config via get_volume_config
   - Load performance trends via get_performance_trends
   - Determine volume adjustments based on saturation/opportunity

   PHASE 2: SEND TYPE ALLOCATION
   - Input: volume_config, days_to_schedule, page_type
   - Algorithm: Distribute send types across days
   - Output: allocation_matrix[day][slot] = send_type_key

   PHASE 3: CONTENT MATCHING
   - For each allocated slot:
     - Call get_send_type_captions with send_type_key
     - Cross-reference vault_availability
     - Select highest scoring caption not yet used
     - Track usage to prevent duplicates

   PHASE 4: AUDIENCE TARGETING
   - For each item:
     - Determine target based on send_type
     - Apply page_type rules
     - Set channel based on send_type.platform_feature

   PHASE 5: TIMING OPTIMIZATION
   - Sort items by priority
   - Assign optimal times based on:
     - Historical best_timing data
     - Send type timing rules
     - min_hours_between constraints
   - Calculate follow-up times

   PHASE 6: FOLLOW-UP GENERATION
   - Identify items with can_have_followup=1
   - Generate ppv_followup items
   - Link via parent_send_id
   - Select followup captions

   PHASE 7: ASSEMBLY & VALIDATION
   - Combine all components
   - Run quality validation
   - Generate output format
   - Save to database

2. Error Handling:
   - Insufficient captions: Warn, use lower freshness threshold
   - No vault content: Skip content_type_id assignment
   - Volume exceeded: Truncate with priority order
   - Invalid send type for page: Filter and warn

3. Adaptive Adjustments:
   - saturation_score > 70: Reduce revenue items -20%
   - opportunity_score > 70: Increase revenue items +20%
   - Low caption freshness: Prioritize text_only bumps
```

### Task 4.2: Allocation Algorithm

**Agent:** `llm-architect`

**Prompt:**
```
Create ALLOCATION_ALGORITHM.md with the complete allocation logic:

1. Volume Tier Defaults:

   | Tier | Fans | Rev/Day | Eng/Day | Ret/Day |
   |------|------|---------|---------|---------|
   | Low | 0-999 | 3 | 3 | 1 |
   | Mid | 1K-4.9K | 4 | 4 | 2 |
   | High | 5K-14.9K | 6 | 5 | 2 |
   | Ultra | 15K+ | 8 | 6 | 3 |

2. Category Distribution Algorithm:

   def allocate_day(volume_config, day_of_week, page_type):
       revenue_slots = []
       engagement_slots = []
       retention_slots = []

       # REVENUE (60% of content)
       # Must include: 2-3 ppv_video
       # Should include: 0-1 bundle OR game OR flash_bundle
       # May include: 0-1 vip_program (if not posted this week)

       # ENGAGEMENT (30% of content)
       # Mix of bump types:
       #   40% bump_normal (short, easy)
       #   20% bump_descriptive (story)
       #   20% bump_text_only (no media needed)
       #   10% bump_flyer (high effort, high impact)
       #   10% dm_farm or like_farm
       # Plus: 1-2 link_drops for active campaigns

       # RETENTION (10% of content, paid pages only)
       # Daily: 1 expired_winback
       # Daily: 1 renew_on_message (to renew_off)
       # As needed: ppv_followup (auto-generated)

       return allocation

3. Day-of-Week Adjustments:
   - Friday: +1 PPV (weekend prep)
   - Saturday: +1 engagement (high activity)
   - Sunday: +1 PPV (high conversion day)
   - Monday: -1 revenue (lower engagement)

4. Variety Rules:
   - No same send_type 2 slots in a row
   - Maximum 2 of same send_type per day
   - bundle/flash_bundle/game: Max 1 per day
   - vip_program: Max 1 per week
   - link_drop: Only for active campaigns

5. Output Format:
   allocation = {
       "2025-12-16": [
           {"slot": 1, "send_type": "ppv_video", "priority": 1},
           {"slot": 2, "send_type": "bump_normal", "priority": 2},
           {"slot": 3, "send_type": "ppv_video", "priority": 1},
           {"slot": 4, "send_type": "link_drop", "priority": 3},
           ...
       ]
   }
```

### Task 4.3: Caption Matching Heuristics

**Agent:** `prompt-engineer`

**Prompt:**
```
Create MATCHING_HEURISTICS.md with caption selection logic:

1. Selection Algorithm:

   def select_caption(creator_id, send_type_key, used_caption_ids):
       # Get type-appropriate captions
       captions = get_send_type_captions(
           creator_id=creator_id,
           send_type_key=send_type_key,
           min_freshness=30,
           min_performance=40,
           limit=20
       )

       # Filter out already used
       available = [c for c in captions if c.caption_id not in used_caption_ids]

       # Score each caption
       for caption in available:
           caption.score = calculate_score(caption, send_type_key)

       # Sort by score descending
       available.sort(key=lambda c: c.score, reverse=True)

       # Return top caption
       return available[0] if available else None

2. Scoring Formula:

   score = (
       performance_score * 0.35 +
       freshness_score * 0.25 +
       type_priority_bonus * 0.20 +
       persona_match_bonus * 0.10 +
       diversity_bonus * 0.10
   )

   Where:
   - type_priority_bonus: 20 if priority=1, 10 if priority=2-3, 0 otherwise
   - persona_match_bonus: Based on tone/emoji alignment
   - diversity_bonus: Higher if content_type not recently used

3. Fallback Strategy:
   - If no captions at freshness>=30: Try freshness>=20
   - If no captions at performance>=40: Try performance>=30
   - If no type-specific captions: Use generic high-performers
   - If still none: Flag for manual caption creation

4. Send Type Specific Rules:

   ppv_video:
   - Prefer ppv_unlock caption_type
   - Long captions (300+ chars)
   - Heavy emoji usage

   bump_text_only:
   - MUST be flirty_opener type
   - Short captions (<100 chars)
   - No media requirements

   ppv_followup:
   - MUST be ppv_followup caption_type
   - Creates urgency/FOMO
   - Short and punchy

   expired_winback:
   - MUST be renewal_pitch type
   - Matches current campaign
   - Includes incentive mention
```

### Task 4.4: Optimization Weights

**Agent:** `llm-architect`

**Prompt:**
```
Create OPTIMIZATION_WEIGHTS.md with tunable parameters:

1. Timing Weights:

   PRIME_HOURS = [10, 14, 19, 21]  # 10am, 2pm, 7pm, 9pm
   PRIME_HOUR_BOOST = 1.3

   PRIME_DAYS = [4, 6]  # Friday, Sunday
   PRIME_DAY_BOOST = 1.2

   AVOID_HOURS = [3, 4, 5, 6, 7]  # 3am-7am
   AVOID_HOUR_PENALTY = 0.5

2. Send Type Timing Preferences:

   TIMING_PREFERENCES = {
       "ppv_video": {"preferred_hours": [19, 21], "boost": 1.3},
       "bundle": {"preferred_hours": [14, 19], "boost": 1.2},
       "bump_normal": {"preferred_hours": "any", "boost": 1.0},
       "link_drop": {"offset_from_parent": 180},  # 3 hours after
       "ppv_followup": {"offset_from_parent": 20},  # 20 min after
       "expired_winback": {"preferred_hours": [12], "boost": 1.0},
   }

3. Volume Adjustment Factors:

   SATURATION_THRESHOLDS = {
       "high": 70,      # Reduce volume
       "moderate": 50,  # Maintain
       "low": 30,       # Increase volume
   }

   ADJUSTMENT_FACTORS = {
       "saturated": 0.8,   # -20% items
       "opportunity": 1.2, # +20% items
       "normal": 1.0,
   }

4. Content Diversity Weights:

   DIVERSITY_TARGETS = {
       "min_content_types_per_week": 5,
       "max_same_type_consecutive": 2,
       "same_type_penalty_per_repeat": 0.9,
   }

5. Caption Freshness Decay:

   FRESHNESS_DECAY = {
       "days_since_use": [0, 7, 14, 30, 60],
       "freshness_score": [100, 80, 60, 40, 20],
   }

6. Price Optimization:

   PRICE_RANGES = {
       "ppv_video": {"min": 5, "max": 50, "default": 15},
       "bundle": {"min": 15, "max": 100, "default": 30},
       "game_post": {"min": 5, "max": 25, "default": 10},
   }

   PRICE_FACTORS = {
       "content_type_premium": {"anal": 1.3, "boy_girl": 1.2, "solo": 1.0},
       "performance_premium": {"top_10_pct": 1.5, "top_25_pct": 1.2},
   }
```

### Task 4.5: Python Implementation (Optional)

**Agent:** `python-pro`

**Prompt:**
```
Create Python implementation files for core algorithms:

1. python/allocation/send_type_allocator.py:
   - Class SendTypeAllocator
   - Method: allocate_week(volume_config, page_type, week_start) -> dict
   - Method: allocate_day(config, day_of_week) -> list
   - Uses the algorithm from ALLOCATION_ALGORITHM.md

2. python/matching/caption_matcher.py:
   - Class CaptionMatcher
   - Method: select_caption(creator_id, send_type_key, used_ids) -> Caption
   - Method: calculate_score(caption, send_type_key) -> float
   - Uses heuristics from MATCHING_HEURISTICS.md

3. python/optimization/schedule_optimizer.py:
   - Class ScheduleOptimizer
   - Method: optimize_timing(items, creator_timing_data) -> list
   - Method: apply_weights(item, weights) -> float
   - Uses weights from OPTIMIZATION_WEIGHTS.md

Note: These Python files are optional enhancements. The core logic
resides in the skill/agent documentation and MCP tools. Python
implementations provide reusable utilities for complex calculations.
```

### Quality Gate 4

**Verification Agent:** `code-reviewer`

**Checklist:**
- [ ] ORCHESTRATION.md documents complete pipeline flow
- [ ] ALLOCATION_ALGORITHM.md provides clear allocation logic
- [ ] MATCHING_HEURISTICS.md defines selection criteria
- [ ] OPTIMIZATION_WEIGHTS.md contains tunable parameters
- [ ] All algorithms are deterministic and reproducible
- [ ] Edge cases handled (insufficient captions, etc.)
- [ ] Weights and thresholds are reasonable
- [ ] Documentation is clear and actionable

**Verification:**
```bash
# Check all documentation files exist
ls -la .claude/skills/eros-schedule-generator/*.md

# Word count check (ensure substantive content)
wc -w .claude/skills/eros-schedule-generator/*.md

# If Python files created, run syntax check
python3 -m py_compile python/allocation/send_type_allocator.py
python3 -m py_compile python/matching/caption_matcher.py
python3 -m py_compile python/optimization/schedule_optimizer.py
```

---

## WAVE 5: Integration & Perfection

### Objective
End-to-end integration testing, comprehensive quality validation, performance benchmarking, and final polish to ensure production readiness.

### Assigned Agents

| Role | Agent | Model | Tools |
|------|-------|-------|-------|
| **Testing** | `code-reviewer` | Opus | All |
| **Debugging** | `debugger` | Sonnet | All |
| **Final QA** | `quality-validator` | Sonnet | MCP tools |

### Tasks

### Task 5.1: End-to-End Testing

**Agent:** `code-reviewer`

**Prompt:**
```
Perform comprehensive end-to-end testing of the enhanced schedule generator:

TEST SUITE 1: Database Integrity
- Verify all 21 send types exist with complete data
- Verify all 5 channels exist
- Verify all 10 audience targets exist
- Verify mapping tables populated
- Verify schedule_items has new columns
- Run PRAGMA foreign_key_check

TEST SUITE 2: MCP Server Tools
- Test all 17 tools individually
- Test get_send_types filtering
- Test get_send_type_captions returns type-appropriate captions
- Test save_schedule with new fields
- Test backward compatibility with old format

TEST SUITE 3: Single Creator Schedule
- Generate schedule for a paid page creator
- Verify all 3 categories represented (revenue, engagement, retention)
- Verify correct send types allocated
- Verify captions match send types
- Verify targets correctly assigned
- Verify follow-ups generated for PPVs
- Verify expiration set for expiring types

TEST SUITE 4: Batch Generation
- Generate schedules for 3 creators (different tiers)
- Verify volume scaling by tier
- Verify page_type restrictions honored
- Verify no errors or warnings

TEST SUITE 5: Edge Cases
- Creator with no captions for a send type
- Creator with empty vault
- Free page (no retention items)
- Ultra-high volume creator (15K+ fans)
- Schedule for specific send types only

Document all test results with pass/fail status and any issues found.
```

### Task 5.2: Performance Validation

**Agent:** `debugger`

**Prompt:**
```
Analyze and optimize performance of the schedule generator:

1. Query Performance:
   - Measure execution time for each MCP tool
   - Identify slow queries (>100ms)
   - Suggest index improvements

2. Generation Benchmarks:
   - Time to generate single creator schedule
   - Time to generate batch (all 37 creators)
   - Target: <60 seconds per creator

3. Memory Usage:
   - Monitor memory during batch generation
   - Identify any memory leaks
   - Optimize data structures if needed

4. Database Size Impact:
   - Measure database size increase from new tables
   - Estimate storage for 1 year of schedules
   - Recommend archival strategy

5. Bottleneck Analysis:
   - Profile the pipeline phases
   - Identify slowest components
   - Recommend optimizations
```

### Task 5.3: Quality Validation

**Agent:** `quality-validator` (custom task)

**Prompt:**
```
Run the quality-validator agent on 5 generated schedules:

For each schedule, validate:

1. Completeness Check:
   - All days have items
   - Revenue/engagement/retention balance correct
   - No empty slots

2. Send Type Validation:
   - All send_type_keys are valid
   - Page type restrictions honored
   - Constraints (max_per_day, etc.) respected

3. Caption Quality:
   - Authenticity score >= 65 for all items
   - Caption type matches send type requirements
   - No duplicate captions in same schedule

4. Timing Validation:
   - All times within creator's active hours
   - min_hours_between respected
   - Follow-ups correctly timed after parents

5. Target Validation:
   - Targets appropriate for send types
   - Channel supports the target
   - Page type compatible

6. Flyer/Media Requirements:
   - Items requiring flyer are flagged
   - Items requiring media have content_type
   - Items with no media are text_only types

Generate quality report with:
- Overall score (0-100)
- Pass/fail for each category
- Specific issues found
- Recommendations
```

### Task 5.4: Documentation Finalization

**Agent:** `code-reviewer`

**Prompt:**
```
Review and finalize all documentation:

1. Update docs/SCHEDULE_GENERATOR_BLUEPRINT.md:
   - Add section on 21 send types
   - Update architecture diagram
   - Add new MCP tools to list
   - Update agent descriptions

2. Create docs/SEND_TYPE_REFERENCE.md:
   - Quick reference for all 21 types
   - Includes key, category, requirements
   - Usage guidelines

3. Update docs/USER_GUIDE.md:
   - Add examples using new send types
   - Document new parameters
   - Add troubleshooting section

4. Create CHANGELOG.md entry:
   - Version 2.0: Enhanced Send Type System
   - List all new features
   - List all modified files
   - Migration instructions
```

### Task 5.5: Final Polish

**Agent:** `code-reviewer`

**Prompt:**
```
Final polish and production readiness check:

1. Code Quality:
   - Run linter on all Python files
   - Check for TODO comments
   - Remove debug statements
   - Ensure consistent formatting

2. Error Messages:
   - All error messages are user-friendly
   - Include actionable information
   - No technical jargon exposed to users

3. Logging:
   - Appropriate log levels
   - Key operations logged
   - No sensitive data in logs

4. Configuration:
   - All hardcoded values moved to config
   - Environment variables documented
   - Default values are sensible

5. Security Review:
   - No SQL injection vulnerabilities
   - Input validation complete
   - No sensitive data exposure

6. Backup Verification:
   - Rollback script tested
   - Database backup confirmed
   - Recovery procedure documented
```

### Quality Gate 5 (FINAL)

**Checklist:**
- [ ] All 5 test suites pass
- [ ] Performance benchmarks met (<60s per creator)
- [ ] Quality validation scores >=85 for all test schedules
- [ ] All documentation updated
- [ ] Code review complete with no critical issues
- [ ] Security review passed
- [ ] Rollback tested and working

**Final Acceptance Test:**
```bash
# Generate schedule for real creator
"Generate a weekly schedule for miss_alexa starting 2025-12-16"

# Verify output includes:
# - Multiple send types from all 3 categories
# - Correct channel assignments
# - Audience targets for retention items
# - Follow-ups for PPV items
# - Expiration for applicable items
# - Quality validation passed

# Save to database and verify
sqlite3 database/eros_sd_main.db "
SELECT
    si.scheduled_date,
    st.send_type_key,
    st.category,
    c.channel_key,
    at.target_key,
    si.is_followup
FROM schedule_items si
JOIN send_types st ON si.send_type_id = st.send_type_id
JOIN channels c ON si.channel_id = c.channel_id
LEFT JOIN audience_targets at ON si.target_id = at.target_id
WHERE si.template_id = (SELECT MAX(template_id) FROM schedule_templates)
ORDER BY si.scheduled_date, si.scheduled_time
LIMIT 20;
"
```

---

## 6. Complete File Inventory

### Files to CREATE

| File | Wave | Agent | Description |
|------|------|-------|-------------|
| `database/migrations/008_send_types_foundation.sql` | 1 | sql-pro | Core tables |
| `database/migrations/008_send_types_seed_data.sql` | 1 | sql-pro | Seed data |
| `database/migrations/008_schedule_items_enhancement.sql` | 1 | sql-pro | Column additions |
| `database/migrations/008_mapping_tables.sql` | 1 | sql-pro | Mapping tables |
| `database/migrations/008_rollback.sql` | 1 | sql-pro | Rollback script |
| `.claude/skills/.../SEND_TYPES.md` | 3 | command-architect | Send type reference |
| `.claude/skills/.../ALLOCATION_RULES.md` | 3 | command-architect | Allocation rules |
| `.claude/skills/.../TARGETING_GUIDE.md` | 3 | command-architect | Targeting guide |
| `.claude/skills/.../FOLLOWUP_PATTERNS.md` | 3 | command-architect | Follow-up patterns |
| `.claude/agents/send-type-allocator.md` | 3 | command-architect | New agent |
| `.claude/agents/audience-targeter.md` | 3 | command-architect | New agent |
| `.claude/agents/followup-generator.md` | 3 | command-architect | New agent |
| `.claude/skills/.../ORCHESTRATION.md` | 4 | llm-architect | Pipeline logic |
| `.claude/skills/.../ALLOCATION_ALGORITHM.md` | 4 | llm-architect | Algorithm |
| `.claude/skills/.../MATCHING_HEURISTICS.md` | 4 | prompt-engineer | Matching logic |
| `.claude/skills/.../OPTIMIZATION_WEIGHTS.md` | 4 | llm-architect | Weights |
| `docs/SEND_TYPE_REFERENCE.md` | 5 | code-reviewer | Quick reference |

### Files to EDIT

| File | Wave | Agent | Changes |
|------|------|-------|---------|
| `mcp/eros_db_server.py` | 2 | python-pro | Add 6 tools, enhance 2 |
| `mcp/test_server.py` | 2 | python-pro | Add tests |
| `.claude/skills/.../SKILL.md` | 3 | command-architect | Full update |
| `.claude/agents/content-curator.md` | 3 | command-architect | Type-aware matching |
| `.claude/agents/timing-optimizer.md` | 3 | command-architect | Type timing |
| `.claude/agents/schedule-assembler.md` | 3 | command-architect | New fields |
| `.claude/agents/quality-validator.md` | 3 | command-architect | New validation |
| `docs/SCHEDULE_GENERATOR_BLUEPRINT.md` | 5 | code-reviewer | Update |
| `docs/USER_GUIDE.md` | 5 | code-reviewer | Update |

---

## 7. Success Criteria

### Minimum Viable Product (MVP)

- [ ] All 21 send types in database
- [ ] MCP tools support new types
- [ ] Single creator schedule generates with multiple send types
- [ ] Schedules save correctly with new fields

### Full Product

- [ ] All 37 creators can be scheduled
- [ ] All 3 categories properly allocated
- [ ] Follow-ups auto-generated
- [ ] Audience targeting working
- [ ] Expiration handling working
- [ ] Quality validation passing >=85

### Excellence Tier

- [ ] Performance <60 seconds per creator
- [ ] Caption authenticity >=75 average
- [ ] Content diversity score >=0.8
- [ ] Zero constraint violations
- [ ] Complete documentation
- [ ] Rollback tested and verified

---

## 8. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Migration corrupts database | HIGH | Backup before each wave, test rollback |
| MCP server breaks | HIGH | Maintain backward compatibility |
| Insufficient captions per type | MEDIUM | Implement fallback strategy |
| Performance degradation | MEDIUM | Benchmark at each wave |
| Agent definitions invalid | LOW | Validate frontmatter syntax |
| Integration failures | MEDIUM | Test incrementally after each wave |

### Rollback Procedure

```bash
# If any wave fails, rollback database:
sqlite3 database/eros_sd_main.db < database/migrations/008_rollback.sql

# Restore backup if needed:
cp database/eros_sd_main.db.backup database/eros_sd_main.db

# Revert MCP server changes:
git checkout mcp/eros_db_server.py

# Revert skill/agent changes:
git checkout .claude/
```

---

## Execution Checklist

```
[ ] PRE-EXECUTION
    [ ] Backup database
    [ ] Review plan with stakeholder
    [ ] Confirm agent availability

[ ] WAVE 1: DATABASE FOUNDATION
    [ ] Task 1.1: Core tables
    [ ] Task 1.2: Seed data
    [ ] Task 1.3: Schedule items enhancement
    [ ] Task 1.4: Mapping tables
    [ ] Task 1.5: Optimization
    [ ] Quality Gate 1 PASSED

[ ] WAVE 2: MCP SERVER
    [ ] Task 2.1: New tools
    [ ] Task 2.2: Enhanced tools
    [ ] Task 2.3: Registration
    [ ] Task 2.4: Tests
    [ ] Quality Gate 2 PASSED

[ ] WAVE 3: SKILL & AGENTS
    [ ] Task 3.1: Enhanced skill
    [ ] Task 3.2: Supporting docs
    [ ] Task 3.3: New agents
    [ ] Task 3.4: Updated agents
    [ ] Quality Gate 3 PASSED

[ ] WAVE 4: PIPELINE INTELLIGENCE
    [ ] Task 4.1: Orchestration
    [ ] Task 4.2: Allocation
    [ ] Task 4.3: Matching
    [ ] Task 4.4: Weights
    [ ] Task 4.5: Python (optional)
    [ ] Quality Gate 4 PASSED

[ ] WAVE 5: INTEGRATION & PERFECTION
    [ ] Task 5.1: E2E testing
    [ ] Task 5.2: Performance
    [ ] Task 5.3: Quality validation
    [ ] Task 5.4: Documentation
    [ ] Task 5.5: Final polish
    [ ] Quality Gate 5 (FINAL) PASSED

[ ] POST-EXECUTION
    [ ] Generate production schedules
    [ ] Monitor for issues
    [ ] Archive backup
```

---

## Conclusion

This Perfected Master Enhancement Plan transforms the EROS Schedule Generator from a basic 2-type system to a comprehensive 21-type professional platform. By executing in 5 carefully orchestrated waves with specialized agents, we ensure:

1. **Database integrity** through proper migration and rollback procedures
2. **API completeness** with 6 new MCP tools and enhanced existing tools
3. **Intelligence** through documented algorithms and heuristics
4. **Quality** through comprehensive testing and validation
5. **Maintainability** through clear documentation and code review

**Total Estimated Execution:** 5 waves, ~4-6 hours of agent time

**Expected Outcome:** A production-ready schedule generator that accurately models all 21 OnlyFans content operations, produces revenue-optimized schedules, and adapts to creator-specific patterns.

---

*Document Version: 2.0*
*Last Updated: 2025-12-15*
*Status: READY FOR EXECUTION*
