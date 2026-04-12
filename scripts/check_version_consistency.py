#!/usr/bin/env python3
"""Detect version drift between pyproject.toml and pixi.toml.

Parses the ``version`` field from both ``pyproject.toml`` (``[project]`` section)
and ``pixi.toml`` (``[workspace]`` section) and fails if they differ.

Usage:
    python scripts/check_version_consistency.py
    python scripts/check_version_consistency.py --repo-root /path/to/repo
    python scripts/check_version_consistency.py --verbose

Exit codes:
    0: Versions are consistent
    1: Versions differ or a file could not be parsed
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Regex to match version = "X.Y.Z" in the [workspace] section of pixi.toml.
# Anchors to the [workspace] header and captures the first version field that
# follows it (before any subsequent section header).  Using re.DOTALL so that
# [^\[]* can span newlines.
# We use regex instead of a TOML parser to avoid reformatting the file.
_PIXI_VERSION_RE = re.compile(
    r'(?s)\[workspace\][^\[]*?version\s*=\s*"([^"]+)"',
)


def get_pyproject_version(repo_root: Path) -> str:
    """Extract the version string from pyproject.toml [project] section.

    Args:
        repo_root: Root directory of the repository.

    Returns:
        The version string (e.g. ``"0.1.0"``).

    Raises:
        SystemExit: With code 1 if the file is missing, malformed, or has
            no ``version`` field in ``[project]``.

    """
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.is_file():
        print(f"ERROR: pyproject.toml not found: {pyproject_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        print(f"ERROR: Could not parse {pyproject_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    project = data.get("project")
    if project is None:
        print(
            f"ERROR: No [project] section found in {pyproject_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    version = project.get("version")
    if version is None:
        print(
            f"ERROR: No version field in [project] section of {pyproject_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    return str(version)


def get_pixi_version(repo_root: Path) -> str:
    """Extract the version string from pixi.toml [workspace] section.

    Args:
        repo_root: Root directory of the repository.

    Returns:
        The version string (e.g. ``"0.1.0"``).

    Raises:
        SystemExit: With code 1 if the file is missing or has no
            ``version = "..."`` line.

    """
    pixi_path = repo_root / "pixi.toml"
    if not pixi_path.is_file():
        print(f"ERROR: pixi.toml not found: {pixi_path}", file=sys.stderr)
        sys.exit(1)

    content = pixi_path.read_text()
    match = _PIXI_VERSION_RE.search(content)
    if not match:
        print(
            f'ERROR: No version = "..." line found in {pixi_path}',
            file=sys.stderr,
        )
        sys.exit(1)

    return match.group(1)


def check_version_consistency(repo_root: Path, verbose: bool = False) -> int:
    """Compare package version in pyproject.toml vs pixi.toml.

    Args:
        repo_root: Root directory of the repository.
        verbose: If True, print the parsed versions even when they match.

    Returns:
        0 if versions match, 1 if they differ.

    """
    pyproject_version = get_pyproject_version(repo_root)
    pixi_version = get_pixi_version(repo_root)

    if verbose:
        print(f"pyproject.toml version: {pyproject_version}")
        print(f"pixi.toml version:      {pixi_version}")

    if pyproject_version != pixi_version:
        print(
            f"ERROR: Package version mismatch detected:\n"
            f"  pyproject.toml: {pyproject_version}\n"
            f"  pixi.toml:      {pixi_version}\n"
            f"Run: pixi run python scripts/bump_version.py <major|minor|patch>\n"
            f"to update both files atomically.",
            file=sys.stderr,
        )
        return 1

    if verbose:
        print(f"OK: Package version is consistent ({pyproject_version})")
    return 0


def main() -> int:
    """CLI entry point for package version consistency checking.

    Returns:
        Exit code (0 if consistent, 1 if mismatch or parse error).

    """
    parser = argparse.ArgumentParser(
        description="Detect version drift between pyproject.toml and pixi.toml",
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
        help="Print parsed versions even when they match",
    )

    args = parser.parse_args()
    return check_version_consistency(args.repo_root, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
