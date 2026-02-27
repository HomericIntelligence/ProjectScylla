"""Regression tests: pixi.toml PyPI dependencies must have upper version bounds."""

import tomllib
from pathlib import Path

import pytest

# Packages that must have an explicit upper bound (<) in their version constraint.
# These are scientific computing / data libraries where major releases may be breaking.
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

_PIXI_TOML = Path(__file__).parents[3] / "pixi.toml"


def _load_pypi_deps() -> dict[str, str]:
    """Load [pypi-dependencies] from pixi.toml and return {name: version_spec}."""
    with _PIXI_TOML.open("rb") as fh:
        data = tomllib.load(fh)
    raw = data.get("pypi-dependencies", {})
    result: dict[str, str] = {}
    for name, spec in raw.items():
        # path-dependencies are dicts (e.g. scylla = {path = ".", editable = true})
        if isinstance(spec, str):
            result[name] = spec
    return result


class TestPixiTomlExists:
    """Sanity-check that pixi.toml is accessible from the test."""

    def test_pixi_toml_exists(self) -> None:
        """pixi.toml must exist at the project root."""
        assert _PIXI_TOML.exists(), f"pixi.toml not found at {_PIXI_TOML}"

    def test_pypi_dependencies_section_present(self) -> None:
        """pixi.toml must contain a [pypi-dependencies] section."""
        deps = _load_pypi_deps()
        assert len(deps) > 0, "[pypi-dependencies] section is empty or missing"


@pytest.mark.parametrize("package", PACKAGES_REQUIRING_UPPER_BOUND)
class TestUpperBoundsPresent:
    """Each targeted PyPI package must declare an upper bound in pixi.toml."""

    def test_package_is_declared(self, package: str) -> None:
        """Package must appear in [pypi-dependencies]."""
        deps = _load_pypi_deps()
        assert package in deps, (
            f"'{package}' is missing from [pypi-dependencies] in pixi.toml"
        )

    def test_upper_bound_present(self, package: str) -> None:
        """Package version constraint must contain '<' (upper bound)."""
        deps = _load_pypi_deps()
        spec = deps.get(package, "")
        assert "<" in spec, (
            f"'{package}' has no upper bound in pixi.toml (got: {spec!r}). "
            "Add a constraint like '>=x.y,<next-major' to prevent silent breakage."
        )
