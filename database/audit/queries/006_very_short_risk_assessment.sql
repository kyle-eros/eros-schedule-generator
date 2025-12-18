-- Audit 006: Very Short Caption Risk Assessment
-- Purpose: Categorize 10-19 char captions by usage/earnings risk

SELECT
  CASE
    WHEN times_used = 0 THEN 'NEVER_USED'
    WHEN times_used > 0 AND total_earnings = 0 THEN 'USED_NO_EARNINGS'
    WHEN total_earnings > 0 AND total_earnings < 10 THEN 'LOW_EARNINGS'
    WHEN total_earnings >= 10 THEN 'DECENT_EARNINGS'
  END as risk_category,
  COUNT(*) as count,
  ROUND(AVG(LENGTH(caption_text)), 1) as avg_length,
  SUM(times_used) as total_uses,
  ROUND(SUM(total_earnings), 2) as total_earnings
FROM caption_bank
WHERE is_active = 1
  AND LENGTH(caption_text) >= 10
  AND LENGTH(caption_text) < 20
GROUP BY risk_category
ORDER BY
  CASE risk_category
    WHEN 'NEVER_USED' THEN 1
    WHEN 'USED_NO_EARNINGS' THEN 2
    WHEN 'LOW_EARNINGS' THEN 3
    WHEN 'DECENT_EARNINGS' THEN 4
  END;
