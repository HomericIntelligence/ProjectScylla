"""Metrics module for statistical calculations, grading, and aggregation.

This module provides statistical functions, grading calculations,
and run aggregation for analyzing evaluation results across multiple runs.
"""

from scylla.metrics.aggregator import (
    AggregatedStats,
    CrossTierAnalysis,
    RunAggregator,
    RunResult,
    TierStatistics,
)
from scylla.metrics.cross_tier import (
    CrossTierAnalyzer,
    PromptSensitivityAnalysis,
    TierTransitionAssessment,
    TierUplift,
)
from scylla.metrics.grading import (
    GradingResult,
    assign_letter_grade,
    calculate_composite_score,
    calculate_cost_delta,
    calculate_cost_of_pass,
    calculate_impl_rate,
    calculate_pass_rate,
    calculate_tier_uplift,
    grade_run,
)
from scylla.metrics.statistics import (
    Statistics,
    calculate_all,
    calculate_mean,
    calculate_median,
    calculate_mode,
    calculate_range,
    calculate_std_dev,
    calculate_variance,
)

__all__ = [
    # Aggregator
    "AggregatedStats",
    "CrossTierAnalysis",
    "RunAggregator",
    "RunResult",
    "TierStatistics",
    # Cross-tier analysis
    "CrossTierAnalyzer",
    "PromptSensitivityAnalysis",
    "TierTransitionAssessment",
    "TierUplift",
    # Grading
    "GradingResult",
    "assign_letter_grade",
    "calculate_composite_score",
    "calculate_cost_delta",
    "calculate_cost_of_pass",
    "calculate_impl_rate",
    "calculate_pass_rate",
    "calculate_tier_uplift",
    "grade_run",
    # Statistics
    "Statistics",
    "calculate_all",
    "calculate_mean",
    "calculate_median",
    "calculate_mode",
    "calculate_range",
    "calculate_std_dev",
    "calculate_variance",
]
