-- =============================================================================
-- Migration 019: Caption Bank Rebuild v2.0
--
-- Purpose: Rebuild caption_bank with lean schema (37 → 17 columns)
-- - Remove 23 unused/bloated columns
-- - Add price tracking (suggested_price, price_range_min, price_range_max)
-- - Add generated char_length column
-- - Normalize performance data to mass_messages (source of truth)
--
-- Created: 2025-12-22
-- =============================================================================

-- Drop caption_bank_v2 if it exists from previous failed migration
DROP TABLE IF EXISTS caption_bank_v2;

-- =============================================================================
-- NEW CAPTION_BANK SCHEMA (v2.0)
-- Lean caption storage with proper classification
-- Performance data normalized to caption_creator_performance and mass_messages
-- =============================================================================

CREATE TABLE caption_bank_v2 (
    -- Primary Key
    caption_id INTEGER PRIMARY KEY,

    -- Core Caption Data (REQUIRED)
    caption_text TEXT NOT NULL,
    caption_hash TEXT NOT NULL UNIQUE,  -- For deduplication (SHA256 of normalized text)

    -- Classification (REQUIRED - 100% accuracy target)
    caption_type TEXT NOT NULL,  -- Maps to send_type_caption_requirements (ppv_message, bump_normal, etc.)
    content_type_id INTEGER NOT NULL,  -- FK to content_types - describes scene/content

    -- Scheduling Eligibility
    schedulable_type TEXT CHECK (schedulable_type IN ('ppv', 'ppv_bump', 'wall')),
    is_paid_page_only INTEGER NOT NULL DEFAULT 0,  -- 1 = paid page exclusive (retention sends)
    is_active INTEGER NOT NULL DEFAULT 1,  -- Soft delete flag

    -- Performance Tier (based on earnings/engagement)
    performance_tier INTEGER NOT NULL DEFAULT 3 CHECK (performance_tier BETWEEN 1 AND 4),
    -- Tier 1: ELITE (PPV >= $500 OR view_rate >= 40%)
    -- Tier 2: PROVEN (PPV >= $200 OR view_rate >= 30%)
    -- Tier 3: STANDARD (PPV >= $100 OR view_rate >= 25%)
    -- Tier 4: UNPROVEN (new/insufficient data)

    -- Price Guidance (NEW - Essential for PPV analytics)
    suggested_price REAL,  -- Median/average price used for this caption
    price_range_min REAL,  -- Observed minimum price
    price_range_max REAL,  -- Observed maximum price

    -- Character Length (auto-calculated for optimal length filtering)
    -- Optimal range: 250-449 chars = +107.6% RPS
    char_length INTEGER GENERATED ALWAYS AS (length(caption_text)) STORED,

    -- Classification Confidence
    classification_confidence REAL NOT NULL DEFAULT 0.5
        CHECK (classification_confidence >= 0 AND classification_confidence <= 1),
    classification_method TEXT NOT NULL DEFAULT 'unknown',
    -- Values: 'keyword', 'structural', 'llm', 'manual', 'imported'

    -- Freshness Tracking (global usage across all creators)
    -- Per-creator freshness tracked in caption_creator_performance
    global_times_used INTEGER NOT NULL DEFAULT 0,
    global_last_used_date TEXT,

    -- Source Performance (aggregated from mass_messages)
    total_earnings REAL DEFAULT 0.0,  -- Lifetime earnings across all uses
    total_sends INTEGER DEFAULT 0,  -- Total times sent
    avg_view_rate REAL DEFAULT 0.0,  -- Average view rate
    avg_purchase_rate REAL DEFAULT 0.0,  -- Average purchase rate (PPV only)

    -- Audit Trail
    source TEXT DEFAULT 'mass_messages_rebuild',  -- Origin: 'mass_messages_rebuild', 'manual', 'import'
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign Key Constraint
    FOREIGN KEY (content_type_id) REFERENCES content_types(content_type_id)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Primary selection query index (caption_type + content_type + active + tier)
CREATE INDEX idx_cb2_selection ON caption_bank_v2(
    caption_type, content_type_id, performance_tier, is_active
) WHERE is_active = 1;

-- Content type filtering (vault matrix joins)
CREATE INDEX idx_cb2_content_type ON caption_bank_v2(content_type_id)
WHERE is_active = 1;

-- Performance tier filtering
CREATE INDEX idx_cb2_tier ON caption_bank_v2(performance_tier)
WHERE is_active = 1;

-- Freshness-based selection (prioritize unused/less used)
CREATE INDEX idx_cb2_freshness ON caption_bank_v2(
    global_last_used_date, global_times_used
) WHERE is_active = 1;

-- Price-based filtering for PPV scheduling
CREATE INDEX idx_cb2_price_range ON caption_bank_v2(
    suggested_price, schedulable_type
) WHERE schedulable_type = 'ppv' AND is_active = 1;

-- Character length optimization (optimal 250-449 chars)
CREATE INDEX idx_cb2_char_length ON caption_bank_v2(
    char_length, caption_type
) WHERE is_active = 1;

-- Caption hash for fast deduplication lookups
CREATE UNIQUE INDEX idx_cb2_hash ON caption_bank_v2(caption_hash);

-- Classification method tracking
CREATE INDEX idx_cb2_classification ON caption_bank_v2(
    classification_method, classification_confidence
);

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Auto-update updated_at timestamp on any modification
CREATE TRIGGER trg_cb2_update_timestamp
AFTER UPDATE ON caption_bank_v2
FOR EACH ROW
BEGIN
    UPDATE caption_bank_v2
    SET updated_at = datetime('now')
    WHERE caption_id = NEW.caption_id;
END;

-- Freshness decay trigger - reduce freshness score on usage
-- (Actual freshness calculation done in caption_creator_performance for per-creator tracking)
CREATE TRIGGER trg_cb2_usage_update
AFTER UPDATE OF global_times_used ON caption_bank_v2
FOR EACH ROW
WHEN NEW.global_times_used > OLD.global_times_used
BEGIN
    UPDATE caption_bank_v2
    SET global_last_used_date = datetime('now')
    WHERE caption_id = NEW.caption_id;
END;

-- =============================================================================
-- PERFORMANCE VIEW (calculated from mass_messages source of truth)
-- =============================================================================

CREATE VIEW IF NOT EXISTS v_caption_performance_summary AS
SELECT
    cb.caption_id,
    cb.caption_text,
    cb.caption_type,
    ct.type_name as content_type,
    cb.performance_tier,
    cb.char_length,
    cb.suggested_price,
    cb.total_earnings,
    cb.total_sends,
    cb.avg_view_rate,
    cb.avg_purchase_rate,
    cb.global_times_used,
    cb.global_last_used_date,
    cb.classification_confidence,
    cb.classification_method,
    -- Freshness score (100 = never used, decreases with usage)
    CASE
        WHEN cb.global_last_used_date IS NULL THEN 100.0
        ELSE MAX(0.0, 100.0 - (julianday('now') - julianday(cb.global_last_used_date)) * 2)
    END as freshness_score,
    -- Composite quality score for selection ranking
    (
        -- Performance component (40%)
        (CASE cb.performance_tier
            WHEN 1 THEN 40
            WHEN 2 THEN 30
            WHEN 3 THEN 20
            ELSE 10
        END) +
        -- Length component (20%) - optimal 250-449
        (CASE
            WHEN cb.char_length BETWEEN 250 AND 449 THEN 20
            WHEN cb.char_length BETWEEN 200 AND 599 THEN 15
            WHEN cb.char_length BETWEEN 100 AND 199 THEN 10
            ELSE 5
        END) +
        -- Freshness component (25%)
        (CASE
            WHEN cb.global_last_used_date IS NULL THEN 25
            WHEN julianday('now') - julianday(cb.global_last_used_date) > 30 THEN 20
            WHEN julianday('now') - julianday(cb.global_last_used_date) > 14 THEN 15
            WHEN julianday('now') - julianday(cb.global_last_used_date) > 7 THEN 10
            ELSE 5
        END) +
        -- Classification confidence (15%)
        (cb.classification_confidence * 15)
    ) as quality_score
FROM caption_bank_v2 cb
JOIN content_types ct ON cb.content_type_id = ct.content_type_id
WHERE cb.is_active = 1;

-- =============================================================================
-- MIGRATION NOTES
-- =============================================================================
--
-- This migration creates caption_bank_v2 alongside the existing caption_bank.
-- Data will be migrated from mass_messages (source of truth) in subsequent steps:
--
-- 1. Extract qualifying PPV captions (earnings >= $100, sent >= 500)
-- 2. Extract qualifying free captions (view_rate >= 25%, sent >= 500)
-- 3. Deduplicate (exact + near-duplicate detection)
-- 4. Classify content_type using keyword patterns
-- 5. Classify send_type using structural detection
-- 6. LLM classification for low-confidence captions
-- 7. Backfill price data from mass_messages
-- 8. Validate with random sample
-- 9. Rename tables: caption_bank → caption_bank_legacy, caption_bank_v2 → caption_bank
--
-- After 90 days, caption_bank_legacy will be archived and deleted.
-- =============================================================================
