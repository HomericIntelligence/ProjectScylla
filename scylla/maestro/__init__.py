"""AI Maestro REST API integration.

This module provides an HTTP client for communicating with the AI Maestro
service to inject failures into agents during E2E evaluation runs.
"""

from scylla.maestro.client import MaestroClient as MaestroClient
from scylla.maestro.errors import MaestroAPIError as MaestroAPIError
from scylla.maestro.errors import MaestroConnectionError as MaestroConnectionError
from scylla.maestro.errors import MaestroError as MaestroError
from scylla.maestro.models import FailureSpec as FailureSpec
from scylla.maestro.models import HealthResponse as HealthResponse
from scylla.maestro.models import InjectionResult as InjectionResult
from scylla.maestro.models import MaestroConfig as MaestroConfig

__all__ = [
    "FailureSpec",
    "HealthResponse",
    "InjectionResult",
    "MaestroAPIError",
    "MaestroClient",
    "MaestroConfig",
    "MaestroConnectionError",
    "MaestroError",
]
