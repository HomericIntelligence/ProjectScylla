"""Test runner orchestration for agent evaluations.

This module provides the EvalRunner class that orchestrates test execution
across multiple tiers, models, and runs in Docker containers.
parallel execution, and file I/O operations.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from scylla.core.results import RunResultBase

if TYPE_CHECKING:
    from scylla.executor.docker import ContainerResult, DockerExecutor
    from scylla.executor.tier_config import TierConfig, TierConfigLoader


class RunStatus(str, Enum):
    """Status of a single run."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class RunnerError(Exception):
    """Base exception for runner errors."""

    pass


class RateLimitError(RunnerError):
    """Raised when API rate limit is exceeded."""

    pass


class InsufficientRunsError(RunnerError):
    """Raised when minimum runs cannot be achieved."""

    pass


class ExecutionInfo(BaseModel):
    """Detailed execution information for container runs.

    This is the executor's detailed execution info, including container
    and output details. For simpler execution info, see:
    - reporting/result.py:ExecutionInfo (minimal, for persistence)
    - core/results.py:BaseExecutionInfo (base type)
    """

    container_id: str = Field(..., description="Docker container ID")
    exit_code: int = Field(..., description="Container exit code")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    timed_out: bool = Field(default=False, description="Whether execution timed out")
    duration_seconds: float = Field(default=0.0, description="Execution duration")
    started_at: str = Field(default="", description="ISO timestamp of start")
    ended_at: str = Field(default="", description="ISO timestamp of end")


class JudgmentResult(BaseModel):
    """Result from judge evaluation."""

    passed: bool = Field(..., description="Whether the run passed judgment")
    score: float = Field(default=0.0, description="Judgment score (0-1)")
    reasoning: str = Field(default="", description="Judge reasoning")
    consensus_runs: int = Field(default=3, description="Number of judge runs for consensus")


class ExecutorRunResult(RunResultBase):
    """Result of a single run with execution tracking.

    This is the executor's run result with status tracking and optional
    judgment. Inherits common fields (run_number, cost_usd, duration_seconds) from RunResultBase.

    For other RunResult types in the hierarchy, see:
    - RunResultBase (core/results.py) - Base Pydantic model
    - E2ERunResult (e2e/models.py) - E2E testing with judge fields
    - ReportingRunResult (reporting/result.py) - Persistence with nested info
    - MetricsRunResult (metrics/aggregator.py) - Statistical aggregation
    """

    status: RunStatus = Field(..., description="Run status")
    execution_info: ExecutionInfo | None = Field(default=None, description="Execution details")
    judgment: JudgmentResult | None = Field(default=None, description="Judge evaluation")
    error_message: str | None = Field(default=None, description="Error message if failed")


class TierSummary(BaseModel):
    """Summary of results for a single tier."""

    tier_id: str = Field(..., description="Tier identifier")
    model: str = Field(..., description="Model identifier")
    total_runs: int = Field(..., description="Total runs attempted")
    passed_runs: int = Field(default=0, description="Runs that passed judgment")
    failed_runs: int = Field(default=0, description="Runs that failed judgment")
    error_runs: int = Field(default=0, description="Runs with errors")
    timeout_runs: int = Field(default=0, description="Runs that timed out")
    pass_rate: float = Field(default=0.0, description="Pass rate (0-1)")
    pass_rate_ci_low: float = Field(default=0.0, description="Pass rate 95% CI lower bound")
    pass_rate_ci_high: float = Field(default=0.0, description="Pass rate 95% CI upper bound")
    runs: list[ExecutorRunResult] = Field(
        default_factory=list, description="Individual run results"
    )


class EvalSummary(BaseModel):
    """Complete summary of a test execution."""

    test_id: str = Field(..., description="Test identifier")
    started_at: str = Field(..., description="ISO timestamp of start")
    ended_at: str = Field(default="", description="ISO timestamp of end")
    status: str = Field(default="running", description="Overall status")
    tiers: dict[str, dict[str, TierSummary]] = Field(
        default_factory=dict,
        description="Results by tier_id -> model -> TierSummary",
    )


class RunnerConfig(BaseModel):
    """Configuration for the test runner."""

    runs_per_tier: int = Field(default=10, description="Number of runs per tier")
    min_successful_runs: int = Field(default=5, description="Minimum runs required per tier")
    parallel: bool = Field(default=False, description="Enable parallel execution")
    max_parallel_workers: int = Field(default=4, description="Max parallel workers")
    timeout_seconds: int = Field(default=3600, description="Timeout per run in seconds")
    max_retries: int = Field(default=6, description="Max retries for rate limits")
    initial_backoff: float = Field(default=1.0, description="Initial backoff in seconds")
    max_backoff: float = Field(default=64.0, description="Maximum backoff in seconds")
    state_file: Path | None = Field(default=None, description="State file for resume support")
    container_image: str = Field(
        default="scylla-runner:latest", description="Docker image for execution"
    )

    model_config = {"arbitrary_types_allowed": True}


@dataclass
class ExecutionState:
    """State for resume support."""

    test_id: str
    completed_runs: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    # tier_id -> model -> list of completed run numbers
    started_at: str = ""
    version: str = "1.0"

    def is_run_completed(self, tier_id: str, model: str, run_number: int) -> bool:
        """Check if a specific run is already completed."""
        tier_runs = self.completed_runs.get(tier_id, {})
        model_runs = tier_runs.get(model, [])
        return run_number in model_runs

    def mark_run_completed(self, tier_id: str, model: str, run_number: int) -> None:
        """Mark a run as completed."""
        if tier_id not in self.completed_runs:
            self.completed_runs[tier_id] = {}
        if model not in self.completed_runs[tier_id]:
            self.completed_runs[tier_id][model] = []
        if run_number not in self.completed_runs[tier_id][model]:
            self.completed_runs[tier_id][model].append(run_number)


def calculate_wilson_ci(
    successes: int, total: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Calculate Wilson score confidence interval for pass rate.

    Args:
        successes: Number of successful runs.
        total: Total number of runs.
        confidence: Confidence level (default 0.95 for 95% CI).

    Returns:
        Tuple of (lower_bound, upper_bound) for pass rate.

    """
    if total == 0:
        return 0.0, 0.0

    z = 1.96 if confidence == 0.95 else 2.576  # Z-score for 95% or 99% CI
    p_hat = successes / total
    n = total

    denominator = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denominator
    margin = (z / denominator) * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))

    return max(0.0, center - margin), min(1.0, center + margin)


def save_state(state: ExecutionState, path: Path) -> None:
    """Save execution state to file.

    Args:
        state: Current execution state.
        path: Path to state file.

    """
    state_dict = {
        "version": state.version,
        "test_id": state.test_id,
        "started_at": state.started_at,
        "completed_runs": state.completed_runs,
    }
    # Atomic write using temp file
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w") as f:
        json.dump(state_dict, f, indent=2)
    temp_path.replace(path)


def load_state(path: Path) -> ExecutionState | None:
    """Load execution state from file.

    Args:
        path: Path to state file.

    Returns:
        Loaded state or None if file doesn't exist.

    """
    if not path.exists():
        return None

    with open(path) as f:
        data = json.load(f)

    # Version compatibility check
    if data.get("version", "0.0") != "1.0":
        return None

    return ExecutionState(
        test_id=data["test_id"],
        completed_runs=data.get("completed_runs", {}),
        started_at=data.get("started_at", ""),
        version=data.get("version", "1.0"),
    )


class EvalRunner:
    """Orchestrates test execution across tiers, models, and runs.

    This class manages the complete test execution workflow:
    1. Load test configuration and tier definitions
    2. Execute runs in Docker containers
    3. Apply exponential backoff for rate limits
    4. Handle partial failures
    5. Aggregate and report results

    Example:
        >>> runner = EvalRunner(docker_executor, tier_loader, config)
        >>> summary = runner.run_test(
        ...     test_id="test-001",
        ...     tiers=["T0", "T1", "T2"],
        ...     models=["claude-sonnet-4-5-20250929"],
        ... )
        >>> print(f"T0 pass rate: {summary.tiers['T0']['claude-sonnet-4-5-20250929'].pass_rate}")

    """

    def __init__(
        self,
        docker_executor: DockerExecutor,
        tier_loader: TierConfigLoader,
        config: RunnerConfig | None = None,
    ) -> None:
        """Initialize the test runner.

        Args:
            docker_executor: Docker executor for container management.
            tier_loader: Tier configuration loader.
            config: Runner configuration (uses defaults if not provided).

        """
        self.docker = docker_executor
        self.tier_loader = tier_loader
        self.config = config or RunnerConfig()
        self._state: ExecutionState | None = None
        self._adapter_func: Callable[..., Any] | None = None
        self._judge_func: Callable[..., JudgmentResult] | None = None

    def set_adapter(self, adapter_func: Callable[..., Any]) -> None:
        """Set the adapter function for running agents.

        Args:
            adapter_func: Function to run the agent adapter.

        """
        self._adapter_func = adapter_func

    def set_judge(self, judge_func: Callable[..., JudgmentResult]) -> None:
        """Set the judge function for evaluating runs.

        Args:
            judge_func: Function to evaluate run results.

        """
        self._judge_func = judge_func

    def run_test(
        self,
        test_id: str,
        tiers: list[str] | None = None,
        models: list[str] | None = None,
        runs_per_tier: int | None = None,
        parallel: bool | None = None,
        resume_from: Path | None = None,
    ) -> EvalSummary:
        """Run a complete test across all specified tiers and models.

        Args:
            test_id: Unique test identifier.
            tiers: List of tier IDs to test (default: all tiers).
            models: List of model IDs to test.
            runs_per_tier: Number of runs per tier (overrides config).
            parallel: Enable parallel execution (overrides config).
            resume_from: Path to state file for resume.

        Returns:
            EvalSummary with complete results.

        Raises:
            RunnerError: If test execution fails critically.
            InsufficientRunsError: If minimum runs cannot be achieved.

        """
        # Validate and initialize configuration
        config = self._initialize_test_config(
            test_id, tiers, models, runs_per_tier, parallel, resume_from
        )

        # Create or resume summary
        summary = self._create_test_summary(test_id, resume_from)

        # Execute across all tiers and models
        self._execute_test_matrix(summary, config)

        # Finalize and return
        return self._finalize_test_summary(summary)

    def _initialize_test_config(
        self,
        test_id: str,
        tiers: list[str] | None,
        models: list[str] | None,
        runs_per_tier: int | None,
        parallel: bool | None,
        resume_from: Path | None,
    ) -> dict[str, Any]:
        """Initialize and validate test configuration.

        Args:
            test_id: Test identifier.
            tiers: List of tier IDs to test (default: all tiers).
            models: List of model IDs to test.
            runs_per_tier: Number of runs per tier (overrides config).
            parallel: Enable parallel execution (overrides config).
            resume_from: Path to state file for resume.

        Returns:
            Dict with validated config: tiers, models, runs, is_parallel.

        Raises:
            RunnerError: If models are not specified.

        """
        # Apply overrides
        runs = runs_per_tier or self.config.runs_per_tier
        is_parallel = parallel if parallel is not None else self.config.parallel

        # Get tiers to test
        if tiers is None:
            tiers = self.tier_loader.get_tier_ids()

        # Models must be provided
        if not models:
            raise RunnerError("At least one model must be specified")

        return {
            "tiers": tiers,
            "models": models,
            "runs": runs,
            "is_parallel": is_parallel,
        }

    def _create_test_summary(self, test_id: str, resume_from: Path | None) -> EvalSummary:
        """Create or resume test summary with state management.

        Args:
            test_id: Test identifier.
            resume_from: Path to state file for resume.

        Returns:
            EvalSummary initialized with test_id and start time.

        """
        # Initialize or load state
        if resume_from and resume_from.exists():
            self._state = load_state(resume_from)
            if self._state and self._state.test_id != test_id:
                self._state = None  # Different test, start fresh

        if self._state is None:
            self._state = ExecutionState(
                test_id=test_id,
                started_at=datetime.now(timezone.utc).isoformat(),
            )

        # Initialize summary
        return EvalSummary(
            test_id=test_id,
            started_at=self._state.started_at,
        )

    def _execute_test_matrix(
        self,
        summary: EvalSummary,
        config: dict[str, Any],
    ) -> None:
        """Execute test matrix across all tiers and models.

        Args:
            summary: EvalSummary to populate with results.
            config: Test configuration dict.

        """
        for tier_id in config["tiers"]:
            tier_config = self.tier_loader.get_tier(tier_id)
            summary.tiers[tier_id] = {}

            for model in config["models"]:
                tier_summary = self._run_tier(
                    test_id=summary.test_id,
                    tier_config=tier_config,
                    model=model,
                    runs=config["runs"],
                    parallel=config["is_parallel"],
                )
                summary.tiers[tier_id][model] = tier_summary

    def _finalize_test_summary(self, summary: EvalSummary) -> EvalSummary:
        """Finalize summary with end timestamp and save state.

        Args:
            summary: EvalSummary to finalize.

        Returns:
            Completed summary.

        """
        summary.ended_at = datetime.now(timezone.utc).isoformat()
        summary.status = "completed"

        # Save final state if configured
        if self.config.state_file:
            save_state(self._state, self.config.state_file)

        return summary

    def _run_tier(
        self,
        test_id: str,
        tier_config: TierConfig,
        model: str,
        runs: int,
        parallel: bool,
    ) -> TierSummary:
        """Run all runs for a single tier and model.

        Args:
            test_id: Test identifier.
            tier_config: Tier configuration.
            model: Model identifier.
            runs: Number of runs.
            parallel: Enable parallel execution.

        Returns:
            TierSummary with results.

        """
        results: list[ExecutorRunResult] = []

        if parallel:
            results = self._run_parallel(test_id, tier_config, model, runs)
        else:
            results = self._run_sequential(test_id, tier_config, model, runs)

        # Aggregate results
        return self._aggregate_tier_results(tier_config.tier_id, model, results)

    def _run_sequential(
        self,
        test_id: str,
        tier_config: TierConfig,
        model: str,
        runs: int,
    ) -> list[ExecutorRunResult]:
        """Run tests sequentially."""
        results: list[ExecutorRunResult] = []

        for run_number in range(1, runs + 1):
            # Check if already completed (resume support)
            if self._state and self._state.is_run_completed(tier_config.tier_id, model, run_number):
                # Skip but don't add to results - we don't have the result
                continue

            result = self._execute_single_run(
                test_id=test_id,
                tier_config=tier_config,
                model=model,
                run_number=run_number,
            )
            results.append(result)

            # Mark completed and save state
            if self._state:
                self._state.mark_run_completed(tier_config.tier_id, model, run_number)
                if self.config.state_file:
                    save_state(self._state, self.config.state_file)

        return results

    def _run_parallel(
        self,
        test_id: str,
        tier_config: TierConfig,
        model: str,
        runs: int,
    ) -> list[ExecutorRunResult]:
        """Run tests in parallel using thread pool."""
        results: list[ExecutorRunResult] = []

        # Determine which runs need to be executed
        runs_to_execute = []
        for run_number in range(1, runs + 1):
            if self._state and self._state.is_run_completed(tier_config.tier_id, model, run_number):
                continue
            runs_to_execute.append(run_number)

        if not runs_to_execute:
            return results

        with ThreadPoolExecutor(max_workers=self.config.max_parallel_workers) as executor:
            future_to_run = {
                executor.submit(
                    self._execute_single_run,
                    test_id=test_id,
                    tier_config=tier_config,
                    model=model,
                    run_number=run_number,
                ): run_number
                for run_number in runs_to_execute
            }

            for future in as_completed(future_to_run):
                run_number = future_to_run[future]
                try:
                    result = future.result()
                    results.append(result)

                    # Mark completed
                    if self._state:
                        self._state.mark_run_completed(tier_config.tier_id, model, run_number)
                        if self.config.state_file:
                            save_state(self._state, self.config.state_file)

                except Exception as e:
                    results.append(
                        ExecutorRunResult(
                            run_number=run_number,
                            status=RunStatus.ERROR,
                            error_message=str(e),
                        )
                    )

        return results

    def _execute_single_run(
        self,
        test_id: str,
        tier_config: TierConfig,
        model: str,
        run_number: int,
    ) -> ExecutorRunResult:
        """Execute a single run with retries for rate limits.

        Args:
            test_id: Test identifier.
            tier_config: Tier configuration.
            model: Model identifier.
            run_number: Run number (1-N).

        Returns:
            ExecutorRunResult with execution outcome.

        """
        container_name = f"scylla-{test_id}-{tier_config.tier_id}-{model}-r{run_number:02d}"

        for attempt in range(self.config.max_retries):
            try:
                execution_info = self._execute_in_container_with_timing(
                    container_name, tier_config, model
                )
                return self._evaluate_execution_result(execution_info, run_number)

            except RateLimitError:
                self._apply_backoff(attempt)
                continue

            except Exception as e:
                return self._create_error_result(run_number, str(e))

        return self._create_rate_limit_exceeded_result(run_number)

    def _execute_in_container_with_timing(
        self,
        container_name: str,
        tier_config: TierConfig,
        model: str,
    ) -> ExecutionInfo:
        """Execute container and add timing information.

        Args:
            container_name: Name for the container.
            tier_config: Tier configuration with prompts.
            model: Model identifier.

        Returns:
            ExecutionInfo with timestamps and duration.

        """
        start_time = datetime.now(timezone.utc)
        execution_info = self._run_in_container(
            container_name=container_name,
            tier_config=tier_config,
            model=model,
        )
        end_time = datetime.now(timezone.utc)

        execution_info.started_at = start_time.isoformat()
        execution_info.ended_at = end_time.isoformat()
        execution_info.duration_seconds = (end_time - start_time).total_seconds()

        return execution_info

    def _evaluate_execution_result(
        self,
        execution_info: ExecutionInfo,
        run_number: int,
    ) -> ExecutorRunResult:
        """Evaluate execution result and run judge if successful.

        Args:
            execution_info: Execution results to evaluate.
            run_number: Run number (1-N).

        Returns:
            ExecutorRunResult with status based on execution and judgment.

        """
        # Check for timeout
        if execution_info.timed_out:
            return ExecutorRunResult(
                run_number=run_number,
                status=RunStatus.TIMEOUT,
                execution_info=execution_info,
            )

        # Check for execution error
        if execution_info.exit_code != 0:
            return ExecutorRunResult(
                run_number=run_number,
                status=RunStatus.ERROR,
                execution_info=execution_info,
                error_message=f"Exit code: {execution_info.exit_code}",
            )

        # Run judge evaluation
        judgment = self._run_judge(execution_info)

        return ExecutorRunResult(
            run_number=run_number,
            status=RunStatus.PASSED if judgment.passed else RunStatus.FAILED,
            execution_info=execution_info,
            judgment=judgment,
        )

    def _apply_backoff(self, attempt: int) -> None:
        """Apply exponential backoff for rate limit retry.

        Args:
            attempt: Current attempt number (0-indexed).

        """
        delay = min(
            self.config.initial_backoff * (2**attempt),
            self.config.max_backoff,
        )
        time.sleep(delay)

    def _create_error_result(self, run_number: int, error_message: str) -> ExecutorRunResult:
        """Create error result from exception.

        Args:
            run_number: Run number (1-N).
            error_message: Error message.

        Returns:
            ExecutorRunResult with ERROR status.

        """
        return ExecutorRunResult(
            run_number=run_number,
            status=RunStatus.ERROR,
            error_message=error_message,
        )

    def _create_rate_limit_exceeded_result(self, run_number: int) -> ExecutorRunResult:
        """Create error result for rate limit retry exhaustion.

        Args:
            run_number: Run number (1-N).

        Returns:
            ExecutorRunResult with ERROR status.

        """
        return ExecutorRunResult(
            run_number=run_number,
            status=RunStatus.ERROR,
            error_message="Rate limit retries exceeded",
        )

    def _run_in_container(
        self,
        container_name: str,
        tier_config: TierConfig,
        model: str,
    ) -> ExecutionInfo:
        """Run agent adapter in a Docker container.

        Args:
            container_name: Name for the container.
            tier_config: Tier configuration with prompts.
            model: Model identifier.

        Returns:
            ExecutionInfo with container results.

        """
        from scylla.executor.docker import ContainerConfig

        # Build container config
        env_vars = {
            "TIER": tier_config.tier_id,
            "MODEL": model,
            "TIER_NAME": tier_config.name,
        }

        # Add API keys from host environment
        env_vars.update(self.docker.get_api_keys_from_env())

        # Add tier-specific settings
        if tier_config.tools_enabled is not None:
            env_vars["TOOLS_ENABLED"] = str(tier_config.tools_enabled).lower()
        if tier_config.delegation_enabled is not None:
            env_vars["DELEGATION_ENABLED"] = str(tier_config.delegation_enabled).lower()
        if tier_config.prompt_content:
            env_vars["TIER_PROMPT"] = tier_config.prompt_content

        config = ContainerConfig(
            image=self.config.container_image,
            name=container_name,
            env_vars=env_vars,
            timeout_seconds=self.config.timeout_seconds,
        )

        result: ContainerResult = self.docker.run(config)

        return ExecutionInfo(
            container_id=result.container_id,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
        )

    def _run_judge(self, execution_info: ExecutionInfo) -> JudgmentResult:
        """Run judge evaluation on execution results.

        Args:
            execution_info: Execution results to evaluate.

        Returns:
            JudgmentResult from evaluation.

        """
        if self._judge_func:
            return self._judge_func(execution_info)

        # Default: pass if exit code is 0
        return JudgmentResult(
            passed=execution_info.exit_code == 0,
            score=1.0 if execution_info.exit_code == 0 else 0.0,
            reasoning="Default judgment based on exit code",
            consensus_runs=1,
        )

    def _aggregate_tier_results(
        self,
        tier_id: str,
        model: str,
        results: list[ExecutorRunResult],
    ) -> TierSummary:
        """Aggregate results for a tier.

        Args:
            tier_id: Tier identifier.
            model: Model identifier.
            results: List of run results.

        Returns:
            TierSummary with aggregated statistics.

        """
        passed = sum(1 for r in results if r.status == RunStatus.PASSED)
        failed = sum(1 for r in results if r.status == RunStatus.FAILED)
        errors = sum(1 for r in results if r.status == RunStatus.ERROR)
        timeouts = sum(1 for r in results if r.status == RunStatus.TIMEOUT)
        total = len(results)

        # Calculate pass rate
        completed = passed + failed
        pass_rate = passed / completed if completed > 0 else 0.0

        # Calculate Wilson CI
        ci_low, ci_high = calculate_wilson_ci(passed, completed)

        return TierSummary(
            tier_id=tier_id,
            model=model,
            total_runs=total,
            passed_runs=passed,
            failed_runs=failed,
            error_runs=errors,
            timeout_runs=timeouts,
            pass_rate=pass_rate,
            pass_rate_ci_low=ci_low,
            pass_rate_ci_high=ci_high,
            runs=results,
        )
