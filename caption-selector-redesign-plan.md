 Caption Selection Redesign Plan

 Overview

 Redesign caption selection to prioritize fresh/unused captions guided by historical performance patterns,
 replacing the current "reuse proven winners" approach.

 User Decisions

 - Exclusion window: 60 days (configurable, can adjust to 30-90)
 - New creators: Fall back to global portfolio patterns
 - Exploration: Yes, 10-15% of slots for testing new patterns
 - Unknown content types: Use global content type performance data

 ---
 Architecture Change Summary

 | Aspect        | CURRENT                     | NEW                               |
 |---------------|-----------------------------|-----------------------------------|
 | Philosophy    | Reuse proven winners        | Fresh captions guided by patterns |
 | Exclusion     | Soft (freshness decay)      | Hard 60-day filter                |
 | Earnings data | 55% of weight (direct)      | Pattern guidance only             |
 | Pool system   | PROVEN > GLOBAL > DISCOVERY | Unified pool with tiers           |
 | Exploration   | 10% discovery pool          | 10-15% intentional exploration    |

 ---
 New Weight Formula

 OLD (Current):
 Earnings(55%) + Freshness(15%) + Persona(15%) + Discovery(10%) + Payday(5%)

 NEW (Proposed):
 PatternMatch(40%) + NeverUsedBonus(25%) + Persona(15%) + FreshnessBonus(10%) + Exploration(10%)

 | Component      | Weight | Description                                                            |
 |----------------|--------|------------------------------------------------------------------------|
 | PatternMatch   | 40%    | How well caption attributes match successful patterns for this creator |
 | NeverUsedBonus | 25%    | Flat bonus for captions never sent to this page                        |
 | Persona        | 15%    | Voice matching (tone/emoji/slang alignment)                            |
 | FreshnessBonus | 10%    | Bonus for high freshness scores                                        |
 | Exploration    | 10%    | Random boost for diversity in exploration slots                        |

 ---
 New Selection Flow

 1. LOAD: Query caption_bank with hard 60-day exclusion filter
 2. PROFILE: Load/cache creator's success pattern (or global fallback)
 3. SCORE: Calculate pattern match score for each fresh caption
 4. TIER: Assign freshness tier (never_used > fresh > excluded)
 5. SELECT: Vose Alias weighted selection
 6. EXPLORE: 10-15% of slots select from low-pattern-score captions
 7. VALIDATE: Apply existing business rules

 Freshness Tiers

 | Tier       | Definition                               | Weight Multiplier |
 |------------|------------------------------------------|-------------------|
 | never_used | No record in mass_messages for this page | 1.5x              |
 | fresh      | Last used >60 days ago                   | 1.0x              |
 | excluded   | Last used <60 days ago                   | HARD EXCLUDE      |

 ---
 Pattern Profiling System

 Two-Tier Pattern Extraction

 Tier 1: Combined Patterns (highest accuracy)
 - Extract patterns as combinations: content_type + tone + hook_type
 - Example: {sextape, seductive, curiosity} → avg_earnings: $85
 - Requires 3+ samples per combination

 Tier 2: Individual Attribute Fallback (when sparse)
 - Single attribute statistics: tone: seductive → $65 avg
 - Used when combined patterns have <3 samples

 Global Fallback (for new creators)
 - When creator has <20 sends with earnings
 - Use cross-portfolio patterns with 0.7x discount

 Pattern Profile Data Structure

 @dataclass
 class PatternProfile:
     creator_id: str

     # Combined patterns: "content_type|tone|hook_type" -> stats
     combined_patterns: dict[str, PatternStats]

     # Individual fallbacks
     content_type_patterns: dict[str, PatternStats]
     tone_patterns: dict[str, PatternStats]
     hook_patterns: dict[str, PatternStats]

     # Metadata
     sample_count: int
     confidence: float  # 0.5-1.0
     is_global_fallback: bool
     cached_at: datetime

 @dataclass
 class PatternStats:
     avg_earnings: float
     sample_count: int
     normalized_score: float  # 0-100 percentile

 Caching Strategy

 - LRU cache with 24-hour TTL
 - Max 100 profiles cached
 - Batch pre-load for all 36 creators on startup

 ---
 Exploration Slot Strategy

 For 10-15% of schedule slots, intentionally select diverse patterns:

 1. Select captions with low pattern scores (< 30)
 2. Prioritize never-used captions
 3. Apply diversity bonus for:
   - Unused hook_type in this schedule: +20 points
   - Unused tone in this schedule: +15 points
   - Under-represented content type: +10 points

 Goal: Discover new winning patterns instead of only following historical winners.

 ---
 Key SQL Queries

 Caption Loading with Hard Exclusion

 SELECT
     cb.caption_id,
     cb.caption_text,
     cb.content_type_id,
     cb.tone,
     cb.emoji_style,
     cb.slang_level,
     cb.performance_score,
     cb.freshness_score,
     CASE
         WHEN recent_use.last_sent IS NULL THEN 'never_used'
         WHEN julianday('now') - julianday(recent_use.last_sent) > :exclusion_days THEN 'fresh'
         ELSE 'excluded'
     END AS freshness_tier
 FROM caption_bank cb
 LEFT JOIN (
     SELECT mm.caption_id, MAX(mm.sending_time) AS last_sent
     FROM mass_messages mm
     WHERE mm.creator_id = :creator_id
     GROUP BY mm.caption_id
 ) recent_use ON cb.caption_id = recent_use.caption_id
 WHERE cb.is_active = 1
   AND cb.content_type_id IN (:content_types)
   AND (cb.creator_id = :creator_id OR cb.is_universal = 1)
   -- Hard exclusion
   AND (recent_use.last_sent IS NULL
        OR julianday('now') - julianday(recent_use.last_sent) > :exclusion_days)
 ORDER BY cb.performance_score DESC
 LIMIT 500

 Pattern Extraction Query

 SELECT
     ct.type_name AS content_type,
     cb.tone,
     cb.emoji_style,
     AVG(mm.earnings) AS avg_earnings,
     COUNT(*) AS sample_count
 FROM mass_messages mm
 JOIN caption_bank cb ON mm.caption_id = cb.caption_id
 JOIN content_types ct ON mm.content_type_id = ct.content_type_id
 WHERE mm.creator_id = :creator_id
   AND mm.sending_time >= datetime('now', '-90 days')
   AND mm.earnings > 0
 GROUP BY ct.type_name, cb.tone, cb.emoji_style
 HAVING COUNT(*) >= 3

 ---
 Files to Modify

 | File                        | Lines | Changes                                                        |
 |-----------------------------|-------|----------------------------------------------------------------|
 | scripts/select_captions.py  | 1,933 | Replace pool system, add exclusion filter, new selection logic |
 | scripts/weights.py          | 774   | New weight formula, pattern scoring                            |
 | scripts/schedule_builder.py | ~500  | Integrate pattern profiles, exploration slots                  |
 | scripts/config_loader.py    | ~200  | Add exclusion_days, exploration_ratio configs                  |

 New Files

 | File                          | Purpose                                                            |
 |-------------------------------|--------------------------------------------------------------------|
 | scripts/pattern_extraction.py | Pattern profile building and caching                               |
 | scripts/fresh_selection.py    | New selection algorithm (optional, could be in select_captions.py) |

 ---
 Implementation Waves & Agent Assignments

 Each wave uses specialized agents optimized for the task. Phases within a wave execute in parallel when
 possible.

 ---
 Wave 1: Foundation (Parallel)

 Phase 1A: Data Models

 Agent: python-pro
 Files: scripts/models.py
 Tasks:
 1. Add PatternProfile dataclass with fields:
   - creator_id, combined_patterns, content_type_patterns
   - tone_patterns, hook_patterns, sample_count, confidence
   - is_global_fallback, cached_at
 2. Add PatternStats dataclass with fields:
   - avg_earnings, sample_count, normalized_score
 3. Add ScoredCaption dataclass extending Caption:
   - pattern_score, freshness_tier, never_used_on_page, selection_weight
 4. Add SelectionPool dataclass replacing StratifiedPools
 Success Criteria:
 - All dataclasses have type hints and docstrings
 - Frozen/slots optimizations applied where appropriate
 - Unit test stubs created

 Phase 1B: Configuration

 Agent: python-pro
 Files: scripts/config_loader.py, config/selection.yaml (new)
 Tasks:
 1. Create config/selection.yaml with all new settings
 2. Add config loading in config_loader.py:
   - exclusion_days: int = 60
   - exploration_ratio: float = 0.15
   - min_pattern_samples: int = 3
   - pattern_cache_ttl_hours: int = 24
   - pattern_lookback_days: int = 90
   - use_global_fallback: bool = True
   - global_fallback_discount: float = 0.7
   - use_legacy_weights: bool = False
 3. Add validation for config bounds
 4. Add environment variable overrides
 Success Criteria:
 - Config file created with documented defaults
 - Config loader validates all values
 - EROS_EXCLUSION_DAYS env var works

 ---
 Wave 2: Core Components (Sequential)

 Phase 2A: Pattern Extraction

 Agent: sql-pro
 Files: scripts/pattern_extraction.py (new)
 Tasks:
 1. Implement build_pattern_profile(conn, creator_id):
   - Query combined patterns (content_type + tone + hook)
   - Query individual attribute fallbacks
   - Calculate normalized scores (percentiles)
   - Detect sparse data (<20 sends) for global fallback
 2. Implement build_global_pattern_profile(conn):
   - Cross-creator pattern aggregation
   - Apply 0.7x discount factor
 3. Implement PatternProfileCache:
   - LRU eviction with max_size=100
   - 24-hour TTL per profile
   - Thread-safe access
 4. Add cache warming function for batch pre-load
 Success Criteria:
 - Combined pattern query returns data for test creator
 - Fallback logic triggers when sample_count < 3
 - Cache hits avoid DB query
 - Global fallback works for new creators

 Phase 2B: SQL Query Optimization

 Agent: database-optimizer
 Files: scripts/pattern_extraction.py, assets/sql/ (new queries)
 Tasks:
 1. Create optimized pattern extraction query with proper indexes
 2. Create unified caption loading query with exclusion subquery
 3. Analyze query plans for both queries
 4. Add any missing indexes to schema
 5. Benchmark queries against 20K caption dataset
 Success Criteria:
 - Pattern query < 100ms
 - Caption loading query < 200ms
 - No full table scans

 ---
 Wave 3: Weight System (Parallel)

 Phase 3A: Pattern Scoring Functions

 Agent: python-pro
 Files: scripts/weights.py
 Tasks:
 1. Add calculate_pattern_score(caption, pattern_profile) -> float:
   - Check combined pattern first
   - Fall back to individual attributes
   - Return 0.3 base score when no pattern data
 2. Add calculate_never_used_bonus(caption, creator_id, conn) -> float:
   - Query mass_messages for usage
   - Return 1.5x for never_used, 1.0x for fresh
 3. Add calculate_exploration_weight(caption, schedule_context) -> float:
   - Inverse pattern score
   - Diversity bonus for unused hook/tone/content_type
 4. Update constants:
   - PATTERN_WEIGHT = 0.40
   - NEVER_USED_WEIGHT = 0.25
   - PERSONA_WEIGHT = 0.15
   - FRESHNESS_BONUS_WEIGHT = 0.10
   - EXPLORATION_WEIGHT = 0.10
 Success Criteria:
 - Pattern score returns 0-100 range
 - Never used bonus correctly identifies fresh captions
 - Exploration weight promotes diversity

 Phase 3B: New Weight Formula

 Agent: python-pro
 Files: scripts/weights.py
 Tasks:
 1. Create calculate_fresh_weight() implementing new formula:
 PatternMatch(40%) + NeverUsedBonus(25%) + Persona(15%) + FreshnessBonus(10%) + Exploration(10%)
 2. Add use_legacy_weights flag check
 3. Maintain backward compatibility with old calculate_weight()
 4. Add logging for weight breakdown debugging
 Success Criteria:
 - New formula produces different rankings than old
 - Legacy flag switches to old formula
 - Weight breakdown logged correctly

 ---
 Wave 4: Selection Refactor (Sequential - Critical Path)

 Phase 4A: Caption Loading with Exclusion

 Agent: python-pro
 Files: scripts/select_captions.py
 Tasks:
 1. Create load_unified_pool(conn, creator_id, content_types, exclusion_days):
   - Execute optimized SQL with exclusion subquery
   - Assign freshness_tier to each caption
   - Hard exclude freshness_tier = 'excluded'
   - Return SelectionPool dataclass
 2. Deprecate (don't remove) load_stratified_pools()
 3. Add migration path for gradual rollout
 Success Criteria:
 - Captions used <60 days ago are excluded
 - never_used tier assigned correctly
 - SelectionPool has same interface as old pools

 Phase 4B: Selection Functions

 Agent: python-pro
 Files: scripts/select_captions.py
 Tasks:
 1. Create select_from_unified_pool(pool, pattern_profile, persona, exclude_ids):
   - Calculate pattern scores for all captions
   - Apply freshness tier multipliers
   - Use Vose Alias selection
 2. Create select_exploration_caption(pool, schedule_context):
   - Filter to low pattern score (<30)
   - Apply diversity bonus
   - Weighted selection
 3. Update select_captions() main function:
   - Load pattern profile from cache
   - Reserve 10-15% slots for exploration
   - Use new selection functions
 Success Criteria:
 - Selection prioritizes never_used captions
 - Exploration slots return diverse content
 - No duplicate captions in same week

 ---
 Wave 5: Integration (Sequential)

 Phase 5A: Pipeline Integration

 Agent: python-pro
 Files: scripts/schedule_builder.py, scripts/pipeline.py
 Tasks:
 1. Update Step 1 (ANALYZE):
   - Load pattern profile for creator
   - Warm cache if needed
 2. Update Step 2 (MATCH CONTENT):
   - Use load_unified_pool() instead of load_stratified_pools()
 3. Update Step 5 (ASSIGN CAPTIONS):
   - Calculate exploration slot count (10-15%)
   - Call select_from_unified_pool() for standard slots
   - Call select_exploration_caption() for exploration slots
 4. Add pattern profile to LLM context output
 Success Criteria:
 - Pipeline runs end-to-end with new selection
 - Exploration slots appear in generated schedules
 - Pattern profile visible in context output

 Phase 5B: LLM Context Update

 Agent: python-pro
 Files: scripts/prepare_llm_context.py
 Tasks:
 1. Add pattern profile section to context output:
   - Top performing content types
   - Top performing tones
   - Sample sizes and confidence
 2. Update caption pool analysis section:
   - Show freshness tier distribution
   - Show exploration candidates count
 3. Update analysis instructions for new system
 Success Criteria:
 - Context shows pattern data
 - Freshness tiers visible in output
 - Instructions reflect new selection logic

 ---
 Wave 6: Validation & Testing (Parallel)

 Phase 6A: Unit Tests

 Agent: python-pro
 Files: tests/test_pattern_extraction.py (new), tests/test_fresh_selection.py (new)
 Tasks:
 1. Test pattern extraction:
   - Combined pattern query returns expected data
   - Individual fallback triggers correctly
   - Global fallback activates for new creators
   - Cache hits/misses work correctly
 2. Test weight calculation:
   - Pattern score calculation
   - Never used bonus calculation
   - Exploration weight calculation
   - Full formula integration
 3. Test selection functions:
   - Exclusion filter works (60-day)
   - Freshness tiers assigned correctly
   - Exploration selection diverse
 Success Criteria:
 - 100% test coverage on new functions
 - All edge cases covered
 - Tests pass on CI

 Phase 6B: Integration Tests

 Agent: python-pro
 Files: tests/test_selection_integration.py (new)
 Tasks:
 1. End-to-end schedule generation with new selection
 2. Verify 0% caption reuse within 60 days
 3. Verify exploration slots appear (10-15%)
 4. Verify pattern matching improves over random
 5. Compare old vs new system outputs
 Success Criteria:
 - Full schedule generates without errors
 - Reuse rate = 0% within exclusion window
 - Exploration ratio within bounds

 Phase 6C: Code Review

 Agent: code-reviewer
 Files: All modified files
 Tasks:
 1. Review all new code for:
   - Type safety and annotations
   - Error handling
   - SQL injection prevention
   - Performance concerns
   - Documentation completeness
 2. Verify backward compatibility
 3. Check for breaking changes
 Success Criteria:
 - No security issues
 - All functions documented
 - Type hints complete
 - No breaking changes to public API

 ---
 Execution Summary

 | Wave | Phases     | Agents                                | Parallel   | Dependencies |
 |------|------------|---------------------------------------|------------|--------------|
 | 1    | 1A, 1B     | python-pro, python-pro                | Yes        | None         |
 | 2    | 2A, 2B     | sql-pro, database-optimizer           | Sequential | Wave 1       |
 | 3    | 3A, 3B     | python-pro, python-pro                | Yes        | Wave 2       |
 | 4    | 4A, 4B     | python-pro, python-pro                | Sequential | Wave 3       |
 | 5    | 5A, 5B     | python-pro, python-pro                | Sequential | Wave 4       |
 | 6    | 6A, 6B, 6C | python-pro, python-pro, code-reviewer | Yes        | Wave 5       |

 Critical Path: Wave 1 → Wave 2 → Wave 3 → Wave 4 → Wave 5 → Wave 6

 Parallel Opportunities:
 - Wave 1: Phases 1A and 1B can run simultaneously
 - Wave 3: Phases 3A and 3B can run simultaneously
 - Wave 6: All three phases can run simultaneously

 ---
 Configuration Options

 # config/selection.yaml

 selection:
   # Hard exclusion window (days)
   exclusion_days: 60

   # Exploration slot ratio
   exploration_ratio: 0.15

   # Pattern extraction
   min_pattern_samples: 3
   pattern_lookback_days: 90

   # Caching
   pattern_cache_ttl_hours: 24
   pattern_cache_max_size: 100

   # Fallback behavior
   use_global_fallback: true
   global_fallback_discount: 0.7

   # Legacy mode (for gradual rollout)
   use_legacy_weights: false

 ---
 Risk Mitigation

 | Risk                        | Mitigation                                               |
 |-----------------------------|----------------------------------------------------------|
 | Not enough fresh captions   | Warning when <20 available, fallback to 30-day exclusion |
 | Pattern data sparse         | Global fallback at 0.7x discount                         |
 | Performance regression      | Legacy mode flag, A/B testing capability                 |
 | Breaking existing schedules | Gradual rollout per creator                              |
 | Slow generation             | Pattern caching, SQL optimization                        |

 ---
 Success Metrics

 | Metric                       | Current       | Target              |
 |------------------------------|---------------|---------------------|
 | Caption reuse within 60 days | ~40%          | 0% (hard exclusion) |
 | Never-used caption rate      | ~20%          | >60%                |
 | Exploration slots            | 10% discovery | 10-15% intentional  |
 | Pattern match coverage       | N/A           | >70% of selections  |
 | Generation time              | <30s          | <35s (acceptable)   |
 | Validation pass rate         | 100%          | 100% (unchanged)    |
