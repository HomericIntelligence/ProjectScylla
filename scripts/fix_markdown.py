#!/usr/bin/env python3
"""Fix common markdown linting issues.

Thin wrapper — delegates to hephaestus.markdown.fixer.main().
Install homericintelligence-hephaestus to use this script.
"""
import sys

from hephaestus.markdown.fixer import main

# Re-export MarkdownFixer for backwards compatibility with existing tests.
# Note: hephaestus MarkdownFixer.__init__ takes an optional FixerOptions
# dataclass rather than verbose/dry_run keyword arguments. Tests that call
# MarkdownFixer(verbose=True) or MarkdownFixer(dry_run=True) will need to
# be updated to use FixerOptions.
from hephaestus.markdown.fixer import FixerOptions, MarkdownFixer  # noqa: F401

if __name__ == "__main__":
    sys.exit(main())
