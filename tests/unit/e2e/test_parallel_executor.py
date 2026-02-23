"""Tests for scylla/e2e/parallel_executor.py.

These tests focus on the RateLimitCoordinator class which uses
multiprocessing.Manager for cross-process coordination.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from scylla.e2e.parallel_executor import RateLimitCoordinator
from scylla.e2e.rate_limit import RateLimitInfo


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
        coordinator = _make_coordinator()
        assert coordinator.check_if_paused() is False

    def test_not_shutdown_initially(self) -> None:
        """Shutdown event is not set on initialization."""
        coordinator = _make_coordinator()
        assert coordinator.is_shutdown_requested() is False

    def test_no_rate_limit_info_initially(self) -> None:
        """get_rate_limit_info returns None when no rate limit has been signaled."""
        coordinator = _make_coordinator()
        assert coordinator.get_rate_limit_info() is None


class TestRateLimitCoordinatorSignaling:
    """Tests for signal_rate_limit and check_if_paused."""

    def test_signal_rate_limit_sets_pause(self) -> None:
        """Signaling a rate limit causes check_if_paused to detect the pause."""
        coordinator = _make_coordinator()
        info = _make_info()

        # Set resume event first so check_if_paused doesn't block
        coordinator._resume_event.set()
        coordinator.signal_rate_limit(info)

        # After signal, pause event should be set
        assert coordinator._pause_event.is_set()

    def test_get_rate_limit_info_returns_info_after_signal(self) -> None:
        """get_rate_limit_info returns the signaled info after a signal."""
        coordinator = _make_coordinator()
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
        coordinator = _make_coordinator()
        # Don't set the pause event
        assert coordinator.get_rate_limit_info() is None


class TestRateLimitCoordinatorResume:
    """Tests for resume_all_workers behavior."""

    def test_resume_clears_pause_event(self) -> None:
        """resume_all_workers clears the pause event."""
        coordinator = _make_coordinator()
        coordinator._pause_event.set()  # Simulate paused state

        coordinator.resume_all_workers()

        assert not coordinator._pause_event.is_set()

    def test_resume_sets_resume_event(self) -> None:
        """resume_all_workers sets the resume event to unblock workers."""
        coordinator = _make_coordinator()
        coordinator._pause_event.set()

        coordinator.resume_all_workers()

        assert coordinator._resume_event.is_set()

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


class TestRateLimitCoordinatorShutdown:
    """Tests for signal_shutdown and is_shutdown_requested."""

    def test_signal_shutdown_sets_flag(self) -> None:
        """signal_shutdown causes is_shutdown_requested to return True."""
        coordinator = _make_coordinator()
        coordinator.signal_shutdown()
        assert coordinator.is_shutdown_requested() is True

    def test_shutdown_not_set_by_default(self) -> None:
        """Shutdown is not requested on initialization."""
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

    def test_returns_true_and_clears_after_resume(self) -> None:
        """Returns True after waiting for resume, and clears resume event."""
        coordinator = _make_coordinator()
        # Set both pause and resume so check_if_paused doesn't block
        coordinator._pause_event.set()
        coordinator._resume_event.set()

        result = coordinator.check_if_paused()

        assert result is True
        # resume event should be cleared
        assert not coordinator._resume_event.is_set()


class TestRunSubtestInProcessSafe:
    """Tests for _run_subtest_in_process_safe — the safe wrapper function.

    This wrapper prevents worker crashes from poisoning ProcessPoolExecutor
    by catching all exceptions and returning structured SubTestResult objects.
    """

    # ------------------------------------------------------------------
    # Fixtures / helpers
    # ------------------------------------------------------------------

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
        from unittest.mock import MagicMock

        from scylla.e2e.models import TierID

        subtest = self._make_subtest_config()

        # Config and tier_config are passed through to the mocked inner function,
        # so MagicMock objects work fine here.
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
            global_semaphore=None,
            experiment_dir=None,
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_success_passthrough(self, tmp_path) -> None:
        """When _run_subtest_in_process succeeds, result is passed through unchanged."""
        from unittest.mock import patch

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
        from unittest.mock import patch

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
        from unittest.mock import patch

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
        from unittest.mock import patch

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
        from unittest.mock import patch

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
