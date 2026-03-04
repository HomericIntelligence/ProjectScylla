"""Tests for scripts/get_stats.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from get_stats import get_issues_stats, get_prs_stats


class TestGetIssuesStats:
    """Tests for get_issues_stats()."""

    def test_returns_counts_on_success(self) -> None:
        """Returns dict with total/open/closed when gh CLI succeeds."""
        mock_total = MagicMock()
        mock_total.returncode = 0
        mock_total.stdout = "10\n"

        mock_open = MagicMock()
        mock_open.returncode = 0
        mock_open.stdout = "3\n"

        with patch("get_stats.subprocess.run", side_effect=[mock_total, mock_open]):
            result = get_issues_stats("2026-01-01", "2026-01-31", None, "owner/repo")

        assert result["total"] == 10
        assert result["open"] == 3
        assert result["closed"] == 7

    def test_returns_zeros_on_gh_failure(self) -> None:
        """Returns all-zero dict when gh CLI fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("get_stats.subprocess.run", return_value=mock_result):
            result = get_issues_stats("2026-01-01", "2026-01-31", None, "owner/repo")

        assert result == {"total": 0, "open": 0, "closed": 0}

    def test_includes_author_filter_in_query(self) -> None:
        """Adds author filter to gh CLI query when author is specified."""
        mock_total = MagicMock()
        mock_total.returncode = 0
        mock_total.stdout = "5\n"

        mock_open = MagicMock()
        mock_open.returncode = 0
        mock_open.stdout = "2\n"

        with patch("get_stats.subprocess.run", side_effect=[mock_total, mock_open]) as mock_run:
            get_issues_stats("2026-01-01", "2026-01-31", "alice", "owner/repo")

        # Check that the query passed to gh includes author filter
        first_call_args = mock_run.call_args_list[0][0][0]
        query_arg = next((a for a in first_call_args if "author:alice" in str(a)), None)
        assert query_arg is not None


class TestGetPrsStats:
    """Tests for get_prs_stats()."""

    def test_returns_counts_on_success(self) -> None:
        """Returns dict with total/merged/open/closed when gh CLI succeeds."""
        mock_total = MagicMock()
        mock_total.returncode = 0
        mock_total.stdout = "20\n"

        mock_merged = MagicMock()
        mock_merged.returncode = 0
        mock_merged.stdout = "15\n"

        mock_open = MagicMock()
        mock_open.returncode = 0
        mock_open.stdout = "3\n"

        with patch(
            "get_stats.subprocess.run",
            side_effect=[mock_total, mock_merged, mock_open],
        ):
            result = get_prs_stats("2026-01-01", "2026-01-31", None, "owner/repo")

        assert result["total"] == 20
        assert result["merged"] == 15
        assert result["open"] == 3
        assert result["closed"] == 2

    def test_returns_zeros_on_gh_failure(self) -> None:
        """Returns all-zero dict when gh CLI fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("get_stats.subprocess.run", return_value=mock_result):
            result = get_prs_stats("2026-01-01", "2026-01-31", None, "owner/repo")

        assert result == {"total": 0, "merged": 0, "open": 0, "closed": 0}

    def test_no_author_filter_by_default(self) -> None:
        """Does not add author filter when author is None."""
        mock_total = MagicMock()
        mock_total.returncode = 0
        mock_total.stdout = "0\n"

        mock_merged = MagicMock()
        mock_merged.returncode = 0
        mock_merged.stdout = "0\n"

        mock_open = MagicMock()
        mock_open.returncode = 0
        mock_open.stdout = "0\n"

        with patch(
            "get_stats.subprocess.run",
            side_effect=[mock_total, mock_merged, mock_open],
        ) as mock_run:
            get_prs_stats("2026-01-01", "2026-01-31", None, "owner/repo")

        first_call_args = mock_run.call_args_list[0][0][0]
        assert not any("author:" in str(a) for a in first_call_args)
