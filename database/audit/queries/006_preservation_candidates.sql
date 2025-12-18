-- Audit 006: Preservation Candidates
-- Purpose: Identify short captions with proven performance to KEEP

SELECT
  caption_text,
  LENGTH(caption_text) as len,
  times_used,
  total_earnings,
  performance_score,
  ROUND(total_earnings / NULLIF(times_used, 0), 2) as earnings_per_use,
  creator_id,
  page_name,
  last_used_date,
  CASE
    WHEN LENGTH(caption_text) < 10 THEN 'Emoji Teaser'
    WHEN LENGTH(caption_text) < 20 THEN 'Very Short Teaser'
    ELSE 'Short Teaser'
  END as teaser_type
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) < 50
  AND (
    total_earnings >= 50
    OR (times_used >= 5 AND performance_score >= 60)
    OR (total_earnings / NULLIF(times_used, 0) >= 30)
  )
ORDER BY total_earnings DESC, times_used DESC
LIMIT 100;
