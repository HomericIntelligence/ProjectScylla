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

    Uses vectorized numpy operations for performance (~50x faster than loops).

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

    # Vectorized comparison: g1[:, None] broadcasts to (n1, n2)
    # g2[None, :] broadcasts to (n1, n2)
    # np.sign gives -1, 0, or 1 for each comparison
    delta = np.sign(g1[:, None] - g2[None, :]).sum() / (n1 * n2)
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


def bonferroni_correction(p_value: float, n_tests: int) -> float:
    """Apply Bonferroni correction for multiple comparisons.

    Adjusts p-value by multiplying by the number of independent tests.
    This controls the family-wise error rate (FWER) at the significance level.

    Args:
        p_value: Original p-value from single test
        n_tests: Number of independent hypothesis tests performed

    Returns:
        Bonferroni-corrected p-value, clamped to [0, 1]

    Example:
        >>> # 6 independent tests at α=0.05 individual level
        >>> # FWER = 1 - (1-0.05)^6 ≈ 0.26 (26% chance of Type I error)
        >>> # Bonferroni corrects to α_adj = 0.05/6 ≈ 0.0083
        >>> bonferroni_correction(0.04, 6)  # Original p=0.04 < 0.05
        0.24  # Adjusted p=0.24 > 0.05, not significant after correction

    """
    return min(1.0, p_value * n_tests)


def compute_consistency(mean: float, std: float) -> float:
    """Compute consistency metric: 1 - coefficient of variation.

    Consistency measures how stable scores are relative to their mean.
    Higher values indicate more consistent (less variable) performance.

    Args:
        mean: Mean of the data
        std: Standard deviation of the data

    Returns:
        Consistency value in [0, 1], where 1 = perfect consistency

    """
    if mean == 0:
        return 0.0
    consistency = 1 - (std / mean)
    return max(0.0, min(1.0, consistency))  # Clamp to [0, 1]


def compute_cop(mean_cost: float, pass_rate: float) -> float:
    """Compute Cost-of-Pass (CoP) metric.

    CoP represents the expected cost to achieve one successful outcome.
    Lower values indicate better cost efficiency.

    Args:
        mean_cost: Mean cost per attempt (USD)
        pass_rate: Success rate in [0, 1]

    Returns:
        CoP in USD, or inf if pass_rate is 0

    """
    if pass_rate == 0:
        return float("inf")
    return mean_cost / pass_rate
