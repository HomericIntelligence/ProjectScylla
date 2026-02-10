"""Tests for git utility functions."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scylla.automation.git_utils import (
    get_current_branch,
    get_repo_info,
    get_repo_root,
    is_clean_working_tree,
    run,
    safe_git_fetch,
)


class TestRun:
    """Tests for run function."""

    def test_successful_command(self):
        """Test running a successful command."""
        result = run(["echo", "hello"], check=True, capture_output=True)

        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_failed_command_with_check(self):
        """Test running a failed command with check=True."""
        with pytest.raises(subprocess.CalledProcessError):
            run(["false"], check=True)

    def test_failed_command_without_check(self):
        """Test running a failed command with check=False."""
        result = run(["false"], check=False)
        assert result.returncode != 0

    def test_with_cwd(self, tmp_path):
        """Test running command with custom working directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = run(["ls", "test.txt"], cwd=tmp_path, capture_output=True)

        assert result.returncode == 0
        assert "test.txt" in result.stdout


class TestGetRepoRoot:
    """Tests for get_repo_root function."""

    @patch("scylla.automation.git_utils.run")
    def test_successful_detection(self, mock_run):
        """Test successful repository root detection."""
        mock_result = Mock()
        mock_result.stdout = "/home/user/repo\n"
        mock_run.return_value = mock_result

        root = get_repo_root()

        assert root == Path("/home/user/repo")
        mock_run.assert_called_once()

    @patch("scylla.automation.git_utils.run")
    def test_not_in_git_repo(self, mock_run):
        """Test when not in a git repository."""
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")

        with pytest.raises(RuntimeError, match="Not in a git repository"):
            get_repo_root()


class TestGetRepoInfo:
    """Tests for get_repo_info function."""

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.get_repo_root")
    def test_ssh_url_format(self, mock_get_root, mock_run):
        """Test parsing SSH URL format."""
        mock_get_root.return_value = Path("/home/user/repo")
        mock_result = Mock()
        mock_result.stdout = "git@github.com:owner/repo.git\n"
        mock_run.return_value = mock_result

        owner, repo = get_repo_info()

        assert owner == "owner"
        assert repo == "repo"

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.get_repo_root")
    def test_https_url_format(self, mock_get_root, mock_run):
        """Test parsing HTTPS URL format."""
        mock_get_root.return_value = Path("/home/user/repo")
        mock_result = Mock()
        mock_result.stdout = "https://github.com/owner/repo.git\n"
        mock_run.return_value = mock_result

        owner, repo = get_repo_info()

        assert owner == "owner"
        assert repo == "repo"

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.get_repo_root")
    def test_invalid_url_format(self, mock_get_root, mock_run):
        """Test handling invalid URL format."""
        mock_get_root.return_value = Path("/home/user/repo")
        mock_result = Mock()
        mock_result.stdout = "invalid-url\n"
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError, match="Unable to parse git remote URL"):
            get_repo_info()


class TestGetCurrentBranch:
    """Tests for get_current_branch function."""

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.get_repo_root")
    def test_successful_detection(self, mock_get_root, mock_run):
        """Test successful branch detection."""
        mock_get_root.return_value = Path("/home/user/repo")
        mock_result = Mock()
        mock_result.stdout = "main\n"
        mock_run.return_value = mock_result

        branch = get_current_branch()

        assert branch == "main"

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.get_repo_root")
    def test_failed_detection(self, mock_get_root, mock_run):
        """Test failed branch detection."""
        mock_get_root.return_value = Path("/home/user/repo")
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")

        with pytest.raises(RuntimeError, match="Failed to get current branch"):
            get_current_branch()


class TestIsCleanWorkingTree:
    """Tests for is_clean_working_tree function."""

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.get_repo_root")
    def test_clean_tree(self, mock_get_root, mock_run):
        """Test clean working tree."""
        mock_get_root.return_value = Path("/home/user/repo")
        mock_result = Mock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        assert is_clean_working_tree() is True

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.get_repo_root")
    def test_dirty_tree(self, mock_get_root, mock_run):
        """Test dirty working tree."""
        mock_get_root.return_value = Path("/home/user/repo")
        mock_result = Mock()
        mock_result.stdout = " M modified_file.txt\n"
        mock_run.return_value = mock_result

        assert is_clean_working_tree() is False

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.get_repo_root")
    def test_error_returns_false(self, mock_get_root, mock_run):
        """Test error returns False."""
        mock_get_root.return_value = Path("/home/user/repo")
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")

        assert is_clean_working_tree() is False


class TestSafeGitFetch:
    """Tests for safe_git_fetch function."""

    @patch("scylla.automation.git_utils.run")
    def test_successful_fetch(self, mock_run):
        """Test successful git fetch."""
        repo_root = Path("/home/user/repo")

        result = safe_git_fetch(repo_root, retries=1)

        assert result is True
        mock_run.assert_called_once()

    @patch("scylla.automation.git_utils.run")
    @patch("scylla.automation.git_utils.time.sleep")
    def test_retry_on_failure(self, mock_sleep, mock_run):
        """Test retry on fetch failure."""
        repo_root = Path("/home/user/repo")
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "git"),
            subprocess.CalledProcessError(1, "git"),
            Mock(),  # Success on third try
        ]

        result = safe_git_fetch(repo_root, retries=3)

        assert result is True
        assert mock_run.call_count == 3

    @patch("scylla.automation.git_utils.run")
    def test_all_retries_fail(self, mock_run):
        """Test when all retries fail."""
        repo_root = Path("/home/user/repo")
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        result = safe_git_fetch(repo_root, retries=2)

        assert result is False
        assert mock_run.call_count == 2
