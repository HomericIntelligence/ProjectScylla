"""Shared fixtures for MaestroClient integration tests."""

from __future__ import annotations

from collections.abc import Callable, Generator

import httpx
import pytest

from scylla.maestro.client import MaestroClient
from scylla.maestro.models import MaestroConfig

_ClientFactory = Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient]


@pytest.fixture()
def maestro_config() -> MaestroConfig:
    """Create a test MaestroConfig pointing at a fake server."""
    return MaestroConfig(
        base_url="http://testserver",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
    )


@pytest.fixture()
def make_client(
    maestro_config: MaestroConfig,
) -> Generator[_ClientFactory]:
    """Yield a factory that injects a MockTransport handler into MaestroClient."""
    clients: list[MaestroClient] = []

    def _make(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> MaestroClient:
        client = MaestroClient(maestro_config)
        client._client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url=maestro_config.base_url,
            timeout=httpx.Timeout(maestro_config.timeout_seconds),
        )
        clients.append(client)
        return client

    yield _make

    for c in clients:
        c.close()
