"""Summary generator for test-level result aggregation."""

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class SummaryStatistics(BaseModel):
    """Statistical summary of a metric across multiple runs."""

    median: float = Field(..., description="Median value")
    mean: float = Field(..., description="Mean value")
    mode: float = Field(..., description="Mode value")
    min: float = Field(..., description="Minimum value")
    max: float = Field(..., description="Maximum value")
    std_dev: float = Field(..., description="Standard deviation")


class ModelStatistics(BaseModel):
    """Statistics for a single model on a test."""

    runs_completed: int = Field(..., description="Number of completed runs")
    pass_rate: SummaryStatistics = Field(..., description="Pass rate statistics")
    impl_rate: SummaryStatistics = Field(..., description="Implementation rate statistics")
    cost_usd: SummaryStatistics = Field(..., description="Cost statistics")
    duration_seconds: SummaryStatistics = Field(..., description="Duration statistics")
    composite_score: SummaryStatistics = Field(..., description="Composite score statistics")
    cost_of_pass: SummaryStatistics = Field(..., description="Cost of pass statistics")
    grade: str = Field(..., description="Letter grade")


class Rankings(BaseModel):
    """Model rankings by different criteria."""

    by_quality: list[str] = Field(default_factory=list, description="Rankings by quality")
    by_cost_efficiency: list[str] = Field(
        default_factory=list, description="Rankings by cost efficiency"
    )
    by_speed: list[str] = Field(default_factory=list, description="Rankings by speed")


class EvaluationReport(BaseModel):
    """Summary of all model results for a single test."""

    test_id: str = Field(..., description="Test identifier")
    test_name: str = Field(..., description="Human-readable test name")
    updated: str = Field(..., description="ISO timestamp of last update")
    runs_per_model: int = Field(..., description="Expected runs per model")
    models: dict[str, ModelStatistics] = Field(default_factory=dict, description="Model statistics")
    rankings: Rankings = Field(default_factory=Rankings, description="Model rankings")

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return self.model_dump_json(indent=indent)

    def write(self, output_dir: Path) -> Path:
        """Write summary.json to output directory.

        Args:
            output_dir: Directory to write summary.json

        Returns:
            Path to written file

        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "summary.json"
        output_path.write_text(self.to_json())
        return output_path


class SummaryGenerator:
    """Generates test summaries by aggregating model results."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize summary generator.

        Args:
            base_dir: Base directory for summaries (e.g., 'summaries/by-test/')

        """
        self.base_dir = base_dir

    def get_summary_dir(self, test_id: str) -> Path:
        """Get the directory path for a test summary.

        Args:
            test_id: Test identifier

        Returns:
            Path to summary directory

        """
        return self.base_dir / test_id

    def calculate_rankings(self, models: dict[str, ModelStatistics]) -> Rankings:
        """Calculate rankings across all models.

        Args:
            models: Dictionary of model_id -> ModelStatistics

        Returns:
            Rankings object with sorted model IDs

        """
        if not models:
            return Rankings()

        # By quality: sort by median composite_score descending
        by_quality = sorted(
            models.keys(),
            key=lambda m: models[m].composite_score.median,
            reverse=True,
        )

        # By cost efficiency: sort by median cost_of_pass ascending
        # Handle infinity by placing those last
        def cost_sort_key(m: str) -> tuple[int, float]:
            cop = models[m].cost_of_pass.median
            if cop == float("inf"):
                return (1, cop)  # Infinity goes last
            return (0, cop)

        by_cost_efficiency = sorted(models.keys(), key=cost_sort_key)

        # By speed: sort by median duration_seconds ascending
        by_speed = sorted(
            models.keys(),
            key=lambda m: models[m].duration_seconds.median,
        )

        return Rankings(
            by_quality=by_quality,
            by_cost_efficiency=by_cost_efficiency,
            by_speed=by_speed,
        )

    def generate_summary(
        self,
        test_id: str,
        test_name: str,
        models: dict[str, ModelStatistics],
        runs_per_model: int = 10,
        timestamp: str | None = None,
    ) -> EvaluationReport:
        """Generate a test summary from model statistics.

        Args:
            test_id: Test identifier
            test_name: Human-readable test name
            models: Dictionary of model_id -> ModelStatistics
            runs_per_model: Expected runs per model
            timestamp: Optional timestamp (auto-generated if not provided)

        Returns:
            EvaluationReport object

        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        rankings = self.calculate_rankings(models)

        return EvaluationReport(
            test_id=test_id,
            test_name=test_name,
            updated=timestamp,
            runs_per_model=runs_per_model,
            models=models,
            rankings=rankings,
        )

    def write_summary(self, summary: EvaluationReport) -> Path:
        """Write a test summary to the appropriate directory.

        Args:
            summary: EvaluationReport to write

        Returns:
            Path to written summary.json

        """
        summary_dir = self.get_summary_dir(summary.test_id)
        return summary.write(summary_dir)

    def read_summary(self, test_id: str) -> EvaluationReport | None:
        """Read a test summary from the file system.

        Args:
            test_id: Test identifier

        Returns:
            EvaluationReport if found, None otherwise

        """
        summary_dir = self.get_summary_dir(test_id)
        summary_path = summary_dir / "summary.json"

        if not summary_path.exists():
            return None

        data = json.loads(summary_path.read_text())
        return EvaluationReport.model_validate(data)


def create_statistics(
    median: float,
    mean: float,
    mode: float,
    min_val: float,
    max_val: float,
    std_dev: float,
) -> SummaryStatistics:
    """Create summary statistics from metric values.

    Args:
        median: Median value
        mean: Mean value
        mode: Mode value
        min_val: Minimum value
        max_val: Maximum value
        std_dev: Standard deviation

    Returns:
        SummaryStatistics object

    """
    return SummaryStatistics(
        median=median,
        mean=mean,
        mode=mode,
        min=min_val,
        max=max_val,
        std_dev=std_dev,
    )


def create_model_statistics(
    runs_completed: int,
    pass_rate: SummaryStatistics,
    impl_rate: SummaryStatistics,
    cost_usd: SummaryStatistics,
    duration_seconds: SummaryStatistics,
    composite_score: SummaryStatistics,
    cost_of_pass: SummaryStatistics,
    grade: str,
) -> ModelStatistics:
    """Create model statistics from run metrics.

    Args:
        runs_completed: Number of completed runs
        pass_rate: Pass rate statistics
        impl_rate: Implementation rate statistics
        cost_usd: Cost statistics
        duration_seconds: Duration statistics
        composite_score: Composite score statistics
        cost_of_pass: Cost of pass statistics
        grade: Letter grade

    Returns:
        ModelStatistics object

    """
    return ModelStatistics(
        runs_completed=runs_completed,
        pass_rate=pass_rate,
        impl_rate=impl_rate,
        cost_usd=cost_usd,
        duration_seconds=duration_seconds,
        composite_score=composite_score,
        cost_of_pass=cost_of_pass,
        grade=grade,
    )
