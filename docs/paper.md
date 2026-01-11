# Taming Scylla

## Understanding the multi-headed agentic deamon of the coding seas

Micah Villmow
Individual
research@villmow.us

---

## Abstract

As large language model-based CLI tools increasingly automate software development tasks, practitioners lack rigorous methods to evaluate how architectural decisions---from prompt engineering to multi-agent hierarchies---affect both capability and cost. We present Scylla, a comprehensive evaluation framework for benchmarking agentic coding tools through a structured ablation study. Our methodology employs seven testing tiers (T0-T6) spanning system prompt variations, domain skills, external tooling, flat delegation, hierarchical orchestration, hybrid combinations, and maximum-capability configurations, encompassing over 114 sub-tests. Using Cost-of-Pass (CoP)---the expected monetary cost to achieve a correct solution---as our primary economic metric, we evaluate Claude Code across multiple Claude model variants. Our LLM-as-Judge protocol employs three independent model evaluators to ensure scoring consistency. This work establishes a reproducible framework for quantifying the trade-offs between architectural complexity and operational efficiency in AI-assisted software development.

---

## Keywords

LLM agents, software engineering benchmarks, cost-of-pass, multi-agent systems, prompt engineering, ablation studies, evaluation frameworks, CLI tools, agentic AI

---

## 1. Summary

<High-level executive summary of the research goals, experimental setup, major findings, and implications.>
With the advancement of large language models has come a massive increase in capabilities for automated computer interactions. What used to require hand-coded algorithms and pipelines can now be done automatically using state of the art coding models to generate instructions that can then be utilized to further improve automated approaches. However, understanding what improves these language models is more of black magic than art, let alone a rigorous science. This paper's goal is to help demistify the magic of prompt engineering by proposing a rigorous evaluation framework across multiple dimensions to help determine how agents interact, the scale that of changes for the agentics, and an attempt to quantify with numbers the benefits of each approach across a broad range of activities.

There are benchmarks for measuring LLM's workflows in various domains, such as agent-bench[1], swe-bench[2], tau-bench[3], etc... There are also prompt evaluation benchmarks such as PromptBench[4] or PromptEval[5]. This paper focuses specifically on coding tools, specifically industry leading tool Claude Code[7], and how prompt modification can change the behavior of the model for better or for worse. This paper also introduces a framework for evaluating other tools in a systematic way, thus allowing extension to domains outside of CLI based coding tools. We show that <insert findings here>. 

This implies that there is still a <summarize implications> and repost here.

---

## 2. Introduction

Anthropic has many good resources for improving Claude Code on their engineering blog, but there is not a simple way to measure easily whether changes to the prompt instructions actually benefit in the way that the user can easily comprehend. Therefor, I am introducing Scylla, a testing framework for evaluating prompts, tools, skills, and agents for solving problems that are common for day to day coding tasks. I wanted to know if sub-agents, skills, tools, or mcp servers were actually contributing to improved code output, without relying on my gut or intuition. This problem came up multiple times when asked by others to explain how to better utilize CLI tools for programming. In my experience, the quality of the prompts has a dramatic improvement on the output of the results. Whether its the prompt to call the tool or MCP server, the prompt to spawn a sub-agent, or the prompt to trigger a skill, these language based triggers are fuzzy in their meaning, unlike a traditional programming language that is very explicit in what it is means and what it does.

First, in section 3, I will introduce the current work that is being done in this area, and explain how they approach the problem. Then, in section 4, I will introduce the testing methodology along with an in-depth analysis of the first test case. This will provide the needed understanding of what is being tested and why on something that should be easily dissectable and understandable. The next three section will introduce three more test cases of varying tasks and complexity that show the variance of results from the various prompts. After that, I will dissect some of the more interesting cases where there was large impacts on the baseline behavior of the model. The final section will showcase the final results across a larger set of test cases, and point to further areas of research and how to extend this to other models.

The questions I am investigating are:
* Is it possible to quantify whether a task is solveable more efficiently by one methodology over others?
* Is the sum of a prompt more than the individual parts? 
* Are there core improvements that can be made purely through extensions to claude code that are generic for all workloads?
* Are there specific prompt techniques that have secondary effects, positive or negative, on other prompt techniques?
* Holding the tool and prompt constant, how much does the underlying model contribute to the quality of the results?

Some hypotheses I have are:
* Certain tasks excel when run as sub-tasks, or tools, or mcp, or skills, that are unrelated to context management.
* Prompt complexity has a negative correlation to higher quality results, i.e. KISS principle, in scenarious that is part of the training set.
* Prompt complexity has a positive correlation to higher quality results, i.e. an inverse KISS principle, in scenerios outside of the training set.

---

## 3. Related Work

I am sure there are other work in this category, but I do not know of them yet, so I will fill this in later once I learn more. Given that we are testing production tools and not models, many, if not all, of the prior work on evaluating prompts and benchmarks does not apply directly here, since there is possibly a large level of indirection between what we are testing and what actually gets executed by the model. The model is hidden behind multiple black boxes, first being the CLI tool itself, but also whatever optimizations and implementation details the vendor implemnents on top of their trained base model. The models themselves aren't not documented publicly, as these details are competitive advantages.

There are multiple benchmarks on judging the models, such as agent-bench[1], swe-bench[2], and tau-bench[3], but no standard benchmarks on these CLI tools on how prompts affect them. The reader can also investigate PromptEval, PromptBench, or lm-evaludation-harness[8], but these also don't benchmark the CLI tools, which are used in production today. The next paragraphs will explain in high level details the various other options on the market.

Several benchmarks have emerged for evaluating LLM agent capabilities. SWE-Bench[2] evaluates models on real-world software engineering tasks derived from GitHub issues, measuring the ability to resolve bugs and implement features in actual codebases. Agent-Bench[1] provides a comprehensive toolkit for assessing multi-turn LLM agents across diverse environments including operating systems, databases, and knowledge graphs, offering fine-grained progress metrics beyond binary success rates. TAU-Bench[3] focuses on tool-augmented agents, measuring how effectively models leverage external tools to accomplish complex tasks. While these benchmarks evaluate model capabilities directly, they do not address the evaluation of production CLI tools where multiple layers of abstraction---including the agentic loop, hooks, skills, and vendor-specific optimizations---mediate between the prompt and the underlying model. Our work bridges this gap by focusing specifically on the tool interface rather than the raw model.

Prompt evaluation frameworks provide systematic approaches for assessing prompt effectiveness. PromptBench[4] offers a unified framework for evaluating prompts across diverse tasks, enabling comparison of different prompting strategies. PromptEval[5] focuses on automated evaluation of prompt quality, measuring both functional correctness and prompt robustness under perturbation. The lm-evaluation-harness[8] from EleutherAI provides a standardized benchmark suite for comparing language model performance across hundreds of tasks with consistent evaluation protocols. These frameworks, however, operate at the model level rather than the tool level. They assume direct access to model inputs and outputs, whereas production CLI tools like Claude Code encapsulate the model within an agentic wrapper that includes system prompts, tool schemas, skill definitions, and orchestration logic. Our evaluation methodology extends these approaches to the tool abstraction level, treating the CLI interface as the primary boundary for prompt injection and output assessment.

My work is based solely on evaluating CLI tools, as the CLI's tools are more than the model themselves, but the agentic loop, with hooks, tools, skills, sub-agents, MCP servers, and other logic wrapped together into a single application where the only way to get control of the behavior is through the english language. From this interface, programmatic tools can be spawned, but the ability to properly and accurately interact with the agent is via a fuzzy language interface, and not via traditional programmatic interfaces. While there are some hooks that allow extra programmatic validation with Claude Code, we are not evaluating those at this time. Claude code has the ability to use agentic evaluation at the hook boundary, but triggering it is guaranteed, and not language based.

---

## 4. Test Methodology

### 4.1 Experimental Design

The experiment is designed by testing english phrases, colloqually known as prompts, via the various methodologies exposed by the tools, in this case Claude Code. The experiment is run by allowing an agent a nearly unfeatered access to the system, only blocked by dangerous ops thanks to the safety-net plugin[9] from cc-marketplace, to perform a task. The task has a well defined solution that is then judged by three different LLM's of various 'strength'. In this case Claude Opus 4.5, Claude Sonnet 4.5, and Claude Haiku 4.5. Each of the 4.5 models are sufficiently advanced in capabilities to be considered independent judges of a task. The judges are provided the same prompt, so the only difference between their results comes from the judge training and implementation differences and not from the prompt or test input. Each judge will receive the output of the task LLM, and provide the results based on the criteria. The judges have the following categories of evaluation; functional correctness, code quality, development pipeline, securty and safety, proportionality and professionalism, and patchfile correctness.

**Table 4.1: LLM-as-Judge Evaluation Categories**

| Category | Weight | Scoring Type | Description |
|----------|--------|--------------|-------------|
| Functional Correctness | 0.35 | Checklist | File existence, output correctness, exit codes, exact output matching |
| Code Quality | 0.20 | Checklist | Syntax validity, idiomatic code, unused imports, PEP8 compliance |
| Proportionality | 0.15 | Checklist | Appropriate scope, minimal files, no unnecessary artifacts or tests |
| Build Pipeline | 0.10 | Checklist | Build passes, format checks, tests (when applicable), pre-commit hooks |
| Overall Quality | 0.20 | Subjective | Engineering judgment on appropriateness, maintainability, and senior engineer approval |

**Total Weight**: 1.0 (100%)

Each category contributes proportionally to the final score. The final score is calculated as:

$$S_{final} = \sum_{i} w_i \cdot \frac{P_i^{achieved}}{P_i^{max}}$$

where $w_i$ represents category weights summing to 1.0, and $P_i$ represents points achieved versus maximum applicable points (excluding N/A items). Individual checklist items within each category are scored using:

- **Binary items**: Full points (1.0) or zero (0.0) with no middle ground
- **Graduated items**: Continuous score 0.0-1.0 proportional to degree of satisfaction
- **Subjective items**: Calibrated assessment using deduction tiers

**Deduction Calibration Scale** (for subjective assessment):

| Severity | Deduction Range | Examples |
|----------|----------------|-----------|
| Negligible | 0.00-0.05 | IDE config files, `__pycache__` artifacts |
| Trivial | 0.05-0.15 | Missing trailing newlines, unused imports |
| Minor | 0.15-0.30 | Missing docstrings, magic numbers |
| Moderate | 0.30-0.50 | Code duplication, hardcoded values |
| Major | 0.50-0.80 | Non-critical security issues, race conditions |
| Severe | 0.80-1.50 | Critical security vulnerabilities |
| Critical | 1.50+ | Non-functioning solutions, destructive operations |

The final score results in one of six grades following an industry-aligned scale:

**Table 4.2: Industry-Aligned Grade Scale**

| Grade | Threshold | Label | Production Interpretation |
|-------|-----------|-------|---------------------------|
| S | 1.00 | Amazing | Exceptional work exceeding requirements; ship immediately |
| A | ≥ 0.80 | Excellent | Production ready; ship with confidence |
| B | ≥ 0.60 | Good | Minor improvements possible; ship after fixes |
| C | ≥ 0.40 | Acceptable | Functional with issues; rework required |
| D | ≥ 0.20 | Marginal | Significant issues; substantial rework |
| F | < 0.20 | Failing | Does not meet requirements; restart |

The default pass threshold is **0.60** (Grade B), representing solutions that are functional and meet requirements with minor improvements possible. The S grade requires a perfect score of 1.00 and explicit citation of work exceeding requirements.

Each experiment can be reproduced by running either the agent script, the judge script, or the test run script. The test run script will properly run the agent script followed by the test run script.

This finishes the summary of a single test. However, the test themselves are defined differently. The test are a prompt and a configuartion file that specify a repository, a github hash, a set of configuration files to override any pre-defined tooling, and a container to run everything in to help with reproducibility. The first test is being used as an example in this paper, and also as a pipecleaner to show that everything works as expected. This example is 'hello world' from octocat, but forked to my repository just to make sure that the repository is not polluted incase the agents make mistakes or do things that the original author probably does not want.

#### Test-001: Hello World Baseline

As a baseline validation, we employ a minimal "Hello World" task designed to verify framework functionality while establishing performance expectations for trivial tasks.

**Test Configuration:**

| Field | Value |
|-------|-------|
| ID | `test-001` |
| Name | Hello World Task |
| Timeout | 300 seconds |
| Pass Threshold | 0.60 (Grade B) |

**Task Prompt:**

Create a Python script `hello.py` that prints "Hello, World!" to stdout, exits with code 0, and uses relative paths. The script should be created in the current working directory.

**Expected Output:**
```
Hello, World!
```

**Rubric Categories and Weights:**

| Category | Weight | Key Criteria |
|----------|--------|--------------|
| Functional Correctness | 35% | File `hello.py` exists; running `python hello.py` produces correct output; exit code 0; output exactly matches |
| Code Quality | 20% | Valid Python syntax; idiomatic code; no unused imports; PEP8 compliant |
| Proportionality | 15% | Total files ≤ 3; LOC ≤ 3; no unnecessary test files; build artifacts cleaned up |
| Build Pipeline | 10% | Syntax check passes; format check passes (if ruff available); tests pass (if required) |
| Overall Quality | 20% | Senior engineer approval; appropriately scoped for Hello World |

**Baseline Expectation:** For this trivial task, T0 (no system prompt) should achieve near-perfect scores (≥0.90), establishing that the framework correctly measures simple tasks before introducing prompt complexity. Higher tiers (T1-T6) are expected to maintain similar performance, as additional architectural complexity provides no benefit for such straightforward tasks. Any significant degradation in performance on this baseline indicates framework issues or harmful prompt interference.

Now that we have gone over the test itself, lets discuss the strategy and tiered approach. The first thing to test is with no prompt at all, including no system prompt. This is to provide as close to a baseline as the base model as possible by overwriting the system prompt with an empty string and not using any configuration or non-default settings from the tool. This provides the baseline that all improvements are measured against. For something as simple as hello world, this baseline should solve the task. The test setup is such that variability in judging will occur, but there is not much one can do to improve the output of a hello world script. However, there are things that you can do that make things worse or break the expected behavior, but I would expect most solutions to be the exact same for all the tests.

#### Tiered Ablation Strategy

Our ablation study employs a seven-tier architecture that progressively introduces agent capabilities, enabling isolation of marginal contributions from each architectural component. The framework encompasses **~114 sub-tests** distributed across tiers, with each tier evaluated independently before advancing to more complex configurations.

**Table 4.3: Testing Tiers (Ablation Study Framework)**

| Tier | Name | Sub-tests | Primary Focus | Tools | Delegation | Key Characteristic |
|------|------|-----------|---------------|-------|------------|-------------------|
| T0 | Prompts | 24 | System prompt ablation (empty → full) | - | No | Baseline: empty prompt (00) through full 1787-line CLAUDE.md (03) plus 18 individual blocks (B01-B18) |
| T1 | Skills | 11 | Domain expertise via installed skills | Default | No | Token-efficient domain knowledge; categories: Agent (5), CI/CD (7), Documentation (4), GitHub (10), Mojo (10), Quality (5), Workflow (5) |
| T2 | Tooling | 15 | External tools and MCP servers | Yes | No | External API access; introduces token efficiency chasm from schema loading |
| T3 | Delegation | 41 | Flat multi-agent with specialists | Yes | Yes | Atomic task design; flat orchestration with specialist agents (L2-L5) |
| T4 | Hierarchy | 7 | Nested orchestration with orchestrators | Yes | Yes | Hierarchical coordination (L0-L1); Task Decomposer, Actor, Monitor, Evaluator roles |
| T5 | Hybrid | 15+ | Optimal combinations from all tiers | Yes | Yes | Combines T2 skills + T4 delegation + selective verification; targets frontier Cost-of-Pass |
| T6 | Super | 1 | Maximum capability configuration | All | All | Theoretical maximum: 61 skills, all MCP servers, 44 agents, full prompt; establishes capability ceiling |

**Progressive Evaluation Methodology:**

1. **T0 (Baseline):** Tests range from empty system prompt (00-empty) establishing raw model capability, through full 1787-line CLAUDE.md prompt (03-full) representing maximum prompt complexity. Individual block tests (06-B01 through 23-B18) enable isolation of specific prompt component contributions.

2. **T1-T2 (Resource Augmentation):** Contrasts token-efficient skills (T2) versus token-heavy tooling (T3). T2 encodes domain expertise directly in prompts, avoiding massive JSON schema overhead. T3 introduces the "Token Efficiency Chasm" where comprehensive tool libraries can consume 150,000+ tokens before reasoning begins.

3. **T3-T4 (Architectural Agentification):** T3 implements flat delegation with atomic task design, showing production cost reductions of 54% and latency improvements of 72% through specialized, stateless agents. T4 introduces nested hierarchy with iterative self-correction loops that can double inference requirements per iteration.

4. **T5 (Optimization):** Synthesizes proven components: T2's token efficiency, T4's atomic delegation, selective rather than mandatory verification, and agentic RAG for dynamic retrieval. Aims to maximize quality-to-cost ratio.

5. **T6 (Theoretical Bound):** Everything enabled simultaneously to establish the upper performance bound and maximum cost baseline. Expected to show diminishing returns due to compounded overhead.

**Controlled Comparison:** For every tier T(n), performance and Cost-of-Pass metrics are compared directly against T(n-1), quantifying the marginal utility of newly introduced architectural features.

### 4.2 Dimensional Search Space

The evaluation framework explores multiple orthogonal dimensions that collectively define the agent configuration space. Each dimension represents a distinct architectural decision with measurable impacts on both capability and cost.

#### 4.2.1 Agent Complexity Axis (Tiers 0-6)

Agent complexity is operationalized through our tiered architecture:

| Tier Range | Complexity Level | Description |
|------------|------------------|-------------|
| T0-T1 | Single-agent, prompt-only | Base model with varying prompt sophistication |
| T2 | Single-agent with tools | External API access via tool schemas |
| T3 | Multi-agent, flat | Specialist agents with central orchestrator |
| T4-T5 | Multi-agent, hierarchical | Nested orchestration with self-correction loops |
| T6 | Maximum configuration | All features enabled simultaneously |

#### 4.2.2 Prompt Complexity Axis

Prompt complexity is measured in lines of system prompt content, ranging from 0 (empty) to 1787 (full CLAUDE.md):

| Level | Lines | Description | Representative Test |
|-------|-------|-------------|---------------------|
| Empty | 0 | No system prompt | T0-00-empty |
| Minimal | ~55 | Safety rules only | T0-06-B02 |
| Core | ~260 | Essential blocks (B02, B07, B18) | T0-03-core |
| Standard | ~400 | Seven core blocks | T0-02-standard |
| Full | 1787 | All 18 CLAUDE.md blocks | T0-03-full |

Individual blocks (B01-B18) can be tested in isolation to determine their specific contributions to performance and cost.

#### 4.2.3 Skill Complexity Axis

Skills are categorized by domain and tested in isolation within T2:

| Category | Count | Example Domains | Token Efficiency |
|----------|-------|-----------------|------------------|
| Agent | 5 | Agent management patterns | High |
| CI/CD | 7 | Build and deployment automation | High |
| Documentation | 4 | Technical writing assistance | Medium |
| GitHub | 10 | Repository management | Medium |
| Mojo | 10 | Mojo language specific | High |
| Quality | 5 | Code quality and review | Medium |
| Workflow | 5 | Development workflow patterns | High |

**Total**: 46 skills across 7 categories. Skills encode domain knowledge directly in prompts, avoiding the token overhead of equivalent tool schemas (typically 50,000+ tokens saved).

#### 4.2.4 Agent Hierarchy Axis

Three organizational patterns are evaluated across T3-T5:

| Pattern | Coordination | Communication Overhead | Use Cases |
|---------|--------------|------------------------|-----------|
| **Flat** | No supervision; peer-to-peer | Low | Simple, independent tasks |
| **Hierarchical** | L0-L4 levels with explicit supervision | High | Complex, interdependent tasks requiring planning |
| **Hybrid** | Selective hierarchy based on task complexity | Medium | Adaptive: flat for simple tasks, hierarchical for complex |

The hierarchy axis directly impacts token distribution costs, as each supervision layer introduces additional orchestration tokens and potential iterative refinement cycles.

---

## 5. Test Metrics

### 5.1 Performance Metrics

**Pass-Rate** measures binary task completion:

$$\text{Pass-Rate} = \frac{\text{correct\_solutions}}{\text{total\_attempts}}$$

**Range**: [0, 1]. A value of 0.0 indicates no correct solutions; 1.0 indicates all solutions correct. "Correct" is defined by task-specific test suite execution. Results should be reported with confidence intervals (95% CI recommended for $n \geq 30$).

**Fine-Grained Progress Rate** ($R_{Prog}$) captures incremental advancement through multi-step tasks:

$$R_{Prog} = \frac{\text{achieved\_progress\_steps}}{\text{expected\_progress\_steps}}$$

**Range**: [0, 1+]. Values exceeding 1.0 indicate beneficial additional steps beyond the minimum required path. This metric enables diagnosis of where agents succeed or fail in complex workflows, particularly valuable for T4-T5 hierarchical architectures with iterative self-correction.

**Consistency** measures output stability across identical inputs:

$$\text{Consistency} = 1 - \frac{\sigma(\text{outputs})}{\mu(\text{outputs})}$$

**Range**: [0, 1], where higher values indicate more deterministic behavior. Particularly relevant for T6 configurations with structured output commands designed to improve reliability.

### 5.2 Quality Metrics

**Implementation Rate** (Impl-Rate) measures semantic requirement satisfaction:

$$\text{Impl-Rate} = \frac{\text{satisfied\_requirements}}{\text{total\_requirements}}$$

**Range**: [0, 1]. Provides finer granularity than binary Pass-Rate by capturing partial credit for incomplete solutions. Verified using LLM-as-Judge (autorater) protocol with three independent model evaluators (Opus 4.5, Sonnet 4, Haiku 4.5) and consensus scoring via median.

**Change Fail Percentage** (CFP) measures production stability:

$$\text{CFP} = \frac{\text{failed\_changes}}{\text{total\_changes}}$$

**Range**: [0, 1]. Lower values indicate more stable, maintainable output. A "failed change" requires immediate remediation (rollback or hotfix). This metric counters raw efficacy claims: high Impl-Rate with high CFP suggests brittle, high-maintenance artifacts.

**PR Revert Rate** measures code quality from agent-generated changes:

$$\text{PR\_Revert\_Rate} = \frac{\text{reverted\_prs}}{\text{merged\_prs}}$$

Real-time quantitative metric tracking frequency of discarded changes due to quality or architectural concerns.

### 5.3 Efficiency and Cost Metrics

**Latency** measures time from query submission to task completion (seconds). Components include:
- Time-to-First-Token (TTFT)
- Total response time
- Tool execution time

Critical for quantifying the operational penalty of iterative architectures (T5), where verification loops significantly increase response time.

**Token Distribution** tracks usage by component type:

$$\text{token\_dist} = \left\{ \frac{\text{input\_tokens}}{\text{total\_tokens}}, \frac{\text{output\_tokens}}{\text{total\_tokens}}, \frac{\text{tool\_input\_tokens}}{\text{total\_tokens}}, \frac{\text{tool\_output\_tokens}}{\text{total\_tokens}} \right\}$$

Enables component-level cost breakdown for identifying cost drivers (e.g., T3's JSON schema overhead, T4's orchestration tokens).

**Cost-of-Pass (CoP)** is our primary economic metric:

$$\text{CoP} = \frac{\text{total\_cost}}{\text{pass\_rate}}$$

**Unit**: USD. **Range**: [0, ∞). Lower values indicate better cost-efficiency. CoP approaches infinity as pass_rate approaches zero, signaling economic infeasibility. Integrates both inference cost and model accuracy into a single sustainability metric.

**Frontier CoP** identifies the optimal configuration:

$$\text{Frontier\_CoP} = \min(\text{CoP}_{T0}, \text{CoP}_{T1}, \ldots, \text{CoP}_{T6})$$

Represents the minimum Cost-of-Pass achievable across all evaluated tiers. Compared against human expert baseline to validate economic viability.

**Model Pricing** (as of January 2026):

| Model | Input ($/1M tokens) | Output ($/1M tokens) |
|-------|---------------------|----------------------|
| Claude Opus 4.5 | $15.00 | $75.00 |
| Claude Sonnet 4 | $3.00 | $15.00 |
| Claude Haiku 4.5 | $1.00 | $5.00 |

---

## 6. Test Configuration

### 6.1 Hardware and Infrastructure

| Component | Specification |
|-----------|---------------|
| Platform | Linux (WSL2) |
| Kernel | 6.6.87.2-microsoft-standard-WSL2 |
| Execution Environment | Containerized (Docker) for reproducibility |
| Isolation | Each test runs in clean workspace |
| Compute | Standard CPU (no GPU required for evaluation) |

Tests execute in isolated Docker containers with repository state restored to specified git hash before each run. This ensures reproducibility across runs and prevents cross-contamination between test cases. Each test receives a fresh container instance with:

- Clean git workspace at specified commit
- Tier-specific configuration files
- Tool/skill definitions as per tier requirements
- Isolated file system for artifact collection

### 6.2 Software Stack

| Component | Version/Tool |
|-----------|--------------|
| CLI Tool | Claude Code (primary evaluation target) |
| Language Runtime | Python 3.12+, Mojo 0.26.1 |
| Package Manager | Pixi |
| Container Runtime | Docker |
| Orchestration | Custom Scylla framework (Mojo implementation) |
| Validation | JSON Schema, YAML validation |
| Version Control | Git |

The evaluation harness coordinates five phases:

1. **Workspace Preparation**: Git clone, checkout specific hash, inject tier configuration
2. **Agent Execution**: Launch Claude Code with tier-specific system prompt and tools
3. **Output Capture**: Collect agent output, command logs, workspace diff, artifacts
4. **Judge Invocation**: Three parallel LLM-as-Judge evaluations (Opus, Sonnet, Haiku)
5. **Metrics Aggregation**: Calculate Pass-Rate, Impl-Rate, CoP, token distribution, consensus scoring

All evaluation infrastructure is implemented in Mojo 0.26.1 for performance and type safety, with Python automation scripts for subprocess management and GitHub API interaction.

### 6.3 Model Configuration

**Execution Models** (performing the tasks):

| Model | Model ID | Context Limit | Temperature | Max Tokens | Primary Use |
|-------|----------|---------------|-------------|------------|-------------|
| Claude Opus 4.5 | claude-opus-4-5-20251101 | 200K | 0.0 | 8192 | T4-T6 complex reasoning, hierarchical orchestration |
| Claude Sonnet 4 | claude-sonnet-4-5-20250929 | 200K | 0.0 | 8192 | T1-T3 standard execution, balanced cost/capability |
| Claude Haiku 4.5 | claude-haiku-4-5-20250929 | 200K | 0.0 | 8192 | T0-T1 simple tasks, cost optimization |

**Judge Configuration** (evaluating the outputs):

- Three independent judge runs per evaluation: Opus 4.5, Sonnet 4, Haiku 4.5
- Consensus scoring via median of three evaluations
- Same evaluation prompt across all judges (only model differs)
- Temperature: 0.0 (deterministic)
- LLM-as-Judge system prompt: `/config/judge/system_prompt.md`

**Safety Settings**:

- Safety-net plugin enabled to block destructive operations
- File system sandboxing within Docker containers
- Network access restricted to Claude API endpoints
- No sudo/root access within containers

---

## 7. Test Cases

### 7.1 Pull Request (PR) Selection Criteria

Test cases are derived from representative software development tasks with rigorous selection methodology to ensure reproducibility and challenge differentiation across tiers.

**Selection Criteria:**

1. **Reproducible**: Testable from specific git commit hash
2. **Well-defined success criteria**: Expressible in rubric format with measurable requirements
3. **Representative**: Reflects real development workflows encountered in production
4. **Incrementally complex**: Ranges from trivial (Hello World) to multi-file architectural changes
5. **Unambiguous**: Clear task description with expected outcomes

**Size Categories:**

| Category | Lines of Code (LOC) | Complexity Characteristics | Example Tasks |
|----------|---------------------|---------------------------|---------------|
| **Small** | < 100 LOC | Single file changes, configuration updates | Config file modification, simple script creation |
| **Medium** | 100-500 LOC | Feature additions, localized refactoring | Add validation logic, implement utility function |
| **Large** | 500-2000 LOC | Multi-file features, architectural changes | New module implementation, build system migration |

Complexity is further proxied by:
- Number of required tool calls
- Depth of context required (how much codebase must be understood)
- Sequential steps needed
- Number of constraints imposed

### 7.2 Workflow Categories

Each workflow category evaluates distinct agent capabilities:

| Category | Description | Complexity | Key Challenges |
|----------|-------------|------------|----------------|
| **Build System** | Makefile, Justfile, build automation configuration | Low-Medium | Syntax correctness, equivalence preservation |
| **CI/CD** | GitHub Actions, deployment pipelines, automation | Medium | Multi-file coordination, environment configuration |
| **Bug Fixing** | Defect resolution from issue description | Medium-High | Root cause diagnosis, minimal change principle |
| **New Features** | Feature implementation from requirements | High | Requirements interpretation, design decisions |
| **Refactoring** | Code restructuring without behavior change | Medium | Behavior preservation, test coverage |
| **Optimization** | Performance improvements, algorithmic enhancements | Medium-High | Profiling, benchmarking, trade-off analysis |
| **Review** | Code review and feedback generation | Medium | Pattern recognition, best practice knowledge |
| **Documentation** | Technical documentation generation | Low-Medium | Clarity, completeness, accuracy |
| **Issue Filing** | Bug report creation from symptoms | Low | Information gathering, reproduction steps |

### 7.3 Test Case Matrix

The test suite contains **47 test cases** spanning workflow categories and complexity levels:

| Test ID Range | Workflow Focus | Tier Coverage | Representative Task |
|---------------|----------------|---------------|---------------------|
| 001-010 | Baseline validation | T0-T6 | Hello World (001), Simple scripts (002-010) |
| 011-020 | Build system tasks | T0-T6 | Justfile to Makefile conversion (011), Build automation |
| 021-030 | Feature implementation | T1-T6 | Add validation logic, Implement utility functions |
| 031-040 | Bug fixing and refactoring | T2-T6 | Fix type errors, Refactor duplicated code |
| 041-047 | Complex multi-step tasks | T3-T6 | Multi-file architectural changes, Full feature delivery |

Each test specifies:

```yaml
id: "NNN-kebab-case-description"
source:
  repo: "https://github.com/user/project"
  hash: "abc123..."  # Specific commit for reproducibility
task:
  prompt_file: "prompt.md"
  timeout_seconds: 3600
validation:
  rubric_file: "expected/rubric.yaml"
tiers: [T0, T1, T2, T3, T4, T5, T6]
runs_per_tier: 10  # For statistical power
```

Tests are designed with monotonic difficulty increase: performance should drop as complexity increases, validating that the benchmark presents meaningful challenge even to advanced models (e.g., Claude Opus 4.5).

---

## 8. Model Summary

### 8.1 Claude Code Models

Our primary evaluation focuses on the Claude model family accessed through the Claude Code CLI tool:

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Context Limit | Strengths | Primary Role |
|-------|---------------------|----------------------|---------------|-----------|--------------|
| **Claude Opus 4.5** | $15.00 | $75.00 | 200K | Deep reasoning, long-horizon planning, complex multi-step tasks | T4-T6 hierarchical orchestration, authoritative judge |
| **Claude Sonnet 4** | $3.00 | $15.00 | 200K | Balanced capability and cost efficiency | T1-T3 standard development tasks, consensus judge |
| **Claude Haiku 4.5** | $1.00 | $5.00 | 200K | Fast inference, cost-optimized for simple tasks | T0-T1 baseline and simple tasks, consensus judge |

**Claude Opus 4.5** serves as the primary model for T4-T6 hierarchical orchestration, where deep planning and iterative self-correction justify higher inference costs. With its 200K context window and advanced reasoning capabilities, it handles the most complex multi-step workflows requiring sustained goal coherence. Opus also functions as the authoritative judge in our three-model consensus protocol, providing the highest-quality evaluation assessments.

**Claude Sonnet 4** provides the workhorse capability for T1-T3 tiers, balancing performance with cost efficiency at $3/$15 per million tokens. Suitable for the majority of standard development tasks including code generation, refactoring, and build system modifications. Serves as the balanced judge in consensus scoring.

**Claude Haiku 4.5** enables cost-optimized execution for simple T0-T1 tasks where architectural complexity provides minimal benefit. At $1/$5 per million tokens, Haiku is 15x cheaper than Opus for input tokens. Despite lower cost, Haiku maintains sufficient capability for straightforward scripting tasks and provides valuable consensus diversity as the third judge.

### 8.2 Future Model Evaluation (Planned)

The framework architecture supports extension to additional CLI-based systems and model families:

| System | Primary Model(s) | Provider | Status |
|--------|------------------|----------|--------|
| OpenAI Codex/GPT-5.2 | GPT family | OpenAI | Future work |
| Gemini CLI | Gemini 3.0 Pro | Google | Future work |
| DeepSeek Coder | DeepSeek models | DeepSeek | Future work |
| Qwen CLI | Qwen 3 | Alibaba | Future work |
| MBZ-K2 | MBZ-K2 | MBZUAI | Future work |
| Kimi CLI | Kimi-K2, Kimi-3 | Moonshot AI | Future work |

### 8.3 Model-Agnostic Framework Design

The Scylla evaluation framework maintains model agnosticism through several design principles:

1. **Standardized Interfaces**: CLI tool abstraction hides model-specific implementation details. Evaluation interacts solely with the tool's natural language interface and file system outputs, never directly with model APIs.

2. **Consistent Metrics**: Cost-of-Pass, Pass-Rate, Impl-Rate, and quality metrics apply uniformly across all models and tools. Economic comparisons remain valid regardless of underlying architecture.

3. **Pluggable Judges**: Judge models are configurable per evaluation. Current implementation uses Claude family (Opus/Sonnet/Haiku), but framework supports arbitrary LLM-as-Judge configurations.

4. **Tiered Comparison**: The same T0-T6 tier structure applies to all CLI tools, enabling apples-to-apples architectural comparisons across vendors.

5. **Reproducible Configurations**: All experiments specify exact model IDs, temperature settings, and token limits in version-controlled YAML, enabling precise reproduction across different tools.

This design enables future benchmarking of competing CLI tools (GitHub Copilot CLI, Cursor, Aider) and emerging model families, maintaining comparability through standardized evaluation protocols.

---

## 9. Results

[Quantitative results, comparative analysis, and cost-performance trade-offs to be reported following completion of experimental evaluation across all tiers. Expected deliverables include: (1) Pass-Rate, Impl-Rate, and $R_{Prog}$ distributions across T0-T6; (2) Cost-of-Pass analysis identifying Frontier CoP; (3) Token distribution breakdown by component (system prompt, skills, tools, orchestration); (4) Latency measurements and consistency scores; (5) Statistical significance testing between tiers; (6) Workflow category performance stratification.]

---

## 10. Discussion

[Discussion of results, implications for agent design and deployment, and observed failure modes to be analyzed following experimental completion. Expected analysis includes: (1) Identification of point of diminishing returns where architectural complexity ceases to justify cost increases; (2) Validation of atomic task design utility in T3-T4 flat delegation; (3) Assessment of token efficiency chasm in T3 tooling versus T2 skills; (4) Analysis of iterative self-correction overhead in T4-T5 hierarchical architectures; (5) Characterization of failure modes (strategic drift, hallucination, over-engineering); (6) Recommendations for T6 hybrid optimization strategies targeting Frontier CoP.]

---

## 11. Conclusions

[Summary of findings and answers to research questions to be synthesized from experimental results. Expected conclusions include: (1) Quantification of architectural trade-offs between T0-T6 tiers in terms of Cost-of-Pass and Pass-Rate; (2) Validation or refutation of hypotheses regarding prompt complexity, skills versus tools token efficiency, and hierarchical orchestration overhead; (3) Identification of optimal tier configurations for different task complexity levels; (4) Key takeaways for practitioners: when to use simple prompts (T0-T1) versus complex architectures (T4-T5), and cost-benefit analysis of agentic features; (5) Research implications for future LLM-based CLI tool design and economic sustainability frameworks.]

---

## 12. Further Work

[Proposed extensions, additional benchmarks, and future research directions to be informed by experimental findings. Anticipated extensions include: (1) Expansion to additional CLI tools (GitHub Copilot CLI, Cursor, Aider, Cody) for cross-vendor comparisons; (2) Evaluation of additional model families (OpenAI GPT-5.2, Gemini 3.0 Pro, DeepSeek, Qwen 3) using the same tier framework; (3) Extension to non-coding domains (data analysis, documentation generation, DevOps automation); (4) Longitudinal studies tracking Cost-of-Pass evolution as models improve; (5) Human expert baseline establishment for economic validation; (6) Statistical treatment using Hierarchical Bayesian Generalised Linear Models (HiBayES) for robust multi-level analysis; (7) Investigation of prompt optimization techniques beyond CLAUDE.md ablation; (8) Extension to additional workflow categories (security auditing, performance profiling, dependency management).]

---

## Acknowledgements

<Acknowledgements and funding sources.>

---

## References

<Bibliography entries in the required citation format.>

---

## Appendices

### Appendix A: Detailed Metric Definitions

For comprehensive metric definitions including formulas, calculation methods, and interpretation guidelines, see:
- `/home/mvillmow/ProjectScylla/.claude/shared/metrics-definitions.md`
- `/home/mvillmow/ProjectScylla/docs/design/metrics-formulas.md`

Key metrics include Pass-Rate, Implementation Rate (Impl-Rate), Fine-Grained Progress Rate ($R_{Prog}$), Consistency, Change Fail Percentage (CFP), Cost-of-Pass (CoP), Frontier CoP, Token Distribution, and Latency.

### Appendix B: Additional Tables and Figures

[Supplementary tables and figures to be included with experimental results. Expected content: (1) Full tier-by-tier performance tables for all 47 test cases; (2) Token distribution visualizations showing component-level cost breakdown; (3) Latency distribution box plots across tiers; (4) Statistical significance matrices (p-values for tier comparisons); (5) Failure mode categorization tables; (6) Workflow category stratification charts.]

### Appendix C: Reproducibility Checklist

**Repository**: `https://github.com/mvillmow/ProjectScylla`

**Key Configuration Files**:
- Tier definitions: `/config/tiers/tiers.yaml`
- Model configurations: `/config/models/*.yaml`
- Judge system prompt: `/config/judge/system_prompt.md`
- Test definitions: `/tests/*/test.yaml`
- Rubric schemas: `/tests/*/expected/rubric.yaml`

**Required Software**:
- Pixi (package manager)
- Docker (containerization)
- Claude Code CLI
- Mojo 0.26.1, Python 3.12+

**Execution Steps**:
```bash
# 1. Clone repository
git clone https://github.com/mvillmow/ProjectScylla
cd ProjectScylla

# 2. Install dependencies
pixi install

# 3. Run evaluation (example for test-001, tier T0)
pixi run mojo src/scylla/run_evaluation.mojo \
  --test tests/001-hello-world \
  --tier T0 \
  --runs 10

# 4. Generate report
pixi run mojo src/scylla/generate_report.mojo \
  --results runs/001-hello-world/T0
```

**Artifact Locations**:
- Run outputs: `/runs/<test-id>/<tier>/`
- Consensus judgments: `/runs/<test-id>/<tier>/judgment.json`
- Metrics summaries: `/summaries/<test-id>/metrics.json`
- Final reports: `/reports/<test-id>/report.md`

