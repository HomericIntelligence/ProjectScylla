#!/usr/bin/env python3
"""Enforce that config/defaults.yaml has the expected filename as a pre-commit gate.

Validates that the defaults configuration file is named 'defaults.yaml', catching
accidental misconfiguration (e.g., loading the wrong file entirely).

Usage:
    python scripts/check_defaults_filename.py
    python scripts/check_defaults_filename.py --config-dir config/

Exit codes:
    0: Validation passed
    1: Validation failed
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scylla.config.validation import validate_defaults_filename  # noqa: E402


def main() -> int:
    """Run defaults filename validation."""
    defaults_path = _REPO_ROOT / "config" / "defaults.yaml"

    if not defaults_path.exists():
        print(f"ERROR: defaults config not found: {defaults_path}", file=sys.stderr)
        return 1

    warnings = validate_defaults_filename(defaults_path)
    if warnings:
        for w in warnings:
            print(f"ERROR: {w}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
