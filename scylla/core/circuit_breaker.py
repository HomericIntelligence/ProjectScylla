"""Circuit breaker pattern for external API calls.

Implements a state machine with three states:
- CLOSED: Normal operation, requests pass through
- OPEN: Requests fail fast without calling the external service
- HALF_OPEN: Limited requests allowed to test recovery

Thread-safe implementation using threading.Lock for concurrent access.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(enum.Enum):
    """States for the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and requests are rejected."""

    def __init__(self, name: str, time_until_recovery: float) -> None:
        """Initialize with circuit breaker name and recovery time.

        Args:
            name: Circuit breaker identifier
            time_until_recovery: Seconds until recovery attempt

        """
        self.name = name
        self.time_until_recovery = time_until_recovery
        super().__init__(
            f"Circuit breaker '{name}' is open. Recovery in {time_until_recovery:.1f}s"
        )


class CircuitBreaker:
    """Circuit breaker for external service calls.

    Tracks failures and opens the circuit when a threshold is exceeded,
    preventing further calls until a recovery timeout has elapsed.

    Args:
        name: Identifier for this circuit breaker instance
        failure_threshold: Number of consecutive failures before opening
        recovery_timeout: Seconds to wait before transitioning to half-open
        half_open_max_calls: Max calls allowed in half-open state

    Example:
        >>> cb = CircuitBreaker("api", failure_threshold=3, recovery_timeout=30)
        >>> result = cb.call(requests.get, "https://api.example.com")

    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker instance
            failure_threshold: Consecutive failures before opening
            recovery_timeout: Seconds before transitioning to half-open
            half_open_max_calls: Max calls allowed in half-open state

        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit breaker state, accounting for recovery timeout."""
        with self._lock:
            return self._effective_state()

    def _effective_state(self) -> CircuitBreakerState:
        """Compute effective state (must hold lock)."""
        if self._state == CircuitBreakerState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitBreakerState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(
                    f"Circuit breaker '{self.name}' transitioning to HALF_OPEN after {elapsed:.1f}s"
                )
        return self._state

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function through the circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func(*args, **kwargs)

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from func (after recording failure)

        """
        with self._lock:
            state = self._effective_state()

            if state == CircuitBreakerState.OPEN:
                time_until = self.recovery_timeout - (time.monotonic() - self._last_failure_time)
                raise CircuitBreakerOpenError(self.name, max(0.0, time_until))

            if state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name, self.recovery_timeout)
                self._half_open_calls += 1

        # Execute outside the lock to avoid blocking other threads
        try:
            result = func(*args, **kwargs)
        except Exception:
            self._record_failure()
            raise

        self._record_success()
        return result

    def _record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.info(
                    f"Circuit breaker '{self.name}' closing after successful half-open call"
                )
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0

    def _record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' re-opened after half-open failure")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' opened after "
                    f"{self._failure_count} consecutive failures"
                )

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = 0.0
            logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")


# Global registry of circuit breakers
_registry: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    half_open_max_calls: int = 1,
) -> CircuitBreaker:
    """Get or create a named circuit breaker (singleton per name).

    Args:
        name: Unique identifier for the circuit breaker
        failure_threshold: Failures before opening (only used on creation)
        recovery_timeout: Recovery timeout in seconds (only used on creation)
        half_open_max_calls: Max half-open calls (only used on creation)

    Returns:
        CircuitBreaker instance for the given name

    """
    with _registry_lock:
        if name not in _registry:
            _registry[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_max_calls=half_open_max_calls,
            )
        return _registry[name]


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers in the registry. Useful for testing."""
    with _registry_lock:
        for cb in _registry.values():
            cb.reset()
        _registry.clear()
