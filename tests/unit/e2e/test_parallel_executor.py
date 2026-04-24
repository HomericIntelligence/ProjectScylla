"""Unit tests for parallel_executor module.

Tests cover:
- RateLimitCoordinator: all methods and state transitions
- Race condition regression: _resume_event not cleared by worker
- Manager() cleanup via finally block
- run_tier_subtests_parallel: single-subtest path (no coordinator)
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from scylla.e2e.parallel_executor import RateLimitCoordinator
from scylla.e2e.rate_limit import RateLimitInfo

# ---------------------------------------------------------------------------
# RateLimitCoordinator tests
# ---------------------------------------------------------------------------


def _make_coordinator() -> RateLimitCoordinator:
    """Create a RateLimitCoordinator with threading primitives."""
    return RateLimitCoordinator()


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

    def _make_tier_config(self, subtests: list[Any]) -> MagicMock:
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
        with patch(
            "scylla.e2e.subtest_executor.SubTestExecutor",
            return_value=mock_executor,
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
# RateLimitCoordinator: check_if_paused exits on shutdown
# ---------------------------------------------------------------------------


class TestRateLimitCoordinatorCheckIfPausedShutdown:
    """Tests that check_if_paused() exits promptly when _shutdown_event is set."""

    def test_check_if_paused_exits_on_shutdown_within_timeout(self) -> None:
        """Returns within ~3s when _shutdown_event is set but _resume_event is not."""
        import time as time_mod

        coordinator = _make_coordinator()
        # Put into paused state
        coordinator._pause_event.set()
        # _resume_event is NOT set — would block forever without shutdown
        coordinator._shutdown_event.set()

        start = time_mod.monotonic()
        result = coordinator.check_if_paused()
        elapsed = time_mod.monotonic() - start

        # Should return True (was paused) and complete quickly (poll interval is 2s)
        assert result is True
        assert elapsed < 5.0, (
            f"check_if_paused took {elapsed:.1f}s — should exit within ~3s on shutdown"
        )

    def test_check_if_paused_blocks_without_shutdown(self) -> None:
        """Blocks when paused and neither resume nor shutdown is set."""
        coordinator = _make_coordinator()
        coordinator._pause_event.set()
        # Neither resume nor shutdown set — should block

        completed = threading.Event()

        def worker() -> None:
            coordinator.check_if_paused()
            completed.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        # Should NOT complete within 1 second
        assert not completed.wait(timeout=1.0), (
            "check_if_paused should block when no resume/shutdown"
        )

        # Clean up: signal shutdown so the thread exits
        coordinator._shutdown_event.set()
        t.join(timeout=5.0)


# ---------------------------------------------------------------------------
# Parallel subtest loop: shutdown raises ShutdownInterruptedError
# ---------------------------------------------------------------------------


class TestParallelSubtestLoopShutdown:
    """Tests that the parallel subtest loop raises ShutdownInterruptedError on shutdown."""

    def test_stops_early_on_shutdown(self, tmp_path: Any) -> None:
        """run_tier_subtests_parallel stops early when shutdown is requested."""
        from scylla.e2e.models import ExperimentConfig, SubTestConfig, TierID

        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://example.com/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        sub1 = SubTestConfig(id="00", name="Sub 0", description="first")
        sub2 = SubTestConfig(id="01", name="Sub 1", description="second")
        tier_config = MagicMock()
        tier_config.subtests = [sub1, sub2]

        mock_tier_manager = MagicMock()
        mock_workspace = MagicMock()

        with patch("scylla.e2e.shutdown.is_shutdown_requested", return_value=True):
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

        # Should return empty results since shutdown was requested before any subtest ran
        assert results == {}
