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
            name = f"{tier_id.value} {subtest_name_suffix}" if subtest_name_suffix else f"{tier_id.value} Sub-test {subtest_id}"
            description = f"Sub-test configuration {dir_name}"

            # T0 sub-tests have special handling for extends_previous
            # 00-empty and 01-vanilla don't extend; 02+ may extend
            extends_previous = tier_id != TierID.T0 or int(subtest_id) >= 2

            if config_file.exists():
                with open(config_file) as f:
                    config_data = yaml.safe_load(f) or {}
                name = config_data.get("name", name)
                description = config_data.get("description", description)
                # Allow config to override extends_previous
                extends_previous = config_data.get("extends_previous", extends_previous)

            subtests.append(
                SubTestConfig(
                    id=subtest_id,
                    name=name,
                    description=description,
                    claude_md_path=claude_md if claude_md.exists() else None,
                    claude_dir_path=claude_dir if claude_dir.exists() else None,
                    extends_previous=extends_previous,
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
