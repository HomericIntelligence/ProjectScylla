"""Tests for GitHub API utilities."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from scylla.automation.github_api import (
    _gh_call,
    fetch_issue_info,
    gh_issue_comment,
    gh_issue_create,
    gh_issue_json,
    gh_pr_create,
    is_issue_closed,
    parse_issue_dependencies,
    prefetch_issue_states,
    write_secure,
)
from scylla.automation.models import IssueState


class TestGhIssueJson:
    """Tests for gh_issue_json function."""

    @patch("scylla.automation.github_api._gh_call")
    def test_successful_fetch(self, mock_gh_call):
        """Test successful issue fetch."""
        mock_result = Mock()
        mock_result.stdout = json.dumps(
            {
                "number": 123,
                "title": "Test issue",
                "state": "OPEN",
                "labels": [{"name": "bug"}],
                "body": "Test body",
            }
        )
        mock_gh_call.return_value = mock_result

        data = gh_issue_json(123)

        assert data["number"] == 123
        assert data["title"] == "Test issue"
        assert data["state"] == "OPEN"

    @patch("scylla.automation.github_api._gh_call")
    def test_failed_fetch(self, mock_gh_call):
        """Test failed issue fetch."""
        mock_gh_call.side_effect = subprocess.CalledProcessError(1, "gh")

        with pytest.raises(RuntimeError, match="Failed to fetch issue"):
            gh_issue_json(123)


class TestParseIssueDependencies:
    """Tests for parse_issue_dependencies function."""

    def test_depends_on_pattern(self):
        """Test parsing 'depends on' pattern."""
        body = "This depends on #123 and also #456"
        deps = parse_issue_dependencies(body)

        assert 123 in deps
        assert 456 in deps

    def test_blocked_by_pattern(self):
        """Test parsing 'blocked by' pattern."""
        body = "Blocked by #789"
        deps = parse_issue_dependencies(body)

        assert 789 in deps

    def test_requires_pattern(self):
        """Test parsing 'requires' pattern."""
        body = "Requires #111"
        deps = parse_issue_dependencies(body)

        assert 111 in deps

    def test_dependencies_section(self):
        """Test parsing dependencies section."""
        body = """
        ## Dependencies
        - #100
        - #200
        """
        deps = parse_issue_dependencies(body)

        assert 100 in deps
        assert 200 in deps

    def test_no_dependencies(self):
        """Test when there are no dependencies."""
        body = "This is a simple issue with no dependencies"
        deps = parse_issue_dependencies(body)

        assert len(deps) == 0

    def test_duplicate_removal(self):
        """Test that duplicates are removed."""
        body = "Depends on #123, blocked by #123"
        deps = parse_issue_dependencies(body)

        assert len(deps) == 1
        assert 123 in deps


class TestFetchIssueInfo:
    """Tests for fetch_issue_info function."""

    @patch("scylla.automation.github_api.gh_issue_json")
    def test_successful_fetch(self, mock_gh_json):
        """Test successful issue info fetch."""
        mock_gh_json.return_value = {
            "number": 123,
            "title": "Test issue",
            "state": "OPEN",
            "labels": [{"name": "bug"}, {"name": "priority"}],
            "body": "Depends on #100",
        }

        issue = fetch_issue_info(123)

        assert issue.number == 123
        assert issue.title == "Test issue"
        assert issue.state == IssueState.OPEN
        assert "bug" in issue.labels
        assert 100 in issue.dependencies


class TestIsIssueClosed:
    """Tests for is_issue_closed function."""

    def test_with_cached_state_closed(self):
        """Test with cached state showing closed."""
        cached = {123: IssueState.CLOSED}

        assert is_issue_closed(123, cached) is True

    def test_with_cached_state_open(self):
        """Test with cached state showing open."""
        cached = {123: IssueState.OPEN}

        assert is_issue_closed(123, cached) is False

    @patch("scylla.automation.github_api.gh_issue_json")
    def test_without_cache_closed(self, mock_gh_json):
        """Test without cache, issue is closed."""
        mock_gh_json.return_value = {"state": "CLOSED"}

        assert is_issue_closed(123) is True

    @patch("scylla.automation.github_api.gh_issue_json")
    def test_without_cache_open(self, mock_gh_json):
        """Test without cache, issue is open."""
        mock_gh_json.return_value = {"state": "OPEN"}

        assert is_issue_closed(123) is False

    @patch("scylla.automation.github_api.gh_issue_json")
    def test_error_returns_false(self, mock_gh_json):
        """Test that errors return False."""
        mock_gh_json.side_effect = Exception("API error")

        assert is_issue_closed(123) is False


class TestPrefetchIssueStates:
    """Tests for prefetch_issue_states function."""

    def test_empty_list(self):
        """Test with empty issue list."""
        states = prefetch_issue_states([])
        assert states == {}

    @patch("scylla.automation.github_api._gh_call")
    @patch("scylla.automation.github_api.get_repo_info")
    def test_successful_batch_fetch(self, mock_repo_info, mock_gh_call):
        """Test successful batch fetch."""
        mock_repo_info.return_value = ("owner", "repo")

        mock_result = Mock()
        mock_result.stdout = json.dumps(
            {
                "data": {
                    "repository": {
                        "issue0": {"number": 123, "state": "OPEN"},
                        "issue1": {"number": 456, "state": "CLOSED"},
                    }
                }
            }
        )
        mock_gh_call.return_value = mock_result

        states = prefetch_issue_states([123, 456])

        assert states[123] == IssueState.OPEN
        assert states[456] == IssueState.CLOSED

    @patch("scylla.automation.github_api.get_repo_info")
    def test_repo_info_failure(self, mock_repo_info):
        """Test when repo info fails."""
        mock_repo_info.side_effect = RuntimeError("Not in repo")

        states = prefetch_issue_states([123])

        assert states == {}


class TestGhCall:
    """Tests for _gh_call function."""

    @patch("scylla.automation.github_api.run")
    def test_successful_call(self, mock_run):
        """Test successful gh call."""
        mock_result = Mock()
        mock_result.stdout = "success"
        mock_run.return_value = mock_result

        result = _gh_call(["issue", "view", "123"])

        assert result.stdout == "success"
        mock_run.assert_called_once()

    @patch("scylla.automation.github_api.run")
    @patch("scylla.automation.github_api.wait_until")
    def test_retry_on_rate_limit(self, mock_wait, mock_run):
        """Test retry on rate limit."""
        # First call fails with rate limit, second succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(
                1, "gh", stderr="API rate limit exceeded. Resets at 1234567890"
            ),
            Mock(stdout="success"),
        ]

        result = _gh_call(["issue", "view", "123"])

        assert result.stdout == "success"
        assert mock_run.call_count == 2
        mock_wait.assert_called_once_with(1234567890, "GitHub API rate limit")

    @patch("scylla.automation.github_api.run")
    def test_fail_fast_on_permission_error(self, mock_run):
        """Test that permission errors fail fast without retry."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "gh", stderr="403 Forbidden: permission denied"
        )

        with pytest.raises(subprocess.CalledProcessError):
            _gh_call(["issue", "view", "123"])

        # Should only call once, no retries
        assert mock_run.call_count == 1

    @patch("scylla.automation.github_api.run")
    def test_fail_fast_on_not_found(self, mock_run):
        """Test that 404 errors fail fast without retry."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "gh", stderr="404 Not Found")

        with pytest.raises(subprocess.CalledProcessError):
            _gh_call(["issue", "view", "123"])

        assert mock_run.call_count == 1

    @patch("scylla.automation.github_api.run")
    def test_fail_fast_on_bad_request(self, mock_run):
        """Test that 400 errors fail fast without retry."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "gh", stderr="400 Bad Request")

        with pytest.raises(subprocess.CalledProcessError):
            _gh_call(["issue", "view", "123"])

        assert mock_run.call_count == 1

    @patch("scylla.automation.github_api.run")
    @patch("scylla.automation.github_api.time.sleep")
    def test_retry_on_transient_error(self, mock_sleep, mock_run):
        """Test retry on transient errors."""
        # Fail twice with transient error, then succeed
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "gh", stderr="Connection reset"),
            subprocess.CalledProcessError(1, "gh", stderr="Connection reset"),
            Mock(stdout="success"),
        ]

        result = _gh_call(["issue", "view", "123"], max_retries=3)

        assert result.stdout == "success"
        assert mock_run.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @patch("scylla.automation.github_api.run")
    def test_claude_usage_limit_detection(self, mock_run):
        """Test detection of Claude usage limit."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "gh", stderr="Usage limit exceeded for your account"
        )

        with pytest.raises(RuntimeError, match="Claude API usage limit"):
            _gh_call(["issue", "view", "123"])


class TestGhIssueComment:
    """Tests for gh_issue_comment function."""

    @patch("scylla.automation.github_api._gh_call")
    def test_successful_comment(self, mock_gh_call):
        """Test successful comment posting."""
        mock_gh_call.return_value = Mock()

        gh_issue_comment(123, "Test comment")

        mock_gh_call.assert_called_once()
        call_args = mock_gh_call.call_args[0][0]
        assert call_args == ["issue", "comment", "123", "--body", "Test comment"]

    @patch("scylla.automation.github_api._gh_call")
    def test_failed_comment(self, mock_gh_call):
        """Test failed comment posting."""
        mock_gh_call.side_effect = subprocess.CalledProcessError(1, "gh")

        with pytest.raises(RuntimeError, match="Failed to post comment"):
            gh_issue_comment(123, "Test comment")


class TestGhIssueCreate:
    """Tests for gh_issue_create function."""

    @patch("scylla.automation.github_api._gh_call")
    def test_successful_creation(self, mock_gh_call):
        """Test successful issue creation."""
        mock_result = Mock()
        mock_result.stdout = "https://github.com/owner/repo/issues/789"
        mock_gh_call.return_value = mock_result

        issue_number = gh_issue_create(
            title="Test issue",
            body="Test body",
        )

        assert issue_number == 789
        mock_gh_call.assert_called_once()
        call_args = mock_gh_call.call_args[0][0]
        assert call_args == ["issue", "create", "--title", "Test issue", "--body", "Test body"]

    @patch("scylla.automation.github_api._gh_call")
    def test_creation_with_labels(self, mock_gh_call):
        """Test issue creation with labels."""
        mock_result = Mock()
        mock_result.stdout = "https://github.com/owner/repo/issues/790"
        mock_gh_call.return_value = mock_result

        issue_number = gh_issue_create(
            title="Test issue",
            body="Test body",
            labels=["bug", "enhancement"],
        )

        assert issue_number == 790
        call_args = mock_gh_call.call_args[0][0]
        assert "--label" in call_args
        assert "bug" in call_args
        assert "enhancement" in call_args

    @patch("scylla.automation.github_api._gh_call")
    def test_creation_without_labels(self, mock_gh_call):
        """Test issue creation without labels."""
        mock_result = Mock()
        mock_result.stdout = "https://github.com/owner/repo/issues/791"
        mock_gh_call.return_value = mock_result

        issue_number = gh_issue_create(
            title="Test issue",
            body="Test body",
            labels=None,
        )

        assert issue_number == 791
        call_args = mock_gh_call.call_args[0][0]
        assert "--label" not in call_args

    @patch("scylla.automation.github_api._gh_call")
    def test_failed_creation(self, mock_gh_call):
        """Test failed issue creation."""
        mock_gh_call.side_effect = subprocess.CalledProcessError(1, "gh")

        with pytest.raises(RuntimeError, match="Failed to create issue"):
            gh_issue_create("Test", "Body")


class TestGhPrCreate:
    """Tests for gh_pr_create function."""

    @patch("scylla.automation.github_api._gh_call")
    def test_successful_pr_creation(self, mock_gh_call):
        """Test successful PR creation."""
        # Mock PR creation response
        mock_create_result = Mock()
        mock_create_result.stdout = "https://github.com/owner/repo/pull/456"

        # Mock auto-merge response
        mock_merge_result = Mock()

        mock_gh_call.side_effect = [mock_create_result, mock_merge_result]

        pr_number = gh_pr_create(
            branch="feature-branch",
            title="Test PR",
            body="Test body",
            auto_merge=True,
        )

        assert pr_number == 456
        assert mock_gh_call.call_count == 2  # create + auto-merge

    @patch("scylla.automation.github_api._gh_call")
    def test_pr_creation_without_auto_merge(self, mock_gh_call):
        """Test PR creation without auto-merge."""
        mock_result = Mock()
        mock_result.stdout = "https://github.com/owner/repo/pull/789"
        mock_gh_call.return_value = mock_result

        pr_number = gh_pr_create(
            branch="feature-branch",
            title="Test PR",
            body="Test body",
            auto_merge=False,
        )

        assert pr_number == 789
        assert mock_gh_call.call_count == 1  # Only create, no auto-merge

    @patch("scylla.automation.github_api._gh_call")
    def test_pr_creation_with_fallback_parsing(self, mock_gh_call):
        """Test PR number extraction fallback."""
        mock_result = Mock()
        # URL without /pull/ pattern
        mock_result.stdout = "https://github.com/owner/repo/123"
        mock_gh_call.return_value = mock_result

        pr_number = gh_pr_create(
            branch="feature-branch",
            title="Test PR",
            body="Test body",
            auto_merge=False,
        )

        assert pr_number == 123

    @patch("scylla.automation.github_api._gh_call")
    def test_pr_creation_auto_merge_failure(self, mock_gh_call):
        """Test PR creation when auto-merge fails."""
        mock_create_result = Mock()
        mock_create_result.stdout = "https://github.com/owner/repo/pull/456"

        # Auto-merge fails but shouldn't crash
        mock_gh_call.side_effect = [
            mock_create_result,
            subprocess.CalledProcessError(1, "gh"),
        ]

        pr_number = gh_pr_create(
            branch="feature-branch",
            title="Test PR",
            body="Test body",
            auto_merge=True,
        )

        # Should still return PR number
        assert pr_number == 456


class TestWriteSecure:
    """Tests for write_secure function."""

    def test_write_new_file(self, tmp_path):
        """Test writing to a new file."""
        test_file = tmp_path / "test.txt"
        content = "test content"

        write_secure(test_file, content)

        assert test_file.exists()
        assert test_file.read_text() == content

    def test_overwrite_existing_file(self, tmp_path):
        """Test overwriting an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        write_secure(test_file, "new content")

        assert test_file.read_text() == "new content"

    def test_create_parent_directories(self, tmp_path):
        """Test that parent directories are created."""
        test_file = tmp_path / "subdir" / "nested" / "test.txt"

        write_secure(test_file, "content")

        assert test_file.exists()
        assert test_file.read_text() == "content"

    def test_atomic_write(self, tmp_path):
        """Test that write is atomic (uses temp file + rename)."""
        test_file = tmp_path / "test.txt"

        # Write initial content
        test_file.write_text("original")

        # Verify temp file pattern during write
        write_secure(test_file, "updated")

        # Should have no temp files left
        temp_files = list(tmp_path.glob(".test.txt.*.tmp"))
        assert len(temp_files) == 0

        # Content should be updated
        assert test_file.read_text() == "updated"

    def test_cleanup_on_error(self, tmp_path):
        """Test that temp files are cleaned up on error."""
        test_file = tmp_path / "test.txt"

        # Make parent directory read-only to cause error
        test_file.parent.chmod(0o444)

        try:
            with pytest.raises(Exception):
                write_secure(test_file, "content")

            # Temp files should be cleaned up
            temp_files = list(tmp_path.glob(".test.txt.*.tmp"))
            assert len(temp_files) == 0
        finally:
            # Restore permissions for cleanup
            test_file.parent.chmod(0o755)
