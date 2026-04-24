"""Asynchronous HTTP client for the Agamemnon Chaos API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from scylla.agamemnon._retry import (
    compute_backoff,
    is_transient_status,
)
from scylla.agamemnon.errors import (
    AgamemnonAPIError,
    AgamemnonConnectionError,
)
from scylla.agamemnon.models import (
    AgamemnonConfig,
    FailureSpec,
    HealthResponse,
    InjectionResult,
)

logger = logging.getLogger(__name__)


class AsyncAgamemnonClient:
    """Asynchronous client for the Agamemnon Chaos API.

    Mirrors the synchronous :class:`AgamemnonClient` interface using
    ``httpx.AsyncClient``. Designed for parallel tier execution without
    blocking the event loop during retries.

    Transient failures (connection errors, timeouts, HTTP 502/503/504) are
    retried with exponential backoff using ``asyncio.sleep``.

    Args:
        config: Agamemnon client configuration.

    """

    def __init__(self, config: AgamemnonConfig) -> None:
        """Initialize the asynchronous Agamemnon client."""
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.timeout_seconds),
        )
        self._health_timeout = httpx.Timeout(config.health_check_timeout_seconds)

    async def close(self) -> None:
        """Close the underlying async HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncAgamemnonClient:
        """Enter the async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the async context manager and close the client."""
        await self.close()

    # -- Public API -----------------------------------------------------------

    async def health_check(self) -> HealthResponse | None:
        """Check Agamemnon API health.

        Returns:
            HealthResponse if the API is reachable, None otherwise.

        """
        try:
            response = await self._client.get("/v1/health", timeout=self._health_timeout)
            response.raise_for_status()
            return HealthResponse.model_validate(response.json())
        except (httpx.HTTPError, Exception):
            logger.warning("Agamemnon health check failed", exc_info=True)
            return None

    async def inject_failure(self, spec: FailureSpec) -> InjectionResult:
        """Inject a failure into an agent.

        Args:
            spec: Failure specification describing what to inject.

        Returns:
            InjectionResult with the injection ID and status.

        Raises:
            AgamemnonConnectionError: On network/timeout failures after retries.
            AgamemnonAPIError: On non-2xx responses after retries.

        """
        response = await self._request_with_retry(
            "POST",
            "/v1/chaos/inject",
            json=spec.model_dump(),
        )
        return InjectionResult.model_validate(response.json())

    async def clear_failure(self, injection_id: str) -> None:
        """Remove an injected failure.

        Args:
            injection_id: ID of the injection to clear.

        Raises:
            AgamemnonConnectionError: On network/timeout failures after retries.
            AgamemnonAPIError: On non-2xx responses after retries.

        """
        await self._request_with_retry("DELETE", f"/v1/chaos/inject/{injection_id}")

    async def list_agents(self) -> list[dict[str, Any]]:
        """List all registered agents.

        Returns:
            List of agent dictionaries.

        Raises:
            AgamemnonConnectionError: On network/timeout failures after retries.
            AgamemnonAPIError: On non-2xx responses after retries.

        """
        response = await self._request_with_retry("GET", "/v1/agents")
        result: list[dict[str, Any]] = response.json()
        return result

    async def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the client."""
        raise NotImplementedError  # pragma: no cover

    # -- Internal retry logic -------------------------------------------------

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an async HTTP request with exponential-backoff retry.

        Retries on connection errors, timeouts, and transient HTTP status codes
        (502, 503, 504). Uses ``asyncio.sleep`` instead of ``time.sleep`` so
        the event loop is not blocked.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.).
            url: URL path relative to base_url.
            **kwargs: Additional arguments passed to httpx.AsyncClient.request.

        Returns:
            The successful httpx.Response.

        Raises:
            AgamemnonConnectionError: After exhausting retries on connection errors.
            AgamemnonAPIError: On non-2xx, non-transient responses, or after
                exhausting retries on transient responses.

        """
        last_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
                if response.is_success:
                    return response
                if is_transient_status(response.status_code):
                    last_error = AgamemnonAPIError(response.status_code, response.text)
                    if attempt < self._config.max_retries:
                        delay = compute_backoff(attempt)
                        logger.warning(
                            "Transient %d from %s %s, retrying in %.1fs (attempt %d/%d)",
                            response.status_code,
                            method,
                            url,
                            delay,
                            attempt + 1,
                            self._config.max_retries,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise last_error
                raise AgamemnonAPIError(response.status_code, response.text)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_error = AgamemnonConnectionError(str(exc))
                if attempt < self._config.max_retries:
                    delay = compute_backoff(attempt)
                    logger.warning(
                        "Connection error on %s %s, retrying in %.1fs (attempt %d/%d): %s",
                        method,
                        url,
                        delay,
                        attempt + 1,
                        self._config.max_retries,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise last_error from exc
        # Should not be reached, but satisfy type checker
        assert last_error is not None  # noqa: S101
        raise last_error
