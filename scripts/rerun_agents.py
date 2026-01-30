#!/usr/bin/env python3
"""Re-run agents for failed or never-run experiment runs.

This script scans an experiment directory, identifies runs that need re-execution
(failed agent, never ran, or missing results), and re-executes just those runs.

Run Status Categories:
  - completed: Agent + judge + run_result.json all exist (no action needed)
  - results:   Agent finished, missing result files (regenerate only)
  - failed:    Agent ran but failed (stderr, no valid output)
  - partial:   Agent started but incomplete execution
  - missing:   Run directory doesn't exist

Usage:
    # Scan and re-run all incomplete runs
    pixi run python scripts/rerun_agents.py /path/to/experiment/

    # Dry run to see classification
    pixi run python scripts/rerun_agents.py /path/to/experiment/ --dry-run

    # Only re-run specific statuses
    pixi run python scripts/rerun_agents.py /path/to/experiment/ \
        --status agent-failed --status never-started

    # Only re-run specific tier
    pixi run python scripts/rerun_agents.py /path/to/experiment/ --tier T0

    # Only regenerate runs with deleted run_result.json (no agent rerun)
    pixi run python scripts/rerun_agents.py /path/to/experiment/ \
        --status results

Examples:
    # Re-run all incomplete runs in an experiment
    pixi run python scripts/rerun_agents.py ~/fullruns/test001-nothinking-haiku/

    # Dry run to see classification
    pixi run python scripts/rerun_agents.py ~/fullruns/test001-nothinking-haiku/ --dry-run

    # Only re-run failed agents
    pixi run python scripts/rerun_agents.py ~/fullruns/test001-nothinking-haiku/ \
        --status failed

    # Only regenerate runs with deleted results (fast, no agent execution)
    pixi run python scripts/rerun_agents.py ~/fullruns/test001-nothinking-haiku/ \
        --status results

    # Re-run missing and partial runs only
    pixi run python scripts/rerun_agents.py ~/fullruns/test001-nothinking-haiku/ \
        --status missing --status partial

    # Only re-run T0 tier failed runs
    pixi run python scripts/rerun_agents.py ~/fullruns/test001-nothinking-haiku/ \
        --tier T0 --status agent-failed

    # Verbose output for debugging
    pixi run python scripts/rerun_agents.py ~/fullruns/test001-nothinking-haiku/ -v

Python Justification: Command-line tool for agent re-execution.

"""

import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Re-run agents for failed or never-run experiment runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Run Status Categories:
  completed  - Agent + judge + run_result.json all exist (no action)
  results    - Agent finished but missing result files
  failed     - Agent ran but failed
  partial    - Agent started but incomplete
  missing    - Run directory doesn't exist

Examples:
  # Re-run all incomplete runs
  %(prog)s ~/fullruns/test001-nothinking-haiku/

  # Dry run to see classification
  %(prog)s ~/fullruns/test001-nothinking-haiku/ --dry-run

  # Only re-run failed agents
  %(prog)s ~/fullruns/test001-nothinking-haiku/ --status failed

  # Only regenerate runs with deleted results (fast, no agent execution)
  %(prog)s ~/fullruns/test001-nothinking-haiku/ --status results

  # Re-run missing and partial runs
  %(prog)s ~/fullruns/test001-nothinking-haiku/ \\
      --status missing --status partial

  # Only re-run T0 tier
  %(prog)s ~/fullruns/test001-nothinking-haiku/ --tier T0
        """,
    )

    parser.add_argument(
        "experiment_dir",
        type=Path,
        help="Path to experiment directory",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show classification and what would be done without executing",
    )

    parser.add_argument(
        "--status",
        action="append",
        dest="statuses",
        choices=[
            "completed",
            "results",
            "failed",
            "partial",
            "missing",
        ],
        help="Only process runs with these statuses. Can be used multiple times. "
        "If not specified, processes all non-completed runs.",
    )

    parser.add_argument(
        "--tier",
        action="append",
        dest="tiers",
        help="Only process these tiers (e.g., --tier T0 --tier T1). Can be used multiple times.",
    )

    parser.add_argument(
        "--subtest",
        action="append",
        dest="subtests",
        help=(
            "Only process these subtests (e.g., --subtest 00 --subtest 01). "
            "Can be used multiple times."
        ),
    )

    parser.add_argument(
        "--runs",
        type=str,
        help="Only process these run numbers (comma-separated, e.g., 1,3,5)",
    )

    parser.add_argument(
        "--skip-regenerate",
        action="store_true",
        help="Skip the final regenerate step",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main() -> int:
    """Rerun failed agents in experiments."""
    args = parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate experiment directory
    if not args.experiment_dir.exists():
        logger.error(f"Experiment directory not found: {args.experiment_dir}")
        return 1

    if not args.experiment_dir.is_dir():
        logger.error(f"Not a directory: {args.experiment_dir}")
        return 1

    # Parse run filter
    run_filter = None
    if args.runs:
        try:
            run_filter = [int(r.strip()) for r in args.runs.split(",")]
        except ValueError:
            logger.error(f"Invalid run numbers: {args.runs}")
            return 1

    # Parse status filter
    status_filter = None
    if args.statuses:
        # Import RunStatus enum
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from scylla.e2e.rerun import RunStatus

        # Map CLI strings to RunStatus enum values
        status_map = {
            "completed": RunStatus.COMPLETED,
            "results": RunStatus.RESULTS,
            "failed": RunStatus.FAILED,
            "partial": RunStatus.PARTIAL,
            "missing": RunStatus.MISSING,
        }
        status_filter = [status_map[s] for s in args.statuses]

    # Import here to avoid slow startup for --help
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from scylla.e2e.rerun import rerun_experiment

    try:
        stats = rerun_experiment(
            experiment_dir=args.experiment_dir,
            dry_run=args.dry_run,
            verbose=args.verbose,
            tier_filter=args.tiers,
            subtest_filter=args.subtests,
            run_filter=run_filter,
            status_filter=status_filter,
            skip_regenerate=args.skip_regenerate,
        )

        # Print summary
        stats.print_summary()

        if stats.runs_rerun_failed > 0:
            logger.warning(f"{stats.runs_rerun_failed} runs failed to rerun")
            return 1

        if not args.dry_run:
            logger.info("✅ Rerun complete")

        return 0

    except FileNotFoundError as e:
        logger.error(f"{e}")
        return 1
    except Exception as e:
        logger.exception(f"Rerun failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
