"""Unit tests for ExperimentSetupManager — extracted from E2ERunner filesystem setup."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.experiment_setup_manager import ExperimentSetupManager
from scylla.e2e.models import ExperimentConfig, TierID

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_config(tmp_path: Path) -> ExperimentConfig:
    """Minimal experiment configuration."""
    return ExperimentConfig(
        experiment_id="test-exp-abc123",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=tmp_path / "prompt.md",
        language="python",
        tiers_to_run=[TierID.T0],
    )


@pytest.fixture
def manager(base_config: ExperimentConfig, tmp_path: Path) -> ExperimentSetupManager:
    """ExperimentSetupManager bound to tmp_path as results_base_dir."""
    return ExperimentSetupManager(base_config, tmp_path / "results")


# ---------------------------------------------------------------------------
# create_experiment_dir
# ---------------------------------------------------------------------------


class TestCreateExperimentDir:
    """Tests for create_experiment_dir()."""

    def test_creates_directory(self, manager: ExperimentSetupManager) -> None:
        """create_experiment_dir() creates the experiment directory."""
        experiment_dir = manager.create_experiment_dir()
        assert experiment_dir.exists()
        assert experiment_dir.is_dir()

    def test_directory_contains_experiment_id(
        self, manager: ExperimentSetupManager, base_config: ExperimentConfig
    ) -> None:
        """Directory name contains the experiment_id."""
        experiment_dir = manager.create_experiment_dir()
        assert base_config.experiment_id in experiment_dir.name

    def test_directory_has_timestamp_prefix(self, manager: ExperimentSetupManager) -> None:
        """Directory name starts with a timestamp (YYYY-MM-DDTHH-MM-SS)."""
        experiment_dir = manager.create_experiment_dir()
        # Timestamp prefix format: 2024-01-15T12-30-00
        import re

        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}", experiment_dir.name)

    def test_creates_config_subdirectory(self, manager: ExperimentSetupManager) -> None:
        """create_experiment_dir() creates a config/ subdirectory."""
        experiment_dir = manager.create_experiment_dir()
        assert (experiment_dir / "config").is_dir()

    def test_creates_judge_prompt_md(self, manager: ExperimentSetupManager) -> None:
        """create_experiment_dir() creates judge_prompt.md in the experiment root."""
        experiment_dir = manager.create_experiment_dir()
        assert (experiment_dir / "judge_prompt.md").exists()

    def test_returns_path_under_results_base_dir(self, manager: ExperimentSetupManager) -> None:
        """Returned path is under results_base_dir."""
        experiment_dir = manager.create_experiment_dir()
        assert experiment_dir.parent == manager.results_base_dir


# ---------------------------------------------------------------------------
# copy_grading_materials
# ---------------------------------------------------------------------------


class TestCopyGradingMaterials:
    """Tests for copy_grading_materials()."""

    def test_copies_prompt_when_exists(
        self, manager: ExperimentSetupManager, base_config: ExperimentConfig, tmp_path: Path
    ) -> None:
        """prompt.md is copied when task_prompt_file exists."""
        base_config.task_prompt_file.write_text("# Task prompt")
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        manager.copy_grading_materials(experiment_dir)

        assert (experiment_dir / "prompt.md").exists()
        assert (experiment_dir / "prompt.md").read_text() == "# Task prompt"

    def test_no_prompt_copy_when_missing(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """prompt.md is NOT created when task_prompt_file doesn't exist."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        manager.copy_grading_materials(experiment_dir)

        assert not (experiment_dir / "prompt.md").exists()

    def test_symlinks_criteria_when_exists(
        self,
        manager: ExperimentSetupManager,
        base_config: ExperimentConfig,
        tmp_path: Path,
    ) -> None:
        """criteria.md symlink is created when the source file exists."""
        expected_dir = base_config.task_prompt_file.parent / "expected"
        expected_dir.mkdir(parents=True)
        (expected_dir / "criteria.md").write_text("criteria content")

        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        manager.copy_grading_materials(experiment_dir)

        criteria_dest = experiment_dir / "criteria.md"
        assert criteria_dest.is_symlink()

    def test_no_criteria_symlink_when_missing(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """criteria.md symlink is NOT created when source file doesn't exist."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        manager.copy_grading_materials(experiment_dir)

        assert not (experiment_dir / "criteria.md").exists()

    def test_symlinks_rubric_when_exists(
        self,
        manager: ExperimentSetupManager,
        base_config: ExperimentConfig,
        tmp_path: Path,
    ) -> None:
        """rubric.yaml symlink is created when the source file exists."""
        expected_dir = base_config.task_prompt_file.parent / "expected"
        expected_dir.mkdir(parents=True)
        (expected_dir / "rubric.yaml").write_text("rubric: content")

        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        manager.copy_grading_materials(experiment_dir)

        rubric_dest = experiment_dir / "rubric.yaml"
        assert rubric_dest.is_symlink()

    def test_creates_judge_prompt_md(self, manager: ExperimentSetupManager, tmp_path: Path) -> None:
        """judge_prompt.md is always created."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        manager.copy_grading_materials(experiment_dir)

        assert (experiment_dir / "judge_prompt.md").exists()
        content = (experiment_dir / "judge_prompt.md").read_text()
        assert "Judge Evaluation Context" in content


# ---------------------------------------------------------------------------
# save_config
# ---------------------------------------------------------------------------


class TestSaveConfig:
    """Tests for save_config()."""

    def test_calls_config_save(self, manager: ExperimentSetupManager, tmp_path: Path) -> None:
        """save_config() calls config.save() with correct path."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()
        (experiment_dir / "config").mkdir()

        with patch("scylla.e2e.models.ExperimentConfig.save") as mock_save:
            manager.save_config(experiment_dir)

        mock_save.assert_called_once_with(experiment_dir / "config" / "experiment.json")


# ---------------------------------------------------------------------------
# capture_baseline
# ---------------------------------------------------------------------------


class TestCaptureBaseline:
    """Tests for capture_baseline()."""

    def test_skips_when_baseline_already_exists(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """capture_baseline() is idempotent: skips if pipeline_baseline.json exists."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()
        (experiment_dir / "pipeline_baseline.json").write_text("{}")

        workspace_manager = MagicMock()

        # Direct call — should not call workspace_manager at all
        manager.capture_baseline(experiment_dir, workspace_manager)

        workspace_manager.create_worktree.assert_not_called()

    def test_calls_workspace_manager_create_worktree(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """capture_baseline() calls create_worktree when baseline is missing."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        workspace_manager = MagicMock()

        with (
            patch("scylla.e2e.llm_judge._run_build_pipeline") as mock_pipeline,
            patch("scylla.e2e.subtest_executor._save_pipeline_baseline"),
        ):
            mock_result = MagicMock()
            mock_result.all_passed = True
            mock_pipeline.return_value = mock_result

            manager.capture_baseline(experiment_dir, workspace_manager)

        workspace_manager.create_worktree.assert_called_once()

    def test_cleans_up_worktree_on_success(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """capture_baseline() always calls cleanup_worktree in finally block."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        workspace_manager = MagicMock()

        with (
            patch("scylla.e2e.llm_judge._run_build_pipeline") as mock_pipeline,
            patch("scylla.e2e.subtest_executor._save_pipeline_baseline"),
        ):
            mock_result = MagicMock()
            mock_result.all_passed = False
            mock_pipeline.return_value = mock_result

            manager.capture_baseline(experiment_dir, workspace_manager)

        workspace_manager.cleanup_worktree.assert_called_once()

    def test_cleans_up_worktree_on_pipeline_failure(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """capture_baseline() cleans up even when pipeline raises."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        workspace_manager = MagicMock()

        with patch("scylla.e2e.llm_judge._run_build_pipeline") as mock_pipeline:
            mock_pipeline.side_effect = RuntimeError("build failed")

            # Should NOT propagate — baseline capture is non-critical
            manager.capture_baseline(experiment_dir, workspace_manager)

        workspace_manager.cleanup_worktree.assert_called_once()

    def test_branch_name_uses_experiment_id_prefix(
        self, manager: ExperimentSetupManager, base_config: ExperimentConfig, tmp_path: Path
    ) -> None:
        """cleanup_worktree is called with branch name derived from experiment_id prefix."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        workspace_manager = MagicMock()

        with (
            patch("scylla.e2e.llm_judge._run_build_pipeline") as mock_pipeline,
            patch("scylla.e2e.subtest_executor._save_pipeline_baseline"),
        ):
            mock_result = MagicMock()
            mock_result.all_passed = True
            mock_pipeline.return_value = mock_result

            manager.capture_baseline(experiment_dir, workspace_manager)

        # Branch name should be "baseline_" + first 8 chars of experiment_id
        expected_branch = f"baseline_{base_config.experiment_id[:8]}"
        cleanup_args = workspace_manager.cleanup_worktree.call_args[0]
        assert cleanup_args[1] == expected_branch


# ---------------------------------------------------------------------------
# write_pid_file / cleanup_pid_file
# ---------------------------------------------------------------------------


class TestPidFile:
    """Tests for write_pid_file() and cleanup_pid_file()."""

    def test_write_pid_file_creates_file(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """write_pid_file() creates experiment.pid with current PID."""
        import os

        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        manager.write_pid_file(experiment_dir)

        pid_file = experiment_dir / "experiment.pid"
        assert pid_file.exists()
        assert pid_file.read_text() == str(os.getpid())

    def test_cleanup_pid_file_removes_file(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """cleanup_pid_file() removes the PID file when it exists."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()
        pid_file = experiment_dir / "experiment.pid"
        pid_file.write_text("12345")

        manager.cleanup_pid_file(experiment_dir)

        assert not pid_file.exists()

    def test_cleanup_pid_file_noop_when_missing(
        self, manager: ExperimentSetupManager, tmp_path: Path
    ) -> None:
        """cleanup_pid_file() does not raise when PID file doesn't exist."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        # Should not raise
        manager.cleanup_pid_file(experiment_dir)
