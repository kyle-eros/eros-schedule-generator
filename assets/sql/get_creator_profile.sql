-- get_creator_profile.sql
-- Get complete creator profile for schedule generation with persona data joined.
--
-- Parameters:
--   :creator_name (TEXT) - page_name to look up
--   :creator_id (TEXT)   - alternative: direct creator_id lookup
--
-- Usage: Pass either :creator_name OR :creator_id (one should be NULL)
--
-- Returns: Single row with creator profile + persona data + volume level

SELECT
    c.creator_id,
    c.page_name,
    c.display_name,
    c.page_type,
    c.subscription_price,
    c.is_active,
    c.timezone,
    c.creator_group,
    c.current_active_fans,
    c.current_following,
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
    END AS volume_level,

    -- Persona data
    p.primary_tone,
    p.emoji_frequency,
    p.favorite_emojis,
    p.slang_level,
    p.avg_sentiment,
    p.avg_caption_length,
    p.last_analyzed AS persona_last_analyzed,

    -- Volume assignment (if exists)
    va.volume_level AS assigned_volume_level,
    va.assigned_at AS volume_assigned_at,
    va.assignment_reason AS volume_reason

FROM creators c
LEFT JOIN creator_personas p ON c.creator_id = p.creator_id
LEFT JOIN volume_assignments va ON c.creator_id = va.creator_id AND va.is_active = 1

WHERE
    (c.page_name = :creator_name OR :creator_name IS NULL)
    AND (c.creator_id = :creator_id OR :creator_id IS NULL)
    AND (c.page_name = :creator_name OR c.creator_id = :creator_id)

LIMIT 1;
