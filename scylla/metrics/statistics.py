"""Statistical calculations for evaluation metrics.

This module provides statistical functions for analyzing
results from multiple evaluation runs.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass


@dataclass
class Statistics:
    """Statistical summary of a set of values.

    Attributes:
        median: Middle value when sorted.
        mean: Arithmetic mean.
        mode: Most frequent value.
        min: Minimum value.
        max: Maximum value.
        std_dev: Standard deviation.
        count: Number of values.

    """

    median: float
    mean: float
    mode: float
    min: float
    max: float
    std_dev: float
    count: int = 0


def calculate_median(values: list[float]) -> float:
    """Calculate the median (middle value).

    For 9 runs, this is the 5th value when sorted.

    Args:
        values: List of numeric values.

    Returns:
        Median value, or 0.0 if empty.

    """
    if not values:
        return 0.0

    sorted_values = sorted(values)
    n = len(sorted_values)

    if n % 2 == 1:
        # Odd count: return middle value
        return sorted_values[n // 2]
    else:
        # Even count: return average of two middle values
        mid = n // 2
        return (sorted_values[mid - 1] + sorted_values[mid]) / 2


def calculate_mean(values: list[float]) -> float:
    """Calculate the arithmetic mean.

    Args:
        values: List of numeric values.

    Returns:
        Mean value, or 0.0 if empty.

    """
    if not values:
        return 0.0

    return sum(values) / len(values)


def calculate_mode(values: list[float]) -> float:
    """Calculate the mode (most frequent value).

    If multiple values tie for most frequent, returns the smallest.
    For continuous values, this may not be meaningful.

    Args:
        values: List of numeric values.

    Returns:
        Mode value, or 0.0 if empty.

    """
    if not values:
        return 0.0

    # Round values to handle floating point comparison
    rounded = [round(v, 6) for v in values]
    counter = Counter(rounded)
    most_common = counter.most_common()

    if not most_common:
        return values[0]

    # Find all values with the maximum frequency
    max_freq = most_common[0][1]
    modes = [v for v, freq in most_common if freq == max_freq]

    # Return the smallest mode for deterministic results
    return min(modes)


def calculate_range(values: list[float]) -> tuple[float, float]:
    """Calculate the range (min, max).

    Args:
        values: List of numeric values.

    Returns:
        Tuple of (min, max), or (0.0, 0.0) if empty.

    """
    if not values:
        return (0.0, 0.0)

    return (min(values), max(values))


def calculate_variance(values: list[float]) -> float:
    """Calculate the population variance.

    Args:
        values: List of numeric values.

    Returns:
        Variance, or 0.0 if empty or single value.

    """
    if len(values) < 2:
        return 0.0

    mean = calculate_mean(values)
    squared_diffs = [(v - mean) ** 2 for v in values]
    return sum(squared_diffs) / len(values)


def calculate_std_dev(values: list[float]) -> float:
    """Calculate the population standard deviation.

    Args:
        values: List of numeric values.

    Returns:
        Standard deviation, or 0.0 if empty or single value.

    """
    variance = calculate_variance(values)
    return math.sqrt(variance)


def calculate_consistency(values: list[float]) -> float:
    """Calculate consistency score from coefficient of variation.

    Measures output stability across multiple runs.
    Higher values indicate more consistent outputs.

    Formula: 1 - (std_dev / mean)

    Args:
        values: List of numeric values.

    Returns:
        Consistency score between 0.0 and 1.0.
        Returns 1.0 if mean is 0 (perfectly consistent at zero).
        Returns 0.0 if empty or single value.

    Reference:
        .claude/shared/metrics-definitions.md - Consistency metric

    """
    if len(values) < 2:
        return 0.0

    mean = calculate_mean(values)
    if mean == 0:
        # All zeros are perfectly consistent
        return 1.0

    std = calculate_std_dev(values)
    # Clamp to [0, 1] in case std > mean
    return max(0.0, min(1.0, 1.0 - (std / abs(mean))))


def calculate_all(values: list[float]) -> Statistics:
    """Calculate all statistics at once.

    Args:
        values: List of numeric values.

    Returns:
        Statistics object with all calculated values.

    """
    if not values:
        return Statistics(
            median=0.0,
            mean=0.0,
            mode=0.0,
            min=0.0,
            max=0.0,
            std_dev=0.0,
            count=0,
        )

    min_val, max_val = calculate_range(values)

    return Statistics(
        median=calculate_median(values),
        mean=calculate_mean(values),
        mode=calculate_mode(values),
        min=min_val,
        max=max_val,
        std_dev=calculate_std_dev(values),
        count=len(values),
    )
