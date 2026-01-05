"""Unit tests for WorkspaceManager retry logic."""

from __future__ import annotations

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
            manager.setup_base_repo()

        # Should only call once
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
                manager.setup_base_repo()

        assert manager.is_setup is True
