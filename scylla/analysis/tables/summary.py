"""Summary statistics tables.

Generates summary tables (Table 1, 5) for tier-level and cost analysis.
"""

from __future__ import annotations

import pandas as pd

from scylla.analysis.config import config
from scylla.analysis.figures import derive_tier_order
from scylla.analysis.stats import (
    bootstrap_ci,
    compute_consistency,
    compute_cop,
)

# Format strings from config
_FMT_RATE = f".{config.precision_rates}f"
_FMT_COST = f".{config.precision_costs}f"
_FMT_PCT = f".{config.precision_percentages}f"


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
        ci_str = (
            f"{row['Pass Rate']:{_FMT_RATE}} "
            f"({row['PR 95% CI Low']:{_FMT_RATE}}, {row['PR 95% CI High']:{_FMT_RATE}})"
        )
        score_str = f"{row['Mean Score']:{_FMT_RATE}} ± {row['Score StdDev']:{_FMT_RATE}}"
        cop_str = f"{row['CoP']:{_FMT_COST}}" if row["CoP"] is not None else "∞"

        md_lines.append(
            f"| {row['Model']} | {row['Tier']} | {row['Subtests']} | "
            f"{ci_str} | {score_str} | {row['Median Score']:{_FMT_RATE}} | "
            f"{row['Consistency']:{_FMT_RATE}} | {cop_str} |"
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
        ci_str = (
            f"{row['Pass Rate']:{_FMT_RATE}} "
            f"({row['PR 95% CI Low']:{_FMT_RATE}}, {row['PR 95% CI High']:{_FMT_RATE}})"
        )
        score_str = f"{row['Mean Score']:{_FMT_RATE}} $\\pm$ {row['Score StdDev']:{_FMT_RATE}}"
        cop_str = f"{row['CoP']:{_FMT_COST}}" if row["CoP"] is not None else "$\\infty$"

        latex_lines.append(
            f"{row['Model']} & {row['Tier']} & {row['Subtests']} & "
            f"{ci_str} & {score_str} & {row['Median Score']:{_FMT_RATE}} & "
            f"{row['Consistency']:{_FMT_RATE}} & {cop_str} \\\\"
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
            cop = compute_cop(mean_cost, pass_rate)

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
            f"{row['CoP']:{_FMT_COST}}"
            if row["CoP"] is not None
            else "∞"
            if row["Tier"] != "**Total**"
            else "—"
        )

        md_lines.append(
            f"| {row['Model']} | {row['Tier']} | {row['Mean Cost']:{_FMT_COST}} | "
            f"{row['Total Cost']:{_FMT_COST}} | {cop_str} | "
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
            f"{row['CoP']:{_FMT_COST}}"
            if row["CoP"] is not None
            else "$\\infty$"
            if row["Tier"] != "**Total**"
            else "---"
        )

        latex_lines.append(
            f"{row['Model']} & {row['Tier']} & {row['Mean Cost']:{_FMT_COST}} & "
            f"{row['Total Cost']:{_FMT_COST}} & {cop_str} & "
            f"{row['Input Tokens']:.0f} & {row['Output Tokens']:.0f} & "
            f"{row['Cache Read']:.0f} & {row['Cache Create']:.0f} \\\\"
        )

    latex_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])

    latex = "\n".join(latex_lines)

    return markdown, latex


__all__ = [
    "table01_tier_summary",
    "table05_cost_analysis",
]
