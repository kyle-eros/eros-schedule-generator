-- Migration: 002_volume_assignments.sql
-- Phase 2: Volume assignment tracking with audit trail
-- Created: 2025-11-30
--
-- This migration adds the volume_assignments table for tracking
-- volume level assignments to creators over time, enabling:
-- - Automated fan-count-based assignments
-- - Manual operator overrides
-- - Full audit trail of changes
-- - Historical reporting and analytics

-- ============================================================================
-- TABLE: volume_assignments
-- ============================================================================
-- Stores volume assignment history for creators with audit trail.
-- Each row represents an assignment event - either automatic or manual.
-- The is_active flag identifies the current assignment for each creator.

CREATE TABLE IF NOT EXISTS volume_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    volume_level TEXT NOT NULL CHECK (volume_level IN ('Low', 'Mid', 'High', 'Ultra')),
    ppv_per_day INTEGER NOT NULL,
    bump_per_day INTEGER NOT NULL,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    assigned_by TEXT NOT NULL DEFAULT 'system',
    assigned_reason TEXT NOT NULL CHECK (
        assigned_reason IN ('fan_count_bracket', 'manual_override', 'adaptive_adjustment')
    ),
    is_active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,

    -- Foreign key to creators table (cascade delete for cleanup)
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE,

    -- Domain constraints
    CHECK (ppv_per_day >= 1 AND ppv_per_day <= 15),
    CHECK (bump_per_day >= 1 AND bump_per_day <= 15),
    CHECK (is_active IN (0, 1))
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Partial index for fast active assignment lookups
-- Only indexes rows where is_active = 1 for performance
CREATE INDEX IF NOT EXISTS idx_va_creator_active
ON volume_assignments(creator_id, is_active)
WHERE is_active = 1;

-- Index for volume level analytics and reporting
CREATE INDEX IF NOT EXISTS idx_va_volume_level
ON volume_assignments(volume_level)
WHERE is_active = 1;

-- Index for audit trail queries (chronological history)
CREATE INDEX IF NOT EXISTS idx_va_assigned_at
ON volume_assignments(assigned_at DESC);

-- Index for tracking system vs manual assignments
CREATE INDEX IF NOT EXISTS idx_va_assigned_by
ON volume_assignments(assigned_by, assigned_at DESC);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: v_current_volume_assignments
-- Provides a joined view of active assignments with creator metadata
-- for easy querying in reports and dashboards
CREATE VIEW IF NOT EXISTS v_current_volume_assignments AS
SELECT
    va.assignment_id,
    va.creator_id,
    va.volume_level,
    va.ppv_per_day,
    va.bump_per_day,
    va.assigned_at,
    va.assigned_by,
    va.assigned_reason,
    va.notes,
    c.page_name,
    c.display_name,
    c.page_type,
    c.current_active_fans,
    c.performance_tier,
    c.current_total_earnings
FROM volume_assignments va
JOIN creators c ON va.creator_id = c.creator_id
WHERE va.is_active = 1
ORDER BY c.page_name;

-- View: v_volume_assignment_stats
-- Provides real-time statistics on volume distribution
CREATE VIEW IF NOT EXISTS v_volume_assignment_stats AS
SELECT
    volume_level,
    COUNT(*) as creator_count,
    AVG(ppv_per_day) as avg_ppv_per_day,
    AVG(bump_per_day) as avg_bump_per_day,
    AVG(c.current_active_fans) as avg_fans,
    SUM(c.current_total_earnings) as total_earnings
FROM volume_assignments va
JOIN creators c ON va.creator_id = c.creator_id
WHERE va.is_active = 1
GROUP BY volume_level
ORDER BY
    CASE volume_level
        WHEN 'Low' THEN 1
        WHEN 'Mid' THEN 2
        WHEN 'High' THEN 3
        WHEN 'Ultra' THEN 4
    END;

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================
--
-- Post-migration steps:
-- 1. Run initial assignment population for existing creators
-- 2. Verify indexes are being used with EXPLAIN QUERY PLAN
-- 3. Monitor performance with SQLite's query analyzer
-- 4. Consider adding triggers for automatic audit logging if needed
--
-- Rollback strategy:
-- DROP VIEW IF EXISTS v_volume_assignment_stats;
-- DROP VIEW IF EXISTS v_current_volume_assignments;
-- DROP INDEX IF EXISTS idx_va_assigned_by;
-- DROP INDEX IF EXISTS idx_va_assigned_at;
-- DROP INDEX IF EXISTS idx_va_volume_level;
-- DROP INDEX IF EXISTS idx_va_creator_active;
-- DROP TABLE IF EXISTS volume_assignments;
