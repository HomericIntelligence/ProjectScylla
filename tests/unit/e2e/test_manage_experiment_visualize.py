"""cmd_visualize tests for scripts/manage_experiment.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from manage_experiment import build_parser, cmd_visualize

# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# cmd_visualize
# ---------------------------------------------------------------------------


class TestCmdVisualize:
    """Tests for cmd_visualize() — experiment state visualization."""

    def _make_checkpoint_file(
        self,
        path: Path,
        experiment_id: str = "test-exp",
        experiment_state: str = "complete",
        tier_states: dict[str, str] | None = None,
        subtest_states: dict[str, dict[str, str]] | None = None,
        run_states: dict[str, dict[str, dict[str, str]]] | None = None,
        completed_runs: dict[str, Any] | None = None,
        started_at: str = "2026-02-23T18:56:10+00:00",
        last_updated_at: str = "2026-02-23T19:20:33+00:00",
        pid: int | None = None,
    ) -> Path:
        """Write a minimal checkpoint JSON file."""
        checkpoint_data: dict[str, Any] = {
            "version": "3.1",
            "experiment_id": experiment_id,
            "experiment_dir": str(path),
            "config_hash": "abc123",
            "started_at": started_at,
            "last_updated_at": last_updated_at,
            "status": "completed" if experiment_state == "complete" else "running",
            "experiment_state": experiment_state,
            "tier_states": tier_states or {},
            "subtest_states": subtest_states or {},
            "run_states": run_states or {},
            "completed_runs": completed_runs or {},
        }
        if pid is not None:
            checkpoint_data["pid"] = pid
        checkpoint_path = path / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data))
        return checkpoint_path

    def test_visualize_subcommand_registered(self) -> None:
        """'visualize' subcommand is registered in build_parser()."""
        parser = build_parser()
        subparsers_action = next(
            action for action in parser._actions if hasattr(action, "choices") and action.choices
        )
        assert "visualize" in subparsers_action.choices

    def test_visualize_default_format_is_tree(self) -> None:
        """'visualize' subcommand defaults output_format to 'tree'."""
        parser = build_parser()
        args = parser.parse_args(["visualize", "/some/path"])
        assert args.output_format == "tree"

    def test_visualize_missing_path_returns_1(self, tmp_path: Path) -> None:
        """cmd_visualize returns 1 when the path does not exist."""
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path / "nonexistent")])
        result = cmd_visualize(args)
        assert result == 1

    def test_visualize_directory_resolves_checkpoint(self, tmp_path: Path) -> None:
        """cmd_visualize accepts a directory and reads checkpoint.json from it."""
        self._make_checkpoint_file(
            tmp_path,
            tier_states={"T0": "complete"},
            subtest_states={"T0": {"00": "aggregated"}},
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path)])
        result = cmd_visualize(args)
        assert result == 0

    def test_visualize_tree_complete_experiment(self, tmp_path: Path, capsys) -> None:
        """Tree format renders experiment name and tier states for a complete experiment."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-017",
            experiment_state="complete",
            tier_states={"T0": "complete", "T1": "complete"},
            subtest_states={"T0": {"00": "aggregated"}, "T1": {"01": "aggregated"}},
            run_states={
                "T0": {"00": {"1": "worktree_cleaned"}},
                "T1": {"01": {"1": "worktree_cleaned"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}, "T1": {"01": {1: "failed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path)])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "test-017" in out
        assert "complete" in out
        assert "T0" in out
        assert "T1" in out
        assert "passed" in out
        assert "failed" in out

    def test_visualize_tree_failed_experiment(self, tmp_path: Path, capsys) -> None:
        """Tree format renders 'failed' state for a failed experiment."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-fail",
            experiment_state="failed",
            tier_states={"T0": "failed"},
            subtest_states={"T0": {"00": "failed"}},
            run_states={"T0": {"00": {"1": "failed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path)])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "test-fail" in out
        assert "failed" in out

    def test_visualize_tree_partial_experiment(self, tmp_path: Path, capsys) -> None:
        """Tree format renders mixed states (partial / in-progress) correctly."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-partial",
            experiment_state="tiers_running",
            tier_states={"T0": "complete", "T1": "running"},
            subtest_states={"T0": {"00": "aggregated"}, "T1": {"01": "runs_in_progress"}},
            run_states={
                "T0": {"00": {"1": "worktree_cleaned"}},
                "T1": {"01": {"1": "agent_complete"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path)])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "T0" in out
        assert "T1" in out
        assert "complete" in out

    def test_visualize_table_format(self, tmp_path: Path, capsys) -> None:
        """Table format includes a header row and a data row per run."""
        self._make_checkpoint_file(
            tmp_path,
            tier_states={"T0": "complete"},
            subtest_states={"T0": {"00": "aggregated"}},
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--format", "table"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "TIER" in out
        assert "STATE" in out
        assert "T0" in out
        assert "worktree_cleaned" in out
        assert "passed" in out

    def test_visualize_json_format(self, tmp_path: Path, capsys) -> None:
        """JSON format outputs valid JSON containing expected keys."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-json",
            experiment_state="complete",
            tier_states={"T0": "complete"},
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--format", "json"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["experiment_id"] == "test-json"
        assert data["experiment_state"] == "complete"
        assert "tier_states" in data
        assert "run_states" in data

    def test_visualize_tier_filter(self, tmp_path: Path, capsys) -> None:
        """--tier T0 limits output to T0 only, omitting T1."""
        self._make_checkpoint_file(
            tmp_path,
            tier_states={"T0": "complete", "T1": "complete"},
            subtest_states={"T0": {"00": "aggregated"}, "T1": {"01": "aggregated"}},
            run_states={
                "T0": {"00": {"1": "worktree_cleaned"}},
                "T1": {"01": {"1": "worktree_cleaned"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}, "T1": {"01": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--tier", "T0"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "T0" in out
        assert "T1" not in out

    def test_visualize_verbose_timestamps(self, tmp_path: Path, capsys) -> None:
        """--verbose shows Started line and PID."""
        self._make_checkpoint_file(
            tmp_path,
            started_at="2026-02-23T18:56:10+00:00",
            last_updated_at="2026-02-23T19:20:33+00:00",
            pid=12345,
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--verbose"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "Started:" in out
        assert "PID: 12345" in out

    def test_visualize_empty_tiers(self, tmp_path: Path, capsys) -> None:
        """Checkpoint with no tier_states renders '(no tiers)' message."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-empty",
            experiment_state="initializing",
            tier_states={},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path)])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "(no tiers)" in out

    def test_visualize_batch_directory(self, tmp_path: Path, capsys) -> None:
        """Batch mode: results dir with multiple experiment subdirs shows all experiments."""
        for exp_id in ["exp-01", "exp-02"]:
            exp_dir = tmp_path / exp_id
            exp_dir.mkdir()
            self._make_checkpoint_file(
                exp_dir,
                experiment_id=exp_id,
                experiment_state="complete",
                tier_states={"T0": "complete"},
            )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path)])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "exp-01" in out
        assert "exp-02" in out

    def test_visualize_states_only_single(self, tmp_path: Path, capsys) -> None:
        """--states-only with single experiment: shows TIER/SUBTEST/RUN/STATE, no EXP or RESULT."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-exp",
            tier_states={"T0": "complete"},
            subtest_states={"T0": {"00": "aggregated"}},
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--states-only"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "TIER" in out
        assert "STATE" in out
        assert "RESULT" not in out
        assert "EXP" not in out
        assert "T0" in out
        assert "worktree_cleaned" in out

    def test_visualize_states_only_batch(self, tmp_path: Path, capsys) -> None:
        """--states-only with multiple experiments shows EXP column in unified table."""
        for exp_id in ["exp-01", "exp-02"]:
            exp_dir = tmp_path / exp_id
            exp_dir.mkdir()
            self._make_checkpoint_file(
                exp_dir,
                experiment_id=exp_id,
                tier_states={"T0": "complete"},
                subtest_states={"T0": {"00": "aggregated"}},
                run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
                completed_runs={"T0": {"00": {1: "passed"}}},
            )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--states-only"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "EXP" in out
        assert "TIER" in out
        assert "STATE" in out
        assert "RESULT" not in out
        assert "exp-01" in out
        assert "exp-02" in out
        assert "worktree_cleaned" in out

    def test_visualize_states_only_tier_filter(self, tmp_path: Path, capsys) -> None:
        """--states-only with --tier T0 limits output to T0 only."""
        self._make_checkpoint_file(
            tmp_path,
            tier_states={"T0": "complete", "T1": "complete"},
            subtest_states={"T0": {"00": "aggregated"}, "T1": {"01": "aggregated"}},
            run_states={
                "T0": {"00": {"1": "worktree_cleaned"}},
                "T1": {"01": {"1": "worktree_cleaned"}},
            },
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--states-only", "--tier", "T0"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "T0" in out
        assert "T1" not in out

    def test_visualize_json_tier_filter(self, tmp_path: Path, capsys: Any) -> None:
        """--format json --tier T0 with multi-tier data: JSON output only contains T0."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-json-filter",
            experiment_state="complete",
            tier_states={"T0": "complete", "T1": "complete"},
            subtest_states={"T0": {"00": "aggregated"}, "T1": {"01": "aggregated"}},
            run_states={
                "T0": {"00": {"1": "worktree_cleaned"}},
                "T1": {"01": {"1": "worktree_cleaned"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}, "T1": {"01": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--format", "json", "--tier", "T0"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "T0" in data["tier_states"]
        assert "T1" not in data["tier_states"]
        assert "T0" in data["run_states"]
        assert "T1" not in data["run_states"]

    def test_visualize_json_tier_filter_nonexistent(self, tmp_path: Path, capsys: Any) -> None:
        """--format json --tier T99 with no matching data: state dicts are empty."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-json-nofilter",
            experiment_state="complete",
            tier_states={"T0": "complete"},
            subtest_states={"T0": {"00": "aggregated"}},
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--format", "json", "--tier", "T99"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["tier_states"] == {}
        assert data["run_states"] == {}

    def test_visualize_table_tier_filter(self, tmp_path: Path, capsys: Any) -> None:
        """--format table --tier T0: table rows contain T0 data and no T1 data."""
        self._make_checkpoint_file(
            tmp_path,
            tier_states={"T0": "complete", "T1": "complete"},
            subtest_states={"T0": {"00": "aggregated"}, "T1": {"01": "aggregated"}},
            run_states={
                "T0": {"00": {"1": "worktree_cleaned"}},
                "T1": {"01": {"1": "worktree_cleaned"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}, "T1": {"01": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--format", "table", "--tier", "T0"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "T0" in out
        assert "T1" not in out

    def test_visualize_table_tier_filter_nonexistent(self, tmp_path: Path, capsys: Any) -> None:
        """--format table --tier T99: header row rendered but no data rows."""
        self._make_checkpoint_file(
            tmp_path,
            tier_states={"T0": "complete"},
            subtest_states={"T0": {"00": "aggregated"}},
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--format", "table", "--tier", "T99"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "TIER" in out
        assert "T0" not in out

    def test_visualize_states_only_overrides_format(self, tmp_path: Path, capsys: Any) -> None:
        """--states-only --format table: states-only table is rendered without RESULT column."""
        self._make_checkpoint_file(
            tmp_path,
            tier_states={"T0": "complete"},
            subtest_states={"T0": {"00": "aggregated"}},
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--states-only", "--format", "table"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "TIER" in out
        assert "STATE" in out
        assert "RESULT" not in out

    def test_visualize_tier_filter_excludes_all_tree(self, tmp_path: Path, capsys: Any) -> None:
        """--tier T99 with tree format: experiment renders but contains no tier data rows."""
        self._make_checkpoint_file(
            tmp_path,
            experiment_id="test-nodata",
            experiment_state="complete",
            tier_states={"T0": "complete"},
            subtest_states={"T0": {"00": "aggregated"}},
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--tier", "T99"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "test-nodata" in out
        assert "T0" not in out


# ---------------------------------------------------------------------------
# --retry-errors in single mode
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _find_checkpoint_path helper
# ---------------------------------------------------------------------------


class TestFindCheckpointPath:
    """Tests for the _find_checkpoint_path helper in manage_experiment.py."""

    def test_find_checkpoint_path_with_timestamp_prefix(self, tmp_path: Path) -> None:
        """Finds checkpoint in a timestamp-prefixed directory matching *-{experiment_id}."""
        from manage_experiment import _find_checkpoint_path

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        exp_dir = results_dir / "2026-02-25T06-12-39-test-001"
        exp_dir.mkdir()
        cp = exp_dir / "checkpoint.json"
        cp.write_text('{"experiment_id": "test-001"}')

        result = _find_checkpoint_path(results_dir, "test-001")
        assert result == cp

    def test_find_checkpoint_path_returns_none_when_no_match(self, tmp_path: Path) -> None:
        """Returns None when no matching directory exists."""
        from manage_experiment import _find_checkpoint_path

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        result = _find_checkpoint_path(results_dir, "nonexistent-exp")
        assert result is None

    def test_find_checkpoint_path_returns_most_recent(self, tmp_path: Path) -> None:
        """When multiple timestamp-prefixed dirs match, returns the most recent one."""
        from manage_experiment import _find_checkpoint_path

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        older = results_dir / "2026-02-24T10-00-00-test-001"
        older.mkdir()
        (older / "checkpoint.json").write_text('{"version": "3.1"}')

        newer = results_dir / "2026-02-25T06-12-39-test-001"
        newer.mkdir()
        (newer / "checkpoint.json").write_text('{"version": "3.1"}')

        result = _find_checkpoint_path(results_dir, "test-001")
        assert result == newer / "checkpoint.json"


# ---------------------------------------------------------------------------
# _derive_run_result and in_progress display
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _derive_run_result and in_progress display
# ---------------------------------------------------------------------------


class TestDeriveRunResult:
    """Tests for _derive_run_result helper and in_progress display in visualize."""

    def _make_checkpoint_file(
        self,
        path: Path,
        run_states: dict[str, dict[str, dict[str, str]]],
        completed_runs: dict[str, Any] | None = None,
    ) -> Path:
        data: dict[str, Any] = {
            "version": "3.1",
            "experiment_id": "test-exp",
            "experiment_dir": str(path),
            "config_hash": "abc123",
            "started_at": "2026-01-01T00:00:00+00:00",
            "last_updated_at": "2026-01-01T00:00:01+00:00",
            "status": "running",
            "experiment_state": "tiers_running",
            "tier_states": {"T0": "subtests_running"},
            "subtest_states": {"T0": {"00": "runs_in_progress"}},
            "run_states": run_states,
            "completed_runs": completed_runs or {},
        }
        cp = path / "checkpoint.json"
        cp.write_text(json.dumps(data))
        return cp

    def test_derive_run_result_returns_in_progress_for_mid_sequence_state(
        self, tmp_path: Path
    ) -> None:
        """_derive_run_result returns 'in_progress' when run_state is mid-sequence."""
        from manage_experiment import _derive_run_result

        from scylla.e2e.checkpoint import load_checkpoint

        self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00": {"1": "replay_generated"}}},
        )
        cp = load_checkpoint(tmp_path / "checkpoint.json")
        result = _derive_run_result(cp, "T0", "00", 1, "replay_generated")
        assert result == "in_progress"

    def test_derive_run_result_returns_stored_status_for_completed_run(
        self, tmp_path: Path
    ) -> None:
        """_derive_run_result returns stored status ('passed') for completed runs."""
        from manage_experiment import _derive_run_result

        from scylla.e2e.checkpoint import load_checkpoint

        self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        cp = load_checkpoint(tmp_path / "checkpoint.json")
        result = _derive_run_result(cp, "T0", "00", 1, "worktree_cleaned")
        assert result == "passed"

    def test_derive_run_result_returns_empty_for_pending(self, tmp_path: Path) -> None:
        """_derive_run_result returns '' for pending runs."""
        from manage_experiment import _derive_run_result

        from scylla.e2e.checkpoint import load_checkpoint

        self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00": {"1": "pending"}}},
        )
        cp = load_checkpoint(tmp_path / "checkpoint.json")
        result = _derive_run_result(cp, "T0", "00", 1, "pending")
        assert result == ""

    def test_visualize_tree_shows_in_progress_for_mid_sequence_run(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """Tree view shows '-> in_progress' for a run stopped mid-sequence by --until."""
        self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00": {"1": "replay_generated"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path)])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "in_progress" in out

    def test_visualize_table_shows_in_progress_for_mid_sequence_run(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """Table view shows 'in_progress' in the RESULT column for mid-sequence runs."""
        self._make_checkpoint_file(
            tmp_path,
            run_states={"T0": {"00": {"1": "replay_generated"}}},
        )
        parser = build_parser()
        args = parser.parse_args(["visualize", str(tmp_path), "--format", "table"])
        result = cmd_visualize(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "in_progress" in out


# ---------------------------------------------------------------------------
# --tiers and --max-subtests flow to ExperimentConfig
# ---------------------------------------------------------------------------
