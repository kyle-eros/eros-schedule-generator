-- Migration 016: Add content_category for bump multiplier calculation
-- Part of Volume Optimization v3.0 (Wave 1)
--
-- Purpose: Enable per-creator bump multipliers based on content type
-- Values: lifestyle (1.0x), softcore (1.5x), amateur (2.0x), explicit (2.67x)

-- Add content_category column to creators table
ALTER TABLE creators ADD COLUMN content_category TEXT
    CHECK (content_category IN ('lifestyle', 'softcore', 'amateur', 'explicit'))
    DEFAULT 'softcore';

-- Create lookup table for bump multipliers (reference data)
CREATE TABLE IF NOT EXISTS content_categories (
    category_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    bump_multiplier REAL NOT NULL DEFAULT 1.0,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Seed bump multiplier reference data
INSERT OR REPLACE INTO content_categories (category_key, display_name, bump_multiplier, description) VALUES
    ('lifestyle', 'Lifestyle', 1.0, 'Non-explicit baseline - GFE, personal connection focus'),
    ('softcore', 'Softcore', 1.5, 'Suggestive content - moderate engagement needs'),
    ('amateur', 'Amateur', 2.0, 'Amateur style - authentic appeal, higher engagement'),
    ('explicit', 'Explicit', 2.67, 'Explicit commercial - maximum engagement multiplier');

-- Create index for filtering by content_category
CREATE INDEX IF NOT EXISTS idx_creators_content_category ON creators(content_category);

-- Verification query (run after migration)
-- SELECT content_category, COUNT(*) FROM creators GROUP BY content_category;
