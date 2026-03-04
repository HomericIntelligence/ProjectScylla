"""Regression tests for Dockerfile pinning requirements."""

from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DOCKERFILE = Path(__file__).parents[3] / "docker" / "Dockerfile"
PYPROJECT_TOML = Path(__file__).parents[3] / "pyproject.toml"


def _parse_hatchling_specifier(requires: list[str]) -> str | None:
    """Return the hatchling specifier string from build-system.requires, or None."""
    for req in requires:
        if req.lower().startswith("hatchling"):
            return req
    return None


def _version_tuple(v: str) -> tuple[int, ...]:
    """Convert '1.29.0' to (1, 29, 0)."""
    return tuple(int(p) for p in v.split("."))


class TestHatchlingPinned:
    """Tests verifying hatchling is pinned in the Dockerfile — see #1141."""

    def test_hatchling_is_pinned(self) -> None:
        """Hatchling must be pinned with == in the builder stage — see #1141."""
        content = DOCKERFILE.read_text()
        match = re.search(r"pip install.*hatchling([^\n]*)", content)
        assert match is not None, "pip install hatchling line not found in Dockerfile"
        assert "==" in match.group(0), (
            "hatchling must be pinned with == (e.g. hatchling==1.29.0); found unpinned install"
        )

    def test_hatchling_version_format(self) -> None:
        """Hatchling pin must use a valid PEP 440 exact version specifier."""
        content = DOCKERFILE.read_text()
        match = re.search(r'pip install.*["\']?hatchling==(\d+\.\d+\.\d+)["\']?', content)
        assert match is not None, (
            "hatchling must be pinned with a full X.Y.Z version "
            "(e.g. hatchling==1.29.0) in Dockerfile"
        )
        version = match.group(1)
        parts = version.split(".")
        assert len(parts) == 3, f"Expected X.Y.Z version, got: {version}"
        assert all(p.isdigit() for p in parts), f"Version parts must be numeric, got: {version}"

    def test_pyproject_hatchling_requirement_parseable(self) -> None:
        """pyproject.toml [build-system].requires must include a hatchling entry."""
        with PYPROJECT_TOML.open("rb") as f:
            data = tomllib.load(f)
        requires: list[str] = data.get("build-system", {}).get("requires", [])
        spec = _parse_hatchling_specifier(requires)
        assert spec is not None, "hatchling not found in [build-system].requires in pyproject.toml"

    def test_hatchling_version_matches_pyproject(self) -> None:
        """Dockerfile hatchling pin must satisfy the constraint in pyproject.toml."""
        with PYPROJECT_TOML.open("rb") as f:
            data = tomllib.load(f)
        requires: list[str] = data.get("build-system", {}).get("requires", [])
        spec = _parse_hatchling_specifier(requires)
        assert spec is not None, "hatchling not in pyproject.toml [build-system].requires"

        content = DOCKERFILE.read_text()
        match = re.search(r"pip install.*?hatchling==(\d+\.\d+\.\d+)", content)
        assert match is not None, "Could not find hatchling==X.Y.Z in Dockerfile"
        pinned = match.group(1)
        pinned_t = _version_tuple(pinned)

        lower_match = re.search(r">=(\d+\.\d+\.\d+)", spec)
        assert lower_match, f"No >= lower bound found in pyproject.toml specifier: {spec!r}"
        lower_t = _version_tuple(lower_match.group(1))

        upper_match = re.search(r"<(\d+(?:\.\d+)*)", spec)
        upper_t = _version_tuple(upper_match.group(1)) if upper_match else None

        assert pinned_t >= lower_t, (
            f"Dockerfile hatchling=={pinned} is below pyproject.toml lower bound "
            f"{lower_match.group(1)} (from {spec!r})"
        )
        if upper_t is not None:
            assert pinned_t < upper_t, (
                f"Dockerfile hatchling=={pinned} violates pyproject.toml upper bound "
                f"(from {spec!r})"
            )


class TestAllStaticPipInstallsPinned:
    """Regression tests ensuring all static pip installs are pinned — see #1209.

    A "static pip install" is any ``RUN pip install <package-name>`` line that
    names a PyPI package literally (not a local path, not a shell-substitution).
    Dynamic installs (e.g. ``pip install $(python3 -c "...")``) are excluded
    because their version constraints come from pyproject.toml.
    Local-path installs (e.g. ``pip install /opt/scylla/``) are also excluded.
    Comment lines are excluded.
    """

    # Regex to find a static RUN pip install line: must start with RUN, must not
    # contain a shell substitution $( or a path-based token.
    _STATIC_PIP_RUN_RE = re.compile(r"^RUN\s+pip\s+install\b")

    def _collect_static_pip_install_lines(self) -> list[str]:
        """Return RUN pip install lines that install named packages statically."""
        content = DOCKERFILE.read_text()
        static_lines: list[str] = []
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            # Must be an actual RUN instruction (not a comment)
            if not self._STATIC_PIP_RUN_RE.match(stripped):
                continue
            # Exclude dynamic shell substitution installs
            if "$(" in stripped:
                continue
            # Exclude local path installs (token starting with / or ./)
            if re.search(r"[\s'](?:/|\./)[\w/.]", stripped):
                continue
            # Exclude continuation lines with no package name (just flags + backslash)
            # i.e. lines that only contain pip install flags and end with backslash
            rest = re.sub(r"\bRUN\s+pip\s+install\b", "", stripped).strip()
            # rest is everything after "pip install"; strip flags
            rest_no_flags = re.sub(r"--\S+", "", rest).strip().rstrip("\\").strip()
            if not rest_no_flags:
                continue
            static_lines.append(stripped)
        return static_lines

    def test_no_unpinned_static_pip_installs(self) -> None:
        """Every static pip install must include an == version pin — see #1209."""
        static_lines = self._collect_static_pip_install_lines()
        assert static_lines, "Expected at least one static pip install line in Dockerfile"
        unpinned: list[str] = []
        for line in static_lines:
            # Extract package tokens after stripping flags (--foo) and the RUN prefix
            rest = re.sub(r"\bRUN\s+pip\s+install\b", "", line).strip()
            rest_no_flags = re.sub(r"--\S+", "", rest).strip()
            # Each remaining token should be a package with ==
            tokens = rest_no_flags.split()
            for token in tokens:
                # Allow quoted tokens like "pkg==1.2.3" or 'pkg==1.2.3'
                token_clean = token.strip("\"'\\")
                if not token_clean:
                    continue
                if "==" not in token_clean:
                    unpinned.append(line)
                    break
        assert not unpinned, (
            "Found static pip install(s) without == pin — see #1209:\n"
            + "\n".join(f"  {ln}" for ln in unpinned)
        )
