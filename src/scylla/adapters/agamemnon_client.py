"""Client for Agamemnon failure injection service.

This module provides sync and async HTTP clients for /v1/chaos/* endpoints
used to inject and clean up transient failures during E2E test runs.

The ``AsyncAgamemnonClient`` is the preferred client for parallel tier
execution because it avoids blocking threads while waiting on network I/O.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AgamemnonConnectionError(Exception):
    """Raised when an Agamemnon client exhausts retries on transient errors."""


# ── Synchronous client ──────────────────────────────────────────────


class AgamemnonClient:
    """Synchronous HTTP client for Agamemnon /v1/chaos/* endpoints.

    Handles transient failures with automatic retry logic (3 attempts,
    exponential backoff: 1 s, 2 s, 4 s).
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize AgamemnonClient.

        Args:
            base_url: Base URL for Agamemnon service (e.g., http://localhost:8080).
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts on transient errors.

        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: Endpoint path (e.g., "/v1/chaos/inject").
            **kwargs: Additional arguments passed to ``httpx.Client.request``.

        Returns:
            httpx.Response on success.

        Raises:
            AgamemnonConnectionError: When retries are exhausted.

        """
        url = f"{self.base_url}{endpoint}"
        backoff_delays = [1, 2, 4]

        for attempt in range(self.max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response
            except (
                httpx.ConnectError,
                httpx.NetworkError,
                httpx.TimeoutException,
                TimeoutError,
            ) as e:
                if attempt < self.max_retries - 1:
                    delay = backoff_delays[attempt]
                    logger.warning(
                        "Transient error on %s %s (attempt %d/%d): %s. Retrying in %ds.",
                        method,
                        url,
                        attempt + 1,
                        self.max_retries,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Failed to connect after %d attempts: %s",
                        self.max_retries,
                        e,
                    )
                    raise AgamemnonConnectionError(
                        f"Failed to reach {url} after {self.max_retries} retries: {e}"
                    ) from e

        raise AgamemnonConnectionError(f"Unexpected error reaching {url}")

    # ── convenience helpers ──────────────────────────────────────────

    def inject_failure(self, spec: dict[str, Any]) -> httpx.Response:
        """POST /v1/chaos/inject — start failure injection.

        Args:
            spec: Failure specification payload.

        Returns:
            httpx.Response from the service.

        """
        return self._request("POST", "/v1/chaos/inject", json=spec)

    def cleanup_failure(self) -> httpx.Response:
        """DELETE /v1/chaos/reset — remove all active failures.

        Returns:
            httpx.Response from the service.

        """
        return self._request("DELETE", "/v1/chaos/reset")


# ── Asynchronous client ─────────────────────────────────────────────


class AsyncAgamemnonClient:
    """Async HTTP client for Agamemnon /v1/chaos/* endpoints.

    Mirrors ``AgamemnonClient`` but uses ``httpx.AsyncClient`` so that
    callers in an ``asyncio`` event loop do not block threads during
    failure injection or cleanup.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize AsyncAgamemnonClient.

        Args:
            base_url: Base URL for Agamemnon service.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts on transient errors.

        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an async HTTP request with retry logic.

        Args:
            method: HTTP method.
            endpoint: Endpoint path.
            **kwargs: Forwarded to ``httpx.AsyncClient.request``.

        Returns:
            httpx.Response on success.

        Raises:
            AgamemnonConnectionError: When retries are exhausted.

        """
        url = f"{self.base_url}{endpoint}"
        backoff_delays = [1, 2, 4]

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response
            except (
                httpx.ConnectError,
                httpx.NetworkError,
                httpx.TimeoutException,
                TimeoutError,
            ) as e:
                if attempt < self.max_retries - 1:
                    delay = backoff_delays[attempt]
                    logger.warning(
                        "Transient error on %s %s (attempt %d/%d): %s. Retrying in %ds.",
                        method,
                        url,
                        attempt + 1,
                        self.max_retries,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Failed to connect after %d attempts: %s",
                        self.max_retries,
                        e,
                    )
                    raise AgamemnonConnectionError(
                        f"Failed to reach {url} after {self.max_retries} retries: {e}"
                    ) from e

        raise AgamemnonConnectionError(f"Unexpected error reaching {url}")

    # ── convenience helpers ──────────────────────────────────────────

    async def inject_failure(self, spec: dict[str, Any]) -> httpx.Response:
        """POST /v1/chaos/inject — start failure injection.

        Args:
            spec: Failure specification payload.

        Returns:
            httpx.Response from the service.

        """
        return await self._request("POST", "/v1/chaos/inject", json=spec)

    async def cleanup_failure(self) -> httpx.Response:
        """DELETE /v1/chaos/reset — remove all active failures.

        Returns:
            httpx.Response from the service.

        """
        return await self._request("DELETE", "/v1/chaos/reset")
