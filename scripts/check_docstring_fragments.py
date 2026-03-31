#!/usr/bin/env python3
"""Check Python docstrings for genuine sentence fragments.

Thin wrapper — delegates to hephaestus.validation.docstrings.main().
Install homericintelligence-hephaestus to use this script.
"""
import sys

from hephaestus.validation.docstrings import main

# Re-export symbols for backwards compatibility with existing tests
from hephaestus.validation.docstrings import (  # noqa: F401
    FragmentFinding,
    format_json,
    format_report,
    scan_file,
    scan_repository,
)

# Backwards-compatible aliases: hephaestus uses public names; Scylla tests
# used the private-prefixed variants.
try:
    from hephaestus.validation.docstrings import is_genuine_fragment as _is_genuine_fragment  # noqa: F401
except ImportError:
    pass

try:
    from hephaestus.validation.docstrings import _is_scylla_file  # noqa: F401
except ImportError:
    # _is_scylla_file is Scylla-specific and not in hephaestus; define a shim
    from pathlib import Path

    def _is_scylla_file(path: Path, root: Path) -> bool:  # type: ignore[misc]
        """Return True if path is a .py file under the src/scylla/ directory."""
        scylla_dir = root / "src" / "scylla"
        return path.suffix == ".py" and path.is_relative_to(scylla_dir)

if __name__ == "__main__":
    sys.exit(main())
