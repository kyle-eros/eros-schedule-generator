-- ============================================================================
-- WAVE 6: Fix send_type_caption_requirements Table
-- ============================================================================
-- Purpose: Replace broken caption_type references with ACTUAL caption_types
--          that exist in the caption_bank table.
--
-- Problem: The current send_type_caption_requirements table references
--          caption_types like 'ppv_unlock', 'sexy_story', 'flirty_opener', etc.
--          that DO NOT EXIST in caption_bank.
--
-- Solution: Delete all old mappings and insert correct mappings using the
--           14 actual caption_types in caption_bank:
--           - bump_normal (20,255 captions)
--           - ppv_message (19,493 captions)
--           - bump_descriptive (14,580 captions)
--           - renew_on_message (2,066 captions)
--           - dm_farm (1,549 captions)
--           - bump_text_only (470 captions)
--           - first_to_tip (331 captions)
--           - bundle (158 captions)
--           - live_promo (140 captions)
--           - vip_program (118 captions)
--           - ppv_video (116 captions)
--           - ppv_followup (112 captions)
--           - bump_flyer (13 captions)
--           - expired_winback (4 captions)
--
-- Date: 2025-12-15
-- ============================================================================

-- Begin transaction for atomic operation
BEGIN TRANSACTION;

-- ============================================================================
-- STEP 1: Clear all broken mappings
-- ============================================================================
DELETE FROM send_type_caption_requirements;

-- ============================================================================
-- STEP 2: Insert correct mappings with priorities
-- ============================================================================
-- Priority 1 = Primary (best match)
-- Priority 2 = Secondary (good fallback)
-- Priority 3 = Tertiary (acceptable alternative)
-- ============================================================================

-- -----------------------------------------------------------------------------
-- REVENUE SEND TYPES (send_type_id 1-7)
-- -----------------------------------------------------------------------------

-- send_type_id 1: ppv_video
-- Primary: ppv_video (exact match, 116 captions)
-- Fallback: ppv_message (similar PPV content, 19,493 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (1, 'ppv_video', 1, 'Primary caption type for PPV video sends');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (1, 'ppv_message', 2, 'Fallback PPV captions with large inventory');

-- send_type_id 2: vip_program
-- Primary: vip_program (exact match, 118 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (2, 'vip_program', 1, 'Dedicated VIP program promotion captions');

-- send_type_id 3: game_post
-- Primary: first_to_tip (gamified content, 331 captions)
-- Fallback: bump_normal (engagement hooks)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (3, 'first_to_tip', 1, 'Gamified tip competition captions');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (3, 'bump_normal', 2, 'Engagement hooks for game posts');

-- send_type_id 4: bundle
-- Primary: bundle (exact match, 158 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (4, 'bundle', 1, 'Bundle offer captions');

-- send_type_id 5: flash_bundle
-- Primary: bundle (urgency variant, 158 captions)
-- Fallback: ppv_message (value proposition)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (5, 'bundle', 1, 'Bundle captions with urgency modification');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (5, 'ppv_message', 2, 'PPV captions for flash bundle urgency');

-- send_type_id 6: snapchat_bundle
-- Primary: bundle (throwback variant, 158 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (6, 'bundle', 1, 'Bundle captions for throwback content packages');

-- send_type_id 7: first_to_tip
-- Primary: first_to_tip (exact match, 331 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (7, 'first_to_tip', 1, 'Gamified tip competition captions');

-- -----------------------------------------------------------------------------
-- ENGAGEMENT SEND TYPES (send_type_id 8-16)
-- -----------------------------------------------------------------------------

-- send_type_id 8: link_drop
-- Primary: ppv_message (value proposition, 19,493 captions)
-- Fallback: bump_normal (engagement hooks, 20,255 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (8, 'ppv_message', 1, 'Value-proposition captions for link drops');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (8, 'bump_normal', 2, 'Engagement captions for link drops');

-- send_type_id 9: wall_link_drop
-- Primary: ppv_message (value proposition, 19,493 captions)
-- Fallback: bump_normal (engagement hooks, 20,255 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (9, 'ppv_message', 1, 'Value-proposition captions for wall link drops');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (9, 'bump_normal', 2, 'Engagement captions for wall link drops');

-- send_type_id 10: bump_normal
-- Primary: bump_normal (exact match, 20,255 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (10, 'bump_normal', 1, 'Standard bump engagement captions');

-- send_type_id 11: bump_descriptive
-- Primary: bump_descriptive (exact match, 14,580 captions)
-- Fallback: bump_normal (similar engagement style)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (11, 'bump_descriptive', 1, 'Descriptive/narrative bump captions');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (11, 'bump_normal', 2, 'Fallback bump captions');

-- send_type_id 12: bump_text_only
-- Primary: bump_text_only (exact match, 470 captions)
-- Fallback: bump_normal (can be used without media)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (12, 'bump_text_only', 1, 'Text-only bump captions (no media)');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (12, 'bump_normal', 2, 'Fallback bump captions usable without media');

-- send_type_id 13: bump_flyer
-- Primary: bump_flyer (exact match, 13 captions)
-- Fallback: bump_descriptive (narrative to complement flyer)
-- Tertiary: bump_normal (general engagement)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (13, 'bump_flyer', 1, 'Captions designed for flyer-based bumps');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (13, 'bump_descriptive', 2, 'Narrative captions to complement flyers');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (13, 'bump_normal', 3, 'General bump fallback for flyer posts');

-- send_type_id 14: dm_farm
-- Primary: dm_farm (exact match, 1,549 captions)
-- Fallback: bump_normal (engagement hooks)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (14, 'dm_farm', 1, 'DM farming engagement captions');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (14, 'bump_normal', 2, 'Engagement hook fallback for DM farming');

-- send_type_id 15: like_farm
-- Primary: dm_farm (engagement hooks, 1,549 captions)
-- Fallback: bump_normal (general engagement)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (15, 'dm_farm', 1, 'Engagement hook captions for like farming');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (15, 'bump_normal', 2, 'General engagement fallback for like farming');

-- send_type_id 16: live_promo
-- Primary: live_promo (exact match, 140 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (16, 'live_promo', 1, 'Live stream announcement captions');

-- -----------------------------------------------------------------------------
-- RETENTION SEND TYPES (send_type_id 17-21)
-- -----------------------------------------------------------------------------

-- send_type_id 17: renew_on_post
-- Primary: renew_on_message (renewal pitch, 2,066 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (17, 'renew_on_message', 1, 'Subscription renewal pitch captions for posts');

-- send_type_id 18: renew_on_message
-- Primary: renew_on_message (exact match, 2,066 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (18, 'renew_on_message', 1, 'Subscription renewal pitch captions for DMs');

-- send_type_id 19: ppv_message
-- Primary: ppv_message (exact match, 19,493 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (19, 'ppv_message', 1, 'PPV unlock captions for direct messages');

-- send_type_id 20: ppv_followup
-- Primary: ppv_followup (exact match, 112 captions)
-- Fallback: ppv_message (similar PPV content)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (20, 'ppv_followup', 1, 'Follow-up captions for unsold PPV');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (20, 'ppv_message', 2, 'PPV message fallback for followups');

-- send_type_id 21: expired_winback
-- Primary: expired_winback (exact match, 4 captions - limited inventory!)
-- Fallback: renew_on_message (re-engagement, 2,066 captions)
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (21, 'expired_winback', 1, 'Re-engagement captions for expired subscribers');
INSERT INTO send_type_caption_requirements (send_type_id, caption_type, priority, notes)
VALUES (21, 'renew_on_message', 2, 'Renewal pitch as winback alternative');

-- Commit transaction
COMMIT;

-- ============================================================================
-- VERIFICATION QUERY
-- Run this after migration to verify all send types have caption coverage
-- ============================================================================
-- SELECT st.send_type_key, st.category,
--        GROUP_CONCAT(stcr.caption_type || ' (p' || stcr.priority || ')') as mappings,
--        SUM(CASE WHEN cb_count.cnt IS NOT NULL THEN cb_count.cnt ELSE 0 END) as total_captions
-- FROM send_types st
-- LEFT JOIN send_type_caption_requirements stcr ON st.send_type_id = stcr.send_type_id
-- LEFT JOIN (
--     SELECT caption_type, COUNT(*) as cnt
--     FROM caption_bank
--     GROUP BY caption_type
-- ) cb_count ON stcr.caption_type = cb_count.caption_type
-- GROUP BY st.send_type_id, st.send_type_key, st.category
-- ORDER BY st.send_type_id;
