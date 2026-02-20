"""Core types and base classes for ProjectScylla.

This module provides foundational types used across the codebase.
"""

from scylla.core.results import (
    BaseRunMetrics,
    ExecutionInfoBase,
    GradingInfoBase,
)

__all__ = [
    "BaseRunMetrics",
    "ExecutionInfoBase",
    "GradingInfoBase",
]
