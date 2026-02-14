# Subtest Best-Run Heatmap (Fig 15b)

## Overview

Figure 15b visualizes the best-performing run for each subtest within each tier, organized as a heatmap. This figure provides a mid-level granularity view that removes run-to-run variance and focuses on the capability ceiling of each agent-tier-subtest combination. By showing only the maximum score achieved across all runs, it reveals the potential performance of each configuration under optimal conditions.

The visualization is structured as a multi-faceted heatmap where:

- Rows represent individual subtests (sorted numerically)
- Columns represent agent models
- Rows are grouped by tiers (T0, T1, T2, etc.)
- Color intensity indicates the highest score achieved (0.0 = red, 0.5 = yellow, 1.0 = green)

## Purpose

This figure serves several critical analytical purposes:

1. **Capability Ceiling Analysis**: Shows the maximum potential performance for each tier-subtest combination, answering "what's the best this configuration can do?"

2. **Variance-Removed Comparison**: Eliminates run-to-run variability to focus on peak capability rather than typical performance, making it easier to identify configurations that can achieve high scores even if inconsistently

3. **Tier Potential Assessment**: Reveals which tiers have the highest performance ceiling for specific subtests, helping identify which architectural choices enable peak performance

4. **Best-Case Benchmarking**: Provides a best-case baseline for comparison with typical performance (fig15a) and aggregate performance (fig15c)

5. **Subtest Difficulty Profiling**: Subtests with uniformly low best-run scores across all tiers indicate inherently difficult tasks, while subtests with high variance suggest tier-dependent capabilities

## Data Source

The figure is generated from the runs DataFrame (`runs_df`), which contains evaluation results for all agent-tier-subtest-run combinations.

### Input Schema

```python
runs_df: pd.DataFrame
# Required columns:
# - agent_model: str        # Agent model identifier (e.g., "opus", "sonnet")
# - tier: str               # Tier identifier (e.g., "T0", "T1", "T2")
# - subtest: str            # Subtest identifier (numeric string, e.g., "00", "01")
# - run_number: str         # Run identifier (e.g., "01", "02", ..., "10")
# - score: float            # Normalized score [0.0, 1.0]
```

### Data Aggregation Process

The data undergoes best-run selection:

```python
# For each (agent_model, tier, subtest), keep only the run with highest score
best_runs = (
    runs_df.sort_values("score", ascending=False)
    .groupby(["agent_model", "tier", "subtest"])
    .first()
    .reset_index()
)
```

This produces one row per (agent_model, tier, subtest) triple, representing the best-performing run for that combination.

### Output Schema

```python
heatmap_data: pd.DataFrame
# Columns:
# - agent_model: str        # Agent model
# - tier: str               # Tier identifier
# - subtest: str            # Subtest identifier
# - run_number: str         # The run number that achieved the best score
# - score: float            # Maximum score achieved [0.0, 1.0]
# - subtest_num: int        # Numeric subtest ID for sorting
```

## Mathematical Formulas

### Best-Run Selection

For each unique combination of agent model, tier, and subtest, select the maximum score:

```
best_score(agent, tier, subtest) = max({score(agent, tier, subtest, run) | run ∈ R})

where:
  R = {01, 02, 03, ..., 10}  # Set of all runs
  score: (agent, tier, subtest, run) → [0, 1]  # Score function
```

In set notation:

```
BestRuns = {(a, t, s, r*, score*) | ∀(a,t,s) ∈ Configurations,
                                     (r*, score*) = argmax score(a,t,s,r)}
                                                    r∈R

where:
  a ∈ AgentModels
  t ∈ Tiers
  s ∈ Subtests
  r ∈ Runs = {01, 02, ..., 10}
```

### Performance Metrics

The best-run approach enables several derived metrics:

**Best-Case Pass Rate** (per tier-subtest):

```
best_pass_rate(tier, subtest) = best_score(tier, subtest)  # If score ∈ {0,1}
```

**Capability Gap** (comparing with typical performance):

```
capability_gap(agent, tier, subtest) = best_score - mean_score

where:
  best_score = max({score_run | run ∈ R})
  mean_score = (1/|R|) * Σ score_run
```

**Tier Ceiling** (maximum achievable score for a tier):

```
tier_ceiling(tier) = (1/|S|) * Σ best_score(tier, s)
                              s∈S

where S = set of all subtests in the tier
```

## Theoretical Foundation

### Best-Run Analysis Rationale

Best-run analysis is based on the principle of **capability ceiling measurement**, which has several theoretical justifications:

1. **Possibility Proof**: If a configuration achieves a high score even once, it proves the capability exists, even if not consistently accessible. This is valuable for understanding the theoretical limits of an architecture.

2. **Variance Decomposition**: Agent performance variance can be decomposed into:

   ```
   Total Variance = Systematic Variance + Stochastic Variance

   Best-run analysis focuses on:
     Capability Ceiling = Mean Performance + (k × Stochastic Variance)

   where k depends on the number of runs
   ```

3. **Upper Confidence Bound**: The best-run score approximates the upper confidence bound of the performance distribution:

   ```
   UCB ≈ best_score ≈ μ + c√(σ²/n)

   where:
     μ = true mean performance
     σ² = performance variance
     n = number of runs
     c = confidence coefficient
   ```

### Comparison with Mean Performance

The relationship between best-run and mean performance is informative:

```
best_score ≥ mean_score + kσ

where:
  k ≈ 1.5 to 2.0 for 10 runs (depends on distribution)
  σ = standard deviation of scores
```

**High Gap (best >> mean)**:

- Indicates high variance/inconsistency
- Configuration has capability but reliability issues
- Potential for improvement through stability enhancements

**Low Gap (best ≈ mean)**:

- Indicates consistent performance
- Configuration reliably achieves near-ceiling results
- Less room for improvement through repeated trials

### Statistical Considerations

**Order Statistics**: The best-run score is the maximum order statistic from a sample of size n=10:

```
E[X_max] = μ + σ × E[Z_max]

where Z_max is the expected maximum of n standard normal samples
For n=10: E[Z_max] ≈ 1.54
```

**Extreme Value Theory**: For large samples, maximum values follow the Gumbel distribution, but with n=10 runs, we're in the small-sample regime where this approximation doesn't apply.

## Visualization Details

### Color Encoding

The heatmap uses a diverging color scheme to represent score ranges:

```
Color Scale: "redyellowgreen"
  - Red (0.0): Complete failure
  - Yellow (0.5): Partial success
  - Green (1.0): Complete success

Domain: [0.0, 1.0]
Normalization: Linear
```

Color assignment:

```python
color=alt.Color(
    "score:Q",
    title="Score",
    scale=alt.Scale(
        scheme="redyellowgreen",
        domain=[0, 1],
    ),
)
```

### Layout Structure

**Faceting Strategy**:

- **Rows**: Tiers (T0, T1, T2, ...) - naturally sorted
- **Columns**: Agent models (dynamically determined from data)
- **Independent Y-scales**: Each tier panel has independent y-axis (subtests vary by tier)

```python
chart = heatmap.facet(
    row=alt.Row("tier:O", title="Tier", sort=tier_order),
    column=alt.Column("agent_model:N", title=None),
).resolve_scale(y="independent")
```

**Panel Dimensions**:

```python
width=100   # Narrow width since only one column per model (vs 10 for all runs)
height=200  # Sufficient height for multiple subtests
```

### Axes Configuration

**X-Axis**: Suppressed since there's only one cell per subtest (the best run)

```python
x=alt.X(
    "agent_model:N",
    title=None,
    axis=alt.Axis(labels=False, ticks=False),
)
```

**Y-Axis**: Subtest identifiers, numerically sorted

```python
y=alt.Y(
    "subtest:O",
    title="Subtest",
    sort=subtest_order,  # ["00", "01", "02", ...]
)
```

### Interactive Elements

**Tooltip Information**:

```python
tooltip=[
    alt.Tooltip("tier:O", title="Tier"),
    alt.Tooltip("subtest:O", title="Subtest"),
    alt.Tooltip("run_number:O", title="Best Run"),  # Which run achieved best score
    alt.Tooltip("score:Q", title="Score", format=".3f"),
]
```

The tooltip includes the run number that achieved the best score, allowing users to trace back to the specific run for detailed analysis.

## Interpretation Guidelines

### Reading the Heatmap

1. **Vertical Patterns** (within a tier-model panel):
   - **Uniform green**: Tier consistently achieves high performance across subtests
   - **Uniform red**: Tier struggles across all subtests (architectural limitation)
   - **Mixed colors**: Tier-specific capabilities (some subtests benefit from tier features)

2. **Horizontal Patterns** (across models):
   - **Consistent colors**: Subtest difficulty is tier-dependent, not model-dependent
   - **Model variations**: Subtest performance varies by agent model characteristics

3. **Across-Tier Patterns** (comparing tier rows):
   - **Improving performance**: Later tiers enable better scores (architectural benefits)
   - **Degrading performance**: Later tiers may introduce complexity/overhead
   - **Plateau patterns**: Diminishing returns from additional tier features

### Comparative Analysis

**Comparing with Fig 15a (All Runs)**:

```
Performance Gap = best_score (fig15b) - mean_score (fig15a)

Interpretation:
  - Large gap: High variance, inconsistent performance
  - Small gap: Stable performance, reliable configuration
  - Zero gap: Perfect consistency (all runs identical)
```

**Comparing with Fig 15c (Tier Summary)**:

```
Tier Ceiling vs Tier Mean:
  - Ceiling >> Mean: Potential for optimization
  - Ceiling ≈ Mean: Already near-optimal
```

### Performance Benchmarks

**Score Interpretation**:

- **[0.0, 0.3)**: Poor performance - architectural mismatch or task too difficult
- **[0.3, 0.5)**: Below average - some capability but significant gaps
- **[0.5, 0.7)**: Moderate performance - partial task completion
- **[0.7, 0.9)**: Good performance - most requirements met
- **[0.9, 1.0]**: Excellent performance - near-complete success

**Best-Run Specific Benchmarks**:

- **Best < 0.5**: Fundamental capability limitation (even optimal runs fail)
- **Best ∈ [0.5, 0.9)**: Capability exists but not fully realized
- **Best ≥ 0.9**: Configuration can achieve high performance (reliability issue if mean << best)

### Decision Criteria

Use this figure to answer:

1. **"What's the performance ceiling?"**
   - Look at best scores for each tier-subtest combination
   - Identifies maximum achievable performance

2. **"Is inconsistency the problem?"**
   - Compare best_score (fig15b) with mean_score (fig15a)
   - Large gap → focus on stability improvements
   - Small gap → near-ceiling performance already

3. **"Which tiers enable peak performance?"**
   - Identify tiers with highest best-run scores
   - Reveals which architectural features unlock capabilities

4. **"Should we invest in more runs?"**
   - If best_score is high but mean_score is low, more runs may help
   - If best_score is already low, more runs won't help

## Related Figures

### Figure Series: Subtest Detail Analysis (Fig 15a/b/c)

The three figures provide complementary views of subtest performance:

| Figure | Granularity | Focus | Use Case |
|--------|-------------|-------|----------|
| **Fig 15a** | Maximum (all runs) | Run-to-run variance | Identifying inconsistency patterns |
| **Fig 15b** | Mid (best run only) | Capability ceiling | Understanding maximum potential |
| **Fig 15c** | Minimum (tier aggregates) | Tier-level trends | High-level tier comparison |

### Upstream Dependencies

These figures provide input context:

- **Fig 01**: Agent-level performance overview (establishes baseline)
- **Fig 02**: Judge variance analysis (score reliability)

### Downstream Dependencies

This figure informs:

- **Fig 15c**: Tier summary aggregation uses best-run insights
- **Cost-of-Pass Analysis**: Best-run costs establish lower bound for optimization

### Complementary Analyses

**Fig 15a (All Runs)**: Shows complete picture including variance

```
Fig 15b = max(Fig 15a runs)  # Vertical compression
```

**Fig 15c (Tier Summary)**: Aggregates across subtests

```
Fig 15c = mean_across_subtests(Fig 15b)  # Horizontal aggregation
```

**Combined Insights**:

```
Performance Profile:
  - Best-case: Fig 15b (capability ceiling)
  - Typical-case: mean(Fig 15a) (expected performance)
  - Aggregate-case: Fig 15c (tier-level summary)
```

## Code Reference

### Source Location

```
File: scylla/analysis/figures/subtest_detail.py
Function: fig15b_subtest_best_heatmap (lines 153-228)
Module: scylla.analysis.figures.subtest_detail
```

### Function Signature

```python
def fig15b_subtest_best_heatmap(
    runs_df: pd.DataFrame,
    output_dir: Path,
    render: bool = True
) -> None:
    """Generate Fig 15b: Per-Tier Subtest Heatmap (Best Run Only).

    Shows only the best-performing run for each subtest.
    Mid-level granularity - removes run variance, focuses on capability ceiling.

    Args:
        runs_df: Runs DataFrame with columns [agent_model, tier, subtest, run_number, score]
        output_dir: Directory for output files (JSON, PNG, PDF)
        render: If True, generate PNG/PDF visualizations

    Outputs:
        - {output_dir}/fig15b_subtest_best_heatmap.json (Vega-Lite spec)
        - {output_dir}/fig15b_subtest_best_heatmap.png (if render=True)
        - {output_dir}/fig15b_subtest_best_heatmap.pdf (if render=True)
    """
```

### Key Implementation Details

**Best-Run Selection** (lines 168-173):

```python
best_runs = (
    runs_df.sort_values("score", ascending=False)
    .groupby(["agent_model", "tier", "subtest"])
    .first()
    .reset_index()
)
```

**Subtest Ordering** (lines 182-183):

```python
heatmap_data["subtest_num"] = heatmap_data["subtest"].astype(int)
subtest_order = sorted(heatmap_data["subtest"].unique(), key=lambda x: int(x))
```

**Tier Ordering** (line 179):

```python
tier_order = derive_tier_order(heatmap_data)
# Uses natural sorting: T0 < T1 < ... < T99
```

### Dependencies

```python
# External libraries
import altair as alt
import pandas as pd
from pathlib import Path

# Internal modules
from scylla.analysis.figures import derive_tier_order
from scylla.analysis.figures.spec_builder import save_figure
```

### Output Files

```
{output_dir}/
├── fig15b_subtest_best_heatmap.json    # Vega-Lite specification
├── fig15b_subtest_best_heatmap.png     # Raster visualization (if render=True)
└── fig15b_subtest_best_heatmap.pdf     # Vector visualization (if render=True)
```

### Related Functions

- `fig15a_subtest_run_heatmap()`: All runs heatmap (lines 87-150)
- `fig15c_tier_summary_heatmap()`: Tier aggregation (lines 231-289)
- `derive_tier_order()`: Tier sorting utility (`scylla/analysis/figures/__init__.py`)
- `save_figure()`: Output file generation (`scylla/analysis/figures/spec_builder.py`)
