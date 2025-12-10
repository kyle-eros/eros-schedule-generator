-- fresh_selection_indexes.sql
-- Optimized indexes for fresh caption selection and pattern extraction.
--
-- Created: 2025-12-10
-- Purpose: Support pool-based caption selection with 60-day exclusion window
--
-- These indexes optimize:
-- 1. Pattern extraction queries (build_pattern_profile)
-- 2. Fresh caption loading queries (fresh_caption_loading.sql)
-- 3. Caption creator performance lookups
--
-- IMPORTANT: Run ANALYZE after creating indexes to update query planner statistics.
-- Example: ANALYZE mass_messages; ANALYZE caption_bank;


-- =============================================================================
-- MASS MESSAGES INDEXES
-- =============================================================================

-- Index for pattern extraction: creator + time range + earnings filter
-- Covers the common WHERE clause: creator_id = ? AND sending_time >= ? AND earnings > 0
-- The existing idx_mass_messages_creator_time handles (creator_id, sending_time) but
-- this index adds earnings for better filtering before join.
CREATE INDEX IF NOT EXISTS idx_mm_creator_time_earnings
ON mass_messages(creator_id, sending_time, earnings)
WHERE creator_id IS NOT NULL AND earnings > 0;
-- Purpose: Optimizes pattern extraction with earnings filter
-- Estimated improvement: Avoids post-filter on earnings after index scan


-- Index for fresh caption loading: creator + caption_id for recent_use lookup
-- Critical for the GROUP BY caption_id subquery in fresh_caption_loading.sql
-- The existing idx_mass_messages_creator_time doesn't include caption_id
CREATE INDEX IF NOT EXISTS idx_mm_creator_caption
ON mass_messages(creator_id, caption_id, sending_time DESC)
WHERE creator_id IS NOT NULL;
-- Purpose: Optimizes recent_use CTE: GROUP BY caption_id, MAX(sending_time)
-- Estimated improvement: Reduces GROUP BY sort operations


-- Covering index for global pattern extraction (no creator filter)
-- When building global portfolio patterns, we scan all messages
-- This partial index only includes messages with earnings > 0 within 90 days
CREATE INDEX IF NOT EXISTS idx_mm_global_patterns
ON mass_messages(content_type_id, caption_id, sending_time, earnings)
WHERE earnings > 0
  AND sending_time >= datetime('now', '-90 days');
-- Purpose: Optimizes global pattern extraction without creator filter
-- Note: This index may need periodic recreation as time window moves
-- Alternative: Use a simpler non-partial index if recreation is undesirable


-- =============================================================================
-- CAPTION BANK INDEXES
-- =============================================================================

-- Index for fresh caption loading: active + content_type + performance ordering
-- Optimizes the main caption query with content type filtering
-- Existing idx_caption_selection is (is_active, content_type_id, caption_type, ...)
-- but includes caption_type which we may not filter on
CREATE INDEX IF NOT EXISTS idx_caption_fresh_selection
ON caption_bank(is_active, content_type_id, creator_id, performance_score DESC)
WHERE is_active = 1;
-- Purpose: Optimizes fresh_caption_loading.sql main query
-- Estimated improvement: Better ordering for LIMIT queries


-- Index for creator-specific + universal caption lookup
-- Covers the common OR condition: (creator_id = ? OR is_universal = 1)
CREATE INDEX IF NOT EXISTS idx_caption_creator_or_universal
ON caption_bank(content_type_id, is_active, creator_id)
WHERE is_active = 1;
-- Purpose: Supports the creator/universal OR condition in WHERE clause
-- Used with content_type_id as leading column for IN (...) queries


-- Index for caption tone/emoji_style lookups in pattern matching
-- Pattern extraction joins on caption_id and needs tone/emoji_style attributes
CREATE INDEX IF NOT EXISTS idx_caption_pattern_attrs
ON caption_bank(caption_id, tone, emoji_style)
WHERE is_active = 1 AND tone IS NOT NULL AND emoji_style IS NOT NULL;
-- Purpose: Covering index for pattern extraction caption lookups
-- Avoids table lookup when only tone/emoji_style needed after caption_id join


-- =============================================================================
-- CAPTION CREATOR PERFORMANCE INDEXES
-- =============================================================================

-- Index for per-page caption performance lookups
-- When we need to know how a caption performed on a specific creator's page
CREATE INDEX IF NOT EXISTS idx_ccp_creator_caption
ON caption_creator_performance(creator_id, caption_id, times_used DESC);
-- Purpose: Fast lookup of caption usage on specific page
-- Supports alternative freshness checking via caption_creator_performance


-- Index for finding top captions per creator
CREATE INDEX IF NOT EXISTS idx_ccp_creator_earnings
ON caption_creator_performance(creator_id, total_earnings DESC)
WHERE times_used >= 1;
-- Purpose: Query top-earning captions for a creator
-- Supports creator analysis and caption selection fallback


-- =============================================================================
-- CONTENT TYPES INDEXES
-- =============================================================================

-- Content types is small (typically <20 rows), but this index helps joins
CREATE INDEX IF NOT EXISTS idx_content_types_name
ON content_types(type_name);
-- Purpose: Fast lookup by type_name when joining pattern results


-- =============================================================================
-- MAINTENANCE QUERIES
-- =============================================================================

-- After creating indexes, update query planner statistics:
-- ANALYZE mass_messages;
-- ANALYZE caption_bank;
-- ANALYZE caption_creator_performance;

-- To check index usage:
-- .expert ON
-- <run your query>
-- .expert OFF

-- To see index sizes:
-- SELECT name, stat FROM sqlite_stat1 WHERE tbl = 'mass_messages';
-- SELECT name, stat FROM sqlite_stat1 WHERE tbl = 'caption_bank';


-- =============================================================================
-- INDEX VERIFICATION QUERIES
-- =============================================================================

-- Verify indexes exist after running this script:
-- SELECT name, sql FROM sqlite_master
-- WHERE type = 'index'
-- AND (name LIKE 'idx_mm_%' OR name LIKE 'idx_caption_%' OR name LIKE 'idx_ccp_%')
-- ORDER BY name;

-- Check for unused indexes (run after production usage):
-- SELECT * FROM sqlite_stat1 WHERE tbl = 'mass_messages';
