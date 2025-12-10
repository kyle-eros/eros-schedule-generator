#!/usr/bin/env python3
"""
Unit tests for pattern_extraction.py

Tests the two-tier pattern extraction system that analyzes historical
mass_message performance to guide caption selection.

Test Categories:
    - TestBuildPatternProfile: Creator-specific profile building
    - TestBuildGlobalPatternProfile: Global fallback profile building
    - TestPatternProfileCache: LRU cache with TTL expiration
    - TestGetPatternScore: Pattern score lookup with fallbacks
    - TestConfidenceCalculation: Confidence scoring based on sample count
    - TestNormalizedScores: Percentile score calculation
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path
TESTS_DIR = Path(__file__).parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from models import PatternProfile, PatternStats
from pattern_extraction import (
    BASE_PATTERN_SCORE,
    GLOBAL_PROFILE_DISCOUNT,
    MIN_SAMPLES_FOR_COMBINED_PATTERN,
    MIN_SAMPLES_FOR_CREATOR_PROFILE,
    PatternProfileCache,
    build_global_pattern_profile,
    build_pattern_profile,
    get_pattern_score,
    warm_pattern_cache,
    _calculate_confidence,
    _calculate_normalized_scores,
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
    """Provide a sample PatternProfile for testing."""
    return PatternProfile(
        creator_id="test_creator",
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
def empty_profile() -> PatternProfile:
    """Provide an empty PatternProfile for edge case testing."""
    return PatternProfile(
        creator_id="empty",
        combined_patterns={},
        content_type_patterns={},
        tone_patterns={},
        hook_patterns={},
        sample_count=0,
        confidence=0.5,
        is_global_fallback=True,
        cached_at=datetime.now(),
    )


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
# TEST: build_pattern_profile()
# =============================================================================


class TestBuildPatternProfile:
    """Tests for build_pattern_profile()."""

    def test_builds_profile_for_existing_creator(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should build profile with combined and individual patterns."""
        profile = build_pattern_profile(db_connection, active_creator_id)

        assert profile.creator_id == active_creator_id
        assert profile.sample_count >= 0
        assert 0.5 <= profile.confidence <= 1.0
        assert profile.cached_at is not None

    def test_sets_global_fallback_for_sparse_data(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Should set is_global_fallback=True when <20 samples."""
        # Test with a non-existent creator that will have 0 samples
        profile = build_pattern_profile(db_connection, "nonexistent_creator_xyz")

        assert profile.sample_count == 0
        assert profile.is_global_fallback is True
        assert profile.confidence == 0.5

    def test_calculates_normalized_scores(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Normalized scores should be 0-100 percentiles."""
        profile = build_pattern_profile(db_connection, active_creator_id)

        # Check content type patterns
        for key, stats in profile.content_type_patterns.items():
            assert 0 <= stats.normalized_score <= 100, (
                f"Content type '{key}' has invalid normalized_score: {stats.normalized_score}"
            )

        # Check tone patterns
        for key, stats in profile.tone_patterns.items():
            assert 0 <= stats.normalized_score <= 100, (
                f"Tone '{key}' has invalid normalized_score: {stats.normalized_score}"
            )

        # Check hook patterns
        for key, stats in profile.hook_patterns.items():
            assert 0 <= stats.normalized_score <= 100, (
                f"Hook '{key}' has invalid normalized_score: {stats.normalized_score}"
            )

    def test_combined_patterns_require_min_samples(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Combined patterns should only appear with 3+ samples."""
        profile = build_pattern_profile(db_connection, active_creator_id)

        for key, stats in profile.combined_patterns.items():
            assert stats.sample_count >= MIN_SAMPLES_FOR_COMBINED_PATTERN, (
                f"Combined pattern '{key}' has only {stats.sample_count} samples, "
                f"minimum required is {MIN_SAMPLES_FOR_COMBINED_PATTERN}"
            )

    def test_returns_correct_dataclass_type(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should return a PatternProfile dataclass."""
        profile = build_pattern_profile(db_connection, active_creator_id)

        assert isinstance(profile, PatternProfile)
        assert hasattr(profile, "combined_patterns")
        assert hasattr(profile, "content_type_patterns")
        assert hasattr(profile, "tone_patterns")
        assert hasattr(profile, "hook_patterns")


# =============================================================================
# TEST: build_global_pattern_profile()
# =============================================================================


class TestBuildGlobalPatternProfile:
    """Tests for build_global_pattern_profile()."""

    def test_builds_global_profile(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Should aggregate patterns across all creators."""
        profile = build_global_pattern_profile(db_connection)

        assert profile.creator_id == "GLOBAL"
        assert profile.is_global_fallback is True
        assert profile.sample_count > 0

    def test_applies_discount_to_scores(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Normalized scores should be discounted by 0.7x."""
        profile = build_global_pattern_profile(db_connection)

        # The max possible discounted score is 100 * 0.7 = 70
        if profile.content_type_patterns:
            max_score = max(
                stats.normalized_score
                for stats in profile.content_type_patterns.values()
            )
            assert max_score <= 100 * GLOBAL_PROFILE_DISCOUNT + 0.1, (
                f"Max score {max_score} exceeds discount threshold"
            )

    def test_global_profile_has_more_patterns(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Global profile should generally have more patterns than individual creators."""
        global_profile = build_global_pattern_profile(db_connection)
        creator_profile = build_pattern_profile(db_connection, active_creator_id)

        # Global should have equal or more samples
        assert global_profile.sample_count >= creator_profile.sample_count


# =============================================================================
# TEST: PatternProfileCache
# =============================================================================


class TestPatternProfileCache:
    """Tests for PatternProfileCache."""

    def test_cache_miss_returns_none(self) -> None:
        """Should return None for uncached profiles."""
        cache = PatternProfileCache()
        assert cache.get("unknown_creator") is None

    def test_cache_set_and_get(self, sample_profile: PatternProfile) -> None:
        """Should store and retrieve profiles."""
        cache = PatternProfileCache()
        cache.set("test_creator", sample_profile)

        retrieved = cache.get("test_creator")
        assert retrieved is not None
        assert retrieved.creator_id == sample_profile.creator_id
        assert retrieved.sample_count == sample_profile.sample_count

    def test_cache_eviction_at_max_size(self, sample_profile: PatternProfile) -> None:
        """Should evict LRU entries when at capacity."""
        cache = PatternProfileCache(max_size=2)

        # Add 3 profiles to a cache with max_size=2
        profile1 = PatternProfile(
            creator_id="creator1",
            combined_patterns={},
            content_type_patterns={},
            tone_patterns={},
            hook_patterns={},
            sample_count=10,
            confidence=0.7,
            is_global_fallback=False,
            cached_at=datetime.now(),
        )
        profile2 = PatternProfile(
            creator_id="creator2",
            combined_patterns={},
            content_type_patterns={},
            tone_patterns={},
            hook_patterns={},
            sample_count=20,
            confidence=0.8,
            is_global_fallback=False,
            cached_at=datetime.now(),
        )

        cache.set("creator1", profile1)
        cache.set("creator2", profile2)
        cache.set("creator3", sample_profile)  # Should evict creator1

        assert cache.get("creator1") is None, "creator1 should have been evicted"
        assert cache.get("creator2") is not None, "creator2 should still be cached"
        assert cache.get("creator3") is not None, "creator3 should be cached"

    def test_cache_ttl_expiration(self, sample_profile: PatternProfile) -> None:
        """Should return None for expired entries."""
        # Create cache with very short TTL (nearly immediate expiration)
        cache = PatternProfileCache(ttl_hours=0)  # 0 hours = immediate
        cache.set("test", sample_profile)

        # Cache entry should be expired immediately or after small delay
        time.sleep(0.01)  # Small delay to ensure expiration
        result = cache.get("test")
        assert result is None, "Expired entry should return None"

    def test_cache_invalidate(self, sample_profile: PatternProfile) -> None:
        """Should remove profile from cache on invalidation."""
        cache = PatternProfileCache()
        cache.set("test_creator", sample_profile)

        assert cache.get("test_creator") is not None

        cache.invalidate("test_creator")

        assert cache.get("test_creator") is None

    def test_cache_clear(self, sample_profile: PatternProfile) -> None:
        """Should remove all profiles from cache on clear."""
        cache = PatternProfileCache()
        cache.set("creator1", sample_profile)
        cache.set("creator2", sample_profile)

        cache.clear()

        assert cache.get("creator1") is None
        assert cache.get("creator2") is None

    def test_cache_stats(self, sample_profile: PatternProfile) -> None:
        """Should return accurate cache statistics."""
        cache = PatternProfileCache(max_size=50, ttl_hours=12)
        cache.set("creator1", sample_profile)
        cache.set("creator2", sample_profile)

        stats = cache.stats()

        assert stats["size"] == 2
        assert stats["max_size"] == 50
        assert stats["ttl_hours"] == 12
        assert "creator1" in stats["cached_creators"]
        assert "creator2" in stats["cached_creators"]

    def test_cache_lru_ordering(self, sample_profile: PatternProfile) -> None:
        """Cache should maintain LRU order on access."""
        cache = PatternProfileCache(max_size=2)

        profile1 = PatternProfile(
            creator_id="creator1",
            combined_patterns={},
            content_type_patterns={},
            tone_patterns={},
            hook_patterns={},
            sample_count=10,
            confidence=0.7,
            is_global_fallback=False,
            cached_at=datetime.now(),
        )
        profile2 = PatternProfile(
            creator_id="creator2",
            combined_patterns={},
            content_type_patterns={},
            tone_patterns={},
            hook_patterns={},
            sample_count=20,
            confidence=0.8,
            is_global_fallback=False,
            cached_at=datetime.now(),
        )

        cache.set("creator1", profile1)
        cache.set("creator2", profile2)

        # Access creator1 to make it most recently used
        _ = cache.get("creator1")

        # Add creator3 - should evict creator2 (now LRU)
        cache.set("creator3", sample_profile)

        assert cache.get("creator1") is not None, "creator1 should still be cached (MRU)"
        assert cache.get("creator2") is None, "creator2 should have been evicted (LRU)"
        assert cache.get("creator3") is not None, "creator3 should be cached"


# =============================================================================
# TEST: get_pattern_score()
# =============================================================================


class TestGetPatternScore:
    """Tests for get_pattern_score()."""

    def test_returns_combined_pattern_score(
        self, sample_profile: PatternProfile
    ) -> None:
        """Should return score from combined patterns when available."""
        # sample_profile has "sextape|seductive|fire" with score 80.0
        score = get_pattern_score(sample_profile, "sextape", "seductive", "fire")

        assert score == 80.0

    def test_falls_back_to_individual_attributes(
        self, sample_profile: PatternProfile
    ) -> None:
        """Should average individual scores when no combined match."""
        # Use attributes that exist individually but not as a combination
        # sextape (75.0), playful (60.0), heart (55.0)
        score = get_pattern_score(sample_profile, "sextape", "playful", "heart")

        # Should be average of available individual patterns
        expected = (75.0 + 60.0 + 55.0) / 3
        assert abs(score - expected) < 0.1, (
            f"Expected {expected}, got {score}"
        )

    def test_returns_base_score_for_no_data(
        self, empty_profile: PatternProfile
    ) -> None:
        """Should return 30.0 base score when profile has no data."""
        score = get_pattern_score(empty_profile, "any", "any", "any")
        assert score == BASE_PATTERN_SCORE

    def test_handles_partial_matches(
        self, sample_profile: PatternProfile
    ) -> None:
        """Should average only available individual patterns."""
        # Only content_type exists, tone and hook don't
        score = get_pattern_score(sample_profile, "sextape", "unknown_tone", "unknown_hook")

        # Should use only sextape pattern (75.0)
        expected = 75.0
        assert abs(score - expected) < 0.1, (
            f"Expected {expected}, got {score}"
        )

    def test_handles_none_values(
        self, sample_profile: PatternProfile
    ) -> None:
        """Should handle None/empty values gracefully."""
        score = get_pattern_score(sample_profile, None, None, None)
        assert score == BASE_PATTERN_SCORE

        score = get_pattern_score(sample_profile, "", "", "")
        assert score == BASE_PATTERN_SCORE

    def test_combined_takes_priority(
        self, sample_profile: PatternProfile
    ) -> None:
        """Combined pattern should take priority over individual patterns."""
        # The combined pattern "sextape|seductive|fire" has score 80.0
        # Individual scores would average differently
        combined_score = get_pattern_score(sample_profile, "sextape", "seductive", "fire")

        # Verify it's using the combined score, not averaged individuals
        # Individual average would be: (75.0 + 70.0 + 65.0) / 3 = 70.0
        assert combined_score == 80.0, (
            "Should use combined pattern score, not individual average"
        )


# =============================================================================
# TEST: Confidence Calculation
# =============================================================================


class TestConfidenceCalculation:
    """Tests for _calculate_confidence()."""

    def test_low_samples_return_minimum_confidence(self) -> None:
        """Should return 0.5 for <20 samples."""
        assert _calculate_confidence(0) == 0.5
        assert _calculate_confidence(10) == 0.5
        assert _calculate_confidence(19) == 0.5

    def test_medium_samples_return_moderate_confidence(self) -> None:
        """Should return 0.7 for 20-50 samples."""
        assert _calculate_confidence(20) == 0.7
        assert _calculate_confidence(35) == 0.7
        assert _calculate_confidence(49) == 0.7

    def test_good_samples_return_good_confidence(self) -> None:
        """Should return 0.85 for 50-100 samples."""
        assert _calculate_confidence(50) == 0.85
        assert _calculate_confidence(75) == 0.85
        assert _calculate_confidence(99) == 0.85

    def test_high_samples_return_full_confidence(self) -> None:
        """Should return 1.0 for 100+ samples."""
        assert _calculate_confidence(100) == 1.0
        assert _calculate_confidence(500) == 1.0
        assert _calculate_confidence(10000) == 1.0


# =============================================================================
# TEST: Normalized Scores Calculation
# =============================================================================


class TestNormalizedScores:
    """Tests for _calculate_normalized_scores()."""

    def test_empty_patterns_return_empty_dict(self) -> None:
        """Should return empty dict for empty input."""
        result = _calculate_normalized_scores([])
        assert result == {}

    def test_single_pattern_gets_100_percentile(self) -> None:
        """Single pattern should get 100 percentile."""
        patterns = [{"content_type": "sextape", "avg_earnings": 50.0}]
        result = _calculate_normalized_scores(patterns)

        assert result["sextape"] == 100.0

    def test_patterns_ranked_by_earnings(self) -> None:
        """Higher earnings should get higher percentile."""
        patterns = [
            {"content_type": "low", "avg_earnings": 10.0},
            {"content_type": "mid", "avg_earnings": 50.0},
            {"content_type": "high", "avg_earnings": 100.0},
        ]
        result = _calculate_normalized_scores(patterns)

        assert result["high"] > result["mid"] > result["low"]

    def test_percentiles_range_0_to_100(self) -> None:
        """All percentiles should be between 0 and 100."""
        patterns = [
            {"content_type": f"type_{i}", "avg_earnings": float(i * 10)}
            for i in range(1, 11)
        ]
        result = _calculate_normalized_scores(patterns)

        for key, score in result.items():
            assert 0 <= score <= 100, f"{key} has invalid score {score}"


# =============================================================================
# TEST: warm_pattern_cache()
# =============================================================================


class TestWarmPatternCache:
    """Tests for warm_pattern_cache()."""

    def test_warms_specified_creators(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should warm cache for specified creator IDs."""
        cache = PatternProfileCache()
        profiles = warm_pattern_cache(
            db_connection, cache, creator_ids=[active_creator_id]
        )

        assert active_creator_id in profiles
        assert cache.get(active_creator_id) is not None

    def test_includes_global_profile(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should also warm the global profile."""
        cache = PatternProfileCache()
        profiles = warm_pattern_cache(
            db_connection, cache, creator_ids=[active_creator_id]
        )

        assert "GLOBAL" in profiles
        assert cache.get("GLOBAL") is not None

    def test_returns_all_loaded_profiles(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Should return dict of all loaded profiles."""
        cache = PatternProfileCache()
        profiles = warm_pattern_cache(
            db_connection, cache, creator_ids=[active_creator_id]
        )

        # Should have at least the creator profile and global
        assert len(profiles) >= 2
        for creator_id, profile in profiles.items():
            assert isinstance(profile, PatternProfile)


# =============================================================================
# TEST: Integration Tests
# =============================================================================


class TestPatternExtractionIntegration:
    """Integration tests combining multiple functions."""

    def test_full_workflow(
        self, db_connection: sqlite3.Connection, active_creator_id: str
    ) -> None:
        """Test complete pattern extraction workflow."""
        # 1. Build pattern profile
        profile = build_pattern_profile(db_connection, active_creator_id)

        # 2. Cache it
        cache = PatternProfileCache()
        cache.set(active_creator_id, profile)

        # 3. Retrieve from cache
        cached = cache.get(active_creator_id)
        assert cached is not None

        # 4. Use for scoring
        if profile.combined_patterns:
            # Get a real combined key
            key = list(profile.combined_patterns.keys())[0]
            ct, tone, hook = key.split("|")
            score = get_pattern_score(cached, ct, tone, hook)
            assert 0 <= score <= 100

    def test_global_fallback_workflow(
        self, db_connection: sqlite3.Connection
    ) -> None:
        """Test fallback to global profile for sparse data."""
        # Build profile for non-existent creator
        creator_profile = build_pattern_profile(db_connection, "sparse_creator_xyz")

        # Should be flagged for global fallback
        assert creator_profile.is_global_fallback is True

        # Build global profile
        global_profile = build_global_pattern_profile(db_connection)

        # Global should have more data
        assert global_profile.sample_count > creator_profile.sample_count
