"""Tests for resilience module composing retry and circuit breaker."""

from __future__ import annotations

import subprocess

import pytest

from scylla.core.circuit_breaker import reset_all_circuit_breakers
from scylla.core.resilience import (
    TRANSIENT_ERROR_PATTERNS,
    is_transient_subprocess_error,
)


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Reset circuit breaker registry before each test."""
    reset_all_circuit_breakers()


class TestIsTransientSubprocessError:
    """Tests for is_transient_subprocess_error function."""

    def test_timeout_expired_is_not_transient(self) -> None:
        """TimeoutExpired is intentional, not transient."""
        error = subprocess.TimeoutExpired(cmd="test", timeout=30)
        assert is_transient_subprocess_error(error) is False

    def test_connection_error_is_transient(self) -> None:
        """ConnectionError is always transient."""
        error = ConnectionError("connection refused")
        assert is_transient_subprocess_error(error) is True

    def test_timeout_error_is_transient(self) -> None:
        """TimeoutError (Python builtin) is transient."""
        error = TimeoutError("operation timed out")
        assert is_transient_subprocess_error(error) is True

    def test_os_error_with_transient_pattern(self) -> None:
        """OSError with transient pattern is transient."""
        error = OSError("connection reset by peer")
        assert is_transient_subprocess_error(error) is True

    def test_os_error_without_transient_pattern(self) -> None:
        """OSError without transient pattern is not transient."""
        error = OSError("permission denied")
        assert is_transient_subprocess_error(error) is False

    def test_subprocess_error_with_transient_pattern(self) -> None:
        """SubprocessError with network-related message is transient."""
        error = subprocess.SubprocessError("early eof from server")
        assert is_transient_subprocess_error(error) is True

    def test_subprocess_error_without_transient_pattern(self) -> None:
        """SubprocessError without transient pattern is not transient."""
        error = subprocess.SubprocessError("invalid argument")
        assert is_transient_subprocess_error(error) is False

    def test_value_error_is_not_transient(self) -> None:
        """Non-subprocess errors are not transient."""
        error = ValueError("invalid value")
        assert is_transient_subprocess_error(error) is False

    def test_called_process_error_with_network_error(self) -> None:
        """CalledProcessError with network stderr is transient."""
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd="git fetch",
            stderr="connection reset by peer",
        )
        assert is_transient_subprocess_error(error) is True


class TestTransientErrorPatterns:
    """Tests for transient error pattern list."""

    def test_patterns_are_lowercase(self) -> None:
        """All patterns should be lowercase for case-insensitive matching."""
        for pattern in TRANSIENT_ERROR_PATTERNS:
            assert pattern == pattern.lower(), f"Pattern not lowercase: {pattern}"

    def test_essential_patterns_present(self) -> None:
        """Essential transient patterns are in the list."""
        essential = [
            "connection reset",
            "connection refused",
            "timed out",
            "early eof",
            "503",
            "502",
            "504",
        ]
        for pattern in essential:
            assert pattern in TRANSIENT_ERROR_PATTERNS, f"Missing pattern: {pattern}"
