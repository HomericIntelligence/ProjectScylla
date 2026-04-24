"""Tests for AgamemnonClient and AsyncAgamemnonClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scylla.adapters.agamemnon_client import (
    AgamemnonClient,
    AgamemnonConnectionError,
    AsyncAgamemnonClient,
)

# ── Sync client tests ────────────────────────────────────────────────


class TestAgamemnonClientInit:
    """Tests for AgamemnonClient initialization."""

    def test_stores_base_url(self) -> None:
        """Base URL is stored without modification."""
        client = AgamemnonClient(base_url="http://localhost:8080")
        assert client.base_url == "http://localhost:8080"

    def test_strips_trailing_slash(self) -> None:
        """Trailing slash is removed from base URL."""
        client = AgamemnonClient(base_url="http://localhost:8080/")
        assert client.base_url == "http://localhost:8080"

    def test_default_timeout(self) -> None:
        """Default timeout is 60 seconds."""
        client = AgamemnonClient(base_url="http://localhost:8080")
        assert client.timeout == 60.0

    def test_default_max_retries(self) -> None:
        """Default max retries is 3."""
        client = AgamemnonClient(base_url="http://localhost:8080")
        assert client.max_retries == 3


class TestAgamemnonClientRequest:
    """Tests for AgamemnonClient._request."""

    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_success(self, mock_client_cls: MagicMock) -> None:
        """Successful request returns response object."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.raise_for_status.return_value = None

        mock_inst = MagicMock()
        mock_inst.request.return_value = mock_resp
        mock_inst.__enter__ = MagicMock(return_value=mock_inst)
        mock_inst.__exit__ = MagicMock(return_value=None)
        mock_client_cls.return_value = mock_inst

        client = AgamemnonClient(base_url="http://localhost:8080")
        result = client._request("POST", "/v1/chaos/inject", json={"tier": "T0"})
        assert result is mock_resp

    @patch("scylla.adapters.agamemnon_client.time.sleep")
    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_retries_then_succeeds(self, mock_client_cls: MagicMock, mock_sleep: MagicMock) -> None:
        """Request retries on transient error and succeeds on next attempt."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.raise_for_status.return_value = None

        mock_inst = MagicMock()
        mock_inst.request.side_effect = [
            httpx.ConnectError("fail"),
            mock_resp,
        ]
        mock_inst.__enter__ = MagicMock(return_value=mock_inst)
        mock_inst.__exit__ = MagicMock(return_value=None)
        mock_client_cls.return_value = mock_inst

        client = AgamemnonClient(base_url="http://localhost:8080")
        result = client._request("POST", "/v1/chaos/inject")
        assert result is mock_resp
        mock_sleep.assert_called_once_with(1)

    @patch("scylla.adapters.agamemnon_client.time.sleep")
    @patch("scylla.adapters.agamemnon_client.httpx.Client")
    def test_exhausts_retries(self, mock_client_cls: MagicMock, mock_sleep: MagicMock) -> None:
        """Raises AgamemnonConnectionError after all retries are exhausted."""
        mock_inst = MagicMock()
        mock_inst.request.side_effect = httpx.ConnectError("refused")
        mock_inst.__enter__ = MagicMock(return_value=mock_inst)
        mock_inst.__exit__ = MagicMock(return_value=None)
        mock_client_cls.return_value = mock_inst

        client = AgamemnonClient(base_url="http://localhost:8080")
        with pytest.raises(AgamemnonConnectionError, match="after 3 retries"):
            client._request("POST", "/v1/chaos/inject")


class TestAgamemnonClientConvenience:
    """Tests for convenience methods inject_failure / cleanup_failure."""

    @patch.object(AgamemnonClient, "_request")
    def test_inject_failure(self, mock_req: MagicMock) -> None:
        """inject_failure POSTs to /v1/chaos/inject with the spec payload."""
        mock_req.return_value = MagicMock(spec=httpx.Response)
        client = AgamemnonClient(base_url="http://localhost:8080")
        client.inject_failure({"tier": "T0", "subtest": "s1"})
        mock_req.assert_called_once_with(
            "POST", "/v1/chaos/inject", json={"tier": "T0", "subtest": "s1"}
        )

    @patch.object(AgamemnonClient, "_request")
    def test_cleanup_failure(self, mock_req: MagicMock) -> None:
        """cleanup_failure DELETEs /v1/chaos/reset."""
        mock_req.return_value = MagicMock(spec=httpx.Response)
        client = AgamemnonClient(base_url="http://localhost:8080")
        client.cleanup_failure()
        mock_req.assert_called_once_with("DELETE", "/v1/chaos/reset")


# ── Async client tests ───────────────────────────────────────────────


class TestAsyncAgamemnonClientInit:
    """Tests for AsyncAgamemnonClient initialization."""

    def test_stores_base_url(self) -> None:
        """Base URL is stored without modification."""
        client = AsyncAgamemnonClient(base_url="http://localhost:8080")
        assert client.base_url == "http://localhost:8080"

    def test_strips_trailing_slash(self) -> None:
        """Trailing slash is removed from base URL."""
        client = AsyncAgamemnonClient(base_url="http://localhost:8080/")
        assert client.base_url == "http://localhost:8080"


class TestAsyncAgamemnonClientRequest:
    """Tests for AsyncAgamemnonClient._request."""

    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        """Successful async request returns response object."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "scylla.adapters.agamemnon_client.httpx.AsyncClient",
            return_value=mock_client,
        ):
            client = AsyncAgamemnonClient(base_url="http://localhost:8080")
            result = await client._request("POST", "/v1/chaos/inject")
            assert result is mock_resp

    @pytest.mark.asyncio()
    async def test_retries_then_succeeds(self) -> None:
        """Async request retries on transient error and succeeds."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            httpx.ConnectError("fail"),
            mock_resp,
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "scylla.adapters.agamemnon_client.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch(
                "scylla.adapters.agamemnon_client.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            client = AsyncAgamemnonClient(base_url="http://localhost:8080")
            result = await client._request("POST", "/v1/chaos/inject")
            assert result is mock_resp

    @pytest.mark.asyncio()
    async def test_exhausts_retries(self) -> None:
        """Raises AgamemnonConnectionError after retries exhausted."""
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "scylla.adapters.agamemnon_client.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch(
                "scylla.adapters.agamemnon_client.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            client = AsyncAgamemnonClient(base_url="http://localhost:8080")
            with pytest.raises(AgamemnonConnectionError, match="after 3 retries"):
                await client._request("POST", "/v1/chaos/inject")


class TestAsyncAgamemnonClientConvenience:
    """Tests for async convenience methods."""

    @pytest.mark.asyncio()
    async def test_inject_failure(self) -> None:
        """inject_failure awaits POST to /v1/chaos/inject."""
        client = AsyncAgamemnonClient(base_url="http://localhost:8080")
        mock_resp = MagicMock(spec=httpx.Response)
        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.inject_failure({"tier": "T0"})
            assert result is mock_resp

    @pytest.mark.asyncio()
    async def test_cleanup_failure(self) -> None:
        """cleanup_failure awaits DELETE to /v1/chaos/reset."""
        client = AsyncAgamemnonClient(base_url="http://localhost:8080")
        mock_resp = MagicMock(spec=httpx.Response)
        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.cleanup_failure()
            assert result is mock_resp
