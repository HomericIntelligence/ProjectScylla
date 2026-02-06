"""Tier configuration management with inheritance.

This module handles loading tier configurations, managing sub-tests,
and implementing the copy+extend inheritance pattern between tiers.

Python Justification: Required for filesystem operations and YAML parsing.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from scylla.e2e.models import ResourceManifest, SubTestConfig, TierBaseline, TierConfig, TierID
from scylla.executor.tier_config import TierConfigLoader

if TYPE_CHECKING:
    pass


class TierManager:
    """Manages tier configurations and inheritance.

    Handles loading tier configs from the filesystem, discovering
    sub-tests, and preparing workspaces with inherited configurations.

    Example:
        >>> manager = TierManager(Path("config/tiers"))
        >>> tier_config = manager.load_tier_config(TierID.T2)
        >>> manager.prepare_workspace(
        ...     workspace=Path("/tmp/workspace"),
        ...     tier_id=TierID.T3,
        ...     subtest_id="01",
        ...     baseline=previous_baseline,
        ... )

    """

    def __init__(self, tiers_dir: Path) -> None:
        """Initialize the tier manager.

        Args:
            tiers_dir: Path to the config/tiers directory (or test-specific tiers dir)

        """
        self.tiers_dir = tiers_dir
        # Initialize global tier config loader from config/tiers/
        # Find the config directory (should be at repo root / config)
        config_dir = Path(__file__).parent.parent.parent / "config"
        self.tier_config_loader = TierConfigLoader(config_dir)

    def load_tier_config(self, tier_id: TierID, skip_agent_teams: bool = False) -> TierConfig:
        """Load configuration for a specific tier.

        Loads tier-level config from config/tiers/ and discovers sub-tests.

        Args:
            tier_id: The tier to load configuration for
            skip_agent_teams: Skip agent teams sub-tests (default: False)

        Returns:
            TierConfig with all sub-tests for the tier.

        """
        # Load global tier configuration from config/tiers/
        global_tier_config = self.tier_config_loader.get_tier(tier_id.value)

        # Discover sub-tests from test-specific directory
        tier_dir = self.tiers_dir / tier_id.value.lower()

        # All tiers now have sub-tests with custom configurations
        # The system_prompt_mode is determined per sub-test, not per tier
        system_prompt_mode = "custom"

        # Discover sub-tests
        subtests = self._discover_subtests(tier_id, tier_dir, skip_agent_teams)

        # Create TierConfig with both global settings and subtests
        return TierConfig(
            tier_id=tier_id,
            subtests=subtests,
            system_prompt_mode=system_prompt_mode,
            prompt_content=global_tier_config.prompt_content,
            tools_enabled=global_tier_config.tools_enabled,
            delegation_enabled=global_tier_config.delegation_enabled,
        )

    def _discover_subtests(
        self, tier_id: TierID, tier_dir: Path, skip_agent_teams: bool = False
    ) -> list[SubTestConfig]:
        """Discover sub-test configurations from shared directory.

        Loads subtest configs from tests/claude-code/shared/subtests/tN/*.yaml.
        All tiers now support numbered sub-tests.

        Args:
            tier_id: The tier identifier
            tier_dir: Path to the tier directory (legacy, kept for compatibility)
            skip_agent_teams: Skip agent teams sub-tests (default: False)

        Returns:
            List of SubTestConfig for each discovered sub-test.

        """
        subtests = []

        # Load from centralized shared directory
        shared_subtests_dir = self._get_shared_dir() / "subtests" / tier_id.value.lower()

        if not shared_subtests_dir.exists():
            return subtests

        # Look for YAML files (format: NN-name.yaml)
        for config_file in sorted(shared_subtests_dir.glob("*.yaml")):
            # Extract ID from filename (e.g., "00-empty.yaml" -> "00")
            file_name = config_file.stem
            if not file_name[:2].isdigit():
                continue

            subtest_id = file_name[:2]

            # Load config
            with open(config_file) as f:
                config_data = yaml.safe_load(f) or {}

            name = config_data.get("name", f"{tier_id.value} Sub-test {subtest_id}")
            description = config_data.get("description", f"Sub-test configuration {file_name}")

            # T0 sub-tests have special handling for extends_previous
            # 00-empty and 01-vanilla don't extend; 02+ may extend
            extends_previous = tier_id != TierID.T0 or int(subtest_id) >= 2
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
            system_prompt_mode = config_data.get("system_prompt_mode", "custom")

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

    def prepare_workspace(
        self,
        workspace: Path,
        tier_id: TierID,
        subtest_id: str,
        baseline: TierBaseline | None = None,
        merged_resources: dict[str, Any] | None = None,
        thinking_enabled: bool = False,
    ) -> None:
        """Prepare a workspace with tier configuration.

        Implements the copy+extend inheritance pattern:
        1. If baseline provided and sub-test extends_previous, copy baseline
        2. Overlay the sub-test's specific configuration

        For T5 sub-tests with inherit_best_from:
        1. Apply merged resources from completed lower tiers first
        2. Overlay the sub-test's own resources on top (e.g., tools: enabled: all)

        For T0 sub-tests, special handling applies:
        - 00-empty: Remove all CLAUDE.md and .claude (no system prompt)
        - 01-vanilla: Use tool defaults (no changes)
        - 02+: Apply the sub-test's CLAUDE.md configuration

        Args:
            workspace: Path to the workspace directory
            tier_id: The tier being prepared
            subtest_id: The sub-test identifier
            baseline: Previous tier's winning baseline (if any)
            merged_resources: Pre-merged resources from multiple tiers (T5 only)
            thinking_enabled: Whether to enable extended thinking mode

        """
        tier_config = self.load_tier_config(tier_id)
        subtest = next((s for s in tier_config.subtests if s.id == subtest_id), None)

        if not subtest:
            raise ValueError(f"Sub-test {subtest_id} not found for tier {tier_id.value}")

        # Special handling for T0 sub-tests
        if tier_id == TierID.T0:
            claude_md = workspace / "CLAUDE.md"
            claude_dir = workspace / ".claude"

            if subtest_id == "00":
                # 00-empty: Remove all configuration (no system prompt)
                if claude_md.exists():
                    claude_md.unlink()
                if claude_dir.exists():
                    shutil.rmtree(claude_dir)
                # Still create settings.json for thinking control
                self._create_settings_json(workspace, subtest, thinking_enabled)
                return
            elif subtest_id == "01":
                # 01-vanilla: Use tool defaults (no changes needed)
                # But still remove any existing CLAUDE.md to ensure clean state
                if claude_md.exists():
                    claude_md.unlink()
                if claude_dir.exists():
                    shutil.rmtree(claude_dir)
                # Still create settings.json for thinking control
                self._create_settings_json(workspace, subtest, thinking_enabled)
                return
            # 02+: Fall through to normal overlay logic

        # Build resource suffix for CLAUDE.md
        # For T5 with merged resources, create temporary SubTestConfig with merged resources
        if merged_resources and tier_id == TierID.T5:
            # Merge subtest resources with inherited resources if needed
            final_merged = merged_resources.copy()
            if subtest.resources:
                for resource_type, resource_spec in subtest.resources.items():
                    if resource_type not in final_merged:
                        final_merged[resource_type] = resource_spec
                    else:
                        temp_merged = final_merged.copy()
                        temp_new = {resource_type: resource_spec}
                        self._merge_tier_resources(temp_merged, temp_new, TierID.T5)
                        final_merged = temp_merged

            # Create temporary SubTestConfig for resource suffix generation
            from dataclasses import replace

            temp_subtest = replace(subtest, resources=final_merged)
            resource_suffix = self.build_resource_suffix(temp_subtest)

            # Apply merged resources with suffix
            self._create_symlinks(workspace, final_merged, resource_suffix)
        # Normal baseline extension for other tiers
        elif baseline and subtest.extends_previous:
            # Build resource suffix from baseline
            from dataclasses import replace

            temp_subtest = replace(subtest, resources=baseline.resources)
            resource_suffix = self.build_resource_suffix(temp_subtest)
            self._apply_baseline(workspace, baseline, resource_suffix)
        else:
            # Build resource suffix from subtest
            resource_suffix = self.build_resource_suffix(subtest)

        # Step 2: Overlay sub-test configuration (skip for T5 with merged_resources)
        if not (merged_resources and tier_id == TierID.T5):
            self._overlay_subtest(workspace, subtest, resource_suffix)

        # Create settings.json with thinking configuration
        self._create_settings_json(workspace, subtest, thinking_enabled)

    def _apply_baseline(
        self, workspace: Path, baseline: TierBaseline, resource_suffix: str | None = None
    ) -> None:
        """Apply baseline configuration to workspace using resources.

        NEW: Uses resource specification to recreate config via symlinks,
        instead of copying files. Falls back to legacy copy for old baselines.

        Args:
            workspace: Target workspace directory
            baseline: Baseline configuration to apply
            resource_suffix: Optional resource usage instructions to append to CLAUDE.md

        """
        # NEW: Use resources to recreate via symlinks (no file copying)
        if baseline.resources:
            self._create_symlinks(workspace, baseline.resources, resource_suffix)
            return

        # LEGACY fallback: Copy from paths (for old baselines without resources)
        if baseline.claude_md_path and baseline.claude_md_path.exists():
            dest = workspace / "CLAUDE.md"
            shutil.copy(baseline.claude_md_path, dest)

        if baseline.claude_dir_path and baseline.claude_dir_path.exists():
            dest = workspace / ".claude"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(baseline.claude_dir_path, dest)

    def _overlay_subtest(
        self, workspace: Path, subtest: SubTestConfig, resource_suffix: str | None = None
    ) -> None:
        """Overlay sub-test configuration onto workspace.

        Uses symlinks to shared resources based on the resources spec.
        All fixtures must use symlink-based configuration (no legacy copy mode).

        Args:
            workspace: Target workspace directory
            subtest: Sub-test configuration to overlay
            resource_suffix: Optional resource usage instructions to append to CLAUDE.md

        """
        # Use symlinks if resources are specified
        if subtest.resources:
            self._create_symlinks(workspace, subtest.resources, resource_suffix)
            return

        # Empty resources is valid (e.g., T0 empty/vanilla subtests)
        # No action needed - workspace will have no CLAUDE.md or .claude

    def _merge_directories(self, src: Path, dest: Path) -> None:
        """Recursively merge source directory into destination.

        Files from source overwrite destination files on conflict.
        Directories are merged recursively.

        Args:
            src: Source directory
            dest: Destination directory

        """
        dest.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            dest_item = dest / item.name
            if item.is_dir():
                self._merge_directories(item, dest_item)
            else:
                shutil.copy(item, dest_item)

    def _get_shared_dir(self) -> Path:
        """Get path to the shared resources directory.

        Returns:
            Path to tests/claude-code/shared/ directory.

        """
        # Navigate from tiers_dir (tests/fixtures/tests/test-XXX) to shared
        # tiers_dir -> tests/fixtures/tests -> tests/fixtures -> tests -> claude-code/shared
        return self.tiers_dir.parent.parent.parent / "claude-code" / "shared"

    def _resolve_resources(self, config_path: Path) -> dict[str, Any]:
        """Parse resources section from config.yaml.

        Args:
            config_path: Path to the config.yaml file

        Returns:
            Dictionary with resources specification (skills, agents, claude_md)

        """
        if not config_path.exists():
            return {}

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        return config.get("resources", {})

    def _create_symlinks(
        self,
        workspace: Path,
        resources: dict[str, Any],
        resource_suffix: str | None = None,
    ) -> None:
        """Create symlinks to shared resources at runtime.

        Args:
            workspace: Target workspace directory
            resources: Resource specification from config.yaml
            resource_suffix: Optional resource usage instructions to append to CLAUDE.md

        """
        shared_dir = self._get_shared_dir()

        # Symlink skills by category
        if "skills" in resources:
            skills_spec = resources["skills"]
            skills_dir = workspace / ".claude" / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)

            # Handle categories (e.g., ["agent", "github"])
            for category in skills_spec.get("categories", []):
                category_dir = shared_dir / "skills" / category
                if category_dir.exists():
                    for skill in category_dir.iterdir():
                        if skill.is_dir():
                            link_path = skills_dir / skill.name
                            if not link_path.exists():
                                os.symlink(skill.resolve(), link_path)

            # Handle individual skill names (e.g., ["gh-create-pr-linked"])
            for skill_name in skills_spec.get("names", []):
                # Search all categories for this skill
                for category_dir in (shared_dir / "skills").iterdir():
                    if category_dir.is_dir():
                        skill_path = category_dir / skill_name
                        if skill_path.exists():
                            link_path = skills_dir / skill_name
                            if not link_path.exists():
                                os.symlink(skill_path.resolve(), link_path)
                            break

        # Symlink agents by level
        if "agents" in resources:
            agents_spec = resources["agents"]
            agents_dir = workspace / ".claude" / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)

            # Handle levels (e.g., [0, 1, 3])
            for level in agents_spec.get("levels", []):
                level_dir = shared_dir / "agents" / f"L{level}"
                if level_dir.exists():
                    for agent in level_dir.iterdir():
                        if agent.is_file() and agent.suffix == ".md":
                            link_path = agents_dir / agent.name
                            if not link_path.exists():
                                os.symlink(agent.resolve(), link_path)

            # Handle individual agent names (e.g., ["chief-architect.md"])
            for agent_name in agents_spec.get("names", []):
                # Search all levels for this agent
                for level_dir in (shared_dir / "agents").iterdir():
                    if level_dir.is_dir() and level_dir.name.startswith("L"):
                        agent_path = level_dir / agent_name
                        if agent_path.exists():
                            link_path = agents_dir / agent_name
                            if not link_path.exists():
                                os.symlink(agent_path.resolve(), link_path)
                            break

        # Compose CLAUDE.md from blocks (with optional resource suffix)
        if "claude_md" in resources:
            claude_md_spec = resources["claude_md"]
            self._compose_claude_md(workspace, claude_md_spec, shared_dir, resource_suffix)
        elif resource_suffix:
            # No claude_md blocks, but we have a resource suffix - create minimal CLAUDE.md
            claude_md = workspace / "CLAUDE.md"
            claude_md.write_text(resource_suffix)

    def _compose_claude_md(
        self,
        workspace: Path,
        spec: dict[str, Any],
        shared_dir: Path,
        resource_suffix: str | None = None,
    ) -> None:
        """Compose CLAUDE.md from blocks at runtime.

        Args:
            workspace: Target workspace directory
            spec: CLAUDE.md specification (preset or blocks list)
            shared_dir: Path to shared resources directory
            resource_suffix: Optional resource usage instructions to append

        """
        blocks_dir = shared_dir / "blocks"
        if not blocks_dir.exists():
            return

        # Get block IDs from spec
        block_ids = spec.get("blocks", [])

        # Handle presets (would need a preset mapping, for now just use blocks)
        if not block_ids and "preset" in spec:
            # TODO: Add preset mappings if needed
            return

        # If no blocks but we have a resource suffix, create CLAUDE.md anyway
        if not block_ids and not resource_suffix:
            return

        content_parts = []
        for block_id in block_ids:
            # Find block file matching pattern like "B02-critical-rules.md"
            matches = list(blocks_dir.glob(f"{block_id}-*.md"))
            if matches:
                content_parts.append(matches[0].read_text())

        # Compose final content
        content = "\n\n".join(content_parts) if content_parts else ""

        # Append resource suffix if provided
        if resource_suffix:
            if content:
                content = f"{content}\n\n{resource_suffix}"
            else:
                content = resource_suffix

        # Write CLAUDE.md if we have any content
        if content:
            claude_md = workspace / "CLAUDE.md"
            claude_md.write_text(content)

    def _create_settings_json(
        self,
        workspace: Path,
        subtest: SubTestConfig,
        thinking_enabled: bool = False,
    ) -> None:
        """Create .claude/settings.json for workspace configuration.

        Includes thinking mode, tool permissions, and MCP server registrations.

        Args:
            workspace: Target workspace directory
            subtest: SubTest configuration with resources specification
            thinking_enabled: Whether to enable thinking mode

        """
        settings = {
            "alwaysThinkingEnabled": thinking_enabled,
        }

        resources = subtest.resources or {}

        # Add tool permissions for T2+ tiers
        if "tools" in resources:
            tools_spec = resources["tools"]
            if isinstance(tools_spec, dict):
                enabled_tools = tools_spec.get("enabled", [])
                if enabled_tools and enabled_tools != "all":
                    # Restrict to specific tools
                    settings["allowedTools"] = enabled_tools
                # If enabled_tools == "all", don't add restriction (all tools allowed)

        # Add MCP server configurations
        if "mcp_servers" in resources:
            mcp_servers = resources["mcp_servers"]
            if mcp_servers:
                settings["mcpServers"] = {}
                for server in mcp_servers:
                    if isinstance(server, dict):
                        name = server["name"]
                        source = server.get("source", "modelcontextprotocol/servers")
                        settings["mcpServers"][name] = {
                            "command": "npx",
                            "args": ["-y", f"@{source}/{name}"],
                        }
                    else:
                        # Simple string format
                        settings["mcpServers"][server] = {
                            "command": "npx",
                            "args": ["-y", f"@modelcontextprotocol/servers/{server}"],
                        }

        # Add experimental agent teams environment variable
        if subtest.agent_teams:
            if "env" not in settings:
                settings["env"] = {}
            settings["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"

        settings_dir = workspace / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "settings.json"
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

    def build_resource_suffix(self, subtest: SubTestConfig) -> str:
        """Build prompt suffix based on configured resources.

        Uses bullet list format for resources:
        - skill1
        - skill2

        If no resources configured, returns generic hint.

        Args:
            subtest: SubTestConfig with resources specification

        Returns:
            Prompt suffix string with resource hints

        """
        suffixes = []
        resources = subtest.resources or {}
        has_any_resources = False

        # Sub-agents
        if "agents" in resources:
            agents_spec = resources["agents"]
            agent_names = []
            for level in agents_spec.get("levels", []):
                level_dir = self._get_shared_dir() / "agents" / f"L{level}"
                if level_dir.exists():
                    for f in level_dir.glob("*.md"):
                        agent_names.append(f.stem)
            agent_names.extend(n.replace(".md", "") for n in agents_spec.get("names", []))
            if agent_names:
                has_any_resources = True
                bullet_list = "\n".join(f"- {name}" for name in sorted(set(agent_names)))
                if len(agent_names) > 1:
                    prefix = "Maximize usage of the following sub-agents to solve this task:"
                else:
                    prefix = "Use the following sub-agent to solve this task:"
                suffixes.append(f"{prefix}\n\n{bullet_list}")

        # Skills
        if "skills" in resources:
            skills_spec = resources["skills"]
            skill_names = []
            for cat in skills_spec.get("categories", []):
                cat_dir = self._get_shared_dir() / "skills" / cat
                if cat_dir.exists():
                    skill_names.extend(d.name for d in cat_dir.iterdir() if d.is_dir())
            skill_names.extend(skills_spec.get("names", []))
            if skill_names:
                has_any_resources = True
                bullet_list = "\n".join(f"- {name}" for name in sorted(set(skill_names)))
                if len(skill_names) > 1:
                    prefix = "Maximize usage of the following skills to complete this task:"
                else:
                    prefix = "Use the following skill to complete this task:"
                suffixes.append(f"{prefix}\n\n{bullet_list}")

        # MCP servers
        if "mcp_servers" in resources:
            mcp_names = [
                m.get("name", m) if isinstance(m, dict) else m for m in resources["mcp_servers"]
            ]
            if mcp_names:
                has_any_resources = True
                bullet_list = "\n".join(f"- {name}" for name in sorted(set(mcp_names)))
                if len(mcp_names) > 1:
                    prefix = "Maximize usage of the following MCP servers to complete this task:"
                else:
                    prefix = "Use the following MCP server to complete this task:"
                suffixes.append(f"{prefix}\n\n{bullet_list}")

        # Tools
        if "tools" in resources:
            tools_spec = resources["tools"]
            if isinstance(tools_spec, dict):
                if tools_spec.get("enabled") == "all":
                    suffixes.append("Maximize usage of all available tools to complete this task.")
                    has_any_resources = True
                elif "names" in tools_spec:
                    tool_names = tools_spec["names"]
                    if tool_names:
                        has_any_resources = True
                        bullet_list = "\n".join(f"- {name}" for name in sorted(tool_names))
                        if len(tool_names) > 1:
                            prefix = "Maximize usage of the following tools to complete this task:"
                        else:
                            prefix = "Use the following tool to complete this task:"
                        suffixes.append(f"{prefix}\n\n{bullet_list}")

        # If no resources configured, add generic hint
        if not has_any_resources:
            base_message = "Complete this task using available tools and your best judgment."
        else:
            base_message = "\n\n".join(suffixes)

        # Always add cleanup instructions (temporary files only)
        cleanup_instructions = (
            "\n\n## Cleanup Requirements\n\n"
            "- Remove any temporary files created during task completion "
            "(build artifacts, cache files, etc.)\n"
            "- Clean up after yourself - the workspace should contain only final deliverables\n"
        )

        return base_message + cleanup_instructions

    def get_baseline_for_subtest(
        self,
        tier_id: TierID,
        subtest_id: str,
        results_dir: Path,
    ) -> TierBaseline:
        """Create a baseline reference from a completed sub-test.

        NEW: Reads resource manifest instead of looking for copied files.
        Falls back to legacy config/ directory for old results.

        Args:
            tier_id: The tier of the winning sub-test
            subtest_id: The winning sub-test ID
            results_dir: Directory containing the sub-test's results

        Returns:
            TierBaseline that can be passed to the next tier.

        """
        # NEW: Read from manifest (no file copying)
        manifest_path = results_dir / "config_manifest.json"
        if manifest_path.exists():
            manifest = ResourceManifest.load(manifest_path)
            return TierBaseline(
                tier_id=tier_id,
                subtest_id=subtest_id,
                claude_md_path=None,  # No longer used with manifest
                claude_dir_path=None,  # No longer used with manifest
                resources=manifest.resources,
            )

        # LEGACY fallback: Read from config/ directory (for old results)
        config_dir = results_dir / "config"
        return TierBaseline(
            tier_id=tier_id,
            subtest_id=subtest_id,
            claude_md_path=config_dir / "CLAUDE.md"
            if (config_dir / "CLAUDE.md").exists()
            else None,
            claude_dir_path=config_dir / ".claude" if (config_dir / ".claude").exists() else None,
        )

    def _get_fixture_config_path(self, tier_id: TierID, subtest_id: str) -> Path:
        """Get path to the fixture's config file in shared directory.

        Args:
            tier_id: The tier identifier
            subtest_id: The subtest identifier

        Returns:
            Path to config.yaml in the shared subtests directory.

        """
        shared_subtests_dir = self._get_shared_dir() / "subtests" / tier_id.value.lower()
        # Find config file starting with subtest_id (e.g., "00-empty.yaml")
        for config_file in shared_subtests_dir.glob(f"{subtest_id}-*.yaml"):
            return config_file
        # Fallback if exact match not found
        return shared_subtests_dir / f"{subtest_id}.yaml"

    def build_merged_baseline(
        self,
        inherit_from_tiers: list[TierID],
        experiment_dir: Path,
    ) -> dict[str, Any]:
        """Build merged resources from multiple tier results.

        Used by T5 subtests to dynamically inherit the best-performing
        configuration from completed lower tiers (T0-T4).

        Args:
            inherit_from_tiers: List of tier IDs to inherit from (e.g., [T0, T1, T3])
            experiment_dir: Path to experiment directory containing tier results

        Returns:
            Merged resources dictionary with combined configurations from all tiers.

        Raises:
            ValueError: If any required tier result is missing or has no best_subtest.

        """
        merged_resources: dict[str, Any] = {}

        for tier_id in inherit_from_tiers:
            # 1. Load tier result.json to get best_subtest
            result_file = experiment_dir / tier_id.value / "result.json"
            best_subtest_file = experiment_dir / tier_id.value / "best_subtest.json"

            best_subtest_id = None
            if result_file.exists():
                with open(result_file) as f:
                    tier_result = json.load(f)
                best_subtest_id = tier_result.get("best_subtest")
            elif best_subtest_file.exists():
                with open(best_subtest_file) as f:
                    selection = json.load(f)
                best_subtest_id = selection.get("winning_subtest")

            if not best_subtest_id:
                raise ValueError(
                    f"Cannot inherit from {tier_id.value}: neither result.json nor "
                    f"best_subtest.json found with best subtest selection. "
                    f"Ensure tier {tier_id.value} completed before T5."
                )

            # 2. Load config_manifest.json from best subtest
            manifest_file = (
                experiment_dir / tier_id.value / best_subtest_id / "config_manifest.json"
            )
            if not manifest_file.exists():
                raise ValueError(
                    f"Cannot inherit from {tier_id.value}/{best_subtest_id}: "
                    f"config_manifest.json not found."
                )

            with open(manifest_file) as f:
                manifest = json.load(f)

            # 3. Merge resources
            subtest_resources = manifest.get("resources", {})
            self._merge_tier_resources(merged_resources, subtest_resources, tier_id)

        return merged_resources

    def _merge_tier_resources(
        self,
        merged_resources: dict[str, Any],
        new_resources: dict[str, Any],
        source_tier: TierID,
    ) -> None:
        """Merge resources from a tier into the accumulated merged resources.

        Implements tier-specific merge strategies:
        - claude_md.blocks: Replace (T0 only provides this)
        - skills.categories/names: Union (combine lists, deduplicate)
        - tools.enabled: "all" wins, else union
        - mcp_servers: Union by server name
        - agents.levels/names: Union (T3 L2-L5 + T4 L0-L1)

        Args:
            merged_resources: Accumulated resources to merge into (modified in place)
            new_resources: Resources from the source tier to merge
            source_tier: The tier ID being merged (for logging/debugging)

        """
        # Merge claude_md blocks (replace - T0 only)
        if "claude_md" in new_resources:
            merged_resources["claude_md"] = new_resources["claude_md"]

        # Merge skills (union)
        if "skills" in new_resources:
            if "skills" not in merged_resources:
                merged_resources["skills"] = {}

            new_skills = new_resources["skills"]

            # Merge categories
            if "categories" in new_skills:
                merged_categories = merged_resources["skills"].get("categories", [])
                merged_categories.extend(new_skills["categories"])
                merged_resources["skills"]["categories"] = list(set(merged_categories))

            # Merge names
            if "names" in new_skills:
                merged_names = merged_resources["skills"].get("names", [])
                merged_names.extend(new_skills["names"])
                merged_resources["skills"]["names"] = list(set(merged_names))

        # Merge tools ("all" wins, else union)
        if "tools" in new_resources:
            if "tools" not in merged_resources:
                merged_resources["tools"] = {}

            new_tools = new_resources["tools"]

            # Check for "all" - it wins
            new_enabled = new_tools.get("enabled", [])
            existing_enabled = merged_resources["tools"].get("enabled", [])

            if new_enabled == "all" or existing_enabled == "all":
                merged_resources["tools"]["enabled"] = "all"
            elif isinstance(new_enabled, list) and isinstance(existing_enabled, list):
                merged_enabled = existing_enabled + new_enabled
                merged_resources["tools"]["enabled"] = list(set(merged_enabled))

        # Merge MCP servers (union by server name)
        if "mcp_servers" in new_resources:
            if "mcp_servers" not in merged_resources:
                merged_resources["mcp_servers"] = []

            existing_servers = {s["name"]: s for s in merged_resources["mcp_servers"]}
            for server in new_resources["mcp_servers"]:
                server_name = server["name"]
                if server_name not in existing_servers:
                    merged_resources["mcp_servers"].append(server)

        # Merge agents (union)
        if "agents" in new_resources:
            if "agents" not in merged_resources:
                merged_resources["agents"] = {}

            new_agents = new_resources["agents"]

            # Merge levels
            if "levels" in new_agents:
                merged_levels = merged_resources["agents"].get("levels", [])
                merged_levels.extend(new_agents["levels"])
                merged_resources["agents"]["levels"] = sorted(list(set(merged_levels)))

            # Merge names
            if "names" in new_agents:
                merged_names = merged_resources["agents"].get("names", [])
                merged_names.extend(new_agents["names"])
                merged_resources["agents"]["names"] = list(set(merged_names))

    def save_resource_manifest(
        self,
        results_dir: Path,
        tier_id: TierID,
        subtest: SubTestConfig,
        workspace: Path,
        baseline: TierBaseline | None = None,
    ) -> None:
        """Save resource manifest for reproducibility.

        Instead of copying CLAUDE.md and .claude/ to results, saves a
        manifest that records what resources were used. This enables
        reproducibility without file duplication.

        Args:
            results_dir: Directory to save manifest to
            tier_id: The tier identifier
            subtest: The subtest configuration
            workspace: Workspace with the composed configuration
            baseline: Previous tier's baseline (for inheritance chain)

        """
        # Compute hash of composed CLAUDE.md for verification
        claude_md = workspace / "CLAUDE.md"
        claude_md_hash = None
        if claude_md.exists():
            claude_md_hash = hashlib.sha256(claude_md.read_bytes()).hexdigest()

        # Record inherited resources for the chain
        inherited_from = None
        if baseline and baseline.resources:
            inherited_from = baseline.resources

        manifest = ResourceManifest(
            tier_id=tier_id.value,
            subtest_id=subtest.id,
            fixture_config_path=str(self._get_fixture_config_path(tier_id, subtest.id)),
            resources=subtest.resources,
            composed_at=datetime.now(timezone.utc).isoformat(),
            claude_md_hash=claude_md_hash,
            inherited_from=inherited_from,
        )

        manifest.save(results_dir / "config_manifest.json")
