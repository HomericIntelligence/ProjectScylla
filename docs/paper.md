# Taming Scylla

## Understanding the multi-headed agentic deamon of the coding seas

Micah Villmow
Individual
research@villmow.us

---

## Abstract

LLM-based tools are automating more and more software development tasks, but there's no rigorous way to evaluate how different developer visible architectural choices, (e.g.prompts, skills, tools, multi-agent setups), actually affect both the capability and cost of the tools. This paper introduces Scylla, an evaluation framework for benchmarking these agentic coding tools through a structured ablation study. The methodology uses seven testing tiers (T0-T6) that progressively add complexity and capabilities to the tools. This gives us a broad range of data to validate what is influencing the resulting solutions and how they are influence. The key metric is Cost-of-Pass (CoP), the expected dollar cost to get a correct solution, which lets us directly compare solution complexity against operational efficiency. The framework is model agnostic, but in this case Anthropic's Claude (Opus, Sonnet, Haiku) is used, while also utilizing independent LLM judges. These independent judges score the results using both direct tests, human driven rubrics, and judgement evaluations. The result is a reproducible framework that quantifies the trade-offs between increasing agent complexity and the results that are achieved from this complexity.

---

## Keywords

LLM agents, software engineering benchmarks, cost-of-pass, multi-agent systems, prompt engineering, ablation studies, evaluation frameworks, CLI tools, agentic AI

---

## 1. Summary

With the advancement of large language models has come a massive increase in capabilities for automated computer interactions. What used to require hand-coded algorithms and pipelines can now be done automatically using state of the art coding models to generate instructions that can then be utilized to further improve automated approaches. However, understanding what improves these language models is more of black magic than art, let alone a rigorous science. This paper's goal is to help demistify the magic of prompt engineering by proposing a rigorous evaluation framework across multiple dimensions to help determine how agents interact, the scale that of changes for the agentics, and an attempt to quantify with numbers the benefits of each approach across a broad range of activities.

There are benchmarks for measuring LLM's workflows in various domains, such as agent-bench[1], swe-bench[2], tau-bench[3], etc... There are also prompt evaluation benchmarks such as PromptBench[4] or PromptEval[5]. This paper focuses specifically on coding tools, specifically industry leading tool Claude Code[7], and how prompt modification can change the behavior of the model for better or for worse. This paper also introduces a framework for evaluating other tools in a systematic way, thus allowing extension to domains outside of CLI based coding tools. We show that <insert findings here>. 

This implies that there is still a <summarize implications> and repost here.

---

## 2. Introduction

Anthropic has many good resources for improving Claude Code on their engineering blog, but there is not a simple way to measure easily whether changes to the prompt instructions actually benefit in the way that the user can easily comprehend. Therefor, I am introducing Scylla, a testing framework for evaluating prompts, tools, skills, and agents for solving problems that are common for day to day coding tasks. I wanted to know if sub-agents, skills, tools, or mcp servers were actually contributing to improved code output, without relying on my gut or intuition. This problem came up multiple times when asked by others to explain how to better utilize CLI tools for programming. In my experience, the quality of the prompts has a dramatic improvement on the output of the results. Whether its the prompt to call the tool or MCP server, the prompt to spawn a sub-agent, or the prompt to trigger a skill, these language based triggers are fuzzy in their meaning. Unlike a traditional programming language that is very explicit in what it is means and what it does, it is not a direct mapping from text to action. This framework is my attempt at helping unwrap this problem.

First, in section 3, I will introduce the current work that is being done in this area, and explain how they approach the problem. Then, in section 4, I will introduce the testing methodology along with an in-depth analysis of the first test case. This will provide the needed understanding of what is being tested, along with why, on something that should be easily dissectable and understandable. The next three section will introduce three more test cases from different categories of tasks that show the variance of results from the same set of prompts. After that, I will dissect some of the more interesting cases where there was large impacts on the baseline behavior of the model, both positive and negative. The final section will showcase the final results across a larger set of test cases, and point to further areas of research, and how to extend this to other models.

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

Given that we are testing production tools and not models, many, if not all, of the prior work on evaluating prompts and benchmarks does not apply directly here, since there is possibly a large level of indirection between what we are testing and what actually gets executed by the model. The tool is a black box and what is executing is hidden behind multiple layers, first being the CLI tool itself, but also whatever optimizations and implementation details the vendor implemnents on top of their trained base model. The models themselves are not documented publicly, as these details are competitive advantages, and the pre or post-processing that occurs is not visible to the user as they occur on the vendors servers.

There are multiple benchmarks on judging the models, such as Agent-Bench[1], SWE-Bench[2], and TAU-Bench[3], but no standard benchmarks on CLI tools, like Claude Code, on how prompts affect them. The reader can also investigate PromptEval, PromptBench, or lm-evaludation-harness[8], but these also don't benchmark the CLI tools, which are used in production today. The next paragraphs will explain in high level details the various other options on the market.

There are several good benchmarks out there for evaluating LLM agents. SWE-Bench[2] tests models on real GitHub issues and answers questions such as, "can they actually fix bugs and add features to real codebases?". Agent-Bench[1] goes broader, testing multi-turn agents across different environments like operating systems, databases, and knowledge graphs, with fine-grained metrics that go beyond just "did it work or not". TAU-Bench[3] focuses on whether agents can effectively use external tools to get things done. But here's the thing: all of these evaluate the models directly. They don't address the agentic loop, hooks, skills, MCP servers, or even vendor optimizations. My work focuses on that tool interface rather than the raw model underneath.

For prompt evaluation specifically, there's PromptBench[4], which gives you a unified way to test prompts across different tasks. PromptEval[5] automates checking whether prompts are good, looking at both correctness and robustness. And EleutherAI's lm-evaluation-harness[8] provides a standardized way to compare model performance across hundreds of tasks. The problem is, these all assume you have direct access to model inputs and outputs. With production tools like Claude Code, the model is wrapped one part of a larger application; the system prompts, tool schemas, skill definitions, orchestration logic all influence how a model works. I believe you can't just test the model; you have to test the whole system. That's what this framework does: it treats the CLI interface as the evaluation boundary and figures out what actually works when you're using these tools in practice.

My work is based solely on evaluating CLI tools, as the CLI's tools are more than the model themselves. As I mentiooned earlier, the agentic loop, with hooks, tools, skills, sub-agents, MCP servers, and other logic wrapped together into a single application where the only way to get control of the behavior is through the english language is what I want to evaluate for effectiveness. From this interface, programmatic tools can be spawned, but the ability to properly and accurately interact with the agent is via a fuzzy language interface, and not via traditional programmatic interfaces. While there are some hooks that allow extra programmatic validation with Claude Code, we are not evaluating those at this time. Claude code has the ability to use agentic evaluation at the hook boundary, but triggering it is guaranteed, and not language based.

---

## 4. Test Methodology

### 4.1 Experimental Design

This experiment is designed by testing english phrases, colloqually known as prompts, via the various methodologies exposed by a CLI tool, in this case Claude Code. The experiment is run by allowing an agent a nearly unfeatered access to the system, only blocking dangerous ops, thanks to the safety-net plugin[9] from cc-marketplace[10], to perform a task. The task has a well defined solution that is then judged by three different LLM's of various 'strength'. In this case Claude Opus 4.5, Claude Sonnet 4.5, and Claude Haiku 4.5. Each of the 4.5 models are sufficiently advanced in capabilities to be considered independent judges of a task with low failure rates. The judges are provided the same prompt, so the only difference between their results comes from the judge training and implementation differences and not from the prompt or test input. Each judge will receive the output of the task LLM, and provide the results based on the criteria. The judges have the following categories of evaluation; functional correctness, code quality, development pipeline, securty and safety, proportionality and professionalism, and patchfile correctness.

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

Each experiment can be reproduced by running by running the top level test run script, which will launch the same set of tasks with the same parameters, where the only variation is the judgement of the LLM's judges when determining how to judge the work.

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

2. **T1-T2 (Skills vs Tools):** Here's where it gets interesting. T1 uses skills, domain knowledge baked into prompts. Token-efficient. T2 uses external tools via JSON schemas. Problem is, loading all those tool definitions can eat 150,000+ tokens before the model even starts thinking[FIXME: Where did this come from?]. I call this the "Token Efficiency Chasm."[FIXME: Where did this come from?]

3. **T3-T4 (Multi-Agent Setups):** T3 does flat delegation, break tasks into smaller pieces and assign them to specialist agents. Production data shows this can cut costs by 54% and latency by 72%[FIXME: Where did this come from?]. T4 adds hierarchy with self-correction loops, but that can double your inference costs per iteration[FIXME: Where did this come from?].

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
| T5 | Best case scenarios | Attempt to pick the best case scenarious from previous runs to see if the sum is more than its parts |
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

Skills are organized by domain. Here's what we're testing in T2:

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

- Three judges per evaluation: Opus 4.5, Sonnet 4, Haiku 4.5
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

I've got **47 test cases** covering different workflows and complexity levels:

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

**Sonnet 4** is the workhorse for T1-T3. Balanced cost/performance at $3/$15 per million tokens. Handles most standard dev work---code gen, refactoring, build configs. The middle judge for consensus.

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

### 12.1 Future Model Evaluation

The framework can extend to other CLI tools and models:

| System | Primary Model(s) | Provider | Status |
|--------|------------------|----------|--------|
| OpenAI Codex/GPT-5.2 | GPT family | OpenAI | Future work |
| Gemini CLI | Gemini 3.0 Pro | Google | Future work |
| DeepSeek Coder | DeepSeek models | DeepSeek | Future work |
| Qwen CLI | Qwen 3 | Alibaba | Future work |
| MBZ-K2 | MBZ-K2 | MBZUAI | Future work |
| Kimi CLI | Kimi-K2, Kimi-3 | Moonshot AI | Future work |

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
- `ProjectScylla/.claude/shared/metrics-definitions.md`
- `ProjectScylla/docs/design/metrics-formulas.md`

Key metrics include Pass-Rate, Implementation Rate (Impl-Rate), Fine-Grained Progress Rate ($R_{Prog}$), Consistency, Change Fail Percentage (CFP), Cost-of-Pass (CoP), Frontier CoP, Token Distribution, and Latency.

### Appendix B: Additional Tables and Figures

[Supplementary tables and figures to be included with experimental results. Expected content: (1) Full tier-by-tier performance tables for all 47 test cases; (2) Token distribution visualizations showing component-level cost breakdown; (3) Latency distribution box plots across tiers; (4) Statistical significance matrices (p-values for tier comparisons); (5) Failure mode categorization tables; (6) Workflow category stratification charts.]

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
pixi run mojo src/scylla/run_evaluation.mojo \
  --test tests/001-hello-world \
  --tier T0 \
  --runs 10

# 4. Generate report
pixi run mojo src/scylla/generate_report.mojo \
  --results runs/001-hello-world/T0
```

**Artifact Locations**:

- Run outputs: `<project_root>/runs/<test-id>/<tier>/`
- Consensus judgments: `<project_root>/runs/<test-id>/<tier>/judgment.json`
- Metrics summaries: `<project_root>/summaries/<test-id>/metrics.json`
- Final reports: `<project_root>/reports/<test-id>/report.md`
