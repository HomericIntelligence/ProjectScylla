#!/usr/bin/env python3
"""Verify CHANGELOG.md contains an entry matching the version in pyproject.toml.

Checks that CHANGELOG.md has a ``## [X.Y.Z]`` or ``## X.Y.Z`` header matching
the ``[project] version`` field in ``pyproject.toml``.  This prevents releasing
without documenting changes.

Usage:
    python scripts/check_changelog_version.py
    python scripts/check_changelog_version.py --repo-root /path/to/repo
    python scripts/check_changelog_version.py --verbose

Exit codes:
    0: CHANGELOG.md contains a matching version entry
    1: Version entry missing or files unreadable
"""

import argparse
import re
import sys
from pathlib import Path

import tomllib

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


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
    if not pyproject.exists():
        print(f"ERROR: pyproject.toml not found at {pyproject}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        print(f"ERROR: Failed to parse pyproject.toml: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        version: str = data["project"]["version"]
    except KeyError:
        print(
            "ERROR: [project].version not found in pyproject.toml",
            file=sys.stderr,
        )
        sys.exit(1)

    return version


def changelog_has_version(repo_root: Path, version: str) -> bool:
    """Check whether CHANGELOG.md contains a header for *version*.

    Scans for ``## [X.Y.Z]`` (Keep a Changelog format) or ``## X.Y.Z``
    (without brackets) anywhere in the file.

    Args:
        repo_root: Path to the repository root containing ``CHANGELOG.md``.
        version: The version string to search for (e.g. ``"0.1.0"``).

    Returns:
        ``True`` if a matching header is found, ``False`` otherwise.

    Raises:
        SystemExit: If ``CHANGELOG.md`` does not exist.

    """
    changelog = repo_root / "CHANGELOG.md"
    if not changelog.exists():
        print(f"ERROR: CHANGELOG.md not found at {changelog}", file=sys.stderr)
        sys.exit(1)

    text = changelog.read_text(encoding="utf-8")

    # Match "## [0.1.0]" with optional trailing content (date, link, etc.)
    # or "## 0.1.0" without brackets.
    # Use (?:\s|$) instead of \b because \b after ']' requires a word char.
    escaped = re.escape(version)
    pattern = rf"^##\s+(?:\[{escaped}\]|{escaped})(?:\s|$)"
    return bool(re.search(pattern, text, re.MULTILINE))


def main() -> int:
    """Run the CHANGELOG version entry check.

    Returns:
        Exit code: 0 if the check passes, 1 if it fails.

    """
    parser = argparse.ArgumentParser(
        description="Verify CHANGELOG.md contains an entry for the pyproject.toml version",
        epilog="Example: %(prog)s --repo-root /path/to/repo",
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
