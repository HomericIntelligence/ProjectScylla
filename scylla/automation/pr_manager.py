"""Pull request management functions for issue implementation.

Provides:
- Committing changes with secret file filtering
- Ensuring PR is created (fallback when Claude doesn't do it)
- Creating pull requests via GitHub CLI
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import cast

from .git_utils import run
from .github_api import _gh_call, fetch_issue_info, gh_pr_create
from .prompts import get_pr_description
from .status_tracker import StatusTracker

logger = logging.getLogger(__name__)

_SECRET_FILES = {
    ".env",
    ".secret",
    "credentials.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
_SECRET_EXTENSIONS = {".key", ".pem", ".pfx", ".p12"}


def commit_changes(issue_number: int, worktree_path: Path) -> None:
    """Commit changes in worktree, filtering out secret files.

    Args:
        issue_number: Issue number (used in commit message and error text)
        worktree_path: Path to git worktree

    Raises:
        RuntimeError: If there are no changes, or all changes are secret files.

    """
    # Check if there are changes
    result = run(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        capture_output=True,
    )

    if not result.stdout.strip():
        raise RuntimeError(
            f"No changes to commit for issue #{issue_number}. "
            "Check if the implementation was successful or if the plan needs revision."
        )

    # Parse git status --porcelain output to get all changed files
    # Format: XY filename or XY "quoted filename" for special chars
    # X = index status, Y = worktree status
    # Common codes: M (modified), A (added), D (deleted), R (renamed), ?? (untracked)
    files_to_add = []

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        # Parse status code and filename
        # Format: "XY filename" where X and Y are status codes
        # Position 0-1: status codes, position 2: space, position 3+: filename
        status = line[:2]
        filename_part = line[3:]  # Don't strip - filename starts at position 3

        # Handle renamed files (format: "old -> new")
        if status.startswith("R") and " -> " in filename_part:
            filename_part = filename_part.split(" -> ", 1)[1]

        # Handle quoted filenames (git quotes names with special chars)
        if filename_part.startswith('"') and filename_part.endswith('"'):
            # Remove quotes - git uses C-style escaping
            filename_part = filename_part[1:-1]

        # Check if file is a potential secret
        filename = Path(filename_part).name

        # Skip secret files (never stage these)
        if filename in _SECRET_FILES or any(filename.endswith(ext) for ext in _SECRET_EXTENSIONS):
            logger.warning(f"Skipping potential secret file: {filename_part}")
            continue

        files_to_add.append(filename_part)

    if not files_to_add:
        raise RuntimeError(
            f"No non-secret files to commit for issue #{issue_number}. "
            "All changes appear to be secret files."
        )

    # Stage the files
    run(["git", "add", *files_to_add], cwd=worktree_path)

    # Generate commit message
    issue = fetch_issue_info(issue_number)
    commit_msg = f"""feat: Implement #{issue_number}

{issue.title}

Closes #{issue_number}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
"""

    # Commit
    run(
        ["git", "commit", "-m", commit_msg],
        cwd=worktree_path,
    )


def ensure_pr_created(
    issue_number: int,
    branch_name: str,
    worktree_path: Path,
    auto_merge: bool = False,
    status_tracker: StatusTracker | None = None,
    slot_id: int | None = None,
) -> int:
    """Ensure commit is pushed and PR is created (fallback if Claude didn't do it).

    Args:
        issue_number: Issue number
        branch_name: Git branch name
        worktree_path: Path to worktree
        auto_merge: Whether to enable auto-merge on the PR
        status_tracker: StatusTracker instance for slot updates (optional)
        slot_id: Worker slot ID for status updates

    Returns:
        PR number

    Raises:
        RuntimeError: If commit doesn't exist or PR creation fails

    """

    def _update_slot(msg: str) -> None:
        if slot_id is not None and status_tracker is not None:
            status_tracker.update_slot(slot_id, msg)

    # Check if commit exists
    _update_slot(f"#{issue_number}: Checking commit")
    result = run(
        ["git", "log", "-1", "--oneline"],
        cwd=worktree_path,
        capture_output=True,
    )
    if not result.stdout.strip():
        raise RuntimeError(
            f"No commit found for issue #{issue_number}. Claude did not create any commits."
        )

    logger.info(f"✓ Commit exists: {result.stdout.strip()[:80]}")

    # Check if branch was pushed, if not push it
    _update_slot(f"#{issue_number}: Pushing branch")
    result = run(
        ["git", "ls-remote", "--heads", "origin", branch_name],
        cwd=worktree_path,
        capture_output=True,
        check=False,
    )
    if not result.stdout.strip():
        logger.warning(f"Branch {branch_name} not pushed, pushing now...")
        run(["git", "push", "-u", "origin", branch_name], cwd=worktree_path)
        logger.info(f"✓ Pushed branch {branch_name} to origin")
    else:
        logger.info(f"✓ Branch {branch_name} already on origin")

    # Check if PR exists, if not create it
    _update_slot(f"#{issue_number}: Creating PR")
    pr_number = None
    try:
        result = _gh_call(["pr", "list", "--head", branch_name, "--json", "number", "--limit", "1"])
        pr_data = json.loads(result.stdout)
        if pr_data and len(pr_data) > 0:
            pr_number = cast(int, pr_data[0]["number"])
            logger.info(f"✓ PR #{pr_number} already exists")
            return pr_number
    except Exception as e:  # broad catch: gh CLI + JSON parsing; fallback is to create PR
        logger.debug(f"Could not find existing PR: {e}")

    # PR doesn't exist, create it
    logger.warning(f"No PR found for branch {branch_name}, creating one...")
    pr_number = create_pr(issue_number, branch_name, auto_merge)
    logger.info(f"✓ Created PR #{pr_number}")
    return pr_number


def create_pr(issue_number: int, branch_name: str, auto_merge: bool = False) -> int:
    """Create pull request for issue.

    Args:
        issue_number: Issue number
        branch_name: Git branch name
        auto_merge: Whether to enable auto-merge on the PR

    Returns:
        PR number

    """
    issue = fetch_issue_info(issue_number)

    pr_title = f"feat: {issue.title}"
    pr_body = get_pr_description(
        issue_number=issue_number,
        summary=f"Implements #{issue_number}",
        changes="- Automated implementation via Claude Code",
        testing="- Automated tests included",
    )

    return gh_pr_create(
        branch=branch_name,
        title=pr_title,
        body=pr_body,
        auto_merge=auto_merge,
    )
