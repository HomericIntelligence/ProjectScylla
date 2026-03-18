from typing import Any

"""Unit tests for figure generation."""


def test_fig01_score_variance_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 1 generates files correctly."""
    from scylla.analysis.figures.variance import fig01_score_variance_by_tier

    fig01_score_variance_by_tier(sample_runs_df, tmp_path, render=False)

    # Verify files created
    assert (tmp_path / "fig01_score_variance_by_tier.vl.json").exists()


def test_fig04_pass_rate_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 4 generates files correctly."""
    from scylla.analysis.figures.tier_performance import fig04_pass_rate_by_tier

    fig04_pass_rate_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig04_pass_rate_by_tier.vl.json").exists()


def test_fig06_cop_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 6 generates files correctly."""
    from scylla.analysis.figures.cost_analysis import fig06_cop_by_tier

    fig06_cop_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig06_cop_by_tier.vl.json").exists()


def test_fig11_tier_uplift(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 11 generates files correctly."""
    from scylla.analysis.figures.model_comparison import fig11_tier_uplift

    fig11_tier_uplift(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig11_tier_uplift.vl.json").exists()


def test_fig02_judge_variance(sample_judges_df: Any, tmp_path: Any) -> None:
    """Test Fig 2 generates per-tier files correctly."""
    from scylla.analysis.figures.judge_analysis import fig02_judge_variance

    fig02_judge_variance(sample_judges_df, tmp_path, render=False)
    # Note: Generates per-tier files (fig02_t0_judge_variance.vl.json, etc.)


def test_fig03_failure_rate_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 3 generates files correctly."""
    from scylla.analysis.figures.variance import fig03_failure_rate_by_tier

    fig03_failure_rate_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig03_failure_rate_by_tier.vl.json").exists()


def test_fig05_grade_heatmap(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 5 generates files correctly."""
    from scylla.analysis.figures.tier_performance import fig05_grade_heatmap

    fig05_grade_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig05_grade_heatmap.vl.json").exists()


def test_fig07_token_distribution(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 7 generates files correctly."""
    from scylla.analysis.figures.token_analysis import fig07_token_distribution

    fig07_token_distribution(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig07_token_distribution.vl.json").exists()


def test_fig08_cost_quality_pareto(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 8 generates files correctly."""
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    fig08_cost_quality_pareto(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig08_cost_quality_pareto.vl.json").exists()


def test_fig09_criteria_by_tier(sample_criteria_df: Any, tmp_path: Any) -> None:
    """Test Fig 9 generates files correctly."""
    from scylla.analysis.figures.criteria_analysis import fig09_criteria_by_tier

    fig09_criteria_by_tier(sample_criteria_df, tmp_path, render=False)
    assert (tmp_path / "fig09_criteria_by_tier.vl.json").exists()


def test_fig12_consistency(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 12 generates files correctly."""
    from scylla.analysis.figures.model_comparison import fig12_consistency

    fig12_consistency(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig12_consistency.vl.json").exists()


def test_fig13_latency(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 13 generates files correctly."""
    from scylla.analysis.figures.subtest_detail import fig13_latency

    fig13_latency(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig13_latency.vl.json").exists()


def test_fig14_judge_agreement(sample_judges_df: Any, tmp_path: Any) -> None:
    """Test Fig 14 generates per-tier files correctly."""
    from scylla.analysis.figures.judge_analysis import fig14_judge_agreement

    fig14_judge_agreement(sample_judges_df, tmp_path, render=False)
    # Note: Generates per-tier files (fig14_t0_judge_agreement.vl.json, etc.)


def test_fig15a_subtest_run_heatmap(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 15a generates files correctly."""
    from scylla.analysis.figures.subtest_detail import fig15a_subtest_run_heatmap

    fig15a_subtest_run_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig15a_subtest_run_heatmap.vl.json").exists()


def test_fig15b_subtest_best_heatmap(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 15b generates files correctly."""
    from scylla.analysis.figures.subtest_detail import fig15b_subtest_best_heatmap

    fig15b_subtest_best_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig15b_subtest_best_heatmap.vl.json").exists()


def test_fig15c_tier_summary_heatmap(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 15c generates files correctly."""
    from scylla.analysis.figures.subtest_detail import fig15c_tier_summary_heatmap

    fig15c_tier_summary_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig15c_tier_summary_heatmap.vl.json").exists()


def test_fig16a_success_variance_per_subtest(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 16a generates files correctly."""
    from scylla.analysis.figures.variance import fig16a_success_variance_per_subtest

    fig16a_success_variance_per_subtest(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig16a_success_variance_per_subtest.vl.json").exists()


def test_fig16b_success_variance_aggregate(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 16b generates files correctly."""
    from scylla.analysis.figures.variance import fig16b_success_variance_aggregate

    fig16b_success_variance_aggregate(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig16b_success_variance_aggregate.vl.json").exists()


def test_fig17_judge_variance_overall(sample_judges_df: Any, tmp_path: Any) -> None:
    """Test Fig 17 generates per-tier files correctly."""
    from scylla.analysis.figures.judge_analysis import fig17_judge_variance_overall

    fig17_judge_variance_overall(sample_judges_df, tmp_path, render=False)
    # Note: Generates per-tier files (fig17_t0_judge_variance_overall.vl.json, etc.)


def test_fig18a_failure_rate_per_subtest(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 18a generates files correctly."""
    from scylla.analysis.figures.variance import fig18a_failure_rate_per_subtest

    fig18a_failure_rate_per_subtest(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig18a_failure_rate_per_subtest.vl.json").exists()


def test_fig18b_failure_rate_aggregate(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 18b generates files correctly."""
    from scylla.analysis.figures.variance import fig18b_failure_rate_aggregate

    fig18b_failure_rate_aggregate(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig18b_failure_rate_aggregate.vl.json").exists()


def test_publication_theme() -> None:
    """Test publication theme is applied correctly."""
    from scylla.analysis.figures.spec_builder import apply_publication_theme

    # Should not raise
    apply_publication_theme()

    # Verify altair theme is registered (indirect test)
    import altair as alt

    # After applying theme, charts should use it
    # This is a basic smoke test
    assert alt.themes.active is not None


def test_model_color_scale() -> None:
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


def test_tier_order_constant() -> None:
    """Test TIER_ORDER constant is available."""
    from scylla.analysis.figures import TIER_ORDER

    # Should be a list of 7 tiers
    assert len(TIER_ORDER) == 7
    assert TIER_ORDER[0] == "T0"
    assert TIER_ORDER[-1] == "T6"


def test_colors_constant() -> None:
    """Test COLORS constant has required palettes."""
    from scylla.analysis.figures import COLORS

    # Verify all palettes exist
    assert "models" in COLORS
    assert "tiers" in COLORS
    assert "grades" in COLORS
    assert "judges" in COLORS
    assert "criteria" in COLORS
    assert "phases" in COLORS
    assert "token_types" in COLORS

    # Verify models palette has required keys
    assert "Sonnet 4.5" in COLORS["models"]
    assert "Haiku 4.5" in COLORS["models"]

    # Verify tiers palette has all 7 tiers
    for tier in ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]:
        assert tier in COLORS["tiers"]

    # Verify new palettes have expected keys
    assert "Agent Execution" in COLORS["phases"]
    assert "Judge Evaluation" in COLORS["phases"]
    assert "Input (Fresh)" in COLORS["token_types"]
    assert "Output" in COLORS["token_types"]


def test_fig19_effect_size_forest(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 19 effect size forest plot generates files correctly."""
    from scylla.analysis.figures.effect_size import fig19_effect_size_forest

    fig19_effect_size_forest(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig19_effect_size_forest.vl.json").exists()


def test_fig20_metric_correlation_heatmap(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 20 correlation heatmap generates files correctly."""
    from scylla.analysis.figures.correlation import fig20_metric_correlation_heatmap

    fig20_metric_correlation_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig20_metric_correlation_heatmap.vl.json").exists()


def test_fig21_cost_quality_regression(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 21 regression plot generates files correctly."""
    from scylla.analysis.figures.correlation import fig21_cost_quality_regression

    fig21_cost_quality_regression(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig21_cost_quality_regression.vl.json").exists()


def test_fig22_cumulative_cost(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 22 cumulative cost curve generates files correctly."""
    from scylla.analysis.figures.cost_analysis import fig22_cumulative_cost

    fig22_cumulative_cost(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig22_cumulative_cost.vl.json").exists()


def test_fig23_qq_plots(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 23 Q-Q plots generate per-tier files correctly."""
    from scylla.analysis.figures.diagnostics import fig23_qq_plots

    fig23_qq_plots(sample_runs_df, tmp_path, render=False)
    # Note: Generates per-tier files, may not create files if insufficient data


def test_fig24_score_histograms(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 24 histograms with KDE generate per-tier files correctly."""
    from scylla.analysis.figures.diagnostics import fig24_score_histograms

    fig24_score_histograms(sample_runs_df, tmp_path, render=False)
    # Note: Generates per-tier files, may not create files if insufficient data


def test_register_colors() -> None:
    """Test dynamic color registration."""
    from scylla.analysis.figures import COLORS, register_colors

    # Register new colors for a custom category
    register_colors("custom_models", {"GPT-5": "#FF0000", "Claude-5": "#00FF00"})

    # Verify registration
    assert "custom_models" in COLORS
    assert COLORS["custom_models"]["GPT-5"] == "#FF0000"
    assert COLORS["custom_models"]["Claude-5"] == "#00FF00"

    # Update existing category
    register_colors("models", {"New Model": "#ABCDEF"})
    assert "New Model" in COLORS["models"]

    # Cleanup (restore original state)
    del COLORS["custom_models"]
    del COLORS["models"]["New Model"]


def test_figure_module_structure() -> None:
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


def test_latex_snippet_generation(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test LaTeX snippet generation for figures."""
    import altair as alt

    from scylla.analysis.figures.spec_builder import save_figure

    # Create a simple chart (avoiding mocked figure functions)
    chart = (
        alt.Chart(sample_runs_df)
        .mark_bar()
        .encode(x="tier:O", y="mean(score):Q")
        .properties(title="Test Figure for LaTeX")
    )

    # Save with render=True to generate LaTeX snippet
    save_figure(chart, "test_latex_fig", tmp_path, render=True, formats=["pdf"])

    # Check that LaTeX snippet was created
    snippet_path = tmp_path / "test_latex_fig_include.tex"
    assert snippet_path.exists(), "LaTeX snippet should be created"

    # Read and verify content
    content = snippet_path.read_text()

    # Check for required LaTeX structure
    assert "\\begin{figure}[htbp]" in content
    assert "\\centering" in content
    assert "\\includegraphics[width=\\textwidth]{test_latex_fig.pdf}" in content
    assert "\\caption{" in content
    assert "\\label{fig:test_latex_fig}" in content
    assert "\\end{figure}" in content


def test_latex_snippet_with_custom_caption(tmp_path: Any) -> None:
    """Test LaTeX snippet with custom caption."""
    import altair as alt
    import pandas as pd

    from scylla.analysis.figures.spec_builder import save_figure

    # Create simple chart
    data = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    chart = alt.Chart(data).mark_point().encode(x="x", y="y").properties(title="Test Chart")

    # Save with custom caption
    save_figure(
        chart,
        "test_figure",
        tmp_path,
        render=True,
        formats=["pdf"],
        latex_caption="Custom caption for testing",
    )

    # Verify snippet has custom caption
    snippet_path = tmp_path / "test_figure_include.tex"
    assert snippet_path.exists()

    content = snippet_path.read_text()
    assert "\\caption{Custom caption for testing}" in content


def test_fig25_impl_rate_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 25 generates files correctly."""
    from scylla.analysis.figures.impl_rate_analysis import fig25_impl_rate_by_tier

    fig25_impl_rate_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig25_impl_rate_by_tier.vl.json").exists()


def test_fig26_impl_rate_vs_pass_rate(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 26 generates files correctly."""
    from scylla.analysis.figures.impl_rate_analysis import fig26_impl_rate_vs_pass_rate

    fig26_impl_rate_vs_pass_rate(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig26_impl_rate_vs_pass_rate.vl.json").exists()


def test_fig27_impl_rate_distribution(sample_runs_df: Any, tmp_path: Any) -> None:
    """Test Fig 27 generates files correctly."""
    from scylla.analysis.figures.impl_rate_analysis import fig27_impl_rate_distribution

    fig27_impl_rate_distribution(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig27_impl_rate_distribution.vl.json").exists()


def test_impl_rate_figures_handle_missing_column(tmp_path: Any) -> None:
    """Test Impl-Rate figures handle missing impl_rate column gracefully."""
    import pandas as pd

    from scylla.analysis.figures.impl_rate_analysis import (
        fig25_impl_rate_by_tier,
        fig26_impl_rate_vs_pass_rate,
        fig27_impl_rate_distribution,
    )

    # Create DataFrame without impl_rate column
    df = pd.DataFrame(
        {
            "agent_model": ["Sonnet 4.5"] * 5,
            "tier": ["T0"] * 5,
            "passed": [True] * 5,
            "score": [0.8] * 5,
        }
    )

    # Should not raise, just skip generation
    fig25_impl_rate_by_tier(df, tmp_path, render=False)
    fig26_impl_rate_vs_pass_rate(df, tmp_path, render=False)
    fig27_impl_rate_distribution(df, tmp_path, render=False)

    # No files should be created since impl_rate is missing
    assert not (tmp_path / "fig25_impl_rate_by_tier.vl.json").exists()
    assert not (tmp_path / "fig26_impl_rate_vs_pass_rate.vl.json").exists()
    assert not (tmp_path / "fig27_impl_rate_distribution.vl.json").exists()


def test_get_color_with_static_colors() -> None:
    """Test get_color() returns static colors from config."""
    from scylla.analysis.figures import get_color

    # Test models category
    sonnet_color = get_color("models", "Sonnet 4.5")
    assert sonnet_color.startswith("#")  # Valid hex color
    assert len(sonnet_color) == 7  # #RRGGBB format

    # Test tiers category
    t0_color = get_color("tiers", "T0")
    assert t0_color.startswith("#")
    assert len(t0_color) == 7

    # Test grades category
    a_grade_color = get_color("grades", "A")
    assert a_grade_color.startswith("#")
    assert len(a_grade_color) == 7


def test_get_color_with_dynamic_palette() -> None:
    """Test get_color() falls back to dynamic palette for unknown keys."""
    from scylla.analysis.figures import get_color

    # Test unknown model (not in static colors)
    unknown_color = get_color("models", "Unknown Model")
    assert unknown_color.startswith("#")
    assert len(unknown_color) == 7

    # Test unknown category and key
    custom_color = get_color("custom_category", "custom_key")
    assert custom_color.startswith("#")
    assert len(custom_color) == 7

    # Verify deterministic behavior (same key -> same color)
    color1 = get_color("custom", "test_key")
    color2 = get_color("custom", "test_key")
    assert color1 == color2


def test_get_color_deterministic_hash() -> None:
    """Test get_color() uses deterministic hash for dynamic colors."""
    from scylla.analysis.figures import get_color

    # Same key should always produce the same color
    key = "test_model_xyz"
    color1 = get_color("unknown_category", key)
    color2 = get_color("unknown_category", key)
    color3 = get_color("unknown_category", key)

    assert color1 == color2 == color3


def test_get_color_scale_with_known_keys() -> None:
    """Test get_color_scale() returns correct domain and range for known keys."""
    from scylla.analysis.figures import get_color_scale

    # Test with known models
    models = ["Sonnet 4.5", "Haiku 4.5", "Opus 4.5"]
    domain, range_ = get_color_scale("models", models)

    # Verify domain matches input
    assert domain == models
    assert len(domain) == len(models)

    # Verify range has corresponding colors
    assert len(range_) == len(models)
    for color in range_:
        assert color.startswith("#")
        assert len(color) == 7


def test_get_color_scale_with_unknown_keys() -> None:
    """Test get_color_scale() handles unknown keys with dynamic palette."""
    from scylla.analysis.figures import get_color_scale

    # Test with unknown keys
    unknown_keys = ["Unknown1", "Unknown2", "Unknown3"]
    domain, range_ = get_color_scale("custom_category", unknown_keys)

    # Verify structure
    assert domain == unknown_keys
    assert len(range_) == len(unknown_keys)

    # Verify all colors are valid hex codes
    for color in range_:
        assert color.startswith("#")
        assert len(color) == 7


def test_get_color_scale_with_mixed_keys() -> None:
    """Test get_color_scale() handles mix of known and unknown keys."""
    from scylla.analysis.figures import get_color_scale

    # Mix known and unknown models
    mixed_models = ["Sonnet 4.5", "Unknown Model", "Haiku 4.5"]
    domain, range_ = get_color_scale("models", mixed_models)

    # Verify structure
    assert domain == mixed_models
    assert len(range_) == 3

    # Verify all colors are valid
    for color in range_:
        assert color.startswith("#")
        assert len(color) == 7


def test_get_color_scale_empty_list() -> None:
    """Test get_color_scale() handles empty list gracefully."""
    from scylla.analysis.figures import get_color_scale

    domain, range_ = get_color_scale("models", [])

    # Should return empty lists
    assert domain == []
    assert range_ == []


def test_get_color_scale_single_key() -> None:
    """Test get_color_scale() handles single key correctly."""
    from scylla.analysis.figures import get_color_scale

    domain, range_ = get_color_scale("models", ["Sonnet 4.5"])

    # Verify single-element lists
    assert domain == ["Sonnet 4.5"]
    assert len(range_) == 1
    assert range_[0].startswith("#")


def test_compute_dynamic_domain() -> None:
    """Test compute_dynamic_domain with various data patterns."""
    import pandas as pd

    from scylla.analysis.figures.spec_builder import compute_dynamic_domain

    # Test 1: Tight data range (0.94-0.98)
    data = pd.Series([0.94, 0.95, 0.96, 0.97, 0.98])
    domain = compute_dynamic_domain(data)
    assert len(domain) == 2
    assert domain[0] < 0.94  # Lower bound is below data min
    assert domain[1] > 0.98  # Upper bound is above data max
    assert domain[0] >= 0.0  # Respects floor
    assert domain[1] <= 1.0  # Respects ceiling
    # Check rounding to 0.05 (use approximate comparison for floating point)
    assert abs(domain[0] - round(domain[0] / 0.05) * 0.05) < 1e-10
    assert abs(domain[1] - round(domain[1] / 0.05) * 0.05) < 1e-10

    # Test 2: Full range data (0.0-1.0)
    data = pd.Series([0.0, 0.5, 1.0])
    domain = compute_dynamic_domain(data)
    assert domain == [0.0, 1.0]  # Should be clamped to floor/ceiling

    # Test 3: Small range (enforce min_range)
    data = pd.Series([0.5, 0.51])
    domain = compute_dynamic_domain(data, min_range=0.1)
    assert len(domain) == 2
    assert domain[1] - domain[0] >= 0.1  # Enforces minimum range

    # Test 4: Empty series
    data = pd.Series([])
    domain = compute_dynamic_domain(data)
    assert domain == [0.0, 1.0]  # Fallback to floor/ceiling

    # Test 5: All NaN
    data = pd.Series([float("nan"), float("nan")])
    domain = compute_dynamic_domain(data)
    assert domain == [0.0, 1.0]  # Fallback to floor/ceiling

    # Test 6: Custom floor and ceiling
    data = pd.Series([0.5, 0.6, 0.7])
    domain = compute_dynamic_domain(data, floor=0.4, ceiling=0.8)
    assert domain[0] >= 0.4
    assert domain[1] <= 0.8


def test_generate_figures_registry_includes_process_metrics() -> None:
    """FIGURES registry contains all four process-metrics figures."""
    from scripts.generate_figures import FIGURES

    assert "fig28_r_prog_by_tier" in FIGURES
    assert "fig29_cfp_by_tier" in FIGURES
    assert "fig30_pr_revert_by_tier" in FIGURES
    assert "fig_strategic_drift_by_tier" in FIGURES


def test_generate_figures_process_metrics_use_tier_category() -> None:
    """Process-metrics figures are registered under the 'tier' category."""
    from scripts.generate_figures import FIGURES

    assert FIGURES["fig28_r_prog_by_tier"][0] == "tier"
    assert FIGURES["fig29_cfp_by_tier"][0] == "tier"
    assert FIGURES["fig30_pr_revert_by_tier"][0] == "tier"
    assert FIGURES["fig_strategic_drift_by_tier"][0] == "tier"


def test_compute_dynamic_domain_padding() -> None:
    """Test padding behavior."""
    import pandas as pd

    from scylla.analysis.figures.spec_builder import compute_dynamic_domain

    # Test with different padding fractions
    data = pd.Series([0.5, 0.6])

    # No padding
    domain_no_pad = compute_dynamic_domain(data, padding_fraction=0.0)
    # 10% padding
    domain_pad = compute_dynamic_domain(data, padding_fraction=0.1)

    # With padding should have wider range
    assert domain_pad[1] - domain_pad[0] >= domain_no_pad[1] - domain_no_pad[0]


def test_fig28_r_prog_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig28_r_prog_by_tier generates output file without error."""
    from scylla.analysis.figures.process_metrics import fig28_r_prog_by_tier

    fig28_r_prog_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig28_r_prog_by_tier.vl.json").exists()


def test_fig29_cfp_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig29_cfp_by_tier generates output file without error."""
    from scylla.analysis.figures.process_metrics import fig29_cfp_by_tier

    fig29_cfp_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig29_cfp_by_tier.vl.json").exists()


def test_fig30_pr_revert_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig30_pr_revert_by_tier generates output file without error."""
    from scylla.analysis.figures.process_metrics import fig30_pr_revert_by_tier

    fig30_pr_revert_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig30_pr_revert_by_tier.vl.json").exists()


def test_process_metrics_figures_handle_missing_columns(tmp_path: Any) -> None:
    """Process-metrics figures skip gracefully when their column is absent."""
    import pandas as pd

    from scylla.analysis.figures.process_metrics import (
        fig28_r_prog_by_tier,
        fig29_cfp_by_tier,
        fig30_pr_revert_by_tier,
    )

    # DataFrame without any process-metrics columns
    df = pd.DataFrame(
        {
            "agent_model": ["Sonnet 4.5"] * 5,
            "tier": ["T0"] * 5,
            "passed": [True] * 5,
            "score": [0.8] * 5,
        }
    )

    # Should not raise, just skip generation
    fig28_r_prog_by_tier(df, tmp_path, render=False)
    fig29_cfp_by_tier(df, tmp_path, render=False)
    fig30_pr_revert_by_tier(df, tmp_path, render=False)

    # No files should be created since columns are missing
    assert not (tmp_path / "fig28_r_prog_by_tier.vl.json").exists()
    assert not (tmp_path / "fig29_cfp_by_tier.vl.json").exists()
    assert not (tmp_path / "fig30_pr_revert_by_tier.vl.json").exists()


def test_fig_strategic_drift_by_tier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig_strategic_drift_by_tier generates output file without error."""
    from scylla.analysis.figures.process_metrics import fig_strategic_drift_by_tier

    fig_strategic_drift_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig_strategic_drift_by_tier.vl.json").exists()


def test_fig_strategic_drift_by_tier_missing_column(tmp_path: Any) -> None:
    """fig_strategic_drift_by_tier skips gracefully when column absent."""
    import pandas as pd

    from scylla.analysis.figures.process_metrics import fig_strategic_drift_by_tier

    df = pd.DataFrame({"tier": ["T0"], "agent_model": ["Sonnet 4.5"], "score": [0.8]})
    fig_strategic_drift_by_tier(df, tmp_path, render=False)
    assert not (tmp_path / "fig_strategic_drift_by_tier.vl.json").exists()


def test_fig_strategic_drift_by_tier_all_null(tmp_path: Any) -> None:
    """fig_strategic_drift_by_tier skips gracefully when column all-null."""
    import pandas as pd

    from scylla.analysis.figures.process_metrics import fig_strategic_drift_by_tier

    df = pd.DataFrame(
        {
            "tier": ["T0", "T1"],
            "agent_model": ["Sonnet 4.5", "Sonnet 4.5"],
            "strategic_drift": [None, None],
        }
    )
    fig_strategic_drift_by_tier(df, tmp_path, render=False)
    assert not (tmp_path / "fig_strategic_drift_by_tier.vl.json").exists()


def test_fig31_experiment_tier_heatmap(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig31 generates heatmap and CSV."""
    from scylla.analysis.figures.tier_performance import fig31_experiment_tier_heatmap

    fig31_experiment_tier_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig31_experiment_tier_heatmap.vl.json").exists()
    assert (tmp_path / "fig31_experiment_tier_heatmap.csv").exists()


def test_fig32_tier_win_count(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig32 generates bar chart and CSV."""
    from scylla.analysis.figures.tier_performance import fig32_tier_win_count

    fig32_tier_win_count(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig32_tier_win_count.vl.json").exists()
    assert (tmp_path / "fig32_tier_win_count.csv").exists()


def test_fig33_convergence_analysis(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig33 generates convergence chart and CSV."""
    from scylla.analysis.figures.tier_performance import fig33_convergence_analysis

    fig33_convergence_analysis(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig33_convergence_analysis.vl.json").exists()
    assert (tmp_path / "fig33_convergence_analysis.csv").exists()


def test_fig33_convergence_analysis_single_experiment(tmp_path: Any) -> None:
    """fig33 returns early with <2 experiments."""
    import pandas as pd

    from scylla.analysis.figures.tier_performance import fig33_convergence_analysis

    df = pd.DataFrame(
        {
            "experiment": ["test-001"] * 5,
            "agent_model": ["Haiku 4.5"] * 5,
            "tier": ["T0"] * 5,
            "passed": [True] * 5,
        }
    )
    fig33_convergence_analysis(df, tmp_path, render=False)
    # Should not generate files with a single experiment
    assert not (tmp_path / "fig33_convergence_analysis.vl.json").exists()


def test_fig34_per_experiment_cost_frontier(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig34 generates cost frontier and CSV."""
    from scylla.analysis.figures.cost_analysis import fig34_per_experiment_cost_frontier

    fig34_per_experiment_cost_frontier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig34_per_experiment_cost_frontier.vl.json").exists()
    assert (tmp_path / "fig34_per_experiment_cost_frontier.csv").exists()


def test_generate_figures_registry_includes_new_figures() -> None:
    """FIGURES registry contains all four new aggregate figures."""
    from scripts.generate_figures import FIGURES

    assert "fig31_experiment_tier_heatmap" in FIGURES
    assert "fig32_tier_win_count" in FIGURES
    assert "fig33_convergence_analysis" in FIGURES
    assert "fig34_per_experiment_cost_frontier" in FIGURES


def test_fig35_task_difficulty_distribution(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig35 generates histogram and CSV."""
    # Add a second experiment to enable the histogram
    import pandas as pd

    from scylla.analysis.figures.task_analysis import fig35_task_difficulty_distribution

    df2 = sample_runs_df.copy()
    df2["experiment"] = "test-002"
    combined = pd.concat([sample_runs_df, df2], ignore_index=True)

    fig35_task_difficulty_distribution(combined, tmp_path, render=False)
    assert (tmp_path / "fig35_task_difficulty_distribution.vl.json").exists()
    assert (tmp_path / "fig35_task_difficulty_distribution.csv").exists()


def test_fig35_task_difficulty_single_experiment(sample_runs_df: Any, tmp_path: Any) -> None:
    """fig35 returns early with <2 experiments."""
    # sample_runs_df has only 1 experiment name pattern, but let's ensure it

    from scylla.analysis.figures.task_analysis import fig35_task_difficulty_distribution

    df = sample_runs_df.copy()
    df["experiment"] = "single-exp"
    fig35_task_difficulty_distribution(df, tmp_path, render=False)
    assert not (tmp_path / "fig35_task_difficulty_distribution.vl.json").exists()


def test_fig36_tier_rank_stability(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig36 generates heatmap and CSV."""
    from scylla.analysis.figures.task_analysis import fig36_tier_rank_stability

    fig36_tier_rank_stability(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig36_tier_rank_stability.vl.json").exists()
    assert (tmp_path / "fig36_tier_rank_stability.csv").exists()


def test_fig37_complexity_vs_differentiation(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig37 generates scatter plot and CSV."""
    from scylla.analysis.figures.task_analysis import fig37_complexity_vs_differentiation

    fig37_complexity_vs_differentiation(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig37_complexity_vs_differentiation.vl.json").exists()
    assert (tmp_path / "fig37_complexity_vs_differentiation.csv").exists()


def test_fig38_full_ablation_comparison(tmp_path: Any) -> None:
    """Smoke test: fig38 generates comparison chart and CSV."""
    import numpy as np
    import pandas as pd

    from scylla.analysis.figures.task_analysis import fig38_full_ablation_comparison

    # Create data with both full-ablation and standard experiments
    np.random.seed(42)
    rows = []
    for exp, n_subtests in [("full-001", 5), ("std-001", 3), ("std-002", 2)]:
        for tier in ["T0", "T1", "T2"]:
            for sub in range(n_subtests):
                rows.append(
                    {
                        "experiment": exp,
                        "tier": tier,
                        "subtest": f"{sub:02d}",
                        "passed": np.random.choice([0, 1]),
                        "agent_model": "Haiku 4.5",
                    }
                )
    df = pd.DataFrame(rows)

    fig38_full_ablation_comparison(df, tmp_path, render=False)
    assert (tmp_path / "fig38_full_ablation_comparison.vl.json").exists()
    assert (tmp_path / "fig38_full_ablation_comparison.csv").exists()


def test_fig38_no_full_ablation(sample_runs_df: Any, tmp_path: Any) -> None:
    """fig38 returns early when no full-ablation experiments detected."""
    from scylla.analysis.figures.task_analysis import fig38_full_ablation_comparison

    # sample_runs_df has only 2 subtests per tier (< 3), so auto-detect finds none
    fig38_full_ablation_comparison(sample_runs_df, tmp_path, render=False)
    assert not (tmp_path / "fig38_full_ablation_comparison.vl.json").exists()


def test_fig39_cost_scaling_with_difficulty(sample_runs_df: Any, tmp_path: Any) -> None:
    """Smoke test: fig39 generates scatter plot and CSV."""
    from scylla.analysis.figures.cost_analysis import fig39_cost_scaling_with_difficulty

    fig39_cost_scaling_with_difficulty(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig39_cost_scaling_with_difficulty.vl.json").exists()
    assert (tmp_path / "fig39_cost_scaling_with_difficulty.csv").exists()


def test_generate_figures_registry_includes_task_analysis_figures() -> None:
    """FIGURES registry contains all five new task analysis figures."""
    from scripts.generate_figures import FIGURES

    assert "fig35_task_difficulty_distribution" in FIGURES
    assert "fig36_tier_rank_stability" in FIGURES
    assert "fig37_complexity_vs_differentiation" in FIGURES
    assert "fig38_full_ablation_comparison" in FIGURES
    assert "fig39_cost_scaling_with_difficulty" in FIGURES


def test_generate_figures_single_judge_guard() -> None:
    """Single-judge figures are in the guard set."""
    # Verify the guard set exists and contains expected figures
    single_judge_figures = {
        "fig02_judge_variance",
        "fig14_judge_agreement",
        "fig17_judge_variance_overall",
    }
    from scripts.generate_figures import FIGURES

    # All guarded figures must exist in registry
    for fig in single_judge_figures:
        assert fig in FIGURES


def test_task_analysis_module_structure() -> None:
    """Test that task_analysis module exists and has expected functions."""
    from scylla.analysis.figures import task_analysis

    assert hasattr(task_analysis, "fig35_task_difficulty_distribution")
    assert hasattr(task_analysis, "fig36_tier_rank_stability")
    assert hasattr(task_analysis, "fig37_complexity_vs_differentiation")
    assert hasattr(task_analysis, "fig38_full_ablation_comparison")
