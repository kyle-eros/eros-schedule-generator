#!/usr/bin/env python3
"""
Match Persona - Persona matching for caption selection.

This script calculates persona boost factors for captions based on
how well they match a creator's voice profile.

Boost Factors:
    - Primary tone match: 1.20x
    - Secondary tone match: 1.10x
    - Emoji frequency match: 1.05x
    - Slang level match: 1.05x
    - Sentiment alignment: 1.05x
    - Maximum combined: 1.40x (capped)

No-Match Penalty:
    - When zero persona signals match (tone, emoji, slang, sentiment),
      a 0.95x penalty is applied instead of neutral 1.0x
    - This encourages better caption selection and persona alignment

Text Detection:
    - Text detection is ALWAYS enabled and should remain so
    - It is critical for captions that don't have tone/slang/emoji
      stored in the database
    - Without it, many captions would incorrectly receive the penalty

Usage:
    python match_persona.py --creator missalexa
    python match_persona.py --creator-id abc123 --output matches.json
    python match_persona.py --creator missalexa --caption-id 12345
"""

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared_context import PersonaProfile

# Path resolution for database
SCRIPT_DIR = Path(__file__).parent

from database import DB_PATH  # noqa: E402

# Boost configuration
PRIMARY_TONE_BOOST = 1.20
SECONDARY_TONE_BOOST = 1.10
EMOJI_FREQUENCY_BOOST = 1.05
SLANG_LEVEL_BOOST = 1.05
SENTIMENT_ALIGNMENT_BOOST = 1.05
MAX_COMBINED_BOOST = 1.40
NO_MATCH_PENALTY = 0.95  # 5% penalty when zero persona signals match

# Tone definitions with keyword patterns for text-based detection
TONE_OPTIONS = ["playful", "aggressive", "sweet", "dominant", "bratty", "seductive", "direct"]

# Tone keyword patterns for text-based detection
TONE_KEYWORDS: dict[str, list[str]] = {
    "playful": [
        "hehe",
        "haha",
        "lol",
        "tease",
        "fun",
        "silly",
        "naughty",
        "game",
        "peek",
        "sneak",
        "surprise",
        "wink",
        "giggle",
        "oops",
        "whoops",
    ],
    "aggressive": [
        "now",
        "demand",
        "obey",
        "serve",
        "worship",
        "kneel",
        "beg",
        "command",
        "order",
        "submit",
        "punish",
        "must",
        "immediately",
    ],
    "sweet": [
        "baby",
        "honey",
        "sweetheart",
        "darling",
        "love",
        "miss you",
        "thinking of you",
        "xoxo",
        "kisses",
        "hugs",
        "cuddle",
        "appreciate",
    ],
    "dominant": [
        "control",
        "power",
        "dominate",
        "boss",
        "authority",
        "rule",
        "permission",
        "allow",
        "decide",
        "own",
        "master",
        "mistress",
    ],
    "bratty": [
        "whatever",
        "duh",
        "like",
        "omg",
        "totally",
        "ugh",
        "please",
        "pretty please",
        "spoil",
        "deserve",
        "want",
        "gimme",
        "fine",
    ],
    "seductive": [
        "seduce",
        "tempt",
        "desire",
        "crave",
        "lust",
        "sensual",
        "intimate",
        "taste",
        "explore",
        "pleasure",
        "fantasy",
        "dream",
        "whisper",
    ],
    "direct": [
        "exclusive",
        "deal",
        "unlock",
        "sale",
        "limited",
        "offer",
        "price",
        "only",
        "today",
        "special",
        "save",
        "worth",
        "value",
        "get",
        "discount",
        "dm",
        "tip",
        "subscribe",
        "free",
        "trial",
        "vip",
        "access",
        "link",
        "check out",
        "available",
        "content",
        "bundle",
    ],
}

# Slang patterns for text-based detection
SLANG_PATTERNS: dict[str, list[str]] = {
    "heavy": [
        "af",
        "asf",
        "ngl",
        "fr",
        "lowkey",
        "highkey",
        "bussin",
        "sus",
        "bet",
        "cap",
        "no cap",
        "periodt",
        "slay",
        "goated",
        "lit",
    ],
    "light": [
        "gonna",
        "wanna",
        "gotta",
        "kinda",
        "sorta",
        "ya",
        "yea",
        "nah",
        "btw",
        "tbh",
        "omg",
        "lmao",
        "lol",
        "rn",
        "imo",
    ],
    "none": [],  # Formal language, no slang markers
}

# Sentiment word lists for alignment scoring
POSITIVE_WORDS = [
    "love",
    "amazing",
    "incredible",
    "best",
    "perfect",
    "beautiful",
    "gorgeous",
    "hot",
    "sexy",
    "exclusive",
    "special",
    "favorite",
    "lucky",
    "reward",
    "treat",
    "gift",
    "worth",
    "premium",
    "quality",
    "stunning",
    "wow",
]

NEGATIVE_WORDS = [
    "miss",
    "regret",
    "hurry",
    "limited",
    "last",
    "final",
    "ending",
    "gone",
    "sold out",
    "missed",
    "never",
    "don't miss",
]

# Emoji frequency levels
EMOJI_FREQUENCY_OPTIONS = ["heavy", "moderate", "light", "none"]

# Slang levels
SLANG_LEVEL_OPTIONS = ["none", "light", "heavy"]


# =============================================================================
# PRE-COMPILED PATTERNS FOR PERFORMANCE
# These are compiled once at module load instead of on every function call
# =============================================================================

# Pre-compiled emoji pattern
EMOJI_PATTERN = re.compile(
    "[\U0001f600-\U0001f64f"  # Emoticons
    "\U0001f300-\U0001f5ff"  # Misc Symbols and Pictographs
    "\U0001f680-\U0001f6ff"  # Transport and Map
    "\U0001f1e0-\U0001f1ff"  # Flags
    "\U00002702-\U000027b0"  # Dingbats
    "\U0001f900-\U0001f9ff"  # Supplemental Symbols
    "\U0001fa00-\U0001fa6f"  # Chess Symbols
    "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
    "\U00002600-\U000026ff"  # Misc Symbols
    "]+",
    flags=re.UNICODE,
)

# Pre-compiled tone keyword patterns: dict[tone, list[tuple[keyword, pattern, is_phrase]]]
TONE_COMPILED_PATTERNS: dict[str, list[tuple[str, re.Pattern, bool]]] = {
    tone: [(kw, re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE), " " in kw) for kw in keywords]
    for tone, keywords in TONE_KEYWORDS.items()
}

# Pre-compiled slang patterns
SLANG_COMPILED_PATTERNS: dict[str, list[re.Pattern]] = {
    level: [re.compile(rf"\b{re.escape(slang)}\b", re.IGNORECASE) for slang in patterns]
    for level, patterns in SLANG_PATTERNS.items()
}

# Pre-compiled sentiment patterns
POSITIVE_COMPILED_PATTERNS: list[re.Pattern] = [
    re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE) for word in POSITIVE_WORDS
]

NEGATIVE_COMPILED_PATTERNS: list[tuple[str, re.Pattern | None]] = [
    (word, None if " " in word else re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE))
    for word in NEGATIVE_WORDS
]


@dataclass(slots=True)
class PersonaMatchResult:
    """Result of persona matching for a caption."""

    caption_id: int
    caption_text: str | None
    caption_tone: str | None
    caption_emoji_style: str | None
    caption_slang_level: str | None
    detected_tone: str | None = None  # Text-based tone detection
    detected_slang_level: str | None = None  # Text-based slang detection
    caption_sentiment: float = 0.5  # 0.0-1.0 sentiment score
    tone_match: bool = False
    emoji_match: bool = False
    slang_match: bool = False
    sentiment_match: bool = False  # New: sentiment alignment
    tone_boost: float = 1.0
    emoji_boost: float = 1.0
    slang_boost: float = 1.0
    sentiment_boost: float = 1.0  # New: sentiment alignment boost
    total_boost: float = 1.0
    match_details: list[str] = field(default_factory=list)


def count_emojis(text: str) -> int:
    """
    Count the number of emojis in text.

    Uses pre-compiled EMOJI_PATTERN for performance.
    """
    emojis = EMOJI_PATTERN.findall(text)
    # Each match might contain multiple emojis
    return sum(len(match) for match in emojis)


def get_emoji_frequency_category(text: str) -> str:
    """
    Categorize emoji frequency in text.

    Categories:
        - heavy: 3+ emojis
        - moderate: 1-2 emojis
        - light: 1 emoji
        - none: 0 emojis
    """
    count = count_emojis(text)

    if count >= 3:
        return "heavy"
    elif count == 2:
        return "moderate"
    elif count == 1:
        return "light"
    else:
        return "none"


def detect_tone_from_text(text: str) -> tuple[str | None, dict[str, int]]:
    """
    Detect tone from caption text using keyword matching.

    Uses pre-compiled TONE_COMPILED_PATTERNS for performance.
    Returns the tone with the highest match count.

    Args:
        text: Caption text to analyze

    Returns:
        Tuple of (detected_tone, scores_dict)
        detected_tone is None if no keywords matched
    """
    if not text:
        return None, {}

    text_lower = text.lower()
    scores: dict[str, int] = {}

    for tone, patterns in TONE_COMPILED_PATTERNS.items():
        score = 0
        for keyword, pattern, is_phrase in patterns:
            if is_phrase:
                # Phrase: use substring matching (phrases get higher weight)
                if keyword in text_lower:
                    score += 2
            else:
                # Single word: use pre-compiled pattern
                matches = pattern.findall(text_lower)
                score += len(matches)

        if score > 0:
            scores[tone] = score

    if not scores:
        return None, {}

    # Return tone with highest score
    detected_tone = max(scores, key=lambda t: scores[t])
    return detected_tone, scores


def detect_slang_level_from_text(text: str) -> str:
    """
    Detect slang level from caption text.

    Uses pre-compiled SLANG_COMPILED_PATTERNS for performance.
    Categorizes as: heavy, light, or none.

    Args:
        text: Caption text to analyze

    Returns:
        Detected slang level ('heavy', 'light', or 'none')
    """
    if not text:
        return "none"

    text_lower = text.lower()

    # Count heavy slang matches using pre-compiled patterns
    heavy_count = 0
    for pattern in SLANG_COMPILED_PATTERNS["heavy"]:
        heavy_count += len(pattern.findall(text_lower))

    if heavy_count >= 2:
        return "heavy"

    # Count light slang matches using pre-compiled patterns
    light_count = 0
    for pattern in SLANG_COMPILED_PATTERNS["light"]:
        light_count += len(pattern.findall(text_lower))

    if light_count >= 2 or heavy_count >= 1:
        return "light"

    return "none"


def calculate_sentiment(text: str) -> float:
    """
    Calculate simple sentiment score for caption text.

    Uses pre-compiled POSITIVE_COMPILED_PATTERNS and NEGATIVE_COMPILED_PATTERNS.
    Score ranges from 0.0 (very negative/urgent) to 1.0 (very positive).

    Args:
        text: Caption text to analyze

    Returns:
        Sentiment score between 0.0 and 1.0
    """
    if not text:
        return 0.5

    text_lower = text.lower()

    # Count positive word matches using pre-compiled patterns
    positive_count = 0
    for pattern in POSITIVE_COMPILED_PATTERNS:
        positive_count += len(pattern.findall(text_lower))

    # Count negative word matches using pre-compiled patterns
    negative_count = 0
    for word, pattern in NEGATIVE_COMPILED_PATTERNS:
        if pattern is None:
            # Phrase: use substring matching
            if word in text_lower:
                negative_count += 1
        else:
            # Single word: use pre-compiled pattern
            negative_count += len(pattern.findall(text_lower))

    # Calculate score based on ratio
    total = positive_count + negative_count
    if total == 0:
        return 0.5  # Neutral

    # Positive words push toward 1.0, negative toward 0.0
    # But we want a balanced formula that accounts for urgency
    positive_ratio = positive_count / total
    base_score = 0.3 + (positive_ratio * 0.5)  # Range: 0.3-0.8

    # Boost if strongly positive
    if positive_count >= 3 and negative_count == 0:
        base_score = min(base_score + 0.15, 1.0)

    return round(base_score, 2)


def check_sentiment_alignment(
    caption_sentiment: float, persona_sentiment: float, tolerance: float = 0.25
) -> bool:
    """
    Check if caption sentiment aligns with persona's average sentiment.

    Args:
        caption_sentiment: Sentiment score of caption (0.0-1.0)
        persona_sentiment: Persona's average sentiment (0.0-1.0)
        tolerance: How close sentiments need to be (default 0.25)

    Returns:
        True if sentiments are aligned within tolerance
    """
    return abs(caption_sentiment - persona_sentiment) <= tolerance


def get_persona_profile(
    conn: sqlite3.Connection, creator_name: str | None = None, creator_id: str | None = None
) -> PersonaProfile | None:
    """
    Load creator persona profile from database.

    Args:
        conn: Database connection
        creator_name: Creator page name (optional)
        creator_id: Creator UUID (optional)

    Returns:
        PersonaProfile or None if not found

    Raises:
        ValueError: If neither creator_name nor creator_id is provided.
    """
    if not creator_name and not creator_id:
        raise ValueError("Must provide either creator_name or creator_id")

    if creator_name:
        query = """
            SELECT
                c.creator_id,
                c.page_name,
                cp.primary_tone,
                cp.secondary_tone,
                cp.emoji_frequency,
                cp.favorite_emojis,
                cp.slang_level,
                cp.avg_sentiment,
                cp.avg_caption_length
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
                cp.secondary_tone,
                cp.emoji_frequency,
                cp.favorite_emojis,
                cp.slang_level,
                cp.avg_sentiment,
                cp.avg_caption_length
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
    favorite_emojis: tuple[str, ...] = ()
    if row["favorite_emojis"]:
        try:
            parsed = json.loads(row["favorite_emojis"])
            favorite_emojis = tuple(parsed) if parsed else ()
        except (json.JSONDecodeError, TypeError):
            pass

    return PersonaProfile(
        creator_id=row["creator_id"],
        page_name=row["page_name"],
        primary_tone=row["primary_tone"] or "playful",
        secondary_tone=row["secondary_tone"],  # Query from database
        emoji_frequency=row["emoji_frequency"] or "moderate",
        favorite_emojis=favorite_emojis,
        slang_level=row["slang_level"] or "light",
        avg_sentiment=row["avg_sentiment"] or 0.5,
        avg_caption_length=row["avg_caption_length"] or 100,
    )


def calculate_persona_boost(
    caption_tone: str | None,
    caption_emoji_style: str | None,
    caption_slang_level: str | None,
    persona: PersonaProfile,
    caption_text: str | None = None,
    use_text_detection: bool = True,
) -> PersonaMatchResult:
    """
    Calculate persona boost factor for a caption.

    Boost factors (cumulative, capped at 1.40x):
        - Primary tone match: 1.20x
        - Secondary tone match: 1.10x
        - Emoji frequency match: 1.05x
        - Slang level match: 1.05x
        - Sentiment alignment: 1.05x

    No-match penalty:
        - When zero persona signals match (tone, emoji, slang, sentiment),
          a 0.95x penalty is applied instead of neutral 1.0x
        - This encourages better caption selection and persona alignment

    Text detection is ALWAYS enabled by default and should remain so.
    It is critical for captions that don't have tone/slang/emoji stored
    in the database. Without it, many captions would incorrectly receive
    the no-match penalty.

    Args:
        caption_tone: Caption's tone attribute (from database)
        caption_emoji_style: Caption's emoji style (from database)
        caption_slang_level: Caption's slang level (from database)
        persona: Creator's persona profile
        caption_text: Optional caption text for text-based detection
        use_text_detection: Whether to use text-based detection (always True)

    Returns:
        PersonaMatchResult with boost details
    """
    result = PersonaMatchResult(
        caption_id=0,
        caption_text=caption_text,
        caption_tone=caption_tone,
        caption_emoji_style=caption_emoji_style,
        caption_slang_level=caption_slang_level,
    )

    total_boost = 1.0

    # Text-based detection for missing attributes
    effective_tone = caption_tone
    effective_slang = caption_slang_level
    effective_emoji = caption_emoji_style

    if use_text_detection and caption_text:
        # Detect tone from text if not set
        if not effective_tone:
            detected_tone, tone_scores = detect_tone_from_text(caption_text)
            if detected_tone:
                result.detected_tone = detected_tone
                effective_tone = detected_tone

        # Detect slang level from text if not set
        if not effective_slang:
            detected_slang = detect_slang_level_from_text(caption_text)
            result.detected_slang_level = detected_slang
            effective_slang = detected_slang

        # Detect emoji frequency from text if not set
        if not effective_emoji:
            effective_emoji = get_emoji_frequency_category(caption_text)

        # Calculate sentiment for alignment checking
        # Only runs when text detection is enabled
        result.caption_sentiment = calculate_sentiment(caption_text)

    # Check primary tone match (1.20x boost)
    if effective_tone and persona.primary_tone:
        if effective_tone.lower() == persona.primary_tone.lower():
            result.tone_match = True
            result.tone_boost = PRIMARY_TONE_BOOST
            total_boost *= PRIMARY_TONE_BOOST
            source = "(detected)" if result.detected_tone else ""
            result.match_details.append(
                f"Primary tone match ({effective_tone}{source}): {PRIMARY_TONE_BOOST:.2f}x"
            )
        elif persona.secondary_tone and effective_tone.lower() == persona.secondary_tone.lower():
            result.tone_match = True
            result.tone_boost = SECONDARY_TONE_BOOST
            total_boost *= SECONDARY_TONE_BOOST
            source = "(detected)" if result.detected_tone else ""
            result.match_details.append(
                f"Secondary tone match ({effective_tone}{source}): {SECONDARY_TONE_BOOST:.2f}x"
            )

    # Check emoji frequency match (1.05x boost)
    if effective_emoji and persona.emoji_frequency:
        if effective_emoji.lower() == persona.emoji_frequency.lower():
            result.emoji_match = True
            result.emoji_boost = EMOJI_FREQUENCY_BOOST
            total_boost *= EMOJI_FREQUENCY_BOOST
            result.match_details.append(
                f"Emoji frequency match ({effective_emoji}): {EMOJI_FREQUENCY_BOOST:.2f}x"
            )

    # Check slang level match (1.05x boost)
    if effective_slang and persona.slang_level:
        if effective_slang.lower() == persona.slang_level.lower():
            result.slang_match = True
            result.slang_boost = SLANG_LEVEL_BOOST
            total_boost *= SLANG_LEVEL_BOOST
            source = "(detected)" if result.detected_slang_level else ""
            result.match_details.append(
                f"Slang level match ({effective_slang}{source}): {SLANG_LEVEL_BOOST:.2f}x"
            )

    # Check sentiment alignment (1.05x boost) - only if text detection is enabled
    if use_text_detection and caption_text and persona.avg_sentiment:
        if check_sentiment_alignment(result.caption_sentiment, persona.avg_sentiment):
            result.sentiment_match = True
            result.sentiment_boost = SENTIMENT_ALIGNMENT_BOOST
            total_boost *= SENTIMENT_ALIGNMENT_BOOST
            result.match_details.append(
                f"Sentiment aligned ({result.caption_sentiment:.2f} ~ {persona.avg_sentiment:.2f}): "
                f"{SENTIMENT_ALIGNMENT_BOOST:.2f}x"
            )

    # Check if ANY persona signal matched
    has_any_match = any(
        [
            result.tone_match,
            result.emoji_match,
            result.slang_match,
            result.sentiment_match,
        ]
    )

    if not has_any_match:
        # No persona signals matched - apply 5% penalty
        result.total_boost = NO_MATCH_PENALTY
        result.match_details.append(f"No persona match - penalty applied: {NO_MATCH_PENALTY:.2f}x")
    else:
        # Cap at maximum boost (existing logic)
        result.total_boost = min(total_boost, MAX_COMBINED_BOOST)

        if result.total_boost == MAX_COMBINED_BOOST and total_boost > MAX_COMBINED_BOOST:
            result.match_details.append(
                f"Boost capped at {MAX_COMBINED_BOOST:.2f}x (was {total_boost:.2f}x)"
            )

    return result


def match_captions_to_persona(
    conn: sqlite3.Connection,
    persona: PersonaProfile,
    caption_id: int | None = None,
    limit: int = 100,
    use_text_detection: bool = True,
) -> list[PersonaMatchResult]:
    """
    Match captions to a persona and calculate boosts.

    Uses both database attributes and text-based detection for matching.
    When database attributes are missing, the caption text is analyzed
    to detect tone, slang level, and sentiment.

    Text detection is ALWAYS enabled by default and should remain so.
    Without text detection, captions missing database attributes would
    incorrectly receive the NO_MATCH_PENALTY (0.95x).

    Args:
        conn: Database connection
        persona: Creator's persona profile
        caption_id: Optional specific caption to match
        limit: Maximum number of captions to process
        use_text_detection: Whether to use text-based detection (always True)

    Returns:
        List of PersonaMatchResult sorted by boost (descending)
    """
    query = """
        SELECT
            caption_id,
            caption_text,
            tone,
            emoji_style,
            slang_level
        FROM caption_bank
        WHERE is_active = 1
          AND (creator_id = ? OR is_universal = 1)
    """
    params: list[Any] = [persona.creator_id]

    if caption_id:
        query += " AND caption_id = ?"
        params.append(caption_id)

    query += f" LIMIT {limit}"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        match_result = calculate_persona_boost(
            caption_tone=row["tone"],
            caption_emoji_style=row["emoji_style"],
            caption_slang_level=row["slang_level"],
            persona=persona,
            caption_text=row["caption_text"],
            use_text_detection=use_text_detection,
        )

        match_result.caption_id = row["caption_id"]

        results.append(match_result)

    # Sort by total boost (descending)
    results.sort(key=lambda r: r.total_boost, reverse=True)

    return results


def format_markdown(persona: PersonaProfile, results: list[PersonaMatchResult]) -> str:
    """Format results as Markdown."""
    lines = [
        f"# Persona Match Results: {persona.page_name}",
        "",
        "## Persona Profile",
        "",
        "| Attribute | Value |",
        "|-----------|-------|",
        f"| Primary Tone | {persona.primary_tone} |",
        f"| Emoji Frequency | {persona.emoji_frequency} |",
        f"| Slang Level | {persona.slang_level} |",
        f"| Avg Sentiment | {persona.avg_sentiment:.2f} |",
        f"| Avg Caption Length | {persona.avg_caption_length} |",
        "",
    ]

    if persona.favorite_emojis:
        lines.append(f"**Favorite Emojis:** {' '.join(persona.favorite_emojis[:10])}")
        lines.append("")

    # Summary stats
    perfect_matches = sum(1 for r in results if r.total_boost >= 1.30)
    good_matches = sum(1 for r in results if 1.10 <= r.total_boost < 1.30)
    neutral_matches = sum(1 for r in results if r.total_boost == 1.0)
    penalized = sum(1 for r in results if r.total_boost == NO_MATCH_PENALTY)
    sentiment_aligned = sum(1 for r in results if r.sentiment_match)
    detected_tones = sum(1 for r in results if r.detected_tone)

    lines.extend(
        [
            "## Match Summary",
            "",
            "| Category | Count |",
            "|----------|-------|",
            f"| Perfect Match (>= 1.30x) | {perfect_matches} |",
            f"| Good Match (1.10-1.30x) | {good_matches} |",
            f"| Neutral (1.0x) | {neutral_matches} |",
            f"| Penalized (0.95x) | {penalized} |",
            f"| Sentiment Aligned | {sentiment_aligned} |",
            f"| Tones Detected (text) | {detected_tones} |",
            f"| Total Captions | {len(results)} |",
            "",
        ]
    )

    lines.extend(
        [
            "## Caption Matches",
            "",
            "| ID | Tone | Emoji | Slang | Sent | Boost | Details |",
            "|----|------|-------|-------|------|-------|---------|",
        ]
    )

    for r in results[:50]:  # Limit display
        tone_check = "Y" if r.tone_match else "-"
        emoji_check = "Y" if r.emoji_match else "-"
        slang_check = "Y" if r.slang_match else "-"
        sent_check = "Y" if r.sentiment_match else "-"
        details = "; ".join(r.match_details) if r.match_details else "-"

        lines.append(
            f"| {r.caption_id} | {tone_check} | {emoji_check} | {slang_check} | {sent_check} | "
            f"{r.total_boost:.2f}x | {details} |"
        )

    if len(results) > 50:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ({len(results) - 50} more) |")

    lines.append("")
    return "\n".join(lines)


def format_json(persona: PersonaProfile, results: list[PersonaMatchResult]) -> str:
    """Format results as JSON."""
    data = {
        "persona": {
            "creator_id": persona.creator_id,
            "page_name": persona.page_name,
            "primary_tone": persona.primary_tone,
            "emoji_frequency": persona.emoji_frequency,
            "slang_level": persona.slang_level,
            "avg_sentiment": persona.avg_sentiment,
            "favorite_emojis": persona.favorite_emojis,
        },
        "summary": {
            "total_captions": len(results),
            "perfect_matches": sum(1 for r in results if r.total_boost >= 1.30),
            "good_matches": sum(1 for r in results if 1.10 <= r.total_boost < 1.30),
            "neutral_matches": sum(1 for r in results if r.total_boost == 1.0),
            "penalized": sum(1 for r in results if r.total_boost == NO_MATCH_PENALTY),
            "sentiment_aligned": sum(1 for r in results if r.sentiment_match),
            "tones_detected": sum(1 for r in results if r.detected_tone),
        },
        "matches": [
            {
                "caption_id": r.caption_id,
                "tone": r.caption_tone,
                "detected_tone": r.detected_tone,
                "emoji_style": r.caption_emoji_style,
                "slang_level": r.caption_slang_level,
                "detected_slang_level": r.detected_slang_level,
                "caption_sentiment": round(r.caption_sentiment, 2),
                "tone_match": r.tone_match,
                "emoji_match": r.emoji_match,
                "slang_match": r.slang_match,
                "sentiment_match": r.sentiment_match,
                "total_boost": round(r.total_boost, 2),
                "match_details": r.match_details,
            }
            for r in results
        ],
    }
    return json.dumps(data, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Match captions to creator persona for boost calculation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Persona Boost Factors:
    - Primary tone match: 1.20x
    - Secondary tone match: 1.10x
    - Emoji frequency match: 1.05x
    - Slang level match: 1.05x
    - Sentiment alignment: 1.05x
    - Maximum combined: 1.40x (capped)

No-Match Penalty:
    - If zero persona signals match: 0.95x penalty applied
    - Encourages better caption selection and persona alignment

Tone Options: playful, aggressive, sweet, dominant, bratty, seductive, direct
Emoji Frequency: heavy, moderate, light, none
Slang Levels: none, light, heavy

Examples:
    python match_persona.py --creator missalexa
    python match_persona.py --creator-id abc123 --output matches.json
    python match_persona.py --creator missalexa --caption-id 12345
        """,
    )

    parser.add_argument("--creator", "-c", help="Creator page name (e.g., missalexa)")
    parser.add_argument("--creator-id", help="Creator UUID")
    parser.add_argument("--caption-id", type=int, help="Specific caption ID to match")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of captions to process (default: 100)",
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--db", default=str(DB_PATH), help=f"Database path (default: {DB_PATH})")

    args = parser.parse_args()

    if not args.creator and not args.creator_id:
        parser.error("Must specify --creator or --creator-id")

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Load persona
        persona = get_persona_profile(conn, creator_name=args.creator, creator_id=args.creator_id)

        if not persona:
            print("Error: Creator not found", file=sys.stderr)
            sys.exit(1)

        # Match captions
        results = match_captions_to_persona(
            conn, persona, caption_id=args.caption_id, limit=args.limit
        )

        if not results:
            print("No captions found to match", file=sys.stderr)
            sys.exit(1)

        # Format output
        if args.format == "json":
            output = format_json(persona, results)
        else:
            output = format_markdown(persona, results)

        if args.output:
            Path(args.output).write_text(output)
            print(f"Results written to {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
