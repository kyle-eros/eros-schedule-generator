"""
PPV Rotation Pattern Tracker for Wave 2 Timing.

Implements a state machine for managing PPV content type rotation patterns.
Patterns rotate every 3-4 days to provide natural variation in content
distribution while maintaining deterministic behavior for reproducibility.

The rotation system uses:
- 4 standard PPV patterns cycling through solo/bundle/winner/sextape variations
- Deterministic seeding based on creator_id for reproducible behavior
- State machine transitions for robust lifecycle management
- 3-4 day rotation with hash-based 50% chance on day 3

Usage:
    from python.orchestration.rotation_tracker import PPVRotationTracker

    tracker = PPVRotationTracker(creator_id="abc123")
    ppv_type = tracker.get_next_ppv_type(schedule_position=0)
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto
from typing import Any

import hashlib
import random

from python.logging_config import get_logger, log_fallback
from python.exceptions import EROSError

logger = get_logger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================


class InvalidTransitionError(EROSError):
    """Raised when an invalid state transition is attempted.

    This exception is raised when the rotation tracker attempts to move
    from one state to another that is not permitted by the state machine.

    Attributes:
        from_state: The current state before attempted transition
        to_state: The target state of the attempted transition
    """

    def __init__(
        self,
        from_state: "RotationState",
        to_state: "RotationState",
        message: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Initialize InvalidTransitionError.

        Args:
            from_state: The current state before attempted transition
            to_state: The target state of the attempted transition
            message: Optional custom message
            details: Optional dictionary with additional context
        """
        msg = message or (
            f"Invalid state transition: {from_state.name} -> {to_state.name}"
        )
        super().__init__(msg, code="E700", details=details)
        self.from_state = from_state
        self.to_state = to_state


# =============================================================================
# State Machine Definitions
# =============================================================================


class RotationState(Enum):
    """States for PPV rotation pattern lifecycle.

    The rotation tracker moves through these states as patterns are
    initialized, used, and rotated.

    States:
        INITIALIZING: Initial state when tracker is created
        PATTERN_ACTIVE: A pattern is currently in use and producing PPV types
        ROTATION_PENDING: Pattern is exhausted but rotation hasn't started
        ROTATING: Pattern rotation is in progress
        PATTERN_EXHAUSTED: Current pattern has been fully used
        ERROR: An error occurred during rotation
    """
    INITIALIZING = auto()
    PATTERN_ACTIVE = auto()
    ROTATION_PENDING = auto()
    ROTATING = auto()
    PATTERN_EXHAUSTED = auto()
    ERROR = auto()


# Valid state transitions for the rotation state machine
VALID_TRANSITIONS: dict[RotationState, set[RotationState]] = {
    RotationState.INITIALIZING: {
        RotationState.PATTERN_ACTIVE,
        RotationState.ERROR,
    },
    RotationState.PATTERN_ACTIVE: {
        RotationState.ROTATION_PENDING,
        RotationState.PATTERN_EXHAUSTED,
        RotationState.ERROR,
    },
    RotationState.ROTATION_PENDING: {
        RotationState.ROTATING,
        RotationState.ERROR,
    },
    RotationState.ROTATING: {
        RotationState.PATTERN_ACTIVE,
        RotationState.ERROR,
    },
    RotationState.PATTERN_EXHAUSTED: {
        RotationState.ROTATION_PENDING,
        RotationState.ROTATING,
        RotationState.ERROR,
    },
    RotationState.ERROR: {
        RotationState.INITIALIZING,  # Allow recovery through re-initialization
    },
}


def validate_transition(
    from_state: RotationState,
    to_state: RotationState
) -> bool:
    """Validate if a state transition is allowed.

    Args:
        from_state: The current state
        to_state: The target state

    Returns:
        True if transition is valid, False otherwise

    Examples:
        >>> validate_transition(RotationState.INITIALIZING, RotationState.PATTERN_ACTIVE)
        True
        >>> validate_transition(RotationState.PATTERN_ACTIVE, RotationState.INITIALIZING)
        False
    """
    valid_targets = VALID_TRANSITIONS.get(from_state, set())
    return to_state in valid_targets


def transition_to(
    current_state: RotationState,
    target_state: RotationState
) -> RotationState:
    """Perform a validated state transition.

    Validates the transition and returns the new state if valid.
    Raises InvalidTransitionError if the transition is not allowed.

    Args:
        current_state: The current state
        target_state: The desired target state

    Returns:
        The new state after successful transition

    Raises:
        InvalidTransitionError: If the transition is not valid

    Examples:
        >>> state = transition_to(RotationState.INITIALIZING, RotationState.PATTERN_ACTIVE)
        >>> state == RotationState.PATTERN_ACTIVE
        True
    """
    if not validate_transition(current_state, target_state):
        raise InvalidTransitionError(
            from_state=current_state,
            to_state=target_state,
            details={
                "valid_transitions": [
                    s.name for s in VALID_TRANSITIONS.get(current_state, set())
                ]
            }
        )
    return target_state


# =============================================================================
# Rotation State Data Model
# =============================================================================


@dataclass
class RotationStateData:
    """Persistent state data for rotation tracking.

    Stores all information needed to persist and restore rotation state
    across sessions.

    Attributes:
        creator_id: The creator this state belongs to
        current_pattern_index: Index of current pattern in STANDARD_PATTERNS
        current_position: Position within the current pattern
        pattern_start_date: When the current pattern started
        days_on_pattern: Number of days using current pattern
        state: Current state machine state
        last_updated: Timestamp of last update
    """
    creator_id: str
    current_pattern_index: int = 0
    current_position: int = 0
    pattern_start_date: date = field(default_factory=date.today)
    days_on_pattern: int = 0
    state: RotationState = RotationState.INITIALIZING
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert state data to dictionary for persistence.

        Returns:
            Dictionary representation suitable for database storage
        """
        return {
            "creator_id": self.creator_id,
            "current_pattern_index": self.current_pattern_index,
            "current_position": self.current_position,
            "pattern_start_date": self.pattern_start_date.isoformat(),
            "days_on_pattern": self.days_on_pattern,
            "state": self.state.name,
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RotationStateData":
        """Create RotationStateData from dictionary.

        Args:
            data: Dictionary with state data fields

        Returns:
            RotationStateData instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        return cls(
            creator_id=data["creator_id"],
            current_pattern_index=data.get("current_pattern_index", 0),
            current_position=data.get("current_position", 0),
            pattern_start_date=date.fromisoformat(data["pattern_start_date"])
            if isinstance(data.get("pattern_start_date"), str)
            else data.get("pattern_start_date", date.today()),
            days_on_pattern=data.get("days_on_pattern", 0),
            state=RotationState[data["state"]]
            if isinstance(data.get("state"), str)
            else data.get("state", RotationState.INITIALIZING),
            last_updated=datetime.fromisoformat(data["last_updated"])
            if isinstance(data.get("last_updated"), str)
            else data.get("last_updated", datetime.now()),
        )


# =============================================================================
# Database Placeholder Functions
# =============================================================================


def db_get_creator_rotation_state(creator_id: str) -> dict[str, Any] | None:
    """Load rotation state from database for a creator.

    Placeholder function for database integration. Replace with actual
    database implementation.

    Args:
        creator_id: The creator ID to look up

    Returns:
        Dictionary with state data if found, None otherwise
    """
    # TODO: Implement actual database lookup
    # Example query:
    # SELECT * FROM creator_rotation_state WHERE creator_id = ?
    logger.debug(
        "Database lookup for rotation state",
        extra={"creator_id": creator_id, "operation": "db_get_creator_rotation_state"}
    )
    return None


def db_save_creator_rotation_state(
    creator_id: str,
    state_data: dict[str, Any]
) -> bool:
    """Save rotation state to database for a creator.

    Placeholder function for database integration. Replace with actual
    database implementation.

    Args:
        creator_id: The creator ID to save for
        state_data: Dictionary with state data to persist

    Returns:
        True if save successful, False otherwise
    """
    # TODO: Implement actual database save
    # Example query:
    # INSERT OR REPLACE INTO creator_rotation_state (creator_id, ...) VALUES (?, ...)
    logger.debug(
        "Database save for rotation state",
        extra={
            "creator_id": creator_id,
            "operation": "db_save_creator_rotation_state",
            "state_data": state_data
        }
    )
    return True


# =============================================================================
# PPV Rotation Tracker
# =============================================================================


class PPVRotationTracker:
    """Manages PPV content type rotation patterns.

    Tracks and rotates through PPV content type patterns to ensure variety
    in content distribution. Each creator has their own rotation state that
    persists across schedule generation sessions.

    The tracker uses a deterministic seeding mechanism based on creator_id
    to ensure reproducible behavior while maintaining natural variation.

    Attributes:
        STANDARD_PATTERNS: List of 4 PPV type patterns to rotate through
        creator_id: The creator this tracker manages
        state_data: Current rotation state data
        _rng: Random number generator seeded by creator_id

    Examples:
        >>> tracker = PPVRotationTracker("creator_123")
        >>> ppv_type = tracker.get_next_ppv_type(0)
        >>> ppv_type in ['solo', 'bundle', 'winner', 'sextape']
        True
    """

    # Standard rotation patterns - each pattern provides variety in PPV types
    # Patterns rotate every 3-4 days for natural variation
    STANDARD_PATTERNS: list[list[str]] = [
        ["solo", "bundle", "winner", "sextape"],
        ["bundle", "sextape", "solo", "winner"],
        ["winner", "solo", "sextape", "bundle"],
        ["sextape", "winner", "bundle", "solo"],
    ]

    def __init__(self, creator_id: str) -> None:
        """Initialize PPVRotationTracker for a creator.

        Loads existing state from database or initializes new state
        if this is a new creator.

        Args:
            creator_id: Unique identifier for the creator

        Raises:
            ValueError: If creator_id is empty
        """
        if not creator_id or not creator_id.strip():
            raise ValueError("creator_id cannot be empty")

        self.creator_id = creator_id
        self._rng = self._create_seeded_rng(creator_id)
        self.state_data = self._load_or_initialize()

        logger.info(
            "PPVRotationTracker initialized",
            extra={
                "creator_id": creator_id,
                "state": self.state_data.state.name,
                "pattern_index": self.state_data.current_pattern_index,
                "days_on_pattern": self.state_data.days_on_pattern,
            }
        )

    def _create_seeded_rng(self, creator_id: str) -> random.Random:
        """Create a deterministically seeded random number generator.

        Uses MD5 hash of creator_id to create a consistent seed,
        ensuring reproducible random behavior for each creator.

        Args:
            creator_id: The creator ID to seed from

        Returns:
            Seeded Random instance
        """
        # Use MD5 hash for deterministic seeding
        hash_bytes = hashlib.md5(creator_id.encode("utf-8")).digest()
        seed = int.from_bytes(hash_bytes[:8], byteorder="big")
        return random.Random(seed)

    def _load_or_initialize(self) -> RotationStateData:
        """Load existing state from database or create new state.

        Attempts to load persisted state for the creator. If no state
        exists, creates a new state with the first pattern.

        Returns:
            RotationStateData with loaded or initialized state
        """
        # Attempt to load from database
        db_state = db_get_creator_rotation_state(self.creator_id)

        if db_state is not None:
            try:
                state_data = RotationStateData.from_dict(db_state)
                # Validate and potentially recover from ERROR state
                if state_data.state == RotationState.ERROR:
                    logger.warning(
                        "Recovering from ERROR state",
                        extra={"creator_id": self.creator_id}
                    )
                    state_data.state = transition_to(
                        state_data.state, RotationState.INITIALIZING
                    )
                    state_data.state = transition_to(
                        state_data.state, RotationState.PATTERN_ACTIVE
                    )
                return state_data
            except (KeyError, ValueError) as e:
                log_fallback(
                    logger,
                    operation="load_rotation_state",
                    fallback_reason=f"Invalid stored state: {e}",
                    fallback_action="Initialize new state",
                    creator_id=self.creator_id
                )

        # Initialize new state
        initial_pattern_index = self._select_initial_pattern()
        state_data = RotationStateData(
            creator_id=self.creator_id,
            current_pattern_index=initial_pattern_index,
            current_position=0,
            pattern_start_date=date.today(),
            days_on_pattern=0,
            state=RotationState.INITIALIZING,
            last_updated=datetime.now(),
        )

        # Transition to PATTERN_ACTIVE
        state_data.state = transition_to(
            state_data.state, RotationState.PATTERN_ACTIVE
        )

        # Persist initial state
        self._save_state(state_data)

        return state_data

    def _select_initial_pattern(self) -> int:
        """Select initial pattern index using deterministic random.

        Uses the seeded RNG to select which pattern to start with,
        ensuring consistent starting point for each creator.

        Returns:
            Index into STANDARD_PATTERNS (0-3)
        """
        return self._rng.randint(0, len(self.STANDARD_PATTERNS) - 1)

    def _save_state(self, state_data: RotationStateData) -> None:
        """Persist state data to database.

        Args:
            state_data: State data to save
        """
        state_data.last_updated = datetime.now()
        success = db_save_creator_rotation_state(
            self.creator_id, state_data.to_dict()
        )
        if not success:
            logger.warning(
                "Failed to persist rotation state",
                extra={"creator_id": self.creator_id}
            )

    def get_next_ppv_type(self, schedule_position: int) -> str:
        """Get the next PPV type based on current rotation.

        Returns the appropriate PPV content type for the given schedule
        position, potentially triggering pattern rotation if conditions
        are met.

        Args:
            schedule_position: Position in the current schedule (0-indexed)

        Returns:
            PPV type string (e.g., 'solo', 'bundle', 'winner', 'sextape')

        Raises:
            InvalidTransitionError: If state machine is in invalid state
        """
        # Check for pattern rotation before returning type
        self._check_pattern_rotation()

        # Get current pattern
        pattern = self.STANDARD_PATTERNS[self.state_data.current_pattern_index]

        # Calculate position within pattern (wrap around)
        pattern_position = (
            self.state_data.current_position + schedule_position
        ) % len(pattern)

        ppv_type = pattern[pattern_position]

        logger.debug(
            "PPV type selected",
            extra={
                "creator_id": self.creator_id,
                "ppv_type": ppv_type,
                "schedule_position": schedule_position,
                "pattern_index": self.state_data.current_pattern_index,
                "pattern_position": pattern_position,
            }
        )

        return ppv_type

    def _check_pattern_rotation(self) -> None:
        """Check if pattern should rotate and trigger rotation if needed.

        Rotation conditions:
        - Day 3: 50% chance (deterministic based on hash)
        - Day 4+: Must rotate

        Uses hash-based deterministic decision for day-3 rotation to
        provide natural variation while maintaining reproducibility.
        """
        # Update days on pattern based on date change
        today = date.today()
        if self.state_data.pattern_start_date < today:
            days_elapsed = (today - self.state_data.pattern_start_date).days
            self.state_data.days_on_pattern = days_elapsed

        days = self.state_data.days_on_pattern

        # Day 4+: Must rotate
        if days >= 4:
            logger.info(
                "Pattern rotation triggered (day 4+)",
                extra={
                    "creator_id": self.creator_id,
                    "days_on_pattern": days,
                }
            )
            self._rotate_pattern()
            return

        # Day 3: 50% deterministic chance
        if days == 3:
            if self._should_rotate_on_day_3():
                logger.info(
                    "Pattern rotation triggered (day 3, hash decision)",
                    extra={
                        "creator_id": self.creator_id,
                        "days_on_pattern": days,
                    }
                )
                self._rotate_pattern()

    def _should_rotate_on_day_3(self) -> bool:
        """Determine if rotation should occur on day 3.

        Uses MD5 hash of creator_id + pattern_start_date for deterministic
        50% probability decision. This ensures:
        - Same decision for same creator on same day
        - Natural variation across different creators/dates
        - Reproducible behavior for testing

        Returns:
            True if rotation should occur, False otherwise
        """
        # Create deterministic hash from creator_id + date
        hash_input = f"{self.creator_id}:{self.state_data.pattern_start_date.isoformat()}"
        hash_bytes = hashlib.md5(hash_input.encode("utf-8")).digest()

        # Use first byte to determine 50% threshold
        decision_byte = hash_bytes[0]
        should_rotate = decision_byte < 128  # 50% threshold

        logger.debug(
            "Day 3 rotation decision",
            extra={
                "creator_id": self.creator_id,
                "hash_input": hash_input,
                "decision_byte": decision_byte,
                "should_rotate": should_rotate,
            }
        )

        return should_rotate

    def _rotate_pattern(self) -> None:
        """Rotate to a new pattern using one of three methods.

        Rotation methods:
        1. Reverse: Reverse current pattern order
        2. Shuffle: Deterministically shuffle current pattern
        3. New: Move to next pattern in STANDARD_PATTERNS

        Method selection is deterministic based on creator_id hash.
        """
        # Transition to ROTATING state
        if self.state_data.state == RotationState.PATTERN_ACTIVE:
            self.state_data.state = transition_to(
                self.state_data.state, RotationState.ROTATION_PENDING
            )
        if self.state_data.state in (
            RotationState.ROTATION_PENDING,
            RotationState.PATTERN_EXHAUSTED
        ):
            self.state_data.state = transition_to(
                self.state_data.state, RotationState.ROTATING
            )

        # Select rotation method deterministically
        method_selector = self._rng.randint(0, 2)

        if method_selector == 0:
            self._rotate_by_reverse()
        elif method_selector == 1:
            self._rotate_by_shuffle()
        else:
            self._rotate_to_new_pattern()

        # Reset pattern tracking
        self.state_data.pattern_start_date = date.today()
        self.state_data.days_on_pattern = 0
        self.state_data.current_position = 0

        # Transition to PATTERN_ACTIVE
        self.state_data.state = transition_to(
            self.state_data.state, RotationState.PATTERN_ACTIVE
        )

        # Persist updated state
        self._save_state(self.state_data)

        logger.info(
            "Pattern rotation completed",
            extra={
                "creator_id": self.creator_id,
                "new_pattern_index": self.state_data.current_pattern_index,
                "method": ["reverse", "shuffle", "new"][method_selector],
            }
        )

    def _rotate_by_reverse(self) -> None:
        """Rotate by reversing to mirror pattern index.

        Maps pattern 0 <-> 3 and pattern 1 <-> 2 to create reversed
        ordering effect.
        """
        current_index = self.state_data.current_pattern_index
        # Mirror index: 0->3, 1->2, 2->1, 3->0
        new_index = len(self.STANDARD_PATTERNS) - 1 - current_index
        self.state_data.current_pattern_index = new_index

        logger.debug(
            "Pattern rotated by reverse",
            extra={
                "creator_id": self.creator_id,
                "old_index": current_index,
                "new_index": new_index,
            }
        )

    def _rotate_by_shuffle(self) -> None:
        """Rotate by selecting a different pattern via deterministic shuffle.

        Uses seeded RNG to select next pattern, excluding current pattern.
        """
        current_index = self.state_data.current_pattern_index
        available_indices = [
            i for i in range(len(self.STANDARD_PATTERNS)) if i != current_index
        ]
        new_index = self._rng.choice(available_indices)
        self.state_data.current_pattern_index = new_index

        logger.debug(
            "Pattern rotated by shuffle",
            extra={
                "creator_id": self.creator_id,
                "old_index": current_index,
                "new_index": new_index,
            }
        )

    def _rotate_to_new_pattern(self) -> None:
        """Rotate to the next pattern in sequence.

        Cycles through patterns 0 -> 1 -> 2 -> 3 -> 0.
        """
        current_index = self.state_data.current_pattern_index
        new_index = (current_index + 1) % len(self.STANDARD_PATTERNS)
        self.state_data.current_pattern_index = new_index

        logger.debug(
            "Pattern rotated to next",
            extra={
                "creator_id": self.creator_id,
                "old_index": current_index,
                "new_index": new_index,
            }
        )

    def advance_position(self, count: int = 1) -> None:
        """Advance the current position within the pattern.

        Called after generating schedule items to track progress through
        the pattern.

        Args:
            count: Number of positions to advance (default 1)
        """
        pattern = self.STANDARD_PATTERNS[self.state_data.current_pattern_index]
        self.state_data.current_position = (
            self.state_data.current_position + count
        ) % len(pattern)
        self._save_state(self.state_data)

    def get_current_pattern(self) -> list[str]:
        """Get the current active pattern.

        Returns:
            List of PPV types in current pattern order
        """
        return self.STANDARD_PATTERNS[self.state_data.current_pattern_index].copy()

    def get_state(self) -> RotationState:
        """Get current state machine state.

        Returns:
            Current RotationState
        """
        return self.state_data.state

    def get_days_on_pattern(self) -> int:
        """Get number of days on current pattern.

        Returns:
            Days elapsed since pattern started
        """
        today = date.today()
        if self.state_data.pattern_start_date < today:
            return (today - self.state_data.pattern_start_date).days
        return self.state_data.days_on_pattern

    def force_rotation(self) -> None:
        """Force immediate pattern rotation.

        Useful for testing or manual intervention. Skips the day-based
        rotation checks.
        """
        logger.info(
            "Forced pattern rotation requested",
            extra={"creator_id": self.creator_id}
        )
        self._rotate_pattern()

    def reset_state(self) -> None:
        """Reset tracker to initial state.

        Clears all state and reinitializes with a fresh pattern.
        Useful for testing or recovery scenarios.
        """
        logger.info(
            "Resetting rotation state",
            extra={"creator_id": self.creator_id}
        )

        # Recreate RNG for fresh seed
        self._rng = self._create_seeded_rng(self.creator_id)

        # Create new initial state
        initial_pattern_index = self._select_initial_pattern()
        self.state_data = RotationStateData(
            creator_id=self.creator_id,
            current_pattern_index=initial_pattern_index,
            current_position=0,
            pattern_start_date=date.today(),
            days_on_pattern=0,
            state=RotationState.PATTERN_ACTIVE,
            last_updated=datetime.now(),
        )

        self._save_state(self.state_data)


# =============================================================================
# Export public API
# =============================================================================

__all__ = [
    # Exception
    "InvalidTransitionError",
    # Enum and state machine
    "RotationState",
    "VALID_TRANSITIONS",
    "validate_transition",
    "transition_to",
    # Data model
    "RotationStateData",
    # Database placeholders
    "db_get_creator_rotation_state",
    "db_save_creator_rotation_state",
    # Main class
    "PPVRotationTracker",
]
