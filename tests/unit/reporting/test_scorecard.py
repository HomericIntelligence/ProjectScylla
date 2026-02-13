"""Tests for scorecard.json generator."""

import json
import tempfile
from pathlib import Path

import pytest

from scylla.reporting.scorecard import (
    EvalResult,
    ModelScorecard,
    OverallStats,
    ScorecardGenerator,
    _grade_to_points,
    _points_to_grade,
    create_test_result,
)


def make_test_result(
    runs_completed: int = 10,
    grade: str = "B",
    median_pass_rate: float = 0.9,
    median_impl_rate: float = 0.85,
    median_cost_usd: float = 1.0,
    median_duration_seconds: float = 60.0,
) -> EvalResult:
    """Create test EvalResult."""
    return EvalResult(
        runs_completed=runs_completed,
        grade=grade,
        median_pass_rate=median_pass_rate,
        median_impl_rate=median_impl_rate,
        median_cost_usd=median_cost_usd,
        median_duration_seconds=median_duration_seconds,
    )


class TestEvalResult:
    """Tests for EvalResult dataclass."""

    def test_create(self) -> None:
        """Test Create."""
        result = EvalResult(
            runs_completed=10,
            grade="A",
            median_pass_rate=1.0,
            median_impl_rate=0.95,
            median_cost_usd=0.50,
            median_duration_seconds=45.0,
        )
        assert result.runs_completed == 10
        assert result.grade == "A"

    def test_to_dict(self) -> None:
        """Test To dict."""
        result = make_test_result()
        data = result.to_dict()

        assert data["runs_completed"] == 10
        assert data["grade"] == "B"
        assert data["median_pass_rate"] == pytest.approx(0.9)
        assert "median_cost_usd" in data


class TestOverallStats:
    """Tests for OverallStats dataclass."""

    def test_create(self) -> None:
        """Test Create."""
        stats = OverallStats(
            tests_completed=5,
            average_grade="B",
            total_cost_usd=25.0,
            total_runs=50,
        )
        assert stats.tests_completed == 5
        assert stats.total_runs == 50

    def test_to_dict(self) -> None:
        """Test To dict."""
        stats = OverallStats(
            tests_completed=5,
            average_grade="B+",
            total_cost_usd=25.0,
            total_runs=50,
        )
        data = stats.to_dict()

        assert data["tests_completed"] == 5
        assert data["average_grade"] == "B+"
        assert data["total_cost_usd"] == pytest.approx(25.0)
        assert data["total_runs"] == 50


class TestModelScorecard:
    """Tests for ModelScorecard dataclass."""

    def test_create(self) -> None:
        """Test Create."""
        scorecard = ModelScorecard(
            model_id="claude-opus-4-5-20251101",
            model_name="Claude Opus 4.5",
            updated="2024-01-15T14:30:00Z",
            overall=OverallStats(5, "B", 25.0, 50),
        )
        assert scorecard.model_id == "claude-opus-4-5-20251101"
        assert scorecard.model_name == "Claude Opus 4.5"

    def test_create_with_tests(self) -> None:
        """Test Create with tests."""
        scorecard = ModelScorecard(
            model_id="claude-opus-4-5-20251101",
            model_name="Claude Opus 4.5",
            updated="2024-01-15T14:30:00Z",
            overall=OverallStats(1, "A", 10.0, 10),
            tests={"001-test": make_test_result()},
        )
        assert "001-test" in scorecard.tests

    def test_to_dict(self) -> None:
        """Test To dict."""
        scorecard = ModelScorecard(
            model_id="claude-opus-4-5-20251101",
            model_name="Claude Opus 4.5",
            updated="2024-01-15T14:30:00Z",
            overall=OverallStats(1, "A", 10.0, 10),
            tests={"001-test": make_test_result()},
        )
        data = scorecard.to_dict()

        assert data["model_id"] == "claude-opus-4-5-20251101"
        assert "overall" in data
        assert "001-test" in data["tests"]

    def test_to_json(self) -> None:
        """Test To json."""
        scorecard = ModelScorecard(
            model_id="test-model",
            model_name="Test Model",
            updated="2024-01-15T14:30:00Z",
            overall=OverallStats(1, "A", 10.0, 10),
        )
        json_str = scorecard.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["model_id"] == "test-model"

    def test_write(self) -> None:
        """Test Write."""
        scorecard = ModelScorecard(
            model_id="test-model",
            model_name="Test Model",
            updated="2024-01-15T14:30:00Z",
            overall=OverallStats(1, "A", 10.0, 10),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_path = scorecard.write(output_dir)

            assert output_path.exists()
            assert output_path.name == "scorecard.json"


class TestGradeConversion:
    """Tests for grade conversion functions."""

    def test_grade_to_points(self) -> None:
        """Test Grade to points."""
        assert _grade_to_points("A") == pytest.approx(4.0)
        assert _grade_to_points("B") == pytest.approx(3.0)
        assert _grade_to_points("C") == pytest.approx(2.0)
        assert _grade_to_points("D") == pytest.approx(1.0)
        assert _grade_to_points("F") == pytest.approx(0.0)

    def test_grade_to_points_with_modifiers(self) -> None:
        """Test Grade to points with modifiers."""
        assert _grade_to_points("A+") == pytest.approx(4.3)
        assert _grade_to_points("A-") == pytest.approx(3.7)
        assert _grade_to_points("B+") == pytest.approx(3.3)
        assert _grade_to_points("B-") == pytest.approx(2.7)

    def test_grade_to_points_edge_cases(self) -> None:
        """Test Grade to points edge cases."""
        assert _grade_to_points("") == pytest.approx(0.0)
        assert _grade_to_points("F-") == pytest.approx(0.0)  # Can't go below 0

    def test_points_to_grade(self) -> None:
        """Test Points to grade."""
        assert _points_to_grade(4.0) == "A"
        assert _points_to_grade(3.0) == "B"
        assert _points_to_grade(2.0) == "C"
        assert _points_to_grade(1.0) == "D"
        assert _points_to_grade(0.0) == "F"

    def test_points_to_grade_with_modifiers(self) -> None:
        """Test Points to grade with modifiers."""
        assert _points_to_grade(3.5) == "A-"
        assert _points_to_grade(3.2) == "B+"
        assert _points_to_grade(2.6) == "B-"

    def test_roundtrip_conversion(self) -> None:
        """Test Roundtrip conversion."""
        # A grade converted to points and back should be stable
        for grade in ["A", "B", "C", "D", "F"]:
            points = _grade_to_points(grade)
            result = _points_to_grade(points)
            assert result == grade


class TestScorecardGeneratorCalculateOverall:
    """Tests for ScorecardGenerator.calculate_overall method."""

    def test_empty_tests(self) -> None:
        """Test Empty tests."""
        generator = ScorecardGenerator(Path("/tmp"))
        overall = generator.calculate_overall({})

        assert overall.tests_completed == 0
        assert overall.average_grade == "F"
        assert overall.total_cost_usd == pytest.approx(0.0)
        assert overall.total_runs == 0

    def test_single_test(self) -> None:
        """Test Single test."""
        generator = ScorecardGenerator(Path("/tmp"))
        tests = {"001-test": make_test_result(runs_completed=10, grade="A")}
        overall = generator.calculate_overall(tests)

        assert overall.tests_completed == 1
        assert overall.average_grade == "A"
        assert overall.total_runs == 10

    def test_multiple_tests(self) -> None:
        """Test Multiple tests."""
        generator = ScorecardGenerator(Path("/tmp"))
        tests = {
            "001-test": make_test_result(runs_completed=10, grade="A"),
            "002-test": make_test_result(runs_completed=10, grade="B"),
            "003-test": make_test_result(runs_completed=10, grade="C"),
        }
        overall = generator.calculate_overall(tests)

        assert overall.tests_completed == 3
        assert overall.total_runs == 30
        # Average of A(4.0) + B(3.0) + C(2.0) = 3.0 -> B
        assert overall.average_grade == "B"

    def test_cost_calculation(self) -> None:
        """Test Cost calculation."""
        generator = ScorecardGenerator(Path("/tmp"))
        tests = {
            "001-test": make_test_result(runs_completed=5, median_cost_usd=1.0),
            "002-test": make_test_result(runs_completed=10, median_cost_usd=2.0),
        }
        overall = generator.calculate_overall(tests)

        # Total cost = 5 * 1.0 + 10 * 2.0 = 25.0
        assert overall.total_cost_usd == pytest.approx(25.0)


class TestScorecardGeneratorGenerateScorecard:
    """Tests for ScorecardGenerator.generate_scorecard method."""

    def test_generate_basic(self) -> None:
        """Test Generate basic."""
        generator = ScorecardGenerator(Path("/tmp"))
        tests = {"001-test": make_test_result()}

        scorecard = generator.generate_scorecard(
            model_id="test-model",
            model_name="Test Model",
            tests=tests,
            timestamp="2024-01-15T14:30:00Z",
        )

        assert scorecard.model_id == "test-model"
        assert scorecard.model_name == "Test Model"
        assert "001-test" in scorecard.tests

    def test_generate_auto_timestamp(self) -> None:
        """Test Generate auto timestamp."""
        generator = ScorecardGenerator(Path("/tmp"))
        tests = {"001-test": make_test_result()}

        scorecard = generator.generate_scorecard(
            model_id="test-model",
            model_name="Test Model",
            tests=tests,
        )

        assert scorecard.updated is not None
        assert scorecard.updated.endswith("Z")

    def test_generate_includes_overall(self) -> None:
        """Test Generate includes overall."""
        generator = ScorecardGenerator(Path("/tmp"))
        tests = {
            "001-test": make_test_result(grade="A"),
            "002-test": make_test_result(grade="B"),
        }

        scorecard = generator.generate_scorecard(
            model_id="test-model",
            model_name="Test Model",
            tests=tests,
        )

        assert scorecard.overall.tests_completed == 2


class TestScorecardGeneratorWriteRead:
    """Tests for ScorecardGenerator write/read methods."""

    def test_write_scorecard(self) -> None:
        """Test Write scorecard."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ScorecardGenerator(Path(tmpdir))
            tests = {"001-test": make_test_result()}

            scorecard = generator.generate_scorecard(
                model_id="test-model",
                model_name="Test Model",
                tests=tests,
            )
            output_path = generator.write_scorecard(scorecard)

            assert output_path.exists()
            expected_path = Path(tmpdir) / "test-model" / "scorecard.json"
            assert output_path == expected_path

    def test_read_scorecard(self) -> None:
        """Test Read scorecard."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ScorecardGenerator(Path(tmpdir))
            tests = {"001-test": make_test_result()}

            scorecard = generator.generate_scorecard(
                model_id="test-model",
                model_name="Test Model",
                tests=tests,
            )
            generator.write_scorecard(scorecard)

            # Read it back
            read_scorecard = generator.read_scorecard("test-model")

            assert read_scorecard is not None
            assert read_scorecard.model_id == "test-model"
            assert "001-test" in read_scorecard.tests
            assert read_scorecard.tests["001-test"].grade == "B"

    def test_read_scorecard_not_found(self) -> None:
        """Test Read scorecard not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ScorecardGenerator(Path(tmpdir))

            result = generator.read_scorecard("nonexistent")
            assert result is None

    def test_read_preserves_overall(self) -> None:
        """Test Read preserves overall."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ScorecardGenerator(Path(tmpdir))
            tests = {
                "001-test": make_test_result(grade="A"),
                "002-test": make_test_result(grade="C"),
            }

            scorecard = generator.generate_scorecard(
                model_id="test-model",
                model_name="Test Model",
                tests=tests,
            )
            generator.write_scorecard(scorecard)

            read_scorecard = generator.read_scorecard("test-model")

            assert read_scorecard is not None
            assert read_scorecard.overall.tests_completed == 2


class TestCreateEvalResult:
    """Tests for create_test_result factory function."""

    def test_create(self) -> None:
        """Test Create."""
        result = create_test_result(
            runs_completed=10,
            grade="A",
            median_pass_rate=1.0,
            median_impl_rate=0.95,
            median_cost_usd=0.50,
            median_duration_seconds=45.0,
        )
        assert result.runs_completed == 10
        assert result.grade == "A"
        assert result.median_pass_rate == pytest.approx(1.0)
