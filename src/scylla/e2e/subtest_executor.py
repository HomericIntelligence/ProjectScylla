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
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from multiprocessing import Manager
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.adapters.base import AdapterConfig
from scylla.adapters.claude_code import ClaudeCodeAdapter
from scylla.e2e.command_logger import CommandLogger
from scylla.e2e.llm_judge import run_llm_judge
from scylla.e2e.models import (
    ExperimentConfig,
    RunResult,
    SubTestConfig,
    SubTestResult,
    TierBaseline,
    TierConfig,
    TierID,
    TokenStats,
)
from scylla.e2e.rate_limit import RateLimitError, RateLimitInfo, wait_for_rate_limit
from scylla.e2e.run_report import save_run_report, save_run_report_json
from scylla.e2e.tier_manager import TierManager
from scylla.e2e.workspace_manager import WorkspaceManager

if TYPE_CHECKING:
    from multiprocessing.managers import SyncManager

    from scylla.e2e.checkpoint import E2ECheckpoint

logger = logging.getLogger(__name__)


def _phase_log(phase: str, message: str) -> None:
    """Log a phase message with timestamp and prefix.

    Args:
        phase: Phase identifier (WORKTREE, AGENT, JUDGE)
        message: Message content

    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    logger.info(f"{timestamp} [{phase}] - {message}")


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
        "token_stats": result.token_stats.to_dict(),
        "cost_usd": result.cost_usd,
        "api_calls": result.api_calls,
    }

    with open(agent_dir / "result.json", "w") as f:
        json.dump(result_data, f, indent=2)


def _load_agent_result(agent_dir: Path) -> AdapterResult:
    """Load agent execution result from agent/result.json.

    Args:
        agent_dir: Path to agent directory

    Returns:
        AdapterResult loaded from file

    """
    import json

    from scylla.adapters.base import AdapterResult, AdapterTokenStats

    with open(agent_dir / "result.json") as f:
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

    with open(judge_dir / "result.json", "w") as f:
        json.dump(result_data, f, indent=2)


def _load_judge_result(judge_dir: Path) -> dict:
    """Load judge evaluation result from judge/result.json.

    Args:
        judge_dir: Path to judge directory

    Returns:
        Dict with score, passed, grade, reasoning

    """
    import json

    # Load from judgment.json (full result with criteria_scores)
    with open(judge_dir / "judgment.json") as f:
        data = json.load(f)

    return data


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

        # Check if ALL runs are already completed (checkpoint resume optimization)
        all_completed = True
        if checkpoint:
            for run_num in range(1, self.config.runs_per_subtest + 1):
                if not checkpoint.is_run_completed(tier_id.value, subtest.id, run_num):
                    all_completed = False
                    break

        # Only setup workspace if there are runs to execute
        if not all_completed:
            # Create workspace at subtest level (shared across all runs)
            workspace = results_dir / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            self._setup_workspace(workspace, CommandLogger(results_dir), tier_id, subtest.id)

            # Prepare tier configuration in workspace once
            self.tier_manager.prepare_workspace(
                workspace=workspace,
                tier_id=tier_id,
                subtest_id=subtest.id,
                baseline=baseline,
            )
        else:
            # All runs completed, just use existing workspace path
            workspace = results_dir / "workspace"

        for run_num in range(1, self.config.runs_per_subtest + 1):
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
                            f"Skipping completed run: {tier_id.value}/{subtest.id}/run_{run_num:02d}"
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
                        f"Checkpoint saved: {tier_id.value}/{subtest.id}/run_{run_num:02d} (status={status})"
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
        self.tier_manager.save_resource_manifest(
            results_dir=results_dir,
            tier_id=tier_id,
            subtest=subtest,
            workspace=workspace,
            baseline=baseline,
        )

        # Aggregate results
        return self._aggregate_results(tier_id, subtest.id, runs)

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
        - agent/: Agent execution artifacts (stdout, stderr, output.txt, command_log.json, replay.sh)
        - judge/: Judge evaluation artifacts (prompt.md, response.txt, judgment.json, replay.sh)
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
        # Create agent and judge subdirectories
        agent_dir = run_dir / "agent"
        judge_dir = run_dir / "judge"
        agent_dir.mkdir(parents=True, exist_ok=True)
        judge_dir.mkdir(parents=True, exist_ok=True)

        # Agent command logger outputs to agent/
        command_logger = CommandLogger(agent_dir)

        # Build context-aware resource suffix
        resource_suffix = self.tier_manager.build_resource_suffix(subtest)
        if resource_suffix:
            task_prompt = f"{task_prompt}\n\n{resource_suffix}"

        # Save task prompt to run dir (for reference, though uniform across runs)
        prompt_file = run_dir / "task_prompt.md"
        prompt_file.write_text(task_prompt)

        # Build extra args for adapter
        extra_args: list[str] = []
        if self.config.max_turns is not None:
            extra_args.extend(["--max-turns", str(self.config.max_turns)])

        # Check if agent result already exists (resume case)
        agent_result_file = agent_dir / "result.json"
        agent_ran = False

        if agent_result_file.exists():
            # Reuse existing agent result
            logger.info(f"Reusing existing agent result: {agent_result_file}")
            result = _load_agent_result(agent_dir)
            duration = 0.0  # Duration not tracked for reused results
        else:
            # Run agent
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

            start_time = datetime.now(UTC)
            try:
                result = self.adapter.run(
                    config=adapter_config,
                    tier_config=None,  # Tier config handled by workspace preparation
                    system_prompt_mode=tier_config.system_prompt_mode,
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

            duration = (datetime.now(UTC) - start_time).total_seconds()

            # Log the command
            cmd = self.adapter._build_command(
                adapter_config,
                task_prompt,
                None,
                tier_config.system_prompt_mode,
            )
            command_logger.log_command(
                cmd=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                duration=duration,
                cwd=str(workspace),
            )

            # Save command logs
            command_logger.save()
            command_logger.save_replay_script()

            # Save agent output to agent/output.txt
            output_file = agent_dir / "output.txt"
            output_file.write_text(result.stdout or "")

            # Save agent result for future resume
            _save_agent_result(agent_dir, result)
            agent_ran = True

        # Run judge evaluation (ALWAYS re-run if agent ran, requirement from user)
        # Only reuse judge result if agent was reused AND judge result exists
        judge_result_file = judge_dir / "result.json"

        if not agent_ran and judge_result_file.exists():
            # Reuse existing judge result (only if agent was also reused)
            logger.info(f"Reusing existing judge result: {judge_result_file}")
            judgment = _load_judge_result(judge_dir)
        else:
            # Run judge (either agent ran, or judge result missing)
            judgment = self._run_judge(
                workspace=workspace,
                task_prompt=task_prompt,
                stdout=result.stdout,
                judge_dir=judge_dir,
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
            duration_seconds=duration,
            judge_score=judgment["score"],
            judge_passed=judgment["passed"],
            judge_grade=judgment["grade"],
            judge_reasoning=judgment["reasoning"],
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
            cost_usd=result.cost_usd,
            duration_seconds=duration,
            tokens_input=run_result.tokens_input,  # Legacy property for fallback
            tokens_output=run_result.tokens_output,  # Legacy property for fallback
            exit_code=result.exit_code,
            task_prompt=task_prompt,
            workspace_path=workspace,
            criteria_scores=judgment.get("criteria_scores"),
            agent_output=result.stdout[:2000] if result.stdout else None,
            token_stats=token_stats.to_dict(),  # Pass detailed stats
        )

        # JSON report for hierarchical linking
        save_run_report_json(
            run_dir=run_dir,
            run_number=run_number,
            score=judgment["score"],
            grade=judgment["grade"],
            passed=judgment["passed"],
            cost_usd=result.cost_usd,
            duration_seconds=duration,
        )

        return run_result

    def _setup_workspace(
        self,
        workspace: Path,
        command_logger: CommandLogger,
        tier_id: TierID,
        subtest_id: str,
    ) -> None:
        """Set up workspace using git worktree from base repo with named branch.

        Args:
            workspace: Target workspace directory
            command_logger: Logger for commands
            tier_id: Tier identifier for branch naming
            subtest_id: Subtest identifier for branch naming

        """
        import shlex

        start_time = datetime.now(UTC)

        # Ensure workspace path is absolute for git worktree
        workspace_abs = workspace.resolve()

        # Generate branch name
        branch_name = f"{tier_id.value}_{subtest_id}"

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

        duration = (datetime.now(UTC) - start_time).total_seconds()
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

    def _run_judge(
        self,
        workspace: Path,
        task_prompt: str,
        stdout: str,
        judge_dir: Path,
    ) -> dict:
        """Run LLM judge evaluation on the result.

        Uses a real LLM to evaluate task completion against the requirements.

        Args:
            workspace: Workspace with agent's output
            task_prompt: The original task prompt
            stdout: Agent's stdout output
            judge_dir: Directory for judge outputs (prompt.md, response.txt, judgment.json, replay.sh)

        Returns:
            Dict with score, passed, grade, and reasoning.

        """
        # Log judge execution phase
        _phase_log(
            "JUDGE",
            f"Running judge with model[{self.config.judge_model}] with prompt[{judge_dir / 'prompt.md'}]",
        )

        # Use the LLM judge for proper evaluation
        judge_result = run_llm_judge(
            workspace=workspace,
            task_prompt=task_prompt,
            agent_output=stdout,
            model=self.config.judge_model,
            judge_dir=judge_dir,  # Judge outputs go in judge/
        )

        return judge_result.to_dict()

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
    with ProcessPoolExecutor(max_workers=config.parallel_subtests) as pool:
        futures = {}

        for subtest in tier_config.subtests:
            subtest_dir = results_dir / subtest.id
            future = pool.submit(
                _run_subtest_in_process,
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
            )
            futures[future] = subtest.id

        # Monitor futures and handle rate limits
        for future in as_completed(futures):
            subtest_id = futures[future]
            try:
                results[subtest_id] = future.result()

                # Check if rate limit was signaled during execution
                rate_limit_info = coordinator.get_rate_limit_info()
                if rate_limit_info and checkpoint and checkpoint_path:
                    logger.info(
                        f"Rate limit detected from {rate_limit_info.source}, pausing all workers..."
                    )
                    # Wait for rate limit to expire
                    wait_for_rate_limit(
                        rate_limit_info.retry_after_seconds, checkpoint, checkpoint_path
                    )
                    # Resume all workers
                    coordinator.resume_all_workers()

            except RateLimitError as e:
                # Rate limit from a worker
                if checkpoint and checkpoint_path:
                    logger.info(f"Rate limit detected from {e.info.source}, pausing all workers...")
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

    return results


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

    Returns:
        SubTestResult

    """
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
