#!/usr/bin/env python3
"""Thin wrapper — delegates to hephaestus.automation.planner.main().

This script is kept for backwards compatibility. Use `hephaestus-plan-issues` instead.
"""
import sys

from hephaestus.automation.planner import main

if __name__ == "__main__":
    sys.exit(main())
