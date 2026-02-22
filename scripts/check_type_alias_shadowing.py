#!/usr/bin/env python3
"""Detect type alias shadowing patterns in Python code.

This script detects anti-patterns where a type alias shadows a more specific
domain name, making code less explicit and harder to understand.

Examples of flagged patterns:
    Result = DomainResult  # ❌ Generic name shadows specific domain name
    RunResult = ExecutorRunResult  # ❌ Removes domain context
    Statistics = AggregatedStatistics  # ❌ Hides aggregation context

Examples of allowed patterns:
    AggregatedStats = Statistics  # ✅ Different name, legitimate abbreviation
    Result = MetricsResult  # ✅ Not a suffix relationship
    # type: ignore[shadowing]  # ✅ Explicit opt-out for rare legitimate cases

Usage:
    # Check specific files
    python scripts/check_type_alias_shadowing.py scylla/metrics/aggregator.py

    # Check all Python files
    python scripts/check_type_alias_shadowing.py scylla/ tests/ scripts/

    # As pre-commit hook (configured in .pre-commit-config.yaml)
    pre-commit run check-type-alias-shadowing --all-files

Exit codes:
    0: No violations found
    1: One or more violations found
"""

import argparse
import re
import sys
from pathlib import Path


def is_shadowing_pattern(alias: str, target: str) -> bool:
    """Check if alias name shadows the target name.

    A shadowing pattern occurs when the alias name is a suffix of the target name,
    indicating that we're removing meaningful context.

    Args:
        alias: The alias name (left side of assignment)
        target: The target name (right side of assignment)

    Returns:
        True if the alias shadows the target, False otherwise

    Examples:
        >>> is_shadowing_pattern("Result", "DomainResult")
        True
        >>> is_shadowing_pattern("RunResult", "ExecutorRunResult")
        True
        >>> is_shadowing_pattern("AggregatedStats", "Statistics")
        False
        >>> is_shadowing_pattern("Result", "MetricsResult")
        False

    """
    # Case-insensitive suffix check
    target_lower = target.lower()
    alias_lower = alias.lower()

    # Must be a proper suffix (not equal, and must end with alias)
    if target_lower == alias_lower:
        return False

    return target_lower.endswith(alias_lower)


def detect_shadowing(file_path: Path) -> list[tuple[int, str, str, str]]:  # noqa: C901  # AST traversal with multiple node types
    """Find type alias shadowing violations in a Python file.

    Args:
        file_path: Path to Python file to check

    Returns:
        List of tuples (line_number, line_content, alias, target) for each violation

    Examples:
        >>> from pathlib import Path
        >>> violations = detect_shadowing(Path("scylla/metrics/aggregator.py"))
        >>> len(violations)  # Number of violations found
        0

    """
    violations = []

    # Pattern matches: Alias = Target
    # Where both are valid Python identifiers (PascalCase for type names)
    pattern = re.compile(r"^([A-Z][a-zA-Z0-9_]*)\s*=\s*([A-Z][a-zA-Z0-9_]*)\s*(?:#.*)?$")

    try:
        with open(file_path, encoding="utf-8") as f:
            in_string = False
            string_delimiter = None

            for line_num, line in enumerate(f, start=1):
                # Track triple-quoted strings (docstrings and multi-line strings)
                stripped = line.strip()
                if '"""' in stripped or "'''" in stripped:
                    # Count triple quotes to determine if we're entering/exiting a string
                    triple_double = stripped.count('"""')
                    triple_single = stripped.count("'''")

                    if triple_double > 0:
                        if in_string and string_delimiter == '"""':
                            in_string = False
                            string_delimiter = None
                        elif not in_string:
                            in_string = True
                            string_delimiter = '"""'
                    elif triple_single > 0:
                        if in_string and string_delimiter == "'''":
                            in_string = False
                            string_delimiter = None
                        elif not in_string:
                            in_string = True
                            string_delimiter = "'''"

                # Skip lines inside multi-line strings
                if in_string:
                    continue

                # Skip lines with opt-out comment
                if "# type: ignore[shadowing]" in line or "# noqa: shadowing" in line:
                    continue

                # Match type alias pattern
                match = pattern.match(stripped)
                if match:
                    alias = match.group(1)
                    target = match.group(2)

                    # Check if this is a shadowing pattern
                    if is_shadowing_pattern(alias, target):
                        violations.append((line_num, stripped, alias, target))

    except (OSError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def format_error(file_path: Path, line_num: int, line: str, alias: str, target: str) -> str:
    """Format a violation as an error message.

    Args:
        file_path: Path to file containing violation
        line_num: Line number of violation
        line: Full line content
        alias: Alias name
        target: Target name

    Returns:
        Formatted error message string

    """
    return (
        f"{file_path}:{line_num}: Type alias shadows domain-specific name\n"
        f"  {line}\n"
        f"  Suggestion: Use '{target}' directly instead of aliasing to '{alias}'\n"
        f"  To suppress this check, add: # type: ignore[shadowing]"
    )


def check_files(file_paths: list[Path]) -> int:
    """Check multiple files for type alias shadowing.

    Args:
        file_paths: List of file or directory paths to check

    Returns:
        Exit code (0 if clean, 1 if violations found)

    """
    all_violations = []

    # Expand directories to Python files
    files_to_check = []
    for path in file_paths:
        if path.is_dir():
            files_to_check.extend(path.rglob("*.py"))
        elif path.suffix == ".py":
            files_to_check.append(path)

    # Check each file
    for file_path in files_to_check:
        violations = detect_shadowing(file_path)
        for line_num, line, alias, target in violations:
            error_msg = format_error(file_path, line_num, line, alias, target)
            all_violations.append(error_msg)

    # Print all violations
    if all_violations:
        print("\n".join(all_violations), file=sys.stderr)
        print(
            f"\nFound {len(all_violations)} type alias shadowing violation(s)",
            file=sys.stderr,
        )
        return 1

    return 0


def main() -> int:
    """CLI entry point for type alias shadowing detection.

    Returns:
        Exit code (0 if clean, 1 if violations found)

    """
    parser = argparse.ArgumentParser(
        description="Detect type alias shadowing patterns in Python code",
        epilog="Example: %(prog)s scylla/ tests/ scripts/",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories to check",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        print(f"Checking {len(args.paths)} path(s) for type alias shadowing...")

    return check_files(args.paths)


if __name__ == "__main__":
    sys.exit(main())
