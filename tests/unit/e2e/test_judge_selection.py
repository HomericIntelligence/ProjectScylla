"""Unit tests for judge selection."""

from __future__ import annotations

import pytest

from scylla.e2e.judge_selection import (
    JudgeSelection,
    JudgeVote,
    _calculate_composite_score,
    select_best_subtest,
)
from scylla.e2e.models import SubTestResult, TierID, TokenStats


class TestJudgeVote:
    """Tests for JudgeVote."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        vote = JudgeVote(
            subtest_id="01",
            score=0.85,
            confidence=0.9,
            reasoning="Good performance",
        )

        d = vote.to_dict()

        assert d["subtest_id"] == "01"
        assert d["score"] == 0.85
        assert d["confidence"] == 0.9


class TestJudgeSelection:
    """Tests for JudgeSelection."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        selection = JudgeSelection(
            winning_subtest="01",
            winning_score=0.85,
            votes=[
                JudgeVote(subtest_id="01", score=0.85, confidence=0.9, reasoning="Good"),
                JudgeVote(subtest_id="02", score=0.80, confidence=0.8, reasoning="Okay"),
            ],
            margin=0.05,
            tiebreaker_needed=False,
        )

        d = selection.to_dict()

        assert d["winning_subtest"] == "01"
        assert d["margin"] == 0.05
        assert len(d["votes"]) == 2


class TestSelectBestSubtest:
    """Tests for select_best_subtest function."""

    def test_single_subtest(self) -> None:
        """Test selection with single subtest."""
        results = {
            "baseline": SubTestResult(
                subtest_id="baseline",
                tier_id=TierID.T0,
                runs=[],
                median_score=0.75,
            ),
        }

        selection = select_best_subtest(results, judge_models=["claude-sonnet-4-5"])

        assert selection.winning_subtest == "baseline"
        assert selection.margin == 1.0
        assert not selection.tiebreaker_needed

    def test_clear_winner(self) -> None:
        """Test selection with clear winner."""
        results = {
            "01": SubTestResult(
                subtest_id="01",
                tier_id=TierID.T2,
                runs=[],
                median_score=0.90,
                consistency=0.9,
            ),
            "02": SubTestResult(
                subtest_id="02",
                tier_id=TierID.T2,
                runs=[],
                median_score=0.70,
                consistency=0.8,
            ),
        }

        selection = select_best_subtest(results, judge_models=["claude-sonnet-4-5"])

        assert selection.winning_subtest == "01"
        assert abs(selection.margin - 0.20) < 0.001  # Float comparison
        assert not selection.tiebreaker_needed

    def test_tiebreaker_triggered(self) -> None:
        """Test that tiebreaker is triggered for close scores and uses token usage."""
        results = {
            "01": SubTestResult(
                subtest_id="01",
                tier_id=TierID.T2,
                runs=[],
                median_score=0.82,
                mean_score=0.82,
                pass_rate=0.8,
                consistency=0.9,
                mean_cost=0.10,
                token_stats=TokenStats(
                    input_tokens=8000,
                    output_tokens=2000,  # total_tokens will be 10000
                ),
            ),
            "02": SubTestResult(
                subtest_id="02",
                tier_id=TierID.T2,
                runs=[],
                median_score=0.80,
                mean_score=0.80,
                pass_rate=0.9,
                consistency=0.95,
                mean_cost=0.08,
                token_stats=TokenStats(
                    input_tokens=6000,
                    output_tokens=1500,  # total_tokens will be 7500 - fewer tokens, should win
                ),
            ),
        }

        selection = select_best_subtest(
            results, judge_models=["claude-sonnet-4-5"], tie_threshold=0.05
        )

        assert selection.tiebreaker_needed
        assert selection.tiebreaker_result is not None
        # 02 should win because it has fewer tokens (7500 < 10000)
        assert selection.winning_subtest == "02"
        assert "token usage" in selection.tiebreaker_result.reasoning.lower()

    def test_empty_results(self) -> None:
        """Test that empty results raise error."""
        with pytest.raises(ValueError, match="No sub-test results"):
            select_best_subtest({}, judge_models=["claude-sonnet-4-5"])


class TestCompositeScore:
    """Tests for composite score calculation."""

    def test_high_score_result(self) -> None:
        """Test composite score for high-performing result."""
        result = SubTestResult(
            subtest_id="01",
            tier_id=TierID.T2,
            runs=[],
            median_score=0.95,
            pass_rate=0.9,
            consistency=0.85,
            mean_cost=0.05,
        )

        score = _calculate_composite_score(result)

        # Should be high (close to 1.0)
        assert score > 0.8

    def test_low_score_result(self) -> None:
        """Test composite score for low-performing result."""
        result = SubTestResult(
            subtest_id="01",
            tier_id=TierID.T2,
            runs=[],
            median_score=0.2,
            pass_rate=0.1,
            consistency=0.3,
            mean_cost=0.80,
        )

        score = _calculate_composite_score(result)

        # Should be low
        assert score < 0.3

    def test_balanced_result(self) -> None:
        """Test composite score for balanced result."""
        result = SubTestResult(
            subtest_id="01",
            tier_id=TierID.T2,
            runs=[],
            median_score=0.5,
            pass_rate=0.5,
            consistency=0.5,
            mean_cost=0.50,
        )

        score = _calculate_composite_score(result)

        # Should be around 0.5
        assert 0.4 < score < 0.6
