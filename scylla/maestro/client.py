"""DEPRECATED: Use scylla.agamemnon.client instead (ADR-006)."""

from scylla.agamemnon.client import AgamemnonClient as AgamemnonClient

# Backward-compat alias (ADR-006)
MaestroClient = AgamemnonClient
