"""Tests for scripts/generate_tables.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMain:
    """Tests for main() table generation logic."""

    def _make_mock_experiments(self) -> list[MagicMock]:
        """Return a non-empty list of mock experiments."""
        return [MagicMock()]

    def test_exits_early_when_no_experiments_found(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Prints error and returns when no experiments are found."""
        with (
            patch("generate_tables.load_all_experiments", return_value=[]),
            patch("generate_tables.load_rubric_weights", return_value={}),
            patch("sys.argv", ["generate_tables.py", "--data-dir", "/tmp/nonexistent"]),
        ):
            from generate_tables import main

            main()

        captured = capsys.readouterr()
        assert "ERROR" in captured.out

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        """Creates the output directory before writing tables."""
        output_dir = tmp_path / "tables"
        experiments = self._make_mock_experiments()

        mock_df = MagicMock()
        mock_df.__len__ = lambda self: 5

        with (
            patch("generate_tables.load_all_experiments", return_value=experiments),
            patch("generate_tables.load_rubric_weights", return_value={}),
            patch("generate_tables.build_runs_df", return_value=mock_df),
            patch("generate_tables.build_judges_df", return_value=mock_df),
            patch("generate_tables.build_criteria_df", return_value=mock_df),
            patch("generate_tables.build_subtests_df", return_value=mock_df),
            patch("generate_tables.table01_tier_summary", return_value=("md", "tex")),
            patch("generate_tables.table02_tier_comparison", return_value=("md", "tex")),
            patch("generate_tables.table02b_impl_rate_comparison", return_value=("md", "tex")),
            patch("generate_tables.table03_judge_agreement", return_value=("md", "tex")),
            patch("generate_tables.table04_criteria_performance", return_value=("md", "tex")),
            patch("generate_tables.table05_cost_analysis", return_value=("md", "tex")),
            patch("generate_tables.table06_model_comparison", return_value=("md", "tex")),
            patch("generate_tables.table07_subtest_detail", return_value=("md", "tex")),
            patch("generate_tables.table08_summary_statistics", return_value=("md", "tex")),
            patch("generate_tables.table09_experiment_config", return_value=("md", "tex")),
            patch("generate_tables.table10_normality_tests", return_value=("md", "tex")),
            patch("generate_tables.table11_experiment_overview", return_value=("md", "tex")),
            patch(
                "sys.argv",
                ["generate_tables.py", "--output-dir", str(output_dir)],
            ),
        ):
            from generate_tables import main

            main()

        assert output_dir.exists()

    def test_writes_md_and_tex_files(self, tmp_path: Path) -> None:
        """Writes .md and .tex files for each table."""
        output_dir = tmp_path / "tables"
        experiments = self._make_mock_experiments()

        mock_df = MagicMock()
        mock_df.__len__ = lambda self: 5

        with (
            patch("generate_tables.load_all_experiments", return_value=experiments),
            patch("generate_tables.load_rubric_weights", return_value={}),
            patch("generate_tables.build_runs_df", return_value=mock_df),
            patch("generate_tables.build_judges_df", return_value=mock_df),
            patch("generate_tables.build_criteria_df", return_value=mock_df),
            patch("generate_tables.build_subtests_df", return_value=mock_df),
            patch("generate_tables.table01_tier_summary", return_value=("# T1 md", "t1 tex")),
            patch("generate_tables.table02_tier_comparison", return_value=("md", "tex")),
            patch("generate_tables.table02b_impl_rate_comparison", return_value=("md", "tex")),
            patch("generate_tables.table03_judge_agreement", return_value=("md", "tex")),
            patch("generate_tables.table04_criteria_performance", return_value=("md", "tex")),
            patch("generate_tables.table05_cost_analysis", return_value=("md", "tex")),
            patch("generate_tables.table06_model_comparison", return_value=("md", "tex")),
            patch("generate_tables.table07_subtest_detail", return_value=("md", "tex")),
            patch("generate_tables.table08_summary_statistics", return_value=("md", "tex")),
            patch("generate_tables.table09_experiment_config", return_value=("md", "tex")),
            patch("generate_tables.table10_normality_tests", return_value=("md", "tex")),
            patch("generate_tables.table11_experiment_overview", return_value=("md", "tex")),
            patch(
                "sys.argv",
                ["generate_tables.py", "--output-dir", str(output_dir)],
            ),
        ):
            from generate_tables import main

            main()

        assert (output_dir / "tab01_tier_summary.md").exists()
        assert (output_dir / "tab01_tier_summary.tex").exists()
