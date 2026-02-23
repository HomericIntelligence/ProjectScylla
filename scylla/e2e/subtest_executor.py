"""Sub-test executor for E2E testing.

This module handles executing individual sub-tests, including
workspace preparation, agent execution, judging, and result aggregation.

This file was decomposed from a 2269-line god class into focused modules:
- parallel_executor.py: Parallel execution and rate limit coordination
- agent_runner.py: Agent execution helpers
- judge_runner.py: Judge execution and consensus
- workspace_setup.py: Workspace management
- subtest_executor.py: Core SubTestExecutor class (this file)

See GitHub Issue #478 for decomposition history.
"""

from __future__ import annotations

import json
import logging
import statistics
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scylla.e2e.llm_judge import BuildPipelineResult

from scylla.adapters.claude_code import ClaudeCodeAdapter

# Import helpers from decomposed modules
from scylla.e2e.agent_runner import (
    _create_agent_model_md,
    _has_valid_agent_result,
    _load_agent_result,
    _save_agent_result,
)
from scylla.e2e.judge_runner import (
    _compute_judge_consensus,
    _has_valid_judge_result,
    _load_judge_result,
    _run_judge,
    _save_judge_result,
)
from scylla.e2e.models import (
    E2ERunResult,
    ExperimentConfig,
    SubTestConfig,
    SubTestResult,
    TierBaseline,
    TierConfig,
    TierID,
    TokenStats,
)
from scylla.e2e.rate_limit import RateLimitError
from scylla.e2e.tier_manager import TierManager
from scylla.e2e.workspace_manager import WorkspaceManager
from scylla.e2e.workspace_setup import (
    _commit_test_config,
    _move_to_failed,
    _setup_workspace,
)

if TYPE_CHECKING:
    from scylla.e2e.checkpoint import E2ECheckpoint
    from scylla.e2e.parallel_executor import RateLimitCoordinator
    from scylla.e2e.scheduler import ParallelismScheduler

logger = logging.getLogger(__name__)

# Re-export functions for backward compatibility
# These imports ensure existing code like:
#   from scylla.e2e.subtest_executor import _commit_test_config
#   from scylla.e2e.subtest_executor import run_tier_subtests_parallel
# continue to work without modification
__all__ = [
    "ExecutionStage",
    # Parallel executor exports (imported lazily to avoid circular imports)
    "RateLimitCoordinator",
    "SubTestExecutor",
    "_commit_test_config",
    "_compute_judge_consensus",
    "_create_agent_model_md",
    "_detect_rate_limit_from_results",  # noqa: F822
    "_has_valid_agent_result",
    "_has_valid_judge_result",
    "_load_agent_result",
    "_load_judge_result",
    # Workspace setup exports
    "_move_to_failed",
    "_retry_with_new_pool",  # noqa: F822
    "_run_judge",
    "_run_subtest_in_process",  # noqa: F822
    "_run_subtest_in_process_safe",  # noqa: F822
    # Agent runner exports
    "_save_agent_result",
    # Judge runner exports
    "_save_judge_result",
    "_setup_workspace",
    "run_tier_subtests_parallel",  # noqa: F822
]


def __getattr__(name: str):
    """Lazy import for parallel executor functions to avoid circular dependency."""
    if name in [
        "RateLimitCoordinator",
        "run_tier_subtests_parallel",
        "_detect_rate_limit_from_results",
        "_retry_with_new_pool",
        "_run_subtest_in_process_safe",
        "_run_subtest_in_process",
    ]:
        from scylla.e2e import parallel_executor

        return getattr(parallel_executor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class ExecutionStage(str, Enum):
    """Execution stages for worker thread reporting."""

    WORKTREE = "WORKTREE"
    AGENT = "AGENT"
    JUDGE = "JUDGE"
    CLEANUP = "CLEANUP"
    COMPLETE = "COMPLETE"


def _save_pipeline_baseline(results_dir: Path, result: BuildPipelineResult) -> None:
    """Save pipeline baseline result to JSON.

    Args:
        results_dir: Directory to save baseline (e.g., results/T2/01/)
        result: BuildPipelineResult to save

    """
    baseline_path = results_dir / "pipeline_baseline.json"
    baseline_path.write_text(json.dumps(result.model_dump(), indent=2))
    logger.info(f"Saved pipeline baseline to {baseline_path}")


def _load_pipeline_baseline(results_dir: Path) -> BuildPipelineResult | None:
    """Load pipeline baseline result from JSON.

    Args:
        results_dir: Directory containing baseline (e.g., results/T2/01/)

    Returns:
        BuildPipelineResult if file exists, None otherwise

    """
    from scylla.e2e.llm_judge import BuildPipelineResult

    baseline_path = results_dir / "pipeline_baseline.json"
    if not baseline_path.exists():
        return None

    try:
        data = json.loads(baseline_path.read_text())
        return BuildPipelineResult(**data)
    except Exception as e:
        logger.warning(f"Failed to load pipeline baseline from {baseline_path}: {e}")
        return None


class SubTestExecutor:
    """Executes sub-tests and aggregates results.

    Handles the complete lifecycle of running a sub-test:
    1. Create workspace (clone repo, checkout commit)
    2. Prepare tier configuration (inheritance + overlay)
    3. Execute agent N times
    4. Judge each run
    5. Aggregate results

    Example:
        >>> executor = SubTestExecutor(config, tier_manager)
        >>> result = executor.run_subtest(
        ...     tier_id=TierID.T2,
        ...     subtest=subtest_config,
        ...     baseline=previous_baseline,
        ...     results_dir=Path("/results/T2/01"),
        ... )

    """

    def __init__(
        self,
        config: ExperimentConfig,
        tier_manager: TierManager,
        workspace_manager: WorkspaceManager,
        adapter: ClaudeCodeAdapter | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            config: Experiment configuration
            tier_manager: Tier configuration manager
            workspace_manager: Workspace manager for git worktrees
            adapter: Optional adapter (defaults to ClaudeCodeAdapter)

        """
        self.config = config
        self.tier_manager = tier_manager
        self.workspace_manager = workspace_manager
        self.adapter = adapter or ClaudeCodeAdapter()

        # Container execution is now handled at the experiment level
        # (entire script runs in container).
        # Individual agent/judge container orchestration is disabled
        self.docker_executor = None

    def run_subtest(  # noqa: C901  # subtest execution orchestration with many outcome paths
        self,
        tier_id: TierID,
        tier_config: TierConfig,
        subtest: SubTestConfig,
        baseline: TierBaseline | None,
        results_dir: Path,
        checkpoint: E2ECheckpoint | None = None,
        checkpoint_path: Path | None = None,
        coordinator: RateLimitCoordinator | None = None,
        scheduler: ParallelismScheduler | None = None,
        experiment_dir: Path | None = None,
    ) -> SubTestResult:
        """Run a single sub-test N times and aggregate results.

        Creates workspace at subtest level (shared across runs) for efficiency.
        Each run gets its own directory for output.txt, judgment.json, etc.

        Supports checkpoint/resume: skips completed runs and saves after each run.

        Args:
            tier_id: The tier being executed
            tier_config: Tier configuration
            subtest: Sub-test configuration
            baseline: Previous tier's winning baseline (if any)
            results_dir: Directory to store results (subtest directory)
            checkpoint: Optional checkpoint for resume capability
            checkpoint_path: Path to checkpoint file for saving
            coordinator: Optional rate limit coordinator for parallel execution
            scheduler: Optional ParallelismScheduler for per-stage concurrency limits
            experiment_dir: Path to experiment directory (needed for T5 inheritance)

        Returns:
            SubTestResult with aggregated metrics.

        """
        from scylla.e2e.models import SubtestState
        from scylla.e2e.stages import RunContext, build_actions_dict
        from scylla.e2e.state_machine import StateMachine

        runs: list[E2ERunResult] = []
        results_dir.mkdir(parents=True, exist_ok=True)

        # Load task prompt once
        task_prompt = self.config.task_prompt_file.read_text()

        # Track last workspace for resource manifest
        last_workspace = None

        # Pipeline baseline is shared across runs; stored in RunContext and
        # propagated back to subsequent RunContext instances below.
        pipeline_baseline: BuildPipelineResult | None = None

        if checkpoint:
            checkpoint.set_subtest_state(
                tier_id.value, subtest.id, SubtestState.RUNS_IN_PROGRESS.value
            )

        for run_num in range(1, self.config.runs_per_subtest + 1):
            # Check for shutdown before starting run
            if coordinator and coordinator.is_shutdown_requested():
                logger.warning(
                    f"Shutdown requested before run {run_num} of "
                    f"{tier_id.value}/{subtest.id}, stopping..."
                )
                break

            # Check coordinator for pause signal before each run
            if coordinator:
                coordinator.check_if_paused()

            run_dir = results_dir / f"run_{run_num:02d}"
            workspace = run_dir / "workspace"

            # Build checkpoint/state-machine objects for this run
            sm = (
                StateMachine(
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                )
                if checkpoint and checkpoint_path
                else None
            )

            # Check if already in a terminal state (fully complete or previously failed)
            if sm and sm.is_complete(tier_id.value, subtest.id, run_num):
                run_result_file = run_dir / "run_result.json"
                if run_dir.exists() and run_result_file.exists():
                    from scylla.e2e.rate_limit import validate_run_result

                    is_valid, failure_reason = validate_run_result(run_dir)
                    if not is_valid:
                        logger.warning(
                            f"Previously completed run is invalid ({failure_reason}), re-running..."
                        )
                        _move_to_failed(run_dir)
                        if checkpoint and checkpoint_path:
                            checkpoint.unmark_run_completed(tier_id.value, subtest.id, run_num)
                            from scylla.e2e.checkpoint import save_checkpoint

                            save_checkpoint(checkpoint, checkpoint_path)
                        # Fall through to re-run
                    else:
                        logger.info(
                            f"Skipping completed run: "
                            f"{tier_id.value}/{subtest.id}/run_{run_num:02d}"
                        )
                        with open(run_result_file) as f:
                            report_data = json.load(f)

                        run_result = E2ERunResult(
                            run_number=report_data["run_number"],
                            exit_code=report_data["exit_code"],
                            token_stats=TokenStats.from_dict(report_data["token_stats"]),
                            cost_usd=report_data["cost_usd"],
                            duration_seconds=report_data["duration_seconds"],
                            agent_duration_seconds=report_data.get("agent_duration_seconds", 0.0),
                            judge_duration_seconds=report_data.get("judge_duration_seconds", 0.0),
                            judge_score=report_data["judge_score"],
                            judge_passed=report_data["judge_passed"],
                            judge_grade=report_data["judge_grade"],
                            judge_reasoning=report_data["judge_reasoning"],
                            workspace_path=Path(report_data["workspace_path"]),
                            logs_path=Path(report_data["logs_path"]),
                            command_log_path=(
                                Path(report_data["command_log_path"])
                                if report_data.get("command_log_path")
                                else None
                            ),
                            criteria_scores=report_data.get("criteria_scores") or {},
                            baseline_pipeline_summary=report_data.get("baseline_pipeline_summary"),
                        )
                        runs.append(run_result)
                        last_workspace = workspace
                        continue

            run_dir.mkdir(parents=True, exist_ok=True)
            workspace.mkdir(parents=True, exist_ok=True)
            last_workspace = workspace

            # Build RunContext for this run
            ctx = RunContext(
                config=self.config,
                tier_id=tier_id,
                tier_config=tier_config,
                subtest=subtest,
                baseline=baseline,
                run_number=run_num,
                run_dir=run_dir,
                workspace=workspace,
                experiment_dir=experiment_dir,
                tier_manager=self.tier_manager,
                workspace_manager=self.workspace_manager,
                adapter=self.adapter,
                pipeline_baseline=pipeline_baseline,
                task_prompt=task_prompt,
                coordinator=coordinator,
                checkpoint=checkpoint,
                checkpoint_path=checkpoint_path,
            )

            actions = build_actions_dict(ctx, scheduler=scheduler)

            try:
                if sm:
                    sm.advance_to_completion(
                        tier_id.value,
                        subtest.id,
                        run_num,
                        actions,
                        until_state=self.config.until_run_state,
                    )
                else:
                    # No checkpoint — run all stages directly without state machine
                    for action in actions.values():
                        action()

                if ctx.run_result:
                    runs.append(ctx.run_result)

                # Propagate pipeline_baseline to subsequent runs
                if ctx.pipeline_baseline is not None and pipeline_baseline is None:
                    pipeline_baseline = ctx.pipeline_baseline

            except RateLimitError as e:
                # Move the run directory to .failed/ so run number can be reused
                if run_dir.exists():
                    _move_to_failed(run_dir)

                # Signal coordinator if available
                if coordinator:
                    coordinator.signal_rate_limit(e.info)
                # Re-raise to be handled at higher level
                raise

        if checkpoint:
            checkpoint.set_subtest_state(
                tier_id.value, subtest.id, SubtestState.RUNS_COMPLETE.value
            )

        # Save resource manifest for inheritance (no file copying)
        # Use last workspace if available, otherwise use the final run's workspace path
        if last_workspace is None and self.config.runs_per_subtest > 0:
            # No runs were executed (all completed via checkpoint), use last run's workspace
            last_run_num = self.config.runs_per_subtest
            last_workspace = results_dir / f"run_{last_run_num:02d}" / "workspace"

        if last_workspace is not None:
            self.tier_manager.save_resource_manifest(
                results_dir=results_dir,
                tier_id=tier_id,
                subtest=subtest,
                workspace=last_workspace,
                baseline=baseline,
            )

        # Aggregate results
        result = self._aggregate_results(tier_id, subtest.id, runs)

        return result

    def _compute_judge_consensus(
        self, judges: list
    ) -> tuple[float | None, bool | None, str | None]:
        """Compute consensus score from multiple judges using simple average.

        This is a wrapper method for backward compatibility.
        The actual implementation is in judge_runner._compute_judge_consensus.

        Args:
            judges: List of individual judge results

        Returns:
            Tuple of (consensus_score, passed, grade)

        """
        return _compute_judge_consensus(judges)

    def _aggregate_results(
        self,
        tier_id: TierID,
        subtest_id: str,
        runs: list[E2ERunResult],
    ) -> SubTestResult:
        """Aggregate results from multiple runs.

        Args:
            tier_id: The tier identifier
            subtest_id: The sub-test identifier
            runs: List of run results

        Returns:
            SubTestResult with aggregated statistics.

        """
        if not runs:
            return SubTestResult(
                subtest_id=subtest_id,
                tier_id=tier_id,
                runs=[],
            )

        scores = [r.judge_score for r in runs]
        costs = [r.cost_usd for r in runs]

        pass_count = sum(1 for r in runs if r.judge_passed)
        pass_rate = pass_count / len(runs)

        mean_score = statistics.mean(scores)
        median_score = statistics.median(scores)
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0.0

        # Consistency: 1 - coefficient of variation
        cv = std_dev / mean_score if mean_score > 0 else 1.0
        consistency = max(0.0, 1.0 - cv)

        # Aggregate token stats from all runs
        from functools import reduce

        token_stats = reduce(
            lambda a, b: a + b,
            [r.token_stats for r in runs],
            TokenStats(),
        )

        # Aggregate grades
        grades = [r.judge_grade for r in runs if r.judge_grade]
        grade_distribution: dict[str, int] | None = None
        modal_grade: str | None = None
        min_grade: str | None = None
        max_grade: str | None = None

        if grades:
            # Build distribution
            grade_distribution = {}
            for g in grades:
                grade_distribution[g] = grade_distribution.get(g, 0) + 1

            # Modal grade (most common)
            modal_grade = max(grade_distribution, key=grade_distribution.get)

            # Grade ordering for min/max (F=worst, S=best)
            grade_order = ["F", "D", "C", "B", "A", "S"]
            grade_indices = [grade_order.index(g) for g in grades if g in grade_order]
            if grade_indices:
                min_grade = grade_order[min(grade_indices)]
                max_grade = grade_order[max(grade_indices)]

        return SubTestResult(
            subtest_id=subtest_id,
            tier_id=tier_id,
            runs=runs,
            pass_rate=pass_rate,
            mean_score=mean_score,
            median_score=median_score,
            std_dev_score=std_dev,
            mean_cost=statistics.mean(costs),
            total_cost=sum(costs),
            consistency=consistency,
            token_stats=token_stats,
            grade_distribution=grade_distribution,
            modal_grade=modal_grade,
            min_grade=min_grade,
            max_grade=max_grade,
        )
