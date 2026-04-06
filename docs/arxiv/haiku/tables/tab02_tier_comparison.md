# Table 2: Tier Pairwise Comparison

*Statistical workflow: Kruskal-Wallis omnibus test, then pairwise Mann-Whitney U with Holm-Bonferroni correction (step-down)*

**Omnibus Test Results (Kruskal-Wallis):**
- claude-haiku-4-5: H(6)=119.01, p=0.0000 ✓ (proceed to pairwise), power=1.000

| Model | Transition | N (T1, T2) | Pass Rate Δ | p-value | Cliff's δ | Power | Significant? |
|-------|------------|------------|-------------|---------|-----------|-------|--------------|
| claude-haiku-4-5 | T0→T1 | (216, 90) | +0.0315 | 1.0000 | +0.031 | 0.069 | No |
| claude-haiku-4-5 | T1→T2 | (90, 135) | +0.0111 | 1.0000 | +0.011 | 0.054 | No |
| claude-haiku-4-5 | T2→T3 | (135, 369) | -0.2190 | 0.0000 | -0.219 | 0.965 | Yes |
| claude-haiku-4-5 | T3→T4 | (369, 126) | -0.1160 | 0.0577 | -0.116 | 0.495 | No |
| claude-haiku-4-5 | T4→T5 | (126, 135) | -0.0132 | 1.0000 | -0.013 | 0.050 | No |
| claude-haiku-4-5 | T5→T6 | (135, 9) | +0.0370 | 1.0000 | +0.037 | 0.054 | No |
| claude-haiku-4-5 | T0→T6 | (216, 9) | -0.2685 | 0.0176 | -0.269 | 0.267 | Yes |