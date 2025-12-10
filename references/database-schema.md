# EROS Database Schema Reference

> Quick reference for constructing queries in the eros-schedule-generator skill.
> Last audited: 2025-12-09 | Database: eros_sd_main.db (80 MB)

---

## Quick Navigation

| Table | Records | Primary Use | Status |
|-------|---------|-------------|--------|
| [creators](#creators) | 36 | Creator profiles and metrics | COMPLETE |
| [mass_messages](#mass_messages) | 68,674 | PPV performance history | PARTIAL - 45% NULL creator_id |
| [caption_bank](#caption_bank) | 20,087 | Caption library with scoring | PARTIAL - 43.5% stale |
| [creator_personas](#creator_personas) | 35 | Voice matching profiles | NEAR COMPLETE - 1 missing |
| [vault_matrix](#vault_matrix) | 1,192 | Content inventory | COMPLETE |
| [content_types](#content_types) | 37 | Content classification | COMPLETE |
| [caption_creator_performance](#caption_creator_performance) | 11,069 | Per-creator stats | COMPLETE |
| [creator_analytics_summary](#creator_analytics_summary) | 36 | Pre-aggregated analytics | PARTIAL - only 90d period |
| [volume_assignments](#volume_assignments) | 36 | Volume level assignments | COMPLETE |
| [wall_posts](#wall_posts) | 198 | Wall post data | COMPLETE |
| [schedulers](#schedulers) | 13 | Scheduler staff | COMPLETE |
| [scheduler_assignments](#scheduler_assignments) | 35 | Creator-scheduler mappings | COMPLETE |
| [caption_audit_log](#caption_audit_log) | 15,084 | Caption change tracking | COMPLETE |
| [llm_quality_scores](#llm_quality_scores) | 0* | LLM caption quality cache | NEW (v2.0) |
| [creator_feature_flags](#creator_feature_flags) | 3 | Feature toggles | MINIMAL |
| [schema_migrations](#schema_migrations) | 3 | DB version tracking | COMPLETE |
| [agent_execution_log](#agent_execution_log) | 1 | Agent activity log | MINIMAL |
| [schedule_templates](#schedule_templates) | 0 | Weekly schedule templates | EMPTY |
| [schedule_items](#schedule_items) | 0 | Individual schedule items | EMPTY |
| [volume_performance_tracking](#volume_performance_tracking) | 0 | Volume optimization tracking | EMPTY |
| [caption_integrity_issues](#caption_integrity_issues) | 0 | Data quality issues | EMPTY |
| [poll_bank](#poll_bank) | 6 | Poll/quiz content storage | NEW (v2.6) |
| [free_preview_bank](#free_preview_bank) | 10 | Free preview content library | NEW (v2.6) |
| [game_wheel_configs](#game_wheel_configs) | 0 | Spin-the-wheel configurations | NEW (v2.6) |
| [vip_post_templates](#vip_post_templates) | 0 | VIP pricing page templates ($200+) | NEW (v3.0) |
| [tip_incentive_templates](#tip_incentive_templates) | 0 | Tip goals and first-to-tip templates | NEW (v3.0) |
| [link_drop_templates](#link_drop_templates) | 0 | Link drop and campaign templates | NEW (v3.0) |
| [engagement_templates](#engagement_templates) | 0 | DM farm, like farm, comment farm | NEW (v3.0) |
| [retention_templates](#retention_templates) | 0 | Renew-on and win-back templates | NEW (v3.0) |
| [bump_variants](#bump_variants) | 0 | Follow-up bump message variants | NEW (v3.0) |

**Total: 36 tables | 28 views | 21 triggers | 144+ indexes**

---

## Core Tables

### creators

**Records:** 36 | **Primary Key:** `creator_id` (TEXT)

**PURPOSE:** Central creator/page information with embedded current performance metrics. This is the authoritative source for creator identity, page type, fan counts, and revenue metrics.

**SKILL INTEGRATION:** Used in **Step 1 (ANALYZE)** to load creator profile. Queried by `load_creator_profile()` in generate_schedule.py. The `page_type` field determines paid vs free page rules in Step 8. The `current_active_fans` field drives volume level calculation in Step 4.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| creator_id | TEXT | NO | Primary key (UUID format) |
| page_name | TEXT | NO | OnlyFans page name (UNIQUE) |
| display_name | TEXT | NO | Display name for schedules |
| page_type | TEXT | NO | 'paid' or 'free' |
| subscription_price | REAL | YES | Monthly subscription price |
| is_active | INTEGER | YES | 1=active, 0=inactive (default: 1) |
| timezone | TEXT | YES | Primary timezone (default: America/Los_Angeles) |
| creator_group | TEXT | YES | Grouping/categorization |
| performance_tier | INTEGER | YES | 1=top, 2=mid, 3=standard (default: 3) |
| **--- Current Metrics ---** | | | |
| current_active_fans | INTEGER | YES | Active subscriber count |
| current_following | INTEGER | YES | Following count |
| current_new_fans | INTEGER | YES | New fans this period |
| current_fans_renew_on | INTEGER | YES | Fans with auto-renew |
| current_renew_on_pct | REAL | YES | Renewal percentage |
| current_expired_fan_change | INTEGER | YES | Expired fan delta |
| **--- Revenue Metrics ---** | | | |
| current_total_earnings | REAL | YES | Total earnings |
| current_subscription_net | REAL | YES | Subscription revenue |
| current_tips_net | REAL | YES | Tips revenue |
| current_message_net | REAL | YES | PPV/message revenue |
| current_posts_net | REAL | YES | Posts revenue |
| current_streams_net | REAL | YES | Streams revenue |
| current_refund_net | REAL | YES | Refunds |
| current_contribution_pct | REAL | YES | Portfolio contribution % |
| current_of_ranking | TEXT | YES | OF ranking (e.g., "0.12%") |
| **--- Efficiency Metrics ---** | | | |
| current_avg_spend_per_spender | REAL | YES | Avg spend per paying fan |
| current_avg_spend_per_txn | REAL | YES | Avg transaction value |
| current_avg_earnings_per_fan | REAL | YES | Revenue per fan |
| current_avg_subscription_length | TEXT | YES | Avg sub duration |
| avg_purchase_rate | REAL | YES | Average purchase rate |
| **--- Metadata ---** | | | |
| metrics_snapshot_date | TEXT | YES | When metrics were captured |
| metrics_period_start | TEXT | YES | Metrics period start |
| metrics_period_end | TEXT | YES | Metrics period end |
| persona_type | TEXT | YES | Persona classification |
| account_age_days | INTEGER | YES | Account age in days |
| ppv_creator_id | TEXT | YES | PPV tracking ID |
| ppv_aliases | TEXT | YES | PPV name aliases |
| created_at | TEXT | YES | Creation timestamp |
| updated_at | TEXT | YES | Update timestamp |
| first_seen_at | TEXT | YES | First seen date |
| last_seen_at | TEXT | YES | Last seen date |
| notes | TEXT | YES | Additional notes |

**ISSUES/WARNINGS:**
- All 12 paid page creators have `subscription_price = $0.00` - needs update from OnlyFans data

**DATA STATUS:** COMPLETE - All 36 creators populated with current metrics

**Key Indexes:**
- `idx_creators_page_name` - page_name lookup
- `idx_creators_active` - partial index for is_active=1
- `idx_creators_active_fans` - is_active + current_active_fans DESC
- `idx_creators_performance_tier` - performance_tier grouping

---

### mass_messages

**Records:** 68,674 | **Primary Key:** `message_id` (TEXT)

**PURPOSE:** Central fact table for PPV performance analytics. Contains historical send data with engagement metrics. Has 8 triggers for automatic caption_bank and caption_creator_performance updates.

**SKILL INTEGRATION:** Used in **Step 1 (ANALYZE)** to calculate best performing hours via `load_optimal_hours()`. Queried with 90-day lookback to find sending_hour patterns. The `view_rate` and `purchase_rate` columns are GENERATED from other columns.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| message_id | TEXT | NO | Primary key identifier |
| creator_id | TEXT | YES | FK to creators |
| page_name | TEXT | YES | Page name (denormalized) |
| message_content | TEXT | YES | Full caption text |
| sending_time | TEXT | NO | ISO datetime sent |
| price | REAL | YES | Unlock price (default: 0.0) |
| sent_count | INTEGER | YES | Recipients (default: 0) |
| viewed_count | INTEGER | YES | Opens (default: 0) |
| purchased_count | INTEGER | YES | Unlocks (default: 0) |
| earnings | REAL | YES | Total revenue (default: 0.0) |
| message_type | TEXT | NO | 'ppv' or 'free' |
| caption_id | INTEGER | YES | FK to caption_bank |
| content_type_id | INTEGER | YES | FK to content_types |
| flyer_used | INTEGER | YES | Flyer usage flag |
| follow_up_sent | INTEGER | YES | Follow-up sent flag |
| original_content_type | TEXT | YES | Original content type |
| classification_confidence | REAL | YES | ML classification confidence |
| imported_at | TEXT | YES | Import timestamp |
| source_file | TEXT | YES | Source file name |
| **--- GENERATED Columns ---** | | | |
| sending_hour | INTEGER | GENERATED | Hour 0-23 (from sending_time) |
| sending_day_of_week | INTEGER | GENERATED | 0=Sun, 6=Sat |
| view_rate | REAL | GENERATED | viewed_count/sent_count |
| purchase_rate | REAL | GENERATED | purchased_count/sent_count |
| revenue_per_send | REAL | GENERATED | earnings/sent_count |

**ISSUES/WARNINGS:**
- **CRITICAL:** 30,361 records (45.4%) have NULL `creator_id` - limits creator-level analytics
- **CRITICAL:** 44,390 records (66.4%) have NULL `caption_id` - prevents caption performance tracking
- **CRITICAL:** 45,476 records (68.1%) have NULL `content_type_id` - limits content type analysis
- 264 records have `viewed_count > sent_count` (data import anomaly)
- 505 records have `sent_count = 0`

**DATA STATUS:** PARTIAL - Core data complete but significant NULL linkage issues

**Triggers:**
- `trg_mm_caption_performance_insert` - Updates caption_bank stats on new message
- `trg_mm_caption_performance_update` - Updates caption_bank when earnings added
- `trg_mm_caption_creator_performance_insert` - Updates per-creator stats on insert
- `trg_mm_caption_creator_performance_update` - Updates per-creator stats on update
- `trg_mm_caption_earnings_correction` - Corrects caption earnings when changed
- `trg_mm_validate_insert` - Validates data integrity on insert
- `trg_mm_validate_update` - Validates data integrity on update

**Key Indexes:**
- `idx_mm_creator_time` - creator_id + sending_time DESC
- `idx_mm_creator_type_analytics` - creator_id + message_type + sending_hour + sending_day_of_week (partial: ppv only)
- `idx_mm_earnings` - earnings DESC
- `idx_mm_caption_earnings` - caption_id + earnings (partial: caption_id NOT NULL AND earnings > 0)

---

### caption_bank

**Records:** 20,087 | **Primary Key:** `caption_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Master caption library with performance scoring and style attributes. Central source for all PPV caption text. Includes freshness decay scoring and persona matching attributes.

**SKILL INTEGRATION:** Used in **Step 2 (MATCH CONTENT)** and **Step 5 (ASSIGN CAPTIONS)**. Queried by `load_available_captions()` with freshness >= 30 filter and vault_matrix join. The Vose Alias weighted selector operates on `performance_score * 0.6 + freshness_score * 0.4` combined weight.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| caption_id | INTEGER | NO | Auto-increment primary key |
| caption_hash | TEXT | NO | Dedup hash (UNIQUE) |
| caption_text | TEXT | NO | Full caption content |
| caption_normalized | TEXT | NO | Normalized for matching |
| caption_type | TEXT | NO | Type classification (ppv, bump, etc.) |
| content_type_id | INTEGER | YES | FK to content_types |
| creator_id | TEXT | YES | FK to creators (if creator-specific) |
| page_name | TEXT | YES | Page name (denormalized) |
| is_universal | INTEGER | YES | 1=works for any creator (default: 0) |
| is_active | INTEGER | YES | 1=active, 0=deactivated (default: 1) |
| schedulable_type | TEXT | YES | Schedulable type (ppv, ppv_follow_up, bundle, flash_bundle) (default: 'ppv') (NEW v3.0) |
| **--- Performance Metrics ---** | | | |
| times_used | INTEGER | YES | Global usage count (default: 0) |
| total_earnings | REAL | YES | Lifetime earnings (default: 0.0) |
| avg_earnings | REAL | YES | Per-use average (default: 0.0) |
| avg_purchase_rate | REAL | YES | Average conversion 0-1 (default: 0.0) |
| avg_view_rate | REAL | YES | Average opens 0-1 (default: 0.0) |
| performance_score | REAL | YES | 0-100 composite score (default: 50.0) |
| performance_tier | INTEGER | YES | 1=winner, 2=good, 3=standard (default: 3) |
| freshness_score | REAL | YES | 0-100, 100=never used (default: 100.0) |
| first_used_date | TEXT | YES | First usage date |
| last_used_date | TEXT | YES | Most recent usage |
| **--- Style Attributes ---** | | | |
| tone | TEXT | YES | playful, aggressive, sweet, dominant, bratty, seductive |
| emoji_style | TEXT | YES | heavy, moderate, light, none |
| slang_level | TEXT | YES | none, light, heavy |
| classification_confidence | REAL | YES | ML confidence (default: 0.0) |
| classification_method | TEXT | YES | How caption was classified |
| required_content_tags | TEXT | YES | Required content tags |
| excluded_content_tags | TEXT | YES | Excluded content tags |
| **--- Metadata ---** | | | |
| created_at | TEXT | YES | Creation timestamp |
| updated_at | TEXT | YES | Last update timestamp |
| created_by | TEXT | YES | Creation source (default: 'pipeline') |
| notes | TEXT | YES | Additional notes |

**Constraints:**
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**ISSUES/WARNINGS:**
- **CRITICAL:** 8,249 captions (43.5%) have `freshness_score < 30` (stale, below usable threshold)
- 84.7% of captions have `performance_score < 20` (may need scoring recalibration)
- 3,481 captions have blank/NULL `page_name` but are not marked `is_universal = 1`
- 99.7% of captions have `times_used = 0` (either new imports or usage not tracked)

**DATA STATUS:** PARTIAL - Schema complete but freshness/performance data needs attention

**Key Indexes:**
- `idx_caption_creator_perf` - creator_id + is_active + caption_type + performance_score DESC + freshness_score DESC (partial: is_active=1)
- `idx_caption_selection` - is_active + content_type_id + caption_type + freshness_score DESC + performance_score DESC
- `idx_caption_universal_selection` - is_active + is_universal + content_type_id + performance_score DESC (partial: is_active=1 AND is_universal=1)
- `idx_caption_freshness_active` - is_active + freshness_score
- `idx_caption_schedulable_type` - schedulable_type + is_active (partial: is_active=1) (NEW v3.0)

---

### creator_personas

**Records:** 35 | **Primary Key:** `persona_id` (INTEGER AUTOINCREMENT), **Unique:** `creator_id`

**PURPOSE:** Voice profiling for persona-based caption matching. Defines each creator's communication style including tone, emoji usage, and slang patterns.

**SKILL INTEGRATION:** Used in **Step 3 (MATCH PERSONA)** to calculate persona boost factors (1.0-1.4x). Queried by `apply_persona_scores()`. When `primary_tone` matches caption `tone`, a 1.20x boost is applied. Missing persona defaults to `primary_tone='playful'`.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| persona_id | INTEGER | NO | Auto-increment primary key |
| creator_id | TEXT | NO | FK to creators |
| primary_tone | TEXT | YES | playful, aggressive, sweet, dominant, bratty, seductive |
| emoji_frequency | TEXT | YES | heavy, moderate, light, none |
| favorite_emojis | TEXT | YES | JSON array of preferred emojis |
| slang_level | TEXT | YES | none, light, heavy |
| avg_sentiment | REAL | YES | -1 to 1 VADER score |
| avg_caption_length | INTEGER | YES | Average character count |
| last_analyzed | TEXT | YES | Last analysis date |
| created_at | TEXT | YES | Creation timestamp |
| updated_at | TEXT | YES | Update timestamp |

**ISSUES/WARNINGS:**
- **MODERATE:** Missing persona for creator `lola_reese_new` (creator_id: `24bf9f2d-0db3-411d-9def-0b149a5553ed`)

**DATA STATUS:** NEAR COMPLETE - 35/36 creators have persona data (97.2%)

**Key Indexes:**
- `idx_persona_creator` - creator_id (covering)

---

### vault_matrix

**Records:** 1,192 | **Primary Key:** `vault_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Content inventory matrix tracking which content types each creator has available. Used to filter captions to only those matching available vault content.

**SKILL INTEGRATION:** Used in **Step 2 (MATCH CONTENT)** to filter captions. The query joins `vault_matrix vm ON cb.creator_id = vm.creator_id AND cb.content_type_id = vm.content_type_id` with `WHERE vm.has_content = 1` filter.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| vault_id | INTEGER | NO | Auto-increment primary key |
| creator_id | TEXT | NO | FK to creators |
| content_type_id | INTEGER | NO | FK to content_types |
| has_content | INTEGER | YES | 1=available (default: 0) |
| quantity_available | INTEGER | YES | Piece count (default: 0) |
| quality_rating | INTEGER | YES | 1-5 scale |
| notes | TEXT | YES | Additional notes |
| updated_at | TEXT | YES | Update timestamp |

**ISSUES/WARNINGS:**
- All entries have `quantity_available = 0` (field not being populated)
- 684/1,192 entries have `has_content = 1` (57.6%)

**DATA STATUS:** COMPLETE - Structure complete, quantity_available unused

**Key Indexes:**
- `idx_vault_creator` - creator_id
- `idx_vault_has_content` - creator_id + has_content

---

### content_types

**Records:** 37 | **Primary Key:** `content_type_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Content classification taxonomy. Defines all content categories (solo, bg, gg, anal, etc.) with priority tiers for scheduling rotation.

**SKILL INTEGRATION:** Used in **Step 2 (MATCH CONTENT)** for type_name lookups. The `priority_tier` field influences content rotation logic in Step 5.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| content_type_id | INTEGER | NO | Auto-increment primary key |
| type_name | TEXT | NO | Content type name (UNIQUE) |
| type_category | TEXT | YES | Category grouping (solo, couples, group, act) |
| description | TEXT | YES | Type description |
| priority_tier | INTEGER | YES | Scheduling priority (1=highest) |
| is_explicit | INTEGER | YES | 1=explicit, 0=SFW (default: 1) |
| created_at | TEXT | YES | Creation timestamp |

**DATA STATUS:** COMPLETE - All 37 content types defined

---

### caption_creator_performance

**Records:** 11,069 | **Primary Key:** `id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Per-creator caption performance tracking. Enables personalized caption selection based on how each caption performs for a specific creator.

**SKILL INTEGRATION:** Can be used for creator-specific caption ranking. Currently the skill uses global caption_bank scores, but this table enables per-creator optimization.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | NO | Auto-increment primary key |
| caption_id | INTEGER | NO | FK to caption_bank |
| creator_id | TEXT | YES | FK to creators |
| page_name | TEXT | YES | Page name (denormalized) |
| times_used | INTEGER | YES | Uses for this creator (default: 0) |
| total_earnings | REAL | YES | Earnings for this creator (default: 0.0) |
| avg_earnings | REAL | YES | Per-use for this creator (default: 0.0) |
| avg_purchase_rate | REAL | YES | Purchase rate (default: 0.0) |
| avg_view_rate | REAL | YES | View rate (default: 0.0) |
| performance_score | REAL | YES | Creator-specific score 0-100 (default: 0.0) |
| first_used_date | TEXT | YES | First use by creator |
| last_used_date | TEXT | YES | Last use by creator |
| created_at | TEXT | YES | Creation timestamp |
| updated_at | TEXT | YES | Update timestamp |

**Constraints:** CHECK (performance_score >= 0 AND performance_score <= 100)

**DATA STATUS:** COMPLETE - Automatically maintained by triggers

**Key Indexes:**
- `idx_ccp_creator_perf` - creator_id + caption_id + performance_score DESC
- `idx_ccp_unique` - caption_id + creator_id (UNIQUE, partial: creator_id IS NOT NULL)

---

### creator_analytics_summary

**Records:** 36 | **Primary Key:** `summary_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Pre-aggregated analytics per creator for fast dashboard queries. Contains best performing hours, days, content types, and price points.

**SKILL INTEGRATION:** Can be used in **Step 1 (ANALYZE)** as an alternative to real-time mass_messages aggregation for faster schedule generation.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| summary_id | INTEGER | NO | Auto-increment primary key |
| creator_id | TEXT | NO | FK to creators |
| page_name | TEXT | YES | Page name (denormalized) |
| period_start | TEXT | NO | Period start date |
| period_end | TEXT | NO | Period end date |
| period_type | TEXT | NO | '7d', '30d', '90d', or 'all_time' |
| total_mass_messages | INTEGER | YES | Message count (default: 0) |
| total_wall_posts | INTEGER | YES | Wall post count (default: 0) |
| total_mm_earnings | REAL | YES | Total PPV earnings (default: 0) |
| avg_mm_earnings | REAL | YES | Per-message average (default: 0) |
| avg_view_rate | REAL | YES | Average opens (default: 0) |
| avg_purchase_rate | REAL | YES | Average conversion (default: 0) |
| best_mm_hours | TEXT | YES | JSON: top performing hours |
| best_days | TEXT | YES | JSON: top performing days |
| best_content_types | TEXT | YES | JSON: top content types |
| best_price_points | TEXT | YES | JSON: optimal prices |
| worst_content_types | TEXT | YES | JSON: worst content types |
| worst_price_points | TEXT | YES | JSON: worst prices |
| calculated_at | TEXT | YES | Calculation timestamp |

**Constraints:** CHECK (period_type IN ('7d', '30d', '90d', 'all_time'))

**ISSUES/WARNINGS:**
- **MODERATE:** Only `90d` period type is populated (missing 7d, 30d, all_time)

**DATA STATUS:** PARTIAL - Only 90-day analytics populated

**Key Indexes:**
- `idx_cas_creator_period` - creator_id + period_type
- `idx_cas_page_name` - page_name

---

### volume_assignments

**Records:** 36 | **Primary Key:** `assignment_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Volume level assignments controlling how many PPVs and bumps to schedule per day for each creator. Supports Low, Mid, High, Ultra levels.

**SKILL INTEGRATION:** Used in **Step 4 (BUILD STRUCTURE)** to determine daily PPV and bump counts. Queried via `v_current_volume_assignments` view.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| assignment_id | INTEGER | NO | Auto-increment primary key |
| creator_id | TEXT | NO | FK to creators |
| volume_level | TEXT | NO | 'Low', 'Mid', 'High', or 'Ultra' |
| ppv_per_day | INTEGER | NO | PPVs per day target |
| bump_per_day | INTEGER | NO | Bumps per day target |
| assigned_at | TEXT | NO | Assignment timestamp (default: now) |
| assigned_by | TEXT | NO | Assigner (default: 'system') |
| assigned_reason | TEXT | NO | Assignment reason |
| is_active | INTEGER | NO | Active status (default: 1) |
| notes | TEXT | YES | Additional notes |

**ISSUES/WARNINGS:**
- **MODERATE:** Skewed distribution: 32 Low, 4 Mid, 0 High, 0 Ultra (no high-volume assignments)

**DATA STATUS:** COMPLETE - All 36 creators have assignments

**Key Indexes:**
- `idx_va_creator_active` - creator_id + is_active (partial: is_active=1)
- `idx_va_volume_level` - volume_level (partial: is_active=1)

---

### wall_posts

**Records:** 198 | **Primary Key:** `post_id` (TEXT)

**PURPOSE:** Wall post performance tracking with timing analytics. Contains post engagement data for wall content optimization.

**SKILL INTEGRATION:** Not directly used in schedule generation. Available for wall post timing analysis via `v_wall_post_best_hours` view.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| post_id | TEXT | NO | Primary key identifier |
| creator_id | TEXT | YES | FK to creators |
| post_content | TEXT | YES | Post content |
| posting_time | TEXT | NO | ISO datetime posted |
| post_type | TEXT | YES | Content category |
| explicitness | TEXT | YES | Explicitness level |
| view_count | INTEGER | YES | Views (default: 0) |
| tips_received | REAL | YES | Tips revenue (default: 0.0) |
| price | REAL | YES | Post price (default: 0.0) |
| purchase_count | INTEGER | YES | Purchase count (default: 0) |
| purchase_earnings | REAL | YES | PPV revenue (default: 0.0) |
| content_type_id | INTEGER | YES | FK to content_types |
| content_type_tags | TEXT | YES | Content type tags |
| caption_id | INTEGER | YES | Matched caption ID |
| original_content_type | TEXT | YES | Original content type |
| imported_at | TEXT | YES | Import timestamp |
| source_file | TEXT | YES | Source file |
| **--- GENERATED Columns ---** | | | |
| posting_hour | INTEGER | GENERATED | Hour 0-23 |
| posting_day_of_week | INTEGER | GENERATED | 0=Sun |
| total_earnings | REAL | GENERATED | tips_received + purchase_earnings |
| revenue_per_view | REAL | GENERATED | total_earnings / view_count |

**DATA STATUS:** COMPLETE

**Key Indexes:**
- `idx_wp_creator_time` - creator_id + posting_time DESC
- `idx_wp_creator_type_analytics` - creator_id + post_type + posting_hour + posting_day_of_week
- `idx_wp_earnings` - total_earnings DESC

---

## Supporting Tables

### schedulers

**Records:** 13 | **Primary Key:** `scheduler_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Scheduler staff profiles for team assignment tracking.

**SKILL INTEGRATION:** Used for scheduler workload views. Not directly used in schedule generation algorithm.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| scheduler_id | INTEGER | NO | Auto-increment primary key |
| name | TEXT | NO | Scheduler name |
| email | TEXT | YES | Email address |
| is_active | INTEGER | YES | Active status (default: 1) |
| role | TEXT | YES | Role/title |
| total_ppvs_target | INTEGER | YES | Total PPV target (default: 0) |
| created_at | TEXT | YES | Creation timestamp |
| updated_at | TEXT | YES | Update timestamp |

**DATA STATUS:** COMPLETE

---

### scheduler_assignments

**Records:** 35 | **Primary Key:** `assignment_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Maps creators to their assigned schedulers with tier and target information.

**SKILL INTEGRATION:** Used for team coordination views. Not used in schedule algorithm.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| assignment_id | INTEGER | NO | Auto-increment primary key |
| scheduler_id | INTEGER | NO | FK to schedulers |
| creator_id | TEXT | NO | FK to creators |
| is_primary | INTEGER | YES | Primary assignment flag (default: 1) |
| assigned_at | TEXT | YES | Assignment timestamp |
| tier | TEXT | YES | Assignment tier |
| content_type | TEXT | YES | Content type focus |
| daily_ppv_target | INTEGER | YES | Daily PPV target (default: 0) |
| weekly_tasks | TEXT | YES | Weekly task notes |
| status | TEXT | YES | Assignment status (default: 'active') |
| notes | TEXT | YES | Additional notes |
| updated_at | TEXT | YES | Update timestamp |

**DATA STATUS:** COMPLETE

---

### caption_audit_log

**Records:** 15,084 | **Primary Key:** `audit_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Audit trail for caption modifications. Tracks field changes, reasons, and confidence scores.

**SKILL INTEGRATION:** Not used in schedule generation. Used for caption quality auditing.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| audit_id | INTEGER | NO | Auto-increment primary key |
| caption_id | INTEGER | NO | FK to caption_bank |
| field_name | TEXT | NO | Name of modified field |
| old_value | TEXT | YES | Previous value |
| new_value | TEXT | YES | New value |
| change_reason | TEXT | NO | Why change was made |
| change_method | TEXT | NO | How change was applied |
| confidence_score | REAL | YES | Confidence in change |
| agent_id | TEXT | YES | Agent that made change |
| created_at | TEXT | YES | Timestamp (default: now) |

**DATA STATUS:** COMPLETE

---

### llm_quality_scores

**Records:** 0* | **Primary Key:** `score_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Cache for LLM-evaluated caption quality scores. Stores authenticity, hook strength, CTA effectiveness, and conversion potential assessments. Scores expire after 7 days. *Table created on first use.

**SKILL INTEGRATION:** Used in **Step 4 (QUALITY SCORING)** in Full Mode. Queried by `QualityScorer.score_caption_batch()` in quality_scoring.py. Scores are cached to avoid redundant LLM calls. The `quality_score` field (0.7-1.3 multiplier) feeds directly into the new weight formula.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| score_id | INTEGER | NO | Auto-increment primary key |
| caption_id | INTEGER | NO | FK to caption_bank |
| creator_id | TEXT | NO | FK to creators |
| quality_score | REAL | NO | Overall multiplier (0.7-1.3) |
| authenticity_score | REAL | YES | Sounds human? (0.0-1.0, 35% weight) |
| hook_score | REAL | YES | Attention grabbing? (0.0-1.0, 25% weight) |
| cta_score | REAL | YES | Clear call-to-action? (0.0-1.0, 20% weight) |
| conversion_score | REAL | YES | Urgency/scarcity? (0.0-1.0, 20% weight) |
| true_tone | TEXT | YES | LLM-detected tone (may differ from caption_bank.tone) |
| classification | TEXT | YES | 'excellent', 'good', 'acceptable', 'poor' |
| reasoning | TEXT | YES | LLM explanation of scores |
| scored_at | TEXT | NO | Timestamp when scored |
| expires_at | TEXT | NO | Cache expiration (scored_at + 7 days) |

**Constraints:**
- UNIQUE(caption_id, creator_id) - One score per caption-creator pair
- Cache auto-expires after 7 days

**Classification Thresholds:**
| Classification | Score Range | Action |
|----------------|-------------|--------|
| Excellent | 0.75+ | Full weight, premium slots |
| Good | 0.50-0.74 | Normal selection |
| Acceptable | 0.30-0.49 | Reduced weight (0.85x modifier) |
| Poor | <0.30 | FILTERED OUT |

**Weight Formula Integration:**
```
# Full Mode weight calculation
quality_normalized = quality_score * 100  # Scale to 0-100
weight = (perf * 0.4 + fresh * 0.2 + quality_normalized * 0.4) * persona_boost * quality_modifier
```

**Key Indexes:**
- `idx_quality_caption_creator` - caption_id + creator_id (covering)
- `idx_quality_expires` - expires_at (for cache cleanup)

**DATA STATUS:** NEW (v2.0) - Table created on first use of Full Mode

---

### creator_feature_flags

**Records:** 3 | **Primary Key:** `flag_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Feature toggles per creator. Enables A/B testing and gradual feature rollouts.

**SKILL INTEGRATION:** Can be used to enable/disable features per creator (e.g., drip windows, follow-ups).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| flag_id | INTEGER | NO | Auto-increment primary key |
| creator_id | TEXT | NO | FK to creators |
| feature_name | TEXT | NO | Feature name |
| enabled | INTEGER | NO | Feature enabled (default: 0) |
| created_at | TEXT | YES | Creation timestamp |
| updated_at | TEXT | YES | Update timestamp |

**Trigger:** `trg_creator_feature_flags_updated_at` - Auto-updates timestamp

**DATA STATUS:** MINIMAL - Only 3 feature flags defined

---

### schema_migrations

**Records:** 3 | **Primary Key:** `version` (TEXT)

**PURPOSE:** Database migration version tracking. Records which migrations have been applied.

**SKILL INTEGRATION:** Not used in schedule generation. System maintenance table.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| version | TEXT | NO | Migration version (primary key) |
| applied_at | TEXT | YES | Application timestamp (default: now) |
| description | TEXT | YES | Migration description |

**DATA STATUS:** COMPLETE

---

### agent_execution_log

**Records:** 1 | **Primary Key:** `log_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Tracks agent execution history and actions.

**SKILL INTEGRATION:** Not used in schedule generation. Audit/monitoring table.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| log_id | INTEGER | NO | Auto-increment primary key |
| agent_id | TEXT | NO | Agent identifier |
| action_type | TEXT | NO | Action type |
| details | TEXT | YES | Additional details |
| records_affected | INTEGER | YES | Records modified |
| timestamp | TEXT | NO | Timestamp |

**DATA STATUS:** MINIMAL

---

## Content Type Template Tables (v3.0)

### vip_post_templates

**Records:** 0 | **Primary Key:** `template_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** VIP pricing page templates for paid page creators at $200+ price points. Used for high-value exclusive content offerings that drive premium revenue.

**SKILL INTEGRATION:** Used in content selection pipeline for VIP pricing page posts. Filtered by `page_type_filter = 'paid'` constraint. Selected via `all_schedulable_content` unified view.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| template_id | INTEGER | NO | - | Auto-increment primary key |
| template_hash | TEXT | NO | - | Unique hash for deduplication (UNIQUE) |
| template_text | TEXT | NO | - | Full template content |
| vip_tier_price | REAL | YES | 200.00 | VIP price point ($200+) |
| tone | TEXT | YES | - | Voice tone (playful, sweet, seductive, etc.) |
| emoji_style | TEXT | YES | - | Emoji usage (heavy, moderate, light, none) |
| flyer_required | INTEGER | YES | 1 | Requires flyer/graphic (1=yes, 0=no) |
| is_active | INTEGER | YES | 1 | Active status (1=active, 0=inactive) |
| is_universal | INTEGER | YES | 0 | Universal template (1=yes, 0=creator-specific) |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| avg_conversion_rate | REAL | YES | 0.0 | Average conversion rate (0.0-1.0) |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'paid' | MUST be 'paid' (CHECK constraint enforced) |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(template_hash) - Prevent duplicate templates
- CHECK (page_type_filter = 'paid') - VIP templates only for paid pages
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**Triggers:**
- `trg_vip_post_updated_at` - Auto-updates updated_at timestamp

**Key Indexes:**
- `idx_vip_active` - is_active + page_type_filter
- `idx_vip_creator` - creator_id + is_active (partial: is_active=1)
- `idx_vip_selection` - is_active + creator_id + freshness_score DESC + performance_score DESC (partial: is_active=1)

**DATA STATUS:** NEW (v3.0) - Empty, ready for population

---

### tip_incentive_templates

**Records:** 0 | **Primary Key:** `template_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Tip incentive and goal templates including first-to-tip, tip goals, tip menus, and tip races. Used to drive tip revenue through gamification and urgency.

**SKILL INTEGRATION:** Used in content selection for tip incentive campaigns. Selected via `all_schedulable_content` view. Filtered by `incentive_type` and `page_type_filter`.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| template_id | INTEGER | NO | - | Auto-increment primary key |
| template_hash | TEXT | NO | - | Unique hash for deduplication (UNIQUE) |
| template_text | TEXT | NO | - | Full template content |
| tip_goal_amount | REAL | YES | - | Tip goal target amount |
| expiration_hours | INTEGER | YES | 24 | Campaign expiration (hours) |
| incentive_type | TEXT | YES | 'first_to_tip' | Type: first_to_tip, tip_goal, tip_menu, tip_race |
| tone | TEXT | YES | - | Voice tone |
| emoji_style | TEXT | YES | - | Emoji usage |
| flyer_required | INTEGER | YES | 1 | Requires flyer/graphic (1=yes, 0=no) |
| is_active | INTEGER | YES | 1 | Active status |
| is_universal | INTEGER | YES | 0 | Universal template |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| avg_conversion_rate | REAL | YES | 0.0 | Average conversion rate |
| avg_tip_amount | REAL | YES | 0.0 | Average tip amount received |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'both' | 'paid', 'free', or 'both' |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(template_hash)
- CHECK (incentive_type IN ('first_to_tip', 'tip_goal', 'tip_menu', 'tip_race'))
- CHECK (page_type_filter IN ('paid', 'free', 'both'))
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**Triggers:**
- `trg_tip_incentive_updated_at` - Auto-updates updated_at timestamp

**Key Indexes:**
- `idx_tip_active` - is_active + page_type_filter
- `idx_tip_creator` - creator_id + is_active (partial: is_active=1)
- `idx_tip_type` - incentive_type + is_active (partial: is_active=1)
- `idx_tip_selection` - is_active + incentive_type + freshness_score DESC + performance_score DESC (partial: is_active=1)

**DATA STATUS:** NEW (v3.0) - Empty, ready for population

---

### link_drop_templates

**Records:** 0 | **Primary Key:** `template_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Link drop templates for cross-promotion, time-sensitive campaigns, and limited-time offers. Used for driving traffic to specific content or external promotions.

**SKILL INTEGRATION:** Used in content selection for link drop campaigns. Selected via `all_schedulable_content` view. Filtered by `link_type` and `page_type_filter`.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| template_id | INTEGER | NO | - | Auto-increment primary key |
| template_hash | TEXT | NO | - | Unique hash for deduplication (UNIQUE) |
| template_text | TEXT | NO | - | Full template content |
| link_type | TEXT | NO | - | Type: campaign, wall_post, ppv, bundle, promo, other |
| expiration_hours | INTEGER | YES | 24 | Link expiration (hours) |
| tone | TEXT | YES | - | Voice tone |
| emoji_style | TEXT | YES | - | Emoji usage |
| flyer_required | INTEGER | YES | 0 | Requires flyer/graphic (1=yes, 0=no) |
| is_active | INTEGER | YES | 1 | Active status |
| is_universal | INTEGER | YES | 1 | Universal template (defaults to universal) |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| click_through_rate | REAL | YES | 0.0 | Average click-through rate |
| conversion_rate | REAL | YES | 0.0 | Average conversion rate |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'both' | 'paid', 'free', or 'both' |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(template_hash)
- CHECK (link_type IN ('campaign', 'wall_post', 'ppv', 'bundle', 'promo', 'other'))
- CHECK (page_type_filter IN ('paid', 'free', 'both'))
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**Triggers:**
- `trg_link_drop_updated_at` - Auto-updates updated_at timestamp

**Key Indexes:**
- `idx_link_active` - is_active + page_type_filter
- `idx_link_type` - link_type + is_active (partial: is_active=1)
- `idx_link_selection` - is_active + link_type + freshness_score DESC + performance_score DESC (partial: is_active=1)

**DATA STATUS:** NEW (v3.0) - Empty, ready for population

---

### engagement_templates

**Records:** 0 | **Primary Key:** `template_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Fan engagement templates for algorithm boosting including DM farm, like farm, comment farm, and question prompts. Used to drive platform engagement and visibility.

**SKILL INTEGRATION:** Used in content selection for engagement campaigns. Selected via `all_schedulable_content` view. Filtered by `engagement_type` and `page_type_filter`.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| template_id | INTEGER | NO | - | Auto-increment primary key |
| template_hash | TEXT | NO | - | Unique hash for deduplication (UNIQUE) |
| template_text | TEXT | NO | - | Full template content |
| engagement_type | TEXT | NO | - | Type: dm_farm, like_farm, comment_farm, emoji_farm, question_prompt |
| incentive_description | TEXT | YES | - | Incentive offered for engagement |
| call_to_action | TEXT | YES | - | Specific CTA text |
| tone | TEXT | YES | - | Voice tone |
| emoji_style | TEXT | YES | - | Emoji usage |
| flyer_required | INTEGER | YES | 0 | Requires flyer/graphic (1=yes, 0=no) |
| is_active | INTEGER | YES | 1 | Active status |
| is_universal | INTEGER | YES | 1 | Universal template (defaults to universal) |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| avg_engagement_rate | REAL | YES | 0.0 | Average engagement rate |
| avg_response_count | INTEGER | YES | 0 | Average responses received |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'both' | 'paid', 'free', or 'both' |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(template_hash)
- CHECK (engagement_type IN ('dm_farm', 'like_farm', 'comment_farm', 'emoji_farm', 'question_prompt'))
- CHECK (page_type_filter IN ('paid', 'free', 'both'))
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**Triggers:**
- `trg_engagement_updated_at` - Auto-updates updated_at timestamp

**Key Indexes:**
- `idx_engagement_type` - engagement_type + is_active
- `idx_engagement_active` - is_active + page_type_filter
- `idx_engagement_selection` - is_active + engagement_type + freshness_score DESC + performance_score DESC (partial: is_active=1)

**DATA STATUS:** NEW (v3.0) - Empty, ready for population

---

### retention_templates

**Records:** 0 | **Primary Key:** `template_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Fan retention and win-back templates for churn prevention including renew-on posts/MMs, expired subscriber campaigns, and loyalty rewards. Used to maximize subscriber lifetime value.

**SKILL INTEGRATION:** Used in content selection for retention campaigns. Selected via `all_schedulable_content` view. Filtered by `retention_type`, `urgency_level`, and `page_type_filter`.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| template_id | INTEGER | NO | - | Auto-increment primary key |
| template_hash | TEXT | NO | - | Unique hash for deduplication (UNIQUE) |
| template_text | TEXT | NO | - | Full template content |
| retention_type | TEXT | NO | - | Type: renew_on_post, renew_on_mm, expired_subscriber, churn_prevention, winback, loyalty_reward |
| incentive_description | TEXT | YES | - | Incentive offered |
| discount_percentage | REAL | YES | 0.0 | Discount percentage (0-100) |
| urgency_level | TEXT | YES | 'medium' | Urgency: low, medium, high, critical |
| tone | TEXT | YES | - | Voice tone |
| emoji_style | TEXT | YES | - | Emoji usage |
| flyer_required | INTEGER | YES | 0 | Requires flyer/graphic (1=yes, 0=no) |
| is_active | INTEGER | YES | 1 | Active status |
| is_universal | INTEGER | YES | 1 | Universal template (defaults to universal) |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| avg_reactivation_rate | REAL | YES | 0.0 | Average reactivation rate |
| avg_revenue_recovered | REAL | YES | 0.0 | Average revenue recovered per use |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'paid' | 'paid', 'free', or 'both' (defaults to 'paid') |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(template_hash)
- CHECK (retention_type IN ('renew_on_post', 'renew_on_mm', 'expired_subscriber', 'churn_prevention', 'winback', 'loyalty_reward'))
- CHECK (urgency_level IN ('low', 'medium', 'high', 'critical'))
- CHECK (page_type_filter IN ('paid', 'free', 'both'))
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**Triggers:**
- `trg_retention_updated_at` - Auto-updates updated_at timestamp

**Key Indexes:**
- `idx_retention_type` - retention_type + is_active
- `idx_retention_active` - is_active + page_type_filter
- `idx_retention_urgency` - urgency_level + is_active (partial: is_active=1)
- `idx_retention_selection` - is_active + retention_type + freshness_score DESC + performance_score DESC (partial: is_active=1)

**DATA STATUS:** NEW (v3.0) - Empty, ready for population

---

### bump_variants

**Records:** 0 | **Primary Key:** `variant_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Follow-up bump message variants sent after PPV to increase conversion. Includes different bump types (flyer, descriptive, text-only) and styles (urgent, playful, seductive).

**SKILL INTEGRATION:** Used in **Step 6 (GENERATE FOLLOW-UPS)** to select bump message variants. Selected via `all_schedulable_content` view. Filtered by `bump_type`, `bump_style`, and `page_type_filter`.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| variant_id | INTEGER | NO | - | Auto-increment primary key |
| variant_hash | TEXT | NO | - | Unique hash for deduplication (UNIQUE) |
| variant_text | TEXT | NO | - | Full bump message content |
| bump_type | TEXT | NO | - | Type: flyer_gif, descriptive, text_only, normal, urgency, scarcity, social_proof |
| bump_style | TEXT | YES | 'standard' | Style: standard, playful, urgent, casual, seductive |
| flyer_required | INTEGER | YES | 0 | Requires flyer/graphic (1=yes, 0=no) |
| recommended_delay_minutes | INTEGER | YES | 30 | Recommended delay after PPV (minutes) |
| tone | TEXT | YES | - | Voice tone |
| emoji_style | TEXT | YES | - | Emoji usage |
| is_active | INTEGER | YES | 1 | Active status |
| is_universal | INTEGER | YES | 1 | Universal template (defaults to universal) |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| avg_conversion_lift | REAL | YES | 0.0 | Average conversion lift percentage |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'both' | 'paid', 'free', or 'both' |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(variant_hash)
- CHECK (bump_type IN ('flyer_gif', 'descriptive', 'text_only', 'normal', 'urgency', 'scarcity', 'social_proof'))
- CHECK (bump_style IN ('standard', 'playful', 'urgent', 'casual', 'seductive'))
- CHECK (page_type_filter IN ('paid', 'free', 'both'))
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**Triggers:**
- `trg_bump_variant_updated_at` - Auto-updates updated_at timestamp

**Key Indexes:**
- `idx_bump_type` - bump_type + is_active
- `idx_bump_active` - is_active + page_type_filter
- `idx_bump_style` - bump_style + is_active (partial: is_active=1)
- `idx_bump_selection` - is_active + bump_type + freshness_score DESC + performance_score DESC (partial: is_active=1)

**DATA STATUS:** NEW (v3.0) - Empty, ready for population

---

## Legacy Engagement Tables (v2.6)

### poll_bank

**Records:** 6 | **Primary Key:** `poll_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Poll and quiz content storage for interactive fan engagement.

**SKILL INTEGRATION:** Can be used for poll-based engagement campaigns. Selected via `all_schedulable_content` view.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| poll_id | INTEGER | NO | - | Auto-increment primary key |
| poll_hash | TEXT | NO | - | Unique hash for deduplication |
| poll_question | TEXT | NO | - | Poll question text |
| poll_options | TEXT | YES | - | JSON array of poll options |
| poll_type | TEXT | YES | 'standard' | Type: standard, quiz, prediction |
| tone | TEXT | YES | - | Voice tone |
| emoji_style | TEXT | YES | - | Emoji usage |
| is_active | INTEGER | YES | 1 | Active status |
| is_universal | INTEGER | YES | 0 | Universal poll |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| avg_engagement_rate | REAL | YES | 0.0 | Average engagement rate |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'both' | 'paid', 'free', or 'both' (NEW v3.0) |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(poll_hash)
- CHECK (page_type_filter IN ('paid', 'free', 'both'))
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**DATA STATUS:** NEW (v2.6) - 6 records populated

---

### free_preview_bank

**Records:** 10 | **Primary Key:** `preview_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Free preview content library for teaser campaigns and content previews.

**SKILL INTEGRATION:** Used for free preview campaigns. Selected via `all_schedulable_content` view.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| preview_id | INTEGER | NO | - | Auto-increment primary key |
| preview_hash | TEXT | NO | - | Unique hash for deduplication |
| preview_text | TEXT | NO | - | Preview text content |
| preview_type | TEXT | YES | 'teaser' | Type: teaser, sample, behind_the_scenes |
| tone | TEXT | YES | - | Voice tone |
| emoji_style | TEXT | YES | - | Emoji usage |
| is_active | INTEGER | YES | 1 | Active status |
| is_universal | INTEGER | YES | 0 | Universal preview |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| avg_conversion_rate | REAL | YES | 0.0 | Average conversion to full content |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'both' | 'paid', 'free', or 'both' (NEW v3.0) |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(preview_hash)
- CHECK (page_type_filter IN ('paid', 'free', 'both'))
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**DATA STATUS:** NEW (v2.6) - 10 records populated

---

### game_wheel_configs

**Records:** 0 | **Primary Key:** `config_id` (INTEGER AUTOINCREMENT)

**PURPOSE:** Spin-the-wheel game configurations for gamified engagement and prize wheels.

**SKILL INTEGRATION:** Can be used for game-based engagement campaigns. Selected via `all_schedulable_content` view.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| config_id | INTEGER | NO | - | Auto-increment primary key |
| config_hash | TEXT | NO | - | Unique hash for deduplication |
| wheel_description | TEXT | NO | - | Wheel description/rules |
| prize_tiers | TEXT | YES | - | JSON array of prize tiers |
| spin_cost | REAL | YES | 0.0 | Cost per spin |
| tone | TEXT | YES | - | Voice tone |
| emoji_style | TEXT | YES | - | Emoji usage |
| is_active | INTEGER | YES | 1 | Active status |
| is_universal | INTEGER | YES | 0 | Universal config |
| creator_id | TEXT | YES | - | FK to creators (NULL if universal) |
| times_used | INTEGER | YES | 0 | Usage count |
| avg_revenue_per_use | REAL | YES | 0.0 | Average revenue per use |
| performance_score | REAL | YES | 50.0 | Performance score (0-100) |
| freshness_score | REAL | YES | 100.0 | Freshness score (0-100) |
| page_type_filter | TEXT | YES | 'both' | 'paid', 'free', or 'both' (NEW v3.0) |
| last_used_date | TEXT | YES | - | Last used timestamp |
| created_at | TEXT | YES | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TEXT | YES | CURRENT_TIMESTAMP | Last update timestamp |

**Constraints:**
- UNIQUE(config_hash)
- CHECK (page_type_filter IN ('paid', 'free', 'both'))
- CHECK (performance_score >= 0 AND performance_score <= 100)
- CHECK (freshness_score >= 0 AND freshness_score <= 100)

**DATA STATUS:** NEW (v2.6) - Empty, ready for population

---

## Empty Tables (Not Yet Populated)

### schedule_templates

**Records:** 0

**PURPOSE:** Weekly schedule templates. Intended to store generated schedule metadata.

**SKILL INTEGRATION:** **NOT CURRENTLY USED** - The skill generates schedules on-demand without persisting templates.

| Key Columns | Description |
|-------------|-------------|
| template_id | Auto-increment primary key |
| creator_id | FK to creators |
| week_start | Week start date |
| week_end | Week end date |
| generated_at | Generation timestamp |
| total_items | Total scheduled items |
| status | 'draft', 'active', 'completed' |

---

### schedule_items

**Records:** 0

**PURPOSE:** Individual schedule entries. Intended to store each scheduled PPV/bump item.

**SKILL INTEGRATION:** **NOT CURRENTLY USED** - Schedule items are returned in-memory without persistence.

| Key Columns | Description |
|-------------|-------------|
| item_id | Auto-increment primary key |
| template_id | FK to schedule_templates |
| scheduled_date | Date |
| scheduled_time | Time |
| item_type | 'ppv', 'bump', 'drip' |
| caption_id | FK to caption_bank |
| suggested_price | Recommended price |

---

### volume_performance_tracking

**Records:** 0

**PURPOSE:** Volume optimization metrics. Intended to track saturation and opportunity signals.

**SKILL INTEGRATION:** **NOT CURRENTLY USED** - Could enable volume level auto-adjustment.

| Key Columns | Description |
|-------------|-------------|
| tracking_id | Auto-increment primary key |
| creator_id | FK to creators |
| tracking_date | Date |
| tracking_period | '7d', '14d', '30d' |
| saturation_score | 0-100 (>70 = reduce volume) |
| opportunity_score | 0-100 (>70 = increase volume) |

---

### caption_integrity_issues

**Records:** 0

**PURPOSE:** Data quality issue tracking. Intended to log caption problems and suggested fixes.

**SKILL INTEGRATION:** **NOT CURRENTLY USED** - Could enable data quality monitoring.

| Key Columns | Description |
|-------------|-------------|
| issue_id | Auto-increment primary key |
| caption_id | FK to caption_bank |
| issue_type | Type of issue |
| severity | 'critical', 'high', 'medium', 'low' |
| status | 'open', 'in_progress', 'resolved' |

---

## Views

### v_schedulable_creators

**PURPOSE:** Active creators ready for scheduling with volume and tier info.

**KEY COLUMNS:** `creator_id`, `page_name`, `display_name`, `page_type`, `current_active_fans`, `volume_level`, `tier_label`

**WHEN TO USE:** Quick lookup of which creators can be scheduled. Used by batch mode in generate_schedule.py.

---

### v_portfolio_summary

**PURPOSE:** Aggregate portfolio statistics across all creators.

**KEY COLUMNS:** `total_creators`, `active_creators`, `paid_pages`, `free_pages`, `total_earnings`, `total_fans`

**WHEN TO USE:** Dashboard summaries and portfolio health checks.

---

### v_top_captions

**PURPOSE:** Top performing active captions with all metadata.

**KEY COLUMNS:** `caption_id`, `caption_text`, `performance_score`, `freshness_score`, `type_name`, `tone`, `page_name`

**WHEN TO USE:** Finding best captions for manual analysis or debugging selection issues.

---

### v_caption_creator_stats

**PURPOSE:** Per-creator caption performance joined with metadata.

**KEY COLUMNS:** `creator_id`, `page_name`, `caption_id`, `caption_type`, `times_used`, `avg_earnings`, `performance_score`

**WHEN TO USE:** Analyzing which captions work best for specific creators.

---

### v_vault_summary

**PURPOSE:** Complete content inventory matrix by creator and type.

**KEY COLUMNS:** `creator_id`, `page_name`, `type_name`, `type_category`, `has_content`, `quantity_available`

**WHEN TO USE:** Checking content availability before schedule generation.

---

### v_stale_captions

**PURPOSE:** Captions below freshness threshold (< 30) that need rest.

**KEY COLUMNS:** `caption_id`, `caption_text`, `freshness_score`, `last_used_date`, `days_since_used`

**WHEN TO USE:** Identifying caption exhaustion. Check before `CaptionExhaustionError`.

---

### v_wall_post_performance

**PURPOSE:** Wall post analytics with timing data.

**KEY COLUMNS:** `post_id`, `page_name`, `post_type`, `view_count`, `total_earnings`, `posting_hour`

**WHEN TO USE:** Analyzing wall post timing patterns.

---

### v_wall_post_best_hours

**PURPOSE:** Optimal wall posting hours by post type.

**KEY COLUMNS:** `posting_hour`, `post_type`, `post_count`, `avg_earnings`, `total_earnings`

**WHEN TO USE:** Finding best times for wall posts.

---

### v_current_volume_assignments

**PURPOSE:** Active volume assignments with creator details.

**KEY COLUMNS:** `creator_id`, `page_name`, `volume_level`, `ppv_per_day`, `bump_per_day`, `current_active_fans`

**WHEN TO USE:** Checking current volume levels before schedule generation.

---

### v_performance_trends

**PURPOSE:** Latest performance trends per creator/period.

**KEY COLUMNS:** `creator_id`, `page_name`, `tracking_period`, `saturation_score`, `opportunity_score`

**WHEN TO USE:** Volume optimization analysis (requires volume_performance_tracking to be populated).

---

### v_volume_assignment_stats

**PURPOSE:** Volume level distribution statistics.

**KEY COLUMNS:** `volume_level`, `creator_count`, `avg_ppv_per_day`, `avg_current_active_fans`

**WHEN TO USE:** Portfolio volume distribution analysis.

---

### v_volume_recommendations

**PURPOSE:** Creators needing volume adjustments based on performance signals.

**KEY COLUMNS:** `creator_id`, `page_name`, `saturation_score`, `opportunity_score`, `recommended_volume_delta`

**WHEN TO USE:** Identifying volume optimization opportunities.

---

### v_creator_scheduler_lookup

**PURPOSE:** Maps creators to their assigned schedulers.

**KEY COLUMNS:** `page_name`, `creator_name`, `scheduler_name`, `tier`, `daily_ppv_target`

**WHEN TO USE:** Team coordination and workload distribution.

---

### v_scheduler_workload

**PURPOSE:** Scheduler workload summary with assigned creators.

**KEY COLUMNS:** `name`, `role`, `model_count`, `total_daily_ppv_target`, `assigned_creators`

**WHEN TO USE:** Scheduler capacity planning.

---

### v_tier_summary

**PURPOSE:** Assignment tier breakdown.

**KEY COLUMNS:** `tier`, `assignment_count`, `total_daily_ppv`, `creators`

**WHEN TO USE:** Tier distribution analysis.

---

### v_todays_schedule

**PURPOSE:** Today's pending schedule items.

**KEY COLUMNS:** `item_id`, `page_name`, `scheduled_time`, `item_type`, `type_name`, `scheduler_name`

**WHEN TO USE:** Daily schedule dashboard (requires schedule_items to be populated).

---

### v_todays_scheduler_tasks

**PURPOSE:** Active scheduler assignments for today.

**KEY COLUMNS:** `scheduler_name`, `creator_name`, `page_name`, `tier`, `daily_ppv_target`

**WHEN TO USE:** Daily task list for schedulers.

---

### all_schedulable_content (NEW v3.0)

**PURPOSE:** Single unified view across ALL schedulable content types for efficient content selection. Combines 10 different content sources into a single queryable interface.

**SOURCES:** caption_bank, vip_post_templates, tip_incentive_templates, link_drop_templates, engagement_templates, retention_templates, bump_variants, poll_bank, free_preview_bank

**KEY COLUMNS:**
- `content_id` - Unique identifier (primary key from source table)
- `source_table` - Origin table name (for tracking source)
- `content_hash` - Deduplication hash
- `content_text` - Full content text (caption_text, template_text, variant_text, etc.)
- `content_type` - Content type name (ppv, vip_post, tip_incentive, link_drop, engagement, retention, bump, poll, free_preview)
- `subtype` - Subtype (caption_type, incentive_type, bump_type, link_type, engagement_type, retention_type, poll_category, preview_type)
- `freshness_score` - 0-100 freshness (polls default to 100.0)
- `performance_score` - 0-100 performance
- `times_used` - Usage count
- `creator_id` - Creator ID (NULL if universal)
- `is_universal` - Universal flag (1=available to all creators)
- `tone` - Voice tone
- `emoji_style` - Emoji usage
- `page_type_filter` - 'paid', 'free', or 'both'
- `last_used_date` - Last used timestamp
- `created_at` - Creation timestamp

**WHEN TO USE:** Query all schedulable content with a single query. Used by content_type_loaders.py for unified content selection across all content types. Filters by is_active=1 in source tables.

**SQL Example:**
```sql
SELECT * FROM all_schedulable_content
WHERE is_active = 1
  AND (creator_id = ? OR is_universal = 1)
  AND freshness_score >= 30
  AND page_type_filter IN (?, 'both')
ORDER BY performance_score DESC, freshness_score DESC
LIMIT 500;
```

---

### v_content_type_availability (NEW v3.0)

**PURPOSE:** Shows content type availability metrics across all creators.

**KEY COLUMNS:** `content_type`, `total_available`, `universal_count`, `creator_specific_count`, `avg_freshness`, `avg_performance`

**WHEN TO USE:** Check content availability before scheduling. Identify content gaps.

---

### v_content_by_page_type (NEW v3.0)

**PURPOSE:** Content availability broken down by page type filter (paid/free/both).

**KEY COLUMNS:** `page_type_filter`, `content_type`, `count`, `avg_freshness`, `avg_performance`

**WHEN TO USE:** Filter content for paid vs free page scheduling. Analyze page-specific content distribution.

---

## Common Query Patterns

### Get creator by name (flexible search)
```sql
SELECT * FROM creators
WHERE page_name LIKE '%name%'
   OR display_name LIKE '%name%'
   OR creator_id = 'exact-uuid-here';
```

### Get PPV performance summary
```sql
SELECT creator_id,
       COUNT(*) as total_ppvs,
       SUM(earnings) as total_revenue,
       AVG(earnings) as avg_earnings,
       AVG(view_rate) as avg_view_rate,
       AVG(purchase_rate) as avg_purchase_rate,
       AVG(revenue_per_send) as avg_rps
FROM mass_messages
WHERE creator_id = ? AND message_type = 'ppv'
GROUP BY creator_id;
```

### Get best hours for creator (90-day lookback)
```sql
SELECT sending_hour,
       COUNT(*) as message_count,
       AVG(earnings) as avg_earnings,
       AVG(purchase_rate) as avg_purchase_rate
FROM mass_messages
WHERE creator_id = ?
  AND message_type = 'ppv'
  AND sending_time >= datetime('now', '-90 days')
GROUP BY sending_hour
HAVING COUNT(*) >= 3
ORDER BY avg_earnings DESC
LIMIT 10;
```

### Get schedulable captions with freshness filter
```sql
SELECT cb.caption_id, cb.caption_text, cb.performance_score,
       cb.freshness_score, ct.type_name, cb.tone
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
WHERE cb.is_active = 1
  AND cb.freshness_score >= 30
  AND (cb.creator_id = ? OR cb.is_universal = 1)
ORDER BY cb.performance_score DESC, cb.freshness_score DESC
LIMIT 500;
```

### Full caption selection query (as used by skill)
```sql
SELECT
    cb.caption_id, cb.caption_text, cb.caption_type,
    cb.content_type_id, ct.type_name AS content_type_name,
    cb.performance_score, cb.freshness_score,
    cb.tone, cb.emoji_style, cb.slang_level, cb.is_universal
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
LEFT JOIN vault_matrix vm ON cb.creator_id = vm.creator_id
    AND cb.content_type_id = vm.content_type_id
WHERE cb.is_active = 1
  AND (cb.creator_id = ? OR cb.is_universal = 1)
  AND cb.freshness_score >= ?
  AND (vm.has_content = 1 OR vm.vault_id IS NULL OR cb.content_type_id IS NULL)
ORDER BY cb.performance_score DESC, cb.freshness_score DESC
LIMIT 500;
```

### Query all schedulable content (v3.0 unified view)
```sql
SELECT content_id, source_table, content_text, content_type, subtype,
       performance_score, freshness_score, tone, page_type_filter
FROM all_schedulable_content
WHERE is_active = 1
  AND (creator_id = ? OR is_universal = 1)
  AND freshness_score >= 30
  AND page_type_filter IN (?, 'both')
ORDER BY performance_score DESC, freshness_score DESC;
```

### Get vault content availability
```sql
SELECT ct.type_name, vm.has_content, vm.quantity_available
FROM vault_matrix vm
JOIN content_types ct ON vm.content_type_id = ct.content_type_id
WHERE vm.creator_id = ?
  AND vm.has_content = 1
ORDER BY ct.priority_tier, ct.type_name;
```

### Get persona for matching
```sql
SELECT cp.primary_tone, cp.emoji_frequency, cp.slang_level, cp.avg_sentiment
FROM creator_personas cp
WHERE cp.creator_id = ?;
```

### Get top captions for creator
```sql
SELECT cb.caption_text, cb.performance_score, cb.freshness_score,
       ccp.times_used, ccp.avg_earnings
FROM caption_creator_performance ccp
JOIN caption_bank cb ON ccp.caption_id = cb.caption_id
WHERE ccp.creator_id = ?
ORDER BY ccp.avg_earnings DESC
LIMIT 10;
```

### Get content type performance
```sql
SELECT ct.type_name, ct.type_category,
       COUNT(mm.message_id) as uses,
       AVG(mm.earnings) as avg_earnings,
       AVG(mm.purchase_rate) as avg_purchase_rate
FROM mass_messages mm
JOIN content_types ct ON mm.content_type_id = ct.content_type_id
WHERE mm.creator_id = ? AND mm.message_type = 'ppv'
GROUP BY ct.content_type_id
ORDER BY avg_earnings DESC;
```

---

## Pipeline-Table Mapping (v3.0 - 9-Step)

| Pipeline Step | Tables Read | Tables Write | Purpose |
|---------------|-------------|--------------|---------|
| **1. ANALYZE** | `creators`, `creator_personas`, `mass_messages` | None | Load profile, persona, best hours |
| **2. MATCH CONTENT** | `caption_bank`, `vault_matrix`, `content_types`, `all_schedulable_content` | None | Filter content by vault and page_type_filter |
| **3. MATCH PERSONA** | `creator_personas` (from step 1) | None | Pattern/LLM tone matching, persona boost |
| **4. BUILD STRUCTURE** | `volume_assignments`, `creators` | None | Get volume level, create time slots with payday optimization |
| **5. ASSIGN CAPTIONS** | `caption_bank` (cached), `all_schedulable_content` | None | Pool-based Vose Alias weighted selection |
| **6. GENERATE FOLLOW-UPS** | `creator_personas` (cached), `bump_variants` | None | Context-aware bump messages (15-45 min) |
| **7. APPLY DRIP WINDOWS** | None | None | Enforce 4-8hr no-PPV zones (if enabled) |
| **8. APPLY PAGE TYPE RULES** | `creators` (cached) | None | page_type pricing rules (if enabled) |
| **9. VALIDATE** | None | None | Auto-correct issues, check rules, hook diversity |
| **Content Selection (v3.0)** | `all_schedulable_content` (unified view), `vip_post_templates`, `tip_incentive_templates`, `link_drop_templates`, `engagement_templates`, `retention_templates`, `bump_variants`, `poll_bank`, `free_preview_bank` | None | Unified content query across 10+ content sources |

**Mode Differences:**
- **Quick Mode**: Pattern-based persona matching in Step 3
- **Full Mode**: LLM-enhanced semantic tone detection in Step 3

---

## Data Quality Summary

### Critical Issues (Immediate Action Required)

| Issue | Table | Impact |
|-------|-------|--------|
| 45.4% NULL creator_id | mass_messages | Breaks creator-level analytics |
| 66.4% NULL caption_id | mass_messages | Prevents caption performance tracking |
| 68.1% NULL content_type_id | mass_messages | Limits content type analysis |
| 43.5% stale captions (freshness < 30) | caption_bank | Reduces scheduling options |
| All paid pages have $0 subscription | creators | Breaks revenue projections |

### Moderate Issues

| Issue | Table | Impact |
|-------|-------|--------|
| Missing 1 persona | creator_personas | lola_reese_new needs persona |
| Only 90d period populated | creator_analytics_summary | Missing 7d, 30d, all_time |
| All quantity_available = 0 | vault_matrix | Field unused |
| 84.7% low performance scores | caption_bank | May need scoring recalibration |
| 264 viewed > sent | mass_messages | Data import anomaly |

### Empty Tables

- `schedule_templates` - Not implemented
- `schedule_items` - Not implemented
- `volume_performance_tracking` - Not implemented
- `caption_integrity_issues` - Not implemented
- `vip_post_templates` - NEW (v3.0) - Ready for population
- `tip_incentive_templates` - NEW (v3.0) - Ready for population
- `link_drop_templates` - NEW (v3.0) - Ready for population
- `engagement_templates` - NEW (v3.0) - Ready for population
- `retention_templates` - NEW (v3.0) - Ready for population
- `bump_variants` - NEW (v3.0) - Ready for population
- `game_wheel_configs` - NEW (v2.6) - Ready for population

### Recommendations

1. **Backfill creator_id in mass_messages** using page_name join
2. **Create persona for lola_reese_new**
3. **Update paid page subscription prices** from OnlyFans data
4. **Run freshness recalculation** to address stale captions
5. **Review performance scoring algorithm** - avg score 10.8/100 seems low
6. **Populate v3.0 template tables** for 20+ content type support

---

## Version Information

| Metric | Value |
|--------|-------|
| Schema Version | 3.0 (with 20+ content type support) |
| Last Audited | 2025-12-09 |
| Total Tables | 36 |
| Total Views | 28 |
| Total Triggers | 21 |
| Total Indexes | 144+ |
| Database Size | ~80 MB |
| Total Records | ~90,000 |

**v3.0 Changes (December 2025):**
- **COLUMN ADDITIONS:**
  - Added `schedulable_type` column to `caption_bank` (ppv, ppv_follow_up, bundle, flash_bundle, etc.)
  - Added `page_type_filter` column to `poll_bank`, `free_preview_bank`, `game_wheel_configs` (paid, free, both)
- **NEW TEMPLATE TABLES (6 tables):**
  - `vip_post_templates` - VIP pricing page templates ($200+ price points, paid-only constraint)
  - `tip_incentive_templates` - First-to-tip, tip goals, tip menus, tip races
  - `link_drop_templates` - Campaign, wall post, PPV, bundle, promo link drops
  - `engagement_templates` - DM farm, like farm, comment farm, emoji farm, question prompts
  - `retention_templates` - Renew-on posts/MMs, expired subscriber, churn prevention, win-back, loyalty rewards
  - `bump_variants` - Follow-up bump variants (flyer_gif, descriptive, text_only, normal, urgency, scarcity, social_proof)
- **NEW VIEWS (3 views):**
  - `all_schedulable_content` - Unified view combining 10 content sources (caption_bank + 6 template tables + 3 legacy tables)
  - `v_content_type_availability` - Content type metrics (total, universal, creator-specific, avg freshness/performance)
  - `v_content_by_page_type` - Content distribution by page type filter
- **NEW TRIGGERS (6 triggers):**
  - `trg_vip_post_updated_at`, `trg_tip_incentive_updated_at`, `trg_link_drop_updated_at`
  - `trg_engagement_updated_at`, `trg_retention_updated_at`, `trg_bump_variant_updated_at`
- **NEW INDEXES (25+ indexes):**
  - Performance indexes on all 6 new template tables (is_active, page_type_filter, creator_id, selection indexes)
  - `idx_caption_schedulable_type` on caption_bank for schedulable_type filtering
- **SCHEMA VERSION:** Updated to 3.0 in schema_migrations table

**v2.6 Changes (December 2025):**
- Added `poll_bank` table for poll/quiz content storage
- Added `game_wheel_configs` table for spin-the-wheel configurations
- Added `free_preview_bank` table for free preview content library
- Added `caption_quality_feedback` table for user feedback
- Added `schedule_execution_log` table for execution tracking
- Added `creator_revenue_targets` table for revenue goals
- Added `content_performance_cache` table for metrics caching
- Added 3 new views: `v_caption_quality_summary`, `v_schedule_execution_status`, `v_revenue_vs_target`
- Fixed missing persona for lola_reese_new (35 -> 36 personas)

**v2.5 Changes (Pipeline v2.0 → v2.1):**
- Pool-based caption selection (PROVEN/GLOBAL_EARNER/DISCOVERY)
- New weight formula: `Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery(10%)`
- Payday optimization with multipliers (1st/15th = 1.15-1.20x)
- Hook diversity tracking and rotation
- Auto-correction for spacing/timing violations
- Timing variance (+/-7-10 min) for authentic scheduling

---

## Fixes Required (Audit: 2025-12-09)

> This section documents fixes identified during the comprehensive database audit.
> Priority: Critical > High > Medium > Low

### High Priority Fixes

#### 1. Standardize Tone Vocabulary

**Issue:** Mismatch between caption_bank tones and creator_personas reduces persona matching by ~15%

**Affected:** caption_bank.tone vs creator_personas.primary_tone

**SQL Fix:**
```sql
-- Update captions with 'aggressive' to 'dominant' (closest match)
UPDATE caption_bank
SET tone = 'dominant',
    updated_at = datetime('now')
WHERE tone = 'aggressive';

-- Update captions with 'direct' to NULL (neutral, no persona boost)
UPDATE caption_bank
SET tone = NULL,
    updated_at = datetime('now')
WHERE tone = 'direct';
```

#### 2. Mark Orphan Captions as Universal

**Issue:** 3,481 captions have no creator_id but aren't marked as universal

**SQL Fix:**
```sql
UPDATE caption_bank
SET is_universal = 1,
    updated_at = datetime('now')
WHERE creator_id IS NULL
  AND is_universal = 0;
```

### Medium Priority Fixes

#### 3. Populate 30-Day Analytics

**Issue:** Only 90-day period populated; 7d, 30d, all_time are missing

**SQL Fix:**
```sql
INSERT INTO creator_analytics_summary (
    creator_id, page_name, period_start, period_end,
    period_type, total_mass_messages, total_mm_earnings,
    avg_mm_earnings, avg_view_rate, avg_purchase_rate,
    calculated_at
)
SELECT
    creator_id,
    page_name,
    DATE('now', '-30 days') as period_start,
    DATE('now') as period_end,
    '30d' as period_type,
    COUNT(*) as total_mass_messages,
    SUM(earnings) as total_mm_earnings,
    AVG(earnings) as avg_mm_earnings,
    AVG(view_rate) as avg_view_rate,
    AVG(purchase_rate) as avg_purchase_rate,
    datetime('now') as calculated_at
FROM mass_messages
WHERE message_type = 'ppv'
  AND sending_time >= datetime('now', '-30 days')
  AND creator_id IS NOT NULL
GROUP BY creator_id;
```

#### 4. Add Tone-Based Caption Index

**Issue:** Caption selection queries can be faster with tone-aware index

**SQL Fix:**
```sql
CREATE INDEX IF NOT EXISTS idx_caption_tone_active
ON caption_bank(tone, is_active, freshness_score DESC)
WHERE is_active = 1 AND tone IS NOT NULL;
```

### Low Priority Fixes

#### 5. Review Volume Assignment Distribution

**Issue:** 32 Low, 4 Mid, 0 High, 0 Ultra - some creators may need upgrades

**SQL to Identify Candidates:**
```sql
SELECT
    c.page_name,
    c.current_active_fans,
    va.volume_level as current_level,
    CASE
        WHEN c.current_active_fans >= 15000 THEN 'Ultra'
        WHEN c.current_active_fans >= 5000 THEN 'High'
        WHEN c.current_active_fans >= 1000 THEN 'Mid'
        ELSE 'Low'
    END as recommended_level
FROM creators c
JOIN volume_assignments va ON c.creator_id = va.creator_id
WHERE va.is_active = 1
  AND (
    (c.current_active_fans >= 1000 AND va.volume_level = 'Low')
    OR (c.current_active_fans >= 5000 AND va.volume_level IN ('Low', 'Mid'))
    OR (c.current_active_fans >= 15000 AND va.volume_level != 'Ultra')
  );
```

### Resolved Issues (From Previous Audit)

- ~~Missing persona for lola_reese_new~~ **FIXED** (now has persona)
- Database integrity checks **PASSED**
- Foreign key constraints **VALID**
- All indexes **FUNCTIONAL**

---
