#!/usr/bin/env python3
"""Enforce tier label consistency in .claude/shared/metrics-definitions.md.

Fails if any known-bad tier label pattern is found, preventing the recurring
regression where tier identifiers (T0-T6) are paired with the wrong tier names.

Known-bad patterns (tier number paired with wrong tier name):
  - T3.*Tool   (T3 is Delegation, not Tooling/T2)
  - T4.*Deleg  (T4 is Hierarchy, not Delegation/T3)
  - T5.*Hier   (T5 is Hybrid, not Hierarchy/T4)
  - T2.*Skill  (T2 is Tooling, not Skills/T1)

Usage:
    python scripts/check_tier_label_consistency.py
    python scripts/check_tier_label_consistency.py --file .claude/shared/metrics-definitions.md

Exit codes:
    0: No violations found
    1: One or more violations found
"""

import argparse
import re
import sys
from pathlib import Path

DEFAULT_TARGET = Path(".claude/shared/metrics-definitions.md")

BAD_PATTERNS: list[tuple[str, str]] = [
    (r"T3.*Tool", "T3 is Delegation, not Tooling"),
    (r"T4.*Deleg", "T4 is Hierarchy, not Delegation"),
    (r"T5.*Hier", "T5 is Hybrid, not Hierarchy"),
    (r"T2.*Skill", "T2 is Tooling, not Skills"),
]


def find_violations(content: str) -> list[tuple[int, str, str, str]]:
    """Find lines matching known-bad tier label patterns.

    Args:
        content: Text content to scan.

    Returns:
        List of (line_number, line_text, pattern, reason) tuples for each match.

    """
    violations: list[tuple[int, str, str, str]] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for pattern, reason in BAD_PATTERNS:
            if re.search(pattern, line):
                violations.append((lineno, line, pattern, reason))
    return violations


def check_tier_label_consistency(target: Path) -> int:
    """Check *target* for known-bad tier label patterns.

    Args:
        target: Path to the markdown file to inspect.

    Returns:
        0 if no violations found, 1 otherwise.

    """
    if not target.is_file():
        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 1

    content = target.read_text(encoding="utf-8")
    violations = find_violations(content)

    if violations:
        print(
            f"ERROR: Found {len(violations)} tier label mismatch(es) in {target}:",
            file=sys.stderr,
        )
        for lineno, line, pattern, reason in violations:
            print(f"  Line {lineno}: {line.rstrip()}", file=sys.stderr)
            print(f"    Pattern: {pattern!r} — {reason}", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    """CLI entry point for tier label consistency checking.

    Returns:
        Exit code (0 if clean, 1 if violations found).

    """
    parser = argparse.ArgumentParser(
        description="Enforce tier label consistency in metrics-definitions.md",
        epilog="Example: %(prog)s --file .claude/shared/metrics-definitions.md",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Markdown file to check (default: {DEFAULT_TARGET})",
    )
    args = parser.parse_args()
    return check_tier_label_consistency(args.file)


if __name__ == "__main__":
    sys.exit(main())
