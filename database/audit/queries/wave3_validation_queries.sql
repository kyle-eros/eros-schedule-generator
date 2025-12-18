-- WAVE 3: Cross-Validation & Relationship Integrity
-- Validation Queries for Caption Bank Reclassification
-- Generated: 2025-12-15

-- ============================================================
-- VALIDATION 1: Content-Send Compatibility Check
-- ============================================================

-- Query 1.1: Full content_type x send_type distribution
SELECT
    cb.caption_type,
    ct.type_name as content_type,
    ct.type_category as content_category,
    st.category as send_category,
    COUNT(*) as count
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
LEFT JOIN send_types st ON cb.caption_type = st.send_type_key
WHERE cb.content_type_id IS NOT NULL
GROUP BY cb.caption_type, ct.type_name, ct.type_category, st.category
ORDER BY count DESC;

-- Query 1.2: Category-level compatibility summary
SELECT
    st.category as send_category,
    ct.type_category as content_category,
    COUNT(*) as combination_count,
    CASE
        WHEN st.category = 'retention' AND ct.type_category = 'engagement' AND ct.type_name = 'renewal_retention' THEN 'VALID'
        WHEN st.category = 'retention' AND st.send_type_key IN ('ppv_message', 'ppv_followup') THEN 'VALID'
        WHEN st.category = 'engagement' THEN 'VALID'
        WHEN st.category = 'revenue' THEN 'VALID'
        WHEN st.category = 'retention' AND ct.type_category IN ('promotional', 'engagement') THEN 'VALID'
        ELSE 'REVIEW'
    END as compatibility_status
FROM caption_bank cb
JOIN send_types st ON cb.caption_type = st.send_type_key
JOIN content_types ct ON cb.content_type_id = ct.content_type_id
GROUP BY st.category, ct.type_category
ORDER BY combination_count DESC;

-- ============================================================
-- VALIDATION 2: Page-Type Constraint Check
-- ============================================================

-- Query 2.1: Find retention sends assigned to free page creators (should return 0)
SELECT
    cb.caption_id,
    cb.caption_type,
    cb.creator_id,
    c.page_name,
    c.page_type,
    st.page_type_restriction,
    st.category as send_category
FROM caption_bank cb
JOIN creators c ON cb.creator_id = c.creator_id
JOIN send_types st ON cb.caption_type = st.send_type_key
WHERE st.page_type_restriction = 'paid'
  AND c.page_type = 'free';

-- Query 2.2: Page-type restriction distribution
SELECT
    cb.is_paid_page_only,
    st.page_type_restriction,
    COUNT(*) as count
FROM caption_bank cb
JOIN send_types st ON cb.caption_type = st.send_type_key
GROUP BY cb.is_paid_page_only, st.page_type_restriction;

-- Query 2.3: Retention send types by creator page type
SELECT
    c.page_type,
    st.send_type_key,
    st.page_type_restriction,
    COUNT(*) as caption_count
FROM caption_bank cb
JOIN creators c ON cb.creator_id = c.creator_id
JOIN send_types st ON cb.caption_type = st.send_type_key
WHERE st.category = 'retention'
GROUP BY c.page_type, st.send_type_key, st.page_type_restriction
ORDER BY c.page_type, caption_count DESC;

-- ============================================================
-- VALIDATION 3: Foreign Key Integrity Checks
-- ============================================================

-- Query 3.1: Orphaned content_type_id references (should return 0)
SELECT
    'content_type_id' as fk_column,
    COUNT(*) as orphaned_count
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
WHERE cb.content_type_id IS NOT NULL
  AND ct.content_type_id IS NULL;

-- Query 3.2: Orphaned caption_type references (should return 0)
SELECT
    'caption_type' as fk_column,
    COUNT(*) as orphaned_count,
    GROUP_CONCAT(DISTINCT cb.caption_type) as orphaned_values
FROM caption_bank cb
LEFT JOIN send_types st ON cb.caption_type = st.send_type_key
WHERE cb.caption_type IS NOT NULL
  AND st.send_type_key IS NULL;

-- Query 3.3: Orphaned creator_id references (should return 0)
SELECT
    'creator_id' as fk_column,
    COUNT(*) as orphaned_count,
    COUNT(DISTINCT cb.creator_id) as unique_orphaned_creators
FROM caption_bank cb
LEFT JOIN creators c ON cb.creator_id = c.creator_id
WHERE cb.creator_id IS NOT NULL
  AND c.creator_id IS NULL;

-- Query 3.4: Taxonomy usage summary
SELECT
    COUNT(DISTINCT ct.type_name) as content_types_used,
    COUNT(DISTINCT st.send_type_key) as send_types_used
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
LEFT JOIN send_types st ON cb.caption_type = st.send_type_key;

-- ============================================================
-- VALIDATION 4: Duplicate Detection
-- ============================================================

-- Query 4.1: Find duplicate captions with different classifications
SELECT
    cb1.caption_normalized,
    COUNT(DISTINCT cb1.caption_id) as duplicate_count,
    COUNT(DISTINCT cb1.caption_type) as different_caption_types,
    COUNT(DISTINCT cb1.content_type_id) as different_content_types,
    GROUP_CONCAT(DISTINCT cb1.caption_type) as caption_types,
    GROUP_CONCAT(DISTINCT cb1.content_type_id) as content_type_ids
FROM caption_bank cb1
WHERE cb1.caption_normalized IS NOT NULL
GROUP BY cb1.caption_normalized
HAVING COUNT(DISTINCT cb1.caption_id) > 1
   AND (COUNT(DISTINCT cb1.caption_type) > 1 OR COUNT(DISTINCT cb1.content_type_id) > 1)
ORDER BY duplicate_count DESC
LIMIT 100;

-- Query 4.2: Duplicate summary statistics
SELECT
    COUNT(*) as total_duplicate_groups
FROM (
    SELECT caption_normalized
    FROM caption_bank
    WHERE caption_normalized IS NOT NULL
    GROUP BY caption_normalized
    HAVING COUNT(DISTINCT caption_id) > 1
       AND (COUNT(DISTINCT caption_type) > 1 OR COUNT(DISTINCT content_type_id) > 1)
);

-- Query 4.3: Total captions affected by duplicates
SELECT
    SUM(dup_count) as total_affected_captions
FROM (
    SELECT COUNT(caption_id) as dup_count
    FROM caption_bank
    WHERE caption_normalized IN (
        SELECT caption_normalized
        FROM caption_bank
        WHERE caption_normalized IS NOT NULL
        GROUP BY caption_normalized
        HAVING COUNT(DISTINCT caption_id) > 1
           AND (COUNT(DISTINCT caption_type) > 1 OR COUNT(DISTINCT content_type_id) > 1)
    )
    GROUP BY caption_normalized
);

-- ============================================================
-- SUPPLEMENTARY: Classification Confidence Analysis
-- ============================================================

-- Query S.1: Confidence score distribution
SELECT
    AVG(classification_confidence) as avg_confidence,
    MIN(classification_confidence) as min_confidence,
    MAX(classification_confidence) as max_confidence,
    COUNT(CASE WHEN classification_confidence >= 0.7 THEN 1 END) as high_confidence_count,
    COUNT(CASE WHEN classification_confidence < 0.7 THEN 1 END) as low_confidence_count
FROM caption_bank
WHERE classification_confidence IS NOT NULL;

-- Query S.2: Classification method distribution
SELECT
    classification_method,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM caption_bank), 2) as percentage
FROM caption_bank
GROUP BY classification_method
ORDER BY count DESC;

-- Query S.3: NULL content_type analysis
SELECT
    caption_type,
    COUNT(*) as null_content_count
FROM caption_bank
WHERE content_type_id IS NULL
GROUP BY caption_type
ORDER BY null_content_count DESC;

-- ============================================================
-- WAVE 3 SUCCESS CRITERIA VERIFICATION
-- ============================================================

-- Final Check: All three criteria in one query
SELECT
    'Foreign Key Orphans' as criteria,
    (SELECT COUNT(*) FROM caption_bank cb
     LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
     WHERE cb.content_type_id IS NOT NULL AND ct.content_type_id IS NULL) +
    (SELECT COUNT(*) FROM caption_bank cb
     LEFT JOIN send_types st ON cb.caption_type = st.send_type_key
     WHERE cb.caption_type IS NOT NULL AND st.send_type_key IS NULL) +
    (SELECT COUNT(*) FROM caption_bank cb
     LEFT JOIN creators c ON cb.creator_id = c.creator_id
     WHERE cb.creator_id IS NOT NULL AND c.creator_id IS NULL) as value,
    0 as target,
    CASE WHEN (SELECT COUNT(*) FROM caption_bank cb
               LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
               WHERE cb.content_type_id IS NOT NULL AND ct.content_type_id IS NULL) = 0
         THEN 'PASS' ELSE 'FAIL' END as status
UNION ALL
SELECT
    'Retention Sends to Free Pages' as criteria,
    (SELECT COUNT(*) FROM caption_bank cb
     JOIN creators c ON cb.creator_id = c.creator_id
     JOIN send_types st ON cb.caption_type = st.send_type_key
     WHERE st.page_type_restriction = 'paid' AND c.page_type = 'free') as value,
    0 as target,
    CASE WHEN (SELECT COUNT(*) FROM caption_bank cb
               JOIN creators c ON cb.creator_id = c.creator_id
               JOIN send_types st ON cb.caption_type = st.send_type_key
               WHERE st.page_type_restriction = 'paid' AND c.page_type = 'free') = 0
         THEN 'PASS' ELSE 'FAIL' END as status;
