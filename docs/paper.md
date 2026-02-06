# Taming Scylla

## Understanding the multi-headed agentic daemon of the coding seas

Micah Villmow
Individual
research@villmow.us

---

## Abstract

LLM-based tools are automating more software development tasks at an exponential rate. But
there's no rigorous way to evaluate how different architectural choices, prompts,
skills, tools, multi-agent setups, materially affect both capability and cost.

This paper introduces Scylla, an evaluation framework for benchmarking agentic
coding tools through structured ablation studies. The methodology uses seven
testing tiers (T0-T6) that progressively add complexity. This lets us isolate
what directly influences results and how.

The key metric is Cost-of-Pass (CoP): the expected dollar cost to get one
correct solution. This directly quantifies the trade-off between complexity and
efficiency.

The framework is model-agnostic, designed to work with any CLI tool. This paper
demonstrates it with Claude Sonnet 4.5, using multiple LLM judges (Opus 4.5,
Sonnet 4.5, Haiku 4.5) from the same vendor for evaluation consensus. Judges
score results using direct tests, human-driven rubrics, and qualitative
assessment.

The result is a reproducible framework that quantifies trade-offs between agent
complexity and actual outcomes.

---

## Keywords

LLM agents, software engineering benchmarks, cost-of-pass, multi-agent systems,
prompt engineering, ablation studies, evaluation frameworks, CLI tools, agentic
AI

---

## 1. Summary

Large language models have ushered in massive increases in capabilities for
automated computer interactions. What used to require hand-coded algorithms and
pipelines can now be done automatically using state of the art coding models to
generate instructions that can then be utilized to further improve automated
approaches. However, understanding what improves these language models is more
of black magic than art, let alone a rigorous science. This paper's goal is to
help demystify the magic of prompt engineering by proposing a rigorous
evaluation framework across multiple dimensions to help determine how agents
interact, the scale of changes for the agentics, and an attempt to quantify
with numbers the benefits of each approach across a broad range of activities.

There are benchmarks for measuring LLM's workflows in various domains, such as
agent-bench[1], swe-bench[2], tau-bench[3], etc... There are also prompt
evaluation benchmarks such as PromptBench[4] or PromptEval[5]. This paper
focuses specifically on coding tools, specifically industry leading tool Claude
Code[7], and how prompt modification can change the behavior of the model for
better or for worse. This paper introduces a framework for evaluating agentic
coding tools in a systematic way, thus allowing extension to domains outside of
CLI based coding tools. I show that on a trivial Hello World task, all seven
tiers (T0-T6) achieve equivalent quality (all grade A, scores 0.943-0.983) while
cost varies 3.8x from $0.065 (T5 hybrid) to $0.247 (T6 super). The framework
successfully differentiates cost structures across architectural choices even
when quality converges.

This implies that architectural complexity does not always improve quality, and
that careful hybrid designs (T5) can achieve Frontier Cost-of-Pass by
selectively combining features rather than maximizing them. The dryrun validates
the framework's ability to measure these trade-offs empirically.

---

## 2. Introduction

Anthropic has many good resources for improving Claude Code on their engineering
blog, but despite these, there are not any intuitive and user-friendly methods
for comparing whether changes to the prompt instructions will yield tangible
benefits. Therefore, I am introducing Scylla, a testing framework for evaluating
prompts, tools, skills, and agents for solving problems that are common for
day-to-day coding tasks. I wanted to know if sub-agents, skills, tools, or mcp
servers were contributing to actual improved code output, without relying on my
gut or intuition. This problem came up multiple times when asked by others to
explain how to better utilize CLI tools for programming. In my experience, the
quality of the prompts has a dramatic improvement on the output of the results.
Whether it is the prompt to call the tool or MCP server, the prompt to spawn a
sub-agent, or the prompt to trigger a skill, these language-based triggers are
fuzzy in their meaning. Unlike a traditional programming language that is very
explicit in what it is means and what it does, prompts do not map directly and
consistently to action. This framework is my attempt at helping unwrap this
problem.

First, in section 3, I will introduce the current work that is being done in
this area, and explain how they approach the problem. Then, in section 4, I will
introduce the testing methodology along with an in-depth analysis of the first
test case. This will provide the needed understanding of what is being tested,
along with why, on something that should be easily analyzed and
understandable. Then I will go over the rest of the testing framework to
showcase what is being tested, measured, and why these are being tested using
simple cases introduced in the previous sections.

The questions I am investigating are:

* Is it possible to quantify whether a task is solveable more efficiently by one
  methodology over others?
* Is the sum of a prompt more than the individual parts?
* Are there core improvements that can be made purely through extensions to
  claude code that are generic for all workloads?
* Are there specific prompt techniques that have secondary effects, positive or
  negative, on other prompt techniques?
* Holding the tool and prompt constant, how much does the underlying model
  contribute to the quality of the results?

Some hypotheses I have are:

* Certain tasks excel when run as sub-tasks, or tools, or mcp, or skills, that
  are unrelated to context management.
* Prompt complexity has a negative correlation to higher quality results, i.e.
  KISS principle, in scenarios that is part of the training set.
* Prompt complexity has a positive correlation to higher quality results, i.e.
  an inverse KISS principle, in scenarios outside of the training set.

---

## 3. Related Work

Given that we are testing production tools and not models, many, if not all, of
the prior work on evaluating prompts and benchmarks do not apply here. Since
there is possibly a large level of indirection between what we are testing and
what actually gets executed by the model due to engineering trade-offs, I am
considering the tool to be a black box and not attempting to reverse engineer
this tool. Despite this, what is executing is hidden behind multiple layers,
first being the CLI tool itself, but also whatever optimizations and
implementation details the vendor implements on top of their trained base model.
The models themselves are not fully documented publicly, as these details are
competitive advantages, and the pre or post-processing that occurs is not always
visible to the user as they can occur vendor-side.

There are multiple benchmarks on judging the models, such as Agent-Bench[1],
SWE-Bench[2], and TAU-Bench[3], but no standard benchmarks on CLI tools, like
Claude Code, on how prompts affect them. The reader can also investigate
PromptEval, PromptBench, or lm-evaluation-harness[8], but these also do not
benchmark the CLI tools, which are used in production today. The next paragraphs
will explain in high level details the various other options on the market.

There are several good benchmarks for evaluating LLM agents. SWE-Bench[2] tests
models on real GitHub issues, can they actually fix bugs and add features to real
codebases? Agent-Bench[1] goes broader, testing multi-turn agents across
different environments like operating systems, databases, and knowledge graphs,
with fine-grained metrics beyond just pass/fail. TAU-Bench[3] focuses on whether
agents can effectively use external tools. These benchmarks evaluate the models
directly. They do not address the full agentic loop, hooks, skills, MCP servers,
vendor optimizations, orchestration logic. My work focuses on that tool
interface rather than the raw model underneath.

For prompt evaluation, there is PromptBench[4] (unified testing across tasks),
PromptEval[5] (automated correctness and robustness checking), and EleutherAI's
lm-evaluation-harness[8] (standardized multi-task comparison). There is a
problem in that the aforementioned all assume direct access to model inputs and
outputs. With production CLI tools like Claude Code, the model is wrapped in
layers of system prompts, tool schemas, skill definitions, and orchestration
logic. I cannot just test the model in isolation, so I must test the whole
system.

My work is based solely on evaluating CLI tools, as the CLI's tools are more
than the model themselves. As I mentioned earlier, the agentic loop, with hooks,
tools, skills, sub-agents, MCP servers, and other logic wrapped together into a
single application where the only way to get control of the behavior is through
the English language is what I want to evaluate for effectiveness. From this
interface, programmatic tools can be spawned, but the ability to properly and
accurately interact with the agent is via a fuzzy language interface, and not
via traditional programmatic interfaces. While there are some hooks that allow
extra programmatic validation with Claude Code, I am not evaluating those at this
time. Claude Code has the ability to use agentic evaluation at the hook
boundary, but triggering it is guaranteed (and not language-based), so it is not
interesting for probabilistic evaluation.

## 4. Test Methodology

### 4.1 Experimental Design

This experiment is designed by testing english phrases, colloquially known as
prompts, via the various methodologies exposed by a CLI tool, in this case
Claude Code. The prompts to be tested are taken from the ProjectOdyssey[6] git
repository at github hash 011a3ff on December 30th 2025. The prompts are broken
down into their components and separated into various tiers which will be
discussed later. These components are used to setup the experiment, which is run
by allowing an agent a nearly unfettered access to the system, only blocking
dangerous ops, thanks to the safety-net plugin[9] from cc-marketplace[10], to
perform a task. The task has a well defined solution that is then judged by
three different LLM's of various 'strength'. In this case Claude Opus 4.5,
Claude Sonnet 4.5, and Claude Haiku 4.5. Each of the 4.5 models are sufficiently
advanced in capabilities to be considered independent judges of a task with low
failure rates. The judges are provided the same prompt, so the only difference
between their results comes from the judge training and implementation
differences and not from the prompt or test input. Each judge will receive the
output of the task LLM, and provide the results based on the criteria. The
judges have the following categories of evaluation; functional correctness, code
quality, development pipeline, security and safety, proportionality and
professionalism, and patchfile correctness.

**Table 4.1: LLM-as-Judge Evaluation Categories**

| Category | Weight | Scoring Type | Description |
|----------|--------|--------------|-------------|
| Functional Correctness | 0.35 | Checklist | File existence, output correctness, exit codes, exact output matching |
| Code Quality | 0.20 | Checklist | Syntax validity, idiomatic code, unused imports, PEP8 compliance |
| Proportionality | 0.15 | Checklist | Appropriate scope, minimal files, no unnecessary artifacts or tests |
| Build Pipeline | 0.10 | Checklist | Build passes, format checks, tests (when applicable), pre-commit hooks |
| Overall Quality | 0.20 | Subjective | Engineering judgment on appropriateness, maintainability, and senior engineer approval |

**Total Weight**: 1.0 (100%)

Each category contributes proportionally to the final score. Here is the formula:

$$S_{final} = \sum_{i} w_i \cdot \frac{P_i^{achieved}}{P_i^{max}}$$

where $w_i$ are the category weights (they sum to 1.0), and $P_i$ is the points
the test got versus the maximum possible (skipping any N/A items). For scoring
individual items:

- **Binary items**: You either get it or you do not (1.0 or 0.0)
- **Graduated items**: Partial credit on a 0.0-1.0 scale based on results
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
| S | 1.00 | Amazing | Perfect score, goes above and beyond |
| A | ≥ 0.80 | Excellent | Production ready |
| B | ≥ 0.60 | Good | Works well, minor tweaks needed |
| C | ≥ 0.40 | Acceptable | It works but has issues |
| D | ≥ 0.20 | Marginal | Lots of problems but salvageable with effort |
| F | < 0.20 | Failing | Complete failure of task |

I use **0.60** (Grade B) as the pass threshold. That means the solution works
and meets requirements, even if there is room for minor improvements. An S grade
needs a perfect 1.00 and you have to actually exceed what was asked for. I would
not expect many, if any, tests to get an S rating.

Each experiment can be reproduced by running the top level test run script,
which will launch the same set of tasks with the same parameters, where the only
variation is the judgement of the LLM's judges when determining how to judge the
work.

This finishes the summary of a single test. However, the test themselves are
defined differently. The test are a prompt and a configuration file that specify
a repository, a github hash, a set of configuration files to override any
pre-defined tooling, set of commands to validate the results, and a container to
run everything in to help with reproducibility. The first test is being used as
an example in this paper, and also as a pipecleaner to show that everything
works as expected. This example is 'hello world' from octocat, but forked to my
repository just to make sure that the repository is not polluted. The precaution
is done just in case the agents make mistakes or do things that the original
author probably does not want to be bothered by.

#### Test-001: Hello World Baseline

First, let us look at the simplest possible test to make sure everything works.
This is literally just creating a "Hello World" script, which is a pipe-cleaner
for the infrastructure and to discuss the methodology without intermixing with
the complexity of more realistic tests.

**Test Configuration:**

| Field | Value |
|-------|-------|
| ID | `test-001` |
| Name | Hello World Task |
| Timeout | 300 seconds |
| Pass Threshold | 0.60 (Grade B) |

**Task Prompt:**

Create a Python script `hello.py` that prints "Hello, World!" to stdout, exits
with code 0, and uses relative paths. The script should be created in the
current working directory.

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
| Functional Correctness | 35% | File `hello.py` exists; running `python
  hello.py` produces correct output; exit code 0; output exactly matches |
| Code Quality | 20% | Valid Python syntax; idiomatic code; no unused imports;
  PEP8 compliant |
| Proportionality | 15% | Total files ≤ 3; LOC ≤ 3; no unnecessary test files;
  build artifacts cleaned up |
| Build Pipeline | 10% | Syntax check passes; format check passes (if ruff
  available); tests pass (if required) |
| Overall Quality | 20% | Senior engineer approval; appropriately scoped for
  Hello World |

**What Should Happen:**

Even T0 (no system prompt at all) is expected to get an 'A',
since we are talking ≥ 0.80 scores. If T0 cannot do Hello World, I will assume
that something is fundamentally wrong with the framework itself and throw out
the results. Higher tiers (T1-T6) should also succeed, as there is no reason
fancy prompts or multi-agent setups would help with something this simple.
However, if performance drops on this test, it means the added complexity is
actually making things worse even on something so simple, so if this happens, we
will analyze why.

Now that we have gone over the test itself, let us discuss the strategy and tiered
approach. The first thing to test is with no prompt at all, including no system
prompt, if the tool allows it. This is to provide as close to a baseline as the
base model as possible by overwriting the system prompt with an empty string and
not using any configuration or non-default settings from the tool. This provides
the baseline that all improvements are measured against. For something as simple
as hello world, this baseline should solve the task. The test setup is such that
variability in judging will occur, but there is not much one can do to improve
the output of a hello world script. However, there are things that you can do
that make things worse or break the expected behavior, but I would expect all
solutions to be the exact same for all the tests. Divergence points to
interesting results.

#### Tiered Ablation Strategy

The core idea is simple: start with nothing, then add one set of things at a
time to see what actually helps. This ablation study uses seven tiers that
progressively add complexity, with **113 sub-tests** total. Each tier gets
tested independently so we can isolate what each component contributes.

**Table 4.3: Testing Tiers (Ablation Study Framework)**

| Tier | Name | Sub-tests | Primary Focus | Tools | Delegation | Key Characteristic |
|------|------|-----------|---------------|-------|------------|-------------------|
| T0 | Prompts | 24 | System prompt ablation (empty → full) | - | No | Baseline: empty prompt (00) through full 1787-line CLAUDE.md (03) plus 18 individual blocks (B01-B18) |
| T1 | Skills | 10 | Domain expertise via installed skills | Default | No | Token-efficient domain knowledge; categories: Agent (5), CI/CD (7), Documentation (4), GitHub (10), Language Specific (10), Quality (5), Workflow (5) |
| T2 | Tooling | 15 | External tools and MCP servers | Yes | No | External API access; introduces token efficiency chasm from schema loading |
| T3 | Delegation | 41 | Flat multi-agent with specialists | Yes | Yes | Atomic task design; flat orchestration with specialist agents (L2-L5) |
| T4 | Hierarchy | 7 | Nested orchestration with orchestrators | Yes | Yes | Hierarchical coordination (L0-L1); Task Decomposer, Actor, Monitor, Evaluator roles |
| T5 | Hybrid | 15+ | Optimal combinations from all tiers | Yes | Yes | Combines various combinations of previously ranked skills |
| T6 | Super | 1 | Maximum capability configuration | All | All | Theoretical maximum: 61 skills, all MCP servers, 44 agents, full prompt; establishes capability ceiling |

**How the Tiers Work:**

1. **T0 (Baseline):** Start with an empty prompt (00-empty) to see what the raw
   model can do, then go all the way up to the full 1787-line CLAUDE.md
   (03-full). Individual blocks (B01-B18) let me test each piece of the prompt
   separately to see what actually matters.

2. **T1-T2 (Skills vs Tools):** T1 uses skills, domain knowledge baked into
   prompts. Token-efficient. T2 uses external tools via JSON schemas. Problem
   is, loading all those tool definitions inflates token usage. I call this the
   "Token Efficiency Chasm", the gap between lean skill-based approaches and
   schema-heavy tool architectures.

3. **T3-T4 (Multi-Agent Setups):** T3 does flat delegation, breaking tasks into
   smaller pieces and assigning them to specialist agents. T4 adds hierarchy
   with self-correction loops, but this complexity can increase costs.

4. **T5 (Smart Combinations):** Take what works from the other tiers, combine
   then together in different combinations. A single test would have the best
   T1 skills, T2 tools, T3 agents, and T4 task delegation. We do not want to
   brute force here due to combinatorial explosion, but picking combinations of
   the top few categories can help give idea what combinations work best
   together.

5. **T6 (Everything):** Turn on everything at once. All skills, tools, agents,
   prompt segments, and servers. This I hope establishes the theoretical max
   performance and shows where diminishing returns kick in, but also can show
   signs of over-engineering if it is occurring.

For each tier T(n), I compare it directly against T(n-1) to see what that
specific change actually achieves in terms of performance and cost.

### 4.2 Dimensional Search Space

The framework tests across four different dimensions. Each one is an independent
knob you can turn, and they all affect both what the agent can do and how much
it costs.

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

Prompt complexity is measured in lines of system prompt content, ranging from 0
(empty) to 1787 (full CLAUDE.md from ProjectOdyssey[6]):

| Level | Lines | Description | Representative Test |
|-------|-------|-------------|---------------------|
| Empty | 0 | No system prompt | T0-00-empty |
| System | 0 | Only system prompt | T0-01-empty |
| Minimal | ~55 | Safety rules only | T0-06-B02 |
| Core | ~260 | Essential blocks (B02, B07, B18) | T0-03-core |
| Standard | ~400 | Seven core blocks | T0-02-standard |
| Full | 1787 | All 18 CLAUDE.md blocks | T0-03-full |

Each block (B01-B18) can be tested separately to see whether the part actually
contributes to the whole.

#### 4.2.3 Skill Complexity Axis

Skills are organized by domain. Here is what we are testing in T1:

| Category | Count | Example Domains | Token Efficiency |
|----------|-------|-----------------|------------------|
| Agent | 5 | Agent management patterns | High |
| CI/CD | 7 | Build and deployment automation | High |
| Documentation | 4 | Technical writing assistance | Medium |
| GitHub | 10 | Repository management | Medium |
| Language | 10 | Programming language specific | High |
| Quality | 5 | Code quality and review | Medium |
| Workflow | 5 | Development workflow patterns | High |

**Total**: 46 skills across 7 categories. Skills bake knowledge into prompts, so
you avoid loading massive tool schemas. But do these actually improve
performance? That is an open question.

#### 4.2.4 Agent Hierarchy Axis

Three ways to organize agents, tested across T3-T4:

| Pattern | Coordination | Communication Overhead | Use Cases |
|---------|--------------|------------------------|-----------|
| **Flat** | No supervision; peer-to-peer | Low | Simple, independent tasks |
| **Hierarchical** | L0-L4 levels with explicit supervision | High | Complex, interdependent tasks requiring planning |
| **Hybrid** | Selective hierarchy based on task complexity | Medium | Adaptive: flat for simple tasks, hierarchical for complex |

Hierarchy matters for costs because each supervision layer adds more
orchestration tokens and potentially more self-correction iterations.

---

## 5. Test Metrics

### 5.1 Performance Metrics

**Pass-Rate** is straightforward, did it work or not:

$$\text{Pass-Rate} = \frac{\text{correct\_solutions}}{\text{total\_attempts}}$$

Range is 0.0 (nothing worked) to 1.0 (everything worked). "Correct" means it
passes the test suite for that specific task. Report this with confidence
 intervals (95% CI if you have 30+ runs).

**Fine-Grained Progress Rate** ($R_{Prog}$) tracks how far you got through
 multi-step tasks:

$$R_{Prog} = \frac{\text{achieved\_progress\_steps}}{\text{expected\_progress\_steps}}$$

Range is 0.0 to 1.0. If you get 1.0, it means the agent took extra steps
that actually helped. This is super useful for debugging where things go wrong
in complex workflows, especially in hierarchical setups with all their
self-correction loops.

**Consistency** measures how stable the outputs are:

$$\text{Consistency} = 1 - \frac{\sigma(\text{outputs})}{\mu(\text{outputs})}$$

Range is 0.0 to 1.0, higher means more deterministic. Matters most for where
you are trying to get reliable structured outputs.

### 5.2 Quality Metrics

**Implementation Rate** (Impl-Rate) measures whether you actually satisfied the
requirements:

$$\text{Impl-Rate} = \frac{\text{satisfied\_requirements}}{\text{total\_requirements}}$$

Range is 0.0 to 1.0. This gives you more detail than just pass/fail, you get
partial credit for incomplete work. Checked using multiple LLM judges with
median scoring for consensus.

### 5.3 Efficiency and Cost Metrics

**Latency** is just time from start to finish (seconds):

- Time-to-First-Token (TTFT)
- Total response time
- Tool execution time

It matters a lot for architectures where verification loops can really slow
things down.

**Token Distribution** shows where your tokens are going:

$$\text{token\_dist} = \left\{ \frac{\text{input\_tokens}}{\text{total\_tokens}}, \frac{\text{output\_tokens}}{\text{total\_tokens}}, \frac{\text{tool\_input\_tokens}}{\text{total\_tokens}}, \frac{\text{tool\_output\_tokens}}{\text{total\_tokens}} \right\}$$

Useful for figuring out what is actually contributing to the cost(like T3's
massive agent prompts or T4's orchestration overhead).

**Cost-of-Pass (CoP)** is the primary metric, what is the expected cost to get
one correct solution:

$$\text{CoP} = \frac{\text{total\_cost}}{\text{pass\_rate}}$$

Units are USD. Lower is better. If pass_rate hits zero, CoP goes to infinity,
that configuration is economically dead. This combines both cost and accuracy
into one number that tells you if something is actually sustainable.

**Frontier CoP** represents the best CoP for all the various tests:

$$\text{Frontier\_CoP} = \min(\text{CoP}_{T0}, \text{CoP}_{T1}, \ldots, \text{CoP}_{T6})$$

This metric currently is just the minimum CoP across all tiers. Comparing this
against what it costs to hire a human expert will allow developers to see if
automation actually makes economic sense. Different model providers will have
different cost assumptions.

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
| Isolation | Each test runs in clean workspace |
| Compute | Standard CPU (no GPU required for evaluation) |

Each test runs in its own git clone with the repo at a specific git
commit. This means every run is reproducible and tests cannot mess with each
other. Every container starts fresh with:

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

1. **Workspace Prep**: Clone the repo, check out the specific commit, inject
   tier config
2. **Run the Agent**: Fire up Claude Code with whatever prompt/tools that tier
   uses
3. **Capture Everything**: Grab the output, command logs, file changes,
   artifacts
4. **Judge It**: Run three LLM judges in parallel (Opus, Sonnet, Haiku)
5. **Calculate Metrics**: Crunch the numbers for Pass-Rate, Impl-Rate, CoP,
   token usage, consensus scores

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

---

## 7. Test Cases

### 7.1 Pull Request (PR) Selection Criteria

Test cases come from real software development tasks. Here is what I consider to
make a good test:

1. **Reproducible**: Pin it to a specific git commit
2. **Clear success criteria**: Can be expressed in a rubric with measurable
   requirements
3. **Representative**: Real work that developers actually do
4. **Incrementally complex**: From trivial (Hello World) to multi-file
   architecture changes
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
- How many constraints you are working under

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

I have designed **47 planned test cases** covering different workflows and
complexity levels:

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

Tests get progressively harder. Performance should drop as complexity increases,
if it does not, the test is too easy even for the advanced models.

---

## 8. Model Summary

### 8.1 Claude Code Models

I am primarily testing Claude models through the Claude Code CLI:

**Opus 4.5** is expected to be accel in T4-T6 where you need deep reasoning and
self-correction.

**Sonnet 4.5** is expected to show benefits at T1-T3. Balanced cost/performance
at $3/$15 per million tokens.

**Haiku 4.5** is expected to be the choice for simple T0-T1 tasks where fancy
features do not help. At $1/$5 per million tokens, it is 15x cheaper than Opus
for inputs. It is not expected to work well with agents, tools, or skills.

### 8.2 Model-Agnostic Framework Design

The framework is designed to work with any CLI tool or model:

1. **Standardized Interfaces**: Everything goes through the CLI's language
   interface and filesystem outputs. Never touches model APIs directly. This
   means vendor-specific details do not matter.

2. **Consistent Metrics**: CoP, Pass-Rate, Impl-Rate work the same across all
   models. You can do apples-to-apples economic comparisons.

3. **Pluggable Judges**: Currently using Claude family for judging, but you can
   swap in any LLM.

4. **Same Tier Structure**: T0-T6 applies to all tools. Direct architectural
   comparisons across vendors.

5. **Reproducible Configs**: Everything is in version-controlled YAML, model IDs,
   temperature, token limits. Easy to reproduce across different tools.

This means you can benchmark OpenCode, Codex, Goose, or whatever new tool
comes out, and the comparisons stay valid.

---

## 9. Results

I will present results from the dryrun experiment (test-001, Hello World task)
across all seven tiers. The dryrun serves as a pipeline validation exercise with
N=1 run per tier, establishing that the framework executes end-to-end
successfully and generates the expected metrics, figures, and tables. Think of
this as a "smoke test", if the pipeline works on the simplest possible task, I
know it will handle the complex stuff later.

### 9.1 Pipeline Validation (Dryrun Overview)

First, the dry run was executed with the following setup:

- **Scope**: 1 model (Sonnet 4.5), 7 tiers (T0-T6), 1 subtest per tier
- **Judges**: 3 judges per run (Opus 4.5, Sonnet 4.5, Haiku 4.5) = 21 total
  judge evaluations
- **Criteria**: 5 criteria per judge × 21 judges = 105 total criteria scores
- **Total cost**: $1.01 (agent execution + judge evaluation)
- **Total duration**: ~1289 seconds (~21.5 minutes) sum of per-tier durations;
  actual wall-clock time was ~550 seconds due to parallel execution
- **Pass rate**: 100% (all 7 tiers passed, all grade A)

Table 1 shows the tier-by-tier summary. All tiers achieved grade A with median
consensus scores ranging from 0.943 (T6) to 0.983 (T2, T3, T5). The task is
trivially easy, as expected, even T0 (minimal prompt) scores 0.973.

**Table 1: Tier Summary (Dryrun)**

| Tier | Pass Rate | Mean Score | Median Score | Grade | CoP ($) |
|------|-----------|-----------------|--------------|-------|---------|
| T0   | 1.000     | 0.973           | 0.973        | A     | 0.14    |
| T1   | 1.000     | 0.970           | 0.970        | A     | 0.13    |
| T2   | 1.000     | 0.983           | 0.983        | A     | 0.14    |
| T3   | 1.000     | 0.983           | 0.983        | A     | 0.13    |
| T4   | 1.000     | 0.960           | 0.960        | A     | 0.17    |
| T5   | 1.000     | 0.983           | 0.983        | A     | 0.07    |
| T6   | 1.000     | 0.943           | 0.943        | A     | 0.25    |

**Key finding**: Quality converges across all tiers (ceiling effect), but cost
varies 3.8x from $0.065 to $0.247.

### 9.2 Cost-of-Pass Analysis

Since all tiers pass (pass_rate = 1.0), Cost-of-Pass equals the raw cost. Figure
6 (see `docs/paper-dryrun/figures/fig06_cop_by_tier.png`) visualizes CoP across
tiers.

**Frontier CoP**: $0.065 (achieved by T5 hybrid)

**Cost ranking** (lowest to highest):
1. **T5** (hybrid): $0.065 — Frontier CoP achieved through selective skill
   loading and minimal cache creation (4.6K vs 23-44K for other tiers)
2. **T1** (skills): $0.127 — Token-efficient skill-based approach
3. **T3** (delegation): $0.129 — Flat multi-agent with efficient orchestration
4. **T0** (baseline): $0.135 — Minimal prompt overhead
5. **T2** (tooling): $0.138 — Tool schema loading increases cache tokens
6. **T4** (hierarchy): $0.168 — Hierarchical orchestration adds 30% overhead vs
   T3
7. **T6** (super): $0.247 — Maximum configuration is 3.8x Frontier CoP;
   diminishing returns evident

T6 (everything enabled) costs the most despite scoring the lowest (0.943). This
is a kitchen sink approach, to see when more equals better.

### 9.3 Token Analysis

Token distribution reveals where costs originate. Figure 7 (see
`docs/paper-dryrun/figures/fig07_token_distribution.png`) shows the breakdown by
token type.

Cache read tokens dominate, 80-99% of total tokens across all tiers, confirming
prompt caching works. But cache creation tokens vary dramatically:

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

The Token Efficiency Chasm I mentioned in Section 4? The data is consistent with
this hypothesis. T6 requires 218K cache read tokens versus T0's 113K, a 1.94x
increase (nearly double). T5 achieves efficiency by minimizing cache creation
(4.6K vs 23-44K), supporting the hybrid strategy.

Output tokens stay stable at 558-725 across tiers, showing the task itself
requires similar generation regardless of architecture.

### 9.4 Latency Analysis

Latency breaks into two components: agent execution time and judge evaluation
time. Figure 13 (see `docs/paper-dryrun/figures/fig13_latency.png`) shows the
breakdown.

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

Judge evaluation dominates, 77-86% of total latency, ranging from 128-178
seconds. This makes sense since 3 judges each evaluate the output independently.

Agent time varies modestly, 25-41 seconds. T5 is fastest (24.8s), T4 slowest
(41.2s). T5's speed advantage aligns with its cost advantage, both stem from
minimal cache loading.

On this trivial task, judge overhead dwarfs agent execution time, since there
are three judges for this simple task. On more complex tasks with multi-step
reasoning, agent time would dominate.

### 9.5 Judge Agreement

Three judges (Opus 4.5, Sonnet 4.5, Haiku 4.5) evaluated each run. Figure 2
(see `docs/paper-dryrun/figures/fig02_judge_variance.png`) and Figure 14 (see
`docs/paper-dryrun/figures/fig14_judge_agreement.png`) show judge variance and
pairwise agreement.

**Judge behavior patterns**:
- **Opus**: Most conservative judge, scores range 0.93-0.96, never awards S
  grade
- **Sonnet**: Moderate judge, scores range 0.90-1.00, awards S grade in 4/7
  tiers (T2, T3, T4, T5)
- **Haiku**: Most generous judge, scores range 0.93-1.00, awards S grade in 5/
  7 tiers

**Pairwise agreement** (Table 3 from
 `docs/paper-dryrun/tables/tab03_judge_agreement.md`):
- **Opus-Sonnet**: Spearman ρ = 0.333, Pearson r = 0.706, mean Δ = 0.033
- **Opus-Haiku**: Spearman ρ = -0.273, Pearson r = -0.063, mean Δ = 0.045
- **Sonnet-Haiku**: Spearman ρ = -0.522, Pearson r = -0.347, mean Δ = 0.037

Krippendorff's α (interval): -0.117. Poor agreement, but expected with N=1 per
tier. **Note**: N=7 is insufficient for reliable correlation estimates; these
values are reported for completeness but should be interpreted with extreme
caution.

Despite low inter-rater agreement, the 3-judge median produces stable final
scores. The median dampens extreme scores, Haiku's 1.00 perfects versus Opus's
0.93 conservatism.

### 9.6 Criteria Breakdown

Judges score five weighted categories: functional correctness (35%),
code quality (20%), proportionality (15%), build pipeline (10%), overall quality
(20%). Figure 9 (see `docs/paper-dryrun/figures/fig09_criteria_by_tier.png`)
shows criteria performance by tier.

All tiers score 0.95-1.00 on functional criteria (file exists, correct output,
exit code 0). Near-perfect, confirming the task is trivially easy.

The largest score differences appear in subjective categories. Proportionality:
T6 scored lower because judges noted cache artifacts (.ruff_cache,
.pytest_cache) remaining in workspace. Overall quality: subjective engineering
judgment shows the most variance across judges.

Build pipeline: all tiers pass with scores 0.90-1.00, confirming clean
execution.

### 9.7 Statistical Limitations

N=1 prevents inferential statistics. With only one run per tier, I cannot compute
confidence intervals, standard deviations, or perform significance tests. All
results are purely descriptive. This is a limitation of this run and not the
framework itself.

The analysis pipeline correctly reports `nan` for standard deviation and sets
confidence intervals to (point, point). Statistical warnings appear in the
output: "Mann-Whitney U test called with sample sizes 1, 1. Need at least 2
samples per group." This was added so that it was clear to users that results
are not expected to be robust.

---

## 10. Discussion

The dry run is not very useful for serious analysis, but what I will dive into
what I learned about the framework's behavior on this trivially simple task,
while being honest about the limitations inherent in N=1 experiments and ceiling
effects.

### 10.1 What the Dryrun Tells Us

The Hello World task is, by design, trivially easy. All seven tiers score grade
A with median scores between 0.943-0.983. This validates exactly what I said in
Section 4: "Even T0 should nail this test." And it did.

**Ceiling effect dominates**: When quality converges at near-perfect levels, we
cannot differentiate tiers by capability. T0's empty prompt (subtest 00 uses no
system prompt at all) and T6's maximal configuration (61 skills + all tools + 44
agents) produce equivalent functional output. This is exactly what we expect for
Hello World, no amount of architectural sophistication helps when the task
requires a single `print()` statement.

**Cost differentiation still works**: Despite quality convergence, Cost-of-Pass
varies 3.8x from $0.065 (T5) to $0.247 (T6). This demonstrates the framework's
ability to measure economic trade-offs even when quality metrics saturate. On
more complex tasks with quality variance, both dimensions should differentiate.

**Pipeline validation successful**: The framework executed all seven tiers,
collected 21 judge evaluations, computed consensus scores, generated 25 figures
and 10 tables, and produced structured CSV exports. All components worked as
designed.

### 10.2 Cost-Performance Trade-offs

The dryrun reveals hints of a pattern: more is not always better.

T5 achieves Frontier CoP through selective feature loading, it combines T1's
efficient skills with T3's delegation patterns but avoids T6's "everything
enabled" overhead. T5's cache creation tokens (4,629) are 5-10x lower than other
tiers (23,106-44,337), directly explaining its cost advantage.

T6 costs the most ($0.247, or 3.8x Frontier CoP) despite scoring the lowest
(0.943). Loading 61 skills + all tools + 44 agents actually made things worse.
Judges explicitly noted cache artifacts and unnecessary complexity. This lines
up with the hypothesis that prompt complexity hurts quality when the task is in
the model's training set.

T4's hierarchical overhead is another example. T4 costs 30% more than T3
($0.168 vs $0.129) for this trivial task. The self-correction loops and nested
orchestration add latency (41.2s vs 29.9s) without improving quality. On complex
tasks needing iterative refinement, maybe T4 justifies the overhead. On simple
tasks, it is pure waste.

The Token Efficiency Chasm I talked about in Section 4? The data supports this
hypothesis. T6's 218K cache read tokens versus T0's 113K (1.94x increase) shows
the cost of loading tool schemas. T2 (tooling) shows similar bloat, 137K total
tokens versus T1's 115K. Skills-based approaches (T1, T3) stay lean while still
enabling domain knowledge.

Bottom line for production: match tier complexity to task complexity. Do not use
T6 for trivial tasks. Do not use T0 for tasks needing specialized tools or
multi-step reasoning. T5's hybrid approach seems to be optimal, load features
selectively based on what the task actually needs, do not just maximize
everything.

### 10.3 Judge Behavior

The 3-judge consensus mechanism reveals interesting patterns.

Haiku hands out S grades easily, 5 out of 7 tiers got perfect scores. Scores
range 0.93-1.00, and Haiku consistently scores higher than Opus or Sonnet.

Opus never awards S grades. Scores range 0.93-0.96, consistently the toughest
judge. Opus reliably deducts points for cache artifacts that Haiku overlooks.

Sonnet splits the difference. Awards S grades in 4/7 tiers (T2, T3, T4, T5),
scores range 0.90-1.00.

Given that the results in most cases are a single line, the 1.0 grade is
incorrect and points to agents being a little too lenient. Maybe some prompt
tweaks will fix this, but that also can be due to the simplicity of this task.
This can be investigated in future analysis.

Inter-rater agreement is predictably low: Krippendorff's α = -0.117. But that is
expected with N=1 and near-perfect scores. On tasks with more variance,
agreement should improve as judges separate clear failures from clear successes.

Despite the disagreement, the 3-judge median works. When Haiku awards 1.00 and
Opus awards 0.93, the median captures the true quality without getting pulled to
either extreme. This validates the multi-judge consensus design.

One scaling problem: judge time dominates total latency. 77-86% of execution
time is judge evaluation (128-178s), not agent execution (25-41s). With 3 judges
per run, judge costs are 3x per evaluation. For large-scale experiments (N=10 ×
113 subtests = 1,130 runs × 3 judges = 3,390 judge evaluations), judge cost uses
the budget fast. Future work should explore single-judge evaluation,
confidence-based selection (use Opus only when Sonnet/Haiku disagree), evaluate
if prompt improvements can get the cheaper Haiku model to be an effective judge,
or give different prompts to the same judge model.

### 10.4 Limitations

N=1 is descriptive only. I cannot compute standard deviations, confidence
intervals, or significance tests. All tier comparisons are point estimates. A
single outlier run could flip all the conclusions.

Single task, trivial complexity. Hello World does not need skills, tools,
multi-agent coordination, or hierarchical reasoning. The dryrun validates the
pipeline works, not whether architectural complexity improves quality on hard
tasks.

Single model. All agent runs use Sonnet 4.5. I have not tested whether tier
rankings hold for Opus 4.5, Haiku 4.5, or other model families.

No thinking mode variants. The dryrun uses standard inference without extended
thinking. Models with thinking enabled might show different cost-quality
trade-offs.

Ceiling effect masks capability differences. When all tiers score 0.94-0.98, I
cannot tell which architecture would excel on harder tasks. The full experiment
(113 subtests including complex multi-file repos) will differentiate
capabilities.

Judge evaluation time bottleneck. 3 sequential judges per run creates a 3x cost
multiplier. Parallel judge execution would reduce latency but not cost.

---

## 11. Conclusions

This paper introduced the Scylla framework, and shows that it works, end-to-end.
All seven tiers executed successfully, three judges scored everything, and the
analysis pipeline spit out figures and tables automatically. The dryrun
validates the methodology on the simplest possible task, Hello World, before I
scale up to complex multi-file repos. What is missing is review and feedback
from others, which is what this paper helps enable.

What did I learn? Five things stand out:

1. The framework is operational.
2. Quality converges on trivial tasks, making the framework overkill.
3. All tiers scored grade A, proving that throwing more complexity at Hello
   World doesn't help, which should be obvious. That obviousness is what makes
   it a good pipe cleaning run.
4. Cost still varies 3.8x despite identical quality, showing the framework can
   measure economic trade-offs even when quality saturates. T5's hybrid approach
   achieves Frontier CoP by selectively loading features instead of maximizing
   everything.
5. And the Token Efficiency Chasm I hypothesized in Section 4? That I can say is
   confirmed, as T6 burns nearly double the tokens (218K vs 113K) compared to
   T0.

Did I answer my original questions? Partially. CoP lets me quantify efficiency;
T5 is 3.8x cheaper than T6 despite equivalent quality. On this task, the sum is
*not* more than the parts; T6 scores lowest despite highest cost. But the hard
questions need harder tasks, I cannot tell if any tier dominates universally from
a single Hello World run, and I have not tested model-to-model comparisons yet.
That work is left for a future exercise.

What about my hypotheses? The KISS principle hypothesis has hints of being
confirmed, maximal complexity (T6) scores worst on this training-set-likely
task. But I have not tested inverse KISS on out-of-distribution tasks yet, and
specialization advantages (H1) are inconclusive because Hello World does not
require delegation or tools.

There is no real practical takeaway yet, since the testing was insufficient to
come to any real conclusions. Answering those questions is left for the next
exercise, and this framework can be used for doing so.

---

## 12. Further Work

The dryrun validates the framework works. Now it is time to scale up and fill in
the gaps.

**Full-scale experiments**: Run the complete test001 dataset with (N=10, 113
 subtests, 1,130 runs total). Running the analysis will start to enable valid
statistical inference about the relationship between prompts and the tools.

**Task diversity**: The dryrun only covers Hello World. The full test suite
includes 46 additional tasks across greenfield (Flask APIs, CLI tools),
brownfield (feature additions to existing repos), refactoring (extract function,
eliminate duplication), bug fixes (off-by-one errors, race conditions), and
documentation (README generation). Running these will show whether tier rankings
hold across workflow categories or if certain tiers excel at specific task
types.

**Cross-vendor and cross-model evaluation**: The framework is model-agnostic by
design. I would love to extend support to other tools, but right now just doing
analysis on Claude Code alone is hitting my budgets for experimentation
extremely quickly. Setting up local models and accessing tools using these
models will allow more experimentation, but I do not have access to that kind of
compute within my budget at the moment.

**Advanced analysis**: I am by no means a statistician, and choices I have made
here might be incorrect. My current analysis uses frequentist statistics. There
are more advanced analysis that I am learning about that could help analyze the
flood of data more efficiently. There is also other metrics and data points that
could be useful in this analysis that I am not collecting. I also can save the
runs and do longitudinal studies to see if the results change consistently over
time.

Given the scale and scope of this task, it is going to be an ongoing effort of
learning, testing, and analyzing.

---

## Acknowledgements

This work was self-funded by the author. Special thanks to Tuan Nguyen for
reviewing early drafts of this paper and providing valuable feedback.

---

## References

[1] @article{liu2023agentbench,
  title   = {AgentBench: Evaluating LLMs as Agents},
  author  = {Xiao Liu and Hao Yu and Hanchen Zhang and Yifan Xu and Xuanyu Lei and Hanyu Lai and Yu Gu and Hangliang Ding and Kaiwen Men and Kejuan Yang and Shudan Zhang and Xiang Deng and Aohan Zeng and Zhengxiao Du and Chenhui Zhang and Sheng Shen and Tianjun Zhang and Yu Su and Huan Sun and Minlie Huang and Yuxiao Dong and Jie Tang},
  year    = {2023},
  journal = {arXiv preprint arXiv: 2308.03688}
}

[2] @inproceedings{
    jimenez2024swebench,
    title={{SWE}-bench: Can Language Models Resolve Real-world Github Issues?},
    author={Carlos E Jimenez and John Yang and Alexander Wettig and Shunyu Yao and Kexin Pei and Ofir Press and Karthik R Narasimhan},
    booktitle={The Twelfth International Conference on Learning Representations},
    year={2024},
    url={https://openreview.net/forum?id=VTF8yNQM66}
}

[3] @misc{yao2024tau,
      title={$\tau$-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains},
      author={Shunyu Yao and Noah Shinn and Pedram Razavi and Karthik Narasimhan},
      year={2024},
      eprint={2406.12045},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2406.12045},
}

[4] @article{zhu2023promptbench2,
  title={PromptBench: A Unified Library for Evaluation of Large Language Models},
  author={Zhu, Kaijie and Zhao, Qinlin and Chen, Hao and Wang, Jindong and Xie, Xing},
  journal={arXiv preprint arXiv:2312.07910},
  year={2023}
}

[5] @article{polo2024efficient,
title={Efficient multi-prompt evaluation of LLMs},
author={Polo, Felipe Maia and Xu, Ronald and Weber, Lucas and Silva, M{\'\i}rian and Bhardwaj, Onkar and Choshen, Leshem and de Oliveira, Allysson Flavio Melo and Sun, Yuekai and Yurochkin, Mikhail},
journal={arXiv preprint arXiv:2405.17202},
year={2024}
}

[6] **ProjectOdyssey: Comprehensive Agent Orchestration Framework.**
    Homeric Intelligence. GitHub repository.
    https://github.com/HomericIntelligence/Projectodyssey
    Accessed on: 12/30/2025
    Github hash: 011a3ff024954c0e15d0220bd67d72d6f74ffb64

[7] Anthropic. (2024). **Claude Code: Agentic CLI Tool for Software Development.** Anthropic AI. https://www.anthropic.com/claude/code

[8] @misc{eval-harness,
  author       = {Gao, Leo and Tow, Jonathan and Abbasi, Baber and Biderman, Stella and Black, Sid and DiPofi, Anthony and Foster, Charles and Golding, Laurence and Hsu, Jeffrey and Le Noac'h, Alain and Li, Haonan and McDonell, Kyle and Muennighoff, Niklas and Ociepa, Chris and Phang, Jason and Reynolds, Laria and Schoelkopf, Hailey and Skowron, Aviya and Sutawika, Lintang and Tang, Eric and Thite, Anish and Wang, Ben and Wang, Kevin and Zou, Andy},
  title        = {The Language Model Evaluation Harness},
  month        = 07,
  year         = 2024,
  publisher    = {Zenodo},
  version      = {v0.4.3},
  doi          = {10.5281/zenodo.12608602},
  url          = {https://zenodo.org/records/12608602}
}

[9] **safety-net: Claude Code Plugin for Dangerous Operation Blocking.** CC-Marketplace. https://github.com/cc-marketplace/safety-net, https://github.com/kenryu42/claude-code-safety-net

[10] **CC-Marketplace: Community Marketplace for Claude Code Plugins and Skills.** https://github.com/cc-marketplace

---

## Appendices

### Appendix A: Detailed Metric Definitions

For comprehensive metric definitions including formulas, calculation methods, and interpretation guidelines, see:
- `<project_root>/.claude/shared/metrics-definitions.md`
- `<project_root>/docs/design/metrics-formulas.md`

Key metrics include Pass-Rate, Implementation Rate (Impl-Rate), Fine-Grained Progress Rate ($R_{Prog}$), Consistency, Cost-of-Pass (CoP), Frontier CoP, Token Distribution, and Latency.

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
- Python 3.12+

**Execution Steps**:

```bash
# 1. Clone repository
git clone https://github.com/HomericIntelligence/ProjectScylla
cd ProjectScylla

# 2. Install dependencies
pixi install

# 3. Run evaluation (example for test-001, tier T0)
pixi run python scripts/run_e2e_experiment.py \
  --test tests/001-hello-world \
  --tier T0 \
  --runs 10

# 4. Generate figures and tables
pixi run python scripts/generate_figures.py \
  --results <output_directory>
pixi run python scripts/generate_tables.py \
  --results <output_directory>
```

**Artifact Locations**:

By default, experiment outputs are written to a timestamped directory outside
the project root (e.g., `~/fullruns/<experiment-id>/<timestamp>/`). The output
directory structure contains:

- Tier results: `<output_dir>/<tier>/<subtest>/run_<N>/`
- Workspace snapshots: `<output_dir>/<tier>/<subtest>/run_<N>/workspace/`
- Agent logs: `<output_dir>/<tier>/<subtest>/run_<N>/agent/`
- Consensus results: `<output_dir>/result.json`
- Analysis outputs: Generated by `scripts/generate_figures.py` and
  `scripts/generate_tables.py` from the `result.json` file
