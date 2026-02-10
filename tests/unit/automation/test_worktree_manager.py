"""Tests for worktree manager."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scylla.automation.worktree_manager import WorktreeManager


class TestWorktreeManager:
    """Tests for WorktreeManager class."""

    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_initialization_default_base_dir(self, mock_get_root, tmp_path):
        """Test initialization with default base directory."""
        mock_get_root.return_value = tmp_path

        manager = WorktreeManager()

        assert manager.repo_root == tmp_path
        assert manager.base_dir == tmp_path / ".worktrees"
        assert manager.worktrees == {}

    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_initialization_custom_base_dir(self, mock_get_root, tmp_path):
        """Test initialization with custom base directory."""
        mock_get_root.return_value = tmp_path
        custom_dir = tmp_path / "custom_worktrees"

        manager = WorktreeManager(base_dir=custom_dir)

        assert manager.base_dir == custom_dir

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_create_worktree_success(self, mock_get_root, mock_run, tmp_path):
        """Test successful worktree creation."""
        mock_get_root.return_value = tmp_path
        # Mock base branch auto-detection
        mock_run.return_value.stdout = "origin/main"
        manager = WorktreeManager()

        worktree_path = manager.create_worktree(123, "123-feature")

        assert worktree_path == manager.base_dir / "issue-123"
        assert manager.worktrees[123] == worktree_path

        # Verify git worktree add was called (plus one call for base branch detection)
        assert mock_run.call_count == 2
        # Check the worktree add call
        call_args = mock_run.call_args[0][0]
        assert call_args[0:2] == ["git", "worktree"]
        assert "123-feature" in call_args

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_create_worktree_default_branch_name(self, mock_get_root, mock_run, tmp_path):
        """Test worktree creation with default branch name."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        manager.create_worktree(456)

        # Should use default branch name
        call_args = mock_run.call_args[0][0]
        assert "456-auto" in call_args

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_create_worktree_already_exists(self, mock_get_root, mock_run, tmp_path):
        """Test creating worktree when already exists."""
        mock_get_root.return_value = tmp_path
        # Mock base branch auto-detection
        mock_run.return_value.stdout = "origin/main"
        manager = WorktreeManager()

        # Create first worktree
        path1 = manager.create_worktree(123, "123-feature")

        # Try to create same worktree again
        path2 = manager.create_worktree(123, "123-feature")

        assert path1 == path2
        # Should call git twice: once for base branch detection, once for first creation
        # Second creation returns early without calling git
        assert mock_run.call_count == 2

    @patch("scylla.automation.worktree_manager.shutil.rmtree")
    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_create_worktree_removes_stale_directory(
        self, mock_get_root, mock_run, mock_rmtree, tmp_path
    ):
        """Test that stale directories are removed before creation."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        # Create mock path that exists
        with patch.object(Path, "exists", return_value=True):
            manager.create_worktree(123, "123-feature")

        # Should try git worktree remove first
        git_remove_calls = [
            c for c in mock_run.call_args_list if "worktree" in c[0][0] and "remove" in c[0][0]
        ]
        assert len(git_remove_calls) >= 1

        # Should call prune after
        prune_calls = [c for c in mock_run.call_args_list if "prune" in c[0][0]]
        assert len(prune_calls) >= 1

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_create_worktree_failure(self, mock_get_root, mock_run, tmp_path):
        """Test worktree creation failure."""
        mock_get_root.return_value = tmp_path
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        manager = WorktreeManager()

        with pytest.raises(RuntimeError, match="Failed to create worktree"):
            manager.create_worktree(123, "123-feature")

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_remove_worktree_success(self, mock_get_root, mock_run, tmp_path):
        """Test successful worktree removal."""
        mock_get_root.return_value = tmp_path
        # Mock base branch auto-detection
        mock_run.return_value.stdout = "origin/main"
        manager = WorktreeManager()

        # Add worktree to tracked list
        worktree_path = manager.base_dir / "issue-123"
        manager.worktrees[123] = worktree_path

        manager.remove_worktree(123)

        assert 123 not in manager.worktrees
        # Called twice: once for base branch detection, once for remove
        assert mock_run.call_count == 2
        call_args = mock_run.call_args[0][0]
        assert call_args[0:3] == ["git", "worktree", "remove"]

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_remove_worktree_force(self, mock_get_root, mock_run, tmp_path):
        """Test forced worktree removal."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        worktree_path = manager.base_dir / "issue-123"
        manager.worktrees[123] = worktree_path

        manager.remove_worktree(123, force=True)

        call_args = mock_run.call_args[0][0]
        assert "--force" in call_args

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_remove_worktree_not_found(self, mock_get_root, mock_run, tmp_path):
        """Test removing non-existent worktree."""
        mock_get_root.return_value = tmp_path
        # Mock base branch auto-detection
        mock_run.return_value.stdout = "origin/main"
        manager = WorktreeManager()

        # Should not crash
        manager.remove_worktree(999)

        # Should only call git for base branch detection, not for remove
        assert mock_run.call_count == 1

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_remove_worktree_failure(self, mock_get_root, mock_run, tmp_path):
        """Test worktree removal failure."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        worktree_path = manager.base_dir / "issue-123"
        manager.worktrees[123] = worktree_path

        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with pytest.raises(RuntimeError, match="Failed to remove worktree"):
            manager.remove_worktree(123)

    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_get_worktree(self, mock_get_root, tmp_path):
        """Test getting worktree path."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        worktree_path = manager.base_dir / "issue-123"
        manager.worktrees[123] = worktree_path

        assert manager.get_worktree(123) == worktree_path
        assert manager.get_worktree(999) is None

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_cleanup_all(self, mock_get_root, mock_run, tmp_path):
        """Test cleaning up all worktrees."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        # Add multiple worktrees
        manager.worktrees[123] = manager.base_dir / "issue-123"
        manager.worktrees[456] = manager.base_dir / "issue-456"
        manager.worktrees[789] = manager.base_dir / "issue-789"

        manager.cleanup_all()

        # All should be removed
        assert len(manager.worktrees) == 0
        # Should call git worktree remove for each
        assert mock_run.call_count >= 3

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_cleanup_all_with_failures(self, mock_get_root, mock_run, tmp_path):
        """Test cleanup continues even if some removals fail."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        manager.worktrees[123] = manager.base_dir / "issue-123"
        manager.worktrees[456] = manager.base_dir / "issue-456"

        # First removal fails, second succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "git"),
            Mock(),
        ]

        # Should not crash
        manager.cleanup_all()

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_prune_worktrees(self, mock_get_root, mock_run, tmp_path):
        """Test pruning stale worktree metadata."""
        mock_get_root.return_value = tmp_path
        # Mock base branch auto-detection
        mock_run.return_value.stdout = "origin/main"
        manager = WorktreeManager()

        manager.prune_worktrees()

        # Called twice: once for base branch detection, once for prune
        assert mock_run.call_count == 2
        call_args = mock_run.call_args[0][0]
        assert call_args == ["git", "worktree", "prune"]

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_list_worktrees(self, mock_get_root, mock_run, tmp_path):
        """Test listing all worktrees."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        mock_result = Mock()
        mock_result.stdout = """worktree /repo
HEAD abc123
branch refs/heads/main

worktree /repo/.worktrees/issue-123
HEAD def456
branch refs/heads/123-feature
"""
        mock_run.return_value = mock_result

        worktrees = manager.list_worktrees()

        assert len(worktrees) == 2
        assert worktrees[0]["path"] == "/repo"
        assert worktrees[0]["branch"] == "refs/heads/main"
        assert worktrees[1]["path"] == "/repo/.worktrees/issue-123"
        assert worktrees[1]["branch"] == "refs/heads/123-feature"

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_ensure_branch_deleted(self, mock_get_root, mock_run, tmp_path):
        """Test deleting branch from local and remote."""
        mock_get_root.return_value = tmp_path
        # Mock base branch auto-detection
        mock_run.return_value.stdout = "origin/main"
        manager = WorktreeManager()

        manager.ensure_branch_deleted("feature-branch")

        # Called 3 times: base branch detection, local delete, remote delete
        assert mock_run.call_count == 3
        # Check local delete (second call)
        local_call = mock_run.call_args_list[1][0][0]
        assert "branch" in local_call and "-D" in local_call
        # Check remote delete (third call)
        remote_call = mock_run.call_args_list[2][0][0]
        assert "push" in remote_call and "--delete" in remote_call

    @patch("scylla.automation.worktree_manager.run")
    @patch("scylla.automation.worktree_manager.get_repo_root")
    def test_ensure_branch_deleted_handles_failure(self, mock_get_root, mock_run, tmp_path):
        """Test branch deletion handles failures gracefully."""
        mock_get_root.return_value = tmp_path
        manager = WorktreeManager()

        # Both deletes fail but shouldn't crash
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        # Should not raise
        manager.ensure_branch_deleted("feature-branch")
