"""Retrospective lifecycle functions for issue implementation.

Provides:
- Running /retrospective skill in Claude sessions
- Checking if retrospective needs re-run
"""

from __future__ import annotations

import logging
from pathlib import Path

from .git_utils import run

logger = logging.getLogger(__name__)


def run_retrospective(
    session_id: str,
    worktree_path: Path,
    issue_number: int,
    state_dir: Path,
    slot_id: int | None = None,
) -> bool:
    """Resume Claude session to run /retrospective.

    Args:
        session_id: Claude session ID
        worktree_path: Path to worktree
        issue_number: Issue number
        state_dir: Directory for state/log files
        slot_id: Worker slot ID (unused; kept for interface symmetry)

    Returns:
        True if retrospective completed successfully, False otherwise

    Runs from worktree directory so Claude can find the session.
    Output is logged to state_dir/retrospective-{issue_number}.log.

    """
    state_dir.mkdir(parents=True, exist_ok=True)
    log_file = state_dir / f"retrospective-{issue_number}.log"
    try:
        result = run(
            [
                "claude",
                "--resume",
                session_id,
                (
                    "/skills-registry-commands:retrospective"
                    " commit the results and create a PR."
                    " IMPORTANT: Only push skills to ProjectMnemosyne."
                    " Do NOT create files under .claude-plugin/ in this repo."
                ),
                "--print",
                "--permission-mode",
                "dontAsk",
                "--allowedTools",
                "Read,Write,Edit,Glob,Grep,Bash",
            ],
            cwd=worktree_path,
            timeout=600,  # 10 minutes
        )
        # Write output to log file
        log_file.write_text(result.stdout or "")
        logger.info(f"Retrospective completed for issue #{issue_number}")
        logger.info(f"Retrospective log: {log_file}")
        return True
    except Exception as e:  # broad catch: external claude process; non-blocking, must not propagate
        logger.warning(f"Retrospective failed for issue #{issue_number}: {e}")

        # Save failure output to log file
        error_output = f"FAILED: {e}\n"
        if hasattr(e, "stdout"):
            error_output += f"\nSTDOUT:\n{e.stdout or ''}"
        if hasattr(e, "stderr"):
            error_output += f"\nSTDERR:\n{e.stderr or ''}"
        log_file.write_text(error_output)

        # Non-blocking: never re-raise
        return False


def retrospective_needs_rerun(issue_number: int, state_dir: Path) -> bool:
    """Check if retrospective log indicates failure.

    Args:
        issue_number: Issue number
        state_dir: Directory containing retrospective log files

    Returns:
        True if retrospective needs to be re-run (missing or failed log)

    """
    log_file = state_dir / f"retrospective-{issue_number}.log"
    if not log_file.exists():
        return True
    try:
        content = log_file.read_text()
        return content.startswith("FAILED:")
    except OSError:
        return True
