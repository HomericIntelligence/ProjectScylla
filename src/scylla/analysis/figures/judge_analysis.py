"""Judge analysis figures.

Generates Fig 2 (per-judge variance) and Fig 14 (inter-judge agreement).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import TIER_ORDER, get_color_scale
from scylla.analysis.figures.spec_builder import save_figure
from scylla.analysis.loader import model_id_to_display
from scylla.analysis.stats import pearson_correlation, spearman_correlation


def fig02_judge_variance(judges_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 2: Per-Judge Scoring Variance.

    Violin + box plots showing score distribution per judge model.

    Args:
        judges_df: Judges DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Prepare data
    data = judges_df[["tier", "judge_model", "judge_score"]].copy()

    # Convert judge model IDs to display names
    data["judge_display"] = data["judge_model"].apply(model_id_to_display)

    # Get judge order dynamically from data
    judge_order = sorted(data["judge_display"].unique())

    # Get dynamic color scale
    domain, range_ = get_color_scale("judges", judge_order)

    # Create violin plot with box plot overlay
    base = alt.Chart(data).encode(
        x=alt.X(
            "judge_display:N",
            title="Judge Model",
            sort=judge_order,
        ),
        y=alt.Y("judge_score:Q", title="Judge Score", scale=alt.Scale(domain=[0, 1])),
        color=alt.Color(
            "judge_display:N",
            title="Judge",
            scale=alt.Scale(domain=domain, range=range_),
            legend=None,
        ),
    )

    # Box plot
    boxplot = base.mark_boxplot(size=20)

    # Combine and facet by tier
    chart = (
        boxplot.facet(
            column=alt.Column("tier:O", title="Tier", sort=TIER_ORDER),
        )
        .properties(title="Judge Score Variance Across Tiers")
        .resolve_scale(x="independent")
    )

    save_figure(chart, "fig02_judge_variance", output_dir, data, render)


def fig14_judge_agreement(judges_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 14: Inter-Judge Agreement.

    3×3 scatter matrix showing pairwise judge score correlations.

    Args:
        judges_df: Judges DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Pivot judges to wide format for pairwise comparison
    judge_pivot = judges_df.pivot_table(
        index=["tier", "subtest", "run_number"],
        columns="judge_number",
        values="judge_score",
    ).reset_index()

    # Get dynamic judge column names from pivot result
    index_cols = ["tier", "subtest", "run_number"]
    judge_cols = [col for col in judge_pivot.columns if col not in index_cols]

    # Rename judge columns to judge_1, judge_2, etc.
    new_cols = index_cols + [f"judge_{i}" for i in range(1, len(judge_cols) + 1)]
    judge_pivot.columns = new_cols
    judge_cols_renamed = [f"judge_{i}" for i in range(1, len(judge_cols) + 1)]

    # Remove rows with missing judges
    judge_pivot = judge_pivot.dropna()

    # Create pairwise comparison data (dynamic based on number of judges)
    pairs = []
    n_judges = len(judge_cols_renamed)

    for i in range(n_judges):
        for j in range(i + 1, n_judges):
            col_x = judge_cols_renamed[i]
            col_y = judge_cols_renamed[j]

            for _, row in judge_pivot.iterrows():
                pairs.append(
                    {
                        "judge_x": f"Judge {i+1}",
                        "judge_y": f"Judge {j+1}",
                        "score_x": row[col_x],
                        "score_y": row[col_y],
                    }
                )

    pairs_df = pd.DataFrame(pairs)

    # Compute correlations for annotations - dynamically get judge pairs from data
    correlations = []
    for (judge_x, judge_y), group in pairs_df.groupby(["judge_x", "judge_y"]):
        spearman_r, _ = spearman_correlation(group["score_x"], group["score_y"])
        pearson_r, _ = pearson_correlation(group["score_x"], group["score_y"])

        correlations.append(
            {
                "judge_x": judge_x,
                "judge_y": judge_y,
                "spearman": spearman_r,
                "pearson": pearson_r,
            }
        )

    corr_df = pd.DataFrame(correlations)

    # Create scatter plot with faceting
    # Use repeat instead of layer + facet to avoid issues
    scatter = (
        alt.Chart(pairs_df)
        .mark_circle(size=10, opacity=0.3)
        .encode(
            x=alt.X("score_x:Q", title="Score (Judge X)", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("score_y:Q", title="Score (Judge Y)", scale=alt.Scale(domain=[0, 1])),
            tooltip=[
                alt.Tooltip("score_x:Q", title="Judge X Score", format=".3f"),
                alt.Tooltip("score_y:Q", title="Judge Y Score", format=".3f"),
            ],
        )
        .facet(
            row=alt.Row("judge_y:N", title=None),
            column=alt.Column("judge_x:N", title=None),
        )
        .properties(title="Inter-Judge Score Agreement")
        .resolve_scale(x="shared", y="shared")
    )

    # Note: We skip the diagonal reference line to avoid layer + facet issues
    # It can be added manually in post-processing if needed
    chart = scatter

    # Save with correlations in CSV
    save_figure(chart, "fig14_judge_agreement", output_dir, pairs_df, render)

    # Also save correlation table
    corr_csv_path = output_dir / "fig14_judge_agreement_correlations.csv"
    corr_df.to_csv(corr_csv_path, index=False)
    print(f"  Saved correlations: {corr_csv_path}")
