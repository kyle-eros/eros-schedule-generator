#!/usr/bin/env python3
"""
Schedule Uniqueness Engine.

Ensures each creator receives a 100% unique schedule by:
1. Using creator-specific historical performance patterns
2. Applying timing variance (7-10 minutes)
3. Weighting content selection based on past success
4. Tracking cross-week deduplication
5. Generating schedule fingerprints for duplicate detection

Usage:
    from schedule_uniqueness import ScheduleUniquenessEngine, UniquenessMetrics

    engine = ScheduleUniquenessEngine(conn, creator_id)
    engine.load_historical_patterns()

    # Apply uniqueness to schedule slots
    weighted_slots = engine.apply_historical_weighting(content_pool, slot)
    varied_slots = engine.apply_timing_variance(slots)
    unique_slots = engine.ensure_uniqueness(varied_slots)

    # Get metrics
    metrics = engine.get_metrics(unique_slots)
    logger.info(f"Uniqueness Score: {metrics.uniqueness_score}%")

Note: This module uses the standard logging module for all diagnostic output.
"""

from __future__ import annotations

import hashlib
import logging
import random
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

# Configure module logger
logger = logging.getLogger(__name__)

__all__ = [
    "ScheduleUniquenessEngine",
    "UniquenessMetrics",
    "apply_uniqueness",
]


@dataclass
class UniquenessMetrics:
    """Metrics for schedule uniqueness.

    Attributes:
        fingerprint: SHA-256 hash (16 chars) uniquely identifying this schedule.
        uniqueness_score: Score from 0-100 indicating schedule uniqueness.
        timing_variance_applied: Number of slots with timing variance.
        historical_weight_factor: Average historical weighting applied.
        cross_week_duplicates: Count of captions also used in recent weeks.
        content_type_distribution: Dict mapping content type to slot count.
    """

    fingerprint: str
    uniqueness_score: float  # 0-100
    timing_variance_applied: int  # Number of slots with variance
    historical_weight_factor: float  # Average historical weighting
    cross_week_duplicates: int  # Captions also used in recent weeks
    content_type_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "fingerprint": self.fingerprint,
            "uniqueness_score": self.uniqueness_score,
            "timing_variance_applied": self.timing_variance_applied,
            "historical_weight_factor": self.historical_weight_factor,
            "cross_week_duplicates": self.cross_week_duplicates,
            "content_type_distribution": self.content_type_distribution,
        }


@dataclass
class HistoricalPattern:
    """Historical performance pattern for a time slot.

    Attributes:
        hour: Hour of day (0-23).
        day_of_week: Day of week (0=Sunday, 6=Saturday).
        avg_purchase_rate: Average purchase rate for this slot.
        send_count: Number of sends in this slot historically.
    """

    hour: int
    day_of_week: int
    avg_purchase_rate: float
    send_count: int


class ScheduleUniquenessEngine:
    """Engine for generating unique schedules per creator.

    This engine ensures each creator receives a 100% unique schedule by:
    - Loading and analyzing historical performance patterns
    - Applying organic timing variance (7-10 minutes)
    - Weighting content based on historical success
    - Tracking cross-week caption usage for freshness
    - Generating fingerprints for duplicate detection

    Attributes:
        conn: SQLite database connection.
        creator_id: Unique identifier for the creator.
        TIMING_VARIANCE_MIN: Minimum timing variance in minutes (-10).
        TIMING_VARIANCE_MAX: Maximum timing variance in minutes (+10).
        VARIANCE_PROBABILITY: Probability of applying variance (0.85).
        PERFORMANCE_WEIGHT: Weight for performance scoring (0.6).
        RECENCY_WEIGHT: Weight for recency scoring (0.2).
        DIVERSITY_WEIGHT: Weight for diversity scoring (0.2).
    """

    # Variance configuration
    TIMING_VARIANCE_MIN: int = -10  # minutes
    TIMING_VARIANCE_MAX: int = 10  # minutes
    VARIANCE_PROBABILITY: float = 0.85  # 85% of slots get variance

    # Historical weighting factors
    PERFORMANCE_WEIGHT: float = 0.6
    RECENCY_WEIGHT: float = 0.2
    DIVERSITY_WEIGHT: float = 0.2

    # Cross-week lookback period
    RECENT_WEEKS_LOOKBACK: int = 4  # 28 days
    HISTORICAL_DAYS_LOOKBACK: int = 90  # 3 months

    # Minimum sends for reliable pattern
    MIN_SENDS_FOR_PATTERN: int = 5

    def __init__(self, conn: sqlite3.Connection, creator_id: str) -> None:
        """Initialize the uniqueness engine.

        Args:
            conn: SQLite database connection with Row factory.
            creator_id: Unique identifier for the creator.
        """
        self.conn = conn
        self.creator_id = creator_id
        self._recent_schedules: list[str] = []
        self._historical_patterns: dict[str, Any] = {}
        self._used_captions_recent: set[int] = set()
        self._hourly_performance: dict[tuple[int, int], HistoricalPattern] = {}

    def load_historical_patterns(self) -> None:
        """Load creator's historical performance patterns from database.

        Loads:
        - Recent schedule fingerprints (last 4 weeks)
        - Recently used caption IDs (last 28 days)
        - Historical timing patterns (last 90 days)

        This method should be called before applying uniqueness operations.
        """
        self._load_recent_schedules()
        self._load_used_captions()
        self._load_timing_patterns()

    def _load_recent_schedules(self) -> None:
        """Load recent schedule fingerprints from database."""
        try:
            # Check if fingerprint column exists
            cursor = self.conn.execute(
                "PRAGMA table_info(schedule_templates)"
            )
            columns = {row[1] for row in cursor.fetchall()}

            if "fingerprint" not in columns:
                # Column doesn't exist, use algorithm_version as proxy
                logger.debug(
                    "fingerprint column not found, using algorithm_version"
                )
                cursor = self.conn.execute(
                    """
                    SELECT algorithm_version, week_start
                    FROM schedule_templates
                    WHERE creator_id = ?
                    ORDER BY week_start DESC
                    LIMIT ?
                    """,
                    (self.creator_id, self.RECENT_WEEKS_LOOKBACK),
                )
            else:
                cursor = self.conn.execute(
                    """
                    SELECT fingerprint, week_start
                    FROM schedule_templates
                    WHERE creator_id = ?
                    ORDER BY week_start DESC
                    LIMIT ?
                    """,
                    (self.creator_id, self.RECENT_WEEKS_LOOKBACK),
                )

            self._recent_schedules = [
                row[0] for row in cursor.fetchall() if row[0]
            ]
            logger.debug(
                "Loaded %d recent schedule fingerprints for %s",
                len(self._recent_schedules),
                self.creator_id,
            )
        except sqlite3.Error as e:
            logger.warning(
                "Failed to load recent schedules for %s: %s",
                self.creator_id,
                e,
            )
            self._recent_schedules = []

    def _load_used_captions(self) -> None:
        """Load recently used caption IDs from database."""
        try:
            cursor = self.conn.execute(
                """
                SELECT DISTINCT si.caption_id
                FROM schedule_items si
                JOIN schedule_templates st ON si.template_id = st.template_id
                WHERE st.creator_id = ?
                AND st.week_start >= date('now', '-28 days')
                AND si.caption_id IS NOT NULL
                """,
                (self.creator_id,),
            )
            self._used_captions_recent = {
                row[0] for row in cursor.fetchall() if row[0]
            }
            logger.debug(
                "Loaded %d recently used captions for %s",
                len(self._used_captions_recent),
                self.creator_id,
            )
        except sqlite3.Error as e:
            logger.warning(
                "Failed to load used captions for %s: %s",
                self.creator_id,
                e,
            )
            self._used_captions_recent = set()

    def _load_timing_patterns(self) -> None:
        """Load historical timing patterns from mass_messages table."""
        try:
            cursor = self.conn.execute(
                """
                SELECT
                    CAST(strftime('%H', mm.sending_time) AS INTEGER) as hour,
                    CAST(strftime('%w', mm.sending_time) AS INTEGER) as day_of_week,
                    AVG(COALESCE(mm.purchase_rate, 0)) as avg_purchase_rate,
                    COUNT(*) as send_count
                FROM mass_messages mm
                WHERE mm.creator_id = ?
                AND mm.sending_time >= date('now', '-90 days')
                AND mm.sending_time IS NOT NULL
                GROUP BY hour, day_of_week
                ORDER BY avg_purchase_rate DESC
                """,
                (self.creator_id,),
            )

            self._historical_patterns = {
                "peak_hours": [],
                "peak_days": [],
                "hourly_performance": {},
            }
            self._hourly_performance = {}

            for row in cursor.fetchall():
                hour = int(row[0]) if row[0] is not None else 12
                day = int(row[1]) if row[1] is not None else 0
                rate = float(row[2]) if row[2] is not None else 0.0
                count = int(row[3]) if row[3] is not None else 0

                pattern = HistoricalPattern(
                    hour=hour,
                    day_of_week=day,
                    avg_purchase_rate=rate,
                    send_count=count,
                )
                self._hourly_performance[(hour, day)] = pattern

                # Track peak hours (minimum sends and decent rate)
                if count >= self.MIN_SENDS_FOR_PATTERN and rate > 0.05:
                    if hour not in self._historical_patterns["peak_hours"]:
                        self._historical_patterns["peak_hours"].append(hour)

                self._historical_patterns["hourly_performance"][
                    (hour, day)
                ] = {
                    "rate": rate,
                    "count": count,
                }

            logger.debug(
                "Loaded %d timing patterns for %s, peak hours: %s",
                len(self._hourly_performance),
                self.creator_id,
                self._historical_patterns["peak_hours"],
            )
        except sqlite3.Error as e:
            logger.warning(
                "Failed to load timing patterns for %s: %s",
                self.creator_id,
                e,
            )
            self._historical_patterns = {
                "peak_hours": [],
                "peak_days": [],
                "hourly_performance": {},
            }
            self._hourly_performance = {}

    def apply_timing_variance(
        self, slots: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Apply 7-10 minute variance to slot times for organic feel.

        Applies random timing variance to schedule slots to make
        sending patterns appear more organic and avoid detectability.

        Args:
            slots: List of slot dictionaries with time information.

        Returns:
            New list of slots with timing variance applied.
            Each slot includes 'timing_variance_applied' field.
        """
        result: list[dict[str, Any]] = []

        for slot in slots:
            slot_copy = slot.copy()

            # Apply variance with probability
            if random.random() < self.VARIANCE_PROBABILITY:
                variance_minutes = random.randint(
                    self.TIMING_VARIANCE_MIN,
                    self.TIMING_VARIANCE_MAX,
                )

                original_time = slot_copy.get("scheduled_time") or slot_copy.get("time")

                if isinstance(original_time, time):
                    # Convert to minutes, apply variance, convert back
                    new_minutes = (
                        original_time.hour * 60 +
                        original_time.minute +
                        variance_minutes
                    )
                    # Clamp to valid range (0:00 - 23:59)
                    new_minutes = max(0, min(23 * 60 + 59, new_minutes))
                    new_time = time(new_minutes // 60, new_minutes % 60)
                    slot_copy["scheduled_time"] = new_time
                    slot_copy["time"] = new_time
                    slot_copy["timing_variance_applied"] = variance_minutes
                elif isinstance(original_time, str):
                    # Handle string time format "HH:MM"
                    try:
                        parts = original_time.split(":")
                        hour = int(parts[0])
                        minute = int(parts[1]) if len(parts) > 1 else 0
                        new_minutes = hour * 60 + minute + variance_minutes
                        new_minutes = max(0, min(23 * 60 + 59, new_minutes))
                        new_time_str = f"{new_minutes // 60:02d}:{new_minutes % 60:02d}"
                        slot_copy["scheduled_time"] = new_time_str
                        slot_copy["time"] = new_time_str
                        slot_copy["timing_variance_applied"] = variance_minutes
                    except (ValueError, IndexError):
                        slot_copy["timing_variance_applied"] = 0
                else:
                    slot_copy["timing_variance_applied"] = 0
            else:
                slot_copy["timing_variance_applied"] = 0

            result.append(slot_copy)

        return result

    def apply_historical_weighting(
        self,
        content_pool: list[dict[str, Any]],
        slot: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Weight content selection based on creator's historical performance.

        Applies multi-factor weighting to content pool based on:
        - Base performance score (60% weight)
        - Historical timing patterns (20% weight)
        - Diversity and recency factors (20% weight)

        Args:
            content_pool: List of content/caption dictionaries.
            slot: The slot dictionary with timing information.

        Returns:
            New list with 'uniqueness_weight' added to each item.
        """
        if not content_pool:
            return content_pool

        # Extract slot timing info
        slot_hour = self._extract_hour(slot)
        slot_day = self._extract_day_of_week(slot)

        weighted_pool: list[dict[str, Any]] = []

        for content in content_pool:
            content_copy = content.copy()

            # Base weight from performance score (0-1 scale)
            base_weight = content.get("performance_score", 50.0) / 100.0

            # Historical timing bonus
            timing_bonus = self._calculate_timing_bonus(slot_hour, slot_day)

            # Recency penalty for recently used captions
            content_id = content.get("content_id") or content.get("caption_id")
            recency_penalty = (
                0.3 if content_id in self._used_captions_recent else 0.0
            )

            # Diversity bonus for underused content types
            content_type = content.get("content_type", "ppv")
            diversity_bonus = self._calculate_diversity_bonus(
                content_type, weighted_pool
            )

            # Calculate final weight using configured factors
            final_weight = (
                base_weight * self.PERFORMANCE_WEIGHT +
                timing_bonus * self.RECENCY_WEIGHT +
                (1 - recency_penalty) * self.DIVERSITY_WEIGHT +
                diversity_bonus
            )

            # Ensure minimum weight for selection probability
            content_copy["uniqueness_weight"] = max(0.01, final_weight)
            weighted_pool.append(content_copy)

        return weighted_pool

    def _extract_hour(self, slot: dict[str, Any]) -> int | None:
        """Extract hour from slot time field."""
        slot_time = slot.get("scheduled_time") or slot.get("time")
        if isinstance(slot_time, time):
            return slot_time.hour
        elif isinstance(slot_time, str):
            try:
                return int(slot_time.split(":")[0])
            except (ValueError, IndexError):
                return None
        return None

    def _extract_day_of_week(self, slot: dict[str, Any]) -> int | None:
        """Extract day of week from slot date field."""
        slot_date = slot.get("scheduled_date") or slot.get("day")
        if isinstance(slot_date, date):
            return slot_date.weekday()
        elif isinstance(slot_date, str):
            try:
                parsed = date.fromisoformat(slot_date)
                return parsed.weekday()
            except ValueError:
                return None
        return None

    def _calculate_timing_bonus(
        self, hour: int | None, day: int | None
    ) -> float:
        """Calculate timing bonus based on historical performance."""
        if hour is None:
            return 0.0

        # Check for historical pattern at this time
        timing_key = (hour, day if day is not None else 0)
        historical_perf = self._hourly_performance.get(timing_key)

        if historical_perf and historical_perf.send_count >= self.MIN_SENDS_FOR_PATTERN:
            # Scale purchase rate to bonus (rate of 0.10 = 0.20 bonus)
            return min(0.5, historical_perf.avg_purchase_rate * 2)

        return 0.0

    def _calculate_diversity_bonus(
        self, content_type: str, current_pool: list[dict[str, Any]]
    ) -> float:
        """Calculate diversity bonus for underused content types."""
        # Count current content types in weighted pool
        type_counts: dict[str, int] = defaultdict(int)
        for item in current_pool:
            ct = item.get("content_type", "ppv")
            type_counts[ct] += 1

        # Less common types get bonus
        current_count = type_counts.get(content_type, 0)
        if current_count == 0:
            return 0.15  # Bonus for introducing new type
        elif current_count <= 2:
            return 0.10
        else:
            return 0.05  # Base diversity

    def generate_fingerprint(self, slots: list[dict[str, Any]]) -> str:
        """Generate unique fingerprint for schedule.

        Creates a SHA-256 hash of the schedule's content and timing,
        truncated to 16 characters for storage efficiency.

        Args:
            slots: List of schedule slot dictionaries.

        Returns:
            16-character hexadecimal fingerprint string.
        """
        # Create stable representation of schedule
        fingerprint_data: list[str] = []

        # Sort slots by date and time for consistent ordering
        sorted_slots = sorted(
            slots,
            key=lambda s: (
                str(s.get("scheduled_date", s.get("day", ""))),
                str(s.get("scheduled_time", s.get("time", ""))),
            ),
        )

        for slot in sorted_slots:
            # Extract time string consistently
            slot_time = slot.get("scheduled_time", slot.get("time"))
            if isinstance(slot_time, time):
                time_str = slot_time.strftime("%H:%M")
            elif isinstance(slot_time, str):
                time_str = slot_time
            else:
                time_str = "00:00"

            slot_data = (
                str(slot.get("content_type", slot.get("item_type", ""))),
                str(
                    slot.get("content_id")
                    or slot.get("caption_id")
                    or "placeholder"
                ),
                str(slot.get("scheduled_date", slot.get("day", ""))),
                time_str,
            )
            fingerprint_data.append("|".join(slot_data))

        fingerprint_string = "\n".join(fingerprint_data)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]

    def check_duplicate(self, fingerprint: str) -> bool:
        """Check if fingerprint matches any recent schedules.

        Args:
            fingerprint: 16-character fingerprint to check.

        Returns:
            True if fingerprint found in recent schedules.
        """
        return fingerprint in self._recent_schedules

    def calculate_uniqueness_score(
        self, slots: list[dict[str, Any]]
    ) -> float:
        """Calculate uniqueness score (0-100).

        Score is based on:
        - Caption freshness (penalty for cross-week duplicates)
        - Content type diversity (bonus for variety)
        - Historical pattern utilization

        Args:
            slots: List of schedule slot dictionaries.

        Returns:
            Uniqueness score from 0 to 100.
        """
        if not slots:
            return 100.0

        score = 100.0

        # Penalty for cross-week caption duplicates (max 30 points)
        caption_ids = {
            s.get("content_id") or s.get("caption_id")
            for s in slots
            if s.get("content_id") or s.get("caption_id")
        }
        duplicates = caption_ids & self._used_captions_recent
        if caption_ids:
            duplicate_ratio = len(duplicates) / len(caption_ids)
            duplicate_penalty = duplicate_ratio * 30
            score -= duplicate_penalty

        # Bonus for content type diversity (max 10 points)
        content_types = [
            s.get("content_type", s.get("item_type", "ppv")) for s in slots
        ]
        unique_types = len(set(content_types))
        diversity_bonus = min(10, unique_types * 2)
        score = min(100, score + diversity_bonus)

        # Penalty for slots without timing variance (max 10 points)
        variance_applied = sum(
            1 for s in slots if s.get("timing_variance_applied", 0) != 0
        )
        if slots:
            variance_ratio = variance_applied / len(slots)
            if variance_ratio < 0.7:  # Less than 70% with variance
                score -= (0.7 - variance_ratio) * 10

        return max(0, round(score, 1))

    def get_metrics(self, slots: list[dict[str, Any]]) -> UniquenessMetrics:
        """Get comprehensive uniqueness metrics.

        Args:
            slots: List of schedule slot dictionaries.

        Returns:
            UniquenessMetrics dataclass with all metrics.
        """
        fingerprint = self.generate_fingerprint(slots)
        uniqueness_score = self.calculate_uniqueness_score(slots)

        timing_variance_count = sum(
            1 for s in slots if s.get("timing_variance_applied", 0) != 0
        )

        # Calculate average historical weight
        weights = [s.get("uniqueness_weight", 1.0) for s in slots]
        avg_weight = sum(weights) / len(weights) if weights else 1.0

        # Count cross-week duplicates
        caption_ids = {
            s.get("content_id") or s.get("caption_id")
            for s in slots
            if s.get("content_id") or s.get("caption_id")
        }
        cross_week_dups = len(caption_ids & self._used_captions_recent)

        # Content type distribution
        type_dist: dict[str, int] = defaultdict(int)
        for slot in slots:
            content_type = slot.get(
                "content_type", slot.get("item_type", "ppv")
            )
            type_dist[content_type] += 1

        return UniquenessMetrics(
            fingerprint=fingerprint,
            uniqueness_score=uniqueness_score,
            timing_variance_applied=timing_variance_count,
            historical_weight_factor=round(avg_weight, 3),
            cross_week_duplicates=cross_week_dups,
            content_type_distribution=dict(type_dist),
        )

    def ensure_uniqueness(
        self,
        slots: list[dict[str, Any]],
        max_attempts: int = 5,
    ) -> list[dict[str, Any]]:
        """Ensure schedule is unique, re-shuffling if needed.

        Attempts to generate a unique schedule by re-applying
        timing variance with different random seeds.

        Args:
            slots: List of schedule slot dictionaries.
            max_attempts: Maximum retry attempts for uniqueness.

        Returns:
            Schedule slots (unique if possible, original if not).
        """
        for attempt in range(max_attempts):
            fingerprint = self.generate_fingerprint(slots)

            if not self.check_duplicate(fingerprint):
                logger.debug(
                    "Schedule unique after %d attempts (fingerprint: %s)",
                    attempt + 1,
                    fingerprint,
                )
                return slots

            # Re-apply variance with different seed
            random.seed(attempt * 1000 + hash(self.creator_id))
            slots = self.apply_timing_variance(slots)

        # Even if duplicate detected, return with warning
        logger.warning(
            "Could not generate unique schedule for %s after %d attempts",
            self.creator_id,
            max_attempts,
        )
        return slots

    def get_peak_hours(self) -> list[int]:
        """Get creator's peak performance hours.

        Returns:
            List of hours (0-23) with high historical performance.
        """
        peak_hours = self._historical_patterns.get("peak_hours", [])
        return list(peak_hours) if peak_hours else []

    def get_recently_used_captions(self) -> set[int]:
        """Get caption IDs used in recent weeks.

        Returns:
            Set of caption IDs used in last 4 weeks.
        """
        return self._used_captions_recent.copy()


def apply_uniqueness(
    slots: list[dict[str, Any]],
    conn: sqlite3.Connection,
    creator_id: str,
) -> tuple[list[dict[str, Any]], UniquenessMetrics]:
    """Apply uniqueness engine to schedule slots.

    Convenience function for integrating with generate_schedule.py.
    Loads historical patterns, applies weighting and variance,
    and ensures uniqueness.

    Args:
        slots: List of schedule slot dictionaries.
        conn: SQLite database connection.
        creator_id: Unique identifier for the creator.

    Returns:
        Tuple of (processed_slots, metrics).

    Example:
        unique_slots, metrics = apply_uniqueness(slots, conn, creator_id)
        print(f"Uniqueness Score: {metrics.uniqueness_score}%")
        print(f"Fingerprint: {metrics.fingerprint}")
    """
    engine = ScheduleUniquenessEngine(conn, creator_id)
    engine.load_historical_patterns()

    # Apply historical weighting to each slot's content pool
    weighted_slots: list[dict[str, Any]] = []
    for slot in slots:
        # Wrap slot in a pool for weighting (single-item pool)
        pool = [slot]
        weighted = engine.apply_historical_weighting(pool, slot)
        weighted_slots.extend(weighted)

    # Apply timing variance
    varied_slots = engine.apply_timing_variance(weighted_slots)

    # Ensure uniqueness
    unique_slots = engine.ensure_uniqueness(varied_slots)

    # Get metrics
    metrics = engine.get_metrics(unique_slots)

    logger.info(
        "Applied uniqueness to %d slots for %s: score=%.1f, fingerprint=%s",
        len(unique_slots),
        creator_id,
        metrics.uniqueness_score,
        metrics.fingerprint,
    )

    return unique_slots, metrics
