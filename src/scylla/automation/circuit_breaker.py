"""Circuit breaker for automation layer.

.. deprecated::
    Import from ``scylla.core.circuit_breaker`` instead.
    This module is a compatibility shim and will be removed in a future release.
"""

import warnings

warnings.warn(
    "scylla.automation.circuit_breaker is deprecated. "
    "Import from scylla.core.circuit_breaker instead.",
    DeprecationWarning,
    stacklevel=2,
)

from scylla.core.circuit_breaker import (  # noqa: E402
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    get_circuit_breaker,
    reset_all_circuit_breakers,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitBreakerState",
    "get_circuit_breaker",
    "reset_all_circuit_breakers",
]
