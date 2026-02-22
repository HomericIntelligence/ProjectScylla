"""Judge evaluator for running evaluations with consensus.

This module provides the JudgeEvaluator class that runs evaluations
with consensus-based scoring and retry logic for disagreement.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from scylla.config.constants import DEFAULT_JUDGE_MODEL
from scylla.judge.utils import extract_json_from_llm_response
from scylla.metrics.grading import assign_letter_grade

logger = logging.getLogger(__name__)


class AdapterProtocol(Protocol):
    """Protocol for adapter interface."""

    def run(
        self,
        config: Any,
        tier_config: Any | None = None,
    ) -> Any:
        """Run the adapter with config."""
        ...


@dataclass
class JudgeScore:
    """A single judge score with confidence.

    Attributes:
        score: The score (0.0 to 1.0).
        confidence: Confidence in the score (0.0 to 1.0).
        notes: Brief notes explaining the score.

    """

    score: float
    confidence: float
    notes: str = ""


@dataclass
class Judgment:
    """Result from a single judge evaluation run.

    Attributes:
        requirements: Scores for each requirement by ID.
        categories: Scores for each category.
        summary: Summary scores and metadata.
        exploratory_testing: Results from exploratory testing.
        qualitative_feedback: Free-form feedback.
        raw_output: Raw JSON output from the judge.

    """

    requirements: dict[str, JudgeScore] = field(default_factory=dict)
    categories: dict[str, JudgeScore] = field(default_factory=dict)
    summary: JudgeSummary | None = None
    exploratory_testing: ExploratoryResult | None = None
    qualitative_feedback: str = ""
    raw_output: str = ""


@dataclass
class JudgeSummary:
    """Summary from a judgment.

    Attributes:
        weighted_score: The weighted score (0.0 to 1.0).
        passed: Whether the evaluation passed.
        letter_grade: Letter grade (A/B/C/D/F).
        overall_confidence: Overall confidence in the judgment.
        strengths: List of identified strengths.
        weaknesses: List of identified weaknesses.

    """

    weighted_score: float
    passed: bool
    letter_grade: str
    overall_confidence: float
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


@dataclass
class ExploratoryResult:
    """Results from exploratory testing phase.

    Attributes:
        commands_run: Commands executed during testing.
        observations: Observations made.
        failures: Failures encountered.

    """

    commands_run: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


@dataclass
class ConsensusJudgment:
    """Consensus judgment from multiple runs.

    Attributes:
        requirements: Consensus scores for each requirement.
        categories: Consensus scores for each category.
        weighted_score: Overall consensus weighted score.
        passed: Whether the evaluation passed.
        letter_grade: Consensus letter grade.
        overall_confidence: Overall confidence from consensus.
        individual_runs: Individual judgment runs.
        run_count: Total number of runs performed.
        initial_runs: Number of initial runs before retry.
        retry_runs: Number of additional retry runs.
        consensus_reached: Whether consensus was reached.
        consensus_reason: Reason for final consensus state.

    """

    requirements: dict[str, float] = field(default_factory=dict)
    categories: dict[str, float] = field(default_factory=dict)
    weighted_score: float = 0.0
    passed: bool = False
    letter_grade: str = "F"
    overall_confidence: float = 0.0
    individual_runs: list[Judgment] = field(default_factory=list)
    run_count: int = 3
    initial_runs: int = 3
    retry_runs: int = 0
    consensus_reached: bool = True
    consensus_reason: str = ""


class EvaluatorConfig(BaseModel):
    """Configuration for the judge evaluator.

    Attributes:
        model: The model to use for judging.
        num_runs: Number of runs for consensus (default 3).
        timeout: Timeout for each run in seconds.
        pass_threshold: Score threshold for passing.

    """

    model: str = Field(default=DEFAULT_JUDGE_MODEL)
    num_runs: int = Field(default=3, ge=1)
    timeout: int = Field(default=300, ge=30)
    pass_threshold: float = Field(default=0.70, ge=0.0, le=1.0)


class ConsensusConfig(BaseModel):
    """Configuration for consensus retry logic.

    Attributes:
        initial_runs: Number of initial judge runs (default 3).
        max_additional_runs: Maximum additional runs on disagreement.
        variance_threshold: Score variance threshold to trigger retry.
        min_confidence: Minimum average confidence to avoid retry.
        score_range_threshold: Maximum allowed score range before retry.

    """

    initial_runs: int = Field(default=3, ge=1)
    max_additional_runs: int = Field(default=5, ge=0)
    variance_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    score_range_threshold: float = Field(default=0.3, ge=0.0, le=1.0)


def needs_additional_runs(
    scores: list[JudgeScore],
    config: ConsensusConfig,
) -> tuple[bool, str]:
    """Determine if additional judge runs are needed.

    Args:
        scores: List of judge scores from runs so far.
        config: Consensus configuration.

    Returns:
        Tuple of (needs_retry, reason).

    """
    if len(scores) < 2:
        return False, "insufficient runs"

    values = [s.score for s in scores]
    confidences = [s.confidence for s in scores]

    # Check variance
    variance = statistics.variance(values)
    if variance > config.variance_threshold:
        return True, f"high variance ({variance:.3f} > {config.variance_threshold})"

    # Check average confidence
    avg_confidence = statistics.mean(confidences)
    if avg_confidence < config.min_confidence:
        return True, f"low confidence ({avg_confidence:.2f} < {config.min_confidence})"

    # Check score range
    score_range = max(values) - min(values)
    if score_range > config.score_range_threshold:
        return True, f"high range ({score_range:.2f} > {config.score_range_threshold})"

    return False, "consensus reached"


class EvaluatorError(Exception):
    """Base exception for evaluator errors."""

    pass


class EvaluationParseError(EvaluatorError):
    """Raised when parsing evaluation output fails."""

    pass


def weighted_consensus(scores: list[JudgeScore]) -> float:
    """Calculate confidence-weighted average of scores.

    Args:
        scores: List of JudgeScore objects.

    Returns:
        Weighted average score (0.0 to 1.0).

    """
    if not scores:
        return 0.0

    total_confidence = sum(s.confidence for s in scores)
    if total_confidence == 0:
        # Fall back to simple average if no confidence
        return sum(s.score for s in scores) / len(scores)

    return sum(s.score * s.confidence for s in scores) / total_confidence


class JudgeEvaluator:
    """Evaluator that runs judge evaluations with consensus and retry logic.

    Runs initial evaluations and performs additional runs when judges
    significantly disagree, up to a configurable maximum.

    Attributes:
        config: Evaluator configuration.
        consensus_config: Consensus retry configuration.
        adapter: The adapter to use for running evaluations.

    """

    def __init__(
        self,
        config: EvaluatorConfig | None = None,
        consensus_config: ConsensusConfig | None = None,
        adapter: AdapterProtocol | None = None,
    ) -> None:
        """Initialize the evaluator.

        Args:
            config: Evaluator configuration.
            consensus_config: Consensus retry configuration.
            adapter: Optional adapter for running evaluations.

        """
        self.config = config or EvaluatorConfig()
        self.consensus_config = consensus_config or ConsensusConfig()
        self.adapter = adapter

    def evaluate_with_consensus(
        self,
        workspace: Path,
        prompt: str,
        criteria: str,
        rubric: str,
        tier_id: str | None = None,
    ) -> ConsensusJudgment:
        """Run judge evaluations with consensus and retry on disagreement.

        First runs initial_runs evaluations, then checks for disagreement.
        If disagreement is detected, runs additional evaluations up to
        max_additional_runs until consensus is reached.

        Args:
            workspace: Path to the workspace to evaluate.
            prompt: The evaluation prompt.
            criteria: Success criteria.
            rubric: The scoring rubric.
            tier_id: Optional tier identifier.

        Returns:
            ConsensusJudgment with weighted consensus scores and retry info.

        Raises:
            EvaluatorError: If evaluation fails.

        """
        judgments: list[Judgment] = []
        initial_runs = self.consensus_config.initial_runs
        retry_runs = 0

        # Run initial evaluations
        for run_num in range(initial_runs):
            logger.info(f"Running initial judge evaluation {run_num + 1}/{initial_runs}")
            try:
                judgment = self._single_evaluation(
                    workspace=workspace,
                    prompt=prompt,
                    criteria=criteria,
                    rubric=rubric,
                    tier_id=tier_id,
                )
                judgments.append(judgment)
            except Exception as e:
                logger.warning(f"Evaluation run {run_num + 1} failed: {e}")
                # Add empty judgment for failed run
                judgments.append(Judgment())

        # Check for disagreement and retry if needed
        scores = self._extract_overall_scores(judgments)
        needs_retry, reason = needs_additional_runs(scores, self.consensus_config)

        while needs_retry and retry_runs < self.consensus_config.max_additional_runs:
            retry_runs += 1
            logger.info(
                f"Running additional judge evaluation {retry_runs}/"
                f"{self.consensus_config.max_additional_runs} (reason: {reason})"
            )
            try:
                judgment = self._single_evaluation(
                    workspace=workspace,
                    prompt=prompt,
                    criteria=criteria,
                    rubric=rubric,
                    tier_id=tier_id,
                )
                judgments.append(judgment)
            except Exception as e:
                logger.warning(f"Retry run {retry_runs} failed: {e}")
                judgments.append(Judgment())

            # Re-check for consensus
            scores = self._extract_overall_scores(judgments)
            needs_retry, reason = needs_additional_runs(scores, self.consensus_config)

        # Calculate final consensus with retry information
        consensus = self._calculate_consensus(judgments)
        consensus.initial_runs = initial_runs
        consensus.retry_runs = retry_runs
        consensus.consensus_reached = not needs_retry
        consensus.consensus_reason = reason

        return consensus

    def _extract_overall_scores(
        self,
        judgments: list[Judgment],
    ) -> list[JudgeScore]:
        """Extract overall scores from judgments for disagreement checking.

        Args:
            judgments: List of judgment runs.

        Returns:
            List of JudgeScore objects for overall scores.

        """
        scores = []
        for j in judgments:
            if j.summary:
                scores.append(
                    JudgeScore(
                        score=j.summary.weighted_score,
                        confidence=j.summary.overall_confidence,
                    )
                )
        return scores

    def _single_evaluation(
        self,
        workspace: Path,
        prompt: str,
        criteria: str,
        rubric: str,
        tier_id: str | None = None,
    ) -> Judgment:
        """Run a single judge evaluation.

        Args:
            workspace: Path to the workspace to evaluate.
            prompt: The evaluation prompt.
            criteria: Success criteria.
            rubric: The scoring rubric.
            tier_id: Optional tier identifier.

        Returns:
            Judgment from this evaluation run.

        Raises:
            EvaluatorError: If evaluation fails.

        """
        if self.adapter is None:
            raise EvaluatorError("No adapter configured for evaluation")

        # Build the full evaluation prompt
        from scylla.judge.prompts import build_judge_prompt

        full_prompt = build_judge_prompt(
            task_prompt=prompt,
            criteria=criteria,
            rubric=rubric,
            tier_id=tier_id,
        )

        # Create adapter config for this run
        from scylla.adapters.base import AdapterConfig

        adapter_config = AdapterConfig(
            model=self.config.model,
            prompt_file=workspace / "eval_prompt.md",
            workspace=workspace,
            output_dir=workspace / "eval_output",
            timeout=self.config.timeout,
        )

        # Write prompt to file
        adapter_config.output_dir.mkdir(parents=True, exist_ok=True)
        adapter_config.prompt_file.write_text(full_prompt)

        # Run evaluation
        result = self.adapter.run(adapter_config)

        # Parse the output
        return self._parse_judgment(result.stdout)

    def _parse_judgment(self, output: str) -> Judgment:
        """Parse judgment from evaluator output.

        Args:
            output: Raw output from the judge.

        Returns:
            Parsed Judgment object.

        Raises:
            EvaluationParseError: If parsing fails.

        """
        # Extract JSON from the output
        json_data = self._extract_json(output)

        if json_data is None:
            logger.warning("No valid JSON found in judge output")
            return Judgment(raw_output=output)

        return self._judgment_from_dict(json_data, output)

    def _extract_json(self, output: str) -> dict[str, Any] | None:
        """Extract JSON object from output text.

        Args:
            output: Raw output text.

        Returns:
            Parsed JSON dict, or None if not found.

        """
        return extract_json_from_llm_response(output)

    def _judgment_from_dict(
        self,
        data: dict[str, Any],
        raw_output: str,
    ) -> Judgment:
        """Create Judgment from parsed dict.

        Args:
            data: Parsed JSON data.
            raw_output: Raw output string.

        Returns:
            Judgment object.

        """
        judgment = Judgment(raw_output=raw_output)

        # Parse requirements
        requirements = data.get("requirements", {})
        for req_id, req_data in requirements.items():
            if isinstance(req_data, dict):
                judgment.requirements[req_id] = JudgeScore(
                    score=float(req_data.get("score") or 0.0),
                    confidence=float(req_data.get("confidence") or 0.5),
                    notes=str(req_data.get("notes") or ""),
                )

        # Parse categories
        categories = data.get("categories", {})
        for cat_name, cat_data in categories.items():
            if isinstance(cat_data, dict):
                judgment.categories[cat_name] = JudgeScore(
                    score=float(cat_data.get("score") or 0.0),
                    confidence=float(cat_data.get("confidence") or 0.5),
                    notes=str(cat_data.get("notes") or ""),
                )

        # Parse summary
        summary = data.get("summary", {})
        if summary:
            judgment.summary = JudgeSummary(
                weighted_score=float(summary.get("weighted_score") or 0.0),
                passed=bool(summary.get("passed") or False),
                letter_grade=str(summary.get("letter_grade") or "F"),
                overall_confidence=float(summary.get("overall_confidence") or 0.5),
                strengths=list(summary.get("strengths") or []),
                weaknesses=list(summary.get("weaknesses") or []),
            )

        # Parse exploratory testing
        exploratory = data.get("exploratory_testing", {})
        if exploratory:
            judgment.exploratory_testing = ExploratoryResult(
                commands_run=list(exploratory.get("commands_run", [])),
                observations=list(exploratory.get("observations", [])),
                failures=list(exploratory.get("failures", [])),
            )

        # Parse qualitative feedback
        judgment.qualitative_feedback = str(data.get("qualitative_feedback", ""))

        return judgment

    def _calculate_consensus(
        self,
        judgments: list[Judgment],
    ) -> ConsensusJudgment:
        """Calculate confidence-weighted consensus across runs.

        Args:
            judgments: List of individual judgments.

        Returns:
            ConsensusJudgment with weighted scores.

        """
        # Guard: No judgments
        if not judgments:
            return ConsensusJudgment()

        # Filter out empty judgments
        valid_judgments = [j for j in judgments if j.requirements or j.categories]

        # Guard: No valid judgments
        if not valid_judgments:
            return ConsensusJudgment(
                individual_runs=judgments,
                run_count=len(judgments),
            )

        # Calculate requirement consensus
        requirement_consensus: dict[str, float] = {}
        all_req_ids = set()
        for j in valid_judgments:
            all_req_ids.update(j.requirements.keys())

        for req_id in all_req_ids:
            scores = [j.requirements[req_id] for j in valid_judgments if req_id in j.requirements]
            if scores:
                requirement_consensus[req_id] = weighted_consensus(scores)

        # Calculate category consensus
        category_consensus: dict[str, float] = {}
        all_categories = set()
        for j in valid_judgments:
            all_categories.update(j.categories.keys())

        for cat in all_categories:
            scores = [j.categories[cat] for j in valid_judgments if cat in j.categories]
            if scores:
                category_consensus[cat] = weighted_consensus(scores)

        # Calculate overall consensus
        overall_scores = []
        for j in valid_judgments:
            if j.summary:
                overall_scores.append(
                    JudgeScore(
                        score=j.summary.weighted_score,
                        confidence=j.summary.overall_confidence,
                    )
                )

        # Determine weighted score
        weighted_score = self._calculate_weighted_score(overall_scores, category_consensus)

        # Determine pass/fail based on consensus score
        passed = weighted_score >= self.config.pass_threshold
        letter_grade = assign_letter_grade(weighted_score)

        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(overall_scores)

        return ConsensusJudgment(
            requirements=requirement_consensus,
            categories=category_consensus,
            weighted_score=weighted_score,
            passed=passed,
            letter_grade=letter_grade,
            overall_confidence=overall_confidence,
            individual_runs=judgments,
            run_count=len(judgments),
        )

    def _calculate_weighted_score(
        self,
        overall_scores: list[JudgeScore],
        category_consensus: dict[str, float],
    ) -> float:
        """Calculate weighted score from overall scores or category consensus.

        Args:
            overall_scores: List of overall scores.
            category_consensus: Category consensus scores.

        Returns:
            Weighted score (0.0 to 1.0).

        """
        if overall_scores:
            return weighted_consensus(overall_scores)

        # Fall back to average of category scores
        if category_consensus:
            return sum(category_consensus.values()) / len(category_consensus)

        return 0.0

    def _calculate_overall_confidence(
        self,
        overall_scores: list[JudgeScore],
    ) -> float:
        """Calculate overall confidence from scores.

        Args:
            overall_scores: List of overall scores.

        Returns:
            Overall confidence (0.0 to 1.0).

        """
        if overall_scores:
            return sum(s.confidence for s in overall_scores) / len(overall_scores)

        return 0.5
