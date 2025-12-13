# Agent System Documentation

## Overview

This directory contains documentation, templates, and reference materials for the ProjectScylla
evaluation-focused agent hierarchy. The operational agent configurations are in `.claude/agents/`
following Claude Code conventions.

## Directory Purpose

### This Directory (`agents/`)

- **Purpose**: Team documentation and reference materials
- **Contents**: READMEs, diagrams, templates, examples
- **Usage**: Read by humans to understand and create agents
- **Version Control**: Committed to repository for team sharing

### Operational Directory (`.claude/agents/`)

- **Purpose**: Working sub-agent configuration files
- **Contents**: Agent .md files that Claude Code executes
- **Usage**: Read by Claude Code to invoke agents
- **Version Control**: Committed to repository for consistency

## Quick Start

### Understanding the System

1. **Read the Hierarchy**: Start with [hierarchy.md](hierarchy.md) to understand the 5 levels
1. **Learn Delegation**: Read [delegation-rules.md](delegation-rules.md) for coordination patterns
1. **Review Templates**: Check [templates/](templates/) for agent configuration examples

### Creating a New Agent

1. **Identify the Level**: Determine which level (0-4) this agent belongs to
1. **Choose a Template**: Use the appropriate template from `templates/`
1. **Fill in Details**: Customize for your specific agent's role
1. **Add to `.claude/agents/`**: Place the config file in `.claude/agents/`
1. **Test**: Verify Claude Code can load and invoke the agent

### Using Agents

Agents can be invoked in two ways:

**Automatic Invocation** (Recommended):

```text
User: "Design the evaluation protocol for tier comparison"
-> Claude recognizes task matches Evaluation Design Agent
-> Agent invokes automatically
```

**Explicit Invocation**:

```text
User: "Use the metrics specialist to calculate Cost-of-Pass"
-> Claude explicitly invokes Metrics Specialist
```

## Agent Hierarchy (5 Levels)

### Level 0: Chief Evaluator

- **Chief Evaluator Agent**: System-wide decisions, evaluation strategy, tier selection

### Level 1: Domain Orchestrators

- Evaluation, Benchmarking, Analysis, Infrastructure Orchestrators
- Manage major evaluation domains

### Level 2: Design Agents

- Experiment Design, Metrics Design, Protocol Design Agents
- Design evaluation methodology and protocols

### Level 3: Specialists

- Metrics, Benchmark, Statistical, Reporting Specialists
- Handle specific evaluation aspects and execution

### Level 4: Engineers

- Implementation, Test, Documentation Engineers
- Write code, tests, documentation

**See [hierarchy.md](hierarchy.md) for complete details**

## Evaluation Focus

Unlike traditional development agent hierarchies, ProjectScylla agents focus on:

### Core Competencies

1. **Experiment Design**: Creating fair, reproducible evaluations
2. **Metrics Collection**: Gathering quality, economic, and process metrics
3. **Statistical Analysis**: Rigorous hypothesis testing and confidence intervals
4. **Cost Optimization**: Identifying efficient architectural choices
5. **Tier Comparison**: Evaluating T0-T6 capability increments

### Testing Tier Expertise

Each agent understands the 7-tier incremental capability matrix:

| Tier | Agent Considerations |
|------|---------------------|
| T0 | Baseline establishment, zero-shot prompting |
| T1 | Prompt engineering evaluation |
| T2 | Skills effectiveness measurement |
| T3 | Tool use efficiency and accuracy |
| T4 | Multi-agent coordination overhead |
| T5 | Hierarchical supervision cost-benefit |
| T6 | Hybrid architecture optimization |

## Delegation Patterns

### Decomposition Delegation

Higher levels break evaluation tasks into smaller pieces:

```text
Chief Evaluator -> Domain Orchestrator -> Design Agent -> Specialist -> Engineer
```

### Specialization Delegation

Orchestrators delegate to specialists based on expertise:

```text
Evaluation Orchestrator
  +-> Experiment Design (for methodology)
  +-> Metrics Design (for measurement)
  +-> Protocol Design (for procedures)
```

### Parallel Delegation

Independent evaluation tasks run simultaneously:

```text
Benchmarking Orchestrator
  +-> Tier-0 Evaluator (parallel)
  +-> Tier-1 Evaluator (parallel)
  +-> Tier-2 Evaluator (parallel)
```

**See [delegation-rules.md](delegation-rules.md) for complete patterns**

## Workflow Integration

### 4-Phase Workflow

**Phase 1: Plan** (Sequential)

- Levels 0-2: Design evaluation methodology

**Phases 2-3: Test/Implementation** (Parallel)

- Levels 3-4: Execute evaluations and collect metrics

**Phase 4: Review** (Sequential)

- All levels: Analyze results and document findings

## Configuration Format

Agents follow Claude Code format with YAML frontmatter:

```yaml
---
name: agent-name
description: Brief description of when to use this agent
tools: Read,Write,Edit,Bash,Grep,Glob
model: sonnet
---

# Agent Name

## Role

[Agent's role in the hierarchy]

## Responsibilities

- Responsibility 1
- Responsibility 2

## Instructions

[Detailed instructions]

## Examples

[Example tasks]

## Constraints

[What NOT to do]
```

**See [templates/](templates/) for complete examples**

## Available Templates

- [level-0-chief-evaluator.md](templates/level-0-chief-evaluator.md) - Chief Evaluator template
- [level-1-orchestrator.md](templates/level-1-orchestrator.md) - Domain Orchestrator template
- [level-2-design-agent.md](templates/level-2-design-agent.md) - Design Agent template
- [level-3-specialist.md](templates/level-3-specialist.md) - Specialist template
- [level-4-engineer.md](templates/level-4-engineer.md) - Engineer template

## Operational Agents

The operational agent configurations are in `.claude/agents/`:

### Level 0: Chief Evaluator (1 agent)

- `chief-evaluator.md` - Strategic evaluation decisions, tier selection, methodology oversight

### Level 1: Domain Orchestrators (4 agents)

- `evaluation-orchestrator.md` - Coordinates evaluation experiments
- `benchmarking-orchestrator.md` - Manages benchmark execution
- `analysis-orchestrator.md` - Oversees statistical analysis
- `infrastructure-orchestrator.md` - Manages evaluation infrastructure

### Level 2: Design Agents (3 agents)

- `experiment-design.md` - Experiment methodology design
- `metrics-design.md` - Metrics definition and collection design
- `protocol-design.md` - Evaluation protocol design

### Level 3: Specialists (6 agents)

- `metrics-specialist.md` - Metrics calculation and collection
- `benchmark-specialist.md` - Benchmark execution and monitoring
- `statistical-specialist.md` - Statistical analysis and hypothesis testing
- `cost-specialist.md` - Cost analysis and optimization
- `reporting-specialist.md` - Report generation and visualization
- `reproducibility-specialist.md` - Experiment reproducibility validation

### Level 4: Engineers (3 agents)

- `implementation-engineer.md` - Evaluation code implementation
- `test-engineer.md` - Test harness development
- `documentation-engineer.md` - Documentation and reports

## Best Practices

### Creating Agents

1. **Single Responsibility**: Each agent has one clear evaluation role
1. **Clear Description**: Description should trigger appropriate auto-invocation
1. **Tool Minimalism**: Only request tools actually needed
1. **Rich Examples**: Show realistic evaluation scenarios
1. **Clear Constraints**: Document what agent should NOT do

### Using Agents

1. **Trust the Hierarchy**: Let orchestrators delegate, don't micromanage
1. **Document Results**: All findings must be captured
1. **Statistical Rigor**: Apply appropriate statistical tests
1. **Cost Awareness**: Track evaluation costs alongside results
1. **Reproducibility**: Ensure experiments can be replicated

## Common Patterns

### Pattern: Evaluating a New Tier

1. **Chief Evaluator** defines evaluation scope
1. **Evaluation Orchestrator** coordinates the evaluation
1. **Experiment Design Agent** creates the protocol
1. **Benchmark Specialist** executes benchmarks
1. **Statistical Specialist** analyzes results
1. **Reporting Specialist** generates findings report

### Pattern: Cost Optimization Study

1. **Chief Evaluator** identifies optimization target
1. **Analysis Orchestrator** coordinates analysis
1. **Cost Specialist** analyzes cost breakdown
1. **Metrics Specialist** collects efficiency metrics
1. **Reporting Specialist** documents recommendations

### Pattern: Adding New Metric

1. **Metrics Design Agent** defines metric specification
1. **Implementation Engineer** implements calculation
1. **Test Engineer** validates accuracy
1. **Documentation Engineer** documents usage

## Troubleshooting

### Agent Not Invoked Automatically

**Problem**: Claude doesn't automatically invoke your agent

**Solutions**:

1. Check description - make it specific and clear
2. Add trigger keywords user would naturally say
3. Test with explicit invocation first
4. Review Claude Code sub-agents documentation

### Evaluation Scope Unclear

**Problem**: Unclear which level agent belongs to

**Solutions**:

1. Review [hierarchy.md](hierarchy.md) for level definitions
2. Consider decision scope: Strategy -> Domain -> Design -> Execution -> Implementation
3. Ask: What does this agent decide vs execute?

## Documentation

### In agents/ (This Directory)

- **README.md** (this file) - Overview and quick start
- **hierarchy.md** - Visual hierarchy diagram and quick reference
- **delegation-rules.md** - Coordination and delegation patterns
- **templates/** - Agent configuration templates

### In .claude/

- **agents/** - Operational agent configurations
- **shared/** - Shared reference files

### In GitHub Issues

Issue-specific documentation is posted directly to GitHub issues as comments.

## References

- [Claude Code Sub-Agents Documentation](https://code.claude.com/docs/en/sub-agents)
- [Project Research Methodology](../docs/research.md)
- [CLAUDE.md](../CLAUDE.md) - Development guidance

## Contributing

### Adding a New Agent Type

1. Determine appropriate level (0-4)
1. Create configuration from template
1. Test with example tasks
1. Document in this README
1. Submit PR for team review

### Improving Documentation

1. Identify gaps or unclear areas
1. Update relevant documentation
1. Add examples if helpful
1. Submit PR for review
