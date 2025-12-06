-- get_active_creators.sql
-- Get all active creators for batch processing with volume level assignment.
--
-- Parameters: None required
--
-- Returns: All active creators with volume levels and key metrics
--
-- Performance optimizations:
--   - Uses idx_creators_active partial index
--   - Uses idx_creators_active_fans for sorting

SELECT
    c.creator_id,
    c.page_name,
    c.display_name,
    c.page_type,
    c.subscription_price,
    c.timezone,
    c.creator_group,
    c.current_active_fans,
    c.current_total_earnings,
    c.current_message_net,
    c.current_avg_spend_per_spender,
    c.current_avg_earnings_per_fan,
    c.current_of_ranking,
    c.performance_tier,
    c.metrics_snapshot_date,

    -- Volume level calculation based on fan count brackets
    CASE
        WHEN c.current_active_fans < 1000 THEN 'Low'
        WHEN c.current_active_fans < 5000 THEN 'Mid'
        WHEN c.current_active_fans < 15000 THEN 'High'
        ELSE 'Ultra'
    END AS calculated_volume_level,

    -- Assigned volume level (may override calculated)
    va.volume_level AS assigned_volume_level,
    va.assigned_at AS volume_assigned_at,
    va.assignment_reason,

    -- Effective volume level (assigned takes precedence)
    COALESCE(
        va.volume_level,
        CASE
            WHEN c.current_active_fans < 1000 THEN 'Low'
            WHEN c.current_active_fans < 5000 THEN 'Mid'
            WHEN c.current_active_fans < 15000 THEN 'High'
            ELSE 'Ultra'
        END
    ) AS effective_volume_level,

    -- Persona summary
    p.primary_tone,
    p.emoji_frequency,
    p.slang_level,

    -- Content availability summary
    (
        SELECT COUNT(*)
        FROM vault_matrix vm
        WHERE vm.creator_id = c.creator_id
            AND vm.has_content = 1
    ) AS content_types_available,

    -- Fresh caption count
    (
        SELECT COUNT(*)
        FROM caption_bank cb
        WHERE (cb.creator_id = c.creator_id OR cb.is_universal = 1)
            AND cb.is_active = 1
            AND cb.freshness_score >= 30
    ) AS fresh_captions_available,

    -- Last message date
    (
        SELECT MAX(mm.sending_time)
        FROM mass_messages mm
        WHERE mm.creator_id = c.creator_id
    ) AS last_message_date,

    -- Messages sent in last 30 days
    (
        SELECT COUNT(*)
        FROM mass_messages mm
        WHERE mm.creator_id = c.creator_id
            AND mm.sending_time >= datetime('now', '-30 days')
    ) AS messages_last_30_days

FROM creators c
LEFT JOIN volume_assignments va ON c.creator_id = va.creator_id AND va.is_active = 1
LEFT JOIN creator_personas p ON c.creator_id = p.creator_id

WHERE c.is_active = 1

ORDER BY
    c.current_active_fans DESC,
    c.current_total_earnings DESC;
