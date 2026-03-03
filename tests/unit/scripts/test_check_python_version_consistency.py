"""Tests for scripts/check_python_version_consistency.py."""

import textwrap
from pathlib import Path

import pytest

from scripts.check_python_version_consistency import (
    check_version_consistency,
    get_dockerfile_python_version,
    get_highest_python_classifier,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_pyproject(directory: Path, classifiers: list[str]) -> Path:
    """Write a minimal pyproject.toml with the given classifiers."""
    classifier_lines = "\n".join(f'    "{c}",' for c in classifiers)
    content = textwrap.dedent(f"""\
        [project]
        name = "test-project"
        version = "0.1.0"
        classifiers = [
        {classifier_lines}
        ]
    """)
    path = directory / "pyproject.toml"
    path.write_text(content)
    return path


def write_dockerfile(directory: Path, from_line: str) -> Path:
    """Write a minimal Dockerfile with the given FROM line."""
    dockerfile_dir = directory / "docker"
    dockerfile_dir.mkdir(exist_ok=True)
    path = dockerfile_dir / "Dockerfile"
    path.write_text(f"# test dockerfile\n{from_line}\nRUN echo hello\n")
    return path


# ---------------------------------------------------------------------------
# TestGetHighestPythonClassifier
# ---------------------------------------------------------------------------


class TestGetHighestPythonClassifier:
    """Tests for get_highest_python_classifier()."""

    def test_single_version_returned(self, tmp_path: Path) -> None:
        """Should return the only X.Y classifier version."""
        write_pyproject(tmp_path, ["Programming Language :: Python :: 3.10"])
        assert get_highest_python_classifier(tmp_path / "pyproject.toml") == "3.10"

    def test_returns_highest_of_multiple(self, tmp_path: Path) -> None:
        """Should return the highest version when multiple X.Y classifiers exist."""
        write_pyproject(
            tmp_path,
            [
                "Programming Language :: Python :: 3.10",
                "Programming Language :: Python :: 3.11",
                "Programming Language :: Python :: 3.13",
                "Programming Language :: Python :: 3.12",
            ],
        )
        assert get_highest_python_classifier(tmp_path / "pyproject.toml") == "3.13"

    def test_ignores_non_version_classifiers(self, tmp_path: Path) -> None:
        """Should ignore classifiers that are not X.Y version entries."""
        write_pyproject(
            tmp_path,
            [
                "Development Status :: 3 - Alpha",
                "Programming Language :: Python :: 3",
                "Programming Language :: Python :: 3.12",
                "License :: OSI Approved :: BSD License",
            ],
        )
        assert get_highest_python_classifier(tmp_path / "pyproject.toml") == "3.12"

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pyproject.toml does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            get_highest_python_classifier(tmp_path / "pyproject.toml")
        assert exc_info.value.code == 1

    def test_no_python_classifiers_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if no Programming Language :: Python :: X.Y classifiers."""
        write_pyproject(
            tmp_path,
            ["Development Status :: 3 - Alpha", "License :: OSI Approved :: BSD License"],
        )
        with pytest.raises(SystemExit) as exc_info:
            get_highest_python_classifier(tmp_path / "pyproject.toml")
        assert exc_info.value.code == 1

    def test_empty_classifiers_list_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if classifiers list is empty."""
        write_pyproject(tmp_path, [])
        with pytest.raises(SystemExit) as exc_info:
            get_highest_python_classifier(tmp_path / "pyproject.toml")
        assert exc_info.value.code == 1

    def test_malformed_toml_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) on malformed TOML without crashing."""
        path = tmp_path / "pyproject.toml"
        path.write_text("this is not [valid toml\n")
        with pytest.raises(SystemExit) as exc_info:
            get_highest_python_classifier(path)
        assert exc_info.value.code == 1

    def test_no_project_section_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if [project] section is missing entirely."""
        path = tmp_path / "pyproject.toml"
        path.write_text("[build-system]\nrequires = ['setuptools']\n")
        with pytest.raises(SystemExit) as exc_info:
            get_highest_python_classifier(path)
        assert exc_info.value.code == 1

    def test_version_comparison_is_numeric(self, tmp_path: Path) -> None:
        """Should compare versions numerically (3.9 < 3.10, not string sort)."""
        write_pyproject(
            tmp_path,
            [
                "Programming Language :: Python :: 3.9",
                "Programming Language :: Python :: 3.10",
            ],
        )
        # String sort would give "3.9" > "3.10", but numeric gives "3.10"
        assert get_highest_python_classifier(tmp_path / "pyproject.toml") == "3.10"


# ---------------------------------------------------------------------------
# TestGetDockerfilePythonVersion
# ---------------------------------------------------------------------------


class TestGetDockerfilePythonVersion:
    """Tests for get_dockerfile_python_version()."""

    def test_simple_from_line(self, tmp_path: Path) -> None:
        """Should parse version from simple FROM python:3.12 line."""
        write_dockerfile(tmp_path, "FROM python:3.12")
        assert get_dockerfile_python_version(tmp_path / "docker" / "Dockerfile") == "3.12"

    def test_slim_variant(self, tmp_path: Path) -> None:
        """Should parse version from FROM python:3.12-slim line."""
        write_dockerfile(tmp_path, "FROM python:3.12-slim")
        assert get_dockerfile_python_version(tmp_path / "docker" / "Dockerfile") == "3.12"

    def test_digest_pinned(self, tmp_path: Path) -> None:
        """Should parse version from digest-pinned FROM line."""
        digest = "sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c"
        write_dockerfile(tmp_path, f"FROM python:3.12-slim@{digest} AS builder")
        assert get_dockerfile_python_version(tmp_path / "docker" / "Dockerfile") == "3.12"

    def test_with_build_stage_alias(self, tmp_path: Path) -> None:
        """Should parse version from FROM python:3.11 AS builder line."""
        write_dockerfile(tmp_path, "FROM python:3.11 AS builder")
        assert get_dockerfile_python_version(tmp_path / "docker" / "Dockerfile") == "3.11"

    def test_case_insensitive_from(self, tmp_path: Path) -> None:
        """Should parse version case-insensitively."""
        write_dockerfile(tmp_path, "from python:3.10-slim")
        assert get_dockerfile_python_version(tmp_path / "docker" / "Dockerfile") == "3.10"

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if Dockerfile does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            get_dockerfile_python_version(tmp_path / "docker" / "Dockerfile")
        assert exc_info.value.code == 1

    def test_no_from_python_line_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if no FROM python:X.Y line is found."""
        dockerfile_dir = tmp_path / "docker"
        dockerfile_dir.mkdir()
        path = dockerfile_dir / "Dockerfile"
        path.write_text("FROM ubuntu:22.04\nRUN apt-get update\n")
        with pytest.raises(SystemExit) as exc_info:
            get_dockerfile_python_version(path)
        assert exc_info.value.code == 1

    def test_uses_first_from_line(self, tmp_path: Path) -> None:
        """Should use the first FROM python:X.Y line in multi-stage builds."""
        dockerfile_dir = tmp_path / "docker"
        dockerfile_dir.mkdir()
        path = dockerfile_dir / "Dockerfile"
        path.write_text("FROM python:3.12-slim AS builder\nFROM python:3.10-slim AS runtime\n")
        assert get_dockerfile_python_version(path) == "3.12"

    @pytest.mark.parametrize(
        "from_line,expected",
        [
            ("FROM python:3.10", "3.10"),
            ("FROM python:3.11-slim", "3.11"),
            ("FROM python:3.12-alpine", "3.12"),
            ("FROM python:3.13-slim@sha256:abc123", "3.13"),
        ],
    )
    def test_various_variants(self, from_line: str, expected: str, tmp_path: Path) -> None:
        """Should parse version from various FROM python:X.Y variants."""
        write_dockerfile(tmp_path, from_line)
        assert get_dockerfile_python_version(tmp_path / "docker" / "Dockerfile") == expected


# ---------------------------------------------------------------------------
# TestCheckVersionConsistency
# ---------------------------------------------------------------------------


class TestCheckVersionConsistency:
    """Tests for check_version_consistency()."""

    def _setup_repo(self, root: Path, classifier_versions: list[str], from_line: str) -> None:
        """Set up a minimal repo with pyproject.toml and Dockerfile."""
        classifiers = [f"Programming Language :: Python :: {v}" for v in classifier_versions]
        write_pyproject(root, classifiers)
        write_dockerfile(root, from_line)

    def test_matching_versions_returns_zero(self, tmp_path: Path) -> None:
        """Should return 0 when pyproject.toml and Dockerfile versions match."""
        self._setup_repo(tmp_path, ["3.12"], "FROM python:3.12-slim")
        assert check_version_consistency(tmp_path) == 0

    def test_mismatch_returns_one(self, tmp_path: Path) -> None:
        """Should return 1 when versions differ."""
        self._setup_repo(tmp_path, ["3.13"], "FROM python:3.12-slim")
        assert check_version_consistency(tmp_path) == 1

    def test_mismatch_prints_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should print descriptive error message to stderr on mismatch."""
        self._setup_repo(tmp_path, ["3.13"], "FROM python:3.12-slim")
        check_version_consistency(tmp_path)
        captured = capsys.readouterr()
        assert "3.13" in captured.err
        assert "3.12" in captured.err

    def test_highest_classifier_is_compared(self, tmp_path: Path) -> None:
        """Should compare the highest classifier version (not just any version)."""
        # Multiple classifiers; highest is 3.13; Dockerfile has 3.13 — should match
        self._setup_repo(
            tmp_path,
            ["3.10", "3.11", "3.12", "3.13"],
            "FROM python:3.13-slim",
        )
        assert check_version_consistency(tmp_path) == 0

    def test_highest_classifier_mismatch(self, tmp_path: Path) -> None:
        """Should fail if highest classifier doesn't match Dockerfile."""
        # Classifiers include 3.13 but Dockerfile is still 3.12
        self._setup_repo(
            tmp_path,
            ["3.10", "3.11", "3.12", "3.13"],
            "FROM python:3.12-slim",
        )
        assert check_version_consistency(tmp_path) == 1

    def test_missing_pyproject_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if pyproject.toml is missing."""
        # Only create Dockerfile, no pyproject.toml
        write_dockerfile(tmp_path, "FROM python:3.12-slim")
        with pytest.raises(SystemExit) as exc_info:
            check_version_consistency(tmp_path)
        assert exc_info.value.code == 1

    def test_missing_dockerfile_exits_one(self, tmp_path: Path) -> None:
        """Should sys.exit(1) if Dockerfile is missing."""
        # Only create pyproject.toml, no Dockerfile
        write_pyproject(tmp_path, ["Programming Language :: Python :: 3.12"])
        with pytest.raises(SystemExit) as exc_info:
            check_version_consistency(tmp_path)
        assert exc_info.value.code == 1

    def test_verbose_prints_versions_on_match(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With verbose=True, should print parsed versions even when they match."""
        self._setup_repo(tmp_path, ["3.12"], "FROM python:3.12-slim")
        result = check_version_consistency(tmp_path, verbose=True)
        assert result == 0
        captured = capsys.readouterr()
        assert "3.12" in captured.out

    def test_verbose_prints_ok_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With verbose=True on a match, should print OK message."""
        self._setup_repo(tmp_path, ["3.12"], "FROM python:3.12-slim")
        check_version_consistency(tmp_path, verbose=True)
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_digest_pinned_dockerfile_matches(self, tmp_path: Path) -> None:
        """Should correctly match when Dockerfile uses digest-pinned FROM."""
        digest = "sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c"
        write_pyproject(tmp_path, ["Programming Language :: Python :: 3.12"])
        write_dockerfile(tmp_path, f"FROM python:3.12-slim@{digest} AS builder")
        assert check_version_consistency(tmp_path) == 0
