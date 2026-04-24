"""Protocol definitions for AgamemnonClient and AsyncAgamemnonClient.

These protocols allow consumers to write code agnostic to sync vs async
by accepting either concrete implementation where the protocol is satisfied.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from scylla.agamemnon.models import FailureSpec, HealthResponse, InjectionResult


@runtime_checkable
class AgamemnonClientProtocol(Protocol):
    """Structural protocol for the synchronous Agamemnon client."""

    def health_check(self) -> HealthResponse | None:
        """Check service health."""
        ...

    def inject_failure(self, spec: FailureSpec) -> InjectionResult:
        """Inject a chaos failure."""
        ...

    def clear_failure(self, injection_id: str) -> None:
        """Clear an injected failure."""
        ...

    def list_agents(self) -> list[dict[str, Any]]:
        """List registered agents."""
        ...

    def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information."""
        ...

    def close(self) -> None:
        """Release underlying resources."""
        ...


@runtime_checkable
class AsyncAgamemnonClientProtocol(Protocol):
    """Structural protocol for the asynchronous Agamemnon client."""

    async def health_check(self) -> HealthResponse | None:
        """Check service health."""
        ...

    async def inject_failure(self, spec: FailureSpec) -> InjectionResult:
        """Inject a chaos failure."""
        ...

    async def clear_failure(self, injection_id: str) -> None:
        """Clear an injected failure."""
        ...

    async def list_agents(self) -> list[dict[str, Any]]:
        """List registered agents."""
        ...

    async def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information."""
        ...

    async def close(self) -> None:
        """Release underlying resources."""
        ...
