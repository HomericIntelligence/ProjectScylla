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

    GradingInfo inheritance hierarchy (Issue #796):
    - GradingInfoBase (this module) - Base Pydantic model with common fields
      └── GradingInfo (reporting/result.py) - Reporting persistence

    RunMetrics inheritance hierarchy (Issue #787):
    - RunMetricsBase (this module) - Base Pydantic model with common fields

    Legacy dataclasses (deprecated):
    - BaseExecutionInfo - Kept for backward compatibility, use ExecutionInfoBase instead
    - BaseRunMetrics - Kept for backward compatibility, use RunMetricsBase instead

    Migration from dataclasses to Pydantic (Issues #604, #658, #787):
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

    model_config = ConfigDict(frozen=True)

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
class GradingInfoBase(BaseModel):
    """Base grading metrics type for all grading results.

    This is the foundational Pydantic model that domain-specific GradingInfo
    types inherit from. It defines the minimum common fields shared across all
    grading results.

    Attributes:
        pass_rate: Pass rate for the run (0.0 or 1.0).
        cost_of_pass: Cost per successful pass in USD.
        composite_score: Combined quality score (0.0-1.0).

    """

    pass_rate: float = Field(..., description="Pass rate (0.0 or 1.0)")
    cost_of_pass: float = Field(..., description="Cost per successful pass")
    composite_score: float = Field(..., description="Combined quality score")


class RunMetricsBase(BaseModel):
    """Base token and cost metrics for all run result types.

    This is the foundational Pydantic model that all domain-specific RunMetrics
    types can inherit from. It defines the minimum common fields shared across
    all evaluation run metrics.

    Attributes:
        tokens_input: Number of input tokens consumed.
        tokens_output: Number of output tokens generated.
        cost_usd: Total cost in USD.

    """

    model_config = ConfigDict(frozen=True)

    tokens_input: int = Field(..., description="Number of input tokens consumed")
    tokens_output: int = Field(..., description="Number of output tokens generated")
    cost_usd: float = Field(..., description="Total cost in USD")

    """Base metrics shared across run result types.

    Attributes:
        tokens_input: Number of input tokens consumed.
        tokens_output: Number of output tokens generated.
        cost_usd: Total cost in USD.

    """

    tokens_input: int
    tokens_output: int
    cost_usd: float

    def __post_init__(self) -> None:
        """Emit a DeprecationWarning on instantiation."""
        warnings.warn(
            "BaseRunMetrics is deprecated and will be removed in v2.0.0. "
            "Use RunMetricsBase instead.",
            DeprecationWarning,
            stacklevel=2,
        )
