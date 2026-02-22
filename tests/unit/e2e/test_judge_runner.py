"""Tests for scylla/e2e/judge_runner.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.judge_runner import (
    _compute_judge_consensus,
    _has_valid_judge_result,
    _load_judge_result,
    _run_judge,
    _save_judge_result,
)
from scylla.e2e.models import JudgeResultSummary
from scylla.e2e.paths import JUDGE_DIR, RESULT_FILE


def _make_judge_result(
    score: float = 0.8,
    passed: bool = True,
    grade: str = "B",
    reasoning: str = "Good work",
    is_valid: bool = True,
    criteria_scores: dict | None = None,
) -> MagicMock:
    """Create a mock JudgeResult."""
    result = MagicMock()
    result.score = score
    result.passed = passed
    result.grade = grade
    result.reasoning = reasoning
    result.is_valid = is_valid
    result.criteria_scores = criteria_scores or {}
    return result


def _make_summary(
    model: str = "claude-haiku-4-5",
    score: float | None = 0.8,
    passed: bool | None = True,
    grade: str | None = "B",
    is_valid: bool = True,
    judge_number: int = 1,
) -> JudgeResultSummary:
    """Create a JudgeResultSummary for testing."""
    return JudgeResultSummary(
        model=model,
        score=score,
        passed=passed,
        grade=grade,
        reasoning="test reasoning",
        judge_number=judge_number,
        is_valid=is_valid,
    )


def _write_judge_result(judge_dir: Path, data: dict) -> None:
    """Write result.json to judge_dir."""
    judge_dir.mkdir(parents=True, exist_ok=True)
    (judge_dir / RESULT_FILE).write_text(json.dumps(data))


class TestSaveJudgeResult:
    """Tests for _save_judge_result()."""

    def test_writes_result_json(self, tmp_path: Path) -> None:
        """Result is written to judge_dir/result.json."""
        judge_dir = tmp_path / JUDGE_DIR
        judge_dir.mkdir()
        mock_result = _make_judge_result()

        _save_judge_result(judge_dir, mock_result)

        assert (judge_dir / RESULT_FILE).exists()

    def test_result_json_contains_required_fields(self, tmp_path: Path) -> None:
        """Saved JSON contains score, passed, grade, reasoning, is_valid."""
        judge_dir = tmp_path / JUDGE_DIR
        judge_dir.mkdir()
        mock_result = _make_judge_result(score=0.9, passed=True, grade="A")

        _save_judge_result(judge_dir, mock_result)

        data = json.loads((judge_dir / RESULT_FILE).read_text())
        assert data["score"] == 0.9
        assert data["passed"] is True
        assert data["grade"] == "A"
        assert "reasoning" in data
        assert "is_valid" in data

    def test_failed_result_saved(self, tmp_path: Path) -> None:
        """Failed result (is_valid=False, score=0.0) is written correctly."""
        judge_dir = tmp_path / JUDGE_DIR
        judge_dir.mkdir()
        mock_result = _make_judge_result(score=0.0, passed=False, grade="F", is_valid=False)

        _save_judge_result(judge_dir, mock_result)

        data = json.loads((judge_dir / RESULT_FILE).read_text())
        assert data["score"] == 0.0
        assert data["passed"] is False
        assert data["is_valid"] is False


class TestLoadJudgeResult:
    """Tests for _load_judge_result()."""

    def test_loads_dict_from_json(self, tmp_path: Path) -> None:
        """Result dict is loaded from judge_dir/result.json."""
        judge_dir = tmp_path / JUDGE_DIR
        data = {"score": 0.75, "passed": True, "grade": "B", "is_valid": True, "reasoning": "ok"}
        _write_judge_result(judge_dir, data)

        result = _load_judge_result(judge_dir)

        assert result["score"] == 0.75
        assert result["passed"] is True
        assert result["grade"] == "B"

    def test_loads_all_fields(self, tmp_path: Path) -> None:
        """All saved fields are available after loading."""
        judge_dir = tmp_path / JUDGE_DIR
        data = {
            "score": 0.5,
            "passed": False,
            "grade": "C",
            "reasoning": "Partial completion",
            "is_valid": True,
            "criteria_scores": {"R001": {"score": 0.5, "explanation": "partial"}},
        }
        _write_judge_result(judge_dir, data)

        result = _load_judge_result(judge_dir)

        assert result["reasoning"] == "Partial completion"
        assert result["criteria_scores"]["R001"]["score"] == 0.5


class TestHasValidJudgeResult:
    """Tests for _has_valid_judge_result()."""

    def _make_judge_dir(self, run_dir: Path) -> Path:
        """Create and return the judge directory."""
        judge_dir = run_dir / JUDGE_DIR
        judge_dir.mkdir(parents=True)
        return judge_dir

    def test_returns_false_when_no_result_file(self, tmp_path: Path) -> None:
        """False when result.json does not exist."""
        self._make_judge_dir(tmp_path)
        assert _has_valid_judge_result(tmp_path) is False

    def test_returns_true_for_valid_result(self, tmp_path: Path) -> None:
        """True for a valid judge result with all required fields."""
        judge_dir = self._make_judge_dir(tmp_path)
        _write_judge_result(
            judge_dir,
            {"score": 0.8, "passed": True, "grade": "B", "is_valid": True},
        )
        assert _has_valid_judge_result(tmp_path) is True

    def test_returns_false_for_malformed_json(self, tmp_path: Path) -> None:
        """False when result.json contains malformed JSON."""
        judge_dir = self._make_judge_dir(tmp_path)
        (judge_dir / RESULT_FILE).write_text("invalid json {{{")
        assert _has_valid_judge_result(tmp_path) is False

    def test_returns_false_when_is_valid_false(self, tmp_path: Path) -> None:
        """False when is_valid is explicitly False."""
        judge_dir = self._make_judge_dir(tmp_path)
        _write_judge_result(
            judge_dir,
            {"score": 0.0, "passed": False, "grade": "F", "is_valid": False},
        )
        assert _has_valid_judge_result(tmp_path) is False

    @pytest.mark.parametrize("missing_field", ["score", "passed", "grade"])
    def test_returns_false_when_required_field_missing(
        self, tmp_path: Path, missing_field: str
    ) -> None:
        """False when any required field (score, passed, grade) is absent."""
        judge_dir = self._make_judge_dir(tmp_path)
        data = {"score": 0.8, "passed": True, "grade": "B"}
        del data[missing_field]
        _write_judge_result(judge_dir, data)
        assert _has_valid_judge_result(tmp_path) is False

    def test_returns_true_when_is_valid_absent(self, tmp_path: Path) -> None:
        """True when is_valid field is absent (defaults to valid)."""
        judge_dir = self._make_judge_dir(tmp_path)
        _write_judge_result(
            judge_dir,
            {"score": 0.7, "passed": True, "grade": "B"},
        )
        assert _has_valid_judge_result(tmp_path) is True


class TestComputeJudgeConsensus:
    """Tests for _compute_judge_consensus()."""

    def test_empty_list_returns_none_tuple(self) -> None:
        """Empty judges list returns (None, None, None)."""
        result = _compute_judge_consensus([])
        assert result == (None, None, None)

    def test_all_invalid_returns_none_tuple(self) -> None:
        """All-invalid judges return (None, None, None)."""
        judges = [
            _make_summary(is_valid=False, score=0.0),
            _make_summary(is_valid=False, score=0.0),
        ]
        result = _compute_judge_consensus(judges)
        assert result == (None, None, None)

    def test_single_valid_judge_score_used(self) -> None:
        """Single valid judge's score becomes the consensus."""
        judges = [_make_summary(score=0.8, passed=True)]
        score, passed, _grade = _compute_judge_consensus(judges)
        assert score == pytest.approx(0.8)
        assert passed is True

    def test_average_score_from_multiple_judges(self) -> None:
        """Consensus score is the average of valid judge scores."""
        judges = [
            _make_summary(score=0.6, passed=False, judge_number=1),
            _make_summary(score=1.0, passed=True, judge_number=2),
        ]
        score, _passed, _grade = _compute_judge_consensus(judges)
        assert score == pytest.approx(0.8)

    def test_majority_vote_for_passed_true(self) -> None:
        """Majority vote determines passed=True."""
        judges = [
            _make_summary(score=0.9, passed=True, judge_number=1),
            _make_summary(score=0.8, passed=True, judge_number=2),
            _make_summary(score=0.4, passed=False, judge_number=3),
        ]
        _, passed, _ = _compute_judge_consensus(judges)
        assert passed is True

    def test_majority_vote_for_passed_false(self) -> None:
        """Majority vote determines passed=False."""
        judges = [
            _make_summary(score=0.3, passed=False, judge_number=1),
            _make_summary(score=0.4, passed=False, judge_number=2),
            _make_summary(score=0.9, passed=True, judge_number=3),
        ]
        _, passed, _ = _compute_judge_consensus(judges)
        assert passed is False

    def test_invalid_judges_excluded_from_consensus(self) -> None:
        """Invalid judges are excluded from score calculation."""
        judges = [
            _make_summary(score=0.0, passed=False, is_valid=False, judge_number=1),
            _make_summary(score=1.0, passed=True, is_valid=True, judge_number=2),
        ]
        score, passed, _ = _compute_judge_consensus(judges)
        assert score == pytest.approx(1.0)
        assert passed is True

    def test_grade_is_returned(self) -> None:
        """A letter grade is returned alongside score and passed."""
        judges = [_make_summary(score=1.0, passed=True)]
        _score, _passed, grade = _compute_judge_consensus(judges)
        assert grade is not None
        assert isinstance(grade, str)

    def test_judges_with_none_score_excluded(self) -> None:
        """Judges with score=None are excluded from consensus."""
        judges = [
            _make_summary(score=None, passed=None, judge_number=1),
            _make_summary(score=0.6, passed=False, judge_number=2),
        ]
        score, _, _ = _compute_judge_consensus(judges)
        assert score == pytest.approx(0.6)


class TestRunJudge:
    """Tests for _run_judge()."""

    def test_raises_when_no_judge_models(self, tmp_path: Path) -> None:
        """ValueError raised when judge_models is None or empty."""
        with pytest.raises(ValueError, match="judge_models is required"):
            _run_judge(
                workspace=tmp_path,
                task_prompt="task",
                stdout="output",
                judge_dir=tmp_path / "judge",
                judge_models=None,
            )

        with pytest.raises(ValueError, match="judge_models is required"):
            _run_judge(
                workspace=tmp_path,
                task_prompt="task",
                stdout="output",
                judge_dir=tmp_path / "judge",
                judge_models=[],
            )

    def test_single_judge_success(self, tmp_path: Path) -> None:
        """Single judge success returns consensus dict and judge list."""
        mock_judge_result = _make_judge_result(score=0.9, passed=True, grade="A")
        judge_dir = tmp_path / "judge"

        with patch("scylla.e2e.judge_runner.run_llm_judge", return_value=mock_judge_result):
            consensus, judges = _run_judge(
                workspace=tmp_path,
                task_prompt="task",
                stdout="output",
                judge_dir=judge_dir,
                judge_models=["claude-haiku-4-5"],
            )

        assert len(judges) == 1
        assert judges[0].score == 0.9
        assert consensus["score"] == pytest.approx(0.9)
        assert consensus["passed"] is True

    def test_judge_failure_records_zero_score(self, tmp_path: Path) -> None:
        """Individual judge failure creates zero-score failed result instead of crashing."""
        judge_dir = tmp_path / "judge"
        judge_dir.mkdir()

        with patch(
            "scylla.e2e.judge_runner.run_llm_judge",
            side_effect=Exception("judge error"),
        ):
            _consensus, judges = _run_judge(
                workspace=tmp_path,
                task_prompt="task",
                stdout="output",
                judge_dir=judge_dir,
                judge_models=["claude-haiku-4-5"],
            )

        assert len(judges) == 1
        assert judges[0].is_valid is False
        assert judges[0].score == 0.0
        assert judges[0].passed is False

    def test_all_judges_failed_returns_zero_score_consensus(self, tmp_path: Path) -> None:
        """When all judges fail, returns zero-score consensus dict."""
        judge_dir = tmp_path / "judge"
        judge_dir.mkdir()

        with patch(
            "scylla.e2e.judge_runner.run_llm_judge",
            side_effect=Exception("judge error"),
        ):
            consensus, judges = _run_judge(
                workspace=tmp_path,
                task_prompt="task",
                stdout="output",
                judge_dir=judge_dir,
                judge_models=["claude-haiku-4-5", "claude-sonnet-4-5"],
            )

        assert consensus["score"] == 0.0
        assert consensus["passed"] is False
        assert consensus["is_valid"] is False
        assert len(judges) == 2

    def test_multiple_judges_consensus(self, tmp_path: Path) -> None:
        """Multiple judges produce an averaged consensus score."""
        results = [
            _make_judge_result(score=0.6, passed=False, grade="C"),
            _make_judge_result(score=1.0, passed=True, grade="S"),
        ]
        judge_dir = tmp_path / "judge"

        with patch("scylla.e2e.judge_runner.run_llm_judge", side_effect=results):
            consensus, judges = _run_judge(
                workspace=tmp_path,
                task_prompt="task",
                stdout="output",
                judge_dir=judge_dir,
                judge_models=["model-a", "model-b"],
            )

        assert len(judges) == 2
        assert consensus["score"] == pytest.approx(0.8)

    def test_rate_limit_error_propagates(self, tmp_path: Path) -> None:
        """RateLimitError from judge propagates immediately (not caught)."""
        from scylla.e2e.rate_limit import RateLimitError, RateLimitInfo

        judge_dir = tmp_path / "judge"
        judge_dir.mkdir()
        info = RateLimitInfo(
            source="judge",
            retry_after_seconds=60,
            error_message="rate limited",
            detected_at="2026-01-01T00:00:00Z",
        )

        with patch(
            "scylla.e2e.judge_runner.run_llm_judge",
            side_effect=RateLimitError(info),
        ):
            with pytest.raises(RateLimitError):
                _run_judge(
                    workspace=tmp_path,
                    task_prompt="task",
                    stdout="output",
                    judge_dir=judge_dir,
                    judge_models=["claude-haiku-4-5"],
                )
