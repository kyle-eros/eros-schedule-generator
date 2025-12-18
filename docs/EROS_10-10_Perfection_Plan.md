# EROS Schedule Generator - 10/10 Perfection Plan

**Project**: EROS Schedule Generator Pipeline v2.2.0
**Created**: December 17, 2025
**Author**: Claude Code Audit Team
**Status**: Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Component Scores](#component-scores)
3. [Component 1: Skill Documentation](#component-1-skill-documentation-85--1010)
4. [Component 2: Agent Definitions](#component-2-agent-definitions-81--1010)
5. [Component 3: Slash Commands](#component-3-slash-commands-75--1010)
6. [Component 4: Python Code](#component-4-python-code-92--1010)
7. [Component 5: MCP Server](#component-5-mcp-server-90--1010)
8. [Component 6: Database Quality](#component-6-database-quality-93--1010)
9. [Implementation Phases](#implementation-phases)
10. [Success Criteria](#success-criteria)
11. [Time Estimates](#time-estimates)

---

## Executive Summary

This plan outlines **46 specific tasks** across **6 components** to bring the EROS Schedule Generator Pipeline from its current state to production-perfect 10/10 quality. The work is organized into 5 implementation phases, prioritized by impact and complexity.

**Key Statistics**:
- Total Tasks: 46
- Files to Modify: 35+
- Estimated Time: ~7.5 hours
- Expected Improvement: +5.3 points total

---

## Component Scores

| Component | Current | Target | Gap | Tasks |
|-----------|---------|--------|-----|-------|
| Skill Documentation | 8.5/10 | 10/10 | 1.5 | 8 |
| Agent Definitions | 8.1/10 | 10/10 | 1.9 | 13 |
| Slash Commands | 7.5/10 | 10/10 | 2.5 | 8 |
| Python Code | 9.2/10 | 10/10 | 0.8 | 6 |
| MCP Server | 9.0/10 | 10/10 | 1.0 | 6 |
| Database Quality | 9.3/10 | 10/10 | 0.7 | 5 |
| **TOTAL** | **52.1/60** | **60/60** | **7.9** | **46** |

---

## Component 1: Skill Documentation (8.5 → 10/10)

### Files to Modify (11 files)

| File | Path |
|------|------|
| SKILL.md | `.claude/skills/eros-schedule-generator/SKILL.md` |
| ORCHESTRATION.md | `.claude/skills/eros-schedule-generator/ORCHESTRATION.md` |
| SEND_TYPES.md | `.claude/skills/eros-schedule-generator/SEND_TYPES.md` |
| DATA_CONTRACTS.md | `.claude/skills/eros-schedule-generator/DATA_CONTRACTS.md` |
| OPTIMIZATION_WEIGHTS.md | `.claude/skills/eros-schedule-generator/OPTIMIZATION_WEIGHTS.md` |
| MATCHING_HEURISTICS.md | `.claude/skills/eros-schedule-generator/MATCHING_HEURISTICS.md` |
| FOLLOWUP_PATTERNS.md | `.claude/skills/eros-schedule-generator/FOLLOWUP_PATTERNS.md` |
| TARGETING_GUIDE.md | `.claude/skills/eros-schedule-generator/TARGETING_GUIDE.md` |
| HELPERS.md | `.claude/skills/eros-schedule-generator/HELPERS.md` |
| ALLOCATION_RULES.md | `.claude/skills/eros-schedule-generator/ALLOCATION_RULES.md` |
| ALLOCATION_ALGORITHM.md | `.claude/skills/eros-schedule-generator/ALLOCATION_ALGORITHM.md` |

### Tasks (8 items)

- [ ] **1.1 Fix SEND_TYPES.md numbering** (+0.2)
  - Change engagement section to start at "10. link_drop" instead of "8."
  - Use consistent 1-22 sequential numbering throughout

- [ ] **1.2 Add tip_goal_non_tippers to DATA_CONTRACTS.md** (+0.2)
  - Add `tip_goal_non_tippers` to TargetKey type union
  - OR clarify it's an alias for `non_tippers`

- [ ] **1.3 Standardize caption scoring weights** (+0.2)
  - Update MATCHING_HEURISTICS.md to use 40/35/15/5/5 weights
  - Update SKILL.md to match ORCHESTRATION.md weights

- [ ] **1.4 Fix jitter range inconsistency** (+0.1)
  - Update ORCHESTRATION.md line 1238 from `-10 to +10` to `-7 to +8`

- [ ] **1.5 Verify python/helpers/ path in HELPERS.md** (+0.1)
  - Update reference path to actual codebase structure

- [ ] **1.6 Add version history entries** (+0.2)
  - Add entries for v1.6.0 through v1.9.0
  - Document all changes made in 2025

- [ ] **1.7 Update MATCHING_HEURISTICS.md for 22 types** (+0.3)
  - Ensure all timing preference tables cover 22 types
  - Add ppv_wall and tip_goal entries

- [ ] **1.8 Add ppv_message deprecation migration note** (+0.2)
  - Add migration note in ORCHESTRATION.md Phase 2
  - Set removal date reminder for 2025-01-16

---

## Component 2: Agent Definitions (8.1 → 10/10)

### Files to Modify (9 files)

| File | Path |
|------|------|
| performance-analyst.md | `.claude/agents/performance-analyst.md` |
| send-type-allocator.md | `.claude/agents/send-type-allocator.md` |
| content-curator.md | `.claude/agents/content-curator.md` |
| audience-targeter.md | `.claude/agents/audience-targeter.md` |
| timing-optimizer.md | `.claude/agents/timing-optimizer.md` |
| followup-generator.md | `.claude/agents/followup-generator.md` |
| schedule-assembler.md | `.claude/agents/schedule-assembler.md` |
| quality-validator.md | `.claude/agents/quality-validator.md` |
| caption-optimizer.md | `.claude/agents/caption-optimizer.md` |

### Tasks (13 items)

- [ ] **2.1 Define all undefined helper functions** (+0.5)

  Add to each agent or central HELPERS.md:
  | Function | Used In |
  |----------|---------|
  | `parse_time()` | timing-optimizer, followup-generator |
  | `weighted_select()` | send-type-allocator |
  | `interleave_categories()` | send-type-allocator |
  | `calculate_freshness()` | content-curator |
  | `calculate_performance()` | content-curator |
  | `determine_media_type()` | schedule-assembler |
  | `count_items_by_day()` | quality-validator |

- [ ] **2.2 Add error handling section to performance-analyst.md** (+0.15)
  - Handle empty `get_performance_trends` response
  - Add timeout/retry guidance
  - Define fallback for insufficient historical data

- [ ] **2.3 Add error handling section to audience-targeter.md** (+0.15)
  - Handle invalid `target_key` values
  - Handle missing page_type
  - Add batch optimization guidance

- [ ] **2.4 Add error handling section to timing-optimizer.md** (+0.1)
  - Add conflict resolution docs
  - Add timezone handling guidance
  - Add DST transition handling

- [ ] **2.5 Consolidate EXPIRATION_RULES constant** (+0.1)
  - Move to single authoritative location (HELPERS.md or DATA_CONTRACTS.md)
  - Remove duplicate in schedule-assembler.md

- [ ] **2.6 Clarify caption-optimizer.md role** (+0.2)
  - Add phase number OR mark as "Optional Utility Agent"
  - Add invocation triggers
  - Add to SKILL.md agent list if required

- [ ] **2.7 Add rollback strategy to schedule-assembler.md** (+0.1)
  - Document rollback if save_schedule fails
  - Add partial failure handling

- [ ] **2.8 Add remediation guidance to quality-validator.md** (+0.15)
  - Add fix suggestions for each validation failure
  - Document NEEDS_REVIEW action procedures

- [ ] **2.9 Fix code example variable definitions** (+0.1)
  - Define `volume_triggers` before use in performance-analyst
  - Define `winners_detected` before use
  - Fix `datetime` import in schedule-assembler

- [ ] **2.10 Add daily limit enforcement to followup-generator.md** (+0.1)
  - Add explicit max 4/day enforcement in algorithm
  - Add parent item deletion handling

- [ ] **2.11 Document ppv_structure_rotation_state table** (+0.1)
  - Add schema documentation
  - Add usage examples

- [ ] **2.12 Add batch optimization to audience-targeter.md** (+0.05)
  - Document single call vs per-item efficiency

- [ ] **2.13 Fix JSON formatting issues** (+0.05)
  - Fix followup-generator.md output JSON (line 472)
  - Verify all JSON examples are syntactically valid

---

## Component 3: Slash Commands (7.5 → 10/10)

### Files to Modify (4 files)

| File | Path |
|------|------|
| generate.md | `.claude/commands/eros/generate.md` |
| analyze.md | `.claude/commands/eros/analyze.md` |
| creators.md | `.claude/commands/eros/creators.md` |
| validate.md | `.claude/commands/eros/validate.md` |

### Tasks (8 items)

- [ ] **3.1 Add output format to analyze.md** (+0.4)
  - Document expected JSON output structure
  - Add example analysis output with all fields

- [ ] **3.2 Add error handling docs to all commands** (+0.5)
  - Invalid creator_id handling
  - Database connection failures
  - MCP tool timeout handling

- [ ] **3.3 Fix freshness threshold in validate.md** (+0.2)
  - Fix calculation: 7 days × 2 = 14, score = 86, not < 85
  - Update threshold to `< 86` OR adjust multiplier

- [ ] **3.4 Enhance argument hints** (+0.3)
  - Change `<creator_id>` to `<creator_id_or_name>`
  - Add example values in hints

- [ ] **3.5 Add comprehensive examples to each command** (+0.4)
  - Add 3+ example usages per command
  - Include edge case examples

- [ ] **3.6 Add validation rules documentation** (+0.3)
  - Document parameter validation rules
  - List valid enum values explicitly

- [ ] **3.7 Add performance expectations** (+0.2)
  - Expected execution time per command
  - Resource usage notes

- [ ] **3.8 Add cross-references between commands** (+0.2)
  - Link related commands
  - Document typical workflow sequences

---

## Component 4: Python Code (9.2 → 10/10)

### Focus Areas

| Directory | Contents |
|-----------|----------|
| `python/` | 95 Python modules |
| `python/tests/` | 34 test files |

### Tasks (6 items)

- [ ] **4.1 Increase test coverage to 80%** (+0.3)
  - Currently at 60% threshold
  - Add tests for edge cases
  - Add negative test cases

- [ ] **4.2 Add integration tests** (+0.2)
  - End-to-end schedule generation tests
  - Database integration tests
  - MCP tool integration tests

- [ ] **4.3 Add performance benchmarks** (+0.1)
  - Add benchmark tests for critical paths
  - Document performance baselines

- [ ] **4.4 Add missing docstrings** (+0.1)
  - Ensure all public functions have docstrings
  - Use Google-style consistently

- [ ] **4.5 Add observability hooks** (+0.05)
  - Add logging instrumentation
  - Add metrics collection points

- [ ] **4.6 Fix any remaining mypy warnings** (+0.05)
  - Ensure 100% type hint coverage
  - Resolve any remaining warnings

---

## Component 5: MCP Server (9.0 → 10/10)

### Focus Areas

| Directory | Contents |
|-----------|----------|
| `mcp/eros_db_server.py` | Main server (99 KB) |
| `mcp/tools/` | 9 tool modules |
| `mcp/test_*.py` | 5 test files |

### Tasks (6 items)

- [ ] **5.1 Add comprehensive API documentation** (+0.3)
  - Add docstrings to all tool functions
  - Add return type documentation
  - Add error code documentation

- [ ] **5.2 Add load/stress testing** (+0.2)
  - Add concurrent request tests
  - Add performance benchmarks
  - Document capacity limits

- [ ] **5.3 Add edge case tests** (+0.2)
  - Test all error conditions
  - Test boundary values
  - Test concurrent access

- [ ] **5.4 Add Prometheus metrics** (+0.15)
  - Response time metrics
  - Error rate metrics
  - Connection pool metrics

- [ ] **5.5 Optimize connection pooling** (+0.1)
  - Review pool size configuration
  - Add connection health checks

- [ ] **5.6 Add request/response logging** (+0.05)
  - Add structured logging
  - Add request tracing

---

## Component 6: Database Quality (9.3 → 10/10)

### Focus Areas

| Directory | Contents |
|-----------|----------|
| `database/eros_sd_main.db` | Production database (250MB) |
| `database/migrations/` | Migration scripts |
| `database/audit/` | Quality reports (93/100) |

### Tasks (5 items)

- [ ] **6.1 Create deployment playbook** (+0.2)
  - Step-by-step deployment checklist
  - Rollback procedures
  - Health check commands

- [ ] **6.2 Document backup/recovery strategy** (+0.2)
  - Daily backup schedule
  - Point-in-time recovery procedure
  - Test restore monthly

- [ ] **6.3 Add monitoring dashboard setup** (+0.15)
  - Database health metrics
  - Query performance monitoring
  - Alert thresholds

- [ ] **6.4 Document remaining schema elements** (+0.1)
  - ppv_structure_rotation_state table
  - Any undocumented tables/columns

- [ ] **6.5 Add performance tuning guide** (+0.05)
  - Index optimization recommendations
  - Query optimization tips
  - Vacuum/analyze schedule

---

## Implementation Phases

### Phase 1: Quick Wins (30 minutes)

**Goal**: Close obvious gaps with immediate fixes

| Task ID | Description | Points |
|---------|-------------|--------|
| 1.1 | Fix SEND_TYPES.md numbering | +0.2 |
| 1.4 | Fix jitter range inconsistency | +0.1 |
| 1.2 | Add missing TargetKey to DATA_CONTRACTS.md | +0.2 |
| 3.3 | Fix validate.md freshness threshold | +0.2 |

**Phase 1 Total**: +0.7 points

---

### Phase 2: Agent Perfection (1-2 hours)

**Goal**: Define all helper functions and add error handling

| Task ID | Description | Points |
|---------|-------------|--------|
| 2.1 | Define all undefined helper functions | +0.5 |
| 2.2 | Add error handling to performance-analyst | +0.15 |
| 2.3 | Add error handling to audience-targeter | +0.15 |
| 2.4 | Add error handling to timing-optimizer | +0.1 |
| 2.5 | Consolidate EXPIRATION_RULES constant | +0.1 |
| 2.6 | Clarify caption-optimizer.md role | +0.2 |
| 2.7 | Add rollback strategy to schedule-assembler | +0.1 |
| 2.8 | Add remediation guidance to quality-validator | +0.15 |
| 2.9 | Fix code example variable definitions | +0.1 |
| 2.10 | Add daily limit enforcement to followup-generator | +0.1 |
| 2.11 | Document ppv_structure_rotation_state table | +0.1 |
| 2.12 | Add batch optimization to audience-targeter | +0.05 |
| 2.13 | Fix JSON formatting issues | +0.05 |

**Phase 2 Total**: +1.85 points

---

### Phase 3: Documentation Enhancement (1 hour)

**Goal**: Improve slash commands and skill documentation

| Task ID | Description | Points |
|---------|-------------|--------|
| 3.1 | Add output format to analyze.md | +0.4 |
| 3.2 | Add error handling docs to all commands | +0.5 |
| 3.4 | Enhance argument hints | +0.3 |
| 3.5 | Add comprehensive examples | +0.4 |
| 3.6 | Add validation rules documentation | +0.3 |
| 3.7 | Add performance expectations | +0.2 |
| 3.8 | Add cross-references between commands | +0.2 |
| 1.3 | Standardize caption scoring weights | +0.2 |
| 1.6 | Add version history entries | +0.2 |
| 1.7 | Update MATCHING_HEURISTICS.md for 22 types | +0.3 |
| 1.8 | Add ppv_message deprecation note | +0.2 |

**Phase 3 Total**: +3.2 points

---

### Phase 4: Code Quality (2-3 hours)

**Goal**: Increase test coverage and add observability

| Task ID | Description | Points |
|---------|-------------|--------|
| 4.1 | Increase test coverage to 80% | +0.3 |
| 4.2 | Add integration tests | +0.2 |
| 4.3 | Add performance benchmarks | +0.1 |
| 4.4 | Add missing docstrings | +0.1 |
| 4.5 | Add observability hooks | +0.05 |
| 4.6 | Fix remaining mypy warnings | +0.05 |
| 5.1 | Add comprehensive API documentation | +0.3 |
| 5.2 | Add load/stress testing | +0.2 |
| 5.3 | Add edge case tests | +0.2 |
| 5.4 | Add Prometheus metrics | +0.15 |
| 5.5 | Optimize connection pooling | +0.1 |
| 5.6 | Add request/response logging | +0.05 |

**Phase 4 Total**: +1.8 points

---

### Phase 5: Infrastructure (1 hour)

**Goal**: Database and operational improvements

| Task ID | Description | Points |
|---------|-------------|--------|
| 6.1 | Create deployment playbook | +0.2 |
| 6.2 | Document backup/recovery strategy | +0.2 |
| 6.3 | Add monitoring dashboard setup | +0.15 |
| 6.4 | Document remaining schema elements | +0.1 |
| 6.5 | Add performance tuning guide | +0.05 |
| 1.5 | Verify python/helpers/ path | +0.1 |

**Phase 5 Total**: +0.8 points

---

## Success Criteria

All components must pass these verification checks:

- [ ] Zero inconsistencies between related files
- [ ] All helper functions defined with implementations
- [ ] Error handling documented for all 8 agents
- [ ] Test coverage ≥ 80%
- [ ] All JSON examples syntactically valid
- [ ] All 22 send types documented consistently everywhere
- [ ] All 17 MCP tools have comprehensive documentation
- [ ] Deployment and operations playbooks exist and are tested

---

## Time Estimates

| Phase | Description | Time | Points |
|-------|-------------|------|--------|
| 1 | Quick Wins | 30 min | +0.7 |
| 2 | Agent Perfection | 2 hrs | +1.85 |
| 3 | Documentation Enhancement | 1 hr | +3.2 |
| 4 | Code Quality | 3 hrs | +1.8 |
| 5 | Infrastructure | 1 hr | +0.8 |
| **TOTAL** | **All Phases** | **~7.5 hrs** | **+8.35** |

---

## Expected Final Scores

| Component | Before | After |
|-----------|--------|-------|
| Skill Documentation | 8.5/10 | **10/10** |
| Agent Definitions | 8.1/10 | **10/10** |
| Slash Commands | 7.5/10 | **10/10** |
| Python Code | 9.2/10 | **10/10** |
| MCP Server | 9.0/10 | **10/10** |
| Database Quality | 9.3/10 | **10/10** |

---

*Plan generated by Claude Code Audit Team - December 17, 2025*
