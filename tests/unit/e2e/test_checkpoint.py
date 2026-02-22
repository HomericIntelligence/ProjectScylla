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
            match=r"Incompatible checkpoint version 1\.0",
        ):
            E2ECheckpoint.from_dict(data)

    def test_from_dict_raises_on_unknown_version(self, tmp_path: Path) -> None:
        """Verify from_dict raises CheckpointError for unknown version."""
        data = {
            "version": "9.9",
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
            match=r"Incompatible checkpoint version 9\.9",
        ):
            E2ECheckpoint.from_dict(data)

    def test_from_dict_accepts_version_2_0_and_migrates_to_v3(self, tmp_path: Path) -> None:
        """Verify from_dict migrates v2.0 to v3.0 automatically."""
        data = {
            "version": "2.0",
            "experiment_id": "test-exp",
            "experiment_dir": str(tmp_path),
            "config_hash": "test-hash",
            "completed_runs": {"T0": {"00-empty": {"1": "passed", "2": "failed"}}},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

        checkpoint = E2ECheckpoint.from_dict(data)
        # Should be migrated to v3.0
        assert checkpoint.version == "3.0"
        assert checkpoint.experiment_id == "test-exp"
        # completed_runs should be preserved with int keys
        assert 1 in checkpoint.completed_runs["T0"]["00-empty"]
        assert 2 in checkpoint.completed_runs["T0"]["00-empty"]
        # run_states should be derived
        assert checkpoint.get_run_state("T0", "00-empty", 1) == "run_complete"
        assert checkpoint.get_run_state("T0", "00-empty", 2) == "run_complete"

    def test_from_dict_accepts_version_3_0(self, tmp_path: Path) -> None:
        """Verify from_dict accepts version 3.0 directly."""
        data = {
            "version": "3.0",
            "experiment_id": "test-exp",
            "experiment_dir": str(tmp_path),
            "config_hash": "test-hash",
            "completed_runs": {},
            "experiment_state": "tiers_running",
            "tier_states": {},
            "subtest_states": {},
            "run_states": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": "",
            "status": "running",
        }

        checkpoint = E2ECheckpoint.from_dict(data)
        assert checkpoint.version == "3.0"
        assert checkpoint.experiment_id == "test-exp"
        assert checkpoint.experiment_state == "tiers_running"


class TestCheckpointV3StateHelpers:
    """Tests for v3.0 state helper methods."""

    def test_get_run_state_returns_pending_for_unknown(self) -> None:
        """Verify get_run_state() returns pending for an unknown run."""
        checkpoint = E2ECheckpoint(experiment_id="test", experiment_dir=".", config_hash="abc")
        assert checkpoint.get_run_state("T0", "00", 1) == "pending"

    def test_set_and_get_run_state(self) -> None:
        """Verify set_run_state() and get_run_state() round-trip correctly."""
        checkpoint = E2ECheckpoint(experiment_id="test", experiment_dir=".", config_hash="abc")
        checkpoint.set_run_state("T0", "00", 1, "agent_complete")
        assert checkpoint.get_run_state("T0", "00", 1) == "agent_complete"

    def test_get_tier_state_returns_pending_for_unknown(self) -> None:
        """Verify get_tier_state() returns pending for an unknown tier."""
        checkpoint = E2ECheckpoint(experiment_id="test", experiment_dir=".", config_hash="abc")
        assert checkpoint.get_tier_state("T0") == "pending"

    def test_set_and_get_tier_state(self) -> None:
        """Verify set_tier_state() and get_tier_state() round-trip correctly."""
        checkpoint = E2ECheckpoint(experiment_id="test", experiment_dir=".", config_hash="abc")
        checkpoint.set_tier_state("T0", "subtests_running")
        assert checkpoint.get_tier_state("T0") == "subtests_running"

    def test_get_subtest_state_returns_pending_for_unknown(self) -> None:
        """Verify get_subtest_state() returns pending for an unknown subtest."""
        checkpoint = E2ECheckpoint(experiment_id="test", experiment_dir=".", config_hash="abc")
        assert checkpoint.get_subtest_state("T0", "00") == "pending"

    def test_set_and_get_subtest_state(self) -> None:
        """Verify set_subtest_state() and get_subtest_state() round-trip correctly."""
        checkpoint = E2ECheckpoint(experiment_id="test", experiment_dir=".", config_hash="abc")
        checkpoint.set_subtest_state("T0", "00", "runs_in_progress")
        assert checkpoint.get_subtest_state("T0", "00") == "runs_in_progress"

    def test_update_heartbeat(self) -> None:
        """Verify update_heartbeat() sets a non-empty timestamp."""
        checkpoint = E2ECheckpoint(experiment_id="test", experiment_dir=".", config_hash="abc")
        assert checkpoint.last_heartbeat == ""
        checkpoint.update_heartbeat()
        assert checkpoint.last_heartbeat != ""

    def test_set_run_state_updates_last_updated_at(self) -> None:
        """Verify set_run_state() updates last_updated_at timestamp."""
        checkpoint = E2ECheckpoint(experiment_id="test", experiment_dir=".", config_hash="abc")
        before = checkpoint.last_updated_at
        checkpoint.set_run_state("T0", "00", 1, "agent_complete")
        assert checkpoint.last_updated_at >= before


class TestCheckpointV3Migration:
    """Tests for v2.0 -> v3.0 migration."""

    def test_migration_preserves_completed_runs(self, tmp_path: Path) -> None:
        """completed_runs data is preserved during migration."""
        data = {
            "version": "2.0",
            "experiment_id": "test",
            "experiment_dir": str(tmp_path),
            "config_hash": "abc",
            "completed_runs": {"T0": {"00-empty": {"1": "passed"}}},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }
        checkpoint = E2ECheckpoint.from_dict(data)
        assert checkpoint.get_run_status("T0", "00-empty", 1) == "passed"

    def test_migration_sets_agent_complete_state(self, tmp_path: Path) -> None:
        """agent_complete status maps to agent_complete run state."""
        data = {
            "version": "2.0",
            "experiment_id": "test",
            "experiment_dir": str(tmp_path),
            "config_hash": "abc",
            "completed_runs": {"T0": {"00-empty": {"1": "agent_complete"}}},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }
        checkpoint = E2ECheckpoint.from_dict(data)
        assert checkpoint.get_run_state("T0", "00-empty", 1) == "agent_complete"

    def test_migration_derives_experiment_state(self, tmp_path: Path) -> None:
        """experiment_state is set to tiers_running during migration."""
        data = {
            "version": "2.0",
            "experiment_id": "test",
            "experiment_dir": str(tmp_path),
            "config_hash": "abc",
            "completed_runs": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }
        checkpoint = E2ECheckpoint.from_dict(data)
        assert checkpoint.experiment_state == "tiers_running"

    def test_v3_checkpoint_roundtrip(self, tmp_path: Path) -> None:
        """Save and load v3.0 checkpoint preserves all state fields."""
        checkpoint = E2ECheckpoint(
            experiment_id="test",
            experiment_dir=str(tmp_path),
            config_hash="abc",
            status="running",
            experiment_state="tiers_running",
        )
        checkpoint.set_run_state("T0", "00", 1, "agent_complete")
        checkpoint.set_tier_state("T0", "subtests_running")
        checkpoint.set_subtest_state("T0", "00", "runs_in_progress")
        checkpoint.update_heartbeat()

        path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, path)

        reloaded = load_checkpoint(path)
        assert reloaded.version == "3.0"
        assert reloaded.experiment_state == "tiers_running"
        assert reloaded.get_run_state("T0", "00", 1) == "agent_complete"
        assert reloaded.get_tier_state("T0") == "subtests_running"
        assert reloaded.get_subtest_state("T0", "00") == "runs_in_progress"
        assert reloaded.last_heartbeat != ""


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
