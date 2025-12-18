-- =============================================================================
-- EROS Database Weekly Health Check
-- =============================================================================
-- Purpose: Automated weekly data quality and health monitoring
-- Schedule: Run every Monday morning before business hours
-- Author: Database Administrator Agent (DBA-003)
--
-- USAGE:
--   sqlite3 database/eros_sd_main.db < database/audits/monitoring/weekly_health_check.sql
--
-- OUTPUT: JSON-formatted health report for alerting integration
-- =============================================================================

SELECT '{"health_check": {';
SELECT '"timestamp": "' || datetime('now') || '",';
SELECT '"database": "eros_sd_main.db",';

-- =============================================================================
-- SECTION 1: Database Size & Fragmentation
-- =============================================================================

SELECT '"storage": {';
SELECT '"page_size": ' || (SELECT page_size FROM pragma_page_size()) || ',';
SELECT '"total_pages": ' || (SELECT page_count FROM pragma_page_count()) || ',';
SELECT '"free_pages": ' || (SELECT freelist_count FROM pragma_freelist_count()) || ',';
SELECT '"fragmentation_pct": ' ||
       ROUND(100.0 * (SELECT freelist_count FROM pragma_freelist_count()) /
                     (SELECT page_count FROM pragma_page_count()), 2) || ',';
SELECT '"size_mb": ' ||
       ROUND((SELECT page_count FROM pragma_page_count()) *
             (SELECT page_size FROM pragma_page_size()) / 1024.0 / 1024.0, 2);
SELECT '},';

-- =============================================================================
-- SECTION 2: Table Row Counts (Trend Tracking)
-- =============================================================================

SELECT '"table_counts": {';
SELECT '"creators": ' || (SELECT COUNT(*) FROM creators) || ',';
SELECT '"caption_bank": ' || (SELECT COUNT(*) FROM caption_bank) || ',';
SELECT '"mass_messages": ' || (SELECT COUNT(*) FROM mass_messages) || ',';
SELECT '"wall_posts": ' || (SELECT COUNT(*) FROM wall_posts) || ',';
SELECT '"caption_creator_performance": ' || (SELECT COUNT(*) FROM caption_creator_performance) || ',';
SELECT '"vault_matrix": ' || (SELECT COUNT(*) FROM vault_matrix) || ',';
SELECT '"creator_personas": ' || (SELECT COUNT(*) FROM creator_personas) || ',';
SELECT '"scheduler_assignments": ' || (SELECT COUNT(*) FROM scheduler_assignments);
SELECT '},';

-- =============================================================================
-- SECTION 3: Data Quality Metrics
-- =============================================================================

SELECT '"data_quality": {';

-- FK Enforcement Check
SELECT '"fk_enforcement": ' || (SELECT foreign_keys FROM pragma_foreign_keys()) || ',';

-- creator_id Coverage
SELECT '"mm_creator_id_coverage_pct": ' ||
       ROUND(100.0 * (SELECT COUNT(*) FROM mass_messages WHERE creator_id IS NOT NULL) /
                     (SELECT COUNT(*) FROM mass_messages), 2) || ',';

-- Invalid page_names
SELECT '"mm_nan_page_names": ' || (SELECT COUNT(*) FROM mass_messages WHERE page_name = 'nan') || ',';

-- Impossible view rates
SELECT '"mm_impossible_view_rates": ' ||
       (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) || ',';

-- Negative sent_count
SELECT '"mm_negative_sent_count": ' ||
       (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0) || ',';

-- Creators without personas
SELECT '"creators_without_persona": ' ||
       (SELECT COUNT(*) FROM creators c LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id WHERE cp.creator_id IS NULL) || ',';

-- Creators without scheduler assignment
SELECT '"creators_without_scheduler": ' ||
       (SELECT COUNT(*) FROM creators c LEFT JOIN scheduler_assignments sa ON c.creator_id = sa.creator_id WHERE sa.creator_id IS NULL);

SELECT '},';

-- =============================================================================
-- SECTION 4: Data Freshness
-- =============================================================================

SELECT '"freshness": {';

-- Latest mass_message import
SELECT '"latest_mm_import": "' ||
       COALESCE((SELECT MAX(imported_at) FROM mass_messages), 'N/A') || '",';

-- Latest analytics update
SELECT '"latest_analytics_update": "' ||
       COALESCE((SELECT MAX(updated_at) FROM creator_analytics_summary), 'N/A') || '",';

-- Latest caption update
SELECT '"latest_caption_update": "' ||
       COALESCE((SELECT MAX(updated_at) FROM caption_bank), 'N/A') || '"';

SELECT '},';

-- =============================================================================
-- SECTION 5: Integrity Checks
-- =============================================================================

SELECT '"integrity": {';

-- Database integrity
SELECT '"integrity_check": "' || (SELECT integrity_check FROM pragma_integrity_check()) || '",';

-- Orphan creator_ids in mass_messages
SELECT '"mm_orphan_creator_ids": ' ||
       (SELECT COUNT(*) FROM mass_messages m
        WHERE m.creator_id IS NOT NULL
        AND m.creator_id NOT IN (SELECT creator_id FROM creators)) || ',';

-- Orphan creator_ids in caption_bank
SELECT '"cb_orphan_creator_ids": ' ||
       (SELECT COUNT(*) FROM caption_bank c
        WHERE c.creator_id IS NOT NULL
        AND c.creator_id NOT IN (SELECT creator_id FROM creators));

SELECT '},';

-- =============================================================================
-- SECTION 6: Overall Quality Score
-- =============================================================================

SELECT '"overall_quality_score": ' ||
(SELECT ROUND(SUM(score * weight) / SUM(weight), 2)
FROM (
    SELECT 0.0 as score, 25 as weight  -- FK disabled
    UNION ALL
    SELECT ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2), 20
    FROM mass_messages
    UNION ALL
    SELECT ROUND(100.0 * SUM(CASE WHEN freshness_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2), 15
    FROM caption_bank WHERE is_active = 1
    UNION ALL
    SELECT ROUND(100.0 * SUM(CASE WHEN performance_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2), 15
    FROM caption_bank
    UNION ALL
    SELECT ROUND(100.0 * SUM(CASE WHEN page_name IS NOT NULL AND display_name IS NOT NULL AND page_type IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2), 15
    FROM creators
    UNION ALL
    SELECT ROUND(100.0 * (1.0 - (
        (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) +
        (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0)
    ) / CAST((SELECT COUNT(*) FROM mass_messages) AS REAL)), 2), 10
));

SELECT '}}';

-- =============================================================================
-- SECTION 7: Alerts (Non-JSON for human review)
-- =============================================================================

SELECT '';
SELECT '-- ALERTS (if any):';

-- Alert: High fragmentation
SELECT CASE
    WHEN (SELECT freelist_count FROM pragma_freelist_count()) * 100.0 /
         (SELECT page_count FROM pragma_page_count()) > 20
    THEN '-- ALERT: Database fragmentation > 20%, recommend VACUUM'
    ELSE ''
END;

-- Alert: nan page_names reappeared
SELECT CASE
    WHEN (SELECT COUNT(*) FROM mass_messages WHERE page_name = 'nan') > 0
    THEN '-- ALERT: nan page_names detected (' ||
         (SELECT COUNT(*) FROM mass_messages WHERE page_name = 'nan') ||
         ' records), check import pipeline'
    ELSE ''
END;

-- Alert: Impossible view rates
SELECT CASE
    WHEN (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) > 0
    THEN '-- ALERT: Impossible view rates detected (' ||
         (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) ||
         ' records)'
    ELSE ''
END;

-- Alert: Creators without personas
SELECT CASE
    WHEN (SELECT COUNT(*) FROM creators c LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id WHERE cp.creator_id IS NULL) > 0
    THEN '-- ALERT: Creators without personas: ' ||
         (SELECT GROUP_CONCAT(page_name) FROM creators c LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id WHERE cp.creator_id IS NULL)
    ELSE ''
END;

-- Alert: Quality score dropped
SELECT CASE
    WHEN (SELECT ROUND(SUM(score * weight) / SUM(weight), 2)
          FROM (
              SELECT 0.0 as score, 25 as weight
              UNION ALL SELECT ROUND(100.0 * SUM(CASE WHEN creator_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2), 20 FROM mass_messages
              UNION ALL SELECT ROUND(100.0 * SUM(CASE WHEN freshness_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2), 15 FROM caption_bank WHERE is_active = 1
              UNION ALL SELECT ROUND(100.0 * SUM(CASE WHEN performance_score BETWEEN 0 AND 100 THEN 1 ELSE 0 END) / COUNT(*), 2), 15 FROM caption_bank
              UNION ALL SELECT ROUND(100.0 * SUM(CASE WHEN page_name IS NOT NULL AND display_name IS NOT NULL AND page_type IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2), 15 FROM creators
              UNION ALL SELECT ROUND(100.0 * (1.0 - ((SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0) + (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0)) / CAST((SELECT COUNT(*) FROM mass_messages) AS REAL)), 2), 10
          )) < 60
    THEN '-- ALERT: Quality score below 60%, review data quality issues'
    ELSE ''
END;

-- =============================================================================
-- END OF WEEKLY HEALTH CHECK
-- =============================================================================
