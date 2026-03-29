"""Shared fixtures for AgamemnonClient integration tests."""

from __future__ import annotations

from collections.abc import Callable, Generator

import httpx
import pytest

from scylla.agamemnon.client import AgamemnonClient
from scylla.agamemnon.models import AgamemnonConfig

_ClientFactory = Callable[[Callable[[httpx.Request], httpx.Response]], AgamemnonClient]


@pytest.fixture()
def agamemnon_config() -> AgamemnonConfig:
    """Create a test AgamemnonConfig pointing at a fake server."""
    return AgamemnonConfig(
        base_url="http://testserver",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
    )


@pytest.fixture()
def make_client(
    agamemnon_config: AgamemnonConfig,
) -> Generator[_ClientFactory]:
    """Yield a factory that injects a MockTransport handler into AgamemnonClient."""
    clients: list[AgamemnonClient] = []

    def _make(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> AgamemnonClient:
        client = AgamemnonClient(agamemnon_config)
        client._client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url=agamemnon_config.base_url,
            timeout=httpx.Timeout(agamemnon_config.timeout_seconds),
        )
        clients.append(client)
        return client

    yield _make

    for c in clients:
        c.close()
