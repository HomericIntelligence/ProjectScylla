"""Git worktree management for parallel issue implementation.

Provides:
- Thread-safe worktree creation and cleanup
- Branch management
- Worktree state tracking
"""

import logging
import shutil
import threading
from pathlib import Path

from .git_utils import get_repo_root, run

logger = logging.getLogger(__name__)


class WorktreeManager:
    """Thread-safe manager for git worktrees.

    Allows parallel issue implementation in isolated worktrees.
    """

    def __init__(self, base_dir: Path | None = None, base_branch: str | None = None):
        """Initialize worktree manager.

        Args:
            base_dir: Base directory for worktrees (default: repo_root/.worktrees)
            base_branch: Base branch for worktrees (default: auto-detect from origin/HEAD)

        """
        self.repo_root = get_repo_root()
        if base_dir is None:
            base_dir = self.repo_root / ".worktrees"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect base branch if not specified
        if base_branch is None:
            try:
                result = run(
                    ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "--short"],
                    cwd=self.repo_root,
                    capture_output=True,
                )
                base_branch = result.stdout.strip()
                logger.debug(f"Auto-detected base branch: {base_branch}")
            except Exception:
                # Fallback to origin/main if auto-detection fails
                base_branch = "origin/main"
                logger.warning("Could not auto-detect base branch, using origin/main")

        self.base_branch = base_branch
        self.worktrees: dict[int, Path] = {}
        self.lock = threading.Lock()

        logger.debug(
            f"Initialized WorktreeManager at {self.base_dir}, base branch: {self.base_branch}"
        )

    def create_worktree(
        self,
        issue_number: int,
        branch_name: str | None = None,
    ) -> Path:
        """Create a new worktree for an issue.

        Args:
            issue_number: Issue number
            branch_name: Branch name (default: {issue_number}-auto)

        Returns:
            Path to worktree directory

        Raises:
            RuntimeError: If worktree creation fails

        """
        with self.lock:
            if issue_number in self.worktrees:
                logger.warning(f"Worktree for issue #{issue_number} already exists")
                return self.worktrees[issue_number]

            if branch_name is None:
                branch_name = f"{issue_number}-auto"

            worktree_path = self.base_dir / f"issue-{issue_number}"

            # Remove existing directory if present
            if worktree_path.exists():
                logger.warning(f"Removing existing worktree directory: {worktree_path}")
                # Try git worktree remove first to clean up git metadata
                try:
                    run(
                        ["git", "worktree", "remove", "--force", str(worktree_path)],
                        cwd=self.repo_root,
                        check=False,
                    )
                except Exception as e:
                    logger.debug(f"git worktree remove failed (expected if not a worktree): {e}")

                # Fallback to direct directory removal
                if worktree_path.exists():
                    shutil.rmtree(worktree_path)

                # Prune stale worktree metadata
                try:
                    run(["git", "worktree", "prune"], cwd=self.repo_root, check=False)
                except Exception as e:
                    logger.debug(f"git worktree prune failed: {e}")

            try:
                # Check if branch already exists
                branch_exists = False
                try:
                    result = run(
                        ["git", "rev-parse", "--verify", branch_name],
                        cwd=self.repo_root,
                        capture_output=True,
                        check=False,
                    )
                    branch_exists = result.returncode == 0
                except Exception:
                    branch_exists = False

                if branch_exists:
                    logger.info(f"Branch {branch_name} already exists, reusing it")
                    # Create worktree from existing branch
                    run(
                        [
                            "git",
                            "worktree",
                            "add",
                            str(worktree_path),
                            branch_name,
                        ],
                        cwd=self.repo_root,
                    )
                else:
                    # Create worktree with new branch from base branch
                    run(
                        [
                            "git",
                            "worktree",
                            "add",
                            "-b",
                            branch_name,
                            str(worktree_path),
                            self.base_branch,
                        ],
                        cwd=self.repo_root,
                    )

                self.worktrees[issue_number] = worktree_path
                logger.info(f"Created worktree for issue #{issue_number} at {worktree_path}")
                return worktree_path

            except Exception as e:
                raise RuntimeError(f"Failed to create worktree: {e}") from e

    def remove_worktree(self, issue_number: int, force: bool = False) -> None:
        """Remove a worktree.

        Args:
            issue_number: Issue number
            force: Force removal even with uncommitted changes

        Raises:
            RuntimeError: If worktree removal fails

        """
        with self.lock:
            if issue_number not in self.worktrees:
                logger.warning(f"No worktree found for issue #{issue_number}")
                return

            worktree_path = self.worktrees[issue_number]

            try:
                # Remove worktree
                cmd = ["git", "worktree", "remove", str(worktree_path)]
                if force:
                    cmd.append("--force")

                run(cmd, cwd=self.repo_root)

                del self.worktrees[issue_number]
                logger.info(f"Removed worktree for issue #{issue_number}")

            except Exception as e:
                raise RuntimeError(f"Failed to remove worktree: {e}") from e

    def get_worktree(self, issue_number: int) -> Path | None:
        """Get worktree path for an issue.

        Args:
            issue_number: Issue number

        Returns:
            Worktree path or None if not found

        """
        with self.lock:
            return self.worktrees.get(issue_number)

    def cleanup_all(self, force: bool = False) -> None:
        """Remove all managed worktrees.

        Args:
            force: Force removal even with uncommitted changes

        Note:
            Known limitation: Releases lock between iterations to avoid
            holding it during slow git operations. If concurrent create_worktree
            is called, new worktrees may be added during cleanup. This is
            acceptable since cleanup_all is typically called during shutdown.

        """
        with self.lock:
            issue_numbers = list(self.worktrees.keys())

        for issue_num in issue_numbers:
            try:
                self.remove_worktree(issue_num, force=force)
            except Exception as e:
                logger.error(f"Failed to remove worktree for issue #{issue_num}: {e}")

    def prune_worktrees(self) -> None:
        """Prune stale worktree administrative files.

        Useful for cleaning up after manual worktree deletion.
        """
        try:
            run(["git", "worktree", "prune"], cwd=self.repo_root)
            logger.info("Pruned stale worktrees")
        except Exception as e:
            logger.error(f"Failed to prune worktrees: {e}")

    def list_worktrees(self) -> list[dict[str, str]]:
        """List all git worktrees in the repository.

        Returns:
            List of worktree info dictionaries

        """
        try:
            result = run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.repo_root,
                capture_output=True,
            )

            worktrees = []
            current: dict[str, str] = {}

            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    if current:
                        worktrees.append(current)
                        current = {}
                    continue

                if line.startswith("worktree "):
                    current["path"] = line.split(" ", 1)[1]
                elif line.startswith("branch "):
                    current["branch"] = line.split(" ", 1)[1]
                elif line.startswith("HEAD "):
                    current["commit"] = line.split(" ", 1)[1]

            if current:
                worktrees.append(current)

            return worktrees

        except Exception as e:
            logger.error(f"Failed to list worktrees: {e}")
            return []

    def ensure_branch_deleted(self, branch_name: str) -> None:
        """Ensure a branch is deleted from local and remote.

        Args:
            branch_name: Branch name to delete

        """
        # Delete local branch
        try:
            run(
                ["git", "branch", "-D", branch_name],
                cwd=self.repo_root,
                check=False,
            )
            logger.debug(f"Deleted local branch {branch_name}")
        except Exception as e:
            logger.warning(f"Failed to delete local branch {branch_name}: {e}")

        # Delete remote branch
        try:
            run(
                ["git", "push", "origin", "--delete", branch_name],
                cwd=self.repo_root,
                check=False,
            )
            logger.debug(f"Deleted remote branch {branch_name}")
        except Exception as e:
            logger.warning(f"Failed to delete remote branch {branch_name}: {e}")
