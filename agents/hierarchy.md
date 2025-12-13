# Agent Hierarchy - Visual Diagram and Quick Reference

## Hierarchy Diagram

```text
+-------------------------------------------------------------+
|                    Level 0: Chief Evaluator                  |
|                   Chief Evaluator Agent                      |
|         (Strategic decisions, tier selection, methodology)   |
+-----------------------------+-------------------------------+
                              |
        +---------------------+---------------------+
        v                     v                     v
+------------------+  +------------------+  +------------------+
|   Level 1:       |  |   Level 1:       |  |   Level 1:       |
|   Evaluation     |  |  Benchmarking    |  |    Analysis      |
|  Orchestrator    |  |  Orchestrator    |  |  Orchestrator    |
+--------+---------+  +--------+---------+  +--------+---------+
         |                     |                      |
         +---------------------+----------------------+
                               |
+-----------------------------+|+------------------------------+
|  Level 1: Infrastructure    ||                               |
|  Orchestrator               ||                               |
+-----------------------------++-------------------------------+
                               |
            +------------------+------------------+
            |   Level 2: Design Agents            |
            +-------------------------------------+
            |  * Experiment Design Agent          |
            |  * Metrics Design Agent             |
            |  * Protocol Design Agent            |
            +------------------+------------------+
                               |
                               v
            +------------------+------------------+
            |   Level 3: Specialists (6 agents)   |
            +-------------------------------------+
            |  * Metrics Specialist               |
            |  * Benchmark Specialist             |
            |  * Statistical Specialist           |
            |  * Cost Specialist                  |
            |  * Reporting Specialist             |
            |  * Reproducibility Specialist       |
            +------------------+------------------+
                               |
                               v
            +------------------+------------------+
            |      Level 4: Engineers             |
            +-------------------------------------+
            |  * Implementation Engineer          |
            |  * Test Engineer                    |
            |  * Documentation Engineer           |
            +-------------------------------------+
```

## Level Summaries

### Level 0: Chief Evaluator

- **Agents**: 1 (Chief Evaluator)
- **Scope**: Entire evaluation framework
- **Decisions**: Strategic (tier selection, methodology, research direction)
- **Phase**: Primarily Plan
- **Key Responsibilities**: Define evaluation strategy, select tiers for comparison, approve methodology

### Level 1: Domain Orchestrators

- **Agents**: 4 (Evaluation, Benchmarking, Analysis, Infrastructure)
- **Scope**: Major evaluation domains
- **Decisions**: Tactical (experiment coordination, resource allocation)
- **Phase**: Plan and Review
- **Key Responsibilities**: Coordinate domain-specific work, manage dependencies

### Level 2: Design Agents

- **Agents**: 3 (Experiment, Metrics, Protocol Design)
- **Scope**: Evaluation methodology
- **Decisions**: Design (experiment structure, metrics selection, procedures)
- **Phase**: Plan
- **Key Responsibilities**: Create rigorous, reproducible evaluation designs

### Level 3: Specialists

- **Agents**: 6 (Metrics, Benchmark, Statistical, Cost, Reporting, Reproducibility)
- **Scope**: Specific evaluation aspects
- **Decisions**: Execution (how to measure, analyze, report)
- **Phase**: Test, Implementation, Review
- **Key Responsibilities**: Execute evaluations, collect data, analyze results

### Level 4: Engineers

- **Agents**: 3 (Implementation, Test, Documentation)
- **Scope**: Code and documentation
- **Decisions**: Implementation details
- **Phase**: Test, Implementation
- **Key Responsibilities**: Write code, create tests, produce documentation

## Evaluation-Specific Considerations

### Tier Expertise by Level

**Level 0-1** (Chief and Orchestrators):

- Deep understanding of T0-T6 capability progression
- Knowledge of cost-benefit tradeoffs across tiers
- Strategic selection of tiers for comparison studies
- Understanding of when each tier is appropriate

**Level 2** (Design Agents):

- Expertise in experiment design for fair tier comparison
- Knowledge of confounding variables in agent evaluation
- Understanding of statistical power requirements
- Familiarity with ablation study methodology

**Level 3** (Specialists):

- Proficiency in metrics collection and calculation
- Knowledge of statistical analysis methods
- Understanding of cost accounting for AI systems
- Ability to identify and document reproducibility requirements

**Level 4** (Engineers):

- Hands-on coding ability for evaluation infrastructure
- Familiarity with LLM API integration
- Ability to write robust test harnesses
- Documentation of experimental procedures

### Cross-Tier Considerations

- **Baseline Establishment**: T0 results inform all other tier comparisons
- **Incremental Analysis**: Each tier compared against previous tier
- **Cost Normalization**: All tiers evaluated on same cost basis (CoP)
- **Statistical Validity**: Sufficient samples for confident tier comparisons

## Delegation Flow

### Top-Down (Task Decomposition)

```text
Evaluation Strategy (Level 0)
    |
    v
Domain Coordination (Level 1)
    |
    v
Methodology Design (Level 2)
    |
    v
Execution & Analysis (Level 3)
    |
    v
Implementation (Level 4)
```

### Bottom-Up (Results Aggregation)

```text
Raw Metrics (Level 4)
    ^
    |
Analyzed Results (Level 3)
    ^
    |
Validated Methodology (Level 2)
    ^
    |
Domain Insights (Level 1)
    ^
    |
Strategic Conclusions (Level 0)
```

## Agent Count

| Level | Name | Count |
|-------|------|-------|
| 0     | Chief Evaluator | 1 |
| 1     | Domain Orchestrators | 4 |
| 2     | Design Agents | 3 |
| 3     | Specialists | 6 |
| 4     | Engineers | 3 |
| **Total** | **All Agents** | **17** |

## Quick Reference

### When to Use Each Level

**Use Level 0** when:

- Deciding which tiers to evaluate
- Setting overall evaluation strategy
- Resolving cross-domain conflicts
- Making methodology decisions

**Use Level 1** when:

- Coordinating a major evaluation effort
- Managing multiple specialists
- Allocating evaluation resources

**Use Level 2** when:

- Designing a new experiment
- Defining new metrics
- Creating evaluation protocols

**Use Level 3** when:

- Executing benchmarks
- Calculating metrics
- Performing statistical analysis
- Generating reports

**Use Level 4** when:

- Writing evaluation code
- Creating test harnesses
- Documenting procedures

## Coordination Rules

1. **Delegate Down**: When task is too detailed for current level
1. **Escalate Up**: When decision exceeds current authority
1. **Coordinate Laterally**: When sharing resources or dependencies
1. **Report Status**: Keep superior informed of progress
1. **Document Decisions**: Capture rationale for future reference

## See Also

- [README.md](README.md) - Overview and quick start
- [delegation-rules.md](delegation-rules.md) - Detailed coordination patterns
- [templates/](templates/) - Agent configuration templates
- [/CLAUDE.md](../CLAUDE.md) - Development guidance
