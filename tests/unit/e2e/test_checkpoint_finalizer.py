"""Unit tests for CheckpointFinalizer — checkpoint lifecycle at experiment boundaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint
from scylla.e2e.checkpoint_finalizer import CheckpointFinalizer
from scylla.e2e.models import ExperimentConfig, ExperimentState, TierID

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_config() -> ExperimentConfig:
    """Minimal experiment configuration."""
    return ExperimentConfig(
        experiment_id="test-exp-abc123",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        language="python",
        tiers_to_run=[TierID.T0],
    )


def _make_checkpoint(tmp_path: Path, experiment_id: str = "test-exp-abc123") -> E2ECheckpoint:
    """Create a minimal checkpoint."""
    return E2ECheckpoint(
        experiment_id=experiment_id,
        experiment_dir=str(tmp_path),
        config_hash="abc123",
        completed_runs={},
        started_at=datetime.now(timezone.utc).isoformat(),
        last_updated_at=datetime.now(timezone.utc).isoformat(),
        status="running",
        rate_limit_source=None,
        rate_limit_until=None,
        pause_count=0,
        pid=12345,
    )


@pytest.fixture
def finalizer(base_config: ExperimentConfig, tmp_path: Path) -> CheckpointFinalizer:
    """CheckpointFinalizer with tmp_path as results_base_dir."""
    return CheckpointFinalizer(base_config, tmp_path)


# ---------------------------------------------------------------------------
# find_existing_checkpoint
# ---------------------------------------------------------------------------


class TestFindExistingCheckpoint:
    """Tests for find_existing_checkpoint()."""

    def test_returns_none_when_results_dir_missing(
        self, base_config: ExperimentConfig, tmp_path: Path
    ) -> None:
        """Returns None when results_base_dir doesn't exist."""
        finalizer = CheckpointFinalizer(base_config, tmp_path / "nonexistent")
        assert finalizer.find_existing_checkpoint() is None

    def test_returns_none_when_no_matching_dirs(
        self, finalizer: CheckpointFinalizer, tmp_path: Path
    ) -> None:
        """Returns None when no directories match the experiment_id pattern."""
        # Create a directory that doesn't match
        (tmp_path / "2024-01-01T00-00-00-other-exp").mkdir()
        assert finalizer.find_existing_checkpoint() is None

    def test_returns_none_when_matching_dir_has_no_checkpoint(
        self, finalizer: CheckpointFinalizer, base_config: ExperimentConfig, tmp_path: Path
    ) -> None:
        """Returns None when matching dir exists but has no checkpoint.json."""
        exp_dir = tmp_path / f"2024-01-01T00-00-00-{base_config.experiment_id}"
        exp_dir.mkdir()
        assert finalizer.find_existing_checkpoint() is None

    def test_returns_checkpoint_path_when_found(
        self, finalizer: CheckpointFinalizer, base_config: ExperimentConfig, tmp_path: Path
    ) -> None:
        """Returns path to checkpoint.json when matching dir exists with checkpoint."""
        exp_dir = tmp_path / f"2024-01-01T00-00-00-{base_config.experiment_id}"
        exp_dir.mkdir()
        checkpoint_file = exp_dir / "checkpoint.json"
        checkpoint_file.write_text("{}")

        result = finalizer.find_existing_checkpoint()
        assert result == checkpoint_file

    def test_returns_most_recent_checkpoint(
        self, finalizer: CheckpointFinalizer, base_config: ExperimentConfig, tmp_path: Path
    ) -> None:
        """Returns the most recent matching checkpoint (sorted by dir name descending)."""
        exp_id = base_config.experiment_id

        older_dir = tmp_path / f"2024-01-01T00-00-00-{exp_id}"
        older_dir.mkdir()
        (older_dir / "checkpoint.json").write_text('{"old": true}')

        newer_dir = tmp_path / f"2024-06-01T12-00-00-{exp_id}"
        newer_dir.mkdir()
        checkpoint_file = newer_dir / "checkpoint.json"
        checkpoint_file.write_text('{"new": true}')

        result = finalizer.find_existing_checkpoint()
        assert result == checkpoint_file


# ---------------------------------------------------------------------------
# handle_experiment_interrupt
# ---------------------------------------------------------------------------


class TestHandleExperimentInterrupt:
    """Tests for handle_experiment_interrupt()."""

    def test_sets_status_interrupted_on_disk(
        self, finalizer: CheckpointFinalizer, tmp_path: Path
    ) -> None:
        """Reloads checkpoint from disk and sets status to 'interrupted'."""
        checkpoint = _make_checkpoint(tmp_path)
        checkpoint_path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, checkpoint_path)

        finalizer.handle_experiment_interrupt(checkpoint, checkpoint_path)

        # Verify disk was updated
        with open(checkpoint_path) as f:
            data = json.load(f)
        assert data["status"] == "interrupted"
        assert data["experiment_state"] == ExperimentState.INTERRUPTED.value

    def test_noop_when_checkpoint_path_missing(
        self, finalizer: CheckpointFinalizer, tmp_path: Path
    ) -> None:
        """Does nothing when checkpoint file doesn't exist."""
        checkpoint = _make_checkpoint(tmp_path)
        missing_path = tmp_path / "nonexistent.json"

        # Should not raise
        finalizer.handle_experiment_interrupt(checkpoint, missing_path)

    def test_fallback_to_in_memory_checkpoint_on_load_error(
        self, finalizer: CheckpointFinalizer, tmp_path: Path
    ) -> None:
        """Falls back to in-memory checkpoint if disk reload fails."""
        checkpoint = _make_checkpoint(tmp_path)
        checkpoint_path = tmp_path / "checkpoint.json"
        checkpoint_path.write_text("{invalid json}")

        # Should not raise; will use in-memory checkpoint
        with patch("scylla.e2e.checkpoint_finalizer.load_checkpoint") as mock_load:
            mock_load.side_effect = ValueError("parse error")
            finalizer.handle_experiment_interrupt(checkpoint, checkpoint_path)

        assert checkpoint.status == "interrupted"

    def test_updates_last_updated_at(self, finalizer: CheckpointFinalizer, tmp_path: Path) -> None:
        """last_updated_at is refreshed on interrupt."""
        checkpoint = _make_checkpoint(tmp_path)
        original_time = checkpoint.last_updated_at
        checkpoint_path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, checkpoint_path)

        finalizer.handle_experiment_interrupt(checkpoint, checkpoint_path)

        with open(checkpoint_path) as f:
            data = json.load(f)
        # last_updated_at should be updated (or at least not older than original)
        assert data["last_updated_at"] >= original_time


# ---------------------------------------------------------------------------
# validate_filesystem_on_resume
# ---------------------------------------------------------------------------


class TestValidateFilesystemOnResume:
    """Tests for validate_filesystem_on_resume()."""

    def test_no_warning_for_non_tiers_running_state(
        self, finalizer: CheckpointFinalizer, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warnings logged for states other than TIERS_RUNNING."""
        experiment_dir = tmp_path / "nonexistent_exp"

        import logging

        with caplog.at_level(logging.WARNING, logger="scylla.e2e.checkpoint_finalizer"):
            finalizer.validate_filesystem_on_resume(experiment_dir, ExperimentState.INITIALIZING)

        assert not caplog.records

    def test_warns_when_experiment_dir_missing_in_tiers_running(
        self, finalizer: CheckpointFinalizer, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Warning logged when TIERS_RUNNING but experiment_dir doesn't exist."""
        missing_dir = tmp_path / "missing_experiment"

        import logging

        with caplog.at_level(logging.WARNING, logger="scylla.e2e.checkpoint_finalizer"):
            finalizer.validate_filesystem_on_resume(missing_dir, ExperimentState.TIERS_RUNNING)

        assert any("experiment_dir missing" in r.message for r in caplog.records)

    def test_warns_when_repos_dir_missing_in_tiers_running(
        self,
        finalizer: CheckpointFinalizer,
        base_config: ExperimentConfig,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning logged when TIERS_RUNNING but repos/ dir doesn't exist."""
        # experiment_dir exists but repos/ doesn't
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()

        import logging

        with caplog.at_level(logging.WARNING, logger="scylla.e2e.checkpoint_finalizer"):
            finalizer.validate_filesystem_on_resume(experiment_dir, ExperimentState.TIERS_RUNNING)

        assert any("repos/ dir missing" in r.message for r in caplog.records)

    def test_no_warning_when_all_dirs_exist(
        self,
        finalizer: CheckpointFinalizer,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No warnings when both experiment_dir and repos/ exist."""
        experiment_dir = tmp_path / "exp"
        experiment_dir.mkdir()
        (tmp_path / "repos").mkdir()

        import logging

        with caplog.at_level(logging.WARNING, logger="scylla.e2e.checkpoint_finalizer"):
            finalizer.validate_filesystem_on_resume(experiment_dir, ExperimentState.TIERS_RUNNING)

        assert not caplog.records


# ---------------------------------------------------------------------------
# mark_checkpoint_completed
# ---------------------------------------------------------------------------


class TestMarkCheckpointCompleted:
    """Tests for mark_checkpoint_completed()."""

    def test_sets_status_completed(self, finalizer: CheckpointFinalizer, tmp_path: Path) -> None:
        """mark_checkpoint_completed() sets checkpoint.status to 'completed'."""
        checkpoint = _make_checkpoint(tmp_path)
        checkpoint_path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, checkpoint_path)

        finalizer.mark_checkpoint_completed(checkpoint, tmp_path)

        assert checkpoint.status == "completed"

    def test_preserves_in_memory_state(
        self, finalizer: CheckpointFinalizer, tmp_path: Path
    ) -> None:
        """mark_checkpoint_completed() preserves existing in-memory state.

        With ThreadPoolExecutor, all worker threads share the same in-memory
        checkpoint, so no disk-merge is needed — the checkpoint is already
        up-to-date when mark_checkpoint_completed() is called.
        """
        checkpoint = _make_checkpoint(tmp_path)
        checkpoint.run_states = {"T0": {"00": {"1": "worktree_cleaned"}}}
        checkpoint.subtest_states = {"T0": {"00": "aggregated"}}
        checkpoint.tier_states = {"T0": "complete"}

        finalizer.mark_checkpoint_completed(checkpoint, tmp_path)

        assert checkpoint.status == "completed"
        assert checkpoint.run_states == {"T0": {"00": {"1": "worktree_cleaned"}}}
        assert checkpoint.subtest_states == {"T0": {"00": "aggregated"}}
        assert checkpoint.tier_states == {"T0": "complete"}
