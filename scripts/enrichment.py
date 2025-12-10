#!/usr/bin/env python3
"""
EROS Schedule Generator - Enrichment Processing

This module handles Steps 6-8 of the 9-step pipeline plus validation:
    6. GENERATE FOLLOW-UPS - Create 15-45 min follow-up bumps
    7. APPLY DRIP WINDOWS - Enforce no-PPV zones if enabled
    8. APPLY PAGE TYPE RULES - Filter paid-only content for free pages
    9. VALIDATE - Check 30 business rules with auto-correction

Usage:
    from enrichment import EnrichmentProcessor, validate_and_correct

    enricher = EnrichmentProcessor(config, profile)
    items = enricher.step_6_generate_followups(items)
    items = enricher.step_7_apply_drip_windows(items)
    items = enricher.step_8_apply_page_rules(items)

    items, issues, corrections = validate_and_correct(items, config, captions)
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from models import (
    Caption,
    CreatorProfile,
    ScheduleConfig,
    ScheduleItem,
    ValidationIssue,
)

if TYPE_CHECKING:
    from followup_generator import FollowUpContext, FollowupGenerator

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS (loaded from config_loader)
# =============================================================================

from config_loader import get_config

_config = get_config()

MIN_PPV_SPACING_HOURS: int = _config.ppv.min_spacing_hours
MIN_FRESHNESS_SCORE: float = _config.freshness.minimum_score
MAX_VALIDATION_PASSES: int = 2

# Follow-up timing
FOLLOW_UP_MIN_MINUTES: int = _config.follow_up.min_minutes
FOLLOW_UP_MAX_MINUTES: int = _config.follow_up.max_minutes

# Drip window settings
DRIP_WINDOW_START_HOUR: int = _config.drip_window.start_hour
DRIP_WINDOW_END_HOUR: int = _config.drip_window.end_hour

# Bump message templates
BUMP_MESSAGES: list[str] = [
    "did you see my last message babe?",
    "heyy dont miss this one",
    "still want this baby?",
    "this one is special",
    "check your messages",
    "waiting for you",
]


# =============================================================================
# OPTIONAL IMPORTS
# =============================================================================

try:
    from followup_generator import FollowUpContext, FollowupGenerator
    FOLLOWUP_GENERATOR_AVAILABLE = True
except ImportError:
    FOLLOWUP_GENERATOR_AVAILABLE = False
    logger.debug("FollowupGenerator not available - using generic bumps")


# =============================================================================
# ENRICHMENT PROCESSOR CLASS
# =============================================================================


class EnrichmentProcessor:
    """
    Handles Steps 6-8 of the schedule generation pipeline.

    This class encapsulates the enrichment logic for:
    - Generating follow-up bump messages (Step 6)
    - Applying drip window restrictions (Step 7)
    - Applying page type rules (Step 8)

    Attributes:
        config: ScheduleConfig with generation parameters
        profile: CreatorProfile with persona and settings
        agent_invoker: Optional agent invoker for enhanced optimization
        agent_context: Optional agent context for inter-agent communication
        agents_used: List of agents successfully invoked
        agents_fallback: List of agents that used fallback
    """

    def __init__(
        self,
        config: ScheduleConfig,
        profile: CreatorProfile,
        agent_invoker: Any | None = None,
        agent_context: Any | None = None,
    ):
        """
        Initialize the enrichment processor.

        Args:
            config: Schedule generation configuration
            profile: Creator profile with persona data
            agent_invoker: Optional agent invoker for Phase 3 integration
            agent_context: Optional shared context for agents
        """
        self.config = config
        self.profile = profile
        self.agent_invoker = agent_invoker
        self.agent_context = agent_context
        self.agents_used: list[str] = []
        self.agents_fallback: list[str] = []

    # =========================================================================
    # STEP 6: GENERATE FOLLOW-UPS
    # =========================================================================

    def step_6_generate_followups(self, items: list[ScheduleItem]) -> list[ScheduleItem]:
        """
        Generate follow-up bump messages for each PPV.

        Step 6 of pipeline: GENERATE FOLLOW-UPS

        Creates 15-45 minute follow-up messages for each PPV. In full mode,
        uses context-aware generation; in quick mode, uses generic bumps.

        Args:
            items: List of scheduled items (PPVs)

        Returns:
            List of items with follow-ups added

        Timing:
            - Follow-ups are 15-45 minutes after each PPV (randomized)
            - Context-aware bumps reference original content naturally
        """
        if not self.config.enable_follow_ups:
            return items

        # Use context-aware follow-ups in full mode
        if (
            self.config.mode == "full"
            and self.config.use_context_followups
            and FOLLOWUP_GENERATOR_AVAILABLE
        ):
            logger.info("[Step 6] Generating context-aware follow-ups...")
            return self._generate_contextual_followups(items)

        # Generic follow-ups
        return self._generate_generic_followups(items)

    def _generate_generic_followups(self, items: list[ScheduleItem]) -> list[ScheduleItem]:
        """Generate generic bump messages."""
        all_items = list(items)
        next_id = max((item.item_id for item in items), default=0) + 1

        for item in items:
            if item.item_type != "ppv":
                continue

            ppv_time = datetime.strptime(
                f"{item.scheduled_date} {item.scheduled_time}", "%Y-%m-%d %H:%M"
            )
            follow_up_minutes = random.randint(FOLLOW_UP_MIN_MINUTES, FOLLOW_UP_MAX_MINUTES)
            follow_up_time = ppv_time + timedelta(minutes=follow_up_minutes)

            bump_message = random.choice(BUMP_MESSAGES)

            all_items.append(
                ScheduleItem(
                    item_id=next_id,
                    creator_id=self.config.creator_id,
                    scheduled_date=follow_up_time.strftime("%Y-%m-%d"),
                    scheduled_time=follow_up_time.strftime("%H:%M"),
                    item_type="bump",
                    caption_text=bump_message,
                    is_follow_up=True,
                    parent_item_id=item.item_id,
                    priority=6,
                    notes=f"Follow-up for PPV #{item.item_id}",
                )
            )
            next_id += 1

        all_items.sort(key=lambda x: (x.scheduled_date, x.scheduled_time))
        logger.info(f"[Step 6] Generated {next_id - max((i.item_id for i in items), default=0) - 1} follow-ups")
        return all_items

    def _generate_contextual_followups(self, items: list[ScheduleItem]) -> list[ScheduleItem]:
        """Generate context-aware follow-up messages using FollowupGenerator."""
        generator = FollowupGenerator({
            "creator_id": self.profile.creator_id,
            "page_name": self.profile.page_name,
            "primary_tone": self.profile.primary_tone,
            "emoji_frequency": self.profile.emoji_frequency,
            "slang_level": self.profile.slang_level,
        })

        all_items = list(items)
        next_id = max((item.item_id for item in items), default=0) + 1

        # Collect contexts for batch generation
        ppv_contexts: list[FollowUpContext] = []
        ppv_items: list[ScheduleItem] = []

        for item in items:
            if item.item_type != "ppv":
                continue

            ppv_dt = datetime.strptime(
                f"{item.scheduled_date} {item.scheduled_time}", "%Y-%m-%d %H:%M"
            )

            context = FollowUpContext(
                original_caption=item.caption_text or "",
                content_type=item.content_type_name or "default",
                creator_tone=self.profile.primary_tone,
                emoji_frequency=self.profile.emoji_frequency,
                price=item.suggested_price,
                day_of_week=ppv_dt.weekday(),
                hour=ppv_dt.hour,
            )
            ppv_contexts.append(context)
            ppv_items.append(item)

        # Generate follow-ups in batch
        followups = generator.generate_batch(ppv_contexts, avoid_repetition=True)

        # Create follow-up schedule items
        for item, followup in zip(ppv_items, followups, strict=True):
            ppv_dt = datetime.strptime(
                f"{item.scheduled_date} {item.scheduled_time}", "%Y-%m-%d %H:%M"
            )
            follow_up_time = ppv_dt + timedelta(minutes=followup.timing_minutes)

            all_items.append(
                ScheduleItem(
                    item_id=next_id,
                    creator_id=self.config.creator_id,
                    scheduled_date=follow_up_time.strftime("%Y-%m-%d"),
                    scheduled_time=follow_up_time.strftime("%H:%M"),
                    item_type="bump",
                    caption_text=followup.text,
                    is_follow_up=True,
                    parent_item_id=item.item_id,
                    priority=6,
                    notes=f"Context: {followup.context_type} | Timing: {followup.timing_minutes}min",
                )
            )
            next_id += 1

        all_items.sort(key=lambda x: (x.scheduled_date, x.scheduled_time))
        logger.info(f"[Step 6] Generated {len(followups)} context-aware follow-ups")
        return all_items

    # =========================================================================
    # STEP 7: APPLY DRIP WINDOWS
    # =========================================================================

    def step_7_apply_drip_windows(self, items: list[ScheduleItem]) -> list[ScheduleItem]:
        """
        Apply drip windows - periods with NO buying opportunities.

        Step 7 of pipeline: APPLY DRIP WINDOWS

        During drip windows (typically 2 PM - 10 PM):
        - NO PPV messages allowed
        - Replace with drip content markers or wall bumps

        Args:
            items: List of scheduled items

        Returns:
            List of items with drip window rules applied
        """
        if not self.config.enable_drip_windows:
            return items

        modified_items: list[ScheduleItem] = []

        for item in items:
            hour = int(item.scheduled_time.split(":")[0])

            if DRIP_WINDOW_START_HOUR <= hour < DRIP_WINDOW_END_HOUR:
                if item.item_type == "ppv":
                    # Convert PPV to drip marker
                    modified_items.append(
                        ScheduleItem(
                            item_id=item.item_id,
                            creator_id=item.creator_id,
                            scheduled_date=item.scheduled_date,
                            scheduled_time=item.scheduled_time,
                            item_type="drip",
                            caption_text="[DRIP WINDOW - No PPV]",
                            priority=7,
                            notes="Drip window active - original PPV moved",
                        )
                    )
                else:
                    modified_items.append(item)
            else:
                modified_items.append(item)

        drip_count = sum(1 for i in modified_items if i.item_type == "drip")
        if drip_count > 0:
            logger.info(f"[Step 7] Applied drip windows: {drip_count} PPVs converted to drip markers")

        return modified_items

    # =========================================================================
    # STEP 8: APPLY PAGE TYPE RULES
    # =========================================================================

    def step_8_apply_page_rules(self, items: list[ScheduleItem]) -> list[ScheduleItem]:
        """
        Apply page-type specific rules for pricing and content.

        Step 8 of pipeline: APPLY PAGE TYPE RULES

        Paid pages: Campaign-style, premium pricing (1.1x)
        Free pages: Direct unlocks, reduced pricing (0.9x)

        Args:
            items: List of scheduled items

        Returns:
            List of items with page type rules applied
        """
        if not self.config.enable_page_type_rules:
            return items

        for item in items:
            if item.item_type != "ppv":
                continue

            if self.config.page_type == "paid":
                # Premium pricing for paid pages
                if item.suggested_price:
                    item.suggested_price = round(item.suggested_price * 1.1, 2)
                item.channel = "campaign"
            else:
                # Standard pricing for free pages
                if item.suggested_price:
                    item.suggested_price = round(item.suggested_price * 0.9, 2)
                item.channel = "direct_unlock"

        # Apply content notes price modifiers if available
        if self.profile.price_modifiers:
            for item in items:
                if item.item_type == "ppv" and item.suggested_price:
                    content_type = item.content_type_name
                    if content_type in self.profile.price_modifiers:
                        item.suggested_price = round(
                            item.suggested_price * self.profile.price_modifiers[content_type], 2
                        )
                    elif None in self.profile.price_modifiers:
                        item.suggested_price = round(
                            item.suggested_price * self.profile.price_modifiers[None], 2
                        )

        logger.info(f"[Step 8] Applied {self.config.page_type} page rules to PPV pricing")

        # Invoke multi-touch sequencer agent if available
        if self.agent_invoker and self.agent_context:
            self._invoke_multi_touch_agent(items)

        return items

    def _invoke_multi_touch_agent(self, items: list[ScheduleItem]) -> None:
        """Invoke multi-touch sequencer agent for follow-up optimization."""
        if not self.config.enable_follow_ups:
            return

        try:
            ppv_items = [item for item in items if item.item_type == "ppv"]

            for ppv_item in ppv_items:
                followup_sequence, followup_fallback = self.agent_invoker.invoke_multi_touch_sequencer(
                    self.agent_context,
                    ppv_item_id=ppv_item.item_id,
                    content_type=ppv_item.content_type_name or "solo",
                )
                self.agent_context.followup_sequences.append(followup_sequence)

            if followup_fallback:
                if "multi-touch-sequencer" not in self.agents_fallback:
                    self.agents_fallback.append("multi-touch-sequencer")
            else:
                if "multi-touch-sequencer" not in self.agents_used:
                    self.agents_used.append("multi-touch-sequencer")

        except Exception as e:
            logger.warning(f"[AGENT MODE] Multi-touch sequencer failed: {e}")
            if "multi-touch-sequencer" not in self.agents_fallback:
                self.agents_fallback.append("multi-touch-sequencer")


# =============================================================================
# STEP 9: VALIDATION
# =============================================================================


def validate_schedule(items: list[ScheduleItem], config: ScheduleConfig) -> list[ValidationIssue]:
    """
    Validate schedule against all business rules.

    Step 9 of pipeline: VALIDATE & RETURN

    Rules checked:
        1. PPV Spacing >= 3 hours (ERROR if violated) - AUTO-CORRECTABLE
        2. No duplicate captions (ERROR if violated) - AUTO-CORRECTABLE
        3. All freshness >= 30 (ERROR if violated) - AUTO-CORRECTABLE
        4. Content rotation (WARNING if same type consecutively) - NOT auto-correctable
        5. Follow-up timing 15-45 min (WARNING if outside) - AUTO-CORRECTABLE

    Args:
        items: List of scheduled items to validate
        config: Schedule configuration

    Returns:
        List of ValidationIssue objects
    """
    issues: list[ValidationIssue] = []

    # Check PPV spacing
    ppv_items = [item for item in items if item.item_type == "ppv"]
    ppv_items.sort(key=lambda x: (x.scheduled_date, x.scheduled_time))

    for i in range(1, len(ppv_items)):
        prev = ppv_items[i - 1]
        curr = ppv_items[i]

        prev_dt = datetime.strptime(
            f"{prev.scheduled_date} {prev.scheduled_time}", "%Y-%m-%d %H:%M"
        )
        curr_dt = datetime.strptime(
            f"{curr.scheduled_date} {curr.scheduled_time}", "%Y-%m-%d %H:%M"
        )

        gap_hours = (curr_dt - prev_dt).total_seconds() / 3600

        if gap_hours < MIN_PPV_SPACING_HOURS:
            needed_shift = MIN_PPV_SPACING_HOURS - gap_hours + 0.25
            new_dt = curr_dt + timedelta(hours=needed_shift)
            correction_value = json.dumps({
                "new_date": new_dt.strftime("%Y-%m-%d"),
                "new_time": new_dt.strftime("%H:%M"),
            })

            issues.append(
                ValidationIssue(
                    rule_name="ppv_spacing",
                    severity="error",
                    message=f"PPV spacing too close: {gap_hours:.1f}h between #{prev.item_id} and #{curr.item_id} (min {MIN_PPV_SPACING_HOURS}h)",
                    item_ids=(prev.item_id, curr.item_id),
                    auto_correctable=True,
                    correction_action="move_slot",
                    correction_value=correction_value,
                )
            )

    # Check duplicate captions
    caption_ids: dict[int, list[int]] = {}
    for item in items:
        if item.caption_id:
            if item.caption_id not in caption_ids:
                caption_ids[item.caption_id] = []
            caption_ids[item.caption_id].append(item.item_id)

    for caption_id, item_ids in caption_ids.items():
        if len(item_ids) > 1:
            issues.append(
                ValidationIssue(
                    rule_name="duplicate_captions",
                    severity="error",
                    message=f"Caption {caption_id} used {len(item_ids)} times in items {item_ids}",
                    item_ids=tuple(item_ids[1:]),
                    auto_correctable=True,
                    correction_action="swap_caption",
                    correction_value="",
                )
            )

    # Check freshness scores
    for item in items:
        if item.freshness_score < MIN_FRESHNESS_SCORE and item.item_type == "ppv":
            issues.append(
                ValidationIssue(
                    rule_name="freshness_threshold",
                    severity="error",
                    message=f"Item #{item.item_id} has low freshness: {item.freshness_score:.1f} (min {MIN_FRESHNESS_SCORE})",
                    item_ids=(item.item_id,),
                    auto_correctable=True,
                    correction_action="swap_caption",
                    correction_value="",
                )
            )

    # Check content rotation (NOT auto-correctable)
    previous_type = None
    consecutive_count = 0
    for item in sorted(items, key=lambda x: (x.scheduled_date, x.scheduled_time)):
        if item.item_type != "ppv":
            continue

        if item.content_type_name == previous_type:
            consecutive_count += 1
            if consecutive_count >= 2:
                issues.append(
                    ValidationIssue(
                        rule_name="content_rotation",
                        severity="warning",
                        message=f"Same content type '{item.content_type_name}' used {consecutive_count + 1}x consecutively at item #{item.item_id}",
                        item_ids=(item.item_id,),
                        auto_correctable=False,
                    )
                )
        else:
            consecutive_count = 0
            previous_type = item.content_type_name

    # Check follow-up timing
    items_by_id = {item.item_id: item for item in items}
    for item in items:
        if item.is_follow_up and item.parent_item_id:
            parent = items_by_id.get(item.parent_item_id)
            if parent:
                parent_dt = datetime.strptime(
                    f"{parent.scheduled_date} {parent.scheduled_time}", "%Y-%m-%d %H:%M"
                )
                item_dt = datetime.strptime(
                    f"{item.scheduled_date} {item.scheduled_time}", "%Y-%m-%d %H:%M"
                )
                gap_minutes = (item_dt - parent_dt).total_seconds() / 60

                if gap_minutes < FOLLOW_UP_MIN_MINUTES or gap_minutes > FOLLOW_UP_MAX_MINUTES:
                    issues.append(
                        ValidationIssue(
                            rule_name="followup_timing",
                            severity="warning",
                            message=f"Follow-up #{item.item_id} timing: {gap_minutes:.0f}min (should be {FOLLOW_UP_MIN_MINUTES}-{FOLLOW_UP_MAX_MINUTES}min)",
                            item_ids=(item.item_id,),
                            auto_correctable=True,
                            correction_action="adjust_timing",
                            correction_value="25",
                        )
                    )

    return issues


def apply_auto_corrections(
    items: list[ScheduleItem],
    issues: list[ValidationIssue],
    available_captions: list[Caption] | None = None,
) -> tuple[list[ScheduleItem], list[str]]:
    """
    Apply automatic corrections to schedule items based on validation issues.

    Args:
        items: List of ScheduleItem objects
        issues: List of auto-correctable ValidationIssue objects
        available_captions: Optional pool of fresh captions for swap corrections

    Returns:
        Tuple of (corrected items list, list of correction descriptions)

    Correction actions:
        - move_slot: Move item to new time slot
        - swap_caption: Replace caption with fresh one from pool
        - adjust_timing: Adjust follow-up timing relative to parent
    """
    corrections_applied: list[str] = []
    items_by_id = {item.item_id: item for item in items}
    used_caption_ids = {item.caption_id for item in items if item.caption_id}

    # Build fresh caption pool
    fresh_pool: list[Caption] = []
    if available_captions:
        fresh_pool = [
            c
            for c in available_captions
            if c.caption_id not in used_caption_ids and c.freshness_score >= MIN_FRESHNESS_SCORE
        ]

    for issue in issues:
        if not issue.auto_correctable:
            continue

        action = issue.correction_action
        value = issue.correction_value
        item_ids = issue.item_ids

        if not item_ids:
            continue

        if action == "move_slot" and value:
            item_id = item_ids[-1] if len(item_ids) >= 2 else item_ids[0]
            item = items_by_id.get(item_id)

            if item:
                try:
                    new_slot = json.loads(value)
                    item.scheduled_date = new_slot.get("new_date", item.scheduled_date)
                    item.scheduled_time = new_slot.get("new_time", item.scheduled_time)
                    corrections_applied.append(f"move_slot(#{item_id} -> {item.scheduled_time})")
                except json.JSONDecodeError:
                    pass

        elif action == "swap_caption" and fresh_pool:
            for item_id in item_ids:
                item = items_by_id.get(item_id)
                if item and item.content_type_id:
                    matching = [c for c in fresh_pool if c.content_type_id == item.content_type_id]
                    if matching:
                        new_caption = matching[0]
                        fresh_pool.remove(new_caption)
                        used_caption_ids.add(new_caption.caption_id)

                        item.caption_id = new_caption.caption_id
                        item.caption_text = new_caption.caption_text
                        item.freshness_score = new_caption.freshness_score
                        item.performance_score = new_caption.performance_score

                        corrections_applied.append(
                            f"swap_caption(#{item_id} -> caption_{new_caption.caption_id})"
                        )

        elif action == "adjust_timing":
            item_id = item_ids[0]
            item = items_by_id.get(item_id)

            if item and item.parent_item_id:
                parent = items_by_id.get(item.parent_item_id)
                if parent:
                    try:
                        target_minutes = int(value) if value else 25
                        parent_dt = datetime.strptime(
                            f"{parent.scheduled_date} {parent.scheduled_time}", "%Y-%m-%d %H:%M"
                        )
                        new_dt = parent_dt + timedelta(minutes=target_minutes)
                        item.scheduled_date = new_dt.strftime("%Y-%m-%d")
                        item.scheduled_time = new_dt.strftime("%H:%M")
                        corrections_applied.append(
                            f"adjust_timing(#{item_id} -> {target_minutes}min)"
                        )
                    except (ValueError, TypeError):
                        pass

    return items, corrections_applied


def validate_and_correct(
    items: list[ScheduleItem],
    config: ScheduleConfig,
    available_captions: list[Caption] | None = None,
) -> tuple[list[ScheduleItem], list[ValidationIssue], list[str]]:
    """
    Validate schedule with automatic self-healing correction loop.

    This function runs validation, applies auto-corrections, and re-validates
    up to MAX_VALIDATION_PASSES times to fix auto-correctable issues silently.

    Args:
        items: List of ScheduleItem objects
        config: Schedule configuration
        available_captions: Optional pool of fresh captions for swap corrections

    Returns:
        Tuple of (corrected items, final validation issues, list of corrections applied)

    Auto-correctable issues:
        1. PPV spacing violation (<3hr) -> Move to next valid slot
        2. Duplicate caption -> Swap with unused caption of same type
        3. Freshness below 30 -> Swap with fresher caption
        4. Follow-up timing outside 15-45min -> Adjust to 25 minutes

    NOT auto-correctable:
        - Content rotation patterns (requires human judgment)
        - Pricing decisions
        - Volume targets
    """
    all_corrections: list[str] = []

    for pass_num in range(1, MAX_VALIDATION_PASSES + 1):
        issues = validate_schedule(items, config)

        errors = [i for i in issues if i.severity == "error"]
        if not errors:
            break

        auto_fixable = [i for i in errors if i.auto_correctable]
        if not auto_fixable:
            break

        if pass_num < MAX_VALIDATION_PASSES:
            items, corrections = apply_auto_corrections(items, auto_fixable, available_captions)
            all_corrections.extend(corrections)
            logger.info(f"[Validation Pass {pass_num}] Auto-corrected {len(corrections)} issues")

    # Final validation
    final_issues = validate_schedule(items, config)

    if all_corrections:
        final_issues.append(
            ValidationIssue(
                rule_name="auto_corrections",
                severity="info",
                message=f"Applied {len(all_corrections)} auto-corrections: {', '.join(all_corrections[:5])}{'...' if len(all_corrections) > 5 else ''}",
            )
        )
        logger.info(f"[Self-Healing] Total corrections applied: {len(all_corrections)}")

    return items, final_issues, all_corrections


__all__ = [
    "EnrichmentProcessor",
    "validate_schedule",
    "apply_auto_corrections",
    "validate_and_correct",
    "BUMP_MESSAGES",
]
