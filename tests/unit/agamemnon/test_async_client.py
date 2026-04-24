"""Tests for the asynchronous AsyncAgamemnonClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from scylla.agamemnon.async_client import AsyncAgamemnonClient
from scylla.agamemnon.errors import AgamemnonAPIError, AgamemnonConnectionError
from scylla.agamemnon.models import (
    AgamemnonConfig,
    FailureSpec,
    HealthResponse,
    InjectionResult,
)


@pytest.fixture()
def config() -> AgamemnonConfig:
    """Return a test AgamemnonConfig."""
    return AgamemnonConfig(
        base_url="http://test:8080",
        enabled=True,
        max_retries=2,
        timeout_seconds=5,
    )


def _make_async_client(
    config: AgamemnonConfig, transport: httpx.MockTransport
) -> AsyncAgamemnonClient:
    """Create an AsyncAgamemnonClient with a mocked transport."""
    client = AsyncAgamemnonClient(config)
    client._client = httpx.AsyncClient(base_url=config.base_url, transport=transport)
    return client


class TestAsyncHealthCheck:
    """Tests for AsyncAgamemnonClient.health_check."""

    @pytest.mark.asyncio()
    async def test_healthy(self, config: AgamemnonConfig) -> None:
        """Verify healthy response is parsed correctly."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/health"
            return httpx.Response(200, json={"status": "ok", "version": "1.0.0"})

        client = _make_async_client(config, httpx.MockTransport(handler))
        result = await client.health_check()
        assert result is not None
        assert result == HealthResponse(status="ok", version="1.0.0")

    @pytest.mark.asyncio()
    async def test_unreachable_returns_none(self, config: AgamemnonConfig) -> None:
        """Verify connection error returns None gracefully."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = _make_async_client(config, httpx.MockTransport(handler))
        result = await client.health_check()
        assert result is None

    @pytest.mark.asyncio()
    async def test_server_error_returns_none(self, config: AgamemnonConfig) -> None:
        """Verify server error returns None gracefully."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        client = _make_async_client(config, httpx.MockTransport(handler))
        result = await client.health_check()
        assert result is None


class TestAsyncInjectFailure:
    """Tests for AsyncAgamemnonClient.inject_failure."""

    @pytest.mark.asyncio()
    async def test_success(self, config: AgamemnonConfig) -> None:
        """Verify successful injection returns parsed result."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/chaos/inject"
            assert request.method == "POST"
            return httpx.Response(200, json={"injection_id": "inj-1", "status": "active"})

        client = _make_async_client(config, httpx.MockTransport(handler))
        spec = FailureSpec(agent_id="a1", failure_type="latency", duration_seconds=60)
        result = await client.inject_failure(spec)
        assert result == InjectionResult(injection_id="inj-1", status="active")

    @pytest.mark.asyncio()
    async def test_api_error(self, config: AgamemnonConfig) -> None:
        """Verify non-2xx response raises AgamemnonAPIError."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, text="Bad Request")

        client = _make_async_client(config, httpx.MockTransport(handler))
        spec = FailureSpec(agent_id="a1", failure_type="latency", duration_seconds=60)
        with pytest.raises(AgamemnonAPIError) as exc_info:
            await client.inject_failure(spec)
        assert exc_info.value.status_code == 400


class TestAsyncClearFailure:
    """Tests for AsyncAgamemnonClient.clear_failure."""

    @pytest.mark.asyncio()
    async def test_success(self, config: AgamemnonConfig) -> None:
        """Verify DELETE request is sent to the correct path."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/chaos/inject/inj-1"
            assert request.method == "DELETE"
            return httpx.Response(200, json={})

        client = _make_async_client(config, httpx.MockTransport(handler))
        await client.clear_failure("inj-1")


class TestAsyncListAgents:
    """Tests for AsyncAgamemnonClient.list_agents."""

    @pytest.mark.asyncio()
    async def test_success(self, config: AgamemnonConfig) -> None:
        """Verify agent list is returned correctly."""
        agents = [{"id": "a1", "name": "Agent 1"}]

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/agents"
            return httpx.Response(200, json=agents)

        client = _make_async_client(config, httpx.MockTransport(handler))
        result = await client.list_agents()
        assert result == agents


class TestAsyncRetryBehavior:
    """Tests for retry logic in AsyncAgamemnonClient."""

    @pytest.mark.asyncio()
    async def test_retries_on_transient_status(self, config: AgamemnonConfig) -> None:
        """Verify transient 503 is retried and succeeds on third attempt."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return httpx.Response(503, text="Service Unavailable")
            return httpx.Response(200, json={"injection_id": "inj-1", "status": "active"})

        client = _make_async_client(config, httpx.MockTransport(handler))
        spec = FailureSpec(agent_id="a1", failure_type="latency", duration_seconds=60)
        with patch("scylla.agamemnon.async_client.asyncio.sleep", new_callable=AsyncMock):
            result = await client.inject_failure(spec)
        assert result.injection_id == "inj-1"
        assert call_count == 3

    @pytest.mark.asyncio()
    async def test_exhausts_retries_on_transient(self, config: AgamemnonConfig) -> None:
        """Verify retries are exhausted and AgamemnonAPIError is raised."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="Service Unavailable")

        client = _make_async_client(config, httpx.MockTransport(handler))
        spec = FailureSpec(agent_id="a1", failure_type="latency", duration_seconds=60)
        with patch("scylla.agamemnon.async_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AgamemnonAPIError) as exc_info:
                await client.inject_failure(spec)
        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio()
    async def test_retries_on_connection_error(self, config: AgamemnonConfig) -> None:
        """Verify connection errors are retried."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise httpx.ConnectError("connection refused")
            return httpx.Response(200, json=[])

        client = _make_async_client(config, httpx.MockTransport(handler))
        with patch("scylla.agamemnon.async_client.asyncio.sleep", new_callable=AsyncMock):
            result = await client.list_agents()
        assert result == []
        assert call_count == 2

    @pytest.mark.asyncio()
    async def test_exhausts_retries_on_connection_error(self, config: AgamemnonConfig) -> None:
        """Verify exhausted connection retries raise AgamemnonConnectionError."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = _make_async_client(config, httpx.MockTransport(handler))
        with patch("scylla.agamemnon.async_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AgamemnonConnectionError):
                await client.list_agents()

    @pytest.mark.asyncio()
    async def test_no_retry_on_non_transient_error(self, config: AgamemnonConfig) -> None:
        """Verify non-transient errors (404) are not retried."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(404, text="Not Found")

        client = _make_async_client(config, httpx.MockTransport(handler))
        with pytest.raises(AgamemnonAPIError) as exc_info:
            await client.list_agents()
        assert exc_info.value.status_code == 404
        assert call_count == 1


class TestAsyncContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio()
    async def test_async_context_manager(self, config: AgamemnonConfig) -> None:
        """Verify async context manager enters and exits cleanly."""
        async with AsyncAgamemnonClient(config) as client:
            assert client is not None
