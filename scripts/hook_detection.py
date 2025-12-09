#!/usr/bin/env python3
"""
Hook Detection - Hook type detection for caption diversity analysis.

Detects opening hook patterns to ensure variety in scheduled content
and prevent pattern detection by subscribers.

Hook Types:
    - CURIOSITY: "You won't believe...", "Guess what..."
    - PERSONAL: "I was thinking about you...", "Made this for you..."
    - EXCLUSIVITY: "Only sharing with...", "Just for you..."
    - RECENCY: "Just recorded...", "Fresh from..."
    - QUESTION: "Have you ever...", "Want to see...?"
    - DIRECT: "New video:", "Unlocked:"
    - TEASING: "Maybe I'll show you...", "If you're lucky..."

Usage:
    from hook_detection import HookType, detect_hook_type, SAME_HOOK_PENALTY

    hook_type, confidence = detect_hook_type("Guess what I just filmed...")
    # Returns (HookType.CURIOSITY, 0.6)
"""

import re
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "HookType",
    "HOOK_PATTERNS",
    "HOOK_COMPILED_PATTERNS",
    "HookDetectionResult",
    "detect_hook_type",
    "SAME_HOOK_PENALTY",
    "MIN_HOOK_DIVERSITY",
]

# Constants for penalty calculation
SAME_HOOK_PENALTY = 0.7  # 30% weight reduction for consecutive same hooks
MIN_HOOK_DIVERSITY = 4  # Minimum different hook types per week


class HookType(Enum):
    """
    Hook types for caption opening lines.

    Used to track and rotate hook styles to prevent detectable patterns
    that could indicate automated/scheduled content to fans.
    """

    CURIOSITY = "curiosity"  # "You won't believe...", "Guess what..."
    PERSONAL = "personal"  # "I was thinking about you...", "Made this for you..."
    EXCLUSIVITY = "exclusivity"  # "Only sharing with...", "Just for you..."
    RECENCY = "recency"  # "Just recorded...", "Fresh from..."
    QUESTION = "question"  # "Have you ever...", "Want to see...?"
    DIRECT = "direct"  # "New video:", "Unlocked:"
    TEASING = "teasing"  # "Maybe I'll show you...", "If you're lucky..."


# Hook patterns for each hook type
# Patterns are ordered by specificity (phrases first, then single words)
HOOK_PATTERNS: dict[str, list[str]] = {
    "curiosity": [
        "you won't believe",
        "guess what",
        "you'll never guess",
        "can you guess",
        "bet you didn't expect",
        "wait until you see",
        "you're not ready for",
        "prepare yourself",
        "i can't believe",
        "something special",
        "secret",
        "surprise",
        "curious",
        "wonder",
    ],
    "personal": [
        "thinking about you",
        "made this for you",
        "made this just for",
        "been thinking of you",
        "thought of you",
        "wanted you to see",
        "wanted to share with you",
        "couldn't stop thinking",
        "you were on my mind",
        "this made me think of you",
        "reminds me of you",
        "for my favorite",
        "for you baby",
        "just for you",
    ],
    "exclusivity": [
        "only sharing with",
        "just for my",
        "exclusive for",
        "only for my",
        "not sharing this anywhere else",
        "you're the only",
        "only you get to see",
        "nobody else gets",
        "keeping this between us",
        "our little secret",
        "vip only",
        "subscribers only",
        "exclusive",
        "private",
    ],
    "recency": [
        "just recorded",
        "just filmed",
        "just shot",
        "fresh from",
        "brand new",
        "hot off",
        "just finished",
        "literally just",
        "moments ago",
        "right now",
        "today's",
        "tonight's",
        "this morning",
        "fresh",
        "new",
    ],
    "question": [
        "have you ever",
        "want to see",
        "wanna see",
        "do you want",
        "would you like",
        "can you handle",
        "ready to see",
        "are you ready",
        "what would you do",
        "what if i",
        "should i",
        "do you think",
        "what do you think",
        "how would you",
    ],
    "direct": [
        "new video",
        "new content",
        "new post",
        "check this out",
        "look at this",
        "here's",
        "here is",
        "presenting",
        "introducing",
        "unlocked",
        "available now",
        "out now",
        "link in",
        "click",
        "tap",
    ],
    "teasing": [
        "maybe i'll show you",
        "if you're lucky",
        "might let you see",
        "if you're good",
        "if you behave",
        "you might get to",
        "i might share",
        "tempted to show",
        "should i tease you",
        "wouldn't you like to know",
        "i'll never tell",
        "wouldn't you like",
        "tease",
        "hint",
        "sneak peek",
        "preview",
    ],
}

# Pre-compiled hook type patterns: dict[hook_type, list[tuple[pattern_str, compiled_pattern, is_phrase]]]
# Phrases are checked with substring matching, single words with word boundary regex
HOOK_COMPILED_PATTERNS: dict[str, list[tuple[str, re.Pattern | None, bool]]] = {
    hook_type: [
        (
            pattern,
            None if " " in pattern else re.compile(rf"\b{re.escape(pattern)}\b", re.IGNORECASE),
            " " in pattern,  # is_phrase
        )
        for pattern in patterns
    ]
    for hook_type, patterns in HOOK_PATTERNS.items()
}


@dataclass(frozen=True, slots=True)
class HookDetectionResult:
    """Result of hook type detection."""

    hook_type: HookType
    confidence: float
    matched_pattern: str | None = None


def detect_hook_type(caption_text: str) -> tuple[HookType, float]:
    """
    Detect the hook type used in a caption's opening.

    Hook types are detected by analyzing the caption text for patterns
    that indicate different engagement strategies (curiosity, personal,
    exclusivity, recency, question, direct, teasing).

    Uses pre-compiled HOOK_COMPILED_PATTERNS for performance.
    Phrases are given 2x weight compared to single words.
    Only the first 200 characters are analyzed (hooks are typically at the start).

    Args:
        caption_text: The caption text to analyze

    Returns:
        Tuple of (HookType, confidence_score)
        - HookType: The detected hook type enum value
        - confidence_score: Float between 0.0-1.0 indicating match confidence
        - Returns (HookType.DIRECT, 0.3) as fallback if no patterns match
    """
    if not caption_text:
        return HookType.DIRECT, 0.3

    # Only analyze the first 200 chars (hooks are at the start)
    text_to_analyze = caption_text[:200].lower()

    scores: dict[str, float] = {}

    for hook_type, patterns in HOOK_COMPILED_PATTERNS.items():
        score = 0.0
        for pattern_str, compiled_pattern, is_phrase in patterns:
            if is_phrase:
                # Phrase: use substring matching (phrases get 2x weight)
                if pattern_str in text_to_analyze:
                    score += 2.0
            else:
                # Single word: use pre-compiled pattern
                if compiled_pattern and compiled_pattern.search(text_to_analyze):
                    score += 1.0

        if score > 0:
            scores[hook_type] = score

    if not scores:
        # No patterns matched - return default
        return HookType.DIRECT, 0.3

    # Find the hook type with highest score
    best_hook_type = max(scores, key=lambda t: scores[t])
    best_score = scores[best_hook_type]

    # Calculate confidence based on score
    # - Score of 1 (single word match) = 0.4 confidence
    # - Score of 2 (phrase match) = 0.6 confidence
    # - Score of 3+ = 0.7-0.9 confidence
    # - Score of 5+ = 0.9+ confidence
    if best_score <= 1:
        confidence = 0.4
    elif best_score <= 2:
        confidence = 0.6
    elif best_score <= 4:
        confidence = 0.7 + (best_score - 3) * 0.1
    else:
        confidence = min(0.9 + (best_score - 5) * 0.02, 1.0)

    # Convert string to HookType enum
    hook_type_enum = HookType(best_hook_type)

    return hook_type_enum, round(confidence, 2)
