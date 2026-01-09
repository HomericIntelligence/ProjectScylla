"""LLM-based judge selection for E2E testing.

This module implements the judge selection algorithm that determines
the best-performing sub-test within a tier, including tie-breaking
with an alternate LLM.

Python Justification: Required for LLM API calls and statistical analysis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scylla.e2e.models import SubTestResult


@dataclass
class JudgeVote:
    """A judge's vote for a sub-test.

    Attributes:
        subtest_id: The sub-test being voted for
        score: The score assigned (0.0 - 1.0)
        confidence: Confidence in the vote (0.0 - 1.0)
        reasoning: Explanation for the vote

    """

    subtest_id: str
    score: float
    confidence: float
    reasoning: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "subtest_id": self.subtest_id,
            "score": self.score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class JudgeSelection:
    """Result of the judge selection process.

    Attributes:
        winning_subtest: ID of the winning sub-test
        winning_score: Score of the winning sub-test
        votes: List of votes from all judges
        margin: Score difference between winner and runner-up
        tiebreaker_needed: Whether a tie-breaker was used
        tiebreaker_result: Result from tie-breaker (if used)

    """

    winning_subtest: str
    winning_score: float
    votes: list[JudgeVote]
    margin: float
    tiebreaker_needed: bool = False
    tiebreaker_result: JudgeVote | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "winning_subtest": self.winning_subtest,
            "winning_score": self.winning_score,
            "votes": [v.to_dict() for v in self.votes],
            "margin": self.margin,
            "tiebreaker_needed": self.tiebreaker_needed,
            "tiebreaker_result": self.tiebreaker_result.to_dict()
            if self.tiebreaker_result
            else None,
        }


def select_best_subtest(
    subtest_results: dict[str, SubTestResult],
    judge_models: list[str],
    tie_threshold: float = 0.05,
) -> JudgeSelection:
    """Select the best sub-test using median judge scores with token-based tie-breaker.

    Algorithm:
    1. Rank sub-tests by median judge score (descending)
    2. If top two are within tie_threshold, use token usage as tie-breaker
    3. Tie-breaker selects the sub-test with fewest total tokens (more efficient)

    Args:
        subtest_results: Dict mapping sub-test ID to results
        judge_models: List of models used for judging (for documentation)
        tie_threshold: Score difference threshold for triggering tie-breaker

    Returns:
        JudgeSelection with the winning sub-test.

    """
    if not subtest_results:
        raise ValueError("No sub-test results to select from")

    # Single sub-test case
    if len(subtest_results) == 1:
        subtest_id, result = next(iter(subtest_results.items()))
        return JudgeSelection(
            winning_subtest=subtest_id,
            winning_score=result.median_score,
            votes=[
                JudgeVote(
                    subtest_id=subtest_id,
                    score=result.median_score,
                    confidence=1.0,
                    reasoning="Only sub-test in tier",
                )
            ],
            margin=1.0,
            tiebreaker_needed=False,
        )

    # Rank by median score (descending)
    ranked = sorted(
        subtest_results.items(),
        key=lambda x: x[1].median_score,
        reverse=True,
    )

    # Create votes from results
    votes = [
        JudgeVote(
            subtest_id=subtest_id,
            score=result.median_score,
            confidence=result.consistency,
            reasoning=f"Pass rate: {result.pass_rate:.1%}, "
            f"Mean score: {result.mean_score:.3f}, "
            f"Consistency: {result.consistency:.3f}",
        )
        for subtest_id, result in ranked
    ]

    first_id, first_result = ranked[0]
    second_id, second_result = ranked[1]
    margin = first_result.median_score - second_result.median_score

    # Check if tie-breaker needed
    if margin < tie_threshold:
        # Use token usage as tiebreaker (fewest tokens wins)
        first_tokens = first_result.token_stats.total_tokens
        second_tokens = second_result.token_stats.total_tokens

        winner_id = first_id if first_tokens <= second_tokens else second_id
        winner_result = subtest_results[winner_id]
        winner_tokens = min(first_tokens, second_tokens)

        tiebreaker_result = JudgeVote(
            subtest_id=winner_id,
            score=winner_result.median_score,
            confidence=1.0,
            reasoning=f"Tie broken by token usage: {winner_tokens} tokens "
            f"({first_id}={first_tokens}, {second_id}={second_tokens}). Lower is better.",
        )

        return JudgeSelection(
            winning_subtest=winner_id,
            winning_score=winner_result.median_score,
            votes=votes,
            margin=margin,
            tiebreaker_needed=True,
            tiebreaker_result=tiebreaker_result,
        )

    return JudgeSelection(
        winning_subtest=first_id,
        winning_score=first_result.median_score,
        votes=votes,
        margin=margin,
        tiebreaker_needed=False,
    )


def _run_tiebreaker(
    first_id: str,
    first_result: SubTestResult,
    second_id: str,
    second_result: SubTestResult,
    model: str,
) -> JudgeVote:
    """Run tie-breaker evaluation between two candidates.

    Uses a different LLM to break the tie by considering multiple
    factors beyond just median score.

    Args:
        first_id: ID of first candidate
        first_result: Results for first candidate
        second_id: ID of second candidate
        second_result: Results for second candidate
        model: LLM model to use for tie-breaking

    Returns:
        JudgeVote indicating the winner.

    """
    # TODO: Implement actual LLM call for tie-breaking
    # For now, use a heuristic based on multiple factors

    # Calculate composite scores
    first_composite = _calculate_composite_score(first_result)
    second_composite = _calculate_composite_score(second_result)

    if first_composite >= second_composite:
        return JudgeVote(
            subtest_id=first_id,
            score=first_composite,
            confidence=0.7,  # Lower confidence for tie-breaker
            reasoning=f"Tie-breaker selected based on composite score "
            f"({first_composite:.3f} vs {second_composite:.3f}). "
            f"Factors: consistency, cost efficiency, pass rate.",
        )
    else:
        return JudgeVote(
            subtest_id=second_id,
            score=second_composite,
            confidence=0.7,
            reasoning=f"Tie-breaker selected based on composite score "
            f"({second_composite:.3f} vs {first_composite:.3f}). "
            f"Factors: consistency, cost efficiency, pass rate.",
        )


def _calculate_composite_score(result: SubTestResult) -> float:
    """Calculate composite score for tie-breaking.

    Weighs multiple factors:
    - Median score (40%)
    - Pass rate (30%)
    - Consistency (20%)
    - Cost efficiency (10%)

    Args:
        result: Sub-test results

    Returns:
        Composite score between 0 and 1.

    """
    # Normalize cost (lower is better, assume $1 is max reasonable)
    max_cost = 1.0
    cost_efficiency = 1.0 - min(result.mean_cost / max_cost, 1.0)

    composite = (
        0.4 * result.median_score
        + 0.3 * result.pass_rate
        + 0.2 * result.consistency
        + 0.1 * cost_efficiency
    )

    return composite


def save_selection(selection: JudgeSelection, path: str | None = None) -> str:
    """Save selection result to JSON.

    Args:
        selection: The judge selection result
        path: Optional file path (if None, returns JSON string)

    Returns:
        JSON string representation.

    """
    json_str = json.dumps(selection.to_dict(), indent=2)

    if path:
        from pathlib import Path

        Path(path).write_text(json_str)

    return json_str
