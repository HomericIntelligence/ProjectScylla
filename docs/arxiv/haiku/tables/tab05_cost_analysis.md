# Table 5: Cost Analysis

| Model | Tier | Mean Cost ($) | Total Cost ($) | CoP ($) | Input Tokens | Output Tokens | Cache Read | Cache Create |
|-------|------|---------------|----------------|---------|--------------|---------------|------------|--------------|
| haiku | T0 | 0.43 | 50.74 | 0.68 | 58 | 9377 | 1434145 | 41934 |
| haiku | T1 | 0.38 | 31.80 | 0.52 | 71 | 10769 | 1903419 | 42476 |
| haiku | T2 | 0.37 | 47.83 | 0.44 | 93 | 9775 | 1675915 | 40779 |
| haiku | T3 | 1.55 | 189.31 | 2.04 | 99 | 15364 | 2146701 | 55505 |
| haiku | T4 | 1.36 | 166.98 | 1.67 | 72 | 14228 | 2005438 | 46003 |
| haiku | T5 | 0.37 | 11.02 | 0.73 | 54 | 8309 | 1654493 | 37359 |
| haiku | T6 | 0.55 | 8.28 | 0.59 | 62 | 13399 | 2701216 | 59523 |
| haiku | **Total** | 0.82 | 505.98 | nan | 48316 | 7336345 | 1142367016 | 28176606 |

*Note: Per-tier token columns show mean tokens per run. The Total row token columns show sum across all runs (mean × n per tier), not the mean of means.*
