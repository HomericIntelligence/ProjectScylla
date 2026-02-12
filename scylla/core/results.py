"""Base result types for evaluation runs.

This module provides foundational types that are extended by domain-specific
result classes throughout the codebase. These base types ensure consistent
field naming and structure across different modules.
Architecture Notes:
    The codebase has multiple result types for different purposes:

    RunResult variants:
    - metrics/aggregator.py:RunResult - For statistical aggregation (minimal fields)
    - executor/runner.py:RunResult - For execution tracking (Pydantic, with ExecutionInfo)
    - e2e/models.py:RunResult - For E2E test results (detailed, with paths)
    - reporting/result.py:RunResult - For persistence (nested info objects)

    ExecutionInfo variants:
    - executor/runner.py:ExecutionInfo - For container execution (detailed)
    - reporting/result.py:ExecutionInfo - For result persistence (minimal)

    This module provides base types with shared fields that domain-specific
    types can extend or compose.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BaseExecutionInfo:
    """Base execution information shared across all result types.

    Attributes:
        exit_code: Process/container exit code (0 = success).
        duration_seconds: Total execution duration.
        timed_out: Whether execution timed out.

    """

    exit_code: int
    duration_seconds: float
    timed_out: bool = False


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


@dataclass
class BaseRunResult:
    """Base run result with common fields.

    Attributes:
        run_number: Run number/identifier.
        cost_usd: Cost in USD.
        duration_seconds: Execution duration.

    """

    run_number: int
    cost_usd: float
    duration_seconds: float


# Type aliases for backward compatibility and documentation
# These help document the relationship between base types and domain types

# metrics/aggregator.py uses these fields for aggregation:
# - run_id (str), pass_rate (float), impl_rate (float), cost_usd (float), duration_seconds (float)

# executor/runner.py uses these fields for tracking:
# - run_number (int), status (RunStatus), execution_info (ExecutionInfo), judgment (JudgmentResult)

# e2e/models.py uses these fields for E2E results:
# - run_number, exit_code, tokens_*, cost_usd, duration_seconds, judge_*, workspace_path, logs_path

# reporting/result.py uses composition:
# - test_id, tier_id, model_id, run_number, execution (ExecutionInfo), metrics (MetricsInfo), etc.
