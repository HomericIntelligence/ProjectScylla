"""Smoke test for the circuit_breaker deprecation shim in the automation layer.

Verifies that the deprecated ``scylla.automation.circuit_breaker`` module still
re-exports all symbols from the canonical ``scylla.core.circuit_breaker`` module,
and that it emits a ``DeprecationWarning`` on import.
"""

import importlib
import warnings

import scylla.core.circuit_breaker as _core_cb


def test_automation_shim_emits_deprecation_warning() -> None:
    """Importing from scylla.automation.circuit_breaker raises DeprecationWarning."""
    # Force a fresh import so the warning fires even if the module is cached.
    import sys

    sys.modules.pop("scylla.automation.circuit_breaker", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module("scylla.automation.circuit_breaker")

    deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecation_warnings, "Expected a DeprecationWarning from the automation shim"
    assert "scylla.core.circuit_breaker" in str(deprecation_warnings[0].message)


def test_automation_shim_re_exports_canonical_symbols() -> None:
    """Symbols from the shim are identical to those in scylla.core.circuit_breaker."""
    import sys

    sys.modules.pop("scylla.automation.circuit_breaker", None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        shim = importlib.import_module("scylla.automation.circuit_breaker")

    assert shim.CircuitBreaker is _core_cb.CircuitBreaker
    assert shim.CircuitBreakerOpenError is _core_cb.CircuitBreakerOpenError
    assert shim.CircuitBreakerState is _core_cb.CircuitBreakerState
    assert shim.get_circuit_breaker is _core_cb.get_circuit_breaker
    assert shim.reset_all_circuit_breakers is _core_cb.reset_all_circuit_breakers
