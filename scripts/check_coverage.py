#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.validation.coverage."""

import sys

from hephaestus.validation.coverage import main

if __name__ == "__main__":
    sys.exit(main())
