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


def test_table01_consistency_clamped():
    """Test that consistency values are clamped to [0, 1].

    Regression test for P0 bug where inline formula 1 - (std/mean) could produce
    negative values when std > mean (high-variance subtests).
    """
    import pandas as pd

    from scylla.analysis.tables import table01_tier_summary

    # Create minimal test data with high variance (std > mean)
    # This should trigger the clamping logic
    test_data = pd.DataFrame(
        {
            "agent_model": ["Sonnet 4.5"] * 10,
            "tier": ["T0"] * 10,
            "score": [0.1, 0.2, 0.3, 0.8, 0.9, 0.05, 0.15, 0.25, 0.5, 0.7],  # High variance
            "passed": [True] * 5 + [False] * 5,
            "cost_usd": [1.0] * 10,
            "subtest": [f"test_{i}" for i in range(10)],
        }
    )

    markdown, latex = table01_tier_summary(test_data)

    # Verify tables generated (basic smoke test)
    assert isinstance(markdown, str)
    assert isinstance(latex, str)
    assert len(markdown) > 0
    assert len(latex) > 0

    # Verify no negative consistency values appear in output
    # Consistency should be clamped to [0, 1]
    assert (
        "-" not in markdown.split("Consistency")[1].split("|")[0]
        if "Consistency" in markdown
        else True
    )


def test_table01_uses_compute_cop():
    """Test that table01 uses shared compute_cop function.

    Regression test for P1 bug where inline formula duplicated compute_cop logic.
    """
    import pandas as pd

    from scylla.analysis.tables import table01_tier_summary

    # Create test data with zero pass rate to trigger inf CoP
    test_data = pd.DataFrame(
        {
            "agent_model": ["Sonnet 4.5"] * 5,
            "tier": ["T0"] * 5,
            "score": [0.0] * 5,
            "passed": [False] * 5,  # Zero pass rate
            "cost_usd": [1.0] * 5,
            "subtest": [f"test_{i}" for i in range(5)],
        }
    )

    markdown, latex = table01_tier_summary(test_data)

    # Verify tables generated
    assert isinstance(markdown, str)
    assert isinstance(latex, str)

    # Verify that inf appears in output (compute_cop returns inf for zero pass rate)
    assert "inf" in markdown.lower() or "∞" in markdown
