#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.automation.implementer.main().

This script is kept for backwards compatibility. Use `hephaestus-implement-issues` instead.
"""
import sys

from hephaestus.automation.implementer import main

if __name__ == "__main__":
    sys.exit(main())
