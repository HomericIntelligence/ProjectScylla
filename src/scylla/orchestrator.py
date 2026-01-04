"""Test orchestrator for agent evaluations.

Python justification: Required for subprocess orchestration and file I/O.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scylla.cli.progress import ProgressDisplay, RunStatus
from scylla.config import ConfigLoader, EvalCase, Rubric
from scylla.executor import WorkspaceManager
from scylla.reporting import ResultWriter, RunResult, create_run_result


@dataclass
class OrchestratorConfig:
    """Configuration for the test orchestrator."""

    base_path: Path = Path(".")
    runs_per_tier: int = 10
    tiers: list[str] | None = None
    model: str | None = None
    quiet: bool = False
    verbose: bool = False


class EvalOrchestrator:
    """Orchestrates test execution with all components.

    Wires together:
    - ConfigLoader: Loads test configurations
    - WorkspaceManager: Creates and manages workspaces
    - Adapters: Runs agents
    - Judge: Evaluates results
    - ResultWriter: Writes results

    Example:
        orchestrator = EvalOrchestrator()
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
        _skip_progress_init: bool = False,
    ) -> RunResult:
        """Run a single test execution.

        Args:
            test_id: Test identifier.
            model_id: Model identifier.
            tier_id: Tier identifier.
            run_number: Run number (1-indexed).
            _skip_progress_init: Internal flag to skip progress initialization.

        Returns:
            RunResult with execution details.

        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")

        # Load test configuration
        test_case = self.loader.load_test(test_id)
        rubric = self.loader.load_rubric(test_id)

        # Start progress tracking (unless called from run_test)
        if not _skip_progress_init:
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

            # Extract values for result creation
            passed = judgment.get("passed", False)
            impl_rate = judgment.get("score", 0.0)
            cost_usd = execution_result.get("cost_usd", 0.0)
            pass_rate = 1.0 if passed else 0.0
            cost_of_pass = cost_usd / pass_rate if pass_rate > 0 else float("inf")
            # Composite score: equal weight (50/50) per metrics-formulas.md
            composite_score = (pass_rate + impl_rate) / 2

            # Create result
            result = create_run_result(
                test_id=test_id,
                tier_id=tier_id,
                model_id=model_id,
                run_number=run_number,
                status="completed",
                duration_seconds=duration,
                exit_code=execution_result.get("exit_code", 0),
                tokens_input=execution_result.get("tokens_in", 0),
                tokens_output=execution_result.get("tokens_out", 0),
                cost_usd=cost_usd,
                api_calls=execution_result.get("api_calls", 1),
                passed=passed,
                impl_rate=impl_rate,
                letter_grade=judgment.get("grade", "F"),
                pass_rate=pass_rate,
                cost_of_pass=cost_of_pass,
                composite_score=composite_score,
            )

            # Write result
            result_path = self.result_writer.write_result(result)

            # Write logs to result directory for independent validation
            result_dir = result_path.parent
            self._write_run_logs(
                result_dir=result_dir,
                execution_result=execution_result,
                judgment=judgment,
                test_case=test_case,
                tier_id=tier_id,
            )

            # Complete progress
            self.progress.complete_run(
                tier_id=tier_id,
                run_number=run_number,
                passed=result.judgment.passed,
                grade=result.judgment.letter_grade,
                cost_usd=result.metrics.cost_usd,
            )
            if not _skip_progress_init:
                self.progress.complete_tier(tier_id)
                self.progress.complete_test()

            return result

        finally:
            # Cleanup workspace (keep logs)
            WorkspaceManager.cleanup(workspace, keep_logs=True)

    def _run_adapter(
        self,
        workspace: Path,
        test_case: EvalCase,
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
        test_case: EvalCase,
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

    def _write_run_logs(
        self,
        result_dir: Path,
        execution_result: dict,
        judgment: dict,
        test_case: EvalCase,
        tier_id: str,
    ) -> None:
        """Write comprehensive logs for independent validation.

        Creates a logs/ subdirectory with:
        - prompt.md: The task prompt (from test case)
        - tier_prompt.md: The tier-specific prompt (if any)
        - stdout.log: Raw stdout from agent execution
        - stderr.log: Raw stderr from agent execution
        - response.json: Parsed JSON response (if available)
        - judgment.json: Judge evaluation details

        Args:
            result_dir: Directory containing result.json
            execution_result: Results dict from adapter
            judgment: Judgment dict from judge
            test_case: Test case configuration
            tier_id: Tier identifier

        """
        import json

        logs_dir = result_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Write final prompt (the actual prompt sent to the agent)
        final_prompt = execution_result.get("final_prompt", "")
        if final_prompt:
            (logs_dir / "final_prompt.md").write_text(final_prompt)

        # Write task prompt (original, without tier injection)
        prompt_path = self.config.base_path / "tests" / test_case.id / "prompt.md"
        if prompt_path.exists():
            (logs_dir / "task_prompt.md").write_text(prompt_path.read_text())

        # Write tier prompt (if applicable)
        if tier_id != "T0":
            # Try to find tier prompt file
            tier_files = list(
                (self.config.base_path.parent / "config" / "tiers").glob(f"t{tier_id[1]}-*.md")
            )
            if tier_files:
                (logs_dir / "tier_prompt.md").write_text(tier_files[0].read_text())

        # Write stdout
        stdout = execution_result.get("stdout", "")
        (logs_dir / "stdout.log").write_text(stdout)

        # Write stderr
        stderr = execution_result.get("stderr", "")
        (logs_dir / "stderr.log").write_text(stderr)

        # Try to parse and write JSON response (if stdout is JSON)
        try:
            response_data = json.loads(stdout.strip())
            (logs_dir / "response.json").write_text(json.dumps(response_data, indent=2))
        except (json.JSONDecodeError, AttributeError):
            pass  # stdout wasn't JSON, that's fine

        # Write judgment details
        judgment_data = {
            "passed": judgment.get("passed", False),
            "score": judgment.get("score", 0.0),
            "grade": judgment.get("grade", "F"),
            "reasoning": judgment.get("reasoning", ""),
        }
        (logs_dir / "judgment.json").write_text(json.dumps(judgment_data, indent=2))

        # Write execution metadata
        exec_metadata = {
            "exit_code": execution_result.get("exit_code", -1),
            "tokens_in": execution_result.get("tokens_in", 0),
            "tokens_out": execution_result.get("tokens_out", 0),
            "cost_usd": execution_result.get("cost_usd", 0.0),
            "api_calls": execution_result.get("api_calls", 0),
        }
        (logs_dir / "execution.json").write_text(json.dumps(exec_metadata, indent=2))

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
        test_data = self.loader._load_yaml(self.config.base_path / "tests" / test_id / "test.yaml")

        if tiers is None:
            tiers = test_data.get("tiers", ["T0"])

        runs = runs_per_tier or self.config.runs_per_tier

        results: list[RunResult] = []

        # Initialize progress for full test run
        self.progress.start_test(test_id, tiers, runs_per_tier=runs)

        for model_id in models:
            for tier_id in tiers:
                self.progress.start_tier(tier_id)
                for run_number in range(1, runs + 1):
                    result = self.run_single(
                        test_id=test_id,
                        model_id=model_id,
                        tier_id=tier_id,
                        run_number=run_number,
                        _skip_progress_init=True,
                    )
                    results.append(result)
                self.progress.complete_tier(tier_id)

        self.progress.complete_test()

        return results
