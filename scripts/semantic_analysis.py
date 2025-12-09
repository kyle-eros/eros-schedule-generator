#!/usr/bin/env python3
"""
Semantic Analysis - Identify captions needing Claude LLM analysis.

This script identifies captions that need semantic analysis by an LLM
(Claude) and prepares structured output for processing.

Captions flagged for LLM analysis when:
    - No stored tone/slang in database AND pattern detection has low confidence
    - Very low pattern confidence (<0.5)
    - Multiple competing tone signals
    - High-value captions (performance >= 75) with low persona match

Output Formats:
    - json: Machine-readable JSON for programmatic processing
    - prompt: Structured markdown prompt for Claude to analyze directly

Usage:
    python semantic_analysis.py --creator missalexa --format json
    python semantic_analysis.py --creator missalexa --format prompt
    python semantic_analysis.py --creator missalexa --output analysis.json
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Import persona matching functions from match_persona.py
from match_persona import (
    PersonaProfile,
    calculate_sentiment,
    detect_slang_level_from_text,
    detect_tone_from_text,
    get_persona_profile,
)

# Path resolution for database
SCRIPT_DIR = Path(__file__).parent

from database import DB_PATH  # noqa: E402

# Analysis thresholds
LOW_CONFIDENCE_THRESHOLD = 0.5
VERY_LOW_CONFIDENCE_THRESHOLD = 0.3
HIGH_VALUE_PERFORMANCE_THRESHOLD = 75
LOW_PERSONA_MATCH_THRESHOLD = 1.05
MAX_CAPTIONS_FOR_PROMPT = 30
MAX_CAPTION_LENGTH = 600


@dataclass
class CaptionForAnalysis:
    """Caption data prepared for LLM semantic analysis."""

    caption_id: int
    caption_text: str
    pattern_detected_tone: str | None
    pattern_detected_slang: str | None
    pattern_sentiment: float
    pattern_confidence: float  # 0.0-1.0
    pattern_boost: float
    needs_llm_analysis: bool
    analysis_reason: str
    creator_primary_tone: str
    creator_emoji_freq: str
    creator_slang_level: str


@dataclass
class AnalysisBatch:
    """Batch of captions prepared for LLM analysis."""

    creator_id: str
    creator_name: str
    creator_display_name: str
    persona_profile: dict[str, Any]
    performance_summary: dict[str, Any]
    total_captions_evaluated: int
    captions_needing_analysis: int
    captions: list[CaptionForAnalysis] = field(default_factory=list)


def calculate_pattern_confidence(
    text: str,
    tone_scores: dict[str, int],
    detected_tone: str | None,
    has_stored_tone: bool,
    has_stored_slang: bool,
) -> tuple[float, str]:
    """
    Calculate confidence level of pattern-based tone detection.

    Confidence levels:
        - 0.9: One dominant tone with strong signal (3+ keyword matches)
        - 0.7: Single clear signal (1-2 keyword matches)
        - 0.5: Weak signal or no stored attributes
        - 0.3: Multiple competing tones or ambiguous

    Args:
        text: Caption text
        tone_scores: Dictionary of tone -> keyword match count
        detected_tone: The detected tone (if any)
        has_stored_tone: Whether database has tone attribute
        has_stored_slang: Whether database has slang attribute

    Returns:
        Tuple of (confidence_score, reason)
    """
    if not text:
        return 0.0, "empty_caption"

    if not tone_scores:
        # No keywords matched at all
        if not has_stored_tone and not has_stored_slang:
            return 0.3, "no_pattern_match_no_stored_attrs"
        return 0.5, "no_pattern_match_has_stored_attrs"

    # Check for competing signals
    sorted_scores = sorted(tone_scores.values(), reverse=True)
    if len(sorted_scores) >= 2:
        top_score = sorted_scores[0]
        second_score = sorted_scores[1]

        # If top two tones are close, confidence is lower
        if top_score > 0 and second_score / top_score > 0.6:
            return 0.3, "competing_tone_signals"

    # Check signal strength
    if detected_tone and tone_scores.get(detected_tone, 0) >= 3:
        # Strong signal: 3+ keyword matches for detected tone
        return 0.9, "dominant_tone_strong_signal"
    elif detected_tone and tone_scores.get(detected_tone, 0) >= 1:
        # Clear but not overwhelming signal
        return 0.7, "single_clear_signal"
    else:
        # Weak signal
        if not has_stored_tone and not has_stored_slang:
            return 0.4, "weak_signal_no_stored_attrs"
        return 0.5, "weak_signal_has_stored_attrs"


def calculate_persona_boost_simple(
    detected_tone: str | None, detected_slang: str | None, persona: PersonaProfile
) -> float:
    """
    Calculate a simple persona boost for filtering purposes.

    This is a simplified version used to identify low-match captions.
    """
    boost = 1.0

    if detected_tone and persona.primary_tone:
        if detected_tone.lower() == persona.primary_tone.lower():
            boost *= 1.20

    if detected_slang and persona.slang_level:
        if detected_slang.lower() == persona.slang_level.lower():
            boost *= 1.05

    return min(boost, 1.40)


def should_flag_for_llm_analysis(
    caption_id: int,
    caption_text: str,
    stored_tone: str | None,
    stored_slang: str | None,
    performance_score: float,
    pattern_confidence: float,
    pattern_boost: float,
    confidence_reason: str,
) -> tuple[bool, str]:
    """
    Determine if a caption should be flagged for LLM analysis.

    Criteria:
        1. No stored tone/slang AND low pattern confidence (<0.7)
        2. Very low pattern confidence (<0.5)
        3. Multiple competing tone signals
        4. High-value caption (perf >= 75) with low persona match (<1.05)

    Args:
        caption_id: Caption ID
        caption_text: Caption text
        stored_tone: Stored tone from database (may be None)
        stored_slang: Stored slang level from database (may be None)
        performance_score: Caption performance score
        pattern_confidence: Calculated pattern confidence
        pattern_boost: Calculated persona boost
        confidence_reason: Reason for confidence level

    Returns:
        Tuple of (should_analyze, reason)
    """
    reasons = []

    # Criterion 1: No stored attributes AND low pattern confidence
    if not stored_tone and not stored_slang and pattern_confidence < 0.7:
        reasons.append("no_stored_attrs_low_confidence")

    # Criterion 2: Very low pattern confidence
    if pattern_confidence < VERY_LOW_CONFIDENCE_THRESHOLD:
        reasons.append("very_low_confidence")

    # Criterion 3: Competing tone signals
    if confidence_reason == "competing_tone_signals":
        reasons.append("competing_tones")

    # Criterion 4: High-value caption with low persona match
    if performance_score >= HIGH_VALUE_PERFORMANCE_THRESHOLD:
        if pattern_boost < LOW_PERSONA_MATCH_THRESHOLD:
            reasons.append("high_value_low_match")

    if reasons:
        return True, "; ".join(reasons)

    return False, ""


def load_captions_for_analysis(
    conn: sqlite3.Connection, creator_id: str, persona: PersonaProfile, limit: int = 500
) -> tuple[list[CaptionForAnalysis], dict[str, Any]]:
    """
    Load captions and evaluate them for LLM analysis need.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator's persona profile
        limit: Maximum captions to evaluate

    Returns:
        Tuple of (captions_for_analysis, performance_summary)
    """
    query = """
        SELECT
            cb.caption_id,
            cb.caption_text,
            cb.tone,
            cb.slang_level,
            cb.performance_score,
            cb.freshness_score
        FROM caption_bank cb
        WHERE cb.is_active = 1
          AND (cb.creator_id = ? OR cb.is_universal = 1)
        ORDER BY cb.performance_score DESC
        LIMIT ?
    """

    cursor = conn.execute(query, (creator_id, limit))
    rows = cursor.fetchall()

    captions = []
    total_evaluated = 0
    needs_analysis_count = 0
    high_confidence_count = 0
    low_confidence_count = 0
    high_value_count = 0

    for row in rows:
        total_evaluated += 1

        caption_text = row["caption_text"] or ""
        stored_tone = row["tone"]
        stored_slang = row["slang_level"]
        performance_score = row["performance_score"] or 50.0

        if performance_score >= HIGH_VALUE_PERFORMANCE_THRESHOLD:
            high_value_count += 1

        # Run pattern detection
        detected_tone, tone_scores = detect_tone_from_text(caption_text)
        detected_slang = detect_slang_level_from_text(caption_text)
        sentiment = calculate_sentiment(caption_text)

        # Calculate pattern confidence
        pattern_confidence, confidence_reason = calculate_pattern_confidence(
            caption_text,
            tone_scores,
            detected_tone,
            has_stored_tone=bool(stored_tone),
            has_stored_slang=bool(stored_slang),
        )

        if pattern_confidence >= 0.7:
            high_confidence_count += 1
        else:
            low_confidence_count += 1

        # Calculate simple persona boost
        pattern_boost = calculate_persona_boost_simple(
            detected_tone or stored_tone, detected_slang or stored_slang, persona
        )

        # Determine if LLM analysis needed
        needs_analysis, analysis_reason = should_flag_for_llm_analysis(
            caption_id=row["caption_id"],
            caption_text=caption_text,
            stored_tone=stored_tone,
            stored_slang=stored_slang,
            performance_score=performance_score,
            pattern_confidence=pattern_confidence,
            pattern_boost=pattern_boost,
            confidence_reason=confidence_reason,
        )

        if needs_analysis:
            needs_analysis_count += 1

        captions.append(
            CaptionForAnalysis(
                caption_id=row["caption_id"],
                caption_text=caption_text[:MAX_CAPTION_LENGTH]
                if len(caption_text) > MAX_CAPTION_LENGTH
                else caption_text,
                pattern_detected_tone=detected_tone,
                pattern_detected_slang=detected_slang,
                pattern_sentiment=round(sentiment, 2),
                pattern_confidence=round(pattern_confidence, 2),
                pattern_boost=round(pattern_boost, 2),
                needs_llm_analysis=needs_analysis,
                analysis_reason=analysis_reason,
                creator_primary_tone=persona.primary_tone,
                creator_emoji_freq=persona.emoji_frequency,
                creator_slang_level=persona.slang_level,
            )
        )

    performance_summary = {
        "total_evaluated": total_evaluated,
        "needs_analysis": needs_analysis_count,
        "high_confidence": high_confidence_count,
        "low_confidence": low_confidence_count,
        "high_value_captions": high_value_count,
        "analysis_rate_pct": round(needs_analysis_count / total_evaluated * 100, 1)
        if total_evaluated > 0
        else 0,
    }

    return captions, performance_summary


def get_creator_display_name(conn: sqlite3.Connection, creator_id: str) -> str:
    """Get creator's display name from database."""
    cursor = conn.execute(
        "SELECT display_name, page_name FROM creators WHERE creator_id = ?", (creator_id,)
    )
    row = cursor.fetchone()
    if row:
        return row["display_name"] or row["page_name"]
    return "Unknown"


def build_analysis_batch(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None,
    limit: int = 500,
) -> AnalysisBatch | None:
    """
    Build a batch of captions for LLM analysis.

    Args:
        conn: Database connection
        creator_name: Creator page name (optional)
        creator_id: Creator UUID (optional)
        limit: Maximum captions to evaluate

    Returns:
        AnalysisBatch or None if creator not found
    """
    # Load persona profile
    persona = get_persona_profile(conn, creator_name=creator_name, creator_id=creator_id)
    if not persona:
        return None

    # Get display name
    display_name = get_creator_display_name(conn, persona.creator_id)

    # Load and analyze captions
    captions, performance_summary = load_captions_for_analysis(
        conn, persona.creator_id, persona, limit
    )

    # Filter to only those needing analysis
    captions_needing_analysis = [c for c in captions if c.needs_llm_analysis]

    return AnalysisBatch(
        creator_id=persona.creator_id,
        creator_name=persona.page_name,
        creator_display_name=display_name,
        persona_profile={
            "primary_tone": persona.primary_tone,
            "secondary_tone": persona.secondary_tone,
            "emoji_frequency": persona.emoji_frequency,
            "slang_level": persona.slang_level,
            "avg_sentiment": persona.avg_sentiment,
            "favorite_emojis": persona.favorite_emojis[:5] if persona.favorite_emojis else [],
        },
        performance_summary=performance_summary,
        total_captions_evaluated=performance_summary["total_evaluated"],
        captions_needing_analysis=performance_summary["needs_analysis"],
        captions=captions_needing_analysis,
    )


def format_as_json(batch: AnalysisBatch) -> str:
    """Format analysis batch as JSON."""
    data = {
        "creator_id": batch.creator_id,
        "creator_name": batch.creator_name,
        "creator_display_name": batch.creator_display_name,
        "persona_profile": batch.persona_profile,
        "performance_summary": batch.performance_summary,
        "total_captions_evaluated": batch.total_captions_evaluated,
        "captions_needing_analysis": batch.captions_needing_analysis,
        "captions": [asdict(c) for c in batch.captions],
    }
    return json.dumps(data, indent=2)


def format_as_prompt(batch: AnalysisBatch) -> str:
    """
    Format analysis batch as a structured prompt for Claude.

    Creates a markdown-formatted prompt with:
        - Creator profile information
        - Analysis summary
        - List of captions needing analysis (limited to MAX_CAPTIONS_FOR_PROMPT)
        - Analysis instructions
        - Response format specification
        - Tone detection guidelines
    """
    lines = [
        "# Semantic Analysis Request for EROS Caption Bank",
        "",
        "## Creator Profile",
        "",
        f"**Creator**: {batch.creator_display_name} (@{batch.creator_name})",
        f"**Creator ID**: {batch.creator_id}",
        "",
        "### Persona Attributes",
        "",
        "| Attribute | Value |",
        "|-----------|-------|",
        f"| Primary Tone | {batch.persona_profile['primary_tone']} |",
        f"| Secondary Tone | {batch.persona_profile.get('secondary_tone', 'N/A') or 'N/A'} |",
        f"| Emoji Frequency | {batch.persona_profile['emoji_frequency']} |",
        f"| Slang Level | {batch.persona_profile['slang_level']} |",
        f"| Avg Sentiment | {batch.persona_profile['avg_sentiment']:.2f} |",
        "",
    ]

    if batch.persona_profile.get("favorite_emojis"):
        emojis = " ".join(batch.persona_profile["favorite_emojis"])
        lines.append(f"**Favorite Emojis**: {emojis}")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Analysis Summary",
            "",
            f"- **Total Captions Evaluated**: {batch.total_captions_evaluated}",
            f"- **Captions Needing Analysis**: {batch.captions_needing_analysis}",
            f"- **Analysis Rate**: {batch.performance_summary['analysis_rate_pct']:.1f}%",
            f"- **High Confidence Detections**: {batch.performance_summary['high_confidence']}",
            f"- **Low Confidence Detections**: {batch.performance_summary['low_confidence']}",
            f"- **High-Value Captions (perf >= 75)**: {batch.performance_summary['high_value_captions']}",
            "",
            "---",
            "",
            "## Captions Requiring Semantic Analysis",
            "",
        ]
    )

    # Limit captions for prompt
    captions_to_show = batch.captions[:MAX_CAPTIONS_FOR_PROMPT]
    remaining = len(batch.captions) - MAX_CAPTIONS_FOR_PROMPT

    for i, caption in enumerate(captions_to_show, 1):
        truncated = caption.caption_text
        if len(truncated) > 300:
            truncated = truncated[:300] + "..."

        lines.extend(
            [
                f"### Caption #{i} (ID: {caption.caption_id})",
                "",
                f'**Text**: "{truncated}"',
                "",
                f"- Pattern Detected Tone: {caption.pattern_detected_tone or 'None'}",
                f"- Pattern Detected Slang: {caption.pattern_detected_slang or 'None'}",
                f"- Pattern Sentiment: {caption.pattern_sentiment}",
                f"- Pattern Confidence: {caption.pattern_confidence}",
                f"- Pattern Boost: {caption.pattern_boost}x",
                f"- **Analysis Reason**: {caption.analysis_reason}",
                "",
            ]
        )

    if remaining > 0:
        lines.extend(
            [
                f"*... and {remaining} more captions requiring analysis (truncated for context window)*",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "## Analysis Instructions",
            "",
            "For each caption above, please determine:",
            "",
            "1. **True Tone**: The actual tone of the caption based on semantic meaning, not just keywords.",
            "   - Options: playful, aggressive, sweet, dominant, bratty, seductive, direct",
            "",
            "2. **Persona Match Score** (0.0-1.0): How well does this caption match the creator's persona?",
            "   - 1.0 = Perfect match for this creator's voice",
            "   - 0.7-0.9 = Good match, minor deviations",
            "   - 0.4-0.6 = Moderate match, could work but not ideal",
            "   - 0.0-0.3 = Poor match, doesn't fit this creator",
            "",
            "3. **Confidence** (0.0-1.0): How confident are you in this assessment?",
            "   - 1.0 = Completely certain",
            "   - 0.7-0.9 = High confidence",
            "   - 0.4-0.6 = Moderate confidence",
            "   - 0.0-0.3 = Low confidence, ambiguous",
            "",
            "4. **Notes**: Brief explanation of your reasoning (1-2 sentences)",
            "",
            "---",
            "",
            "## Response Format",
            "",
            "Please respond with a JSON array in this exact format:",
            "",
            "```json",
            "[",
            "  {",
            '    "caption_id": 12345,',
            '    "true_tone": "playful",',
            '    "persona_match_score": 0.85,',
            '    "confidence": 0.90,',
            '    "notes": "Clear playful tone with teasing language that matches creator style."',
            "  },",
            "  ...",
            "]",
            "```",
            "",
            "---",
            "",
            "## Tone Detection Guidelines",
            "",
            "| Tone | Characteristics | Keywords/Signals |",
            "|------|-----------------|------------------|",
            "| playful | Teasing, fun, lighthearted | hehe, lol, tease, wink, surprise |",
            "| aggressive | Commanding, urgent, demanding | now, obey, demand, must, immediately |",
            "| sweet | Affectionate, warm, caring | baby, honey, love, xoxo, miss you |",
            "| dominant | Controlling, authoritative | control, power, permission, own, rule |",
            "| bratty | Entitled, pouty, demanding but cute | whatever, ugh, deserve, spoil, gimme |",
            "| seductive | Sensual, alluring, intimate | tempt, desire, crave, fantasy, whisper |",
            "| direct | Transactional, clear offers | exclusive, deal, unlock, sale, limited |",
            "",
            "---",
            "",
            "## Sarcasm and Subtext Detection Tips",
            "",
            "- **Sarcasm**: Look for mismatches between apparent keywords and context",
            '  - "Oh sure, I\'ll just give this away for free" = NOT sweet, likely bratty/sarcastic',
            '  - "Whatever you say, boss" = Could be bratty, not necessarily dominant',
            "",
            "- **Emojis can shift tone**: Same text with different emojis = different tone",
            '  - "Do it now" = aggressive',
            '  - "Do it now hehe" = playful/bratty',
            "",
            "- **Context clues**: Consider the overall message intent",
            "  - Sales/offer language usually = direct, even if dressed up",
            "  - Genuine compliments = sweet",
            "  - Teasing about paying = bratty or playful",
            "",
            "---",
            "",
            "## Anti-AI Humanization Guidelines",
            "",
            "When evaluating captions, also consider whether they sound authentically human.",
            "Captions that feel robotic or AI-generated should receive LOWER persona match scores.",
            "",
            "**Red Flags for AI-Sounding Content:**",
            "",
            '- Overly formal or stiff language ("I would like to offer you...")',
            "- Perfect grammar with no personality quirks or casual mistakes",
            '- Generic phrases that could apply to anyone ("This exclusive content...")',
            "- Lack of specific personality markers (emoji, slang, tone)",
            "- Repetitive sentence structures",
            '- Missing contractions ("do not" instead of "don\'t")',
            "",
            "**Hallmarks of Authentic Human Captions:**",
            "",
            "- Personality-specific language and catchphrases",
            "- Natural use of emojis that match the creator's style",
            "- Casual contractions and informal grammar",
            "- Specific references (timing, content, personal touches)",
            "- Conversational tone that feels like a DM, not an ad",
            "- Imperfect punctuation that matches real texting",
            "",
            "**Boost Score Adjustments:**",
            "",
            "- If a caption sounds robotic: **reduce persona_match_score by 0.1-0.2**",
            "- If a caption sounds authentically like the creator: **increase by 0.05-0.1**",
            "- Prioritize captions that would pass as genuine creator messages",
            "",
            "---",
            "",
            f"*Analysis batch generated for {batch.creator_display_name}*",
            f"*{len(captions_to_show)} captions presented for analysis*",
            "",
        ]
    )

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Identify captions needing Claude LLM semantic analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Captions are flagged for LLM analysis when:
    - No stored tone/slang AND pattern detection has low confidence
    - Very low pattern confidence (<0.5)
    - Multiple competing tone signals
    - High-value captions (perf >= 75) with low persona match

Output Formats:
    json   - Machine-readable JSON for programmatic processing
    prompt - Structured markdown prompt for Claude to analyze

Examples:
    python semantic_analysis.py --creator missalexa --format json
    python semantic_analysis.py --creator missalexa --format prompt
    python semantic_analysis.py --creator missalexa --output analysis.json
        """,
    )

    parser.add_argument("--creator", "-c", help="Creator page name (e.g., missalexa)")
    parser.add_argument("--creator-id", help="Creator UUID")
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "prompt"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--limit", type=int, default=500, help="Maximum captions to evaluate (default: 500)"
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

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Build analysis batch
        batch = build_analysis_batch(
            conn, creator_name=args.creator, creator_id=args.creator_id, limit=args.limit
        )

        if not batch:
            print("Error: Creator not found", file=sys.stderr)
            sys.exit(1)

        # Format output
        if args.format == "json":
            output = format_as_json(batch)
        else:
            output = format_as_prompt(batch)

        # Write or print
        if args.output:
            Path(args.output).write_text(output)
            print(f"Analysis written to {args.output}", file=sys.stderr)
            print(f"  Total evaluated: {batch.total_captions_evaluated}", file=sys.stderr)
            print(f"  Needs analysis: {batch.captions_needing_analysis}", file=sys.stderr)
        else:
            print(output)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
