"""Tests for shared retry logic."""

from __future__ import annotations

from scylla.agamemnon._retry import (
    BACKOFF_BASE,
    BACKOFF_FACTOR,
    TRANSIENT_STATUS_CODES,
    compute_backoff,
    is_transient_status,
)


class TestComputeBackoff:
    """Tests for compute_backoff."""

    def test_attempt_zero(self) -> None:
        """Verify base delay for first attempt."""
        assert compute_backoff(0) == BACKOFF_BASE

    def test_attempt_one(self) -> None:
        """Verify exponential growth on second attempt."""
        assert compute_backoff(1) == BACKOFF_BASE * BACKOFF_FACTOR

    def test_attempt_two(self) -> None:
        """Verify exponential growth on third attempt."""
        assert compute_backoff(2) == BACKOFF_BASE * (BACKOFF_FACTOR**2)


class TestIsTransientStatus:
    """Tests for is_transient_status."""

    def test_transient_codes(self) -> None:
        """Verify 502, 503, 504 are transient."""
        for code in TRANSIENT_STATUS_CODES:
            assert is_transient_status(code) is True

    def test_non_transient_codes(self) -> None:
        """Verify common non-transient codes are not flagged."""
        for code in (200, 400, 401, 403, 404, 500):
            assert is_transient_status(code) is False
