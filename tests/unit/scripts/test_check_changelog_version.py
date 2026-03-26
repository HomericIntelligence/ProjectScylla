"""Tests for scripts/check_changelog_version.py."""

import sys
import textwrap
from pathlib import Path

import pytest

from scripts.check_changelog_version import (
    changelog_has_version,
    extract_version_from_pyproject,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_pyproject(tmp_path: Path, content: str) -> Path:
    """Write a pyproject.toml to *tmp_path* and return its path."""
    path = tmp_path / "pyproject.toml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def write_changelog(tmp_path: Path, content: str) -> Path:
    """Write a CHANGELOG.md to *tmp_path* and return its path."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


PYPROJECT_VERSION_010 = """\
    [project]
    name = "scylla"
    version = "0.1.0"
"""

PYPROJECT_VERSION_200 = """\
    [project]
    name = "scylla"
    version = "2.0.0"
"""

PYPROJECT_NO_VERSION = """\
    [project]
    name = "scylla"
"""

CHANGELOG_WITH_010 = """\
    # Changelog

    ## [Unreleased]

    ## [0.1.0] - 2026-03-25

    ### Added
    - Initial release
"""

CHANGELOG_BARE_010 = """\
    # Changelog

    ## 0.1.0

    ### Added
    - Initial release
"""

CHANGELOG_NO_MATCH = """\
    # Changelog

    ## [Unreleased]

    ## [0.2.0] - 2026-04-01

    ### Added
    - Something else
"""

CHANGELOG_EMPTY = ""


# ---------------------------------------------------------------------------
# extract_version_from_pyproject
# ---------------------------------------------------------------------------


class TestExtractVersionFromPyproject:
    """Tests for extract_version_from_pyproject()."""

    def test_reads_version(self, tmp_path: Path) -> None:
        """Should return the version string."""
        write_pyproject(tmp_path, PYPROJECT_VERSION_010)
        assert extract_version_from_pyproject(tmp_path) == "0.1.0"

    def test_reads_different_version(self, tmp_path: Path) -> None:
        """Should return a different version string."""
        write_pyproject(tmp_path, PYPROJECT_VERSION_200)
        assert extract_version_from_pyproject(tmp_path) == "2.0.0"

    def test_missing_file_exits(self, tmp_path: Path) -> None:
        """Should exit 1 when pyproject.toml is absent."""
        with pytest.raises(SystemExit):
            extract_version_from_pyproject(tmp_path)

    def test_missing_key_exits(self, tmp_path: Path) -> None:
        """Should exit 1 when [project].version is missing."""
        write_pyproject(tmp_path, PYPROJECT_NO_VERSION)
        with pytest.raises(SystemExit):
            extract_version_from_pyproject(tmp_path)


# ---------------------------------------------------------------------------
# changelog_has_version
# ---------------------------------------------------------------------------


class TestChangelogHasVersion:
    """Tests for changelog_has_version()."""

    def test_bracketed_version_found(self, tmp_path: Path) -> None:
        """Should return True for '## [0.1.0]' format."""
        write_changelog(tmp_path, CHANGELOG_WITH_010)
        assert changelog_has_version(tmp_path, "0.1.0") is True

    def test_bare_version_found(self, tmp_path: Path) -> None:
        """Should return True for '## 0.1.0' format (no brackets)."""
        write_changelog(tmp_path, CHANGELOG_BARE_010)
        assert changelog_has_version(tmp_path, "0.1.0") is True

    def test_version_not_found(self, tmp_path: Path) -> None:
        """Should return False when the version is not present."""
        write_changelog(tmp_path, CHANGELOG_NO_MATCH)
        assert changelog_has_version(tmp_path, "0.1.0") is False

    def test_empty_changelog(self, tmp_path: Path) -> None:
        """Should return False for an empty CHANGELOG.md."""
        write_changelog(tmp_path, CHANGELOG_EMPTY)
        assert changelog_has_version(tmp_path, "0.1.0") is False

    def test_missing_changelog_exits(self, tmp_path: Path) -> None:
        """Should exit 1 when CHANGELOG.md is absent."""
        with pytest.raises(SystemExit):
            changelog_has_version(tmp_path, "0.1.0")

    def test_no_partial_match(self, tmp_path: Path) -> None:
        """Should not match '0.1.0' inside '0.1.0-beta' or '10.1.0'."""
        write_changelog(tmp_path, "## [0.1.0-beta]\n## [10.1.0]\n")
        assert changelog_has_version(tmp_path, "0.1.0") is False


# ---------------------------------------------------------------------------
# main (integration via sys.argv)
# ---------------------------------------------------------------------------


class TestMain:
    """Integration tests for main()."""

    def test_happy_path_returns_zero(self, tmp_path: Path) -> None:
        """Should return 0 when CHANGELOG has a matching entry."""
        write_pyproject(tmp_path, PYPROJECT_VERSION_010)
        write_changelog(tmp_path, CHANGELOG_WITH_010)
        sys.argv = ["check_changelog_version.py", "--repo-root", str(tmp_path)]
        assert main() == 0

    def test_missing_entry_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when CHANGELOG lacks the version."""
        write_pyproject(tmp_path, PYPROJECT_VERSION_010)
        write_changelog(tmp_path, CHANGELOG_NO_MATCH)
        sys.argv = ["check_changelog_version.py", "--repo-root", str(tmp_path)]
        assert main() == 1

    def test_verbose_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print PASS message with --verbose."""
        write_pyproject(tmp_path, PYPROJECT_VERSION_010)
        write_changelog(tmp_path, CHANGELOG_WITH_010)
        sys.argv = [
            "check_changelog_version.py",
            "--repo-root",
            str(tmp_path),
            "--verbose",
        ]
        assert main() == 0
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "0.1.0" in captured.out

    def test_repo_root_argument(self, tmp_path: Path) -> None:
        """Should respect --repo-root for finding files."""
        subdir = tmp_path / "nested"
        subdir.mkdir()
        write_pyproject(subdir, PYPROJECT_VERSION_010)
        write_changelog(subdir, CHANGELOG_WITH_010)
        sys.argv = ["check_changelog_version.py", "--repo-root", str(subdir)]
        assert main() == 0
