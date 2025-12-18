-- Audit 006: Content Type Analysis
-- Purpose: Analyze short captions by content type distribution

SELECT
  COALESCE(ct.type_name, cb.caption_type, 'UNCLASSIFIED') as content_type,
  CASE
    WHEN LENGTH(cb.caption_text) < 10 THEN 'emoji_only'
    WHEN LENGTH(cb.caption_text) < 20 THEN 'very_short'
    WHEN LENGTH(cb.caption_text) < 50 THEN 'short'
    ELSE 'normal'
  END as length_category,
  COUNT(*) as count,
  ROUND(AVG(cb.performance_score), 2) as avg_perf,
  SUM(cb.times_used) as total_uses,
  ROUND(SUM(cb.total_earnings), 2) as total_earnings
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
WHERE cb.is_active = 1
GROUP BY content_type, length_category
HAVING length_category IN ('emoji_only', 'very_short', 'short')
ORDER BY content_type, MIN(LENGTH(cb.caption_text));
