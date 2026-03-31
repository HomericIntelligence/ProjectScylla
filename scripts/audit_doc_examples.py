#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.validation.doc_policy."""

import sys

from hephaestus.validation.doc_policy import main

if __name__ == "__main__":
    sys.exit(main())
