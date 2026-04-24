"""Agamemnon Chaos Client for optional fault-injection via the Odysseus agent mesh.

This package provides both synchronous and asynchronous HTTP clients for the
Agamemnon Chaos API. The async variant is designed for parallel tier execution
without blocking the event loop.

Typical usage::

    from scylla.agamemnon import AgamemnonClient, AgamemnonConfig

    config = AgamemnonConfig(base_url="http://localhost:8080", enabled=True)
    with AgamemnonClient(config) as client:
        health = client.health_check()
        result = client.inject_failure(spec)

For async usage::

    from scylla.agamemnon import AsyncAgamemnonClient, AgamemnonConfig

    config = AgamemnonConfig(base_url="http://localhost:8080", enabled=True)
    async with AsyncAgamemnonClient(config) as client:
        health = await client.health_check()
        result = await client.inject_failure(spec)
"""

from scylla.agamemnon.async_client import AsyncAgamemnonClient
from scylla.agamemnon.client import AgamemnonClient
from scylla.agamemnon.errors import (
    AgamemnonAPIError,
    AgamemnonConnectionError,
    AgamemnonError,
)
from scylla.agamemnon.models import (
    AgamemnonConfig,
    FailureSpec,
    HealthResponse,
    InjectionResult,
)
from scylla.agamemnon.protocols import (
    AgamemnonClientProtocol as AgamemnonClientProtocol,
)
from scylla.agamemnon.protocols import (
    AsyncAgamemnonClientProtocol as AsyncAgamemnonClientProtocol,
)

__all__ = [
    "AgamemnonAPIError",
    "AgamemnonClient",
    "AgamemnonClientProtocol",
    "AgamemnonConfig",
    "AgamemnonConnectionError",
    "AgamemnonError",
    "AsyncAgamemnonClient",
    "AsyncAgamemnonClientProtocol",
    "FailureSpec",
    "HealthResponse",
    "InjectionResult",
]
