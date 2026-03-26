"""Resilience utilities composing retry and circuit breaker patterns.

Provides high-level helpers for subprocess calls with:
- Automatic retry on transient errors (network, subprocess crashes)
- Circuit breaker integration for fail-fast on repeated failures
- Rate limit error passthrough (not retried, handled by RateLimitCoordinator)
"""

from __future__ import annotations

import logging
import subprocess

from scylla.automation.retry import retry_with_backoff
from scylla.core.circuit_breaker import CircuitBreaker, get_circuit_breaker

logger = logging.getLogger(__name__)

# Transient subprocess error types that should be retried
TRANSIENT_SUBPROCESS_ERRORS: tuple[type[Exception], ...] = (
    subprocess.SubprocessError,
    ConnectionError,
    TimeoutError,
    OSError,
)

# Patterns in stderr that indicate transient (retryable) failures
TRANSIENT_ERROR_PATTERNS: list[str] = [
    "connection reset",
    "connection refused",
    "network unreachable",
    "network is unreachable",
    "temporary failure",
    "could not resolve host",
    "curl 56",
    "timed out",
    "early eof",
    "recv failure",
    "broken pipe",
    "connection timed out",
    "ssl handshake",
    "503",
    "502",
    "504",
]


def is_transient_subprocess_error(error: Exception) -> bool:
    """Check if a subprocess error is transient and should be retried.

    Checks both the exception type and any stderr content in the error
    message for known transient patterns.

    Args:
        error: Exception to check

    Returns:
        True if the error is transient and retryable

    """
    # Check exception type
    if isinstance(error, subprocess.TimeoutExpired):
        return False  # Intentional timeouts should not be retried

    if isinstance(error, TRANSIENT_SUBPROCESS_ERRORS):
        # For generic OSError/SubprocessError, check for transient patterns
        if isinstance(error, (OSError, subprocess.SubprocessError)):
            # Build searchable text from all available error info
            parts = [str(error).lower()]
            if isinstance(error, subprocess.CalledProcessError):
                if error.stderr:
                    parts.append(str(error.stderr).lower())
                if error.stdout:
                    parts.append(str(error.stdout).lower())
            error_str = " ".join(parts)
            return any(pattern in error_str for pattern in TRANSIENT_ERROR_PATTERNS)
        return True

    return False


def resilient_call(
    func: object,
    *args: object,
    circuit_breaker_name: str | None = None,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs: object,
) -> object:
    """Execute a function with retry and optional circuit breaker.

    Combines retry-with-backoff and circuit breaker for external calls.
    Rate limit errors are NOT retried - they propagate immediately for
    the RateLimitCoordinator to handle.

    Args:
        func: Function to call
        *args: Positional arguments for func
        circuit_breaker_name: Optional circuit breaker name for fail-fast
        max_retries: Maximum retry attempts
        initial_delay: Initial backoff delay in seconds
        max_delay: Maximum backoff delay cap in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Result of func(*args, **kwargs)

    Raises:
        CircuitBreakerOpenError: If circuit breaker is open
        Exception: Final exception after retries exhausted

    """
    cb: CircuitBreaker | None = None
    if circuit_breaker_name:
        cb = get_circuit_breaker(circuit_breaker_name)

    @retry_with_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=2,
        retry_on=TRANSIENT_SUBPROCESS_ERRORS,
        logger=logger.warning,
        max_delay=max_delay,
        jitter=True,
    )
    def _inner() -> object:
        if cb:
            return cb.call(func, *args, **kwargs)  # type: ignore[arg-type]
        callable_func = func
        return callable_func(*args, **kwargs)  # type: ignore[operator]

    return _inner()
