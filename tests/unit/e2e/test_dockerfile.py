"""Regression tests for Dockerfile pinning requirements."""

from __future__ import annotations

import re
from pathlib import Path

DOCKERFILE = Path(__file__).parents[3] / "docker" / "Dockerfile"


class TestHatchlingPinned:
    """Tests verifying hatchling is pinned in the Dockerfile — see #1141."""

    def test_hatchling_is_pinned(self) -> None:
        """Hatchling must be pinned with == in the builder stage — see #1141."""
        content = DOCKERFILE.read_text()
        match = re.search(r"pip install.*hatchling([^\n]*)", content)
        assert match is not None, "pip install hatchling line not found in Dockerfile"
        assert "==" in match.group(0), (
            "hatchling must be pinned with == (e.g. hatchling==1.27.0); found unpinned install"
        )

    def test_hatchling_version_format(self) -> None:
        """Hatchling pin must use a valid PEP 440 exact version specifier."""
        content = DOCKERFILE.read_text()
        match = re.search(r'pip install.*["\']?hatchling==(\d+\.\d+\.\d+)["\']?', content)
        assert match is not None, (
            "hatchling must be pinned with a full X.Y.Z version "
            "(e.g. hatchling==1.27.0) in Dockerfile"
        )
        version = match.group(1)
        parts = version.split(".")
        assert len(parts) == 3, f"Expected X.Y.Z version, got: {version}"
        assert all(p.isdigit() for p in parts), f"Version parts must be numeric, got: {version}"
