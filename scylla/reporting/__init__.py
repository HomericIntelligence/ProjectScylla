"""Reporting module for generating evaluation reports.

This module provides result writing and report generation capabilities.
"""

from scylla.reporting.json_report import (
    JsonReportGenerator as JsonReportGenerator,
)
from scylla.reporting.json_report import (
    _sanitize_for_json as _sanitize_for_json,
)
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
    "EvalResult",
    "EvaluationReport",
    "ExecutionInfo",
    "GradingInfo",
    "JsonReportGenerator",
    "JudgmentInfo",
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
    "_sanitize_for_json",
    "create_model_statistics",
    "create_report_data",
    "create_run_result",
    "create_statistics",
    "create_test_result",
    "create_tier_metrics",
]
