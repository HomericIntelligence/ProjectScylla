#!/usr/bin/env python3
"""Regenerate results.json and reports from existing run_result.json files.

This script rebuilds experiment results without re-running agents or judges.
It can also selectively re-run judges for runs that are missing judge results.

Usage:
    # Minimal: just regenerate from existing data
    pixi run python scripts/regenerate_results.py /path/to/experiment/

    # Re-judge missing judges first, then regenerate
    pixi run python scripts/regenerate_results.py /path/to/experiment/ --rejudge

    # Override judge model
    pixi run python scripts/regenerate_results.py /path/to/experiment/ \
        --rejudge --judge-model claude-opus-4-5-20251101

    # Dry run to see what would be done
    pixi run python scripts/regenerate_results.py /path/to/experiment/ \
        --rejudge --dry-run

Examples:
    # Regenerate results after fixing run_result.json manually
    pixi run python scripts/regenerate_results.py \
        ~/fullruns/2026-01-29T12-00-00-experiment/

    # Re-judge runs that had judge failures and regenerate
    pixi run python scripts/regenerate_results.py \
        ~/fullruns/2026-01-29T12-00-00-experiment/ \
        --rejudge --verbose

Python Justification: Command-line tool for result regeneration.

"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Regenerate experiment results and reports from run data."""
    parser = argparse.ArgumentParser(
        description="Regenerate results.json and reports from existing run_result.json files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Regenerate from existing data
  %(prog)s /path/to/experiment/

  # Re-judge missing judges and regenerate
  %(prog)s /path/to/experiment/ --rejudge

  # Override judge model
  %(prog)s /path/to/experiment/ --rejudge --judge-model claude-opus-4-5-20251101

  # Dry run
  %(prog)s /path/to/experiment/ --rejudge --dry-run
        """,
    )

    parser.add_argument(
        "experiment_dir",
        type=Path,
        help="Path to experiment directory containing run_result.json files",
    )

    parser.add_argument(
        "--rejudge",
        action="store_true",
        help="Re-run judges for runs missing valid judge results",
    )

    parser.add_argument(
        "--judge-model",
        type=str,
        help="Override judge model (default: from config/experiment.json)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying files",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Validate experiment directory
    if not args.experiment_dir.exists():
        print(f"❌ Experiment directory not found: {args.experiment_dir}", file=sys.stderr)
        return 1

    if not args.experiment_dir.is_dir():
        print(f"❌ Not a directory: {args.experiment_dir}", file=sys.stderr)
        return 1

    # Import here to avoid slow startup for --help
    from scylla.e2e.regenerate import regenerate_experiment

    try:
        stats = regenerate_experiment(
            experiment_dir=args.experiment_dir,
            rejudge=args.rejudge,
            judge_model=args.judge_model,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        if stats.runs_valid == 0:
            print("\n⚠️  No valid run results found", file=sys.stderr)
            return 1

        print("\n✅ Regeneration complete")
        return 0

    except FileNotFoundError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ Regeneration failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
