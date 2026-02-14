"""Unit tests for WorkspaceManager retry logic."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from scylla.e2e.workspace_manager import WorkspaceManager


class TestSetupBaseRepoRetry:
    """Tests for setup_base_repo retry logic."""

    def test_successful_clone_first_attempt(self, tmp_path: Path) -> None:
        """Test successful clone on first attempt."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        # Mock successful clone
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("fcntl.flock"):  # Mock file locking
                manager.setup_base_repo()

        # Should only call once (for clone)
        assert mock_run.call_count == 1
        assert manager.is_setup is True

    def test_retry_on_transient_network_error(self, tmp_path: Path) -> None:
        """Test retry succeeds on second attempt for transient network error."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        # First attempt fails with connection reset, second succeeds
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "error: RPC failed; curl 56 Recv failure: Connection reset by peer"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stderr = ""

        with patch("subprocess.run", side_effect=[fail_result, success_result]) as mock_run:
            with patch("time.sleep") as mock_sleep:
                with patch("fcntl.flock"):  # Mock file locking
                    manager.setup_base_repo()

        # Should retry and succeed
        assert mock_run.call_count == 2
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args == call(1.0)  # 1s delay for first retry
        assert manager.is_setup is True

    def test_retry_with_early_eof_error(self, tmp_path: Path) -> None:
        """Test retry on 'early EOF' error."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "fatal: early EOF\nfatal: fetch-pack: invalid index-pack output"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stderr = ""

        with patch("subprocess.run", side_effect=[fail_result, success_result]):
            with patch("time.sleep"):
                with patch("fcntl.flock"):
                    manager.setup_base_repo()

        assert manager.is_setup is True

    def test_exponential_backoff_timing(self, tmp_path: Path) -> None:
        """Test exponential backoff timing: 1s, 2s, then success."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        # Fail twice, succeed on third
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "connection reset by peer"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stderr = ""

        with patch(
            "subprocess.run",
            side_effect=[fail_result, fail_result, success_result],
        ):
            with patch("time.sleep") as mock_sleep:
                with patch("fcntl.flock"):
                    manager.setup_base_repo()

        # Should have exponential backoff: 1s, 2s
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list == [call(1.0), call(2.0)]

    def test_immediate_failure_on_auth_error(self, tmp_path: Path) -> None:
        """Test immediate failure on authentication error (non-transient)."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        # Auth error is not transient
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "fatal: Authentication failed for repository"

        with patch("subprocess.run", return_value=fail_result) as mock_run:
            with patch("time.sleep") as mock_sleep:
                with patch("fcntl.flock"):
                    with pytest.raises(RuntimeError, match="Failed to clone repository"):
                        manager.setup_base_repo()

        # Should NOT retry
        assert mock_run.call_count == 1
        assert mock_sleep.call_count == 0

    def test_immediate_failure_on_not_found(self, tmp_path: Path) -> None:
        """Test immediate failure on repository not found (non-transient)."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/nonexistent.git",
        )

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "fatal: repository 'https://github.com/test/nonexistent.git' not found"

        with patch("subprocess.run", return_value=fail_result) as mock_run:
            with patch("time.sleep") as mock_sleep:
                with patch("fcntl.flock"):
                    with pytest.raises(RuntimeError, match="Failed to clone repository"):
                        manager.setup_base_repo()

        # Should NOT retry
        assert mock_run.call_count == 1
        assert mock_sleep.call_count == 0

    def test_exhausted_retries_raises_error(self, tmp_path: Path) -> None:
        """Test that exhausted retries raises RuntimeError."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        # Fail all attempts
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "curl 56: Connection reset by peer"

        with patch("subprocess.run", return_value=fail_result) as mock_run:
            with patch("time.sleep") as mock_sleep:
                with patch("fcntl.flock"):
                    with pytest.raises(RuntimeError, match="Failed to clone repository"):
                        manager.setup_base_repo()

        # Should retry max times (3 total attempts)
        assert mock_run.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between attempts

    def test_retry_on_timeout_error(self, tmp_path: Path) -> None:
        """Test retry on timeout error."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "fatal: unable to access repository: Operation timed out"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stderr = ""

        with patch("subprocess.run", side_effect=[fail_result, success_result]):
            with patch("time.sleep"):
                with patch("fcntl.flock"):
                    manager.setup_base_repo()

        assert manager.is_setup is True

    def test_retry_on_network_unreachable(self, tmp_path: Path) -> None:
        """Test retry on network unreachable error."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "fatal: unable to access repository: Network is unreachable"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stderr = ""

        with patch("subprocess.run", side_effect=[fail_result, success_result]):
            with patch("time.sleep"):
                with patch("fcntl.flock"):
                    manager.setup_base_repo()

        assert manager.is_setup is True

    def test_idempotent_setup(self, tmp_path: Path) -> None:
        """Test that setup_base_repo is idempotent."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        # First call
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("fcntl.flock"):
                manager.setup_base_repo()
                manager.setup_base_repo()  # Second call should be no-op

        # Should only run once
        assert mock_run.call_count == 1

    def test_case_insensitive_error_detection(self, tmp_path: Path) -> None:
        """Test that error detection is case-insensitive."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
        )

        # Mixed case error message
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "Error: Connection RESET by peer"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stderr = ""

        with patch("subprocess.run", side_effect=[fail_result, success_result]):
            with patch("time.sleep"):
                with patch("fcntl.flock"):
                    manager.setup_base_repo()

        assert manager.is_setup is True


class TestCentralizedRepos:
    """Tests for centralized repository functionality."""

    def test_repos_dir_sets_centralized_path(self, tmp_path: Path) -> None:
        """Test that repos_dir parameter sets centralized path correctly."""
        repos_dir = tmp_path / "repos"
        repo_url = "https://github.com/test/repo.git"

        manager = WorkspaceManager(
            experiment_dir=tmp_path / "experiment",
            repo_url=repo_url,
            repos_dir=repos_dir,
        )

        # Calculate expected UUID
        expected_uuid = hashlib.sha256(repo_url.encode()).hexdigest()[:16]
        expected_path = repos_dir / expected_uuid

        assert manager.base_repo == expected_path
        assert manager.repos_dir == repos_dir

    def test_repos_dir_none_fallback(self, tmp_path: Path) -> None:
        """Test that repos_dir=None uses legacy per-experiment layout."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
            repos_dir=None,
        )

        assert manager.base_repo == tmp_path / "repo"
        assert manager.repos_dir is None

    def test_deterministic_repo_uuid(self, tmp_path: Path) -> None:
        """Test that same URL always produces same UUID."""
        repos_dir = tmp_path / "repos"
        repo_url = "https://github.com/test/repo.git"

        manager1 = WorkspaceManager(
            experiment_dir=tmp_path / "exp1",
            repo_url=repo_url,
            repos_dir=repos_dir,
        )
        manager2 = WorkspaceManager(
            experiment_dir=tmp_path / "exp2",
            repo_url=repo_url,
            repos_dir=repos_dir,
        )

        assert manager1.base_repo == manager2.base_repo

    def test_reuses_existing_clone(self, tmp_path: Path) -> None:
        """Test that existing clone is reused without re-cloning."""
        repos_dir = tmp_path / "repos"
        repo_url = "https://github.com/test/repo.git"

        manager = WorkspaceManager(
            experiment_dir=tmp_path / "experiment",
            repo_url=repo_url,
            repos_dir=repos_dir,
        )

        # Create mock existing repo
        manager.base_repo.mkdir(parents=True)
        (manager.base_repo / ".git").mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("fcntl.flock"):
                manager.setup_base_repo()

        # Should NOT clone (no git clone call)
        assert mock_run.call_count == 0
        assert manager.is_setup is True

    def test_ensure_commit_available_fetches(self, tmp_path: Path) -> None:
        """Test that _ensure_commit_available fetches commit if not in object store."""
        repos_dir = tmp_path / "repos"
        manager = WorkspaceManager(
            experiment_dir=tmp_path / "experiment",
            repo_url="https://github.com/test/repo.git",
            commit="abc123",
            repos_dir=repos_dir,
        )

        # Mock that commit doesn't exist, then fetch succeeds
        check_result = MagicMock()
        check_result.returncode = 1  # Not found

        fetch_result = MagicMock()
        fetch_result.returncode = 0
        fetch_result.stderr = ""

        with patch("subprocess.run", side_effect=[check_result, fetch_result]) as mock_run:
            manager._ensure_commit_available()

        # Should call cat-file check, then fetch
        assert mock_run.call_count == 2
        assert "cat-file" in str(mock_run.call_args_list[0])
        assert "fetch" in str(mock_run.call_args_list[1])

    def test_full_clone_for_centralized(self, tmp_path: Path) -> None:
        """Test that centralized repos use full clone (no --depth=1)."""
        repos_dir = tmp_path / "repos"
        manager = WorkspaceManager(
            experiment_dir=tmp_path / "experiment",
            repo_url="https://github.com/test/repo.git",
            repos_dir=repos_dir,
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("fcntl.flock"):
                manager.setup_base_repo()

        # Check that clone command does NOT include --depth=1
        clone_call = mock_run.call_args_list[0]
        clone_cmd = clone_call[0][0]
        assert "--depth=1" not in clone_cmd
        assert "clone" in clone_cmd

    def test_shallow_clone_for_legacy(self, tmp_path: Path) -> None:
        """Test that legacy per-experiment layout uses shallow clone."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
            repos_dir=None,  # Legacy layout
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("fcntl.flock"):
                manager.setup_base_repo()

        # Check that clone command DOES include --depth=1
        clone_call = mock_run.call_args_list[0]
        clone_cmd = clone_call[0][0]
        assert "--depth=1" in clone_cmd

    def test_worktree_includes_commit(self, tmp_path: Path) -> None:
        """Test that git worktree add includes commit hash directly."""
        manager = WorkspaceManager(
            experiment_dir=tmp_path,
            repo_url="https://github.com/test/repo.git",
            commit="abc123",
        )
        manager._is_setup = True
        manager.base_repo.mkdir(parents=True)

        workspace = tmp_path / "workspace"

        # Mock worktree creation
        worktree_result = MagicMock()
        worktree_result.returncode = 0

        with patch("subprocess.run", return_value=worktree_result) as mock_run:
            manager.create_worktree(workspace, "T0", "01", 1)

        # Should have only 1 call: git worktree add with commit
        assert mock_run.call_count == 1

        # Single call: git worktree add (should include commit)
        worktree_cmd = mock_run.call_args_list[0][0][0]
        assert "worktree" in worktree_cmd
        assert "add" in worktree_cmd
        assert "abc123" in worktree_cmd
