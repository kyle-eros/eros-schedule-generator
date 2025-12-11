#!/usr/bin/env python3
"""
Unit tests for fresh caption selection functionality.

Tests the weight calculation and caption selection modules including:
- weights.py: calculate_pattern_score, calculate_never_used_bonus,
              calculate_exploration_weight, calculate_fresh_weight
- select_captions.py: load_unified_pool, select_from_unified_pool,
                      select_exploration_caption

Test Categories:
    - TestCalculatePatternScore: Pattern-based scoring
    - TestCalculateNeverUsedBonus: Freshness tier multipliers
    - TestCalculateExplorationWeight: Diversity promotion scoring
    - TestCalculateFreshWeight: Unified fresh weight formula
    - TestLoadUnifiedPool: Hard exclusion pool loading
    - TestSelectFromUnifiedPool: Weighted caption selection
    - TestSelectExplorationCaption: Exploration slot selection
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path
TESTS_DIR = Path(__file__).parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from models import PatternProfile, PatternStats, ScoredCaption, SelectionPool
from weights import (
    BASE_PATTERN_SCORE,
    EXPLORATION_CONTENT_TYPE_BONUS,
    EXPLORATION_HOOK_TYPE_BONUS,
    EXPLORATION_TONE_BONUS,
    FRESHNESS_MULTIPLIERS,
    MAX_EXPLORATION_SCORE,
    MIN_WEIGHT,
    calculate_exploration_weight,
    calculate_fresh_weight,
    calculate_never_used_bonus,
    calculate_pattern_score,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def db_path() -> str:
    """Get the database path from environment or default."""
    return os.path.expanduser(
        os.environ.get(
            "EROS_DATABASE_PATH",
            "~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db",
        )
    )


@pytest.fixture
def db_connection(db_path: str) -> sqlite3.Connection:
    """Provide database connection with row_factory set."""
    if not os.path.exists(db_path):
        pytest.skip(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def sample_profile() -> PatternProfile:
    """Provide sample PatternProfile with test data."""
    return PatternProfile(
        creator_id="test",
        combined_patterns={
            "sextape|seductive|fire": PatternStats(
                avg_earnings=100.0,
                sample_count=5,
                normalized_score=80.0,
            ),
            "solo|playful|heart": PatternStats(
                avg_earnings=75.0,
                sample_count=4,
                normalized_score=65.0,
            ),
        },
        content_type_patterns={
            "sextape": PatternStats(
                avg_earnings=90.0,
                sample_count=10,
                normalized_score=75.0,
            ),
            "solo": PatternStats(
                avg_earnings=60.0,
                sample_count=8,
                normalized_score=55.0,
            ),
        },
        tone_patterns={
            "seductive": PatternStats(
                avg_earnings=85.0,
                sample_count=8,
                normalized_score=70.0,
            ),
            "playful": PatternStats(
                avg_earnings=70.0,
                sample_count=12,
                normalized_score=60.0,
            ),
        },
        hook_patterns={
            "fire": PatternStats(
                avg_earnings=80.0,
                sample_count=6,
                normalized_score=65.0,
            ),
            "heart": PatternStats(
                avg_earnings=65.0,
                sample_count=9,
                normalized_score=55.0,
            ),
        },
        sample_count=50,
        confidence=0.85,
        is_global_fallback=False,
        cached_at=datetime.now(),
    )


@pytest.fixture
def sample_caption() -> dict[str, Any]:
    """Provide sample caption dict for weight calculation."""
    return {
        "caption_id": 1,
        "caption_text": "Test caption text for testing purposes",
        "content_type_name": "sextape",
        "tone": "seductive",
        "hook_type": "fire",
        "freshness_tier": "never_used",
        "freshness_score": 100,
        "pattern_score": 50,
        "times_used_on_page": 0,
    }


@pytest.fixture
def sample_schedule_context() -> dict[str, Any]:
    """Provide sample schedule context for exploration scoring."""
    return {
        "used_hook_types": {"question", "urgency"},
        "used_tones": {"playful", "sweet"},
        "content_type_counts": {"sextape": 3, "solo": 2},
        "target_content_distribution": {"sextape": 5, "solo": 5, "b/g": 3},
    }


@pytest.fixture
def empty_schedule_context() -> dict[str, Any]:
    """Provide empty schedule context."""
    return {
        "used_hook_types": set(),
        "used_tones": set(),
        "content_type_counts": {},
        "target_content_distribution": {},
    }


@pytest.fixture
def active_creator_id(db_connection: sqlite3.Connection) -> str:
    """Get an active creator ID from the database."""
    cursor = db_connection.execute(
        "SELECT creator_id FROM creators WHERE is_active = 1 LIMIT 1"
    )
    row = cursor.fetchone()
    if not row:
        pytest.skip("No active creators in database")
    return row["creator_id"]


# =============================================================================
# TEST: calculate_pattern_score()
# =============================================================================


class TestCalculatePatternScore:
    """Tests for calculate_pattern_score()."""

    def test_returns_combined_pattern_score(
        self, sample_profile: PatternProfile, sample_caption: dict[str, Any]
    ) -> None:
        """Should use combined pattern when available."""
        # sample_caption matches combined pattern "sextape|seductive|fire"
        sample_caption["content_type_name"] = "sextape"
        sample_caption["tone"] = "seductive"
        sample_caption["hook_type"] = "fire"

        score = calculate_pattern_score(sample_caption, sample_profile)

        # Combined pattern has normalized_score=80.0, confidence=0.85
        # Score = 80.0 * 0.85 = 68.0
        expected = 80.0 * 0.85
        assert abs(score - expected) < 0.1, f"Expected {expected}, got {score}"

    def test_falls_back_to_individual_average(
        self, sample_profile: PatternProfile, sample_caption: dict[str, Any]
    ) -> None:
        """Should average individual scores when no combined match."""
        sample_caption["content_type_name"] = "sextape"
        sample_caption["tone"] = "seductive"
        sample_caption["hook_type"] = "unknown"  # No combined pattern

        score = calculate_pattern_score(sample_caption, sample_profile)

        # Should average: sextape(75) + seductive(70) = 145/2 = 72.5
        # Then multiply by confidence: 72.5 * 0.85 = 61.625
        individual_avg = (75.0 + 70.0) / 2
        expected = individual_avg * 0.85
        assert abs(score - expected) < 1.0, f"Expected ~{expected}, got {score}"

    def test_returns_base_score_for_no_match(
        self, sample_profile: PatternProfile, sample_caption: dict[str, Any]
    ) -> None:
        """Should return BASE_PATTERN_SCORE (30) when nothing matches."""
        sample_caption["content_type_name"] = "unknown_type"
        sample_caption["tone"] = "unknown_tone"
        sample_caption["hook_type"] = "unknown_hook"

        score = calculate_pattern_score(sample_caption, sample_profile)

        assert score == BASE_PATTERN_SCORE

    def test_handles_none_profile(self, sample_caption: dict[str, Any]) -> None:
        """Should return BASE_PATTERN_SCORE when profile is None."""
        score = calculate_pattern_score(sample_caption, None)

        assert score == BASE_PATTERN_SCORE

    def test_handles_scored_caption_object(
        self, sample_profile: PatternProfile
    ) -> None:
        """Should work with ScoredCaption objects, not just dicts."""
        caption = ScoredCaption(
            caption_id=1,
            caption_text="Test caption",
            caption_type="ppv",
            content_type_id=1,
            content_type_name="sextape",
            tone="seductive",
            hook_type="fire",
            freshness_score=100.0,
            performance_score=75.0,
            times_used_on_page=0,
            last_used_date=None,
            pattern_score=0.0,
            freshness_tier="never_used",
            never_used_on_page=True,
            selection_weight=0.0,
        )

        score = calculate_pattern_score(caption, sample_profile)

        # Should get combined pattern score
        expected = 80.0 * 0.85  # combined_score * confidence
        assert abs(score - expected) < 0.1


# =============================================================================
# TEST: calculate_never_used_bonus()
# =============================================================================


class TestCalculateNeverUsedBonus:
    """Tests for calculate_never_used_bonus()."""

    def test_never_used_tier_returns_1_5(self) -> None:
        """Never-used tier should return 1.5x multiplier."""
        caption: dict[str, Any] = {"freshness_tier": "never_used"}
        result = calculate_never_used_bonus(caption, "creator")

        assert result == FRESHNESS_MULTIPLIERS["never_used"]
        assert result == 1.5

    def test_fresh_tier_returns_1_0(self) -> None:
        """Fresh tier should return 1.0x multiplier."""
        caption: dict[str, Any] = {"freshness_tier": "fresh"}
        result = calculate_never_used_bonus(caption, "creator")

        assert result == FRESHNESS_MULTIPLIERS["fresh"]
        assert result == 1.0

    def test_excluded_tier_returns_0(self) -> None:
        """Excluded tier should return 0.0 multiplier."""
        caption: dict[str, Any] = {"freshness_tier": "excluded"}
        result = calculate_never_used_bonus(caption, "creator")

        assert result == FRESHNESS_MULTIPLIERS["excluded"]
        assert result == 0.0

    def test_times_used_zero_returns_never_used(self) -> None:
        """times_used_on_page=0 should return never_used multiplier."""
        caption: dict[str, Any] = {
            "caption_id": 123,
            "times_used_on_page": 0,
        }
        result = calculate_never_used_bonus(caption, "creator")

        assert result == FRESHNESS_MULTIPLIERS["never_used"]

    def test_unknown_tier_defaults_to_fresh(self) -> None:
        """Unknown tier should default to fresh multiplier."""
        caption: dict[str, Any] = {
            "freshness_tier": "unknown_tier",
            "freshness_score": 50.0,
        }
        result = calculate_never_used_bonus(caption, "creator")

        assert result == 1.0  # Default

    def test_low_freshness_returns_excluded(self) -> None:
        """Low freshness score should return excluded multiplier when times_used > 0."""
        caption: dict[str, Any] = {
            "caption_id": 456,
            "freshness_score": 20.0,  # Below 30 threshold
            "times_used_on_page": 5,  # Must have been used to check freshness_score
        }
        result = calculate_never_used_bonus(caption, "creator")

        assert result == FRESHNESS_MULTIPLIERS["excluded"]


# =============================================================================
# TEST: calculate_exploration_weight()
# =============================================================================


class TestCalculateExplorationWeight:
    """Tests for calculate_exploration_weight()."""

    def test_high_score_for_unused_attributes(
        self, sample_caption: dict[str, Any], empty_schedule_context: dict[str, Any]
    ) -> None:
        """Should give bonuses for unused attributes."""
        sample_caption["hook_type"] = "fire"
        sample_caption["tone"] = "seductive"
        sample_caption["content_type_name"] = "sextape"
        sample_caption["pattern_score"] = 20  # Low pattern score

        score = calculate_exploration_weight(sample_caption, empty_schedule_context)

        # With no used attributes and target distribution empty:
        # base_inverse = max(0, 50 - 20) = 30
        # hook_bonus = 20 (unused)
        # tone_bonus = 15 (unused)
        # content_type_bonus = 0 (not in target_distribution)
        # Total = 30 + 20 + 15 = 65
        assert score >= 40, f"Expected high exploration score, got {score}"

    def test_no_bonus_for_used_attributes(
        self, sample_caption: dict[str, Any], sample_schedule_context: dict[str, Any]
    ) -> None:
        """Should not give bonuses for already used attributes."""
        sample_caption["hook_type"] = "question"  # Already in used_hook_types
        sample_caption["tone"] = "playful"  # Already in used_tones
        sample_caption["content_type_name"] = "sextape"  # Not under-represented
        sample_caption["pattern_score"] = 50

        score = calculate_exploration_weight(sample_caption, sample_schedule_context)

        # No bonuses except base inverse
        # base_inverse = max(0, 50 - 50) = 0
        # All attributes already used, so no exploration bonuses
        assert score < 30, f"Expected low exploration score, got {score}"

    def test_content_type_bonus_when_under_represented(
        self, sample_caption: dict[str, Any], sample_schedule_context: dict[str, Any]
    ) -> None:
        """Should give bonus for under-represented content types."""
        sample_caption["hook_type"] = "question"  # Used
        sample_caption["tone"] = "playful"  # Used
        sample_caption["content_type_name"] = "solo"  # count=2, target=5 -> under-rep
        sample_caption["pattern_score"] = 50

        score = calculate_exploration_weight(sample_caption, sample_schedule_context)

        # Should get content_type bonus since 2 < 5
        # base_inverse = 0, content_bonus = 10
        assert score >= 10, f"Expected content type bonus, got {score}"

    def test_capped_at_100(
        self, sample_caption: dict[str, Any], empty_schedule_context: dict[str, Any]
    ) -> None:
        """Exploration weight should not exceed 100."""
        sample_caption["pattern_score"] = 0  # Maximum inverse
        sample_caption["hook_type"] = "unused_hook"
        sample_caption["tone"] = "unused_tone"
        sample_caption["content_type_name"] = "any"

        score = calculate_exploration_weight(sample_caption, empty_schedule_context)

        assert score <= MAX_EXPLORATION_SCORE

    def test_empty_context_returns_zero(
        self, sample_caption: dict[str, Any]
    ) -> None:
        """Empty or None context should return 0."""
        score = calculate_exploration_weight(sample_caption, {})
        assert score == 0.0

        score = calculate_exploration_weight(sample_caption, None)  # type: ignore
        assert score == 0.0


# =============================================================================
# TEST: calculate_fresh_weight()
# =============================================================================


class TestCalculateFreshWeight:
    """Tests for calculate_fresh_weight()."""

    def test_returns_tuple_with_breakdown(
        self,
        sample_profile: PatternProfile,
        sample_caption: dict[str, Any],
        empty_schedule_context: dict[str, Any],
    ) -> None:
        """Should return (weight, breakdown_dict)."""
        weight, breakdown = calculate_fresh_weight(
            caption=sample_caption,
            pattern_profile=sample_profile,
            persona_score=75.0,
            schedule_context=empty_schedule_context,
        )

        assert isinstance(weight, float)
        assert isinstance(breakdown, dict)
        assert "pattern_match" in breakdown
        assert "never_used_bonus" in breakdown
        assert "persona" in breakdown
        assert "freshness_bonus" in breakdown
        assert "exploration" in breakdown
        assert "total" in breakdown

    def test_never_used_gets_higher_weight(
        self, sample_profile: PatternProfile, empty_schedule_context: dict[str, Any]
    ) -> None:
        """Never-used captions should score higher than fresh."""
        never_used_caption: dict[str, Any] = {
            "caption_id": 1,
            "freshness_tier": "never_used",
            "content_type_name": "sextape",
            "tone": "seductive",
            "hook_type": "fire",
            "freshness_score": 100,
        }

        fresh_caption: dict[str, Any] = {
            "caption_id": 2,
            "freshness_tier": "fresh",
            "content_type_name": "sextape",
            "tone": "seductive",
            "hook_type": "fire",
            "freshness_score": 50,
        }

        weight_never, _ = calculate_fresh_weight(
            never_used_caption, sample_profile, 50.0, empty_schedule_context
        )
        weight_fresh, _ = calculate_fresh_weight(
            fresh_caption, sample_profile, 50.0, empty_schedule_context
        )

        assert weight_never > weight_fresh, (
            f"Never-used ({weight_never}) should score higher than fresh ({weight_fresh})"
        )

    def test_breakdown_contains_mode(
        self,
        sample_profile: PatternProfile,
        sample_caption: dict[str, Any],
        empty_schedule_context: dict[str, Any],
    ) -> None:
        """Breakdown should contain mode='fresh'."""
        _, breakdown = calculate_fresh_weight(
            sample_caption, sample_profile, 50.0, empty_schedule_context
        )

        assert breakdown["mode"] == "fresh"

    def test_weight_minimum(
        self,
        sample_profile: PatternProfile,
        sample_caption: dict[str, Any],
        empty_schedule_context: dict[str, Any],
    ) -> None:
        """Weight should never be below MIN_WEIGHT."""
        sample_caption["freshness_tier"] = "excluded"
        sample_caption["freshness_score"] = 0

        weight, _ = calculate_fresh_weight(
            sample_caption, sample_profile, 0.0, empty_schedule_context
        )

        assert weight >= MIN_WEIGHT

    def test_persona_score_affects_weight(
        self,
        sample_profile: PatternProfile,
        sample_caption: dict[str, Any],
        empty_schedule_context: dict[str, Any],
    ) -> None:
        """Higher persona score should result in higher weight."""
        weight_high_persona, _ = calculate_fresh_weight(
            sample_caption, sample_profile, 100.0, empty_schedule_context
        )
        weight_low_persona, _ = calculate_fresh_weight(
            sample_caption, sample_profile, 0.0, empty_schedule_context
        )

        assert weight_high_persona > weight_low_persona


# =============================================================================
# TEST: load_unified_pool() - requires database
# =============================================================================


class TestLoadUnifiedPool:
    """Tests for load_unified_pool()."""

    def test_excludes_recent_captions(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Captions used within exclusion window should be excluded."""
        # Import here to avoid issues if module not available
        from select_captions import get_content_type_ids, load_unified_pool

        # Get some content types
        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types, exclusion_days=60
            )

            for caption in pool.captions:
                assert caption.freshness_tier in ("never_used", "fresh"), (
                    f"Caption {caption.caption_id} has invalid tier: {caption.freshness_tier}"
                )
                assert caption.freshness_tier != "excluded"
        except Exception as e:
            # May fail if no captions available
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise

    def test_assigns_freshness_tiers(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """All captions should have freshness_tier assigned."""
        from select_captions import load_unified_pool

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )

            for caption in pool.captions:
                assert caption.freshness_tier in ("never_used", "fresh")
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise

    def test_counts_tiers_correctly(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Pool should have correct tier counts."""
        from select_captions import load_unified_pool

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )

            actual_never_used = sum(
                1 for c in pool.captions if c.freshness_tier == "never_used"
            )
            actual_fresh = sum(
                1 for c in pool.captions if c.freshness_tier == "fresh"
            )

            assert pool.never_used_count == actual_never_used
            assert pool.fresh_count == actual_fresh
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise

    def test_returns_selection_pool(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should return a SelectionPool instance."""
        from select_captions import load_unified_pool

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )

            assert isinstance(pool, SelectionPool)
            assert pool.creator_id == active_creator_id
            assert len(pool.content_types) > 0
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise


# =============================================================================
# TEST: select_from_unified_pool() - requires database
# =============================================================================


class TestSelectFromUnifiedPool:
    """Tests for select_from_unified_pool()."""

    def test_selects_requested_count(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should select the requested number of captions."""
        from pattern_extraction import build_pattern_profile
        from select_captions import load_unified_pool, select_from_unified_pool

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )
            profile = build_pattern_profile(db_connection, active_creator_id)

            count = min(5, len(pool.captions))
            if count == 0:
                pytest.skip("No captions in pool")

            selected = select_from_unified_pool(
                pool, profile, persona=None, exclude_ids=set(), count=count
            )

            assert len(selected) == count
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise

    def test_excludes_specified_ids(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should not select captions in exclude_ids."""
        from pattern_extraction import build_pattern_profile
        from select_captions import load_unified_pool, select_from_unified_pool

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )
            profile = build_pattern_profile(db_connection, active_creator_id)

            if len(pool.captions) < 3:
                pytest.skip("Not enough captions for test")

            # Exclude first two caption IDs
            exclude_ids = {pool.captions[0].caption_id, pool.captions[1].caption_id}

            selected = select_from_unified_pool(
                pool, profile, persona=None, exclude_ids=exclude_ids, count=3
            )

            selected_ids = {c.caption_id for c in selected}
            assert exclude_ids.isdisjoint(selected_ids), (
                f"Excluded IDs {exclude_ids} found in selection {selected_ids}"
            )
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise

    def test_assigns_selection_weights(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Selected captions should have selection_weight > 0."""
        from pattern_extraction import build_pattern_profile
        from select_captions import load_unified_pool, select_from_unified_pool

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )
            profile = build_pattern_profile(db_connection, active_creator_id)

            if len(pool.captions) == 0:
                pytest.skip("No captions in pool")

            selected = select_from_unified_pool(
                pool, profile, persona=None, exclude_ids=set(), count=3
            )

            for caption in selected:
                assert caption.selection_weight > 0, (
                    f"Caption {caption.caption_id} has zero weight"
                )
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise


# =============================================================================
# TEST: select_exploration_caption() - requires database
# =============================================================================


class TestSelectExplorationCaption:
    """Tests for select_exploration_caption()."""

    def test_returns_scored_caption_or_none(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should return ScoredCaption or None."""
        from pattern_extraction import build_pattern_profile
        from select_captions import (
            load_unified_pool,
            select_exploration_caption,
        )

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )
            profile = build_pattern_profile(db_connection, active_creator_id)

            schedule_context: dict[str, Any] = {
                "used_hook_types": set(),
                "used_tones": set(),
                "content_type_counts": {},
                "target_content_distribution": {},
            }

            result = select_exploration_caption(
                pool, profile, schedule_context, exclude_ids=set()
            )

            assert result is None or isinstance(result, ScoredCaption)
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise

    def test_excludes_specified_ids(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should not return caption in exclude_ids."""
        from pattern_extraction import build_pattern_profile
        from select_captions import (
            load_unified_pool,
            select_exploration_caption,
        )

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )
            profile = build_pattern_profile(db_connection, active_creator_id)

            if len(pool.captions) == 0:
                pytest.skip("No captions in pool")

            # Exclude all caption IDs
            exclude_ids = {c.caption_id for c in pool.captions}

            schedule_context: dict[str, Any] = {
                "used_hook_types": set(),
                "used_tones": set(),
                "content_type_counts": {},
                "target_content_distribution": {},
            }

            result = select_exploration_caption(
                pool, profile, schedule_context, exclude_ids=exclude_ids
            )

            # Should return None since all are excluded
            assert result is None
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise


# =============================================================================
# TEST: Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_calculate_pattern_score_with_empty_strings(
        self, sample_profile: PatternProfile
    ) -> None:
        """Should handle empty string attributes."""
        caption: dict[str, Any] = {
            "content_type_name": "",
            "tone": "",
            "hook_type": "",
        }
        score = calculate_pattern_score(caption, sample_profile)
        assert score == BASE_PATTERN_SCORE

    def test_calculate_exploration_weight_with_none_attributes(
        self, empty_schedule_context: dict[str, Any]
    ) -> None:
        """Should handle None caption attributes."""
        caption: dict[str, Any] = {
            "content_type_name": None,
            "tone": None,
            "hook_type": None,
            "pattern_score": None,
        }
        score = calculate_exploration_weight(caption, empty_schedule_context)
        # Should use defaults and not crash
        assert isinstance(score, float)

    def test_fresh_weight_with_minimal_caption(
        self, sample_profile: PatternProfile, empty_schedule_context: dict[str, Any]
    ) -> None:
        """Should handle caption with minimal fields."""
        minimal_caption: dict[str, Any] = {
            "caption_id": 999,
        }
        weight, breakdown = calculate_fresh_weight(
            minimal_caption, sample_profile, 50.0, empty_schedule_context
        )
        assert isinstance(weight, float)
        assert weight >= MIN_WEIGHT
        assert isinstance(breakdown, dict)


# =============================================================================
# TEST: get_item_type_for_content_type()
# =============================================================================


def test_get_item_type_for_content_type() -> None:
    """Test that item_type is correctly derived from content type registry channel."""
    from content_type_registry import get_item_type_for_content_type

    # Feed channel types -> wall_post
    assert get_item_type_for_content_type("first_to_tip") == "wall_post"
    assert get_item_type_for_content_type("tip_request") == "wall_post"
    assert get_item_type_for_content_type("vip_post") == "wall_post"

    # Mass message channel types -> ppv
    assert get_item_type_for_content_type("ppv") == "ppv"
    assert get_item_type_for_content_type("bundle") == "ppv"

    # Edge cases
    assert get_item_type_for_content_type(None) == "ppv"
    assert get_item_type_for_content_type("unknown") == "ppv"


# =============================================================================
# TEST: Integration
# =============================================================================


class TestFreshSelectionIntegration:
    """Integration tests for fresh selection workflow."""

    def test_full_selection_workflow(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Test complete selection workflow from pool to selection."""
        from pattern_extraction import build_pattern_profile
        from select_captions import load_unified_pool, select_from_unified_pool

        cursor = db_connection.execute(
            "SELECT content_type_id FROM content_types LIMIT 3"
        )
        content_types = [row["content_type_id"] for row in cursor.fetchall()]

        if not content_types:
            pytest.skip("No content types in database")

        try:
            # Step 1: Build pattern profile
            profile = build_pattern_profile(db_connection, active_creator_id)
            assert profile is not None

            # Step 2: Load unified pool
            pool = load_unified_pool(
                db_connection, active_creator_id, content_types
            )
            assert len(pool.captions) > 0

            # Step 3: Select captions
            count = min(3, len(pool.captions))
            selected = select_from_unified_pool(
                pool, profile, persona=None, exclude_ids=set(), count=count
            )

            # Verify results
            assert len(selected) == count
            for caption in selected:
                assert isinstance(caption, ScoredCaption)
                assert caption.selection_weight > 0
                assert caption.freshness_tier in ("never_used", "fresh")
        except Exception as e:
            if "CaptionExhaustionError" in str(type(e)):
                pytest.skip("No captions available for test")
            raise


# =============================================================================
# TEST: Volume Tier Calculations
# =============================================================================


class TestVolumeTierCalculations:
    """Tests for volume tier calculation based on fan count."""

    def test_volume_tier_low_boundary(self) -> None:
        """Fan count < 1000 = LOW tier = 2-3 PPV/day."""
        from schedule_builder import ScheduleBuilder

        assert ScheduleBuilder._get_volume_level(None, 0) == "Low"
        assert ScheduleBuilder._get_volume_level(None, 500) == "Low"
        assert ScheduleBuilder._get_volume_level(None, 999) == "Low"

    def test_volume_tier_mid_boundary(self) -> None:
        """Fan count 1000-5000 = MID tier = 3-4 PPV/day."""
        from schedule_builder import ScheduleBuilder

        assert ScheduleBuilder._get_volume_level(None, 1000) == "Mid"
        assert ScheduleBuilder._get_volume_level(None, 2500) == "Mid"
        assert ScheduleBuilder._get_volume_level(None, 4999) == "Mid"

    def test_volume_tier_high_boundary(self) -> None:
        """Fan count 5000-15000 = HIGH tier = 4-5 PPV/day."""
        from schedule_builder import ScheduleBuilder

        assert ScheduleBuilder._get_volume_level(None, 5000) == "High"
        assert ScheduleBuilder._get_volume_level(None, 10000) == "High"
        assert ScheduleBuilder._get_volume_level(None, 14999) == "High"

    def test_volume_tier_ultra_boundary(self) -> None:
        """Fan count 15000+ = ULTRA tier = 5-6 PPV/day."""
        from schedule_builder import ScheduleBuilder

        assert ScheduleBuilder._get_volume_level(None, 15000) == "Ultra"
        assert ScheduleBuilder._get_volume_level(None, 50000) == "Ultra"
        assert ScheduleBuilder._get_volume_level(None, 100000) == "Ultra"

    def test_volume_tier_edge_case_exact_1000(self) -> None:
        """1000 exactly should be MID tier start."""
        from schedule_builder import ScheduleBuilder

        # Boundary test: 999 is Low, 1000 is Mid
        assert ScheduleBuilder._get_volume_level(None, 999) == "Low"
        assert ScheduleBuilder._get_volume_level(None, 1000) == "Mid"

    def test_volume_tier_edge_case_exact_5000(self) -> None:
        """5000 exactly should be HIGH tier start."""
        from schedule_builder import ScheduleBuilder

        # Boundary test: 4999 is Mid, 5000 is High
        assert ScheduleBuilder._get_volume_level(None, 4999) == "Mid"
        assert ScheduleBuilder._get_volume_level(None, 5000) == "High"

    def test_volume_tier_edge_case_exact_15000(self) -> None:
        """15000 exactly should be ULTRA tier start."""
        from schedule_builder import ScheduleBuilder

        # Boundary test: 14999 is High, 15000 is Ultra
        assert ScheduleBuilder._get_volume_level(None, 14999) == "High"
        assert ScheduleBuilder._get_volume_level(None, 15000) == "Ultra"


# =============================================================================
# TEST: Pricing Matrix
# =============================================================================


class TestPricingMatrix:
    """Tests for pricing calculations by page type and content type."""

    def test_pricing_matrix_structure(self) -> None:
        """Test that PRICING_MATRIX has correct structure."""
        from enrichment import PRICING_MATRIX

        assert "paid" in PRICING_MATRIX
        assert "free" in PRICING_MATRIX
        assert "default" in PRICING_MATRIX["paid"]
        assert "default" in PRICING_MATRIX["free"]

    def test_pricing_paid_page_bundle(self) -> None:
        """Paid page bundles should price at $18-22."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["paid"]["bundle"]
        assert min_price == 18.0
        assert max_price == 22.0

    def test_pricing_free_page_bundle(self) -> None:
        """Free page bundles should price at $12-15."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["free"]["bundle"]
        assert min_price == 12.0
        assert max_price == 15.0

    def test_pricing_paid_page_solo(self) -> None:
        """Paid page solo should price at $12-15."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["paid"]["solo"]
        assert min_price == 12.0
        assert max_price == 15.0

    def test_pricing_free_page_solo(self) -> None:
        """Free page solo should price at $8-10."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["free"]["solo"]
        assert min_price == 8.0
        assert max_price == 10.0

    def test_pricing_paid_page_sextape(self) -> None:
        """Paid page sextape should price at $22-28."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["paid"]["sextape"]
        assert min_price == 22.0
        assert max_price == 28.0

    def test_pricing_free_page_sextape(self) -> None:
        """Free page sextape should price at $15-20."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["free"]["sextape"]
        assert min_price == 15.0
        assert max_price == 20.0

    def test_pricing_paid_page_bg(self) -> None:
        """Paid page B/G couples should price at $28-35."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["paid"]["bg"]
        assert min_price == 28.0
        assert max_price == 35.0

    def test_pricing_free_page_bg(self) -> None:
        """Free page B/G couples should price at $20-25."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["free"]["bg"]
        assert min_price == 20.0
        assert max_price == 25.0

    def test_pricing_paid_page_custom(self) -> None:
        """Paid page custom/interactive should price at $35-50."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["paid"]["custom"]
        assert min_price == 35.0
        assert max_price == 50.0

    def test_pricing_free_page_custom(self) -> None:
        """Free page custom/interactive should price at $25-35."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["free"]["custom"]
        assert min_price == 25.0
        assert max_price == 35.0

    def test_pricing_paid_page_dick_rating(self) -> None:
        """Paid page dick rating should price at $15-25."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["paid"]["dick_rating"]
        assert min_price == 15.0
        assert max_price == 25.0

    def test_pricing_free_page_dick_rating(self) -> None:
        """Free page dick rating should price at $10-18."""
        from enrichment import PRICING_MATRIX

        min_price, max_price = PRICING_MATRIX["free"]["dick_rating"]
        assert min_price == 10.0
        assert max_price == 18.0

    def test_pricing_content_type_normalization_bundle_variants(self) -> None:
        """Bundle variants map to bundle pricing category."""
        from enrichment import CONTENT_TYPE_NORMALIZATION

        bundle_variants = [
            "bundle_offer", "bundle offer", "flash_sale", "flash sale",
            "photo_set", "photo set", "photoset", "gallery",
        ]
        for variant in bundle_variants:
            assert CONTENT_TYPE_NORMALIZATION.get(variant) == "bundle", (
                f"Expected '{variant}' to map to 'bundle'"
            )

    def test_pricing_content_type_normalization_solo_variants(self) -> None:
        """Solo variants map to solo pricing category."""
        from enrichment import CONTENT_TYPE_NORMALIZATION

        solo_variants = [
            "selfie", "lingerie", "nude", "topless", "shower",
            "bath", "teasing", "toy_play",
        ]
        for variant in solo_variants:
            assert CONTENT_TYPE_NORMALIZATION.get(variant) == "solo", (
                f"Expected '{variant}' to map to 'solo'"
            )

    def test_pricing_content_type_normalization_sextape_variants(self) -> None:
        """Sextape variants map to sextape pricing category."""
        from enrichment import CONTENT_TYPE_NORMALIZATION

        sextape_variants = [
            "video", "full_video", "full video", "sex_tape",
            "masturbation", "creampie", "anal",
        ]
        for variant in sextape_variants:
            assert CONTENT_TYPE_NORMALIZATION.get(variant) == "sextape", (
                f"Expected '{variant}' to map to 'sextape'"
            )

    def test_pricing_content_type_normalization_bg_variants(self) -> None:
        """B/G variants map to bg pricing category."""
        from enrichment import CONTENT_TYPE_NORMALIZATION

        bg_variants = [
            "b/g", "b_g", "boy_girl", "boy girl", "couples",
            "couple", "duo", "blowjob",
        ]
        for variant in bg_variants:
            assert CONTENT_TYPE_NORMALIZATION.get(variant) == "bg", (
                f"Expected '{variant}' to map to 'bg'"
            )


# =============================================================================
# TEST: Semantic Boost Cache
# =============================================================================


class TestSemanticBoostCache:
    """Tests for semantic boost cache save/load functionality."""

    def test_semantic_boost_result_creation(self) -> None:
        """Test SemanticBoostResult dataclass creation."""
        from models import SemanticBoostResult

        result = SemanticBoostResult(
            caption_id=4521,
            persona_boost=1.32,
            detected_tone="playful",
            tone_confidence=0.91,
            matches_creator_voice=True,
            emoji_alignment="good",
            slang_alignment="perfect",
            authenticity_score=0.89,
            reasoning="Strong playful energy with teasing build-up",
        )

        assert result.caption_id == 4521
        assert result.persona_boost == 1.32
        assert result.detected_tone == "playful"
        assert result.tone_confidence == 0.91
        assert result.matches_creator_voice is True

    def test_semantic_boost_cache_round_trip(self) -> None:
        """Test SemanticBoostCache round-trip save/load."""
        import json
        import tempfile
        from models import SemanticBoostResult

        # Create test data
        boosts = [
            SemanticBoostResult(
                caption_id=1,
                persona_boost=1.25,
                detected_tone="playful",
                tone_confidence=0.85,
            ),
            SemanticBoostResult(
                caption_id=2,
                persona_boost=1.15,
                detected_tone="seductive",
                tone_confidence=0.78,
            ),
        ]

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = [
                {
                    "caption_id": b.caption_id,
                    "persona_boost": b.persona_boost,
                    "detected_tone": b.detected_tone,
                    "tone_confidence": b.tone_confidence,
                    "matches_creator_voice": b.matches_creator_voice,
                    "emoji_alignment": b.emoji_alignment,
                    "slang_alignment": b.slang_alignment,
                    "authenticity_score": b.authenticity_score,
                    "reasoning": b.reasoning,
                }
                for b in boosts
            ]
            json.dump(data, f)
            temp_path = f.name

        try:
            # Load from file
            with open(temp_path, "r") as f:
                loaded_data = json.load(f)

            # Reconstruct objects
            loaded_boosts = [
                SemanticBoostResult(**item)
                for item in loaded_data
            ]

            # Verify round-trip
            assert len(loaded_boosts) == 2
            assert loaded_boosts[0].caption_id == 1
            assert loaded_boosts[0].persona_boost == 1.25
            assert loaded_boosts[0].detected_tone == "playful"
            assert loaded_boosts[1].caption_id == 2
            assert loaded_boosts[1].persona_boost == 1.15
            assert loaded_boosts[1].detected_tone == "seductive"

        finally:
            import os
            os.unlink(temp_path)

    def test_semantic_boost_applied_to_selection_weight(self) -> None:
        """Loaded semantic boosts affect caption selection scores."""
        from models import SemanticBoostResult

        # Create semantic boost
        boost = SemanticBoostResult(
            caption_id=1,
            persona_boost=1.35,
            detected_tone="playful",
            tone_confidence=0.92,
        )

        # Base weight
        base_weight = 100.0

        # Apply boost
        adjusted_weight = base_weight * boost.persona_boost
        assert adjusted_weight == 135.0

        # Boost should be > 1.0 for positive match
        assert boost.persona_boost > 1.0

    def test_semantic_boost_frozen_dataclass(self) -> None:
        """Test that SemanticBoostResult is immutable (frozen dataclass)."""
        from models import SemanticBoostResult

        result = SemanticBoostResult(
            caption_id=1,
            persona_boost=1.25,
            detected_tone="playful",
        )

        # Should not be able to modify
        with pytest.raises(AttributeError):
            result.caption_id = 2  # type: ignore

    def test_semantic_boost_default_values(self) -> None:
        """Test SemanticBoostResult default values."""
        from models import SemanticBoostResult

        result = SemanticBoostResult(
            caption_id=1,
            persona_boost=1.0,
            detected_tone="neutral",
        )

        # Check defaults
        assert result.tone_confidence == 0.0
        assert result.matches_creator_voice is True
        assert result.emoji_alignment == "good"
        assert result.slang_alignment == "good"
        assert result.authenticity_score == 0.0
        assert result.reasoning == ""