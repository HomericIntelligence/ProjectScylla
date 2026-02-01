"""Statistical table generation.

Generates markdown and LaTeX tables for the paper.

Python Justification: Uses pandas for table formatting and data manipulation.
"""

from __future__ import annotations

import pandas as pd
from scipy import stats as scipy_stats

from scylla.analysis.figures import derive_tier_order
from scylla.analysis.stats import (
    bootstrap_ci,
    cliffs_delta,
    compute_consistency,
    compute_cop,
    holm_bonferroni_correction,
    krippendorff_alpha,
    kruskal_wallis,
    mann_whitney_u,
    pearson_correlation,
    shapiro_wilk,
    spearman_correlation,
)

# Statistical significance threshold
ALPHA = 0.05


def table01_tier_summary(runs_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 1: Tier Summary.

    Args:
        runs_df: Runs DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    # Compute statistics per (agent_model, tier)
    rows = []
    for model in sorted(runs_df["agent_model"].unique()):
        for tier in tier_order:
            subset = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]
            if len(subset) == 0:
                continue

            # Pass rate with 95% CI
            passed = subset["passed"].astype(int)
            pr_mean, pr_low, pr_high = bootstrap_ci(passed)

            # Score statistics
            score_mean = subset["score"].mean()
            score_std = subset["score"].std()
            score_median = subset["score"].median()

            # Consistency
            consistency = compute_consistency(score_mean, score_std)

            # Cost-of-Pass
            mean_cost = subset["cost_usd"].mean()
            cop = compute_cop(mean_cost, pr_mean)

            # Count subtests
            n_subtests = subset["subtest"].nunique()

            rows.append(
                {
                    "Model": model,
                    "Tier": tier,
                    "Subtests": n_subtests,
                    "Pass Rate": pr_mean,
                    "PR 95% CI Low": pr_low,
                    "PR 95% CI High": pr_high,
                    "Mean Score": score_mean,
                    "Score StdDev": score_std,
                    "Median Score": score_median,
                    "Consistency": consistency,
                    "CoP": cop if cop != float("inf") else None,
                }
            )

    df = pd.DataFrame(rows)

    # Format markdown table
    md_lines = ["# Table 1: Tier Summary", ""]
    md_lines.append(
        "| Model | Tier | Subtests | Pass Rate (95% CI) | Mean Score (±σ) | "
        "Median | Consistency | CoP ($) |"
    )
    md_lines.append(
        "|-------|------|----------|-------------------|-----------------|"
        "--------|-------------|---------|"
    )

    for _, row in df.iterrows():
        ci_str = f"{row['Pass Rate']:.3f} ({row['PR 95% CI Low']:.3f}, {row['PR 95% CI High']:.3f})"
        score_str = f"{row['Mean Score']:.3f} ± {row['Score StdDev']:.3f}"
        cop_str = f"{row['CoP']:.4f}" if row["CoP"] is not None else "∞"

        md_lines.append(
            f"| {row['Model']} | {row['Tier']} | {row['Subtests']} | "
            f"{ci_str} | {score_str} | {row['Median Score']:.3f} | "
            f"{row['Consistency']:.3f} | {cop_str} |"
        )

    markdown = "\n".join(md_lines)

    # Format LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Tier Summary Statistics}",
        r"\label{tab:tier_summary}",
        r"\begin{tabular}{llrccccr}",
        r"\toprule",
        r"Model & Tier & Subtests & Pass Rate (95\% CI) & "
        r"Mean Score ($\pm\sigma$) & Median & Consistency & CoP (\$) \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        ci_str = f"{row['Pass Rate']:.3f} ({row['PR 95% CI Low']:.3f}, {row['PR 95% CI High']:.3f})"
        score_str = f"{row['Mean Score']:.3f} $\\pm$ {row['Score StdDev']:.3f}"
        cop_str = f"{row['CoP']:.4f}" if row["CoP"] is not None else "$\\infty$"

        latex_lines.append(
            f"{row['Model']} & {row['Tier']} & {row['Subtests']} & "
            f"{ci_str} & {score_str} & {row['Median Score']:.3f} & "
            f"{row['Consistency']:.3f} & {cop_str} \\\\"
        )

    latex_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )

    latex = "\n".join(latex_lines)

    return markdown, latex


def table02_tier_comparison(runs_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 2: Tier Pairwise Comparison.

    Uses Kruskal-Wallis omnibus test followed by pairwise Mann-Whitney U tests
    with Holm-Bonferroni correction (step-down, less conservative than Bonferroni).

    Statistical workflow:
    1. Run Kruskal-Wallis omnibus test across all tiers
    2. If omnibus p < ALPHA, proceed to pairwise comparisons
    3. Apply Holm-Bonferroni correction to pairwise p-values

    Args:
        runs_df: Runs DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    import logging

    logger = logging.getLogger(__name__)

    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    # Compute pairwise comparisons
    rows = []
    omnibus_results = []  # Store omnibus test results for table footer

    for model in sorted(runs_df["agent_model"].unique()):
        model_runs = runs_df[runs_df["agent_model"] == model]

        # Step 1: Kruskal-Wallis omnibus test across all tiers
        tier_groups = [
            model_runs[model_runs["tier"] == tier]["passed"].astype(int) for tier in tier_order
        ]
        # Filter out empty groups
        tier_groups = [g for g in tier_groups if len(g) > 0]

        if len(tier_groups) < 2:
            logger.warning(
                f"Model {model}: Insufficient tier groups ({len(tier_groups)}) for omnibus test"
            )
            continue

        h_stat, omnibus_p = kruskal_wallis(*tier_groups)
        omnibus_results.append((model, h_stat, omnibus_p))

        # Step 2: Only proceed to pairwise tests if omnibus is significant
        proceed_to_pairwise = omnibus_p < ALPHA

        # Collect all pairwise raw p-values for Holm-Bonferroni correction
        pairwise_data = []

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            tier1_data = model_runs[model_runs["tier"] == tier1]
            tier2_data = model_runs[model_runs["tier"] == tier2]

            if len(tier1_data) == 0 or len(tier2_data) == 0:
                continue

            # Check for small sample sizes
            n1, n2 = len(tier1_data), len(tier2_data)
            if n1 < 10 or n2 < 10:
                logger.warning(f"Model {model}, {tier1}→{tier2}: Small sample size (N={n1}, {n2})")

            # Pass rate delta
            pr1 = tier1_data["passed"].mean()
            pr2 = tier2_data["passed"].mean()
            pr_delta = pr2 - pr1

            # Mann-Whitney U test (raw p-value)
            _, pvalue_raw = mann_whitney_u(
                tier1_data["passed"].astype(int),
                tier2_data["passed"].astype(int),
            )

            # Effect size (Cliff's delta)
            delta = cliffs_delta(
                tier2_data["passed"].astype(int),
                tier1_data["passed"].astype(int),
            )

            pairwise_data.append(
                {
                    "Model": model,
                    "Transition": f"{tier1}→{tier2}",
                    "N1": n1,
                    "N2": n2,
                    "Pass Rate Δ": pr_delta,
                    "p_raw": pvalue_raw,
                    "Cliff's δ": delta,
                }
            )

        # Add overall first→last tier comparison
        first_tier = tier_order[0]
        last_tier = tier_order[-1]
        first_data = model_runs[model_runs["tier"] == first_tier]
        last_data = model_runs[model_runs["tier"] == last_tier]

        if len(first_data) > 0 and len(last_data) > 0:
            n1, n2 = len(first_data), len(last_data)
            pr_first = first_data["passed"].mean()
            pr_last = last_data["passed"].mean()
            pr_delta = pr_last - pr_first

            _, pvalue_raw = mann_whitney_u(
                first_data["passed"].astype(int),
                last_data["passed"].astype(int),
            )

            delta = cliffs_delta(
                last_data["passed"].astype(int),
                first_data["passed"].astype(int),
            )

            pairwise_data.append(
                {
                    "Model": model,
                    "Transition": f"{first_tier}→{last_tier}",
                    "N1": n1,
                    "N2": n2,
                    "Pass Rate Δ": pr_delta,
                    "p_raw": pvalue_raw,
                    "Cliff's δ": delta,
                }
            )

        # Step 3: Apply Holm-Bonferroni correction to all pairwise p-values for this model
        if proceed_to_pairwise:
            raw_p_values = [d["p_raw"] for d in pairwise_data]
            corrected_p_values = holm_bonferroni_correction(raw_p_values)

            for i, corrected_p in enumerate(corrected_p_values):
                pairwise_data[i]["p-value"] = corrected_p
                pairwise_data[i]["Significant"] = "Yes" if corrected_p < ALPHA else "No"
        else:
            # Omnibus test not significant - don't perform pairwise tests
            for i in range(len(pairwise_data)):
                pairwise_data[i]["p-value"] = None
                pairwise_data[i]["Significant"] = "N/A (omnibus n.s.)"

        rows.extend(pairwise_data)

    df = pd.DataFrame(rows)

    # Markdown table
    md_lines = [
        "# Table 2: Tier Pairwise Comparison",
        "",
        "*Statistical workflow: Kruskal-Wallis omnibus test, then pairwise Mann-Whitney U "
        "with Holm-Bonferroni correction (step-down)*",
        "",
    ]

    # Add omnibus results to header
    md_lines.append("**Omnibus Test Results (Kruskal-Wallis):**")
    for model, h_stat, omnibus_p in omnibus_results:
        sig_str = "✓ (proceed to pairwise)" if omnibus_p < ALPHA else "✗ (skip pairwise)"
        md_lines.append(f"- {model}: H={h_stat:.2f}, p={omnibus_p:.4f} {sig_str}")
    md_lines.append("")

    md_lines.append(
        "| Model | Transition | N (T1, T2) | Pass Rate Δ | p-value | Cliff's δ | Significant? |"
    )
    md_lines.append(
        "|-------|------------|------------|-------------|---------|-----------|--------------|"
    )

    for _, row in df.iterrows():
        cliffs_delta_val = row["Cliff's δ"]
        n_str = f"({row['N1']}, {row['N2']})"
        pval_str = f"{row['p-value']:.4f}" if row["p-value"] is not None else "—"

        md_lines.append(
            f"| {row['Model']} | {row['Transition']} | {n_str} | {row['Pass Rate Δ']:+.4f} | "
            f"{pval_str} | {cliffs_delta_val:+.3f} | {row['Significant']} |"
        )

    markdown = "\n".join(md_lines)

    # LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Tier Pairwise Comparison}",
        r"\label{tab:tier_comparison}",
        r"\begin{tabular}{llrrrrl}",
        r"\toprule",
        r"Model & Transition & N (T1, T2) & Pass Rate $\Delta$ & p-value & "
        r"Cliff's $\delta$ & Significant? \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        sig_mark = r"\checkmark" if row["Significant"] == "Yes" else ""
        cliffs_delta_val = row["Cliff's δ"]
        n_str = f"({row['N1']}, {row['N2']})"
        pval_str = f"{row['p-value']:.4f}" if row["p-value"] is not None else "---"

        latex_lines.append(
            f"{row['Model']} & {row['Transition']} & {n_str} & {row['Pass Rate Δ']:+.4f} & "
            f"{pval_str} & {cliffs_delta_val:+.3f} & {sig_mark} \\\\"
        )

    latex_lines.extend(
        [
            r"\midrule",
            r"\multicolumn{7}{l}{\textbf{Omnibus Test (Kruskal-Wallis):}} \\",
        ]
    )

    for model, h_stat, omnibus_p in omnibus_results:
        sig_str = rf"$p < {ALPHA}$" if omnibus_p < ALPHA else rf"$p \geq {ALPHA}$ (n.s.)"
        latex_lines.append(
            rf"\multicolumn{{7}}{{l}}{{{model}: $H={h_stat:.2f}$, "
            rf"$p={omnibus_p:.4f}$ {sig_str}}} \\"
        )

    latex_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )

    latex = "\n".join(latex_lines)

    return markdown, latex


def table02b_impl_rate_comparison(runs_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 2b: Impl-Rate Tier Pairwise Comparison.

    Uses Kruskal-Wallis omnibus test followed by pairwise Mann-Whitney U tests
    with Holm-Bonferroni correction (step-down, less conservative than Bonferroni).

    Analogous to table02 but for Implementation Rate instead of Pass-Rate.

    Statistical workflow:
    1. Run Kruskal-Wallis omnibus test across all tiers
    2. If omnibus p < ALPHA, proceed to pairwise comparisons
    3. Apply Holm-Bonferroni correction to pairwise p-values

    Args:
        runs_df: Runs DataFrame (must include impl_rate column)

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    import logging

    logger = logging.getLogger(__name__)

    # Check if impl_rate column exists
    if "impl_rate" not in runs_df.columns:
        logger.error("impl_rate column not found in runs_df")
        return "Error: impl_rate column not found", "Error: impl_rate column not found"

    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    # Compute pairwise comparisons
    rows = []
    omnibus_results = []  # Store omnibus test results for table footer

    for model in sorted(runs_df["agent_model"].unique()):
        model_runs = runs_df[runs_df["agent_model"] == model]

        # Step 1: Kruskal-Wallis omnibus test across all tiers
        tier_groups = [
            model_runs[model_runs["tier"] == tier]["impl_rate"].dropna() for tier in tier_order
        ]
        # Filter out empty groups
        tier_groups = [g for g in tier_groups if len(g) > 0]

        if len(tier_groups) < 2:
            logger.warning(
                f"Model {model}: Insufficient tier groups ({len(tier_groups)}) for omnibus test"
            )
            continue

        h_stat, omnibus_p = kruskal_wallis(*tier_groups)
        omnibus_results.append((model, h_stat, omnibus_p))

        # Step 2: Only proceed to pairwise tests if omnibus is significant
        proceed_to_pairwise = omnibus_p < ALPHA

        # Collect all pairwise raw p-values for Holm-Bonferroni correction
        pairwise_data = []

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            tier1_data = model_runs[model_runs["tier"] == tier1]
            tier2_data = model_runs[model_runs["tier"] == tier2]

            if len(tier1_data) == 0 or len(tier2_data) == 0:
                continue

            # Check for small sample sizes
            n1, n2 = len(tier1_data), len(tier2_data)
            if n1 < 10 or n2 < 10:
                logger.warning(f"Model {model}, {tier1}→{tier2}: Small sample size (N={n1}, {n2})")

            # Impl-Rate delta
            ir1 = tier1_data["impl_rate"].mean()
            ir2 = tier2_data["impl_rate"].mean()
            ir_delta = ir2 - ir1

            # Mann-Whitney U test (raw p-value)
            _, pvalue_raw = mann_whitney_u(
                tier1_data["impl_rate"].dropna(),
                tier2_data["impl_rate"].dropna(),
            )

            # Effect size (Cliff's delta)
            delta = cliffs_delta(
                tier2_data["impl_rate"].dropna(),
                tier1_data["impl_rate"].dropna(),
            )

            pairwise_data.append(
                {
                    "Model": model,
                    "Transition": f"{tier1}→{tier2}",
                    "N1": n1,
                    "N2": n2,
                    "Impl-Rate Δ": ir_delta,
                    "p_raw": pvalue_raw,
                    "Cliff's δ": delta,
                }
            )

        # Add overall first→last tier comparison
        first_tier = tier_order[0]
        last_tier = tier_order[-1]
        first_data = model_runs[model_runs["tier"] == first_tier]
        last_data = model_runs[model_runs["tier"] == last_tier]

        if len(first_data) > 0 and len(last_data) > 0:
            ir_first = first_data["impl_rate"].mean()
            ir_last = last_data["impl_rate"].mean()
            ir_delta_overall = ir_last - ir_first

            _, pvalue_raw_overall = mann_whitney_u(
                first_data["impl_rate"].dropna(),
                last_data["impl_rate"].dropna(),
            )

            delta_overall = cliffs_delta(
                last_data["impl_rate"].dropna(),
                first_data["impl_rate"].dropna(),
            )

            pairwise_data.append(
                {
                    "Model": model,
                    "Transition": f"{first_tier}→{last_tier} (Overall)",
                    "N1": len(first_data),
                    "N2": len(last_data),
                    "Impl-Rate Δ": ir_delta_overall,
                    "p_raw": pvalue_raw_overall,
                    "Cliff's δ": delta_overall,
                }
            )

        # Step 3: Apply Holm-Bonferroni correction to all pairwise p-values for this model
        if proceed_to_pairwise:
            raw_p_values = [d["p_raw"] for d in pairwise_data]
            corrected_p_values = holm_bonferroni_correction(raw_p_values)

            for i, corrected_p in enumerate(corrected_p_values):
                pairwise_data[i]["p-value"] = corrected_p
                pairwise_data[i]["Significant"] = "Yes" if corrected_p < ALPHA else "No"
        else:
            # Omnibus test not significant - don't perform pairwise tests
            for i in range(len(pairwise_data)):
                pairwise_data[i]["p-value"] = None
                pairwise_data[i]["Significant"] = "N/A (omnibus n.s.)"

        rows.extend(pairwise_data)

    # Generate markdown table
    md_lines = [
        "# Table 2b: Impl-Rate Tier Pairwise Comparison",
        "",
        "*Statistical workflow: Kruskal-Wallis omnibus test, then pairwise Mann-Whitney U "
        "with Holm-Bonferroni correction (step-down)*",
        "",
    ]

    # Add omnibus results to header
    md_lines.append("**Omnibus Test Results (Kruskal-Wallis):**")
    for model, h_stat, omnibus_p in omnibus_results:
        sig_str = "✓ (proceed to pairwise)" if omnibus_p < ALPHA else "✗ (skip pairwise)"
        md_lines.append(f"- {model}: H={h_stat:.2f}, p={omnibus_p:.4f} {sig_str}")
    md_lines.append("")

    md_lines.append(
        "| Model | Transition | N (T1, T2) | Impl-Rate Δ | p-value | Cliff's δ | Significant? |"
    )
    md_lines.append(
        "|-------|------------|------------|-------------|---------|-----------|--------------|"
    )

    for row in rows:
        n_str = f"({row['N1']}, {row['N2']})"
        delta_str = f"{row['Impl-Rate Δ']:+.3f}"
        cliffs_delta_val = row["Cliff's δ"]
        cliffs_str = f"{cliffs_delta_val:+.3f}" if cliffs_delta_val is not None else "N/A"

        if row["p-value"] is not None:
            p_str = f"{row['p-value']:.4f}"
        else:
            p_str = "—"

        md_lines.append(
            f"| {row['Model']} | {row['Transition']} | {n_str} | {delta_str} | "
            f"{p_str} | {cliffs_str} | {row['Significant']} |"
        )

    md_lines.extend(
        [
            "",
            "*Statistical notes:*",
            "- *Positive Δ indicates improvement from T1 → T2*",
            "- *Cliff's δ: negligible (<0.11), small (0.11-0.28), "
            "medium (0.28-0.43), large (>0.43)*",
            "- *p-values are Holm-Bonferroni corrected (more powerful than Bonferroni)*",
            "- *N/A (omnibus n.s.) = Kruskal-Wallis omnibus test was not significant, "
            "pairwise tests skipped*",
        ]
    )

    markdown = "\n".join(md_lines)

    # Generate LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Impl-Rate Tier Pairwise Comparison}",
        r"\label{tab:impl_rate_tier_comparison}",
        r"\small",
        r"\begin{tabular}{llccccc}",
        r"\toprule",
        r"Model & Transition & N (T1, T2) & Impl-Rate $\Delta$ & "
        r"p-value & Cliff's $\delta$ & Significant? \\",
        r"\midrule",
    ]

    for row in rows:
        n_str = f"({row['N1']}, {row['N2']})"
        delta_str = f"{row['Impl-Rate Δ']:+.3f}"
        cliffs_delta_val = row["Cliff's δ"]
        cliffs_str = f"{cliffs_delta_val:+.3f}" if cliffs_delta_val is not None else "N/A"

        if row["p-value"] is not None:
            p_str = f"{row['p-value']:.4f}"
        else:
            p_str = r"---"

        sig_str = row["Significant"]
        if sig_str == "Yes":
            sig_str = r"$\checkmark$"
        elif sig_str == "No":
            sig_str = r"$\times$"

        latex_lines.append(
            f"{row['Model']} & {row['Transition']} & {n_str} & {delta_str} & "
            f"{p_str} & {cliffs_str} & {sig_str} \\\\"
        )

    latex_lines.extend(
        [
            r"\midrule",
            r"\multicolumn{7}{l}{\textbf{Omnibus Test (Kruskal-Wallis):}} \\",
        ]
    )

    for model, h_stat, omnibus_p in omnibus_results:
        sig_str = rf"$p < {ALPHA}$" if omnibus_p < ALPHA else rf"$p \geq {ALPHA}$ (n.s.)"
        latex_lines.append(
            rf"\multicolumn{{7}}{{l}}{{{model}: $H={h_stat:.2f}$, "
            rf"$p={omnibus_p:.4f}$ {sig_str}}} \\"
        )

    latex_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\begin{tablenotes}",
            r"\small",
            r"\item Positive $\Delta$ indicates improvement from T1 $\to$ T2.",
            r"\item Cliff's $\delta$: negligible ($<0.11$), small ($0.11$--$0.28$), "
            r"medium ($0.28$--$0.43$), large ($>0.43$).",
            r"\item p-values are Holm-Bonferroni corrected (step-down).",
            r"\end{tablenotes}",
            r"\end{table}",
        ]
    )

    latex = "\n".join(latex_lines)

    return markdown, latex


def table03_judge_agreement(judges_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 3: Judge Agreement.

    Args:
        judges_df: Judges DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    # Pivot judges to wide format
    judge_pivot = judges_df.pivot_table(
        index=["tier", "subtest", "run_number"],
        columns="judge_number",
        values="judge_score",
    ).reset_index()

    # Get dynamic judge column names from pivot result
    # Column names are: ['tier', 'subtest', 'run_number', 1, 2, 3, ...]
    index_cols = ["tier", "subtest", "run_number"]
    judge_cols = [col for col in judge_pivot.columns if col not in index_cols]

    # Rename judge columns to judge_1, judge_2, etc.
    new_cols = index_cols + [f"judge_{i}" for i in range(1, len(judge_cols) + 1)]
    judge_pivot.columns = new_cols
    judge_cols_renamed = [f"judge_{i}" for i in range(1, len(judge_cols) + 1)]

    judge_pivot = judge_pivot.dropna()

    # Pairwise correlations (dynamic based on number of judges)
    # Generate all pairs: (0,1), (0,2), (1,2), etc.
    rows = []
    n_judges = len(judge_cols_renamed)
    for i in range(n_judges):
        for j in range(i + 1, n_judges):
            col_x = judge_cols_renamed[i]
            col_y = judge_cols_renamed[j]

            spearman_r, _ = spearman_correlation(judge_pivot[col_x], judge_pivot[col_y])
            pearson_r, _ = pearson_correlation(judge_pivot[col_x], judge_pivot[col_y])
            mean_delta = (judge_pivot[col_x] - judge_pivot[col_y]).abs().mean()

            rows.append(
                {
                    "Judge Pair": f"Judge {i+1} – Judge {j+1}",
                    "Spearman ρ": spearman_r,
                    "Pearson r": pearson_r,
                    "Mean |Δ Score|": mean_delta,
                }
            )

    # Krippendorff's alpha (all judges)
    ratings_matrix = judge_pivot[judge_cols_renamed].values.T
    alpha = krippendorff_alpha(ratings_matrix, level="interval")

    rows.append(
        {
            "Judge Pair": "All Judges (Overall)",
            "Spearman ρ": None,
            "Pearson r": None,
            "Mean |Δ Score|": None,
        }
    )

    df = pd.DataFrame(rows)

    # Markdown
    md_lines = ["# Table 3: Judge Agreement", ""]
    md_lines.append("| Judge Pair | Spearman ρ | Pearson r | Mean |Δ Score| |")
    md_lines.append("|------------|------------|-----------|---------------|")

    for _, row in df.iterrows():
        if row["Spearman ρ"] is not None:
            md_lines.append(
                f"| {row['Judge Pair']} | {row['Spearman ρ']:.3f} | "
                f"{row['Pearson r']:.3f} | {row['Mean |Δ Score|']:.4f} |"
            )
        else:
            md_lines.append(f"| {row['Judge Pair']} | — | — | — |")

    md_lines.append(f"\n**Krippendorff's α** (interval): {alpha:.3f}")

    markdown = "\n".join(md_lines)

    # LaTeX
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Judge Agreement Metrics}",
        r"\label{tab:judge_agreement}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Judge Pair & Spearman $\rho$ & Pearson $r$ & " r"Mean $|\Delta \text{Score}|$ \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        if row["Spearman ρ"] is not None:
            latex_lines.append(
                f"{row['Judge Pair']} & {row['Spearman ρ']:.3f} & "
                f"{row['Pearson r']:.3f} & {row['Mean |Δ Score|']:.4f} \\\\"
            )
        else:
            latex_lines.append(f"{row['Judge Pair']} & — & — & — \\\\")

    latex_lines.extend(
        [
            r"\midrule",
            rf"\multicolumn{{4}}{{l}}{{Krippendorff's $\alpha$ (interval): {alpha:.3f}}} \\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )

    latex = "\n".join(latex_lines)

    return markdown, latex


def table04_criteria_performance(
    criteria_df: pd.DataFrame,
    runs_df: pd.DataFrame,
    criteria_weights: dict[str, float] | None = None,
) -> tuple[str, str]:
    """Generate Table 4: Per-Criteria Performance.

    Uses Mann-Whitney U tests with Holm-Bonferroni correction for cross-model
    comparison of criteria scores.

    Args:
        criteria_df: Criteria DataFrame
        runs_df: Runs DataFrame for model filtering
        criteria_weights: Optional criteria weights dict. Derived from data if not provided.

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    # Use provided weights or derive from data
    if criteria_weights is None:
        # Derive criteria and uniform weights from the actual data
        unique_criteria = sorted(criteria_df["criterion"].unique())
        n = len(unique_criteria)
        criteria_weights = {c: 1.0 / n for c in unique_criteria} if n > 0 else {}

    # Aggregate by (agent_model, criterion)
    criterion_stats = []
    for model in sorted(criteria_df["agent_model"].unique()):
        for criterion in criteria_weights.keys():
            subset = criteria_df[
                (criteria_df["agent_model"] == model) & (criteria_df["criterion"] == criterion)
            ]
            if len(subset) == 0:
                continue

            # Filter to numeric scores only
            numeric_scores = pd.to_numeric(subset["criterion_score"], errors="coerce")
            numeric_scores = numeric_scores.dropna()

            if len(numeric_scores) == 0:
                continue

            mean_score = numeric_scores.mean()
            std_score = numeric_scores.std()

            criterion_stats.append(
                {
                    "Model": model,
                    "Criterion": criterion,
                    "Weight": criteria_weights[criterion],
                    "Mean Score": mean_score,
                    "Std Dev": std_score,
                }
            )

    df = pd.DataFrame(criterion_stats)

    # Cross-model comparison (Mann-Whitney U tests with Holm-Bonferroni correction)
    # Collect all raw p-values first, then apply correction
    if len(df["Model"].unique()) == 2:
        models = sorted(df["Model"].unique())
        model1, model2 = models[0], models[1]

        raw_p_values = []
        test_metadata = []

        for criterion in criteria_weights.keys():
            m1_data = criteria_df[
                (criteria_df["agent_model"] == model1) & (criteria_df["criterion"] == criterion)
            ]["criterion_score"]
            m2_data = criteria_df[
                (criteria_df["agent_model"] == model2) & (criteria_df["criterion"] == criterion)
            ]["criterion_score"]

            # Filter to numeric
            m1_numeric = pd.to_numeric(m1_data, errors="coerce").dropna()
            m2_numeric = pd.to_numeric(m2_data, errors="coerce").dropna()

            if len(m1_numeric) > 0 and len(m2_numeric) > 0:
                _, pvalue_raw = mann_whitney_u(m1_numeric, m2_numeric)
                winner = model1 if m1_numeric.mean() > m2_numeric.mean() else model2

                raw_p_values.append(pvalue_raw)
                test_metadata.append({"criterion": criterion, "winner": winner})

        # Apply Holm-Bonferroni correction to all raw p-values
        if raw_p_values:
            corrected_p_values = holm_bonferroni_correction(raw_p_values)

            for i, metadata in enumerate(test_metadata):
                df.loc[
                    (df["Model"] == model1) & (df["Criterion"] == metadata["criterion"]), "p-value"
                ] = corrected_p_values[i]
                df.loc[
                    (df["Model"] == model1) & (df["Criterion"] == metadata["criterion"]), "Winner"
                ] = metadata["winner"]

    # Get models dynamically
    models = sorted(df["Model"].unique())

    # Markdown table
    md_lines = ["# Table 4: Per-Criteria Performance", ""]

    # Build header dynamically
    model_headers = " | ".join([f"{model} Mean (±σ)" for model in models])
    md_lines.append(f"| Criterion | Weight | {model_headers} | p-value | Winner |")

    separator = "|" + "|".join(["-" * 10 for _ in range(3 + len(models))]) + "|"
    md_lines.append(separator)

    for criterion in criteria_weights.keys():
        criterion_rows = df[df["Criterion"] == criterion]
        if len(criterion_rows) == 0:
            continue

        # Build model columns dynamically
        model_strs = []
        for model in models:
            model_row = criterion_rows[criterion_rows["Model"] == model]
            if len(model_row) > 0:
                model_strs.append(
                    f"{model_row['Mean Score'].iloc[0]:.3f} ± {model_row['Std Dev'].iloc[0]:.3f}"
                )
            else:
                model_strs.append("—")

        # Get p-value and winner from first model row (they're identical across models)
        first_model_row = criterion_rows[criterion_rows["Model"] == models[0]]
        pvalue_str = (
            f"{first_model_row['p-value'].iloc[0]:.4f}"
            if len(first_model_row) > 0 and "p-value" in first_model_row.columns
            else "—"
        )
        winner_str = (
            first_model_row["Winner"].iloc[0]
            if len(first_model_row) > 0 and "Winner" in first_model_row.columns
            else "—"
        )

        model_cols = " | ".join(model_strs)
        md_lines.append(
            f"| {criterion} | {criteria_weights[criterion]:.2f} | "
            f"{model_cols} | {pvalue_str} | {winner_str} |"
        )

    markdown = "\n".join(md_lines)

    # LaTeX table
    # Build column format dynamically:
    # l (criterion) r (weight) + l for each model + l (pvalue) + l (winner)
    col_format = "lr" + "l" * len(models) + "ll"

    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Per-Criteria Performance Comparison}",
        r"\label{tab:criteria_performance}",
        rf"\begin{{tabular}}{{{col_format}}}",
        r"\toprule",
    ]

    # Build header dynamically
    model_headers = " & ".join([f"{model} Mean ($\\pm\\sigma$)" for model in models])
    latex_lines.append(rf"Criterion & Weight & {model_headers} & p-value & Winner \\")
    latex_lines.append(r"\midrule")

    for criterion in criteria_weights.keys():
        criterion_rows = df[df["Criterion"] == criterion]
        if len(criterion_rows) == 0:
            continue

        # Build model columns dynamically
        model_strs = []
        for model in models:
            model_row = criterion_rows[criterion_rows["Model"] == model]
            if len(model_row) > 0:
                mean_score = model_row["Mean Score"].iloc[0]
                std_dev = model_row["Std Dev"].iloc[0]
                model_strs.append(f"{mean_score:.3f} $\\pm$ {std_dev:.3f}")
            else:
                model_strs.append("---")

        # Get p-value and winner from first model row
        first_model_row = criterion_rows[criterion_rows["Model"] == models[0]]
        pvalue_str = (
            f"{first_model_row['p-value'].iloc[0]:.4f}"
            if len(first_model_row) > 0 and "p-value" in first_model_row.columns
            else "---"
        )
        winner_str = (
            first_model_row["Winner"].iloc[0]
            if len(first_model_row) > 0 and "Winner" in first_model_row.columns
            else "---"
        )

        model_cols = " & ".join(model_strs)
        latex_lines.append(
            f"{criterion} & {criteria_weights[criterion]:.2f} & "
            f"{model_cols} & {pvalue_str} & {winner_str} \\\\"
        )

    latex_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])

    latex = "\n".join(latex_lines)

    return markdown, latex


def table05_cost_analysis(runs_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 5: Cost Analysis.

    Args:
        runs_df: Runs DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    # Compute cost statistics per (agent_model, tier)
    rows = []
    for model in sorted(runs_df["agent_model"].unique()):
        for tier in tier_order:
            subset = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]
            if len(subset) == 0:
                continue

            mean_cost = subset["cost_usd"].mean()
            total_cost = subset["cost_usd"].sum()

            # CoP
            pass_rate = subset["passed"].mean()
            cop = mean_cost / pass_rate if pass_rate > 0 else float("inf")

            # Token breakdown
            input_tokens = subset["input_tokens"].mean()
            output_tokens = subset["output_tokens"].mean()
            cache_read = subset["cache_read_tokens"].mean()
            cache_create = subset["cache_creation_tokens"].mean()

            rows.append(
                {
                    "Model": model,
                    "Tier": tier,
                    "Mean Cost": mean_cost,
                    "Total Cost": total_cost,
                    "CoP": cop if cop != float("inf") else None,
                    "Input Tokens": input_tokens,
                    "Output Tokens": output_tokens,
                    "Cache Read": cache_read,
                    "Cache Create": cache_create,
                }
            )

    # Add totals row per model
    for model in sorted(runs_df["agent_model"].unique()):
        model_subset = runs_df[runs_df["agent_model"] == model]
        rows.append(
            {
                "Model": model,
                "Tier": "**Total**",
                "Mean Cost": model_subset["cost_usd"].mean(),
                "Total Cost": model_subset["cost_usd"].sum(),
                "CoP": None,
                "Input Tokens": model_subset["input_tokens"].sum(),
                "Output Tokens": model_subset["output_tokens"].sum(),
                "Cache Read": model_subset["cache_read_tokens"].sum(),
                "Cache Create": model_subset["cache_creation_tokens"].sum(),
            }
        )

    df = pd.DataFrame(rows)

    # Markdown table
    md_lines = ["# Table 5: Cost Analysis", ""]
    md_lines.append(
        "| Model | Tier | Mean Cost ($) | Total Cost ($) | CoP ($) | Input Tokens | "
        "Output Tokens | Cache Read | Cache Create |"
    )
    md_lines.append(
        "|-------|------|---------------|----------------|---------|--------------|"
        "---------------|------------|--------------|"
    )

    for _, row in df.iterrows():
        cop_str = (
            f"{row['CoP']:.4f}"
            if row["CoP"] is not None
            else "∞"
            if row["Tier"] != "**Total**"
            else "—"
        )

        md_lines.append(
            f"| {row['Model']} | {row['Tier']} | {row['Mean Cost']:.4f} | "
            f"{row['Total Cost']:.2f} | {cop_str} | "
            f"{row['Input Tokens']:.0f} | {row['Output Tokens']:.0f} | "
            f"{row['Cache Read']:.0f} | {row['Cache Create']:.0f} |"
        )

    markdown = "\n".join(md_lines)

    # LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Cost Analysis by Tier}",
        r"\label{tab:cost_analysis}",
        r"\small",
        r"\begin{tabular}{llrrrrrrrr}",
        r"\toprule",
        r"Model & Tier & Mean Cost (\$) & Total Cost (\$) & CoP (\$) & Input & "
        r"Output & Cache Read & Cache Create \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        cop_str = (
            f"{row['CoP']:.4f}"
            if row["CoP"] is not None
            else "$\\infty$"
            if row["Tier"] != "**Total**"
            else "---"
        )

        latex_lines.append(
            f"{row['Model']} & {row['Tier']} & {row['Mean Cost']:.4f} & "
            f"{row['Total Cost']:.2f} & {cop_str} & "
            f"{row['Input Tokens']:.0f} & {row['Output Tokens']:.0f} & "
            f"{row['Cache Read']:.0f} & {row['Cache Create']:.0f} \\\\"
        )

    latex_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])

    latex = "\n".join(latex_lines)

    return markdown, latex


def table06_model_comparison(runs_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 6: Model Comparison Summary.

    Applies Holm-Bonferroni correction for all pairwise model comparisons.
    For N models, performs C(N,2) pairwise comparisons, each with 2 tests (pass rate + mean score).

    Args:
        runs_df: Runs DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    from itertools import combinations

    models = sorted(runs_df["agent_model"].unique())

    if len(models) < 2:
        return "# Table 6: Model Comparison\n\nError: Need at least 2 models", ""

    # Generate all pairwise comparisons
    model_pairs = list(combinations(models, 2))

    # Collect all raw p-values and metadata for Holm-Bonferroni correction
    raw_p_values = []
    test_metadata = []

    for model1, model2 in model_pairs:
        m1_data = runs_df[runs_df["agent_model"] == model1]
        m2_data = runs_df[runs_df["agent_model"] == model2]

        # Pass rate
        pr1, pr2 = m1_data["passed"].mean(), m2_data["passed"].mean()
        _, pr_pvalue_raw = mann_whitney_u(
            m1_data["passed"].astype(int), m2_data["passed"].astype(int)
        )
        raw_p_values.append(pr_pvalue_raw)
        test_metadata.append(
            {
                "pair": (model1, model2),
                "metric": "Overall Pass Rate",
                "model1_val": pr1,
                "model2_val": pr2,
                "delta": pr1 - pr2,
            }
        )

        # Mean score
        ms1, ms2 = m1_data["score"].mean(), m2_data["score"].mean()
        _, ms_pvalue_raw = mann_whitney_u(m1_data["score"], m2_data["score"])
        raw_p_values.append(ms_pvalue_raw)
        test_metadata.append(
            {
                "pair": (model1, model2),
                "metric": "Mean Score",
                "model1_val": ms1,
                "model2_val": ms2,
                "delta": ms1 - ms2,
            }
        )

    # Apply Holm-Bonferroni correction to all raw p-values
    corrected_p_values = holm_bonferroni_correction(raw_p_values)

    # Build comparison table with corrected p-values
    all_metrics = []
    for i, metadata in enumerate(test_metadata):
        model1, model2 = metadata["pair"]
        all_metrics.append(
            {
                "Pair": f"{model1} vs {model2}",
                "Metric": metadata["metric"],
                model1: metadata["model1_val"],
                model2: metadata["model2_val"],
                "Δ": metadata["delta"],
                "p-value": corrected_p_values[i],
            }
        )

        # Mean cost (no p-value)
        mc1, mc2 = m1_data["cost_usd"].mean(), m2_data["cost_usd"].mean()
        all_metrics.append(
            {
                "Pair": f"{model1} vs {model2}",
                "Metric": "Mean Cost ($)",
                model1: mc1,
                model2: mc2,
                "Δ": mc1 - mc2,
                "p-value": None,
            }
        )

        # Frontier CoP
        # Compute CoP per tier, then take minimum (frontier)
        tier_costs_1 = m1_data.groupby("tier")["cost_usd"].mean()
        tier_pass_rates_1 = m1_data.groupby("tier")["passed"].mean()
        tier_cops_1 = pd.Series(
            {
                tier: compute_cop(tier_costs_1[tier], tier_pass_rates_1[tier])
                for tier in tier_costs_1.index
            }
        )
        cop1 = tier_cops_1.min()

        tier_costs_2 = m2_data.groupby("tier")["cost_usd"].mean()
        tier_pass_rates_2 = m2_data.groupby("tier")["passed"].mean()
        tier_cops_2 = pd.Series(
            {
                tier: compute_cop(tier_costs_2[tier], tier_pass_rates_2[tier])
                for tier in tier_costs_2.index
            }
        )
        cop2 = tier_cops_2.min()
        all_metrics.append(
            {
                "Pair": f"{model1} vs {model2}",
                "Metric": "Frontier CoP ($)",
                model1: cop1,
                model2: cop2,
                "Δ": cop1 - cop2,
                "p-value": None,
            }
        )

        # Best tier
        best_tier1 = m1_data.groupby("tier")["passed"].mean().idxmax()
        best_tier2 = m2_data.groupby("tier")["passed"].mean().idxmax()
        all_metrics.append(
            {
                "Pair": f"{model1} vs {model2}",
                "Metric": "Best Tier (Pass Rate)",
                model1: best_tier1,
                model2: best_tier2,
                "Δ": "—",
                "p-value": None,
            }
        )

        # Consistency
        tier_stats1 = m1_data.groupby("tier")["score"].agg(["mean", "std"])
        tier_stats2 = m2_data.groupby("tier")["score"].agg(["mean", "std"])

        consistencies1 = [
            compute_consistency(row["mean"], row["std"]) for _, row in tier_stats1.iterrows()
        ]
        consistencies2 = [
            compute_consistency(row["mean"], row["std"]) for _, row in tier_stats2.iterrows()
        ]

        consistency1 = sum(consistencies1) / len(consistencies1) if consistencies1 else 0.0
        consistency2 = sum(consistencies2) / len(consistencies2) if consistencies2 else 0.0

        all_metrics.append(
            {
                "Pair": f"{model1} vs {model2}",
                "Metric": "Mean Consistency",
                model1: consistency1,
                model2: consistency2,
                "Δ": consistency1 - consistency2,
                "p-value": None,
            }
        )

        # Total tokens
        tt1 = m1_data["total_tokens"].sum()
        tt2 = m2_data["total_tokens"].sum()
        all_metrics.append(
            {
                "Pair": f"{model1} vs {model2}",
                "Metric": "Total Tokens",
                model1: tt1,
                model2: tt2,
                "Δ": tt1 - tt2,
                "p-value": None,
            }
        )

    df = pd.DataFrame(all_metrics)

    # Markdown table
    md_lines = ["# Table 6: Model Comparison Summary", ""]

    # If only 2 models, use original 2-column format
    if len(models) == 2:
        model1, model2 = models[0], models[1]
        md_lines.append(f"| Metric | {model1} | {model2} | Δ | p-value |")
        md_lines.append("|--------|----------|----------|---|---------|")

        for _, row in df.iterrows():
            val1_str = f"{row[model1]:.3f}" if isinstance(row[model1], float) else str(row[model1])
            val2_str = f"{row[model2]:.3f}" if isinstance(row[model2], float) else str(row[model2])
            delta_str = f"{row['Δ']:+.3f}" if isinstance(row["Δ"], float) else str(row["Δ"])
            pval_str = f"{row['p-value']:.4f}" if row["p-value"] is not None else "—"

            md_lines.append(
                f"| {row['Metric']} | {val1_str} | {val2_str} | {delta_str} | {pval_str} |"
            )
    else:
        # For N models, group by pair
        md_lines.append("| Pair | Metric | Model 1 | Model 2 | Δ | p-value |")
        md_lines.append("|------|--------|---------|---------|---|---------|")

        for _, row in df.iterrows():
            # Model names from the pair
            pair_models = row["Pair"].split(" vs ")
            model1, model2 = pair_models[0], pair_models[1]

            val1_str = f"{row[model1]:.3f}" if isinstance(row[model1], float) else str(row[model1])
            val2_str = f"{row[model2]:.3f}" if isinstance(row[model2], float) else str(row[model2])
            delta_str = f"{row['Δ']:+.3f}" if isinstance(row["Δ"], float) else str(row["Δ"])
            pval_str = f"{row['p-value']:.4f}" if row["p-value"] is not None else "—"

            md_lines.append(
                f"| {row['Pair']} | {row['Metric']} | {val1_str} | {val2_str} | "
                f"{delta_str} | {pval_str} |"
            )

    markdown = "\n".join(md_lines)

    # LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Model Comparison Summary}",
        r"\label{tab:model_comparison}",
    ]

    if len(models) == 2:
        model1, model2 = models[0], models[1]
        latex_lines.extend(
            [
                r"\begin{tabular}{lrrrl}",
                r"\toprule",
                f"Metric & {model1} & {model2} & $\\Delta$ & p-value \\\\",
                r"\midrule",
            ]
        )

        for _, row in df.iterrows():
            val1_str = f"{row[model1]:.3f}" if isinstance(row[model1], float) else str(row[model1])
            val2_str = f"{row[model2]:.3f}" if isinstance(row[model2], float) else str(row[model2])
            delta_str = f"{row['Δ']:+.3f}" if isinstance(row["Δ"], float) else str(row["Δ"])
            pval_str = f"{row['p-value']:.4f}" if row["p-value"] is not None else "---"

            latex_lines.append(
                f"{row['Metric']} & {val1_str} & {val2_str} & {delta_str} & {pval_str} \\\\"
            )
    else:
        latex_lines.extend(
            [
                r"\begin{tabular}{llrrrl}",
                r"\toprule",
                "Pair & Metric & Model 1 & Model 2 & $\\Delta$ & p-value \\\\",
                r"\midrule",
            ]
        )

        for _, row in df.iterrows():
            pair_models = row["Pair"].split(" vs ")
            model1, model2 = pair_models[0], pair_models[1]

            val1_str = f"{row[model1]:.3f}" if isinstance(row[model1], float) else str(row[model1])
            val2_str = f"{row[model2]:.3f}" if isinstance(row[model2], float) else str(row[model2])
            delta_str = f"{row['Δ']:+.3f}" if isinstance(row["Δ"], float) else str(row["Δ"])
            pval_str = f"{row['p-value']:.4f}" if row["p-value"] is not None else "---"

            latex_lines.append(
                f"{row['Pair']} & {row['Metric']} & {val1_str} & {val2_str} & "
                f"{delta_str} & {pval_str} \\\\"
            )

    latex_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])

    latex = "\n".join(latex_lines)

    return markdown, latex


def table07_subtest_detail(runs_df: pd.DataFrame, subtests_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 7: Full Subtest Results (Appendix B).

    Args:
        runs_df: Runs DataFrame
        subtests_df: Subtests DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    # Build detailed subtest table
    rows = []
    for model in sorted(runs_df["agent_model"].unique()):
        for tier in tier_order:
            tier_subtests = subtests_df[
                (subtests_df["agent_model"] == model) & (subtests_df["tier"] == tier)
            ].sort_values("subtest")

            for _, subtest_row in tier_subtests.iterrows():
                # Grade distribution as string
                grade_dist = (
                    f"S:{int(subtest_row['grade_S'])} A:{int(subtest_row['grade_A'])} "
                    f"B:{int(subtest_row['grade_B'])} C:{int(subtest_row['grade_C'])} "
                    f"D:{int(subtest_row['grade_D'])} F:{int(subtest_row['grade_F'])}"
                )

                rows.append(
                    {
                        "Model": model,
                        "Tier": tier,
                        "Subtest": subtest_row["subtest"],
                        "Pass Rate": subtest_row["pass_rate"],
                        "Mean Score": subtest_row["mean_score"],
                        "Std Dev": subtest_row["std_score"],
                        "Cost ($)": subtest_row["mean_cost"],
                        "Modal Grade": subtest_row["modal_grade"],
                        "Grade Dist": grade_dist,
                    }
                )

    df = pd.DataFrame(rows)

    # Markdown table (paginated for readability)
    md_lines = ["# Table 7: Full Subtest Results (Appendix B)", ""]
    md_lines.append(
        "| Model | Tier | Subtest | Pass Rate | Mean Score | Std Dev | Cost ($) | "
        "Modal Grade | Grade Distribution |"
    )
    md_lines.append(
        "|-------|------|---------|-----------|------------|---------|----------|"
        "-------------|-------------------|"
    )

    for _, row in df.iterrows():
        md_lines.append(
            f"| {row['Model']} | {row['Tier']} | {row['Subtest']} | "
            f"{row['Pass Rate']:.3f} | {row['Mean Score']:.3f} | {row['Std Dev']:.3f} | "
            f"{row['Cost ($)']:.4f} | {row['Modal Grade']} | {row['Grade Dist']} |"
        )

    markdown = "\n".join(md_lines)

    # LaTeX table (use longtable for multi-page)
    latex_lines = [
        r"\begin{longtable}{llrrrrrll}",
        r"\caption{Full Subtest Results (Appendix B)} \\",
        r"\toprule",
        r"Model & Tier & ST & Pass Rate & Mean Score & Std Dev & Cost (\$) & "
        r"Grade & Distribution \\",
        r"\midrule",
        r"\endfirsthead",
        r"\multicolumn{9}{c}{\textit{Table 7 (continued)}} \\",
        r"\toprule",
        r"Model & Tier & ST & Pass Rate & Mean Score & Std Dev & Cost (\$) & "
        r"Grade & Distribution \\",
        r"\midrule",
        r"\endhead",
        r"\bottomrule",
        r"\endfoot",
    ]

    for _, row in df.iterrows():
        latex_lines.append(
            f"{row['Model']} & {row['Tier']} & {row['Subtest']} & "
            f"{row['Pass Rate']:.3f} & {row['Mean Score']:.3f} & {row['Std Dev']:.3f} & "
            f"{row['Cost ($)']:.4f} & {row['Modal Grade']} & \\tiny {row['Grade Dist']} \\\\"
        )

    latex_lines.append(r"\end{longtable}")

    latex = "\n".join(latex_lines)

    return markdown, latex


def table08_summary_statistics(runs_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 8: Summary Statistics.

    Descriptive statistics for all metrics by model.
    Essential foundation for any paper - shows data characteristics.

    Args:
        runs_df: Runs DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    metrics = {
        "score": "Score",
        "cost_usd": "Cost (USD)",
        "duration_seconds": "Duration (s)",
        "total_tokens": "Total Tokens",
    }

    rows = []
    for model in sorted(runs_df["agent_model"].unique()):
        model_data = runs_df[runs_df["agent_model"] == model]

        for metric_col, metric_name in metrics.items():
            data = model_data[metric_col].dropna()

            if len(data) == 0:
                continue

            # Calculate statistics
            n = len(data)
            mean_val = data.mean()
            median_val = data.median()
            min_val = data.min()
            max_val = data.max()
            q1 = data.quantile(0.25)
            q3 = data.quantile(0.75)
            std_val = data.std()

            # Skewness and kurtosis using scipy
            skew_val = scipy_stats.skew(data)
            kurt_val = scipy_stats.kurtosis(data)

            rows.append(
                {
                    "Model": model,
                    "Metric": metric_name,
                    "N": n,
                    "Mean": mean_val,
                    "Median": median_val,
                    "Min": min_val,
                    "Max": max_val,
                    "Q1": q1,
                    "Q3": q3,
                    "StdDev": std_val,
                    "Skewness": skew_val,
                    "Kurtosis": kurt_val,
                }
            )

    df = pd.DataFrame(rows)

    # Markdown table
    md_lines = ["# Table 8: Summary Statistics", ""]
    md_lines.append(
        "| Model | Metric | N | Mean | Median | Min | Max | Q1 | Q3 | StdDev | Skew | Kurt |"
    )
    md_lines.append(
        "|-------|--------|---|------|--------|-----|-----|----|----|--------|------|------|"
    )

    for _, row in df.iterrows():
        md_lines.append(
            f"| {row['Model']} | {row['Metric']} | {row['N']} | "
            f"{row['Mean']:.4f} | {row['Median']:.4f} | {row['Min']:.4f} | "
            f"{row['Max']:.4f} | {row['Q1']:.4f} | {row['Q3']:.4f} | "
            f"{row['StdDev']:.4f} | {row['Skewness']:.3f} | {row['Kurtosis']:.3f} |"
        )

    markdown = "\n".join(md_lines)

    # LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Summary Statistics by Model and Metric}",
        r"\label{tab:summary_statistics}",
        r"\small",
        r"\begin{tabular}{llrrrrrrrrrrr}",
        r"\toprule",
        r"Model & Metric & N & Mean & Median & Min & Max & Q1 & Q3 & StdDev & Skew & Kurt \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        latex_lines.append(
            f"{row['Model']} & {row['Metric']} & {row['N']} & "
            f"{row['Mean']:.4f} & {row['Median']:.4f} & {row['Min']:.4f} & "
            f"{row['Max']:.4f} & {row['Q1']:.4f} & {row['Q3']:.4f} & "
            f"{row['StdDev']:.4f} & {row['Skewness']:.3f} & {row['Kurtosis']:.3f} \\\\"
        )

    latex_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])

    latex = "\n".join(latex_lines)

    return markdown, latex


def table09_experiment_config(runs_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 9: Experiment Configuration.

    Derived entirely from data - no hardcoded values.
    Documents the experimental setup for reproducibility.

    Args:
        runs_df: Runs DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    rows = []

    # Group by experiment (if experiment column exists, else treat all as one experiment)
    if "experiment" in runs_df.columns:
        experiments = sorted(runs_df["experiment"].unique())
    else:
        experiments = ["default"]
        runs_df = runs_df.copy()
        runs_df["experiment"] = "default"

    for experiment in experiments:
        exp_data = (
            runs_df[runs_df["experiment"] == experiment] if experiment != "default" else runs_df
        )

        # Derive configuration from data
        agent_models = sorted(exp_data["agent_model"].unique())
        tiers = derive_tier_order(exp_data)
        n_tiers = len(tiers)

        # Subtests per tier (count unique subtests in each tier)
        subtests_per_tier = {}
        for tier in tiers:
            tier_data = exp_data[exp_data["tier"] == tier]
            subtests_per_tier[tier] = tier_data["subtest"].nunique()

        # Runs per subtest (mode of run counts across all subtests)
        runs_per_subtest_counts = exp_data.groupby(["tier", "subtest"]).size()
        runs_per_subtest = int(runs_per_subtest_counts.mode().iloc[0])

        # Total runs
        total_runs = len(exp_data)

        # Judge models (if available)
        if "judge_model" in exp_data.columns:
            judge_models = sorted(exp_data["judge_model"].dropna().unique())
            judge_models_str = ", ".join(judge_models)
        else:
            judge_models_str = "N/A"

        # Format subtests/tier as summary
        subtest_summary = f"{min(subtests_per_tier.values())}-{max(subtests_per_tier.values())}"
        if min(subtests_per_tier.values()) == max(subtests_per_tier.values()):
            subtest_summary = str(min(subtests_per_tier.values()))

        rows.append(
            {
                "Experiment": experiment,
                "Agent Models": ", ".join(agent_models),
                "Tiers": n_tiers,
                "Tier IDs": ", ".join(tiers),
                "Subtests/Tier": subtest_summary,
                "Runs/Subtest": runs_per_subtest,
                "Total Runs": total_runs,
                "Judge Models": judge_models_str,
            }
        )

    df = pd.DataFrame(rows)

    # Markdown table
    md_lines = ["# Table 9: Experiment Configuration", ""]
    md_lines.append(
        "| Experiment | Agent Models | Tiers | Tier IDs | Subtests/Tier | "
        "Runs/Subtest | Total Runs | Judge Models |"
    )
    md_lines.append(
        "|------------|--------------|-------|----------|---------------|"
        "--------------|------------|--------------|"
    )

    for _, row in df.iterrows():
        # Truncate long tier IDs for markdown
        tier_ids = row["Tier IDs"]
        if len(tier_ids) > 40:
            tier_ids = tier_ids[:37] + "..."

        md_lines.append(
            f"| {row['Experiment']} | {row['Agent Models']} | {row['Tiers']} | "
            f"{tier_ids} | {row['Subtests/Tier']} | {row['Runs/Subtest']} | "
            f"{row['Total Runs']} | {row['Judge Models']} |"
        )

    markdown = "\n".join(md_lines)

    # LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Experiment Configuration (Data-Derived)}",
        r"\label{tab:experiment_config}",
        r"\small",
        r"\begin{tabular}{llrllrrr}",
        r"\toprule",
        r"Experiment & Models & Tiers & Tier IDs & ST/Tier & Runs/ST & Total & Judges \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        # Truncate tier IDs for LaTeX
        tier_ids = row["Tier IDs"]
        if len(tier_ids) > 30:
            tier_ids = tier_ids[:27] + "..."

        latex_lines.append(
            f"{row['Experiment']} & {row['Agent Models']} & {row['Tiers']} & "
            f"{tier_ids} & {row['Subtests/Tier']} & {row['Runs/Subtest']} & "
            f"{row['Total Runs']} & {row['Judge Models']} \\\\"
        )

    latex_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])

    latex = "\n".join(latex_lines)

    return markdown, latex


def table10_normality_tests(runs_df: pd.DataFrame) -> tuple[str, str]:
    """Generate Table 10: Normality Tests.

    Shapiro-Wilk tests for all metric distributions.
    Justifies use of non-parametric statistical tests.

    Args:
        runs_df: Runs DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(runs_df)
    metrics = {
        "score": "Score",
        "cost_usd": "Cost (USD)",
    }

    rows = []
    for model in sorted(runs_df["agent_model"].unique()):
        for tier in tier_order:
            tier_data = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]

            if len(tier_data) < 3:
                # Shapiro-Wilk requires at least 3 samples
                continue

            for metric_col, metric_name in metrics.items():
                data = tier_data[metric_col].dropna()

                if len(data) < 3:
                    continue

                # Shapiro-Wilk test
                w_stat, p_value = shapiro_wilk(data)

                # Interpret result
                is_normal = "Yes" if p_value > ALPHA else "No"

                rows.append(
                    {
                        "Model": model,
                        "Tier": tier,
                        "Metric": metric_name,
                        "N": len(data),
                        "W": w_stat,
                        "p-value": p_value,
                        "Normal? (α=0.05)": is_normal,
                    }
                )

    df = pd.DataFrame(rows)

    # Markdown table
    md_lines = [
        "# Table 10: Normality Tests (Shapiro-Wilk)",
        "",
        "*Tests null hypothesis that data is normally distributed. "
        f"p > {ALPHA} means cannot reject normality.*",
        "",
    ]
    md_lines.append("| Model | Tier | Metric | N | W | p-value | Normal? (α=0.05) |")
    md_lines.append("|-------|------|--------|---|---|---------|------------------|")

    for _, row in df.iterrows():
        md_lines.append(
            f"| {row['Model']} | {row['Tier']} | {row['Metric']} | {row['N']} | "
            f"{row['W']:.4f} | {row['p-value']:.4f} | {row['Normal? (α=0.05)']} |"
        )

    # Summary statistics
    normal_count = len(df[df["Normal? (α=0.05)"] == "Yes"])
    total_count = len(df)
    md_lines.append(
        f"\n**Summary**: {normal_count}/{total_count} "
        f"({100*normal_count/total_count:.1f}%) distributions pass normality test"
    )

    markdown = "\n".join(md_lines)

    # LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Normality Tests (Shapiro-Wilk)}",
        r"\label{tab:normality_tests}",
        r"\begin{tabular}{llrrrrl}",
        r"\toprule",
        r"Model & Tier & Metric & N & W & p-value & Normal? ($\alpha=0.05$) \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        normal_symbol = r"\checkmark" if row["Normal? (α=0.05)"] == "Yes" else r"$\times$"
        latex_lines.append(
            f"{row['Model']} & {row['Tier']} & {row['Metric']} & {row['N']} & "
            f"{row['W']:.4f} & {row['p-value']:.4f} & {normal_symbol} \\\\"
        )

    latex_lines.extend(
        [
            r"\midrule",
            rf"\multicolumn{{7}}{{l}}{{\textit{{Summary: {normal_count}/{total_count} "
            rf"({100*normal_count/total_count:.1f}\%) pass normality test}}}} \\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )

    latex = "\n".join(latex_lines)

    return markdown, latex


# Export all table generators
__all__ = [
    "table01_tier_summary",
    "table02_tier_comparison",
    "table02b_impl_rate_comparison",
    "table03_judge_agreement",
    "table04_criteria_performance",
    "table05_cost_analysis",
    "table06_model_comparison",
    "table07_subtest_detail",
    "table08_summary_statistics",
    "table09_experiment_config",
    "table10_normality_tests",
]
