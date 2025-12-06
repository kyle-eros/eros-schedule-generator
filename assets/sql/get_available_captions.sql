-- get_available_captions.sql
-- Get fresh, high-performing captions for a creator filtered by vault availability.
--
-- Parameters:
--   :creator_id (TEXT)    - Creator UUID
--   :min_freshness (INT)  - Minimum freshness score (default 30)
--
-- Returns: Captions ordered by combined_score (performance * 0.6 + freshness * 0.4)
--
-- Performance optimizations:
--   - Uses idx_caption_creator_perf index
--   - Pre-filters by is_active in WHERE clause
--   - Joins vault_matrix to filter by content availability

SELECT
    cb.caption_id,
    cb.caption_text,
    cb.caption_type,
    cb.content_type_id,
    ct.type_name AS content_type_name,
    ct.type_category,
    cb.performance_score,
    cb.freshness_score,
    cb.avg_earnings,
    cb.avg_purchase_rate,
    cb.avg_view_rate,
    cb.times_used,
    cb.last_used_date,
    cb.performance_tier,
    cb.tone,
    cb.emoji_style,
    cb.slang_level,
    cb.is_universal,

    -- Combined score calculation: performance weighted 60%, freshness weighted 40%
    ROUND(
        (cb.performance_score * 0.6) + (cb.freshness_score * 0.4),
        2
    ) AS combined_score,

    -- Days since last used
    CASE
        WHEN cb.last_used_date IS NOT NULL
        THEN CAST(julianday('now') - julianday(cb.last_used_date) AS INTEGER)
        ELSE NULL
    END AS days_since_used,

    -- Vault availability for this content type
    vm.quantity_available AS vault_quantity,
    vm.has_content AS vault_has_content

FROM caption_bank cb
INNER JOIN content_types ct ON cb.content_type_id = ct.content_type_id
LEFT JOIN vault_matrix vm ON cb.creator_id = vm.creator_id
    AND cb.content_type_id = vm.content_type_id

WHERE
    cb.is_active = 1
    AND (
        cb.creator_id = :creator_id
        OR (cb.is_universal = 1 AND cb.creator_id IS NULL)
    )
    AND cb.freshness_score >= COALESCE(:min_freshness, 30)
    -- Only include if vault has content (or vault not tracked)
    AND (vm.has_content = 1 OR vm.vault_id IS NULL)

ORDER BY
    combined_score DESC,
    cb.performance_score DESC,
    cb.freshness_score DESC

LIMIT 500;
