"""Integration tests for zombie detection + resume flow.

Validates that a checkpoint with status=running and a dead PID / stale heartbeat
is detected as a zombie and reset to 'interrupted' by ResumeManager.handle_zombie().

These are integration tests — they exercise real disk I/O via save_checkpoint /
load_checkpoint against a temp directory, with no mocking of file operations.

Covers:
1. Core zombie case: dead PID + stale heartbeat → status reset to 'interrupted'
2. State data preservation: run/subtest/tier states survive the zombie reset
3. Non-zombie case: fresh heartbeat → checkpoint left unchanged
4. experiment_dir=None is a no-op — no disk write occurs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, load_checkpoint, save_checkpoint
from scylla.e2e.models import ExperimentConfig
from scylla.e2e.resume_manager import ResumeManager
from tests.integration.e2e.conftest import make_checkpoint

pytestmark = pytest.mark.integration

# A PID that is guaranteed to be dead: Linux's max PID is 4,194,304.
# Using 999_999_999 avoids any need to mock os.kill.
_DEAD_PID = 999_999_999

# Heartbeat ages in seconds
_STALE_HEARTBEAT_AGE = 300  # well past the 120s default timeout
_FRESH_HEARTBEAT_AGE = 10  # well within the 120s default timeout


def _stale_heartbeat() -> str:
    """Return an ISO timestamp 300 seconds in the past."""
    return (datetime.now(timezone.utc) - timedelta(seconds=_STALE_HEARTBEAT_AGE)).isoformat()


def _fresh_heartbeat() -> str:
    """Return an ISO timestamp 10 seconds in the past."""
    return (datetime.now(timezone.utc) - timedelta(seconds=_FRESH_HEARTBEAT_AGE)).isoformat()


def _make_resume_manager(checkpoint: E2ECheckpoint) -> ResumeManager:
    """Build a ResumeManager with a minimal mock config and tier_manager."""
    config = MagicMock(spec=ExperimentConfig)
    tier_manager = MagicMock()
    return ResumeManager(checkpoint, config, tier_manager)


class TestZombieResetsStatusToInterrupted:
    """Core case from the issue: dead PID + stale heartbeat → interrupted."""

    def test_status_is_interrupted_after_handle_zombie(self, tmp_path: Path) -> None:
        """handle_zombie() resets checkpoint.status to 'interrupted' for a zombie."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_stale_heartbeat(),
            experiment_dir=str(tmp_path),
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        rm = _make_resume_manager(cp)
        _, updated_cp = rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=tmp_path,
            heartbeat_timeout_seconds=120,
        )

        assert updated_cp.status == "interrupted"

    def test_disk_checkpoint_is_interrupted_after_handle_zombie(self, tmp_path: Path) -> None:
        """handle_zombie() persists the 'interrupted' status to disk."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_stale_heartbeat(),
            experiment_dir=str(tmp_path),
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        rm = _make_resume_manager(cp)
        rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=tmp_path,
            heartbeat_timeout_seconds=120,
        )

        on_disk = load_checkpoint(cp_path)
        assert on_disk.status == "interrupted"


class TestZombieResetPreservesStateData:
    """Zombie reset must not lose any run/subtest/tier state data."""

    def test_run_states_preserved(self, tmp_path: Path) -> None:
        """run_states survive a zombie reset unchanged."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_stale_heartbeat(),
            experiment_dir=str(tmp_path),
            run_states={"T0": {"00": {"1": "replay_generated", "2": "worktree_cleaned"}}},
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        rm = _make_resume_manager(cp)
        _, updated_cp = rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=tmp_path,
            heartbeat_timeout_seconds=120,
        )

        assert updated_cp.run_states == {
            "T0": {"00": {"1": "replay_generated", "2": "worktree_cleaned"}}
        }

    def test_subtest_states_preserved(self, tmp_path: Path) -> None:
        """subtest_states survive a zombie reset unchanged."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_stale_heartbeat(),
            experiment_dir=str(tmp_path),
            subtest_states={"T0": {"00": "aggregated"}},
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        rm = _make_resume_manager(cp)
        _, updated_cp = rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=tmp_path,
            heartbeat_timeout_seconds=120,
        )

        assert updated_cp.subtest_states == {"T0": {"00": "aggregated"}}

    def test_tier_states_preserved(self, tmp_path: Path) -> None:
        """tier_states survive a zombie reset unchanged."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_stale_heartbeat(),
            experiment_dir=str(tmp_path),
            tier_states={"T0": "complete", "T1": "config_loaded"},
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        rm = _make_resume_manager(cp)
        _, updated_cp = rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=tmp_path,
            heartbeat_timeout_seconds=120,
        )

        assert updated_cp.tier_states == {"T0": "complete", "T1": "config_loaded"}

    def test_experiment_state_preserved(self, tmp_path: Path) -> None:
        """experiment_state survives a zombie reset unchanged."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_stale_heartbeat(),
            experiment_dir=str(tmp_path),
            experiment_state="subtests_running",
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        rm = _make_resume_manager(cp)
        _, updated_cp = rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=tmp_path,
            heartbeat_timeout_seconds=120,
        )

        assert updated_cp.experiment_state == "subtests_running"


class TestNonZombieCheckpointUnchanged:
    """Fresh heartbeat → handle_zombie() must leave checkpoint untouched."""

    def test_fresh_heartbeat_status_unchanged(self, tmp_path: Path) -> None:
        """Checkpoint with a fresh heartbeat is not reset."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_fresh_heartbeat(),
            experiment_dir=str(tmp_path),
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        rm = _make_resume_manager(cp)
        _, updated_cp = rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=tmp_path,
            heartbeat_timeout_seconds=120,
        )

        assert updated_cp.status == "running"

    def test_fresh_heartbeat_disk_checkpoint_unchanged(self, tmp_path: Path) -> None:
        """Disk checkpoint is not modified when heartbeat is fresh."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_fresh_heartbeat(),
            experiment_dir=str(tmp_path),
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        original_mtime = cp_path.stat().st_mtime

        rm = _make_resume_manager(cp)
        rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=tmp_path,
            heartbeat_timeout_seconds=120,
        )

        assert cp_path.stat().st_mtime == original_mtime

    def test_non_running_status_not_reset(self, tmp_path: Path) -> None:
        """A checkpoint with status != 'running' is never treated as a zombie."""
        for status in ("interrupted", "completed", "failed", "paused_rate_limit"):
            cp = make_checkpoint(
                status=status,
                pid=_DEAD_PID,
                last_heartbeat=_stale_heartbeat(),
                experiment_dir=str(tmp_path),
            )
            cp_path = tmp_path / f"checkpoint_{status}.json"
            save_checkpoint(cp, cp_path)

            rm = _make_resume_manager(cp)
            _, updated_cp = rm.handle_zombie(
                checkpoint_path=cp_path,
                experiment_dir=tmp_path,
                heartbeat_timeout_seconds=120,
            )

            assert updated_cp.status == status, f"status={status!r} should not be changed"


class TestExperimentDirNoneIsNoop:
    """experiment_dir=None makes handle_zombie() a complete no-op."""

    def test_returns_unchanged_checkpoint(self, tmp_path: Path) -> None:
        """handle_zombie(experiment_dir=None) returns the original checkpoint."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_stale_heartbeat(),
            experiment_dir=str(tmp_path),
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        rm = _make_resume_manager(cp)
        _, updated_cp = rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=None,
        )

        assert updated_cp.status == "running"

    def test_no_disk_write_when_experiment_dir_none(self, tmp_path: Path) -> None:
        """handle_zombie(experiment_dir=None) does not write to disk."""
        cp = make_checkpoint(
            status="running",
            pid=_DEAD_PID,
            last_heartbeat=_stale_heartbeat(),
            experiment_dir=str(tmp_path),
        )
        # Do not write checkpoint to disk first — verify no file is created
        cp_path = tmp_path / "checkpoint.json"

        rm = _make_resume_manager(cp)
        rm.handle_zombie(
            checkpoint_path=cp_path,
            experiment_dir=None,
        )

        assert not cp_path.exists()
