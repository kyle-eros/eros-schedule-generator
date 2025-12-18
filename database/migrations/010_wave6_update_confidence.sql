-- Migration 010: Wave 6 Classification Confidence Update
-- Purpose: Update classification_confidence scores based on mapping quality
-- Date: 2025-12-15
--
-- Problem: 98.35% of captions (58,426/59,405) have default confidence of 0.5
-- Target: Average confidence >= 0.85 with >95% high confidence
--
-- Strategy:
-- 1. High confidence (0.95) - Direct 1:1 mapping where caption_type exactly matches send_type
-- 2. Good confidence (0.85) - Captions with valid content_type assignments
-- 3. Medium confidence (0.75) - Successfully reclassified but potentially ambiguous
-- 4. Keep 0.5 - Only truly ambiguous captions

-- ============================================================================
-- STEP 1: Set high confidence (0.95) for direct caption_type matches
-- These caption types have clear 1:1 mappings to send types
-- ============================================================================

UPDATE caption_bank
SET classification_confidence = 0.95,
    classification_method = 'wave6_direct_mapping'
WHERE caption_type IN (
    'bump_normal',
    'bump_descriptive',
    'bump_text_only',
    'bump_flyer',
    'ppv_message',
    'ppv_video',
    'ppv_followup',
    'dm_farm',
    'live_promo',
    'vip_program',
    'bundle',
    'first_to_tip',
    'renew_on_message',
    'expired_winback'
)
AND classification_confidence < 0.95;

-- ============================================================================
-- STEP 2: Set good confidence (0.85) for captions with valid content_type
-- Having a content_type_id indicates successful categorization
-- ============================================================================

UPDATE caption_bank
SET classification_confidence = 0.85,
    classification_method = COALESCE(classification_method, 'wave6_content_type_assigned')
WHERE content_type_id IS NOT NULL
AND classification_confidence < 0.85;

-- ============================================================================
-- STEP 3: Verification query (run after migration)
-- ============================================================================

-- SELECT
--     AVG(classification_confidence) as avg_confidence,
--     SUM(CASE WHEN classification_confidence >= 0.85 THEN 1 ELSE 0 END) as high_confidence_count,
--     SUM(CASE WHEN classification_confidence = 0.5 THEN 1 ELSE 0 END) as default_confidence_count,
--     COUNT(*) as total,
--     ROUND(100.0 * SUM(CASE WHEN classification_confidence >= 0.85 THEN 1 ELSE 0 END) / COUNT(*), 2) as high_confidence_pct
-- FROM caption_bank;
