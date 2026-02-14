"""Tests for the IssueImplementer automation."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.automation.implementer import IssueImplementer
from scylla.automation.models import ImplementerOptions


@pytest.fixture
def mock_options():
    """Create mock ImplementerOptions."""
    return ImplementerOptions(
        epic_number=123,
        dry_run=False,
        max_workers=1,
        enable_retrospective=False,  # Explicitly disable for most tests
        enable_follow_up=False,  # Disable for most tests
    )


@pytest.fixture
def implementer(mock_options):
    """Create an IssueImplementer instance."""
    with (
        patch("scylla.automation.implementer.get_repo_root") as mock_repo,
        patch.object(Path, "mkdir"),
    ):
        mock_repo.return_value = Path("/repo")
        return IssueImplementer(mock_options)


class TestRunClaudeCode:
    """Tests for _run_claude_code method."""

    def test_captures_session_id_from_json(self, implementer):
        """Test successful session_id capture from JSON output."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "type": "result",
                "session_id": "abc123-def456",
                "result": "Implementation complete",
                "total_cost_usd": 0.13,
            }
        )

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch.object(Path, "write_text"),
            patch.object(Path, "unlink"),
        ):
            mock_run.return_value = mock_result

            session_id = implementer._run_claude_code(
                issue_number=123,
                worktree_path=Path("/tmp/worktree"),
                prompt="Implement issue",
            )

            assert session_id == "abc123-def456"
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "claude"
            # Should now pass a file path, not --message
            assert ".claude-prompt-123.md" in args[1]
            assert "--output-format" in args
            assert "json" in args

    def test_graceful_failure_on_json_parse_error(self, implementer):
        """Test graceful handling when JSON parse fails."""
        mock_result = MagicMock()
        mock_result.stdout = "Not valid JSON"

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
            patch.object(Path, "write_text"),
            patch.object(Path, "unlink"),
        ):
            mock_run.return_value = mock_result

            session_id = implementer._run_claude_code(
                issue_number=123,
                worktree_path=Path("/tmp/worktree"),
                prompt="Implement issue",
            )

            assert session_id is None
            mock_logger.warning.assert_called_once()
            assert "Could not parse session_id" in str(mock_logger.warning.call_args)

    def test_graceful_failure_on_missing_session_id(self, implementer):
        """Test graceful handling when session_id is missing from JSON."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "type": "result",
                "result": "Implementation complete",
            }
        )

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch.object(Path, "write_text"),
            patch.object(Path, "unlink"),
        ):
            mock_run.return_value = mock_result

            session_id = implementer._run_claude_code(
                issue_number=123,
                worktree_path=Path("/tmp/worktree"),
                prompt="Implement issue",
            )

            # Should return None when session_id is missing
            assert session_id is None

    def test_timeout_raises_runtime_error(self, implementer):
        """Test timeout handling."""
        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch.object(Path, "write_text"),
            patch.object(Path, "unlink"),
        ):
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 1800)

            with pytest.raises(RuntimeError, match="timed out"):
                implementer._run_claude_code(
                    issue_number=123,
                    worktree_path=Path("/tmp/worktree"),
                    prompt="Implement issue",
                )

    def test_dry_run_returns_none(self, mock_options):
        """Test dry run mode returns None."""
        mock_options.dry_run = True
        implementer = IssueImplementer(mock_options)

        session_id = implementer._run_claude_code(
            issue_number=123,
            worktree_path=Path("/tmp/worktree"),
            prompt="Implement issue",
        )

        assert session_id is None


class TestRunRetrospective:
    """Tests for _run_retrospective method."""

    def test_successful_retrospective(self, implementer):
        """Test successful retrospective run."""
        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            implementer._run_retrospective(
                session_id="abc123",
                worktree_path=Path("/tmp/worktree"),
                issue_number=123,
            )

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "claude"
            assert args[1] == "--resume"
            assert args[2] == "abc123"
            assert "/skills-registry-commands:retrospective" in args[3]
            assert "--print" in args
            assert "--tools" in args
            assert "Bash" in args
            assert "--allowedTools" in args
            assert "Bash(git:*)" in args
            assert "Bash(gh:*)" in args

            # Should log success
            mock_logger.info.assert_called_once()
            assert "Retrospective completed" in str(mock_logger.info.call_args)

    def test_graceful_failure_on_error(self, implementer):
        """Test graceful failure when retrospective errors."""
        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            mock_run.side_effect = RuntimeError("Claude error")

            # Should not raise - graceful degradation
            implementer._run_retrospective(
                session_id="abc123",
                worktree_path=Path("/tmp/worktree"),
                issue_number=123,
            )

            # Should log warning
            mock_logger.warning.assert_called_once()
            assert "Retrospective failed" in str(mock_logger.warning.call_args)

    def test_timeout_is_non_blocking(self, implementer):
        """Test timeout in retrospective doesn't block pipeline."""
        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 600)

            # Should not raise
            implementer._run_retrospective(
                session_id="abc123",
                worktree_path=Path("/tmp/worktree"),
                issue_number=123,
            )

            # Should log warning
            mock_logger.warning.assert_called_once()


class TestImplementIssuePipeline:
    """Tests for _implement_issue pipeline with retrospective."""

    def test_retrospective_phase_when_enabled(self, mock_options):
        """Test retrospective phase runs when enabled."""
        mock_options.enable_retrospective = True

        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer, "_run_claude_code", return_value="session123"),
                patch.object(implementer, "_commit_changes"),
                patch.object(implementer, "_create_pr", return_value=456),
                patch.object(implementer, "_run_retrospective") as mock_retro,
                patch.object(implementer, "_save_state"),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch("scylla.automation.implementer.run"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123)
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Retrospective should have been called
                mock_retro.assert_called_once()
                assert mock_retro.call_args[0][0] == "session123"
                assert result.success is True

    def test_retrospective_phase_when_disabled(self, mock_options):
        """Test retrospective phase skipped when disabled."""
        mock_options.enable_retrospective = False

        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer, "_run_claude_code", return_value="session123"),
                patch.object(implementer, "_commit_changes"),
                patch.object(implementer, "_create_pr", return_value=456),
                patch.object(implementer, "_run_retrospective") as mock_retro,
                patch.object(implementer, "_save_state"),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch("scylla.automation.implementer.run"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123)
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Retrospective should NOT have been called
                mock_retro.assert_not_called()
                assert result.success is True

    def test_retrospective_skipped_when_no_session_id(self, mock_options):
        """Test retrospective skipped when session_id is None."""
        mock_options.enable_retrospective = True

        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer, "_run_claude_code", return_value=None),
                patch.object(implementer, "_commit_changes"),
                patch.object(implementer, "_create_pr", return_value=456),
                patch.object(implementer, "_run_retrospective") as mock_retro,
                patch.object(implementer, "_save_state"),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch("scylla.automation.implementer.run"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123)
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Retrospective should NOT have been called (no session_id)
                mock_retro.assert_not_called()
                assert result.success is True


class TestParseFollowUpItems:
    """Tests for _parse_follow_up_items method."""

    def test_valid_json_in_code_block(self, implementer):
        """Test parsing JSON from code blocks."""
        text = """Here are the follow-up items:
```json
[
  {
    "title": "Add tests",
    "body": "Need more tests",
    "labels": ["test"]
  }
]
```
"""
        items = implementer._parse_follow_up_items(text)

        assert len(items) == 1
        assert items[0]["title"] == "Add tests"
        assert items[0]["body"] == "Need more tests"
        assert items[0]["labels"] == ["test"]

    def test_valid_bare_json(self, implementer):
        """Test parsing bare JSON array."""
        text = '[{"title": "Fix bug", "body": "Found a bug", "labels": ["bug"]}]'

        items = implementer._parse_follow_up_items(text)

        assert len(items) == 1
        assert items[0]["title"] == "Fix bug"

    def test_empty_array(self, implementer):
        """Test parsing empty array."""
        text = "```json\n[]\n```"

        items = implementer._parse_follow_up_items(text)

        assert items == []

    def test_empty_string(self, implementer):
        """Test handling empty string."""
        items = implementer._parse_follow_up_items("")

        assert items == []

    def test_invalid_json(self, implementer):
        """Test graceful handling of invalid JSON."""
        text = "This is not valid JSON {{"

        items = implementer._parse_follow_up_items(text)

        assert items == []

    def test_missing_required_fields_skipped(self, implementer):
        """Test that items missing required fields are skipped."""
        text = """
[
  {"title": "Valid item", "body": "Has both fields", "labels": []},
  {"title": "Missing body"},
  {"body": "Missing title"},
  {"title": "Another valid", "body": "Also valid"}
]
"""
        items = implementer._parse_follow_up_items(text)

        assert len(items) == 2
        assert items[0]["title"] == "Valid item"
        assert items[1]["title"] == "Another valid"

    def test_caps_at_five_items(self, implementer):
        """Test that items are capped at 5."""
        items_json = [{"title": f"Item {i}", "body": f"Body {i}", "labels": []} for i in range(10)]
        text = f"```json\n{json.dumps(items_json)}\n```"

        items = implementer._parse_follow_up_items(text)

        assert len(items) == 5


class TestRunFollowUpIssues:
    """Tests for _run_follow_up_issues method."""

    def test_successful_creation(self, implementer):
        """Test successful follow-up issue creation."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {"result": '[{"title": "Add tests", "body": "Need tests", "labels": ["test"]}]'}
        )

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.gh_issue_create") as mock_create,
            patch("scylla.automation.implementer.gh_issue_comment") as mock_comment,
            patch("scylla.automation.implementer.time.sleep"),
        ):
            mock_run.return_value = mock_result
            mock_create.return_value = 456

            implementer._run_follow_up_issues("session123", Path("/tmp"), 123)

            mock_create.assert_called_once()
            assert "Need tests" in mock_create.call_args[1]["body"]
            assert "Follow-up from #123" in mock_create.call_args[1]["body"]

            mock_comment.assert_called_once()
            assert "#456" in mock_comment.call_args[0][1]

    def test_no_items_identified(self, implementer):
        """Test when no follow-up items are identified."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"result": "[]"})

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.gh_issue_create") as mock_create,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            mock_run.return_value = mock_result

            implementer._run_follow_up_issues("session123", Path("/tmp"), 123)

            mock_create.assert_not_called()
            assert any(
                "No follow-up items" in str(call) for call in mock_logger.info.call_args_list
            )

    def test_graceful_failure_on_error(self, implementer):
        """Test graceful handling when run fails."""
        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 600)

            # Should not raise
            implementer._run_follow_up_issues("session123", Path("/tmp"), 123)

            assert any("failed" in str(call).lower() for call in mock_logger.warning.call_args_list)

    def test_partial_failure_creates_available_issues(self, implementer):
        """Test that partial failures still create available issues."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "result": """[
                    {"title": "Item 1", "body": "Body 1", "labels": []},
                    {"title": "Item 2", "body": "Body 2", "labels": []}
                ]"""
            }
        )

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.gh_issue_create") as mock_create,
            patch("scylla.automation.implementer.gh_issue_comment") as mock_comment,
            patch("scylla.automation.implementer.time.sleep"),
        ):
            mock_run.return_value = mock_result
            # First succeeds, second fails
            mock_create.side_effect = [789, RuntimeError("API error")]

            implementer._run_follow_up_issues("session123", Path("/tmp"), 123)

            assert mock_create.call_count == 2
            mock_comment.assert_called_once()
            # Only successful issue in summary
            assert "#789" in mock_comment.call_args[0][1]


class TestImplementIssuePipelineFollowUp:
    """Tests for follow-up phase in _implement_issue pipeline."""

    def test_follow_up_enabled_runs_phase(self):
        """Test that follow-up phase runs when enabled and session_id exists."""
        mock_options = ImplementerOptions(
            epic_number=123,
            dry_run=False,
            max_workers=1,
            enable_follow_up=True,
        )

        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer, "_run_claude_code", return_value="session789"),
                patch.object(implementer, "_commit_changes"),
                patch.object(implementer, "_create_pr", return_value=456),
                patch.object(implementer, "_run_follow_up_issues") as mock_follow_up,
                patch.object(implementer, "_save_state"),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch("scylla.automation.implementer.run"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123, session_id="session789")
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Follow-up should have been called
                mock_follow_up.assert_called_once()
                assert result.success is True

    def test_follow_up_disabled_skips_phase(self):
        """Test that follow-up phase is skipped when disabled."""
        mock_options = ImplementerOptions(
            epic_number=123,
            dry_run=False,
            max_workers=1,
            enable_follow_up=False,
        )

        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer, "_run_claude_code", return_value="session789"),
                patch.object(implementer, "_commit_changes"),
                patch.object(implementer, "_create_pr", return_value=456),
                patch.object(implementer, "_run_follow_up_issues") as mock_follow_up,
                patch.object(implementer, "_save_state"),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch("scylla.automation.implementer.run"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123, session_id="session789")
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Follow-up should NOT have been called
                mock_follow_up.assert_not_called()
                assert result.success is True

    def test_no_session_id_skips_follow_up(self):
        """Test that follow-up is skipped when session_id is None."""
        mock_options = ImplementerOptions(
            epic_number=123,
            dry_run=False,
            max_workers=1,
            enable_follow_up=True,
        )

        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer, "_run_claude_code", return_value=None),
                patch.object(implementer, "_commit_changes"),
                patch.object(implementer, "_create_pr", return_value=456),
                patch.object(implementer, "_run_follow_up_issues") as mock_follow_up,
                patch.object(implementer, "_save_state"),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch("scylla.automation.implementer.run"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123)
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Follow-up should NOT have been called (no session_id)
                mock_follow_up.assert_not_called()
                assert result.success is True
