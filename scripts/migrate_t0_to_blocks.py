#!/usr/bin/env python3
"""Migrate T0 test fixtures from duplicated CLAUDE.md files to block-based composition.

This script updates T0 subtest config.yaml files to use the resources.claude_md.blocks
specification, then deletes the duplicated CLAUDE.md files.

Python Justification: Required for filesystem operations, YAML parsing, and regex.

Usage:
    python scripts/migrate_t0_to_blocks.py tests/fixtures/tests/
    python scripts/migrate_t0_to_blocks.py tests/fixtures/tests/ --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


# Block mapping based on directory naming patterns
DIRECTORY_TO_BLOCKS: dict[str, list[str]] = {
    "00-empty": [],
    "01-vanilla": [],
    "02-critical-only": ["B02"],
    "03-full": [f"B{i:02d}" for i in range(1, 19)],  # B01-B18
    "04-minimal": ["B01", "B02"],
    "05-core-seven": [f"B{i:02d}" for i in range(1, 8)],  # B01-B07
}

# Add single-block patterns (06-B01 through 23-B18)
for i in range(1, 19):
    dir_num = 5 + i  # 06, 07, ..., 23
    DIRECTORY_TO_BLOCKS[f"{dir_num:02d}-B{i:02d}"] = [f"B{i:02d}"]


def get_blocks_for_directory(dir_name: str) -> list[str] | None:
    """Get the block list for a directory name.

    Args:
        dir_name: Directory name like "03-full" or "07-B02"

    Returns:
        List of block IDs, or None if directory doesn't match known patterns.
    """
    # Direct match
    if dir_name in DIRECTORY_TO_BLOCKS:
        return DIRECTORY_TO_BLOCKS[dir_name]

    # Try matching BXX pattern for single blocks
    match = re.match(r"^\d{2}-(B\d{2})$", dir_name)
    if match:
        return [match.group(1)]

    return None


def update_config_yaml(config_path: Path, blocks: list[str], dry_run: bool = False) -> bool:
    """Update config.yaml to add resources.claude_md.blocks.

    Args:
        config_path: Path to the config.yaml file
        blocks: List of block IDs to add
        dry_run: If True, don't actually write changes

    Returns:
        True if file was updated (or would be in dry-run), False otherwise.
    """
    if not config_path.exists():
        print(f"  Warning: config.yaml not found at {config_path}")
        return False

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    # Skip if already has resources
    if "resources" in config:
        print(f"  Skipping {config_path} - already has resources")
        return False

    # Add resources section
    if blocks:
        config["resources"] = {"claude_md": {"blocks": blocks}}
    else:
        # Empty blocks means no CLAUDE.md needed (00-empty, 01-vanilla)
        config["resources"] = {"claude_md": {"blocks": []}}

    if not dry_run:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return True


def delete_claude_md(claude_md_path: Path, dry_run: bool = False) -> bool:
    """Delete the CLAUDE.md file.

    Args:
        claude_md_path: Path to the CLAUDE.md file
        dry_run: If True, don't actually delete

    Returns:
        True if file was deleted (or would be in dry-run), False otherwise.
    """
    if not claude_md_path.exists():
        return False

    if not dry_run:
        claude_md_path.unlink()

    return True


def migrate_t0_fixtures(fixtures_dir: Path, dry_run: bool = False) -> dict[str, int]:
    """Migrate all T0 fixtures in the given directory.

    Args:
        fixtures_dir: Path to tests/fixtures/tests/
        dry_run: If True, don't make any changes

    Returns:
        Dictionary with counts of actions taken.
    """
    stats = {
        "tests_processed": 0,
        "configs_updated": 0,
        "files_deleted": 0,
        "skipped": 0,
        "errors": 0,
    }

    if not fixtures_dir.exists():
        print(f"Error: Directory not found: {fixtures_dir}")
        return stats

    # Find all test directories
    test_dirs = sorted(fixtures_dir.glob("test-*"))
    if not test_dirs:
        print(f"No test directories found in {fixtures_dir}")
        return stats

    for test_dir in test_dirs:
        t0_dir = test_dir / "t0"
        if not t0_dir.exists():
            continue

        stats["tests_processed"] += 1
        print(f"\nProcessing {test_dir.name}/t0/")

        # Process each subtest directory
        for subtest_dir in sorted(t0_dir.iterdir()):
            if not subtest_dir.is_dir():
                continue

            dir_name = subtest_dir.name
            blocks = get_blocks_for_directory(dir_name)

            if blocks is None:
                print(f"  Warning: Unknown directory pattern: {dir_name}")
                stats["errors"] += 1
                continue

            config_path = subtest_dir / "config.yaml"
            claude_md_path = subtest_dir / "CLAUDE.md"

            # Update config.yaml
            action = "would update" if dry_run else "updated"
            if update_config_yaml(config_path, blocks, dry_run):
                print(f"  {action} {dir_name}/config.yaml with blocks: {blocks}")
                stats["configs_updated"] += 1
            else:
                stats["skipped"] += 1

            # Delete CLAUDE.md
            action = "would delete" if dry_run else "deleted"
            if delete_claude_md(claude_md_path, dry_run):
                print(f"  {action} {dir_name}/CLAUDE.md")
                stats["files_deleted"] += 1

    return stats


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate T0 fixtures from duplicated CLAUDE.md to block-based composition"
    )
    parser.add_argument(
        "fixtures_dir",
        type=Path,
        help="Path to tests/fixtures/tests/ directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN MODE ===\n")

    stats = migrate_t0_fixtures(args.fixtures_dir, dry_run=args.dry_run)

    print("\n=== Summary ===")
    print(f"Tests processed: {stats['tests_processed']}")
    print(f"Configs updated: {stats['configs_updated']}")
    print(f"Files deleted: {stats['files_deleted']}")
    print(f"Skipped (already migrated): {stats['skipped']}")
    print(f"Errors: {stats['errors']}")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
