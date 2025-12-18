-- =============================================================================
-- EROS Database Anomaly Detection
-- =============================================================================
-- Purpose: Identify statistical anomalies and data quality issues
-- Author: Database Administrator Agent (DBA-003)
--
-- USAGE:
--   sqlite3 database/eros_sd_main.db < database/audits/monitoring/anomaly_detection.sql
--
-- This script checks for:
--   1. Statistical outliers in numeric fields
--   2. Impossible or illogical data combinations
--   3. Suspicious patterns that may indicate data corruption
--   4. Temporal anomalies
-- =============================================================================

SELECT '============================================';
SELECT 'EROS Database Anomaly Detection Report';
SELECT 'Generated: ' || datetime('now');
SELECT '============================================';
SELECT '';

-- =============================================================================
-- SECTION 1: Impossible Data Values
-- =============================================================================

SELECT '--- Impossible Data Values ---';
SELECT '';

-- View rate > 100% (viewed > sent)
SELECT 'Impossible view rates (viewed > sent): ' ||
       (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0);

-- Negative counts
SELECT 'Negative sent_count: ' || (SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0);
SELECT 'Negative viewed_count: ' || (SELECT COUNT(*) FROM mass_messages WHERE viewed_count < 0);
SELECT 'Negative purchased_count: ' || (SELECT COUNT(*) FROM mass_messages WHERE purchased_count < 0);
SELECT 'Negative earnings: ' || (SELECT COUNT(*) FROM mass_messages WHERE earnings < 0);

-- Times used negative or unreasonably high
SELECT 'Negative times_used: ' || (SELECT COUNT(*) FROM caption_bank WHERE times_used < 0);
SELECT 'times_used > 1000 (unusual): ' || (SELECT COUNT(*) FROM caption_bank WHERE times_used > 1000);

-- Scores out of valid range
SELECT 'freshness_score out of range: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE freshness_score < 0 OR freshness_score > 100);
SELECT 'performance_score out of range: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE performance_score < 0 OR performance_score > 100);

SELECT '';

-- =============================================================================
-- SECTION 2: Temporal Anomalies
-- =============================================================================

SELECT '--- Temporal Anomalies ---';
SELECT '';

-- first_used_date > last_used_date (impossible timeline)
SELECT 'Captions with first_used > last_used: ' ||
       (SELECT COUNT(*) FROM caption_bank
        WHERE first_used_date IS NOT NULL
        AND last_used_date IS NOT NULL
        AND first_used_date > last_used_date);

-- Messages with future dates
SELECT 'Messages with future sending_time: ' ||
       (SELECT COUNT(*) FROM mass_messages
        WHERE sending_time > datetime('now', '+1 day'));

-- Very old messages (pre-2020)
SELECT 'Messages before 2020 (possibly corrupted): ' ||
       (SELECT COUNT(*) FROM mass_messages
        WHERE sending_time < '2020-01-01'
        AND sending_time IS NOT NULL);

-- created_at > updated_at
SELECT 'Records with created_at > updated_at: ' ||
       (SELECT COUNT(*) FROM caption_bank
        WHERE created_at > updated_at
        AND created_at IS NOT NULL
        AND updated_at IS NOT NULL);

SELECT '';

-- =============================================================================
-- SECTION 3: Statistical Outliers
-- =============================================================================

SELECT '--- Statistical Outliers ---';
SELECT '';

-- Earnings outliers (> 3 standard deviations from mean)
SELECT 'Earnings statistics:';
SELECT '  Mean: $' || ROUND((SELECT AVG(earnings) FROM mass_messages WHERE earnings > 0), 2);
SELECT '  Max: $' || ROUND((SELECT MAX(earnings) FROM mass_messages), 2);
SELECT '  Stddev approx: $' || ROUND((SELECT AVG(earnings * earnings) - AVG(earnings) * AVG(earnings) FROM mass_messages WHERE earnings > 0), 2);

-- High earnings count
SELECT '  Messages > $1000: ' || (SELECT COUNT(*) FROM mass_messages WHERE earnings > 1000);
SELECT '  Messages > $5000: ' || (SELECT COUNT(*) FROM mass_messages WHERE earnings > 5000);
SELECT '  Messages > $10000 (review): ' || (SELECT COUNT(*) FROM mass_messages WHERE earnings > 10000);

SELECT '';

-- Purchase rate outliers
SELECT 'Purchase rate anomalies:';
SELECT '  purchase_rate > 100%: ' ||
       (SELECT COUNT(*) FROM mass_messages
        WHERE sent_count > 0 AND (100.0 * purchased_count / sent_count) > 100);

-- View rate distribution
SELECT 'View rate anomalies:';
SELECT '  view_rate > 100%: ' ||
       (SELECT COUNT(*) FROM mass_messages
        WHERE sent_count > 0 AND (100.0 * viewed_count / sent_count) > 100);

SELECT '';

-- =============================================================================
-- SECTION 4: Data Consistency Anomalies
-- =============================================================================

SELECT '--- Data Consistency Anomalies ---';
SELECT '';

-- Captions with usage but zero earnings
SELECT 'Captions used but total_earnings = 0: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE times_used > 0 AND total_earnings = 0);

-- Captions with earnings but no usage
SELECT 'Captions with earnings but times_used = 0: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE times_used = 0 AND total_earnings > 0);

-- Performance score = 50 (default) but has been used
SELECT 'Captions with default perf score (50) but used: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE times_used > 5 AND performance_score = 50.0);

-- Active captions with very old last_used_date
SELECT 'Active captions not used in 6+ months: ' ||
       (SELECT COUNT(*) FROM caption_bank
        WHERE is_active = 1
        AND last_used_date < datetime('now', '-6 months')
        AND last_used_date IS NOT NULL);

SELECT '';

-- =============================================================================
-- SECTION 5: String Data Anomalies
-- =============================================================================

SELECT '--- String Data Anomalies ---';
SELECT '';

-- Python 'nan' string leakage
SELECT 'page_name = nan: ' || (SELECT COUNT(*) FROM mass_messages WHERE page_name = 'nan');
SELECT 'caption_text contains nan: ' || (SELECT COUNT(*) FROM caption_bank WHERE caption_text LIKE '%nan%');

-- Empty strings instead of NULL
SELECT 'Empty page_name strings: ' ||
       (SELECT COUNT(*) FROM mass_messages WHERE page_name = '');
SELECT 'Empty caption_text: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE caption_text = '');

-- Very short captions (possibly truncated)
SELECT 'Captions < 10 chars: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE LENGTH(caption_text) < 10);

-- Very long captions (possibly concatenation errors)
SELECT 'Captions > 2000 chars: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE LENGTH(caption_text) > 2000);

SELECT '';

-- =============================================================================
-- SECTION 6: Duplicate Detection
-- =============================================================================

SELECT '--- Duplicate Detection ---';
SELECT '';

-- Duplicate caption hashes (should be unique)
SELECT 'Duplicate caption_hash count: ' ||
       (SELECT COUNT(*) - COUNT(DISTINCT caption_hash) FROM caption_bank);

-- Potential duplicate messages (same creator, time, earnings)
SELECT 'Potential duplicate messages (same creator/time/earnings): ' ||
       (SELECT COUNT(*) - COUNT(DISTINCT creator_id || '|' || sending_time || '|' || earnings)
        FROM mass_messages
        WHERE creator_id IS NOT NULL);

SELECT '';

-- =============================================================================
-- SECTION 7: Anomaly Summary
-- =============================================================================

SELECT '============================================';
SELECT 'ANOMALY DETECTION SUMMARY';
SELECT '============================================';

SELECT 'Critical anomalies (require immediate attention):';
SELECT '  - Impossible view rates: ' ||
       (SELECT COUNT(*) FROM mass_messages WHERE viewed_count > sent_count AND sent_count > 0);
SELECT '  - Negative values: ' ||
       ((SELECT COUNT(*) FROM mass_messages WHERE sent_count < 0) +
        (SELECT COUNT(*) FROM mass_messages WHERE earnings < 0) +
        (SELECT COUNT(*) FROM caption_bank WHERE times_used < 0));
SELECT '  - Score range violations: ' ||
       ((SELECT COUNT(*) FROM caption_bank WHERE freshness_score < 0 OR freshness_score > 100) +
        (SELECT COUNT(*) FROM caption_bank WHERE performance_score < 0 OR performance_score > 100));

SELECT '';
SELECT 'Warning anomalies (review recommended):';
SELECT '  - Temporal inconsistencies: ' ||
       (SELECT COUNT(*) FROM caption_bank WHERE first_used_date > last_used_date AND first_used_date IS NOT NULL AND last_used_date IS NOT NULL);
SELECT '  - String anomalies (nan/empty): ' ||
       ((SELECT COUNT(*) FROM mass_messages WHERE page_name = 'nan') +
        (SELECT COUNT(*) FROM mass_messages WHERE page_name = ''));
SELECT '  - Earnings outliers (>$10k): ' ||
       (SELECT COUNT(*) FROM mass_messages WHERE earnings > 10000);

SELECT '';
SELECT '============================================';

-- =============================================================================
-- END OF ANOMALY DETECTION
-- =============================================================================
