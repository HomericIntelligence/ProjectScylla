"""Unit tests for scylla/e2e/stage_finalization.py.

Tests cover:
- stage_execute_judge: no-op when ctx.judgment already set (resume path)
- stage_finalize_run: error handling when prerequisites are missing
- stage_finalize_run: baseline_summary construction from pipeline_baseline
- stage_finalize_run: checkpoint.mark_run_completed called with correct status
- stage_finalize_run: run_result.json written with core fields
- stage_write_report: error handling when prerequisites are missing
- stage_write_report: reads process_metrics from run_result.json
- stage_write_report: tolerates missing run_result.json gracefully
- stage_cleanup_worktree: cleans up workspace for passed runs
- stage_cleanup_worktree: preserves workspace for failed runs
- stage_cleanup_worktree: cleanup failure is non-fatal
- stage_cleanup_worktree: falls back to checkpoint status when run_result is None
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.stage_finalization import (
    stage_cleanup_worktree,
    stage_execute_judge,
    stage_finalize_run,
    stage_write_report,
)
from scylla.e2e.stages import RunContext

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_run_context(tmp_path: Path) -> RunContext:
    """Minimal RunContext for stage_finalization tests."""
    from scylla.e2e.models import (
        ExperimentConfig,
        SubTestConfig,
        TierConfig,
        TierID,
    )

    run_dir = tmp_path / "run_01"
    run_dir.mkdir()
    workspace = run_dir / "workspace"
    workspace.mkdir()

    (run_dir / "agent").mkdir()
    (run_dir / "judge").mkdir()

    config = ExperimentConfig(
        experiment_id="test-finalization",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        language="python",
        models=["claude-sonnet-4-5-20250929"],
        runs_per_subtest=1,
        judge_models=["claude-opus-4-5-20251101"],
        timeout_seconds=60,
    )
    subtest = SubTestConfig(id="00-empty", name="Empty", description="Empty subtest")
    tier_config = TierConfig(tier_id=TierID.T0, subtests=[subtest])

    return RunContext(
        config=config,
        tier_id=TierID.T0,
        tier_config=tier_config,
        subtest=subtest,
        baseline=None,
        run_number=1,
        run_dir=run_dir,
        workspace=workspace,
        experiment_dir=tmp_path,
        tier_manager=MagicMock(),
        workspace_manager=MagicMock(),
        adapter=MagicMock(),
        task_prompt="Fix the bug",
    )


def _make_adapter_result(exit_code: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a minimal AdapterResult mock."""
    from scylla.e2e.models import TokenStats

    token_stats_mock = MagicMock()
    token_stats_mock.to_token_stats.return_value = TokenStats(input_tokens=100, output_tokens=50)
    result = MagicMock()
    result.exit_code = exit_code
    result.token_stats = token_stats_mock
    result.cost_usd = 0.01
    result.stderr = stderr
    result.stdout = stdout
    return result


def _make_judgment(
    passed: bool = True,
    score: float = 0.8,
    grade: str = "B",
    reasoning: str = "Good work",
) -> dict[str, Any]:
    """Build a minimal judgment dict."""
    return {
        "score": score,
        "passed": passed,
        "grade": grade,
        "reasoning": reasoning,
        "criteria_scores": {},
    }


def _make_run_result(
    ctx: RunContext,
    passed: bool = True,
) -> MagicMock:
    """Build a minimal E2ERunResult mock."""
    from scylla.e2e.models import TokenStats

    rr = MagicMock()
    rr.judge_passed = passed
    rr.judge_score = 0.8 if passed else 0.3
    rr.tokens_input = 100
    rr.tokens_output = 50
    rr.token_stats = TokenStats(input_tokens=100, output_tokens=50)
    return rr


# ---------------------------------------------------------------------------
# TestStageExecuteJudge
# ---------------------------------------------------------------------------


class TestStageExecuteJudge:
    """Tests for stage_execute_judge()."""

    def test_noop_when_judgment_already_set(self, minimal_run_context: RunContext) -> None:
        """When ctx.judgment is already set (resume), the stage is a no-op."""
        ctx = minimal_run_context
        existing_judgment: dict[str, Any] = {
            "score": 0.9,
            "passed": True,
            "grade": "A",
            "reasoning": "Pre-loaded",
        }
        ctx.judgment = existing_judgment

        # If any judge machinery were invoked, it would raise; confirm it is not
        stage_execute_judge(ctx)

        # judgment must remain exactly as-is
        assert ctx.judgment is existing_judgment

    def test_noop_does_not_modify_judges(self, minimal_run_context: RunContext) -> None:
        """Resume no-op does not alter ctx.judges."""
        ctx = minimal_run_context
        ctx.judgment = {"score": 0.5, "passed": False, "grade": "D", "reasoning": "ok"}
        ctx.judges = []

        stage_execute_judge(ctx)

        assert ctx.judges == []

    def test_raises_when_no_judge_models(self, minimal_run_context: RunContext) -> None:
        """Raises ValueError when judge_models is empty and judgment is None."""
        ctx = minimal_run_context
        # judgment is None (not a resume), and config has no judge_models after override
        ctx.judgment = None
        ctx.config = ctx.config.model_copy(update={"judge_models": []})

        with pytest.raises(ValueError, match="judge_models is required"):
            stage_execute_judge(ctx)

    def test_reloads_judge_prompt_from_disk_when_empty(
        self, minimal_run_context: RunContext
    ) -> None:
        """Defense-in-depth: reloads judge_prompt from disk when ctx.judge_prompt is empty."""
        ctx = minimal_run_context
        ctx.judgment = None
        ctx.judge_prompt = ""
        (ctx.run_dir / "judge_prompt.md").write_text("prompt from disk")

        # Patch _call_claude_judge at its source module
        valid_response = '{"score": 0.8, "passed": true, "reasoning": "ok"}'
        with patch(
            "scylla.e2e.llm_judge._call_claude_judge",
            return_value=("", "", valid_response),
        ):
            stage_execute_judge(ctx)

        assert ctx.judge_prompt == "prompt from disk"
        assert ctx.judgment is not None

    def test_raises_when_judge_prompt_empty_and_no_file(
        self, minimal_run_context: RunContext
    ) -> None:
        """Raises ValueError when judge_prompt is empty and no judge_prompt.md on disk."""
        ctx = minimal_run_context
        ctx.judgment = None
        ctx.judge_prompt = ""
        # No judge_prompt.md written to run_dir

        with pytest.raises(ValueError, match="judge_prompt is empty"):
            stage_execute_judge(ctx)

    def test_retries_on_parse_failure(self, minimal_run_context: RunContext) -> None:
        """Judge retries once with JSON reminder when first attempt returns non-JSON."""
        ctx = minimal_run_context
        ctx.judgment = None
        ctx.judge_prompt = "evaluate this"

        bad_response = "Sorry, I cannot evaluate this."
        good_response = '{"score": 0.9, "passed": true, "reasoning": "great"}'

        call_count = 0

        def mock_call_judge(prompt: str, model: str, workspace: object) -> tuple[str, str, str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("", "", bad_response)
            return ("", "", good_response)

        with patch(
            "scylla.e2e.llm_judge._call_claude_judge",
            side_effect=mock_call_judge,
        ):
            stage_execute_judge(ctx)

        assert call_count == 2
        assert ctx.judgment is not None
        assert ctx.judgment["score"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# TestStageFinalizeRun
# ---------------------------------------------------------------------------


class TestStageFinalizeRun:
    """Tests for stage_finalize_run()."""

    def test_raises_when_agent_result_missing(self, minimal_run_context: RunContext) -> None:
        """Raises RuntimeError when agent_result is None."""
        ctx = minimal_run_context
        ctx.agent_result = None
        ctx.judgment = _make_judgment()

        with pytest.raises(RuntimeError, match="agent_result is None for"):
            stage_finalize_run(ctx)

    def test_raises_when_judgment_missing(self, minimal_run_context: RunContext) -> None:
        """Raises RuntimeError when judgment is None."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = None

        with pytest.raises(RuntimeError, match="judgment is None for"):
            stage_finalize_run(ctx)

    def test_run_result_json_created(self, minimal_run_context: RunContext) -> None:
        """stage_finalize_run writes run_result.json to ctx.run_dir."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        assert (ctx.run_dir / "run_result.json").exists()

    def test_run_result_json_has_core_fields(self, minimal_run_context: RunContext) -> None:
        """run_result.json contains required E2ERunResult fields."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment(passed=True, score=0.75)
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert "run_number" in data
        assert "judge_score" in data
        assert "judge_passed" in data
        assert "cost_usd" in data
        assert data["judge_score"] == pytest.approx(0.75)
        assert data["judge_passed"] is True

    def test_ctx_run_result_set(self, minimal_run_context: RunContext) -> None:
        """After the stage, ctx.run_result is populated."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        assert ctx.run_result is not None

    def test_baseline_summary_none_when_no_pipeline_baseline(
        self, minimal_run_context: RunContext
    ) -> None:
        """baseline_pipeline_summary is None in run_result.json when pipeline_baseline absent."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.pipeline_baseline = None
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert data["baseline_pipeline_summary"] is None

    def test_baseline_summary_built_when_pipeline_baseline_set(
        self, minimal_run_context: RunContext
    ) -> None:
        """baseline_pipeline_summary is populated when ctx.pipeline_baseline is set."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.progress_steps = []
        ctx.change_results = []

        pipeline_baseline = MagicMock()
        pipeline_baseline.all_passed = True
        pipeline_baseline.build_passed = True
        pipeline_baseline.format_passed = True
        pipeline_baseline.test_passed = True
        ctx.pipeline_baseline = pipeline_baseline

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert data["baseline_pipeline_summary"] is not None
        assert data["baseline_pipeline_summary"]["all_passed"] is True

    def test_checkpoint_mark_run_completed_passed(self, minimal_run_context: RunContext) -> None:
        """checkpoint.mark_run_completed is called with 'passed' for passing run."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment(passed=True)
        ctx.progress_steps = []
        ctx.change_results = []

        mock_checkpoint = MagicMock()
        ctx.checkpoint = mock_checkpoint

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        mock_checkpoint.mark_run_completed.assert_called_once()
        call_kwargs = mock_checkpoint.mark_run_completed.call_args
        assert call_kwargs.kwargs.get("status") == "passed" or (
            len(call_kwargs.args) >= 4 and call_kwargs.args[3] == "passed"
        )

    def test_checkpoint_mark_run_completed_failed(self, minimal_run_context: RunContext) -> None:
        """checkpoint.mark_run_completed is called with 'failed' for failing run."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment(passed=False, score=0.2)
        ctx.progress_steps = []
        ctx.change_results = []

        mock_checkpoint = MagicMock()
        ctx.checkpoint = mock_checkpoint

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        mock_checkpoint.mark_run_completed.assert_called_once()
        call_kwargs = mock_checkpoint.mark_run_completed.call_args
        assert call_kwargs.kwargs.get("status") == "failed" or (
            len(call_kwargs.args) >= 4 and call_kwargs.args[3] == "failed"
        )

    def test_no_checkpoint_call_when_checkpoint_is_none(
        self, minimal_run_context: RunContext
    ) -> None:
        """No crash when ctx.checkpoint is None — mark_run_completed is not called."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.progress_steps = []
        ctx.change_results = []
        ctx.checkpoint = None

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)  # must not raise

        assert ctx.run_result is not None

    def test_process_metrics_block_written(self, minimal_run_context: RunContext) -> None:
        """run_result.json contains a process_metrics block."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert "process_metrics" in data
        pm = data["process_metrics"]
        for key in ("r_prog", "strategic_drift", "cfp", "pr_revert_rate"):
            assert key in pm

    def test_rate_limit_error_propagates(self, minimal_run_context: RunContext) -> None:
        """RateLimitError from detect_rate_limit is re-raised."""
        from datetime import datetime, timezone

        from scylla.e2e.rate_limit import RateLimitError, RateLimitInfo

        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.progress_steps = []
        ctx.change_results = []

        rate_limit_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=None,
            error_message="Rate limit detected",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=rate_limit_info):
            with pytest.raises(RateLimitError):
                stage_finalize_run(ctx)

    def test_progress_tracking_and_changes_in_json(self, minimal_run_context: RunContext) -> None:
        """run_result.json has progress_tracking and changes blocks."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert "progress_tracking" in data
        assert "changes" in data
        assert isinstance(data["progress_tracking"], list)
        assert isinstance(data["changes"], list)


# ---------------------------------------------------------------------------
# TestStageWriteReport
# ---------------------------------------------------------------------------


class TestStageWriteReport:
    """Tests for stage_write_report()."""

    def test_raises_when_run_result_missing(self, minimal_run_context: RunContext) -> None:
        """Raises RuntimeError when ctx.run_result is None."""
        ctx = minimal_run_context
        ctx.run_result = None
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()

        with pytest.raises(RuntimeError, match="run_result must be set"):
            stage_write_report(ctx)

    def test_raises_when_agent_result_missing(self, minimal_run_context: RunContext) -> None:
        """Raises RuntimeError when ctx.agent_result is None."""
        ctx = minimal_run_context
        ctx.run_result = _make_run_result(ctx)
        ctx.agent_result = None
        ctx.judgment = _make_judgment()

        with pytest.raises(RuntimeError, match="agent_result is None for"):
            stage_write_report(ctx)

    def test_raises_when_judgment_missing(self, minimal_run_context: RunContext) -> None:
        """Raises RuntimeError when ctx.judgment is None."""
        ctx = minimal_run_context
        ctx.run_result = _make_run_result(ctx)
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = None

        with pytest.raises(RuntimeError, match="judgment is None for"):
            stage_write_report(ctx)

    def test_reads_process_metrics_from_run_result_json(
        self, minimal_run_context: RunContext
    ) -> None:
        """stage_write_report reads process_metrics from run_result.json on disk."""
        ctx = minimal_run_context
        ctx.run_result = _make_run_result(ctx)
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()

        # Pre-seed a run_result.json with process_metrics
        run_result_data = {
            "run_number": 1,
            "judge_score": 0.8,
            "process_metrics": {
                "r_prog": 0.6,
                "strategic_drift": 0.1,
                "cfp": 0.0,
                "pr_revert_rate": 0.0,
            },
        }
        (ctx.run_dir / "run_result.json").write_text(json.dumps(run_result_data))

        captured_pm: dict[str, Any] = {}

        def fake_save_run_report(**kwargs: Any) -> None:
            nonlocal captured_pm
            captured_pm = kwargs.get("process_metrics") or {}

        with (
            patch(
                "scylla.e2e.run_report.save_run_report",
                side_effect=fake_save_run_report,
            ),
            patch("scylla.e2e.run_report.save_run_report_json"),
        ):
            stage_write_report(ctx)

        assert captured_pm.get("r_prog") == pytest.approx(0.6)

    def test_tolerates_missing_run_result_json(self, minimal_run_context: RunContext) -> None:
        """stage_write_report does not crash when run_result.json is absent."""
        ctx = minimal_run_context
        ctx.run_result = _make_run_result(ctx)
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()

        # No run_result.json present — process_metrics will be None
        called_with_none: dict[str, Any] = {}

        def fake_save_run_report(**kwargs: Any) -> None:
            called_with_none["pm"] = kwargs.get("process_metrics")

        with (
            patch(
                "scylla.e2e.run_report.save_run_report",
                side_effect=fake_save_run_report,
            ),
            patch("scylla.e2e.run_report.save_run_report_json"),
        ):
            stage_write_report(ctx)  # must not raise

        assert called_with_none.get("pm") is None

    def test_tolerates_invalid_run_result_json(self, minimal_run_context: RunContext) -> None:
        """stage_write_report does not crash when run_result.json has invalid JSON."""
        ctx = minimal_run_context
        ctx.run_result = _make_run_result(ctx)
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()

        (ctx.run_dir / "run_result.json").write_text("{not valid json")

        with (
            patch("scylla.e2e.run_report.save_run_report"),
            patch("scylla.e2e.run_report.save_run_report_json"),
        ):
            stage_write_report(ctx)  # must not raise

    def test_save_run_report_called_with_correct_args(
        self, minimal_run_context: RunContext
    ) -> None:
        """save_run_report is called with correct tier_id, subtest_id, and run_number."""
        ctx = minimal_run_context
        ctx.run_result = _make_run_result(ctx)
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment(passed=True, score=0.85, grade="A")

        captured: dict[str, Any] = {}

        def fake_save_run_report(**kwargs: Any) -> None:
            captured.update(kwargs)

        with (
            patch(
                "scylla.e2e.run_report.save_run_report",
                side_effect=fake_save_run_report,
            ),
            patch("scylla.e2e.run_report.save_run_report_json"),
        ):
            stage_write_report(ctx)

        assert captured["tier_id"] == "T0"
        assert captured["subtest_id"] == "00-empty"
        assert captured["run_number"] == 1
        assert captured["score"] == pytest.approx(0.85)
        assert captured["grade"] == "A"

    def test_save_run_report_json_called(self, minimal_run_context: RunContext) -> None:
        """save_run_report_json is called once."""
        ctx = minimal_run_context
        ctx.run_result = _make_run_result(ctx)
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()

        with (
            patch("scylla.e2e.run_report.save_run_report"),
            patch("scylla.e2e.run_report.save_run_report_json") as mock_json_report,
        ):
            stage_write_report(ctx)

        mock_json_report.assert_called_once()


# ---------------------------------------------------------------------------
# TestStageCleanupWorktree
# ---------------------------------------------------------------------------


class TestStageCleanupWorktree:
    """Tests for stage_cleanup_worktree()."""

    def test_cleanup_called_for_passed_run(self, minimal_run_context: RunContext) -> None:
        """cleanup_worktree is called when run passed and workspace exists."""
        ctx = minimal_run_context
        run_result = _make_run_result(ctx, passed=True)
        ctx.run_result = run_result
        wm = cast(MagicMock, ctx.workspace_manager)

        stage_cleanup_worktree(ctx)

        wm.cleanup_worktree.assert_called_once_with(ctx.workspace)

    def test_cleanup_not_called_for_failed_run(self, minimal_run_context: RunContext) -> None:
        """cleanup_worktree is NOT called when run failed."""
        ctx = minimal_run_context
        run_result = _make_run_result(ctx, passed=False)
        ctx.run_result = run_result
        wm = cast(MagicMock, ctx.workspace_manager)

        stage_cleanup_worktree(ctx)

        wm.cleanup_worktree.assert_not_called()

    def test_cleanup_not_called_when_workspace_absent(
        self, minimal_run_context: RunContext
    ) -> None:
        """cleanup_worktree is NOT called when workspace does not exist."""
        ctx = minimal_run_context
        run_result = _make_run_result(ctx, passed=True)
        ctx.run_result = run_result
        wm = cast(MagicMock, ctx.workspace_manager)

        # Remove workspace so it does not exist
        ctx.workspace.rmdir()

        stage_cleanup_worktree(ctx)

        wm.cleanup_worktree.assert_not_called()

    def test_cleanup_failure_is_non_fatal(self, minimal_run_context: RunContext) -> None:
        """Exception from cleanup_worktree is caught and does not propagate."""
        ctx = minimal_run_context
        run_result = _make_run_result(ctx, passed=True)
        ctx.run_result = run_result
        wm = cast(MagicMock, ctx.workspace_manager)

        wm.cleanup_worktree.side_effect = OSError("disk full")

        # Must not raise
        stage_cleanup_worktree(ctx)

    def test_falls_back_to_checkpoint_when_run_result_is_none(
        self, minimal_run_context: RunContext
    ) -> None:
        """Falls back to checkpoint.get_run_status when ctx.run_result is None."""
        ctx = minimal_run_context
        ctx.run_result = None  # No run_result set
        wm = cast(MagicMock, ctx.workspace_manager)

        mock_checkpoint = MagicMock()
        mock_checkpoint.get_run_status.return_value = "passed"
        ctx.checkpoint = mock_checkpoint

        stage_cleanup_worktree(ctx)

        wm.cleanup_worktree.assert_called_once_with(ctx.workspace)

    def test_preserves_workspace_when_checkpoint_says_failed(
        self, minimal_run_context: RunContext
    ) -> None:
        """Does not clean up when checkpoint indicates 'failed'."""
        ctx = minimal_run_context
        ctx.run_result = None
        wm = cast(MagicMock, ctx.workspace_manager)

        mock_checkpoint = MagicMock()
        mock_checkpoint.get_run_status.return_value = "failed"
        ctx.checkpoint = mock_checkpoint

        stage_cleanup_worktree(ctx)

        wm.cleanup_worktree.assert_not_called()

    def test_preserves_workspace_when_no_run_result_and_no_checkpoint(
        self, minimal_run_context: RunContext
    ) -> None:
        """Does not clean up when both run_result and checkpoint are None."""
        ctx = minimal_run_context
        ctx.run_result = None
        ctx.checkpoint = None
        wm = cast(MagicMock, ctx.workspace_manager)

        stage_cleanup_worktree(ctx)

        wm.cleanup_worktree.assert_not_called()

    def test_cleanup_uses_correct_workspace_path(self, minimal_run_context: RunContext) -> None:
        """cleanup_worktree is called with ctx.workspace (not run_dir)."""
        ctx = minimal_run_context
        run_result = _make_run_result(ctx, passed=True)
        ctx.run_result = run_result
        wm = cast(MagicMock, ctx.workspace_manager)

        stage_cleanup_worktree(ctx)

        wm.cleanup_worktree.assert_called_once_with(ctx.workspace)
        # Ensure it was not called with run_dir
        call_args = wm.cleanup_worktree.call_args[0]
        assert call_args[0] == ctx.workspace
        assert call_args[0] != ctx.run_dir
