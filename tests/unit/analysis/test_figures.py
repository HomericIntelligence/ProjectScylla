"""Unit tests for figure generation."""

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(scope="function")
def mock_save_figure():
    """Mock save_figure to avoid file I/O during tests."""
    with patch("scylla.analysis.figures.spec_builder.save_figure") as mock:
        yield mock


def test_fig01_score_variance_by_tier(sample_runs_df, mock_save_figure):
    """Test Fig 1 generates without errors."""
    from scylla.analysis.figures.variance import fig01_score_variance_by_tier

    # Should not raise
    fig01_score_variance_by_tier(sample_runs_df, Path("/tmp"), render=False)

    # Verify save_figure was called
    assert mock_save_figure.called


def test_fig04_pass_rate_by_tier(sample_runs_df, mock_save_figure):
    """Test Fig 4 generates without errors."""
    from scylla.analysis.figures.tier_performance import fig04_pass_rate_by_tier

    fig04_pass_rate_by_tier(sample_runs_df, Path("/tmp"), render=False)
    assert mock_save_figure.called


def test_fig06_cop_by_tier(sample_runs_df):
    """Test Fig 6 generates without errors."""
    from scylla.analysis.figures.cost_analysis import fig06_cop_by_tier

    with patch("scylla.analysis.figures.cost_analysis.save_figure") as mock:
        fig06_cop_by_tier(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig11_tier_uplift(sample_runs_df, mock_save_figure):
    """Test Fig 11 generates without errors."""
    from scylla.analysis.figures.model_comparison import fig11_tier_uplift

    fig11_tier_uplift(sample_runs_df, Path("/tmp"), render=False)
    assert mock_save_figure.called


def test_fig02_judge_variance(sample_judges_df, mock_save_figure):
    """Test Fig 2 generates without errors."""
    from scylla.analysis.figures.judge_analysis import fig02_judge_variance

    fig02_judge_variance(sample_judges_df, Path("/tmp"), render=False)
    assert mock_save_figure.called


def test_fig03_failure_rate_by_tier(sample_runs_df):
    """Test Fig 3 generates without errors."""
    from scylla.analysis.figures.variance import fig03_failure_rate_by_tier

    with patch("scylla.analysis.figures.variance.save_figure") as mock:
        fig03_failure_rate_by_tier(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig05_grade_heatmap(sample_runs_df):
    """Test Fig 5 generates without errors."""
    from scylla.analysis.figures.tier_performance import fig05_grade_heatmap

    with patch("scylla.analysis.figures.tier_performance.save_figure") as mock:
        fig05_grade_heatmap(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig07_token_distribution(sample_runs_df, mock_save_figure):
    """Test Fig 7 generates without errors."""
    from scylla.analysis.figures.token_analysis import fig07_token_distribution

    fig07_token_distribution(sample_runs_df, Path("/tmp"), render=False)
    assert mock_save_figure.called


def test_fig08_cost_quality_pareto(sample_runs_df):
    """Test Fig 8 generates without errors."""
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    with patch("scylla.analysis.figures.cost_analysis.save_figure") as mock:
        fig08_cost_quality_pareto(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig09_criteria_by_tier(sample_criteria_df, mock_save_figure):
    """Test Fig 9 generates without errors."""
    from scylla.analysis.figures.criteria_analysis import fig09_criteria_by_tier

    fig09_criteria_by_tier(sample_criteria_df, Path("/tmp"), render=False)
    assert mock_save_figure.called


def test_fig10_score_violin(sample_runs_df):
    """Test Fig 10 generates without errors."""
    from scylla.analysis.figures.tier_performance import fig10_score_violin

    with patch("scylla.analysis.figures.tier_performance.save_figure") as mock:
        fig10_score_violin(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig12_consistency(sample_runs_df):
    """Test Fig 12 generates without errors."""
    from scylla.analysis.figures.model_comparison import fig12_consistency

    with patch("scylla.analysis.figures.model_comparison.save_figure") as mock:
        fig12_consistency(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig13_latency(sample_runs_df):
    """Test Fig 13 generates without errors."""
    from scylla.analysis.figures.subtest_detail import fig13_latency

    with patch("scylla.analysis.figures.subtest_detail.save_figure") as mock:
        fig13_latency(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig14_judge_agreement(sample_judges_df):
    """Test Fig 14 generates without errors."""
    from scylla.analysis.figures.judge_analysis import fig14_judge_agreement

    with patch("scylla.analysis.figures.judge_analysis.save_figure") as mock:
        fig14_judge_agreement(sample_judges_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig15_subtest_heatmap(sample_runs_df):
    """Test Fig 15 generates without errors."""
    from scylla.analysis.figures.subtest_detail import fig15_subtest_heatmap

    with patch("scylla.analysis.figures.subtest_detail.save_figure") as mock:
        fig15_subtest_heatmap(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig16_success_variance_by_test(sample_runs_df):
    """Test Fig 16 generates without errors."""
    from scylla.analysis.figures.variance import fig16_success_variance_by_test

    with patch("scylla.analysis.figures.variance.save_figure") as mock:
        fig16_success_variance_by_test(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig17_judge_variance_overall(sample_judges_df):
    """Test Fig 17 generates without errors."""
    from scylla.analysis.figures.judge_analysis import fig17_judge_variance_overall

    with patch("scylla.analysis.figures.judge_analysis.save_figure") as mock:
        fig17_judge_variance_overall(sample_judges_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig18_failure_rate_by_test(sample_runs_df):
    """Test Fig 18 generates without errors."""
    from scylla.analysis.figures.variance import fig18_failure_rate_by_test

    with patch("scylla.analysis.figures.variance.save_figure") as mock:
        fig18_failure_rate_by_test(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_publication_theme():
    """Test publication theme is applied correctly."""
    from scylla.analysis.figures.spec_builder import apply_publication_theme

    # Should not raise
    apply_publication_theme()

    # Verify altair theme is registered (indirect test)
    import altair as alt

    # After applying theme, charts should use it
    # This is a basic smoke test
    assert alt.themes.active is not None


def test_model_color_scale():
    """Test model color scale helper."""
    from scylla.analysis.figures.spec_builder import model_color_scale

    # Test with sample model names
    models = ["Opus 4.5", "Sonnet 4.5", "Haiku 4.5"]
    scale = model_color_scale(models)

    # Verify it's an Altair Scale
    import altair as alt

    assert isinstance(scale, alt.Scale)

    # Verify domain and range are set
    assert scale.domain is not None
    assert scale.range is not None

    # Verify domain matches input models
    assert scale.domain == models
    assert len(scale.domain) == len(models)
    assert len(scale.range) == len(models)


def test_tier_order_constant():
    """Test TIER_ORDER constant is available."""
    from scylla.analysis.figures import TIER_ORDER

    # Should be a list of 7 tiers
    assert len(TIER_ORDER) == 7
    assert TIER_ORDER[0] == "T0"
    assert TIER_ORDER[-1] == "T6"


def test_colors_constant():
    """Test COLORS constant has required palettes."""
    from scylla.analysis.figures import COLORS

    # Verify all palettes exist
    assert "models" in COLORS
    assert "tiers" in COLORS
    assert "grades" in COLORS
    assert "judges" in COLORS
    assert "criteria" in COLORS

    # Verify models palette has required keys
    assert "Sonnet 4.5" in COLORS["models"]
    assert "Haiku 4.5" in COLORS["models"]

    # Verify tiers palette has all 7 tiers
    for tier in ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]:
        assert tier in COLORS["tiers"]


def test_fig19_effect_size_forest(sample_runs_df):
    """Test Fig 19 effect size forest plot generates without errors."""
    from scylla.analysis.figures.effect_size import fig19_effect_size_forest

    with patch("scylla.analysis.figures.effect_size.save_figure") as mock:
        fig19_effect_size_forest(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig20_metric_correlation_heatmap(sample_runs_df):
    """Test Fig 20 correlation heatmap generates without errors."""
    from scylla.analysis.figures.correlation import fig20_metric_correlation_heatmap

    with patch("scylla.analysis.figures.correlation.save_figure") as mock:
        fig20_metric_correlation_heatmap(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig21_cost_quality_regression(sample_runs_df):
    """Test Fig 21 regression plot generates without errors."""
    from scylla.analysis.figures.correlation import fig21_cost_quality_regression

    with patch("scylla.analysis.figures.correlation.save_figure") as mock:
        fig21_cost_quality_regression(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig22_cumulative_cost(sample_runs_df):
    """Test Fig 22 cumulative cost curve generates without errors."""
    from scylla.analysis.figures.cost_analysis import fig22_cumulative_cost

    with patch("scylla.analysis.figures.cost_analysis.save_figure") as mock:
        fig22_cumulative_cost(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_fig23_qq_plots(sample_runs_df):
    """Test Fig 23 Q-Q plots generate without errors."""
    from scylla.analysis.figures.diagnostics import fig23_qq_plots

    with patch("scylla.analysis.figures.diagnostics.save_figure"):
        fig23_qq_plots(sample_runs_df, Path("/tmp"), render=False)
        # Note: may not be called if insufficient data
        # Just check it doesn't crash


def test_fig24_score_histograms(sample_runs_df):
    """Test Fig 24 histograms with KDE generate without errors."""
    from scylla.analysis.figures.diagnostics import fig24_score_histograms

    with patch("scylla.analysis.figures.diagnostics.save_figure") as mock:
        fig24_score_histograms(sample_runs_df, Path("/tmp"), render=False)
        assert mock.called


def test_figure_module_structure():
    """Test that all figure modules exist."""
    figure_modules = [
        "tier_performance",
        "variance",
        "cost_analysis",
        "token_analysis",
        "model_comparison",
        "judge_analysis",
        "criteria_analysis",
        "subtest_detail",
        "effect_size",
        "correlation",
        "diagnostics",
    ]

    for module_name in figure_modules:
        module = __import__(f"scylla.analysis.figures.{module_name}", fromlist=[module_name])
        assert module is not None
