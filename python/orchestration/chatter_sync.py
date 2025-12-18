"""
Chatter Content Sync Tool for synchronized content manifest generation.

Provides tools for chatter teams to receive synchronized content manifests
that coordinate DM-based sends with the main schedule.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


# Channels relevant to chatter team operations
CHATTER_CHANNELS: frozenset[str] = frozenset({
    "mass_message",
    "targeted_message",
})

# Send types that require chatter team involvement
CHATTER_SEND_TYPES: frozenset[str] = frozenset({
    "dm_farm",
    "ppv_unlock",
    "expired_winback",
    "vip_program",
    "first_to_tip",
})


class ChatterContentSync:
    """Stateless synchronizer for generating chatter team content manifests.

    This class provides methods to filter schedule items relevant to the chatter
    team and generate structured manifests for coordination purposes.

    Example:
        >>> sync = ChatterContentSync()
        >>> manifest = sync.generate_chatter_content_manifest(schedule, "creator_123")
        >>> print(manifest["total_items"])
    """

    def generate_chatter_content_manifest(
        self,
        schedule: list[dict[str, Any]],
        creator_id: str,
    ) -> dict[str, Any]:
        """Generate a comprehensive content manifest for chatter team coordination.

        Filters schedule items to those relevant for chatter operations and
        organizes them into a structured manifest grouped by date.

        Args:
            schedule: List of schedule items containing send_type, channel,
                content details, and timing information.
            creator_id: Unique identifier for the creator.

        Returns:
            Dictionary containing:
                - creator_id: The creator identifier
                - generated_at: ISO timestamp of manifest generation
                - total_items: Count of chatter-relevant items
                - manifest_by_date: Items grouped by schedule_date
                - manifest_all: Flat list of all manifest items
                - chatter_instructions: List of coordination instructions
        """
        manifest_items: list[dict[str, Any]] = []

        for item in schedule:
            send_type = item.get("send_type", "")
            channel = item.get("channel", "")

            if not self._is_chatter_relevant(send_type, channel):
                continue

            manifest_item: dict[str, Any] = {
                "schedule_date": item.get("schedule_date"),
                "send_type": send_type,
                "channel": channel,
                "content_id": item.get("content_id"),
                "content_type": item.get("content_type"),
                "caption_text": item.get("caption_text"),
                "price": item.get("price"),
                "audience_target": item.get("audience_target"),
                "label": item.get("label"),
                "special_notes": self._generate_chatter_notes(item),
            }
            manifest_items.append(manifest_item)

        # Group items by date for easier coordination
        manifest_by_date: dict[str, list[dict[str, Any]]] = {}
        for manifest_item in manifest_items:
            date_key = manifest_item.get("schedule_date") or "unscheduled"
            if date_key not in manifest_by_date:
                manifest_by_date[date_key] = []
            manifest_by_date[date_key].append(manifest_item)

        return {
            "creator_id": creator_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_items": len(manifest_items),
            "manifest_by_date": manifest_by_date,
            "manifest_all": manifest_items,
            "chatter_instructions": self._generate_chatter_instructions(schedule),
        }

    def _is_chatter_relevant(self, send_type: str, channel: str) -> bool:
        """Determine if a schedule item is relevant for chatter team operations.

        An item is chatter-relevant if it uses a chatter channel (mass_message,
        targeted_message) OR uses a send type that requires chatter involvement.

        Args:
            send_type: The send type key (e.g., "ppv_unlock", "dm_farm").
            channel: The distribution channel (e.g., "mass_message", "wall_post").

        Returns:
            True if the item requires chatter team attention, False otherwise.
        """
        return channel in CHATTER_CHANNELS or send_type in CHATTER_SEND_TYPES

    def _generate_chatter_notes(self, item: dict[str, Any]) -> str | None:
        """Generate special handling notes for chatter team based on item attributes.

        Different send types and audience targets require specific chatter behaviors.
        This method generates appropriate guidance notes.

        Args:
            item: Schedule item dictionary containing send_type, audience_target,
                price, and other relevant fields.

        Returns:
            Concatenated notes string separated by " | ", or None if no special
            handling is required.
        """
        notes: list[str] = []
        send_type = item.get("send_type", "")
        audience_target = item.get("audience_target", "")
        price = item.get("price")

        if send_type == "first_to_tip":
            price_display = f"${price}" if price else "$XX"
            notes.append(f"Monitor for first tipper - award {price_display} content")

        if send_type == "vip_program":
            notes.append("VIP campaign - premium engagement required")

        if audience_target == "high_spenders":
            notes.append("High-value audience - personalized responses recommended")

        if send_type == "expired_winback":
            notes.append("Expired sub winback - be extra engaging")

        return " | ".join(notes) if notes else None

    def _generate_chatter_instructions(
        self,
        schedule: list[dict[str, Any]],
    ) -> list[str]:
        """Generate coordination instructions for chatter team based on schedule.

        Base instructions are always included, with additional context-specific
        instructions added based on the schedule contents.

        Args:
            schedule: Full schedule list to analyze for special requirements.

        Returns:
            List of instruction strings for chatter team coordination.
        """
        instructions: list[str] = [
            "Review manifest items before each scheduled time slot",
            "Match DM content with scheduled send types for consistency",
            "Use provided captions as conversation starters, adapt to subscriber tone",
            "Track first-to-tip competitions and award winners promptly",
        ]

        # Check for VIP content in schedule
        has_vip = any(
            item.get("send_type") == "vip_program"
            for item in schedule
        )

        if has_vip:
            instructions.append(
                "VIP program sends require priority attention and premium engagement"
            )

        return instructions


def export_chatter_manifest_json(
    schedule: list[dict[str, Any]],
    creator_id: str,
    output_path: str,
) -> str:
    """Export chatter content manifest to a JSON file.

    Convenience function that creates a manifest and writes it to disk.

    Args:
        schedule: List of schedule items to process.
        creator_id: Unique identifier for the creator.
        output_path: File path where the JSON manifest will be written.

    Returns:
        The output_path where the manifest was written.

    Example:
        >>> path = export_chatter_manifest_json(schedule, "creator_123", "/tmp/manifest.json")
        >>> print(f"Manifest exported to: {path}")
    """
    sync = ChatterContentSync()
    manifest = sync.generate_chatter_content_manifest(schedule, creator_id)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    return output_path
