"""Tests for Dockerfile Python version constraints.

Ensures the base image satisfies the Python 3.11+ requirement imposed by
the use of tomllib (stdlib since Python 3.11) in the dependency-extraction
RUN layer. See issue #1138.
"""

import re
from pathlib import Path

import pytest

DOCKERFILE_PATH = Path(__file__).parents[3] / "docker" / "Dockerfile"

# Minimum Python version required for tomllib (stdlib since 3.11)
MIN_PYTHON_VERSION = (3, 11)


def _parse_python_base_versions(dockerfile_content: str) -> list[tuple[int, int]]:
    """Extract Python version tuples from all FROM lines in a Dockerfile.

    Matches patterns like ``python:3.12-slim`` or ``python:3.11.0-slim``,
    returning a list of ``(major, minor)`` tuples for each FROM line that
    references a Python base image.

    Args:
        dockerfile_content: Raw text content of the Dockerfile.

    Returns:
        List of (major, minor) version tuples found in FROM lines.
    """
    versions: list[tuple[int, int]] = []
    for line in dockerfile_content.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("FROM"):
            continue
        match = re.search(r"python:(\d+)\.(\d+)", stripped, re.IGNORECASE)
        if match:
            versions.append((int(match.group(1)), int(match.group(2))))
    return versions


class TestDockerfileBaseImageVersion:
    """Assert Dockerfile base image meets Python 3.11+ requirement."""

    def test_dockerfile_exists(self) -> None:
        """Dockerfile must exist at docker/Dockerfile."""
        assert DOCKERFILE_PATH.is_file(), (
            f"Dockerfile not found at {DOCKERFILE_PATH}. "
            "Ensure docker/Dockerfile exists in the repository root."
        )

    def test_base_image_python_version_meets_tomllib_requirement(self) -> None:
        """Every Python base image in the Dockerfile must be >= 3.11.

        tomllib is only available in the Python stdlib from 3.11 onwards. If
        the base image is downgraded to 3.10 the dependency-extraction RUN
        layer will fail with ModuleNotFoundError. This test acts as a
        regression guard. See issue #1138.
        """
        content = DOCKERFILE_PATH.read_text()
        versions = _parse_python_base_versions(content)

        assert versions, (
            "No Python base image version found in Dockerfile FROM lines. "
            "Expected at least one 'FROM python:X.Y...' statement."
        )

        for major, minor in versions:
            assert (major, minor) >= MIN_PYTHON_VERSION, (
                f"Dockerfile base image python:{major}.{minor} is below the "
                f"minimum required version {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}. "
                "tomllib is only available in the Python stdlib from 3.11+. "
                "Either keep the base image at 3.11+ or add a tomli fallback "
                "(see issue #1138 and the comment in docker/Dockerfile)."
            )

    def test_tomllib_constraint_comment_present(self) -> None:
        """Dockerfile must contain the tomllib constraint comment.

        This is a regression guard ensuring the constraint documentation
        added in issue #1138 is not accidentally removed.
        """
        content = DOCKERFILE_PATH.read_text()
        assert "tomllib" in content, (
            "The word 'tomllib' was not found in docker/Dockerfile. "
            "The constraint comment documenting the Python 3.11+ requirement "
            "appears to have been removed. See issue #1138."
        )
        assert "#1138" in content, (
            "Issue #1138 reference not found in docker/Dockerfile. "
            "The constraint comment linking to issue #1138 appears to have "
            "been removed."
        )


class TestParsePythonBaseVersions:
    """Unit tests for _parse_python_base_versions helper."""

    def test_single_from_line(self) -> None:
        """Should extract version from a single FROM line."""
        content = "FROM python:3.12-slim AS builder"
        assert _parse_python_base_versions(content) == [(3, 12)]

    def test_multiple_from_lines(self) -> None:
        """Should extract all versions from multiple FROM lines."""
        content = (
            "FROM python:3.12-slim AS builder\n"
            "FROM python:3.12-slim\n"
        )
        assert _parse_python_base_versions(content) == [(3, 12), (3, 12)]

    def test_ignores_non_python_from_lines(self) -> None:
        """FROM lines not referencing python images should be ignored."""
        content = (
            "FROM ubuntu:22.04\n"
            "FROM python:3.11-slim\n"
        )
        assert _parse_python_base_versions(content) == [(3, 11)]

    def test_ignores_non_from_lines(self) -> None:
        """Non-FROM lines containing 'python' should not be parsed."""
        content = (
            "# python:3.10 would fail here\n"
            "FROM python:3.12-slim\n"
            "RUN python3 --version\n"
        )
        assert _parse_python_base_versions(content) == [(3, 12)]

    def test_sha256_pinned_image(self) -> None:
        """Should extract version from SHA256-pinned FROM line."""
        content = (
            "FROM python:3.12-slim"
            "@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c\n"
        )
        assert _parse_python_base_versions(content) == [(3, 12)]

    def test_empty_dockerfile(self) -> None:
        """Empty Dockerfile should return empty list."""
        assert _parse_python_base_versions("") == []

    @pytest.mark.parametrize(
        "version_str,expected",
        [
            ("python:3.10-slim", (3, 10)),
            ("python:3.11-slim", (3, 11)),
            ("python:3.12-slim", (3, 12)),
            ("python:3.13-slim", (3, 13)),
            ("python:3.11.0-slim", (3, 11)),
        ],
    )
    def test_various_versions(self, version_str: str, expected: tuple[int, int]) -> None:
        """Should parse various version string formats correctly."""
        content = f"FROM {version_str}"
        assert _parse_python_base_versions(content) == [expected]
