# EROS Schedule Generator - Perfection Execution Plan

> **Version:** 1.0.0
> **Created:** 2025-12-15
> **Target:** 100% Production Perfection
> **Subscription Tier:** MAX 20X
> **Estimated Duration:** 8 Waves

---

## Executive Overview

This execution plan transforms the EROS Schedule Generator from its current **80/100** state to **100/100 production perfection**. Each wave is designed to be executed sequentially with specialized sub-agents optimized for maximum accuracy and Claude Code 2025 best practices compliance.

### Current State Assessment

| Component | Current Score | Target Score | Gap |
|-----------|---------------|--------------|-----|
| Security Layer | 82/100 | 100/100 | 18 points |
| Database Integrity | 75/100 | 100/100 | 25 points |
| Code Quality | 76/100 | 100/100 | 24 points |
| Type Safety | 70/100 | 100/100 | 30 points |
| Architecture | 78/100 | 100/100 | 22 points |
| Agent Definitions | 85/100 | 100/100 | 15 points |
| Documentation | 82/100 | 100/100 | 18 points |
| Test Coverage | 50/100 | 100/100 | 50 points |
| **Overall** | **80/100** | **100/100** | **20 points** |

### Success Criteria

Upon completion, the system will:
- Generate **optimal weekly schedules** for all 37+ active creators on demand
- Follow **Claude Code 2025 best practices** throughout
- Achieve **zero critical/high-severity issues**
- Maintain **100% type safety** with full mypy compliance
- Provide **comprehensive test coverage** (>90%)
- Execute with **sub-second response times** for all MCP tools

---

## Wave Structure Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PERFECTION EXECUTION PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WAVE 1: CRITICAL FOUNDATION                                                │
│  ├── security-engineer ──────► SQL Protection & FK Enforcement              │
│  └── database-administrator ─► Data Integrity & Orphan Cleanup              │
│                                    │                                        │
│                                    ▼                                        │
│  WAVE 2: TYPE SAFETY & CODE QUALITY                                         │
│  ├── python-pro ─────────────► Type Annotations & Dataclass Patterns        │
│  └── code-reviewer ──────────► Code Standards & Best Practices              │
│                                    │                                        │
│                                    ▼                                        │
│  WAVE 3: ARCHITECTURE RESTRUCTURING                                         │
│  ├── refactoring-pro ────────► MCP Server Modularization                    │
│  └── backend-developer ──────► Domain Models & Registry Pattern             │
│                                    │                                        │
│                                    ▼                                        │
│  WAVE 4: AGENT & SKILL PERFECTION                                           │
│  ├── command-architect ──────► Agent Definitions & Orchestration            │
│  └── prompt-engineer ────────► Prompt Optimization & Triggers               │
│                                    │                                        │
│                                    ▼                                        │
│  WAVE 5: DOCUMENTATION EXCELLENCE                                           │
│  ├── documentation-engineer ─► README & User Guides                         │
│  └── technical-writer ───────► API Reference & Cross-References             │
│                                    │                                        │
│                                    ▼                                        │
│  WAVE 6: TESTING & VALIDATION                                               │
│  ├── python-pro ─────────────► Unit Tests & Integration Tests               │
│  └── code-reviewer ──────────► Test Coverage & Quality Gates                │
│                                    │                                        │
│                                    ▼                                        │
│  WAVE 7: PERFORMANCE OPTIMIZATION                                           │
│  ├── database-optimizer ─────► Query Optimization & Indexing                │
│  └── performance-analyst ────► Caching & Response Time Tuning               │
│                                    │                                        │
│                                    ▼                                        │
│  WAVE 8: FINAL VERIFICATION & POLISH                                        │
│  ├── code-reviewer ──────────► Full Codebase Audit                          │
│  ├── quality-validator ──────► Schedule Generation Validation               │
│  └── multi-agent-coordinator ► Production Readiness Certification           │
│                                    │                                        │
│                                    ▼                                        │
│                         ┌─────────────────┐                                 │
│                         │  100% PERFECT   │                                 │
│                         │  PRODUCTION     │                                 │
│                         │  READY          │                                 │
│                         └─────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# WAVE 1: CRITICAL FOUNDATION

**Priority:** CRITICAL
**Estimated Duration:** 2-3 hours
**Dependencies:** None (Starting Wave)
**Risk Level:** HIGH - Must complete before proceeding

## Objectives

1. Eliminate all security vulnerabilities in database access layer
2. Enable foreign key enforcement for data integrity
3. Clean orphan records and NULL references
4. Establish secure foundation for all subsequent waves

## Agent Assignments

### Agent 1.1: security-engineer

**Mission:** Harden the MCP database server against all SQL-based attacks and configuration exploits.

**Specific Tasks:**

```markdown
TASK 1.1.1: Enhance execute_query SQL Protection
- Location: mcp/eros_db_server.py:1055-1105
- Action: Add PRAGMA, VACUUM, REINDEX, ANALYZE to dangerous keyword blocklist
- Add comment injection detection (/* */ and -- patterns)
- Implement query complexity limits (max 5 JOINs, max 3 subqueries)
- Add row limit enforcement (max 10,000 rows returned)

TASK 1.1.2: Add Database Connection Security
- Location: mcp/eros_db_server.py:get_db_connection()
- Action: Add connection timeout (30 seconds)
- Enable secure_delete pragma
- Set busy_timeout for concurrent access
- Implement connection validation before returning

TASK 1.1.3: Implement Request Validation
- Location: mcp/eros_db_server.py (all tool handlers)
- Action: Add input length limits for all string parameters
- Validate creator_id format (alphanumeric + underscore only)
- Sanitize all outputs before returning to prevent data leakage

TASK 1.1.4: Add Security Headers and Logging
- Location: mcp/eros_db_server.py
- Action: Implement security event logging
- Log all execute_query calls with sanitized query preview
- Add rate limiting metadata (for future implementation)
```

**Validation Criteria:**
- [ ] All SQL injection test cases pass (existing + 10 new edge cases)
- [ ] PRAGMA commands blocked in execute_query
- [ ] Connection security pragmas enabled
- [ ] All inputs validated before database operations

---

### Agent 1.2: database-administrator

**Mission:** Restore complete data integrity and enable foreign key enforcement.

**Specific Tasks:**

```markdown
TASK 1.2.1: Enable Foreign Key Enforcement
- Location: mcp/eros_db_server.py:get_db_connection()
- Action: Add conn.execute("PRAGMA foreign_keys = ON")
- Verify enforcement with test constraint violation
- Document behavior change in CHANGELOG.md

TASK 1.2.2: Clean Orphan Records
- Location: Database direct operations
- Action: Remove 180 orphan caption_creator_performance records
- Create backup before deletion
- Log cleanup statistics

TASK 1.2.3: Address NULL creator_id in mass_messages
- Location: Database analysis and cleanup
- Action: Analyze 18,780 NULL creator_id records
- Determine if recoverable from other fields (page_name correlation)
- Either backfill or archive to separate table for historical reference
- Document decision and rationale

TASK 1.2.4: Enable WAL Mode for Concurrency
- Location: Database configuration
- Action: Execute PRAGMA journal_mode=WAL
- Verify WAL file creation
- Test concurrent read performance
- Document in database README

TASK 1.2.5: Refresh Index Statistics
- Location: Database maintenance
- Action: Run ANALYZE on all tables
- Verify sqlite_stat1 updated
- Document recommended maintenance schedule
```

**Validation Criteria:**
- [ ] Foreign keys enforced (test with intentional violation)
- [ ] Zero orphan records in caption_creator_performance
- [ ] NULL creator_id issue documented with resolution
- [ ] WAL mode active
- [ ] Index statistics fresh (<24 hours)

---

## Wave 1 Completion Checklist

```markdown
□ SECURITY
  □ execute_query blocks PRAGMA, VACUUM, REINDEX commands
  □ Comment injection patterns detected and blocked
  □ Query complexity limits enforced
  □ Row return limits enforced
  □ Connection timeout configured
  □ Input validation on all string parameters

□ DATABASE INTEGRITY
  □ PRAGMA foreign_keys = ON in all connections
  □ Orphan records cleaned (with backup)
  □ NULL creator_id issue resolved
  □ WAL mode enabled
  □ ANALYZE run on all tables

□ DOCUMENTATION
  □ CHANGELOG.md updated with all changes
  □ Security measures documented
  □ Database maintenance schedule documented
```

---

# WAVE 2: TYPE SAFETY & CODE QUALITY

**Priority:** HIGH
**Estimated Duration:** 3-4 hours
**Dependencies:** Wave 1 Complete
**Risk Level:** MEDIUM

## Objectives

1. Achieve 100% type annotation correctness
2. Implement modern Python dataclass patterns
3. Eliminate all code smells and anti-patterns
4. Establish consistent coding standards

## Agent Assignments

### Agent 2.1: python-pro

**Mission:** Transform all Python code to fully type-safe, modern Python 3.11+ standards.

**Specific Tasks:**

```markdown
TASK 2.1.1: Fix Type Annotation Errors
- Locations:
  - python/allocation/send_type_allocator.py: Lines 156, 189, 236, 278, 326, 370-374
  - python/matching/caption_matcher.py: Line 406
  - python/optimization/schedule_optimizer.py: Lines 14, 76, 491
- Action: Replace all `any` with `Any` from typing module
- Add missing type annotations to all function parameters and returns
- Use Union syntax: `X | None` instead of `Optional[X]`

TASK 2.1.2: Modernize Dataclass Patterns
- Locations: All dataclasses in python/ directory
- Action: Add frozen=True and slots=True to all dataclasses
- Example transformation:
  ```python
  # Before
  @dataclass
  class VolumeConfig:
      tier: VolumeTier
      revenue_per_day: int

  # After
  @dataclass(frozen=True, slots=True)
  class VolumeConfig:
      tier: VolumeTier
      revenue_per_day: int
  ```
- Verify no mutation of dataclass instances in code
- Update any code that mutates to create new instances

TASK 2.1.3: Extract Magic Numbers to Named Constants
- Location: python/matching/caption_matcher.py:392-399
- Action: Create constants module or class-level constants
  ```python
  # Create named constants
  FRESHNESS_DECAY_RATE = 2.0
  MIN_FRESHNESS_SCORE = 20.0
  USAGE_PENALTY_INITIAL = 10
  USAGE_PENALTY_CONTINUED = 8
  ```
- Apply same pattern to schedule_optimizer.py scoring

TASK 2.1.4: Remove Unused Imports
- Locations:
  - python/allocation/send_type_allocator.py: Line 16 (random)
  - python/optimization/schedule_optimizer.py: Line 16 (random if unused)
  - database/audit/fix_scripts/tone_classifier.py: Line 34 (Generator)
- Action: Remove all unused imports
- Run isort for import organization

TASK 2.1.5: Add Type Stubs for External Dependencies
- Location: Create python/py.typed marker file
- Action: Ensure all public APIs are fully typed
- Add py.typed to package for PEP 561 compliance

TASK 2.1.6: Fix Hardcoded Database Paths
- Locations:
  - database/fetish_themed_classifier.py: Line 12
  - database/wave1_engagement_classifier.py: Line 12
  - database/wave1_explicit_couples_classifier.py: Line 22
- Action: Replace with environment variable pattern
  ```python
  DB_PATH = os.environ.get("EROS_DB_PATH",
      Path(__file__).parent / "eros_sd_main.db")
  ```
```

**Validation Criteria:**
- [ ] mypy --strict passes with zero errors
- [ ] All dataclasses use frozen=True, slots=True
- [ ] Zero unused imports
- [ ] All magic numbers extracted to constants
- [ ] No hardcoded absolute paths

---

### Agent 2.2: code-reviewer

**Mission:** Ensure all code meets production quality standards and Claude Code 2025 best practices.

**Specific Tasks:**

```markdown
TASK 2.2.1: Implement Exception Hierarchy
- Location: Create python/exceptions.py
- Action: Define custom exception hierarchy
  ```python
  class EROSError(Exception):
      """Base exception for EROS system."""
      pass

  class CreatorNotFoundError(EROSError):
      """Raised when creator lookup fails."""
      pass

  class InsufficientCaptionsError(EROSError):
      """Raised when not enough captions available."""
      pass

  class ValidationError(EROSError):
      """Raised when validation fails."""
      pass

  class DatabaseError(EROSError):
      """Raised for database operation failures."""
      pass

  class ConfigurationError(EROSError):
      """Raised for configuration issues."""
      pass
  ```
- Update all modules to use custom exceptions
- Add exception handling documentation

TASK 2.2.2: Replace Silent Failures with Logged Warnings
- Location: python/optimization/schedule_optimizer.py:289-290
- Action: Add logging for fallback scenarios
  ```python
  import logging
  logger = logging.getLogger(__name__)

  # Instead of silent fallback:
  logger.warning(
      f"No optimal time found for {item.send_type_key}, "
      f"using random time: {fallback_time}"
  )
  ```
- Apply pattern to all fallback scenarios

TASK 2.2.3: Add Logging Infrastructure
- Location: Create python/logging_config.py
- Action: Configure structured logging
  ```python
  import logging
  import json

  class JSONFormatter(logging.Formatter):
      def format(self, record):
          log_obj = {
              "timestamp": self.formatTime(record),
              "level": record.levelname,
              "module": record.module,
              "message": record.getMessage(),
          }
          return json.dumps(log_obj)
  ```
- Add logger to all Python modules

TASK 2.2.4: Implement Context Manager for Database
- Location: mcp/eros_db_server.py
- Action: Create proper context manager
  ```python
  from contextlib import contextmanager

  @contextmanager
  def get_db_connection():
      conn = sqlite3.connect(DB_PATH)
      conn.row_factory = sqlite3.Row
      conn.execute("PRAGMA foreign_keys = ON")
      try:
          yield conn
      finally:
          conn.close()
  ```
- Update all tool functions to use context manager

TASK 2.2.5: Add Input Validation Decorators
- Location: Create python/validators.py
- Action: Create reusable validation decorators
  ```python
  from functools import wraps

  def validate_creator_id(func):
      @wraps(func)
      def wrapper(creator_id: str, *args, **kwargs):
          if not creator_id or not creator_id.strip():
              raise ValidationError("creator_id cannot be empty")
          if len(creator_id) > 100:
              raise ValidationError("creator_id too long")
          return func(creator_id, *args, **kwargs)
      return wrapper
  ```
```

**Validation Criteria:**
- [ ] Custom exception hierarchy implemented and used
- [ ] All fallback scenarios logged with warnings
- [ ] Structured logging configured for all modules
- [ ] Context manager pattern used for database
- [ ] Input validation decorators applied

---

## Wave 2 Completion Checklist

```markdown
□ TYPE SAFETY
  □ All `any` replaced with `Any`
  □ All functions have return type annotations
  □ Union syntax used (X | None)
  □ mypy --strict passes

□ DATACLASS PATTERNS
  □ All dataclasses have frozen=True
  □ All dataclasses have slots=True
  □ No dataclass mutation in code

□ CODE QUALITY
  □ Custom exception hierarchy created
  □ All unused imports removed
  □ Magic numbers extracted to constants
  □ Structured logging configured
  □ Context manager for database connections

□ DOCUMENTATION
  □ CHANGELOG.md updated
  □ New modules documented with docstrings
```

---

# WAVE 3: ARCHITECTURE RESTRUCTURING

**Priority:** HIGH
**Estimated Duration:** 4-5 hours
**Dependencies:** Wave 2 Complete
**Risk Level:** MEDIUM-HIGH

## Objectives

1. Modularize the 2,159-line MCP server into maintainable components
2. Implement Send Type Registry pattern to eliminate duplication
3. Create unified domain model layer
4. Establish configuration management system

## Agent Assignments

### Agent 3.1: refactoring-pro

**Mission:** Restructure the MCP server into a modular, maintainable architecture.

**Specific Tasks:**

```markdown
TASK 3.1.1: Create MCP Server Module Structure
- Current: Single 2,159-line file
- Target Structure:
  ```
  mcp/
  ├── __init__.py          # Package exports
  ├── server.py            # Main entry point, routing (200 lines max)
  ├── protocol.py          # JSON-RPC protocol handling
  ├── connection.py        # Database connection management
  ├── tools/
  │   ├── __init__.py
  │   ├── base.py          # Tool decorator and registry
  │   ├── creator.py       # get_creator_profile, get_active_creators
  │   ├── caption.py       # get_top_captions, get_send_type_captions
  │   ├── schedule.py      # save_schedule
  │   ├── send_types.py    # get_send_types, get_send_type_details
  │   ├── performance.py   # get_performance_trends, get_best_timing
  │   ├── targeting.py     # get_audience_targets, get_channels
  │   └── query.py         # execute_query (with security)
  └── utils/
      ├── __init__.py
      ├── helpers.py       # row_to_dict, resolve_creator_id
      └── security.py      # Query validation, sanitization
  ```

TASK 3.1.2: Implement Tool Decorator Pattern
- Location: mcp/tools/base.py
- Action: Create decorator-based tool registration
  ```python
  from typing import Callable, Any
  from functools import wraps

  TOOL_REGISTRY: dict[str, dict[str, Any]] = {}

  def mcp_tool(
      name: str,
      description: str,
      schema: dict[str, Any]
  ) -> Callable:
      def decorator(func: Callable) -> Callable:
          @wraps(func)
          def wrapper(*args, **kwargs):
              return func(*args, **kwargs)

          TOOL_REGISTRY[name] = {
              "function": wrapper,
              "description": description,
              "schema": schema
          }
          return wrapper
      return decorator
  ```

TASK 3.1.3: Extract Protocol Handling
- Location: mcp/protocol.py
- Action: Separate JSON-RPC protocol from business logic
  ```python
  class MCPProtocol:
      def parse_request(self, line: str) -> dict[str, Any]: ...
      def format_response(self, result: Any, id: int) -> str: ...
      def format_error(self, error: str, id: int) -> str: ...
  ```

TASK 3.1.4: Create Unified Server Entry Point
- Location: mcp/server.py
- Action: Clean main loop with routing
  ```python
  def main() -> None:
      protocol = MCPProtocol()

      for line in sys.stdin:
          request = protocol.parse_request(line)

          if request["method"] == "tools/list":
              result = list_tools()
          elif request["method"] == "tools/call":
              result = dispatch_tool(request["params"])

          response = protocol.format_response(result, request["id"])
          print(response, flush=True)
  ```

TASK 3.1.5: Migrate All Tool Functions
- Action: Move each tool function to appropriate module
- Maintain exact same function signatures
- Update imports in __init__.py
- Run full test suite after each migration
```

**Validation Criteria:**
- [ ] No single file exceeds 400 lines
- [ ] All existing tests pass after restructure
- [ ] Tool decorator pattern used for all 17 tools
- [ ] Clear separation between protocol and business logic

---

### Agent 3.2: backend-developer

**Mission:** Implement unified domain models and Send Type Registry pattern.

**Specific Tasks:**

```markdown
TASK 3.2.1: Create Domain Model Package
- Location: python/models/
- Action: Create canonical domain models
  ```python
  # python/models/__init__.py
  from .creator import Creator, CreatorProfile
  from .caption import Caption, CaptionScore
  from .schedule import ScheduleItem, ScheduleTemplate
  from .send_type import SendType, SendTypeConfig
  from .volume import VolumeConfig, VolumeTier

  __all__ = [
      "Creator", "CreatorProfile",
      "Caption", "CaptionScore",
      "ScheduleItem", "ScheduleTemplate",
      "SendType", "SendTypeConfig",
      "VolumeConfig", "VolumeTier"
  ]
  ```

TASK 3.2.2: Implement Send Type Registry
- Location: python/registry/send_type_registry.py
- Action: Single source of truth for send type configuration
  ```python
  from dataclasses import dataclass
  from typing import ClassVar

  @dataclass(frozen=True, slots=True)
  class SendTypeConfig:
      key: str
      name: str
      category: str  # revenue, engagement, retention
      page_type: str  # paid, free, both
      timing_preferences: dict[str, Any]
      caption_requirements: list[str]
      max_per_day: int | None
      max_per_week: int | None

  class SendTypeRegistry:
      _instance: ClassVar["SendTypeRegistry | None"] = None
      _types: dict[str, SendTypeConfig]

      def __new__(cls) -> "SendTypeRegistry":
          if cls._instance is None:
              cls._instance = super().__new__(cls)
          return cls._instance

      def load_from_database(self, conn: sqlite3.Connection) -> None:
          """Load all send type configuration from database."""
          ...

      def get(self, key: str) -> SendTypeConfig:
          """Get send type by key."""
          ...

      def get_by_category(self, category: str) -> list[SendTypeConfig]:
          """Get all send types in a category."""
          ...

      def get_timing_preferences(self, key: str) -> dict[str, Any]:
          """Get timing preferences for a send type."""
          ...
  ```

TASK 3.2.3: Remove Hardcoded Taxonomy Lists
- Locations to clean:
  - python/allocation/send_type_allocator.py: Lines 102-130
  - python/optimization/schedule_optimizer.py: Lines 76-231
- Action: Replace with registry lookups
  ```python
  # Before
  REVENUE_TYPES = ["ppv_video", "vip_program", ...]

  # After
  from python.registry import SendTypeRegistry
  registry = SendTypeRegistry()
  revenue_types = registry.get_by_category("revenue")
  ```

TASK 3.2.4: Create Configuration Management
- Location: python/config/
- Action: Centralized configuration loading
  ```python
  # python/config/settings.py
  from pathlib import Path
  import yaml

  class Settings:
      _instance = None

      def __new__(cls):
          if cls._instance is None:
              cls._instance = super().__new__(cls)
              cls._instance._load()
          return cls._instance

      def _load(self) -> None:
          config_path = Path(__file__).parent / "scheduling.yaml"
          if config_path.exists():
              with open(config_path) as f:
                  self._config = yaml.safe_load(f)
          else:
              self._config = self._defaults()

      @property
      def scoring_weights(self) -> dict[str, float]:
          return self._config["scoring"]["weights"]
  ```

TASK 3.2.5: Create Configuration YAML
- Location: python/config/scheduling.yaml
- Action: Externalize all configuration
  ```yaml
  scoring:
    weights:
      performance: 0.35
      freshness: 0.25
      type_priority: 0.20
      persona_match: 0.10
      diversity: 0.10

    thresholds:
      min_performance: 40
      min_freshness: 30
      reuse_days: 30

  timing:
    prime_hours: [10, 14, 19, 21]
    prime_days: [4, 5, 6]  # Fri, Sat, Sun
    avoid_hours: [3, 4, 5, 6, 7]
    min_spacing_minutes: 45
    max_per_hour: 2

  volume:
    tiers:
      LOW:
        paid: {revenue: 3, engagement: 3, retention: 1}
        free: {revenue: 4, engagement: 3, retention: 0}
      MID:
        paid: {revenue: 4, engagement: 3, retention: 2}
        free: {revenue: 5, engagement: 3, retention: 0}
      HIGH:
        paid: {revenue: 5, engagement: 4, retention: 2}
        free: {revenue: 6, engagement: 4, retention: 0}
      ULTRA:
        paid: {revenue: 6, engagement: 5, retention: 3}
        free: {revenue: 8, engagement: 5, retention: 0}
  ```
```

**Validation Criteria:**
- [ ] All domain models in single package
- [ ] SendTypeRegistry singleton implemented
- [ ] Zero hardcoded taxonomy lists in Python code
- [ ] All configuration in YAML files
- [ ] Existing tests pass with new architecture

---

## Wave 3 Completion Checklist

```markdown
□ MCP SERVER MODULARIZATION
  □ Server split into 10+ focused modules
  □ No file exceeds 400 lines
  □ Tool decorator pattern implemented
  □ Protocol handling separated

□ DOMAIN MODELS
  □ python/models/ package created
  □ All dataclasses in single location
  □ Consistent naming conventions

□ SEND TYPE REGISTRY
  □ Registry singleton implemented
  □ Loads from database
  □ All hardcoded lists removed
  □ Caching for performance

□ CONFIGURATION
  □ scheduling.yaml created
  □ Settings singleton implemented
  □ Environment variable overrides supported
  □ Configuration validation on load

□ TESTING
  □ All existing tests pass
  □ New modules have unit tests
  □ Integration tests updated
```

---

# WAVE 4: AGENT & SKILL PERFECTION

**Priority:** HIGH
**Estimated Duration:** 3-4 hours
**Dependencies:** Wave 3 Complete
**Risk Level:** LOW-MEDIUM

## Objectives

1. Perfect all 8 agent definitions for optimal performance
2. Optimize orchestration for MAX 20X tier capabilities
3. Ensure all prompts follow Claude Code 2025 best practices
4. Add proactive invocation triggers

## Agent Assignments

### Agent 4.1: command-architect

**Mission:** Perfect all Claude Code agent definitions and skill files.

**Specific Tasks:**

```markdown
TASK 4.1.1: Fix Agent Model Specifications
- Locations:
  - .claude/agents/timing-optimizer.md
  - .claude/agents/followup-generator.md
- Action: Change model: haiku to model: sonnet
- Rationale: Complex timing calculations require stronger reasoning

TASK 4.1.2: Add Proactive Invocation Triggers
- Location: All agent description fields
- Action: Add "Use PROACTIVELY..." language
- Example transformations:
  ```yaml
  # Before (send-type-allocator.md)
  description: Allocate send types to daily schedule slots...

  # After
  description: Allocate send types to daily schedule slots.
    Use PROACTIVELY in Phase 2 of schedule generation
    AFTER performance-analyst completes.
  ```

TASK 4.1.3: Standardize Agent Frontmatter
- Action: Ensure all agents have consistent structure
  ```yaml
  ---
  name: agent-name
  description: One-line description with PROACTIVELY trigger.
  model: sonnet
  tools:
    - mcp__eros-db__tool1
    - mcp__eros-db__tool2
  ---

  ## Mission
  [Clear single-sentence mission]

  ## Invocation Context
  [When this agent is invoked in the pipeline]

  ## Constraints
  [Explicit MUST and MUST NOT rules]

  ## Algorithm
  [Numbered steps with decision points]

  ## Output Format
  [JSON schema for output]

  ## Error Handling
  [Fallback strategies]
  ```

TASK 4.1.4: Update CLAUDE.md MCP Tools
- Location: CLAUDE.md
- Action: Add all 17 MCP tools with descriptions
  ```markdown
  ## MCP Tools Available

  ### Creator Data
  - `get_creator_profile` - Comprehensive creator data with analytics
  - `get_active_creators` - List all active creators with metrics
  - `get_persona_profile` - Creator tone, emoji style, slang level

  ### Performance & Analytics
  - `get_performance_trends` - Saturation/opportunity scores (7d/14d/30d)
  - `get_content_type_rankings` - TOP/MID/LOW/AVOID classifications
  - `get_best_timing` - Optimal posting times from history

  ### Content & Captions
  - `get_top_captions` - Performance-ranked captions with freshness
  - `get_send_type_captions` - Type-specific caption retrieval
  - `get_vault_availability` - Available content types in vault

  ### Send Type Configuration
  - `get_send_types` - Full 21-type taxonomy
  - `get_send_type_details` - Complete config for single type
  - `get_volume_config` - Category-based volume limits

  ### Targeting & Channels
  - `get_audience_targets` - Targeting segment options
  - `get_channels` - Distribution channel configuration

  ### Schedule Operations
  - `save_schedule` - Persist generated schedule
  - `execute_query` - Custom read-only SQL queries
  ```

TASK 4.1.5: Resolve Agent Count Discrepancy
- Issue: Documentation inconsistently shows 7 vs 8 agents
- Action: Verify exact agent count and update all references
- Files to update:
  - CLAUDE.md
  - SKILL.md
  - SCHEDULE_GENERATOR_BLUEPRINT.md
  - USER_GUIDE.md
```

**Validation Criteria:**
- [ ] All agents use model: sonnet (except simple lookup agents)
- [ ] All agents have proactive triggers in descriptions
- [ ] Consistent frontmatter structure across all agents
- [ ] CLAUDE.md lists all 17 MCP tools
- [ ] Agent count consistent across all documentation

---

### Agent 4.2: prompt-engineer

**Mission:** Optimize all prompts for maximum schedule quality.

**Specific Tasks:**

```markdown
TASK 4.2.1: Optimize SKILL.md for MAX 20X Tier
- Location: .claude/skills/eros-schedule-generator/SKILL.md
- Action: Add tier-specific optimizations
  ```markdown
  ## MAX 20X Tier Optimizations

  When operating under MAX 20X subscription:
  - Utilize parallel agent execution where possible
  - Enable enhanced reasoning for complex decisions
  - Leverage extended context for full week optimization
  - Apply premium scheduling algorithms
  ```

TASK 4.2.2: Enhance quality-validator Prompts
- Location: .claude/agents/quality-validator.md
- Action: Add comprehensive validation checklist
  ```markdown
  ## Validation Checklist

  ### Content Quality
  - [ ] No duplicate captions within 7-day window
  - [ ] All captions have freshness_score >= 30
  - [ ] All captions have performance_score >= 40
  - [ ] Persona tone matches creator profile

  ### Timing Quality
  - [ ] Minimum 45-minute spacing between sends
  - [ ] No sends during avoid_hours (3-7 AM)
  - [ ] Revenue items in prime slots
  - [ ] PPV followups have correct delay

  ### Constraint Compliance
  - [ ] Retention types only on paid pages
  - [ ] VIP program max 1/week
  - [ ] Snapchat bundle max 1/week
  - [ ] PPV followups max 4/day
  ```

TASK 4.2.3: Add Chain-of-Thought Prompting
- Location: All agent files
- Action: Add explicit reasoning instructions
  ```markdown
  ## Reasoning Process

  Before making decisions, think through:
  1. What is the creator's current saturation level?
  2. What content types are performing best?
  3. What timing has historically worked?
  4. What constraints apply to this page type?

  Document your reasoning in the output.
  ```

TASK 4.2.4: Create Orchestration Checkpoints
- Location: .claude/skills/eros-schedule-generator/ORCHESTRATION.md
- Action: Add validation checkpoints between phases
  ```markdown
  ## Phase Transition Checkpoints

  ### After Phase 1 (Performance Analysis)
  - Verify creator profile loaded successfully
  - Confirm saturation_score calculated
  - Validate volume_config retrieved

  ### After Phase 2 (Send Type Allocation)
  - Verify daily allocation totals match volume_config
  - Confirm retention types excluded for free pages
  - Validate weekly limits not exceeded

  [Continue for all phases]
  ```
```

**Validation Criteria:**
- [ ] MAX 20X tier optimizations documented
- [ ] Comprehensive validation checklist in quality-validator
- [ ] Chain-of-thought prompting in all agents
- [ ] Phase transition checkpoints defined

---

## Wave 4 Completion Checklist

```markdown
□ AGENT DEFINITIONS
  □ All agents use appropriate model (sonnet for complex)
  □ Proactive triggers in all descriptions
  □ Consistent frontmatter structure
  □ Constraints explicitly documented
  □ Output formats defined

□ SKILL FILES
  □ MAX 20X tier optimizations added
  □ All 17 MCP tools documented
  □ Phase transition checkpoints defined
  □ Error recovery strategies documented

□ PROMPTS
  □ Chain-of-thought reasoning added
  □ Comprehensive validation checklists
  □ Decision documentation requirements
  □ Fallback strategies defined

□ CONSISTENCY
  □ Agent count matches everywhere
  □ Tool names match MCP server
  □ Terminology consistent
```

---

# WAVE 5: DOCUMENTATION EXCELLENCE

**Priority:** HIGH
**Estimated Duration:** 3-4 hours
**Dependencies:** Wave 4 Complete
**Risk Level:** LOW

## Objectives

1. Create Fortune 500-quality README.md
2. Fix all cross-reference issues
3. Create comprehensive getting started guide
4. Ensure documentation matches implementation

## Agent Assignments

### Agent 5.1: documentation-engineer

**Mission:** Create and perfect all user-facing documentation.

**Specific Tasks:**

```markdown
TASK 5.1.1: Create README.md
- Location: /README.md (project root)
- Action: Create comprehensive entry point
  ```markdown
  # EROS Schedule Generator

  > AI-Powered Multi-Agent Schedule Generation for OnlyFans Creators

  [![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)]()
  [![Python](https://img.shields.io/badge/python-3.11+-green.svg)]()
  [![Claude Code](https://img.shields.io/badge/claude--code-2025-purple.svg)]()

  ## Overview

  EROS (Enhanced Revenue Optimization System) generates optimized weekly
  posting schedules using an 8-agent pipeline and 21-type send taxonomy.

  **Key Features:**
  - 🤖 8 specialized AI agents working in concert
  - 📊 21 distinct send types across 3 categories
  - 🎯 Intelligent audience targeting
  - ⏰ ML-optimized timing recommendations
  - 📈 Performance-driven content selection

  ## Quick Start

  ```bash
  # Generate a schedule
  /eros:generate alexia

  # Analyze creator performance
  /eros:analyze alexia

  # List all creators
  /eros:creators
  ```

  ## Documentation

  | Document | Description |
  |----------|-------------|
  | [User Guide](docs/USER_GUIDE.md) | Complete usage instructions |
  | [Send Type Reference](docs/SEND_TYPE_REFERENCE.md) | 21-type taxonomy details |
  | [Architecture](docs/SCHEDULE_GENERATOR_BLUEPRINT.md) | Technical architecture |
  | [API Reference](docs/API_REFERENCE.md) | MCP tool documentation |

  ## Requirements

  - Claude Code with MAX subscription
  - Python 3.11+
  - SQLite database (included)

  ## License

  Proprietary - All Rights Reserved
  ```

TASK 5.1.2: Create GETTING_STARTED.md
- Location: docs/GETTING_STARTED.md
- Action: Step-by-step onboarding guide
  ```markdown
  # Getting Started with EROS

  ## Prerequisites

  Before you begin, ensure you have:
  - [ ] Claude Code installed and configured
  - [ ] MAX subscription tier active
  - [ ] Project directory cloned

  ## Step 1: Verify Installation

  Run this command to verify the database connection:
  ```bash
  /eros:creators
  ```

  You should see a list of active creators.

  ## Step 2: Analyze a Creator

  Before generating a schedule, analyze the creator's performance:
  ```bash
  /eros:analyze alexia
  ```

  Review:
  - Saturation score (lower = more opportunity)
  - Top content types
  - Best performing times

  ## Step 3: Generate Your First Schedule

  Generate a weekly schedule:
  ```bash
  /eros:generate alexia
  ```

  The system will:
  1. Analyze performance trends
  2. Allocate send types by category
  3. Select optimal captions
  4. Assign audience targets
  5. Optimize timing
  6. Generate followups
  7. Validate quality

  ## Step 4: Review and Save

  Review the generated schedule for:
  - [ ] Appropriate send type mix
  - [ ] Quality caption selections
  - [ ] Optimal timing distribution
  - [ ] Correct targeting

  If satisfied, confirm to save to database.

  ## Next Steps

  - Read [Send Type Reference](SEND_TYPE_REFERENCE.md)
  - Review [Best Practices](USER_GUIDE.md#best-practices)
  - Explore [Advanced Features](USER_GUIDE.md#advanced-features)
  ```

TASK 5.1.3: Fix Cross-Reference Paths
- Locations:
  - docs/USER_GUIDE.md: Lines 336, 484-486
- Action: Fix relative paths
  ```markdown
  # Before (broken)
  See [Send Type Reference](/docs/SEND_TYPE_REFERENCE.md)

  # After (fixed)
  See [Send Type Reference](SEND_TYPE_REFERENCE.md)
  ```

TASK 5.1.4: Create API_REFERENCE.md
- Location: docs/API_REFERENCE.md
- Action: Document all MCP tools
  ```markdown
  # EROS API Reference

  ## MCP Tools

  ### get_creator_profile

  Retrieves comprehensive profile for a creator.

  **Parameters:**
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | creator_id | string | Yes | Creator ID or page_name |

  **Returns:**
  ```json
  {
    "creator_id": "alexia",
    "page_name": "alexia",
    "page_type": "paid",
    "fan_count": 5000,
    "performance_tier": 2,
    "volume_level": "MID",
    ...
  }
  ```

  **Example:**
  ```
  get_creator_profile(creator_id="alexia")
  ```

  [Repeat for all 17 tools]
  ```
```

**Validation Criteria:**
- [ ] README.md exists at project root
- [ ] GETTING_STARTED.md provides complete onboarding
- [ ] All cross-references resolve correctly
- [ ] API_REFERENCE.md documents all 17 tools

---

### Agent 5.2: technical-writer

**Mission:** Ensure documentation accuracy and professional quality.

**Specific Tasks:**

```markdown
TASK 5.2.1: Standardize Document Headers
- Action: All docs >500 lines get Table of Contents
- Apply consistent header format:
  ```markdown
  # Document Title

  > Brief description

  **Version:** X.Y.Z | **Updated:** YYYY-MM-DD

  ## Table of Contents

  1. [Section 1](#section-1)
  2. [Section 2](#section-2)
  ...
  ```

TASK 5.2.2: Create Glossary
- Location: docs/GLOSSARY.md
- Action: Define all domain terms
  ```markdown
  # EROS Glossary

  ## A

  **Audience Target**: A segment of subscribers defined by
  engagement level, purchase history, or subscription status.

  ## F

  **Freshness Score**: A 0-100 metric indicating how recently
  a caption was used. Calculated as:
  `100 - (days_since_use * 2)`, minimum 0.

  ## S

  **Saturation Score**: A 0-100 metric indicating audience
  fatigue level. Higher scores indicate more recent activity.

  **Send Type**: One of 21 categorized message types
  (7 revenue, 9 engagement, 5 retention).

  [Continue for all terms]
  ```

TASK 5.2.3: Update Version Footers
- Action: Standardize all document footers
  ```markdown
  ---

  *Version 2.0.0 | Last Updated: 2025-12-15 |
  [Report Issue](https://github.com/...)*
  ```

TASK 5.2.4: Verify Code Examples
- Action: Test all code examples in documentation
- Ensure examples match current implementation
- Add "Verified" badge to tested examples

TASK 5.2.5: Create Migration Guide
- Location: database/migrations/README.md
- Action: Document migration execution order
  ```markdown
  # Database Migrations

  ## Execution Order

  Run migrations in numerical order:

  1. `001_initial_schema.sql`
  2. `002_add_indexes.sql`
  ...
  8. `008_send_types_foundation.sql`

  ## Running Migrations

  ```bash
  sqlite3 database/eros_sd_main.db < database/migrations/008_send_types_foundation.sql
  ```

  ## Rollback

  Backup before any migration:
  ```bash
  cp database/eros_sd_main.db database/eros_sd_main.db.backup
  ```
  ```
```

**Validation Criteria:**
- [ ] All documents have standardized headers
- [ ] Glossary covers all domain terms
- [ ] Version footers consistent
- [ ] Code examples verified working
- [ ] Migration guide complete

---

## Wave 5 Completion Checklist

```markdown
□ README.md
  □ Created at project root
  □ Badges for version/python/claude-code
  □ Quick start examples
  □ Documentation index

□ USER DOCUMENTATION
  □ GETTING_STARTED.md complete
  □ API_REFERENCE.md for all tools
  □ GLOSSARY.md with all terms
  □ Migration guide created

□ QUALITY
  □ All cross-references working
  □ Consistent headers and footers
  □ Code examples verified
  □ No broken links

□ ACCURACY
  □ Agent count consistent (8)
  □ Tool count consistent (17)
  □ Version numbers aligned
```

---

# WAVE 6: TESTING & VALIDATION

**Priority:** HIGH
**Estimated Duration:** 4-5 hours
**Dependencies:** Wave 5 Complete
**Risk Level:** MEDIUM

## Objectives

1. Fix all broken tests
2. Achieve >90% code coverage
3. Add integration tests for full pipeline
4. Create automated quality gates

## Agent Assignments

### Agent 6.1: python-pro

**Mission:** Create comprehensive test suite with full coverage.

**Specific Tasks:**

```markdown
TASK 6.1.1: Fix Broken Test Imports
- Location: python/tests/test_core_algorithms.py:18-25
- Action: Remove non-existent imports
  ```python
  # Remove these non-existent imports:
  # from python.allocation.send_type_allocator import DayContext
  # from python.matching.caption_matcher import PersonaProfile

  # Keep only existing classes:
  from python.allocation.send_type_allocator import (
      SendTypeAllocator,
      VolumeTier,
      VolumeConfig,
  )
  from python.matching.caption_matcher import (
      CaptionMatcher,
      Caption,
  )
  ```

TASK 6.1.2: Add Unit Tests for All Modules
- Location: python/tests/
- Action: Create comprehensive test files
  ```
  python/tests/
  ├── __init__.py
  ├── conftest.py           # Shared fixtures
  ├── test_allocator.py     # SendTypeAllocator tests
  ├── test_matcher.py       # CaptionMatcher tests
  ├── test_optimizer.py     # ScheduleOptimizer tests
  ├── test_models.py        # Domain model tests
  ├── test_registry.py      # SendTypeRegistry tests
  ├── test_config.py        # Configuration tests
  └── test_exceptions.py    # Exception hierarchy tests
  ```

TASK 6.1.3: Create Test Fixtures
- Location: python/tests/conftest.py
- Action: Define reusable fixtures
  ```python
  import pytest
  from python.models import Creator, Caption, VolumeConfig

  @pytest.fixture
  def sample_creator() -> Creator:
      return Creator(
          creator_id="test_creator",
          page_name="test_creator",
          page_type="paid",
          fan_count=5000,
          performance_tier=2
      )

  @pytest.fixture
  def sample_captions() -> list[Caption]:
      return [
          Caption(
              caption_id=1,
              caption_text="Test caption 1",
              caption_type="sexting",
              performance_score=85.0,
              freshness_score=90.0
          ),
          # Add more varied examples
      ]

  @pytest.fixture
  def sample_volume_config() -> VolumeConfig:
      return VolumeConfig(
          tier=VolumeTier.MID,
          revenue_per_day=4,
          engagement_per_day=3,
          retention_per_day=2
      )
  ```

TASK 6.1.4: Add Edge Case Tests
- Action: Test boundary conditions
  ```python
  class TestSendTypeAllocator:
      def test_volume_tier_boundary_999_fans(self):
          """Exactly 999 fans should be LOW tier."""
          tier = SendTypeAllocator.get_volume_tier(999)
          assert tier == VolumeTier.LOW

      def test_volume_tier_boundary_1000_fans(self):
          """Exactly 1000 fans should be MID tier."""
          tier = SendTypeAllocator.get_volume_tier(1000)
          assert tier == VolumeTier.MID

      def test_free_page_no_retention(self):
          """Free pages should never get retention types."""
          allocator = SendTypeAllocator()
          allocation = allocator.allocate_day(
              config=sample_config,
              page_type="free",
              day=datetime.now()
          )
          retention_types = [i for i in allocation
                           if i["category"] == "retention"]
          assert len(retention_types) == 0
  ```

TASK 6.1.5: Add Integration Tests
- Location: python/tests/test_integration.py
- Action: Test full pipeline flow
  ```python
  class TestScheduleGenerationPipeline:
      def test_full_pipeline_paid_page(self, db_connection):
          """Test complete schedule generation for paid page."""
          # Phase 1: Performance analysis
          profile = get_creator_profile("test_creator")
          assert profile["page_type"] == "paid"

          # Phase 2: Send type allocation
          allocator = SendTypeAllocator()
          allocation = allocator.allocate_week(...)
          assert len(allocation) == 7  # 7 days

          # Phase 3: Caption matching
          matcher = CaptionMatcher()
          for day, items in allocation.items():
              for item in items:
                  caption = matcher.select_caption(...)
                  assert caption is not None

          # Continue through all phases
          ...

      def test_full_pipeline_free_page(self, db_connection):
          """Test complete schedule generation for free page."""
          # Similar but verify no retention types
          ...
  ```
```

**Validation Criteria:**
- [ ] All tests pass (pytest exits 0)
- [ ] No import errors in test files
- [ ] Edge cases covered for all boundary conditions
- [ ] Integration tests cover full pipeline

---

### Agent 6.2: code-reviewer

**Mission:** Establish quality gates and coverage requirements.

**Specific Tasks:**

```markdown
TASK 6.2.1: Configure pytest Coverage
- Location: pyproject.toml
- Action: Add coverage configuration
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["python/tests", "mcp"]
  python_files = ["test_*.py"]
  python_classes = ["Test*"]
  python_functions = ["test_*"]
  addopts = "--cov=python --cov=mcp --cov-report=html --cov-report=term-missing"

  [tool.coverage.run]
  source = ["python", "mcp"]
  omit = ["**/tests/*", "**/__init__.py"]

  [tool.coverage.report]
  fail_under = 90
  show_missing = true
  exclude_lines = [
      "pragma: no cover",
      "if TYPE_CHECKING:",
      "raise NotImplementedError",
  ]
  ```

TASK 6.2.2: Add MCP Server Tests
- Location: mcp/test_tools.py
- Action: Test all 17 tools with mocked database
  ```python
  import pytest
  from unittest.mock import MagicMock, patch

  class TestMCPTools:
      @pytest.fixture
      def mock_db(self):
          with patch('mcp.connection.get_db_connection') as mock:
              conn = MagicMock()
              mock.return_value.__enter__.return_value = conn
              yield conn

      def test_get_creator_profile_found(self, mock_db):
          """Test successful creator profile retrieval."""
          mock_db.execute.return_value.fetchone.return_value = {
              "creator_id": "test",
              "page_name": "test",
              "page_type": "paid"
          }

          result = get_creator_profile("test")

          assert result["creator_id"] == "test"
          assert "error" not in result

      def test_get_creator_profile_not_found(self, mock_db):
          """Test creator not found handling."""
          mock_db.execute.return_value.fetchone.return_value = None

          result = get_creator_profile("nonexistent")

          assert "error" in result
  ```

TASK 6.2.3: Create Test Quality Gates
- Location: .github/workflows/test.yml (or CI equivalent)
- Action: Define automated quality checks
  ```yaml
  name: Test Suite

  on: [push, pull_request]

  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: '3.11'

        - name: Install dependencies
          run: pip install -e ".[dev]"

        - name: Run type checking
          run: mypy --strict python/ mcp/

        - name: Run tests with coverage
          run: pytest --cov-fail-under=90

        - name: Check code style
          run: ruff check python/ mcp/
  ```

TASK 6.2.4: Add Contract Tests for MCP
- Location: mcp/test_contracts.py
- Action: Verify tool response schemas
  ```python
  from jsonschema import validate

  CREATOR_PROFILE_SCHEMA = {
      "type": "object",
      "required": ["creator_id", "page_name", "page_type"],
      "properties": {
          "creator_id": {"type": "string"},
          "page_name": {"type": "string"},
          "page_type": {"enum": ["paid", "free"]},
          "fan_count": {"type": "integer", "minimum": 0},
          "performance_tier": {"type": "integer", "minimum": 1, "maximum": 5}
      }
  }

  def test_creator_profile_contract():
      result = get_creator_profile("test_creator")
      if "error" not in result:
          validate(instance=result, schema=CREATOR_PROFILE_SCHEMA)
  ```

TASK 6.2.5: Create Performance Benchmarks
- Location: python/tests/test_performance.py
- Action: Ensure response time requirements
  ```python
  import time
  import pytest

  class TestPerformance:
      @pytest.mark.benchmark
      def test_caption_selection_speed(self, sample_captions):
          """Caption selection should complete in <100ms."""
          matcher = CaptionMatcher()

          start = time.perf_counter()
          for _ in range(100):
              matcher.select_caption(
                  send_type_key="ppv_video",
                  captions=sample_captions
              )
          elapsed = (time.perf_counter() - start) / 100

          assert elapsed < 0.1, f"Caption selection too slow: {elapsed:.3f}s"

      @pytest.mark.benchmark
      def test_full_week_allocation_speed(self, sample_config):
          """Full week allocation should complete in <500ms."""
          allocator = SendTypeAllocator()

          start = time.perf_counter()
          allocator.allocate_week(
              config=sample_config,
              page_type="paid",
              week_start=datetime.now()
          )
          elapsed = time.perf_counter() - start

          assert elapsed < 0.5, f"Week allocation too slow: {elapsed:.3f}s"
  ```
```

**Validation Criteria:**
- [ ] pytest-cov configured with 90% threshold
- [ ] All 17 MCP tools have tests
- [ ] Contract tests for all tool responses
- [ ] Performance benchmarks defined and passing
- [ ] CI pipeline configured (if applicable)

---

## Wave 6 Completion Checklist

```markdown
□ TEST FIXES
  □ All import errors resolved
  □ Non-existent class references removed
  □ Tests run without errors

□ COVERAGE
  □ >90% line coverage
  □ All modules have tests
  □ Edge cases covered
  □ Integration tests complete

□ QUALITY GATES
  □ mypy --strict passes
  □ Coverage threshold enforced
  □ Contract tests pass
  □ Performance benchmarks pass

□ CI/CD
  □ Test workflow configured
  □ Automated on push/PR
  □ Coverage reports generated
```

---

# WAVE 7: PERFORMANCE OPTIMIZATION

**Priority:** MEDIUM-HIGH
**Estimated Duration:** 2-3 hours
**Dependencies:** Wave 6 Complete
**Risk Level:** LOW

## Objectives

1. Optimize database queries for sub-100ms response
2. Implement intelligent caching
3. Reduce memory footprint
4. Ensure scalability for 37+ creators

## Agent Assignments

### Agent 7.1: database-optimizer

**Mission:** Optimize all database operations for maximum performance.

**Specific Tasks:**

```markdown
TASK 7.1.1: Analyze and Optimize Slow Queries
- Action: Run EXPLAIN QUERY PLAN on all MCP tool queries
- Identify any TABLE SCAN operations
- Add missing indexes for common query patterns

TASK 7.1.2: Add Missing Composite Indexes
- Location: Database migration
- Action: Create optimized indexes
  ```sql
  -- Composite index for caption selection
  CREATE INDEX IF NOT EXISTS idx_cb_active_type_perf
  ON caption_bank(is_active, caption_type, performance_score DESC)
  WHERE is_active = 1;

  -- Composite index for timing analysis
  CREATE INDEX IF NOT EXISTS idx_mm_timing_analysis
  ON mass_messages(creator_id, message_type, sending_time, earnings)
  WHERE earnings > 0;

  -- Composite index for freshness calculation
  CREATE INDEX IF NOT EXISTS idx_ccp_freshness
  ON caption_creator_performance(creator_id, caption_id, last_used_date DESC);
  ```

TASK 7.1.3: Implement Query Result Caching
- Location: mcp/utils/cache.py
- Action: Add TTL-based caching for expensive queries
  ```python
  from functools import lru_cache
  from datetime import datetime, timedelta
  from typing import Any

  class QueryCache:
      def __init__(self, ttl_seconds: int = 300):
          self._cache: dict[str, tuple[Any, datetime]] = {}
          self._ttl = timedelta(seconds=ttl_seconds)

      def get(self, key: str) -> Any | None:
          if key in self._cache:
              value, timestamp = self._cache[key]
              if datetime.now() - timestamp < self._ttl:
                  return value
              del self._cache[key]
          return None

      def set(self, key: str, value: Any) -> None:
          self._cache[key] = (value, datetime.now())

      def invalidate(self, pattern: str) -> None:
          keys_to_delete = [k for k in self._cache if pattern in k]
          for k in keys_to_delete:
              del self._cache[k]

  # Use for expensive queries
  cache = QueryCache(ttl_seconds=300)

  def get_creator_profile_cached(creator_id: str) -> dict:
      cache_key = f"creator_profile:{creator_id}"
      cached = cache.get(cache_key)
      if cached:
          return cached

      result = get_creator_profile(creator_id)
      cache.set(cache_key, result)
      return result
  ```

TASK 7.1.4: Optimize save_schedule Transaction
- Location: mcp/tools/schedule.py (after restructure)
- Action: Use batch operations
  ```python
  def save_schedule(creator_id: str, week_start: str, items: list) -> dict:
      with get_db_connection() as conn:
          try:
              # Batch insert with executemany
              conn.executemany(
                  """
                  INSERT INTO schedule_items (...)
                  VALUES (?, ?, ?, ...)
                  """,
                  [(item["field1"], item["field2"], ...) for item in items]
              )
              conn.commit()
          except sqlite3.Error:
              conn.rollback()
              raise
  ```

TASK 7.1.5: Add Database Connection Pooling
- Location: mcp/connection.py
- Action: Implement connection pool for concurrent access
  ```python
  from queue import Queue
  from threading import Lock

  class ConnectionPool:
      def __init__(self, db_path: str, max_connections: int = 5):
          self._db_path = db_path
          self._pool: Queue[sqlite3.Connection] = Queue(maxsize=max_connections)
          self._lock = Lock()

          # Pre-create connections
          for _ in range(max_connections):
              self._pool.put(self._create_connection())

      def _create_connection(self) -> sqlite3.Connection:
          conn = sqlite3.connect(self._db_path)
          conn.row_factory = sqlite3.Row
          conn.execute("PRAGMA foreign_keys = ON")
          conn.execute("PRAGMA journal_mode = WAL")
          return conn

      @contextmanager
      def get_connection(self):
          conn = self._pool.get()
          try:
              yield conn
          finally:
              self._pool.put(conn)
  ```
```

**Validation Criteria:**
- [ ] All queries complete in <100ms
- [ ] No TABLE SCAN operations in critical paths
- [ ] Caching reduces redundant queries by >50%
- [ ] Connection pool handles concurrent requests

---

### Agent 7.2: performance-analyst

**Mission:** Ensure schedule generation meets performance targets.

**Specific Tasks:**

```markdown
TASK 7.2.1: Profile Schedule Generation Pipeline
- Action: Add timing instrumentation to each phase
  ```python
  import time
  from contextlib import contextmanager

  @contextmanager
  def timed_phase(phase_name: str):
      start = time.perf_counter()
      try:
          yield
      finally:
          elapsed = time.perf_counter() - start
          logger.info(f"Phase {phase_name}: {elapsed:.3f}s")

  # Usage in orchestration
  with timed_phase("1_performance_analysis"):
      analysis = performance_analyst.analyze(creator_id)

  with timed_phase("2_send_type_allocation"):
      allocation = allocator.allocate_week(...)
  ```

TASK 7.2.2: Optimize Caption Matching
- Location: python/matching/caption_matcher.py
- Action: Pre-sort captions and use binary search
  ```python
  from bisect import bisect_left

  class CaptionMatcher:
      def __init__(self):
          self._captions_by_type: dict[str, list[Caption]] = {}

      def preload_captions(self, captions: list[Caption]) -> None:
          """Pre-sort captions by type and score for fast lookup."""
          for caption in captions:
              if caption.caption_type not in self._captions_by_type:
                  self._captions_by_type[caption.caption_type] = []
              self._captions_by_type[caption.caption_type].append(caption)

          # Sort by performance_score descending
          for cap_type in self._captions_by_type:
              self._captions_by_type[cap_type].sort(
                  key=lambda c: c.performance_score,
                  reverse=True
              )
  ```

TASK 7.2.3: Implement Lazy Loading
- Action: Only load data when needed
  ```python
  class LazyCreatorProfile:
      def __init__(self, creator_id: str):
          self._creator_id = creator_id
          self._profile: dict | None = None
          self._captions: list[Caption] | None = None

      @property
      def profile(self) -> dict:
          if self._profile is None:
              self._profile = get_creator_profile(self._creator_id)
          return self._profile

      @property
      def captions(self) -> list[Caption]:
          if self._captions is None:
              self._captions = get_top_captions(self._creator_id)
          return self._captions
  ```

TASK 7.2.4: Add Performance Monitoring
- Location: Create python/monitoring.py
- Action: Track and report metrics
  ```python
  from dataclasses import dataclass, field
  from datetime import datetime

  @dataclass
  class PerformanceMetrics:
      schedule_id: str
      creator_id: str
      start_time: datetime = field(default_factory=datetime.now)
      phase_timings: dict[str, float] = field(default_factory=dict)
      query_count: int = 0
      cache_hits: int = 0
      cache_misses: int = 0

      def record_phase(self, phase: str, duration: float) -> None:
          self.phase_timings[phase] = duration

      @property
      def total_duration(self) -> float:
          return sum(self.phase_timings.values())

      @property
      def cache_hit_rate(self) -> float:
          total = self.cache_hits + self.cache_misses
          return self.cache_hits / total if total > 0 else 0.0

      def to_dict(self) -> dict:
          return {
              "schedule_id": self.schedule_id,
              "creator_id": self.creator_id,
              "total_duration_ms": self.total_duration * 1000,
              "phases": self.phase_timings,
              "cache_hit_rate": self.cache_hit_rate
          }
  ```

TASK 7.2.5: Set Performance Targets
- Location: Document in docs/PERFORMANCE.md
- Action: Define and track SLAs
  ```markdown
  # Performance Targets

  ## Response Time SLAs

  | Operation | Target | Current |
  |-----------|--------|---------|
  | get_creator_profile | <50ms | TBD |
  | get_top_captions | <100ms | TBD |
  | Full schedule generation | <5s | TBD |
  | save_schedule | <200ms | TBD |

  ## Throughput Targets

  - Schedule generations per minute: >10
  - Concurrent creator support: 37+
  - Database connections: 5 pooled
  ```
```

**Validation Criteria:**
- [ ] Full schedule generation <5 seconds
- [ ] Individual MCP calls <100ms
- [ ] Performance metrics tracked
- [ ] SLAs documented

---

## Wave 7 Completion Checklist

```markdown
□ DATABASE OPTIMIZATION
  □ All slow queries identified and optimized
  □ Missing indexes added
  □ WAL mode enabled
  □ Connection pooling implemented

□ CACHING
  □ Query result caching implemented
  □ Cache invalidation on writes
  □ >50% cache hit rate achieved

□ PERFORMANCE MONITORING
  □ Phase timing instrumentation added
  □ Metrics collection implemented
  □ Performance targets documented

□ VALIDATION
  □ All benchmarks passing
  □ <5s full schedule generation
  □ <100ms individual queries
```

---

# WAVE 8: FINAL VERIFICATION & POLISH

**Priority:** CRITICAL
**Estimated Duration:** 2-3 hours
**Dependencies:** Waves 1-7 Complete
**Risk Level:** LOW

## Objectives

1. Complete end-to-end validation of entire system
2. Verify schedule quality meets production standards
3. Certify production readiness
4. Create final audit report

## Agent Assignments

### Agent 8.1: code-reviewer

**Mission:** Final comprehensive code audit.

**Specific Tasks:**

```markdown
TASK 8.1.1: Full Codebase Security Audit
- Action: Re-run all security checks
- Verify all Wave 1 security measures in place
- Check for any regressions
- Sign off on security posture

TASK 8.1.2: Code Quality Final Check
- Action: Run all linters and type checkers
  ```bash
  mypy --strict python/ mcp/
  ruff check python/ mcp/
  black --check python/ mcp/
  ```
- Verify zero errors/warnings
- Document any accepted exceptions

TASK 8.1.3: Test Suite Validation
- Action: Run full test suite with coverage
  ```bash
  pytest --cov=python --cov=mcp --cov-report=html
  ```
- Verify >90% coverage maintained
- All tests passing

TASK 8.1.4: Documentation Accuracy Check
- Action: Verify all documentation matches implementation
- Check version numbers consistent
- Verify all links working
- Sign off on documentation completeness
```

---

### Agent 8.2: quality-validator

**Mission:** Validate schedule generation quality.

**Specific Tasks:**

```markdown
TASK 8.2.1: Generate Test Schedules for All Creators
- Action: Generate schedules for all 37+ active creators
- Run quality validation on each
- Document any failures

TASK 8.2.2: Validate Schedule Quality Metrics
- Action: For each generated schedule, verify:
  □ No duplicate captions within 7-day window
  □ All captions have freshness_score >= 30
  □ All captions have performance_score >= 40
  □ Minimum 45-minute spacing between sends
  □ No sends during avoid_hours
  □ Retention types only on paid pages
  □ VIP program max 1/week
  □ Snapchat bundle max 1/week
  □ PPV followups max 4/day

TASK 8.2.3: Edge Case Testing
- Action: Test edge cases:
  □ Creator with minimal captions
  □ Creator with zero history
  □ Free page schedule generation
  □ High-saturation creator
  □ Low-saturation creator
  □ All volume tiers (LOW/MID/HIGH/ULTRA)

TASK 8.2.4: Output Format Validation
- Action: Verify output matches expected schema
- Validate JSON structure
- Check all required fields present
- Verify database persistence correct
```

---

### Agent 8.3: multi-agent-coordinator

**Mission:** Certify production readiness.

**Specific Tasks:**

```markdown
TASK 8.3.1: System Integration Verification
- Action: End-to-end test of full system
  ```
  1. User invokes /eros:generate alexia
  2. Skill activates
  3. All 8 agents execute in sequence
  4. Schedule generated and validated
  5. Schedule saved to database
  6. Success response returned
  ```
- Document full flow completion

TASK 8.3.2: Create Final Audit Report
- Location: FINAL_AUDIT_REPORT.md
- Action: Document final state
  ```markdown
  # EROS Schedule Generator - Final Audit Report

  **Date:** 2025-12-XX
  **Version:** 2.0.0
  **Status:** PRODUCTION READY

  ## Executive Summary

  All 8 waves of the Perfection Execution Plan have been
  completed successfully.

  ## Final Scores

  | Component | Score |
  |-----------|-------|
  | Security | 100/100 |
  | Code Quality | 100/100 |
  | Architecture | 100/100 |
  | Documentation | 100/100 |
  | Test Coverage | 95/100 |
  | Performance | 100/100 |
  | **Overall** | **100/100** |

  ## Certification

  This system is certified for production use with the
  MAX 20X subscription tier.

  [Signatures/Timestamps]
  ```

TASK 8.3.3: Update CHANGELOG.md
- Action: Document all changes from execution plan
  ```markdown
  ## [2.1.0] - 2025-12-XX

  ### Security
  - Enhanced SQL injection protection with PRAGMA blocking
  - Added connection security pragmas
  - Implemented input validation decorators

  ### Code Quality
  - Fixed all type annotation errors (any → Any)
  - Implemented frozen dataclasses with slots
  - Added custom exception hierarchy
  - Configured structured logging

  ### Architecture
  - Modularized MCP server into 10+ focused modules
  - Implemented Send Type Registry pattern
  - Created unified domain model package
  - Externalized configuration to YAML

  ### Documentation
  - Created README.md with quick start
  - Added GETTING_STARTED.md tutorial
  - Created API_REFERENCE.md for all 17 tools
  - Fixed all cross-reference paths

  ### Testing
  - Fixed all broken test imports
  - Achieved >90% code coverage
  - Added integration tests
  - Created performance benchmarks

  ### Performance
  - Added composite indexes for common queries
  - Implemented query result caching
  - Added connection pooling
  - Achieved <5s schedule generation
  ```

TASK 8.3.4: Version Bump
- Action: Update version to 2.1.0 across all files
  - pyproject.toml
  - CLAUDE.md
  - SKILL.md
  - README.md
```

---

## Wave 8 Completion Checklist

```markdown
□ CODE AUDIT
  □ Security audit passed
  □ Type checking passed
  □ Linting passed
  □ Test suite passed (>90% coverage)

□ SCHEDULE QUALITY
  □ All 37+ creators tested
  □ Quality metrics validated
  □ Edge cases handled
  □ Output format verified

□ PRODUCTION READINESS
  □ End-to-end flow verified
  □ Final audit report created
  □ CHANGELOG.md updated
  □ Version bumped to 2.1.0

□ CERTIFICATION
  □ All waves completed
  □ 100/100 score achieved
  □ Production ready certified
```

---

# Appendix A: Agent Quick Reference

| Agent | Primary Use | Wave(s) |
|-------|-------------|---------|
| security-engineer | SQL protection, FK enforcement | 1 |
| database-administrator | Data integrity, maintenance | 1, 7 |
| python-pro | Type safety, tests | 2, 6 |
| code-reviewer | Code standards, quality gates | 2, 6, 8 |
| refactoring-pro | Architecture restructuring | 3 |
| backend-developer | Domain models, registry | 3 |
| command-architect | Agent/skill definitions | 4 |
| prompt-engineer | Prompt optimization | 4 |
| documentation-engineer | User documentation | 5 |
| technical-writer | Technical accuracy | 5 |
| database-optimizer | Query optimization | 7 |
| performance-analyst | Performance tuning | 7 |
| quality-validator | Schedule validation | 8 |
| multi-agent-coordinator | Integration, certification | 8 |

---

# Appendix B: File Change Summary

## Files to Create

| File | Wave | Purpose |
|------|------|---------|
| python/exceptions.py | 2 | Custom exception hierarchy |
| python/logging_config.py | 2 | Structured logging |
| python/validators.py | 2 | Input validation decorators |
| python/models/*.py | 3 | Domain model package |
| python/registry/send_type_registry.py | 3 | Send type singleton |
| python/config/settings.py | 3 | Configuration management |
| python/config/scheduling.yaml | 3 | External configuration |
| mcp/tools/*.py | 3 | Modularized MCP tools |
| mcp/protocol.py | 3 | JSON-RPC handling |
| mcp/connection.py | 3 | Database connection pool |
| mcp/utils/cache.py | 7 | Query caching |
| python/monitoring.py | 7 | Performance metrics |
| README.md | 5 | Project entry point |
| docs/GETTING_STARTED.md | 5 | Onboarding guide |
| docs/API_REFERENCE.md | 5 | MCP tool documentation |
| docs/GLOSSARY.md | 5 | Term definitions |
| docs/PERFORMANCE.md | 7 | Performance targets |
| database/migrations/README.md | 5 | Migration guide |
| FINAL_AUDIT_REPORT.md | 8 | Production certification |

## Files to Modify

| File | Wave | Changes |
|------|------|---------|
| mcp/eros_db_server.py | 1, 3 | Security + Modularization |
| python/allocation/send_type_allocator.py | 2, 3 | Types + Registry |
| python/matching/caption_matcher.py | 2 | Types + Constants |
| python/optimization/schedule_optimizer.py | 2 | Types + Constants |
| python/tests/test_core_algorithms.py | 6 | Fix imports |
| .claude/agents/*.md | 4 | Model specs + Triggers |
| CLAUDE.md | 4, 5 | Tools + Docs |
| SKILL.md | 4 | MAX 20X optimization |
| pyproject.toml | 6 | Coverage config |
| CHANGELOG.md | 8 | Version 2.1.0 |

---

# Appendix C: Estimated Timeline

| Wave | Duration | Cumulative |
|------|----------|------------|
| Wave 1: Critical Foundation | 2-3 hours | 2-3 hours |
| Wave 2: Type Safety | 3-4 hours | 5-7 hours |
| Wave 3: Architecture | 4-5 hours | 9-12 hours |
| Wave 4: Agents/Skills | 3-4 hours | 12-16 hours |
| Wave 5: Documentation | 3-4 hours | 15-20 hours |
| Wave 6: Testing | 4-5 hours | 19-25 hours |
| Wave 7: Performance | 2-3 hours | 21-28 hours |
| Wave 8: Verification | 2-3 hours | 23-31 hours |

**Total Estimated Duration: 23-31 hours**

---

# Appendix D: Success Metrics

## Quantitative Targets

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Code Coverage | ~50% | >90% | pytest-cov |
| Type Errors | 10+ | 0 | mypy --strict |
| Security Issues | 3 | 0 | Manual audit |
| Documentation Score | 82/100 | 100/100 | Audit checklist |
| Response Time | Unknown | <5s | Performance tests |
| Test Pass Rate | Unknown | 100% | pytest |

## Qualitative Targets

- [ ] All 37+ creators can have schedules generated on demand
- [ ] Schedule quality passes all validation checks
- [ ] System follows Claude Code 2025 best practices
- [ ] Documentation enables self-service usage
- [ ] Architecture supports future extension

---

**End of Perfection Execution Plan**

*This document serves as the authoritative guide for achieving 100% production perfection of the EROS Schedule Generator system.*
