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
    # Scorecard
    "EvalResult",
    # Summary
    "EvaluationReport",
    # Result
    "ExecutionInfo",
    "GradingInfo",
    "JudgmentInfo",
    # Markdown
    "MarkdownReportGenerator",
    "MetricsInfo",
    "ModelScorecard",
    "ModelStatistics",
    "OverallStats",
    "Rankings",
    "ReportData",
    "ReportingRunResult",
    "ResultWriter",
    "ScorecardGenerator",
    "SensitivityAnalysis",
    "SummaryGenerator",
    "SummaryStatistics",
    "TierMetrics",
    "TransitionAssessment",
    "create_model_statistics",
    "create_report_data",
    "create_run_result",
    "create_statistics",
    "create_test_result",
    "create_tier_metrics",
]
