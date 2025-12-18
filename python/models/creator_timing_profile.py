"""
Creator Timing Profile - Per-creator timing characteristics.

Generates unique, deterministic timing characteristics for each creator
based on their creator_id. This ensures:
- Same creator always gets consistent timing patterns
- Different creators have different scheduling "personalities"
- Variation is deterministic and reproducible
"""

import hashlib
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class CreatorTimingProfile:
    """Unique timing characteristics per creator.

    Generates deterministic but varied timing parameters based on
    creator_id hash. This creates per-creator scheduling "personalities"
    that remain consistent across schedule generations.

    Attributes:
        creator_id: The creator identifier
        seed: Deterministic seed derived from creator_id
        base_jitter_offset: Creator-specific jitter bias (-5 to +5 minutes)
        preferred_start_hour: Day start preference (7-10 AM)
        preferred_end_hour: Day end preference (21-23)
        strategy_rotation_offset: Offset for strategy rotation (0-4)
        time_clustering_preference: Tendency for time distribution
        prime_hour_shift: Shift applied to prime hours (-1 to +1)
    """

    creator_id: str
    seed: int
    base_jitter_offset: int
    preferred_start_hour: int
    preferred_end_hour: int
    strategy_rotation_offset: int
    time_clustering_preference: Literal[
        "spread_evenly", "cluster_morning", "cluster_evening", "balanced"
    ]
    prime_hour_shift: int

    @classmethod
    def from_creator_id(cls, creator_id: str) -> "CreatorTimingProfile":
        """Create a timing profile from a creator_id.

        Generates all timing characteristics deterministically from the
        creator_id using MD5 hashing. Same creator_id always produces
        identical profile.

        Args:
            creator_id: The creator identifier (page_name or creator_id)

        Returns:
            CreatorTimingProfile with all characteristics derived from id
        """
        if not creator_id:
            # Default profile for empty creator_id
            return cls(
                creator_id="",
                seed=0,
                base_jitter_offset=0,
                preferred_start_hour=8,
                preferred_end_hour=22,
                strategy_rotation_offset=0,
                time_clustering_preference="balanced",
                prime_hour_shift=0
            )

        # Generate deterministic seed from creator_id
        seed = int(hashlib.md5(creator_id.encode()).hexdigest()[:8], 16)

        # Derive all characteristics from seed
        clustering_options: list[Literal[
            "spread_evenly", "cluster_morning", "cluster_evening", "balanced"
        ]] = ["spread_evenly", "cluster_morning", "cluster_evening", "balanced"]

        return cls(
            creator_id=creator_id,
            seed=seed,
            # Jitter bias: -5 to +5 minutes
            base_jitter_offset=(seed % 11) - 5,
            # Day start: 7-10 AM
            preferred_start_hour=7 + (seed % 4),
            # Day end: 21-23 (9-11 PM)
            preferred_end_hour=21 + (seed % 3),
            # Strategy rotation offset: 0-4
            strategy_rotation_offset=seed % 5,
            # Time clustering preference
            time_clustering_preference=clustering_options[seed % len(clustering_options)],
            # Prime hour shift: -1, 0, or +1
            prime_hour_shift=(seed % 3) - 1
        )

    def apply_jitter_bias(self, base_jitter: int) -> int:
        """Apply creator-specific bias to jitter value.

        Shifts the base jitter by the creator's bias, creating
        unique timing patterns per creator.

        Args:
            base_jitter: Base jitter value in minutes

        Returns:
            Biased jitter value, clamped to reasonable range
        """
        biased = base_jitter + self.base_jitter_offset
        # Clamp to -10 to +10 range
        return max(-10, min(10, biased))

    def adjust_hour_for_preference(self, hour: int) -> int:
        """Adjust an hour based on creator's day boundaries.

        Ensures hours fall within creator's preferred active window.

        Args:
            hour: Hour to adjust (0-23)

        Returns:
            Hour clamped to creator's preferred window
        """
        return max(self.preferred_start_hour, min(self.preferred_end_hour, hour))

    def should_cluster_at_time(self, hour: int) -> bool:
        """Check if this hour aligns with creator's clustering preference.

        Used to give bonus scores to times that match creator's
        natural posting rhythm.

        Args:
            hour: Hour to check (0-23)

        Returns:
            True if this hour matches clustering preference
        """
        if self.time_clustering_preference == "cluster_morning":
            return 8 <= hour <= 12
        elif self.time_clustering_preference == "cluster_evening":
            return 18 <= hour <= 22
        elif self.time_clustering_preference == "spread_evenly":
            # Prefer off-peak hours for spreading
            return hour in [9, 11, 13, 16, 18, 20]
        else:  # balanced
            return True  # No strong preference

    def get_adjusted_prime_hours(self, base_prime_hours: list[int]) -> list[int]:
        """Apply creator's prime hour shift to base prime hours.

        Args:
            base_prime_hours: Standard prime hours list

        Returns:
            Shifted prime hours unique to this creator
        """
        adjusted = []
        for hour in base_prime_hours:
            new_hour = hour + self.prime_hour_shift
            # Clamp to valid range
            new_hour = max(6, min(23, new_hour))
            adjusted.append(new_hour)
        return adjusted

    def __repr__(self) -> str:
        """Concise representation for debugging."""
        return (
            f"CreatorTimingProfile('{self.creator_id}': "
            f"jitter={self.base_jitter_offset:+d}, "
            f"hours={self.preferred_start_hour}-{self.preferred_end_hour}, "
            f"cluster={self.time_clustering_preference})"
        )
