#!/usr/bin/env python3
"""Bulk GitHub issue implementation script.

Implements GitHub issues in parallel using Claude Code in isolated
git worktrees with dependency resolution.

Usage:
    python scripts/implement_issues.py --epic 123
    python scripts/implement_issues.py --epic 123 --analyze
    python scripts/implement_issues.py --health-check
"""

import argparse
import logging
import sys

# Project is installed via editable install, no sys.path manipulation needed
from scylla.automation.implementer import IssueImplementer
from scylla.automation.models import ImplementerOptions


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
        description="Bulk implement GitHub issues using Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Implement all issues in an epic
  %(prog)s --epic 123

  # Implement specific issues
  %(prog)s --issues 595 596 597

  # Implement a single issue
  %(prog)s --issues 595

  # Analyze dependencies without implementing
  %(prog)s --epic 123 --analyze

  # Resume previous implementation
  %(prog)s --epic 123 --resume

  # Health check
  %(prog)s --health-check

  # Dry run
  %(prog)s --issues 595 --dry-run

  # Use more workers
  %(prog)s --epic 123 --max-workers 5

  # Don't auto-merge PRs
  %(prog)s --issues 595 --no-auto-merge
        """,
    )

    parser.add_argument(
        "--epic",
        type=int,
        help="Epic issue number containing sub-issues",
    )

    parser.add_argument(
        "--issues",
        type=int,
        nargs="+",
        help="Specific issue numbers to implement (alternative to --epic)",
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze dependencies without implementing",
    )

    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run health check of dependencies and environment",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume previous implementation from saved state",
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        choices=range(1, 33),
        metavar="N",
        help="Maximum number of parallel workers, 1-32 (default: 3)",
    )

    parser.add_argument(
        "--no-skip-closed",
        action="store_true",
        help="Implement closed issues (default: skip closed issues)",
    )

    parser.add_argument(
        "--no-auto-merge",
        action="store_true",
        help="Don't enable auto-merge on created PRs",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )

    parser.add_argument(
        "--no-retrospective",
        action="store_true",
        help="Disable /retrospective after implementation (enabled by default)",
    )

    parser.add_argument(
        "--no-follow-up",
        action="store_true",
        help="Disable automatic filing of follow-up issues (enabled by default)",
    )

    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Disable curses UI (use plain logging instead)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Validation
    if not args.health_check and not args.epic and not args.issues:
        parser.error("Either --epic, --issues, or --health-check is required")

    if args.epic and args.issues:
        parser.error("Cannot specify both --epic and --issues")

    return args


def main() -> int:
    """Execute the issue implementation workflow."""
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # Build options
    options = ImplementerOptions(
        epic_number=args.epic or 0,
        issues=args.issues or [],
        analyze_only=args.analyze,
        health_check=args.health_check,
        resume=args.resume,
        max_workers=args.max_workers,
        skip_closed=not args.no_skip_closed,
        auto_merge=not args.no_auto_merge,
        dry_run=args.dry_run,
        enable_retrospective=not args.no_retrospective,
        enable_follow_up=not args.no_follow_up,
        enable_ui=not args.no_ui,
    )

    if args.health_check:
        logger.info("Running health check")
    elif args.issues:
        logger.info(f"Starting implementation of issues: {args.issues}")
    else:
        logger.info(f"Starting implementation of epic #{args.epic}")

    try:
        # Run implementer
        implementer = IssueImplementer(options)
        results = implementer.run()

        # Check results
        if not args.health_check and not args.analyze:
            failed = [num for num, result in results.items() if not result.success]

            if failed:
                logger.error(f"Failed to implement {len(failed)} issue(s): {failed}")
                return 1

        logger.info("Complete")
        return 0
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130  # Standard exit code for SIGINT


if __name__ == "__main__":
    sys.exit(main())
