#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.validation.docstrings."""

import sys

from hephaestus.validation.docstrings import main

if __name__ == "__main__":
    sys.exit(main())
