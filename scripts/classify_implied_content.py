#!/usr/bin/env python3
"""
Classify Implied Content - LLM-assisted caption classification pipeline.

This script identifies captions that should be reclassified from explicit
solo content types (pussy_play, solo, tits_play, toy_play) to their implied
equivalents for use on free pages and promotional content.

The classification uses pattern-based pre-screening followed by LLM analysis
to determine if content is EXPLICIT (shows direct action) or IMPLIED (suggests
without showing).

Content Type Mappings:
    16 (pussy_play)  -> 34 (implied_pussy_play)
    19 (solo)        -> 35 (implied_solo)
    18 (tits_play)   -> 36 (implied_tits_play)
    17 (toy_play)    -> 37 (implied_toy_play)

Usage:
    # Dry run (preview only)
    python classify_implied_content.py --dry-run

    # Create backup only
    python classify_implied_content.py --backup-only

    # Process specific content type
    python classify_implied_content.py --content-type pussy_play

    # Process with custom batch size
    python classify_implied_content.py --batch-size 25 --dry-run

    # Apply changes (requires backup first)
    python classify_implied_content.py --apply

    # Rollback from backup
    python classify_implied_content.py --rollback backups/file.json

    # Review flagged items
    python classify_implied_content.py --show-review
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from logging_config import configure_logging, get_logger  # noqa: E402

# Configure logging
logger = get_logger("classify_implied")

# Database path resolution
from database import DB_PATH as DEFAULT_DB_PATH  # noqa: E402

# Content type mappings
EXPLICIT_TO_IMPLIED_MAP: dict[int, int] = {
    16: 34,  # pussy_play -> implied_pussy_play
    19: 35,  # solo -> implied_solo
    18: 36,  # tits_play -> implied_tits_play
    17: 37,  # toy_play -> implied_toy_play
}

CONTENT_TYPE_NAMES: dict[int, str] = {
    16: "pussy_play",
    17: "toy_play",
    18: "tits_play",
    19: "solo",
    34: "implied_pussy_play",
    35: "implied_solo",
    36: "implied_tits_play",
    37: "implied_toy_play",
}

# Classification confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.90
MEDIUM_CONFIDENCE_THRESHOLD = 0.75
LOW_CONFIDENCE_THRESHOLD = 0.50

# Pattern dictionaries for signal detection
EXPLICIT_SIGNALS: list[tuple[str, re.Pattern[str]]] = [
    ("direct_action", re.compile(r"\b(watch me|see me|showing|spreading|playing with my)\b", re.I)),
    (
        "body_parts_explicit",
        re.compile(r"\b(pussy|clit|nipples|ass|tits) (shot|pic|video|close.?up)\b", re.I),
    ),
    ("insertion", re.compile(r"\b(insert|inside|penetrat|stretch|fill|deep)\b", re.I)),
    (
        "masturbation",
        re.compile(r"\b(masturbat|finger(ing)?|rub(bing)?|touch(ing)? (my|myself))\b", re.I),
    ),
    ("toy_action", re.compile(r"\b(vibrat(or|ing)|dildo|toy|wand) (inside|deep|in my)\b", re.I)),
    ("orgasm", re.compile(r"\b(cum(ming)?|orgasm|squirt|climax|finish)\b", re.I)),
    ("explicit_offer", re.compile(r"\b(full (video|vid)|uncensored|xxx|explicit|nude)\b", re.I)),
    ("pov_explicit", re.compile(r"\b(pov|point of view|your view|look at)\b", re.I)),
]

IMPLIED_SIGNALS: list[tuple[str, re.Pattern[str]]] = [
    ("teasing_language", re.compile(r"\b(teas(e|ing)|hint|glimpse|peek|sneak)\b", re.I)),
    ("suggestive", re.compile(r"\b(suggest(ive)?|imply|imagine|wonder|maybe)\b", re.I)),
    ("almost", re.compile(r"\b(almost|nearly|about to|getting ready|warming up)\b", re.I)),
    ("covered", re.compile(r"\b(cover(ed)?|hidden|behind|underneath|under my)\b", re.I)),
    ("partial", re.compile(r"\b(partial|half|slight|little|bit of)\b", re.I)),
    ("anticipation", re.compile(r"\b(waiting|anticipat|building|before I|soon)\b", re.I)),
    ("soft_language", re.compile(r"\b(soft|gentle|slow|sensual|intimate)\b", re.I)),
    ("question_tease", re.compile(r"\b(want to see|curious|ready for|interested in)\?", re.I)),
    ("emoji_tease", re.compile(r"[;)]+\s*$|(\ud83d\ude0f|\ud83d\ude09|\ud83d\ude18|[;)])", re.I)),
]


@dataclass
class Caption:
    """Caption data for classification."""

    caption_id: int
    caption_text: str
    content_type_id: int
    content_type_name: str
    performance_score: float
    creator_id: str | None = None
    page_name: str | None = None


@dataclass
class SignalAnalysis:
    """Results of pattern-based signal detection."""

    explicit_signals: list[str] = field(default_factory=list)
    implied_signals: list[str] = field(default_factory=list)
    explicit_count: int = 0
    implied_count: int = 0
    ambiguity_score: float = 0.0  # Higher = more ambiguous


@dataclass
class ClassificationResult:
    """Result of caption classification."""

    caption_id: int
    classification: str  # 'EXPLICIT' or 'IMPLIED'
    confidence: float
    signals_detected: list[str] = field(default_factory=list)
    reasoning: str = ""
    needs_review: bool = False
    original_type_id: int | None = None
    new_type_id: int | None = None
    classified_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ClassificationBatch:
    """A batch of captions for LLM processing."""

    batch_id: int
    captions: list[Caption]
    results: list[ClassificationResult] = field(default_factory=list)


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """
    Create a database connection with row factory.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        SQLite connection with Row factory enabled.

    Raises:
        FileNotFoundError: If database file does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_captions(
    db_path: Path, content_type_ids: list[int], limit: int | None = None
) -> list[Caption]:
    """
    Load captions from the database for specified content types.

    Args:
        db_path: Path to the SQLite database.
        content_type_ids: List of content type IDs to load.
        limit: Optional limit on number of captions to load.

    Returns:
        List of Caption objects.
    """
    conn = get_db_connection(db_path)

    placeholders = ",".join("?" * len(content_type_ids))
    query = f"""
        SELECT
            cb.caption_id,
            cb.caption_text,
            cb.content_type_id,
            ct.type_name AS content_type_name,
            cb.performance_score,
            cb.creator_id,
            cb.page_name
        FROM caption_bank cb
        JOIN content_types ct ON cb.content_type_id = ct.content_type_id
        WHERE cb.content_type_id IN ({placeholders})
          AND cb.is_active = 1
        ORDER BY cb.performance_score DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    try:
        cursor = conn.execute(query, content_type_ids)
        rows = cursor.fetchall()

        captions = [
            Caption(
                caption_id=row["caption_id"],
                caption_text=row["caption_text"],
                content_type_id=row["content_type_id"],
                content_type_name=row["content_type_name"],
                performance_score=row["performance_score"] or 50.0,
                creator_id=row["creator_id"],
                page_name=row["page_name"],
            )
            for row in rows
        ]

        logger.info(f"Loaded {len(captions)} captions from {len(content_type_ids)} content types")
        return captions

    finally:
        conn.close()


def detect_signals(text: str) -> SignalAnalysis:
    """
    Pre-screen caption text for EXPLICIT and IMPLIED patterns.

    Uses regex pattern matching to identify linguistic signals that
    indicate whether content is explicit or implied/teasing.

    Args:
        text: Caption text to analyze.

    Returns:
        SignalAnalysis with detected signals and counts.
    """
    analysis = SignalAnalysis()

    # Check for explicit signals
    for signal_name, pattern in EXPLICIT_SIGNALS:
        if pattern.search(text):
            analysis.explicit_signals.append(signal_name)
            analysis.explicit_count += 1

    # Check for implied signals
    for signal_name, pattern in IMPLIED_SIGNALS:
        if pattern.search(text):
            analysis.implied_signals.append(signal_name)
            analysis.implied_count += 1

    # Calculate ambiguity score
    analysis.ambiguity_score = calculate_ambiguity(analysis.explicit_count, analysis.implied_count)

    return analysis


def calculate_ambiguity(explicit_count: int, implied_count: int) -> float:
    """
    Calculate ambiguity score based on signal balance.

    A score of 0.0 means clearly one type, 1.0 means maximum ambiguity.
    Higher ambiguity means the caption needs LLM analysis.

    Args:
        explicit_count: Number of explicit signals detected.
        implied_count: Number of implied signals detected.

    Returns:
        Ambiguity score between 0.0 and 1.0.
    """
    total = explicit_count + implied_count

    if total == 0:
        # No signals - moderate ambiguity, needs LLM
        return 0.7

    # Calculate how balanced the signals are
    # If all signals are one type, low ambiguity
    # If evenly split, high ambiguity
    max_count = max(explicit_count, implied_count)
    balance = 1 - (max_count / total)

    # Scale to 0-1 range (0.5 balance = maximum ambiguity)
    ambiguity = balance * 2

    return min(ambiguity, 1.0)


def sort_by_ambiguity(
    captions: list[Caption], analyses: dict[int, SignalAnalysis]
) -> list[Caption]:
    """
    Sort captions by ambiguity score (highest first).

    Prioritizes ambiguous captions for LLM processing as they
    benefit most from contextual analysis.

    Args:
        captions: List of captions to sort.
        analyses: Dictionary mapping caption_id to SignalAnalysis.

    Returns:
        Sorted list of captions.
    """
    return sorted(
        captions,
        key=lambda c: analyses.get(c.caption_id, SignalAnalysis()).ambiguity_score,
        reverse=True,
    )


def create_batches(captions: list[Caption], batch_size: int = 50) -> list[ClassificationBatch]:
    """
    Create processing batches from captions.

    Args:
        captions: List of captions to batch.
        batch_size: Maximum captions per batch.

    Returns:
        List of ClassificationBatch objects.
    """
    batches = []

    for i in range(0, len(captions), batch_size):
        batch_captions = captions[i : i + batch_size]
        batch = ClassificationBatch(batch_id=i // batch_size + 1, captions=batch_captions)
        batches.append(batch)

    logger.info(f"Created {len(batches)} batches of up to {batch_size} captions each")
    return batches


def get_prompt_template() -> str:
    """
    Get the LLM prompt template for classification.

    Returns:
        Prompt template string with {captions} placeholder.
    """
    return """You are an expert content classifier for OnlyFans captions. Your task is to classify each caption as either EXPLICIT or IMPLIED based on the language used.

CLASSIFICATION RULES:

EXPLICIT - The caption describes or promises:
- Direct visual content (showing, watching, seeing body parts)
- Active masturbation or self-pleasure
- Toy insertion or penetration
- Orgasm/climax descriptions
- Uncensored/full nude content
- POV angles of explicit acts

IMPLIED - The caption uses:
- Teasing or suggestive language without explicit description
- Anticipation building ("almost", "about to", "getting ready")
- Covered or partially hidden content
- Questions that invite imagination
- Soft/sensual language without explicit action
- Hints at what might happen next

CAPTIONS TO CLASSIFY:
{captions}

For each caption, respond in this JSON format:
{{
    "classifications": [
        {{
            "caption_id": <id>,
            "classification": "EXPLICIT" or "IMPLIED",
            "confidence": <0.0-1.0>,
            "signals": ["signal1", "signal2"],
            "reasoning": "<brief explanation>"
        }}
    ]
}}

Be conservative - if there's clear explicit language, classify as EXPLICIT.
Only classify as IMPLIED if the language is genuinely teasing without explicit promises."""


def classify_batch_with_llm(
    batch: ClassificationBatch, prompt_template: str
) -> list[ClassificationResult]:
    """
    STUB: Classify a batch of captions using LLM.

    This is a stub function that marks all captions as needing review.
    The actual LLM classification will be performed by the orchestrator
    that imports and uses this module.

    Args:
        batch: ClassificationBatch containing captions to classify.
        prompt_template: The prompt template to use (for future implementation).

    Returns:
        List of ClassificationResult objects with needs_review=True.
    """
    logger.info(f"Processing batch {batch.batch_id} with {len(batch.captions)} captions (STUB)")

    results = []

    for caption in batch.captions:
        # Run pattern detection for initial classification
        analysis = detect_signals(caption.caption_text)

        # Determine preliminary classification from patterns
        if analysis.explicit_count > analysis.implied_count:
            classification = "EXPLICIT"
            confidence = min(0.6 + (analysis.explicit_count * 0.05), 0.85)
        elif analysis.implied_count > analysis.explicit_count:
            classification = "IMPLIED"
            confidence = min(0.6 + (analysis.implied_count * 0.05), 0.85)
        else:
            # Ambiguous - default to EXPLICIT (conservative)
            classification = "EXPLICIT"
            confidence = 0.5

        # Calculate new type ID if implied
        new_type_id = None
        if classification == "IMPLIED":
            new_type_id = EXPLICIT_TO_IMPLIED_MAP.get(caption.content_type_id)

        result = ClassificationResult(
            caption_id=caption.caption_id,
            classification=classification,
            confidence=confidence,
            signals_detected=analysis.explicit_signals + analysis.implied_signals,
            reasoning="STUB: Requires LLM classification",
            needs_review=True,  # All stub results need review
            original_type_id=caption.content_type_id,
            new_type_id=new_type_id,
        )

        results.append(result)

    batch.results = results
    return results


def apply_classifications(
    conn: sqlite3.Connection,
    results: list[ClassificationResult],
    dry_run: bool = True,
    auto_apply_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    """
    Apply classification results to the database.

    Updates caption_bank.content_type_id for captions classified as IMPLIED
    and logs all classifications to caption_classifications table.

    Args:
        conn: Database connection.
        results: List of ClassificationResult objects.
        dry_run: If True, only preview changes without applying.
        auto_apply_threshold: Confidence threshold for auto-apply.

    Returns:
        Dictionary with apply statistics.
    """
    stats = {
        "total": len(results),
        "explicit": 0,
        "implied": 0,
        "auto_applied": 0,
        "needs_review": 0,
        "skipped": 0,
        "errors": [],
    }

    cursor = conn.cursor()

    for result in results:
        if result.classification == "EXPLICIT":
            stats["explicit"] += 1
            continue  # No change needed for explicit

        stats["implied"] += 1

        if result.new_type_id is None:
            stats["skipped"] += 1
            continue

        # Determine if auto-apply or review
        if result.confidence >= auto_apply_threshold and not result.needs_review:
            stats["auto_applied"] += 1
            needs_review = 0
        else:
            stats["needs_review"] += 1
            needs_review = 1
            result.needs_review = True

        if dry_run:
            logger.debug(
                f"[DRY RUN] Would reclassify caption {result.caption_id}: "
                f"{result.original_type_id} -> {result.new_type_id} "
                f"(confidence: {result.confidence:.2f}, review: {needs_review})"
            )
            continue

        try:
            # Insert classification record
            cursor.execute(
                """
                INSERT INTO caption_classifications (
                    caption_id,
                    original_type_id,
                    new_type_id,
                    classification,
                    confidence,
                    signals_detected,
                    reasoning,
                    needs_review,
                    classified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    result.caption_id,
                    result.original_type_id,
                    result.new_type_id,
                    result.classification,
                    result.confidence,
                    json.dumps(result.signals_detected),
                    result.reasoning,
                    needs_review,
                    result.classified_at,
                ),
            )

            # Only update caption_bank if confidence meets threshold
            if result.confidence >= auto_apply_threshold and not result.needs_review:
                cursor.execute(
                    """
                    UPDATE caption_bank
                    SET content_type_id = ?,
                        updated_at = datetime('now')
                    WHERE caption_id = ?
                """,
                    (result.new_type_id, result.caption_id),
                )

                # Log to audit table
                cursor.execute(
                    """
                    INSERT INTO caption_audit_log (
                        caption_id,
                        field_name,
                        old_value,
                        new_value,
                        change_reason,
                        change_method,
                        confidence_score,
                        agent_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        result.caption_id,
                        "content_type_id",
                        str(result.original_type_id),
                        str(result.new_type_id),
                        f"Reclassified as IMPLIED: {result.reasoning}",
                        "llm_classification",
                        result.confidence,
                        "classify_implied_content",
                    ),
                )

        except sqlite3.Error as e:
            stats["errors"].append({"caption_id": result.caption_id, "error": str(e)})
            logger.error(f"Error applying classification for {result.caption_id}: {e}")

    if not dry_run:
        conn.commit()
        logger.info(f"Applied {stats['auto_applied']} classifications to database")

    return stats


def create_backup(conn: sqlite3.Connection, output_path: Path, content_type_ids: list[int]) -> Path:
    """
    Create a backup of current caption classifications.

    Args:
        conn: Database connection.
        output_path: Directory to save backup file.
        content_type_ids: Content type IDs being processed.

    Returns:
        Path to the created backup file.
    """
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = output_path / f"caption_backup_{timestamp}.json"

    placeholders = ",".join("?" * len(content_type_ids))
    query = f"""
        SELECT
            caption_id,
            content_type_id,
            classification_confidence,
            classification_method,
            updated_at
        FROM caption_bank
        WHERE content_type_id IN ({placeholders})
          AND is_active = 1
    """

    cursor = conn.execute(query, content_type_ids)
    rows = cursor.fetchall()

    backup_data = {
        "created_at": datetime.now().isoformat(),
        "content_type_ids": content_type_ids,
        "total_captions": len(rows),
        "captions": [
            {
                "caption_id": row["caption_id"],
                "content_type_id": row["content_type_id"],
                "classification_confidence": row["classification_confidence"],
                "classification_method": row["classification_method"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ],
    }

    with open(backup_file, "w") as f:
        json.dump(backup_data, f, indent=2)

    logger.info(f"Created backup with {len(rows)} captions: {backup_file}")
    return backup_file


def rollback_from_backup(
    conn: sqlite3.Connection, backup_path: Path, dry_run: bool = True
) -> dict[str, Any]:
    """
    Restore caption classifications from backup.

    Args:
        conn: Database connection.
        backup_path: Path to backup JSON file.
        dry_run: If True, only preview changes.

    Returns:
        Dictionary with rollback statistics.

    Raises:
        FileNotFoundError: If backup file does not exist.
        ValueError: If backup file is invalid.
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    with open(backup_path) as f:
        backup_data = json.load(f)

    if "captions" not in backup_data:
        raise ValueError("Invalid backup file format: missing 'captions' key")

    stats = {
        "total": len(backup_data["captions"]),
        "restored": 0,
        "skipped": 0,
        "errors": [],
    }

    cursor = conn.cursor()

    for caption in backup_data["captions"]:
        caption_id = caption["caption_id"]
        original_type_id = caption["content_type_id"]

        if dry_run:
            logger.debug(f"[DRY RUN] Would restore caption {caption_id} to type {original_type_id}")
            stats["restored"] += 1
            continue

        try:
            # Restore original content_type_id
            cursor.execute(
                """
                UPDATE caption_bank
                SET content_type_id = ?,
                    updated_at = datetime('now')
                WHERE caption_id = ?
            """,
                (original_type_id, caption_id),
            )

            # Log rollback to audit
            cursor.execute(
                """
                INSERT INTO caption_audit_log (
                    caption_id,
                    field_name,
                    old_value,
                    new_value,
                    change_reason,
                    change_method,
                    agent_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    caption_id,
                    "content_type_id",
                    "unknown",  # We don't know current value without querying
                    str(original_type_id),
                    f"Rollback from backup: {backup_path.name}",
                    "rollback",
                    "classify_implied_content",
                ),
            )

            stats["restored"] += 1

        except sqlite3.Error as e:
            stats["errors"].append({"caption_id": caption_id, "error": str(e)})
            stats["skipped"] += 1

    if not dry_run:
        conn.commit()
        logger.info(f"Rolled back {stats['restored']} captions from backup")

    return stats


def show_review_queue(db_path: Path) -> list[dict[str, Any]]:
    """
    Display captions that need manual review.

    Args:
        db_path: Path to the database.

    Returns:
        List of captions needing review.
    """
    conn = get_db_connection(db_path)

    query = """
        SELECT
            cc.classification_id,
            cc.caption_id,
            cb.caption_text,
            ct_orig.type_name AS original_type,
            ct_new.type_name AS new_type,
            cc.classification,
            cc.confidence,
            cc.signals_detected,
            cc.reasoning,
            cc.classified_at
        FROM caption_classifications cc
        JOIN caption_bank cb ON cc.caption_id = cb.caption_id
        LEFT JOIN content_types ct_orig ON cc.original_type_id = ct_orig.content_type_id
        LEFT JOIN content_types ct_new ON cc.new_type_id = ct_new.content_type_id
        WHERE cc.needs_review = 1
          AND cc.reviewed_at IS NULL
        ORDER BY cc.confidence DESC, cc.classified_at DESC
    """

    try:
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        review_items = []
        for row in rows:
            item = {
                "classification_id": row["classification_id"],
                "caption_id": row["caption_id"],
                "caption_text": row["caption_text"][:100] + "..."
                if len(row["caption_text"]) > 100
                else row["caption_text"],
                "original_type": row["original_type"],
                "new_type": row["new_type"],
                "classification": row["classification"],
                "confidence": row["confidence"],
                "signals": json.loads(row["signals_detected"]) if row["signals_detected"] else [],
                "reasoning": row["reasoning"],
                "classified_at": row["classified_at"],
            }
            review_items.append(item)

        return review_items

    finally:
        conn.close()


def get_classification_stats(db_path: Path) -> dict[str, Any]:
    """
    Get statistics on current classifications.

    Args:
        db_path: Path to the database.

    Returns:
        Dictionary with classification statistics.
    """
    conn = get_db_connection(db_path)

    try:
        # Count by classification type
        cursor = conn.execute("""
            SELECT
                classification,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence,
                SUM(CASE WHEN needs_review = 1 THEN 1 ELSE 0 END) as needs_review
            FROM caption_classifications
            GROUP BY classification
        """)

        by_classification = {}
        for row in cursor.fetchall():
            by_classification[row["classification"]] = {
                "count": row["count"],
                "avg_confidence": round(row["avg_confidence"] or 0, 3),
                "needs_review": row["needs_review"],
            }

        # Count by original content type
        cursor = conn.execute("""
            SELECT
                ct.type_name,
                COUNT(*) as total,
                SUM(CASE WHEN cc.classification = 'IMPLIED' THEN 1 ELSE 0 END) as implied
            FROM caption_classifications cc
            JOIN content_types ct ON cc.original_type_id = ct.content_type_id
            GROUP BY cc.original_type_id
        """)

        by_content_type = {}
        for row in cursor.fetchall():
            by_content_type[row["type_name"]] = {
                "total": row["total"],
                "implied": row["implied"],
                "implied_pct": round(row["implied"] / row["total"] * 100, 1)
                if row["total"] > 0
                else 0,
            }

        return {
            "by_classification": by_classification,
            "by_content_type": by_content_type,
        }

    finally:
        conn.close()


def run_classification_pipeline(
    db_path: Path,
    content_type_ids: list[int],
    batch_size: int = 50,
    dry_run: bool = True,
    backup_only: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """
    Run the full classification pipeline.

    Args:
        db_path: Path to the database.
        content_type_ids: Content type IDs to process.
        batch_size: Captions per batch.
        dry_run: If True, preview only.
        backup_only: If True, only create backup.
        limit: Optional limit on captions to process.

    Returns:
        Pipeline execution statistics.
    """
    logger.info(f"Starting classification pipeline (dry_run={dry_run})")

    conn = get_db_connection(db_path)

    try:
        # Step 1: Create backup
        backup_dir = SCRIPT_DIR / "backups"
        backup_file = create_backup(conn, backup_dir, content_type_ids)

        if backup_only:
            return {
                "status": "backup_only",
                "backup_file": str(backup_file),
            }

        # Step 2: Load captions
        captions = load_captions(db_path, content_type_ids, limit)

        if not captions:
            return {
                "status": "no_captions",
                "message": "No captions found for specified content types",
            }

        # Step 3: Detect signals for all captions
        analyses: dict[int, SignalAnalysis] = {}
        for caption in captions:
            analyses[caption.caption_id] = detect_signals(caption.caption_text)

        # Step 4: Sort by ambiguity
        sorted_captions = sort_by_ambiguity(captions, analyses)

        # Step 5: Create batches
        batches = create_batches(sorted_captions, batch_size)

        # Step 6: Process batches (stub implementation)
        all_results: list[ClassificationResult] = []
        prompt_template = get_prompt_template()

        for batch in batches:
            results = classify_batch_with_llm(batch, prompt_template)
            all_results.extend(results)

        # Step 7: Apply classifications
        apply_stats = apply_classifications(conn, all_results, dry_run=dry_run)

        return {
            "status": "completed",
            "dry_run": dry_run,
            "backup_file": str(backup_file),
            "total_captions": len(captions),
            "batches_processed": len(batches),
            "apply_stats": apply_stats,
        }

    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Classify captions as EXPLICIT or IMPLIED for content type reclassification.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Preview all classifications
    python classify_implied_content.py --dry-run

    # Process only pussy_play content type
    python classify_implied_content.py --content-type pussy_play --dry-run

    # Create backup without processing
    python classify_implied_content.py --backup-only

    # View review queue
    python classify_implied_content.py --show-review

    # Rollback to previous state
    python classify_implied_content.py --rollback backups/caption_backup_20251207_120000.json
        """,
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to EROS database (default: {DEFAULT_DB_PATH})",
    )

    parser.add_argument(
        "--content-type",
        type=str,
        choices=["pussy_play", "solo", "tits_play", "toy_play", "all"],
        default="all",
        help="Content type to process (default: all)",
    )

    parser.add_argument(
        "--batch-size", type=int, default=50, help="Number of captions per batch (default: 50)"
    )

    parser.add_argument("--limit", type=int, help="Limit number of captions to process")

    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without applying to database"
    )

    parser.add_argument(
        "--apply", action="store_true", help="Apply changes to database (requires confirmation)"
    )

    parser.add_argument(
        "--backup-only", action="store_true", help="Only create backup, don't process"
    )

    parser.add_argument("--rollback", type=Path, help="Rollback from specified backup file")

    parser.add_argument(
        "--show-review", action="store_true", help="Show captions that need manual review"
    )

    parser.add_argument("--stats", action="store_true", help="Show classification statistics")

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Configure logging level
    if args.verbose:
        configure_logging(level="DEBUG")

    # Handle rollback
    if args.rollback:
        logger.info(f"Rolling back from backup: {args.rollback}")
        conn = get_db_connection(args.db)
        try:
            stats = rollback_from_backup(conn, args.rollback, dry_run=args.dry_run)
            print(json.dumps(stats, indent=2))
            return 0
        finally:
            conn.close()

    # Handle show review
    if args.show_review:
        review_items = show_review_queue(args.db)
        if not review_items:
            print("No captions pending review.")
        else:
            print(f"\n=== {len(review_items)} Captions Pending Review ===\n")
            for item in review_items:
                print(f"ID: {item['caption_id']}")
                print(f"  Text: {item['caption_text']}")
                print(f"  {item['original_type']} -> {item['new_type']}")
                print(f"  Classification: {item['classification']} ({item['confidence']:.2f})")
                print(f"  Signals: {', '.join(item['signals'])}")
                print()
        return 0

    # Handle stats
    if args.stats:
        stats = get_classification_stats(args.db)
        print(json.dumps(stats, indent=2))
        return 0

    # Determine content type IDs to process
    content_type_map = {
        "pussy_play": [16],
        "solo": [19],
        "tits_play": [18],
        "toy_play": [17],
        "all": [16, 17, 18, 19],
    }
    content_type_ids = content_type_map[args.content_type]

    # Determine dry_run mode
    dry_run = args.dry_run or not args.apply

    if args.apply and not args.dry_run:
        # Require confirmation for apply
        print("\n*** WARNING: This will modify the database! ***")
        print(f"Content types: {args.content_type}")
        print(f"Database: {args.db}")
        response = input("\nType 'yes' to confirm: ")
        if response.lower() != "yes":
            print("Aborted.")
            return 1

    # Run pipeline
    result = run_classification_pipeline(
        db_path=args.db,
        content_type_ids=content_type_ids,
        batch_size=args.batch_size,
        dry_run=dry_run,
        backup_only=args.backup_only,
        limit=args.limit,
    )

    # Output results
    print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
