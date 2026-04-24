"""Client for Agamemnon failure injection service.

This module provides an HTTP client for /v1/chaos/* endpoints
used to inject transient failures during E2E test runs.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AgamemnonConnectionError(Exception):
    """Raised when AgamemnonClient exhausts retries on transient errors."""

    pass


class AgamemnonClient:
    """HTTP client for Agamemnon /v1/chaos/* endpoints.

    Handles transient failures with automatic retry logic (3 attempts,
    exponential backoff: 1s, 2s, 4s).
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
        """Execute HTTP request to /v1/chaos/* endpoint with retry logic.

        Retries on transient failures (connection errors, timeouts) with
        exponential backoff. Raises AgamemnonConnectionError when retries
        are exhausted.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: Endpoint path (e.g., "/v1/chaos/inject").
            **kwargs: Additional arguments passed to httpx.request.

        Returns:
            httpx.Response object from successful request.

        Raises:
            AgamemnonConnectionError: When retries exhausted on transient errors.
            httpx.HTTPError: On non-transient HTTP errors.

        """
        url = f"{self.base_url}{endpoint}"
        backoff_delays = [1, 2, 4]  # seconds

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
                # Transient error - retry if attempts remain
                if attempt < self.max_retries - 1:
                    delay = backoff_delays[attempt]
                    logger.warning(
                        f"Transient error on {method} {url} (attempt {attempt + 1}/"
                        f"{self.max_retries}): {e}. Retrying in {delay}s."
                    )
                    time.sleep(delay)
                else:
                    # Exhausted retries
                    logger.error(
                        f"Failed to connect after {self.max_retries} attempts: {e}"
                    )
                    raise AgamemnonConnectionError(
                        f"Failed to reach {url} after {self.max_retries} retries: {e}"
                    ) from e

        # Should not reach here, but satisfy type checker
        raise AgamemnonConnectionError(f"Unexpected error reaching {url}")
