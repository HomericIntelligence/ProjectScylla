"""Tier configuration management with inheritance.

This module handles loading tier configurations, managing sub-tests,
and implementing the copy+extend inheritance pattern between tiers.

Python Justification: Required for filesystem operations and YAML parsing.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from scylla.e2e.models import SubTestConfig, TierBaseline, TierConfig, TierID

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

        # Determine system prompt mode based on tier
        if tier_id == TierID.T0:
            system_prompt_mode = "none"
        elif tier_id == TierID.T1:
            system_prompt_mode = "default"
        else:
            system_prompt_mode = "custom"  # T2+ use CLAUDE.md

        # Discover sub-tests
        subtests = self._discover_subtests(tier_id, tier_dir)

        return TierConfig(
            tier_id=tier_id,
            subtests=subtests,
            system_prompt_mode=system_prompt_mode,
        )

    def _discover_subtests(self, tier_id: TierID, tier_dir: Path) -> list[SubTestConfig]:
        """Discover sub-test configurations in a tier directory.

        Args:
            tier_id: The tier identifier
            tier_dir: Path to the tier directory

        Returns:
            List of SubTestConfig for each discovered sub-test.
        """
        subtests = []

        # For T0 and T1, there's only a baseline (no numbered sub-tests)
        if tier_id in (TierID.T0, TierID.T1):
            subtests.append(
                SubTestConfig(
                    id="baseline",
                    name=f"{tier_id.value} Baseline",
                    description=f"Baseline configuration for {tier_id.value}",
                    claude_md_path=None,
                    claude_dir_path=None,
                    extends_previous=False,
                )
            )
            return subtests

        # For T2+, look for numbered subdirectories
        if not tier_dir.exists():
            return subtests

        for subdir in sorted(tier_dir.iterdir()):
            if subdir.is_dir() and subdir.name.isdigit():
                claude_md = subdir / "CLAUDE.md"
                claude_dir = subdir / ".claude"

                # Load metadata if config.yaml exists
                config_file = subdir / "config.yaml"
                name = f"{tier_id.value} Sub-test {subdir.name}"
                description = f"Sub-test configuration {subdir.name}"

                if config_file.exists():
                    with open(config_file) as f:
                        config_data = yaml.safe_load(f) or {}
                    name = config_data.get("name", name)
                    description = config_data.get("description", description)

                subtests.append(
                    SubTestConfig(
                        id=subdir.name,
                        name=name,
                        description=description,
                        claude_md_path=claude_md if claude_md.exists() else None,
                        claude_dir_path=claude_dir if claude_dir.exists() else None,
                        extends_previous=True,
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

        Args:
            workspace: Path to the workspace directory
            tier_id: The tier being prepared
            subtest_id: The sub-test identifier
            baseline: Previous tier's winning baseline (if any)
        """
        # For T0, ensure no CLAUDE.md exists (clean slate)
        if tier_id == TierID.T0:
            claude_md = workspace / "CLAUDE.md"
            claude_dir = workspace / ".claude"
            if claude_md.exists():
                claude_md.unlink()
            if claude_dir.exists():
                shutil.rmtree(claude_dir)
            return

        # For T1, use defaults (no changes needed)
        if tier_id == TierID.T1:
            return

        # For T2+, apply inheritance and overlay
        tier_config = self.load_tier_config(tier_id)
        subtest = next((s for s in tier_config.subtests if s.id == subtest_id), None)

        if not subtest:
            raise ValueError(f"Sub-test {subtest_id} not found for tier {tier_id.value}")

        # Step 1: Copy baseline if extending from previous tier
        if baseline and subtest.extends_previous:
            self._copy_baseline(workspace, baseline)

        # Step 2: Overlay sub-test configuration
        self._overlay_subtest(workspace, subtest)

    def _copy_baseline(self, workspace: Path, baseline: TierBaseline) -> None:
        """Copy baseline configuration to workspace.

        Args:
            workspace: Target workspace directory
            baseline: Baseline configuration to copy
        """
        # Copy CLAUDE.md
        if baseline.claude_md_path and baseline.claude_md_path.exists():
            dest = workspace / "CLAUDE.md"
            shutil.copy(baseline.claude_md_path, dest)

        # Copy .claude directory
        if baseline.claude_dir_path and baseline.claude_dir_path.exists():
            dest = workspace / ".claude"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(baseline.claude_dir_path, dest)

    def _overlay_subtest(self, workspace: Path, subtest: SubTestConfig) -> None:
        """Overlay sub-test configuration onto workspace.

        This merges the sub-test's CLAUDE.md and .claude directory
        with any existing configuration from the baseline.

        Args:
            workspace: Target workspace directory
            subtest: Sub-test configuration to overlay
        """
        # Handle CLAUDE.md
        if subtest.claude_md_path and subtest.claude_md_path.exists():
            dest = workspace / "CLAUDE.md"
            if dest.exists() and subtest.extends_previous:
                # Merge: append sub-test content to existing
                existing = dest.read_text()
                addition = subtest.claude_md_path.read_text()
                merged = f"{existing}\n\n# Tier {subtest.id} Additions\n\n{addition}"
                dest.write_text(merged)
            else:
                # Replace
                shutil.copy(subtest.claude_md_path, dest)

        # Handle .claude directory
        if subtest.claude_dir_path and subtest.claude_dir_path.exists():
            dest = workspace / ".claude"
            if dest.exists() and subtest.extends_previous:
                # Merge: copy files from sub-test, overwriting conflicts
                self._merge_directories(subtest.claude_dir_path, dest)
            else:
                # Replace
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(subtest.claude_dir_path, dest)

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

    def get_baseline_for_subtest(
        self,
        tier_id: TierID,
        subtest_id: str,
        results_dir: Path,
    ) -> TierBaseline:
        """Create a baseline reference from a completed sub-test.

        Args:
            tier_id: The tier of the winning sub-test
            subtest_id: The winning sub-test ID
            results_dir: Directory containing the sub-test's results

        Returns:
            TierBaseline that can be passed to the next tier.
        """
        config_dir = results_dir / "config"

        return TierBaseline(
            tier_id=tier_id,
            subtest_id=subtest_id,
            claude_md_path=config_dir / "CLAUDE.md" if (config_dir / "CLAUDE.md").exists() else None,
            claude_dir_path=config_dir / ".claude" if (config_dir / ".claude").exists() else None,
        )

    def save_subtest_config(
        self,
        workspace: Path,
        results_dir: Path,
    ) -> None:
        """Save the workspace configuration to results directory.

        Preserves the CLAUDE.md and .claude directory used for this
        sub-test so it can be used as a baseline for the next tier.

        Args:
            workspace: Workspace with the configuration
            results_dir: Results directory to save to
        """
        config_dir = results_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Save CLAUDE.md
        claude_md = workspace / "CLAUDE.md"
        if claude_md.exists():
            shutil.copy(claude_md, config_dir / "CLAUDE.md")

        # Save .claude directory
        claude_dir = workspace / ".claude"
        if claude_dir.exists():
            dest = config_dir / ".claude"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(claude_dir, dest)
