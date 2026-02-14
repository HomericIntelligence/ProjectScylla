"""Tests for GitHub API error handling."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scylla.automation.github_api import _gh_call, gh_pr_create


class TestAutoMergeErrorHandling:
    """Tests for auto-merge error handling."""

    def test_auto_merge_runtime_error_caught(self):
        """Test that RuntimeError from rate limit doesn't escape gh_pr_create."""
        with (
            patch("scylla.automation.github_api._gh_call") as mock_gh_call,
            patch("scylla.automation.github_api.logger") as mock_logger,
        ):
            # First call succeeds (PR creation), second call raises RuntimeError
            pr_output = "https://github.com/owner/repo/pull/123"
            mock_gh_call.side_effect = [
                MagicMock(stdout=pr_output),
                RuntimeError("GitHub API usage limit reached"),
            ]

            # Should not raise - error is caught and logged
            pr_number = gh_pr_create(
                branch="test-branch",
                title="Test PR",
                body="Test body",
                auto_merge=True,
            )

            # PR should still be created successfully
            assert pr_number == 123

            # Warning should be logged about auto-merge failure
            assert mock_logger.warning.called
            warning_msg = str(mock_logger.warning.call_args)
            assert "auto-merge" in warning_msg.lower()

    def test_auto_merge_called_process_error_caught(self):
        """Test that CalledProcessError is also caught."""
        with (
            patch("scylla.automation.github_api._gh_call") as mock_gh_call,
            patch("scylla.automation.github_api.logger") as mock_logger,
        ):
            # First call succeeds, second call raises CalledProcessError
            pr_output = "https://github.com/owner/repo/pull/456"
            mock_gh_call.side_effect = [
                MagicMock(stdout=pr_output),
                subprocess.CalledProcessError(1, ["gh", "pr", "merge"], stderr="Error"),
            ]

            # Should not raise
            pr_number = gh_pr_create(
                branch="test-branch",
                title="Test PR",
                body="Test body",
                auto_merge=True,
            )

            assert pr_number == 456
            assert mock_logger.warning.called


class TestGhCallTimeout:
    """Tests for gh CLI timeout."""

    def test_gh_call_timeout(self):
        """Test that timeout is passed to subprocess."""
        with patch("scylla.automation.github_api.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="output")

            _gh_call(["issue", "view", "123"])

            # Verify timeout was passed
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 120

    def test_gh_call_timeout_expired(self):
        """Test that TimeoutExpired is propagated."""
        with patch("scylla.automation.github_api.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["gh", "issue", "view"], 120)

            # Should raise after all retries
            with pytest.raises(subprocess.TimeoutExpired):
                _gh_call(["issue", "view", "123"])
