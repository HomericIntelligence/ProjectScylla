"""Circuit breaker pattern for external API calls.

This module re-exports from hephaestus.resilience.circuit_breaker for
backwards compatibility. Import directly from hephaestus.resilience for
new code.
"""
from hephaestus.resilience.circuit_breaker import (  # noqa: F401
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
