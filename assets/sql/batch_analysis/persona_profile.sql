-- persona_profile.sql
-- Phase 8: Persona & Voice Analysis
-- Creator persona profile with communication style metrics.
--
-- Parameters:
--   ? - creator_id (TEXT)
--
-- Returns: Complete persona profile with tone, emoji, slang, and sentiment data

SELECT
    c.page_name,
    c.display_name,
    c.page_type,
    c.persona_type,

    -- Core persona attributes
    cp.primary_tone,
    cp.emoji_frequency,
    cp.favorite_emojis,
    cp.slang_level,
    ROUND(cp.avg_sentiment, 2) AS avg_sentiment,
    cp.avg_caption_length,
    cp.last_analyzed AS persona_last_analyzed,

    -- Derived persona insights
    CASE cp.emoji_frequency
        WHEN 'heavy' THEN 'High visual engagement style'
        WHEN 'moderate' THEN 'Balanced communication style'
        WHEN 'light' THEN 'Text-focused communication'
        WHEN 'none' THEN 'Professional/minimal style'
        ELSE 'Unknown style'
    END AS emoji_insight,

    CASE cp.slang_level
        WHEN 'heavy' THEN 'Very casual, Gen-Z appeal'
        WHEN 'light' THEN 'Approachable, casual tone'
        WHEN 'none' THEN 'Professional, clean language'
        ELSE 'Standard language'
    END AS slang_insight,

    CASE
        WHEN cp.avg_sentiment > 0.5 THEN 'Very Positive'
        WHEN cp.avg_sentiment > 0.2 THEN 'Positive'
        WHEN cp.avg_sentiment > -0.2 THEN 'Neutral'
        WHEN cp.avg_sentiment > -0.5 THEN 'Negative'
        ELSE 'Very Negative'
    END AS sentiment_category,

    -- Caption length category
    CASE
        WHEN cp.avg_caption_length < 50 THEN 'Concise'
        WHEN cp.avg_caption_length < 100 THEN 'Medium'
        WHEN cp.avg_caption_length < 200 THEN 'Detailed'
        ELSE 'Long-form'
    END AS caption_length_category,

    -- Persona completeness score
    (
        CASE WHEN cp.primary_tone IS NOT NULL THEN 20 ELSE 0 END +
        CASE WHEN cp.emoji_frequency IS NOT NULL THEN 20 ELSE 0 END +
        CASE WHEN cp.favorite_emojis IS NOT NULL THEN 20 ELSE 0 END +
        CASE WHEN cp.slang_level IS NOT NULL THEN 20 ELSE 0 END +
        CASE WHEN cp.avg_sentiment IS NOT NULL THEN 20 ELSE 0 END
    ) AS persona_completeness_pct,

    -- Caption stats for this creator
    (
        SELECT COUNT(*)
        FROM caption_bank cb
        WHERE cb.creator_id = c.creator_id
          AND cb.is_active = 1
    ) AS creator_specific_captions,

    (
        SELECT COUNT(*)
        FROM caption_bank cb
        WHERE cb.is_universal = 1
          AND cb.is_active = 1
    ) AS universal_captions_available,

    -- Tone match stats
    (
        SELECT COUNT(*)
        FROM caption_bank cb
        WHERE (cb.creator_id = c.creator_id OR cb.is_universal = 1)
          AND cb.is_active = 1
          AND cb.tone = cp.primary_tone
    ) AS matching_tone_captions

FROM creators c
LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
WHERE c.creator_id = ?;
