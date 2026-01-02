# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProjectScylla is an AI agent testing and optimization framework designed to measure, evaluate, and improve
the performance and cost-efficiency of agentic AI workflows. Named after the mythic trial from Homer's Odyssey,
Scylla represents the challenge of navigating trade-offs between capability gains and operational costs.

**Current Status**: Research and planning phase - establishing benchmarking methodology, metrics definitions,
and evaluation protocols before implementation begins.

**Ecosystem Context**: Part of a three-project ecosystem:

- **ProjectOdyssey** - Training and capability development for agents
- **ProjectKeystone** - Communication and distributed agent coordination
- **ProjectScylla** - Testing, measurement, and optimization under constraints (this project)

## Critical Rules - Read First

### Never Push Directly to Main

**The `main` branch is protected. ALL changes MUST go through a pull request.**

**ABSOLUTELY PROHIBITED:**

```bash
git checkout main
git add <files>
git commit -m "changes"
git push origin main  # BLOCKED - Will be rejected by GitHub
```

**Why this is prohibited:**

- Bypasses code review and CI checks
- Can break production immediately
- Violates GitHub branch protection rules
- Makes it impossible to track changes properly

**CORRECT WORKFLOW (Always Use PRs):**

```bash
# 1. Create feature branch
git checkout -b <issue-number>-description

# 2. Make changes and commit
git add <files>
git commit -m "type(scope): description"

# 3. Push feature branch
git push -u origin <issue-number>-description

# 4. Create pull request
gh pr create \
  --title "Brief description" \
  --body "Closes #<issue-number>" \
  --label "appropriate-label"

# 5. Enable auto-merge
gh pr merge --auto --rebase
```

**Emergency Situations:**

- Even for critical CI fixes, CREATE A PR
- Even for one-line changes, CREATE A PR
- Even if you're fixing your own mistake, CREATE A PR
- NO EXCEPTIONS - Always use the PR workflow

**See Also:**

- PR Best Practices: [PR Workflow](/.claude/shared/pr-workflow.md)

## Quick Links

### Core Guidelines

- [Mojo Syntax & Patterns](/.claude/shared/mojo-guidelines.md)
- [Mojo Anti-Patterns](/.claude/shared/mojo-anti-patterns.md) - Common failure patterns
- [PR Workflow](/.claude/shared/pr-workflow.md)
- [GitHub Issue Workflow](/.claude/shared/github-issue-workflow.md)
- [Common Constraints](/.claude/shared/common-constraints.md)
- [Error Handling](/.claude/shared/error-handling.md)
- [Evaluation Guidelines](/.claude/shared/evaluation-guidelines.md)
- [Metrics Definitions](/.claude/shared/metrics-definitions.md)

### Agent System

- [Agent Hierarchy](/agents/hierarchy.md) - 5-level hierarchy
- [Agent Configurations](/.claude/agents/) - Evaluation-focused agents
- [Delegation Rules](/agents/delegation-rules.md)

## Working with Agents

This project uses a hierarchical agent system for all development work. **Always use agents** as the primary
method for completing tasks.

### Agent Hierarchy

See [agents/hierarchy.md](agents/hierarchy.md) for the complete agent hierarchy including:

- 5-level hierarchy (L0 Chief Evaluator → L4 Junior Engineers)
- Model assignments (Opus, Sonnet, Haiku)
- Specialized evaluation and benchmarking agents

### Key Agent Principles

1. **Always start with orchestrators** for new evaluation work
1. **All outputs** must be posted as comments on the GitHub issue
1. **Link all PRs** to issues using `gh pr create --issue <number>` or "Closes #123" in description
1. **Minimal changes only** - smallest change that solves the problem
1. **No scope creep** - focus only on issue requirements
1. **Reply to each review comment** with `Fixed - [brief description]`
1. **Delegate to skills** - Use "Use the X skill to..." pattern for automation

### Key Development Principles

1. KISS - *K*eep *I*t *S*imple *S*tupid -> Don't add complexity when a simpler solution works
1. YAGNI - *Y*ou *A*in't *G*onna *N*eed *I*t -> Don't add things until they are required
1. TDD - *T*est *D*riven *D*evelopment -> Write tests to drive the implementation
1. DRY - *D*on't *R*epeat *Y*ourself -> Don't duplicate functionality, data structures, or algorithms
1. SOLID - *S**O**L**I**D* ->
   . Single Responsibility
   . Open-Closed
   . Liskov Substitution
   . Interface Segregation
   . Dependency Inversion
1. Modularity - Develop independent modules through well defined interfaces
1. POLA - *P*rinciple *O*f *L*east *A*stonishment - Create intuitive and predictable interfaces

### Documentation Rules

- **Issue-specific outputs**: Post as comments on the GitHub issue using `gh issue comment <number>`
- **Developer documentation**: `/docs/dev/` (architectural decisions, design docs)
- **Team guides**: `/agents/` (quick start, hierarchy, templates)
- **Never duplicate** documentation across locations - link instead
- See `.claude/shared/github-issue-workflow.md` for GitHub issue read/write patterns

## Testing Tiers (Ablation Study Framework)

ProjectScylla benchmarks AI agent architectures across 7 testing tiers with ~114+ sub-tests:

| Tier | Name | Sub-tests | Description |
|------|------|-----------|-------------|
| T0 | Prompts | 24 | System prompt ablation (empty → full CLAUDE.md) |
| T1 | Skills | 10 | Domain expertise via installed skills by category |
| T2 | Tooling | 15 | External tools and MCP servers |
| T3 | Delegation | 41 | Flat multi-agent with specialist agents |
| T4 | Hierarchy | 7 | Nested orchestration with orchestrator agents |
| T5 | Hybrid | 15 | Best combinations and permutations |
| T6 | Super | 1 | Everything enabled at maximum capability |

### Evaluation Protocol

Each tier is evaluated against:

1. **Quality Metrics**: Pass-Rate, Implementation Rate, Fine-Grained Progress Rate
2. **Economic Metrics**: Cost-of-Pass (CoP), token distribution, component-level costs
3. **Process Metrics**: Latency, consistency, strategic drift

## Core Metrics

### Quality Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| Pass-Rate | `correct_solutions / total_attempts` | Functional test coverage |
| Impl-Rate | `satisfied_requirements / total_requirements` | Semantic requirement satisfaction |
| R_Prog | `progress_steps / expected_steps` | Fine-grained advancement tracking |
| Consistency | `std(outputs) / mean(outputs)` | Output stability across runs |

### Economic Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| Cost-of-Pass (CoP) | `total_cost / pass_rate` | Expected cost per correct solution |
| Frontier CoP | `min(CoP_tier0, ..., CoP_tier6)` | Minimum cost across all tiers |
| Token Distribution | `tokens_by_component / total_tokens` | Component-level cost breakdown |
| CFP | `failed_changes / total_changes` | Change Fail Percentage |

### Process Metrics

| Metric | Description |
|--------|-------------|
| Latency | Time from query to resolution |
| Strategic Drift | Goal coherence over multi-step tasks |
| Ablation Score | Isolated component contribution |

## Language Preference

### Mojo First - For All Implementation

**Default to Mojo** for ALL evaluation and benchmarking implementations:

- Evaluation harnesses and benchmark runners
- Metrics calculation and collection
- Statistical analysis and data processing
- Performance-critical tensor operations
- Type-safe metric components
- SIMD-optimized calculations

**Use Python for Automation** when technical limitations require it:

- Subprocess output capture (Mojo limitation - cannot capture stdout/stderr)
- Regex-heavy text processing (no Mojo regex support in stdlib)
- GitHub API interaction via Python libraries (`gh` CLI, REST API)
- **MUST document justification** when using Python

**Rule of Thumb** (Decision Tree):

1. **Evaluation/benchmarking implementation?** -> Mojo (required)
1. **Automation needing subprocess output?** -> Python (allowed, document why)
1. **Automation needing regex?** -> Python (allowed, document why)
1. **Interface with Python-only libraries?** -> Python (allowed, document why)
1. **Everything else?** -> Mojo (default)

### Why Mojo for Evaluation

- **Performance**: Faster for numerical computations and metrics
- **Type safety**: Catch errors at compile time
- **Memory safety**: Built-in ownership and borrow checking
- **SIMD optimization**: Parallel operations for large datasets
- **Consistency**: Same language as ProjectOdyssey ecosystem

### Configuration Files

- YAML for experiment configurations
- JSON for API schemas and tool definitions
- Markdown for documentation and reports

## Mojo Development Guidelines

**Current Version**: Mojo 0.26.1

**Quick Reference**: See [mojo-guidelines.md](/.claude/shared/mojo-guidelines.md) for v0.26.1 syntax

**Critical Patterns**:

- **Constructors**: Use `out self` (not `mut self`)
- **Mutating methods**: Use `mut self`
- **Ownership transfer**: Use `^` operator for List/Dict/String
- **List initialization**: Use literals `[1, 2, 3]` not `List[Int](1, 2, 3)`

**Common Mistakes**: See [mojo-anti-patterns.md](/.claude/shared/mojo-anti-patterns.md) for failure patterns

**Compiler as Truth**: When uncertain, test with `mojo build` - the compiler is authoritative

## Claude 4 & Claude Code Optimization

### Extended Thinking

**When to Use Extended Thinking**: Use for complex reasoning tasks:

- Designing evaluation protocols and experiment methodology
- Analyzing benchmark results and identifying patterns
- Planning multi-tier comparison studies
- Debugging complex evaluation failures
- Statistical analysis and interpretation

**When NOT to Use Extended Thinking**:

- Simple metric calculations
- Boilerplate test generation
- Straightforward data collection
- Well-defined configuration tasks

### Thinking Budget Guidelines

| Task Type | Budget | Examples | Rationale |
|-----------|--------|----------|-----------|
| **Simple** | None | Update config | Mechanical changes |
| **Standard** | 5K-10K | Add test case | Well-defined |
| **Complex** | 10K-20K | Design experiment | Dependencies |
| **Analysis** | 20K-50K | Interpret results | Deep analysis |
| **Research** | 50K+ | New methodology | Novel design |

### Agent Skills vs Sub-Agents

**Decision Tree**: Choose between skills and sub-agents based on task characteristics:

```text
Is the task well-defined with predictable steps?
+-- YES -> Use an Agent Skill
|   +-- Is it a GitHub operation? -> Use gh-* skills
|   +-- Is it data collection? -> Use metrics-* skills
|   +-- Is it a CI/CD task? -> Use ci-* skills
|   +-- Is it report generation? -> Use report-* skills
|
+-- NO -> Use a Sub-Agent
    +-- Does it require exploration/discovery? -> Use sub-agent
    +-- Does it need adaptive decision-making? -> Use sub-agent
    +-- Is the workflow dynamic/context-dependent? -> Use sub-agent
    +-- Does it need extended thinking? -> Use sub-agent
```

### Output Style Guidelines

#### Code References

**DO**: Use absolute file paths with line numbers when referencing code:

```markdown
GOOD: Updated /home/user/ProjectScylla/src/metrics/cop.py:45-52

BAD: Updated cop.py (ambiguous - which file?)
```

#### Benchmark Results

**DO**: Use structured tables for benchmark results:

```markdown
## Benchmark Results: Task-X

| Tier | Pass-Rate | CoP ($) | Latency (s) |
|------|-----------|---------|-------------|
| T0   | 0.23      | 4.35    | 12.3        |
| T1   | 0.45      | 2.22    | 15.7        |
| T2   | 0.67      | 1.49    | 18.2        |
```

## Delegation to Agent Hub

.claude/ is the centralized location for agent configurations and skills. Sub-agents reference
`.claude/agents/*.md` for roles and capabilities.

### Shared Reference Files

All agents reference these shared files to avoid duplication:

| File | Purpose |
|------|---------|
| `.claude/shared/common-constraints.md` | Minimal changes principle, scope discipline |
| `.claude/shared/pr-workflow.md` | PR creation, verification, review responses |
| `.claude/shared/github-issue-workflow.md` | Issue read/write patterns |
| `.claude/shared/error-handling.md` | Retry strategy, timeout handling, escalation |
| `.claude/shared/evaluation-guidelines.md` | Evaluation methodology and best practices |
| `.claude/shared/metrics-definitions.md` | Complete metrics definitions and formulas |
| `.claude/shared/mojo-guidelines.md` | Mojo v0.26.1 syntax, parameter conventions |
| `.claude/shared/mojo-anti-patterns.md` | Common Mojo failure patterns |

## Environment Setup

This project uses Pixi for environment management with Mojo 0.26.1:

```bash
# Pixi is already configured - dependencies are in pixi.toml
# Mojo is the primary language for all implementations

# Run Mojo tests
pixi run mojo test tests/

# Build Mojo package
pixi run mojo build src/

# Format Mojo code
pixi run mojo format src/

# Run pre-commit hooks
pre-commit run --all-files
```

## Common Commands

### Development Workflows

**Pull Requests**: See [pr-workflow.md](/.claude/shared/pr-workflow.md)

- Creating PRs with `gh pr create --body "Closes #<number>"`
- Responding to review comments
- Post-merge cleanup

**GitHub Issues**: See [github-issue-workflow.md](/.claude/shared/github-issue-workflow.md)

- Read context: `gh issue view <number> --comments`
- Post updates: `gh issue comment <number> --body "..."`

**Git Workflow**: Feature branch -> PR -> Auto-merge (never push to main)

### Pre-commit Hooks

Pre-commit hooks automatically check code quality before commits.

```bash
# Install pre-commit hooks (one-time setup)
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files

# NEVER skip hooks with --no-verify
# If a hook fails, fix the code instead
```

**--no-verify is ABSOLUTELY PROHIBITED**. No exceptions.

## Repository Architecture

### Project Structure

```text
ProjectScylla/
+-- agents/                      # Team documentation
|   +-- README.md                # Quick start guide
|   +-- hierarchy.md             # Visual hierarchy diagram
|   +-- delegation-rules.md      # Coordination patterns
|   +-- templates/               # Agent configuration templates
+-- docs/
|   +-- research.md              # Research methodology
|   +-- dev/                     # Developer documentation
+-- src/                         # Mojo source code
|   +-- metrics/                 # Metrics calculation (.mojo)
|   +-- evaluation/              # Evaluation harnesses (.mojo)
|   +-- benchmarks/              # Benchmark definitions (.mojo)
|   +-- analysis/                # Statistical analysis (.mojo)
+-- tests/                       # Mojo test suite
+-- experiments/                 # Experiment configurations (YAML)
+-- results/                     # Benchmark results (JSON)
+-- scripts/                     # Python automation scripts
+-- .claude/                     # Operational configurations
|   +-- agents/                  # Agent configs
|   +-- shared/                  # Shared reference files
+-- pixi.toml                    # Pixi configuration
+-- CLAUDE.md                    # This file
+-- README.md                    # Project overview
```

### 4-Phase Development Workflow

Every component follows a hierarchical workflow with clear dependencies:

**Workflow**: Plan -> [Test | Implementation] -> Review

1. **Plan** - Design evaluation methodology and experiment protocols (MUST complete first)
1. **Test** - Write test harnesses and validation (parallel after Plan)
1. **Implementation** - Build evaluation infrastructure (parallel after Plan)
1. **Review** - Validate results and document findings (runs after parallel phases complete)

## GitHub Issue Structure

All planning is done through GitHub issues with clear structure:

### Issue Body Format

```markdown
## Objective
Brief description (2-3 sentences)

## Deliverables
- [ ] Deliverable 1
- [ ] Deliverable 2

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Dependencies
- Depends on #<parent-issue>
- Related: #<sibling-issue>

## Notes
Additional context
```

### Issue Labels

- `research` - Research and methodology
- `evaluation` - Evaluation infrastructure
- `metrics` - Metrics implementation
- `benchmark` - Benchmark definitions
- `analysis` - Statistical analysis
- `documentation` - Documentation work

## Git Workflow

### Branch Naming

- `main` - Production branch (protected, requires PR)
- `<issue-number>-<description>` - Feature/fix branches (e.g., `42-add-cop-metric`)

### Development Workflow

**IMPORTANT:** The `main` branch is protected. All changes must go through a pull request.

1. **Create a feature branch:**

   ```bash
   git checkout -b <issue-number>-<description>
   ```

1. **Make your changes and commit:**

   ```bash
   git add <files>
   git commit -m "type(scope): Brief description"
   ```

1. **Push the feature branch:**

   ```bash
   git push -u origin <branch-name>
   ```

1. **Create pull request:**

   ```bash
   gh pr create \
     --title "[Type] Brief description" \
     --body "Closes #<issue-number>"
   ```

1. **Enable auto-merge:**

   ```bash
   gh pr merge --auto --rebase
   ```

   **Always enable auto-merge** so PRs merge automatically once CI passes.

## Commit Message Format

Follow conventional commits:

```text
feat(metrics): Add Cost-of-Pass calculation
fix(evaluation): Correct token counting logic
docs(readme): Update benchmark instructions
refactor(analysis): Standardize statistical tests
```

## Troubleshooting

### GitHub CLI Issues

```bash
# Check authentication
gh auth status

# If missing scopes, refresh authentication
gh auth refresh -h github.com
```

### Mojo Compilation Errors

- Check Mojo version: `mojo --version` (requires 0.26.1+)
- Review [mojo-anti-patterns.md](/.claude/shared/mojo-anti-patterns.md) for common issues
- Test with `mojo build` - compiler is authoritative
- Check ownership patterns (common source of errors)

### Script Errors (Python Automation)

- Verify Python version: `python3 --version` (requires 3.10+)
- Check file permissions
- Review error logs

## Important Files

- `docs/research.md` - Research methodology and evaluation framework
- `README.md` - Main project documentation
- `.claude/shared/github-issue-workflow.md` - GitHub issue read/write patterns
