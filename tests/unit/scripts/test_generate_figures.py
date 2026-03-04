"""Tests for scripts/generate_figures.py."""

from __future__ import annotations

from generate_figures import FIGURES


class TestFiguresRegistry:
    """Tests for the FIGURES module-level registry."""

    def test_figures_dict_is_not_empty(self) -> None:
        """FIGURES registry contains at least one entry."""
        assert len(FIGURES) > 0

    def test_figures_keys_are_strings(self) -> None:
        """All keys in FIGURES are strings."""
        for key in FIGURES:
            assert isinstance(key, str)

    def test_figures_values_are_tuples(self) -> None:
        """All values in FIGURES are (category_str, callable) tuples."""
        for name, value in FIGURES.items():
            assert isinstance(value, tuple), f"{name} value is not a tuple"
            assert len(value) == 2, f"{name} tuple has unexpected length"

    def test_figures_categories_are_strings(self) -> None:
        """First element of each tuple (category) is a string."""
        for name, (category, _fn) in FIGURES.items():
            assert isinstance(category, str), f"{name} category is not a string"

    def test_figures_functions_are_callable(self) -> None:
        """Second element of each tuple (generator fn) is callable."""
        for name, (_category, fn) in FIGURES.items():
            assert callable(fn), f"{name} generator function is not callable"

    def test_known_figures_present(self) -> None:
        """Spot-check that key figures are registered."""
        expected = [
            "fig01_score_variance_by_tier",
            "fig04_pass_rate_by_tier",
            "fig06_cop_by_tier",
        ]
        for fig in expected:
            assert fig in FIGURES, f"{fig} not found in FIGURES registry"

    def test_no_duplicate_figure_names(self) -> None:
        """All figure names are unique (dict keys are inherently unique)."""
        # This is trivially true for a dict but documents the intent.
        assert len(FIGURES) == len(set(FIGURES.keys()))
