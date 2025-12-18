-- Migration 013: Add vault_notes column to creators table
-- Purpose: Store per-creator vault-specific notes and restrictions
-- Date: 2025-12-18
-- Author: Claude Code

-- Add vault_notes column to store creator-specific vault restrictions and preferences
-- Examples:
--   - "Prohibited: Face closeups due to privacy preference"
--   - "Prefers: Solo content on Mondays, B/G content Wed-Fri"
--   - "Special: Use flirty tone, avoid explicit language in teasers"

ALTER TABLE creators ADD COLUMN vault_notes TEXT;

-- Update migration tracking
INSERT INTO schema_version (version, description, applied_at)
VALUES (13, 'Add vault_notes column to creators table', datetime('now'));
