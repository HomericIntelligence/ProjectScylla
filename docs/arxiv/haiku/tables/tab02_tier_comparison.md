# Table 2: Tier Pairwise Comparison

*Statistical workflow: Kruskal-Wallis omnibus test, then pairwise Mann-Whitney U with Holm-Bonferroni correction (step-down)*

**Omnibus Test Results (Kruskal-Wallis):**
- haiku: H(6)=27.49, p=0.0001 ✓ (proceed to pairwise)

| Model | Transition | N (T1, T2) | Pass Rate Δ | p-value | Cliff's δ | Significant? |
|-------|------------|------------|-------------|---------|-----------|--------------|
| haiku | T0→T1 | (117, 83) | +0.0939 | 0.4865 | +0.094 | No |
| haiku | T1→T2 | (83, 130) | +0.0958 | 0.3725 | +0.096 | No |
| haiku | T2→T3 | (130, 122) | -0.0685 | 0.4865 | -0.068 | No |
| haiku | T3→T4 | (122, 123) | +0.0507 | 0.4865 | +0.051 | No |
| haiku | T4→T5 | (123, 30) | -0.3130 | 0.0024 | -0.313 | Yes |
| haiku | T5→T6 | (30, 15) | +0.4333 | 0.0243 | +0.433 | Yes |
| haiku | T0→T6 | (117, 15) | +0.2923 | 0.1187 | +0.292 | No |
