"""Shared retry logic for sync and async Agamemnon clients."""

from __future__ import annotations

import logging
from typing import Final

logger = logging.getLogger(__name__)

#: HTTP status codes considered transient and eligible for retry.
TRANSIENT_STATUS_CODES: Final[frozenset[int]] = frozenset({502, 503, 504})

#: Base delay in seconds for exponential backoff.
BACKOFF_BASE: Final[float] = 1.0

#: Multiplier for exponential backoff.
BACKOFF_FACTOR: Final[float] = 2.0


def compute_backoff(attempt: int) -> float:
    """Compute exponential backoff delay for a given attempt (0-indexed).

    Uses formula: base * factor^attempt

    Args:
        attempt: Zero-indexed retry attempt number.

    Returns:
        Delay in seconds before the next retry.

    """
    return BACKOFF_BASE * (BACKOFF_FACTOR**attempt)


def is_transient_status(status_code: int) -> bool:
    """Check whether an HTTP status code is considered transient.

    Args:
        status_code: HTTP status code to check.

    Returns:
        True if the status code is transient and should be retried.

    """
    return status_code in TRANSIENT_STATUS_CODES
