#!/usr/bin/env python3
"""Master script to generate all analysis outputs.

Runs data export, figure generation, and table generation in sequence.

Python Justification: Orchestrates other Python scripts.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_script(script_name: str, args: list[str], description: str) -> bool:
    """Run a script and return success status.

    Args:
        script_name: Name of the script to run
        args: Command-line arguments for the script
        description: Human-readable description

    Returns:
        True if successful, False otherwise

    """
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}\n")

    cmd = ["pixi", "run", "-e", "analysis", "python", script_name, *args]

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: {script_name} failed with return code {e.returncode}")
        return False


def main() -> None:
    """Run the complete analysis pipeline."""
    parser = argparse.ArgumentParser(
        description="Generate all analysis outputs (data + figures + tables)",
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
        default=Path("docs"),
        help="Base output directory (default: docs/)",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Skip rendering figures to PNG/PDF",
    )
    parser.add_argument(
        "--skip-data",
        action="store_true",
        help="Skip data export (assume CSVs already exist)",
    )
    parser.add_argument(
        "--skip-figures",
        action="store_true",
        help="Skip figure generation",
    )
    parser.add_argument(
        "--skip-tables",
        action="store_true",
        help="Skip table generation",
    )

    args = parser.parse_args()

    success = True

    # Step 1: Export data
    if not args.skip_data:
        export_args = [
            "--data-dir",
            str(args.data_dir),
            "--output-dir",
            str(args.output_dir / "data"),
        ]
        if not run_script(
            "scripts/export_data.py",
            export_args,
            "Step 1/3: Exporting experiment data to CSV",
        ):
            success = False

    # Step 2: Generate figures
    if not args.skip_figures and success:
        figure_args = [
            "--data-dir",
            str(args.data_dir),
            "--output-dir",
            str(args.output_dir / "figures"),
        ]
        if args.no_render:
            figure_args.append("--no-render")

        if not run_script(
            "scripts/generate_figures.py",
            figure_args,
            "Step 2/3: Generating figures (Vega-Lite specs + CSV)",
        ):
            success = False

    # Step 3: Generate tables
    if not args.skip_tables and success:
        table_args = [
            "--data-dir",
            str(args.data_dir),
            "--output-dir",
            str(args.output_dir / "tables"),
        ]
        if not run_script(
            "scripts/generate_tables.py",
            table_args,
            "Step 3/3: Generating statistical tables (Markdown + LaTeX)",
        ):
            success = False

    # Summary
    print(f"\n{'='*70}")
    if success:
        print("✓ All analysis outputs generated successfully!")
        print("\nOutputs:")
        print(f"  Data:    {args.output_dir / 'data'}/*.csv, summary.json")
        print(f"  Figures: {args.output_dir / 'figures'}/*.{{vl.json,csv}}")
        print(f"  Tables:  {args.output_dir / 'tables'}/*.{{md,tex}}")
        print("\nNext steps:")
        print(f"  - View figures: open {args.output_dir / 'figures'}/*.vl.json in Vega Editor")
        print(f"  - View tables: {args.output_dir / 'tables'}/*.md")
        print(f"  - Use data: {args.output_dir / 'data'}/*.csv")
    else:
        print("✗ Some steps failed. Check output above for errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
