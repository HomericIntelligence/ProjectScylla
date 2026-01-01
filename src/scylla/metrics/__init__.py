"""Metrics module for statistical calculations, grading, and aggregation.

This module provides statistical functions, grading calculations,
run aggregation, process metrics, and token tracking for analyzing
evaluation results across multiple runs.
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
from scylla.metrics.process import (
    ChangeResult,
    ProcessMetrics,
    ProgressStep,
    ProgressTracker,
    calculate_cfp,
    calculate_cfp_simple,
    calculate_pr_revert_rate,
    calculate_pr_revert_rate_simple,
    calculate_process_metrics,
    calculate_process_metrics_simple,
    calculate_r_prog,
    calculate_r_prog_simple,
    calculate_strategic_drift,
    calculate_strategic_drift_simple,
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
from scylla.metrics.token_tracking import (
    ComponentCost,
    ComponentType,
    TierTokenAnalysis,
    TokenDistribution,
    TokenTracker,
    TokenUsage,
    analyze_tier_tokens,
    calculate_token_efficiency_ratio,
    compare_t2_t3_efficiency,
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
    # Process metrics
    "ChangeResult",
    "ProcessMetrics",
    "ProgressStep",
    "ProgressTracker",
    "calculate_cfp",
    "calculate_cfp_simple",
    "calculate_pr_revert_rate",
    "calculate_pr_revert_rate_simple",
    "calculate_process_metrics",
    "calculate_process_metrics_simple",
    "calculate_r_prog",
    "calculate_r_prog_simple",
    "calculate_strategic_drift",
    "calculate_strategic_drift_simple",
    # Statistics
    "Statistics",
    "calculate_all",
    "calculate_mean",
    "calculate_median",
    "calculate_mode",
    "calculate_range",
    "calculate_std_dev",
    "calculate_variance",
    # Token tracking
    "ComponentCost",
    "ComponentType",
    "TierTokenAnalysis",
    "TokenDistribution",
    "TokenTracker",
    "TokenUsage",
    "analyze_tier_tokens",
    "calculate_token_efficiency_ratio",
    "compare_t2_t3_efficiency",
]
