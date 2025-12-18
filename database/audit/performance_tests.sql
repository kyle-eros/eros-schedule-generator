-- EROS Schedule Generator Performance Test Suite
-- Generated: 2025-12-15
-- Purpose: Comprehensive performance analysis of database queries

-- =============================================================================
-- 1. INDEX VERIFICATION TESTS
-- =============================================================================

-- Check all required indexes on schedule_items
.print "=== INDEX VERIFICATION ==="
.print ""
SELECT
    'schedule_items indexes' AS test,
    COUNT(*) AS index_count
FROM sqlite_master
WHERE type = 'index'
AND tbl_name = 'schedule_items';

-- Verify specific required indexes
SELECT
    name AS index_name,
    CASE
        WHEN name IN (
            'idx_schedule_items_send_type',
            'idx_schedule_items_channel_id',
            'idx_schedule_items_target',
            'idx_schedule_items_parent'
        ) THEN 'REQUIRED - PRESENT'
        ELSE 'additional'
    END AS status
FROM sqlite_master
WHERE type = 'index'
AND tbl_name = 'schedule_items'
ORDER BY status DESC, name;

.print ""
.print "=== FOREIGN KEY INDEXES ==="
SELECT
    m.name AS table_name,
    COUNT(DISTINCT i.name) AS index_count
FROM sqlite_master m
LEFT JOIN sqlite_master i ON i.tbl_name = m.name AND i.type = 'index'
WHERE m.type = 'table'
AND m.name IN ('schedule_items', 'send_types', 'channels', 'audience_targets',
               'send_type_caption_requirements', 'send_type_content_compatibility')
GROUP BY m.name
ORDER BY m.name;

-- =============================================================================
-- 2. QUERY PERFORMANCE TESTS - MCP TOOL QUERIES
-- =============================================================================

.print ""
.print "=== MCP TOOL QUERY PERFORMANCE ==="
.print ""

-- Test 1: get_send_types query with filtering
.print "Test 1: get_send_types with category filter"
.timer ON
EXPLAIN QUERY PLAN
SELECT
    send_type_id,
    send_type_key,
    category,
    display_name,
    requires_media,
    requires_price,
    has_expiration,
    can_have_followup
FROM send_types
WHERE is_active = 1
AND category = 'revenue'
AND page_type_restriction IN ('paid', 'both')
ORDER BY sort_order;

-- Execute actual query to measure time
SELECT
    send_type_id,
    send_type_key,
    category,
    display_name
FROM send_types
WHERE is_active = 1
AND category = 'revenue'
AND page_type_restriction IN ('paid', 'both')
ORDER BY sort_order
LIMIT 5;
.timer OFF

.print ""
.print "Test 2: get_send_type_captions with JOIN"
.timer ON
EXPLAIN QUERY PLAN
SELECT
    st.send_type_key,
    st.display_name,
    cb.caption_id,
    cb.caption_text,
    cb.caption_type,
    cb.eros_score
FROM send_types st
JOIN send_type_caption_requirements scr ON st.send_type_id = scr.send_type_id
JOIN caption_bank cb ON scr.caption_type = cb.caption_type
WHERE st.send_type_key = 'ppv_video'
AND cb.is_active = 1
AND cb.is_schedulable = 1
ORDER BY cb.eros_score DESC
LIMIT 10;
.timer OFF

.print ""
.print "Test 3: get_volume_config extended query"
.timer ON
EXPLAIN QUERY PLAN
SELECT
    c.creator_id,
    c.page_name,
    c.page_type,
    va.assigned_volume,
    va.effective_date,
    vo.override_level,
    st.send_type_key,
    st.category
FROM creators c
LEFT JOIN volume_assignments va ON c.creator_id = va.creator_id
LEFT JOIN volume_overrides vo ON c.creator_id = vo.creator_id AND vo.is_active = 1
LEFT JOIN send_types st ON st.is_active = 1
WHERE c.is_active = 1
AND c.creator_id = 'CID001';
.timer OFF

.print ""
.print "Test 4: save_schedule insert performance simulation"
.timer ON
EXPLAIN QUERY PLAN
INSERT INTO schedule_items (
    template_id, creator_id, scheduled_date, scheduled_time,
    item_type, channel, send_type_id, channel_id, target_id,
    caption_id, content_type_id, suggested_price,
    media_type, campaign_goal, status
) VALUES (
    1, 'CID001', '2025-12-16', '10:00:00',
    'PPV', 'mass_message', 1, 1, 1,
    1, 1, 29.99,
    'video', 500.00, 'pending'
);

-- Rollback the insert
ROLLBACK;
.timer OFF

-- =============================================================================
-- 3. VIEW PERFORMANCE TESTS
-- =============================================================================

.print ""
.print "=== VIEW PERFORMANCE ANALYSIS ==="
.print ""

.print "Test 5: v_schedule_items_full query plan"
.timer ON
EXPLAIN QUERY PLAN
SELECT * FROM v_schedule_items_full
WHERE creator_id = 'CID001'
AND scheduled_date >= date('now')
ORDER BY scheduled_datetime
LIMIT 20;
.timer OFF

.print ""
.print "Test 6: v_schedule_items_full with send_type filter"
.timer ON
EXPLAIN QUERY PLAN
SELECT
    item_id,
    scheduled_datetime,
    send_type_name,
    channel_name,
    target_name,
    caption_text
FROM v_schedule_items_full
WHERE send_type_key = 'ppv_video'
AND status = 'pending'
ORDER BY scheduled_datetime;
.timer OFF

-- =============================================================================
-- 4. COMPLEX JOIN PERFORMANCE
-- =============================================================================

.print ""
.print "=== COMPLEX JOIN PERFORMANCE ==="
.print ""

.print "Test 7: Caption selection with send_type compatibility"
.timer ON
EXPLAIN QUERY PLAN
SELECT
    cb.caption_id,
    cb.caption_text,
    cb.caption_type,
    cb.eros_score,
    st.send_type_key,
    ct.content_type_name
FROM caption_bank cb
JOIN send_type_caption_requirements scr ON cb.caption_type = scr.caption_type
JOIN send_types st ON scr.send_type_id = st.send_type_id
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
WHERE cb.creator_id = 'CID001'
AND cb.is_active = 1
AND cb.is_schedulable = 1
AND st.send_type_key = 'ppv_video'
AND cb.last_used_date < date('now', '-7 days')
ORDER BY cb.eros_score DESC
LIMIT 10;
.timer OFF

.print ""
.print "Test 8: Multi-table schedule building query"
.timer ON
EXPLAIN QUERY PLAN
SELECT
    si.item_id,
    si.scheduled_datetime,
    c.page_name,
    st.display_name AS send_type,
    ch.display_name AS channel,
    at.display_name AS target,
    cb.caption_text,
    ct.content_type_name
FROM schedule_items si
JOIN creators c ON si.creator_id = c.creator_id
LEFT JOIN send_types st ON si.send_type_id = st.send_type_id
LEFT JOIN channels ch ON si.channel_id = ch.channel_id
LEFT JOIN audience_targets at ON si.target_id = at.target_id
LEFT JOIN caption_bank cb ON si.caption_id = cb.caption_id
LEFT JOIN content_types ct ON si.content_type_id = ct.content_type_id
WHERE si.scheduled_date BETWEEN date('now') AND date('now', '+7 days')
AND si.status = 'pending'
ORDER BY si.scheduled_datetime;
.timer OFF

-- =============================================================================
-- 5. AGGREGATION PERFORMANCE
-- =============================================================================

.print ""
.print "=== AGGREGATION PERFORMANCE ==="
.print ""

.print "Test 9: Schedule statistics by send_type"
.timer ON
EXPLAIN QUERY PLAN
SELECT
    st.send_type_key,
    st.category,
    COUNT(*) AS item_count,
    AVG(si.suggested_price) AS avg_price,
    SUM(si.campaign_goal) AS total_goal
FROM schedule_items si
JOIN send_types st ON si.send_type_id = st.send_type_id
WHERE si.scheduled_date >= date('now')
AND si.status = 'pending'
GROUP BY st.send_type_key, st.category
ORDER BY item_count DESC;
.timer OFF

.print ""
.print "Test 10: Creator schedule density analysis"
.timer ON
EXPLAIN QUERY PLAN
SELECT
    c.creator_id,
    c.page_name,
    COUNT(si.item_id) AS scheduled_count,
    COUNT(DISTINCT si.scheduled_date) AS active_days,
    COUNT(DISTINCT st.category) AS category_variety
FROM creators c
LEFT JOIN schedule_items si ON c.creator_id = si.creator_id
    AND si.scheduled_date >= date('now')
    AND si.status = 'pending'
LEFT JOIN send_types st ON si.send_type_id = st.send_type_id
WHERE c.is_active = 1
GROUP BY c.creator_id, c.page_name
HAVING scheduled_count > 0
ORDER BY scheduled_count DESC;
.timer OFF

-- =============================================================================
-- 6. DATA VOLUME STATISTICS
-- =============================================================================

.print ""
.print "=== DATA VOLUME STATISTICS ==="
.print ""

SELECT 'Total schedule_items' AS metric, COUNT(*) AS count FROM schedule_items
UNION ALL
SELECT 'Pending items', COUNT(*) FROM schedule_items WHERE status = 'pending'
UNION ALL
SELECT 'Items with send_type_id', COUNT(*) FROM schedule_items WHERE send_type_id IS NOT NULL
UNION ALL
SELECT 'Items with channel_id', COUNT(*) FROM schedule_items WHERE channel_id IS NOT NULL
UNION ALL
SELECT 'Items with target_id', COUNT(*) FROM schedule_items WHERE target_id IS NOT NULL
UNION ALL
SELECT 'Total send_types', COUNT(*) FROM send_types
UNION ALL
SELECT 'Active send_types', COUNT(*) FROM send_types WHERE is_active = 1
UNION ALL
SELECT 'Total channels', COUNT(*) FROM channels
UNION ALL
SELECT 'Total audience_targets', COUNT(*) FROM audience_targets
UNION ALL
SELECT 'Total caption_bank', COUNT(*) FROM caption_bank
UNION ALL
SELECT 'Schedulable captions', COUNT(*) FROM caption_bank WHERE is_schedulable = 1;

-- =============================================================================
-- 7. INDEX USAGE ANALYSIS
-- =============================================================================

.print ""
.print "=== INDEX USAGE STATISTICS ==="
.print ""

-- Check sqlite_stat1 for index statistics
SELECT
    tbl AS table_name,
    idx AS index_name,
    stat AS statistics
FROM sqlite_stat1
WHERE tbl IN ('schedule_items', 'send_types', 'channels', 'audience_targets')
ORDER BY tbl, idx;

-- =============================================================================
-- 8. POTENTIAL N+1 QUERY PATTERNS
-- =============================================================================

.print ""
.print "=== N+1 QUERY PATTERN DETECTION ==="
.print ""

-- Check for potential N+1 in schedule item processing
.print "Checking schedule items without send_type data (would require N queries):"
SELECT COUNT(*) AS items_needing_lookup
FROM schedule_items si
WHERE si.send_type_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM send_types st WHERE st.send_type_id = si.send_type_id
);

.print ""
.print "Checking schedule items without channel data (would require N queries):"
SELECT COUNT(*) AS items_needing_lookup
FROM schedule_items si
WHERE si.channel_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM channels ch WHERE ch.channel_id = si.channel_id
);

-- =============================================================================
-- 9. COMPOSITE INDEX EFFECTIVENESS
-- =============================================================================

.print ""
.print "=== COMPOSITE INDEX EFFECTIVENESS ==="
.print ""

-- Test composite index on schedule_items
.print "Test: Creator + Date lookup (uses idx_items_creator_date)"
.timer ON
EXPLAIN QUERY PLAN
SELECT item_id, scheduled_time, item_type
FROM schedule_items
WHERE creator_id = 'CID001'
AND scheduled_date = '2025-12-16'
AND status = 'pending';
.timer OFF

-- Test send_types composite index
.print ""
.print "Test: Send type selection (uses idx_send_types_schedule_selection)"
.timer ON
EXPLAIN QUERY PLAN
SELECT send_type_id, send_type_key, display_name
FROM send_types
WHERE is_active = 1
AND category = 'revenue'
AND page_type_restriction = 'paid'
ORDER BY sort_order;
.timer OFF

-- =============================================================================
-- 10. WRITE PERFORMANCE TESTS
-- =============================================================================

.print ""
.print "=== WRITE PERFORMANCE ANALYSIS ==="
.print ""

-- Analyze indexes that would be updated on insert
.print "Indexes updated on schedule_items insert:"
SELECT name
FROM sqlite_master
WHERE type = 'index'
AND tbl_name = 'schedule_items'
ORDER BY name;

.print ""
.print "Performance test complete!"
