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

    scale = model_color_scale()

    # Verify it's an Altair Scale
    import altair as alt

    assert isinstance(scale, alt.Scale)

    # Verify domain and range are set
    assert scale.domain is not None
    assert scale.range is not None


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
    ]

    for module_name in figure_modules:
        module = __import__(f"scylla.analysis.figures.{module_name}", fromlist=[module_name])
        assert module is not None
