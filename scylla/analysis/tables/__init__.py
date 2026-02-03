"""Statistical table generation.

This package provides table generation functions for research papers,
organized by table purpose:

- summary: Summary statistics tables (Table 1, 5)
- comparison: Statistical comparison tables (Table 2, 2b, 4, 6)
- detail: Detailed and appendix tables (Table 3, 7-11)

Python Justification: Uses pandas for table formatting and data manipulation.
"""

from __future__ import annotations

# Import all table functions from submodules
from scylla.analysis.tables.comparison import (
    table02_tier_comparison,
    table02b_impl_rate_comparison,
    table04_criteria_performance,
    table06_model_comparison,
)
from scylla.analysis.tables.detail import (
    table03_judge_agreement,
    table07_subtest_detail,
    table08_summary_statistics,
    table09_experiment_config,
    table10_normality_tests,
)
from scylla.analysis.tables.summary import (
    table01_tier_summary,
    table05_cost_analysis,
)

# Export all table functions
__all__ = [
    # Summary tables
    "table01_tier_summary",
    "table05_cost_analysis",
    # Comparison tables
    "table02_tier_comparison",
    "table02b_impl_rate_comparison",
    "table04_criteria_performance",
    "table06_model_comparison",
    # Detail tables
    "table03_judge_agreement",
    "table07_subtest_detail",
    "table08_summary_statistics",
    "table09_experiment_config",
    "table10_normality_tests",
]
