#!/usr/bin/env python3
"""Add missing docstrings to test methods.

This script automatically adds docstrings to test methods that are missing them,
based on the test method name.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def generate_docstring(method_name: str) -> str:
    """Generate a docstring from a test method name.

    Args:
        method_name: Name of the test method (e.g., 'test_init_default')

    Returns:
        Generated docstring text

    """
    # Remove 'test_' prefix
    name = method_name.replace("test_", "")

    # Convert snake_case to words
    words = name.replace("_", " ")

    # Capitalize first letter
    docstring = words[0].upper() + words[1:] + "."

    return f'"""Test {docstring}"""'


def add_docstrings_to_file(file_path: Path) -> int:
    """Add docstrings to test methods in a file.

    Args:
        file_path: Path to the Python file

    Returns:
        Number of docstrings added

    """
    content = file_path.read_text()
    lines = content.split("\n")
    modified = False
    count = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a test method definition
        match = re.match(r'^(\s+)def (test_\w+)\(', line)
        if match:
            indent = match.group(1)
            method_name = match.group(2)

            # Check if next line is already a docstring
            next_line_idx = i + 1
            if next_line_idx < len(lines):
                next_line = lines[next_line_idx].strip()
                if not (next_line.startswith('"""') or next_line.startswith("'''")):
                    # Add docstring
                    docstring = generate_docstring(method_name)
                    lines.insert(next_line_idx, f"{indent}    {docstring}")
                    modified = True
                    count += 1
                    i += 1  # Skip the newly inserted line

        i += 1

    if modified:
        file_path.write_text("\n".join(lines))

    return count


def main() -> None:
    """Add docstrings to all test files with D102 errors."""
    # Get list of files with D102 errors
    result = subprocess.run(
        ["pixi", "run", "ruff", "check", ".", "--select", "D102"],
        capture_output=True,
        text=True,
    )

    # Extract file paths from ruff output
    files_with_errors: set[Path] = set()
    for line in result.stdout.split("\n"):
        if "-->" in line:
            # Parse line like: "  --> tests/integration/test_orchestrator.py:16:9"
            parts = line.split("-->")
            if len(parts) == 2:
                file_path_str = parts[1].strip().split(":")[0]
                files_with_errors.add(Path(file_path_str))

    print(f"Found {len(files_with_errors)} files with D102 errors")

    total_added = 0
    for file_path in sorted(files_with_errors):
        if file_path.exists():
            count = add_docstrings_to_file(file_path)
            if count > 0:
                print(f"Added {count} docstrings to {file_path}")
                total_added += count

    print(f"\nTotal docstrings added: {total_added}")


if __name__ == "__main__":
    main()
