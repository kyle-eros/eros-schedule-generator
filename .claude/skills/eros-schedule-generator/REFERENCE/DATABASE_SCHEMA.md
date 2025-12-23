# Database Schema Quick Reference

This reference documents the correct column names and table structures for the EROS database. Use this to prevent schema mismatches when writing custom queries.

**CRITICAL**: Always prefer MCP tools over raw SQL queries. MCP tools abstract the database schema and enforce Four-Layer Defense validation.

## Common Schema Mistakes

These incorrect column names have caused pipeline failures:

| Table | WRONG Column | CORRECT Column | Correct Type |
|-------|--------------|----------------|--------------|
| `content_categories` | `category_name` | `display_name` | TEXT |
| `content_types` | `content_type_name` | `type_name` | TEXT |
| `send_types` | `send_type_name` | `display_name` | TEXT |
| `creator_personas` | `tone` | `primary_tone` | TEXT |
| `creator_personas` | `archetype` | N/A | Does not exist |
| `creator_personas` | `voice_sample_1` | N/A | Does not exist |
| `top_content_types` | `content_type_id` | `content_type` | TEXT (name) |
| `vault_matrix` | `content_type` | `content_type_id` | INTEGER (FK) |
| `v_wall_post_best_hours` | `hour_of_day` | `posting_hour` | INTEGER |
| `volume_assignments` | `weekly_ppv_cap` | N/A | Does not exist |
| `volume_assignments` | `weekly_total_cap` | N/A | Does not exist |
| `caption_bank` | `tone` | N/A | Removed in v2.0 |
| `caption_bank` | `performance_score` | `performance_tier` | INTEGER (1-4) |
| `caption_bank` | `creator_id` | N/A | Removed (universal pool) |
| `caption_bank` | `emoji_style` | N/A | Removed in v2.0 |
| `caption_bank` | `slang_level` | N/A | Removed in v2.0 |

## Non-Existent Tables

| Referenced Table | ACTUAL Table |
|-----------------|--------------|
| `content_type_rankings` | `top_content_types` |

## Critical Table Schemas

### creators

```sql
CREATE TABLE creators (
  creator_id TEXT PRIMARY KEY,
  page_name TEXT NOT NULL UNIQUE,
  display_name TEXT,
  page_type TEXT CHECK(page_type IN ('paid', 'free')),
  subscription_price REAL,
  timezone TEXT DEFAULT 'America/Los_Angeles',
  creator_group TEXT,
  current_active_fans INTEGER DEFAULT 0,
  current_total_earnings REAL DEFAULT 0,
  performance_tier INTEGER CHECK(performance_tier BETWEEN 1 AND 5),
  persona_type TEXT,
  is_active INTEGER DEFAULT 1,
  content_category TEXT,  -- FK to content_categories.category_key
  vault_notes TEXT,
  created_at TEXT,
  updated_at TEXT
);
```

### creator_personas

```sql
CREATE TABLE creator_personas (
  persona_id INTEGER PRIMARY KEY AUTOINCREMENT,
  creator_id TEXT NOT NULL UNIQUE,
  primary_tone TEXT,        -- NOT 'tone'
  secondary_tone TEXT,      -- Separate column for secondary
  emoji_frequency TEXT,     -- 'none', 'light', 'moderate', 'heavy'
  favorite_emojis TEXT,     -- JSON array of emoji strings
  slang_level TEXT,         -- 'none', 'low', 'medium', 'high'
  avg_sentiment REAL,       -- 0.0 to 1.0
  avg_caption_length INTEGER,
  last_analyzed TEXT,
  created_at TEXT,
  updated_at TEXT,
  FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Note**: `archetype`, `voice_sample_1`, `voice_sample_2`, `signature_phrases` do NOT exist in this table.

### content_types

```sql
CREATE TABLE content_types (
  content_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
  type_name TEXT UNIQUE NOT NULL,  -- NOT 'content_type_name'
  type_category TEXT,
  description TEXT,
  priority_tier INTEGER,
  is_explicit INTEGER DEFAULT 0,
  created_at TEXT
);
```

### content_categories

```sql
CREATE TABLE content_categories (
  category_key TEXT PRIMARY KEY,
  display_name TEXT,      -- NOT 'category_name'
  bump_multiplier REAL,   -- 1.0-2.67x based on category
  description TEXT,
  created_at TEXT
);
```

**Bump Multipliers**:
| category_key | display_name | bump_multiplier |
|--------------|--------------|-----------------|
| lifestyle | Lifestyle | 1.0 |
| softcore | Softcore | 1.5 |
| amateur | Amateur | 2.0 |
| explicit | Explicit | 2.67 |

### send_types

```sql
CREATE TABLE send_types (
  send_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
  send_type_key TEXT UNIQUE NOT NULL,
  category TEXT CHECK(category IN ('revenue', 'engagement', 'retention')),
  display_name TEXT,        -- NOT 'send_type_name'
  description TEXT,
  purpose TEXT,
  strategy TEXT,
  requires_media INTEGER DEFAULT 0,
  requires_flyer INTEGER DEFAULT 0,
  requires_price INTEGER DEFAULT 0,
  requires_link INTEGER DEFAULT 0,
  has_expiration INTEGER DEFAULT 0,
  default_expiration_hours INTEGER,
  can_have_followup INTEGER DEFAULT 0,
  followup_delay_minutes INTEGER,
  page_type_restriction TEXT CHECK(page_type_restriction IN ('paid', 'free', 'both')),
  caption_length TEXT,
  emoji_recommendation TEXT,
  max_per_day INTEGER,
  max_per_week INTEGER,
  min_hours_between INTEGER,
  sort_order INTEGER,
  is_active INTEGER DEFAULT 1,
  created_at TEXT
);
```

### vault_matrix

```sql
CREATE TABLE vault_matrix (
  vault_id INTEGER PRIMARY KEY AUTOINCREMENT,
  creator_id TEXT NOT NULL,
  content_type_id INTEGER NOT NULL,  -- FK, NOT 'content_type' directly
  has_content INTEGER DEFAULT 0,
  quantity_available INTEGER DEFAULT 0,
  quality_rating INTEGER CHECK(quality_rating BETWEEN 1 AND 5),
  notes TEXT,
  updated_at TEXT,
  UNIQUE(creator_id, content_type_id),
  FOREIGN KEY (creator_id) REFERENCES creators(creator_id),
  FOREIGN KEY (content_type_id) REFERENCES content_types(content_type_id)
);
```

**To get content type name, must JOIN**:
```sql
SELECT vm.*, ct.type_name
FROM vault_matrix vm
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE vm.creator_id = ?;
```

### top_content_types

```sql
CREATE TABLE top_content_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creator_id TEXT NOT NULL,
  analysis_date DATE NOT NULL,
  content_type TEXT NOT NULL,  -- TEXT name, NOT content_type_id
  rank INTEGER,
  send_count INTEGER,
  total_earnings REAL,
  avg_earnings REAL,
  avg_purchase_rate REAL,
  avg_rps REAL,
  performance_tier TEXT CHECK(performance_tier IN ('TOP', 'MID', 'LOW', 'AVOID')),
  recommendation TEXT,
  confidence_score REAL,
  UNIQUE(creator_id, analysis_date, content_type)
);
```

**Note**: This table stores `content_type` as TEXT (the name), not as a foreign key ID.

### volume_assignments

```sql
CREATE TABLE volume_assignments (
  assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  creator_id TEXT NOT NULL,
  volume_level TEXT CHECK(volume_level IN ('Low', 'Mid', 'High', 'Ultra')),
  ppv_per_day INTEGER,
  bump_per_day INTEGER,
  assigned_at TEXT,
  assigned_by TEXT,
  assigned_reason TEXT,
  is_active INTEGER DEFAULT 1,
  notes TEXT,
  FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);
```

**Note**: `weekly_ppv_cap`, `weekly_total_cap`, and similar columns do NOT exist. Weekly caps are calculated dynamically by `get_volume_config()`.

### v_wall_post_best_hours (VIEW)

```sql
CREATE VIEW v_wall_post_best_hours AS
SELECT
  posting_hour,      -- NOT 'hour_of_day'
  post_type,
  post_count,
  avg_earnings,
  avg_revenue_per_view,
  total_earnings_sum
FROM ...;
```

### caption_bank (v2.0 - Rebuilt 2025-12-22)

```sql
CREATE TABLE caption_bank (
  -- Primary Key
  caption_id INTEGER PRIMARY KEY,

  -- Core Caption Data (REQUIRED)
  caption_text TEXT NOT NULL,
  caption_hash TEXT NOT NULL UNIQUE,  -- SHA256 hash for deduplication

  -- Classification (REQUIRED - 100% accuracy target)
  caption_type TEXT NOT NULL,         -- Maps to send_type_caption_requirements
  content_type_id INTEGER NOT NULL,   -- FK to content_types

  -- Scheduling Eligibility
  schedulable_type TEXT CHECK (schedulable_type IN ('ppv', 'ppv_bump', 'wall')),
  is_paid_page_only INTEGER NOT NULL DEFAULT 0,  -- 1 = paid page exclusive
  is_active INTEGER NOT NULL DEFAULT 1,          -- Soft delete flag

  -- Performance Tier (1=ELITE, 2=PROVEN, 3=STANDARD, 4=UNPROVEN)
  performance_tier INTEGER NOT NULL DEFAULT 3 CHECK (performance_tier BETWEEN 1 AND 4),

  -- Price Guidance
  suggested_price REAL,
  price_range_min REAL,
  price_range_max REAL,

  -- Auto-calculated length for optimal filtering
  char_length INTEGER GENERATED ALWAYS AS (length(caption_text)) STORED,

  -- Classification Confidence
  classification_confidence REAL NOT NULL DEFAULT 0.5
    CHECK (classification_confidence >= 0 AND classification_confidence <= 1),
  classification_method TEXT NOT NULL DEFAULT 'unknown',  -- 'keyword', 'structural', 'llm', 'manual'

  -- Freshness Tracking (global usage)
  global_times_used INTEGER NOT NULL DEFAULT 0,
  global_last_used_date TEXT,

  -- Source Performance (aggregated from mass_messages)
  total_earnings REAL DEFAULT 0.0,
  total_sends INTEGER DEFAULT 0,
  avg_view_rate REAL DEFAULT 0.0,
  avg_purchase_rate REAL DEFAULT 0.0,

  -- Audit Trail
  source TEXT DEFAULT 'mass_messages_rebuild',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (content_type_id) REFERENCES content_types(content_type_id)
);
```

**Performance Tier Definitions**:
| Tier | Name | Criteria (PPV) | Criteria (Free) |
|------|------|----------------|-----------------|
| 1 | ELITE | earnings >= $500 | view_rate >= 40% |
| 2 | PROVEN | earnings >= $200 | view_rate >= 30% |
| 3 | STANDARD | earnings >= $100 | view_rate >= 25% |
| 4 | UNPROVEN | < $100 or insufficient data | < 25% or insufficient data |

**Removed Columns (from v1)**:
- `tone` - Never queried in MCP tools
- `performance_score` - Replaced by `performance_tier`
- `creator_id` - Universal pool (all captions shared)
- `emoji_style`, `slang_level` - 99%+ default values
- Various unused columns (23 total removed)

**Optimal Character Length**:
- 250-449 chars = +107.6% RPS (best performance)
- Use `char_length` column for filtering

## Common Query Patterns

### Get vault-compliant content types for a creator

```sql
SELECT ct.type_name, vm.quantity_available, vm.quality_rating
FROM vault_matrix vm
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE vm.creator_id = ?
  AND vm.has_content = 1;
```

### Get content type rankings with AVOID exclusion

```sql
SELECT content_type, performance_tier, avg_earnings, avg_rps
FROM top_content_types
WHERE creator_id = ?
  AND analysis_date = (SELECT MAX(analysis_date) FROM top_content_types WHERE creator_id = ?)
  AND performance_tier != 'AVOID'
ORDER BY rank ASC;
```

### Get creator persona with correct columns

```sql
SELECT creator_id, primary_tone, secondary_tone, emoji_frequency,
       slang_level, favorite_emojis, avg_sentiment
FROM creator_personas
WHERE creator_id = ?;
```

### Get best posting hours (correct view)

```sql
SELECT posting_hour, avg_earnings, post_count
FROM v_wall_post_best_hours
WHERE post_type = 'permanent'
ORDER BY avg_earnings DESC
LIMIT 10;
```

## MCP Tool to Table Mapping

| MCP Tool | Primary Table(s) |
|----------|------------------|
| `get_creator_profile` | `creators`, `creator_personas`, `top_content_types` |
| `get_persona_profile` | `creator_personas` |
| `get_vault_availability` | `vault_matrix` JOIN `content_types` |
| `get_content_type_rankings` | `top_content_types` |
| `get_volume_config` | Dynamic calculation (not static table) |
| `get_best_timing` | `mass_messages`, `day_of_week_performance` |
| `get_top_captions` | `caption_bank` JOIN `vault_matrix` |
| `get_send_types` | `send_types` |
| `save_schedule` | `schedule_templates`, `schedule_items` |

## Why MCP Tools Are Preferred

1. **Schema Abstraction**: MCP tools use correct column names internally
2. **Four-Layer Defense**: Vault/AVOID filtering enforced at query level
3. **Input Validation**: Parameters validated before query execution
4. **Parameterized Queries**: SQL injection protection built-in
5. **Consistent Types**: Return types documented and stable

**NEVER use raw SQL when MCP tool is available.**
