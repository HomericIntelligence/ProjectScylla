"""Unit tests for checkpoint module functions and exceptions.

Tests coverage for functions and exception handling not covered by test_resume.py.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scylla.e2e.checkpoint import (
    CheckpointError,
    ConfigMismatchError,
    E2ECheckpoint,
    compute_config_hash,
    get_experiment_status,
    load_checkpoint,
    save_checkpoint,
)
from scylla.e2e.models import (
    ExperimentConfig,
    TierID,
)


@pytest.fixture
def experiment_config() -> ExperimentConfig:
    """Create a minimal experiment configuration for testing."""
    return ExperimentConfig(
        experiment_id="test-config",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        language="mojo",
        models=["claude-sonnet-4-5-20250929"],
        runs_per_subtest=3,
        tiers_to_run=[TierID.T0],
        judge_models=["claude-opus-4-5-20251101"],
        parallel_subtests=2,
        timeout_seconds=300,
    )


class TestComputeConfigHash:
    """Tests for compute_config_hash() function."""

    def test_compute_config_hash_returns_16_char_hex(
        self, experiment_config: ExperimentConfig
    ) -> None:
        """Verify hash is 16-character hex string."""
        hash_value = compute_config_hash(experiment_config)
        assert len(hash_value) == 16
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_compute_config_hash_deterministic(self, experiment_config: ExperimentConfig) -> None:
        """Verify same config produces same hash."""
        hash1 = compute_config_hash(experiment_config)
        hash2 = compute_config_hash(experiment_config)
        assert hash1 == hash2

    def test_compute_config_hash_different_for_different_configs(
        self, experiment_config: ExperimentConfig
    ) -> None:
        """Verify different configs produce different hashes."""
        hash1 = compute_config_hash(experiment_config)

        # Modify a field that affects results
        experiment_config.runs_per_subtest = 5
        hash2 = compute_config_hash(experiment_config)

        assert hash1 != hash2

    def test_compute_config_hash_ignores_parallel_subtests(
        self, experiment_config: ExperimentConfig
    ) -> None:
        """Verify parallel_subtests doesn't affect hash (parallelization only)."""
        hash1 = compute_config_hash(experiment_config)

        # Change parallel_subtests
        experiment_config.parallel_subtests = 4
        hash2 = compute_config_hash(experiment_config)

        # Hash should be the same
        assert hash1 == hash2

    def test_compute_config_hash_ignores_max_subtests(
        self, experiment_config: ExperimentConfig
    ) -> None:
        """Verify max_subtests doesn't affect hash (development/testing only)."""
        hash1 = compute_config_hash(experiment_config)

        # Create a copy with max_subtests set
        experiment_config_copy = ExperimentConfig(
            experiment_id=experiment_config.experiment_id,
            task_repo=experiment_config.task_repo,
            task_commit=experiment_config.task_commit,
            task_prompt_file=experiment_config.task_prompt_file,
            language=experiment_config.language,
            models=experiment_config.models,
            runs_per_subtest=experiment_config.runs_per_subtest,
            tiers_to_run=experiment_config.tiers_to_run,
            judge_models=experiment_config.judge_models,
            parallel_subtests=experiment_config.parallel_subtests,
            timeout_seconds=experiment_config.timeout_seconds,
            max_subtests=5,  # Add max_subtests
        )
        hash2 = compute_config_hash(experiment_config_copy)

        # Hash should be the same (max_subtests is excluded)
        assert hash1 == hash2


class TestGetExperimentStatus:
    """Tests for get_experiment_status() function."""

    def test_get_experiment_status_no_checkpoint(self, tmp_path: Path) -> None:
        """Verify status when no checkpoint exists."""
        status = get_experiment_status(tmp_path)
        assert status["running"] is False
        assert status["status"] == "unknown"

    def test_get_experiment_status_with_checkpoint(self, tmp_path: Path) -> None:
        """Verify status reads checkpoint data."""
        # Create checkpoint
        checkpoint = E2ECheckpoint(
            experiment_id="test-exp",
            experiment_dir=str(tmp_path),
            config_hash="test-hash",
            completed_runs={"T0": {"T0_00": {1: "passed", 2: "passed"}}},
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status="paused_rate_limit",
            rate_limit_until="2026-02-13T00:00:00Z",
        )
        checkpoint_path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, checkpoint_path)

        status = get_experiment_status(tmp_path)
        assert status["status"] == "paused_rate_limit"
        assert status["completed_runs"] == 2
        assert status["rate_limit_until"] == "2026-02-13T00:00:00Z"

    def test_get_experiment_status_corrupted_checkpoint(self, tmp_path: Path) -> None:
        """Verify status handles corrupted checkpoint gracefully."""
        checkpoint_path = tmp_path / "checkpoint.json"
        checkpoint_path.write_text("{ invalid json")

        status = get_experiment_status(tmp_path)
        assert status["running"] is False
        assert status["status"] == "unknown"

    def test_get_experiment_status_running_process(self, tmp_path: Path) -> None:
        """Verify status detects running process."""
        pid_path = tmp_path / "experiment.pid"
        current_pid = os.getpid()
        pid_path.write_text(str(current_pid))

        status = get_experiment_status(tmp_path)
        assert status["running"] is True
        assert status["pid"] == current_pid

    def test_get_experiment_status_dead_process(self, tmp_path: Path) -> None:
        """Verify status detects dead process."""
        pid_path = tmp_path / "experiment.pid"
        # Use a PID that doesn't exist (very high number unlikely to exist)
        dead_pid = 999999
        pid_path.write_text(str(dead_pid))

        status = get_experiment_status(tmp_path)
        assert status["running"] is False
        assert status["pid"] is None

    def test_get_experiment_status_invalid_pid_file(self, tmp_path: Path) -> None:
        """Verify status handles invalid PID file gracefully."""
        pid_path = tmp_path / "experiment.pid"
        pid_path.write_text("not-a-number")

        status = get_experiment_status(tmp_path)
        assert status["running"] is False
        assert status["pid"] is None


class TestCheckpointExceptions:
    """Tests for checkpoint exception classes."""

    def test_checkpoint_error_can_be_raised(self) -> None:
        """Verify CheckpointError can be raised."""
        with pytest.raises(CheckpointError, match="Test error"):
            raise CheckpointError("Test error")

    def test_checkpoint_error_is_exception(self) -> None:
        """Verify CheckpointError is an Exception."""
        assert issubclass(CheckpointError, Exception)

    def test_config_mismatch_error_can_be_raised(self) -> None:
        """Verify ConfigMismatchError can be raised."""
        with pytest.raises(ConfigMismatchError, match="Config mismatch"):
            raise ConfigMismatchError("Config mismatch")

    def test_config_mismatch_error_is_checkpoint_error(self) -> None:
        """Verify ConfigMismatchError is a CheckpointError."""
        assert issubclass(ConfigMismatchError, CheckpointError)


class TestCheckpointVersionMismatch:
    """Tests for from_dict version mismatch handling."""

    def test_from_dict_raises_on_version_1_0(self, tmp_path: Path) -> None:
        """Verify from_dict raises CheckpointError for v1.0."""
        data = {
            "version": "1.0",
            "experiment_id": "test-exp",
            "experiment_dir": str(tmp_path),
            "config_hash": "test-hash",
            "completed_runs": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

        with pytest.raises(
            CheckpointError,
            match="Incompatible checkpoint version 1.0.*requires checkpoint format 2.0",
        ):
            E2ECheckpoint.from_dict(data)

    def test_from_dict_raises_on_unknown_version(self, tmp_path: Path) -> None:
        """Verify from_dict raises CheckpointError for unknown version."""
        data = {
            "version": "3.5",
            "experiment_id": "test-exp",
            "experiment_dir": str(tmp_path),
            "config_hash": "test-hash",
            "completed_runs": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

        with pytest.raises(
            CheckpointError,
            match="Incompatible checkpoint version 3.5.*requires checkpoint format 2.0",
        ):
            E2ECheckpoint.from_dict(data)

    def test_from_dict_accepts_version_2_0(self, tmp_path: Path) -> None:
        """Verify from_dict accepts version 2.0."""
        data = {
            "version": "2.0",
            "experiment_id": "test-exp",
            "experiment_dir": str(tmp_path),
            "config_hash": "test-hash",
            "completed_runs": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

        checkpoint = E2ECheckpoint.from_dict(data)
        assert checkpoint.version == "2.0"
        assert checkpoint.experiment_id == "test-exp"


class TestSaveCheckpointErrors:
    """Tests for save_checkpoint error handling."""

    def test_save_checkpoint_raises_on_write_failure(self, tmp_path: Path) -> None:
        """Verify save_checkpoint raises CheckpointError on write failure."""
        checkpoint = E2ECheckpoint(
            experiment_id="test-exp",
            experiment_dir=str(tmp_path),
            config_hash="test-hash",
        )

        # Use a path that doesn't exist and can't be created
        invalid_path = tmp_path / "nonexistent" / "checkpoint.json"

        with pytest.raises(CheckpointError, match="Failed to save checkpoint"):
            save_checkpoint(checkpoint, invalid_path)

    def test_save_checkpoint_atomic_write_uses_temp_file(self, tmp_path: Path) -> None:
        """Verify save_checkpoint uses atomic write with temp file."""
        checkpoint = E2ECheckpoint(
            experiment_id="test-exp",
            experiment_dir=str(tmp_path),
            config_hash="test-hash",
        )
        checkpoint_path = tmp_path / "checkpoint.json"

        with patch("scylla.e2e.checkpoint.os.getpid", return_value=12345):
            save_checkpoint(checkpoint, checkpoint_path)

        # Verify final file exists
        assert checkpoint_path.exists()

        # Verify temp file was cleaned up (by atomic rename)
        temp_files = list(tmp_path.glob("checkpoint.tmp.*"))
        assert len(temp_files) == 0


class TestLoadCheckpointErrors:
    """Tests for load_checkpoint error handling."""

    def test_load_checkpoint_raises_on_missing_file(self, tmp_path: Path) -> None:
        """Verify load_checkpoint raises CheckpointError when file doesn't exist."""
        missing_path = tmp_path / "missing.json"

        with pytest.raises(CheckpointError, match="Checkpoint file not found"):
            load_checkpoint(missing_path)

    def test_load_checkpoint_raises_on_json_decode_error(self, tmp_path: Path) -> None:
        """Verify load_checkpoint raises CheckpointError on invalid JSON."""
        corrupt_path = tmp_path / "corrupt.json"
        corrupt_path.write_text("{ invalid json")

        with pytest.raises(CheckpointError, match="Failed to load checkpoint"):
            load_checkpoint(corrupt_path)

    def test_load_checkpoint_raises_on_read_permission_error(self, tmp_path: Path) -> None:
        """Verify load_checkpoint raises CheckpointError on read permission error."""
        checkpoint = E2ECheckpoint(
            experiment_id="test-exp",
            experiment_dir=str(tmp_path),
            config_hash="test-hash",
        )
        checkpoint_path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, checkpoint_path)

        # Mock open to raise PermissionError
        with patch("scylla.e2e.checkpoint.open", side_effect=PermissionError("No access")):
            with pytest.raises(CheckpointError, match="Failed to load checkpoint"):
                load_checkpoint(checkpoint_path)
