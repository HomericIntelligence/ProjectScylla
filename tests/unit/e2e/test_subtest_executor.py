"""Unit tests for subtest executor functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scylla.e2e.llm_judge import _parse_judge_response
from scylla.e2e.models import (
    E2ERunResult,
    ExperimentConfig,
    JudgeResultSummary,
    TierConfig,
    TierID,
    TokenStats,
)
from scylla.e2e.subtest_executor import (
    SubTestExecutor,
    _has_valid_judge_result,
    _move_to_failed,
    aggregate_run_results,
)


def _make_run_result(
    run_number: int = 1,
    judge_score: float = 0.8,
    judge_passed: bool = True,
    judge_grade: str = "B",
    cost_usd: float = 0.10,
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> E2ERunResult:
    """Build a minimal E2ERunResult for testing aggregate_run_results."""
    return E2ERunResult(
        run_number=run_number,
        exit_code=0,
        token_stats=TokenStats(input_tokens=input_tokens, output_tokens=output_tokens),
        agent_duration_seconds=10.0,
        judge_duration_seconds=5.0,
        judge_score=judge_score,
        judge_passed=judge_passed,
        judge_grade=judge_grade,
        judge_reasoning="Test reasoning",
        workspace_path=Path("/tmp/workspace"),
        logs_path=Path("/tmp/logs"),
        cost_usd=cost_usd,
        duration_seconds=15.0,
    )


class TestMoveToFailed:
    """Tests for _move_to_failed function."""

    def test_move_creates_failed_dir(self, tmp_path: Path) -> None:
        """Test that .failed/ directory is created."""
        run_dir = tmp_path / "subtest" / "run_01"
        run_dir.mkdir(parents=True)
        (run_dir / "output.txt").write_text("test output")

        new_path = _move_to_failed(run_dir)

        assert (tmp_path / "subtest" / ".failed").exists()
        assert new_path.name == "run_01_attempt_01"
        assert not run_dir.exists()
        assert (new_path / "output.txt").exists()

    def test_move_increments_attempt(self, tmp_path: Path) -> None:
        """Test that attempt number increments."""
        subtest_dir = tmp_path / "subtest"
        failed_dir = subtest_dir / ".failed"
        failed_dir.mkdir(parents=True)
        (failed_dir / "run_01_attempt_01").mkdir()

        run_dir = subtest_dir / "run_01"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir)

        assert new_path.name == "run_01_attempt_02"

    def test_move_preserves_contents(self, tmp_path: Path) -> None:
        """Test that all contents are preserved during move."""
        run_dir = tmp_path / "subtest" / "run_03"
        run_dir.mkdir(parents=True)
        (run_dir / "output.txt").write_text("agent output")
        (run_dir / "stderr.log").write_text("error log")
        (run_dir / "run_result.json").write_text('{"exit_code": -1}')

        new_path = _move_to_failed(run_dir)

        assert (new_path / "output.txt").read_text() == "agent output"
        assert (new_path / "stderr.log").read_text() == "error log"
        assert (new_path / "run_result.json").read_text() == '{"exit_code": -1}'

    def test_move_with_custom_attempt(self, tmp_path: Path) -> None:
        """Test move with custom attempt number."""
        run_dir = tmp_path / "subtest" / "run_01"
        run_dir.mkdir(parents=True)

        new_path = _move_to_failed(run_dir, attempt=5)

        assert new_path.name == "run_01_attempt_05"

    def test_move_multiple_increments(self, tmp_path: Path) -> None:
        """Test that multiple attempts increment correctly."""
        subtest_dir = tmp_path / "subtest"
        failed_dir = subtest_dir / ".failed"
        failed_dir.mkdir(parents=True)

        # Create attempts 01-03
        (failed_dir / "run_01_attempt_01").mkdir()
        (failed_dir / "run_01_attempt_02").mkdir()
        (failed_dir / "run_01_attempt_03").mkdir()

        run_dir = subtest_dir / "run_01"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir)

        assert new_path.name == "run_01_attempt_04"


class TestComputeJudgeConsensus:
    """Tests for _compute_judge_consensus method."""

    def test_consensus_all_valid_judges(self) -> None:
        """Test consensus computation with all valid judges."""
        from scylla.e2e.models import ExperimentConfig, TierID

        config = ExperimentConfig(
            experiment_id="test-consensus",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        # Create executor with mocked dependencies
        executor = SubTestExecutor(config, MagicMock(), MagicMock())

        judges = [
            JudgeResultSummary(
                model="claude-sonnet-4-5",
                score=0.8,
                passed=True,
                grade="B",
                reasoning="Good work",
                judge_number=1,
                is_valid=True,
            ),
            JudgeResultSummary(
                model="claude-opus-4-6",
                score=0.9,
                passed=True,
                grade="A",
                reasoning="Excellent",
                judge_number=2,
                is_valid=True,
            ),
        ]

        score, passed, grade = executor._compute_judge_consensus(judges)

        assert score is not None
        assert abs(score - 0.85) < 0.001  # Average of 0.8 and 0.9
        assert passed is True
        assert grade == "A"  # Grade for 0.85 (>= 0.80)

    def test_consensus_with_invalid_judge(self) -> None:
        """Test consensus computation excludes invalid judges."""
        from scylla.e2e.models import ExperimentConfig, TierID

        config = ExperimentConfig(
            experiment_id="test-consensus",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        executor = SubTestExecutor(config, MagicMock(), MagicMock())

        judges = [
            JudgeResultSummary(
                model="claude-sonnet-4-5",
                score=0.9,
                passed=True,
                grade="A",
                reasoning="Valid judgment",
                judge_number=1,
                is_valid=True,
            ),
            JudgeResultSummary(
                model="claude-haiku-4-5",
                score=0.0,
                passed=False,
                grade="F",
                reasoning="Invalid judgment",
                judge_number=2,
                is_valid=False,
            ),
        ]

        score, passed, grade = executor._compute_judge_consensus(judges)

        # Invalid judge is excluded from consensus
        assert score is not None
        assert abs(score - 0.9) < 0.001  # Only valid judge (0.9)
        assert passed is True
        assert grade == "A"  # Grade for 0.9

    def test_consensus_no_judges(self) -> None:
        """Test consensus computation with no judges."""
        from scylla.e2e.models import ExperimentConfig, TierID

        config = ExperimentConfig(
            experiment_id="test-consensus",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        executor = SubTestExecutor(config, MagicMock(), MagicMock())

        score, passed, grade = executor._compute_judge_consensus([])

        assert score is None
        assert passed is None
        assert grade is None


class TestParseJudgeResponse:
    """Tests for _parse_judge_response function."""

    def test_parse_judge_response_raises_on_invalid_json(self) -> None:
        """Test _parse_judge_response raises ValueError on non-JSON response."""
        invalid_responses = [
            "This is not JSON at all",
            "The agent passed the test successfully",
            "{ incomplete json",
            '{"score": 0.8, invalid}',
        ]

        for response in invalid_responses:
            with pytest.raises(ValueError, match="Judge response does not contain valid JSON"):
                _parse_judge_response(response)

    def test_parse_judge_response_raises_on_missing_score(self) -> None:
        """Test _parse_judge_response raises ValueError when JSON has no score field."""
        # Valid JSON but missing the required 'score' field
        invalid_responses = [
            '{"status": "ok"}',
            '{"passed": true, "reasoning": "Good work"}',
            '{"grade": "A", "reasoning": "Excellent"}',
        ]

        for response in invalid_responses:
            with pytest.raises(ValueError, match="Judge response missing required 'score' field"):
                _parse_judge_response(response)

    def test_parse_judge_response_handles_xml_wrapped_json(self) -> None:
        """Test _parse_judge_response handles XML-wrapped JSON with preamble text."""
        response = """Here is the evaluation result:
<json_evaluation>
{"score": 0.8, "passed": true, "reasoning": "Good work"}
</json_evaluation>
"""
        result = _parse_judge_response(response)
        assert result.score == 0.8
        assert result.passed is True
        assert result.reasoning == "Good work"
        assert result.grade == "A"

    def test_parse_judge_response_handles_preamble_text(self) -> None:
        """Test _parse_judge_response handles JSON with preamble text."""
        response = (
            'Here is my evaluation: {"score": 0.95, "passed": true, "reasoning": "Excellent work"}'
        )
        result = _parse_judge_response(response)
        assert result.score == 0.95
        assert result.passed is True
        assert result.reasoning == "Excellent work"
        assert result.grade == "A"

    def test_parse_judge_response_handles_markdown_code_block(self) -> None:
        """Test _parse_judge_response handles JSON in markdown code blocks."""
        response = '```json\n{"score": 0.7, "passed": true, "reasoning": "Good"}\n```'
        result = _parse_judge_response(response)
        assert result.score == 0.7
        assert result.passed is True
        assert result.reasoning == "Good"
        assert result.grade == "B"


class TestCheckpointResumeWithNullCriteriaScores:
    """Tests for checkpoint resume when criteria_scores is null in stored data."""

    def _make_report_data(self, criteria_scores_value: object) -> dict:
        """Build a minimal report_data dict with the given criteria_scores value."""
        from scylla.e2e.models import TokenStats

        token_stats = TokenStats(input_tokens=100, output_tokens=50)
        return {
            "run_number": 1,
            "exit_code": 0,
            "token_stats": token_stats.to_dict(),
            "cost_usd": 0.05,
            "duration_seconds": 10.0,
            "agent_duration_seconds": 8.0,
            "judge_duration_seconds": 2.0,
            "judge_score": 0.8,
            "judge_passed": True,
            "judge_grade": "B",
            "judge_reasoning": "Good",
            "workspace_path": "/workspace",
            "logs_path": "/logs",
            "criteria_scores": criteria_scores_value,
        }

    def test_criteria_scores_null_in_report_data(self) -> None:
        """Test that criteria_scores=null in checkpoint data does not raise ValidationError."""
        from scylla.e2e.models import E2ERunResult, TokenStats

        report_data = self._make_report_data(None)

        # This is the exact pattern from subtest_executor.py line 360
        result = E2ERunResult(
            run_number=report_data["run_number"],
            exit_code=report_data["exit_code"],
            token_stats=TokenStats.from_dict(report_data["token_stats"]),
            cost_usd=report_data["cost_usd"],
            duration_seconds=report_data["duration_seconds"],
            agent_duration_seconds=report_data["agent_duration_seconds"],
            judge_duration_seconds=report_data["judge_duration_seconds"],
            judge_score=report_data["judge_score"],
            judge_passed=report_data["judge_passed"],
            judge_grade=report_data["judge_grade"],
            judge_reasoning=report_data["judge_reasoning"],
            workspace_path=Path(report_data["workspace_path"]),
            logs_path=Path(report_data["logs_path"]),
            criteria_scores=report_data.get("criteria_scores") or {},
        )

        assert result.criteria_scores == {}

    def test_criteria_scores_missing_key_in_report_data(self) -> None:
        """Test that missing criteria_scores key in checkpoint data defaults to {}."""
        from scylla.e2e.models import E2ERunResult, TokenStats

        report_data = self._make_report_data(None)
        del report_data["criteria_scores"]  # Simulate missing key

        result = E2ERunResult(
            run_number=report_data["run_number"],
            exit_code=report_data["exit_code"],
            token_stats=TokenStats.from_dict(report_data["token_stats"]),
            cost_usd=report_data["cost_usd"],
            duration_seconds=report_data["duration_seconds"],
            agent_duration_seconds=report_data["agent_duration_seconds"],
            judge_duration_seconds=report_data["judge_duration_seconds"],
            judge_score=report_data["judge_score"],
            judge_passed=report_data["judge_passed"],
            judge_grade=report_data["judge_grade"],
            judge_reasoning=report_data["judge_reasoning"],
            workspace_path=Path(report_data["workspace_path"]),
            logs_path=Path(report_data["logs_path"]),
            criteria_scores=report_data.get("criteria_scores") or {},
        )

        assert result.criteria_scores == {}


class TestHasValidJudgeResult:
    """Tests for _has_valid_judge_result function."""

    def test_has_valid_judge_result_rejects_invalid(self, tmp_path: Path) -> None:
        """Test that _has_valid_judge_result returns False for is_valid=False."""
        run_dir = tmp_path / "run_01"
        judge_dir = run_dir / "judge"
        judge_dir.mkdir(parents=True)
        result_file = judge_dir / "result.json"
        result_file.write_text('{"score": 0.8, "passed": true, "grade": "B", "is_valid": false}')

        assert not _has_valid_judge_result(run_dir)

    def test_has_valid_judge_result_accepts_valid(self, tmp_path: Path) -> None:
        """Test that _has_valid_judge_result returns True for valid judgment."""
        run_dir = tmp_path / "run_01"
        judge_dir = run_dir / "judge"
        judge_dir.mkdir(parents=True)
        result_file = judge_dir / "result.json"
        result_file.write_text('{"score": 0.9, "passed": true, "grade": "A", "is_valid": true}')

        assert _has_valid_judge_result(run_dir)

    def test_has_valid_judge_result_accepts_valid_no_is_valid_field(self, tmp_path: Path) -> None:
        """Test _has_valid_judge_result returns True when is_valid is missing (defaults to True)."""
        run_dir = tmp_path / "run_01"
        judge_dir = run_dir / "judge"
        judge_dir.mkdir(parents=True)
        result_file = judge_dir / "result.json"
        result_file.write_text('{"score": 0.9, "passed": true, "grade": "A"}')

        assert _has_valid_judge_result(run_dir)


class TestPipelineBaselineUsesExperimentConfigLanguage:
    """Regression tests for the TierConfig.language AttributeError bug.

    stage_capture_baseline in stages.py must use ctx.config.language
    (ExperimentConfig) when calling _run_build_pipeline. TierConfig does not
    have a language field, so accessing tier_config.language raises
    AttributeError at runtime.

    These tests inspect the actual source code and model structure - no mocking.
    """

    def test_tier_config_has_no_language_attribute(self) -> None:
        """TierConfig must not have a language field.

        This confirms the bug precondition: if tier_config.language were ever
        accessed, it would raise AttributeError.
        """
        tier_config = TierConfig(tier_id=TierID.T0, subtests=[])
        assert not hasattr(tier_config, "language"), (
            "TierConfig now has a language field. Update stages.py to "
            "use tier_config.language if intentional, then remove this assertion."
        )

    def test_experiment_config_has_language_attribute(self) -> None:
        """ExperimentConfig has a language field - the correct source."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="mojo",
            tiers_to_run=[TierID.T0],
        )
        assert config.language == "mojo"

    def test_stage_capture_baseline_uses_ctx_config_language(self) -> None:
        """stages.py stage_capture_baseline must use ctx.config.language, not tier_config.language.

        Inspects the source of stage_capture_baseline to verify the correct
        attribute path is used when calling _run_build_pipeline.
        """
        import ast
        import inspect
        import textwrap

        from scylla.e2e.stages import stage_capture_baseline

        source = textwrap.dedent(inspect.getsource(stage_capture_baseline))
        tree = ast.parse(source)

        bad_pattern_found = False
        correct_pattern_found = False

        for node in ast.walk(tree):
            # Look for keyword argument: language=<something>
            if not isinstance(node, ast.keyword):
                continue
            if node.arg != "language":
                continue
            value = node.value
            # Check for tier_config.language (the bug)
            if (
                isinstance(value, ast.Attribute)
                and value.attr == "language"
                and isinstance(value.value, ast.Name)
                and value.value.id == "tier_config"
            ):
                bad_pattern_found = True
            # Check for ctx.config.language (the correct pattern in stages.py)
            if (
                isinstance(value, ast.Attribute)
                and value.attr == "language"
                and isinstance(value.value, ast.Attribute)
                and value.value.attr == "config"
                and isinstance(value.value.value, ast.Name)
                and value.value.value.id == "ctx"
            ):
                correct_pattern_found = True

        assert not bad_pattern_found, (
            "stages.stage_capture_baseline uses tier_config.language - "
            "this causes AttributeError since TierConfig has no language field. "
            "Use ctx.config.language instead."
        )
        assert correct_pattern_found, (
            "stages.stage_capture_baseline does not use ctx.config.language "
            "when calling _run_build_pipeline."
        )


# ---------------------------------------------------------------------------
# aggregate_run_results tests (Phase 5C)
# ---------------------------------------------------------------------------


class TestAggregateRunResults:
    """Tests for the module-level aggregate_run_results() function.

    This function is shared between SubTestExecutor and regenerate.py to
    eliminate code duplication (Phase 3E DRY cleanup).
    """

    def test_empty_runs_returns_zero_pass_rate(self) -> None:
        """Empty run list returns a SubTestResult with zero-value stats."""
        result = aggregate_run_results(TierID.T0, "00-empty", [])

        assert result.pass_rate == 0.0
        assert result.runs == []
        assert result.subtest_id == "00-empty"
        assert result.tier_id == TierID.T0

    def test_single_passing_run(self) -> None:
        """Single passing run yields pass_rate=1.0."""
        runs = [_make_run_result(judge_passed=True, judge_score=0.9)]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert result.pass_rate == 1.0
        assert abs(result.mean_score - 0.9) < 0.001

    def test_single_failing_run(self) -> None:
        """Single failing run yields pass_rate=0.0."""
        runs = [_make_run_result(judge_passed=False, judge_score=0.3)]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert result.pass_rate == 0.0
        assert abs(result.mean_score - 0.3) < 0.001

    def test_mixed_runs_pass_rate(self) -> None:
        """3 passing out of 5 runs yields pass_rate=0.6."""
        runs = [
            _make_run_result(run_number=1, judge_passed=True, judge_score=0.9),
            _make_run_result(run_number=2, judge_passed=True, judge_score=0.8),
            _make_run_result(run_number=3, judge_passed=True, judge_score=0.7),
            _make_run_result(run_number=4, judge_passed=False, judge_score=0.4),
            _make_run_result(run_number=5, judge_passed=False, judge_score=0.3),
        ]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert abs(result.pass_rate - 0.6) < 0.001

    def test_mean_score_calculation(self) -> None:
        """mean_score is the arithmetic mean of all judge scores."""
        runs = [
            _make_run_result(run_number=1, judge_score=0.6),
            _make_run_result(run_number=2, judge_score=0.8),
            _make_run_result(run_number=3, judge_score=1.0),
        ]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert abs(result.mean_score - 0.8) < 0.001

    def test_total_cost_aggregation(self) -> None:
        """total_cost is the sum of all run costs."""
        runs = [
            _make_run_result(run_number=1, cost_usd=0.10),
            _make_run_result(run_number=2, cost_usd=0.20),
            _make_run_result(run_number=3, cost_usd=0.15),
        ]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert abs(result.total_cost - 0.45) < 0.001

    def test_token_stats_aggregation(self) -> None:
        """token_stats are summed across all runs."""
        runs = [
            _make_run_result(run_number=1, input_tokens=1000, output_tokens=500),
            _make_run_result(run_number=2, input_tokens=2000, output_tokens=800),
        ]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert result.token_stats is not None
        assert result.token_stats.input_tokens == 3000
        assert result.token_stats.output_tokens == 1300

    def test_grade_distribution(self) -> None:
        """grade_distribution counts each grade letter."""
        runs = [
            _make_run_result(run_number=1, judge_grade="A"),
            _make_run_result(run_number=2, judge_grade="A"),
            _make_run_result(run_number=3, judge_grade="B"),
        ]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert result.grade_distribution is not None
        assert result.grade_distribution["A"] == 2
        assert result.grade_distribution["B"] == 1

    def test_min_max_grade(self) -> None:
        """min_grade and max_grade reflect worst/best grades across runs."""
        runs = [
            _make_run_result(run_number=1, judge_grade="S"),
            _make_run_result(run_number=2, judge_grade="B"),
            _make_run_result(run_number=3, judge_grade="D"),
        ]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert result.min_grade == "D"  # Worst
        assert result.max_grade == "S"  # Best

    def test_consistency_perfect_scores(self) -> None:
        """Identical scores yield consistency=1.0 (zero std dev)."""
        runs = [_make_run_result(run_number=i, judge_score=0.8) for i in range(1, 5)]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert abs(result.consistency - 1.0) < 0.001

    def test_consistency_variable_scores(self) -> None:
        """Variable scores yield consistency < 1.0."""
        runs = [
            _make_run_result(run_number=1, judge_score=0.1),
            _make_run_result(run_number=2, judge_score=0.9),
        ]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert result.consistency < 1.0

    def test_runs_list_preserved(self) -> None:
        """The runs field contains all input run results."""
        runs = [_make_run_result(run_number=i) for i in range(1, 4)]
        result = aggregate_run_results(TierID.T0, "00-empty", runs)

        assert len(result.runs) == 3

    def test_subtest_id_and_tier_id_set(self) -> None:
        """subtest_id and tier_id are set correctly from parameters."""
        runs = [_make_run_result(run_number=1)]
        result = aggregate_run_results(TierID.T1, "my-subtest", runs)

        assert result.subtest_id == "my-subtest"
        assert result.tier_id == TierID.T1

    def test_exported_from_subtest_executor(self) -> None:
        """aggregate_run_results is in __all__ of subtest_executor."""
        import scylla.e2e.subtest_executor as module

        assert "aggregate_run_results" in module.__all__
