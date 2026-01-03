"""Result writer for per-run evaluation results.

Python justification: JSON serialization and file I/O for result persistence.
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class ExecutionInfo:
    """Execution metadata for a run.

    This is the minimal execution info for result persistence.
    For other ExecutionInfo types, see:
    - executor/runner.py:ExecutionInfo (detailed with container info)
    - core/results.py:BaseExecutionInfo (base type)
    """

    status: str
    duration_seconds: float
    exit_code: int


@dataclass
class MetricsInfo:
    """Token and cost metrics for a run."""

    tokens_input: int
    tokens_output: int
    cost_usd: float
    api_calls: int


@dataclass
class JudgmentInfo:
    """Judge evaluation results for a run."""

    passed: bool
    impl_rate: float
    letter_grade: str


@dataclass
class GradingInfo:
    """Calculated grading metrics for a run."""

    pass_rate: float
    cost_of_pass: float
    composite_score: float


@dataclass
class RunResult:
    """Complete result for a single evaluation run.

    Contains all execution, metrics, judgment, and grading data
    using composition with nested info objects.

    This is the persistence result with nested info objects.
    For other RunResult types, see:
    - executor/runner.py:RunResult (execution tracking with status)
    - e2e/models.py:RunResult (E2E testing with paths)
    - metrics/aggregator.py:RunResult (statistical aggregation)
    - core/results.py:BaseRunResult (base type)
    """

    test_id: str
    tier_id: str
    model_id: str
    run_number: int
    timestamp: str
    execution: ExecutionInfo
    metrics: MetricsInfo
    judgment: JudgmentInfo
    grading: GradingInfo

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "test_id": self.test_id,
            "tier_id": self.tier_id,
            "model_id": self.model_id,
            "run_number": self.run_number,
            "timestamp": self.timestamp,
            "execution": asdict(self.execution),
            "metrics": asdict(self.metrics),
            "judgment": asdict(self.judgment),
            "grading": asdict(self.grading),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

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

    def get_run_dir(
        self, test_id: str, tier_id: str, run_number: int
    ) -> Path:
        """Get the directory path for a specific run.

        Args:
            test_id: Test identifier
            tier_id: Tier identifier (T0, T1, etc.)
            run_number: Run number (1-10)

        Returns:
            Path to run directory
        """
        return self.base_dir / test_id / tier_id / f"run_{run_number:02d}"

    def write_result(self, result: RunResult) -> Path:
        """Write a run result to the appropriate directory.

        Args:
            result: Run result to write

        Returns:
            Path to written result.json
        """
        run_dir = self.get_run_dir(
            result.test_id, result.tier_id, result.run_number
        )
        return result.write(run_dir)

    def read_result(
        self, test_id: str, tier_id: str, run_number: int
    ) -> RunResult | None:
        """Read a run result from the file system.

        Args:
            test_id: Test identifier
            tier_id: Tier identifier
            run_number: Run number

        Returns:
            RunResult if found, None otherwise
        """
        run_dir = self.get_run_dir(test_id, tier_id, run_number)
        result_path = run_dir / "result.json"

        if not result_path.exists():
            return None

        data = json.loads(result_path.read_text())
        return RunResult(
            test_id=data["test_id"],
            tier_id=data["tier_id"],
            model_id=data["model_id"],
            run_number=data["run_number"],
            timestamp=data["timestamp"],
            execution=ExecutionInfo(**data["execution"]),
            metrics=MetricsInfo(**data["metrics"]),
            judgment=JudgmentInfo(**data["judgment"]),
            grading=GradingInfo(**data["grading"]),
        )


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
) -> RunResult:
    """Factory function to create a RunResult with all components.

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
        Fully constructed RunResult
    """
    if timestamp is None:
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    return RunResult(
        test_id=test_id,
        tier_id=tier_id,
        model_id=model_id,
        run_number=run_number,
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
