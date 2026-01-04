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
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from scylla.e2e.models import ResourceManifest, SubTestConfig, TierBaseline, TierConfig, TierID

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
            tiers_dir: Path to the config/tiers directory
        """
        self.tiers_dir = tiers_dir

    def load_tier_config(self, tier_id: TierID) -> TierConfig:
        """Load configuration for a specific tier.

        Discovers all sub-tests for the tier and returns a complete
        TierConfig object.

        Args:
            tier_id: The tier to load configuration for

        Returns:
            TierConfig with all sub-tests for the tier.
        """
        tier_dir = self.tiers_dir / tier_id.value.lower()

        # All tiers now have sub-tests with custom configurations
        # The system_prompt_mode is determined per sub-test, not per tier
        system_prompt_mode = "custom"

        # Discover sub-tests
        subtests = self._discover_subtests(tier_id, tier_dir)

        return TierConfig(
            tier_id=tier_id,
            subtests=subtests,
            system_prompt_mode=system_prompt_mode,
        )

    def _discover_subtests(self, tier_id: TierID, tier_dir: Path) -> list[SubTestConfig]:
        """Discover sub-test configurations in a tier directory.

        All tiers now support numbered sub-tests. Sub-test directories use
        the format "NN-name" (e.g., "00-empty", "01-vanilla", "02-critical-only").

        Args:
            tier_id: The tier identifier
            tier_dir: Path to the tier directory

        Returns:
            List of SubTestConfig for each discovered sub-test.
        """
        subtests = []

        if not tier_dir.exists():
            return subtests

        # Look for numbered subdirectories (format: NN-name or just NN)
        for subdir in sorted(tier_dir.iterdir()):
            if not subdir.is_dir():
                continue

            # Match directories starting with digits (e.g., "00-empty", "01", "02-vanilla")
            dir_name = subdir.name
            if not dir_name[:2].isdigit():
                continue

            # Extract ID (first two digits) and name
            subtest_id = dir_name[:2]
            subtest_name_suffix = dir_name[3:] if len(dir_name) > 2 and dir_name[2] == "-" else ""

            claude_md = subdir / "CLAUDE.md"
            claude_dir = subdir / ".claude"

            # Load metadata if config.yaml exists
            config_file = subdir / "config.yaml"
            name = (
                f"{tier_id.value} {subtest_name_suffix}"
                if subtest_name_suffix
                else f"{tier_id.value} Sub-test {subtest_id}"
            )
            description = f"Sub-test configuration {dir_name}"

            # T0 sub-tests have special handling for extends_previous
            # 00-empty and 01-vanilla don't extend; 02+ may extend
            extends_previous = tier_id != TierID.T0 or int(subtest_id) >= 2

            # Load resources spec for symlink-based fixtures
            resources: dict[str, Any] = {}

            if config_file.exists():
                with open(config_file) as f:
                    config_data = yaml.safe_load(f) or {}
                name = config_data.get("name", name)
                description = config_data.get("description", description)
                # Allow config to override extends_previous
                extends_previous = config_data.get("extends_previous", extends_previous)
                # Load resources specification for runtime symlinks
                resources = config_data.get("resources", {})

                # Also capture mcp_servers into resources for prompt suffixes
                mcp_servers = config_data.get("mcp_servers", [])
                if mcp_servers:
                    resources["mcp_servers"] = mcp_servers

            subtests.append(
                SubTestConfig(
                    id=subtest_id,
                    name=name,
                    description=description,
                    claude_md_path=claude_md if claude_md.exists() else None,
                    claude_dir_path=claude_dir if claude_dir.exists() else None,
                    extends_previous=extends_previous,
                    resources=resources,
                )
            )

        return subtests

    def prepare_workspace(
        self,
        workspace: Path,
        tier_id: TierID,
        subtest_id: str,
        baseline: TierBaseline | None = None,
    ) -> None:
        """Prepare a workspace with tier configuration.

        Implements the copy+extend inheritance pattern:
        1. If baseline provided and sub-test extends_previous, copy baseline
        2. Overlay the sub-test's specific configuration

        For T0 sub-tests, special handling applies:
        - 00-empty: Remove all CLAUDE.md and .claude (no system prompt)
        - 01-vanilla: Use tool defaults (no changes)
        - 02+: Apply the sub-test's CLAUDE.md configuration

        Args:
            workspace: Path to the workspace directory
            tier_id: The tier being prepared
            subtest_id: The sub-test identifier
            baseline: Previous tier's winning baseline (if any)
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
                return
            elif subtest_id == "01":
                # 01-vanilla: Use tool defaults (no changes needed)
                # But still remove any existing CLAUDE.md to ensure clean state
                if claude_md.exists():
                    claude_md.unlink()
                if claude_dir.exists():
                    shutil.rmtree(claude_dir)
                return
            # 02+: Fall through to normal overlay logic

        # Step 1: Apply baseline if extending from previous tier
        if baseline and subtest.extends_previous:
            self._apply_baseline(workspace, baseline)

        # Step 2: Overlay sub-test configuration
        self._overlay_subtest(workspace, subtest)

    def _apply_baseline(self, workspace: Path, baseline: TierBaseline) -> None:
        """Apply baseline configuration to workspace using resources.

        NEW: Uses resource specification to recreate config via symlinks,
        instead of copying files. Falls back to legacy copy for old baselines.

        Args:
            workspace: Target workspace directory
            baseline: Baseline configuration to apply
        """
        # NEW: Use resources to recreate via symlinks (no file copying)
        if baseline.resources:
            self._create_symlinks(workspace, baseline.resources)
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

    def _overlay_subtest(self, workspace: Path, subtest: SubTestConfig) -> None:
        """Overlay sub-test configuration onto workspace.

        Uses symlinks to shared resources based on the resources spec.
        All fixtures must use symlink-based configuration (no legacy copy mode).

        Args:
            workspace: Target workspace directory
            subtest: Sub-test configuration to overlay
        """
        # Use symlinks if resources are specified
        if subtest.resources:
            self._create_symlinks(workspace, subtest.resources)
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

    def _create_symlinks(self, workspace: Path, resources: dict[str, Any]) -> None:
        """Create symlinks to shared resources at runtime.

        Args:
            workspace: Target workspace directory
            resources: Resource specification from config.yaml
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

        # Compose CLAUDE.md from blocks
        if "claude_md" in resources:
            claude_md_spec = resources["claude_md"]
            self._compose_claude_md(workspace, claude_md_spec, shared_dir)

    def _compose_claude_md(
        self,
        workspace: Path,
        spec: dict[str, Any],
        shared_dir: Path,
    ) -> None:
        """Compose CLAUDE.md from blocks at runtime.

        Args:
            workspace: Target workspace directory
            spec: CLAUDE.md specification (preset or blocks list)
            shared_dir: Path to shared resources directory
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

        if not block_ids:
            return

        content_parts = []
        for block_id in block_ids:
            # Find block file matching pattern like "B02-critical-rules.md"
            matches = list(blocks_dir.glob(f"{block_id}-*.md"))
            if matches:
                content_parts.append(matches[0].read_text())

        if content_parts:
            claude_md = workspace / "CLAUDE.md"
            claude_md.write_text("\n\n".join(content_parts))

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
                suffixes.append(f"Use the following sub-agents to solve this task:\n{bullet_list}")

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
                suffixes.append(f"Use the following skills to complete this task:\n{bullet_list}")

        # MCP servers
        if "mcp_servers" in resources:
            mcp_names = [m.get("name", m) if isinstance(m, dict) else m for m in resources["mcp_servers"]]
            if mcp_names:
                has_any_resources = True
                bullet_list = "\n".join(f"- {name}" for name in sorted(set(mcp_names)))
                suffixes.append(f"Use the following MCP servers to complete this task:\n{bullet_list}")

        # Tools
        if "tools" in resources:
            tool_names = resources["tools"].get("names", [])
            if tool_names:
                has_any_resources = True
                bullet_list = "\n".join(f"- {name}" for name in sorted(tool_names))
                suffixes.append(f"Use the following tools to complete this task:\n{bullet_list}")

        # If no resources configured, add generic hint
        if not has_any_resources:
            return "Complete this task using available tools and your best judgment."

        return "\n\n".join(suffixes)

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
        """Get path to the fixture's config.yaml file.

        Args:
            tier_id: The tier identifier
            subtest_id: The subtest identifier

        Returns:
            Path to config.yaml in the fixture directory.
        """
        tier_dir = self.tiers_dir / tier_id.value.lower()
        # Find directory starting with subtest_id (e.g., "03-full")
        for subdir in tier_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith(subtest_id):
                return subdir / "config.yaml"
        return tier_dir / subtest_id / "config.yaml"

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
            composed_at=datetime.now(UTC).isoformat(),
            claude_md_hash=claude_md_hash,
            inherited_from=inherited_from,
        )

        manifest.save(results_dir / "config_manifest.json")
