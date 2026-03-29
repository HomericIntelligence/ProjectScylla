"""DEPRECATED: Use scylla.agamemnon.models instead (ADR-006)."""

from scylla.agamemnon.models import AgamemnonConfig as AgamemnonConfig
from scylla.agamemnon.models import FailureSpec as FailureSpec
from scylla.agamemnon.models import HealthResponse as HealthResponse
from scylla.agamemnon.models import InjectionResult as InjectionResult

# Backward-compat aliases (ADR-006)
MaestroConfig = AgamemnonConfig
