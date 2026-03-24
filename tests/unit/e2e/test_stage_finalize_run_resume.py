"""Unit tests for process metrics resume in scylla/e2e/stages.py.

Tests cover:
- _load_process_metrics_from_run_result: loading progress_steps and change_results
  from a previously-saved run_result.json
- stage_finalize_run resume integration: correct behaviour when ctx fields are None
  and a prior run_result.json is available on disk
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.stages import (
    RunContext,
    _load_process_metrics_from_run_result,
    stage_finalize_run,
)
from scylla.metrics.process import ChangeResult, ProgressStep

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_run_context(tmp_path: Path) -> RunContext:
    """Minimal RunContext for resume tests."""
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
        experiment_id="test-resume",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        language="python",
        models=["claude-sonnet-4-6"],
        runs_per_subtest=1,
        judge_models=["claude-opus-4-6"],
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


def _make_run_result_json(
    run_dir: Path,
    progress_tracking: list[dict[str, Any]] | None = None,
    changes: list[dict[str, Any]] | None = None,
) -> None:
    """Write a minimal run_result.json to run_dir."""
    data: dict[str, Any] = {
        "run_number": 1,
        "judge_score": 0.8,
        "judge_passed": True,
    }
    if progress_tracking is not None:
        data["progress_tracking"] = progress_tracking
    if changes is not None:
        data["changes"] = changes
    (run_dir / "run_result.json").write_text(json.dumps(data))


def _make_adapter_result() -> MagicMock:
    """Build a minimal AdapterResult mock."""
    from scylla.e2e.models import TokenStats

    token_stats_mock = MagicMock()
    token_stats_mock.to_token_stats.return_value = TokenStats(input_tokens=100, output_tokens=50)
    result = MagicMock()
    result.exit_code = 0
    result.token_stats = token_stats_mock
    result.cost_usd = 0.01
    result.stderr = ""
    result.stdout = ""
    return result


def _make_judgment(passed: bool = True, score: float = 0.8) -> dict[str, Any]:
    """Build a minimal judgment dict."""
    return {
        "score": score,
        "passed": passed,
        "grade": "B",
        "reasoning": "Good work",
        "criteria_scores": {},
    }


# ---------------------------------------------------------------------------
# TestLoadProcessMetricsFromRunResult
# ---------------------------------------------------------------------------


class TestLoadProcessMetricsFromRunResult:
    """Tests for _load_process_metrics_from_run_result() helper."""

    def test_returns_none_when_no_file(self, tmp_path: Path) -> None:
        """Returns (None, None) when run_result.json does not exist."""
        steps, changes = _load_process_metrics_from_run_result(tmp_path)
        assert steps is None
        assert changes is None

    def test_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        """Returns (None, None) when file contains invalid JSON."""
        (tmp_path / "run_result.json").write_text("{invalid json}")
        steps, changes = _load_process_metrics_from_run_result(tmp_path)
        assert steps is None
        assert changes is None

    def test_returns_none_on_os_error(self, tmp_path: Path) -> None:
        """Returns (None, None) when file read raises OSError."""
        run_result = tmp_path / "run_result.json"
        run_result.write_text("{}")
        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            steps, changes = _load_process_metrics_from_run_result(tmp_path)
        assert steps is None
        assert changes is None

    def test_returns_none_when_keys_missing(self, tmp_path: Path) -> None:
        """Returns (None, None) when file has no progress_tracking/changes keys."""
        (tmp_path / "run_result.json").write_text(json.dumps({"judge_score": 0.8}))
        steps, changes = _load_process_metrics_from_run_result(tmp_path)
        assert steps is None
        assert changes is None

    def test_loads_progress_steps(self, tmp_path: Path) -> None:
        """Loads progress_tracking into list[ProgressStep]."""
        _make_run_result_json(
            tmp_path,
            progress_tracking=[
                {
                    "step_id": "a.py",
                    "description": "Modified a.py",
                    "weight": 0.6,
                    "completed": True,
                    "goal_alignment": 0.8,
                }
            ],
        )
        steps, _ = _load_process_metrics_from_run_result(tmp_path)
        assert steps is not None
        assert len(steps) == 1
        assert steps[0].step_id == "a.py"
        assert steps[0].weight == pytest.approx(0.6)
        assert steps[0].completed is True
        assert steps[0].goal_alignment == pytest.approx(0.8)

    def test_loads_change_results(self, tmp_path: Path) -> None:
        """Loads changes into list[ChangeResult]."""
        _make_run_result_json(
            tmp_path,
            changes=[
                {
                    "change_id": "b.py",
                    "description": "Modified b.py",
                    "succeeded": True,
                    "caused_failure": False,
                    "reverted": False,
                }
            ],
        )
        _, changes = _load_process_metrics_from_run_result(tmp_path)
        assert changes is not None
        assert len(changes) == 1
        assert changes[0].change_id == "b.py"
        assert changes[0].succeeded is True

    def test_skips_malformed_step_entries(self, tmp_path: Path) -> None:
        """Skips step entries missing required fields; loads valid ones."""
        _make_run_result_json(
            tmp_path,
            progress_tracking=[
                {"description": "no step_id"},  # missing step_id — skipped
                {"step_id": "valid.py", "description": "Valid step"},
            ],
        )
        steps, _ = _load_process_metrics_from_run_result(tmp_path)
        assert steps is not None
        assert len(steps) == 1
        assert steps[0].step_id == "valid.py"

    def test_skips_malformed_change_entries(self, tmp_path: Path) -> None:
        """Skips change entries missing required fields; loads valid ones."""
        _make_run_result_json(
            tmp_path,
            changes=[
                {"description": "no change_id"},  # missing change_id — skipped
                {"change_id": "ok.py", "description": "OK change"},
            ],
        )
        _, changes = _load_process_metrics_from_run_result(tmp_path)
        assert changes is not None
        assert len(changes) == 1
        assert changes[0].change_id == "ok.py"

    def test_loads_both_simultaneously(self, tmp_path: Path) -> None:
        """Returns both lists non-None when both keys are present."""
        _make_run_result_json(
            tmp_path,
            progress_tracking=[{"step_id": "x.py", "description": "x"}],
            changes=[{"change_id": "y.py", "description": "y"}],
        )
        steps, changes = _load_process_metrics_from_run_result(tmp_path)
        assert steps is not None
        assert changes is not None

    def test_empty_arrays_return_empty_lists(self, tmp_path: Path) -> None:
        """Empty arrays in JSON return empty lists (not None)."""
        _make_run_result_json(tmp_path, progress_tracking=[], changes=[])
        steps, changes = _load_process_metrics_from_run_result(tmp_path)
        assert steps == []
        assert changes == []

    def test_uses_defaults_for_optional_step_fields(self, tmp_path: Path) -> None:
        """Optional step fields default correctly when absent."""
        _make_run_result_json(
            tmp_path,
            progress_tracking=[{"step_id": "z.py", "description": "z"}],
        )
        steps, _ = _load_process_metrics_from_run_result(tmp_path)
        assert steps is not None
        assert steps[0].weight == pytest.approx(1.0)
        assert steps[0].completed is False
        assert steps[0].goal_alignment == pytest.approx(1.0)

    def test_uses_defaults_for_optional_change_fields(self, tmp_path: Path) -> None:
        """Optional change fields default correctly when absent."""
        _make_run_result_json(
            tmp_path,
            changes=[{"change_id": "z.py", "description": "z"}],
        )
        _, changes = _load_process_metrics_from_run_result(tmp_path)
        assert changes is not None
        assert changes[0].succeeded is True
        assert changes[0].caused_failure is False
        assert changes[0].reverted is False

    def test_returns_progress_step_instances(self, tmp_path: Path) -> None:
        """Loaded steps are ProgressStep instances."""
        _make_run_result_json(
            tmp_path,
            progress_tracking=[{"step_id": "a.py", "description": "a"}],
        )
        steps, _ = _load_process_metrics_from_run_result(tmp_path)
        assert steps is not None
        assert isinstance(steps[0], ProgressStep)

    def test_returns_change_result_instances(self, tmp_path: Path) -> None:
        """Loaded changes are ChangeResult instances."""
        _make_run_result_json(
            tmp_path,
            changes=[{"change_id": "a.py", "description": "a"}],
        )
        _, changes = _load_process_metrics_from_run_result(tmp_path)
        assert changes is not None
        assert isinstance(changes[0], ChangeResult)


# ---------------------------------------------------------------------------
# TestStageFinalizeRunResumeIntegration
# ---------------------------------------------------------------------------


class TestStageFinalizeRunResumeIntegration:
    """Integration tests: stage_finalize_run reloads metrics from run_result.json on resume."""

    def test_resume_loads_steps_when_none(self, minimal_run_context: RunContext) -> None:
        """When ctx.progress_steps is None and run_result.json exists, data is reloaded."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        # Simulate prior run_result.json with progress data
        _make_run_result_json(
            ctx.run_dir,
            progress_tracking=[
                {
                    "step_id": "prior.py",
                    "description": "Modified prior.py",
                    "weight": 1.0,
                    "completed": True,
                    "goal_alignment": 0.0,
                }
            ],
            changes=[],
        )
        # progress_steps is None (simulate crash before stage_capture_diff)
        assert ctx.progress_steps is None
        assert ctx.change_results is None

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert len(data["progress_tracking"]) == 1
        assert data["progress_tracking"][0]["step_id"] == "prior.py"

    def test_resume_does_not_overwrite_empty_list(self, minimal_run_context: RunContext) -> None:
        """An empty list from stage_capture_diff must NOT be overwritten by file data."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        # Write a file with data — should be ignored because ctx list is already set
        _make_run_result_json(
            ctx.run_dir,
            progress_tracking=[{"step_id": "file.py", "description": "file"}],
            changes=[{"change_id": "file.py", "description": "file"}],
        )
        # Explicitly set to empty lists (agent made no changes this session)
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert data["progress_tracking"] == []
        assert data["changes"] == []

    def test_resume_does_not_overwrite_fresh_steps(self, minimal_run_context: RunContext) -> None:
        """Fresh ctx.progress_steps are preserved even when file has different data."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        _make_run_result_json(
            ctx.run_dir,
            progress_tracking=[{"step_id": "old.py", "description": "old"}],
        )
        ctx.progress_steps = [
            ProgressStep(step_id="fresh.py", description="Fresh step", completed=True)
        ]
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        step_ids = [s["step_id"] for s in data["progress_tracking"]]
        assert "fresh.py" in step_ids
        assert "old.py" not in step_ids

    def test_resume_graceful_when_no_file(self, minimal_run_context: RunContext) -> None:
        """No crash when ctx.progress_steps is None and no run_result.json exists."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        # No prior file, both ctx fields are None
        assert ctx.progress_steps is None
        assert ctx.change_results is None

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert data["progress_tracking"] == []
        assert data["changes"] == []

    def test_resume_process_metrics_non_empty(self, minimal_run_context: RunContext) -> None:
        """r_prog is non-zero when steps are loaded from prior run_result.json."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment(passed=True, score=0.8)
        ctx.agent_ran = True
        ctx.diff_result = {}
        _make_run_result_json(
            ctx.run_dir,
            progress_tracking=[
                {
                    "step_id": "a.py",
                    "description": "Modified a.py",
                    "weight": 1.0,
                    "completed": True,
                    "goal_alignment": 0.0,
                },
                {
                    "step_id": "b.py",
                    "description": "Modified b.py",
                    "weight": 1.0,
                    "completed": True,
                    "goal_alignment": 0.0,
                },
            ],
            changes=[],
        )
        assert ctx.progress_steps is None

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert data["process_metrics"]["r_prog"] > 0.0

    def test_resume_only_change_results_none(self, minimal_run_context: RunContext) -> None:
        """Only ctx.change_results is reloaded when progress_steps is already set."""
        ctx = minimal_run_context
        ctx.agent_result = _make_adapter_result()
        ctx.judgment = _make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        _make_run_result_json(
            ctx.run_dir,
            progress_tracking=[{"step_id": "disk.py", "description": "disk"}],
            changes=[{"change_id": "from_disk.py", "description": "from disk"}],
        )
        # progress_steps is already set; change_results is None
        ctx.progress_steps = [
            ProgressStep(step_id="ctx.py", description="from ctx", completed=True)
        ]
        assert ctx.change_results is None

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        step_ids = [s["step_id"] for s in data["progress_tracking"]]
        change_ids = [c["change_id"] for c in data["changes"]]
        # Fresh progress_steps preserved, change_results loaded from disk
        assert "ctx.py" in step_ids
        assert "disk.py" not in step_ids
        assert "from_disk.py" in change_ids
