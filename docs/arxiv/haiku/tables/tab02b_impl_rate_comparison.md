# Table 2b: Impl-Rate Tier Pairwise Comparison

*Statistical workflow: Kruskal-Wallis omnibus test, then pairwise Mann-Whitney U with Holm-Bonferroni correction (step-down)*

**Omnibus Test Results (Kruskal-Wallis):**
- haiku: H(6)=18.97, p=0.0042 ✓ (proceed to pairwise)

| Model | Transition | N (T1, T2) | Impl-Rate Δ | p-value | Cliff's δ | Significant? |
|-------|------------|------------|-------------|---------|-----------|--------------|
| haiku | T0→T1 | (117, 83) | +0.1021 | 0.5205 | +0.120 | No |
| haiku | T1→T2 | (83, 130) | +0.0499 | 1.0000 | +0.010 | No |
| haiku | T2→T3 | (130, 122) | -0.0399 | 1.0000 | +0.015 | No |
| haiku | T3→T4 | (122, 123) | +0.0771 | 0.3491 | +0.134 | No |
| haiku | T4→T5 | (123, 30) | -0.1749 | 0.0221 | -0.380 | Yes |
| haiku | T5→T6 | (30, 15) | +0.1906 | 0.3491 | +0.367 | No |
| haiku | T0→T6 | (117, 15) | +0.2049 | 0.5205 | +0.240 | No |
