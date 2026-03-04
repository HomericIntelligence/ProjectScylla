"""Tests for scripts/common.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from common import LABEL_COLORS, Colors, get_agents_dir


# ---------------------------------------------------------------------------
# LABEL_COLORS
# ---------------------------------------------------------------------------


class TestLabelColors:
    """Tests for LABEL_COLORS constant."""

    def test_is_dict(self) -> None:
        """LABEL_COLORS is a dictionary."""
        assert isinstance(LABEL_COLORS, dict)

    def test_contains_expected_keys(self) -> None:
        """LABEL_COLORS contains expected workflow labels."""
        expected = {"research", "evaluation", "metrics", "benchmark", "analysis", "documentation"}
        assert expected.issubset(set(LABEL_COLORS.keys()))

    def test_values_are_hex_strings(self) -> None:
        """All color values are hex strings (6 chars)."""
        for key, value in LABEL_COLORS.items():
            assert len(value) == 6, f"Color for '{key}' is not 6 chars: {value!r}"
            int(value, 16)  # Should not raise ValueError


# ---------------------------------------------------------------------------
# get_agents_dir
# ---------------------------------------------------------------------------


class TestGetAgentsDir:
    """Tests for get_agents_dir()."""

    def test_returns_agents_dir_when_exists(self, tmp_path: Path) -> None:
        """Returns the agents directory path when it exists."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        with patch("common.get_repo_root", return_value=tmp_path):
            result = get_agents_dir()

        assert result == agents_dir

    def test_raises_when_agents_dir_missing(self, tmp_path: Path) -> None:
        """Raises RuntimeError when agents directory does not exist."""
        with patch("common.get_repo_root", return_value=tmp_path):
            with pytest.raises(RuntimeError, match="Agents directory not found"):
                get_agents_dir()


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------


class TestColors:
    """Tests for Colors class."""

    def test_color_codes_are_ansi_strings(self) -> None:
        """Color code attributes are non-empty strings by default."""
        assert Colors.HEADER.startswith("\033[")
        assert Colors.OKGREEN.startswith("\033[")
        assert Colors.FAIL.startswith("\033[")

    def test_disable_clears_all_colors(self) -> None:
        """Colors.disable() sets all color codes to empty strings."""
        # Save originals
        original_header = Colors.HEADER
        original_okgreen = Colors.OKGREEN

        try:
            Colors.disable()
            assert Colors.HEADER == ""
            assert Colors.OKBLUE == ""
            assert Colors.OKCYAN == ""
            assert Colors.OKGREEN == ""
            assert Colors.WARNING == ""
            assert Colors.FAIL == ""
            assert Colors.ENDC == ""
            assert Colors.BOLD == ""
            assert Colors.UNDERLINE == ""
        finally:
            # Restore originals so other tests are not affected
            Colors.HEADER = original_header
            Colors.OKGREEN = original_okgreen
            Colors.OKBLUE = "\033[94m"
            Colors.OKCYAN = "\033[96m"
            Colors.WARNING = "\033[93m"
            Colors.FAIL = "\033[91m"
            Colors.ENDC = "\033[0m"
            Colors.BOLD = "\033[1m"
            Colors.UNDERLINE = "\033[4m"
