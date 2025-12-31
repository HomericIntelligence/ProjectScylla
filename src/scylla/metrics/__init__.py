"""Metrics module for statistical calculations and aggregation.

This module provides statistical functions for analyzing evaluation results
across multiple runs.
"""

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
    "Statistics",
    "calculate_all",
    "calculate_mean",
    "calculate_median",
    "calculate_mode",
    "calculate_range",
    "calculate_std_dev",
    "calculate_variance",
]
