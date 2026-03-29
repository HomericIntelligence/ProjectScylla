"""DEPRECATED: Use scylla.agamemnon instead (ADR-006).

All symbols re-exported for backward compatibility.
"""

from scylla.agamemnon import AgamemnonAPIError as AgamemnonAPIError
from scylla.agamemnon import AgamemnonClient as AgamemnonClient
from scylla.agamemnon import AgamemnonConfig as AgamemnonConfig
from scylla.agamemnon import AgamemnonConnectionError as AgamemnonConnectionError
from scylla.agamemnon import AgamemnonError as AgamemnonError
from scylla.agamemnon import FailureSpec as FailureSpec
from scylla.agamemnon import HealthResponse as HealthResponse
from scylla.agamemnon import InjectionResult as InjectionResult

# Backward-compat aliases (ADR-006)
MaestroAPIError = AgamemnonAPIError
MaestroClient = AgamemnonClient
MaestroConfig = AgamemnonConfig
MaestroConnectionError = AgamemnonConnectionError
MaestroError = AgamemnonError
