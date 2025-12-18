"""
Wave 2 Timing Saga Coordinator.

Implements the saga pattern for multi-step timing operations with automatic
rollback on failure. Coordinates:
1. PPV rotation pattern updates
2. Schedule validation
3. Followup generation
4. Jitter application

If any step fails, all previous steps are compensated in reverse order,
ensuring atomicity of timing operations.

Usage:
    saga = Wave2TimingSaga(creator_id="abc123")
    result = await saga.execute(daily_schedule)

    if result.status == SagaStatus.COMPLETED:
        print("All timing operations completed successfully")
    elif result.status == SagaStatus.ROLLED_BACK:
        print(f"Operation failed and rolled back: {result.error}")
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from python.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Saga Status Enum
# =============================================================================


class SagaStatus(Enum):
    """Status states for saga execution.

    States:
        PENDING: Saga created but not yet started
        IN_PROGRESS: Saga is actively executing steps
        COMPLETED: All steps completed successfully
        COMPENSATING: Failure detected, executing compensations
        FAILED: Compensations failed or could not complete
        ROLLED_BACK: All compensations executed successfully
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# =============================================================================
# Saga Step Dataclass
# =============================================================================


@dataclass
class SagaStep:
    """A single step in the saga with its compensation action.

    Each step represents an atomic operation that may have side effects.
    If the step succeeds, its compensation is pushed onto the compensation
    stack. If any subsequent step fails, compensations are executed in
    reverse order.

    Attributes:
        name: Human-readable step identifier for logging
        action: Callable that performs the step's work
        compensation: Callable that undoes the step's work
        timeout_seconds: Maximum time allowed for step execution
    """

    name: str
    action: Callable[[], Any]
    compensation: Callable[[], Any]
    timeout_seconds: float = 30.0


# =============================================================================
# Saga Result Dataclass
# =============================================================================


@dataclass
class SagaResult:
    """Result of saga execution.

    Captures comprehensive information about saga execution including
    timing, completed steps, and any errors encountered.

    Attributes:
        status: Final status of the saga
        completed_steps: List of step names that completed successfully
        failed_step: Name of the step that failed (if any)
        error: Error message describing the failure (if any)
        compensation_errors: Errors encountered during compensation
        execution_time_ms: Total execution time in milliseconds
    """

    status: SagaStatus
    completed_steps: list[str]
    failed_step: Optional[str] = None
    error: Optional[str] = None
    compensation_errors: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


# =============================================================================
# Saga Step Error Exception
# =============================================================================


class SagaStepError(Exception):
    """Raised when a saga step fails.

    This exception triggers the compensation process. It captures
    information about which step failed and why.

    Attributes:
        step_name: Name of the step that failed
        original_error: The underlying exception that caused the failure
    """

    def __init__(
        self,
        message: str,
        step_name: Optional[str] = None,
        original_error: Optional[Exception] = None
    ) -> None:
        """Initialize SagaStepError.

        Args:
            message: Human-readable error description
            step_name: Name of the step that failed
            original_error: The underlying exception
        """
        super().__init__(message)
        self.step_name = step_name
        self.original_error = original_error


# =============================================================================
# Wave2TimingSaga Class
# =============================================================================


class Wave2TimingSaga:
    """Coordinates timing operations with automatic rollback.

    Implements the saga pattern for multi-step timing operations:
    1. Rotation pattern update - Apply PPV rotation pattern
    2. Schedule validation - Validate schedule constraints
    3. Followup generation - Generate PPV followups
    4. Jitter application - Apply time jitter to schedule items

    If any step fails, all previous steps are compensated in reverse order.

    Example:
        saga = Wave2TimingSaga("creator_123")
        result = await saga.execute(daily_schedule)

        if result.status == SagaStatus.COMPLETED:
            # Schedule is ready for use
            pass
        elif result.status == SagaStatus.ROLLED_BACK:
            # Handle failure, original state restored
            logger.error(f"Saga failed: {result.error}")

    Attributes:
        creator_id: Creator identifier for timing operations
        completed_steps: Steps that have been executed successfully
        compensation_stack: LIFO stack of compensation functions
        status: Current saga status
    """

    # Round minutes to avoid for jitter
    ROUND_MINUTES: frozenset[int] = frozenset({0, 15, 30, 45})

    # Valid PPV styles for rotation
    PPV_STYLES: tuple[str, ...] = ("solo", "bundle", "winner", "sextape")

    def __init__(self, creator_id: str) -> None:
        """Initialize the timing saga.

        Args:
            creator_id: Creator identifier for timing operations
        """
        self.creator_id = creator_id
        self.completed_steps: list[str] = []
        self.compensation_stack: list[Callable[[], Any]] = []
        self.status = SagaStatus.PENDING
        self._original_state: dict[str, Any] = {}
        self._generated_followups: list[dict[str, Any]] = []

        logger.info(
            "Wave2TimingSaga initialized",
            extra={"creator_id": creator_id}
        )

    async def execute(self, daily_schedule: list[dict[str, Any]]) -> SagaResult:
        """Execute the timing saga with full compensation support.

        Runs all four timing steps in sequence. If any step fails,
        all previously completed steps are compensated in reverse order.

        Args:
            daily_schedule: The schedule to process. Each item should have
                at minimum 'id' and 'scheduled_time' fields.

        Returns:
            SagaResult with status and execution details

        Raises:
            No exceptions are raised - all errors are captured in SagaResult
        """
        start_time = datetime.now()

        logger.info(
            "Starting Wave2TimingSaga execution",
            extra={
                "creator_id": self.creator_id,
                "schedule_items": len(daily_schedule)
            }
        )

        # Define saga steps
        steps = [
            SagaStep(
                name="rotation_update",
                action=lambda: self._apply_rotation(daily_schedule),
                compensation=lambda: self._rollback_rotation(),
                timeout_seconds=30.0
            ),
            SagaStep(
                name="schedule_validation",
                action=lambda: self._validate_schedule(daily_schedule),
                compensation=lambda: None,  # Validation has no side effects
                timeout_seconds=15.0
            ),
            SagaStep(
                name="followup_generation",
                action=lambda: self._generate_followups(daily_schedule),
                compensation=lambda: self._remove_followups(daily_schedule),
                timeout_seconds=30.0
            ),
            SagaStep(
                name="jitter_application",
                action=lambda: self._apply_jitter(daily_schedule),
                compensation=lambda: self._restore_original_times(daily_schedule),
                timeout_seconds=15.0
            ),
        ]

        self.status = SagaStatus.IN_PROGRESS

        try:
            for step in steps:
                try:
                    # Execute step with timeout using asyncio.to_thread for sync ops
                    await asyncio.wait_for(
                        asyncio.to_thread(step.action),
                        timeout=step.timeout_seconds
                    )
                    self.completed_steps.append(step.name)
                    self.compensation_stack.append(step.compensation)

                    logger.debug(
                        f"Saga step completed: {step.name}",
                        extra={
                            "creator_id": self.creator_id,
                            "step": step.name
                        }
                    )

                except asyncio.TimeoutError:
                    raise SagaStepError(
                        f"Step {step.name} timed out after {step.timeout_seconds}s",
                        step_name=step.name
                    )
                except SagaStepError:
                    raise
                except Exception as e:
                    raise SagaStepError(
                        f"Step {step.name} failed: {str(e)}",
                        step_name=step.name,
                        original_error=e
                    )

            # All steps completed successfully
            self.status = SagaStatus.COMPLETED
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "Wave2TimingSaga completed successfully",
                extra={
                    "creator_id": self.creator_id,
                    "completed_steps": self.completed_steps,
                    "execution_time_ms": execution_time
                }
            )

            return SagaResult(
                status=SagaStatus.COMPLETED,
                completed_steps=self.completed_steps.copy(),
                execution_time_ms=execution_time
            )

        except SagaStepError as e:
            logger.warning(
                f"Saga step failed, initiating compensation: {e}",
                extra={
                    "creator_id": self.creator_id,
                    "failed_step": e.step_name,
                    "completed_steps": self.completed_steps
                }
            )
            return await self._compensate(str(e), start_time)

    async def _compensate(
        self,
        error: str,
        start_time: datetime
    ) -> SagaResult:
        """Execute compensation actions in reverse order.

        Runs through the compensation stack LIFO, attempting to undo
        all successfully completed steps.

        Args:
            error: Error message that triggered compensation
            start_time: When saga execution started

        Returns:
            SagaResult with rollback status and any compensation errors
        """
        self.status = SagaStatus.COMPENSATING
        compensation_errors: list[str] = []
        failed_step = self.completed_steps[-1] if self.completed_steps else None

        logger.info(
            "Executing saga compensations",
            extra={
                "creator_id": self.creator_id,
                "compensations_to_execute": len(self.compensation_stack)
            }
        )

        # Execute compensations in reverse order (LIFO)
        while self.compensation_stack:
            compensation = self.compensation_stack.pop()
            try:
                await asyncio.to_thread(compensation)
            except Exception as comp_error:
                error_msg = f"Compensation failed: {str(comp_error)}"
                compensation_errors.append(error_msg)
                logger.error(
                    error_msg,
                    extra={"creator_id": self.creator_id}
                )

        # Determine final status
        if compensation_errors:
            self.status = SagaStatus.FAILED
        else:
            self.status = SagaStatus.ROLLED_BACK

        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Saga compensation complete: {self.status.value}",
            extra={
                "creator_id": self.creator_id,
                "status": self.status.value,
                "compensation_errors": len(compensation_errors),
                "execution_time_ms": execution_time
            }
        )

        return SagaResult(
            status=self.status,
            completed_steps=self.completed_steps.copy(),
            failed_step=failed_step,
            error=error,
            compensation_errors=compensation_errors,
            execution_time_ms=execution_time
        )

    # =========================================================================
    # Step 1: Rotation Pattern
    # =========================================================================

    def _apply_rotation(self, schedule: list[dict[str, Any]]) -> None:
        """Step 1: Apply PPV rotation pattern to schedule.

        Updates PPV items in the schedule with the appropriate style
        based on the current rotation pattern for this creator.

        Args:
            schedule: Schedule items to update
        """
        # Save original rotation state for rollback
        self._original_state["rotation"] = self._get_current_rotation()

        # Get rotation pattern for this creator
        pattern = self._get_rotation_pattern()

        # Apply pattern to PPV items
        ppv_index = 0
        for item in schedule:
            if item.get("is_ppv", False) or item.get("category") == "revenue":
                if "ppv_style" not in item or item["ppv_style"] is None:
                    item["ppv_style"] = pattern[ppv_index % len(pattern)]
                    ppv_index += 1

        logger.debug(
            "Applied rotation pattern",
            extra={
                "creator_id": self.creator_id,
                "pattern": pattern,
                "ppv_items_updated": ppv_index
            }
        )

    def _rollback_rotation(self) -> None:
        """Compensate rotation by restoring original state."""
        if "rotation" in self._original_state:
            self._restore_rotation(self._original_state["rotation"])
            logger.debug(
                "Rolled back rotation state",
                extra={"creator_id": self.creator_id}
            )

    def _get_current_rotation(self) -> dict[str, Any]:
        """Get current rotation state.

        Returns:
            Current rotation state dictionary
        """
        # In production, this would load from database
        # For now, return empty state
        return {
            "pattern": list(self.PPV_STYLES),
            "pattern_start_date": datetime.now().isoformat(),
            "days_on_pattern": 0
        }

    def _restore_rotation(self, state: dict[str, Any]) -> None:
        """Restore rotation state.

        Args:
            state: State to restore
        """
        # In production, this would save to database
        logger.debug(
            "Restored rotation state",
            extra={"creator_id": self.creator_id, "state": state}
        )

    def _get_rotation_pattern(self) -> list[str]:
        """Get the current PPV rotation pattern for this creator.

        Uses deterministic seeding based on creator_id and date
        to ensure consistent patterns.

        Returns:
            List of PPV styles in rotation order
        """
        # Create deterministic seed
        seed_string = f"{self.creator_id}:{datetime.now().strftime('%Y-%m-%d')}"
        seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        # Standard patterns
        patterns = [
            ["solo", "bundle", "winner", "sextape"],
            ["winner", "solo", "sextape", "bundle"],
            ["bundle", "sextape", "solo", "winner"],
            ["sextape", "winner", "bundle", "solo"],
        ]

        return rng.choice(patterns)

    # =========================================================================
    # Step 2: Schedule Validation
    # =========================================================================

    def _validate_schedule(self, schedule: list[dict[str, Any]]) -> None:
        """Step 2: Validate schedule constraints.

        Checks for same-style back-to-back violations and other
        timing constraints. This step has no side effects.

        Args:
            schedule: Schedule items to validate

        Raises:
            SagaStepError: If validation fails
        """
        result = self._validate_no_consecutive_same_style(schedule)
        if not result["is_valid"]:
            raise SagaStepError(
                f"Validation failed: {result['errors']}",
                step_name="schedule_validation"
            )

        logger.debug(
            "Schedule validation passed",
            extra={"creator_id": self.creator_id}
        )

    def _validate_no_consecutive_same_style(
        self,
        daily_schedule: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Validate no consecutive same-style PPVs.

        Prevents winner/winner or bundle/bundle back-to-back scheduling.

        Args:
            daily_schedule: Schedule items to validate

        Returns:
            Dict with is_valid and errors fields
        """
        ppv_items = [
            item for item in daily_schedule
            if item.get("is_ppv", False) or item.get("category") == "revenue"
        ]

        if len(ppv_items) < 2:
            return {"is_valid": True, "errors": []}

        errors = []

        # Check consecutive same-style
        for i in range(len(ppv_items) - 1):
            current_style = ppv_items[i].get("ppv_style")
            next_style = ppv_items[i + 1].get("ppv_style")

            if (
                current_style == next_style
                and current_style in ("winner", "bundle")
            ):
                errors.append(
                    f"Two {current_style} PPVs back-to-back at positions {i} and {i+1}"
                )

        # Check AM/PM distribution
        style_by_period: dict[str, list[str]] = {"AM": [], "PM": []}
        for item in ppv_items:
            scheduled_time = item.get("scheduled_time")
            if isinstance(scheduled_time, str):
                try:
                    hour = int(scheduled_time.split(":")[0])
                except (ValueError, IndexError):
                    hour = 12
            elif isinstance(scheduled_time, datetime):
                hour = scheduled_time.hour
            else:
                hour = 12

            period = "AM" if hour < 12 else "PM"
            style = item.get("ppv_style", "unknown")
            style_by_period[period].append(style)

        from collections import Counter

        for period, styles in style_by_period.items():
            style_counts = Counter(styles)
            for style, count in style_counts.items():
                if count > 1 and style in ("winner", "bundle"):
                    errors.append(
                        f"Multiple {style} PPVs in {period} period ({count} found)"
                    )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Step 3: Followup Generation
    # =========================================================================

    def _generate_followups(self, schedule: list[dict[str, Any]]) -> None:
        """Step 3: Generate PPV followups.

        Creates followup messages for PPV items within the 15-45 minute
        optimal window.

        Args:
            schedule: Schedule items to process
        """
        self._original_state["followups"] = []
        self._generated_followups = []

        for item in schedule:
            if item.get("is_ppv", False) or item.get("send_type_key") in (
                "ppv_unlock", "ppv_wall", "bundle", "flash_bundle"
            ):
                followup = self._create_followup(item)
                if followup:
                    self._generated_followups.append(followup)
                    schedule.append(followup)
                    self._original_state["followups"].append(followup.get("id"))

        logger.debug(
            "Generated followups",
            extra={
                "creator_id": self.creator_id,
                "followups_created": len(self._generated_followups)
            }
        )

    def _remove_followups(self, schedule: list[dict[str, Any]]) -> None:
        """Compensate by removing generated followups.

        Args:
            schedule: Schedule to remove followups from
        """
        followup_ids = self._original_state.get("followups", [])
        # Remove items with matching IDs
        schedule[:] = [
            item for item in schedule
            if item.get("id") not in followup_ids
        ]

        logger.debug(
            "Removed generated followups",
            extra={
                "creator_id": self.creator_id,
                "followups_removed": len(followup_ids)
            }
        )

    def _create_followup(self, parent_item: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Create a followup for a PPV item.

        Args:
            parent_item: The parent PPV item

        Returns:
            Followup item dict or None if cannot create
        """
        parent_time = parent_item.get("scheduled_time")
        if not parent_time:
            return None

        # Parse parent time
        if isinstance(parent_time, str):
            try:
                parent_dt = datetime.strptime(parent_time, "%H:%M")
                # Set to today
                parent_dt = parent_dt.replace(
                    year=datetime.now().year,
                    month=datetime.now().month,
                    day=datetime.now().day
                )
            except ValueError:
                try:
                    parent_dt = datetime.fromisoformat(parent_time)
                except ValueError:
                    return None
        elif isinstance(parent_time, datetime):
            parent_dt = parent_time
        else:
            return None

        # Generate followup time (15-45 minutes after parent)
        followup_dt = self._schedule_followup_time(parent_dt)

        # Create followup item
        followup_id = f"followup_{parent_item.get('id', hash(str(parent_item)))}"

        return {
            "id": followup_id,
            "send_type_key": "ppv_followup",
            "scheduled_time": followup_dt.strftime("%H:%M"),
            "scheduled_date": parent_item.get("scheduled_date", datetime.now().strftime("%Y-%m-%d")),
            "parent_id": parent_item.get("id"),
            "category": "retention",
            "priority": 2,
            "is_followup": True
        }

    def _schedule_followup_time(self, parent_time: datetime) -> datetime:
        """Schedule followup within 15-45 minute window.

        Uses truncated normal distribution centered at 28 minutes
        for natural-feeling timing.

        Args:
            parent_time: Parent PPV time

        Returns:
            Followup datetime
        """
        # Create deterministic seed
        seed_string = f"{self.creator_id}:{parent_time.isoformat()}"
        seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        # Generate offset using truncated normal distribution
        # Mean: 28 minutes (sweet spot), StdDev: 8 minutes
        offset_minutes = self._truncated_normal_sample(
            rng, mean=28, std_dev=8, min_val=15, max_val=45
        )

        return parent_time + timedelta(minutes=offset_minutes)

    def _truncated_normal_sample(
        self,
        rng: random.Random,
        mean: float,
        std_dev: float,
        min_val: float,
        max_val: float,
        max_attempts: int = 100
    ) -> int:
        """Generate sample from truncated normal distribution.

        Args:
            rng: Random number generator
            mean: Mean of distribution
            std_dev: Standard deviation
            min_val: Minimum value
            max_val: Maximum value
            max_attempts: Maximum rejection sampling attempts

        Returns:
            Integer sample within [min_val, max_val]
        """
        import math

        for _ in range(max_attempts):
            # Box-Muller transform
            u1 = rng.random()
            u2 = rng.random()
            z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
            sample = mean + z * std_dev

            if min_val <= sample <= max_val:
                return round(sample)

        # Fallback to uniform if rejection sampling fails
        return rng.randint(int(min_val), int(max_val))

    # =========================================================================
    # Step 4: Jitter Application
    # =========================================================================

    def _apply_jitter(self, schedule: list[dict[str, Any]]) -> None:
        """Step 4: Apply time jitter to all items.

        Adds random time offset to each item while avoiding round
        minutes (:00, :15, :30, :45) for organic appearance.

        Args:
            schedule: Schedule items to jitter
        """
        # Save original times for rollback
        self._original_state["original_times"] = {}

        for item in schedule:
            item_id = item.get("id", id(item))
            original_time = item.get("scheduled_time")

            if original_time:
                self._original_state["original_times"][item_id] = original_time

                # Parse time
                if isinstance(original_time, str):
                    try:
                        time_dt = datetime.strptime(original_time, "%H:%M")
                    except ValueError:
                        continue
                elif isinstance(original_time, datetime):
                    time_dt = original_time
                else:
                    continue

                # Apply jitter
                jittered_dt = self._apply_time_jitter(time_dt)
                item["scheduled_time"] = jittered_dt.strftime("%H:%M")

        logger.debug(
            "Applied jitter to schedule",
            extra={
                "creator_id": self.creator_id,
                "items_jittered": len(self._original_state["original_times"])
            }
        )

    def _restore_original_times(self, schedule: list[dict[str, Any]]) -> None:
        """Compensate by restoring original times.

        Args:
            schedule: Schedule to restore
        """
        original_times = self._original_state.get("original_times", {})

        for item in schedule:
            item_id = item.get("id", id(item))
            if item_id in original_times:
                item["scheduled_time"] = original_times[item_id]

        logger.debug(
            "Restored original times",
            extra={
                "creator_id": self.creator_id,
                "items_restored": len(original_times)
            }
        )

    def _apply_time_jitter(self, base_time: datetime) -> datetime:
        """Apply deterministic jitter avoiding round minutes.

        Args:
            base_time: Base scheduled time

        Returns:
            Jittered datetime avoiding :00, :15, :30, :45
        """
        # Create deterministic seed
        seed_string = f"{self.creator_id}:{base_time.strftime('%Y-%m-%d:%H:%M')}"
        seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        base_minute = base_time.minute

        # Generate jitter offset in range [-7, +8] avoiding round minutes
        valid_offsets = []
        for offset in range(-7, 9):
            resulting_minute = (base_minute + offset) % 60
            if resulting_minute not in self.ROUND_MINUTES:
                valid_offsets.append(offset)

        if not valid_offsets:
            # Edge case: all offsets land on round minutes (shouldn't happen)
            offset = 1 if (base_minute + 1) % 60 not in self.ROUND_MINUTES else 2
        else:
            offset = rng.choice(valid_offsets)

        return base_time + timedelta(minutes=offset)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "SagaStatus",
    "SagaStep",
    "SagaResult",
    "SagaStepError",
    "Wave2TimingSaga",
]
