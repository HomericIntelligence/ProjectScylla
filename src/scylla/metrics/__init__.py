"""Metrics module for statistical calculations and grading.

This module provides statistical functions and grading calculations
for analyzing evaluation results across multiple runs.
"""

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
