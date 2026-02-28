"""Regression tests for Dockerfile pinning requirements.

Validates that build-critical dependencies are pinned with exact version
specifiers in docker/Dockerfile to ensure reproducible builds — see #1141.
"""

import re
from pathlib import Path

DOCKERFILE = Path(__file__).parents[3] / "docker" / "Dockerfile"


def test_hatchling_is_pinned() -> None:
    """hatchling must be pinned with == in the builder stage — see #1141."""
    content = DOCKERFILE.read_text()
    match = re.search(r"pip install[^\n]*hatchling([^\n]*)", content)
    assert match is not None, "pip install hatchling line not found in Dockerfile"
    assert "==" in match.group(0), (
        "hatchling must be pinned with == (e.g. hatchling==1.29.0); "
        "found unpinned install"
    )
