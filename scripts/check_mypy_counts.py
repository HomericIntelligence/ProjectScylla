#!/usr/bin/env python3
"""Validate that MYPY_KNOWN_ISSUES.md counts match actual mypy output.

This script runs mypy in a single invocation over all tracked paths, re-enabling
tests-only suppressed error codes, counts violations per error code, and compares
against the documented table in MYPY_KNOWN_ISSUES.md.

scylla/ and scripts/ are fully compliant (#687) — only tests/ has suppressed codes
(tracked in TESTS_ONLY_ERROR_CODES, suppressed via [[tool.mypy.overrides]], see #940).

Every PR that changes suppressed error counts must update MYPY_KNOWN_ISSUES.md.
This script enforces that requirement as a pre-commit hook.

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

# scylla/ and scripts/ are fully compliant — no globally-disabled error codes remain (#687)
DISABLED_ERROR_CODES: list[str] = []

# Error codes suppressed only in the [[tool.mypy.overrides]] for tests.*
# These have zero violations in scylla/ and scripts/ but non-zero in tests/
TESTS_ONLY_ERROR_CODES = [
    "call-arg",
    "var-annotated",
    "misc",
    "method-assign",
    "union-attr",
]

# All tracked codes (global disabled + tests-only); currently only tests-only remain
ALL_TRACKED_CODES = DISABLED_ERROR_CODES + TESTS_ONLY_ERROR_CODES

# Paths mypy checks (must match pre-commit hook file patterns)
MYPY_PATHS = ["scripts/", "scylla/", "tests/"]

# Regex to extract error code from the end of a mypy error line
# Matches: ... error: Some message  [error-code]
_ERROR_LINE_RE = re.compile(r"\berror:.*\[([a-z][a-z0-9-]*)\]$")

# Regex to extract the file path from the beginning of a mypy error/note line
# Matches: path/to/file.py:123: error: ...
_FILE_PATH_RE = re.compile(r"^([^:]+\.py):\d+")

# Regex to parse table rows from MYPY_KNOWN_ISSUES.md
# Matches: | error-code | 42 | description |
# Skips header rows, separator rows, and the Total row
_TABLE_ROW_RE = re.compile(r"^\|\s*`?([a-z][a-z0-9-]+)`?\s*\|\s*(\d+)\s*\|")

# Regex to match the Total row for updating
_TOTAL_ROW_RE = re.compile(r"(\|\s*\*\*Total\*\*\s*\|\s*\*\*)\d+(\*\*\s*\|)")

# Regex to match per-directory section headings
# Matches: ## Error Count Table — scylla/
_SECTION_HEADING_RE = re.compile(r"^##\s+Error Count Table\s+—\s+(.+?)\s*$")


def parse_known_issues_table(md_path: Path) -> dict[str, int]:
    """Parse the error count table from MYPY_KNOWN_ISSUES.md.

    Supports both the legacy flat format and the new per-directory format.
    In per-directory format, all sections are merged into a single dict
    (for backward compatibility with callers expecting a flat result).

    Args:
        md_path: Path to the MYPY_KNOWN_ISSUES.md file.

    Returns:
        Dictionary mapping error code to documented count (summed across all sections).

    Raises:
        SystemExit: With code 2 if the file is missing or the table cannot be parsed.

    """
    per_dir = parse_known_issues_per_dir(md_path)
    if per_dir:
        # Merge counts across all directories
        merged: dict[str, int] = {}
        for dir_counts in per_dir.values():
            for code, count in dir_counts.items():
                merged[code] = merged.get(code, 0) + count
        return merged

    # Fallback: legacy flat table parse
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


def parse_known_issues_per_dir(md_path: Path) -> dict[str, dict[str, int]]:
    """Parse per-directory error count sections from MYPY_KNOWN_ISSUES.md.

    Looks for sections headed by '## Error Count Table — <dir>/' and parses
    each table within that section.

    Args:
        md_path: Path to the MYPY_KNOWN_ISSUES.md file.

    Returns:
        Dict mapping directory name (e.g. "scylla/") to its error code counts.
        Returns an empty dict if no per-directory sections are found.

    Raises:
        SystemExit: With code 2 if the file is missing or cannot be read.

    """
    if not md_path.exists():
        print(
            f"error: {md_path} not found. Create it or run with --update to generate.",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        content = md_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: Cannot read {md_path}: {e}", file=sys.stderr)
        sys.exit(2)

    result: dict[str, dict[str, int]] = {}
    current_dir: str | None = None

    for line in content.splitlines():
        heading_match = _SECTION_HEADING_RE.match(line)
        if heading_match:
            current_dir = heading_match.group(1)
            result[current_dir] = {}
            continue

        if current_dir is not None:
            row_match = _TABLE_ROW_RE.match(line)
            if row_match:
                code = row_match.group(1)
                count = int(row_match.group(2))
                result[current_dir][code] = count

    return result


def run_mypy_and_count(repo_root: Path) -> dict[str, int]:
    """Run mypy with tracked error codes re-enabled and count errors by code.

    Runs mypy in a single invocation and returns aggregate counts across all paths.

    Args:
        repo_root: Repository root directory (working directory for mypy).

    Returns:
        Dictionary mapping error code to actual violation count.

    """
    counts_per_dir = run_mypy_per_dir(repo_root)
    merged: dict[str, int] = {}
    for dir_counts in counts_per_dir.values():
        for code, count in dir_counts.items():
            merged[code] = merged.get(code, 0) + count
    return merged


def run_mypy_per_dir(repo_root: Path) -> dict[str, dict[str, int]]:
    """Run mypy in a single invocation and partition error counts by directory.

    Runs mypy once over all MYPY_PATHS with TESTS_ONLY_ERROR_CODES re-enabled,
    then partitions output lines by directory prefix. This replaces the previous
    3-invocation approach to cut CI time by ~2/3 (closes #1005).

    Args:
        repo_root: Repository root directory (working directory for mypy).

    Returns:
        Dict mapping directory path (e.g. "tests/") to its error code counts.

    """
    # Build single command covering all paths
    # Enable tests-only codes so they are counted when they appear in tests/
    # (DISABLED_ERROR_CODES is empty — scylla/ and scripts/ are fully compliant)
    all_tracked = set(TESTS_ONLY_ERROR_CODES)

    cmd = ["pixi", "run", "mypy"] + list(MYPY_PATHS)
    for code in TESTS_ONLY_ERROR_CODES:
        cmd += ["--enable-error-code", code]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except FileNotFoundError:
        print("error: 'pixi' not found. Ensure pixi is installed and in PATH.", file=sys.stderr)
        sys.exit(2)

    # Initialize result with empty counts for each directory
    result: dict[str, dict[str, int]] = {path: {} for path in MYPY_PATHS}

    for line in proc.stdout.splitlines():
        file_match = _FILE_PATH_RE.match(line)
        if not file_match:
            continue
        file_path = file_match.group(1)

        # Find which directory this file belongs to
        owning_dir = next((p for p in MYPY_PATHS if file_path.startswith(p)), None)
        if owning_dir is None:
            continue

        error_match = _ERROR_LINE_RE.search(line)
        if error_match:
            code = error_match.group(1)
            if code in all_tracked:
                result[owning_dir][code] = result[owning_dir].get(code, 0) + 1

    return result


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

    Supports both legacy flat format and per-directory section format. In
    per-directory format, counts from ``actual`` are written to the section
    that corresponds to each directory.  For per-directory updates pass
    ``actual`` as the merged aggregate; use ``update_table_per_dir`` to write
    per-directory breakdowns.

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
            if code in actual or code in ALL_TRACKED_CODES:
                new_count = actual.get(code, 0)
                # Replace just the count cell: | code | OLD | rest |
                line = re.sub(
                    r"(\|\s*" + re.escape(code) + r"\s*\|\s*)\d+(\s*\|)",
                    rf"\g<1>{new_count}\g<2>",
                    line,
                )
        # Update Total row
        elif _TOTAL_ROW_RE.search(line):
            total = sum(actual.get(c, 0) for c in ALL_TRACKED_CODES)
            line = _TOTAL_ROW_RE.sub(rf"\g<1>{total}\g<2>", line)

        new_lines.append(line)

    md_path.write_text("".join(new_lines), encoding="utf-8")
    print(f"Updated {md_path} with current mypy counts.")


def update_table_per_dir(md_path: Path, actual_per_dir: dict[str, dict[str, int]]) -> None:
    """Rewrite per-directory sections in MYPY_KNOWN_ISSUES.md.

    For each '## Error Count Table — <dir>/' section, updates count cells and
    the Total row using the counts from ``actual_per_dir[dir]``. Sections not
    present in ``actual_per_dir`` are left unchanged.

    Args:
        md_path: Path to MYPY_KNOWN_ISSUES.md.
        actual_per_dir: Per-directory error counts (dir → error code → count).

    """
    content = md_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    current_dir: str | None = None
    current_actual: dict[str, int] = {}

    for line in lines:
        heading_match = _SECTION_HEADING_RE.match(line)
        if heading_match:
            current_dir = heading_match.group(1)
            current_actual = actual_per_dir.get(current_dir, {})
            new_lines.append(line)
            continue

        row_match = _TABLE_ROW_RE.match(line)
        if row_match and current_dir is not None:
            code = row_match.group(1)
            tracked = ALL_TRACKED_CODES if current_dir == "tests/" else DISABLED_ERROR_CODES
            if code in current_actual or code in tracked:
                new_count = current_actual.get(code, 0)
                line = re.sub(
                    r"(\|\s*" + re.escape(code) + r"\s*\|\s*)\d+(\s*\|)",
                    rf"\g<1>{new_count}\g<2>",
                    line,
                )
        elif _TOTAL_ROW_RE.search(line) and current_dir is not None:
            tracked = ALL_TRACKED_CODES if current_dir == "tests/" else DISABLED_ERROR_CODES
            total = sum(current_actual.get(c, 0) for c in tracked)
            line = _TOTAL_ROW_RE.sub(rf"\g<1>{total}\g<2>", line)

        new_lines.append(line)

    md_path.write_text("".join(new_lines), encoding="utf-8")
    print(f"Updated {md_path} with per-directory mypy counts.")


def main() -> int:  # noqa: C901  # CLI entry point with update/validate modes and per-dir/flat fallback
    """CLI entry point for mypy count validation.

    Returns:
        Exit code: 0 (clean or --strict with only decreases), 1 (mismatch), 2 (file/config error).

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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Only fail on count increases (regressions); treat decreases as warnings.",
    )
    args = parser.parse_args()

    # Locate repo root and markdown file
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    md_path = args.md_path if args.md_path else repo_root / "MYPY_KNOWN_ISSUES.md"

    if args.update:
        # In update mode: run mypy per directory, then overwrite the table
        print("Running mypy to collect current error counts...")
        actual_per_dir = run_mypy_per_dir(repo_root)
        if not md_path.exists():
            print(
                f"error: {md_path} not found. Create the file first, then re-run --update.",
                file=sys.stderr,
            )
            return 2

        # Use per-directory update if sections exist, otherwise flat update
        existing_per_dir = parse_known_issues_per_dir(md_path)
        if existing_per_dir:
            update_table_per_dir(md_path, actual_per_dir)
        else:
            # Legacy flat update: merge all dirs into one dict
            merged: dict[str, int] = {}
            for dir_counts in actual_per_dir.values():
                for code, count in dir_counts.items():
                    merged[code] = merged.get(code, 0) + count
            update_table(md_path, merged)
        return 0

    # Validation mode: compare documented vs. actual
    per_dir_documented = parse_known_issues_per_dir(md_path)

    print("Running mypy to collect current error counts...")
    actual_per_dir = run_mypy_per_dir(repo_root)

    if per_dir_documented:
        # Per-directory validation
        all_mismatches: list[str] = []
        for directory in MYPY_PATHS:
            documented = per_dir_documented.get(directory, {})
            actual = actual_per_dir.get(directory, {})
            mismatches = diff_counts(documented, actual)
            if mismatches:
                all_mismatches.append(f"  {directory}:")
                all_mismatches.extend(f"  {m}" for m in mismatches)

        if all_mismatches:
            if args.strict:
                regressions = [m for m in all_mismatches if "↑" in m]
                warnings = [m for m in all_mismatches if "↓" in m]
                if warnings:
                    print(
                        f"check-mypy-counts: WARNING — {md_path.name} has improved counts "
                        "(run --update to sync):"
                    )
                    for msg in warnings:
                        print(msg)
                if regressions:
                    print(
                        f"check-mypy-counts: FAIL — {md_path.name} is out of date:",
                        file=sys.stderr,
                    )
                    for msg in regressions:
                        print(msg, file=sys.stderr)
                    print(
                        "\nFix: run `python scripts/check_mypy_counts.py --update` "
                        "and commit the updated MYPY_KNOWN_ISSUES.md.",
                        file=sys.stderr,
                    )
                    return 1
            else:
                print(
                    f"check-mypy-counts: FAIL — {md_path.name} is out of date:",
                    file=sys.stderr,
                )
                for msg in all_mismatches:
                    print(msg, file=sys.stderr)
                print(
                    "\nFix: run `python scripts/check_mypy_counts.py --update` "
                    "and commit the updated MYPY_KNOWN_ISSUES.md.",
                    file=sys.stderr,
                )
                return 1

        print(f"check-mypy-counts: OK — {md_path.name} counts match mypy output.")
        return 0

    # Legacy flat validation
    documented_flat = parse_known_issues_table(md_path)
    merged_actual: dict[str, int] = {}
    for dir_counts in actual_per_dir.values():
        for code, count in dir_counts.items():
            merged_actual[code] = merged_actual.get(code, 0) + count

    mismatches = diff_counts(documented_flat, merged_actual)
    if mismatches:
        if args.strict:
            regressions = [m for m in mismatches if "↑" in m]
            warnings = [m for m in mismatches if "↓" in m]
            if warnings:
                print(
                    f"check-mypy-counts: WARNING — {md_path.name} has improved counts "
                    "(run --update to sync):"
                )
                for msg in warnings:
                    print(msg)
            if regressions:
                print(
                    f"check-mypy-counts: FAIL — {md_path.name} is out of date:",
                    file=sys.stderr,
                )
                for msg in regressions:
                    print(msg, file=sys.stderr)
                print(
                    "\nFix: run `python scripts/check_mypy_counts.py --update` "
                    "and commit the updated MYPY_KNOWN_ISSUES.md.",
                    file=sys.stderr,
                )
                return 1
        else:
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
