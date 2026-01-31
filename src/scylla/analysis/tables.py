"""Statistical table generation.

Generates markdown and LaTeX tables for the paper.

Python Justification: Uses pandas for table formatting and data manipulation.
"""

from __future__ import annotations

import pandas as pd

from scylla.analysis.figures import derive_tier_order
from scylla.analysis.stats import (
    bonferroni_correction,
    bootstrap_ci,
    cliffs_delta,
    compute_consistency,
    krippendorff_alpha,
    mann_whitney_u,
    pearson_correlation,
    spearman_correlation,
)


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
            cop = mean_cost / pr_mean if pr_mean > 0 else float("inf")

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

    Applies Bonferroni correction for (n-1) consecutive tier comparisons + 1 overall.

    Args:
        runs_df: Runs DataFrame

    Returns:
        Tuple of (markdown_table, latex_table)

    """
    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)
    n_tests = len(tier_order)  # (n-1) consecutive + 1 overall comparison

    # Compute pairwise comparisons
    rows = []
    for model in sorted(runs_df["agent_model"].unique()):
        model_runs = runs_df[runs_df["agent_model"] == model]

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            tier1_data = model_runs[model_runs["tier"] == tier1]
            tier2_data = model_runs[model_runs["tier"] == tier2]

            if len(tier1_data) == 0 or len(tier2_data) == 0:
                continue

            # Pass rate delta
            pr1 = tier1_data["passed"].mean()
            pr2 = tier2_data["passed"].mean()
            pr_delta = pr2 - pr1

            # Mann-Whitney U test with Bonferroni correction
            _, pvalue_raw = mann_whitney_u(
                tier1_data["passed"].astype(int),
                tier2_data["passed"].astype(int),
            )
            pvalue = bonferroni_correction(pvalue_raw, n_tests)

            # Effect size (Cliff's delta)
            delta = cliffs_delta(
                tier2_data["passed"].astype(int),
                tier1_data["passed"].astype(int),
            )

            rows.append(
                {
                    "Model": model,
                    "Transition": f"{tier1}→{tier2}",
                    "Pass Rate Δ": pr_delta,
                    "p-value": pvalue,
                    "Cliff's δ": delta,
                    "Significant": "Yes" if pvalue < 0.05 else "No",
                }
            )

        # Add overall first→last tier comparison
        first_tier = tier_order[0]
        last_tier = tier_order[-1]
        first_data = model_runs[model_runs["tier"] == first_tier]
        last_data = model_runs[model_runs["tier"] == last_tier]

        if len(first_data) > 0 and len(last_data) > 0:
            pr_first = first_data["passed"].mean()
            pr_last = last_data["passed"].mean()
            pr_delta = pr_last - pr_first

            _, pvalue_raw = mann_whitney_u(
                first_data["passed"].astype(int),
                last_data["passed"].astype(int),
            )
            pvalue = bonferroni_correction(pvalue_raw, n_tests)

            delta = cliffs_delta(
                last_data["passed"].astype(int),
                first_data["passed"].astype(int),
            )

            rows.append(
                {
                    "Model": model,
                    "Transition": f"{first_tier}→{last_tier}",
                    "Pass Rate Δ": pr_delta,
                    "p-value": pvalue,
                    "Cliff's δ": delta,
                    "Significant": "Yes" if pvalue < 0.05 else "No",
                }
            )

    df = pd.DataFrame(rows)

    # Markdown table
    md_lines = [
        "# Table 2: Tier Pairwise Comparison",
        "",
        "*p-values adjusted using Bonferroni correction (n=7 tests per model)*",
        "",
    ]
    md_lines.append("| Model | Transition | Pass Rate Δ | p-value | Cliff's δ | Significant? |")
    md_lines.append("|-------|------------|-------------|---------|-----------|--------------|")

    for _, row in df.iterrows():
        cliffs_delta_val = row["Cliff's δ"]
        md_lines.append(
            f"| {row['Model']} | {row['Transition']} | {row['Pass Rate Δ']:+.4f} | "
            f"{row['p-value']:.4f} | {cliffs_delta_val:+.3f} | {row['Significant']} |"
        )

    markdown = "\n".join(md_lines)

    # LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Tier Pairwise Comparison}",
        r"\label{tab:tier_comparison}",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Model & Transition & Pass Rate $\Delta$ & p-value & "
        r"Cliff's $\delta$ & Significant? \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        sig_mark = r"\checkmark" if row["Significant"] == "Yes" else ""
        cliffs_delta_val = row["Cliff's δ"]
        latex_lines.append(
            f"{row['Model']} & {row['Transition']} & {row['Pass Rate Δ']:+.4f} & "
            f"{row['p-value']:.4f} & {cliffs_delta_val:+.3f} & {sig_mark} \\\\"
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

    Args:
        criteria_df: Criteria DataFrame
        runs_df: Runs DataFrame for model filtering
        criteria_weights: Optional criteria weights dict. Falls back to hardcoded defaults.

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

    # Cross-model comparison (Mann-Whitney U tests with Bonferroni correction)
    # 5 criteria comparisons
    n_tests = len(criteria_weights)

    if len(df["Model"].unique()) == 2:
        models = sorted(df["Model"].unique())
        model1, model2 = models[0], models[1]

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
                pvalue = bonferroni_correction(pvalue_raw, n_tests)
                winner = model1 if m1_numeric.mean() > m2_numeric.mean() else model2

                # Add to dataframe
                df.loc[(df["Model"] == model1) & (df["Criterion"] == criterion), "p-value"] = pvalue
                df.loc[(df["Model"] == model1) & (df["Criterion"] == criterion), "Winner"] = winner

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

    Applies Bonferroni correction for all pairwise model comparisons.
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
    n_tests_per_pair = 2  # pass rate + mean score per pair
    n_total_tests = n_tests_per_pair * len(model_pairs)

    # For backward compatibility, if exactly 2 models, use original n_tests
    n_tests = 2 if len(models) == 2 else n_total_tests

    # Build comparison table for all pairs
    all_metrics = []

    for model1, model2 in model_pairs:
        m1_data = runs_df[runs_df["agent_model"] == model1]
        m2_data = runs_df[runs_df["agent_model"] == model2]

        # Pass rate
        pr1, pr2 = m1_data["passed"].mean(), m2_data["passed"].mean()
        _, pr_pvalue_raw = mann_whitney_u(
            m1_data["passed"].astype(int), m2_data["passed"].astype(int)
        )
        pr_pvalue = bonferroni_correction(pr_pvalue_raw, n_tests)

        all_metrics.append(
            {
                "Pair": f"{model1} vs {model2}",
                "Metric": "Overall Pass Rate",
                model1: pr1,
                model2: pr2,
                "Δ": pr1 - pr2,
                "p-value": pr_pvalue,
            }
        )

        # Mean score
        ms1, ms2 = m1_data["score"].mean(), m2_data["score"].mean()
        _, ms_pvalue_raw = mann_whitney_u(m1_data["score"], m2_data["score"])
        ms_pvalue = bonferroni_correction(ms_pvalue_raw, n_tests)

        all_metrics.append(
            {
                "Pair": f"{model1} vs {model2}",
                "Metric": "Mean Score",
                model1: ms1,
                model2: ms2,
                "Δ": ms1 - ms2,
                "p-value": ms_pvalue,
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
        cop1 = (
            m1_data.groupby("tier")["cost_usd"].mean() / m1_data.groupby("tier")["passed"].mean()
        ).min()
        cop2 = (
            m2_data.groupby("tier")["cost_usd"].mean() / m2_data.groupby("tier")["passed"].mean()
        ).min()
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


# Export all table generators
__all__ = [
    "table01_tier_summary",
    "table02_tier_comparison",
    "table03_judge_agreement",
    "table04_criteria_performance",
    "table05_cost_analysis",
    "table06_model_comparison",
    "table07_subtest_detail",
]
