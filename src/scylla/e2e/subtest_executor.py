"""Sub-test executor for E2E testing.

This module handles executing individual sub-tests, including
workspace preparation, agent execution, judging, and result aggregation.

Python Justification: Required for subprocess execution, parallel processing,
and filesystem operations.
"""

from __future__ import annotations

import shutil
import statistics
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
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
)
from scylla.e2e.run_report import save_run_report, save_run_report_json
from scylla.e2e.tier_manager import TierManager
from scylla.e2e.workspace_manager import WorkspaceManager

if TYPE_CHECKING:
    pass


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
    ) -> SubTestResult:
        """Run a single sub-test N times and aggregate results.

        Creates workspace at subtest level (shared across runs) for efficiency.
        Each run gets its own directory for output.txt, judgment.json, etc.

        Args:
            tier_id: The tier being executed
            tier_config: Tier configuration
            subtest: Sub-test configuration
            baseline: Previous tier's winning baseline (if any)
            results_dir: Directory to store results (subtest directory)

        Returns:
            SubTestResult with aggregated metrics.
        """
        runs: list[RunResult] = []
        results_dir.mkdir(parents=True, exist_ok=True)

        # Load task prompt once
        task_prompt = self.config.task_prompt_file.read_text()

        # Create workspace at subtest level (shared across all runs)
        workspace = results_dir / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        self._setup_workspace(workspace, CommandLogger(results_dir))

        # Prepare tier configuration in workspace once
        self.tier_manager.prepare_workspace(
            workspace=workspace,
            tier_id=tier_id,
            subtest_id=subtest.id,
            baseline=baseline,
        )

        for run_num in range(1, self.config.runs_per_subtest + 1):
            run_dir = results_dir / f"run_{run_num:02d}"
            run_dir.mkdir(parents=True, exist_ok=True)

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

        Files are placed directly in run_dir (no logs/ subdir):
        - output.txt: Agent stdout
        - command_log.json: Execution details
        - judgment.json: LLM judge result
        - report.md: Run report

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
        # All files go directly in run_dir (no logs/ subdir)
        command_logger = CommandLogger(run_dir)

        # Save task prompt to run dir (for reference, though uniform across runs)
        prompt_file = run_dir / "task_prompt.md"
        prompt_file.write_text(task_prompt)

        # Build extra args for adapter
        extra_args: list[str] = []
        if self.config.max_turns is not None:
            extra_args.extend(["--max-turns", str(self.config.max_turns)])

        adapter_config = AdapterConfig(
            model=self.config.models[0],
            prompt_file=prompt_file,
            workspace=workspace,
            output_dir=run_dir,  # Files go directly in run_dir
            timeout=self.config.timeout_seconds,
            extra_args=extra_args,
        )

        # Execute agent
        start_time = datetime.now(UTC)
        try:
            result = self.adapter.run(
                config=adapter_config,
                tier_config=None,  # Tier config handled by workspace preparation
                system_prompt_mode=tier_config.system_prompt_mode,
            )
        except Exception as e:
            # Handle execution errors
            result = type(
                "ErrorResult",
                (),
                {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "cost_usd": 0.0,
                    "api_calls": 0,
                },
            )()

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

        # Save agent output to output.txt
        output_file = run_dir / "output.txt"
        output_file.write_text(result.stdout or "")

        # Run judge evaluation
        judgment = self._run_judge(
            workspace=workspace,
            task_prompt=task_prompt,
            stdout=result.stdout,
            run_dir=run_dir,
        )

        run_result = RunResult(
            run_number=run_number,
            exit_code=result.exit_code,
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            cost_usd=result.cost_usd,
            duration_seconds=duration,
            judge_score=judgment["score"],
            judge_passed=judgment["passed"],
            judge_grade=judgment["grade"],
            judge_reasoning=judgment["reasoning"],
            workspace_path=workspace,
            logs_path=run_dir,  # Now same as run_dir (no logs/ subdir)
            command_log_path=run_dir / "command_log.json",
        )

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
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            exit_code=result.exit_code,
            task_prompt=task_prompt,
            workspace_path=workspace,
            criteria_scores=judgment.get("criteria_scores"),
            agent_output=result.stdout[:2000] if result.stdout else None,
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
    ) -> None:
        """Set up workspace using git worktree from base repo.

        Args:
            workspace: Target workspace directory
            command_logger: Logger for commands
        """
        start_time = datetime.now(UTC)

        # Ensure workspace path is absolute for git worktree
        workspace_abs = workspace.resolve()

        # Create worktree from shared base repo
        worktree_cmd = [
            "git",
            "-C",
            str(self.workspace_manager.base_repo),
            "worktree",
            "add",
            "--detach",
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

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr}")

    def _run_judge(
        self,
        workspace: Path,
        task_prompt: str,
        stdout: str,
        run_dir: Path,
    ) -> dict:
        """Run LLM judge evaluation on the result.

        Uses a real LLM to evaluate task completion against the requirements.

        Args:
            workspace: Workspace with agent's output
            task_prompt: The original task prompt
            stdout: Agent's stdout output
            run_dir: Directory for judge logs (judgment.json goes here)

        Returns:
            Dict with score, passed, grade, and reasoning.
        """
        # Use the LLM judge for proper evaluation
        judge_result = run_llm_judge(
            workspace=workspace,
            task_prompt=task_prompt,
            agent_output=stdout,
            model=self.config.judge_model,
            logs_dir=run_dir,  # Judge logs go in run_dir
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
        )


def run_tier_subtests_parallel(
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    tier_manager: TierManager,
    workspace_manager: WorkspaceManager,
    baseline: TierBaseline | None,
    results_dir: Path,
) -> dict[str, SubTestResult]:
    """Run all sub-tests for a tier in parallel.

    Args:
        config: Experiment configuration
        tier_id: The tier being executed
        tier_config: Tier configuration with sub-tests
        tier_manager: Tier configuration manager
        workspace_manager: Workspace manager for git worktrees
        baseline: Previous tier's winning baseline
        results_dir: Base directory for tier results

    Returns:
        Dict mapping sub-test ID to results.
    """
    results: dict[str, SubTestResult] = {}
    executor = SubTestExecutor(config, tier_manager, workspace_manager)

    # For single sub-test (T0, T1), run directly
    if len(tier_config.subtests) <= 1:
        for subtest in tier_config.subtests:
            subtest_dir = results_dir / subtest.id
            results[subtest.id] = executor.run_subtest(
                tier_id=tier_id,
                tier_config=tier_config,
                subtest=subtest,
                baseline=baseline,
                results_dir=subtest_dir,
            )
        return results

    # For multiple sub-tests, run in parallel
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
            )
            futures[future] = subtest.id

        for future in as_completed(futures):
            subtest_id = futures[future]
            try:
                results[subtest_id] = future.result()
            except Exception as e:
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
) -> SubTestResult:
    """Run a sub-test in a separate process.

    This is a helper for parallel execution.
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
    )
