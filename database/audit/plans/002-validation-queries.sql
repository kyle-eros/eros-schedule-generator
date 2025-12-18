-- ============================================================================
-- TONE CLASSIFICATION BACKFILL - VALIDATION QUERIES
-- Phase 3A: Statistical Validation
-- Date: 2025-12-12
-- ============================================================================

-- Query 1: Verify zero NULL tones
-- Expected: 0 (all captions should have tone assigned)
SELECT 'Query 1: NULL Tone Count' as query_name;
SELECT COUNT(*) as null_count FROM caption_bank WHERE tone IS NULL;

-- Query 2: Tone distribution with confidence and performance metrics
-- Shows distribution of all 6 valid tones with quality metrics
SELECT 'Query 2: Tone Distribution with Confidence' as query_name;
SELECT
    tone,
    COUNT(*) as count,
    ROUND(AVG(classification_confidence), 2) as avg_confidence,
    ROUND(AVG(performance_score), 2) as avg_performance
FROM caption_bank
GROUP BY tone
ORDER BY count DESC;

-- Query 3: Confidence distribution in ranges
-- Success criteria: 80%+ should have confidence >= 0.70
SELECT 'Query 3: Confidence Distribution' as query_name;
SELECT
  CASE
    WHEN classification_confidence >= 0.90 THEN '0.90-1.00'
    WHEN classification_confidence >= 0.80 THEN '0.80-0.89'
    WHEN classification_confidence >= 0.70 THEN '0.70-0.79'
    WHEN classification_confidence >= 0.60 THEN '0.60-0.69'
    ELSE '0.00-0.59'
  END as confidence_range,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM caption_bank), 2) as percentage
FROM caption_bank
WHERE tone IS NOT NULL
GROUP BY confidence_range
ORDER BY confidence_range DESC;

-- Query 4: Invalid tones check
-- Expected: Empty result (no invalid tone values)
SELECT 'Query 4: Invalid Tones Check' as query_name;
SELECT tone, COUNT(*) as count
FROM caption_bank
WHERE tone NOT IN ('seductive', 'aggressive', 'playful', 'submissive', 'dominant', 'bratty')
  AND tone IS NOT NULL
GROUP BY tone;

-- Query 5: Classification method breakdown
-- Shows effectiveness of each classification tier
SELECT 'Query 5: Classification Method Breakdown' as query_name;
SELECT
    classification_method,
    COUNT(*) as count,
    ROUND(AVG(classification_confidence), 2) as avg_confidence,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM caption_bank WHERE tone IS NOT NULL), 2) as percentage
FROM caption_bank
WHERE tone IS NOT NULL AND classification_method IS NOT NULL
GROUP BY classification_method
ORDER BY count DESC;

-- Query 6: Performance correlation by tier and tone
-- Analyzes relationship between performance and tone classification
SELECT 'Query 6: Performance Correlation' as query_name;
SELECT
  CASE
    WHEN performance_score >= 70 THEN 'High (70+)'
    WHEN performance_score >= 40 THEN 'Mid (40-69)'
    ELSE 'Low/NULL (<40)'
  END as performance_tier,
  tone,
  COUNT(*) as count,
  ROUND(AVG(classification_confidence), 3) as avg_confidence
FROM caption_bank
WHERE tone IS NOT NULL
GROUP BY performance_tier, tone
ORDER BY performance_tier, count DESC;

-- Query 7: Summary statistics
-- Overall validation summary
SELECT 'Query 7: Summary Statistics' as query_name;
SELECT
    COUNT(*) as total_captions,
    SUM(CASE WHEN tone IS NOT NULL THEN 1 ELSE 0 END) as with_tone,
    SUM(CASE WHEN tone IS NULL THEN 1 ELSE 0 END) as without_tone,
    ROUND(AVG(CASE WHEN tone IS NOT NULL THEN classification_confidence ELSE NULL END), 3) as overall_avg_confidence,
    SUM(CASE WHEN classification_confidence >= 0.70 THEN 1 ELSE 0 END) as high_confidence_count,
    ROUND(SUM(CASE WHEN classification_confidence >= 0.70 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as high_confidence_pct
FROM caption_bank;

-- Query 8: Classification tier effectiveness comparison
-- Compares Tier 1 (high-confidence), Tier 2 (text analysis), Tier 3 (defaults)
SELECT 'Query 8: Tier Effectiveness Comparison' as query_name;
SELECT
    CASE
        WHEN classification_method LIKE '%tier1%' OR classification_method LIKE '%high%' THEN 'Tier 1: High Confidence'
        WHEN classification_method LIKE '%tier2%' OR classification_method LIKE '%text%' OR classification_method LIKE '%pattern%' THEN 'Tier 2: Text Analysis'
        WHEN classification_method LIKE '%tier3%' OR classification_method LIKE '%default%' THEN 'Tier 3: Default'
        ELSE 'Other/Unknown'
    END as tier,
    COUNT(*) as count,
    ROUND(AVG(classification_confidence), 3) as avg_confidence,
    ROUND(AVG(performance_score), 2) as avg_performance
FROM caption_bank
WHERE tone IS NOT NULL
GROUP BY tier
ORDER BY tier;

-- Query 9: Before vs After comparison (if baseline available)
-- Compares current state with baseline metrics
SELECT 'Query 9: Current vs Baseline Comparison' as query_name;
SELECT
    'Current State' as snapshot,
    COUNT(*) as total,
    SUM(CASE WHEN tone IS NOT NULL THEN 1 ELSE 0 END) as with_tone,
    SUM(CASE WHEN tone IS NULL THEN 1 ELSE 0 END) as null_tone,
    ROUND(AVG(classification_confidence), 3) as avg_confidence
FROM caption_bank;

-- ============================================================================
-- END OF VALIDATION QUERIES
-- ============================================================================
