"""Analysis pipeline for experiment results.

This module provides data loading, statistical analysis, figure generation,
and table generation for the ProjectScylla experiment results.

Python Justification: Required for scientific computing libraries (pandas,
numpy, scipy, matplotlib, altair) which have no Mojo equivalents.
"""

from scylla.analysis.dataframes import (
    build_criteria_df,
    build_judges_df,
    build_runs_df,
    build_subtests_df,
)
from scylla.analysis.loader import load_all_experiments, load_experiment

__all__ = [
    "load_all_experiments",
    "load_experiment",
    "build_runs_df",
    "build_judges_df",
    "build_criteria_df",
    "build_subtests_df",
]
