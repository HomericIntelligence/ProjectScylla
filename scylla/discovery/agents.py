"""Agent discovery and organization.

Extracted from scripts/organize_agents.py to provide reusable discovery logic
for the dynamic benchmark generator.
"""

import re
import shutil
from pathlib import Path


def parse_agent_level(file_path: Path) -> int | None:
    """Extract the level from an agent's YAML frontmatter.

    Args:
        file_path: Path to agent markdown file

    Returns:
        Agent level (0-5) if found in frontmatter, None otherwise

    Example:
        >>> parse_agent_level(Path("agents/chief-evaluator.md"))
        0
    """
    with open(file_path) as f:
        content = f.read()

    # Look for level in YAML frontmatter
    match = re.search(r"^level:\s*(\d+)", content, re.MULTILINE)
    if match:
        return int(match.group(1))

    return None


def discover_agents(source_dir: Path) -> dict[int, list[Path]]:
    """Scan agents directory and classify by hierarchy level.

    Args:
        source_dir: Directory containing agent .md files

    Returns:
        Dictionary mapping level (0-5) to list of agent file paths.
        Agents without valid levels are not included.

    Example:
        >>> agents = discover_agents(Path(".claude/agents"))
        >>> agents[0]  # L0 agents
        [Path(".claude/agents/chief-evaluator.md")]
    """
    agent_files = list(source_dir.glob("*.md"))
    result: dict[int, list[Path]] = {i: [] for i in range(6)}

    for agent_file in agent_files:
        level = parse_agent_level(agent_file)
        if level is not None and 0 <= level <= 5:
            result[level].append(agent_file)

    return result


def organize_agents(source_dir: Path, dest_dir: Path) -> dict[int, list[str]]:
    """Copy agents from source to destination, organized by level.

    Creates L0-L5 subdirectories and copies agent files into the appropriate
    level directory.

    Args:
        source_dir: Directory containing source agent .md files
        dest_dir: Destination directory (will create L0-L5 subdirs)

    Returns:
        Dictionary mapping level to list of organized agent filenames

    Example:
        >>> organize_agents(
        ...     Path(".claude/agents"),
        ...     Path("tests/shared/agents")
        ... )
        {0: ['chief-evaluator.md'], 1: ['experiment-design.md'], ...}
    """
    # Ensure destination directories exist
    for level in range(6):
        (dest_dir / f"L{level}").mkdir(parents=True, exist_ok=True)

    # Discover and organize
    agents_by_level = discover_agents(source_dir)
    stats: dict[int, list[str]] = {i: [] for i in range(6)}

    for level, agent_files in agents_by_level.items():
        for agent_file in agent_files:
            dest_path = dest_dir / f"L{level}" / agent_file.name
            shutil.copy2(agent_file, dest_path)
            stats[level].append(agent_file.name)

    return stats
