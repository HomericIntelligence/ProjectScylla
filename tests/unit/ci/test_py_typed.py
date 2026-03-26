"""Regression tests ensuring the PEP 561 py.typed marker is shipped correctly.

Validates that:
1. ``scylla/py.typed`` exists on disk.
2. ``pyproject.toml`` force-includes it in wheel builds.
"""

from __future__ import annotations

import sys
from pathlib import Path

# tomllib is built-in for Python 3.11+; fall back to tomli for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_py_typed_marker_exists() -> None:
    """The PEP 561 py.typed marker file must exist on disk."""
    marker = _PROJECT_ROOT / "scylla" / "py.typed"
    assert marker.exists(), f"Missing PEP 561 marker: {marker}"


def test_pyproject_force_includes_py_typed() -> None:
    """pyproject.toml must force-include scylla/py.typed in wheel builds."""
    pyproject = _PROJECT_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    force_include: dict[str, str] = (
        data.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    assert "scylla/py.typed" in force_include, (
        f"scylla/py.typed not in [tool.hatch.build.targets.wheel.force-include]: {force_include}"
    )
