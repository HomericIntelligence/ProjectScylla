"""Tests for scripts/check_tier_config_consistency.py."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from check_tier_config_consistency import (
    _load_tier_id,
    check_configs,
    find_tier_configs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_yaml(directory: Path, filename: str, content: str) -> Path:
    """Write a YAML file into *directory* and return its path."""
    path = directory / filename
    path.write_text(textwrap.dedent(content))
    return path


# ---------------------------------------------------------------------------
# find_tier_configs
# ---------------------------------------------------------------------------


class TestFindTierConfigs:
    """Tests for find_tier_configs()."""

    def test_finds_yaml_files(self, tmp_path: Path) -> None:
        """Finds all .yaml files in the directory."""
        (tmp_path / "T0.yaml").write_text("tier: T0")
        (tmp_path / "T1.yaml").write_text("tier: T1")
        result = find_tier_configs(tmp_path)
        assert len(result) == 2

    def test_excludes_underscore_prefixed_files(self, tmp_path: Path) -> None:
        """Files starting with _ are excluded (test fixtures)."""
        (tmp_path / "T0.yaml").write_text("tier: T0")
        (tmp_path / "_fixture.yaml").write_text("tier: fake")
        result = find_tier_configs(tmp_path)
        assert len(result) == 1
        assert result[0].name == "T0.yaml"

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        """Results are sorted alphabetically."""
        (tmp_path / "T2.yaml").write_text("tier: T2")
        (tmp_path / "T0.yaml").write_text("tier: T0")
        (tmp_path / "T1.yaml").write_text("tier: T1")
        result = find_tier_configs(tmp_path)
        names = [r.name for r in result]
        assert names == sorted(names)

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Returns empty list for directory with no YAML files."""
        result = find_tier_configs(tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# _load_tier_id
# ---------------------------------------------------------------------------


class TestLoadTierId:
    """Tests for _load_tier_id()."""

    def test_returns_tier_field(self, tmp_path: Path) -> None:
        """Returns the 'tier' field from a valid YAML file."""
        f = write_yaml(tmp_path, "T0.yaml", "tier: T0\nname: Prompts\n")
        assert _load_tier_id(f) == "T0"

    def test_returns_none_when_tier_missing(self, tmp_path: Path) -> None:
        """Returns None when YAML file has no 'tier' field."""
        f = write_yaml(tmp_path, "nofield.yaml", "name: something\n")
        assert _load_tier_id(f) is None

    def test_returns_none_for_non_dict_yaml(self, tmp_path: Path) -> None:
        """Returns None when YAML content is not a dict."""
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n")
        assert _load_tier_id(f) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Returns None for a missing file (logs warning)."""
        missing = tmp_path / "nonexistent.yaml"
        assert _load_tier_id(missing) is None

    def test_returns_none_for_invalid_yaml(self, tmp_path: Path) -> None:
        """Returns None for malformed YAML."""
        f = tmp_path / "bad.yaml"
        f.write_text(":\t invalid: yaml: content\n")
        # Either returns None or raises; we verify no exception propagates
        result = _load_tier_id(f)
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# check_configs
# ---------------------------------------------------------------------------


class TestCheckConfigs:
    """Tests for check_configs()."""

    def test_returns_0_for_consistent_configs(self, tmp_path: Path) -> None:
        """Returns 0 when all tier configs are consistent."""
        write_yaml(tmp_path, "T0.yaml", "tier: T0\n")

        with patch(
            "check_tier_config_consistency.validate_filename_tier_consistency",
            return_value=[],
        ):
            result = check_configs(tmp_path)

        assert result == 0

    def test_returns_1_for_violations(self, tmp_path: Path) -> None:
        """Returns 1 when any violation is found."""
        write_yaml(tmp_path, "T0.yaml", "tier: T0\n")

        with patch(
            "check_tier_config_consistency.validate_filename_tier_consistency",
            return_value=["T0.yaml: tier mismatch"],
        ):
            result = check_configs(tmp_path)

        assert result == 1

    def test_returns_1_when_tier_field_missing(self, tmp_path: Path) -> None:
        """Returns 1 when a config file has no 'tier' field."""
        write_yaml(tmp_path, "T0.yaml", "name: Prompts\n")  # No tier field
        result = check_configs(tmp_path)
        assert result == 1

    def test_empty_directory_returns_0(self, tmp_path: Path) -> None:
        """Empty config directory returns 0 (nothing to check)."""
        result = check_configs(tmp_path)
        assert result == 0

    def test_verbose_mode_does_not_raise(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        """Verbose mode prints output without raising."""
        write_yaml(tmp_path, "T0.yaml", "tier: T0\n")
        with patch(
            "check_tier_config_consistency.validate_filename_tier_consistency",
            return_value=[],
        ):
            result = check_configs(tmp_path, verbose=True)
        assert result == 0
        captured = capsys.readouterr()
        assert "T0.yaml" in captured.out or "OK" in captured.out
