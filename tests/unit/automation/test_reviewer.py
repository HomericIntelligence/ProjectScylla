"""Tests for the PRReviewer automation."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.automation.models import ReviewerOptions, ReviewPhase, ReviewState
from scylla.automation.reviewer import PRReviewer


@pytest.fixture
def mock_options() -> ReviewerOptions:
    """Create mock ReviewerOptions."""
    return ReviewerOptions(
        issues=[595, 596],
        max_workers=1,
        dry_run=False,
        enable_retrospective=False,
        enable_ui=False,
    )


@pytest.fixture
def reviewer(mock_options: ReviewerOptions) -> PRReviewer:
    """Create a PRReviewer instance with mocked filesystem."""
    with (
        patch("scylla.automation.reviewer.get_repo_root") as mock_repo,
        patch.object(Path, "mkdir"),
    ):
        mock_repo.return_value = Path("/repo")
        return PRReviewer(mock_options)


class TestReviewerOptions:
    """Tests for ReviewerOptions model."""

    def test_default_values(self) -> None:
        """Test ReviewerOptions defaults."""
        opts = ReviewerOptions()
        assert opts.issues == []
        assert opts.max_workers == 3
        assert opts.dry_run is False
        assert opts.enable_retrospective is True
        assert opts.enable_ui is True

    def test_custom_values(self) -> None:
        """Test ReviewerOptions with custom values."""
        opts = ReviewerOptions(
            issues=[1, 2, 3],
            max_workers=5,
            dry_run=True,
            enable_retrospective=False,
            enable_ui=False,
        )
        assert opts.issues == [1, 2, 3]
        assert opts.max_workers == 5
        assert opts.dry_run is True
        assert opts.enable_retrospective is False
        assert opts.enable_ui is False


class TestReviewState:
    """Tests for ReviewState model."""

    def test_default_phase(self) -> None:
        """Test ReviewState starts in ANALYZING phase."""
        state = ReviewState(issue_number=1, pr_number=10)
        assert state.phase == ReviewPhase.ANALYZING
        assert state.worktree_path is None
        assert state.branch_name is None
        assert state.plan_path is None
        assert state.session_id is None
        assert state.error is None
        assert state.completed_at is None

    def test_all_phases_exist(self) -> None:
        """Test all ReviewPhase enum values are defined."""
        phases = {p.value for p in ReviewPhase}
        assert "analyzing" in phases
        assert "fixing" in phases
        assert "pushing" in phases
        assert "retrospective" in phases
        assert "completed" in phases
        assert "failed" in phases


class TestPRDiscovery:
    """Tests for _discover_prs and _find_pr_for_issue methods."""

    def test_find_pr_via_branch_name(self, reviewer: PRReviewer) -> None:
        """Test PR discovery via branch name lookup."""
        with patch("scylla.automation.reviewer._gh_call") as mock_gh:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps([{"number": 42}])
            mock_gh.return_value = mock_result

            pr_number = reviewer._find_pr_for_issue(595)

            assert pr_number == 42
            # Verify branch-name strategy was tried
            call_args = mock_gh.call_args_list[0][0][0]
            assert "595-auto-impl" in call_args

    def test_find_pr_via_body_search_fallback(self, reviewer: PRReviewer) -> None:
        """Test PR discovery falls back to body search when branch not found."""
        with patch("scylla.automation.reviewer._gh_call") as mock_gh:
            empty_result = MagicMock()
            empty_result.stdout = "[]"

            body_result = MagicMock()
            body_result.stdout = json.dumps([{"number": 99}])

            # First call (branch lookup) returns empty, second call (search) returns PR
            mock_gh.side_effect = [empty_result, body_result]

            pr_number = reviewer._find_pr_for_issue(595)

            assert pr_number == 99
            assert mock_gh.call_count == 2

    def test_find_pr_returns_none_when_not_found(self, reviewer: PRReviewer) -> None:
        """Test returns None when no PR is found by either strategy."""
        with patch("scylla.automation.reviewer._gh_call") as mock_gh:
            empty_result = MagicMock()
            empty_result.stdout = "[]"
            mock_gh.return_value = empty_result

            pr_number = reviewer._find_pr_for_issue(595)

            assert pr_number is None

    def test_discover_prs_multiple_issues(self, reviewer: PRReviewer) -> None:
        """Test _discover_prs returns mapping for all found PRs."""
        with patch.object(reviewer, "_find_pr_for_issue") as mock_find:
            mock_find.side_effect = [42, None]

            result = reviewer._discover_prs([595, 596])

            assert result == {595: 42}
            assert 596 not in result

    def test_discover_prs_handles_gh_call_exception(self, reviewer: PRReviewer) -> None:
        """Test _find_pr_for_issue handles gh call exceptions gracefully."""
        with patch("scylla.automation.reviewer._gh_call") as mock_gh:
            mock_gh.side_effect = [
                subprocess.CalledProcessError(1, ["gh"]),
                subprocess.CalledProcessError(1, ["gh"]),
            ]

            pr_number = reviewer._find_pr_for_issue(595)

            assert pr_number is None

    def test_discover_prs_empty_issues_list(self, reviewer: PRReviewer) -> None:
        """Test _discover_prs with empty issues list returns empty dict."""
        result = reviewer._discover_prs([])
        assert result == {}


class TestGatherPRContext:
    """Tests for _gather_pr_context method."""

    def test_all_fields_populated(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that all context fields are populated on success."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_issue = MagicMock()
        mock_issue.body = "Issue description here"

        with (
            patch("scylla.automation.reviewer._gh_call") as mock_gh,
            patch("scylla.automation.reviewer.fetch_issue_info") as mock_fetch,
        ):
            mock_fetch.return_value = mock_issue

            diff_result = MagicMock()
            diff_result.stdout = "diff content here"

            pr_view_result = MagicMock()
            pr_view_result.stdout = json.dumps(
                {
                    "body": "PR description",
                    "reviews": [
                        {
                            "state": "CHANGES_REQUESTED",
                            "author": {"login": "user1"},
                            "body": "Please fix X",
                        }
                    ],
                    "comments": [{"author": {"login": "user2"}, "body": "Also fix Y"}],
                }
            )

            checks_result = MagicMock()
            checks_result.stdout = json.dumps(
                [
                    {"name": "ci/test", "state": "completed", "conclusion": "failure"},
                ]
            )

            run_list_result = MagicMock()
            run_list_result.stdout = "[]"

            mock_gh.side_effect = [diff_result, pr_view_result, checks_result, run_list_result]

            context = reviewer._gather_pr_context(42, 595, worktree_path)

        assert context["pr_diff"] == "diff content here"
        assert context["pr_description"] == "PR description"
        assert "CHANGES_REQUESTED" in context["review_comments"]
        assert "Please fix X" in context["review_comments"]
        assert "Also fix Y" in context["review_comments"]
        assert "ci/test" in context["ci_status"]
        assert "failure" in context["ci_status"]
        assert context["issue_body"] == "Issue description here"

    def test_graceful_partial_failure(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that context is still returned if some calls fail."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with (
            patch("scylla.automation.reviewer._gh_call") as mock_gh,
            patch("scylla.automation.reviewer.fetch_issue_info") as mock_fetch,
        ):
            mock_fetch.side_effect = RuntimeError("API error")
            mock_gh.side_effect = Exception("All calls fail")

            # Should not raise — returns empty strings for failed fields
            context = reviewer._gather_pr_context(42, 595, worktree_path)

        assert isinstance(context, dict)
        assert "pr_diff" in context
        assert "issue_body" in context

    def test_context_caps_long_diff(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that very long PR diffs are capped."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        long_diff = "x" * 20000

        with (
            patch("scylla.automation.reviewer._gh_call") as mock_gh,
            patch("scylla.automation.reviewer.fetch_issue_info") as mock_fetch,
        ):
            mock_fetch.side_effect = RuntimeError("skip")

            diff_result = MagicMock()
            diff_result.stdout = long_diff

            pr_view_result = MagicMock()
            pr_view_result.stdout = json.dumps({"body": "", "reviews": [], "comments": []})

            checks_result = MagicMock()
            checks_result.stdout = "[]"

            run_list_result = MagicMock()
            run_list_result.stdout = "[]"

            mock_gh.side_effect = [diff_result, pr_view_result, checks_result, run_list_result]

            context = reviewer._gather_pr_context(42, 595, worktree_path)

        # Diff should be capped at 8000 chars
        assert len(context["pr_diff"]) <= 8000


class TestRunAnalysisSession:
    """Tests for _run_analysis_session method."""

    def test_creates_plan_file(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that analysis session creates a plan file."""
        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {"result": "## Summary\nNo issues found.", "session_id": "s1"}
        )

        context = {
            "pr_diff": "",
            "issue_body": "",
            "ci_status": "",
            "ci_logs": "",
            "review_comments": "",
            "pr_description": "",
        }

        with (
            patch("scylla.automation.reviewer.run") as mock_run,
            patch("scylla.automation.reviewer.write_secure") as mock_write,
        ):
            mock_run.return_value = mock_result

            plan_path = reviewer._run_analysis_session(42, 595, worktree_path, context)

        assert plan_path is not None
        assert "review-plan-595" in plan_path
        mock_write.assert_called_once()

    def test_uses_read_only_tools(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that analysis session uses only read-only tools."""
        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"result": "plan content", "session_id": "s1"})

        context = {
            "pr_diff": "",
            "issue_body": "",
            "ci_status": "",
            "ci_logs": "",
            "review_comments": "",
            "pr_description": "",
        }

        with (
            patch("scylla.automation.reviewer.run") as mock_run,
            patch("scylla.automation.reviewer.write_secure"),
        ):
            mock_run.return_value = mock_result
            reviewer._run_analysis_session(42, 595, worktree_path, context)

            call_args = mock_run.call_args[0][0]
            assert "--allowedTools" in call_args
            tools_idx = call_args.index("--allowedTools")
            tools = call_args[tools_idx + 1]
            # Analysis must not include Write or Edit
            assert "Write" not in tools
            assert "Edit" not in tools
            assert "Read" in tools

    def test_dry_run_returns_none(self, mock_options: ReviewerOptions) -> None:
        """Test dry run mode skips analysis and returns None."""
        mock_options.dry_run = True
        with (
            patch("scylla.automation.reviewer.get_repo_root") as mock_repo,
            patch.object(Path, "mkdir"),
        ):
            mock_repo.return_value = Path("/repo")
            reviewer = PRReviewer(mock_options)

        context = {
            "pr_diff": "",
            "issue_body": "",
            "ci_status": "",
            "ci_logs": "",
            "review_comments": "",
            "pr_description": "",
        }
        plan_path = reviewer._run_analysis_session(42, 595, Path("/tmp"), context)

        assert plan_path is None

    def test_timeout_raises_runtime_error(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test timeout handling raises RuntimeError."""
        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        context = {
            "pr_diff": "",
            "issue_body": "",
            "ci_status": "",
            "ci_logs": "",
            "review_comments": "",
            "pr_description": "",
        }

        with patch("scylla.automation.reviewer.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 1200)

            with pytest.raises(RuntimeError, match="timed out"):
                reviewer._run_analysis_session(42, 595, worktree_path, context)

    def test_process_error_raises_runtime_error(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test CalledProcessError raises RuntimeError."""
        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        context = {
            "pr_diff": "",
            "issue_body": "",
            "ci_status": "",
            "ci_logs": "",
            "review_comments": "",
            "pr_description": "",
        }

        with patch("scylla.automation.reviewer.run") as mock_run:
            error = subprocess.CalledProcessError(1, ["claude"], stderr="error output")
            error.stdout = ""
            error.stderr = "error output"
            mock_run.side_effect = error

            with pytest.raises(RuntimeError, match="Analysis session failed"):
                reviewer._run_analysis_session(42, 595, worktree_path, context)


class TestRunFixSession:
    """Tests for _run_fix_session method."""

    def test_captures_session_id(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that fix session captures session_id from JSON output."""
        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        plan_file = tmp_path / "review-plan-595.md"
        plan_file.write_text("## Summary\nFix these things.")

        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"session_id": "fix-session-abc", "result": "Done"})

        with patch("scylla.automation.reviewer.run") as mock_run:
            mock_run.return_value = mock_result

            session_id = reviewer._run_fix_session(42, 595, worktree_path, str(plan_file))

        assert session_id == "fix-session-abc"

    def test_uses_full_tools(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that fix session uses full tool set including Write and Edit."""
        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        plan_file = tmp_path / "review-plan-595.md"
        plan_file.write_text("plan content")

        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"session_id": "s1", "result": "Done"})

        with patch("scylla.automation.reviewer.run") as mock_run:
            mock_run.return_value = mock_result
            reviewer._run_fix_session(42, 595, worktree_path, str(plan_file))

            call_args = mock_run.call_args[0][0]
            assert "--allowedTools" in call_args
            tools_idx = call_args.index("--allowedTools")
            tools = call_args[tools_idx + 1]
            assert "Write" in tools
            assert "Edit" in tools
            assert "Read" in tools

    def test_dry_run_returns_none(self, mock_options: ReviewerOptions) -> None:
        """Test dry run mode skips fix session and returns None."""
        mock_options.dry_run = True
        with (
            patch("scylla.automation.reviewer.get_repo_root") as mock_repo,
            patch.object(Path, "mkdir"),
        ):
            mock_repo.return_value = Path("/repo")
            reviewer = PRReviewer(mock_options)

        session_id = reviewer._run_fix_session(42, 595, Path("/tmp"), "/tmp/plan.md")
        assert session_id is None

    def test_timeout_raises_runtime_error(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test timeout handling raises RuntimeError."""
        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        plan_file = tmp_path / "plan.md"
        plan_file.write_text("plan")

        with patch("scylla.automation.reviewer.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 1800)

            with pytest.raises(RuntimeError, match="timed out"):
                reviewer._run_fix_session(42, 595, worktree_path, str(plan_file))

    def test_missing_plan_file_uses_empty_plan(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that missing plan file results in empty plan string (no crash)."""
        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"session_id": "s1", "result": "Done"})

        with patch("scylla.automation.reviewer.run") as mock_run:
            mock_run.return_value = mock_result
            # Pass a non-existent plan path
            session_id = reviewer._run_fix_session(42, 595, worktree_path, "/nonexistent/plan.md")

        assert session_id == "s1"


class TestReviewPR:
    """Tests for _review_pr end-to-end workflow."""

    def test_successful_review_returns_worker_result(
        self, reviewer: PRReviewer, tmp_path: Path
    ) -> None:
        """Test successful PR review returns WorkerResult with success=True."""
        reviewer.state_dir = tmp_path

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with (
            patch.object(reviewer.worktree_manager, "create_worktree") as mock_create,
            patch.object(reviewer, "_gather_pr_context") as mock_context,
            patch.object(reviewer, "_run_analysis_session") as mock_analysis,
            patch.object(reviewer, "_run_fix_session") as mock_fix,
            patch.object(reviewer, "_push_fixes") as mock_push,
            patch.object(reviewer, "_save_state"),
        ):
            mock_create.return_value = worktree_path
            mock_context.return_value = {
                "pr_diff": "",
                "issue_body": "",
                "ci_status": "",
                "ci_logs": "",
                "review_comments": "",
                "pr_description": "",
            }
            mock_analysis.return_value = str(tmp_path / "plan.md")
            mock_fix.return_value = "session-abc"
            mock_push.return_value = None

            result = reviewer._review_pr(595, 42)

        assert result.success is True
        assert result.issue_number == 595
        assert result.pr_number == 42

    def test_failed_slot_acquisition_returns_failure(self, reviewer: PRReviewer) -> None:
        """Test failure when no worker slot is available."""
        with patch.object(reviewer.status_tracker, "acquire_slot") as mock_acquire:
            mock_acquire.return_value = None

            result = reviewer._review_pr(595, 42)

        assert result.success is False
        assert "slot" in (result.error or "").lower()

    def test_analysis_failure_propagates(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that analysis session failure is propagated as WorkerResult failure."""
        reviewer.state_dir = tmp_path

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with (
            patch.object(reviewer.worktree_manager, "create_worktree") as mock_create,
            patch.object(reviewer, "_gather_pr_context") as mock_context,
            patch.object(reviewer, "_run_analysis_session") as mock_analysis,
            patch.object(reviewer, "_save_state"),
        ):
            mock_create.return_value = worktree_path
            mock_context.return_value = {
                "pr_diff": "",
                "issue_body": "",
                "ci_status": "",
                "ci_logs": "",
                "review_comments": "",
                "pr_description": "",
            }
            mock_analysis.side_effect = RuntimeError("Analysis failed catastrophically")

            result = reviewer._review_pr(595, 42)

        assert result.success is False
        assert "Analysis failed catastrophically" in (result.error or "")

    def test_fix_failure_propagates(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that fix session failure is propagated as WorkerResult failure."""
        reviewer.state_dir = tmp_path

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with (
            patch.object(reviewer.worktree_manager, "create_worktree") as mock_create,
            patch.object(reviewer, "_gather_pr_context") as mock_context,
            patch.object(reviewer, "_run_analysis_session") as mock_analysis,
            patch.object(reviewer, "_run_fix_session") as mock_fix,
            patch.object(reviewer, "_save_state"),
        ):
            mock_create.return_value = worktree_path
            mock_context.return_value = {
                "pr_diff": "",
                "issue_body": "",
                "ci_status": "",
                "ci_logs": "",
                "review_comments": "",
                "pr_description": "",
            }
            mock_analysis.return_value = str(tmp_path / "plan.md")
            mock_fix.side_effect = RuntimeError("Fix session timed out")

            result = reviewer._review_pr(595, 42)

        assert result.success is False
        assert "Fix session timed out" in (result.error or "")

    def test_push_failure_propagates(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that push failure is propagated as WorkerResult failure."""
        reviewer.state_dir = tmp_path

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with (
            patch.object(reviewer.worktree_manager, "create_worktree") as mock_create,
            patch.object(reviewer, "_gather_pr_context") as mock_context,
            patch.object(reviewer, "_run_analysis_session") as mock_analysis,
            patch.object(reviewer, "_run_fix_session") as mock_fix,
            patch.object(reviewer, "_push_fixes") as mock_push,
            patch.object(reviewer, "_save_state"),
        ):
            mock_create.return_value = worktree_path
            mock_context.return_value = {
                "pr_diff": "",
                "issue_body": "",
                "ci_status": "",
                "ci_logs": "",
                "review_comments": "",
                "pr_description": "",
            }
            mock_analysis.return_value = str(tmp_path / "plan.md")
            mock_fix.return_value = "s1"
            mock_push.side_effect = subprocess.CalledProcessError(1, ["git", "push"])

            result = reviewer._review_pr(595, 42)

        assert result.success is False

    def test_state_saved_as_failed_on_error(self, reviewer: PRReviewer, tmp_path: Path) -> None:
        """Test that state is saved as FAILED when an error occurs."""
        reviewer.state_dir = tmp_path

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        saved_states: list[ReviewState] = []

        def capture_save(state: ReviewState) -> None:
            saved_states.append(ReviewState(**state.model_dump()))

        with (
            patch.object(reviewer.worktree_manager, "create_worktree") as mock_create,
            patch.object(reviewer, "_gather_pr_context") as mock_context,
            patch.object(reviewer, "_run_analysis_session") as mock_analysis,
            patch.object(reviewer, "_save_state", side_effect=capture_save),
        ):
            mock_create.return_value = worktree_path
            mock_context.return_value = {
                "pr_diff": "",
                "issue_body": "",
                "ci_status": "",
                "ci_logs": "",
                "review_comments": "",
                "pr_description": "",
            }
            mock_analysis.side_effect = RuntimeError("boom")

            reviewer._review_pr(595, 42)

        # At least one saved state should be FAILED
        assert any(s.phase == ReviewPhase.FAILED for s in saved_states)

    def test_retrospective_skipped_when_disabled(
        self, reviewer: PRReviewer, tmp_path: Path
    ) -> None:
        """Test that retrospective is not called when enable_retrospective=False."""
        reviewer.state_dir = tmp_path

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with (
            patch.object(reviewer.worktree_manager, "create_worktree") as mock_create,
            patch.object(reviewer, "_gather_pr_context") as mock_context,
            patch.object(reviewer, "_run_analysis_session") as mock_analysis,
            patch.object(reviewer, "_run_fix_session") as mock_fix,
            patch.object(reviewer, "_push_fixes"),
            patch.object(reviewer, "_run_retrospective") as mock_retro,
            patch.object(reviewer, "_save_state"),
        ):
            mock_create.return_value = worktree_path
            mock_context.return_value = {
                "pr_diff": "",
                "issue_body": "",
                "ci_status": "",
                "ci_logs": "",
                "review_comments": "",
                "pr_description": "",
            }
            mock_analysis.return_value = None
            mock_fix.return_value = "session-id"

            reviewer._review_pr(595, 42)

        mock_retro.assert_not_called()

    def test_retrospective_called_when_enabled(
        self, mock_options: ReviewerOptions, tmp_path: Path
    ) -> None:
        """Test retrospective is called when enable_retrospective=True and session_id exists."""
        mock_options.enable_retrospective = True

        with (
            patch("scylla.automation.reviewer.get_repo_root") as mock_repo,
            patch.object(Path, "mkdir"),
        ):
            mock_repo.return_value = Path("/repo")
            reviewer = PRReviewer(mock_options)

        reviewer.state_dir = tmp_path
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with (
            patch.object(reviewer.worktree_manager, "create_worktree") as mock_create,
            patch.object(reviewer, "_gather_pr_context") as mock_context,
            patch.object(reviewer, "_run_analysis_session") as mock_analysis,
            patch.object(reviewer, "_run_fix_session") as mock_fix,
            patch.object(reviewer, "_push_fixes"),
            patch.object(reviewer, "_run_retrospective") as mock_retro,
            patch.object(reviewer, "_save_state"),
        ):
            mock_create.return_value = worktree_path
            mock_context.return_value = {
                "pr_diff": "",
                "issue_body": "",
                "ci_status": "",
                "ci_logs": "",
                "review_comments": "",
                "pr_description": "",
            }
            mock_analysis.return_value = None
            mock_fix.return_value = "session-abc"
            mock_retro.return_value = True

            reviewer._review_pr(595, 42)

        mock_retro.assert_called_once()
