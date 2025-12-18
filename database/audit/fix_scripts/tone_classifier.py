#!/usr/bin/env python3
"""
Tone Classification Backfill Script for EROS Caption Bank.

Production-ready script with three classification strategies:
- Rule-based: Fast pattern matching using keywords/phrases
- LLM-based: Claude API for semantic analysis
- Hybrid: Rule-based first, LLM fallback for low-confidence (<0.7)

Usage:
    python tone_classifier.py classify --tier high --method hybrid --dry-run
    python tone_classifier.py classify --tier mid --method hybrid
    python tone_classifier.py classify --tier low --method rule_based
    python tone_classifier.py status
    python tone_classifier.py resume

Author: EROS Scheduling System
Version: 1.0.0
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Generator

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

# =============================================================================
# CONFIGURATION
# =============================================================================

# Database path (from environment or default)
DEFAULT_DB_PATH = Path.home() / "Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
DB_PATH = Path(os.environ.get("EROS_DATABASE_PATH", DEFAULT_DB_PATH))

# Checkpoint and log directories
CHECKPOINT_DIR = Path.home() / ".eros/checkpoints"
LOG_DIR = Path.home() / ".eros/logs"

# Batch configuration
BATCH_SIZE = 500
COMMIT_INTERVAL = 100  # Commit every N updates for safety

# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.7
MIN_CONFIDENCE_FOR_UPDATE = 0.5

# Allowed tones (validated against these)
ALLOWED_TONES = frozenset([
    "seductive",
    "aggressive",
    "playful",
    "submissive",
    "dominant",
    "bratty",
])

# Default tone when classification fails validation
DEFAULT_TONE = "seductive"
DEFAULT_CONFIDENCE = 0.5


# =============================================================================
# TONE PATTERN DEFINITIONS
# =============================================================================

TONE_PATTERNS: dict[str, dict[str, Any]] = {
    "seductive": {
        "keywords": [
            "waiting for you", "just for you", "all yours", "come over",
            "miss you", "thinking of you", "want you", "need you",
            "make you", "tease", "tempt", "desire", "craving",
            "wet", "juicy", "hot", "sexy", "naughty", "bad",
            "bedroom", "bed", "tonight", "later", "private",
            "secret", "between us", "fantasy", "dream",
            "worship", "staring", "can't look away", "attention",
        ],
        "phrases": [
            r"waiting for you",
            r"just for you",
            r"all yours",
            r"come (and |to )?see",
            r"what if",
            r"imagine",
            r"(i'?m|i am) (so |really )?wet",
            r"get.{1,10}wet",
            r"make you",
            r"drive you",
            r"turn.{1,10}on",
            r"work overtime",
            r"can't (stop|look away)",
        ],
        "weight": 1.0,
    },
    "aggressive": {
        "keywords": [
            "fuck", "fucking", "fucked", "shit", "damn",
            "now", "immediately", "right now", "slut", "whore",
            "bitch", "hard", "rough", "destroy", "wreck",
            "pound", "rail",
        ],
        "phrases": [
            r"fuck (me|you|this|on|in)",
            r"get fucked",
            r"right (fucking )?now",
            r"do it now",
            r"you (little |fucking )?slut",
            r"on your knees",
            r"pound",
            r"destroy",
            r"wreck",
        ],
        "weight": 1.2,  # Higher weight for explicit content
    },
    "playful": {
        "keywords": [
            "hehe", "hihi", "haha", "lol", "oops", "oopsie",
            "guess what", "guess who", "fun", "play", "game",
            "surprise", "peek", "tease", "silly", "cute",
            "ready to play", "wanna play", "distract",
        ],
        "phrases": [
            r"guess (what|who)",
            r"wanna (play|have fun)",
            r"oops",
            r"hehe|hihi|haha",
            r"\blol\b",
            r"just kidding",
            r"teehee",
            r"purr-",
            r"which (one|do you)",
        ],
        "weight": 1.0,
    },
    "submissive": {
        "keywords": [
            "please", "for you", "whatever you want", "use me",
            "yours", "anything", "make me", "let me", "i need",
            "i want", "take me", "have me", "do what you want",
            "anything you want", "just tell me", "command me",
        ],
        "phrases": [
            r"please\b",
            r"for you",
            r"whatever you (want|need|say)",
            r"use me",
            r"(i'?m|i am) yours",
            r"make me",
            r"take me",
            r"tell me what",
            r"anything (you want|for you)",
            r"i'll do anything",
            r"(your )?good girl",
        ],
        "weight": 1.0,
    },
    "dominant": {
        "keywords": [
            "obey", "submit", "kneel", "worship", "command",
            "control", "domination", "dominatrix", "mistress",
            "master", "slave", "servant", "pet", "collar",
            "punishment", "discipline", "demand",
        ],
        "phrases": [
            r"on your knees",
            r"do as i say",
            r"obey (me)?",
            r"submit (to me)?",
            r"kneel (for|before)",
            r"worship (me|my)",
            r"(your )?mistress",
            r"good (boy|girl|pet)",
            r"be a good",
            r"mommy demands",
            r"misstress",
        ],
        "weight": 1.0,
    },
    "bratty": {
        "keywords": [
            "you better", "i deserve", "spoil me", "treat me",
            "buy me", "give me", "i want", "deserve",
            "princess", "queen", "goddess", "worship",
            "beg", "please me", "serve me",
        ],
        "phrases": [
            r"you better",
            r"i deserve",
            r"spoil me",
            r"treat me",
            r"buy me",
            r"give me",
            r"(your )?princess",
            r"(your )?queen",
            r"worship (me|my)",
            r"beg (for|me)",
        ],
        "weight": 1.0,
    },
}


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class ClassificationMethod(str, Enum):
    """Classification method options."""
    RULE_BASED = "rule_based"
    LLM = "llm"
    HYBRID = "hybrid"


class PerformanceTier(str, Enum):
    """Caption performance tiers."""
    HIGH = "high"
    MID = "mid"
    LOW = "low"
    ALL = "all"


@dataclass
class ClassificationResult:
    """Result of a tone classification."""
    caption_id: int
    tone: str
    confidence: float
    method: str
    patterns_matched: list[str] = field(default_factory=list)
    is_valid: bool = True
    error_message: str | None = None


@dataclass
class CheckpointData:
    """Checkpoint state for resume capability."""
    last_caption_id: int
    total_processed: int
    total_updated: int
    tier: str
    method: str
    started_at: str
    updated_at: str
    dry_run: bool = False


@dataclass
class BatchStats:
    """Statistics for a processing batch."""
    processed: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    rule_based: int = 0
    llm_based: int = 0
    tone_distribution: dict[str, int] = field(default_factory=dict)


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging with Rich handler and file output."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_file = LOG_DIR / f"tone_classifier_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Create logger
    logger = logging.getLogger("tone_classifier")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with Rich
    console_handler = RichHandler(
        console=Console(stderr=True),
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
    )
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.info(f"Logging to file: {log_file}")
    return logger


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

class DatabaseManager:
    """Manages SQLite database connections and operations."""

    def __init__(self, db_path: Path, logger: logging.Logger):
        self.db_path = db_path
        self.logger = logger
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Establish database connection."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        self._conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self.logger.info(f"Connected to database: {self.db_path}")
        return self._conn

    @property
    def conn(self) -> sqlite3.Connection:
        """Get active connection."""
        if self._conn is None:
            return self.connect()
        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            self.logger.info("Database connection closed")

    def get_captions_needing_classification(
        self,
        tier: PerformanceTier,
        batch_size: int,
        offset_id: int = 0,
    ) -> list[sqlite3.Row]:
        """Fetch captions that need tone classification."""
        tier_filter = self._get_tier_filter(tier)

        query = f"""
            SELECT caption_id, caption_text, caption_normalized,
                   performance_tier, performance_score
            FROM caption_bank
            WHERE is_active = 1
              AND (tone IS NULL OR tone = '')
              AND caption_id > ?
              {tier_filter}
            ORDER BY caption_id ASC
            LIMIT ?
        """
        cursor = self.conn.execute(query, (offset_id, batch_size))
        return cursor.fetchall()

    def _get_tier_filter(self, tier: PerformanceTier) -> str:
        """Generate SQL filter for performance tier."""
        if tier == PerformanceTier.HIGH:
            return "AND performance_tier = 1"
        elif tier == PerformanceTier.MID:
            return "AND performance_tier = 2"
        elif tier == PerformanceTier.LOW:
            return "AND performance_tier IN (3, 4, 5)"
        return ""  # ALL tiers

    def update_caption_tone(
        self,
        caption_id: int,
        tone: str,
        confidence: float,
        method: str,
    ) -> bool:
        """Update tone classification for a caption."""
        try:
            self.conn.execute(
                """
                UPDATE caption_bank
                SET tone = ?,
                    classification_confidence = ?,
                    classification_method = ?,
                    updated_at = datetime('now')
                WHERE caption_id = ?
                """,
                (tone, confidence, method, caption_id),
            )
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Failed to update caption {caption_id}: {e}")
            return False

    def commit(self) -> None:
        """Commit current transaction."""
        self.conn.commit()

    def get_classification_stats(self) -> dict[str, Any]:
        """Get current classification statistics."""
        stats = {}

        # Total counts
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN tone IS NULL OR tone = '' THEN 1 ELSE 0 END) as unclassified,
                SUM(CASE WHEN tone IS NOT NULL AND tone != '' THEN 1 ELSE 0 END) as classified
            FROM caption_bank
            WHERE is_active = 1
        """)
        row = cursor.fetchone()
        stats["total"] = row["total"]
        stats["unclassified"] = row["unclassified"]
        stats["classified"] = row["classified"]

        # By tier
        cursor = self.conn.execute("""
            SELECT
                performance_tier,
                COUNT(*) as total,
                SUM(CASE WHEN tone IS NULL OR tone = '' THEN 1 ELSE 0 END) as unclassified
            FROM caption_bank
            WHERE is_active = 1
            GROUP BY performance_tier
            ORDER BY performance_tier
        """)
        stats["by_tier"] = {row["performance_tier"]: dict(row) for row in cursor.fetchall()}

        # Tone distribution
        cursor = self.conn.execute("""
            SELECT tone, COUNT(*) as count
            FROM caption_bank
            WHERE is_active = 1 AND tone IS NOT NULL AND tone != ''
            GROUP BY tone
            ORDER BY count DESC
        """)
        stats["tone_distribution"] = {row["tone"]: row["count"] for row in cursor.fetchall()}

        # Method distribution
        cursor = self.conn.execute("""
            SELECT classification_method, COUNT(*) as count
            FROM caption_bank
            WHERE is_active = 1 AND classification_method IS NOT NULL
            GROUP BY classification_method
            ORDER BY count DESC
        """)
        stats["method_distribution"] = {
            row["classification_method"]: row["count"] for row in cursor.fetchall()
        }

        # Average confidence
        cursor = self.conn.execute("""
            SELECT AVG(classification_confidence) as avg_confidence
            FROM caption_bank
            WHERE is_active = 1 AND classification_confidence > 0
        """)
        row = cursor.fetchone()
        stats["avg_confidence"] = round(row["avg_confidence"] or 0, 3)

        return stats


# =============================================================================
# CHECKPOINT MANAGEMENT
# =============================================================================

class CheckpointManager:
    """Manages checkpoint files for resume capability."""

    def __init__(self, checkpoint_dir: Path, logger: logging.Logger):
        self.checkpoint_dir = checkpoint_dir
        self.logger = logger
        self.checkpoint_file = checkpoint_dir / "tone_classifier_checkpoint.json"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: CheckpointData) -> None:
        """Save checkpoint to file."""
        data.updated_at = datetime.now().isoformat()
        with open(self.checkpoint_file, "w") as f:
            json.dump(data.__dict__, f, indent=2)
        self.logger.debug(f"Checkpoint saved: {data.last_caption_id}")

    def load(self) -> CheckpointData | None:
        """Load checkpoint from file."""
        if not self.checkpoint_file.exists():
            return None
        try:
            with open(self.checkpoint_file) as f:
                data = json.load(f)
            return CheckpointData(**data)
        except (json.JSONDecodeError, TypeError) as e:
            self.logger.warning(f"Invalid checkpoint file: {e}")
            return None

    def clear(self) -> None:
        """Remove checkpoint file."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            self.logger.info("Checkpoint cleared")


# =============================================================================
# RULE-BASED CLASSIFIER
# =============================================================================

class RuleBasedClassifier:
    """Rule-based tone classification using pattern matching."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        for tone, config in TONE_PATTERNS.items():
            self._compiled_patterns[tone] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in config["phrases"]
            ]

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify tone using rule-based pattern matching.

        Returns ClassificationResult with tone, confidence, and matched patterns.
        """
        text_lower = text.lower()
        tone_scores: dict[str, float] = {}
        detected_patterns: dict[str, list[str]] = {}

        for tone, config in TONE_PATTERNS.items():
            score = 0.0
            patterns_found: list[str] = []

            # Check keywords (1 point each)
            for keyword in config["keywords"]:
                if keyword in text_lower:
                    score += 1.0
                    patterns_found.append(keyword)

            # Check regex phrases (2 points each, weighted higher)
            for pattern in self._compiled_patterns[tone]:
                if pattern.search(text_lower):
                    score += 2.0
                    # Clean pattern for display
                    clean_pattern = pattern.pattern.replace(r"\b", "").replace(r"\s+", " ")
                    patterns_found.append(clean_pattern)

            # Apply tone weight
            score *= config["weight"]

            if score > 0:
                tone_scores[tone] = score
                detected_patterns[tone] = patterns_found

        # Determine best tone
        if not tone_scores:
            return ClassificationResult(
                caption_id=0,  # Will be set by caller
                tone=DEFAULT_TONE,
                confidence=DEFAULT_CONFIDENCE,
                method="rule_based_default",
                patterns_matched=[],
            )

        best_tone = max(tone_scores, key=tone_scores.get)
        max_score = tone_scores[best_tone]

        # Calculate confidence (normalize, max ~0.95)
        confidence = min(0.95, 0.5 + (max_score / 20.0))

        # Validate tone
        if best_tone not in ALLOWED_TONES:
            self.logger.warning(f"Invalid tone detected: {best_tone}, defaulting to {DEFAULT_TONE}")
            best_tone = DEFAULT_TONE
            confidence = DEFAULT_CONFIDENCE

        return ClassificationResult(
            caption_id=0,
            tone=best_tone,
            confidence=round(confidence, 3),
            method="rule_based",
            patterns_matched=detected_patterns.get(best_tone, [])[:5],
        )


# =============================================================================
# LLM-BASED CLASSIFIER
# =============================================================================

class LLMClassifier:
    """LLM-based tone classification using Claude API."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Anthropic client."""
        try:
            from anthropic import Anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                self.logger.warning("ANTHROPIC_API_KEY not set, LLM classification unavailable")
                return
            self._client = Anthropic(api_key=api_key)
        except ImportError:
            self.logger.warning("anthropic package not installed, LLM classification unavailable")

    @property
    def is_available(self) -> bool:
        """Check if LLM classification is available."""
        return self._client is not None

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify tone using Claude API.

        Returns ClassificationResult with tone, confidence, and reasoning.
        """
        if not self.is_available:
            return ClassificationResult(
                caption_id=0,
                tone=DEFAULT_TONE,
                confidence=DEFAULT_CONFIDENCE,
                method="llm_unavailable",
                is_valid=False,
                error_message="LLM client not available",
            )

        prompt = f"""Analyze the tone of this OnlyFans caption and classify it into ONE of these categories:
- seductive: Alluring, teasing, creating desire
- aggressive: Explicit, demanding, intense
- playful: Fun, lighthearted, teasing in a cute way
- submissive: Eager to please, compliant, yielding
- dominant: Commanding, controlling, powerful
- bratty: Entitled, demanding attention/gifts, princess-like

Caption: "{text}"

Respond with ONLY valid JSON in this exact format:
{{"tone": "<tone>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}}"""

        try:
            response = self._client.messages.create(
                model="claude-3-haiku-20240307",  # Fast and cheap for classification
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )

            result_text = response.content[0].text.strip()

            # Parse JSON response
            try:
                result = json.loads(result_text)
                tone = result.get("tone", DEFAULT_TONE).lower()
                confidence = float(result.get("confidence", DEFAULT_CONFIDENCE))
                reasoning = result.get("reasoning", "")

                # Validate tone
                if tone not in ALLOWED_TONES:
                    self.logger.warning(f"LLM returned invalid tone: {tone}")
                    tone = DEFAULT_TONE
                    confidence = DEFAULT_CONFIDENCE

                return ClassificationResult(
                    caption_id=0,
                    tone=tone,
                    confidence=round(min(confidence, 0.95), 3),
                    method="llm",
                    patterns_matched=[reasoning] if reasoning else [],
                )

            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse LLM response: {e}")
                return ClassificationResult(
                    caption_id=0,
                    tone=DEFAULT_TONE,
                    confidence=DEFAULT_CONFIDENCE,
                    method="llm_parse_error",
                    is_valid=False,
                    error_message=f"JSON parse error: {e}",
                )

        except Exception as e:
            self.logger.error(f"LLM API error: {e}")
            return ClassificationResult(
                caption_id=0,
                tone=DEFAULT_TONE,
                confidence=DEFAULT_CONFIDENCE,
                method="llm_error",
                is_valid=False,
                error_message=str(e),
            )

    def classify_batch(self, captions: list[tuple[int, str]]) -> list[ClassificationResult]:
        """Classify multiple captions (with rate limiting)."""
        results = []
        for caption_id, text in captions:
            result = self.classify(text)
            result.caption_id = caption_id
            results.append(result)
            time.sleep(0.1)  # Basic rate limiting
        return results


# =============================================================================
# HYBRID CLASSIFIER
# =============================================================================

class HybridClassifier:
    """Hybrid classifier: rule-based first, LLM fallback for low confidence."""

    def __init__(
        self,
        rule_classifier: RuleBasedClassifier,
        llm_classifier: LLMClassifier,
        logger: logging.Logger,
        confidence_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
    ):
        self.rule_classifier = rule_classifier
        self.llm_classifier = llm_classifier
        self.logger = logger
        self.confidence_threshold = confidence_threshold

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify using hybrid approach.

        1. Apply rule-based classification first
        2. If confidence >= threshold, use rule-based result
        3. If confidence < threshold, call LLM
        """
        # Step 1: Rule-based classification
        rule_result = self.rule_classifier.classify(text)

        # Step 2: Check confidence threshold
        if rule_result.confidence >= self.confidence_threshold:
            return rule_result

        # Step 3: LLM fallback
        if not self.llm_classifier.is_available:
            # Return rule-based result if LLM unavailable
            self.logger.debug(
                f"LLM unavailable, using low-confidence rule result: {rule_result.confidence}"
            )
            return rule_result

        self.logger.debug(
            f"Rule confidence {rule_result.confidence} < {self.confidence_threshold}, using LLM"
        )
        llm_result = self.llm_classifier.classify(text)

        # If LLM failed, fall back to rule-based
        if not llm_result.is_valid:
            return rule_result

        llm_result.method = "hybrid_llm"
        return llm_result


# =============================================================================
# CLASSIFICATION PROCESSOR
# =============================================================================

class ClassificationProcessor:
    """Main processor for tone classification backfill."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        checkpoint_manager: CheckpointManager,
        logger: logging.Logger,
        console: Console,
    ):
        self.db_manager = db_manager
        self.checkpoint_manager = checkpoint_manager
        self.logger = logger
        self.console = console

        # Initialize classifiers
        self.rule_classifier = RuleBasedClassifier(logger)
        self.llm_classifier = LLMClassifier(logger)
        self.hybrid_classifier = HybridClassifier(
            self.rule_classifier,
            self.llm_classifier,
            logger,
        )

    def get_classifier(self, method: ClassificationMethod):
        """Get appropriate classifier based on method."""
        if method == ClassificationMethod.RULE_BASED:
            return self.rule_classifier
        elif method == ClassificationMethod.LLM:
            return self.llm_classifier
        return self.hybrid_classifier

    def process_batch(
        self,
        captions: list[sqlite3.Row],
        classifier,
        dry_run: bool = False,
    ) -> BatchStats:
        """Process a batch of captions."""
        stats = BatchStats()

        for row in captions:
            caption_id = row["caption_id"]
            text = row["caption_text"] or row["caption_normalized"]

            if not text:
                stats.skipped += 1
                continue

            try:
                result = classifier.classify(text)
                result.caption_id = caption_id

                # Track method used
                if "llm" in result.method:
                    stats.llm_based += 1
                else:
                    stats.rule_based += 1

                # Track tone distribution
                stats.tone_distribution[result.tone] = (
                    stats.tone_distribution.get(result.tone, 0) + 1
                )

                # Update database (unless dry run)
                if not dry_run:
                    success = self.db_manager.update_caption_tone(
                        caption_id=caption_id,
                        tone=result.tone,
                        confidence=result.confidence,
                        method=result.method,
                    )
                    if success:
                        stats.updated += 1
                    else:
                        stats.errors += 1
                else:
                    stats.updated += 1  # Count as "would update" in dry run

                stats.processed += 1

            except Exception as e:
                self.logger.error(f"Error processing caption {caption_id}: {e}")
                stats.errors += 1

        return stats

    def run_classification(
        self,
        tier: PerformanceTier,
        method: ClassificationMethod,
        dry_run: bool = False,
        resume: bool = False,
    ) -> dict[str, Any]:
        """Run the classification process."""
        classifier = self.get_classifier(method)

        # Check for resume
        start_id = 0
        total_processed = 0
        total_updated = 0

        if resume:
            checkpoint = self.checkpoint_manager.load()
            if checkpoint and checkpoint.tier == tier.value and checkpoint.method == method.value:
                start_id = checkpoint.last_caption_id
                total_processed = checkpoint.total_processed
                total_updated = checkpoint.total_updated
                self.logger.info(f"Resuming from checkpoint: caption_id={start_id}")
            else:
                self.logger.warning("No valid checkpoint found, starting fresh")

        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            refresh_per_second=2,
        ) as progress:
            # Get total count for progress bar
            stats = self.db_manager.get_classification_stats()
            total_remaining = stats["unclassified"]

            task = progress.add_task(
                f"[cyan]Classifying ({tier.value} tier, {method.value})",
                total=total_remaining,
                completed=total_processed,
            )

            batch_num = 0
            last_id = start_id

            while True:
                # Fetch batch
                captions = self.db_manager.get_captions_needing_classification(
                    tier=tier,
                    batch_size=BATCH_SIZE,
                    offset_id=last_id,
                )

                if not captions:
                    self.logger.info("No more captions to process")
                    break

                batch_num += 1
                self.logger.info(f"Processing batch {batch_num} ({len(captions)} captions)")

                # Process batch
                batch_stats = self.process_batch(captions, classifier, dry_run)

                # Update totals
                total_processed += batch_stats.processed
                total_updated += batch_stats.updated
                last_id = captions[-1]["caption_id"]

                # Commit periodically
                if not dry_run and batch_num % (COMMIT_INTERVAL // BATCH_SIZE + 1) == 0:
                    self.db_manager.commit()

                # Save checkpoint
                checkpoint_data = CheckpointData(
                    last_caption_id=last_id,
                    total_processed=total_processed,
                    total_updated=total_updated,
                    tier=tier.value,
                    method=method.value,
                    started_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                    dry_run=dry_run,
                )
                self.checkpoint_manager.save(checkpoint_data)

                # Update progress
                progress.update(task, advance=batch_stats.processed)

                # Log batch summary
                self.logger.info(
                    f"Batch {batch_num}: processed={batch_stats.processed}, "
                    f"updated={batch_stats.updated}, errors={batch_stats.errors}, "
                    f"rule={batch_stats.rule_based}, llm={batch_stats.llm_based}"
                )

        # Final commit
        if not dry_run:
            self.db_manager.commit()

        # Clear checkpoint on successful completion
        if not dry_run:
            self.checkpoint_manager.clear()

        return {
            "total_processed": total_processed,
            "total_updated": total_updated,
            "batches": batch_num,
            "tier": tier.value,
            "method": method.value,
            "dry_run": dry_run,
        }


# =============================================================================
# CLI APPLICATION
# =============================================================================

app = typer.Typer(
    name="tone_classifier",
    help="Tone Classification Backfill for EROS Caption Bank",
    add_completion=False,
)
console = Console()


@app.command()
def classify(
    tier: PerformanceTier = typer.Option(
        PerformanceTier.ALL,
        "--tier", "-t",
        help="Performance tier to process (high, mid, low, all)",
    ),
    method: ClassificationMethod = typer.Option(
        ClassificationMethod.HYBRID,
        "--method", "-m",
        help="Classification method (rule_based, llm, hybrid)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without making database changes",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level", "-l",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    ),
) -> None:
    """Run tone classification on captions."""
    logger = setup_logging(log_level)

    console.print(Panel.fit(
        f"[bold cyan]Tone Classification Backfill[/bold cyan]\n"
        f"Tier: {tier.value} | Method: {method.value} | Dry Run: {dry_run}",
        title="EROS Caption Bank",
    ))

    # Validate LLM availability for LLM/hybrid methods
    if method in (ClassificationMethod.LLM, ClassificationMethod.HYBRID):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            console.print(
                "[yellow]Warning: ANTHROPIC_API_KEY not set. "
                "LLM classification will be unavailable.[/yellow]"
            )
            if method == ClassificationMethod.LLM:
                console.print("[red]Error: LLM method requires API key.[/red]")
                raise typer.Exit(1)

    # Initialize components
    db_manager = DatabaseManager(DB_PATH, logger)
    checkpoint_manager = CheckpointManager(CHECKPOINT_DIR, logger)

    try:
        db_manager.connect()

        processor = ClassificationProcessor(
            db_manager=db_manager,
            checkpoint_manager=checkpoint_manager,
            logger=logger,
            console=console,
        )

        # Run classification
        results = processor.run_classification(
            tier=tier,
            method=method,
            dry_run=dry_run,
            resume=False,
        )

        # Display results
        console.print("\n[bold green]Classification Complete[/bold green]")
        console.print(f"  Processed: {results['total_processed']}")
        console.print(f"  Updated: {results['total_updated']}")
        console.print(f"  Batches: {results['batches']}")

        if dry_run:
            console.print("\n[yellow]DRY RUN - No changes were made to the database[/yellow]")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        db_manager.close()


@app.command()
def resume(
    log_level: str = typer.Option(
        "INFO",
        "--log-level", "-l",
        help="Logging level",
    ),
) -> None:
    """Resume classification from last checkpoint."""
    logger = setup_logging(log_level)

    checkpoint_manager = CheckpointManager(CHECKPOINT_DIR, logger)
    checkpoint = checkpoint_manager.load()

    if not checkpoint:
        console.print("[yellow]No checkpoint found. Use 'classify' command instead.[/yellow]")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold cyan]Resuming Classification[/bold cyan]\n"
        f"Tier: {checkpoint.tier} | Method: {checkpoint.method}\n"
        f"Last ID: {checkpoint.last_caption_id} | Processed: {checkpoint.total_processed}",
        title="EROS Caption Bank",
    ))

    # Initialize components
    db_manager = DatabaseManager(DB_PATH, logger)

    try:
        db_manager.connect()

        processor = ClassificationProcessor(
            db_manager=db_manager,
            checkpoint_manager=checkpoint_manager,
            logger=logger,
            console=console,
        )

        # Run classification with resume
        results = processor.run_classification(
            tier=PerformanceTier(checkpoint.tier),
            method=ClassificationMethod(checkpoint.method),
            dry_run=checkpoint.dry_run,
            resume=True,
        )

        # Display results
        console.print("\n[bold green]Classification Complete[/bold green]")
        console.print(f"  Total Processed: {results['total_processed']}")
        console.print(f"  Total Updated: {results['total_updated']}")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        db_manager.close()


@app.command()
def status() -> None:
    """Show current classification status and statistics."""
    console.print(Panel.fit(
        "[bold cyan]Classification Status[/bold cyan]",
        title="EROS Caption Bank",
    ))

    # Check database
    if not DB_PATH.exists():
        console.print(f"[red]Database not found: {DB_PATH}[/red]")
        raise typer.Exit(1)

    logger = logging.getLogger("tone_classifier")
    logger.addHandler(logging.NullHandler())

    db_manager = DatabaseManager(DB_PATH, logger)

    try:
        db_manager.connect()
        stats = db_manager.get_classification_stats()

        # Overall stats table
        overall_table = Table(title="Overall Statistics")
        overall_table.add_column("Metric", style="cyan")
        overall_table.add_column("Value", style="green", justify="right")

        overall_table.add_row("Total Captions", f"{stats['total']:,}")
        overall_table.add_row("Classified", f"{stats['classified']:,}")
        overall_table.add_row("Unclassified", f"{stats['unclassified']:,}")
        pct = (stats["classified"] / stats["total"] * 100) if stats["total"] > 0 else 0
        overall_table.add_row("Progress", f"{pct:.1f}%")
        overall_table.add_row("Avg Confidence", f"{stats['avg_confidence']:.3f}")

        console.print(overall_table)

        # By tier table
        tier_table = Table(title="By Performance Tier")
        tier_table.add_column("Tier", style="cyan")
        tier_table.add_column("Total", justify="right")
        tier_table.add_column("Unclassified", justify="right")
        tier_table.add_column("Progress", justify="right")

        for tier, data in sorted(stats["by_tier"].items()):
            total = data["total"]
            uncl = data["unclassified"]
            pct = ((total - uncl) / total * 100) if total > 0 else 0
            tier_table.add_row(
                str(tier),
                f"{total:,}",
                f"{uncl:,}",
                f"{pct:.1f}%",
            )

        console.print(tier_table)

        # Tone distribution table
        if stats["tone_distribution"]:
            tone_table = Table(title="Tone Distribution")
            tone_table.add_column("Tone", style="cyan")
            tone_table.add_column("Count", justify="right")
            tone_table.add_column("Percentage", justify="right")

            total_classified = sum(stats["tone_distribution"].values())
            for tone, count in sorted(
                stats["tone_distribution"].items(),
                key=lambda x: -x[1]
            ):
                pct = (count / total_classified * 100) if total_classified > 0 else 0
                tone_table.add_row(tone, f"{count:,}", f"{pct:.1f}%")

            console.print(tone_table)

        # Method distribution table
        if stats["method_distribution"]:
            method_table = Table(title="Classification Method Distribution")
            method_table.add_column("Method", style="cyan")
            method_table.add_column("Count", justify="right")

            for method, count in sorted(
                stats["method_distribution"].items(),
                key=lambda x: -x[1]
            ):
                method_table.add_row(method, f"{count:,}")

            console.print(method_table)

        # Check for checkpoint
        checkpoint_manager = CheckpointManager(CHECKPOINT_DIR, logger)
        checkpoint = checkpoint_manager.load()

        if checkpoint:
            console.print("\n[yellow]Active Checkpoint Found:[/yellow]")
            console.print(f"  Tier: {checkpoint.tier}")
            console.print(f"  Method: {checkpoint.method}")
            console.print(f"  Last ID: {checkpoint.last_caption_id}")
            console.print(f"  Processed: {checkpoint.total_processed}")
            console.print(f"  Updated: {checkpoint.updated_at}")
            console.print("\n[dim]Run 'resume' to continue from checkpoint[/dim]")

    finally:
        db_manager.close()


@app.command()
def test_classification(
    text: str = typer.Argument(..., help="Caption text to test classification"),
    method: ClassificationMethod = typer.Option(
        ClassificationMethod.HYBRID,
        "--method", "-m",
        help="Classification method to use",
    ),
) -> None:
    """Test classification on a single caption."""
    logger = logging.getLogger("tone_classifier")
    logger.addHandler(logging.NullHandler())

    console.print(Panel.fit(
        f"[bold cyan]Testing Classification[/bold cyan]\n"
        f"Method: {method.value}",
        title="EROS Caption Bank",
    ))

    # Initialize classifiers
    rule_classifier = RuleBasedClassifier(logger)
    llm_classifier = LLMClassifier(logger)
    hybrid_classifier = HybridClassifier(rule_classifier, llm_classifier, logger)

    if method == ClassificationMethod.RULE_BASED:
        classifier = rule_classifier
    elif method == ClassificationMethod.LLM:
        classifier = llm_classifier
    else:
        classifier = hybrid_classifier

    result = classifier.classify(text)

    # Display result
    result_table = Table(title="Classification Result")
    result_table.add_column("Field", style="cyan")
    result_table.add_column("Value", style="green")

    result_table.add_row("Input", text[:100] + "..." if len(text) > 100 else text)
    result_table.add_row("Tone", result.tone)
    result_table.add_row("Confidence", f"{result.confidence:.3f}")
    result_table.add_row("Method", result.method)
    result_table.add_row("Patterns", ", ".join(result.patterns_matched[:3]) or "None")

    console.print(result_table)


if __name__ == "__main__":
    app()
