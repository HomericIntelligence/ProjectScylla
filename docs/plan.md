# ProjectScylla Implementation Plan

## Overview

Build an agent testing framework that evaluates AI agent effectiveness across multiple models. Tests are pure configuration (prompt, repo, hash, expected result). **Claude Code + Opus 4.5 serves as the judge** for validating test results.

**Language**: Test Evaluation framework is implemented in Python only. Testing itself can cover any language.

**GitHub Epic**: [#2 - Agent Testing Framework Implementation](https://github.com/mvillmow/ProjectScylla/issues/2)

---

## Research Paradigm

### Core Hypothesis

**Task-dependent value** - Different tasks benefit from different tiers. There is no universal "best" tier.

### Research Question

How sensitive are agents to system prompt changes? Does the complexity of higher tiers (T3-T6) provide proportional value increase?

### Testing Methodology

- Each test runs against **ALL tiers** (T0, T1, T2, T3+)
- Each tier runs **10 times** for statistical validity
- Each run executes in **isolated Docker container**
- **3-run judge consensus** with confidence-weighted averaging

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   TEST CASES    │     │    FRAMEWORK    │     │    OUTPUTS      │
│   (Data/Config) │────▶│    (Python)     │────▶│   (Results)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
   - prompt                - executor              - judgment.json
   - repo URL              - adapter               - result.json
   - git hash              - judge (Opus 4.5)      - summary.json
   - criteria              - aggregator            - report.md
```

### Three-Phase Execution

```
PHASE 1: EXECUTE                 PHASE 2: JUDGE                 PHASE 3: REPORT
┌─────────────────┐             ┌─────────────────┐             ┌─────────────────┐
│ For each tier:  │             │ For each run:   │             │ Aggregate:      │
│ - Docker container│──────────▶│ - 3-run consensus│───────────▶│ - Statistics    │
│ - Run adapter   │  workspace  │ - Score rubric  │  judgment   │ - Cross-tier    │
│ - Capture logs  │             │ - Confidence    │             │ - Report        │
└─────────────────┘             └─────────────────┘             └─────────────────┘
     × 10 runs                      × 3 judges                       × 1
```

---

## Tier System

| Tier | Name | Description | Prompt Source |
|------|------|-------------|---------------|
| T0 | Vanilla | Base LLM, tool default, zero customization | Tool default |
| T1 | Prompted | System prompt with chain-of-thought | `tiers/t1-prompted.md` |
| T2 | Skills | Domain expertise encoded in prompts | `tiers/t2-skills.md` |
| T3+ | Tooling | External tools, multi-agent orchestration | `tiers/t3-tooling.md` |

---

## LLM-as-a-Judge Categories

| Category | Weight | Description |
|----------|--------|-------------|
| Functional Correctness | 2.0 | Does the solution work as intended? |
| Completeness | 1.5 | Are all requirements addressed? |
| Code Quality | 1.0 | Readability, maintainability, best practices |
| Simplicity | 1.0 | Prefer simple working solutions over complex ones |
| Lack of Duplication | 0.5 | DRY principle adherence |
| Clarity | 1.0 | Clear, understandable implementation |
| Documentation | 0.5 | Appropriate comments and documentation |
| Architectural Cleanliness | 0.5 | Clean separation of concerns |
| Efficiency | 0.5 | Resource usage, performance considerations |
| Cleanup Script Quality | 1.0 | Proper cleanup/teardown script creation |

**Total Weight**: 9.5

---

## Key Metrics

| Metric | Formula | Purpose |
|--------|---------|---------|
| **Pass Rate Variance** | `var(pass_rates_by_tier)` | Measure prompt sensitivity |
| **Cost-of-Pass Delta** | `max(CoP) - min(CoP)` | Cost difference between tiers |
| **Tier Uplift** | `(T_n - T_0) / T_0` | Percentage improvement over baseline |
| **Consistency** | `std_dev(scores_within_tier)` | Reliability of each tier |

---

## Implementation Phases

### Phase 1: Foundation

| Issue | Title | Status |
|-------|-------|--------|
| [#3](https://github.com/mvillmow/ProjectScylla/issues/3) | [Infra] Project structure and environment setup | Open |
| [#4](https://github.com/mvillmow/ProjectScylla/issues/4) | [Infra] Configuration loading system | Open |
| [#5](https://github.com/mvillmow/ProjectScylla/issues/5) | [Docs] Architecture documentation | Open |
| [#6](https://github.com/mvillmow/ProjectScylla/issues/6) | [Docs] Test schema specification | Open |

### Phase 2: Execution Engine

| Issue | Title | Status |
|-------|-------|--------|
| [#7](https://github.com/mvillmow/ProjectScylla/issues/7) | [Core] Workspace management | Open |
| [#8](https://github.com/mvillmow/ProjectScylla/issues/8) | [Core] Test runner orchestration | Open |
| [#9](https://github.com/mvillmow/ProjectScylla/issues/9) | [Core] Log and metrics capture | Open |
| [#10](https://github.com/mvillmow/ProjectScylla/issues/10) | [Docs] Adapter interface specification | Open |

### Phase 3: Adapters

| Issue | Title | Status |
|-------|-------|--------|
| [#11](https://github.com/mvillmow/ProjectScylla/issues/11) | [Adapter] Base adapter class | Open |
| [#12](https://github.com/mvillmow/ProjectScylla/issues/12) | [Adapter] Claude Code adapter | Open |
| [#13](https://github.com/mvillmow/ProjectScylla/issues/13) | [Adapter] OpenAI Codex adapter | Open |
| [#14](https://github.com/mvillmow/ProjectScylla/issues/14) | [Adapter] Cline adapter | Open |
| [#15](https://github.com/mvillmow/ProjectScylla/issues/15) | [Adapter] OpenCode adapter | Open |

### Phase 4: Judge System

| Issue | Title | Status |
|-------|-------|--------|
| [#16](https://github.com/mvillmow/ProjectScylla/issues/16) | [Judge] Rubric parser | Open |
| [#17](https://github.com/mvillmow/ProjectScylla/issues/17) | [Judge] Judge prompt templates | Open |
| [#18](https://github.com/mvillmow/ProjectScylla/issues/18) | [Judge] Evaluator implementation | Open |
| [#19](https://github.com/mvillmow/ProjectScylla/issues/19) | [Judge] Judgment parser | Open |
| [#20](https://github.com/mvillmow/ProjectScylla/issues/20) | [Docs] Judge protocol documentation | Open |
| [#38](https://github.com/mvillmow/ProjectScylla/issues/38) | [Judge] Cleanup script evaluation | Open |

### Phase 5: Metrics and Statistics

| Issue | Title | Status |
|-------|-------|--------|
| [#21](https://github.com/mvillmow/ProjectScylla/issues/21) | [Metrics] Statistical calculations | Open |
| [#22](https://github.com/mvillmow/ProjectScylla/issues/22) | [Metrics] Grading calculations | Open |
| [#23](https://github.com/mvillmow/ProjectScylla/issues/23) | [Metrics] 10-run aggregation | Open |
| [#24](https://github.com/mvillmow/ProjectScylla/issues/24) | [Docs] Metrics formulas documentation | Open |
| [#37](https://github.com/mvillmow/ProjectScylla/issues/37) | [Metrics] Cross-tier analysis | Open |

### Phase 6: Reporting

| Issue | Title | Status |
|-------|-------|--------|
| [#25](https://github.com/mvillmow/ProjectScylla/issues/25) | [Report] result.json writer | Open |
| [#26](https://github.com/mvillmow/ProjectScylla/issues/26) | [Report] summary.json generator | Open |
| [#27](https://github.com/mvillmow/ProjectScylla/issues/27) | [Report] scorecard.json generator | Open |
| [#28](https://github.com/mvillmow/ProjectScylla/issues/28) | [Report] Markdown report generator | Open |

### Phase 7: CLI

| Issue | Title | Status |
|-------|-------|--------|
| [#29](https://github.com/mvillmow/ProjectScylla/issues/29) | [CLI] Command-line interface | Open |
| [#30](https://github.com/mvillmow/ProjectScylla/issues/30) | [CLI] Progress display | Open |

### Phase 8: First Test Case

| Issue | Title | Status |
|-------|-------|--------|
| [#31](https://github.com/mvillmow/ProjectScylla/issues/31) | [Test] Create 001-justfile-to-makefile test case | Open |
| [#32](https://github.com/mvillmow/ProjectScylla/issues/32) | [Test] Validate framework with single run | Open |
| [#33](https://github.com/mvillmow/ProjectScylla/issues/33) | [Test] Execute full 10-run suite | Open |
| [#34](https://github.com/mvillmow/ProjectScylla/issues/34) | [Test] Generate first report | Open |

### Phase 9: Tier System (NEW)

| Issue | Title | Status |
|-------|-------|--------|
| [#35](https://github.com/mvillmow/ProjectScylla/issues/35) | [Core] Docker container orchestration | Open |
| [#36](https://github.com/mvillmow/ProjectScylla/issues/36) | [Core] Tier configuration system | Open |

---

## Directory Structure

```
ProjectScylla/
├── tests/                              # TEST CASES (Pure Data)
│   └── <test-id>/
│       ├── test.yaml                   # Test definition
│       ├── prompt.md                   # Agent prompt
│       └── expected/
│           ├── criteria.md             # Success criteria
│           └── rubric.yaml             # Scoring rubric
│
├── config/
│   ├── defaults.yaml                   # Global defaults
│   ├── models/                         # Model-specific configs
│   └── tiers/                          # Tier definitions (T0-T3+)
│
├── src/scylla/
│   ├── cli.py                          # Command-line interface
│   ├── executor/                       # Test execution
│   │   ├── runner.py                   # Main test runner
│   │   ├── workspace.py                # Git clone management
│   │   ├── docker.py                   # Container orchestration
│   │   └── tier_config.py              # Tier configuration
│   ├── adapters/                       # Agent CLI adapters
│   ├── judge/                          # Claude + Opus evaluation
│   ├── metrics/                        # Statistical calculations
│   └── reporting/                      # Report generation
│
├── runs/                               # OUTPUTS (gitignored)
├── summaries/                          # AGGREGATED RESULTS
├── reports/                            # HUMAN-READABLE REPORTS
└── docs/design/                        # DOCUMENTATION
```

---

## Test Execution Matrix

For each test case:

```
Test: 001-justfile-to-makefile
├── Tier: T0 (Vanilla)
│   ├── Run 01 [container-001-t0-r01]
│   ├── Run 02 [container-001-t0-r02]
│   └── ... (10 runs)
├── Tier: T1 (Prompted)
│   └── ... (10 runs)
├── Tier: T2 (Skills)
│   └── ... (10 runs)
└── Tier: T3+ (Tooling)
    └── ... (10 runs)

Total: 40 runs per test × N adapters
```

---

## Critical Path

```
#3 Project Structure
    ↓
#4 Config Loading → #36 Tier Config
    ↓
#7 Workspace → #35 Docker
    ↓
#8 Test Runner
    ↓
#11 Base Adapter → #12 Claude Adapter
    ↓
#16 Rubric Parser → #17 Judge Prompts → #18 Evaluator
    ↓
#21 Statistics → #23 Aggregation → #37 Cross-Tier
    ↓
#26 Summary → #28 Report
    ↓
#31 First Test → #32 Single Run → #33 Full Suite → #34 Report
```

---

## First Test Case

**Test ID**: `001-justfile-to-makefile`

| Field | Value |
|-------|-------|
| **Repository** | https://github.com/mvillmow/ProjectOdyssey |
| **Git Hash** | ce739d4aa328f1c0815b33e2812c4b889868b740 |
| **Task** | Convert justfile to Makefile + create cleanup script |
| **Tiers** | T0, T1, T2, T3+ |
| **Runs per Tier** | 10 |

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python only | Simplicity, ecosystem, subprocess capture |
| Validation | Claude Code + Opus 4.5 | Semantic evaluation beyond programmatic checks |
| Judge Consensus | 3 runs, confidence-weighted | Ensure consistent evaluations |
| Runs per tier | 10 | Statistical validity |
| Container isolation | Docker | Independent runs, reproducibility |
| Tiers | T0-T3+ | Test prompt sensitivity across complexity levels |

---

## References

- Full plan: `.claude/plans/swift-skipping-creek.md`
- Research docs: `docs/research.md`
- Test case: `tests/001-justfile-to-makefile/`

---

*Last updated: 2025-12-28*
