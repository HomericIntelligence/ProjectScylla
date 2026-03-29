"""Unit tests for the rehydrate module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.judge_selection import JudgeSelection
from scylla.e2e.models import TierID
from scylla.e2e.rehydrate import (
    load_experiment_tier_results,
    load_subtest_run_results,
    load_tier_selection,
    load_tier_subtest_results,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_run_result(run_dir: Path, run_number: int = 1, judge_score: float = 0.8) -> Path:
    """Write a minimal run_result.json to run_dir."""
    run_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "run_number": run_number,
        "exit_code": 0,
        "token_stats": {"input_tokens": 100, "output_tokens": 50},
        "cost_usd": 0.01,
        "duration_seconds": 10.0,
        "agent_duration_seconds": 8.0,
        "judge_duration_seconds": 2.0,
        "judge_score": judge_score,
        "judge_passed": judge_score >= 0.5,
        "judge_grade": "B" if judge_score >= 0.5 else "F",
        "judge_reasoning": "Test reasoning",
        "workspace_path": "/tmp/workspace",
        "logs_path": "/tmp/logs",
        "command_log_path": None,
        "criteria_scores": {},
    }
    path = run_dir / "run_result.json"
    path.write_text(json.dumps(data))
    return path


def _write_best_subtest(tier_dir: Path, winning_subtest: str = "00") -> Path:
    """Write a minimal best_subtest.json to tier_dir."""
    data = {
        "winning_subtest": winning_subtest,
        "winning_score": 0.8,
        "votes": [
            {
                "subtest_id": winning_subtest,
                "score": 0.8,
                "confidence": 0.9,
                "reasoning": "Best result",
            }
        ],
        "margin": 0.1,
        "tiebreaker_needed": False,
        "tiebreaker_result": None,
    }
    path = tier_dir / "best_subtest.json"
    path.write_text(json.dumps(data))
    return path


# ---------------------------------------------------------------------------
# load_subtest_run_results
# ---------------------------------------------------------------------------


class TestLoadSubtestRunResults:
    """Tests for load_subtest_run_results."""

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        """Returns empty list when directory does not exist."""
        result = load_subtest_run_results(tmp_path / "nonexistent")
        assert result == []

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        """Returns empty list when directory exists but has no run dirs."""
        results_dir = tmp_path / "subtest"
        results_dir.mkdir()
        result = load_subtest_run_results(results_dir)
        assert result == []

    def test_loads_single_run(self, tmp_path: Path) -> None:
        """Loads a single run_result.json."""
        results_dir = tmp_path / "subtest"
        _write_run_result(results_dir / "run_01", run_number=1, judge_score=0.9)

        result = load_subtest_run_results(results_dir)

        assert len(result) == 1
        assert result[0].run_number == 1
        assert result[0].judge_score == pytest.approx(0.9)

    def test_loads_multiple_runs_sorted(self, tmp_path: Path) -> None:
        """Loads multiple runs and returns them sorted by run_number."""
        results_dir = tmp_path / "subtest"
        _write_run_result(results_dir / "run_03", run_number=3, judge_score=0.7)
        _write_run_result(results_dir / "run_01", run_number=1, judge_score=0.9)
        _write_run_result(results_dir / "run_02", run_number=2, judge_score=0.8)

        result = load_subtest_run_results(results_dir)

        assert len(result) == 3
        assert [r.run_number for r in result] == [1, 2, 3]

    def test_skips_failed_directories(self, tmp_path: Path) -> None:
        """Skips run_result.json files under .failed/ subdirectories."""
        results_dir = tmp_path / "subtest"
        _write_run_result(results_dir / "run_01", run_number=1, judge_score=0.9)
        _write_run_result(results_dir / ".failed" / "run_01_attempt_01", run_number=1)

        result = load_subtest_run_results(results_dir)

        assert len(result) == 1
        assert result[0].run_number == 1

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        """Skips run dirs with invalid JSON without raising."""
        results_dir = tmp_path / "subtest"
        run_dir = results_dir / "run_01"
        run_dir.mkdir(parents=True)
        (run_dir / "run_result.json").write_text("not valid json")

        result = load_subtest_run_results(results_dir)
        assert result == []


# ---------------------------------------------------------------------------
# load_tier_subtest_results
# ---------------------------------------------------------------------------


class TestLoadTierSubtestResults:
    """Tests for load_tier_subtest_results."""

    def test_nonexistent_tier_dir_returns_empty(self, tmp_path: Path) -> None:
        """Returns empty dict when tier directory does not exist."""
        result = load_tier_subtest_results(tmp_path / "T0", TierID.T0)
        assert result == {}

    def test_empty_tier_dir_returns_empty(self, tmp_path: Path) -> None:
        """Returns empty dict when tier dir has no subtest subdirs."""
        tier_dir = tmp_path / "T0"
        tier_dir.mkdir()
        result = load_tier_subtest_results(tier_dir, TierID.T0)
        assert result == {}

    def test_loads_subtests_with_runs(self, tmp_path: Path) -> None:
        """Loads SubTestResult for each subtest subdirectory."""
        tier_dir = tmp_path / "T0"
        # Subtest 00: 2 passing runs
        _write_run_result(tier_dir / "00" / "run_01", run_number=1, judge_score=0.9)
        _write_run_result(tier_dir / "00" / "run_02", run_number=2, judge_score=0.8)
        # Subtest 01: 1 passing run
        _write_run_result(tier_dir / "01" / "run_01", run_number=1, judge_score=0.7)

        result = load_tier_subtest_results(tier_dir, TierID.T0)

        assert set(result.keys()) == {"00", "01"}
        assert result["00"].total_cost == pytest.approx(0.02)
        assert len(result["00"].runs) == 2
        assert len(result["01"].runs) == 1

    def test_skips_subtests_with_no_runs(self, tmp_path: Path) -> None:
        """Skips subtest directories that have no run_result.json files."""
        tier_dir = tmp_path / "T0"
        (tier_dir / "00").mkdir(parents=True)  # empty subtest dir
        _write_run_result(tier_dir / "01" / "run_01", run_number=1, judge_score=0.9)

        result = load_tier_subtest_results(tier_dir, TierID.T0)

        assert set(result.keys()) == {"01"}

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        """Skips directories starting with '.' (e.g., .failed)."""
        tier_dir = tmp_path / "T0"
        _write_run_result(tier_dir / ".hidden" / "run_01", run_number=1)
        _write_run_result(tier_dir / "00" / "run_01", run_number=1, judge_score=0.9)

        result = load_tier_subtest_results(tier_dir, TierID.T0)

        assert set(result.keys()) == {"00"}

    def test_result_has_aggregated_metrics(self, tmp_path: Path) -> None:
        """SubTestResult has correct aggregated pass_rate and median_score."""
        tier_dir = tmp_path / "T1"
        _write_run_result(tier_dir / "00" / "run_01", run_number=1, judge_score=1.0)
        _write_run_result(tier_dir / "00" / "run_02", run_number=2, judge_score=0.0)
        _write_run_result(tier_dir / "00" / "run_03", run_number=3, judge_score=1.0)

        result = load_tier_subtest_results(tier_dir, TierID.T1)

        assert "00" in result
        assert result["00"].pass_rate == pytest.approx(2 / 3)
        assert result["00"].median_score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# load_tier_selection
# ---------------------------------------------------------------------------


class TestLoadTierSelection:
    """Tests for load_tier_selection."""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """Returns None when best_subtest.json does not exist."""
        result = load_tier_selection(tmp_path / "T0")
        assert result is None

    def test_loads_valid_selection(self, tmp_path: Path) -> None:
        """Loads and parses JudgeSelection from best_subtest.json."""
        tier_dir = tmp_path / "T0"
        tier_dir.mkdir()
        _write_best_subtest(tier_dir, winning_subtest="05")

        result = load_tier_selection(tier_dir)

        assert result is not None
        assert isinstance(result, JudgeSelection)
        assert result.winning_subtest == "05"
        assert result.winning_score == pytest.approx(0.8)
        assert len(result.votes) == 1

    def test_invalid_json_returns_none(self, tmp_path: Path) -> None:
        """Returns None when best_subtest.json has invalid JSON."""
        tier_dir = tmp_path / "T0"
        tier_dir.mkdir()
        (tier_dir / "best_subtest.json").write_text("not valid json")

        result = load_tier_selection(tier_dir)
        assert result is None

    def test_tiebreaker_none_is_handled(self, tmp_path: Path) -> None:
        """Selection with tiebreaker_result=null parses correctly."""
        tier_dir = tmp_path / "T0"
        tier_dir.mkdir()
        _write_best_subtest(tier_dir)  # tiebreaker_result is None by default

        result = load_tier_selection(tier_dir)

        assert result is not None
        assert result.tiebreaker_needed is False
        assert result.tiebreaker_result is None


# ---------------------------------------------------------------------------
# load_experiment_tier_results
# ---------------------------------------------------------------------------


class TestLoadExperimentTierResults:
    """Tests for load_experiment_tier_results."""

    def test_empty_experiment_dir_returns_empty(self, tmp_path: Path) -> None:
        """Returns empty dict when no run_result.json files found."""
        config = MagicMock()
        config.judge_models = ["claude-haiku-4-5"]
        result = load_experiment_tier_results(tmp_path, config)
        assert result == {}

    def test_delegates_to_regenerate(self, tmp_path: Path) -> None:
        """Delegates to scan_run_results and rebuild_tier_results."""
        config = MagicMock()
        config.judge_models = ["claude-haiku-4-5"]

        mock_run_results: dict[str, dict[str, list[object]]] = {"T0": {"00": []}}
        mock_tier_results = {TierID.T0: MagicMock()}

        with (
            patch(
                "scylla.e2e.regenerate.scan_run_results",
                return_value=mock_run_results,
            ) as mock_scan,
            patch(
                "scylla.e2e.regenerate.rebuild_tier_results",
                return_value=mock_tier_results,
            ) as mock_rebuild,
        ):
            result = load_experiment_tier_results(tmp_path, config)

        mock_scan.assert_called_once()
        mock_rebuild.assert_called_once()
        assert result == mock_tier_results

    def test_loads_from_real_run_data(self, tmp_path: Path) -> None:
        """Integration: loads tier results from actual run_result.json files in completed/."""
        config = MagicMock()
        config.judge_models = ["claude-haiku-4-5"]

        # Create a run_result.json under completed/T0/00/run_01/ (new structure)
        _write_run_result(
            tmp_path / "completed" / "T0" / "00" / "run_01", run_number=1, judge_score=0.9
        )

        result = load_experiment_tier_results(tmp_path, config)

        assert TierID.T0 in result
        assert "00" in result[TierID.T0].subtest_results
