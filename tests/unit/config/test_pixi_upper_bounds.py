"""Regression test: all key PyPI deps in pixi.toml must have an upper-bound constraint.

This test prevents future PRs from silently removing upper-bound constraints that
guard against accidental breakage on major-version upgrades of scientific libraries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import tomllib

PIXI_TOML = Path(__file__).parents[3] / "pixi.toml"

# Packages in [pypi-dependencies] that must carry an upper-bound constraint.
# Local path deps (e.g., scylla = { path = ".", editable = true }) are excluded.
PACKAGES_REQUIRING_UPPER_BOUND = [
    "matplotlib",
    "numpy",
    "pandas",
    "seaborn",
    "scipy",
    "altair",
    "vl-convert-python",
    "krippendorff",
    "statsmodels",
    "jsonschema",
    "defusedxml",
]


@pytest.fixture(scope="module")
def pypi_deps() -> dict[str, Any]:
    """Load [pypi-dependencies] from pixi.toml."""
    with PIXI_TOML.open("rb") as f:
        data: dict[str, Any] = tomllib.load(f)
    result: dict[str, Any] = data["pypi-dependencies"]
    return result


@pytest.mark.parametrize("package", PACKAGES_REQUIRING_UPPER_BOUND)
def test_package_has_upper_bound(package: str, pypi_deps: dict[str, Any]) -> None:
    """Each named PyPI dependency must include a '<' upper-bound constraint."""
    assert package in pypi_deps, (
        f"{package!r} not found in [pypi-dependencies] of pixi.toml. "
        "Either add it back with an upper-bound constraint or remove it from "
        "PACKAGES_REQUIRING_UPPER_BOUND in this test."
    )
    version_spec = pypi_deps[package]
    assert "<" in version_spec, (
        f"{package!r} has no upper-bound in pixi.toml: {version_spec!r}. "
        "Add a '<next-major>' constraint (e.g. '>=3.8,<4') to prevent silent "
        "breakage when a new major version is released."
    )
