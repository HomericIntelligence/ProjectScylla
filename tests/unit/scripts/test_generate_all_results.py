"""Tests for scripts/generate_all_results.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from generate_all_results import run_script


class TestRunScript:
    """Tests for run_script()."""

    def test_returns_true_on_success(self) -> None:
        """Returns True when subprocess exits with code 0."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("generate_all_results.subprocess.run", return_value=mock_result):
            result = run_script("scripts/export_data.py", [], "Exporting data")

        assert result is True

    def test_returns_false_on_failure(self) -> None:
        """Returns False when subprocess exits with non-zero code."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("generate_all_results.subprocess.run", return_value=mock_result):
            result = run_script("scripts/export_data.py", [], "Exporting data")

        assert result is False

    def test_returns_false_on_exception(self) -> None:
        """Returns False when subprocess raises an exception."""
        with patch("generate_all_results.subprocess.run", side_effect=OSError("not found")):
            result = run_script("scripts/export_data.py", [], "Exporting data")

        assert result is False

    def test_passes_args_to_subprocess(self) -> None:
        """Forwards extra args to the subprocess command."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("generate_all_results.subprocess.run", return_value=mock_result) as mock_run:
            run_script("scripts/export_data.py", ["--data-dir", "/tmp"], "desc")

        call_cmd = mock_run.call_args[0][0]
        assert "--data-dir" in call_cmd
        assert "/tmp" in call_cmd

    def test_command_includes_pixi_run(self) -> None:
        """Command starts with 'pixi run python'."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("generate_all_results.subprocess.run", return_value=mock_result) as mock_run:
            run_script("scripts/export_data.py", [], "desc")

        call_cmd = mock_run.call_args[0][0]
        assert call_cmd[:3] == ["pixi", "run", "python"]


class TestMain:
    """Tests for main() orchestration logic."""

    def test_runs_all_three_steps_by_default(self) -> None:
        """Calls run_script three times when no skip flags are set."""
        with patch("generate_all_results.run_script", return_value=True) as mock_run:
            with patch("generate_all_results.terminal_guard"):
                from generate_all_results import main

                with patch(
                    "sys.argv",
                    ["generate_all_results.py"],
                ):
                    main()

        assert mock_run.call_count == 3

    def test_skips_figures_when_flag_set(self) -> None:
        """Skips figure generation step when --skip-figures is passed."""
        with patch("generate_all_results.run_script", return_value=True) as mock_run:
            with patch("generate_all_results.terminal_guard"):
                from generate_all_results import main

                with patch(
                    "sys.argv",
                    ["generate_all_results.py", "--skip-figures"],
                ):
                    main()

        # Should only run export_data and generate_tables (2 calls)
        assert mock_run.call_count == 2
