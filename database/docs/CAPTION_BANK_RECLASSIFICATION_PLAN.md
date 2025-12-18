# CAPTION BANK RECLASSIFICATION EXECUTION PLAN

## Project Overview

**Objective:** Fully reclassify all 59,405 captions in the caption_bank table using ONLY the taxonomies defined in:
- `content_types.json` (39 content types)
- `send_types.json` (21 send types across 3 categories)

**Current State:** 22 legacy caption_types, 37 content_type_ids with 1.1% NULL values
**Target State:** 100% alignment with canonical JSON taxonomy files

---

## CANONICAL TAXONOMIES

### Content Types (39 Types) - From content_types.json

| Category | Content Types |
|----------|---------------|
| **Explicit Solo** | solo, pussy_play, tits_play, toy_play, squirt |
| **Explicit Oral** | blowjob, deepthroat, blowjob_dildo, deepthroat_dildo |
| **Explicit Couples** | boy_girl, girl_girl, boy_girl_girl, girl_girl_girl, creampie, anal |
| **Interactive** | joi, dick_rating, gfe |
| **Fetish/Themed** | dom_sub, feet, lingerie, shower_bath, pool_outdoor, pov, story_roleplay |
| **Implied/Teasing** | implied_solo, implied_pussy_play, implied_tits_play, implied_toy_play, teasing |
| **Promotional** | bundle_offer, flash_sale, exclusive_content, live_stream, behind_scenes |
| **Engagement** | tip_request, renewal_retention |

### Send Types (21 Types) - From send_types.json

| Category | Send Type | Purpose |
|----------|-----------|---------|
| **Revenue & Sales (7)** | vip_post | VIP program promotion |
| | ppv_post | Pay-per-view video sales |
| | game_post | Gamified buying opportunities |
| | bundle_post | Content bundle offers |
| | flash_bundle_post | Limited-quantity urgency bundles |
| | snapchat_bundle | Throwback Snapchat nudes |
| | first_to_tip_post | Gamified tip incentives |
| **Engagement & Bumps (9)** | link_drop | Push previous posts to feeds |
| | wall_post_link_drop | Wall campaign promotion |
| | normal_bump | Flirty DM enticement |
| | descriptive_bump | Storytelling-driven DMs |
| | text_only_bump | Quick no-media engagement |
| | flyer_gif_bump | High-visibility designed media |
| | dm_farm | Immediate DM triggers |
| | like_farm | Engagement metric boosting |
| | live_promo | Livestream notifications |
| **Retention & Backend (5)** | renew_on_post | Auto-renewal encouragement (paid only) |
| | renew_on_message | Mass message renewal targeting |
| | ppv_unlock_message | Mass PPV/unlock delivery |
| | ppv_followup | Close-the-sale follow-ups |
| | expired_subscriber_message | Win-back campaigns (paid only) |

---

## WAVE EXECUTION ARCHITECTURE

### Wave 0: Pre-Flight Preparation
**Duration:** Single execution
**Purpose:** Establish safety nets and validation baselines

```
AGENTS DEPLOYED:
├── database-backup-agent
│   └── Creates timestamped backup of caption_bank
├── schema-validator-agent
│   └── Validates JSON taxonomy files against DB schema
└── baseline-metrics-agent
    └── Records current distribution for comparison
```

**Deliverables:**
- [ ] Full backup: `caption_bank_backup_reclassification_YYYYMMDD`
- [ ] Schema validation report
- [ ] Baseline metrics snapshot (CSV export)

---

### Wave 1: Content Type Classification
**Purpose:** Assign correct content_type from 39 canonical types to ALL captions
**Parallelization:** 8 concurrent agents by content category

```
AGENTS DEPLOYED (Parallel):
├── explicit-solo-classifier
│   └── Patterns: solo, pussy_play, tits_play, toy_play, squirt
├── explicit-oral-classifier
│   └── Patterns: blowjob, deepthroat, *_dildo
├── explicit-couples-classifier
│   └── Patterns: boy_girl, girl_girl, *_girl_girl, creampie, anal
├── interactive-classifier
│   └── Patterns: joi, dick_rating, gfe
├── fetish-themed-classifier
│   └── Patterns: dom_sub, feet, lingerie, shower_bath, pool_outdoor, pov, story_roleplay
├── implied-teasing-classifier
│   └── Patterns: implied_*, teasing
├── promotional-classifier
│   └── Patterns: bundle_offer, flash_sale, exclusive_content, live_stream, behind_scenes
└── engagement-classifier
    └── Patterns: tip_request, renewal_retention
```

**Strategy:**
1. Each agent analyzes caption_text using NLP pattern matching
2. Cross-reference against existing content_type_id (if not NULL)
3. Assign highest-confidence content_type from canonical 39
4. Flag ambiguous captions (confidence < 0.7) for Wave 4 review

**Success Criteria:**
- [ ] 100% of captions have non-NULL content_type
- [ ] All content_types are from canonical 39 list
- [ ] Confidence score > 0.7 for 95%+ captions

---

### Wave 2: Send Type Classification
**Purpose:** Map caption_type field to canonical 21 send types
**Parallelization:** 3 concurrent agents by category

```
AGENTS DEPLOYED (Parallel):
├── revenue-send-type-classifier
│   └── Maps to: vip_post, ppv_post, game_post, bundle_post, flash_bundle_post, snapchat_bundle, first_to_tip_post
├── engagement-send-type-classifier
│   └── Maps to: link_drop, wall_post_link_drop, normal_bump, descriptive_bump, text_only_bump, flyer_gif_bump, dm_farm, like_farm, live_promo
└── retention-send-type-classifier
    └── Maps to: renew_on_post, renew_on_message, ppv_unlock_message, ppv_followup, expired_subscriber_message
```

**Mapping Rules:**

| Legacy caption_type | New send_type |
|--------------------|---------------|
| ppv_unlock | ppv_unlock_message |
| ppv | ppv_post |
| ppv_followup | ppv_followup |
| flirty_opener | normal_bump |
| descriptive_tease | descriptive_bump |
| normal_bump | normal_bump |
| engagement | dm_farm |
| mood_check | text_only_bump |
| tell_me | dm_farm |
| renewal_reminder | renew_on_message |
| general | normal_bump |
| tip_campaign | first_to_tip_post |
| custom_promo | bundle_post |
| live_promo | live_promo |
| vip_promo | vip_post |
| dick_rating | ppv_post |
| sexting_promo | ppv_post |
| vidcall_promo | ppv_post |
| feed_bump | flyer_gif_bump |
| teaser | normal_bump |
| promo | bundle_post |
| expired_winback | expired_subscriber_message |

**Strategy:**
1. Apply deterministic mapping rules for high-confidence legacy types
2. Analyze caption_text semantics for ambiguous cases
3. Validate page_type constraints (retention types only for paid pages)
4. Update caption_type field with canonical send_type key

**Success Criteria:**
- [ ] All 22 legacy caption_types mapped
- [ ] 100% of captions have valid send_type from canonical 21
- [ ] Retention types verified against page_type constraints

---

### Wave 3: Cross-Validation & Relationship Integrity
**Purpose:** Ensure content_type + send_type combinations are valid
**Parallelization:** 4 concurrent validation agents

```
AGENTS DEPLOYED (Parallel):
├── content-send-compatibility-validator
│   └── Validates content_type × send_type allowed combinations
├── page-type-constraint-validator
│   └── Ensures retention sends only on paid pages
├── foreign-key-integrity-validator
│   └── Verifies all IDs reference valid master records
└── duplicate-detection-validator
    └── Identifies duplicate captions with different classifications
```

**Validation Rules:**
1. **Revenue send types** should match promotional/explicit content types
2. **Engagement send types** should match teasing/implied content types
3. **Retention send types** should match renewal_retention content type
4. **PPV types** can have ANY content_type (flexible)

**Success Criteria:**
- [ ] Zero orphaned foreign key references
- [ ] Zero retention sends assigned to free page creators
- [ ] < 5% incompatible content_type × send_type combinations

---

### Wave 4: Human-in-the-Loop Review
**Purpose:** Resolve low-confidence and edge-case classifications
**Parallelization:** Single coordinating agent with batch processing

```
AGENTS DEPLOYED (Sequential):
├── ambiguity-prioritizer-agent
│   └── Ranks low-confidence captions by impact (usage, performance_score)
├── batch-review-presenter-agent
│   └── Presents batches of 50 captions for human review
└── review-integration-agent
    └── Applies human decisions back to database
```

**Review Criteria (Captions flagged if ANY):**
- classification_confidence < 0.7
- Multiple valid content_type candidates
- Caption_text length < 20 chars (insufficient signal)
- Performance_score in top 5% (high-value captions)

**Success Criteria:**
- [ ] All flagged captions reviewed or approved by rules
- [ ] Manual review classification_method = 'manual_reclassification'
- [ ] Confidence scores updated to reflect review

---

### Wave 5: Quality Assurance & Metrics
**Purpose:** Final validation and before/after comparison
**Parallelization:** 3 concurrent QA agents

```
AGENTS DEPLOYED (Parallel):
├── distribution-comparison-agent
│   └── Compares before/after taxonomy distributions
├── coverage-completeness-agent
│   └── Ensures 100% coverage with no NULL values
└── performance-preservation-agent
    └── Verifies no performance_score data was lost
```

**Metrics to Capture:**

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| NULL content_type_id | 656 | 0 | -656 |
| Unique caption_types | 22 | 21 | -1 |
| Unique content_types | 37 | 39 | +2 |
| Avg classification_confidence | 0.5 | 0.85+ | +0.35 |
| Unmapped caption_types | 22,348 | 0 | -22,348 |

**Success Criteria:**
- [ ] Zero NULL values in content_type or send_type columns
- [ ] 100% of values from canonical JSON lists
- [ ] Confidence improvement > 30 percentage points

---

### Wave 6: Migration & Cleanup
**Purpose:** Finalize changes and update dependent systems
**Parallelization:** Sequential (dependencies)

```
AGENTS DEPLOYED (Sequential):
├── send-type-caption-requirements-updater
│   └── Updates mapping table with new taxonomy
├── vault-matrix-synchronizer
│   └── Ensures vault_matrix reflects new content_types
├── legacy-backup-archiver
│   └── Archives old classification data for rollback
└── documentation-updater
    └── Updates SEND_TYPE_REFERENCE.md and related docs
```

**Cleanup Tasks:**
1. Drop legacy caption_type values not in canonical list
2. Update `send_type_caption_requirements` table
3. Regenerate `caption_classifications` audit records
4. Update migration version number

**Success Criteria:**
- [ ] All dependent tables updated
- [ ] Documentation reflects new taxonomy
- [ ] Rollback procedure documented and tested

---

## AGENT DEPLOYMENT SUMMARY

| Wave | Agents | Parallelism | Est. Captions/Wave |
|------|--------|-------------|-------------------|
| 0 | 3 | Sequential | N/A (setup) |
| 1 | 8 | Parallel | 59,405 |
| 2 | 3 | Parallel | 59,405 |
| 3 | 4 | Parallel | 59,405 (validation) |
| 4 | 3 | Sequential | ~3,000 (flagged) |
| 5 | 3 | Parallel | 59,405 (QA) |
| 6 | 4 | Sequential | N/A (cleanup) |
| **TOTAL** | **28** | Mixed | **59,405 classified** |

---

## ROLLBACK PROCEDURE

If any wave fails critical success criteria:

1. **Immediate:** Halt all subsequent waves
2. **Assess:** Review failure logs and impact scope
3. **Restore:** Use backup from Wave 0
   ```sql
   DROP TABLE caption_bank;
   ALTER TABLE caption_bank_backup_reclassification_YYYYMMDD
     RENAME TO caption_bank;
   ```
4. **Post-mortem:** Document failure cause and remediation

---

## EXECUTION COMMANDS

```bash
# Wave 0: Pre-flight
/eros:backup caption_bank
/eros:validate-taxonomy

# Wave 1: Content Type Classification
/eros:classify content --parallel 8 --batch-size 1000

# Wave 2: Send Type Classification
/eros:classify send_type --parallel 3 --batch-size 1000

# Wave 3: Cross-Validation
/eros:validate relationships --parallel 4

# Wave 4: Human Review
/eros:review flagged --batch-size 50

# Wave 5: Quality Assurance
/eros:qa compare --baseline wave0_metrics.csv

# Wave 6: Migration
/eros:migrate apply --version reclassification_v1
```

---

## SUCCESS METRICS

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Coverage** | 100% | Zero NULL content_type or send_type |
| **Accuracy** | 95%+ | Based on manual sample validation |
| **Confidence** | 0.85+ avg | classification_confidence field |
| **Taxonomy Compliance** | 100% | Only canonical values present |
| **Performance Preservation** | 100% | No performance_score data loss |
| **Execution Time** | < 4 hours | Full pipeline completion |

---

## APPENDIX A: Legacy to Canonical Mapping Reference

### Caption Type Migration Map

```
LEGACY (22 types)              CANONICAL SEND TYPE (21 types)
─────────────────────────────────────────────────────────────
ppv_unlock (19,493)        →   ppv_unlock_message
flirty_opener (17,774)     →   normal_bump
descriptive_tease (14,535) →   descriptive_bump
renewal_reminder (2,108)   →   renew_on_message
general (1,269)            →   normal_bump
normal_bump (1,217)        →   normal_bump
engagement (1,073)         →   dm_farm
mood_check (470)           →   text_only_bump
tell_me (466)              →   dm_farm
tip_campaign (330)         →   first_to_tip_post
custom_promo (154)         →   bundle_post
live_promo (140)           →   live_promo
vip_promo (118)            →   vip_post
ppv_followup (112)         →   ppv_followup
ppv (55)                   →   ppv_post
dick_rating (28)           →   ppv_post
sexting_promo (23)         →   ppv_post
vidcall_promo (15)         →   ppv_post
feed_bump (13)             →   flyer_gif_bump
teaser (4)                 →   normal_bump
promo (4)                  →   bundle_post
expired_winback (4)        →   expired_subscriber_message
```

### Content Type Canonical List (39 types)

```
CATEGORY                   CONTENT TYPES
─────────────────────────────────────────
Explicit                   anal, blowjob, blowjob_dildo, boy_girl,
                          boy_girl_girl, creampie, deepthroat,
                          deepthroat_dildo, girl_girl, girl_girl_girl,
                          pussy_play, solo, squirt, tits_play, toy_play

Interactive               dick_rating, gfe, joi

Fetish/Themed             behind_scenes, dom_sub, feet, lingerie,
                          live_stream, pool_outdoor, pov, shower_bath,
                          story_roleplay

Implied/Teasing           implied_pussy_play, implied_solo,
                          implied_tits_play, implied_toy_play, teasing

Promotional               bundle_offer, exclusive_content, flash_sale

Engagement                renewal_retention, tip_request
```

---

## APPENDIX B: Agent Capability Requirements

### Classification Agents (Waves 1-2)
- **Input:** caption_text, existing metadata
- **Output:** content_type OR send_type, confidence_score
- **Capabilities:** NLP pattern matching, semantic analysis, confidence scoring
- **Batch Size:** 1,000 captions per invocation
- **Timeout:** 60 seconds per batch

### Validation Agents (Wave 3)
- **Input:** Full caption_bank table
- **Output:** Validation report, flagged records
- **Capabilities:** SQL queries, constraint checking, relationship validation
- **Batch Size:** Full table scan
- **Timeout:** 120 seconds

### QA Agents (Wave 5)
- **Input:** Before/after metrics
- **Output:** Comparison report, pass/fail status
- **Capabilities:** Statistical comparison, coverage analysis
- **Batch Size:** N/A (aggregate metrics)
- **Timeout:** 30 seconds

---

**Document Version:** 1.0.0
**Created:** 2025-12-15
**Author:** EROS Schedule Generator System
**Status:** READY FOR EXECUTION
