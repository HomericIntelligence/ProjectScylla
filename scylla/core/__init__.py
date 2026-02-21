"""Core types and base classes for ProjectScylla.

This module provides foundational types used across the codebase.
"""

from scylla.core.results import (
    ExecutionInfoBase,
    GradingInfoBase,
    JudgmentInfoBase,
    MetricsInfoBase,
    RunMetricsBase,
)

__all__ = [
    "ExecutionInfoBase",
    "GradingInfoBase",
    "JudgmentInfoBase",
    "MetricsInfoBase",
    "RunMetricsBase",
]
