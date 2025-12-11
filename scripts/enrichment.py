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
from validate_schedule import ScheduleValidator

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
# PAGE-TYPE-AWARE PRICING (from CLAUDE.md 2025 Best Practices)
# =============================================================================

# Price ranges by content type and page type (min, max)
# Based on CLAUDE.md 2025 Market Rates
# 2025 CLAUDE.md Market Rates Pricing Matrix
# Maps content type categories to price ranges for paid/free pages
# Each tuple is (min_price, max_price) in USD
#
# IMPORTANT: These rates are from CLAUDE.md and must match exactly:
# | Content Type      | Paid Page | Free Page |
# |-------------------|-----------|-----------|
# | Solo/Selfie       | $12-15    | $8-10     |
# | Bundle (3-5)      | $18-22    | $12-15    |
# | Sextape/Full Vid  | $22-28    | $15-20    |
# | B/G Couples       | $28-35    | $20-25    |
# | Custom/Interactive| $35-50    | $25-35    |
# | Dick Ratings      | $15-25    | $10-18    |
PRICING_MATRIX: dict[str, dict[str, tuple[float, float]]] = {
    "paid": {
        "solo": (12.0, 15.0),
        "bundle": (18.0, 22.0),
        "flash_bundle": (18.0, 22.0),  # Same as bundle
        "sextape": (22.0, 28.0),
        "bg": (28.0, 35.0),
        "custom": (35.0, 50.0),
        "dick_rating": (15.0, 25.0),
        "ppv": (12.0, 15.0),  # PPV defaults to solo pricing
        "default": (12.0, 18.0),
    },
    "free": {
        "solo": (8.0, 10.0),
        "bundle": (12.0, 15.0),
        "flash_bundle": (12.0, 15.0),  # Same as bundle
        "sextape": (15.0, 20.0),
        "bg": (20.0, 25.0),
        "custom": (25.0, 35.0),
        "dick_rating": (10.0, 18.0),
        "ppv": (8.0, 10.0),  # PPV defaults to solo pricing
        "default": (8.0, 12.0),
    },
}

# Content type normalization mapping for pricing lookup
# Maps various content type names to their pricing category
# IMPORTANT: This mapping must cover all database content_type names
CONTENT_TYPE_NORMALIZATION: dict[str, str] = {
    # Direct category names (canonical)
    "solo": "solo",
    "bundle": "bundle",
    "flash_bundle": "flash_bundle",  # Keep as flash_bundle for PRICING_MATRIX lookup
    "sextape": "sextape",
    "bg": "bg",
    "custom": "custom",
    "dick_rating": "dick_rating",
    "ppv": "ppv",  # Generic PPV type
    # Bundle variants
    "bundle_offer": "bundle",
    "bundle offer": "bundle",
    "flash_sale": "bundle",
    "flash sale": "bundle",
    "photo_set": "bundle",
    "photo set": "bundle",
    "photoset": "bundle",
    "gallery": "bundle",
    "photo bundle": "bundle",
    "pic bundle": "bundle",
    "multi-pic": "bundle",
    "multipic": "bundle",
    # Solo variants
    "shower_bath": "solo",
    "shower bath": "solo",
    "shower": "solo",
    "bath": "solo",
    "selfie": "solo",
    "lingerie": "solo",
    "nude": "solo",
    "topless": "solo",
    "solo pic": "solo",
    "solo photo": "solo",
    "single": "solo",
    "pic": "solo",
    "photo": "solo",
    "teasing": "solo",
    "tease": "solo",
    "toy_play": "solo",
    "toy play": "solo",
    "pussy_play": "solo",
    "pussy play": "solo",
    "tits_play": "solo",
    "tits play": "solo",
    "pov": "solo",
    "implied_solo": "solo",
    "implied solo": "solo",
    # Sextape/video variants
    "video": "sextape",
    "full_video": "sextape",
    "full video": "sextape",
    "sex_tape": "sextape",
    "sex tape": "sextape",
    "masturbation": "sextape",
    "solo video": "sextape",
    "full length": "sextape",
    "full-length": "sextape",
    "explicit video": "sextape",
    "creampie": "sextape",
    "anal": "sextape",
    "squirt": "sextape",
    # B/G variants
    "b/g": "bg",
    "b_g": "bg",
    "boy_girl": "bg",
    "boy girl": "bg",
    "boy/girl": "bg",
    "couples": "bg",
    "couple": "bg",
    "couples content": "bg",
    "duo": "bg",
    "blowjob": "bg",
    "deepthroat": "bg",
    "girl_girl": "bg",
    "girl girl": "bg",
    "boy_girl_girl": "bg",
    "girl_girl_girl": "bg",
    # Dick rating variants
    "dick rating": "dick_rating",
    "dickrating": "dick_rating",
    "rating": "dick_rating",
    "cock rating": "dick_rating",
    "cock_rating": "dick_rating",
    # Custom variants
    "custom_content": "custom",
    "custom content": "custom",
    "personalized": "custom",
    "custom video": "custom",
    "custom_video": "custom",
    "personal": "custom",
    "joi": "custom",
    "gfe": "custom",
    "dom_sub": "custom",
    "story_roleplay": "custom",
    # PPV/Exclusive content
    "exclusive_content": "ppv",
    "exclusive content": "ppv",
    "live_stream": "ppv",
    "live stream": "ppv",
}


def normalize_content_type_for_pricing(content_type: str | None) -> str:
    """
    Normalize content type name to a pricing category.

    This function maps database content type names to pricing categories
    defined in CLAUDE.md 2025 Market Rates. The mapping is critical for
    correct pricing application.

    Args:
        content_type: Raw content type name from database

    Returns:
        Normalized pricing category (solo, bundle, sextape, bg, custom, dick_rating, or default)

    Priority order:
        1. Direct match in CONTENT_TYPE_NORMALIZATION (most specific)
        2. Substring match for key category names (fallback)
        3. "default" if nothing matches (logs warning)
    """
    if not content_type:
        logger.debug("normalize_content_type_for_pricing: content_type is None/empty, using 'default'")
        return "default"

    # Lowercase for matching
    ct_lower = content_type.lower().strip()

    # Check direct match in normalization map (preferred)
    if ct_lower in CONTENT_TYPE_NORMALIZATION:
        normalized = CONTENT_TYPE_NORMALIZATION[ct_lower]
        logger.debug(f"normalize_content_type_for_pricing: '{content_type}' -> '{normalized}' (direct match)")
        return normalized

    # Substring matching for key category names (fallback)
    # Order matters - more specific checks first
    if "bundle" in ct_lower or "flash" in ct_lower or "gallery" in ct_lower or "photo_set" in ct_lower:
        logger.debug(f"normalize_content_type_for_pricing: '{content_type}' -> 'bundle' (substring match)")
        return "bundle"
    if "sextape" in ct_lower or "sex_tape" in ct_lower or "sex tape" in ct_lower:
        logger.debug(f"normalize_content_type_for_pricing: '{content_type}' -> 'sextape' (substring match)")
        return "sextape"
    if "video" in ct_lower and "solo" not in ct_lower:
        # "video" maps to sextape unless it's "solo video"
        logger.debug(f"normalize_content_type_for_pricing: '{content_type}' -> 'sextape' (video substring)")
        return "sextape"
    if "solo" in ct_lower or "selfie" in ct_lower:
        logger.debug(f"normalize_content_type_for_pricing: '{content_type}' -> 'solo' (substring match)")
        return "solo"
    if "b/g" in ct_lower or "bg" in ct_lower or "couple" in ct_lower or "boy" in ct_lower:
        logger.debug(f"normalize_content_type_for_pricing: '{content_type}' -> 'bg' (substring match)")
        return "bg"
    if "custom" in ct_lower or "personalized" in ct_lower or "personal" in ct_lower:
        logger.debug(f"normalize_content_type_for_pricing: '{content_type}' -> 'custom' (substring match)")
        return "custom"
    if "dick" in ct_lower or "rating" in ct_lower or "cock" in ct_lower:
        logger.debug(f"normalize_content_type_for_pricing: '{content_type}' -> 'dick_rating' (substring match)")
        return "dick_rating"

    # Fallback to default - log a warning since this may indicate missing mapping
    logger.warning(
        f"normalize_content_type_for_pricing: '{content_type}' not recognized, using 'default' pricing. "
        f"Consider adding this content type to CONTENT_TYPE_NORMALIZATION."
    )
    return "default"


def calculate_price(
    content_type: str | None,
    page_type: str,
    performance_score: float = 50.0,
    persona_boost: float = 1.0,
    price_modifiers: dict[str | None, float] | None = None,
) -> float:
    """
    Calculate optimal price based on content type, page type, and performance.

    This follows CLAUDE.md 2025 Market Rates for OnlyFans pricing:
    - Free page bundles: $12-15
    - Free page solo: $8-10
    - Paid page bundles: $18-22
    - Paid page solo: $12-15
    - etc.

    Args:
        content_type: Content type (solo, bundle, sextape, etc.)
        page_type: Page type (paid or free)
        performance_score: Historical performance score (0-100)
        persona_boost: Persona match multiplier (1.0-1.4)
        price_modifiers: Creator-specific modifiers from content_notes

    Returns:
        Calculated price rounded to 2 decimal places

    Example:
        >>> calculate_price("bundle", "free", performance_score=75.0)
        13.88  # In $12-15 range, weighted toward upper end
        >>> calculate_price("solo", "paid", performance_score=90.0, persona_boost=1.2)
        15.30  # High performance + persona boost
    """
    # Normalize content type to pricing category
    # First try our local normalization, then fall back to registry
    normalized_type = normalize_content_type_for_pricing(content_type)

    # If we got "default", try using the content_type_registry as fallback
    if normalized_type == "default" and content_type:
        try:
            from content_type_registry import get_pricing_category, normalize_content_type
            registry_type = normalize_content_type(content_type)
            registry_pricing = get_pricing_category(registry_type)
            if registry_pricing and registry_pricing != "default":
                normalized_type = registry_pricing
                logger.debug(
                    f"calculate_price: Using registry fallback for '{content_type}' -> "
                    f"registry_type='{registry_type}' -> pricing='{normalized_type}'"
                )
        except ImportError:
            pass

    # Normalize page type
    page_type_key = "paid" if page_type.lower() == "paid" else "free"

    # Get base range from matrix
    ranges = PRICING_MATRIX.get(page_type_key, PRICING_MATRIX["free"])
    min_price, max_price = ranges.get(normalized_type, ranges["default"])

    # Calculate position in range based on performance (0-100 -> 0-1)
    # Higher performance = higher in the price range
    perf_factor = min(max(performance_score / 100.0, 0.0), 1.0)
    base_price = min_price + (max_price - min_price) * perf_factor

    # Apply persona boost (max 10% price increase for perfect 1.4x match)
    # Formula: 1.0 + (boost - 1.0) * 0.25
    # At 1.0 boost: 1.0x (no change)
    # At 1.2 boost: 1.05x (5% increase)
    # At 1.4 boost: 1.10x (10% increase)
    boost_factor = 1.0 + (persona_boost - 1.0) * 0.25

    # Apply creator-specific modifiers
    modifier_factor = 1.0
    if price_modifiers:
        # Check for specific content type modifier
        if content_type and content_type in price_modifiers:
            modifier_factor = price_modifiers[content_type]
            logger.debug(f"Applying content-specific price modifier: {content_type} -> {modifier_factor}x")
        elif normalized_type in price_modifiers:
            modifier_factor = price_modifiers[normalized_type]
            logger.debug(f"Applying normalized price modifier: {normalized_type} -> {modifier_factor}x")
        # Check for "all" content type modifier
        elif "all" in price_modifiers:
            modifier_factor = price_modifiers["all"]
            logger.debug(f"Applying 'all' price modifier: {modifier_factor}x")
        # Check for None key (legacy format)
        elif None in price_modifiers:
            modifier_factor = price_modifiers[None]
            logger.debug(f"Applying default price modifier: {modifier_factor}x")

    final_price = base_price * boost_factor * modifier_factor

    logger.debug(
        f"Price calculation: {content_type} ({normalized_type}) on {page_type_key} page | "
        f"Range: ${min_price:.2f}-${max_price:.2f} | "
        f"Base: ${base_price:.2f} (perf={performance_score:.0f}) | "
        f"Boost: {boost_factor:.2f}x | Modifier: {modifier_factor:.2f}x | "
        f"Final: ${final_price:.2f}"
    )

    return round(final_price, 2)


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

        Uses CLAUDE.md 2025 Market Rates for content-type-aware pricing:
        - FREE page bundles: $12-15 (not flat $8-9)
        - FREE page solo: $8-10
        - FREE page sextape: $15-20
        - PAID page bundles: $18-22
        - etc.

        Price is calculated based on:
        - Content type (bundle, solo, sextape, bg, custom, dick_rating)
        - Page type (paid vs free)
        - Performance score (higher = higher in range)
        - Persona boost (up to 10% increase)
        - Creator-specific price modifiers from content_notes

        Args:
            items: List of scheduled items

        Returns:
            List of items with page type rules applied
        """
        if not self.config.enable_page_type_rules:
            return items

        pricing_summary: dict[str, list[float]] = {}
        price_modifiers = self.profile.price_modifiers if self.profile else None

        for item in items:
            if item.item_type != "ppv":
                continue

            # Calculate price using new content-type-aware pricing
            new_price = calculate_price(
                content_type=item.content_type_name,
                page_type=self.config.page_type,
                performance_score=item.performance_score or 50.0,
                persona_boost=getattr(item, "persona_boost", 1.0),
                price_modifiers=price_modifiers,
            )

            # Store old price for logging
            old_price = item.suggested_price

            # Update item with new price
            item.suggested_price = new_price

            # Set channel based on page type
            if self.config.page_type == "paid":
                item.channel = "campaign"
            else:
                item.channel = "direct_unlock"

            # Track pricing by content type for summary logging
            ct_name = normalize_content_type_for_pricing(item.content_type_name)
            if ct_name not in pricing_summary:
                pricing_summary[ct_name] = []
            pricing_summary[ct_name].append(new_price)

            # Add pricing note to item
            price_note = f"Price: ${old_price:.2f} -> ${new_price:.2f} ({ct_name})"
            if item.notes:
                item.notes = f"{item.notes} | {price_note}"
            else:
                item.notes = price_note

        # Log pricing summary
        summary_parts = []
        for ct_name, prices in sorted(pricing_summary.items()):
            avg_price = sum(prices) / len(prices) if prices else 0
            summary_parts.append(f"{ct_name}: ${avg_price:.2f} avg ({len(prices)} items)")

        logger.info(
            f"[Step 8] Applied {self.config.page_type} page pricing | "
            f"{', '.join(summary_parts) if summary_parts else 'no PPV items'}"
        )

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


def _schedule_item_to_dict(item: ScheduleItem) -> dict[str, Any]:
    """
    Convert a ScheduleItem dataclass to a dictionary for validation.

    This is needed because ScheduleValidator.validate() expects dict items.
    We cannot use dataclasses.asdict() because ScheduleItem uses slots=True.

    Args:
        item: ScheduleItem dataclass instance

    Returns:
        Dictionary representation of the ScheduleItem
    """
    return {
        "item_id": item.item_id,
        "creator_id": item.creator_id,
        "scheduled_date": item.scheduled_date,
        "scheduled_time": item.scheduled_time,
        "item_type": item.item_type,
        "channel": item.channel,
        "caption_id": item.caption_id,
        "caption_text": item.caption_text,
        "content_type_id": item.content_type_id,
        "content_type_name": item.content_type_name,
        "suggested_price": item.suggested_price,
        "freshness_score": item.freshness_score,
        "performance_score": item.performance_score,
        "is_follow_up": item.is_follow_up,
        "parent_item_id": item.parent_item_id,
        "status": item.status,
        "priority": item.priority,
        "notes": item.notes,
        # Expanded content type fields
        "poll_options": item.poll_options,
        "poll_duration_hours": item.poll_duration_hours,
        "wheel_config_id": item.wheel_config_id,
        "preview_type": item.preview_type,
        "linked_ppv_id": item.linked_ppv_id,
        "is_paid_post": item.is_paid_post,
    }


def validate_schedule(items: list[ScheduleItem], config: ScheduleConfig) -> list[ValidationIssue]:
    """
    Validate schedule against ALL 30+ business rules using ScheduleValidator.

    Step 9 of pipeline: VALIDATE & RETURN

    This function delegates to ScheduleValidator which checks ALL rules (V001-V032):
        Core Rules (V001-V018):
        - V001: PPV Spacing >= 3 hours
        - V002: Freshness minimum >= 30
        - V003: Follow-up timing 15-45 min
        - V004: No duplicate captions
        - V005: Vault availability
        - V006: Volume compliance
        - V007: Price bounds
        - V008: Wall post spacing
        - V009: Preview-PPV linkage
        - V010: Poll spacing
        - V011: Poll duration
        - V012: Game wheel validity
        - V013: Wall post volume
        - V014: Poll volume
        - V015: Hook rotation
        - V016: Hook diversity
        - V017: Content rotation
        - V018: Empty schedule check

        Extended Rules (V020-V032):
        - V020: Page type compliance
        - V021: VIP post spacing
        - V022: Link drop spacing
        - V023: Engagement daily limit
        - V024: Engagement weekly limit
        - V025: Retention timing
        - V026: Bundle spacing
        - V027: Flash bundle spacing
        - V028: Game post weekly limit
        - V029: Bump variant rotation
        - V030: Content type rotation
        - V031: Placeholder warnings
        - V032: Performance minimum

    Args:
        items: List of scheduled items to validate
        config: Schedule configuration with page_type, week_start, etc.

    Returns:
        List of ValidationIssue objects from all 30+ validation rules
    """
    # Convert ScheduleItem dataclasses to dicts for ScheduleValidator
    item_dicts = [_schedule_item_to_dict(item) for item in items]

    # Use week_start from config (already a date object)
    week_start = config.week_start if config.week_start else None

    # Instantiate the full validator with thresholds from config
    validator = ScheduleValidator(
        min_ppv_spacing_hours=MIN_PPV_SPACING_HOURS,
        min_freshness=MIN_FRESHNESS_SCORE,
        max_consecutive_same_type=3,
    )

    # Run ALL 30+ validation rules
    # Note: volume_target uses ppv_per_day from config
    # Note: vault_types would need to be passed from CreatorProfile if needed
    result = validator.validate(
        items=item_dicts,
        volume_target=config.ppv_per_day,
        vault_types=None,  # Would require profile.vault_types if strict vault checking needed
        page_type=config.page_type,
        week_start=week_start,
    )

    # Log validation summary
    total_rules = len(set(issue.rule_name for issue in result.issues))
    logger.info(
        f"[Step 9] Validation complete: {result.error_count} errors, "
        f"{result.warning_count} warnings, {result.info_count} info | "
        f"{total_rules} rules triggered issues"
    )

    return result.issues


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
    # Page-type-aware pricing
    "PRICING_MATRIX",
    "CONTENT_TYPE_NORMALIZATION",
    "normalize_content_type_for_pricing",
    "calculate_price",
]
