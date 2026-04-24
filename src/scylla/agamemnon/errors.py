"""Exception hierarchy for the Agamemnon Chaos Client."""

from __future__ import annotations


class AgamemnonError(Exception):
    """Base exception for all Agamemnon client errors."""


class AgamemnonConnectionError(AgamemnonError):
    """Network failures and timeouts when communicating with Agamemnon."""


class AgamemnonAPIError(AgamemnonError):
    """Non-2xx HTTP response from the Agamemnon API.

    Attributes:
        status_code: HTTP status code returned by the API.
        response_body: Raw response body text.

    """

    def __init__(self, status_code: int, response_body: str) -> None:
        """Initialize with status code and response body."""
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Agamemnon API error {status_code}: {response_body}")
