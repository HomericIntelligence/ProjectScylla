# ProjectScylla Implementation Plan Review

This document captures the clarifying questions asked during plan review and the decisions made.

**Review Date**: 2025-12-28
**Status**: COMPLETE - All decisions captured

## Decisions Summary

| Question | Decision |
|----------|----------|
| API Key Handling | Environment Variables (docker -e flags) |
| Runs per Tier | **9 runs** (standardized) |
| Test Focus | **Both tiers AND models** (Claude, GPT-4, etc.) |
| T0 Baseline | **Tool default behavior** (use agent CLI defaults) |
| Judge Location | **Separate container** (isolated from agent container) |
| Tier Prompts | **Independent** (each tier self-contained) |
| Docker Fallback | **Fail with error** (Docker is required) |
| Timeout Handling | **Include as failures** (pass_rate=0, impl_rate=0) |
| Report Audience | **Researchers/Engineers** (detailed technical analysis) |
| Judge Disagreement | **Run additional passes** until consensus emerges |
| First Test Scope | **Claude Code only** (add other adapters incrementally) |

## Context Files

1. `/home/mvillmow/ProjectScylla/docs/plan.md` - Implementation plan (UPDATED with decisions)
2. `/home/mvillmow/.claude/plans/swift-skipping-creek.md` - Detailed 21-part plan
3. `/home/mvillmow/.claude/plans/mellow-wandering-pnueli.md` - Plan review document
4. `/home/mvillmow/ProjectScylla/tests/001-justfile-to-makefile/` - First test case

## GitHub Issues

### Original Issues (#3-#38)

#### Phase 1: Foundation
- #3 - Project structure and environment setup
- #4 - Configuration loading system (UPDATED: runs_per_tier: 9)
- #5 - Architecture documentation
- #6 - Test schema specification

#### Phase 2: Execution Engine
- #7 - Workspace management
- #8 - Test runner orchestration (UPDATED: 9 runs, tiers+models, judge container)
- #9 - Log and metrics capture
- #10 - Adapter interface specification

#### Phase 3: Adapters
- #11 - Base adapter class (UPDATED: T0 = tool defaults, independent tiers)
- #12 - Claude Code adapter
- #13 - OpenAI Codex adapter (Phase 2 - not needed for first test)
- #14 - Cline adapter (Phase 2 - not needed for first test)
- #15 - OpenCode adapter (Phase 2 - not needed for first test)

#### Phase 4: Judge System
- #16 - Rubric parser
- #17 - Judge prompt templates (includes 10 quality categories)
- #18 - Evaluator implementation (UPDATED: separate container, retry on disagreement)
- #19 - Judgment parser
- #20 - Judge protocol documentation
- #38 - Cleanup script evaluation

#### Phase 5: Metrics and Statistics
- #21 - Statistical calculations
- #22 - Grading calculations
- #23 - 9-run aggregation (UPDATED: was 10-run)
- #24 - Metrics formulas documentation
- #37 - Cross-tier analysis

#### Phase 6: Reporting
- #25 - result.json writer
- #26 - summary.json generator
- #27 - scorecard.json generator
- #28 - Markdown report generator (includes tier comparison)

#### Phase 7: CLI
- #29 - Command-line interface
- #30 - Progress display

#### Phase 8: First Test Case
- #31 - Create 001-justfile-to-makefile test case (includes cleanup script)
- #32 - Validate framework with single run
- #33 - Execute full 9-run suite (UPDATED: was 10-run)
- #34 - Generate first report

#### Phase 9: Tier System
- #35 - Docker container orchestration (UPDATED: API keys via env vars, required)
- #36 - Tier configuration system (UPDATED: independent tiers, T0 = tool defaults)

### New Issues Created (#40-#43)

- #40 - [Infra] Dockerfile specification for scylla-runner:latest
- #41 - [Core] Judge container orchestration
- #42 - [Config] Create tier prompt template files
- #43 - [Core] Judge consensus with retry logic

---

## Review Methodology

For each phase, cross-reference the plan with the GitHub issues:

1. Read the issue with `gh issue view <number> --comments`
2. Compare issue details against plan sections
3. Identify inconsistencies, gaps, or missing details
4. Note any assumptions in the issue that aren't validated

---

## Resolved Questions

### 1. Test Execution Model

**Reference Issues**: #7, #8, #9, #35

| Question | Decision |
|----------|----------|
| How are API keys/credentials passed? | **Environment variables** via docker -e flags |
| What if Docker is unavailable? | **Fail with error** - Docker is required |
| Container isolation | Agent and judge run in **separate containers** |
| Timeout handling | **Include as failures** (pass_rate=0, impl_rate=0) |

**Still TBD** (implementation details):
- Container resource limits (CPU, memory, disk)
- Internet access handling

---

### 2. Tier System Specifics

**Reference Issues**: #36, #11, #8

| Question | Decision |
|----------|----------|
| T0 (Vanilla) behavior | **Tool default behavior** - use agent CLI defaults |
| Are tiers cumulative? | **No - independent** - each tier is self-contained |
| Testing scope | **Both tiers AND models** (Claude, GPT-4, etc.) |

**New Issue Created**: #42 - Create tier prompt template files

---

### 3. Judge System Details

**Reference Issues**: #16, #17, #18, #19, #20, #38

| Question | Decision |
|----------|----------|
| Where does judge run? | **Separate container** from agent |
| Judge disagreement handling | **Run additional passes** until consensus |
| Workspace access | Via **volume mount** (read-only) |

**New Issues Created**:
- #41 - Judge container orchestration
- #43 - Judge consensus with retry logic

---

### 4. Metrics & Statistics

**Reference Issues**: #21, #22, #23, #24, #37

| Question | Decision |
|----------|----------|
| Runs per tier | **9 runs** (standardized) |
| Timeout runs in stats? | **Include as failures** |
| Cost-of-Pass when pass_rate=0 | Return **infinity** |

---

### 5. Adapter Interface

**Reference Issues**: #10, #11, #12, #13, #14, #15

| Question | Decision |
|----------|----------|
| First test adapter scope | **Claude Code only** |
| Other adapters | **Phase 2** - not needed for first test |
| T0 prompt injection | **None** - use tool defaults |
| T1-T3+ prompt injection | Tier prompt prepended to task prompt |

---

### 6. First Test Case Specifics

**Reference Issues**: #31, #32, #33, #34

| Question | Decision |
|----------|----------|
| Runs per tier | **9 runs** (was 10) |
| Adapter for first test | **Claude Code only** |
| Cleanup script | Required - evaluated as one of 10 quality categories |

---

### 7. Reporting & Output

**Reference Issues**: #25, #26, #27, #28

| Question | Decision |
|----------|----------|
| Report audience | **Researchers/Engineers** - detailed technical analysis |
| Visualization | Tables primarily (charts/graphs TBD) |

---

### 8. Operational Concerns

**Reference Issues**: #3, #4, #29, #30

| Question | Decision |
|----------|----------|
| Docker requirement | **Required** - fail if unavailable |
| Minimum runs for stats | 5/9 runs must succeed |

**Still TBD**:
- CI/CD integration details
- Storage management strategy

---

### 9. Edge Cases & Error Handling

**Reference Issues**: #8, #9, #18, #35

| Question | Decision |
|----------|----------|
| Timeout handling | **Include as failures** |
| Judge failures | **Retry with additional passes** |

---

### 10. Research Validity

**Reference Issues**: #37, #24, #20

| Question | Decision |
|----------|----------|
| Baseline | T0 (Vanilla) = **tool default behavior** |
| Reproducibility | Tier prompts documented in config/tiers/ |
| Cross-model testing | **Yes** - test both tiers AND models |

---

## Interview Approach Used

Questions were grouped into batches of 3-4 related topics:

**Batch 1: Core Execution Model**
- API key handling
- Docker availability fallback
- Runs per tier standardization

**Batch 2: Tier System**
- T0 Vanilla definition
- Tier prompt relationship

**Batch 3: Judge System**
- Judge execution context
- Disagreement handling

**Batch 4: Scope**
- Report audience
- First test adapter scope

---

## Completed Actions

### 1. Updated docs/plan.md
- Changed "10 runs" to "9 runs" throughout
- Added testing scope: "tiers AND models"
- Expanded Key Decisions table with all clarifications
- Updated issue titles (#23, #33)

### 2. Updated GitHub Issues with Decision Comments
| Issue | Key Updates |
|-------|-------------|
| #4 | runs_per_tier: 9, API keys via env vars |
| #8 | 9 runs, tiers+models, separate judge container |
| #11 | T0 = tool default behavior, independent tiers |
| #18 | Separate judge container, retry on disagreement |
| #35 | Docker required, API keys via env vars |
| #36 | Independent tier prompts, T0 = tool defaults |

### 3. Created New GitHub Issues
| Issue | Title |
|-------|-------|
| #40 | [Infra] Dockerfile specification for scylla-runner:latest |
| #41 | [Core] Judge container orchestration |
| #42 | [Config] Create tier prompt template files |
| #43 | [Core] Judge consensus with retry logic |

---

## Commands Reference

```bash
# Read issue with comments
gh issue view <number> --comments

# Update issue body
gh issue edit <number> --body-file <file>

# Add comment to issue
gh issue comment <number> --body "..."

# Create new issue
gh issue create --title "..." --body "..." --label "..."

# List all issues
gh issue list --limit 50
```

---

*Review completed 2025-12-28*
