#!/usr/bin/env python3
"""Validate test coverage against configurable thresholds.

Thin wrapper — delegates to hephaestus.validation.coverage.main().
Install homericintelligence-hephaestus to use this script.
"""
import sys

from hephaestus.validation.coverage import main

# Re-export symbols for backwards compatibility with existing tests
from hephaestus.validation.coverage import (  # noqa: F401
    check_coverage,
    get_module_threshold,
    load_coverage_config,
    parse_coverage_report,
)

if __name__ == "__main__":
    sys.exit(main())
