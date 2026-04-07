# Table 5: Cost Analysis

| Model | Tier | Mean Cost ($) | Total Cost ($) | CoP ($) | Input Tokens | Output Tokens | Cache Read | Cache Create |
|-------|------|---------------|----------------|---------|--------------|---------------|------------|--------------|
| claude-haiku-4-5 | T0 | 0.11 | 23.65 | 0.12 | 67 | 2409 | 593588 | 24501 |
| claude-haiku-4-5 | T1 | 0.11 | 10.19 | 0.12 | 42 | 2601 | 644806 | 24674 |
| claude-haiku-4-5 | T2 | 0.11 | 14.89 | 0.11 | 43 | 2659 | 638340 | 23350 |
| claude-haiku-4-5 | T3 | 0.11 | 41.62 | 0.15 | 60 | 2637 | 632159 | 24241 |
| claude-haiku-4-5 | T4 | 0.12 | 14.71 | 0.18 | 41 | 2584 | 649313 | 24472 |
| claude-haiku-4-5 | T5 | 0.12 | 15.91 | 0.19 | 49 | 2565 | 657564 | 28149 |
| claude-haiku-4-5 | T6 | 0.15 | 1.35 | 0.22 | 47 | 2665 | 772688 | 47389 |
| claude-haiku-4-5 | **Total** | 0.11 | 122.31 | --- | 58,559* | 2,782,286* | 683,228,777* | 26,920,157* |

*Token columns show per-run means for individual tiers and absolute totals (*) for the Total row.
