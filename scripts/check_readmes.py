#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.validation.markdown."""

import sys

from hephaestus.validation.markdown import check_readmes_main as main

if __name__ == "__main__":
    sys.exit(main())
