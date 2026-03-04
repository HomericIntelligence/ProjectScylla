"""Tests for scripts/implement_issues.py."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from implement_issues import parse_args, setup_logging


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_sets_debug_level_when_verbose(self) -> None:
        """Configures DEBUG level when verbose=True."""
        with patch("implement_issues.logging.basicConfig") as mock_config:
            setup_logging(verbose=True)

        mock_config.assert_called_once()
        call_kwargs = mock_config.call_args[1]
        assert call_kwargs["level"] == logging.DEBUG

    def test_sets_info_level_by_default(self) -> None:
        """Configures INFO level when verbose=False."""
        with patch("implement_issues.logging.basicConfig") as mock_config:
            setup_logging(verbose=False)

        mock_config.assert_called_once()
        call_kwargs = mock_config.call_args[1]
        assert call_kwargs["level"] == logging.INFO

    def test_creates_log_file_when_log_dir_given(self, tmp_path: Path) -> None:
        """Creates a FileHandler when log_dir is specified."""
        log_dir = tmp_path / "logs"

        with patch("implement_issues.logging.basicConfig"):
            with patch("implement_issues.logging.FileHandler"):
                with patch("implement_issues.logging.getLogger"):
                    setup_logging(log_dir=log_dir)

        assert log_dir.exists()

    def test_no_file_handler_without_log_dir(self) -> None:
        """Does not create a FileHandler when log_dir is None."""
        with patch("implement_issues.logging.basicConfig"):
            with patch("implement_issues.logging.FileHandler") as mock_fh:
                setup_logging(log_dir=None)

        mock_fh.assert_not_called()


class TestParseArgs:
    """Tests for parse_args()."""

    def test_parses_epic_number(self) -> None:
        """Parses --epic argument as an integer."""
        with patch("sys.argv", ["implement_issues.py", "--epic", "123"]):
            args = parse_args()

        assert args.epic == 123

    def test_parses_issues_list(self) -> None:
        """Parses multiple --issues as a list of ints."""
        with patch("sys.argv", ["implement_issues.py", "--issues", "595", "596", "597"]):
            args = parse_args()

        assert args.issues == [595, 596, 597]

    def test_dry_run_defaults_false(self) -> None:
        """dry_run is False when --dry-run is not passed."""
        with patch("sys.argv", ["implement_issues.py", "--issues", "1"]):
            args = parse_args()

        assert args.dry_run is False

    def test_dry_run_set_true(self) -> None:
        """dry_run is True when --dry-run is passed."""
        with patch("sys.argv", ["implement_issues.py", "--issues", "1", "--dry-run"]):
            args = parse_args()

        assert args.dry_run is True

    def test_max_workers_default(self) -> None:
        """max_workers defaults to 3."""
        with patch("sys.argv", ["implement_issues.py", "--issues", "1"]):
            args = parse_args()

        assert args.max_workers == 3

    def test_analyze_flag(self) -> None:
        """--analyze flag is captured."""
        with patch("sys.argv", ["implement_issues.py", "--epic", "1", "--analyze"]):
            args = parse_args()

        assert args.analyze is True

    def test_health_check_flag(self) -> None:
        """--health-check flag is captured."""
        with patch("sys.argv", ["implement_issues.py", "--health-check"]):
            args = parse_args()

        assert args.health_check is True
