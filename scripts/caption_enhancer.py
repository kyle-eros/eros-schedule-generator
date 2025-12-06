#!/usr/bin/env python3
"""
Caption Enhancer - Minor authenticity tweaks for captions.

This module implements MINOR tweaks only for authenticity, NOT full rewrites.
All transformations are rule-based and preserve the original message's core
content while making it sound more natural and human.

Enhancement Categories:
    - Contractions: "do not miss this" -> "don't miss this"
    - Emoji Match: "Check this out" -> "Check this out fire_emoji" (if heavy user)
    - Casual Punctuation: "Hey. Are you ready." -> "Hey... are you ready"
    - Slang (heavy only): "you right now" -> "u rn"
    - Pet Name Rotation: "babe" (repeated) -> "baby", "hun", "love"

OFF LIMITS (preserve always):
    - Sentence structure
    - Core message content
    - Length (+/- 15% max)
    - Product mentions, prices, CTAs

Validation Checks:
    - Length change < 15%
    - 85%+ core words preserved
    - No new sentences added

Usage:
    python caption_enhancer.py --caption "Check this out babe" --creator missalexa
    python caption_enhancer.py --file captions.json --output enhanced.json
    python caption_enhancer.py --creator missalexa --format json
"""

import argparse
import json
import os
import random
import re
import sqlite3
import sys
from dataclasses import dataclass, field
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

# Enhancement thresholds
MAX_LENGTH_CHANGE = 0.15  # 15% maximum length change
MIN_WORD_PRESERVATION = 0.85  # 85% of words must be preserved
MAX_CHANGE_SCORE = 0.15  # Maximum acceptable change score before rollback

# Stopwords to exclude from word preservation calculation
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "and", "but", "if", "or", "because", "until",
    "while", "although", "though", "after", "i", "me", "my", "myself",
    "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself",
    "yourselves", "he", "him", "his", "himself", "she", "her", "hers",
    "herself", "it", "its", "itself", "they", "them", "their", "theirs",
    "themselves", "what", "which", "who", "whom", "this", "that", "these",
    "those", "am", "about", "against", "both", "also", "any",
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EnhancementResult:
    """Result of caption enhancement."""

    caption_id: int
    original_text: str
    enhanced_text: str
    tweaks_applied: list[str] = field(default_factory=list)
    change_score: float = 0.0  # 0.0-1.0 (lower = fewer changes)
    validation_passed: bool = True
    validation_errors: list[str] = field(default_factory=list)
    used_original: bool = False  # True if enhancement was rolled back

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "caption_id": self.caption_id,
            "original_text": self.original_text,
            "enhanced_text": self.enhanced_text,
            "tweaks_applied": self.tweaks_applied,
            "change_score": round(self.change_score, 3),
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
            "used_original": self.used_original,
        }


@dataclass
class PersonaContext:
    """Persona context for enhancement decisions."""

    creator_id: str
    page_name: str
    primary_tone: str = "playful"
    emoji_frequency: str = "moderate"  # heavy, moderate, light, none
    slang_level: str = "light"  # heavy, light, none
    favorite_emojis: list[str] = field(default_factory=list)


# =============================================================================
# CAPTION ENHANCER CLASS
# =============================================================================

class CaptionEnhancer:
    """
    Apply minor authenticity tweaks to captions.

    This class implements rule-based transformations that make captions
    sound more natural and human while preserving the core message.
    """

    # Pet name pools for rotation
    PET_NAMES_POOL = ["babe", "baby", "hun", "love", "sweetie", "handsome", "sexy"]

    # Contraction mappings (formal -> casual)
    CONTRACTIONS = {
        "do not": "don't",
        "does not": "doesn't",
        "did not": "didn't",
        "will not": "won't",
        "would not": "wouldn't",
        "could not": "couldn't",
        "should not": "shouldn't",
        "can not": "can't",
        "cannot": "can't",
        "is not": "isn't",
        "are not": "aren't",
        "was not": "wasn't",
        "were not": "weren't",
        "have not": "haven't",
        "has not": "hasn't",
        "had not": "hadn't",
        "I am": "I'm",
        "I have": "I've",
        "I will": "I'll",
        "I would": "I'd",
        "you are": "you're",
        "you have": "you've",
        "you will": "you'll",
        "you would": "you'd",
        "he is": "he's",
        "she is": "she's",
        "it is": "it's",
        "we are": "we're",
        "they are": "they're",
        "that is": "that's",
        "what is": "what's",
        "who is": "who's",
        "let us": "let's",
        "going to": "gonna",
        "want to": "wanna",
        "got to": "gotta",
        "kind of": "kinda",
        "sort of": "sorta",
    }

    # Heavy slang mappings (only for heavy slang personas)
    HEAVY_SLANG = {
        "you": "u",
        "your": "ur",
        "right now": "rn",
        "to be honest": "tbh",
        "by the way": "btw",
        "in my opinion": "imo",
        "for real": "fr",
        "because": "cuz",
        "tonight": "2nite",
    }

    # Emoji pools by emotion/context
    EMOJI_POOLS = {
        "excitement": ["\U0001F525", "\U0001F60D", "\U0001F975", "\U0001F495", "\u2728"],  # fire, heart_eyes, hot_face, two_hearts, sparkles
        "teasing": ["\U0001F60F", "\U0001F440", "\U0001F608", "\U0001F92D", "\U0001F48B"],  # smirk, eyes, imp, face_with_hand_over_mouth, kiss
        "urgency": ["\u23F0", "\U0001F6A8", "\u26A1", "\U0001F4A6"],  # alarm_clock, rotating_light, zap, sweat_droplets
        "affection": ["\U0001F495", "\u2764\uFE0F", "\U0001F970", "\U0001F618", "\U0001F497"],  # two_hearts, red_heart, smiling_face_with_hearts, kiss_face, growing_heart
    }

    # Context keywords for emoji matching
    EMOJI_CONTEXT_KEYWORDS = {
        "excitement": ["new", "just", "finally", "omg", "wow", "amazing", "incredible", "hot", "sexy"],
        "teasing": ["peek", "sneak", "tease", "curious", "want", "see", "show", "secret"],
        "urgency": ["now", "today", "limited", "hurry", "quick", "fast", "last", "ends"],
        "affection": ["love", "miss", "thinking", "special", "appreciate", "thank", "baby", "babe"],
    }

    # Pre-compiled patterns for performance
    _contraction_patterns: dict[str, re.Pattern] = {}
    _slang_patterns: dict[str, re.Pattern] = {}

    def __init__(self, persona: PersonaContext):
        """
        Initialize with creator persona for context.

        Args:
            persona: PersonaContext with creator's style preferences.
        """
        self.persona = persona
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        # Compile contraction patterns (case-insensitive)
        for formal, _ in self.CONTRACTIONS.items():
            if formal not in self._contraction_patterns:
                self._contraction_patterns[formal] = re.compile(
                    rf"\b{re.escape(formal)}\b",
                    re.IGNORECASE
                )

        # Compile slang patterns (case-insensitive, word boundaries)
        for word, _ in self.HEAVY_SLANG.items():
            if word not in self._slang_patterns:
                self._slang_patterns[word] = re.compile(
                    rf"\b{re.escape(word)}\b",
                    re.IGNORECASE
                )

    def enhance_caption(
        self,
        caption_id: int,
        original_text: str,
        context: dict[str, Any] | None = None
    ) -> EnhancementResult:
        """
        Apply minor tweaks to a caption based on persona.

        Args:
            caption_id: Caption identifier.
            original_text: Original caption text.
            context: Optional additional context (used_pet_names, etc.).

        Returns:
            EnhancementResult with enhanced text and metadata.
        """
        if context is None:
            context = {}

        result = EnhancementResult(
            caption_id=caption_id,
            original_text=original_text,
            enhanced_text=original_text,
        )

        text = original_text
        tweaks = []

        # 1. Apply contractions (always, unless persona is very formal)
        text, contraction_tweaks = self.apply_contractions(text)
        tweaks.extend(contraction_tweaks)

        # 2. Apply casual punctuation
        text, punct_tweaks = self.apply_casual_punctuation(text)
        tweaks.extend(punct_tweaks)

        # 3. Apply slang (only for heavy slang personas)
        if self.persona.slang_level == "heavy":
            text, slang_tweaks = self.apply_slang(text, "heavy")
            tweaks.extend(slang_tweaks)

        # 4. Rotate pet names if provided in context
        used_names = context.get("used_pet_names", set())
        if isinstance(used_names, list):
            used_names = set(used_names)
        text, name_tweaks = self.rotate_pet_names(text, used_names)
        tweaks.extend(name_tweaks)

        # 5. Apply emoji matching (based on persona emoji frequency)
        if self.persona.emoji_frequency in ("heavy", "moderate"):
            text, emoji_tweaks = self.apply_emoji_matching(
                text,
                self.persona.emoji_frequency
            )
            tweaks.extend(emoji_tweaks)

        # Update result
        result.enhanced_text = text
        result.tweaks_applied = tweaks

        # Calculate change score
        result.change_score = self.calculate_change_score(original_text, text)

        # Validate enhancement
        passed, errors = self.validate_enhancement(original_text, text)
        result.validation_passed = passed
        result.validation_errors = errors

        return result

    def apply_contractions(self, text: str) -> tuple[str, list[str]]:
        """
        Insert contractions where formal language exists.

        Args:
            text: Input text.

        Returns:
            Tuple of (modified text, list of tweaks applied).
        """
        tweaks = []
        modified = text

        for formal, casual in self.CONTRACTIONS.items():
            pattern = self._contraction_patterns.get(formal)
            if pattern and pattern.search(modified):
                # Preserve case of first character
                def replace_match(m: re.Match) -> str:
                    matched = m.group(0)
                    if matched[0].isupper():
                        # Capitalize first letter of replacement
                        return casual[0].upper() + casual[1:]
                    return casual

                new_text = pattern.sub(replace_match, modified)
                if new_text != modified:
                    tweaks.append(f"contraction:{formal}->{casual}")
                    modified = new_text

        return modified, tweaks

    def apply_emoji_matching(
        self,
        text: str,
        target_emoji_style: str
    ) -> tuple[str, list[str]]:
        """
        Add emojis to match creator's emoji frequency.

        Only adds emojis if the text doesn't already have enough,
        and only at appropriate positions (end of text).

        Args:
            text: Input text.
            target_emoji_style: 'heavy', 'moderate', 'light', or 'none'.

        Returns:
            Tuple of (modified text, list of tweaks applied).
        """
        tweaks = []

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
        existing_emojis = emoji_pattern.findall(text)
        existing_count = sum(len(e) for e in existing_emojis)

        # Determine target emoji count
        target_count = {
            "heavy": 3,
            "moderate": 2,
            "light": 1,
            "none": 0,
        }.get(target_emoji_style, 1)

        # Don't add emojis if we already have enough
        if existing_count >= target_count:
            return text, tweaks

        # Determine emoji context from text
        text_lower = text.lower()
        best_context = "excitement"  # Default
        best_score = 0

        for context, keywords in self.EMOJI_CONTEXT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_context = context

        # Select emoji based on context
        emoji_pool = self.EMOJI_POOLS.get(best_context, self.EMOJI_POOLS["excitement"])

        # Prefer creator's favorite emojis if available
        if self.persona.favorite_emojis:
            # Use favorite emoji if it matches the context pool or randomly
            emoji_to_add = random.choice(self.persona.favorite_emojis[:3])
        else:
            emoji_to_add = random.choice(emoji_pool)

        # Add emoji at end of text (preserve trailing punctuation)
        modified = text.rstrip()
        if modified and modified[-1] in ".!?":
            # Insert before final punctuation if it's just one
            if len(modified) > 1 and modified[-2] not in ".!?":
                modified = modified[:-1] + " " + emoji_to_add + modified[-1]
            else:
                modified = modified + " " + emoji_to_add
        else:
            modified = modified + " " + emoji_to_add

        tweaks.append(f"emoji_add:{emoji_to_add}")
        return modified, tweaks

    def apply_casual_punctuation(self, text: str) -> tuple[str, list[str]]:
        """
        Soften formal punctuation (periods to ellipses, etc.).

        Rules:
        - Multiple consecutive short sentences -> add ellipsis instead of period
        - "Hey." -> "Hey..." at start (if followed by more text)
        - Soften multiple exclamation marks

        Args:
            text: Input text.

        Returns:
            Tuple of (modified text, list of tweaks applied).
        """
        tweaks = []
        modified = text

        # Pattern: Short sentence followed by another sentence (formal style)
        # "Hey. Are you ready." -> "Hey... are you ready"
        short_sentence_pattern = re.compile(r"([A-Za-z]{2,10})\.\s+([A-Z])")

        def soften_period(m: re.Match) -> str:
            word = m.group(1)
            next_char = m.group(2)
            # Only soften if it's a short greeting-like word
            if word.lower() in ("hey", "hi", "yo", "so", "well", "ok", "okay"):
                return f"{word}... {next_char.lower()}"
            return m.group(0)

        new_text = short_sentence_pattern.sub(soften_period, modified)
        if new_text != modified:
            tweaks.append("casual_punct:period_to_ellipsis")
            modified = new_text

        # Reduce excessive exclamation marks (!!!! -> !!)
        excess_exclaim = re.compile(r"!{3,}")
        new_text = excess_exclaim.sub("!!", modified)
        if new_text != modified:
            tweaks.append("casual_punct:reduce_exclaim")
            modified = new_text

        # Add ellipsis to trailing thoughts (if ends with certain words)
        trailing_words = ["and", "but", "so", "like", "just", "maybe", "or"]
        words = modified.split()
        if words and words[-1].lower().rstrip(".,!?") in trailing_words:
            if not modified.rstrip().endswith("..."):
                modified = modified.rstrip(".,!? ") + "..."
                tweaks.append("casual_punct:trailing_ellipsis")

        return modified, tweaks

    def apply_slang(self, text: str, slang_level: str) -> tuple[str, list[str]]:
        """
        Apply slang for heavy slang personas only.

        This is conservative - only applies ONE safe substitution per caption
        to avoid exceeding change limits.

        Args:
            text: Input text.
            slang_level: 'heavy', 'light', or 'none'.

        Returns:
            Tuple of (modified text, list of tweaks applied).
        """
        tweaks = []

        if slang_level != "heavy":
            return text, tweaks

        modified = text

        # Only apply a subset of safe slang replacements
        # IMPORTANT: Only apply ONE slang replacement per caption to stay within limits
        safe_slang = {
            "to be honest": "tbh",
            "by the way": "btw",
            "for real": "fr",
            "right now": "rn",
        }

        for phrase, replacement in safe_slang.items():
            pattern = self._slang_patterns.get(phrase)
            if pattern and pattern.search(modified):
                new_text = pattern.sub(replacement, modified)
                if new_text != modified:
                    tweaks.append(f"slang:{phrase}->{replacement}")
                    modified = new_text
                    # Stop after ONE slang replacement to avoid too many changes
                    return modified, tweaks

        # Only apply "you" -> "u" if no phrase slang was applied
        # And only for single occurrences to minimize change
        if not tweaks and self.persona.slang_level == "heavy":
            # Conservative: only replace first standalone "you" in short text
            you_pattern = re.compile(r"\byou\b(?![a-z])", re.IGNORECASE)
            matches = you_pattern.findall(modified)
            # Only apply if exactly one "you" to minimize change
            if len(matches) == 1:
                new_text = you_pattern.sub("u", modified, count=1)
                if new_text != modified:
                    tweaks.append("slang:you->u")
                    modified = new_text

        return modified, tweaks

    def rotate_pet_names(
        self,
        text: str,
        used_names: set[str]
    ) -> tuple[str, list[str]]:
        """
        Rotate pet names to avoid repetition.

        If a pet name has been used recently, substitute with an alternative.

        Args:
            text: Input text.
            used_names: Set of pet names already used recently.

        Returns:
            Tuple of (modified text, list of tweaks applied).
        """
        tweaks = []
        modified = text

        # Find pet names in text
        for pet_name in self.PET_NAMES_POOL:
            pattern = re.compile(rf"\b{re.escape(pet_name)}\b", re.IGNORECASE)
            if pattern.search(modified) and pet_name.lower() in {n.lower() for n in used_names}:
                # Find an alternative that hasn't been used
                alternatives = [
                    name for name in self.PET_NAMES_POOL
                    if name.lower() not in {n.lower() for n in used_names}
                ]
                if alternatives:
                    replacement = random.choice(alternatives)

                    def replace_preserving_case(m: re.Match) -> str:
                        original = m.group(0)
                        if original[0].isupper():
                            return replacement.capitalize()
                        return replacement.lower()

                    new_text = pattern.sub(replace_preserving_case, modified)
                    if new_text != modified:
                        tweaks.append(f"pet_name_rotate:{pet_name}->{replacement}")
                        modified = new_text
                    break  # Only rotate one pet name per caption

        return modified, tweaks

    def validate_enhancement(
        self,
        original: str,
        enhanced: str
    ) -> tuple[bool, list[str]]:
        """
        Validate that enhancement stayed within bounds.

        Checks:
        - Length change < 15%
        - 85%+ core words preserved
        - No new sentences added

        Args:
            original: Original text.
            enhanced: Enhanced text.

        Returns:
            Tuple of (passed, list of error messages).
        """
        errors = []

        # Length check (+/- 15%)
        orig_len = len(original)
        new_len = len(enhanced)
        if orig_len > 0:
            length_change = abs(new_len - orig_len) / orig_len
            if length_change > MAX_LENGTH_CHANGE:
                errors.append(
                    f"Length change {length_change:.1%} exceeds {MAX_LENGTH_CHANGE:.0%} limit"
                )

        # Core words preserved check (85%+)
        # Extract words, excluding stopwords and contractions
        orig_words = set(
            w.lower() for w in re.findall(r"\b\w+\b", original.lower())
            if w.lower() not in STOPWORDS and len(w) > 2
        )
        # For new_words, also extract short words to catch slang abbreviations
        new_words = set(
            w.lower() for w in re.findall(r"\b\w+\b", enhanced.lower())
            if w.lower() not in STOPWORDS and len(w) > 2
        )
        # Separately extract short words that might be slang abbreviations
        new_words_all = set(
            w.lower() for w in re.findall(r"\b\w+\b", enhanced.lower())
        )

        if orig_words:
            # Check how many original content words are still present
            # (accounting for contractions like "do not" -> "don't"
            #  and slang abbreviations like "right now" -> "rn")

            # Slang abbreviation mappings (abbreviation -> original words)
            slang_preserves = {
                "rn": {"right", "now"},
                "tbh": {"to", "be", "honest"},
                "btw": {"by", "the", "way"},
                "fr": {"for", "real"},
                "imo": {"in", "my", "opinion"},
                "cuz": {"because"},
                "u": {"you"},
                "ur": {"your"},
            }

            # Build set of words that are considered "preserved" via slang
            # Check ALL words including short ones for slang abbreviations
            slang_preserved_words: set[str] = set()
            for abbrev in new_words_all:
                if abbrev in slang_preserves:
                    slang_preserved_words.update(slang_preserves[abbrev])

            # Pet names are interchangeable - any pet name can replace another
            pet_names_lower = {name.lower() for name in self.PET_NAMES_POOL}
            has_pet_name_in_new = bool(new_words_all & pet_names_lower)

            preserved_count = 0
            for word in orig_words:
                if word in new_words:
                    preserved_count += 1
                # Check if word was part of a contraction that got contracted
                elif any(word in formal.lower().split() for formal in self.CONTRACTIONS.keys()):
                    preserved_count += 1  # Count contracted words as preserved
                # Check if word was replaced by slang abbreviation
                elif word in slang_preserved_words:
                    preserved_count += 1  # Count slang-abbreviated words as preserved
                # Check if pet name was rotated to another pet name
                elif word in pet_names_lower and has_pet_name_in_new:
                    preserved_count += 1  # Count rotated pet names as preserved

            preserved_ratio = preserved_count / len(orig_words)
            if preserved_ratio < MIN_WORD_PRESERVATION:
                errors.append(
                    f"Only {preserved_ratio:.1%} of original words preserved "
                    f"(need {MIN_WORD_PRESERVATION:.0%}+)"
                )

        # No new sentences check
        # Count sentence-ending punctuation
        orig_sentences = len(re.findall(r"[.!?]+", original))
        new_sentences = len(re.findall(r"[.!?]+", enhanced))
        if new_sentences > orig_sentences + 1:
            errors.append(f"New sentences added: {new_sentences - orig_sentences}")

        return len(errors) == 0, errors

    def calculate_change_score(self, original: str, enhanced: str) -> float:
        """
        Calculate how much the text changed (0=identical, 1=completely different).

        Uses word-level comparison to properly handle minor tweaks like
        contractions and emoji additions.

        Args:
            original: Original text.
            enhanced: Enhanced text.

        Returns:
            Change score between 0.0 and 1.0.
        """
        if original == enhanced:
            return 0.0

        if not original or not enhanced:
            return 1.0

        # Normalize for comparison: lowercase, extract words
        orig_words = re.findall(r"\b\w+\b", original.lower())
        new_words = re.findall(r"\b\w+\b", enhanced.lower())

        if not orig_words:
            return 0.0 if not new_words else 1.0

        # Count word-level changes
        # Words that are in original but not in enhanced
        orig_set = set(orig_words)
        new_set = set(new_words)

        # Account for contractions: "do not" -> "don't" should count as minimal change
        # Map contracted forms back to their components
        contraction_components = {
            "don't": {"do", "not"},
            "doesn't": {"does", "not"},
            "didn't": {"did", "not"},
            "won't": {"will", "not"},
            "wouldn't": {"would", "not"},
            "couldn't": {"could", "not"},
            "shouldn't": {"should", "not"},
            "can't": {"can", "not", "cannot"},
            "isn't": {"is", "not"},
            "aren't": {"are", "not"},
            "wasn't": {"was", "not"},
            "weren't": {"were", "not"},
            "haven't": {"have", "not"},
            "hasn't": {"has", "not"},
            "hadn't": {"had", "not"},
            "i'm": {"i", "am"},
            "i've": {"i", "have"},
            "i'll": {"i", "will"},
            "i'd": {"i", "would"},
            "you're": {"you", "are"},
            "you've": {"you", "have"},
            "you'll": {"you", "will"},
            "you'd": {"you", "would"},
            "he's": {"he", "is"},
            "she's": {"she", "is"},
            "it's": {"it", "is"},
            "we're": {"we", "are"},
            "they're": {"they", "are"},
            "that's": {"that", "is"},
            "what's": {"what", "is"},
            "who's": {"who", "is"},
            "let's": {"let", "us"},
            "gonna": {"going", "to"},
            "wanna": {"want", "to"},
            "gotta": {"got", "to"},
            "kinda": {"kind", "of"},
            "sorta": {"sort", "of"},
        }

        # Also account for slang abbreviations
        slang_components = {
            "rn": {"right", "now"},
            "tbh": {"to", "be", "honest"},
            "btw": {"by", "the", "way"},
            "fr": {"for", "real"},
            "imo": {"in", "my", "opinion"},
            "cuz": {"because"},
            "u": {"you"},
            "ur": {"your"},
        }

        # Pet names are interchangeable - treat them as equivalent
        pet_names_lower = {name.lower() for name in self.PET_NAMES_POOL}
        has_pet_name_in_orig = bool(orig_set & pet_names_lower)
        has_pet_name_in_new = bool(new_set & pet_names_lower)

        # Expand new_set with contraction and slang equivalents
        expanded_new_set = set(new_set)
        for word in new_set:
            if word in contraction_components:
                expanded_new_set.update(contraction_components[word])
            if word in slang_components:
                expanded_new_set.update(slang_components[word])

        # Calculate how many original words are "missing" (not found or contracted)
        missing_count = 0
        for word in orig_set:
            if word not in expanded_new_set:
                # Pet name rotation is allowed - doesn't count as missing
                if word in pet_names_lower and has_pet_name_in_new:
                    continue  # Pet name was rotated, not missing
                # Check if it's a stopword (less important)
                elif word in STOPWORDS:
                    missing_count += 0.3  # Partial weight for stopwords
                else:
                    missing_count += 1.0

        # Calculate how many words were added
        # Don't count contractions, slang abbreviations, or rotated pet names as "new" words
        added_count = 0
        for word in new_set:
            if word not in orig_set and word not in contraction_components and word not in slang_components:
                # Pet name rotation is allowed - doesn't count as added
                if word in pet_names_lower and has_pet_name_in_orig:
                    continue  # Pet name was rotated in, not new
                added_count += 0.5  # Adding words is less penalized than removing

        # Total change normalized by original word count
        total_change = missing_count + added_count
        max_possible = len(orig_set) + len(new_set)

        if max_possible == 0:
            return 0.0

        # Also factor in length change (protect against division by zero)
        max_len = max(len(original), len(enhanced))
        length_change = abs(len(original) - len(enhanced)) / max_len if max_len > 0 else 0.0

        # Combine word-level and length-level changes
        # Word changes are more significant (70% weight)
        word_score = min(1.0, total_change / len(orig_set)) if orig_set else 0.0
        combined_score = (word_score * 0.7) + (length_change * 0.3)

        return min(1.0, combined_score)

    def enhance_with_rollback(
        self,
        caption_id: int,
        original_text: str,
        context: dict[str, Any] | None = None
    ) -> EnhancementResult:
        """
        Enhance caption with automatic rollback if validation fails.

        Args:
            caption_id: Caption identifier.
            original_text: Original caption text.
            context: Optional additional context.

        Returns:
            EnhancementResult with potential rollback to original.
        """
        result = self.enhance_caption(caption_id, original_text, context)

        # Check change score threshold
        if result.change_score > MAX_CHANGE_SCORE:
            result.used_original = True
            result.enhanced_text = original_text
            result.validation_errors.append(
                f"Change score {result.change_score:.2f} > {MAX_CHANGE_SCORE}, rolled back"
            )
            result.tweaks_applied = []

        # If validation failed, use original
        elif not result.validation_passed:
            result.used_original = True
            result.enhanced_text = original_text
            result.tweaks_applied = []

        return result


# =============================================================================
# ANTI-AI RED FLAGS DETECTOR
# =============================================================================

def detect_ai_red_flags(text: str) -> list[str]:
    """
    Detect patterns that suggest AI-generated content.

    These are red flags that should NOT be introduced by enhancement.

    Args:
        text: Text to analyze.

    Returns:
        List of detected red flags.
    """
    flags = []
    text_lower = text.lower()

    # Overly formal language patterns
    formal_patterns = [
        (r"\bi would like to offer\b", "formal: 'I would like to offer'"),
        (r"\bplease do not hesitate\b", "formal: 'please do not hesitate'"),
        (r"\bi am pleased to\b", "formal: 'I am pleased to'"),
        (r"\bkindly\b", "formal: 'kindly'"),
        (r"\bwhereby\b", "formal: 'whereby'"),
        (r"\bfurthermore\b", "formal: 'furthermore'"),
        (r"\bthus\b", "formal: 'thus'"),
        (r"\bhence\b", "formal: 'hence'"),
        (r"\bin conclusion\b", "formal: 'in conclusion'"),
    ]

    for pattern, flag in formal_patterns:
        if re.search(pattern, text_lower):
            flags.append(flag)

    # Perfect grammar with no personality (no contractions in long text)
    if len(text) > 100:
        has_contractions = any(c in text_lower for c in ["'m", "'re", "'ve", "'ll", "'t", "'d", "'s"])
        if not has_contractions:
            flags.append("no contractions in long text")

    # Generic phrases that could apply to anyone
    generic_patterns = [
        (r"\bcheck out this\b", "generic: 'check out this'"),
        (r"\bdon't miss this opportunity\b", "generic: 'don't miss this opportunity'"),
        (r"\bact now\b", "generic: 'act now'"),
        (r"\blimited time offer\b", "generic: 'limited time offer'"),
    ]

    for pattern, flag in generic_patterns:
        if re.search(pattern, text_lower):
            flags.append(flag)

    # Over-punctuated excitement
    if re.search(r"[!?]{3,}", text):
        flags.append("over-punctuated: excessive !!! or ???")

    # Repetitive sentence structures (starting same way 3+ times)
    sentences = re.split(r"[.!?]+", text)
    if len(sentences) >= 3:
        starts = [s.strip()[:20].lower() for s in sentences if s.strip()]
        if len(starts) >= 3:
            # Check for similar starts
            for i, start in enumerate(starts[:-2]):
                if starts[i + 1].startswith(start[:10]) and starts[i + 2].startswith(start[:10]):
                    flags.append("repetitive sentence structure")
                    break

    return flags


# =============================================================================
# AUTHENTICITY VERIFICATION PROMPT (for LLM use)
# =============================================================================

AUTHENTICITY_VERIFICATION_PROMPT = '''
## Authenticity Verification

Compare ORIGINAL vs ENHANCED caption:

ORIGINAL: "{original}"
ENHANCED: "{enhanced}"

Answer YES or NO:
1. Does ENHANCED sound like a real person texting?
2. Does ENHANCED avoid formal/corporate language?
3. Would this pass as a genuine DM from the creator?
4. Is ENHANCED equally or MORE authentic than ORIGINAL?

If ANY answer is NO, return: {{"use_original": true, "reason": "..."}}
If ALL answers are YES, return: {{"use_enhanced": true}}
'''


def build_authenticity_prompt(original: str, enhanced: str) -> str:
    """
    Build prompt for LLM-based authenticity verification.

    Args:
        original: Original caption text.
        enhanced: Enhanced caption text.

    Returns:
        Formatted prompt string.
    """
    return AUTHENTICITY_VERIFICATION_PROMPT.format(
        original=original,
        enhanced=enhanced,
    )


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def get_persona_from_db(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None
) -> PersonaContext | None:
    """
    Load persona context from database.

    Args:
        conn: Database connection.
        creator_name: Creator page name.
        creator_id: Creator UUID.

    Returns:
        PersonaContext or None if not found.
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

    # Parse favorite emojis from JSON
    favorite_emojis = []
    if row["favorite_emojis"]:
        try:
            favorite_emojis = json.loads(row["favorite_emojis"])
        except (json.JSONDecodeError, TypeError):
            pass

    return PersonaContext(
        creator_id=row["creator_id"],
        page_name=row["page_name"],
        primary_tone=row["primary_tone"] or "playful",
        emoji_frequency=row["emoji_frequency"] or "moderate",
        slang_level=row["slang_level"] or "light",
        favorite_emojis=favorite_emojis,
    )


def load_captions_from_db(
    conn: sqlite3.Connection,
    creator_id: str,
    limit: int = 50
) -> list[dict[str, Any]]:
    """
    Load captions from database for enhancement.

    Args:
        conn: Database connection.
        creator_id: Creator UUID.
        limit: Maximum captions to load.

    Returns:
        List of caption dictionaries.
    """
    query = """
        SELECT
            caption_id,
            caption_text
        FROM caption_bank
        WHERE is_active = 1
          AND (creator_id = ? OR is_universal = 1)
        ORDER BY performance_score DESC
        LIMIT ?
    """
    cursor = conn.execute(query, (creator_id, limit))

    captions = []
    for row in cursor.fetchall():
        captions.append({
            "caption_id": row["caption_id"],
            "caption_text": row["caption_text"],
        })

    return captions


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def format_markdown(
    persona: PersonaContext,
    results: list[EnhancementResult]
) -> str:
    """
    Format enhancement results as Markdown report.

    Args:
        persona: Persona context.
        results: List of EnhancementResult objects.

    Returns:
        Formatted Markdown string.
    """
    lines = [
        f"# Caption Enhancement Results: {persona.page_name}",
        "",
        "## Persona Context",
        "",
        "| Attribute | Value |",
        "|-----------|-------|",
        f"| Primary Tone | {persona.primary_tone} |",
        f"| Emoji Frequency | {persona.emoji_frequency} |",
        f"| Slang Level | {persona.slang_level} |",
        "",
    ]

    # Summary stats
    enhanced_count = sum(1 for r in results if not r.used_original)
    rollback_count = sum(1 for r in results if r.used_original)
    validation_failures = sum(1 for r in results if not r.validation_passed)

    lines.extend([
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total Captions | {len(results)} |",
        f"| Enhanced | {enhanced_count} |",
        f"| Rolled Back | {rollback_count} |",
        f"| Validation Failures | {validation_failures} |",
        "",
    ])

    # Tweak frequency
    tweak_counts: dict[str, int] = {}
    for r in results:
        for tweak in r.tweaks_applied:
            tweak_type = tweak.split(":")[0]
            tweak_counts[tweak_type] = tweak_counts.get(tweak_type, 0) + 1

    if tweak_counts:
        lines.extend([
            "## Tweak Frequency",
            "",
            "| Tweak Type | Count |",
            "|------------|-------|",
        ])
        for tweak_type, count in sorted(tweak_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {tweak_type} | {count} |")
        lines.append("")

    # Detailed results
    lines.extend([
        "## Detailed Results",
        "",
    ])

    for r in results[:30]:  # Limit display
        status = "ROLLBACK" if r.used_original else "ENHANCED"
        lines.extend([
            f"### Caption {r.caption_id} [{status}]",
            "",
            f"**Original:** {r.original_text[:200]}{'...' if len(r.original_text) > 200 else ''}",
            "",
            f"**Enhanced:** {r.enhanced_text[:200]}{'...' if len(r.enhanced_text) > 200 else ''}",
            "",
            f"**Change Score:** {r.change_score:.3f}",
            "",
        ])

        if r.tweaks_applied:
            lines.append(f"**Tweaks:** {', '.join(r.tweaks_applied)}")
            lines.append("")

        if r.validation_errors:
            lines.append(f"**Errors:** {', '.join(r.validation_errors)}")
            lines.append("")

        lines.append("---")
        lines.append("")

    if len(results) > 30:
        lines.append(f"*({len(results) - 30} more results not shown)*")
        lines.append("")

    return "\n".join(lines)


def format_json(
    persona: PersonaContext,
    results: list[EnhancementResult]
) -> str:
    """
    Format enhancement results as JSON.

    Args:
        persona: Persona context.
        results: List of EnhancementResult objects.

    Returns:
        JSON string.
    """
    data = {
        "persona": {
            "creator_id": persona.creator_id,
            "page_name": persona.page_name,
            "primary_tone": persona.primary_tone,
            "emoji_frequency": persona.emoji_frequency,
            "slang_level": persona.slang_level,
        },
        "summary": {
            "total": len(results),
            "enhanced": sum(1 for r in results if not r.used_original),
            "rolled_back": sum(1 for r in results if r.used_original),
            "validation_failures": sum(1 for r in results if not r.validation_passed),
        },
        "results": [r.to_dict() for r in results],
    }

    return json.dumps(data, indent=2, ensure_ascii=False)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Enhance captions for authenticity with minor tweaks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Enhancement Categories:
    - Contractions: "do not" -> "don't"
    - Emoji Match: Add emojis for heavy/moderate emoji users
    - Casual Punctuation: "Hey. Ready." -> "Hey... ready"
    - Slang (heavy only): "right now" -> "rn"
    - Pet Name Rotation: Avoid repetition of "babe", etc.

Validation Rules:
    - Length change must be < 15%
    - 85%+ of content words must be preserved
    - No new sentences can be added

Examples:
    python caption_enhancer.py --caption "Check this out babe" --creator missalexa
    python caption_enhancer.py --file captions.json --creator missalexa --output enhanced.json
    python caption_enhancer.py --creator missalexa --limit 20 --format json
        """
    )

    parser.add_argument(
        "--caption", "-t",
        help="Single caption text to enhance"
    )
    parser.add_argument(
        "--creator", "-c",
        help="Creator page name for persona context"
    )
    parser.add_argument(
        "--creator-id",
        help="Creator UUID for persona context"
    )
    parser.add_argument(
        "--file", "-f",
        help="JSON file with captions to enhance (array of {caption_id, caption_text})"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum captions to process from database (default: 50)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help=f"Database path (default: {DB_PATH})"
    )
    parser.add_argument(
        "--check-ai-flags",
        action="store_true",
        help="Also check for AI red flags in captions"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.caption and not args.file and not args.creator and not args.creator_id:
        parser.error(
            "Must specify --caption (for single text), "
            "--file (for batch), or --creator/--creator-id (for database)"
        )

    # Connect to database if needed
    conn = None
    if args.creator or args.creator_id or (not args.caption and not args.file):
        db_path = Path(args.db)
        if not db_path.exists():
            print(f"Error: Database not found: {db_path}", file=sys.stderr)
            sys.exit(1)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

    try:
        # Load persona
        if conn and (args.creator or args.creator_id):
            persona = get_persona_from_db(
                conn,
                creator_name=args.creator,
                creator_id=args.creator_id
            )
            if not persona:
                print("Error: Creator not found", file=sys.stderr)
                sys.exit(1)
        else:
            # Default persona for single caption testing
            persona = PersonaContext(
                creator_id="test",
                page_name="test",
                primary_tone="playful",
                emoji_frequency="moderate",
                slang_level="light",
            )

        # Initialize enhancer
        enhancer = CaptionEnhancer(persona)

        # Load captions
        captions: list[dict[str, Any]] = []

        if args.caption:
            # Single caption mode
            captions = [{"caption_id": 0, "caption_text": args.caption}]
        elif args.file:
            # File mode
            with open(args.file) as f:
                captions = json.load(f)
        elif conn:
            # Database mode
            captions = load_captions_from_db(conn, persona.creator_id, args.limit)

        if not captions:
            print("No captions to enhance", file=sys.stderr)
            sys.exit(1)

        # Enhance captions
        results = []
        for cap in captions:
            result = enhancer.enhance_with_rollback(
                cap["caption_id"],
                cap["caption_text"]
            )

            # Optionally check AI flags
            if args.check_ai_flags:
                flags = detect_ai_red_flags(result.enhanced_text)
                if flags:
                    result.validation_errors.extend([f"AI flag: {f}" for f in flags])

            results.append(result)

        # Format output
        if args.format == "json":
            output = format_json(persona, results)
        else:
            output = format_markdown(persona, results)

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"Results written to {args.output}")
        else:
            print(output)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
