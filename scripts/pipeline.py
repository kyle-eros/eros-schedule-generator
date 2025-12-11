#!/usr/bin/env python3
"""
EROS Schedule Generator - Pipeline Orchestration

This module provides the SchedulePipeline class that orchestrates the 9-step
schedule generation pipeline. It delegates to focused modules for each step
group while maintaining the overall flow and error handling.

Pipeline Modes
==============

Two pipeline modes are available:

1. **Fresh Mode (RECOMMENDED)** - ``run_fresh()``
   Uses unified pool with pattern-based fresh selection.
   This is the default and recommended approach.

2. **Legacy Mode (DEPRECATED)** - ``run()``
   Uses stratified pools with earnings-based selection.
   Maintained for backward compatibility only.

Persona Matching: Legacy vs Fresh
=================================

The key difference between modes is how Step 3 (MATCH PERSONA) works:

**Legacy Mode** (deprecated):
    - Uses ``step_3_match_persona(captions)``
    - Mutates Caption objects directly to set ``persona_boost`` attribute
    - Pre-computes boosts before selection
    - Works with stratified pools (proven/global_earner/discovery)

**Fresh Mode** (recommended):
    - Uses ``step_3_get_persona_profile()``
    - Returns a PersonaProfile object (no mutation)
    - Persona matching is done dynamically during selection
    - Works with unified SelectionPool and pattern-based scoring

Code Path Comparison::

    # LEGACY (deprecated) - uses mutation-based persona matching
    pipeline = SchedulePipeline(config, conn)
    result = pipeline.run()
    # Internally calls:
    #   - step_2_match_content() -> returns (captions, stratified_pools)
    #   - step_3_match_persona(captions) -> mutates captions with persona_boost
    #   - assign_captions() -> uses mutated captions

    # FRESH (recommended) - uses profile-based persona matching
    pipeline = SchedulePipeline(config, conn)
    result = pipeline.run_fresh()
    # Internally calls:
    #   - step_2_match_content_unified() -> returns SelectionPool
    #   - step_3_get_persona_profile() -> returns PersonaProfile
    #   - step_5_assign_captions_fresh() -> uses pool + profile together

9-Step Pipeline (Fresh Mode)
============================

    1. ANALYZE - Load creator profile, metrics, and pattern profile
    2. MATCH CONTENT - Load unified caption pool with freshness tiers
    3. MATCH PERSONA - Load persona profile for voice matching
    4. BUILD STRUCTURE - Create weekly time slots with payday optimization
    5. ASSIGN CAPTIONS - Fresh-focused selection with exploration slots
    6. GENERATE FOLLOW-UPS - Create 15-45 min follow-up bumps
    7. APPLY DRIP WINDOWS - Enforce no-PPV zones if enabled
    8. APPLY PAGE TYPE RULES - Filter paid-only content for free pages
    9. VALIDATE - Check 30 business rules with auto-correction

Usage
=====

Fresh mode (recommended)::

    from pipeline import SchedulePipeline, run_pipeline_fresh
    from models import ScheduleConfig

    config = ScheduleConfig(
        creator_id="abc123",
        creator_name="missalexa",
        page_type="paid",
        week_start=date(2025, 1, 6),
        week_end=date(2025, 1, 12),
    )

    # Fresh mode (recommended)
    pipeline = SchedulePipeline(config, conn)
    result = pipeline.run_fresh()

    # Or use convenience function
    result = run_pipeline_fresh(config, conn)
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from models import (
    Caption,
    CreatorProfile,
    PatternProfile,
    PersonaProfile,
    ScheduleConfig,
    ScheduleItem,
    ScheduleResult,
    SelectionPool,
    SemanticBoostResult,
    ValidationIssue,
)

if TYPE_CHECKING:
    from select_captions import StratifiedPools
    from pattern_extraction import PatternProfileCache

logger = logging.getLogger(__name__)


class SchedulePipeline:
    """
    Orchestrates the 9-step schedule generation pipeline.

    This class coordinates between schedule_builder (steps 1-4),
    caption assignment (step 5), and enrichment (steps 6-8) modules.

    Supports two modes:
        - Legacy mode (run): Uses stratified pools with earnings-based selection
        - Fresh mode (run_fresh): Uses unified pool with pattern-based selection

    Attributes:
        config: ScheduleConfig with all generation parameters
        conn: Database connection with row_factory
        mode: Pipeline mode ("quick" or "full")
        use_fresh_selection: Whether to use new fresh-focused selection
        profile: Loaded creator profile (after step 1)
        pattern_profile: PatternProfile for scoring (after step 1, fresh mode)
        pattern_cache: Cache for reusing pattern profiles across creators
        captions: Available captions (after step 2, legacy mode)
        selection_pool: Unified caption pool (after step 2, fresh mode)
        stratified_pools: Pool-based caption pools (after step 2, legacy mode)
        persona_profile: PersonaProfile for voice matching (after step 3, fresh mode)
        slots: Weekly time slots (after step 4)
        items: Scheduled items (after step 5)
        result: Final ScheduleResult (after step 9)
    """

    def __init__(
        self,
        config: ScheduleConfig,
        conn: sqlite3.Connection,
        mode: str = "full",
        pattern_cache: PatternProfileCache | None = None,
        semantic_boosts: dict[int, SemanticBoostResult] | None = None,
    ):
        """
        Initialize the pipeline.

        Args:
            config: Schedule generation configuration
            conn: Database connection with row_factory set
            mode: Pipeline mode - "quick" (no LLM) or "full" (with LLM)
            pattern_cache: Optional shared cache for pattern profiles
            semantic_boosts: Optional dict mapping caption_id to SemanticBoostResult
                for overriding pattern-based persona matching in Step 3
        """
        self.config = config
        self.conn = conn
        self.mode = mode

        # State accumulated during pipeline execution (legacy)
        self.profile: CreatorProfile | None = None
        self.captions: list[Caption] = []
        self.stratified_pools: dict[int, StratifiedPools] = {}
        self.content_type_allocation: dict[str, int] = {}
        self.slots: list[dict[str, Any]] = []
        self.items: list[ScheduleItem] = []
        self.result: ScheduleResult | None = None

        # State for fresh mode
        self.use_fresh_selection: bool = False
        self.pattern_profile: PatternProfile | None = None
        self.pattern_cache = pattern_cache
        self.selection_pool: SelectionPool | None = None
        self.persona_profile: PersonaProfile | None = None

        # Semantic boost overrides (from Claude's analysis)
        self.semantic_boosts: dict[int, SemanticBoostResult] = semantic_boosts or {}
        self.semantic_boosts_applied: int = 0
        self.pattern_boosts_applied: int = 0

        # Agent integration (Phase 3)
        self.agent_invoker = None
        self.agent_context = None

        # Schedule builder instance (for fresh mode)
        self._builder = None

    def run(self) -> ScheduleResult:
        """
        Execute the full 9-step pipeline (LEGACY MODE).

        .. deprecated::
            This method uses the legacy stratified pools approach and is
            deprecated in favor of :meth:`run_fresh`. The legacy mode will
            be maintained for backward compatibility but is no longer the
            recommended approach.

        Key Differences from run_fresh():
            - Uses stratified pools (proven/global_earner/discovery)
            - Calls step_3_match_persona() which mutates Caption objects
            - Uses earnings-based selection rather than pattern-based scoring

        Migration:
            # Legacy (this method - deprecated)
            result = pipeline.run()

            # Fresh (recommended)
            result = pipeline.run_fresh()

        Returns:
            ScheduleResult with items, validation, and metadata

        Raises:
            VaultEmptyError: If creator has no content types in vault
            CaptionExhaustionError: If no captions meet freshness threshold
        """
        import warnings
        warnings.warn(
            "SchedulePipeline.run() is deprecated. Use run_fresh() for pattern-based "
            "fresh-focused caption selection. The legacy mode will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        schedule_id = str(uuid.uuid4())[:8]

        # Try to auto-load semantic boosts from cache
        self._try_load_semantic_cache()

        # Initialize result
        self.result = ScheduleResult(
            schedule_id=schedule_id,
            creator_id=self.config.creator_id,
            creator_name=self.config.creator_name,
            display_name=self.config.creator_name,
            page_type=self.config.page_type,
            week_start=self.config.week_start.isoformat(),
            week_end=self.config.week_end.isoformat(),
            volume_level=self.config.volume_level,
            generated_at=datetime.now().isoformat(),
        )

        # Initialize agent system if enabled
        if self.config.use_agents:
            self._initialize_agents()

        # Execute pipeline steps
        try:
            # Steps 1-4: Schedule Building
            self._execute_build_steps()

            # Step 5: Caption Assignment
            self._execute_assignment_step()

            # Steps 6-8: Enrichment
            self._execute_enrichment_steps()

            # Step 9: Validation
            self._execute_validation_step()

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.result.validation_issues.append(
                ValidationIssue(
                    rule_name="pipeline_error",
                    severity="error",
                    message=str(e),
                )
            )
            self.result.validation_passed = False

        # Finalize result
        self._finalize_result()

        return self.result

    def _initialize_agents(self) -> None:
        """Initialize agent system for enhanced optimization."""
        try:
            from agent_invoker import AgentInvoker
            from shared_context import ScheduleContext
            from database import DB_PATH

            self.agent_invoker = AgentInvoker(db_path=str(DB_PATH))
            self.agent_context = ScheduleContext(
                creator_id=self.config.creator_id,
                week_start=self.config.week_start,
                week_end=self.config.week_end,
                mode=self.mode,
            )

            available_agents = self.agent_invoker.get_available_agents()
            logger.info(f"[AGENT MODE] Available agents: {len(available_agents)}")
            self.result.agent_mode = "enabled"

        except ImportError as e:
            logger.warning(f"[AGENT MODE] Agent system not available: {e}")
            self.result.agent_mode = "disabled"
        except Exception as e:
            logger.warning(f"[AGENT MODE] Agent initialization failed: {e}")
            self.result.agent_mode = "disabled"

    def _execute_build_steps(self) -> None:
        """Execute steps 1-4: Schedule Building."""
        from schedule_builder import ScheduleBuilder

        builder = ScheduleBuilder(
            config=self.config,
            conn=self.conn,
            agent_invoker=self.agent_invoker,
            agent_context=self.agent_context,
        )

        # Step 1: ANALYZE
        self.profile = builder.step_1_analyze()
        if not self.profile:
            self.result.validation_issues.append(
                ValidationIssue(
                    rule_name="creator_not_found",
                    severity="error",
                    message=f"Creator not found: {self.config.creator_id}",
                )
            )
            self.result.validation_passed = False
            return

        self.result.display_name = self.profile.display_name
        self.result.best_hours = self.profile.best_hours

        # Step 2: MATCH CONTENT
        self.captions, self.stratified_pools = builder.step_2_match_content()
        if not self.captions:
            self.result.validation_issues.append(
                ValidationIssue(
                    rule_name="no_captions",
                    severity="error",
                    message="No eligible captions found with freshness >= 30",
                )
            )
            self.result.validation_passed = False
            return

        # Load vault types for result
        self.result.vault_types = builder.get_vault_type_names()

        # Step 3: MATCH PERSONA
        self.captions = builder.step_3_match_persona(self.captions)

        # Apply semantic boost overrides if provided
        if self.semantic_boosts:
            self._apply_semantic_overrides(self.captions)

        # Step 4: BUILD STRUCTURE
        self.slots, self.content_type_allocation = builder.step_4_build_structure()

        # Track agent usage
        if builder.agents_used:
            self.result.agents_used.extend(builder.agents_used)
        if builder.agents_fallback:
            self.result.agents_fallback.extend(builder.agents_fallback)

    def _apply_semantic_overrides(self, captions: list[Caption]) -> None:
        """
        Apply semantic boost overrides to captions.

        When a caption has a semantic boost result from Claude's analysis,
        override the pattern-based persona_boost with the semantic value.

        Args:
            captions: List of Caption objects to potentially override
        """
        for caption in captions:
            if caption.caption_id in self.semantic_boosts:
                semantic_result = self.semantic_boosts[caption.caption_id]
                original_boost = caption.persona_boost
                caption.persona_boost = semantic_result.persona_boost
                self.semantic_boosts_applied += 1

                logger.debug(
                    f"[Step 3] Semantic override for caption {caption.caption_id}: "
                    f"{original_boost:.2f}x -> {semantic_result.persona_boost:.2f}x "
                    f"(tone={semantic_result.detected_tone}, "
                    f"confidence={semantic_result.tone_confidence:.2f})"
                )
            else:
                self.pattern_boosts_applied += 1

        if self.semantic_boosts_applied > 0:
            logger.info(
                f"[Step 3] Applied {self.semantic_boosts_applied} semantic overrides, "
                f"{self.pattern_boosts_applied} pattern-based boosts"
            )

    def _apply_semantic_overrides_to_pool(self) -> None:
        """
        Apply semantic boost overrides to ScoredCaption objects in selection pool.

        Since ScoredCaption is frozen, we create new instances with updated
        selection_weight values that incorporate the semantic boost.

        The selection_weight is recalculated as:
            new_weight = pattern_score * semantic_persona_boost

        This replaces the original weight that was calculated with pattern-based
        persona matching.
        """
        from models import ScoredCaption

        if not self.selection_pool:
            return

        updated_captions: list[ScoredCaption] = []
        total_weight = 0.0

        for caption in self.selection_pool.captions:
            if caption.caption_id in self.semantic_boosts:
                semantic_result = self.semantic_boosts[caption.caption_id]

                # Recalculate selection weight with semantic boost
                # Base weight uses pattern_score, apply semantic persona_boost
                new_weight = caption.pattern_score * semantic_result.persona_boost
                total_weight += new_weight
                self.semantic_boosts_applied += 1

                # Create new ScoredCaption with updated weight
                updated_caption = ScoredCaption(
                    caption_id=caption.caption_id,
                    caption_text=caption.caption_text,
                    caption_type=caption.caption_type,
                    content_type_id=caption.content_type_id,
                    content_type_name=caption.content_type_name,
                    tone=semantic_result.detected_tone,  # Use detected tone
                    hook_type=caption.hook_type,
                    freshness_score=caption.freshness_score,
                    performance_score=caption.performance_score,
                    times_used_on_page=caption.times_used_on_page,
                    last_used_date=caption.last_used_date,
                    pattern_score=caption.pattern_score,
                    freshness_tier=caption.freshness_tier,
                    never_used_on_page=caption.never_used_on_page,
                    selection_weight=new_weight,
                )
                updated_captions.append(updated_caption)

                logger.debug(
                    f"[Step 3] Semantic pool override for caption {caption.caption_id}: "
                    f"weight {caption.selection_weight:.2f} -> {new_weight:.2f} "
                    f"(boost={semantic_result.persona_boost:.2f}x)"
                )
            else:
                updated_captions.append(caption)
                total_weight += caption.selection_weight
                self.pattern_boosts_applied += 1

        # Update selection pool with new captions
        self.selection_pool = SelectionPool(
            captions=updated_captions,
            never_used_count=self.selection_pool.never_used_count,
            fresh_count=self.selection_pool.fresh_count,
            total_weight=total_weight,
            creator_id=self.selection_pool.creator_id,
            content_types=self.selection_pool.content_types,
            low_performance_filtered_count=self.selection_pool.low_performance_filtered_count,
            low_performance_included_count=self.selection_pool.low_performance_included_count,
        )

        if self.semantic_boosts_applied > 0:
            logger.info(
                f"[Step 3] Applied {self.semantic_boosts_applied} semantic pool overrides, "
                f"{self.pattern_boosts_applied} pattern-based weights"
            )

    def _execute_assignment_step(self) -> None:
        """Execute step 5: Caption Assignment."""
        if not self.profile or not self.captions or not self.slots:
            return

        # Import assignment function
        from schedule_builder import assign_captions

        persona_dict = {
            "primary_tone": self.profile.primary_tone,
            "emoji_frequency": self.profile.emoji_frequency,
            "slang_level": self.profile.slang_level,
        }

        self.items = assign_captions(
            slots=self.slots,
            captions=self.captions,
            config=self.config,
            pools=self.stratified_pools,
            persona=persona_dict,
            content_type_allocation=self.content_type_allocation,
        )

        logger.info(f"[Step 5] Assigned {len(self.items)} PPV items")

    def _execute_enrichment_steps(self) -> None:
        """Execute steps 6-8: Enrichment."""
        if not self.profile or not self.items:
            return

        from enrichment import EnrichmentProcessor

        enricher = EnrichmentProcessor(
            config=self.config,
            profile=self.profile,
            agent_invoker=self.agent_invoker,
            agent_context=self.agent_context,
        )

        # Step 6: Generate Follow-ups
        self.items = enricher.step_6_generate_followups(self.items)

        # Step 7: Apply Drip Windows
        self.items = enricher.step_7_apply_drip_windows(self.items)

        # Step 8: Apply Page Type Rules
        self.items = enricher.step_8_apply_page_rules(self.items)

        # Track agent usage
        if enricher.agents_used:
            self.result.agents_used.extend(enricher.agents_used)
        if enricher.agents_fallback:
            self.result.agents_fallback.extend(enricher.agents_fallback)

    def _execute_validation_step(self) -> None:
        """Execute step 9: Validation with self-healing."""
        if not self.items:
            return

        from enrichment import validate_and_correct

        self.items, issues, corrections = validate_and_correct(
            items=self.items,
            config=self.config,
            available_captions=self.captions,
        )

        self.result.validation_issues = issues
        self.result.validation_passed = not any(
            i.severity == "error" for i in issues
        )

        if corrections:
            logger.info(f"[Step 9] Applied {len(corrections)} auto-corrections")

    def _finalize_result(self) -> None:
        """Populate final result statistics."""
        if not self.result:
            return

        self.result.items = self.items
        self.result.total_ppvs = sum(1 for i in self.items if i.item_type == "ppv")
        self.result.total_bumps = sum(1 for i in self.items if i.item_type == "bump")
        self.result.total_follow_ups = sum(1 for i in self.items if i.is_follow_up)
        self.result.total_drip = sum(1 for i in self.items if i.item_type == "drip")
        self.result.unique_captions = len({i.caption_id for i in self.items if i.caption_id})

        ppv_items = [i for i in self.items if i.item_type == "ppv"]
        if ppv_items:
            self.result.avg_freshness = sum(i.freshness_score for i in ppv_items) / len(ppv_items)
            self.result.avg_performance = sum(i.performance_score for i in ppv_items) / len(ppv_items)

        # Extended content type counts
        self.result.total_wall_posts = sum(1 for i in self.items if i.item_type == "wall_post")
        self.result.total_free_previews = sum(1 for i in self.items if i.item_type == "free_preview")
        self.result.total_polls = sum(1 for i in self.items if i.item_type == "poll")
        self.result.total_game_wheels = sum(1 for i in self.items if i.item_type == "game_wheel")

        # Finalize agent mode status
        if self.config.use_agents:
            total_agents = len(self.result.agents_used) + len(self.result.agents_fallback)
            successful = len(self.result.agents_used)

            if successful == 0 and total_agents > 0:
                self.result.agent_mode = "disabled"
            elif successful < total_agents:
                self.result.agent_mode = "partial"
            elif successful > 0:
                self.result.agent_mode = "enabled"

        # Add semantic boost metadata to pipeline_context
        self.result.pipeline_context["semantic_boosts"] = {
            "semantic_overrides_applied": self.semantic_boosts_applied,
            "pattern_boosts_applied": self.pattern_boosts_applied,
            "semantic_file_used": len(self.semantic_boosts) > 0,
            "total_semantic_entries": len(self.semantic_boosts),
        }

    # =========================================================================
    # FRESH MODE PIPELINE
    # =========================================================================

    def _try_load_semantic_cache(self) -> None:
        """
        Try to auto-load semantic boosts from cache if none were provided.

        Checks the semantic cache for the creator/week combination and loads
        any previously saved Claude analysis results. This allows semantic
        analysis to persist between sessions.

        The cache location is:
            ~/.eros/schedules/semantic/{creator_name}/{week}_semantic.json
        """
        if self.semantic_boosts:
            # Already have semantic boosts (provided via --semantic-file)
            logger.info(
                f"[Pipeline] Using provided semantic boosts ({len(self.semantic_boosts)} entries)"
            )
            return

        try:
            from semantic_boost_cache import SemanticBoostCache

            cache = SemanticBoostCache()
            week_str = self.config.week_start.strftime("%G-W%V")

            # Try to load from cache
            cached_boosts = cache.load(self.config.creator_name, week_str)

            if cached_boosts:
                self.semantic_boosts = cached_boosts
                logger.info(
                    f"[Pipeline] Auto-loaded {len(cached_boosts)} semantic boosts from cache "
                    f"for {self.config.creator_name}/{week_str}"
                )
            else:
                # Try loading latest available cache (within 4 weeks)
                cached_boosts, cached_week = cache.load_latest(
                    self.config.creator_name, max_age_weeks=4
                )
                if cached_boosts:
                    self.semantic_boosts = cached_boosts
                    logger.info(
                        f"[Pipeline] Auto-loaded {len(cached_boosts)} semantic boosts "
                        f"from recent cache ({cached_week}) for {self.config.creator_name}"
                    )
                else:
                    logger.debug(
                        f"[Pipeline] No semantic cache found for {self.config.creator_name}"
                    )

        except ImportError:
            logger.debug("[Pipeline] Semantic boost cache module not available")
        except Exception as e:
            logger.warning(f"[Pipeline] Failed to load semantic cache: {e}")

    def run_fresh(self) -> ScheduleResult:
        """
        Execute the 9-step pipeline using fresh-focused caption selection.

        This mode prioritizes never-used captions and uses pattern-based scoring
        to predict performance. It includes exploration slots for discovering
        new caption styles.

        Returns:
            ScheduleResult with items, validation, and metadata

        Raises:
            VaultEmptyError: If creator has no content types in vault
            CaptionExhaustionError: If no captions meet freshness threshold
        """
        from config_loader import load_selection_config
        from pattern_extraction import PatternProfileCache

        self.use_fresh_selection = True
        schedule_id = str(uuid.uuid4())[:8]

        # Try to auto-load semantic boosts from cache
        self._try_load_semantic_cache()

        # Load selection config
        try:
            selection_config = load_selection_config()
            logger.info(
                f"[Pipeline] Fresh mode: exploration_ratio={selection_config.exploration_ratio}, "
                f"exclusion_days={selection_config.exclusion_days}"
            )
        except Exception as e:
            logger.warning(f"[Pipeline] Failed to load selection config: {e}")
            selection_config = None

        # Initialize pattern cache if not provided
        if self.pattern_cache is None:
            self.pattern_cache = PatternProfileCache()
            logger.info("[Pipeline] Pattern cache initialized")

        # Initialize result
        self.result = ScheduleResult(
            schedule_id=schedule_id,
            creator_id=self.config.creator_id,
            creator_name=self.config.creator_name,
            display_name=self.config.creator_name,
            page_type=self.config.page_type,
            week_start=self.config.week_start.isoformat(),
            week_end=self.config.week_end.isoformat(),
            volume_level=self.config.volume_level,
            generated_at=datetime.now().isoformat(),
        )

        # Initialize agent system if enabled
        if self.config.use_agents:
            self._initialize_agents()

        # Execute pipeline steps
        try:
            # Steps 1-4: Schedule Building (fresh mode)
            self._execute_build_steps_fresh()

            # Step 5: Caption Assignment (fresh mode)
            self._execute_assignment_step_fresh()

            # Steps 6-8: Enrichment
            self._execute_enrichment_steps()

            # Step 9: Validation
            self._execute_validation_step_fresh()

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.result.validation_issues.append(
                ValidationIssue(
                    rule_name="pipeline_error",
                    severity="error",
                    message=str(e),
                )
            )
            self.result.validation_passed = False

        # Finalize result
        self._finalize_result_fresh()

        return self.result

    def _execute_build_steps_fresh(self) -> None:
        """Execute steps 1-4 using fresh mode: Schedule Building."""
        from schedule_builder import ScheduleBuilder

        builder = ScheduleBuilder(
            config=self.config,
            conn=self.conn,
            agent_invoker=self.agent_invoker,
            agent_context=self.agent_context,
            pattern_cache=self.pattern_cache,
        )
        self._builder = builder  # Store for later use

        # Step 1: ANALYZE (includes pattern profile loading)
        self.profile = builder.step_1_analyze()
        if not self.profile:
            self.result.validation_issues.append(
                ValidationIssue(
                    rule_name="creator_not_found",
                    severity="error",
                    message=f"Creator not found: {self.config.creator_id}",
                )
            )
            self.result.validation_passed = False
            return

        self.result.display_name = self.profile.display_name
        self.result.best_hours = self.profile.best_hours
        self.pattern_profile = builder.pattern_profile

        # Step 2: MATCH CONTENT (unified pool)
        self.selection_pool = builder.step_2_match_content_unified()
        if not self.selection_pool or not self.selection_pool.captions:
            self.result.validation_issues.append(
                ValidationIssue(
                    rule_name="no_captions",
                    severity="error",
                    message="No eligible captions found in unified pool",
                )
            )
            self.result.validation_passed = False
            return

        # Load vault types for result
        self.result.vault_types = builder.get_vault_type_names()

        # Step 3: MATCH PERSONA (get persona profile)
        self.persona_profile = builder.step_3_get_persona_profile()

        # Apply semantic boost overrides to selection pool if provided
        if self.semantic_boosts and self.selection_pool:
            self._apply_semantic_overrides_to_pool()

        # Step 4: BUILD STRUCTURE
        self.slots, self.content_type_allocation = builder.step_4_build_structure()

        # Track agent usage
        if builder.agents_used:
            self.result.agents_used.extend(builder.agents_used)
        if builder.agents_fallback:
            self.result.agents_fallback.extend(builder.agents_fallback)

        logger.info(
            f"[Pipeline] Fresh build complete: {len(self.selection_pool.captions)} captions, "
            f"{len(self.slots)} slots, pattern confidence={self.pattern_profile.confidence if self.pattern_profile else 0:.2f}"
        )

    def _execute_assignment_step_fresh(self) -> None:
        """Execute step 5: Caption Assignment using fresh-focused selection."""
        if not self._builder or not self.selection_pool or not self.slots:
            return

        self.items = self._builder.step_5_assign_captions_fresh(
            slots=self.slots,
            pool=self.selection_pool,
            persona=self.persona_profile,
            content_type_allocation=self.content_type_allocation,
        )

        logger.info(f"[Step 5] Assigned {len(self.items)} PPV items (fresh mode)")

    def _execute_validation_step_fresh(self) -> None:
        """Execute step 9: Validation with self-healing (fresh mode)."""
        if not self.items:
            return

        from enrichment import validate_and_correct

        # For fresh mode, use pool captions as available captions
        available_captions = []
        if self.selection_pool:
            # Convert ScoredCaption to Caption for validation
            for sc in self.selection_pool.captions:
                available_captions.append(
                    Caption(
                        caption_id=sc.caption_id,
                        caption_text=sc.caption_text,
                        caption_type="ppv",
                        content_type_id=sc.content_type_id,
                        content_type_name=sc.content_type_name,
                        performance_score=sc.pattern_score,
                        freshness_score=sc.freshness_score,
                        tone=sc.tone,
                        emoji_style=None,
                        slang_level=None,
                        is_universal=False,
                    )
                )

        self.items, issues, corrections = validate_and_correct(
            items=self.items,
            config=self.config,
            available_captions=available_captions,
        )

        self.result.validation_issues = issues
        self.result.validation_passed = not any(
            i.severity == "error" for i in issues
        )

        if corrections:
            logger.info(f"[Step 9] Applied {len(corrections)} auto-corrections")

    def _finalize_result_fresh(self) -> None:
        """Populate final result statistics (fresh mode)."""
        self._finalize_result()

        # Add fresh-mode specific metadata
        if self.result and self._builder:
            pipeline_context = self._builder.get_pipeline_context()
            self.result.pipeline_context = pipeline_context

            # Add pattern profile summary to notes
            if pipeline_context.get("pattern_profile"):
                pp = pipeline_context["pattern_profile"]
                self.result.selection_mode = "fresh"
                self.result.pattern_confidence = pp.get("confidence", 0)
                self.result.is_global_fallback = pp.get("is_global_fallback", False)
            else:
                self.result.selection_mode = "fresh"
                self.result.pattern_confidence = 0
                self.result.is_global_fallback = True

    def get_pipeline_context(self) -> dict[str, Any]:
        """
        Get pipeline context for debugging and LLM integration.

        Returns:
            Dictionary with creator, pattern, and pool information
        """
        if self._builder:
            return self._builder.get_pipeline_context()

        return {
            "creator_id": self.config.creator_id,
            "mode": "legacy" if not self.use_fresh_selection else "fresh",
            "pattern_profile": None,
            "selection_pool": None,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def run_pipeline(
    config: ScheduleConfig,
    conn: sqlite3.Connection,
    mode: str = "full",
    semantic_boosts: dict[int, SemanticBoostResult] | None = None,
) -> ScheduleResult:
    """
    Convenience function to run the legacy pipeline.

    .. deprecated::
        This function uses the deprecated legacy pipeline. Use :func:`run_pipeline_fresh`
        instead for pattern-based fresh-focused caption selection.

    Args:
        config: Schedule generation configuration
        conn: Database connection with row_factory
        mode: Pipeline mode ("quick" or "full")
        semantic_boosts: Optional dict mapping caption_id to SemanticBoostResult
            for overriding pattern-based persona matching in Step 3

    Returns:
        ScheduleResult with items, validation, and metadata
    """
    import warnings
    warnings.warn(
        "run_pipeline() is deprecated. Use run_pipeline_fresh() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    pipeline = SchedulePipeline(config, conn, mode, semantic_boosts=semantic_boosts)
    return pipeline.run()


def run_pipeline_fresh(
    config: ScheduleConfig,
    conn: sqlite3.Connection,
    mode: str = "full",
    pattern_cache: PatternProfileCache | None = None,
    semantic_boosts: dict[int, SemanticBoostResult] | None = None,
) -> ScheduleResult:
    """
    Convenience function to run the fresh-focused pipeline.

    This uses the new pattern-based caption selection that prioritizes
    never-used captions and includes exploration slots for variety.

    Args:
        config: Schedule generation configuration
        conn: Database connection with row_factory
        mode: Pipeline mode ("quick" or "full")
        pattern_cache: Optional shared cache for batch processing
        semantic_boosts: Optional dict mapping caption_id to SemanticBoostResult
            for overriding pattern-based persona matching in Step 3

    Returns:
        ScheduleResult with items, validation, and metadata
    """
    pipeline = SchedulePipeline(config, conn, mode, pattern_cache, semantic_boosts)
    return pipeline.run_fresh()


def warm_pattern_cache(
    conn: sqlite3.Connection,
    creator_ids: list[str] | None = None,
) -> PatternProfileCache:
    """
    Pre-warm pattern cache for multiple creators.

    Useful for batch processing where the same pattern profiles
    can be reused across multiple schedule generations.

    Args:
        conn: Database connection with row_factory
        creator_ids: Optional list of creator IDs to pre-warm.
                     If None, loads global profile only.

    Returns:
        PatternProfileCache with loaded profiles
    """
    from pattern_extraction import (
        PatternProfileCache,
        build_global_pattern_profile,
        build_pattern_profile,
    )

    cache = PatternProfileCache()

    # Always load global profile
    try:
        global_profile = build_global_pattern_profile(conn)
        cache.set("GLOBAL", global_profile)
        logger.info(f"[Cache] Loaded global profile: {global_profile.sample_count} samples")
    except Exception as e:
        logger.warning(f"[Cache] Failed to load global profile: {e}")

    # Load creator-specific profiles if requested
    if creator_ids:
        for creator_id in creator_ids:
            try:
                profile = build_pattern_profile(conn, creator_id)
                cache.set(creator_id, profile)
                logger.info(
                    f"[Cache] Loaded profile for {creator_id}: "
                    f"{profile.sample_count} samples, confidence={profile.confidence:.2f}"
                )
            except Exception as e:
                logger.warning(f"[Cache] Failed to load profile for {creator_id}: {e}")

    return cache


__all__ = [
    "SchedulePipeline",
    "run_pipeline",
    "run_pipeline_fresh",
    "warm_pattern_cache",
]
