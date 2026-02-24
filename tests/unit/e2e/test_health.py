"""Unit tests for health monitoring module.

Tests cover:
- _pid_is_alive() for live, dead, and current process
- _heartbeat_is_stale() for fresh, stale, and missing heartbeats
- is_zombie() detection logic (all three conditions)
- reset_zombie_checkpoint() updates status and saves checkpoint
- HeartbeatThread updates heartbeat periodically and stops cleanly
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, load_checkpoint, save_checkpoint
from scylla.e2e.health import (
    HeartbeatThread,
    _heartbeat_is_stale,
    _pid_is_alive,
    is_zombie,
    reset_zombie_checkpoint,
)

# ---------------------------------------------------------------------------
# _pid_is_alive tests
# ---------------------------------------------------------------------------


class TestPidIsAlive:
    """Tests for _pid_is_alive() helper function."""

    def test_current_process_is_alive(self) -> None:
        """Verify _pid_is_alive() returns True for the current process."""
        assert _pid_is_alive(os.getpid()) is True

    def test_very_high_pid_is_dead(self) -> None:
        """Verify _pid_is_alive() returns False for a PID that does not exist."""
        # PID 999999 is extremely unlikely to exist
        assert _pid_is_alive(999999) is False


# ---------------------------------------------------------------------------
# _heartbeat_is_stale tests
# ---------------------------------------------------------------------------


class TestHeartbeatIsStale:
    """Tests for _heartbeat_is_stale() helper function."""

    def test_empty_string_is_stale(self) -> None:
        """Verify an empty string heartbeat is considered stale."""
        assert _heartbeat_is_stale("", timeout_seconds=120) is True

    def test_none_is_stale(self) -> None:
        """Verify a None heartbeat is considered stale."""
        assert _heartbeat_is_stale(None, timeout_seconds=120) is True  # type: ignore[arg-type]

    def test_fresh_heartbeat_is_not_stale(self) -> None:
        """Verify a recent heartbeat timestamp is not stale."""
        fresh = datetime.now(timezone.utc).isoformat()
        assert _heartbeat_is_stale(fresh, timeout_seconds=120) is False

    def test_stale_heartbeat_is_stale(self) -> None:
        """Verify an old heartbeat timestamp is stale."""
        stale = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        assert _heartbeat_is_stale(stale, timeout_seconds=120) is True

    def test_exactly_at_timeout_is_stale(self) -> None:
        """A heartbeat exactly at the timeout boundary is stale (>)."""
        at_boundary = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        # 120s old with 120s timeout -> stale (>)
        assert _heartbeat_is_stale(at_boundary, timeout_seconds=120) is True

    def test_just_before_timeout_is_not_stale(self) -> None:
        """Verify a heartbeat just within the timeout window is not stale."""
        fresh = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        assert _heartbeat_is_stale(fresh, timeout_seconds=120) is False

    def test_unparseable_timestamp_is_stale(self) -> None:
        """Verify an unparseable timestamp is treated as stale."""
        assert _heartbeat_is_stale("not-a-timestamp", timeout_seconds=120) is True

    def test_naive_datetime_is_handled(self) -> None:
        """Verify a naive datetime (no timezone) is handled without raising."""
        # Naive datetime (no timezone) — implementation treats as stale because
        # it cannot safely determine age without timezone info.
        # This is conservative: better to re-run than to skip work.
        naive = datetime.now().isoformat()  # no tzinfo
        # The result depends on implementation; just check it doesn't raise
        result = _heartbeat_is_stale(naive, timeout_seconds=120)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# is_zombie tests
# ---------------------------------------------------------------------------


@pytest.fixture
def running_checkpoint(tmp_path: Path) -> E2ECheckpoint:
    """Create a checkpoint with status=running and a stale heartbeat."""
    return E2ECheckpoint(
        experiment_id="zombie-test",
        experiment_dir=str(tmp_path),
        config_hash="abc",
        status="running",
        pid=999999,  # Dead PID
        last_heartbeat=(datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat(),
        started_at=datetime.now(timezone.utc).isoformat(),
        last_updated_at=datetime.now(timezone.utc).isoformat(),
    )


class TestIsZombie:
    """Tests for is_zombie() function."""

    def test_zombie_detected_dead_pid_stale_heartbeat(
        self, running_checkpoint: E2ECheckpoint, tmp_path: Path
    ) -> None:
        """Verify is_zombie() detects a zombie with a dead PID and stale heartbeat."""
        assert is_zombie(running_checkpoint, tmp_path, heartbeat_timeout_seconds=120) is True

    def test_not_zombie_if_status_not_running(
        self, running_checkpoint: E2ECheckpoint, tmp_path: Path
    ) -> None:
        """Verify is_zombie() returns False when status is not running."""
        running_checkpoint.status = "completed"
        assert is_zombie(running_checkpoint, tmp_path, heartbeat_timeout_seconds=120) is False

    def test_not_zombie_if_pid_is_alive(
        self, running_checkpoint: E2ECheckpoint, tmp_path: Path
    ) -> None:
        """Verify is_zombie() returns False when the PID is still alive."""
        running_checkpoint.pid = os.getpid()  # Current process is alive
        running_checkpoint.last_heartbeat = (
            datetime.now(timezone.utc) - timedelta(seconds=300)
        ).isoformat()
        assert is_zombie(running_checkpoint, tmp_path, heartbeat_timeout_seconds=120) is False

    def test_not_zombie_if_heartbeat_fresh(
        self, running_checkpoint: E2ECheckpoint, tmp_path: Path
    ) -> None:
        """Verify is_zombie() returns False when heartbeat is fresh despite dead PID."""
        # Dead PID but fresh heartbeat -> another process might have taken over
        running_checkpoint.last_heartbeat = datetime.now(timezone.utc).isoformat()
        assert is_zombie(running_checkpoint, tmp_path, heartbeat_timeout_seconds=120) is False

    def test_zombie_detected_via_pid_file(self, tmp_path: Path) -> None:
        """Zombie detected when PID comes from experiment.pid file."""
        checkpoint = E2ECheckpoint(
            experiment_id="zombie-test",
            experiment_dir=str(tmp_path),
            config_hash="abc",
            status="running",
            pid=None,  # No PID in checkpoint
            last_heartbeat=(datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat(),
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
        )
        # Write dead PID to file
        pid_file = tmp_path / "experiment.pid"
        pid_file.write_text("999999")

        assert is_zombie(checkpoint, tmp_path, heartbeat_timeout_seconds=120) is True

    def test_not_zombie_when_no_pid_info_and_fresh_heartbeat(self, tmp_path: Path) -> None:
        """Cannot confirm zombie if no PID info and heartbeat is fresh."""
        checkpoint = E2ECheckpoint(
            experiment_id="test",
            experiment_dir=str(tmp_path),
            config_hash="abc",
            status="running",
            pid=None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
        )
        assert is_zombie(checkpoint, tmp_path, heartbeat_timeout_seconds=120) is False


# ---------------------------------------------------------------------------
# reset_zombie_checkpoint tests
# ---------------------------------------------------------------------------


class TestResetZombieCheckpoint:
    """Tests for reset_zombie_checkpoint() function."""

    def test_sets_status_to_interrupted(
        self, running_checkpoint: E2ECheckpoint, tmp_path: Path
    ) -> None:
        """Verify reset_zombie_checkpoint() sets status to interrupted."""
        path = tmp_path / "checkpoint.json"
        save_checkpoint(running_checkpoint, path)

        result = reset_zombie_checkpoint(running_checkpoint, path)
        assert result.status == "interrupted"

    def test_saves_checkpoint_to_disk(
        self, running_checkpoint: E2ECheckpoint, tmp_path: Path
    ) -> None:
        """Verify reset_zombie_checkpoint() persists the updated status to disk."""
        path = tmp_path / "checkpoint.json"
        save_checkpoint(running_checkpoint, path)

        reset_zombie_checkpoint(running_checkpoint, path)

        # Reload from disk and verify
        reloaded = load_checkpoint(path)
        assert reloaded.status == "interrupted"

    def test_preserves_run_states(self, tmp_path: Path) -> None:
        """Run state data is preserved when resetting zombie."""
        checkpoint = E2ECheckpoint(
            experiment_id="test",
            experiment_dir=str(tmp_path),
            config_hash="abc",
            status="running",
            last_heartbeat=(datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat(),
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
        )
        checkpoint.set_run_state("T0", "00-empty", 1, "agent_complete")
        checkpoint.mark_run_completed("T0", "01-basic", 1, "passed")

        path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, path)

        reset_zombie_checkpoint(checkpoint, path)

        reloaded = load_checkpoint(path)
        assert reloaded.status == "interrupted"
        assert reloaded.get_run_state("T0", "00-empty", 1) == "agent_complete"
        assert reloaded.get_run_status("T0", "01-basic", 1) == "passed"


# ---------------------------------------------------------------------------
# HeartbeatThread tests
# ---------------------------------------------------------------------------


class TestHeartbeatThread:
    """Tests for HeartbeatThread class."""

    def test_heartbeat_updates_periodically(self, tmp_path: Path) -> None:
        """HeartbeatThread updates last_heartbeat within the interval."""
        checkpoint = E2ECheckpoint(
            experiment_id="test",
            experiment_dir=str(tmp_path),
            config_hash="abc",
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
        )
        path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, path)

        thread = HeartbeatThread(checkpoint, path, interval_seconds=1)
        thread.start()

        # Poll until heartbeat appears (up to 10s to tolerate WSL2 load)
        deadline = time.monotonic() + 10
        reloaded = load_checkpoint(path)
        while reloaded.last_heartbeat == "" and time.monotonic() < deadline:
            time.sleep(0.1)
            reloaded = load_checkpoint(path)

        thread.stop()
        thread.join(timeout=5)

        # Heartbeat is now written to disk (not to the in-memory checkpoint object)
        assert reloaded.last_heartbeat != ""
        assert not _heartbeat_is_stale(reloaded.last_heartbeat, timeout_seconds=30)

    def test_heartbeat_thread_stops_cleanly(self, tmp_path: Path) -> None:
        """stop() causes the thread to exit cleanly."""
        checkpoint = E2ECheckpoint(
            experiment_id="test",
            experiment_dir=str(tmp_path),
            config_hash="abc",
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
        )
        path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, path)

        thread = HeartbeatThread(checkpoint, path, interval_seconds=60)
        thread.start()
        assert thread.is_alive()

        thread.stop()
        thread.join(timeout=5)

        # Thread should have stopped
        assert not thread.is_alive()

    def test_heartbeat_thread_is_daemon(self, tmp_path: Path) -> None:
        """HeartbeatThread is a daemon thread so it doesn't block process exit."""
        checkpoint = E2ECheckpoint(
            experiment_id="test",
            experiment_dir=str(tmp_path),
            config_hash="abc",
        )
        path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, path)

        thread = HeartbeatThread(checkpoint, path, interval_seconds=60)
        assert thread.daemon is True

    def test_heartbeat_thread_persists_to_disk(self, tmp_path: Path) -> None:
        """Heartbeat is written to the checkpoint file on disk."""
        checkpoint = E2ECheckpoint(
            experiment_id="test",
            experiment_dir=str(tmp_path),
            config_hash="abc",
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
        )
        path = tmp_path / "checkpoint.json"
        save_checkpoint(checkpoint, path)

        thread = HeartbeatThread(checkpoint, path, interval_seconds=1)
        thread.start()

        # Poll until heartbeat appears (up to 10s to tolerate WSL2 load)
        deadline = time.monotonic() + 10
        reloaded = load_checkpoint(path)
        while reloaded.last_heartbeat == "" and time.monotonic() < deadline:
            time.sleep(0.1)
            reloaded = load_checkpoint(path)

        thread.stop()
        thread.join(timeout=5)

        # Verify heartbeat was written to disk
        assert reloaded.last_heartbeat != ""
        assert not _heartbeat_is_stale(reloaded.last_heartbeat, timeout_seconds=30)
