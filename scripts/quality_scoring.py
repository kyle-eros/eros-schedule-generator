#!/usr/bin/env python3
"""
Quality Scoring - LLM-based caption quality assessment for schedule generation.

This module implements semantic quality scoring using Claude's language model
to evaluate captions on authenticity, hook strength, CTA effectiveness, and
conversion potential.

Quality Scoring Factors (4 factors):
    - Authenticity (35%): Sounds human, not AI-generated
    - Hook Strength (25%): First line grabs attention, creates FOMO
    - CTA Effectiveness (20%): Clear call-to-action, easy to understand
    - Conversion Potential (20%): Uses urgency, scarcity, emotional appeal

Quality Score Output: 0.7x - 1.3x multiplier
    - Excellent (0.75+): Full weight, premium slots
    - Good (0.50-0.74): Normal selection
    - Acceptable (0.30-0.49): Reduced weight (0.85x)
    - Poor (<0.30): FILTERED OUT

New Weight Formula:
    weight = (perf * 0.4 + fresh * 0.2 + quality * 0.4) * persona_boost * quality_modifier

Usage:
    python quality_scoring.py --creator missalexa --limit 20
    python quality_scoring.py --creator missalexa --no-cache --format json
    python quality_scoring.py --creator missalexa --min-score 0.5 --output scores.json
"""

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
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

# Quality scoring weights
AUTHENTICITY_WEIGHT = 0.35
HOOK_WEIGHT = 0.25
CTA_WEIGHT = 0.20
CONVERSION_WEIGHT = 0.20

# Quality score thresholds
EXCELLENT_THRESHOLD = 0.75
GOOD_THRESHOLD = 0.50
ACCEPTABLE_THRESHOLD = 0.30

# Quality multiplier mapping
MULTIPLIER_MIN = 0.70
MULTIPLIER_MAX = 1.30

# Quality modifier for weight calculation
ACCEPTABLE_MODIFIER = 0.85
POOR_MODIFIER = 0.0  # Filtered out

# Cache expiration in days
DEFAULT_CACHE_DAYS = 7

# Batch size for LLM scoring
DEFAULT_BATCH_SIZE = 20


# =============================================================================
# DATABASE TABLE CREATION SQL
# =============================================================================

CREATE_QUALITY_SCORES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_quality_scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    caption_id INTEGER NOT NULL,
    creator_id TEXT NOT NULL,
    quality_score REAL NOT NULL,
    authenticity_score REAL,
    hook_score REAL,
    cta_score REAL,
    conversion_score REAL,
    true_tone TEXT,
    classification TEXT,
    reasoning TEXT,
    scored_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    UNIQUE(caption_id, creator_id)
);

CREATE INDEX IF NOT EXISTS idx_quality_caption_creator
ON llm_quality_scores(caption_id, creator_id);

CREATE INDEX IF NOT EXISTS idx_quality_expires
ON llm_quality_scores(expires_at);
"""


# =============================================================================
# LLM QUALITY ASSESSMENT PROMPT
# =============================================================================

QUALITY_ASSESSMENT_PROMPT = """## Caption Quality Assessment

You are an expert OnlyFans content strategist evaluating caption quality for PPV messages.
For each caption, rate on a scale of 0.0 to 1.0:

### Scoring Criteria

1. **Hook Strength** (0.0-1.0): Does the first sentence create curiosity/desire?
   - STRONG (0.8-1.0): "I never show this to anyone...", "Just recorded something special for you..."
   - MODERATE (0.5-0.7): "New content!", "Something hot for you"
   - WEAK (0.0-0.4): "Check this out", "New video", generic openers

2. **CTA Effectiveness** (0.0-1.0): Clear call-to-action?
   - STRONG (0.8-1.0): "Unlock now to see...", "Tip $X to receive...", specific action
   - MODERATE (0.5-0.7): Implied action, "Available now"
   - WEAK (0.0-0.4): No CTA, buried CTA, confusing instructions

3. **Authenticity** (0.0-1.0): Sounds like a real human DM?
   - RED FLAGS (low score): Formal language, perfect grammar, generic phrasing, robotic
   - GREEN FLAGS (high score): Contractions, personality, natural emoji use, casual tone

4. **Conversion Potential** (0.0-1.0): Uses urgency, scarcity, emotional appeal?
   - STRONG (0.8-1.0): Time limits, exclusivity, personal connection, desire triggers
   - MODERATE (0.5-0.7): Some emotional appeal or value proposition
   - WEAK (0.0-0.4): No urgency, no emotional hook, purely transactional

### Creator Context
- **Name:** {creator_name}
- **Primary Tone:** {primary_tone}
- **Emoji Style:** {emoji_frequency}
- **Slang Level:** {slang_level}

### Captions to Evaluate
{captions_list}

### Response Format
Return a JSON array with one object per caption:
```json
[
  {{
    "caption_id": 123,
    "hook_score": 0.75,
    "cta_score": 0.60,
    "authenticity_score": 0.85,
    "conversion_score": 0.70,
    "overall_score": 0.73,
    "true_tone": "playful",
    "reasoning": "Strong opening hook with personal touch, clear CTA but could be more urgent"
  }}
]
```

IMPORTANT:
- Return ONLY the JSON array, no additional text
- Include ALL captions provided
- Scores must be between 0.0 and 1.0
- Overall score is the weighted average: (hook*0.25 + cta*0.20 + authenticity*0.35 + conversion*0.20)
"""


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class QualityScore:
    """Quality score result for a single caption."""

    caption_id: int
    authenticity_score: float  # 0.0-1.0
    hook_score: float  # 0.0-1.0
    cta_score: float  # 0.0-1.0
    conversion_score: float  # 0.0-1.0
    overall_score: float  # Weighted average -> 0.0-1.0
    quality_multiplier: float  # Mapped to 0.7-1.3
    classification: str  # excellent, good, acceptable, poor
    reasoning: str
    true_tone: str | None  # LLM-detected tone
    scored_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=DEFAULT_CACHE_DAYS))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "caption_id": self.caption_id,
            "authenticity_score": round(self.authenticity_score, 3),
            "hook_score": round(self.hook_score, 3),
            "cta_score": round(self.cta_score, 3),
            "conversion_score": round(self.conversion_score, 3),
            "overall_score": round(self.overall_score, 3),
            "quality_multiplier": round(self.quality_multiplier, 3),
            "classification": self.classification,
            "reasoning": self.reasoning,
            "true_tone": self.true_tone,
            "scored_at": self.scored_at.isoformat() if isinstance(self.scored_at, datetime) else self.scored_at,
            "expires_at": self.expires_at.isoformat() if isinstance(self.expires_at, datetime) else self.expires_at,
        }


@dataclass
class CreatorProfile:
    """Creator profile for quality scoring context."""

    creator_id: str
    page_name: str
    primary_tone: str = "playful"
    emoji_frequency: str = "moderate"
    slang_level: str = "light"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def score_to_multiplier(overall_score: float) -> float:
    """
    Map 0-1 score to 0.7-1.3 multiplier.

    Args:
        overall_score: Quality score between 0.0 and 1.0.

    Returns:
        Quality multiplier between 0.7 and 1.3.
    """
    # Linear mapping: 0.0 -> 0.7, 1.0 -> 1.3
    return MULTIPLIER_MIN + (overall_score * (MULTIPLIER_MAX - MULTIPLIER_MIN))


def classify_score(overall_score: float) -> str:
    """
    Classify quality score into category.

    Args:
        overall_score: Quality score between 0.0 and 1.0.

    Returns:
        Classification string: 'excellent', 'good', 'acceptable', or 'poor'.
    """
    if overall_score >= EXCELLENT_THRESHOLD:
        return "excellent"
    elif overall_score >= GOOD_THRESHOLD:
        return "good"
    elif overall_score >= ACCEPTABLE_THRESHOLD:
        return "acceptable"
    else:
        return "poor"


def get_quality_modifier(classification: str) -> float:
    """
    Get weight modifier based on quality classification.

    Args:
        classification: Quality classification string.

    Returns:
        Modifier to apply to caption weight.
    """
    if classification == "excellent":
        return 1.0
    elif classification == "good":
        return 1.0
    elif classification == "acceptable":
        return ACCEPTABLE_MODIFIER
    else:  # poor
        return POOR_MODIFIER


def calculate_weighted_score(
    authenticity: float,
    hook: float,
    cta: float,
    conversion: float
) -> float:
    """
    Calculate weighted overall quality score.

    Args:
        authenticity: Authenticity score (0.0-1.0).
        hook: Hook strength score (0.0-1.0).
        cta: CTA effectiveness score (0.0-1.0).
        conversion: Conversion potential score (0.0-1.0).

    Returns:
        Weighted overall score (0.0-1.0).
    """
    return (
        authenticity * AUTHENTICITY_WEIGHT +
        hook * HOOK_WEIGHT +
        cta * CTA_WEIGHT +
        conversion * CONVERSION_WEIGHT
    )


def calculate_enhanced_weight(
    performance_score: float,
    freshness_score: float,
    quality_score: float,
    persona_boost: float,
    quality_modifier: float
) -> float:
    """
    Calculate enhanced caption weight with quality scoring.

    New formula: (perf * 0.4 + fresh * 0.2 + quality * 0.4) * persona_boost * quality_modifier

    Args:
        performance_score: Historical performance score (0-100).
        freshness_score: Caption freshness score (0-100).
        quality_score: LLM quality score (0.0-1.0).
        persona_boost: Persona match boost (1.0-1.4).
        quality_modifier: Quality-based modifier (0.0-1.0).

    Returns:
        Final enhanced weight.
    """
    # Normalize quality score to 0-100 scale for consistency
    quality_normalized = quality_score * 100

    base_weight = (
        performance_score * 0.4 +
        freshness_score * 0.2 +
        quality_normalized * 0.4
    )

    return base_weight * persona_boost * quality_modifier


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def ensure_quality_table_exists(conn: sqlite3.Connection) -> None:
    """
    Create the llm_quality_scores table if it doesn't exist.

    Args:
        conn: Database connection.
    """
    conn.executescript(CREATE_QUALITY_SCORES_TABLE_SQL)
    conn.commit()


def get_cached_scores(
    conn: sqlite3.Connection,
    caption_ids: list[int],
    creator_id: str
) -> dict[int, QualityScore]:
    """
    Retrieve cached quality scores from database.

    Args:
        conn: Database connection.
        caption_ids: List of caption IDs to look up.
        creator_id: Creator ID for the scores.

    Returns:
        Dictionary mapping caption_id to QualityScore for valid cached scores.
    """
    if not caption_ids:
        return {}

    # Ensure table exists before querying
    ensure_quality_table_exists(conn)

    placeholders = ",".join("?" * len(caption_ids))
    query = f"""
        SELECT
            caption_id,
            quality_score,
            authenticity_score,
            hook_score,
            cta_score,
            conversion_score,
            true_tone,
            classification,
            reasoning,
            scored_at,
            expires_at
        FROM llm_quality_scores
        WHERE caption_id IN ({placeholders})
          AND creator_id = ?
          AND expires_at > datetime('now')
    """

    params = list(caption_ids) + [creator_id]
    cursor = conn.execute(query, params)

    cached = {}
    for row in cursor.fetchall():
        try:
            scored_at = datetime.fromisoformat(row["scored_at"]) if row["scored_at"] else datetime.now()
            expires_at = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else datetime.now() + timedelta(days=DEFAULT_CACHE_DAYS)

            cached[row["caption_id"]] = QualityScore(
                caption_id=row["caption_id"],
                # Use explicit None check to preserve valid 0.0 scores
                authenticity_score=row["authenticity_score"] if row["authenticity_score"] is not None else 0.5,
                hook_score=row["hook_score"] if row["hook_score"] is not None else 0.5,
                cta_score=row["cta_score"] if row["cta_score"] is not None else 0.5,
                conversion_score=row["conversion_score"] if row["conversion_score"] is not None else 0.5,
                overall_score=row["quality_score"],
                quality_multiplier=score_to_multiplier(row["quality_score"]),
                classification=row["classification"] or classify_score(row["quality_score"]),
                reasoning=row["reasoning"] or "",
                true_tone=row["true_tone"],
                scored_at=scored_at,
                expires_at=expires_at,
            )
        except (ValueError, TypeError) as e:
            print(f"Warning: Failed to parse cached score for caption {row['caption_id']}: {e}", file=sys.stderr)
            continue

    return cached


def save_quality_scores(
    conn: sqlite3.Connection,
    scores: list[QualityScore],
    creator_id: str
) -> int:
    """
    Save quality scores to database cache.

    Uses INSERT OR REPLACE to handle UNIQUE constraint on (caption_id, creator_id).

    Args:
        conn: Database connection.
        scores: List of QualityScore objects to save.
        creator_id: Creator ID for the scores.

    Returns:
        Number of scores saved.
    """
    if not scores:
        return 0

    ensure_quality_table_exists(conn)

    insert_sql = """
        INSERT OR REPLACE INTO llm_quality_scores (
            caption_id, creator_id, quality_score,
            authenticity_score, hook_score, cta_score, conversion_score,
            true_tone, classification, reasoning, scored_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    saved_count = 0
    for score in scores:
        try:
            scored_at_str = score.scored_at.isoformat() if isinstance(score.scored_at, datetime) else score.scored_at
            expires_at_str = score.expires_at.isoformat() if isinstance(score.expires_at, datetime) else score.expires_at

            conn.execute(insert_sql, (
                score.caption_id,
                creator_id,
                score.overall_score,
                score.authenticity_score,
                score.hook_score,
                score.cta_score,
                score.conversion_score,
                score.true_tone,
                score.classification,
                score.reasoning,
                scored_at_str,
                expires_at_str,
            ))
            saved_count += 1
        except sqlite3.Error as e:
            print(f"Warning: Failed to save score for caption {score.caption_id}: {e}", file=sys.stderr)

    conn.commit()
    return saved_count


def cleanup_expired_scores(conn: sqlite3.Connection) -> int:
    """
    Remove expired scores from cache.

    Args:
        conn: Database connection.

    Returns:
        Number of scores deleted.
    """
    cursor = conn.execute(
        "DELETE FROM llm_quality_scores WHERE expires_at < datetime('now')"
    )
    conn.commit()
    return cursor.rowcount


# =============================================================================
# CREATOR AND CAPTION LOADING
# =============================================================================

def get_creator_profile(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None
) -> CreatorProfile | None:
    """
    Load creator profile from database.

    Args:
        conn: Database connection.
        creator_name: Creator page name (optional).
        creator_id: Creator UUID (optional).

    Returns:
        CreatorProfile or None if not found.
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

    return CreatorProfile(
        creator_id=row["creator_id"],
        page_name=row["page_name"],
        primary_tone=row["primary_tone"] or "playful",
        emoji_frequency=row["emoji_frequency"] or "moderate",
        slang_level=row["slang_level"] or "light",
    )


def load_captions_for_scoring(
    conn: sqlite3.Connection,
    creator_id: str,
    limit: int = 100,
    caption_ids: list[int] | None = None
) -> list[dict[str, Any]]:
    """
    Load captions from database for quality scoring.

    Args:
        conn: Database connection.
        creator_id: Creator UUID.
        limit: Maximum number of captions to load.
        caption_ids: Optional specific caption IDs to load.

    Returns:
        List of caption dictionaries.
    """
    if caption_ids:
        placeholders = ",".join("?" * len(caption_ids))
        query = f"""
            SELECT
                caption_id,
                caption_text,
                caption_type,
                tone,
                performance_score,
                freshness_score
            FROM caption_bank
            WHERE caption_id IN ({placeholders})
              AND is_active = 1
        """
        cursor = conn.execute(query, caption_ids)
    else:
        query = """
            SELECT
                caption_id,
                caption_text,
                caption_type,
                tone,
                performance_score,
                freshness_score
            FROM caption_bank
            WHERE is_active = 1
              AND (creator_id = ? OR is_universal = 1)
            ORDER BY performance_score DESC, freshness_score DESC
            LIMIT ?
        """
        cursor = conn.execute(query, (creator_id, limit))

    captions = []
    for row in cursor.fetchall():
        captions.append({
            "caption_id": row["caption_id"],
            "caption_text": row["caption_text"],
            "caption_type": row["caption_type"],
            "tone": row["tone"],
            "performance_score": row["performance_score"] or 50.0,
            "freshness_score": row["freshness_score"] or 100.0,
        })

    return captions


# =============================================================================
# LLM SCORING (MOCK FOR NON-LLM ENVIRONMENTS)
# =============================================================================

def build_llm_prompt(
    captions: list[dict[str, Any]],
    profile: CreatorProfile
) -> str:
    """
    Build the LLM prompt for quality assessment.

    Args:
        captions: List of caption dictionaries.
        profile: Creator profile for context.

    Returns:
        Formatted prompt string.
    """
    # Format captions list
    captions_text = []
    for cap in captions:
        text_preview = cap["caption_text"][:300] if len(cap["caption_text"]) > 300 else cap["caption_text"]
        captions_text.append(f"- **ID {cap['caption_id']}**: {text_preview}")

    captions_list = "\n".join(captions_text)

    return QUALITY_ASSESSMENT_PROMPT.format(
        creator_name=profile.page_name,
        primary_tone=profile.primary_tone,
        emoji_frequency=profile.emoji_frequency,
        slang_level=profile.slang_level,
        captions_list=captions_list,
    )


def parse_llm_response(response_text: str) -> list[dict[str, Any]]:
    """
    Parse LLM JSON response into score dictionaries.

    Args:
        response_text: Raw LLM response text.

    Returns:
        List of score dictionaries.

    Raises:
        ValueError: If response cannot be parsed.
    """
    # Try to extract JSON from response
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end].strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "results" in data:
            return data["results"]
        else:
            raise ValueError("Expected JSON array or object with 'results' key")
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}")


def create_quality_score_from_llm(result: dict[str, Any], cache_days: int = DEFAULT_CACHE_DAYS) -> QualityScore:
    """
    Create QualityScore from parsed LLM result.

    Args:
        result: Dictionary with LLM scores.
        cache_days: Number of days until score expires.

    Returns:
        QualityScore object.
    """
    # Extract scores with defaults
    authenticity = float(result.get("authenticity_score", 0.5))
    hook = float(result.get("hook_score", 0.5))
    cta = float(result.get("cta_score", 0.5))
    conversion = float(result.get("conversion_score", 0.5))

    # Clamp scores to valid range
    authenticity = max(0.0, min(1.0, authenticity))
    hook = max(0.0, min(1.0, hook))
    cta = max(0.0, min(1.0, cta))
    conversion = max(0.0, min(1.0, conversion))

    # Calculate overall if not provided
    if "overall_score" in result:
        overall = float(result["overall_score"])
        overall = max(0.0, min(1.0, overall))
    else:
        overall = calculate_weighted_score(authenticity, hook, cta, conversion)

    now = datetime.now()

    return QualityScore(
        caption_id=int(result["caption_id"]),
        authenticity_score=authenticity,
        hook_score=hook,
        cta_score=cta,
        conversion_score=conversion,
        overall_score=overall,
        quality_multiplier=score_to_multiplier(overall),
        classification=classify_score(overall),
        reasoning=result.get("reasoning", ""),
        true_tone=result.get("true_tone"),
        scored_at=now,
        expires_at=now + timedelta(days=cache_days),
    )


def score_captions_heuristic(
    captions: list[dict[str, Any]],
    profile: CreatorProfile,
    cache_days: int = DEFAULT_CACHE_DAYS
) -> list[QualityScore]:
    """
    Score captions using heuristic rules (fallback when LLM unavailable).

    This provides reasonable quality estimates based on text patterns.

    Args:
        captions: List of caption dictionaries.
        profile: Creator profile for context.
        cache_days: Number of days until scores expire.

    Returns:
        List of QualityScore objects.
    """
    scores = []
    now = datetime.now()

    # Hook patterns that indicate strong openings
    strong_hooks = [
        "never show", "just recorded", "only for you", "secret", "private",
        "can't believe", "finally", "waited so long", "been thinking",
        "just made", "wanted to share", "special", "exclusive"
    ]

    # CTA patterns
    strong_cta = [
        "unlock", "tip", "send", "get it", "claim", "grab", "open",
        "see it", "watch", "available now", "dm me"
    ]

    # Urgency/scarcity patterns
    urgency_words = [
        "only", "limited", "today", "now", "hurry", "last chance",
        "running out", "few left", "before", "ends", "expires"
    ]

    # Authenticity indicators (informal language)
    authenticity_markers = [
        "hehe", "lol", "omg", "'m", "'re", "'ve", "'ll", "'t",
        "gonna", "wanna", "kinda", "ya", "babe", "baby", "hun"
    ]

    for cap in captions:
        text_lower = cap["caption_text"].lower()
        text = cap["caption_text"]

        # Hook score
        hook = 0.4  # Base
        for pattern in strong_hooks:
            if pattern in text_lower:
                hook = min(hook + 0.15, 0.95)
        # Bonus for question or ellipsis opener
        if text_lower.startswith(("what if", "do you", "ever wonder", "want to")):
            hook += 0.1
        if "..." in text[:50]:
            hook += 0.05

        # CTA score
        cta = 0.3  # Base
        for pattern in strong_cta:
            if pattern in text_lower:
                cta = min(cta + 0.2, 0.95)

        # Authenticity score
        authenticity = 0.5  # Base
        for marker in authenticity_markers:
            if marker in text_lower:
                authenticity = min(authenticity + 0.08, 0.95)
        # Penalty for overly formal language
        if text[0].isupper() and text[-1] == "." and "!" not in text:
            authenticity -= 0.1
        # Emoji presence
        if any(ord(c) > 127 for c in text):  # Simple emoji check
            authenticity += 0.1

        # Conversion score
        conversion = 0.4  # Base
        for word in urgency_words:
            if word in text_lower:
                conversion = min(conversion + 0.12, 0.95)
        # Personal pronouns
        if " you " in text_lower or "your " in text_lower:
            conversion += 0.1

        # Clamp all scores
        hook = max(0.0, min(1.0, hook))
        cta = max(0.0, min(1.0, cta))
        authenticity = max(0.0, min(1.0, authenticity))
        conversion = max(0.0, min(1.0, conversion))

        overall = calculate_weighted_score(authenticity, hook, cta, conversion)

        scores.append(QualityScore(
            caption_id=cap["caption_id"],
            authenticity_score=round(authenticity, 3),
            hook_score=round(hook, 3),
            cta_score=round(cta, 3),
            conversion_score=round(conversion, 3),
            overall_score=round(overall, 3),
            quality_multiplier=score_to_multiplier(overall),
            classification=classify_score(overall),
            reasoning="Heuristic scoring (LLM unavailable)",
            true_tone=cap.get("tone"),
            scored_at=now,
            expires_at=now + timedelta(days=cache_days),
        ))

    return scores


# =============================================================================
# QUALITY SCORER CLASS
# =============================================================================

class QualityScorer:
    """
    LLM-based caption quality scorer with caching.

    This class manages quality scoring for captions, using cached scores
    when available and falling back to heuristic scoring when LLM is unavailable.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        cache_days: int = DEFAULT_CACHE_DAYS,
        use_llm: bool = False
    ):
        """
        Initialize the QualityScorer.

        Args:
            conn: Database connection for caching.
            cache_days: Number of days to cache scores.
            use_llm: Whether to use LLM for scoring (requires external integration).
        """
        self.conn = conn
        self.cache_days = cache_days
        self.use_llm = use_llm

        # Ensure cache table exists
        ensure_quality_table_exists(conn)

    def score_caption_batch(
        self,
        captions: list[dict[str, Any]],
        creator_profile: CreatorProfile,
        use_cache: bool = True
    ) -> dict[int, QualityScore]:
        """
        Score a batch of captions using LLM or heuristics, with caching.

        Args:
            captions: List of caption dictionaries with caption_id and caption_text.
            creator_profile: Creator profile for context.
            use_cache: Whether to use cached scores.

        Returns:
            Dictionary mapping caption_id to QualityScore.
        """
        if not captions:
            return {}

        caption_ids = [c["caption_id"] for c in captions]
        results: dict[int, QualityScore] = {}

        # Check cache first
        if use_cache:
            cached = get_cached_scores(self.conn, caption_ids, creator_profile.creator_id)
            results.update(cached)

            # Filter out cached captions
            captions_to_score = [c for c in captions if c["caption_id"] not in cached]
        else:
            captions_to_score = captions

        if not captions_to_score:
            return results

        # Score remaining captions
        if self.use_llm:
            # Build prompt for LLM
            prompt = build_llm_prompt(captions_to_score, creator_profile)
            # TODO: Integrate with actual LLM API
            # For now, fall back to heuristic scoring
            print("Note: LLM scoring not yet integrated, using heuristic fallback", file=sys.stderr)
            new_scores = score_captions_heuristic(
                captions_to_score, creator_profile, self.cache_days
            )
        else:
            new_scores = score_captions_heuristic(
                captions_to_score, creator_profile, self.cache_days
            )

        # Save new scores to cache
        saved = save_quality_scores(self.conn, new_scores, creator_profile.creator_id)
        if saved > 0:
            print(f"Cached {saved} new quality scores", file=sys.stderr)

        # Add to results
        for score in new_scores:
            results[score.caption_id] = score

        return results

    def filter_by_quality(
        self,
        captions: list[dict[str, Any]],
        scores: dict[int, QualityScore],
        min_score: float = ACCEPTABLE_THRESHOLD
    ) -> list[dict[str, Any]]:
        """
        Filter captions below quality threshold.

        Args:
            captions: List of caption dictionaries.
            scores: Dictionary mapping caption_id to QualityScore.
            min_score: Minimum overall quality score (default 0.30).

        Returns:
            List of captions with quality score >= min_score.
        """
        filtered = []
        for cap in captions:
            caption_id = cap["caption_id"]
            if caption_id in scores:
                if scores[caption_id].overall_score >= min_score:
                    filtered.append(cap)
            else:
                # No score available, include by default
                filtered.append(cap)

        return filtered

    def get_scores_summary(
        self,
        scores: dict[int, QualityScore]
    ) -> dict[str, Any]:
        """
        Generate summary statistics for quality scores.

        Args:
            scores: Dictionary of quality scores.

        Returns:
            Summary statistics dictionary.
        """
        if not scores:
            return {
                "total": 0,
                "excellent": 0,
                "good": 0,
                "acceptable": 0,
                "poor": 0,
                "avg_score": 0.0,
                "avg_multiplier": 1.0,
            }

        score_list = list(scores.values())
        classifications = [s.classification for s in score_list]

        return {
            "total": len(score_list),
            "excellent": classifications.count("excellent"),
            "good": classifications.count("good"),
            "acceptable": classifications.count("acceptable"),
            "poor": classifications.count("poor"),
            "avg_score": round(sum(s.overall_score for s in score_list) / len(score_list), 3),
            "avg_multiplier": round(sum(s.quality_multiplier for s in score_list) / len(score_list), 3),
        }


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def format_markdown(
    profile: CreatorProfile,
    scores: dict[int, QualityScore],
    captions: list[dict[str, Any]]
) -> str:
    """
    Format quality scores as Markdown report.

    Args:
        profile: Creator profile.
        scores: Dictionary of quality scores.
        captions: List of caption dictionaries.

    Returns:
        Formatted Markdown string.
    """
    score_list = sorted(scores.values(), key=lambda s: s.overall_score, reverse=True)

    lines = [
        f"# Quality Scores: {profile.page_name}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Scored | {len(score_list)} |",
        f"| Excellent (>= 0.75) | {sum(1 for s in score_list if s.classification == 'excellent')} |",
        f"| Good (0.50-0.74) | {sum(1 for s in score_list if s.classification == 'good')} |",
        f"| Acceptable (0.30-0.49) | {sum(1 for s in score_list if s.classification == 'acceptable')} |",
        f"| Poor (< 0.30) | {sum(1 for s in score_list if s.classification == 'poor')} |",
        "",
    ]

    if score_list:
        avg_score = sum(s.overall_score for s in score_list) / len(score_list)
        avg_mult = sum(s.quality_multiplier for s in score_list) / len(score_list)
        lines.extend([
            f"**Average Score:** {avg_score:.3f}",
            f"**Average Multiplier:** {avg_mult:.2f}x",
            "",
        ])

    lines.extend([
        "## Detailed Scores",
        "",
        "| ID | Class | Score | Mult | Auth | Hook | CTA | Conv | Tone |",
        "|----|-------|-------|------|------|------|-----|------|------|",
    ])

    for s in score_list[:50]:  # Limit display
        lines.append(
            f"| {s.caption_id} | {s.classification} | {s.overall_score:.2f} | "
            f"{s.quality_multiplier:.2f}x | {s.authenticity_score:.2f} | "
            f"{s.hook_score:.2f} | {s.cta_score:.2f} | {s.conversion_score:.2f} | "
            f"{s.true_tone or '-'} |"
        )

    if len(score_list) > 50:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | ... | ({len(score_list) - 50} more) |")

    lines.append("")
    return "\n".join(lines)


def format_json(
    profile: CreatorProfile,
    scores: dict[int, QualityScore],
    captions: list[dict[str, Any]]
) -> str:
    """
    Format quality scores as JSON.

    Args:
        profile: Creator profile.
        scores: Dictionary of quality scores.
        captions: List of caption dictionaries.

    Returns:
        JSON string.
    """
    score_list = sorted(scores.values(), key=lambda s: s.overall_score, reverse=True)

    data = {
        "creator": {
            "creator_id": profile.creator_id,
            "page_name": profile.page_name,
            "primary_tone": profile.primary_tone,
        },
        "summary": {
            "total_scored": len(score_list),
            "excellent": sum(1 for s in score_list if s.classification == "excellent"),
            "good": sum(1 for s in score_list if s.classification == "good"),
            "acceptable": sum(1 for s in score_list if s.classification == "acceptable"),
            "poor": sum(1 for s in score_list if s.classification == "poor"),
            "avg_score": round(sum(s.overall_score for s in score_list) / len(score_list), 3) if score_list else 0,
            "avg_multiplier": round(sum(s.quality_multiplier for s in score_list) / len(score_list), 3) if score_list else 1.0,
        },
        "scores": [s.to_dict() for s in score_list],
    }

    return json.dumps(data, indent=2)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Score caption quality using LLM-based assessment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Quality Scoring Factors:
    - Authenticity (35%): Sounds human, not AI-generated
    - Hook Strength (25%): First line grabs attention
    - CTA Effectiveness (20%): Clear call-to-action
    - Conversion Potential (20%): Urgency, scarcity, emotion

Score Classifications:
    - Excellent (>= 0.75): Full weight, premium slots (1.15-1.30x)
    - Good (0.50-0.74): Normal selection (0.95-1.14x)
    - Acceptable (0.30-0.49): Reduced weight (0.85x modifier)
    - Poor (< 0.30): FILTERED OUT

Examples:
    python quality_scoring.py --creator missalexa --limit 20
    python quality_scoring.py --creator missalexa --no-cache --format json
    python quality_scoring.py --creator missalexa --min-score 0.5
        """
    )

    parser.add_argument(
        "--creator", "-c",
        help="Creator page name (e.g., missalexa)"
    )
    parser.add_argument(
        "--creator-id",
        help="Creator UUID"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Maximum captions to score (default: {DEFAULT_BATCH_SIZE})"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=ACCEPTABLE_THRESHOLD,
        help=f"Minimum quality score to include (default: {ACCEPTABLE_THRESHOLD})"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache, force fresh scoring"
    )
    parser.add_argument(
        "--cleanup-cache",
        action="store_true",
        help="Remove expired scores from cache and exit"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help=f"Database path (default: {DB_PATH})"
    )

    args = parser.parse_args()

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Handle cache cleanup
        if args.cleanup_cache:
            ensure_quality_table_exists(conn)
            deleted = cleanup_expired_scores(conn)
            print(f"Cleaned up {deleted} expired quality scores")
            sys.exit(0)

        # Require creator for scoring
        if not args.creator and not args.creator_id:
            parser.error("Must specify --creator or --creator-id (or use --cleanup-cache)")

        # Load creator profile
        profile = get_creator_profile(
            conn,
            creator_name=args.creator,
            creator_id=args.creator_id
        )

        if not profile:
            print("Error: Creator not found", file=sys.stderr)
            sys.exit(1)

        # Load captions
        captions = load_captions_for_scoring(conn, profile.creator_id, args.limit)

        if not captions:
            print("No captions found to score", file=sys.stderr)
            sys.exit(1)

        # Initialize scorer
        scorer = QualityScorer(conn, use_llm=False)

        # Score captions
        scores = scorer.score_caption_batch(
            captions,
            profile,
            use_cache=not args.no_cache
        )

        # Filter by minimum score
        filtered = scorer.filter_by_quality(captions, scores, args.min_score)

        # Report filtering
        if len(filtered) < len(captions):
            print(
                f"Filtered out {len(captions) - len(filtered)} captions below "
                f"quality threshold ({args.min_score})",
                file=sys.stderr
            )

        # Format output
        if args.format == "json":
            output = format_json(profile, scores, captions)
        else:
            output = format_markdown(profile, scores, captions)

        if args.output:
            Path(args.output).write_text(output)
            print(f"Results written to {args.output}")
        else:
            print(output)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
