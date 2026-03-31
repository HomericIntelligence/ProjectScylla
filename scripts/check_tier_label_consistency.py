#!/usr/bin/env python3
"""Check tier label consistency in markdown files.

Thin wrapper — delegates to hephaestus.validation.tier_labels.main().
Install homericintelligence-hephaestus>=0.6.0 to use this script.

Note: hephaestus.validation.tier_labels will be available in v0.6.0.
Until then, this wrapper will raise ImportError at runtime.
"""
import sys

from hephaestus.validation.tier_labels import main  # available in hephaestus>=0.6.0

# Re-export symbols for backwards compatibility with existing tests
from hephaestus.validation.tier_labels import (  # noqa: F401
    BAD_PATTERNS,
    TierLabelFinding,
    _collect_mismatches,
    check_tier_label_consistency,
    find_violations,
    format_json,
    format_report,
    scan_repository,
)

if __name__ == "__main__":
    sys.exit(main())
