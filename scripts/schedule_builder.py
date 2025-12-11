#!/usr/bin/env python3
"""
EROS Schedule Generator - Schedule Builder

This module handles Steps 1-5 of the 9-step pipeline:
    1. ANALYZE - Load creator profile, metrics, and pattern profile
    2. MATCH CONTENT - Load caption pool (unified or stratified)
    3. MATCH PERSONA - Score captions by voice profile
    4. BUILD STRUCTURE - Create weekly time slots with payday optimization
    5. ASSIGN CAPTIONS - Select and assign captions to slots

Step 3 (MATCH PERSONA) - Two Code Paths
=======================================

This module contains two persona matching methods:

**step_3_match_persona(captions)** - DEPRECATED (Legacy):
    - Mutates Caption objects directly to set ``persona_boost`` attribute
    - Used with legacy ``step_2_match_content()`` which returns stratified pools
    - Called by ``SchedulePipeline.run()`` (deprecated)
    - Will emit DeprecationWarning when called

**step_3_get_persona_profile()** - RECOMMENDED (Fresh):
    - Returns a PersonaProfile object (no mutation)
    - Used with ``step_2_match_content_unified()`` which returns SelectionPool
    - Called by ``SchedulePipeline.run_fresh()`` (recommended)
    - Persona matching done dynamically during ``step_5_assign_captions_fresh()``

Migration Guide
===============

If you're calling these methods directly, migrate as follows::

    # OLD (deprecated)
    captions, pools = builder.step_2_match_content()
    captions = builder.step_3_match_persona(captions)
    items = assign_captions(slots, captions, config, pools, ...)

    # NEW (recommended)
    pool = builder.step_2_match_content_unified()
    persona = builder.step_3_get_persona_profile()
    items = builder.step_5_assign_captions_fresh(slots, pool, persona, ...)

Usage (Fresh Mode - Recommended)
================================

::

    from schedule_builder import ScheduleBuilder

    builder = ScheduleBuilder(config, conn)
    profile = builder.step_1_analyze()
    pool = builder.step_2_match_content_unified()  # Returns SelectionPool
    persona = builder.step_3_get_persona_profile()  # Returns PersonaProfile
    slots, allocation = builder.step_4_build_structure()
    items = builder.step_5_assign_captions_fresh(slots, pool, persona, allocation)
"""

from __future__ import annotations

import json
import logging
import random
import sqlite3
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from models import (
    Caption,
    CreatorProfile,
    PatternProfile,
    PersonaProfile,
    ScheduleConfig,
    ScheduleItem,
    ScoredCaption,
    SelectionPool,
)

if TYPE_CHECKING:
    from select_captions import StratifiedPools

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS (loaded from config_loader)
# =============================================================================

from config_loader import get_config
from content_type_registry import get_item_type_for_content_type

_config = get_config()

MIN_PPV_SPACING_HOURS: int = _config.ppv.min_spacing_hours
ROTATION_ORDER: list[str] = list(_config.content_types.rotation_order)
PREMIUM_CONTENT_TYPES: set[str] = set(_config.content_types.premium)
PAYDAY_PREMIUM_BOOST: float = _config.payday.premium_boost
PAYDAY_PREMIUM_PENALTY: float = _config.payday.premium_penalty


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def parse_content_notes(notes_json: str | None) -> dict:
    """Parse JSON notes from creators.notes field."""
    if not notes_json:
        return {}
    try:
        return json.loads(notes_json)
    except json.JSONDecodeError:
        return {"page_strategy": notes_json}


def extract_filter_keywords(notes: dict) -> set[str]:
    """Extract keywords to filter from content notes."""
    keywords = set()
    if notes.get("caption_filters", {}).get("exclude_keywords"):
        keywords.update(notes["caption_filters"]["exclude_keywords"])
    for restriction in notes.get("content_restrictions", []):
        if restriction.get("filter_keywords"):
            keywords.update(restriction["filter_keywords"])
    return keywords


def extract_price_modifiers(notes: dict) -> dict[str | None, float]:
    """Extract price modifiers by content type."""
    modifiers = {}
    for guidance in notes.get("pricing_guidance", []):
        content_type = guidance.get("content_type")
        modifier = guidance.get("price_modifier", 1.0)
        modifiers[content_type] = modifier
    for restriction in notes.get("content_restrictions", []):
        if restriction.get("price_modifier"):
            content_type = restriction.get("content_type")
            modifiers[content_type] = restriction["price_modifier"]
    return modifiers


# =============================================================================
# SCHEDULE BUILDER CLASS
# =============================================================================


class ScheduleBuilder:
    """
    Handles Steps 1-5 of the schedule generation pipeline.

    This class encapsulates the logic for:
    - Loading creator profile, analytics, and pattern profile (Step 1)
    - Loading unified caption pool with freshness tiers (Step 2)
    - Applying persona scores (Step 3)
    - Building weekly time slots (Step 4)
    - Assigning captions with exploration slots (Step 5)

    Attributes:
        config: ScheduleConfig with generation parameters
        conn: Database connection with row_factory
        agent_invoker: Optional agent invoker for enhanced optimization
        agent_context: Optional agent context for inter-agent communication
        profile: Loaded creator profile (set after step 1)
        pattern_profile: PatternProfile for caption scoring (set after step 1)
        pattern_cache: PatternProfileCache for reusing profiles
        persona_profile: PersonaProfile for persona matching (set after step 3)
        selection_pool: SelectionPool for caption selection (set after step 2)
        agents_used: List of agents successfully invoked
        agents_fallback: List of agents that used fallback
    """

    def __init__(
        self,
        config: ScheduleConfig,
        conn: sqlite3.Connection,
        agent_invoker: Any | None = None,
        agent_context: Any | None = None,
        pattern_cache: Any | None = None,
    ):
        """
        Initialize the schedule builder.

        Args:
            config: Schedule generation configuration
            conn: Database connection with row_factory set
            agent_invoker: Optional agent invoker for Phase 3 integration
            agent_context: Optional shared context for agents
            pattern_cache: Optional PatternProfileCache for reusing profiles
        """
        self.config = config
        self.conn = conn
        self.agent_invoker = agent_invoker
        self.agent_context = agent_context
        self.profile: CreatorProfile | None = None
        self.pattern_profile: PatternProfile | None = None
        self.pattern_cache = pattern_cache
        self.persona_profile: PersonaProfile | None = None
        self.selection_pool: SelectionPool | None = None
        self.agents_used: list[str] = []
        self.agents_fallback: list[str] = []

    # =========================================================================
    # STEP 1: ANALYZE
    # =========================================================================

    def step_1_analyze(self) -> CreatorProfile | None:
        """
        Load creator profile from database.

        Step 1 of pipeline: ANALYZE

        Returns:
            CreatorProfile with all creator data, or None if not found

        Raises:
            VaultEmptyError: If creator has no content types in vault
        """
        from exceptions import VaultEmptyError

        if self.config.creator_name:
            query = """
                SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                       c.current_active_fans, c.notes,
                       cp.primary_tone, cp.secondary_tone, cp.emoji_frequency,
                       cp.slang_level, cp.avg_sentiment
                FROM creators c
                LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
                WHERE c.page_name = ? OR c.display_name = ?
                LIMIT 1
            """
            cursor = self.conn.execute(
                query, (self.config.creator_name, self.config.creator_name)
            )
        else:
            query = """
                SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                       c.current_active_fans, c.notes,
                       cp.primary_tone, cp.secondary_tone, cp.emoji_frequency,
                       cp.slang_level, cp.avg_sentiment
                FROM creators c
                LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
                WHERE c.creator_id = ?
                LIMIT 1
            """
            cursor = self.conn.execute(query, (self.config.creator_id,))

        row = cursor.fetchone()
        if not row:
            return None

        active_fans = row["current_active_fans"] or 0

        # Load best hours from historical data
        best_hours = self._load_optimal_hours(row["creator_id"])

        # Load vault content types
        vault_types = self._load_vault_types(row["creator_id"])

        # Validate vault is not empty
        if not vault_types:
            raise VaultEmptyError(row["creator_id"], row["page_name"])

        # Parse content notes
        content_notes = parse_content_notes(row["notes"] if row["notes"] else None)
        filter_keywords = extract_filter_keywords(content_notes)
        price_modifiers = extract_price_modifiers(content_notes)

        # Determine volume level
        volume_level = self._get_volume_level(active_fans)

        self.profile = CreatorProfile(
            creator_id=row["creator_id"],
            page_name=row["page_name"],
            display_name=row["display_name"] or row["page_name"],
            page_type=row["page_type"] or "paid",
            active_fans=active_fans,
            volume_level=volume_level,
            primary_tone=row["primary_tone"] or "playful",
            emoji_frequency=row["emoji_frequency"] or "moderate",
            slang_level=row["slang_level"] or "light",
            avg_sentiment=row["avg_sentiment"] or 0.5,
            secondary_tone=row["secondary_tone"],
            best_hours=best_hours,
            vault_types=vault_types,
            content_notes=content_notes,
            filter_keywords=filter_keywords,
            price_modifiers=price_modifiers,
        )

        logger.info(
            f"[Step 1] Loaded profile for {self.profile.page_name} "
            f"({active_fans} fans, {len(vault_types)} content types)"
        )

        # Load pattern profile for caption scoring
        self._load_pattern_profile()

        # Invoke agent for timing optimization if available
        if self.agent_invoker and self.agent_context:
            self._invoke_timing_agents()

        return self.profile

    def _load_pattern_profile(self) -> None:
        """
        Load pattern profile for the creator during analysis.

        Checks cache first, builds new profile if not cached.
        Falls back to global profile if creator has sparse data.
        """
        from pattern_extraction import (
            PatternProfileCache,
            build_global_pattern_profile,
            build_pattern_profile,
        )

        if not self.profile:
            return

        creator_id = self.profile.creator_id

        # Initialize cache if not provided
        if self.pattern_cache is None:
            self.pattern_cache = PatternProfileCache()

        # Check cache first
        cached_profile = self.pattern_cache.get(creator_id)
        if cached_profile is not None:
            self.pattern_profile = cached_profile
            logger.info(
                f"[Step 1] Using cached pattern profile for {self.profile.page_name}: "
                f"{cached_profile.sample_count} samples, confidence={cached_profile.confidence:.2f}"
            )
            return

        # Build new profile
        try:
            profile = build_pattern_profile(self.conn, creator_id)
            self.pattern_cache.set(creator_id, profile)

            # If sparse data, also load global profile for fallback
            if profile.is_global_fallback:
                global_profile = self.pattern_cache.get("GLOBAL")
                if global_profile is None:
                    global_profile = build_global_pattern_profile(self.conn)
                    self.pattern_cache.set("GLOBAL", global_profile)
                logger.info(
                    f"[Step 1] Creator {self.profile.page_name} has sparse data, "
                    f"global fallback profile available"
                )

            self.pattern_profile = profile
            logger.info(
                f"[Step 1] Built pattern profile for {self.profile.page_name}: "
                f"{profile.sample_count} samples, "
                f"{len(profile.combined_patterns)} combined patterns, "
                f"confidence={profile.confidence:.2f}"
            )

        except Exception as e:
            logger.warning(f"[Step 1] Failed to build pattern profile: {e}")
            # Create minimal fallback profile
            self.pattern_profile = PatternProfile(
                creator_id=creator_id,
                sample_count=0,
                confidence=0.5,
                is_global_fallback=True,
            )

    def _load_optimal_hours(self, creator_id: str) -> list[int]:
        """Load best performing hours from historical data."""
        query = """
            SELECT sending_hour, AVG(earnings) as avg_earnings
            FROM mass_messages
            WHERE creator_id = ?
              AND message_type = 'ppv'
              AND earnings IS NOT NULL
              AND sending_time >= datetime('now', '-90 days')
            GROUP BY sending_hour
            HAVING COUNT(*) >= 3
            ORDER BY avg_earnings DESC
            LIMIT 10
        """
        cursor = self.conn.execute(query, (creator_id,))
        hours = [row["sending_hour"] for row in cursor.fetchall()]

        if not hours:
            hours = [10, 14, 18, 20, 21]  # Default peak engagement windows

        return hours

    def _load_vault_types(self, creator_id: str) -> list[int]:
        """Load available content types from vault."""
        query = """
            SELECT content_type_id
            FROM vault_matrix
            WHERE creator_id = ? AND has_content = 1
        """
        cursor = self.conn.execute(query, (creator_id,))
        return [row["content_type_id"] for row in cursor.fetchall()]

    def _get_volume_level(self, active_fans: int) -> str:
        """
        Determine volume level from fan count.

        Volume Tiers (from CLAUDE.md):
            - Low: <1,000 fans (14-21 PPV/week)
            - Mid: 1,000-5,000 fans (21-28 PPV/week)
            - High: 5,000-15,000 fans (28-35 PPV/week)
            - Ultra: 15,000+ fans (35-42 PPV/week)

        Args:
            active_fans: Current active fan count

        Returns:
            Volume tier string (Low, Mid, High, Ultra)
        """
        if active_fans < 1000:
            return "Low"
        elif active_fans < 5000:
            return "Mid"
        elif active_fans < 15000:
            return "High"
        else:
            return "Ultra"

    def _invoke_timing_agents(self) -> None:
        """Invoke timing-related agents."""
        try:
            from shared_context import CreatorProfile as AgentCreatorProfile

            self.agent_context.creator_profile = AgentCreatorProfile(
                creator_id=self.profile.creator_id,
                page_name=self.profile.page_name,
                display_name=self.profile.display_name,
                page_type=self.profile.page_type,
                subscription_price=0.0,
                current_active_fans=self.profile.active_fans,
                performance_tier=1,
                current_total_earnings=0.0,
                current_avg_spend_per_txn=0.0,
                current_avg_earnings_per_fan=0.0,
                volume_level=self.profile.volume_level,
                ppv_per_day=self.config.ppv_per_day,
                bump_per_day=self.config.bump_per_day,
            )

            # Invoke timezone optimizer
            timing_strategy, timing_fallback = self.agent_invoker.invoke_timezone_optimizer(
                self.agent_context
            )
            self.agent_context.timing = timing_strategy

            if timing_fallback:
                self.agents_fallback.append("timezone-optimizer")
            else:
                self.agents_used.append("timezone-optimizer")

            # Invoke page type optimizer
            page_rules, page_fallback = self.agent_invoker.invoke_page_type_optimizer(
                self.agent_context
            )
            self.agent_context.page_type_rules = page_rules

            if page_fallback:
                self.agents_fallback.append("page-type-optimizer")
            else:
                self.agents_used.append("page-type-optimizer")

        except Exception as e:
            logger.warning(f"[AGENT MODE] Timing agents failed: {e}")
            self.agents_fallback.extend(["timezone-optimizer", "page-type-optimizer"])

    # =========================================================================
    # STEP 2: MATCH CONTENT
    # =========================================================================

    def step_2_match_content(self) -> tuple[list[Caption], dict[int, StratifiedPools]]:
        """
        Filter captions by vault availability and load stratified pools.

        Step 2 of pipeline: MATCH CONTENT (LEGACY)

        .. deprecated::
            This method is deprecated. Use :meth:`step_2_match_content_unified`
            instead, which returns a SelectionPool for use with the fresh pipeline.

        Returns:
            Tuple of (captions list, stratified pools dict)
        """
        import warnings
        warnings.warn(
            "step_2_match_content() is deprecated. Use step_2_match_content_unified() "
            "with the fresh pipeline (run_fresh) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from content_type_strategy import ContentTypeStrategy, get_content_type_earnings
        from select_captions import StratifiedPools
        from weights import POOL_DISCOVERY, POOL_GLOBAL_EARNER, POOL_PROVEN, determine_pool_type

        if not self.profile:
            return [], {}

        # Get allowed content types from vault
        strategy = ContentTypeStrategy(self.conn, self.profile.creator_id)
        allowed_pools = strategy.get_allowed_content_types()
        allowed_content_types = [p.content_type_id for p in allowed_pools]

        if not allowed_content_types:
            logger.warning("[Step 2] No content types found in vault_matrix")
            return [], {}

        logger.info(f"[Step 2] Content type gate: {len(allowed_content_types)} allowed types")

        # Load captions
        captions = self._load_available_captions(allowed_content_types)

        if not captions:
            return [], {}

        # Get content type earnings for pool calculations
        content_type_earnings = get_content_type_earnings(self.conn, self.profile.creator_id)

        # Build type names mapping
        type_names: dict[int, str] = {}
        for cap in captions:
            if cap.content_type_id and cap.content_type_name:
                type_names[cap.content_type_id] = cap.content_type_name

        # Initialize stratified pools
        pools: dict[int, StratifiedPools] = {}
        for ct_id in allowed_content_types:
            ct_name = type_names.get(ct_id, f"type_{ct_id}")
            ct_avg = content_type_earnings.get(ct_name, 50.0)
            pools[ct_id] = StratifiedPools(
                content_type_id=ct_id,
                type_name=ct_name,
                proven=[],
                global_earners=[],
                discovery=[],
                content_type_avg_earnings=ct_avg,
            )

        # Partition captions into pools
        for caption in captions:
            ct_id = caption.content_type_id
            if ct_id is None or ct_id not in pools:
                continue

            pool_type = determine_pool_type(caption)
            if pool_type == POOL_PROVEN:
                pools[ct_id].proven.append(caption)
            elif pool_type == POOL_GLOBAL_EARNER:
                pools[ct_id].global_earners.append(caption)
            else:
                pools[ct_id].discovery.append(caption)

        # Log pool statistics
        total_proven = sum(len(p.proven) for p in pools.values())
        total_global = sum(len(p.global_earner) for p in pools.values())
        total_discovery = sum(len(p.discovery) for p in pools.values())
        logger.info(
            f"[Step 2] Stratified pools: {total_proven} proven, "
            f"{total_global} global_earner, {total_discovery} discovery"
        )

        return captions, pools

    def step_2_match_content_unified(self) -> SelectionPool:
        """
        Load unified caption pool for fresh-focused selection.

        Step 2 of pipeline: MATCH CONTENT (new unified pool approach)

        This method replaces the stratified pool approach with a unified pool
        that contains pre-scored captions with freshness tiers. The pool is
        stored in self.selection_pool for use in step 5.

        Returns:
            SelectionPool with scored captions ready for selection

        Raises:
            ValueError: If creator profile not loaded
        """
        from config_loader import SelectionConfig, load_selection_config
        from content_type_strategy import ContentTypeStrategy
        from select_captions import load_unified_pool, log_pool_statistics

        if not self.profile:
            raise ValueError("Creator profile not loaded. Run step_1_analyze first.")

        # Load selection config
        try:
            selection_config = load_selection_config()
        except Exception as e:
            logger.warning(f"[Step 2] Failed to load selection config: {e}, using defaults")
            selection_config = SelectionConfig()

        # Get allowed content types from vault
        strategy = ContentTypeStrategy(self.conn, self.profile.creator_id)
        allowed_pools = strategy.get_allowed_content_types()
        allowed_content_types = [p.content_type_id for p in allowed_pools]

        if not allowed_content_types:
            logger.warning("[Step 2] No content types found in vault_matrix")
            self.selection_pool = SelectionPool(
                creator_id=self.profile.creator_id,
                captions=[],
                never_used_count=0,
                fresh_count=0,
                total_weight=0.0,
                content_types=[],
            )
            return self.selection_pool

        logger.info(f"[Step 2] Content type gate: {len(allowed_content_types)} allowed types")

        # Load unified pool using new select_captions module
        try:
            pool = load_unified_pool(
                conn=self.conn,
                creator_id=self.profile.creator_id,
                content_types=allowed_content_types,
                exclusion_days=selection_config.exclusion_days,
                limit=500,
            )

            # Log pool statistics
            log_pool_statistics(pool)

            self.selection_pool = pool
            logger.info(
                f"[Step 2] Loaded unified pool: {len(pool.captions)} captions, "
                f"{pool.never_used_count} never-used, {pool.fresh_count} fresh"
            )

            return pool

        except Exception as e:
            logger.error(f"[Step 2] Failed to load unified pool: {e}")
            # Return empty pool on failure
            self.selection_pool = SelectionPool(
                creator_id=self.profile.creator_id,
                captions=[],
                never_used_count=0,
                fresh_count=0,
                total_weight=0.0,
                content_types=[],
            )
            return self.selection_pool

    def _load_available_captions(self, vault_types: list[int]) -> list[Caption]:
        """Load captions filtered by freshness and vault."""
        query = """
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.caption_type,
                cb.content_type_id,
                ct.type_name AS content_type_name,
                cb.performance_score,
                cb.freshness_score,
                cb.tone,
                cb.emoji_style,
                cb.slang_level,
                cb.is_universal,
                cb.avg_earnings AS global_avg_earnings,
                cb.times_used AS global_times_used,
                ccp.avg_earnings AS creator_avg_earnings,
                ccp.times_used AS creator_times_used,
                COALESCE(ccp.avg_earnings, cb.avg_earnings, 0) AS effective_earnings,
                CASE
                    WHEN ccp.avg_earnings IS NOT NULL AND ccp.avg_earnings > 0 THEN 'creator'
                    WHEN cb.avg_earnings IS NOT NULL AND cb.avg_earnings > 0 THEN 'global'
                    ELSE 'none'
                END AS earnings_source,
                CASE
                    WHEN ccp.times_used IS NULL OR ccp.times_used < ? THEN 1
                    ELSE 0
                END AS is_untested
            FROM caption_bank cb
            LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
            LEFT JOIN vault_matrix vm ON cb.creator_id = vm.creator_id
                AND cb.content_type_id = vm.content_type_id
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id AND ccp.creator_id = ?
            WHERE cb.is_active = 1
              AND (cb.creator_id = ? OR cb.is_universal = 1)
              AND cb.freshness_score >= ?
              AND (vm.has_content = 1 OR vm.vault_id IS NULL OR cb.content_type_id IS NULL)
            ORDER BY effective_earnings DESC, cb.performance_score DESC, cb.freshness_score DESC
            LIMIT 500
        """

        cursor = self.conn.execute(
            query,
            (
                self.config.min_uses_for_tested,
                self.profile.creator_id,
                self.profile.creator_id,
                self.config.min_freshness,
            ),
        )

        captions = []
        for row in cursor.fetchall():
            if row["content_type_id"] and row["content_type_id"] not in vault_types:
                continue

            captions.append(
                Caption(
                    caption_id=row["caption_id"],
                    caption_text=row["caption_text"],
                    caption_type=row["caption_type"],
                    content_type_id=row["content_type_id"],
                    content_type_name=row["content_type_name"],
                    performance_score=row["performance_score"] or 50.0,
                    freshness_score=row["freshness_score"] or 100.0,
                    tone=row["tone"],
                    emoji_style=row["emoji_style"],
                    slang_level=row["slang_level"],
                    is_universal=bool(row["is_universal"]),
                    creator_avg_earnings=row["creator_avg_earnings"],
                    global_avg_earnings=row["global_avg_earnings"],
                    creator_times_used=row["creator_times_used"] or 0,
                    global_times_used=row["global_times_used"] or 0,
                    earnings_source=row["earnings_source"],
                    is_untested=bool(row["is_untested"]),
                )
            )

        # Filter by keywords
        if self.profile.filter_keywords:
            original_count = len(captions)
            captions = [
                c
                for c in captions
                if not any(kw.lower() in c.caption_text.lower() for kw in self.profile.filter_keywords)
            ]
            filtered = original_count - len(captions)
            if filtered > 0:
                logger.info(f"Filtered {filtered} captions by content restriction keywords")

        logger.info(f"[Step 2] Loaded {len(captions)} eligible captions")
        return captions

    def get_vault_type_names(self) -> list[str]:
        """Get vault type names for result metadata."""
        if not self.profile:
            return []

        query = """
            SELECT ct.type_name
            FROM vault_matrix vm
            JOIN content_types ct ON vm.content_type_id = ct.content_type_id
            WHERE vm.creator_id = ? AND vm.has_content = 1
        """
        cursor = self.conn.execute(query, (self.profile.creator_id,))
        return [row["type_name"] for row in cursor.fetchall()]

    # =========================================================================
    # STEP 3: MATCH PERSONA
    # =========================================================================

    def step_3_match_persona(self, captions: list[Caption]) -> list[Caption]:
        """
        Apply persona boost scores to all captions.

        Step 3 of pipeline: MATCH PERSONA (LEGACY)

        .. deprecated::
            This method is deprecated and will be removed in a future version.
            Use :meth:`step_3_get_persona_profile` instead for fresh-focused
            selection. The legacy method mutates Caption objects directly,
            while the fresh method returns a PersonaProfile for use with
            pattern-based scoring in the unified pool.

        Migration Path:
            Legacy (this method):
                captions = builder.step_3_match_persona(captions)
                # Captions now have persona_boost set

            Fresh (preferred):
                persona_profile = builder.step_3_get_persona_profile()
                # Use persona_profile with step_5_assign_captions_fresh()

        Args:
            captions: List of Caption objects to score

        Returns:
            List of captions with persona_boost set (mutated in place)
        """
        import warnings
        warnings.warn(
            "step_3_match_persona() is deprecated. Use step_3_get_persona_profile() "
            "with the fresh pipeline (run_fresh) instead. See docstring for migration path.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self.profile:
            return captions

        from match_persona import PersonaProfile as MatchPersonaProfile
        from match_persona import calculate_persona_boost as full_persona_boost

        persona = MatchPersonaProfile(
            creator_id=self.profile.creator_id,
            page_name=self.profile.page_name,
            primary_tone=self.profile.primary_tone,
            secondary_tone=getattr(self.profile, "secondary_tone", None),
            emoji_frequency=self.profile.emoji_frequency,
            slang_level=self.profile.slang_level,
            avg_sentiment=self.profile.avg_sentiment,
        )

        boosted_count = 0
        for caption in captions:
            match_result = full_persona_boost(
                caption_tone=caption.tone,
                caption_emoji_style=caption.emoji_style,
                caption_slang_level=caption.slang_level,
                persona=persona,
                caption_text=caption.caption_text,
                use_text_detection=True,
            )

            caption.persona_boost = match_result.total_boost
            caption.combined_score = caption.performance_score * 0.6 + caption.freshness_score * 0.4

            if caption.persona_boost > 1.0:
                boosted_count += 1

        logger.info(f"[Step 3] Applied persona scores: {boosted_count}/{len(captions)} boosted")

        # Invoke content strategy agents if available
        if self.agent_invoker and self.agent_context:
            self._invoke_content_strategy_agents()

        return captions

    def step_3_get_persona_profile(self) -> PersonaProfile | None:
        """
        Load and cache persona profile for the creator.

        Step 3 of pipeline: MATCH PERSONA (FRESH - PREFERRED)

        This is the preferred method for persona matching in the fresh pipeline.
        Unlike the deprecated :meth:`step_3_match_persona`, this method:

        1. Returns a PersonaProfile object instead of mutating captions
        2. Works with the unified SelectionPool and pattern-based scoring
        3. Is used by :meth:`step_5_assign_captions_fresh` for fresh-focused selection

        The PersonaProfile is used during caption selection to calculate
        persona match scores dynamically, rather than pre-computing boosts
        on Caption objects.

        Usage:
            builder = ScheduleBuilder(config, conn)
            profile = builder.step_1_analyze()
            pool = builder.step_2_match_content_unified()
            persona = builder.step_3_get_persona_profile()  # Returns PersonaProfile
            items = builder.step_5_assign_captions_fresh(slots, pool, persona)

        Returns:
            PersonaProfile for use in caption selection, or None if not available
        """
        if not self.profile:
            return None

        # Check if already loaded
        if self.persona_profile is not None:
            return self.persona_profile

        # Create PersonaProfile from creator profile data
        self.persona_profile = PersonaProfile(
            creator_id=self.profile.creator_id,
            page_name=self.profile.page_name,
            primary_tone=self.profile.primary_tone,
            secondary_tone=getattr(self.profile, "secondary_tone", None),
            emoji_frequency=self.profile.emoji_frequency,
            favorite_emojis=(),  # Would need to be loaded separately
            slang_level=self.profile.slang_level,
            avg_sentiment=self.profile.avg_sentiment,
            avg_caption_length=100,  # Default
        )

        logger.info(
            f"[Step 3] Loaded persona profile: tone={self.persona_profile.primary_tone}, "
            f"emoji={self.persona_profile.emoji_frequency}, "
            f"slang={self.persona_profile.slang_level}"
        )

        # Invoke content strategy agents if available
        if self.agent_invoker and self.agent_context:
            self._invoke_content_strategy_agents()

        return self.persona_profile

    def _invoke_content_strategy_agents(self) -> None:
        """Invoke content strategy agents."""
        try:
            from shared_context import PersonaProfile

            self.agent_context.persona_profile = PersonaProfile(
                creator_id=self.profile.creator_id,
                primary_tone=self.profile.primary_tone,
                emoji_frequency=self.profile.emoji_frequency,
                favorite_emojis="",
                slang_level=self.profile.slang_level,
                avg_sentiment=self.profile.avg_sentiment,
                avg_caption_length=0,
            )

            # Invoke content rotation architect
            rotation_strategy, rotation_fallback = self.agent_invoker.invoke_content_rotation_architect(
                self.agent_context
            )
            self.agent_context.rotation = rotation_strategy

            if rotation_fallback:
                self.agents_fallback.append("content-rotation-architect")
            else:
                self.agents_used.append("content-rotation-architect")

            # Invoke pricing strategist
            pricing_strategy, pricing_fallback = self.agent_invoker.invoke_pricing_strategist(
                self.agent_context
            )
            self.agent_context.pricing = pricing_strategy

            if pricing_fallback:
                self.agents_fallback.append("pricing-strategist")
            else:
                self.agents_used.append("pricing-strategist")

        except Exception as e:
            logger.warning(f"[AGENT MODE] Content strategy agents failed: {e}")
            self.agents_fallback.extend(["content-rotation-architect", "pricing-strategist"])

    # =========================================================================
    # STEP 4: BUILD STRUCTURE
    # =========================================================================

    def step_4_build_structure(self) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """
        Build weekly time slots with payday optimization.

        Step 4 of pipeline: BUILD STRUCTURE

        Returns:
            Tuple of (slots list, content_type_allocation dict)
        """
        if not self.profile:
            return [], {}

        from content_type_strategy import ContentTypeStrategy
        from weights import calculate_payday_multiplier, is_high_payday_multiplier, is_mid_cycle

        best_hours = self.profile.best_hours or [8, 12, 16, 20]
        slots: list[dict[str, Any]] = []
        slot_id = 0

        # Determine if paid page with weekly strategy
        is_paid_page = self.config.is_paid_page or self.config.page_type == "paid"
        has_weekly_strategy = getattr(self.config, "volume_strategy", None) and self.config.volume_period == "week"

        # Generate PPV slots
        if is_paid_page and has_weekly_strategy:
            slots = self._build_paid_page_slots(best_hours, slot_id)
        else:
            slots = self._build_free_page_slots(best_hours, slot_id)

        # Apply timing variance
        slots = self._apply_timing_variance(slots)

        # Sort by datetime
        slots.sort(key=lambda s: (s["date"], s["time"]))

        # Calculate content type allocation
        ppv_slots = [s for s in slots if s.get("type") == "ppv"]
        total_ppv_slots = len(ppv_slots)

        strategy = ContentTypeStrategy(self.conn, self.profile.creator_id)
        content_type_allocation = strategy.allocate_slots_by_content_type(total_ppv_slots)

        logger.info(f"[Step 4] Built {total_ppv_slots} PPV slots, allocation: {content_type_allocation}")

        return slots, content_type_allocation

    def _build_paid_page_slots(self, best_hours: list[int], start_slot_id: int) -> list[dict[str, Any]]:
        """Build slots for paid page (campaign-style weekly distribution)."""
        from weights import calculate_payday_multiplier, is_high_payday_multiplier, is_mid_cycle

        optimal_days = ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        if hasattr(self.config, "volume_strategy") and self.config.volume_strategy:
            if self.config.volume_strategy.optimal_days:
                optimal_days = self.config.volume_strategy.optimal_days

        weekly_ppv = self.config.ppv_per_week or (self.config.ppv_per_day * 7)
        ppv_per_optimal_day = max(1, weekly_ppv // len(optimal_days))
        remaining_ppv = weekly_ppv

        slots = []
        slot_id = start_slot_id
        current_date = self.config.week_start

        while current_date <= self.config.week_end and remaining_ppv > 0:
            day_name = current_date.strftime("%A")
            payday_mult = calculate_payday_multiplier(current_date)
            payday_optimal = is_high_payday_multiplier(current_date)
            mid_cycle = is_mid_cycle(current_date)

            if day_name in optimal_days:
                day_ppv_count = min(ppv_per_optimal_day, remaining_ppv)
                ppv_hours = self._select_spaced_hours_strict(best_hours, day_ppv_count)

                for i, hour in enumerate(ppv_hours):
                    if remaining_ppv <= 0:
                        break
                    slot_id += 1
                    minute = random.choice([0, 15, 30, 45])
                    slots.append({
                        "slot_id": slot_id,
                        "date": current_date.isoformat(),
                        "day_name": day_name,
                        "time": f"{hour:02d}:{minute:02d}",
                        "hour": hour,
                        "type": "ppv",
                        "priority": 3 if i == 0 else 5,
                        "payday_multiplier": payday_mult,
                        "is_payday_optimal": payday_optimal,
                        "is_mid_cycle": mid_cycle,
                    })
                    remaining_ppv -= 1

            current_date += timedelta(days=1)

        return slots

    def _build_free_page_slots(self, best_hours: list[int], start_slot_id: int) -> list[dict[str, Any]]:
        """Build slots for free page (daily distribution)."""
        from weights import calculate_payday_multiplier, is_high_payday_multiplier, is_mid_cycle

        available_hours = self._generate_spaced_hours(best_hours, self.config.ppv_per_day)
        slots = []
        slot_id = start_slot_id
        current_date = self.config.week_start

        while current_date <= self.config.week_end:
            day_name = current_date.strftime("%A")
            payday_mult = calculate_payday_multiplier(current_date)
            payday_optimal = is_high_payday_multiplier(current_date)
            mid_cycle = is_mid_cycle(current_date)

            ppv_hours = self._select_spaced_hours_strict(available_hours, self.config.ppv_per_day)

            for hour in ppv_hours:
                slot_id += 1
                minute = random.choice([0, 15, 30, 45])
                slots.append({
                    "slot_id": slot_id,
                    "date": current_date.isoformat(),
                    "day_name": day_name,
                    "time": f"{hour:02d}:{minute:02d}",
                    "hour": hour,
                    "type": "ppv",
                    "priority": 3 if hour in best_hours[:3] else 5,
                    "payday_multiplier": payday_mult,
                    "is_payday_optimal": payday_optimal,
                    "is_mid_cycle": mid_cycle,
                })

            current_date += timedelta(days=1)

        return slots

    def _generate_spaced_hours(self, best_hours: list[int], min_count: int) -> list[int]:
        """Generate hours with at least 3-hour spacing."""
        available = list(best_hours)
        all_hours = list(range(8, 23))

        for hour in all_hours:
            if hour not in available:
                has_space = all(abs(hour - h) >= 3 for h in available)
                if has_space:
                    available.append(hour)

        available.sort()
        return available

    def _select_spaced_hours_strict(self, available_hours: list[int], count: int) -> list[int]:
        """Select hours with 4-hour minimum spacing."""
        if count <= 0:
            return []

        ideal_schedules = {
            2: [10, 18],
            3: [8, 14, 20],
            4: [8, 12, 16, 20],
            5: [6, 10, 14, 18, 22],
        }

        if count in ideal_schedules:
            selected = list(ideal_schedules[count])
        else:
            selected = []
            for hour in [10, 14, 18, 22, 8]:
                if len(selected) >= count:
                    break
                has_space = all(abs(hour - h) >= 4 for h in selected)
                if has_space:
                    selected.append(hour)

        # Substitute with best hours where possible
        sorted_best = sorted(available_hours)
        for best_hour in sorted_best:
            for i, ideal_hour in enumerate(selected):
                if abs(best_hour - ideal_hour) <= 2:
                    other_hours = [h for j, h in enumerate(selected) if j != i]
                    has_space = all(abs(best_hour - h) >= 4 for h in other_hours)
                    if has_space and best_hour not in selected:
                        selected[i] = best_hour
                        break

        selected.sort()
        return selected[:count]

    def _apply_timing_variance(self, slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply natural timing variance to prevent robotic patterns."""
        weekend_days = {"Saturday", "Sunday"}

        for slot in slots:
            if slot.get("type") != "ppv":
                continue

            time_str = slot.get("time", "12:00")
            try:
                hour, minute = map(int, time_str.split(":"))
                current_time = time(hour=hour, minute=minute)
            except (ValueError, AttributeError):
                continue

            day_name = slot.get("day_name", "")
            is_weekend = day_name in weekend_days
            variance_minutes = 10 if is_weekend else 7
            variance = random.randint(-variance_minutes, variance_minutes)

            total_minutes = current_time.hour * 60 + current_time.minute + variance
            total_minutes = max(0, min(23 * 60 + 59, total_minutes))

            new_hour = total_minutes // 60
            new_minute = total_minutes % 60

            slot["time"] = f"{new_hour:02d}:{new_minute:02d}"
            slot["hour"] = new_hour

        logger.info("[Step 4] Applied timing variance to slot times")
        return slots

    # =========================================================================
    # STEP 5: ASSIGN CAPTIONS (New Fresh-Focused Method)
    # =========================================================================

    def step_5_assign_captions_fresh(
        self,
        slots: list[dict[str, Any]],
        pool: SelectionPool | None = None,
        persona: PersonaProfile | None = None,
        content_type_allocation: dict[str, int] | None = None,
    ) -> list[ScheduleItem]:
        """
        Assign captions using fresh-focused selection with exploration slots.

        Step 5 of pipeline: ASSIGN CAPTIONS (new unified approach)

        This method uses the new fresh-focused selection algorithm that:
        - Prioritizes never-used captions
        - Uses pattern scoring to predict performance
        - Reserves 15% of slots for exploration/diversity
        - Tracks used attributes for variety

        Args:
            slots: List of slot dicts from step_4_build_structure
            pool: Optional SelectionPool (uses self.selection_pool if not provided)
            persona: Optional PersonaProfile (uses self.persona_profile if not provided)
            content_type_allocation: Optional content type allocation dict

        Returns:
            List of ScheduleItem objects with assigned captions
        """
        from config_loader import load_selection_config
        from select_captions import (
            calculate_persona_match,
            select_exploration_caption,
            select_from_unified_pool,
        )
        from weights import calculate_fresh_weight

        # Use instance attributes if not provided
        if pool is None:
            pool = self.selection_pool
        if persona is None:
            persona = self.persona_profile
        pattern_profile = self.pattern_profile

        if pool is None or not pool.captions:
            logger.warning("[Step 5] No captions in pool, returning empty schedule")
            return []

        # Load selection config for exploration ratio
        try:
            selection_config = load_selection_config()
            exploration_ratio = selection_config.exploration_ratio
        except Exception:
            exploration_ratio = 0.15  # Default 15%

        # Filter to PPV slots only
        ppv_slots = [s for s in slots if s.get("type") == "ppv"]
        total_slots = len(ppv_slots)

        if total_slots == 0:
            logger.warning("[Step 5] No PPV slots to fill")
            return []

        # Calculate exploration slot count and indices
        num_exploration = int(total_slots * exploration_ratio)
        exploration_indices = set(random.sample(range(total_slots), num_exploration)) if num_exploration > 0 else set()

        logger.info(
            f"[Step 5] Assigning captions: {total_slots} PPV slots, "
            f"{num_exploration} exploration slots ({exploration_ratio*100:.0f}%)"
        )

        # Track used captions and attributes for diversity
        exclude_ids: set[int] = set()
        schedule_context: dict[str, Any] = {
            "used_hook_types": set(),
            "used_tones": set(),
            "content_type_counts": {},
            "target_content_distribution": content_type_allocation or {},
        }

        items: list[ScheduleItem] = []
        exploration_count = 0

        for i, slot in enumerate(ppv_slots):
            is_exploration = i in exploration_indices
            caption: ScoredCaption | None = None

            if is_exploration:
                # Try exploration selection first (prioritizes diversity)
                caption = select_exploration_caption(
                    pool, pattern_profile, schedule_context, exclude_ids
                )
                if caption is not None:
                    exploration_count += 1
                else:
                    # Fall back to standard selection
                    is_exploration = False
                    selected = select_from_unified_pool(
                        pool, pattern_profile, persona, exclude_ids, count=1
                    )
                    caption = selected[0] if selected else None
            else:
                # Standard selection using pattern-guided weights
                selected = select_from_unified_pool(
                    pool, pattern_profile, persona, exclude_ids, count=1
                )
                caption = selected[0] if selected else None

            if caption:
                # Update tracking
                exclude_ids.add(caption.caption_id)

                if caption.hook_type:
                    schedule_context["used_hook_types"].add(caption.hook_type)
                if caption.tone:
                    schedule_context["used_tones"].add(caption.tone)
                if caption.content_type_name:
                    ct_name = caption.content_type_name
                    schedule_context["content_type_counts"][ct_name] = (
                        schedule_context["content_type_counts"].get(ct_name, 0) + 1
                    )

                # Calculate price based on slot context
                # NOTE: This is a placeholder price - Step 8 will recalculate using
                # the full page-type-aware pricing matrix from CLAUDE.md 2025 rates
                base_price = 14.99 if self.config.page_type == "paid" else 9.99
                payday_mult = slot.get("payday_multiplier", 1.0)
                is_payday_optimal = slot.get("is_payday_optimal", False)
                is_mid_cycle = slot.get("is_mid_cycle", False)

                # Payday adjustments (Step 8 will apply final content-type pricing)
                if is_payday_optimal:
                    base_price *= 1.15
                elif is_mid_cycle:
                    base_price *= 0.95

                # Build selection note
                slot_type = "exploration" if is_exploration else "standard"
                freshness_tier = caption.freshness_tier or "unknown"
                payday_tag = ""
                if is_payday_optimal:
                    payday_tag = " | PAYDAY"
                elif is_mid_cycle:
                    payday_tag = " | mid-cycle"

                selection_note = (
                    f"Selection: {slot_type} | Tier: {freshness_tier} | "
                    f"Pattern: {caption.pattern_score:.1f} | "
                    f"Weight: {caption.selection_weight:.1f}{payday_tag}"
                )

                items.append(
                    ScheduleItem(
                        item_id=slot["slot_id"],
                        creator_id=self.config.creator_id,
                        scheduled_date=slot["date"],
                        scheduled_time=slot["time"],
                        item_type=get_item_type_for_content_type(caption.content_type_name),
                        caption_id=caption.caption_id,
                        caption_text=caption.caption_text,
                        content_type_id=caption.content_type_id,
                        content_type_name=caption.content_type_name,
                        suggested_price=round(base_price, 2),
                        freshness_score=caption.freshness_score,
                        performance_score=caption.pattern_score,  # Use pattern score
                        priority=slot.get("priority", 5),
                        notes=selection_note,
                    )
                )

        logger.info(
            f"[Step 5] Caption assignment complete: {len(items)} items, "
            f"{exploration_count} exploration slots filled, "
            f"content distribution: {schedule_context['content_type_counts']}"
        )

        return items

    def get_pipeline_context(self) -> dict[str, Any]:
        """
        Return pipeline context including pattern profile for debugging/LLM context.

        Returns:
            Dictionary with creator profile, pattern profile, and pipeline state
        """
        context: dict[str, Any] = {
            "creator_id": self.config.creator_id,
            "creator_name": self.config.creator_name,
            "week_start": self.config.week_start.isoformat() if self.config.week_start else None,
            "week_end": self.config.week_end.isoformat() if self.config.week_end else None,
            "volume_level": self.profile.volume_level if self.profile else None,
            "page_type": self.config.page_type,
        }

        # Add pattern profile data
        if self.pattern_profile:
            profile = self.pattern_profile
            context["pattern_profile"] = {
                "sample_count": profile.sample_count,
                "confidence": profile.confidence,
                "is_global_fallback": profile.is_global_fallback,
                "combined_patterns_count": len(profile.combined_patterns),
                "content_type_patterns_count": len(profile.content_type_patterns),
                "tone_patterns_count": len(profile.tone_patterns),
                "hook_patterns_count": len(profile.hook_patterns),
                "top_content_types": self._get_top_patterns(profile.content_type_patterns),
                "top_tones": self._get_top_patterns(profile.tone_patterns),
            }
        else:
            context["pattern_profile"] = None

        # Add selection pool stats
        if self.selection_pool:
            pool = self.selection_pool
            context["selection_pool"] = {
                "total_captions": len(pool.captions),
                "never_used_count": pool.never_used_count,
                "fresh_count": pool.fresh_count,
                "total_weight": pool.total_weight,
                "content_types": pool.content_types,
            }
        else:
            context["selection_pool"] = None

        # Add persona profile
        if self.persona_profile:
            context["persona_profile"] = {
                "primary_tone": self.persona_profile.primary_tone,
                "emoji_frequency": self.persona_profile.emoji_frequency,
                "slang_level": self.persona_profile.slang_level,
            }
        else:
            context["persona_profile"] = None

        return context

    def _get_top_patterns(
        self, patterns: dict[str, Any], limit: int = 5
    ) -> list[dict[str, Any]]:
        """Extract top N patterns by normalized score."""
        if not patterns:
            return []

        sorted_patterns = sorted(
            patterns.items(),
            key=lambda x: x[1].normalized_score if hasattr(x[1], "normalized_score") else 0,
            reverse=True,
        )

        return [
            {
                "name": name,
                "avg_earnings": stats.avg_earnings if hasattr(stats, "avg_earnings") else 0,
                "sample_count": stats.sample_count if hasattr(stats, "sample_count") else 0,
                "score": stats.normalized_score if hasattr(stats, "normalized_score") else 0,
            }
            for name, stats in sorted_patterns[:limit]
        ]


# =============================================================================
# STEP 5: ASSIGN CAPTIONS (Legacy Functions)
# =============================================================================


def assign_captions(
    slots: list[dict[str, Any]],
    captions: list[Caption],
    config: ScheduleConfig,
    pools: dict[int, StratifiedPools] | None = None,
    persona: dict[str, str] | None = None,
    content_type_allocation: dict[str, int] | None = None,
) -> list[ScheduleItem]:
    """
    Assign captions to time slots using pool-based selection.

    Step 5 of pipeline: ASSIGN CAPTIONS (LEGACY)

    .. deprecated::
        This function is deprecated. Use
        :meth:`ScheduleBuilder.step_5_assign_captions_fresh` instead for
        fresh-focused selection with pattern-based scoring.

    Args:
        slots: List of slot dicts with date, time, hour, type keys
        captions: List of Caption objects (for legacy mode)
        config: Schedule configuration
        pools: Optional stratified pools for pool-based selection
        persona: Optional creator persona dict
        content_type_allocation: Optional content type slot allocation

    Returns:
        List of ScheduleItem objects
    """
    import warnings
    warnings.warn(
        "assign_captions() is deprecated. Use ScheduleBuilder.step_5_assign_captions_fresh() "
        "with the fresh pipeline (run_fresh) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from content_type_strategy import PREMIUM_HOURS
    from weights import POOL_DISCOVERY, POOL_GLOBAL_EARNER, POOL_PROVEN, calculate_weight, get_max_earnings

    if pools is not None and persona is not None and content_type_allocation is not None:
        return _assign_captions_pooled(
            slots, pools, persona, content_type_allocation, config
        )

    # Legacy fallback
    return _assign_captions_legacy(slots, captions, config)


def _assign_captions_pooled(
    slots: list[dict[str, Any]],
    pools: dict[int, StratifiedPools],
    persona: dict[str, str],
    content_type_allocation: dict[str, int],
    config: ScheduleConfig,
) -> list[ScheduleItem]:
    """Pool-based caption assignment."""
    from content_type_strategy import PREMIUM_HOURS
    from weights import POOL_DISCOVERY, POOL_GLOBAL_EARNER, POOL_PROVEN, calculate_weight, get_max_earnings

    ppv_slots = [s for s in slots if s.get("type") == "ppv"]
    total_ppv_slots = len(ppv_slots)

    if total_ppv_slots == 0 or not pools:
        return []

    # Calculate slot tier distribution
    discovery_ratio = config.reserved_slot_ratio
    premium_ratio = 0.25
    discovery_count = int(total_ppv_slots * discovery_ratio)
    premium_count = int(total_ppv_slots * premium_ratio)

    # Identify premium slots (peak hours)
    premium_slot_indices: set[int] = set()
    for i, slot in enumerate(ppv_slots):
        if slot.get("hour") in PREMIUM_HOURS:
            if len(premium_slot_indices) < premium_count:
                premium_slot_indices.add(i)

    # Identify discovery slots (distributed evenly)
    discovery_candidates = [i for i in range(total_ppv_slots) if i not in premium_slot_indices]
    discovery_slot_indices = _identify_discovery_slots(discovery_candidates, discovery_count)

    # Track content type usage
    content_type_used: dict[str, int] = dict.fromkeys(content_type_allocation.keys(), 0)
    available_types = set(content_type_allocation.keys())

    items: list[ScheduleItem] = []
    used_caption_ids: set[int] = set()
    previous_content_type: str | None = None

    for slot_index, slot in enumerate(ppv_slots):
        # Determine slot tier
        if slot_index in premium_slot_indices:
            slot_tier = "premium"
        elif slot_index in discovery_slot_indices:
            slot_tier = "discovery"
        else:
            slot_tier = "standard"

        is_payday_optimal = slot.get("is_payday_optimal", False)
        slot_is_mid_cycle = slot.get("is_mid_cycle", False)

        # Select target content type
        target_type = _select_target_content_type(
            available_types,
            content_type_allocation,
            content_type_used,
            previous_content_type,
            is_payday_optimal,
            slot_is_mid_cycle,
        )

        # Select caption from pool
        selected_caption, pool_type = _select_from_stratified_pool(
            pools, target_type, slot_tier, used_caption_ids, previous_content_type, config
        )

        if selected_caption:
            used_caption_ids.add(selected_caption.caption_id)
            previous_content_type = selected_caption.content_type_name

            ct_name = selected_caption.content_type_name or "unknown"
            content_type_used[ct_name] = content_type_used.get(ct_name, 0) + 1

            # Calculate placeholder price
            # NOTE: Step 8 will recalculate using full page-type-aware pricing matrix
            base_price = 14.99 if config.page_type == "paid" else 9.99
            if selected_caption.performance_score >= 80:
                base_price *= 1.2
            elif selected_caption.performance_score < 50:
                base_price *= 0.9

            payday_mult = slot.get("payday_multiplier", 1.0)
            payday_tag = ""
            if is_payday_optimal:
                payday_tag = " | Payday: OPTIMAL"
            elif slot_is_mid_cycle:
                payday_tag = " | Payday: mid-cycle"

            selection_note = (
                f"Pool: {pool_type} | Tier: {slot_tier} | "
                f"Boost: {selected_caption.persona_boost:.2f}x | "
                f"PaydayMult: {payday_mult:.2f}x{payday_tag}"
            )

            items.append(
                ScheduleItem(
                    item_id=slot["slot_id"],
                    creator_id=config.creator_id,
                    scheduled_date=slot["date"],
                    scheduled_time=slot["time"],
                    item_type=get_item_type_for_content_type(selected_caption.content_type_name),
                    caption_id=selected_caption.caption_id,
                    caption_text=selected_caption.caption_text,
                    content_type_id=selected_caption.content_type_id,
                    content_type_name=selected_caption.content_type_name,
                    suggested_price=round(base_price, 2),
                    freshness_score=selected_caption.freshness_score,
                    performance_score=selected_caption.performance_score,
                    priority=slot["priority"],
                    notes=selection_note,
                )
            )

    logger.info(f"[Step 5] Content type distribution: {content_type_used}")
    return items


def _assign_captions_legacy(
    slots: list[dict[str, Any]],
    captions: list[Caption],
    config: ScheduleConfig,
) -> list[ScheduleItem]:
    """Legacy caption assignment (fallback)."""
    from utils import VoseAliasSelector

    if not captions:
        return []

    # Partition captions
    tested = [c for c in captions if not c.is_untested and (c.creator_times_used or 0) >= config.min_uses_for_tested]
    untested = [c for c in captions if c not in tested]

    ppv_slots = [s for s in slots if s["type"] == "ppv"]
    total_ppv_slots = len(ppv_slots)

    # Build selectors
    tested_selector = None
    untested_selector = None

    if tested:
        try:
            tested_selector = VoseAliasSelector(tested, lambda c: c.final_weight)
        except ValueError:
            pass

    if untested:
        try:
            untested_selector = VoseAliasSelector(untested, lambda c: c.freshness_score * c.persona_boost)
        except ValueError:
            pass

    items = []
    used_caption_ids: set[int] = set()
    previous_content_type: str | None = None

    for slot in slots:
        if slot["type"] != "ppv":
            continue

        target_type = _get_next_content_type(previous_content_type, {c.content_type_name for c in captions if c.content_type_name})
        selected_caption: Caption | None = None

        # Try tested pool first
        if tested_selector:
            for _ in range(50):
                candidate = tested_selector.select()
                if candidate.caption_id not in used_caption_ids:
                    if candidate.content_type_name != previous_content_type or previous_content_type is None:
                        selected_caption = candidate
                        break

        # Fallback to first unused
        if not selected_caption:
            for c in captions:
                if c.caption_id not in used_caption_ids:
                    selected_caption = c
                    break

        if selected_caption:
            used_caption_ids.add(selected_caption.caption_id)
            previous_content_type = selected_caption.content_type_name

            # Calculate placeholder price
            # NOTE: Step 8 will recalculate using full page-type-aware pricing matrix
            base_price = 14.99 if config.page_type == "paid" else 9.99
            if selected_caption.performance_score >= 80:
                base_price *= 1.2
            elif selected_caption.performance_score < 50:
                base_price *= 0.9

            items.append(
                ScheduleItem(
                    item_id=slot["slot_id"],
                    creator_id=config.creator_id,
                    scheduled_date=slot["date"],
                    scheduled_time=slot["time"],
                    item_type=get_item_type_for_content_type(selected_caption.content_type_name),
                    caption_id=selected_caption.caption_id,
                    caption_text=selected_caption.caption_text,
                    content_type_id=selected_caption.content_type_id,
                    content_type_name=selected_caption.content_type_name,
                    suggested_price=round(base_price, 2),
                    freshness_score=selected_caption.freshness_score,
                    performance_score=selected_caption.performance_score,
                    priority=slot["priority"],
                    notes=f"Boost: {selected_caption.persona_boost:.2f}x",
                )
            )

    return items


def _identify_discovery_slots(candidates: list[int], count: int) -> set[int]:
    """Distribute discovery slots evenly across the week."""
    if not candidates or count <= 0:
        return set()

    total = len(candidates)
    if count >= total:
        return set(candidates)

    indices = set()
    step = total / count
    for i in range(count):
        idx = int(i * step + step / 2)
        idx = min(idx, total - 1)
        indices.add(candidates[idx])

    return indices


def _select_target_content_type(
    available_types: set[str],
    content_type_allocation: dict[str, int],
    content_type_used: dict[str, int],
    previous_content_type: str | None,
    is_payday_optimal: bool = False,
    is_mid_cycle: bool = False,
) -> str | None:
    """Select target content type with payday-aware prioritization."""
    remaining_allocation: dict[str, int] = {}
    for ct_name in available_types:
        if ct_name == previous_content_type:
            continue
        allocated = content_type_allocation.get(ct_name, 0)
        used = content_type_used.get(ct_name, 0)
        remaining = allocated - used
        if remaining > 0:
            remaining_allocation[ct_name] = remaining

    if not remaining_allocation:
        return _get_next_content_type(previous_content_type, available_types)

    # Apply payday-aware weighting
    weighted_types: list[tuple[str, float]] = []
    for ct_name, remaining in remaining_allocation.items():
        weight = float(remaining)
        is_premium = ct_name in PREMIUM_CONTENT_TYPES

        if is_payday_optimal and is_premium:
            weight *= PAYDAY_PREMIUM_BOOST
        elif is_mid_cycle and is_premium:
            weight *= PAYDAY_PREMIUM_PENALTY

        weighted_types.append((ct_name, weight))

    if weighted_types:
        types, weights = zip(*weighted_types, strict=True)
        total_weight = sum(weights)
        if total_weight > 0:
            probs = [w / total_weight for w in weights]
            return random.choices(types, weights=probs, k=1)[0]

    return next(iter(remaining_allocation.keys()), None)


def _get_next_content_type(previous_type: str | None, available_types: set[str]) -> str | None:
    """Get next content type following rotation pattern."""
    if not available_types:
        return None

    candidates = [t for t in available_types if t != previous_type]
    if not candidates:
        return list(available_types)[0] if available_types else None

    for rotation_type in ROTATION_ORDER:
        if rotation_type in candidates:
            return rotation_type

    return random.choice(candidates)


def _select_from_stratified_pool(
    pools: dict[int, StratifiedPools],
    target_content_type: str | None,
    slot_tier: str,
    used_ids: set[int],
    previous_type: str | None,
    config: ScheduleConfig,
) -> tuple[Caption | None, str]:
    """Select caption from stratified pools based on slot tier."""
    from weights import POOL_DISCOVERY, POOL_GLOBAL_EARNER, POOL_PROVEN, calculate_weight, get_max_earnings

    if slot_tier == "premium":
        pool_priority = [POOL_PROVEN]
    elif slot_tier == "discovery":
        pool_priority = [POOL_DISCOVERY, POOL_GLOBAL_EARNER]
    else:
        pool_priority = [POOL_PROVEN, POOL_GLOBAL_EARNER]

    # Find matching content type pools
    target_pools: list[StratifiedPools] = []
    if target_content_type:
        for _ct_id, pool in pools.items():
            if pool.content_type_name == target_content_type:
                target_pools.append(pool)
                break

    if not target_pools:
        for _ct_id, pool in pools.items():
            if pool.content_type_name != previous_type:
                target_pools.append(pool)

    # Try each pool tier in priority order
    for pool_type in pool_priority:
        for sp in target_pools:
            if pool_type == POOL_PROVEN:
                candidates = sp.proven
            elif pool_type == POOL_GLOBAL_EARNER:
                candidates = sp.global_earner
            else:
                candidates = sp.discovery

            available = [c for c in candidates if c.caption_id not in used_ids]
            if not available:
                continue

            max_earnings = get_max_earnings(available, pool_type)

            for caption in available:
                caption.final_weight = calculate_weight(
                    caption,
                    pool_type=pool_type,
                    content_type_avg_earnings=sp.content_type_avg_earnings,
                    max_earnings=max_earnings,
                    persona_boost=caption.persona_boost,
                )

            weights = [c.final_weight for c in available]
            total_weight = sum(weights)
            if total_weight > 0:
                selected = random.choices(available, weights=weights, k=1)[0]
                return selected, pool_type

            if available:
                return available[0], pool_type

    return None, "none"


__all__ = [
    "ScheduleBuilder",
    "assign_captions",
    "parse_content_notes",
    "extract_filter_keywords",
    "extract_price_modifiers",
]
