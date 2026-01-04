"""Tests for result.json writer.

Python justification: Required for pytest testing framework.
"""

import json
import tempfile
from pathlib import Path

from scylla.reporting.result import (
    ExecutionInfo,
    GradingInfo,
    JudgmentInfo,
    MetricsInfo,
    ResultWriter,
    RunResult,
    create_run_result,
)


def make_execution() -> ExecutionInfo:
    """Create test ExecutionInfo."""
    return ExecutionInfo(
        status="completed",
        duration_seconds=45.0,
        exit_code=0,
    )


def make_metrics() -> MetricsInfo:
    """Create test MetricsInfo."""
    return MetricsInfo(
        tokens_input=10000,
        tokens_output=5000,
        cost_usd=0.50,
        api_calls=5,
    )


def make_judgment() -> JudgmentInfo:
    """Create test JudgmentInfo."""
    return JudgmentInfo(
        passed=True,
        impl_rate=0.85,
        letter_grade="B",
    )


def make_grading() -> GradingInfo:
    """Create test GradingInfo."""
    return GradingInfo(
        pass_rate=1.0,
        cost_of_pass=0.50,
        composite_score=0.925,
    )


def make_run_result() -> RunResult:
    """Create test RunResult."""
    return RunResult(
        test_id="001-test",
        tier_id="T1",
        model_id="claude-opus-4-5-20251101",
        run_number=1,
        timestamp="2024-01-15T14:30:00Z",
        execution=make_execution(),
        metrics=make_metrics(),
        judgment=make_judgment(),
        grading=make_grading(),
    )


class TestExecutionInfo:
    """Tests for ExecutionInfo dataclass."""

    def test_create(self) -> None:
        """Test Create."""
        info = ExecutionInfo(
            status="completed",
            duration_seconds=45.0,
            exit_code=0,
        )
        assert info.status == "completed"
        assert info.duration_seconds == 45.0
        assert info.exit_code == 0

    def test_failed_status(self) -> None:
        """Test Failed status."""
        info = ExecutionInfo(
            status="failed",
            duration_seconds=10.0,
            exit_code=1,
        )
        assert info.status == "failed"
        assert info.exit_code == 1

    def test_timeout_status(self) -> None:
        """Test Timeout status."""
        info = ExecutionInfo(
            status="timeout",
            duration_seconds=300.0,
            exit_code=-1,
        )
        assert info.status == "timeout"


class TestMetricsInfo:
    """Tests for MetricsInfo dataclass."""

    def test_create(self) -> None:
        """Test Create."""
        info = MetricsInfo(
            tokens_input=10000,
            tokens_output=5000,
            cost_usd=0.50,
            api_calls=5,
        )
        assert info.tokens_input == 10000
        assert info.tokens_output == 5000
        assert info.cost_usd == 0.50
        assert info.api_calls == 5

    def test_zero_values(self) -> None:
        """Test Zero values."""
        info = MetricsInfo(
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
            api_calls=0,
        )
        assert info.tokens_input == 0
        assert info.cost_usd == 0.0


class TestJudgmentInfo:
    """Tests for JudgmentInfo dataclass."""

    def test_passed(self) -> None:
        """Test Passed."""
        info = JudgmentInfo(
            passed=True,
            impl_rate=0.95,
            letter_grade="A",
        )
        assert info.passed is True
        assert info.impl_rate == 0.95
        assert info.letter_grade == "A"

    def test_failed(self) -> None:
        """Test Failed."""
        info = JudgmentInfo(
            passed=False,
            impl_rate=0.3,
            letter_grade="F",
        )
        assert info.passed is False
        assert info.letter_grade == "F"


class TestGradingInfo:
    """Tests for GradingInfo dataclass."""

    def test_create(self) -> None:
        """Test Create."""
        info = GradingInfo(
            pass_rate=1.0,
            cost_of_pass=0.50,
            composite_score=0.925,
        )
        assert info.pass_rate == 1.0
        assert info.cost_of_pass == 0.50
        assert info.composite_score == 0.925

    def test_failed_run(self) -> None:
        """Test Failed run."""
        info = GradingInfo(
            pass_rate=0.0,
            cost_of_pass=float("inf"),
            composite_score=0.15,
        )
        assert info.pass_rate == 0.0
        assert info.cost_of_pass == float("inf")


class TestRunResult:
    """Tests for RunResult dataclass."""

    def test_create(self) -> None:
        """Test Create."""
        result = make_run_result()
        assert result.test_id == "001-test"
        assert result.tier_id == "T1"
        assert result.model_id == "claude-opus-4-5-20251101"
        assert result.run_number == 1
        assert result.timestamp == "2024-01-15T14:30:00Z"

    def test_to_dict(self) -> None:
        """Test To dict."""
        result = make_run_result()
        data = result.to_dict()

        assert data["test_id"] == "001-test"
        assert data["tier_id"] == "T1"
        assert data["model_id"] == "claude-opus-4-5-20251101"
        assert data["run_number"] == 1
        assert "execution" in data
        assert "metrics" in data
        assert "judgment" in data
        assert "grading" in data

    def test_to_dict_execution(self) -> None:
        """Test To dict execution."""
        result = make_run_result()
        data = result.to_dict()

        assert data["execution"]["status"] == "completed"
        assert data["execution"]["duration_seconds"] == 45.0
        assert data["execution"]["exit_code"] == 0

    def test_to_dict_metrics(self) -> None:
        """Test To dict metrics."""
        result = make_run_result()
        data = result.to_dict()

        assert data["metrics"]["tokens_input"] == 10000
        assert data["metrics"]["tokens_output"] == 5000
        assert data["metrics"]["cost_usd"] == 0.50
        assert data["metrics"]["api_calls"] == 5

    def test_to_dict_judgment(self) -> None:
        """Test To dict judgment."""
        result = make_run_result()
        data = result.to_dict()

        assert data["judgment"]["passed"] is True
        assert data["judgment"]["impl_rate"] == 0.85
        assert data["judgment"]["letter_grade"] == "B"

    def test_to_dict_grading(self) -> None:
        """Test To dict grading."""
        result = make_run_result()
        data = result.to_dict()

        assert data["grading"]["pass_rate"] == 1.0
        assert data["grading"]["cost_of_pass"] == 0.50
        assert data["grading"]["composite_score"] == 0.925

    def test_to_json(self) -> None:
        """Test To json."""
        result = make_run_result()
        json_str = result.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["test_id"] == "001-test"

    def test_to_json_formatting(self) -> None:
        """Test To json formatting."""
        result = make_run_result()

        # Default indent
        json_str = result.to_json()
        assert "\n" in json_str  # Has newlines due to indent

        # Custom indent
        result.to_json(indent=None)
        # With indent=None, json.dumps still produces valid JSON

    def test_write(self) -> None:
        """Test Write."""
        result = make_run_result()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_path = result.write(output_dir)

            assert output_path.exists()
            assert output_path.name == "result.json"

            # Verify content
            data = json.loads(output_path.read_text())
            assert data["test_id"] == "001-test"

    def test_write_creates_directories(self) -> None:
        """Test Write creates directories."""
        result = make_run_result()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Nested directory that doesn't exist
            output_dir = Path(tmpdir) / "a" / "b" / "c"
            output_path = result.write(output_dir)

            assert output_path.exists()
            assert output_dir.exists()


class TestResultWriter:
    """Tests for ResultWriter class."""

    def test_init(self) -> None:
        """Test Init."""
        writer = ResultWriter(Path("/tmp/runs"))
        assert writer.base_dir == Path("/tmp/runs")

    def test_get_run_dir(self) -> None:
        """Test Get run dir."""
        writer = ResultWriter(Path("/tmp/runs"))
        run_dir = writer.get_run_dir("001-test", "T1", 1)

        assert run_dir == Path("/tmp/runs/001-test/T1/run_01")

    def test_get_run_dir_formatting(self) -> None:
        """Test Get run dir formatting."""
        writer = ResultWriter(Path("/tmp/runs"))

        # Single digit run number should be zero-padded
        run_dir = writer.get_run_dir("test", "T0", 5)
        assert run_dir.name == "run_05"

        # Double digit run number
        run_dir = writer.get_run_dir("test", "T0", 10)
        assert run_dir.name == "run_10"

    def test_write_result(self) -> None:
        """Test Write result."""
        result = make_run_result()

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResultWriter(Path(tmpdir))
            output_path = writer.write_result(result)

            assert output_path.exists()
            expected_path = Path(tmpdir) / "001-test" / "T1" / "run_01" / "result.json"
            assert output_path == expected_path

    def test_read_result(self) -> None:
        """Test Read result."""
        result = make_run_result()

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResultWriter(Path(tmpdir))
            writer.write_result(result)

            # Read it back
            read_result = writer.read_result("001-test", "T1", 1)

            assert read_result is not None
            assert read_result.test_id == "001-test"
            assert read_result.tier_id == "T1"
            assert read_result.model_id == "claude-opus-4-5-20251101"
            assert read_result.execution.status == "completed"

    def test_read_result_not_found(self) -> None:
        """Test Read result not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResultWriter(Path(tmpdir))

            result = writer.read_result("nonexistent", "T0", 1)
            assert result is None

    def test_write_multiple_runs(self) -> None:
        """Test Write multiple runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResultWriter(Path(tmpdir))

            for run_num in range(1, 11):
                result = RunResult(
                    test_id="001-test",
                    tier_id="T1",
                    model_id="test-model",
                    run_number=run_num,
                    timestamp="2024-01-15T14:30:00Z",
                    execution=make_execution(),
                    metrics=make_metrics(),
                    judgment=make_judgment(),
                    grading=make_grading(),
                )
                writer.write_result(result)

            # Verify all 10 runs written
            tier_dir = Path(tmpdir) / "001-test" / "T1"
            run_dirs = list(tier_dir.iterdir())
            assert len(run_dirs) == 10

    def test_write_multiple_tiers(self) -> None:
        """Test Write multiple tiers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResultWriter(Path(tmpdir))

            for tier in ["T0", "T1", "T2", "T3"]:
                result = RunResult(
                    test_id="001-test",
                    tier_id=tier,
                    model_id="test-model",
                    run_number=1,
                    timestamp="2024-01-15T14:30:00Z",
                    execution=make_execution(),
                    metrics=make_metrics(),
                    judgment=make_judgment(),
                    grading=make_grading(),
                )
                writer.write_result(result)

            # Verify all tiers written
            test_dir = Path(tmpdir) / "001-test"
            tier_dirs = list(test_dir.iterdir())
            assert len(tier_dirs) == 4


class TestCreateRunResult:
    """Tests for create_run_result factory function."""

    def test_create_with_all_params(self) -> None:
        """Test Create with all params."""
        result = create_run_result(
            test_id="001-test",
            tier_id="T1",
            model_id="test-model",
            run_number=1,
            status="completed",
            duration_seconds=45.0,
            exit_code=0,
            tokens_input=10000,
            tokens_output=5000,
            cost_usd=0.50,
            api_calls=5,
            passed=True,
            impl_rate=0.85,
            letter_grade="B",
            pass_rate=1.0,
            cost_of_pass=0.50,
            composite_score=0.925,
            timestamp="2024-01-15T14:30:00Z",
        )

        assert result.test_id == "001-test"
        assert result.execution.status == "completed"
        assert result.metrics.tokens_input == 10000
        assert result.judgment.passed is True
        assert result.grading.pass_rate == 1.0

    def test_create_auto_timestamp(self) -> None:
        """Test Create auto timestamp."""
        result = create_run_result(
            test_id="001-test",
            tier_id="T0",
            model_id="test-model",
            run_number=1,
            status="completed",
            duration_seconds=45.0,
            exit_code=0,
            tokens_input=10000,
            tokens_output=5000,
            cost_usd=0.50,
            api_calls=5,
            passed=True,
            impl_rate=0.85,
            letter_grade="B",
            pass_rate=1.0,
            cost_of_pass=0.50,
            composite_score=0.925,
        )

        # Timestamp should be auto-generated
        assert result.timestamp is not None
        assert result.timestamp.endswith("Z")

    def test_create_failed_run(self) -> None:
        """Test Create failed run."""
        result = create_run_result(
            test_id="001-test",
            tier_id="T0",
            model_id="test-model",
            run_number=1,
            status="failed",
            duration_seconds=10.0,
            exit_code=1,
            tokens_input=5000,
            tokens_output=1000,
            cost_usd=0.10,
            api_calls=2,
            passed=False,
            impl_rate=0.2,
            letter_grade="F",
            pass_rate=0.0,
            cost_of_pass=float("inf"),
            composite_score=0.1,
        )

        assert result.execution.status == "failed"
        assert result.judgment.passed is False
        assert result.grading.pass_rate == 0.0
