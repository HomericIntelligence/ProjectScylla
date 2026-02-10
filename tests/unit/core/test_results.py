"""Tests for scylla.core.results module.

Python justification: Required for pytest testing framework.
"""

from scylla.core.results import BaseExecutionInfo, BaseRunMetrics, BaseRunResult


class TestBaseExecutionInfo:
    """Tests for BaseExecutionInfo dataclass."""

    def test_construction_success(self) -> None:
        """Basic construction with valid parameters."""
        info = BaseExecutionInfo(
            exit_code=0,
            duration_seconds=10.5,
            timed_out=False,
        )
        assert info.exit_code == 0
        assert info.duration_seconds == 10.5
        assert info.timed_out is False

    def test_construction_failure(self) -> None:
        """Construction with failure exit code."""
        info = BaseExecutionInfo(
            exit_code=1,
            duration_seconds=5.0,
            timed_out=False,
        )
        assert info.exit_code == 1
        assert info.duration_seconds == 5.0

    def test_construction_timeout(self) -> None:
        """Construction with timeout flag."""
        info = BaseExecutionInfo(
            exit_code=124,
            duration_seconds=30.0,
            timed_out=True,
        )
        assert info.exit_code == 124
        assert info.duration_seconds == 30.0
        assert info.timed_out is True

    def test_timed_out_default_false(self) -> None:
        """timed_out should default to False if not specified."""
        info = BaseExecutionInfo(exit_code=0, duration_seconds=1.0)
        assert info.timed_out is False

    def test_negative_exit_code(self) -> None:
        """Support negative exit codes (e.g., killed by signal)."""
        info = BaseExecutionInfo(
            exit_code=-9,
            duration_seconds=2.5,
        )
        assert info.exit_code == -9

    def test_zero_duration(self) -> None:
        """Support zero duration (very fast execution)."""
        info = BaseExecutionInfo(
            exit_code=0,
            duration_seconds=0.0,
        )
        assert info.duration_seconds == 0.0

    def test_equality(self) -> None:
        """Test dataclass equality."""
        info1 = BaseExecutionInfo(exit_code=0, duration_seconds=10.0, timed_out=False)
        info2 = BaseExecutionInfo(exit_code=0, duration_seconds=10.0, timed_out=False)
        info3 = BaseExecutionInfo(exit_code=1, duration_seconds=10.0, timed_out=False)

        assert info1 == info2
        assert info1 != info3

    def test_repr(self) -> None:
        """Test string representation."""
        info = BaseExecutionInfo(exit_code=0, duration_seconds=10.5, timed_out=False)
        repr_str = repr(info)
        assert "BaseExecutionInfo" in repr_str
        assert "exit_code=0" in repr_str
        assert "duration_seconds=10.5" in repr_str


class TestBaseRunMetrics:
    """Tests for BaseRunMetrics dataclass."""

    def test_construction_basic(self) -> None:
        """Basic construction with valid parameters."""
        metrics = BaseRunMetrics(
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.05,
        )
        assert metrics.tokens_input == 1000
        assert metrics.tokens_output == 500
        assert metrics.cost_usd == 0.05

    def test_construction_zero_values(self) -> None:
        """Construction with zero values."""
        metrics = BaseRunMetrics(
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
        )
        assert metrics.tokens_input == 0
        assert metrics.tokens_output == 0
        assert metrics.cost_usd == 0.0

    def test_construction_large_values(self) -> None:
        """Construction with large token counts."""
        metrics = BaseRunMetrics(
            tokens_input=1_000_000,
            tokens_output=500_000,
            cost_usd=100.50,
        )
        assert metrics.tokens_input == 1_000_000
        assert metrics.tokens_output == 500_000
        assert metrics.cost_usd == 100.50

    def test_total_tokens_calculation(self) -> None:
        """Verify total tokens can be derived from input + output."""
        metrics = BaseRunMetrics(
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.05,
        )
        total = metrics.tokens_input + metrics.tokens_output
        assert total == 1500

    def test_equality(self) -> None:
        """Test dataclass equality."""
        metrics1 = BaseRunMetrics(tokens_input=1000, tokens_output=500, cost_usd=0.05)
        metrics2 = BaseRunMetrics(tokens_input=1000, tokens_output=500, cost_usd=0.05)
        metrics3 = BaseRunMetrics(tokens_input=2000, tokens_output=500, cost_usd=0.05)

        assert metrics1 == metrics2
        assert metrics1 != metrics3

    def test_repr(self) -> None:
        """Test string representation."""
        metrics = BaseRunMetrics(tokens_input=1000, tokens_output=500, cost_usd=0.05)
        repr_str = repr(metrics)
        assert "BaseRunMetrics" in repr_str
        assert "tokens_input=1000" in repr_str
        assert "tokens_output=500" in repr_str


class TestBaseRunResult:
    """Tests for BaseRunResult dataclass."""

    def test_construction_basic(self) -> None:
        """Basic construction with valid parameters."""
        result = BaseRunResult(
            run_number=1,
            cost_usd=0.05,
            duration_seconds=10.5,
        )
        assert result.run_number == 1
        assert result.cost_usd == 0.05
        assert result.duration_seconds == 10.5

    def test_construction_multiple_runs(self) -> None:
        """Construction with different run numbers."""
        result1 = BaseRunResult(run_number=1, cost_usd=0.05, duration_seconds=10.0)
        result2 = BaseRunResult(run_number=2, cost_usd=0.06, duration_seconds=11.0)
        result3 = BaseRunResult(run_number=10, cost_usd=0.10, duration_seconds=15.0)

        assert result1.run_number == 1
        assert result2.run_number == 2
        assert result3.run_number == 10

    def test_zero_cost(self) -> None:
        """Support zero cost (free tier, cached results, etc.)."""
        result = BaseRunResult(
            run_number=1,
            cost_usd=0.0,
            duration_seconds=10.0,
        )
        assert result.cost_usd == 0.0

    def test_zero_duration(self) -> None:
        """Support zero duration (cached/instant results)."""
        result = BaseRunResult(
            run_number=1,
            cost_usd=0.05,
            duration_seconds=0.0,
        )
        assert result.duration_seconds == 0.0

    def test_high_cost(self) -> None:
        """Support high cost values."""
        result = BaseRunResult(
            run_number=1,
            cost_usd=999.99,
            duration_seconds=1000.0,
        )
        assert result.cost_usd == 999.99

    def test_long_duration(self) -> None:
        """Support long duration values."""
        result = BaseRunResult(
            run_number=1,
            cost_usd=1.00,
            duration_seconds=3600.0,  # 1 hour
        )
        assert result.duration_seconds == 3600.0

    def test_equality(self) -> None:
        """Test dataclass equality."""
        result1 = BaseRunResult(run_number=1, cost_usd=0.05, duration_seconds=10.0)
        result2 = BaseRunResult(run_number=1, cost_usd=0.05, duration_seconds=10.0)
        result3 = BaseRunResult(run_number=2, cost_usd=0.05, duration_seconds=10.0)

        assert result1 == result2
        assert result1 != result3

    def test_repr(self) -> None:
        """Test string representation."""
        result = BaseRunResult(run_number=1, cost_usd=0.05, duration_seconds=10.5)
        repr_str = repr(result)
        assert "BaseRunResult" in repr_str
        assert "run_number=1" in repr_str
        assert "cost_usd=0.05" in repr_str


class TestComposedTypes:
    """Tests for composed usage of base types."""

    def test_result_with_execution_info_composition(self) -> None:
        """Test composing BaseRunResult with BaseExecutionInfo."""
        # This tests the pattern used in domain-specific types
        result = BaseRunResult(
            run_number=1,
            cost_usd=0.05,
            duration_seconds=10.5,
        )

        execution = BaseExecutionInfo(
            exit_code=0,
            duration_seconds=10.5,
            timed_out=False,
        )

        # Verify duration consistency
        assert result.duration_seconds == execution.duration_seconds

    def test_result_with_metrics_composition(self) -> None:
        """Test composing BaseRunResult with BaseRunMetrics."""
        result = BaseRunResult(
            run_number=1,
            cost_usd=0.05,
            duration_seconds=10.5,
        )

        metrics = BaseRunMetrics(
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.05,
        )

        # Verify cost consistency
        assert result.cost_usd == metrics.cost_usd

    def test_full_composition_pattern(self) -> None:
        """Test full composition of all three base types."""
        # Simulates the pattern used in reporting.result.py
        run_number = 1
        cost = 0.05
        duration = 10.5

        result = BaseRunResult(
            run_number=run_number,
            cost_usd=cost,
            duration_seconds=duration,
        )

        execution = BaseExecutionInfo(
            exit_code=0,
            duration_seconds=duration,
            timed_out=False,
        )

        metrics = BaseRunMetrics(
            tokens_input=1000,
            tokens_output=500,
            cost_usd=cost,
        )

        # Verify consistency across composed types
        assert result.run_number == run_number
        assert result.cost_usd == metrics.cost_usd
        assert result.duration_seconds == execution.duration_seconds
