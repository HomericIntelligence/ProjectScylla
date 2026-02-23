"""Unit tests for parallel_executor module.

Tests cover:
- RateLimitCoordinator: all methods and state transitions
- Race condition regression: _resume_event not cleared by worker
- Manager() cleanup via finally block
- run_tier_subtests_parallel: single-subtest path (no coordinator)
- WorkspaceManager.from_existing() usage in child process
- _run_subtest_in_process_safe: safe wrapper for worker exceptions
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from scylla.e2e.parallel_executor import RateLimitCoordinator
from scylla.e2e.rate_limit import RateLimitInfo

# ---------------------------------------------------------------------------
# RateLimitCoordinator tests
# ---------------------------------------------------------------------------


def _make_coordinator() -> RateLimitCoordinator:
    """Create a RateLimitCoordinator backed by threading primitives.

    Uses threading.Event (same API as multiprocessing Event proxy) and a
    plain dict (same API as multiprocessing dict proxy) instead of spinning
    up a real multiprocessing.Manager, which is expensive in the test suite.
    """
    mgr = MagicMock()
    mgr.Event.side_effect = threading.Event
    mgr.dict.return_value = {}
    return RateLimitCoordinator(mgr)


def _make_info(
    source: str = "agent",
    retry_after_seconds: float = 60.0,
    error_message: str = "rate limit exceeded",
    detected_at: str | None = None,
) -> RateLimitInfo:
    """Create a RateLimitInfo for testing."""
    return RateLimitInfo(
        source=source,
        retry_after_seconds=retry_after_seconds,
        error_message=error_message,
        detected_at=detected_at or datetime.now(timezone.utc).isoformat(),
    )


class TestRateLimitCoordinatorInitialState:
    """Tests for initial state of RateLimitCoordinator."""

    def test_not_paused_initially(self) -> None:
        """check_if_paused() returns False before any signal."""
        coordinator = _make_coordinator()
        assert coordinator.check_if_paused() is False

    def test_get_rate_limit_info_none_initially(self) -> None:
        """get_rate_limit_info() returns None before any signal."""
        coordinator = _make_coordinator()
        assert coordinator.get_rate_limit_info() is None

    def test_not_shutdown_initially(self) -> None:
        """is_shutdown_requested() returns False initially."""
        coordinator = _make_coordinator()
        assert coordinator.is_shutdown_requested() is False


class TestRateLimitCoordinatorSignalRateLimit:
    """Tests for signal_rate_limit() and subsequent state."""

    def test_signal_sets_paused(self) -> None:
        """After signal_rate_limit(), check_if_paused() returns True."""
        coordinator = _make_coordinator()
        info = _make_info()
        coordinator.signal_rate_limit(info)
        assert coordinator._pause_event.is_set()

    def test_signal_stores_rate_info(self) -> None:
        """After signal_rate_limit(), get_rate_limit_info() returns the stored info."""
        coordinator = _make_coordinator()
        info = _make_info(source="judge", retry_after_seconds=120.0)
        coordinator.signal_rate_limit(info)
        stored = coordinator.get_rate_limit_info()
        assert stored is not None
        assert stored.source == info.source
        assert stored.retry_after_seconds == info.retry_after_seconds
        assert stored.error_message == info.error_message

    def test_get_rate_limit_info_returns_none_when_not_paused(self) -> None:
        """get_rate_limit_info returns None when pause event is not set."""
        coordinator = _make_coordinator()
        assert coordinator.get_rate_limit_info() is None


class TestRateLimitCoordinatorResumeAllWorkers:
    """Tests for resume_all_workers() — clears pause, sets resume."""

    def test_resume_clears_pause_event(self) -> None:
        """After resume_all_workers(), _pause_event is cleared."""
        coordinator = _make_coordinator()
        info = _make_info()
        coordinator.signal_rate_limit(info)
        coordinator.resume_all_workers()
        assert not coordinator._pause_event.is_set()

    def test_resume_sets_resume_event(self) -> None:
        """After resume_all_workers(), _resume_event is set."""
        coordinator = _make_coordinator()
        info = _make_info()
        coordinator.signal_rate_limit(info)
        coordinator.resume_all_workers()
        assert coordinator._resume_event.is_set()

    def test_check_if_paused_returns_false_after_resume(self) -> None:
        """check_if_paused() returns False after pause-then-resume cycle."""
        coordinator = _make_coordinator()
        info = _make_info()
        coordinator.signal_rate_limit(info)
        coordinator.resume_all_workers()
        result = coordinator.check_if_paused()
        assert result is False

    def test_after_resume_get_rate_limit_info_returns_none(self) -> None:
        """After resume, get_rate_limit_info returns None (pause cleared)."""
        coordinator = _make_coordinator()
        info = _make_info()
        coordinator._pause_event.set()
        coordinator._rate_limit_info.update(
            {
                "source": info.source,
                "retry_after_seconds": info.retry_after_seconds,
                "error_message": info.error_message,
                "detected_at": info.detected_at,
            }
        )
        coordinator.resume_all_workers()
        assert coordinator.get_rate_limit_info() is None


class TestRateLimitCoordinatorResumeEventRaceCondition:
    """Regression test: _resume_event must NOT be cleared by check_if_paused().

    Previously, workers called self._resume_event.clear() after waking up.
    This caused a race where one worker cleared the event before other workers
    had a chance to observe it, permanently blocking them.

    The fix: only resume_all_workers() (the producer/main thread) manages
    Event state. Workers only observe.
    """

    def test_check_if_paused_does_not_clear_resume_event(self) -> None:
        """check_if_paused() does NOT call _resume_event.clear()."""
        import inspect

        coordinator = _make_coordinator()
        source = inspect.getsource(coordinator.check_if_paused)

        # The fix: worker should never call _resume_event.clear()
        assert "_resume_event.clear()" not in source, (
            "check_if_paused() must not clear _resume_event — only "
            "resume_all_workers() (producer/main thread) should manage Event state. "
            "Clearing in worker causes race where one worker blocks all others."
        )


class TestRateLimitCoordinatorShutdown:
    """Tests for signal_shutdown() and is_shutdown_requested()."""

    def test_signal_shutdown_sets_flag(self) -> None:
        """After signal_shutdown(), is_shutdown_requested() returns True."""
        coordinator = _make_coordinator()
        coordinator.signal_shutdown()
        assert coordinator.is_shutdown_requested() is True

    def test_not_shutdown_before_signal(self) -> None:
        """is_shutdown_requested() returns False before signal_shutdown()."""
        coordinator = _make_coordinator()
        assert coordinator.is_shutdown_requested() is False

    def test_signal_shutdown_is_idempotent(self) -> None:
        """Calling signal_shutdown multiple times does not raise."""
        coordinator = _make_coordinator()
        coordinator.signal_shutdown()
        coordinator.signal_shutdown()
        assert coordinator.is_shutdown_requested() is True


class TestRateLimitCoordinatorCheckIfPaused:
    """Tests for the check_if_paused method."""

    def test_returns_false_when_not_paused(self) -> None:
        """Returns False immediately when pause event is not set."""
        coordinator = _make_coordinator()
        result = coordinator.check_if_paused()
        assert result is False

    def test_returns_true_when_paused_and_resumed(self) -> None:
        """Returns True after waiting for resume; does NOT clear _resume_event.

        The race condition fix: only resume_all_workers() (producer) may clear
        _resume_event. check_if_paused() (worker) must only observe it.
        """
        coordinator = _make_coordinator()
        # Set both pause and resume so check_if_paused doesn't block
        coordinator._pause_event.set()
        coordinator._resume_event.set()

        result = coordinator.check_if_paused()

        assert result is True
        # resume event must NOT be cleared by the worker (race condition fix)
        assert coordinator._resume_event.is_set()


# ---------------------------------------------------------------------------
# run_tier_subtests_parallel: single-subtest path
# ---------------------------------------------------------------------------


class TestRunTierSubtestsParallelSingleSubtest:
    """Tests for run_tier_subtests_parallel with a single subtest (no Manager needed)."""

    def _make_subtest_config(self, subtest_id: str = "00-empty") -> MagicMock:
        """Create a mock SubTestConfig."""
        subtest = MagicMock()
        subtest.id = subtest_id
        return subtest

    def _make_tier_config(self, subtests: list) -> MagicMock:
        """Create a mock TierConfig with given subtests."""
        tier_config = MagicMock()
        tier_config.subtests = subtests
        return tier_config

    def test_single_subtest_no_coordinator_created(self, tmp_path: Path) -> None:
        """Single-subtest path runs without creating a Manager or coordinator."""
        from scylla.e2e.models import ExperimentConfig, SubTestResult, TierID

        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://example.com/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        mock_result = SubTestResult(
            subtest_id="00-empty",
            tier_id=TierID.T0,
            runs=[],
            pass_rate=0.0,
        )

        subtest = self._make_subtest_config("00-empty")
        tier_config = self._make_tier_config([subtest])
        mock_tier_manager = MagicMock()
        mock_workspace = MagicMock()
        mock_executor = MagicMock()
        mock_executor.run_subtest.return_value = mock_result

        # SubTestExecutor is imported inside the function body, so patch at import site
        with (
            patch(
                "scylla.e2e.subtest_executor.SubTestExecutor",
                return_value=mock_executor,
            ),
            patch("scylla.e2e.parallel_executor.Manager") as mock_manager_cls,
            patch(
                "scylla.e2e.parallel_executor.SubTestExecutor",
                return_value=mock_executor,
                create=True,
            ),
        ):
            from scylla.e2e.parallel_executor import run_tier_subtests_parallel

            results = run_tier_subtests_parallel(
                config=config,
                tier_id=TierID.T0,
                tier_config=tier_config,
                tier_manager=mock_tier_manager,
                workspace_manager=mock_workspace,
                baseline=None,
                results_dir=tmp_path,
            )

        # Manager should NOT be instantiated for single-subtest path
        mock_manager_cls.assert_not_called()
        assert "00-empty" in results
        assert results["00-empty"] is mock_result

    def test_single_subtest_executor_called_with_correct_args(self, tmp_path: Path) -> None:
        """Single-subtest path passes correct arguments to run_subtest."""
        from scylla.e2e.models import ExperimentConfig, SubTestResult, TierID

        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://example.com/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        mock_result = SubTestResult(
            subtest_id="00-empty",
            tier_id=TierID.T0,
            runs=[],
            pass_rate=0.0,
        )

        subtest = self._make_subtest_config("00-empty")
        tier_config = self._make_tier_config([subtest])
        mock_tier_manager = MagicMock()
        mock_workspace = MagicMock()
        mock_executor = MagicMock()
        mock_executor.run_subtest.return_value = mock_result

        # The function does `from scylla.e2e.subtest_executor import SubTestExecutor`
        # so we patch it where it gets imported inside run_tier_subtests_parallel
        with patch("scylla.e2e.subtest_executor.SubTestExecutor", return_value=mock_executor):
            from scylla.e2e.parallel_executor import run_tier_subtests_parallel

            run_tier_subtests_parallel(
                config=config,
                tier_id=TierID.T0,
                tier_config=tier_config,
                tier_manager=mock_tier_manager,
                workspace_manager=mock_workspace,
                baseline=None,
                results_dir=tmp_path,
            )

        # run_subtest should be called exactly once with coordinator=None
        # (single-subtest path passes None since no parallel coordinator is needed)
        mock_executor.run_subtest.assert_called_once()
        call_kwargs = mock_executor.run_subtest.call_args.kwargs
        assert call_kwargs["coordinator"] is None


# ---------------------------------------------------------------------------
# WorkspaceManager.from_existing usage
# ---------------------------------------------------------------------------


class TestWorkspaceManagerFromExisting:
    """Tests verifying WorkspaceManager.from_existing() is used in child process."""

    def test_from_existing_is_used_not_is_setup_hack(self) -> None:
        """_run_subtest_in_process uses WorkspaceManager.from_existing(), not _is_setup=True hack.

        This is a regression guard to ensure the _is_setup attribute mutation hack
        has been replaced by the proper from_existing() classmethod.
        """
        import inspect

        from scylla.e2e.parallel_executor import _run_subtest_in_process

        source = inspect.getsource(_run_subtest_in_process)

        # Should use from_existing classmethod
        assert "from_existing" in source, (
            "_run_subtest_in_process must use WorkspaceManager.from_existing() "
            "instead of manually setting _is_setup=True"
        )

        # Should NOT use the old _is_setup=True hack
        assert "_is_setup = True" not in source, (
            "_run_subtest_in_process must not use the _is_setup=True hack — "
            "use WorkspaceManager.from_existing() instead"
        )

    def test_manager_shutdown_in_finally(self) -> None:
        """run_tier_subtests_parallel calls manager.shutdown() in finally block.

        This is a regression guard to ensure Manager() resources are cleaned up
        even if an exception is raised during parallel execution.
        """
        import inspect

        from scylla.e2e.parallel_executor import run_tier_subtests_parallel

        source = inspect.getsource(run_tier_subtests_parallel)

        # Should have manager.shutdown() in a finally block
        assert "manager.shutdown()" in source, (
            "run_tier_subtests_parallel must call manager.shutdown() to prevent "
            "resource leaks from multiprocessing.Manager()"
        )


# ---------------------------------------------------------------------------
# _run_subtest_in_process_safe tests
# ---------------------------------------------------------------------------


class TestRunSubtestInProcessSafe:
    """Tests for _run_subtest_in_process_safe — the safe wrapper function.

    This wrapper prevents worker crashes from poisoning ProcessPoolExecutor
    by catching all exceptions and returning structured SubTestResult objects.
    """

    def _make_subtest_config(self):
        """Create a minimal SubTestConfig for testing."""
        from scylla.e2e.models import SubTestConfig

        return SubTestConfig(
            id="test-01",
            name="Test Sub-test",
            description="A sub-test used in unit tests",
        )

    def _make_call_args(self, tmp_path) -> dict:
        """Build the keyword arguments for _run_subtest_in_process_safe.

        Uses MagicMock for complex objects since _run_subtest_in_process is mocked.
        """
        from scylla.e2e.models import TierID

        subtest = self._make_subtest_config()
        config = MagicMock()
        tier_config = MagicMock()

        return dict(
            config=config,
            tier_id=TierID.T0,
            tier_config=tier_config,
            subtest=subtest,
            baseline=None,
            results_dir=tmp_path / "results",
            tiers_dir=tmp_path / "tiers",
            base_repo=tmp_path / "repo",
            repo_url="https://github.com/example/repo.git",
            commit=None,
            checkpoint=None,
            checkpoint_path=None,
            coordinator=None,
            scheduler=None,
            experiment_dir=None,
        )

    def test_success_passthrough(self, tmp_path) -> None:
        """When _run_subtest_in_process succeeds, result is passed through unchanged."""
        from scylla.e2e.models import SubTestResult, TierID
        from scylla.e2e.parallel_executor import _run_subtest_in_process_safe

        expected_result = SubTestResult(
            subtest_id="test-01",
            tier_id=TierID.T0,
            runs=[],
            pass_rate=1.0,
            mean_score=1.0,
            median_score=1.0,
            std_dev_score=0.0,
            mean_cost=0.01,
            total_cost=0.01,
            consistency=1.0,
            selection_reason="Success",
        )

        call_args = self._make_call_args(tmp_path)

        with patch(
            "scylla.e2e.parallel_executor._run_subtest_in_process",
            return_value=expected_result,
        ) as mock_inner:
            result = _run_subtest_in_process_safe(**call_args)

        mock_inner.assert_called_once()
        assert result is expected_result

    def test_rate_limit_error_handling(self, tmp_path) -> None:
        """RateLimitError is caught; SubTestResult has rate_limit_info set."""
        from scylla.e2e.models import SubTestResult, TierID
        from scylla.e2e.parallel_executor import _run_subtest_in_process_safe
        from scylla.e2e.rate_limit import RateLimitError, RateLimitInfo

        rate_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=60.0,
            error_message="Too Many Requests",
            detected_at="2026-01-01T00:00:00Z",
        )

        call_args = self._make_call_args(tmp_path)

        with patch(
            "scylla.e2e.parallel_executor._run_subtest_in_process",
            side_effect=RateLimitError(rate_info),
        ):
            result = _run_subtest_in_process_safe(**call_args)

        assert isinstance(result, SubTestResult)
        assert result.rate_limit_info is not None
        assert result.rate_limit_info.source == "agent"
        assert result.rate_limit_info.retry_after_seconds == 60.0
        assert result.rate_limit_info.error_message == "Too Many Requests"
        assert result.selection_reason.startswith("RateLimitError:")
        assert result.subtest_id == "test-01"
        assert result.tier_id == TierID.T0
        assert result.pass_rate == 0.0

    def test_generic_exception_handling(self, tmp_path) -> None:
        """Generic Exception is caught; SubTestResult carries error info."""
        from scylla.e2e.models import SubTestResult, TierID
        from scylla.e2e.parallel_executor import _run_subtest_in_process_safe

        call_args = self._make_call_args(tmp_path)

        with patch(
            "scylla.e2e.parallel_executor._run_subtest_in_process",
            side_effect=RuntimeError("something went very wrong"),
        ):
            result = _run_subtest_in_process_safe(**call_args)

        assert isinstance(result, SubTestResult)
        assert result.rate_limit_info is None
        assert "RuntimeError" in result.selection_reason
        assert "something went very wrong" in result.selection_reason
        assert result.selection_reason.startswith("WorkerError:")
        assert result.subtest_id == "test-01"
        assert result.tier_id == TierID.T0
        assert result.pass_rate == 0.0

    def test_never_raises(self, tmp_path) -> None:
        """Safe wrapper never raises for any Exception subclass from inner function.

        The wrapper catches Exception (and RateLimitError), converting them to
        structured SubTestResult objects.  BaseException subclasses like SystemExit
        are intentionally NOT suppressed (they signal process termination).
        """
        from scylla.e2e.parallel_executor import _run_subtest_in_process_safe

        call_args = self._make_call_args(tmp_path)

        for exc in [
            ValueError("bad value"),
            KeyError("missing key"),
            MemoryError("out of memory"),
            OSError("disk full"),
        ]:
            with patch(
                "scylla.e2e.parallel_executor._run_subtest_in_process",
                side_effect=exc,
            ):
                try:
                    _run_subtest_in_process_safe(**call_args)
                except Exception as raised:  # noqa: BLE001
                    raise AssertionError(
                        f"_run_subtest_in_process_safe raised {type(raised).__name__} "
                        f"when it should never raise"
                    ) from raised

    def test_returns_subtest_result_type(self, tmp_path) -> None:
        """Return type is always SubTestResult regardless of inner outcome."""
        from scylla.e2e.models import SubTestResult
        from scylla.e2e.parallel_executor import _run_subtest_in_process_safe
        from scylla.e2e.rate_limit import RateLimitError, RateLimitInfo

        call_args = self._make_call_args(tmp_path)

        scenarios = [
            RuntimeError("worker blew up"),
            ValueError("unexpected value"),
            RateLimitError(
                RateLimitInfo(
                    source="judge",
                    retry_after_seconds=30.0,
                    error_message="judge rate limited",
                    detected_at="2026-01-01T00:00:00Z",
                )
            ),
        ]

        for exc in scenarios:
            with patch(
                "scylla.e2e.parallel_executor._run_subtest_in_process",
                side_effect=exc,
            ):
                result = _run_subtest_in_process_safe(**call_args)
                assert isinstance(result, SubTestResult), (
                    f"Expected SubTestResult but got {type(result).__name__} "
                    f"when inner raised {type(exc).__name__}"
                )
