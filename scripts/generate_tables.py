#!/usr/bin/env python3
"""Generate statistical tables for the paper.

Generates both markdown and LaTeX versions of all tables.

Python Justification: Table generation using pandas and custom formatters.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scylla.analysis import (
    build_criteria_df,
    build_judges_df,
    build_runs_df,
    build_subtests_df,
    load_all_experiments,
    load_rubric_weights,
)
from scylla.analysis.tables import (
    table01_tier_summary,
    table02_tier_comparison,
    table02b_impl_rate_comparison,
    table03_judge_agreement,
    table04_criteria_performance,
    table05_cost_analysis,
    table06_model_comparison,
    table07_subtest_detail,
    table08_summary_statistics,
    table09_experiment_config,
    table10_normality_tests,
)


def main() -> None:
    """Run the table generation script."""
    parser = argparse.ArgumentParser(description="Generate tables for the paper")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / "fullruns",
        help="Root of fullruns/ (default: ~/fullruns)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/tables"),
        help="Output directory (default: docs/tables)",
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

    # Load rubric weights
    print("Loading rubric weights...")
    rubric_weights = load_rubric_weights(args.data_dir, exclude=args.exclude)
    if rubric_weights:
        print(f"  Loaded weights: {rubric_weights}")
    else:
        print("  No rubric found, using defaults")

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

    # Generate tables with error isolation
    print(f"\nGenerating tables in {output_dir}...")

    tables = [
        ("Table 1", "tab01_tier_summary", lambda: table01_tier_summary(runs_df)),
        ("Table 2", "tab02_tier_comparison", lambda: table02_tier_comparison(runs_df)),
        ("Table 2b", "tab02b_impl_rate_comparison", lambda: table02b_impl_rate_comparison(runs_df)),
        ("Table 3", "tab03_judge_agreement", lambda: table03_judge_agreement(judges_df)),
        (
            "Table 4",
            "tab04_criteria_performance",
            lambda: table04_criteria_performance(criteria_df, runs_df, rubric_weights),
        ),
        ("Table 5", "tab05_cost_analysis", lambda: table05_cost_analysis(runs_df)),
        ("Table 6", "tab06_model_comparison", lambda: table06_model_comparison(runs_df)),
        (
            "Table 7",
            "tab07_subtest_detail",
            lambda: table07_subtest_detail(runs_df, subtests_df),
        ),
        ("Table 8", "tab08_summary_statistics", lambda: table08_summary_statistics(runs_df)),
        ("Table 9", "tab09_experiment_config", lambda: table09_experiment_config(runs_df)),
        ("Table 10", "tab10_normality_tests", lambda: table10_normality_tests(runs_df)),
    ]

    success_count = 0
    failed = []

    for table_name, file_prefix, generator_func in tables:
        print(f"\n{table_name}")
        try:
            md, tex = generator_func()
            (output_dir / f"{file_prefix}.md").write_text(md)
            (output_dir / f"{file_prefix}.tex").write_text(tex)
            print(f"  ✓ Saved {file_prefix}.{{md,tex}}")
            success_count += 1
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed.append((table_name, str(e)))

    # Summary
    print(f"\n{'=' * 70}")
    print(f"Summary: {success_count}/{len(tables)} tables generated successfully")
    if failed:
        print(f"\nFailed tables ({len(failed)}):")
        for table_name, error in failed:
            print(f"  ✗ {table_name}: {error}")
    print(f"\nOutput directory: {output_dir}")


if __name__ == "__main__":
    main()
