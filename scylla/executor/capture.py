"""Log and metrics capture utilities for test execution.

This module provides utilities for capturing stdout, stderr, and metrics
during test execution in Docker containers.
file I/O (Mojo stdlib limitation - cannot capture stdout/stderr).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ExecutionMetrics(BaseModel):
    """Metrics captured during test execution.

    This model represents the metrics.json schema for recording
    token usage, cost, timing, and execution results.
    """

    tokens_input: int = Field(default=0, description="Input tokens consumed")
    tokens_output: int = Field(default=0, description="Output tokens generated")
    tokens_total: int = Field(default=0, description="Total tokens (input + output)")
    cost_usd: float = Field(default=0.0, description="Estimated cost in USD")
    api_calls: int = Field(default=0, description="Number of API calls made")
    duration_seconds: float = Field(default=0.0, description="Execution duration")
    exit_code: int = Field(default=0, description="Process exit code")
    error: str | None = Field(default=None, description="Error message if failed")
    started_at: str = Field(default="", description="ISO timestamp of start")
    ended_at: str = Field(default="", description="ISO timestamp of end")

    def calculate_totals(self) -> None:
        """Calculate derived fields."""
        self.tokens_total = self.tokens_input + self.tokens_output


@dataclass
class LogCapture:
    r"""Captures log output to files with streaming support.

    This class handles capturing stdout, stderr, and agent logs
    during test execution, writing to files in real-time.

    Example:
        >>> # Context manager (recommended)
        >>> with LogCapture(Path("/output")) as capture:
        ...     capture.write_stdout("output line\n")
        ...     capture.write_stderr("error line\n")

        >>> # Manual usage
        >>> capture = LogCapture(Path("/output"))
        >>> capture.start()
        >>> capture.write_stdout("output line\n")
        >>> metrics = capture.stop(exit_code=0)

    """

    output_dir: Path
    stdout_path: Path = field(init=False)
    stderr_path: Path = field(init=False)
    agent_log_path: Path = field(init=False)
    metrics_path: Path = field(init=False)
    _started_at: datetime | None = field(default=None, init=False)
    _ended_at: datetime | None = field(default=None, init=False)
    _stdout_file: Any = field(default=None, init=False)
    _stderr_file: Any = field(default=None, init=False)
    _agent_log_file: Any = field(default=None, init=False)
    _metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics, init=False)

    def __post_init__(self) -> None:
        """Initialize paths."""
        self.stdout_path = self.output_dir / "stdout.log"
        self.stderr_path = self.output_dir / "stderr.log"
        self.agent_log_path = self.output_dir / "agent.log"
        self.metrics_path = self.output_dir / "metrics.json"

    def __enter__(self) -> LogCapture:
        """Context manager entry.

        Returns:
            Self for use in with statement.

        """
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Exception traceback if raised.

        """
        error_msg = str(exc_val) if exc_val else None
        exit_code = 1 if exc_type else 0
        self.stop(exit_code=exit_code, error=error_msg)

    def start(self) -> None:
        """Start log capture session.

        Opens log files for writing and records start time.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._started_at = datetime.now(timezone.utc)
        self._metrics = ExecutionMetrics(started_at=self._started_at.isoformat())

        # Open files for streaming writes
        self._stdout_file = open(self.stdout_path, "w")
        self._stderr_file = open(self.stderr_path, "w")
        self._agent_log_file = open(self.agent_log_path, "w")

    def write_stdout(self, data: str) -> None:
        """Write data to stdout log.

        Args:
            data: Data to write (may include newlines).

        """
        if self._stdout_file:
            self._stdout_file.write(data)
            self._stdout_file.flush()

    def write_stderr(self, data: str) -> None:
        """Write data to stderr log.

        Args:
            data: Data to write (may include newlines).

        """
        if self._stderr_file:
            self._stderr_file.write(data)
            self._stderr_file.flush()

    def write_agent_log(self, data: str) -> None:
        """Write data to agent log.

        Args:
            data: Data to write (may include newlines).

        """
        if self._agent_log_file:
            self._agent_log_file.write(data)
            self._agent_log_file.flush()

    def stop(
        self,
        exit_code: int = 0,
        error: str | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_usd: float = 0.0,
        api_calls: int = 0,
    ) -> ExecutionMetrics:
        """Stop log capture and write metrics.

        Args:
            exit_code: Process exit code.
            error: Error message if execution failed.
            tokens_input: Input tokens consumed.
            tokens_output: Output tokens generated.
            cost_usd: Estimated cost in USD.
            api_calls: Number of API calls made.

        Returns:
            ExecutionMetrics with captured data.

        """
        self._ended_at = datetime.now(timezone.utc)

        # Close log files
        if self._stdout_file:
            self._stdout_file.close()
            self._stdout_file = None
        if self._stderr_file:
            self._stderr_file.close()
            self._stderr_file = None
        if self._agent_log_file:
            self._agent_log_file.close()
            self._agent_log_file = None

        # Calculate duration
        duration = 0.0
        if self._started_at and self._ended_at:
            duration = (self._ended_at - self._started_at).total_seconds()

        # Update metrics
        self._metrics.exit_code = exit_code
        self._metrics.error = error
        self._metrics.tokens_input = tokens_input
        self._metrics.tokens_output = tokens_output
        self._metrics.cost_usd = cost_usd
        self._metrics.api_calls = api_calls
        self._metrics.duration_seconds = duration
        self._metrics.ended_at = self._ended_at.isoformat()
        self._metrics.calculate_totals()

        # Write metrics.json
        self._write_metrics()

        return self._metrics

    def _write_metrics(self) -> None:
        """Write metrics to JSON file."""
        with open(self.metrics_path, "w") as f:
            json.dump(self._metrics.model_dump(), f, indent=2)

    def get_metrics(self) -> ExecutionMetrics:
        """Get current metrics state.

        Returns:
            Current ExecutionMetrics.

        """
        return self._metrics

    def update_metrics(
        self,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        cost_usd: float | None = None,
        api_calls: int | None = None,
    ) -> None:
        """Update metrics with new values.

        Args:
            tokens_input: Input tokens to add.
            tokens_output: Output tokens to add.
            cost_usd: Cost to add.
            api_calls: API calls to add.

        """
        if tokens_input is not None:
            self._metrics.tokens_input += tokens_input
        if tokens_output is not None:
            self._metrics.tokens_output += tokens_output
        if cost_usd is not None:
            self._metrics.cost_usd += cost_usd
        if api_calls is not None:
            self._metrics.api_calls += api_calls
        self._metrics.calculate_totals()


class StreamingCapture:
    r"""Context manager for streaming log capture.

    Provides a convenient context manager interface for capturing
    logs during test execution.

    Example:
        >>> with StreamingCapture(Path("/output")) as capture:
        ...     capture.write_stdout("output\n")
        ...     capture.write_stderr("error\n")
        >>> # metrics.json is written automatically on exit

    """

    def __init__(self, output_dir: Path) -> None:
        """Initialize streaming capture.

        Args:
            output_dir: Directory for log files.

        """
        self._capture = LogCapture(output_dir)
        self._exit_code = 0
        self._error: str | None = None

    def __enter__(self) -> StreamingCapture:
        """Enter context and start capture."""
        self._capture.start()
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> bool:
        """Exit context and stop capture."""
        if exc_val:
            self._error = str(exc_val)
            self._exit_code = 1

        # Get accumulated metrics before stopping
        current_metrics = self._capture.get_metrics()
        self._capture.stop(
            exit_code=self._exit_code,
            error=self._error,
            tokens_input=current_metrics.tokens_input,
            tokens_output=current_metrics.tokens_output,
            cost_usd=current_metrics.cost_usd,
            api_calls=current_metrics.api_calls,
        )
        return False  # Don't suppress exceptions

    def write_stdout(self, data: str) -> None:
        """Write to stdout log."""
        self._capture.write_stdout(data)

    def write_stderr(self, data: str) -> None:
        """Write to stderr log."""
        self._capture.write_stderr(data)

    def write_agent_log(self, data: str) -> None:
        """Write to agent log."""
        self._capture.write_agent_log(data)

    def update_metrics(
        self,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        cost_usd: float | None = None,
        api_calls: int | None = None,
    ) -> None:
        """Update execution metrics."""
        self._capture.update_metrics(
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            api_calls=api_calls,
        )

    def set_exit_code(self, code: int) -> None:
        """Set the exit code for metrics."""
        self._exit_code = code

    def set_error(self, error: str) -> None:
        """Set error message for metrics."""
        self._error = error


def load_metrics(path: Path) -> ExecutionMetrics | None:
    """Load metrics from JSON file.

    Args:
        path: Path to metrics.json file.

    Returns:
        ExecutionMetrics if file exists and is valid, None otherwise.

    """
    if not path.exists():
        return None

    try:
        with open(path) as f:
            data = json.load(f)
        return ExecutionMetrics.model_validate(data)
    except (json.JSONDecodeError, Exception):
        return None


def aggregate_metrics(metrics_list: list[ExecutionMetrics]) -> ExecutionMetrics:
    """Aggregate multiple execution metrics.

    Args:
        metrics_list: List of metrics to aggregate.

    Returns:
        Aggregated ExecutionMetrics with summed values.

    """
    if not metrics_list:
        return ExecutionMetrics()

    total = ExecutionMetrics()
    for m in metrics_list:
        total.tokens_input += m.tokens_input
        total.tokens_output += m.tokens_output
        total.cost_usd += m.cost_usd
        total.api_calls += m.api_calls
        total.duration_seconds += m.duration_seconds

    total.calculate_totals()
    total.started_at = metrics_list[0].started_at
    total.ended_at = metrics_list[-1].ended_at

    # Count errors
    errors = [m for m in metrics_list if m.exit_code != 0]
    if errors:
        total.exit_code = 1
        total.error = f"{len(errors)} of {len(metrics_list)} runs failed"

    return total
