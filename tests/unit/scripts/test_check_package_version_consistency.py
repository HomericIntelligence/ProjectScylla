"""Tests for scripts/check_package_version_consistency.py."""

import textwrap
from pathlib import Path

import pytest

from scripts.check_package_version_consistency import (
    check_changelog,
    check_init_version,
    check_package_version_consistency,
    check_pixi_version,
    check_skill_files,
    find_aspirational_versions,
    get_canonical_version,
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


def write_init(directory: Path, version: str = "0.1.0") -> Path:
    """Write a minimal scylla/__init__.py with __version__."""
    scylla_dir = directory / "scylla"
    scylla_dir.mkdir(exist_ok=True)
    path = scylla_dir / "__init__.py"
    path.write_text(f'__version__ = "{version}"\n')
    return path


def write_changelog(directory: Path, content: str) -> Path:
    """Write a CHANGELOG.md with the given content."""
    path = directory / "CHANGELOG.md"
    path.write_text(content)
    return path


def write_skill_file(directory: Path, rel_path: str, content: str) -> Path:
    """Write a skill markdown file at the given relative path."""
    path = directory / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def setup_minimal_repo(
    root: Path,
    *,
    pyproject_version: str = "0.1.0",
    pixi_version: str = "0.1.0",
    init_version: str = "0.1.0",
) -> None:
    """Set up a minimal repo with consistent version files."""
    write_pyproject(root, pyproject_version)
    write_pixi(root, pixi_version)
    write_init(root, init_version)


# ---------------------------------------------------------------------------
# TestGetCanonicalVersion
# ---------------------------------------------------------------------------


class TestGetCanonicalVersion:
    """Tests for get_canonical_version()."""

    def test_reads_version(self, tmp_path: Path) -> None:
        """Should return the version string from pyproject.toml."""
        write_pyproject(tmp_path, "0.1.0")
        assert get_canonical_version(tmp_path / "pyproject.toml") == "0.1.0"

    def test_reads_higher_version(self, tmp_path: Path) -> None:
        """Should return any valid semver version."""
        write_pyproject(tmp_path, "2.3.1")
        assert get_canonical_version(tmp_path / "pyproject.toml") == "2.3.1"

    def test_missing_file_exits(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pyproject.toml does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            get_canonical_version(tmp_path / "pyproject.toml")
        assert exc_info.value.code == 1

    def test_malformed_toml_exits(self, tmp_path: Path) -> None:
        """Should sys.exit(1) on malformed TOML."""
        path = tmp_path / "pyproject.toml"
        path.write_text("not [valid toml\n")
        with pytest.raises(SystemExit) as exc_info:
            get_canonical_version(path)
        assert exc_info.value.code == 1

    def test_missing_version_key_exits(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if [project].version is missing."""
        path = tmp_path / "pyproject.toml"
        path.write_text('[project]\nname = "scylla"\n')
        with pytest.raises(SystemExit) as exc_info:
            get_canonical_version(path)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# TestCheckPixiVersion
# ---------------------------------------------------------------------------


class TestCheckPixiVersion:
    """Tests for check_pixi_version()."""

    def test_matching_version_passes(self, tmp_path: Path) -> None:
        """Should return empty list when pixi.toml version matches."""
        write_pixi(tmp_path, "0.1.0")
        assert check_pixi_version(tmp_path, "0.1.0") == []

    def test_mismatched_version_fails(self, tmp_path: Path) -> None:
        """Should return error when pixi.toml version differs."""
        write_pixi(tmp_path, "0.2.0")
        errors = check_pixi_version(tmp_path, "0.1.0")
        assert len(errors) == 1
        assert "0.2.0" in errors[0]
        assert "0.1.0" in errors[0]

    def test_missing_pixi_toml(self, tmp_path: Path) -> None:
        """Should return error when pixi.toml is missing."""
        errors = check_pixi_version(tmp_path, "0.1.0")
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_missing_workspace_version(self, tmp_path: Path) -> None:
        """Should return error when [workspace].version key is absent."""
        path = tmp_path / "pixi.toml"
        path.write_text('[workspace]\nname = "scylla"\n')
        errors = check_pixi_version(tmp_path, "0.1.0")
        assert len(errors) == 1
        assert "No [workspace].version" in errors[0]


# ---------------------------------------------------------------------------
# TestCheckInitVersion
# ---------------------------------------------------------------------------


class TestCheckInitVersion:
    """Tests for check_init_version()."""

    def test_matching_version_passes(self, tmp_path: Path) -> None:
        """Should return empty list when __version__ matches."""
        write_init(tmp_path, "0.1.0")
        assert check_init_version(tmp_path, "0.1.0") == []

    def test_mismatched_version_fails(self, tmp_path: Path) -> None:
        """Should return error when __version__ differs."""
        write_init(tmp_path, "0.2.0")
        errors = check_init_version(tmp_path, "0.1.0")
        assert len(errors) == 1
        assert "0.2.0" in errors[0]

    def test_missing_init_file(self, tmp_path: Path) -> None:
        """Should return error when __init__.py is missing."""
        errors = check_init_version(tmp_path, "0.1.0")
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_importlib_metadata_passes(self, tmp_path: Path) -> None:
        """Should pass when __init__.py uses importlib.metadata (no hardcoded __version__)."""
        scylla_dir = tmp_path / "scylla"
        scylla_dir.mkdir()
        init_path = scylla_dir / "__init__.py"
        init_path.write_text(
            "from importlib.metadata import version as _get_version\n"
            '__version__ = _get_version("scylla")\n'
        )
        # The regex won't match the dynamic assignment — no error
        assert check_init_version(tmp_path, "0.1.0") == []

    def test_single_quote_version(self, tmp_path: Path) -> None:
        """Should match __version__ with single quotes."""
        scylla_dir = tmp_path / "scylla"
        scylla_dir.mkdir()
        init_path = scylla_dir / "__init__.py"
        init_path.write_text("__version__ = '0.1.0'\n")
        assert check_init_version(tmp_path, "0.1.0") == []


# ---------------------------------------------------------------------------
# TestFindAspirationalVersions
# ---------------------------------------------------------------------------


class TestFindAspirationalVersions:
    """Tests for find_aspirational_versions()."""

    def test_no_versions_passes(self, tmp_path: Path) -> None:
        """Should return empty list for files with no version references."""
        path = tmp_path / "test.md"
        path.write_text("# No version references here\n")
        assert find_aspirational_versions(path, (0, 1, 0), "test.md") == []

    def test_matching_version_passes(self, tmp_path: Path) -> None:
        """Should not flag versions equal to canonical."""
        path = tmp_path / "test.md"
        path.write_text("Released in v0.1.0\n")
        assert find_aspirational_versions(path, (0, 1, 0), "test.md") == []

    def test_lower_version_passes(self, tmp_path: Path) -> None:
        """Should not flag versions below canonical."""
        path = tmp_path / "test.md"
        path.write_text("Originally released in v0.0.1\n")
        assert find_aspirational_versions(path, (0, 1, 0), "test.md") == []

    def test_higher_version_fails(self, tmp_path: Path) -> None:
        """Should flag versions above canonical."""
        path = tmp_path / "test.md"
        path.write_text("Will be removed in v2.0.0\n")
        errors = find_aspirational_versions(path, (0, 1, 0), "test.md")
        assert len(errors) == 1
        assert "v2.0.0" in errors[0]
        assert ":1:" in errors[0]

    def test_multiple_versions_on_same_line(self, tmp_path: Path) -> None:
        """Should flag all aspirational versions even on the same line."""
        path = tmp_path / "test.md"
        path.write_text("| v1.5.0 | deprecated | v2.0.0 | removed |\n")
        errors = find_aspirational_versions(path, (0, 1, 0), "test.md")
        assert len(errors) == 2

    def test_version_without_v_prefix(self, tmp_path: Path) -> None:
        """Should detect version numbers without a 'v' prefix."""
        path = tmp_path / "test.md"
        path.write_text("Deprecated as of 1.5.0\n")
        errors = find_aspirational_versions(path, (0, 1, 0), "test.md")
        assert len(errors) == 1
        assert "v1.5.0" in errors[0]

    def test_reports_correct_line_number(self, tmp_path: Path) -> None:
        """Should report the correct line number for aspirational versions."""
        path = tmp_path / "test.md"
        path.write_text("line 1\nline 2\nRemoved in v3.0.0\nline 4\n")
        errors = find_aspirational_versions(path, (0, 1, 0), "test.md")
        assert len(errors) == 1
        assert ":3:" in errors[0]

    def test_url_embedded_versions_ignored(self, tmp_path: Path) -> None:
        """Should not flag versions embedded in URL paths."""
        path = tmp_path / "test.md"
        path.write_text(
            "Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).\n"
        )
        assert find_aspirational_versions(path, (0, 1, 0), "test.md") == []


# ---------------------------------------------------------------------------
# TestCheckChangelog
# ---------------------------------------------------------------------------


class TestCheckChangelog:
    """Tests for check_changelog()."""

    def test_no_changelog_passes(self, tmp_path: Path) -> None:
        """Should pass when CHANGELOG.md does not exist."""
        assert check_changelog(tmp_path, "0.1.0") == []

    def test_clean_changelog_passes(self, tmp_path: Path) -> None:
        """Should pass when CHANGELOG.md only references canonical or lower versions."""
        write_changelog(
            tmp_path,
            "# Changelog\n\n## [0.1.0] - 2026-03-25\n\n### Added\n\n- Feature X\n",
        )
        assert check_changelog(tmp_path, "0.1.0") == []

    def test_aspirational_version_detected(self, tmp_path: Path) -> None:
        """Should detect aspirational version references in CHANGELOG.md."""
        write_changelog(
            tmp_path,
            "# Changelog\n\n## [Unreleased]\n\n"
            "### Deprecated\n\n- Deprecated as of v1.5.0, removed in v2.0.0\n",
        )
        errors = check_changelog(tmp_path, "0.1.0")
        assert len(errors) == 2
        assert any("v1.5.0" in e for e in errors)
        assert any("v2.0.0" in e for e in errors)

    def test_migration_timeline_table_detected(self, tmp_path: Path) -> None:
        """Should detect aspirational versions in Migration Timeline tables."""
        write_changelog(
            tmp_path,
            "## Migration Timeline\n\n"
            "| Version | Action |\n"
            "|---------|--------|\n"
            "| v1.5.0  | Deprecated |\n"
            "| v2.0.0  | Removed |\n",
        )
        errors = check_changelog(tmp_path, "0.1.0")
        assert len(errors) == 2


# ---------------------------------------------------------------------------
# TestCheckSkillFiles
# ---------------------------------------------------------------------------


class TestCheckSkillFiles:
    """Tests for check_skill_files()."""

    def test_no_skill_dirs_passes(self, tmp_path: Path) -> None:
        """Should pass when neither .claude-plugin/skills/ nor .claude/ exist."""
        assert check_skill_files(tmp_path, "0.1.0") == []

    def test_clean_skill_file_passes(self, tmp_path: Path) -> None:
        """Should pass when skill files only reference the canonical version."""
        write_skill_file(
            tmp_path,
            ".claude-plugin/skills/example/SKILL.md",
            "# Example Skill\n\nAdded in v0.1.0\n",
        )
        assert check_skill_files(tmp_path, "0.1.0") == []

    def test_aspirational_in_skills_detected(self, tmp_path: Path) -> None:
        """Should detect aspirational versions in .claude-plugin/skills/ files."""
        write_skill_file(
            tmp_path,
            ".claude-plugin/skills/backward-compat-removal/SKILL.md",
            "# backward-compat-removal\n\nRemove as part of v2.0.0 cleanup\n",
        )
        errors = check_skill_files(tmp_path, "0.1.0")
        assert len(errors) == 1
        assert "v2.0.0" in errors[0]
        assert "backward-compat-removal" in errors[0]

    def test_aspirational_in_claude_dir_detected(self, tmp_path: Path) -> None:
        """Should detect aspirational versions in .claude/ markdown files."""
        write_skill_file(
            tmp_path,
            ".claude/agents/test-agent.md",
            "# Agent\n\nTarget version: v3.0.0\n",
        )
        errors = check_skill_files(tmp_path, "0.1.0")
        assert len(errors) == 1
        assert "v3.0.0" in errors[0]

    def test_non_md_files_ignored(self, tmp_path: Path) -> None:
        """Should only scan .md files, not other file types."""
        skills_dir = tmp_path / ".claude-plugin" / "skills" / "example"
        skills_dir.mkdir(parents=True)
        (skills_dir / "config.yaml").write_text("version: v5.0.0\n")
        assert check_skill_files(tmp_path, "0.1.0") == []

    def test_multiple_skill_files_scanned(self, tmp_path: Path) -> None:
        """Should scan all markdown files across both directories."""
        write_skill_file(
            tmp_path,
            ".claude-plugin/skills/skill-a/SKILL.md",
            "Removed in v2.0.0\n",
        )
        write_skill_file(
            tmp_path,
            ".claude/shared/guidance.md",
            "Planned for v3.0.0\n",
        )
        errors = check_skill_files(tmp_path, "0.1.0")
        assert len(errors) == 2

    def test_external_tool_versions_not_flagged(self, tmp_path: Path) -> None:
        """Should not flag versions that match or are below canonical."""
        write_skill_file(
            tmp_path,
            ".claude-plugin/skills/ci/SKILL.md",
            "# CI Skill\n\nUses action v0.0.1 and tool 0.1.0\n",
        )
        assert check_skill_files(tmp_path, "0.1.0") == []


# ---------------------------------------------------------------------------
# TestCheckPackageVersionConsistency (integration)
# ---------------------------------------------------------------------------


class TestCheckPackageVersionConsistency:
    """Integration tests for check_package_version_consistency()."""

    def test_all_consistent_returns_zero(self, tmp_path: Path) -> None:
        """Should return 0 when all versions match and no aspirational refs."""
        setup_minimal_repo(tmp_path)
        write_changelog(tmp_path, "# Changelog\n\n## [0.1.0]\n\n- Initial\n")
        assert check_package_version_consistency(tmp_path) == 0

    def test_pixi_mismatch_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when pixi.toml version differs."""
        setup_minimal_repo(tmp_path, pixi_version="0.2.0")
        assert check_package_version_consistency(tmp_path) == 1

    def test_init_mismatch_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when __init__.py version differs."""
        setup_minimal_repo(tmp_path, init_version="0.2.0")
        assert check_package_version_consistency(tmp_path) == 1

    def test_changelog_aspirational_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when CHANGELOG.md has aspirational versions."""
        setup_minimal_repo(tmp_path)
        write_changelog(tmp_path, "Deprecated in v1.5.0, removed in v2.0.0\n")
        assert check_package_version_consistency(tmp_path) == 1

    def test_skill_files_not_scanned_by_default(self, tmp_path: Path) -> None:
        """Should NOT scan skill files when --scan-skills is not set."""
        setup_minimal_repo(tmp_path)
        write_skill_file(
            tmp_path,
            ".claude-plugin/skills/test/SKILL.md",
            "Removed in v9.0.0\n",
        )
        assert check_package_version_consistency(tmp_path, scan_skills=False) == 0

    def test_skill_files_scanned_when_enabled(self, tmp_path: Path) -> None:
        """Should scan skill files when --scan-skills is True."""
        setup_minimal_repo(tmp_path)
        write_skill_file(
            tmp_path,
            ".claude-plugin/skills/test/SKILL.md",
            "Removed in v9.0.0\n",
        )
        assert check_package_version_consistency(tmp_path, scan_skills=True) == 1

    def test_verbose_prints_ok(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """With verbose=True, should print OK message on success."""
        setup_minimal_repo(tmp_path)
        result = check_package_version_consistency(tmp_path, verbose=True)
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out
        assert "0.1.0" in captured.out

    def test_verbose_prints_canonical_version(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With verbose=True, should print the canonical version."""
        setup_minimal_repo(tmp_path)
        check_package_version_consistency(tmp_path, verbose=True)
        captured = capsys.readouterr()
        assert "Canonical version" in captured.out

    def test_error_count_reported(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Should report total violation count on failure."""
        setup_minimal_repo(tmp_path, pixi_version="0.2.0", init_version="0.3.0")
        check_package_version_consistency(tmp_path)
        captured = capsys.readouterr()
        assert "2 package version consistency violation(s)" in captured.err

    def test_missing_pyproject_exits(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pyproject.toml is missing."""
        with pytest.raises(SystemExit) as exc_info:
            check_package_version_consistency(tmp_path)
        assert exc_info.value.code == 1
