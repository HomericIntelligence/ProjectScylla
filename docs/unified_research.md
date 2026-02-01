# Project Odyssey: Unified Research Document
## A Comprehensive Blueprint for Benchmarking LLM Agent Architectures

---

## Executive Summary

This unified research document establishes the complete strategic and technical foundation for **Project Odyssey**, a rigorous benchmarking initiative designed to evaluate the marginal utility and economic sustainability of incremental agentic complexity. By integrating the **Architectural Integration Model (AIM)** with a **Cost-of-Pass (CoP)** economic framework, this project addresses the critical "Token Efficiency Chasm" and identifies the "Point of Diminishing Returns" where architectural sophistication no longer justifies its operational cost.

The study encompasses:
- **9 PR workflow categories** across **3 size tiers** (135 total test cases)
- **7 incremental complexity tiers** (T0-T6)
- **12 LLM models** spanning Claude, GPT, Gemini, and open-source alternatives
- **Multi-dimensional search** across agent, prompt, skill, and hierarchy complexity

---

## I. Introduction

### I.A. Problem Statement and Motivation

The effective integration of large language models (LLMs) into autonomous software engineering systems necessitates a rigorous evaluation framework that moves beyond simple success metrics. While sophisticated agent architectures promise increased efficacy, they introduce significant operational overhead requiring economic metrics to evaluate true sustainability.

### I.B. Research Questions

1. What is the optimal tier of architectural complexity for different software engineering tasks?
2. How does the Cost-of-Pass scale across incremental capability tiers?
3. Where is the Point of Diminishing Returns for multi-agent architectures?
4. What hybrid configurations maximize the efficacy-to-cost ratio?

### I.C. Contributions

This paper provides:
- A comprehensive **Incremental Capability Matrix (T0-T6)** for ablative benchmarking
- The **Cost-of-Pass (CoP)** economic framework for agent evaluation
- Empirical analysis of the **Token Efficiency Chasm** between Skills (T2) and Tooling (T3)
- Validation of **Task-Contingent Coordination Laws** for multi-agent systems
- Actionable guidance for production deployment of LLM agents

---

## II. Theoretical Framework

### II.A. Architectural Integration Model (AIM)

The **Architectural Integration Model** provides a predictive framework for determining optimal coordination strategies based on measurable task properties. The core premise mandates that the system must reserve larger, higher-cost models exclusively for strategic planning while deploying smaller, high-throughput models for standardized execution.

#### Biological Analogues for Modular Agent Design

Modern agent design draws parallels to cognitive structures:

| Component | Biological Analogue | Function |
|-----------|---------------------|----------|
| **Task Decomposer** | Anterior Prefrontal Cortex (aPFC) | Abstract planning, goal decomposition |
| **Actor** | Dorsolateral PFC (dlPFC) | Action generation from current state |
| **Monitor** | Anterior Cingulate Cortex (ACC) | Error detection, constraint checking |
| **Evaluator/Predictor** | Orbitofrontal Cortex (OFC) | Heuristic value estimation, self-reflection |
| **Orchestrator** | Executive Function | Progress management, termination |

### II.B. Task-Contingent Coordination Laws

Empirical research validates that coordination is not universally beneficial. The scaling laws dictate:

| Task Type | Coordination Strategy | Performance Delta |
|-----------|----------------------|-------------------|
| Parallelizable (financial reasoning) | Centralized | **+80.9%** |
| Exploratory (web navigation) | Decentralized | **+9.2%** |
| Sequential (rigid planning) | Multi-agent | **-39% to -70%** |

**Critical Thresholds:**
- **Capability Saturation:** Coordination yields diminishing or negative returns once single-agent baseline exceeds ~45% accuracy
- **Error Amplification:** Independent agents amplify failures **17.2x** vs. **4.4x** for centralized coordination

### II.C. Task Dependency Depth (TDD)

**Task Dependency Depth (TDD)** quantifies the maximum effective depth of delegation an agent can manage before system overhead leads to failure:

- **T1 Agents (Utility):** TDD ≤ 2 (direct tool use or single inference step)
- **T2 Agents (Strategic):** TDD ≥ 3 (recursive problem-solving, multi-cycle context)

---

## III. Test Methodology

### III.A. Experimental Design

The study follows a controlled, sequential introduction of agentic capabilities. By benchmarking performance and cost at each incremental step (T(n) versus T(n-1)), the study quantifies the marginal utility of specific architectural components.

### III.B. Dimensional Search Space

The benchmark explores four primary dimensions:

1. **Agent Complexity (Tiers 0-6):** Progressive architectural sophistication
2. **Prompt Complexity (0-10):** From zero-shot to heavily engineered prompts
3. **Skill Complexity:** Domain expertise encoded in prompts
4. **Agent Hierarchy:** Flat, hierarchical, and hybrid configurations

### III.C. Ablation Study Blueprint

Components are systematically removed to quantify marginal contributions:
- Testing T5 with/without Monitor function isolates the cost-benefit of iterative self-correction
- Comparing T3 (Tooling) vs T2 (Skills) quantifies the Token Efficiency Chasm

---

## IV. Test Metrics

### IV.A. Performance Metrics

| Metric | Definition | Purpose | Status |
|--------|------------|---------|--------|
| **Full Completion Score (S_Full)** | Binary/scalar goal completion | Final success measurement | Implemented (Pass-Rate) |
| **Fine-Grained Progress Rate (R_Prog)** | Incremental advancement tracking | Diagnose planning failures | **Excluded** (see §IV.D) |
| **Latency** | Query-to-resolution time | Operational efficiency | Implemented |
| **Consistency** | Output stability on identical inputs | Determinism validation | Implemented |

### IV.B. Quality Metrics

| Metric | Category | Definition | Status |
|--------|----------|------------|--------|
| **Pass-Rate** | Functional | Automated test-case assessment | Implemented |
| **Implementation Rate (Impl-Rate)** | Semantic | LLM-as-Judge requirement verification | Implemented |
| **Change Fail Percentage (CFP)** | Stability | Production changes causing failures | **Excluded** (see §IV.D) |
| **PR Revert Rate** | Quality | Human-rejected agent-generated code | **Excluded** (see §IV.D) |

### IV.C. Economic Metrics

**Cost-of-Pass (CoP)** is the core economic metric:

```
CoP = Expected Cost / Accuracy (R_m(p))
```

Key properties:
- If accuracy = 0, CoP → ∞ (economic infeasibility)
- **Frontier CoP** = min(CoP) across all tiers
- Must be compared against human labor cost for viability assessment

**Granular Cost Tracking:**
- Dynamic calculation with differential input/output token pricing
- Component-level cost breakdown (Orchestrator, Monitor, Tools)
- Token distribution analysis per architectural module

### IV.D. Metric Scope and Exclusions

This study implements a focused subset of metrics optimized for initial publication and practical data collection constraints.

**Implemented Metrics (Core Focus):**
- **Pass-Rate**: Automated test-based success measurement
- **Impl-Rate**: LLM-as-Judge semantic requirement satisfaction
- **Consistency**: Output stability across runs (1 - CV)
- **CoP**: Cost-of-Pass economic viability
- **Latency**: Query-to-resolution time
- **Token Distribution**: Component-level cost breakdown
- **Krippendorff's Alpha**: Inter-rater reliability for judge consensus

**Excluded Metrics (Future Work):**

| Metric | Status | Exclusion Rationale |
|--------|--------|---------------------|
| **R_Prog** (Fine-Grained Progress) | Not Implemented | Requires execution trajectory instrumentation not present in current data collection. Would need: (1) task-specific step definitions, (2) progress tracking during agent execution, (3) expected vs. achieved step comparison. Impl-Rate provides adequate granularity for requirement satisfaction without trajectory analysis. |
| **Strategic Drift** | Not Implemented | Requires goal alignment tracking across intermediate actions. Current architecture focuses on final outcomes rather than intermediate state analysis. |
| **CFP** (Change Fail Percentage) | Not Implemented | Requires multi-run stability analysis with failure attribution. Current study focuses on single-run quality metrics. |
| **PR Revert Rate** | Not Implemented | Requires human code review integration and production deployment tracking beyond current scope. |
| **Ablation Score** | Not Implemented | Tier comparison methodology (T0-T6) provides architectural contribution analysis without requiring explicit ablation scoring. |

**Design Rationale:**

The implemented metrics provide:
1. **Functional Coverage**: Pass-Rate measures correctness via automated tests
2. **Semantic Coverage**: Impl-Rate captures requirement satisfaction beyond binary pass/fail
3. **Economic Viability**: CoP enables cost-benefit analysis across tiers
4. **Statistical Rigor**: Krippendorff's Alpha validates judge consensus
5. **Process Efficiency**: Latency and token distribution identify bottlenecks

This focused metric set enables:
- Rigorous tier comparison (primary research question)
- Economic sustainability assessment
- Publication-quality statistical analysis
- Practical data collection with existing infrastructure

Future iterations may incorporate excluded metrics pending:
- Enhanced agent instrumentation for trajectory tracking
- Multi-run stability analysis infrastructure
- Human review integration for production quality metrics

---

## V. Test Configuration

### V.A. PR Size Categories

| Category | Lines of Code | Complexity |
|----------|---------------|------------|
| Small | < 100 LOC | Low |
| Medium | 300-500 LOC | Moderate |
| Large | 500-2000 LOC | High |

### V.B. Workflow Categories

Nine representative software engineering workflows, each with 5 PRs per size category:

1. **Build System:** Build configuration, dependency management
2. **CI/CD:** Pipeline configuration, deployment automation
3. **Bug Fixing:** Defect resolution, regression fixes
4. **New Features:** Feature implementation, API additions
5. **Refactoring:** Code restructuring, pattern application
6. **Optimization:** Performance improvements, resource efficiency
7. **Review:** Code review suggestions, PR feedback
8. **Documentation:** Doc generation, comment updates
9. **Issue Filing:** Bug reports, feature requests

**Total Test Cases:** 9 workflows × 3 sizes × 5 PRs = **135 test cases per tier**

---

## VI. The Incremental Capability Matrix (T0-T6)

### VI.A. Tier Definitions

| Tier | Name | Feature Enabled | Primary Function | Dominant Cost Driver | Hypothesized Viability |
|------|------|-----------------|------------------|---------------------|----------------------|
| **T0** | Vanilla | Base LLM (Zero-shot) | Baseline establishment | Single inference cost | Low CoP, Low Efficacy |
| **T1** | Prompted | System Prompt + CoT | Context engineering | Input token cost | Low CoP, Moderate Efficacy |
| **T2** | Skills | Prompt-Encoded Expertise | Domain judgment | Context (mitigated) | **Excellent CoP**, High Efficacy |
| **T3** | Tooling | External API/Schemas | Real-world execution | Schema token overhead | High Efficacy, **Poor CoP** |
| **T4** | Delegation | Flat Multi-Agent | Atomic task design | Orchestration latency | High Efficacy, Moderate CoP |
| **T5** | Hierarchy | Nested Orchestration | Deep planning + verification | Iterative verification | Very High Efficacy, High CoP |
| **T6** | Hybrid | Optimal Combinations | Economic optimization | Synergistic overhead | **Maximized CoP Ratio** |

### VI.B. The Token Efficiency Chasm (T2 vs. T3)

A critical economic distinction exists at the Skills vs. Tooling boundary:

**T2 (Skills):**
- Domain knowledge encoded in prompts
- Token-efficient representation
- High efficacy for judgment-based tasks

**T3 (Tooling):**
- External functions via JSON schemas
- Agents load comprehensive libraries "just in case"
- Results in **50,000-150,000 token** context consumption
- Sharp CoP decline despite standardized interface benefits

### VI.C. Architectural Agentification (T4-T5)

**T4 - Flat Delegation (Atomic Task Design):**
- Breaks workflows into narrow, stateless tasks
- Production results: **54% cost reduction**, **72% latency drop**
- Optimized for parallelizable task patterns

**T5 - Nested Hierarchy:**
- Pyramid structure with Monitor/Evaluator loops
- Critic verification **doubles inference per iteration**
- Essential for long-horizon, complex problem solving
- Must justify CoP increase through robustness gains

### VI.D. Hybrid Optimization (T6)

Optimal configurations combine:
- T2's token-efficient Skills
- T4's Atomic Delegation patterns
- **Agentic RAG:** Dynamic tool direction based on retrieved context
- Empirical findings: **78% error rate reduction** vs. traditional RAG

---

## VII. Model Summary

### VII.A. Claude Code Suite

| Model | Role | Configuration |
|-------|------|---------------|
| **Claude Opus** | Strategic orchestration (T2) | Max context, highest reasoning |
| **Claude Sonnet** | Balanced execution (T1/T2) | Cost-effective, high quality |
| **Claude Haiku** | High-throughput utility (T1) | Fast, low-cost, deterministic |

### VII.B. OpenAI/Codex

| Model | Role | Configuration |
|-------|------|---------------|
| **GPT-5.2 / Codex** | Code-specialized agent | Extended context, code-tuned |

### VII.C. Large Model CLI-Based Systems

All models evaluated in CLI-based agentic workflows:

| Model | Provider | Specialization |
|-------|----------|----------------|
| Claude Opus | Anthropic | General reasoning |
| OpenAI GPT-5.2 | OpenAI | Code + reasoning |
| Gemini 3.0 Pro | Google | Multi-modal |
| DeepSeek | DeepSeek AI | Code + reasoning |
| Qwen 3 | Alibaba | Open-source |
| MBZ-K2 | TII/UAE | Open-source |
| Kimi-K2 | Moonshot | Extended context |
| Kimi-3 | Moonshot | Extended context |

---

## VIII. Expected Results

### VIII.A. Tier Performance Patterns

Based on theoretical analysis and preliminary findings:

1. **T0-T1:** Establishes baseline; minimal cost, limited efficacy on complex tasks
2. **T2:** Expected sweet spot for judgment-heavy tasks; best CoP efficiency
3. **T3:** Efficacy spike with severe CoP degradation (Token Efficiency Chasm)
4. **T4:** Strong performance on parallelizable workflows; validated atomic patterns
5. **T5:** Highest raw efficacy; must justify 2x+ cost through stability metrics
6. **T6:** Optimal hybrid configurations; best overall CoP/Efficacy ratio

### VIII.B. Workflow-Specific Hypotheses

| Workflow | Best Tier | Rationale |
|----------|-----------|-----------|
| Bug Fixing | T4/T5 | Requires exploration + verification |
| Refactoring | T2/T4 | Pattern application, atomic changes |
| Documentation | T2 | Judgment-based, token-efficient |
| New Features | T5/T6 | Long-horizon planning required |
| CI/CD | T3/T4 | External tool integration |

---

## IX. Conclusions

### IX.A. Point of Diminishing Returns

The study will identify the specific complexity tier where marginal architectural complexity leads to exponentially rising CoP not justified by performance gains. Preliminary analysis suggests:

- **T4** represents optimal balance for most parallelizable tasks
- **T5** justified only for long-horizon problems requiring verification
- **T6 hybrid** configurations achieve best frontier CoP

### IX.B. Key Takeaways

1. **Token Efficiency Chasm** is a critical economic barrier at T3
2. **Atomic Task Design** (T4) provides consistent cost-latency benefits
3. **Task-Contingent Coordination** must match strategy to task characteristics
4. **Skills > Tools** for judgment-based tasks (T2 > T3 for CoP)
5. **Hybrid T6** configurations combining Skills + Delegation optimize economic sustainability

---

## X. Further Work

### X.A. Statistical Framework Enhancement

Future research will employ **Hierarchical Bayesian Generalised Linear Models (HiBayES)** to properly account for the asymmetric and multi-level structure of evaluation data across tiers, workflows, and models.

### X.B. Extended Benchmarking

- Expand to additional task domains beyond software engineering
- Incorporate real-time production metrics (CFP, revert rates)
- Develop automated tier-selection systems based on task profiling

### X.C. Optimization Strategies

- Model distillation for Monitor/Critic roles to reduce T5 costs
- Dynamic tool loading to mitigate T3 Token Efficiency Chasm
- Adaptive coordination strategy selection based on task characteristics

---

## References

1. AWS - What are AI Agents?
2. GitHub - agentic-ablation: Automated neural network ablation studies
3. Emergent Mind - Modular LLM-Agent Architecture
4. Emergent Mind - Hierarchical Agentic Taxonomy
5. arXiv - Zero-shot 3D Map Generation with LLM Agents
6. OpenReview - AgentBoard: An Analytical Evaluation Board
7. arXiv - AgentBoard: Multi-turn LLM Agents
8. arXiv - TheAgentCompany: Benchmarking LLM Agents
9. Frontiers - Large language models in zero-shot semantic annotation
10. Arkon Data - Agentic AI Frameworks Comparison
11. Anthropic - Effective context engineering for AI agents
12. Arcade Blog - Skills vs Tools for AI Agents
13. arXiv - Review of Tools for Zero-Code LLM Application Development
14. Medium - Token-Efficient Agent Architecture
15. arXiv - Self-Resource Allocation in Multi-Agent LLM Systems
16. HockeyStack - Optimizing Latency and Cost in Multi-Agent Systems
17. ResearchGate - InfiAgent: Self-Evolving Pyramid Agent Framework
18. Medium - AI Agent Evaluation: Frameworks and Best Practices
19. Evidently AI - LLM evaluation metrics
20. Vellum AI - Agentic RAG: Architecture and Limitations
21. Moonlight - Benchmarking LLM-based Agent Systems
22. arXiv - BenchAgents: Multi-Agent Systems for Benchmark Creation
23. GitHub - Cost-of-Pass: An Economic Framework
24. OpenReview - Cost-of-Pass Framework
25. NVIDIA - LLM Inference Benchmarking
26. DX - Three metrics for measuring AI impact on code quality
27. AISI - HiBayES: Hierarchical Bayesian modelling for LLM evaluation
