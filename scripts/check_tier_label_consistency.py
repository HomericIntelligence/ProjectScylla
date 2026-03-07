#!/usr/bin/env python3
"""Enforce tier label consistency in .claude/shared/metrics-definitions.md.

Fails if any known-bad tier label pattern is found, preventing the recurring
regression where tier identifiers (T0-T6) are paired with the wrong tier names.

Tier → canonical name mapping:
  T0=Prompts, T1=Skills, T2=Tooling, T3=Delegation, T4=Hierarchy, T5=Hybrid, T6=Super

Known-bad patterns (tier number paired with wrong tier name):
  Original set:
  - T3.*Tool   (T3 is Delegation, not Tooling/T2)
  - T4.*Deleg  (T4 is Hierarchy, not Delegation/T3)
  - T5.*Hier   (T5 is Hybrid, not Hierarchy/T4)
  - T2.*Skill  (T2 is Tooling, not Skills/T1)

  Reverse/symmetric set (bounded .{0,10} to avoid cross-tier false positives):
  - T2.{0,10}Deleg  (T2 is Tooling, not Delegation/T3)
  - T3.{0,10}Hier   (T3 is Delegation, not Hierarchy/T4)
  - T4.{0,10}Hybrid (T4 is Hierarchy, not Hybrid/T5)
  - T1.{0,10}Tool   (T1 is Skills, not Tooling/T2)
  - T0.{0,10}Skill  (T0 is Prompts, not Skills/T1)
  - T1.{0,10}Prompt (T1 is Skills, not Prompts/T0)
  - T2.{0,10}Prompt (T2 is Tooling, not Prompts/T0)
  - T3.{0,10}Skill  (T3 is Delegation, not Skills/T1)
  - T4.{0,10}Tool   (T4 is Hierarchy, not Tooling/T2)
  - T5.{0,10}Deleg  (T5 is Hybrid, not Delegation/T3)
  - T6.{0,10}Hier   (T6 is Super, not Hierarchy/T4)
  - T6.{0,10}Hybrid (T6 is Super, not Hybrid/T5)
  - T0.{0,10}Tool   (T0 is Prompts, not Tooling/T2)
  - T0.{0,10}Deleg  (T0 is Prompts, not Delegation/T3)
  - T5.{0,10}Skill  (T5 is Hybrid, not Skills/T1)
  - T6.{0,10}Deleg  (T6 is Super, not Delegation/T3)

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
    # Original set
    (r"T3.*Tool", "T3 is Delegation, not Tooling"),
    (r"T4.*Deleg", "T4 is Hierarchy, not Delegation"),
    (r"T5.*Hier", "T5 is Hybrid, not Hierarchy"),
    (r"T2.*Skill", "T2 is Tooling, not Skills"),
    # Reverse/symmetric set (bounded to 10 chars to avoid cross-tier false positives)
    (r"T2.{0,10}Deleg", "T2 is Tooling, not Delegation"),
    (r"T3.{0,10}Hier", "T3 is Delegation, not Hierarchy"),
    (r"T4.{0,10}Hybrid", "T4 is Hierarchy, not Hybrid"),
    (r"T1.{0,10}Tool", "T1 is Skills, not Tooling"),
    (r"T0.{0,10}Skill", "T0 is Prompts, not Skills"),
    (r"T1.{0,10}Prompt", "T1 is Skills, not Prompts"),
    (r"T2.{0,10}Prompt", "T2 is Tooling, not Prompts"),
    (r"T3.{0,10}Skill", "T3 is Delegation, not Skills"),
    (r"T4.{0,10}Tool", "T4 is Hierarchy, not Tooling"),
    (r"T5.{0,10}Deleg", "T5 is Hybrid, not Delegation"),
    (r"T6.{0,10}Hier", "T6 is Super, not Hierarchy"),
    (r"T6.{0,10}Hybrid", "T6 is Super, not Hybrid"),
    (r"T0.{0,10}Tool", "T0 is Prompts, not Tooling"),
    (r"T0.{0,10}Deleg", "T0 is Prompts, not Delegation"),
    (r"T5.{0,10}Skill", "T5 is Hybrid, not Skills"),
    (r"T6.{0,10}Deleg", "T6 is Super, not Delegation"),
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
