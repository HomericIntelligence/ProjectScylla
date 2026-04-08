#!/usr/bin/env python3
"""Analyze tier x task interaction using Scheirer-Ray-Hare test.

The standard export pipeline runs SRH with agent_model as factor_a,
which degenerates with a single model. This script uses experiment
(i.e., task) as factor_a to test whether tier effects depend on task.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scylla.analysis import build_runs_df, load_all_experiments
from scylla.analysis.stats import scheirer_ray_hare


def json_nan_handler(obj: object) -> object:
    """Handle NaN/inf for JSON serialization."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def main() -> None:
    """Run Scheirer-Ray-Hare tier x experiment interaction analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze tier x task interaction via Scheirer-Ray-Hare"
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
        default=Path("docs/arxiv/haiku/data"),
        help="Output directory (default: docs/arxiv/haiku/data)",
    )
    args = parser.parse_args()

    experiments = load_all_experiments(args.data_dir)
    runs_df = build_runs_df(experiments)

    results = {}
    for metric in ["score", "cost_usd", "impl_rate"]:
        if metric not in runs_df.columns:
            continue
        df = runs_df.dropna(subset=[metric])
        if df.empty:
            continue

        srh = scheirer_ray_hare(
            df,
            value_col=metric,
            factor_a_col="experiment",
            factor_b_col="tier",
        )
        results[metric] = srh

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_file = args.output_dir / "srh_tier_experiment.json"
    output_file.write_text(json.dumps(results, indent=2, default=json_nan_handler))
    print(f"Wrote {output_file}")

    for metric, srh in results.items():
        print(f"\n{metric}:")
        for factor, vals in srh.items():
            h = vals.get("h_statistic", "?")
            p = vals.get("p_value", "?")
            sig = (
                "***"
                if isinstance(p, float) and p < 0.001
                else (
                    "**"
                    if isinstance(p, float) and p < 0.01
                    else ("*" if isinstance(p, float) and p < 0.05 else "")
                )
            )
            print(
                f"  {factor}: H={h:.3f}, p={p:.6f} {sig}"
                if isinstance(h, float)
                else f"  {factor}: {vals}"
            )


if __name__ == "__main__":
    main()
