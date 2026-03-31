#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.markdown.fixer."""

import sys

from hephaestus.markdown.fixer import main

if __name__ == "__main__":
    sys.exit(main())
