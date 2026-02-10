#!/usr/bin/env python3
"""Bulk GitHub issue planning script.

Generates implementation plans for GitHub issues using Claude Code
and posts them as issue comments.

Usage:
    python scripts/plan_issues.py --issues 123 456 789
    python scripts/plan_issues.py --issues 123 --force --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path

# Project is installed via editable install, no sys.path manipulation needed
from scylla.automation.models import PlannerOptions
from scylla.automation.planner import Planner


def setup_logging(verbose: bool = False) -> None:
    """Configure logging.

    Args:
        verbose: Enable verbose (DEBUG) logging

    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Bulk plan GitHub issues using Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plan specific issues
  %(prog)s --issues 123 456 789

  # Force re-plan even if plan exists
  %(prog)s --issues 123 --force

  # Dry run (no actual planning)
  %(prog)s --issues 123 --dry-run

  # Use custom system prompt
  %(prog)s --issues 123 --system-prompt .claude/agents/planner.md

  # Plan with more parallelism
  %(prog)s --issues 123 456 789 --parallel 5
        """,
    )

    parser.add_argument(
        "--issues",
        type=int,
        nargs="+",
        required=True,
        help="Issue numbers to plan",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-planning even if plan already exists",
    )

    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        choices=range(1, 33),
        metavar="N",
        help="Number of parallel workers, 1-32 (default: 3)",
    )

    parser.add_argument(
        "--system-prompt",
        type=Path,
        help="Path to system prompt file for Claude Code",
    )

    parser.add_argument(
        "--no-skip-closed",
        action="store_true",
        help="Plan closed issues (default: skip closed issues)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main() -> int:
    """Execute the issue planning workflow."""
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    logger.info("Starting issue planner")
    logger.info(f"Issues to plan: {args.issues}")

    try:
        # Build options
        options = PlannerOptions(
            issues=args.issues,
            dry_run=args.dry_run,
            force=args.force,
            parallel=args.parallel,
            system_prompt_file=args.system_prompt,
            skip_closed=not args.no_skip_closed,
        )

        # Run planner
        planner = Planner(options)
        results = planner.run()

        # Check results
        failed = [num for num, result in results.items() if not result.success]

        if failed:
            logger.error(f"Failed to plan {len(failed)} issue(s): {failed}")
            return 1

        logger.info("Planning complete")
        return 0
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130  # Standard exit code for SIGINT


if __name__ == "__main__":
    sys.exit(main())
