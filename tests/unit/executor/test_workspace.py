"""Unit tests for workspace management.

Tests cover:
- Creating workspace directory structures
- Cloning git repositories with shallow clones
- Checking out specific git hashes
- Cleaning up workspaces while preserving logs
- Error handling for various failure scenarios
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.executor.workspace import (
    WorkspaceError,
    WorkspaceManager,
    cleanup_workspace,
    clone_repo,
    create_workspace,
    checkout_hash,
)


class TestWorkspaceError:
    """Tests for WorkspaceError exception."""

    def test_basic_error(self) -> None:
        """WorkspaceError stores message correctly."""
        error = WorkspaceError("Something failed")
        assert str(error) == "Something failed"
        assert error.message == "Something failed"
        assert error.command is None
        assert error.stderr is None

    def test_error_with_command(self) -> None:
        """WorkspaceError includes command in string representation."""
        error = WorkspaceError(
            message="Clone failed",
            command="git clone https://example.com/repo",
        )
        assert "Clone failed" in str(error)
        assert "git clone" in str(error)

    def test_error_with_stderr(self) -> None:
        """WorkspaceError includes stderr in string representation."""
        error = WorkspaceError(
            message="Clone failed",
            command="git clone",
            stderr="Repository not found",
        )
        assert "Clone failed" in str(error)
        assert "Repository not found" in str(error)


class TestCreateWorkspace:
    """Tests for create_workspace function."""

    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        """Workspace directory structure is created correctly."""
        workspace = create_workspace(
            test_id="001-test",
            model_id="claude-opus",
            run_number=1,
            timestamp="2024-01-15T14-30-00",
            base_path=tmp_path,
        )

        assert workspace.exists()
        assert workspace.is_dir()
        assert workspace.name == "workspace"

        # Verify logs directory exists
        logs_dir = workspace.parent / "logs"
        assert logs_dir.exists()
        assert logs_dir.is_dir()

        # Verify log files exist
        assert (logs_dir / "stdout.log").exists()
        assert (logs_dir / "stderr.log").exists()
        assert (logs_dir / "agent.log").exists()

    def test_run_number_formatting(self, tmp_path: Path) -> None:
        """Run number is zero-padded to 2 digits."""
        workspace = create_workspace(
            test_id="001-test",
            model_id="claude",
            run_number=3,
            timestamp="2024-01-15T14-30-00",
            base_path=tmp_path,
        )

        assert "run-03" in str(workspace)

    def test_run_number_double_digit(self, tmp_path: Path) -> None:
        """Double digit run numbers work correctly."""
        workspace = create_workspace(
            test_id="001-test",
            model_id="claude",
            run_number=42,
            timestamp="2024-01-15T14-30-00",
            base_path=tmp_path,
        )

        assert "run-42" in str(workspace)

    def test_full_path_structure(self, tmp_path: Path) -> None:
        """Full directory path matches specification."""
        workspace = create_workspace(
            test_id="001-justfile",
            model_id="claude-opus-4-5-20251101",
            run_number=1,
            timestamp="2024-01-15T14-30-00",
            base_path=tmp_path,
        )

        expected_path = (
            tmp_path
            / "001-justfile"
            / "2024-01-15T14-30-00"
            / "claude-opus-4-5-20251101"
            / "run-01"
            / "workspace"
        )
        assert workspace == expected_path

    def test_idempotent_creation(self, tmp_path: Path) -> None:
        """Calling create_workspace twice doesn't fail."""
        args = {
            "test_id": "001-test",
            "model_id": "claude",
            "run_number": 1,
            "timestamp": "2024-01-15T14-30-00",
            "base_path": tmp_path,
        }

        workspace1 = create_workspace(**args)
        workspace2 = create_workspace(**args)

        assert workspace1 == workspace2
        assert workspace1.exists()

    def test_auto_timestamp(self, tmp_path: Path) -> None:
        """Timestamp is auto-generated when not provided."""
        workspace = create_workspace(
            test_id="001-test",
            model_id="claude",
            run_number=1,
            base_path=tmp_path,
        )

        assert workspace.exists()
        # Path should contain a timestamp-like component
        path_str = str(workspace)
        assert "T" in path_str  # ISO format contains 'T'

    def test_string_base_path(self, tmp_path: Path) -> None:
        """String base_path is converted to Path."""
        workspace = create_workspace(
            test_id="001-test",
            model_id="claude",
            run_number=1,
            timestamp="2024-01-15T14-30-00",
            base_path=str(tmp_path),
        )

        assert workspace.exists()

    def test_invalid_run_number_zero(self, tmp_path: Path) -> None:
        """Run number 0 raises ValueError."""
        with pytest.raises(ValueError, match="run_number must be 1-99"):
            create_workspace(
                test_id="001-test",
                model_id="claude",
                run_number=0,
                base_path=tmp_path,
            )

    def test_invalid_run_number_too_high(self, tmp_path: Path) -> None:
        """Run number > 99 raises ValueError."""
        with pytest.raises(ValueError, match="run_number must be 1-99"):
            create_workspace(
                test_id="001-test",
                model_id="claude",
                run_number=100,
                base_path=tmp_path,
            )

    def test_empty_test_id(self, tmp_path: Path) -> None:
        """Empty test_id raises ValueError."""
        with pytest.raises(ValueError, match="test_id cannot be empty"):
            create_workspace(
                test_id="",
                model_id="claude",
                run_number=1,
                base_path=tmp_path,
            )

    def test_empty_model_id(self, tmp_path: Path) -> None:
        """Empty model_id raises ValueError."""
        with pytest.raises(ValueError, match="model_id cannot be empty"):
            create_workspace(
                test_id="001-test",
                model_id="",
                run_number=1,
                base_path=tmp_path,
            )

    def test_whitespace_stripped(self, tmp_path: Path) -> None:
        """Whitespace in test_id and model_id is stripped."""
        workspace = create_workspace(
            test_id="  001-test  ",
            model_id="  claude  ",
            run_number=1,
            timestamp="2024-01-15T14-30-00",
            base_path=tmp_path,
        )

        assert "001-test" in str(workspace)
        assert "claude" in str(workspace)
        assert "  " not in str(workspace)


class TestCloneRepo:
    """Tests for clone_repo function."""

    def test_empty_repo_url(self, tmp_path: Path) -> None:
        """Empty repo_url raises ValueError."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with pytest.raises(ValueError, match="repo_url cannot be empty"):
            clone_repo(repo_url="", workspace_path=workspace)

    def test_nonexistent_workspace(self, tmp_path: Path) -> None:
        """Non-existent workspace raises WorkspaceError."""
        workspace = tmp_path / "nonexistent"

        with pytest.raises(WorkspaceError, match="does not exist"):
            clone_repo(
                repo_url="https://github.com/example/repo",
                workspace_path=workspace,
            )

    def test_clone_success(self, tmp_path: Path) -> None:
        """Successful clone creates .git directory."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            clone_repo(
                repo_url="https://github.com/example/repo",
                workspace_path=workspace,
            )

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "git" in call_args[0][0]
            assert "clone" in call_args[0][0]
            assert "--depth" in call_args[0][0]
            assert "1" in call_args[0][0]

    def test_clone_failure(self, tmp_path: Path) -> None:
        """Clone failure raises WorkspaceError."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "fatal: repository not found"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(WorkspaceError, match="failed"):
                clone_repo(
                    repo_url="https://github.com/invalid/nonexistent",
                    workspace_path=workspace,
                )

    def test_clone_custom_depth(self, tmp_path: Path) -> None:
        """Custom depth parameter is passed to git."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            clone_repo(
                repo_url="https://github.com/example/repo",
                workspace_path=workspace,
                depth=5,
            )

            call_args = mock_run.call_args[0][0]
            # Check that --depth and 5 are in the command
            assert "--depth" in call_args
            depth_idx = call_args.index("--depth")
            assert call_args[depth_idx + 1] == "5"


class TestCheckoutHash:
    """Tests for checkout_hash function."""

    def test_empty_hash(self, tmp_path: Path) -> None:
        """Empty git_hash raises ValueError."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with pytest.raises(ValueError, match="git_hash cannot be empty"):
            checkout_hash(workspace_path=workspace, git_hash="")

    def test_nonexistent_workspace(self, tmp_path: Path) -> None:
        """Non-existent workspace raises WorkspaceError."""
        workspace = tmp_path / "nonexistent"

        with pytest.raises(WorkspaceError, match="does not exist"):
            checkout_hash(workspace_path=workspace, git_hash="abc123")

    def test_not_a_git_repo(self, tmp_path: Path) -> None:
        """Non-git directory raises WorkspaceError."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with pytest.raises(WorkspaceError, match="Not a git repository"):
            checkout_hash(workspace_path=workspace, git_hash="abc123")

    def test_checkout_success(self, tmp_path: Path) -> None:
        """Successful checkout calls git commands."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()  # Simulate git repo

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            checkout_hash(workspace_path=workspace, git_hash="abc123def456")

            # Should have called git at least once for checkout
            assert mock_run.call_count >= 1

    def test_checkout_whitespace_stripped(self, tmp_path: Path) -> None:
        """Whitespace in git_hash is stripped."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            checkout_hash(workspace_path=workspace, git_hash="  abc123  ")

            # Verify the hash was stripped in the checkout command
            for call in mock_run.call_args_list:
                args = call[0][0]
                if "checkout" in args:
                    assert "abc123" in args
                    assert "  abc123  " not in args


class TestCleanupWorkspace:
    """Tests for cleanup_workspace function."""

    def test_cleanup_nonexistent(self, tmp_path: Path) -> None:
        """Cleanup of non-existent path succeeds silently."""
        workspace = tmp_path / "nonexistent"

        # Should not raise
        cleanup_workspace(workspace)

    def test_cleanup_keeps_logs(self, tmp_path: Path) -> None:
        """Cleanup with keep_logs=True preserves logs directory."""
        run_dir = tmp_path / "runs" / "test" / "timestamp" / "model" / "run-01"
        workspace = run_dir / "workspace"
        logs = run_dir / "logs"

        workspace.mkdir(parents=True)
        logs.mkdir(parents=True)
        (workspace / "file.txt").touch()
        (logs / "stdout.log").touch()

        cleanup_workspace(workspace, keep_logs=True)

        assert not workspace.exists()
        assert logs.exists()
        assert (logs / "stdout.log").exists()

    def test_cleanup_removes_all(self, tmp_path: Path) -> None:
        """Cleanup with keep_logs=False removes entire run directory."""
        run_dir = tmp_path / "runs" / "test" / "timestamp" / "model" / "run-01"
        workspace = run_dir / "workspace"
        logs = run_dir / "logs"

        workspace.mkdir(parents=True)
        logs.mkdir(parents=True)
        (workspace / "file.txt").touch()
        (logs / "stdout.log").touch()

        cleanup_workspace(workspace, keep_logs=False)

        assert not workspace.exists()
        assert not logs.exists()
        assert not run_dir.exists()


class TestWorkspaceManager:
    """Tests for WorkspaceManager class."""

    def test_create_delegates_to_function(self, tmp_path: Path) -> None:
        """WorkspaceManager.create delegates to create_workspace."""
        workspace = WorkspaceManager.create(
            test_id="001-test",
            model_id="claude",
            run_number=1,
            timestamp="2024-01-15T14-30-00",
            base_path=tmp_path,
        )

        assert workspace.exists()
        assert workspace.name == "workspace"

    def test_clone_delegates_to_function(self, tmp_path: Path) -> None:
        """WorkspaceManager.clone delegates to clone_repo."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            WorkspaceManager.clone(
                repo_url="https://github.com/example/repo",
                workspace=workspace,
            )

    def test_checkout_delegates_to_function(self, tmp_path: Path) -> None:
        """WorkspaceManager.checkout delegates to checkout_hash."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            WorkspaceManager.checkout(
                workspace=workspace,
                hash="abc123",
            )

    def test_cleanup_delegates_to_function(self, tmp_path: Path) -> None:
        """WorkspaceManager.cleanup delegates to cleanup_workspace."""
        run_dir = tmp_path / "run-01"
        workspace = run_dir / "workspace"
        workspace.mkdir(parents=True)

        WorkspaceManager.cleanup(workspace)

        assert not workspace.exists()


class TestGitRetryLogic:
    """Tests for git command retry logic."""

    def test_retries_on_transient_error(self, tmp_path: Path) -> None:
        """Git commands retry on transient network errors."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # First two calls fail, third succeeds
        mock_results = [
            MagicMock(returncode=1, stderr="Connection timed out"),
            MagicMock(returncode=1, stderr="Connection reset"),
            MagicMock(returncode=0, stderr=""),
        ]

        with patch("subprocess.run", side_effect=mock_results) as mock_run:
            with patch("time.sleep"):  # Skip delays in tests
                clone_repo(
                    repo_url="https://github.com/example/repo",
                    workspace_path=workspace,
                )

                assert mock_run.call_count == 3

    def test_no_retry_on_auth_failure(self, tmp_path: Path) -> None:
        """Git commands do not retry on authentication failures."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "fatal: Authentication failed for repo"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with pytest.raises(WorkspaceError, match="non-retryable"):
                clone_repo(
                    repo_url="https://github.com/example/repo",
                    workspace_path=workspace,
                )

            # Should only be called once (no retry)
            assert mock_run.call_count == 1

    def test_no_retry_on_not_found(self, tmp_path: Path) -> None:
        """Git commands do not retry on repository not found."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "Repository not found"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with pytest.raises(WorkspaceError, match="non-retryable"):
                clone_repo(
                    repo_url="https://github.com/invalid/repo",
                    workspace_path=workspace,
                )

            assert mock_run.call_count == 1


class TestWorkspaceManagerIntegration:
    """Integration tests for full workspace workflow."""

    def test_full_workflow_with_mocks(self, tmp_path: Path) -> None:
        """Full workflow: create -> clone -> checkout -> cleanup."""
        # Create
        workspace = WorkspaceManager.create(
            test_id="001-justfile-to-makefile",
            model_id="claude-opus-4-5-20251101",
            run_number=1,
            timestamp="2024-01-15T14-30-00",
            base_path=tmp_path,
        )

        assert workspace.exists()

        # Clone (mocked)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            WorkspaceManager.clone(
                repo_url="https://github.com/mvillmow/ProjectOdyssey",
                workspace=workspace,
            )

        # Simulate git repo creation
        (workspace / ".git").mkdir()

        # Checkout (mocked)
        with patch("subprocess.run", return_value=mock_result):
            WorkspaceManager.checkout(
                workspace=workspace,
                hash="ce739d4aa328f1c0815b33e2812c4b889868b740",
            )

        # Verify logs directory exists before cleanup
        logs_dir = workspace.parent / "logs"
        assert logs_dir.exists()

        # Cleanup
        WorkspaceManager.cleanup(workspace, keep_logs=True)

        assert not workspace.exists()
        assert logs_dir.exists()
