"""Sub-test executor for E2E testing.

This module handles executing individual sub-tests, including
workspace preparation, agent execution, judging, and result aggregation.

Python Justification: Required for subprocess execution, parallel processing,
and filesystem operations.
"""

from __future__ import annotations

import logging
import shutil
import statistics
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime, timezone
from enum import Enum
from multiprocessing import Manager
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.adapters.base import AdapterConfig
from scylla.adapters.claude_code import ClaudeCodeAdapter
from scylla.e2e.command_logger import CommandLogger
from scylla.e2e.llm_judge import run_llm_judge
from scylla.e2e.models import (
    ExperimentConfig,
    JudgeResultSummary,
    RunResult,
    SubTestConfig,
    SubTestResult,
    TierBaseline,
    TierConfig,
    TierID,
    TokenStats,
)
from scylla.e2e.paths import (
    RESULT_FILE,
    get_agent_dir,
    get_agent_result_file,
    get_judge_dir,
    get_judge_result_file,
)
from scylla.e2e.rate_limit import (
    RateLimitError,
    RateLimitInfo,
    detect_rate_limit,
    wait_for_rate_limit,
)
from scylla.e2e.run_report import save_run_report, save_run_report_json
from scylla.e2e.tier_manager import TierManager
from scylla.e2e.workspace_manager import WorkspaceManager

if TYPE_CHECKING:
    from multiprocessing.managers import SyncManager

    from scylla.adapters.base import AdapterResult
    from scylla.e2e.checkpoint import E2ECheckpoint
    from scylla.judge.evaluator import JudgeResult

logger = logging.getLogger(__name__)


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


def _move_to_failed(run_dir: Path, attempt: int = 1) -> Path:
    """Move a failed run directory to .failed/ subdirectory.

    Args:
        run_dir: Path to the run directory (e.g., results/T0/01/run_01/)
        attempt: Attempt number for naming (default 1)

    Returns:
        Path to the new location in .failed/

    """
    failed_dir = run_dir.parent / ".failed"
    failed_dir.mkdir(parents=True, exist_ok=True)

    # Generate new name: run_03 -> .failed/run_03_attempt_01
    run_name = run_dir.name
    new_name = f"{run_name}_attempt_{attempt:02d}"
    new_path = failed_dir / new_name

    # Find next available attempt number if exists
    while new_path.exists():
        attempt += 1
        new_name = f"{run_name}_attempt_{attempt:02d}"
        new_path = failed_dir / new_name

    # Move the directory
    shutil.move(str(run_dir), str(new_path))
    logger.info(f"Moved failed run to {new_path}")

    return new_path


def _save_agent_result(agent_dir: Path, result: AdapterResult) -> None:
    """Save agent execution result to agent/result.json.

    Args:
        agent_dir: Path to agent directory
        result: AdapterResult from agent execution

    """
    import json

    result_data = {
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "token_stats": result.token_stats.model_dump(),
        "cost_usd": result.cost_usd,
        "api_calls": result.api_calls,
    }

    with open(agent_dir / RESULT_FILE, "w") as f:
        json.dump(result_data, f, indent=2)


def _create_agent_model_md(agent_dir: Path, model: str) -> None:
    """Create MODEL.md file with agent model and version information.

    Args:
        agent_dir: Path to agent directory
        model: Model identifier used for the agent

    """
    import subprocess

    # Try to get claude-code version
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            claude_code_version = result.stdout.strip()
        else:
            claude_code_version = "unknown"
    except Exception:
        claude_code_version = "unknown"

    model_info = f"""# Agent Model Information

**Model**: {model}
**Claude Code Version**: {claude_code_version}
**Timestamp**: {datetime.now(timezone.utc).isoformat()}

## Configuration
- Model ID: {model}
- Output Format: text
- Permissions: dangerously-skip-permissions (for testing)

## Environment
- Generated by ProjectScylla E2E Framework
"""

    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "MODEL.md").write_text(model_info)


def _commit_test_config(workspace: Path) -> None:
    """Commit test configuration files so agent sees them as existing state.

    Commits CLAUDE.md and .claude/ directory if they exist, so the agent
    sees them as part of the repository's existing state rather than
    uncommitted changes.

    Args:
        workspace: Path to the workspace directory

    """
    import subprocess

    # Stage CLAUDE.md if it exists
    claude_md = workspace / "CLAUDE.md"
    if claude_md.exists():
        subprocess.run(
            ["git", "add", "CLAUDE.md"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

    # Stage .claude/ directory if it exists
    claude_dir = workspace / ".claude"
    if claude_dir.exists():
        subprocess.run(
            ["git", "add", ".claude/"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

    # Check if there are staged changes
    status_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=workspace,
        capture_output=True,
        timeout=30,
    )

    # If there are staged changes, commit them
    if status_result.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", "[scylla] Initialize test configuration"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )


def _load_agent_result(agent_dir: Path) -> AdapterResult:
    """Load agent execution result from agent/result.json.

    Args:
        agent_dir: Path to agent directory

    Returns:
        AdapterResult loaded from file

    """
    import json

    from scylla.adapters.base import AdapterResult, AdapterTokenStats

    with open(agent_dir / RESULT_FILE) as f:
        data = json.load(f)

    token_stats = AdapterTokenStats(**data["token_stats"])

    return AdapterResult(
        exit_code=data["exit_code"],
        stdout=data["stdout"],
        stderr=data["stderr"],
        token_stats=token_stats,
        cost_usd=data["cost_usd"],
        api_calls=data["api_calls"],
    )


def _save_judge_result(judge_dir: Path, result: JudgeResult) -> None:
    """Save judge evaluation result to judge/result.json.

    Args:
        judge_dir: Path to judge directory
        result: JudgeResult from judge evaluation

    """
    import json

    # Save to result.json (simplified version for quick checking)
    result_data = {
        "score": result.score,
        "passed": result.passed,
        "grade": result.grade,
        "reasoning": result.reasoning,
    }

    with open(judge_dir / RESULT_FILE, "w") as f:
        json.dump(result_data, f, indent=2)


def _load_judge_result(judge_dir: Path) -> dict:
    """Load judge evaluation result from judge/result.json.

    Args:
        judge_dir: Path to judge directory

    Returns:
        Dict with score, passed, grade, reasoning

    """
    import json

    # FIX: Use result.json (same file that _has_valid_judge_result validates)
    # Previously tried to read judgment.json which doesn't exist at this path
    result_file = judge_dir / RESULT_FILE
    with open(result_file) as f:
        data = json.load(f)

    return data


def _has_valid_agent_result(run_dir: Path) -> bool:
    """Check if a valid agent result exists for the run.

    A result is considered invalid if:
    - Result file doesn't exist
    - JSON is malformed
    - Required fields are missing
    - exit_code is -1 AND all token_stats are 0 (incomplete execution)

    Args:
        run_dir: Path to the run directory

    Returns:
        True if valid agent result exists, False otherwise

    """
    import json

    result_file = get_agent_result_file(run_dir)
    if not result_file.exists():
        return False

    try:
        data = json.loads(result_file.read_text())
        # Check all required fields exist
        required_fields = ["exit_code", "token_stats", "cost_usd"]
        if not all(field in data for field in required_fields):
            return False

        # Check for incomplete execution: exit_code=-1 AND all token stats are 0
        # This indicates the agent threw an exception but created files
        if data["exit_code"] == -1:
            token_stats = data["token_stats"]
            all_tokens_zero = (
                token_stats.get("input_tokens", 0) == 0
                and token_stats.get("output_tokens", 0) == 0
                and token_stats.get("cache_creation_tokens", 0) == 0
                and token_stats.get("cache_read_tokens", 0) == 0
            )
            if all_tokens_zero:
                logger.warning(
                    f"Invalid result detected at {run_dir}: "
                    f"exit_code=-1 with zero token stats (incomplete execution)"
                )
                return False

        return True
    except (json.JSONDecodeError, KeyError, OSError):
        return False


def _has_valid_judge_result(run_dir: Path) -> bool:
    """Check if a valid judge result exists for the run.

    Args:
        run_dir: Path to the run directory

    Returns:
        True if valid judge result exists, False otherwise

    """
    import json

    result_file = get_judge_result_file(run_dir)
    if not result_file.exists():
        return False

    try:
        data = json.loads(result_file.read_text())
        # Check all required fields exist
        required_fields = ["score", "passed", "grade"]
        return all(field in data for field in required_fields)
    except (json.JSONDecodeError, KeyError, OSError):
        return False


class RateLimitCoordinator:
    """Coordinates rate limit pause across parallel workers.

    When ANY worker detects a rate limit, this coordinator:
    1. Signals all workers to pause
    2. Waits for the rate limit to expire
    3. Signals all workers to resume

    Uses multiprocessing.Manager for cross-process coordination.

    Example:
        >>> manager = Manager()
        >>> coordinator = RateLimitCoordinator(manager)
        >>> # In worker process:
        >>> if coordinator.check_if_paused():
        >>>     # Worker blocks here until resume
        >>>     pass

    """

    def __init__(self, manager: SyncManager) -> None:
        """Initialize coordinator with shared state.

        Args:
            manager: Multiprocessing manager for shared objects

        """
        self._pause_event = manager.Event()
        self._resume_event = manager.Event()
        self._rate_limit_info = manager.dict()
        self._shutdown_event = manager.Event()

    def signal_rate_limit(self, info: RateLimitInfo) -> None:
        """Signal that a rate limit was detected (called by worker).

        This sets the pause event, causing all workers to block.

        Args:
            info: Rate limit detection information

        """
        self._rate_limit_info.update(
            {
                "source": info.source,
                "retry_after_seconds": info.retry_after_seconds,
                "error_message": info.error_message,
                "detected_at": info.detected_at,
            }
        )
        self._pause_event.set()
        logger.info(f"Rate limit coordinator: pause signal from {info.source}")

    def check_if_paused(self) -> bool:
        """Check if pause is active and wait if needed (called by workers).

        Workers call this before each operation. If pause is active,
        they block here until resume signal.

        Returns:
            True if was paused and now resumed, False if never paused

        """
        if self._pause_event.is_set():
            logger.debug("Worker blocked on pause event, waiting for resume...")
            self._resume_event.wait()  # Block until resume
            self._resume_event.clear()
            logger.debug("Worker resumed after rate limit wait")
            return True
        return False

    def get_rate_limit_info(self) -> RateLimitInfo | None:
        """Get current rate limit info if available.

        Returns:
            RateLimitInfo if rate limit is active, None otherwise

        """
        if not self._pause_event.is_set():
            return None

        info_dict = dict(self._rate_limit_info)
        if not info_dict:
            return None

        return RateLimitInfo(
            source=info_dict["source"],
            retry_after_seconds=info_dict["retry_after_seconds"],
            error_message=info_dict["error_message"],
            detected_at=info_dict["detected_at"],
        )

    def resume_all_workers(self) -> None:
        """Signal all workers to resume (called by main thread after wait).

        Clears the pause event and sets resume event.
        """
        self._pause_event.clear()
        self._resume_event.set()
        logger.info("Rate limit coordinator: resume signal sent to all workers")

    def signal_shutdown(self) -> None:
        """Signal all workers to stop accepting new work and exit gracefully."""
        self._shutdown_event.set()
        logger.info("Shutdown signal sent to all workers")

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested.

        Returns:
            True if shutdown is requested, False otherwise

        """
        return self._shutdown_event.is_set()


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

    def run_subtest(
        self,
        tier_id: TierID,
        tier_config: TierConfig,
        subtest: SubTestConfig,
        baseline: TierBaseline | None,
        results_dir: Path,
        checkpoint: E2ECheckpoint | None = None,
        checkpoint_path: Path | None = None,
        coordinator: RateLimitCoordinator | None = None,
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

        Returns:
            SubTestResult with aggregated metrics.

        """
        runs: list[RunResult] = []
        results_dir.mkdir(parents=True, exist_ok=True)

        # Load task prompt once
        task_prompt = self.config.task_prompt_file.read_text()

        # Track last workspace for resource manifest
        last_workspace = None

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
                        # Load from saved RunResult
                        import json
                        from pathlib import Path

                        from scylla.e2e.models import TokenStats

                        with open(run_result_file) as f:
                            report_data = json.load(f)

                        # Reconstruct RunResult from JSON
                        run_result = RunResult(
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
                            criteria_scores=report_data.get("criteria_scores", {}),
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
                self._setup_workspace(
                    workspace, CommandLogger(run_dir), tier_id, subtest.id, run_number=run_num
                )

            # Prepare tier configuration in workspace
            thinking_enabled = (
                self.config.thinking_mode is not None and self.config.thinking_mode != "None"
            )
            self.tier_manager.prepare_workspace(
                workspace=workspace,
                tier_id=tier_id,
                subtest_id=subtest.id,
                baseline=baseline,
                thinking_enabled=thinking_enabled,
            )

            # Commit test configs so agent sees them as existing state
            _commit_test_config(workspace)

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

    def _run_via_replay_script(
        self,
        replay_script: Path,
        agent_dir: Path,
        workspace: Path,
        adapter_config: AdapterConfig,
        tier_config: TierConfig,
    ) -> AdapterResult:
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

    def _run_agent_execution(
        self,
        tier_config: TierConfig,
        adapter_config: AdapterConfig,
        task_prompt: str,
        agent_dir: Path,
        workspace: Path,
        prompt_file: Path,
        agent_name: str | None = None,
    ) -> AdapterResult:
        """Run agent execution directly (no nested containers).

        Container isolation is now handled at the experiment level - the entire
        run_e2e_experiment.py script runs inside a container. This method always
        runs the agent directly using the adapter.

        Args:
            tier_config: Tier configuration for system prompt mode
            adapter_config: Adapter configuration
            task_prompt: Task prompt text
            agent_dir: Directory for agent outputs
            workspace: Workspace directory
            prompt_file: Path to task prompt file
            agent_name: Optional agent name for T3/T4 delegation tiers

        Returns:
            AdapterResult with execution details

        """
        # Always use direct execution (container is at experiment level, not per-agent)
        return self.adapter.run(
            config=adapter_config,
            tier_config=None,
            system_prompt_mode=tier_config.system_prompt_mode,
            agent_name=agent_name,
        )

    def _execute_single_run(
        self,
        tier_id: TierID,
        tier_config: TierConfig,
        subtest: SubTestConfig,
        baseline: TierBaseline | None,
        run_number: int,
        run_dir: Path,
        workspace: Path,
        task_prompt: str,
    ) -> RunResult:
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

        Returns:
            RunResult with execution details.

        """
        import json

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
        command_logger = CommandLogger(agent_dir)

        # Build context-aware resource suffix
        resource_suffix = self.tier_manager.build_resource_suffix(subtest)
        prompt_file = run_dir / "task_prompt.md"

        if resource_suffix:
            # Resource suffix modifies the prompt - must write full content
            task_prompt = f"{task_prompt}\n\n{resource_suffix}"
            prompt_file.write_text(task_prompt)
        else:
            # No modification - symlink to experiment-level copy for deduplication
            experiment_prompt = self.experiment_dir / "prompt.md"
            if experiment_prompt.exists():
                prompt_file.symlink_to(experiment_prompt.resolve())
            else:
                # Fallback: write full content if experiment copy doesn't exist
                prompt_file.write_text(task_prompt)

        # Build extra args for adapter
        extra_args: list[str] = []
        if self.config.max_turns is not None:
            extra_args.extend(["--max-turns", str(self.config.max_turns)])

        # Check if valid agent result already exists (resume case)
        agent_ran = False

        if _has_valid_agent_result(run_dir):
            # Reuse existing valid agent result
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
                tier_config.system_prompt_mode,
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
            experiment_dir = run_dir.parent.parent.parent
            rubric_path = experiment_dir / "rubric.yaml"
            if not rubric_path.exists():
                rubric_path = None

            judgment, judges = self._run_judge(
                workspace=workspace,
                task_prompt=task_prompt,
                stdout=result.stdout,
                judge_dir=judge_dir,
                language=self.config.language,
                rubric_path=rubric_path,
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
        from scylla.e2e.rate_limit import RateLimitError, detect_rate_limit

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

        run_result = RunResult(
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
            criteria_scores=judgment.get("criteria_scores", {}),
        )

        # Save full RunResult for checkpoint resume
        import json

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

    def _setup_workspace(
        self,
        workspace: Path,
        command_logger: CommandLogger,
        tier_id: TierID,
        subtest_id: str,
        run_number: int,
    ) -> None:
        """Set up workspace using git worktree from base repo with named branch.

        Args:
            workspace: Target workspace directory
            command_logger: Logger for commands
            tier_id: Tier identifier for branch naming
            subtest_id: Subtest identifier for branch naming
            run_number: Run number for branch naming

        """
        import shlex

        start_time = datetime.now(timezone.utc)

        # Ensure workspace path is absolute for git worktree
        workspace_abs = workspace.resolve()

        # Generate branch name with run number
        branch_name = f"{tier_id.value}_{subtest_id}_run_{run_number:02d}"

        # Log worktree creation phase
        _phase_log("WORKTREE", f"Creating worktree [{branch_name}] @ [{workspace_abs}]")

        # Create worktree with named branch
        worktree_cmd = [
            "git",
            "-C",
            str(self.workspace_manager.base_repo),
            "worktree",
            "add",
            "-b",
            branch_name,
            str(workspace_abs),
        ]

        # Add commit reference if specified
        if self.config.task_commit:
            worktree_cmd.append(self.config.task_commit)

        result = subprocess.run(
            worktree_cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        command_logger.log_command(
            cmd=worktree_cmd,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            duration=duration,
        )

        # Handle branch already exists (resume scenario)
        if result.returncode != 0 and "already exists" in result.stderr:
            logger.info(f"Branch {branch_name} exists, attempting recovery for resume...")

            # Step 1: Remove stale worktree entry if it exists
            prune_cmd = [
                "git",
                "-C",
                str(self.workspace_manager.base_repo),
                "worktree",
                "prune",
            ]
            subprocess.run(prune_cmd, capture_output=True, text=True, timeout=30)

            # Step 2: Try to remove existing worktree (may fail if already gone)
            remove_cmd = [
                "git",
                "-C",
                str(self.workspace_manager.base_repo),
                "worktree",
                "remove",
                "--force",
                str(workspace_abs),
            ]
            subprocess.run(remove_cmd, capture_output=True, text=True, timeout=30)

            # Step 3: Delete the branch
            delete_branch_cmd = [
                "git",
                "-C",
                str(self.workspace_manager.base_repo),
                "branch",
                "-D",
                branch_name,
            ]
            subprocess.run(delete_branch_cmd, capture_output=True, text=True, timeout=30)

            # Step 4: Clean up workspace directory if exists
            if workspace_abs.exists():
                shutil.rmtree(workspace_abs)

            # Step 5: Retry worktree creation
            result = subprocess.run(
                worktree_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to create worktree even after cleanup: {result.stderr}")

        elif result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr}")

        # Save worktree creation command (create only, no cleanup)
        subtest_dir = workspace.parent
        worktree_script = subtest_dir / "worktree_create.sh"
        worktree_script.write_text(
            f"#!/bin/bash\n# Worktree: {branch_name} @ {workspace_abs}\n"
            + " ".join(shlex.quote(arg) for arg in worktree_cmd)
            + "\n"
        )
        worktree_script.chmod(0o755)

    def _compute_judge_consensus(
        self, judges: list[JudgeResultSummary]
    ) -> tuple[float | None, bool | None, str | None]:
        """Compute consensus score from multiple judges using simple average.

        Args:
            judges: List of individual judge results

        Returns:
            Tuple of (consensus_score, passed, grade)

        """
        if not judges:
            return (None, None, None)

        # Filter judges with valid scores
        valid = [j for j in judges if j.score is not None]
        if not valid:
            return (None, None, None)

        # Simple average across judges
        consensus_score = sum(j.score for j in valid) / len(valid)

        # Majority vote for passed
        passed_votes = sum(1 for j in valid if j.passed)
        passed = passed_votes > len(valid) / 2

        # Grade from consensus score
        if consensus_score >= 0.95:
            grade = "S"
        elif consensus_score >= 0.80:
            grade = "A"
        elif consensus_score >= 0.60:
            grade = "B"
        elif consensus_score >= 0.40:
            grade = "C"
        elif consensus_score >= 0.20:
            grade = "D"
        else:
            grade = "F"

        return (consensus_score, passed, grade)

    def _run_judge(
        self,
        workspace: Path,
        task_prompt: str,
        stdout: str,
        judge_dir: Path,
        language: str = "mojo",
        rubric_path: Path | None = None,
    ) -> tuple[dict, list[JudgeResultSummary]]:
        """Run LLM judge evaluation(s) on the result.

        Runs multiple judges if configured, computes consensus.

        Args:
            workspace: Workspace with agent's output
            task_prompt: The original task prompt
            stdout: Agent's stdout output
            judge_dir: Directory for judge outputs
                (judge_01/, judge_02/, etc. for each judge)
            language: Programming language for build pipeline ('python' or 'mojo')
            rubric_path: Optional path to rubric YAML file

        Returns:
            Tuple of (consensus_dict, judges_list)
            - consensus_dict: Dict with consensus score, passed, grade, reasoning
            - judges_list: List of JudgeResultSummary for each judge

        """
        judges = []

        # Run each configured judge
        for judge_num, model in enumerate(self.config.judge_models, start=1):
            _phase_log(
                "JUDGE",
                f"Running judge {judge_num}/{len(self.config.judge_models)} "
                f"with model[{model}]",
            )

            # Use the LLM judge for proper evaluation
            judge_result = run_llm_judge(
                workspace=workspace,
                task_prompt=task_prompt,
                agent_output=stdout,
                model=model,
                judge_dir=judge_dir,
                judge_run_number=judge_num,  # Creates judge_01/, judge_02/, etc.
                language=language,
                rubric_path=rubric_path,
            )

            # Store individual judge result
            judge_summary = JudgeResultSummary(
                model=model,
                score=judge_result.score,
                passed=judge_result.passed,
                grade=judge_result.grade,
                reasoning=judge_result.reasoning,
                judge_number=judge_num,
            )
            judges.append(judge_summary)

        # Compute consensus from all judges
        consensus_score, consensus_passed, consensus_grade = self._compute_judge_consensus(judges)

        # Build consensus dict (use primary judge's reasoning)
        primary_reasoning = judges[0].reasoning if judges else ""
        consensus_dict = {
            "score": consensus_score,
            "passed": consensus_passed,
            "grade": consensus_grade,
            "reasoning": primary_reasoning,
        }

        return consensus_dict, judges

    def _aggregate_results(
        self,
        tier_id: TierID,
        subtest_id: str,
        runs: list[RunResult],
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


def run_tier_subtests_parallel(
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    tier_manager: TierManager,
    workspace_manager: WorkspaceManager,
    baseline: TierBaseline | None,
    results_dir: Path,
    checkpoint: E2ECheckpoint | None = None,
    checkpoint_path: Path | None = None,
    global_semaphore=None,
) -> dict[str, SubTestResult]:
    """Run all sub-tests for a tier in parallel with rate limit handling.

    When any worker hits a rate limit, ALL workers are paused until
    the rate limit expires, then all resume.

    Args:
        config: Experiment configuration
        tier_id: The tier being executed
        tier_config: Tier configuration with sub-tests
        tier_manager: Tier configuration manager
        workspace_manager: Workspace manager for git worktrees
        baseline: Previous tier's winning baseline
        results_dir: Base directory for tier results
        checkpoint: Optional checkpoint for resume capability
        checkpoint_path: Path to checkpoint file for saving
        global_semaphore: Optional global semaphore to limit total concurrent agents

    Returns:
        Dict mapping sub-test ID to results.

    """
    results: dict[str, SubTestResult] = {}
    executor = SubTestExecutor(config, tier_manager, workspace_manager)

    # Create rate limit coordinator for parallel execution
    manager = Manager()
    coordinator = RateLimitCoordinator(manager)

    # For single sub-test (T0, T1), run directly (no need for coordinator)
    if len(tier_config.subtests) <= 1:
        for subtest in tier_config.subtests:
            subtest_dir = results_dir / subtest.id
            try:
                results[subtest.id] = executor.run_subtest(
                    tier_id=tier_id,
                    tier_config=tier_config,
                    subtest=subtest,
                    baseline=baseline,
                    results_dir=subtest_dir,
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    coordinator=None,  # No parallel workers
                )
            except RateLimitError as e:
                # Handle rate limit in main thread for single subtest
                if checkpoint and checkpoint_path:
                    logger.info(f"Rate limit detected from {e.info.source}, waiting...")
                    wait_for_rate_limit(e.info.retry_after_seconds, checkpoint, checkpoint_path)
                    # Retry the subtest after wait
                    results[subtest.id] = executor.run_subtest(
                        tier_id=tier_id,
                        tier_config=tier_config,
                        subtest=subtest,
                        baseline=baseline,
                        results_dir=subtest_dir,
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        coordinator=None,
                    )
                else:
                    raise  # No checkpoint, can't handle - propagate
        return results

    # For multiple sub-tests, run in parallel with coordinator
    total_subtests = len(tier_config.subtests)
    start_time = time.time()

    try:
        with ProcessPoolExecutor(max_workers=config.parallel_subtests) as pool:
            futures = {}

            for subtest in tier_config.subtests:
                subtest_dir = results_dir / subtest.id
                future = pool.submit(
                    _run_subtest_in_process_safe,  # Use safe wrapper to prevent pool crashes
                    config=config,
                    tier_id=tier_id,
                    tier_config=tier_config,
                    subtest=subtest,
                    baseline=baseline,
                    results_dir=subtest_dir,
                    tiers_dir=tier_manager.tiers_dir,
                    base_repo=workspace_manager.base_repo,
                    repo_url=workspace_manager.repo_url,
                    commit=workspace_manager.commit,
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    coordinator=coordinator,
                    global_semaphore=global_semaphore,
                )
                futures[future] = subtest.id

            # Monitor futures and handle rate limits
            completed_count = 0
            for future in as_completed(futures):
                subtest_id = futures[future]
                try:
                    results[subtest_id] = future.result()
                    completed_count += 1

                    # Log progress after each completion
                    elapsed = time.time() - start_time
                    active_workers = total_subtests - completed_count
                    logger.info(
                        f"[PROGRESS] Tier {tier_id.value}: "
                        f"{completed_count}/{total_subtests} complete, "
                        f"{active_workers} active, elapsed: {elapsed:.0f}s"
                    )

                    # Check for shutdown request
                    from scylla.e2e.runner import is_shutdown_requested

                    if is_shutdown_requested():
                        logger.warning("Shutdown requested, signaling workers to stop...")
                        coordinator.signal_shutdown()
                        break

                    # Check if rate limit was signaled during execution
                    rate_limit_info = coordinator.get_rate_limit_info()
                    if rate_limit_info and checkpoint and checkpoint_path:
                        logger.info(f"Rate limit from {rate_limit_info.source}, pausing workers...")
                        # Wait for rate limit to expire
                        wait_for_rate_limit(
                            rate_limit_info.retry_after_seconds, checkpoint, checkpoint_path
                        )
                        # Resume all workers
                        coordinator.resume_all_workers()

                except RateLimitError as e:
                    # Rate limit from a worker
                    if checkpoint and checkpoint_path:
                        logger.info(
                            f"Rate limit detected from {e.info.source}, pausing all workers..."
                        )
                        wait_for_rate_limit(e.info.retry_after_seconds, checkpoint, checkpoint_path)
                        coordinator.resume_all_workers()
                    else:
                        # Create error result
                        results[subtest_id] = SubTestResult(
                            subtest_id=subtest_id,
                            tier_id=tier_id,
                            runs=[],
                            pass_rate=0.0,
                            mean_score=0.0,
                            median_score=0.0,
                            std_dev_score=0.0,
                            mean_cost=0.0,
                            total_cost=0.0,
                            consistency=0.0,
                            selection_reason=f"Rate limit: {e.info.error_message}",
                        )
                        completed_count += 1

                        # Log progress after error
                        elapsed = time.time() - start_time
                        active_workers = total_subtests - completed_count
                        logger.info(
                            f"[PROGRESS] Tier {tier_id.value}: "
                            f"{completed_count}/{total_subtests} complete, "
                            f"{active_workers} active, elapsed: {elapsed:.0f}s"
                        )

                except Exception as e:
                    # Other errors
                    results[subtest_id] = SubTestResult(
                        subtest_id=subtest_id,
                        tier_id=tier_id,
                        runs=[],
                        pass_rate=0.0,
                        mean_score=0.0,
                        median_score=0.0,
                        std_dev_score=0.0,
                        mean_cost=0.0,
                        total_cost=0.0,
                        consistency=0.0,
                        selection_reason=f"Error: {e}",
                    )
                    completed_count += 1

                    # Log progress after error
                    elapsed = time.time() - start_time
                    active_workers = total_subtests - completed_count
                    logger.info(
                        f"[PROGRESS] Tier {tier_id.value}: "
                        f"{completed_count}/{total_subtests} complete, "
                        f"{active_workers} active, elapsed: {elapsed:.0f}s"
                    )

    except (KeyboardInterrupt, BrokenProcessPool) as e:
        if isinstance(e, BrokenProcessPool):
            # Scan results for rate limit indicators
            rate_limit_info = _detect_rate_limit_from_results(results, results_dir)

            if rate_limit_info and checkpoint and checkpoint_path:
                logger.warning(
                    f"BrokenProcessPool caused by rate limit from {rate_limit_info.source}"
                )
                logger.info(f"Waiting {rate_limit_info.retry_after_seconds or 60}s before retry...")

                wait_for_rate_limit(
                    rate_limit_info.retry_after_seconds,
                    checkpoint,
                    checkpoint_path,
                )

                # Identify remaining subtests (not yet completed OR marked as rate_limited)
                remaining = [
                    s
                    for s in tier_config.subtests
                    if s.id not in results
                    or results[s.id].selection_reason.startswith("RateLimitError:")
                ]

                if remaining:
                    logger.info(f"Retrying {len(remaining)} subtests after rate limit...")
                    retry_results = _retry_with_new_pool(
                        remaining_subtests=remaining,
                        config=config,
                        tier_id=tier_id,
                        tier_config=tier_config,
                        tier_manager=tier_manager,
                        workspace_manager=workspace_manager,
                        baseline=baseline,
                        results_dir=results_dir,
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        global_semaphore=global_semaphore,
                    )
                    results.update(retry_results)
                    return results

            # Not a rate limit, or no checkpoint - fall through to cleanup
            logger.error(f"BrokenProcessPool with no recovery path: {e}")

        # KeyboardInterrupt or unrecoverable - cleanup
        logger.warning("Experiment interrupted, cleaning up...")
        # Cancel pending futures
        for future in futures:
            if not future.done():
                future.cancel()

    return results


def _detect_rate_limit_from_results(
    results: dict[str, SubTestResult],
    results_dir: Path,
) -> RateLimitInfo | None:
    """Detect rate limit from completed results OR .failed/ directories.

    Checks:
    1. SubTestResult.rate_limit_info field (from safe wrapper)
    2. SubTestResult.selection_reason for "RateLimitError:" prefix
    3. .failed/*/agent/result.json for rate limit patterns in stderr

    Args:
        results: Dictionary of completed subtest results
        results_dir: Base directory for tier results

    Returns:
        RateLimitInfo if rate limit detected, None otherwise

    """
    # Check structured results first (from safe wrapper)
    for subtest_id, result in results.items():
        if result.rate_limit_info:
            logger.debug(f"Rate limit found in {subtest_id}.rate_limit_info")
            return result.rate_limit_info
        if result.selection_reason.startswith("RateLimitError:"):
            # Parse from selection_reason if rate_limit_info not available
            logger.debug(f"Rate limit found in {subtest_id}.selection_reason")
            return RateLimitInfo(
                source="agent",
                retry_after_seconds=None,  # Will use default
                error_message=result.selection_reason,
                detected_at=datetime.now(timezone.utc).isoformat(),
            )

    # Check .failed/ directories for crashed workers
    for failed_dir in results_dir.rglob(".failed/*/agent/result.json"):
        try:
            import json

            data = json.loads(failed_dir.read_text())
            stderr = data.get("stderr", "")
            stdout = data.get("stdout", "")

            rate_info = detect_rate_limit(stdout, stderr, source="agent")
            if rate_info:
                logger.debug(f"Rate limit found in failed run: {failed_dir}")
                return rate_info
        except Exception as e:
            logger.debug(f"Failed to check {failed_dir} for rate limit: {e}")
            continue

    return None


def _retry_with_new_pool(
    remaining_subtests: list[SubTestConfig],
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    tier_manager: TierManager,
    workspace_manager: WorkspaceManager,
    baseline: TierBaseline | None,
    results_dir: Path,
    checkpoint: E2ECheckpoint | None,
    checkpoint_path: Path | None,
    global_semaphore,
    max_retries: int = 3,
) -> dict[str, SubTestResult]:
    """Create new ProcessPoolExecutor and retry remaining subtests.

    Has its own retry loop for repeated rate limits.

    Args:
        remaining_subtests: Subtests that need to be retried
        config: Experiment configuration
        tier_id: Tier identifier
        tier_config: Tier configuration
        tier_manager: Tier manager instance
        workspace_manager: Workspace manager instance
        baseline: Previous tier's baseline
        results_dir: Base directory for tier results
        checkpoint: Optional checkpoint for resume
        checkpoint_path: Path to checkpoint file
        global_semaphore: Global semaphore for limiting concurrent agents
        max_retries: Maximum retry attempts for rate limits

    Returns:
        Dictionary of SubTestResults for retried subtests

    """
    results: dict[str, SubTestResult] = {}
    retries = 0

    while remaining_subtests and retries < max_retries:
        logger.info(
            f"Retry attempt {retries + 1}/{max_retries} for {len(remaining_subtests)} subtests"
        )

        try:
            # Fresh coordinator for new pool
            manager = Manager()
            coordinator = RateLimitCoordinator(manager)

            with ProcessPoolExecutor(max_workers=config.parallel_subtests) as pool:
                futures = {}
                for subtest in remaining_subtests:
                    subtest_dir = results_dir / subtest.id
                    future = pool.submit(
                        _run_subtest_in_process_safe,  # Use safe wrapper
                        config=config,
                        tier_id=tier_id,
                        tier_config=tier_config,
                        subtest=subtest,
                        baseline=baseline,
                        results_dir=subtest_dir,
                        tiers_dir=tier_manager.tiers_dir,
                        base_repo=workspace_manager.base_repo,
                        repo_url=workspace_manager.repo_url,
                        commit=workspace_manager.commit,
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        coordinator=coordinator,
                        global_semaphore=global_semaphore,
                    )
                    futures[future] = subtest.id

                # Collect results
                for future in as_completed(futures):
                    subtest_id = futures[future]
                    try:
                        result = future.result()
                        results[subtest_id] = result
                    except Exception as e:
                        # Should not happen with safe wrapper, but be defensive
                        logger.error(f"Unexpected exception from safe wrapper: {e}")
                        results[subtest_id] = SubTestResult(
                            subtest_id=subtest_id,
                            tier_id=tier_id,
                            runs=[],
                            pass_rate=0.0,
                            selection_reason=f"UnexpectedError: {e}",
                        )

            # Check for rate-limited results that need retry
            remaining_subtests = [
                s
                for s in remaining_subtests
                if s.id in results and results[s.id].selection_reason.startswith("RateLimitError:")
            ]

            if remaining_subtests:
                # More rate limits - wait and retry
                rate_info = _detect_rate_limit_from_results(results, results_dir)
                if rate_info and checkpoint and checkpoint_path:
                    logger.info(
                        f"Rate limit still active after retry {retries + 1}, waiting again..."
                    )
                    wait_for_rate_limit(
                        rate_info.retry_after_seconds,
                        checkpoint,
                        checkpoint_path,
                    )
                else:
                    # No rate limit info but still failing - give up
                    logger.warning(
                        f"Subtests still failing after retry {retries + 1} "
                        f"but no rate limit detected"
                    )
                    break

                retries += 1
            else:
                # All subtests completed successfully or with non-rate-limit errors
                break

        except BrokenProcessPool as e:
            # Pool crashed again - check for rate limit and retry
            logger.warning(f"BrokenProcessPool during retry attempt {retries + 1}: {e}")
            rate_info = _detect_rate_limit_from_results(results, results_dir)
            if rate_info and checkpoint and checkpoint_path:
                wait_for_rate_limit(
                    rate_info.retry_after_seconds,
                    checkpoint,
                    checkpoint_path,
                )
                retries += 1
            else:
                # Pool crashed but not due to rate limit - give up
                logger.error("BrokenProcessPool without rate limit, cannot retry")
                break

    if retries >= max_retries:
        logger.warning(
            f"Max retries ({max_retries}) reached, {len(remaining_subtests)} subtests still failing"
        )

    return results


def _run_subtest_in_process_safe(
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    subtest: SubTestConfig,
    baseline: TierBaseline | None,
    results_dir: Path,
    tiers_dir: Path,
    base_repo: Path,
    repo_url: str,
    commit: str | None,
    checkpoint: E2ECheckpoint | None = None,
    checkpoint_path: Path | None = None,
    coordinator: RateLimitCoordinator | None = None,
    global_semaphore=None,
) -> SubTestResult:
    """Safe wrapper that catches ALL exceptions and returns structured error.

    This prevents worker crashes from poisoning the entire ProcessPoolExecutor.
    Any exception (including RateLimitError) is converted to a SubTestResult
    with error details in selection_reason.

    Args:
        (same as _run_subtest_in_process)

    Returns:
        SubTestResult (never raises exceptions)

    """
    try:
        return _run_subtest_in_process(
            config=config,
            tier_id=tier_id,
            tier_config=tier_config,
            subtest=subtest,
            baseline=baseline,
            results_dir=results_dir,
            tiers_dir=tiers_dir,
            base_repo=base_repo,
            repo_url=repo_url,
            commit=commit,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            coordinator=coordinator,
            global_semaphore=global_semaphore,
        )
    except RateLimitError as e:
        # Return structured error, don't crash pool
        logger.warning(
            f"Rate limit in worker for {tier_id.value}/{subtest.id}: {e.info.error_message}"
        )
        return SubTestResult(
            subtest_id=subtest.id,
            tier_id=tier_id,
            runs=[],
            pass_rate=0.0,
            mean_score=0.0,
            median_score=0.0,
            std_dev_score=0.0,
            mean_cost=0.0,
            total_cost=0.0,
            consistency=0.0,
            selected_as_best=False,
            selection_reason=f"RateLimitError: {e.info.error_message}",
            # Store rate limit info for retry logic
            rate_limit_info=e.info,
        )
    except Exception as e:
        # ANY exception becomes structured error
        logger.error(
            f"Worker exception for {tier_id.value}/{subtest.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        return SubTestResult(
            subtest_id=subtest.id,
            tier_id=tier_id,
            runs=[],
            pass_rate=0.0,
            mean_score=0.0,
            median_score=0.0,
            std_dev_score=0.0,
            mean_cost=0.0,
            total_cost=0.0,
            consistency=0.0,
            selected_as_best=False,
            selection_reason=f"WorkerError: {type(e).__name__}: {e}",
        )


def _run_subtest_in_process(
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    subtest: SubTestConfig,
    baseline: TierBaseline | None,
    results_dir: Path,
    tiers_dir: Path,
    base_repo: Path,
    repo_url: str,
    commit: str | None,
    checkpoint: E2ECheckpoint | None = None,
    checkpoint_path: Path | None = None,
    coordinator: RateLimitCoordinator | None = None,
    global_semaphore=None,
) -> SubTestResult:
    """Run a sub-test in a separate process.

    This is a helper for parallel execution with checkpoint and rate limit support.

    Args:
        config: Experiment configuration
        tier_id: Tier ID
        tier_config: Tier configuration
        subtest: Subtest configuration
        baseline: Baseline from previous tier
        results_dir: Results directory for this subtest
        tiers_dir: Path to tier configurations
        base_repo: Base repository path
        repo_url: Repository URL
        commit: Commit hash
        checkpoint: Optional checkpoint for resume
        checkpoint_path: Path to checkpoint file
        coordinator: Optional rate limit coordinator
        global_semaphore: Optional global semaphore to limit concurrent agents across all tiers

    Returns:
        SubTestResult

    """
    # Acquire global semaphore to limit concurrent agents across all tiers
    if global_semaphore:
        global_semaphore.acquire()

    try:
        tier_manager = TierManager(tiers_dir)
        # Recreate workspace manager in child process
        workspace_manager = WorkspaceManager(
            experiment_dir=base_repo.parent,
            repo_url=repo_url,
            commit=commit,
        )
        workspace_manager._is_setup = True  # Base repo already exists
        workspace_manager.base_repo = base_repo

        executor = SubTestExecutor(config, tier_manager, workspace_manager)
        return executor.run_subtest(
            tier_id=tier_id,
            tier_config=tier_config,
            subtest=subtest,
            baseline=baseline,
            results_dir=results_dir,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            coordinator=coordinator,
        )
    finally:
        # Always release semaphore, even if exception occurred
        if global_semaphore:
            global_semaphore.release()
