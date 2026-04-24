"""Synchronous and asynchronous Agamemnon chaos fault injection clients.

These clients communicate with the Agamemnon REST API (``/v1/chaos/*``)
to inject and clear failures in the Odysseus agent mesh.  Both classes
expose the same method names and signatures so they can be used
interchangeably behind :class:`AgamemnonClientProtocol` and
:class:`AsyncAgamemnonClientProtocol`.
"""

from __future__ import annotations

from typing import Any

from scylla.agamemnon.models import (
    AgamemnonConfig,
    FailureSpec,
    HealthResponse,
    InjectionResult,
)


class AgamemnonClient:
    """Synchronous HTTP client for the Agamemnon chaos API."""

    def __init__(self, config: AgamemnonConfig) -> None:
        """Initialise the client with the given configuration."""
        self._config = config

    # -- public API --------------------------------------------------------

    def health_check(self) -> HealthResponse | None:
        """``GET /v1/health``; returns ``None`` if unreachable."""
        raise NotImplementedError  # pragma: no cover

    def inject_failure(self, spec: FailureSpec) -> InjectionResult:
        """``POST /v1/chaos/inject`` -- inject a failure into an agent."""
        raise NotImplementedError  # pragma: no cover

    def clear_failure(self, injection_id: str) -> None:
        """``DELETE /v1/chaos/inject/{id}`` -- remove an injected failure."""
        raise NotImplementedError  # pragma: no cover

    def list_agents(self) -> list[dict[str, Any]]:
        """``GET /v1/agents`` -- list all registered agents."""
        raise NotImplementedError  # pragma: no cover

    def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the client."""
        raise NotImplementedError  # pragma: no cover

    def close(self) -> None:
        """Release underlying resources."""


class AsyncAgamemnonClient:
    """Asynchronous HTTP client for the Agamemnon chaos API."""

    def __init__(self, config: AgamemnonConfig) -> None:
        """Initialise the client with the given configuration."""
        self._config = config

    # -- public API --------------------------------------------------------

    async def health_check(self) -> HealthResponse | None:
        """``GET /v1/health``; returns ``None`` if unreachable."""
        raise NotImplementedError  # pragma: no cover

    async def inject_failure(self, spec: FailureSpec) -> InjectionResult:
        """``POST /v1/chaos/inject`` -- inject a failure into an agent."""
        raise NotImplementedError  # pragma: no cover

    async def clear_failure(self, injection_id: str) -> None:
        """``DELETE /v1/chaos/inject/{id}`` -- remove an injected failure."""
        raise NotImplementedError  # pragma: no cover

    async def list_agents(self) -> list[dict[str, Any]]:
        """``GET /v1/agents`` -- list all registered agents."""
        raise NotImplementedError  # pragma: no cover

    async def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the client."""
        raise NotImplementedError  # pragma: no cover

    async def close(self) -> None:
        """Release underlying resources."""
