#!/usr/bin/env python3
"""Enforce Python version consistency between pyproject.toml and Dockerfile.

Parses the highest ``Programming Language :: Python :: X.Y`` classifier from
``pyproject.toml`` and asserts it matches the major.minor version in the
Dockerfile ``FROM python:X.Y`` line.  Exits 1 if they differ or if either
file is missing or malformed.

Usage:
    python scripts/check_python_version_consistency.py
    python scripts/check_python_version_consistency.py --repo-root /path/to/repo
    python scripts/check_python_version_consistency.py --verbose

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

# Regex to match FROM lines like: FROM python:3.12-slim or FROM python:3.12-slim@sha256:...
_DOCKERFILE_FROM_RE = re.compile(r"^\s*FROM\s+python:(\d+\.\d+)", re.IGNORECASE | re.MULTILINE)

# Regex to extract X.Y from a classifier string
_CLASSIFIER_VERSION_RE = re.compile(r"Programming Language :: Python :: (\d+\.\d+)$")


def get_highest_python_classifier(pyproject_path: Path) -> str:
    """Parse the highest Python X.Y classifier from pyproject.toml.

    Args:
        pyproject_path: Path to ``pyproject.toml``.

    Returns:
        The highest ``"X.Y"`` version string found in classifiers.

    Raises:
        SystemExit: With code 1 if the file is missing, malformed, or has
            no ``Programming Language :: Python :: X.Y`` classifiers.

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

    classifiers: list[str] = data.get("project", {}).get("classifiers", [])

    versions: list[tuple[int, int]] = []
    for classifier in classifiers:
        m = _CLASSIFIER_VERSION_RE.match(classifier.strip())
        if m:
            major, minor = m.group(1).split(".")
            versions.append((int(major), int(minor)))

    if not versions:
        print(
            "ERROR: No 'Programming Language :: Python :: X.Y' classifiers"
            f" found in {pyproject_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    highest = max(versions)
    return f"{highest[0]}.{highest[1]}"


def get_dockerfile_python_version(dockerfile_path: Path) -> str:
    """Parse the Python major.minor version from the first FROM python:X.Y line.

    Args:
        dockerfile_path: Path to the Dockerfile.

    Returns:
        The ``"X.Y"`` version string from the ``FROM python:X.Y`` line.

    Raises:
        SystemExit: With code 1 if the file is missing or has no
            ``FROM python:X.Y`` line.

    """
    if not dockerfile_path.is_file():
        print(f"ERROR: Dockerfile not found: {dockerfile_path}", file=sys.stderr)
        sys.exit(1)

    content = dockerfile_path.read_text()
    m = _DOCKERFILE_FROM_RE.search(content)
    if not m:
        print(
            f"ERROR: No 'FROM python:X.Y' line found in {dockerfile_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    return m.group(1)


def check_version_consistency(repo_root: Path, verbose: bool = False) -> int:
    """Compare Python version in pyproject.toml classifiers vs Dockerfile FROM.

    Args:
        repo_root: Root directory of the repository.
        verbose: If True, print the parsed versions even when they match.

    Returns:
        0 if versions match, 1 if they differ.

    """
    pyproject_path = repo_root / "pyproject.toml"
    dockerfile_path = repo_root / "docker" / "Dockerfile"

    classifier_version = get_highest_python_classifier(pyproject_path)
    dockerfile_version = get_dockerfile_python_version(dockerfile_path)

    if verbose:
        print(f"pyproject.toml highest classifier: Python {classifier_version}")
        print(f"Dockerfile FROM python version:    {dockerfile_version}")

    if classifier_version != dockerfile_version:
        print(
            f"ERROR: Python version mismatch detected:\n"
            f"  pyproject.toml highest classifier: {classifier_version}\n"
            f"  Dockerfile FROM python:            {dockerfile_version}\n"
            f"Update the Dockerfile FROM line or pyproject.toml classifiers so they match.",
            file=sys.stderr,
        )
        return 1

    if verbose:
        print(f"OK: Python version is consistent ({classifier_version})")
    return 0


def main() -> int:
    """CLI entry point for Python version consistency checking.

    Returns:
        Exit code (0 if consistent, 1 if mismatch or parse error).

    """
    parser = argparse.ArgumentParser(
        description="Enforce Python version consistency between pyproject.toml and Dockerfile",
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
