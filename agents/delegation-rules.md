# Delegation Rules - Quick Reference

## Core Delegation Rules

### Rule 1: Scope Reduction

Each delegation reduces scope by one level:

```text
Strategy -> Domain -> Design -> Execution -> Implementation
```

### Rule 2: Specification Detail

Each level adds more detail:

```text
Evaluation goals -> Domain plans -> Methodology specs -> Execution details -> Code
```

### Rule 3: Autonomy Increase

Lower levels have more implementation freedom, less strategic freedom

### Rule 4: Review Responsibility

Each level reviews the work of the level below

### Rule 5: Escalation Path

Issues escalate one level up until resolved

### Rule 6: Horizontal Coordination

Same-level agents coordinate when sharing resources or dependencies

## When to Delegate

### Delegate Down When

- Task is too detailed for current level
- Specific expertise required
- Work can be parallelized
- Clear specification can be provided

### Escalate Up When

- Decision exceeds your authority
- Resources needed from higher level
- Blocker cannot be resolved at current level
- Conflicts with other same-level agents

### Coordinate Horizontally When

- Sharing evaluation resources
- Dependencies between experiments
- Interface negotiation needed
- Cross-cutting concerns (cost, reproducibility)

## Delegation Patterns

### Pattern 1: Sequential Delegation

```text
Orchestrator
  | completes planning
  | delegates to Design Agent
Design Agent
  | completes design
  | delegates to Specialist
Specialist
```

**Use When**: Tasks have strict dependencies (design before execution)

### Pattern 2: Parallel Delegation

```text
Benchmarking Orchestrator
  +-> Tier-0 Benchmark (parallel)
  +-> Tier-1 Benchmark (parallel)
  +-> Tier-2 Benchmark (parallel)
```

**Use When**: Tier evaluations are independent

### Pattern 3: Fan-Out/Fan-In

```text
Evaluation Orchestrator
  +-> Metrics Specialist --+
  +-> Benchmark Specialist-+-> Statistical Specialist
  +-> Cost Specialist -----+
```

**Use When**: Multiple data sources need aggregation

## Evaluation-Specific Delegation

### Experiment Design Decisions

**Level 0-1 Decides**:

- Which tiers to compare
- Sample sizes and statistical power
- Overall evaluation timeline

**Level 2 Implements**:

- Experiment methodology
- Metrics selection
- Protocol details

**Level 3-4 Executes**:

- Benchmark runs
- Data collection
- Result analysis

### Cost Analysis Delegation

**Level 2** (Design):

- Defines cost categories
- Specifies attribution methodology
- Plans cost-per-component breakdown

**Level 3** (Specialist):

- Implements cost tracking
- Calculates Cost-of-Pass
- Identifies optimization opportunities

**Level 4** (Engineer):

- Writes cost collection code
- Integrates with API billing
- Creates cost reports

## Status Reporting

### Report Frequency

- **Per Experiment**: For evaluation runs
- **Per Analysis**: For statistical results
- **On Completion**: Always
- **On Blocker**: Immediately

### Report Template

```markdown
## Evaluation Status Report

**Agent**: Micah Villmow <research@villmow.us>
**Level**: [0-4]
**Date**: [YYYY-MM-DD]
**Experiment**: [Experiment ID]

### Progress: [%]

### Completed

- [Item 1]

### In Progress

- [Item 1]

### Blockers

- [None / Description]

### Key Findings

- [Finding 1]

### Next Steps

- [Step 1]
```

## Handoff Protocol

### When Completing Work

1. **Document What Was Done**
1. **List Artifacts Produced** (data, reports, code)
1. **Specify Next Steps** for receiving agent
1. **Note Any Gotchas** or important context
1. **Request Confirmation** from receiving agent

### Handoff Template

```markdown
## Task Handoff

**From**: Micah Villmow
**To**: [Next Agent Name]
**Task**: [Description]

**Completed**:

- [What you did]

**Artifacts**:

- `path/to/data.json` - [description]
- `path/to/report.md` - [description]

**Next Steps**:

- [What next agent should do]

**Notes**:

- [Important context]
```

## Escalation Protocol

### Blocker Escalation

```text
1. Identify blocker
2. Document:
   - What's blocking you
   - What you've tried
   - Impact on evaluation
3. Escalate to immediate superior
4. Superior resolves or escalates further
```

### Conflict Escalation

```text
1. Agents attempt to resolve
2. If unresolved, both escalate to common superior
3. Superior reviews, decides, provides rationale
4. Both agents implement decision
```

## Decision Authority

| Level | Can Decide | Must Escalate |
|-------|-----------|---------------|
| 0 | Evaluation strategy, tier selection | Business priorities |
| 1 | Domain organization, resource allocation | Cross-domain strategy |
| 2 | Methodology design, metrics selection | Strategic changes |
| 3 | Execution approach, analysis methods | Methodology changes |
| 4 | Implementation details, code structure | Design decisions |

## Quick Decision Tree

```text
Can I decide this myself?
  +-- YES -> Decide, document, proceed
  +-- NO -> Can my superior decide?
         +-- YES -> Escalate one level
         +-- NO -> Escalate higher

Do I need input from peers?
  +-- YES -> Coordinate horizontally first
  +-- NO -> Proceed independently

Is this blocked?
  +-- YES -> Can I resolve?
  |       +-- YES -> Resolve and document
  |       +-- NO -> Escalate
  +-- NO -> Proceed

Should I delegate this?
  +-- Too detailed for my level? -> Delegate down
  +-- Requires specific expertise? -> Delegate to specialist
  +-- Can run in parallel? -> Delegate to multiple agents
  +-- Within my scope? -> Handle myself
```

## Anti-Patterns

### Don't Do This

**Skipping Levels**:

- WRONG: Engineer -> Chief Evaluator
- RIGHT: Engineer -> Specialist -> Design Agent -> Orchestrator -> Chief

**Micro-Managing**:

- WRONG: Orchestrator specifying code implementation details
- RIGHT: Orchestrator specifying requirements and success criteria

**Working in Silos**:

- WRONG: No communication, surprise conflicts
- RIGHT: Regular status updates, coordinate on shared resources

**Hoarding Decisions**:

- WRONG: Make all evaluation decisions yourself
- RIGHT: Delegate appropriately, trust hierarchy

## See Also

- [hierarchy.md](hierarchy.md) - Visual hierarchy and levels
- [README.md](README.md) - Overview and quick start
- [/CLAUDE.md](../CLAUDE.md) - Development guidance
