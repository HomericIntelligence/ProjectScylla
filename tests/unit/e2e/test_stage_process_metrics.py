"""Unit tests for process metrics helpers in scylla/e2e/stage_process_metrics.py.

Tests cover:
- _parse_diff_numstat_output: direct unit tests for the numstat parser
- _get_diff_stat: parsing git diff --numstat output
- _build_change_results: constructing ChangeResult list from diff_stat
- _build_progress_steps: constructing ProgressStep list from workspace_state
- _finalize_change_results: updating ChangeResult with actual judge outcome
- _finalize_progress_steps: updating ProgressStep with actual judge score
- stage_finalize_run integration: process_metrics block written to run_result.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.stage_process_metrics import (
    _build_change_results,
    _build_progress_steps,
    _finalize_change_results,
    _finalize_progress_steps,
    _get_diff_stat,
    _parse_diff_numstat_output,
)
from scylla.e2e.stages import (
    RunContext,
    stage_finalize_run,
)
from scylla.metrics.process import ChangeResult, ProgressStep

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_run_context(tmp_path: Path) -> RunContext:
    """Minimal RunContext for process metrics tests."""
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

    # Create required subdirectories
    (run_dir / "agent").mkdir()
    (run_dir / "judge").mkdir()

    config = ExperimentConfig(
        experiment_id="test-pm",
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


# ---------------------------------------------------------------------------
# TestParseDiffNumstatOutput
# ---------------------------------------------------------------------------


class TestParseDiffNumstatOutput:
    """Direct unit tests for _parse_diff_numstat_output()."""

    def test_empty_string_returns_empty_dict(self) -> None:
        """Empty input returns empty dict."""
        result = _parse_diff_numstat_output("")
        assert result == {}

    def test_parses_single_modified_file(self) -> None:
        """Parses a single modified file correctly."""
        result = _parse_diff_numstat_output("5\t3\tpath/to/file.py\n")
        assert result == {"path/to/file.py": (5, 3)}

    def test_parses_multiple_files(self) -> None:
        """Parses multiple files in one output."""
        output = "7\t3\ta.py\n3\t0\tb.py\n"
        result = _parse_diff_numstat_output(output)
        assert result == {"a.py": (7, 3), "b.py": (3, 0)}

    def test_skips_binary_files_with_dash_counts(self) -> None:
        r"""Binary files (-\t-\t<path>) are skipped."""
        output = "1\t0\ta.py\n-\t-\timage.png\n"
        result = _parse_diff_numstat_output(output)
        assert "a.py" in result
        assert "image.png" not in result

    def test_skips_lines_with_fewer_than_three_parts(self) -> None:
        """Lines that don't have 3 tab-separated parts are skipped."""
        output = "not\ta\tvalid\tline\n5\t2\tgood.py\n"
        result = _parse_diff_numstat_output(output)
        # The extra-column line is skipped, good.py is parsed
        assert "good.py" in result

    def test_skips_lines_with_non_integer_counts(self) -> None:
        """Lines with non-integer insertion/deletion counts are skipped."""
        output = "abc\txyz\tfile.py\n5\t2\tgood.py\n"
        result = _parse_diff_numstat_output(output)
        assert "file.py" not in result
        assert "good.py" in result

    def test_skips_lines_with_empty_filepath(self) -> None:
        """Lines with empty filepath after strip are skipped."""
        output = "5\t2\t\n3\t1\tgood.py\n"
        result = _parse_diff_numstat_output(output)
        assert "" not in result
        assert "good.py" in result

    def test_strips_whitespace_from_filepath(self) -> None:
        """File path trailing whitespace is stripped."""
        output = "3\t0\tpath/to/file.py\n"
        result = _parse_diff_numstat_output(output)
        assert "path/to/file.py" in result

    def test_insertions_only_file(self) -> None:
        """Handles file with only insertions (0 deletions)."""
        result = _parse_diff_numstat_output("20\t0\tnew_file.py\n")
        assert result["new_file.py"] == (20, 0)

    def test_deletions_only_file(self) -> None:
        """Handles file with only deletions (0 insertions)."""
        result = _parse_diff_numstat_output("0\t5\told_file.py\n")
        assert result["old_file.py"] == (0, 5)

    def test_returns_tuple_per_file(self) -> None:
        """Each file maps to a (insertions, deletions) tuple."""
        result = _parse_diff_numstat_output("10\t2\ta.py\n")
        ins, dels = result["a.py"]
        assert ins == 10
        assert dels == 2

    def test_skips_only_ins_dash(self) -> None:
        """Skips line when only insertions field is '-'."""
        output = "-\t5\tfile.py\n"
        result = _parse_diff_numstat_output(output)
        assert result == {}

    def test_skips_only_dels_dash(self) -> None:
        """Skips line when only deletions field is '-'."""
        output = "5\t-\tfile.py\n"
        result = _parse_diff_numstat_output(output)
        assert result == {}

    @pytest.mark.parametrize(
        "numstat_line,expected",
        [
            ("1\t1\tone.py\n", {"one.py": (1, 1)}),
            ("100\t200\ttwo.py\n", {"two.py": (100, 200)}),
            ("0\t0\tempty.py\n", {"empty.py": (0, 0)}),
        ],
    )
    def test_parametrized_valid_lines(
        self, numstat_line: str, expected: dict[str, tuple[int, int]]
    ) -> None:
        """Parametrized: various valid numstat lines are parsed correctly."""
        result = _parse_diff_numstat_output(numstat_line)
        assert result == expected


# ---------------------------------------------------------------------------
# TestGetDiffStat
# ---------------------------------------------------------------------------


class TestGetDiffStat:
    """Tests for _get_diff_stat() helper."""

    def test_returns_empty_on_no_changes(self, tmp_path: Path) -> None:
        """Empty workspace returns empty dict."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = _get_diff_stat(tmp_path)
        assert result == {}

    def test_parses_modified_file(self, tmp_path: Path) -> None:
        """Parses a modified file with exact insertion and deletion counts."""
        numstat_output = "2\t3\tfoo/bar.py\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=numstat_output, stderr="")
            result = _get_diff_stat(tmp_path)
        assert "foo/bar.py" in result
        insertions, deletions = result["foo/bar.py"]
        assert insertions == 2
        assert deletions == 3

    def test_parses_multiple_files(self, tmp_path: Path) -> None:
        """Parses multiple changed files."""
        numstat_output = "7\t3\ta.py\n3\t0\tb.py\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=numstat_output, stderr="")
            result = _get_diff_stat(tmp_path)
        assert "a.py" in result
        assert "b.py" in result

    def test_returns_empty_on_git_error(self, tmp_path: Path) -> None:
        """Returns empty dict when git command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="fatal: not a git repo"
            )
            result = _get_diff_stat(tmp_path)
        assert result == {}

    def test_returns_empty_on_exception(self, tmp_path: Path) -> None:
        """Returns empty dict when subprocess raises an exception."""
        with patch("subprocess.run", side_effect=OSError("not found")):
            result = _get_diff_stat(tmp_path)
        assert result == {}

    def test_returns_empty_on_timeout(self, tmp_path: Path) -> None:
        """Returns empty dict on subprocess timeout."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            result = _get_diff_stat(tmp_path)
        assert result == {}

    def test_insertions_only_file(self, tmp_path: Path) -> None:
        """Handles file with only insertions."""
        numstat_output = "20\t0\tnew_file.py\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=numstat_output, stderr="")
            result = _get_diff_stat(tmp_path)
        assert "new_file.py" in result
        insertions, deletions = result["new_file.py"]
        assert insertions == 20
        assert deletions == 0

    def test_deletions_only_file(self, tmp_path: Path) -> None:
        """Handles file with only deletions."""
        numstat_output = "0\t5\told_file.py\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=numstat_output, stderr="")
            result = _get_diff_stat(tmp_path)
        assert "old_file.py" in result
        insertions, deletions = result["old_file.py"]
        assert insertions == 0
        assert deletions == 5

    def test_skips_binary_files(self, tmp_path: Path) -> None:
        r"""Binary files (shown as '-\t-\t<path>') are skipped."""
        numstat_output = "1\t0\ta.py\n-\t-\timage.png\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=numstat_output, stderr="")
            result = _get_diff_stat(tmp_path)
        assert "a.py" in result
        assert "image.png" not in result

    def test_strips_whitespace_from_paths(self, tmp_path: Path) -> None:
        """File paths are stripped of leading/trailing whitespace."""
        numstat_output = "3\t0\tpath/to/file.py\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=numstat_output, stderr="")
            result = _get_diff_stat(tmp_path)
        assert "path/to/file.py" in result


# ---------------------------------------------------------------------------
# TestBuildChangeResults
# ---------------------------------------------------------------------------


class TestBuildChangeResults:
    """Tests for _build_change_results() helper."""

    def test_returns_empty_for_empty_diff_stat(self) -> None:
        """Empty diff_stat produces empty list."""
        result = _build_change_results({}, judge_passed=True, pipeline_passed=True)
        assert result == []

    def test_one_change_per_file(self) -> None:
        """One ChangeResult per file in diff_stat."""
        diff_stat = {"a.py": (5, 2), "b.py": (10, 0)}
        result = _build_change_results(diff_stat, judge_passed=True, pipeline_passed=True)
        assert len(result) == 2

    def test_change_id_is_file_path(self) -> None:
        """change_id equals the file path."""
        diff_stat = {"foo/bar.py": (3, 1)}
        result = _build_change_results(diff_stat, judge_passed=True, pipeline_passed=True)
        assert result[0].change_id == "foo/bar.py"

    def test_succeeded_equals_judge_passed(self) -> None:
        """Succeeded field matches judge_passed argument."""
        diff_stat = {"a.py": (1, 0)}
        passed = _build_change_results(diff_stat, judge_passed=True, pipeline_passed=True)
        failed = _build_change_results(diff_stat, judge_passed=False, pipeline_passed=True)
        assert passed[0].succeeded is True
        assert failed[0].succeeded is False

    def test_caused_failure_when_pipeline_failed(self) -> None:
        """caused_failure is True when pipeline_passed is False."""
        diff_stat = {"a.py": (1, 0)}
        result = _build_change_results(diff_stat, judge_passed=False, pipeline_passed=False)
        assert result[0].caused_failure is True

    def test_not_caused_failure_when_pipeline_passed(self) -> None:
        """caused_failure is False when pipeline_passed is True."""
        diff_stat = {"a.py": (1, 0)}
        result = _build_change_results(diff_stat, judge_passed=True, pipeline_passed=True)
        assert result[0].caused_failure is False

    def test_reverted_always_false(self) -> None:
        """Reverted is always False at write time."""
        diff_stat = {"a.py": (1, 0)}
        result = _build_change_results(diff_stat, judge_passed=True, pipeline_passed=True)
        assert result[0].reverted is False

    def test_description_contains_filepath(self) -> None:
        """Description contains the file path."""
        diff_stat = {"src/module.py": (2, 1)}
        result = _build_change_results(diff_stat, judge_passed=True, pipeline_passed=True)
        assert "src/module.py" in result[0].description

    def test_returns_list_of_change_result(self) -> None:
        """Returns list of ChangeResult instances."""
        diff_stat = {"a.py": (1, 0)}
        result = _build_change_results(diff_stat, judge_passed=True, pipeline_passed=True)
        assert isinstance(result[0], ChangeResult)


# ---------------------------------------------------------------------------
# TestBuildProgressSteps
# ---------------------------------------------------------------------------


class TestBuildProgressSteps:
    """Tests for _build_progress_steps() helper."""

    def test_returns_empty_for_no_changes(self) -> None:
        """No changes in workspace_state produces empty list."""
        workspace_state = "Files modified/created by agent:\n(no changes detected)"
        result = _build_progress_steps(workspace_state, judge_score=0.8, diff_stat={})
        assert result == []

    def test_one_step_per_modified_file(self) -> None:
        """One ProgressStep per modified file."""
        workspace_state = (
            "Files modified/created by agent:\n- `a.py` (modified)\n- `b.py` (created)"
        )
        diff_stat = {"a.py": (5, 2), "b.py": (10, 0)}
        result = _build_progress_steps(workspace_state, judge_score=0.7, diff_stat=diff_stat)
        assert len(result) == 2

    def test_step_id_is_file_path(self) -> None:
        """step_id equals the file path."""
        workspace_state = "Files modified/created by agent:\n- `foo/bar.py` (modified)"
        diff_stat = {"foo/bar.py": (3, 1)}
        result = _build_progress_steps(workspace_state, judge_score=0.5, diff_stat=diff_stat)
        assert result[0].step_id == "foo/bar.py"

    def test_completed_is_true(self) -> None:
        """All steps are completed=True (agent actually modified them)."""
        workspace_state = "Files modified/created by agent:\n- `a.py` (modified)"
        diff_stat = {"a.py": (1, 0)}
        result = _build_progress_steps(workspace_state, judge_score=0.6, diff_stat=diff_stat)
        assert result[0].completed is True

    def test_goal_alignment_equals_judge_score(self) -> None:
        """goal_alignment equals the judge_score argument."""
        workspace_state = "Files modified/created by agent:\n- `a.py` (modified)"
        diff_stat = {"a.py": (5, 0)}
        result = _build_progress_steps(workspace_state, judge_score=0.9, diff_stat=diff_stat)
        assert result[0].goal_alignment == pytest.approx(0.9)

    def test_weights_sum_to_one_with_multiple_files(self) -> None:
        """Weights are normalized so they sum to 1.0 when multiple files present."""
        workspace_state = (
            "Files modified/created by agent:\n- `a.py` (modified)\n- `b.py` (created)"
        )
        diff_stat = {"a.py": (5, 0), "b.py": (15, 0)}
        result = _build_progress_steps(workspace_state, judge_score=0.8, diff_stat=diff_stat)
        total_weight = sum(s.weight for s in result)
        assert total_weight == pytest.approx(1.0, abs=1e-9)

    def test_equal_weights_for_equal_line_counts(self) -> None:
        """Equal line deltas produce equal weights."""
        workspace_state = (
            "Files modified/created by agent:\n- `a.py` (modified)\n- `b.py` (modified)"
        )
        diff_stat = {"a.py": (5, 0), "b.py": (5, 0)}
        result = _build_progress_steps(workspace_state, judge_score=0.5, diff_stat=diff_stat)
        assert result[0].weight == pytest.approx(result[1].weight)

    def test_default_weight_when_file_not_in_diff_stat(self) -> None:
        """Files not in diff_stat get default weight of 1.0 before normalization."""
        workspace_state = "Files modified/created by agent:\n- `a.py` (modified)"
        result = _build_progress_steps(workspace_state, judge_score=0.5, diff_stat={})
        # Single file with no diff_stat: weight normalized to 1.0
        assert result[0].weight == pytest.approx(1.0)

    def test_description_contains_status_and_path(self) -> None:
        """Description contains both status and file path."""
        workspace_state = "Files modified/created by agent:\n- `src/foo.py` (added)"
        diff_stat = {"src/foo.py": (8, 0)}
        result = _build_progress_steps(workspace_state, judge_score=0.5, diff_stat=diff_stat)
        assert "src/foo.py" in result[0].description

    def test_returns_list_of_progress_step(self) -> None:
        """Returns list of ProgressStep instances."""
        workspace_state = "Files modified/created by agent:\n- `a.py` (modified)"
        diff_stat = {"a.py": (1, 0)}
        result = _build_progress_steps(workspace_state, judge_score=0.5, diff_stat=diff_stat)
        assert isinstance(result[0], ProgressStep)

    def test_handles_empty_workspace_state(self) -> None:
        """Empty workspace_state string returns empty list."""
        result = _build_progress_steps("", judge_score=0.5, diff_stat={})
        assert result == []

    def test_handles_deleted_files(self) -> None:
        """Deleted files are included as steps."""
        workspace_state = "Files modified/created by agent:\n- `old.py` (deleted)"
        diff_stat = {"old.py": (0, 10)}
        result = _build_progress_steps(workspace_state, judge_score=0.5, diff_stat=diff_stat)
        assert len(result) == 1
        assert result[0].step_id == "old.py"

    def test_multiple_files_absent_from_diff_stat_get_equal_weights(self) -> None:
        """Multiple files all absent from diff_stat each get default delta 1, equal weights."""
        workspace_state = (
            "Files modified/created by agent:\n"
            "- `a.py` (modified)\n"
            "- `b.py` (modified)\n"
            "- `c.py` (modified)"
        )
        # No diff_stat entries — all files default to delta 1
        result = _build_progress_steps(workspace_state, judge_score=0.5, diff_stat={})
        assert len(result) == 3
        weights = [s.weight for s in result]
        assert all(w == pytest.approx(weights[0]) for w in weights)
        assert sum(weights) == pytest.approx(1.0)

    def test_heavier_file_gets_larger_weight(self) -> None:
        """File with more line changes receives proportionally larger weight."""
        workspace_state = (
            "Files modified/created by agent:\n- `small.py` (modified)\n- `big.py` (modified)"
        )
        diff_stat = {"small.py": (1, 0), "big.py": (9, 0)}
        result = _build_progress_steps(workspace_state, judge_score=0.8, diff_stat=diff_stat)
        small_weight = next(s.weight for s in result if s.step_id == "small.py")
        big_weight = next(s.weight for s in result if s.step_id == "big.py")
        assert big_weight > small_weight
        assert big_weight == pytest.approx(0.9)
        assert small_weight == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# TestFinalizeHelpers
# ---------------------------------------------------------------------------


class TestFinalizeChangeResults:
    """Tests for _finalize_change_results() helper."""

    def test_returns_empty_for_empty_input(self) -> None:
        """Empty input returns empty list."""
        result = _finalize_change_results([], judge_passed=True, pipeline_passed=True)
        assert result == []

    def test_updates_succeeded_from_judge_passed(self) -> None:
        """Succeeded is updated from judge_passed."""
        original = [ChangeResult(change_id="a.py", description="Modified a.py", succeeded=False)]
        result = _finalize_change_results(original, judge_passed=True, pipeline_passed=True)
        assert result[0].succeeded is True

    def test_updates_caused_failure_from_pipeline_passed(self) -> None:
        """caused_failure is updated from pipeline_passed."""
        original = [
            ChangeResult(change_id="a.py", description="Modified a.py", caused_failure=False)
        ]
        result = _finalize_change_results(original, judge_passed=False, pipeline_passed=False)
        assert result[0].caused_failure is True

    def test_preserves_reverted_false(self) -> None:
        """Reverted remains False."""
        original = [ChangeResult(change_id="a.py", description="Modified a.py")]
        result = _finalize_change_results(original, judge_passed=True, pipeline_passed=True)
        assert result[0].reverted is False

    def test_does_not_mutate_original(self) -> None:
        """Original list is not mutated."""
        original = [ChangeResult(change_id="a.py", description="Modified a.py", succeeded=False)]
        _finalize_change_results(original, judge_passed=True, pipeline_passed=True)
        assert original[0].succeeded is False

    def test_returns_change_result_instances(self) -> None:
        """Returns ChangeResult instances."""
        original = [ChangeResult(change_id="a.py", description="Modified a.py")]
        result = _finalize_change_results(original, judge_passed=True, pipeline_passed=True)
        assert isinstance(result[0], ChangeResult)


class TestFinalizeProgressSteps:
    """Tests for _finalize_progress_steps() helper."""

    def test_returns_empty_for_empty_input(self) -> None:
        """Empty input returns empty list."""
        result = _finalize_progress_steps([], judge_score=0.8)
        assert result == []

    def test_updates_goal_alignment_from_judge_score(self) -> None:
        """goal_alignment is updated from judge_score."""
        original = [ProgressStep(step_id="a.py", description="Modified a.py", goal_alignment=0.0)]
        result = _finalize_progress_steps(original, judge_score=0.75)
        assert result[0].goal_alignment == pytest.approx(0.75)

    def test_completed_remains_true(self) -> None:
        """Completed remains True."""
        original = [ProgressStep(step_id="a.py", description="Modified a.py", completed=True)]
        result = _finalize_progress_steps(original, judge_score=0.5)
        assert result[0].completed is True

    def test_does_not_mutate_original(self) -> None:
        """Original list is not mutated."""
        original = [ProgressStep(step_id="a.py", description="Modified a.py", goal_alignment=0.0)]
        _finalize_progress_steps(original, judge_score=0.9)
        assert original[0].goal_alignment == 0.0

    def test_returns_progress_step_instances(self) -> None:
        """Returns ProgressStep instances."""
        original = [ProgressStep(step_id="a.py", description="Modified a.py")]
        result = _finalize_progress_steps(original, judge_score=0.5)
        assert isinstance(result[0], ProgressStep)

    def test_weight_preserved(self) -> None:
        """Weight field is preserved unchanged."""
        original = [ProgressStep(step_id="a.py", description="Modified a.py", weight=0.6)]
        result = _finalize_progress_steps(original, judge_score=0.5)
        assert result[0].weight == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# TestStageFinalizeRunProcessMetrics
# ---------------------------------------------------------------------------


class TestStageFinalizeRunProcessMetrics:
    """Integration tests: stage_finalize_run writes process_metrics to run_result.json."""

    def _make_adapter_result(self) -> MagicMock:
        """Build a minimal AdapterResult mock."""
        from scylla.e2e.models import TokenStats

        token_stats_mock = MagicMock()
        token_stats_mock.to_token_stats.return_value = TokenStats(
            input_tokens=100, output_tokens=50
        )
        result = MagicMock()
        result.exit_code = 0
        result.token_stats = token_stats_mock
        result.cost_usd = 0.01
        result.stderr = ""
        result.stdout = ""
        return result

    def _make_judgment(self, passed: bool = True, score: float = 0.8) -> dict[str, Any]:
        """Build a minimal judgment dict."""
        return {
            "score": score,
            "passed": passed,
            "grade": "B",
            "reasoning": "Good work",
            "criteria_scores": {},
        }

    def test_process_metrics_written_to_run_result(self, minimal_run_context: RunContext) -> None:
        """stage_finalize_run writes process_metrics block to run_result.json."""
        ctx = minimal_run_context
        ctx.agent_result = self._make_adapter_result()
        ctx.judgment = self._make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {
            "workspace_state": "Files modified/created by agent:\n- `a.py` (modified)",
            "patchfile": "",
            "deleted_files": [],
        }
        ctx.progress_steps = [
            ProgressStep(
                step_id="a.py",
                description="Modified a.py",
                weight=1.0,
                completed=True,
                goal_alignment=0.0,
            )
        ]
        ctx.change_results = [ChangeResult(change_id="a.py", description="Modified a.py")]

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        result_path = ctx.run_dir / "run_result.json"
        assert result_path.exists()
        data = json.loads(result_path.read_text())
        assert "process_metrics" in data
        pm = data["process_metrics"]
        assert "r_prog" in pm
        assert "strategic_drift" in pm
        assert "cfp" in pm
        assert "pr_revert_rate" in pm

    def test_progress_tracking_written_to_run_result(self, minimal_run_context: RunContext) -> None:
        """stage_finalize_run writes progress_tracking block to run_result.json."""
        ctx = minimal_run_context
        ctx.agent_result = self._make_adapter_result()
        ctx.judgment = self._make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        ctx.progress_steps = [
            ProgressStep(
                step_id="b.py",
                description="Modified b.py",
                weight=1.0,
                completed=True,
                goal_alignment=0.0,
            )
        ]
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert "progress_tracking" in data
        assert isinstance(data["progress_tracking"], list)
        assert len(data["progress_tracking"]) == 1
        assert data["progress_tracking"][0]["step_id"] == "b.py"

    def test_changes_written_to_run_result(self, minimal_run_context: RunContext) -> None:
        """stage_finalize_run writes changes block to run_result.json."""
        ctx = minimal_run_context
        ctx.agent_result = self._make_adapter_result()
        ctx.judgment = self._make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        ctx.progress_steps = []
        ctx.change_results = [ChangeResult(change_id="c.py", description="Modified c.py")]

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert "changes" in data
        assert isinstance(data["changes"], list)
        assert len(data["changes"]) == 1
        assert data["changes"][0]["change_id"] == "c.py"

    def test_empty_process_metrics_when_no_changes(self, minimal_run_context: RunContext) -> None:
        """No changes produces zero process_metrics values."""
        ctx = minimal_run_context
        ctx.agent_result = self._make_adapter_result()
        ctx.judgment = self._make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        pm = data["process_metrics"]
        assert pm["r_prog"] == 0.0
        assert pm["cfp"] == 0.0
        assert pm["pr_revert_rate"] == 0.0

    def test_process_metrics_none_ctx_fields_handled_gracefully(
        self, minimal_run_context: RunContext
    ) -> None:
        """None progress_steps and change_results are handled as empty lists."""
        ctx = minimal_run_context
        ctx.agent_result = self._make_adapter_result()
        ctx.judgment = self._make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        # Leave progress_steps and change_results as None (default)
        assert ctx.progress_steps is None
        assert ctx.change_results is None

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert "process_metrics" in data
        assert "progress_tracking" in data
        assert "changes" in data

    def test_judge_score_propagated_to_goal_alignment(
        self, minimal_run_context: RunContext
    ) -> None:
        """goal_alignment in progress_tracking reflects judge_score."""
        ctx = minimal_run_context
        ctx.agent_result = self._make_adapter_result()
        ctx.judgment = self._make_judgment(passed=True, score=0.9)
        ctx.agent_ran = True
        ctx.diff_result = {}
        ctx.progress_steps = [
            ProgressStep(
                step_id="x.py",
                description="Modified x.py",
                weight=1.0,
                completed=True,
                goal_alignment=0.0,
            )
        ]
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        # goal_alignment should be updated to judge score (0.9)
        assert data["progress_tracking"][0]["goal_alignment"] == pytest.approx(0.9)

    def test_judge_passed_propagated_to_changes_succeeded(
        self, minimal_run_context: RunContext
    ) -> None:
        """Succeeded in changes reflects judge_passed."""
        ctx = minimal_run_context
        ctx.agent_result = self._make_adapter_result()
        ctx.judgment = self._make_judgment(passed=True, score=0.8)
        ctx.agent_ran = True
        ctx.diff_result = {}
        ctx.progress_steps = []
        ctx.change_results = [
            ChangeResult(change_id="y.py", description="Modified y.py", succeeded=False)
        ]

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        assert data["changes"][0]["succeeded"] is True

    def test_existing_run_result_fields_preserved(self, minimal_run_context: RunContext) -> None:
        """Existing run_result.json fields (judge_score, etc.) still present."""
        ctx = minimal_run_context
        ctx.agent_result = self._make_adapter_result()
        ctx.judgment = self._make_judgment()
        ctx.agent_ran = True
        ctx.diff_result = {}
        ctx.progress_steps = []
        ctx.change_results = []

        with patch("scylla.e2e.rate_limit.detect_rate_limit", return_value=None):
            stage_finalize_run(ctx)

        data = json.loads((ctx.run_dir / "run_result.json").read_text())
        # Core E2ERunResult fields must still be present
        assert "judge_score" in data
        assert "judge_passed" in data
        assert "run_number" in data
        assert "cost_usd" in data
