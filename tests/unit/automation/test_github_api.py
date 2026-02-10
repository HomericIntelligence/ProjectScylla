"""Tests for GitHub API utilities."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from scylla.automation.github_api import (
    fetch_issue_info,
    gh_issue_json,
    is_issue_closed,
    parse_issue_dependencies,
    prefetch_issue_states,
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
