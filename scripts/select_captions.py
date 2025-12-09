#!/usr/bin/env python3
"""
Select Captions - Pool-based caption selection using stratified earnings methodology.

This script implements multi-stage pool-based selection of captions using
the Vose Alias Method for O(1) selection time after O(n) preprocessing.

Pool Classification:
- PROVEN: creator_times_used >= 3 AND creator_avg_earnings > 0
  (Captions with proven performance for THIS creator)
- GLOBAL_EARNER: creator_times_used < 3 AND global_times_used >= 3 AND global_avg_earnings > 0
  (Captions that earn globally but untested for this creator)
- DISCOVERY: All others (new imports, under-tested, or no earnings data)

Weight Formula:
    Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery Bonus(10%)

Slot Types:
- premium: PROVEN pool only (highest earners for prime time slots)
- standard: PROVEN + GLOBAL_EARNER pools (normal PPV slots)
- discovery: DISCOVERY pool with import prioritization (exploration slots)

Usage:
    python select_captions.py --creator missalexa --count 10
    python select_captions.py --creator-id abc123 --count 20 --slot-type premium
    python select_captions.py --creator missalexa --count 5 --output captions.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from utils import VoseAliasSelector
from weights import (
    calculate_weight,
    calculate_discovery_bonus,
    get_max_earnings,
    POOL_PROVEN,
    POOL_GLOBAL_EARNER,
    POOL_DISCOVERY,
    EARNINGS_WEIGHT,
    FRESHNESS_WEIGHT,
    PERSONA_WEIGHT,
    DISCOVERY_BONUS_WEIGHT,
)
from content_type_strategy import (
    get_content_type_earnings,
    ContentTypeStrategy,
)


# =============================================================================
# PATH CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
HOME_DIR = Path.home()

# Database path resolution with multiple candidate locations
_env_db_path = os.environ.get("EROS_DATABASE_PATH", "")
DB_PATH_CANDIDATES = [
    Path(_env_db_path) if _env_db_path else None,
    HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / ".eros" / "eros.db",
]
DB_PATH_CANDIDATES = [p for p in DB_PATH_CANDIDATES if p is not None]

DB_PATH = next(
    (p for p in DB_PATH_CANDIDATES if p.exists()),
    DB_PATH_CANDIDATES[1] if len(DB_PATH_CANDIDATES) > 1 else DB_PATH_CANDIDATES[0]
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Pool classification thresholds
MIN_USES_FOR_PROVEN: int = 3
"""Minimum creator-specific uses to be considered PROVEN."""

MIN_USES_FOR_GLOBAL_EARNER: int = 3
"""Minimum global uses to be considered GLOBAL_EARNER."""

# Import recency window
RECENT_IMPORT_DAYS: int = 30
"""Days since import to be considered 'recent' for prioritization."""

# Persona matching
NO_MATCH_PENALTY: float = 0.95
"""Penalty applied when no persona signals match (5% reduction)."""


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Caption:
    """Caption data for pool-based selection."""

    # Core identification
    caption_id: int
    caption_text: str
    caption_type: str
    content_type_id: int | None
    content_type_name: str | None

    # Performance metrics
    performance_score: float
    freshness_score: float

    # Persona matching attributes
    tone: str | None
    emoji_style: str | None
    slang_level: str | None
    is_universal: bool

    # Pool classification
    pool_type: str = POOL_DISCOVERY
    """Pool classification: 'PROVEN', 'GLOBAL_EARNER', or 'DISCOVERY'."""

    # Earnings data
    creator_avg_earnings: float | None = None
    """Creator-specific average earnings (from caption_creator_performance)."""

    global_avg_earnings: float | None = None
    """Global average earnings (from caption_bank)."""

    creator_times_used: int = 0
    """Times this caption was used by THIS creator."""

    global_times_used: int = 0
    """Total global times used across all creators."""

    # Source tracking
    source: str = "internal"
    """Caption source: 'internal' or 'external_import'."""

    imported_at: str | None = None
    """Timestamp of import (ISO format) for external imports."""

    # Computed scores
    combined_score: float = 0.0
    persona_boost: float = 1.0
    final_weight: float = 0.0


@dataclass
class StratifiedPools:
    """Captions stratified into 3 pools per content type."""

    content_type_id: int
    type_name: str
    proven: list[Caption] = field(default_factory=list)
    """Captions with creator_times_used >= 3 and creator_avg_earnings > 0."""

    global_earners: list[Caption] = field(default_factory=list)
    """Captions with global_times_used >= 3, untested on this creator."""

    discovery: list[Caption] = field(default_factory=list)
    """Under-tested or new imports."""

    @property
    def total_count(self) -> int:
        """Total captions across all pools."""
        return len(self.proven) + len(self.global_earners) + len(self.discovery)

    def get_expected_earnings(self) -> float:
        """
        Weighted average expected earnings for this content type.

        Priority:
        1. Mean of creator_avg_earnings from PROVEN pool
        2. Mean of global_avg_earnings from GLOBAL_EARNER pool (with 20% discount)
        3. Mean of performance_score from DISCOVERY pool (as proxy, 50% discount)
        4. Default fallback of $50
        """
        if self.proven:
            proven_earnings = [
                c.creator_avg_earnings
                for c in self.proven
                if c.creator_avg_earnings is not None and c.creator_avg_earnings > 0
            ]
            if proven_earnings:
                return statistics.mean(proven_earnings)

        if self.global_earners:
            global_earnings = [
                c.global_avg_earnings
                for c in self.global_earners
                if c.global_avg_earnings is not None and c.global_avg_earnings > 0
            ]
            if global_earnings:
                return statistics.mean(global_earnings) * 0.8

        if self.discovery:
            discovery_scores = [c.performance_score for c in self.discovery]
            if discovery_scores:
                return statistics.mean(discovery_scores) * 0.5

        return 50.0

    def get_all_captions(self) -> list[Caption]:
        """Return all captions from all pools."""
        return self.proven + self.global_earners + self.discovery


# =============================================================================
# PERSONA MATCHING
# =============================================================================

def calculate_persona_boost(caption: Caption, persona: dict[str, str]) -> float:
    """
    Calculate persona boost factor for a caption.

    Boost factors:
    - Primary tone match: 1.20x
    - Emoji frequency match: 1.10x (cumulative)
    - Slang level match: 1.10x (cumulative)
    - Maximum combined: 1.40x (capped)
    - No match penalty: 0.95x (when zero signals match)

    Args:
        caption: Caption to evaluate
        persona: Creator persona dict with primary_tone, emoji_frequency, slang_level

    Returns:
        Boost factor between 0.95 and 1.4
    """
    boost = 1.0
    has_any_match = False

    # Primary tone match (1.20x)
    if caption.tone and persona.get("primary_tone"):
        if caption.tone.lower() == persona["primary_tone"].lower():
            boost *= 1.20
            has_any_match = True

    # Emoji frequency match (1.10x)
    if caption.emoji_style and persona.get("emoji_frequency"):
        if caption.emoji_style.lower() == persona["emoji_frequency"].lower():
            boost *= 1.10
            has_any_match = True

    # Slang level match (1.10x)
    if caption.slang_level and persona.get("slang_level"):
        if caption.slang_level.lower() == persona["slang_level"].lower():
            boost *= 1.10
            has_any_match = True

    # Apply no-match penalty if zero signals matched
    if not has_any_match:
        return NO_MATCH_PENALTY

    # Cap at 1.40x
    return min(boost, 1.40)


# =============================================================================
# DATABASE LOADING
# =============================================================================

def load_persona(conn: sqlite3.Connection, creator_id: str) -> dict[str, str]:
    """Load creator persona from database."""
    query = """
        SELECT primary_tone, emoji_frequency, slang_level
        FROM creator_personas
        WHERE creator_id = ?
    """
    cursor = conn.execute(query, (creator_id,))
    row = cursor.fetchone()

    if row:
        return {
            "primary_tone": row["primary_tone"] or "",
            "emoji_frequency": row["emoji_frequency"] or "",
            "slang_level": row["slang_level"] or "",
        }

    return {}


def load_stratified_pools(
    conn: sqlite3.Connection,
    creator_id: str,
    allowed_content_types: list[int] | None = None,
    min_freshness: float = 30.0,
    min_uses_for_proven: int = MIN_USES_FOR_PROVEN,
) -> dict[int, StratifiedPools]:
    """
    Load captions into stratified pools per content type.

    Pool Classification:
    - PROVEN: creator_times_used >= min_uses_for_proven AND creator_avg_earnings > 0
    - GLOBAL_EARNER: creator_times_used < min_uses_for_proven
                     AND global_times_used >= MIN_USES_FOR_GLOBAL_EARNER
                     AND global_avg_earnings > 0
    - DISCOVERY: All others (new imports, under-tested)

    Args:
        conn: Database connection with row_factory set
        creator_id: Creator UUID
        allowed_content_types: Optional list of content_type_ids to filter
            If None, loads all content types from vault_matrix
        min_freshness: Minimum freshness score
        min_uses_for_proven: Uses threshold for PROVEN classification

    Returns:
        Dict mapping content_type_id -> StratifiedPools
    """
    # If no allowed_content_types provided, get from vault_matrix
    if allowed_content_types is None:
        vault_query = """
            SELECT content_type_id FROM vault_matrix
            WHERE creator_id = ? AND has_content = 1
        """
        vault_cursor = conn.execute(vault_query, (creator_id,))
        allowed_content_types = [row["content_type_id"] for row in vault_cursor.fetchall()]

    if not allowed_content_types:
        return {}

    # Build placeholders for IN clause
    placeholders = ",".join("?" * len(allowed_content_types))

    query = f"""
        WITH creator_perf AS (
            SELECT caption_id, avg_earnings, times_used
            FROM caption_creator_performance
            WHERE creator_id = ?
        )
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
            cb.source,
            cb.imported_at,
            -- Global data
            cb.avg_earnings AS global_avg_earnings,
            cb.times_used AS global_times_used,
            -- Creator-specific data
            cp.avg_earnings AS creator_avg_earnings,
            COALESCE(cp.times_used, 0) AS creator_times_used,
            -- Pool classification
            CASE
                WHEN COALESCE(cp.times_used, 0) >= ? AND COALESCE(cp.avg_earnings, 0) > 0
                    THEN 'PROVEN'
                WHEN COALESCE(cp.times_used, 0) < ?
                     AND COALESCE(cb.times_used, 0) >= ?
                     AND COALESCE(cb.avg_earnings, 0) > 0
                    THEN 'GLOBAL_EARNER'
                ELSE 'DISCOVERY'
            END AS pool_type
        FROM caption_bank cb
        LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
        LEFT JOIN creator_perf cp ON cb.caption_id = cp.caption_id
        WHERE cb.is_active = 1
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= ?
          AND cb.content_type_id IN ({placeholders})
        ORDER BY pool_type, COALESCE(cp.avg_earnings, cb.avg_earnings, 0) DESC
    """

    # Parameter order for query
    params: list[Any] = [
        creator_id,                    # CTE WHERE
        min_uses_for_proven,           # CASE WHEN (PROVEN check)
        min_uses_for_proven,           # CASE WHEN (GLOBAL_EARNER check)
        MIN_USES_FOR_GLOBAL_EARNER,    # CASE WHEN (global times used)
        creator_id,                    # Main WHERE creator_id
        min_freshness,                 # Main WHERE freshness_score
    ]
    params.extend(allowed_content_types)  # IN clause

    cursor = conn.execute(query, params)

    # Initialize pools for each content type
    pools: dict[int, StratifiedPools] = {}
    content_type_names: dict[int, str] = {}

    for row in cursor.fetchall():
        content_type_id = row["content_type_id"]
        type_name = row["content_type_name"] or "unknown"

        # Create pool if not exists
        if content_type_id not in pools:
            pools[content_type_id] = StratifiedPools(
                content_type_id=content_type_id,
                type_name=type_name,
            )
            content_type_names[content_type_id] = type_name

        caption = Caption(
            caption_id=row["caption_id"],
            caption_text=row["caption_text"],
            caption_type=row["caption_type"],
            content_type_id=content_type_id,
            content_type_name=type_name,
            performance_score=row["performance_score"] or 50.0,
            freshness_score=row["freshness_score"] or 100.0,
            tone=row["tone"],
            emoji_style=row["emoji_style"],
            slang_level=row["slang_level"],
            is_universal=bool(row["is_universal"]),
            pool_type=row["pool_type"],
            creator_avg_earnings=row["creator_avg_earnings"],
            global_avg_earnings=row["global_avg_earnings"],
            creator_times_used=row["creator_times_used"] or 0,
            global_times_used=row["global_times_used"] or 0,
            source=row["source"] or "internal",
            imported_at=row["imported_at"],
        )

        # Add to appropriate pool
        pool = pools[content_type_id]
        if caption.pool_type == POOL_PROVEN:
            pool.proven.append(caption)
        elif caption.pool_type == POOL_GLOBAL_EARNER:
            pool.global_earners.append(caption)
        else:
            pool.discovery.append(caption)

    # Ensure all requested content types have pools (even if empty)
    for ct_id in allowed_content_types:
        if ct_id not in pools:
            # Get type name from database
            name_cursor = conn.execute(
                "SELECT type_name FROM content_types WHERE content_type_id = ?",
                (ct_id,)
            )
            name_row = name_cursor.fetchone()
            type_name = name_row["type_name"] if name_row else "unknown"
            pools[ct_id] = StratifiedPools(
                content_type_id=ct_id,
                type_name=type_name,
            )

    return pools


# =============================================================================
# POOL-SPECIFIC SELECTION FUNCTIONS
# =============================================================================

def _get_content_type_weights(
    pools: dict[int, StratifiedPools],
    content_type_weights: dict[str, float] | None = None,
    exclude_content_type: str | None = None,
) -> dict[str, float]:
    """
    Get normalized content type weights for selection.

    Args:
        pools: Stratified pools by content type
        content_type_weights: Optional pre-calculated weights by type name
        exclude_content_type: Content type to exclude from selection

    Returns:
        Dict mapping type_name to weight (normalized to sum to 1.0)
    """
    if content_type_weights is None:
        # Equal weights if not provided
        weights = {
            pool.type_name: 1.0
            for pool in pools.values()
            if pool.type_name != exclude_content_type
        }
    else:
        weights = {
            type_name: weight
            for type_name, weight in content_type_weights.items()
            if type_name != exclude_content_type
        }

    # Normalize
    total = sum(weights.values())
    if total > 0:
        return {name: w / total for name, w in weights.items()}
    return weights


def _calculate_weight_for_caption(
    caption: Caption,
    persona: dict[str, str],
    content_type_avg_earnings: float,
    max_earnings: float,
) -> float:
    """
    Calculate final weight for a caption using the new formula.

    Args:
        caption: Caption to calculate weight for
        persona: Creator persona for boost calculation
        content_type_avg_earnings: Average earnings for this content type
        max_earnings: Maximum earnings for normalization

    Returns:
        Final weight value
    """
    persona_boost = calculate_persona_boost(caption, persona)
    caption.persona_boost = persona_boost

    weight = calculate_weight(
        caption=caption,
        pool_type=caption.pool_type,
        content_type_avg_earnings=content_type_avg_earnings,
        max_earnings=max_earnings,
        persona_boost=persona_boost,
    )

    caption.final_weight = weight
    caption.combined_score = weight
    return weight


def select_from_proven_pool(
    pools: dict[int, StratifiedPools],
    persona: dict[str, str],
    exclude_ids: set[int],
    exclude_content_type: str | None = None,
    content_type_weights: dict[str, float] | None = None,
) -> Caption | None:
    """
    Select from PROVEN pool only, weighted by earnings.

    Used for premium slots where we want proven performers.

    Args:
        pools: Stratified pools by content type
        persona: Creator persona for boost calculation
        exclude_ids: Caption IDs already selected (to avoid duplicates)
        exclude_content_type: Content type to exclude (for variety)
        content_type_weights: Optional earnings-based weights by type

    Returns:
        Selected caption or None if no eligible captions
    """
    # Collect all PROVEN captions across content types
    eligible: list[Caption] = []

    for pool in pools.values():
        if exclude_content_type and pool.type_name == exclude_content_type:
            continue

        for caption in pool.proven:
            if caption.caption_id not in exclude_ids:
                eligible.append(caption)

    if not eligible:
        return None

    # Calculate max earnings for normalization
    max_earnings = get_max_earnings(eligible, pool_type=POOL_PROVEN)

    # Calculate weights for all eligible captions
    type_weights = _get_content_type_weights(pools, content_type_weights, exclude_content_type)

    for caption in eligible:
        content_type_avg = pools[caption.content_type_id].get_expected_earnings()
        _calculate_weight_for_caption(caption, persona, content_type_avg, max_earnings)

        # Apply content type weight multiplier
        type_name = caption.content_type_name or "unknown"
        type_multiplier = type_weights.get(type_name, 1.0)
        caption.final_weight *= type_multiplier

    # Build selector and select
    try:
        selector = VoseAliasSelector(eligible, lambda c: c.final_weight)
        return selector.select()
    except ValueError:
        # Fallback: return highest weight caption
        return max(eligible, key=lambda c: c.final_weight)


def select_from_standard_pools(
    pools: dict[int, StratifiedPools],
    persona: dict[str, str],
    exclude_ids: set[int],
    exclude_content_type: str | None = None,
    content_type_weights: dict[str, float] | None = None,
) -> Caption | None:
    """
    Select from PROVEN + GLOBAL_EARNER pools.

    Used for standard PPV slots.

    Args:
        pools: Stratified pools by content type
        persona: Creator persona for boost calculation
        exclude_ids: Caption IDs already selected
        exclude_content_type: Content type to exclude
        content_type_weights: Optional earnings-based weights by type

    Returns:
        Selected caption or None if no eligible captions
    """
    # Collect PROVEN and GLOBAL_EARNER captions
    eligible: list[Caption] = []

    for pool in pools.values():
        if exclude_content_type and pool.type_name == exclude_content_type:
            continue

        for caption in pool.proven + pool.global_earners:
            if caption.caption_id not in exclude_ids:
                eligible.append(caption)

    if not eligible:
        return None

    # Calculate max earnings using appropriate pool type
    max_earnings = max(
        get_max_earnings([c for c in eligible if c.pool_type == POOL_PROVEN], POOL_PROVEN),
        get_max_earnings([c for c in eligible if c.pool_type == POOL_GLOBAL_EARNER], POOL_GLOBAL_EARNER),
    )
    if max_earnings <= 0:
        max_earnings = 100.0

    # Calculate weights
    type_weights = _get_content_type_weights(pools, content_type_weights, exclude_content_type)

    for caption in eligible:
        content_type_avg = pools[caption.content_type_id].get_expected_earnings()
        _calculate_weight_for_caption(caption, persona, content_type_avg, max_earnings)

        # Apply content type weight multiplier
        type_name = caption.content_type_name or "unknown"
        type_multiplier = type_weights.get(type_name, 1.0)
        caption.final_weight *= type_multiplier

    # Build selector and select
    try:
        selector = VoseAliasSelector(eligible, lambda c: c.final_weight)
        return selector.select()
    except ValueError:
        return max(eligible, key=lambda c: c.final_weight)


def select_from_discovery_pool(
    pools: dict[int, StratifiedPools],
    persona: dict[str, str],
    exclude_ids: set[int],
    exclude_content_type: str | None = None,
    prioritize_recent_imports: bool = True,
) -> Caption | None:
    """
    Select from DISCOVERY pool.

    Used for discovery slots to test new content.

    Priority order:
    1. Recent imports (imported_at within 30 days) with high global earnings
    2. External imports not yet tested
    3. High global earners untested on this creator
    4. Under-tested captions

    Args:
        pools: Stratified pools by content type
        persona: Creator persona for boost calculation
        exclude_ids: Caption IDs already selected
        exclude_content_type: Content type to exclude
        prioritize_recent_imports: Whether to boost recent imports

    Returns:
        Selected caption or None if no eligible captions
    """
    # Collect all DISCOVERY captions
    eligible: list[Caption] = []

    for pool in pools.values():
        if exclude_content_type and pool.type_name == exclude_content_type:
            continue

        for caption in pool.discovery:
            if caption.caption_id not in exclude_ids:
                eligible.append(caption)

    if not eligible:
        return None

    # Calculate cutoff date for recent imports
    recent_cutoff = (datetime.now() - timedelta(days=RECENT_IMPORT_DAYS)).isoformat()

    # Calculate max earnings for discovery bonus
    max_global_earnings = get_max_earnings(eligible, pool_type=POOL_DISCOVERY)
    if max_global_earnings <= 0:
        max_global_earnings = 100.0

    # Calculate weights with discovery-specific bonuses
    for caption in eligible:
        content_type_avg = pools[caption.content_type_id].get_expected_earnings()
        _calculate_weight_for_caption(caption, persona, content_type_avg, max_global_earnings)

        # Apply additional discovery prioritization
        if prioritize_recent_imports:
            # Bonus for recent external imports
            if caption.source == "external_import" and caption.imported_at:
                if caption.imported_at >= recent_cutoff:
                    caption.final_weight *= 1.5  # 50% boost for recent imports

            # Bonus for external imports in general
            elif caption.source == "external_import":
                caption.final_weight *= 1.2  # 20% boost for external imports

            # Bonus for high global earners
            if caption.global_avg_earnings and caption.global_avg_earnings > content_type_avg:
                caption.final_weight *= 1.3  # 30% boost for above-average global earners

    # Build selector and select
    try:
        selector = VoseAliasSelector(eligible, lambda c: c.final_weight)
        return selector.select()
    except ValueError:
        return max(eligible, key=lambda c: c.final_weight)


# =============================================================================
# MAIN SELECTION FUNCTION
# =============================================================================

def select_captions(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None,
    count: int = 10,
    min_freshness: float = 30.0,
    use_persona: bool = True,
    slot_type: str = "standard",
) -> list[Caption]:
    """
    Select captions using multi-stage pool-based selection.

    Selection varies by slot_type:
    - premium: PROVEN pool only, highest earners
    - standard: PROVEN + GLOBAL_EARNER pools
    - discovery: DISCOVERY pool with import prioritization

    Args:
        conn: Database connection
        creator_name: Creator page name (optional)
        creator_id: Creator UUID (optional)
        count: Number of captions to select
        min_freshness: Minimum freshness score
        use_persona: Whether to apply persona boost
        slot_type: 'premium', 'standard', or 'discovery'

    Returns:
        List of selected Caption objects
    """
    # Validate slot_type
    valid_slot_types = {"premium", "standard", "discovery"}
    if slot_type not in valid_slot_types:
        raise ValueError(f"Invalid slot_type: {slot_type}. Must be one of: {valid_slot_types}")

    # Resolve creator ID
    if creator_name and not creator_id:
        cursor = conn.execute(
            "SELECT creator_id FROM creators WHERE page_name = ? OR display_name = ?",
            (creator_name, creator_name)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Creator not found: {creator_name}")
        creator_id = row["creator_id"]

    if not creator_id:
        raise ValueError("Must provide creator_name or creator_id")

    # Load content type earnings for weighting
    content_type_earnings = get_content_type_earnings(conn, creator_id)

    # Get allowed content types from vault_matrix
    strategy = ContentTypeStrategy(conn, creator_id)
    allowed_types = [ct.content_type_id for ct in strategy.get_allowed_content_types()]

    # Load stratified pools
    pools = load_stratified_pools(
        conn,
        creator_id,
        allowed_content_types=allowed_types,
        min_freshness=min_freshness,
    )

    if not pools:
        return []

    # Load persona
    persona = {}
    if use_persona:
        persona = load_persona(conn, creator_id)

    # Select captions based on slot type
    selected: list[Caption] = []
    exclude_ids: set[int] = set()
    last_content_type: str | None = None

    # Map content type name to earnings weight
    content_type_weights = {
        pool.type_name: content_type_earnings.get(pool.type_name, 50.0)
        for pool in pools.values()
    }

    for _ in range(count):
        caption: Caption | None = None

        # Select based on slot type
        if slot_type == "premium":
            caption = select_from_proven_pool(
                pools=pools,
                persona=persona,
                exclude_ids=exclude_ids,
                exclude_content_type=last_content_type,
                content_type_weights=content_type_weights,
            )
            # Fallback to standard if no proven available
            if caption is None:
                caption = select_from_standard_pools(
                    pools=pools,
                    persona=persona,
                    exclude_ids=exclude_ids,
                    exclude_content_type=last_content_type,
                    content_type_weights=content_type_weights,
                )

        elif slot_type == "standard":
            caption = select_from_standard_pools(
                pools=pools,
                persona=persona,
                exclude_ids=exclude_ids,
                exclude_content_type=last_content_type,
                content_type_weights=content_type_weights,
            )
            # Fallback to discovery if no standard available
            if caption is None:
                caption = select_from_discovery_pool(
                    pools=pools,
                    persona=persona,
                    exclude_ids=exclude_ids,
                    exclude_content_type=last_content_type,
                )

        elif slot_type == "discovery":
            caption = select_from_discovery_pool(
                pools=pools,
                persona=persona,
                exclude_ids=exclude_ids,
                exclude_content_type=last_content_type,
            )
            # Fallback to global earners if discovery exhausted
            if caption is None:
                caption = select_from_standard_pools(
                    pools=pools,
                    persona=persona,
                    exclude_ids=exclude_ids,
                    exclude_content_type=last_content_type,
                    content_type_weights=content_type_weights,
                )

        if caption is None:
            # Try one more time without content type exclusion
            if slot_type == "premium":
                caption = select_from_proven_pool(pools, persona, exclude_ids)
            elif slot_type == "standard":
                caption = select_from_standard_pools(pools, persona, exclude_ids)
            else:
                caption = select_from_discovery_pool(pools, persona, exclude_ids)

        if caption is None:
            # No more eligible captions
            break

        selected.append(caption)
        exclude_ids.add(caption.caption_id)
        last_content_type = caption.content_type_name

    return selected


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def format_markdown(captions: list[Caption]) -> str:
    """Format selected captions as Markdown."""
    lines = [
        "# Selected Captions",
        "",
        f"**Total Selected:** {len(captions)}",
        "",
        "| # | ID | Pool | Type | Earnings | Fresh | Boost | Weight | Preview |",
        "|---|-----|------|------|----------|-------|-------|--------|---------|",
    ]

    for i, c in enumerate(captions, 1):
        preview = c.caption_text[:40] + "..." if len(c.caption_text) > 40 else c.caption_text
        preview = preview.replace("|", "\\|").replace("\n", " ")

        # Get effective earnings for display
        if c.pool_type == POOL_PROVEN:
            effective_earnings = c.creator_avg_earnings or 0
        elif c.pool_type == POOL_GLOBAL_EARNER:
            effective_earnings = c.global_avg_earnings or 0
        else:
            effective_earnings = c.performance_score * 0.5  # Discovery proxy

        lines.append(
            f"| {i} | {c.caption_id} | {c.pool_type[:4]} | {c.content_type_name or 'N/A'} | "
            f"${effective_earnings:.2f} | {c.freshness_score:.1f} | "
            f"{c.persona_boost:.2f}x | {c.final_weight:.1f} | {preview} |"
        )

    lines.append("")

    # Pool distribution summary
    proven_count = sum(1 for c in captions if c.pool_type == POOL_PROVEN)
    global_count = sum(1 for c in captions if c.pool_type == POOL_GLOBAL_EARNER)
    discovery_count = sum(1 for c in captions if c.pool_type == POOL_DISCOVERY)

    lines.extend([
        "## Pool Distribution",
        f"- PROVEN: {proven_count} ({100*proven_count/len(captions):.1f}%)" if captions else "- PROVEN: 0",
        f"- GLOBAL_EARNER: {global_count} ({100*global_count/len(captions):.1f}%)" if captions else "- GLOBAL_EARNER: 0",
        f"- DISCOVERY: {discovery_count} ({100*discovery_count/len(captions):.1f}%)" if captions else "- DISCOVERY: 0",
        "",
    ])

    return "\n".join(lines)


def format_json(captions: list[Caption]) -> str:
    """Format selected captions as JSON."""
    data = [
        {
            "caption_id": c.caption_id,
            "caption_text": c.caption_text,
            "caption_type": c.caption_type,
            "content_type_id": c.content_type_id,
            "content_type_name": c.content_type_name,
            "pool_type": c.pool_type,
            "performance_score": round(c.performance_score, 2),
            "freshness_score": round(c.freshness_score, 2),
            "creator_avg_earnings": round(c.creator_avg_earnings, 2) if c.creator_avg_earnings else None,
            "global_avg_earnings": round(c.global_avg_earnings, 2) if c.global_avg_earnings else None,
            "creator_times_used": c.creator_times_used,
            "global_times_used": c.global_times_used,
            "source": c.source,
            "imported_at": c.imported_at,
            "persona_boost": round(c.persona_boost, 2),
            "final_weight": round(c.final_weight, 2),
        }
        for c in captions
    ]
    return json.dumps(data, indent=2)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Select captions using pool-based weighted random selection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python select_captions.py --creator missalexa --count 10
    python select_captions.py --creator-id abc123 --count 20 --slot-type premium
    python select_captions.py --creator missalexa --count 5 --output captions.json --format json
    python select_captions.py --creator missalexa --count 3 --slot-type discovery

Pool Classification:
    PROVEN: creator_times_used >= 3 AND creator_avg_earnings > 0
    GLOBAL_EARNER: creator_times_used < 3 AND global_times_used >= 3 AND global_avg_earnings > 0
    DISCOVERY: All others (new imports, under-tested)

Weight Formula:
    Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery Bonus(10%)

Slot Types:
    premium: PROVEN pool only (highest earners for prime time)
    standard: PROVEN + GLOBAL_EARNER pools (normal PPV)
    discovery: DISCOVERY pool with import prioritization

Persona Boost:
    - Primary tone match: 1.20x
    - Emoji frequency match: 1.10x
    - Slang level match: 1.10x
    - Maximum combined: 1.40x
    - No match penalty: 0.95x
        """
    )

    parser.add_argument(
        "--creator", "-c",
        help="Creator page name (e.g., missalexa)"
    )
    parser.add_argument(
        "--creator-id",
        help="Creator UUID"
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Number of captions to select (default: 10)"
    )
    parser.add_argument(
        "--slot-type", "-s",
        choices=["premium", "standard", "discovery"],
        default="standard",
        help="Slot type: premium, standard, or discovery (default: standard)"
    )
    parser.add_argument(
        "--min-freshness",
        type=float,
        default=30.0,
        help="Minimum freshness score (default: 30)"
    )
    parser.add_argument(
        "--no-persona",
        action="store_true",
        help="Disable persona boost"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help=f"Database path (default: {DB_PATH})"
    )

    args = parser.parse_args()

    if not args.creator and not args.creator_id:
        parser.error("Must specify --creator or --creator-id")

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        captions = select_captions(
            conn,
            creator_name=args.creator,
            creator_id=args.creator_id,
            count=args.count,
            min_freshness=args.min_freshness,
            use_persona=not args.no_persona,
            slot_type=args.slot_type,
        )

        if not captions:
            print("No eligible captions found", file=sys.stderr)
            sys.exit(1)

        if args.format == "json":
            output = format_json(captions)
        else:
            output = format_markdown(captions)

        if args.output:
            Path(args.output).write_text(output)
            print(f"Captions written to {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
