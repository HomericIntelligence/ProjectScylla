#!/usr/bin/env python3
"""Enforce tests/unit/ mirroring convention.

Fails if any ``test_*.py`` file exists directly under ``tests/unit/``
(depth 1 only).  Test files must live in sub-packages that mirror the
``scylla/`` source layout (e.g. ``tests/unit/metrics/``).

Allowed files at ``tests/unit/`` root: ``__init__.py``, ``conftest.py``.

Usage:
    python scripts/check_unit_test_structure.py
    python scripts/check_unit_test_structure.py --unit-root tests/unit/

Exit codes:
    0: No violations found
    1: One or more violations found
"""

import argparse
import sys
from pathlib import Path

ALLOWED_NAMES = {"__init__.py", "conftest.py"}


def find_violations(unit_root: Path) -> list[Path]:
    """Find test_*.py files placed directly under *unit_root*.

    Args:
        unit_root: Root of the unit test directory to inspect.

    Returns:
        Sorted list of violating file paths.

    """
    return sorted(p for p in unit_root.glob("test_*.py") if p.name not in ALLOWED_NAMES)


def check_unit_test_structure(unit_root: Path) -> int:
    """Check that no test_*.py files exist directly under *unit_root*.

    Args:
        unit_root: Root of the unit test directory to inspect.

    Returns:
        0 if no violations found, 1 otherwise.

    """
    if not unit_root.is_dir():
        print(f"ERROR: Directory not found: {unit_root}", file=sys.stderr)
        return 1

    violations = find_violations(unit_root)
    if violations:
        print(
            "ERROR: test_*.py files found directly under tests/unit/.\n"
            "Move them into the appropriate sub-package (e.g. tests/unit/metrics/).\n"
            "Violation(s):",
            file=sys.stderr,
        )
        for p in violations:
            print(f"  {p}", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    """CLI entry point for unit test structure checking.

    Returns:
        Exit code (0 if clean, 1 if violations found).

    """
    parser = argparse.ArgumentParser(
        description="Enforce tests/unit/ mirroring convention",
        epilog="Example: %(prog)s --unit-root tests/unit/",
    )
    parser.add_argument(
        "--unit-root",
        type=Path,
        default=Path("tests/unit"),
        help="Root of the unit test directory (default: tests/unit)",
    )
    args = parser.parse_args()
    return check_unit_test_structure(args.unit_root)


if __name__ == "__main__":
    sys.exit(main())
