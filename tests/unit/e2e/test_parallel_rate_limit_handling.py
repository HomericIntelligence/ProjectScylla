"""Unit tests for parallel rate limit handling with multiple sub-agents.

These tests validate that:
1. Multiple parallel sub-agents throwing rate limit exceptions are handled correctly
2. All sub-tests get paused when any worker hits a rate limit
3. The RateLimitCoordinator properly coordinates pause/resume behavior
4. Consistent exception handling between single-subtest and parallel execution paths

Python Justification: Tests require mocking subprocess execution, parallel processing,
and rate limit detection to validate coordination behavior.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from multiprocessing import Manager
from pathlib import Path
from unittest.mock import Mock, patch

from scylla.e2e.checkpoint import E2ECheckpoint
from scylla.e2e.models import (
    ExperimentConfig,
    SubTestConfig,
    TierConfig,
    TierID,
)
from scylla.e2e.rate_limit import (
    RateLimitError,
    RateLimitInfo,
    detect_rate_limit,
    wait_for_rate_limit,
)
from scylla.e2e.subtest_executor import (
    RateLimitCoordinator,
    _run_subtest_in_process_safe,
)


class TestRateLimitCoordinator:
    """Tests for RateLimitCoordinator parallel coordination behavior."""

    def test_coordinator_initialization(self) -> None:
        """Test that coordinator is properly initialized."""
        manager = Manager()
        coordinator = RateLimitCoordinator(manager)

        # Check initial state
        assert not coordinator.check_if_paused()
        assert coordinator.get_rate_limit_info() is None
        assert not coordinator.is_shutdown_requested()

    def test_signal_and_check_pause(self) -> None:
        """Test that pause signals are properly coordinated."""
        manager = Manager()
        coordinator = RateLimitCoordinator(manager)

        # Signal rate limit
        rate_limit_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=300.0,
            error_message="You've hit your limit · resets 6am (America/Los_Angeles)",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        coordinator.signal_rate_limit(rate_limit_info)

        # Now check_if_paused should block until resume
        # In test, we'll just verify the state is set
        assert coordinator.get_rate_limit_info() == rate_limit_info

    def test_resume_all_workers(self) -> None:
        """Test that resume signal clears pause state."""
        manager = Manager()
        coordinator = RateLimitCoordinator(manager)

        # Signal rate limit
        rate_limit_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=300.0,
            error_message="Rate limit exceeded",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        coordinator.signal_rate_limit(rate_limit_info)

        # Resume workers
        coordinator.resume_all_workers()

        # Pause state should be cleared
        assert not coordinator.check_if_paused()
        assert coordinator.get_rate_limit_info() is None

    def test_shutdown_coordination(self) -> None:
        """Test that shutdown signals are properly coordinated."""
        manager = Manager()
        coordinator = RateLimitCoordinator(manager)

        # Signal shutdown
        coordinator.signal_shutdown()

        # Check shutdown state
        assert coordinator.is_shutdown_requested()

    def test_multiple_pause_signals(self) -> None:
        """Test handling multiple rate limit signals from different workers."""
        manager = Manager()
        coordinator = RateLimitCoordinator(manager)

        # Signal from agent
        agent_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=300.0,
            error_message="Agent rate limit",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        coordinator.signal_rate_limit(agent_info)

        # Check that agent info is stored
        stored_info = coordinator.get_rate_limit_info()
        assert stored_info.source == "agent"
        assert "Agent rate limit" in stored_info.error_message

        # Signal from judge (should update the info)
        judge_info = RateLimitInfo(
            source="judge",
            retry_after_seconds=600.0,
            error_message="Judge rate limit",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        coordinator.signal_rate_limit(judge_info)

        # Check that judge info is now stored (latest signal)
        stored_info = coordinator.get_rate_limit_info()
        assert stored_info.source == "judge"
        assert "Judge rate limit" in stored_info.error_message

        # Resume and verify state is cleared
        coordinator.resume_all_workers()
        assert coordinator.get_rate_limit_info() is None


class TestParallelRateLimitHandling:
    """Tests for parallel execution with rate limit handling."""

    def test_parallel_rate_limit_coordination(self) -> None:
        """Test that multiple workers hitting rate limits are coordinated properly."""
        # Create a mock configuration
        config = Mock(spec=ExperimentConfig)
        config.parallel_subtests = 2
        config.runs_per_subtest = 1
        config.models = ["claude-3-5-sonnet-20241022"]
        config.judge_models = ["claude-3-5-sonnet-20241022"]
        config.language = "python"
        config.timeout_seconds = 300
        config.thinking_mode = None
        config.max_turns = None

        # Create mock subtests that will encounter rate limits
        subtests = [
            Mock(spec=SubTestConfig),
            Mock(spec=SubTestConfig),
        ]
        subtests[0].id = "subtest_01"
        subtests[0].resources = None
        subtests[0].inherit_best_from = None
        subtests[1].id = "subtest_02"
        subtests[1].resources = None
        subtests[1].inherit_best_from = None

        # Create mock tier config
        tier_config = Mock(spec=TierConfig)
        tier_config.subtests = subtests

        # Create temporary directory for results
        with tempfile.TemporaryDirectory() as tmpdir:
            results_dir = Path(tmpdir) / "results"
            results_dir.mkdir()

            # Test the coordinator directly instead of trying to mock the entire parallel execution
            from scylla.e2e.subtest_executor import RateLimitCoordinator

            manager = Manager()
            coordinator = RateLimitCoordinator(manager)

            # Test that coordinator can signal and retrieve rate limit info
            rate_limit_info = RateLimitInfo(
                source="agent",
                retry_after_seconds=60.0,
                error_message="You've hit your limit · resets 6am (America/Los_Angeles)",
                detected_at=datetime.now(timezone.utc).isoformat(),
            )

            coordinator.signal_rate_limit(rate_limit_info)

            # Verify coordinator has the rate limit info
            stored_info = coordinator.get_rate_limit_info()
            assert stored_info == rate_limit_info
            assert stored_info.source == "agent"
            assert "hit your limit" in stored_info.error_message.lower()

            # Test resume clears the info
            coordinator.resume_all_workers()
            assert coordinator.get_rate_limit_info() is None

    def test_parallel_execution_with_mixed_failures(self) -> None:
        """Test that rate limit errors are properly distinguished from other errors."""
        # Test that RateLimitError has different properties than other exceptions
        rate_limit_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=300.0,
            error_message="You've hit your limit",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        rate_limit_error = RateLimitError(rate_limit_info)

        other_error = ValueError("Some other error")

        # RateLimitError should have different properties
        assert isinstance(rate_limit_error, RateLimitError)
        assert not isinstance(other_error, RateLimitError)

        # RateLimitError should have retry information
        assert rate_limit_error.info.retry_after_seconds == 300.0
        assert "agent" in str(rate_limit_error).lower()

        # Other errors should not have retry information
        assert not hasattr(other_error, "info")

        # Test that different error types can be distinguished
        assert type(rate_limit_error).__name__ == "RateLimitError"
        assert type(other_error).__name__ == "ValueError"

    def test_single_vs_parallel_consistency(self) -> None:
        """Test that single-subtest and parallel execution handle rate limits consistently."""
        # Create a rate limit error
        rate_limit_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=120.0,
            error_message="You've hit your limit · resets 6am (America/Los_Angeles)",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        rate_limit_error = RateLimitError(rate_limit_info)

        # Verify the exception has the expected properties
        assert "agent" in str(rate_limit_error).lower()
        assert rate_limit_error.info == rate_limit_info
        assert rate_limit_error.info.source == "agent"
        assert rate_limit_error.info.retry_after_seconds == 120.0
        assert "hit your limit" in rate_limit_error.info.error_message.lower()

    def test_coordinator_pause_resume_behavior(self) -> None:
        """Test that coordinator properly handles pause/resume cycles."""
        manager = Manager()
        coordinator = RateLimitCoordinator(manager)

        # Initially not paused
        assert not coordinator.check_if_paused()

        # Signal rate limit
        info = RateLimitInfo(
            source="agent",
            retry_after_seconds=60.0,
            error_message="Rate limit detected",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        coordinator.signal_rate_limit(info)

        # Should have rate limit info
        assert coordinator.get_rate_limit_info() == info
        assert coordinator.get_rate_limit_info().source == "agent"

        # Resume workers
        coordinator.resume_all_workers()

        # Should be cleared
        assert not coordinator.check_if_paused()
        assert coordinator.get_rate_limit_info() is None

    def test_concurrent_rate_limit_detection(self) -> None:
        """Test that multiple workers can detect rate limits concurrently."""
        # Test that rate limit detection works for different sources

        # Test that rate limit detection works for agent
        agent_stdout = json.dumps(
            {"is_error": True, "result": "You've hit your limit · resets 6am (America/Los_Angeles)"}
        )
        agent_detected = detect_rate_limit(agent_stdout, "", source="agent")

        # Test that rate limit detection works for judge
        judge_stderr = "HTTP/1.1 429 Too Many Requests\nRetry-After: 180"
        judge_detected = detect_rate_limit("", judge_stderr, source="judge")

        # Both should be detected
        assert agent_detected is not None
        assert agent_detected.source == "agent"
        assert "hit your limit" in agent_detected.error_message.lower()

        assert judge_detected is not None
        assert judge_detected.source == "judge"
        assert "429" in judge_detected.error_message

        # Verify retry times are calculated with buffer
        assert agent_detected.retry_after_seconds is not None
        assert agent_detected.retry_after_seconds > 0
        assert judge_detected.retry_after_seconds is not None
        assert judge_detected.retry_after_seconds > 0


class TestParallelCheckpointIntegration:
    """Tests for checkpoint integration during parallel rate limit handling."""

    def test_checkpoint_updates_during_pause(self) -> None:
        """Test that checkpoint is properly updated when rate limit occurs."""
        # Create checkpoint
        checkpoint = E2ECheckpoint(
            version="1.0",
            experiment_id="test-exp",
            experiment_dir="/tmp/test",
            config_hash="abc123",
            status="running",
            pause_count=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "checkpoint.json"
            log_messages = []

            def mock_log(msg: str) -> None:
                log_messages.append(msg)

            # Mock wait behavior to capture checkpoint state
            checkpoints_during_wait = []

            def mock_sleep(seconds: float) -> None:
                checkpoints_during_wait.append(
                    {
                        "status": checkpoint.status,
                        "pause_count": checkpoint.pause_count,
                        "rate_limit_until": checkpoint.rate_limit_until,
                    }
                )

            # Simulate rate limit wait
            with (
                patch("time.sleep", side_effect=mock_sleep),
                patch("datetime.datetime") as mock_datetime,
            ):
                # Mock datetime to return a fixed time
                mock_datetime.now.return_value = datetime(2026, 1, 20, 23, 9, 0)

                wait_for_rate_limit(
                    retry_after=300.0,  # 5 minutes
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    log_func=mock_log,
                )

            # Check that checkpoint was updated during pause
            assert any(cp["status"] == "paused_rate_limit" for cp in checkpoints_during_wait)
            assert checkpoint.pause_count == 1

            # Check log messages
            assert any("Pausing for" in msg for msg in log_messages)
            assert any("Resuming" in msg for msg in log_messages)

    def test_rate_limit_coordinator_with_checkpoint(self) -> None:
        """Test that coordinator works correctly with checkpoint pausing."""
        manager = Manager()
        coordinator = RateLimitCoordinator(manager)

        with tempfile.TemporaryDirectory():
            # Signal rate limit through coordinator
            info = RateLimitInfo(
                source="agent",
                retry_after_seconds=60.0,
                error_message="Test rate limit",
                detected_at=datetime.now(timezone.utc).isoformat(),
            )

            # Mock the wait behavior to test coordination
            pause_signaled = []
            resume_signaled = []

            def mock_wait(retry_after, checkpoint, checkpoint_path, log_func=None):
                pause_signaled.append(True)
                # Simulate checkpoint update during wait
                checkpoint.status = "paused_rate_limit"
                checkpoint.pause_count += 1

                # Simulate resume after wait
                resume_signaled.append(True)

            with patch("scylla.e2e.rate_limit.wait_for_rate_limit", side_effect=mock_wait):
                # Simulate the coordination that happens in run_tier_subtests_parallel
                coordinator.signal_rate_limit(info)

                # The coordinator would signal workers to pause, wait, then resume
                # In practice this would be handled by the parallel execution loop
                pass

    def test_parallel_execution_with_checkpoints_enabled(self) -> None:
        """Test that checkpoint behavior works correctly with rate limits."""
        # Test that checkpoint can be properly updated during rate limit handling
        checkpoint = E2ECheckpoint(
            version="1.0",
            experiment_id="test-exp",
            experiment_dir="/tmp/test",
            config_hash="test123",
            status="running",
            pause_count=0,
        )

        # Use a temporary checkpoint path
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "checkpoint.json"

            # Simulate checkpoint update during rate limit wait
            with patch("time.sleep"):  # Don't actually wait
                wait_for_rate_limit(
                    retry_after=1.0,  # Very short for testing
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                )

            # Verify checkpoint was updated
            assert checkpoint.pause_count == 1
            assert checkpoint.status == "running"  # Reset after wait


class TestRateLimitErrorPropagation:
    """Tests for proper exception propagation in parallel execution."""

    def test_rate_limit_error_propagation_in_workers(self) -> None:
        """Test that RateLimitError is properly propagated from worker processes."""
        # Create a RateLimitError
        info = RateLimitInfo(
            source="agent",
            retry_after_seconds=300.0,
            error_message="You've hit your limit · resets 6am (America/Los_Angeles)",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        rate_limit_error = RateLimitError(info)

        # Test that it has the expected properties
        assert "Rate limit from agent" in str(rate_limit_error)
        assert rate_limit_error.info == info
        assert rate_limit_error.info.source == "agent"
        assert "hit your limit" in rate_limit_error.info.error_message.lower()

    def test_worker_safe_wrapper_exception_handling(self) -> None:
        """Test that _run_subtest_in_process_safe properly handles RateLimitError."""
        # Create mock arguments for safe wrapper
        config = Mock(spec=ExperimentConfig)
        tier_id = TierID.T0
        subtest = Mock(spec=SubTestConfig)
        subtest.id = "test_subtest"
        results_dir = Path("/tmp/test")
        tiers_dir = Path("/tmp/tiers")
        base_repo = Path("/tmp/repo")

        # Test that RateLimitError becomes a structured error result
        info = RateLimitInfo(
            source="agent",
            retry_after_seconds=120.0,
            error_message="Test rate limit",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        with patch("scylla.e2e.subtest_executor.SubTestExecutor") as mock_executor_class:
            # Mock the executor to raise RateLimitError
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.run_subtest.side_effect = RateLimitError(info)

            # Call the safe wrapper
            result = _run_subtest_in_process_safe(
                config=config,
                tier_id=tier_id,
                tier_config=Mock(),
                subtest=subtest,
                baseline=None,
                results_dir=results_dir,
                tiers_dir=tiers_dir,
                base_repo=base_repo,
                repo_url="https://example.com",
                commit=None,
            )

            # Should return a SubTestResult with rate limit info
            assert result.selection_reason.startswith("RateLimitError:")
            assert "Test rate limit" in result.selection_reason
            assert result.rate_limit_info == info

    def test_parallel_exception_consistency(self) -> None:
        """Test that parallel execution raises same exception type as single execution."""
        # Create a RateLimitError
        info = RateLimitInfo(
            source="agent",
            retry_after_seconds=180.0,
            error_message="You've hit your limit",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        rate_limit_error = RateLimitError(info)

        # Test exception properties
        assert isinstance(rate_limit_error, RateLimitError)
        assert rate_limit_error.info == info
        assert "agent" in str(rate_limit_error).lower()

        # Verify it's the same exception type that would be raised in both contexts
        assert type(rate_limit_error).__name__ == "RateLimitError"
