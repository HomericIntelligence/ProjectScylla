#!/usr/bin/env python3
"""Check that README test count documentation matches actual test counts.

Prevents README values like '3,000+ tests' and '129+ test files' from
going stale by comparing documented floors against actual collected counts.

CI fails when:
  - The documented floor exceeds the actual count (README overclaims).
  - The actual count exceeds the documented floor by more than the
    configured tolerance (README is significantly out of date).

Usage:
    python scripts/check_test_counts.py --readme README.md --test-dir tests
    python scripts/check_test_counts.py
        --readme README.md --test-dir tests
        --tolerance-tests 100 --tolerance-files 5
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Regex patterns for parsing README documented values
# ---------------------------------------------------------------------------

# Matches "3,000+" or "3000+" before the word "test" (not "test file")
_RE_TEST_COUNT = re.compile(r"([\d,]+)\+\s*tests(?!\s*file)", re.IGNORECASE)

# Matches "129+" before "test file"
_RE_FILE_COUNT = re.compile(r"([\d,]+)\+\s*test\s*file", re.IGNORECASE)


def _parse_int(raw: str) -> int:
    """Strip commas and convert to int."""
    return int(raw.replace(",", ""))


def parse_readme_counts(readme: Path) -> tuple[int, int]:
    """Return (test_floor, file_floor) parsed from README documented values.

    Searches all occurrences of the patterns and returns the maximum found
    value for each metric, which is the most conservative documented floor.

    Args:
        readme: Path to README.md.

    Returns:
        Tuple of (test_floor, file_floor).

    Raises:
        ValueError: If either count cannot be found in the README.

    """
    text = readme.read_text(encoding="utf-8")

    test_matches = _RE_TEST_COUNT.findall(text)
    file_matches = _RE_FILE_COUNT.findall(text)

    if not test_matches:
        raise ValueError(f"No test count pattern (e.g. '3,000+ tests') found in {readme}")
    if not file_matches:
        raise ValueError(f"No test file count pattern (e.g. '129+ test files') found in {readme}")

    test_floor = max(_parse_int(m) for m in test_matches)
    file_floor = max(_parse_int(m) for m in file_matches)

    return test_floor, file_floor


def collect_actual_counts(
    test_dir: Path,
    pytest_cmd: list[str] | None = None,
) -> tuple[int, int]:
    """Return (actual_tests, actual_files) from the test suite.

    Args:
        test_dir: Root directory for test discovery (e.g. ``tests/``).
        pytest_cmd: pytest executable command list. Defaults to
            ``[sys.executable, "-m", "pytest"]``.

    Returns:
        Tuple of (collected_test_count, test_file_count).

    Raises:
        RuntimeError: If pytest collection fails.

    """
    if pytest_cmd is None:
        pytest_cmd = [sys.executable, "-m", "pytest"]

    # Collect test count via pytest
    result = subprocess.run(
        [*pytest_cmd, str(test_dir), "--collect-only", "-q", "--no-header"],
        capture_output=True,
        text=True,
    )

    # pytest exits with 5 when no tests are collected, 0/1/2 otherwise.
    # Any exit code other than 0 or 5 indicates a collection error.
    if result.returncode not in (0, 1, 5):
        raise RuntimeError(
            f"pytest --collect-only failed (exit {result.returncode}):\n{result.stderr}"
        )

    # The last non-empty line of stdout is like "3257 tests collected in 11s"
    # or "no tests ran" when collection is empty.
    actual_tests = 0
    output = (result.stdout + result.stderr).strip()
    for line in reversed(output.splitlines()):
        line = line.strip()
        m = re.search(r"(\d+)\s+test", line)
        if m:
            actual_tests = int(m.group(1))
            break

    # Count test files using glob
    actual_files = len(list(test_dir.rglob("test_*.py")))

    return actual_tests, actual_files


def check_counts(
    actual: int,
    documented_floor: int,
    tolerance: int,
    label: str,
) -> tuple[bool, str]:
    """Compare actual count against documented floor with tolerance.

    Fails when:
    - actual < documented_floor  (README overclaims)
    - actual > documented_floor + tolerance  (README is too stale)

    Args:
        actual: True collected count.
        documented_floor: The ``N+`` value from README.
        tolerance: Maximum allowed excess above documented_floor.
        label: Human-readable name for the metric (e.g. "tests").

    Returns:
        Tuple of (passed: bool, message: str).

    """
    upper_bound = documented_floor + tolerance

    if actual < documented_floor:
        msg = (
            f"❌ {label}: README documents {documented_floor}+ "
            f"but only {actual} were found (README overclaims by "
            f"{documented_floor - actual})"
        )
        return False, msg

    if actual > upper_bound:
        msg = (
            f"❌ {label}: {actual} found but README only documents "
            f"{documented_floor}+ (gap {actual - documented_floor} > "
            f"tolerance {tolerance}). Update README to {actual}+."
        )
        return False, msg

    msg = (
        f"✅ {label}: {actual} found, README documents {documented_floor}+ "
        f"(within tolerance {tolerance})"
    )
    return True, msg


def main() -> None:
    """Parse args, collect counts, compare, and exit 0/1."""
    parser = argparse.ArgumentParser(
        description="Check README test count documentation against actual counts."
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path("README.md"),
        help="Path to README.md (default: README.md)",
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=Path("tests"),
        help="Root directory for test discovery (default: tests)",
    )
    parser.add_argument(
        "--tolerance-tests",
        type=int,
        default=100,
        help="Max allowed excess of actual tests above documented floor (default: 100)",
    )
    parser.add_argument(
        "--tolerance-files",
        type=int,
        default=5,
        help="Max allowed excess of actual files above documented floor (default: 5)",
    )
    parser.add_argument(
        "--pytest-cmd",
        nargs="+",
        default=None,
        help="pytest command to use (default: sys.executable -m pytest)",
    )
    args = parser.parse_args()

    if not args.readme.exists():
        print(f"❌ README not found: {args.readme}", file=sys.stderr)
        sys.exit(1)

    if not args.test_dir.exists():
        print(f"❌ Test directory not found: {args.test_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse documented floors
    try:
        test_floor, file_floor = parse_readme_counts(args.readme)
    except ValueError as exc:
        print(f"❌ Failed to parse README: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n📋 README documented floors: {test_floor}+ tests, {file_floor}+ files")

    # Collect actual counts
    try:
        actual_tests, actual_files = collect_actual_counts(
            args.test_dir,
            pytest_cmd=args.pytest_cmd,
        )
    except RuntimeError as exc:
        print(f"❌ Collection failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 Actual counts: {actual_tests} tests, {actual_files} files\n")

    # Compare
    tests_ok, tests_msg = check_counts(actual_tests, test_floor, args.tolerance_tests, "tests")
    files_ok, files_msg = check_counts(actual_files, file_floor, args.tolerance_files, "test files")

    print(tests_msg)
    print(files_msg)

    if tests_ok and files_ok:
        print("\n✅ All test count checks passed.")
        sys.exit(0)
    else:
        print("\n❌ Test count check failed. Update README.md to reflect actual counts.")
        sys.exit(1)


if __name__ == "__main__":
    main()
