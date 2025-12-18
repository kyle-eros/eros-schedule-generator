-- Audit 006: Short Caption Performance Distribution
-- Purpose: Analyze performance by length range (20-49 chars)

SELECT
  CASE
    WHEN LENGTH(caption_text) < 25 THEN '20-24 chars'
    WHEN LENGTH(caption_text) < 30 THEN '25-29 chars'
    WHEN LENGTH(caption_text) < 35 THEN '30-34 chars'
    WHEN LENGTH(caption_text) < 40 THEN '35-39 chars'
    WHEN LENGTH(caption_text) < 45 THEN '40-44 chars'
    ELSE '45-49 chars'
  END as length_range,
  COUNT(*) as count,
  ROUND(AVG(performance_score), 2) as avg_perf,
  ROUND(AVG(times_used), 2) as avg_uses,
  ROUND(AVG(total_earnings), 2) as avg_earnings,
  COUNT(CASE WHEN times_used = 0 THEN 1 END) as never_used
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) >= 20
  AND LENGTH(caption_text) < 50
GROUP BY length_range
ORDER BY MIN(LENGTH(caption_text));
