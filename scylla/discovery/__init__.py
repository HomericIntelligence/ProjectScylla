"""Resource discovery library for test fixtures.

This module provides reusable functions for discovering and organizing
resources from codebases: agents, skills, and CLAUDE.md blocks.

Extracted from scripts/organize_*.py to provide a clean API for the
dynamic benchmark generator.
"""

from scylla.discovery.agents import discover_agents, organize_agents, parse_agent_level
from scylla.discovery.blocks import discover_blocks, extract_blocks
from scylla.discovery.skills import (
    CATEGORY_MAPPINGS,
    discover_skills,
    get_skill_category,
    organize_skills,
)

__all__ = [
    # Agents
    "parse_agent_level",
    "discover_agents",
    "organize_agents",
    # Skills
    "CATEGORY_MAPPINGS",
    "get_skill_category",
    "discover_skills",
    "organize_skills",
    # Blocks
    "discover_blocks",
    "extract_blocks",
]
