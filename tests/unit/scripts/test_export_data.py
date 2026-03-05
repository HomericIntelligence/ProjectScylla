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

    def test_result_dict_contains_all_expected_columns(self) -> None:
        """Each result dict contains all seven expected column keys."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.92, 0.3)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        assert len(result) > 0
        expected_keys = {"model", "tier", "metric", "n", "w_statistic", "p_value", "is_normal"}
        assert set(result[0].keys()) == expected_keys

    def test_result_n_matches_data_length(self) -> None:
        """The 'n' field equals the number of non-null values for the metric."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.95, 0.4)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        score_entry = next(r for r in result if r["metric"] == "score")
        assert score_entry["n"] == 5

    def test_result_w_statistic_is_float(self) -> None:
        """The 'w_statistic' field is a float."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.92, 0.3)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        score_entry = next(r for r in result if r["metric"] == "score")
        assert isinstance(score_entry["w_statistic"], float)
        assert score_entry["w_statistic"] == 0.92

    def test_result_p_value_is_float(self) -> None:
        """The 'p_value' field is a float."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.95, 0.12)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        score_entry = next(r for r in result if r["metric"] == "score")
        assert isinstance(score_entry["p_value"], float)
        assert score_entry["p_value"] == 0.12

    def test_is_normal_true_when_p_value_above_threshold(self) -> None:
        """Sets is_normal=True when p_value > 0.05."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.98, 0.8)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        score_entry = next(r for r in result if r["metric"] == "score")
        assert score_entry["is_normal"] is True

    def test_is_normal_false_when_p_value_at_or_below_threshold(self) -> None:
        """Sets is_normal=False when p_value <= 0.05."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.70, 0.03)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        score_entry = next(r for r in result if r["metric"] == "score")
        assert score_entry["is_normal"] is False

    def test_skips_metric_column_not_present_in_dataframe(self) -> None:
        """Skips metric columns that do not exist in the DataFrame."""
        import pandas as pd
        from export_data import _compute_normality_tests

        # Only 'score' column present; impl_rate, cost_usd, etc. are absent
        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.95, 0.4)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        metrics_returned = {r["metric"] for r in result}
        assert metrics_returned == {"score"}

    def test_produces_one_entry_per_metric_per_model_and_tier(self) -> None:
        """Produces exactly one result dict per (model, tier, metric) combination."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
                "impl_rate": [0.2, 0.4, 0.6, 0.8, 1.0],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.95, 0.4)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        assert len(result) == 2
        metrics_returned = {r["metric"] for r in result}
        assert metrics_returned == {"score", "impl_rate"}

    def test_metric_field_matches_column_name(self) -> None:
        """The 'metric' field in each result matches the DataFrame column name."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "cost_usd": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.95, 0.4)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        assert len(result) == 1
        assert result[0]["metric"] == "cost_usd"

    def test_skips_metric_values_with_fewer_than_three_non_null(self) -> None:
        """Skips metric column when fewer than 3 non-null values remain after dropna."""
        import pandas as pd
        from export_data import _compute_normality_tests

        runs_df = pd.DataFrame(
            {
                "agent_model": ["m1"] * 5,
                "tier": ["T0"] * 5,
                "score": [0.1, 0.5, 0.9, 0.3, 0.7],
                "impl_rate": [None, None, None, 0.8, 1.0],
            }
        )
        with patch("export_data.shapiro_wilk", return_value=(0.95, 0.4)):
            result = _compute_normality_tests(runs_df, ["m1"], ["T0"])

        metrics_returned = {r["metric"] for r in result}
        assert "impl_rate" not in metrics_returned
        assert "score" in metrics_returned
