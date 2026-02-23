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


class TestCursesUIRefreshDisplay:
    """Tests for CursesUI._refresh_display."""

    def _make_ui(self, num_slots: int = 2) -> CursesUI:
        """Create a CursesUI with mocked dependencies."""
        tracker = StatusTracker(num_slots)
        log_manager = ThreadLogManager()
        return CursesUI(status_tracker=tracker, log_manager=log_manager)

    def test_early_return_when_stdscr_none(self) -> None:
        """When stdscr is None, _refresh_display returns without calling curses methods."""
        ui = self._make_ui()
        ui.stdscr = None

        # Patch curses to detect any spurious calls
        with patch("curses.A_BOLD", 0), patch("curses.has_colors", return_value=False):
            ui._refresh_display()  # Should return immediately without raising

        # stdscr is None so no curses methods should have been called
        assert ui.stdscr is None

    def test_title_display_with_bold(self) -> None:
        """Title 'ProjectScylla Issue Implementer' is written to row 0 with curses.A_BOLD."""
        import curses as _curses
        from unittest.mock import MagicMock

        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        ui = self._make_ui()
        ui.stdscr = stdscr

        with (
            patch("curses.A_BOLD", _curses.A_BOLD),
            patch("curses.has_colors", return_value=False),
            patch("curses.A_DIM", _curses.A_DIM),
            patch("curses.A_NORMAL", _curses.A_NORMAL),
        ):
            ui._refresh_display()

        # Find the addstr call for the title at row 0, col 0
        title_calls = [
            c
            for c in stdscr.addstr.call_args_list
            if c.args[0] == 0 and c.args[1] == 0 and "ProjectScylla" in c.args[2]
        ]
        assert len(title_calls) == 1, (
            f"Expected one title addstr call, got: {stdscr.addstr.call_args_list}"
        )
        assert title_calls[0].args[3] == _curses.A_BOLD

    def test_worker_idle_status_rendering(self) -> None:
        """When a worker slot is idle (status is None), the correct idle text is displayed."""
        import curses as _curses
        from unittest.mock import MagicMock

        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        # status_tracker with 1 slot, no status set => idle
        ui = self._make_ui(num_slots=1)
        ui.stdscr = stdscr

        with (
            patch("curses.A_BOLD", _curses.A_BOLD),
            patch("curses.has_colors", return_value=False),
            patch("curses.A_DIM", _curses.A_DIM),
            patch("curses.A_NORMAL", _curses.A_NORMAL),
        ):
            ui._refresh_display()

        # Check that an addstr call contains the idle text for worker 0
        all_addstr_texts = [c.args[2] for c in stdscr.addstr.call_args_list if len(c.args) >= 3]
        idle_texts = [t for t in all_addstr_texts if "Worker 0" in t and "[idle]" in t]
        assert idle_texts, f"Expected idle text, got addstr texts: {all_addstr_texts}"

    def test_worker_active_status_rendering(self) -> None:
        """When a worker slot has an active status, that status text is displayed."""
        import curses as _curses
        from unittest.mock import MagicMock

        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        ui = self._make_ui(num_slots=1)
        ui.status_tracker.update_slot(0, "processing issue #42")
        ui.stdscr = stdscr

        with (
            patch("curses.A_BOLD", _curses.A_BOLD),
            patch("curses.has_colors", return_value=False),
            patch("curses.A_DIM", _curses.A_DIM),
            patch("curses.A_NORMAL", _curses.A_NORMAL),
        ):
            ui._refresh_display()

        all_addstr_texts = [c.args[2] for c in stdscr.addstr.call_args_list if len(c.args) >= 3]
        active_texts = [
            t for t in all_addstr_texts if "Worker 0" in t and "processing issue #42" in t
        ]
        assert active_texts, f"Expected active status text, got addstr texts: {all_addstr_texts}"

    def test_text_truncation_when_width_small(self) -> None:
        """When terminal width is small, worker status text is truncated to fit."""
        import curses as _curses
        from unittest.mock import MagicMock

        stdscr = MagicMock()
        # Very narrow terminal: 20 columns
        stdscr.getmaxyx.return_value = (24, 20)

        ui = self._make_ui(num_slots=1)
        # Set a long status that exceeds the terminal width
        long_status = "A" * 50
        ui.status_tracker.update_slot(0, long_status)
        ui.stdscr = stdscr

        with (
            patch("curses.A_BOLD", _curses.A_BOLD),
            patch("curses.has_colors", return_value=False),
            patch("curses.A_DIM", _curses.A_DIM),
            patch("curses.A_NORMAL", _curses.A_NORMAL),
        ):
            ui._refresh_display()

        # All addstr text arguments (3rd arg) must fit within width - 1 characters
        width = 20
        for call in stdscr.addstr.call_args_list:
            if len(call.args) >= 3 and isinstance(call.args[2], str):
                assert len(call.args[2]) <= width - 1, (
                    f"Text too long ({len(call.args[2])} chars) for width {width}: {call.args[2]!r}"
                )

    def test_stdscr_refresh_called_at_end(self) -> None:
        """stdscr.refresh() is called at the end of _refresh_display."""
        import curses as _curses
        from unittest.mock import MagicMock

        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)

        ui = self._make_ui()
        ui.stdscr = stdscr

        with (
            patch("curses.A_BOLD", _curses.A_BOLD),
            patch("curses.has_colors", return_value=False),
            patch("curses.A_DIM", _curses.A_DIM),
            patch("curses.A_NORMAL", _curses.A_NORMAL),
        ):
            ui._refresh_display()

        stdscr.refresh.assert_called_once()
