"""Filtering utilities for E2E evaluation and reporting.

This module provides functions to filter out test infrastructure files
that should not be counted as agent-generated outputs.
"""


def is_test_config_file(file_path: str) -> bool:
    """Check if a file is part of the test configuration (should be ignored).

    Test config files like CLAUDE.md and .claude/ are set up by the test
    framework, not created by the agent being evaluated.

    Args:
        file_path: Relative file path from workspace root

    Returns:
        True if the file should be ignored in evaluation and reports.

    """
    # Normalize path for comparison
    path = file_path.strip()

    # Ignore CLAUDE.md at root level
    if path == "CLAUDE.md":
        return True

    # Ignore .claude/ directory and all its contents
    return path == ".claude" or path.startswith(".claude/")
