# Table 2b: Impl-Rate Tier Pairwise Comparison

*Statistical workflow: Kruskal-Wallis omnibus test, then pairwise Mann-Whitney U with Holm-Bonferroni correction (step-down)*

**Omnibus Test Results (Kruskal-Wallis):**
- claude-haiku-4-5: H(6)=5.47, p=0.4855 ✗ (skip pairwise), power=1.000

| Model | Transition | N (T1, T2) | Impl-Rate Δ | p-value | Cliff's δ | Power | Significant? |
|-------|------------|------------|-------------|---------|-----------|-------|--------------|
| claude-haiku-4-5 | T0→T1 | (216, 90) | +0.0373 | — | +0.057 | 0.125 | N/A (omnibus n.s.) |
| claude-haiku-4-5 | T1→T2 | (90, 135) | -0.0108 | — | -0.038 | 0.079 | N/A (omnibus n.s.) |
| claude-haiku-4-5 | T2→T3 | (135, 369) | -0.0129 | — | -0.044 | 0.115 | N/A (omnibus n.s.) |
| claude-haiku-4-5 | T3→T4 | (369, 126) | -0.0052 | — | -0.067 | 0.201 | N/A (omnibus n.s.) |
| claude-haiku-4-5 | T4→T5 | (126, 135) | -0.0284 | — | -0.019 | 0.055 | N/A (omnibus n.s.) |
| claude-haiku-4-5 | T5→T6 | (135, 9) | +0.0275 | — | +0.117 | 0.091 | N/A (omnibus n.s.) |
| claude-haiku-4-5 | T0→T6 | (216, 9) | +0.0075 | — | -0.118 | 0.084 | N/A (omnibus n.s.) |
