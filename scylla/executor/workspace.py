"""Workspace management for agent test execution.

This module handles git repository cloning, workspace directory management,
and cleanup operations to create isolated test environments.
(Mojo limitation - cannot capture stdout/stderr).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path


class WorkspaceError(Exception):
    """Exception raised for workspace operations.

    Attributes:
        message: Human-readable error description.
        command: The command that failed (if applicable).
        stderr: Standard error output from failed command (if available).

    """

    def __init__(
        self,
        message: str,
        command: str | None = None,
        stderr: str | None = None,
    ) -> None:
        """Initialize WorkspaceError.

        Args:
            message: Human-readable error description.
            command: The command that failed (if applicable).
            stderr: Standard error output from failed command.

        """
        self.message = message
        self.command = command
        self.stderr = stderr
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return formatted error message."""
        parts = [self.message]
        if self.command:
            parts.append(f"Command: {self.command}")
        if self.stderr:
            parts.append(f"Stderr: {self.stderr}")
        return "\n".join(parts)


def _run_git_command(
    args: list[str],
    cwd: Path | None = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> subprocess.CompletedProcess[str]:
    """Run git command with retry logic for transient failures.

    Implements exponential backoff for network-related failures.
    Does NOT retry on permanent failures like authentication or 404 errors.

    Args:
        args: Git command arguments (without 'git' prefix).
        cwd: Working directory for the command.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for exponential backoff.

    Returns:
        CompletedProcess result from successful execution.

    Raises:
        WorkspaceError: If command fails after all retries.

    """
    command = ["git"] + args
    command_str = " ".join(command)

    # Patterns that indicate non-retryable errors
    non_retryable_patterns = [
        "Authentication failed",
        "Permission denied",
        "Repository not found",
        "fatal: Could not read from remote repository",
        "Invalid username or password",
        "not a git repository",
    ]

    last_error: subprocess.CompletedProcess[str] | None = None

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return result

            # Check if this is a non-retryable error
            stderr_lower = result.stderr.lower()
            for pattern in non_retryable_patterns:
                if pattern.lower() in stderr_lower:
                    raise WorkspaceError(
                        message=f"Git command failed (non-retryable): {pattern}",
                        command=command_str,
                        stderr=result.stderr.strip(),
                    )

            last_error = result

            # Wait before retry with exponential backoff
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                time.sleep(delay)

        except OSError as e:
            raise WorkspaceError(
                message=f"Failed to execute git command: {e}",
                command=command_str,
            ) from e

    # All retries exhausted
    stderr = last_error.stderr.strip() if last_error else "Unknown error"
    raise WorkspaceError(
        message=f"Git command failed after {max_retries} attempts",
        command=command_str,
        stderr=stderr,
    )


def create_workspace(
    test_id: str,
    model_id: str,
    run_number: int,
    timestamp: str | None = None,
    base_path: Path | str = Path("runs"),
) -> Path:
    """Create isolated workspace directory for a test run.

    Creates the following directory structure:
    ```
    runs/<test-id>/<timestamp>/<model-id>/run-NN/
    ├── workspace/     # Git clone destination (returned path)
    └── logs/          # Log files directory
        ├── stdout.log
        ├── stderr.log
        └── agent.log
    ```

    Args:
        test_id: Unique test identifier (e.g., "001-justfile-to-makefile").
        model_id: Model identifier (e.g., "claude-opus-4-5-20251101").
        run_number: Run number (1-99), will be zero-padded.
        timestamp: ISO-8601 timestamp. If None, uses current time.
        base_path: Base directory for runs (default: "runs").

    Returns:
        Path to the workspace directory (for git clone).

    Raises:
        WorkspaceError: If directory creation fails.
        ValueError: If run_number is out of range.

    """
    if not 1 <= run_number <= 99:
        raise ValueError(f"run_number must be 1-99, got: {run_number}")

    if not test_id or not test_id.strip():
        raise ValueError("test_id cannot be empty")

    if not model_id or not model_id.strip():
        raise ValueError("model_id cannot be empty")

    # Normalize inputs
    test_id = test_id.strip()
    model_id = model_id.strip()

    # Generate timestamp if not provided
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    # Ensure base_path is a Path
    base_path = Path(base_path)

    # Build directory structure
    run_dir = base_path / test_id / timestamp / model_id / f"run-{run_number:02d}"
    workspace_dir = run_dir / "workspace"
    logs_dir = run_dir / "logs"

    try:
        # Create directories
        workspace_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Create empty log files
        (logs_dir / "stdout.log").touch()
        (logs_dir / "stderr.log").touch()
        (logs_dir / "agent.log").touch()

    except OSError as e:
        raise WorkspaceError(
            message=f"Failed to create workspace directory: {e}",
        ) from e

    return workspace_dir


def clone_repo(
    repo_url: str,
    workspace_path: Path | str,
    depth: int = 1,
) -> None:
    """Clone repository to workspace with shallow clone.

    Uses shallow clone (--depth=1) by default to minimize download time
    and disk usage.

    Args:
        repo_url: Git repository URL (HTTPS or SSH).
        workspace_path: Path to clone into.
        depth: Shallow clone depth (default 1).

    Raises:
        WorkspaceError: If clone fails.
        ValueError: If repo_url is empty or invalid.

    """
    if not repo_url or not repo_url.strip():
        raise ValueError("repo_url cannot be empty")

    workspace_path = Path(workspace_path)

    if not workspace_path.exists():
        raise WorkspaceError(
            message=f"Workspace path does not exist: {workspace_path}",
        )

    # Clone directly into the workspace directory
    # Use '.' to clone into the existing directory
    args = ["clone", "--depth", str(depth), repo_url, "."]

    _run_git_command(args, cwd=workspace_path)


def checkout_hash(
    workspace_path: Path | str,
    git_hash: str,
) -> None:
    """Checkout specific git hash in workspace.

    For shallow clones, this first fetches the specific commit then
    performs the checkout. Results in a detached HEAD state (expected).

    Args:
        workspace_path: Path to cloned repository.
        git_hash: Full or short git hash to checkout.

    Raises:
        WorkspaceError: If checkout fails (hash not found, not a git repo, etc.).
        ValueError: If git_hash is empty.

    """
    if not git_hash or not git_hash.strip():
        raise ValueError("git_hash cannot be empty")

    workspace_path = Path(workspace_path)
    git_hash = git_hash.strip()

    if not workspace_path.exists():
        raise WorkspaceError(
            message=f"Workspace path does not exist: {workspace_path}",
        )

    if not (workspace_path / ".git").exists():
        raise WorkspaceError(
            message=f"Not a git repository: {workspace_path}",
        )

    # For shallow clones, we need to fetch the specific commit first
    # Use --depth=1 to keep it shallow
    fetch_args = ["fetch", "--depth=1", "origin", git_hash]

    try:
        _run_git_command(fetch_args, cwd=workspace_path)
    except WorkspaceError:
        # If fetch fails, the hash might already be available locally
        # (e.g., if it's the HEAD commit). Try checkout anyway.
        pass

    # Checkout the specific commit
    checkout_args = ["checkout", git_hash]
    _run_git_command(checkout_args, cwd=workspace_path)


def cleanup_workspace(
    workspace_path: Path | str,
    keep_logs: bool = True,
) -> None:
    """Clean up workspace after test run.

    By default, preserves the logs directory while removing the workspace.
    This allows reviewing logs after the test completes without keeping
    the full repository clone.

    Args:
        workspace_path: Path to workspace directory.
        keep_logs: If True, preserve logs/ directory (default True).

    Raises:
        WorkspaceError: If cleanup fails.

    """
    workspace_path = Path(workspace_path)

    if not workspace_path.exists():
        # Already cleaned up, nothing to do
        return

    try:
        if keep_logs:
            # Remove only the workspace directory
            shutil.rmtree(workspace_path)
        else:
            # Remove the entire run directory (parent of workspace)
            run_dir = workspace_path.parent
            shutil.rmtree(run_dir)

    except OSError as e:
        raise WorkspaceError(
            message=f"Failed to cleanup workspace: {e}",
        ) from e


class WorkspaceManager:
    """Manager class for workspace operations.

    Provides a class-based interface for workspace management operations.
    All methods are static for stateless operation.

    Example usage:
        ```python
        workspace = WorkspaceManager.create(
            test_id="001-justfile-to-makefile",
            model_id="claude-opus-4-5-20251101",
            run_number=1,
        )

        WorkspaceManager.clone(
            repo_url="https://github.com/example/repo",
            workspace=workspace,
        )

        WorkspaceManager.checkout(
            workspace=workspace,
            hash="abc123def456",
        )

        # After test completion
        WorkspaceManager.cleanup(workspace, keep_logs=True)
        ```
    """

    @staticmethod
    def create(
        test_id: str,
        model_id: str,
        run_number: int,
        timestamp: str | None = None,
        base_path: Path | str = Path("runs"),
    ) -> Path:
        """Create workspace and return path.

        See :func:`create_workspace` for full documentation.
        """
        return create_workspace(
            test_id=test_id,
            model_id=model_id,
            run_number=run_number,
            timestamp=timestamp,
            base_path=base_path,
        )

    @staticmethod
    def clone(
        repo_url: str,
        workspace: Path | str,
        depth: int = 1,
    ) -> None:
        """Clone repository to workspace.

        See :func:`clone_repo` for full documentation.
        """
        clone_repo(repo_url=repo_url, workspace_path=workspace, depth=depth)

    @staticmethod
    def checkout(
        workspace: Path | str,
        hash: str,
    ) -> None:
        """Checkout specific hash.

        See :func:`checkout_hash` for full documentation.
        """
        checkout_hash(workspace_path=workspace, git_hash=hash)

    @staticmethod
    def cleanup(
        workspace: Path | str,
        keep_logs: bool = True,
    ) -> None:
        """Clean up workspace.

        See :func:`cleanup_workspace` for full documentation.
        """
        cleanup_workspace(workspace_path=workspace, keep_logs=keep_logs)
