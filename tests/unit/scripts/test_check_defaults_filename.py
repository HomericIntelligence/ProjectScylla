"""Tests for scripts/check_defaults_filename.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from check_defaults_filename import main


class TestMain:
    """Tests for main()."""

    def test_returns_zero_when_validation_passes(self, tmp_path: Path) -> None:
        """Returns 0 when defaults file exists and validation passes."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        defaults_file = config_dir / "defaults.yaml"
        defaults_file.write_text("key: value\n")

        with (
            patch("check_defaults_filename._REPO_ROOT", tmp_path),
            patch("check_defaults_filename.validate_defaults_filename", return_value=[]),
        ):
            result = main()

        assert result == 0

    def test_returns_one_when_file_missing(self, tmp_path: Path) -> None:
        """Returns 1 when defaults config file does not exist."""
        with patch("check_defaults_filename._REPO_ROOT", tmp_path):
            # No defaults.yaml in tmp_path/config/
            result = main()

        assert result == 1

    def test_returns_one_when_validation_fails(self, tmp_path: Path) -> None:
        """Returns 1 when validate_defaults_filename returns warnings."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        defaults_file = config_dir / "defaults.yaml"
        defaults_file.write_text("key: value\n")

        with (
            patch("check_defaults_filename._REPO_ROOT", tmp_path),
            patch(
                "check_defaults_filename.validate_defaults_filename",
                return_value=["filename mismatch"],
            ),
        ):
            result = main()

        assert result == 1

    def test_prints_errors_when_validation_fails(self, tmp_path: Path, capsys: object) -> None:
        """Prints each warning to stderr when validation fails."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        defaults_file = config_dir / "defaults.yaml"
        defaults_file.write_text("key: value\n")

        with (
            patch("check_defaults_filename._REPO_ROOT", tmp_path),
            patch(
                "check_defaults_filename.validate_defaults_filename",
                return_value=["bad name"],
            ),
        ):
            main()
