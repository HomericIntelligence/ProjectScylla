#!/usr/bin/env python3
"""CLI entry point for E2E experiments.

This script provides a command-line interface for running E2E experiments
with the ProjectScylla evaluation framework.

Usage:
    python scripts/run_e2e_experiment.py --config experiment.yaml
    python scripts/run_e2e_experiment.py --repo <url> --commit <hash> --prompt <file>

Python Justification: Required for CLI argument parsing and experiment orchestration.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scylla.e2e.models import ExperimentConfig, TierID
from scylla.e2e.runner import run_experiment

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
        description="Run E2E experiments with ProjectScylla",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with config file
    python scripts/run_e2e_experiment.py --config experiments/hello-world.yaml

    # Run with CLI arguments
    python scripts/run_e2e_experiment.py \\
        --repo https://github.com/octocat/Hello-World \\
        --commit 7fd1a60 \\
        --prompt tests/fixtures/tests/test-001/prompt.md \\
        --tiers T0 T1 T2

    # Quick test with fewer runs
    python scripts/run_e2e_experiment.py \\
        --config experiments/test.yaml \\
        --runs 3 \\
        --tiers T0 T1
        """,
    )

    # Config file
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to experiment configuration YAML file",
    )

    # Direct arguments (override config)
    parser.add_argument(
        "--repo",
        type=str,
        help="Task repository URL",
    )
    parser.add_argument(
        "--commit",
        type=str,
        help="Task commit hash",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        help="Path to task prompt file",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default="experiment",
        help="Experiment identifier (default: experiment)",
    )

    # Tier selection
    parser.add_argument(
        "--tiers",
        nargs="+",
        type=str,
        default=["T0", "T1"],
        help="Tiers to run (default: T0 T1)",
    )

    # Run settings
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Runs per sub-test (default: 10)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=4,
        help="Max parallel sub-tests (default: 4)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Timeout per run in seconds (default: 3600)",
    )

    # Model settings
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-5-20250929",
        help="Primary model for task execution",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default="claude-opus-4-5-20251101",
        help="Model for judging (default: claude-opus-4-5-20251101)",
    )
    parser.add_argument(
        "--tiebreaker-model",
        type=str,
        default="opus-4.5",
        help="Model for tie-breaking (default: opus-4.5)",
    )

    # Paths
    parser.add_argument(
        "--tiers-dir",
        type=Path,
        default=Path("config/tiers"),
        help="Path to tier configurations (default: config/tiers)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Path to results directory (default: results)",
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )

    return parser.parse_args()


def load_config_from_yaml(path: Path) -> dict:
    """Load configuration from YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Configuration dictionary
    """
    with open(path) as f:
        return yaml.safe_load(f) or {}


def build_config(args: argparse.Namespace) -> ExperimentConfig:
    """Build experiment configuration from arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        ExperimentConfig instance
    """
    # Start with defaults
    config_dict = {
        "experiment_id": args.experiment_id,
        "task_repo": "",
        "task_commit": "",
        "task_prompt_file": None,
        "models": [args.model],
        "runs_per_subtest": args.runs,
        "tiers_to_run": [TierID.from_string(t) for t in args.tiers],
        "judge_model": args.judge_model,
        "tiebreaker_model": args.tiebreaker_model,
        "parallel_subtests": args.parallel,
        "timeout_seconds": args.timeout,
    }

    # Load from YAML if provided
    if args.config:
        yaml_config = load_config_from_yaml(args.config)
        config_dict.update({
            "experiment_id": yaml_config.get("experiment_id", config_dict["experiment_id"]),
            "task_repo": yaml_config.get("task_repo", config_dict["task_repo"]),
            "task_commit": yaml_config.get("task_commit", config_dict["task_commit"]),
            "task_prompt_file": Path(yaml_config["task_prompt_file"]) if yaml_config.get("task_prompt_file") else None,
            "runs_per_subtest": yaml_config.get("runs_per_subtest", config_dict["runs_per_subtest"]),
            "tiers_to_run": [TierID.from_string(t) for t in yaml_config.get("tiers", args.tiers)],
        })

    # Override with CLI arguments
    if args.repo:
        config_dict["task_repo"] = args.repo
    if args.commit:
        config_dict["task_commit"] = args.commit
    if args.prompt:
        config_dict["task_prompt_file"] = args.prompt

    # Validate required fields
    if not config_dict["task_repo"]:
        raise ValueError("Task repository (--repo) is required")
    if not config_dict["task_prompt_file"]:
        raise ValueError("Task prompt file (--prompt) is required")

    return ExperimentConfig(
        experiment_id=config_dict["experiment_id"],
        task_repo=config_dict["task_repo"],
        task_commit=config_dict["task_commit"] or "",
        task_prompt_file=config_dict["task_prompt_file"],
        models=config_dict["models"],
        runs_per_subtest=config_dict["runs_per_subtest"],
        tiers_to_run=config_dict["tiers_to_run"],
        judge_model=config_dict["judge_model"],
        tiebreaker_model=config_dict["tiebreaker_model"],
        parallel_subtests=config_dict["parallel_subtests"],
        timeout_seconds=config_dict["timeout_seconds"],
    )


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    args = parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    try:
        # Build configuration
        config = build_config(args)

        logger.info(f"Starting experiment: {config.experiment_id}")
        logger.info(f"Task repo: {config.task_repo}")
        logger.info(f"Tiers: {[t.value for t in config.tiers_to_run]}")
        logger.info(f"Runs per sub-test: {config.runs_per_subtest}")

        # Ensure directories exist
        args.tiers_dir.mkdir(parents=True, exist_ok=True)
        args.results_dir.mkdir(parents=True, exist_ok=True)

        # Run experiment
        result = run_experiment(
            config=config,
            tiers_dir=args.tiers_dir,
            results_dir=args.results_dir,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(f"Duration: {result.total_duration_seconds:.1f}s")
        print(f"Total Cost: ${result.total_cost:.4f}")
        print()

        if result.best_overall_tier:
            print(f"Best Tier: {result.best_overall_tier.value}")
            print(f"Best Sub-test: {result.best_overall_subtest}")
            print(f"Frontier CoP: ${result.frontier_cop:.4f}")
        else:
            print("No passing results found")

        print()
        print("Tier Results:")
        print("-" * 60)
        for tier_id in config.tiers_to_run:
            tier_result = result.tier_results.get(tier_id)
            if tier_result:
                status = "PASS" if tier_result.best_subtest_score > 0.5 else "FAIL"
                print(
                    f"  {tier_id.value}: {status} "
                    f"(score: {tier_result.best_subtest_score:.3f}, "
                    f"cost: ${tier_result.total_cost:.4f})"
                )

        print("=" * 60)

        return 0

    except KeyboardInterrupt:
        logger.warning("Experiment interrupted by user")
        return 130

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    except Exception as e:
        logger.exception(f"Experiment failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
