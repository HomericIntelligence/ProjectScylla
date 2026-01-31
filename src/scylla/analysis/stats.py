"""Statistical analysis functions.

Provides confidence intervals, significance tests, effect sizes,
and inter-rater reliability calculations.

Python Justification: scipy is a Python-only scientific computing library.
"""

from __future__ import annotations

import krippendorff
import numpy as np
import pandas as pd
from scipy import stats


def bootstrap_ci(
    data: pd.Series | np.ndarray, confidence: float = 0.95, n_resamples: int = 10000
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval.

    Args:
        data: Data to bootstrap
        confidence: Confidence level (default: 0.95 for 95% CI)
        n_resamples: Number of bootstrap resamples

    Returns:
        Tuple of (mean, lower_bound, upper_bound)

    """
    data_array = np.array(data)
    mean = np.mean(data_array)

    # Use scipy's bootstrap for percentile CI
    res = stats.bootstrap(
        (data_array,),
        np.mean,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="percentile",
        random_state=42,
    )

    return mean, res.confidence_interval.low, res.confidence_interval.high


def mann_whitney_u(
    group1: pd.Series | np.ndarray, group2: pd.Series | np.ndarray
) -> tuple[float, float]:
    """Perform Mann-Whitney U test (non-parametric).

    Args:
        group1: First group
        group2: Second group

    Returns:
        Tuple of (U statistic, p-value)

    """
    statistic, pvalue = stats.mannwhitneyu(group1, group2, alternative="two-sided")
    return float(statistic), float(pvalue)


def cliffs_delta(group1: pd.Series | np.ndarray, group2: pd.Series | np.ndarray) -> float:
    """Compute Cliff's delta effect size (non-parametric).

    Interpretation:
        |δ| < 0.147: negligible
        |δ| < 0.33: small
        |δ| < 0.474: medium
        |δ| >= 0.474: large

    Args:
        group1: First group
        group2: Second group

    Returns:
        Cliff's delta in range [-1, 1]

    """
    g1 = np.array(group1)
    g2 = np.array(group2)

    n1, n2 = len(g1), len(g2)
    if n1 == 0 or n2 == 0:
        return 0.0

    # Count dominance relationships
    dominance = 0
    for x in g1:
        for y in g2:
            if x > y:
                dominance += 1
            elif x < y:
                dominance -= 1

    delta = dominance / (n1 * n2)
    return float(delta)


def spearman_correlation(
    x: pd.Series | np.ndarray, y: pd.Series | np.ndarray
) -> tuple[float, float]:
    """Compute Spearman rank correlation.

    Args:
        x: First variable
        y: Second variable

    Returns:
        Tuple of (correlation, p-value)

    """
    corr, pvalue = stats.spearmanr(x, y)
    return float(corr), float(pvalue)


def pearson_correlation(
    x: pd.Series | np.ndarray, y: pd.Series | np.ndarray
) -> tuple[float, float]:
    """Compute Pearson correlation.

    Args:
        x: First variable
        y: Second variable

    Returns:
        Tuple of (correlation, p-value)

    """
    corr, pvalue = stats.pearsonr(x, y)
    return float(corr), float(pvalue)


def krippendorff_alpha(ratings: np.ndarray, level: str = "ordinal") -> float:
    """Compute Krippendorff's alpha for inter-rater reliability.

    Wrapper around the krippendorff package for correct implementation.

    Args:
        ratings: 2D array of shape (n_judges, n_items)
        level: Measurement level ("nominal", "ordinal", "interval", "ratio")

    Returns:
        Krippendorff's alpha in range [-1, 1]

    """
    # Convert to numpy array
    ratings = np.array(ratings)

    # The krippendorff package expects (n_units, n_coders) format
    # Our input is (n_judges, n_items), so we need to transpose
    reliability_data = ratings

    # Call the krippendorff package
    return float(krippendorff.alpha(reliability_data=reliability_data, level_of_measurement=level))
