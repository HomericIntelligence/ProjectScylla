"""Smoke test for circuit_breaker re-export shim in automation layer."""

from scylla.automation.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    get_circuit_breaker,
    reset_all_circuit_breakers,
)


def test_circuit_breaker_imports() -> None:
    """Verify that circuit breaker symbols are importable from scylla.automation."""
    assert CircuitBreaker is not None
    assert CircuitBreakerOpenError is not None
    assert CircuitBreakerState is not None
    assert get_circuit_breaker is not None
    assert reset_all_circuit_breakers is not None
