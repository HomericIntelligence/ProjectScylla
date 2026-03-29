"""DEPRECATED: Use scylla.agamemnon.errors instead (ADR-006)."""

from scylla.agamemnon.errors import AgamemnonAPIError as AgamemnonAPIError
from scylla.agamemnon.errors import AgamemnonConnectionError as AgamemnonConnectionError
from scylla.agamemnon.errors import AgamemnonError as AgamemnonError

# Backward-compat aliases (ADR-006)
MaestroAPIError = AgamemnonAPIError
MaestroConnectionError = AgamemnonConnectionError
MaestroError = AgamemnonError
