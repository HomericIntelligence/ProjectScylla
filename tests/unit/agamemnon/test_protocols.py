"""Tests verifying AgamemnonClient protocol structural compatibility."""

from __future__ import annotations

import inspect

import pytest

from scylla.agamemnon import (
    AgamemnonClient,
    AgamemnonClientProtocol,
    AgamemnonConfig,
    AsyncAgamemnonClient,
    AsyncAgamemnonClientProtocol,
)

PROTOCOL_METHODS = [
    "health_check",
    "inject_failure",
    "clear_failure",
    "list_agents",
    "get_diagnostics",
    "close",
]


# ---------------------------------------------------------------------------
# Sync client tests
# ---------------------------------------------------------------------------


class TestSyncClientSatisfiesProtocol:
    """Verify AgamemnonClient satisfies AgamemnonClientProtocol."""

    def test_isinstance_check(self) -> None:
        """Sync client passes runtime_checkable isinstance check."""
        config = AgamemnonConfig()
        client = AgamemnonClient(config)
        assert isinstance(client, AgamemnonClientProtocol)

    @pytest.mark.parametrize("method", PROTOCOL_METHODS)
    def test_has_method(self, method: str) -> None:
        """Sync client exposes every protocol method."""
        assert hasattr(AgamemnonClient, method)
        assert callable(getattr(AgamemnonClient, method))

    @pytest.mark.parametrize("method", PROTOCOL_METHODS)
    def test_method_is_not_coroutine(self, method: str) -> None:
        """Sync client methods are not coroutines."""
        func = getattr(AgamemnonClient, method)
        assert not inspect.iscoroutinefunction(func)


# ---------------------------------------------------------------------------
# Async client tests
# ---------------------------------------------------------------------------


class TestAsyncClientSatisfiesProtocol:
    """Verify AsyncAgamemnonClient satisfies AsyncAgamemnonClientProtocol."""

    def test_isinstance_check(self) -> None:
        """Async client passes runtime_checkable isinstance check."""
        config = AgamemnonConfig()
        client = AsyncAgamemnonClient(config)
        assert isinstance(client, AsyncAgamemnonClientProtocol)

    @pytest.mark.parametrize("method", PROTOCOL_METHODS)
    def test_has_method(self, method: str) -> None:
        """Async client exposes every protocol method."""
        assert hasattr(AsyncAgamemnonClient, method)
        assert callable(getattr(AsyncAgamemnonClient, method))

    @pytest.mark.parametrize("method", PROTOCOL_METHODS)
    def test_method_is_coroutine(self, method: str) -> None:
        """Async client methods are coroutines."""
        func = getattr(AsyncAgamemnonClient, method)
        assert inspect.iscoroutinefunction(func)


# ---------------------------------------------------------------------------
# Signature compatibility tests
# ---------------------------------------------------------------------------


class TestProtocolSignatureCompatibility:
    """Verify method signatures match between protocols and concrete classes."""

    @pytest.mark.parametrize("method", PROTOCOL_METHODS)
    def test_sync_signatures_match(self, method: str) -> None:
        """Sync protocol and client share identical parameter names."""
        proto_sig = inspect.signature(getattr(AgamemnonClientProtocol, method))
        client_sig = inspect.signature(getattr(AgamemnonClient, method))
        # Compare parameter names and annotations (excluding 'self')
        proto_params = list(proto_sig.parameters.values())[1:]  # skip self
        client_params = list(client_sig.parameters.values())[1:]  # skip self
        assert len(proto_params) == len(client_params)
        for p_param, c_param in zip(proto_params, client_params, strict=True):
            assert p_param.name == c_param.name

    @pytest.mark.parametrize("method", PROTOCOL_METHODS)
    def test_async_signatures_match(self, method: str) -> None:
        """Async protocol and client share identical parameter names."""
        proto_sig = inspect.signature(getattr(AsyncAgamemnonClientProtocol, method))
        client_sig = inspect.signature(getattr(AsyncAgamemnonClient, method))
        proto_params = list(proto_sig.parameters.values())[1:]
        client_params = list(client_sig.parameters.values())[1:]
        assert len(proto_params) == len(client_params)
        for p_param, c_param in zip(proto_params, client_params, strict=True):
            assert p_param.name == c_param.name
