"""Unit tests for subtest executor functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from scylla.e2e.llm_judge import _parse_judge_response
from scylla.e2e.models import JudgeResultSummary
from scylla.e2e.subtest_executor import (
    SubTestExecutor,
    _has_valid_judge_result,
    _move_to_failed,
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
        from unittest.mock import MagicMock

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

        assert abs(score - 0.85) < 0.001  # Average of 0.8 and 0.9
        assert passed is True
        assert grade == "A"  # Grade for 0.85 (>= 0.80)

    def test_consensus_with_invalid_judge(self) -> None:
        """Test consensus computation excludes invalid judges."""
        from unittest.mock import MagicMock

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
        assert abs(score - 0.9) < 0.001  # Only valid judge (0.9)
        assert passed is True
        assert grade == "A"  # Grade for 0.9

    def test_consensus_no_judges(self) -> None:
        """Test consensus computation with no judges."""
        from unittest.mock import MagicMock

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
