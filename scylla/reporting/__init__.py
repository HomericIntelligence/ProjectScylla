"""Reporting module for generating evaluation reports.

This module provides result writing and report generation capabilities.
"""

from scylla.reporting.markdown import (
    MarkdownReportGenerator,
    ReportData,
    SensitivityAnalysis,
    TierMetrics,
    TransitionAssessment,
    create_report_data,
    create_tier_metrics,
)
from scylla.reporting.result import (
    ExecutionInfo,
    GradingInfo,
    JudgmentInfo,
    MetricsInfo,
    ReportingRunResult,
    ResultWriter,
    create_run_result,
)
from scylla.reporting.scorecard import (
    EvalResult,
    ModelScorecard,
    OverallStats,
    ScorecardGenerator,
    create_test_result,
)
from scylla.reporting.summary import (
    EvaluationReport,
    ModelStatistics,
    Rankings,
    SummaryGenerator,
    SummaryStatistics,
    create_model_statistics,
    create_statistics,
)

__all__ = [
    # Markdown
    "MarkdownReportGenerator",
    "ReportData",
    "SensitivityAnalysis",
    "TierMetrics",
    "TransitionAssessment",
    "create_report_data",
    "create_tier_metrics",
    # Result
    "ExecutionInfo",
    "GradingInfo",
    "JudgmentInfo",
    "MetricsInfo",
    "ReportingRunResult",
    "ResultWriter",
    "create_run_result",
    # Scorecard
    "EvalResult",
    "ModelScorecard",
    "OverallStats",
    "ScorecardGenerator",
    "create_test_result",
    # Summary
    "EvaluationReport",
    "ModelStatistics",
    "Rankings",
    "SummaryGenerator",
    "SummaryStatistics",
    "create_model_statistics",
    "create_statistics",
]
