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

    def __init__(self, base_dir: Path | None = None):
        """Initialize worktree manager.

        Args:
            base_dir: Base directory for worktrees (default: repo_root/.worktrees)

        """
        self.repo_root = get_repo_root()
        if base_dir is None:
            base_dir = self.repo_root / ".worktrees"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.worktrees: dict[int, Path] = {}
        self.lock = threading.Lock()

        logger.debug(f"Initialized WorktreeManager at {self.base_dir}")

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
                shutil.rmtree(worktree_path)

            try:
                # Create worktree with new branch from main
                run(
                    [
                        "git",
                        "worktree",
                        "add",
                        "-b",
                        branch_name,
                        str(worktree_path),
                        "origin/main",
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
