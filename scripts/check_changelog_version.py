#!/usr/bin/env python3
"""Check that CHANGELOG.md contains an entry for the current version.

Thin wrapper — delegates to hephaestus.git.changelog.check_version_main().
Install homericintelligence-hephaestus to use this script.
"""
import sys
from pathlib import Path

# Import from hephaestus (canonical implementation)
from hephaestus.git.changelog import (
    changelog_has_version as _hephaestus_changelog_has_version,
    check_version_main,
    extract_version_from_pyproject as _hephaestus_extract_version,
)


# Compatibility shims: Scylla's API took repo_root: Path and internally
# appended the filename; hephaestus takes the file path directly.


def extract_version_from_pyproject(repo_root: Path) -> str:
    """Read the ``[project] version`` field from ``pyproject.toml``.

    Args:
        repo_root: Path to the repository root containing ``pyproject.toml``.

    Returns:
        The version string (e.g. ``"0.1.0"``).

    Raises:
        SystemExit: If ``pyproject.toml`` is missing, unreadable, or lacks the key.

    """
    pyproject = repo_root / "pyproject.toml"
    version = _hephaestus_extract_version(pyproject)
    if version is None:
        print(f"ERROR: Could not read version from {pyproject}", file=sys.stderr)
        sys.exit(1)
    return version


def changelog_has_version(repo_root: Path, version: str) -> bool:
    """Check whether CHANGELOG.md contains a header for *version*.

    Args:
        repo_root: Path to the repository root containing ``CHANGELOG.md``.
        version: The version string to search for.

    Returns:
        ``True`` if a matching header is found, ``False`` otherwise.

    Raises:
        SystemExit: If ``CHANGELOG.md`` does not exist.

    """
    changelog = repo_root / "CHANGELOG.md"
    if not changelog.exists():
        print(f"ERROR: CHANGELOG.md not found at {changelog}", file=sys.stderr)
        sys.exit(1)
    return _hephaestus_changelog_has_version(changelog, version)


def main() -> int:
    """Run the CHANGELOG version entry check.

    Returns:
        Exit code: 0 if the check passes, 1 if it fails.

    """
    import argparse

    _REPO_ROOT = Path(__file__).parent.parent

    parser = argparse.ArgumentParser(
        description="Verify CHANGELOG.md contains an entry for the pyproject.toml version",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help="Path to repository root (default: parent of this script)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print passing check details",
    )
    args = parser.parse_args()
    repo_root: Path = args.repo_root

    version = extract_version_from_pyproject(repo_root)

    if changelog_has_version(repo_root, version):
        if args.verbose:
            print(f"PASS: CHANGELOG.md contains entry for version {version}")
        return 0

    print(
        f"CHANGELOG.md has no entry for version {version} "
        f"(expected a '## [{version}]' or '## {version}' header)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
