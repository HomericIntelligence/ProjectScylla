"""Tests for AgamemnonClient HTTP client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from scylla.adapters.agamemnon_client import (
    AgamemnonClient,
    AgamemnonConnectionError,
)


class TestAgamemnonClient:
    """Tests for AgamemnonClient."""

    def test_init(self) -> None:
        """Test client initialization."""
        client = AgamemnonClient(
            base_url="http://localhost:8080",
            timeout=30.0,
            max_retries=3,
        )
        assert client.base_url == "http://localhost:8080"
        assert client.timeout == 30.0
        assert client.max_retries == 3

    def test_init_strips_trailing_slash(self) -> None:
        """Test that base_url trailing slash is stripped."""
        client = AgamemnonClient(base_url="http://localhost:8080/")
        assert client.base_url == "http://localhost:8080"

    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_request_success(self, mock_client_class: MagicMock) -> None:
        """Test successful request."""
        # Mock the response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None

        # Mock the client context manager
        mock_client_instance = MagicMock()
        mock_client_instance.request.return_value = mock_response
        mock_client_instance.__enter__.return_value = mock_client_instance
        mock_client_instance.__exit__.return_value = None
        mock_client_class.return_value = mock_client_instance

        client = AgamemnonClient(base_url="http://localhost:8080")
        result = client._request("POST", "/v1/chaos/inject", json={"delay": 1})

        assert result == mock_response
        mock_client_instance.request.assert_called_once_with(
            "POST",
            "http://localhost:8080/v1/chaos/inject",
            json={"delay": 1},
        )

    @patch("scylla.adapters.agamemnon_client.time.sleep")
    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_request_retries_on_connection_error(
        self,
        mock_client_class: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """Test that request retries on transient connection errors."""
        # Mock the response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None

        # Mock the client: fail first 2 times, succeed on 3rd
        mock_client_instance = MagicMock()
        mock_client_instance.request.side_effect = [
            httpx.ConnectError("Connection failed"),
            httpx.ConnectError("Connection failed"),
            mock_response,
        ]
        mock_client_instance.__enter__.return_value = mock_client_instance
        mock_client_instance.__exit__.return_value = None
        mock_client_class.return_value = mock_client_instance

        client = AgamemnonClient(base_url="http://localhost:8080")
        result = client._request("POST", "/v1/chaos/inject")

        assert result == mock_response
        assert mock_client_instance.request.call_count == 3
        # Verify backoff delays: 1s, 2s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    @patch("scylla.adapters.agamemnon_client.time.sleep")
    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_request_retries_on_timeout(
        self,
        mock_client_class: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """Test that request retries on timeout errors."""
        # Mock the client: fail on timeout first, succeed on 2nd
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None

        mock_client_instance = MagicMock()
        mock_client_instance.request.side_effect = [
            httpx.TimeoutException("Request timed out"),
            mock_response,
        ]
        mock_client_instance.__enter__.return_value = mock_client_instance
        mock_client_instance.__exit__.return_value = None
        mock_client_class.return_value = mock_client_instance

        client = AgamemnonClient(base_url="http://localhost:8080")
        result = client._request("GET", "/v1/chaos/status")

        assert result == mock_response
        assert mock_client_instance.request.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("scylla.adapters.agamemnon_client.time.sleep")
    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_request_exhausts_retries(
        self,
        mock_client_class: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """Test that AgamemnonConnectionError is raised after retries exhausted."""
        # Mock the client: always fail
        mock_client_instance = MagicMock()
        mock_client_instance.request.side_effect = httpx.ConnectError(
            "Connection refused"
        )
        mock_client_instance.__enter__.return_value = mock_client_instance
        mock_client_instance.__exit__.return_value = None
        mock_client_class.return_value = mock_client_instance

        client = AgamemnonClient(base_url="http://localhost:8080")

        with pytest.raises(AgamemnonConnectionError) as exc_info:
            client._request("POST", "/v1/chaos/inject")

        assert "Failed to reach" in str(exc_info.value)
        assert "after 3 retries" in str(exc_info.value)
        assert mock_client_instance.request.call_count == 3
        # Verify all backoff delays: 1s, 2s, 4s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_request_network_error(
        self,
        mock_client_class: MagicMock,
    ) -> None:
        """Test that request retries on network errors."""
        # Mock the client: fail with NetworkError then succeed
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None

        mock_client_instance = MagicMock()
        mock_client_instance.request.side_effect = [
            httpx.NetworkError("Network unreachable"),
            mock_response,
        ]
        mock_client_instance.__enter__.return_value = mock_client_instance
        mock_client_instance.__exit__.return_value = None
        mock_client_class.return_value = mock_client_instance

        with patch("scylla.adapters.agamemnon_client.time.sleep"):
            client = AgamemnonClient(base_url="http://localhost:8080")
            result = client._request("DELETE", "/v1/chaos/reset")

        assert result == mock_response
        assert mock_client_instance.request.call_count == 2

    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_request_with_custom_timeout(
        self,
        mock_client_class: MagicMock,
    ) -> None:
        """Test request with custom timeout value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None

        mock_client_instance = MagicMock()
        mock_client_instance.request.return_value = mock_response
        mock_client_instance.__enter__.return_value = mock_client_instance
        mock_client_instance.__exit__.return_value = None
        mock_client_class.return_value = mock_client_instance

        client = AgamemnonClient(
            base_url="http://localhost:8080",
            timeout=120.0,
        )
        client._request("GET", "/v1/chaos/status")

        # Verify timeout was passed to httpx.Client
        mock_client_class.assert_called_once_with(timeout=120.0)
