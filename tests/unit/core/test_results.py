"""Tests for scylla.core.results module."""

import pytest
from pydantic import ValidationError

from scylla.core.results import ExecutionInfoBase


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
            info.exit_code = 1

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
