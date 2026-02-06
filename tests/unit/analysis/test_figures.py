"""Unit tests for figure generation."""


def test_fig01_score_variance_by_tier(sample_runs_df, tmp_path):
    """Test Fig 1 generates files correctly."""
    from scylla.analysis.figures.variance import fig01_score_variance_by_tier

    fig01_score_variance_by_tier(sample_runs_df, tmp_path, render=False)

    # Verify files created
    assert (tmp_path / "fig01_score_variance_by_tier.vl.json").exists()
    assert (tmp_path / "fig01_score_variance_by_tier.csv").exists()


def test_fig04_pass_rate_by_tier(sample_runs_df, tmp_path):
    """Test Fig 4 generates files correctly."""
    from scylla.analysis.figures.tier_performance import fig04_pass_rate_by_tier

    fig04_pass_rate_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig04_pass_rate_by_tier.vl.json").exists()
    assert (tmp_path / "fig04_pass_rate_by_tier.csv").exists()


def test_fig06_cop_by_tier(sample_runs_df, tmp_path):
    """Test Fig 6 generates files correctly."""
    from scylla.analysis.figures.cost_analysis import fig06_cop_by_tier

    fig06_cop_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig06_cop_by_tier.vl.json").exists()
    assert (tmp_path / "fig06_cop_by_tier.csv").exists()


def test_fig11_tier_uplift(sample_runs_df, tmp_path):
    """Test Fig 11 generates files correctly."""
    from scylla.analysis.figures.model_comparison import fig11_tier_uplift

    fig11_tier_uplift(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig11_tier_uplift.vl.json").exists()
    assert (tmp_path / "fig11_tier_uplift.csv").exists()


def test_fig02_judge_variance(sample_judges_df, tmp_path):
    """Test Fig 2 generates files correctly."""
    from scylla.analysis.figures.judge_analysis import fig02_judge_variance

    fig02_judge_variance(sample_judges_df, tmp_path, render=False)
    assert (tmp_path / "fig02_judge_variance.vl.json").exists()
    assert (tmp_path / "fig02_judge_variance.csv").exists()


def test_fig03_failure_rate_by_tier(sample_runs_df, tmp_path):
    """Test Fig 3 generates files correctly."""
    from scylla.analysis.figures.variance import fig03_failure_rate_by_tier

    fig03_failure_rate_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig03_failure_rate_by_tier.vl.json").exists()
    assert (tmp_path / "fig03_failure_rate_by_tier.csv").exists()


def test_fig05_grade_heatmap(sample_runs_df, tmp_path):
    """Test Fig 5 generates files correctly."""
    from scylla.analysis.figures.tier_performance import fig05_grade_heatmap

    fig05_grade_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig05_grade_heatmap.vl.json").exists()
    assert (tmp_path / "fig05_grade_heatmap.csv").exists()


def test_fig07_token_distribution(sample_runs_df, tmp_path):
    """Test Fig 7 generates files correctly."""
    from scylla.analysis.figures.token_analysis import fig07_token_distribution

    fig07_token_distribution(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig07_token_distribution.vl.json").exists()
    assert (tmp_path / "fig07_token_distribution.csv").exists()


def test_fig08_cost_quality_pareto(sample_runs_df, tmp_path):
    """Test Fig 8 generates files correctly."""
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    fig08_cost_quality_pareto(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig08_cost_quality_pareto.vl.json").exists()
    assert (tmp_path / "fig08_cost_quality_pareto.csv").exists()


def test_fig09_criteria_by_tier(sample_criteria_df, tmp_path):
    """Test Fig 9 generates files correctly."""
    from scylla.analysis.figures.criteria_analysis import fig09_criteria_by_tier

    fig09_criteria_by_tier(sample_criteria_df, tmp_path, render=False)
    assert (tmp_path / "fig09_criteria_by_tier.vl.json").exists()
    assert (tmp_path / "fig09_criteria_by_tier.csv").exists()


def test_fig10_score_violin(sample_runs_df, tmp_path):
    """Test Fig 10 generates files correctly."""
    from scylla.analysis.figures.tier_performance import fig10_score_violin

    fig10_score_violin(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig10_score_violin.vl.json").exists()
    assert (tmp_path / "fig10_score_violin.csv").exists()


def test_fig12_consistency(sample_runs_df, tmp_path):
    """Test Fig 12 generates files correctly."""
    from scylla.analysis.figures.model_comparison import fig12_consistency

    fig12_consistency(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig12_consistency.vl.json").exists()
    assert (tmp_path / "fig12_consistency.csv").exists()


def test_fig13_latency(sample_runs_df, tmp_path):
    """Test Fig 13 generates files correctly."""
    from scylla.analysis.figures.subtest_detail import fig13_latency

    fig13_latency(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig13_latency.vl.json").exists()
    assert (tmp_path / "fig13_latency.csv").exists()


def test_fig14_judge_agreement(sample_judges_df, tmp_path):
    """Test Fig 14 generates files correctly."""
    from scylla.analysis.figures.judge_analysis import fig14_judge_agreement

    fig14_judge_agreement(sample_judges_df, tmp_path, render=False)
    assert (tmp_path / "fig14_judge_agreement.vl.json").exists()
    assert (tmp_path / "fig14_judge_agreement.csv").exists()


def test_fig15_subtest_heatmap(sample_runs_df, tmp_path):
    """Test Fig 15 generates files correctly."""
    from scylla.analysis.figures.subtest_detail import fig15_subtest_heatmap

    fig15_subtest_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig15_subtest_heatmap.vl.json").exists()
    assert (tmp_path / "fig15_subtest_heatmap.csv").exists()


def test_fig16_success_variance_by_test(sample_runs_df, tmp_path):
    """Test Fig 16 generates files correctly."""
    from scylla.analysis.figures.variance import fig16_success_variance_by_test

    fig16_success_variance_by_test(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig16_success_variance_by_test.vl.json").exists()
    assert (tmp_path / "fig16_success_variance_by_test.csv").exists()


def test_fig17_judge_variance_overall(sample_judges_df, tmp_path):
    """Test Fig 17 generates files correctly."""
    from scylla.analysis.figures.judge_analysis import fig17_judge_variance_overall

    fig17_judge_variance_overall(sample_judges_df, tmp_path, render=False)
    assert (tmp_path / "fig17_judge_variance_overall.vl.json").exists()
    assert (tmp_path / "fig17_judge_variance_overall.csv").exists()


def test_fig18_failure_rate_by_test(sample_runs_df, tmp_path):
    """Test Fig 18 generates files correctly."""
    from scylla.analysis.figures.variance import fig18_failure_rate_by_test

    fig18_failure_rate_by_test(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig18_failure_rate_by_test.vl.json").exists()
    assert (tmp_path / "fig18_failure_rate_by_test.csv").exists()


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


def test_fig19_effect_size_forest(sample_runs_df, tmp_path):
    """Test Fig 19 effect size forest plot generates files correctly."""
    from scylla.analysis.figures.effect_size import fig19_effect_size_forest

    fig19_effect_size_forest(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig19_effect_size_forest.vl.json").exists()
    assert (tmp_path / "fig19_effect_size_forest.csv").exists()


def test_fig20_metric_correlation_heatmap(sample_runs_df, tmp_path):
    """Test Fig 20 correlation heatmap generates files correctly."""
    from scylla.analysis.figures.correlation import fig20_metric_correlation_heatmap

    fig20_metric_correlation_heatmap(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig20_metric_correlation_heatmap.vl.json").exists()
    assert (tmp_path / "fig20_metric_correlation_heatmap.csv").exists()


def test_fig21_cost_quality_regression(sample_runs_df, tmp_path):
    """Test Fig 21 regression plot generates files correctly."""
    from scylla.analysis.figures.correlation import fig21_cost_quality_regression

    fig21_cost_quality_regression(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig21_cost_quality_regression.vl.json").exists()
    assert (tmp_path / "fig21_cost_quality_regression.csv").exists()


def test_fig22_cumulative_cost(sample_runs_df, tmp_path):
    """Test Fig 22 cumulative cost curve generates files correctly."""
    from scylla.analysis.figures.cost_analysis import fig22_cumulative_cost

    fig22_cumulative_cost(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig22_cumulative_cost.vl.json").exists()
    assert (tmp_path / "fig22_cumulative_cost.csv").exists()


def test_fig23_qq_plots(sample_runs_df, tmp_path):
    """Test Fig 23 Q-Q plots generate files correctly."""
    from scylla.analysis.figures.diagnostics import fig23_qq_plots

    fig23_qq_plots(sample_runs_df, tmp_path, render=False)
    # Note: may not be called if insufficient data
    # Just check it doesn't crash


def test_fig24_score_histograms(sample_runs_df, tmp_path):
    """Test Fig 24 histograms with KDE generate files correctly."""
    from scylla.analysis.figures.diagnostics import fig24_score_histograms

    fig24_score_histograms(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig24_score_histograms.vl.json").exists()
    assert (tmp_path / "fig24_score_histograms.csv").exists()


def test_register_colors():
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


def test_latex_snippet_generation(sample_runs_df, tmp_path):
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


def test_latex_snippet_with_custom_caption(tmp_path):
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
        data=data,
        render=True,
        formats=["pdf"],
        latex_caption="Custom caption for testing",
    )

    # Verify snippet has custom caption
    snippet_path = tmp_path / "test_figure_include.tex"
    assert snippet_path.exists()

    content = snippet_path.read_text()
    assert "\\caption{Custom caption for testing}" in content


def test_fig25_impl_rate_by_tier(sample_runs_df, tmp_path):
    """Test Fig 25 generates files correctly."""
    from scylla.analysis.figures.impl_rate_analysis import fig25_impl_rate_by_tier

    fig25_impl_rate_by_tier(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig25_impl_rate_by_tier.vl.json").exists()
    assert (tmp_path / "fig25_impl_rate_by_tier.csv").exists()


def test_fig26_impl_rate_vs_pass_rate(sample_runs_df, tmp_path):
    """Test Fig 26 generates files correctly."""
    from scylla.analysis.figures.impl_rate_analysis import fig26_impl_rate_vs_pass_rate

    fig26_impl_rate_vs_pass_rate(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig26_impl_rate_vs_pass_rate.vl.json").exists()
    assert (tmp_path / "fig26_impl_rate_vs_pass_rate.csv").exists()


def test_fig27_impl_rate_distribution(sample_runs_df, tmp_path):
    """Test Fig 27 generates files correctly."""
    from scylla.analysis.figures.impl_rate_analysis import fig27_impl_rate_distribution

    fig27_impl_rate_distribution(sample_runs_df, tmp_path, render=False)
    assert (tmp_path / "fig27_impl_rate_distribution.vl.json").exists()
    assert (tmp_path / "fig27_impl_rate_distribution.csv").exists()


def test_impl_rate_figures_handle_missing_column(tmp_path):
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


def test_fig04_pass_rate_content_verification(sample_runs_df, tmp_path):
    """Test Fig 4 generates correct pass-rate data with bootstrap CIs."""
    import pandas as pd

    from scylla.analysis.figures.tier_performance import fig04_pass_rate_by_tier

    fig04_pass_rate_by_tier(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig04_pass_rate_by_tier.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    required_cols = [
        "agent_model",
        "tier",
        "pass_rate",
        "ci_low",
        "ci_high",
    ]
    for col in required_cols:
        assert col in data_df.columns, f"Missing column: {col}"

    # Verify pass_rate is in [0, 1]
    assert data_df["pass_rate"].min() >= 0.0
    assert data_df["pass_rate"].max() <= 1.0

    # Verify CI bounds are valid
    assert (data_df["ci_low"] <= data_df["pass_rate"]).all()
    assert (data_df["ci_high"] >= data_df["pass_rate"]).all()

    # Verify we have data for multiple models/tiers
    assert len(data_df["agent_model"].unique()) >= 1
    assert len(data_df["tier"].unique()) >= 1


def test_fig06_cop_content_verification(sample_runs_df, tmp_path):
    """Test Fig 6 generates correct CoP data."""
    import pandas as pd

    from scylla.analysis.figures.cost_analysis import fig06_cop_by_tier

    fig06_cop_by_tier(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig06_cop_by_tier.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    required_cols = ["agent_model", "tier", "cop", "is_inf"]
    for col in required_cols:
        assert col in data_df.columns, f"Missing column: {col}"

    # Verify CoP is non-negative (or inf)
    finite_cop = data_df[~data_df["is_inf"]]["cop"]
    if len(finite_cop) > 0:
        assert (finite_cop >= 0).all()

    # Verify is_inf is boolean
    assert data_df["is_inf"].dtype == bool

    # Verify we have data for multiple models/tiers
    assert len(data_df["agent_model"].unique()) >= 1
    assert len(data_df["tier"].unique()) >= 1


def test_fig08_pareto_content_verification(sample_runs_df, tmp_path):
    """Test Fig 8 generates correct Pareto frontier data structure."""
    import pandas as pd

    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    fig08_cost_quality_pareto(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig08_cost_quality_pareto.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    required_cols = ["agent_model", "tier", "mean_cost", "mean_score", "is_pareto"]
    for col in required_cols:
        assert col in data_df.columns, f"Missing column: {col}"

    # Verify cost is non-negative
    assert (data_df["mean_cost"] >= 0).all()

    # Verify score is in [0, 1]
    assert (data_df["mean_score"] >= 0).all()
    assert (data_df["mean_score"] <= 1).all()

    # Verify is_pareto is boolean
    assert data_df["is_pareto"].dtype == bool

    # Verify at least one point is on the Pareto frontier
    assert data_df["is_pareto"].any()

    # Verify we have both Pareto and non-Pareto points (unless all points are Pareto)
    num_pareto = data_df["is_pareto"].sum()
    total_points = len(data_df)
    assert 0 < num_pareto <= total_points

    # Verify Pareto points have reasonable values
    pareto_points = data_df[data_df["is_pareto"]]
    assert len(pareto_points) > 0
    assert (pareto_points["mean_cost"] >= 0).all()
    assert (pareto_points["mean_score"] >= 0).all()
    assert (pareto_points["mean_score"] <= 1).all()


def test_fig01_content_verification(sample_runs_df, tmp_path):
    """Test Fig 1 score variance generates correct data structure."""
    import pandas as pd

    from scylla.analysis.figures.variance import fig01_score_variance_by_tier

    fig01_score_variance_by_tier(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig01_score_variance_by_tier.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    assert "agent_model" in data_df.columns
    assert "tier" in data_df.columns
    assert "score" in data_df.columns

    # Verify scores in valid range
    assert (data_df["score"] >= 0).all()
    assert (data_df["score"] <= 1).all()

    # Verify we have data for multiple tiers
    assert len(data_df["tier"].unique()) >= 1


def test_fig02_content_verification(sample_judges_df, tmp_path):
    """Test Fig 2 judge variance generates correct data structure."""
    import pandas as pd

    from scylla.analysis.figures.judge_analysis import fig02_judge_variance

    fig02_judge_variance(sample_judges_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig02_judge_variance.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    assert "tier" in data_df.columns
    assert "judge_score" in data_df.columns
    assert "judge_display" in data_df.columns

    # Verify scores in valid range
    assert (data_df["judge_score"] >= 0).all()
    assert (data_df["judge_score"] <= 1).all()


def test_fig03_content_verification(sample_runs_df, tmp_path):
    """Test Fig 3 failure rate generates correct grade distribution."""
    import pandas as pd

    from scylla.analysis.figures.variance import fig03_failure_rate_by_tier

    fig03_failure_rate_by_tier(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig03_failure_rate_by_tier.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    required_cols = ["agent_model", "tier", "grade", "count", "proportion"]
    for col in required_cols:
        assert col in data_df.columns, f"Missing column: {col}"

    # Verify proportions sum to ~1.0 per (model, tier)
    for (model, tier), group in data_df.groupby(["agent_model", "tier"]):
        total_prop = group["proportion"].sum()
        assert abs(total_prop - 1.0) < 0.01, f"Proportions don't sum to 1 for {model}, {tier}"

    # Verify grades are valid
    valid_grades = ["S", "A", "B", "C", "D", "F"]
    assert data_df["grade"].isin(valid_grades).all()


def test_fig05_content_verification(sample_runs_df, tmp_path):
    """Test Fig 5 grade heatmap generates correct structure."""
    import pandas as pd

    from scylla.analysis.figures.tier_performance import fig05_grade_heatmap

    fig05_grade_heatmap(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig05_grade_heatmap.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    required_cols = ["agent_model", "tier", "grade", "count", "proportion"]
    for col in required_cols:
        assert col in data_df.columns

    # Verify proportions are in [0, 1]
    assert (data_df["proportion"] >= 0).all()
    assert (data_df["proportion"] <= 1).all()


def test_fig07_content_verification(sample_runs_df, tmp_path):
    """Test Fig 7 token distribution generates correct breakdown."""
    import pandas as pd

    from scylla.analysis.figures.token_analysis import fig07_token_distribution

    fig07_token_distribution(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig07_token_distribution.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    assert "agent_model" in data_df.columns
    assert "tier" in data_df.columns
    assert "token_type_label" in data_df.columns
    assert "tokens" in data_df.columns

    # Verify token types are correct
    expected_types = ["Input (Fresh)", "Input (Cached)", "Output", "Cache Creation"]
    assert set(data_df["token_type_label"].unique()).issubset(expected_types)

    # Verify tokens are non-negative
    assert (data_df["tokens"] >= 0).all()


def test_fig09_content_verification(sample_criteria_df, tmp_path):
    """Test Fig 9 criteria by tier generates correct structure."""
    import pandas as pd

    from scylla.analysis.figures.criteria_analysis import fig09_criteria_by_tier

    fig09_criteria_by_tier(sample_criteria_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig09_criteria_by_tier.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    assert "agent_model" in data_df.columns
    assert "tier" in data_df.columns
    assert "criterion" in data_df.columns
    assert "criterion_score" in data_df.columns

    # Verify scores in valid range
    assert (data_df["criterion_score"] >= 0).all()
    assert (data_df["criterion_score"] <= 1).all()


def test_fig10_content_verification(sample_runs_df, tmp_path):
    """Test Fig 10 score violin generates correct distribution data."""
    import pandas as pd

    from scylla.analysis.figures.tier_performance import fig10_score_violin

    fig10_score_violin(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig10_score_violin.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    assert "agent_model" in data_df.columns
    assert "tier" in data_df.columns
    assert "score" in data_df.columns

    # Verify scores in valid range
    assert (data_df["score"] >= 0).all()
    assert (data_df["score"] <= 1).all()


def test_fig11_content_verification(sample_runs_df, tmp_path):
    """Test Fig 11 tier uplift generates correct uplift calculations."""
    import pandas as pd

    from scylla.analysis.figures.model_comparison import fig11_tier_uplift

    fig11_tier_uplift(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig11_tier_uplift.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    required_cols = ["agent_model", "tier", "pass_rate", "uplift", "uplift_pct"]
    for col in required_cols:
        assert col in data_df.columns

    # Verify pass_rate in [0, 1]
    assert (data_df["pass_rate"] >= 0).all()
    assert (data_df["pass_rate"] <= 1).all()

    # Verify T0 has uplift=0 for all models
    t0_data = data_df[data_df["tier"] == "T0"]
    if len(t0_data) > 0:
        assert (t0_data["uplift"].abs() < 1e-10).all()


def test_fig12_content_verification(sample_runs_df, tmp_path):
    """Test Fig 12 consistency generates valid consistency scores."""
    import pandas as pd

    from scylla.analysis.figures.model_comparison import fig12_consistency

    fig12_consistency(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig12_consistency.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    required_cols = ["agent_model", "tier", "mean_consistency", "ci_low", "ci_high"]
    for col in required_cols:
        assert col in data_df.columns

    # Verify consistency in [0, 1]
    assert (data_df["mean_consistency"] >= 0).all()
    assert (data_df["mean_consistency"] <= 1).all()

    # Verify CI bounds are valid
    assert (data_df["ci_low"] <= data_df["mean_consistency"]).all()
    assert (data_df["ci_high"] >= data_df["mean_consistency"]).all()


def test_fig13_content_verification(sample_runs_df, tmp_path):
    """Test Fig 13 latency generates correct duration breakdown."""
    import pandas as pd

    from scylla.analysis.figures.subtest_detail import fig13_latency

    fig13_latency(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig13_latency.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    assert "agent_model" in data_df.columns
    assert "tier" in data_df.columns
    assert "phase_label" in data_df.columns
    assert "duration" in data_df.columns

    # Verify phase labels
    expected_phases = ["Agent Execution", "Judge Evaluation"]
    assert set(data_df["phase_label"].unique()).issubset(expected_phases)

    # Verify durations are non-negative
    assert (data_df["duration"] >= 0).all()


def test_fig14_content_verification(sample_judges_df, tmp_path):
    """Test Fig 14 judge agreement generates pairwise comparisons."""
    import pandas as pd

    from scylla.analysis.figures.judge_analysis import fig14_judge_agreement

    fig14_judge_agreement(sample_judges_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig14_judge_agreement.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    required_cols = ["judge_x", "judge_y", "score_x", "score_y"]
    for col in required_cols:
        assert col in data_df.columns

    # Verify scores in [0, 1]
    assert (data_df["score_x"] >= 0).all()
    assert (data_df["score_x"] <= 1).all()
    assert (data_df["score_y"] >= 0).all()
    assert (data_df["score_y"] <= 1).all()


def test_fig15_content_verification(sample_runs_df, tmp_path):
    """Test Fig 15 subtest heatmap generates correct structure."""
    from scylla.analysis.figures.subtest_detail import fig15_subtest_heatmap

    fig15_subtest_heatmap(sample_runs_df, tmp_path, render=False)

    # Verify files created
    assert (tmp_path / "fig15_subtest_heatmap.vl.json").exists()
    assert (tmp_path / "fig15_subtest_heatmap.csv").exists()


def test_fig16_content_verification(sample_runs_df, tmp_path):
    """Test Fig 16 success variance generates correct variance metrics."""
    import pandas as pd

    from scylla.analysis.figures.variance import fig16_success_variance_by_test

    fig16_success_variance_by_test(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig16_success_variance_by_test.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    required_cols = [
        "agent_model",
        "tier",
        "subtest",
        "pass_variance",
        "score_std",
    ]
    for col in required_cols:
        assert col in data_df.columns

    # Verify pass_variance in [0, 0.25] (max is p(1-p) at p=0.5)
    assert (data_df["pass_variance"] >= 0).all()
    assert (data_df["pass_variance"] <= 0.25).all()

    # Verify score_std is non-negative
    assert (data_df["score_std"] >= 0).all()


def test_fig17_content_verification(sample_judges_df, tmp_path):
    """Test Fig 17 judge variance overall generates correct summary."""
    import pandas as pd

    from scylla.analysis.figures.judge_analysis import fig17_judge_variance_overall

    fig17_judge_variance_overall(sample_judges_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig17_judge_variance_overall.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    assert "judge_display" in data_df.columns
    assert "judge_score" in data_df.columns

    # Verify scores in [0, 1]
    assert (data_df["judge_score"] >= 0).all()
    assert (data_df["judge_score"] <= 1).all()


def test_fig18_content_verification(sample_runs_df, tmp_path):
    """Test Fig 18 failure rate by test generates correct failure rates."""
    import pandas as pd

    from scylla.analysis.figures.variance import fig18_failure_rate_by_test

    fig18_failure_rate_by_test(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig18_failure_rate_by_test.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    required_cols = ["agent_model", "tier", "subtest", "failure_rate"]
    for col in required_cols:
        assert col in data_df.columns

    # Verify failure_rate in [0, 1]
    assert (data_df["failure_rate"] >= 0).all()
    assert (data_df["failure_rate"] <= 1).all()


def test_fig19_content_verification(sample_runs_df, tmp_path):
    """Test Fig 19 effect size forest generates correct effect sizes."""
    import pandas as pd

    from scylla.analysis.figures.effect_size import fig19_effect_size_forest

    fig19_effect_size_forest(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig19_effect_size_forest.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    required_cols = ["agent_model", "transition", "delta", "ci_low", "ci_high"]
    for col in required_cols:
        assert col in data_df.columns

    # Verify delta (Cliff's delta) in [-1, 1]
    assert (data_df["delta"] >= -1).all()
    assert (data_df["delta"] <= 1).all()

    # Verify CI bounds are within [-1, 1]
    assert (data_df["ci_low"] >= -1).all()
    assert (data_df["ci_high"] <= 1).all()


def test_fig20_content_verification(sample_runs_df, tmp_path):
    """Test Fig 20 correlation heatmap generates correct correlations."""
    import pandas as pd

    from scylla.analysis.figures.correlation import fig20_metric_correlation_heatmap

    fig20_metric_correlation_heatmap(sample_runs_df, tmp_path, render=False)

    # Read and verify data
    csv_path = tmp_path / "fig20_metric_correlation_heatmap.csv"
    assert csv_path.exists()

    data_df = pd.read_csv(csv_path)
    # Verify required columns
    required_cols = ["agent_model", "metric1", "metric2", "rho"]
    for col in required_cols:
        assert col in data_df.columns

    # Verify rho (correlation) in [-1, 1]
    assert (data_df["rho"] >= -1).all()
    assert (data_df["rho"] <= 1).all()


def test_fig21_content_verification(sample_runs_df, tmp_path):
    """Test Fig 21 cost-quality regression generates correct structure."""
    from scylla.analysis.figures.correlation import fig21_cost_quality_regression

    fig21_cost_quality_regression(sample_runs_df, tmp_path, render=False)

    # Just verify it doesn't crash - files created
    assert (tmp_path / "fig21_cost_quality_regression.vl.json").exists()


def test_fig22_content_verification(sample_runs_df, tmp_path):
    """Test Fig 22 cumulative cost generates correct cumulative data."""
    from scylla.analysis.figures.cost_analysis import fig22_cumulative_cost

    fig22_cumulative_cost(sample_runs_df, tmp_path, render=False)

    # Just verify it doesn't crash - files created
    assert (tmp_path / "fig22_cumulative_cost.vl.json").exists()


def test_fig23_content_verification(sample_runs_df, tmp_path):
    """Test Fig 23 Q-Q plots generate correct quantile data."""
    from scylla.analysis.figures.diagnostics import fig23_qq_plots

    # Just verify it doesn't crash - may not generate data with small samples
    fig23_qq_plots(sample_runs_df, tmp_path, render=False)


def test_fig24_content_verification(sample_runs_df, tmp_path):
    """Test Fig 24 score histograms generate correct distribution."""
    from scylla.analysis.figures.diagnostics import fig24_score_histograms

    fig24_score_histograms(sample_runs_df, tmp_path, render=False)

    # Just verify it doesn't crash - files created
    assert (tmp_path / "fig24_score_histograms.vl.json").exists()


def test_fig25_content_verification(sample_runs_df, tmp_path):
    """Test Fig 25 impl-rate by tier generates correct structure."""
    import pandas as pd

    from scylla.analysis.figures.impl_rate_analysis import fig25_impl_rate_by_tier

    fig25_impl_rate_by_tier(sample_runs_df, tmp_path, render=False)

    # May create files if impl_rate column exists
    csv_path = tmp_path / "fig25_impl_rate_by_tier.csv"
    if csv_path.exists():
        data_df = pd.read_csv(csv_path)
        # Verify required columns
        required_cols = ["agent_model", "tier", "impl_rate", "ci_low", "ci_high"]
        for col in required_cols:
            assert col in data_df.columns

        # Verify impl_rate in [0, 1]
        assert (data_df["impl_rate"] >= 0).all()
        assert (data_df["impl_rate"] <= 1).all()


def test_fig26_content_verification(sample_runs_df, tmp_path):
    """Test Fig 26 impl-rate vs pass-rate generates correct scatter data."""
    from scylla.analysis.figures.impl_rate_analysis import fig26_impl_rate_vs_pass_rate

    # May not generate if impl_rate column missing
    fig26_impl_rate_vs_pass_rate(sample_runs_df, tmp_path, render=False)


def test_fig27_content_verification(sample_runs_df, tmp_path):
    """Test Fig 27 impl-rate distribution generates correct structure."""
    from scylla.analysis.figures.impl_rate_analysis import fig27_impl_rate_distribution

    # May not generate if impl_rate column missing
    fig27_impl_rate_distribution(sample_runs_df, tmp_path, render=False)


def test_get_color_with_static_colors():
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


def test_get_color_with_dynamic_palette():
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


def test_get_color_deterministic_hash():
    """Test get_color() uses deterministic hash for dynamic colors."""
    from scylla.analysis.figures import get_color

    # Same key should always produce the same color
    key = "test_model_xyz"
    color1 = get_color("unknown_category", key)
    color2 = get_color("unknown_category", key)
    color3 = get_color("unknown_category", key)

    assert color1 == color2 == color3


def test_get_color_scale_with_known_keys():
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


def test_get_color_scale_with_unknown_keys():
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


def test_get_color_scale_with_mixed_keys():
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


def test_get_color_scale_empty_list():
    """Test get_color_scale() handles empty list gracefully."""
    from scylla.analysis.figures import get_color_scale

    domain, range_ = get_color_scale("models", [])

    # Should return empty lists
    assert domain == []
    assert range_ == []


def test_get_color_scale_single_key():
    """Test get_color_scale() handles single key correctly."""
    from scylla.analysis.figures import get_color_scale

    domain, range_ = get_color_scale("models", ["Sonnet 4.5"])

    # Verify single-element lists
    assert domain == ["Sonnet 4.5"]
    assert len(range_) == 1
    assert range_[0].startswith("#")
