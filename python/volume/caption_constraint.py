"""
Caption pool awareness for volume allocation.

Checks caption availability and flags slots needing manual intervention
without reducing overall volume targets. The system maintains full volume
but identifies slots that need manual caption selection.

This module provides:
- CaptionAvailability: Per-send-type caption availability metrics
- CaptionPoolStatus: Overall caption pool analysis for a creator
- ScheduleSlot: Schedule item with caption assignment/flagging
- CaptionPoolAnalyzer: High-level analyzer class
- VolumeConstraintResult: Result of validating volume against caption pool
- Integration with VolumeConfig from dynamic_calculator

Usage:
    from python.volume.caption_constraint import (
        CaptionPoolAnalyzer,
        get_caption_pool_status,
        validate_volume_against_captions,
    )

    # Analyze caption pool for a creator
    analyzer = CaptionPoolAnalyzer(db_path="/path/to/db.sqlite")
    status = analyzer.analyze(creator_id="creator_123")

    # Check for critical shortages
    if not status.sufficient_coverage:
        for send_type in status.critical_types:
            print(f"Need more captions for {send_type}")

    # Validate VolumeConfig against caption pool
    from python.models.volume import VolumeConfig
    result = analyzer.validate_volume_config(creator_id, volume_config)
    if not result.is_viable:
        print(f"Shortages: {result.shortages}")
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from python.exceptions import DatabaseError
from python.logging_config import get_logger

if TYPE_CHECKING:
    from python.models.volume import VolumeConfig

logger = get_logger(__name__)

# Complete mapping of send_type_key to category based on the 22-type taxonomy
# Reference: docs/SEND_TYPE_REFERENCE.md
SEND_TYPE_CATEGORIES: Dict[str, str] = {
    # Revenue types (9)
    "ppv_unlock": "revenue",
    "ppv_wall": "revenue",
    "tip_goal": "revenue",
    "bundle": "revenue",
    "flash_bundle": "revenue",
    "game_post": "revenue",
    "first_to_tip": "revenue",
    "vip_program": "revenue",
    "snapchat_bundle": "revenue",
    # Engagement types (9)
    "link_drop": "engagement",
    "wall_link_drop": "engagement",
    "bump_normal": "engagement",
    "bump_descriptive": "engagement",
    "bump_text_only": "engagement",
    "bump_flyer": "engagement",
    "dm_farm": "engagement",
    "like_farm": "engagement",
    "live_promo": "engagement",
    # Retention types (4)
    "renew_on_post": "retention",
    "renew_on_message": "retention",
    "ppv_followup": "retention",
    "expired_winback": "retention",
    # Deprecated (1) - still supported during transition
    "ppv_message": "retention",
}


def get_send_type_category(send_type_key: str) -> str:
    """Get the category for a send type key.

    Uses the authoritative SEND_TYPE_CATEGORIES mapping. Falls back to
    prefix-based detection for unknown types (should not happen in production).

    Args:
        send_type_key: The send type key (e.g., 'ppv_unlock', 'bump_normal').

    Returns:
        Category string: 'revenue', 'engagement', or 'retention'.
    """
    if send_type_key in SEND_TYPE_CATEGORIES:
        return SEND_TYPE_CATEGORIES[send_type_key]

    # Fallback for unknown types (should not happen with proper data)
    logger.warning(
        "Unknown send_type_key, using prefix-based category detection",
        extra={"send_type_key": send_type_key},
    )
    if send_type_key.startswith(
        ("ppv_", "vip_", "bundle", "flash_", "snapchat_", "game_", "first_", "tip_")
    ):
        return "revenue"
    elif send_type_key.startswith(("renew_", "expired_")):
        return "retention"
    return "engagement"


@dataclass
class CaptionAvailability:
    """Caption availability for a specific send type.

    Tracks caption pool metrics for a single send type, including
    counts of total, fresh, and usable captions.

    Attributes:
        send_type_key: The send type this availability is for.
        total_captions: Total captions in the pool for this type.
        fresh_captions: Captions meeting freshness threshold.
        usable_captions: Fresh captions also meeting performance threshold.
        avg_freshness: Average freshness score of usable captions.
        avg_performance: Average performance score of usable captions.
        days_of_coverage: How many days of sends this pool can support.
    """

    send_type_key: str
    total_captions: int = 0
    fresh_captions: int = 0
    usable_captions: int = 0
    avg_freshness: float = 0.0
    avg_performance: float = 0.0
    days_of_coverage: float = 0.0

    def is_critical(self, threshold: int = 3) -> bool:
        """Check if this send type has critically low captions.

        Args:
            threshold: Minimum usable captions needed. Defaults to 3.

        Returns:
            True if usable_captions is below threshold.
        """
        return self.usable_captions < threshold


@dataclass
class CaptionPoolStatus:
    """Overall caption pool status for a creator.

    Aggregates caption availability across all send types and provides
    summary statistics for schedule planning.

    Attributes:
        creator_id: Creator identifier.
        analyzed_at: When this analysis was performed.
        by_send_type: Caption availability per send type.
        by_category: Aggregated usable caption counts per category.
        critical_types: Send types with <3 usable captions.
        sufficient_coverage: Whether pool can support a full week.
        coverage_days: Estimated days of coverage for all types.
    """

    creator_id: str
    analyzed_at: datetime = field(default_factory=datetime.now)
    by_send_type: Dict[str, CaptionAvailability] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    critical_types: List[str] = field(default_factory=list)
    sufficient_coverage: bool = True
    coverage_days: float = 7.0

    def get_category_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary statistics by category.

        Returns:
            Dict mapping category to summary with total usable and critical count.
        """
        summary: Dict[str, Dict[str, Any]] = {}
        for send_type_key, availability in self.by_send_type.items():
            category = get_send_type_category(send_type_key)

            if category not in summary:
                summary[category] = {"total_usable": 0, "critical_count": 0}

            summary[category]["total_usable"] += availability.usable_captions
            if availability.is_critical():
                summary[category]["critical_count"] += 1

        return summary

    def get_category_availability(self) -> Dict[str, int]:
        """Get total usable captions per category.

        Aggregates usable captions across all send types within each category.
        Useful for comparing against VolumeConfig category requirements.

        Returns:
            Dict mapping category ('revenue', 'engagement', 'retention') to
            total usable caption count across all send types in that category.
        """
        category_totals: Dict[str, int] = {
            "revenue": 0,
            "engagement": 0,
            "retention": 0,
        }

        for send_type_key, availability in self.by_send_type.items():
            category = get_send_type_category(send_type_key)
            category_totals[category] += availability.usable_captions

        return category_totals


@dataclass
class ScheduleSlot:
    """A scheduled item that may need caption assignment.

    Represents a single slot in the schedule with caption assignment
    status. Used to flag slots needing manual caption selection.

    Attributes:
        scheduled_date: Date for this slot (YYYY-MM-DD format).
        scheduled_time: Time for this slot (HH:MM format).
        send_type_key: The type of send.
        needs_caption: Whether manual caption selection is needed.
        caption_id: Assigned caption ID (if available).
        caption_note: Explanation if caption needed.
        priority: Slot priority (1=highest).
    """

    scheduled_date: str
    scheduled_time: str
    send_type_key: str
    needs_caption: bool = False
    caption_id: Optional[int] = None
    caption_note: str = ""
    priority: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert slot to dictionary for serialization.

        Returns:
            Dict representation of the slot.
        """
        return {
            "scheduled_date": self.scheduled_date,
            "scheduled_time": self.scheduled_time,
            "send_type_key": self.send_type_key,
            "needs_caption": self.needs_caption,
            "caption_id": self.caption_id,
            "caption_note": self.caption_note,
            "priority": self.priority,
        }


@dataclass
class VolumeConstraintResult:
    """Result of validating volume requirements against caption pool.

    Provides a clear assessment of whether a VolumeConfig can be supported
    by the available caption pool, with detailed shortage information.

    Attributes:
        is_viable: True if caption pool can support the requested volume.
        pool_status: The underlying CaptionPoolStatus analysis.
        category_requirements: Required captions per category for the period.
        category_availability: Available captions per category.
        shortages: Dict of categories with shortages and details.
        recommendations: List of actionable recommendations.
        days_analyzed: Number of days the analysis covers.
    """

    is_viable: bool
    pool_status: CaptionPoolStatus
    category_requirements: Dict[str, int] = field(default_factory=dict)
    category_availability: Dict[str, int] = field(default_factory=dict)
    shortages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    days_analyzed: int = 7

    def get_shortage_summary(self) -> str:
        """Get human-readable summary of shortages.

        Returns:
            Multi-line string describing shortages and recommendations.
        """
        if self.is_viable:
            return "Caption pool is sufficient for requested volume."

        lines = ["Caption pool shortages detected:"]
        for category, details in self.shortages.items():
            needed = details.get("needed", 0)
            available = details.get("available", 0)
            shortage = details.get("shortage", 0)
            lines.append(
                f"  - {category.capitalize()}: Need {needed}, have {available} "
                f"(short by {shortage})"
            )

        if self.recommendations:
            lines.append("\nRecommendations:")
            for rec in self.recommendations:
                lines.append(f"  - {rec}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dict representation suitable for JSON serialization.
        """
        return {
            "is_viable": self.is_viable,
            "days_analyzed": self.days_analyzed,
            "category_requirements": self.category_requirements,
            "category_availability": self.category_availability,
            "shortages": self.shortages,
            "recommendations": self.recommendations,
            "critical_send_types": self.pool_status.critical_types,
        }


def get_caption_pool_status(
    conn: sqlite3.Connection,
    creator_id: str,
    min_freshness: float = 30.0,
    min_performance: float = 40.0,
) -> CaptionPoolStatus:
    """Analyze caption pool for a creator.

    Queries the caption_bank to determine availability of usable
    captions per send type and category. A caption is considered
    usable if it is active, meets freshness threshold, and meets
    performance threshold.

    Args:
        conn: Database connection.
        creator_id: Creator to analyze.
        min_freshness: Minimum freshness score threshold (default 30).
        min_performance: Minimum performance score threshold (default 40).

    Returns:
        CaptionPoolStatus with detailed availability analysis.

    Raises:
        DatabaseError: If query fails.
    """
    query = """
        WITH send_type_captions AS (
            SELECT
                st.send_type_key,
                st.category,
                cb.caption_id,
                COALESCE(cb.freshness_score, 100) as freshness,
                COALESCE(cb.performance_score, 50) as performance,
                cb.is_active
            FROM send_types st
            JOIN send_type_caption_requirements stcr ON st.send_type_id = stcr.send_type_id
            JOIN caption_bank cb ON stcr.caption_type = cb.caption_type AND cb.creator_id = ?
            WHERE st.is_active = 1
        )
        SELECT
            send_type_key,
            category,
            COUNT(*) as total,
            SUM(CASE WHEN is_active = 1 AND freshness >= ? THEN 1 ELSE 0 END) as fresh,
            SUM(CASE
                WHEN is_active = 1 AND freshness >= ? AND performance >= ?
                THEN 1 ELSE 0
            END) as usable,
            AVG(CASE
                WHEN is_active = 1 AND freshness >= ? AND performance >= ?
                THEN freshness
            END) as avg_fresh,
            AVG(CASE
                WHEN is_active = 1 AND freshness >= ? AND performance >= ?
                THEN performance
            END) as avg_perf
        FROM send_type_captions
        GROUP BY send_type_key, category
        ORDER BY category, send_type_key
    """

    try:
        cursor = conn.execute(
            query,
            (
                creator_id,
                min_freshness,
                min_freshness,
                min_performance,
                min_freshness,
                min_performance,
                min_freshness,
                min_performance,
            ),
        )
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to analyze caption pool: {e}",
            operation="caption_pool_analysis",
            details={"creator_id": creator_id},
        )

    status = CaptionPoolStatus(creator_id=creator_id)
    category_totals: Dict[str, int] = {}

    for row in rows:
        send_type_key, category, total, fresh, usable, avg_fresh, avg_perf = row

        availability = CaptionAvailability(
            send_type_key=send_type_key,
            total_captions=total or 0,
            fresh_captions=fresh or 0,
            usable_captions=usable or 0,
            avg_freshness=avg_fresh or 0.0,
            avg_performance=avg_perf or 0.0,
            days_of_coverage=(usable or 0) / 1.0,  # Assumes 1 per day
        )

        status.by_send_type[send_type_key] = availability

        # Track critical types (< 3 usable)
        if (usable or 0) < 3:
            status.critical_types.append(send_type_key)

        # Aggregate by category
        if category not in category_totals:
            category_totals[category] = 0
        category_totals[category] += usable or 0

    status.by_category = category_totals
    status.sufficient_coverage = len(status.critical_types) == 0

    logger.debug(
        "Caption pool analyzed",
        extra={
            "creator_id": creator_id,
            "send_types_analyzed": len(status.by_send_type),
            "critical_types": len(status.critical_types),
            "sufficient": status.sufficient_coverage,
        },
    )

    return status


def check_caption_availability(
    schedule_items: List[ScheduleSlot],
    pool: CaptionPoolStatus,
    conn: sqlite3.Connection,
) -> List[ScheduleSlot]:
    """Check and assign captions to schedule slots.

    For each slot, attempts to assign a usable caption. If no caption
    is available, marks the slot as needing manual intervention.

    This function DOES NOT reduce volume - it maintains all slots
    and surfaces gaps for manual resolution.

    Args:
        schedule_items: List of schedule slots to check.
        pool: Caption pool status from get_caption_pool_status().
        conn: Database connection for caption lookup.

    Returns:
        Updated schedule items with caption assignments/flags.
    """
    # Track assigned captions to avoid duplicates within same schedule
    assigned_caption_ids: set = set()

    for item in schedule_items:
        availability = pool.by_send_type.get(item.send_type_key)

        if not availability or availability.usable_captions == 0:
            item.needs_caption = True
            item.caption_note = f"No fresh captions available for {item.send_type_key}"
            continue

        # Try to find an unassigned caption
        caption = _find_best_caption(
            conn,
            pool.creator_id,
            item.send_type_key,
            assigned_caption_ids,
        )

        if caption:
            item.needs_caption = False
            item.caption_id = caption[0]
            assigned_caption_ids.add(caption[0])
        else:
            item.needs_caption = True
            item.caption_note = (
                f"All fresh captions for {item.send_type_key} already assigned"
            )

    return schedule_items


def _find_best_caption(
    conn: sqlite3.Connection,
    creator_id: str,
    send_type_key: str,
    exclude_ids: set,
    min_freshness: float = 30.0,
    min_performance: float = 40.0,
) -> Optional[Tuple[int, float, float]]:
    """Find the best available caption for a send type.

    Searches for usable captions that have not already been assigned,
    prioritizing by caption requirement priority, freshness, and performance.

    Args:
        conn: Database connection.
        creator_id: Creator to find caption for.
        send_type_key: Send type to match.
        exclude_ids: Caption IDs to exclude (already assigned).
        min_freshness: Minimum freshness threshold.
        min_performance: Minimum performance threshold.

    Returns:
        Tuple of (caption_id, freshness_score, performance_score) or None.
    """
    # Build exclude clause - use placeholders for safety
    if exclude_ids:
        exclude_list = ",".join("?" for _ in exclude_ids)
        exclude_clause = f"AND cb.caption_id NOT IN ({exclude_list})"
        params: List[Any] = [
            creator_id,
            send_type_key,
            min_freshness,
            min_performance,
            *exclude_ids,
        ]
    else:
        exclude_clause = ""
        params = [creator_id, send_type_key, min_freshness, min_performance]

    query = f"""
        SELECT cb.caption_id, cb.freshness_score, cb.performance_score
        FROM caption_bank cb
        JOIN send_type_caption_requirements stcr ON cb.caption_type = stcr.caption_type
        JOIN send_types st ON stcr.send_type_id = st.send_type_id
        WHERE cb.creator_id = ?
          AND st.send_type_key = ?
          AND cb.is_active = 1
          AND COALESCE(cb.freshness_score, 100) >= ?
          AND COALESCE(cb.performance_score, 50) >= ?
          {exclude_clause}
        ORDER BY
            stcr.priority ASC,
            cb.freshness_score DESC,
            cb.performance_score DESC
        LIMIT 1
    """

    try:
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return row if row else None
    except sqlite3.Error:
        return None


def get_caption_shortage_report(
    pool: CaptionPoolStatus,
    daily_volume: Dict[str, int],
    days: int = 7,
) -> Dict[str, Dict[str, Any]]:
    """Generate a report of caption shortages for planning.

    Compares required caption volume against available pool to
    identify shortages that need to be addressed.

    Args:
        pool: Caption pool status.
        daily_volume: Expected sends per day by send type.
        days: Number of days to plan for (default 7).

    Returns:
        Dict mapping send_type_key to shortage details including:
        - needed: Total captions needed for the period
        - available: Currently usable captions
        - shortage: Number of additional captions needed
        - status: 'critical', 'insufficient', or 'adequate'
        - message: Human-readable explanation
    """
    report: Dict[str, Dict[str, Any]] = {}

    for send_type_key, daily_count in daily_volume.items():
        needed = daily_count * days
        available = pool.by_send_type.get(send_type_key)

        if not available:
            report[send_type_key] = {
                "needed": needed,
                "available": 0,
                "shortage": needed,
                "status": "critical",
                "message": f"No captions found for {send_type_key}",
            }
        elif available.usable_captions < needed:
            shortage = needed - available.usable_captions
            status = "insufficient" if shortage > needed // 2 else "limited"
            report[send_type_key] = {
                "needed": needed,
                "available": available.usable_captions,
                "shortage": shortage,
                "status": status,
                "message": f"Need {shortage} more captions for {send_type_key}",
            }

    return report


def get_caption_coverage_estimate(
    pool: CaptionPoolStatus,
    daily_volume: Dict[str, int],
) -> Dict[str, float]:
    """Estimate days of coverage per send type.

    Calculates how many days of scheduling each send type can support
    based on current caption availability and daily volume requirements.

    Args:
        pool: Caption pool status.
        daily_volume: Expected sends per day by send type.

    Returns:
        Dict mapping send_type_key to estimated days of coverage.
    """
    coverage: Dict[str, float] = {}

    for send_type_key, daily_count in daily_volume.items():
        if daily_count == 0:
            coverage[send_type_key] = float("inf")
            continue

        available = pool.by_send_type.get(send_type_key)
        if not available:
            coverage[send_type_key] = 0.0
        else:
            coverage[send_type_key] = available.usable_captions / daily_count

    return coverage


def validate_volume_against_captions(
    pool: CaptionPoolStatus,
    volume_config: "VolumeConfig",
    days: int = 7,
) -> VolumeConstraintResult:
    """Validate that a VolumeConfig can be supported by caption pool.

    Compares the category-based volume requirements from VolumeConfig
    against the aggregated caption availability per category to determine
    if the schedule is viable.

    Args:
        pool: Caption pool status from get_caption_pool_status().
        volume_config: Volume configuration to validate.
        days: Number of days to plan for (default 7).

    Returns:
        VolumeConstraintResult with viability assessment and details.

    Example:
        >>> pool = get_caption_pool_status(conn, "creator_123")
        >>> config = VolumeConfig(
        ...     tier=VolumeTier.HIGH,
        ...     revenue_per_day=5,
        ...     engagement_per_day=6,
        ...     retention_per_day=2,
        ...     fan_count=12000,
        ...     page_type="paid"
        ... )
        >>> result = validate_volume_against_captions(pool, config, days=7)
        >>> if not result.is_viable:
        ...     print(result.get_shortage_summary())
    """
    # Calculate requirements for the period
    requirements = {
        "revenue": volume_config.revenue_per_day * days,
        "engagement": volume_config.engagement_per_day * days,
        "retention": volume_config.retention_per_day * days,
    }

    # Get available captions per category
    availability = pool.get_category_availability()

    # Check for shortages
    shortages: Dict[str, Dict[str, Any]] = {}
    recommendations: List[str] = []

    for category, required in requirements.items():
        available = availability.get(category, 0)
        if available < required:
            shortage = required - available
            shortages[category] = {
                "needed": required,
                "available": available,
                "shortage": shortage,
                "status": "critical" if available == 0 else "insufficient",
            }

            # Generate recommendation
            if available == 0:
                recommendations.append(
                    f"Add {category} captions urgently - none available"
                )
            else:
                recommendations.append(
                    f"Add {shortage} more {category} captions "
                    f"(have {available}, need {required})"
                )

    # Add critical send type warnings
    for critical_type in pool.critical_types:
        category = get_send_type_category(critical_type)
        recommendations.append(
            f"Warning: {critical_type} has fewer than 3 usable captions"
        )

    is_viable = len(shortages) == 0

    logger.debug(
        "Volume validation complete",
        extra={
            "creator_id": pool.creator_id,
            "is_viable": is_viable,
            "shortages": len(shortages),
            "requirements": requirements,
            "availability": availability,
        },
    )

    return VolumeConstraintResult(
        is_viable=is_viable,
        pool_status=pool,
        category_requirements=requirements,
        category_availability=availability,
        shortages=shortages,
        recommendations=recommendations,
        days_analyzed=days,
    )


class CaptionPoolAnalyzer:
    """High-level analyzer for caption pool management.

    Provides convenient methods for analyzing caption availability
    and generating reports for schedule planning.

    Attributes:
        db_path: Path to the SQLite database.
        min_freshness: Minimum freshness score threshold.
        min_performance: Minimum performance score threshold.

    Example:
        analyzer = CaptionPoolAnalyzer("/path/to/db.sqlite")
        status = analyzer.analyze("creator_123")

        if not status.sufficient_coverage:
            print(f"Critical types: {status.critical_types}")
    """

    def __init__(
        self,
        db_path: str,
        min_freshness: float = 30.0,
        min_performance: float = 40.0,
    ) -> None:
        """Initialize CaptionPoolAnalyzer.

        Args:
            db_path: Path to the SQLite database file.
            min_freshness: Minimum freshness score threshold.
            min_performance: Minimum performance score threshold.
        """
        self.db_path = db_path
        self.min_freshness = min_freshness
        self.min_performance = min_performance

    def analyze(self, creator_id: str) -> CaptionPoolStatus:
        """Analyze caption pool for a creator.

        Args:
            creator_id: Creator to analyze.

        Returns:
            CaptionPoolStatus with detailed availability analysis.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            return get_caption_pool_status(
                conn,
                creator_id,
                self.min_freshness,
                self.min_performance,
            )
        finally:
            conn.close()

    def check_schedule(
        self,
        creator_id: str,
        schedule_items: List[ScheduleSlot],
    ) -> List[ScheduleSlot]:
        """Check and annotate schedule items with caption availability.

        Args:
            creator_id: Creator the schedule is for.
            schedule_items: List of schedule slots to check.

        Returns:
            Updated schedule items with caption assignments/flags.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            pool = get_caption_pool_status(
                conn,
                creator_id,
                self.min_freshness,
                self.min_performance,
            )
            return check_caption_availability(schedule_items, pool, conn)
        finally:
            conn.close()

    def get_shortage_report(
        self,
        creator_id: str,
        daily_volume: Dict[str, int],
        days: int = 7,
    ) -> Dict[str, Dict[str, Any]]:
        """Generate shortage report for planning.

        Args:
            creator_id: Creator to analyze.
            daily_volume: Expected sends per day by send type.
            days: Number of days to plan for.

        Returns:
            Dict mapping send_type_key to shortage details.
        """
        pool = self.analyze(creator_id)
        return get_caption_shortage_report(pool, daily_volume, days)

    def validate_volume_config(
        self,
        creator_id: str,
        volume_config: "VolumeConfig",
        days: int = 7,
    ) -> VolumeConstraintResult:
        """Validate a VolumeConfig against caption pool availability.

        Integrates with the dynamic volume calculator by validating that
        a computed VolumeConfig can be supported by the available caption pool.

        Args:
            creator_id: Creator to analyze.
            volume_config: Volume configuration from calculate_dynamic_volume().
            days: Number of days to plan for.

        Returns:
            VolumeConstraintResult with viability assessment.

        Example:
            >>> from python.volume import calculate_dynamic_volume, PerformanceContext
            >>> context = PerformanceContext(fan_count=12000, page_type="paid")
            >>> volume = calculate_dynamic_volume(context)
            >>>
            >>> analyzer = CaptionPoolAnalyzer("/path/to/db.sqlite")
            >>> result = analyzer.validate_volume_config("creator_123", volume)
            >>> if not result.is_viable:
            ...     print(result.get_shortage_summary())
        """
        pool = self.analyze(creator_id)
        return validate_volume_against_captions(pool, volume_config, days)

    def get_coverage_estimate(
        self,
        creator_id: str,
        daily_volume: Dict[str, int],
    ) -> Dict[str, float]:
        """Estimate days of coverage per send type.

        Convenience wrapper around get_caption_coverage_estimate.

        Args:
            creator_id: Creator to analyze.
            daily_volume: Expected sends per day by send type.

        Returns:
            Dict mapping send_type_key to estimated days of coverage.
        """
        pool = self.analyze(creator_id)
        return get_caption_coverage_estimate(pool, daily_volume)


__all__ = [
    # Dataclasses
    "CaptionAvailability",
    "CaptionPoolStatus",
    "ScheduleSlot",
    "VolumeConstraintResult",
    # Main analyzer class
    "CaptionPoolAnalyzer",
    # Core functions
    "get_caption_pool_status",
    "check_caption_availability",
    "get_caption_shortage_report",
    "get_caption_coverage_estimate",
    # VolumeConfig integration
    "validate_volume_against_captions",
    # Send type category mapping
    "SEND_TYPE_CATEGORIES",
    "get_send_type_category",
]
