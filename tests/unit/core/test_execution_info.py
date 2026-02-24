"""Tests for ExecutionInfo hierarchy (Pydantic models)."""

import pytest
from pydantic import ValidationError

from scylla.core.results import ExecutionInfoBase
from scylla.executor.runner import ExecutorExecutionInfo
from scylla.reporting.result import ReportingExecutionInfo


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

    def test_negative_exit_code(self) -> None:
        """Support negative exit codes (e.g., killed by signal)."""
        info = ExecutionInfoBase(
            exit_code=-9,
            duration_seconds=2.5,
        )
        assert info.exit_code == -9

    def test_zero_duration(self) -> None:
        """Support zero duration (very fast execution)."""
        info = ExecutionInfoBase(
            exit_code=0,
            duration_seconds=0.0,
        )
        assert info.duration_seconds == 0.0

    def test_immutability(self) -> None:
        """Test that instances are frozen (immutable)."""
        info = ExecutionInfoBase(exit_code=0, duration_seconds=10.0)
        with pytest.raises(ValidationError):
            info.exit_code = 1

    def test_model_dump(self) -> None:
        """Test Pydantic serialization."""
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
        """Test model equality."""
        info1 = ExecutionInfoBase(exit_code=0, duration_seconds=10.0, timed_out=False)
        info2 = ExecutionInfoBase(exit_code=0, duration_seconds=10.0, timed_out=False)
        info3 = ExecutionInfoBase(exit_code=1, duration_seconds=10.0, timed_out=False)

        assert info1 == info2
        assert info1 != info3


class TestExecutorExecutionInfo:
    """Tests for ExecutorExecutionInfo (executor/runner.py)."""

    def test_construction_basic(self) -> None:
        """Basic construction with container-specific fields."""
        info = ExecutorExecutionInfo(
            container_id="abc123",
            exit_code=0,
            duration_seconds=10.5,
            stdout="Success",
            stderr="",
            timed_out=False,
            started_at="2024-01-01T00:00:00Z",
            ended_at="2024-01-01T00:00:10Z",
        )
        assert info.container_id == "abc123"
        assert info.exit_code == 0
        assert info.duration_seconds == 10.5
        assert info.stdout == "Success"
        assert info.stderr == ""
        assert info.timed_out is False
        assert info.started_at == "2024-01-01T00:00:00Z"
        assert info.ended_at == "2024-01-01T00:00:10Z"

    def test_inheritance_from_base(self) -> None:
        """Test that ExecutorExecutionInfo inherits from ExecutionInfoBase."""
        info = ExecutorExecutionInfo(
            container_id="abc123",
            exit_code=0,
            duration_seconds=10.5,
        )
        assert isinstance(info, ExecutionInfoBase)

    def test_optional_fields(self) -> None:
        """Test that optional fields have defaults."""
        info = ExecutorExecutionInfo(
            container_id="abc123",
            exit_code=0,
            duration_seconds=10.5,
        )
        assert info.stdout == ""
        assert info.stderr == ""
        assert info.timed_out is False
        assert info.started_at == ""
        assert info.ended_at == ""

    def test_model_dump(self) -> None:
        """Test Pydantic serialization."""
        info = ExecutorExecutionInfo(
            container_id="abc123",
            exit_code=0,
            duration_seconds=10.5,
            stdout="Success",
        )
        data = info.model_dump()
        assert data["container_id"] == "abc123"
        assert data["exit_code"] == 0
        assert data["duration_seconds"] == 10.5
        assert data["stdout"] == "Success"
        assert "stderr" in data
        assert "timed_out" in data


class TestReportingExecutionInfo:
    """Tests for ReportingExecutionInfo (reporting/result.py)."""

    def test_construction_basic(self) -> None:
        """Basic construction with status field."""
        info = ReportingExecutionInfo(
            status="completed",
            exit_code=0,
            duration_seconds=10.5,
            timed_out=False,
        )
        assert info.status == "completed"
        assert info.exit_code == 0
        assert info.duration_seconds == 10.5
        assert info.timed_out is False

    def test_inheritance_from_base(self) -> None:
        """Test that ReportingExecutionInfo inherits from ExecutionInfoBase."""
        info = ReportingExecutionInfo(
            status="completed",
            exit_code=0,
            duration_seconds=10.5,
        )
        assert isinstance(info, ExecutionInfoBase)

    def test_status_field_required(self) -> None:
        """Test that status field is required."""
        with pytest.raises(ValidationError):
            ReportingExecutionInfo(  # type: ignore
                exit_code=0,
                duration_seconds=10.5,
            )

    def test_model_dump(self) -> None:
        """Test Pydantic serialization."""
        info = ReportingExecutionInfo(
            status="completed",
            exit_code=0,
            duration_seconds=10.5,
        )
        data = info.model_dump()
        assert data["status"] == "completed"
        assert data["exit_code"] == 0
        assert data["duration_seconds"] == 10.5
        assert "timed_out" in data


class TestBackwardCompatibility:
    """Tests for backward compatibility via type aliases."""

    def test_reporting_type_alias(self) -> None:
        """Test that ExecutionInfo alias works in reporting module."""
        from scylla.reporting.result import ExecutionInfo

        # Should be the same as ReportingExecutionInfo
        info = ExecutionInfo(
            status="completed",
            exit_code=0,
            duration_seconds=10.5,
        )
        assert isinstance(info, ReportingExecutionInfo)
        assert isinstance(info, ExecutionInfoBase)


class TestInheritanceHierarchy:
    """Tests for the ExecutionInfo inheritance hierarchy."""

    def test_executor_is_execution_info_base(self) -> None:
        """Test ExecutorExecutionInfo is an instance of ExecutionInfoBase."""
        info = ExecutorExecutionInfo(
            container_id="abc123",
            exit_code=0,
            duration_seconds=10.5,
        )
        assert isinstance(info, ExecutionInfoBase)

    def test_reporting_is_execution_info_base(self) -> None:
        """Test ReportingExecutionInfo is an instance of ExecutionInfoBase."""
        info = ReportingExecutionInfo(
            status="completed",
            exit_code=0,
            duration_seconds=10.5,
        )
        assert isinstance(info, ExecutionInfoBase)

    def test_base_fields_accessible_in_subtypes(self) -> None:
        """Test that base fields are accessible in all subtypes."""
        executor_info = ExecutorExecutionInfo(
            container_id="abc123",
            exit_code=0,
            duration_seconds=10.5,
        )
        reporting_info = ReportingExecutionInfo(
            status="completed",
            exit_code=0,
            duration_seconds=10.5,
        )

        # All subtypes should have base fields
        assert executor_info.exit_code == 0
        assert executor_info.duration_seconds == 10.5
        assert executor_info.timed_out is False

        assert reporting_info.exit_code == 0
        assert reporting_info.duration_seconds == 10.5
        assert reporting_info.timed_out is False
