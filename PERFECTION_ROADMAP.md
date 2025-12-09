# EROS Schedule Generator - Perfection Roadmap

## Executive Summary

This document outlines all remaining fixes and enhancements needed to bring the EROS Schedule Generator skill package to **100% perfection** for production use across your 36-creator, $438K+ OnlyFans portfolio.

**Current State:** 85% Complete - Functional, tested, documented
**Target State:** 100% Perfect - Zero technical debt, fully optimized, bulletproof

---

## Priority 1: Critical Fixes (Must Have)

### 1.1 Database Schema Mismatch in Volume Optimizer Tests

**Problem:** 33 tests fail due to missing `earnings` column in test database
**Impact:** Cannot validate volume optimizer functionality in CI/CD
**Files Affected:** `tests/test_volume_optimizer.py`, `scripts/volume_optimizer.py`

**Root Cause:**
```python
# volume_optimizer.py line ~790
metrics_cursor = self.conn.execute(metrics_query, (row["creator_id"],))
# Query references 'earnings' column that doesn't exist in current schema
```

**Perfect Fix:**
```python
# Option A: Update the SQL query to use existing columns
# Replace 'earnings' with the actual column from creators table
# The schema has 'current_message_net' and 'current_subscription_net' instead

# Option B: Add migration to create 'earnings' as computed column/view
CREATE VIEW creator_earnings AS
SELECT
    creator_id,
    (current_message_net + current_subscription_net) as earnings
FROM creators;
```

**Action Required:**
1. Audit `volume_optimizer.py` lines 780-820 for all column references
2. Cross-reference with actual database schema in `references/database-schema.md`
3. Update queries OR add database migration
4. Verify all 33 tests pass

---

### 1.2 Consolidate PersonaProfile Definition

**Problem:** `PersonaProfile` dataclass defined in 3 different files with different fields
**Impact:** Runtime errors when passing profiles between modules, maintenance nightmare

**Current State:**
| Location | Fields | Attributes |
|----------|--------|------------|
| `shared_context.py:133` | 7 fields | `frozen=False` |
| `match_persona.py:341` | 9 fields | `frozen=True, slots=True` |
| `followup_generator.py:106` | 6 fields | `frozen=True, slots=True` |

**Perfect Fix:**

Create ONE canonical definition in `shared_context.py`:
```python
@dataclass(frozen=True, slots=True)
class PersonaProfile:
    """Canonical persona profile - single source of truth.

    All modules MUST import from shared_context, not define their own.
    """
    creator_id: str
    page_name: str
    primary_tone: str
    secondary_tone: str | None = None
    emoji_frequency: str = "moderate"
    favorite_emojis: str = ""
    slang_level: str = "light"
    avg_sentiment: float = 0.5
    avg_caption_length: int = 150
```

Then update imports in:
- `match_persona.py` - Remove local definition, import from shared_context
- `followup_generator.py` - Remove local definition, import from shared_context
- `generate_schedule.py` - Already imports from shared_context ✓

---

### 1.3 Extract Database Path Resolution

**Problem:** Identical 10-line pattern copy-pasted in 12+ files
**Impact:** Changes require updating 12 files, inconsistency risk, harder to test

**Current Pattern (repeated everywhere):**
```python
_env_db_path = os.environ.get("EROS_DATABASE_PATH", "")
DB_PATH_CANDIDATES = [
    Path(_env_db_path) if _env_db_path else None,
    HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / ".eros" / "eros.db",
]
DB_PATH_CANDIDATES = [p for p in DB_PATH_CANDIDATES if p is not None]
DB_PATH = next((p for p in DB_PATH_CANDIDATES if p.exists()), None)
```

**Perfect Fix:**

Create `scripts/database.py`:
```python
"""Database configuration - single source of truth for database path resolution."""
from pathlib import Path
import os
import sqlite3
from functools import lru_cache

HOME_DIR = Path.home()

def get_database_path() -> Path:
    """Resolve database path from environment or standard locations.

    Returns:
        Path to the EROS database file.

    Raises:
        FileNotFoundError: If no valid database found.
    """
    env_path = os.environ.get("EROS_DATABASE_PATH", "")

    candidates = [
        Path(env_path) if env_path else None,
        HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
        HOME_DIR / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
        HOME_DIR / ".eros" / "eros.db",
    ]

    for path in candidates:
        if path and path.exists():
            return path

    raise FileNotFoundError(
        "EROS database not found. Set EROS_DATABASE_PATH or place database in standard location."
    )

@lru_cache(maxsize=1)
def get_database_connection() -> sqlite3.Connection:
    """Get cached database connection with Row factory."""
    conn = sqlite3.connect(str(get_database_path()))
    conn.row_factory = sqlite3.Row
    return conn

# Module-level constant for backwards compatibility
DB_PATH = get_database_path()
```

Then update all 12 files to:
```python
from database import DB_PATH, get_database_connection
```

**Files to Update:**
1. `match_persona.py`
2. `select_captions.py`
3. `validate_schedule.py`
4. `generate_schedule.py`
5. `calculate_freshness.py`
6. `semantic_analysis.py`
7. `quality_scoring.py`
8. `followup_generator.py`
9. `caption_enhancer.py`
10. `volume_optimizer.py`
11. `prepare_llm_context.py`
12. `classify_implied_content.py`
13. `agent_invoker.py`

---

## Priority 2: High Impact Improvements

### 2.1 Extract Hook Detection to Separate Module

**Problem:** Hook detection logic buried in `match_persona.py` (1,177 lines)
**Impact:** Module doing two unrelated things (persona matching + hook detection)

**Perfect Fix:**

Create `scripts/hook_detection.py`:
```python
"""Hook type detection for caption diversity analysis.

Detects opening hook patterns to ensure variety in scheduled content
and prevent pattern detection by subscribers.
"""
from enum import Enum
import re
from dataclasses import dataclass

class HookType(Enum):
    """Opening hook categories for captions."""
    CURIOSITY = "curiosity"      # "You won't believe...", "Guess what..."
    PERSONAL = "personal"        # "I was thinking about you...", "I made this for you..."
    EXCLUSIVITY = "exclusivity"  # "Only for you...", "Special access..."
    RECENCY = "recency"          # "Just recorded...", "Fresh content..."
    QUESTION = "question"        # "Want to see...?", "Ready for...?"
    DIRECT = "direct"            # "Check this out", "New video"
    TEASING = "teasing"          # "Maybe I'll show you...", "If you're good..."

HOOK_PATTERNS: dict[HookType, list[str]] = {
    HookType.CURIOSITY: [
        r"you won't believe",
        r"guess what",
        r"wait until you see",
        r"you're not ready for",
    ],
    HookType.PERSONAL: [
        r"i was thinking about you",
        r"made this (just )?for you",
        r"wanted you to see",
        r"you've been on my mind",
    ],
    # ... rest of patterns
}

@dataclass(frozen=True, slots=True)
class HookDetectionResult:
    """Result of hook type detection."""
    hook_type: HookType
    confidence: float
    matched_pattern: str | None = None

def detect_hook_type(caption_text: str) -> HookDetectionResult:
    """Detect the opening hook type of a caption.

    Args:
        caption_text: The caption text to analyze.

    Returns:
        HookDetectionResult with detected type and confidence.
    """
    text_lower = caption_text.lower()[:100]  # Only check opening

    for hook_type, patterns in HOOK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return HookDetectionResult(
                    hook_type=hook_type,
                    confidence=0.85,
                    matched_pattern=pattern,
                )

    # Fallback to DIRECT with low confidence
    return HookDetectionResult(
        hook_type=HookType.DIRECT,
        confidence=0.3,
        matched_pattern=None,
    )

# Constants for penalty calculation
SAME_HOOK_PENALTY = 0.7  # 30% weight reduction for consecutive same hooks
MIN_HOOK_DIVERSITY = 4   # Minimum different hook types per week
```

Then update imports in:
- `match_persona.py` - Remove hook code, add `from hook_detection import *`
- `select_captions.py` - Update import source
- `validate_schedule.py` - Update import source

---

### 2.2 Consolidate StratifiedPools Definition

**Problem:** Two different `StratifiedPools` implementations
**Impact:** Confusion about which version to use, potential bugs

**Current State:**
- `generate_schedule.py:74-99` - Basic definition
- `select_captions.py:173-229` - Extended with methods

**Perfect Fix:**

Keep ONLY the `select_captions.py` version (more complete), remove from `generate_schedule.py`:

```python
# In generate_schedule.py, replace local definition with:
from select_captions import StratifiedPools
```

---

### 2.3 Update Package __init__.py with Public API

**Problem:** No clear public API, users must know internal module names
**Impact:** Poor developer experience, harder to use as library

**Perfect Fix:**

Update `scripts/__init__.py`:
```python
"""EROS Schedule Generator - Public API.

Usage:
    from scripts import generate_schedule, ScheduleValidator, PersonaProfile

    # Generate a schedule
    result = generate_schedule(creator_name="missalexa", week="2025-W02")

    # Validate a schedule
    validator = ScheduleValidator()
    issues = validator.validate(schedule_items)
"""

# Core functionality
from .generate_schedule import (
    generate_schedule,
    ScheduleConfig,
    ScheduleResult,
    ScheduleItem,
)

# Validation
from .validate_schedule import (
    ScheduleValidator,
    ValidationIssue,
    ValidationResult,
)

# Data structures
from .shared_context import (
    ScheduleContext,
    PersonaProfile,
)

# Selection
from .select_captions import (
    select_captions,
    StratifiedPools,
    Caption,
)

# Persona matching
from .match_persona import (
    get_persona_profile,
    calculate_persona_boost,
    PersonaMatchResult,
)

# Hook detection
from .hook_detection import (
    HookType,
    detect_hook_type,
    SAME_HOOK_PENALTY,
)

# Weights
from .weights import (
    calculate_weight,
    calculate_payday_multiplier,
    POOL_PROVEN,
    POOL_GLOBAL_EARNER,
    POOL_DISCOVERY,
)

# Database
from .database import (
    DB_PATH,
    get_database_path,
    get_database_connection,
)

__all__ = [
    # Core
    "generate_schedule",
    "ScheduleConfig",
    "ScheduleResult",
    "ScheduleItem",
    # Validation
    "ScheduleValidator",
    "ValidationIssue",
    "ValidationResult",
    # Data structures
    "ScheduleContext",
    "PersonaProfile",
    # Selection
    "select_captions",
    "StratifiedPools",
    "Caption",
    # Persona
    "get_persona_profile",
    "calculate_persona_boost",
    "PersonaMatchResult",
    # Hooks
    "HookType",
    "detect_hook_type",
    "SAME_HOOK_PENALTY",
    # Weights
    "calculate_weight",
    "calculate_payday_multiplier",
    "POOL_PROVEN",
    "POOL_GLOBAL_EARNER",
    "POOL_DISCOVERY",
    # Database
    "DB_PATH",
    "get_database_path",
    "get_database_connection",
]

__version__ = "2.1.0"
```

---

## Priority 3: Code Quality Enhancements

### 3.1 Standardize Error Handling

**Problem:** Mix of custom exceptions, ValueError, and generic Exception
**Impact:** Inconsistent error handling, harder to catch specific errors

**Perfect Fix:**

Create `scripts/exceptions.py`:
```python
"""Custom exceptions for EROS Schedule Generator."""

class ErosError(Exception):
    """Base exception for all EROS errors."""
    pass

class DatabaseError(ErosError):
    """Database-related errors."""
    pass

class CreatorNotFoundError(ErosError):
    """Creator not found in database."""
    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Creator not found: {identifier}")

class CaptionExhaustionError(ErosError):
    """Not enough fresh captions available."""
    def __init__(self, creator_id: str, available: int, required: int):
        self.creator_id = creator_id
        self.available = available
        self.required = required
        super().__init__(
            f"Caption exhaustion for {creator_id}: {available} available, {required} required"
        )

class VaultEmptyError(ErosError):
    """No content available in vault."""
    def __init__(self, creator_id: str, content_type: str | None = None):
        self.creator_id = creator_id
        self.content_type = content_type
        msg = f"Empty vault for {creator_id}"
        if content_type:
            msg += f" (content type: {content_type})"
        super().__init__(msg)

class ValidationError(ErosError):
    """Schedule validation failed."""
    def __init__(self, issues: list, message: str = "Validation failed"):
        self.issues = issues
        super().__init__(f"{message}: {len(issues)} issues found")

class ConfigurationError(ErosError):
    """Invalid configuration."""
    pass
```

Then update all modules to use these exceptions consistently.

---

### 3.2 Add Type Stubs for External Consumers

**Problem:** External tools can't get type hints when importing
**Impact:** No IDE autocomplete for consumers of this package

**Perfect Fix:**

Create `scripts/py.typed` (empty marker file) and ensure all public functions have complete type hints.

---

### 3.3 Standardize Logging

**Problem:** Mix of `print()` to stderr and `logging` module
**Impact:** Inconsistent log output, harder to filter/configure

**Perfect Fix:**

Update all modules to use the existing `logging_config.py`:
```python
# In each module, replace:
print(f"Error: {e}", file=sys.stderr)

# With:
from logging_config import get_logger
logger = get_logger(__name__)
logger.error(f"Error: {e}")
```

---

## Priority 4: Documentation Gaps

### 4.1 Create EXAMPLES.md

**Purpose:** Concrete input/output examples for common use cases

**Content:**
```markdown
# EROS Schedule Generator - Examples

## Quick Schedule Generation
### Input
```bash
python scripts/generate_schedule.py --creator missalexa --week 2025-W02
```

### Output
```json
{
  "schedule": [
    {
      "slot_id": "mon-ppv-1",
      "day": "2025-01-06",
      "time": "10:07",
      "message_type": "ppv",
      "caption_id": 4521,
      "content_type": "bundle",
      "price": 18.00,
      "persona_boost": 1.25
    }
  ]
}
```

## Full Semantic Analysis Mode
...
```

---

### 4.2 Create TROUBLESHOOTING.md

**Purpose:** Common errors and resolutions

**Content:**
```markdown
# Troubleshooting Guide

## CaptionExhaustionError
**Symptom:** "All captions below freshness threshold"
**Cause:** Captions used too recently (< 14 days)
**Solution:** Wait 7-14 days for freshness recovery, or import new captions

## Database Not Found
**Symptom:** "EROS database not found"
**Solution:** Set `EROS_DATABASE_PATH` environment variable
...
```

---

## Priority 5: Performance Optimizations

### 5.1 Add Connection Pooling

**Problem:** New database connection created for each operation
**Impact:** Unnecessary overhead, potential connection leaks

**Perfect Fix:**

In `database.py`:
```python
from contextlib import contextmanager
import threading

_connection_pool: dict[int, sqlite3.Connection] = {}
_pool_lock = threading.Lock()

@contextmanager
def get_connection():
    """Get a thread-local database connection."""
    thread_id = threading.get_ident()

    with _pool_lock:
        if thread_id not in _connection_pool:
            conn = sqlite3.connect(str(get_database_path()))
            conn.row_factory = sqlite3.Row
            _connection_pool[thread_id] = conn

    try:
        yield _connection_pool[thread_id]
    finally:
        pass  # Connection stays in pool for reuse
```

---

### 5.2 Add Query Result Caching

**Problem:** Same queries executed multiple times per schedule generation
**Impact:** Unnecessary database load

**Perfect Fix:**

Add `@lru_cache` to expensive, stable queries:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_creator_profile_cached(creator_id: str) -> dict:
    """Cached creator profile lookup."""
    return get_creator_profile(creator_id)
```

---

## Implementation Order

### Phase 1: Critical (Week 1)
1. Fix database schema mismatch (1.1)
2. Consolidate PersonaProfile (1.2)
3. Extract database path resolution (1.3)

### Phase 2: High Impact (Week 2)
1. Extract hook detection module (2.1)
2. Consolidate StratifiedPools (2.2)
3. Update __init__.py public API (2.3)

### Phase 3: Quality (Week 3)
1. Standardize exceptions (3.1)
2. Add type stubs (3.2)
3. Standardize logging (3.3)

### Phase 4: Documentation (Week 4)
1. Create EXAMPLES.md (4.1)
2. Create TROUBLESHOOTING.md (4.2)

### Phase 5: Performance (Future)
1. Connection pooling (5.1)
2. Query caching (5.2)

---

## Success Criteria

When complete, the package will have:

| Metric | Current | Target |
|--------|---------|--------|
| Test pass rate | 174/207 (84%) | 207/207 (100%) |
| Code duplication | ~12 files | 0 files |
| PersonaProfile definitions | 3 | 1 |
| Public API clarity | Poor | Excellent |
| Exception consistency | Mixed | Unified |
| Documentation completeness | 85% | 100% |

---

## Estimated Effort

| Priority | Tasks | Effort | Impact |
|----------|-------|--------|--------|
| P1 Critical | 3 | 8 hours | Fixes broken tests, eliminates bugs |
| P2 High | 3 | 6 hours | Improves maintainability |
| P3 Quality | 3 | 4 hours | Professional polish |
| P4 Docs | 2 | 2 hours | Better user experience |
| P5 Perf | 2 | 3 hours | Faster execution |
| **Total** | **13** | **23 hours** | **100% Perfect** |

---

## Verification Checklist

After implementing all fixes:

- [ ] All 207 tests pass
- [ ] `PersonaProfile` imported from single location in all files
- [ ] `DB_PATH` imported from `database.py` in all files
- [ ] `HookType` imported from `hook_detection.py` in all files
- [ ] No `type: ignore` comments remaining
- [ ] All public functions have complete docstrings
- [ ] SKILL.md validates against Claude Code 2025 spec
- [ ] README.md examples all work
- [ ] `mypy scripts/` passes with no errors
- [ ] `ruff check scripts/` passes with no errors

---

*Document Version: 1.0*
*Created: 2025-12-09*
*Package Version: 2.1.0*
