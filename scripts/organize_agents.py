#!/usr/bin/env python3
"""Organize agents by hierarchy level.

This script reads agent files from ProjectOdyssey and organizes them
into L0-L5 directories based on their YAML frontmatter level.
"""

import re
import shutil
from pathlib import Path

# Source and destination directories
SOURCE_DIR = Path("/home/mvillmow/ProjectOdysseyManual/.claude/agents")
DEST_DIR = Path("/tmp/ProjectScylla/tests/claude-code/shared/agents")


def get_agent_level(file_path: Path) -> int | None:
    """Extract the level from an agent's YAML frontmatter."""
    with open(file_path) as f:
        content = f.read()

    # Look for level in YAML frontmatter
    match = re.search(r"^level:\s*(\d+)", content, re.MULTILINE)
    if match:
        return int(match.group(1))

    return None


def organize_agents() -> None:
    """Organize all agents by their hierarchy level."""
    # Get all .md files in source directory
    agent_files = list(SOURCE_DIR.glob("*.md"))
    print(f"Found {len(agent_files)} agent files in {SOURCE_DIR}")

    # Track statistics
    stats = {i: [] for i in range(6)}
    unknown = []

    for agent_file in agent_files:
        level = get_agent_level(agent_file)

        if level is not None and 0 <= level <= 5:
            dest_path = DEST_DIR / f"L{level}" / agent_file.name
            shutil.copy2(agent_file, dest_path)
            stats[level].append(agent_file.name)
        else:
            unknown.append(agent_file.name)

    # Print results
    print("\nAgents organized by level:")
    for level in range(6):
        agents = stats[level]
        print(f"\n  L{level}: {len(agents)} agents")
        for agent in sorted(agents):
            print(f"    - {agent}")

    if unknown:
        print(f"\n  Unknown level: {len(unknown)} agents")
        for agent in unknown:
            print(f"    - {agent}")

    total = sum(len(v) for v in stats.values())
    print(f"\nTotal: {total} agents organized, {len(unknown)} with unknown level")


def main():
    """Organize agent configuration files into level-based directories."""
    # Ensure destination directories exist
    for level in range(6):
        (DEST_DIR / f"L{level}").mkdir(parents=True, exist_ok=True)

    organize_agents()


if __name__ == "__main__":
    main()
