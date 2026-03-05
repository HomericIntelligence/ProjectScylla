"""Tests for the retrospective module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from scylla.automation.retrospective import retrospective_needs_rerun, run_retrospective


class TestRetrospectiveNeedsRerun:
    """Tests for retrospective_needs_rerun."""

    def test_missing_log_returns_true(self, tmp_path: Path) -> None:
        """Returns True when log file doesn't exist."""
        assert retrospective_needs_rerun(42, tmp_path) is True

    def test_failed_log_returns_true(self, tmp_path: Path) -> None:
        """Returns True when log file starts with FAILED:."""
        log_file = tmp_path / "retrospective-42.log"
        log_file.write_text("FAILED: something went wrong\nmore output")
        assert retrospective_needs_rerun(42, tmp_path) is True

    def test_successful_log_returns_false(self, tmp_path: Path) -> None:
        """Returns False when log file has successful content."""
        log_file = tmp_path / "retrospective-42.log"
        log_file.write_text("Retrospective completed successfully.")
        assert retrospective_needs_rerun(42, tmp_path) is False

    def test_empty_log_returns_false(self, tmp_path: Path) -> None:
        """Returns False for an empty log file (not failed)."""
        log_file = tmp_path / "retrospective-42.log"
        log_file.write_text("")
        assert retrospective_needs_rerun(42, tmp_path) is False

    def test_unreadable_log_returns_true(self, tmp_path: Path) -> None:
        """Returns True when log file cannot be read."""
        log_file = tmp_path / "retrospective-42.log"
        log_file.write_text("content")
        log_file.chmod(0o000)
        try:
            assert retrospective_needs_rerun(42, tmp_path) is True
        finally:
            log_file.chmod(0o644)


class TestRunRetrospective:
    """Tests for run_retrospective."""

    def test_success_writes_log_and_returns_true(self, tmp_path: Path) -> None:
        """Returns True and writes log on successful claude run."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = "Retrospective complete. PR created."

        with patch("scylla.automation.retrospective.run", return_value=mock_result):
            result = run_retrospective("session-abc", worktree_path, 42, tmp_path)

        assert result is True
        log_file = tmp_path / "retrospective-42.log"
        assert log_file.exists()
        assert log_file.read_text() == "Retrospective complete. PR created."

    def test_failure_writes_failed_log_and_returns_false(self, tmp_path: Path) -> None:
        """Returns False and writes FAILED: log on exception."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with patch(
            "scylla.automation.retrospective.run", side_effect=RuntimeError("claude crashed")
        ):
            result = run_retrospective("session-abc", worktree_path, 42, tmp_path)

        assert result is False
        log_file = tmp_path / "retrospective-42.log"
        assert log_file.exists()
        assert log_file.read_text().startswith("FAILED:")

    def test_creates_state_dir_if_missing(self, tmp_path: Path) -> None:
        """Creates state_dir if it does not exist."""
        state_dir = tmp_path / "nested" / "state"
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = "done"

        with patch("scylla.automation.retrospective.run", return_value=mock_result):
            run_retrospective("session-abc", worktree_path, 42, state_dir)

        assert state_dir.exists()

    def test_slot_id_accepted(self, tmp_path: Path) -> None:
        """slot_id parameter is accepted without error."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = "done"

        with patch("scylla.automation.retrospective.run", return_value=mock_result):
            result = run_retrospective("session-abc", worktree_path, 42, tmp_path, slot_id=3)

        assert result is True
