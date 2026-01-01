# Metrics Formulas Documentation

This document defines all metrics formulas used in ProjectScylla's evaluation framework.

## Overview

ProjectScylla uses a multi-tier evaluation system with:
- **10 runs per tier** for statistical validity
- **Per-run metrics** for individual evaluation
- **Aggregate statistics** across runs
- **Cross-tier analysis** for comparison

## Per-Run Metrics

### Pass Rate

Binary pass/fail indicator for each run.

```
pass_rate = 1.0 if passed else 0.0
```

| Value | Meaning |
|-------|---------|
| 1.0 | Run passed all tests |
| 0.0 | Run failed one or more tests |

### Implementation Rate (impl_rate)

Semantic requirement satisfaction from the judge's weighted score.

```
impl_rate = judgment.summary.weighted_score
```

Value range: `[0.0, 1.0]`

### Cost (USD)

Total cost of the run in US dollars.

```
cost_usd = input_tokens * input_price + output_tokens * output_price
```

Pricing varies by model:
| Model | Input ($/1M) | Output ($/1M) |
|-------|-------------|---------------|
| Claude Opus 4.5 | $15.00 | $75.00 |
| Claude Sonnet 4 | $3.00 | $15.00 |
| GPT-4o | $5.00 | $15.00 |

### Duration

Time from start to completion in seconds.

```
duration_seconds = end_time - start_time
```

### Cost of Pass (CoP)

Expected cost to achieve a successful run.

```
cost_of_pass = cost_usd / pass_rate

# If pass_rate = 0:
cost_of_pass = infinity  # Infinitely expensive to pass
```

**Interpretation**:
- Lower CoP = more cost-effective
- `CoP = $1.00` means each pass costs $1.00
- `CoP = infinity` means never passes (avoid this tier)

### Composite Score

Weighted combination of pass_rate and impl_rate.

```
composite_score = (pass_rate * pass_weight + impl_rate * impl_weight) / (pass_weight + impl_weight)

# Default weights:
pass_weight = 0.5
impl_weight = 0.5

# Simplified (equal weights):
composite_score = (pass_rate + impl_rate) / 2
```

## Aggregate Statistics (10 Runs)

Each metric is aggregated across 10 runs per tier.

### Median

Middle value when sorted. For 10 runs, average of 5th and 6th values.

```
sorted_values = sorted(values)
n = len(sorted_values)

if n % 2 == 1:
    median = sorted_values[n // 2]
else:
    mid = n // 2
    median = (sorted_values[mid - 1] + sorted_values[mid]) / 2
```

**Why median?** More robust to outliers than mean.

### Mean

Arithmetic average.

```
mean = sum(values) / len(values)
```

### Mode

Most frequent value.

```
mode = most_common(values)

# If multiple modes, return smallest
```

### Range (Min/Max)

Minimum and maximum values.

```
min_value = min(values)
max_value = max(values)
```

### Standard Deviation

Measure of spread around the mean.

```
variance = sum((v - mean)^2 for v in values) / len(values)
std_dev = sqrt(variance)
```

**Why population std_dev?** We have all 10 runs, not a sample.

### All Statistics

```python
@dataclass
class Statistics:
    median: float
    mean: float
    mode: float
    min: float
    max: float
    std_dev: float
    count: int
```

## Letter Grade Assignment

Grades are assigned from the median composite score.

| Grade | Threshold | Meaning |
|-------|-----------|---------|
| A | >= 0.95 | Excellent |
| B | >= 0.85 | Good |
| C | >= 0.75 | Satisfactory |
| D | >= 0.65 | Marginal |
| F | < 0.65 | Failing |

```
def assign_letter_grade(score: float) -> str:
    if score >= 0.95: return "A"
    if score >= 0.85: return "B"
    if score >= 0.75: return "C"
    if score >= 0.65: return "D"
    return "F"
```

## Cross-Tier Metrics

### Tier Uplift

Percentage improvement over T0 baseline.

```
tier_uplift = (tier_score - t0_score) / t0_score

# Example:
# T0 composite = 0.75
# T1 composite = 0.90
# uplift = (0.90 - 0.75) / 0.75 = 0.20 (20% improvement)
```

**Interpretation**:
- Positive = improvement over baseline
- Negative = regression (worse than baseline)
- Zero = no change

### Pass Rate Variance

How much pass rates differ across tiers.

```
pass_rate_variance = variance([tier.pass_rate.median for tier in tiers])
```

**Interpretation**:
- Low variance = consistent across tiers (prompt insensitive)
- High variance = varies by tier (prompt sensitive)

### Cost Variance

How much costs differ across tiers.

```
cost_variance = variance([tier.cost_usd.median for tier in tiers])
```

### Cost Delta

Difference between most and least expensive tiers.

```
cost_delta = max(costs) - min(costs)
```

## Example Calculations

### Example 1: Single Run

```
Input:
  passed = True
  weighted_score = 0.85
  cost_usd = 0.50

Calculations:
  pass_rate = 1.0
  impl_rate = 0.85
  cost_of_pass = 0.50 / 1.0 = $0.50
  composite_score = (1.0 + 0.85) / 2 = 0.925
  grade = "A" (0.925 >= 0.95? No -> 0.925 >= 0.85? Yes -> "B")

Wait, 0.925 >= 0.85 but < 0.95, so grade = "B"
```

### Example 2: 10-Run Aggregation

```
Input (pass_rates):
  [1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0]

Calculations:
  sorted = [0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
  median = (1.0 + 1.0) / 2 = 1.0
  mean = 8/10 = 0.8
  mode = 1.0
  min = 0.0
  max = 1.0
  std_dev = sqrt((2*(0.8)^2 + 8*(0.2)^2) / 10) = sqrt(0.16) = 0.4
```

### Example 3: Cross-Tier Analysis

```
Input:
  T0: composite_median = 0.70
  T1: composite_median = 0.80
  T2: composite_median = 0.85
  T3: composite_median = 0.90

Tier Uplifts (vs T0):
  T1: (0.80 - 0.70) / 0.70 = 0.143 (14.3%)
  T2: (0.85 - 0.70) / 0.70 = 0.214 (21.4%)
  T3: (0.90 - 0.70) / 0.70 = 0.286 (28.6%)

Variance:
  mean = (0.70 + 0.80 + 0.85 + 0.90) / 4 = 0.8125
  variance = ((0.70-0.8125)^2 + (0.80-0.8125)^2 +
              (0.85-0.8125)^2 + (0.90-0.8125)^2) / 4
           = (0.01266 + 0.00016 + 0.00141 + 0.00766) / 4
           = 0.00547
```

## Process Metrics

These metrics capture the quality of the agent's execution process, not just the final outcome.

### Fine-Grained Progress Rate (R_Prog)

Captures incremental advancements through the execution trajectory.

```
r_prog = achieved_weighted_steps / expected_weighted_steps

# Simple version (equal weights):
r_prog = achieved_steps / expected_steps
```

**Interpretation**:
- 1.0 = all expected steps completed
- 0.5 = halfway through expected steps
- 0.0 = no progress

**Why R_Prog?** Diagnoses where agents fail in multi-step tasks.

### Strategic Drift

Measures how much intermediate actions diverge from the intended goal.

```
strategic_drift = 1 - (sum(goal_alignment * weight) / sum(weight))

# Simple version (binary alignment):
strategic_drift = 1 - (goal_aligned_actions / total_actions)
```

**Interpretation**:
- 0.0 = perfect alignment (no drift)
- 1.0 = complete misalignment (all actions off-track)

### Change Fail Percentage (CFP)

DevOps stability metric: percentage of changes that cause service failures.

```
cfp = failed_changes / total_changes
```

**Interpretation**:
- 0.0 = no failures (stable output)
- 0.1 = 10% of changes cause failures
- High CFP indicates brittle solutions

### PR Revert Rate

Frequency of agent-generated changes rejected by human reviewers.

```
pr_revert_rate = reverted_changes / total_changes
```

## Token Tracking (T2 vs T3 Analysis)

These metrics analyze the "Token Efficiency Chasm" between T2 (Skills) and T3 (Tooling).

### Schema Overhead

Total tokens consumed by tool schemas (T3+).

```
schema_overhead = sum(tokens for component_type == TOOL_SCHEMA)
```

**Key insight**: T3 architectures load JSON schemas that can consume 50k+ tokens upfront.

### Skill Efficiency

Ratio of skill tokens to total (skill + schema) tokens.

```
skill_efficiency = skill_tokens / (skill_tokens + schema_overhead)
```

**Interpretation**:
- 1.0 = no schema overhead (pure T2)
- 0.2 = 80% of tokens are schema overhead

### Token Efficiency Ratio

Comparison of schema tokens to skill tokens.

```
token_efficiency_ratio = schema_tokens / skill_tokens
```

**Interpretation**:
- ratio > 1.0 = schemas use more tokens than skills
- ratio = 10.0 = schemas use 10x more tokens

### Component Cost Breakdown

Track costs at the component level:

| Component Type | Description |
|----------------|-------------|
| `SYSTEM_PROMPT` | Base system prompt |
| `SKILL_PROMPT` | T2 skill instructions |
| `DOMAIN_EXPERTISE` | T2 domain knowledge |
| `TOOL_SCHEMA` | T3 JSON tool definitions |
| `TOOL_CALL` | T3 tool invocations |
| `TOOL_RESPONSE` | T3 tool results |
| `ORCHESTRATOR` | T4/T5 coordination |
| `SUB_AGENT` | T4/T5 delegated agents |
| `MONITOR` | T5 error detection |
| `EVALUATOR` | T5 self-reflection |

```python
# Calculate per-component costs
distribution = tracker.calculate_distribution(
    input_price=3.0,   # $/1M input tokens
    output_price=15.0, # $/1M output tokens
)

# Get schema overhead percentage
schema_pct = distribution.get_type_percentage(ComponentType.TOOL_SCHEMA)
```

## Summary Table

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|----------------|
| pass_rate | `1.0 if passed else 0.0` | [0, 1] | Higher = better |
| impl_rate | `weighted_score` | [0, 1] | Higher = better |
| cost_usd | `input*price + output*price` | [0, ∞) | Lower = better |
| cost_of_pass | `cost / pass_rate` | [0, ∞] | Lower = better |
| composite | `(pass + impl) / 2` | [0, 1] | Higher = better |
| tier_uplift | `(tier - t0) / t0` | (-∞, ∞) | Positive = improvement |
| variance | `Σ(x - μ)² / n` | [0, ∞) | Lower = more consistent |
| r_prog | `achieved / expected` | [0, 1] | Higher = more progress |
| strategic_drift | `1 - alignment` | [0, 1] | Lower = better alignment |
| cfp | `failed / total` | [0, 1] | Lower = more stable |
| schema_overhead | `sum(schema_tokens)` | [0, ∞) | Lower = more efficient |

## Related Documentation

- [Judge Protocol](./judge-protocol.md) - How judgments produce weighted_score
- [Evaluation Categories](./judge-protocol.md#evaluation-categories) - 10 quality categories
- [Research Methodology](../research.md) - Original metrics definitions
