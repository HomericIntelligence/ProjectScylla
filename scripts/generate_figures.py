#!/usr/bin/env python3
"""Generate all figures for the paper.

Loads experiment data and generates Vega-Lite specifications with CSV data.

Python Justification: Orchestrates Python-only scientific libraries (pandas,
altair) for figure generation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scylla.analysis import (
    build_criteria_df,
    build_judges_df,
    build_runs_df,
    load_all_experiments,
)
from scylla.analysis.figures.correlation import (
    fig20_metric_correlation_heatmap,
    fig21_cost_quality_regression,
)
from scylla.analysis.figures.cost_analysis import (
    fig06_cop_by_tier,
    fig08_cost_quality_pareto,
    fig22_cumulative_cost,
)
from scylla.analysis.figures.criteria_analysis import fig09_criteria_by_tier
from scylla.analysis.figures.diagnostics import fig23_qq_plots, fig24_score_histograms
from scylla.analysis.figures.effect_size import fig19_effect_size_forest
from scylla.analysis.figures.impl_rate_analysis import (
    fig25_impl_rate_by_tier,
    fig26_impl_rate_vs_pass_rate,
    fig27_impl_rate_distribution,
)
from scylla.analysis.figures.judge_analysis import (
    fig02_judge_variance,
    fig14_judge_agreement,
    fig17_judge_variance_overall,
)
from scylla.analysis.figures.model_comparison import fig11_tier_uplift, fig12_consistency
from scylla.analysis.figures.spec_builder import apply_publication_theme
from scylla.analysis.figures.subtest_detail import fig13_latency, fig15_subtest_heatmap
from scylla.analysis.figures.tier_performance import (
    fig04_pass_rate_by_tier,
    fig05_grade_heatmap,
    fig10_score_violin,
)
from scylla.analysis.figures.token_analysis import fig07_token_distribution
from scylla.analysis.figures.variance import (
    fig01_score_variance_by_tier,
    fig03_failure_rate_by_tier,
    fig16_success_variance_by_test,
    fig18_failure_rate_by_test,
)

# Figure registry mapping names to generator functions
FIGURES = {
    "fig01_score_variance_by_tier": ("variance", fig01_score_variance_by_tier),
    "fig02_judge_variance": ("judge", fig02_judge_variance),
    "fig03_failure_rate_by_tier": ("variance", fig03_failure_rate_by_tier),
    "fig04_pass_rate_by_tier": ("tier", fig04_pass_rate_by_tier),
    "fig05_grade_heatmap": ("tier", fig05_grade_heatmap),
    "fig06_cop_by_tier": ("cost", fig06_cop_by_tier),
    "fig07_token_distribution": ("token", fig07_token_distribution),
    "fig08_cost_quality_pareto": ("cost", fig08_cost_quality_pareto),
    "fig09_criteria_by_tier": ("criteria", fig09_criteria_by_tier),
    "fig10_score_violin": ("tier", fig10_score_violin),
    "fig11_tier_uplift": ("model", fig11_tier_uplift),
    "fig12_consistency": ("model", fig12_consistency),
    "fig13_latency": ("cost", fig13_latency),
    "fig14_judge_agreement": ("judge", fig14_judge_agreement),
    "fig15_subtest_heatmap": ("subtest", fig15_subtest_heatmap),
    "fig16_success_variance_by_test": ("variance", fig16_success_variance_by_test),
    "fig17_judge_variance_overall": ("judge", fig17_judge_variance_overall),
    "fig18_failure_rate_by_test": ("variance", fig18_failure_rate_by_test),
    "fig19_effect_size_forest": ("effect_size", fig19_effect_size_forest),
    "fig20_metric_correlation_heatmap": ("correlation", fig20_metric_correlation_heatmap),
    "fig21_cost_quality_regression": ("correlation", fig21_cost_quality_regression),
    "fig22_cumulative_cost": ("cost", fig22_cumulative_cost),
    "fig23_qq_plots": ("diagnostics", fig23_qq_plots),
    "fig24_score_histograms": ("diagnostics", fig24_score_histograms),
    "fig25_impl_rate_by_tier": ("impl_rate", fig25_impl_rate_by_tier),
    "fig26_impl_rate_vs_pass_rate": ("impl_rate", fig26_impl_rate_vs_pass_rate),
    "fig27_impl_rate_distribution": ("impl_rate", fig27_impl_rate_distribution),
}


def main() -> None:
    """Run the figure generation script."""
    parser = argparse.ArgumentParser(
        description="Generate figures for the paper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / "fullruns",
        help="Root of fullruns/ (default: ~/fullruns)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/figures"),
        help="Output directory (default: docs/figures)",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Skip rendering to PNG/PDF (only generate specs and CSVs)",
    )
    parser.add_argument(
        "--figures",
        type=str,
        default="all",
        help="Comma-separated figure names (default: all)",
    )
    parser.add_argument(
        "--list-figures",
        action="store_true",
        help="List available figures and exit",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=[],
        help="Experiment names to exclude (e.g., --exclude test001-dryrun)",
    )

    args = parser.parse_args()

    if args.list_figures:
        print("Available figures:")
        for name, (category, _) in FIGURES.items():
            print(f"  {name} ({category})")
        return

    # Apply publication theme
    apply_publication_theme()

    # Load experiment data
    print(f"Loading experiments from {args.data_dir}")
    experiments = load_all_experiments(args.data_dir, exclude=args.exclude)

    if not experiments:
        print("ERROR: No experiments found")
        return

    # Build DataFrames
    print("Building DataFrames...")
    runs_df = build_runs_df(experiments)
    judges_df = build_judges_df(experiments)
    criteria_df = build_criteria_df(experiments)

    print(f"  Runs: {len(runs_df)}")
    print(f"  Judges: {len(judges_df)}")
    print(f"  Criteria: {len(criteria_df)}")

    # Determine which figures to generate
    if args.figures == "all":
        figures_to_generate = list(FIGURES.keys())
    else:
        figures_to_generate = [f.strip() for f in args.figures.split(",")]

    # Generate figures with error isolation
    render = not args.no_render
    output_dir = Path(args.output_dir)

    print(f"\nGenerating {len(figures_to_generate)} figures...")
    success_count = 0
    failed = []

    for fig_name in figures_to_generate:
        if fig_name not in FIGURES:
            print(f"WARNING: Unknown figure '{fig_name}', skipping")
            continue

        category, generator_func = FIGURES[fig_name]
        print(f"\n{fig_name} ({category}):")

        try:
            # Determine which DataFrame to pass
            if category in (
                "variance",
                "tier",
                "cost",
                "token",
                "model",
                "subtest",
                "effect_size",
                "correlation",
                "diagnostics",
                "impl_rate",
            ):
                generator_func(runs_df, output_dir, render=render)
            elif category == "judge":
                generator_func(judges_df, output_dir, render=render)
            elif category == "criteria":
                generator_func(criteria_df, output_dir, render=render)
            else:
                print(f"  ERROR: Unknown category '{category}'")
                failed.append((fig_name, "Unknown category"))
                continue

            print(f"  ✓ {fig_name} generated successfully")
            success_count += 1

        except Exception as e:
            print(f"  ✗ {fig_name} failed: {e}")
            failed.append((fig_name, str(e)))

    # Summary
    print(f"\n{'=' * 70}")
    print(f"Summary: {success_count}/{len(figures_to_generate)} figures generated successfully")
    if failed:
        print(f"\nFailed figures ({len(failed)}):")
        for fig_name, error in failed:
            print(f"  ✗ {fig_name}: {error}")
    print(f"\nOutput directory: {output_dir}")
    print("\nNext steps:")
    print(f"  - View specs: open {output_dir}/*.vl.json in Vega Editor")
    print(f"  - View data: {output_dir}/*.csv")
    if render:
        print(f"  - View images: {output_dir}/*.png")


if __name__ == "__main__":
    main()
