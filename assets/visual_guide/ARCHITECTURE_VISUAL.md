# EROS Schedule Generator Architecture

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                                       ║
║  ███████╗██████╗  ██████╗ ███████╗    ███████╗ ██████╗██╗  ██╗███████╗██████╗ ██╗   ██╗██╗     ███████╗║
║  ██╔════╝██╔══██╗██╔═══██╗██╔════╝    ██╔════╝██╔════╝██║  ██║██╔════╝██╔══██╗██║   ██║██║     ██╔════╝║
║  █████╗  ██████╔╝██║   ██║███████╗    ███████╗██║     ███████║█████╗  ██║  ██║██║   ██║██║     █████╗  ║
║  ██╔══╝  ██╔══██╗██║   ██║╚════██║    ╚════██║██║     ██╔══██║██╔══╝  ██║  ██║██║   ██║██║     ██╔══╝  ║
║  ███████╗██║  ██║╚██████╔╝███████║    ███████║╚██████╗██║  ██║███████╗██████╔╝╚██████╔╝███████╗███████╗║
║  ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚══════╝╚══════╝║
║                                                                                                       ║
║                              GENERATOR ARCHITECTURE v2.0                                              ║
║                                                                                                       ║
║       12-Step Extended Pipeline | 19 Scripts | 22,800 Lines | 36 Creators | 19,590 Captions          ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 1: High-Level Workflow Overview

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   SYSTEM WORKFLOW OVERVIEW                                            ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║   ╭───────────────────╮       ╭───────────────────╮       ╭───────────────────╮       ╭─────────────╮ ║
║   │                   │       │                   │       │                   │       │             │ ║
║   │      INPUT        │       │     PROCESS       │       │     VALIDATE      │       │   OUTPUT    │ ║
║   │                   │       │                   │       │                   │       │             │ ║
║   │  Creator Name     │       │  12-Step Pipeline │       │  Business Rules   │       │  Markdown   │ ║
║   │  Target Week      │══════>│  Caption Select   │══════>│  Spacing Check    │══════>│  Schedule   │ ║
║   │  Mode (Quick/Full)│       │  Persona Match    │       │  Freshness Audit  │       │  File       │ ║
║   │                   │       │  Quality Scoring  │       │                   │       │             │ ║
║   ╰───────────────────╯       ╰─────────┬─────────╯       ╰───────────────────╯       ╰─────────────╯ ║
║                                         │                                                             ║
║                   ┌─────────────────────┴─────────────────────┐                                       ║
║                   │                                           │                                       ║
║                   ▼                                           ▼                                       ║
║         ┌─────────────────────┐                 ┌─────────────────────┐                               ║
║         │                     │                 │                     │                               ║
║         │      DATABASE       │                 │    SUB-AGENTS       │                               ║
║         │  eros_sd_main.db    │                 │   (7 Specialized)   │                               ║
║         │                     │                 │                     │                               ║
║         │  36 creators        │                 │  • timezone-opt     │                               ║
║         │  19,590 captions    │                 │  • pricing-strat    │                               ║
║         │  66,826 messages    │                 │  • content-rotate   │                               ║
║         │  35 personas        │                 │  • revenue-forecast │                               ║
║         │                     │                 │  • validation-guard │                               ║
║         └─────────────────────┘                 └─────────────────────┘                               ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 2: Execution Modes

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   EXECUTION MODES                                                     ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │                                                                                                 │ ║
║   │        QUICK MODE                                    FULL MODE                                  │ ║
║   │        ══════════                                    ═════════                                  │ ║
║   │                                                                                                 │ ║
║   │   Entry Point:                                  Entry Point:                                    │ ║
║   │   generate_schedule.py                          prepare_llm_context.py                          │ ║
║   │                                                                                                 │ ║
║   │   Time: < 30 seconds                            Time: < 60 seconds                              │ ║
║   │                                                                                                 │ ║
║   │   ┌───────────────────────┐                     ┌───────────────────────┐                       │ ║
║   │   │  Steps 1-9            │                     │  Steps 1-9            │                       │ ║
║   │   │  Pattern matching     │                     │  + Step 4B (Quality)  │                       │ ║
║   │   │  No LLM calls         │                     │  + Step 7B (Enhance)  │                       │ ║
║   │   │                       │                     │  + Step 8B (Follow-up)│                       │ ║
║   │   │                       │                     │  LLM Semantic Analysis│                       │ ║
║   │   └───────────────────────┘                     └───────────────────────┘                       │ ║
║   │                                                                                                 │ ║
║   │   Weight Formula:                               Weight Formula:                                 │ ║
║   │   perf×0.6 + fresh×0.4                          perf×0.5 + fresh×0.3 + quality×0.2              │ ║
║   │   × persona_boost                               × persona_boost                                 │ ║
║   │                                                                                                 │ ║
║   │   Best For:                                     Best For:                                       │ ║
║   │   • Daily scheduling                            • Important launches                            │ ║
║   │   • Routine operations                          • High-value creators                           │ ║
║   │   • Speed priority                              • Maximum optimization                          │ ║
║   │                                                                                                 │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 3: Detailed Component Map

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   FILE COMPONENT ARCHITECTURE                                         ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║                                   ┌─────────────────────┐                                             ║
║                                   │      SKILL.md       │                                             ║
║                                   │   (Entry Point)     │                                             ║
║                                   │  Trigger & Routing  │                                             ║
║                                   └──────────┬──────────┘                                             ║
║                                              │                                                        ║
║              ┌───────────────────────────────┼───────────────────────────────┐                        ║
║              │                               │                               │                        ║
║              ▼                               ▼                               ▼                        ║
║   ╭─────────────────────╮     ╭─────────────────────────────╮     ╭─────────────────────╮             ║
║   │   assets/           │     │       references/           │     │     scripts/        │             ║
║   │   ───────           │     │       ───────────           │     │     ────────        │             ║
║   │                     │     │                             │     │   (19 files)        │             ║
║   │ ┌─────────────────┐ │     │ ┌─────────────────────────┐ │     │                     │             ║
║   │ │ sql/            │ │     │ │  database-schema.md     │ │     │ ┌─────────────────┐ │             ║
║   │ │ ──── (6 core)   │ │     │ │  (1,107 lines)          │ │     │ │ CORE PIPELINE   │ │             ║
║   │ │ • creator       │ │     │ └─────────────────────────┘ │     │ │ ═══════════════ │ │             ║
║   │ │   profile       │ │     │ ┌─────────────────────────┐ │     │ │ generate_       │ │             ║
║   │ │ • captions      │ │     │ │  scheduling_rules.md    │ │     │ │ schedule.py     │ │             ║
║   │ │ • vault         │ │     │ │  (542 lines)            │ │     │ │ (2,153 lines)   │ │             ║
║   │ │ • optimal hrs   │ │     │ └─────────────────────────┘ │     │ ├─────────────────┤ │             ║
║   │ │ • perf trends   │ │     │ ┌─────────────────────────┐ │     │ │ analyze_        │ │             ║
║   │ │ • active list   │ │     │ │  analytics_algorithms   │ │     │ │ creator.py      │ │             ║
║   │ └─────────────────┘ │     │ │  (399 lines)            │ │     │ │ select_         │ │             ║
║   │ ┌─────────────────┐ │     │ └─────────────────────────┘ │     │ │ captions.py     │ │             ║
║   │ │ sql/batch_      │ │     │ ┌─────────────────────────┐ │     │ │ match_          │ │             ║
║   │ │ analysis/       │ │     │ │  architecture.md        │ │     │ │ persona.py      │ │             ║
║   │ │ ──── (10 files) │ │     │ │  extraction_map.md      │ │     │ │ volume_         │ │             ║
║   │ │ • portfolio_    │ │     │ │  strategy-frameworks    │ │     │ │ optimizer.py    │ │             ║
║   │ │   summary       │ │     │ │  industry-benchmarks    │ │     │ │ calculate_      │ │             ║
║   │ │ • caption_      │ │     │ │  validation_report      │ │     │ │ freshness.py    │ │             ║
║   │ │   health        │ │     │ │  gap_analysis           │ │     │ │ followup_       │ │             ║
║   │ │ • ppv_metrics   │ │     │ │  2025_insights          │ │     │ │ generator.py    │ │             ║
║   │ │ • pricing       │ │     │ └─────────────────────────┘ │     │ │ validate_       │ │             ║
║   │ │ • content_perf  │ │     │                             │     │ │ schedule.py     │ │             ║
║   │ │ • timing        │ │     │   (11 files, 6,741 lines)   │     │ └─────────────────┘ │             ║
║   │ │ • positioning   │ │     │                             │     │                     │             ║
║   │ │ • persona       │ │     ╰─────────────────────────────╯     │ ┌─────────────────┐ │             ║
║   │ │ • revenue       │ │                                         │ │ LLM INTEGRATION │ │             ║
║   │ └─────────────────┘ │                                         │ │ ═══════════════ │ │             ║
║   │                     │                                         │ │ prepare_llm_    │ │             ║
║   ╰─────────────────────╯                                         │ │ context.py      │ │             ║
║              │                                                    │ │ semantic_       │ │             ║
║              │                                                    │ │ analysis.py     │ │             ║
║              │                                                    │ │ apply_llm_      │ │             ║
║              │                                                    │ │ insights.py     │ │             ║
║              │                                                    │ │ quality_        │ │             ║
║              │                                                    │ │ scoring.py      │ │             ║
║              │                                                    │ │ caption_        │ │             ║
║              │                                                    │ │ enhancer.py     │ │             ║
║              │                                                    │ └─────────────────┘ │             ║
║              │                                                    │                     │             ║
║              │                                                    │ ┌─────────────────┐ │             ║
║              │                                                    │ │ INFRASTRUCTURE  │ │             ║
║              │                                                    │ │ ═══════════════ │ │             ║
║              │                                                    │ │ agent_          │ │             ║
║              │                                                    │ │ invoker.py      │ │             ║
║              │                                                    │ │ shared_         │ │             ║
║              │                                                    │ │ context.py      │ │             ║
║              │                                                    │ │ batch_portfolio │ │             ║
║              │                                                    │ │ _analysis.py    │ │             ║
║              │                                                    │ │ volume_valid    │ │             ║
║              │                                                    │ │ _report.py      │ │             ║
║              │                                                    │ │ verify_         │ │             ║
║              │                                                    │ │ deployment.py   │ │             ║
║              │                                                    │ └─────────────────┘ │             ║
║              │                                                    │                     │             ║
║              │                                                    ╰─────────────────────╯             ║
║              │                                                              │                         ║
║              └──────────────────────────────────────────────────────────────┘                         ║
║                                             │                                                         ║
║                                             ▼                                                         ║
║                              ╔═════════════════════════════╗                                          ║
║                              ║                             ║                                          ║
║                              ║     eros_sd_main.db         ║                                          ║
║                              ║     ─────────────────       ║                                          ║
║                              ║     Production Database     ║                                          ║
║                              ║                             ║                                          ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 4: Database Interaction Flow

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   DATABASE INTERACTION FLOW                                           ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║    ┌─────────────────────────────────────────────────────────────────────────────────────────────┐    ║
║    │                              eros_sd_main.db (SQLite)                                        │    ║
║    │   ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db                                 │    ║
║    ├─────────────────────────────────────────────────────────────────────────────────────────────┤    ║
║    │                                                                                             │    ║
║    │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐  │    ║
║    │   │  creators   │   │caption_bank │   │  creator_   │   │vault_matrix │   │   mass_     │  │    ║
║    │   │             │   │             │   │  personas   │   │             │   │  messages   │  │    ║
║    │   │  36 active  │   │   19,590    │   │     35      │   │   1,188     │   │   66,826    │  │    ║
║    │   │  creators   │   │  captions   │   │  personas   │   │  entries    │   │  messages   │  │    ║
║    │   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘  │    ║
║    │          │                 │                 │                 │                 │          │    ║
║    └──────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┼──────────┘    ║
║               │                 │                 │                 │                 │               ║
║               └─────────────────┴────────┬────────┴─────────────────┴─────────────────┘               ║
║                                          │                                                            ║
║              ┌───────────────────────────┴───────────────────────────┐                                ║
║              │                                                       │                                ║
║              ▼                                                       ▼                                ║
║   ┌─────────────────────┐                             ┌─────────────────────┐                         ║
║   │   assets/sql/       │                             │   assets/sql/       │                         ║
║   │   ─────────────     │                             │   batch_analysis/   │                         ║
║   │   CORE QUERIES      │                             │   ───────────────   │                         ║
║   │   (6 files)         │                             │   PORTFOLIO QUERIES │                         ║
║   │                     │                             │   (10 files)        │                         ║
║   │  • get_creator_     │                             │                     │                         ║
║   │    profile.sql      │                             │  • portfolio_       │                         ║
║   │  • get_available_   │                             │    summary.sql      │                         ║
║   │    captions.sql     │                             │  • caption_         │                         ║
║   │  • get_vault_       │                             │    health.sql       │                         ║
║   │    inventory.sql    │                             │  • ppv_metrics.sql  │                         ║
║   │  • get_optimal_     │                             │  • pricing_         │                         ║
║   │    hours.sql        │                             │    analysis.sql     │                         ║
║   │  • get_performance_ │                             │  • content_         │                         ║
║   │    trends.sql       │                             │    performance.sql  │                         ║
║   │  • get_active_      │                             │  • timing_          │                         ║
║   │    creators.sql     │                             │    analysis.sql     │                         ║
║   └──────────┬──────────┘                             └─────────────────────┘                         ║
║              │                                                                                        ║
║              ▼                                                                                        ║
║   ┌─────────────────────┐                                                                             ║
║   │ generate_schedule.py│                                                                             ║
║   │         or          │                                                                             ║
║   │prepare_llm_context  │                                                                             ║
║   │       .py           │                                                                             ║
║   │                     │                                                                             ║
║   │  12-Step Pipeline   │                                                                             ║
║   │  Vose Alias Select  │                                                                             ║
║   │  Persona Matching   │                                                                             ║
║   │  Quality Scoring    │                                                                             ║
║   └──────────┬──────────┘                                                                             ║
║              │                                                                                        ║
║              ▼                                                                                        ║
║   ┌─────────────────────┐                                                                             ║
║   │validate_schedule.py │                                                                             ║
║   │                     │                                                                             ║
║   │  - PPV spacing      │                                                                             ║
║   │  - Duplicates       │                                                                             ║
║   │  - Freshness        │                                                                             ║
║   │  - Rotation         │                                                                             ║
║   │  - Content type     │                                                                             ║
║   └──────────┬──────────┘                                                                             ║
║              │                                                                                        ║
║              ▼                                                                                        ║
║   ╭─────────────────────────────╮                                                                     ║
║   │                             │                                                                     ║
║   │     MARKDOWN OUTPUT         │                                                                     ║
║   │                             │                                                                     ║
║   │  7-day PPV Schedule         │                                                                     ║
║   │  + Bump Follow-ups          │                                                                     ║
║   │  + Performance Predictions  │                                                                     ║
║   │  + Quality Scores           │                                                                     ║
║   │                             │                                                                     ║
║   ╰─────────────────────────────╯                                                                     ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 5: The Complete 12-Step Extended Pipeline

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                               12-STEP EXTENDED PIPELINE VISUALIZATION                                 ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │  INPUT: creator_name, target_week, mode (quick/full)                                            │ ║
║   └──────────────────────────────────────────────┬──────────────────────────────────────────────────┘ ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 1: ANALYZE                                                     [analyze_creator.py]   │    ║
║   │  ─────────────────                                                                           │    ║
║   │  Load creator profile from database                                                          │    ║
║   │  Tables: creators, creator_personas, mass_messages, vault_matrix                             │    ║
║   │  Output: CreatorProfile object with fan_count, page_type, persona_id                         │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 2: MATCH CONTENT                                               [select_captions.py]   │    ║
║   │  ──────────────────                                                                          │    ║
║   │  Filter captions by: vault availability, freshness >= 30, performance score                  │    ║
║   │  Formula: freshness = 100 * (0.5 ^ (days_since_use / 14))  [14-day half-life]               │    ║
║   │  Output: List of eligible Caption objects                                                    │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 3: MATCH PERSONA                                                 [match_persona.py]   │    ║
║   │  ─────────────────                                                                           │    ║
║   │  Apply persona boost multiplier (1.0x - 1.4x max)                                            │    ║
║   │  • tone_match = 1.0 - 1.20x   • emoji_match = 1.0 - 1.05x   • slang_match = 1.0 - 1.05x     │    ║
║   │  Output: Captions with boosted scores                                                        │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 4: BUILD STRUCTURE                                            [volume_optimizer.py]   │    ║
║   │  ───────────────────                                                                         │    ║
║   │  Create weekly time slots with 4-hour minimum spacing                                        │    ║
║   │  ┌────────────────────────────────────────────────────────────────┐                          │    ║
║   │  │  VOLUME LEVELS                                                 │                          │    ║
║   │  │  Fan Count      Level    PPV/Day  Bump/Day  Weekly Total       │                          │    ║
║   │  │  < 1,000        Low      2-3      2-3       14-21              │                          │    ║
║   │  │  1,000-5,000    Mid      3-4      3-4       21-28              │                          │    ║
║   │  │  5,000-15,000   High     4-5      4-5       28-35              │                          │    ║
║   │  │  15,000+        Ultra    5-6      5-6       35-42              │                          │    ║
║   │  └────────────────────────────────────────────────────────────────┘                          │    ║
║   │  Output: WeeklyStructure with time slot placeholders                                         │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 4B: QUALITY SCORING (Full Mode Only)                          [quality_scoring.py]    │    ║
║   │  ─────────────────────────────────────────                                                   │    ║
║   │  LLM-based caption quality assessment                                                        │    ║
║   │  ┌────────────────────────────────────────────────────────────────┐                          │    ║
║   │  │  QUALITY FACTORS                                               │                          │    ║
║   │  │  Authenticity:         35%   Hook Strength:       25%          │                          │    ║
║   │  │  CTA Effectiveness:    20%   Conversion Potential: 20%         │                          │    ║
║   │  └────────────────────────────────────────────────────────────────┘                          │    ║
║   │  Output: Quality scores for caption ranking                                                  │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 5: ASSIGN CAPTIONS                                 [select_captions.py + Vose Alias]  │    ║
║   │  ───────────────────                                                                         │    ║
║   │  Use Vose Alias Method for O(1) weighted random selection                                    │    ║
║   │  Quick: weight = perf×0.6 + fresh×0.4 × persona_boost                                       │    ║
║   │  Full:  weight = perf×0.5 + fresh×0.3 + quality×0.2 × persona_boost                         │    ║
║   │  Output: Time slots populated with selected captions                                         │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 6: GENERATE FOLLOW-UPS                                      [followup_generator.py]   │    ║
║   │  ───────────────────────                                                                     │    ║
║   │  Create context-aware bump messages 15-45 minutes after each PPV                             │    ║
║   │  Timing: Random offset between 15-45 min                                                     │    ║
║   │  Style: Matches original PPV tone and urgency                                                │    ║
║   │  Output: PPV slots with associated bump message times                                        │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 7: APPLY DRIP WINDOWS                                                                  │    ║
║   │  ──────────────────────                                                                      │    ║
║   │  Mark no-PPV zones if drip mode enabled                                                      │    ║
║   │  Drip Window: 4-8 hours after drip content                                                   │    ║
║   │  Purpose: Prevent PPV fatigue during peak browse hours                                       │    ║
║   │  Output: Schedule with protected time zones marked                                           │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 7B: CAPTION ENHANCEMENT (Full Mode Only)                      [caption_enhancer.py]   │    ║
║   │  ──────────────────────────────────────────                                                  │    ║
║   │  Authenticity tweaks for natural-sounding content                                            │    ║
║   │  • Contraction insertion (do not → don't)                                                    │    ║
║   │  • Emoji calibration to match persona                                                        │    ║
║   │  • Slang level adjustment                                                                    │    ║
║   │  Output: Enhanced captions with improved authenticity                                        │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 8: APPLY PAGE TYPE RULES                                                               │    ║
║   │  ───────────────────                                                                         │    ║
║   │  Adjust pricing based on page type                                                           │    ║
║   │  Paid Page: +10% on all prices    Free Page: -10% on all prices                             │    ║
║   │  Output: Schedule with adjusted pricing                                                      │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 8B: CONTEXTUAL FOLLOW-UPS (Full Mode Only)                    [followup_generator.py] │    ║
║   │  ────────────────────────────────────────────                                                │    ║
║   │  Personalized bump messages based on content context                                         │    ║
║   │  • Analyzes original PPV content type                                                        │    ║
║   │  • Generates contextually relevant follow-up                                                 │    ║
║   │  • Matches urgency and tone                                                                  │    ║
║   │  Output: Context-aware follow-up messages                                                    │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ╭──────────────────────────────────────────────────────────────────────────────────────────────╮    ║
║   │  STEP 9: VALIDATE                                                   [validate_schedule.py]  │    ║
║   │  ────────────────                                                                            │    ║
║   │  Final validation against all business rules                                                 │    ║
║   │  ┌────────────────────────────────────────────────────────────────┐                          │    ║
║   │  │  VALIDATION RULES                                              │                          │    ║
║   │  │  [x] PPV spacing >= 3 hours (hard minimum)                    │                          │    ║
║   │  │  [x] No duplicate captions in schedule                        │                          │    ║
║   │  │  [x] All captions have freshness >= 30                        │                          │    ║
║   │  │  [x] No same content type 3x consecutive                      │                          │    ║
║   │  │  [x] Follow-up timing 15-45 min after PPV                     │                          │    ║
║   │  │  [x] Daily PPV count matches volume level                     │                          │    ║
║   │  └────────────────────────────────────────────────────────────────┘                          │    ║
║   │  Output: Validated schedule or error report                                                  │    ║
║   ╰──────────────────────────────────────────────────────────────────────────────────────────────╯    ║
║                                                  │                                                    ║
║                                                  ▼                                                    ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │  OUTPUT: 7-Day PPV Schedule (Markdown)                                                          │ ║
║   │  - Day-by-day posting times          - Follow-up bump timing                                    │ ║
║   │  - Caption text with persona match   - Performance predictions                                  │ ║
║   │  - Suggested pricing per item        - Quality scores (Full mode)                               │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 6: Sub-Agent Architecture

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   SUB-AGENT DELEGATION SYSTEM                                         ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │                                                                                                 │ ║
║   │                              agent_invoker.py (605 lines)                                       │ ║
║   │                              ═══════════════════════════════                                    │ ║
║   │                                                                                                 │ ║
║   │                                         │                                                       │ ║
║   │              ┌──────────────────────────┼──────────────────────────┐                            │ ║
║   │              │              │           │           │              │                            │ ║
║   │              ▼              ▼           ▼           ▼              ▼                            │ ║
║   │   ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐    │ ║
║   │   │   timezone-   │ │   pricing-    │ │   content-    │ │   revenue-    │ │  validation-  │    │ ║
║   │   │   optimizer   │ │  strategist   │ │   rotation-   │ │  forecaster   │ │   guardian    │    │ ║
║   │   │               │ │               │ │   architect   │ │               │ │               │    │ ║
║   │   │  Optimize     │ │  Dynamic      │ │  Content      │ │  Revenue      │ │  Advanced     │    │ ║
║   │   │  send times   │ │  pricing      │ │  variety &    │ │  projection   │ │  validation   │    │ ║
║   │   │  across       │ │  recommend    │ │  rotation     │ │  and          │ │  and          │    │ ║
║   │   │  time zones   │ │  -ations      │ │  patterns     │ │  optimization │ │  compliance   │    │ ║
║   │   └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘    │ ║
║   │                                                                                                 │ ║
║   │              ┌──────────────────────────┬──────────────────────────┐                            │ ║
║   │              ▼                          ▼                          │                            │ ║
║   │   ┌───────────────┐          ┌───────────────┐                     │                            │ ║
║   │   │   page-type-  │          │  multi-touch- │                     │                            │ ║
║   │   │   optimizer   │          │   sequencer   │                     │                            │ ║
║   │   │               │          │               │                     │                            │ ║
║   │   │  Paid vs Free │          │  Multi-msg    │                     │                            │ ║
║   │   │  page         │          │  sequence     │                     │                            │ ║
║   │   │  optimization │          │  planning     │                     │                            │ ║
║   │   └───────────────┘          └───────────────┘                     │                            │ ║
║   │                                                                    │                            │ ║
║   │   Shared Context: shared_context.py (191 lines)                   │                            │ ║
║   │   ════════════════════════════════════════════                    │                            │ ║
║   │   ScheduleContext, CreatorProfile, PersonaProfile, PricingStrategy│                            │ ║
║   │                                                                                                 │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 7: Algorithm Deep Dive

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   KEY ALGORITHMS                                                      ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │                               VOSE ALIAS METHOD                                                 │ ║
║   │                               ═════════════════                                                 │ ║
║   │                                                                                                 │ ║
║   │   Purpose: O(1) weighted random selection from caption pool                                     │ ║
║   │                                                                                                 │ ║
║   │   ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │ ║
║   │   │   PREPROCESSING (O(n))                  SELECTION (O(1))                                │   │ ║
║   │   │   ════════════════════                  ═══════════════                                 │   │ ║
║   │   │                                                                                         │   │ ║
║   │   │   Weights: [0.4, 0.1, 0.3, 0.2]        1. Pick random index i                          │   │ ║
║   │   │                                         2. Pick random float r in [0,1]                 │   │ ║
║   │   │   Build probability and alias tables    3. If r < prob[i]: return i                     │   │ ║
║   │   │                                            Else: return alias[i]                        │   │ ║
║   │   │   prob:  [1.0, 0.4, 1.0, 0.8]                                                          │   │ ║
║   │   │   alias: [ - ,  0 ,  - ,  2 ]          Constant time regardless of pool size!          │   │ ║
║   │   └─────────────────────────────────────────────────────────────────────────────────────────┘   │ ║
║   │                                                                                                 │ ║
║   │   Advantage: Traditional weighted selection is O(n), Vose Alias is O(1) after setup            │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │                               FRESHNESS DECAY                                                   │ ║
║   │                               ═══════════════                                                   │ ║
║   │                                                                                                 │ ║
║   │   Formula: freshness = 100 * (0.5 ^ (days_since_use / 14))                                      │ ║
║   │                                                                                                 │ ║
║   │   ┌────────────────────────────────────────────────────────────────────────────────────────┐    │ ║
║   │   │   100 |*                                                                               │    │ ║
║   │   │       | *                                                                              │    │ ║
║   │   │    75 |  *                                                                             │    │ ║
║   │   │       |   **                                                                           │    │ ║
║   │   │    50 |     **              <- 14-day half-life point                                  │    │ ║
║   │   │       |       ***                                                                      │    │ ║
║   │   │    30 |- - - - -*** - - - - <- Minimum threshold for selection                         │    │ ║
║   │   │       |           ****                                                                 │    │ ║
║   │   │     0 |_______________******______                                                     │    │ ║
║   │   │       0    7    14   21   28   35  days                                                │    │ ║
║   │   └────────────────────────────────────────────────────────────────────────────────────────┘    │ ║
║   │                                                                                                 │ ║
║   │   Caption becomes ineligible after ~24 days (freshness drops below 30)                          │ ║
║   │   Recovery: Wait 7-14 days after heavy use, or add new captions                                 │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │                               PERSONA BOOST CALCULATION                                         │ ║
║   │                               ═════════════════════════                                         │ ║
║   │                                                                                                 │ ║
║   │   ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐                     │ ║
║   │   │   TONE MATCH      │     │   EMOJI MATCH     │     │   SLANG MATCH     │                     │ ║
║   │   │   Match: 1.20x    │  x  │   Match: 1.05x    │  x  │   Match: 1.05x    │  = FINAL BOOST      │ ║
║   │   │   Miss:  1.00x    │     │   Miss:  1.00x    │     │   Miss:  1.00x    │    (max 1.40x)      │ ║
║   │   └───────────────────┘     └───────────────────┘     └───────────────────┘                     │ ║
║   │                                                                                                 │ ║
║   │   Example: Flirty tone (1.2) + emoji user (1.05) + uses slang (1.05) = 1.323x boost            │ ║
║   │   Impact: 20-40% conversion rate improvement with proper persona matching                       │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 8: File Reference Legend

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   FILE REFERENCE LEGEND                                               ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │                                                                                                 │ ║
║   │   FILE                           LINES    ROLE                           PIPELINE PHASE         │ ║
║   │   ════                           ═════    ════                           ══════════════         │ ║
║   │                                                                                                 │ ║
║   │   SKILL.md                       532      Skill definition               Entry Point            │ ║
║   │                                                                                                 │ ║
║   │   CORE PIPELINE SCRIPTS                                                                         │ ║
║   │   ─────────────────────                                                                         │ ║
║   │   generate_schedule.py           2,153    Main orchestrator              All Steps              │ ║
║   │   analyze_creator.py             943      Creator analytics              Step 1                 │ ║
║   │   select_captions.py             645      Caption pool mgmt              Step 2, 5              │ ║
║   │   match_persona.py               894      Persona boost calc             Step 3                 │ ║
║   │   volume_optimizer.py            1,179    Volume calculation             Step 4                 │ ║
║   │   calculate_freshness.py         519      Freshness decay                Step 2                 │ ║
║   │   followup_generator.py          1,059    Follow-up generation           Step 6, 8B             │ ║
║   │   validate_schedule.py           603      Business rules                 Step 9                 │ ║
║   │                                                                                                 │ ║
║   │   LLM INTEGRATION SCRIPTS                                                                       │ ║
║   │   ───────────────────────                                                                       │ ║
║   │   prepare_llm_context.py         806      Full mode entry                Native Integration    │ ║
║   │   semantic_analysis.py           735      Tone detection                 Step 3                 │ ║
║   │   apply_llm_insights.py          701      AI recommendations             Step 5                 │ ║
║   │   quality_scoring.py             1,287    Quality assessment             Step 4B                │ ║
║   │   caption_enhancer.py            1,388    Authenticity tweaks            Step 7B                │ ║
║   │                                                                                                 │ ║
║   │   INFRASTRUCTURE & UTILITIES                                                                    │ ║
║   │   ──────────────────────────                                                                    │ ║
║   │   agent_invoker.py               605      Sub-agent delegation           Orchestration          │ ║
║   │   shared_context.py              191      Shared data structures         Infrastructure         │ ║
║   │   batch_portfolio_analysis.py    5,737    Portfolio audit                Standalone             │ ║
║   │   volume_validation_report.py    851      Volume reporting               Utility                │ ║
║   │   verify_deployment.py           321      Deployment check               Utility                │ ║
║   │                                                                                                 │ ║
║   │   TESTING                                                                                       │ ║
║   │   ───────                                                                                       │ ║
║   │   test_volume_optimizer.py       2,183    Volume optimizer tests         Testing                │ ║
║   │                                                                                                 │ ║
║   │   SQL QUERIES (16 total)                                                                        │ ║
║   │   ─────────────────────                                                                         │ ║
║   │   assets/sql/                    6 core   Creator, captions, vault       Steps 1, 2, 4, 5       │ ║
║   │   assets/sql/batch_analysis/     10 files Portfolio analysis             Standalone             │ ║
║   │                                                                                                 │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
║   ═══════════════════════════════════════════════════════════════════════════════════════════════════ ║
║                                                                                                       ║
║   LEGEND                                                                                              ║
║   ══════                                                                                              ║
║                                                                                                       ║
║   ┌──────┐  Standard component         ╔══════╗  Critical/Primary component                          ║
║   │      │  (files, modules)           ║      ║  (database, main engine)                             ║
║   └──────┘                             ╚══════╝                                                       ║
║                                                                                                       ║
║   ╭──────╮  External interface         ────►   Data flow direction                                   ║
║   │      │  (input, output)            ═════►  Primary data flow                                     ║
║   ╰──────╯                                                                                            ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Section 9: Execution Summary

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   QUICK EXECUTION REFERENCE                                           ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                       ║
║   TRIGGER PHRASES                                                                                     ║
║   ═══════════════                                                                                     ║
║   - "generate schedule for [creator]"                                                                 ║
║   - "create weekly schedule"                                                                          ║
║   - "optimize PPV timing for [creator]"                                                               ║
║   - "select captions for [creator]"                                                                   ║
║                                                                                                       ║
║   COMMAND LINE USAGE                                                                                  ║
║   ══════════════════                                                                                  ║
║                                                                                                       ║
║   Quick Mode (pattern-only, faster):                                                                  ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │  python3 ~/.claude/skills/eros-schedule-generator/scripts/generate_schedule.py \               │ ║
║   │      --creator missalexa --week 2025-W50                                                        │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
║   Full Mode (semantic analysis):                                                                      ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐ ║
║   │  python3 ~/.claude/skills/eros-schedule-generator/scripts/prepare_llm_context.py \             │ ║
║   │      --creator missalexa --week 2025-W50 --mode full                                            │ ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                                       ║
║   PERFORMANCE TARGETS                                                                                 ║
║   ═══════════════════                                                                                 ║
║                                                                                                       ║
║   ┌──────────────────────────┬─────────────┬────────────────────────────────┐                         ║
║   │  Metric                  │  Target     │  How to Measure                │                         ║
║   ├──────────────────────────┼─────────────┼────────────────────────────────┤                         ║
║   │  Persona boost coverage  │  75%+       │  Count persona_boost > 1.0     │                         ║
║   │  Validation pass rate    │  100%       │  All schedules pass rules      │                         ║
║   │  PPV spacing compliance  │  100%       │  No spacing < 3 hours          │                         ║
║   │  Freshness compliance    │  100%       │  All captions >= 30            │                         ║
║   │  Content rotation        │  100%       │  No 3x same type               │                         ║
║   │  Quick mode time         │  <30 sec    │  Pattern-only timing           │                         ║
║   │  Full mode time          │  <60 sec    │  With LLM analysis             │                         ║
║   └──────────────────────────┴─────────────┴────────────────────────────────┘                         ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                                       ║
║                                  EROS SCHEDULE GENERATOR v2.0                                         ║
║                                                                                                       ║
║                  12-Step Extended Pipeline | 19 Scripts | 22,800 Lines of Code                       ║
║                        36 Creators | 19,590 Captions | $438K+ Portfolio                               ║
║                                                                                                       ║
║                                      Architecture Document                                            ║
║                                     Generated: December 2025                                          ║
║                                                                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
```
