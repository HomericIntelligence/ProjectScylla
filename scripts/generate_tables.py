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

    # Generate tables
    print(f"\nGenerating tables in {output_dir}...")

    # Table 1: Tier Summary
    print("\nTable 1: Tier Summary")
    md, tex = table01_tier_summary(runs_df)
    (output_dir / "tab01_tier_summary.md").write_text(md)
    (output_dir / "tab01_tier_summary.tex").write_text(tex)
    print("  Saved tab01_tier_summary.{md,tex}")

    # Table 2: Tier Pairwise Comparison
    print("\nTable 2: Tier Pairwise Comparison")
    md, tex = table02_tier_comparison(runs_df)
    (output_dir / "tab02_tier_comparison.md").write_text(md)
    (output_dir / "tab02_tier_comparison.tex").write_text(tex)
    print("  Saved tab02_tier_comparison.{md,tex}")

    # Table 3: Judge Agreement
    print("\nTable 3: Judge Agreement")
    md, tex = table03_judge_agreement(judges_df)
    (output_dir / "tab03_judge_agreement.md").write_text(md)
    (output_dir / "tab03_judge_agreement.tex").write_text(tex)
    print("  Saved tab03_judge_agreement.{md,tex}")

    # Table 4: Per-Criteria Performance
    print("\nTable 4: Per-Criteria Performance")
    md, tex = table04_criteria_performance(criteria_df, runs_df)
    (output_dir / "tab04_criteria_performance.md").write_text(md)
    (output_dir / "tab04_criteria_performance.tex").write_text(tex)
    print("  Saved tab04_criteria_performance.{md,tex}")

    # Table 5: Cost Analysis
    print("\nTable 5: Cost Analysis")
    md, tex = table05_cost_analysis(runs_df)
    (output_dir / "tab05_cost_analysis.md").write_text(md)
    (output_dir / "tab05_cost_analysis.tex").write_text(tex)
    print("  Saved tab05_cost_analysis.{md,tex}")

    # Table 6: Model Comparison
    print("\nTable 6: Model Comparison Summary")
    md, tex = table06_model_comparison(runs_df)
    (output_dir / "tab06_model_comparison.md").write_text(md)
    (output_dir / "tab06_model_comparison.tex").write_text(tex)
    print("  Saved tab06_model_comparison.{md,tex}")

    # Table 7: Full Subtest Results (Appendix B)
    print("\nTable 7: Full Subtest Results (Appendix B)")
    md, tex = table07_subtest_detail(runs_df, subtests_df)
    (output_dir / "tab07_subtest_detail.md").write_text(md)
    (output_dir / "tab07_subtest_detail.tex").write_text(tex)
    print("  Saved tab07_subtest_detail.{md,tex}")

    print(f"\nAll 7 tables saved to {output_dir}")


if __name__ == "__main__":
    main()
