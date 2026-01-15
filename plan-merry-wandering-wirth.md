# Plan: Fill in Paper Sections for docs/paper.md

## Overview

Fill in the `<...>` marked sections in `docs/paper.md` with high-quality academic writing. The paper is about ProjectScylla, an evaluation framework for benchmarking AI agent CLI tools (specifically Claude Code) across different architectural configurations.

**Excluded from this plan**: References section (user will handle manually)

## Implementation Approach

Edit `docs/paper.md` sequentially, replacing each `<...>` placeholder with properly formatted academic content. Use markdown tables for structured data and LaTeX-style math notation (`$...$`) for formulas.

## Sections to Fill In

### 1. Abstract (Line 13)
Write ~150-200 word abstract covering:
- Problem: Lack of rigorous evaluation for AI coding CLI tools
- Approach: Ablation study across 7 tiers (T0-T6) with ~114 sub-tests
- Key contribution: Cost-of-Pass (CoP) economic framework
- Target models: Claude Code with Claude 4.5 family (Opus, Sonnet, Haiku)

### 2. Keywords (Line 19)
Add: `LLM agents, benchmarking, cost-of-pass, multi-agent systems, software engineering, ablation study, prompt engineering`

### 3. Section 3: Related Work - Benchmarks paragraph (Line 60)
Cover:
- SWE-Bench, Agent-Bench, TAU-Bench for task evaluation
- Focus on how they evaluate models vs. our CLI tool focus

### 4. Section 3: Related Work - Prompt harnesses paragraph (Line 62)
Cover:
- PromptBench, PromptEval, lm-evaluation-harness
- Their model-level focus vs our tool-level abstraction

### 5. Section 4.1: Evaluation Categories Table (Line 74)
Create table from rubric data:

| Category | Weight | Description |
|----------|--------|-------------|
| Functional Correctness | 2.0 | Does the solution work as intended? |
| Completeness | 1.5 | Are all requirements addressed? |
| Code Quality | 1.0 | Readability, maintainability |
| Simplicity | 1.0 | Prefer simple working solutions |
| Lack of Duplication | 0.5 | DRY principle |
| Clarity | 1.0 | Clear implementation |
| Documentation | 0.5 | Appropriate comments |
| Architectural Cleanliness | 0.5 | Separation of concerns |
| Efficiency | 0.5 | Resource usage |
| Cleanup Script Quality | 1.0 | Proper teardown |
| Workspace Cleanliness | 1.0 | Proportionate files |
| Test Quality | 1.0 | Appropriate tests |
| Scope Discipline | 1.0 | No over-engineering |

### 6. Section 4.1: Category Weights List (Line 78)
List format with percentages (total weight 12.5)

### 7. Section 4.1: Grade Scale Table (Line 80)
| Grade | Threshold | Description |
|-------|-----------|-------------|
| S | 1.00 | Amazing - exceeds requirements |
| A | 0.80+ | Excellent - production ready |
| B | 0.60+ | Good - minor improvements |
| C | 0.40+ | Acceptable - functional with issues |
| D | 0.20+ | Marginal - significant issues |
| F | <0.20 | Failing - does not meet requirements |

### 8. Section 4.1: Test-001 Example (Line 86)
Include from tests/fixtures/tests/test-001/:
- Task: Create Hello World Python script
- Prompt summary
- Rubric categories (Functional 35%, Code Quality 20%, Proportionality 15%, Build Pipeline 10%, Overall Quality 20%)
- Pass threshold: 0.60

### 9. Section 4.1: Ablation Strategy (Line 91)
Cover tiered approach from research.md and tiers.yaml:
- T0: Empty prompt baseline
- T1-T6 progressive complexity
- ~114 sub-tests total
- Controlled comparison methodology

### 10. Section 4.2: Dimensional Search Space (Lines 95-101)
Define each dimension:
- **Agent Complexity**: T0-T6 tiers
- **Prompt Complexity**: 0-10 scale (empty to full CLAUDE.md)
- **Skill Complexity**: Domain expertise categories
- **Agent Hierarchy**: Flat vs nested vs hybrid

### 11. Section 5: Test Metrics (Lines 104-119)
#### 5.1 Performance Metrics
- Pass-Rate: correct_solutions / total_attempts
- Progress Rate (R_Prog): achieved_steps / expected_steps
- Consistency: 1 - (std/mean)

#### 5.2 Quality Metrics
- Implementation Rate: satisfied_requirements / total_requirements
- LLM-as-Judge validation

#### 5.3 Efficiency/Cost Metrics
- Latency measurements
- Token usage (input/output/tool)
- Cost-of-Pass: total_cost / pass_rate
- Frontier CoP: min across all tiers

### 12. Section 6: Test Configuration (Lines 122-134)
#### 6.1 Hardware/Infrastructure
- Containerized Docker execution
- Standard compute (no GPU required for evaluation)

#### 6.2 Software Stack
- Claude Code CLI
- Python 3.10+
- Mojo 0.26.1 for evaluation infrastructure

#### 6.3 Model Configuration
- Claude Opus 4.5: $5/M input, $25/M output
- Claude Sonnet 4.5: $3/M input, $15/M output
- Claude Haiku 4.5: $1/M input, $5/M output
- Temperature: 0.0, Max tokens: 8192

### 13. Section 7: Test Cases (Lines 138-167)
#### 7.1 PR Selection Criteria
- Small: <100 LOC
- Medium: 300-500 LOC
- Large: 500-2000 LOC

#### 7.2 Workflow Categories
Define each: Build System, CI/CD, Bug Fixing, New Features, Refactoring, Optimization, Review, Documentation, Issue Filing

#### 7.3 Test Case Matrix
Reference tiers.yaml structure

### 14. Section 8: Model Summary (Lines 170-193)
#### 8.1 Claude Code Models
- Opus 4.5: Most capable, highest cost
- Sonnet 4.5: Balanced capability/cost
- Haiku 4.5: Fast, lowest cost

#### 8.2-8.3 Other Models (placeholder)
Acknowledge OpenAI, Gemini, DeepSeek, Qwen, etc. as future work

### 15. Sections 9-12: Placeholder Text for Results/Discussion/Conclusions/Further Work
Add academic placeholder text indicating these sections will be completed after experiments:
- Section 9: "[Quantitative results, comparative analysis, and cost-performance trade-offs to be reported following completion of experimental evaluation across all tiers.]"
- Section 10: "[Discussion of results, implications for agent design, and observed failure modes to be analyzed following experimental completion.]"
- Section 11: "[Summary of findings and answers to research questions to be synthesized from experimental results.]"
- Section 12: "[Proposed extensions and future research directions to be informed by experimental findings.]"

### 16. Appendices (Lines 247-259)
Add placeholder descriptions:
- Appendix A: Reference to metrics-definitions.md
- Appendix B: "[Supplementary tables and figures to be included with experimental results.]"
- Appendix C: "[Reproducibility checklist with configurations and artifact locations.]"

## Critical Files to Reference

| File | Purpose |
|------|---------|
| `docs/research.md` | Primary research methodology (36 citations) |
| `config/tiers/tiers.yaml` | Tier definitions |
| `config/judge/system_prompt.md` | Judge evaluation criteria |
| `tests/fixtures/tests/test-001/` | Hello World example |
| `src/scylla/judge/prompts.py` | Category weights |
| `.claude/shared/metrics-definitions.md` | Metric formulas |

## Writing Style Guidelines

- **Academic tone**: Formal, objective, precise
- **No emojis** per project rules
- **Active voice** where possible
- **Cite existing research.md** content appropriately
- **Use tables** for structured data
- **Mathematical notation** for formulas: `$formula$`

## Detailed Content Drafts

### Abstract Draft (~180 words)
> As large language model-based CLI tools increasingly automate software development tasks, practitioners lack rigorous methods to evaluate how architectural decisions---from prompt engineering to multi-agent hierarchies---affect both capability and cost. We present Scylla, a comprehensive evaluation framework for benchmarking agentic coding tools through a structured ablation study. Our methodology employs seven testing tiers (T0-T6) spanning system prompt variations, domain skills, external tooling, flat delegation, hierarchical orchestration, hybrid combinations, and maximum-capability configurations, encompassing over 114 sub-tests. Using Cost-of-Pass (CoP)---the expected monetary cost to achieve a correct solution---as our primary economic metric, we evaluate Claude Code across multiple Claude model variants. Our LLM-as-Judge protocol employs three independent model evaluators to ensure scoring consistency. This work establishes a reproducible framework for quantifying the trade-offs between architectural complexity and operational efficiency in AI-assisted software development.

### Keywords Draft
> LLM agents, software engineering benchmarks, cost-of-pass, multi-agent systems, prompt engineering, ablation studies, evaluation frameworks, CLI tools, agentic AI

### Related Work - Benchmarks Paragraph Draft
Cover SWE-Bench [2], Agent-Bench [1], TAU-Bench [3] - note that these evaluate models directly, while our work evaluates CLI tools where multiple abstraction layers mediate between prompts and models.

### Related Work - Prompt Harnesses Paragraph Draft
Cover PromptBench [4], PromptEval [5], lm-evaluation-harness [8] - note these operate at model level with direct input/output access, while CLI tools encapsulate models within agentic wrappers.

## Verification

After writing:
1. Read final paper to verify coherence
2. Check all `<...>` markers are replaced
3. Ensure consistent terminology with research.md
4. Verify tables render correctly in markdown
