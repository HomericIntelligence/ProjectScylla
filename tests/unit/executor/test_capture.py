"""Tests for log and metrics capture.

Python justification: Required for pytest testing framework.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scylla.executor.capture import (
    ExecutionMetrics,
    LogCapture,
    StreamingCapture,
    aggregate_metrics,
    load_metrics,
)


class TestExecutionMetrics:
    """Tests for ExecutionMetrics model."""

    def test_default_values(self) -> None:
        """Test default metric values."""
        metrics = ExecutionMetrics()
        assert metrics.tokens_input == 0
        assert metrics.tokens_output == 0
        assert metrics.tokens_total == 0
        assert metrics.cost_usd == 0.0
        assert metrics.api_calls == 0
        assert metrics.exit_code == 0
        assert metrics.error is None

    def test_calculate_totals(self) -> None:
        """Test token total calculation."""
        metrics = ExecutionMetrics(tokens_input=100, tokens_output=50)
        metrics.calculate_totals()
        assert metrics.tokens_total == 150

    def test_with_values(self) -> None:
        """Test creating metrics with values."""
        metrics = ExecutionMetrics(
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.05,
            api_calls=3,
            duration_seconds=60.5,
            exit_code=0,
        )
        assert metrics.tokens_input == 1000
        assert metrics.cost_usd == 0.05
        assert metrics.duration_seconds == 60.5


class TestLogCapture:
    """Tests for LogCapture class."""

    def test_initialization(self) -> None:
        """Test LogCapture initialization."""
        with TemporaryDirectory() as tmpdir:
            capture = LogCapture(Path(tmpdir))
            assert capture.stdout_path == Path(tmpdir) / "stdout.log"
            assert capture.stderr_path == Path(tmpdir) / "stderr.log"
            assert capture.agent_log_path == Path(tmpdir) / "agent.log"
            assert capture.metrics_path == Path(tmpdir) / "metrics.json"

    def test_start_creates_directory(self) -> None:
        """Test that start creates output directory."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "logs"
            capture = LogCapture(output_dir)
            capture.start()
            capture.stop()
            assert output_dir.exists()

    def test_write_stdout(self) -> None:
        """Test writing to stdout log."""
        with TemporaryDirectory() as tmpdir:
            capture = LogCapture(Path(tmpdir))
            capture.start()
            capture.write_stdout("Hello\n")
            capture.write_stdout("World\n")
            capture.stop()

            content = capture.stdout_path.read_text()
            assert content == "Hello\nWorld\n"

    def test_write_stderr(self) -> None:
        """Test writing to stderr log."""
        with TemporaryDirectory() as tmpdir:
            capture = LogCapture(Path(tmpdir))
            capture.start()
            capture.write_stderr("Error occurred\n")
            capture.stop()

            content = capture.stderr_path.read_text()
            assert content == "Error occurred\n"

    def test_write_agent_log(self) -> None:
        """Test writing to agent log."""
        with TemporaryDirectory() as tmpdir:
            capture = LogCapture(Path(tmpdir))
            capture.start()
            capture.write_agent_log("Agent action: read file\n")
            capture.stop()

            content = capture.agent_log_path.read_text()
            assert content == "Agent action: read file\n"

    def test_stop_writes_metrics(self) -> None:
        """Test that stop writes metrics.json."""
        with TemporaryDirectory() as tmpdir:
            capture = LogCapture(Path(tmpdir))
            capture.start()
            metrics = capture.stop(
                exit_code=0,
                tokens_input=100,
                tokens_output=50,
                cost_usd=0.01,
                api_calls=2,
            )

            assert capture.metrics_path.exists()
            assert metrics.tokens_input == 100
            assert metrics.tokens_output == 50
            assert metrics.tokens_total == 150
            assert metrics.cost_usd == 0.01
            assert metrics.api_calls == 2

    def test_duration_calculated(self) -> None:
        """Test that duration is calculated."""
        with TemporaryDirectory() as tmpdir:
            capture = LogCapture(Path(tmpdir))
            capture.start()
            # Small delay for measurable duration
            metrics = capture.stop()

            assert metrics.duration_seconds >= 0
            assert metrics.started_at != ""
            assert metrics.ended_at != ""

    def test_update_metrics(self) -> None:
        """Test updating metrics incrementally."""
        with TemporaryDirectory() as tmpdir:
            capture = LogCapture(Path(tmpdir))
            capture.start()

            capture.update_metrics(tokens_input=50)
            capture.update_metrics(tokens_input=50, tokens_output=25)
            capture.update_metrics(api_calls=1)
            capture.update_metrics(api_calls=1, cost_usd=0.01)

            metrics = capture.get_metrics()
            assert metrics.tokens_input == 100
            assert metrics.tokens_output == 25
            assert metrics.api_calls == 2
            assert metrics.cost_usd == 0.01

            capture.stop()

    def test_error_capture(self) -> None:
        """Test capturing error information."""
        with TemporaryDirectory() as tmpdir:
            capture = LogCapture(Path(tmpdir))
            capture.start()
            metrics = capture.stop(
                exit_code=1,
                error="Connection refused",
            )

            assert metrics.exit_code == 1
            assert metrics.error == "Connection refused"


class TestStreamingCapture:
    """Tests for StreamingCapture context manager."""

    def test_context_manager_basic(self) -> None:
        """Test basic context manager usage."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with StreamingCapture(output_dir) as capture:
                capture.write_stdout("output\n")
                capture.write_stderr("error\n")

            assert (output_dir / "stdout.log").exists()
            assert (output_dir / "stderr.log").exists()
            assert (output_dir / "metrics.json").exists()

    def test_context_manager_with_exception(self) -> None:
        """Test context manager handles exceptions."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with pytest.raises(ValueError):
                with StreamingCapture(output_dir) as capture:
                    capture.write_stdout("before error\n")
                    raise ValueError("Test error")

            # Metrics should still be written with error info
            metrics = load_metrics(output_dir / "metrics.json")
            assert metrics is not None
            assert metrics.exit_code == 1
            assert "Test error" in (metrics.error or "")

    def test_set_exit_code(self) -> None:
        """Test setting exit code manually."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with StreamingCapture(output_dir) as capture:
                capture.set_exit_code(42)

            metrics = load_metrics(output_dir / "metrics.json")
            assert metrics is not None
            assert metrics.exit_code == 42

    def test_update_metrics_in_context(self) -> None:
        """Test updating metrics within context."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with StreamingCapture(output_dir) as capture:
                capture.update_metrics(tokens_input=100)
                capture.update_metrics(tokens_output=50)
                capture.update_metrics(cost_usd=0.05)

            metrics = load_metrics(output_dir / "metrics.json")
            assert metrics is not None
            assert metrics.tokens_input == 100
            assert metrics.tokens_output == 50
            assert metrics.cost_usd == pytest.approx(0.05)


class TestLoadMetrics:
    """Tests for load_metrics function."""

    def test_load_valid_metrics(self) -> None:
        """Test loading valid metrics file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "metrics.json"
            data = {
                "tokens_input": 100,
                "tokens_output": 50,
                "tokens_total": 150,
                "cost_usd": 0.05,
                "api_calls": 3,
                "duration_seconds": 30.5,
                "exit_code": 0,
                "error": None,
                "started_at": "2024-01-01T00:00:00",
                "ended_at": "2024-01-01T00:00:30",
            }
            path.write_text(json.dumps(data))

            metrics = load_metrics(path)
            assert metrics is not None
            assert metrics.tokens_input == 100
            assert metrics.cost_usd == 0.05

    def test_load_nonexistent_file(self) -> None:
        """Test loading from nonexistent file."""
        result = load_metrics(Path("/nonexistent/metrics.json"))
        assert result is None

    def test_load_invalid_json(self) -> None:
        """Test loading invalid JSON file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "metrics.json"
            path.write_text("not valid json")

            result = load_metrics(path)
            assert result is None


class TestAggregateMetrics:
    """Tests for aggregate_metrics function."""

    def test_empty_list(self) -> None:
        """Test aggregating empty list."""
        result = aggregate_metrics([])
        assert result.tokens_input == 0
        assert result.cost_usd == 0.0

    def test_single_metrics(self) -> None:
        """Test aggregating single metrics."""
        metrics = ExecutionMetrics(
            tokens_input=100,
            tokens_output=50,
            cost_usd=0.05,
            api_calls=3,
            duration_seconds=30.0,
        )
        result = aggregate_metrics([metrics])
        assert result.tokens_input == 100
        assert result.cost_usd == 0.05

    def test_multiple_metrics(self) -> None:
        """Test aggregating multiple metrics."""
        metrics_list = [
            ExecutionMetrics(
                tokens_input=100,
                tokens_output=50,
                cost_usd=0.05,
                api_calls=3,
                duration_seconds=30.0,
                started_at="2024-01-01T00:00:00",
                ended_at="2024-01-01T00:00:30",
            ),
            ExecutionMetrics(
                tokens_input=200,
                tokens_output=100,
                cost_usd=0.10,
                api_calls=5,
                duration_seconds=45.0,
                started_at="2024-01-01T00:01:00",
                ended_at="2024-01-01T00:01:45",
            ),
            ExecutionMetrics(
                tokens_input=150,
                tokens_output=75,
                cost_usd=0.07,
                api_calls=4,
                duration_seconds=35.0,
                started_at="2024-01-01T00:02:00",
                ended_at="2024-01-01T00:02:35",
            ),
        ]

        result = aggregate_metrics(metrics_list)
        assert result.tokens_input == 450
        assert result.tokens_output == 225
        assert result.tokens_total == 675
        assert result.cost_usd == pytest.approx(0.22)
        assert result.api_calls == 12
        assert result.duration_seconds == pytest.approx(110.0)
        assert result.started_at == "2024-01-01T00:00:00"
        assert result.ended_at == "2024-01-01T00:02:35"

    def test_aggregation_with_errors(self) -> None:
        """Test aggregation with failed runs."""
        metrics_list = [
            ExecutionMetrics(exit_code=0),
            ExecutionMetrics(exit_code=1),
            ExecutionMetrics(exit_code=0),
            ExecutionMetrics(exit_code=1),
        ]

        result = aggregate_metrics(metrics_list)
        assert result.exit_code == 1
        assert "2 of 4" in (result.error or "")
