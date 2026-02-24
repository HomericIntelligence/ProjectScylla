#!/usr/bin/env python3
r"""Unified experiment management CLI.

Replaces the following individual scripts:
  - run_e2e_experiment.py  (use: manage_experiment.py run)
  - run_e2e_batch.py       (use: manage_experiment.py run --config <dir>/)
  - rerun_agents.py        (use: manage_experiment.py run --from replay_generated)
  - rerun_judges.py        (use: manage_experiment.py run --from judge_pipeline_run)
  - regenerate_results.py  (use: manage_experiment.py run --from run_finalized)
  - repair_checkpoint.py   (use: manage_experiment.py repair)

All subcommands support --until / --until-tier / --until-experiment for
incremental validation: stop execution at a specific state (inclusive) without
marking the run as failed, enabling resume from that point.

Usage:
    # Run experiment (single test)
    python scripts/manage_experiment.py run \\
        --config tests/fixtures/tests/test-001 \\
        --tiers T0 --runs 1

    # Batch run all tests in a parent dir
    python scripts/manage_experiment.py run \\
        --config tests/fixtures/tests/ --threads 4

    # Batch run specific tests
    python scripts/manage_experiment.py run \\
        --config tests/fixtures/tests/ --tests test-001 test-005

    # Re-run agents (from replay_generated forward)
    python scripts/manage_experiment.py run \\
        --config tests/fixtures/tests/test-001 --from replay_generated \\
        --filter-tier T0 --filter-status failed

    # Re-run judges (from judge_pipeline_run forward)
    python scripts/manage_experiment.py run \\
        --config tests/fixtures/tests/test-001 --from judge_pipeline_run \\
        --filter-tier T0

    # Regenerate reports from existing data
    python scripts/manage_experiment.py run \\
        --config tests/fixtures/tests/test-001 --from run_finalized

    # Repair corrupt checkpoint
    python scripts/manage_experiment.py repair /path/to/checkpoint.json

    # Stop all runs after agent_complete for incremental validation (inclusive)
    python scripts/manage_experiment.py run \\
        --config tests/fixtures/tests/test-001 \\
        --tiers T0 --runs 1 --until agent_complete
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

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
        action="append",
        type=Path,
        default=None,
        help="Path to test config directory or YAML file (repeatable for batch mode). "
        "When a single directory containing test-* subdirs is given, auto-expands "
        "to batch mode. When specified multiple times, runs all tests in parallel.",
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
        help="Stop all runs AFTER reaching this RunState (inclusive). "
        "E.g., --until agent_complete executes the agent and stops. "
        "Preserves state for future resume.",
    )
    parser.add_argument(
        "--until-tier",
        type=str,
        default=None,
        metavar="STATE",
        help="Stop each tier AFTER reaching this TierState (inclusive). "
        "Preserves state for future resume.",
    )
    parser.add_argument(
        "--until-experiment",
        type=str,
        default=None,
        metavar="STATE",
        help="Stop the experiment AFTER reaching this ExperimentState (inclusive). "
        "Preserves state for future resume.",
    )
    # --from arguments for re-execution
    parser.add_argument(
        "--from",
        "--from-run",
        dest="from_run",
        type=str,
        default=None,
        metavar="STATE",
        help="Reset runs to PENDING and re-execute from this RunState forward. "
        "E.g., --from replay_generated to re-run agents. "
        "Requires an existing experiment with a checkpoint.",
    )
    parser.add_argument(
        "--from-tier",
        type=str,
        default=None,
        metavar="STATE",
        help="Reset tiers to before this TierState and re-execute.",
    )
    parser.add_argument(
        "--from-experiment",
        type=str,
        default=None,
        metavar="STATE",
        help="Reset experiment to this ExperimentState and re-execute.",
    )
    # Filter arguments for --from
    parser.add_argument(
        "--filter-tier",
        action="append",
        type=str,
        default=None,
        help="Only apply --from to these tiers (repeatable)",
    )
    parser.add_argument(
        "--filter-subtest",
        action="append",
        type=str,
        default=None,
        help="Only apply --from to these subtests (repeatable)",
    )
    parser.add_argument(
        "--filter-run",
        action="append",
        type=int,
        default=None,
        help="Only apply --from to these run numbers (repeatable)",
    )
    parser.add_argument(
        "--filter-status",
        action="append",
        type=str,
        default=None,
        help="Only apply --from to runs with these statuses: passed/failed/agent_complete",
    )
    parser.add_argument(
        "--filter-judge-slot",
        action="append",
        type=int,
        default=None,
        help="Only apply --from to these judge slot numbers (1-indexed). "
        "NOTE: judge-slot-level filtering is not yet implemented in the reset logic; "
        "this argument is accepted but has no effect.",
    )
    # Batch mode arguments
    parser.add_argument(
        "--threads", type=int, default=4, help="Parallel threads for batch mode (default: 4)"
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        type=str,
        default=None,
        help="Filter to specific test IDs (batch mode)",
    )
    parser.add_argument(
        "--retry-errors", action="store_true", help="Re-run failed tests (batch mode)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-error output")


def _run_batch(test_dirs: list[Path], args: argparse.Namespace) -> int:
    """Run multiple tests using in-process ThreadPoolExecutor.

    Each test runs run_experiment() directly in its own thread.
    Results are saved incrementally to batch_summary.json.

    Args:
        test_dirs: List of test directories to run
        args: Parsed CLI arguments

    Returns:
        0 on success, 1 on failure

    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime, timezone

    import yaml

    from scylla.e2e.models import ExperimentConfig, ExperimentState, RunState, TierID, TierState
    from scylla.e2e.runner import run_experiment
    from scylla.utils.terminal import terminal_guard

    _save_lock = threading.Lock()

    def save_result(result: dict) -> None:
        """Save a single result to batch_summary.json (thread-safe)."""
        import json

        summary_path = args.results_dir / "batch_summary.json"
        tmp_path = args.results_dir / f"batch_summary.json.tmp.{threading.get_ident()}"
        with _save_lock:
            if summary_path.exists():
                try:
                    with open(summary_path) as f:
                        summary = json.load(f)
                except Exception:
                    summary = {"results": []}
            else:
                summary = {"results": []}
            summary["results"].append(result)
            with open(tmp_path, "w") as f:
                json.dump(summary, f, indent=2)
            tmp_path.rename(summary_path)

    def run_one_test(test_dir: Path) -> dict:
        """Run a single test and return result dict."""
        test_id = test_dir.name
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            # Load test.yaml
            test_config: dict = {}
            if (test_dir / "test.yaml").exists():
                try:
                    from scylla.e2e.models import TestFixture

                    fixture = TestFixture.from_directory(test_dir)
                    test_config = {
                        "experiment_id": fixture.id,
                        "task_repo": fixture.source_repo,
                        "task_commit": fixture.source_hash,
                        "task_prompt_file": "prompt.md",
                        "timeout_seconds": fixture.timeout_seconds,
                        "language": fixture.language,
                    }
                except Exception:
                    with open(test_dir / "test.yaml") as f:
                        test_config = yaml.safe_load(f) or {}

            task_repo = args.repo or test_config.get("task_repo") or test_config.get("repo")
            task_commit = args.commit or test_config.get("task_commit") or test_config.get("commit")
            experiment_id = args.experiment_id or test_config.get("experiment_id") or test_id
            language = test_config.get("language", "python")

            prompt_file = args.prompt
            if prompt_file is None:
                prompt_name = test_config.get("task_prompt_file", "prompt.md")
                prompt_file = test_dir / prompt_name

            if not task_repo or not task_commit:
                return {
                    "test_id": test_id,
                    "status": "error",
                    "error": "Missing task_repo or task_commit",
                }

            model_map = {
                "sonnet": "claude-sonnet-4-5-20250929",
                "opus": "claude-opus-4-5-20251101",
                "haiku": "claude-haiku-4-5-20251001",
            }
            model_id = model_map.get(args.model, args.model)
            judge_model_id = model_map.get(args.judge_model, args.judge_model)

            tier_ids = []
            for tier_str in args.tiers:
                tier_ids.append(TierID[tier_str])

            until_run_state: RunState | None = None
            if args.until:
                until_run_state = RunState(args.until)

            until_tier_state: TierState | None = None
            if args.until_tier:
                until_tier_state = TierState(args.until_tier)

            until_experiment_state: ExperimentState | None = None
            if args.until_experiment:
                until_experiment_state = ExperimentState(args.until_experiment)

            from_run_state: RunState | None = None
            if args.from_run:
                from_run_state = RunState(args.from_run)

            from_tier_state: TierState | None = None
            if args.from_tier:
                from_tier_state = TierState(args.from_tier)

            from_experiment_state: ExperimentState | None = None
            if args.from_experiment:
                from_experiment_state = ExperimentState(args.from_experiment)

            timeout_seconds = args.timeout or int(test_config.get("timeout_seconds", 3600))

            config = ExperimentConfig(
                experiment_id=experiment_id,
                task_repo=task_repo,
                task_commit=task_commit,
                task_prompt_file=prompt_file,
                language=language,
                models=[model_id],
                runs_per_subtest=args.runs,
                judge_models=[judge_model_id],
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
                from_run_state=from_run_state,
                from_tier_state=from_tier_state,
                from_experiment_state=from_experiment_state,
                filter_tiers=args.filter_tier,
                filter_subtests=args.filter_subtest,
                filter_runs=args.filter_run,
                filter_statuses=args.filter_status,
                filter_judge_slots=args.filter_judge_slot,
            )

            # If --from specified, load existing checkpoint and reset states
            if from_run_state or from_tier_state or from_experiment_state:
                from scylla.e2e.checkpoint import (
                    load_checkpoint,
                    reset_experiment_for_from_state,
                    reset_runs_for_from_state,
                    reset_tiers_for_from_state,
                    save_checkpoint,
                )

                checkpoint_path = args.results_dir / experiment_id / "checkpoint.json"
                if checkpoint_path.exists():
                    checkpoint = load_checkpoint(checkpoint_path)
                    reset_count = 0
                    if from_run_state:
                        reset_count += reset_runs_for_from_state(
                            checkpoint,
                            from_run_state.value,
                            tier_filter=args.filter_tier,
                            subtest_filter=args.filter_subtest,
                            run_filter=args.filter_run,
                            status_filter=args.filter_status,
                        )
                    if from_tier_state:
                        reset_count += reset_tiers_for_from_state(
                            checkpoint,
                            from_tier_state.value,
                            tier_filter=args.filter_tier,
                        )
                    if from_experiment_state:
                        reset_count += reset_experiment_for_from_state(
                            checkpoint,
                            from_experiment_state.value,
                        )
                    save_checkpoint(checkpoint, checkpoint_path)
                    logger.info(f"[{test_id}] Reset {reset_count} items for --from. Resuming...")
                else:
                    logger.warning(
                        f"[{test_id}] --from specified but no checkpoint at {checkpoint_path}; "
                        "starting fresh"
                    )

            with terminal_guard():
                results = run_experiment(
                    config=config,
                    tiers_dir=test_dir,
                    results_dir=args.results_dir,
                    fresh=args.fresh,
                )

            status = "success" if results else "error"
            result = {"test_id": test_id, "status": status, "started_at": started_at}
        except Exception as e:
            logger.error(f"Test {test_id} failed with exception: {e}")
            result = {
                "test_id": test_id,
                "status": "error",
                "error": str(e),
                "started_at": started_at,
            }

        save_result(result)
        return result

    args.results_dir.mkdir(parents=True, exist_ok=True)

    # Handle retry-errors: load existing batch_summary and skip completed tests
    completed_ids: set[str] = set()
    if not args.fresh:
        import json

        summary_path = args.results_dir / "batch_summary.json"
        if summary_path.exists():
            try:
                with open(summary_path) as f:
                    summary = json.load(f)
                for r in summary.get("results", []):
                    if r.get("status") != "error" or not args.retry_errors:
                        completed_ids.add(r["test_id"])
            except Exception:
                pass

    # Apply --tests filter
    if args.tests:
        test_dirs = [d for d in test_dirs if d.name in args.tests]

    # Skip already-completed tests
    to_run = [d for d in test_dirs if d.name not in completed_ids]

    if not to_run:
        logger.info("All tests already completed in batch. Nothing to run.")
        return 0

    logger.info(f"Batch mode: running {len(to_run)} tests with {args.threads} threads")

    all_results: list[dict] = []
    failed_count = 0

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(run_one_test, d): d for d in to_run}
        for future in as_completed(futures):
            test_dir = futures[future]
            try:
                result = future.result()
                all_results.append(result)
                if result.get("status") != "success":
                    failed_count += 1
                    logger.warning(
                        f"Test {test_dir.name} completed with status: {result['status']}"
                    )
                else:
                    logger.info(f"Test {test_dir.name} completed successfully")
            except Exception as e:
                logger.error(f"Test {test_dir.name} raised exception: {e}")
                failed_count += 1

    total = len(to_run)
    passed = total - failed_count
    logger.info(f"Batch complete: {passed}/{total} tests succeeded")

    return 0 if failed_count == 0 else 1


def cmd_run(args: argparse.Namespace) -> int:  # noqa: C901 — unified run command
    """Execute the 'run' subcommand (single test or batch mode)."""
    import yaml

    from scylla.e2e.models import ExperimentConfig, ExperimentState, RunState, TierID, TierState
    from scylla.e2e.runner import run_experiment
    from scylla.utils.terminal import terminal_guard

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    # Resolve configs list
    configs: list[Path] = args.config or [Path("tests/claude-code/shared")]

    # Auto-expand: if a single path is a parent of test-* dirs, discover batch
    if len(configs) == 1 and configs[0].is_dir():
        parent = configs[0]
        test_dirs = sorted(
            d for d in parent.glob("test-*") if d.is_dir() and d.name != "test-config-loader"
        )
        if test_dirs:
            # This is a parent dir containing test-* subdirs → batch mode
            return _run_batch(test_dirs, args)

    # Multiple configs → batch mode
    if len(configs) > 1:
        return _run_batch(configs, args)

    # Single config → existing single-test behavior
    tiers_dir = configs[0]

    # Load test.yaml defaults if present
    test_config: dict[str, Any] = {}
    if tiers_dir and (tiers_dir / "test.yaml").exists():
        try:
            from scylla.e2e.models import TestFixture

            fixture = TestFixture.from_directory(tiers_dir)
            test_config = {
                "experiment_id": fixture.id,
                "task_repo": fixture.source_repo,
                "task_commit": fixture.source_hash,
                "task_prompt_file": "prompt.md",
                "timeout_seconds": fixture.timeout_seconds,
                "language": fixture.language,
            }
        except Exception:
            with open(tiers_dir / "test.yaml") as f:
                raw = yaml.safe_load(f) or {}
            test_config = raw

    # Load YAML config file if provided (single file path)
    yaml_config: dict[str, Any] = {}
    if tiers_dir and tiers_dir.is_file() and tiers_dir.suffix in (".yaml", ".yml"):
        with open(tiers_dir) as f:
            yaml_config = yaml.safe_load(f) or {}
        tiers_dir = tiers_dir.parent

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
        prompt_file = tiers_dir / prompt_name

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

    # Parse --from state
    from_run_state: RunState | None = None
    if args.from_run:
        try:
            from_run_state = RunState(args.from_run)
        except ValueError:
            logger.error(
                f"Unknown --from state: {args.from_run!r}. "
                f"Valid values: {[s.value for s in RunState]}"
            )
            return 1

    from_tier_state: TierState | None = None
    if args.from_tier:
        try:
            from_tier_state = TierState(args.from_tier)
        except ValueError:
            logger.error(
                f"Unknown --from-tier state: {args.from_tier!r}. "
                f"Valid values: {[s.value for s in TierState]}"
            )
            return 1

    from_experiment_state: ExperimentState | None = None
    if args.from_experiment:
        try:
            from_experiment_state = ExperimentState(args.from_experiment)
        except ValueError:
            logger.error(
                f"Unknown --from-experiment state: {args.from_experiment!r}. "
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
        from_run_state=from_run_state,
        from_tier_state=from_tier_state,
        from_experiment_state=from_experiment_state,
        filter_tiers=args.filter_tier,
        filter_subtests=args.filter_subtest,
        filter_runs=args.filter_run,
        filter_statuses=args.filter_status,
        filter_judge_slots=args.filter_judge_slot,
    )

    # If --from specified, load existing checkpoint and reset states
    if from_run_state or from_tier_state or from_experiment_state:
        from scylla.e2e.checkpoint import (
            load_checkpoint,
            reset_experiment_for_from_state,
            reset_runs_for_from_state,
            reset_tiers_for_from_state,
            save_checkpoint,
        )

        checkpoint_path = args.results_dir / experiment_id / "checkpoint.json"
        if not checkpoint_path.exists():
            logger.error(
                f"--from requires existing experiment with checkpoint at {checkpoint_path}"
            )
            return 1

        checkpoint = load_checkpoint(checkpoint_path)
        reset_count = 0

        if from_run_state:
            reset_count += reset_runs_for_from_state(
                checkpoint,
                from_run_state.value,
                tier_filter=args.filter_tier,
                subtest_filter=args.filter_subtest,
                run_filter=args.filter_run,
                status_filter=args.filter_status,
            )
        if from_tier_state:
            reset_count += reset_tiers_for_from_state(
                checkpoint,
                from_tier_state.value,
                tier_filter=args.filter_tier,
            )
        if from_experiment_state:
            reset_count += reset_experiment_for_from_state(
                checkpoint,
                from_experiment_state.value,
            )

        save_checkpoint(checkpoint, checkpoint_path)
        logger.info(f"Reset {reset_count} items for --from. Resuming execution...")

    with terminal_guard():
        results = run_experiment(
            config=config,
            tiers_dir=tiers_dir,
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
  run     Run single or batch experiments with optional --from re-execution
  repair  Repair corrupt checkpoint (rebuilds from run_result.json files)

Use 'manage_experiment.py <subcommand> --help' for subcommand-specific options.

Equivalence mapping (old → new):
  batch --results-dir X --threads 4
    → run --config tests/fixtures/tests/ --threads 4 --results-dir X
  rerun-agents /exp/ --tier T0 --status failed
    → run --config <test-dir> --results-dir /exp/ --from replay_generated
          --filter-tier T0 --filter-status failed
  rerun-judges /exp/ --tier T0 --judge-slot 1 2
    → run --config <test-dir> --results-dir /exp/ --from judge_pipeline_run
          --filter-tier T0 --filter-judge-slot 1 2
  regenerate /exp/
    → run --config <test-dir> --results-dir /exp/ --from run_finalized
        """,
    )

    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")
    subparsers.required = True

    # run subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Run single or batch E2E experiments (with optional --from re-execution)",
        description="Run E2E experiments. Supports single test, batch mode (multi-config or "
        "parent dir), and re-execution via --from.",
    )
    _add_run_args(run_parser)

    # repair subcommand (kept as-is)
    repair_parser = subparsers.add_parser(
        "repair",
        help="Repair corrupt checkpoint by rebuilding from run_result.json files",
        description="Fix checkpoints where completed_runs is empty despite having completed runs.",
    )
    _add_repair_args(repair_parser)

    return parser


def main() -> int:
    """Run the experiment management CLI."""
    parser = build_parser()
    args = parser.parse_args()

    subcommand_map = {
        "run": cmd_run,
        "repair": cmd_repair,
    }

    handler = subcommand_map.get(args.subcommand)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
