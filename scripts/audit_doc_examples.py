#!/usr/bin/env python3
"""Audit documentation command examples for policy violations.

Thin wrapper — delegates to hephaestus.validation.doc_policy.main().
Install homericintelligence-hephaestus>=0.6.0 to use this script.

Note: hephaestus.validation.doc_policy will be available in v0.6.0.
Until then, this wrapper will raise ImportError at runtime.
"""
import sys

from hephaestus.validation.doc_policy import main  # available in hephaestus>=0.6.0

# Re-export symbols for backwards compatibility with existing tests
from hephaestus.validation.doc_policy import (  # noqa: F401, E402
    Finding,
    Severity,
    _extract_code_blocks,
    format_json_report,
    format_text_report,
    scan_file,
    scan_repository,
)

if __name__ == "__main__":
    sys.exit(main())
