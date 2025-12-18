# WAVE 2: TIMING & SCHEDULING PRECISION

**Status:** Ready for Execution (after Wave 1)
**Duration:** Weeks 3-4
**Priority:** P0/P1
**Expected Impact:** +10-50% conversion through timing optimization

---

## FORMAL STATE MACHINE DEFINITION

The rotation system operates as a finite state machine with well-defined states and transitions:

```python
from enum import Enum
from typing import Dict, List

class RotationState(Enum):
    """Valid states for the PPV rotation state machine."""
    INITIALIZING = "initializing"      # Loading or creating initial state
    PATTERN_ACTIVE = "pattern_active"  # Currently using a rotation pattern
    ROTATION_PENDING = "rotation_pending"  # Day 3, awaiting rotation decision
    ROTATING = "rotating"              # Actively changing to new pattern
    PATTERN_EXHAUSTED = "pattern_exhausted"  # All patterns used recently
    ERROR = "error"                    # Error state requiring recovery

# Valid state transitions - enforced at runtime
VALID_TRANSITIONS: Dict[RotationState, List[RotationState]] = {
    RotationState.INITIALIZING: [RotationState.PATTERN_ACTIVE, RotationState.ERROR],
    RotationState.PATTERN_ACTIVE: [RotationState.ROTATION_PENDING, RotationState.ERROR],
    RotationState.ROTATION_PENDING: [RotationState.ROTATING, RotationState.PATTERN_ACTIVE],
    RotationState.ROTATING: [RotationState.PATTERN_ACTIVE, RotationState.PATTERN_EXHAUSTED, RotationState.ERROR],
    RotationState.PATTERN_EXHAUSTED: [RotationState.PATTERN_ACTIVE],
    RotationState.ERROR: [RotationState.INITIALIZING],
}

def validate_transition(current: RotationState, target: RotationState) -> bool:
    """Validate that a state transition is allowed."""
    return target in VALID_TRANSITIONS.get(current, [])

def transition_to(current: RotationState, target: RotationState) -> RotationState:
    """Execute a state transition with validation."""
    if not validate_transition(current, target):
        raise InvalidTransitionError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Valid targets: {[s.value for s in VALID_TRANSITIONS.get(current, [])]}"
        )
    return target

class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass
```

### State Transition Diagram

```
                    +---------------+
                    | INITIALIZING  |
                    +-------+-------+
                            |
                            v
    +--------------------> PATTERN_ACTIVE <--------------------+
    |                       |                                  |
    |                       v                                  |
    |               ROTATION_PENDING ----+                     |
    |                       |            |                     |
    |                       v            |                     |
    |                   ROTATING --------+------> PATTERN_EXHAUSTED
    |                       |
    |                       v
    +---------------------- ERROR <--- (any state on failure)
```

---

## WAVE ENTRY GATE

### Prerequisites
- [ ] Wave 1 completed and validated
- [ ] All Wave 1 quality gates passed
- [ ] Database access for state tracking

### Dependencies
- Wave 1: Foundation & Critical Scoring (COMPLETE)

---

## OBJECTIVE

Implement all timing rules that affect conversion through proper spacing, followup windows, and rotation patterns. These rules create authentic-feeling schedules that don't appear robotic or automated.

---

## GAPS ADDRESSED

### Gap 1.1: PPV Structure Rotation Pattern Enforcement (P0 CRITICAL)

**Current State:** No tracking or enforcement of PPV type rotation
**Target State:** Pattern changes every 3-4 days

**Rotation Pattern Example:**
```
Day 1-3:  solo -> bundle -> winner -> sextape
Day 4-7:  sextape -> winner -> bundle -> solo (reversed)
Day 8-10: winner -> solo -> sextape -> bundle (shuffled)
```

**Business Impact:** +10-15% conversion through authenticity

---

### Gap 1.2: Same-Style Back-to-Back Prevention (P0 CRITICAL)

**Current State:** 2hr same-type spacing exists, but no same-style prevention
**Target State:** No winner/winner or bundle/bundle consecutively

**Rule:**
- Never schedule two winner PPVs back-to-back
- Never schedule two bundle PPVs consecutively
- Enforce AM/PM split for same styles within a day

**Business Impact:** -15-20% spam perception reduction

---

### Gap 1.3: PPV Followup Timing Window Enforcement (P0 CRITICAL)

**Current State:** Fixed 20-minute offset
**Target State:** Randomized 15-45 minute window

**Reference Data:**
- Too early (<15 min) = Appears spammy
- Optimal (15-45 min) = Fan still engaged
- Too late (>45 min) = Fan may be offline

**Business Impact:** +30-50% followup conversion

---

### Gap 1.5: Link Drop 24-Hour Expiration (P2 MEDIUM)

**Current State:** No expiration tracking
**Target State:** All link drops expire after 24 hours

**Business Impact:** Feed hygiene, urgency creation

---

### Gap 1.6: Pinned Post Rotation (P2 MEDIUM)

**Current State:** No pinned post management
**Target State:** Max 3-5 pins, rotate every 72 hours

**Business Impact:** Feed optimization, highlight high-value content

---

### Gap 10.7: Jitter Avoidance of Round Minutes (P1 HIGH)

**Current State:** Jitter exists but verification needed
**Target State:** Confirmed avoidance of :00, :15, :30, :45

**Business Impact:** Organic appearance, avoid automation detection

---

## AGENT DEPLOYMENT

### Group A (Parallel Execution)

| Agent | Task | Complexity |
|-------|------|------------|
| `python-pro` | Build PPV rotation tracker | MEDIUM |
| `database-optimizer` | Add rotation state to creator profiles | MEDIUM |

### Group B (Parallel with Group A)

| Agent | Task | Complexity |
|-------|------|------------|
| `python-pro` | Build same-style validator | LOW |
| `python-pro` | Refactor followup timing generator | LOW |
| `python-pro` | Add expiration tracking | LOW |

### Sequential (After Groups A+B)

| Agent | Task | Complexity |
|-------|------|------------|
| `code-reviewer` | Review timing logic | MEDIUM |
| `refactoring-pro` | Optimize rotation storage | LOW |

---

## IMPLEMENTATION TASKS

### Task 2.1: PPV Rotation Pattern Tracker

**Agent:** python-pro, database-optimizer
**Complexity:** MEDIUM
**Files:** `/python/orchestration/rotation_tracker.py`, database schema

```python
from datetime import datetime, timedelta
from typing import List
import random

class PPVRotationTracker:
    """Track and enforce PPV rotation patterns per creator."""

    STANDARD_PATTERNS = [
        ['solo', 'bundle', 'winner', 'sextape'],
        ['winner', 'solo', 'sextape', 'bundle'],
        ['bundle', 'sextape', 'solo', 'winner'],
        ['sextape', 'winner', 'bundle', 'solo'],
    ]

    def __init__(self, creator_id: str):
        self.creator_id = creator_id
        self.current_pattern = self._load_or_initialize()

    def _load_or_initialize(self) -> dict:
        """Load existing state or initialize new pattern."""
        # Load from database
        state = db.get_creator_rotation_state(self.creator_id)

        if not state:
            return {
                'pattern': random.choice(self.STANDARD_PATTERNS),
                'pattern_start_date': datetime.now(),
                'days_on_pattern': 0
            }
        return state

    def get_next_ppv_type(self, schedule_position: int) -> str:
        """Get the next PPV type based on rotation pattern."""
        self._check_pattern_rotation()
        pattern = self.current_pattern['pattern']
        return pattern[schedule_position % len(pattern)]

    def _check_pattern_rotation(self):
        """Rotate pattern every 3-4 days with deterministic day-3 decision."""
        days_since_start = (datetime.now() - self.current_pattern['pattern_start_date']).days

        if days_since_start < 3:
            return  # Too early to rotate

        if days_since_start >= 4:
            # Must rotate at day 4+
            self._rotate_pattern()
        else:
            # Day 3: deterministic 50% chance based on creator for natural variation
            seed = int(hashlib.md5(
                f"{self.creator_id}:{self.current_pattern['pattern_start_date'].isoformat()}".encode()
            ).hexdigest()[:8], 16)
            if seed % 2 == 0:
                self._rotate_pattern()

    def _rotate_pattern(self):
        """Change to a new pattern (reverse, shuffle, or new selection)."""
        current = self.current_pattern['pattern']

        # Randomly choose rotation method
        method = random.choice(['reverse', 'shuffle', 'new'])

        if method == 'reverse':
            new_pattern = current[::-1]
        elif method == 'shuffle':
            new_pattern = current.copy()
            random.shuffle(new_pattern)
        else:
            available = [p for p in self.STANDARD_PATTERNS if p != current]
            new_pattern = random.choice(available)

        self.current_pattern = {
            'pattern': new_pattern,
            'pattern_start_date': datetime.now(),
            'days_on_pattern': 0
        }

        # Save to database
        db.save_creator_rotation_state(self.creator_id, self.current_pattern)


# Database schema addition (SQLite-compatible)
"""
-- SQLite-compatible schema (no JSONB, use TEXT for JSON storage)
CREATE TABLE IF NOT EXISTS creator_rotation_state (
    creator_id TEXT PRIMARY KEY,
    rotation_pattern TEXT NOT NULL,  -- JSON stored as TEXT, parsed at application layer
    pattern_start_date TEXT NOT NULL,  -- ISO 8601 datetime string
    days_on_pattern INTEGER DEFAULT 0,
    current_state TEXT DEFAULT 'initializing',  -- RotationState enum value
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Index for efficient state queries
CREATE INDEX IF NOT EXISTS idx_rotation_state_updated
ON creator_rotation_state(updated_at);

-- Index for finding creators in specific states
CREATE INDEX IF NOT EXISTS idx_rotation_current_state
ON creator_rotation_state(current_state);
"""
```

---

### Task 2.1b: Wave 2 Timing Saga Coordinator

**Agent:** python-pro
**Complexity:** HIGH
**File:** `/python/orchestration/timing_saga.py`

The saga pattern ensures multi-step timing operations complete atomically with automatic rollback on failure.

```python
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Any
from datetime import datetime
from enum import Enum
import asyncio

class SagaStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

@dataclass
class SagaStep:
    """A single step in the saga with its compensation action."""
    name: str
    action: Callable
    compensation: Callable
    timeout_seconds: float = 30.0

@dataclass
class SagaResult:
    """Result of saga execution."""
    status: SagaStatus
    completed_steps: List[str]
    failed_step: Optional[str] = None
    error: Optional[str] = None
    compensation_errors: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

class Wave2TimingSaga:
    """
    Coordinates timing operations with automatic rollback.

    Implements the saga pattern for multi-step timing operations:
    1. Rotation pattern update
    2. Schedule validation
    3. Followup generation
    4. Jitter application

    If any step fails, all previous steps are compensated in reverse order.
    """

    def __init__(self, creator_id: str):
        self.creator_id = creator_id
        self.completed_steps: List[str] = []
        self.compensation_stack: List[Callable] = []
        self.status = SagaStatus.PENDING
        self._original_state: dict = {}

    async def execute(self, daily_schedule: list) -> SagaResult:
        """
        Execute the timing saga with full compensation support.

        Args:
            daily_schedule: The schedule to process

        Returns:
            SagaResult with status and details
        """
        start_time = datetime.now()

        steps = [
            SagaStep(
                name="rotation_update",
                action=lambda: self._apply_rotation(daily_schedule),
                compensation=lambda: self._rollback_rotation()
            ),
            SagaStep(
                name="schedule_validation",
                action=lambda: self._validate_schedule(daily_schedule),
                compensation=lambda: None  # Validation has no side effects
            ),
            SagaStep(
                name="followup_generation",
                action=lambda: self._generate_followups(daily_schedule),
                compensation=lambda: self._remove_followups(daily_schedule)
            ),
            SagaStep(
                name="jitter_application",
                action=lambda: self._apply_jitter(daily_schedule),
                compensation=lambda: self._restore_original_times(daily_schedule)
            ),
        ]

        self.status = SagaStatus.IN_PROGRESS

        try:
            for step in steps:
                try:
                    # Execute step with timeout
                    await asyncio.wait_for(
                        asyncio.to_thread(step.action),
                        timeout=step.timeout_seconds
                    )
                    self.completed_steps.append(step.name)
                    self.compensation_stack.append(step.compensation)
                except asyncio.TimeoutError:
                    raise SagaStepError(f"Step {step.name} timed out after {step.timeout_seconds}s")
                except Exception as e:
                    raise SagaStepError(f"Step {step.name} failed: {str(e)}")

            self.status = SagaStatus.COMPLETED
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return SagaResult(
                status=SagaStatus.COMPLETED,
                completed_steps=self.completed_steps.copy(),
                execution_time_ms=execution_time
            )

        except SagaStepError as e:
            return await self._compensate(str(e), start_time)

    async def _compensate(self, error: str, start_time: datetime) -> SagaResult:
        """Execute compensation actions in reverse order."""
        self.status = SagaStatus.COMPENSATING
        compensation_errors = []
        failed_step = self.completed_steps[-1] if self.completed_steps else None

        # Execute compensations in reverse order
        while self.compensation_stack:
            compensation = self.compensation_stack.pop()
            try:
                await asyncio.to_thread(compensation)
            except Exception as comp_error:
                compensation_errors.append(str(comp_error))

        self.status = SagaStatus.ROLLED_BACK if not compensation_errors else SagaStatus.FAILED
        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        return SagaResult(
            status=self.status,
            completed_steps=self.completed_steps.copy(),
            failed_step=failed_step,
            error=error,
            compensation_errors=compensation_errors,
            execution_time_ms=execution_time
        )

    def _apply_rotation(self, schedule: list) -> None:
        """Step 1: Apply rotation pattern."""
        self._original_state['rotation'] = self._get_current_rotation()
        # Apply new rotation...

    def _rollback_rotation(self) -> None:
        """Compensate rotation by restoring original state."""
        if 'rotation' in self._original_state:
            self._restore_rotation(self._original_state['rotation'])

    def _validate_schedule(self, schedule: list) -> None:
        """Step 2: Validate schedule constraints."""
        result = validate_no_consecutive_same_style(schedule)
        if not result['is_valid']:
            raise ValueError(f"Validation failed: {result['errors']}")

    def _generate_followups(self, schedule: list) -> None:
        """Step 3: Generate PPV followups."""
        self._original_state['followups'] = []
        # Generate followups and track them...

    def _remove_followups(self, schedule: list) -> None:
        """Compensate by removing generated followups."""
        for followup_id in self._original_state.get('followups', []):
            # Remove followup from schedule...
            pass

    def _apply_jitter(self, schedule: list) -> None:
        """Step 4: Apply time jitter to all items."""
        self._original_state['original_times'] = {
            item['id']: item['scheduled_time'] for item in schedule
        }
        # Apply jitter...

    def _restore_original_times(self, schedule: list) -> None:
        """Compensate by restoring original times."""
        for item in schedule:
            if item['id'] in self._original_state.get('original_times', {}):
                item['scheduled_time'] = self._original_state['original_times'][item['id']]

    def _get_current_rotation(self) -> dict:
        """Get current rotation state from database."""
        # Implementation...
        return {}

    def _restore_rotation(self, state: dict) -> None:
        """Restore rotation state to database."""
        # Implementation...
        pass

class SagaStepError(Exception):
    """Raised when a saga step fails."""
    pass
```

---

### Task 2.2: Same-Style Back-to-Back Validator

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/orchestration/timing_validator.py`

```python
def validate_no_consecutive_same_style(daily_schedule: list) -> dict:
    """
    Prevent winner/winner or bundle/bundle back-to-back.
    Enforce AM/PM split for same-style duplicates.
    """
    ppv_items = [item for item in daily_schedule if item.get('is_ppv', False)]

    if len(ppv_items) < 2:
        return {'is_valid': True}

    errors = []

    # Check consecutive same-style
    for i in range(len(ppv_items) - 1):
        current_style = ppv_items[i].get('ppv_style')
        next_style = ppv_items[i + 1].get('ppv_style')

        if current_style == next_style and current_style in ['winner', 'bundle']:
            errors.append(
                f"Two {current_style} PPVs back-to-back at positions {i} and {i+1}. "
                f"Violates authenticity rule."
            )

    # Check AM/PM split for same-style duplicates
    style_by_period = {'AM': [], 'PM': []}
    for item in ppv_items:
        hour = item.get('hour', 12)
        period = 'AM' if hour < 12 else 'PM'
        style_by_period[period].append(item.get('ppv_style'))

    for period, styles in style_by_period.items():
        from collections import Counter
        style_counts = Counter(styles)
        for style, count in style_counts.items():
            if count > 1 and style in ['winner', 'bundle']:
                errors.append(
                    f"Multiple {style} PPVs in {period} period ({count} found). "
                    f"Apply AM/PM split."
                )

    return {
        'is_valid': len(errors) == 0,
        'errors': errors
    }


def validate_and_repair_consecutive_styles(daily_schedule: list) -> dict:
    """
    Validate and automatically repair same-style back-to-back violations.

    Repair strategies applied in order:
    1. Swap positions with non-violating item
    2. Insert spacing item between violations
    3. Move to different time period (AM/PM)
    4. Flag for manual review if unrepairable

    Args:
        daily_schedule: List of schedule items to validate and repair

    Returns:
        dict with is_valid, repairs_applied, remaining_errors
    """
    validation = validate_no_consecutive_same_style(daily_schedule)

    if validation['is_valid']:
        return {
            'is_valid': True,
            'repairs_applied': [],
            'remaining_errors': []
        }

    repairs_applied = []
    ppv_items = [item for item in daily_schedule if item.get('is_ppv', False)]

    # Strategy 1: Try position swapping
    for i in range(len(ppv_items) - 1):
        current_style = ppv_items[i].get('ppv_style')
        next_style = ppv_items[i + 1].get('ppv_style')

        if current_style == next_style and current_style in ['winner', 'bundle']:
            # Find a non-matching item to swap with
            for j in range(i + 2, len(ppv_items)):
                if ppv_items[j].get('ppv_style') != current_style:
                    # Swap positions
                    ppv_items[i + 1], ppv_items[j] = ppv_items[j], ppv_items[i + 1]
                    repairs_applied.append({
                        'strategy': 'position_swap',
                        'original_position': i + 1,
                        'swapped_with': j,
                        'style': current_style
                    })
                    break

    # Strategy 2: AM/PM redistribution
    style_by_period = {'AM': [], 'PM': []}
    for idx, item in enumerate(ppv_items):
        hour = item.get('hour', 12)
        period = 'AM' if hour < 12 else 'PM'
        style_by_period[period].append((idx, item))

    for period in ['AM', 'PM']:
        other_period = 'PM' if period == 'AM' else 'AM'
        styles_in_period = [item[1].get('ppv_style') for item in style_by_period[period]]

        from collections import Counter
        style_counts = Counter(styles_in_period)

        for style, count in style_counts.items():
            if count > 1 and style in ['winner', 'bundle']:
                # Move excess to other period
                items_to_move = [
                    (idx, item) for idx, item in style_by_period[period]
                    if item.get('ppv_style') == style
                ][1:]  # Keep first, move rest

                for idx, item in items_to_move:
                    # Adjust hour to other period
                    if other_period == 'AM':
                        item['hour'] = 10  # Default AM hour
                    else:
                        item['hour'] = 14  # Default PM hour

                    repairs_applied.append({
                        'strategy': 'am_pm_redistribution',
                        'item_index': idx,
                        'from_period': period,
                        'to_period': other_period,
                        'style': style
                    })

    # Re-validate after repairs
    final_validation = validate_no_consecutive_same_style(daily_schedule)

    return {
        'is_valid': final_validation['is_valid'],
        'repairs_applied': repairs_applied,
        'remaining_errors': final_validation.get('errors', [])
    }
```

---

### Task 2.2b: Timing Metrics and Observability

**Agent:** python-pro
**Complexity:** MEDIUM
**File:** `/python/orchestration/timing_metrics.py`

Comprehensive logging and metrics for timing operations to enable debugging and performance monitoring.

```python
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
import json

# Import project logging configuration
from python.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TimingEvent:
    """Structured timing event for logging."""
    event_type: str
    creator_id: str
    timestamp: str
    details: Dict[str, Any]
    duration_ms: Optional[float] = None


class TimingMetrics:
    """
    Centralized metrics collection for Wave 2 timing operations.

    All timing events are logged in structured JSON format for easy
    parsing by log aggregation systems (ELK, Datadog, etc.).
    """

    @staticmethod
    def log_rotation_change(
        creator_id: str,
        old_pattern: list,
        new_pattern: list,
        method: str,
        days_on_previous: int
    ) -> None:
        """
        Log when a creator's PPV rotation pattern changes.

        Args:
            creator_id: Creator identifier
            old_pattern: Previous rotation pattern
            new_pattern: New rotation pattern
            method: How rotation was determined (reverse, shuffle, new)
            days_on_previous: Days spent on previous pattern
        """
        event = TimingEvent(
            event_type="rotation_change",
            creator_id=creator_id,
            timestamp=datetime.now().isoformat(),
            details={
                "old_pattern": old_pattern,
                "new_pattern": new_pattern,
                "rotation_method": method,
                "days_on_previous_pattern": days_on_previous,
                "pattern_diversity_score": TimingMetrics._calculate_diversity(old_pattern, new_pattern)
            }
        )
        logger.info(f"TIMING_EVENT: {json.dumps(asdict(event))}")

    @staticmethod
    def log_followup_scheduled(
        creator_id: str,
        parent_time: datetime,
        followup_time: datetime,
        gap_minutes: float,
        ppv_type: str
    ) -> None:
        """
        Log when a PPV followup is scheduled.

        Args:
            creator_id: Creator identifier
            parent_time: Time of parent PPV
            followup_time: Scheduled followup time
            gap_minutes: Minutes between parent and followup
            ppv_type: Type of PPV (winner, bundle, etc.)
        """
        is_optimal = 15 <= gap_minutes <= 45

        event = TimingEvent(
            event_type="followup_scheduled",
            creator_id=creator_id,
            timestamp=datetime.now().isoformat(),
            details={
                "parent_time": parent_time.isoformat(),
                "followup_time": followup_time.isoformat(),
                "gap_minutes": round(gap_minutes, 1),
                "ppv_type": ppv_type,
                "is_optimal_window": is_optimal,
                "window_position": "early" if gap_minutes < 20 else ("late" if gap_minutes > 40 else "optimal")
            }
        )
        logger.info(f"TIMING_EVENT: {json.dumps(asdict(event))}")

        if not is_optimal:
            logger.warning(
                f"Followup timing outside optimal window for {creator_id}: "
                f"{gap_minutes:.1f} min (expected 15-45 min)"
            )

    @staticmethod
    def log_jitter_applied(
        creator_id: str,
        original_time: datetime,
        jittered_time: datetime,
        send_type: str
    ) -> None:
        """Log when time jitter is applied to a schedule item."""
        offset_minutes = (jittered_time - original_time).total_seconds() / 60
        is_round_minute = jittered_time.minute in {0, 15, 30, 45}

        event = TimingEvent(
            event_type="jitter_applied",
            creator_id=creator_id,
            timestamp=datetime.now().isoformat(),
            details={
                "original_time": original_time.isoformat(),
                "jittered_time": jittered_time.isoformat(),
                "offset_minutes": round(offset_minutes, 1),
                "send_type": send_type,
                "final_minute": jittered_time.minute,
                "avoided_round_minute": not is_round_minute
            }
        )
        logger.info(f"TIMING_EVENT: {json.dumps(asdict(event))}")

        if is_round_minute:
            logger.error(
                f"CRITICAL: Jitter landed on round minute for {creator_id}: "
                f":{jittered_time.minute:02d}"
            )

    @staticmethod
    def log_validation_result(
        creator_id: str,
        validation_type: str,
        is_valid: bool,
        errors: list,
        repairs_applied: list = None
    ) -> None:
        """Log validation results including any repairs."""
        event = TimingEvent(
            event_type="validation_result",
            creator_id=creator_id,
            timestamp=datetime.now().isoformat(),
            details={
                "validation_type": validation_type,
                "is_valid": is_valid,
                "error_count": len(errors),
                "errors": errors[:5],  # Limit to first 5 for log size
                "repairs_applied": repairs_applied or [],
                "repair_count": len(repairs_applied) if repairs_applied else 0
            }
        )

        if is_valid:
            logger.info(f"TIMING_EVENT: {json.dumps(asdict(event))}")
        else:
            logger.warning(f"TIMING_EVENT: {json.dumps(asdict(event))}")

    @staticmethod
    def log_saga_execution(
        creator_id: str,
        saga_result: 'SagaResult',
        schedule_item_count: int
    ) -> None:
        """Log saga execution results."""
        event = TimingEvent(
            event_type="saga_execution",
            creator_id=creator_id,
            timestamp=datetime.now().isoformat(),
            duration_ms=saga_result.execution_time_ms,
            details={
                "status": saga_result.status.value,
                "completed_steps": saga_result.completed_steps,
                "failed_step": saga_result.failed_step,
                "error": saga_result.error,
                "compensation_errors": saga_result.compensation_errors,
                "schedule_item_count": schedule_item_count
            }
        )

        if saga_result.status.value == "completed":
            logger.info(f"TIMING_EVENT: {json.dumps(asdict(event))}")
        else:
            logger.error(f"TIMING_EVENT: {json.dumps(asdict(event))}")

    @staticmethod
    def _calculate_diversity(old_pattern: list, new_pattern: list) -> float:
        """Calculate how different the new pattern is from the old."""
        if not old_pattern or not new_pattern:
            return 1.0
        differences = sum(1 for a, b in zip(old_pattern, new_pattern) if a != b)
        return differences / len(old_pattern)
```

---

### Task 2.3: Followup Timing Window Enforcement

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/orchestration/followup_generator.py`

```python
import random
import hashlib
import math
from datetime import datetime, timedelta
from typing import Optional

def schedule_ppv_followup(
    parent_ppv_time: datetime,
    creator_id: str,
    min_offset: int = 15,
    max_offset: int = 45,
    allow_next_day: bool = False
) -> datetime:
    """
    Generate followup time within 15-45 minute optimal window.

    Uses truncated normal distribution centered at 28 minutes (sweet spot)
    for more natural timing that clusters around optimal engagement window.

    Args:
        parent_ppv_time: Time of the parent PPV
        creator_id: Creator identifier for deterministic seeding
        min_offset: Minimum minutes after parent (default 15)
        max_offset: Maximum minutes after parent (default 45)
        allow_next_day: If True, allow followup to cross midnight boundary

    Returns:
        Scheduled followup datetime

    Raises:
        ValueError: If followup would cross midnight without allow_next_day
    """
    # Create deterministic seed from creator + date
    seed_string = f"{creator_id}:{parent_ppv_time.strftime('%Y-%m-%d:%H:%M')}"
    seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Use truncated normal distribution centered at 28 minutes (optimal sweet spot)
    # This creates more natural clustering around the engagement peak
    mean = 28  # Sweet spot: not too pushy, fan still engaged
    std_dev = 8  # Provides good spread across the window

    # Generate using rejection sampling for truncated normal
    followup_offset_minutes = _truncated_normal_sample(
        rng, mean, std_dev, min_offset, max_offset
    )

    followup_time = parent_ppv_time + timedelta(minutes=followup_offset_minutes)

    # Day boundary handling
    if followup_time.date() > parent_ppv_time.date():
        if not allow_next_day:
            # Clamp to 11:59 PM on same day
            followup_time = parent_ppv_time.replace(hour=23, minute=59, second=0)
            # Log warning for monitoring
            actual_gap = (followup_time - parent_ppv_time).total_seconds() / 60
            if actual_gap < min_offset:
                raise ValueError(
                    f"PPV at {parent_ppv_time.strftime('%H:%M')} too late for followup. "
                    f"Gap would be {actual_gap:.0f} min (minimum: {min_offset} min). "
                    f"Consider scheduling PPV earlier or setting allow_next_day=True."
                )

    # Validate result
    actual_gap = (followup_time - parent_ppv_time).total_seconds() / 60
    if not (min_offset <= actual_gap <= max_offset) and not allow_next_day:
        raise ValueError(
            f"Followup timing violation: {actual_gap:.0f} min "
            f"(required: {min_offset}-{max_offset} min)"
        )

    return followup_time


def _truncated_normal_sample(
    rng: random.Random,
    mean: float,
    std_dev: float,
    min_val: float,
    max_val: float,
    max_attempts: int = 100
) -> float:
    """
    Generate a sample from truncated normal distribution using rejection sampling.

    Args:
        rng: Seeded random number generator
        mean: Mean of the normal distribution
        std_dev: Standard deviation
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        max_attempts: Maximum rejection sampling attempts

    Returns:
        Sample value within [min_val, max_val]
    """
    for _ in range(max_attempts):
        # Box-Muller transform for normal distribution
        u1 = rng.random()
        u2 = rng.random()
        z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        sample = mean + z * std_dev

        if min_val <= sample <= max_val:
            return round(sample)

    # Fallback to uniform if rejection sampling fails
    return rng.randint(int(min_val), int(max_val))


def validate_followup_window(parent_time: datetime, followup_time: datetime) -> dict:
    """Validate followup is within optimal window."""
    gap_minutes = (followup_time - parent_time).total_seconds() / 60

    if gap_minutes < 15:
        return {
            'is_valid': False,
            'gap_minutes': gap_minutes,
            'error': f"Followup too early ({gap_minutes:.0f} min). Minimum: 15 min."
        }

    if gap_minutes > 45:
        return {
            'is_valid': False,
            'gap_minutes': gap_minutes,
            'error': f"Followup too late ({gap_minutes:.0f} min). Maximum: 45 min."
        }

    return {
        'is_valid': True,
        'gap_minutes': gap_minutes
    }
```

---

### Task 2.4: Link Drop Expiration Tracking

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/models/schedule_item.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

@dataclass
class ScheduleItem:
    """Schedule item with expiration support."""
    send_type: str
    scheduled_time: datetime
    channel: str
    caption_id: Optional[str] = None
    price: Optional[float] = None
    parent_id: Optional[str] = None
    expiration_time: Optional[datetime] = None  # NEW FIELD

    def __post_init__(self):
        """Set expiration for link drops."""
        if self.send_type in ['link_drop', 'wall_link_drop']:
            if self.expiration_time is None:
                self.expiration_time = self.scheduled_time + timedelta(hours=24)


def create_link_drop(
    parent_campaign: ScheduleItem,
    scheduled_time: datetime
) -> ScheduleItem:
    """Create link drop with 24-hour expiration."""
    return ScheduleItem(
        send_type='link_drop',
        scheduled_time=scheduled_time,
        channel='wall_post',
        parent_id=parent_campaign.id if hasattr(parent_campaign, 'id') else None,
        expiration_time=scheduled_time + timedelta(hours=24)
    )
```

---

### Task 2.5: Pinned Post Rotation Manager

**Agent:** python-pro
**Complexity:** MEDIUM
**File:** `/python/orchestration/pinned_post_manager.py`

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

@dataclass
class PinItem:
    post_id: str
    pin_start: datetime
    pin_end: datetime
    priority: float  # Based on estimated revenue

class PinnedPostManager:
    """Manage pinned post rotation with max 5 pins and 72-hour lifecycle."""

    MAX_PINNED = 5
    PIN_DURATION_HOURS = 72

    def __init__(self, creator_id: str):
        self.creator_id = creator_id
        self.active_pins: List[PinItem] = self._load_active_pins()

    def _load_active_pins(self) -> List[PinItem]:
        """Load current pinned posts from database."""
        # Load from database, filter expired
        pins = db.get_active_pins(self.creator_id)
        now = datetime.now()
        return [p for p in pins if p.pin_end > now]

    def should_pin(self, schedule_item: dict) -> bool:
        """Determine if item should be pinned."""
        return schedule_item.get('send_type') in ['ppv_wall', 'game_post']

    def schedule_pin(self, schedule_item: dict) -> Optional[PinItem]:
        """Schedule item for pinning with rotation."""
        if not self.should_pin(schedule_item):
            return None

        scheduled_time = schedule_item['scheduled_time']
        priority = schedule_item.get('estimated_revenue', 0)

        # Check if we need to unpin something
        if len(self.active_pins) >= self.MAX_PINNED:
            # Find lowest priority pin
            lowest = min(self.active_pins, key=lambda p: p.priority)
            if priority > lowest.priority:
                self._unpin(lowest)
            else:
                return None  # New item is lower priority, don't pin

        pin_item = PinItem(
            post_id=schedule_item.get('id', str(hash(str(schedule_item)))),
            pin_start=scheduled_time,
            pin_end=scheduled_time + timedelta(hours=self.PIN_DURATION_HOURS),
            priority=priority
        )

        self.active_pins.append(pin_item)
        self._save_pin(pin_item)

        return pin_item

    def _unpin(self, pin_item: PinItem):
        """Remove pin from active list."""
        self.active_pins.remove(pin_item)
        db.remove_pin(self.creator_id, pin_item.post_id)

    def _save_pin(self, pin_item: PinItem):
        """Save pin to database."""
        db.save_pin(self.creator_id, pin_item)

    def get_pins_to_remove(self, current_time: datetime) -> List[PinItem]:
        """Get pins that have exceeded 72-hour duration."""
        expired = [p for p in self.active_pins if p.pin_end <= current_time]
        return expired
```

---

### Task 2.5b: Idempotency Guard

**Agent:** python-pro
**Complexity:** MEDIUM
**File:** `/python/orchestration/idempotency.py`

Prevents duplicate operations when timing functions are called multiple times with the same parameters.

```python
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from dataclasses import dataclass
from functools import wraps
import threading


@dataclass
class IdempotencyRecord:
    """Record of a previously executed operation."""
    operation_key: str
    result: Any
    executed_at: datetime
    expires_at: datetime


class IdempotencyGuard:
    """
    Prevents duplicate execution of timing operations.

    Uses content-addressable storage based on operation parameters
    to detect and prevent duplicate calls within a configurable window.
    """

    def __init__(self, ttl_minutes: int = 60):
        """
        Initialize the idempotency guard.

        Args:
            ttl_minutes: How long to remember operations (default 60 minutes)
        """
        self._store: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.RLock()
        self._ttl = timedelta(minutes=ttl_minutes)

    def _generate_key(self, operation: str, params: dict) -> str:
        """Generate a unique key for an operation + parameters combination."""
        # Normalize parameters for consistent hashing
        normalized = json.dumps(params, sort_keys=True, default=str)
        content = f"{operation}:{normalized}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def check_and_store(
        self,
        operation: str,
        params: dict,
        result: Any
    ) -> tuple[bool, Optional[Any]]:
        """
        Check if operation was already executed; if not, store the result.

        Args:
            operation: Name of the operation
            params: Parameters that uniquely identify this call
            result: Result to store if this is a new operation

        Returns:
            Tuple of (is_duplicate, previous_result_or_none)
        """
        key = self._generate_key(operation, params)
        now = datetime.now()

        with self._lock:
            # Clean expired entries
            self._cleanup_expired(now)

            # Check for existing record
            if key in self._store:
                record = self._store[key]
                if record.expires_at > now:
                    return (True, record.result)

            # Store new record
            self._store[key] = IdempotencyRecord(
                operation_key=key,
                result=result,
                executed_at=now,
                expires_at=now + self._ttl
            )
            return (False, None)

    def is_duplicate(self, operation: str, params: dict) -> bool:
        """Check if an operation would be a duplicate without storing."""
        key = self._generate_key(operation, params)
        now = datetime.now()

        with self._lock:
            if key in self._store:
                record = self._store[key]
                return record.expires_at > now
            return False

    def invalidate(self, operation: str, params: dict) -> bool:
        """
        Manually invalidate a stored operation result.

        Returns True if an entry was removed, False if not found.
        """
        key = self._generate_key(operation, params)
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def _cleanup_expired(self, now: datetime) -> int:
        """Remove expired entries. Returns count of removed entries."""
        expired_keys = [
            k for k, v in self._store.items()
            if v.expires_at <= now
        ]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)


# Global guard instance for timing operations
_timing_guard = IdempotencyGuard(ttl_minutes=60)


def idempotent(operation_name: str = None):
    """
    Decorator to make a function idempotent.

    Usage:
        @idempotent("schedule_followup")
        def schedule_ppv_followup(parent_time, creator_id, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            # Build params dict from args and kwargs
            params = {
                'args': args,
                'kwargs': kwargs
            }

            # Check if duplicate
            if _timing_guard.is_duplicate(op_name, params):
                is_dup, prev_result = _timing_guard.check_and_store(
                    op_name, params, None
                )
                if is_dup:
                    return prev_result

            # Execute and store
            result = func(*args, **kwargs)
            _timing_guard.check_and_store(op_name, params, result)
            return result

        return wrapper
    return decorator
```

---

### Task 2.5c: Circuit Breaker for Database Operations

**Agent:** python-pro
**Complexity:** MEDIUM
**File:** `/python/orchestration/circuit_breaker.py`

Prevents cascading failures when database operations fail repeatedly.

```python
import time
import threading
from datetime import datetime, timedelta
from typing import Callable, TypeVar, Generic, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests flow through
    OPEN = "open"          # Failing, requests are rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Statistics for circuit breaker monitoring."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker for database and external service operations.

    Prevents repeated calls to failing services, allowing them time
    to recover while providing fallback values.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
        fallback_value: Optional[T] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before trying half-open
            half_open_max_calls: Test calls allowed in half-open state
            fallback_value: Value to return when circuit is open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.half_open_max_calls = half_open_max_calls
        self.fallback_value = fallback_value

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = threading.RLock()
        self._last_state_change = datetime.now()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for automatic transitions."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if datetime.now() - self._last_state_change >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def call(self, func: Callable[[], T]) -> T:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Function to execute

        Returns:
            Function result or fallback value

        Raises:
            CircuitOpenError: If circuit is open and no fallback defined
        """
        with self._lock:
            current_state = self.state
            self._stats.total_calls += 1

            if current_state == CircuitState.OPEN:
                self._stats.rejected_calls += 1
                if self.fallback_value is not None:
                    return self.fallback_value
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is open. "
                    f"Try again after {self.recovery_timeout.seconds}s"
                )

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    self._stats.rejected_calls += 1
                    if self.fallback_value is not None:
                        return self.fallback_value
                    raise CircuitOpenError(
                        f"Circuit '{self.name}' half-open limit reached"
                    )
                self._half_open_calls += 1

        # Execute outside lock to avoid blocking
        try:
            result = func()
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    def _record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._stats.successful_calls += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)

    def _record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._stats.failed_calls += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self._stats.consecutive_failures >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.now()

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._stats.consecutive_successes = 0

        # Log state transition for monitoring
        from python.logging_config import get_logger
        logger = get_logger(__name__)
        logger.warning(
            f"Circuit '{self.name}' transitioned: {old_state.value} -> {new_state.value}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "stats": {
                    "total_calls": self._stats.total_calls,
                    "successful_calls": self._stats.successful_calls,
                    "failed_calls": self._stats.failed_calls,
                    "rejected_calls": self._stats.rejected_calls,
                    "consecutive_failures": self._stats.consecutive_failures,
                    "consecutive_successes": self._stats.consecutive_successes,
                }
            }


class CircuitOpenError(Exception):
    """Raised when a call is rejected due to open circuit."""
    pass


# Pre-configured circuit breakers for common operations
rotation_state_circuit = CircuitBreaker(
    name="rotation_state_db",
    failure_threshold=3,
    recovery_timeout=30,
    fallback_value=None  # Will use default pattern
)

timing_validation_circuit = CircuitBreaker(
    name="timing_validation",
    failure_threshold=5,
    recovery_timeout=15,
    fallback_value={'is_valid': True, 'errors': [], 'fallback': True}
)


def circuit_protected(circuit: CircuitBreaker):
    """Decorator to protect a function with a circuit breaker."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return circuit.call(lambda: func(*args, **kwargs))
        return wrapper
    return decorator
```

---

### Task 2.6: Time Jitter Implementation

**Agent:** python-pro
**Complexity:** MEDIUM
**File:** `/python/orchestration/timing_optimizer.py`

```python
import hashlib
import random
from datetime import datetime, timedelta

def apply_time_jitter(base_time: datetime, creator_id: str) -> datetime:
    """
    Apply deterministic jitter that avoids round minutes (:00, :15, :30, :45).

    Args:
        base_time: The base scheduled time
        creator_id: Creator identifier for deterministic seeding

    Returns:
        Jittered datetime guaranteed to not land on round minutes
    """
    ROUND_MINUTES = {0, 15, 30, 45}

    # Create deterministic seed from creator + time
    seed_string = f"{creator_id}:{base_time.strftime('%Y-%m-%d:%H:%M')}"
    seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    base_minute = base_time.minute

    # Generate jitter offset in range [-7, +8] that results in non-round minute
    valid_offsets = []
    for offset in range(-7, 9):
        resulting_minute = (base_minute + offset) % 60
        if resulting_minute not in ROUND_MINUTES:
            valid_offsets.append(offset)

    if not valid_offsets:
        # Edge case: all offsets land on round minutes (impossible but defensive)
        offset = 1 if (base_minute + 1) % 60 not in ROUND_MINUTES else 2
    else:
        offset = rng.choice(valid_offsets)

    return base_time + timedelta(minutes=offset)
```

---

### Task 2.7: Jitter Round Minute Verification

**Agent:** code-reviewer
**Complexity:** LOW
**File:** `/python/tests/test_timing.py`

```python
import pytest
from datetime import datetime
from ..orchestration.timing_optimizer import apply_time_jitter

class TestJitterAvoidance:
    """Verify jitter never lands on round minutes."""

    ROUND_MINUTES = [0, 15, 30, 45]

    @pytest.mark.parametrize("creator_id", ['test_1', 'test_2', 'test_3', 'test_4', 'test_5'])
    @pytest.mark.parametrize("hour", range(24))
    def test_jitter_avoids_round_minutes(self, creator_id, hour):
        """Test jitter across multiple creators and hours."""
        base_time = datetime(2025, 1, 15, hour, 30)  # Start at :30
        jittered = apply_time_jitter(base_time, creator_id)

        assert jittered.minute not in self.ROUND_MINUTES, \
            f"Jitter landed on round minute: {jittered.minute} for {creator_id} at hour {hour}"

    def test_jitter_is_deterministic(self):
        """Same creator + time = same jitter output."""
        base_time = datetime(2025, 1, 15, 14, 30)
        creator_id = 'determinism_test'

        result1 = apply_time_jitter(base_time, creator_id)
        result2 = apply_time_jitter(base_time, creator_id)

        assert result1 == result2, "Jitter should be deterministic for same inputs"

    def test_jitter_range(self):
        """Jitter should be within -7 to +8 minutes."""
        base_time = datetime(2025, 1, 15, 14, 30)

        for i in range(100):
            creator_id = f'range_test_{i}'
            jittered = apply_time_jitter(base_time, creator_id)

            diff_minutes = (jittered - base_time).total_seconds() / 60

            assert -7 <= diff_minutes <= 8, \
                f"Jitter out of range: {diff_minutes} minutes"
```

---

### Task 2.8: Integration with CreatorTimingProfile

**Agent:** python-pro
**Complexity:** LOW
**File:** `/python/orchestration/timing_integration.py`

**IMPORTANT**: Wave 2 timing operations should leverage the existing `CreatorTimingProfile` model at `/python/models/creator_timing_profile.py` for creator-specific timing preferences and historical patterns.

```python
"""
Integration layer connecting Wave 2 timing components with existing CreatorTimingProfile.

The CreatorTimingProfile model contains:
- Preferred posting windows per day
- Historical engagement patterns by hour
- Timezone information
- Activity level indicators
- Best performing time slots

All Wave 2 timing operations should consult this profile for creator-specific adjustments.
"""

from typing import Optional
from datetime import datetime, time

# Import existing model
from python.models.creator_timing_profile import CreatorTimingProfile


class TimingProfileIntegration:
    """
    Integrates Wave 2 timing with existing CreatorTimingProfile.

    This ensures timing decisions respect creator-specific patterns
    rather than using global defaults.
    """

    def __init__(self, creator_id: str):
        self.creator_id = creator_id
        self._profile: Optional[CreatorTimingProfile] = None

    @property
    def profile(self) -> CreatorTimingProfile:
        """Lazy load the creator's timing profile."""
        if self._profile is None:
            self._profile = CreatorTimingProfile.load(self.creator_id)
        return self._profile

    def get_optimal_followup_window(self) -> tuple[int, int]:
        """
        Get creator-specific optimal followup window.

        Returns tuple of (min_minutes, max_minutes) based on
        creator's historical engagement patterns.
        """
        # Default window
        min_offset, max_offset = 15, 45

        if self.profile and self.profile.engagement_patterns:
            # Adjust based on creator's audience response time patterns
            avg_response_time = self.profile.engagement_patterns.get('avg_response_minutes', 30)

            # Tighten window around creator's sweet spot
            min_offset = max(15, int(avg_response_time * 0.6))
            max_offset = min(45, int(avg_response_time * 1.5))

        return (min_offset, max_offset)

    def should_allow_next_day_followup(self) -> bool:
        """
        Determine if this creator's audience engages across midnight.

        Some creators have international audiences where day boundaries
        matter less.
        """
        if self.profile and self.profile.timezone_info:
            # Check if creator has significant international audience
            return self.profile.timezone_info.get('multi_timezone_audience', False)
        return False

    def get_am_pm_preference(self) -> Optional[str]:
        """
        Get creator's preferred posting period for same-style spacing.

        Returns 'AM', 'PM', or None if no preference.
        """
        if self.profile and self.profile.preferred_windows:
            peak_hour = self.profile.preferred_windows.get('peak_engagement_hour', 12)
            return 'AM' if peak_hour < 12 else 'PM'
        return None

    def adjust_jitter_for_creator(self, base_jitter: int) -> int:
        """
        Adjust jitter based on creator's posting style.

        Some creators prefer tighter schedules, others more varied.
        """
        if self.profile:
            variation_preference = self.profile.activity_indicators.get('timing_variation', 'medium')

            if variation_preference == 'low':
                return max(1, base_jitter // 2)  # Tighter timing
            elif variation_preference == 'high':
                return min(8, base_jitter * 2)  # More variation

        return base_jitter


def get_timing_integration(creator_id: str) -> TimingProfileIntegration:
    """Factory function to get timing integration for a creator."""
    return TimingProfileIntegration(creator_id)
```

---

### Task 2.9: Advanced Test Cases

**Agent:** code-reviewer
**Complexity:** MEDIUM
**File:** `/python/tests/test_timing_advanced.py`

Additional test cases covering concurrency, boundary conditions, and recovery scenarios.

```python
import pytest
import asyncio
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock

from ..orchestration.timing_saga import Wave2TimingSaga, SagaStatus
from ..orchestration.idempotency import IdempotencyGuard, idempotent
from ..orchestration.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError
from ..orchestration.rotation_tracker import PPVRotationTracker
from ..orchestration.followup_generator import schedule_ppv_followup


class TestConcurrency:
    """Tests for thread safety and concurrent access."""

    def test_idempotency_guard_thread_safety(self):
        """Verify idempotency guard handles concurrent access safely."""
        guard = IdempotencyGuard(ttl_minutes=1)
        results = []
        errors = []

        def concurrent_check(thread_id):
            try:
                is_dup, _ = guard.check_and_store(
                    "test_op",
                    {"key": "same_key"},
                    f"result_{thread_id}"
                )
                results.append((thread_id, is_dup))
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Run 100 concurrent threads
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(concurrent_check, i) for i in range(100)]
            for f in futures:
                f.result()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Exactly one should be non-duplicate (first)
        non_duplicates = [r for r in results if not r[1]]
        assert len(non_duplicates) == 1, \
            f"Expected 1 non-duplicate, got {len(non_duplicates)}"

    def test_circuit_breaker_thread_safety(self):
        """Verify circuit breaker handles concurrent failures correctly."""
        breaker = CircuitBreaker(
            name="test_concurrent",
            failure_threshold=5,
            recovery_timeout=1
        )

        call_count = [0]
        lock = threading.Lock()

        def failing_call():
            with lock:
                call_count[0] += 1
            raise Exception("Simulated failure")

        def attempt_call(thread_id):
            try:
                breaker.call(failing_call)
            except (Exception, CircuitOpenError):
                pass

        # Run concurrent failures
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_call, i) for i in range(50)]
            for f in futures:
                f.result()

        # Circuit should be open
        assert breaker.state == CircuitState.OPEN

        # Not all calls should have executed (some rejected after circuit opened)
        assert call_count[0] < 50

    def test_rotation_tracker_concurrent_updates(self):
        """Verify rotation tracker handles concurrent rotation checks."""
        results = []

        def check_rotation(creator_suffix):
            tracker = PPVRotationTracker(f"concurrent_test_{creator_suffix}")
            ppv_type = tracker.get_next_ppv_type(0)
            results.append(ppv_type)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_rotation, i) for i in range(100)]
            for f in futures:
                f.result()

        # All results should be valid PPV types
        valid_types = {'solo', 'bundle', 'winner', 'sextape'}
        for result in results:
            assert result in valid_types, f"Invalid PPV type: {result}"


class TestBoundaryConditions:
    """Tests for edge cases and boundary conditions."""

    def test_followup_at_2359(self):
        """Followup for PPV at 23:30 should handle day boundary."""
        parent_time = datetime(2025, 1, 15, 23, 30)

        # Without allow_next_day, should clamp to 23:59
        followup = schedule_ppv_followup(
            parent_time, "boundary_test", allow_next_day=False
        )
        assert followup.date() == parent_time.date()
        assert followup.hour == 23
        assert followup.minute == 59

    def test_followup_at_2350_with_next_day(self):
        """Followup for late PPV with allow_next_day should cross midnight."""
        parent_time = datetime(2025, 1, 15, 23, 50)

        followup = schedule_ppv_followup(
            parent_time, "boundary_test", allow_next_day=True
        )

        # Should be valid window even if crosses midnight
        gap = (followup - parent_time).total_seconds() / 60
        assert 15 <= gap <= 45

    def test_empty_schedule_validation(self):
        """Empty schedule should pass validation."""
        from ..orchestration.timing_validator import validate_no_consecutive_same_style

        result = validate_no_consecutive_same_style([])
        assert result['is_valid'] is True

    def test_single_item_schedule(self):
        """Single item schedule should pass validation."""
        from ..orchestration.timing_validator import validate_no_consecutive_same_style

        schedule = [{'is_ppv': True, 'ppv_style': 'winner', 'hour': 14}]
        result = validate_no_consecutive_same_style(schedule)
        assert result['is_valid'] is True

    def test_rotation_on_day_zero(self):
        """New creator should get valid initial pattern."""
        tracker = PPVRotationTracker("new_creator_test")

        # First call should work
        ppv_type = tracker.get_next_ppv_type(0)
        assert ppv_type in {'solo', 'bundle', 'winner', 'sextape'}

    def test_jitter_at_minute_zero(self):
        """Jitter starting at :00 should still avoid round minutes."""
        from ..orchestration.timing_optimizer import apply_time_jitter

        base_time = datetime(2025, 1, 15, 14, 0)  # Exactly on the hour
        jittered = apply_time_jitter(base_time, "zero_minute_test")

        assert jittered.minute not in {0, 15, 30, 45}

    def test_jitter_at_minute_59(self):
        """Jitter starting at :59 should handle hour boundary."""
        from ..orchestration.timing_optimizer import apply_time_jitter

        base_time = datetime(2025, 1, 15, 14, 59)
        jittered = apply_time_jitter(base_time, "edge_minute_test")

        # Should be valid minute (not round) and could wrap to next hour
        assert jittered.minute not in {0, 15, 30, 45}


class TestRecovery:
    """Tests for failure recovery and compensation."""

    @pytest.mark.asyncio
    async def test_saga_compensation_on_failure(self):
        """Saga should compensate all completed steps on failure."""
        saga = Wave2TimingSaga("recovery_test")

        # Mock to fail on step 3
        with patch.object(saga, '_generate_followups', side_effect=Exception("Simulated failure")):
            result = await saga.execute([
                {'id': '1', 'scheduled_time': datetime.now()},
                {'id': '2', 'scheduled_time': datetime.now()}
            ])

        assert result.status == SagaStatus.ROLLED_BACK
        assert "rotation_update" in result.completed_steps
        assert "schedule_validation" in result.completed_steps
        assert result.failed_step is not None

    @pytest.mark.asyncio
    async def test_saga_timeout_handling(self):
        """Saga should handle step timeouts gracefully."""
        saga = Wave2TimingSaga("timeout_test")

        async def slow_rotation(*args):
            await asyncio.sleep(60)  # Simulate very slow operation

        with patch.object(saga, '_apply_rotation', slow_rotation):
            result = await saga.execute([])

        assert result.status in [SagaStatus.ROLLED_BACK, SagaStatus.FAILED]
        assert "timed out" in result.error.lower()

    def test_circuit_breaker_recovery(self):
        """Circuit breaker should recover after timeout."""
        breaker = CircuitBreaker(
            name="recovery_test",
            failure_threshold=2,
            recovery_timeout=1  # 1 second for fast test
        )

        # Cause failures to open circuit
        for _ in range(3):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except:
                pass

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        import time
        time.sleep(1.5)

        # Should transition to half-open
        assert breaker.state == CircuitState.HALF_OPEN

        # Successful call should close circuit
        breaker.call(lambda: "success")
        breaker.call(lambda: "success")
        breaker.call(lambda: "success")

        assert breaker.state == CircuitState.CLOSED

    def test_idempotency_expiration(self):
        """Idempotency records should expire after TTL."""
        import time

        guard = IdempotencyGuard(ttl_minutes=0)  # Immediate expiration for test

        # Store an operation
        guard.check_and_store("test", {"key": "value"}, "result1")

        # Wait a moment
        time.sleep(0.1)

        # Should be able to execute again (not duplicate)
        is_dup, _ = guard.check_and_store("test", {"key": "value"}, "result2")
        assert not is_dup  # Should not be duplicate due to expiration


class TestStateTransitions:
    """Tests for state machine transition validation."""

    def test_valid_state_transitions(self):
        """All defined transitions should be valid."""
        from ..orchestration.rotation_tracker import (
            RotationState, VALID_TRANSITIONS, validate_transition
        )

        for state, valid_targets in VALID_TRANSITIONS.items():
            for target in valid_targets:
                assert validate_transition(state, target), \
                    f"Transition {state} -> {target} should be valid"

    def test_invalid_state_transitions(self):
        """Invalid transitions should be rejected."""
        from ..orchestration.rotation_tracker import (
            RotationState, validate_transition, transition_to, InvalidTransitionError
        )

        # Cannot go from INITIALIZING directly to ROTATING
        assert not validate_transition(
            RotationState.INITIALIZING,
            RotationState.ROTATING
        )

        # Cannot go from PATTERN_EXHAUSTED to ERROR
        assert not validate_transition(
            RotationState.PATTERN_EXHAUSTED,
            RotationState.ERROR
        )

        # transition_to should raise for invalid transitions
        with pytest.raises(InvalidTransitionError):
            transition_to(RotationState.INITIALIZING, RotationState.ROTATING)

    def test_error_recovery_transition(self):
        """Error state should only transition to INITIALIZING."""
        from ..orchestration.rotation_tracker import (
            RotationState, VALID_TRANSITIONS
        )

        valid_from_error = VALID_TRANSITIONS[RotationState.ERROR]
        assert valid_from_error == [RotationState.INITIALIZING]
```

---

## SUCCESS CRITERIA

### Must Pass Before Wave Exit

- [ ] **PPV Rotation**
  - Pattern tracked per creator
  - Pattern changes every 3-4 days
  - Multiple rotation methods working (reverse, shuffle, new)

- [ ] **Same-Style Prevention**
  - Validator catches winner/winner violations
  - Validator catches bundle/bundle violations
  - AM/PM split enforced for duplicates

- [ ] **Followup Window**
  - 100% of followups within 15-45 min window
  - Deterministic seeding produces consistent results
  - No fixed 20-minute offsets

- [ ] **Link Drop Expiration**
  - All link drops have expiration_time field
  - Expiration set to +24 hours from scheduled time

- [ ] **Pinned Post Rotation**
  - Max 5 pins enforced
  - 72-hour lifecycle implemented
  - Priority-based replacement working

- [ ] **Jitter Implementation & Verification**
  - `apply_time_jitter()` function implemented
  - All tests passing for round minute avoidance
  - Determinism verified
  - Range (-7 to +8 min) verified
  - Followup timing applies jitter correctly

- [ ] **State Machine & Transitions**
  - RotationState enum defined with all states
  - VALID_TRANSITIONS map enforced
  - Invalid transitions raise InvalidTransitionError
  - State transition diagram documented

- [ ] **Saga Coordinator**
  - Wave2TimingSaga handles all 4 steps
  - Compensation executes in reverse order on failure
  - Step timeouts handled gracefully
  - SagaResult captures full execution details

- [ ] **Observability**
  - TimingMetrics logs all rotation changes
  - Followup scheduling logged with gap analysis
  - Jitter application tracked
  - Validation results logged with repair details

- [ ] **Resilience Patterns**
  - IdempotencyGuard prevents duplicate operations
  - CircuitBreaker protects database operations
  - Fallback values defined for open circuits
  - TTL-based expiration working

- [ ] **CreatorTimingProfile Integration**
  - TimingProfileIntegration class implemented
  - Creator-specific followup windows calculated
  - AM/PM preferences respected
  - Jitter adjusted per creator style

---

## QUALITY GATES

### 1. Unit Test Coverage
- [ ] All new functions have 90%+ coverage
- [ ] Edge cases tested (empty schedules, single items)

### 2. Integration Test
- [ ] Generate 14-day schedule
- [ ] Verify rotation changes at least 3 times
- [ ] Verify zero back-to-back violations

### 3. Timing Test
- [ ] Generate 50 followups
- [ ] Verify 100% in 15-45 min window
- [ ] Verify no :00, :15, :30, :45 minutes

### 4. Performance Test
- [ ] Rotation tracking adds <10ms
- [ ] Full validation suite <500ms

### 5. Concurrency Tests
- [ ] IdempotencyGuard thread safety verified (100 concurrent threads)
- [ ] CircuitBreaker handles concurrent failures correctly
- [ ] Rotation tracker handles concurrent updates

### 6. Boundary Condition Tests
- [ ] Followup at 23:30 handles day boundary
- [ ] Followup with allow_next_day crosses midnight correctly
- [ ] Empty and single-item schedules pass validation
- [ ] Jitter at minute :00 and :59 handled

### 7. Recovery Tests
- [ ] Saga compensation on failure verified
- [ ] Saga timeout handling verified
- [ ] Circuit breaker recovery after timeout verified
- [ ] Idempotency expiration verified

### 8. State Transition Tests
- [ ] All valid transitions pass validation
- [ ] Invalid transitions raise InvalidTransitionError
- [ ] Error state only transitions to INITIALIZING

---

## WAVE EXIT CHECKLIST

Before proceeding to Wave 3:

- [ ] All 6 original gaps implemented
- [ ] All 9 tasks completed (2.1 through 2.9)
- [ ] Formal state machine (RotationState) implemented
- [ ] SQLite-compatible schema deployed
- [ ] Wave2TimingSaga coordinator functional
- [ ] TimingMetrics observability integrated
- [ ] Truncated normal distribution for followups implemented
- [ ] Day boundary handling with allow_next_day parameter
- [ ] validate_and_repair_consecutive_styles() functional
- [ ] IdempotencyGuard preventing duplicates
- [ ] CircuitBreaker protecting database operations
- [ ] CreatorTimingProfile integration complete
- [ ] All unit tests passing (including advanced tests)
- [ ] All concurrency tests passing
- [ ] All boundary condition tests passing
- [ ] All recovery tests passing
- [ ] All state transition tests passing
- [ ] Code review completed
- [ ] Quality gates verified
- [ ] Database migrations applied

---

## ROLLBACK PROCEDURE

If Wave 2 needs to be rolled back:

1. Disable rotation tracker (use random selection)
2. Remove same-style validator
3. Revert followup to fixed 20-minute offset
4. Remove expiration_time field processing
5. Disable pinned post manager
6. Keep jitter as-is (verification only)

---

**Wave 2 Ready for Execution (after Wave 1)**
