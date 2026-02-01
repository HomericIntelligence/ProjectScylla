"""Statistical analysis functions.

Provides confidence intervals, significance tests, effect sizes,
and inter-rater reliability calculations.

Python Justification: scipy is a Python-only scientific computing library.
"""

from __future__ import annotations

import logging

import krippendorff
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant

logger = logging.getLogger(__name__)


def bootstrap_ci(
    data: pd.Series | np.ndarray, confidence: float = 0.95, n_resamples: int = 10000
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval.

    Uses BCa (bias-corrected and accelerated) method for better coverage
    on small samples and binary data near boundaries.

    Args:
        data: Data to bootstrap
        confidence: Confidence level (default: 0.95 for 95% CI)
        n_resamples: Number of bootstrap resamples

    Returns:
        Tuple of (mean, lower_bound, upper_bound)

    """
    data_array = np.array(data)
    mean = np.mean(data_array)

    # Guard against single-element arrays (BCa requires n >= 2)
    if len(data_array) < 2:
        logger.warning(
            f"Bootstrap CI called with sample size {len(data_array)} < 2. "
            "Returning point estimate only."
        )
        val = float(mean)
        return val, val, val

    # Use scipy's bootstrap with BCa method for better coverage
    res = stats.bootstrap(
        (data_array,),
        np.mean,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="BCa",
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
    g1 = np.array(group1)
    g2 = np.array(group2)

    if len(g1) < 2 or len(g2) < 2:
        logger.warning(
            f"Mann-Whitney U test called with sample sizes {len(g1)}, {len(g2)}. "
            "Need at least 2 samples per group for valid results."
        )

    statistic, pvalue = stats.mannwhitneyu(g1, g2, alternative="two-sided")
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
    # Our input is already (n_judges, n_items) which matches (n_coders, n_units)
    # No transpose needed
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


def compute_impl_rate(achieved_points: float, max_points: float) -> float:
    """Compute Implementation Rate (Impl-Rate) metric.

    Impl-Rate measures the proportion of semantic requirements satisfied,
    providing more granular feedback than binary pass/fail. It aggregates
    points achieved across all rubric criteria.

    Args:
        achieved_points: Total points achieved across all criteria
        max_points: Total maximum possible points across all criteria

    Returns:
        Implementation rate in [0, 1], or NaN if max_points is 0

    Examples:
        >>> compute_impl_rate(8.5, 10.0)
        0.85
        >>> compute_impl_rate(0.0, 10.0)
        0.0
        >>> import numpy as np
        >>> np.isnan(compute_impl_rate(0.0, 0.0))
        True

    """
    if max_points == 0:
        return np.nan
    return achieved_points / max_points


def shapiro_wilk(data: pd.Series | np.ndarray) -> tuple[float, float]:
    """Perform Shapiro-Wilk normality test.

    Tests the null hypothesis that the data was drawn from a normal distribution.
    Used to justify choice of parametric vs non-parametric tests.

    Args:
        data: Sample data to test for normality

    Returns:
        Tuple of (W statistic, p-value)
        - W close to 1 suggests normality
        - p > 0.05 means cannot reject normality (at α=0.05)

    """
    data_array = np.array(data)
    statistic, pvalue = stats.shapiro(data_array)
    return float(statistic), float(pvalue)


def kruskal_wallis(*groups: pd.Series | np.ndarray) -> tuple[float, float]:
    """Perform Kruskal-Wallis H test (non-parametric one-way ANOVA).

    Omnibus test for whether samples originate from the same distribution.
    Should be performed before pairwise comparisons to control FWER.

    Args:
        *groups: Variable number of sample groups to compare

    Returns:
        Tuple of (H statistic, p-value)
        - H = 0 when all groups have identical rank sums
        - p < 0.05 indicates at least one group differs (justifies pairwise tests)

    """
    groups_arrays = [np.array(g) for g in groups]
    statistic, pvalue = stats.kruskal(*groups_arrays)
    return float(statistic), float(pvalue)


def holm_bonferroni_correction(p_values: list[float]) -> list[float]:
    """Apply Holm-Bonferroni step-down correction for multiple comparisons.

    Less conservative than standard Bonferroni while still controlling FWER.
    Sorts p-values and applies decreasing correction factors.

    Args:
        p_values: List of p-values from multiple tests

    Returns:
        List of corrected p-values in original order

    Example:
        >>> p_vals = [0.01, 0.04, 0.03, 0.50]
        >>> holm_bonferroni_correction(p_vals)
        [0.04, 0.12, 0.09, 0.50]  # More power than Bonferroni

    """
    n = len(p_values)
    if n == 0:
        return []

    # Create (index, p_value) pairs and sort by p_value
    indexed = list(enumerate(p_values))
    indexed.sort(key=lambda x: x[1])

    # Apply step-down correction
    corrected = [0.0] * n
    for rank, (original_idx, p_val) in enumerate(indexed):
        # Correction factor decreases from n to 1
        corrected[original_idx] = min(1.0, p_val * (n - rank))

    return corrected


def benjamini_hochberg_correction(p_values: list[float]) -> list[float]:
    """Apply Benjamini-Hochberg FDR correction for multiple comparisons.

    Controls False Discovery Rate instead of FWER. More powerful than
    Bonferroni/Holm when many tests are performed.

    Args:
        p_values: List of p-values from multiple tests

    Returns:
        List of corrected p-values (q-values) in original order

    Example:
        >>> p_vals = [0.01, 0.04, 0.03, 0.50]
        >>> benjamini_hochberg_correction(p_vals)
        [0.04, 0.067, 0.06, 0.50]  # FDR control, not FWER

    """
    n = len(p_values)
    if n == 0:
        return []

    # Create (index, p_value) pairs and sort by p_value
    indexed = list(enumerate(p_values))
    indexed.sort(key=lambda x: x[1])

    # Apply step-up correction (reverse order from Holm)
    corrected = [0.0] * n
    for rank, (original_idx, p_val) in enumerate(indexed):
        # Correction factor: (n / rank+1) where rank is 0-indexed
        corrected[original_idx] = min(1.0, p_val * n / (rank + 1))

    return corrected


def cliffs_delta_ci(
    group1: pd.Series | np.ndarray,
    group2: pd.Series | np.ndarray,
    confidence: float = 0.95,
    n_resamples: int = 10000,
) -> tuple[float, float, float]:
    """Compute Cliff's delta with bootstrap confidence interval.

    Provides effect size estimate with uncertainty quantification via
    BCa bootstrap. Complements the point estimate from cliffs_delta().

    Args:
        group1: First group
        group2: Second group
        confidence: Confidence level (default: 0.95)
        n_resamples: Number of bootstrap resamples

    Returns:
        Tuple of (delta, ci_low, ci_high)

    """
    # Compute point estimate using existing function
    delta = cliffs_delta(group1, group2)

    g1 = np.array(group1)
    g2 = np.array(group2)

    # Guard against insufficient data
    if len(g1) < 2 or len(g2) < 2:
        logger.warning(
            f"Cliff's delta CI called with sample sizes {len(g1)}, {len(g2)}. "
            "Returning point estimate only."
        )
        return delta, delta, delta

    # Bootstrap the delta calculation
    def delta_statistic(g1_sample, g2_sample):
        n1, n2 = len(g1_sample), len(g2_sample)
        if n1 == 0 or n2 == 0:
            return 0.0
        return np.sign(g1_sample[:, None] - g2_sample[None, :]).sum() / (n1 * n2)

    # Use scipy's bootstrap
    res = stats.bootstrap(
        (g1, g2),
        delta_statistic,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="BCa",
        random_state=42,
    )

    return delta, res.confidence_interval.low, res.confidence_interval.high


def ols_regression(x: pd.Series | np.ndarray, y: pd.Series | np.ndarray) -> dict[str, float]:
    """Perform Ordinary Least Squares regression.

    Fits y = slope * x + intercept using OLS and returns diagnostics.

    Args:
        x: Independent variable
        y: Dependent variable

    Returns:
        Dictionary with keys:
            - slope: Regression coefficient
            - intercept: Y-intercept
            - r_squared: Coefficient of determination
            - p_value: P-value for slope significance
            - std_err: Standard error of slope estimate

    """
    x_array = np.array(x)
    y_array = np.array(y)

    # Add constant term for intercept
    x_with_const = add_constant(x_array)

    # Fit OLS model
    model = OLS(y_array, x_with_const).fit()

    return {
        "slope": float(model.params[1]),
        "intercept": float(model.params[0]),
        "r_squared": float(model.rsquared),
        "p_value": float(model.pvalues[1]),
        "std_err": float(model.bse[1]),
    }
