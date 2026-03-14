"""Tests for scripts/generate_figures.py."""

from __future__ import annotations

from generate_figures import FIGURES

# ---------------------------------------------------------------------------
# TestFiguresRegistry
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "variance",
    "tier",
    "cost",
    "token",
    "model",
    "subtest",
    "effect_size",
    "correlation",
    "diagnostics",
    "impl_rate",
    "judge",
    "criteria",
}


class TestFiguresRegistry:
    """Tests for the FIGURES registry dict."""

    def test_registry_is_non_empty(self) -> None:
        """FIGURES registry contains at least one entry."""
        assert len(FIGURES) > 0

    def test_all_values_are_category_callable_tuples(self) -> None:
        """Every registry value is a 2-tuple of (str category, callable generator)."""
        for name, value in FIGURES.items():
            assert isinstance(value, tuple), f"{name}: expected tuple"
            assert len(value) == 2, f"{name}: expected 2-tuple"
            category, func = value
            assert isinstance(category, str), f"{name}: category should be str"
            assert callable(func), f"{name}: second element should be callable"

    def test_all_figure_names_start_with_fig(self) -> None:
        """All registry keys follow the 'fig' naming convention."""
        for name in FIGURES:
            assert name.startswith("fig"), f"{name} does not start with 'fig'"

    def test_all_categories_are_valid(self) -> None:
        """Every figure's category string belongs to the set of known valid categories."""
        for name, (category, _) in FIGURES.items():
            assert category in VALID_CATEGORIES, f"{name} has unknown category '{category}'"

    def test_no_duplicate_generator_functions(self) -> None:
        """No two figures share the same generator function object."""
        seen: dict[int, str] = {}
        for name, (_, func) in FIGURES.items():
            func_id = id(func)
            assert func_id not in seen, f"{name} reuses generator from {seen[func_id]}"
            seen[func_id] = name

    def test_expected_figure_count(self) -> None:
        """Registry contains at least 30 figures, consistent with the documented ~34."""
        # 34 figures as documented in README and audit
        assert len(FIGURES) >= 30, f"Expected ~34 figures, got {len(FIGURES)}"
