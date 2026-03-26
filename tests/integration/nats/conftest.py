"""Shared fixtures for NATS integration tests.

Provides a real nats-server process on an ephemeral port with JetStream
enabled, plus a helper class for publishing messages via nats-py.
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import tempfile
import time
from collections.abc import Generator
from typing import Any

import pytest


def _find_free_port() -> int:
    """Find a free TCP port by binding to port 0."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


def _wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 5.0) -> None:
    """Block until a TCP port is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"nats-server did not start on {host}:{port} within {timeout}s")


class NATSPublisher:
    """Synchronous wrapper around nats-py for publishing JetStream messages.

    Manages its own asyncio event loop for test-side publishing.
    """

    def __init__(self, url: str, stream: str = "TASKS") -> None:
        """Initialize the publisher with a NATS URL and stream name."""
        self._url = url
        self._stream = stream
        self._loop = asyncio.new_event_loop()
        self._nc: Any = None
        self._js: Any = None
        self._setup()

    def _setup(self) -> None:
        """Connect to NATS and create the JetStream stream."""
        import nats as nats_client

        self._nc = self._loop.run_until_complete(nats_client.connect(self._url))
        self._js = self._nc.jetstream()
        self._loop.run_until_complete(
            self._js.add_stream(name=self._stream, subjects=["hi.tasks.>"])
        )

    def publish_json(self, subject: str, payload: dict[str, Any]) -> None:
        """Publish a JSON-encoded message to the given subject."""
        self._loop.run_until_complete(self._js.publish(subject, json.dumps(payload).encode()))

    def publish_raw(self, subject: str, data: bytes) -> None:
        """Publish raw bytes to the given subject."""
        self._loop.run_until_complete(self._js.publish(subject, data))

    def purge_stream(self) -> None:
        """Purge all messages from the stream so tests start clean."""
        self._loop.run_until_complete(self._js.purge_stream(self._stream))

    def close(self) -> None:
        """Drain the connection and close the event loop."""
        if self._nc:
            self._loop.run_until_complete(self._nc.drain())
        self._loop.close()


@pytest.fixture(scope="session")
def nats_port() -> int:
    """Return an ephemeral TCP port for nats-server."""
    return _find_free_port()


@pytest.fixture(scope="session")
def nats_url(nats_port: int) -> Generator[str, None, None]:
    """Start a real nats-server process and yield its URL.

    The server runs with JetStream enabled on an ephemeral port.
    It is terminated in teardown.
    """
    with tempfile.TemporaryDirectory() as store_dir:
        proc = subprocess.Popen(
            [
                "nats-server",
                "-p",
                str(nats_port),
                "-js",
                "-sd",
                store_dir,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            _wait_for_port(nats_port)
            yield f"nats://127.0.0.1:{nats_port}"
        finally:
            proc.terminate()
            proc.wait(timeout=10)


@pytest.fixture()
def publisher(nats_url: str) -> Generator[NATSPublisher, None, None]:
    """Yield a NATSPublisher connected to the test server.

    Creates the TASKS stream and tears down the connection after the test.
    """
    pub = NATSPublisher(nats_url)
    pub.purge_stream()
    yield pub
    pub.close()
