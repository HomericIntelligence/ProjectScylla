"""Tests for AgamemnonClient retry logic.

Verifies that transient failures (connection errors, timeouts, HTTP 502/503/504)
are retried with exponential backoff, while permanent errors (4xx) raise immediately.
"""

from typing import Any
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from scylla.agamemnon.client import AgamemnonClient
from scylla.agamemnon.errors import AgamemnonAPIError, AgamemnonConnectionError
from scylla.agamemnon.models import AgamemnonConfig, FailureSpec


@pytest.fixture
def retry_config() -> AgamemnonConfig:
    """Config with 3 retries for retry tests."""
    return AgamemnonConfig(
        base_url="http://localhost:8080",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
        max_retries=3,
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


class TestRetryOnTransientErrors:
    """Verify that transient exceptions trigger retries then succeed."""

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_retry_connect_error_then_succeed(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """ConnectError on first attempt, success on second."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = [
            httpx.ConnectError("refused"),
            _mock_response(json_data=[]),
        ]

        client = AgamemnonClient(retry_config)
        client._client = mock_http
        result = client.list_agents()

        assert result == []
        assert mock_http.request.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_retry_timeout_then_succeed(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """TimeoutException on first attempt, success on second."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = [
            httpx.ReadTimeout("timed out"),
            _mock_response(json_data=[]),
        ]

        client = AgamemnonClient(retry_config)
        client._client = mock_http
        result = client.list_agents()

        assert result == []
        assert mock_http.request.call_count == 2

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_retry_remote_protocol_error_then_succeed(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """RemoteProtocolError on first attempt, success on second."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = [
            httpx.RemoteProtocolError("server disconnected"),
            _mock_response(json_data=[]),
        ]

        client = AgamemnonClient(retry_config)
        client._client = mock_http
        result = client.list_agents()

        assert result == []
        assert mock_http.request.call_count == 2

    @pytest.mark.parametrize("status_code", [502, 503, 504])
    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_retry_retryable_status_then_succeed(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
        status_code: int,
    ) -> None:
        """HTTP 502/503/504 on first attempt, success on second."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = [
            _mock_response(status_code=status_code, text="Server Error"),
            _mock_response(json_data=[]),
        ]

        client = AgamemnonClient(retry_config)
        client._client = mock_http
        result = client.list_agents()

        assert result == []
        assert mock_http.request.call_count == 2
        mock_sleep.assert_called_once_with(1.0)


class TestRetryExhaustion:
    """Verify that exhausting all retries raises the appropriate error."""

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_all_retries_exhausted_connection_error(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """Raises AgamemnonConnectionError after max_retries+1 ConnectErrors."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        with pytest.raises(AgamemnonConnectionError, match="after 4 attempts"):
            client.list_agents()

        assert mock_http.request.call_count == 4  # 1 initial + 3 retries
        assert mock_sleep.call_count == 3

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_all_retries_exhausted_502(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """Raises AgamemnonAPIError after max_retries+1 502s."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(status_code=502, text="Bad Gateway")

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        with pytest.raises(AgamemnonAPIError) as exc_info:
            client.list_agents()

        assert exc_info.value.status_code == 502
        assert mock_http.request.call_count == 4


class TestNoRetryOnPermanentErrors:
    """Verify that permanent client errors are not retried."""

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_no_retry_on_client_error(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
        status_code: int,
    ) -> None:
        """4xx errors raise immediately without retry."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            status_code=status_code, text="Client Error"
        )

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        with pytest.raises(AgamemnonAPIError) as exc_info:
            client.list_agents()

        assert exc_info.value.status_code == status_code
        assert mock_http.request.call_count == 1  # No retries
        mock_sleep.assert_not_called()

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_no_retry_on_500(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """HTTP 500 is not in the retryable set — raises immediately."""
        mock_http = mock_client_cls.return_value
        mock_http.request.return_value = _mock_response(
            status_code=500, text="Internal Server Error"
        )

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        with pytest.raises(AgamemnonAPIError) as exc_info:
            client.list_agents()

        assert exc_info.value.status_code == 500
        assert mock_http.request.call_count == 1
        mock_sleep.assert_not_called()


class TestRetryBackoff:
    """Verify exponential backoff timing."""

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_backoff_delays(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """Delays follow 1s, 2s, 4s exponential pattern."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        with pytest.raises(AgamemnonConnectionError):
            client.list_agents()

        assert mock_sleep.call_args_list == [
            call(1.0),
            call(2.0),
            call(4.0),
        ]


class TestRetryLogging:
    """Verify that retry attempts are logged."""

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_retry_logs_warning(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Each retry attempt logs a WARNING with attempt info."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = [
            httpx.ConnectError("refused"),
            _mock_response(json_data=[]),
        ]

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        import logging

        with caplog.at_level(logging.WARNING, logger="scylla.agamemnon.client"):
            client.list_agents()

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "attempt 1/4" in record.message
        assert "retrying in 1.0s" in record.message

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_retry_502_logs_warning(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """HTTP 502 retry logs a WARNING with status code."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = [
            _mock_response(status_code=502, text="Bad Gateway"),
            _mock_response(json_data=[]),
        ]

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        import logging

        with caplog.at_level(logging.WARNING, logger="scylla.agamemnon.client"):
            client.list_agents()

        assert len(caplog.records) == 1
        assert "502" in caplog.records[0].message


class TestRetryConfig:
    """Verify configurable retry behavior."""

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_max_retries_zero_disables_retry(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """With max_retries=0, errors raise immediately."""
        config = AgamemnonConfig(
            base_url="http://localhost:8080",
            enabled=True,
            max_retries=0,
        )
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AgamemnonClient(config)
        client._client = mock_http

        with pytest.raises(AgamemnonConnectionError):
            client.list_agents()

        assert mock_http.request.call_count == 1
        mock_sleep.assert_not_called()

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_max_retries_custom_value(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """With max_retries=1, only 1 retry is attempted."""
        config = AgamemnonConfig(
            base_url="http://localhost:8080",
            enabled=True,
            max_retries=1,
        )
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AgamemnonClient(config)
        client._client = mock_http

        with pytest.raises(AgamemnonConnectionError):
            client.list_agents()

        assert mock_http.request.call_count == 2  # 1 initial + 1 retry
        mock_sleep.assert_called_once_with(1.0)


class TestRetryWithPublicMethods:
    """Verify that public methods benefit from retry logic."""

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_inject_failure_retries_on_transient(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """inject_failure retries on transient errors."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = [
            httpx.ConnectError("refused"),
            _mock_response(json_data={"injection_id": "inj-001", "status": "active"}),
        ]

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        result = client.inject_failure(spec)

        assert result.injection_id == "inj-001"
        assert mock_http.request.call_count == 2

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_clear_failure_retries_on_transient(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """clear_failure retries on transient errors."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = [
            httpx.ReadTimeout("timed out"),
            _mock_response(json_data={}),
        ]

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        client.clear_failure("inj-001")
        assert mock_http.request.call_count == 2

    @patch("scylla.agamemnon.client.time.sleep")
    @patch("scylla.agamemnon.client.httpx.Client")
    def test_health_check_retries_before_returning_none(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
        retry_config: AgamemnonConfig,
    ) -> None:
        """health_check retries internally before returning None."""
        mock_http = mock_client_cls.return_value
        mock_http.request.side_effect = httpx.ConnectError("refused")

        client = AgamemnonClient(retry_config)
        client._client = mock_http

        result = client.health_check()

        assert result is None
        # All retries exhausted, then health_check catches the error
        assert mock_http.request.call_count == 4  # 1 + 3 retries
