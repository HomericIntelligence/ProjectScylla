"""Tests for experiment regeneration functionality.

Python Justification: Testing Python regeneration module.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

from scylla.e2e.models import ExperimentConfig, RunResult, TierID, TokenStats
from scylla.e2e.regenerate import (
    RegenerateStats,
    _aggregate_results,
    _find_frontier,
    _has_valid_agent_result,
    _has_valid_judge_result,
    rebuild_tier_results,
    scan_run_results,
)


def test_has_valid_agent_result_missing_file(tmp_path: Path) -> None:
    """Test _has_valid_agent_result with missing file."""
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()
    assert not _has_valid_agent_result(run_dir)


def test_has_valid_agent_result_valid(tmp_path: Path) -> None:
    """Test _has_valid_agent_result with valid result."""
    run_dir = tmp_path / "run_01"
    agent_dir = run_dir / "agent"
    agent_dir.mkdir(parents=True)

    result_data = {
        "exit_code": 0,
        "token_stats": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        },
        "cost_usd": 0.01,
    }

    (agent_dir / "result.json").write_text(json.dumps(result_data))

    assert _has_valid_agent_result(run_dir)


def test_has_valid_agent_result_incomplete_execution(tmp_path: Path) -> None:
    """Test _has_valid_agent_result with incomplete execution (exit_code=-1, zero tokens)."""
    run_dir = tmp_path / "run_01"
    agent_dir = run_dir / "agent"
    agent_dir.mkdir(parents=True)

    result_data = {
        "exit_code": -1,
        "token_stats": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        },
        "cost_usd": 0.0,
    }

    (agent_dir / "result.json").write_text(json.dumps(result_data))

    assert not _has_valid_agent_result(run_dir)


def test_has_valid_judge_result_missing_file(tmp_path: Path) -> None:
    """Test _has_valid_judge_result with missing file."""
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()
    assert not _has_valid_judge_result(run_dir)


def test_has_valid_judge_result_valid(tmp_path: Path) -> None:
    """Test _has_valid_judge_result with valid result."""
    run_dir = tmp_path / "run_01"
    judge_dir = run_dir / "judge"
    judge_dir.mkdir(parents=True)

    result_data = {
        "score": 0.85,
        "passed": True,
        "grade": "A",
        "reasoning": "Good work",
    }

    (judge_dir / "result.json").write_text(json.dumps(result_data))

    assert _has_valid_judge_result(run_dir)


def test_aggregate_results_empty() -> None:
    """Test _aggregate_results with empty runs list."""
    result = _aggregate_results(TierID.T0, "00-test", [])

    assert result.subtest_id == "00-test"
    assert result.tier_id == TierID.T0
    assert result.runs == []


def test_aggregate_results_single_run() -> None:
    """Test _aggregate_results with a single run."""
    run = RunResult(
        run_number=1,
        exit_code=0,
        token_stats=TokenStats(input_tokens=100, output_tokens=50),
        cost_usd=0.01,
        duration_seconds=10.0,
        agent_duration_seconds=8.0,
        judge_duration_seconds=2.0,
        judge_score=0.85,
        judge_passed=True,
        judge_grade="A",
        judge_reasoning="Good",
        workspace_path=Path("/tmp/workspace"),
        logs_path=Path("/tmp/logs"),
    )

    result = _aggregate_results(TierID.T0, "00-test", [run])

    assert result.subtest_id == "00-test"
    assert result.tier_id == TierID.T0
    assert result.pass_rate == 1.0
    assert result.mean_score == 0.85
    assert result.median_score == 0.85
    assert result.mean_cost == 0.01
    assert result.modal_grade == "A"


def test_aggregate_results_multiple_runs() -> None:
    """Test _aggregate_results with multiple runs."""
    runs = [
        RunResult(
            run_number=1,
            exit_code=0,
            token_stats=TokenStats(input_tokens=100, output_tokens=50),
            cost_usd=0.01,
            duration_seconds=10.0,
            agent_duration_seconds=8.0,
            judge_duration_seconds=2.0,
            judge_score=0.85,
            judge_passed=True,
            judge_grade="A",
            judge_reasoning="Good",
            workspace_path=Path("/tmp/workspace1"),
            logs_path=Path("/tmp/logs1"),
        ),
        RunResult(
            run_number=2,
            exit_code=0,
            token_stats=TokenStats(input_tokens=120, output_tokens=60),
            cost_usd=0.012,
            duration_seconds=12.0,
            agent_duration_seconds=9.0,
            judge_duration_seconds=3.0,
            judge_score=0.75,
            judge_passed=True,
            judge_grade="B",
            judge_reasoning="Good",
            workspace_path=Path("/tmp/workspace2"),
            logs_path=Path("/tmp/logs2"),
        ),
    ]

    result = _aggregate_results(TierID.T0, "00-test", runs)

    assert result.subtest_id == "00-test"
    assert result.tier_id == TierID.T0
    assert result.pass_rate == 1.0
    assert result.mean_score == 0.80
    assert result.median_score == 0.80
    assert result.mean_cost == 0.011
    assert result.modal_grade in ["A", "B"]  # Both appear once


def test_find_frontier_empty() -> None:
    """Test _find_frontier with empty tier results."""
    tier_results = {}
    best_tier, best_cop = _find_frontier(tier_results)

    assert best_tier is None
    assert best_cop == float("inf")


def test_scan_run_results_empty_directory(tmp_path: Path) -> None:
    """Test scan_run_results with empty directory."""
    stats = RegenerateStats()
    results = scan_run_results(tmp_path, stats)

    assert results == {}
    assert stats.runs_found == 0
    assert stats.runs_valid == 0


def test_scan_run_results_with_valid_runs(tmp_path: Path) -> None:
    """Test scan_run_results with valid run_result.json files."""
    # Create directory structure: T0/00-test/run_01/run_result.json
    tier_dir = tmp_path / "T0"
    subtest_dir = tier_dir / "00-test"
    run_dir = subtest_dir / "run_01"
    run_dir.mkdir(parents=True)

    run_data = {
        "run_number": 1,
        "exit_code": 0,
        "token_stats": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        },
        "cost_usd": 0.01,
        "duration_seconds": 10.0,
        "agent_duration_seconds": 8.0,
        "judge_duration_seconds": 2.0,
        "judge_score": 0.85,
        "judge_passed": True,
        "judge_grade": "A",
        "judge_reasoning": "Good",
        "workspace_path": "/tmp/workspace",
        "logs_path": "/tmp/logs",
        "criteria_scores": {},
    }

    (run_dir / "run_result.json").write_text(json.dumps(run_data))

    stats = RegenerateStats()
    results = scan_run_results(tmp_path, stats)

    assert stats.runs_found == 1
    assert stats.runs_valid == 1
    assert "T0" in results
    assert "00-test" in results["T0"]
    assert len(results["T0"]["00-test"]) == 1
    assert results["T0"]["00-test"][0].run_number == 1


def test_scan_run_results_skips_failed_directories(tmp_path: Path) -> None:
    """Test scan_run_results skips .failed directories."""
    # Create directory structure with .failed
    tier_dir = tmp_path / "T0"
    subtest_dir = tier_dir / "00-test"
    run_dir = subtest_dir / ".failed" / "run_01"
    run_dir.mkdir(parents=True)

    run_data = {
        "run_number": 1,
        "exit_code": -1,
        "token_stats": {"input_tokens": 0, "output_tokens": 0},
        "cost_usd": 0.0,
        "duration_seconds": 0.0,
        "judge_score": 0.0,
        "judge_passed": False,
        "judge_grade": "F",
        "judge_reasoning": "Failed",
        "workspace_path": "/tmp/workspace",
        "logs_path": "/tmp/logs",
    }

    (run_dir / "run_result.json").write_text(json.dumps(run_data))

    stats = RegenerateStats()
    results = scan_run_results(tmp_path, stats)

    assert stats.runs_found == 1
    assert stats.runs_skipped == 1
    assert results == {}


def test_rebuild_tier_results_empty() -> None:
    """Test rebuild_tier_results with empty run results."""
    config = MagicMock(spec=ExperimentConfig)
    config.judge_model = "claude-opus-4-5-20251101"
    stats = RegenerateStats()

    tier_results = rebuild_tier_results({}, config, stats)

    assert tier_results == {}
    assert stats.tiers_processed == 0
    assert stats.subtests_processed == 0
