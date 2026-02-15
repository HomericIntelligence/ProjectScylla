"""Result writer for per-run evaluation results."""

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from scylla.core.results import ExecutionInfoBase, RunResultBase


class ReportingExecutionInfo(ExecutionInfoBase):
    """Execution metadata for result persistence.

    This is the minimal execution info for result persistence. Inherits common
    fields (exit_code, duration_seconds, timed_out) from ExecutionInfoBase.

    For other ExecutionInfo types in the hierarchy, see:
    - ExecutionInfoBase (core/results.py) - Base Pydantic model
    - ExecutorExecutionInfo (executor/runner.py) - Detailed with container info
    - BaseExecutionInfo (core/results.py) - Legacy dataclass (deprecated)

    Attributes:
        status: Execution status (e.g., "completed", "failed", "timeout").

    """

    status: str = Field(..., description="Execution status")


# Backward-compatible type alias
ExecutionInfo = ReportingExecutionInfo


class MetricsInfo(BaseModel):
    """Token and cost metrics for a run."""

    tokens_input: int = Field(..., description="Input tokens")
    tokens_output: int = Field(..., description="Output tokens")
    cost_usd: float = Field(..., description="Cost in USD")
    api_calls: int = Field(..., description="Number of API calls")


class JudgmentInfo(BaseModel):
    """Judge evaluation results for a run."""

    passed: bool = Field(..., description="Whether the run passed")
    impl_rate: float = Field(..., description="Implementation rate (0.0-1.0)")
    letter_grade: str = Field(..., description="Letter grade")


class GradingInfo(BaseModel):
    """Calculated grading metrics for a run."""

    pass_rate: float = Field(..., description="Pass rate (0.0 or 1.0)")
    cost_of_pass: float = Field(..., description="Cost per successful pass")
    composite_score: float = Field(..., description="Combined quality score")


class ReportingRunResult(RunResultBase):
    """Complete result for a single evaluation run.

    Contains all execution, metrics, judgment, and grading data
    using composition with nested info objects.

    This is the persistence result with nested info objects.
    Inherits common fields (run_number, cost_usd, duration_seconds) from RunResultBase.

    Note: cost_usd and duration_seconds are inherited from RunResultBase but also
    present in the nested metrics/execution objects for backward compatibility.

    For other RunResult types in the hierarchy, see:
    - RunResultBase (core/results.py) - Base Pydantic model
    - ExecutorRunResult (executor/runner.py) - Execution tracking with status
    - E2ERunResult (e2e/models.py) - E2E testing with paths
    - MetricsRunResult (metrics/aggregator.py) - Statistical aggregation
    """

    test_id: str = Field(..., description="Test identifier")
    tier_id: str = Field(..., description="Tier identifier")
    model_id: str = Field(..., description="Model identifier")
    timestamp: str = Field(..., description="ISO timestamp")
    execution: ExecutionInfo = Field(..., description="Execution metadata")
    metrics: MetricsInfo = Field(..., description="Token and cost metrics")
    judgment: JudgmentInfo = Field(..., description="Judge evaluation results")
    grading: GradingInfo = Field(..., description="Calculated grading metrics")

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return self.model_dump_json(indent=indent)

    def write(self, output_dir: Path) -> Path:
        """Write result.json to output directory.

        Args:
            output_dir: Directory to write result.json

        Returns:
            Path to written file

        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "result.json"
        output_path.write_text(self.to_json())
        return output_path


class ResultWriter:
    """Writes run results to the file system."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize result writer.

        Args:
            base_dir: Base directory for results (e.g., 'runs/')

        """
        self.base_dir = base_dir

    def get_run_dir(self, test_id: str, tier_id: str, run_number: int) -> Path:
        """Get the directory path for a specific run.

        Args:
            test_id: Test identifier
            tier_id: Tier identifier (T0, T1, etc.)
            run_number: Run number (1-10)

        Returns:
            Path to run directory

        """
        return self.base_dir / test_id / tier_id / f"run_{run_number:02d}"

    def write_result(self, result: ReportingRunResult) -> Path:
        """Write a run result to the appropriate directory.

        Args:
            result: Run result to write

        Returns:
            Path to written result.json

        """
        run_dir = self.get_run_dir(result.test_id, result.tier_id, result.run_number)
        return result.write(run_dir)

    def read_result(self, test_id: str, tier_id: str, run_number: int) -> ReportingRunResult | None:
        """Read a run result from the file system.

        Args:
            test_id: Test identifier
            tier_id: Tier identifier
            run_number: Run number

        Returns:
            ReportingRunResult if found, None otherwise

        """
        run_dir = self.get_run_dir(test_id, tier_id, run_number)
        result_path = run_dir / "result.json"

        if not result_path.exists():
            return None

        data = json.loads(result_path.read_text())
        return ReportingRunResult.model_validate(data)


def create_run_result(
    test_id: str,
    tier_id: str,
    model_id: str,
    run_number: int,
    status: str,
    duration_seconds: float,
    exit_code: int,
    tokens_input: int,
    tokens_output: int,
    cost_usd: float,
    api_calls: int,
    passed: bool,
    impl_rate: float,
    letter_grade: str,
    pass_rate: float,
    cost_of_pass: float,
    composite_score: float,
    timestamp: str | None = None,
) -> ReportingRunResult:
    """Create a RunResult with all components.

    Args:
        test_id: Test identifier
        tier_id: Tier identifier (T0, T1, etc.)
        model_id: Model identifier
        run_number: Run number (1-10)
        status: Execution status (completed, failed, timeout)
        duration_seconds: Run duration
        exit_code: Process exit code
        tokens_input: Input tokens used
        tokens_output: Output tokens generated
        cost_usd: Total cost in USD
        api_calls: Number of API calls
        passed: Whether the run passed
        impl_rate: Implementation rate (0.0-1.0)
        letter_grade: Letter grade (A, B, C, D, F)
        pass_rate: Pass rate (0.0 or 1.0)
        cost_of_pass: Cost per successful pass
        composite_score: Combined quality score

    Returns:
        Fully constructed ReportingRunResult

    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return ReportingRunResult(
        test_id=test_id,
        tier_id=tier_id,
        model_id=model_id,
        run_number=run_number,
        cost_usd=cost_usd,  # Inherited from RunResultBase
        duration_seconds=duration_seconds,  # Inherited from RunResultBase
        timestamp=timestamp,
        execution=ExecutionInfo(
            status=status,
            duration_seconds=duration_seconds,
            exit_code=exit_code,
        ),
        metrics=MetricsInfo(
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            api_calls=api_calls,
        ),
        judgment=JudgmentInfo(
            passed=passed,
            impl_rate=impl_rate,
            letter_grade=letter_grade,
        ),
        grading=GradingInfo(
            pass_rate=pass_rate,
            cost_of_pass=cost_of_pass,
            composite_score=composite_score,
        ),
    )
