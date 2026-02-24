"""Analysis configuration loader.

Loads and provides access to centralized analysis parameters from config.yaml.
Ensures reproducibility by centralizing all tunable parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

__all__ = ["AnalysisConfig", "config"]


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
        return cast(float, self.get("statistical", "alpha", default=0.05))

    @property
    def bootstrap_resamples(self) -> int:
        """Number of bootstrap resamples."""
        return cast(int, self.get("statistical", "bootstrap", "n_resamples", default=10000))

    @property
    def bootstrap_random_state(self) -> int:
        """Random state for bootstrap resampling."""
        return cast(int, self.get("statistical", "bootstrap", "random_state", default=42))

    @property
    def bootstrap_confidence(self) -> float:
        """Bootstrap confidence level."""
        return cast(float, self.get("statistical", "bootstrap", "confidence_level", default=0.95))

    @property
    def min_sample_bootstrap(self) -> int:
        """Minimum sample size for bootstrap CI."""
        return cast(int, self.get("statistical", "min_samples", "bootstrap_ci", default=2))

    @property
    def min_sample_mann_whitney(self) -> int:
        """Minimum sample size for Mann-Whitney U test."""
        return cast(int, self.get("statistical", "min_samples", "mann_whitney", default=2))

    @property
    def min_sample_normality(self) -> int:
        """Minimum sample size for normality tests."""
        return cast(int, self.get("statistical", "min_samples", "normality_test", default=3))

    @property
    def min_sample_correlation(self) -> int:
        """Minimum sample size for correlation analysis."""
        return cast(int, self.get("statistical", "min_samples", "correlation", default=3))

    @property
    def min_sample_kruskal_wallis(self) -> int:
        """Minimum sample size for Kruskal-Wallis test."""
        return cast(int, self.get("statistical", "min_samples", "kruskal_wallis", default=2))

    @property
    def power_n_simulations(self) -> int:
        """Number of simulations for power analysis."""
        return cast(int, self.get("statistical", "power_analysis", "n_simulations", default=10000))

    @property
    def power_random_state(self) -> int:
        """Random state for power analysis simulations."""
        return cast(int, self.get("statistical", "power_analysis", "random_state", default=42))

    @property
    def adequate_power_threshold(self) -> float:
        """Threshold for adequate statistical power."""
        return cast(
            float,
            self.get("statistical", "power_analysis", "adequate_power_threshold", default=0.80),
        )

    @property
    def png_dpi_scale(self) -> float:
        """PNG DPI scale factor (300 DPI / 100 base = 3.0)."""
        dpi = cast(float, self.get("figures", "dpi", "png", default=300))
        return dpi / 100.0

    @property
    def figure_width(self) -> int:
        """Default figure width."""
        return cast(int, self.get("figures", "default_width", default=400))

    @property
    def figure_height(self) -> int:
        """Default figure height."""
        return cast(int, self.get("figures", "default_height", default=300))

    @property
    def pass_threshold(self) -> float:
        """Reference line threshold for acceptable pass-rate."""
        return cast(float, self.get("figures", "pass_threshold", default=0.60))

    @property
    def grade_order(self) -> list[str]:
        """Canonical grade ordering (S=best, F=worst)."""
        return cast(
            list[str], self.get("colors", "grade_order", default=["S", "A", "B", "C", "D", "F"])
        )

    @property
    def correlation_metrics(self) -> dict[str, str]:
        """Metric pairs for correlation analysis (column_name: display_name)."""
        return cast(
            dict[str, str],
            self.get(
                "figures",
                "correlation_metrics",
                default={
                    "score": "Score",
                    "cost_usd": "Cost (USD)",
                    "total_tokens": "Total Tokens",
                    "duration_seconds": "Duration (s)",
                },
            ),
        )

    @property
    def pipeline_version(self) -> str:
        """Analysis pipeline version."""
        return cast(str, self.get("reproducibility", "pipeline_version", default="1.0.0"))

    @property
    def config_version(self) -> str:
        """Configuration file version."""
        return cast(str, self.get("reproducibility", "config_version", default="1.0.0"))

    @property
    def colors(self) -> dict[str, dict[str, str]]:
        """All color palettes from config."""
        return cast(dict[str, dict[str, str]], self.get("colors", default={}))

    @property
    def model_colors(self) -> dict[str, str]:
        """Model color palette."""
        return cast(dict[str, str], self.get("colors", "models", default={}))

    @property
    def tier_colors(self) -> dict[str, str]:
        """Tier color palette."""
        return cast(dict[str, str], self.get("colors", "tiers", default={}))

    @property
    def grade_colors(self) -> dict[str, str]:
        """Grade color palette."""
        return cast(dict[str, str], self.get("colors", "grades", default={}))

    @property
    def judge_colors(self) -> dict[str, str]:
        """Judge color palette."""
        return cast(dict[str, str], self.get("colors", "judges", default={}))

    @property
    def criteria_colors(self) -> dict[str, str]:
        """Criteria color palette."""
        return cast(dict[str, str], self.get("colors", "criteria", default={}))

    @property
    def precision_p_values(self) -> int:
        """Number of decimal places for p-values."""
        return cast(int, self.get("tables", "precision", "p_values", default=4))

    @property
    def precision_effect_sizes(self) -> int:
        """Number of decimal places for effect sizes."""
        return cast(int, self.get("tables", "precision", "effect_sizes", default=3))

    @property
    def precision_percentages(self) -> int:
        """Number of decimal places for percentages."""
        return cast(int, self.get("tables", "precision", "percentages", default=1))

    @property
    def precision_costs(self) -> int:
        """Number of decimal places for costs."""
        return cast(int, self.get("tables", "precision", "costs", default=2))

    @property
    def precision_rates(self) -> int:
        """Number of decimal places for rates."""
        return cast(int, self.get("tables", "precision", "rates", default=3))

    @property
    def phase_colors(self) -> dict[str, str]:
        """Phase color palette."""
        return cast(dict[str, str], self.get("colors", "phases", default={}))

    @property
    def token_type_colors(self) -> dict[str, str]:
        """Token type color palette."""
        return cast(dict[str, str], self.get("colors", "token_types", default={}))


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
