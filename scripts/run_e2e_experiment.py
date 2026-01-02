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
    # Minimal: just specify tiers-dir (repo, commit, prompt from test.yaml)
    python scripts/run_e2e_experiment.py \\
        --tiers-dir tests/fixtures/tests/test-001 \\
        --tiers T0 --runs 1

    # Quick T0 validation
    python scripts/run_e2e_experiment.py \\
        --tiers-dir tests/fixtures/tests/test-001 \\
        --tiers T0 --runs 1 -v

    # Run all tiers with defaults from test.yaml
    python scripts/run_e2e_experiment.py \\
        --tiers-dir tests/fixtures/tests/test-001 \\
        --tiers T0 T1 T2 T3 T4 T5 T6

    # Override repo/commit from CLI
    python scripts/run_e2e_experiment.py \\
        --tiers-dir tests/fixtures/tests/test-001 \\
        --repo https://github.com/example/repo \\
        --commit abc123 \\
        --tiers T0 T1
        """,
    )

    # Config file
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to experiment configuration YAML file",
    )

    # Direct arguments (override config) - all optional if test.yaml exists
    parser.add_argument(
        "--repo",
        type=str,
        help="Task repository URL (default: from test.yaml)",
    )
    parser.add_argument(
        "--commit",
        type=str,
        help="Task commit hash (default: from test.yaml)",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        help="Path to task prompt file (default: from test.yaml)",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Experiment identifier (default: from test.yaml id)",
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
        help="Timeout per run in seconds (default: from test.yaml or 3600)",
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


def load_test_config(tiers_dir: Path) -> dict | None:
    """Load test configuration from test.yaml in tiers directory.

    This provides default values for repo, commit, prompt, timeout, and experiment-id.

    Args:
        tiers_dir: Path to tier configurations directory

    Returns:
        Configuration dictionary or None if not found
    """
    test_yaml = tiers_dir / "test.yaml"
    if not test_yaml.exists():
        return None

    with open(test_yaml) as f:
        config = yaml.safe_load(f) or {}

    return {
        "experiment_id": config.get("id"),
        "task_repo": config.get("source", {}).get("repo"),
        "task_commit": config.get("source", {}).get("hash"),
        "task_prompt_file": config.get("task", {}).get("prompt_file"),
        "timeout_seconds": config.get("task", {}).get("timeout_seconds"),
        "tiers": config.get("tiers"),
    }


def build_config(args: argparse.Namespace) -> ExperimentConfig:
    """Build experiment configuration from arguments.

    Priority (highest to lowest):
    1. CLI arguments (--repo, --commit, etc.)
    2. Config YAML file (--config)
    3. Test config (test.yaml in --tiers-dir)
    4. Defaults

    Args:
        args: Parsed command-line arguments

    Returns:
        ExperimentConfig instance
    """
    # Load test config from tiers-dir (provides defaults for repo, commit, prompt, etc.)
    test_config = load_test_config(args.tiers_dir)

    # Start with defaults, using test config if available
    config_dict = {
        "experiment_id": args.experiment_id or (test_config.get("experiment_id") if test_config else None) or "experiment",
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

    # Apply test config defaults (from test.yaml in tiers-dir)
    if test_config:
        if test_config.get("task_repo"):
            config_dict["task_repo"] = test_config["task_repo"]
        if test_config.get("task_commit"):
            config_dict["task_commit"] = test_config["task_commit"]
        if test_config.get("task_prompt_file"):
            # Resolve prompt file relative to tiers-dir
            config_dict["task_prompt_file"] = args.tiers_dir / test_config["task_prompt_file"]
        if test_config.get("timeout_seconds") and args.timeout == 3600:  # Only if not explicitly set
            config_dict["timeout_seconds"] = test_config["timeout_seconds"]

    # Load from YAML config if provided (overrides test config)
    if args.config:
        yaml_config = load_config_from_yaml(args.config)
        if yaml_config.get("experiment_id"):
            config_dict["experiment_id"] = yaml_config["experiment_id"]
        if yaml_config.get("task_repo"):
            config_dict["task_repo"] = yaml_config["task_repo"]
        if yaml_config.get("task_commit"):
            config_dict["task_commit"] = yaml_config["task_commit"]
        if yaml_config.get("task_prompt_file"):
            config_dict["task_prompt_file"] = Path(yaml_config["task_prompt_file"])
        if yaml_config.get("runs_per_subtest"):
            config_dict["runs_per_subtest"] = yaml_config["runs_per_subtest"]
        if yaml_config.get("tiers"):
            config_dict["tiers_to_run"] = [TierID.from_string(t) for t in yaml_config["tiers"]]

    # Override with CLI arguments (highest priority)
    if args.repo:
        config_dict["task_repo"] = args.repo
    if args.commit:
        config_dict["task_commit"] = args.commit
    if args.prompt:
        config_dict["task_prompt_file"] = args.prompt

    # Validate required fields
    if not config_dict["task_repo"]:
        raise ValueError("Task repository required: set in test.yaml, --config, or --repo")
    if not config_dict["task_prompt_file"]:
        raise ValueError("Task prompt required: set in test.yaml, --config, or --prompt")

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
