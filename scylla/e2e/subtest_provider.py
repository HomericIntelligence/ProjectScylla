"""Subtest discovery providers for TierManager.

This module provides the SubtestProvider protocol and implementations
for discovering subtests from different sources (filesystem, dynamic generation).

Extracted from TierManager to enable dynamic benchmark generation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import yaml

if TYPE_CHECKING:
    from scylla.e2e.models import SubTestConfig, TierID

# Magic values extracted as constants
SUBTEST_ID_PREFIX_LENGTH = 2  # "NN" prefix in filenames
DEFAULT_SYSTEM_PROMPT_MODE = "custom"
T0_FIRST_EXTENDING_SUBTEST = 2  # T0 subtests 00-01 don't extend, 02+ do


class SubtestProvider(Protocol):
    """Protocol for subtest discovery.

    Implementations provide different methods of discovering subtests:
    - FileSystemSubtestProvider: Load from YAML files (current behavior)
    - DynamicSubtestProvider: Generate from BenchmarkSpec (future)
    """

    def discover_subtests(
        self, tier_id: TierID, skip_agent_teams: bool = False
    ) -> list[SubTestConfig]:
        """Discover subtests for a given tier."""
        ...


class FileSystemSubtestProvider:
    """Discover subtests from filesystem YAML files.

    This is the current behavior extracted from TierManager._discover_subtests().
    Loads subtest configs from shared/subtests/tN/*.yaml.
    """

    def __init__(self, shared_dir: Path) -> None:
        """Initialize the filesystem provider.

        Args:
            shared_dir: Path to the shared resources directory
                       (e.g., tests/claude-code/shared/)

        """
        self.shared_dir = shared_dir

    def discover_subtests(
        self, tier_id: TierID, skip_agent_teams: bool = False
    ) -> list[SubTestConfig]:
        """Discover sub-test configurations from shared directory.

        Loads subtest configs from shared/subtests/tN/*.yaml.
        All tiers now support numbered sub-tests.

        Args:
            tier_id: The tier identifier
            skip_agent_teams: Skip agent teams sub-tests (default: False)

        Returns:
            List of SubTestConfig for each discovered sub-test.

        """
        from scylla.e2e.models import SubTestConfig

        subtests: list[SubTestConfig] = []

        # Load from centralized shared directory
        shared_subtests_dir = self.shared_dir / "subtests" / tier_id.value.lower()

        if not shared_subtests_dir.exists():
            return subtests

        # Look for YAML files (format: NN-name.yaml)
        for config_file in sorted(shared_subtests_dir.glob("*.yaml")):
            # Extract ID from filename (e.g., "00-empty.yaml" -> "00")
            file_name = config_file.stem
            if not file_name[:SUBTEST_ID_PREFIX_LENGTH].isdigit():
                continue

            subtest_id = file_name[:SUBTEST_ID_PREFIX_LENGTH]

            # Load config
            with open(config_file) as f:
                config_data = yaml.safe_load(f) or {}

            name = config_data.get("name", f"{tier_id.value} Sub-test {subtest_id}")
            description = config_data.get("description", f"Sub-test configuration {file_name}")

            # T0 sub-tests have special handling for extends_previous
            # 00-empty and 01-vanilla don't extend; 02+ may extend
            extends_previous = (
                tier_id.value != "T0" or int(subtest_id) >= T0_FIRST_EXTENDING_SUBTEST
            )
            # Allow config to override extends_previous
            extends_previous = config_data.get("extends_previous", extends_previous)

            # Load resources specification
            resources: dict[str, Any] = config_data.get("resources", {})

            # Also capture root-level fields into resources for prompt suffixes
            mcp_servers = config_data.get("mcp_servers", [])
            if mcp_servers:
                resources["mcp_servers"] = mcp_servers

            # Map tools at root level
            tools = config_data.get("tools", {})
            if tools:
                resources["tools"] = tools

            # Map agents at root level
            agents = config_data.get("agents", {})
            if agents:
                resources["agents"] = agents

            # Map skills at root level
            skills = config_data.get("skills", {})
            if skills:
                resources["skills"] = skills

            # Parse inherit_best_from for T5 subtests
            from scylla.e2e.models import TierID

            inherit_best_from: list[TierID] = []
            if "inherit_best_from" in config_data:
                raw_tiers = config_data.get("inherit_best_from", [])
                inherit_best_from = [TierID.from_string(t) for t in raw_tiers]

            # Parse agent_teams flag
            agent_teams = config_data.get("agent_teams", False)

            # Skip if agent_teams is enabled but we're filtering them out
            if skip_agent_teams and agent_teams:
                continue

            # Parse system_prompt_mode for this subtest
            system_prompt_mode = config_data.get("system_prompt_mode", DEFAULT_SYSTEM_PROMPT_MODE)

            subtests.append(
                SubTestConfig(
                    id=subtest_id,
                    name=name,
                    description=description,
                    claude_md_path=None,  # No longer used with centralized configs
                    claude_dir_path=None,  # No longer used with centralized configs
                    extends_previous=extends_previous,
                    resources=resources,
                    inherit_best_from=inherit_best_from,
                    agent_teams=agent_teams,
                    system_prompt_mode=system_prompt_mode,
                )
            )

        return subtests
