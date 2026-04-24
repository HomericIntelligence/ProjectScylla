"""Agamemnon chaos fault injection client for the Odysseus agent mesh.

This module provides synchronous and asynchronous clients for the
Agamemnon REST API, along with Protocol types that allow consumers
to write code agnostic to sync vs async.
"""

from scylla.agamemnon.client import AgamemnonClient as AgamemnonClient
from scylla.agamemnon.client import AsyncAgamemnonClient as AsyncAgamemnonClient
from scylla.agamemnon.errors import AgamemnonAPIError as AgamemnonAPIError
from scylla.agamemnon.errors import AgamemnonConnectionError as AgamemnonConnectionError
from scylla.agamemnon.errors import AgamemnonError as AgamemnonError
from scylla.agamemnon.models import AgamemnonConfig as AgamemnonConfig
from scylla.agamemnon.models import FailureSpec as FailureSpec
from scylla.agamemnon.models import HealthResponse as HealthResponse
from scylla.agamemnon.models import InjectionResult as InjectionResult
from scylla.agamemnon.protocols import (
    AgamemnonClientProtocol as AgamemnonClientProtocol,
)
from scylla.agamemnon.protocols import (
    AsyncAgamemnonClientProtocol as AsyncAgamemnonClientProtocol,
)

__all__ = [
    "AgamemnonAPIError",
    "AgamemnonClient",
    "AgamemnonClientProtocol",
    "AgamemnonConfig",
    "AgamemnonConnectionError",
    "AgamemnonError",
    "AsyncAgamemnonClient",
    "AsyncAgamemnonClientProtocol",
    "FailureSpec",
    "HealthResponse",
    "InjectionResult",
]
