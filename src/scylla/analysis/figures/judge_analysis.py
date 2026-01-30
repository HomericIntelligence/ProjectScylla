"""Judge analysis figures.

Generates Fig 2 (per-judge variance) and Fig 14 (inter-judge agreement).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import COLORS
from scylla.analysis.figures.spec_builder import save_figure
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

    # Simplify judge model names for display
    model_name_map = {
        "claude-opus-4-5-20251101": "Opus 4.5",
        "claude-sonnet-4-5-20250129": "Sonnet 4.5",
        "claude-haiku-4-5-20241223": "Haiku 4.5",
    }
    data["judge_display"] = data["judge_model"].map(model_name_map)

    tier_order = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]
    judge_order = ["Opus 4.5", "Sonnet 4.5", "Haiku 4.5"]

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
            scale=alt.Scale(
                domain=judge_order,
                range=[
                    COLORS["judges"]["claude-opus-4-5-20251101"],
                    COLORS["judges"]["claude-sonnet-4-5-20250129"],
                    COLORS["judges"]["claude-haiku-4-5-20241223"],
                ],
            ),
            legend=None,
        ),
    )

    # Box plot
    boxplot = base.mark_boxplot(size=20)

    # Combine and facet by tier
    chart = (
        boxplot.facet(
            column=alt.Column("tier:O", title="Tier", sort=tier_order),
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

    judge_pivot.columns = [
        "tier",
        "subtest",
        "run_number",
        "judge_1",
        "judge_2",
        "judge_3",
    ]

    # Remove rows with missing judges
    judge_pivot = judge_pivot.dropna()

    # Create pairwise comparison data
    pairs = []

    # Judge 1 vs Judge 2
    for _, row in judge_pivot.iterrows():
        pairs.append(
            {
                "judge_x": "Judge 1 (Opus)",
                "judge_y": "Judge 2 (Sonnet)",
                "score_x": row["judge_1"],
                "score_y": row["judge_2"],
            }
        )

    # Judge 1 vs Judge 3
    for _, row in judge_pivot.iterrows():
        pairs.append(
            {
                "judge_x": "Judge 1 (Opus)",
                "judge_y": "Judge 3 (Haiku)",
                "score_x": row["judge_1"],
                "score_y": row["judge_3"],
            }
        )

    # Judge 2 vs Judge 3
    for _, row in judge_pivot.iterrows():
        pairs.append(
            {
                "judge_x": "Judge 2 (Sonnet)",
                "judge_y": "Judge 3 (Haiku)",
                "score_x": row["judge_2"],
                "score_y": row["judge_3"],
            }
        )

    pairs_df = pd.DataFrame(pairs)

    # Compute correlations for annotations
    correlations = []
    for judge_x, judge_y in [
        ("Judge 1 (Opus)", "Judge 2 (Sonnet)"),
        ("Judge 1 (Opus)", "Judge 3 (Haiku)"),
        ("Judge 2 (Sonnet)", "Judge 3 (Haiku)"),
    ]:
        subset = pairs_df[(pairs_df["judge_x"] == judge_x) & (pairs_df["judge_y"] == judge_y)]
        spearman_r, _ = spearman_correlation(subset["score_x"], subset["score_y"])
        pearson_r, _ = pearson_correlation(subset["score_x"], subset["score_y"])

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
