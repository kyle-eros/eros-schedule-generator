#!/usr/bin/env python3
"""
Select Captions - Pool-based caption selection with hard exclusion filtering.

This script implements caption selection using two approaches:

1. **Unified Pool (Recommended, v2.2+):**
   - Hard exclusion based on mass_messages send history
   - Freshness tiers: 'never_used' (highest priority), 'fresh' (reusable)
   - Uses `load_unified_pool()` with configurable exclusion window (default 60 days)
   - Pattern-based scoring for selection weighting

2. **Stratified Pools (Legacy, deprecated):**
   - Pool classification: PROVEN, GLOBAL_EARNER, DISCOVERY
   - Uses static freshness_score field
   - Will be removed in v3.0

Unified Pool Approach (Phase 4):
    - Captions sent within exclusion_days are completely excluded
    - Never-used captions prioritized over fresh captions
    - Selection weight combines pattern score, freshness tier, and persona boost

Legacy Pool Classification:
- PROVEN: creator_times_used >= 3 AND creator_avg_earnings > 0
- GLOBAL_EARNER: creator_times_used < 3 AND global_times_used >= 3 AND global_avg_earnings > 0
- DISCOVERY: All others (new imports, under-tested, or no earnings data)

Weight Formula:
    Weight = Earnings(60%) + Freshness(15%) + Persona(15%) + Discovery Bonus(10%)

Slot Types:
- premium: PROVEN pool only (highest earners for prime time slots)
- standard: PROVEN + GLOBAL_EARNER pools (normal PPV slots)
- discovery: DISCOVERY pool with import prioritization (exploration slots)

Usage:
    # CLI (legacy mode)
    python select_captions.py --creator missalexa --count 10
    python select_captions.py --creator-id abc123 --count 20 --slot-type premium

    # Python API (unified pool, recommended)
    from select_captions import load_unified_pool, get_content_type_ids

    content_types = get_content_type_ids(conn, ['sextape', 'solo'])
    pool = load_unified_pool(conn, creator_id, content_types, exclusion_days=60)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sqlite3
import statistics
import sys
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from content_type_strategy import (
    ContentTypeStrategy,
    get_content_type_earnings,
)
from exceptions import CaptionExhaustionError
from hook_detection import HookType, detect_hook_type
from match_persona import calculate_persona_boost, get_persona_profile
from models import PatternProfile, ScoredCaption, SelectionPool
from pattern_extraction import PatternProfileCache, build_pattern_profile
from shared_context import PersonaProfile
from utils import VoseAliasSelector
from weights import (
    EXPLORATION_WEIGHT,
    PATTERN_WEIGHT,
    POOL_DISCOVERY,
    POOL_GLOBAL_EARNER,
    POOL_PROVEN,
    calculate_exploration_weight,
    calculate_fresh_weight,
    calculate_weight,
    get_max_earnings,
)

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent

from database import DB_PATH  # noqa: E402

# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

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

# Hook rotation (Phase 3 - Authenticity & Anti-Detection)
SAME_HOOK_PENALTY: float = 0.7
"""Penalty applied when caption has same hook type as previous selection (30% reduction)."""

# Hard exclusion window for unified pool (Phase 4)
DEFAULT_EXCLUSION_DAYS: int = 60
"""Default days for hard caption exclusion based on mass_messages history."""

DEFAULT_POOL_LIMIT: int = 500
"""Default maximum captions to load in unified pool."""

# =============================================================================
# SQL QUERY FOR UNIFIED POOL LOADING
# =============================================================================

FRESH_CAPTION_QUERY = """
WITH recent_use AS (
    SELECT
        mm.caption_id,
        MAX(mm.sending_time) AS last_sent,
        COUNT(*) AS times_used,
        SUM(CASE WHEN mm.earnings > 0 THEN mm.earnings ELSE 0 END) AS total_earnings_on_page
    FROM mass_messages mm
    WHERE mm.creator_id = ?
    GROUP BY mm.caption_id
)
SELECT
    cb.caption_id,
    cb.caption_text,
    cb.caption_type,
    cb.content_type_id,
    ct.type_name AS content_type_name,
    ct.type_category,
    cb.tone,
    cb.emoji_style AS hook_type,
    cb.slang_level,
    cb.performance_score,
    cb.freshness_score AS bank_freshness_score,
    cb.creator_id AS caption_creator_id,
    cb.is_universal,
    CASE
        WHEN ru.last_sent IS NULL THEN 'never_used'
        WHEN julianday('now') - julianday(ru.last_sent) > ? THEN 'fresh'
        ELSE 'excluded'
    END AS freshness_tier,
    CASE WHEN ru.last_sent IS NULL THEN 1 ELSE 0 END AS never_used_on_page,
    COALESCE(ru.times_used, 0) AS times_used_on_page,
    ru.last_sent AS last_sent_on_page,
    COALESCE(ru.total_earnings_on_page, 0.0) AS total_earnings_on_page,
    CASE
        WHEN ru.last_sent IS NOT NULL
        THEN CAST(julianday('now') - julianday(ru.last_sent) AS INTEGER)
        ELSE NULL
    END AS days_since_sent
FROM caption_bank cb
LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
LEFT JOIN recent_use ru ON cb.caption_id = ru.caption_id
WHERE
    cb.is_active = 1
    AND cb.content_type_id IN ({content_type_placeholders})
    AND (cb.creator_id = ? OR cb.is_universal = 1)
    AND (
        ru.last_sent IS NULL
        OR julianday('now') - julianday(ru.last_sent) > ?
    )
ORDER BY
    CASE freshness_tier
        WHEN 'never_used' THEN 0
        WHEN 'fresh' THEN 1
    END,
    cb.performance_score DESC,
    days_since_sent DESC NULLS FIRST
LIMIT ?
"""


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(slots=True)
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

    # Hook type for anti-detection rotation (Phase 3)
    hook_type: HookType | None = None
    """Detected hook type from caption text for rotation tracking."""

    hook_confidence: float = 0.0
    """Confidence score for hook type detection (0.0-1.0)."""


@dataclass(slots=True)
class StratifiedPools:
    """
    Captions stratified into 3 pools per content type.

    This is the canonical StratifiedPools definition. All other modules
    should import from select_captions.

    Pools:
        - proven: Captions with creator-specific earnings data
        - global_earners: Captions with global earnings but no creator data
        - discovery: Captions with no earnings data (new imports, under-tested)

    Backwards Compatibility:
        - content_type_name: Alias for type_name
        - global_earner: Property returning global_earners
        - has_proven: Property indicating if proven pool has captions
        - content_type_avg_earnings: Cached expected earnings value
    """

    content_type_id: int
    type_name: str
    proven: list[Caption] = field(default_factory=list)
    """Captions with creator_times_used >= 3 and creator_avg_earnings > 0."""

    global_earners: list[Caption] = field(default_factory=list)
    """Captions with global_times_used >= 3, untested on this creator."""

    discovery: list[Caption] = field(default_factory=list)
    """Under-tested or new imports."""

    content_type_avg_earnings: float = 50.0
    """Average earnings for this content type (for backwards compatibility)."""

    # -------------------------------------------------------------------------
    # Core Properties
    # -------------------------------------------------------------------------

    @property
    def total_count(self) -> int:
        """Total captions across all pools."""
        return len(self.proven) + len(self.global_earners) + len(self.discovery)

    @property
    def has_proven(self) -> bool:
        """Whether this content type has proven performers."""
        return len(self.proven) > 0

    # -------------------------------------------------------------------------
    # Backwards Compatibility Properties
    # -------------------------------------------------------------------------

    @property
    def content_type_name(self) -> str:
        """Alias for type_name (backwards compatibility with generate_schedule.py)."""
        return self.type_name

    @property
    def global_earner(self) -> list[Caption]:
        """Alias for global_earners (backwards compatibility with generate_schedule.py)."""
        return self.global_earners

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

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


def _legacy_persona_boost(caption: Caption, persona: dict[str, str]) -> float:
    """
    [LEGACY] Calculate persona boost factor for a caption.

    Note: This is the legacy implementation. For new code, use
    calculate_persona_boost() from match_persona module.

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


def load_other_creator_names(conn: sqlite3.Connection, exclude_page_name: str) -> set[str]:
    """
    Load all creator names except the target creator to detect cross-contamination.

    Returns a set of lowercase names that should NOT appear in captions
    for the target creator (unless it's their own name).
    """
    cursor = conn.execute(
        "SELECT page_name, display_name FROM creators WHERE is_active = 1"
    )
    names = set()
    target_lower = exclude_page_name.lower().replace("_", " ")

    for row in cursor:
        page_name = (row["page_name"] or "").lower().replace("_", " ")
        display_name = (row["display_name"] or "").lower()

        # Skip short names (< 4 chars) to avoid false positives
        if len(page_name) >= 4 and page_name != target_lower:
            names.add(page_name)
        if len(display_name) >= 4 and display_name.lower() != target_lower:
            names.add(display_name)

    # Also remove any name that's part of the target name
    target_parts = set(target_lower.split())
    names = {n for n in names if n not in target_parts}

    return names


def validate_caption_ownership(
    caption_text: str, other_creator_names: set[str]
) -> tuple[bool, str | None]:
    """
    Check if a caption references other creators (data quality issue).

    Args:
        caption_text: The caption text to validate
        other_creator_names: Set of other creator names to check against

    Returns:
        Tuple of (is_valid, detected_name_if_invalid)
    """
    text_lower = caption_text.lower()

    for name in other_creator_names:
        if name in text_lower:
            return False, name

    return True, None


def load_stratified_pools(
    conn: sqlite3.Connection,
    creator_id: str,
    allowed_content_types: list[int] | None = None,
    min_freshness: float = 30.0,
    min_uses_for_proven: int = MIN_USES_FOR_PROVEN,
    page_name: str | None = None,
) -> dict[int, StratifiedPools]:
    """
    [DEPRECATED] Load captions into stratified pools per content type.

    .. deprecated:: 2.2
        Use :func:`load_unified_pool` instead. This function is maintained
        for backward compatibility and will be removed in v3.0.

    The unified pool approach provides:
    - Hard exclusion based on actual send history (mass_messages table)
    - Simpler freshness tier assignment ('never_used' or 'fresh')
    - Pattern-based scoring instead of pool classification

    Pool Classification (Legacy):
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
        page_name: Optional page name for cross-contamination filtering

    Returns:
        Dict mapping content_type_id -> StratifiedPools

    See Also:
        load_unified_pool: The recommended replacement function.
    """
    warnings.warn(
        "load_stratified_pools() is deprecated and will be removed in v3.0. "
        "Use load_unified_pool() instead for hard exclusion-based caption loading.",
        DeprecationWarning,
        stacklevel=2,
    )
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
        creator_id,  # CTE WHERE
        min_uses_for_proven,  # CASE WHEN (PROVEN check)
        min_uses_for_proven,  # CASE WHEN (GLOBAL_EARNER check)
        MIN_USES_FOR_GLOBAL_EARNER,  # CASE WHEN (global times used)
        creator_id,  # Main WHERE creator_id
        min_freshness,  # Main WHERE freshness_score
    ]
    params.extend(allowed_content_types)  # IN clause

    cursor = conn.execute(query, params)

    # Load other creator names for cross-contamination validation
    other_creator_names: set[str] = set()
    filtered_count = 0
    if page_name:
        other_creator_names = load_other_creator_names(conn, page_name)

    # Initialize pools for each content type
    pools: dict[int, StratifiedPools] = {}
    content_type_names: dict[int, str] = {}

    for row in cursor.fetchall():
        # Validate caption doesn't reference other creators
        if page_name and other_creator_names:
            caption_text = row["caption_text"] or ""
            is_valid, detected_name = validate_caption_ownership(
                caption_text, other_creator_names
            )
            if not is_valid:
                filtered_count += 1
                continue  # Skip this caption

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
                "SELECT type_name FROM content_types WHERE content_type_id = ?", (ct_id,)
            )
            name_row = name_cursor.fetchone()
            type_name = name_row["type_name"] if name_row else "unknown"
            pools[ct_id] = StratifiedPools(
                content_type_id=ct_id,
                type_name=type_name,
            )

    # Log filtered count if any
    if filtered_count > 0:
        print(f"[INFO] Filtered {filtered_count} captions referencing other creators")

    return pools


# =============================================================================
# UNIFIED POOL LOADING (Phase 4 - Hard Exclusion)
# =============================================================================


def get_content_type_ids(
    conn: sqlite3.Connection,
    content_type_names: list[str],
) -> list[int]:
    """
    Convert content type names to IDs.

    Looks up content type IDs from the content_types table based on
    human-readable type names.

    Args:
        conn: Database connection with row_factory set to sqlite3.Row.
        content_type_names: List of type names (e.g., ['sextape', 'solo', 'b/g']).

    Returns:
        List of content_type_id integers corresponding to the provided names.
        Names that don't exist in the database are silently ignored.

    Example:
        >>> ids = get_content_type_ids(conn, ['sextape', 'solo'])
        >>> ids
        [1, 2]
    """
    if not content_type_names:
        return []

    placeholders = ",".join("?" * len(content_type_names))
    query = f"""
        SELECT content_type_id, type_name
        FROM content_types
        WHERE type_name IN ({placeholders})
    """
    cursor = conn.execute(query, content_type_names)
    rows = cursor.fetchall()

    # Return IDs in same order as input names where possible
    name_to_id = {row["type_name"]: row["content_type_id"] for row in rows}
    return [name_to_id[name] for name in content_type_names if name in name_to_id]


def log_pool_statistics(pool: SelectionPool) -> None:
    """
    Log pool statistics for debugging and monitoring.

    Outputs pool composition statistics to the logger for tracking
    caption availability and pool health.

    Args:
        pool: SelectionPool with scored captions to analyze.

    Example output:
        [INFO] Loaded 245 captions: 45 never_used, 200 fresh
        [INFO] Content types: sextape, solo, b/g
    """
    logger.info(
        f"Loaded {len(pool.captions)} captions: "
        f"{pool.never_used_count} never_used, {pool.fresh_count} fresh"
    )
    if pool.content_types:
        logger.info(f"Content types: {', '.join(pool.content_types)}")


def load_unified_pool(
    conn: sqlite3.Connection,
    creator_id: str,
    content_types: list[int],
    exclusion_days: int = DEFAULT_EXCLUSION_DAYS,
    limit: int = DEFAULT_POOL_LIMIT,
) -> SelectionPool:
    """
    Load caption pool with hard exclusion filtering based on mass_messages history.

    This function implements the unified pool approach where freshness is determined
    by actual send history rather than static freshness scores. Captions sent within
    the exclusion window are completely excluded from the pool.

    Replaces load_stratified_pools() with a unified approach:
    - Hard exclude captions used within exclusion_days (based on mass_messages)
    - Assign freshness_tier to each caption ('never_used' or 'fresh')
    - Return SelectionPool with scored captions ready for weighted selection

    Args:
        conn: Database connection with row_factory set to sqlite3.Row.
        creator_id: Creator page UUID from the creators table.
        content_types: List of content_type_ids to include in the pool.
            Use get_content_type_ids() to convert names to IDs.
        exclusion_days: Days for hard exclusion window (default 60).
            Captions sent within this window are excluded entirely.
        limit: Maximum captions to load (default 500).
            Captions are ordered by priority before limiting.

    Returns:
        SelectionPool: Unified pool with freshness tiers assigned and
        metadata populated. The captions are ordered with never_used first,
        then fresh, sorted by performance_score within each tier.

    Raises:
        CaptionExhaustionError: If no fresh captions are available after
            applying the exclusion filter. Contains creator_id, available
            count (0), and required count.

    Example:
        >>> pool = load_unified_pool(
        ...     conn,
        ...     creator_id="abc123",
        ...     content_types=[1, 2, 3],
        ...     exclusion_days=60
        ... )
        >>> len(pool.captions)
        245
        >>> pool.never_used_count
        45

    Note:
        The exclusion is based on the mass_messages table, not the static
        freshness_score field in caption_bank. This provides more accurate
        freshness tracking based on actual send history.
    """
    if not content_types:
        raise CaptionExhaustionError(
            creator_id=creator_id,
            available=0,
            required=1,
            content_type="(no content types specified)",
        )

    # Build query with content type placeholders
    placeholders = ",".join("?" * len(content_types))
    query = FRESH_CAPTION_QUERY.format(content_type_placeholders=placeholders)

    # Parameter order matches the query:
    # 1. creator_id for CTE WHERE clause
    # 2. exclusion_days for first CASE WHEN (freshness_tier)
    # 3. content_types for IN clause (expanded)
    # 4. creator_id for main WHERE clause
    # 5. exclusion_days for main WHERE clause filter
    # 6. limit for LIMIT clause
    params: list[Any] = [
        creator_id,  # CTE WHERE mm.creator_id = ?
        exclusion_days,  # CASE WHEN freshness_tier
    ]
    params.extend(content_types)  # IN clause
    params.extend([
        creator_id,  # WHERE (cb.creator_id = ? OR ...)
        exclusion_days,  # WHERE ... julianday > ?
        limit,  # LIMIT ?
    ])

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        raise CaptionExhaustionError(
            creator_id=creator_id,
            available=0,
            required=1,
            content_type=f"content_types={content_types}",
        )

    # Convert to ScoredCaption objects
    captions: list[ScoredCaption] = []
    never_used_count = 0
    fresh_count = 0
    content_type_names_seen: set[str] = set()

    for row in rows:
        freshness_tier = row["freshness_tier"]
        content_type_name = row["content_type_name"] or "unknown"
        content_type_names_seen.add(content_type_name)

        # Parse last_used_date if present
        last_used_date = None
        if row["last_sent_on_page"]:
            try:
                # Handle various date formats from SQLite
                date_str = row["last_sent_on_page"]
                if isinstance(date_str, str):
                    # Try ISO format first, then other common formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
                        try:
                            last_used_date = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
            except (ValueError, TypeError):
                pass

        caption = ScoredCaption(
            caption_id=row["caption_id"],
            caption_text=row["caption_text"],
            caption_type=row["caption_type"] or "ppv",
            content_type_id=row["content_type_id"],
            content_type_name=content_type_name,
            tone=row["tone"],
            hook_type=row["hook_type"],
            freshness_score=row["bank_freshness_score"] or 100.0,
            times_used_on_page=row["times_used_on_page"] or 0,
            last_used_date=last_used_date,
            pattern_score=0.0,  # Will be calculated during selection
            freshness_tier=freshness_tier,
            never_used_on_page=bool(row["never_used_on_page"]),
            selection_weight=0.0,  # Will be calculated during selection
        )
        captions.append(caption)

        if freshness_tier == "never_used":
            never_used_count += 1
        elif freshness_tier == "fresh":
            fresh_count += 1

    pool = SelectionPool(
        captions=captions,
        never_used_count=never_used_count,
        fresh_count=fresh_count,
        total_weight=0.0,  # Will be calculated during selection
        creator_id=creator_id,
        content_types=sorted(content_type_names_seen),
    )

    # Log statistics for monitoring
    log_pool_statistics(pool)

    return pool


# =============================================================================
# UNIFIED POOL SELECTION FUNCTIONS (Phase 4B - Fresh Selection Algorithm)
# =============================================================================


def calculate_persona_match(
    caption: ScoredCaption,
    persona: PersonaProfile | None,
) -> float:
    """
    Calculate persona match score (0-100) for a caption.

    Converts the persona boost multiplier (0.95-1.40) to a 0-100 scale
    for use in the weight calculation formula.

    Args:
        caption: ScoredCaption with tone attribute for matching.
        persona: PersonaProfile for the creator, or None if not available.

    Returns:
        Persona match score (0-100). Returns 50.0 (neutral) if no persona provided.

    Conversion:
        - 0.95x boost (no match penalty) -> ~0 score
        - 1.0x boost (neutral) -> ~11 score
        - 1.20x boost (primary tone match) -> ~56 score
        - 1.40x boost (max combined) -> 100 score
    """
    if persona is None:
        return 50.0  # Neutral score when no persona available

    # Use calculate_persona_boost from match_persona module
    match_result = calculate_persona_boost(
        caption_tone=caption.tone,
        caption_emoji_style=caption.hook_type,  # hook_type is loaded from emoji_style
        caption_slang_level=None,  # Not stored on ScoredCaption
        persona=persona,
        caption_text=caption.caption_text,
        use_text_detection=True,
    )

    # Convert boost (0.95-1.40) to score (0-100)
    # Formula: (boost - 0.95) / (1.40 - 0.95) * 100
    boost = match_result.total_boost
    score = ((boost - 0.95) / (1.40 - 0.95)) * 100
    return max(0.0, min(100.0, score))


def select_from_unified_pool(
    pool: SelectionPool,
    pattern_profile: PatternProfile,
    persona: PersonaProfile | None,
    exclude_ids: set[int],
    count: int = 1,
) -> list[ScoredCaption]:
    """
    Select captions from unified pool using new weight formula.

    Selection process:
    1. Filter out excluded caption IDs
    2. Calculate pattern scores for all captions
    3. Apply freshness tier multipliers
    4. Calculate persona scores
    5. Use Vose Alias weighted selection

    The weight formula prioritizes fresh content guided by historical patterns:
        PatternMatch(40%) + NeverUsedBonus(25%) + Persona(15%) +
        FreshnessBonus(10%) + Exploration(10%)

    Args:
        pool: SelectionPool from load_unified_pool().
        pattern_profile: PatternProfile for this creator (from pattern_extraction).
        persona: PersonaProfile for persona matching (optional).
        exclude_ids: Set of caption_ids to exclude (already used in schedule).
        count: Number of captions to select.

    Returns:
        List of selected ScoredCaption objects with calculated selection_weight.

    Raises:
        CaptionExhaustionError: If no available captions after exclusion filtering.

    Example:
        >>> pool = load_unified_pool(conn, creator_id, content_types)
        >>> profile = build_pattern_profile(conn, creator_id)
        >>> selected = select_from_unified_pool(pool, profile, persona, exclude_ids, count=5)
        >>> for caption in selected:
        ...     print(f"{caption.caption_id}: {caption.selection_weight:.1f}")
    """
    # Filter out excluded IDs
    available = [c for c in pool.captions if c.caption_id not in exclude_ids]

    if not available:
        raise CaptionExhaustionError(
            creator_id=pool.creator_id,
            available=0,
            required=count,
            content_type="(all content types after exclusion)",
        )

    # Build schedule context for exploration scoring
    schedule_context: dict[str, Any] = {
        "used_hook_types": set(),
        "used_tones": set(),
        "content_type_counts": {},
        "target_content_distribution": {},
    }

    # Score all captions
    scored_captions: list[ScoredCaption] = []

    for caption in available:
        # Calculate persona score
        persona_score = calculate_persona_match(caption, persona)

        # Calculate fresh weight using the new formula
        weight, breakdown = calculate_fresh_weight(
            caption={
                "caption_id": caption.caption_id,
                "content_type_name": caption.content_type_name,
                "tone": caption.tone,
                "hook_type": caption.hook_type,
                "freshness_score": caption.freshness_score,
                "freshness_tier": caption.freshness_tier,
                "times_used_on_page": caption.times_used_on_page,
                "pattern_score": caption.pattern_score,
            },
            pattern_profile=pattern_profile,
            persona_score=persona_score,
            schedule_context=schedule_context,
            creator_id=pool.creator_id,
        )

        # Calculate pattern score from breakdown
        pattern_score_value = breakdown.get("raw_pattern_score", 30.0)

        # Create new ScoredCaption with calculated scores
        # Note: ScoredCaption is frozen=True, so we need to create a new instance
        scored = ScoredCaption(
            caption_id=caption.caption_id,
            caption_text=caption.caption_text,
            caption_type=caption.caption_type,
            content_type_id=caption.content_type_id,
            content_type_name=caption.content_type_name,
            tone=caption.tone,
            hook_type=caption.hook_type,
            freshness_score=caption.freshness_score,
            times_used_on_page=caption.times_used_on_page,
            last_used_date=caption.last_used_date,
            pattern_score=pattern_score_value,
            freshness_tier=caption.freshness_tier,
            never_used_on_page=caption.never_used_on_page,
            selection_weight=weight,
        )
        scored_captions.append(scored)

    # Normalize weights for probability calculation
    total_weight = sum(c.selection_weight for c in scored_captions)
    if total_weight == 0:
        # Equal probability if all weights are 0
        probabilities = [1.0 / len(scored_captions)] * len(scored_captions)
    else:
        probabilities = [c.selection_weight / total_weight for c in scored_captions]

    # Use Vose Alias for efficient O(1) selection
    try:
        selector = VoseAliasSelector(scored_captions, lambda c: c.selection_weight)
        selected = selector.select_multiple(count, allow_duplicates=False)
    except ValueError:
        # Fallback to random.choices if VoseAliasSelector fails
        logger.warning("VoseAliasSelector failed, falling back to random.choices")
        selected = random.choices(scored_captions, weights=probabilities, k=min(count, len(scored_captions)))
        # Remove duplicates while preserving order
        seen_ids: set[int] = set()
        unique_selected: list[ScoredCaption] = []
        for s in selected:
            if s.caption_id not in seen_ids:
                unique_selected.append(s)
                seen_ids.add(s.caption_id)
        selected = unique_selected

    logger.debug(
        f"Selected {len(selected)} captions from pool of {len(available)} "
        f"(total_weight={total_weight:.1f})"
    )

    return selected


def select_exploration_caption(
    pool: SelectionPool,
    pattern_profile: PatternProfile,
    schedule_context: dict[str, Any],
    exclude_ids: set[int],
) -> ScoredCaption | None:
    """
    Select a caption for exploration slots (10-15% of schedule).

    Prioritizes captions that promote schedule diversity:
    - Captions with low pattern scores (< 30) - testing new patterns
    - Never-used captions on this page
    - Diverse attributes (unused hook_type, tone, content_type)

    Exploration slots help discover new high-performing patterns and
    prevent over-reliance on historically successful content.

    Args:
        pool: SelectionPool from load_unified_pool().
        pattern_profile: PatternProfile for pattern scoring.
        schedule_context: Current schedule state with used attributes:
            - used_hook_types: set[str] - Hook types already in schedule
            - used_tones: set[str] - Tones already in schedule
            - content_type_counts: dict[str, int] - Count per content type
            - target_content_distribution: dict[str, int] - Target counts
        exclude_ids: Already used caption IDs.

    Returns:
        ScoredCaption selected for exploration, or None if no candidates.

    Example:
        >>> context = {
        ...     "used_hook_types": {"question", "urgency"},
        ...     "used_tones": {"playful"},
        ...     "content_type_counts": {"sextape": 5},
        ...     "target_content_distribution": {"sextape": 5, "solo": 3}
        ... }
        >>> caption = select_exploration_caption(pool, profile, context, exclude_ids)
    """
    # Minimum exploration score threshold for consideration
    EXPLORATION_THRESHOLD = 20.0

    # Filter to exploration candidates
    candidates: list[tuple[ScoredCaption, float]] = []

    for caption in pool.captions:
        if caption.caption_id in exclude_ids:
            continue

        # Calculate exploration weight
        exploration_score = calculate_exploration_weight(
            caption={
                "content_type_name": caption.content_type_name,
                "tone": caption.tone,
                "hook_type": caption.hook_type,
                "pattern_score": caption.pattern_score,
            },
            schedule_context=schedule_context,
        )

        # Boost for never-used captions
        if caption.never_used_on_page:
            exploration_score *= 1.5

        # Boost for low pattern scores (encourages testing new patterns)
        if caption.pattern_score < 30:
            exploration_score += 15.0

        if exploration_score > EXPLORATION_THRESHOLD:
            candidates.append((caption, exploration_score))

    if not candidates:
        logger.debug("No exploration candidates above threshold")
        return None

    # Weighted selection favoring high exploration scores
    total = sum(score for _, score in candidates)
    if total <= 0:
        # Uniform selection if scores sum to 0
        return random.choice([c for c, _ in candidates])

    # Use weighted random selection
    r = random.random() * total
    cumulative = 0.0
    for caption, score in candidates:
        cumulative += score
        if r <= cumulative:
            logger.debug(
                f"Selected exploration caption {caption.caption_id} "
                f"(exploration_score={score:.1f})"
            )
            return caption

    # Fallback to last candidate
    return candidates[-1][0]


def select_captions_fresh(
    conn: sqlite3.Connection,
    creator_id: str,
    content_types: list[int],
    slot_count: int,
    persona: PersonaProfile | None = None,
    exploration_ratio: float = 0.15,
    exclusion_days: int = DEFAULT_EXCLUSION_DAYS,
    pattern_cache: PatternProfileCache | None = None,
) -> list[tuple[ScoredCaption, bool]]:
    """
    Main caption selection using fresh-focused algorithm.

    This is the primary entry point for the new selection algorithm.
    It combines pattern-based scoring with freshness prioritization
    and exploration slots.

    Process:
    1. Load unified pool with exclusion filter
    2. Load/cache pattern profile for the creator
    3. Reserve 10-15% slots for exploration (diversity)
    4. Select captions for standard slots (high pattern scores)
    5. Select captions for exploration slots (diversity focus)
    6. Return captions with exploration flag

    Args:
        conn: Database connection with row_factory set.
        creator_id: Creator page UUID.
        content_types: List of content_type_ids to include.
        slot_count: Total number of captions needed.
        persona: Optional PersonaProfile for persona matching.
        exploration_ratio: Fraction of slots for exploration (default 0.15).
        exclusion_days: Days for hard exclusion (default 60).
        pattern_cache: Optional PatternProfileCache for reuse.

    Returns:
        List of tuples: (ScoredCaption, is_exploration_slot).
        The is_exploration_slot boolean indicates if the caption was
        selected via the exploration algorithm.

    Raises:
        CaptionExhaustionError: If insufficient captions available.

    Example:
        >>> content_types = get_content_type_ids(conn, ['sextape', 'solo'])
        >>> results = select_captions_fresh(
        ...     conn, creator_id, content_types, slot_count=28,
        ...     persona=persona, exploration_ratio=0.15
        ... )
        >>> for caption, is_exploration in results:
        ...     slot_type = "exploration" if is_exploration else "standard"
        ...     print(f"{caption.caption_id}: {slot_type}")
    """
    # Load pool
    pool = load_unified_pool(conn, creator_id, content_types, exclusion_days)

    # Get or build pattern profile
    if pattern_cache is not None:
        profile = pattern_cache.get(creator_id)
        if profile is None:
            profile = build_pattern_profile(conn, creator_id)
            pattern_cache.set(creator_id, profile)
    else:
        profile = build_pattern_profile(conn, creator_id)

    # Calculate exploration slot count
    num_exploration = int(slot_count * exploration_ratio)
    num_standard = slot_count - num_exploration

    # Determine which slot indices are exploration slots
    exploration_indices = set(random.sample(range(slot_count), num_exploration)) if num_exploration > 0 else set()

    # Track used captions and attributes
    exclude_ids: set[int] = set()
    schedule_context: dict[str, Any] = {
        "used_hook_types": set(),
        "used_tones": set(),
        "content_type_counts": {},
        "target_content_distribution": {},
    }

    result_captions: list[tuple[ScoredCaption, bool]] = []

    for i in range(slot_count):
        caption: ScoredCaption | None = None
        is_exploration = i in exploration_indices

        if is_exploration:
            # Exploration slot - prioritize diversity
            caption = select_exploration_caption(
                pool, profile, schedule_context, exclude_ids
            )
            if caption is None:
                # Fall back to standard selection
                selected = select_from_unified_pool(
                    pool, profile, persona, exclude_ids, count=1
                )
                caption = selected[0] if selected else None
                is_exploration = False  # Mark as non-exploration if fallback used
        else:
            # Standard slot - use pattern-guided selection
            selected = select_from_unified_pool(
                pool, profile, persona, exclude_ids, count=1
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

            result_captions.append((caption, is_exploration))
        else:
            # No caption available - log warning
            logger.warning(
                f"No caption available for slot {i} "
                f"(exclude_ids={len(exclude_ids)}, pool_size={len(pool.captions)})"
            )

    logger.info(
        f"Selected {len(result_captions)} captions: "
        f"{sum(1 for _, exp in result_captions if exp)} exploration, "
        f"{sum(1 for _, exp in result_captions if not exp)} standard"
    )

    return result_captions


def vose_alias_select(
    items: list[ScoredCaption],
    probabilities: list[float],
    count: int,
) -> list[ScoredCaption]:
    """
    Weighted random selection using Vose's Alias Method.

    Efficient O(1) selection after O(n) setup. Falls back to random.choices
    if VoseAliasSelector fails.

    Args:
        items: List of ScoredCaption objects to select from.
        probabilities: Probability weights for each item (must sum to ~1.0).
        count: Number of items to select.

    Returns:
        List of selected ScoredCaption objects (no duplicates).

    Note:
        This is a convenience wrapper around VoseAliasSelector.select_multiple().
        For repeated selections from the same distribution, prefer creating
        a VoseAliasSelector directly.
    """
    if not items:
        return []

    try:
        # Use weights instead of probabilities for VoseAliasSelector
        selector = VoseAliasSelector(items, lambda c: c.selection_weight)
        return selector.select_multiple(count, allow_duplicates=False)
    except ValueError:
        # Fallback to random.choices
        selected = random.choices(items, weights=probabilities, k=min(count, len(items)))
        # Remove duplicates
        seen: set[int] = set()
        unique: list[ScoredCaption] = []
        for s in selected:
            if s.caption_id not in seen:
                unique.append(s)
                seen.add(s.caption_id)
        return unique


def get_or_load_persona(
    conn: sqlite3.Connection,
    creator_id: str,
) -> PersonaProfile | None:
    """
    Load PersonaProfile for a creator, handling missing data gracefully.

    Args:
        conn: Database connection.
        creator_id: Creator UUID.

    Returns:
        PersonaProfile or None if not found.

    Example:
        >>> persona = get_or_load_persona(conn, creator_id)
        >>> if persona:
        ...     print(f"Persona tone: {persona.primary_tone}")
    """
    try:
        return get_persona_profile(conn, creator_id=creator_id)
    except Exception as e:
        logger.warning(f"Failed to load persona for {creator_id}: {e}")
        return None


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
            pool.type_name: 1.0 for pool in pools.values() if pool.type_name != exclude_content_type
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
    persona_boost = _legacy_persona_boost(caption, persona)
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
    last_hook_type: HookType | None = None,
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
        last_hook_type: Hook type of previously selected caption (for rotation penalty)

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

        # Detect hook type and apply penalty if same as previous (Phase 3)
        hook_type, hook_confidence = detect_hook_type(caption.caption_text)
        caption.hook_type = hook_type
        caption.hook_confidence = hook_confidence

        if last_hook_type is not None and hook_type == last_hook_type:
            # Apply 0.7x penalty for same consecutive hook type
            caption.final_weight *= SAME_HOOK_PENALTY

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
    last_hook_type: HookType | None = None,
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
        last_hook_type: Hook type of previously selected caption (for rotation penalty)

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
        get_max_earnings(
            [c for c in eligible if c.pool_type == POOL_GLOBAL_EARNER], POOL_GLOBAL_EARNER
        ),
    )
    if max_earnings <= 0:
        max_earnings = 100.0

    # Calculate weights
    type_weights = _get_content_type_weights(pools, content_type_weights, exclude_content_type)

    for caption in eligible:
        content_type_avg = pools[caption.content_type_id].get_expected_earnings()
        _calculate_weight_for_caption(caption, persona, content_type_avg, max_earnings)

        # Detect hook type and apply penalty if same as previous (Phase 3)
        hook_type, hook_confidence = detect_hook_type(caption.caption_text)
        caption.hook_type = hook_type
        caption.hook_confidence = hook_confidence

        if last_hook_type is not None and hook_type == last_hook_type:
            # Apply 0.7x penalty for same consecutive hook type
            caption.final_weight *= SAME_HOOK_PENALTY

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
    last_hook_type: HookType | None = None,
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
        last_hook_type: Hook type of previously selected caption (for rotation penalty)

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

        # Detect hook type and apply penalty if same as previous (Phase 3)
        hook_type, hook_confidence = detect_hook_type(caption.caption_text)
        caption.hook_type = hook_type
        caption.hook_confidence = hook_confidence

        if last_hook_type is not None and hook_type == last_hook_type:
            # Apply 0.7x penalty for same consecutive hook type
            caption.final_weight *= SAME_HOOK_PENALTY

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

    Raises:
        ValueError: If slot_type is invalid, or if creator is not found,
            or if neither creator_name nor creator_id is provided.
    """
    # Validate slot_type
    valid_slot_types = {"premium", "standard", "discovery"}
    if slot_type not in valid_slot_types:
        raise ValueError(f"Invalid slot_type: {slot_type}. Must be one of: {valid_slot_types}")

    # Resolve creator ID
    if creator_name and not creator_id:
        cursor = conn.execute(
            "SELECT creator_id FROM creators WHERE page_name = ? OR display_name = ?",
            (creator_name, creator_name),
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
    last_hook_type: HookType | None = None  # Track for hook rotation penalty

    # Map content type name to earnings weight
    content_type_weights = {
        pool.type_name: content_type_earnings.get(pool.type_name, 50.0) for pool in pools.values()
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
                last_hook_type=last_hook_type,
            )
            # Fallback to standard if no proven available
            if caption is None:
                caption = select_from_standard_pools(
                    pools=pools,
                    persona=persona,
                    exclude_ids=exclude_ids,
                    exclude_content_type=last_content_type,
                    content_type_weights=content_type_weights,
                    last_hook_type=last_hook_type,
                )

        elif slot_type == "standard":
            caption = select_from_standard_pools(
                pools=pools,
                persona=persona,
                exclude_ids=exclude_ids,
                exclude_content_type=last_content_type,
                content_type_weights=content_type_weights,
                last_hook_type=last_hook_type,
            )
            # Fallback to discovery if no standard available
            if caption is None:
                caption = select_from_discovery_pool(
                    pools=pools,
                    persona=persona,
                    exclude_ids=exclude_ids,
                    exclude_content_type=last_content_type,
                    last_hook_type=last_hook_type,
                )

        elif slot_type == "discovery":
            caption = select_from_discovery_pool(
                pools=pools,
                persona=persona,
                exclude_ids=exclude_ids,
                exclude_content_type=last_content_type,
                last_hook_type=last_hook_type,
            )
            # Fallback to global earners if discovery exhausted
            if caption is None:
                caption = select_from_standard_pools(
                    pools=pools,
                    persona=persona,
                    exclude_ids=exclude_ids,
                    exclude_content_type=last_content_type,
                    content_type_weights=content_type_weights,
                    last_hook_type=last_hook_type,
                )

        if caption is None:
            # Try one more time without content type exclusion
            if slot_type == "premium":
                caption = select_from_proven_pool(
                    pools, persona, exclude_ids, last_hook_type=last_hook_type
                )
            elif slot_type == "standard":
                caption = select_from_standard_pools(
                    pools, persona, exclude_ids, last_hook_type=last_hook_type
                )
            else:
                caption = select_from_discovery_pool(
                    pools, persona, exclude_ids, last_hook_type=last_hook_type
                )

        if caption is None:
            # No more eligible captions
            break

        selected.append(caption)
        exclude_ids.add(caption.caption_id)
        last_content_type = caption.content_type_name
        last_hook_type = caption.hook_type  # Update for next iteration

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
        "| # | ID | Pool | Type | Hook | Earnings | Fresh | Boost | Weight | Preview |",
        "|---|-----|------|------|------|----------|-------|-------|--------|---------|",
    ]

    for i, c in enumerate(captions, 1):
        preview = c.caption_text[:35] + "..." if len(c.caption_text) > 35 else c.caption_text
        preview = preview.replace("|", "\\|").replace("\n", " ")

        # Get effective earnings for display
        if c.pool_type == POOL_PROVEN:
            effective_earnings = c.creator_avg_earnings or 0
        elif c.pool_type == POOL_GLOBAL_EARNER:
            effective_earnings = c.global_avg_earnings or 0
        else:
            effective_earnings = c.performance_score * 0.5  # Discovery proxy

        # Get hook type abbreviation
        hook_abbr = c.hook_type.value[:4] if c.hook_type else "N/A"

        lines.append(
            f"| {i} | {c.caption_id} | {c.pool_type[:4]} | {c.content_type_name or 'N/A'} | "
            f"{hook_abbr} | ${effective_earnings:.2f} | {c.freshness_score:.1f} | "
            f"{c.persona_boost:.2f}x | {c.final_weight:.1f} | {preview} |"
        )

    lines.append("")

    # Pool distribution summary
    proven_count = sum(1 for c in captions if c.pool_type == POOL_PROVEN)
    global_count = sum(1 for c in captions if c.pool_type == POOL_GLOBAL_EARNER)
    discovery_count = sum(1 for c in captions if c.pool_type == POOL_DISCOVERY)

    lines.extend(
        [
            "## Pool Distribution",
            f"- PROVEN: {proven_count} ({100 * proven_count / len(captions):.1f}%)"
            if captions
            else "- PROVEN: 0",
            f"- GLOBAL_EARNER: {global_count} ({100 * global_count / len(captions):.1f}%)"
            if captions
            else "- GLOBAL_EARNER: 0",
            f"- DISCOVERY: {discovery_count} ({100 * discovery_count / len(captions):.1f}%)"
            if captions
            else "- DISCOVERY: 0",
            "",
        ]
    )

    # Hook type distribution (Phase 3)
    if captions:
        hook_counts: dict[str, int] = {}
        for c in captions:
            hook_name = c.hook_type.value if c.hook_type else "unknown"
            hook_counts[hook_name] = hook_counts.get(hook_name, 0) + 1

        lines.extend(
            [
                "## Hook Type Distribution",
            ]
        )
        for hook_name, count in sorted(hook_counts.items(), key=lambda x: -x[1]):
            pct = 100 * count / len(captions)
            lines.append(f"- {hook_name}: {count} ({pct:.1f}%)")
        lines.append("")

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
            "creator_avg_earnings": round(c.creator_avg_earnings, 2)
            if c.creator_avg_earnings
            else None,
            "global_avg_earnings": round(c.global_avg_earnings, 2)
            if c.global_avg_earnings
            else None,
            "creator_times_used": c.creator_times_used,
            "global_times_used": c.global_times_used,
            "source": c.source,
            "imported_at": c.imported_at,
            "persona_boost": round(c.persona_boost, 2),
            "final_weight": round(c.final_weight, 2),
            # Hook type fields (Phase 3)
            "hook_type": c.hook_type.value if c.hook_type else None,
            "hook_confidence": round(c.hook_confidence, 2),
        }
        for c in captions
    ]
    return json.dumps(data, indent=2)


# =============================================================================
# CONTENT ASSIGNER ENGINE
# =============================================================================


class ContentAssigner:
    """
    Unified content assignment engine for all 20+ content types.

    This class provides centralized content assignment across all schedulable
    content types, handling:
    - Pool loading for all content types
    - Weighted selection using Vose Alias Method
    - Cross-content-type deduplication
    - Content rotation enforcement
    - Placeholder generation for empty pools

    Weight Formula:
        Weight = Performance(60%) + Freshness(15%) + Persona(15%) + Discovery(10%)

    Example:
        >>> assigner = ContentAssigner(conn, creator_id, "paid", persona)
        >>> assigner.load_all_pools()
        >>> for slot in slots:
        ...     content = assigner.assign_content_to_slot(slot)
        ...     if content:
        ...         slot.update(content)
        >>> stats = assigner.get_assignment_stats()
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        creator_id: str,
        page_type: str,
        persona: dict[str, str],
        min_freshness: float = 30.0,
    ) -> None:
        """
        Initialize the ContentAssigner.

        Args:
            conn: SQLite database connection with row_factory set
            creator_id: Creator UUID
            page_type: Page type ("paid" or "free")
            persona: Creator persona dict with primary_tone, emoji_frequency, slang_level
            min_freshness: Minimum freshness score for caption selection
        """
        self.conn = conn
        self.creator_id = creator_id
        self.page_type = page_type
        self.persona = persona
        self.min_freshness = min_freshness

        # Content pools by type
        self._content_pools: dict[str, list[dict[str, Any]]] = {}
        self._caption_pools: dict[int, StratifiedPools] = {}

        # Tracking for deduplication and stats
        self._used_content_ids: set[int] = set()
        self._content_type_counts: dict[str, int] = defaultdict(int)
        self._recent_content_types: list[str] = []

        # Load PPV captions into stratified pools
        self._load_caption_pools()

    def _load_caption_pools(self) -> None:
        """Pre-load stratified caption pools for PPV content types."""
        strategy = ContentTypeStrategy(self.conn, self.creator_id)
        allowed_types = [ct.content_type_id for ct in strategy.get_allowed_content_types()]

        if allowed_types:
            self._caption_pools = load_stratified_pools(
                self.conn,
                self.creator_id,
                allowed_content_types=allowed_types,
                min_freshness=self.min_freshness,
            )

    def load_all_pools(self) -> None:
        """
        Pre-load content pools for all valid content types.

        Loads content from the database for each content type valid for
        the current page type. Uses specialized loaders from content_type_loaders.
        """
        from content_type_loaders import load_content_by_type
        from content_type_registry import REGISTRY

        valid_types = REGISTRY.get_types_for_page(self.page_type)

        for content_type in valid_types:
            type_id = content_type.type_id

            # Skip ppv and ppv_follow_up - these use stratified pools
            if type_id in ("ppv", "ppv_follow_up"):
                continue

            pool = load_content_by_type(
                self.conn,
                self.creator_id,
                type_id,
                self.page_type,
                self.persona,
            )
            self._content_pools[type_id] = pool

        logger.info(
            f"ContentAssigner loaded {len(self._content_pools)} content pools "
            f"+ {len(self._caption_pools)} caption pools for {self.page_type} page"
        )

    def assign_content_to_slot(self, slot: dict[str, Any]) -> dict[str, Any] | None:
        """
        Assign appropriate content to a slot, avoiding duplicates.

        Args:
            slot: Slot dictionary with at minimum 'content_type' key

        Returns:
            Content dictionary merged with slot info, or None if assignment failed
        """
        content_type = slot.get("content_type", "ppv")

        # Handle PPV content types via stratified pools
        if content_type in ("ppv", "ppv_follow_up"):
            return self._assign_ppv_content(slot)

        # Get content pool for this type
        pool = self._content_pools.get(content_type, [])

        # Filter out already-used content
        available = [
            c for c in pool
            if c.get("content_id") is None or c.get("content_id") not in self._used_content_ids
        ]

        if not available:
            # Return placeholder if pool exhausted
            return self._create_placeholder(content_type, slot)

        # Weight-based selection
        selected = self._weighted_select(available)

        if selected:
            content_id = selected.get("content_id")
            if content_id is not None:
                self._used_content_ids.add(content_id)

            self._content_type_counts[content_type] += 1
            self._update_recent_types(content_type)

            # Merge slot data with content data
            return {**slot, **selected}

        return self._create_placeholder(content_type, slot)

    def _assign_ppv_content(self, slot: dict[str, Any]) -> dict[str, Any] | None:
        """
        Assign PPV content using stratified pools.

        Uses existing pool-based selection logic for PPV slots.

        Args:
            slot: Slot dictionary with type and timing info

        Returns:
            Content dictionary with caption data, or placeholder
        """
        if not self._caption_pools:
            return self._create_placeholder("ppv", slot)

        # Determine slot tier based on hour
        hour = slot.get("hour", 12)
        if hour in (18, 21):
            slot_tier = "premium"
        else:
            slot_tier = "standard"

        # Get previous content type for rotation
        previous_type = self._recent_content_types[-1] if self._recent_content_types else None

        # Try to select from appropriate pool
        selected_caption: Caption | None = None

        if slot_tier == "premium":
            selected_caption = select_from_proven_pool(
                pools=self._caption_pools,
                persona=self.persona,
                exclude_ids=self._used_content_ids,
                exclude_content_type=previous_type,
            )
            if selected_caption is None:
                selected_caption = select_from_standard_pools(
                    pools=self._caption_pools,
                    persona=self.persona,
                    exclude_ids=self._used_content_ids,
                    exclude_content_type=previous_type,
                )
        else:
            selected_caption = select_from_standard_pools(
                pools=self._caption_pools,
                persona=self.persona,
                exclude_ids=self._used_content_ids,
                exclude_content_type=previous_type,
            )
            if selected_caption is None:
                selected_caption = select_from_discovery_pool(
                    pools=self._caption_pools,
                    persona=self.persona,
                    exclude_ids=self._used_content_ids,
                    exclude_content_type=previous_type,
                )

        if selected_caption:
            self._used_content_ids.add(selected_caption.caption_id)
            self._content_type_counts["ppv"] += 1
            content_type_name = selected_caption.content_type_name or "ppv"
            self._update_recent_types(content_type_name)

            return {
                **slot,
                "content_id": selected_caption.caption_id,
                "content_text": selected_caption.caption_text,
                "content_type": selected_caption.content_type_name or "ppv",
                "content_type_id": selected_caption.content_type_id,
                "has_caption": True,
                "freshness_score": selected_caption.freshness_score,
                "performance_score": selected_caption.performance_score,
                "persona_boost": selected_caption.persona_boost,
                "pool_type": selected_caption.pool_type,
            }

        return self._create_placeholder("ppv", slot)

    def _weighted_select(self, pool: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        Select content using weighted random selection.

        Uses cumulative weight selection for efficiency. For very large
        pools, Vose Alias Method would be more efficient.

        Args:
            pool: List of content dictionaries

        Returns:
            Selected content dictionary, or None if pool is empty
        """
        if not pool:
            return None
        if len(pool) == 1:
            return pool[0]

        # Calculate weights for all items
        weights: list[float] = []
        for item in pool:
            weight = self._calculate_weight(item)
            weights.append(weight)

        # Normalize and select using cumulative weights
        total = sum(weights)
        if total <= 0:
            return random.choice(pool)

        r = random.random() * total
        cumulative = 0.0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return pool[i]

        return pool[-1]

    def _calculate_weight(self, item: dict[str, Any]) -> float:
        """
        Calculate selection weight for content item.

        Weight Formula:
            60% performance + 15% freshness + 15% persona + 10% discovery

        Args:
            item: Content dictionary

        Returns:
            Final weight value (minimum 0.01)
        """
        # Base scores
        performance = item.get("performance_score", 50.0)
        freshness = item.get("freshness_score", 50.0)
        persona_boost = item.get("persona_boost", 1.0)

        # Discovery bonus for under-tested content
        times_used = item.get("times_used", 0)
        if times_used is None:
            times_used = 0
        discovery_bonus = 1.5 if times_used < 3 else 1.0

        # Calculate weighted score
        weight = (
            (performance / 100.0) * 0.60 +
            (freshness / 100.0) * 0.15 +
            (persona_boost - 0.95) * 0.15 +  # Normalized persona impact
            discovery_bonus * 0.10
        )

        return max(0.01, weight)

    def _create_placeholder(
        self, content_type: str, slot: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Create placeholder for slot without available content.

        Args:
            content_type: The content type identifier
            slot: Original slot dictionary

        Returns:
            Placeholder content dictionary with theme guidance
        """
        from content_type_loaders import get_theme_guidance

        theme_guidance = get_theme_guidance(content_type)

        return {
            **slot,
            "content_id": None,
            "content_text": None,
            "content_type": content_type,
            "has_caption": False,
            "theme_guidance": theme_guidance,
            "freshness_score": 100.0,
            "performance_score": 50.0,
            "persona_boost": 1.0,
        }

    def _update_recent_types(self, content_type: str) -> None:
        """Track recent content types for rotation enforcement."""
        self._recent_content_types.append(content_type)
        if len(self._recent_content_types) > 5:
            self._recent_content_types.pop(0)

    def ensure_no_duplicates(
        self, assigned_slots: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Verify no duplicate content IDs across all slots.

        Post-processes assigned slots to ensure no caption is used twice
        in the same week across ANY content type.

        Args:
            assigned_slots: List of assigned slot dictionaries

        Returns:
            Deduplicated list of slots with alternatives for duplicates
        """
        seen_ids: set[int] = set()
        deduplicated: list[dict[str, Any]] = []

        for slot in assigned_slots:
            content_id = slot.get("content_id")

            # No content_id means placeholder - always valid
            if content_id is None:
                deduplicated.append(slot)
                continue

            if content_id in seen_ids:
                # Replace with alternative or placeholder
                slot = self._find_alternative(slot)
            else:
                seen_ids.add(content_id)

            deduplicated.append(slot)

        return deduplicated

    def _find_alternative(self, slot: dict[str, Any]) -> dict[str, Any]:
        """
        Find alternative content for a duplicate slot.

        Args:
            slot: Slot with duplicate content_id

        Returns:
            Slot with alternative content or placeholder
        """
        content_type = slot.get("content_type", "ppv")

        # Try to find another caption in the same pool
        if content_type in ("ppv", "ppv_follow_up"):
            pool = self._get_all_captions_as_dicts()
        else:
            pool = self._content_pools.get(content_type, [])

        available = [
            c for c in pool
            if c.get("content_id") is not None
            and c.get("content_id") not in self._used_content_ids
        ]

        if available:
            selected = self._weighted_select(available)
            if selected:
                content_id = selected.get("content_id")
                if content_id is not None:
                    self._used_content_ids.add(content_id)
                return {**slot, **selected}

        # Fall back to placeholder
        return self._create_placeholder(content_type, slot)

    def _get_all_captions_as_dicts(self) -> list[dict[str, Any]]:
        """Convert all caption pool captions to dictionaries."""
        result: list[dict[str, Any]] = []

        for pool in self._caption_pools.values():
            for caption in pool.get_all_captions():
                result.append({
                    "content_id": caption.caption_id,
                    "content_text": caption.caption_text,
                    "content_type": caption.content_type_name,
                    "content_type_id": caption.content_type_id,
                    "freshness_score": caption.freshness_score,
                    "performance_score": caption.performance_score,
                    "persona_boost": caption.persona_boost,
                    "pool_type": caption.pool_type,
                })

        return result

    def enforce_rotation(
        self, assigned_slots: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Ensure no same content type 3x consecutively.

        Post-processes assigned slots to enforce content type rotation
        and prevent audience fatigue from repetitive content.

        Args:
            assigned_slots: List of assigned slot dictionaries

        Returns:
            List of slots with rotation enforced
        """
        result: list[dict[str, Any]] = []
        recent_types: list[str] = []

        for slot in assigned_slots:
            content_type = slot.get("content_type", "unknown")

            # Check for 3x consecutive same type
            if len(recent_types) >= 2 and all(t == content_type for t in recent_types[-2:]):
                # Try to swap with different type content
                slot = self._attempt_rotation_swap(slot, result)
                content_type = slot.get("content_type", "unknown")

            result.append(slot)
            recent_types.append(content_type)
            if len(recent_types) > 5:
                recent_types.pop(0)

        return result

    def _attempt_rotation_swap(
        self, slot: dict[str, Any], previous_slots: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Attempt to swap slot content with a different type.

        Args:
            slot: Slot with repeated content type
            previous_slots: Previously processed slots

        Returns:
            Original or swapped slot
        """
        current_type = slot.get("content_type", "unknown")

        # Try to find content from a different type
        for type_id, pool in self._content_pools.items():
            if type_id == current_type:
                continue

            available = [
                c for c in pool
                if c.get("content_id") is None
                or c.get("content_id") not in self._used_content_ids
            ]

            if available:
                selected = self._weighted_select(available)
                if selected:
                    content_id = selected.get("content_id")
                    if content_id is not None:
                        self._used_content_ids.add(content_id)

                    logger.debug(
                        f"Rotation swap: {current_type} -> {type_id} "
                        f"to avoid 3x consecutive"
                    )
                    return {**slot, **selected}

        # Couldn't swap - return original
        return slot

    def get_assignment_stats(self) -> dict[str, Any]:
        """
        Return statistics about content assignment.

        Returns:
            Dictionary with assignment statistics including:
            - total_assigned: Total slots with content
            - unique_content_used: Count of unique content IDs
            - by_content_type: Count per content type
            - pools_loaded: List of loaded pool names
        """
        return {
            "total_assigned": sum(self._content_type_counts.values()),
            "unique_content_used": len(self._used_content_ids),
            "by_content_type": dict(self._content_type_counts),
            "caption_pools_loaded": list(self._caption_pools.keys()),
            "content_pools_loaded": list(self._content_pools.keys()),
        }


# =============================================================================
# MULTI-TYPE STRATIFIED POOLS
# =============================================================================


class MultiTypeStratifiedPools:
    """
    Manages stratified pools across multiple content types.

    This class provides a unified interface for managing stratified caption
    pools for all PPV-like content types that use the earnings-based pool
    classification (PROVEN, GLOBAL_EARNER, DISCOVERY).

    Example:
        >>> multi_pools = MultiTypeStratifiedPools(conn, creator_id, "paid")
        >>> ppv_pool = multi_pools.get_pool("ppv")
        >>> caption = ppv_pool.proven[0] if ppv_pool.has_proven else None
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        creator_id: str,
        page_type: str,
        min_freshness: float = 30.0,
    ) -> None:
        """
        Initialize multi-type stratified pools manager.

        Args:
            conn: Database connection with row_factory set
            creator_id: Creator UUID
            page_type: Page type ("paid" or "free")
            min_freshness: Minimum freshness score for captions
        """
        self.conn = conn
        self.creator_id = creator_id
        self.page_type = page_type
        self.min_freshness = min_freshness
        self._pools: dict[str, StratifiedPools] = {}
        self._loaded = False

    def load_pools(self) -> None:
        """Load stratified pools for all valid content types."""
        strategy = ContentTypeStrategy(self.conn, self.creator_id)
        allowed_types = [ct.content_type_id for ct in strategy.get_allowed_content_types()]

        if allowed_types:
            pools_by_id = load_stratified_pools(
                self.conn,
                self.creator_id,
                allowed_content_types=allowed_types,
                min_freshness=self.min_freshness,
            )

            # Index by type name for easier lookup
            for pool in pools_by_id.values():
                self._pools[pool.type_name] = pool

        self._loaded = True
        logger.info(f"MultiTypeStratifiedPools loaded {len(self._pools)} pools")

    def get_pool(self, content_type: str) -> StratifiedPools | None:
        """
        Get stratified pool for content type.

        Args:
            content_type: Content type name

        Returns:
            StratifiedPools for the type, or None if not found
        """
        if not self._loaded:
            self.load_pools()

        return self._pools.get(content_type)

    def get_all_pools(self) -> dict[str, StratifiedPools]:
        """
        Get all loaded pools.

        Returns:
            Dictionary mapping type name to StratifiedPools
        """
        if not self._loaded:
            self.load_pools()

        return self._pools

    def get_pool_stats(self) -> dict[str, dict[str, int]]:
        """
        Get statistics for all pools.

        Returns:
            Dictionary mapping type name to pool size stats
        """
        if not self._loaded:
            self.load_pools()

        stats: dict[str, dict[str, int]] = {}
        for type_name, pool in self._pools.items():
            stats[type_name] = {
                "proven": len(pool.proven),
                "global_earners": len(pool.global_earners),
                "discovery": len(pool.discovery),
                "total": pool.total_count,
            }
        return stats


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

Hook Rotation (Phase 3 - Anti-Detection):
    - Same consecutive hook penalty: 0.70x
    - Hook types: curiosity, personal, exclusivity, recency, question, direct, teasing
    - Promotes natural variation in opening hooks
        """,
    )

    parser.add_argument("--creator", "-c", help="Creator page name (e.g., missalexa)")
    parser.add_argument("--creator-id", help="Creator UUID")
    parser.add_argument(
        "--count", "-n", type=int, default=10, help="Number of captions to select (default: 10)"
    )
    parser.add_argument(
        "--slot-type",
        "-s",
        choices=["premium", "standard", "discovery"],
        default="standard",
        help="Slot type: premium, standard, or discovery (default: standard)",
    )
    parser.add_argument(
        "--min-freshness", type=float, default=30.0, help="Minimum freshness score (default: 30)"
    )
    parser.add_argument("--no-persona", action="store_true", help="Disable persona boost")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--db", default=str(DB_PATH), help=f"Database path (default: {DB_PATH})")

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
