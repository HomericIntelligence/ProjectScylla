"""Exception hierarchy for AI Maestro REST API integration."""


class MaestroError(Exception):
    """Base exception for all Maestro API errors."""


class MaestroConnectionError(MaestroError):
    """Raised when the Maestro API is unreachable or a connection times out."""


class MaestroAPIError(MaestroError):
    """Raised when the Maestro API returns a non-2xx response.

    Attributes:
        status_code: HTTP status code from the response.
        response_body: Raw response body text.

    """

    def __init__(self, message: str, status_code: int, response_body: str = "") -> None:
        """Initialize MaestroAPIError.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code from the response.
            response_body: Raw response body text.

        """
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
