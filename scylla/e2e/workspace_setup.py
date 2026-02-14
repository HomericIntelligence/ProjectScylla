"""Workspace setup and management for E2E testing.

This module handles:
- Setting up git worktrees for isolated test execution
- Committing test configurations
- Moving failed runs to .failed/ directory
"""

from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scylla.e2e.command_logger import CommandLogger
    from scylla.e2e.models import TierID

logger = logging.getLogger(__name__)


def _move_to_failed(run_dir: Path, attempt: int = 1) -> Path:
    """Move a failed run directory to .failed/ subdirectory.

    Args:
        run_dir: Path to the run directory (e.g., results/T0/01/run_01/)
        attempt: Attempt number for naming (default 1)

    Returns:
        Path to the new location in .failed/

    """
    failed_dir = run_dir.parent / ".failed"
    failed_dir.mkdir(parents=True, exist_ok=True)

    # Generate new name: run_03 -> .failed/run_03_attempt_01
    run_name = run_dir.name
    new_name = f"{run_name}_attempt_{attempt:02d}"
    new_path = failed_dir / new_name

    # Find next available attempt number if exists
    while new_path.exists():
        attempt += 1
        new_name = f"{run_name}_attempt_{attempt:02d}"
        new_path = failed_dir / new_name

    # Move the directory
    shutil.move(str(run_dir), str(new_path))
    logger.info(f"Moved failed run to {new_path}")

    return new_path


def _commit_test_config(workspace: Path) -> None:
    """Commit test configuration files so agent sees them as existing state.

    Commits CLAUDE.md and .claude/ directory if they exist, so the agent
    sees them as part of the repository's existing state rather than
    uncommitted changes.

    Args:
        workspace: Path to the workspace directory

    """
    # Stage CLAUDE.md if it exists
    claude_md = workspace / "CLAUDE.md"
    if claude_md.exists():
        subprocess.run(
            ["git", "add", "CLAUDE.md"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

    # Stage .claude/ directory if it exists
    claude_dir = workspace / ".claude"
    if claude_dir.exists():
        subprocess.run(
            ["git", "add", ".claude/"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

    # Check if there are staged changes
    status_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=workspace,
        capture_output=True,
        timeout=30,
    )

    # If there are staged changes, commit them
    if status_result.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", "[scylla] Initialize test configuration"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )


def _setup_workspace(
    workspace: Path,
    command_logger: CommandLogger,
    tier_id: TierID,
    subtest_id: str,
    run_number: int,
    base_repo: Path,
    task_commit: str | None = None,
) -> None:
    """Set up workspace using git worktree from base repo with named branch.

    Args:
        workspace: Target workspace directory
        command_logger: Logger for commands
        tier_id: Tier identifier for branch naming
        subtest_id: Subtest identifier for branch naming
        run_number: Run number for branch naming
        base_repo: Base repository path
        task_commit: Optional commit hash to checkout

    """
    start_time = datetime.now(timezone.utc)

    # Ensure workspace path is absolute for git worktree
    workspace_abs = workspace.resolve()

    # Generate branch name with run number
    branch_name = f"{tier_id.value}_{subtest_id}_run_{run_number:02d}"

    # Log worktree creation phase
    _phase_log("WORKTREE", f"Creating worktree [{branch_name}] @ [{workspace_abs}]")

    # Create worktree with named branch and commit in a single step
    worktree_cmd = [
        "git",
        "-C",
        str(base_repo),
        "worktree",
        "add",
        "-b",
        branch_name,
        str(workspace_abs),
    ]
    if task_commit:
        worktree_cmd.append(task_commit)

    result = subprocess.run(
        worktree_cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    command_logger.log_command(
        cmd=worktree_cmd,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
        duration=duration,
    )

    # Handle branch already exists (resume scenario)
    if result.returncode != 0 and "already exists" in result.stderr:
        logger.info(f"Branch {branch_name} exists, attempting recovery for resume...")

        # Step 1: Remove stale worktree entry if it exists
        prune_cmd = [
            "git",
            "-C",
            str(base_repo),
            "worktree",
            "prune",
        ]
        subprocess.run(prune_cmd, capture_output=True, text=True, timeout=30)

        # Step 2: Try to remove existing worktree (may fail if already gone)
        remove_cmd = [
            "git",
            "-C",
            str(base_repo),
            "worktree",
            "remove",
            "--force",
            str(workspace_abs),
        ]
        subprocess.run(remove_cmd, capture_output=True, text=True, timeout=30)

        # Step 3: Delete the branch
        delete_branch_cmd = [
            "git",
            "-C",
            str(base_repo),
            "branch",
            "-D",
            branch_name,
        ]
        subprocess.run(delete_branch_cmd, capture_output=True, text=True, timeout=30)

        # Step 4: Clean up workspace directory if exists
        if workspace_abs.exists():
            shutil.rmtree(workspace_abs)

        # Step 5: Retry worktree creation (commit already included in worktree_cmd)
        result = subprocess.run(
            worktree_cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree even after cleanup: {result.stderr}")

    elif result.returncode != 0:
        raise RuntimeError(f"Failed to create worktree: {result.stderr}")

    # Save worktree creation command (create only, no cleanup)
    subtest_dir = workspace.parent
    worktree_script = subtest_dir / "worktree_create.sh"
    script_lines = [
        "#!/bin/bash",
        f"# Worktree: {branch_name} @ {workspace_abs}",
        " ".join(shlex.quote(arg) for arg in worktree_cmd),
    ]
    if task_commit:
        checkout_cmd = ["git", "-C", str(workspace_abs), "checkout", task_commit]
        script_lines.append(" ".join(shlex.quote(arg) for arg in checkout_cmd))
    worktree_script.write_text("\n".join(script_lines) + "\n")
    worktree_script.chmod(0o755)


def _phase_log(phase: str, message: str) -> None:
    """Log a phase message with timestamp and prefix.

    Args:
        phase: Phase identifier (WORKTREE, AGENT, JUDGE)
        message: Message content

    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    logger.info(f"{timestamp} [{phase}] - {message}")
