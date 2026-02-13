"""Scorecard generator for model-level result aggregation."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class EvalResult:
    """Summary of a model's performance on a single test."""

    runs_completed: int
    grade: str
    median_pass_rate: float
    median_impl_rate: float
    median_cost_usd: float
    median_duration_seconds: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "runs_completed": self.runs_completed,
            "grade": self.grade,
            "median_pass_rate": self.median_pass_rate,
            "median_impl_rate": self.median_impl_rate,
            "median_cost_usd": self.median_cost_usd,
            "median_duration_seconds": self.median_duration_seconds,
        }


@dataclass
class OverallStats:
    """Overall statistics for a model across all tests."""

    tests_completed: int
    average_grade: str
    total_cost_usd: float
    total_runs: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "tests_completed": self.tests_completed,
            "average_grade": self.average_grade,
            "total_cost_usd": self.total_cost_usd,
            "total_runs": self.total_runs,
        }


@dataclass
class ModelScorecard:
    """Scorecard aggregating all test results for a single model."""

    model_id: str
    model_name: str
    updated: str
    overall: OverallStats
    tests: dict[str, EvalResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "updated": self.updated,
            "overall": self.overall.to_dict(),
            "tests": {k: v.to_dict() for k, v in self.tests.items()},
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def write(self, output_dir: Path) -> Path:
        """Write scorecard.json to output directory.

        Args:
            output_dir: Directory to write scorecard.json

        Returns:
            Path to written file

        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "scorecard.json"
        output_path.write_text(self.to_json())
        return output_path


def _grade_to_points(grade: str) -> float:
    """Convert letter grade to point value for averaging.

    Uses industry-aligned scale where S is the highest grade.

    Args:
        grade: Letter grade (S, A, B, C, D, F with optional +/-)

    Returns:
        Numeric point value (0.0 to 5.0)

    """
    base_points = {"S": 5.0, "A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}

    if not grade:
        return 0.0

    base = grade[0].upper()
    points = base_points.get(base, 0.0)

    if len(grade) > 1:
        modifier = grade[1]
        if modifier == "+":
            points += 0.3
        elif modifier == "-":
            points -= 0.3

    return max(0.0, min(5.0, points))


def _points_to_grade(points: float) -> str:
    """Convert point value back to letter grade.

    Uses industry-aligned scale where S is the highest grade.

    Args:
        points: Numeric point value (0.0 to 5.0)

    Returns:
        Letter grade string (S, A, B, C, D, or F with optional +/-)

    """
    if points >= 4.85:
        return "S"
    elif points >= 3.85:
        return "A"
    elif points >= 3.5:
        return "A-"
    elif points >= 3.15:
        return "B+"
    elif points >= 2.85:
        return "B"
    elif points >= 2.5:
        return "B-"
    elif points >= 2.15:
        return "C+"
    elif points >= 1.85:
        return "C"
    elif points >= 1.5:
        return "C-"
    elif points >= 1.15:
        return "D+"
    elif points >= 0.85:
        return "D"
    elif points >= 0.5:
        return "D-"
    else:
        return "F"


class ScorecardGenerator:
    """Generates model scorecards by aggregating test results."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize scorecard generator.

        Args:
            base_dir: Base directory for scorecards (e.g., 'summaries/by-model/')

        """
        self.base_dir = base_dir

    def get_scorecard_dir(self, model_id: str) -> Path:
        """Get the directory path for a model scorecard.

        Args:
            model_id: Model identifier

        Returns:
            Path to scorecard directory

        """
        return self.base_dir / model_id

    def calculate_overall(self, tests: dict[str, EvalResult]) -> OverallStats:
        """Calculate overall statistics from test results.

        Args:
            tests: Dictionary of test_id -> EvalResult

        Returns:
            OverallStats with aggregated values

        """
        if not tests:
            return OverallStats(
                tests_completed=0,
                average_grade="F",
                total_cost_usd=0.0,
                total_runs=0,
            )

        tests_completed = len(tests)
        total_runs = sum(t.runs_completed for t in tests.values())
        total_cost = sum(t.median_cost_usd * t.runs_completed for t in tests.values())

        # Calculate average grade
        total_points = sum(_grade_to_points(t.grade) for t in tests.values())
        avg_points = total_points / tests_completed if tests_completed > 0 else 0.0
        average_grade = _points_to_grade(avg_points)

        return OverallStats(
            tests_completed=tests_completed,
            average_grade=average_grade,
            total_cost_usd=total_cost,
            total_runs=total_runs,
        )

    def generate_scorecard(
        self,
        model_id: str,
        model_name: str,
        tests: dict[str, EvalResult],
        timestamp: str | None = None,
    ) -> ModelScorecard:
        """Generate a model scorecard from test results.

        Args:
            model_id: Model identifier
            model_name: Human-readable model name
            tests: Dictionary of test_id -> EvalResult
            timestamp: Optional timestamp (auto-generated if not provided)

        Returns:
            ModelScorecard object

        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        overall = self.calculate_overall(tests)

        return ModelScorecard(
            model_id=model_id,
            model_name=model_name,
            updated=timestamp,
            overall=overall,
            tests=tests,
        )

    def write_scorecard(self, scorecard: ModelScorecard) -> Path:
        """Write a model scorecard to the appropriate directory.

        Args:
            scorecard: ModelScorecard to write

        Returns:
            Path to written scorecard.json

        """
        scorecard_dir = self.get_scorecard_dir(scorecard.model_id)
        return scorecard.write(scorecard_dir)

    def read_scorecard(self, model_id: str) -> ModelScorecard | None:
        """Read a model scorecard from the file system.

        Args:
            model_id: Model identifier

        Returns:
            ModelScorecard if found, None otherwise

        """
        scorecard_dir = self.get_scorecard_dir(model_id)
        scorecard_path = scorecard_dir / "scorecard.json"

        if not scorecard_path.exists():
            return None

        data = json.loads(scorecard_path.read_text())

        tests = {}
        for test_id, test_data in data.get("tests", {}).items():
            tests[test_id] = EvalResult(
                runs_completed=test_data["runs_completed"],
                grade=test_data["grade"],
                median_pass_rate=test_data["median_pass_rate"],
                median_impl_rate=test_data["median_impl_rate"],
                median_cost_usd=test_data["median_cost_usd"],
                median_duration_seconds=test_data["median_duration_seconds"],
            )

        overall_data = data["overall"]
        overall = OverallStats(
            tests_completed=overall_data["tests_completed"],
            average_grade=overall_data["average_grade"],
            total_cost_usd=overall_data["total_cost_usd"],
            total_runs=overall_data["total_runs"],
        )

        return ModelScorecard(
            model_id=data["model_id"],
            model_name=data["model_name"],
            updated=data["updated"],
            overall=overall,
            tests=tests,
        )


def create_test_result(
    runs_completed: int,
    grade: str,
    median_pass_rate: float,
    median_impl_rate: float,
    median_cost_usd: float,
    median_duration_seconds: float,
) -> EvalResult:
    """Create an EvalResult from evaluation metrics.

    Args:
        runs_completed: Number of completed runs
        grade: Letter grade
        median_pass_rate: Median pass rate
        median_impl_rate: Median implementation rate
        median_cost_usd: Median cost in USD
        median_duration_seconds: Median duration in seconds

    Returns:
        EvalResult object

    """
    return EvalResult(
        runs_completed=runs_completed,
        grade=grade,
        median_pass_rate=median_pass_rate,
        median_impl_rate=median_impl_rate,
        median_cost_usd=median_cost_usd,
        median_duration_seconds=median_duration_seconds,
    )
