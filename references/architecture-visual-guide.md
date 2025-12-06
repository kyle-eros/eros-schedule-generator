# EROS Schedule Generator v2.0
## Visual Architecture Guide

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    EROS Schedule Generator v2.0                               ║
║                    Visual Architecture Documentation                          ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Version: 2.0.0  │  Scripts: 23  │  Lines: 23,650  │  Sub-Agents: 7          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [File Structure Tree](#2-file-structure-tree)
3. [12-Step Pipeline Flow Diagram](#3-12-step-pipeline-flow-diagram)
4. [Script Interaction Map](#4-script-interaction-map)
5. [Sub-Agent Orchestration](#5-sub-agent-orchestration)
6. [Database Entity Relationships](#6-database-entity-relationships)
7. [Data Flow: Request to Schedule](#7-data-flow-request-to-schedule)
8. [Symbol Legend](#8-symbol-legend)

---

## 1. System Architecture Overview

A three-layer architecture for automated PPV schedule generation.

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         SYSTEM ARCHITECTURE                                   ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ╭─────────────────────────────────────────────────────────────────────╮    ║
║   │                    📱 PRESENTATION LAYER                            │    ║
║   │                Claude Code Skill Interface                          │    ║
║   │  ┌─────────────────────────────────────────────────────────────┐   │    ║
║   │  │  Trigger: "Generate schedule for [creator]"                 │   │    ║
║   │  │  Entry Points:                                              │   │    ║
║   │  │    • generate_schedule.py (Quick Mode, <30s)                │   │    ║
║   │  │    • prepare_llm_context.py (Full Mode, <60s)               │   │    ║
║   │  └─────────────────────────────────────────────────────────────┘   │    ║
║   ╰───────────────────────────────────┬─────────────────────────────────╯    ║
║                                       │                                      ║
║                                       ▼                                      ║
║   ╭─────────────────────────────────────────────────────────────────────╮    ║
║   │                    ⚙️  PROCESSING LAYER                             │    ║
║   │                  12-Step Schedule Pipeline                          │    ║
║   │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │    ║
║   │  │   ANALYZE    │►│MATCH CONTENT │►│MATCH PERSONA │►│   BUILD    │ │    ║
║   │  │   Step 1     │ │   Step 2     │ │   Step 3     │ │  Step 4    │ │    ║
║   │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │    ║
║   │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │    ║
║   │  │   QUALITY    │►│   ASSIGN     │►│ FOLLOW-UPS   │►│   DRIP     │ │    ║
║   │  │  Step 4B*    │ │   Step 5     │ │   Step 6     │ │  Step 7    │ │    ║
║   │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │    ║
║   │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    ║
║   │  │   ENHANCE    │►│ PAGE TYPE    │►│  VALIDATE    │  * Full Mode  │    ║
║   │  │  Step 7B*    │ │   Step 8     │ │   Step 9     │    Only       │    ║
║   │  └──────────────┘ └──────────────┘ └──────────────┘                │    ║
║   ╰───────────────────────────────────┬─────────────────────────────────╯    ║
║                                       │                                      ║
║                                       ▼                                      ║
║   ╭─────────────────────────────────────────────────────────────────────╮    ║
║   │                       💾 DATA LAYER                                 │    ║
║   │                    SQLite Database + Cache                          │    ║
║   │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐       │    ║
║   │  │   creators      │ │  caption_bank   │ │  mass_messages  │       │    ║
║   │  │   (36 records)  │ │  (19,590 recs)  │ │   (66,826 recs) │       │    ║
║   │  └─────────────────┘ └─────────────────┘ └─────────────────┘       │    ║
║   │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐       │    ║
║   │  │ creator_personas│ │  vault_matrix   │ │  content_types  │       │    ║
║   │  │   (35 records)  │ │  (1,188 recs)   │ │   (33 records)  │       │    ║
║   │  └─────────────────┘ └─────────────────┘ └─────────────────┘       │    ║
║   ╰─────────────────────────────────────────────────────────────────────╯    ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### Layer Responsibilities

| Layer | Purpose | Components |
|-------|---------|------------|
| **Presentation** | Skill invocation, mode selection | SKILL.md trigger, CLI arguments |
| **Processing** | 12-step pipeline execution | 23 Python scripts, 7 sub-agents |
| **Data** | Persistence, caching | SQLite database, agent cache |

---

## 2. File Structure Tree

Complete package organization with 23 Python scripts.

```
📁 eros-schedule-generator/
│
├── 📄 SKILL.md ──────────────────────────── Skill Definition (633 lines)
│   │                                        ├─ Trigger phrases
│   │                                        ├─ 12-step pipeline docs
│   │                                        ├─ Semantic analysis guidelines
│   │                                        └─ Business rules reference
│
├── 📄 README.md ─────────────────────────── Project Documentation (612 lines)
│
├── 📄 INTEGRATED_AGENTS.md ──────────────── Agent Orchestration (384 lines)
│
├── 📁 scripts/ ──────────────────────────── Python Scripts (23 files, 23,650 lines)
│   │
│   │  # Core Pipeline (Steps 1-9)
│   ├── generate_schedule.py ─────────────── Main Orchestrator (2,153 lines)
│   ├── analyze_creator.py ───────────────── Step 1: ANALYZE (943 lines)
│   ├── select_captions.py ───────────────── Step 2: MATCH CONTENT (645 lines)
│   ├── match_persona.py ─────────────────── Step 3: MATCH PERSONA (894 lines)
│   ├── volume_optimizer.py ──────────────── Step 4: BUILD STRUCTURE (1,179 lines)
│   ├── calculate_freshness.py ───────────── Step 5: ASSIGN support (519 lines)
│   ├── followup_generator.py ────────────── Step 6: FOLLOW-UPS (1,059 lines)
│   ├── validate_schedule.py ─────────────── Step 9: VALIDATE (603 lines)
│   │
│   │  # LLM Enhancement (Full Mode)
│   ├── prepare_llm_context.py ───────────── Full Mode Entry (806 lines)
│   ├── quality_scoring.py ───────────────── Step 4B: QUALITY (1,287 lines)
│   ├── caption_enhancer.py ──────────────── Step 7B: ENHANCE (1,388 lines)
│   ├── semantic_analysis.py ─────────────── Tone Detection (735 lines)
│   ├── apply_llm_insights.py ────────────── LLM Integration (701 lines)
│   │
│   │  # Infrastructure & Utilities
│   ├── agent_invoker.py ─────────────────── Sub-Agent Framework (605 lines)
│   ├── shared_context.py ────────────────── Shared Dataclasses (191 lines)
│   ├── utils.py ─────────────────────────── VoseAliasSelector (183 lines)
│   ├── logging_config.py ────────────────── Logging Setup (119 lines)
│   ├── content_type_loaders.py ──────────── Content Loading (385 lines)
│   ├── content_type_schedulers.py ───────── Content Scheduling (486 lines)
│   │
│   │  # Analysis & Reporting
│   ├── batch_portfolio_analysis.py ──────── Portfolio Audit (5,737 lines)
│   ├── volume_validation_report.py ──────── Volume Reports (851 lines)
│   ├── verify_deployment.py ─────────────── Deployment Check (321 lines)
│   │
│   │  # Testing
│   └── test_volume_optimizer.py ─────────── Test Suite (2,183 lines)
│
├── 📁 references/ ───────────────────────── Technical Documentation (11 files)
│   ├── architecture.md ──────────────────── Pipeline Architecture (725 lines)
│   ├── architecture-visual-guide.md ─────── This File
│   ├── database-schema.md ───────────────── Database Reference (1,107 lines)
│   ├── scheduling_rules.md ──────────────── Business Rules (542 lines)
│   └── [7 more reference docs]
│
├── 📁 assets/
│   ├── sql/ ─────────────────────────────── Core SQL Queries (6 files)
│   └── sql/batch_analysis/ ──────────────── Portfolio Queries (10 files)
│
└── 📁 tests/ ────────────────────────────── Test Suite
    └── test_*.py
```

---

## 3. 12-Step Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    EROS 12-STEP EXTENDED PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   INPUT                                                                         │
│   ┌──────────────────┐                                                          │
│   │ • creator_id     │     MODE SELECTION                                       │
│   │ • week (YYYY-Www)│     ┌─────────────────────────────────────┐              │
│   │ • mode           │────►│ Quick: generate_schedule.py         │              │
│   │   (quick/full)   │     │ Full:  prepare_llm_context.py       │              │
│   └──────────────────┘     └─────────────────┬───────────────────┘              │
│                                              │                                  │
│   ═══════════════════════════════════════════╪══════════════════════════════    │
│   PHASE 1: DATA GATHERING                    ▼                                  │
│   ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                 │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 1: ANALYZE                                                       │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ • Load creator profile from database                            │   │     │
│   │ │ • Calculate 30-90 day performance metrics                       │   │     │
│   │ │ • Determine volume tier (Base/Growth/Scale/High/Ultra)          │   │     │
│   │ │ • Load persona (tone, emoji frequency, slang level)             │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│                                              ▼                                  │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 2: MATCH CONTENT                                                 │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ • Query caption_bank for available captions                     │   │     │
│   │ │ • Filter by vault_matrix availability                           │   │     │
│   │ │ • Enforce freshness >= 30 threshold                             │   │     │
│   │ │ • Remove recently used captions                                 │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│                                              ▼                                  │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 3: MATCH PERSONA                                                 │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ • Calculate persona_boost for each caption (1.0-1.4x)           │   │     │
│   │ │ • Match primary tone (+0.20)                                    │   │     │
│   │ │ • Match emoji frequency (+0.05)                                 │   │     │
│   │ │ • Match slang level (+0.05)                                     │   │     │
│   │ │ • Sentiment alignment (+0.05)                                   │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│   ═══════════════════════════════════════════╪══════════════════════════════    │
│   PHASE 2: SCHEDULE BUILDING                 ▼                                  │
│   ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                 │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 4: BUILD STRUCTURE                                               │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ • Create 7-day time slot matrix                                 │   │     │
│   │ │ • Apply volume tier (2-6 PPV/day)                               │   │     │
│   │ │ • Optimize for peak hours (6PM, 9PM, 11PM)                      │   │     │
│   │ │ • Enforce 4-hour spacing between PPVs                           │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│                              ┌───────────────┴───────────────┐                  │
│                              │                               │                  │
│                         FULL MODE                       QUICK MODE              │
│                              │                               │                  │
│                              ▼                               │                  │
│   ┌──────────────────────────────────────────────┐           │                  │
│   │ STEP 4B: QUALITY SCORING (Full Mode Only)    │           │                  │
│   │ ┌────────────────────────────────────────┐   │           │                  │
│   │ │ • LLM evaluates each caption            │   │           │                  │
│   │ │ • Authenticity (35% weight)             │   │           │                  │
│   │ │ • Hook Strength (25%)                   │   │           │                  │
│   │ │ • CTA Effectiveness (20%)               │   │           │                  │
│   │ │ • Conversion Potential (20%)            │   │           │                  │
│   │ └────────────────────────────────────────┘   │           │                  │
│   └──────────────────────────────────────────────┘           │                  │
│                              │                               │                  │
│                              └───────────────┬───────────────┘                  │
│                                              │                                  │
│                                              ▼                                  │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 5: ASSIGN CAPTIONS                                               │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ • Calculate final weight per caption                            │   │     │
│   │ │   Quick: (perf×0.6 + fresh×0.4) × persona_boost                 │   │     │
│   │ │   Full:  (perf×0.4 + fresh×0.2 + quality×0.4) × boost           │   │     │
│   │ │ • Vose Alias weighted random selection (O(1))                   │   │     │
│   │ │ • Assign captions to time slots                                 │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│   ═══════════════════════════════════════════╪══════════════════════════════    │
│   PHASE 3: FOLLOW-UPS & ADJUSTMENTS          ▼                                  │
│   ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                 │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 6: GENERATE FOLLOW-UPS                                           │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ • Create bump messages for PPVs (perf_score >= 60)              │   │     │
│   │ │ • Timing: 15-45 minutes after parent PPV                        │   │     │
│   │ │ • Context-aware: content type, price, time of day               │   │     │
│   │ │ • Match creator's tone and emoji style                          │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│                                              ▼                                  │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 7: APPLY DRIP WINDOWS                                            │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ • Identify drip content time slots                              │   │     │
│   │ │ • Enforce 4-8 hour no-PPV zones after drips                     │   │     │
│   │ │ • Bumps ARE allowed within drip windows                         │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│                              ┌───────────────┴───────────────┐                  │
│                              │                               │                  │
│                         FULL MODE                       QUICK MODE              │
│                              │                               │                  │
│                              ▼                               │                  │
│   ┌──────────────────────────────────────────────┐           │                  │
│   │ STEP 7B: CAPTION ENHANCEMENT (Full Only)     │           │                  │
│   │ ┌────────────────────────────────────────┐   │           │                  │
│   │ │ • Add contractions ("don't" not "do not") │  │           │                  │
│   │ │ • Calibrate emoji frequency             │   │           │                  │
│   │ │ • Adjust slang level to match persona   │   │           │                  │
│   │ │ • Max 15% length change (safety)        │   │           │                  │
│   │ └────────────────────────────────────────┘   │           │                  │
│   └──────────────────────────────────────────────┘           │                  │
│                              │                               │                  │
│                              └───────────────┬───────────────┘                  │
│                                              │                                  │
│   ═══════════════════════════════════════════╪══════════════════════════════    │
│   PHASE 4: FINALIZATION                      ▼                                  │
│   ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                 │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 8: APPLY PAGE TYPE RULES                                         │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ • Paid page: Standard pricing matrix                            │   │     │
│   │ │ • Free page: Higher PPV frequency, lower prices                 │   │     │
│   │ │ • Adjust volume levels accordingly                              │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│                                              ▼                                  │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 9: VALIDATE & RETURN                                             │     │
│   │ ┌─────────────────────────────────────────────────────────────────┐   │     │
│   │ │ VALIDATION RULES (15+)                                          │   │     │
│   │ │ ✓ PPV spacing >= 3 hours (ERROR if violated)                    │   │     │
│   │ │ ✓ All captions freshness >= 30                                  │   │     │
│   │ │ ✓ Content types match vault availability                        │   │     │
│   │ │ ✓ Follow-ups 15-45 min after parent PPV                         │   │     │
│   │ │ ✓ No PPVs within drip windows                                   │   │     │
│   │ │ ✓ Daily PPV count matches volume tier                           │   │     │
│   │ │ ✓ No duplicate captions in same week                            │   │     │
│   │ │ ✓ No same content type 3x consecutive                           │   │     │
│   │ └─────────────────────────────────────────────────────────────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                              │                                  │
│                                              ▼                                  │
│   OUTPUT                                                                        │
│   ┌──────────────────┐                                                          │
│   │ List[ScheduleItem]                                                          │
│   │ • item_type (ppv/bump/drip/wall_post)                                       │
│   │ • send_time (datetime)                                                      │
│   │ • caption_text                                                              │
│   │ • content_type                                                              │
│   │ • price                                                                     │
│   │ • persona_boost                                                             │
│   │                                                                             │
│   │ ValidationReport                                                            │
│   │ • errors: List[ValidationIssue]                                             │
│   │ • warnings: List[ValidationIssue]                                           │
│   │ • info: List[ValidationIssue]                                               │
│   └──────────────────┘                                                          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Script Interaction Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       SCRIPT DEPENDENCY MAP                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │         generate_schedule.py        │
                    │           (ORCHESTRATOR)            │
                    │         2,153 lines | Steps 1-9     │
                    └──────────────────┬──────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────┐              ┌───────────────┐              ┌───────────────┐
│analyze_creator│              │select_captions│              │ match_persona │
│    .py        │              │     .py       │              │     .py       │
│   Step 1      │              │   Step 2      │              │   Step 3      │
│  943 lines    │              │  645 lines    │              │  894 lines    │
└───────────────┘              └───────┬───────┘              └───────────────┘
                                       │
                                       ▼
                               ┌───────────────┐
                               │    utils.py   │
                               │VoseAliasSelector│
                               │  183 lines    │
                               └───────────────┘
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────┐              ┌───────────────┐              ┌───────────────┐
│volume_optimizer│             │calculate_     │              │followup_      │
│     .py       │              │freshness.py   │              │generator.py   │
│   Step 4      │              │  Step 5 help  │              │   Step 6      │
│ 1,179 lines   │              │  519 lines    │              │ 1,059 lines   │
└───────────────┘              └───────────────┘              └───────────────┘
                                       │
                                       ▼
                               ┌───────────────┐
                               │validate_      │
                               │schedule.py    │
                               │   Step 9      │
                               │  603 lines    │
                               └───────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                    OPTIONAL MODULES (Full Mode)                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────┬──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────────┐          ┌───────────────────┐          ┌───────────────────┐
│prepare_llm_context│          │  quality_scoring  │          │ caption_enhancer  │
│       .py         │          │       .py         │          │       .py         │
│  Full Mode Entry  │          │    Step 4B        │          │    Step 7B        │
│    806 lines      │          │   1,287 lines     │          │   1,388 lines     │
└─────────┬─────────┘          └───────────────────┘          └───────────────────┘
          │
          ▼
┌───────────────────┐          ┌───────────────────┐
│ semantic_analysis │          │ apply_llm_insights│
│       .py         │          │       .py         │
│  Tone Detection   │          │  LLM Integration  │
│    735 lines      │          │    701 lines      │
└───────────────────┘          └───────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SUB-AGENT FRAMEWORK                                          │
└─────────────────────────────────────────────────────────────────────────────────┘

                               ┌───────────────────┐
                               │  agent_invoker.py │
                               │   605 lines       │
                               └─────────┬─────────┘
                                         │
        ┌────────────┬────────────┬──────┴──────┬────────────┬────────────┐
        │            │            │             │            │            │
        ▼            ▼            ▼             ▼            ▼            ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │timezone-│ │content- │ │volume-  │   │revenue- │ │multi-   │ │validatn-│
   │optimizer│ │strategy-│ │calibratr│   │optimizer│ │touch-   │ │guardian │
   │ (haiku) │ │optimizer│ │(sonnet) │   │(sonnet) │ │sequencer│ │(sonnet) │
   └─────────┘ │(sonnet) │ └─────────┘   └─────────┘ │ (opus)  │ └─────────┘
               └─────────┘                           └─────────┘
```

---

## 5. Sub-Agent Orchestration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SUB-AGENT ORCHESTRATION (v2.0)                               │
└─────────────────────────────────────────────────────────────────────────────────┘

     PHASE 1: DATA COLLECTION (Parallel, Fast)
     ══════════════════════════════════════════════════════════════════════════

     ┌───────────────────────────┐     ┌───────────────────────────┐
     │   timezone-optimizer      │     │ onlyfans-business-analyst │
     │   ───────────────────     │     │ ─────────────────────────  │
     │   Model: haiku            │     │   Model: opus              │
     │   Timeout: 15s            │     │   Timeout: 45s             │
     │   Cache: 30 days          │     │   Cache: 14 days           │
     │                           │     │                            │
     │   Purpose:                │     │   Purpose:                 │
     │   Optimize send times     │     │   Market research &        │
     │   across time zones       │     │   benchmarks               │
     └───────────────────────────┘     └───────────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
     PHASE 2: OPTIMIZATION (Sequential, Context-Dependent)
     ══════════════════════════════════════════════════════════════════════════

     ┌───────────────────────────┐
     │ content-strategy-optimizer │
     │ ─────────────────────────  │
     │   Model: sonnet            │
     │   Timeout: 30s             │
     │   Cache: 7 days            │
     │                            │
     │   Purpose:                 │
     │   Content rotation         │
     │   patterns & variety       │
     └─────────────┬─────────────┘
                   ▼
     ┌───────────────────────────┐
     │    volume-calibrator       │
     │    ─────────────────       │
     │   Model: sonnet            │
     │   Timeout: 30s             │
     │   Cache: 3 days            │
     │                            │
     │   Purpose:                 │
     │   Saturation detection     │
     │   & volume optimization    │
     └─────────────┬─────────────┘
                   ▼
     ┌───────────────────────────┐
     │    revenue-optimizer       │
     │    ─────────────────       │
     │   Model: sonnet            │
     │   Timeout: 30s             │
     │   Cache: 7 days            │
     │                            │
     │   Purpose:                 │
     │   Dynamic pricing          │
     │   recommendations          │
     └─────────────┬─────────────┘
                   ▼
     PHASE 3: FOLLOW-UP DESIGN
     ══════════════════════════════════════════════════════════════════════════

     ┌───────────────────────────┐
     │   multi-touch-sequencer    │
     │   ─────────────────────    │
     │   Model: opus              │
     │   Timeout: 45s             │
     │   Cache: 1 day             │
     │                            │
     │   Purpose:                 │
     │   3-touch follow-up        │
     │   sequence planning        │
     └─────────────┬─────────────┘
                   ▼
     PHASE 4: VALIDATION (Never Cached)
     ══════════════════════════════════════════════════════════════════════════

     ┌───────────────────────────┐
     │   validation-guardian      │
     │   ──────────────────       │
     │   Model: sonnet            │
     │   Timeout: 30s             │
     │   Cache: NEVER             │
     │                            │
     │   Purpose:                 │
     │   15+ rule validation      │
     │   & compliance             │
     └───────────────────────────┘
```

---

## 6. Database Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DATABASE ENTITY RELATIONSHIPS                                │
│                    (Schedule Generation Focus)                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────────────┐
                                    │   content_types     │ [DIMENSION]
                                    │   (33 records)      │
                                    ├─────────────────────┤
                                    │ PK content_type_id  │
                                    │    type_name        │
                                    │    type_category    │
                                    │    priority_tier    │
                                    └──────────┬──────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
     ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
     │    vault_matrix     │    │    caption_bank     │    │   mass_messages     │
     │   (1,188 records)   │    │  (19,590 records)   │    │  (66,826 records)   │
     │      [BRIDGE]       │    │    [DIMENSION]      │    │       [FACT]        │
     ├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤
     │ FK creator_id ──────┼───►│ PK caption_id       │◄───┼─ FK caption_id      │
     │ FK content_type_id  │    │ FK content_type_id  │    │ FK content_type_id  │
     │    has_content      │    │    caption_text     │    │ FK creator_id ──────┼──┐
     │    quantity         │    │    performance_score│    │    message_content  │  │
     └──────────┬──────────┘    │    freshness_score  │    │    sending_time     │  │
                │               │    tone             │    │    price, earnings  │  │
                │               │    emoji_style      │    │    view_rate        │  │
                │               │    slang_level      │    │    purchase_rate    │  │
                │               └──────────┬──────────┘    └──────────┬──────────┘  │
                │                          │                          │             │
                │                          │                          │             │
                ▼                          ▼                          │             │
     ╔═════════════════════════════════════════════════════════════════════════════╗
     ║                          creators (36 records) [HUB]                        ║
     ╠═════════════════════════════════════════════════════════════════════════════╣
     ║ PK creator_id          │ Performance Metrics:                               ║
     ║    page_name           │   current_active_fans                              ║
     ║    display_name        │   current_total_earnings                           ║
     ║    page_type           │   current_avg_earnings_per_fan                     ║
     ║    subscription_price  │   performance_tier                                 ║
     ║    is_active           │                                                    ║
     ╚═════════════════════════════════════════════════════════════════════════════╝
                │
                │
     ┌──────────┴──────────┐
     │                     │
     ▼                     ▼
┌─────────────────┐  ┌─────────────────────┐
│creator_personas │  │caption_creator_perf │
│ (35 records)    │  │  (11,069 records)   │
│     [DIM]       │  │      [BRIDGE]       │
├─────────────────┤  ├─────────────────────┤
│FK creator_id    │  │ FK caption_id       │
│   primary_tone  │  │ FK creator_id       │
│   emoji_frequency│  │    times_used       │
│   slang_level   │  │    total_earnings   │
│   avg_sentiment │  │    performance_score│
└─────────────────┘  └─────────────────────┘


KEY QUERIES FOR SCHEDULE GENERATION:
═══════════════════════════════════════════════════════════════════════════════

Step 1 (ANALYZE):
    SELECT * FROM creators c
    JOIN creator_personas cp ON c.creator_id = cp.creator_id
    WHERE c.page_name = ?

Step 2 (MATCH CONTENT):
    SELECT cb.* FROM caption_bank cb
    JOIN vault_matrix vm ON cb.content_type_id = vm.content_type_id
    WHERE vm.creator_id = ? AND vm.has_content = 1
    AND cb.freshness_score >= 30

Step 3 (MATCH PERSONA):
    SELECT cp.primary_tone, cp.emoji_frequency, cp.slang_level
    FROM creator_personas cp WHERE cp.creator_id = ?
```

---

## 7. Data Flow: Request to Schedule

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    REQUEST → SCHEDULE DATA FLOW                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

     User Request                    Claude Code                    EROS Pipeline
          │                              │                              │
          │ "Generate schedule           │                              │
          │  for missalexa"              │                              │
          │─────────────────────────────►│                              │
          │                              │                              │
          │                              │  Skill Trigger Match         │
          │                              │  (SKILL.md patterns)         │
          │                              │─────────────────────────────►│
          │                              │                              │
          │                              │                    MODE SELECTION
          │                              │                    ┌─────────┴─────────┐
          │                              │                    │                   │
          │                              │               Quick Mode          Full Mode
          │                              │                    │                   │
          │                              │           generate_schedule   prepare_llm_context
          │                              │                    │                   │
          │                              │                    └─────────┬─────────┘
          │                              │                              │
          │                              │                    STEP 1: ANALYZE
          │                              │                    ┌─────────────────┐
          │                              │                    │ Creator lookup  │
          │                              │                    │ Volume tier     │
          │                              │                    │ Persona load    │
          │                              │                    └────────┬────────┘
          │                              │                             │
          │                              │                    STEP 2-3: CONTENT+PERSONA
          │                              │                    ┌─────────────────┐
          │                              │                    │ Caption query   │
          │                              │                    │ Freshness check │
          │                              │                    │ Persona boost   │
          │                              │                    └────────┬────────┘
          │                              │                             │
          │                              │                    STEP 4-5: BUILD+ASSIGN
          │                              │                    ┌─────────────────┐
          │                              │                    │ Time slots      │
          │                              │                    │ Vose Alias      │
          │                              │                    │ selection       │
          │                              │                    └────────┬────────┘
          │                              │                             │
          │                              │                    STEP 6-8: FOLLOW-UPS+RULES
          │                              │                    ┌─────────────────┐
          │                              │                    │ Bumps (15-45m)  │
          │                              │                    │ Drip windows    │
          │                              │                    │ Page type rules │
          │                              │                    └────────┬────────┘
          │                              │                             │
          │                              │                    STEP 9: VALIDATE
          │                              │                    ┌─────────────────┐
          │                              │                    │ 15+ rules       │
          │                              │                    │ Error/Warning   │
          │                              │◄────────────────────│ collection      │
          │                              │                    └─────────────────┘
          │                              │
          │                              │  Format Output
          │     Weekly Schedule          │  (Markdown/JSON)
          │     + Validation Report      │
          │◄─────────────────────────────│
          │                              │


OUTPUT STRUCTURE:
═══════════════════════════════════════════════════════════════════════════════

ScheduleResult {
    items: [
        ScheduleItem {
            item_type: "ppv",
            send_time: "2025-W50-1T18:00:00",
            caption_text: "exclusive content...",
            content_type: "solo",
            price: 15.00,
            persona_boost: 1.25,
            freshness_score: 85
        },
        ScheduleItem {
            item_type: "bump",
            send_time: "2025-W50-1T18:30:00",
            parent_id: 1,
            caption_text: "did you see..."
        },
        ...
    ],
    validation: ValidationReport {
        errors: [],
        warnings: ["PPV spacing 3.5h at slot 4 (recommended 4h)"],
        info: ["21 PPVs scheduled for week"]
    }
}
```

---

## 8. Symbol Legend

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SYMBOL QUICK REFERENCE                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  BOX STYLES                    FLOW INDICATORS         TABLE TYPES              │
│  ──────────                    ───────────────         ───────────              │
│  ╔══╗ Primary/Important        ───► Single flow        [HUB] Central entity     │
│  ┌──┐ Secondary/Standard       ═══► Multi/parallel     [FACT] Transaction data  │
│  ╭──╮ Optional/Phase           ◄──► Bidirectional      [DIM] Reference data     │
│                                                        [BRIDGE] Junction table  │
│                                                                                 │
│  LAYER INDICATORS              STEP INDICATORS         RELATIONSHIP             │
│  ────────────────              ───────────────         ────────────             │
│  📱 Presentation               Step N  Required        PK Primary Key           │
│  ⚙️  Processing                Step NB Optional        FK Foreign Key           │
│  💾 Data                       * Full Mode Only        1:N One to Many          │
│                                                                                 │
│  MODEL INDICATORS              CACHE INDICATORS                                 │
│  ────────────────              ────────────────                                 │
│  haiku  Fast, simple           30 days  Long cache                              │
│  sonnet Balanced               7 days   Medium cache                            │
│  opus   Complex reasoning      never    No cache                                │
│                                                                                 │
│  PIPELINE PHASES                                                                │
│  ───────────────                                                                │
│  Phase 1: Data Gathering (Steps 1-3)                                            │
│  Phase 2: Schedule Building (Steps 4-5, 4B)                                     │
│  Phase 3: Follow-ups & Adjustments (Steps 6-8, 7B)                              │
│  Phase 4: Finalization (Step 9)                                                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         QUICK REFERENCE CARD                                  ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  ENTRY POINTS                                                                 ║
║  ────────────                                                                 ║
║  Quick Mode: python generate_schedule.py --creator NAME --week YYYY-Www       ║
║  Full Mode:  python prepare_llm_context.py --creator NAME --week YYYY-Www     ║
║                                                                               ║
║  EXECUTION TIME                                                               ║
║  ──────────────                                                               ║
║  Quick Mode: <30 seconds (pattern matching only)                              ║
║  Full Mode:  <60 seconds (with LLM semantic analysis)                         ║
║                                                                               ║
║  VOLUME TIERS                                                                 ║
║  ────────────                                                                 ║
║  Base:   2 PPV/day (14/week) - Default minimum                                ║
║  Growth: 3 PPV/day (21/week) - Conv >0.10% OR $/PPV >$40                      ║
║  Scale:  4 PPV/day (28/week) - Conv >0.25% AND $/PPV >$50                     ║
║  High:   5 PPV/day (35/week) - Conv >0.35% AND $/PPV >$65                     ║
║  Ultra:  6 PPV/day (42/week) - Conv >0.40% AND $/PPV >$75                     ║
║                                                                               ║
║  CRITICAL THRESHOLDS                                                          ║
║  ───────────────────                                                          ║
║  PPV Spacing: 3h minimum (ERROR), 4h recommended (WARNING)                    ║
║  Freshness: >= 30 required for scheduling                                     ║
║  Persona Boost: 1.0x - 1.4x (capped)                                          ║
║  Follow-up Delay: 15-45 minutes after parent PPV                              ║
║                                                                               ║
║  DATABASE PATH                                                                ║
║  ─────────────                                                                ║
║  ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db                    ║
║                                                                               ║
║  KEY TABLES                                                                   ║
║  ──────────                                                                   ║
║  creators: 36  │  caption_bank: 19,590  │  mass_messages: 66,826              ║
║  creator_personas: 35  │  vault_matrix: 1,188  │  content_types: 33           ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

*Generated: 2025-12-06 | EROS Schedule Generator v2.0 | 23 Scripts | 23,650 Lines*
