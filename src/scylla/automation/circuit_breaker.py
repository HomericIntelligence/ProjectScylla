"""Circuit breaker for automation layer — re-exports from hephaestus.resilience."""

from hephaestus.resilience.circuit_breaker import (
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
