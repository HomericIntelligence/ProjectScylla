"""cmd_run tests for scripts/manage_experiment.py."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

from manage_experiment import MODEL_ALIASES, build_parser

# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


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

        def mock_reset_runs(checkpoint: Any, from_state: Any, **kwargs: Any) -> Any:
            reset_calls.append(("runs", from_state, kwargs))
            return 1

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_reset_tiers(checkpoint: Any, from_state: Any, **kwargs: Any) -> Any:
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

        def mock_reset_tiers(checkpoint: Any, from_state: Any, **kwargs: Any) -> Any:
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

        def mock_reset_experiment(checkpoint: Any, from_state: Any) -> Any:
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

        def mock_reset_runs(checkpoint: Any, from_state: Any, **kwargs: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_batch(test_dirs: Any, passed_args: Any) -> Any:
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

        def mock_reset_runs(checkpoint: Any, from_state: Any, **kwargs: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

    def test_retry_errors_uses_last_entry_per_test(self, tmp_path: Path) -> None:
        """--retry-errors uses only the last entry per test_id.

        test-001 has entries [error, error, success] — last is success, so skipped.
        test-002 has entries [success, success, error] — last is error, so re-run.
        """
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        summary = {
            "results": [
                {"test_id": "test-001", "status": "error", "error": "first error"},
                {"test_id": "test-002", "status": "success"},
                {"test_id": "test-001", "status": "error", "error": "second error"},
                {"test_id": "test-002", "status": "success"},
                {"test_id": "test-001", "status": "success"},
                {"test_id": "test-002", "status": "error", "error": "final error"},
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
            executed_ids.append(config.experiment_id)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        # Only test-002 (last entry is error) was re-run; test-001 (last entry is success) skipped
        assert executed_ids == ["test-002"]

    def test_retry_errors_reruns_success_test_with_failed_checkpoint_runs(
        self, tmp_path: Path
    ) -> None:
        """--retry-errors reruns a 'success' test if its checkpoint has failed runs."""
        from datetime import datetime, timezone

        from manage_experiment import cmd_run

        from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # batch_summary says test-001 succeeded at the batch level; test-002 also success (clean)
        summary = {
            "results": [
                {"test_id": "test-001", "status": "success"},
                {"test_id": "test-002", "status": "success"},
            ]
        }
        (results_dir / "batch_summary.json").write_text(json.dumps(summary))

        # Create checkpoint for test-001 with a failed run and an intermediate-state run
        exp_dir = results_dir / "2024-01-01T00-00-00-test-001"
        exp_dir.mkdir(parents=True)
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="complete",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="complete",
            run_states={
                "T0": {"00": {"1": "worktree_cleaned"}},
                "T1": {"01": {"1": "failed", "2": "judge_prompt_built"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        save_checkpoint(checkpoint, exp_dir / "checkpoint.json")

        # Create clean checkpoint for test-002 (no failures)
        exp_dir2 = results_dir / "2024-01-01T00-00-00-test-002"
        exp_dir2.mkdir(parents=True)
        checkpoint2 = E2ECheckpoint(
            experiment_id="test-002",
            experiment_dir=str(exp_dir2),
            config_hash="abc123",
            experiment_state="complete",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="complete",
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        save_checkpoint(checkpoint2, exp_dir2 / "checkpoint.json")

        self._make_test_dir_with_yaml(tmp_path / "test-001", "test-001")
        self._make_test_dir_with_yaml(tmp_path / "test-002", "test-002")

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

        executed_ids: list[str] = []

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
            executed_ids.append(config.experiment_id)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        # test-001 must be re-run (checkpoint has failed run); test-002 skipped (all clean)
        assert "test-001" in executed_ids
        assert "test-002" not in executed_ids

    def test_retry_errors_skips_success_test_with_all_runs_complete(self, tmp_path: Path) -> None:
        """--retry-errors skips a 'success' test when all checkpoint runs are complete."""
        from datetime import datetime, timezone

        from manage_experiment import cmd_run

        from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        summary = {
            "results": [
                {"test_id": "test-001", "status": "success"},
                {"test_id": "test-002", "status": "error"},
            ]
        }
        (results_dir / "batch_summary.json").write_text(json.dumps(summary))

        # Checkpoint with all runs at worktree_cleaned (no failures)
        exp_dir = results_dir / "2024-01-01T00-00-00-test-001"
        exp_dir.mkdir(parents=True)
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="complete",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="complete",
            run_states={
                "T0": {"00": {"1": "worktree_cleaned"}},
                "T1": {"01": {"1": "worktree_cleaned"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}, "T1": {"01": {1: "passed"}}},
        )
        save_checkpoint(checkpoint, exp_dir / "checkpoint.json")

        self._make_test_dir_with_yaml(tmp_path / "test-001", "test-001")
        self._make_test_dir_with_yaml(tmp_path / "test-002", "test-002")

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

        executed_ids: list[str] = []

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
            executed_ids.append(config.experiment_id)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        # test-001 skipped (success + no retryable runs); test-002 re-runs (error status)
        assert "test-001" not in executed_ids
        assert "test-002" in executed_ids

    def test_retry_errors_resets_failed_and_rate_limited_runs(self, tmp_path: Path) -> None:
        """_reset_non_completed_runs resets failed/rate_limited and cascades intermediate states."""
        from datetime import datetime, timezone

        from manage_experiment import _reset_non_completed_runs

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        exp_dir.mkdir()
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="failed",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="failed",
            run_states={
                "T0": {"00": {"1": "failed", "2": "worktree_cleaned", "3": "judge_prompt_built"}},
                "T1": {"01": {"1": "rate_limited", "2": "replay_generated"}},
            },
            completed_runs={},
        )

        reset_count = _reset_non_completed_runs(checkpoint)

        # All non-completed runs counted (failed + rate_limited + intermediate = 4)
        assert reset_count == 4
        assert checkpoint.run_states["T0"]["00"]["1"] == "pending"
        assert checkpoint.run_states["T1"]["01"]["1"] == "pending"
        # Intermediate runs keep their state (resume where they left off)
        assert checkpoint.run_states["T0"]["00"]["3"] == "judge_prompt_built"
        assert checkpoint.run_states["T1"]["01"]["2"] == "replay_generated"
        # Completed run is untouched
        assert checkpoint.run_states["T0"]["00"]["2"] == "worktree_cleaned"
        # Subtest states cascade to pending (both T0/00 and T1/01 have non-completed runs)
        assert checkpoint.get_subtest_state("T0", "00") == "pending"
        assert checkpoint.get_subtest_state("T1", "01") == "pending"
        # Tier states cascade to pending
        assert checkpoint.get_tier_state("T0") == "pending"
        assert checkpoint.get_tier_state("T1") == "pending"
        # Experiment state updated
        assert checkpoint.experiment_state == "tiers_running"

    def test_reset_non_completed_runs_intermediate_states_preserved(self, tmp_path: Path) -> None:
        """Intermediate run states are preserved; tier/subtest cascade happens for re-entry."""
        from datetime import datetime, timezone

        from manage_experiment import _reset_non_completed_runs

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        exp_dir.mkdir()
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="complete",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="complete",
            run_states={
                "T0": {
                    "00": {
                        "1": "worktree_cleaned",
                        "2": "judge_prompt_built",
                        "3": "dir_structure_created",
                    }
                },
                "T2": {"01": {"1": "replay_generated", "2": "config_committed"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}},
        )

        reset_count = _reset_non_completed_runs(checkpoint)

        # 4 intermediate non-completed runs found
        assert reset_count == 4
        # Intermediate run states are preserved (resume where they left off)
        assert checkpoint.run_states["T0"]["00"]["2"] == "judge_prompt_built"
        assert checkpoint.run_states["T0"]["00"]["3"] == "dir_structure_created"
        assert checkpoint.run_states["T2"]["01"]["1"] == "replay_generated"
        assert checkpoint.run_states["T2"]["01"]["2"] == "config_committed"
        # Completed run is untouched
        assert checkpoint.run_states["T0"]["00"]["1"] == "worktree_cleaned"
        # Subtest/tier cascade happens so the run loop re-enters
        assert checkpoint.get_subtest_state("T0", "00") == "pending"
        assert checkpoint.get_subtest_state("T2", "01") == "pending"
        assert checkpoint.get_tier_state("T0") == "pending"
        assert checkpoint.get_tier_state("T2") == "pending"
        assert checkpoint.experiment_state == "tiers_running"

    def test_checkpoint_has_retryable_runs_true_for_intermediate_states(
        self, tmp_path: Path
    ) -> None:
        """_checkpoint_has_retryable_runs returns True for runs at intermediate states."""
        from datetime import datetime, timezone

        from manage_experiment import _checkpoint_has_retryable_runs

        from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint

        exp_dir = tmp_path / "exp"
        exp_dir.mkdir()
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="complete",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="complete",
            run_states={
                "T0": {"00": {"1": "worktree_cleaned", "2": "judge_prompt_built"}},
            },
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        cp_path = exp_dir / "checkpoint.json"
        save_checkpoint(checkpoint, cp_path)

        assert _checkpoint_has_retryable_runs(cp_path) is True

    def test_checkpoint_has_retryable_runs_false_when_all_complete(self, tmp_path: Path) -> None:
        """_checkpoint_has_retryable_runs returns False when all runs are worktree_cleaned."""
        from datetime import datetime, timezone

        from manage_experiment import _checkpoint_has_retryable_runs

        from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint

        exp_dir = tmp_path / "exp"
        exp_dir.mkdir()
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="complete",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="complete",
            run_states={
                "T0": {"00": {"1": "worktree_cleaned", "2": "worktree_cleaned"}},
                "T1": {"01": {"1": "worktree_cleaned"}},
            },
            completed_runs={"T0": {"00": {1: "passed", 2: "passed"}}, "T1": {"01": {1: "passed"}}},
        )
        cp_path = exp_dir / "checkpoint.json"
        save_checkpoint(checkpoint, cp_path)

        assert _checkpoint_has_retryable_runs(cp_path) is False

    def test_checkpoint_has_retryable_runs_true_for_judge_failed(self, tmp_path: Path) -> None:
        """_checkpoint_has_retryable_runs returns True for judge-failed runs.

        worktree_cleaned state with completed_runs status == "failed".
        """
        from datetime import datetime, timezone

        from manage_experiment import _checkpoint_has_retryable_runs

        from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint

        exp_dir = tmp_path / "exp"
        exp_dir.mkdir()
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="complete",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="complete",
            run_states={
                "T0": {"00": {"1": "worktree_cleaned", "2": "worktree_cleaned"}},
            },
            completed_runs={"T0": {"00": {1: "passed", 2: "failed"}}},
        )
        cp_path = exp_dir / "checkpoint.json"
        save_checkpoint(checkpoint, cp_path)

        assert _checkpoint_has_retryable_runs(cp_path) is True

    def test_reset_non_completed_runs_resets_judge_failed_worktree_cleaned(
        self, tmp_path: Path
    ) -> None:
        """_reset_non_completed_runs resets worktree_cleaned runs with judge-failed status."""
        from datetime import datetime, timezone

        from manage_experiment import _reset_non_completed_runs

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        exp_dir.mkdir()
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="complete",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="complete",
            run_states={
                "T0": {"00": {"1": "worktree_cleaned", "2": "worktree_cleaned"}},
            },
            completed_runs={"T0": {"00": {1: "passed", 2: "failed"}}},
        )

        reset_count = _reset_non_completed_runs(checkpoint)

        assert reset_count == 1
        # Run 1 (passed) is untouched
        assert checkpoint.run_states["T0"]["00"]["1"] == "worktree_cleaned"
        assert checkpoint.get_run_status("T0", "00", 1) == "passed"
        # Run 2 (judge-failed) is reset to pending
        assert checkpoint.run_states["T0"]["00"]["2"] == "pending"
        assert checkpoint.get_run_status("T0", "00", 2) is None
        # Subtest and tier cascade
        assert checkpoint.get_subtest_state("T0", "00") == "pending"
        assert checkpoint.get_tier_state("T0") == "pending"
        assert checkpoint.experiment_state == "tiers_running"

    def test_reconcile_checkpoint_with_disk_advances_stale_state(self, tmp_path: Path) -> None:
        """_reconcile_checkpoint_with_disk advances stale intermediate state to worktree_cleaned."""
        import json
        from datetime import datetime, timezone

        from manage_experiment import _reconcile_checkpoint_with_disk

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        run_dir = exp_dir / "T0" / "00" / "run_01"
        run_dir.mkdir(parents=True)

        # Create run_result.json + report.md, no workspace dir => worktree_cleaned
        run_result = {"judge_passed": True, "cost_usd": 0.01}
        (run_dir / "run_result.json").write_text(json.dumps(run_result))
        (run_dir / "report.md").write_text("# Report")

        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="tiers_running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "judge_prompt_built"}}},
            completed_runs={},
        )

        corrected = _reconcile_checkpoint_with_disk(checkpoint, exp_dir)

        assert corrected == 1
        assert checkpoint.run_states["T0"]["00"]["1"] == "worktree_cleaned"
        assert checkpoint.get_run_status("T0", "00", 1) == "passed"

    def test_reconcile_checkpoint_with_disk_leaves_no_disk_state(self, tmp_path: Path) -> None:
        """_reconcile_checkpoint_with_disk leaves pending runs with no disk artifacts as-is."""
        from datetime import datetime, timezone

        from manage_experiment import _reconcile_checkpoint_with_disk

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"

        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="tiers_running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "pending"}}},
            completed_runs={},
        )

        corrected = _reconcile_checkpoint_with_disk(checkpoint, exp_dir)

        assert corrected == 0
        assert checkpoint.run_states["T0"]["00"]["1"] == "pending"

    def test_reconcile_checkpoint_with_disk_detects_judge_failed_from_run_result(
        self, tmp_path: Path
    ) -> None:
        """_reconcile_checkpoint_with_disk reads judge_passed=False from run_result.json."""
        import json
        from datetime import datetime, timezone

        from manage_experiment import _reconcile_checkpoint_with_disk

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        run_dir = exp_dir / "T0" / "00" / "run_01"
        run_dir.mkdir(parents=True)

        # Judge failed run: judge_passed=False
        run_result = {"judge_passed": False, "cost_usd": 0.01}
        (run_dir / "run_result.json").write_text(json.dumps(run_result))
        (run_dir / "report.md").write_text("# Report")

        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="tiers_running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "dir_structure_created"}}},
            completed_runs={},
        )

        corrected = _reconcile_checkpoint_with_disk(checkpoint, exp_dir)

        assert corrected == 1
        assert checkpoint.run_states["T0"]["00"]["1"] == "worktree_cleaned"
        assert checkpoint.get_run_status("T0", "00", 1) == "failed"

    def test_reconcile_checkpoint_with_disk_does_not_regress_advanced_state(
        self, tmp_path: Path
    ) -> None:
        """_reconcile_checkpoint_with_disk never regresses a state already more advanced."""
        import json
        from datetime import datetime, timezone

        from manage_experiment import _reconcile_checkpoint_with_disk

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        run_dir = exp_dir / "T0" / "00" / "run_01"
        run_dir.mkdir(parents=True)

        # Only agent result exists (no judge result or run_result.json)
        agent_dir = run_dir / "agent"
        agent_dir.mkdir()
        agent_result = {
            "exit_code": 0,
            "token_stats": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
            },
            "cost_usd": 0.01,
        }
        (agent_dir / "result.json").write_text(json.dumps(agent_result))

        # Checkpoint already at judge_complete — more advanced than agent_complete
        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="tiers_running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "judge_complete"}}},
            completed_runs={},
        )

        corrected = _reconcile_checkpoint_with_disk(checkpoint, exp_dir)

        # No regression — state stays at judge_complete
        assert corrected == 0
        assert checkpoint.run_states["T0"]["00"]["1"] == "judge_complete"

    def test_reconcile_corrupted_run_result_json(self, tmp_path: Path) -> None:
        """Malformed run_result.json leaves state unchanged (no crash)."""
        from datetime import datetime, timezone

        from manage_experiment import _reconcile_checkpoint_with_disk

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        run_dir = exp_dir / "T0" / "00" / "run_01"
        run_dir.mkdir(parents=True)

        # Write malformed JSON
        (run_dir / "run_result.json").write_text("{ not valid json !!!")
        (run_dir / "report.md").write_text("# Report")

        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="tiers_running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "judge_prompt_built"}}},
            completed_runs={},
        )

        # Should not raise; state advances via disk evidence but status stays None
        corrected = _reconcile_checkpoint_with_disk(checkpoint, exp_dir)

        # State is advanced (report.md + no workspace => worktree_cleaned inferred)
        assert corrected == 1
        assert checkpoint.run_states["T0"]["00"]["1"] == "worktree_cleaned"
        # set_run_state("worktree_cleaned") auto-calls mark_run_completed with "passed"
        # because no explicit inferred_status is set (corrupted JSON → None)
        assert checkpoint.get_run_status("T0", "00", 1) == "passed"

    def test_reconcile_missing_judge_passed_field(self, tmp_path: Path) -> None:
        """run_result.json without judge_passed advances state but leaves status=None."""
        import json
        from datetime import datetime, timezone

        from manage_experiment import _reconcile_checkpoint_with_disk

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        run_dir = exp_dir / "T0" / "00" / "run_01"
        run_dir.mkdir(parents=True)

        # run_result.json exists but has no judge_passed key
        (run_dir / "run_result.json").write_text(json.dumps({"cost_usd": 0.05}))
        (run_dir / "report.md").write_text("# Report")

        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="tiers_running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "baseline_captured"}}},
            completed_runs={},
        )

        corrected = _reconcile_checkpoint_with_disk(checkpoint, exp_dir)

        assert corrected == 1
        assert checkpoint.run_states["T0"]["00"]["1"] == "worktree_cleaned"
        # judge_passed defaulted to False by .get("judge_passed", False) → status="failed"
        assert checkpoint.get_run_status("T0", "00", 1) == "failed"

    def test_reconcile_worktree_created_state_gets_correct_rank(self, tmp_path: Path) -> None:
        """Run stuck in worktree_created with agent artifact on disk advances to agent_complete."""
        import json
        from datetime import datetime, timezone

        from manage_experiment import _reconcile_checkpoint_with_disk

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"
        run_dir = exp_dir / "T0" / "00" / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        agent_result = {
            "exit_code": 0,
            "token_stats": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
            },
            "cost_usd": 0.01,
        }
        (agent_dir / "result.json").write_text(json.dumps(agent_result))

        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="tiers_running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={"T0": {"00": {"1": "worktree_created"}}},
            completed_runs={},
        )

        corrected = _reconcile_checkpoint_with_disk(checkpoint, exp_dir)

        assert corrected == 1
        assert checkpoint.run_states["T0"]["00"]["1"] == "agent_complete"

    def test_reset_interleaved_rate_limited_and_failed(self, tmp_path: Path) -> None:
        """Mixed run states: failed + rate_limited reset; worktree_cleaned preserved."""
        from datetime import datetime, timezone

        from manage_experiment import _reset_non_completed_runs

        from scylla.e2e.checkpoint import E2ECheckpoint

        exp_dir = tmp_path / "exp"

        checkpoint = E2ECheckpoint(
            experiment_id="test-001",
            experiment_dir=str(exp_dir),
            config_hash="abc123",
            experiment_state="tiers_running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="running",
            run_states={
                "T0": {
                    "00": {
                        "1": "failed",
                        "2": "rate_limited",
                        "3": "worktree_cleaned",
                    }
                }
            },
            completed_runs={"T0": {"00": {3: "passed"}}},
        )

        _reset_non_completed_runs(checkpoint)

        assert checkpoint.run_states["T0"]["00"]["1"] == "pending"
        assert checkpoint.run_states["T0"]["00"]["2"] == "pending"
        assert checkpoint.run_states["T0"]["00"]["3"] == "worktree_cleaned"
        assert checkpoint.get_run_status("T0", "00", 3) == "passed"

    def test_reconcile_state_order_covers_all_run_states(self) -> None:
        """All non-terminal RunState values must appear in state_rank (regression guard)."""
        import inspect

        import manage_experiment

        from scylla.e2e.models import RunState

        # Extract state_order from the function source to avoid calling it with real args.
        # Instead, instantiate a minimal proxy to extract the dict at runtime.
        # We inspect the function source to find the state_order list.
        source = inspect.getsource(manage_experiment._reconcile_checkpoint_with_disk)

        terminal_states = {RunState.FAILED.value, RunState.RATE_LIMITED.value}
        non_terminal = {s.value for s in RunState if s.value not in terminal_states}

        for state_value in non_terminal:
            assert state_value in source, (
                f"RunState '{state_value}' is missing from _reconcile_checkpoint_with_disk "
                f"state_order — add it in the correct sequential position."
            )


# ---------------------------------------------------------------------------
# --add-judge in batch mode (bug fix validation)
# ---------------------------------------------------------------------------


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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

    def _run_and_capture(self, args: Any) -> Any:
        """Run cmd_run with args and return captured ExperimentConfig."""
        from manage_experiment import cmd_run

        captured: list[Any] = []

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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


# ---------------------------------------------------------------------------
# --config existence check
# ---------------------------------------------------------------------------


class TestConfigPathExistence:
    """Tests that a non-existent --config path gives a clear error message."""

    def test_nonexistent_config_reports_clear_error(self, tmp_path: Path, caplog: Any) -> None:
        """--config /nonexistent/path returns 1 and error message mentions the path."""
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

        def mock_reset_runs(checkpoint: Any, from_state: Any, **kwargs: Any) -> Any:
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

        def mock_reset_runs(checkpoint: Any, from_state: Any, **kwargs: Any) -> Any:
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

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
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


# ---------------------------------------------------------------------------
# --retry-errors in single mode
# ---------------------------------------------------------------------------


class TestRetryErrorsInSingleMode:
    """Tests --retry-errors single mode resets non-completed runs via _reset_non_completed_runs."""

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
        """--retry-errors single mode resets failed runs to pending (non-completed runs reset)."""
        from datetime import datetime, timezone

        from manage_experiment import cmd_run

        from scylla.e2e.checkpoint import E2ECheckpoint, load_checkpoint, save_checkpoint

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

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        # Verify the failed run was reset to pending in the checkpoint on disk
        saved = load_checkpoint(checkpoint_path)
        assert saved.run_states["T0"]["00"]["1"] == "pending"

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

    def test_retry_errors_resets_all_terminal_runs_across_tiers(self, tmp_path: Path) -> None:
        """--retry-errors resets terminal runs in all tiers via _reset_non_completed_runs."""
        from datetime import datetime, timezone

        from manage_experiment import cmd_run

        from scylla.e2e.checkpoint import E2ECheckpoint, load_checkpoint, save_checkpoint

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

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", return_value={"T0": {}}),
        ):
            result = cmd_run(args)

        assert result == 0
        # Both T0 and T1 failed runs are reset to pending
        saved = load_checkpoint(checkpoint_path)
        assert saved.run_states["T0"]["00"]["1"] == "pending"
        assert saved.run_states["T1"]["00"]["1"] == "pending"


# ---------------------------------------------------------------------------
# _find_checkpoint_path helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# --tiers and --max-subtests flow to ExperimentConfig
# ---------------------------------------------------------------------------


class TestCmdRunTiersAndMaxSubtests:
    """Tests that --tiers and --max-subtests CLI args flow through to ExperimentConfig."""

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

    def test_tiers_flag_flows_to_config(self, tmp_path: Path) -> None:
        """--tiers T0 T2 sets config.tiers_to_run to [TierID.T0, TierID.T2]."""
        from scylla.e2e.models import TierID

        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        from manage_experiment import cmd_run

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--tiers",
                "T0",
                "T2",
                "--skip-judge-validation",
            ]
        )

        captured_configs: list[Any] = []

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 1
        assert captured_configs[0].tiers_to_run == [TierID.T0, TierID.T2]

    def test_max_subtests_flag_flows_to_config(self, tmp_path: Path) -> None:
        """--max-subtests 3 sets config.max_subtests to 3."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        from manage_experiment import cmd_run

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--max-subtests",
                "3",
                "--skip-judge-validation",
            ]
        )

        captured_configs: list[Any] = []

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 1
        assert captured_configs[0].max_subtests == 3

    def test_default_tiers_flow_to_config(self, tmp_path: Path) -> None:
        """Without --tiers, config.tiers_to_run is non-empty (default tier list)."""
        config_dir = tmp_path / "test-dir"
        self._make_test_dir(config_dir)

        from manage_experiment import cmd_run

        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                str(config_dir),
                "--skip-judge-validation",
            ]
        )

        captured_configs: list[Any] = []

        def mock_run_experiment(config: Any, tiers_dir: Any, results_dir: Any, fresh: Any) -> Any:
            captured_configs.append(config)
            return {"T0": {}}

        with (
            patch("scylla.e2e.model_validation.validate_model", return_value=True),
            patch("scylla.e2e.runner.run_experiment", side_effect=mock_run_experiment),
        ):
            result = cmd_run(args)

        assert result == 0
        assert len(captured_configs) == 1
        assert len(captured_configs[0].tiers_to_run) > 0


# ---------------------------------------------------------------------------
# cmd_repair() edge cases: skip existing entries and corrupt JSON handling
# ---------------------------------------------------------------------------
