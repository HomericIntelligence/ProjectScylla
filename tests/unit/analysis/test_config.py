"""Unit tests for analysis configuration."""

import pytest

from scylla.analysis.config import ALPHA, AnalysisConfig, config


def test_config_singleton():
    """Test config is a singleton."""
    config1 = AnalysisConfig()
    config2 = AnalysisConfig()
    assert config1 is config2


def test_config_alpha():
    """Test alpha parameter."""
    assert config.alpha == pytest.approx(0.05)
    assert ALPHA == pytest.approx(0.05)


def test_config_bootstrap_params():
    """Test bootstrap parameters."""
    assert config.bootstrap_resamples == 10000
    assert config.bootstrap_random_state == 42
    assert config.bootstrap_confidence == pytest.approx(0.95)


def test_config_min_samples():
    """Test minimum sample size parameters."""
    assert config.min_sample_bootstrap == 2
    assert config.min_sample_mann_whitney == 2
    assert config.min_sample_normality == 3
    assert config.min_sample_correlation == 3


def test_config_figure_params():
    """Test figure parameters."""
    assert config.png_dpi_scale == pytest.approx(3.0)  # 300 DPI / 100
    assert config.figure_width == 400
    assert config.figure_height == 300


def test_config_get_nested():
    """Test nested key access."""
    assert config.get("statistical", "alpha") == pytest.approx(0.05)
    assert config.get("figures", "dpi", "png") == 300
    assert config.get("nonexistent", "key", default="default") == "default"


def test_config_versions():
    """Test version metadata."""
    assert config.pipeline_version == "1.0.0"
    assert config.config_version == "1.0.0"
