#!/usr/bin/env python3
"""Migrate test fixtures from file duplication to symlink-based resource specs.

This script analyzes existing .claude/ directories in test fixtures, determines
which shared resources they contain, and updates config.yaml with a resources
section. The duplicated files can then be removed.

Usage:
    python scripts/migrate_to_symlinks.py --dry-run
    python scripts/migrate_to_symlinks.py --execute
    python scripts/migrate_to_symlinks.py --execute --test test-001  # Single test

Python Justification: Required for filesystem operations, YAML manipulation,
and complex path matching logic.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "tests"
SHARED_DIR = PROJECT_ROOT / "tests" / "claude-code" / "shared"


def build_skill_category_map() -> dict[str, str]:
    """Build mapping of skill name -> category from shared directory.

    Returns:
        Dict mapping skill directory name to its category.

    """
    skill_map = {}
    skills_dir = SHARED_DIR / "skills"

    if not skills_dir.exists():
        return skill_map

    for category_dir in skills_dir.iterdir():
        if category_dir.is_dir():
            category = category_dir.name
            for skill in category_dir.iterdir():
                if skill.is_dir():
                    skill_map[skill.name] = category

    return skill_map


def build_agent_level_map() -> dict[str, int]:
    """Build mapping of agent filename -> level from shared directory.

    Returns:
        Dict mapping agent filename to its level (0-5).

    """
    agent_map = {}
    agents_dir = SHARED_DIR / "agents"

    if not agents_dir.exists():
        return agent_map

    for level_dir in agents_dir.iterdir():
        if level_dir.is_dir() and level_dir.name.startswith("L"):
            try:
                level = int(level_dir.name[1:])
            except ValueError:
                continue

            for agent in level_dir.iterdir():
                if agent.is_file() and agent.suffix == ".md":
                    agent_map[agent.name] = level

    return agent_map


def analyze_subtest(
    subtest_dir: Path,
    skill_map: dict[str, str],
    agent_map: dict[str, int],
) -> dict:
    """Analyze .claude/ directory to determine resource specification.

    Args:
        subtest_dir: Path to the subtest directory
        skill_map: Mapping of skill name to category
        agent_map: Mapping of agent filename to level

    Returns:
        Resource specification dict for config.yaml

    """
    resources: dict = {}
    claude_dir = subtest_dir / ".claude"

    if not claude_dir.exists():
        return resources

    # Analyze skills
    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        categories = set()
        for skill in skills_dir.iterdir():
            if skill.is_dir():
                category = skill_map.get(skill.name)
                if category:
                    categories.add(category)

        if categories:
            resources["skills"] = {"categories": sorted(categories)}

    # Analyze agents
    agents_dir = claude_dir / "agents"
    if agents_dir.exists():
        levels = set()
        for agent in agents_dir.iterdir():
            if agent.is_file() and agent.suffix == ".md":
                level = agent_map.get(agent.name)
                if level is not None:
                    levels.add(level)

        if levels:
            resources["agents"] = {"levels": sorted(levels)}

    return resources


def migrate_subtest(
    subtest_dir: Path,
    skill_map: dict[str, str],
    agent_map: dict[str, int],
    dry_run: bool,
) -> tuple[bool, str]:
    """Migrate a single subtest directory.

    Args:
        subtest_dir: Path to the subtest directory
        skill_map: Mapping of skill name to category
        agent_map: Mapping of agent filename to level
        dry_run: If True, don't make changes

    Returns:
        Tuple of (success, message)

    """
    config_path = subtest_dir / "config.yaml"
    claude_dir = subtest_dir / ".claude"

    # Skip if no .claude directory
    if not claude_dir.exists():
        return True, "No .claude directory"

    # Analyze resources
    resources = analyze_subtest(subtest_dir, skill_map, agent_map)

    if not resources:
        return True, "No resources identified"

    # Load existing config
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # Skip if already has resources
    if config.get("resources"):
        return True, "Already has resources"

    # Add resources to config
    config["resources"] = resources

    if dry_run:
        return True, f"Would add: {resources}"

    # Write updated config
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Remove duplicated .claude directory
    shutil.rmtree(claude_dir)

    # Remove CLAUDE.md if it exists (will be regenerated from blocks)
    claude_md = subtest_dir / "CLAUDE.md"
    if claude_md.exists():
        claude_md.unlink()

    return True, f"Migrated: {resources}"


def migrate_test(
    test_dir: Path,
    skill_map: dict[str, str],
    agent_map: dict[str, int],
    dry_run: bool,
) -> dict:
    """Migrate all subtests in a test directory.

    Args:
        test_dir: Path to test directory (e.g., test-001)
        skill_map: Mapping of skill name to category
        agent_map: Mapping of agent filename to level
        dry_run: If True, don't make changes

    Returns:
        Dict with migration statistics

    """
    stats = {"migrated": 0, "skipped": 0, "errors": 0}

    for tier_dir in sorted(test_dir.glob("t[0-6]")):
        for subtest_dir in sorted(tier_dir.glob("[0-9][0-9]-*")):
            try:
                success, message = migrate_subtest(subtest_dir, skill_map, agent_map, dry_run)
                if "Migrated" in message or "Would add" in message:
                    stats["migrated"] += 1
                    print(f"  {subtest_dir.relative_to(test_dir)}: {message}")
                else:
                    stats["skipped"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"  ERROR {subtest_dir.relative_to(test_dir)}: {e}")

    return stats


def main() -> None:
    """Migrate test fixtures to symlink-based resources."""
    parser = argparse.ArgumentParser(description="Migrate test fixtures to symlink-based resources")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration",
    )
    parser.add_argument(
        "--test",
        type=str,
        help="Only migrate a specific test (e.g., test-001)",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Specify --dry-run or --execute")
        return

    # Build lookup maps
    print("Building lookup maps...")
    skill_map = build_skill_category_map()
    agent_map = build_agent_level_map()
    print(f"  Found {len(skill_map)} skills in {len(set(skill_map.values()))} categories")
    print(f"  Found {len(agent_map)} agents across {len(set(agent_map.values()))} levels")

    # Find test directories
    if args.test:
        test_dirs = [FIXTURES_DIR / args.test]
        if not test_dirs[0].exists():
            print(f"Test directory not found: {test_dirs[0]}")
            return
    else:
        test_dirs = sorted(FIXTURES_DIR.glob("test-*"))

    print(f"\nMigrating {len(test_dirs)} test(s)...")
    total_stats = {"migrated": 0, "skipped": 0, "errors": 0}

    for test_dir in test_dirs:
        print(f"\n{test_dir.name}:")
        stats = migrate_test(test_dir, skill_map, agent_map, dry_run=args.dry_run)
        for key in total_stats:
            total_stats[key] += stats[key]

    print(f"\n{'DRY RUN ' if args.dry_run else ''}Summary:")
    print(f"  Migrated: {total_stats['migrated']}")
    print(f"  Skipped: {total_stats['skipped']}")
    print(f"  Errors: {total_stats['errors']}")

    if args.dry_run:
        print("\nRun with --execute to apply changes")


if __name__ == "__main__":
    main()
