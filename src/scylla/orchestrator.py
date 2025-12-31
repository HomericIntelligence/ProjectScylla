"""Test orchestrator for agent evaluations.

Python justification: Required for subprocess orchestration and file I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from scylla.cli.progress import ProgressDisplay, RunStatus
from scylla.config import ConfigLoader, Rubric, TestCase
from scylla.executor import WorkspaceManager
from scylla.reporting import RunResult, ResultWriter, create_run_result


@dataclass
class OrchestratorConfig:
    """Configuration for the test orchestrator."""

    base_path: Path = Path(".")
    runs_per_tier: int = 10
    tiers: list[str] | None = None
    model: str | None = None
    quiet: bool = False
    verbose: bool = False


class TestOrchestrator:
    """Orchestrates test execution with all components.

    Wires together:
    - ConfigLoader: Loads test configurations
    - WorkspaceManager: Creates and manages workspaces
    - Adapters: Runs agents
    - Judge: Evaluates results
    - ResultWriter: Writes results

    Example:
        orchestrator = TestOrchestrator()
        result = orchestrator.run_single(
            test_id="001-justfile-to-makefile",
            model_id="claude-opus-4-5-20251101",
        )
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            config: Orchestrator configuration.
        """
        self.config = config or OrchestratorConfig()
        self.loader = ConfigLoader(self.config.base_path)
        self.progress = ProgressDisplay(
            quiet=self.config.quiet,
            verbose=self.config.verbose,
        )
        self.result_writer = ResultWriter(self.config.base_path / "runs")
        self._adapter_func: Callable | None = None
        self._judge_func: Callable | None = None

    def set_adapter(self, adapter_func: Callable) -> None:
        """Set the adapter function for running agents."""
        self._adapter_func = adapter_func

    def set_judge(self, judge_func: Callable) -> None:
        """Set the judge function for evaluation."""
        self._judge_func = judge_func

    def run_single(
        self,
        test_id: str,
        model_id: str,
        tier_id: str = "T0",
        run_number: int = 1,
    ) -> RunResult:
        """Run a single test execution.

        Args:
            test_id: Test identifier.
            model_id: Model identifier.
            tier_id: Tier identifier.
            run_number: Run number (1-indexed).

        Returns:
            RunResult with execution details.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")

        # Load test configuration
        test_case = self.loader.load_test(test_id)
        rubric = self.loader.load_rubric(test_id)

        # Start progress tracking
        self.progress.start_test(test_id, [tier_id], runs_per_tier=1)
        self.progress.start_tier(tier_id)
        self.progress.start_run(tier_id, run_number)

        # Create workspace
        workspace = WorkspaceManager.create(
            test_id=test_id,
            model_id=model_id,
            run_number=run_number,
            timestamp=timestamp,
            base_path=self.config.base_path / "runs",
        )

        try:
            # Clone repository
            WorkspaceManager.clone(
                repo_url=test_case.source.repo,
                workspace=workspace,
            )

            # Checkout specific hash
            WorkspaceManager.checkout(
                workspace=workspace,
                hash=test_case.source.hash,
            )

            # Execute adapter (if configured)
            start_time = datetime.now(UTC)
            execution_result = self._run_adapter(
                workspace=workspace,
                test_case=test_case,
                model_id=model_id,
                tier_id=tier_id,
            )
            end_time = datetime.now(UTC)
            duration = (end_time - start_time).total_seconds()

            # Update progress to judging
            self.progress.update_run_status(tier_id, run_number, RunStatus.JUDGING)

            # Run judge evaluation
            judgment = self._run_judge(
                workspace=workspace,
                test_case=test_case,
                rubric=rubric,
                execution_result=execution_result,
            )

            # Create result
            result = create_run_result(
                test_id=test_id,
                tier_id=tier_id,
                model_id=model_id,
                run_number=run_number,
                duration_seconds=duration,
                tokens_in=execution_result.get("tokens_in", 0),
                tokens_out=execution_result.get("tokens_out", 0),
                cost_usd=execution_result.get("cost_usd", 0.0),
                passed=judgment.get("passed", False),
                score=judgment.get("score", 0.0),
                grade=judgment.get("grade", "F"),
                reasoning=judgment.get("reasoning", ""),
            )

            # Write result
            result_path = self.result_writer.write_result(result)

            # Complete progress
            self.progress.complete_run(
                tier_id=tier_id,
                run_number=run_number,
                passed=result.judgment.passed,
                grade=result.grading.grade,
                cost_usd=result.metrics.cost_usd,
            )
            self.progress.complete_tier(tier_id)
            self.progress.complete_test()

            return result

        finally:
            # Cleanup workspace (keep logs)
            WorkspaceManager.cleanup(workspace, keep_logs=True)

    def _run_adapter(
        self,
        workspace: Path,
        test_case: TestCase,
        model_id: str,
        tier_id: str,
    ) -> dict:
        """Run the adapter to execute the agent.

        Args:
            workspace: Path to workspace.
            test_case: Test configuration.
            model_id: Model identifier.
            tier_id: Tier identifier.

        Returns:
            Dict with execution results.
        """
        if self._adapter_func:
            return self._adapter_func(
                workspace=workspace,
                test_case=test_case,
                model_id=model_id,
                tier_id=tier_id,
            )

        # Default: return mock execution
        return {
            "tokens_in": 1000,
            "tokens_out": 500,
            "cost_usd": 0.05,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        }

    def _run_judge(
        self,
        workspace: Path,
        test_case: TestCase,
        rubric: Rubric,
        execution_result: dict,
    ) -> dict:
        """Run the judge to evaluate results.

        Args:
            workspace: Path to workspace.
            test_case: Test configuration.
            rubric: Evaluation rubric.
            execution_result: Results from adapter.

        Returns:
            Dict with judgment.
        """
        if self._judge_func:
            return self._judge_func(
                workspace=workspace,
                test_case=test_case,
                rubric=rubric,
                execution_result=execution_result,
            )

        # Default: return mock judgment
        return {
            "passed": True,
            "score": 0.85,
            "grade": "B",
            "reasoning": "Default judgment for testing",
        }

    def run_test(
        self,
        test_id: str,
        models: list[str],
        tiers: list[str] | None = None,
        runs_per_tier: int | None = None,
    ) -> list[RunResult]:
        """Run a complete test across all tiers and models.

        Args:
            test_id: Test identifier.
            models: List of model identifiers.
            tiers: List of tier identifiers (default: from test config).
            runs_per_tier: Number of runs per tier (default: from config).

        Returns:
            List of RunResult objects.
        """
        # Load test to get default tiers
        test_case = self.loader.load_test(test_id)
        test_data = self.loader._load_yaml(
            self.config.base_path / "tests" / test_id / "test.yaml"
        )

        if tiers is None:
            tiers = test_data.get("tiers", ["T0"])

        runs = runs_per_tier or self.config.runs_per_tier

        results: list[RunResult] = []

        for model_id in models:
            for tier_id in tiers:
                for run_number in range(1, runs + 1):
                    result = self.run_single(
                        test_id=test_id,
                        model_id=model_id,
                        tier_id=tier_id,
                        run_number=run_number,
                    )
                    results.append(result)

        return results
