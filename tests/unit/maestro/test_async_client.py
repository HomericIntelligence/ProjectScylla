"""Tests for scylla.maestro.async_client."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from scylla.maestro.async_client import AsyncMaestroClient
from scylla.maestro.errors import MaestroAPIError, MaestroConnectionError
from scylla.maestro.models import (
    FailureSpec,
    HealthResponse,
    InjectionResult,
    MaestroConfig,
)


@pytest.fixture
def config() -> MaestroConfig:
    """Create a test MaestroConfig."""
    return MaestroConfig(
        base_url="http://localhost:23000",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
    )


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | list[dict[str, Any]] | None = None,
    text: str = "",
) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data
    resp.text = text
    return resp


def _async_client_mock() -> AsyncMock:
    """Build an AsyncMock standing in for httpx.AsyncClient."""
    mock = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


class TestAsyncMaestroClientContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self, config: MaestroConfig) -> None:
        """__aenter__ returns the client instance."""
        client = AsyncMaestroClient(config)
        result = await client.__aenter__()
        assert result is client
        await client.close()

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self, config: MaestroConfig) -> None:
        """__aexit__ closes the underlying httpx client."""
        client = AsyncMaestroClient(config)
        client._client = _async_client_mock()
        await client.__aexit__(None, None, None)
        client._client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_with_statement(self, config: MaestroConfig) -> None:
        """Client works as an async context manager."""
        async with AsyncMaestroClient(config) as client:
            assert isinstance(client, AsyncMaestroClient)


class TestAsyncHealthCheck:
    """Tests for AsyncMaestroClient.health_check."""

    @pytest.mark.asyncio
    async def test_success(self, config: MaestroConfig) -> None:
        """Successful health check returns HealthResponse."""
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(
            json_data={"status": "ok", "version": "1.0.0"}
        )

        client = AsyncMaestroClient(config)
        client._client = mock_http
        result = await client.health_check()

        assert isinstance(result, HealthResponse)
        assert result.status == "ok"
        assert result.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self, config: MaestroConfig) -> None:
        """Connection failure returns None instead of raising."""
        mock_http = _async_client_mock()
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AsyncMaestroClient(config)
        client._client = mock_http
        result = await client.health_check()

        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, config: MaestroConfig) -> None:
        """Timeout returns None instead of raising."""
        mock_http = _async_client_mock()
        mock_http.request.side_effect = httpx.ReadTimeout("timed out")

        client = AsyncMaestroClient(config)
        client._client = mock_http
        result = await client.health_check()

        assert result is None

    @pytest.mark.asyncio
    async def test_non_2xx_returns_none(self, config: MaestroConfig) -> None:
        """Non-2xx status returns None (API error caught internally)."""
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(status_code=503, text="Service Unavailable")

        client = AsyncMaestroClient(config)
        client._client = mock_http
        result = await client.health_check()

        assert result is None


class TestAsyncListAgents:
    """Tests for AsyncMaestroClient.list_agents."""

    @pytest.mark.asyncio
    async def test_success(self, config: MaestroConfig) -> None:
        """Successful list returns agent dicts."""
        agents = [{"id": "agent-1", "name": "Test Agent"}]
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(json_data=agents)

        client = AsyncMaestroClient(config)
        client._client = mock_http
        result = await client.list_agents()

        assert result == agents

    @pytest.mark.asyncio
    async def test_connection_error_raises(self, config: MaestroConfig) -> None:
        """Connection failure raises MaestroConnectionError."""
        mock_http = _async_client_mock()
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AsyncMaestroClient(config)
        client._client = mock_http

        with pytest.raises(MaestroConnectionError):
            await client.list_agents()

    @pytest.mark.asyncio
    async def test_non_2xx_raises_api_error(self, config: MaestroConfig) -> None:
        """Non-2xx response raises MaestroAPIError."""
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(
            status_code=500, text="Internal Server Error"
        )

        client = AsyncMaestroClient(config)
        client._client = mock_http

        with pytest.raises(MaestroAPIError) as exc_info:
            await client.list_agents()

        assert exc_info.value.status_code == 500
        assert exc_info.value.response_body == "Internal Server Error"


class TestAsyncInjectFailure:
    """Tests for AsyncMaestroClient.inject_failure."""

    @pytest.mark.asyncio
    async def test_success(self, config: MaestroConfig) -> None:
        """Successful injection returns InjectionResult."""
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(
            json_data={"injection_id": "inj-001", "status": "active"}
        )

        client = AsyncMaestroClient(config)
        client._client = mock_http

        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        result = await client.inject_failure(spec)

        assert isinstance(result, InjectionResult)
        assert result.injection_id == "inj-001"
        assert result.status == "active"

        # Verify the payload sent
        call_args = mock_http.request.call_args
        assert call_args[1]["json"] == {
            "agent_id": "agent-1",
            "failure_type": "crash",
            "parameters": {},
        }

    @pytest.mark.asyncio
    async def test_with_duration(self, config: MaestroConfig) -> None:
        """Duration is included in payload when specified."""
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(
            json_data={"injection_id": "inj-002", "status": "active"}
        )

        client = AsyncMaestroClient(config)
        client._client = mock_http

        spec = FailureSpec(
            agent_id="agent-1",
            failure_type="network_delay",
            duration_seconds=30,
            parameters={"latency_ms": 200},
        )
        await client.inject_failure(spec)

        call_args = mock_http.request.call_args
        assert call_args[1]["json"] == {
            "agent_id": "agent-1",
            "failure_type": "network_delay",
            "duration_seconds": 30,
            "parameters": {"latency_ms": 200},
        }

    @pytest.mark.asyncio
    async def test_timeout_raises(self, config: MaestroConfig) -> None:
        """Timeout raises MaestroConnectionError."""
        mock_http = _async_client_mock()
        mock_http.request.side_effect = httpx.ReadTimeout("timed out")

        client = AsyncMaestroClient(config)
        client._client = mock_http

        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        with pytest.raises(MaestroConnectionError, match="timed out"):
            await client.inject_failure(spec)


class TestAsyncClearFailure:
    """Tests for AsyncMaestroClient.clear_failure."""

    @pytest.mark.asyncio
    async def test_success(self, config: MaestroConfig) -> None:
        """Successful clear does not raise."""
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(json_data={})

        client = AsyncMaestroClient(config)
        client._client = mock_http
        await client.clear_failure("inj-001")

        call_args = mock_http.request.call_args
        assert call_args[0] == ("DELETE", "/api/agents/inject/inj-001")

    @pytest.mark.asyncio
    async def test_not_found_raises(self, config: MaestroConfig) -> None:
        """404 raises MaestroAPIError."""
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(status_code=404, text="Not Found")

        client = AsyncMaestroClient(config)
        client._client = mock_http

        with pytest.raises(MaestroAPIError) as exc_info:
            await client.clear_failure("nonexistent")

        assert exc_info.value.status_code == 404


class TestAsyncGetDiagnostics:
    """Tests for AsyncMaestroClient.get_diagnostics."""

    @pytest.mark.asyncio
    async def test_success(self, config: MaestroConfig) -> None:
        """Successful diagnostics returns dict."""
        diag = {"uptime": 3600, "agents_active": 5}
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(json_data=diag)

        client = AsyncMaestroClient(config)
        client._client = mock_http
        result = await client.get_diagnostics()

        assert result == diag

    @pytest.mark.asyncio
    async def test_null_response_returns_empty_dict(self, config: MaestroConfig) -> None:
        """Null JSON response is coerced to empty dict."""
        mock_http = _async_client_mock()
        mock_http.request.return_value = _mock_response(json_data=None)

        client = AsyncMaestroClient(config)
        client._client = mock_http
        result = await client.get_diagnostics()

        assert result == {}
