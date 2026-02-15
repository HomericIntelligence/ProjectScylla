"""Tests for the IssueImplementer automation."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.automation.implementer import IssueImplementer
from scylla.automation.models import ImplementerOptions, IssueInfo


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

    def test_captures_session_id_from_json(self, implementer, tmp_path):
        """Test successful session_id capture from JSON output."""
        implementer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir(exist_ok=True)

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
        ):
            mock_run.return_value = mock_result

            session_id = implementer._run_claude_code(
                issue_number=123,
                worktree_path=worktree_path,
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
            # Verify permission mode and allowed tools
            assert "--permission-mode" in args
            assert "dontAsk" in args
            assert "--allowedTools" in args
            assert "Read,Write,Edit,Glob,Grep,Bash" in args

    def test_graceful_failure_on_json_parse_error(self, implementer, tmp_path):
        """Test graceful handling when JSON parse fails."""
        implementer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir(exist_ok=True)

        mock_result = MagicMock()
        mock_result.stdout = "Not valid JSON"

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            mock_run.return_value = mock_result

            session_id = implementer._run_claude_code(
                issue_number=123,
                worktree_path=worktree_path,
                prompt="Implement issue",
            )

            assert session_id is None
            mock_logger.warning.assert_called_once()
            assert "Could not parse session_id" in str(mock_logger.warning.call_args)

    def test_graceful_failure_on_missing_session_id(self, implementer, tmp_path):
        """Test graceful handling when session_id is missing from JSON."""
        implementer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir(exist_ok=True)

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "type": "result",
                "result": "Implementation complete",
            }
        )

        with (
            patch("scylla.automation.implementer.run") as mock_run,
        ):
            mock_run.return_value = mock_result

            session_id = implementer._run_claude_code(
                issue_number=123,
                worktree_path=worktree_path,
                prompt="Implement issue",
            )

            # Should return None when session_id is missing
            assert session_id is None

    def test_timeout_raises_runtime_error(self, implementer, tmp_path):
        """Test timeout handling."""
        implementer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir(exist_ok=True)

        with (
            patch("scylla.automation.implementer.run") as mock_run,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 1800)

            with pytest.raises(RuntimeError, match="timed out"):
                implementer._run_claude_code(
                    issue_number=123,
                    worktree_path=worktree_path,
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

    def test_claude_code_output_saved_to_log(self, implementer, tmp_path):
        """Test that Claude Code stdout is saved to log file on success."""
        # Use tmp_path for state_dir to enable actual file writes
        implementer.state_dir = tmp_path
        implementer.state_dir.mkdir(exist_ok=True)

        # Create worktree directory
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir(exist_ok=True)

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "type": "result",
                "session_id": "test-session-123",
                "result": "Implementation complete",
            }
        )

        with (
            patch("scylla.automation.implementer.run") as mock_run,
        ):
            mock_run.return_value = mock_result

            implementer._run_claude_code(
                issue_number=123,
                worktree_path=worktree_path,
                prompt="Implement issue",
            )

            # Verify log file was created and contains stdout
            log_file = tmp_path / "claude-123.log"
            assert log_file.exists()
            assert "test-session-123" in log_file.read_text()

    def test_claude_code_failure_saved_to_log(self, implementer, tmp_path):
        """Test that Claude Code failure output is saved to log file."""
        # Use tmp_path for state_dir
        implementer.state_dir = tmp_path
        implementer.state_dir.mkdir(exist_ok=True)

        # Create worktree directory
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir(exist_ok=True)

        with (
            patch("scylla.automation.implementer.run") as mock_run,
        ):
            error = subprocess.CalledProcessError(
                returncode=1,
                cmd=["claude"],
                output="Some output",
                stderr="Error message",
            )
            error.stdout = "Claude stdout output"
            error.stderr = "Claude stderr output"
            mock_run.side_effect = error

            with pytest.raises(RuntimeError, match="Claude Code failed"):
                implementer._run_claude_code(
                    issue_number=456,
                    worktree_path=worktree_path,
                    prompt="Implement issue",
                )

            # Verify log file was created with failure details
            log_file = tmp_path / "claude-456.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "EXIT CODE: 1" in content
            assert "Claude stdout output" in content
            assert "Claude stderr output" in content


class TestRunRetrospective:
    """Tests for _run_retrospective method."""

    def test_successful_retrospective(self, implementer, tmp_path):
        """Test successful retrospective run."""
        # Use tmp_path for state_dir to enable actual file writes
        implementer.state_dir = tmp_path
        implementer.state_dir.mkdir(exist_ok=True)

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            # Mock successful run with stdout
            mock_run.return_value = MagicMock(stdout="Retrospective output")

            result = implementer._run_retrospective(
                session_id="abc123",
                worktree_path=Path("/tmp/worktree"),
                issue_number=123,
                slot_id=None,
            )

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            kwargs = mock_run.call_args[1]

            # Verify command args
            assert args[0] == "claude"
            assert args[1] == "--resume"
            assert args[2] == "abc123"
            assert "/skills-registry-commands:retrospective" in args[3]
            assert "--print" in args
            assert "--permission-mode" in args
            assert "dontAsk" in args
            assert "--allowedTools" in args
            assert "Read,Write,Edit,Glob,Grep,Bash" in args

            # Verify cwd is worktree_path, not repo_root
            assert kwargs["cwd"] == Path("/tmp/worktree")

            # Verify log file was created and written
            log_file = tmp_path / "retrospective-123.log"
            assert log_file.exists()
            assert log_file.read_text() == "Retrospective output"

            # Should log success with log file path
            assert mock_logger.info.call_count == 2
            assert "Retrospective completed" in str(mock_logger.info.call_args_list[0])
            assert "Retrospective log" in str(mock_logger.info.call_args_list[1])

            # Should return True on success
            assert result is True

    def test_graceful_failure_on_error(self, implementer, tmp_path):
        """Test graceful failure when retrospective errors."""
        implementer.state_dir = tmp_path

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            mock_run.side_effect = RuntimeError("Claude error")

            # Should not raise - graceful degradation
            result = implementer._run_retrospective(
                session_id="abc123",
                worktree_path=Path("/tmp/worktree"),
                issue_number=123,
                slot_id=None,
            )

            # Should log warning
            mock_logger.warning.assert_called_once()
            assert "Retrospective failed" in str(mock_logger.warning.call_args)

            # Should return False on failure
            assert result is False

    def test_timeout_is_non_blocking(self, implementer, tmp_path):
        """Test timeout in retrospective doesn't block pipeline."""
        implementer.state_dir = tmp_path

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 600)

            # Should not raise
            result = implementer._run_retrospective(
                session_id="abc123",
                worktree_path=Path("/tmp/worktree"),
                issue_number=123,
                slot_id=None,
            )

            # Should log warning
            mock_logger.warning.assert_called_once()

            # Should return False on timeout
            assert result is False

    def test_retrospective_failure_saved_to_log(self, implementer, tmp_path):
        """Test that retrospective failure output is saved to log file."""
        # Use tmp_path for state_dir
        implementer.state_dir = tmp_path
        implementer.state_dir.mkdir(exist_ok=True)

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger"),
        ):
            error = subprocess.CalledProcessError(
                returncode=1,
                cmd=["claude"],
                output="Retrospective output",
                stderr="Retrospective error",
            )
            error.stdout = "Retrospective stdout"
            error.stderr = "Retrospective stderr"
            mock_run.side_effect = error

            # Should not raise (non-blocking)
            result = implementer._run_retrospective(
                session_id="test123",
                worktree_path=Path("/tmp/worktree"),
                issue_number=789,
            )

            # Verify log file was created with failure details
            log_file = tmp_path / "retrospective-789.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "FAILED:" in content
            assert "Retrospective stdout" in content
            assert "Retrospective stderr" in content

            # Should return False on failure
            assert result is False

    def test_retrospective_needs_rerun_failed_log(self, implementer, tmp_path):
        """Test _retrospective_needs_rerun returns True for failed log."""
        implementer.state_dir = tmp_path

        # Create failed log file
        log_file = tmp_path / "retrospective-123.log"
        log_file.write_text("FAILED: Session not found")

        result = implementer._retrospective_needs_rerun(123)
        assert result is True

    def test_retrospective_needs_rerun_no_log(self, implementer, tmp_path):
        """Test _retrospective_needs_rerun returns True when no log exists."""
        implementer.state_dir = tmp_path

        result = implementer._retrospective_needs_rerun(123)
        assert result is True

    def test_retrospective_no_rerun_successful_log(self, implementer, tmp_path):
        """Test _retrospective_needs_rerun returns False for successful log."""
        implementer.state_dir = tmp_path

        # Create successful log file
        log_file = tmp_path / "retrospective-123.log"
        log_file.write_text("Retrospective completed successfully")

        result = implementer._retrospective_needs_rerun(123)
        assert result is False

    def test_rerun_failed_retrospectives_finds_failures(self, implementer, tmp_path):
        """Test _rerun_failed_retrospectives re-runs failed retrospectives."""
        implementer.state_dir = tmp_path

        # Create state for completed issue with failed retrospective
        from scylla.automation.models import ImplementationPhase, ImplementationState

        state = ImplementationState(
            issue_number=123,
            phase=ImplementationPhase.COMPLETED,
            retrospective_completed=False,
            session_id="session123",
            worktree_path=str(tmp_path / "worktree"),
        )
        implementer.states[123] = state

        # Create worktree directory
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        # Create failed log
        log_file = tmp_path / "retrospective-123.log"
        log_file.write_text("FAILED: Session not found")

        with (
            patch.object(implementer, "_run_retrospective", return_value=True) as mock_retro,
            patch.object(implementer, "_save_state") as mock_save,
        ):
            results = implementer._rerun_failed_retrospectives()

            # Should have re-run retrospective
            mock_retro.assert_called_once_with("session123", worktree, 123, slot_id=None)
            assert results == {123: True}
            assert state.retrospective_completed is True
            mock_save.assert_called_once()

    def test_rerun_skips_already_successful(self, implementer, tmp_path):
        """Test _rerun_failed_retrospectives skips already successful retrospectives."""
        implementer.state_dir = tmp_path

        # Create state for completed issue with successful retrospective
        from scylla.automation.models import ImplementationPhase, ImplementationState

        state = ImplementationState(
            issue_number=123,
            phase=ImplementationPhase.COMPLETED,
            retrospective_completed=True,  # Already completed
            session_id="session123",
            worktree_path=str(tmp_path / "worktree"),
        )
        implementer.states[123] = state

        with patch.object(implementer, "_run_retrospective") as mock_retro:
            results = implementer._rerun_failed_retrospectives()

            # Should NOT re-run
            mock_retro.assert_not_called()
            assert results == {}

    def test_old_state_without_retrospective_completed(self, implementer, tmp_path):
        """Test backward compatibility for old JSON files without retrospective_completed."""
        # Simulate loading old state JSON that doesn't have retrospective_completed field
        old_state_json = """
        {
            "issue_number": 123,
            "phase": "completed",
            "worktree_path": "/tmp/worktree",
            "session_id": "session123",
            "started_at": "2024-01-01T00:00:00Z",
            "attempts": 0
        }
        """

        from scylla.automation.models import ImplementationState

        # Pydantic should handle missing field with default False
        state = ImplementationState.model_validate_json(old_state_json)

        # Should default to False (correct: their retrospectives did fail)
        assert state.retrospective_completed is False
        assert state.issue_number == 123


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
                patch.object(implementer, "_ensure_pr_created", return_value=456),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    return_value=IssueInfo(number=123, title="Test issue", body="Test body"),
                ),
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
                patch.object(implementer, "_ensure_pr_created", return_value=456),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    return_value=IssueInfo(number=123, title="Test issue", body="Test body"),
                ),
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
                patch.object(implementer, "_ensure_pr_created", return_value=456),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    return_value=IssueInfo(number=123, title="Test issue", body="Test body"),
                ),
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

    def test_successful_creation(self, implementer, tmp_path):
        """Test successful follow-up issue creation."""
        implementer.state_dir = tmp_path

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

    def test_no_items_identified(self, implementer, tmp_path):
        """Test when no follow-up items are identified."""
        implementer.state_dir = tmp_path

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

    def test_graceful_failure_on_error(self, implementer, tmp_path):
        """Test graceful handling when run fails."""
        implementer.state_dir = tmp_path

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 600)

            # Should not raise
            implementer._run_follow_up_issues("session123", Path("/tmp"), 123)

            assert any("failed" in str(call).lower() for call in mock_logger.warning.call_args_list)

    def test_partial_failure_creates_available_issues(self, implementer, tmp_path):
        """Test that partial failures still create available issues."""
        implementer.state_dir = tmp_path

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

    def test_follow_up_output_saved_to_log(self, implementer, tmp_path):
        """Test that follow-up output is saved to log file on success."""
        # Use tmp_path for state_dir
        implementer.state_dir = tmp_path
        implementer.state_dir.mkdir(exist_ok=True)

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {"result": '[{"title": "Follow-up", "body": "Body", "labels": []}]'}
        )

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.gh_issue_create", return_value=999),
            patch("scylla.automation.implementer.gh_issue_comment"),
            patch("scylla.automation.implementer.time.sleep"),
        ):
            mock_run.return_value = mock_result

            implementer._run_follow_up_issues("session456", Path("/tmp"), 321)

            # Verify log file was created with output
            log_file = tmp_path / "follow-up-321.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "Follow-up" in content

    def test_follow_up_failure_saved_to_log(self, implementer, tmp_path):
        """Test that follow-up failure output is saved to log file."""
        # Use tmp_path for state_dir
        implementer.state_dir = tmp_path
        implementer.state_dir.mkdir(exist_ok=True)

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger"),
        ):
            error = subprocess.CalledProcessError(
                returncode=1,
                cmd=["claude"],
                output="Follow-up output",
                stderr="Follow-up error",
            )
            error.stdout = "Follow-up stdout"
            error.stderr = "Follow-up stderr"
            mock_run.side_effect = error

            # Should not raise (non-blocking)
            implementer._run_follow_up_issues("session456", Path("/tmp"), 555)

            # Verify log file was created with failure details
            log_file = tmp_path / "follow-up-555.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "FAILED:" in content
            assert "Follow-up stdout" in content
            assert "Follow-up stderr" in content


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
                patch.object(implementer, "_ensure_pr_created", return_value=456),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    return_value=IssueInfo(number=123, title="Test issue", body="Test body"),
                ),
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
                patch.object(implementer, "_ensure_pr_created", return_value=456),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    return_value=IssueInfo(number=123, title="Test issue", body="Test body"),
                ),
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
                patch.object(implementer, "_ensure_pr_created", return_value=456),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    return_value=IssueInfo(number=123, title="Test issue", body="Test body"),
                ),
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


class TestLogHelper:
    """Tests for _log helper method."""

    def test_log_helper_routes_to_ui(self, implementer):
        """Test that _log writes to both logger and log_manager."""
        with (
            patch("scylla.automation.implementer.logger") as mock_logger,
            patch.object(implementer.log_manager, "log") as mock_log_manager,
            patch("scylla.automation.implementer.threading") as mock_threading,
        ):
            mock_threading.get_ident.return_value = 12345

            implementer._log("error", "Test error message")

            # Should log to standard logger
            mock_logger.error.assert_called_once_with("Test error message")

            # Should log to UI with ERROR prefix
            mock_log_manager.assert_called_once_with(12345, "ERROR: Test error message")

    def test_log_helper_warning_level(self, implementer):
        """Test _log with warning level."""
        with (
            patch("scylla.automation.implementer.logger") as mock_logger,
            patch.object(implementer.log_manager, "log") as mock_log_manager,
            patch("scylla.automation.implementer.threading") as mock_threading,
        ):
            mock_threading.get_ident.return_value = 12345

            implementer._log("warning", "Test warning")

            mock_logger.warning.assert_called_once_with("Test warning")
            mock_log_manager.assert_called_once_with(12345, "WARN: Test warning")

    def test_log_helper_info_level(self, implementer):
        """Test _log with info level (no prefix)."""
        with (
            patch("scylla.automation.implementer.logger") as mock_logger,
            patch.object(implementer.log_manager, "log") as mock_log_manager,
            patch("scylla.automation.implementer.threading") as mock_threading,
        ):
            mock_threading.get_ident.return_value = 12345

            implementer._log("info", "Test info")

            mock_logger.info.assert_called_once_with("Test info")
            mock_log_manager.assert_called_once_with(12345, "Test info")

    def test_log_helper_custom_thread_id(self, implementer):
        """Test _log with custom thread_id."""
        with (
            patch("scylla.automation.implementer.logger") as mock_logger,
            patch.object(implementer.log_manager, "log") as mock_log_manager,
        ):
            implementer._log("error", "Custom thread", thread_id=99999)

            mock_logger.error.assert_called_once_with("Custom thread")
            mock_log_manager.assert_called_once_with(99999, "ERROR: Custom thread")


class TestErrorVisibility:
    """Tests for error visibility in UI."""

    def test_failure_shows_in_status_slot(self, mock_options):
        """Test that slot shows FAILED before release."""
        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch.object(implementer, "_save_state"),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    side_effect=RuntimeError("API error"),
                ),
                patch.object(implementer.status_tracker, "update_slot") as mock_update,
                patch.object(implementer.status_tracker, "release_slot"),
                patch.object(implementer.status_tracker, "acquire_slot", return_value=0),
                patch("scylla.automation.implementer.time.sleep"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123)
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Should show failure in slot before release
                assert any(
                    "FAILED" in str(call) and "#123" in str(call)
                    for call in mock_update.call_args_list
                )
                assert result.success is False

    def test_exception_classification_timeout(self, mock_options):
        """Test TimeoutExpired exceptions are classified correctly."""
        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch.object(implementer, "_save_state"),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    side_effect=subprocess.TimeoutExpired(["claude", "code"], 1800),
                ),
                patch.object(implementer.status_tracker, "update_slot"),
                patch.object(implementer.status_tracker, "release_slot"),
                patch.object(implementer.status_tracker, "acquire_slot", return_value=0),
                patch.object(implementer, "_log") as mock_log,
                patch("scylla.automation.implementer.time.sleep"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123)
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Should log with "Timeout" classification
                assert any("Timeout" in str(call) for call in mock_log.call_args_list)
                assert result.success is False

    def test_exception_classification_called_process_error(self, mock_options):
        """Test CalledProcessError exceptions are classified correctly."""
        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=True),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch.object(implementer, "_save_state"),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    side_effect=subprocess.CalledProcessError(
                        1, ["gh", "issue", "view"], stderr="Error"
                    ),
                ),
                patch.object(implementer.status_tracker, "update_slot"),
                patch.object(implementer.status_tracker, "release_slot"),
                patch.object(implementer.status_tracker, "acquire_slot", return_value=0),
                patch.object(implementer, "_log") as mock_log,
                patch("scylla.automation.implementer.time.sleep"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123)
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Should log with "Command failed" classification
                assert any("Command failed" in str(call) for call in mock_log.call_args_list)
                assert result.success is False


class TestGranularStatusUpdates:
    """Tests for granular status updates."""

    def test_granular_status_updates(self, mock_options):
        """Test that status shows granular sub-steps."""
        with (
            patch("scylla.automation.implementer.get_repo_root"),
            patch.object(Path, "mkdir"),
        ):
            implementer = IssueImplementer(mock_options)

            with (
                patch.object(implementer, "_get_or_create_state") as mock_state,
                patch.object(implementer, "_has_plan", return_value=False),
                patch.object(implementer, "_generate_plan"),
                patch.object(implementer, "_run_claude_code", return_value="session123"),
                patch.object(implementer, "_ensure_pr_created", return_value=456),
                patch(
                    "scylla.automation.implementer.fetch_issue_info",
                    return_value=IssueInfo(number=123, title="Test", body="Body"),
                ),
                patch.object(implementer, "_save_state"),
                patch.object(implementer.worktree_manager, "create_worktree"),
                patch.object(implementer.status_tracker, "update_slot") as mock_update,
                patch.object(implementer.status_tracker, "release_slot"),
                patch.object(implementer.status_tracker, "acquire_slot", return_value=0),
                patch("scylla.automation.implementer.time.sleep"),
            ):
                from scylla.automation.models import ImplementationState

                mock_state_obj = ImplementationState(issue_number=123)
                mock_state.return_value = mock_state_obj

                result = implementer._implement_issue(123)

                # Should have multiple granular status updates
                status_messages = [str(call) for call in mock_update.call_args_list]

                # Check for key sub-steps
                assert any("Creating worktree" in msg for msg in status_messages)
                assert any("Checking plan" in msg for msg in status_messages)
                assert any("Generating plan" in msg for msg in status_messages)
                assert any("Fetching issue" in msg for msg in status_messages)
                assert any("Running Claude Code" in msg for msg in status_messages)

                assert result.success is True
