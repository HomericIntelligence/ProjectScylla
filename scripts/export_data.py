#!/usr/bin/env python3
"""Export experiment data to CSV files.

Exports runs, judges, criteria, and subtests DataFrames to CSV for external use.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

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
    kruskal_wallis_power,
    mann_whitney_power,
    mann_whitney_u,
    scheirer_ray_hare,
    shapiro_wilk,
    spearman_correlation,
)


def json_nan_handler(obj: Any) -> Any:
    """Convert NaN/inf values to None for JSON serialization."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _compute_normality_tests(
    runs_df: Any, models: list[str], tier_order: list[str]
) -> list[dict[str, Any]]:
    """Compute Shapiro-Wilk normality tests per (model, tier) for four metrics.

    Args:
        runs_df: Runs DataFrame
        models: Sorted list of model identifiers
        tier_order: List of tier IDs in order

    Returns:
        List of normality test result dicts

    """
    normality_tests: list[dict[str, Any]] = []
    metric_cols = ["score", "impl_rate", "cost_usd", "duration_seconds"]

    for model in models:
        for tier in tier_order:
            tier_data = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]

            if len(tier_data) < 3:
                continue

            for metric in metric_cols:
                values = tier_data[metric].dropna()
                if len(values) >= 3:
                    w_stat, p_value = shapiro_wilk(values)
                    normality_tests.append(
                        {
                            "model": model,
                            "tier": tier,
                            "metric": metric,
                            "n": len(values),
                            "w_statistic": float(w_stat),
                            "p_value": float(p_value),
                            "is_normal": bool(p_value > 0.05),
                        }
                    )

    return normality_tests


def _compute_omnibus_tests(
    runs_df: Any, models: list[str], tier_order: list[str]
) -> list[dict[str, Any]]:
    """Compute Kruskal-Wallis omnibus tests across tiers per model for three metrics.

    Args:
        runs_df: Runs DataFrame
        models: Sorted list of model identifiers
        tier_order: List of tier IDs in order

    Returns:
        List of omnibus test result dicts

    """
    omnibus_tests: list[dict[str, Any]] = []

    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]

        metric_configs = [
            (
                "pass_rate",
                [model_runs[model_runs["tier"] == t]["passed"].astype(int) for t in tier_order],
            ),
            (
                "impl_rate",
                [model_runs[model_runs["tier"] == t]["impl_rate"].dropna() for t in tier_order],
            ),
            (
                "duration_seconds",
                [
                    model_runs[model_runs["tier"] == t]["duration_seconds"].dropna()
                    for t in tier_order
                ],
            ),
        ]

        for metric_name, tier_groups_raw in metric_configs:
            tier_groups = [g for g in tier_groups_raw if len(g) > 0]
            if len(tier_groups) >= 2:
                h_stat, p_value = kruskal_wallis(*tier_groups)
                omnibus_tests.append(
                    {
                        "model": model,
                        "metric": metric_name,
                        "n_groups": len(tier_groups),
                        "h_statistic": float(h_stat),
                        "p_value": float(p_value),
                        "is_significant": bool(p_value < 0.05),
                    }
                )

    return omnibus_tests


def _collect_pairwise_pass_rate(
    model_runs: Any, model: str, tier_order: list[str]
) -> tuple[list[float], list[dict[str, Any]]]:
    """Collect raw p-values and metadata for pass_rate pairwise comparisons.

    Includes consecutive tier pairs plus overall first->last contrast.

    Args:
        model_runs: Runs DataFrame filtered to one model
        model: Model identifier
        tier_order: List of tier IDs in order

    Returns:
        Tuple of (raw_p_values, test_metadata)

    """
    raw_p_values: list[float] = []
    test_metadata: list[dict[str, Any]] = []

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

    # Add overall first->last tier contrast to the correction family
    first_tier, last_tier = tier_order[0], tier_order[-1]
    first_data = model_runs[model_runs["tier"] == first_tier]
    last_data = model_runs[model_runs["tier"] == last_tier]
    if len(first_data) > 0 and len(last_data) > 0:
        u_stat_fl, p_value_fl = mann_whitney_u(
            first_data["passed"].astype(int), last_data["passed"].astype(int)
        )
        raw_p_values.append(p_value_fl)
        test_metadata.append(
            {
                "model": model,
                "tier1": first_tier,
                "tier2": last_tier,
                "n1": len(first_data),
                "n2": len(last_data),
                "u_statistic": float(u_stat_fl),
                "overall_contrast": True,
            }
        )

    return raw_p_values, test_metadata


def _compute_pairwise_comparisons(
    runs_df: Any, models: list[str], tier_order: list[str]
) -> list[dict[str, Any]]:
    """Compute Mann-Whitney pairwise comparisons with Holm-Bonferroni correction.

    Covers pass_rate (with first->last contrast), impl_rate, and duration_seconds.

    Args:
        runs_df: Runs DataFrame
        models: Sorted list of model identifiers
        tier_order: List of tier IDs in order

    Returns:
        List of pairwise comparison result dicts

    """
    pairwise: list[dict[str, Any]] = []

    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]

        # pass_rate: consecutive pairs + first->last contrast
        raw_p_values, test_metadata = _collect_pairwise_pass_rate(model_runs, model, tier_order)
        if raw_p_values:
            corrected = holm_bonferroni_correction(raw_p_values)
            for i, metadata in enumerate(test_metadata):
                pairwise.append(
                    {
                        **metadata,
                        "metric": "pass_rate",
                        "p_value_raw": float(raw_p_values[i]),
                        "p_value": float(corrected[i]),
                        "is_significant": bool(corrected[i] < 0.05),
                    }
                )

        # impl_rate and duration_seconds: consecutive pairs only
        for metric in ("impl_rate", "duration_seconds"):
            raw_p_values = []
            test_metadata = []

            for i in range(len(tier_order) - 1):
                tier1, tier2 = tier_order[i], tier_order[i + 1]
                d1 = model_runs[model_runs["tier"] == tier1][metric].dropna()
                d2 = model_runs[model_runs["tier"] == tier2][metric].dropna()

                if len(d1) < 2 or len(d2) < 2:
                    continue

                u_stat, p_value_raw = mann_whitney_u(d1, d2)
                raw_p_values.append(p_value_raw)
                test_metadata.append(
                    {
                        "model": model,
                        "tier1": tier1,
                        "tier2": tier2,
                        "n1": len(d1),
                        "n2": len(d2),
                        "u_statistic": float(u_stat),
                    }
                )

            if raw_p_values:
                corrected = holm_bonferroni_correction(raw_p_values)
                for i, metadata in enumerate(test_metadata):
                    pairwise.append(
                        {
                            **metadata,
                            "metric": metric,
                            "p_value_raw": float(raw_p_values[i]),
                            "p_value": float(corrected[i]),
                            "is_significant": bool(corrected[i] < 0.05),
                        }
                    )

    return pairwise


def _compute_effect_sizes(
    runs_df: Any, models: list[str], tier_order: list[str]
) -> list[dict[str, Any]]:
    """Compute Cliff's delta effect sizes with CIs for tier transitions.

    Covers pass_rate, impl_rate, and duration_seconds for consecutive tier pairs.

    Args:
        runs_df: Runs DataFrame
        models: Sorted list of model identifiers
        tier_order: List of tier IDs in order

    Returns:
        List of effect size result dicts

    """
    effect_sizes: list[dict[str, Any]] = []

    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            t1 = model_runs[model_runs["tier"] == tier1]
            t2 = model_runs[model_runs["tier"] == tier2]

            if len(t1) < 2 or len(t2) < 2:
                continue

            # pass_rate
            delta, ci_low, ci_high = cliffs_delta_ci(
                t2["passed"].astype(int), t1["passed"].astype(int)
            )
            effect_sizes.append(
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

            # impl_rate and duration_seconds
            for metric in ("impl_rate", "duration_seconds"):
                d1 = t1[metric].dropna()
                d2 = t2[metric].dropna()
                if len(d1) >= 2 and len(d2) >= 2:
                    delta, ci_low, ci_high = cliffs_delta_ci(d2, d1)
                    effect_sizes.append(
                        {
                            "model": model,
                            "metric": metric,
                            "tier1": tier1,
                            "tier2": tier2,
                            "cliffs_delta": float(delta),
                            "ci_low": float(ci_low),
                            "ci_high": float(ci_high),
                            "is_significant": bool(not (ci_low <= 0 <= ci_high)),
                        }
                    )

    return effect_sizes


def _compute_power_analysis(
    runs_df: Any,
    models: list[str],
    tier_order: list[str],
    effect_sizes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute post-hoc power estimates for pairwise Mann-Whitney transitions.

    Uses simulation-based power estimation (10,000 iterations, seed=42).
    Also includes KW omnibus power at medium effect (eta^2 = 0.06) per model.

    Args:
        runs_df: Runs DataFrame
        models: Sorted list of model identifiers
        tier_order: List of tier IDs in order
        effect_sizes: Previously computed effect size results

    Returns:
        List of power analysis result dicts

    """
    power_analysis: list[dict[str, Any]] = []

    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            n1 = len(model_runs[model_runs["tier"] == tier1])
            n2 = len(model_runs[model_runs["tier"] == tier2])

            if n1 < 2 or n2 < 2:
                continue

            observed_delta = next(
                (
                    es["cliffs_delta"]
                    for es in effect_sizes
                    if es["model"] == model
                    and es["metric"] == "pass_rate"
                    and es["tier1"] == tier1
                    and es["tier2"] == tier2
                ),
                None,
            )

            if observed_delta is None:
                continue

            power_analysis.append(
                {
                    "model": model,
                    "metric": "pass_rate",
                    "tier1": tier1,
                    "tier2": tier2,
                    "n1": n1,
                    "n2": n2,
                    "observed_delta": float(observed_delta),
                    "power_at_observed": float(mann_whitney_power(n1, n2, abs(observed_delta))),
                    "power_at_medium_0_3": float(mann_whitney_power(n1, n2, 0.3)),
                }
            )

        # Overall KW power for pass_rate across all tiers
        tier_groups = [
            g
            for g in (model_runs[model_runs["tier"] == t]["passed"].astype(int) for t in tier_order)
            if len(g) > 0
        ]
        if len(tier_groups) >= 2:
            kw_power = kruskal_wallis_power([len(g) for g in tier_groups], effect_size=0.06)
            power_analysis.append(
                {
                    "model": model,
                    "metric": "pass_rate_omnibus",
                    "tier1": tier_order[0],
                    "tier2": tier_order[-1],
                    "n1": sum(len(g) for g in tier_groups),
                    "n2": None,
                    "observed_delta": None,
                    "power_at_observed": None,
                    "power_at_medium_0_3": float(kw_power),
                }
            )

    return power_analysis


def _compute_correlations(runs_df: Any, models: list[str]) -> list[dict[str, Any]]:
    """Compute Spearman correlations between key metric pairs per model.

    Args:
        runs_df: Runs DataFrame
        models: Sorted list of model identifiers

    Returns:
        List of correlation result dicts

    """
    metric_pairs = [
        ("score", "cost_usd"),
        ("score", "total_tokens"),
        ("score", "duration_seconds"),
        ("score", "impl_rate"),
        ("impl_rate", "cost_usd"),
        ("impl_rate", "duration_seconds"),
        ("cost_usd", "total_tokens"),
    ]
    correlations: list[dict[str, Any]] = []

    for model in models:
        model_data = runs_df[runs_df["agent_model"] == model]

        for metric1, metric2 in metric_pairs:
            if metric1 not in model_data.columns or metric2 not in model_data.columns:
                continue

            valid_idx = model_data[[metric1, metric2]].dropna().index
            if len(valid_idx) < 3:
                continue

            rho, p_value = spearman_correlation(
                model_data.loc[valid_idx, metric1], model_data.loc[valid_idx, metric2]
            )
            correlations.append(
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

    return correlations


def _compute_tier_descriptives(
    runs_df: Any, models: list[str], tier_order: list[str]
) -> list[dict[str, Any]]:
    """Compute tier-level descriptive statistics including CoP and Frontier CoP.

    Args:
        runs_df: Runs DataFrame
        models: Sorted list of model identifiers
        tier_order: List of tier IDs in order

    Returns:
        List of tier descriptive stat dicts

    """
    tier_descriptives: list[dict[str, Any]] = []

    for model in models:
        model_runs = runs_df[runs_df["agent_model"] == model]
        tier_cops: list[float | None] = []

        for tier in tier_order:
            tier_data = model_runs[model_runs["tier"] == tier]
            if len(tier_data) == 0:
                continue

            pass_rate = float(tier_data["passed"].mean())
            mean_cost = float(tier_data["cost_usd"].mean())
            cop = compute_cop(mean_cost, pass_rate)
            tier_cops.append(cop if cop != float("inf") else None)

            tier_descriptives.append(
                {
                    "model": model,
                    "tier": tier,
                    "n": len(tier_data),
                    "pass_rate": pass_rate,
                    "mean_cost": mean_cost,
                    "median_cost": float(tier_data["cost_usd"].median()),
                    "cop": float(cop) if cop != float("inf") else None,
                }
            )

        valid_cops = [c for c in tier_cops if c is not None]
        if valid_cops:
            frontier = compute_frontier_cop(valid_cops)
            frontier_tier = next(
                (t for t, c in zip(tier_order, tier_cops, strict=False) if c == frontier),
                None,
            )
            tier_descriptives.append(
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

    return tier_descriptives


def _compute_interaction_tests(runs_df: Any) -> list[dict[str, Any]]:
    """Compute Scheirer-Ray-Hare model x tier interaction tests for four metrics.

    Args:
        runs_df: Runs DataFrame

    Returns:
        List of interaction test result dicts

    """
    interaction_tests: list[dict[str, Any]] = []
    interaction_metrics = ["score", "impl_rate", "cost_usd", "duration_seconds"]

    for metric in interaction_metrics:
        metric_data = runs_df[["agent_model", "tier", metric]].dropna()

        if len(metric_data) < 10:
            continue

        srh_results = scheirer_ray_hare(
            metric_data, value_col=metric, factor_a_col="agent_model", factor_b_col="tier"
        )

        for effect_name, effect_result in srh_results.items():
            interaction_tests.append(
                {
                    "metric": metric,
                    "effect": effect_name,
                    "h_statistic": effect_result["h_statistic"],
                    "df": effect_result["df"],
                    "p_value": effect_result["p_value"],
                    "is_significant": bool(effect_result["p_value"] < 0.05),
                }
            )

    return interaction_tests


def compute_statistical_results(runs_df: Any, tier_order: list[str]) -> dict[str, Any]:
    """Compute all statistical test results for export.

    Pairwise comparisons use Holm-Bonferroni correction per model.
    Both raw and corrected p-values are exported for transparency.

    Args:
        runs_df: Runs DataFrame
        tier_order: List of tier IDs in order

    Returns:
        Dictionary of statistical test results with corrected p-values

    """
    models = sorted(runs_df["agent_model"].unique())

    effect_sizes = _compute_effect_sizes(runs_df, models, tier_order)

    return {
        "pipeline_version": config.pipeline_version,
        "config_version": config.config_version,
        "normality_tests": _compute_normality_tests(runs_df, models, tier_order),
        "omnibus_tests": _compute_omnibus_tests(runs_df, models, tier_order),
        "pairwise_comparisons": _compute_pairwise_comparisons(runs_df, models, tier_order),
        "effect_sizes": effect_sizes,
        "power_analysis": _compute_power_analysis(runs_df, models, tier_order, effect_sizes),
        "correlations": _compute_correlations(runs_df, models),
        "tier_descriptives": _compute_tier_descriptives(runs_df, models, tier_order),
        "interaction_tests": _compute_interaction_tests(runs_df),
    }


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
    overall_r_prog = runs_df["r_prog"].dropna()
    overall_cfp = runs_df["cfp"].dropna()
    overall_pr_revert_rate = runs_df["pr_revert_rate"].dropna()
    overall_strategic_drift = runs_df["strategic_drift"].dropna()
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
            "mean_r_prog": float(overall_r_prog.mean()) if not overall_r_prog.empty else None,
            "mean_cfp": float(overall_cfp.mean()) if not overall_cfp.empty else None,
            "mean_pr_revert_rate": float(overall_pr_revert_rate.mean())
            if not overall_pr_revert_rate.empty
            else None,
            "mean_strategic_drift": float(overall_strategic_drift.mean())
            if not overall_strategic_drift.empty
            else None,
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

        model_r_prog = model_df["r_prog"].dropna()
        model_cfp = model_df["cfp"].dropna()
        model_pr_revert_rate = model_df["pr_revert_rate"].dropna()
        model_strategic_drift = model_df["strategic_drift"].dropna()

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
            "mean_r_prog": float(model_r_prog.mean()) if not model_r_prog.empty else None,
            "mean_cfp": float(model_cfp.mean()) if not model_cfp.empty else None,
            "mean_pr_revert_rate": float(model_pr_revert_rate.mean())
            if not model_pr_revert_rate.empty
            else None,
            "mean_strategic_drift": float(model_strategic_drift.mean())
            if not model_strategic_drift.empty
            else None,
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

        tier_r_prog = tier_df["r_prog"].dropna()
        tier_cfp = tier_df["cfp"].dropna()
        tier_pr_revert_rate = tier_df["pr_revert_rate"].dropna()
        tier_strategic_drift = tier_df["strategic_drift"].dropna()

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
            "mean_r_prog": float(tier_r_prog.mean()) if not tier_r_prog.empty else None,
            "mean_cfp": float(tier_cfp.mean()) if not tier_cfp.empty else None,
            "mean_pr_revert_rate": float(tier_pr_revert_rate.mean())
            if not tier_pr_revert_rate.empty
            else None,
            "mean_strategic_drift": float(tier_strategic_drift.mean())
            if not tier_strategic_drift.empty
            else None,
        }

    # Verify consistency between summary count and CSV count
    # (both come from the same judges_df, so they must match)
    if summary["total_judge_evaluations"] != len(judges_df):
        raise ValueError(
            f"Judge count mismatch: summary reports {summary['total_judge_evaluations']} "
            f"but judges_df has {len(judges_df)} rows. This indicates the summary and CSV "
            f"were generated from different data states."
        )

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
