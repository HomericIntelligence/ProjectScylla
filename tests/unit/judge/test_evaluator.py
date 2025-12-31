"""Tests for judge evaluator.

Python justification: Required for pytest testing framework.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scylla.judge.evaluator import (
    ConsensusJudgment,
    EvaluationParseError,
    EvaluatorConfig,
    EvaluatorError,
    ExploratoryResult,
    Judgment,
    JudgeEvaluator,
    JudgeScore,
    JudgeSummary,
    assign_grade,
    weighted_consensus,
)


class TestJudgeScore:
    """Tests for JudgeScore dataclass."""

    def test_create_score(self) -> None:
        """Test creating a score."""
        score = JudgeScore(score=0.8, confidence=0.9, notes="Good")
        assert score.score == 0.8
        assert score.confidence == 0.9
        assert score.notes == "Good"

    def test_default_notes(self) -> None:
        """Test default empty notes."""
        score = JudgeScore(score=0.5, confidence=0.5)
        assert score.notes == ""


class TestWeightedConsensus:
    """Tests for weighted consensus calculation."""

    def test_empty_scores(self) -> None:
        """Test empty scores returns 0."""
        assert weighted_consensus([]) == 0.0

    def test_single_score(self) -> None:
        """Test single score returns that score."""
        scores = [JudgeScore(score=0.8, confidence=0.9)]
        assert weighted_consensus(scores) == pytest.approx(0.8)

    def test_equal_confidence(self) -> None:
        """Test equal confidence gives simple average."""
        scores = [
            JudgeScore(score=0.6, confidence=0.5),
            JudgeScore(score=0.8, confidence=0.5),
            JudgeScore(score=1.0, confidence=0.5),
        ]
        assert weighted_consensus(scores) == pytest.approx(0.8)

    def test_unequal_confidence(self) -> None:
        """Test unequal confidence weights correctly."""
        scores = [
            JudgeScore(score=0.9, confidence=0.9),
            JudgeScore(score=0.5, confidence=0.1),
        ]
        assert weighted_consensus(scores) == pytest.approx(0.86)

    def test_zero_confidence_fallback(self) -> None:
        """Test zero confidence falls back to simple average."""
        scores = [
            JudgeScore(score=0.6, confidence=0.0),
            JudgeScore(score=0.8, confidence=0.0),
        ]
        assert weighted_consensus(scores) == pytest.approx(0.7)


class TestAssignGrade:
    """Tests for grade assignment."""

    def test_grade_a(self) -> None:
        assert assign_grade(0.95) == "A"
        assert assign_grade(1.0) == "A"

    def test_grade_b(self) -> None:
        assert assign_grade(0.85) == "B"
        assert assign_grade(0.94) == "B"

    def test_grade_c(self) -> None:
        assert assign_grade(0.75) == "C"
        assert assign_grade(0.84) == "C"

    def test_grade_d(self) -> None:
        assert assign_grade(0.65) == "D"
        assert assign_grade(0.74) == "D"

    def test_grade_f(self) -> None:
        assert assign_grade(0.64) == "F"
        assert assign_grade(0.0) == "F"


class TestEvaluatorConfig:
    """Tests for EvaluatorConfig."""

    def test_default_config(self) -> None:
        config = EvaluatorConfig()
        assert config.model == "claude-opus-4-5-20251101"
        assert config.num_runs == 3
        assert config.timeout == 300
        assert config.pass_threshold == 0.70

    def test_custom_config(self) -> None:
        config = EvaluatorConfig(model="test-model", num_runs=5)
        assert config.model == "test-model"
        assert config.num_runs == 5

    def test_invalid_num_runs(self) -> None:
        with pytest.raises(ValueError):
            EvaluatorConfig(num_runs=0)


class TestJudgment:
    """Tests for Judgment dataclass."""

    def test_empty_judgment(self) -> None:
        judgment = Judgment()
        assert judgment.requirements == {}
        assert judgment.categories == {}
        assert judgment.summary is None

    def test_judgment_with_scores(self) -> None:
        judgment = Judgment(
            requirements={"R001": JudgeScore(score=0.9, confidence=0.8)},
        )
        assert "R001" in judgment.requirements


class TestJudgeSummary:
    """Tests for JudgeSummary dataclass."""

    def test_summary(self) -> None:
        summary = JudgeSummary(
            weighted_score=0.85,
            passed=True,
            letter_grade="B",
            overall_confidence=0.9,
        )
        assert summary.weighted_score == 0.85
        assert summary.passed is True


class TestConsensusJudgment:
    """Tests for ConsensusJudgment dataclass."""

    def test_empty_consensus(self) -> None:
        consensus = ConsensusJudgment()
        assert consensus.weighted_score == 0.0
        assert consensus.passed is False
        assert consensus.run_count == 3


class TestJudgeEvaluator:
    """Tests for JudgeEvaluator class."""

    def test_init_default_config(self) -> None:
        evaluator = JudgeEvaluator()
        assert evaluator.config.num_runs == 3
        assert evaluator.adapter is None

    def test_init_custom_config(self) -> None:
        config = EvaluatorConfig(num_runs=5)
        evaluator = JudgeEvaluator(config=config)
        assert evaluator.config.num_runs == 5


class TestExtractJson:
    """Tests for JSON extraction."""

    def test_extract_json_block(self) -> None:
        evaluator = JudgeEvaluator()
        output = '```json\n{"score": 0.8}\n```'
        result = evaluator._extract_json(output)
        assert result is not None
        assert result["score"] == 0.8

    def test_extract_raw_json(self) -> None:
        evaluator = JudgeEvaluator()
        output = 'Text {"score": 0.8} more'
        result = evaluator._extract_json(output)
        assert result is not None
        assert result["score"] == 0.8

    def test_extract_nested_json(self) -> None:
        evaluator = JudgeEvaluator()
        output = '{"outer": {"inner": 123}}'
        result = evaluator._extract_json(output)
        assert result["outer"]["inner"] == 123

    def test_extract_no_json(self) -> None:
        evaluator = JudgeEvaluator()
        result = evaluator._extract_json("Plain text")
        assert result is None


class TestParseJudgment:
    """Tests for judgment parsing."""

    def test_parse_full_judgment(self) -> None:
        evaluator = JudgeEvaluator()
        output = '''{
            "requirements": {"R001": {"score": 0.9, "confidence": 0.8, "notes": "Met"}},
            "categories": {"code_quality": {"score": 0.85, "confidence": 0.9}},
            "summary": {
                "weighted_score": 0.87, "passed": true, "letter_grade": "B",
                "overall_confidence": 0.85, "strengths": [], "weaknesses": []
            },
            "qualitative_feedback": "Good"
        }'''
        judgment = evaluator._parse_judgment(output)
        assert judgment.requirements["R001"].score == 0.9
        assert judgment.summary.passed is True

    def test_parse_empty_output(self) -> None:
        evaluator = JudgeEvaluator()
        judgment = evaluator._parse_judgment("")
        assert judgment.requirements == {}


class TestCalculateConsensus:
    """Tests for consensus calculation."""

    def test_consensus_empty(self) -> None:
        evaluator = JudgeEvaluator()
        consensus = evaluator._calculate_consensus([])
        assert consensus.weighted_score == 0.0

    def test_consensus_single_valid(self) -> None:
        evaluator = JudgeEvaluator()
        judgment = Judgment(
            requirements={"R001": JudgeScore(score=0.9, confidence=0.8)},
            summary=JudgeSummary(
                weighted_score=0.87, passed=True, letter_grade="B",
                overall_confidence=0.85,
            ),
        )
        consensus = evaluator._calculate_consensus([judgment])
        assert consensus.weighted_score == pytest.approx(0.87)

    def test_consensus_multiple_runs(self) -> None:
        evaluator = JudgeEvaluator()
        judgments = [
            Judgment(
                requirements={"R001": JudgeScore(score=0.8, confidence=0.9)},
                summary=JudgeSummary(weighted_score=0.8, passed=True,
                    letter_grade="B", overall_confidence=0.9),
            ),
            Judgment(
                requirements={"R001": JudgeScore(score=0.9, confidence=0.7)},
                summary=JudgeSummary(weighted_score=0.9, passed=True,
                    letter_grade="A", overall_confidence=0.7),
            ),
        ]
        consensus = evaluator._calculate_consensus(judgments)
        assert consensus.run_count == 2
        assert "R001" in consensus.requirements


class TestRunConsensus:
    """Tests for run with consensus."""

    def test_no_adapter_raises(self) -> None:
        evaluator = JudgeEvaluator()
        with TemporaryDirectory() as tmpdir:
            with pytest.raises(EvaluatorError, match="No adapter"):
                evaluator._single_evaluation(
                    workspace=Path(tmpdir),
                    prompt="Test", criteria="C", rubric="R",
                )

    def test_runs_correct_number(self) -> None:
        config = EvaluatorConfig(num_runs=3)
        evaluator = JudgeEvaluator(config=config)
        call_count = 0

        def mock_eval(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return Judgment(
                requirements={"R001": JudgeScore(score=0.8, confidence=0.9)},
                summary=JudgeSummary(weighted_score=0.8, passed=True,
                    letter_grade="B", overall_confidence=0.9),
            )

        evaluator._single_evaluation = mock_eval
        with TemporaryDirectory() as tmpdir:
            consensus = evaluator.evaluate_with_consensus(
                workspace=Path(tmpdir), prompt="T", criteria="C", rubric="R",
            )
        assert call_count == 3


class TestErrors:
    """Tests for error classes."""

    def test_evaluator_error(self) -> None:
        error = EvaluatorError("Test")
        assert str(error) == "Test"

    def test_parse_error(self) -> None:
        error = EvaluationParseError("Parse")
        assert isinstance(error, EvaluatorError)
