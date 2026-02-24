"""Smoke tests for scripts/manage_experiment.py — parser construction and argument validation.

Tests cover:
- build_parser() produces a parser with expected subcommands (run, repair)
- run subcommand accepts its documented required/optional arguments
- Multi-path --config triggers batch mode detection
- Auto-expansion of parent dir to batch mode
- Invalid --until / --until-tier / --until-experiment values return exit code 1
- Valid --until values are accepted without error
- --from / --from-tier / --from-experiment argument parsing
- cmd_repair with a mock checkpoint rebuilds completed_runs entries
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from manage_experiment import build_parser, cmd_repair

# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Tests for build_parser() — verifies subcommand registration."""

    def test_parser_returns_argument_parser(self) -> None:
        """build_parser() returns a non-None ArgumentParser."""
        import argparse

        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_run_and_repair_subcommands_registered(self) -> None:
        """'run' and 'repair' subcommands are registered; old ones are gone."""
        parser = build_parser()
        subparsers_action = next(
            action for action in parser._actions if hasattr(action, "choices") and action.choices
        )
        registered = set(subparsers_action.choices.keys())
        assert "run" in registered
        assert "repair" in registered
        # Old subcommands must be removed
        assert "batch" not in registered
        assert "rerun-agents" not in registered
        assert "rerun-judges" not in registered
        assert "regenerate" not in registered

    def test_run_subcommand_accepts_tiers_arg(self) -> None:
        """'run' subcommand accepts --tiers argument."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--tiers",
                "T0",
                "T1",
            ]
        )
        assert args.tiers == ["T0", "T1"]
        assert args.subcommand == "run"

    def test_run_subcommand_defaults(self) -> None:
        """'run' subcommand has expected default values."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
            ]
        )
        assert args.runs == 10
        assert args.parallel == 4
        assert args.model == "sonnet"
        assert args.judge_model == "sonnet"
        assert args.thinking == "None"
        assert args.until is None
        assert args.until_tier is None
        assert args.until_experiment is None
        assert args.from_run is None
        assert args.from_tier is None
        assert args.from_experiment is None
        assert args.filter_tier is None
        assert args.filter_subtest is None
        assert args.filter_run is None
        assert args.filter_status is None
        assert args.filter_judge_slot is None
        assert args.threads == 4
        assert args.tests is None
        assert not args.retry_errors

    def test_repair_subcommand_requires_checkpoint_path(self) -> None:
        """'repair' subcommand requires a positional checkpoint_path argument."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["repair"])  # Missing required positional

    def test_repair_subcommand_accepts_checkpoint_path(self) -> None:
        """'repair' subcommand accepts checkpoint_path positional."""
        parser = build_parser()
        args = parser.parse_args(["repair", "/path/to/checkpoint.json"])
        assert args.checkpoint_path == Path("/path/to/checkpoint.json")
        assert args.subcommand == "repair"

    def test_run_accepts_until_flag(self) -> None:
        """'run' subcommand accepts --until state flag."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--until",
                "agent_complete",
            ]
        )
        assert args.until == "agent_complete"

    def test_run_accepts_until_tier_flag(self) -> None:
        """'run' subcommand accepts --until-tier state flag."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--until-tier",
                "subtests_complete",
            ]
        )
        assert args.until_tier == "subtests_complete"

    def test_run_accepts_until_experiment_flag(self) -> None:
        """'run' subcommand accepts --until-experiment state flag."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--until-experiment",
                "tiers_running",
            ]
        )
        assert args.until_experiment == "tiers_running"

    def test_run_accepts_from_flag(self) -> None:
        """'run' subcommand accepts --from state flag."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--from",
                "replay_generated",
            ]
        )
        assert args.from_run == "replay_generated"

    def test_run_accepts_from_run_alias(self) -> None:
        """'run' subcommand accepts --from-run as alias for --from."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--from-run",
                "agent_complete",
            ]
        )
        assert args.from_run == "agent_complete"

    def test_run_accepts_from_tier_flag(self) -> None:
        """'run' subcommand accepts --from-tier flag."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--from-tier",
                "subtests_running",
            ]
        )
        assert args.from_tier == "subtests_running"

    def test_run_accepts_from_experiment_flag(self) -> None:
        """'run' subcommand accepts --from-experiment flag."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--from-experiment",
                "tiers_running",
            ]
        )
        assert args.from_experiment == "tiers_running"

    def test_run_accepts_filter_tier(self) -> None:
        """'run' subcommand accepts --filter-tier (repeatable)."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--filter-tier",
                "T0",
                "--filter-tier",
                "T1",
            ]
        )
        assert args.filter_tier == ["T0", "T1"]

    def test_run_accepts_filter_status(self) -> None:
        """'run' subcommand accepts --filter-status (repeatable)."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--filter-status",
                "failed",
                "--filter-status",
                "agent_complete",
            ]
        )
        assert args.filter_status == ["failed", "agent_complete"]

    def test_run_accepts_filter_judge_slot(self) -> None:
        """'run' subcommand accepts --filter-judge-slot (repeatable)."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--filter-judge-slot",
                "1",
                "--filter-judge-slot",
                "2",
            ]
        )
        assert args.filter_judge_slot == [1, 2]

    def test_run_accepts_threads(self) -> None:
        """'run' subcommand accepts --threads argument."""
        parser = build_parser()
        args = parser.parse_args(["run", "--threads", "8"])
        assert args.threads == 8

    def test_run_accepts_tests_filter(self) -> None:
        """'run' subcommand accepts --tests for batch filtering."""
        parser = build_parser()
        args = parser.parse_args(["run", "--tests", "test-001", "test-005"])
        assert args.tests == ["test-001", "test-005"]

    def test_run_accepts_retry_errors(self) -> None:
        """'run' subcommand accepts --retry-errors flag."""
        parser = build_parser()
        args = parser.parse_args(["run", "--retry-errors"])
        assert args.retry_errors is True

    def test_run_accepts_multi_config(self) -> None:
        """'run' subcommand accepts multiple --config arguments."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                "/path/to/test-001",
                "--config",
                "/path/to/test-002",
            ]
        )
        assert len(args.config) == 2
        assert args.config[0] == Path("/path/to/test-001")
        assert args.config[1] == Path("/path/to/test-002")

    def test_subcommand_required(self) -> None:
        """Calling with no subcommand exits with error."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


# ---------------------------------------------------------------------------
# Batch mode detection
# ---------------------------------------------------------------------------


class TestBatchModeDetection:
    """Tests for batch mode detection in cmd_run()."""

    def test_single_config_dir_without_test_subdirs_is_single_mode(self, tmp_path: Path) -> None:
        """A single --config dir with no test-* subdirs stays in single-test mode."""
        # Create a dir without test-* subdirs
        config_dir = tmp_path / "shared"
        config_dir.mkdir()

        parser = build_parser()
        args = parser.parse_args(["run", "--config", str(config_dir)])
        # Should have config=[config_dir] and len=1 with no test-* subdirs
        assert args.config == [config_dir]

    def test_auto_discovery_from_parent_dir(self, tmp_path: Path) -> None:
        """A parent dir containing test-* subdirs triggers batch mode."""
        # Create test-* subdirs
        for i in [1, 2, 3]:
            (tmp_path / f"test-{i:03d}").mkdir()
        # Also create non-test dir (should be excluded)
        (tmp_path / "shared").mkdir()

        from manage_experiment import cmd_run

        call_args = []

        def mock_run_batch(test_dirs, passed_args):
            call_args.append(test_dirs)
            return 0

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path),
                "--skip-judge-validation",
            ]
        )

        with patch("manage_experiment._run_batch", side_effect=mock_run_batch):
            result = cmd_run(args)

        assert result == 0
        assert len(call_args) == 1
        # Should have discovered exactly the 3 test-* dirs
        discovered = {d.name for d in call_args[0]}
        assert discovered == {"test-001", "test-002", "test-003"}

    def test_multiple_config_triggers_batch(self, tmp_path: Path) -> None:
        """Multiple --config arguments trigger batch mode."""
        dir1 = tmp_path / "test-001"
        dir2 = tmp_path / "test-002"
        dir1.mkdir()
        dir2.mkdir()

        from manage_experiment import cmd_run

        call_args = []

        def mock_run_batch(test_dirs, passed_args):
            call_args.append(test_dirs)
            return 0

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(dir1),
                "--config",
                str(dir2),
            ]
        )

        with patch("manage_experiment._run_batch", side_effect=mock_run_batch):
            result = cmd_run(args)

        assert result == 0
        assert len(call_args) == 1
        assert len(call_args[0]) == 2


# ---------------------------------------------------------------------------
# cmd_run argument validation (until state parsing)
# ---------------------------------------------------------------------------


class TestCmdRunUntilValidation:
    """Tests for cmd_run() --until argument validation."""

    def test_invalid_until_state_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns exit code 1 for an unknown --until state."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--config",
                str(tmp_path),
                "--until",
                "nonexistent_state_xyz",
                "--skip-judge-validation",  # avoid API call
            ]
        )

        from manage_experiment import cmd_run

        # Mock validate_model to avoid API call
        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1

    def test_invalid_until_tier_state_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns exit code 1 for an unknown --until-tier state."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--config",
                str(tmp_path),
                "--until-tier",
                "invalid_tier_state",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1

    def test_invalid_until_experiment_state_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns exit code 1 for an unknown --until-experiment state."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--config",
                str(tmp_path),
                "--until-experiment",
                "invalid_experiment_state",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1

    def test_missing_repo_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns exit code 1 when --repo is missing."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--commit",
                "abc123",
                "--config",
                str(tmp_path),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1

    def test_missing_commit_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns exit code 1 when --commit is missing."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--config",
                str(tmp_path),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1


# ---------------------------------------------------------------------------
# --from argument validation
# ---------------------------------------------------------------------------


class TestCmdRunFromValidation:
    """Tests for cmd_run() --from argument parsing and validation."""

    def test_invalid_from_state_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns exit code 1 for an unknown --from state."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--config",
                str(tmp_path),
                "--from",
                "nonexistent_state_xyz",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1

    def test_from_requires_existing_checkpoint(self, tmp_path: Path) -> None:
        """cmd_run returns 1 when --from is used but no checkpoint exists."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--config",
                str(tmp_path),
                "--from",
                "agent_complete",
                "--results-dir",
                str(tmp_path / "results"),
                "--experiment-id",
                "test-exp",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1  # No checkpoint exists

    def test_invalid_from_tier_state_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns exit code 1 for an unknown --from-tier state."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--config",
                str(tmp_path),
                "--from-tier",
                "invalid_tier_xyz",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1

    def test_invalid_from_experiment_state_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns exit code 1 for an unknown --from-experiment state."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--config",
                str(tmp_path),
                "--from-experiment",
                "invalid_experiment_xyz",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1


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
        # Create directory structure
        run_dir = tmp_path / "T0" / "00-empty" / "run_01"
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
        run_dir = tmp_path / "T0" / "00-empty" / "run_01"
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
        # Create two run directories
        for run_num in [1, 2]:
            run_dir = tmp_path / "T0" / "00-empty" / f"run_{run_num:02d}"
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
