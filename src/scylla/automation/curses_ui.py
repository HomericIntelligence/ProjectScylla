"""Curses-based UI for parallel worker visualization.

Provides:
- Thread-safe log buffer management
- Real-time status display with curses
- Per-thread log routing
"""

import atexit
import contextlib
import curses
import logging
import threading
import time
from collections import deque
from typing import Any

from .status_tracker import StatusTracker

logger = logging.getLogger(__name__)


class LogBuffer:
    """Thread-safe circular log buffer."""

    def __init__(self, maxlen: int = 1000):
        """Initialize log buffer.

        Args:
            maxlen: Maximum number of log entries to keep

        """
        self.buffer: deque[str] = deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def append(self, message: str) -> None:
        """Append a log message.

        Args:
            message: Log message to append

        """
        with self.lock:
            self.buffer.append(message)

    def get_recent(self, n: int) -> list[str]:
        """Get the n most recent log entries.

        Args:
            n: Number of entries to retrieve

        Returns:
            List of recent log messages

        """
        with self.lock:
            return list(self.buffer)[-n:]

    def clear(self) -> None:
        """Clear the log buffer."""
        with self.lock:
            self.buffer.clear()


class ThreadLogManager:
    """Manager for per-thread log buffers.

    Routes log messages to thread-specific buffers for organized display.
    """

    def __init__(self) -> None:
        """Initialize thread log manager."""
        self.buffers: dict[int, LogBuffer] = {}
        self.lock = threading.Lock()

    def get_buffer(self, thread_id: int) -> LogBuffer:
        """Get log buffer for a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            LogBuffer for the thread

        """
        with self.lock:
            if thread_id not in self.buffers:
                self.buffers[thread_id] = LogBuffer()
            return self.buffers[thread_id]

    def log(self, thread_id: int, message: str) -> None:
        """Log a message to a thread's buffer.

        Args:
            thread_id: Thread identifier
            message: Log message

        """
        buffer = self.get_buffer(thread_id)
        buffer.append(message)


class CursesUI:
    """Curses-based UI for displaying worker status and logs.

    Displays:
    - Real-time worker status slots
    - Recent log messages
    - Progress indicators
    """

    def __init__(
        self,
        status_tracker: StatusTracker,
        log_manager: ThreadLogManager,
    ):
        """Initialize curses UI.

        Args:
            status_tracker: StatusTracker instance
            log_manager: ThreadLogManager instance

        """
        self.status_tracker = status_tracker
        self.log_manager = log_manager
        self.stdscr: Any = None
        self.running = False
        self.thread: threading.Thread | None = None

    def _emergency_cleanup(self) -> None:
        """Emergency cleanup for atexit — restores terminal if stop() was not called."""
        with contextlib.suppress(Exception):
            curses.endwin()
        from scylla.utils.terminal import restore_terminal

        restore_terminal()

    def start(self) -> None:
        """Start the curses UI in a background thread."""
        if self.running:
            logger.warning("CursesUI already running")
            return

        self.running = True
        atexit.register(self._emergency_cleanup)
        self.thread = threading.Thread(target=self._run_ui, daemon=True)
        self.thread.start()
        logger.debug("Started CursesUI thread")

    def stop(self) -> None:
        """Stop the curses UI."""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        atexit.unregister(self._emergency_cleanup)
        logger.debug("Stopped CursesUI")

    def _run_ui(self) -> None:
        """Run the curses UI loop."""
        try:
            curses.wrapper(self._curses_main)
        except Exception as e:
            logger.error(f"CursesUI error: {e}")
        finally:
            # Always reset running flag so UI can be restarted
            self.running = False

    def _curses_main(self, stdscr: Any) -> None:
        """Run the main curses loop.

        Args:
            stdscr: Curses standard screen object

        """
        self.stdscr = stdscr
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(True)  # Non-blocking input

        # Initialize color pairs if available
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)

        while self.running:
            try:
                self._refresh_display()
                time.sleep(0.5)  # Update twice per second
            except curses.error:
                # Terminal too small or other display error
                pass
            except KeyboardInterrupt:
                break

    def _refresh_display(self) -> None:  # noqa: C901  # TUI rendering with many display states
        """Refresh the curses display."""
        if not self.stdscr:
            return

        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()

        # Display title
        title = "ProjectScylla Issue Implementer"
        if len(title) < width:
            self.stdscr.addstr(0, 0, title, curses.A_BOLD)

        # Display worker status slots
        statuses = self.status_tracker.get_status()
        row = 2
        for i, status in enumerate(statuses):
            if row >= height - 1:
                break

            if status is None:
                status_text = f"Worker {i}: [idle]"
                attr = curses.color_pair(1) if curses.has_colors() else curses.A_DIM
            else:
                status_text = f"Worker {i}: {status}"
                attr = curses.color_pair(2) if curses.has_colors() else curses.A_NORMAL

            # Truncate to fit width
            if len(status_text) > width - 1:
                status_text = status_text[: width - 4] + "..."

            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, 0, status_text, attr)

            row += 1

        # Display separator
        if row < height - 1:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, 0, "-" * min(width - 1, 80))
            row += 1

        # Display recent logs
        if row < height - 1:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, 0, "Recent Activity:", curses.A_BOLD)
            row += 1

            # Gather recent logs from all threads
            all_logs: list[str] = []
            # Take snapshot to avoid RuntimeError if dict changes during iteration
            for buffer in list(self.log_manager.buffers.values()):
                all_logs.extend(buffer.get_recent(10))

            # Display most recent logs
            for log_msg in all_logs[-(height - row - 1) :]:
                if row >= height - 1:
                    break

                # Truncate to fit width
                if len(log_msg) > width - 1:
                    log_msg = log_msg[: width - 4] + "..."

                with contextlib.suppress(curses.error):
                    self.stdscr.addstr(row, 0, log_msg)

                row += 1

        self.stdscr.refresh()
