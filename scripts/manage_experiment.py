#!/usr/bin/env python3
r"""Unified experiment management CLI.

Replaces the following individual scripts:
  - run_e2e_experiment.py  (use: manage_experiment.py run)
  - run_e2e_batch.py       (use: manage_experiment.py batch)
  - rerun_agents.py        (use: manage_experiment.py rerun-agents)
  - rerun_judges.py        (use: manage_experiment.py rerun-judges)
  - repair_checkpoint.py   (use: manage_experiment.py repair)
  - regenerate_results.py  (use: manage_experiment.py regenerate)

All subcommands support --until / --until-tier / --until-experiment for
incremental validation: stop execution at a specific state without marking
the run as failed, enabling resume from that point.

Usage:
    # Run experiment (single test)
    python scripts/manage_experiment.py run \\
        --tiers-dir tests/fixtures/tests/test-001 \\
        --tiers T0 --runs 1

    # Batch run all tests
    python scripts/manage_experiment.py batch \\
        --results-dir results/ --threads 4

    # Re-run failed agents
    python scripts/manage_experiment.py rerun-agents /path/to/experiment/

    # Re-run failed judges
    python scripts/manage_experiment.py rerun-judges /path/to/experiment/

    # Repair corrupt checkpoint
    python scripts/manage_experiment.py repair /path/to/checkpoint.json

    # Regenerate reports from existing data
    python scripts/manage_experiment.py regenerate /path/to/experiment/

    # Stop all runs at agent_complete for incremental validation
    python scripts/manage_experiment.py run \\
        --tiers-dir tests/fixtures/tests/test-001 \\
        --tiers T0 --runs 1 --until agent_complete
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Subcommand: run
# ---------------------------------------------------------------------------


def _add_run_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'run' subcommand."""
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to experiment configuration YAML file",
    )
    parser.add_argument("--repo", type=str, help="Task repository URL (default: from test.yaml)")
    parser.add_argument("--commit", type=str, help="Task commit hash (default: from test.yaml)")
    parser.add_argument(
        "--prompt", type=Path, help="Path to task prompt file (default: from test.yaml)"
    )
    parser.add_argument("--experiment-id", type=str, default=None, help="Experiment identifier")
    parser.add_argument(
        "--tiers",
        nargs="+",
        type=str,
        default=["T0", "T1"],
        help="Tiers to run (default: T0 T1)",
    )
    parser.add_argument("--runs", type=int, default=10, help="Runs per sub-test (default: 10)")
    parser.add_argument(
        "--parallel", type=int, default=4, help="Max parallel sub-tests (default: 4)"
    )
    parser.add_argument(
        "--parallel-high",
        type=int,
        default=2,
        help="Max concurrent high-memory operations (default: 2)",
    )
    parser.add_argument(
        "--parallel-med",
        type=int,
        default=4,
        help="Max concurrent medium-memory operations (default: 4)",
    )
    parser.add_argument(
        "--parallel-low",
        type=int,
        default=8,
        help="Max concurrent low-memory operations (default: 8)",
    )
    parser.add_argument(
        "--timeout", type=int, default=3600, help="Timeout per run in seconds (default: 3600)"
    )
    parser.add_argument("--max-subtests", type=int, default=None, help="Limit sub-tests per tier")
    parser.add_argument(
        "--skip-agent-teams", action="store_true", help="Skip agent teams sub-tests"
    )
    parser.add_argument(
        "--use-containers",
        action="store_true",
        help="Run agents/judges in Docker containers",
    )
    parser.add_argument("--model", type=str, default="sonnet", help="Primary model")
    parser.add_argument("--judge-model", type=str, default="sonnet", help="Model for judging")
    parser.add_argument(
        "--add-judge",
        action="append",
        nargs="?",
        const="sonnet",
        metavar="MODEL",
        help="Add additional judge model (use multiple times)",
    )
    parser.add_argument(
        "--skip-judge-validation",
        action="store_true",
        help="Skip model validation for judges",
    )
    parser.add_argument(
        "--thinking",
        choices=["None", "Low", "High", "UltraThink"],
        default="None",
        help="Thinking mode (default: None)",
    )
    parser.add_argument(
        "--tiers-dir",
        type=Path,
        default=Path("tests/claude-code/shared"),
        help="Path to tier configurations (default: tests/claude-code/shared)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Path to results directory (default: results)",
    )
    parser.add_argument(
        "--fresh", action="store_true", help="Start fresh, ignoring existing checkpoint"
    )
    parser.add_argument(
        "--until",
        "--until-run",
        dest="until",
        type=str,
        default=None,
        metavar="STATE",
        help="Stop all runs at this RunState (e.g. agent_complete). "
        "Preserves state for future resume.",
    )
    parser.add_argument(
        "--until-tier",
        type=str,
        default=None,
        metavar="STATE",
        help="Stop each tier at this TierState (e.g. subtests_running). "
        "Preserves state for future resume.",
    )
    parser.add_argument(
        "--until-experiment",
        type=str,
        default=None,
        metavar="STATE",
        help="Stop the experiment at this ExperimentState (e.g. tiers_running). "
        "Preserves state for future resume.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-error output")


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the 'run' subcommand."""
    import yaml

    from scylla.e2e.models import ExperimentConfig, ExperimentState, RunState, TierID, TierState
    from scylla.e2e.runner import run_experiment
    from scylla.utils.terminal import terminal_guard

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    # Load test.yaml defaults if present
    test_config: dict = {}
    if args.tiers_dir and (args.tiers_dir / "test.yaml").exists():
        try:
            from scylla.e2e.models import TestFixture

            fixture = TestFixture.from_directory(args.tiers_dir)
            test_config = {
                "experiment_id": fixture.id,
                "task_repo": fixture.source_repo,
                "task_commit": fixture.source_hash,
                "task_prompt_file": "prompt.md",
                "timeout_seconds": fixture.timeout_seconds,
                "language": fixture.language,
            }
        except Exception:
            with open(args.tiers_dir / "test.yaml") as f:
                raw = yaml.safe_load(f) or {}
            test_config = raw

    # Load YAML config file if provided
    yaml_config: dict = {}
    if args.config and args.config.exists():
        with open(args.config) as f:
            yaml_config = yaml.safe_load(f) or {}

    # Merge: CLI overrides yaml_config overrides test_config
    merged = {**test_config, **yaml_config}

    task_repo = args.repo or merged.get("task_repo") or merged.get("repo")
    task_commit = args.commit or merged.get("task_commit") or merged.get("commit")
    experiment_id = args.experiment_id or merged.get("experiment_id") or "experiment"
    language = merged.get("language", "python")

    # Resolve prompt file
    prompt_file = args.prompt
    if prompt_file is None:
        prompt_name = merged.get("task_prompt_file", "prompt.md")
        prompt_file = args.tiers_dir / prompt_name

    if not task_repo:
        logger.error("--repo is required (or set in test.yaml)")
        return 1
    if not task_commit:
        logger.error("--commit is required (or set in test.yaml)")
        return 1

    # Resolve model IDs
    from scylla.e2e.model_validation import validate_model

    model_map = {
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-5-20251101",
        "haiku": "claude-haiku-4-5-20251001",
    }
    model_id = model_map.get(args.model, args.model)
    judge_model_id = model_map.get(args.judge_model, args.judge_model)
    judge_models = [judge_model_id]
    if args.add_judge:
        for extra_judge in args.add_judge:
            if extra_judge:
                extra_id = model_map.get(extra_judge, extra_judge)
                if extra_id not in judge_models:
                    judge_models.append(extra_id)

    # Validate judges (unless skipped)
    if not args.skip_judge_validation:
        for jm in judge_models:
            if not validate_model(jm):
                logger.warning(f"Judge model {jm!r} may be unavailable")

    # Resolve tiers
    tier_ids = []
    for tier_str in args.tiers:
        try:
            tier_ids.append(TierID[tier_str])
        except KeyError:
            logger.error(f"Unknown tier: {tier_str!r}")
            return 1

    # Parse --until / --until-run state
    until_run_state: RunState | None = None
    if args.until:
        try:
            until_run_state = RunState(args.until)
        except ValueError:
            logger.error(
                f"Unknown --until state: {args.until!r}. "
                f"Valid values: {[s.value for s in RunState]}"
            )
            return 1

    # Parse --until-tier state
    until_tier_state: TierState | None = None
    if args.until_tier:
        try:
            until_tier_state = TierState(args.until_tier)
        except ValueError:
            logger.error(
                f"Unknown --until-tier state: {args.until_tier!r}. "
                f"Valid values: {[s.value for s in TierState]}"
            )
            return 1

    # Parse --until-experiment state
    until_experiment_state: ExperimentState | None = None
    if args.until_experiment:
        try:
            until_experiment_state = ExperimentState(args.until_experiment)
        except ValueError:
            logger.error(
                f"Unknown --until-experiment state: {args.until_experiment!r}. "
                f"Valid values: {[s.value for s in ExperimentState]}"
            )
            return 1

    timeout_seconds = args.timeout or int(merged.get("timeout_seconds", 3600))

    config = ExperimentConfig(
        experiment_id=experiment_id,
        task_repo=task_repo,
        task_commit=task_commit,
        task_prompt_file=prompt_file,
        language=language,
        models=[model_id],
        runs_per_subtest=args.runs,
        judge_models=judge_models,
        parallel_subtests=args.parallel,
        parallel_high=args.parallel_high,
        parallel_med=args.parallel_med,
        parallel_low=args.parallel_low,
        timeout_seconds=timeout_seconds,
        max_subtests=args.max_subtests,
        skip_agent_teams=args.skip_agent_teams,
        use_containers=args.use_containers,
        thinking_mode=args.thinking or "None",
        tiers_to_run=tier_ids,
        until_run_state=until_run_state,
        until_tier_state=until_tier_state,
        until_experiment_state=until_experiment_state,
    )

    with terminal_guard():
        results = run_experiment(
            config=config,
            tiers_dir=args.tiers_dir,
            results_dir=args.results_dir,
            fresh=args.fresh,
        )

    if results:
        logger.info("Experiment complete")
        return 0
    else:
        logger.error("Experiment failed or returned no results")
        return 1


# ---------------------------------------------------------------------------
# Subcommand: batch
# ---------------------------------------------------------------------------


def _add_batch_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'batch' subcommand."""
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results"), help="Output directory"
    )
    parser.add_argument("--threads", type=int, default=4, help="Parallel threads (default: 4)")
    parser.add_argument("--model", type=str, default="sonnet", help="Primary model")
    parser.add_argument("--judge-model", type=str, default="sonnet", help="Judge model")
    parser.add_argument(
        "--tiers", nargs="+", type=str, default=None, help="Filter to specific tiers"
    )
    parser.add_argument(
        "--tests", nargs="+", type=str, default=None, help="Filter to specific test IDs"
    )
    parser.add_argument("--runs", type=int, default=10, help="Runs per sub-test (default: 10)")
    parser.add_argument("--max-subtests", type=int, default=None, help="Limit sub-tests per tier")
    parser.add_argument(
        "--thinking",
        choices=["None", "Low", "High", "UltraThink"],
        default="None",
        help="Thinking mode",
    )
    parser.add_argument("--fresh", action="store_true", help="Clear batch summary and restart")
    parser.add_argument("--retry-errors", action="store_true", help="Re-run failed tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")


def cmd_batch(args: argparse.Namespace) -> int:
    """Execute the 'batch' subcommand — delegates to run_e2e_batch logic."""
    import scripts.run_e2e_batch as batch_module

    # Build argv list and pass it directly to the parser to avoid mutating sys.argv
    argv: list[str] = []
    if args.results_dir:
        argv += ["--results-dir", str(args.results_dir)]
    if args.threads:
        argv += ["--threads", str(args.threads)]
    if args.model:
        argv += ["--model", args.model]
    if args.judge_model:
        argv += ["--judge-model", args.judge_model]
    if args.tiers:
        argv += ["--tiers"] + args.tiers
    if args.tests:
        argv += ["--tests"] + args.tests
    if args.runs:
        argv += ["--runs", str(args.runs)]
    if args.max_subtests:
        argv += ["--max-subtests", str(args.max_subtests)]
    if args.thinking and args.thinking != "None":
        argv += ["--thinking", args.thinking]
    if args.fresh:
        argv.append("--fresh")
    if args.retry_errors:
        argv.append("--retry-errors")
    if args.verbose:
        argv.append("-v")

    return batch_module.main(argv=argv)


# ---------------------------------------------------------------------------
# Subcommand: rerun-agents
# ---------------------------------------------------------------------------


def _add_rerun_agents_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'rerun-agents' subcommand."""
    parser.add_argument("experiment_dir", type=Path, help="Path to experiment directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument(
        "--status",
        action="append",
        default=None,
        metavar="STATUS",
        help="Filter by run status (may repeat). Choices: completed/results/failed/partial/missing",
    )
    parser.add_argument("--tier", type=str, default=None, help="Filter to specific tier")
    parser.add_argument("--subtest", type=str, default=None, help="Filter to specific subtest")
    parser.add_argument(
        "--runs", nargs="+", type=int, default=None, help="Filter to specific run numbers"
    )
    parser.add_argument(
        "--skip-regenerate",
        action="store_true",
        help="Skip final regenerate step after re-running",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")


def cmd_rerun_agents(args: argparse.Namespace) -> int:
    """Execute the 'rerun-agents' subcommand."""
    from scylla.e2e.rerun import rerun_experiment

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    rerun_experiment(
        experiment_dir=args.experiment_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
        tier_filter=args.tier,
        subtest_filter=args.subtest,
        run_filter=args.runs,
        status_filter=args.status,
        skip_regenerate=args.skip_regenerate,
    )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: rerun-judges
# ---------------------------------------------------------------------------


def _add_rerun_judges_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'rerun-judges' subcommand."""
    parser.add_argument("experiment_dir", type=Path, help="Path to experiment directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument(
        "--status",
        action="append",
        default=None,
        metavar="STATUS",
        help="Filter by status (complete/missing/failed/agent_failed)",
    )
    parser.add_argument("--tier", type=str, default=None, help="Filter to specific tier")
    parser.add_argument("--subtest", type=str, default=None, help="Filter to specific subtest")
    parser.add_argument(
        "--runs", nargs="+", type=int, default=None, help="Filter to specific run numbers"
    )
    parser.add_argument(
        "--judge-slot",
        nargs="+",
        type=int,
        default=None,
        help="Filter to specific judge slot numbers (1-indexed)",
    )
    parser.add_argument(
        "--regenerate-only",
        action="store_true",
        help="Only regenerate consensus (no re-run)",
    )
    parser.add_argument(
        "--parallel", type=int, default=1, help="Number of parallel judge slots (default: 1)"
    )
    parser.add_argument("--judge-model", type=str, default=None, help="Override judge model")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")


def cmd_rerun_judges(args: argparse.Namespace) -> int:
    """Execute the 'rerun-judges' subcommand."""
    from scylla.e2e.rerun_judges import rerun_judges_experiment

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    rerun_judges_experiment(
        experiment_dir=args.experiment_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
        tier_filter=args.tier,
        subtest_filter=args.subtest,
        run_filter=args.runs,
        judge_slot_filter=args.judge_slot,
        status_filter=args.status,
        judge_model=args.judge_model,
        regenerate_only=args.regenerate_only,
        parallel=args.parallel,
    )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: repair
# ---------------------------------------------------------------------------


def _add_repair_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'repair' subcommand."""
    parser.add_argument("checkpoint_path", type=Path, help="Path to checkpoint JSON file")


def cmd_repair(args: argparse.Namespace) -> int:
    """Execute the 'repair' subcommand."""
    import json

    from scylla.e2e.checkpoint import load_checkpoint, save_checkpoint

    checkpoint_path = args.checkpoint_path
    if not checkpoint_path.exists():
        logger.error(f"Checkpoint not found: {checkpoint_path}")
        return 1

    logger.info(f"Repairing checkpoint: {checkpoint_path}")

    checkpoint = load_checkpoint(checkpoint_path)
    experiment_dir = Path(checkpoint.experiment_dir)

    fixed_count = 0
    for tier_id in checkpoint.run_states:
        for subtest_id in checkpoint.run_states[tier_id]:
            for run_num_str in checkpoint.run_states[tier_id][subtest_id]:
                run_num = int(run_num_str)
                run_result_path = (
                    experiment_dir / tier_id / subtest_id / f"run_{run_num:02d}" / "run_result.json"
                )
                if run_result_path.exists():
                    try:
                        result_data = json.loads(run_result_path.read_text())
                        passed = result_data.get("judge_passed", False)
                        status = "passed" if passed else "failed"
                        existing = (
                            checkpoint.completed_runs.get(tier_id, {})
                            .get(subtest_id, {})
                            .get(run_num)
                        )
                        if existing is None:
                            if tier_id not in checkpoint.completed_runs:
                                checkpoint.completed_runs[tier_id] = {}
                            if subtest_id not in checkpoint.completed_runs[tier_id]:
                                checkpoint.completed_runs[tier_id][subtest_id] = {}
                            checkpoint.completed_runs[tier_id][subtest_id][run_num] = status
                            fixed_count += 1
                            logger.info(
                                f"Repaired: {tier_id}/{subtest_id}/run_{run_num:02d} = {status}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Could not repair {tier_id}/{subtest_id}/run_{run_num:02d}: {e}"
                        )

    if fixed_count > 0:
        save_checkpoint(checkpoint, checkpoint_path)
        logger.info(f"Repaired {fixed_count} run(s). Checkpoint saved.")
    else:
        logger.info("No repairs needed.")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: regenerate
# ---------------------------------------------------------------------------


def _add_regenerate_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'regenerate' subcommand."""
    parser.add_argument("experiment_dir", type=Path, help="Path to experiment directory")
    parser.add_argument(
        "--rejudge", action="store_true", help="Re-run judges for runs missing judge results"
    )
    parser.add_argument("--judge-model", type=str, default=None, help="Override judge model")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")


def cmd_regenerate(args: argparse.Namespace) -> int:
    """Execute the 'regenerate' subcommand."""
    from scylla.e2e.regenerate import regenerate_experiment

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    regenerate_experiment(
        experiment_dir=args.experiment_dir,
        rejudge=args.rejudge,
        judge_model=args.judge_model,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="manage_experiment.py",
        description="Unified experiment management CLI for ProjectScylla E2E testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Subcommands:
  run           Run a single experiment (replaces run_e2e_experiment.py)
  batch         Run all tests in parallel (replaces run_e2e_batch.py)
  rerun-agents  Re-run failed agent executions (replaces rerun_agents.py)
  rerun-judges  Re-run failed judge evaluations (replaces rerun_judges.py)
  repair        Repair corrupt checkpoint (replaces repair_checkpoint.py)
  regenerate    Rebuild reports from existing data (replaces regenerate_results.py)

Use 'manage_experiment.py <subcommand> --help' for subcommand-specific options.
        """,
    )

    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")
    subparsers.required = True

    # run subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Run a single E2E experiment",
        description="Run a single E2E experiment with specified tiers and configuration.",
    )
    _add_run_args(run_parser)

    # batch subcommand
    batch_parser = subparsers.add_parser(
        "batch",
        help="Run all tests in parallel (batch mode)",
        description="Run all E2E tests across multiple threads with load balancing.",
    )
    _add_batch_args(batch_parser)

    # rerun-agents subcommand
    rerun_agents_parser = subparsers.add_parser(
        "rerun-agents",
        help="Re-run failed/incomplete agent executions",
        description="Scan experiment, identify incomplete runs, and re-execute agents.",
    )
    _add_rerun_agents_args(rerun_agents_parser)

    # rerun-judges subcommand
    rerun_judges_parser = subparsers.add_parser(
        "rerun-judges",
        help="Re-run failed/incomplete judge evaluations",
        description="Scan experiment, identify incomplete judge slots, and re-run them.",
    )
    _add_rerun_judges_args(rerun_judges_parser)

    # repair subcommand
    repair_parser = subparsers.add_parser(
        "repair",
        help="Repair corrupt checkpoint by rebuilding from run_result.json files",
        description="Fix checkpoints where completed_runs is empty despite having completed runs.",
    )
    _add_repair_args(repair_parser)

    # regenerate subcommand
    regenerate_parser = subparsers.add_parser(
        "regenerate",
        help="Regenerate reports from existing run data",
        description="Rebuild results.json and reports from existing run_result.json files.",
    )
    _add_regenerate_args(regenerate_parser)

    return parser


def main() -> int:
    """Run the experiment management CLI."""
    parser = build_parser()
    args = parser.parse_args()

    subcommand_map = {
        "run": cmd_run,
        "batch": cmd_batch,
        "rerun-agents": cmd_rerun_agents,
        "rerun-judges": cmd_rerun_judges,
        "repair": cmd_repair,
        "regenerate": cmd_regenerate,
    }

    handler = subcommand_map.get(args.subcommand)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
