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
)
from scylla.analysis.figures.spec_builder import apply_publication_theme
from scylla.analysis.tables import (
    table01_tier_summary,
    table02_tier_comparison,
    table03_judge_agreement,
    table04_criteria_performance,
    table05_cost_analysis,
    table06_model_comparison,
    table07_subtest_detail,
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

    args = parser.parse_args()

    # Apply publication theme
    apply_publication_theme()

    # Load experiment data
    print(f"Loading experiments from {args.data_dir}")
    experiments = load_all_experiments(args.data_dir, exclude=["test001-dryrun"])

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

    # Generate tables with error isolation
    print(f"\nGenerating tables in {output_dir}...")

    tables = [
        ("Table 1", "tab01_tier_summary", lambda: table01_tier_summary(runs_df)),
        ("Table 2", "tab02_tier_comparison", lambda: table02_tier_comparison(runs_df)),
        ("Table 3", "tab03_judge_agreement", lambda: table03_judge_agreement(judges_df)),
        (
            "Table 4",
            "tab04_criteria_performance",
            lambda: table04_criteria_performance(criteria_df, runs_df),
        ),
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

    # Continue with remaining tables
    remaining_tables = [
        ("Table 5", "tab05_cost_analysis", lambda: table05_cost_analysis(runs_df)),
        ("Table 6", "tab06_model_comparison", lambda: table06_model_comparison(runs_df)),
        (
            "Table 7",
            "tab07_subtest_detail",
            lambda: table07_subtest_detail(runs_df, subtests_df),
        ),
    ]

    for table_name, file_prefix, generator_func in remaining_tables:
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
    print(f"\n{'='*70}")
    print(f"Summary: {success_count}/7 tables generated successfully")
    if failed:
        print(f"\nFailed tables ({len(failed)}):")
        for table_name, error in failed:
            print(f"  ✗ {table_name}: {error}")
    print(f"\nOutput directory: {output_dir}")


if __name__ == "__main__":
    main()
