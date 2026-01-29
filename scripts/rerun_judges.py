#!/usr/bin/env python3
"""Re-run judges for failed or never-run judge evaluations.

This script scans an experiment directory, identifies individual judge slots
(judge_01, judge_02, judge_03) that need re-execution, and re-runs them.
After re-running, regenerates judge/result.json consensus.

Judge Slot Status Categories:
  - complete:      judgment.json exists and is valid (no action)
  - missing:       judge_NN/ dir doesn't exist
  - failed:        judge_NN/ exists but judgment.json is invalid/missing
  - agent_failed:  Agent failed, cannot judge (skip)

Usage:
    # Scan and re-run all incomplete judge slots
    pixi run python scripts/rerun_judges.py /path/to/experiment/

    # Dry run to see per-slot classification
    pixi run python scripts/rerun_judges.py /path/to/experiment/ --dry-run

    # Only re-run missing judge slots (never ran)
    pixi run python scripts/rerun_judges.py /path/to/experiment/ --status missing

    # Only re-run judge slot 3
    pixi run python scripts/rerun_judges.py /path/to/experiment/ --judge-slot 3

    # Regenerate consensus without re-running judges
    pixi run python scripts/rerun_judges.py /path/to/experiment/ --regenerate-only

Examples:
    # Re-run all incomplete judge slots in an experiment
    pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/

    # Dry run to see per-slot classification
    pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ --dry-run

    # Only re-run missing judge slots
    pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
        --status missing

    # Only re-run judge slot 3 (haiku in 3-judge setup)
    pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
        --judge-slot 3

    # Regenerate consensus files (all judges exist, result.json missing)
    pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking/ \
        --regenerate-only

    # Verbose output for debugging
    pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ -v

Python Justification: Command-line tool for judge re-execution.

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
        description="Re-run judges for failed or never-run judge evaluations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Judge Slot Status Categories:
  complete      - judgment.json exists and is valid (no action)
  missing       - judge_NN/ dir doesn't exist
  failed        - judge_NN/ exists but judgment.json is invalid/missing
  agent_failed  - Agent failed, cannot judge (skip)

Examples:
  # Re-run all incomplete judge slots
  %(prog)s ~/fullruns/test001-nothinking-haiku/

  # Dry run to see per-slot classification
  %(prog)s ~/fullruns/test001-nothinking-haiku/ --dry-run

  # Only re-run missing judge slots
  %(prog)s ~/fullruns/test001-nothinking-haiku/ --status missing

  # Only re-run judge slot 3 (haiku)
  %(prog)s ~/fullruns/test001-nothinking-haiku/ --judge-slot 3

  # Regenerate consensus without re-running judges
  %(prog)s ~/fullruns/test001-nothinking/ --regenerate-only
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
            "complete",
            "missing",
            "failed",
            "agent_failed",
        ],
        help="Only process judge slots with these statuses. Can be used multiple times. "
        "If not specified, processes all non-complete judge slots.",
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
        "--judge-slot",
        action="append",
        type=int,
        dest="judge_slots",
        help="Only process these judge slots (e.g., --judge-slot 1 --judge-slot 3). "
        "Judge numbers match config order: 1=first model, 2=second, 3=third.",
    )

    parser.add_argument(
        "--judge-model",
        type=str,
        help="Judge model to use (DEPRECATED - uses config.judge_models)",
    )

    parser.add_argument(
        "--regenerate-only",
        action="store_true",
        help="Only regenerate judge/result.json consensus from existing per-judge results. "
        "Does not re-run any judges.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main() -> int:
    """Execute the rerun judges command."""
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
        # Import JudgeSlotStatus enum
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from scylla.e2e.rerun_judges import JudgeSlotStatus

        # Map CLI strings to JudgeSlotStatus enum values
        status_map = {
            "complete": JudgeSlotStatus.COMPLETE,
            "missing": JudgeSlotStatus.MISSING,
            "failed": JudgeSlotStatus.FAILED,
            "agent_failed": JudgeSlotStatus.AGENT_FAILED,
        }
        status_filter = [status_map[s] for s in args.statuses]

    # Import here to avoid slow startup for --help
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from scylla.e2e.rerun_judges import rerun_judges_experiment

    try:
        stats = rerun_judges_experiment(
            experiment_dir=args.experiment_dir,
            dry_run=args.dry_run,
            verbose=args.verbose,
            tier_filter=args.tiers,
            subtest_filter=args.subtests,
            run_filter=run_filter,
            judge_slot_filter=args.judge_slots,
            status_filter=status_filter,
            judge_model=args.judge_model,
            regenerate_only=args.regenerate_only,
        )

        # Summary already printed by rerun_judges_experiment()

        if stats.slots_rerun_failed > 0:
            logger.warning(f"{stats.slots_rerun_failed} judge slots failed to rerun")
            return 1

        if not args.dry_run and stats.slots_rerun_success > 0:
            logger.info("✅ Judge slot rerun complete")

        return 0

    except FileNotFoundError as e:
        logger.error(f"{e}")
        return 1
    except Exception as e:
        logger.exception(f"Judge rerun failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
