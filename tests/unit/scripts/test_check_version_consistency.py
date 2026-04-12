"""Tests for scripts/check_version_consistency.py."""

import textwrap
from pathlib import Path

import pytest

from scripts.check_version_consistency import (
    check_version_consistency,
    get_pixi_version,
    get_pyproject_version,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_pyproject(directory: Path, version: str) -> Path:
    """Write a minimal pyproject.toml with the given version."""
    content = textwrap.dedent(f"""\
        [project]
        name = "test-project"
        version = "{version}"
    """)
    path = directory / "pyproject.toml"
    path.write_text(content)
    return path


def write_pixi_toml(directory: Path, version: str) -> Path:
    """Write a minimal pixi.toml with the given version."""
    content = textwrap.dedent(f"""\
        [workspace]
        name = "test-project"
        version = "{version}"
        channels = ["conda-forge"]
    """)
    path = directory / "pixi.toml"
    path.write_text(content)
    return path


def setup_repo(root: Path, version: str) -> None:
    """Create both pyproject.toml and pixi.toml with matching version."""
    write_pyproject(root, version)
    write_pixi_toml(root, version)


# ---------------------------------------------------------------------------
# TestGetPyprojectVersion
# ---------------------------------------------------------------------------


class TestGetPyprojectVersion:
    """Tests for get_pyproject_version()."""

    def test_valid_version(self, tmp_path: Path) -> None:
        """Should return the version string from pyproject.toml."""
        write_pyproject(tmp_path, "1.2.3")
        assert get_pyproject_version(tmp_path) == "1.2.3"

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pyproject.toml does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            get_pyproject_version(tmp_path)
        assert exc_info.value.code == 1

    def test_malformed_toml_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) on malformed TOML."""
        path = tmp_path / "pyproject.toml"
        path.write_text("this is not [valid toml\n")
        with pytest.raises(SystemExit) as exc_info:
            get_pyproject_version(tmp_path)
        assert exc_info.value.code == 1

    def test_no_project_section_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if [project] section is missing."""
        path = tmp_path / "pyproject.toml"
        path.write_text("[build-system]\nrequires = ['setuptools']\n")
        with pytest.raises(SystemExit) as exc_info:
            get_pyproject_version(tmp_path)
        assert exc_info.value.code == 1

    def test_no_version_field_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if version field is missing from [project]."""
        path = tmp_path / "pyproject.toml"
        path.write_text('[project]\nname = "test"\n')
        with pytest.raises(SystemExit) as exc_info:
            get_pyproject_version(tmp_path)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# TestGetPixiVersion
# ---------------------------------------------------------------------------


class TestGetPixiVersion:
    """Tests for get_pixi_version()."""

    def test_valid_version(self, tmp_path: Path) -> None:
        """Should return the version string from pixi.toml."""
        write_pixi_toml(tmp_path, "0.5.1")
        assert get_pixi_version(tmp_path) == "0.5.1"

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pixi.toml does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            get_pixi_version(tmp_path)
        assert exc_info.value.code == 1

    def test_no_version_line_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if no version line is found."""
        path = tmp_path / "pixi.toml"
        path.write_text("[workspace]\nname = 'test'\n")
        with pytest.raises(SystemExit) as exc_info:
            get_pixi_version(tmp_path)
        assert exc_info.value.code == 1

    def test_version_with_spaces(self, tmp_path: Path) -> None:
        """Should handle version lines with extra spaces."""
        path = tmp_path / "pixi.toml"
        path.write_text('[workspace]\nversion  =  "2.0.0"\n')
        assert get_pixi_version(tmp_path) == "2.0.0"

    def test_ignores_dependency_version_outside_workspace(self, tmp_path: Path) -> None:
        """Should not pick up a version field that appears outside [workspace]."""
        content = textwrap.dedent("""\
            [workspace]
            name = "test-project"
            version = "1.2.3"

            [dependencies]
            some-dep = "9.9.9"
            another = { version = "8.8.8" }
        """)
        path = tmp_path / "pixi.toml"
        path.write_text(content)
        assert get_pixi_version(tmp_path) == "1.2.3"

    def test_version_field_before_workspace_not_matched(self, tmp_path: Path) -> None:
        """Should not match a version = line that appears before [workspace]."""
        content = textwrap.dedent("""\
            [other]
            version = "0.0.1"

            [workspace]
            name = "test-project"
            version = "1.0.0"
        """)
        path = tmp_path / "pixi.toml"
        path.write_text(content)
        assert get_pixi_version(tmp_path) == "1.0.0"


# ---------------------------------------------------------------------------
# TestCheckVersionConsistency
# ---------------------------------------------------------------------------


class TestCheckVersionConsistency:
    """Tests for check_version_consistency()."""

    def test_matching_versions_returns_zero(self, tmp_path: Path) -> None:
        """Should return 0 when versions match."""
        setup_repo(tmp_path, "0.1.0")
        assert check_version_consistency(tmp_path) == 0

    def test_mismatch_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when versions differ."""
        write_pyproject(tmp_path, "0.2.0")
        write_pixi_toml(tmp_path, "0.1.0")
        assert check_version_consistency(tmp_path) == 1

    def test_mismatch_prints_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should print descriptive error message to stderr on mismatch."""
        write_pyproject(tmp_path, "0.2.0")
        write_pixi_toml(tmp_path, "0.1.0")
        check_version_consistency(tmp_path)
        captured = capsys.readouterr()
        assert "0.2.0" in captured.err
        assert "0.1.0" in captured.err

    def test_verbose_prints_versions_on_match(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With verbose=True, should print parsed versions even when they match."""
        setup_repo(tmp_path, "1.0.0")
        result = check_version_consistency(tmp_path, verbose=True)
        assert result == 0
        captured = capsys.readouterr()
        assert "1.0.0" in captured.out

    def test_verbose_prints_ok_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With verbose=True on a match, should print OK message."""
        setup_repo(tmp_path, "1.0.0")
        check_version_consistency(tmp_path, verbose=True)
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_missing_pyproject_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pyproject.toml is missing."""
        write_pixi_toml(tmp_path, "0.1.0")
        with pytest.raises(SystemExit) as exc_info:
            check_version_consistency(tmp_path)
        assert exc_info.value.code == 1

    def test_missing_pixi_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pixi.toml is missing."""
        write_pyproject(tmp_path, "0.1.0")
        with pytest.raises(SystemExit) as exc_info:
            check_version_consistency(tmp_path)
        assert exc_info.value.code == 1
