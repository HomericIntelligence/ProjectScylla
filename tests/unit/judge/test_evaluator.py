"""Tests for judge evaluator."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scylla.judge.evaluator import (
    ConsensusConfig,
    ConsensusJudgment,
    EvaluationParseError,
    EvaluatorConfig,
    EvaluatorError,
    JudgeEvaluator,
    JudgeScore,
    JudgeSummary,
    Judgment,
    assign_letter_grade,
    needs_additional_runs,
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
    """Tests for grade assignment using industry-aligned scale."""

    def test_grade_s(self) -> None:
        """S grade requires perfect score (1.0)."""
        assert assign_letter_grade(1.0) == "S"

    def test_grade_a(self) -> None:
        """A grade: >= 0.80 (Excellent - production ready)."""
        assert assign_letter_grade(0.80) == "A"
        assert assign_letter_grade(0.99) == "A"

    def test_grade_b(self) -> None:
        """B grade: >= 0.60 (Good - minor improvements possible)."""
        assert assign_letter_grade(0.60) == "B"
        assert assign_letter_grade(0.79) == "B"

    def test_grade_c(self) -> None:
        """C grade: >= 0.40 (Acceptable - functional with issues)."""
        assert assign_letter_grade(0.40) == "C"
        assert assign_letter_grade(0.59) == "C"

    def test_grade_d(self) -> None:
        """D grade: >= 0.20 (Marginal - significant issues)."""
        assert assign_letter_grade(0.20) == "D"
        assert assign_letter_grade(0.39) == "D"

    def test_grade_f(self) -> None:
        """F grade: < 0.20 (Failing - does not meet requirements)."""
        assert assign_letter_grade(0.19) == "F"
        assert assign_letter_grade(0.0) == "F"


class TestEvaluatorConfig:
    """Tests for EvaluatorConfig."""

    def test_default_config(self) -> None:
        """Test Default config."""
        config = EvaluatorConfig()
        assert config.model == "claude-opus-4-5-20251101"
        assert config.num_runs == 3
        assert config.timeout == 300
        assert config.pass_threshold == 0.70

    def test_custom_config(self) -> None:
        """Test Custom config."""
        config = EvaluatorConfig(model="test-model", num_runs=5)
        assert config.model == "test-model"
        assert config.num_runs == 5

    def test_invalid_num_runs(self) -> None:
        """Test Invalid num runs."""
        with pytest.raises(ValueError):
            EvaluatorConfig(num_runs=0)


class TestJudgment:
    """Tests for Judgment dataclass."""

    def test_empty_judgment(self) -> None:
        """Test Empty judgment."""
        judgment = Judgment()
        assert judgment.requirements == {}
        assert judgment.categories == {}
        assert judgment.summary is None

    def test_judgment_with_scores(self) -> None:
        """Test Judgment with scores."""
        judgment = Judgment(
            requirements={"R001": JudgeScore(score=0.9, confidence=0.8)},
        )
        assert "R001" in judgment.requirements


class TestJudgeSummary:
    """Tests for JudgeSummary dataclass."""

    def test_summary(self) -> None:
        """Test Summary."""
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
        """Test Empty consensus."""
        consensus = ConsensusJudgment()
        assert consensus.weighted_score == 0.0
        assert consensus.passed is False
        assert consensus.run_count == 3


class TestJudgeEvaluator:
    """Tests for JudgeEvaluator class."""

    def test_init_default_config(self) -> None:
        """Test Init default config."""
        evaluator = JudgeEvaluator()
        assert evaluator.config.num_runs == 3
        assert evaluator.adapter is None

    def test_init_custom_config(self) -> None:
        """Test Init custom config."""
        config = EvaluatorConfig(num_runs=5)
        evaluator = JudgeEvaluator(config=config)
        assert evaluator.config.num_runs == 5


class TestExtractJson:
    """Tests for JSON extraction."""

    def test_extract_json_block(self) -> None:
        """Test Extract json block."""
        evaluator = JudgeEvaluator()
        output = '```json\n{"score": 0.8}\n```'
        result = evaluator._extract_json(output)
        assert result is not None
        assert result["score"] == 0.8

    def test_extract_raw_json(self) -> None:
        """Test Extract raw json."""
        evaluator = JudgeEvaluator()
        output = 'Text {"score": 0.8} more'
        result = evaluator._extract_json(output)
        assert result is not None
        assert result["score"] == 0.8

    def test_extract_nested_json(self) -> None:
        """Test Extract nested json."""
        evaluator = JudgeEvaluator()
        output = '{"outer": {"inner": 123}}'
        result = evaluator._extract_json(output)
        assert result["outer"]["inner"] == 123

    def test_extract_no_json(self) -> None:
        """Test Extract no json."""
        evaluator = JudgeEvaluator()
        result = evaluator._extract_json("Plain text")
        assert result is None


class TestParseJudgment:
    """Tests for judgment parsing."""

    def test_parse_full_judgment(self) -> None:
        """Test Parse full judgment."""
        evaluator = JudgeEvaluator()
        output = """{
            "requirements": {"R001": {"score": 0.9, "confidence": 0.8, "notes": "Met"}},
            "categories": {"code_quality": {"score": 0.85, "confidence": 0.9}},
            "summary": {
                "weighted_score": 0.87, "passed": true, "letter_grade": "B",
                "overall_confidence": 0.85, "strengths": [], "weaknesses": []
            },
            "qualitative_feedback": "Good"
        }"""
        judgment = evaluator._parse_judgment(output)
        assert judgment.requirements["R001"].score == 0.9
        assert judgment.summary.passed is True

    def test_parse_empty_output(self) -> None:
        """Test Parse empty output."""
        evaluator = JudgeEvaluator()
        judgment = evaluator._parse_judgment("")
        assert judgment.requirements == {}


class TestCalculateConsensus:
    """Tests for consensus calculation."""

    def test_consensus_empty(self) -> None:
        """Test Consensus empty."""
        evaluator = JudgeEvaluator()
        consensus = evaluator._calculate_consensus([])
        assert consensus.weighted_score == 0.0

    def test_consensus_single_valid(self) -> None:
        """Test Consensus single valid."""
        evaluator = JudgeEvaluator()
        judgment = Judgment(
            requirements={"R001": JudgeScore(score=0.9, confidence=0.8)},
            summary=JudgeSummary(
                weighted_score=0.87,
                passed=True,
                letter_grade="B",
                overall_confidence=0.85,
            ),
        )
        consensus = evaluator._calculate_consensus([judgment])
        assert consensus.weighted_score == pytest.approx(0.87)

    def test_consensus_multiple_runs(self) -> None:
        """Test Consensus multiple runs."""
        evaluator = JudgeEvaluator()
        judgments = [
            Judgment(
                requirements={"R001": JudgeScore(score=0.8, confidence=0.9)},
                summary=JudgeSummary(
                    weighted_score=0.8, passed=True, letter_grade="B", overall_confidence=0.9
                ),
            ),
            Judgment(
                requirements={"R001": JudgeScore(score=0.9, confidence=0.7)},
                summary=JudgeSummary(
                    weighted_score=0.9, passed=True, letter_grade="A", overall_confidence=0.7
                ),
            ),
        ]
        consensus = evaluator._calculate_consensus(judgments)
        assert consensus.run_count == 2
        assert "R001" in consensus.requirements


class TestRunConsensus:
    """Tests for run with consensus."""

    def test_no_adapter_raises(self) -> None:
        """Test No adapter raises."""
        evaluator = JudgeEvaluator()
        with TemporaryDirectory() as tmpdir:
            with pytest.raises(EvaluatorError, match="No adapter"):
                evaluator._single_evaluation(
                    workspace=Path(tmpdir),
                    prompt="Test",
                    criteria="C",
                    rubric="R",
                )

    def test_runs_correct_number(self) -> None:
        """Test Runs correct number."""
        config = EvaluatorConfig(num_runs=3)
        evaluator = JudgeEvaluator(config=config)
        call_count = 0

        def mock_eval(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return Judgment(
                requirements={"R001": JudgeScore(score=0.8, confidence=0.9)},
                summary=JudgeSummary(
                    weighted_score=0.8, passed=True, letter_grade="B", overall_confidence=0.9
                ),
            )

        evaluator._single_evaluation = mock_eval
        with TemporaryDirectory() as tmpdir:
            evaluator.evaluate_with_consensus(
                workspace=Path(tmpdir),
                prompt="T",
                criteria="C",
                rubric="R",
            )
        assert call_count == 3


class TestErrors:
    """Tests for error classes."""

    def test_evaluator_error(self) -> None:
        """Test Evaluator error."""
        error = EvaluatorError("Test")
        assert str(error) == "Test"

    def test_parse_error(self) -> None:
        """Test Parse error."""
        error = EvaluationParseError("Parse")
        assert isinstance(error, EvaluatorError)


class TestConsensusConfig:
    """Tests for ConsensusConfig."""

    def test_default_config(self) -> None:
        """Test Default config."""
        config = ConsensusConfig()
        assert config.initial_runs == 3
        assert config.max_additional_runs == 5
        assert config.variance_threshold == 0.15
        assert config.min_confidence == 0.6
        assert config.score_range_threshold == 0.3

    def test_custom_config(self) -> None:
        """Test Custom config."""
        config = ConsensusConfig(
            initial_runs=5,
            max_additional_runs=10,
            variance_threshold=0.2,
        )
        assert config.initial_runs == 5
        assert config.max_additional_runs == 10
        assert config.variance_threshold == 0.2


class TestNeedsAdditionalRuns:
    """Tests for needs_additional_runs function."""

    def test_insufficient_runs(self) -> None:
        """Test Insufficient runs."""
        config = ConsensusConfig()
        scores = [JudgeScore(score=0.8, confidence=0.9)]
        needs, reason = needs_additional_runs(scores, config)
        assert needs is False
        assert "insufficient" in reason

    def test_high_variance_triggers_retry(self) -> None:
        """Test High variance triggers retry."""
        config = ConsensusConfig(
            variance_threshold=0.01,  # Low threshold
            score_range_threshold=0.5,  # High enough to not trigger first
        )
        # Variance of [0.5, 0.9, 0.7] = 0.0267, range = 0.4
        scores = [
            JudgeScore(score=0.5, confidence=0.9),
            JudgeScore(score=0.9, confidence=0.9),
            JudgeScore(score=0.7, confidence=0.9),
        ]
        needs, reason = needs_additional_runs(scores, config)
        assert needs is True
        assert "variance" in reason

    def test_low_confidence_triggers_retry(self) -> None:
        """Test Low confidence triggers retry."""
        config = ConsensusConfig(min_confidence=0.8)
        scores = [
            JudgeScore(score=0.8, confidence=0.5),
            JudgeScore(score=0.8, confidence=0.5),
            JudgeScore(score=0.8, confidence=0.5),
        ]
        needs, reason = needs_additional_runs(scores, config)
        assert needs is True
        assert "confidence" in reason

    def test_high_range_triggers_retry(self) -> None:
        """Test High range triggers retry."""
        config = ConsensusConfig(
            variance_threshold=0.5,  # High enough to not trigger
            min_confidence=0.0,  # Low enough to not trigger
            score_range_threshold=0.2,
        )
        scores = [
            JudgeScore(score=0.5, confidence=0.9),
            JudgeScore(score=0.8, confidence=0.9),
        ]
        needs, reason = needs_additional_runs(scores, config)
        assert needs is True
        assert "range" in reason

    def test_consensus_reached(self) -> None:
        """Test Consensus reached."""
        config = ConsensusConfig()
        scores = [
            JudgeScore(score=0.8, confidence=0.9),
            JudgeScore(score=0.82, confidence=0.9),
            JudgeScore(score=0.79, confidence=0.85),
        ]
        needs, reason = needs_additional_runs(scores, config)
        assert needs is False
        assert "consensus" in reason


class TestConsensusJudgmentRetryFields:
    """Tests for new retry-related fields in ConsensusJudgment."""

    def test_default_retry_fields(self) -> None:
        """Test Default retry fields."""
        consensus = ConsensusJudgment()
        assert consensus.initial_runs == 3
        assert consensus.retry_runs == 0
        assert consensus.consensus_reached is True
        assert consensus.consensus_reason == ""

    def test_retry_fields_populated(self) -> None:
        """Test Retry fields populated."""
        consensus = ConsensusJudgment(
            initial_runs=3,
            retry_runs=2,
            consensus_reached=False,
            consensus_reason="max retries reached",
        )
        assert consensus.initial_runs == 3
        assert consensus.retry_runs == 2
        assert consensus.consensus_reached is False
        assert consensus.run_count == 3  # Default, should be 3 + 2 = 5 in practice


class TestEvaluatorWithConsensusConfig:
    """Tests for JudgeEvaluator with consensus configuration."""

    def test_init_with_consensus_config(self) -> None:
        """Test Init with consensus config."""
        config = EvaluatorConfig()
        consensus_config = ConsensusConfig(max_additional_runs=10)
        evaluator = JudgeEvaluator(
            config=config,
            consensus_config=consensus_config,
        )
        assert evaluator.consensus_config.max_additional_runs == 10

    def test_retry_on_high_variance(self) -> None:
        """Test Retry on high variance."""
        consensus_config = ConsensusConfig(
            initial_runs=3,
            max_additional_runs=2,
            variance_threshold=0.01,  # Very low, will trigger retry
        )
        evaluator = JudgeEvaluator(consensus_config=consensus_config)
        call_count = 0

        def fake_single_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Alternating scores to create variance
            score = 0.7 if call_count % 2 == 0 else 0.9
            return Judgment(
                requirements={"R001": JudgeScore(score=score, confidence=0.9)},
                summary=JudgeSummary(
                    weighted_score=score,
                    passed=True,
                    letter_grade="B",
                    overall_confidence=0.9,
                ),
            )

        evaluator._single_evaluation = fake_single_run
        with TemporaryDirectory() as tmpdir:
            consensus = evaluator.evaluate_with_consensus(
                workspace=Path(tmpdir),
                prompt="T",
                criteria="C",
                rubric="R",
            )
        # Should have done initial 3 + 2 retries = 5 calls
        assert call_count == 5
        assert consensus.retry_runs == 2

    def test_no_retry_on_consensus(self) -> None:
        """Test No retry on consensus."""
        consensus_config = ConsensusConfig(
            initial_runs=3,
            max_additional_runs=5,
        )
        evaluator = JudgeEvaluator(consensus_config=consensus_config)
        call_count = 0

        def fake_single_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Consistent scores - no variance
            return Judgment(
                requirements={"R001": JudgeScore(score=0.8, confidence=0.9)},
                summary=JudgeSummary(
                    weighted_score=0.8,
                    passed=True,
                    letter_grade="B",
                    overall_confidence=0.9,
                ),
            )

        evaluator._single_evaluation = fake_single_run
        with TemporaryDirectory() as tmpdir:
            consensus = evaluator.evaluate_with_consensus(
                workspace=Path(tmpdir),
                prompt="T",
                criteria="C",
                rubric="R",
            )
        # Should only do initial 3 runs
        assert call_count == 3
        assert consensus.retry_runs == 0
        assert consensus.consensus_reached is True
