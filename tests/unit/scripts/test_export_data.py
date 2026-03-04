"""Tests for scripts/export_data.py."""

from __future__ import annotations

import math
from unittest.mock import patch

from export_data import json_nan_handler


class TestJsonNanHandler:
    """Tests for json_nan_handler()."""

    def test_converts_nan_to_none(self) -> None:
        """Converts float NaN to None."""
        assert json_nan_handler(math.nan) is None

    def test_converts_inf_to_none(self) -> None:
        """Converts positive infinity to None."""
        assert json_nan_handler(math.inf) is None

    def test_converts_neg_inf_to_none(self) -> None:
        """Converts negative infinity to None."""
        assert json_nan_handler(-math.inf) is None

    def test_passes_through_normal_float(self) -> None:
        """Returns normal float values unchanged."""
        assert json_nan_handler(3.14) == 3.14

    def test_passes_through_zero(self) -> None:
        """Returns 0.0 unchanged."""
        assert json_nan_handler(0.0) == 0.0

    def test_passes_through_non_float(self) -> None:
        """Returns non-float objects unchanged."""
        obj = {"key": "value"}
        assert json_nan_handler(obj) is obj

    def test_passes_through_string(self) -> None:
        """Returns strings unchanged."""
        assert json_nan_handler("hello") == "hello"

    def test_passes_through_none(self) -> None:
        """Returns None input unchanged."""
        assert json_nan_handler(None) is None


class TestComputeNormalityTests:
    """Tests for _compute_normality_tests()."""

    def test_skips_tier_with_fewer_than_three_rows(self) -> None:
        """Skips tiers with less than 3 data points."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1", "m1"],
                "tier": ["T0", "T0"],
                "score": [0.5, 0.6],
            }
        )
        result = _compute_normality_tests(runs_df, ["m1"], ["T0"])
        assert result == []

    def test_returns_empty_list_for_empty_dataframe(self) -> None:
        """Returns empty list when dataframe has no rows."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(columns=["agent_model", "tier", "score"])
        result = _compute_normality_tests(runs_df, ["m1"], ["T0"])
        assert result == []

    def test_calls_shapiro_wilk_for_valid_data(self) -> None:
        """Calls shapiro_wilk for each metric with >= 3 data points."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.95, 0.4)) as mock_sw:
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        assert mock_sw.called
        assert len(result) > 0
        assert result[0]["model"] == "m1"
        assert result[0]["tier"] == "T0"
