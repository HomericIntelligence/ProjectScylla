#!/usr/bin/env python3
"""Migrate subtest config.yaml files from per-test directories to shared centralized location.

This script:
1. Verifies that shared/subtests/ already has the canonical configs
2. Deletes the per-test tier directories (t0/, t1/, t2/, t3/, t4/, t5/, t6/)
3. Keeps test-specific files (test.yaml, config.yaml, expected/, prompt.md, etc.)

Python Justification: Required for filesystem operations.

Usage:
    python scripts/migrate_subtests_to_shared.py tests/fixtures/tests/
    python scripts/migrate_subtests_to_shared.py tests/fixtures/tests/ --dry-run
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


# Tier directories to remove (these are now loaded from shared/subtests/)
TIER_DIRS = ["t0", "t1", "t2", "t3", "t4", "t5", "t6"]

# Files/dirs to keep at test level (not delete)
KEEP_AT_TEST_LEVEL = {
    "test.yaml",
    "config.yaml",
    "expected",
    "prompt.md",
    ".gitkeep",
}


def verify_shared_subtests(shared_dir: Path) -> dict[str, int]:
    """Verify that shared subtests directory has configs.

    Args:
        shared_dir: Path to tests/claude-code/shared/subtests/

    Returns:
        Dictionary mapping tier name to count of subtests.
    """
    counts = {}
    for tier in TIER_DIRS:
        tier_dir = shared_dir / tier
        if tier_dir.exists():
            counts[tier] = len(list(tier_dir.glob("*.yaml")))
        else:
            counts[tier] = 0
    return counts


def delete_tier_directories(test_dir: Path, dry_run: bool = False) -> dict[str, int]:
    """Delete tier directories from a test directory.

    Args:
        test_dir: Path to a test directory (e.g., tests/fixtures/tests/test-001/)
        dry_run: If True, don't actually delete

    Returns:
        Dictionary with counts: dirs_deleted, files_deleted
    """
    stats = {"dirs_deleted": 0, "files_deleted": 0}

    for tier in TIER_DIRS:
        tier_dir = test_dir / tier
        if not tier_dir.exists():
            continue

        # Count files recursively
        for f in tier_dir.rglob("*"):
            if f.is_file():
                stats["files_deleted"] += 1

        stats["dirs_deleted"] += 1

        if not dry_run:
            shutil.rmtree(tier_dir)

    return stats


def migrate_fixtures(fixtures_dir: Path, shared_subtests_dir: Path, dry_run: bool = False) -> dict[str, int]:
    """Migrate all test fixtures.

    Args:
        fixtures_dir: Path to tests/fixtures/tests/
        shared_subtests_dir: Path to tests/claude-code/shared/subtests/
        dry_run: If True, don't make any changes

    Returns:
        Dictionary with counts of actions taken.
    """
    stats = {
        "tests_processed": 0,
        "tier_dirs_deleted": 0,
        "files_deleted": 0,
        "errors": 0,
    }

    if not fixtures_dir.exists():
        print(f"Error: Directory not found: {fixtures_dir}")
        stats["errors"] += 1
        return stats

    # Verify shared subtests exist
    print("Verifying shared subtests directory...")
    shared_counts = verify_shared_subtests(shared_subtests_dir)
    total_shared = sum(shared_counts.values())

    if total_shared == 0:
        print(f"Error: No shared subtests found in {shared_subtests_dir}")
        print("Run the following first to create shared subtests:")
        print("  mkdir -p tests/claude-code/shared/subtests/t{0,1,2,3,4,5,6}")
        print("  # Copy configs from test-001")
        stats["errors"] += 1
        return stats

    print(f"Found {total_shared} shared subtest configs:")
    for tier, count in sorted(shared_counts.items()):
        print(f"  {tier}: {count} subtests")

    # Find all test directories
    test_dirs = sorted(fixtures_dir.glob("test-*"))
    if not test_dirs:
        print(f"No test directories found in {fixtures_dir}")
        return stats

    print(f"\nProcessing {len(test_dirs)} test directories...")

    for test_dir in test_dirs:
        stats["tests_processed"] += 1

        action = "would delete" if dry_run else "deleting"
        tier_stats = delete_tier_directories(test_dir, dry_run)

        if tier_stats["dirs_deleted"] > 0:
            print(f"  {test_dir.name}: {action} {tier_stats['dirs_deleted']} tier dirs, "
                  f"{tier_stats['files_deleted']} files")
            stats["tier_dirs_deleted"] += tier_stats["dirs_deleted"]
            stats["files_deleted"] += tier_stats["files_deleted"]

    return stats


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate subtest configs from per-test to shared centralized location"
    )
    parser.add_argument(
        "fixtures_dir",
        type=Path,
        help="Path to tests/fixtures/tests/ directory",
    )
    parser.add_argument(
        "--shared-dir",
        type=Path,
        default=None,
        help="Path to shared subtests directory (default: auto-detected)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    # Auto-detect shared directory
    if args.shared_dir:
        shared_subtests_dir = args.shared_dir
    else:
        # Navigate from fixtures_dir to shared/subtests
        # fixtures_dir = tests/fixtures/tests/
        # shared = tests/claude-code/shared/subtests/
        shared_subtests_dir = args.fixtures_dir.parent.parent / "claude-code" / "shared" / "subtests"

    if args.dry_run:
        print("=== DRY RUN MODE ===\n")

    print(f"Fixtures directory: {args.fixtures_dir}")
    print(f"Shared subtests directory: {shared_subtests_dir}\n")

    stats = migrate_fixtures(args.fixtures_dir, shared_subtests_dir, dry_run=args.dry_run)

    print("\n=== Summary ===")
    print(f"Tests processed: {stats['tests_processed']}")
    print(f"Tier directories deleted: {stats['tier_dirs_deleted']}")
    print(f"Files deleted: {stats['files_deleted']}")
    print(f"Errors: {stats['errors']}")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
