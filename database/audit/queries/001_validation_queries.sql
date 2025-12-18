-- ============================================
-- VALIDATION QUERIES: Content Type Classification
-- Plan ID: 001-CONTENT-TYPE-CLASSIFICATION
-- Created: 2025-12-12
-- ============================================

-- 1. Completeness Check
SELECT
    'Total Captions' as metric,
    COUNT(*) as count,
    100.0 as target_pct,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank), 2) as actual_pct
FROM caption_bank
UNION ALL
SELECT
    'Classified' as metric,
    COUNT(*) as count,
    100.0 as target_pct,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank), 2) as actual_pct
FROM caption_bank WHERE content_type_id IS NOT NULL
UNION ALL
SELECT
    'High Confidence (>=0.7)' as metric,
    COUNT(*) as count,
    95.0 as target_pct,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank), 2) as actual_pct
FROM caption_bank WHERE classification_confidence >= 0.7;

-- 2. Foreign Key Integrity
SELECT
    'Invalid FK References' as metric,
    COUNT(*) as count
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
WHERE cb.content_type_id IS NOT NULL AND ct.content_type_id IS NULL;

-- 3. Content Type Distribution
SELECT
    ct.type_name,
    ct.type_category,
    COUNT(cb.caption_id) as count,
    ROUND(100.0 * COUNT(cb.caption_id) / (SELECT COUNT(*) FROM caption_bank), 2) as pct
FROM caption_bank cb
JOIN content_types ct ON cb.content_type_id = ct.content_type_id
GROUP BY ct.type_name, ct.type_category
ORDER BY count DESC;

-- 4. Classification Method Distribution
SELECT
    classification_method,
    COUNT(*) as count,
    ROUND(AVG(classification_confidence), 3) as avg_confidence
FROM caption_bank
WHERE content_type_id IS NOT NULL
GROUP BY classification_method
ORDER BY count DESC;

-- 5. Confidence Tier Distribution
SELECT
    CASE
        WHEN classification_confidence >= 0.9 THEN 'High (0.9-1.0)'
        WHEN classification_confidence >= 0.7 THEN 'Medium (0.7-0.9)'
        WHEN classification_confidence >= 0.5 THEN 'Low (0.5-0.7)'
        ELSE 'Very Low (<0.5)'
    END as confidence_tier,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank), 2) as pct
FROM caption_bank
WHERE content_type_id IS NOT NULL
GROUP BY confidence_tier
ORDER BY MIN(classification_confidence) DESC;
