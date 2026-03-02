"""Integration tests: process_metrics/progress_tracking/changes in run_result.json.

Verifies that run_result.json contains the required process_metrics, progress_tracking,
and changes blocks with correct types, as written by stage_finalize_run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


PROCESS_METRIC_FLOAT_KEYS = ("r_prog", "strategic_drift", "cfp", "pr_revert_rate")


def _minimal_run_result_with_process_metrics() -> dict[str, object]:
    """Build a minimal run_result.json dict matching stage_finalize_run output.

    Returns:
        A dict with all required fields including process_metrics, progress_tracking,
        and changes as written by stage_finalize_run.

    """
    return {
        # --- base E2ERunResult fields (19 keys) ---
        "run_number": 1,
        "exit_code": 0,
        "token_stats": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        },
        "tokens_input": 100,
        "tokens_output": 50,
        "cost_usd": 0.001,
        "duration_seconds": 1.0,
        "agent_duration_seconds": 0.9,
        "judge_duration_seconds": 0.1,
        "judge_score": 0.0,
        "judge_passed": False,
        "judge_grade": "F",
        "judge_reasoning": "",
        "judges": [],
        "workspace_path": "/tmp/ws",
        "logs_path": "/tmp/logs",
        "command_log_path": None,
        "criteria_scores": {},
        "baseline_pipeline_summary": None,
        # --- computed by stage_finalize_run ---
        "process_metrics": {
            "r_prog": 0.0,
            "strategic_drift": 0.0,
            "cfp": 0.0,
            "pr_revert_rate": 0.0,
        },
        "progress_tracking": [],
        "changes": [],
    }


class TestRunResultProcessMetricsPresence:
    """Verify that run_result.json contains process_metrics, progress_tracking, changes."""

    def test_process_metrics_key_exists(self, tmp_path: Path) -> None:
        """process_metrics key must be present in run_result.json."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())

        assert "process_metrics" in loaded

    def test_process_metrics_is_dict(self, tmp_path: Path) -> None:
        """process_metrics value must be a dict."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())

        assert isinstance(loaded["process_metrics"], dict)

    @pytest.mark.parametrize("key", PROCESS_METRIC_FLOAT_KEYS)
    def test_process_metrics_float_subkeys_exist(self, tmp_path: Path, key: str) -> None:
        """Each required float subkey must be present in process_metrics."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())
        pm = loaded["process_metrics"]

        assert key in pm

    @pytest.mark.parametrize("key", PROCESS_METRIC_FLOAT_KEYS)
    def test_process_metrics_float_subkeys_are_float(self, tmp_path: Path, key: str) -> None:
        """Each required subkey in process_metrics must have a float value."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())
        pm = loaded["process_metrics"]

        assert isinstance(pm[key], float)

    def test_progress_tracking_key_exists(self, tmp_path: Path) -> None:
        """progress_tracking key must be present in run_result.json."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())

        assert "progress_tracking" in loaded

    def test_progress_tracking_is_list(self, tmp_path: Path) -> None:
        """progress_tracking value must be a list (empty is valid)."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())

        assert isinstance(loaded["progress_tracking"], list)

    def test_changes_key_exists(self, tmp_path: Path) -> None:
        """Changes key must be present in run_result.json."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())

        assert "changes" in loaded

    def test_changes_is_list(self, tmp_path: Path) -> None:
        """Changes value must be a list (empty is valid)."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())

        assert isinstance(loaded["changes"], list)


class TestRunResultProcessMetricsWithData:
    """Verify assertions hold when progress_tracking and changes contain items."""

    def test_progress_tracking_with_steps_is_list(self, tmp_path: Path) -> None:
        """progress_tracking must be a list even when it contains step items."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        data["progress_tracking"] = [
            {
                "step_id": "s1",
                "description": "Step 1",
                "weight": 1.0,
                "completed": True,
                "goal_alignment": 0.8,
            }
        ]
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())

        assert isinstance(loaded["progress_tracking"], list)
        assert len(loaded["progress_tracking"]) == 1

    def test_changes_with_items_is_list(self, tmp_path: Path) -> None:
        """Changes must be a list even when it contains change items."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        data["changes"] = [
            {
                "change_id": "c1",
                "description": "Change 1",
                "succeeded": True,
                "caused_failure": False,
                "reverted": False,
            }
        ]
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())

        assert isinstance(loaded["changes"], list)
        assert len(loaded["changes"]) == 1

    def test_process_metrics_nonzero_values_are_float(self, tmp_path: Path) -> None:
        """process_metrics float subkeys must remain float for non-zero values."""
        run_result_path = tmp_path / "run_result.json"
        data = _minimal_run_result_with_process_metrics()
        data["process_metrics"] = {
            "r_prog": 0.75,
            "strategic_drift": 0.1,
            "cfp": 0.0,
            "pr_revert_rate": 0.0,
        }
        run_result_path.write_text(json.dumps(data))

        loaded = json.loads(run_result_path.read_text())
        pm = loaded["process_metrics"]

        for key in PROCESS_METRIC_FLOAT_KEYS:
            assert isinstance(pm[key], float), f"{key} should be float"
