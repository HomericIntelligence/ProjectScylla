"""Base result types for evaluation runs.

This module provides foundational Pydantic-based types that are extended by
domain-specific result classes throughout the codebase. These base types ensure
consistent field naming, structure, and validation across different modules.

Architecture Notes:
    All RunResult types now inherit from RunResultBase (Pydantic BaseModel):

    RunResult inheritance hierarchy:
    - RunResultBase (this module) - Base Pydantic model with common fields
      ├── MetricsRunResult (metrics/aggregator.py) - Statistical aggregation
      ├── ExecutorRunResult (executor/runner.py) - Execution tracking with status
      ├── E2ERunResult (e2e/models.py) - E2E testing with detailed paths
      └── ReportingRunResult (reporting/result.py) - Persistence with nested info

    ExecutionInfo inheritance hierarchy (Issue #658):
    - ExecutionInfoBase (this module) - Base Pydantic model with common fields
      ├── ExecutorExecutionInfo (executor/runner.py) - Container execution (detailed)
      └── ReportingExecutionInfo (reporting/result.py) - Result persistence (minimal)

    Legacy dataclass (deprecated):
    - BaseExecutionInfo - Kept for backward compatibility, use ExecutionInfoBase instead

    Migration from dataclasses to Pydantic (Issues #604, #658):
    - Leverages recent Pydantic migration (commit 38a3df1)
    - Enables shared validation logic via Pydantic
    - Provides consistent serialization with .model_dump()
    - Maintains frozen=True for immutability
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class RunResultBase(BaseModel):
    """Base result type for all execution results.

    This is the foundational Pydantic model that all domain-specific RunResult
    types inherit from. It defines the minimum common fields shared across all
    evaluation results.

    Note: Fields have sensible defaults to support incremental result construction
    in different execution contexts (e.g., executor may not have cost data initially).

    Attributes:
        run_number: Run number/identifier (1-indexed).
        cost_usd: Total cost in USD for this run (default: 0.0).
        duration_seconds: Total execution duration in seconds (default: 0.0).

    """

    model_config = ConfigDict()

    run_number: int = Field(
        default=0, description="Run number/identifier (1-indexed, 0 if not applicable)"
    )
    cost_usd: float = Field(default=0.0, description="Total cost in USD")
    duration_seconds: float = Field(default=0.0, description="Total execution duration in seconds")


class ExecutionInfoBase(BaseModel):
    """Base execution information type for all execution results.

    This is the foundational Pydantic model that all domain-specific ExecutionInfo
    types inherit from. It defines the minimum common fields shared across all
    execution results.

    Note: Fields have sensible defaults to support incremental result construction
    in different execution contexts.

    Attributes:
        exit_code: Process/container exit code (0 = success).
        duration_seconds: Total execution duration in seconds (default: 0.0).
        timed_out: Whether execution timed out (default: False).

    """

    model_config = ConfigDict(frozen=True)

    exit_code: int = Field(..., description="Process/container exit code (0 = success)")
    duration_seconds: float = Field(default=0.0, description="Total execution duration in seconds")
    timed_out: bool = Field(default=False, description="Whether execution timed out")


@dataclass
class BaseExecutionInfo:
    """Base execution information shared across all result types.

    .. deprecated::
        Use ExecutionInfoBase (Pydantic model) instead. This dataclass is kept
        for backward compatibility only. New code should use ExecutionInfoBase
        and its domain-specific subtypes (ExecutorExecutionInfo, ReportingExecutionInfo).

    For the new Pydantic-based hierarchy, see:
    - ExecutionInfoBase (this module) - Base Pydantic model
    - ExecutorExecutionInfo (executor/runner.py) - Container execution
    - ReportingExecutionInfo (reporting/result.py) - Result persistence

    Attributes:
        exit_code: Process/container exit code (0 = success).
        duration_seconds: Total execution duration.
        timed_out: Whether execution timed out.

    """

    exit_code: int
    duration_seconds: float
    timed_out: bool = False

    def __post_init__(self) -> None:
        """Emit a DeprecationWarning on instantiation."""
        warnings.warn(
            "BaseExecutionInfo is deprecated and will be removed in v2.0.0. "
            "Use ExecutionInfoBase instead.",
            DeprecationWarning,
            stacklevel=2,
        )


@dataclass
class BaseRunMetrics:
    """Base metrics shared across run result types.

    Attributes:
        tokens_input: Number of input tokens consumed.
        tokens_output: Number of output tokens generated.
        cost_usd: Total cost in USD.

    """

    tokens_input: int
    tokens_output: int
    cost_usd: float
