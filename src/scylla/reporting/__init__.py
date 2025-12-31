"""Reporting module for generating evaluation reports.

This module provides result writing and report generation capabilities.
"""

from scylla.reporting.result import (
    ExecutionInfo,
    GradingInfo,
    JudgmentInfo,
    MetricsInfo,
    ResultWriter,
    RunResult,
    create_run_result,
)
from scylla.reporting.scorecard import (
    ModelScorecard,
    OverallStats,
    ScorecardGenerator,
    TestResult,
    create_test_result,
)
from scylla.reporting.summary import (
    ModelStatistics,
    Rankings,
    SummaryGenerator,
    SummaryStatistics,
    TestSummary,
    create_model_statistics,
    create_statistics,
)

__all__ = [
    # Result
    "ExecutionInfo",
    "GradingInfo",
    "JudgmentInfo",
    "MetricsInfo",
    "ResultWriter",
    "RunResult",
    "create_run_result",
    # Scorecard
    "ModelScorecard",
    "OverallStats",
    "ScorecardGenerator",
    "TestResult",
    "create_test_result",
    # Summary
    "ModelStatistics",
    "Rankings",
    "SummaryGenerator",
    "SummaryStatistics",
    "TestSummary",
    "create_model_statistics",
    "create_statistics",
]
