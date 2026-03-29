"""cmd_repair tests for scripts/manage_experiment.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from manage_experiment import build_parser, cmd_repair

# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# cmd_repair with mock checkpoint
# ---------------------------------------------------------------------------


class TestCmdRepair:
    """Tests for cmd_repair() — checkpoint repair logic."""

    def _make_checkpoint_file(
        self, path: Path, run_states: dict[str, Any], completed_runs: dict[str, Any]
    ) -> Path:
        """Write a minimal checkpoint JSON file.

        Args:
            path: The experiment directory (checkpoint is written as path/checkpoint.json,
                  and experiment_dir in the checkpoint points to this same directory).

        """
        checkpoint_data = {
            "version": "3.1",
            "experiment_id": "test-exp",
            "experiment_dir": str(path),  # experiment_dir = path (not path.parent)
            "config_hash": "abc123",
            "started_at": "2024-01-01T00:00:00+00:00",
            "last_updated_at": "2024-01-01T00:00:00+00:00",
            "status": "interrupted",
            "run_states": run_states,
            "completed_runs": completed_runs,
        }
        checkpoint_path = path / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data))
        return checkpoint_path

    def test_repair_missing_checkpoint_returns_1(self, tmp_path: Path) -> None:
        """cmd_repair returns 1 when checkpoint file does not exist."""
        parser = build_parser()
        args = parser.parse_args(["repair", str(tmp_path / "nonexistent.json")])

        result = cmd_repair(args)
        assert result == 1

    def test_repair_fills_completed_runs_from_run_result(self, tmp_path: Path) -> None:
        """cmd_repair rebuilds completed_runs[tier][subtest][run_num] from run_result.json."""
        # Create directory structure under completed/ (promoted runs live here)
        run_dir = tmp_path / "completed" / "T0" / "00-empty" / "run_01"
        run_dir.mkdir(parents=True)

        # Write a passing run_result.json
        (run_dir / "run_result.json").write_text(json.dumps({"judge_passed": True}))

        # Write checkpoint with run in run_states but empty completed_runs
        checkpoint_path = self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00-empty": {"1": "worktree_cleaned"}}},
            completed_runs={},
        )

        parser = build_parser()
        args = parser.parse_args(["repair", str(checkpoint_path)])
        result = cmd_repair(args)

        assert result == 0

        # Verify checkpoint was updated
        from scylla.e2e.checkpoint import load_checkpoint

        updated = load_checkpoint(checkpoint_path)
        assert "T0" in updated.completed_runs
        assert "00-empty" in updated.completed_runs["T0"]
        # Pydantic coerces the string run_num key to int on load
        assert updated.completed_runs["T0"]["00-empty"][1] == "passed"

    def test_repair_marks_failed_run_correctly(self, tmp_path: Path) -> None:
        """cmd_repair marks runs with judge_passed=False as 'failed'."""
        run_dir = tmp_path / "completed" / "T0" / "00-empty" / "run_01"
        run_dir.mkdir(parents=True)

        # Write a failing run_result.json
        (run_dir / "run_result.json").write_text(json.dumps({"judge_passed": False}))

        checkpoint_path = self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00-empty": {"1": "worktree_cleaned"}}},
            completed_runs={},
        )

        parser = build_parser()
        args = parser.parse_args(["repair", str(checkpoint_path)])
        cmd_repair(args)

        from scylla.e2e.checkpoint import load_checkpoint

        updated = load_checkpoint(checkpoint_path)
        assert updated.completed_runs["T0"]["00-empty"][1] == "failed"

    def test_repair_no_run_results_is_noop(self, tmp_path: Path) -> None:
        """cmd_repair returns 0 and makes no changes when no run_result.json files exist."""
        checkpoint_path = self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00-empty": {"1": "pending"}}},
            completed_runs={},
        )

        parser = build_parser()
        args = parser.parse_args(["repair", str(checkpoint_path)])
        result = cmd_repair(args)

        assert result == 0

        from scylla.e2e.checkpoint import load_checkpoint

        updated = load_checkpoint(checkpoint_path)
        # No changes made since no run_result.json files exist
        assert updated.completed_runs == {}

    def test_repair_processes_multiple_runs(self, tmp_path: Path) -> None:
        """cmd_repair processes all runs in run_states and returns 0."""
        # Create two run directories under completed/ (promoted runs)
        for run_num in [1, 2]:
            run_dir = tmp_path / "completed" / "T0" / "00-empty" / f"run_{run_num:02d}"
            run_dir.mkdir(parents=True)
            (run_dir / "run_result.json").write_text(
                json.dumps({"judge_passed": run_num == 1})  # run 1 passes, run 2 fails
            )

        checkpoint_path = self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00-empty": {"1": "worktree_cleaned", "2": "worktree_cleaned"}}},
            completed_runs={},
        )

        parser = build_parser()
        args = parser.parse_args(["repair", str(checkpoint_path)])
        result = cmd_repair(args)

        assert result == 0

        from scylla.e2e.checkpoint import load_checkpoint

        updated = load_checkpoint(checkpoint_path)
        assert updated.completed_runs["T0"]["00-empty"][1] == "passed"
        assert updated.completed_runs["T0"]["00-empty"][2] == "failed"


# ---------------------------------------------------------------------------
# --from with existing checkpoint (reset + resume)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# cmd_repair() edge cases: skip existing entries and corrupt JSON handling
# ---------------------------------------------------------------------------


class TestCmdRepairEdgeCases:
    """Tests for cmd_repair() edge cases not covered by TestCmdRepair."""

    def _make_checkpoint_file(
        self, path: Path, run_states: dict[str, Any], completed_runs: dict[str, Any]
    ) -> Path:
        """Write a minimal checkpoint JSON file."""
        checkpoint_data = {
            "version": "3.1",
            "experiment_id": "test-exp",
            "experiment_dir": str(path),
            "config_hash": "abc123",
            "started_at": "2024-01-01T00:00:00+00:00",
            "last_updated_at": "2024-01-01T00:00:00+00:00",
            "status": "interrupted",
            "run_states": run_states,
            "completed_runs": completed_runs,
        }
        checkpoint_path = path / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data))
        return checkpoint_path

    def test_repair_skips_existing_completed_run(self, tmp_path: Path) -> None:
        """cmd_repair does not overwrite an existing completed_runs entry."""
        run_dir = tmp_path / "completed" / "T0" / "00-empty" / "run_01"
        run_dir.mkdir(parents=True)

        # run_result.json says failed, but checkpoint already has it as passed
        (run_dir / "run_result.json").write_text(json.dumps({"judge_passed": False}))

        checkpoint_path = self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00-empty": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00-empty": {"1": "passed"}}},
        )

        parser = build_parser()
        args = parser.parse_args(["repair", str(checkpoint_path)])
        result = cmd_repair(args)

        assert result == 0

        from scylla.e2e.checkpoint import load_checkpoint

        updated = load_checkpoint(checkpoint_path)
        # Existing "passed" entry must not be overwritten by run_result.json's "failed"
        assert updated.completed_runs["T0"]["00-empty"][1] == "passed"

    def test_repair_handles_corrupt_run_result_json(self, tmp_path: Path) -> None:
        """cmd_repair continues past a corrupt run_result.json without crashing."""
        run_dir = tmp_path / "completed" / "T0" / "00-empty" / "run_01"
        run_dir.mkdir(parents=True)

        # Write invalid JSON
        (run_dir / "run_result.json").write_text("{ not valid json }")

        checkpoint_path = self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00-empty": {"1": "worktree_cleaned"}}},
            completed_runs={},
        )

        parser = build_parser()
        args = parser.parse_args(["repair", str(checkpoint_path)])
        result = cmd_repair(args)

        # Must not crash and must return 0
        assert result == 0

        from scylla.e2e.checkpoint import load_checkpoint

        updated = load_checkpoint(checkpoint_path)
        # corrupt file means no entry was added
        assert updated.completed_runs == {}
