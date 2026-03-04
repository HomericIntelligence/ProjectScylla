"""Tests for scripts/plan_issues.py."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from plan_issues import parse_args, setup_logging


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_sets_debug_level_when_verbose(self) -> None:
        """Configures DEBUG level when verbose=True."""
        with patch("plan_issues.logging.basicConfig") as mock_config:
            setup_logging(verbose=True)

        mock_config.assert_called_once()
        assert mock_config.call_args[1]["level"] == logging.DEBUG

    def test_sets_info_level_by_default(self) -> None:
        """Configures INFO level when verbose=False."""
        with patch("plan_issues.logging.basicConfig") as mock_config:
            setup_logging(verbose=False)

        mock_config.assert_called_once()
        assert mock_config.call_args[1]["level"] == logging.INFO


class TestParseArgs:
    """Tests for parse_args()."""

    def test_parses_issues_list(self) -> None:
        """Parses --issues as a list of ints."""
        with patch("sys.argv", ["plan_issues.py", "--issues", "123", "456"]):
            args = parse_args()

        assert args.issues == [123, 456]

    def test_dry_run_defaults_false(self) -> None:
        """dry_run is False by default."""
        with patch("sys.argv", ["plan_issues.py", "--issues", "1"]):
            args = parse_args()

        assert args.dry_run is False

    def test_dry_run_set_true(self) -> None:
        """dry_run is True when --dry-run is passed."""
        with patch("sys.argv", ["plan_issues.py", "--issues", "1", "--dry-run"]):
            args = parse_args()

        assert args.dry_run is True

    def test_parallel_defaults_to_three(self) -> None:
        """Parallel defaults to 3."""
        with patch("sys.argv", ["plan_issues.py", "--issues", "1"]):
            args = parse_args()

        assert args.parallel == 3

    def test_force_defaults_false(self) -> None:
        """Force is False by default."""
        with patch("sys.argv", ["plan_issues.py", "--issues", "1"]):
            args = parse_args()

        assert args.force is False

    def test_system_prompt_path(self, tmp_path: Path) -> None:
        """Parses --system-prompt as a Path."""
        prompt_file = tmp_path / "prompt.md"
        with patch(
            "sys.argv", ["plan_issues.py", "--issues", "1", "--system-prompt", str(prompt_file)]
        ):
            args = parse_args()

        assert args.system_prompt == prompt_file


class TestMain:
    """Tests for main()."""

    def test_returns_one_on_planner_failure(self) -> None:
        """Returns 1 when planner reports failures."""
        mock_planner = MagicMock()
        mock_planner.run.return_value = {123: MagicMock(success=False)}

        with (
            patch("plan_issues.Planner", return_value=mock_planner),
            patch("sys.argv", ["plan_issues.py", "--issues", "123"]),
        ):
            from plan_issues import main

            result = main()

        assert result == 1

    def test_returns_zero_on_success(self) -> None:
        """Returns 0 when all issues are planned successfully."""
        mock_planner = MagicMock()
        mock_planner.run.return_value = {123: MagicMock(success=True)}

        with (
            patch("plan_issues.Planner", return_value=mock_planner),
            patch("sys.argv", ["plan_issues.py", "--issues", "123"]),
        ):
            from plan_issues import main

            result = main()

        assert result == 0

    def test_returns_130_on_keyboard_interrupt(self) -> None:
        """Returns 130 on KeyboardInterrupt."""
        mock_planner = MagicMock()
        mock_planner.run.side_effect = KeyboardInterrupt

        with (
            patch("plan_issues.Planner", return_value=mock_planner),
            patch("sys.argv", ["plan_issues.py", "--issues", "1"]),
        ):
            from plan_issues import main

            result = main()

        assert result == 130
