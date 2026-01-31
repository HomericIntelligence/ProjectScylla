"""Unit tests for table generation.

Note: These are basic smoke tests to ensure tables can be generated.
Full validation of table content is deferred to integration tests.
"""

import pytest


@pytest.mark.skipif(True, reason="Requires full DataFrame with judge data")
def test_table01_tier_summary_format(sample_runs_df):
    """Test Table 1 returns valid dual-format output."""
    from scylla.analysis.tables import table01_tier_summary

    markdown, latex = table01_tier_summary(sample_runs_df)

    # Verify both formats are non-empty strings
    assert isinstance(markdown, str)
    assert isinstance(latex, str)
    assert len(markdown) > 0
    assert len(latex) > 0


def test_tables_module_imports():
    """Test that tables module can be imported."""
    import scylla.analysis.tables

    assert scylla.analysis.tables is not None


def test_table_function_signatures():
    """Test that all table functions exist with expected signature."""
    import inspect

    from scylla.analysis import tables

    # List of expected table functions
    table_functions = [
        "table01_tier_summary",
        "table02_tier_comparison",
        "table03_judge_agreement",
        "table04_criteria_performance",
        "table05_cost_analysis",
        "table06_model_comparison",
        "table07_subtest_detail",
    ]

    for func_name in table_functions:
        assert hasattr(tables, func_name), f"Missing function: {func_name}"
        func = getattr(tables, func_name)
        sig = inspect.signature(func)
        # Should return tuple[str, str] for (markdown, latex)
        # Check if annotation is the string "tuple[str, str]" or the actual type
        ann = sig.return_annotation
        is_valid = (
            ann == inspect._empty
            or ann == tuple[str, str]
            or (isinstance(ann, str) and ann == "tuple[str, str]")
        )
        assert is_valid, f"Invalid return annotation for {func_name}: {ann}"
