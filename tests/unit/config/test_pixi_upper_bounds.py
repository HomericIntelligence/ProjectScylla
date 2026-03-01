"""Regression test: all PyPI dependencies in pixi.toml must have upper bounds.

This test guards against unbounded PyPI dependency specs, which can cause
unexpected breakage when a major version is released.
"""

import sys
from pathlib import Path

import pytest

# tomllib is built-in for Python 3.11+; fall back to tomli for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

PIXI_TOML = Path(__file__).parents[3] / "pixi.toml"

# Packages that are exempt from the upper-bound requirement
# (e.g. local editable installs specified as path tables)
_EXEMPT_PACKAGES = frozenset({"scylla"})


def _load_pypi_deps() -> dict[str, object]:
    """Return the merged dict of all pypi-dependency sections from pixi.toml."""
    with PIXI_TOML.open("rb") as fh:
        data = tomllib.load(fh)

    deps: dict[str, object] = {}

    # Top-level [pypi-dependencies]
    deps.update(data.get("pypi-dependencies", {}))

    # Feature-level [feature.<name>.pypi-dependencies]
    for feature in data.get("feature", {}).values():
        deps.update(feature.get("pypi-dependencies", {}))

    return deps


def _has_upper_bound(spec: object) -> bool:
    """Return True if the version spec string contains a '<' upper bound."""
    if not isinstance(spec, str):
        # Table form (e.g. {path = ".", editable = true}) — not a version spec
        return True
    return "<" in spec


def _pypi_packages_without_upper_bound() -> list[str]:
    """Return names of PyPI packages that lack an upper-bound constraint."""
    deps = _load_pypi_deps()
    return [
        name
        for name, spec in deps.items()
        if name not in _EXEMPT_PACKAGES and not _has_upper_bound(spec)
    ]


class TestPixiUpperBounds:
    """All PyPI dependencies in pixi.toml must specify an upper bound (<X)."""

    def test_pixi_toml_exists(self) -> None:
        """Assert that pixi.toml exists at the expected repository root path."""
        assert PIXI_TOML.exists(), f"pixi.toml not found at {PIXI_TOML}"

    @pytest.mark.parametrize(
        "package",
        _pypi_packages_without_upper_bound(),
        # If the list is empty the test is effectively a no-op (pass).
    )
    def test_package_has_upper_bound(self, package: str) -> None:
        """Assert that the given PyPI package spec contains a '<' upper bound."""
        deps = _load_pypi_deps()
        spec = deps[package]
        assert "<" in str(spec), (
            f"PyPI package '{package}' is missing an upper bound in pixi.toml. "
            f"Current spec: {spec!r}. "
            "Add a '<next-major>' constraint to prevent unexpected breakage."
        )

    def test_no_packages_missing_upper_bound(self) -> None:
        """Fail with a clear summary if any packages are missing upper bounds."""
        missing = _pypi_packages_without_upper_bound()
        assert not missing, (
            f"The following PyPI packages in pixi.toml lack upper bounds: "
            f"{missing}. Add '<next-major>' constraints for each."
        )
