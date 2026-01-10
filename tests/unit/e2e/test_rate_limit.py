"""Unit tests for rate limit detection and handling."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint
from scylla.e2e.rate_limit import (
    RateLimitError,
    RateLimitInfo,
    check_api_rate_limit_status,
    detect_rate_limit,
    parse_retry_after,
    validate_run_result,
    wait_for_rate_limit,
)


class TestRateLimitInfo:
    """Tests for RateLimitInfo dataclass."""

    def test_valid_agent_source(self) -> None:
        """Test creating RateLimitInfo with agent source."""
        info = RateLimitInfo(
            source="agent",
            retry_after_seconds=60.0,
            error_message="Rate limit exceeded",
            detected_at="2026-01-03T12:00:00Z",
        )

        assert info.source == "agent"
        assert info.retry_after_seconds == 60.0

    def test_valid_judge_source(self) -> None:
        """Test creating RateLimitInfo with judge source."""
        info = RateLimitInfo(
            source="judge",
            retry_after_seconds=120.0,
            error_message="HTTP 429",
            detected_at="2026-01-03T12:00:00Z",
        )

        assert info.source == "judge"

    def test_invalid_source(self) -> None:
        """Test that invalid source raises ValueError."""
        with pytest.raises(ValueError, match="Invalid source: invalid"):
            RateLimitInfo(
                source="invalid",
                retry_after_seconds=60.0,
                error_message="Error",
                detected_at="2026-01-03T12:00:00Z",
            )

    def test_none_retry_after(self) -> None:
        """Test RateLimitInfo with None retry_after."""
        info = RateLimitInfo(
            source="agent",
            retry_after_seconds=None,
            error_message="Rate limit detected",
            detected_at="2026-01-03T12:00:00Z",
        )

        assert info.retry_after_seconds is None


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_exception_message(self) -> None:
        """Test exception message formatting."""
        info = RateLimitInfo(
            source="agent",
            retry_after_seconds=60.0,
            error_message="You've hit your limit",
            detected_at="2026-01-03T12:00:00Z",
        )

        error = RateLimitError(info)

        assert str(error) == "Rate limit from agent: You've hit your limit"
        assert error.info == info


class TestParseRetryAfter:
    """Tests for parse_retry_after function."""

    def test_retry_after_header_seconds(self) -> None:
        """Test parsing Retry-After header with seconds."""
        stderr = "HTTP/1.1 429 Too Many Requests\nRetry-After: 60\n"

        result = parse_retry_after(stderr)

        # Should add 10% buffer: 60 * 1.1 = 66
        assert result == 66.0

    def test_retry_after_case_insensitive(self) -> None:
        """Test Retry-After parsing is case insensitive."""
        stderr = "retry-after: 30"

        result = parse_retry_after(stderr)

        assert result == 33.0  # 30 * 1.1

    def test_resets_4pm_format(self) -> None:
        """Test parsing 'resets 4pm (America/Los_Angeles)' format."""
        stderr = "You've hit your limit · resets 4pm (America/Los_Angeles)"

        result = parse_retry_after(stderr)

        # Should calculate seconds until 4pm Pacific and add 10% buffer
        assert result is not None
        assert result > 0

    def test_resets_12am_format(self) -> None:
        """Test parsing midnight reset time."""
        stderr = "Rate limit resets 12am (America/Los_Angeles)"

        result = parse_retry_after(stderr)

        assert result is not None
        assert result > 0

    def test_resets_with_minutes(self) -> None:
        """Test parsing time with minutes."""
        stderr = "resets 11:30pm (America/Los_Angeles)"

        result = parse_retry_after(stderr)

        assert result is not None
        assert result > 0

    def test_resets_timezone_fallback(self) -> None:
        """Test timezone fallback to America/Los_Angeles."""
        stderr = "resets 4pm"  # No timezone specified

        result = parse_retry_after(stderr)

        # Should still work with default timezone
        assert result is not None
        assert result > 0

    def test_resets_invalid_timezone(self) -> None:
        """Test handling of invalid timezone."""
        stderr = "resets 4pm (Invalid/Timezone)"

        result = parse_retry_after(stderr)

        # Should fallback to UTC and still work
        assert result is not None
        assert result > 0

    def test_no_retry_after_info(self) -> None:
        """Test when no retry information is present."""
        stderr = "Some random error message"

        result = parse_retry_after(stderr)

        assert result is None

    def test_from_json_error_message(self) -> None:
        """Test parsing from JSON error message (bug fix verification)."""
        # This is the critical test case for the bug we fixed
        error_msg = "You've hit your limit · resets 4pm (America/Los_Angeles)"

        result = parse_retry_after(error_msg)

        assert result is not None
        assert result > 0


class TestDetectRateLimit:
    """Tests for detect_rate_limit function."""

    def test_detect_from_json_is_error_hit_limit(self) -> None:
        """Test detection from JSON is_error field with 'hit your limit'."""
        # This is the exact format from the failing test cases
        stdout = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "result": "You've hit your limit · resets 4pm (America/Los_Angeles)",
            }
        )
        stderr = ""

        info = detect_rate_limit(stdout, stderr, source="agent")

        assert info is not None
        assert info.source == "agent"
        assert "hit your limit" in info.error_message.lower()
        assert info.retry_after_seconds is not None
        assert info.retry_after_seconds > 0

    def test_detect_from_json_rate_limit_keyword(self) -> None:
        """Test detection from JSON with 'rate limit' keyword."""
        stdout = json.dumps(
            {
                "is_error": True,
                "result": "API rate limit exceeded. Please try again later.",
            }
        )
        stderr = ""

        info = detect_rate_limit(stdout, stderr, source="judge")

        assert info is not None
        assert info.source == "judge"
        assert "rate limit" in info.error_message.lower()

    def test_detect_from_json_overloaded(self) -> None:
        """Test detection from JSON with 'overloaded' keyword."""
        stdout = json.dumps(
            {
                "is_error": True,
                "error": "Service is currently overloaded",
            }
        )
        stderr = ""

        info = detect_rate_limit(stdout, stderr)

        assert info is not None
        assert "overloaded" in info.error_message.lower()

    def test_detect_from_json_429(self) -> None:
        """Test detection from JSON with '429' keyword."""
        stdout = json.dumps(
            {
                "is_error": True,
                "result": "HTTP 429 Too Many Requests",
            }
        )
        stderr = ""

        info = detect_rate_limit(stdout, stderr)

        assert info is not None
        assert "429" in info.error_message

    def test_json_is_error_but_not_rate_limit(self) -> None:
        """Test that other errors don't trigger rate limit detection."""
        stdout = json.dumps(
            {
                "is_error": True,
                "result": "File not found error",
            }
        )
        stderr = ""

        info = detect_rate_limit(stdout, stderr)

        assert info is None

    def test_detect_from_stderr_429(self) -> None:
        """Test detection from stderr with HTTP 429."""
        stdout = "Normal output"
        stderr = "HTTP/1.1 429 Too Many Requests\nRetry-After: 60"

        info = detect_rate_limit(stdout, stderr)

        assert info is not None
        assert info.error_message == "HTTP 429: Rate limit exceeded"
        assert info.retry_after_seconds == 66.0  # 60 * 1.1

    def test_detect_from_stderr_rate_limit_text(self) -> None:
        """Test detection from stderr with 'rate limit' text."""
        stdout = ""
        stderr = "Error: API rate limit exceeded"

        info = detect_rate_limit(stdout, stderr)

        assert info is not None
        assert info.error_message == "Rate limit detected in stderr"

    def test_detect_from_stderr_hit_your_limit(self) -> None:
        """Test detection from stderr with 'hit your limit'."""
        stdout = ""
        stderr = "You've hit your limit for this hour"

        info = detect_rate_limit(stdout, stderr)

        assert info is not None
        assert info.error_message == "API limit hit"

    def test_detect_from_stderr_overloaded(self) -> None:
        """Test detection from stderr with 'overloaded'."""
        stdout = ""
        stderr = "The API is currently overloaded. Please retry."

        info = detect_rate_limit(stdout, stderr)

        assert info is not None
        assert info.error_message == "API overloaded"

    def test_no_rate_limit_detected(self) -> None:
        """Test when no rate limit is detected."""
        stdout = json.dumps({"status": "success", "result": "OK"})
        stderr = "Normal stderr output"

        info = detect_rate_limit(stdout, stderr)

        assert info is None

    def test_invalid_json_falls_back_to_stderr(self) -> None:
        """Test that invalid JSON falls back to stderr pattern matching."""
        stdout = "Not valid JSON"
        stderr = "429 Rate limit exceeded"

        info = detect_rate_limit(stdout, stderr)

        assert info is not None
        assert info.error_message == "HTTP 429: Rate limit exceeded"

    def test_priority_json_over_stderr(self) -> None:
        """Test that JSON detection takes priority over stderr."""
        # Both JSON and stderr have rate limit indicators
        stdout = json.dumps(
            {
                "is_error": True,
                "result": "You've hit your limit · resets 4pm (America/Los_Angeles)",
            }
        )
        stderr = "Retry-After: 30"

        info = detect_rate_limit(stdout, stderr)

        # Should parse from JSON result first, then fallback to stderr for retry time
        assert info is not None
        assert "hit your limit" in info.error_message.lower()
        # Should try JSON message first, then stderr (which has Retry-After: 30)
        assert info.retry_after_seconds is not None


class TestWaitForRateLimit:
    """Tests for wait_for_rate_limit function."""

    def test_wait_with_retry_after(self) -> None:
        """Test wait behavior with specified retry_after."""
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

            # Use short wait time for test
            with patch("time.sleep"):
                wait_for_rate_limit(
                    retry_after=0.1,  # Very short for testing
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    log_func=mock_log,
                )

            # Check that checkpoint was updated
            assert checkpoint.status == "running"
            assert checkpoint.rate_limit_until is None
            assert checkpoint.pause_count == 1

            # Check log messages
            assert any("Pausing for" in msg for msg in log_messages)
            assert any("Resuming" in msg for msg in log_messages)

    def test_wait_with_none_retry_after(self) -> None:
        """Test wait behavior with None retry_after (uses default)."""
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

            with patch("time.sleep"):
                wait_for_rate_limit(
                    retry_after=None,  # Should use default 60s
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    log_func=mock_log,
                )

            # Check default message
            assert any("default 60s" in msg for msg in log_messages)

    def test_checkpoint_updates(self) -> None:
        """Test that checkpoint is properly updated during wait."""
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

            # Mock time.sleep to track checkpoint state during pause
            checkpoints_during_wait = []

            def mock_sleep(seconds: float) -> None:
                # Capture checkpoint state during wait
                checkpoints_during_wait.append(
                    {
                        "status": checkpoint.status,
                        "rate_limit_until": checkpoint.rate_limit_until,
                        "pause_count": checkpoint.pause_count,
                    }
                )

            with patch("time.sleep", side_effect=mock_sleep):
                wait_for_rate_limit(
                    retry_after=0.1,
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                )

            # During wait, status should have been paused
            assert any(cp["status"] == "paused_rate_limit" for cp in checkpoints_during_wait)

            # After wait, status should be running
            assert checkpoint.status == "running"
            assert checkpoint.rate_limit_until is None
            assert checkpoint.pause_count == 1


class TestIntegration:
    """Integration tests combining detection and handling."""

    def test_full_rate_limit_flow(self) -> None:
        """Test complete flow from detection to waiting."""
        # Simulate agent output with rate limit
        stdout = json.dumps(
            {
                "type": "result",
                "is_error": True,
                "result": "You've hit your limit · resets 4pm (America/Los_Angeles)",
            }
        )
        stderr = ""

        # Detect rate limit
        info = detect_rate_limit(stdout, stderr, source="agent")
        assert info is not None

        # Verify we can raise exception
        error = RateLimitError(info)
        assert "agent" in str(error)

        # Verify we have retry time
        assert info.retry_after_seconds is not None
        assert info.retry_after_seconds > 0

    def test_stderr_fallback_flow(self) -> None:
        """Test flow when JSON parsing fails."""
        stdout = "Invalid JSON {{"
        stderr = "HTTP 429 Too Many Requests\nRetry-After: 60"

        # Should fall back to stderr detection
        info = detect_rate_limit(stdout, stderr, source="judge")

        assert info is not None
        assert info.source == "judge"
        assert info.retry_after_seconds == 66.0  # 60 * 1.1


class TestValidateRunResult:
    """Tests for validate_run_result function."""

    def test_valid_run(self, tmp_path: Path) -> None:
        """Test validation of a valid run."""
        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        # Create valid run_result.json
        (run_dir / "run_result.json").write_text(
            json.dumps(
                {
                    "exit_code": 0,
                    "judge_reasoning": "Task completed successfully",
                }
            )
        )
        (run_dir / "stderr.log").write_text("Normal output")
        (run_dir / "stdout.log").write_text("Normal output")

        is_valid, reason = validate_run_result(run_dir)

        assert is_valid is True
        assert reason is None

    def test_rate_limited_run_in_stderr(self, tmp_path: Path) -> None:
        """Test detection of rate-limited run via stderr."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        (run_dir / "run_result.json").write_text(
            json.dumps(
                {
                    "exit_code": -1,
                    "judge_reasoning": "Invalid: Unable to evaluate agent output",
                }
            )
        )
        (agent_dir / "stderr.log").write_text(
            "Rate limit from agent: You've hit your limit · resets 2am (America/Los_Angeles)"
        )

        is_valid, reason = validate_run_result(run_dir)

        assert is_valid is False
        assert "rate limit" in reason.lower()

    def test_rate_limited_run_in_stdout_json(self, tmp_path: Path) -> None:
        """Test detection of rate-limited run via stdout JSON."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        (run_dir / "run_result.json").write_text(
            json.dumps(
                {
                    "exit_code": -1,
                    "judge_reasoning": "Invalid: Unable to evaluate agent output",
                }
            )
        )
        (agent_dir / "stdout.log").write_text(
            json.dumps(
                {
                    "type": "result",
                    "is_error": True,
                    "result": "You've hit your limit · resets 2am (America/Los_Angeles)",
                }
            )
        )

        is_valid, reason = validate_run_result(run_dir)

        assert is_valid is False
        assert "rate limit" in reason.lower()

    def test_exit_code_minus_one_with_invalid_judge(self, tmp_path: Path) -> None:
        """Test detection of failed run with exit_code=-1 and invalid judge output."""
        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        (run_dir / "run_result.json").write_text(
            json.dumps(
                {
                    "exit_code": -1,
                    "judge_reasoning": "Invalid: Unable to evaluate agent output",
                }
            )
        )
        (run_dir / "stderr.log").write_text("Some other error")

        is_valid, reason = validate_run_result(run_dir)

        assert is_valid is False
        assert "exit_code=-1" in reason

    def test_missing_files_returns_valid(self, tmp_path: Path) -> None:
        """Test that missing files returns valid (no evidence of failure)."""
        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        is_valid, reason = validate_run_result(run_dir)

        assert is_valid is True
        assert reason is None


class TestCheckApiRateLimitStatus:
    """Tests for check_api_rate_limit_status function."""

    @patch("scylla.e2e.rate_limit.subprocess.run")
    def test_no_rate_limit(self, mock_run) -> None:
        """Test when API is not rate limited."""
        mock_run.return_value.stderr = "Success"
        mock_run.return_value.returncode = 0

        result = check_api_rate_limit_status()

        assert result is None

    @patch("scylla.e2e.rate_limit.subprocess.run")
    def test_rate_limit_detected(self, mock_run) -> None:
        """Test when rate limit is detected in stderr."""
        from subprocess import CompletedProcess

        mock_run.return_value = CompletedProcess(
            args=["claude", "--print", "ping"],
            returncode=1,
            stdout="",
            stderr="Rate limit exceeded. Retry-After: 120",
        )

        result = check_api_rate_limit_status()

        assert result is not None
        assert result.source == "agent"
        assert result.retry_after_seconds == 132.0  # 120 * 1.1
        assert "Rate limit" in result.error_message

    @patch("scylla.e2e.rate_limit.subprocess.run")
    def test_hit_your_limit_detected(self, mock_run) -> None:
        """Test when 'hit your limit' message is detected."""
        from subprocess import CompletedProcess

        mock_run.return_value = CompletedProcess(
            args=["claude", "--print", "ping"],
            returncode=1,
            stdout="",
            stderr="You've hit your limit · resets 4pm (America/Los_Angeles)",
        )

        result = check_api_rate_limit_status()

        assert result is not None
        assert result.source == "agent"
        assert "hit your limit" in result.error_message.lower()

    @patch("scylla.e2e.rate_limit.subprocess.run")
    def test_timeout_returns_none(self, mock_run) -> None:
        """Test that subprocess timeout returns None (not treated as rate limit)."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("claude", 30)

        result = check_api_rate_limit_status()

        assert result is None

    @patch("scylla.e2e.rate_limit.subprocess.run")
    def test_other_exception_returns_none(self, mock_run) -> None:
        """Test that other exceptions return None."""
        mock_run.side_effect = OSError("Command not found")

        result = check_api_rate_limit_status()

        assert result is None
