"""Exceptions for the ProjectAgamemnon chaos API client."""

from __future__ import annotations


class AgamemnonError(Exception):
    """Base exception for all Agamemnon client errors."""


class AgamemnonConnectionError(AgamemnonError):
    """Raised on network failures, timeouts, or connection errors."""


class AgamemnonAPIError(AgamemnonError):
    """Raised when the Agamemnon API returns a non-2xx HTTP response.

    Attributes:
        status_code: HTTP status code from the response.
        response_body: Raw response body text.

    """

    def __init__(self, message: str, status_code: int, response_body: str = "") -> None:
        """Initialize AgamemnonAPIError.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code from the response.
            response_body: Raw response body text.

        """
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
