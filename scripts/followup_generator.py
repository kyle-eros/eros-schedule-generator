#!/usr/bin/env python3
"""
Follow-up Generator - Context-aware bump messages for PPV follow-ups.

This module replaces generic hardcoded bump messages with context-aware
follow-up messages that match the original PPV content and creator persona.

Context-Aware Strategy:
    - Content-based: References the content type naturally
    - Urgency: Creates FOMO with time pressure
    - Emotional: Personal connection and desire
    - Teasing: Curiosity and playful engagement

Follow-up Timing Guidelines:
    - Evening (6-11 PM): 15-25 min (people are active)
    - Afternoon (2-5 PM): 20-30 min
    - Morning (9-1 PM): 30-45 min (slower response)
    - Weekend: Slightly longer delays
    - High-price PPV (>= $25): Faster follow-up

Usage:
    python followup_generator.py --caption "enjoy 11 mins of me getting creamy..." --content-type squirt
    python followup_generator.py --creator missalexa --count 7 --format json
    python followup_generator.py --caption "new video" --strategy urgency --hour 21
"""

import argparse
import json
import os
import random
import re
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Path resolution for database
# Standard order: 1) env var, 2) Developer, 3) Documents, 4) .eros fallback
SCRIPT_DIR = Path(__file__).parent
HOME_DIR = Path.home()

# Build candidates list with env var first (if set)
_env_db_path = os.environ.get("EROS_DATABASE_PATH", "")
DB_PATH_CANDIDATES = [
    Path(_env_db_path) if _env_db_path else None,
    HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / ".eros" / "eros.db",
]
DB_PATH_CANDIDATES = [p for p in DB_PATH_CANDIDATES if p is not None]
DB_PATH = next((p for p in DB_PATH_CANDIDATES if p.exists()), DB_PATH_CANDIDATES[1] if len(DB_PATH_CANDIDATES) > 1 else DB_PATH_CANDIDATES[0])

# Timing constraints
MIN_TIMING_MINUTES = 15
MAX_TIMING_MINUTES = 45
DEFAULT_TIMING_MINUTES = 25

# High-value PPV threshold
HIGH_VALUE_PPV_PRICE = 25.0


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FollowUpMessage:
    """Result of follow-up message generation."""

    message_id: str  # Unique identifier
    text: str  # The follow-up message
    context_type: str  # content_based, urgency, emotional, teasing
    timing_minutes: int  # Suggested delay after PPV (15-45 min)
    confidence: float  # 0.0-1.0 confidence in appropriateness
    source: str  # "template", "generated", "hybrid"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "message_id": self.message_id,
            "text": self.text,
            "context_type": self.context_type,
            "timing_minutes": self.timing_minutes,
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }


@dataclass
class FollowUpContext:
    """Context for generating a follow-up message."""

    original_caption: str  # The original PPV caption
    content_type: str  # solo, bg, squirt, anal, etc.
    creator_tone: str = "playful"  # playful, aggressive, sweet, etc.
    emoji_frequency: str = "moderate"  # heavy, moderate, light, none
    price: float | None = None  # PPV price for value-based bumps
    day_of_week: int = 0  # 0=Mon, 6=Sun
    hour: int = 21  # 0-23, default evening


@dataclass(frozen=True, slots=True)
class PersonaProfile:
    """Creator persona profile for follow-up generation."""

    creator_id: str
    page_name: str
    primary_tone: str = "playful"
    emoji_frequency: str = "moderate"
    slang_level: str = "light"
    favorite_emojis: tuple[str, ...] = ()


# =============================================================================
# FOLLOW-UP GENERATOR CLASS
# =============================================================================

class FollowupGenerator:
    """
    Generate context-aware follow-up messages for PPV content.

    This class provides template-based and hybrid follow-up generation
    that matches the original PPV content and creator's voice profile.
    """

    # Template pools organized by content type
    CONTENT_BASED_TEMPLATES: dict[str, list[str]] = {
        "solo": [
            "did you see this one {pet_name}? it's just me...",
            "this one's special {pet_name}... wanna see?",
            "i was thinking about you when i made this one",
            "just me being naughty {pet_name}...",
            "hope you like this one... it's personal",
        ],
        "bg": [
            "you gotta see what happened {pet_name}...",
            "this got SO intense... just saying",
            "i think you'll really like this one",
            "things got a little crazy {pet_name}...",
            "this one is different... promise",
        ],
        "squirt": [
            "omg {pet_name} this one got messy",
            "you missed something good... just saying",
            "this is one of my favorites tbh",
            "couldn't help myself with this one {pet_name}...",
            "this one really got me going...",
        ],
        "anal": [
            "something extra special for you {pet_name}",
            "you're gonna love this one trust me",
            "this got really intense...",
            "i was feeling extra adventurous {pet_name}...",
            "this is the good stuff...",
        ],
        "bj": [
            "you need to see this {pet_name}...",
            "i was really into this one...",
            "hope you're ready for this {pet_name}",
            "this one's all about you...",
            "i think you'll like what you see...",
        ],
        "lesbian": [
            "you gotta see this {pet_name}...",
            "we had so much fun with this one...",
            "double the fun for you {pet_name}",
            "this got wild... just saying",
            "thought you might like this one...",
        ],
        "threesome": [
            "things got crazy {pet_name}...",
            "you're missing out on this one...",
            "this was SO fun to make...",
            "extra special surprise for you {pet_name}",
            "trust me you want this one...",
        ],
        "pov": [
            "made this one just for you {pet_name}...",
            "imagine this is for you...",
            "this feels so personal {pet_name}",
            "pretend you're here with me...",
            "this one's from my perspective...",
        ],
        "custom": [
            "this one's exclusive {pet_name}...",
            "made this special just for you...",
            "you're gonna love this one...",
            "can't show this to everyone {pet_name}",
            "this is between us...",
        ],
        "dick_rating": [
            "ready to hear what i think {pet_name}?",
            "i have thoughts {pet_name}...",
            "curious what i said?",
            "made this one just for you...",
            "hope you're ready to hear this...",
        ],
        "sexting": [
            "let's have some fun {pet_name}...",
            "i'm in a mood... you?",
            "wanna play {pet_name}?",
            "thinking about you rn...",
            "i'm feeling frisky {pet_name}...",
        ],
        "default": [
            "did you see this one yet {pet_name}?",
            "don't wanna miss this one {pet_name}...",
            "i made this one just for you",
            "checking in... did you see this?",
            "this one's really good {pet_name}...",
        ],
    }

    # Urgency templates (time pressure)
    URGENCY_TEMPLATES: list[str] = [
        "going off soon {pet_name}...",
        "not gonna be available much longer",
        "just checking if you saw this one...",
        "don't want you to miss out {pet_name}",
        "last chance to grab this one...",
        "about to take this down {pet_name}...",
        "running out of time on this one...",
        "gonna be gone soon...",
    ]

    # Emotional templates (personal connection)
    EMOTIONAL_TEMPLATES: list[str] = [
        "i'd really love for you to see this {pet_name}",
        "this one means a lot to me...",
        "made this thinking of you {pet_name}",
        "i put a lot into this one...",
        "hope this makes your day better {pet_name}",
        "wanted to share something special with you...",
        "you're one of my favorites {pet_name}...",
        "thought you'd appreciate this one...",
    ]

    # Teasing templates (curiosity/playful)
    TEASING_TEMPLATES: list[str] = [
        "guess what happens in this one...",
        "bet you can't guess what i did {pet_name}",
        "you're gonna be surprised by this one",
        "wanna know what i got up to?",
        "curious yet {pet_name}?",
        "i dare you to open this one...",
        "you'll never guess...",
        "something you haven't seen before {pet_name}...",
    ]

    # Value-based templates (for high-price PPV)
    VALUE_TEMPLATES: list[str] = [
        "this is my best content {pet_name}...",
        "worth every penny trust me...",
        "you won't regret this one...",
        "premium stuff just for you {pet_name}",
        "this is the good stuff...",
        "my favorite video yet {pet_name}...",
    ]

    # Pet name options for personalization
    PET_NAMES: list[str] = ["babe", "baby", "hun", "love", "handsome", "sexy", "cutie"]

    # Emoji pools by context
    EMOJI_POOLS: dict[str, list[str]] = {
        "teasing": ["\U0001F440", "\U0001F60F", "\U0001F92D", "\U0001F608"],  # eyes, smirk, shushing_face, imp
        "emotional": ["\U0001F495", "\u2764\uFE0F", "\U0001F970", "\U0001F618"],  # two_hearts, heart, smiling_face_with_hearts, kiss
        "urgency": ["\u23F0", "\U0001F6A8", "\U0001F625"],  # alarm_clock, rotating_light, disappointed_relieved
        "excitement": ["\U0001F525", "\U0001F975", "\U0001F4A6", "\U0001F60D"],  # fire, hot_face, sweat_droplets, heart_eyes
    }

    def __init__(self, persona: PersonaProfile | dict[str, Any] | None = None):
        """
        Initialize the follow-up generator.

        Args:
            persona: Optional PersonaProfile or dict with creator persona info.
        """
        if persona is None:
            self.persona = PersonaProfile(
                creator_id="default",
                page_name="default",
            )
        elif isinstance(persona, dict):
            emojis = persona.get("favorite_emojis", ())
            self.persona = PersonaProfile(
                creator_id=persona.get("creator_id", "default"),
                page_name=persona.get("page_name", "default"),
                primary_tone=persona.get("primary_tone", "playful"),
                emoji_frequency=persona.get("emoji_frequency", "moderate"),
                slang_level=persona.get("slang_level", "light"),
                favorite_emojis=tuple(emojis) if emojis else (),
            )
        else:
            self.persona = persona

        # Track used elements for repetition avoidance
        self._used_templates: set[str] = set()
        self._used_pet_names: set[str] = set()

    def generate_followup(
        self,
        context: FollowUpContext,
        strategy: str = "auto",
        pet_name: str | None = None,
    ) -> FollowUpMessage:
        """
        Generate a context-aware follow-up message.

        Args:
            context: FollowUpContext with original caption info.
            strategy: "content_based", "urgency", "emotional", "teasing", or "auto".
            pet_name: Optional specific pet name to use.

        Returns:
            FollowUpMessage with generated text and metadata.
        """
        # Auto-select strategy based on context
        if strategy == "auto":
            strategy = self._select_strategy(context)

        # Select and personalize template
        template = self._select_template(context.content_type, strategy)
        text = self._personalize_template(template, context, pet_name)

        # Calculate timing
        timing = self._calculate_timing(context)

        # Calculate confidence
        confidence = self._calculate_confidence(context, strategy)

        return FollowUpMessage(
            message_id=str(uuid.uuid4())[:8],
            text=text,
            context_type=strategy,
            timing_minutes=timing,
            confidence=confidence,
            source="template",
        )

    def generate_batch(
        self,
        contexts: list[FollowUpContext],
        avoid_repetition: bool = True,
    ) -> list[FollowUpMessage]:
        """
        Generate follow-ups for multiple PPVs, avoiding repetition.

        Args:
            contexts: List of FollowUpContext objects.
            avoid_repetition: Whether to avoid repeating templates/pet names.

        Returns:
            List of FollowUpMessage objects.
        """
        results: list[FollowUpMessage] = []

        if avoid_repetition:
            self._used_templates.clear()
            self._used_pet_names.clear()

        for context in contexts:
            # Get fresh pet name
            available_names = [n for n in self.PET_NAMES if n not in self._used_pet_names]
            if not available_names:
                self._used_pet_names.clear()
                available_names = self.PET_NAMES.copy()

            pet_name = random.choice(available_names)
            self._used_pet_names.add(pet_name)

            # Generate follow-up
            followup = self.generate_followup(context, pet_name=pet_name)

            if avoid_repetition:
                self._used_templates.add(followup.text)

            results.append(followup)

        return results

    def _select_strategy(self, context: FollowUpContext) -> str:
        """
        Auto-select the best strategy based on context.

        Args:
            context: FollowUpContext with PPV info.

        Returns:
            Strategy string.
        """
        # High-value PPV -> emotional or value-based
        if context.price and context.price >= HIGH_VALUE_PPV_PRICE:
            return random.choice(["emotional", "content_based"])

        # Evening hours -> teasing works well
        if 18 <= context.hour <= 23:
            weights = {"content_based": 40, "teasing": 35, "emotional": 15, "urgency": 10}
        # Morning -> softer approach
        elif 6 <= context.hour <= 12:
            weights = {"emotional": 40, "content_based": 40, "teasing": 15, "urgency": 5}
        # Afternoon -> mix
        else:
            weights = {"content_based": 35, "teasing": 30, "urgency": 20, "emotional": 15}

        # Weekend adjustments
        if context.day_of_week >= 5:  # Saturday/Sunday
            weights["teasing"] = weights.get("teasing", 20) + 10
            weights["urgency"] = max(0, weights.get("urgency", 10) - 5)

        # Weighted random selection
        strategies = list(weights.keys())
        weights_list = [weights[s] for s in strategies]
        return random.choices(strategies, weights=weights_list, k=1)[0]

    def _select_template(
        self,
        content_type: str,
        strategy: str,
    ) -> str:
        """
        Select appropriate template based on strategy and content type.

        Args:
            content_type: Content type (solo, bg, etc.).
            strategy: Strategy type.

        Returns:
            Template string.
        """
        # Get template pool based on strategy
        if strategy == "urgency":
            pool = self.URGENCY_TEMPLATES
        elif strategy == "emotional":
            pool = self.EMOTIONAL_TEMPLATES
        elif strategy == "teasing":
            pool = self.TEASING_TEMPLATES
        else:  # content_based or default
            # Get content-specific templates, fall back to default
            pool = self.CONTENT_BASED_TEMPLATES.get(
                content_type.lower(),
                self.CONTENT_BASED_TEMPLATES["default"]
            )

        # Filter out recently used templates
        available = [t for t in pool if t not in self._used_templates]
        if not available:
            # Reset if all used
            available = pool.copy()

        return random.choice(available)

    def _personalize_template(
        self,
        template: str,
        context: FollowUpContext,
        pet_name: str | None = None,
    ) -> str:
        """
        Insert persona-specific elements into template.

        Args:
            template: Template string with {pet_name} placeholder.
            context: FollowUpContext for styling.
            pet_name: Optional specific pet name.

        Returns:
            Personalized message text.
        """
        # Select pet name if not provided
        if pet_name is None:
            available = [n for n in self.PET_NAMES if n not in self._used_pet_names]
            if not available:
                available = self.PET_NAMES.copy()
            pet_name = random.choice(available)

        # Replace placeholder
        text = template.replace("{pet_name}", pet_name)

        # Match emoji style
        text = self._match_emoji_style(text, context.emoji_frequency)

        # Apply tone adjustments
        text = self._apply_tone_adjustments(text, context.creator_tone)

        return text

    def _match_emoji_style(self, text: str, target_style: str) -> str:
        """
        Adjust emoji density to match creator's style.

        Args:
            text: Message text.
            target_style: Target emoji style (heavy, moderate, light, none).

        Returns:
            Text with adjusted emoji usage.
        """
        # Count existing emojis
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U00002600-\U000026FF"
            "]+",
            flags=re.UNICODE
        )
        existing = emoji_pattern.findall(text)
        existing_count = sum(len(e) for e in existing)

        # Determine target count
        target_counts = {
            "heavy": 2,
            "moderate": 1,
            "light": 0,  # Maybe add one
            "none": 0,
        }
        target_count = target_counts.get(target_style, 1)

        # Don't add if we have enough or style is none
        if existing_count >= target_count or target_style == "none":
            return text

        # Add emoji if needed
        if existing_count < target_count and target_style != "none":
            # Select emoji based on text content
            emoji_context = "excitement"  # Default
            text_lower = text.lower()

            if any(word in text_lower for word in ["curious", "guess", "bet", "surprise"]):
                emoji_context = "teasing"
            elif any(word in text_lower for word in ["love", "special", "thinking", "favorite"]):
                emoji_context = "emotional"
            elif any(word in text_lower for word in ["soon", "last", "miss", "running"]):
                emoji_context = "urgency"

            pool = self.EMOJI_POOLS.get(emoji_context, self.EMOJI_POOLS["excitement"])

            # Prefer creator's favorite emojis if available
            if self.persona.favorite_emojis:
                emoji = random.choice(self.persona.favorite_emojis[:3])
            else:
                emoji = random.choice(pool)

            # Add at end
            text = text.rstrip() + " " + emoji

        return text

    def _apply_tone_adjustments(self, text: str, tone: str) -> str:
        """
        Apply minor tone-based adjustments.

        Args:
            text: Message text.
            tone: Creator's primary tone.

        Returns:
            Tone-adjusted text.
        """
        # Aggressive/dominant tones: more direct
        if tone in ("aggressive", "dominant"):
            # Remove trailing ellipses sometimes
            if text.endswith("...") and random.random() < 0.3:
                text = text.rstrip(".") + "."
            return text

        # Bratty tone: add more casual flair
        if tone == "bratty":
            if "..." not in text and random.random() < 0.3:
                text = text.rstrip(".!") + "..."
            return text

        # Sweet tone: softer endings
        if tone == "sweet":
            if not any(emoji in text for emoji in ["\u2764", "\U0001F495", "\U0001F618"]):
                if random.random() < 0.2:
                    text = text.rstrip() + " \U0001F495"
            return text

        # Default: no adjustment
        return text

    def _calculate_timing(self, context: FollowUpContext) -> int:
        """
        Calculate optimal follow-up timing in minutes.

        Guidelines:
            - Evening hours (6-11 PM): 15-25 min (people are active)
            - Afternoon (2-5 PM): 20-30 min
            - Morning (9-1 PM): 30-45 min (slower response)
            - Weekend: Slightly longer delays
            - High-price PPV: Shorter follow-up (more important)

        Args:
            context: FollowUpContext with timing info.

        Returns:
            Timing in minutes (15-45).
        """
        base_timing = DEFAULT_TIMING_MINUTES

        # Adjust for time of day
        if 18 <= context.hour <= 23:  # Evening peak
            base_timing = 20
        elif 6 <= context.hour <= 8:  # Early morning
            base_timing = 40
        elif 9 <= context.hour <= 13:  # Morning
            base_timing = 35
        elif 14 <= context.hour <= 17:  # Afternoon
            base_timing = 25

        # Weekend adjustment (people check less frequently)
        if context.day_of_week >= 5:  # Sat/Sun
            base_timing += 5

        # High-value PPV gets faster follow-up
        if context.price and context.price >= HIGH_VALUE_PPV_PRICE:
            base_timing = max(MIN_TIMING_MINUTES, base_timing - 5)

        # Add small random variation (+/- 3 min)
        variation = random.randint(-3, 3)
        base_timing += variation

        # Ensure within bounds
        return max(MIN_TIMING_MINUTES, min(MAX_TIMING_MINUTES, base_timing))

    def _calculate_confidence(
        self,
        context: FollowUpContext,
        strategy: str,
    ) -> float:
        """
        Calculate confidence score for the generated follow-up.

        Args:
            context: FollowUpContext.
            strategy: Selected strategy.

        Returns:
            Confidence score (0.0-1.0).
        """
        confidence = 0.7  # Base confidence

        # Content type match boost
        if context.content_type.lower() in self.CONTENT_BASED_TEMPLATES:
            confidence += 0.1

        # Strategy appropriateness
        if strategy == "content_based":
            confidence += 0.05
        elif strategy == "emotional" and context.price and context.price >= HIGH_VALUE_PPV_PRICE:
            confidence += 0.1
        elif strategy == "teasing" and 18 <= context.hour <= 23:
            confidence += 0.05

        # Persona match (if we have persona info)
        if self.persona.primary_tone == context.creator_tone:
            confidence += 0.05

        return min(1.0, confidence)

    def reset_tracking(self) -> None:
        """Reset used templates and pet names tracking."""
        self._used_templates.clear()
        self._used_pet_names.clear()


# =============================================================================
# LLM GENERATION (OPTIONAL FULL MODE)
# =============================================================================

CONTEXTUAL_FOLLOWUP_PROMPT = '''
## Context-Aware Follow-Up Message

Generate a natural follow-up/bump message for this PPV:

Original Caption: "{original_caption}"
Content Type: {content_type}
Creator Tone: {creator_tone}
Emoji Style: {emoji_frequency}

Requirements:
1. Sound like a real DM from the creator
2. Reference the content naturally (not explicitly)
3. Create curiosity/FOMO
4. Match the creator's tone and emoji style
5. Keep it under 100 characters
6. Use one pet name (babe, baby, hun, love)

Return just the follow-up message, no quotes.
'''


def build_llm_prompt(context: FollowUpContext) -> str:
    """
    Build prompt for LLM-based follow-up generation.

    Args:
        context: FollowUpContext with PPV info.

    Returns:
        Formatted prompt string.
    """
    # Truncate caption for prompt
    caption_preview = context.original_caption[:150]
    if len(context.original_caption) > 150:
        caption_preview += "..."

    return CONTEXTUAL_FOLLOWUP_PROMPT.format(
        original_caption=caption_preview,
        content_type=context.content_type,
        creator_tone=context.creator_tone,
        emoji_frequency=context.emoji_frequency,
    )


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def get_persona_from_db(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None,
) -> PersonaProfile | None:
    """
    Load persona profile from database.

    Args:
        conn: Database connection.
        creator_name: Creator page name.
        creator_id: Creator UUID.

    Returns:
        PersonaProfile or None if not found.
    """
    if not creator_name and not creator_id:
        raise ValueError("Must provide either creator_name or creator_id")

    if creator_name:
        query = """
            SELECT
                c.creator_id,
                c.page_name,
                cp.primary_tone,
                cp.emoji_frequency,
                cp.favorite_emojis,
                cp.slang_level
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.page_name = ? OR c.display_name = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_name, creator_name))
    else:
        query = """
            SELECT
                c.creator_id,
                c.page_name,
                cp.primary_tone,
                cp.emoji_frequency,
                cp.favorite_emojis,
                cp.slang_level
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.creator_id = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_id,))

    row = cursor.fetchone()
    if not row:
        return None

    # Parse favorite emojis from JSON with type validation
    favorite_emojis: tuple[str, ...] = ()
    if row["favorite_emojis"]:
        try:
            parsed = json.loads(row["favorite_emojis"])
            if isinstance(parsed, list):
                favorite_emojis = tuple(str(e) for e in parsed)
        except (json.JSONDecodeError, TypeError):
            pass

    return PersonaProfile(
        creator_id=row["creator_id"],
        page_name=row["page_name"],
        primary_tone=row["primary_tone"] or "playful",
        emoji_frequency=row["emoji_frequency"] or "moderate",
        slang_level=row["slang_level"] or "light",
        favorite_emojis=favorite_emojis,
    )


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def format_markdown(
    messages: list[FollowUpMessage],
    persona: PersonaProfile | None = None,
) -> str:
    """
    Format follow-up messages as Markdown.

    Args:
        messages: List of FollowUpMessage objects.
        persona: Optional persona for context.

    Returns:
        Formatted Markdown string.
    """
    lines = [
        "# Follow-Up Messages",
        "",
    ]

    if persona:
        lines.extend([
            f"**Creator:** {persona.page_name}",
            f"**Tone:** {persona.primary_tone}",
            f"**Emoji Style:** {persona.emoji_frequency}",
            "",
        ])

    lines.extend([
        "## Generated Messages",
        "",
        "| # | Message | Strategy | Timing | Confidence |",
        "|---|---------|----------|--------|------------|",
    ])

    for i, msg in enumerate(messages, 1):
        # Escape pipe characters in message
        text_escaped = msg.text.replace("|", "\\|")
        lines.append(
            f"| {i} | {text_escaped} | {msg.context_type} | "
            f"{msg.timing_minutes} min | {msg.confidence:.2f} |"
        )

    lines.extend([
        "",
        "## Summary",
        "",
        f"- **Total Generated:** {len(messages)}",
        f"- **Avg Timing:** {sum(m.timing_minutes for m in messages) / len(messages):.0f} min" if messages else "- **Avg Timing:** N/A",
        f"- **Avg Confidence:** {sum(m.confidence for m in messages) / len(messages):.2f}" if messages else "- **Avg Confidence:** N/A",
        "",
    ])

    # Strategy breakdown
    strategies: dict[str, int] = {}
    for msg in messages:
        strategies[msg.context_type] = strategies.get(msg.context_type, 0) + 1

    if strategies:
        lines.extend([
            "### Strategy Distribution",
            "",
        ])
        for strategy, count in sorted(strategies.items(), key=lambda x: -x[1]):
            pct = count / len(messages) * 100
            lines.append(f"- **{strategy}:** {count} ({pct:.0f}%)")
        lines.append("")

    return "\n".join(lines)


def format_json(
    messages: list[FollowUpMessage],
    persona: PersonaProfile | None = None,
) -> str:
    """
    Format follow-up messages as JSON.

    Args:
        messages: List of FollowUpMessage objects.
        persona: Optional persona for context.

    Returns:
        JSON string.
    """
    data: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "count": len(messages),
        "messages": [msg.to_dict() for msg in messages],
    }

    if persona:
        data["persona"] = {
            "creator_id": persona.creator_id,
            "page_name": persona.page_name,
            "primary_tone": persona.primary_tone,
            "emoji_frequency": persona.emoji_frequency,
        }

    if messages:
        data["summary"] = {
            "avg_timing": round(sum(m.timing_minutes for m in messages) / len(messages), 1),
            "avg_confidence": round(sum(m.confidence for m in messages) / len(messages), 3),
            "strategies": {},
        }
        for msg in messages:
            data["summary"]["strategies"][msg.context_type] = (
                data["summary"]["strategies"].get(msg.context_type, 0) + 1
            )

    return json.dumps(data, indent=2, ensure_ascii=False)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Generate context-aware follow-up messages for PPV content.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Strategies:
    - content_based: References the content type naturally
    - urgency: Creates FOMO with time pressure
    - emotional: Personal connection and desire
    - teasing: Curiosity and playful engagement
    - auto: Automatically selects best strategy

Timing Guidelines:
    - Evening (6-11 PM): 15-25 min
    - Afternoon (2-5 PM): 20-30 min
    - Morning (9-1 PM): 30-45 min
    - Weekend: +5 min
    - High-price PPV (>= $25): -5 min

Examples:
    python followup_generator.py --caption "enjoy 11 mins..." --content-type squirt
    python followup_generator.py --creator missalexa --count 7 --format json
    python followup_generator.py --strategy urgency --price 35 --hour 21
        """
    )

    parser.add_argument(
        "--caption", "-t",
        help="Original PPV caption text"
    )
    parser.add_argument(
        "--content-type", "-ct",
        default="default",
        help="Content type (solo, bg, squirt, anal, etc.)"
    )
    parser.add_argument(
        "--creator", "-c",
        help="Creator page name for persona"
    )
    parser.add_argument(
        "--creator-id",
        help="Creator UUID for persona"
    )
    parser.add_argument(
        "--strategy", "-s",
        choices=["auto", "content_based", "urgency", "emotional", "teasing"],
        default="auto",
        help="Follow-up strategy (default: auto)"
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=1,
        help="Number of follow-ups to generate (default: 1)"
    )
    parser.add_argument(
        "--price",
        type=float,
        help="PPV price for value-based timing"
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=21,
        help="Hour of PPV send (0-23, default: 21)"
    )
    parser.add_argument(
        "--day",
        type=int,
        default=0,
        help="Day of week (0=Mon, 6=Sun, default: 0)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help=f"Database path (default: {DB_PATH})"
    )

    args = parser.parse_args()

    # Load persona if creator specified
    persona: PersonaProfile | None = None
    if args.creator or args.creator_id:
        db_path = Path(args.db)
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                persona = get_persona_from_db(
                    conn,
                    creator_name=args.creator,
                    creator_id=args.creator_id
                )
                if not persona:
                    print(f"Warning: Creator not found, using defaults", file=sys.stderr)
            finally:
                conn.close()
        else:
            print(f"Warning: Database not found: {db_path}", file=sys.stderr)

    # Initialize generator
    generator = FollowupGenerator(persona)

    # Build context
    context = FollowUpContext(
        original_caption=args.caption or "Generic PPV content",
        content_type=args.content_type,
        creator_tone=persona.primary_tone if persona else "playful",
        emoji_frequency=persona.emoji_frequency if persona else "moderate",
        price=args.price,
        day_of_week=args.day,
        hour=args.hour,
    )

    # Generate follow-ups
    if args.count == 1:
        messages = [generator.generate_followup(context, strategy=args.strategy)]
    else:
        # Generate batch with variety
        contexts = [context] * args.count
        messages = generator.generate_batch(contexts, avoid_repetition=True)

    # Format output
    if args.format == "json":
        output = format_json(messages, persona)
    else:
        output = format_markdown(messages, persona)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Results written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
