"""
Timing Metrics and Observability for Schedule Generation.

Provides structured logging for timing-related events during schedule
generation, including rotation changes, followup scheduling, jitter
application, validation results, and saga executions.

This module enables comprehensive observability into the scheduling
pipeline's timing decisions for debugging, analytics, and optimization.

Usage:
    from python.orchestration.timing_metrics import TimingMetrics

    # Log a rotation pattern change
    TimingMetrics.log_rotation_change(
        creator_id="abc123",
        old_pattern="PPBE",
        new_pattern="BPPE",
        method="performance_based",
        days_on_previous=7
    )
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from python.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class TimingEvent:
    """Structured timing event for observability.

    Captures all relevant context for a timing-related event during
    schedule generation. Events are logged as JSON for structured
    querying and analysis.

    Attributes:
        event_type: Type of timing event (e.g., 'rotation_change', 'followup_scheduled')
        creator_id: Creator identifier for the event
        timestamp: ISO 8601 timestamp when event occurred
        details: Event-specific details dictionary
        duration_ms: Optional duration in milliseconds for timed operations
    """

    event_type: str
    creator_id: str
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None

    @classmethod
    def create(
        cls,
        event_type: str,
        creator_id: str,
        details: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> "TimingEvent":
        """Factory method to create a TimingEvent with current timestamp.

        Args:
            event_type: Type of timing event
            creator_id: Creator identifier
            details: Event-specific details
            duration_ms: Optional duration in milliseconds

        Returns:
            TimingEvent with populated timestamp
        """
        return cls(
            event_type=event_type,
            creator_id=creator_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=details or {},
            duration_ms=duration_ms,
        )


class TimingMetrics:
    """Static methods for logging timing-related events.

    Provides a consistent interface for logging structured timing events
    throughout the schedule generation pipeline. All events are logged
    as JSON with the prefix 'TIMING_EVENT:' for easy parsing.

    Event Types:
        - rotation_change: Pattern rotation strategy changed
        - followup_scheduled: PPV followup scheduled
        - jitter_applied: Time jitter applied to schedule item
        - validation_result: Schedule validation completed
        - saga_execution: Saga-based schedule generation completed
    """

    @staticmethod
    def _log_event(event: TimingEvent) -> None:
        """Internal method to log a timing event as JSON.

        Args:
            event: The TimingEvent to log
        """
        logger.info(f"TIMING_EVENT: {json.dumps(asdict(event))}")

    @staticmethod
    def log_rotation_change(
        creator_id: str,
        old_pattern: str,
        new_pattern: str,
        method: str,
        days_on_previous: int,
    ) -> TimingEvent:
        """Log a rotation pattern change event.

        Records when a creator's send type rotation pattern changes,
        including the method used to determine the new pattern and
        how long the previous pattern was active.

        Args:
            creator_id: Creator identifier
            old_pattern: Previous rotation pattern (e.g., 'PPBE')
            new_pattern: New rotation pattern (e.g., 'BPPE')
            method: Method used to determine rotation ('performance_based',
                'scheduled_rotation', 'manual_override', 'initial_assignment')
            days_on_previous: Number of days the previous pattern was active

        Returns:
            The logged TimingEvent for testing/verification
        """
        diversity_score = TimingMetrics._calculate_diversity(old_pattern, new_pattern)

        event = TimingEvent.create(
            event_type="rotation_change",
            creator_id=creator_id,
            details={
                "old_pattern": old_pattern,
                "new_pattern": new_pattern,
                "method": method,
                "days_on_previous": days_on_previous,
                "diversity_score": diversity_score,
            },
        )
        TimingMetrics._log_event(event)
        return event

    @staticmethod
    def log_followup_scheduled(
        creator_id: str,
        parent_time: str,
        followup_time: str,
        gap_minutes: int,
        ppv_type: str,
    ) -> TimingEvent:
        """Log a PPV followup scheduling event.

        Records when a PPV followup is scheduled, including timing
        analysis to identify suboptimal followup windows.

        Optimal window: 15-45 minutes after parent PPV
        - < 20 min: 'early' (may seem pushy)
        - > 40 min: 'late' (reduced conversion)
        - 20-40 min: 'optimal'

        Args:
            creator_id: Creator identifier
            parent_time: Parent PPV scheduled time (HH:MM format)
            followup_time: Followup scheduled time (HH:MM format)
            gap_minutes: Minutes between parent and followup
            ppv_type: Type of PPV ('ppv_unlock', 'ppv_wall', 'bundle', etc.)

        Returns:
            The logged TimingEvent for testing/verification
        """
        # Determine window position
        is_optimal_window = 15 <= gap_minutes <= 45

        if gap_minutes < 20:
            window_position = "early"
        elif gap_minutes > 40:
            window_position = "late"
        else:
            window_position = "optimal"

        event = TimingEvent.create(
            event_type="followup_scheduled",
            creator_id=creator_id,
            details={
                "parent_time": parent_time,
                "followup_time": followup_time,
                "gap_minutes": gap_minutes,
                "ppv_type": ppv_type,
                "is_optimal_window": is_optimal_window,
                "window_position": window_position,
            },
        )

        # Log at appropriate level based on window optimality
        if not is_optimal_window:
            logger.warning(
                f"TIMING_EVENT: {json.dumps(asdict(event))} - "
                f"Followup outside optimal window ({window_position})"
            )
        else:
            TimingMetrics._log_event(event)

        return event

    @staticmethod
    def log_jitter_applied(
        creator_id: str,
        original_time: str,
        jittered_time: str,
        send_type: str,
    ) -> TimingEvent:
        """Log a jitter application event.

        Records when time jitter is applied to a schedule item,
        flagging errors when jitter lands on round minutes that
        indicate potential algorithm issues.

        Round minutes (:00, :15, :30, :45) suggest jitter may not
        be properly randomizing or may be hitting modulo boundaries.

        Args:
            creator_id: Creator identifier
            original_time: Original scheduled time (HH:MM format)
            jittered_time: Time after jitter applied (HH:MM format)
            send_type: The send type being jittered

        Returns:
            The logged TimingEvent for testing/verification
        """
        # Parse times to extract minutes
        try:
            original_minutes = int(original_time.split(":")[1])
            jittered_minutes = int(jittered_time.split(":")[1])
            jitter_delta = jittered_minutes - original_minutes
        except (IndexError, ValueError):
            original_minutes = 0
            jittered_minutes = 0
            jitter_delta = 0

        # Check for round minute landing (potential algorithm issue)
        is_round_minute = jittered_minutes in (0, 15, 30, 45)

        event = TimingEvent.create(
            event_type="jitter_applied",
            creator_id=creator_id,
            details={
                "original_time": original_time,
                "jittered_time": jittered_time,
                "send_type": send_type,
                "jitter_delta_minutes": jitter_delta,
                "is_round_minute": is_round_minute,
            },
        )

        # Log error for round minute landing (indicates potential jitter issue)
        if is_round_minute:
            logger.error(
                f"TIMING_EVENT: {json.dumps(asdict(event))} - "
                f"Jitter landed on round minute :{jittered_minutes:02d}"
            )
        else:
            TimingMetrics._log_event(event)

        return event

    @staticmethod
    def log_validation_result(
        creator_id: str,
        validation_type: str,
        is_valid: bool,
        errors: list[str],
        repairs_applied: list[str],
    ) -> TimingEvent:
        """Log a schedule validation result.

        Records the outcome of a validation pass, including any
        errors found and repairs that were automatically applied.

        Args:
            creator_id: Creator identifier
            validation_type: Type of validation ('timing', 'diversity',
                'channel', 'gap_compliance', 'full')
            is_valid: Whether validation passed
            errors: List of validation error messages
            repairs_applied: List of automatic repairs that were applied

        Returns:
            The logged TimingEvent for testing/verification
        """
        event = TimingEvent.create(
            event_type="validation_result",
            creator_id=creator_id,
            details={
                "validation_type": validation_type,
                "is_valid": is_valid,
                "error_count": len(errors),
                "errors": errors,
                "repair_count": len(repairs_applied),
                "repairs_applied": repairs_applied,
            },
        )

        # Log warning for validation failures
        if not is_valid:
            logger.warning(
                f"TIMING_EVENT: {json.dumps(asdict(event))} - "
                f"Validation failed with {len(errors)} error(s)"
            )
        else:
            TimingMetrics._log_event(event)

        return event

    @staticmethod
    def log_saga_execution(
        creator_id: str,
        saga_result: str,
        schedule_item_count: int,
        duration_ms: float | None = None,
    ) -> TimingEvent:
        """Log a saga execution result.

        Records the outcome of a saga-based schedule generation,
        including the number of items generated and execution time.

        Args:
            creator_id: Creator identifier
            saga_result: Saga outcome ('success', 'partial_success',
                'rollback', 'failed', 'compensated')
            schedule_item_count: Number of schedule items generated
            duration_ms: Optional execution duration in milliseconds

        Returns:
            The logged TimingEvent for testing/verification
        """
        is_success = saga_result in ("success", "partial_success")

        event = TimingEvent.create(
            event_type="saga_execution",
            creator_id=creator_id,
            details={
                "saga_result": saga_result,
                "schedule_item_count": schedule_item_count,
                "is_success": is_success,
            },
            duration_ms=duration_ms,
        )

        # Log error for saga failures
        if not is_success:
            logger.error(
                f"TIMING_EVENT: {json.dumps(asdict(event))} - "
                f"Saga execution failed: {saga_result}"
            )
        else:
            TimingMetrics._log_event(event)

        return event

    @staticmethod
    def _calculate_diversity(old_pattern: str, new_pattern: str) -> float:
        """Calculate diversity score between two rotation patterns.

        Measures how different the new pattern is from the old pattern.
        Higher scores indicate more variety in the rotation change.

        Score = (number of position differences) / (pattern length)

        Args:
            old_pattern: Previous rotation pattern string
            new_pattern: New rotation pattern string

        Returns:
            Diversity score from 0.0 (identical) to 1.0 (completely different)

        Examples:
            >>> TimingMetrics._calculate_diversity("PPBE", "PPBE")
            0.0
            >>> TimingMetrics._calculate_diversity("PPBE", "EBPP")
            1.0
            >>> TimingMetrics._calculate_diversity("PPBE", "BPBE")
            0.5
        """
        if not old_pattern or not new_pattern:
            return 0.0

        # Use the shorter pattern length for comparison
        pattern_length = min(len(old_pattern), len(new_pattern))
        if pattern_length == 0:
            return 0.0

        # Count position differences
        differences = 0
        for i in range(pattern_length):
            if old_pattern[i] != new_pattern[i]:
                differences += 1

        # Add difference count for length mismatch
        length_diff = abs(len(old_pattern) - len(new_pattern))
        differences += length_diff

        # Calculate score using total length
        total_length = max(len(old_pattern), len(new_pattern))
        return differences / total_length


__all__ = [
    "TimingEvent",
    "TimingMetrics",
]
