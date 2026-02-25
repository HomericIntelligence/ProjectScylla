"""Smoke tests for scripts/manage_experiment.py — parser construction and argument validation.

Tests cover:
- build_parser() produces a parser with expected subcommands (run, repair)
- run subcommand accepts its documented required/optional arguments
- Multi-path --config triggers batch mode detection
- Auto-expansion of parent dir to batch mode
- test-config-loader exclusion in batch auto-discovery
- Invalid --until / --until-tier / --until-experiment values return exit code 1
- Valid --until values are accepted without error
- --from / --from-tier / --from-experiment argument parsing
- --from with existing checkpoint: reset functions called + run_experiment invoked
- --from in batch mode: reset logic called per-test
- --add-judge dedup: duplicate judge models are not added twice
- --add-judge bare flag (no value) uses const="sonnet"
- YAML config file mode: single .yaml file as --config
- YAML config file overrides values from test.yaml
- --filter-judge-slot: accepted but has no effect (not-yet-implemented)
- Non-existent --config path in single mode returns exit code 1
- cmd_repair with a mock checkpoint rebuilds completed_runs entries
- --verbose / --quiet set root logger level
- --fresh forwarded to run_experiment
- --until* valid values flow to ExperimentConfig
- --from-tier with --filter-tier passes tier_filter kwarg
- --from-experiment calls reset_experiment_for_from_state
- batch --from without checkpoint warns and runs fresh
- --tests filter limits batch execution
- --retry-errors reruns only failed tests
- --add-judge in batch mode appends extra judge to judge_models
- --from + --filter-status failed resets failed runs (checkpoint.py fix)
- --parallel-high/med/low flow to ExperimentConfig
- model alias (opus/haiku) resolves to full model ID
- unknown tier name returns exit code 1
- --skip-judge-validation skips validate_model call
- --timeout overrides test.yaml value
- --thinking High flows to ExperimentConfig
- --timeout defaults to test.yaml when not specified on CLI
- MODEL_ALIASES module-level constant exists with expected keys
- invalid --tiers in batch mode returns 1 before running tests
- invalid --from in batch mode returns 1 before running tests
- non-existent --config reports clear error about path (not --repo)
- run_experiment() exception in single mode returns 1
- batch test missing task_repo returns error result dict
- --filter-subtest passed to reset_runs_for_from_state
- --filter-run passed to reset_runs_for_from_state
- --prompt override flows to ExperimentConfig
- --retry-errors in single mode resets failed runs via reset_runs_for_from_state
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from manage_experiment import MODEL_ALIASES, build_parser, cmd_repair, cmd_visualize

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
# --verbose / --quiet logging level
# ---------------------------------------------------------------------------


class TestVerboseQuietLogging:
    """Tests that --verbose/--quiet adjust the root logger level."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_verbose_sets_root_logger_to_debug(self, tmp_path: Path) -> None:
        """--verbose causes cmd_run to set root logger level to DEBUG."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--verbose",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        root_logger = logging.getLogger()
        original_level = root_logger.level
        try:
            with (
                patch("scylla.e2e.model_validation.validate_model", return_value=True),
                patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
            ):
                cmd_run(args)
            assert root_logger.level == logging.DEBUG
        finally:
            root_logger.setLevel(original_level)

    def test_quiet_sets_root_logger_to_error(self, tmp_path: Path) -> None:
        """--quiet causes cmd_run to set root logger level to ERROR."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--quiet",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        root_logger = logging.getLogger()
        original_level = root_logger.level
        try:
            with (
                patch("scylla.e2e.model_validation.validate_model", return_value=True),
                patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
            ):
                cmd_run(args)
            assert root_logger.level == logging.ERROR
        finally:
            root_logger.setLevel(original_level)


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


# ---------------------------------------------------------------------------
# --from with existing checkpoint (reset + resume)
# ---------------------------------------------------------------------------


class TestCmdRunFromWithCheckpoint:
    """Tests for cmd_run() --from with an existing checkpoint."""

    def _make_minimal_checkpoint(self, results_dir: Path, experiment_id: str) -> Path:
        """Create a minimal checkpoint using the timestamp-prefixed directory format."""
        exp_dir_name = f"2024-01-01T00-00-00-{experiment_id}"
        checkpoint_data = {
            "version": "3.1",
            "experiment_id": experiment_id,
            "experiment_dir": str(results_dir / exp_dir_name),
            "config_hash": "abc123",
            "started_at": "2024-01-01T00:00:00+00:00",
            "last_updated_at": "2024-01-01T00:00:00+00:00",
            "status": "interrupted",
            "run_states": {"T0": {"00": {"1": "replay_generated"}}},
            "completed_runs": {},
        }
        checkpoint_dir = results_dir / exp_dir_name
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data))
        return checkpoint_path

    def test_from_with_checkpoint_calls_reset_and_run(self, tmp_path: Path) -> None:
        """--from with existing checkpoint calls reset function and then run_experiment."""
        results_dir = tmp_path / "results"
        experiment_id = "test-exp"
        self._make_minimal_checkpoint(results_dir, experiment_id)

        # Create a minimal test dir (no test.yaml, so we need --repo/--commit)
        config_dir = tmp_path / "test-dir"
        config_dir.mkdir()

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--experiment-id",
                experiment_id,
                "--results-dir",
                str(results_dir),
                "--from",
                "replay_generated",
                "--filter-tier",
                "T0",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        reset_calls = []
        run_calls = []

        def mock_reset_runs(checkpoint, from_state, **kwargs):
            reset_calls.append(("runs", from_state, kwargs))
            return 1

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            run_calls.append((config, fresh))
            return {"T0": {}}  # truthy result

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch(
                "scylla.e2e.checkpoint.reset_runs_for_from_state",
                side_effect=mock_reset_runs,
            ),
            patch(
                "scylla.e2e.checkpoint.reset_tiers_for_from_state",
                return_value=0,
            ),
            patch(
                "scylla.e2e.checkpoint.reset_experiment_for_from_state",
                return_value=0,
            ),
            patch(
                "scylla.e2e.runner.run_experiment",
                side_effect=mock_run_experiment,
            ),
        ):
            result = cmd_run(args)

        assert result == 0
        # reset_runs_for_from_state was called with correct state and filters
        assert len(reset_calls) == 1
        assert reset_calls[0][1] == "replay_generated"
        assert reset_calls[0][2]["tier_filter"] == ["T0"]
        # run_experiment was called
        assert len(run_calls) == 1

    def test_from_tier_with_checkpoint_calls_tier_reset(self, tmp_path: Path) -> None:
        """--from-tier with existing checkpoint calls reset_tiers_for_from_state."""
        results_dir = tmp_path / "results"
        experiment_id = "test-exp"
        self._make_minimal_checkpoint(results_dir, experiment_id)

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir()

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--experiment-id",
                experiment_id,
                "--results-dir",
                str(results_dir),
                "--from-tier",
                "subtests_running",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        tier_reset_calls = []

        def mock_reset_tiers(checkpoint, from_state, **kwargs):
            tier_reset_calls.append(from_state)
            return 1

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch(
                "scylla.e2e.checkpoint.reset_runs_for_from_state",
                return_value=0,
            ),
            patch(
                "scylla.e2e.checkpoint.reset_tiers_for_from_state",
                side_effect=mock_reset_tiers,
            ),
            patch(
                "scylla.e2e.checkpoint.reset_experiment_for_from_state",
                return_value=0,
            ),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(tier_reset_calls) == 1
        assert tier_reset_calls[0] == "subtests_running"

    def test_from_tier_with_filter_tier_passes_filter(self, tmp_path: Path) -> None:
        """--from-tier with --filter-tier passes tier_filter kwarg to reset_tiers_for_from_state."""
        results_dir = tmp_path / "results"
        experiment_id = "test-exp"
        self._make_minimal_checkpoint(results_dir, experiment_id)

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir()

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--experiment-id",
                experiment_id,
                "--results-dir",
                str(results_dir),
                "--from-tier",
                "subtests_running",
                "--filter-tier",
                "T0",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        tier_reset_kwargs: list[dict[str, Any]] = []

        def mock_reset_tiers(checkpoint, from_state, **kwargs):
            tier_reset_kwargs.append(kwargs)
            return 1

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.checkpoint.reset_runs_for_from_state", return_value=0),
            patch(
                "scylla.e2e.checkpoint.reset_tiers_for_from_state",
                side_effect=mock_reset_tiers,
            ),
            patch("scylla.e2e.checkpoint.reset_experiment_for_from_state", return_value=0),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(tier_reset_kwargs) == 1
        assert tier_reset_kwargs[0]["tier_filter"] == ["T0"]

    def test_from_experiment_with_checkpoint_calls_experiment_reset(self, tmp_path: Path) -> None:
        """--from-experiment calls reset_experiment_for_from_state with the correct state."""
        results_dir = tmp_path / "results"
        experiment_id = "test-exp"
        self._make_minimal_checkpoint(results_dir, experiment_id)

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir()

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--experiment-id",
                experiment_id,
                "--results-dir",
                str(results_dir),
                "--from-experiment",
                "tiers_running",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        experiment_reset_calls: list[str] = []

        def mock_reset_experiment(checkpoint, from_state):
            experiment_reset_calls.append(from_state)
            return 1

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.checkpoint.reset_runs_for_from_state", return_value=0),
            patch("scylla.e2e.checkpoint.reset_tiers_for_from_state", return_value=0),
            patch(
                "scylla.e2e.checkpoint.reset_experiment_for_from_state",
                side_effect=mock_reset_experiment,
            ),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(experiment_reset_calls) == 1
        assert experiment_reset_calls[0] == "tiers_running"


# ---------------------------------------------------------------------------
# --from in batch mode
# ---------------------------------------------------------------------------


class TestCmdRunFromInBatchMode:
    """Tests that --from reset logic is applied per-test in batch mode."""

    def _make_checkpoint(self, results_dir: Path, experiment_id: str) -> Path:
        """Create a minimal checkpoint at the expected path."""
        checkpoint_data = {
            "version": "3.1",
            "experiment_id": experiment_id,
            "experiment_dir": str(results_dir / experiment_id),
            "config_hash": "abc123",
            "started_at": "2024-01-01T00:00:00+00:00",
            "last_updated_at": "2024-01-01T00:00:00+00:00",
            "status": "interrupted",
            "run_states": {"T0": {"00": {"1": "replay_generated"}}},
            "completed_runs": {},
        }
        checkpoint_dir = results_dir / experiment_id
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data))
        return checkpoint_path

    def test_from_in_batch_calls_reset_for_each_test(self, tmp_path: Path) -> None:
        """--from in batch mode calls checkpoint reset for each test that has a checkpoint."""
        import yaml

        # Create two test dirs with test.yaml and checkpoints
        results_dir = tmp_path / "results"
        for test_name in ["test-001", "test-002"]:
            test_dir = tmp_path / test_name
            test_dir.mkdir()
            # Use keys that run_one_test expects (task_repo/task_commit)
            test_yaml = {
                "task_repo": "https://github.com/test/repo",
                "task_commit": "abc123",
                "experiment_id": test_name,
                "timeout_seconds": 3600,
                "language": "python",
            }
            (test_dir / "test.yaml").write_text(yaml.dump(test_yaml))
            (test_dir / "prompt.md").write_text("test prompt")
            self._make_checkpoint(results_dir, test_name)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--from",
                "replay_generated",
                "--results-dir",
                str(results_dir),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        reset_calls: list[str] = []

        def mock_reset_runs(checkpoint, from_state, **kwargs):
            reset_calls.append(from_state)
            return 1

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch(
                "scylla.e2e.checkpoint.reset_runs_for_from_state",
                side_effect=mock_reset_runs,
            ),
            patch(
                "scylla.e2e.checkpoint.reset_tiers_for_from_state",
                return_value=0,
            ),
            patch(
                "scylla.e2e.checkpoint.reset_experiment_for_from_state",
                return_value=0,
            ),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        # reset was called once per test that has a checkpoint
        assert len(reset_calls) == 2
        assert all(s == "replay_generated" for s in reset_calls)

    def test_invalid_from_in_batch_returns_1_early(self, tmp_path: Path) -> None:
        """Invalid --from value in batch mode returns 1 before spawning any threads.

        Early validation catches the invalid state and returns 1 immediately. No
        batch_summary.json is written because no tests are executed.
        """
        import yaml

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Two configs required to trigger batch mode (multiple --config paths)
        for test_name in ["test-001", "test-002"]:
            test_dir = tmp_path / test_name
            test_dir.mkdir()
            test_yaml = {
                "task_repo": "https://github.com/test/repo",
                "task_commit": "abc123",
                "experiment_id": test_name,
                "timeout_seconds": 3600,
                "language": "python",
            }
            (test_dir / "test.yaml").write_text(yaml.dump(test_yaml))
            (test_dir / "prompt.md").write_text("test prompt")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--from",
                "not_a_valid_state",
                "--results-dir",
                str(results_dir),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.runner.run_experiment") as mock_run:
            result = cmd_run(args)

        assert result == 1
        # Early validation returns before spawning threads — no tests run
        mock_run.assert_not_called()
        # No batch_summary.json is written
        assert not (results_dir / "batch_summary.json").exists()


# ---------------------------------------------------------------------------
# --add-judge dedup logic
# ---------------------------------------------------------------------------


class TestAddJudgeDedup:
    """Tests for --add-judge deduplication."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_add_judge_duplicate_not_added_twice(self, tmp_path: Path) -> None:
        """--add-judge with a duplicate model ID does not add it twice."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        # --judge-model sonnet + --add-judge sonnet → should dedup to a single sonnet entry
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--judge-model",
                "sonnet",
                "--add-judge",
                "sonnet",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            cmd_run(args)

        assert len(captured_configs) == 1
        # judge_models should contain exactly one entry (deduped)
        sonnet_id = "claude-sonnet-4-5-20250929"
        assert captured_configs[0].judge_models == [sonnet_id]

    def test_add_judge_different_model_appended(self, tmp_path: Path) -> None:
        """--add-judge with a different model is appended to judge_models."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--judge-model",
                "sonnet",
                "--add-judge",
                "opus",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            cmd_run(args)

        assert len(captured_configs) == 1
        sonnet_id = "claude-sonnet-4-5-20250929"
        opus_id = "claude-opus-4-5-20251101"
        assert captured_configs[0].judge_models == [sonnet_id, opus_id]

    def test_add_judge_bare_flag_defaults_to_sonnet(self, tmp_path: Path) -> None:
        """--add-judge with no value uses const='sonnet'; deduped against default judge-model."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        # --add-judge with no value: argparse uses const="sonnet"
        # --judge-model defaults to "sonnet", so the result deduplicates to one sonnet entry
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--add-judge",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            cmd_run(args)

        assert len(captured_configs) == 1
        sonnet_id = "claude-sonnet-4-5-20250929"
        assert captured_configs[0].judge_models == [sonnet_id]


# ---------------------------------------------------------------------------
# YAML config file mode
# ---------------------------------------------------------------------------


class TestYamlConfigFileMode:
    """Tests for single .yaml file as --config argument."""

    def test_yaml_file_config_is_loaded_and_merged(self, tmp_path: Path) -> None:
        """A single .yaml file as --config is loaded and merged into config."""
        import yaml

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir()
        # Create a prompt.md so single-test path doesn't fail early
        (config_dir / "prompt.md").write_text("test prompt")
        yaml_path = config_dir / "override.yaml"
        yaml_path.write_text(
            yaml.dump(
                {
                    "task_repo": "https://github.com/yaml/repo",
                    "task_commit": "yaml_commit",
                    "experiment_id": "yaml-exp",
                }
            )
        )

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(yaml_path),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 1
        assert captured_configs[0].task_repo == "https://github.com/yaml/repo"
        assert captured_configs[0].task_commit == "yaml_commit"
        assert captured_configs[0].experiment_id == "yaml-exp"

    def test_yaml_config_overrides_test_yaml_values(self, tmp_path: Path) -> None:
        """A --config .yaml file's values override those from test.yaml in the same dir."""
        import yaml

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir()
        # test.yaml has experiment_id="from-test"
        (config_dir / "test.yaml").write_text(
            yaml.dump(
                {
                    "task_repo": "https://github.com/test/repo",
                    "task_commit": "abc123",
                    "experiment_id": "from-test",
                    "timeout_seconds": 3600,
                    "language": "python",
                }
            )
        )
        (config_dir / "prompt.md").write_text("test prompt")
        # override.yaml has experiment_id="from-override"
        override_yaml = config_dir / "override.yaml"
        override_yaml.write_text(
            yaml.dump(
                {
                    "task_repo": "https://github.com/override/repo",
                    "task_commit": "override_commit",
                    "experiment_id": "from-override",
                }
            )
        )

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(override_yaml),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 1
        assert captured_configs[0].experiment_id == "from-override"


# ---------------------------------------------------------------------------
# test-config-loader exclusion in batch discovery
# ---------------------------------------------------------------------------


class TestTestConfigLoaderExclusion:
    """Tests that test-config-loader is excluded from batch auto-discovery."""

    def test_test_config_loader_excluded_from_batch(self, tmp_path: Path) -> None:
        """test-config-loader dir is excluded from batch auto-discovery."""
        # Create test-* dirs including test-config-loader
        (tmp_path / "test-001").mkdir()
        (tmp_path / "test-002").mkdir()
        (tmp_path / "test-config-loader").mkdir()

        from manage_experiment import cmd_run

        call_args = []

        def mock_run_batch(test_dirs, passed_args):
            call_args.append(list(test_dirs))
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
        discovered_names = {d.name for d in call_args[0]}
        assert "test-config-loader" not in discovered_names
        assert "test-001" in discovered_names
        assert "test-002" in discovered_names


# ---------------------------------------------------------------------------
# --filter-judge-slot has no effect (not-yet-implemented)
# ---------------------------------------------------------------------------


class TestFilterJudgeSlotNoEffect:
    """Tests that --filter-judge-slot is accepted but does not affect behavior."""

    def test_filter_judge_slot_stored_on_config_but_not_passed_to_reset(
        self, tmp_path: Path
    ) -> None:
        """--filter-judge-slot is stored on ExperimentConfig but not passed to reset functions."""
        import yaml

        results_dir = tmp_path / "results"
        experiment_id = "test-exp"

        # Create checkpoint using timestamp-prefixed directory format
        exp_dir_name = f"2024-01-01T00-00-00-{experiment_id}"
        checkpoint_data = {
            "version": "3.1",
            "experiment_id": experiment_id,
            "experiment_dir": str(results_dir / exp_dir_name),
            "config_hash": "abc123",
            "started_at": "2024-01-01T00:00:00+00:00",
            "last_updated_at": "2024-01-01T00:00:00+00:00",
            "status": "interrupted",
            "run_states": {"T0": {"00": {"1": "judge_pipeline_run"}}},
            "completed_runs": {},
        }
        checkpoint_dir = results_dir / exp_dir_name
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        (checkpoint_dir / "checkpoint.json").write_text(json.dumps(checkpoint_data))

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir()
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": experiment_id,
            "timeout_seconds": 3600,
            "language": "python",
        }
        (config_dir / "test.yaml").write_text(yaml.dump(test_yaml))
        (config_dir / "prompt.md").write_text("test prompt")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--results-dir",
                str(results_dir),
                "--from",
                "judge_pipeline_run",
                "--filter-judge-slot",
                "1",
                "--filter-judge-slot",
                "2",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        reset_kwargs_captured: list[dict[str, Any]] = []

        def mock_reset_runs(checkpoint, from_state, **kwargs):
            reset_kwargs_captured.append(kwargs)
            return 0

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch(
                "scylla.e2e.checkpoint.reset_runs_for_from_state",
                side_effect=mock_reset_runs,
            ),
            patch(
                "scylla.e2e.checkpoint.reset_tiers_for_from_state",
                return_value=0,
            ),
            patch(
                "scylla.e2e.checkpoint.reset_experiment_for_from_state",
                return_value=0,
            ),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        # --filter-judge-slot is NOT passed to reset_runs_for_from_state
        assert len(reset_kwargs_captured) == 1
        assert "judge_slot_filter" not in reset_kwargs_captured[0]


# ---------------------------------------------------------------------------
# Non-existent --config path in single mode
# ---------------------------------------------------------------------------


class TestNonExistentConfigPath:
    """Tests for error behavior when --config path doesn't exist in single mode."""

    def test_nonexistent_config_single_mode_returns_1(self, tmp_path: Path) -> None:
        """cmd_run returns 1 when run_experiment returns falsy for a non-existent config.

        A non-existent path is not a parent dir with test-* subdirs, so it falls
        through to single-test mode. run_experiment is called with the non-existent
        tiers_dir. When run_experiment returns falsy (None), cmd_run returns 1.
        """
        nonexistent = tmp_path / "does-not-exist"

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(nonexistent),
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            # run_experiment returns None (falsy) → cmd_run returns 1
            patch("scylla.e2e.runner.run_experiment", return_value=None),
        ):
            result = cmd_run(args)

        assert result == 1


# ---------------------------------------------------------------------------
# --fresh flag forwarding
# ---------------------------------------------------------------------------


class TestFreshFlag:
    """Tests that --fresh is forwarded to run_experiment."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_fresh_flag_forwarded_to_run_experiment(self, tmp_path: Path) -> None:
        """--fresh is passed as fresh=True to run_experiment."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--fresh",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_fresh: list[bool] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_fresh.append(fresh)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_fresh) == 1
        assert captured_fresh[0] is True

    def test_no_fresh_flag_passes_false(self, tmp_path: Path) -> None:
        """Omitting --fresh passes fresh=False to run_experiment."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_fresh: list[bool] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_fresh.append(fresh)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_fresh) == 1
        assert captured_fresh[0] is False


# ---------------------------------------------------------------------------
# --until* valid values flow to ExperimentConfig
# ---------------------------------------------------------------------------


class TestUntilStateFlowsToConfig:
    """Tests that valid --until* values are converted and stored in ExperimentConfig."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_until_run_state_flows_to_config(self, tmp_path: Path) -> None:
        """--until agent_complete sets config.until_run_state == RunState.AGENT_COMPLETE."""
        from scylla.e2e.models import RunState

        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--until",
                "agent_complete",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 1
        assert captured_configs[0].until_run_state == RunState.AGENT_COMPLETE

    def test_until_tier_state_flows_to_config(self, tmp_path: Path) -> None:
        """--until-tier subtests_complete sets config.until_tier_state to SUBTESTS_COMPLETE."""
        from scylla.e2e.models import TierState

        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--until-tier",
                "subtests_complete",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 1
        assert captured_configs[0].until_tier_state == TierState.SUBTESTS_COMPLETE

    def test_until_experiment_state_flows_to_config(self, tmp_path: Path) -> None:
        """--until-experiment tiers_running sets config.until_experiment_state to TIERS_RUNNING."""
        from scylla.e2e.models import ExperimentState

        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--until-experiment",
                "tiers_running",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 1
        assert captured_configs[0].until_experiment_state == ExperimentState.TIERS_RUNNING


# ---------------------------------------------------------------------------
# batch --from without checkpoint: warns and runs fresh
# ---------------------------------------------------------------------------


class TestBatchFromMissingCheckpoint:
    """Tests batch --from behavior when no checkpoint exists for a test."""

    def test_from_without_checkpoint_warns_and_runs_fresh(self, tmp_path: Path) -> None:
        """--from in batch mode with no checkpoint logs warning and still calls run_experiment."""
        import yaml

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Two test dirs with test.yaml but NO checkpoints
        for test_name in ["test-001", "test-002"]:
            test_dir = tmp_path / test_name
            test_dir.mkdir()
            test_yaml = {
                "task_repo": "https://github.com/test/repo",
                "task_commit": "abc123",
                "experiment_id": test_name,
                "timeout_seconds": 3600,
                "language": "python",
            }
            (test_dir / "test.yaml").write_text(yaml.dump(test_yaml))
            (test_dir / "prompt.md").write_text("test prompt")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--from",
                "replay_generated",
                "--results-dir",
                str(results_dir),
                "--threads",
                "1",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        run_experiment_calls: list[str] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            run_experiment_calls.append(config.experiment_id)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        # Returns 0 (not 1) because run_experiment succeeded for both
        assert result == 0
        # run_experiment was called for both tests despite missing checkpoints
        assert len(run_experiment_calls) == 2


# ---------------------------------------------------------------------------
# --tests filter limits batch execution
# ---------------------------------------------------------------------------


class TestBatchTestsFilter:
    """Tests that --tests filters which tests are run in batch mode."""

    def test_tests_filter_limits_batch_to_specified_ids(self, tmp_path: Path) -> None:
        """--tests test-001 test-003 runs only those two, skipping test-002."""
        import yaml

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Three test dirs
        for test_name in ["test-001", "test-002", "test-003"]:
            test_dir = tmp_path / test_name
            test_dir.mkdir()
            test_yaml = {
                "task_repo": "https://github.com/test/repo",
                "task_commit": "abc123",
                "experiment_id": test_name,
                "timeout_seconds": 3600,
                "language": "python",
            }
            (test_dir / "test.yaml").write_text(yaml.dump(test_yaml))
            (test_dir / "prompt.md").write_text("test prompt")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--config",
                str(tmp_path / "test-003"),
                "--tests",
                "test-001",
                "test-003",
                "--results-dir",
                str(results_dir),
                "--threads",
                "1",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        executed_ids: list[str] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            executed_ids.append(config.experiment_id)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(executed_ids) == 2
        assert "test-001" in executed_ids
        assert "test-003" in executed_ids
        assert "test-002" not in executed_ids


# ---------------------------------------------------------------------------
# --retry-errors behavioral logic
# ---------------------------------------------------------------------------


class TestRetryErrorsInBatch:
    """Tests that --retry-errors reruns only failed tests."""

    def _make_test_dir_with_yaml(self, path: Path, test_name: str) -> None:
        """Create a test dir with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": test_name,
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_retry_errors_reruns_failed_tests(self, tmp_path: Path) -> None:
        """--retry-errors reruns test-001 (error) but skips test-002 (success)."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Pre-populate batch_summary.json: test-001=error, test-002=success
        summary = {
            "results": [
                {"test_id": "test-001", "status": "error", "error": "some error"},
                {"test_id": "test-002", "status": "success"},
            ]
        }
        (results_dir / "batch_summary.json").write_text(json.dumps(summary))

        for test_name in ["test-001", "test-002"]:
            self._make_test_dir_with_yaml(tmp_path / test_name, test_name)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--retry-errors",
                "--results-dir",
                str(results_dir),
                "--threads",
                "1",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        executed_ids: list[str] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            executed_ids.append(config.experiment_id)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        # Only test-001 (the errored one) was re-run
        assert executed_ids == ["test-001"]

    def test_without_retry_errors_skips_all_completed(self, tmp_path: Path) -> None:
        """Without --retry-errors, both success and error tests are skipped."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Pre-populate batch_summary.json: test-001=error, test-002=success
        summary = {
            "results": [
                {"test_id": "test-001", "status": "error", "error": "some error"},
                {"test_id": "test-002", "status": "success"},
            ]
        }
        (results_dir / "batch_summary.json").write_text(json.dumps(summary))

        for test_name in ["test-001", "test-002"]:
            self._make_test_dir_with_yaml(tmp_path / test_name, test_name)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--results-dir",
                str(results_dir),
                "--threads",
                "1",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        executed_ids: list[str] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            executed_ids.append(config.experiment_id)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        # No tests were re-run (all previously completed)
        assert executed_ids == []


# ---------------------------------------------------------------------------
# --add-judge in batch mode (bug fix validation)
# ---------------------------------------------------------------------------


class TestAddJudgeBatchMode:
    """Tests that --add-judge is applied correctly in batch mode."""

    def _make_test_dir_with_yaml(self, path: Path, test_name: str) -> None:
        """Create a test dir with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": test_name,
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_add_judge_in_batch_mode_appends_to_judge_models(self, tmp_path: Path) -> None:
        """In batch mode, --add-judge opus with --judge-model sonnet yields both in judge_models."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        for test_name in ["test-001", "test-002"]:
            self._make_test_dir_with_yaml(tmp_path / test_name, test_name)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--judge-model",
                "sonnet",
                "--add-judge",
                "opus",
                "--results-dir",
                str(results_dir),
                "--threads",
                "1",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured_configs: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 2
        sonnet_id = "claude-sonnet-4-5-20250929"
        opus_id = "claude-opus-4-5-20251101"
        # Both batch configs should have both judge models
        for config in captured_configs:
            assert config.judge_models == [sonnet_id, opus_id]


# ---------------------------------------------------------------------------
# --from + --filter-status failed (bug fix validation)
# ---------------------------------------------------------------------------


class TestFromWithFilterStatusFailed:
    """Tests that --from + --filter-status failed resets failed runs."""

    def test_from_with_filter_status_failed_resets_failed_runs(self) -> None:
        """--from replay_generated + --filter-status failed resets a run in 'failed' state."""
        from datetime import datetime, timezone

        from scylla.e2e.checkpoint import E2ECheckpoint, reset_runs_for_from_state

        cp = E2ECheckpoint(
            experiment_id="test-exp",
            experiment_dir="/tmp/test-exp",
            config_hash="abc123",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "failed"}}},
            completed_runs={"T0": {"00": {1: "failed"}}},
        )

        count = reset_runs_for_from_state(cp, "replay_generated", status_filter=["failed"])

        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "pending"

    def test_from_without_filter_status_leaves_failed_run_alone(self) -> None:
        """Without --filter-status, a 'failed' run is NOT reset (preserves existing behavior)."""
        from datetime import datetime, timezone

        from scylla.e2e.checkpoint import E2ECheckpoint, reset_runs_for_from_state

        cp = E2ECheckpoint(
            experiment_id="test-exp",
            experiment_dir="/tmp/test-exp",
            config_hash="abc123",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "failed"}}},
            completed_runs={"T0": {"00": {1: "failed"}}},
        )

        count = reset_runs_for_from_state(cp, "replay_generated")

        assert count == 0
        assert cp.run_states["T0"]["00"]["1"] == "failed"


# ---------------------------------------------------------------------------
# --parallel-high / --parallel-med / --parallel-low flow to ExperimentConfig
# ---------------------------------------------------------------------------


class TestParallelSemaphoreFlowsToConfig:
    """Tests that parallel semaphore args flow through to ExperimentConfig."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def _run_and_capture(self, args) -> Any:
        """Run cmd_run with args and return captured ExperimentConfig."""
        from manage_experiment import cmd_run

        captured: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            cmd_run(args)

        return captured[0]

    def test_parallel_high_flows_to_config(self, tmp_path: Path) -> None:
        """--parallel-high 3 is stored in ExperimentConfig.parallel_high."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--parallel-high",
                "3",
                "--skip-judge-validation",
            ]
        )
        config = self._run_and_capture(args)
        assert config.parallel_high == 3

    def test_parallel_med_flows_to_config(self, tmp_path: Path) -> None:
        """--parallel-med 5 is stored in ExperimentConfig.parallel_med."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--parallel-med",
                "5",
                "--skip-judge-validation",
            ]
        )
        config = self._run_and_capture(args)
        assert config.parallel_med == 5

    def test_parallel_low_flows_to_config(self, tmp_path: Path) -> None:
        """--parallel-low 10 is stored in ExperimentConfig.parallel_low."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--parallel-low",
                "10",
                "--skip-judge-validation",
            ]
        )
        config = self._run_and_capture(args)
        assert config.parallel_low == 10


# ---------------------------------------------------------------------------
# Model alias resolution
# ---------------------------------------------------------------------------


class TestModelAliasResolution:
    """Tests that model/judge alias names resolve to full model IDs."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_model_opus_resolves_to_full_id(self, tmp_path: Path) -> None:
        """--model opus resolves to full opus model ID in ExperimentConfig.models."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--model",
                "opus",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            cmd_run(args)

        opus_id = "claude-opus-4-5-20251101"
        assert captured[0].models == [opus_id]

    def test_judge_model_haiku_resolves_to_full_id(self, tmp_path: Path) -> None:
        """--judge-model haiku resolves to full haiku ID in ExperimentConfig.judge_models."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--judge-model",
                "haiku",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            cmd_run(args)

        haiku_id = "claude-haiku-4-5-20251001"
        assert haiku_id in captured[0].judge_models


# ---------------------------------------------------------------------------
# Unknown tier name
# ---------------------------------------------------------------------------


class TestUnknownTierReturnsError:
    """Tests that an unknown tier name in --tiers returns exit code 1."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_unknown_tier_returns_1(self, tmp_path: Path) -> None:
        """--tiers TX (unknown tier) returns exit code 1."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--tiers",
                "TX",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)

        assert result == 1


# ---------------------------------------------------------------------------
# Judge validation behavior
# ---------------------------------------------------------------------------


class TestJudgeValidationBehavior:
    """Tests for --skip-judge-validation flag behavior."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_skip_judge_validation_skips_validate_model(self, tmp_path: Path) -> None:
        """With --skip-judge-validation, validate_model is never called."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True) as mock_validate,
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            cmd_run(args)

        mock_validate.assert_not_called()

    def test_without_skip_validation_calls_validate_model(self, tmp_path: Path) -> None:
        """Without --skip-judge-validation, validate_model is called for each judge model."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
            ]
        )

        from manage_experiment import cmd_run

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True) as mock_validate,
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            cmd_run(args)

        mock_validate.assert_called()


# ---------------------------------------------------------------------------
# --timeout override
# ---------------------------------------------------------------------------


class TestTimeoutOverride:
    """Tests that --timeout overrides the test.yaml timeout_seconds value."""

    def test_timeout_overrides_test_yaml(self, tmp_path: Path) -> None:
        """--timeout 7200 overrides test.yaml timeout_seconds=1800 in ExperimentConfig."""
        import yaml

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 1800,
            "language": "python",
        }
        (config_dir / "test.yaml").write_text(yaml.dump(test_yaml))
        (config_dir / "prompt.md").write_text("test prompt")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--timeout",
                "7200",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            cmd_run(args)

        assert captured[0].timeout_seconds == 7200


# ---------------------------------------------------------------------------
# --thinking mode flow to ExperimentConfig
# ---------------------------------------------------------------------------


class TestThinkingModeFlowsToConfig:
    """Tests that --thinking mode value flows to ExperimentConfig."""

    def test_thinking_high_flows_to_config(self, tmp_path: Path) -> None:
        """--thinking High sets ExperimentConfig.thinking_mode to 'High'."""
        import yaml

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (config_dir / "test.yaml").write_text(yaml.dump(test_yaml))
        (config_dir / "prompt.md").write_text("test prompt")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--thinking",
                "High",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            cmd_run(args)

        assert captured[0].thinking_mode == "High"


# ---------------------------------------------------------------------------
# --timeout defaults to test.yaml when not specified on CLI (bug fix)
# ---------------------------------------------------------------------------


class TestTimeoutFallbackToTestYaml:
    """Tests that --timeout defaults to test.yaml timeout_seconds when not given on CLI."""

    def test_timeout_defaults_to_test_yaml_when_not_specified(self, tmp_path: Path) -> None:
        """No --timeout on CLI: ExperimentConfig.timeout_seconds comes from test.yaml."""
        import yaml

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 7200,
            "language": "python",
        }
        (config_dir / "test.yaml").write_text(yaml.dump(test_yaml))
        (config_dir / "prompt.md").write_text("test prompt")

        parser = build_parser()
        # No --timeout on CLI
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--skip-judge-validation",
            ]
        )
        assert args.timeout is None  # verify default is None

        from manage_experiment import cmd_run

        captured: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert captured[0].timeout_seconds == 7200


# ---------------------------------------------------------------------------
# MODEL_ALIASES module-level constant
# ---------------------------------------------------------------------------


class TestModelAliasConstant:
    """Tests for MODEL_ALIASES module-level constant."""

    def test_model_aliases_has_expected_keys(self) -> None:
        """MODEL_ALIASES is a module-level dict with sonnet, opus, and haiku keys."""
        assert isinstance(MODEL_ALIASES, dict)
        assert "sonnet" in MODEL_ALIASES
        assert "opus" in MODEL_ALIASES
        assert "haiku" in MODEL_ALIASES

    def test_model_aliases_values_are_full_model_ids(self) -> None:
        """MODEL_ALIASES values contain full versioned model IDs."""
        assert MODEL_ALIASES["sonnet"] == "claude-sonnet-4-5-20250929"
        assert MODEL_ALIASES["opus"] == "claude-opus-4-5-20251101"
        assert MODEL_ALIASES["haiku"] == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Batch early validation (--tiers / --from before spawning threads)
# ---------------------------------------------------------------------------


class TestBatchEarlyValidation:
    """Tests that invalid global args in batch mode fail fast before any tests run."""

    def _make_test_dir_with_yaml(self, path: Path, test_name: str) -> None:
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        (path / "test.yaml").write_text(
            yaml.dump(
                {
                    "task_repo": "https://github.com/test/repo",
                    "task_commit": "abc123",
                    "experiment_id": test_name,
                    "timeout_seconds": 3600,
                    "language": "python",
                }
            )
        )
        (path / "prompt.md").write_text("test prompt")

    def test_invalid_tiers_in_batch_returns_1_before_running(self, tmp_path: Path) -> None:
        """--tiers TX in batch mode returns 1 before run_experiment is called."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        for test_name in ["test-001", "test-002"]:
            self._make_test_dir_with_yaml(tmp_path / test_name, test_name)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--tiers",
                "TX",
                "--results-dir",
                str(results_dir),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.runner.run_experiment") as mock_run:
            result = cmd_run(args)

        assert result == 1
        mock_run.assert_not_called()

    def test_invalid_from_in_batch_returns_1_before_running(self, tmp_path: Path) -> None:
        """--from bogus_state in batch mode returns 1 before run_experiment is called."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        for test_name in ["test-001", "test-002"]:
            self._make_test_dir_with_yaml(tmp_path / test_name, test_name)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path / "test-001"),
                "--config",
                str(tmp_path / "test-002"),
                "--from",
                "bogus_state_xyz",
                "--results-dir",
                str(results_dir),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.runner.run_experiment") as mock_run:
            result = cmd_run(args)

        assert result == 1
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# --config existence check
# ---------------------------------------------------------------------------


class TestConfigPathExistence:
    """Tests that a non-existent --config path gives a clear error message."""

    def test_nonexistent_config_reports_clear_error(self, tmp_path: Path, caplog) -> None:
        """--config /nonexistent/path returns 1 and error message mentions the path."""
        import logging

        nonexistent = tmp_path / "does-not-exist-at-all"

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(nonexistent),
                "--repo",
                "https://github.com/test/repo",
                "--commit",
                "abc123",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            caplog.at_level(logging.ERROR),
        ):
            result = cmd_run(args)

        assert result == 1
        # Error message should reference the path, not "--repo is required"
        error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any(str(nonexistent) in msg for msg in error_messages), (
            f"Expected path in error messages, got: {error_messages}"
        )
        assert not any("--repo is required" in msg for msg in error_messages), (
            f"Got misleading --repo error: {error_messages}"
        )


# ---------------------------------------------------------------------------
# Single-mode run_experiment() exception handling
# ---------------------------------------------------------------------------


class TestSingleModeExceptionHandling:
    """Tests that exceptions from run_experiment() in single mode return 1 cleanly."""

    def test_run_experiment_exception_returns_1(self, tmp_path: Path) -> None:
        """run_experiment() raising RuntimeError returns 1 without propagating exception."""
        import yaml

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "test.yaml").write_text(
            yaml.dump(
                {
                    "task_repo": "https://github.com/test/repo",
                    "task_commit": "abc123",
                    "experiment_id": "test-exp",
                    "timeout_seconds": 3600,
                    "language": "python",
                }
            )
        )
        (config_dir / "prompt.md").write_text("test prompt")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch(
                "scylla.e2e.runner.run_experiment",
                side_effect=RuntimeError("simulated failure"),
            ),
        ):
            result = cmd_run(args)

        assert result == 1  # exception converted to exit code 1


# ---------------------------------------------------------------------------
# Batch test missing task_repo returns error result
# ---------------------------------------------------------------------------


class TestBatchMissingTaskRepo:
    """Tests that a batch test with no task_repo and no --repo returns an error result."""

    def test_batch_test_missing_repo_returns_error_result(self, tmp_path: Path) -> None:
        """test.yaml with no task_repo and no CLI --repo causes batch to return exit code 1.

        The missing-repo check returns early from run_one_test() before save_result() is called,
        so the result dict is not persisted to batch_summary.json. The thread pool receives the
        dict and increments failed_count, causing the batch to return 1.
        """
        import yaml

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # test.yaml with task_repo intentionally missing
        test_dir = tmp_path / "test-001"
        test_dir.mkdir()
        (test_dir / "test.yaml").write_text(
            yaml.dump(
                {
                    "task_commit": "abc123",
                    "experiment_id": "test-001",
                    "timeout_seconds": 3600,
                    "language": "python",
                    # task_repo intentionally absent
                }
            )
        )
        (test_dir / "prompt.md").write_text("test prompt")

        # Need a second config to trigger batch mode (multiple --config)
        test_dir2 = tmp_path / "test-002"
        test_dir2.mkdir()
        (test_dir2 / "test.yaml").write_text(
            yaml.dump(
                {
                    "task_repo": "https://github.com/test/repo",
                    "task_commit": "abc123",
                    "experiment_id": "test-002",
                    "timeout_seconds": 3600,
                    "language": "python",
                }
            )
        )
        (test_dir2 / "prompt.md").write_text("test prompt")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(test_dir),
                "--config",
                str(test_dir2),
                "--results-dir",
                str(results_dir),
                "--threads",
                "1",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        # test-001 fails (missing repo), test-002 succeeds → batch returns 1
        assert result == 1


# ---------------------------------------------------------------------------
# --filter-subtest and --filter-run wiring to reset functions
# ---------------------------------------------------------------------------


class TestFilterSubtestAndRunWiring:
    """Tests that --filter-subtest and --filter-run are passed to reset_runs_for_from_state."""

    def _make_minimal_checkpoint(self, results_dir: Path, experiment_id: str) -> None:
        exp_dir_name = f"2024-01-01T00-00-00-{experiment_id}"
        checkpoint_data = {
            "version": "3.1",
            "experiment_id": experiment_id,
            "experiment_dir": str(results_dir / exp_dir_name),
            "config_hash": "abc123",
            "started_at": "2024-01-01T00:00:00+00:00",
            "last_updated_at": "2024-01-01T00:00:00+00:00",
            "status": "interrupted",
            "run_states": {"T0": {"00": {"1": "replay_generated"}}},
            "completed_runs": {},
        }
        checkpoint_dir = results_dir / exp_dir_name
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        (checkpoint_dir / "checkpoint.json").write_text(json.dumps(checkpoint_data))

    def _make_test_dir(self, path: Path, experiment_id: str) -> None:
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        (path / "test.yaml").write_text(
            yaml.dump(
                {
                    "task_repo": "https://github.com/test/repo",
                    "task_commit": "abc123",
                    "experiment_id": experiment_id,
                    "timeout_seconds": 3600,
                    "language": "python",
                }
            )
        )
        (path / "prompt.md").write_text("test prompt")

    def test_filter_subtest_passed_to_reset_function(self, tmp_path: Path) -> None:
        """--from replay_generated --filter-subtest 00 calls reset with subtest_filter=['00']."""
        results_dir = tmp_path / "results"
        experiment_id = "test-exp"
        self._make_minimal_checkpoint(results_dir, experiment_id)
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir, experiment_id)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--results-dir",
                str(results_dir),
                "--from",
                "replay_generated",
                "--filter-subtest",
                "00",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        reset_kwargs: list[dict[str, Any]] = []

        def mock_reset_runs(checkpoint, from_state, **kwargs):
            reset_kwargs.append(kwargs)
            return 1

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.checkpoint.reset_runs_for_from_state", side_effect=mock_reset_runs),
            patch("scylla.e2e.checkpoint.reset_tiers_for_from_state", return_value=0),
            patch("scylla.e2e.checkpoint.reset_experiment_for_from_state", return_value=0),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(reset_kwargs) == 1
        assert reset_kwargs[0]["subtest_filter"] == ["00"]

    def test_filter_run_passed_to_reset_function(self, tmp_path: Path) -> None:
        """--from replay_generated --filter-run 1 calls reset with run_filter=[1]."""
        results_dir = tmp_path / "results"
        experiment_id = "test-exp"
        self._make_minimal_checkpoint(results_dir, experiment_id)
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir, experiment_id)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--results-dir",
                str(results_dir),
                "--from",
                "replay_generated",
                "--filter-run",
                "1",
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        reset_kwargs: list[dict[str, Any]] = []

        def mock_reset_runs(checkpoint, from_state, **kwargs):
            reset_kwargs.append(kwargs)
            return 1

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.checkpoint.reset_runs_for_from_state", side_effect=mock_reset_runs),
            patch("scylla.e2e.checkpoint.reset_tiers_for_from_state", return_value=0),
            patch("scylla.e2e.checkpoint.reset_experiment_for_from_state", return_value=0),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(reset_kwargs) == 1
        assert reset_kwargs[0]["run_filter"] == [1]


# ---------------------------------------------------------------------------
# --prompt override flows to ExperimentConfig
# ---------------------------------------------------------------------------


class TestPromptOverride:
    """Tests that --prompt overrides the test.yaml task_prompt_file value."""

    def test_prompt_flag_overrides_test_yaml(self, tmp_path: Path) -> None:
        """--prompt /custom/prompt.md sets config.task_prompt_file to that path."""
        import yaml

        config_dir = tmp_path / "test-dir"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "test.yaml").write_text(
            yaml.dump(
                {
                    "task_repo": "https://github.com/test/repo",
                    "task_commit": "abc123",
                    "experiment_id": "test-exp",
                    "task_prompt_file": "prompt.md",
                    "timeout_seconds": 3600,
                    "language": "python",
                }
            )
        )
        (config_dir / "prompt.md").write_text("default prompt")

        custom_prompt = tmp_path / "custom_prompt.md"
        custom_prompt.write_text("custom prompt content")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--prompt",
                str(custom_prompt),
                "--skip-judge-validation",
            ]
        )

        from manage_experiment import cmd_run

        captured: list[Any] = []

        def mock_run_experiment(config, tiers_dir, results_dir, fresh):
            captured.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert captured[0].task_prompt_file == custom_prompt


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


# ---------------------------------------------------------------------------
# --retry-errors in single mode
# ---------------------------------------------------------------------------


class TestRetryErrorsInSingleMode:
    """Tests that --retry-errors in single mode resets failed runs via reset_runs_for_from_state."""

    def _make_test_dir(self, path: Path) -> None:
        """Create a minimal test directory with test.yaml and prompt.md."""
        import yaml

        path.mkdir(parents=True, exist_ok=True)
        test_yaml = {
            "task_repo": "https://github.com/test/repo",
            "task_commit": "abc123",
            "experiment_id": "test-exp",
            "timeout_seconds": 3600,
            "language": "python",
        }
        (path / "test.yaml").write_text(yaml.dump(test_yaml))
        (path / "prompt.md").write_text("test prompt")

    def test_retry_errors_single_mode_calls_reset_for_failed_runs(self, tmp_path: Path) -> None:
        """--retry-errors single mode calls reset_runs_for_from_state with status_filter=failed."""
        from datetime import datetime, timezone

        from manage_experiment import cmd_run

        from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint

        config_dir = tmp_path / "test-exp"
        self._make_test_dir(config_dir)

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create an existing checkpoint with a failed run (timestamp-prefixed dir)
        exp_dir = results_dir / "2024-01-01T00-00-00-test-exp"
        exp_dir.mkdir(parents=True)
        checkpoint = E2ECheckpoint(
            experiment_id="test-exp",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="failed",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="failed",
            run_states={"T0": {"00": {"1": "failed"}}},
            completed_runs={"T0": {"00": {1: "failed"}}},
        )
        checkpoint_path = exp_dir / "checkpoint.json"
        save_checkpoint(checkpoint, checkpoint_path)

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--results-dir",
                str(results_dir),
                "--retry-errors",
                "--skip-judge-validation",
            ]
        )

        reset_calls: list[Any] = []

        def mock_reset(cp, from_state, **kwargs):
            reset_calls.append({"from_state": from_state, "kwargs": kwargs})
            return 1

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
            patch(
                "scylla.e2e.checkpoint.reset_runs_for_from_state",
                side_effect=mock_reset,
            ),
        ):
            result = cmd_run(args)

        assert result == 0
        # Verify reset_runs_for_from_state was called with status_filter=["failed"]
        assert len(reset_calls) == 1
        assert reset_calls[0]["kwargs"].get("status_filter") == ["failed"]

    def test_retry_errors_single_mode_no_existing_checkpoint_is_noop(self, tmp_path: Path) -> None:
        """--retry-errors with no existing checkpoint is a no-op (fresh run starts normally)."""
        from manage_experiment import cmd_run

        config_dir = tmp_path / "test-exp"
        self._make_test_dir(config_dir)

        results_dir = tmp_path / "results"
        results_dir.mkdir()
        # No checkpoint.json created — fresh run

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--results-dir",
                str(results_dir),
                "--retry-errors",
                "--skip-judge-validation",
            ]
        )

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}) as mock_run,
        ):
            result = cmd_run(args)

        assert result == 0
        mock_run.assert_called_once()

    def test_retry_errors_scoped_to_cli_tiers(self, tmp_path: Path) -> None:
        """--retry-errors --tiers T0 scopes reset to T0 only via tier_filter."""
        from datetime import datetime, timezone

        from manage_experiment import cmd_run

        from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint

        config_dir = tmp_path / "test-exp"
        self._make_test_dir(config_dir)

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Checkpoint has failed runs in both T0 and T1
        exp_dir = results_dir / "2024-01-01T00-00-00-test-exp"
        exp_dir.mkdir(parents=True)
        checkpoint = E2ECheckpoint(
            experiment_id="test-exp",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="failed",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="failed",
            run_states={
                "T0": {"00": {"1": "failed"}},
                "T1": {"00": {"1": "failed"}},
            },
            completed_runs={
                "T0": {"00": {1: "failed"}},
                "T1": {"00": {1: "failed"}},
            },
        )
        save_checkpoint(checkpoint, exp_dir / "checkpoint.json")

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--results-dir",
                str(results_dir),
                "--retry-errors",
                "--tiers",
                "T0",
                "--skip-judge-validation",
            ]
        )

        reset_calls: list[Any] = []

        def mock_reset(cp, from_state, **kwargs):
            reset_calls.append({"from_state": from_state, "kwargs": kwargs})
            return 1

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
            patch(
                "scylla.e2e.checkpoint.reset_runs_for_from_state",
                side_effect=mock_reset,
            ),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(reset_calls) == 1
        assert reset_calls[0]["kwargs"].get("tier_filter") == ["T0"]
        assert reset_calls[0]["kwargs"].get("status_filter") == ["failed"]


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
