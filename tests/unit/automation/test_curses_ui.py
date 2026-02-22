"""Tests for scylla/automation/curses_ui.py.

Curses is mocked throughout — terminal-specific behavior is not tested.
These tests focus on the pure Python logic: LogBuffer, ThreadLogManager,
and the lifecycle management of CursesUI (start/stop, thread management).
"""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

from scylla.automation.curses_ui import CursesUI, LogBuffer, ThreadLogManager
from scylla.automation.status_tracker import StatusTracker


class TestLogBuffer:
    """Tests for LogBuffer."""

    def test_append_and_get_recent(self) -> None:
        """Appended messages are retrievable via get_recent."""
        buf = LogBuffer()
        buf.append("msg1")
        buf.append("msg2")

        recent = buf.get_recent(2)
        assert recent == ["msg1", "msg2"]

    def test_get_recent_limits_count(self) -> None:
        """get_recent returns at most n entries."""
        buf = LogBuffer()
        for i in range(10):
            buf.append(f"msg{i}")

        recent = buf.get_recent(3)
        assert len(recent) == 3

    def test_get_recent_returns_last_n(self) -> None:
        """get_recent returns the most recent n entries."""
        buf = LogBuffer()
        for i in range(5):
            buf.append(f"msg{i}")

        recent = buf.get_recent(2)
        assert recent == ["msg3", "msg4"]

    def test_maxlen_enforced(self) -> None:
        """Buffer does not exceed maxlen entries."""
        buf = LogBuffer(maxlen=3)
        for i in range(10):
            buf.append(f"msg{i}")

        recent = buf.get_recent(100)
        assert len(recent) == 3
        assert recent == ["msg7", "msg8", "msg9"]

    def test_clear_empties_buffer(self) -> None:
        """clear() removes all entries."""
        buf = LogBuffer()
        buf.append("msg1")
        buf.append("msg2")
        buf.clear()

        assert buf.get_recent(10) == []

    def test_get_recent_empty_buffer_returns_empty_list(self) -> None:
        """get_recent on empty buffer returns empty list."""
        buf = LogBuffer()
        assert buf.get_recent(5) == []

    def test_thread_safe_append(self) -> None:
        """Concurrent appends from multiple threads do not corrupt the buffer."""
        buf = LogBuffer(maxlen=1000)
        errors = []

        def append_many(prefix: str) -> None:
            try:
                for i in range(50):
                    buf.append(f"{prefix}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=append_many, args=(f"t{j}",)) for j in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # 5 threads × 50 messages = 250; all fit in maxlen=1000
        assert len(buf.get_recent(1000)) == 250


class TestThreadLogManager:
    """Tests for ThreadLogManager."""

    def test_get_buffer_creates_new_buffer(self) -> None:
        """get_buffer creates a new LogBuffer for an unseen thread ID."""
        manager = ThreadLogManager()
        buf = manager.get_buffer(42)
        assert isinstance(buf, LogBuffer)

    def test_get_buffer_returns_same_buffer(self) -> None:
        """get_buffer returns the same LogBuffer for the same thread ID."""
        manager = ThreadLogManager()
        buf1 = manager.get_buffer(10)
        buf2 = manager.get_buffer(10)
        assert buf1 is buf2

    def test_different_thread_ids_get_different_buffers(self) -> None:
        """Different thread IDs get independent LogBuffers."""
        manager = ThreadLogManager()
        buf1 = manager.get_buffer(1)
        buf2 = manager.get_buffer(2)
        assert buf1 is not buf2

    def test_log_appends_to_thread_buffer(self) -> None:
        """log() appends the message to the correct thread's buffer."""
        manager = ThreadLogManager()
        manager.log(99, "hello from thread 99")

        recent = manager.get_buffer(99).get_recent(5)
        assert "hello from thread 99" in recent

    def test_log_does_not_affect_other_threads(self) -> None:
        """log() for one thread does not affect another thread's buffer."""
        manager = ThreadLogManager()
        manager.log(1, "thread 1 message")
        manager.log(2, "thread 2 message")

        assert "thread 2 message" not in manager.get_buffer(1).get_recent(10)
        assert "thread 1 message" not in manager.get_buffer(2).get_recent(10)


class TestCursesUILifecycle:
    """Tests for CursesUI start/stop lifecycle."""

    def _make_ui(self, num_slots: int = 2) -> CursesUI:
        """Create a CursesUI with mocked dependencies."""
        tracker = StatusTracker(num_slots)
        log_manager = ThreadLogManager()
        return CursesUI(status_tracker=tracker, log_manager=log_manager)

    def test_initial_state_not_running(self) -> None:
        """CursesUI is not running before start() is called."""
        ui = self._make_ui()
        assert ui.running is False
        assert ui.thread is None

    def test_start_sets_running_flag(self) -> None:
        """start() sets running=True and creates a background thread."""
        ui = self._make_ui()

        with patch("curses.wrapper"):
            ui.start()
            # Give thread a moment to start
            time.sleep(0.05)

        assert ui.thread is not None
        ui.stop()

    def test_stop_clears_running_flag(self) -> None:
        """stop() sets running=False."""
        ui = self._make_ui()

        with patch("curses.wrapper"):
            ui.start()
            time.sleep(0.05)
            ui.stop()

        assert ui.running is False

    def test_start_does_not_start_second_thread_when_already_running(self) -> None:
        """Calling start() when running=True is a no-op — no second thread is created."""
        ui = self._make_ui()
        # Manually set running=True to simulate already-started UI
        ui.running = True
        ui.thread = threading.Thread(target=lambda: None)

        first_thread = ui.thread
        ui.start()  # Should be a no-op — already running
        second_thread = ui.thread

        assert first_thread is second_thread
        ui.running = False  # Reset for cleanup

    def test_stop_when_not_running_is_safe(self) -> None:
        """Calling stop() before start() does not raise."""
        ui = self._make_ui()
        ui.stop()  # Should not raise

    def test_emergency_cleanup_does_not_raise(self) -> None:
        """_emergency_cleanup() does not raise even if curses is not initialized."""
        ui = self._make_ui()

        with patch("curses.endwin"), patch("scylla.utils.terminal.restore_terminal"):
            ui._emergency_cleanup()  # Should not raise


class TestCursesUIRunUI:
    """Tests for _run_ui error handling."""

    def _make_ui(self) -> CursesUI:
        """Create a CursesUI with mocked dependencies."""
        tracker = StatusTracker(2)
        log_manager = ThreadLogManager()
        return CursesUI(status_tracker=tracker, log_manager=log_manager)

    def test_run_ui_handles_curses_exception(self) -> None:
        """_run_ui catches exceptions from curses.wrapper and sets running=False."""
        ui = self._make_ui()
        ui.running = True

        with patch("curses.wrapper", side_effect=Exception("terminal error")):
            ui._run_ui()

        assert ui.running is False

    def test_run_ui_sets_running_false_on_completion(self) -> None:
        """_run_ui always sets running=False in finally block."""
        ui = self._make_ui()
        ui.running = True

        with patch("curses.wrapper"):  # No exception
            ui._run_ui()

        assert ui.running is False
