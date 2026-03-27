"""Judge analysis figures.

Generates Fig 2 (per-judge variance) and Fig 14 (inter-judge agreement).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import compute_dynamic_domain, save_figure
from scylla.analysis.loader import model_id_to_display


def fig02_judge_variance(judges_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 2: Per-Judge Scoring Variance.

    Histogram showing judge score distribution with 0.05 bin width.
    Generates separate figures per tier to avoid Altair's 5,000-row limit.

    Args:
        judges_df: Judges DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Prepare data
    data = judges_df[["tier", "judge_score"]].copy()

    # Derive tier order from data
    tier_order = derive_tier_order(data)

    # Generate separate figure for each tier
    for tier in tier_order:
        tier_data = data[data["tier"] == tier]

        if len(tier_data) == 0:
            continue

        # Create histogram with 0.05 bin width
        histogram = (
            alt.Chart(tier_data)
            .mark_bar()
            .encode(
                x=alt.X("judge_score:Q", bin=alt.Bin(step=0.05), title="Judge Score"),
                y=alt.Y("count():Q", title="Count"),
            )
        )

        chart = histogram.properties(
            title=f"Judge Score Distribution - {tier}",
            width=400,
            height=300,
        )

        # Save with tier-specific filename
        tier_suffix = tier.lower().replace(" ", "-")
        save_figure(chart, f"fig02_{tier_suffix}_judge_variance", output_dir, render)


def fig14_judge_agreement(judges_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 14: Inter-Judge Agreement.

    3×3 scatter matrix showing pairwise judge score correlations.

    Args:
        judges_df: Judges DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Pivot judges to wide format for pairwise comparison
    # Include agent_model in index for per-model faceting
    index_cols = ["agent_model", "tier", "subtest", "run_number"]
    judge_pivot = judges_df.pivot_table(
        index=index_cols,
        columns="judge_number",
        values="judge_score",
    ).reset_index()

    # Get dynamic judge column names from pivot result
    judge_cols = [col for col in judge_pivot.columns if col not in index_cols]

    # Rename judge columns to judge_1, judge_2, etc.
    new_cols = index_cols + [f"judge_{i}" for i in range(1, len(judge_cols) + 1)]
    judge_pivot.columns = new_cols
    judge_cols_renamed = [f"judge_{i}" for i in range(1, len(judge_cols) + 1)]

    # Remove rows with missing judges
    judge_pivot = judge_pivot.dropna()

    # Create pairwise comparison data - reorganized to show 1v2, 2v3, 1v3 in single row
    pairs = []
    n_judges = len(judge_cols_renamed)

    # Define specific pairs we want: (1,2), (2,3), (1,3) - in that order
    pair_indices = [(0, 1), (1, 2), (0, 2)]  # (1v2), (2v3), (1v3)

    for i, j in pair_indices:
        if i < n_judges and j < n_judges:
            col_x = judge_cols_renamed[i]
            col_y = judge_cols_renamed[j]

            for _, row in judge_pivot.iterrows():
                pairs.append(
                    {
                        "agent_model": row["agent_model"],
                        "tier": row["tier"],
                        "pair_label": f"Judge {i + 1} vs {j + 1}",
                        "judge_x": f"Judge {i + 1}",
                        "judge_y": f"Judge {j + 1}",
                        "score_x": row[col_x],
                        "score_y": row[col_y],
                    }
                )

    pairs_df = pd.DataFrame(pairs)

    # Derive tier order for loop
    tier_order = derive_tier_order(judges_df)

    # Generate separate figure for each tier
    for tier in tier_order:
        tier_pairs_df = pairs_df[pairs_df["tier"] == tier]

        if len(tier_pairs_df) == 0:
            continue

        # Compute dynamic domains for scatter axes
        score_x_domain = compute_dynamic_domain(tier_pairs_df["score_x"])
        score_y_domain = compute_dynamic_domain(tier_pairs_df["score_y"])

        # Create scatter plot with faceting by pair_label and agent_model
        scatter = (
            alt.Chart(tier_pairs_df)
            .mark_circle(size=60, opacity=0.6)
            .encode(
                x=alt.X(
                    "score_x:Q", title="First Judge Score", scale=alt.Scale(domain=score_x_domain)
                ),
                y=alt.Y(
                    "score_y:Q", title="Second Judge Score", scale=alt.Scale(domain=score_y_domain)
                ),
                tooltip=[
                    alt.Tooltip("pair_label:N", title="Comparison"),
                    alt.Tooltip("judge_x:N", title="Judge"),
                    alt.Tooltip("score_x:Q", title="Score X", format=".3f"),
                    alt.Tooltip("judge_y:N", title="Judge"),
                    alt.Tooltip("score_y:Q", title="Score Y", format=".3f"),
                ],
            )
            .properties(width=250, height=250)
            .facet(
                column=alt.Column(
                    "pair_label:N",
                    title=None,
                    sort=["Judge 1 vs 2", "Judge 2 vs 3", "Judge 1 vs 3"],
                ),
                row=alt.Row("agent_model:N", title="Agent Model"),
            )
            .properties(title=f"Inter-Judge Score Agreement - {tier}")
            .resolve_scale(x="shared", y="shared")
        )

        # Save with tier-specific filename
        tier_suffix = tier.lower().replace(" ", "-")
        save_figure(scatter, f"fig14_{tier_suffix}_judge_agreement", output_dir, render)


def fig17_judge_variance_overall(
    judges_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 17: Judge Variance per Tier.

    Two-panel figure showing judge scoring behavior per tier:
    - Panel A: Box plot of score distributions per judge
    - Panel B: Bar chart of per-judge scoring standard deviation
    Generates separate figures per tier to avoid Altair's 5,000-row limit.

    Args:
        judges_df: Judges DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Prepare data - convert judge model IDs to display names
    data = judges_df[["tier", "judge_model", "judge_score"]].copy()
    data["judge_display"] = data["judge_model"].apply(model_id_to_display)

    # Derive tier order
    tier_order = derive_tier_order(data)

    # Generate separate figure for each tier
    for tier in tier_order:
        tier_data = data[data["tier"] == tier]

        if len(tier_data) == 0:
            continue

        # Get judge order dynamically from tier data
        judge_order = sorted(tier_data["judge_display"].unique())

        # Get dynamic color scale
        domain, range_ = get_color_scale("judges", judge_order)

        # Compute dynamic domain for judge score axis with increased padding for boxplot whiskers
        score_domain = compute_dynamic_domain(tier_data["judge_score"], padding_fraction=0.15)

        # Panel A: Box plot of score distributions
        boxplot = (
            alt.Chart(tier_data)
            .mark_boxplot(size=40)
            .encode(
                x=alt.X(
                    "judge_display:N",
                    title="Judge Model",
                    sort=judge_order,
                ),
                y=alt.Y("judge_score:Q", title="Judge Score", scale=alt.Scale(domain=score_domain)),
                color=alt.Color(
                    "judge_display:N",
                    title="Judge",
                    scale=alt.Scale(domain=domain, range=range_),
                    legend=None,
                ),
            )
            .properties(title="Panel A: Score Distribution per Judge", width=300)
        )

        # Panel B: Standard deviation bars
        std_data = tier_data.groupby("judge_display")["judge_score"].std().reset_index()
        std_data.columns = ["judge_display", "score_std"]

        # Compute dynamic domain for score std dev
        std_max = max(0.3, float(std_data["score_std"].max()) * 1.1)

        bars = (
            alt.Chart(std_data)
            .mark_bar()
            .encode(
                x=alt.X("judge_display:N", title="Judge Model", sort=judge_order),
                y=alt.Y(
                    "score_std:Q",
                    title="Score Std Dev",
                    scale=alt.Scale(domain=[0, round(std_max / 0.05) * 0.05]),
                ),
                color=alt.Color(
                    "judge_display:N",
                    scale=alt.Scale(domain=domain, range=range_),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("judge_display:N", title="Judge"),
                    alt.Tooltip("score_std:Q", title="Std Dev", format=".3f"),
                ],
            )
            .properties(title="Panel B: Scoring Standard Deviation", width=300)
        )

        # Combine panels horizontally
        chart = (boxplot | bars).properties(title=f"Judge Variance - {tier}")

        # Save with tier-specific filename
        tier_suffix = tier.lower().replace(" ", "-")
        save_figure(chart, f"fig17_{tier_suffix}_judge_variance_overall", output_dir, render)
