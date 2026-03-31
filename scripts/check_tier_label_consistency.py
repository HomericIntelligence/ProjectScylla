#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.validation.tier_labels."""

import sys

from hephaestus.validation.tier_labels import main

if __name__ == "__main__":
    sys.exit(main())
