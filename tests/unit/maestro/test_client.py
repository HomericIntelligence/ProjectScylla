"""Unit tests for MaestroClient with retry logic."""

import logging
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

from scylla.maestro.client import MaestroClient
from scylla.maestro.errors import MaestroAPIError, MaestroConnectionError, MaestroError
from scylla.maestro.models import (
    FailureSpec,
    HealthResponse,
    InjectionResult,
    MaestroConfig,
)


class TestMaestroClientRetry:
    """Tests for retry logic in MaestroClient._request()."""

    def test_success_first_attempt(self, maestro_config: MaestroConfig) -> None:
        """Test successful request on first attempt (no sleep)."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            response = Mock()
            response.is_success = True
            mock_client.request.return_value = response

            with patch("time.sleep") as mock_sleep:
                client = MaestroClient(maestro_config)
                result = client._request("GET", "/api/v1/health")

            assert result is response
            mock_sleep.assert_not_called()
            mock_client.request.assert_called_once()

    def test_retry_succeeds_on_second_attempt(
        self, maestro_config: MaestroConfig
    ) -> None:
        """Test retry succeeds on second attempt (1 sleep call)."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True
            mock_client.request.side_effect = [
                httpx.ConnectError("Connection failed"),
                ok_response,
            ]

            with patch("time.sleep") as mock_sleep:
                client = MaestroClient(maestro_config)
                result = client._request("GET", "/api/v1/health")

            assert result is ok_response
            mock_sleep.assert_called_once_with(1.0)
            assert mock_client.request.call_count == 2

    def test_retry_succeeds_on_third_attempt(
        self, maestro_config: MaestroConfig
    ) -> None:
        """Test retry succeeds on third attempt (2 sleep calls with correct delays)."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True
            mock_client.request.side_effect = [
                httpx.TimeoutException("Timeout"),
                httpx.ConnectError("Connection failed"),
                ok_response,
            ]

            with patch("time.sleep") as mock_sleep:
                client = MaestroClient(maestro_config)
                result = client._request("GET", "/api/v1/health")

            assert result is ok_response
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(2.0)
            assert mock_client.request.call_count == 3

    def test_retry_exhausted_raises_connection_error(
        self, maestro_config: MaestroConfig
    ) -> None:
        """Test that exhausted retries raise MaestroConnectionError."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            mock_client.request.side_effect = httpx.ConnectError("Connection failed")

            client = MaestroClient(maestro_config)
            with pytest.raises(MaestroConnectionError) as exc_info:
                client._request("GET", "/api/v1/health")

            assert "after 4 attempts" in str(exc_info.value)
            assert mock_client.request.call_count == 4  # max_retries + 1

    def test_max_retries_zero_disables_retry(self) -> None:
        """Test that max_retries=0 disables retry (single attempt)."""
        config = MaestroConfig(max_retries=0)
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            mock_client.request.side_effect = httpx.ConnectError("Connection failed")

            client = MaestroClient(config)
            with pytest.raises(MaestroConnectionError):
                client._request("GET", "/api/v1/health")

            mock_client.request.assert_called_once()

    def test_timeout_exception_retried(self, maestro_config: MaestroConfig) -> None:
        """Test that TimeoutException is retried."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True
            mock_client.request.side_effect = [
                httpx.TimeoutException("Request timed out"),
                ok_response,
            ]

            client = MaestroClient(maestro_config)
            result = client._request("GET", "/api/v1/health")

            assert result is ok_response

    def test_remote_protocol_error_retried(self, maestro_config: MaestroConfig) -> None:
        """Test that RemoteProtocolError is retried."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True
            mock_client.request.side_effect = [
                httpx.RemoteProtocolError("Protocol error"),
                ok_response,
            ]

            client = MaestroClient(maestro_config)
            result = client._request("GET", "/api/v1/health")

            assert result is ok_response

    def test_http_502_retried(self, maestro_config: MaestroConfig) -> None:
        """Test that HTTP 502 is retried."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True

            error_response = Mock()
            error_response.is_success = False
            error_response.status_code = 502
            mock_client.request.side_effect = [error_response, ok_response]

            with patch("time.sleep") as mock_sleep:
                client = MaestroClient(maestro_config)
                result = client._request("GET", "/api/v1/health")

            assert result is ok_response
            mock_sleep.assert_called_once()

    def test_http_503_retried(self, maestro_config: MaestroConfig) -> None:
        """Test that HTTP 503 is retried."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True

            error_response = Mock()
            error_response.is_success = False
            error_response.status_code = 503
            mock_client.request.side_effect = [error_response, ok_response]

            client = MaestroClient(maestro_config)
            result = client._request("GET", "/api/v1/health")

            assert result is ok_response

    def test_http_504_retried(self, maestro_config: MaestroConfig) -> None:
        """Test that HTTP 504 is retried."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True

            error_response = Mock()
            error_response.is_success = False
            error_response.status_code = 504
            mock_client.request.side_effect = [error_response, ok_response]

            client = MaestroClient(maestro_config)
            result = client._request("GET", "/api/v1/health")

            assert result is ok_response

    def test_404_not_retried(self, maestro_config: MaestroConfig) -> None:
        """Test that HTTP 404 is not retried and raises immediately."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            error_response = Mock()
            error_response.is_success = False
            error_response.status_code = 404
            error_response.text = "Not found"
            mock_client.request.return_value = error_response

            client = MaestroClient(maestro_config)
            with pytest.raises(MaestroAPIError) as exc_info:
                client._request("GET", "/api/not-found")

            assert exc_info.value.status_code == 404
            mock_client.request.assert_called_once()

    def test_500_not_retried(self, maestro_config: MaestroConfig) -> None:
        """Test that HTTP 500 is not retried and raises immediately."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            error_response = Mock()
            error_response.is_success = False
            error_response.status_code = 500
            error_response.text = "Internal server error"
            mock_client.request.return_value = error_response

            client = MaestroClient(maestro_config)
            with pytest.raises(MaestroAPIError) as exc_info:
                client._request("GET", "/api/v1/health")

            assert exc_info.value.status_code == 500
            mock_client.request.assert_called_once()

    def test_non_retryable_http_error_not_retried(
        self, maestro_config: MaestroConfig
    ) -> None:
        """Test that non-retryable httpx errors raise immediately."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            # Use a non-retryable httpx error
            mock_client.request.side_effect = httpx.HTTPError("Some HTTP error")

            client = MaestroClient(maestro_config)
            with pytest.raises(MaestroError):
                client._request("GET", "/api/v1/health")

            mock_client.request.assert_called_once()

    def test_backoff_timing(self, maestro_config: MaestroConfig) -> None:
        """Test that backoff delays follow exponential pattern (1s, 2s, 4s)."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True
            mock_client.request.side_effect = [
                httpx.ConnectError("Connection failed"),
                httpx.ConnectError("Connection failed"),
                httpx.ConnectError("Connection failed"),
                ok_response,
            ]

            with patch("time.sleep") as mock_sleep:
                client = MaestroClient(maestro_config)
                result = client._request("GET", "/api/v1/health")

            assert result is ok_response
            assert mock_sleep.call_count == 3
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls == [1.0, 2.0, 4.0]

    def test_warning_logged_on_retry(
        self, maestro_config: MaestroConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that warning is logged on retry with attempt info."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            ok_response = Mock()
            ok_response.is_success = True
            mock_client.request.side_effect = [
                httpx.ConnectError("Connection failed"),
                ok_response,
            ]

            with caplog.at_level(logging.WARNING):
                client = MaestroClient(maestro_config)
                client._request("GET", "/api/v1/health")

            assert any("attempt 1/4" in record.message for record in caplog.records)
            assert any("retrying in 1.0s" in record.message for record in caplog.records)

    def test_context_manager(self, maestro_config: MaestroConfig) -> None:
        """Test that context manager properly closes the client."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            with MaestroClient(maestro_config) as client:
                pass

            mock_client.close.assert_called_once()

    def test_explicit_close(self, maestro_config: MaestroConfig) -> None:
        """Test that explicit close() works."""
        with patch("scylla.maestro.client.httpx.Client") as MockClient:
            mock_client = Mock()
            MockClient.return_value = mock_client

            client = MaestroClient(maestro_config)
            client.close()

            mock_client.close.assert_called_once()


class TestMaestroClientPublicAPI:
    """Tests for public API methods."""

    def test_health_check_success(self, maestro_config: MaestroConfig) -> None:
        """Test successful health check."""
        with patch.object(MaestroClient, "_request") as mock_request:
            response = Mock()
            response.json.return_value = {"status": "ok", "version": "1.0"}
            mock_request.return_value = response

            client = MaestroClient(maestro_config)
            result = client.health_check()

            assert isinstance(result, HealthResponse)
            assert result.status == "ok"
            assert result.version == "1.0"

    def test_health_check_failure_returns_none(self, maestro_config: MaestroConfig) -> None:
        """Test that health check returns None on error."""
        with patch.object(MaestroClient, "_request") as mock_request:
            mock_request.side_effect = MaestroConnectionError("Failed to connect")

            client = MaestroClient(maestro_config)
            result = client.health_check()

            assert result is None

    def test_list_agents(self, maestro_config: MaestroConfig) -> None:
        """Test listing agents."""
        with patch.object(MaestroClient, "_request") as mock_request:
            response = Mock()
            response.json.return_value = [{"id": "agent-1"}, {"id": "agent-2"}]
            mock_request.return_value = response

            client = MaestroClient(maestro_config)
            result = client.list_agents()

            assert len(result) == 2
            assert result[0]["id"] == "agent-1"

    def test_inject_failure(self, maestro_config: MaestroConfig) -> None:
        """Test failure injection."""
        with patch.object(MaestroClient, "_request") as mock_request:
            response = Mock()
            response.json.return_value = {"injection_id": "inj-123", "status": "active"}
            mock_request.return_value = response

            client = MaestroClient(maestro_config)
            spec = FailureSpec(agent_id="agent-1", failure_type="crash")
            result = client.inject_failure(spec)

            assert isinstance(result, InjectionResult)
            assert result.injection_id == "inj-123"
            assert result.status == "active"

    def test_clear_failure(self, maestro_config: MaestroConfig) -> None:
        """Test clearing an injected failure."""
        with patch.object(MaestroClient, "_request") as mock_request:
            response = Mock()
            mock_request.return_value = response

            client = MaestroClient(maestro_config)
            client.clear_failure("inj-123")

            mock_request.assert_called_once_with("DELETE", "/api/agents/inject/inj-123")

    def test_get_diagnostics(self, maestro_config: MaestroConfig) -> None:
        """Test retrieving diagnostics."""
        with patch.object(MaestroClient, "_request") as mock_request:
            response = Mock()
            response.json.return_value = {"uptime": 3600, "agents": 5}
            mock_request.return_value = response

            client = MaestroClient(maestro_config)
            result = client.get_diagnostics()

            assert result["uptime"] == 3600
            assert result["agents"] == 5
