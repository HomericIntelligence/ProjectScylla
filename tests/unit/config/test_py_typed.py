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
    """py.typed must be covered by the hatch wheel packages config so it ships in the wheel.

    Hatchling automatically includes py.typed when the package directory is listed in
    [tool.hatch.build.targets.wheel] packages — no force-include entry is needed.
    """
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)

    wheel: dict[str, object] = (
        data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {})
    )

    packages: list[str] = wheel.get("packages", [])  # type: ignore[assignment]

    assert any("scylla" in pkg for pkg in packages), (
        "src/scylla is not listed in [tool.hatch.build.targets.wheel] packages — "
        "py.typed will not be included in the wheel"
    )
