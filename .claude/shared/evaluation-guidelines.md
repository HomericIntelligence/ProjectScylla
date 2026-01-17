# Evaluation Guidelines

Shared evaluation methodology guidelines for all agents. Reference this file for evaluation best practices.

## Core Principles

### Scientific Rigor

1. **Reproducibility**: All experiments must be reproducible
2. **Statistical Validity**: Use appropriate statistical methods
3. **Fair Comparison**: Control for confounding variables
4. **Transparency**: Document all methodology decisions

### Cost Awareness

1. **Track All Costs**: Include API calls, compute, human time
2. **Report CoP**: Cost-of-Pass is the primary economic metric
3. **Optimize Responsibly**: Balance cost reduction with validity

## Experiment Design

### Before Starting

1. **Define Hypothesis**: What are you testing?
2. **Select Metrics**: Which metrics will you collect?
3. **Determine Sample Size**: Calculate required n for statistical power
4. **Plan Analysis**: How will you analyze results?

### Sample Size Guidance

| Effect Size | Required n (per group) | Power |
|-------------|------------------------|-------|
| Large (d=0.8) | 26 | 0.80 |
| Medium (d=0.5) | 64 | 0.80 |
| Small (d=0.2) | 394 | 0.80 |

For tier comparisons, minimum n=50 per tier recommended.

### Randomization

- Randomize task order within each tier
- Use fixed random seeds for reproducibility
- Document seed values in experiment configuration

## Benchmark Execution

### Setup Checklist

- [ ] Environment documented (Python version, dependencies)
- [ ] API keys configured (not committed to repo)
- [ ] Random seeds set
- [ ] Logging enabled
- [ ] Cost tracking enabled

### During Execution

- Monitor for anomalies (unusual latency, error rates)
- Track token usage per request
- Log all API responses
- Handle errors gracefully (see error-handling.md)

### After Execution

- Validate data completeness
- Check for outliers
- Calculate summary statistics
- Archive raw data

## Metrics Collection

### Quality Metrics

**Pass-Rate**:

```python
pass_rate = correct_solutions / total_attempts
```

**Implementation Rate** (Impl-Rate):

```python
impl_rate = satisfied_requirements / total_requirements
```

**Fine-Grained Progress Rate** (R_Prog):

```python
r_prog = achieved_progress_steps / expected_progress_steps
```

### Economic Metrics

**Cost-of-Pass** (CoP):

```python
cop = total_cost / pass_rate
# If pass_rate = 0, report as "infinite" or "N/A"
```

**Token Distribution**:

```python
token_dist = {
    'input': input_tokens / total_tokens,
    'output': output_tokens / total_tokens
}
```

### Process Metrics

**Latency**: Time from request to response (seconds)

**Consistency**: Standard deviation across multiple runs

## Statistical Analysis

### Comparing Two Tiers

Use independent samples t-test or Mann-Whitney U:

```python
from scipy import stats

# For normally distributed data
t_stat, p_value = stats.ttest_ind(tier_a_results, tier_b_results)

# For non-normal data
u_stat, p_value = stats.mannwhitneyu(tier_a_results, tier_b_results)
```

### Comparing Multiple Tiers

Use ANOVA or Kruskal-Wallis:

```python
# Parametric
f_stat, p_value = stats.f_oneway(t0, t1, t2, t3)

# Non-parametric
h_stat, p_value = stats.kruskal(t0, t1, t2, t3)
```

### Post-hoc Tests

For significant ANOVA results, use Tukey HSD:

```python
from statsmodels.stats.multicomp import pairwise_tukeyhsd

tukey = pairwise_tukeyhsd(all_results, tier_labels, alpha=0.05)
```

### Reporting Statistics

Always report:

- Sample size (n)
- Mean and standard deviation
- 95% confidence intervals
- p-values
- Effect size (Cohen's d)

## Tier-Specific Considerations

### T0 (Prompts)

- System prompt ablation (24 sub-tests)
- Baseline reference for all comparisons
- Document exact system prompt per sub-test
- Track prompt iteration history

### T1 (Skills)

- Domain expertise via installed skills (10 sub-tests by category)
- Document skill definitions
- Track which skills are used per task
- Measure skill activation frequency

### T2 (Tooling)

- External tools and MCP servers (15 sub-tests)
- Document tool schemas
- Track tool usage patterns
- Measure tool call success rate

### T3 (Delegation)

- Flat multi-agent with specialist agents (41 sub-tests per agent)
- Document agent topology
- Track inter-agent communication
- Measure coordination overhead

### T4 (Hierarchy)

- Nested orchestration with orchestrator agents (7 sub-tests)
- Document supervision structure
- Track correction frequency
- Measure iteration count to success

### T5 (Hybrid)

- Best combinations and permutations from all tiers (15 sub-tests)
- Document component selection rationale
- Track which components from which tiers
- Measure synergy effects

### T6 (Super)

- Everything enabled at maximum capability (1 sub-test)
- Document all enabled components
- Track combined effect of all capabilities
- Measure peak performance vs cost trade-off

## Reporting Results

### Required Elements

1. **Methodology Summary**: How the evaluation was conducted
2. **Results Table**: All metrics per tier
3. **Statistical Analysis**: Significance tests and effect sizes
4. **Visualizations**: Charts where helpful
5. **Conclusions**: Key findings and recommendations
6. **Limitations**: Known limitations and caveats

### Results Table Template

```markdown
| Tier | n | Pass-Rate (95% CI) | CoP ($) | Latency (s) |
|------|---|-------------------|---------|-------------|
| T0   | 50 | 0.23 (0.12-0.34) | 4.35    | 12.3        |
| T1   | 50 | 0.45 (0.31-0.59) | 2.22    | 15.7        |
```

### Visualization Guidelines

- Use bar charts for tier comparisons
- Include error bars (95% CI)
- Use consistent colors across analyses
- Label axes clearly

## Common Pitfalls

### Avoid These Mistakes

1. **p-hacking**: Don't run tests until you find significance
2. **Cherry-picking**: Report all results, not just favorable ones
3. **Underpowered studies**: Ensure adequate sample size
4. **Confounding variables**: Control for prompt quality, task difficulty
5. **Publication bias**: Document null results

### Quality Checks

Before reporting results:

- [ ] Sample size meets minimum requirements
- [ ] Statistical tests are appropriate
- [ ] Confidence intervals are included
- [ ] Effect sizes are reported
- [ ] Limitations are documented
