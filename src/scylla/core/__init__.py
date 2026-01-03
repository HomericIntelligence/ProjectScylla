"""Core types and base classes for ProjectScylla.

This module provides foundational types used across the codebase.
"""

from scylla.core.results import (
    BaseExecutionInfo,
    BaseRunMetrics,
    BaseRunResult,
)

__all__ = [
    "BaseExecutionInfo",
    "BaseRunMetrics",
    "BaseRunResult",
]
