"""Summary generator for test-level result aggregation.

Python justification: JSON serialization and file I/O for summary persistence.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class SummaryStatistics:
    """Statistical summary of a metric across multiple runs."""

    median: float
    mean: float
    mode: float
    min: float
    max: float
    std_dev: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "median": self.median,
            "mean": self.mean,
            "mode": self.mode,
            "min": self.min,
            "max": self.max,
            "std_dev": self.std_dev,
        }


@dataclass
class ModelStatistics:
    """Statistics for a single model on a test."""

    runs_completed: int
    pass_rate: SummaryStatistics
    impl_rate: SummaryStatistics
    cost_usd: SummaryStatistics
    duration_seconds: SummaryStatistics
    composite_score: SummaryStatistics
    cost_of_pass: SummaryStatistics
    grade: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "runs_completed": self.runs_completed,
            "pass_rate": self.pass_rate.to_dict(),
            "impl_rate": self.impl_rate.to_dict(),
            "cost_usd": self.cost_usd.to_dict(),
            "duration_seconds": self.duration_seconds.to_dict(),
            "composite_score": self.composite_score.to_dict(),
            "cost_of_pass": self.cost_of_pass.to_dict(),
            "grade": self.grade,
        }


@dataclass
class Rankings:
    """Model rankings by different criteria."""

    by_quality: list[str] = field(default_factory=list)
    by_cost_efficiency: list[str] = field(default_factory=list)
    by_speed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "by_quality": self.by_quality,
            "by_cost_efficiency": self.by_cost_efficiency,
            "by_speed": self.by_speed,
        }


@dataclass
class EvaluationReport:
    """Summary of all model results for a single test."""

    test_id: str
    test_name: str
    updated: str
    runs_per_model: int
    models: dict[str, ModelStatistics] = field(default_factory=dict)
    rankings: Rankings = field(default_factory=Rankings)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "updated": self.updated,
            "runs_per_model": self.runs_per_model,
            "models": {k: v.to_dict() for k, v in self.models.items()},
            "rankings": self.rankings.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

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
            timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

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

        models = {}
        for model_id, model_data in data.get("models", {}).items():
            models[model_id] = ModelStatistics(
                runs_completed=model_data["runs_completed"],
                pass_rate=SummaryStatistics(**model_data["pass_rate"]),
                impl_rate=SummaryStatistics(**model_data["impl_rate"]),
                cost_usd=SummaryStatistics(**model_data["cost_usd"]),
                duration_seconds=SummaryStatistics(**model_data["duration_seconds"]),
                composite_score=SummaryStatistics(**model_data["composite_score"]),
                cost_of_pass=SummaryStatistics(**model_data["cost_of_pass"]),
                grade=model_data["grade"],
            )

        rankings_data = data.get("rankings", {})
        rankings = Rankings(
            by_quality=rankings_data.get("by_quality", []),
            by_cost_efficiency=rankings_data.get("by_cost_efficiency", []),
            by_speed=rankings_data.get("by_speed", []),
        )

        return EvaluationReport(
            test_id=data["test_id"],
            test_name=data["test_name"],
            updated=data["updated"],
            runs_per_model=data["runs_per_model"],
            models=models,
            rankings=rankings,
        )


def create_statistics(
    median: float,
    mean: float,
    mode: float,
    min_val: float,
    max_val: float,
    std_dev: float,
) -> SummaryStatistics:
    """Factory function to create SummaryStatistics.

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
    pass_rate: Statistics,
    impl_rate: Statistics,
    cost_usd: Statistics,
    duration_seconds: Statistics,
    composite_score: Statistics,
    cost_of_pass: Statistics,
    grade: str,
) -> ModelStatistics:
    """Factory function to create ModelStatistics.

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
