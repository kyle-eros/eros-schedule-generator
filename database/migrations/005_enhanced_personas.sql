-- Migration: 005_enhanced_personas.sql
-- Enhanced Creator Persona System with Voice Analysis and Brand Archetypes
-- Created: 2025-12-01
--
-- This migration adds comprehensive persona modeling tables for the EROS system,
-- enabling AI-powered voice matching, brand archetype analysis, and authentic
-- caption generation. The enhanced persona system captures:
-- - Detailed tone and personality dimensions (OCEAN model)
-- - Brand archetype classification with confidence scoring
-- - Emoji usage patterns and writing mechanics
-- - Authentic voice samples for AI training
-- - Google Form response storage and processing
-- - Reference archetype definitions for classification
--
-- NOTE: This migration does NOT drop the existing creator_personas table.
-- Data migration from the old table should be performed separately after
-- verifying the new schema is functioning correctly.

-- ============================================================================
-- TABLE: creator_personas_enhanced
-- ============================================================================
-- Main enhanced persona table storing comprehensive voice and brand profiles.
-- Each creator has one enhanced persona record that captures their unique
-- communication style, personality dimensions, and content preferences.
-- This table replaces the simpler creator_personas with a richer model.

CREATE TABLE IF NOT EXISTS creator_personas_enhanced (
    persona_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL UNIQUE,

    -- -------------------------------------------------------------------------
    -- Identity Section
    -- -------------------------------------------------------------------------
    -- How the creator refers to themselves and wants to be displayed
    preferred_name TEXT,                    -- Name they use in messages (e.g., "Bella", "Princess")
    display_name TEXT,                      -- Public-facing display name

    -- -------------------------------------------------------------------------
    -- Tone Dimensions
    -- -------------------------------------------------------------------------
    -- Primary and secondary communication tones with confidence scoring
    primary_tone TEXT CHECK (primary_tone IN (
        'playful', 'flirty', 'teasing', 'direct', 'mysterious',
        'dominant', 'submissive', 'romantic', 'casual', 'professional'
    )),
    secondary_tone TEXT CHECK (secondary_tone IS NULL OR secondary_tone IN (
        'playful', 'flirty', 'teasing', 'direct', 'mysterious',
        'dominant', 'submissive', 'romantic', 'casual', 'professional'
    )),
    tone_confidence REAL DEFAULT 0.0 CHECK (tone_confidence >= 0.0 AND tone_confidence <= 1.0),

    -- -------------------------------------------------------------------------
    -- OCEAN Personality Model (Big Five)
    -- -------------------------------------------------------------------------
    -- Scores from 0.0 (low) to 1.0 (high) for each dimension
    openness_score REAL CHECK (openness_score IS NULL OR (openness_score >= 0.0 AND openness_score <= 1.0)),
    conscientiousness_score REAL CHECK (conscientiousness_score IS NULL OR (conscientiousness_score >= 0.0 AND conscientiousness_score <= 1.0)),
    extraversion_score REAL CHECK (extraversion_score IS NULL OR (extraversion_score >= 0.0 AND extraversion_score <= 1.0)),
    agreeableness_score REAL CHECK (agreeableness_score IS NULL OR (agreeableness_score >= 0.0 AND agreeableness_score <= 1.0)),
    emotional_expressiveness REAL CHECK (emotional_expressiveness IS NULL OR (emotional_expressiveness >= 0.0 AND emotional_expressiveness <= 1.0)),

    -- -------------------------------------------------------------------------
    -- Brand Archetype Classification
    -- -------------------------------------------------------------------------
    -- Primary archetype with optional secondary and confidence scoring
    primary_archetype TEXT CHECK (primary_archetype IS NULL OR primary_archetype IN (
        'girl_next_door',       -- Approachable, sweet, relatable
        'seductress',           -- Sultry, confident, alluring
        'playful_tease',        -- Fun, flirty, keeps them guessing
        'girlfriend_experience', -- Intimate, caring, personal connection
        'the_dominant',         -- Commanding, powerful, in control
        'the_submissive',       -- Yielding, eager to please
        'innocent_next_door',   -- Sweet, naive aesthetic
        'party_girl',           -- Wild, fun, spontaneous
        'transactional_pro'     -- Direct, business-focused, efficient
    )),
    secondary_archetype TEXT CHECK (secondary_archetype IS NULL OR secondary_archetype IN (
        'girl_next_door', 'seductress', 'playful_tease', 'girlfriend_experience',
        'the_dominant', 'the_submissive', 'innocent_next_door', 'party_girl',
        'transactional_pro'
    )),
    archetype_confidence REAL DEFAULT 0.0 CHECK (archetype_confidence >= 0.0 AND archetype_confidence <= 1.0),

    -- -------------------------------------------------------------------------
    -- Emoji Analytics
    -- -------------------------------------------------------------------------
    -- Detailed emoji usage patterns for voice matching
    emoji_frequency TEXT CHECK (emoji_frequency IS NULL OR emoji_frequency IN (
        'heavy', 'moderate', 'light', 'none'
    )),
    emoji_per_message REAL DEFAULT 0.0 CHECK (emoji_per_message >= 0.0),
    favorite_emojis TEXT,                   -- JSON array of most-used emojis
    forbidden_emojis TEXT,                  -- JSON array of emojis to never use
    uses_emoji_substitution INTEGER DEFAULT 0 CHECK (uses_emoji_substitution IN (0, 1)),

    -- -------------------------------------------------------------------------
    -- Writing Mechanics
    -- -------------------------------------------------------------------------
    -- Structural patterns in caption composition
    avg_caption_length INTEGER DEFAULT 100 CHECK (avg_caption_length >= 0),
    caption_length_preference TEXT CHECK (caption_length_preference IS NULL OR caption_length_preference IN (
        'short', 'medium', 'long', 'varies'
    )),
    exclamation_density REAL DEFAULT 0.0 CHECK (exclamation_density >= 0.0),
    question_density REAL DEFAULT 0.0 CHECK (question_density >= 0.0),
    ellipsis_density REAL DEFAULT 0.0 CHECK (ellipsis_density >= 0.0),
    capitalization_style TEXT CHECK (capitalization_style IS NULL OR capitalization_style IN (
        'standard', 'all_caps_emphasis', 'no_caps', 'title_case', 'mixed'
    )),
    uses_markdown INTEGER DEFAULT 0 CHECK (uses_markdown IN (0, 1)),

    -- -------------------------------------------------------------------------
    -- Opener and Closer Patterns
    -- -------------------------------------------------------------------------
    -- How the creator typically starts and ends messages
    opener_style TEXT CHECK (opener_style IS NULL OR opener_style IN (
        'greeting', 'question', 'emoji', 'announcement', 'direct', 'teaser'
    )),
    closer_style TEXT CHECK (closer_style IS NULL OR closer_style IN (
        'question', 'emoji', 'cta', 'statement', 'ellipsis', 'none'
    )),
    signature_openers TEXT,                 -- JSON array of typical opening phrases
    signature_closers TEXT,                 -- JSON array of typical closing phrases

    -- -------------------------------------------------------------------------
    -- Vocabulary Analysis
    -- -------------------------------------------------------------------------
    -- Lexical patterns and distinctive word usage
    slang_level TEXT CHECK (slang_level IS NULL OR slang_level IN (
        'heavy', 'light', 'rare', 'none'
    )),
    vocabulary_size INTEGER DEFAULT 0 CHECK (vocabulary_size >= 0),
    type_token_ratio REAL DEFAULT 0.0 CHECK (type_token_ratio >= 0.0 AND type_token_ratio <= 1.0),
    vocabulary_fingerprint TEXT,            -- JSON object of distinctive word frequencies
    signature_phrases TEXT,                 -- JSON array of unique phrases this creator uses

    -- -------------------------------------------------------------------------
    -- Pet Names and Self-Reference
    -- -------------------------------------------------------------------------
    -- Terms of endearment and how they refer to themselves
    pet_names_for_fans TEXT,                -- JSON array (e.g., ["babe", "love", "cutie"])
    self_reference_terms TEXT,              -- JSON array (e.g., ["your girl", "princess"])

    -- -------------------------------------------------------------------------
    -- Boundaries and Restrictions
    -- -------------------------------------------------------------------------
    -- Content the creator will not produce or words they avoid
    forbidden_words TEXT,                   -- JSON array of words to never use
    content_boundaries TEXT,                -- JSON object describing content limits

    -- -------------------------------------------------------------------------
    -- Persuasion Style
    -- -------------------------------------------------------------------------
    -- How the creator motivates fan engagement and purchases
    persuasion_triggers TEXT,               -- JSON array of effective triggers
    urgency_style TEXT CHECK (urgency_style IS NULL OR urgency_style IN (
        'soft_fomo', 'hard_deadline', 'none', 'playful_tease'
    )),
    cta_style TEXT CHECK (cta_style IS NULL OR cta_style IN (
        'direct', 'suggestive', 'question', 'command'
    )),

    -- -------------------------------------------------------------------------
    -- Relationship Style
    -- -------------------------------------------------------------------------
    -- The dynamic the creator establishes with their audience
    relationship_style TEXT CHECK (relationship_style IS NULL OR relationship_style IN (
        'intimate_partner', 'fantasy_object', 'friend', 'dom_sub', 'professional', 'hybrid'
    )),
    power_dynamic REAL DEFAULT 0.0 CHECK (power_dynamic >= -1.0 AND power_dynamic <= 1.0),
    emotional_distance REAL DEFAULT 0.5 CHECK (emotional_distance >= 0.0 AND emotional_distance <= 1.0),

    -- -------------------------------------------------------------------------
    -- Content Preferences
    -- -------------------------------------------------------------------------
    -- Types of content the creator produces and what performs well
    preferred_content_types TEXT,           -- JSON array of content types they like to create
    top_performing_content_types TEXT,      -- JSON array of highest-earning content types
    content_description_style TEXT CHECK (content_description_style IS NULL OR content_description_style IN (
        'narrative', 'list', 'teaser', 'product', 'casual'
    )),

    -- -------------------------------------------------------------------------
    -- Sentiment Analysis
    -- -------------------------------------------------------------------------
    -- Overall emotional tone patterns
    avg_sentiment REAL DEFAULT 0.0 CHECK (avg_sentiment >= -1.0 AND avg_sentiment <= 1.0),
    sentiment_variability REAL DEFAULT 0.0 CHECK (sentiment_variability >= 0.0 AND sentiment_variability <= 1.0),

    -- -------------------------------------------------------------------------
    -- Data Quality Metrics
    -- -------------------------------------------------------------------------
    -- Indicators of profile completeness and reliability
    messages_analyzed INTEGER DEFAULT 0 CHECK (messages_analyzed >= 0),
    voice_samples_count INTEGER DEFAULT 0 CHECK (voice_samples_count >= 0),
    profile_quality TEXT CHECK (profile_quality IS NULL OR profile_quality IN (
        'excellent', 'good', 'basic', 'minimal'
    )),
    confidence_score REAL DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    data_sources TEXT,                      -- JSON array of data sources used

    -- -------------------------------------------------------------------------
    -- Metadata and Timestamps
    -- -------------------------------------------------------------------------
    form_response_id INTEGER,               -- Link to most recent form response
    last_analyzed TEXT,                     -- When voice analysis was last run
    last_form_update TEXT,                  -- When form data was last incorporated
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),

    -- -------------------------------------------------------------------------
    -- Foreign Key Constraints
    -- -------------------------------------------------------------------------
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: creator_voice_samples
-- ============================================================================
-- Stores authentic text samples from creators for voice matching and AI training.
-- Multiple samples per creator, categorized by type for targeted retrieval.
-- These samples form the ground truth for generating voice-matched content.

CREATE TABLE IF NOT EXISTS creator_voice_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,

    -- Sample Classification
    sample_type TEXT NOT NULL CHECK (sample_type IN (
        'self_description',     -- How they describe themselves
        'greeting',             -- How they say hello
        'signoff',              -- How they end messages
        'signature_phrase',     -- Unique phrases they commonly use
        'pet_name',             -- Terms of endearment they use
        'solo_ppv_caption',     -- Caption for solo PPV content
        'bg_ppv_caption',       -- Caption for B/G PPV content
        'bump_caption',         -- Follow-up/reminder captions
        'teaser_caption',       -- Teaser/preview captions
        'best_caption',         -- Their self-identified best work
        'unique_style_note'     -- Notes about unique style elements
    )),

    -- Sample Content
    sample_text TEXT NOT NULL,
    sample_context TEXT,                    -- Optional context about when/how this was used

    -- Sample Metrics
    character_count INTEGER NOT NULL CHECK (character_count >= 0),
    word_count INTEGER NOT NULL CHECK (word_count >= 0),
    emoji_count INTEGER DEFAULT 0 CHECK (emoji_count >= 0),
    sentiment_score REAL CHECK (sentiment_score IS NULL OR (sentiment_score >= -1.0 AND sentiment_score <= 1.0)),

    -- Sample Status
    is_active INTEGER DEFAULT 1 CHECK (is_active IN (0, 1)),
    source TEXT DEFAULT 'google_form' CHECK (source IN (
        'google_form', 'manual_entry', 'scraped', 'ai_generated', 'imported'
    )),

    -- Timestamps
    collected_at TEXT DEFAULT (datetime('now')),

    -- Foreign Key
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: creator_form_responses
-- ============================================================================
-- Stores raw Google Form response data for audit trail and reprocessing.
-- Each form submission is stored with its complete raw data, allowing
-- for schema evolution without data loss and debugging of processing issues.

CREATE TABLE IF NOT EXISTS creator_form_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT,                        -- NULL until matched to a creator

    -- Form Response Identification
    onlyfans_page_name TEXT NOT NULL,       -- Page name from form (for matching)
    google_form_response_id TEXT UNIQUE,    -- Google's response ID for deduplication
    response_timestamp TEXT NOT NULL,       -- When the form was submitted

    -- Raw Data Storage
    raw_response_json TEXT NOT NULL,        -- Complete form response as JSON

    -- Processing Status
    processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN (
        'pending',          -- Not yet processed
        'processed',        -- Successfully extracted and saved
        'failed',           -- Processing failed (see notes in raw_response_json)
        'needs_review'      -- Requires manual review (ambiguous data)
    )),

    -- Matching and Timestamps
    matched_at TEXT,                        -- When matched to creator_id
    created_at TEXT DEFAULT (datetime('now')),

    -- Foreign Key (nullable for unmatched responses)
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id)
);

-- ============================================================================
-- TABLE: archetype_definitions
-- ============================================================================
-- Reference table defining brand archetypes with typical characteristics.
-- Used for classification guidance and UI display. Seed data should be
-- loaded after migration to populate the archetype library.

CREATE TABLE IF NOT EXISTS archetype_definitions (
    archetype_id TEXT PRIMARY KEY,

    -- Archetype Identity
    archetype_name TEXT NOT NULL,
    description TEXT,

    -- Typical Characteristics (JSON)
    typical_ocean_profile TEXT,             -- JSON: typical Big Five scores
    typical_voice_markers TEXT,             -- JSON: common voice characteristics

    -- Examples and Guidance
    example_captions TEXT,                  -- JSON array of example captions

    -- Compatibility Mapping
    compatible_archetypes TEXT,             -- JSON array of compatible archetype IDs
    incompatible_archetypes TEXT            -- JSON array of incompatible archetype IDs
);

-- ============================================================================
-- INDEXES: creator_personas_enhanced
-- ============================================================================

-- Unique index on creator_id for fast lookups and FK enforcement
CREATE UNIQUE INDEX IF NOT EXISTS idx_cpe_creator_id
ON creator_personas_enhanced(creator_id);

-- Index for filtering by primary tone
CREATE INDEX IF NOT EXISTS idx_cpe_primary_tone
ON creator_personas_enhanced(primary_tone)
WHERE primary_tone IS NOT NULL;

-- Index for filtering by primary archetype
CREATE INDEX IF NOT EXISTS idx_cpe_primary_archetype
ON creator_personas_enhanced(primary_archetype)
WHERE primary_archetype IS NOT NULL;

-- Index for finding high-quality profiles
CREATE INDEX IF NOT EXISTS idx_cpe_profile_quality
ON creator_personas_enhanced(profile_quality, confidence_score DESC)
WHERE profile_quality IS NOT NULL;

-- ============================================================================
-- INDEXES: creator_voice_samples
-- ============================================================================

-- Index for retrieving all samples for a creator
CREATE INDEX IF NOT EXISTS idx_cvs_creator_id
ON creator_voice_samples(creator_id);

-- Index for retrieving samples by type
CREATE INDEX IF NOT EXISTS idx_cvs_sample_type
ON creator_voice_samples(sample_type);

-- Composite index for active samples by creator (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_cvs_creator_active
ON creator_voice_samples(creator_id, is_active)
WHERE is_active = 1;

-- Index for source tracking and auditing
CREATE INDEX IF NOT EXISTS idx_cvs_source
ON creator_voice_samples(source, collected_at DESC);

-- ============================================================================
-- INDEXES: creator_form_responses
-- ============================================================================

-- Index for matching responses to creators
CREATE INDEX IF NOT EXISTS idx_cfr_creator_id
ON creator_form_responses(creator_id)
WHERE creator_id IS NOT NULL;

-- Index for finding unmatched responses by page name
CREATE INDEX IF NOT EXISTS idx_cfr_page_name
ON creator_form_responses(onlyfans_page_name);

-- Index for processing queue
CREATE INDEX IF NOT EXISTS idx_cfr_processing_status
ON creator_form_responses(processing_status, created_at)
WHERE processing_status IN ('pending', 'needs_review');

-- ============================================================================
-- VIEW: v_enhanced_persona_summary
-- ============================================================================
-- Provides a joined view of enhanced personas with creator metadata
-- for easy reporting, dashboards, and persona management interfaces.

CREATE VIEW IF NOT EXISTS v_enhanced_persona_summary AS
SELECT
    cpe.persona_id,
    cpe.creator_id,
    c.page_name,
    c.display_name AS creator_display_name,
    cpe.preferred_name,
    cpe.display_name AS persona_display_name,
    c.page_type,
    c.current_active_fans,
    c.performance_tier,

    -- Tone Summary
    cpe.primary_tone,
    cpe.secondary_tone,
    cpe.tone_confidence,

    -- Archetype Summary
    cpe.primary_archetype,
    cpe.secondary_archetype,
    cpe.archetype_confidence,

    -- OCEAN Summary
    cpe.openness_score,
    cpe.conscientiousness_score,
    cpe.extraversion_score,
    cpe.agreeableness_score,
    cpe.emotional_expressiveness,

    -- Writing Style Summary
    cpe.emoji_frequency,
    cpe.caption_length_preference,
    cpe.slang_level,

    -- Relationship Summary
    cpe.relationship_style,
    cpe.power_dynamic,
    cpe.emotional_distance,

    -- Data Quality
    cpe.profile_quality,
    cpe.confidence_score,
    cpe.messages_analyzed,
    cpe.voice_samples_count,

    -- Timestamps
    cpe.last_analyzed,
    cpe.last_form_update,
    cpe.created_at,
    cpe.updated_at

FROM creator_personas_enhanced cpe
JOIN creators c ON cpe.creator_id = c.creator_id
ORDER BY c.page_name;

-- ============================================================================
-- VIEW: v_voice_samples_by_creator
-- ============================================================================
-- Aggregates voice samples with counts per type for each creator.
-- Useful for assessing data completeness and sample coverage.

CREATE VIEW IF NOT EXISTS v_voice_samples_by_creator AS
SELECT
    cvs.creator_id,
    c.page_name,
    c.display_name,
    COUNT(*) AS total_samples,
    SUM(CASE WHEN cvs.is_active = 1 THEN 1 ELSE 0 END) AS active_samples,
    SUM(CASE WHEN cvs.sample_type = 'self_description' THEN 1 ELSE 0 END) AS self_description_count,
    SUM(CASE WHEN cvs.sample_type = 'greeting' THEN 1 ELSE 0 END) AS greeting_count,
    SUM(CASE WHEN cvs.sample_type = 'signoff' THEN 1 ELSE 0 END) AS signoff_count,
    SUM(CASE WHEN cvs.sample_type = 'signature_phrase' THEN 1 ELSE 0 END) AS signature_phrase_count,
    SUM(CASE WHEN cvs.sample_type = 'pet_name' THEN 1 ELSE 0 END) AS pet_name_count,
    SUM(CASE WHEN cvs.sample_type = 'solo_ppv_caption' THEN 1 ELSE 0 END) AS solo_ppv_caption_count,
    SUM(CASE WHEN cvs.sample_type = 'bg_ppv_caption' THEN 1 ELSE 0 END) AS bg_ppv_caption_count,
    SUM(CASE WHEN cvs.sample_type = 'bump_caption' THEN 1 ELSE 0 END) AS bump_caption_count,
    SUM(CASE WHEN cvs.sample_type = 'teaser_caption' THEN 1 ELSE 0 END) AS teaser_caption_count,
    SUM(CASE WHEN cvs.sample_type = 'best_caption' THEN 1 ELSE 0 END) AS best_caption_count,
    SUM(CASE WHEN cvs.sample_type = 'unique_style_note' THEN 1 ELSE 0 END) AS unique_style_note_count,
    AVG(cvs.character_count) AS avg_character_count,
    AVG(cvs.word_count) AS avg_word_count,
    AVG(cvs.emoji_count) AS avg_emoji_count,
    AVG(cvs.sentiment_score) AS avg_sentiment,
    MIN(cvs.collected_at) AS first_sample_at,
    MAX(cvs.collected_at) AS latest_sample_at
FROM creator_voice_samples cvs
JOIN creators c ON cvs.creator_id = c.creator_id
GROUP BY cvs.creator_id, c.page_name, c.display_name
ORDER BY total_samples DESC;

-- ============================================================================
-- VIEW: v_form_response_queue
-- ============================================================================
-- Shows pending and needs_review form responses for processing queue.
-- Useful for monitoring form response ingestion and matching.

CREATE VIEW IF NOT EXISTS v_form_response_queue AS
SELECT
    cfr.response_id,
    cfr.onlyfans_page_name,
    cfr.google_form_response_id,
    cfr.response_timestamp,
    cfr.processing_status,
    cfr.creator_id,
    c.page_name AS matched_page_name,
    c.display_name AS matched_display_name,
    cfr.matched_at,
    cfr.created_at
FROM creator_form_responses cfr
LEFT JOIN creators c ON cfr.creator_id = c.creator_id
WHERE cfr.processing_status IN ('pending', 'needs_review', 'failed')
ORDER BY
    CASE cfr.processing_status
        WHEN 'failed' THEN 1
        WHEN 'needs_review' THEN 2
        WHEN 'pending' THEN 3
    END,
    cfr.created_at ASC;

-- ============================================================================
-- TRIGGER: Update updated_at on persona modification
-- ============================================================================
-- Automatically updates the updated_at timestamp whenever a persona is modified.

CREATE TRIGGER IF NOT EXISTS trg_cpe_updated_at
AFTER UPDATE ON creator_personas_enhanced
FOR EACH ROW
BEGIN
    UPDATE creator_personas_enhanced
    SET updated_at = datetime('now')
    WHERE persona_id = NEW.persona_id;
END;

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================
--
-- Post-migration steps:
-- 1. Seed archetype_definitions table with initial archetype data:
--    INSERT INTO archetype_definitions (archetype_id, archetype_name, description, ...)
--    VALUES ('girl_next_door', 'Girl Next Door', 'Approachable, sweet, relatable persona...', ...);
--    (See separate seed script: seed_archetype_definitions.sql)
--
-- 2. Data migration from old creator_personas table (if exists):
--    - Extract existing persona data
--    - Map fields to new enhanced schema
--    - Insert into creator_personas_enhanced
--    - Verify data integrity
--    - Only then consider deprecating old table
--
-- 3. Import existing voice samples from form responses:
--    - Process any existing Google Form responses
--    - Update creator_form_responses status to 'processed'
--    - Link samples to creator_voice_samples
--
-- 4. Verify indexes are being used with EXPLAIN QUERY PLAN:
--    EXPLAIN QUERY PLAN SELECT * FROM creator_personas_enhanced WHERE creator_id = 'test';
--    EXPLAIN QUERY PLAN SELECT * FROM creator_voice_samples WHERE creator_id = 'test' AND is_active = 1;
--
-- 5. Monitor performance and adjust indexes as query patterns emerge
--
-- 6. Consider adding full-text search indexes if text search is needed:
--    CREATE VIRTUAL TABLE IF NOT EXISTS voice_samples_fts USING fts5(
--        sample_text, content='creator_voice_samples', content_rowid='sample_id'
--    );
--
-- ============================================================================
-- ROLLBACK STRATEGY
-- ============================================================================
-- To completely rollback this migration, execute the following in order:
--
-- DROP TRIGGER IF EXISTS trg_cpe_updated_at;
-- DROP VIEW IF EXISTS v_form_response_queue;
-- DROP VIEW IF EXISTS v_voice_samples_by_creator;
-- DROP VIEW IF EXISTS v_enhanced_persona_summary;
-- DROP INDEX IF EXISTS idx_cfr_processing_status;
-- DROP INDEX IF EXISTS idx_cfr_page_name;
-- DROP INDEX IF EXISTS idx_cfr_creator_id;
-- DROP INDEX IF EXISTS idx_cvs_source;
-- DROP INDEX IF EXISTS idx_cvs_creator_active;
-- DROP INDEX IF EXISTS idx_cvs_sample_type;
-- DROP INDEX IF EXISTS idx_cvs_creator_id;
-- DROP INDEX IF EXISTS idx_cpe_profile_quality;
-- DROP INDEX IF EXISTS idx_cpe_primary_archetype;
-- DROP INDEX IF EXISTS idx_cpe_primary_tone;
-- DROP INDEX IF EXISTS idx_cpe_creator_id;
-- DROP TABLE IF EXISTS archetype_definitions;
-- DROP TABLE IF EXISTS creator_form_responses;
-- DROP TABLE IF EXISTS creator_voice_samples;
-- DROP TABLE IF EXISTS creator_personas_enhanced;
--
-- ============================================================================
-- ARCHETYPE SEED DATA NOTES
-- ============================================================================
-- After running this migration, seed the archetype_definitions table with:
--
-- INSERT INTO archetype_definitions VALUES
-- ('girl_next_door', 'Girl Next Door', 'Approachable, sweet, relatable...', ...),
-- ('seductress', 'Seductress', 'Sultry, confident, alluring...', ...),
-- ...etc
--
-- See: database/reference_tables/archetype_seed_data.sql
