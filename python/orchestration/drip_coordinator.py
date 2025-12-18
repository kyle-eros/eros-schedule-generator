"""
Drip Set Coordinator - Wave 4 Task 4.5 (Gap 1.4)

Creates 4-8 hour immersive windows with NO buying opportunities.
CRITICAL: PPVs during drip windows break immersion and reduce chatter revenue by 40-60%.

Architecture:
- Frozen dataclass DripWindow with slots for memory efficiency
- Strict validation: NO revenue types during drip window
- Allowed: bump types, dm_farm, like_farm, ppv_followup only
- Blocked: ALL revenue sends (9 types) + link drops + retention sends
- Robust hour extraction from both 'hour' and 'scheduled_time' fields

Version: 2.2.0
"""

import random
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any, List, Dict, Optional, Set

from python.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DripWindow:
    """
    Immutable representation of a drip set coordination window.

    A drip window is a 4-8 hour period where only engagement content
    is allowed, creating immersion for chatter revenue.
    """
    start_hour: int
    end_hour: int
    outfit_id: str
    allowed_types: tuple[str, ...]  # tuple for immutability
    blocked_types: tuple[str, ...]  # tuple for immutability


class DripSetCoordinator:
    """
    Coordinate 4-8hr drip windows with NO buying opportunities.
    Creates illusion of real-time presence for chatter engagement.
    """

    # Types ALLOWED during drip window (engagement only)
    # Updated to use 22-type taxonomy names
    ALLOWED_DURING_DRIP = (
        'bump_normal',      # Standard bump
        'bump_descriptive', # Detailed bump
        'bump_text_only',   # Text-only bump
        'bump_flyer',       # Flyer-style bump
        'dm_farm',          # DM engagement farming
        'like_farm',        # Like engagement farming
    )

    # PPV types that are allowed during drip (don't break immersion)
    ALLOWED_PPV_DURING_DRIP = ('ppv_followup',)  # Followups expected by user

    # Types BLOCKED during drip window (NO buying opportunities)
    # Updated to use 22-type taxonomy names from CLAUDE.md
    BLOCKED_DURING_DRIP = (
        # Revenue types (9 types)
        'ppv_unlock',       # Main PPV unlock
        'ppv_wall',         # Wall PPV
        'tip_goal',         # Tip goal
        'bundle',           # Bundle offer
        'flash_bundle',     # Flash/limited bundle
        'game_post',        # Game posts
        'first_to_tip',     # First-to-tip competitions
        'vip_program',      # VIP program offers
        'snapchat_bundle',  # Snapchat bundle offers

        # Engagement types that involve purchases
        'link_drop',        # Link drops (external purchases)
        'wall_link_drop',   # Wall link drops

        # Retention types (only on paid pages, but still block during drip)
        'renew_on_post',    # Renewal reminders on wall
        'renew_on_message', # Renewal reminders via DM
        'expired_winback',  # Expired subscriber winback
    )

    def __init__(self, creator_id: str):
        self.creator_id = creator_id
        logger.debug(f"Initialized DripSetCoordinator for creator: {creator_id}")

    def plan_drip_window(
        self,
        daily_schedule: List[Dict],
        vault_content: Optional[Dict] = None,
        preferred_start_hour: int = 14,  # 2 PM default
    ) -> DripWindow:
        """
        Plan a 4-8 hour drip window for the day.

        Args:
            daily_schedule: Current day's schedule
            vault_content: Available vault content with outfit IDs
            preferred_start_hour: Preferred start hour (default 2 PM)

        Returns:
            DripWindow configuration (immutable)
        """
        # Randomize duration between 4-8 hours
        duration = random.randint(4, 8)
        start_hour = preferred_start_hour
        end_hour = start_hour + duration

        # Ensure we don't go past midnight
        if end_hour > 24:
            end_hour = 24
            duration = end_hour - start_hour

        # Select outfit for this window
        outfit_id = self._select_outfit(vault_content)

        logger.info(f"Planned drip window: {start_hour}:00-{end_hour}:00 ({duration}h) with outfit {outfit_id}")

        return DripWindow(
            start_hour=start_hour,
            end_hour=end_hour,
            outfit_id=outfit_id,
            allowed_types=tuple(self.ALLOWED_DURING_DRIP),  # Ensure tuple
            blocked_types=tuple(self.BLOCKED_DURING_DRIP)   # Ensure tuple
        )

    def _extract_hour(self, item: Dict) -> int:
        """
        Extract hour from schedule item, handling both formats.

        Args:
            item: Schedule item dict

        Returns:
            Hour as integer (0-23)

        Handles:
            - 'hour' field as integer (e.g., 14)
            - 'scheduled_time' field as string (e.g., "14:30:00" or "2025-01-15T14:30:00")
        """
        # Try direct 'hour' field first
        if 'hour' in item:
            hour_val = item['hour']
            if isinstance(hour_val, (int, float)):
                return int(hour_val)

        # Try 'scheduled_time' string parsing
        if 'scheduled_time' in item:
            scheduled_time = item['scheduled_time']
            if isinstance(scheduled_time, str):
                # Handle ISO format with T separator
                if 'T' in scheduled_time:
                    time_part = scheduled_time.split('T')[1]
                else:
                    time_part = scheduled_time

                # Extract hour from HH:MM:SS or HH:MM format
                try:
                    hour_str = time_part.split(':')[0]
                    return int(hour_str)
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse scheduled_time: {scheduled_time}")

        # Default to 0 if unable to parse
        logger.warning(f"Could not extract hour from item: {item}")
        return 0

    def validate_drip_window(
        self,
        daily_schedule: List[Dict],
        drip_window: DripWindow
    ) -> Dict:
        """
        Validate that no buying opportunities are scheduled during drip window.

        CRITICAL: PPVs during drip windows BREAK immersion and reduce
        chatter revenue by 40-60%.

        Args:
            daily_schedule: List of schedule items for the day
            drip_window: The drip window to validate against

        Returns:
            Validation result dict with is_valid, violations, and message
        """
        violations = []

        for item in daily_schedule:
            # Use robust hour extraction (handles both 'hour' and 'scheduled_time')
            item_hour = self._extract_hour(item)
            send_type = item.get('send_type', '') or item.get('send_type_key', '')

            # Check if item is during drip window
            if drip_window.start_hour <= item_hour < drip_window.end_hour:
                # Check if it's a blocked type
                if send_type in drip_window.blocked_types:
                    violations.append({
                        'item': item,
                        'send_type': send_type,
                        'hour': item_hour,
                        'message': f"{send_type} at {item_hour}:00 violates drip window ({drip_window.start_hour}-{drip_window.end_hour})"
                    })
                elif send_type.startswith('ppv') or 'ppv' in send_type.lower():
                    # Catch any PPV-like types we might have missed
                    # But exclude allowed PPV types that don't break immersion
                    if send_type not in self.ALLOWED_PPV_DURING_DRIP:
                        violations.append({
                            'item': item,
                            'send_type': send_type,
                            'hour': item_hour,
                            'message': f"PPV-type '{send_type}' during drip window breaks immersion"
                        })

        if violations:
            logger.warning(f"DRIP VIOLATION: {len(violations)} buying opportunities during drip window")
            for v in violations:
                logger.warning(f"  - {v['send_type']} at {v['hour']}:00")
            return {
                'is_valid': False,
                'violations': violations,
                'violation_count': len(violations),
                'message': f"CRITICAL: {len(violations)} buying opportunities during drip window. Breaks immersion.",
                'action_required': 'Move all buying opportunities outside drip window'
            }

        logger.info(f"Drip window validated successfully: {drip_window.start_hour}:00-{drip_window.end_hour}:00")
        return {
            'is_valid': True,
            'drip_window': {
                'start': drip_window.start_hour,
                'end': drip_window.end_hour,
                'duration': drip_window.end_hour - drip_window.start_hour,
                'outfit': drip_window.outfit_id
            },
            'message': 'Drip window validated - no buying opportunities detected'
        }

    def _select_outfit(self, vault_content: Optional[Dict[str, Any]]) -> str:
        """Select outfit ID for drip window."""
        if vault_content and 'sexting_sets' in vault_content:
            sets = vault_content['sexting_sets']
            if sets:
                selected: str = random.choice(sets)['id']
                return selected

        return f"outfit_{random.randint(1000, 9999)}"

    def generate_drip_bumps(
        self,
        drip_window: DripWindow,
        bumps_per_hour: int = 1
    ) -> List[Dict]:
        """
        Generate bump schedule items for drip window.
        All bumps should use the same outfit for consistency.
        """
        bumps = []

        for hour in range(drip_window.start_hour, drip_window.end_hour):
            # Wall bump
            bumps.append({
                'send_type': 'bump_drip',
                'channel': 'wall_post',
                'hour': hour,
                'outfit_id': drip_window.outfit_id,
                'drip_window': True
            })

            # MM bump (staggered by 30 minutes)
            if hour + 0.5 < drip_window.end_hour:
                bumps.append({
                    'send_type': 'bump_drip',
                    'channel': 'mass_message',
                    'hour': hour + 0.5,
                    'outfit_id': drip_window.outfit_id,
                    'drip_window': True
                })

        return bumps
