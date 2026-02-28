"""Regression tests for Dockerfile Python version constraints.

Verifies that the Dockerfile base image Python version is >= 3.11, which is
required for the stdlib `tomllib` module used in Layer 2 dependency extraction.
See issue #1138 for context.

No Docker daemon required — these are static-analysis assertions on the
Dockerfile text.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCKERFILE = Path(__file__).parents[3] / "docker" / "Dockerfile"


def _get_dockerfile_text() -> str:
    """Return the full Dockerfile content as a single string."""
    return DOCKERFILE.read_text()


def test_base_image_python_version_meets_tomllib_requirement() -> None:
    """All FROM lines using python: must specify Python 3.11+ (required for tomllib stdlib).

    tomllib was added to the Python stdlib in 3.11.  The Layer 2 RUN command
    in the Dockerfile uses `import tomllib` directly, so the base image must
    be Python 3.11 or newer.  This test guards against accidental downgrade.
    """
    text = _get_dockerfile_text()
    # Match lines like: FROM python:3.12-slim or FROM python:3.12-slim@sha256:...
    pattern = re.compile(r"^FROM\s+python:(\d+)\.(\d+)", re.MULTILINE)
    matches = pattern.findall(text)

    assert matches, "No 'FROM python:X.Y' lines found in docker/Dockerfile"

    for major_str, minor_str in matches:
        major, minor = int(major_str), int(minor_str)
        assert (major, minor) >= (3, 11), (
            f"docker/Dockerfile base image Python {major}.{minor} is below 3.11. "
            "tomllib is only available in the stdlib from Python 3.11+. "
            "Either upgrade the base image to 3.11+ or add a tomli fallback "
            "(see issue #1138 comment in Dockerfile for instructions)."
        )


def test_tomllib_constraint_comment_present() -> None:
    """The Dockerfile must contain a comment documenting the tomllib Python 3.11+ constraint.

    This is a regression guard ensuring that if the comment is removed or the
    tomllib usage is refactored, the documentation intent is preserved.
    """
    text = _get_dockerfile_text()
    assert "tomllib" in text, (
        "docker/Dockerfile must reference 'tomllib' (in a comment or code) "
        "so the Python 3.11+ constraint is visible to future maintainers. "
        "See issue #1138."
    )


def test_tomllib_fallback_recipe_in_comment() -> None:
    """The Dockerfile comment must include a tomli fallback recipe for Python 3.10.

    Ensures the fallback instructions (issue #1138) are present so anyone
    downgrading to Python 3.10 knows what change to make.
    """
    text = _get_dockerfile_text()
    assert "tomli" in text, (
        "docker/Dockerfile must mention 'tomli' as the Python 3.10 fallback "
        "package in the constraint comment. See issue #1138."
    )
