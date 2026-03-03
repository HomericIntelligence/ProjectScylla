#!/usr/bin/env python3
"""Enforce consistency between documentation metric values and authoritative config sources.

Checks:
1. Coverage threshold in CLAUDE.md matches ``fail_under`` in ``pyproject.toml``.
2. ``--cov=<path>`` in README.md matches ``addopts`` in ``pyproject.toml``.
3. ``--cov-fail-under=N`` in ``addopts`` matches ``fail_under`` in ``[tool.coverage.report]``.
4. Test count in README.md is within 10% of actual pytest collect count.

Usage:
    python scripts/check_doc_config_consistency.py
    python scripts/check_doc_config_consistency.py --repo-root /path/to/repo
    python scripts/check_doc_config_consistency.py --verbose

Exit codes:
    0: All checks pass
    1: One or more checks failed
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import tomllib

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def load_pyproject_coverage_threshold(repo_root: Path) -> int:
    """Read ``fail_under`` from ``[tool.coverage.report]`` in ``pyproject.toml``.

    Args:
        repo_root: Path to the repository root containing ``pyproject.toml``.

    Returns:
        The integer value of ``fail_under``.

    Raises:
        SystemExit: If ``pyproject.toml`` is missing, unreadable, or lacks the key.

    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        print(f"ERROR: pyproject.toml not found at {pyproject}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        print(f"ERROR: Failed to parse pyproject.toml: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        threshold = data["tool"]["coverage"]["report"]["fail_under"]
    except KeyError:
        print(
            "ERROR: [tool.coverage.report].fail_under not found in pyproject.toml",
            file=sys.stderr,
        )
        sys.exit(1)

    return int(threshold)


def extract_cov_path_from_pyproject(repo_root: Path) -> str:
    """Read the ``--cov=<path>`` value from ``[tool.pytest.ini_options].addopts``.

    Args:
        repo_root: Path to the repository root containing ``pyproject.toml``.

    Returns:
        The package path string (e.g. ``"scylla"``).

    Raises:
        SystemExit: If the key is missing or no ``--cov=`` flag is found.

    """
    pyproject = repo_root / "pyproject.toml"
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        print(f"ERROR: Failed to parse pyproject.toml: {exc}", file=sys.stderr)
        sys.exit(1)

    addopts = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", [])

    # addopts may be a list or a string
    if isinstance(addopts, str):
        addopts_items: list[str] = addopts.split()
    else:
        addopts_items = list(addopts)

    for item in addopts_items:
        m = re.match(r"^--cov=(.+)$", item)
        if m:
            return m.group(1)

    print(
        "ERROR: No --cov=<path> found in [tool.pytest.ini_options].addopts in pyproject.toml",
        file=sys.stderr,
    )
    sys.exit(1)


def check_claude_md_threshold(repo_root: Path, expected_threshold: int) -> list[str]:
    """Check that CLAUDE.md documents the correct coverage threshold.

    Searches for the pattern ``<N>%+ test coverage`` in CLAUDE.md and verifies
    the integer ``<N>`` matches *expected_threshold*.

    Args:
        repo_root: Path to the repository root.
        expected_threshold: The authoritative threshold value from ``pyproject.toml``.

    Returns:
        List of error strings (empty if all checks pass).

    """
    claude_md = repo_root / "CLAUDE.md"
    if not claude_md.exists():
        return [f"CLAUDE.md not found at {claude_md}"]

    text = claude_md.read_text(encoding="utf-8")
    # Match patterns like "75%+ test coverage" or "75% test coverage"
    matches = re.findall(r"(\d+)%\+?\s+test coverage", text)

    if not matches:
        return [
            "CLAUDE.md: No coverage threshold mention found "
            "(expected pattern: '<N>%+ test coverage')"
        ]

    errors: list[str] = []
    for raw in matches:
        found = int(raw)
        if found != expected_threshold:
            errors.append(
                f"CLAUDE.md: Coverage threshold mismatch — "
                f"CLAUDE.md says {found}%, pyproject.toml says {expected_threshold}%"
            )
    return errors


def check_readme_cov_path(repo_root: Path, expected_path: str) -> list[str]:
    """Check that all ``--cov=<path>`` occurrences in README.md match *expected_path*.

    Args:
        repo_root: Path to the repository root.
        expected_path: The authoritative ``--cov`` path from ``pyproject.toml``.

    Returns:
        List of error strings (empty if all checks pass).

    """
    readme = repo_root / "README.md"
    if not readme.exists():
        return [f"README.md not found at {readme}"]

    text = readme.read_text(encoding="utf-8")
    occurrences = re.findall(r"--cov=(\S+)", text)

    if not occurrences:
        # No --cov= in README is acceptable — nothing to validate
        return []

    errors: list[str] = []
    for path in occurrences:
        if path != expected_path:
            errors.append(
                f"README.md: --cov path mismatch — "
                f"README.md has '--cov={path}', pyproject.toml uses '--cov={expected_path}'"
            )
    return errors


def extract_cov_fail_under_from_addopts(repo_root: Path) -> int | None:
    """Read the ``--cov-fail-under=N`` value from ``[tool.pytest.ini_options].addopts``.

    Args:
        repo_root: Path to the repository root containing ``pyproject.toml``.

    Returns:
        The integer threshold if a ``--cov-fail-under=N`` flag is present, or ``None``
        if no such flag exists in *addopts*.

    Raises:
        SystemExit: If ``pyproject.toml`` is missing or unreadable.

    """
    pyproject = repo_root / "pyproject.toml"
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        print(f"ERROR: Failed to parse pyproject.toml: {exc}", file=sys.stderr)
        sys.exit(1)

    addopts = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", [])

    if isinstance(addopts, str):
        addopts_items: list[str] = addopts.split()
    else:
        addopts_items = list(addopts)

    for item in addopts_items:
        m = re.match(r"^--cov-fail-under=(\d+)$", item)
        if m:
            return int(m.group(1))

    return None


def check_addopts_cov_fail_under(repo_root: Path, expected_threshold: int) -> list[str]:
    """Check that ``--cov-fail-under`` in ``addopts`` matches ``fail_under`` in coverage report.

    Reads ``--cov-fail-under=N`` from ``[tool.pytest.ini_options].addopts`` and compares it
    to *expected_threshold* (from ``[tool.coverage.report].fail_under``).

    Args:
        repo_root: Path to the repository root.
        expected_threshold: The authoritative threshold from ``[tool.coverage.report].fail_under``.

    Returns:
        List of error strings (empty if all checks pass).

    """
    addopts_threshold = extract_cov_fail_under_from_addopts(repo_root)

    if addopts_threshold is None:
        return [
            "pyproject.toml: No --cov-fail-under=N flag found in [tool.pytest.ini_options].addopts"
        ]

    if addopts_threshold != expected_threshold:
        return [
            f"pyproject.toml: --cov-fail-under mismatch — "
            f"[tool.pytest.ini_options].addopts has --cov-fail-under={addopts_threshold}, "
            f"but [tool.coverage.report].fail_under={expected_threshold}"
        ]

    return []


def collect_actual_test_count(repo_root: Path) -> int | None:
    """Run ``pytest --collect-only -q`` and return the number of collected tests.

    Args:
        repo_root: Path to the repository root where pytest should be invoked.

    Returns:
        The integer test count if collection succeeds and is parseable, or ``None``
        if pytest is unavailable or the output cannot be parsed.

    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None

    output = result.stdout + result.stderr
    # Match "N selected" or "N tests collected" or "N test collected"
    m = re.search(r"(\d+)\s+(?:tests?\s+)?(?:selected|collected)", output)
    if m:
        count = int(m.group(1))
        return count if count > 0 else None
    return None


def check_readme_test_count(
    repo_root: Path, actual_count: int, tolerance: float = 0.10
) -> list[str]:
    """Check that test count claims in README.md are within *tolerance* of *actual_count*.

    Searches README.md for patterns like ``3,500+ tests`` or ``3172 tests`` and flags
    any documented count that differs from *actual_count* by more than *tolerance* (10%).

    Args:
        repo_root: Path to the repository root.
        actual_count: The authoritative test count from ``pytest --collect-only``.
        tolerance: Fractional tolerance (default 0.10 = 10%).

    Returns:
        List of error strings (empty if all checks pass).

    """
    readme = repo_root / "README.md"
    if not readme.exists():
        return [f"README.md not found at {readme}"]

    text = readme.read_text(encoding="utf-8")
    raw_matches = re.findall(r"(\d[\d,]*)\+?\s+tests?", text, re.IGNORECASE)

    if not raw_matches:
        return ["README.md: No test count mention found (expected pattern: '<N> tests')"]

    errors: list[str] = []
    for raw in raw_matches:
        doc_count = int(raw.replace(",", ""))
        if abs(doc_count - actual_count) / actual_count > tolerance:
            errors.append(
                f"README.md: Test count mismatch — "
                f"README.md says {doc_count}, actual pytest count is {actual_count} "
                f"(tolerance: {int(tolerance * 100)}%)"
            )
    return errors


def main() -> int:
    """Run all doc/config consistency checks.

    Returns:
        Exit code: 0 if all checks pass, 1 if any fail.

    """
    parser = argparse.ArgumentParser(
        description="Enforce consistency between doc metric values and pyproject.toml",
        epilog="Example: %(prog)s --repo-root /path/to/repo",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help="Path to repository root (default: parent of this script)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print passing check names",
    )
    args = parser.parse_args()
    repo_root: Path = args.repo_root

    all_errors: list[str] = []

    # --- Check 1: Coverage threshold ---
    expected_threshold = load_pyproject_coverage_threshold(repo_root)
    threshold_errors = check_claude_md_threshold(repo_root, expected_threshold)
    if threshold_errors:
        all_errors.extend(threshold_errors)
    elif args.verbose:
        print(f"PASS: CLAUDE.md coverage threshold matches pyproject.toml ({expected_threshold}%)")

    # --- Check 2: --cov path ---
    expected_cov_path = extract_cov_path_from_pyproject(repo_root)
    cov_errors = check_readme_cov_path(repo_root, expected_cov_path)
    if cov_errors:
        all_errors.extend(cov_errors)
    elif args.verbose:
        print(f"PASS: README.md --cov path matches pyproject.toml (--cov={expected_cov_path})")

    # --- Check 3: --cov-fail-under in addopts matches [tool.coverage.report].fail_under ---
    addopts_errors = check_addopts_cov_fail_under(repo_root, expected_threshold)
    if addopts_errors:
        all_errors.extend(addopts_errors)
    elif args.verbose:
        print(
            f"PASS: [tool.pytest.ini_options].addopts --cov-fail-under matches "
            f"[tool.coverage.report].fail_under ({expected_threshold}%)"
        )

    # --- Check 4: README.md test count ---
    actual_count = collect_actual_test_count(repo_root)
    if actual_count is None:
        if args.verbose:
            print("SKIP: Could not collect actual test count (pytest unavailable)")
    else:
        count_errors = check_readme_test_count(repo_root, actual_count)
        if count_errors:
            all_errors.extend(count_errors)
        elif args.verbose:
            print(f"PASS: README.md test count is within 10% of actual ({actual_count})")

    if all_errors:
        for error in all_errors:
            print(error, file=sys.stderr)
        print(
            f"\nFound {len(all_errors)} doc/config consistency violation(s).",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
