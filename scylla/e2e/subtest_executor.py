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
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scylla.e2e.llm_judge import BuildPipelineResult

from scylla.adapters.base import AdapterConfig
from scylla.adapters.claude_code import ClaudeCodeAdapter

# Import helpers from decomposed modules
from scylla.e2e.agent_runner import (
    _create_agent_model_md,
    _has_valid_agent_result,
    _load_agent_result,
    _save_agent_result,
)
from scylla.e2e.command_logger import CommandLogger
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
from scylla.e2e.paths import (
    get_agent_dir,
    get_judge_dir,
)
from scylla.e2e.rate_limit import (
    RateLimitError,
    detect_rate_limit,
)
from scylla.e2e.run_report import save_run_report, save_run_report_json
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


def _phase_log(phase: str, message: str) -> None:
    """Log a phase message with timestamp and prefix.

    Args:
        phase: Phase identifier (WORKTREE, AGENT, JUDGE)
        message: Message content

    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    logger.info(f"{timestamp} [{phase}] - {message}")


def _stage_log(
    subtest_id: str, stage: ExecutionStage, status: str, elapsed: float | None = None
) -> None:
    """Log execution stage with sub-test context and timing.

    Args:
        subtest_id: Sub-test identifier (e.g., "T0_00")
        stage: Execution stage
        status: Status description (e.g., "Starting", "Complete")
        elapsed: Optional elapsed time in seconds

    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    elapsed_str = f" ({elapsed:.1f}s)" if elapsed is not None else ""
    logger.info(f"{timestamp} [{subtest_id}] Stage: {stage.value} - {status}{elapsed_str}")


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
            experiment_dir: Path to experiment directory (needed for T5 inheritance)

        Returns:
            SubTestResult with aggregated metrics.

        """
        runs: list[E2ERunResult] = []
        results_dir.mkdir(parents=True, exist_ok=True)

        # Load task prompt once
        task_prompt = self.config.task_prompt_file.read_text()

        # Track last workspace for resource manifest
        last_workspace = None

        # Pipeline baseline (captured once before first run)
        pipeline_baseline: BuildPipelineResult | None = None

        for run_num in range(1, self.config.runs_per_subtest + 1):
            # Check for shutdown before starting run
            if coordinator and coordinator.is_shutdown_requested():
                logger.warning(
                    f"Shutdown requested before run {run_num} of "
                    f"{tier_id.value}/{subtest.id}, stopping..."
                )
                break

            # Check if run already completed (checkpoint resume)
            if checkpoint and checkpoint.is_run_completed(tier_id.value, subtest.id, run_num):
                run_dir = results_dir / f"run_{run_num:02d}"
                run_result_file = run_dir / "run_result.json"

                if run_dir.exists() and run_result_file.exists():
                    # Validate the run result before considering it completed
                    from scylla.e2e.rate_limit import validate_run_result

                    is_valid, failure_reason = validate_run_result(run_dir)

                    if not is_valid:
                        logger.warning(
                            f"Previously completed run is invalid ({failure_reason}), re-running..."
                        )
                        # Move to .failed/ and unmark from checkpoint
                        _move_to_failed(run_dir)
                        checkpoint.unmark_run_completed(tier_id.value, subtest.id, run_num)
                        if checkpoint_path:
                            from scylla.e2e.checkpoint import save_checkpoint

                            save_checkpoint(checkpoint, checkpoint_path)
                        # Don't skip - fall through to re-run
                    else:
                        logger.info(
                            f"Skipping completed run: "
                            f"{tier_id.value}/{subtest.id}/run_{run_num:02d}"
                        )
                        # Load from saved E2ERunResult
                        with open(run_result_file) as f:
                            report_data = json.load(f)

                        # Reconstruct E2ERunResult from JSON
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
                        continue

            # Check coordinator for pause signal before each run
            if coordinator:
                coordinator.check_if_paused()

            run_dir = results_dir / f"run_{run_num:02d}"
            run_dir.mkdir(parents=True, exist_ok=True)

            # Create workspace per run in run_N/workspace/
            workspace = run_dir / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            last_workspace = workspace  # Track for resource manifest

            # Check if run already passed and workspace exists - preserve it
            run_status = None
            if checkpoint:
                run_status = checkpoint.get_run_status(tier_id.value, subtest.id, run_num)

            if run_status == "passed" and workspace.exists():
                logger.info(
                    f"Run {run_num} already passed (checkpoint), preserving existing workspace"
                )
                # Skip workspace setup - use existing workspace
            else:
                # Setup workspace with git worktree
                _setup_workspace(
                    workspace=workspace,
                    command_logger=CommandLogger(log_dir=run_dir),
                    tier_id=tier_id,
                    subtest_id=subtest.id,
                    run_number=run_num,
                    base_repo=self.workspace_manager.base_repo,
                    task_commit=self.config.task_commit,
                    experiment_id=self.config.experiment_id,
                )

            # Build merged resources for T5 subtests with inherit_best_from
            merged_resources = None
            if tier_id == TierID.T5 and subtest.inherit_best_from and experiment_dir:
                try:
                    merged_resources = self.tier_manager.build_merged_baseline(
                        subtest.inherit_best_from,
                        experiment_dir,
                    )
                except ValueError as e:
                    logger.error(f"Failed to build merged baseline for T5/{subtest.id}: {e}")
                    raise

            # Prepare tier configuration in workspace
            thinking_enabled = (
                self.config.thinking_mode is not None and self.config.thinking_mode != "None"
            )
            self.tier_manager.prepare_workspace(
                workspace=workspace,
                tier_id=tier_id,
                subtest_id=subtest.id,
                baseline=baseline,
                merged_resources=merged_resources,
                thinking_enabled=thinking_enabled,
            )

            # Commit test configs so agent sees them as existing state
            _commit_test_config(workspace)

            # Capture pipeline baseline once (before first run)
            if pipeline_baseline is None:
                # Try to load from checkpoint first
                pipeline_baseline = _load_pipeline_baseline(results_dir)

                # If not found, capture now
                if pipeline_baseline is None:
                    from scylla.e2e.llm_judge import _run_build_pipeline

                    _phase_log("BASELINE", "Capturing pipeline baseline before agent runs")
                    pipeline_baseline = _run_build_pipeline(
                        workspace=workspace,
                        language=self.config.language,
                    )

                    # Save baseline for checkpoint resume
                    _save_pipeline_baseline(results_dir, pipeline_baseline)

                    # Log status summary
                    baseline_status = (
                        "ALL PASSED ✓" if pipeline_baseline.all_passed else "SOME FAILED ✗"
                    )
                    logger.info(f"Pipeline baseline: {baseline_status}")

            try:
                run_result = self._execute_single_run(
                    tier_id=tier_id,
                    tier_config=tier_config,
                    subtest=subtest,
                    baseline=baseline,
                    run_number=run_num,
                    run_dir=run_dir,
                    workspace=workspace,
                    task_prompt=task_prompt,
                    experiment_dir=experiment_dir,
                    pipeline_baseline=pipeline_baseline,
                )
                runs.append(run_result)

                # Save checkpoint after each run (with pass/fail status)
                if checkpoint and checkpoint_path:
                    from scylla.e2e.checkpoint import save_checkpoint

                    # Status based on judge pass/fail
                    status = "passed" if run_result.judge_passed else "failed"
                    checkpoint.mark_run_completed(tier_id.value, subtest.id, run_num, status=status)
                    save_checkpoint(checkpoint, checkpoint_path)
                    logger.debug(
                        f"Checkpoint saved: "
                        f"{tier_id.value}/{subtest.id}/run_{run_num:02d} (status={status})"
                    )

            except RateLimitError as e:
                # Move the run directory to .failed/ so run number can be reused
                if run_dir.exists():
                    _move_to_failed(run_dir)

                # Signal coordinator if available
                if coordinator:
                    coordinator.signal_rate_limit(e.info)
                # Re-raise to be handled at higher level
                raise

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
        return self._aggregate_results(tier_id, subtest.id, runs)

    def _execute_single_run(  # noqa: C901  # workspace setup with many config scenarios
        self,
        tier_id: TierID,
        tier_config: TierConfig,
        subtest: SubTestConfig,
        baseline: TierBaseline | None,
        run_number: int,
        run_dir: Path,
        workspace: Path,
        task_prompt: str,
        experiment_dir: Path | None = None,
        pipeline_baseline: BuildPipelineResult | None = None,
    ) -> E2ERunResult:
        """Execute a single run of the sub-test.

        Files are organized in agent/ and judge/ subdirectories:
        - agent/: Agent execution artifacts
          (stdout, stderr, output.txt, command_log.json, replay.sh)
        - judge/: Judge evaluation artifacts
          (prompt.md, response.txt, judgment.json, replay.sh)
        - task_prompt.md: Task given to agent
        - run_result.json: Combined result
        - report.md: Per-run report

        Args:
            tier_id: The tier being executed
            tier_config: Tier configuration
            subtest: Sub-test configuration
            baseline: Previous tier's baseline
            run_number: The run number (1-indexed)
            run_dir: Directory for this run's outputs
            workspace: Shared workspace at subtest level
            task_prompt: The task prompt text
            experiment_dir: Path to experiment directory (needed for T5 inheritance)

        Returns:
            E2ERunResult with execution details.

        """
        # Track execution timing and stages
        subtest_id = f"{tier_id.value}_{subtest.id}"
        start_time = time.time()

        # Create agent and judge subdirectories
        agent_dir = get_agent_dir(run_dir)
        judge_dir = get_judge_dir(run_dir)
        agent_dir.mkdir(parents=True, exist_ok=True)
        judge_dir.mkdir(parents=True, exist_ok=True)

        # Set permissions to allow container user (UID 999) to write
        # Container runs as 'scylla' user which needs write access to output dirs
        agent_dir.chmod(0o777)
        judge_dir.chmod(0o777)

        # Agent command logger outputs to agent/
        command_logger = CommandLogger(log_dir=agent_dir)

        # Resource suffix is now handled in CLAUDE.md by tier_manager.prepare_workspace()
        # Task prompt stays clean - just symlink to experiment-level copy for deduplication
        prompt_file = run_dir / "task_prompt.md"

        # Handle resume: remove existing file/symlink before creating
        if prompt_file.exists() or prompt_file.is_symlink():
            prompt_file.unlink()

        if experiment_dir is not None:
            experiment_prompt = experiment_dir / "prompt.md"
            if experiment_prompt.exists():
                prompt_file.symlink_to(experiment_prompt.resolve())
            else:
                # Fallback: write full content if experiment copy doesn't exist
                prompt_file.write_text(task_prompt)
        else:
            # No experiment_dir provided, write directly
            prompt_file.write_text(task_prompt)

        # Build extra args for adapter
        extra_args: list[str] = []
        if self.config.max_turns is not None:
            extra_args.extend(["--max-turns", str(self.config.max_turns)])

        # Check if valid agent result already exists (resume case)
        agent_ran = False

        if _has_valid_agent_result(run_dir):
            # Reuse existing valid agent result
            from scylla.e2e.paths import get_agent_result_file

            agent_result_file = get_agent_result_file(run_dir)
            logger.info(f"[SKIP] Agent already completed: {agent_result_file}")
            result = _load_agent_result(agent_dir)
            # Read persisted timing from file
            agent_timing_file = agent_dir / "timing.json"
            if agent_timing_file.exists():
                timing_data = json.loads(agent_timing_file.read_text())
                duration = timing_data.get("agent_duration_seconds", 0.0)
            else:
                duration = 0.0  # Fallback for old runs without timing file
        else:
            # Run agent
            _stage_log(subtest_id, ExecutionStage.AGENT, "Starting")

            adapter_config = AdapterConfig(
                model=self.config.models[0],
                prompt_file=prompt_file,
                workspace=workspace,
                output_dir=agent_dir,  # Agent files go in agent/
                timeout=self.config.timeout_seconds,
                extra_args=extra_args,
            )

            _phase_log(
                "AGENT",
                f"Running agent with model[{self.config.models[0]}] with prompt[{prompt_file}]",
            )

            # Extract agent name from subtest config for T3/T4 delegation tiers
            agent_name = None
            if subtest.resources and "agents" in subtest.resources:
                agents_spec = subtest.resources["agents"]
                # Get agent names from the config
                agent_names_list = agents_spec.get("names", [])
                # For T3/T4, expect single agent (not multiple)
                if agent_names_list:
                    # Take first agent name, remove .md extension if present
                    agent_name = agent_names_list[0].replace(".md", "")
                    logger.info(f"Using agent: {agent_name}")

            # Write prompt to agent/prompt.md for replay.sh
            # Inject thinking keyword based on config if not None
            final_prompt = task_prompt
            if self.config.thinking_mode and self.config.thinking_mode != "None":
                thinking_keywords = {
                    "Low": "think",
                    "High": "think hard",
                    "UltraThink": "ultrathink",
                }
                keyword = thinking_keywords.get(self.config.thinking_mode, "")
                if keyword:
                    final_prompt = f"{keyword}\n\n{task_prompt}"

            agent_prompt_file = agent_dir / "prompt.md"
            agent_prompt_file.write_text(final_prompt)

            # Build command with file path instead of string
            # Modify the command to reference the prompt file
            cmd = self.adapter._build_command(
                adapter_config,
                str(agent_prompt_file.resolve()),  # Pass absolute file path
                None,
                subtest.system_prompt_mode,
                agent_name,
            )

            # Pre-log the command (before execution)
            # We'll update stdout/stderr/exit_code after execution
            command_logger.log_command(
                cmd=cmd,
                stdout="",  # Will be filled after execution
                stderr="",  # Will be filled after execution
                exit_code=0,  # Will be updated after execution
                duration=0.0,  # Will be updated after execution
                cwd=str(workspace.resolve()),  # Use absolute path for replay.sh
            )

            # Generate replay.sh BEFORE execution
            command_logger.save()
            replay_script = command_logger.save_replay_script()

            # Execute via replay.sh
            agent_start = datetime.now(timezone.utc)
            try:
                result = self._run_via_replay_script(
                    replay_script=replay_script,
                    agent_dir=agent_dir,
                    workspace=workspace,
                    adapter_config=adapter_config,
                    tier_config=tier_config,
                )
            except Exception as e:
                # Handle execution errors - create a mock result with token_stats
                from scylla.adapters.base import AdapterResult, AdapterTokenStats

                result = AdapterResult(
                    exit_code=-1,
                    stdout="",
                    stderr=str(e),
                    token_stats=AdapterTokenStats(),
                    cost_usd=0.0,
                    api_calls=0,
                )

            duration = (datetime.now(timezone.utc) - agent_start).total_seconds()

            # Update the logged command with actual results
            command_logger.update_last_command(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                duration=duration,
            )

            # Save updated command logs
            command_logger.save()

            # Persist timing to file for resume capability
            agent_timing_file = agent_dir / "timing.json"
            with open(agent_timing_file, "w") as f:
                json.dump(
                    {
                        "agent_duration_seconds": duration,
                        "measured_at": datetime.now(timezone.utc).isoformat(),
                    },
                    f,
                    indent=2,
                )

            # Save agent output to agent/output.txt
            output_file = agent_dir / "output.txt"
            output_file.write_text(result.stdout or "")

            # Save agent result for future resume
            _save_agent_result(agent_dir, result)

            # Create MODEL.md with agent model info
            _create_agent_model_md(agent_dir, self.config.models[0])

            agent_ran = True
            _stage_log(subtest_id, ExecutionStage.AGENT, "Complete", duration)

        # Run judge evaluation (ALWAYS re-run if agent ran, requirement from user)
        # Only reuse judge result if agent was reused AND valid judge result exists
        if not agent_ran and _has_valid_judge_result(run_dir):
            # Reuse existing valid judge result (only if agent was also reused)
            from scylla.e2e.paths import get_judge_result_file

            judge_result_file = get_judge_result_file(run_dir)
            logger.info(f"[SKIP] Judge already completed: {judge_result_file}")
            judgment = _load_judge_result(judge_dir)
            judges = []  # No individual judge data for resumed results
            # Read persisted timing from file
            judge_timing_file = judge_dir / "timing.json"
            if judge_timing_file.exists():
                timing_data = json.loads(judge_timing_file.read_text())
                judge_duration = timing_data.get("judge_duration_seconds", 0.0)
            else:
                judge_duration = 0.0  # Fallback for old runs without timing file
        else:
            # Run judge (either agent ran, or judge result missing)
            _stage_log(subtest_id, ExecutionStage.JUDGE, "Starting")
            judge_start = datetime.now(timezone.utc)

            # Find rubric path (symlinked at experiment root)
            # results_dir structure: experiment_dir/T0/01/
            experiment_dir_calc = run_dir.parent.parent.parent
            rubric_path = experiment_dir_calc / "rubric.yaml"
            if not rubric_path.exists():
                rubric_path = None

            judgment, judges = _run_judge(
                workspace=workspace,
                task_prompt=task_prompt,
                stdout=result.stdout,
                judge_dir=judge_dir,
                language=self.config.language,
                rubric_path=rubric_path,
                judge_models=self.config.judge_models,
                pipeline_baseline=pipeline_baseline,
            )

            # Save pipeline commands once per run (not per judge)
            from scylla.e2e.llm_judge import _save_pipeline_commands

            _save_pipeline_commands(run_dir, workspace, language=self.config.language)

            judge_duration = (datetime.now(timezone.utc) - judge_start).total_seconds()
            _stage_log(subtest_id, ExecutionStage.JUDGE, "Complete", judge_duration)

            # Persist timing to file for resume capability
            judge_timing_file = judge_dir / "timing.json"
            with open(judge_timing_file, "w") as f:
                json.dump(
                    {
                        "judge_duration_seconds": judge_duration,
                        "measured_at": datetime.now(timezone.utc).isoformat(),
                    },
                    f,
                    indent=2,
                )

            # Save judge result for future resume
            from scylla.e2e.llm_judge import JudgeResult

            judge_result_obj = JudgeResult(
                score=judgment["score"],
                passed=judgment["passed"],
                grade=judgment["grade"],
                reasoning=judgment["reasoning"],
                is_valid=judgment.get("is_valid", True),
            )
            _save_judge_result(judge_dir, judge_result_obj)

        # Convert adapter token stats to E2E token stats
        token_stats = result.token_stats.to_token_stats()

        # Check for rate limit in run artifacts BEFORE considering complete
        # Check stderr and stdout for rate limit patterns (adapter may have missed it)
        stderr_content = result.stderr or ""
        stdout_content = result.stdout or ""
        rate_limit_info = detect_rate_limit(stdout_content, stderr_content, source="agent")

        if rate_limit_info:
            # Rate limit detected - raise error to prevent marking as completed
            raise RateLimitError(rate_limit_info)

        # Also check for "invalid" judge output with exit_code=-1
        if result.exit_code == -1 and judgment.get("reasoning", "").startswith("Invalid:"):
            # Double-check stderr for rate limit
            rate_limit_info = detect_rate_limit(stdout_content, stderr_content, source="agent")
            if rate_limit_info:
                raise RateLimitError(rate_limit_info)

        # Convert baseline to summary dict if available
        baseline_summary = None
        if pipeline_baseline:
            baseline_summary = {
                "all_passed": pipeline_baseline.all_passed,
                "build_passed": pipeline_baseline.build_passed,
                "format_passed": pipeline_baseline.format_passed,
                "test_passed": pipeline_baseline.test_passed,
            }

        run_result = E2ERunResult(
            run_number=run_number,
            exit_code=result.exit_code,
            token_stats=token_stats,
            cost_usd=result.cost_usd,
            duration_seconds=duration + judge_duration,
            agent_duration_seconds=duration,
            judge_duration_seconds=judge_duration,
            judge_score=judgment["score"],
            judge_passed=judgment["passed"],
            judge_grade=judgment["grade"],
            judge_reasoning=judgment["reasoning"],
            judges=judges,  # Individual judge results
            workspace_path=workspace,
            logs_path=agent_dir,  # Points to agent/ subdirectory
            command_log_path=agent_dir / "command_log.json",
            criteria_scores=judgment.get("criteria_scores") or {},
            baseline_pipeline_summary=baseline_summary,
        )

        # Save full E2ERunResult for checkpoint resume
        with open(run_dir / "run_result.json", "w") as f:
            json.dump(run_result.to_dict(), f, indent=2)

        # Generate per-run reports (markdown and JSON)
        save_run_report(
            output_path=run_dir / "report.md",
            tier_id=tier_id.value,
            subtest_id=subtest.id,
            run_number=run_number,
            score=judgment["score"],
            grade=judgment["grade"],
            passed=judgment["passed"],
            reasoning=judgment["reasoning"],
            judges=judges,  # Individual judge results for multi-judge tables
            cost_usd=result.cost_usd,
            duration_seconds=duration + judge_duration,
            tokens_input=run_result.tokens_input,  # Legacy property for fallback
            tokens_output=run_result.tokens_output,  # Legacy property for fallback
            exit_code=result.exit_code,
            task_prompt=task_prompt,
            workspace_path=workspace,
            criteria_scores=judgment.get("criteria_scores"),
            agent_output=result.stdout[:2000] if result.stdout else None,
            token_stats=token_stats.to_dict(),  # Pass detailed stats
            agent_duration_seconds=duration,
            judge_duration_seconds=judge_duration,
        )

        # JSON report for hierarchical linking
        save_run_report_json(
            run_dir=run_dir,
            run_number=run_number,
            score=judgment["score"],
            grade=judgment["grade"],
            passed=judgment["passed"],
            cost_usd=result.cost_usd,
            duration_seconds=duration + judge_duration,
        )

        # Log completion with total time
        total_elapsed = time.time() - start_time
        _stage_log(subtest_id, ExecutionStage.COMPLETE, "All stages complete", total_elapsed)

        return run_result

    def _run_via_replay_script(
        self,
        replay_script: Path,
        agent_dir: Path,
        workspace: Path,
        adapter_config: AdapterConfig,
        tier_config: TierConfig,
    ):
        """Execute agent via replay.sh script.

        This method runs replay.sh and parses the results from log files.

        Args:
            replay_script: Path to replay.sh
            agent_dir: Directory for agent outputs
            workspace: Workspace directory
            adapter_config: Adapter configuration
            tier_config: Tier configuration

        Returns:
            AdapterResult with execution details

        """
        import subprocess

        from scylla.adapters.base import AdapterResult

        # Execute replay.sh (resolve to absolute path for subprocess)
        result = subprocess.run(
            ["bash", str(replay_script.resolve())],
            capture_output=True,
            text=True,
            timeout=adapter_config.timeout,
            cwd=workspace.resolve(),
        )

        # Read stdout/stderr from captured subprocess output
        # (Log files exist but are empty until we update them later)
        stdout = result.stdout
        stderr = result.stderr

        # Parse token stats and cost from stdout
        token_stats = self.adapter._parse_token_stats(stdout, stderr)
        api_calls = self.adapter._parse_api_calls(stdout, stderr)
        cost = self.adapter._parse_cost(stdout)

        if cost == 0.0 and (token_stats.input_tokens > 0 or token_stats.output_tokens > 0):
            total_input = token_stats.input_tokens + token_stats.cache_read_tokens
            cost = self.adapter.calculate_cost(
                total_input, token_stats.output_tokens, adapter_config.model
            )

        # Write logs (for consistency with adapter behavior)
        self.adapter.write_logs(agent_dir, stdout, stderr)

        return AdapterResult(
            exit_code=result.returncode,
            stdout=stdout,
            stderr=stderr,
            token_stats=token_stats,
            cost_usd=cost,
            api_calls=api_calls,
        )

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
