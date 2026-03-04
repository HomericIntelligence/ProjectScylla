"""Tests for scripts/merge_prs.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from merge_prs import check_pr_status, merge_pr

# ---------------------------------------------------------------------------
# check_pr_status
# ---------------------------------------------------------------------------


class TestCheckPrStatus:
    """Tests for check_pr_status()."""

    def test_returns_all_true_for_ready_pr(self) -> None:
        """Returns all-True dict for a PR that is ready to merge."""
        pr_data = {
            "statusCheckRollup": [
                {"conclusion": "SUCCESS"},
                {"conclusion": "SKIPPED"},
            ],
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
        }
        import json

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pr_data)

        with patch("merge_prs.subprocess.run", return_value=mock_result):
            status = check_pr_status(42)

        assert status["ci_passing"] is True
        assert status["mergeable"] is True
        assert status["approved"] is True

    def test_ci_failing_when_check_failed(self) -> None:
        """ci_passing is False when any check has FAILURE conclusion."""
        import json

        pr_data = {
            "statusCheckRollup": [{"conclusion": "FAILURE"}],
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pr_data)

        with patch("merge_prs.subprocess.run", return_value=mock_result):
            status = check_pr_status(42)

        assert status["ci_passing"] is False

    def test_not_mergeable_when_conflicts(self) -> None:
        """Mergeable is False when PR has merge conflicts."""
        import json

        pr_data = {
            "statusCheckRollup": [],
            "mergeable": "CONFLICTING",
            "reviewDecision": "APPROVED",
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pr_data)

        with patch("merge_prs.subprocess.run", return_value=mock_result):
            status = check_pr_status(42)

        assert status["mergeable"] is False

    def test_approved_when_review_decision_none(self) -> None:
        """Approved is True when reviewDecision is None (review not required)."""
        import json
        from typing import Any

        pr_data: dict[str, Any] = {
            "statusCheckRollup": [],
            "mergeable": "MERGEABLE",
            "reviewDecision": None,
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pr_data)

        with patch("merge_prs.subprocess.run", return_value=mock_result):
            status = check_pr_status(42)

        assert status["approved"] is True

    def test_returns_all_false_on_gh_failure(self) -> None:
        """Returns all-False dict when gh CLI call fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("merge_prs.subprocess.run", return_value=mock_result):
            status = check_pr_status(42)

        assert status["ci_passing"] is False
        assert status["mergeable"] is False
        assert status["approved"] is False

    def test_all_neutral_checks_pass(self) -> None:
        """NEUTRAL checks are treated as passing."""
        import json

        pr_data = {
            "statusCheckRollup": [{"conclusion": "NEUTRAL"}],
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pr_data)

        with patch("merge_prs.subprocess.run", return_value=mock_result):
            status = check_pr_status(42)

        assert status["ci_passing"] is True


# ---------------------------------------------------------------------------
# merge_pr
# ---------------------------------------------------------------------------


class TestMergePr:
    """Tests for merge_pr()."""

    def test_dry_run_returns_true_without_calling_gh(self) -> None:
        """Dry-run mode returns True without calling subprocess."""
        with patch("merge_prs.subprocess.run") as mock_run:
            result = merge_pr(42, dry_run=True)
        assert result is True
        mock_run.assert_not_called()

    def test_successful_merge_returns_true(self) -> None:
        """Returns True when gh pr merge succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("merge_prs.subprocess.run", return_value=mock_result):
            result = merge_pr(42)

        assert result is True

    def test_failed_merge_returns_false(self) -> None:
        """Returns False when gh pr merge fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Merge failed"

        with patch("merge_prs.subprocess.run", return_value=mock_result):
            result = merge_pr(42)

        assert result is False

    def test_uses_rebase_strategy(self) -> None:
        """Gh pr merge is called with --rebase flag."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("merge_prs.subprocess.run", return_value=mock_result) as mock_run:
            merge_pr(42)

        call_args = mock_run.call_args[0][0]
        assert "--rebase" in call_args
