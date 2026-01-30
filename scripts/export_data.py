#!/usr/bin/env python3
"""Export experiment data to CSV files.

Exports runs, judges, criteria, and subtests DataFrames to CSV for external use.

Python Justification: Data export using pandas DataFrame.to_csv().
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scylla.analysis import (
    build_criteria_df,
    build_judges_df,
    build_runs_df,
    build_subtests_df,
    load_all_experiments,
)


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

    args = parser.parse_args()

    # Load experiment data
    print(f"Loading experiments from {args.data_dir}")
    experiments = load_all_experiments(args.data_dir)

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
            "total_cost": float(runs_df["cost_usd"].sum()),
            "mean_cost_per_run": float(runs_df["cost_usd"].mean()),
        },
        "by_model": {},
    }

    for model in runs_df["agent_model"].unique():
        model_df = runs_df[runs_df["agent_model"] == model]
        summary["by_model"][model] = {
            "total_runs": len(model_df),
            "pass_rate": float(model_df["passed"].mean()),
            "mean_score": float(model_df["score"].mean()),
            "total_cost": float(model_df["cost_usd"].sum()),
            "mean_cost_per_run": float(model_df["cost_usd"].mean()),
        }

    summary_path = output_dir / "summary.json"
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2)
    print("  Exported summary.json")

    print("\nExport complete!")


if __name__ == "__main__":
    main()
