#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.git.changelog."""

import sys

from hephaestus.git.changelog import check_version_main as main

if __name__ == "__main__":
    sys.exit(main())
