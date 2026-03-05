"""Tests for the pr_manager module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.automation.pr_manager import commit_changes, create_pr, ensure_pr_created


class TestCommitChanges:
    """Tests for commit_changes."""

    def test_raises_on_no_changes(self, tmp_path: Path) -> None:
        """Raises RuntimeError when git status shows no changes."""
        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("scylla.automation.pr_manager.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="No changes to commit"):
                commit_changes(42, tmp_path)

    def test_stages_and_commits_clean_files(self, tmp_path: Path) -> None:
        """Stages files and creates commit for clean (non-secret) files."""
        status_result = MagicMock()
        status_result.stdout = "M  README.md\nA  new_file.py\n"

        commit_result = MagicMock()
        commit_result.stdout = ""

        mock_issue = MagicMock()
        mock_issue.title = "Fix something"

        with (
            patch(
                "scylla.automation.pr_manager.run",
                side_effect=[status_result, MagicMock(), commit_result],
            ) as mock_run,
            patch("scylla.automation.pr_manager.fetch_issue_info", return_value=mock_issue),
        ):
            commit_changes(42, tmp_path)

        # Second call is git add, third is git commit
        add_call = mock_run.call_args_list[1]
        assert "git" in add_call[0][0]
        assert "add" in add_call[0][0]
        assert "README.md" in add_call[0][0]
        assert "new_file.py" in add_call[0][0]

    def test_skips_secret_files(self, tmp_path: Path) -> None:
        """Skips known secret filenames when staging."""
        status_result = MagicMock()
        status_result.stdout = "M  .env\nM  id_rsa\nA  safe_file.py\n"

        mock_issue = MagicMock()
        mock_issue.title = "Fix something"

        with (
            patch(
                "scylla.automation.pr_manager.run",
                side_effect=[status_result, MagicMock(), MagicMock()],
            ) as mock_run,
            patch("scylla.automation.pr_manager.fetch_issue_info", return_value=mock_issue),
        ):
            commit_changes(42, tmp_path)

        add_call = mock_run.call_args_list[1]
        assert ".env" not in add_call[0][0]
        assert "id_rsa" not in add_call[0][0]
        assert "safe_file.py" in add_call[0][0]

    def test_skips_secret_extensions(self, tmp_path: Path) -> None:
        """Skips files with secret extensions (.pem, .key, etc.)."""
        status_result = MagicMock()
        status_result.stdout = "A  cert.pem\nA  key.key\nA  app.py\n"

        mock_issue = MagicMock()
        mock_issue.title = "Add certs"

        with (
            patch(
                "scylla.automation.pr_manager.run",
                side_effect=[status_result, MagicMock(), MagicMock()],
            ) as mock_run,
            patch("scylla.automation.pr_manager.fetch_issue_info", return_value=mock_issue),
        ):
            commit_changes(42, tmp_path)

        add_call = mock_run.call_args_list[1]
        assert "cert.pem" not in add_call[0][0]
        assert "key.key" not in add_call[0][0]
        assert "app.py" in add_call[0][0]

    def test_raises_when_all_files_are_secrets(self, tmp_path: Path) -> None:
        """Raises RuntimeError when all changed files are secret files."""
        status_result = MagicMock()
        status_result.stdout = "M  .env\nM  credentials.json\n"

        with patch("scylla.automation.pr_manager.run", return_value=status_result):
            with pytest.raises(RuntimeError, match="No non-secret files"):
                commit_changes(42, tmp_path)

    def test_handles_renamed_files(self, tmp_path: Path) -> None:
        """Correctly parses renamed files (R  old -> new format)."""
        status_result = MagicMock()
        status_result.stdout = "R  old_name.py -> new_name.py\n"

        mock_issue = MagicMock()
        mock_issue.title = "Rename file"

        with (
            patch(
                "scylla.automation.pr_manager.run",
                side_effect=[status_result, MagicMock(), MagicMock()],
            ) as mock_run,
            patch("scylla.automation.pr_manager.fetch_issue_info", return_value=mock_issue),
        ):
            commit_changes(42, tmp_path)

        add_call = mock_run.call_args_list[1]
        assert "new_name.py" in add_call[0][0]
        assert "old_name.py" not in add_call[0][0]


class TestEnsurePrCreated:
    """Tests for ensure_pr_created."""

    def test_returns_existing_pr_number(self, tmp_path: Path) -> None:
        """Returns existing PR number when PR already exists."""
        log_result = MagicMock()
        log_result.stdout = "abc1234 feat: implement"

        remote_result = MagicMock()
        remote_result.stdout = "abc1234\trefs/heads/branch"

        pr_list_result = MagicMock()
        pr_list_result.stdout = json.dumps([{"number": 99}])

        with (
            patch(
                "scylla.automation.pr_manager.run",
                side_effect=[log_result, remote_result],
            ),
            patch("scylla.automation.pr_manager._gh_call", return_value=pr_list_result),
        ):
            pr_num = ensure_pr_created(42, "42-branch", tmp_path)

        assert pr_num == 99

    def test_creates_pr_when_none_exists(self, tmp_path: Path) -> None:
        """Creates a new PR when no existing PR is found."""
        log_result = MagicMock()
        log_result.stdout = "abc1234 feat: implement"

        remote_result = MagicMock()
        remote_result.stdout = "abc1234\trefs/heads/branch"

        pr_list_result = MagicMock()
        pr_list_result.stdout = json.dumps([])

        mock_issue = MagicMock()
        mock_issue.title = "Fix thing"

        with (
            patch(
                "scylla.automation.pr_manager.run",
                side_effect=[log_result, remote_result],
            ),
            patch("scylla.automation.pr_manager._gh_call", return_value=pr_list_result),
            patch("scylla.automation.pr_manager.fetch_issue_info", return_value=mock_issue),
            patch("scylla.automation.pr_manager.gh_pr_create", return_value=55),
        ):
            pr_num = ensure_pr_created(42, "42-branch", tmp_path)

        assert pr_num == 55

    def test_raises_when_no_commit_exists(self, tmp_path: Path) -> None:
        """Raises RuntimeError when git log shows no commits."""
        log_result = MagicMock()
        log_result.stdout = ""

        with patch("scylla.automation.pr_manager.run", return_value=log_result):
            with pytest.raises(RuntimeError, match="No commit found"):
                ensure_pr_created(42, "42-branch", tmp_path)

    def test_pushes_branch_when_not_on_remote(self, tmp_path: Path) -> None:
        """Pushes branch when it is not yet on remote."""
        log_result = MagicMock()
        log_result.stdout = "abc1234 feat: implement"

        remote_result = MagicMock()
        remote_result.stdout = ""  # Not on remote

        push_result = MagicMock()
        pr_list_result = MagicMock()
        pr_list_result.stdout = json.dumps([{"number": 77}])

        with (
            patch(
                "scylla.automation.pr_manager.run",
                side_effect=[log_result, remote_result, push_result],
            ),
            patch("scylla.automation.pr_manager._gh_call", return_value=pr_list_result),
        ):
            pr_num = ensure_pr_created(42, "42-branch", tmp_path)

        assert pr_num == 77

    def test_status_tracker_updated(self, tmp_path: Path) -> None:
        """Status tracker is updated when slot_id is provided."""
        log_result = MagicMock()
        log_result.stdout = "abc1234 feat: implement"

        remote_result = MagicMock()
        remote_result.stdout = "abc1234\trefs/heads/branch"

        pr_list_result = MagicMock()
        pr_list_result.stdout = json.dumps([{"number": 88}])

        mock_tracker = MagicMock()

        with (
            patch(
                "scylla.automation.pr_manager.run",
                side_effect=[log_result, remote_result],
            ),
            patch("scylla.automation.pr_manager._gh_call", return_value=pr_list_result),
        ):
            ensure_pr_created(42, "42-branch", tmp_path, status_tracker=mock_tracker, slot_id=2)

        assert mock_tracker.update_slot.call_count >= 2


class TestCreatePr:
    """Tests for create_pr."""

    def test_creates_pr_with_correct_title(self) -> None:
        """Creates PR with title derived from issue title."""
        mock_issue = MagicMock()
        mock_issue.title = "Add new feature"

        with (
            patch("scylla.automation.pr_manager.fetch_issue_info", return_value=mock_issue),
            patch("scylla.automation.pr_manager.gh_pr_create", return_value=123) as mock_create,
        ):
            pr_num = create_pr(42, "42-branch")

        assert pr_num == 123
        call_kwargs = mock_create.call_args[1]
        assert "Add new feature" in call_kwargs["title"]

    def test_passes_auto_merge_flag(self) -> None:
        """Passes auto_merge flag to gh_pr_create."""
        mock_issue = MagicMock()
        mock_issue.title = "Fix bug"

        with (
            patch("scylla.automation.pr_manager.fetch_issue_info", return_value=mock_issue),
            patch("scylla.automation.pr_manager.gh_pr_create", return_value=99) as mock_create,
        ):
            create_pr(42, "42-branch", auto_merge=True)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["auto_merge"] is True
