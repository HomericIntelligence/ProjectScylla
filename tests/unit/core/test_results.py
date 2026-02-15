"""Tests for scylla.core.results module."""

import pytest
from pydantic import ValidationError

from scylla.core.results import BaseExecutionInfo, BaseRunMetrics, ExecutionInfoBase


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


class TestComposedTypes:
    """Tests for composed usage of base types."""

    def test_execution_info_composition(self) -> None:
        """Test composing execution info."""
        # This tests the pattern used in domain-specific types
        duration = 10.5

        execution = BaseExecutionInfo(
            exit_code=0,
            duration_seconds=duration,
            timed_out=False,
        )

        # Verify duration is captured
        assert execution.duration_seconds == duration

    def test_metrics_composition(self) -> None:
        """Test composing metrics."""
        cost = 0.05

        metrics = BaseRunMetrics(
            tokens_input=1000,
            tokens_output=500,
            cost_usd=cost,
        )

        # Verify cost is captured
        assert metrics.cost_usd == cost

    def test_full_composition_pattern(self) -> None:
        """Test full composition of execution info and metrics."""
        # Simulates the pattern used in reporting.result.py
        cost = 0.05
        duration = 10.5

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
        assert metrics.cost_usd == cost
        assert execution.duration_seconds == duration


class TestExecutionInfoBase:
    """Tests for ExecutionInfoBase Pydantic model."""

    def test_construction_success(self) -> None:
        """Basic construction with valid parameters."""
        info = ExecutionInfoBase(
            exit_code=0,
            duration_seconds=10.5,
            timed_out=False,
        )
        assert info.exit_code == 0
        assert info.duration_seconds == 10.5
        assert info.timed_out is False

    def test_construction_failure(self) -> None:
        """Construction with failure exit code."""
        info = ExecutionInfoBase(
            exit_code=1,
            duration_seconds=5.0,
            timed_out=False,
        )
        assert info.exit_code == 1
        assert info.duration_seconds == 5.0

    def test_construction_timeout(self) -> None:
        """Construction with timeout flag."""
        info = ExecutionInfoBase(
            exit_code=124,
            duration_seconds=30.0,
            timed_out=True,
        )
        assert info.exit_code == 124
        assert info.duration_seconds == 30.0
        assert info.timed_out is True

    def test_timed_out_default_false(self) -> None:
        """timed_out should default to False if not specified."""
        info = ExecutionInfoBase(exit_code=0, duration_seconds=1.0)
        assert info.timed_out is False

    def test_immutability(self) -> None:
        """Test that instances are frozen (immutable)."""
        info = ExecutionInfoBase(exit_code=0, duration_seconds=10.0)
        with pytest.raises(ValidationError):
            info.exit_code = 1  # type: ignore

    def test_model_dump(self) -> None:
        """Test Pydantic serialization with .model_dump()."""
        info = ExecutionInfoBase(
            exit_code=0,
            duration_seconds=10.5,
            timed_out=False,
        )
        data = info.model_dump()
        assert data == {
            "exit_code": 0,
            "duration_seconds": 10.5,
            "timed_out": False,
        }

    def test_equality(self) -> None:
        """Test Pydantic model equality."""
        info1 = ExecutionInfoBase(exit_code=0, duration_seconds=10.0, timed_out=False)
        info2 = ExecutionInfoBase(exit_code=0, duration_seconds=10.0, timed_out=False)
        info3 = ExecutionInfoBase(exit_code=1, duration_seconds=10.0, timed_out=False)

        assert info1 == info2
        assert info1 != info3


class TestBaseExecutionInfoBackwardCompatibility:
    """Tests for BaseExecutionInfo dataclass (deprecated, backward compatibility)."""

    def test_dataclass_still_works(self) -> None:
        """Test that legacy BaseExecutionInfo dataclass still works."""
        info = BaseExecutionInfo(
            exit_code=0,
            duration_seconds=10.5,
            timed_out=False,
        )
        assert info.exit_code == 0
        assert info.duration_seconds == 10.5
        assert info.timed_out is False

    def test_dataclass_and_pydantic_have_same_fields(self) -> None:
        """Test that dataclass and Pydantic model have the same core fields."""
        dataclass_info = BaseExecutionInfo(
            exit_code=0,
            duration_seconds=10.5,
            timed_out=False,
        )
        pydantic_info = ExecutionInfoBase(
            exit_code=0,
            duration_seconds=10.5,
            timed_out=False,
        )

        # Same values in same fields
        assert dataclass_info.exit_code == pydantic_info.exit_code
        assert dataclass_info.duration_seconds == pydantic_info.duration_seconds
        assert dataclass_info.timed_out == pydantic_info.timed_out
