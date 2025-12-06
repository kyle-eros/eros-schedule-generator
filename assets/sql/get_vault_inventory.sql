-- get_vault_inventory.sql
-- Get content availability by type for a creator with fresh caption counts.
--
-- Parameters:
--   :creator_id (TEXT) - Creator UUID
--
-- Returns: Content type inventory with vault availability and caption stats
--
-- Performance optimizations:
--   - Uses idx_vault_creator and idx_vault_has_content indexes
--   - Subquery uses idx_caption_creator_perf for fresh caption counts

SELECT
    vm.content_type_id,
    ct.type_name,
    ct.type_category,
    ct.priority_tier,
    ct.is_explicit,
    vm.has_content,
    vm.quantity_available,
    vm.quality_rating,
    vm.notes AS vault_notes,
    vm.updated_at AS vault_updated_at,

    -- Count of fresh captions available for this content type
    (
        SELECT COUNT(*)
        FROM caption_bank cb
        WHERE (cb.creator_id = :creator_id OR (cb.is_universal = 1 AND cb.creator_id IS NULL))
            AND cb.content_type_id = vm.content_type_id
            AND cb.is_active = 1
            AND cb.freshness_score >= 30
    ) AS fresh_caption_count,

    -- Count of high-performing captions (score >= 70)
    (
        SELECT COUNT(*)
        FROM caption_bank cb
        WHERE (cb.creator_id = :creator_id OR (cb.is_universal = 1 AND cb.creator_id IS NULL))
            AND cb.content_type_id = vm.content_type_id
            AND cb.is_active = 1
            AND cb.performance_score >= 70
    ) AS high_performer_count,

    -- Average performance score for this content type
    (
        SELECT ROUND(AVG(cb.performance_score), 1)
        FROM caption_bank cb
        WHERE (cb.creator_id = :creator_id OR (cb.is_universal = 1 AND cb.creator_id IS NULL))
            AND cb.content_type_id = vm.content_type_id
            AND cb.is_active = 1
    ) AS avg_content_type_performance,

    -- Scheduling readiness flag
    CASE
        WHEN vm.has_content = 1
            AND vm.quantity_available > 0
            AND (
                SELECT COUNT(*)
                FROM caption_bank cb
                WHERE (cb.creator_id = :creator_id OR (cb.is_universal = 1 AND cb.creator_id IS NULL))
                    AND cb.content_type_id = vm.content_type_id
                    AND cb.is_active = 1
                    AND cb.freshness_score >= 30
            ) > 0
        THEN 1
        ELSE 0
    END AS ready_to_schedule

FROM vault_matrix vm
INNER JOIN content_types ct ON vm.content_type_id = ct.content_type_id

WHERE vm.creator_id = :creator_id

ORDER BY
    ct.priority_tier ASC,
    vm.quantity_available DESC,
    ct.type_name ASC;
