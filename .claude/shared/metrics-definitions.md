# Metrics Definitions

Complete definitions of all metrics used in ProjectScylla evaluations.

## Quality Metrics

### Pass-Rate

**Definition**: Proportion of attempts that produce a correct solution.

**Formula**:

```
Pass-Rate = correct_solutions / total_attempts
```

**Range**: [0, 1]

**Interpretation**:

- 0.0 = No correct solutions
- 1.0 = All solutions correct

**Notes**:

- "Correct" defined by task-specific test suite
- Report with confidence intervals

### Implementation Rate (Impl-Rate)

**Definition**: Proportion of semantic requirements satisfied by the solution.

**Formula**:

```
Impl-Rate = satisfied_requirements / total_requirements
```

**Range**: [0, 1]

**Interpretation**:

- Measures partial credit for incomplete solutions
- More granular than binary Pass-Rate

**Notes**:

- Requires predefined requirement checklist
- Each requirement should be independently verifiable

### Fine-Grained Progress Rate (R_Prog)

**Definition**: Proportion of expected progress steps achieved during problem-solving.

**Formula**:

```
R_Prog = achieved_progress_steps / expected_progress_steps
```

**Range**: [0, 1+]

**Interpretation**:

- Captures step-by-step advancement
- Can exceed 1.0 if agent takes extra (beneficial) steps

**Notes**:

- Requires progress step definitions per task
- Useful for debugging agent behavior

### Consistency

**Definition**: Stability of outputs across multiple runs with identical inputs.

**Formula**:

```
Consistency = 1 - (std(outputs) / mean(outputs))
```

**Range**: [0, 1] (higher is more consistent)

**Notes**:

- Requires multiple runs per task
- Temperature=0 should yield high consistency

## Economic Metrics

### Cost-of-Pass (CoP)

**Definition**: Expected monetary cost to obtain one correct solution.

**Formula**:

```
CoP = total_cost / pass_rate
```

**Unit**: USD ($)

**Range**: [0, infinity)

**Interpretation**:

- Lower is better
- Infinite if pass_rate = 0

**Notes**:

- Primary economic metric for tier comparison
- Include all costs (input tokens, output tokens, tools)

### Frontier CoP

**Definition**: Minimum Cost-of-Pass across all evaluated tiers.

**Formula**:

```
Frontier_CoP = min(CoP_T0, CoP_T1, ..., CoP_T6)
```

**Interpretation**:

- Identifies most cost-effective tier
- Target for optimization

### Token Distribution

**Definition**: Breakdown of token usage by component.

**Formula**:

```
token_dist = {
    'input': input_tokens / total_tokens,
    'output': output_tokens / total_tokens,
    'tool_input': tool_input_tokens / total_tokens,
    'tool_output': tool_output_tokens / total_tokens
}
```

**Notes**:

- Helps identify cost drivers
- Useful for optimization targeting

### Change Fail Percentage (CFP)

**Definition**: Proportion of code changes that cause failures.

**Formula**:

```
CFP = failed_changes / total_changes
```

**Range**: [0, 1]

**Interpretation**:

- Lower is better
- Measures production stability

### PR Revert Rate

**Definition**: Proportion of pull requests that are reverted.

**Formula**:

```
PR_Revert_Rate = reverted_prs / merged_prs
```

**Range**: [0, 1]

**Interpretation**:

- Lower is better
- Indicates code quality

## Process Metrics

### Latency

**Definition**: Time from query submission to response completion.

**Unit**: Seconds (s)

**Components**:

- Time-to-First-Token (TTFT)
- Total response time
- Tool execution time (if applicable)

### Strategic Drift

**Definition**: Deviation from original goal over multi-step tasks.

**Measurement**:

```
Strategic_Drift = cosine_distance(initial_goal_embedding, final_action_embedding)
```

**Range**: [0, 2]

**Interpretation**:

- 0 = Perfect goal alignment
- 2 = Completely opposite direction

### Ablation Score

**Definition**: Isolated contribution of a single component to overall performance.

**Formula**:

```
Ablation_Score = performance_with_component - performance_without_component
```

**Interpretation**:

- Positive = Component improves performance
- Negative = Component hurts performance
- Near zero = Component has no effect

## Tier-Specific Metrics

### T3 (Tooling)

**Tool Call Success Rate**:

```
Tool_Success_Rate = successful_tool_calls / total_tool_calls
```

**Tool Utilization**:

```
Tool_Utilization = tasks_using_tools / total_tasks
```

### T4 (Delegation)

**Delegation Overhead**:

```
Delegation_Overhead = multi_agent_cost / single_agent_equivalent_cost
```

**Task Distribution Efficiency**:

```
Task_Distribution_Efficiency = 1 - (idle_time / total_time)
```

### T5 (Hierarchy)

**Correction Frequency**:

```
Correction_Frequency = corrections_made / total_steps
```

**Iterations to Success**:

```
Iterations_to_Success = number_of_self_correction_loops
```

## Statistical Reporting

### Standard Format

Always report metrics with:

1. **Point estimate**: The calculated value
2. **Confidence interval**: 95% CI recommended
3. **Sample size**: n for the calculation
4. **Comparison p-value**: If comparing tiers

### Example

```markdown
Pass-Rate: 0.67 (95% CI: 0.54-0.80), n=50
CoP: $1.49 (95% CI: $1.21-$1.77), n=50
Latency: 18.2s (95% CI: 16.4-20.0s), n=50
```

## Aggregation Methods

### Across Tasks

For comparing tiers across multiple tasks:

```
Aggregate_Metric = mean(task_metrics, weights=task_importance)
```

### Across Runs

For combining multiple runs of same experiment:

```
Combined_Estimate = mean(run_estimates)
Combined_SE = sqrt(sum(run_SE^2)) / n_runs
```

## Metric Selection Guide

| Question | Primary Metric | Secondary Metrics |
|----------|---------------|-------------------|
| Which tier is most accurate? | Pass-Rate | Impl-Rate, R_Prog |
| Which tier is most cost-effective? | CoP | Token Distribution |
| Which tier is fastest? | Latency | TTFT |
| Which tier is most reliable? | Consistency | CFP |
| Is this component useful? | Ablation Score | - |
