"""Analysis configuration loader.

Loads and provides access to centralized analysis parameters from config.yaml.
Ensures reproducibility by centralizing all tunable parameters.

Python Justification: YAML loading and dict access (no Mojo stdlib support yet).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class AnalysisConfig:
    """Analysis configuration singleton."""

    _instance: AnalysisConfig | None = None
    _config: dict[str, Any] | None = None

    def __new__(cls) -> AnalysisConfig:
        """Singleton pattern to ensure config is loaded once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Load configuration from YAML file."""
        if self._config is None:
            config_path = Path(__file__).parent / "config.yaml"
            with open(config_path, encoding="utf-8") as f:
                self._config = yaml.safe_load(f)

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get configuration value by nested keys.

        Args:
            *keys: Nested keys to traverse (e.g., "statistical", "alpha")
            default: Default value if key path not found

        Returns:
            Configuration value or default

        Examples:
            >>> config = AnalysisConfig()
            >>> config.get("statistical", "alpha")
            0.05
            >>> config.get("figures", "dpi", "png")
            300

        """
        value = self._config
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    @property
    def alpha(self) -> float:
        """Statistical significance threshold."""
        return self.get("statistical", "alpha", default=0.05)

    @property
    def bootstrap_resamples(self) -> int:
        """Number of bootstrap resamples."""
        return self.get("statistical", "bootstrap", "n_resamples", default=10000)

    @property
    def bootstrap_random_state(self) -> int:
        """Random state for bootstrap resampling."""
        return self.get("statistical", "bootstrap", "random_state", default=42)

    @property
    def bootstrap_confidence(self) -> float:
        """Bootstrap confidence level."""
        return self.get("statistical", "bootstrap", "confidence_level", default=0.95)

    @property
    def min_sample_bootstrap(self) -> int:
        """Minimum sample size for bootstrap CI."""
        return self.get("statistical", "min_samples", "bootstrap_ci", default=2)

    @property
    def min_sample_mann_whitney(self) -> int:
        """Minimum sample size for Mann-Whitney U test."""
        return self.get("statistical", "min_samples", "mann_whitney", default=2)

    @property
    def min_sample_normality(self) -> int:
        """Minimum sample size for normality tests."""
        return self.get("statistical", "min_samples", "normality_test", default=3)

    @property
    def min_sample_correlation(self) -> int:
        """Minimum sample size for correlation analysis."""
        return self.get("statistical", "min_samples", "correlation", default=3)

    @property
    def png_dpi_scale(self) -> float:
        """PNG DPI scale factor (300 DPI / 100 base = 3.0)."""
        dpi = self.get("figures", "dpi", "png", default=300)
        return dpi / 100.0

    @property
    def figure_width(self) -> int:
        """Default figure width."""
        return self.get("figures", "default_width", default=400)

    @property
    def figure_height(self) -> int:
        """Default figure height."""
        return self.get("figures", "default_height", default=300)

    @property
    def pass_threshold(self) -> float:
        """Reference line threshold for acceptable pass-rate."""
        return self.get("figures", "pass_threshold", default=0.60)

    @property
    def grade_order(self) -> list[str]:
        """Canonical grade ordering (S=best, F=worst)."""
        return self.get("colors", "grade_order", default=["S", "A", "B", "C", "D", "F"])

    @property
    def pipeline_version(self) -> str:
        """Analysis pipeline version."""
        return self.get("reproducibility", "pipeline_version", default="1.0.0")

    @property
    def config_version(self) -> str:
        """Configuration file version."""
        return self.get("reproducibility", "config_version", default="1.0.0")


# Global singleton instance
config = AnalysisConfig()

# Convenient module-level constants (for backwards compatibility)
ALPHA = config.alpha
BOOTSTRAP_RESAMPLES = config.bootstrap_resamples
BOOTSTRAP_RANDOM_STATE = config.bootstrap_random_state
BOOTSTRAP_CONFIDENCE = config.bootstrap_confidence
MIN_SAMPLE_BOOTSTRAP = config.min_sample_bootstrap
MIN_SAMPLE_MANN_WHITNEY = config.min_sample_mann_whitney
MIN_SAMPLE_NORMALITY = config.min_sample_normality
MIN_SAMPLE_CORRELATION = config.min_sample_correlation
PNG_DPI_SCALE = config.png_dpi_scale
FIGURE_WIDTH = config.figure_width
FIGURE_HEIGHT = config.figure_height
