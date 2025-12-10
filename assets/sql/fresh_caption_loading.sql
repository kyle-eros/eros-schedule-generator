-- fresh_caption_loading.sql
-- Unified caption loading with hard 60-day exclusion based on mass_messages history.
--
-- This query implements the pool-based caption selection approach where freshness
-- is determined by actual send history (from mass_messages) rather than the static
-- freshness_score field in caption_bank.
--
-- Parameters:
--   :creator_id (TEXT)        - Creator UUID to load captions for
--   :exclusion_days (INT)     - Days since last send to exclude caption (default 60)
--   :content_type_ids (TEXT)  - Comma-separated content type IDs (expanded in query)
--   :limit (INT)              - Maximum captions to return (default 500)
--
-- Returns: Fresh captions with freshness tier assignment
--
-- Freshness Tiers:
--   - 'never_used'  : Caption has never been sent to this creator's page
--   - 'fresh'       : Caption was last sent > exclusion_days ago
--   - 'excluded'    : Caption was sent within exclusion window (filtered out)
--
-- Performance Optimizations:
--   - Uses idx_mass_messages_creator_time for recent_use subquery
--   - Materializes recent_use CTE to avoid repeated scans
--   - Filters exclusion in WHERE clause (not HAVING) for early filtering
--   - Orders by never_used first, then performance_score for optimal selection
--
-- Index Requirements:
--   - idx_mass_messages_creator_time ON mass_messages(creator_id, sending_time)
--   - idx_caption_bank_active_content ON caption_bank(is_active, content_type_id)
--
-- Example Usage:
--   -- Load fresh solo and sextape captions for creator
--   SELECT * FROM (
--     -- This query with :content_type_ids = '1,2'
--   )

WITH recent_use AS MATERIALIZED (
    -- Aggregate send history per caption for this creator
    -- Uses idx_mass_messages_creator_time for efficient creator filtering
    SELECT
        mm.caption_id,
        MAX(mm.sending_time) AS last_sent,
        COUNT(*) AS times_used,
        SUM(CASE WHEN mm.earnings > 0 THEN mm.earnings ELSE 0 END) AS total_earnings_on_page
    FROM mass_messages mm
    WHERE mm.creator_id = :creator_id
    GROUP BY mm.caption_id
)

SELECT
    cb.caption_id,
    cb.caption_text,
    cb.content_type_id,
    ct.type_name AS content_type_name,
    ct.type_category,
    cb.tone,
    cb.emoji_style AS hook_type,
    cb.slang_level,
    cb.performance_score,
    cb.freshness_score AS bank_freshness_score,  -- Static freshness from caption_bank
    cb.creator_id AS caption_creator_id,
    cb.is_universal,

    -- Dynamic freshness tier based on actual send history
    CASE
        WHEN ru.last_sent IS NULL THEN 'never_used'
        WHEN julianday('now') - julianday(ru.last_sent) > :exclusion_days THEN 'fresh'
        ELSE 'excluded'
    END AS freshness_tier,

    -- Boolean flags for sorting/filtering
    CASE WHEN ru.last_sent IS NULL THEN 1 ELSE 0 END AS never_used_on_page,

    -- Usage stats for this creator's page
    COALESCE(ru.times_used, 0) AS times_used_on_page,
    ru.last_sent AS last_sent_on_page,
    COALESCE(ru.total_earnings_on_page, 0.0) AS total_earnings_on_page,

    -- Days since last sent (NULL if never sent)
    CASE
        WHEN ru.last_sent IS NOT NULL
        THEN CAST(julianday('now') - julianday(ru.last_sent) AS INTEGER)
        ELSE NULL
    END AS days_since_sent,

    -- Combined selection score
    -- Prioritizes never-used captions, then high performers
    CASE
        WHEN ru.last_sent IS NULL THEN cb.performance_score + 100  -- +100 boost for never_used
        ELSE cb.performance_score
    END AS selection_priority

FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
LEFT JOIN recent_use ru ON cb.caption_id = ru.caption_id

WHERE
    cb.is_active = 1
    -- Filter by content types (caller should expand :content_type_ids to IN list)
    -- Example: AND cb.content_type_id IN (1, 2, 3)
    AND cb.content_type_id IN (:content_type_id_1, :content_type_id_2, :content_type_id_3,
                               :content_type_id_4, :content_type_id_5, :content_type_id_6,
                               :content_type_id_7, :content_type_id_8, :content_type_id_9,
                               :content_type_id_10)
    -- Match creator-specific or universal captions
    AND (cb.creator_id = :creator_id OR cb.is_universal = 1)
    -- Hard exclusion filter - must pass to be included
    AND (
        ru.last_sent IS NULL
        OR julianday('now') - julianday(ru.last_sent) > :exclusion_days
    )

ORDER BY
    -- Never-used captions first, then fresh
    CASE freshness_tier
        WHEN 'never_used' THEN 0
        WHEN 'fresh' THEN 1
    END,
    -- Within each tier, order by performance
    cb.performance_score DESC,
    -- Tie-breaker: prefer captions not used recently
    days_since_sent DESC NULLS FIRST

LIMIT :limit;


-- =============================================================================
-- Alternative: Single content type query (simpler, often faster)
-- =============================================================================
-- When loading for a single content type, use this simpler version:
--
-- WITH recent_use AS MATERIALIZED (
--     SELECT mm.caption_id, MAX(mm.sending_time) AS last_sent, COUNT(*) AS times_used
--     FROM mass_messages mm
--     WHERE mm.creator_id = :creator_id
--     GROUP BY mm.caption_id
-- )
-- SELECT cb.*, ru.last_sent, ru.times_used,
--     CASE WHEN ru.last_sent IS NULL THEN 'never_used'
--          WHEN julianday('now') - julianday(ru.last_sent) > 60 THEN 'fresh'
--          ELSE 'excluded' END AS freshness_tier
-- FROM caption_bank cb
-- LEFT JOIN recent_use ru ON cb.caption_id = ru.caption_id
-- WHERE cb.is_active = 1
--   AND cb.content_type_id = :content_type_id
--   AND (cb.creator_id = :creator_id OR cb.is_universal = 1)
--   AND (ru.last_sent IS NULL OR julianday('now') - julianday(ru.last_sent) > 60)
-- ORDER BY CASE WHEN ru.last_sent IS NULL THEN 0 ELSE 1 END, cb.performance_score DESC
-- LIMIT :limit;
