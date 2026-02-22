"""Tests for scylla.utils.terminal."""

from __future__ import annotations

import signal
import sys
from unittest.mock import MagicMock, patch

import pytest

import scylla.utils.terminal as terminal_module
from scylla.utils.terminal import install_signal_handlers, restore_terminal, terminal_guard

# ---------------------------------------------------------------------------
# restore_terminal
# ---------------------------------------------------------------------------


class TestRestoreTerminal:
    """Tests for restore_terminal()."""

    def test_calls_stty_sane_when_tty(self) -> None:
        """Calls stty sane when stdin is a TTY."""
        with (
            patch.object(sys.stdin, "isatty", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            restore_terminal()
            mock_run.assert_called_once_with(["stty", "sane"], stdin=sys.stdin, check=False)

    def test_no_op_when_not_tty(self) -> None:
        """Does not call stty sane when stdin is not a TTY."""
        with (
            patch.object(sys.stdin, "isatty", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            restore_terminal()
            mock_run.assert_not_called()

    def test_swallows_subprocess_exception(self) -> None:
        """Does not raise when stty subprocess fails."""
        with (
            patch.object(sys.stdin, "isatty", return_value=True),
            patch("subprocess.run", side_effect=OSError("stty not found")),
        ):
            # Must not raise
            restore_terminal()

    def test_swallows_any_exception(self) -> None:
        """Does not raise when isatty() itself raises."""
        with (
            patch.object(sys.stdin, "isatty", side_effect=RuntimeError("boom")),
        ):
            # Outer try/except swallows all exceptions
            try:
                restore_terminal()
            except RuntimeError:
                pytest.fail("restore_terminal must not raise")


# ---------------------------------------------------------------------------
# install_signal_handlers
# ---------------------------------------------------------------------------


class TestInstallSignalHandlers:
    """Tests for install_signal_handlers()."""

    def _get_handler(self, signum: int) -> object:
        """Return the currently installed handler for signum."""
        return signal.getsignal(signum)

    def test_first_sigint_calls_shutdown_fn(self) -> None:
        """First SIGINT calls the shutdown function."""
        shutdown_fn = MagicMock()
        install_signal_handlers(shutdown_fn)

        handler = self._get_handler(signal.SIGINT)
        assert callable(handler)

        # Simulate first Ctrl+C
        handler(signal.SIGINT, None)  # type: ignore[call-arg]
        shutdown_fn.assert_called_once()

    def test_second_sigint_raises_systemexit(self) -> None:
        """Second SIGINT forces sys.exit(128 + signum)."""
        shutdown_fn = MagicMock()
        install_signal_handlers(shutdown_fn)

        handler = self._get_handler(signal.SIGINT)

        # First signal — sets the flag
        handler(signal.SIGINT, None)  # type: ignore[call-arg]

        # Second signal — must force-exit
        with (
            patch.object(terminal_module, "restore_terminal"),
            pytest.raises(SystemExit) as exc_info,
        ):
            handler(signal.SIGINT, None)  # type: ignore[call-arg]

        assert exc_info.value.code == 128 + signal.SIGINT

    def test_second_sigint_restores_terminal(self) -> None:
        """Second SIGINT calls restore_terminal before exiting."""
        shutdown_fn = MagicMock()
        install_signal_handlers(shutdown_fn)

        handler = self._get_handler(signal.SIGINT)
        handler(signal.SIGINT, None)  # type: ignore[call-arg]

        with (
            patch.object(terminal_module, "restore_terminal") as mock_restore,
            pytest.raises(SystemExit),
        ):
            handler(signal.SIGINT, None)  # type: ignore[call-arg]

        mock_restore.assert_called_once()

    def test_reinstall_resets_shutdown_flag(self) -> None:
        """Re-calling install_signal_handlers resets the escalation counter."""
        shutdown_fn = MagicMock()
        install_signal_handlers(shutdown_fn)

        handler = self._get_handler(signal.SIGINT)
        handler(signal.SIGINT, None)  # type: ignore[call-arg]

        # Re-install — flag should be reset
        install_signal_handlers(shutdown_fn)
        handler = self._get_handler(signal.SIGINT)

        # First signal again — should NOT raise SystemExit
        handler(signal.SIGINT, None)  # type: ignore[call-arg]
        assert shutdown_fn.call_count == 2  # called twice total, not force-exited


# ---------------------------------------------------------------------------
# terminal_guard
# ---------------------------------------------------------------------------


class TestTerminalGuard:
    """Tests for terminal_guard() context manager."""

    def test_restores_terminal_on_normal_exit(self) -> None:
        """Calls restore_terminal on normal context exit."""
        with patch.object(terminal_module, "restore_terminal") as mock_restore:
            with terminal_guard():
                pass
            mock_restore.assert_called_once()

    def test_restores_terminal_on_exception(self) -> None:
        """Calls restore_terminal even when body raises an exception."""
        with patch.object(terminal_module, "restore_terminal") as mock_restore:
            with pytest.raises(ValueError), terminal_guard():
                raise ValueError("oops")
            mock_restore.assert_called_once()

    def test_installs_signal_handlers_when_shutdown_fn_provided(self) -> None:
        """Calls install_signal_handlers when shutdown_fn is given."""
        shutdown_fn = MagicMock()
        with (
            patch.object(terminal_module, "install_signal_handlers") as mock_install,
            patch.object(terminal_module, "restore_terminal"),
        ):
            with terminal_guard(shutdown_fn):
                pass
            mock_install.assert_called_once_with(shutdown_fn)

    def test_no_signal_handlers_when_no_shutdown_fn(self) -> None:
        """Does not install signal handlers when shutdown_fn is None."""
        with (
            patch.object(terminal_module, "install_signal_handlers") as mock_install,
            patch.object(terminal_module, "restore_terminal"),
        ):
            with terminal_guard():
                pass
            mock_install.assert_not_called()
