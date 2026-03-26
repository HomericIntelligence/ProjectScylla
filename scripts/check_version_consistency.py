"""Check that the version string is consistent across all declaration sites.

Reads the version from:
  1. pyproject.toml  (project.version)
  2. pixi.toml       (workspace.version)
  3. scylla/__init__.py (__version__)

Exits non-zero if any disagree.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _read_toml_version(path: Path, table_key: str) -> str | None:
    """Read a version string from a TOML file without requiring a TOML library.

    Looks for ``version = "..."`` under a ``[<table_key>]`` header.

    Args:
        path: Path to the TOML file.
        table_key: The TOML table header to search under (e.g. "project" or "workspace").

    Returns:
        The version string, or None if not found.

    """
    if not path.exists():
        return None

    text = path.read_text()
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_table = stripped == f"[{table_key}]"
            continue
        if in_table:
            match = re.match(r'^version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    return None


def _read_init_version(path: Path) -> str | None:
    """Read ``__version__`` from a Python file.

    Args:
        path: Path to the Python file (e.g. ``scylla/__init__.py``).

    Returns:
        The version string, or None if not found.

    """
    if not path.exists():
        return None

    text = path.read_text()
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def check_version_consistency(root: Path | None = None) -> int:
    """Check version consistency across declaration sites.

    Args:
        root: Project root directory. Defaults to the repository root
              (parent of the ``scripts/`` directory).

    Returns:
        0 if all versions match, 1 otherwise.

    """
    if root is None:
        root = Path(__file__).resolve().parent.parent

    sources: dict[str, str | None] = {
        "pyproject.toml": _read_toml_version(root / "pyproject.toml", "project"),
        "pixi.toml": _read_toml_version(root / "pixi.toml", "workspace"),
        "scylla/__init__.py": _read_init_version(root / "scylla" / "__init__.py"),
    }

    missing = [name for name, ver in sources.items() if ver is None]
    if missing:
        for name in missing:
            print(f"ERROR: could not read version from {name}")
        return 1

    versions = {name: ver for name, ver in sources.items() if ver is not None}
    unique = set(versions.values())

    if len(unique) == 1:
        version = unique.pop()
        print(f"OK: all version sources agree: {version}")
        return 0

    print("ERROR: version mismatch detected:")
    for name, ver in versions.items():
        print(f"  {name}: {ver}")
    return 1


if __name__ == "__main__":
    sys.exit(check_version_consistency())
