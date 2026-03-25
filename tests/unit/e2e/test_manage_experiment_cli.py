"""Parser and CLI argument tests for scripts/manage_experiment.py."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from manage_experiment import build_parser

# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


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
        assert args.model == "claude-sonnet-4-6"
        assert args.judge_model == "claude-opus-4-6"
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

        def mock_run_batch(test_dirs: Any, passed_args: Any) -> Any:
            call_args.append(test_dirs)
            return 0

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(tmp_path),
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

        def mock_run_batch(test_dirs: Any, passed_args: Any) -> Any:
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
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1


# ---------------------------------------------------------------------------
# --from argument validation
# ---------------------------------------------------------------------------


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
            ]
        )

        from manage_experiment import cmd_run

        with patch("scylla.e2e.model_validation.validate_model", return_value=True):
            result = cmd_run(args)
        assert result == 1


# ---------------------------------------------------------------------------
# cmd_repair with mock checkpoint
# ---------------------------------------------------------------------------
