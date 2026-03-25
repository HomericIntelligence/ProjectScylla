"""Tests for scylla.maestro.client."""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from scylla.maestro.client import MaestroClient
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


class TestMaestroClientContextManager:
    """Tests for context manager protocol."""

    def test_enter_returns_self(self, config: MaestroConfig) -> None:
        """__enter__ returns the client instance."""
        client = MaestroClient(config)
        assert client.__enter__() is client
        client.close()

    def test_exit_closes_client(self, config: MaestroConfig) -> None:
        """__exit__ closes the underlying httpx client."""
        with patch.object(MaestroClient, "close") as mock_close:
            client = MaestroClient(config)
            client.__exit__(None, None, None)
            mock_close.assert_called_once()

    def test_with_statement(self, config: MaestroConfig) -> None:
        """Client works as a context manager."""
        with MaestroClient(config) as client:
            assert isinstance(client, MaestroClient)


class TestHealthCheck:
    """Tests for MaestroClient.health_check."""

    @patch("scylla.maestro.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Successful health check returns HealthResponse."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            json_data={"status": "ok", "version": "1.0.0"}
        )

        client = MaestroClient(config)
        client._client = mock_http
        result = client.health_check()

        assert isinstance(result, HealthResponse)
        assert result.status == "ok"
        assert result.version == "1.0.0"

    @patch("scylla.maestro.client.httpx.Client")
    def test_connection_error_returns_none(
        self, mock_client_cls: MagicMock, config: MaestroConfig
    ) -> None:
        """Connection failure returns None instead of raising."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = MaestroClient(config)
        client._client = mock_http
        result = client.health_check()

        assert result is None

    @patch("scylla.maestro.client.httpx.Client")
    def test_timeout_returns_none(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Timeout returns None instead of raising."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ReadTimeout("timed out")

        client = MaestroClient(config)
        client._client = mock_http
        result = client.health_check()

        assert result is None

    @patch("scylla.maestro.client.httpx.Client")
    def test_non_2xx_returns_none(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Non-2xx status returns None (API error caught internally)."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(status_code=503, text="Service Unavailable")

        client = MaestroClient(config)
        client._client = mock_http
        result = client.health_check()

        assert result is None


class TestListAgents:
    """Tests for MaestroClient.list_agents."""

    @patch("scylla.maestro.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Successful list returns agent dicts."""
        agents = [{"id": "agent-1", "name": "Test Agent"}]
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(json_data=agents)

        client = MaestroClient(config)
        client._client = mock_http
        result = client.list_agents()

        assert result == agents

    @patch("scylla.maestro.client.httpx.Client")
    def test_connection_error_raises(
        self, mock_client_cls: MagicMock, config: MaestroConfig
    ) -> None:
        """Connection failure raises MaestroConnectionError."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = MaestroClient(config)
        client._client = mock_http

        with pytest.raises(MaestroConnectionError):
            client.list_agents()

    @patch("scylla.maestro.client.httpx.Client")
    def test_non_2xx_raises_api_error(
        self, mock_client_cls: MagicMock, config: MaestroConfig
    ) -> None:
        """Non-2xx response raises MaestroAPIError."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            status_code=500, text="Internal Server Error"
        )

        client = MaestroClient(config)
        client._client = mock_http

        with pytest.raises(MaestroAPIError) as exc_info:
            client.list_agents()

        assert exc_info.value.status_code == 500
        assert exc_info.value.response_body == "Internal Server Error"


class TestInjectFailure:
    """Tests for MaestroClient.inject_failure."""

    @patch("scylla.maestro.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Successful injection returns InjectionResult."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            json_data={"injection_id": "inj-001", "status": "active"}
        )

        client = MaestroClient(config)
        client._client = mock_http

        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        result = client.inject_failure(spec)

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

    @patch("scylla.maestro.client.httpx.Client")
    def test_with_duration(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Duration is included in payload when specified."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            json_data={"injection_id": "inj-002", "status": "active"}
        )

        client = MaestroClient(config)
        client._client = mock_http

        spec = FailureSpec(
            agent_id="agent-1",
            failure_type="network_delay",
            duration_seconds=30,
            parameters={"latency_ms": 200},
        )
        client.inject_failure(spec)

        call_args = mock_http.request.call_args
        assert call_args[1]["json"] == {
            "agent_id": "agent-1",
            "failure_type": "network_delay",
            "duration_seconds": 30,
            "parameters": {"latency_ms": 200},
        }

    @patch("scylla.maestro.client.httpx.Client")
    def test_timeout_raises(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Timeout raises MaestroConnectionError."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ReadTimeout("timed out")

        client = MaestroClient(config)
        client._client = mock_http

        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        with pytest.raises(MaestroConnectionError, match="timed out"):
            client.inject_failure(spec)


class TestClearFailure:
    """Tests for MaestroClient.clear_failure."""

    @patch("scylla.maestro.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Successful clear does not raise."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(json_data={})

        client = MaestroClient(config)
        client._client = mock_http
        client.clear_failure("inj-001")

        call_args = mock_http.request.call_args
        assert call_args[0] == ("DELETE", "/api/agents/inject/inj-001")

    @patch("scylla.maestro.client.httpx.Client")
    def test_not_found_raises(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """404 raises MaestroAPIError."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(status_code=404, text="Not Found")

        client = MaestroClient(config)
        client._client = mock_http

        with pytest.raises(MaestroAPIError) as exc_info:
            client.clear_failure("nonexistent")

        assert exc_info.value.status_code == 404


class TestGetDiagnostics:
    """Tests for MaestroClient.get_diagnostics."""

    @patch("scylla.maestro.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: MaestroConfig) -> None:
        """Successful diagnostics returns dict."""
        diag = {"uptime": 3600, "agents_active": 5}
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(json_data=diag)

        client = MaestroClient(config)
        client._client = mock_http
        result = client.get_diagnostics()

        assert result == diag

    @patch("scylla.maestro.client.httpx.Client")
    def test_null_response_returns_empty_dict(
        self, mock_client_cls: MagicMock, config: MaestroConfig
    ) -> None:
        """Null JSON response is coerced to empty dict."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(json_data=None)

        client = MaestroClient(config)
        client._client = mock_http
        result = client.get_diagnostics()

        assert result == {}
