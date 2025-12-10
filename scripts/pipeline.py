#!/usr/bin/env python3
"""
EROS Schedule Generator - Pipeline Orchestration

This module provides the SchedulePipeline class that orchestrates the 9-step
schedule generation pipeline. It delegates to focused modules for each step
group while maintaining the overall flow and error handling.

Two pipeline modes are available:
    1. Legacy mode (run): Uses stratified pools with earnings-based selection
    2. Fresh mode (run_fresh): Uses unified pool with pattern-based fresh selection

9-Step Pipeline (Fresh Mode):
    1. ANALYZE - Load creator profile, metrics, and pattern profile
    2. MATCH CONTENT - Load unified caption pool with freshness tiers
    3. MATCH PERSONA - Load persona profile for voice matching
    4. BUILD STRUCTURE - Create weekly time slots with payday optimization
    5. ASSIGN CAPTIONS - Fresh-focused selection with exploration slots
    6. GENERATE FOLLOW-UPS - Create 15-45 min follow-up bumps
    7. APPLY DRIP WINDOWS - Enforce no-PPV zones if enabled
    8. APPLY PAGE TYPE RULES - Filter paid-only content for free pages
    9. VALIDATE - Check 30 business rules with auto-correction

Usage:
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
    ):
        """
        Initialize the pipeline.

        Args:
            config: Schedule generation configuration
            conn: Database connection with row_factory set
            mode: Pipeline mode - "quick" (no LLM) or "full" (with LLM)
            pattern_cache: Optional shared cache for pattern profiles
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

        # Agent integration (Phase 3)
        self.agent_invoker = None
        self.agent_context = None

        # Schedule builder instance (for fresh mode)
        self._builder = None

    def run(self) -> ScheduleResult:
        """
        Execute the full 9-step pipeline.

        Returns:
            ScheduleResult with items, validation, and metadata

        Raises:
            VaultEmptyError: If creator has no content types in vault
            CaptionExhaustionError: If no captions meet freshness threshold
        """
        schedule_id = str(uuid.uuid4())[:8]

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

        # Step 4: BUILD STRUCTURE
        self.slots, self.content_type_allocation = builder.step_4_build_structure()

        # Track agent usage
        if builder.agents_used:
            self.result.agents_used.extend(builder.agents_used)
        if builder.agents_fallback:
            self.result.agents_fallback.extend(builder.agents_fallback)

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

    # =========================================================================
    # FRESH MODE PIPELINE
    # =========================================================================

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
) -> ScheduleResult:
    """
    Convenience function to run the legacy pipeline.

    Args:
        config: Schedule generation configuration
        conn: Database connection with row_factory
        mode: Pipeline mode ("quick" or "full")

    Returns:
        ScheduleResult with items, validation, and metadata
    """
    pipeline = SchedulePipeline(config, conn, mode)
    return pipeline.run()


def run_pipeline_fresh(
    config: ScheduleConfig,
    conn: sqlite3.Connection,
    mode: str = "full",
    pattern_cache: PatternProfileCache | None = None,
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

    Returns:
        ScheduleResult with items, validation, and metadata
    """
    pipeline = SchedulePipeline(config, conn, mode, pattern_cache)
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
