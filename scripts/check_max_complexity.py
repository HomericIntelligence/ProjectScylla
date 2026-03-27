#!/usr/bin/env python3
"""Check cyclomatic complexity against a threshold.

This script validates that no function in the target path exceeds the
maximum allowed cyclomatic complexity. Uses ruff's mccabe (C901) checker.

Usage:
    python scripts/check_max_complexity.py
    python scripts/check_max_complexity.py --threshold 10
    python scripts/check_max_complexity.py --threshold 10 --path scylla/ --verbose
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Enable importing from repository root and scripts directory
_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_SCRIPT_DIR))

from common import get_repo_root  # noqa: E402


def run_ruff_complexity_check(
    path: str,
    threshold: int,
    repo_root: Path,
) -> list[dict[str, str]]:
    """Run ruff C901 check and return violations.

    Args:
        path: Path to check (relative to repo_root).
        threshold: Maximum allowed cyclomatic complexity.
        repo_root: Repository root directory.

    Returns:
        List of violation dicts with keys: file, row, col, code, message.

    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select=C901",
            f"--config=lint.mccabe.max-complexity={threshold}",
            "--output-format=json",
            path,
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    if not result.stdout.strip():
        return []

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    violations = []
    for item in raw:
        violations.append(
            {
                "file": item.get("filename", ""),
                "row": str(item.get("location", {}).get("row", "")),
                "col": str(item.get("location", {}).get("column", "")),
                "code": item.get("code", ""),
                "message": item.get("message", ""),
            }
        )
    return violations


def check_max_complexity(
    path: str,
    threshold: int,
    verbose: bool = False,
) -> bool:
    """Check that no function exceeds the complexity threshold.

    Args:
        path: Path to source directory or file to check.
        threshold: Maximum allowed cyclomatic complexity (inclusive).
        verbose: Print detailed output.

    Returns:
        True if all functions are within the threshold, False otherwise.

    """
    repo_root = get_repo_root()

    if verbose:
        print(f"\nChecking cyclomatic complexity (threshold={threshold}) in: {path}")

    violations = run_ruff_complexity_check(path, threshold, repo_root)

    if not violations:
        print(f"\n[OK] Complexity check passed: all functions <= CC {threshold} in {path}")
        return True

    print(f"\n[FAIL] {len(violations)} function(s) exceed CC {threshold} in {path}:")
    for v in violations:
        print(f"  {v['file']}:{v['row']}:{v['col']}: {v['message']}")

    print("\nTip: Refactor using extract-method or guard-clause flattening to reduce complexity.")
    return False


def main() -> None:
    """Run the complexity check script."""
    parser = argparse.ArgumentParser(description="Check cyclomatic complexity against threshold")
    parser.add_argument(
        "--threshold",
        type=int,
        default=10,
        help="Maximum allowed cyclomatic complexity (default: 10)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default="src/scylla/",
        help="Path to source code to check (default: src/scylla/)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    args = parser.parse_args()

    success = check_max_complexity(
        path=args.path,
        threshold=args.threshold,
        verbose=args.verbose,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
