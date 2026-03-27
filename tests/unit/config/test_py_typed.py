"""Test that the scylla package includes a PEP 561 py.typed marker.

The marker file tells type checkers (mypy, pyright, etc.) that the package
ships inline type annotations and should be treated as typed.
"""

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).parents[3]
SCYLLA_PKG = REPO_ROOT / "src" / "scylla"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_py_typed_marker_exists() -> None:
    """src/scylla/py.typed must exist as a file (PEP 561)."""
    marker = SCYLLA_PKG / "py.typed"
    assert marker.is_file(), f"Missing PEP 561 marker: {marker}"


def test_py_typed_in_hatch_build_targets() -> None:
    """py.typed must be listed in hatch wheel force-include so it ships in the wheel."""
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)

    force_include: dict[str, str] = (
        data.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )

    assert "src/scylla/py.typed" in force_include, (
        "src/scylla/py.typed is not in [tool.hatch.build.targets.wheel.force-include]"
    )
