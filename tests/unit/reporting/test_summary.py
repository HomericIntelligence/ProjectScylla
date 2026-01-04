"""Tests for summary.json generator.

Python justification: Required for pytest testing framework.
"""

import json
import tempfile
from pathlib import Path

from scylla.reporting.summary import (
    EvaluationReport,
    ModelStatistics,
    Rankings,
    SummaryGenerator,
    SummaryStatistics,
    create_model_statistics,
    create_statistics,
)


def make_statistics(
    median: float = 0.8,
    mean: float = 0.75,
    mode: float = 0.8,
    min_val: float = 0.6,
    max_val: float = 0.9,
    std_dev: float = 0.1,
) -> SummaryStatistics:
    """Create test SummaryStatistics."""
    return SummaryStatistics(
        median=median,
        mean=mean,
        mode=mode,
        min=min_val,
        max=max_val,
        std_dev=std_dev,
    )


def make_model_statistics(
    runs_completed: int = 10,
    grade: str = "B",
    composite_median: float = 0.85,
    cost_median: float = 1.0,
    duration_median: float = 60.0,
) -> ModelStatistics:
    """Create test ModelStatistics."""
    return ModelStatistics(
        runs_completed=runs_completed,
        pass_rate=make_statistics(median=0.9),
        impl_rate=make_statistics(median=0.8),
        cost_usd=make_statistics(median=cost_median),
        duration_seconds=make_statistics(median=duration_median),
        composite_score=make_statistics(median=composite_median),
        cost_of_pass=make_statistics(median=cost_median / 0.9),
        grade=grade,
    )


class EvaluationReportStatistics:
    """Tests for SummaryStatistics dataclass."""

    def test_create(self) -> None:
        stats = SummaryStatistics(
            median=0.8,
            mean=0.75,
            mode=0.8,
            min=0.6,
            max=0.9,
            std_dev=0.1,
        )
        assert stats.median == 0.8
        assert stats.mean == 0.75
        assert stats.std_dev == 0.1

    def test_to_dict(self) -> None:
        stats = make_statistics()
        data = stats.to_dict()

        assert data["median"] == 0.8
        assert data["mean"] == 0.75
        assert "min" in data
        assert "max" in data

    def test_zero_values(self) -> None:
        stats = SummaryStatistics(
            median=0.0,
            mean=0.0,
            mode=0.0,
            min=0.0,
            max=0.0,
            std_dev=0.0,
        )
        assert stats.median == 0.0


class TestModelStatistics:
    """Tests for ModelStatistics dataclass."""

    def test_create(self) -> None:
        model_stats = make_model_statistics()
        assert model_stats.runs_completed == 10
        assert model_stats.grade == "B"

    def test_to_dict(self) -> None:
        model_stats = make_model_statistics()
        data = model_stats.to_dict()

        assert data["runs_completed"] == 10
        assert data["grade"] == "B"
        assert "pass_rate" in data
        assert "impl_rate" in data
        assert "cost_usd" in data

    def test_to_dict_nested_stats(self) -> None:
        model_stats = make_model_statistics()
        data = model_stats.to_dict()

        # Nested statistics should be dicts
        assert isinstance(data["pass_rate"], dict)
        assert data["pass_rate"]["median"] == 0.9


class TestRankings:
    """Tests for Rankings dataclass."""

    def test_create_empty(self) -> None:
        rankings = Rankings()
        assert rankings.by_quality == []
        assert rankings.by_cost_efficiency == []
        assert rankings.by_speed == []

    def test_create_with_values(self) -> None:
        rankings = Rankings(
            by_quality=["model-a", "model-b"],
            by_cost_efficiency=["model-b", "model-a"],
            by_speed=["model-a", "model-b"],
        )
        assert rankings.by_quality == ["model-a", "model-b"]
        assert rankings.by_cost_efficiency[0] == "model-b"

    def test_to_dict(self) -> None:
        rankings = Rankings(
            by_quality=["model-a"],
            by_cost_efficiency=["model-b"],
            by_speed=["model-a"],
        )
        data = rankings.to_dict()

        assert data["by_quality"] == ["model-a"]
        assert data["by_cost_efficiency"] == ["model-b"]


class TestEvaluationReport:
    """Tests for EvaluationReport dataclass."""

    def test_create(self) -> None:
        summary = EvaluationReport(
            test_id="001-test",
            test_name="Test Name",
            updated="2024-01-15T14:30:00Z",
            runs_per_model=10,
        )
        assert summary.test_id == "001-test"
        assert summary.runs_per_model == 10

    def test_create_with_models(self) -> None:
        summary = EvaluationReport(
            test_id="001-test",
            test_name="Test Name",
            updated="2024-01-15T14:30:00Z",
            runs_per_model=10,
            models={"model-a": make_model_statistics()},
        )
        assert "model-a" in summary.models

    def test_to_dict(self) -> None:
        summary = EvaluationReport(
            test_id="001-test",
            test_name="Test Name",
            updated="2024-01-15T14:30:00Z",
            runs_per_model=10,
            models={"model-a": make_model_statistics()},
            rankings=Rankings(by_quality=["model-a"]),
        )
        data = summary.to_dict()

        assert data["test_id"] == "001-test"
        assert data["test_name"] == "Test Name"
        assert "model-a" in data["models"]
        assert data["rankings"]["by_quality"] == ["model-a"]

    def test_to_json(self) -> None:
        summary = EvaluationReport(
            test_id="001-test",
            test_name="Test Name",
            updated="2024-01-15T14:30:00Z",
            runs_per_model=10,
        )
        json_str = summary.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["test_id"] == "001-test"

    def test_write(self) -> None:
        summary = EvaluationReport(
            test_id="001-test",
            test_name="Test Name",
            updated="2024-01-15T14:30:00Z",
            runs_per_model=10,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_path = summary.write(output_dir)

            assert output_path.exists()
            assert output_path.name == "summary.json"


class EvaluationReportGeneratorCalculateRankings:
    """Tests for SummaryGenerator.calculate_rankings method."""

    def test_empty_models(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))
        rankings = generator.calculate_rankings({})

        assert rankings.by_quality == []
        assert rankings.by_cost_efficiency == []
        assert rankings.by_speed == []

    def test_single_model(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))
        models = {"model-a": make_model_statistics()}
        rankings = generator.calculate_rankings(models)

        assert rankings.by_quality == ["model-a"]
        assert rankings.by_cost_efficiency == ["model-a"]
        assert rankings.by_speed == ["model-a"]

    def test_ranking_by_quality(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))
        models = {
            "model-a": make_model_statistics(composite_median=0.7),
            "model-b": make_model_statistics(composite_median=0.9),
            "model-c": make_model_statistics(composite_median=0.8),
        }
        rankings = generator.calculate_rankings(models)

        # Higher composite score first
        assert rankings.by_quality == ["model-b", "model-c", "model-a"]

    def test_ranking_by_cost_efficiency(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))
        models = {
            "model-a": make_model_statistics(cost_median=2.0),
            "model-b": make_model_statistics(cost_median=1.0),
            "model-c": make_model_statistics(cost_median=3.0),
        }
        rankings = generator.calculate_rankings(models)

        # Lower cost first (more efficient)
        assert rankings.by_cost_efficiency == ["model-b", "model-a", "model-c"]

    def test_ranking_by_speed(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))
        models = {
            "model-a": make_model_statistics(duration_median=60.0),
            "model-b": make_model_statistics(duration_median=30.0),
            "model-c": make_model_statistics(duration_median=90.0),
        }
        rankings = generator.calculate_rankings(models)

        # Lower duration first (faster)
        assert rankings.by_speed == ["model-b", "model-a", "model-c"]

    def test_infinity_cost_ranked_last(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))

        model_with_inf = make_model_statistics()
        model_with_inf.cost_of_pass = make_statistics(median=float("inf"))

        model_normal = make_model_statistics()
        model_normal.cost_of_pass = make_statistics(median=1.0)

        models = {
            "model-inf": model_with_inf,
            "model-normal": model_normal,
        }
        rankings = generator.calculate_rankings(models)

        # Infinity cost should be last
        assert rankings.by_cost_efficiency[-1] == "model-inf"


class EvaluationReportGeneratorGenerateSummary:
    """Tests for SummaryGenerator.generate_summary method."""

    def test_generate_basic(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))
        models = {"model-a": make_model_statistics()}

        summary = generator.generate_summary(
            test_id="001-test",
            test_name="Test Name",
            models=models,
            timestamp="2024-01-15T14:30:00Z",
        )

        assert summary.test_id == "001-test"
        assert summary.test_name == "Test Name"
        assert "model-a" in summary.models

    def test_generate_auto_timestamp(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))
        models = {"model-a": make_model_statistics()}

        summary = generator.generate_summary(
            test_id="001-test",
            test_name="Test Name",
            models=models,
        )

        assert summary.updated is not None
        assert summary.updated.endswith("Z")

    def test_generate_includes_rankings(self) -> None:
        generator = SummaryGenerator(Path("/tmp"))
        models = {
            "model-a": make_model_statistics(composite_median=0.7),
            "model-b": make_model_statistics(composite_median=0.9),
        }

        summary = generator.generate_summary(
            test_id="001-test",
            test_name="Test Name",
            models=models,
        )

        assert summary.rankings.by_quality[0] == "model-b"


class EvaluationReportGeneratorWriteRead:
    """Tests for SummaryGenerator write/read methods."""

    def test_write_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SummaryGenerator(Path(tmpdir))
            models = {"model-a": make_model_statistics()}

            summary = generator.generate_summary(
                test_id="001-test",
                test_name="Test Name",
                models=models,
            )
            output_path = generator.write_summary(summary)

            assert output_path.exists()
            expected_path = Path(tmpdir) / "001-test" / "summary.json"
            assert output_path == expected_path

    def test_read_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SummaryGenerator(Path(tmpdir))
            models = {"model-a": make_model_statistics()}

            summary = generator.generate_summary(
                test_id="001-test",
                test_name="Test Name",
                models=models,
            )
            generator.write_summary(summary)

            # Read it back
            read_summary = generator.read_summary("001-test")

            assert read_summary is not None
            assert read_summary.test_id == "001-test"
            assert "model-a" in read_summary.models
            assert read_summary.models["model-a"].grade == "B"

    def test_read_summary_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SummaryGenerator(Path(tmpdir))

            result = generator.read_summary("nonexistent")
            assert result is None

    def test_read_preserves_rankings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SummaryGenerator(Path(tmpdir))
            models = {
                "model-a": make_model_statistics(composite_median=0.7),
                "model-b": make_model_statistics(composite_median=0.9),
            }

            summary = generator.generate_summary(
                test_id="001-test",
                test_name="Test Name",
                models=models,
            )
            generator.write_summary(summary)

            read_summary = generator.read_summary("001-test")

            assert read_summary is not None
            assert read_summary.rankings.by_quality[0] == "model-b"


class TestCreateStatistics:
    """Tests for create_statistics factory function."""

    def test_create(self) -> None:
        stats = create_statistics(
            median=0.8,
            mean=0.75,
            mode=0.8,
            min_val=0.6,
            max_val=0.9,
            std_dev=0.1,
        )
        assert stats.median == 0.8
        assert stats.min == 0.6
        assert stats.max == 0.9


class TestCreateModelStatistics:
    """Tests for create_model_statistics factory function."""

    def test_create(self) -> None:
        stats = create_model_statistics(
            runs_completed=10,
            pass_rate=make_statistics(),
            impl_rate=make_statistics(),
            cost_usd=make_statistics(),
            duration_seconds=make_statistics(),
            composite_score=make_statistics(),
            cost_of_pass=make_statistics(),
            grade="A",
        )
        assert stats.runs_completed == 10
        assert stats.grade == "A"
