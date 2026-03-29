"""Tests for scylla.agamemnon.client."""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from scylla.agamemnon.client import AgamemnonClient
from scylla.agamemnon.errors import AgamemnonAPIError, AgamemnonConnectionError
from scylla.agamemnon.models import (
    AgamemnonConfig,
    FailureSpec,
    HealthResponse,
    InjectionResult,
)


@pytest.fixture
def config() -> AgamemnonConfig:
    """Create a test AgamemnonConfig with retries disabled for basic tests."""
    return AgamemnonConfig(
        base_url="http://localhost:8080",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
        max_retries=0,
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


class TestAgamemnonClientContextManager:
    """Tests for context manager protocol."""

    def test_enter_returns_self(self, config: AgamemnonConfig) -> None:
        """__enter__ returns the client instance."""
        client = AgamemnonClient(config)
        assert client.__enter__() is client
        client.close()

    def test_exit_closes_client(self, config: AgamemnonConfig) -> None:
        """__exit__ closes the underlying httpx client."""
        with patch.object(AgamemnonClient, "close") as mock_close:
            client = AgamemnonClient(config)
            client.__exit__(None, None, None)
            mock_close.assert_called_once()

    def test_with_statement(self, config: AgamemnonConfig) -> None:
        """Client works as a context manager."""
        with AgamemnonClient(config) as client:
            assert isinstance(client, AgamemnonClient)


class TestHealthCheck:
    """Tests for AgamemnonClient.health_check."""

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: AgamemnonConfig) -> None:
        """Successful health check returns HealthResponse."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            json_data={"status": "ok", "version": "1.0.0"}
        )

        client = AgamemnonClient(config)
        client._client = mock_http
        result = client.health_check()

        assert isinstance(result, HealthResponse)
        assert result.status == "ok"
        assert result.version == "1.0.0"

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_connection_error_returns_none(
        self, mock_client_cls: MagicMock, config: AgamemnonConfig
    ) -> None:
        """Connection failure returns None instead of raising."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AgamemnonClient(config)
        client._client = mock_http
        result = client.health_check()

        assert result is None

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_timeout_returns_none(
        self, mock_client_cls: MagicMock, config: AgamemnonConfig
    ) -> None:
        """Timeout returns None instead of raising."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ReadTimeout("timed out")

        client = AgamemnonClient(config)
        client._client = mock_http
        result = client.health_check()

        assert result is None

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_non_2xx_returns_none(
        self, mock_client_cls: MagicMock, config: AgamemnonConfig
    ) -> None:
        """Non-2xx status returns None (API error caught internally)."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(status_code=503, text="Service Unavailable")

        client = AgamemnonClient(config)
        client._client = mock_http
        result = client.health_check()

        assert result is None


class TestListAgents:
    """Tests for AgamemnonClient.list_agents."""

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: AgamemnonConfig) -> None:
        """Successful list returns agent dicts."""
        agents: list[dict[str, Any]] = [{"id": "agent-1", "name": "Test Agent"}]
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(json_data=agents)

        client = AgamemnonClient(config)
        client._client = mock_http
        result = client.list_agents()

        assert result == agents

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_connection_error_raises(
        self, mock_client_cls: MagicMock, config: AgamemnonConfig
    ) -> None:
        """Connection failure raises AgamemnonConnectionError."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AgamemnonClient(config)
        client._client = mock_http

        with pytest.raises(AgamemnonConnectionError):
            client.list_agents()

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_non_2xx_raises_api_error(
        self, mock_client_cls: MagicMock, config: AgamemnonConfig
    ) -> None:
        """Non-2xx response raises AgamemnonAPIError."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            status_code=500, text="Internal Server Error"
        )

        client = AgamemnonClient(config)
        client._client = mock_http

        with pytest.raises(AgamemnonAPIError) as exc_info:
            client.list_agents()

        assert exc_info.value.status_code == 500
        assert exc_info.value.response_body == "Internal Server Error"


class TestInjectFailure:
    """Tests for AgamemnonClient.inject_failure."""

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: AgamemnonConfig) -> None:
        """Successful injection returns InjectionResult."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            json_data={"injection_id": "inj-001", "status": "active"}
        )

        client = AgamemnonClient(config)
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

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_with_duration(self, mock_client_cls: MagicMock, config: AgamemnonConfig) -> None:
        """Duration is included in payload when specified."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            json_data={"injection_id": "inj-002", "status": "active"}
        )

        client = AgamemnonClient(config)
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

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_timeout_raises(self, mock_client_cls: MagicMock, config: AgamemnonConfig) -> None:
        """Timeout raises AgamemnonConnectionError."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ReadTimeout("timed out")

        client = AgamemnonClient(config)
        client._client = mock_http

        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        with pytest.raises(AgamemnonConnectionError, match="timed out"):
            client.inject_failure(spec)


class TestClearFailure:
    """Tests for AgamemnonClient.clear_failure."""

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: AgamemnonConfig) -> None:
        """Successful clear does not raise."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(json_data={})

        client = AgamemnonClient(config)
        client._client = mock_http
        client.clear_failure("inj-001")

        call_args = mock_http.request.call_args
        assert call_args[0] == ("DELETE", "/v1/chaos/inject/inj-001")

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_not_found_raises(self, mock_client_cls: MagicMock, config: AgamemnonConfig) -> None:
        """404 raises AgamemnonAPIError."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(status_code=404, text="Not Found")

        client = AgamemnonClient(config)
        client._client = mock_http

        with pytest.raises(AgamemnonAPIError) as exc_info:
            client.clear_failure("nonexistent")

        assert exc_info.value.status_code == 404


class TestGetDiagnostics:
    """Tests for AgamemnonClient.get_diagnostics."""

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock, config: AgamemnonConfig) -> None:
        """Successful diagnostics returns dict."""
        diag: dict[str, Any] = {"uptime": 3600, "agents_active": 5}
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(json_data=diag)

        client = AgamemnonClient(config)
        client._client = mock_http
        result = client.get_diagnostics()

        assert result == diag

    @patch("scylla.agamemnon.client.httpx.Client")
    def test_null_response_returns_empty_dict(
        self, mock_client_cls: MagicMock, config: AgamemnonConfig
    ) -> None:
        """Null JSON response is coerced to empty dict."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(json_data=None)

        client = AgamemnonClient(config)
        client._client = mock_http
        result = client.get_diagnostics()

        assert result == {}
