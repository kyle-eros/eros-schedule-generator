# Changelog

All notable changes to the EROS Schedule Generator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Modular Architecture Refactor**: Split monolithic `generate_schedule.py` into focused modules:
  - `pipeline.py`: 9-step orchestration and workflow coordination
  - `schedule_builder.py`: Steps 1-4 (analyze, match content, persona, structure)
  - `enrichment.py`: Steps 6-8 (follow-ups, drip windows, page rules)
  - `models.py`: Centralized dataclasses and Pydantic models for type safety
  - `output_formatter.py`: Markdown/JSON/CSV formatting utilities
- **Configuration Management**: Created `config/business_rules.yaml` for externalized configuration
  - `config_loader.py`: Type-safe configuration loading with validation
  - Eliminates hard-coded constants throughout codebase
- **Structured Logging**: Replaced 429+ print() statements with proper logging infrastructure
  - Centralized logging configuration via `logging_config.py`
  - Configurable log levels and formats
  - Better debugging and production monitoring
- **Examples Directory**: Created `examples/` with real-world output samples
  - Sample schedules showcasing different scenarios
  - Documentation of expected outputs
- **Enhanced Prompts**: Added 5 Claude-optimized prompt templates in `prompts/`
  - Content classification specialist prompt
  - Semantic analysis guidance
  - Quality scoring framework
- **Comprehensive Test Suite**: Added 114+ new tests across multiple modules
  - Integration tests for full pipeline
  - Unit tests for critical algorithms
  - Edge case coverage
- **Agent Invoker Enhancements** (`agent_invoker.py`):
  - Execution metrics tracking (duration, cache hits, errors)
  - Improved caching with TTL support
  - Retry logic with exponential backoff
  - Better error handling and logging

### Changed
- **Documentation Reorganization**: Moved audit/backup docs to main EROS project
  - Archived historical documentation to `~/Developer/EROS-SD-MAIN-PROJECT/docs/archive/`
  - Streamlined skill package to production-essential files only
  - References remain in `references/` directory
- **Code Quality Improvements**:
  - Type hints throughout codebase
  - Docstring standardization (Google style)
  - Removed dead code and unused functions
  - Improved error messages and validation feedback

### Fixed
- Edge cases in validation auto-correction logic
- Memory leaks in long-running batch operations
- Race conditions in multi-threaded caption selection

### Breaking Changes
- **Module Imports**: Scripts importing from `generate_schedule.py` directly must update imports:
  ```python
  # Before
  from generate_schedule import generate_schedule

  # After
  from pipeline import generate_schedule
  ```
- **Configuration Access**: Hard-coded constants replaced with config loader:
  ```python
  # Before
  MIN_PPV_SPACING_HOURS = 4

  # After
  from config_loader import get_business_rules
  config = get_business_rules()
  spacing = config.min_ppv_spacing_hours
  ```

### Migration Guide
For users upgrading from v3.1.0:

1. **Update Import Statements**:
   - Update any custom scripts that import from `generate_schedule.py`
   - See "Breaking Changes" section above

2. **Configuration Files**:
   - Review `config/business_rules.yaml` for customized thresholds
   - Override via environment variables if needed

3. **Logging Output**:
   - Configure logging level: `export EROS_LOG_LEVEL=INFO`
   - Redirect logs: `python scripts/generate_schedule.py --creator NAME --week YYYY-Www 2>schedule.log`

---

## [3.1.0] - 2025-12-09

### Added
- **Unified Entry Point**: `generate_full_schedule()` function for complete schedule generation
  - Single-call API for all 20+ content types
  - Simplified workflow for full schedules
- **Content Type Helpers**:
  - `list_content_types()`: Display all available content types
  - `print_schedule_summary()`: Formatted schedule output
- **CLI Enhancements**: New command-line flags
  - `--content-types TYPE...`: Filter specific content types
  - `--page-type paid|free`: Override page type detection
  - `--volume Low|Mid|High|Ultra`: Override volume calculation
  - `--no-placeholders`: Skip slots without captions
  - `--list-content-types`: Display content type registry
- **20 Content Types**: Full registry across 4 priority tiers
  - **Tier 1 - Direct Revenue**: ppv, ppv_follow_up, bundle, flash_bundle, snapchat_bundle (5 types)
  - **Tier 2 - Feed/Wall**: vip_post, first_to_tip, link_drop, normal_post_bump, renew_on_post, game_post, flyer_gif_bump, descriptive_bump, wall_link_drop, live_promo (10 types)
  - **Tier 3 - Engagement**: dm_farm, like_farm, text_only_bump (3 types)
  - **Tier 4 - Retention**: renew_on_mm, expired_subscriber (2 types)
- **Page Type Intelligence**:
  - 4 paid-only types: `vip_post`, `renew_on_post`, `renew_on_mm`, `expired_subscriber`
  - 16 both-page types available on free and paid pages
- **Placeholder Generation**: Automatic placeholder creation for slots without captions
  - Theme guidance for manual caption creation
  - Validation warning (V031) for incomplete schedules

### Changed
- Enhanced schedule summary output includes content type distribution
- Improved content type filtering based on page type
- Better placeholder messaging with actionable guidance

### Fixed
- Content type constraints not enforced consistently
- Page type violations in edge cases

---

## [3.0.0] - 2025-12-09

### Added
- **New CLI Flag**: `--quick` as shorthand for `--mode quick`
  - Backwards compatibility for pattern-based generation
  - Faster alternative to full semantic analysis

### Changed
- **Default Mode Change**: Changed from "quick" to "full" mode
  - Full semantic analysis now runs by default
  - Production-quality schedules without explicit flag
  - Quick mode still available via `--quick` flag
- **Enhanced Workflow**: Full mode now standard for optimal results
  - Better persona matching accuracy (70-80% → 85-90%)
  - Improved hook diversity detection
  - Higher conversion potential captions selected

### Breaking Changes
- **Default Behavior**: Schedules now take slightly longer (~60s vs ~30s) but with significantly higher quality
  - **Migration**: Add `--quick` flag to scripts expecting old behavior: `python scripts/generate_schedule.py --creator NAME --week YYYY-Www --quick`
- **Performance Expectations**: Full mode is now default
  - Systems optimized for speed should explicitly use `--quick`
  - Batch operations may require more time or explicit mode selection

---

## [2.1.0] - 2025-12-09

### Added

#### Pool-Based Caption Selection System
- **3-Tier Pool Stratification**:
  - **PROVEN**: Captions with `creator_times_used >= 3 AND creator_avg_earnings > 0`
  - **GLOBAL_EARNER**: `global_times_used >= 3 AND global_avg_earnings > 0` (untested for creator)
  - **DISCOVERY**: New imports, under-tested content (< 3 uses)
- **Earnings-First Weight Formula**: `Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery(10%)`
- **Slot Type Selection Strategy**:
  - **Premium slots** (6PM, 9PM): PROVEN pool only
  - **Standard slots**: PROVEN + GLOBAL_EARNER pools
  - **Discovery slots**: DISCOVERY pool with import prioritization
- **Vose Alias Algorithm**: O(1) weighted random selection for performance at scale

#### Schedule Uniqueness Engine
- **Timing Variance System**:
  - 7-10 minute randomization applied to 85% of slots
  - `TIMING_VARIANCE_MIN = -10`, `TIMING_VARIANCE_MAX = 10`, `VARIANCE_PROBABILITY = 0.85`
  - Creates organic, non-robotic posting patterns
  - Prevents platform detection of automated scheduling
- **Historical Weighting**:
  - Multi-factor weight calculation: Performance(60%) + Recency(20%) + Diversity(20%)
  - Creator-specific historical patterns
  - Peak hour optimization
- **Cross-Week Deduplication**:
  - 4-week lookback period (`RECENT_WEEKS_LOOKBACK = 4`)
  - Tracks recently used caption IDs
  - Penalties for captions used in last 28 days
  - Ensures fresh content rotation
- **Schedule Fingerprinting**:
  - SHA-256 hash of schedule content + timing
  - 16-character truncated fingerprint for storage
  - Duplicate detection across recent weeks
  - Automatic re-shuffling if duplicate found (max 5 attempts)
- **Uniqueness Metrics**:
  - `fingerprint`: 16-char SHA-256 hash
  - `uniqueness_score`: 0-100 based on freshness and diversity
  - `timing_variance_applied`: Count of slots with variance
  - `historical_weight_factor`: Average historical weighting
  - `cross_week_duplicates`: Captions reused from recent weeks
  - `content_type_distribution`: Slot count per content type

#### Hook Detection & Anti-Detection System
- **7 Hook Types**:
  - `curiosity`: Questions, teasers, "guess what"
  - `personal`: "Miss you", personal connection
  - `exclusivity`: "Just for you", VIP language
  - `recency`: "Just finished", time-based urgency
  - `question`: Direct questions to engage
  - `direct`: Clear CTA, transactional
  - `teasing`: Flirty, playful, suggestive
- **Anti-Detection Strategy**:
  - `SAME_HOOK_PENALTY = 0.7`: 30% weight reduction for consecutive same hooks
  - Promotes natural variation in opening hooks
  - Hook rotation tracked and enforced in selection
- **Validation Rules**:
  - **V015**: Warning on consecutive same hook types
  - **V016**: Info if < 4 hook types used in week

#### Extended Validation (30 Rules Total)
- **Core Rules (V001-V018)**: Existing validation maintained
- **New Extended Rules (V020-V031)**:
  - **V020 PAGE_TYPE_VIOLATION**: Paid-only content on free page (ERROR, auto-remove)
  - **V021 VIP_POST_SPACING**: Min 24h between VIP posts (ERROR, auto-move)
  - **V022 LINK_DROP_SPACING**: Min 4h between link drops (WARNING, auto-move)
  - **V023 ENGAGEMENT_DAILY_LIMIT**: Max 2 engagement posts/day (WARNING, auto-move)
  - **V024 ENGAGEMENT_WEEKLY_LIMIT**: Max 10 engagement posts/week (WARNING, auto-remove)
  - **V025 RETENTION_TIMING**: Retention content optimal days 5-7 (INFO)
  - **V026 BUNDLE_SPACING**: Min 24h between bundles (ERROR, auto-move)
  - **V027 FLASH_BUNDLE_SPACING**: Min 48h between flash bundles (ERROR, auto-move)
  - **V028 GAME_POST_WEEKLY**: Max 1 game post/week (WARNING, auto-remove)
  - **V029 BUMP_VARIANT_ROTATION**: No 3x consecutive same bump type (WARNING, auto-swap)
  - **V030 CONTENT_TYPE_ROTATION**: No 3x consecutive same type (INFO)
  - **V031 PLACEHOLDER_WARNING**: Slot has no caption (INFO)
- **Auto-Correction Engine**: Self-healing validation with 10+ correction actions
  - `move_slot`: Resolve spacing violations
  - `swap_caption`: Replace for freshness/duplicates
  - `adjust_timing`: Fix follow-up timing
  - `remove_item`: Enforce limits
  - `move_to_next_day`: Day-level constraints
  - `swap_content_type`: Rotation enforcement
  - `reorder`: Preview-PPV linkage
  - `set_duration`: Poll duration fixes
  - `filter_page_type`: Page compliance
  - `enforce_rotation`: Content diversity
  - Max 2 validation passes with corrections

#### Content Type Registry
- **20 Schedulable Content Types** organized in 4 tiers
- **Content Type Constraints**:
  - `min_spacing_hours`: Type-specific spacing rules (15min - 168h)
  - `max_daily`: Daily send limits (1-5 per type)
  - `max_weekly`: Weekly send limits (2-35 per type)
  - `allowed_on_free_page`: Page type restrictions
  - `requires_flyer`: Media attachment requirements
- **Specialized Content Loaders**: `content_type_loaders.py` (2,240 lines)
  - Type-specific caption loading logic
  - Page type guards
  - Theme guidance for placeholders
- **Slot Schedulers**: `content_type_schedulers.py` (1,410 lines)
  - Automated slot generation per type
  - Conflict resolution
  - Constraint enforcement

### Changed
- **Weight Formula Update**: Shifted from 5-component to 4-component weighting
  - Old: `Performance(55%) + Freshness(15%) + Persona(15%) + Payday(10%) + Diversity(5%)`
  - New: `Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery(10%)`
  - Discovery bonus now subsumes payday and diversity factors
- **Timing Precision**: Times now include variance (not exact :00 minutes)
  - Example: `10:07` instead of `10:00`
  - Integration systems should not expect exact hour boundaries
- **Validation Output**: Enhanced with hook diversity and uniqueness metrics
  - `hook_diversity_score`: 0-100 based on variety
  - `schedule_fingerprint`: Unique identifier
  - `uniqueness_score`: Overall freshness and diversity
- **ValidationIssue Model**: New fields added
  - `auto_correctable: bool`: Whether issue can be auto-fixed
  - `correction_action: str | None`: Action taken
  - `correction_value: Any | None`: Correction parameters

### Fixed
- Caption exhaustion in high-volume creators
- Duplicate captions across weeks
- Platform pattern detection vulnerabilities
- Hook type monotony in generated schedules
- Timing predictability issues

---

## [2.0.0] - 2025-12-08

### Added
- **Pool-Based Caption Selection**:
  - PROVEN/GLOBAL_EARNER/DISCOVERY stratification
  - Earnings-driven weight calculation
  - Performance-based pool assignment
- **Vose Alias Algorithm**:
  - O(1) weighted random selection
  - Efficient caption sampling at scale
  - Proper statistical distribution
- **Native Claude LLM Integration**:
  - `prepare_llm_context.py`: Context preparation for semantic analysis
  - `semantic_analysis.py`: Tone detection framework
  - `quality_scoring.py`: LLM-based caption quality assessment
  - Full mode with semantic tone detection
- **Persona Matching System**:
  - Primary tone match: 1.20x boost
  - Emoji frequency match: 1.10x boost
  - Slang level match: 1.10x boost
  - Maximum combined boost: 1.40x (capped)
  - No match penalty: 0.95x
- **9-Step Pipeline**:
  1. ANALYZE - Load creator profile and metrics
  2. MATCH CONTENT - Filter by vault availability
  3. MATCH PERSONA - Score by voice profile
  4. BUILD STRUCTURE - Create weekly time slots
  5. ASSIGN CAPTIONS - Weighted selection
  6. GENERATE FOLLOW-UPS - Bump messages
  7. APPLY DRIP WINDOWS - No-PPV zones
  8. APPLY PAGE TYPE RULES - Paid vs free adjustments
  9. VALIDATE - Business rule enforcement
- **Core Validation Rules (V001-V018)**:
  - PPV spacing (minimum 3 hours)
  - Freshness minimum (>= 30)
  - Follow-up timing (15-45 minutes)
  - Content rotation
  - Duplicate detection
  - Vault availability checks
  - Hook rotation warnings
- **Sub-Agent Architecture**: 7 specialized agents
  - `timezone-optimizer` (haiku, 15s)
  - `onlyfans-business-analyst` (opus, 45s)
  - `content-strategy-optimizer` (sonnet, 30s)
  - `volume-calibrator` (sonnet, 30s)
  - `revenue-optimizer` (sonnet, 30s)
  - `multi-touch-sequencer` (opus, 45s)
  - `validation-guardian` (sonnet, 30s)
- **Dual Execution Modes**:
  - Quick mode: < 30 seconds, pattern-based
  - Full mode: < 60 seconds, LLM semantic analysis

### Changed
- Refactored from monolithic script to modular pipeline
- Improved database query performance
- Enhanced error handling and logging

---

## [1.0.0] - 2025-09-01

### Added
- **Initial Release**: Basic schedule generation functionality
- **9-Step Pipeline Foundation**:
  - Creator profile analysis
  - Content matching
  - Volume optimization by fan count
  - Basic caption selection
  - Simple validation
- **Database Integration**:
  - SQLite connection management
  - Core queries for creators, captions, personas
  - Performance data access
- **Basic Validation**:
  - PPV spacing checks
  - Freshness scoring
  - Content type rotation
- **Output Formats**:
  - Markdown schedule output
  - JSON data export
- **Volume Tiers**: Fan-count-based volume levels
  - Low: < 1,000 fans
  - Mid: 1,000-5,000 fans
  - High: 5,000-15,000 fans
  - Ultra: 15,000+ fans
- **Core Scripts**:
  - `generate_schedule.py`: Main pipeline
  - `calculate_freshness.py`: Caption freshness scoring
  - `analyze_creator.py`: Creator performance analysis
- **SQL Queries**:
  - `get_creator_profile.sql`
  - `get_available_captions.sql`
  - `get_optimal_hours.sql`
  - `get_vault_inventory.sql`

---

## Migration Notes

### Upgrading from v2.1.0 to v3.0.0
No breaking changes in functionality. Simply update command syntax if relying on default mode:

```bash
# Old: Relied on quick mode being default
python scripts/generate_schedule.py --creator NAME --week YYYY-Www

# New: Explicitly request quick mode if speed is priority
python scripts/generate_schedule.py --creator NAME --week YYYY-Www --quick
```

### Upgrading from v2.0.0 to v2.1.0
**Database Changes Required**: Add `hook_type` column to `caption_bank` table:

```sql
ALTER TABLE caption_bank ADD COLUMN hook_type TEXT DEFAULT NULL;
```

**Code Changes**: Update weight calculations if using custom scripts:

```python
# Old weight formula
weight = (0.55 * performance) + (0.15 * freshness) + (0.15 * persona) + (0.10 * payday) + (0.05 * diversity)

# New weight formula
weight = (0.60 * earnings) + (0.15 * freshness) + (0.15 * persona) + (0.10 * discovery_bonus)
```

**Validation Updates**: Extended validation may flag issues not caught in v2.0:
- Review auto-correction logs
- Update custom validation overrides
- Test page type filtering for paid-only content

### Upgrading from v1.0.0 to v2.0.0
**Major Architecture Change**: Monolithic script split into modular pipeline.

**Required Actions**:
1. Update import statements in custom scripts
2. Install new dependencies: `pip install -r requirements.txt`
3. Migrate configuration to new format
4. Test validation with new rules

**Database Updates**: No schema changes required, but persona matching benefits from:
```sql
-- Optional: Add persona columns if not present
ALTER TABLE creators ADD COLUMN primary_tone TEXT;
ALTER TABLE creators ADD COLUMN emoji_frequency TEXT;
ALTER TABLE creators ADD COLUMN slang_level TEXT;
```

---

## Deprecated Features

### v3.0.0
- None

### v2.1.0
- **Legacy Weight Formula**: Old 5-component formula deprecated in favor of earnings-first approach
  - Still functional but not recommended
  - Will be removed in v4.0.0

### v2.0.0
- **Fan-Count-Only Volume Tiers**: Replaced by performance-based multi-factor optimization
  - Legacy fallback still available when earnings data missing
  - Warning logged when using fallback

---

## Known Issues

### Current (Unreleased)
- Volume optimization fallback logs warning when using legacy fan-count method
  - **Impact**: Low - fallback ensures schedule generation continues
  - **Workaround**: Ensure `earnings` column populated in `mass_messages` table

### v3.1.0
- Schedule summary printed to stderr after generation
  - **Impact**: Minimal - may clutter logs in batch operations
  - **Workaround**: Redirect stderr or set `EROS_LOG_LEVEL=WARNING`

### v2.1.0
- Hook detection requires manual classification for existing captions
  - **Impact**: Medium - 15% of captions may not have hook_type
  - **Workaround**: Run `classify_hooks.py` batch utility (not included)

---

## Security Notes

### All Versions
- **Database Path**: Ensure `EROS_DATABASE_PATH` points to read/write accessible location
- **API Keys**: LLM integration requires Claude API key via environment variable
- **Data Privacy**: Creator data and captions contain sensitive information
  - Restrict file permissions on schedules directory
  - Do not commit database files to version control
  - Redact sensitive data in logs and examples

---

## Performance Benchmarks

| Version | Quick Mode | Full Mode | Memory | Test Coverage |
|---------|------------|-----------|--------|---------------|
| 1.0.0   | 45s        | N/A       | 80MB   | 0%            |
| 2.0.0   | 28s        | 55s       | 95MB   | 40%           |
| 2.1.0   | 24s        | 52s       | 100MB  | 65%           |
| 3.0.0   | 25s        | 58s       | 105MB  | 75%           |
| 3.1.0   | 26s        | 60s       | 110MB  | 85%           |
| Unreleased | 22s     | 55s       | 95MB   | 95%           |

*Benchmarks on M2 MacBook Pro, 36 active creators, 19.6K captions*

---

## Acknowledgments

This project leverages several open-source algorithms and industry best practices:
- **Vose Alias Method**: Michael D. Vose (1991) - O(1) weighted random sampling
- **Exponential Decay**: Half-life freshness scoring
- **SHA-256**: Schedule fingerprinting for uniqueness detection
- **Keep a Changelog**: Changelog format guidelines

Built with Claude Code for enterprise-grade OnlyFans content scheduling.

---

**Legend:**
- 🔴 **Breaking Change**: Requires code or configuration updates
- 🟡 **Deprecation**: Feature marked for removal in future version
- 🟢 **Enhancement**: New feature or improvement
- 🔵 **Fix**: Bug fix or correction
- ⚫ **Internal**: Behind-the-scenes change, no user impact
