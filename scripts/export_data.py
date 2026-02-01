#!/usr/bin/env python3
"""Export experiment data to CSV files.

Exports runs, judges, criteria, and subtests DataFrames to CSV for external use.

Python Justification: Data export using pandas DataFrame.to_csv().
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scylla.analysis import (
    build_criteria_df,
    build_judges_df,
    build_runs_df,
    build_subtests_df,
    load_all_experiments,
)
from scylla.analysis.config import config
from scylla.analysis.figures import derive_tier_order
from scylla.analysis.stats import (
    cliffs_delta_ci,
    compute_cop,
    compute_frontier_cop,
    holm_bonferroni_correction,
    kruskal_wallis,
    mann_whitney_u,
    shapiro_wilk,
    spearman_correlation,
)


def json_nan_handler(obj):
    """Convert NaN/inf values to None for JSON serialization."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj


def compute_statistical_results(runs_df, tier_order):
    """Compute all statistical test results for export.

    Pairwise comparisons use Holm-Bonferroni correction per model.
    Both raw and corrected p-values are exported for transparency.

    Args:
        runs_df: Runs DataFrame
        tier_order: List of tier IDs in order

    Returns:
        Dictionary of statistical test results with corrected p-values

    """
    results = {
        "pipeline_version": config.pipeline_version,
        "config_version": config.config_version,
        "normality_tests": [],
        "omnibus_tests": [],
        "pairwise_comparisons": [],
        "effect_sizes": [],
        "correlations": [],
        "tier_descriptives": [],  # Tier-level descriptive statistics (CoP, etc.)
    }

    models = sorted(runs_df["agent_model"].unique())

    # Normality tests (Shapiro-Wilk) per (model, tier)
    for model in models:
        for tier in tier_order:
            tier_data = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]

            if len(tier_data) < 3:
                continue

            # Test score distribution
            scores = tier_data["score"].dropna()
            if len(scores) >= 3:
                w_stat, p_value = shapiro_wilk(scores)
                results["normality_tests"].append(
                    {
                        "model": model,
                        "tier": tier,
                        "metric": "score",
                        "n": len(scores),
                        "w_statistic": float(w_stat),
                        "p_value": float(p_value),
                        "is_normal": bool(p_value > 0.05),
                    }
                )

            # Test impl_rate distribution
            impl_rates = tier_data["impl_rate"].dropna()
            if len(impl_rates) >= 3:
                w_stat, p_value = shapiro_wilk(impl_rates)
                results["normality_tests"].append(
                    {
                        "model": model,
                        "tier": tier,
                        "metric": "impl_rate",
                        "n": len(impl_rates),
                        "w_statistic": float(w_stat),
                        "p_value": float(p_value),
                        "is_normal": bool(p_value > 0.05),
                    }
                )

            # Test cost distribution
            costs = tier_data["cost_usd"].dropna()
            if len(costs) >= 3:
                w_stat, p_value = shapiro_wilk(costs)
                results["normality_tests"].append(
                    {
                        "model": model,
                        "tier": tier,
                        "metric": "cost_usd",
                        "n": len(costs),
                        "w_statistic": float(w_stat),
                        "p_value": float(p_value),
                        "is_normal": bool(p_value > 0.05),
                    }
                )

    # Omnibus tests (Kruskal-Wallis) across tiers per model
    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]

        # Collect tier groups for passed metric
        tier_groups = [
            model_runs[model_runs["tier"] == tier]["passed"].astype(int) for tier in tier_order
        ]
        tier_groups = [g for g in tier_groups if len(g) > 0]

        if len(tier_groups) >= 2:
            h_stat, p_value = kruskal_wallis(*tier_groups)
            results["omnibus_tests"].append(
                {
                    "model": model,
                    "metric": "pass_rate",
                    "n_groups": len(tier_groups),
                    "h_statistic": float(h_stat),
                    "p_value": float(p_value),
                    "is_significant": bool(p_value < 0.05),
                }
            )

        # Collect tier groups for impl_rate metric
        tier_groups_impl = [
            model_runs[model_runs["tier"] == tier]["impl_rate"].dropna() for tier in tier_order
        ]
        tier_groups_impl = [g for g in tier_groups_impl if len(g) > 0]

        if len(tier_groups_impl) >= 2:
            h_stat, p_value = kruskal_wallis(*tier_groups_impl)
            results["omnibus_tests"].append(
                {
                    "model": model,
                    "metric": "impl_rate",
                    "n_groups": len(tier_groups_impl),
                    "h_statistic": float(h_stat),
                    "p_value": float(p_value),
                    "is_significant": bool(p_value < 0.05),
                }
            )

    # Pairwise comparisons (Mann-Whitney U) between consecutive tiers
    # Collect raw p-values per model, then apply Holm-Bonferroni correction
    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]
        raw_p_values = []
        test_metadata = []

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            tier1_data = model_runs[model_runs["tier"] == tier1]
            tier2_data = model_runs[model_runs["tier"] == tier2]

            if len(tier1_data) == 0 or len(tier2_data) == 0:
                continue

            u_stat, p_value_raw = mann_whitney_u(
                tier1_data["passed"].astype(int), tier2_data["passed"].astype(int)
            )

            raw_p_values.append(p_value_raw)
            test_metadata.append(
                {
                    "model": model,
                    "tier1": tier1,
                    "tier2": tier2,
                    "n1": len(tier1_data),
                    "n2": len(tier2_data),
                    "u_statistic": float(u_stat),
                }
            )

        # Apply Holm-Bonferroni correction to all pairwise tests for this model
        if raw_p_values:
            corrected_p_values = holm_bonferroni_correction(raw_p_values)

            for i, metadata in enumerate(test_metadata):
                results["pairwise_comparisons"].append(
                    {
                        **metadata,
                        "metric": "pass_rate",
                        "p_value_raw": float(raw_p_values[i]),
                        "p_value": float(corrected_p_values[i]),
                        "is_significant": bool(corrected_p_values[i] < 0.05),
                    }
                )

    # Pairwise comparisons for impl_rate between consecutive tiers
    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]
        raw_p_values = []
        test_metadata = []

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            tier1_data = model_runs[model_runs["tier"] == tier1]["impl_rate"].dropna()
            tier2_data = model_runs[model_runs["tier"] == tier2]["impl_rate"].dropna()

            if len(tier1_data) < 2 or len(tier2_data) < 2:
                continue

            u_stat, p_value_raw = mann_whitney_u(tier1_data, tier2_data)

            raw_p_values.append(p_value_raw)
            test_metadata.append(
                {
                    "model": model,
                    "tier1": tier_order[i],
                    "tier2": tier_order[i + 1],
                    "n1": len(tier1_data),
                    "n2": len(tier2_data),
                    "u_statistic": float(u_stat),
                }
            )

        # Apply Holm-Bonferroni correction
        if raw_p_values:
            corrected_p_values = holm_bonferroni_correction(raw_p_values)

            for i, metadata in enumerate(test_metadata):
                results["pairwise_comparisons"].append(
                    {
                        **metadata,
                        "metric": "impl_rate",
                        "p_value_raw": float(raw_p_values[i]),
                        "p_value": float(corrected_p_values[i]),
                        "is_significant": bool(corrected_p_values[i] < 0.05),
                    }
                )

    # Effect sizes (Cliff's delta with CI) for tier transitions
    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            tier1_data = model_runs[model_runs["tier"] == tier1]
            tier2_data = model_runs[model_runs["tier"] == tier2]

            if len(tier1_data) < 2 or len(tier2_data) < 2:
                continue

            # Effect size for pass_rate
            delta, ci_low, ci_high = cliffs_delta_ci(
                tier2_data["passed"].astype(int), tier1_data["passed"].astype(int)
            )

            results["effect_sizes"].append(
                {
                    "model": model,
                    "metric": "pass_rate",
                    "tier1": tier1,
                    "tier2": tier2,
                    "cliffs_delta": float(delta),
                    "ci_low": float(ci_low),
                    "ci_high": float(ci_high),
                    "is_significant": bool(not (ci_low <= 0 <= ci_high)),
                }
            )

            # Effect size for impl_rate
            tier1_impl = tier1_data["impl_rate"].dropna()
            tier2_impl = tier2_data["impl_rate"].dropna()

            if len(tier1_impl) >= 2 and len(tier2_impl) >= 2:
                delta, ci_low, ci_high = cliffs_delta_ci(tier2_impl, tier1_impl)

                results["effect_sizes"].append(
                    {
                        "model": model,
                        "metric": "impl_rate",
                        "tier1": tier1,
                        "tier2": tier2,
                        "cliffs_delta": float(delta),
                        "ci_low": float(ci_low),
                        "ci_high": float(ci_high),
                        "is_significant": bool(not (ci_low <= 0 <= ci_high)),
                    }
                )

    # Correlations between key metrics
    metrics = [
        ("score", "cost_usd"),
        ("score", "total_tokens"),
        ("score", "duration_seconds"),
        ("score", "impl_rate"),
        ("impl_rate", "cost_usd"),
        ("impl_rate", "duration_seconds"),
        ("cost_usd", "total_tokens"),
    ]

    for model in models:
        model_data = runs_df[runs_df["agent_model"] == model]

        for metric1, metric2 in metrics:
            if metric1 not in model_data.columns or metric2 not in model_data.columns:
                continue

            # Get valid data (drop NaN)
            valid_idx = model_data[[metric1, metric2]].dropna().index
            if len(valid_idx) < 3:
                continue

            rho, p_value = spearman_correlation(
                model_data.loc[valid_idx, metric1], model_data.loc[valid_idx, metric2]
            )

            results["correlations"].append(
                {
                    "model": model,
                    "metric1": metric1,
                    "metric2": metric2,
                    "n": len(valid_idx),
                    "spearman_rho": float(rho),
                    "p_value": float(p_value),
                    "is_significant": bool(p_value < 0.05),
                }
            )

    # Tier-level descriptive statistics (CoP analysis)
    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]
        tier_cops = []

        for tier in tier_order:
            tier_data = model_runs[model_runs["tier"] == tier]

            if len(tier_data) == 0:
                continue

            pass_rate = float(tier_data["passed"].mean())
            mean_cost = float(tier_data["cost_usd"].mean())
            median_cost = float(tier_data["cost_usd"].median())
            cop = compute_cop(mean_cost, pass_rate)

            tier_cops.append(cop if cop != float("inf") else None)

            results["tier_descriptives"].append(
                {
                    "model": model,
                    "tier": tier,
                    "n": len(tier_data),
                    "pass_rate": pass_rate,
                    "mean_cost": mean_cost,
                    "median_cost": median_cost,
                    "cop": float(cop) if cop != float("inf") else None,
                }
            )

        # Add Frontier CoP for this model
        valid_cops = [c for c in tier_cops if c is not None]
        if valid_cops:
            frontier = compute_frontier_cop(valid_cops)
            # Find which tier achieved the frontier
            frontier_tier = None
            for i, (tier, cop) in enumerate(zip(tier_order, tier_cops)):
                if cop == frontier:
                    frontier_tier = tier
                    break

            results["tier_descriptives"].append(
                {
                    "model": model,
                    "tier": "frontier",
                    "n": sum(len(model_runs[model_runs["tier"] == t]) for t in tier_order),
                    "pass_rate": None,
                    "mean_cost": None,
                    "median_cost": None,
                    "cop": float(frontier),
                    "frontier_tier": frontier_tier,
                }
            )

    return results


def main() -> None:
    """Run the data export script."""
    parser = argparse.ArgumentParser(description="Export experiment data to CSV")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / "fullruns",
        help="Root of fullruns/ (default: ~/fullruns)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/data"),
        help="Output directory (default: docs/data)",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=[],
        help="Experiment names to exclude (e.g., --exclude test001-dryrun)",
    )

    args = parser.parse_args()

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
    subtests_df = build_subtests_df(runs_df)

    print(f"  Runs: {len(runs_df)}")
    print(f"  Judges: {len(judges_df)}")
    print(f"  Criteria: {len(criteria_df)}")
    print(f"  Subtests: {len(subtests_df)}")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export CSVs
    print(f"\nExporting to {output_dir}...")

    runs_df.to_csv(output_dir / "runs.csv", index=False)
    print(f"  Exported runs.csv ({len(runs_df)} rows)")

    judges_df.to_csv(output_dir / "judges.csv", index=False)
    print(f"  Exported judges.csv ({len(judges_df)} rows)")

    criteria_df.to_csv(output_dir / "criteria.csv", index=False)
    print(f"  Exported criteria.csv ({len(criteria_df)} rows)")

    subtests_df.to_csv(output_dir / "subtests.csv", index=False)
    print(f"  Exported subtests.csv ({len(subtests_df)} rows)")

    # Export summary statistics as JSON
    summary = {
        "pipeline_version": config.pipeline_version,
        "config_version": config.config_version,
        "total_experiments": len(experiments),
        "total_runs": len(runs_df),
        "total_judge_evaluations": len(judges_df),
        "total_criteria_scores": len(criteria_df),
        "total_subtests": len(subtests_df),
        "models": runs_df["agent_model"].unique().tolist(),
        "tiers": sorted(runs_df["tier"].unique().tolist()),
        "overall_stats": {
            "pass_rate": float(runs_df["passed"].mean()),
            "mean_score": float(runs_df["score"].mean()),
            "mean_impl_rate": float(runs_df["impl_rate"].mean()),
            "median_impl_rate": float(runs_df["impl_rate"].median()),
            "total_cost": float(runs_df["cost_usd"].sum()),
            "mean_cost_per_run": float(runs_df["cost_usd"].mean()),
        },
        "by_model": {},
    }

    # Enhanced by_model statistics
    for model in runs_df["agent_model"].unique():
        model_df = runs_df[runs_df["agent_model"] == model]

        # Compute additional statistics
        scores = model_df["score"].dropna()
        impl_rates = model_df["impl_rate"].dropna()
        costs = model_df["cost_usd"].dropna()
        durations = model_df["duration_seconds"].dropna()
        pass_rate = float(model_df["passed"].mean())
        mean_cost = float(costs.mean())

        # Compute overall CoP for this model
        model_cop = compute_cop(mean_cost, pass_rate)

        # Compute Frontier CoP (minimum CoP across all tiers for this model)
        tier_cops = []
        for tier in sorted(model_df["tier"].unique()):
            tier_data = model_df[model_df["tier"] == tier]
            tier_pass_rate = float(tier_data["passed"].mean())
            tier_mean_cost = float(tier_data["cost_usd"].mean())
            tier_cop = compute_cop(tier_mean_cost, tier_pass_rate)
            if tier_cop != float("inf"):
                tier_cops.append(tier_cop)

        frontier_cop = compute_frontier_cop(tier_cops) if tier_cops else float("inf")

        summary["by_model"][model] = {
            "total_runs": len(model_df),
            "pass_rate": pass_rate,
            "mean_score": float(scores.mean()),
            "median_score": float(scores.median()),
            "std_score": float(scores.std()),
            "min_score": float(scores.min()),
            "max_score": float(scores.max()),
            "q1_score": float(scores.quantile(0.25)),
            "q3_score": float(scores.quantile(0.75)),
            "mean_impl_rate": float(impl_rates.mean()),
            "median_impl_rate": float(impl_rates.median()),
            "std_impl_rate": float(impl_rates.std()),
            "min_impl_rate": float(impl_rates.min()),
            "max_impl_rate": float(impl_rates.max()),
            "total_cost": float(costs.sum()),
            "mean_cost_per_run": mean_cost,
            "median_cost": float(costs.median()),
            "cop": float(model_cop) if model_cop != float("inf") else None,
            "frontier_cop": float(frontier_cop) if frontier_cop != float("inf") else None,
            "total_tokens": int(model_df["total_tokens"].sum()),
            "mean_duration": float(durations.mean()),
            "n_subtests": int(model_df["subtest"].nunique()),
            "tiers": sorted(model_df["tier"].unique().tolist()),
        }

    # Add by_tier statistics (aggregated across all models)
    tier_order = derive_tier_order(runs_df)
    summary["by_tier"] = {}

    for tier in tier_order:
        tier_df = runs_df[runs_df["tier"] == tier]
        scores = tier_df["score"].dropna()
        impl_rates = tier_df["impl_rate"].dropna()
        costs = tier_df["cost_usd"].dropna()
        pass_rate = float(tier_df["passed"].mean())
        mean_cost = float(costs.mean())

        # Compute Cost-of-Pass for this tier
        cop = compute_cop(mean_cost, pass_rate)

        summary["by_tier"][tier] = {
            "total_runs": len(tier_df),
            "pass_rate": pass_rate,
            "mean_score": float(scores.mean()),
            "median_score": float(scores.median()),
            "std_score": float(scores.std()),
            "mean_impl_rate": float(impl_rates.mean()),
            "median_impl_rate": float(impl_rates.median()),
            "std_impl_rate": float(impl_rates.std()),
            "mean_cost": mean_cost,
            "total_cost": float(costs.sum()),
            "cop": float(cop) if cop != float("inf") else None,
            "n_subtests": int(tier_df["subtest"].nunique()),
        }

    summary_path = output_dir / "summary.json"
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2, default=json_nan_handler)
    print("  Exported summary.json")

    # Export statistical test results
    print("  Computing statistical results...")
    statistical_results = compute_statistical_results(runs_df, tier_order)

    stats_path = output_dir / "statistical_results.json"
    with stats_path.open("w") as f:
        json.dump(statistical_results, f, indent=2, default=json_nan_handler)
    print("  Exported statistical_results.json")

    print("\nExport complete!")


if __name__ == "__main__":
    main()
