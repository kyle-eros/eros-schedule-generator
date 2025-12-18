-- Audit 006: Emoji-Only Caption Analysis
-- Purpose: Identify <10 char captions (emoji teasers) and assess cleanup risk

SELECT
  caption_text,
  LENGTH(caption_text) as len,
  times_used,
  total_earnings,
  performance_score,
  source,
  CASE
    WHEN times_used >= 3 AND total_earnings >= 50 THEN 'PRESERVE - High Performer'
    WHEN times_used > 0 THEN 'PRESERVE - Has Usage'
    ELSE 'CLEANUP CANDIDATE'
  END as recommendation,
  created_at,
  last_used_date
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 10
ORDER BY total_earnings DESC, times_used DESC;
