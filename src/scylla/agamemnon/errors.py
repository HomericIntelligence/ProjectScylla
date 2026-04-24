"""Exception hierarchy for the Agamemnon chaos client."""

from __future__ import annotations


class AgamemnonError(Exception):
    """Base exception for Agamemnon client errors."""


class AgamemnonConnectionError(AgamemnonError):
    """Raised on network failures or timeouts."""


class AgamemnonAPIError(AgamemnonError):
    """Raised on non-2xx HTTP responses.

    Attributes:
        status_code: HTTP status code from the server.
        response_body: Raw response body text.

    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: str = "",
    ) -> None:
        """Create an API error with status code and optional response body."""
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
