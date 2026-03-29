"""HTTP client for the ProjectAgamemnon chaos REST API.

Provides ``AgamemnonClient``, a thin wrapper around ``httpx.Client`` that
exposes health-checking, agent listing, failure injection, and diagnostics
endpoints.  Transient failures are automatically retried with exponential
backoff (configurable via ``AgamemnonConfig.max_retries``).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from scylla.agamemnon.errors import AgamemnonAPIError, AgamemnonConnectionError, AgamemnonError
from scylla.agamemnon.models import (
    AgamemnonConfig,
    FailureSpec,
    HealthResponse,
    InjectionResult,
)

logger = logging.getLogger(__name__)

# Status codes that indicate transient server-side issues worth retrying.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({502, 503, 504})

# httpx exception types that represent transient network problems.
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
)

_BASE_RETRY_DELAY: float = 1.0
_RETRY_BACKOFF_FACTOR: int = 2


class AgamemnonClient:
    """Synchronous HTTP client for the ProjectAgamemnon chaos REST API.

    Typical usage::

        config = AgamemnonConfig(base_url="http://localhost:8080", enabled=True)
        with AgamemnonClient(config) as client:
            if client.health_check():
                result = client.inject_failure(spec)

    The client can also be used without a context manager; call :meth:`close`
    explicitly when done.
    """

    def __init__(self, config: AgamemnonConfig) -> None:
        """Initialize the Agamemnon client.

        Args:
            config: Agamemnon configuration with base URL and timeouts.

        """
        self._config = config
        self._base_url = config.base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(config.timeout_seconds),
        )

    # -- Context manager -----------------------------------------------------

    def __enter__(self) -> AgamemnonClient:
        """Enter the context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the context manager and close the underlying HTTP client."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    # -- Helpers -------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send an HTTP request with automatic retry on transient failures.

        Retries on connection errors, timeouts, remote protocol errors, and
        HTTP 502/503/504 responses using exponential backoff (1s, 2s, 4s, ...).
        Non-retryable errors (e.g. HTTP 400/401/403/404) raise immediately.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.).
            path: URL path relative to the base URL.
            json: Optional JSON body for POST/PUT requests.
            timeout: Optional per-request timeout override.

        Returns:
            The ``httpx.Response`` object.

        Raises:
            AgamemnonConnectionError: On network or timeout failures after retries.
            AgamemnonAPIError: On non-2xx status codes (after retries for 502/503/504).

        """
        max_attempts = self._config.max_retries + 1
        last_exception: Exception | None = None

        for attempt in range(max_attempts):
            try:
                response = self._client.request(
                    method,
                    path,
                    json=json,
                    timeout=timeout,
                )
            except _RETRYABLE_EXCEPTIONS as exc:
                last_exception = exc
                if attempt < self._config.max_retries:
                    delay = _BASE_RETRY_DELAY * (_RETRY_BACKOFF_FACTOR**attempt)
                    logger.warning(
                        "Agamemnon request %s %s failed (attempt %d/%d): %s — retrying in %.1fs",
                        method,
                        path,
                        attempt + 1,
                        max_attempts,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                # Last attempt exhausted — raise as connection error
                raise AgamemnonConnectionError(
                    f"Failed to connect to Agamemnon API at {self._base_url} "
                    f"after {max_attempts} attempts: {exc}"
                ) from exc
            except httpx.HTTPError as exc:
                raise AgamemnonError(f"HTTP error communicating with Agamemnon API: {exc}") from exc

            # Check for non-success status codes
            if not response.is_success:
                if (
                    response.status_code in _RETRYABLE_STATUS_CODES
                    and attempt < self._config.max_retries
                ):
                    delay = _BASE_RETRY_DELAY * (_RETRY_BACKOFF_FACTOR**attempt)
                    logger.warning(
                        "Agamemnon API returned %d for %s %s (attempt %d/%d) — retrying in %.1fs",
                        response.status_code,
                        method,
                        path,
                        attempt + 1,
                        max_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise AgamemnonAPIError(
                    f"Agamemnon API returned {response.status_code} for {method} {path}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            return response

        # Should only be reached if max_retries > 0 and all attempts raised
        # retryable exceptions (the last attempt re-raises above, so this is
        # a safety net for the type checker).
        raise AgamemnonConnectionError(  # pragma: no cover
            f"All {max_attempts} attempts to {method} {path} failed: {last_exception}"
        )

    # -- Public API ----------------------------------------------------------

    def health_check(self) -> HealthResponse | None:
        """Check Agamemnon API health.

        Returns:
            A ``HealthResponse`` if the service is healthy, or ``None`` if the
            service is unreachable.

        """
        try:
            response = self._request(
                "GET",
                "/v1/health",
                timeout=self._config.health_check_timeout_seconds,
            )
            data: dict[str, Any] = response.json() or {}
            return HealthResponse(**data)
        except AgamemnonError:
            logger.debug("Agamemnon health check failed", exc_info=True)
            return None

    def list_agents(self) -> list[dict[str, Any]]:
        """List all agents registered with Agamemnon.

        Returns:
            A list of agent dictionaries.

        Raises:
            AgamemnonConnectionError: On network failures.
            AgamemnonAPIError: On non-2xx responses.

        """
        response = self._request("GET", "/v1/agents")
        result: list[dict[str, Any]] = response.json() or []
        return result

    def inject_failure(self, spec: FailureSpec) -> InjectionResult:
        """Inject a failure into a target agent via the chaos API.

        Args:
            spec: The failure specification describing what to inject.

        Returns:
            An ``InjectionResult`` with the injection ID and status.

        Raises:
            AgamemnonConnectionError: On network failures.
            AgamemnonAPIError: On non-2xx responses.

        """
        payload: dict[str, Any] = {
            "agent_id": spec.agent_id,
            "failure_type": spec.failure_type,
            "parameters": spec.parameters or {},
        }
        if spec.duration_seconds is not None:
            payload["duration_seconds"] = spec.duration_seconds

        response = self._request("POST", "/v1/chaos/inject", json=payload)
        data: dict[str, Any] = response.json() or {}
        return InjectionResult(**data)

    def clear_failure(self, injection_id: str) -> None:
        """Remove a previously injected failure.

        Args:
            injection_id: The injection ID returned by :meth:`inject_failure`.

        Raises:
            AgamemnonConnectionError: On network failures.
            AgamemnonAPIError: On non-2xx responses.

        """
        self._request("DELETE", f"/v1/chaos/inject/{injection_id}")

    def get_diagnostics(self) -> dict[str, Any]:
        """Retrieve Agamemnon diagnostic information.

        Returns:
            A dictionary of diagnostic data.

        Raises:
            AgamemnonConnectionError: On network failures.
            AgamemnonAPIError: On non-2xx responses.

        """
        response = self._request("GET", "/v1/health")
        result: dict[str, Any] = response.json() or {}
        return result
