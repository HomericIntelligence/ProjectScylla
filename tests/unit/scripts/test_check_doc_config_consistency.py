"""Tests for scripts/check_doc_config_consistency.py."""

import textwrap
from pathlib import Path

import pytest

from scripts.check_doc_config_consistency import (
    check_addopts_cov_fail_under,
    check_claude_md_threshold,
    check_readme_cov_path,
    extract_cov_fail_under_from_addopts,
    extract_cov_path_from_pyproject,
    load_pyproject_coverage_threshold,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_pyproject(tmp_path: Path, content: str) -> Path:
    """Write a pyproject.toml to *tmp_path* and return its path."""
    path = tmp_path / "pyproject.toml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def write_claude_md(tmp_path: Path, content: str) -> Path:
    """Write a CLAUDE.md to *tmp_path* and return its path."""
    path = tmp_path / "CLAUDE.md"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def write_readme(tmp_path: Path, content: str) -> Path:
    """Write a README.md to *tmp_path* and return its path."""
    path = tmp_path / "README.md"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


PYPROJECT_THRESHOLD_75 = """\
    [tool.coverage.report]
    fail_under = 75
"""

PYPROJECT_THRESHOLD_80 = """\
    [tool.coverage.report]
    fail_under = 80
"""

PYPROJECT_COV_SCYLLA = """\
    [tool.pytest.ini_options]
    addopts = ["--cov=scylla", "--cov-report=term-missing", "--cov-fail-under=75"]
"""

PYPROJECT_FULL = """\
    [tool.coverage.report]
    fail_under = 75

    [tool.pytest.ini_options]
    addopts = ["--cov=scylla", "--cov-report=term-missing", "--cov-fail-under=75"]
"""


# ---------------------------------------------------------------------------
# load_pyproject_coverage_threshold
# ---------------------------------------------------------------------------


class TestLoadPyprojectCoverageThreshold:
    """Tests for load_pyproject_coverage_threshold()."""

    def test_reads_threshold(self, tmp_path: Path) -> None:
        """Should return the integer fail_under value."""
        write_pyproject(tmp_path, PYPROJECT_THRESHOLD_75)
        assert load_pyproject_coverage_threshold(tmp_path) == 75

    def test_reads_different_threshold(self, tmp_path: Path) -> None:
        """Should return 80 when fail_under is 80."""
        write_pyproject(tmp_path, PYPROJECT_THRESHOLD_80)
        assert load_pyproject_coverage_threshold(tmp_path) == 80

    def test_missing_pyproject_exits(self, tmp_path: Path) -> None:
        """Should exit 1 when pyproject.toml is absent."""
        with pytest.raises(SystemExit) as exc_info:
            load_pyproject_coverage_threshold(tmp_path)
        assert exc_info.value.code == 1

    def test_missing_fail_under_key_exits(self, tmp_path: Path) -> None:
        """Should exit 1 when the fail_under key is absent."""
        write_pyproject(tmp_path, "[tool.coverage.run]\nbranch = true\n")
        with pytest.raises(SystemExit) as exc_info:
            load_pyproject_coverage_threshold(tmp_path)
        assert exc_info.value.code == 1

    def test_invalid_toml_exits(self, tmp_path: Path) -> None:
        """Should exit 1 on malformed TOML."""
        (tmp_path / "pyproject.toml").write_bytes(b"not = valid [ toml }")
        with pytest.raises(SystemExit) as exc_info:
            load_pyproject_coverage_threshold(tmp_path)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# extract_cov_path_from_pyproject
# ---------------------------------------------------------------------------


class TestExtractCovPathFromPyproject:
    """Tests for extract_cov_path_from_pyproject()."""

    def test_extracts_path(self, tmp_path: Path) -> None:
        """Should return the package path from --cov=<path>."""
        write_pyproject(tmp_path, PYPROJECT_COV_SCYLLA)
        assert extract_cov_path_from_pyproject(tmp_path) == "scylla"

    def test_extracts_different_path(self, tmp_path: Path) -> None:
        """Should return the correct path for a different package."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = ["--cov=mypackage"]\n',
        )
        assert extract_cov_path_from_pyproject(tmp_path) == "mypackage"

    def test_addopts_as_string(self, tmp_path: Path) -> None:
        """Should handle addopts as a plain string."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = "--cov=scylla --cov-report=term"\n',
        )
        assert extract_cov_path_from_pyproject(tmp_path) == "scylla"

    def test_no_cov_flag_exits(self, tmp_path: Path) -> None:
        """Should exit 1 when no --cov= flag is present in addopts."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = ["-v", "--tb=short"]\n',
        )
        with pytest.raises(SystemExit) as exc_info:
            extract_cov_path_from_pyproject(tmp_path)
        assert exc_info.value.code == 1

    def test_missing_addopts_exits(self, tmp_path: Path) -> None:
        """Should exit 1 when addopts is entirely absent."""
        write_pyproject(tmp_path, "[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
        with pytest.raises(SystemExit) as exc_info:
            extract_cov_path_from_pyproject(tmp_path)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# check_claude_md_threshold
# ---------------------------------------------------------------------------


class TestCheckClaudeMdThreshold:
    """Tests for check_claude_md_threshold()."""

    def test_matching_threshold_returns_no_errors(self, tmp_path: Path) -> None:
        """Should return empty list when CLAUDE.md matches expected threshold."""
        write_claude_md(
            tmp_path,
            "studies with 75%+ test coverage enforced in CI.\n",
        )
        assert check_claude_md_threshold(tmp_path, 75) == []

    def test_matching_threshold_without_plus_returns_no_errors(self, tmp_path: Path) -> None:
        """Should also match '75% test coverage' (without '+')."""
        write_claude_md(
            tmp_path,
            "requires 75% test coverage in this project.\n",
        )
        assert check_claude_md_threshold(tmp_path, 75) == []

    def test_mismatched_threshold_returns_error(self, tmp_path: Path) -> None:
        """Should return an error when CLAUDE.md has a different threshold."""
        write_claude_md(
            tmp_path,
            "studies with 80%+ test coverage enforced in CI.\n",
        )
        errors = check_claude_md_threshold(tmp_path, 75)
        assert len(errors) == 1
        assert "80%" in errors[0]
        assert "75%" in errors[0]

    def test_missing_claude_md_returns_error(self, tmp_path: Path) -> None:
        """Should return an error when CLAUDE.md does not exist."""
        errors = check_claude_md_threshold(tmp_path, 75)
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_no_coverage_mention_returns_error(self, tmp_path: Path) -> None:
        """Should return an error when CLAUDE.md has no coverage threshold mention."""
        write_claude_md(tmp_path, "No mention of coverage here.\n")
        errors = check_claude_md_threshold(tmp_path, 75)
        assert len(errors) == 1
        assert "No coverage threshold mention" in errors[0]

    def test_multiple_matching_occurrences_no_errors(self, tmp_path: Path) -> None:
        """Multiple matching occurrences should all pass."""
        write_claude_md(
            tmp_path,
            "75%+ test coverage enforced. Also: 75%+ test coverage required.\n",
        )
        assert check_claude_md_threshold(tmp_path, 75) == []

    def test_multiple_occurrences_one_mismatch_returns_error(self, tmp_path: Path) -> None:
        """If any occurrence mismatches, an error should be returned."""
        write_claude_md(
            tmp_path,
            "75%+ test coverage enforced. Also: 80%+ test coverage elsewhere.\n",
        )
        errors = check_claude_md_threshold(tmp_path, 75)
        assert len(errors) == 1
        assert "80%" in errors[0]


# ---------------------------------------------------------------------------
# check_readme_cov_path
# ---------------------------------------------------------------------------


class TestCheckReadmeCovPath:
    """Tests for check_readme_cov_path()."""

    def test_matching_path_returns_no_errors(self, tmp_path: Path) -> None:
        """Should return empty list when README.md --cov path matches."""
        write_readme(
            tmp_path,
            "Run: pytest tests/ --cov=scylla --cov-report=html\n",
        )
        assert check_readme_cov_path(tmp_path, "scylla") == []

    def test_mismatched_path_returns_error(self, tmp_path: Path) -> None:
        """Should return an error when README.md has the wrong --cov path."""
        write_readme(
            tmp_path,
            "Run: pytest tests/ --cov=wrong_pkg --cov-report=html\n",
        )
        errors = check_readme_cov_path(tmp_path, "scylla")
        assert len(errors) == 1
        assert "wrong_pkg" in errors[0]
        assert "scylla" in errors[0]

    def test_no_cov_in_readme_returns_no_errors(self, tmp_path: Path) -> None:
        """README.md with no --cov= occurrences should pass without error."""
        write_readme(tmp_path, "Just run pytest to execute tests.\n")
        assert check_readme_cov_path(tmp_path, "scylla") == []

    def test_missing_readme_returns_error(self, tmp_path: Path) -> None:
        """Should return an error when README.md does not exist."""
        errors = check_readme_cov_path(tmp_path, "scylla")
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_multiple_matching_occurrences_no_errors(self, tmp_path: Path) -> None:
        """Multiple correct --cov=scylla occurrences should all pass."""
        write_readme(
            tmp_path,
            "pytest --cov=scylla\nalso pytest --cov=scylla --cov-report=html\n",
        )
        assert check_readme_cov_path(tmp_path, "scylla") == []

    def test_multiple_occurrences_one_mismatch_returns_errors(self, tmp_path: Path) -> None:
        """Should report each mismatched --cov occurrence."""
        write_readme(
            tmp_path,
            "pytest --cov=scylla\npytest --cov=wrong_pkg\n",
        )
        errors = check_readme_cov_path(tmp_path, "scylla")
        assert len(errors) == 1
        assert "wrong_pkg" in errors[0]


# ---------------------------------------------------------------------------
# extract_cov_fail_under_from_addopts
# ---------------------------------------------------------------------------


class TestExtractCovFailUnderFromAddopts:
    """Tests for extract_cov_fail_under_from_addopts()."""

    def test_extracts_threshold(self, tmp_path: Path) -> None:
        """Should return the integer threshold from --cov-fail-under=N."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = ["--cov-fail-under=75"]\n',
        )
        assert extract_cov_fail_under_from_addopts(tmp_path) == 75

    def test_extracts_different_threshold(self, tmp_path: Path) -> None:
        """Should return 80 when --cov-fail-under=80 is set."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = ["--cov-fail-under=80"]\n',
        )
        assert extract_cov_fail_under_from_addopts(tmp_path) == 80

    def test_flag_absent_returns_none(self, tmp_path: Path) -> None:
        """Should return None when no --cov-fail-under flag is present."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = ["--cov=scylla"]\n',
        )
        assert extract_cov_fail_under_from_addopts(tmp_path) is None

    def test_addopts_as_string(self, tmp_path: Path) -> None:
        """Should handle addopts as a plain string."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = "--cov=scylla --cov-fail-under=75"\n',
        )
        assert extract_cov_fail_under_from_addopts(tmp_path) == 75

    def test_no_addopts_returns_none(self, tmp_path: Path) -> None:
        """Should return None when addopts key is absent."""
        write_pyproject(tmp_path, "[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
        assert extract_cov_fail_under_from_addopts(tmp_path) is None

    def test_invalid_toml_exits(self, tmp_path: Path) -> None:
        """Should exit 1 on malformed TOML."""
        (tmp_path / "pyproject.toml").write_bytes(b"not = valid [ toml }")
        with pytest.raises(SystemExit) as exc_info:
            extract_cov_fail_under_from_addopts(tmp_path)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# check_addopts_cov_fail_under
# ---------------------------------------------------------------------------


class TestCheckAddoptsCovFailUnder:
    """Tests for check_addopts_cov_fail_under()."""

    def test_matching_threshold_returns_no_errors(self, tmp_path: Path) -> None:
        """Should return empty list when addopts threshold matches expected."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = ["--cov-fail-under=75"]\n',
        )
        assert check_addopts_cov_fail_under(tmp_path, 75) == []

    def test_mismatched_threshold_returns_error(self, tmp_path: Path) -> None:
        """Should return an error when addopts threshold differs from expected."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = ["--cov-fail-under=80"]\n',
        )
        errors = check_addopts_cov_fail_under(tmp_path, 75)
        assert len(errors) == 1
        assert "80" in errors[0]
        assert "75" in errors[0]

    def test_missing_flag_returns_error(self, tmp_path: Path) -> None:
        """Should return an error when --cov-fail-under is absent from addopts."""
        write_pyproject(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = ["--cov=scylla"]\n',
        )
        errors = check_addopts_cov_fail_under(tmp_path, 75)
        assert len(errors) == 1
        assert "--cov-fail-under" in errors[0]


# ---------------------------------------------------------------------------
# Integration: main() via subprocess
# ---------------------------------------------------------------------------


class TestMainIntegration:
    """Integration tests for the main() function using tmp_path repos."""

    def _make_repo(
        self,
        tmp_path: Path,
        threshold: int = 75,
        cov_path: str = "scylla",
        claude_threshold: int = 75,
        readme_cov: str = "scylla",
        addopts_fail_under: int | None = 75,
    ) -> Path:
        """Create a minimal fake repo with all required files."""
        addopts_items = [f'"--cov={cov_path}"']
        if addopts_fail_under is not None:
            addopts_items.append(f'"--cov-fail-under={addopts_fail_under}"')
        addopts_str = ", ".join(addopts_items)
        write_pyproject(
            tmp_path,
            f"[tool.coverage.report]\nfail_under = {threshold}\n\n"
            f"[tool.pytest.ini_options]\naddopts = [{addopts_str}]\n",
        )
        write_claude_md(
            tmp_path,
            f"This project requires {claude_threshold}%+ test coverage enforced in CI.\n",
        )
        write_readme(
            tmp_path,
            f"Run tests: pytest --cov={readme_cov} --cov-report=html\n",
        )
        return tmp_path

    def test_all_matching_exits_zero(self, tmp_path: Path) -> None:
        """All matching values should produce exit code 0."""
        import sys

        from scripts.check_doc_config_consistency import main

        repo = self._make_repo(tmp_path)
        original_argv = sys.argv
        sys.argv = ["check_doc_config_consistency.py", "--repo-root", str(repo)]
        try:
            result = main()
            assert result == 0
        finally:
            sys.argv = original_argv

    def test_threshold_mismatch_exits_one(self, tmp_path: Path) -> None:
        """Coverage threshold mismatch should produce exit code 1."""
        import sys

        from scripts.check_doc_config_consistency import main

        repo = self._make_repo(tmp_path, threshold=75, claude_threshold=80)
        original_argv = sys.argv
        sys.argv = ["check_doc_config_consistency.py", "--repo-root", str(repo)]
        try:
            result = main()
            assert result == 1
        finally:
            sys.argv = original_argv

    def test_cov_path_mismatch_exits_one(self, tmp_path: Path) -> None:
        """--cov path mismatch should produce exit code 1."""
        import sys

        from scripts.check_doc_config_consistency import main

        repo = self._make_repo(tmp_path, cov_path="scylla", readme_cov="wrong_pkg")
        original_argv = sys.argv
        sys.argv = ["check_doc_config_consistency.py", "--repo-root", str(repo)]
        try:
            result = main()
            assert result == 1
        finally:
            sys.argv = original_argv

    def test_addopts_fail_under_mismatch_exits_one(self, tmp_path: Path) -> None:
        """--cov-fail-under mismatch in addopts should produce exit code 1."""
        import sys

        from scripts.check_doc_config_consistency import main

        repo = self._make_repo(tmp_path, threshold=75, addopts_fail_under=80)
        original_argv = sys.argv
        sys.argv = ["check_doc_config_consistency.py", "--repo-root", str(repo)]
        try:
            result = main()
            assert result == 1
        finally:
            sys.argv = original_argv

    def test_addopts_fail_under_absent_exits_one(self, tmp_path: Path) -> None:
        """Missing --cov-fail-under in addopts should produce exit code 1."""
        import sys

        from scripts.check_doc_config_consistency import main

        repo = self._make_repo(tmp_path, addopts_fail_under=None)
        original_argv = sys.argv
        sys.argv = ["check_doc_config_consistency.py", "--repo-root", str(repo)]
        try:
            result = main()
            assert result == 1
        finally:
            sys.argv = original_argv
