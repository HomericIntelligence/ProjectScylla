#!/usr/bin/env python3
"""Enforce package version consistency across pyproject.toml, pixi.toml, and CHANGELOG.md.

Reads the canonical version from ``pyproject.toml`` ``[project].version`` and
validates that:

1. ``pixi.toml`` ``[workspace].version`` matches.
2. ``scylla/__init__.py`` uses ``importlib.metadata`` (not a hardcoded string).
3. ``CHANGELOG.md`` does not reference version numbers higher than the canonical
   version (aspirational versions like ``v2.0.0`` when the project is at ``0.1.0``).

Usage:
    python scripts/check_package_version_consistency.py
    python scripts/check_package_version_consistency.py --repo-root /path/to/repo
    python scripts/check_package_version_consistency.py --verbose

Exit codes:
    0: All version sources are consistent
    1: A mismatch or policy violation was detected
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Regex matching hardcoded ``__version__ = "..."`` assignments.
_HARDCODED_VERSION_RE = re.compile(r'^__version__\s*=\s*["\'][\d.]+["\']', re.MULTILINE)

# Regex matching version-like references in CHANGELOG (e.g., ``v1.5.0``, ``v2.0.0``).
_CHANGELOG_VERSION_REF_RE = re.compile(r"\bv(\d+\.\d+\.\d+)\b")


def _parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Convert a dotted version string to an integer tuple for comparison.

    Args:
        version_str: A version string like ``"0.1.0"`` or ``"2.0.0"``.

    Returns:
        A tuple of integers, e.g. ``(0, 1, 0)``.

    """
    return tuple(int(p) for p in version_str.split("."))


def get_pyproject_version(pyproject_path: Path) -> str:
    """Read the canonical version from ``pyproject.toml`` ``[project].version``.

    Args:
        pyproject_path: Path to ``pyproject.toml``.

    Returns:
        The version string.

    Raises:
        SystemExit: If the file is missing, malformed, or has no version field.

    """
    if not pyproject_path.is_file():
        print(f"ERROR: pyproject.toml not found: {pyproject_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        print(f"ERROR: Could not parse {pyproject_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    version = data.get("project", {}).get("version")
    if not version:
        print(
            f"ERROR: No [project].version found in {pyproject_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    return str(version)


def get_pixi_version(pixi_path: Path) -> str:
    """Read the version from ``pixi.toml`` ``[workspace].version``.

    Args:
        pixi_path: Path to ``pixi.toml``.

    Returns:
        The version string.

    Raises:
        SystemExit: If the file is missing, malformed, or has no version field.

    """
    if not pixi_path.is_file():
        print(f"ERROR: pixi.toml not found: {pixi_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(pixi_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        print(f"ERROR: Could not parse {pixi_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    version = data.get("workspace", {}).get("version")
    if not version:
        print(
            f"ERROR: No [workspace].version found in {pixi_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    return str(version)


def check_init_uses_importlib(init_path: Path) -> bool:
    """Check that ``__init__.py`` uses ``importlib.metadata`` instead of a hardcoded version.

    Args:
        init_path: Path to ``scylla/__init__.py``.

    Returns:
        True if the file uses importlib.metadata, False if it has a hardcoded version.

    """
    if not init_path.is_file():
        print(f"ERROR: __init__.py not found: {init_path}", file=sys.stderr)
        sys.exit(1)

    content = init_path.read_text()
    return not _HARDCODED_VERSION_RE.search(content)


def find_aspirational_versions(changelog_path: Path, canonical_version: str) -> list[str]:
    """Find version references in CHANGELOG.md that exceed the canonical version.

    Args:
        changelog_path: Path to ``CHANGELOG.md``.
        canonical_version: The canonical version from ``pyproject.toml``.

    Returns:
        A list of aspirational version strings found (e.g. ``["v1.5.0", "v2.0.0"]``).

    """
    if not changelog_path.is_file():
        # CHANGELOG.md is optional — no error if missing.
        return []

    content = changelog_path.read_text()
    canonical_tuple = _parse_version_tuple(canonical_version)

    aspirational: list[str] = []
    for match in _CHANGELOG_VERSION_REF_RE.finditer(content):
        ref_version = match.group(1)
        # Skip version references inside URLs (e.g., semver.org/spec/v2.0.0.html)
        start = match.start()
        line_start = content.rfind("\n", 0, start) + 1
        line_end = content.find("\n", start)
        if line_end == -1:
            line_end = len(content)
        line = content[line_start:line_end]
        # Skip if the version appears inside a URL (http:// or https://)
        if re.search(r"https?://\S*" + re.escape(match.group(0)), line):
            continue
        if _parse_version_tuple(ref_version) > canonical_tuple:
            full_ref = f"v{ref_version}"
            if full_ref not in aspirational:
                aspirational.append(full_ref)

    return aspirational


def check_package_version_consistency(repo_root: Path, verbose: bool = False) -> int:
    """Validate package version consistency across all sources.

    Args:
        repo_root: Root directory of the repository.
        verbose: If True, print details even when everything is consistent.

    Returns:
        0 if all sources are consistent, 1 if any mismatch is found.

    """
    pyproject_path = repo_root / "pyproject.toml"
    pixi_path = repo_root / "pixi.toml"
    init_path = repo_root / "scylla" / "__init__.py"
    changelog_path = repo_root / "CHANGELOG.md"

    canonical = get_pyproject_version(pyproject_path)
    errors: list[str] = []

    # Check pixi.toml version matches
    pixi_version = get_pixi_version(pixi_path)
    if pixi_version != canonical:
        errors.append(f"pixi.toml version ({pixi_version}) != pyproject.toml version ({canonical})")
    elif verbose:
        print(f"OK: pixi.toml version matches ({pixi_version})")

    # Check __init__.py uses importlib.metadata
    if not check_init_uses_importlib(init_path):
        errors.append(
            "scylla/__init__.py has a hardcoded __version__ string. "
            "Use importlib.metadata.version() instead."
        )
    elif verbose:
        print("OK: scylla/__init__.py uses importlib.metadata (no hardcoded version)")

    # Check CHANGELOG.md for aspirational version references
    aspirational = find_aspirational_versions(changelog_path, canonical)
    if aspirational:
        refs = ", ".join(aspirational)
        errors.append(
            f"CHANGELOG.md references versions higher than {canonical}: {refs}. "
            "Use [Unreleased] convention instead of aspirational version numbers."
        )
    elif verbose:
        print("OK: CHANGELOG.md has no aspirational version references")

    if errors:
        print("ERROR: Package version inconsistencies detected:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if verbose:
        print(f"OK: All version sources are consistent ({canonical})")
    return 0


def main() -> int:
    """CLI entry point for package version consistency checking.

    Returns:
        Exit code (0 if consistent, 1 if mismatch detected).

    """
    parser = argparse.ArgumentParser(
        description=(
            "Enforce package version consistency across pyproject.toml, pixi.toml, and CHANGELOG.md"
        ),
        epilog="Example: %(prog)s --repo-root /path/to/repo --verbose",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Repository root directory (default: parent of this script's directory)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print details even when versions are consistent",
    )

    args = parser.parse_args()
    return check_package_version_consistency(args.repo_root, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
