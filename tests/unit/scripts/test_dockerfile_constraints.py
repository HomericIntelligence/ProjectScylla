"""Tests for Dockerfile Python version constraints.

Ensures the base image satisfies the Python 3.10+ minimum and that the
dependency-extraction RUN layer uses a tomllib/tomli fallback so it works
on both Python 3.10 and 3.11+. See issues #1138 and #1200.
"""

import re
from pathlib import Path

import pytest

DOCKERFILE_PATH = Path(__file__).parents[3] / "docker" / "Dockerfile"

# Minimum Python version supported by the builder stage (tomli fallback added in #1200)
MIN_PYTHON_VERSION = (3, 10)


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


def _parse_base_image_digest(dockerfile_content: str, image_pattern: str) -> list[str]:
    """Extract SHA256 digest strings from FROM lines matching a given image pattern.

    For each FROM line that references an image matching ``image_pattern``,
    extracts ``@sha256:<64 hex chars>`` and returns the full ``sha256:...`` string.

    Args:
        dockerfile_content: Raw text content of the Dockerfile.
        image_pattern: Regex pattern used to identify the target base image
            (e.g. ``r"python:"`` or ``r"node:"``).

    Returns:
        List of digest strings (e.g. ``["sha256:abc...", "sha256:abc..."]``) found
        on matching FROM lines, in the order they appear.

    """
    digests: list[str] = []
    for line in dockerfile_content.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("FROM"):
            continue
        if not re.search(image_pattern, stripped, re.IGNORECASE):
            continue
        match = re.search(r"@(sha256:[a-f0-9]{64})", stripped, re.IGNORECASE)
        if match:
            digests.append(match.group(1))
    return digests


def _parse_python_base_digests(dockerfile_content: str) -> list[str]:
    """Extract SHA256 digest strings from Python base image FROM lines in a Dockerfile.

    Matches ``@sha256:<64 hex chars>`` on FROM lines that reference a ``python:``
    base image.  Each matched digest is returned as a full ``sha256:...`` string.

    Args:
        dockerfile_content: Raw text content of the Dockerfile.

    Returns:
        List of digest strings (e.g. ``["sha256:abc...", "sha256:abc..."]``) found
        on Python FROM lines, in the order they appear.

    """
    return _parse_base_image_digest(dockerfile_content, r"python:")


class TestDockerfileBaseImageVersion:
    """Assert Dockerfile base image meets Python 3.10+ minimum requirement."""

    def test_dockerfile_exists(self) -> None:
        """Dockerfile must exist at docker/Dockerfile."""
        assert DOCKERFILE_PATH.is_file(), (
            f"Dockerfile not found at {DOCKERFILE_PATH}. "
            "Ensure docker/Dockerfile exists in the repository root."
        )

    def test_base_image_python_version_meets_tomllib_requirement(self) -> None:
        """Every Python base image in the Dockerfile must be >= 3.10.

        The dependency-extraction RUN layer uses a tomllib/tomli fallback
        (tomllib stdlib since 3.11, tomli pre-installed for 3.10). This test
        acts as a regression guard. See issues #1138 and #1200.
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
                "The builder stage requires Python 3.10+ (tomli fallback added in #1200). "
                "See issues #1138 and #1200 and the comment in docker/Dockerfile."
            )

    def test_tomllib_constraint_comment_present(self) -> None:
        """Dockerfile must reference both tomllib and the fallback mechanism.

        This is a regression guard ensuring the tomllib/tomli fallback
        added in issues #1138 and #1200 is not accidentally removed.
        """
        content = DOCKERFILE_PATH.read_text()
        assert "tomllib" in content, (
            "The word 'tomllib' was not found in docker/Dockerfile. "
            "The tomllib/tomli fallback appears to have been removed. "
            "See issues #1138 and #1200."
        )
        assert "tomli" in content, (
            "The word 'tomli' was not found in docker/Dockerfile. "
            "The tomli fallback package for Python 3.10 appears to have been removed. "
            "See issue #1200."
        )

    def test_tomli_fallback_present(self) -> None:
        """Dockerfile must contain the try/except ImportError tomli fallback.

        Verifies that the dependency-extraction RUN layer includes the
        try/except pattern so Python 3.10 environments can fall back to tomli.
        See issue #1200.
        """
        content = DOCKERFILE_PATH.read_text()
        assert "except ImportError:" in content, (
            "No 'except ImportError:' found in docker/Dockerfile. "
            "The tomllib->tomli fallback pattern appears to have been removed. "
            "See issue #1200."
        )
        assert "import tomli as tomllib" in content, (
            "The 'import tomli as tomllib' fallback was not found in docker/Dockerfile. "
            "The Python 3.10 fallback for tomllib appears to have been removed. "
            "See issue #1200."
        )


class TestParsePythonBaseVersions:
    """Unit tests for _parse_python_base_versions helper."""

    def test_single_from_line(self) -> None:
        """Should extract version from a single FROM line."""
        content = "FROM python:3.12-slim AS builder"
        assert _parse_python_base_versions(content) == [(3, 12)]

    def test_multiple_from_lines(self) -> None:
        """Should extract all versions from multiple FROM lines."""
        content = "FROM python:3.12-slim AS builder\nFROM python:3.12-slim\n"
        assert _parse_python_base_versions(content) == [(3, 12), (3, 12)]

    def test_ignores_non_python_from_lines(self) -> None:
        """FROM lines not referencing python images should be ignored."""
        content = "FROM ubuntu:22.04\nFROM python:3.11-slim\n"
        assert _parse_python_base_versions(content) == [(3, 11)]

    def test_ignores_non_from_lines(self) -> None:
        """Non-FROM lines containing 'python' should not be parsed."""
        content = "# python:3.10 would fail here\nFROM python:3.12-slim\nRUN python3 --version\n"
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


class TestDockerfileBaseImageDigestConsistency:
    """Assert all Python base image FROM lines share the same SHA256 digest."""

    def test_all_python_from_lines_have_sha256_digest(self) -> None:
        """Every Python FROM line must carry a SHA256 digest pin.

        A missing digest on any stage means that stage can silently drift to a
        different upstream image without triggering a build failure.  This test
        acts as a regression guard for digest pin removal.
        """
        content = DOCKERFILE_PATH.read_text()
        versions = _parse_python_base_versions(content)
        digests = _parse_python_base_digests(content)

        assert versions, (
            "No Python base image version found in Dockerfile FROM lines. "
            "Expected at least one 'FROM python:X.Y...' statement."
        )
        assert len(digests) == len(versions), (
            f"Expected {len(versions)} SHA256 digest(s) (one per Python FROM line) "
            f"but found {len(digests)}. "
            "Every Python base image FROM line must include a @sha256:<64-hex> pin."
        )
        for digest in digests:
            assert digest, "Empty digest string found — SHA256 pin must be non-empty."

    def test_builder_and_runtime_digests_are_identical(self) -> None:
        """All Python FROM lines must reference the same SHA256 digest.

        If the builder stage is updated to a new digest without updating the
        runtime stage (or vice versa), the two stages silently diverge.  This
        test catches that drift.
        """
        content = DOCKERFILE_PATH.read_text()
        digests = _parse_python_base_digests(content)

        assert len(digests) >= 2, (
            f"Expected at least 2 SHA256 digest pins (builder + runtime) but found {len(digests)}. "
            "Both the builder and runtime FROM lines must include @sha256 pins."
        )
        assert len(set(digests)) == 1, (
            "Python base image SHA256 digests differ between stages: "
            + ", ".join(digests)
            + ". All stages must reference the same digest to avoid drift."
        )


def _parse_node_base_digest(dockerfile_content: str) -> str | None:
    """Extract SHA256 digest from the node base image FROM line.

    Matches ``node:XX-slim@sha256:<64 hex>`` on FROM lines.

    Args:
        dockerfile_content: Raw text content of the Dockerfile.

    Returns:
        The digest string (e.g. ``sha256:abc...``), or ``None`` if not found.

    """
    digests = _parse_base_image_digest(dockerfile_content, r"node:")
    return digests[0] if digests else None


class TestDockerfileNodeImageDigestPin:
    """Assert the node:20-slim FROM line carries a SHA256 digest pin."""

    def test_node_from_line_has_sha256_digest(self) -> None:
        """The node-source stage must carry a SHA256 digest pin.

        Without a digest pin, the node stage can silently drift to a
        different upstream image.  See issues #1542 and #1591.
        """
        content = DOCKERFILE_PATH.read_text()
        digest = _parse_node_base_digest(content)
        assert digest is not None, (
            "No SHA256 digest found on the node:*-slim FROM line in docker/Dockerfile. "
            "The node-source stage must include a @sha256:<64-hex> pin for reproducibility. "
            "See issue #1591."
        )

    def test_node_digest_is_64_hex_chars(self) -> None:
        """The node digest must be a valid 64-character hex string."""
        content = DOCKERFILE_PATH.read_text()
        digest = _parse_node_base_digest(content)
        assert digest is not None, "No node digest found"
        assert re.fullmatch(r"sha256:[a-f0-9]{64}", digest), (
            f"Node digest '{digest}' is not a valid sha256:<64-hex> string."
        )


class TestParseNodeBaseDigest:
    """Unit tests for _parse_node_base_digest helper."""

    _DIGEST = "sha256:" + "a" * 64

    def test_node_from_line_with_digest(self) -> None:
        """Should extract digest from a node FROM line."""
        content = f"FROM node:20-slim@{self._DIGEST} AS node-source"
        assert _parse_node_base_digest(content) == self._DIGEST

    def test_node_from_line_without_digest(self) -> None:
        """Node FROM line without @sha256 should return None."""
        content = "FROM node:20-slim AS node-source"
        assert _parse_node_base_digest(content) is None

    def test_ignores_python_from_lines(self) -> None:
        """FROM lines referencing python images should be ignored."""
        content = f"FROM python:3.12-slim@{self._DIGEST}\nFROM node:20-slim AS node-source"
        assert _parse_node_base_digest(content) is None

    def test_ignores_comment_lines(self) -> None:
        """Comment lines containing node digest should be ignored."""
        content = (
            f"# FROM node:20-slim@{self._DIGEST}\nFROM node:20-slim@{self._DIGEST} AS node-source"
        )
        assert _parse_node_base_digest(content) == self._DIGEST

    def test_empty_dockerfile(self) -> None:
        """Empty Dockerfile should return None."""
        assert _parse_node_base_digest("") is None

    def test_short_hash_not_matched(self) -> None:
        """A hash shorter than 64 hex chars must not be matched."""
        short = "sha256:" + "f" * 63
        content = f"FROM node:20-slim@{short} AS node-source"
        assert _parse_node_base_digest(content) is None


class TestParsePythonBaseDigests:
    """Unit tests for _parse_python_base_digests helper."""

    _DIGEST = "sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c"

    def test_single_from_line_with_digest(self) -> None:
        """Should extract digest from a single Python FROM line."""
        content = f"FROM python:3.12-slim@{self._DIGEST} AS builder"
        assert _parse_python_base_digests(content) == [self._DIGEST]

    def test_multiple_from_lines_same_digest(self) -> None:
        """Should extract the same digest from multiple Python FROM lines."""
        content = (
            f"FROM python:3.12-slim@{self._DIGEST} AS builder\n"
            f"FROM python:3.12-slim@{self._DIGEST}\n"
        )
        assert _parse_python_base_digests(content) == [self._DIGEST, self._DIGEST]

    def test_multiple_from_lines_different_digests(self) -> None:
        """Should return distinct digests when stages differ."""
        digest_b = "sha256:" + "a" * 64
        content = (
            f"FROM python:3.12-slim@{self._DIGEST} AS builder\nFROM python:3.12-slim@{digest_b}\n"
        )
        assert _parse_python_base_digests(content) == [self._DIGEST, digest_b]

    def test_from_line_without_digest(self) -> None:
        """Python FROM line without @sha256 should return an empty list."""
        content = "FROM python:3.12-slim AS builder"
        assert _parse_python_base_digests(content) == []

    def test_ignores_non_python_from_lines(self) -> None:
        """FROM lines not referencing python images should be ignored."""
        content = f"FROM ubuntu:22.04@{self._DIGEST}\nFROM python:3.12-slim@{self._DIGEST}\n"
        assert _parse_python_base_digests(content) == [self._DIGEST]

    def test_ignores_comment_lines(self) -> None:
        """Comment lines containing digest-like strings should be ignored."""
        content = f"# FROM python:3.12-slim@{self._DIGEST}\nFROM python:3.12-slim@{self._DIGEST}\n"
        assert _parse_python_base_digests(content) == [self._DIGEST]

    def test_empty_dockerfile(self) -> None:
        """Empty Dockerfile should return an empty list."""
        assert _parse_python_base_digests("") == []

    def test_short_hash_not_matched(self) -> None:
        """A hash shorter than 64 hex chars must not be matched."""
        short_digest = "sha256:" + "f" * 63  # 63 chars — one short
        content = f"FROM python:3.12-slim@{short_digest} AS builder"
        assert _parse_python_base_digests(content) == []
