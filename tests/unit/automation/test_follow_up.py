"""Tests for the follow_up module."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from scylla.automation.follow_up import parse_follow_up_items, run_follow_up_issues


class TestParseFollowUpItems:
    """Tests for parse_follow_up_items."""

    def test_parses_json_in_code_block(self) -> None:
        """Extracts items from fenced JSON code block."""
        text = '```json\n[{"title": "T1", "body": "B1", "labels": ["bug"]}]\n```'
        items = parse_follow_up_items(text)
        assert len(items) == 1
        assert items[0]["title"] == "T1"
        assert items[0]["body"] == "B1"
        assert items[0]["labels"] == ["bug"]

    def test_parses_bare_json_array(self) -> None:
        """Extracts items from bare JSON array without code block."""
        text = 'Some text\n[{"title": "T2", "body": "B2"}]\nmore text'
        items = parse_follow_up_items(text)
        assert len(items) == 1
        assert items[0]["title"] == "T2"
        assert items[0]["labels"] == []  # default

    def test_returns_empty_on_no_json(self) -> None:
        """Returns empty list when no JSON array found."""
        items = parse_follow_up_items("No JSON here.")
        assert items == []

    def test_caps_at_five_items(self) -> None:
        """Caps returned items at 5 even if more are present."""
        raw = json.dumps([{"title": f"T{i}", "body": f"B{i}"} for i in range(10)])
        items = parse_follow_up_items(raw)
        assert len(items) == 5

    def test_skips_items_missing_required_fields(self) -> None:
        """Skips items without title or body."""
        raw = json.dumps(
            [
                {"title": "Good", "body": "Body"},
                {"title": "Missing body"},
                {"body": "Missing title"},
            ]
        )
        items = parse_follow_up_items(raw)
        assert len(items) == 1
        assert items[0]["title"] == "Good"

    def test_skips_non_dict_items(self) -> None:
        """Skips non-dict entries in the array."""
        raw = json.dumps(
            [
                {"title": "T1", "body": "B1"},
                "not a dict",
                42,
            ]
        )
        items = parse_follow_up_items(raw)
        assert len(items) == 1

    def test_ensures_labels_is_list(self) -> None:
        """Sets labels to [] when missing or not a list."""
        raw = json.dumps(
            [
                {"title": "T1", "body": "B1", "labels": "not-a-list"},
            ]
        )
        items = parse_follow_up_items(raw)
        assert items[0]["labels"] == []

    def test_returns_empty_on_invalid_json(self) -> None:
        """Returns empty list on malformed JSON."""
        items = parse_follow_up_items("[{bad json")
        assert items == []

    def test_returns_empty_when_root_not_array(self) -> None:
        """Returns empty list when JSON root is not an array."""
        items = parse_follow_up_items('{"key": "value"}')
        assert items == []


class TestRunFollowUpIssues:
    """Tests for run_follow_up_issues."""

    def _make_claude_output(self, items: list[dict[str, Any]]) -> str:
        """Build fake JSON claude output with follow-up items."""
        return json.dumps({"result": json.dumps(items)})

    def test_creates_issues_and_posts_summary(self, tmp_path: Path) -> None:
        """Creates follow-up issues and posts a summary comment."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        items = [
            {"title": "Follow 1", "body": "Body 1", "labels": []},
            {"title": "Follow 2", "body": "Body 2", "labels": []},
        ]
        mock_result = MagicMock()
        mock_result.stdout = self._make_claude_output(items)

        with (
            patch("scylla.automation.follow_up.run", return_value=mock_result),
            patch(
                "scylla.automation.follow_up.gh_issue_create", side_effect=[101, 102]
            ) as mock_create,
            patch("scylla.automation.follow_up.gh_issue_comment") as mock_comment,
            patch("scylla.automation.follow_up.time.sleep"),
        ):
            run_follow_up_issues("sess", worktree_path, 42, tmp_path)

        assert mock_create.call_count == 2
        mock_comment.assert_called_once()
        comment_body = mock_comment.call_args[0][1]
        assert "#101" in comment_body
        assert "#102" in comment_body

    def test_no_items_skips_issue_creation(self, tmp_path: Path) -> None:
        """Does nothing when no items are identified."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"result": "No follow-ups needed."})

        with (
            patch("scylla.automation.follow_up.run", return_value=mock_result),
            patch("scylla.automation.follow_up.gh_issue_create") as mock_create,
        ):
            run_follow_up_issues("sess", worktree_path, 42, tmp_path)

        mock_create.assert_not_called()

    def test_failure_writes_log_and_does_not_raise(self, tmp_path: Path) -> None:
        """On failure, writes FAILED log and does not propagate exception."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with patch("scylla.automation.follow_up.run", side_effect=RuntimeError("claude failed")):
            # Should not raise
            run_follow_up_issues("sess", worktree_path, 42, tmp_path)

        log_file = tmp_path / "follow-up-42.log"
        assert log_file.exists()
        assert log_file.read_text().startswith("FAILED:")

    def test_cleans_up_prompt_file_on_success(self, tmp_path: Path) -> None:
        """Prompt file is removed after successful run."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"result": "[]"})

        with (
            patch("scylla.automation.follow_up.run", return_value=mock_result),
            patch("scylla.automation.follow_up.time.sleep"),
        ):
            run_follow_up_issues("sess", worktree_path, 42, tmp_path)

        prompt_file = worktree_path / ".claude-followup-42.md"
        assert not prompt_file.exists()

    def test_cleans_up_prompt_file_on_failure(self, tmp_path: Path) -> None:
        """Prompt file is removed even after failure."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with patch("scylla.automation.follow_up.run", side_effect=RuntimeError("fail")):
            run_follow_up_issues("sess", worktree_path, 42, tmp_path)

        prompt_file = worktree_path / ".claude-followup-42.md"
        assert not prompt_file.exists()

    def test_status_tracker_updated_per_item(self, tmp_path: Path) -> None:
        """Status tracker is called for each item when slot_id is provided."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        items = [{"title": "T1", "body": "B1", "labels": []}]
        mock_result = MagicMock()
        mock_result.stdout = self._make_claude_output(items)
        mock_tracker = MagicMock()

        with (
            patch("scylla.automation.follow_up.run", return_value=mock_result),
            patch("scylla.automation.follow_up.gh_issue_create", return_value=201),
            patch("scylla.automation.follow_up.gh_issue_comment"),
            patch("scylla.automation.follow_up.time.sleep"),
        ):
            run_follow_up_issues("sess", worktree_path, 42, tmp_path, mock_tracker, slot_id=1)

        mock_tracker.update_slot.assert_called_once_with(1, "#42: Creating follow-up 1/1")
