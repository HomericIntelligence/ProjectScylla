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
        enable_retrospective=False,
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

        with patch("scylla.automation.implementer.run") as mock_run:
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
            assert "--message" in args
            assert "--output-format" in args
            assert "json" in args

    def test_graceful_failure_on_json_parse_error(self, implementer):
        """Test graceful handling when JSON parse fails."""
        mock_result = MagicMock()
        mock_result.stdout = "Not valid JSON"

        with (
            patch("scylla.automation.implementer.run") as mock_run,
            patch("scylla.automation.implementer.logger") as mock_logger,
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

        with patch("scylla.automation.implementer.run") as mock_run:
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
        with patch("scylla.automation.implementer.run") as mock_run:
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
            assert "--message" in args
            assert "/skills-registry-commands:retrospective" in " ".join(args)

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
