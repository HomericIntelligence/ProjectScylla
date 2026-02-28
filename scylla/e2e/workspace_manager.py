"""Workspace manager for E2E experiments using git worktrees.

This module provides efficient workspace management by cloning a repository once
and using git worktrees for each test run, reducing storage and network overhead.
"""

from __future__ import annotations

import fcntl
import hashlib
import logging
import subprocess
import time
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
        repos_dir: Path | None = None,
    ) -> None:
        """Initialize workspace manager.

        Args:
            experiment_dir: Root directory for the experiment
            repo_url: Git repository URL to clone
            commit: Specific commit to checkout (optional)
            repos_dir: Optional directory for centralized repo clones.
                      If provided, clones are shared across experiments.
                      If None, uses legacy per-experiment layout.

        """
        self.experiment_dir = experiment_dir
        self.repo_url = repo_url
        self.commit = commit
        self.repos_dir = repos_dir
        self._is_setup = False
        self._worktree_count = 0

        # Calculate base_repo path based on repos_dir
        if repos_dir is not None:
            # Centralized clone: use deterministic UUID from repo URL
            repo_uuid = hashlib.sha256(repo_url.encode()).hexdigest()[:16]
            self.base_repo = repos_dir / repo_uuid
        else:
            # Legacy per-experiment clone
            self.base_repo = experiment_dir / "repo"

    @classmethod
    def from_existing(
        cls,
        base_repo: Path,
        repo_url: str,
        commit: str | None,
    ) -> WorkspaceManager:
        """Create a WorkspaceManager for an already-cloned base repository.

        Used in child processes (parallel_executor._run_subtest_in_process) where
        the repository was cloned by the parent process and the child just needs
        a WorkspaceManager instance that points at the existing clone.

        Args:
            base_repo: Path to the already-cloned repository root
            repo_url: Git repository URL (for metadata)
            commit: Commit hash (for metadata)

        Returns:
            WorkspaceManager with _is_setup=True pointing at base_repo

        """
        instance = cls(
            experiment_dir=base_repo.parent,
            repo_url=repo_url,
            commit=commit,
        )
        instance._is_setup = True
        instance.base_repo = base_repo
        return instance

    def setup_base_repo(self) -> None:
        """Clone repository once at experiment start.

        For centralized repos (repos_dir set):
        - Creates a full clone shared across experiments
        - Uses file locking for parallel safety
        - Reuses existing clone if present
        - Only fetches specific commits (no checkout in base)

        For per-experiment repos (repos_dir=None):
        - Creates shallow clone in experiment directory
        - Checks out specific commit in base repo

        Uses exponential backoff retry for transient network errors.
        """
        if self._is_setup:
            logger.debug("Base repo already set up")
            return

        # Create parent directory
        self.base_repo.parent.mkdir(parents=True, exist_ok=True)

        # Use file-based locking for centralized repos to handle parallel access
        lock_path = self.base_repo.parent / f".{self.base_repo.name}.lock"
        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                # Check if base repo already exists (centralized repos reuse)
                if self.base_repo.exists() and (self.base_repo / ".git").exists():
                    logger.info(f"Reusing existing base repo: {self.base_repo}")
                else:
                    logger.info(f"Cloning base repo to {self.base_repo}")

                    # Determine clone depth based on layout
                    # Centralized repos need full clone for commit availability
                    # Per-experiment repos can use shallow clone
                    use_shallow = self.repos_dir is None

                    clone_cmd = ["git", "clone"]
                    if use_shallow:
                        clone_cmd.append("--depth=1")
                    clone_cmd.extend([self.repo_url, str(self.base_repo)])

                    # Retry logic for transient network errors
                    max_retries = 3
                    base_delay = 1.0

                    for attempt in range(max_retries):
                        result = subprocess.run(
                            clone_cmd,
                            capture_output=True,
                            text=True,
                        )

                        if result.returncode == 0:
                            break

                        stderr = result.stderr.lower()

                        # Detect transient network errors (retry-able)
                        transient_patterns = [
                            "connection reset",
                            "connection refused",
                            "network unreachable",
                            "network is unreachable",
                            "temporary failure",
                            "could not resolve host",
                            "curl 56",  # RPC failed curl error
                            "timed out",
                            "early eof",
                            "recv failure",
                        ]

                        is_transient = any(pattern in stderr for pattern in transient_patterns)

                        # Fail immediately on non-transient errors or last attempt
                        if not is_transient or attempt == max_retries - 1:
                            raise RuntimeError(f"Failed to clone repository: {result.stderr}")

                        # Exponential backoff: 1s, 2s, 4s
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Git clone failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {delay}s: {result.stderr.strip()}"
                        )
                        time.sleep(delay)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

        # Handle commit checkout/fetch based on layout
        if self.commit:
            if self.repos_dir is not None:
                # Centralized: only ensure commit is available, no checkout in base
                self._ensure_commit_available()
            else:
                # Legacy: checkout commit in base repo
                self._checkout_commit()

        self._is_setup = True
        logger.info("Base repo setup complete")

    def _checkout_commit(self) -> None:
        """Fetch and checkout specific commit in base repo (legacy per-experiment layout)."""
        if self.commit is None:
            raise RuntimeError("commit must be set before calling _checkout_commit")
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

    def _ensure_commit_available(self) -> None:
        """Ensure the target commit exists in repo object store (centralized layout).

        Only fetches the commit into the object store without checking it out.
        Base repo HEAD stays on default branch so it can be shared across experiments.
        """
        if self.commit is None:
            raise RuntimeError("commit must be set before calling _ensure_commit_available")
        # Check if commit already exists in object store
        check_cmd = ["git", "-C", str(self.base_repo), "cat-file", "-t", self.commit]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.debug(f"Commit {self.commit} already available in object store")
            return  # Already available

        # Fetch the specific commit
        fetch_cmd = ["git", "-C", str(self.base_repo), "fetch", "origin", self.commit]
        result = subprocess.run(fetch_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.debug(f"Fetch returned non-zero (may be ok): {result.stderr}")

    def create_worktree(
        self,
        workspace_path: Path,
        tier_id: str | None = None,
        subtest_id: str | None = None,
        run_number: int | None = None,
    ) -> tuple[list[str], str]:
        """Create a worktree for a single run with named branch.

        Args:
            workspace_path: Path where the worktree should be created
            tier_id: Optional tier ID (e.g., "T0", "T1") for branch naming
            subtest_id: Optional subtest ID (e.g., "01", "02") for branch naming
            run_number: Optional run number for branch naming (e.g., 1, 2, 3)

        Returns:
            Tuple of (command_list, branch_name) for logging/reproducibility

        Raises:
            RuntimeError: If base repo not set up or worktree creation fails

        """
        if not self._is_setup:
            raise RuntimeError("Base repo not set up. Call setup_base_repo() first.")

        # Ensure parent directory exists
        workspace_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate branch name from tier/subtest/run or fall back to counter
        if tier_id and subtest_id:
            if run_number is not None:
                branch_name = f"{tier_id}_{subtest_id}_run_{run_number:02d}"
            else:
                branch_name = f"{tier_id}_{subtest_id}"
        else:
            self._worktree_count += 1
            branch_name = f"worktree-{self._worktree_count}"

        # Create worktree with named branch and commit in a single step
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
