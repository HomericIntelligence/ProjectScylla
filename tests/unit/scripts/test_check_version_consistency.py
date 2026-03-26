"""Tests for version consistency across declaration sites."""

from __future__ import annotations

from pathlib import Path

import pytest

from scylla import __version__

# Repository root — three levels up from tests/unit/scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _read_toml_version(path: Path, table_key: str) -> str | None:
    """Read version from a TOML file without a TOML library."""
    import re

    text = path.read_text()
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_table = stripped == f"[{table_key}]"
            continue
        if in_table:
            match = re.match(r'^version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    return None


class TestVersionConsistency:
    """Verify that all version declaration sites agree."""

    def test_pyproject_matches_init(self) -> None:
        """pyproject.toml version matches scylla.__version__."""
        pyproject_version = _read_toml_version(REPO_ROOT / "pyproject.toml", "project")
        assert pyproject_version == __version__

    def test_pixi_matches_init(self) -> None:
        """pixi.toml version matches scylla.__version__."""
        pixi_version = _read_toml_version(REPO_ROOT / "pixi.toml", "workspace")
        assert pixi_version == __version__

    def test_all_three_agree(self) -> None:
        """All three version sources report the same value."""
        pyproject = _read_toml_version(REPO_ROOT / "pyproject.toml", "project")
        pixi = _read_toml_version(REPO_ROOT / "pixi.toml", "workspace")
        assert pyproject == pixi == __version__


class TestCheckVersionConsistencyScript:
    """Tests for the scripts/check_version_consistency.py module."""

    def test_consistent_versions(self, tmp_path: Path) -> None:
        """Script returns 0 when all versions match."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
        (tmp_path / "pixi.toml").write_text('[workspace]\nversion = "1.2.3"\n')
        init_dir = tmp_path / "scylla"
        init_dir.mkdir()
        (init_dir / "__init__.py").write_text('__version__ = "1.2.3"\n')

        from check_version_consistency import check_version_consistency

        assert check_version_consistency(tmp_path) == 0

    def test_inconsistent_versions(self, tmp_path: Path) -> None:
        """Script returns 1 when versions differ."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
        (tmp_path / "pixi.toml").write_text('[workspace]\nversion = "9.9.9"\n')
        init_dir = tmp_path / "scylla"
        init_dir.mkdir()
        (init_dir / "__init__.py").write_text('__version__ = "1.2.3"\n')

        from check_version_consistency import check_version_consistency

        assert check_version_consistency(tmp_path) == 1

    def test_missing_file(self, tmp_path: Path) -> None:
        """Script returns 1 when a version source file is missing."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        # pixi.toml and scylla/__init__.py are missing

        from check_version_consistency import check_version_consistency

        assert check_version_consistency(tmp_path) == 1

    @pytest.mark.parametrize(
        "pyproject_ver,pixi_ver,init_ver",
        [
            ("0.1.0", "0.1.0", "0.2.0"),
            ("0.1.0", "0.2.0", "0.1.0"),
            ("0.2.0", "0.1.0", "0.1.0"),
        ],
    )
    def test_single_mismatch_detected(
        self,
        tmp_path: Path,
        pyproject_ver: str,
        pixi_ver: str,
        init_ver: str,
    ) -> None:
        """Script detects when exactly one source disagrees."""
        (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{pyproject_ver}"\n')
        (tmp_path / "pixi.toml").write_text(f'[workspace]\nversion = "{pixi_ver}"\n')
        init_dir = tmp_path / "scylla"
        init_dir.mkdir()
        (init_dir / "__init__.py").write_text(f'__version__ = "{init_ver}"\n')

        from check_version_consistency import check_version_consistency

        assert check_version_consistency(tmp_path) == 1
