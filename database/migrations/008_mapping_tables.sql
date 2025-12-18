-- ============================================================================
-- Migration: 008_mapping_tables.sql
-- Version: 1.0.0
-- Created: 2025-12-15
--
-- Purpose: Mapping tables that connect send_types to caption_types and
--          content_types for the EROS Schedule Generator system.
--
-- Tables Created:
--   - send_type_caption_requirements: Maps optimal caption_types per send_type
--   - send_type_content_compatibility: Maps content_type compatibility per send_type
--
-- Dependencies (run in order):
--   1. 008_send_types_foundation.sql (creates send_types, channels, audience_targets tables)
--   2. 008_send_types_seed_data.sql (populates send_types with 21 types)
--   3. content_types table (existing schema)
--   4. caption_bank table (existing schema)
--
-- ============================================================================

-- ============================================================================
-- TABLE: send_type_caption_requirements
-- Maps which caption_types work best for each send_type with priority ranking
-- ============================================================================

CREATE TABLE IF NOT EXISTS send_type_caption_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_id INTEGER NOT NULL REFERENCES send_types(send_type_id),
    caption_type TEXT NOT NULL,  -- matches caption_bank.caption_type
    priority INTEGER DEFAULT 3,  -- 1=primary (best match), 2=good, 3=acceptable, 4=secondary, 5=fallback
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(send_type_id, caption_type)
);

-- ============================================================================
-- TABLE: send_type_content_compatibility
-- Maps which content_types are compatible with each send_type
-- ============================================================================

CREATE TABLE IF NOT EXISTS send_type_content_compatibility (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_type_id INTEGER NOT NULL REFERENCES send_types(send_type_id),
    content_type_id INTEGER NOT NULL REFERENCES content_types(content_type_id),
    compatibility TEXT NOT NULL CHECK (compatibility IN ('required', 'recommended', 'allowed', 'discouraged', 'forbidden')),
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(send_type_id, content_type_id)
);

-- ============================================================================
-- INDEXES
-- Performance optimization for common query patterns
-- ============================================================================

-- send_type_caption_requirements indexes
CREATE INDEX IF NOT EXISTS idx_caption_requirements_send_type
    ON send_type_caption_requirements(send_type_id);

CREATE INDEX IF NOT EXISTS idx_caption_requirements_caption_type
    ON send_type_caption_requirements(caption_type);

-- send_type_content_compatibility indexes
CREATE INDEX IF NOT EXISTS idx_content_compatibility_send_type
    ON send_type_content_compatibility(send_type_id);

CREATE INDEX IF NOT EXISTS idx_content_compatibility_content_type
    ON send_type_content_compatibility(content_type_id);

-- Composite index for priority-based caption selection
CREATE INDEX IF NOT EXISTS idx_caption_requirements_priority
    ON send_type_caption_requirements(send_type_id, priority);

-- ============================================================================
-- NOTE: send_types seed data is now in 008_send_types_seed_data.sql
-- This file only contains mapping table data that references send_types.
-- Run 008_send_types_seed_data.sql BEFORE this file.
-- ============================================================================

-- ============================================================================
-- SEED DATA: send_type_caption_requirements
-- Maps optimal caption_types for each send_type with priority ranking
--
-- Priority Levels:
--   1 = Primary (best match, use first)
--   2 = Good (strong secondary option)
--   3 = Acceptable (can use if needed)
--   4 = Secondary (lower priority match)
--   5 = Fallback (use only when no better options)
--
-- Caption Types Available:
--   ppv_unlock, ppv_followup, renewal_pitch, flirty_opener, sexy_story,
--   engagement_hook, game_promo, bundle_offer, dm_invite, like_request,
--   live_announcement, vip_promo, flash_sale, winback
-- ============================================================================

-- First, clear existing data for idempotency
DELETE FROM send_type_caption_requirements;

-- ppv_video -> ppv_unlock (primary), sexy_story (acceptable)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'ppv_unlock', 1, 'Primary caption type for PPV video content'
FROM send_types WHERE send_type_key = 'ppv_video';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'sexy_story', 3, 'Narrative captions can enhance PPV appeal'
FROM send_types WHERE send_type_key = 'ppv_video';

-- vip_program -> vip_promo (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'vip_promo', 1, 'Dedicated VIP promotion captions'
FROM send_types WHERE send_type_key = 'vip_program';

-- game_post -> game_promo (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'game_promo', 1, 'Game and contest promotion captions'
FROM send_types WHERE send_type_key = 'game_post';

-- bundle -> bundle_offer (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'bundle_offer', 1, 'Bundle and package promotion captions'
FROM send_types WHERE send_type_key = 'bundle';

-- flash_bundle -> flash_sale (primary), bundle_offer (good)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'flash_sale', 1, 'Urgency-driven flash sale captions'
FROM send_types WHERE send_type_key = 'flash_bundle';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'bundle_offer', 2, 'Standard bundle captions with urgency modification'
FROM send_types WHERE send_type_key = 'flash_bundle';

-- snapchat_bundle -> bundle_offer (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'bundle_offer', 1, 'Bundle captions for throwback content packages'
FROM send_types WHERE send_type_key = 'snapchat_bundle';

-- first_to_tip -> game_promo (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'game_promo', 1, 'Gamified tip competition captions'
FROM send_types WHERE send_type_key = 'first_to_tip';

-- link_drop -> ppv_unlock (good), bundle_offer (good)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'ppv_unlock', 2, 'Value-proposition captions for link drops'
FROM send_types WHERE send_type_key = 'link_drop';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'bundle_offer', 2, 'Bundle-style captions for link drops'
FROM send_types WHERE send_type_key = 'link_drop';

-- wall_link_drop -> ppv_unlock (good), bundle_offer (good)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'ppv_unlock', 2, 'Value-proposition captions for wall link drops'
FROM send_types WHERE send_type_key = 'wall_link_drop';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'bundle_offer', 2, 'Bundle-style captions for wall link drops'
FROM send_types WHERE send_type_key = 'wall_link_drop';

-- bump_normal -> flirty_opener (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'flirty_opener', 1, 'Flirty engagement captions for standard bumps'
FROM send_types WHERE send_type_key = 'bump_normal';

-- bump_descriptive -> sexy_story (primary), flirty_opener (good)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'sexy_story', 1, 'Narrative captions for descriptive bumps'
FROM send_types WHERE send_type_key = 'bump_descriptive';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'flirty_opener', 2, 'Flirty fallback for descriptive bumps'
FROM send_types WHERE send_type_key = 'bump_descriptive';

-- bump_text_only -> flirty_opener (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'flirty_opener', 1, 'Flirty text-only engagement captions'
FROM send_types WHERE send_type_key = 'bump_text_only';

-- bump_flyer -> sexy_story (primary), flirty_opener (good)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'sexy_story', 1, 'Narrative captions to complement flyer bumps'
FROM send_types WHERE send_type_key = 'bump_flyer';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'flirty_opener', 2, 'Flirty fallback for flyer bumps'
FROM send_types WHERE send_type_key = 'bump_flyer';

-- dm_farm -> dm_invite (primary), flirty_opener (good)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'dm_invite', 1, 'Direct message invitation captions'
FROM send_types WHERE send_type_key = 'dm_farm';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'flirty_opener', 2, 'Flirty DM engagement captions'
FROM send_types WHERE send_type_key = 'dm_farm';

-- like_farm -> like_request (primary), engagement_hook (good)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'like_request', 1, 'Request likes and engagement captions'
FROM send_types WHERE send_type_key = 'like_farm';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'engagement_hook', 2, 'General engagement hook captions'
FROM send_types WHERE send_type_key = 'like_farm';

-- live_promo -> live_announcement (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'live_announcement', 1, 'Live stream announcement captions'
FROM send_types WHERE send_type_key = 'live_promo';

-- renew_on_post -> renewal_pitch (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'renewal_pitch', 1, 'Subscription renewal pitch captions'
FROM send_types WHERE send_type_key = 'renew_on_post';

-- renew_on_message -> renewal_pitch (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'renewal_pitch', 1, 'Subscription renewal pitch captions for DM'
FROM send_types WHERE send_type_key = 'renew_on_message';

-- ppv_message -> ppv_unlock (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'ppv_unlock', 1, 'PPV unlock captions for direct messages'
FROM send_types WHERE send_type_key = 'ppv_message';

-- ppv_followup -> ppv_followup (primary)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'ppv_followup', 1, 'Follow-up captions for unsold PPV'
FROM send_types WHERE send_type_key = 'ppv_followup';

-- expired_winback -> winback (primary), renewal_pitch (good)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'winback', 1, 'Re-engagement captions for expired subscribers'
FROM send_types WHERE send_type_key = 'expired_winback';

INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
SELECT send_type_id, 'renewal_pitch', 2, 'Renewal pitch as winback alternative'
FROM send_types WHERE send_type_key = 'expired_winback';

-- ============================================================================
-- SEED DATA: send_type_content_compatibility
-- Default: All combinations set to 'allowed'
-- Then apply specific overrides for special cases
--
-- Compatibility Levels:
--   required    - Must use this content type
--   recommended - Preferred content type
--   allowed     - Can use this content type (default)
--   discouraged - Should avoid unless necessary
--   forbidden   - Cannot use this content type
-- ============================================================================

-- First, clear existing data for idempotency
DELETE FROM send_type_content_compatibility;

-- Insert default 'allowed' compatibility for all send_type + content_type combinations
-- This uses a CROSS JOIN to generate all possible combinations
INSERT INTO send_type_content_compatibility (send_type_id, content_type_id, compatibility, notes)
SELECT
    st.send_type_id,
    ct.content_type_id,
    'allowed',
    'Default compatibility - all content types allowed'
FROM send_types st
CROSS JOIN content_types ct
WHERE st.is_active = 1;

-- ============================================================================
-- OVERRIDES: snapchat_bundle - recommend throwback content
-- Mark solo and implied_solo as 'recommended' for throwback authenticity
-- ============================================================================

UPDATE send_type_content_compatibility
SET
    compatibility = 'recommended',
    notes = 'Throwback content works well with solo/implied solo types'
WHERE send_type_id = (SELECT send_type_id FROM send_types WHERE send_type_key = 'snapchat_bundle')
  AND content_type_id IN (
      SELECT content_type_id FROM content_types
      WHERE type_name IN ('solo', 'implied_solo')
  );

-- ============================================================================
-- OVERRIDES: live_promo - only live_stream content is valid
-- Set live_stream as 'required', all others as 'forbidden'
-- ============================================================================

-- First, mark all content types as 'forbidden' for live_promo
UPDATE send_type_content_compatibility
SET
    compatibility = 'forbidden',
    notes = 'Live promo requires live stream content only'
WHERE send_type_id = (SELECT send_type_id FROM send_types WHERE send_type_key = 'live_promo');

-- Then, set live_stream as 'required'
UPDATE send_type_content_compatibility
SET
    compatibility = 'required',
    notes = 'Live promo must use live stream content'
WHERE send_type_id = (SELECT send_type_id FROM send_types WHERE send_type_key = 'live_promo')
  AND content_type_id IN (
      SELECT content_type_id FROM content_types
      WHERE type_name = 'live_stream'
  );

-- ============================================================================
-- ADDITIONAL RECOMMENDED COMPATIBILITY RULES
-- These are soft recommendations based on content-send type alignment
-- ============================================================================

-- PPV sends work best with high-value content types
UPDATE send_type_content_compatibility
SET
    compatibility = 'recommended',
    notes = 'High-value content recommended for PPV sends'
WHERE send_type_id IN (
    SELECT send_type_id FROM send_types
    WHERE send_type_key IN ('ppv_video', 'ppv_message')
)
AND content_type_id IN (
    SELECT content_type_id FROM content_types
    WHERE type_name IN ('bg', 'gg', 'solo', 'anal', 'squirt', 'creampie', 'facial', 'bj')
);

-- Bundle sends work well with variety content
UPDATE send_type_content_compatibility
SET
    compatibility = 'recommended',
    notes = 'Variety content recommended for bundles'
WHERE send_type_id IN (
    SELECT send_type_id FROM send_types
    WHERE send_type_key IN ('bundle', 'flash_bundle')
)
AND content_type_id IN (
    SELECT content_type_id FROM content_types
    WHERE type_name IN ('solo', 'implied_solo', 'tease', 'behind_the_scenes')
);

-- Bump sends work well with teaser content
UPDATE send_type_content_compatibility
SET
    compatibility = 'recommended',
    notes = 'Teaser content recommended for engagement bumps'
WHERE send_type_id IN (
    SELECT send_type_id FROM send_types
    WHERE send_type_key IN ('bump_normal', 'bump_descriptive', 'bump_flyer')
)
AND content_type_id IN (
    SELECT content_type_id FROM content_types
    WHERE type_name IN ('tease', 'implied_solo', 'selfie', 'lifestyle')
);

-- ============================================================================
-- VIEW: v_send_type_caption_matrix
-- Provides a denormalized view of send types with their caption requirements
-- ============================================================================

DROP VIEW IF EXISTS v_send_type_caption_matrix;

CREATE VIEW v_send_type_caption_matrix AS
SELECT
    st.send_type_id,
    st.send_type_key,
    st.category,
    st.display_name AS send_type_name,
    scr.caption_type,
    scr.priority,
    scr.notes,
    CASE scr.priority
        WHEN 1 THEN 'Primary'
        WHEN 2 THEN 'Good'
        WHEN 3 THEN 'Acceptable'
        WHEN 4 THEN 'Secondary'
        WHEN 5 THEN 'Fallback'
        ELSE 'Unknown'
    END AS priority_label
FROM send_types st
LEFT JOIN send_type_caption_requirements scr ON st.send_type_id = scr.send_type_id
WHERE st.is_active = 1
ORDER BY st.category, st.sort_order, scr.priority;

-- ============================================================================
-- VIEW: v_send_type_content_matrix
-- Provides a denormalized view of send types with content compatibility
-- ============================================================================

DROP VIEW IF EXISTS v_send_type_content_matrix;

CREATE VIEW v_send_type_content_matrix AS
SELECT
    st.send_type_id,
    st.send_type_key,
    st.category,
    st.display_name AS send_type_name,
    ct.content_type_id,
    ct.type_name AS content_type_name,
    scc.compatibility,
    scc.notes
FROM send_types st
LEFT JOIN send_type_content_compatibility scc ON st.send_type_id = scc.send_type_id
LEFT JOIN content_types ct ON scc.content_type_id = ct.content_type_id
WHERE st.is_active = 1
ORDER BY st.category, st.sort_order, scc.compatibility, ct.type_name;

-- ============================================================================
-- FUNCTION-LIKE VIEW: v_best_captions_for_send_type
-- Helps find optimal captions for a given send type
-- Join this view with caption_bank to find matching captions
-- ============================================================================

DROP VIEW IF EXISTS v_best_captions_for_send_type;

CREATE VIEW v_best_captions_for_send_type AS
SELECT
    st.send_type_id,
    st.send_type_key,
    st.display_name AS send_type_name,
    scr.caption_type,
    scr.priority,
    COUNT(cb.caption_id) AS available_captions,
    ROUND(AVG(cb.performance_score), 2) AS avg_performance,
    ROUND(AVG(cb.freshness_score), 2) AS avg_freshness
FROM send_types st
JOIN send_type_caption_requirements scr ON st.send_type_id = scr.send_type_id
LEFT JOIN caption_bank cb ON cb.caption_type = scr.caption_type AND cb.is_active = 1
WHERE st.is_active = 1
GROUP BY st.send_type_id, st.send_type_key, st.display_name, scr.caption_type, scr.priority
ORDER BY st.send_type_key, scr.priority;

-- ============================================================================
-- MIGRATION TRACKING
-- Record this migration in schema_migrations table
-- ============================================================================

INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
VALUES (
    '008_mapping_tables',
    datetime('now'),
    'Send type mapping tables: send_type_caption_requirements and send_type_content_compatibility with seed data and views'
);

-- ============================================================================
-- VERIFICATION QUERIES
-- Run these after migration to verify successful application
-- ============================================================================

-- 1. Verify send_type_caption_requirements has data:
--    SELECT send_type_key, caption_type, priority
--    FROM v_send_type_caption_matrix
--    ORDER BY send_type_key, priority;

-- 2. Verify send_type_content_compatibility has data:
--    SELECT send_type_key, COUNT(*) as content_types,
--           SUM(CASE WHEN compatibility = 'required' THEN 1 ELSE 0 END) as required_count,
--           SUM(CASE WHEN compatibility = 'recommended' THEN 1 ELSE 0 END) as recommended_count,
--           SUM(CASE WHEN compatibility = 'allowed' THEN 1 ELSE 0 END) as allowed_count,
--           SUM(CASE WHEN compatibility = 'forbidden' THEN 1 ELSE 0 END) as forbidden_count
--    FROM v_send_type_content_matrix
--    GROUP BY send_type_key;

-- 3. Verify all 21 send types have caption mappings:
--    SELECT COUNT(DISTINCT send_type_id) as mapped_send_types
--    FROM send_type_caption_requirements;

-- 4. Check caption availability per send type:
--    SELECT * FROM v_best_captions_for_send_type;

-- ============================================================================
-- ROLLBACK STRATEGY
-- To rollback this migration:
--
-- DROP VIEW IF EXISTS v_best_captions_for_send_type;
-- DROP VIEW IF EXISTS v_send_type_content_matrix;
-- DROP VIEW IF EXISTS v_send_type_caption_matrix;
-- DROP INDEX IF EXISTS idx_caption_requirements_priority;
-- DROP INDEX IF EXISTS idx_content_compatibility_content_type;
-- DROP INDEX IF EXISTS idx_content_compatibility_send_type;
-- DROP INDEX IF EXISTS idx_caption_requirements_caption_type;
-- DROP INDEX IF EXISTS idx_caption_requirements_send_type;
-- DROP TABLE IF EXISTS send_type_content_compatibility;
-- DROP TABLE IF EXISTS send_type_caption_requirements;
-- DELETE FROM schema_migrations WHERE version = '008_mapping_tables';
--
-- ============================================================================
-- END OF MIGRATION 008_mapping_tables.sql
-- ============================================================================
