"""Tests for scripts/check_package_version_consistency.py."""

import textwrap
from pathlib import Path

import pytest

from scripts.check_package_version_consistency import (
    check_init_uses_importlib,
    check_package_version_consistency,
    find_aspirational_versions,
    get_pixi_version,
    get_pyproject_version,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_pyproject(directory: Path, version: str = "0.1.0") -> Path:
    """Write a minimal pyproject.toml with the given version."""
    content = textwrap.dedent(f"""\
        [project]
        name = "scylla"
        version = "{version}"
    """)
    path = directory / "pyproject.toml"
    path.write_text(content)
    return path


def write_pixi(directory: Path, version: str = "0.1.0") -> Path:
    """Write a minimal pixi.toml with the given version."""
    content = textwrap.dedent(f"""\
        [workspace]
        name = "scylla"
        version = "{version}"
    """)
    path = directory / "pixi.toml"
    path.write_text(content)
    return path


def write_init_importlib(directory: Path) -> Path:
    """Write an __init__.py that uses importlib.metadata."""
    init_dir = directory / "scylla"
    init_dir.mkdir(exist_ok=True)
    path = init_dir / "__init__.py"
    path.write_text(
        textwrap.dedent("""\
        from importlib.metadata import version as _get_version
        __version__ = _get_version("scylla")
    """)
    )
    return path


def write_init_hardcoded(directory: Path, version: str = "0.1.0") -> Path:
    """Write an __init__.py with a hardcoded __version__."""
    init_dir = directory / "scylla"
    init_dir.mkdir(exist_ok=True)
    path = init_dir / "__init__.py"
    path.write_text(f'__version__ = "{version}"\n')
    return path


def write_changelog(directory: Path, content: str) -> Path:
    """Write a CHANGELOG.md with the given content."""
    path = directory / "CHANGELOG.md"
    path.write_text(content)
    return path


def setup_consistent_repo(root: Path, version: str = "0.1.0") -> None:
    """Set up a minimal repo with all version sources consistent."""
    write_pyproject(root, version)
    write_pixi(root, version)
    write_init_importlib(root)
    write_changelog(
        root,
        "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- Something new\n",
    )


# ---------------------------------------------------------------------------
# TestGetPyprojectVersion
# ---------------------------------------------------------------------------


class TestGetPyprojectVersion:
    """Tests for get_pyproject_version()."""

    def test_reads_version(self, tmp_path: Path) -> None:
        """Should return the version from [project].version."""
        write_pyproject(tmp_path, "1.2.3")
        assert get_pyproject_version(tmp_path / "pyproject.toml") == "1.2.3"

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pyproject.toml does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            get_pyproject_version(tmp_path / "pyproject.toml")
        assert exc_info.value.code == 1

    def test_no_version_field_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if [project].version is missing."""
        path = tmp_path / "pyproject.toml"
        path.write_text("[project]\nname = 'scylla'\n")
        with pytest.raises(SystemExit) as exc_info:
            get_pyproject_version(path)
        assert exc_info.value.code == 1

    def test_malformed_toml_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) on malformed TOML."""
        path = tmp_path / "pyproject.toml"
        path.write_text("this is not [valid toml\n")
        with pytest.raises(SystemExit) as exc_info:
            get_pyproject_version(path)
        assert exc_info.value.code == 1

    def test_no_project_section_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if [project] section is missing."""
        path = tmp_path / "pyproject.toml"
        path.write_text("[build-system]\nrequires = ['setuptools']\n")
        with pytest.raises(SystemExit) as exc_info:
            get_pyproject_version(path)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# TestGetPixiVersion
# ---------------------------------------------------------------------------


class TestGetPixiVersion:
    """Tests for get_pixi_version()."""

    def test_reads_version(self, tmp_path: Path) -> None:
        """Should return the version from [workspace].version."""
        write_pixi(tmp_path, "0.1.0")
        assert get_pixi_version(tmp_path / "pixi.toml") == "0.1.0"

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pixi.toml does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            get_pixi_version(tmp_path / "pixi.toml")
        assert exc_info.value.code == 1

    def test_no_version_field_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if [workspace].version is missing."""
        path = tmp_path / "pixi.toml"
        path.write_text("[workspace]\nname = 'scylla'\n")
        with pytest.raises(SystemExit) as exc_info:
            get_pixi_version(path)
        assert exc_info.value.code == 1

    def test_malformed_toml_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) on malformed TOML."""
        path = tmp_path / "pixi.toml"
        path.write_text("not valid [toml\n")
        with pytest.raises(SystemExit) as exc_info:
            get_pixi_version(path)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# TestCheckInitUsesImportlib
# ---------------------------------------------------------------------------


class TestCheckInitUsesImportlib:
    """Tests for check_init_uses_importlib()."""

    def test_importlib_pattern_passes(self, tmp_path: Path) -> None:
        """Should return True when __init__.py uses importlib.metadata."""
        path = write_init_importlib(tmp_path)
        assert check_init_uses_importlib(path) is True

    def test_hardcoded_version_fails(self, tmp_path: Path) -> None:
        """Should return False when __init__.py has a hardcoded version string."""
        path = write_init_hardcoded(tmp_path)
        assert check_init_uses_importlib(path) is False

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if __init__.py does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            check_init_uses_importlib(tmp_path / "scylla" / "__init__.py")
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# TestFindAspirationalVersions
# ---------------------------------------------------------------------------


class TestFindAspirationalVersions:
    """Tests for find_aspirational_versions()."""

    def test_no_aspirational_versions(self, tmp_path: Path) -> None:
        """Should return empty list when no version refs exceed canonical."""
        write_changelog(tmp_path, "# Changelog\n\n## [Unreleased]\n\n- Some change\n")
        assert find_aspirational_versions(tmp_path / "CHANGELOG.md", "0.1.0") == []

    def test_finds_aspirational_versions(self, tmp_path: Path) -> None:
        """Should find version references higher than canonical."""
        write_changelog(
            tmp_path,
            "# Changelog\n\nDeprecated as of v1.5.0. Removed in v2.0.0.\n",
        )
        result = find_aspirational_versions(tmp_path / "CHANGELOG.md", "0.1.0")
        assert "v1.5.0" in result
        assert "v2.0.0" in result

    def test_ignores_versions_at_or_below_canonical(self, tmp_path: Path) -> None:
        """Should ignore version refs that are <= canonical version."""
        write_changelog(
            tmp_path,
            "# Changelog\n\nReleased in v0.1.0. Also v0.0.1.\n",
        )
        assert find_aspirational_versions(tmp_path / "CHANGELOG.md", "0.1.0") == []

    def test_missing_changelog_returns_empty(self, tmp_path: Path) -> None:
        """Should return empty list when CHANGELOG.md does not exist."""
        assert find_aspirational_versions(tmp_path / "CHANGELOG.md", "0.1.0") == []

    def test_deduplicates_references(self, tmp_path: Path) -> None:
        """Should not return duplicate version references."""
        write_changelog(
            tmp_path,
            "Deprecated v1.5.0. Also deprecated v1.5.0. Removed v2.0.0.\n",
        )
        result = find_aspirational_versions(tmp_path / "CHANGELOG.md", "0.1.0")
        assert result.count("v1.5.0") == 1
        assert result.count("v2.0.0") == 1

    def test_higher_canonical_excludes_lower_refs(self, tmp_path: Path) -> None:
        """When canonical is 2.0.0, v1.5.0 should not be flagged."""
        write_changelog(
            tmp_path,
            "# Changelog\n\nDeprecated as of v1.5.0.\n",
        )
        assert find_aspirational_versions(tmp_path / "CHANGELOG.md", "2.0.0") == []

    def test_ignores_versions_in_urls(self, tmp_path: Path) -> None:
        """Should not flag version references that appear inside URLs."""
        write_changelog(
            tmp_path,
            (
                "# Changelog\n\n"
                "Format follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n"
            ),
        )
        assert find_aspirational_versions(tmp_path / "CHANGELOG.md", "0.1.0") == []


# ---------------------------------------------------------------------------
# TestCheckPackageVersionConsistency
# ---------------------------------------------------------------------------


class TestCheckPackageVersionConsistency:
    """Tests for check_package_version_consistency()."""

    def test_all_consistent_returns_zero(self, tmp_path: Path) -> None:
        """Should return 0 when all version sources are consistent."""
        setup_consistent_repo(tmp_path)
        assert check_package_version_consistency(tmp_path) == 0

    def test_pixi_mismatch_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when pixi.toml version differs from pyproject.toml."""
        setup_consistent_repo(tmp_path)
        write_pixi(tmp_path, "0.2.0")
        assert check_package_version_consistency(tmp_path) == 1

    def test_hardcoded_init_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when __init__.py has a hardcoded version."""
        setup_consistent_repo(tmp_path)
        write_init_hardcoded(tmp_path)
        assert check_package_version_consistency(tmp_path) == 1

    def test_aspirational_changelog_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when CHANGELOG.md has aspirational version refs."""
        setup_consistent_repo(tmp_path)
        write_changelog(
            tmp_path,
            "# Changelog\n\nDeprecated as of v1.5.0. Removed in v2.0.0.\n",
        )
        assert check_package_version_consistency(tmp_path) == 1

    def test_verbose_prints_ok_on_success(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With verbose=True, should print OK messages when consistent."""
        setup_consistent_repo(tmp_path)
        result = check_package_version_consistency(tmp_path, verbose=True)
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_mismatch_prints_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should print descriptive error to stderr on mismatch."""
        setup_consistent_repo(tmp_path)
        write_pixi(tmp_path, "0.2.0")
        check_package_version_consistency(tmp_path)
        captured = capsys.readouterr()
        assert "0.2.0" in captured.err
        assert "0.1.0" in captured.err

    def test_multiple_errors_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should report all errors, not just the first one."""
        setup_consistent_repo(tmp_path)
        write_pixi(tmp_path, "0.2.0")
        write_init_hardcoded(tmp_path)
        write_changelog(
            tmp_path,
            "# Changelog\n\nDeprecated as of v1.5.0.\n",
        )
        result = check_package_version_consistency(tmp_path)
        assert result == 1
        captured = capsys.readouterr()
        # All three errors should be present
        assert "pixi.toml" in captured.err
        assert "hardcoded" in captured.err
        assert "v1.5.0" in captured.err

    def test_missing_changelog_not_an_error(self, tmp_path: Path) -> None:
        """Should pass when CHANGELOG.md does not exist (it's optional)."""
        write_pyproject(tmp_path)
        write_pixi(tmp_path)
        write_init_importlib(tmp_path)
        # No CHANGELOG.md written
        assert check_package_version_consistency(tmp_path) == 0
