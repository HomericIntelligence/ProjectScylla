# Table 2b: Impl-Rate Tier Pairwise Comparison

*Statistical workflow: Kruskal-Wallis omnibus test, then pairwise Mann-Whitney U with Holm-Bonferroni correction (step-down)*

**Omnibus Test Results (Kruskal-Wallis):**
- Sonnet 4.5: H(6)=nan, p=nan ✗ (skip pairwise)

| Model | Transition | N (T1, T2) | Impl-Rate Δ | p-value | Cliff's δ | Significant? |
|-------|------------|------------|-------------|---------|-----------|--------------|
| Sonnet 4.5 | T0→T1 | (1, 1) | -0.002 | — | -1.000 | N/A (omnibus n.s.) |
| Sonnet 4.5 | T1→T2 | (1, 1) | +0.010 | — | +1.000 | N/A (omnibus n.s.) |
| Sonnet 4.5 | T2→T3 | (1, 1) | -0.007 | — | -1.000 | N/A (omnibus n.s.) |
| Sonnet 4.5 | T3→T4 | (1, 1) | -0.037 | — | -1.000 | N/A (omnibus n.s.) |
| Sonnet 4.5 | T4→T5 | (1, 1) | +0.043 | — | +1.000 | N/A (omnibus n.s.) |
| Sonnet 4.5 | T5→T6 | (1, 1) | -0.033 | — | -1.000 | N/A (omnibus n.s.) |
| Sonnet 4.5 | T0→T6 (Overall) | (1, 1) | -0.026 | — | -1.000 | N/A (omnibus n.s.) |

*Statistical notes:*
- *Positive Δ indicates improvement from T1 → T2*
- *Cliff's δ: negligible (<0.11), small (0.11-0.28), medium (0.28-0.43), large (>0.43)*
- *p-values are Holm-Bonferroni corrected (more powerful than Bonferroni)*
- *N/A (omnibus n.s.) = Kruskal-Wallis omnibus test was not significant, pairwise tests skipped*
