"""Tests for Dockerfile EXTRAS group name validation.

Ensures the Layer 2 RUN snippet validates EXTRAS group names against
[project.optional-dependencies] in pyproject.toml, emitting a clear error
and exiting non-zero for unknown names. See issue #1204.
"""

import re
import sys
from pathlib import Path

import pytest
import tomllib

DOCKERFILE_PATH = Path(__file__).parents[3] / "docker" / "Dockerfile"
PYPROJECT_PATH = Path(__file__).parents[3] / "pyproject.toml"


def _extract_layer2_run_snippet(dockerfile_content: str) -> str:
    """Extract the Layer 2 RUN python3 -c block from Dockerfile content.

    Searches for the RUN block that contains ``optional-dependencies``, which
    identifies the Layer 2 dependency-extraction snippet. Returns the full
    block including continuation lines.

    Args:
        dockerfile_content: Raw text content of the Dockerfile.

    Returns:
        The matched RUN block as a string, or an empty string if not found.

    """
    # Match a RUN line (with possible continuations via backslash) that contains
    # "optional-dependencies"
    pattern = re.compile(
        r"(RUN python3 -c .*?(?:\\\n.*?)*)\n(?!.*\\)",
        re.DOTALL,
    )
    for match in pattern.finditer(dockerfile_content):
        block = match.group(1)
        if "optional-dependencies" in block:
            return block
    return ""


class TestDockerfileExtrasValidation:
    """Assert Dockerfile Layer 2 snippet validates EXTRAS group names."""

    def test_dockerfile_exists(self) -> None:
        """Dockerfile must exist at docker/Dockerfile."""
        assert DOCKERFILE_PATH.is_file(), (
            f"Dockerfile not found at {DOCKERFILE_PATH}. "
            "Ensure docker/Dockerfile exists in the repository root."
        )

    def test_layer2_snippet_contains_sys_exit(self) -> None:
        """Layer 2 RUN snippet must call sys.exit for invalid EXTRAS groups.

        Without a sys.exit(1) call, unknown group names would be silently
        ignored. This test guards against regression. See issue #1204.
        """
        content = DOCKERFILE_PATH.read_text()
        snippet = _extract_layer2_run_snippet(content)
        assert snippet, (
            "Could not find the Layer 2 python3 -c RUN block in docker/Dockerfile. "
            "Expected a RUN block referencing 'optional-dependencies'."
        )
        assert "sys.exit" in snippet, (
            "Layer 2 RUN snippet does not contain 'sys.exit'. "
            "Unknown EXTRAS groups must trigger sys.exit(1). See issue #1204."
        )

    def test_layer2_snippet_validates_optional_dependencies(self) -> None:
        """Layer 2 RUN snippet must reference 'unknown' for validation logic.

        The validation must compute unknown group names by comparing EXTRAS
        against the valid set from [project.optional-dependencies]. See #1204.
        """
        content = DOCKERFILE_PATH.read_text()
        snippet = _extract_layer2_run_snippet(content)
        assert snippet, "Could not find the Layer 2 python3 -c RUN block in docker/Dockerfile."
        assert "unknown" in snippet, (
            "Layer 2 RUN snippet does not reference 'unknown'. "
            "The validation logic must identify unknown EXTRAS group names. "
            "See issue #1204."
        )

    def test_layer2_snippet_contains_error_message(self) -> None:
        """Layer 2 RUN snippet must emit an 'Unknown EXTRAS group' error message.

        The error message must be clear enough for operators to diagnose typos
        in EXTRAS. See issue #1204.
        """
        content = DOCKERFILE_PATH.read_text()
        assert "Unknown EXTRAS group" in content, (
            "The string 'Unknown EXTRAS group' was not found in docker/Dockerfile. "
            "The Layer 2 validation must emit a clear error message for unknown "
            "EXTRAS group names. See issue #1204."
        )

    def test_layer2_snippet_references_issue_1204(self) -> None:
        """Dockerfile must reference issue #1204 in a comment.

        Acts as a regression guard ensuring the validation added in issue
        #1204 is not accidentally removed without updating the comment.
        """
        content = DOCKERFILE_PATH.read_text()
        assert "#1204" in content, (
            "Issue #1204 reference not found in docker/Dockerfile. "
            "The comment linking to issue #1204 appears to have been removed."
        )


class TestOptionalDependenciesNonEmpty:
    """Regression guard: pyproject.toml optional-dependencies must be non-empty.

    If [project.optional-dependencies] becomes empty, the validation in Layer 2
    would trivially accept any EXTRAS value (nothing to validate against). These
    tests guard against that regression.
    """

    def test_pyproject_has_optional_dependencies(self) -> None:
        """pyproject.toml must define at least one optional-dependency group.

        If optional-dependencies is empty, the Docker EXTRAS validation would
        accept any string without error (nothing to compare against).
        """
        assert PYPROJECT_PATH.is_file(), f"pyproject.toml not found at {PYPROJECT_PATH}."
        with PYPROJECT_PATH.open("rb") as f:
            data = tomllib.load(f)

        opt = data.get("project", {}).get("optional-dependencies", {})
        assert opt, (
            "[project.optional-dependencies] in pyproject.toml is empty or missing. "
            "The Docker EXTRAS validation requires at least one group to be defined."
        )

    @pytest.mark.parametrize("group", ["analysis", "dev"])
    def test_known_groups_are_present(self, group: str) -> None:
        """Known optional-dependency groups must remain defined in pyproject.toml.

        The groups 'analysis' and 'dev' are documented in docker/Dockerfile and
        referenced by users. Their removal would silently break EXTRAS builds.
        """
        with PYPROJECT_PATH.open("rb") as f:
            data = tomllib.load(f)

        opt = data.get("project", {}).get("optional-dependencies", {})
        assert group in opt, (
            f"Optional-dependency group '{group}' not found in pyproject.toml. "
            f"Known groups documented in docker/Dockerfile must remain defined. "
            f"Available groups: {sorted(opt.keys())}"
        )


# tomllib is stdlib since Python 3.11; validate the runtime satisfies this.
_TOMLLIB_MIN = (3, 11)
if sys.version_info < _TOMLLIB_MIN:
    raise RuntimeError(  # pragma: no cover
        f"tomllib requires Python {_TOMLLIB_MIN[0]}.{_TOMLLIB_MIN[1]}+; "
        f"running {sys.version_info.major}.{sys.version_info.minor}"
    )
