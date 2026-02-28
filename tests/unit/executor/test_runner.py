"""Tests for test runner orchestration."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from scylla.executor.runner import (
    EvalRunner,
    EvalSummary,
    ExecutionState,
    ExecutorExecutionInfo,
    ExecutorRunResult,
    JudgmentResult,
    RunnerConfig,
    RunnerError,
    RunStatus,
    TierSummary,
    calculate_wilson_ci,
    load_state,
    save_state,
)


class TestCalculateWilsonCI:
    """Tests for Wilson score confidence interval calculation."""

    def test_zero_runs(self) -> None:
        """Test CI with zero runs."""
        low, high = calculate_wilson_ci(0, 0)
        assert low == 0.0
        assert high == 0.0

    def test_all_pass(self) -> None:
        """Test CI when all runs pass."""
        low, high = calculate_wilson_ci(10, 10)
        assert low > 0.6  # Should be high
        assert high == 1.0

    def test_all_fail(self) -> None:
        """Test CI when all runs fail."""
        low, high = calculate_wilson_ci(0, 10)
        assert low == 0.0
        assert high < 0.4  # Should be low

    def test_half_pass(self) -> None:
        """Test CI when half pass."""
        low, high = calculate_wilson_ci(5, 10)
        assert low < 0.5
        assert high > 0.5
        assert low > 0.2
        assert high < 0.8

    def test_single_run_pass(self) -> None:
        """Test CI with single passing run."""
        low, high = calculate_wilson_ci(1, 1)
        assert low > 0.0
        assert high == 1.0


class TestExecutionState:
    """Tests for execution state management."""

    def test_new_state(self) -> None:
        """Test creating a new state."""
        state = ExecutionState(test_id="test-001")
        assert state.test_id == "test-001"
        assert state.completed_runs == {}

    def test_mark_run_completed(self) -> None:
        """Test marking runs as completed."""
        state = ExecutionState(test_id="test-001")
        state.mark_run_completed("T0", "model-a", 1)
        state.mark_run_completed("T0", "model-a", 2)
        state.mark_run_completed("T1", "model-a", 1)

        assert state.is_run_completed("T0", "model-a", 1)
        assert state.is_run_completed("T0", "model-a", 2)
        assert state.is_run_completed("T1", "model-a", 1)
        assert not state.is_run_completed("T0", "model-a", 3)
        assert not state.is_run_completed("T2", "model-a", 1)

    def test_duplicate_mark(self) -> None:
        """Test that duplicate marks don't create duplicates."""
        state = ExecutionState(test_id="test-001")
        state.mark_run_completed("T0", "model-a", 1)
        state.mark_run_completed("T0", "model-a", 1)

        assert state.completed_runs["T0"]["model-a"].count(1) == 1


class TestSaveLoadState:
    """Tests for state persistence."""

    def test_save_and_load(self) -> None:
        """Test saving and loading state."""
        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"

            state = ExecutionState(
                test_id="test-001",
                started_at="2024-01-01T00:00:00",
            )
            state.mark_run_completed("T0", "model-a", 1)
            state.mark_run_completed("T0", "model-a", 2)

            save_state(state, state_path)
            loaded = load_state(state_path)

            assert loaded is not None
            assert loaded.test_id == "test-001"
            assert loaded.started_at == "2024-01-01T00:00:00"
            assert loaded.is_run_completed("T0", "model-a", 1)
            assert loaded.is_run_completed("T0", "model-a", 2)

    def test_load_nonexistent(self) -> None:
        """Test loading from nonexistent file."""
        result = load_state(Path("/nonexistent/path/state.json"))
        assert result is None

    def test_atomic_write(self) -> None:
        """Test that save uses atomic write pattern."""
        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            temp_path = state_path.with_suffix(".tmp")

            state = ExecutionState(test_id="test-001")
            save_state(state, state_path)

            # Temp file should not exist after save
            assert not temp_path.exists()
            assert state_path.exists()


class TestExecutorRunResult:
    """Tests for run result model."""

    def test_passed_result(self) -> None:
        """Test creating a passed result."""
        result = ExecutorRunResult(
            run_number=1,
            status=RunStatus.PASSED,
            execution_info=ExecutorExecutionInfo(
                container_id="container-1",
                exit_code=0,
            ),
            judgment=JudgmentResult(passed=True, score=1.0),
        )
        assert result.status == RunStatus.PASSED
        assert result.judgment is not None
        assert result.judgment.passed

    def test_failed_result(self) -> None:
        """Test creating a failed result."""
        result = ExecutorRunResult(
            run_number=2,
            status=RunStatus.FAILED,
            judgment=JudgmentResult(passed=False, score=0.0),
        )
        assert result.status == RunStatus.FAILED

    def test_error_result(self) -> None:
        """Test creating an error result."""
        result = ExecutorRunResult(
            run_number=3,
            status=RunStatus.ERROR,
            error_message="Connection failed",
        )
        assert result.status == RunStatus.ERROR
        assert result.error_message == "Connection failed"


class TestTierSummary:
    """Tests for tier summary model."""

    def test_empty_summary(self) -> None:
        """Test creating an empty summary."""
        summary = TierSummary(
            tier_id="T0",
            model="model-a",
            total_runs=0,
        )
        assert summary.pass_rate == 0.0

    def test_summary_with_runs(self) -> None:
        """Test summary with runs."""
        summary = TierSummary(
            tier_id="T0",
            model="model-a",
            total_runs=10,
            passed_runs=7,
            failed_runs=3,
            pass_rate=0.7,
            pass_rate_ci_low=0.4,
            pass_rate_ci_high=0.9,
        )
        assert summary.pass_rate == 0.7
        assert summary.total_runs == 10


class TestRunnerConfig:
    """Tests for runner configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RunnerConfig()
        assert config.runs_per_tier == 10
        assert config.min_successful_runs == 5
        assert not config.parallel
        assert config.timeout_seconds == 3600
        assert config.max_retries == 6

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = RunnerConfig(
            runs_per_tier=20,
            parallel=True,
            max_parallel_workers=8,
        )
        assert config.runs_per_tier == 20
        assert config.parallel
        assert config.max_parallel_workers == 8


class TestTestRunner:
    """Tests for TestRunner class."""

    @pytest.fixture
    def mock_docker(self) -> MagicMock:
        """Create a mock Docker executor."""
        mock = MagicMock()
        mock.get_api_keys_from_env.return_value = {}
        mock.run.return_value = MagicMock(
            container_id="test-container",
            exit_code=0,
            stdout="success",
            stderr="",
            timed_out=False,
        )
        return mock

    @pytest.fixture
    def mock_tier_loader(self) -> MagicMock:
        """Create a mock tier config loader."""
        mock = MagicMock()
        mock.get_tier_ids.return_value = ["T0", "T1"]
        mock.get_tier.return_value = MagicMock(
            tier_id="T0",
            name="Vanilla",
            tools_enabled=None,
            delegation_enabled=None,
        )
        return mock

    def test_runner_initialization(
        self, mock_docker: MagicMock, mock_tier_loader: MagicMock
    ) -> None:
        """Test runner initialization."""
        runner = EvalRunner(mock_docker, mock_tier_loader)
        assert runner.docker == mock_docker
        assert runner.tier_loader == mock_tier_loader

    def test_run_test_requires_models(
        self, mock_docker: MagicMock, mock_tier_loader: MagicMock
    ) -> None:
        """Test that run_test requires models."""
        runner = EvalRunner(mock_docker, mock_tier_loader)
        with pytest.raises(RunnerError, match="At least one model"):
            runner.run_test(test_id="test-001", models=[])

    def test_run_test_basic(self, mock_docker: MagicMock, mock_tier_loader: MagicMock) -> None:
        """Test basic test execution."""
        config = RunnerConfig(runs_per_tier=2)
        runner = EvalRunner(mock_docker, mock_tier_loader, config)

        summary = runner.run_test(
            test_id="test-001",
            tiers=["T0"],
            models=["model-a"],
        )

        assert summary.test_id == "test-001"
        assert "T0" in summary.tiers
        assert "model-a" in summary.tiers["T0"]
        assert summary.status == "completed"

    def test_run_test_with_resume(
        self, mock_docker: MagicMock, mock_tier_loader: MagicMock
    ) -> None:
        """Test resuming from state file."""
        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"

            # Create initial state
            state = ExecutionState(test_id="test-001")
            state.mark_run_completed("T0", "model-a", 1)
            save_state(state, state_path)

            config = RunnerConfig(runs_per_tier=2)
            runner = EvalRunner(mock_docker, mock_tier_loader, config)

            runner.run_test(
                test_id="test-001",
                tiers=["T0"],
                models=["model-a"],
                resume_from=state_path,
            )

            # Only 1 run should have been executed (run 2)
            assert mock_docker.run.call_count == 1

    def test_custom_judge(self, mock_docker: MagicMock, mock_tier_loader: MagicMock) -> None:
        """Test setting custom judge function."""
        config = RunnerConfig(runs_per_tier=1)
        runner = EvalRunner(mock_docker, mock_tier_loader, config)

        custom_judgment = JudgmentResult(
            passed=True,
            score=0.95,
            reasoning="Custom evaluation",
        )
        runner.set_judge(lambda _: custom_judgment)

        summary = runner.run_test(
            test_id="test-001",
            tiers=["T0"],
            models=["model-a"],
        )

        tier_summary = summary.tiers["T0"]["model-a"]
        assert tier_summary.runs[0].judgment is not None
        assert tier_summary.runs[0].judgment.score == 0.95


class TestTestRunnerAggregation:
    """Tests for result aggregation."""

    @pytest.fixture
    def mock_docker(self) -> MagicMock:
        """Create a mock Docker executor."""
        mock = MagicMock()
        mock.get_api_keys_from_env.return_value = {}
        return mock

    @pytest.fixture
    def mock_tier_loader(self) -> MagicMock:
        """Create a mock tier config loader."""
        mock = MagicMock()
        mock.get_tier_ids.return_value = ["T0"]
        mock.get_tier.return_value = MagicMock(
            tier_id="T0",
            name="Vanilla",
            tools_enabled=None,
            delegation_enabled=None,
        )
        return mock

    def test_aggregation_all_pass(
        self, mock_docker: MagicMock, mock_tier_loader: MagicMock
    ) -> None:
        """Test aggregation when all runs pass."""
        mock_docker.run.return_value = MagicMock(
            container_id="test-container",
            exit_code=0,
            stdout="success",
            stderr="",
            timed_out=False,
        )

        config = RunnerConfig(runs_per_tier=5)
        runner = EvalRunner(mock_docker, mock_tier_loader, config)

        summary = runner.run_test(
            test_id="test-001",
            tiers=["T0"],
            models=["model-a"],
        )

        tier_summary = summary.tiers["T0"]["model-a"]
        assert tier_summary.passed_runs == 5
        assert tier_summary.failed_runs == 0
        assert tier_summary.pass_rate == 1.0

    def test_aggregation_mixed_results(
        self, mock_docker: MagicMock, mock_tier_loader: MagicMock
    ) -> None:
        """Test aggregation with mixed pass/fail from judge."""
        call_count = [0]

        def mock_run(_: MagicMock) -> MagicMock:
            call_count[0] += 1
            # All runs complete successfully (exit_code=0)
            return MagicMock(
                container_id=f"container-{call_count[0]}",
                exit_code=0,
                stdout="output",
                stderr="",
                timed_out=False,
            )

        mock_docker.run.side_effect = mock_run

        config = RunnerConfig(runs_per_tier=5)
        runner = EvalRunner(mock_docker, mock_tier_loader, config)

        # Custom judge that fails some runs
        judge_count = [0]

        def custom_judge(_: ExecutorExecutionInfo) -> JudgmentResult:
            judge_count[0] += 1
            passed = judge_count[0] <= 3  # First 3 pass, next 2 fail
            return JudgmentResult(
                passed=passed,
                score=1.0 if passed else 0.0,
            )

        runner.set_judge(custom_judge)

        summary = runner.run_test(
            test_id="test-001",
            tiers=["T0"],
            models=["model-a"],
        )

        tier_summary = summary.tiers["T0"]["model-a"]
        assert tier_summary.passed_runs == 3
        assert tier_summary.failed_runs == 2
        assert tier_summary.pass_rate == 0.6


class TestTestRunnerParallel:
    """Tests for parallel execution."""

    @pytest.fixture
    def mock_docker(self) -> MagicMock:
        """Create a mock Docker executor."""
        mock = MagicMock()
        mock.get_api_keys_from_env.return_value = {}
        mock.run.return_value = MagicMock(
            container_id="test-container",
            exit_code=0,
            stdout="success",
            stderr="",
            timed_out=False,
        )
        return mock

    @pytest.fixture
    def mock_tier_loader(self) -> MagicMock:
        """Create a mock tier config loader."""
        mock = MagicMock()
        mock.get_tier_ids.return_value = ["T0"]
        mock.get_tier.return_value = MagicMock(
            tier_id="T0",
            name="Vanilla",
            tools_enabled=None,
            delegation_enabled=None,
        )
        return mock

    def test_parallel_execution(self, mock_docker: MagicMock, mock_tier_loader: MagicMock) -> None:
        """Test parallel execution mode."""
        config = RunnerConfig(runs_per_tier=4, parallel=True, max_parallel_workers=2)
        runner = EvalRunner(mock_docker, mock_tier_loader, config)

        summary = runner.run_test(
            test_id="test-001",
            tiers=["T0"],
            models=["model-a"],
        )

        assert mock_docker.run.call_count == 4
        tier_summary = summary.tiers["T0"]["model-a"]
        assert tier_summary.total_runs == 4


class TestFinalizeTestSummaryGuard:
    """Tests for the _finalize_test_summary RuntimeError guard (issue #1143)."""

    def test_raises_runtime_error_when_state_is_none_and_state_file_configured(
        self, tmp_path: Path
    ) -> None:
        """_finalize_test_summary raises RuntimeError when _state is None but state_file is set."""
        mock_docker = MagicMock()
        mock_docker.get_api_keys_from_env.return_value = {}
        mock_tier_loader = MagicMock()

        config = RunnerConfig(state_file=tmp_path / "state.json")
        runner = EvalRunner(mock_docker, mock_tier_loader, config)
        # _state is None by default — do not call _create_test_summary
        assert runner._state is None

        summary = EvalSummary(test_id="test-001", started_at="2026-01-01T00:00:00+00:00")
        with pytest.raises(
            RuntimeError, match="_state must be initialized before finalizing test summary"
        ):
            runner._finalize_test_summary(summary)
