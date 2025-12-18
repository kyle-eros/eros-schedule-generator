-- Audit 006: Cleanup Candidates
-- Purpose: Identify captions safe to deactivate (zero risk)

SELECT
  caption_id,
  caption_text,
  LENGTH(caption_text) as len,
  times_used,
  total_earnings,
  performance_score,
  source,
  created_at,
  CASE
    WHEN LENGTH(caption_text) < 10 AND times_used = 0
      THEN 'EMOJI_DEADWEIGHT'
    WHEN LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 AND times_used = 0
      THEN 'VERY_SHORT_NEVER_USED'
    WHEN LENGTH(caption_text) >= 10 AND LENGTH(caption_text) < 20 AND total_earnings = 0 AND times_used > 0
      THEN 'VERY_SHORT_NO_EARNINGS'
    WHEN LENGTH(caption_text) < 20 AND performance_score < 40 AND times_used > 0 AND times_used < 3 AND total_earnings > 0
      THEN 'VERY_SHORT_LOW_PERFORMANCE_WITH_EARNINGS'
    WHEN LENGTH(caption_text) < 20 AND performance_score < 40
      THEN 'VERY_SHORT_LOW_PERFORMANCE'
  END as cleanup_reason
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 20
  AND (
    times_used = 0
    OR (times_used > 0 AND total_earnings = 0)
    OR (performance_score < 40 AND times_used < 3)
  )
  AND (creator_id IS NULL OR creator_id = '')
ORDER BY LENGTH(caption_text), times_used DESC;
