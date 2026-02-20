#!/usr/bin/env python3
"""Validate that MYPY_KNOWN_ISSUES.md counts match actual mypy output.

This script runs mypy with all disabled error codes re-enabled, counts violations
per error code, and compares against the documented table in MYPY_KNOWN_ISSUES.md.

Every PR that fixes mypy errors must update MYPY_KNOWN_ISSUES.md. This script
enforces that requirement as a pre-commit hook.

Usage:
    # Validate counts (exits 1 if mismatch)
    python scripts/check_mypy_counts.py

    # Auto-update MYPY_KNOWN_ISSUES.md with actual counts
    python scripts/check_mypy_counts.py --update

    # Check against a custom markdown file
    python scripts/check_mypy_counts.py --md-path path/to/MYPY_KNOWN_ISSUES.md

Exit codes:
    0: Documented counts match actual mypy output
    1: Counts differ (diff printed to stderr)
    2: MYPY_KNOWN_ISSUES.md not found or table not parseable
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Error codes disabled in pyproject.toml [tool.mypy] disable_error_code
# These are the codes we re-enable when running the validation check
DISABLED_ERROR_CODES = [
    "assignment",
    "operator",
    "arg-type",
    "valid-type",
    "index",
    "attr-defined",
    "misc",
    "override",
    "no-redef",
    "exit-return",
    "union-attr",
    "var-annotated",
    "call-arg",
    "return-value",
    "call-overload",
]

# Paths mypy checks (must match pre-commit hook file patterns)
MYPY_PATHS = ["scripts/", "scylla/", "tests/"]

# Regex to extract error code from the end of a mypy error line
# Matches: ... error: Some message  [error-code]
_ERROR_LINE_RE = re.compile(r"\berror:.*\[([a-z][a-z0-9-]*)\]$")

# Regex to parse table rows from MYPY_KNOWN_ISSUES.md
# Matches: | error-code | 42 | description |
# Skips header rows, separator rows, and the Total row
_TABLE_ROW_RE = re.compile(r"^\|\s*([a-z][a-z0-9-]+)\s*\|\s*(\d+)\s*\|")

# Regex to match the Total row for updating
_TOTAL_ROW_RE = re.compile(r"(\|\s*\*\*Total\*\*\s*\|\s*\*\*)\d+(\*\*\s*\|)")


def parse_known_issues_table(md_path: Path) -> dict[str, int]:
    """Parse the error count table from MYPY_KNOWN_ISSUES.md.

    Args:
        md_path: Path to the MYPY_KNOWN_ISSUES.md file.

    Returns:
        Dictionary mapping error code to documented count.

    Raises:
        SystemExit: With code 2 if the file is missing or the table cannot be parsed.

    """
    if not md_path.exists():
        print(
            f"error: {md_path} not found. Create it or run with --update to generate.",
            file=sys.stderr,
        )
        sys.exit(2)

    counts: dict[str, int] = {}
    try:
        content = md_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: Cannot read {md_path}: {e}", file=sys.stderr)
        sys.exit(2)

    for line in content.splitlines():
        match = _TABLE_ROW_RE.match(line)
        if match:
            code = match.group(1)
            count = int(match.group(2))
            counts[code] = count

    if not counts:
        print(
            f"error: No error code table found in {md_path}. "
            "Expected rows matching '| error-code | N | description |'.",
            file=sys.stderr,
        )
        sys.exit(2)

    return counts


def run_mypy_and_count(repo_root: Path) -> dict[str, int]:
    """Run mypy with all disabled error codes re-enabled and count errors by code.

    Args:
        repo_root: Repository root directory (working directory for mypy).

    Returns:
        Dictionary mapping error code to actual violation count.

    """
    cmd = ["pixi", "run", "mypy"] + MYPY_PATHS
    for code in DISABLED_ERROR_CODES:
        cmd += ["--enable-error-code", code]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except FileNotFoundError:
        print("error: 'pixi' not found. Ensure pixi is installed and in PATH.", file=sys.stderr)
        sys.exit(2)

    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        match = _ERROR_LINE_RE.search(line)
        if match:
            code = match.group(1)
            # Only count codes we track (ignore codes from other sources)
            if code in DISABLED_ERROR_CODES:
                counts[code] = counts.get(code, 0) + 1

    return counts


def diff_counts(documented: dict[str, int], actual: dict[str, int]) -> list[str]:
    """Compare documented counts against actual mypy counts.

    Args:
        documented: Error code counts from MYPY_KNOWN_ISSUES.md.
        actual: Error code counts from running mypy.

    Returns:
        List of human-readable mismatch messages. Empty if counts match.

    """
    messages: list[str] = []

    all_codes = sorted(set(documented) | set(actual))
    for code in all_codes:
        doc_count = documented.get(code, 0)
        act_count = actual.get(code, 0)
        if doc_count == act_count:
            continue

        if code not in documented:
            messages.append(
                f"  [{code}]: undocumented in MYPY_KNOWN_ISSUES.md "
                f"(actual: {act_count}) — add a row for this error code"
            )
        elif code not in actual:
            if doc_count > 0:
                messages.append(
                    f"  [{code}]: documented count is {doc_count} but mypy reports 0 "
                    "— update count to 0 or remove the row"
                )
        else:
            messages.append(
                f"  [{code}]: documented={doc_count}, actual={act_count} "
                f"({'↓' if act_count < doc_count else '↑'}{abs(act_count - doc_count)})"
            )

    return messages


def update_table(md_path: Path, actual: dict[str, int]) -> None:
    """Rewrite the count column in MYPY_KNOWN_ISSUES.md to match actual mypy counts.

    Only updates count cells and the Total row. All other content is preserved.

    Args:
        md_path: Path to MYPY_KNOWN_ISSUES.md.
        actual: Actual error counts from mypy (error code → count).

    """
    content = md_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []

    for line in lines:
        # Update data rows
        row_match = _TABLE_ROW_RE.match(line)
        if row_match:
            code = row_match.group(1)
            if code in actual or code in DISABLED_ERROR_CODES:
                new_count = actual.get(code, 0)
                # Replace just the count cell: | code | OLD | rest |
                line = re.sub(
                    r"(\|\s*" + re.escape(code) + r"\s*\|\s*)\d+(\s*\|)",
                    lambda m, c=new_count: f"{m.group(1)}{c}{m.group(2)}",
                    line,
                )
        # Update Total row
        elif _TOTAL_ROW_RE.search(line):
            total = sum(actual.get(c, 0) for c in DISABLED_ERROR_CODES)
            line = _TOTAL_ROW_RE.sub(rf"\g<1>{total}\g<2>", line)

        new_lines.append(line)

    md_path.write_text("".join(new_lines), encoding="utf-8")
    print(f"Updated {md_path} with current mypy counts.")


def main() -> int:
    """CLI entry point for mypy count validation.

    Returns:
        Exit code: 0 (clean), 1 (mismatch), 2 (file/config error).

    """
    parser = argparse.ArgumentParser(
        description="Validate MYPY_KNOWN_ISSUES.md counts against actual mypy output",
        epilog="Run with --update to auto-fix stale counts after fixing type errors.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update MYPY_KNOWN_ISSUES.md with actual mypy counts instead of validating",
    )
    parser.add_argument(
        "--md-path",
        type=Path,
        default=None,
        help="Path to MYPY_KNOWN_ISSUES.md (default: repo root)",
    )
    args = parser.parse_args()

    # Locate repo root and markdown file
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    md_path = args.md_path if args.md_path else repo_root / "MYPY_KNOWN_ISSUES.md"

    if args.update:
        # In update mode: run mypy, then overwrite the table
        print("Running mypy to collect current error counts...")
        actual = run_mypy_and_count(repo_root)
        if not md_path.exists():
            print(
                f"error: {md_path} not found. Create the file first, then re-run --update.",
                file=sys.stderr,
            )
            return 2
        update_table(md_path, actual)
        return 0

    # Validation mode: compare documented vs. actual
    documented = parse_known_issues_table(md_path)
    print("Running mypy to collect current error counts...")
    actual = run_mypy_and_count(repo_root)

    mismatches = diff_counts(documented, actual)
    if mismatches:
        print(
            f"check-mypy-counts: FAIL — {md_path.name} is out of date:",
            file=sys.stderr,
        )
        for msg in mismatches:
            print(msg, file=sys.stderr)
        print(
            "\nFix: run `python scripts/check_mypy_counts.py --update` "
            "and commit the updated MYPY_KNOWN_ISSUES.md.",
            file=sys.stderr,
        )
        return 1

    print(f"check-mypy-counts: OK — {md_path.name} counts match mypy output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
