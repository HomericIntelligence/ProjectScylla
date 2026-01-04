"""Workspace manager for E2E experiments using git worktrees.

Python Justification: Required for subprocess orchestration and git operations.

This module provides efficient workspace management by cloning a repository once
and using git worktrees for each test run, reducing storage and network overhead.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages git worktrees for experiment runs.

    Instead of cloning the repository for each test run, this manager:
    1. Clones the repo once at experiment start
    2. Creates lightweight worktrees for each run
    3. Shares the .git directory across all worktrees

    This reduces storage by ~99% and speeds up workspace setup significantly.
    """

    def __init__(
        self,
        experiment_dir: Path,
        repo_url: str,
        commit: str | None = None,
    ) -> None:
        """Initialize workspace manager.

        Args:
            experiment_dir: Root directory for the experiment
            repo_url: Git repository URL to clone
            commit: Specific commit to checkout (optional)
        """
        self.experiment_dir = experiment_dir
        self.repo_url = repo_url
        self.commit = commit
        self.base_repo = experiment_dir / "repo"
        self._is_setup = False
        self._worktree_count = 0

    def setup_base_repo(self) -> None:
        """Clone repository once at experiment start.

        Creates a shallow clone with the specified commit checked out.
        This is the single source for all worktrees.
        """
        if self._is_setup:
            logger.debug("Base repo already set up")
            return

        logger.info(f"Cloning base repo to {self.base_repo}")

        # Create experiment directory if needed
        self.experiment_dir.mkdir(parents=True, exist_ok=True)

        # Clone with depth=1 for efficiency
        clone_cmd = [
            "git",
            "clone",
            "--depth=1",
            self.repo_url,
            str(self.base_repo),
        ]

        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone repository: {result.stderr}")

        # If specific commit requested, fetch and checkout
        if self.commit:
            self._checkout_commit()

        self._is_setup = True
        logger.info("Base repo setup complete")

    def _checkout_commit(self) -> None:
        """Fetch and checkout specific commit in base repo."""
        # Try to fetch the specific commit
        fetch_cmd = [
            "git",
            "-C",
            str(self.base_repo),
            "fetch",
            "--depth=1",
            "origin",
            self.commit,
        ]

        result = subprocess.run(
            fetch_cmd,
            capture_output=True,
            text=True,
        )

        # Fetch may fail if commit is already in shallow clone, that's ok
        if result.returncode != 0:
            logger.debug(f"Fetch returned non-zero (may be ok): {result.stderr}")

        # Checkout the commit
        checkout_cmd = [
            "git",
            "-C",
            str(self.base_repo),
            "checkout",
            self.commit,
        ]

        result = subprocess.run(
            checkout_cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to checkout commit {self.commit}: {result.stderr}")

    def create_worktree(
        self,
        workspace_path: Path,
        tier_id: str | None = None,
        subtest_id: str | None = None,
    ) -> tuple[list[str], str]:
        """Create a worktree for a single run with named branch.

        Args:
            workspace_path: Path where the worktree should be created
            tier_id: Optional tier ID (e.g., "T0", "T1") for branch naming
            subtest_id: Optional subtest ID (e.g., "01", "02") for branch naming

        Returns:
            Tuple of (command_list, branch_name) for logging/reproducibility

        Raises:
            RuntimeError: If base repo not set up or worktree creation fails
        """
        if not self._is_setup:
            raise RuntimeError("Base repo not set up. Call setup_base_repo() first.")

        # Ensure parent directory exists
        workspace_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate branch name from tier/subtest or fall back to counter
        if tier_id and subtest_id:
            branch_name = f"{tier_id}_{subtest_id}"
        else:
            self._worktree_count += 1
            branch_name = f"worktree-{self._worktree_count}"

        # Create worktree with named branch instead of detached HEAD
        worktree_cmd = [
            "git",
            "-C",
            str(self.base_repo),
            "worktree",
            "add",
            "-b",
            branch_name,
            str(workspace_path),
        ]

        # Add commit reference if specified
        if self.commit:
            worktree_cmd.append(self.commit)

        result = subprocess.run(
            worktree_cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree at {workspace_path}: {result.stderr}")

        logger.debug(f"Created worktree at {workspace_path} on branch {branch_name}")

        return worktree_cmd, branch_name

    def cleanup_worktree(self, workspace_path: Path, branch_name: str | None = None) -> None:
        """Remove a worktree after run completion and delete its branch.

        Args:
            workspace_path: Path to the worktree to remove
            branch_name: Optional branch name to delete after removing worktree
        """
        if not workspace_path.exists():
            return

        # Remove the worktree
        remove_cmd = [
            "git",
            "-C",
            str(self.base_repo),
            "worktree",
            "remove",
            "--force",
            str(workspace_path),
        ]

        result = subprocess.run(
            remove_cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning(f"Failed to remove worktree: {result.stderr}")
            return

        # Delete the branch if specified
        if branch_name:
            delete_branch_cmd = [
                "git",
                "-C",
                str(self.base_repo),
                "branch",
                "-D",
                branch_name,
            ]

            result = subprocess.run(
                delete_branch_cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"Failed to delete branch {branch_name}: {result.stderr}")

    def cleanup_all(self) -> None:
        """Cleanup all worktrees and prune stale entries."""
        if not self.base_repo.exists():
            return

        # Prune worktrees that no longer exist
        prune_cmd = [
            "git",
            "-C",
            str(self.base_repo),
            "worktree",
            "prune",
        ]

        subprocess.run(prune_cmd, capture_output=True, text=True)
        logger.debug("Pruned stale worktrees")

    @property
    def is_setup(self) -> bool:
        """Check if base repo is set up."""
        return self._is_setup
