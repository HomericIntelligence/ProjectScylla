"""Tests for scylla/e2e/parallel_executor.py.

These tests focus on the RateLimitCoordinator class which uses
multiprocessing.Manager for cross-process coordination.
"""

from __future__ import annotations

from multiprocessing import Manager

from scylla.e2e.parallel_executor import RateLimitCoordinator
from scylla.e2e.rate_limit import RateLimitInfo


def _make_info(
    source: str = "agent",
    retry_after_seconds: float = 60.0,
    error_message: str = "rate limited",
    detected_at: str = "2026-01-01T00:00:00Z",
) -> RateLimitInfo:
    """Create a RateLimitInfo for testing."""
    return RateLimitInfo(
        source=source,
        retry_after_seconds=retry_after_seconds,
        error_message=error_message,
        detected_at=detected_at,
    )


class TestRateLimitCoordinatorInitialState:
    """Tests for initial state of RateLimitCoordinator."""

    def test_not_paused_initially(self) -> None:
        """Pause event is not set on initialization — workers proceed normally."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            assert coordinator.check_if_paused() is False

    def test_not_shutdown_initially(self) -> None:
        """Shutdown event is not set on initialization."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            assert coordinator.is_shutdown_requested() is False

    def test_no_rate_limit_info_initially(self) -> None:
        """get_rate_limit_info returns None when no rate limit has been signaled."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            assert coordinator.get_rate_limit_info() is None


class TestRateLimitCoordinatorSignaling:
    """Tests for signal_rate_limit and check_if_paused."""

    def test_signal_rate_limit_sets_pause(self) -> None:
        """Signaling a rate limit causes check_if_paused to detect the pause."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            info = _make_info()

            # Set resume event first so check_if_paused doesn't block
            coordinator._resume_event.set()
            coordinator.signal_rate_limit(info)

            # After signal, pause event should be set
            assert coordinator._pause_event.is_set()

    def test_get_rate_limit_info_returns_info_after_signal(self) -> None:
        """get_rate_limit_info returns the signaled info after a signal."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            info = _make_info(source="judge", retry_after_seconds=120.0)

            coordinator._pause_event.set()  # Simulate already-set pause
            coordinator.signal_rate_limit(info)

            result = coordinator.get_rate_limit_info()
            assert result is not None
            assert result.source == "judge"
            assert result.retry_after_seconds == 120.0
            assert result.error_message == "rate limited"

    def test_get_rate_limit_info_returns_none_when_not_paused(self) -> None:
        """get_rate_limit_info returns None when pause event is not set."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            # Don't set the pause event
            assert coordinator.get_rate_limit_info() is None


class TestRateLimitCoordinatorResume:
    """Tests for resume_all_workers behavior."""

    def test_resume_clears_pause_event(self) -> None:
        """resume_all_workers clears the pause event."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            coordinator._pause_event.set()  # Simulate paused state

            coordinator.resume_all_workers()

            assert not coordinator._pause_event.is_set()

    def test_resume_sets_resume_event(self) -> None:
        """resume_all_workers sets the resume event to unblock workers."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            coordinator._pause_event.set()

            coordinator.resume_all_workers()

            assert coordinator._resume_event.is_set()

    def test_after_resume_get_rate_limit_info_returns_none(self) -> None:
        """After resume, get_rate_limit_info returns None (pause cleared)."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
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


class TestRateLimitCoordinatorShutdown:
    """Tests for signal_shutdown and is_shutdown_requested."""

    def test_signal_shutdown_sets_flag(self) -> None:
        """signal_shutdown causes is_shutdown_requested to return True."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            coordinator.signal_shutdown()
            assert coordinator.is_shutdown_requested() is True

    def test_shutdown_not_set_by_default(self) -> None:
        """Shutdown is not requested on initialization."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            assert coordinator.is_shutdown_requested() is False

    def test_signal_shutdown_is_idempotent(self) -> None:
        """Calling signal_shutdown multiple times does not raise."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            coordinator.signal_shutdown()
            coordinator.signal_shutdown()
            assert coordinator.is_shutdown_requested() is True


class TestRateLimitCoordinatorCheckIfPaused:
    """Tests for the check_if_paused method."""

    def test_returns_false_when_not_paused(self) -> None:
        """Returns False immediately when pause event is not set."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            result = coordinator.check_if_paused()
            assert result is False

    def test_returns_true_and_clears_after_resume(self) -> None:
        """Returns True after waiting for resume, and clears resume event."""
        with Manager() as mgr:
            coordinator = RateLimitCoordinator(mgr)
            # Set both pause and resume so check_if_paused doesn't block
            coordinator._pause_event.set()
            coordinator._resume_event.set()

            result = coordinator.check_if_paused()

            assert result is True
            # resume event should be cleared
            assert not coordinator._resume_event.is_set()
