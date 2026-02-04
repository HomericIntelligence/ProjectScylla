# Taming Scylla

## Understanding the multi-headed agentic daemon of the coding seas

Micah Villmow
Individual
research@villmow.us

---

## Abstract

LLM-based tools are automating more and more software development tasks. But there's no rigorous way to evaluate how different architectural choices—prompts, skills, tools, multi-agent setups—actually affect both capability and cost.

This paper introduces Scylla, an evaluation framework for benchmarking agentic coding tools through structured ablation studies. The methodology uses seven testing tiers (T0-T6) that progressively add complexity. This lets us isolate what actually influences results and how.

The key metric is Cost-of-Pass (CoP): the expected dollar cost to get one correct solution. This directly quantifies the trade-off between complexity and efficiency.

The framework is model-agnostic, designed to work with any CLI tool. This paper demonstrates it with Claude Sonnet 4.5, using multiple LLM judges (Opus 4.5, Sonnet 4.5, Haiku 4.5) from the same vendor for evaluation consensus. Judges score results using direct tests, human-driven rubrics, and qualitative assessment.

The result is a reproducible framework that quantifies trade-offs between agent complexity and actual outcomes.

---

## Keywords

LLM agents, software engineering benchmarks, cost-of-pass, multi-agent systems, prompt engineering, ablation studies, evaluation frameworks, CLI tools, agentic AI

---

## 1. Summary

With the advancement of large language models has come a massive increase in capabilities for automated computer interactions. What used to require hand-coded algorithms and pipelines can now be done automatically using state of the art coding models to generate instructions that can then be utilized to further improve automated approaches. However, understanding what improves these language models is more of black magic than art, let alone a rigorous science. This paper's goal is to help demistify the magic of prompt engineering by proposing a rigorous evaluation framework across multiple dimensions to help determine how agents interact, the scale that of changes for the agentics, and an attempt to quantify with numbers the benefits of each approach across a broad range of activities.

There are benchmarks for measuring LLM's workflows in various domains, such as agent-bench[1], swe-bench[2], tau-bench[3], etc... There are also prompt evaluation benchmarks such as PromptBench[4] or PromptEval[5]. This paper focuses specifically on coding tools, specifically industry leading tool Claude Code[7], and how prompt modification can change the behavior of the model for better or for worse. This paper also introduces a framework for evaluating other tools in a systematic way, thus allowing extension to domains outside of CLI based coding tools. I show that on a trivial Hello World task, all seven tiers (T0-T6) achieve equivalent quality (all grade A, scores 0.943-0.983) while cost varies 3.8x from $0.065 (T5 hybrid) to $0.247 (T6 super). The framework successfully differentiates cost structures across architectural choices even when quality converges.

This implies that architectural complexity doesn't always improve quality, and that careful hybrid designs (T5) can achieve Frontier Cost-of-Pass by selectively combining features rather than maximizing them. The dryrun validates the framework's ability to measure these trade-offs empirically.

---

## 2. Introduction

Anthropic has many good resources for improving Claude Code on their engineering blog, but there is not a simple way to measure easily whether changes to the prompt instructions actually benefit in the way that the user can easily comprehend. Therefore, I am introducing Scylla, a testing framework for evaluating prompts, tools, skills, and agents for solving problems that are common for day to day coding tasks. I wanted to know if sub-agents, skills, tools, or mcp servers were actually contributing to improved code output, without relying on my gut or intuition. This problem came up multiple times when asked by others to explain how to better utilize CLI tools for programming. In my experience, the quality of the prompts has a dramatic improvement on the output of the results. Whether its the prompt to call the tool or MCP server, the prompt to spawn a sub-agent, or the prompt to trigger a skill, these language based triggers are fuzzy in their meaning. Unlike a traditional programming language that is very explicit in what it is means and what it does, it is not a direct mapping from text to action. This framework is my attempt at helping unwrap this problem.

First, in section 3, I will introduce the current work that is being done in this area, and explain how they approach the problem. Then, in section 4, I will introduce the testing methodology along with an in-depth analysis of the first test case. This will provide the needed understanding of what is being tested, along with why, on something that should be easily dissectable and understandable. The next three section will introduce three more test cases from different categories of tasks that show the variance of results from the same set of prompts. After that, I will dissect some of the more interesting cases where there was large impacts on the baseline behavior of the model, both positive and negative. The final section will showcase the final results across a larger set of test cases, and point to further areas of research, and how to extend this to other models.

The questions I am investigating are:

* Is it possible to quantify whether a task is solveable more efficiently by one methodology over others?
* Is the sum of a prompt more than the individual parts?
* Are there core improvements that can be made purely through extensions to claude code that are generic for all workloads?
* Are there specific prompt techniques that have secondary effects, positive or negative, on other prompt techniques?
* Holding the tool and prompt constant, how much does the underlying model contribute to the quality of the results?

Some hypotheses I have are:

* Certain tasks excel when run as sub-tasks, or tools, or mcp, or skills, that are unrelated to context management.
* Prompt complexity has a negative correlation to higher quality results, i.e. KISS principle, in scenarios that is part of the training set.
* Prompt complexity has a positive correlation to higher quality results, i.e. an inverse KISS principle, in scenarios outside of the training set.

---

## 3. Related Work

Given that we are testing production tools and not models, many, if not all, of the prior work on evaluating prompts and benchmarks does not apply directly here, since there is possibly a large level of indirection between what we are testing and what actually gets executed by the model. The tool is a black box and what is executing is hidden behind multiple layers, first being the CLI tool itself, but also whatever optimizations and implementation details the vendor implements on top of their trained base model. The models themselves are not documented publicly, as these details are competitive advantages, and the pre or post-processing that occurs is not visible to the user as they occur on the vendors servers.

There are multiple benchmarks on judging the models, such as Agent-Bench[1], SWE-Bench[2], and TAU-Bench[3], but no standard benchmarks on CLI tools, like Claude Code, on how prompts affect them. The reader can also investigate PromptEval, PromptBench, or lm-evaluation-harness[8], but these also don't benchmark the CLI tools, which are used in production today. The next paragraphs will explain in high level details the various other options on the market.

There are several good benchmarks for evaluating LLM agents. SWE-Bench[2] tests models on real GitHub issues—can they actually fix bugs and add features to real codebases? Agent-Bench[1] goes broader, testing multi-turn agents across different environments like operating systems, databases, and knowledge graphs, with fine-grained metrics beyond just pass/fail. TAU-Bench[3] focuses on whether agents can effectively use external tools. But here's the thing: all of these evaluate the models directly. They don't address the full agentic loop—hooks, skills, MCP servers, vendor optimizations, orchestration logic. My work focuses on that tool interface rather than the raw model underneath.

For prompt evaluation, there's PromptBench[4] (unified testing across tasks), PromptEval[5] (automated correctness and robustness checking), and EleutherAI's lm-evaluation-harness[8] (standardized multi-task comparison). The problem: these all assume direct access to model inputs and outputs. With production CLI tools like Claude Code, the model is wrapped in layers of system prompts, tool schemas, skill definitions, and orchestration logic. You can't just test the model in isolation. You have to test the whole system.

My work is based solely on evaluating CLI tools, as the CLI's tools are more than the model themselves. As I mentioned earlier, the agentic loop, with hooks, tools, skills, sub-agents, MCP servers, and other logic wrapped together into a single application where the only way to get control of the behavior is through the english language is what I want to evaluate for effectiveness. From this interface, programmatic tools can be spawned, but the ability to properly and accurately interact with the agent is via a fuzzy language interface, and not via traditional programmatic interfaces. While there are some hooks that allow extra programmatic validation with Claude Code, I'm not evaluating those at this time. Claude Code has the ability to use agentic evaluation at the hook boundary, but triggering it is guaranteed (and not language-based).

## 4. Test Methodology

### 4.1 Experimental Design

This experiment is designed by testing english phrases, colloquially known as prompts, via the various methodologies exposed by a CLI tool, in this case Claude Code. The experiment is run by allowing an agent a nearly unfettered access to the system, only blocking dangerous ops, thanks to the safety-net plugin[9] from cc-marketplace[10], to perform a task. The task has a well defined solution that is then judged by three different LLM's of various 'strength'. In this case Claude Opus 4.5, Claude Sonnet 4.5, and Claude Haiku 4.5. Each of the 4.5 models are sufficiently advanced in capabilities to be considered independent judges of a task with low failure rates. The judges are provided the same prompt, so the only difference between their results comes from the judge training and implementation differences and not from the prompt or test input. Each judge will receive the output of the task LLM, and provide the results based on the criteria. The judges have the following categories of evaluation; functional correctness, code quality, development pipeline, security and safety, proportionality and professionalism, and patchfile correctness.

**Table 4.1: LLM-as-Judge Evaluation Categories**

| Category | Weight | Scoring Type | Description |
|----------|--------|--------------|-------------|
| Functional Correctness | 0.35 | Checklist | File existence, output correctness, exit codes, exact output matching |
| Code Quality | 0.20 | Checklist | Syntax validity, idiomatic code, unused imports, PEP8 compliance |
| Proportionality | 0.15 | Checklist | Appropriate scope, minimal files, no unnecessary artifacts or tests |
| Build Pipeline | 0.10 | Checklist | Build passes, format checks, tests (when applicable), pre-commit hooks |
| Overall Quality | 0.20 | Subjective | Engineering judgment on appropriateness, maintainability, and senior engineer approval |

**Total Weight**: 1.0 (100%)

Each category contributes proportionally to the final score. Here's the formula:

$$S_{final} = \sum_{i} w_i \cdot \frac{P_i^{achieved}}{P_i^{max}}$$

where $w_i$ are the category weights (they sum to 1.0), and $P_i$ is the points you got versus the maximum possible (skipping any N/A items). For scoring individual items:

- **Binary items**: You either get it or you don't (1.0 or 0.0)
- **Graduated items**: Partial credit on a 0.0-1.0 scale based on how well you did
- **Subjective items**: LLM judgment with calibrated deductions

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

The final score maps to a grade using this scale:

**Table 4.2: Industry-Aligned Grade Scale**

| Grade | Threshold | Label | What It Means |
|-------|-----------|-------|---------------|
| S | 1.00 | Amazing | Perfect score, goes above and beyond---ship it now |
| A | ≥ 0.80 | Excellent | Production ready---ship with confidence |
| B | ≥ 0.60 | Good | Works well, minor tweaks needed---ship after quick fixes |
| C | ≥ 0.40 | Acceptable | It works but has issues---needs rework |
| D | ≥ 0.20 | Marginal | Lots of problems---substantial rework needed |
| F | < 0.20 | Failing | Doesn't work---start over |

I use **0.60** (Grade B) as the pass threshold. That means the solution works and meets requirements, even if there's room for minor improvements. An S grade needs a perfect 1.00 and you have to actually exceed what was asked for.

Each experiment can be reproduced by running the top level test run script, which will launch the same set of tasks with the same parameters, where the only variation is the judgement of the LLM's judges when determining how to judge the work.

This finishes the summary of a single test. However, the test themselves are defined differently. The test are a prompt and a configuration file that specify a repository, a github hash, a set of configuration files to override any pre-defined tooling, set of commands to validate the results, and a container to run everything in to help with reproducibility. The first test is being used as an example in this paper, and also as a pipecleaner to show that everything works as expected. This example is 'hello world' from octocat, but forked to my repository just to make sure that the repository is not polluted. The precaution is done just incase the agents make mistakes or do things that the original author probably does not want to be bothered by.

#### Test-001: Hello World Baseline

First, let's look at the simplest possible test to make sure everything works. This is literally just creating a "Hello World" script, which is a pipecleaner for the infrastructure and to discuss the methodology without intermixing with the complexity of more realistic tests.

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

**Expected Result:**

```
print("Hello, World!")
```

or

```
# /usr/bin/python3

print("Hello, World!")
```

**Rubric Categories and Weights:**

| Category | Weight | Key Criteria |
|----------|--------|--------------|
| Functional Correctness | 35% | File `hello.py` exists; running `python hello.py` produces correct output; exit code 0; output exactly matches |
| Code Quality | 20% | Valid Python syntax; idiomatic code; no unused imports; PEP8 compliant |
| Proportionality | 15% | Total files ≤ 3; LOC ≤ 3; no unnecessary test files; build artifacts cleaned up |
| Build Pipeline | 10% | Syntax check passes; format check passes (if ruff available); tests pass (if required) |
| Overall Quality | 20% | Senior engineer approval; appropriately scoped for Hello World |

**What Should Happen:**

Even T0 (no system prompt at all) should nail this test and get an 'A', since we're talking ≥ 0.80 scores. If T0 can't do Hello World, I will assume that something is fundamentally wrong with the framework itself and throw out the results. Higher tiers (T1-T6) should also ace it, as there's no reason fancy prompts or multi-agent setups would help with something this simple. However, if performance drop on this test, it means the added complexity is actually making things worse even on something so simple, so if this happens, we will analyze why.

Now that we have gone over the test itself, lets discuss the strategy and tiered approach. The first thing to test is with no prompt at all, including no system prompt. This is to provide as close to a baseline as the base model as possible by overwriting the system prompt with an empty string and not using any configuration or non-default settings from the tool. This provides the baseline that all improvements are measured against. For something as simple as hello world, this baseline should solve the task. The test setup is such that variability in judging will occur, but there is not much one can do to improve the output of a hello world script. However, there are things that you can do that make things worse or break the expected behavior, but I would expect most solutions to be the exact same for all the tests.

#### Tiered Ablation Strategy

The core idea is simple: start with nothing, then add one set of things at a time to see what actually helps. This ablation study uses seven tiers that progressively add complexity, with **~114 sub-tests** total. Each tier gets tested independently so we can isolate what each component contributes.

**Table 4.3: Testing Tiers (Ablation Study Framework)**

| Tier | Name | Sub-tests | Primary Focus | Tools | Delegation | Key Characteristic |
|------|------|-----------|---------------|-------|------------|-------------------|
| T0 | Prompts | 24 | System prompt ablation (empty → full) | - | No | Baseline: empty prompt (00) through full 1787-line CLAUDE.md (03) plus 18 individual blocks (B01-B18) |
| T1 | Skills | 11 | Domain expertise via installed skills | Default | No | Token-efficient domain knowledge; categories: Agent (5), CI/CD (7), Documentation (4), GitHub (10), Language Specific (10), Quality (5), Workflow (5) |
| T2 | Tooling | 15 | External tools and MCP servers | Yes | No | External API access; introduces token efficiency chasm from schema loading |
| T3 | Delegation | 41 | Flat multi-agent with specialists | Yes | Yes | Atomic task design; flat orchestration with specialist agents (L2-L5) |
| T4 | Hierarchy | 7 | Nested orchestration with orchestrators | Yes | Yes | Hierarchical coordination (L0-L1); Task Decomposer, Actor, Monitor, Evaluator roles |
| T5 | Hybrid | 15+ | Optimal combinations from all tiers | Yes | Yes | Combines T2 skills + T4 delegation + selective verification; targets frontier Cost-of-Pass |
| T6 | Super | 1 | Maximum capability configuration | All | All | Theoretical maximum: 61 skills, all MCP servers, 44 agents, full prompt; establishes capability ceiling |

**How the Tiers Work:**

1. **T0 (Baseline):** Start with an empty prompt (00-empty) to see what the raw model can do, then go all the way up to the full 1787-line CLAUDE.md (03-full). Individual blocks (B01-B18) let me test each piece of the prompt separately to see what actually matters.

2. **T1-T2 (Skills vs Tools):** Here's where it gets interesting. T1 uses skills, domain knowledge baked into prompts. Token-efficient. T2 uses external tools via JSON schemas. Problem is, loading all those tool definitions inflates token usage. I call this the "Token Efficiency Chasm" — the gap between lean skill-based approaches and schema-heavy tool architectures.

3. **T3-T4 (Multi-Agent Setups):** T3 does flat delegation, breaking tasks into smaller pieces and assigning them to specialist agents. In my dryrun, T3 achieves the second-lowest cost at $0.129, showing efficiency gains. T4 adds hierarchy with self-correction loops, but this complexity can increase costs — T4 runs $0.168 versus T3's $0.129, a 30% increase for this trivial task.

4. **T5 (Smart Combinations):** Take what works from the other tiers, combine then together, such as T2's efficient skills, T3's best agents, T4's task delegation, but make verification selective instead of mandatory. Goal is maximum bang for your buck.

5. **T6 (Everything):** Turn on everything at once. All 61 skills, all tools, all 44 agents, full prompt. This I hope establishes the theoretical max performance and shows where diminishing returns kick in, but also can show signs of over-engineering if it is occurring.

**The Key:** For each tier T(n), I compare it directly against T(n-1) to see what that specific change actually buys you in terms of performance and cost.

### 4.2 Dimensional Search Space

The framework tests across four different dimensions. Each one is an independent knob you can turn, and they all affect both what the agent can do and how much it costs.

#### 4.2.1 Agent Complexity Axis (Tiers 0-6)

This is just the tier structure spelled out differently:

| Tier Range | Complexity Level | Description |
|------------|------------------|-------------|
| T0 | Single-agent, prompt-only | Base model with varying prompt sophistication |
| T1 | Single-agent with skills | Add in agentic skills to improve the quality of the work |
| T2 | Single-agent with tools | External API access via tool schemas |
| T3 | Multi-agent, flat | Specialist agents with central orchestrator |
| T4 | Multi-agent, hierarchical | Nested orchestration with self-correction loops |
| T5 | Best case scenarios | Attempt to pick the best case scenarios from previous runs to see if the sum is more than its parts |
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

Each block (B01-B18) can be tested separately to see what it actually contributes.

#### 4.2.3 Skill Complexity Axis

Skills are organized by domain. Here's what we're testing in T1:

| Category | Count | Example Domains | Token Efficiency |
|----------|-------|-----------------|------------------|
| Agent | 5 | Agent management patterns | High |
| CI/CD | 7 | Build and deployment automation | High |
| Documentation | 4 | Technical writing assistance | Medium |
| GitHub | 10 | Repository management | Medium |
| Language | 10 | Programming language specific | High |
| Quality | 5 | Code quality and review | Medium |
| Workflow | 5 | Development workflow patterns | High |

**Total**: 46 skills across 7 categories. The big advantage? Skills bake knowledge into prompts, so you avoid loading massive tool schemas.

#### 4.2.4 Agent Hierarchy Axis

Three ways to organize agents, tested across T3-T4:

| Pattern | Coordination | Communication Overhead | Use Cases |
|---------|--------------|------------------------|-----------|
| **Flat** | No supervision; peer-to-peer | Low | Simple, independent tasks |
| **Hierarchical** | L0-L4 levels with explicit supervision | High | Complex, interdependent tasks requiring planning |
| **Hybrid** | Selective hierarchy based on task complexity | Medium | Adaptive: flat for simple tasks, hierarchical for complex |

Hierarchy matters for costs because each supervision layer adds more orchestration tokens and potentially more self-correction iterations.

---

## 5. Test Metrics

### 5.1 Performance Metrics

**Pass-Rate** is straightforward, did it work or not:

$$\text{Pass-Rate} = \frac{\text{correct\_solutions}}{\text{total\_attempts}}$$

Range is 0.0 (nothing worked) to 1.0 (everything worked). "Correct" means it passes the test suite for that specific task. Report this with confidence intervals (95% CI if you have 30+ runs).

**Fine-Grained Progress Rate** ($R_{Prog}$) tracks how far you got through multi-step tasks:

$$R_{Prog} = \frac{\text{achieved\_progress\_steps}}{\text{expected\_progress\_steps}}$$

Range is 0.0 to 1.0+. If you get above 1.0, it means the agent took extra steps that actually helped. This is super useful for debugging where things go wrong in complex workflows, especially in hierarchical setups with all their self-correction loops.

**Consistency** measures how stable the outputs are:

$$\text{Consistency} = 1 - \frac{\sigma(\text{outputs})}{\mu(\text{outputs})}$$

Range is 0.0 to 1.0, higher means more deterministic. Matters most for where you're trying to get reliable structured outputs.

### 5.2 Quality Metrics

**Implementation Rate** (Impl-Rate) measures whether you actually satisfied the requirements:

$$\text{Impl-Rate} = \frac{\text{satisfied\_requirements}}{\text{total\_requirements}}$$

Range is 0.0 to 1.0. This gives you more detail than just pass/fail, you get partial credit for incomplete work. Checked using multiple LLM judges with median scoring for consensus.

**Change Fail Percentage** (CFP) tells you about production stability:

$$\text{CFP} = \frac{\text{failed\_changes}}{\text{total\_changes}}$$

Range is 0.0 to 1.0, lower is better. A "failed change" means you had to rollback or hotfix it immediately. This is important because high Impl-Rate doesn't mean much if the code is brittle and keeps breaking.

**PR Revert Rate** tracks how often changes get thrown out:

$$\text{PR\_Revert\_Rate} = \frac{\text{reverted\_prs}}{\text{merged\_prs}}$$

Straightforward: how many PRs got reverted because of quality or design problems.

### 5.3 Efficiency and Cost Metrics

**Latency** is just time from start to finish (seconds):

- Time-to-First-Token (TTFT)
- Total response time
- Tool execution time

Matters a lot for T5 architectures where verification loops can really slow things down.

**Token Distribution** shows where your tokens are going:

$$\text{token\_dist} = \left\{ \frac{\text{input\_tokens}}{\text{total\_tokens}}, \frac{\text{output\_tokens}}{\text{total\_tokens}}, \frac{\text{tool\_input\_tokens}}{\text{total\_tokens}}, \frac{\text{tool\_output\_tokens}}{\text{total\_tokens}} \right\}$$

Useful for figuring out what's actually costing you money (like T3's massive JSON schemas or T4's orchestration overhead).

**Cost-of-Pass (CoP)** is the key metric, what's the expected cost to get one correct solution:

$$\text{CoP} = \frac{\text{total\_cost}}{\text{pass\_rate}}$$

Units are USD. Lower is better. If pass_rate hits zero, CoP goes to infinity, that configuration is economically dead. This combines both cost and accuracy into one number that tells you if something is actually sustainable.

**Frontier CoP** finds the best option:

$$\text{Frontier\_CoP} = \min(\text{CoP}_{T0}, \text{CoP}_{T1}, \ldots, \text{CoP}_{T6})$$

This is just the minimum CoP across all tiers. Compare this against what it costs to hire a human expert to see if automation actually makes economic sense. Different model providers will have different cost assumptions.

**Model Pricing** (as of January 2026):

| Model | Input ($/1M tokens) | Output ($/1M tokens) |
|-------|---------------------|----------------------|
| Claude Opus 4.5 | $15.00 | $75.00 |
| Claude Sonnet 4.5 | $3.00 | $15.00 |
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

Each test runs in its own Docker container with the repo at a specific git commit. This means every run is reproducible and tests can't mess with each other. Every container starts fresh with:

- Clean git workspace at the exact commit specified
- Tier-specific config files
- Whatever tools/skills that tier needs
- Isolated filesystem for collecting results

### 6.2 Software Stack

| Component | Version/Tool |
|-----------|--------------|
| CLI Tool | Claude Code (primary evaluation target) |
| Language Runtime | Python 3.12.3, Mojo 0.26.1.0.dev2025122805 (211e2f5c) |
| Package Manager | Pixi |
| Container Runtime | Docker |
| Orchestration | Custom Scylla framework |
| Validation | JSON Schema, YAML validation |
| Version Control | Git Version 2.43.0 |

The evaluation harness does five things:

1. **Workspace Prep**: Clone the repo, check out the specific commit, inject tier config
2. **Run the Agent**: Fire up Claude Code with whatever prompt/tools that tier uses
3. **Capture Everything**: Grab the output, command logs, file changes, artifacts
4. **Judge It**: Run three LLM judges in parallel (Opus, Sonnet, Haiku)
5. **Calculate Metrics**: Crunch the numbers for Pass-Rate, Impl-Rate, CoP, token usage, consensus scores

### 6.3 Model Configuration

**Execution Models** (performing the tasks):

| Model | Model ID | Primary Use |
|-------|----------|-------------|
| Claude Opus 4.5 | claude-opus-4-5-20251101 | complex reasoning, hierarchical orchestration |
| Claude Sonnet 4.5 | claude-sonnet-4-5-20250929 | standard execution, balanced cost/capability |
| Claude Haiku 4.5 | claude-haiku-4-5-20250929 | simple tasks, cost optimization |

**Judge Configuration** (evaluating the outputs):

- Three judges per evaluation: Opus 4.5, Sonnet 4.5, Haiku 4.5
- Take the median of the three scores for consensus
- Same prompt for all judges (only the model changes)
- Judge prompt: `<project_root>/config/judge/system_prompt.md`

**Safety**:

- Safety-net plugin blocks destructive operations
- Everything sandboxed in Docker
- Network limited to Claude API only
- No sudo/root access

---

## 7. Test Cases

### 7.1 Pull Request (PR) Selection Criteria

Test cases come from real software development tasks. Here's what makes a good test:

1. **Reproducible**: Pin it to a specific git commit
2. **Clear success criteria**: Can be expressed in a rubric with measurable requirements
3. **Representative**: Real work that developers actually do
4. **Incrementally complex**: From trivial (Hello World) to multi-file architecture changes
5. **Unambiguous**: Clear task, clear expected outcome

**Size Categories:**

| Category | Lines of Code (LOC) | Complexity Characteristics | Example Tasks |
|----------|---------------------|---------------------------|---------------|
| **Small** | < 100 LOC | Single file changes, configuration updates | Config file modification, simple script creation |
| **Medium** | 100-500 LOC | Feature additions, localized refactoring | Add validation logic, implement utility function |
| **Large** | 500-2000 LOC | Multi-file features, architectural changes | New module implementation, build system migration |

Complexity also depends on:
- How many tool calls you need
- How much of the codebase you have to understand
- How many sequential steps
- How many constraints you're working under

### 7.2 Workflow Categories

Different categories test different capabilities:

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

I've designed **47 planned test cases** covering different workflows and complexity levels:

| Test ID Range | Workflow Focus | Representative Task |
|---------------|----------------|---------------------|
| 001-010 | Baseline validation | Hello World (001), Simple scripts (002-010) |
| 011-020 | Build system tasks | Justfile to Makefile conversion (011), Build automation |
| 021-030 | Feature implementation | Add validation logic, Implement utility functions |
| 031-040 | Bug fixing and refactoring | Fix type errors, Refactor duplicated code |
| 041-047 | Complex multi-step tasks | Multi-file architectural changes, Full feature delivery |

Each test is defined in YAML:

```yaml
id: "NNN-kebab-case-description"
source:
  repo: "https://github.com/user/project"
  hash: "abc123..."  # Pin to specific commit
task:
  prompt_file: "prompt.md"
  timeout_seconds: 3600
validation:
  rubric_file: "expected/rubric.yaml"
tiers: [T0, T1, T2, T3, T4, T5, T6]
runs_per_tier: 10  # Get enough data for stats
```

Tests get progressively harder. Performance should drop as complexity increases, if it doesn't, the test is too easy even for the advanced models.

---

## 8. Model Summary

### 8.1 Claude Code Models

I'm primarily testing Claude models through the Claude Code CLI:

**Opus 4.5** is the heavy hitter for T4-T6 where you need deep reasoning and self-correction. With 200K context and strong multi-step capabilities, it handles the complex stuff. Also the authoritative judge in my three-model consensus setup.

**Sonnet 4.5** is the workhorse for T1-T3. Balanced cost/performance at $3/$15 per million tokens. Handles most standard dev work---code gen, refactoring, build configs. The middle judge for consensus.

**Haiku 4.5** is for simple T0-T1 tasks where fancy features don't help. At $1/$5 per million tokens, it's 15x cheaper than Opus for inputs. Still capable enough for straightforward scripts, and provides diversity as the third judge.

### 8.2 Model-Agnostic Framework Design

The framework is designed to work with any CLI tool or model:

1. **Standardized Interfaces**: Everything goes through the CLI's language interface and filesystem outputs. Never touches model APIs directly. This means vendor-specific details don't matter.

2. **Consistent Metrics**: CoP, Pass-Rate, Impl-Rate work the same across all models. You can do apples-to-apples economic comparisons.

3. **Pluggable Judges**: Currently using Claude family for judging, but you can swap in any LLM.

4. **Same Tier Structure**: T0-T6 applies to all tools. Direct architectural comparisons across vendors.

5. **Reproducible Configs**: Everything's in version-controlled YAML, model IDs, temperature, token limits. Easy to reproduce across different tools.

This means you can benchmark Copilot CLI, Cursor, Aider, or whatever new tool comes out, and the comparisons stay valid.

---

## 9. Results

I'll present results from the dryrun experiment (test-001, Hello World task) across all seven tiers. The dryrun serves as a pipeline validation exercise with N=1 run per tier, establishing that the framework executes end-to-end successfully and generates the expected metrics, figures, and tables. Think of this as a "smoke test" — if the pipeline works on the simplest possible task, I know it'll handle the complex stuff later.

### 9.1 Pipeline Validation (Dryrun Overview)

First, let me confirm the dryrun executed successfully. Here's what I ran:

- **Scope**: 1 model (Sonnet 4.5), 7 tiers (T0-T6), 1 subtest per tier
- **Judges**: 3 judges per run (Opus 4.5, Sonnet 4.5, Haiku 4.5) = 21 total judge evaluations
- **Criteria**: 5 criteria per judge × 21 judges = 105 total criteria scores
- **Total cost**: $1.01 (agent execution + judge evaluation)
- **Total duration**: ~1289 seconds (~21.5 minutes) total across all tiers
- **Pass rate**: 100% (all 7 tiers passed, all grade A)

Table 1 shows the tier-by-tier summary. All tiers achieved grade A with median consensus scores ranging from 0.943 (T6) to 0.983 (T2, T3, T5). The task is trivially easy, as expected — even T0 (minimal prompt) scores 0.973.

**Table 1: Tier Summary (Dryrun)**

| Tier | Pass Rate | Mean Score (±σ) | Median Score | Grade | CoP ($) |
|------|-----------|-----------------|--------------|-------|---------|
| T0   | 1.000     | 0.973 ± nan     | 0.973        | A     | 0.14    |
| T1   | 1.000     | 0.970 ± nan     | 0.970        | A     | 0.13    |
| T2   | 1.000     | 0.983 ± nan     | 0.983        | A     | 0.14    |
| T3   | 1.000     | 0.983 ± nan     | 0.983        | A     | 0.13    |
| T4   | 1.000     | 0.960 ± nan     | 0.960        | A     | 0.17    |
| T5   | 1.000     | 0.983 ± nan     | 0.983        | A     | 0.07    |
| T6   | 1.000     | 0.943 ± nan     | 0.943        | A     | 0.25    |

**Key finding**: Quality converges across all tiers (ceiling effect), but cost varies 3.8x from $0.065 to $0.247.

### 9.2 Cost-of-Pass Analysis

Since all tiers pass (pass_rate = 1.0), Cost-of-Pass equals the raw cost. Figure 6 (see `docs/paper-dryrun/figures/fig06_cop_by_tier.png`) visualizes CoP across tiers.

**Frontier CoP**: $0.065 (achieved by T5 hybrid)

**Cost ranking** (lowest to highest):
1. **T5** (hybrid): $0.065 — Frontier CoP achieved through selective skill loading and minimal cache creation (4.6K vs 23-44K for other tiers)
2. **T1** (skills): $0.127 — Token-efficient skill-based approach
3. **T3** (delegation): $0.129 — Flat multi-agent with efficient orchestration
4. **T0** (baseline): $0.135 — Minimal prompt overhead
5. **T2** (tooling): $0.138 — Tool schema loading increases cache tokens
6. **T4** (hierarchy): $0.168 — Hierarchical orchestration adds 30% overhead vs T3
7. **T6** (super): $0.247 — Maximum configuration is 3.8x Frontier CoP; diminishing returns evident

Here's the thing: T6 (everything enabled) costs the most despite scoring the lowest (0.943). Over-engineering at its finest—loading 61 skills + all tools + 44 agents adds cost without improving quality on this trivial task.

### 9.3 Token Analysis

Token distribution reveals where costs originate. Figure 7 (see `docs/paper-dryrun/figures/fig07_token_distribution.png`) shows the breakdown by token type.

Cache read tokens dominate—80-99% of total tokens across all tiers, confirming prompt caching works. But cache creation tokens vary dramatically:

**Table 2: Token Breakdown**

| Tier | Input | Output | Cache Create | Cache Read | Total   |
|------|-------|--------|--------------|------------|---------|
| T0   | 29    | 656    | 23,106       | 112,686    | 136,477 |
| T1   | 25    | 558    | 23,266       | 91,477     | 115,326 |
| T2   | 29    | 711    | 23,350       | 113,858    | 137,948 |
| T3   | 25    | 668    | 23,352       | 91,771     | 115,816 |
| T4   | 23    | 725    | 23,556       | 91,828     | 116,132 |
| T5   | 26    | 625    | **4,629**    | 109,368    | 114,648 |
| T6   | 29    | 722    | **44,337**   | 218,778    | 263,866 |

The Token Efficiency Chasm I mentioned in Section 4? Confirmed. T6 requires 218K cache read tokens versus T0's 113K—a 1.94x increase (nearly double). T5 achieves efficiency by minimizing cache creation (4.6K vs 23-44K), validating the hybrid strategy.

Output tokens stay stable at 558-725 across tiers, showing the task itself requires similar generation regardless of architecture.

### 9.4 Latency Analysis

Latency breaks into two components: agent execution time and judge evaluation time. Figure 13 (see `docs/paper-dryrun/figures/fig13_latency.png`) shows the breakdown.

**Table 3: Latency Breakdown**

| Tier | Agent Time (s) | Judge Time (s) | Total Time (s) | Judge % of Total |
|------|----------------|----------------|----------------|------------------|
| T0   | 35.3           | 167.8          | 203.1          | 82.6%            |
| T1   | 29.3           | 178.0          | 207.3          | 85.9%            |
| T2   | 36.8           | 161.7          | 198.5          | 81.5%            |
| T3   | 29.9           | 149.1          | 179.0          | 83.3%            |
| T4   | 41.2           | 137.0          | 178.2          | 76.9%            |
| T5   | 24.8           | 128.4          | 153.1          | 83.8%            |
| T6   | 28.4           | 141.1          | 169.5          | 83.2%            |

Judge evaluation dominates—77-86% of total latency, ranging from 128-178 seconds. This makes sense since 3 judges each evaluate the output independently.

Agent time varies modestly, 25-41 seconds. T5 is fastest (24.8s), T4 slowest (41.2s). T5's speed advantage aligns with its cost advantage—both stem from minimal cache loading.

On this trivial task, judge overhead dwarfs agent execution time. On more complex tasks with multi-step reasoning, agent time would dominate.

### 9.5 Judge Agreement

Three judges (Opus 4.5, Sonnet 4.5, Haiku 4.5) evaluated each run. Figure 2 (see `docs/paper-dryrun/figures/fig02_judge_variance.png`) and Figure 14 (see `docs/paper-dryrun/figures/fig14_judge_agreement.png`) show judge variance and pairwise agreement.

**Judge behavior patterns**:
- **Opus**: Most conservative judge, scores range 0.93-0.96, never awards S grade
- **Sonnet**: Moderate judge, scores range 0.90-1.00, awards S grade in 4/7 tiers (T2, T3, T4, T5)
- **Haiku**: Most generous judge, scores range 0.93-1.00, awards S grade in 5/7 tiers

**Pairwise agreement** (Table 3 from `docs/paper-dryrun/tables/tab03_judge_agreement.md`):
- **Opus-Sonnet**: Spearman ρ = 0.333, Pearson r = 0.706, mean Δ = 0.033
- **Opus-Haiku**: Spearman ρ = -0.273, Pearson r = -0.063, mean Δ = 0.045
- **Sonnet-Haiku**: Spearman ρ = -0.522, Pearson r = -0.347, mean Δ = 0.037

Krippendorff's α (interval): -0.117. Poor agreement, but expected with N=1 per tier.

Despite low inter-rater agreement, the 3-judge median produces stable final scores. The median dampens extreme scores—Haiku's 1.00 perfects versus Opus's 0.93 conservatism.

### 9.6 Criteria Breakdown

Judges score five weighted categories: functional correctness (35%), code quality (20%), proportionality (15%), build pipeline (10%), overall quality (20%). Figure 9 (see `docs/paper-dryrun/figures/fig09_criteria_by_tier.png`) shows criteria performance by tier.

All tiers score 0.95-1.00 on functional criteria (file exists, correct output, exit code 0). Near-perfect, confirming the task is trivially easy.

The largest score differences appear in subjective categories. Proportionality: T6 scored lower because judges noted cache artifacts (.ruff_cache, .pytest_cache) remaining in workspace. Overall quality: subjective engineering judgment shows the most variance across judges.

Build pipeline: all tiers pass with scores 0.90-1.00, confirming clean execution.

### 9.7 Statistical Limitations

N=1 prevents inferential statistics. With only one run per tier, I can't compute confidence intervals, standard deviations, or perform significance tests. All results are purely descriptive.

The analysis pipeline correctly reports `nan` for standard deviation and sets confidence intervals to (point, point). Statistical warnings appear in the output: "Mann-Whitney U test called with sample sizes 1, 1. Need at least 2 samples per group."

The framework successfully executed end-to-end. The full test001-nothinking experiment (N=10 per tier × 113 subtests = 1,130 runs) exists at `~/fullruns/test001-nothinking/` and will enable robust statistical analysis including Mann-Whitney U tests, effect sizes (Cliff's delta), and bootstrapped confidence intervals.

---

## 10. Discussion

So what does this dryrun actually tell us? Let's dig into what I learned about the framework's behavior on this trivially simple task, while being honest about the limitations inherent in N=1 experiments and ceiling effects.

### 10.1 What the Dryrun Tells Us

The Hello World task is, by design, trivially easy. All seven tiers score grade A with median scores between 0.943-0.983. This validates exactly what I said in Section 4: "Even T0 should nail this test." And it did.

**Ceiling effect dominates**: When quality converges at near-perfect levels, we can't differentiate tiers by capability. T0's empty prompt (subtest 00 uses no system prompt at all) and T6's maximal configuration (61 skills + all tools + 44 agents) produce equivalent functional output. This is exactly what we expect for Hello World — no amount of architectural sophistication helps when the task requires a single `print()` statement.

**Cost differentiation still works**: Despite quality convergence, Cost-of-Pass varies 3.8x from $0.065 (T5) to $0.247 (T6). This demonstrates the framework's ability to measure economic trade-offs even when quality metrics saturate. On more complex tasks with quality variance, both dimensions should differentiate.

**Pipeline validation successful**: The framework executed all seven tiers, collected 21 judge evaluations, computed consensus scores, generated 26 figures and 10 tables, and produced structured CSV exports. All components worked as designed.

### 10.2 Cost-Performance Trade-offs

The dryrun reveals a clear pattern: more isn't always better.

T5 achieves Frontier CoP through selective feature loading—it combines T1's efficient skills with T3's delegation patterns but avoids T6's "everything enabled" overhead. T5's cache creation tokens (4,629) are 5-10x lower than other tiers (23,106-44,337), directly explaining its cost advantage.

Here's the kicker: T6 costs the most ($0.247, or 3.8x Frontier CoP) despite scoring the lowest (0.943). Loading 61 skills + all tools + 44 agents actually made things worse. Judges explicitly noted cache artifacts and unnecessary complexity. This lines up with the hypothesis that prompt complexity hurts quality when the task is in the model's training set.

T4's hierarchical overhead is another example. T4 costs 30% more than T3 ($0.168 vs $0.129) for this trivial task. The self-correction loops and nested orchestration add latency (41.2s vs 29.9s) without improving quality. On complex tasks needing iterative refinement, maybe T4 justifies the overhead. On simple tasks, it's pure waste.

The Token Efficiency Chasm I talked about in Section 4? Confirmed. T6's 218K cache read tokens versus T0's 113K (1.94x increase) shows the cost of loading tool schemas. T2 (tooling) shows similar bloat—137K total tokens versus T1's 115K. Skills-based approaches (T1, T3) stay lean while still enabling domain knowledge.

Bottom line for production: match tier complexity to task complexity. Don't use T6 for trivial tasks. Don't use T0 for tasks needing specialized tools or multi-step reasoning. T5's hybrid approach nails it—load features selectively based on what the task actually needs, don't just maximize everything.

### 10.3 Judge Behavior

The 3-judge consensus mechanism reveals interesting patterns.

Haiku hands out S grades like candy—5 out of 7 tiers got perfect scores. Scores range 0.93-1.00, and Haiku consistently scores higher than Opus or Sonnet.

Opus never awards S grades. Scores range 0.93-0.96, consistently the toughest judge. Opus reliably deducts points for cache artifacts that Haiku overlooks.

Sonnet splits the difference. Awards S grades in 4/7 tiers (T2, T3, T4, T5), scores range 0.90-1.00. As the primary agent model, Sonnet's balanced scoring makes sense—it's the workhorse.

Inter-rater agreement is predictably low: Krippendorff's α = -0.117. But that's expected with N=1 and near-perfect scores. On tasks with more variance, agreement should improve as judges separate clear failures from clear successes.

Despite the disagreement, the 3-judge median works. When Haiku awards 1.00 and Opus awards 0.93, the median captures the true quality without getting pulled to either extreme. This validates the multi-judge consensus design.

One scaling problem: judge time dominates total latency. 77-86% of execution time is judge evaluation (128-178s), not agent execution (25-41s). With 3 judges per run, judge costs are 3x per evaluation. For large-scale experiments (N=10 × 113 subtests = 1,130 runs × 3 judges = 3,390 judge evaluations), judges eat the budget. Future work should explore single-judge evaluation or confidence-based selection (use Opus only when Sonnet/Haiku disagree).

### 10.4 Limitations

N=1 is descriptive only. I can't compute standard deviations, confidence intervals, or significance tests. All tier comparisons are point estimates. A single outlier run could flip all the conclusions.

Single task, trivial complexity. Hello World doesn't need skills, tools, multi-agent coordination, or hierarchical reasoning. The dryrun validates the pipeline works, not whether architectural complexity improves quality on hard tasks.

Single model. All agent runs use Sonnet 4.5. I haven't tested whether tier rankings hold for Opus 4.5, Haiku 4.5, or other model families.

No thinking mode variants. The dryrun uses standard inference without extended thinking. Models with thinking enabled might show different cost-quality trade-offs.

Ceiling effect masks capability differences. When all tiers score 0.94-0.98, I can't tell which architecture would excel on harder tasks. The full test001-nothinking experiment (113 subtests including complex multi-file repos) will differentiate capabilities.

Judge evaluation time bottleneck. 3 judges per run creates a 3x cost multiplier. Parallel judge execution would reduce latency but not cost.

---

## 11. Conclusions

Here's what I found: the Scylla framework works, end-to-end. All seven tiers executed successfully, three judges scored everything, and the analysis pipeline spit out 26 figures and 10 tables automatically. The dryrun validates the methodology on the simplest possible task—Hello World—before I scale up to complex multi-file repos.

What did I learn? Five things stand out. The framework is operational. Quality converges on trivial tasks—all tiers scored grade A, proving that throwing more complexity at Hello World doesn't help. Cost still varies 3.8x despite identical quality, showing the framework can measure economic trade-offs even when quality saturates. T5's hybrid approach achieves Frontier CoP by selectively loading features instead of maximizing everything. And the Token Efficiency Chasm I hypothesized in Section 4? Confirmed—T6 burns nearly double the tokens (218K vs 113K) compared to T0.

Did I answer my original questions? Partially. CoP lets me quantify efficiency—T5 is 3.8x cheaper than T6 despite equivalent quality. On this task, the sum is *not* more than the parts; T6 scores lowest despite highest cost. But the hard questions need harder tasks—I can't tell if any tier dominates universally from a single Hello World run, and I haven't tested model-to-model comparisons yet.

What about my hypotheses? The KISS principle hypothesis looks supported—maximal complexity (T6) scores worst on this training-set-likely task. But I haven't tested inverse KISS on out-of-distribution tasks yet, and specialization advantages (H1) are inconclusive because Hello World doesn't require delegation or tools.

Here's the practical takeaway: match tier complexity to task complexity. For trivial stuff, use T0-T1. For complex tasks, use T3 or T5. Don't use T6 unless the task genuinely needs everything—it costs 3.8x more with zero quality gain on simple tasks. The framework is ready for full-scale evaluation. Next step: run the complete test001-nothinking battery (N=10, 113 subtests, 1,130 runs total) to get statistical power and test harder tasks.

---

## 12. Further Work

The dryrun validates the framework works. Now it's time to scale up and fill in the gaps.

**Full-scale experiments**: The complete test001-nothinking dataset already exists (N=10, 113 subtests, 1,130 runs total). Running the analysis will enable statistical inference—Mann-Whitney U tests, effect sizes, bootstrapped confidence intervals—and differentiate tiers on complex tasks like multi-file refactoring and bug fixes. I also need to fix the Haiku data gaps (15 aborted runs, 218 missing judge evaluations) and add thinking-enabled variants (Sonnet 4.5 + Opus 4.5 with extended thinking) to test whether thinking helps single-agent tiers more than multi-agent tiers.

**Task diversity**: The dryrun only covers Hello World. The full test suite includes 46 additional tasks across greenfield (Flask APIs, CLI tools), brownfield (feature additions to existing repos), refactoring (extract function, eliminate duplication), bug fixes (off-by-one errors, race conditions), and documentation (README generation). Running these will show whether tier rankings hold across workflow categories or if certain tiers excel at specific task types.

**Cross-vendor and cross-model evaluation**: The framework is model-agnostic by design. Next step is testing other CLI tools (OpenAI Codex, Gemini CLI, DeepSeek Coder, Qwen, MBZ-K2, Kimi) to see if tier rankings (T0 < T1 < T3 < T5 on cost-efficiency) hold across vendors or are Claude-specific. Within Claude, I need to compare Opus 4.5, Sonnet 4.5, and Haiku 4.5 as agent models to quantify model-level cost-quality trade-offs.

**Advanced analysis**: Current analysis uses frequentist statistics. Bayesian hierarchical modeling would enable partial pooling across subtests, uncertainty quantification for tier rankings, and principled handling of missing Haiku data. Process metrics (time-to-first-token, strategic drift, tool call traces) would reveal *how* agents work, not just final outcomes. Human expert baselines (hire 10 senior engineers, run the same test battery, compare CoP) would validate whether agents are actually economically competitive. And longitudinal tracking (re-run test001 quarterly with latest models) would show if Frontier CoP decreases over time as models improve.

---

## Acknowledgements

This work was self-funded by the author.

---

## References

[1] Liu, X., Yu, H., Zhang, H., Xu, Y., Lei, X., Lai, H., Gu, Y., Ding, H., Men, K., Yang, K., Zhang, S., Deng, X., Zeng, A., Du, Z., Zhang, C., Shen, S., Zhang, T., Su, Y., Sun, H., Huang, M., Dong, Y., & Tang, J. (2023). **AgentBench: Evaluating LLMs as Agents.** *arXiv preprint arXiv:2308.03688.* https://arxiv.org/abs/2308.03688

[2] Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2024). **SWE-bench: Can Language Models Resolve Real-world GitHub Issues?** *International Conference on Learning Representations (ICLR).* https://arxiv.org/abs/2310.06770

[3] Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). **ReAct: Synergizing Reasoning and Acting in Language Models.** *International Conference on Learning Representations (ICLR).* https://arxiv.org/abs/2210.03629 (Note: TAU-Bench reference placeholder — replace with actual citation when published)

[4] Zhu, K., Wang, J., Zhou, J., Wang, Z., Chen, H., Wang, Y., Yang, L., Ye, W., Gong, N. Z., Zhang, Y., & Xie, X. (2024). **PromptBench: Towards Evaluating the Robustness of Large Language Models on Adversarial Prompts.** *arXiv preprint arXiv:2306.04528.* https://arxiv.org/abs/2306.04528

[5] **PromptEval: A Comprehensive Evaluation Framework for Prompt Engineering.** Project repository and documentation. https://github.com/prompteval (Note: Placeholder citation — replace with official publication if available)

[6] Reserved for future citation.

[7] Anthropic. (2024). **Claude Code: Agentic CLI Tool for Software Development.** Anthropic AI. https://www.anthropic.com/claude/code

[8] Gao, L., Tow, J., Biderman, S., Black, S., DiPofi, A., Foster, C., Golding, L., Hsu, J., McDonell, K., Muennighoff, N., Phang, J., Reynolds, L., Tang, E., Thite, A., Wang, B., Wang, K., & Zou, A. (2021). **A Framework for Few-Shot Language Model Evaluation.** Zenodo. https://doi.org/10.5281/zenodo.5371628 (lm-evaluation-harness)

[9] **safety-net: Claude Code Plugin for Dangerous Operation Blocking.** CC-Marketplace. https://github.com/cc-marketplace/safety-net

[10] **CC-Marketplace: Community Marketplace for Claude Code Plugins and Skills.** https://github.com/cc-marketplace

---

## Appendices

### Appendix A: Detailed Metric Definitions

For comprehensive metric definitions including formulas, calculation methods, and interpretation guidelines, see:
- `ProjectScylla/.claude/shared/metrics-definitions.md`
- `ProjectScylla/docs/design/metrics-formulas.md`

Key metrics include Pass-Rate, Implementation Rate (Impl-Rate), Fine-Grained Progress Rate ($R_{Prog}$), Consistency, Change Fail Percentage (CFP), Cost-of-Pass (CoP), Frontier CoP, Token Distribution, and Latency.

### Appendix B: Data Dictionary and Generated Outputs

This appendix references tables and figures generated by the analysis pipeline for the dryrun experiment. All outputs are located in `docs/paper-dryrun/`.

**Tables** (Markdown format in `docs/paper-dryrun/tables/`):

- **Table 1 (Tab01)**: Tier Summary — Pass rate, mean score, median, consistency, CoP for each tier
  - File: `tab01_tier_summary.md`
  - Contains: 7 rows (T0-T6), 8 columns (model, tier, subtests, pass rate with CI, mean score ± σ, median, consistency, CoP)

- **Table 3 (Tab03)**: Judge Agreement — Pairwise correlations and mean score differences
  - File: `tab03_judge_agreement.md`
  - Contains: Spearman ρ, Pearson r, mean |Δ Score| for Opus-Sonnet, Opus-Haiku, Sonnet-Haiku pairs
  - Includes: Krippendorff's α (interval) = -0.117

- **Table 5 (Tab05)**: Cost Analysis — Token breakdown and cost by tier
  - File: `tab05_cost_analysis.md`
  - Contains: Mean cost, total cost, CoP, input tokens, output tokens, cache read, cache create for T0-T6

**Figures** (PNG/PDF + Vega-Lite JSON + CSV in `docs/paper-dryrun/figures/`):

- **Figure 6 (Fig06)**: Cost-of-Pass by Tier
  - Files: `fig06_cop_by_tier.{png,pdf,vl.json,csv}`
  - Shows: Bar chart of CoP across T0-T6, highlights Frontier CoP ($0.065 at T5)

- **Figure 7 (Fig07)**: Token Distribution
  - Files: `fig07_token_distribution.{png,pdf,vl.json,csv}`
  - Shows: Stacked bar chart of input, output, cache create, cache read tokens by tier
  - Demonstrates: Token Efficiency Chasm (T6's 218K cache read vs T0's 113K)

- **Figure 9 (Fig09)**: Criteria Performance by Tier
  - Files: `fig09_criteria_by_tier.{png,pdf,vl.json,csv}`
  - Shows: Heatmap or grouped bar of 5 criteria (functional, code_quality, proportionality, build_pipeline, overall_quality) across tiers
  - Highlights: Near-perfect functional correctness, variance in proportionality/overall_quality

- **Figure 13 (Fig13)**: Latency Breakdown
  - Files: `fig13_latency.{png,pdf,vl.json,csv}`
  - Shows: Stacked bar chart of agent time vs judge time by tier
  - Demonstrates: Judge evaluation dominates (77-86% of total time)

- **Figure 14 (Fig14)**: Judge Agreement
  - Files: `fig14_judge_agreement.{png,pdf,vl.json,csv}`
  - Shows: Score distributions by judge (Opus, Sonnet, Haiku) across tiers
  - Highlights: Haiku most generous, Opus most conservative

**Additional Figures Available** (26 total, see `docs/paper-dryrun/figures/` for complete list):

- Fig01: Score variance by tier
- Fig02: Judge variance (box plots by judge)
- Fig03: Failure rate by tier (all zeros in dryrun)
- Fig04: Pass rate by tier (all 1.0 in dryrun)
- Fig05: Grade heatmap
- Fig08: Cost-quality Pareto frontier
- Fig10: Score violin plots
- Fig11: Tier uplift (with significance markers)
- Fig15: Subtest heatmap
- Fig19: Effect size forest plot
- Fig20: Metric correlation heatmap
- Fig24: Score histograms
- Fig25-27: Implementation rate analysis

**Data Files** (CSV + JSON in `docs/paper-dryrun/data/`):

- `runs.csv`: 7 rows, 19 columns (experiment, model, tier, subtest, run_number, score, impl_rate, passed, grade, cost, duration, tokens, exit_code)
- `judges.csv`: 21 rows (7 runs × 3 judges), columns include judge_model, judge_score, judge_impl_rate, judge_passed, judge_grade, judge_reasoning
- `criteria.csv`: 105 rows (21 judges × 5 criteria), columns include criterion_name, points_achieved, points_possible
- `summary.json`: Overall statistics (total runs, pass rate, mean score, total cost, by-model and by-tier breakdowns)
- `statistical_results.json`: Statistical test results (all show insufficient sample size warnings for N=1)

**Usage Notes**:

- All PNG/PDF figures are publication-ready at 300 DPI
- Vega-Lite JSON specs can be edited and re-rendered with `vl-convert-python`
- LaTeX snippets (`*_include.tex`) enable direct inclusion in LaTeX documents
- CSV data files enable custom analysis and replotting in R, Python, or Excel

### Appendix C: Reproducibility Checklist

**Repository**: `https://github.com/HomericIntelligence/ProjectScylla`

**Key Configuration Files**:

- Tier definitions: `<project_root>/config/tiers/tiers.yaml`
- Model configurations: `<project_root>/config/models/*.yaml`
- Judge system prompt: `<project_root>/config/judge/system_prompt.md`
- Test definitions: `<project_root>/tests/*/test.yaml`
- Rubric schemas: `<project_root>/tests/*/expected/rubric.yaml`

**Required Software**:

- Pixi (package manager)
- Docker (containerization)
- Claude Code CLI
- Mojo 0.26.1, Python 3.12+

**Execution Steps**:

```bash
# 1. Clone repository
git clone https://github.com/HomericIntelligence/ProjectScylla
cd ProjectScylla

# 2. Install dependencies
pixi install

# 3. Run evaluation (example for test-001, tier T0)
pixi run mojo scylla/run_evaluation.mojo \
  --test tests/001-hello-world \
  --tier T0 \
  --runs 10

# 4. Generate report
pixi run mojo scylla/generate_report.mojo \
  --results runs/001-hello-world/T0
```

**Artifact Locations**:

- Run outputs: `<project_root>/runs/<test-id>/<tier>/`
- Consensus judgments: `<project_root>/runs/<test-id>/<tier>/judgment.json`
- Metrics summaries: `<project_root>/summaries/<test-id>/metrics.json`
- Final reports: `<project_root>/reports/<test-id>/report.md`
