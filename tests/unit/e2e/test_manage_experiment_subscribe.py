"""cmd_subscribe tests for scripts/manage_experiment.py."""

from __future__ import annotations

import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

from manage_experiment import build_parser

# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


class TestBuildParserSubscribe:
    """Tests for subscribe subcommand registration in build_parser()."""

    def test_subscribe_subcommand_registered(self) -> None:
        """'subscribe' is registered as a subcommand in build_parser()."""
        parser = build_parser()
        subparsers_action = next(
            action for action in parser._actions if hasattr(action, "choices") and action.choices
        )
        assert "subscribe" in subparsers_action.choices


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


class TestSubscribeArgs:
    """Tests for subscribe subcommand argument parsing."""

    def test_config_dir_default(self) -> None:
        """--config-dir defaults to current directory."""
        parser = build_parser()
        args = parser.parse_args(["subscribe"])
        assert args.config_dir == Path(".")
        assert args.subcommand == "subscribe"

    def test_config_dir_custom(self) -> None:
        """--config-dir accepts a custom path."""
        parser = build_parser()
        args = parser.parse_args(["subscribe", "--config-dir", "/custom/path"])
        assert args.config_dir == Path("/custom/path")


# ---------------------------------------------------------------------------
# cmd_subscribe — error paths
# ---------------------------------------------------------------------------


class TestCmdSubscribeErrors:
    """Tests for cmd_subscribe() error handling."""

    def test_nats_disabled_returns_1(self, tmp_path: Path) -> None:
        """Returns 1 when NATS is disabled in config."""
        from manage_experiment import cmd_subscribe

        mock_defaults = MagicMock()
        mock_defaults.nats.enabled = False

        mock_loader = MagicMock()
        mock_loader.load_defaults.return_value = mock_defaults

        parser = build_parser()
        args = parser.parse_args(["subscribe", "--config-dir", str(tmp_path)])

        with patch("scylla.config.ConfigLoader", return_value=mock_loader):
            result = cmd_subscribe(args)

        assert result == 1

    def test_missing_config_returns_1(self, tmp_path: Path) -> None:
        """Returns 1 when ConfigLoader raises ConfigurationError."""
        from manage_experiment import cmd_subscribe

        from scylla.config import ConfigurationError

        mock_loader = MagicMock()
        mock_loader.load_defaults.side_effect = ConfigurationError("defaults.yaml not found")

        parser = build_parser()
        args = parser.parse_args(["subscribe", "--config-dir", str(tmp_path)])

        with patch("scylla.config.ConfigLoader", return_value=mock_loader):
            result = cmd_subscribe(args)

        assert result == 1

    def test_nats_import_error_returns_1(self, tmp_path: Path) -> None:
        """Returns 1 when scylla.nats cannot be imported."""
        from manage_experiment import cmd_subscribe

        mock_defaults = MagicMock()
        mock_defaults.nats.enabled = True

        mock_loader = MagicMock()
        mock_loader.load_defaults.return_value = mock_defaults

        parser = build_parser()
        args = parser.parse_args(["subscribe", "--config-dir", str(tmp_path)])

        with (
            patch("scylla.config.ConfigLoader", return_value=mock_loader),
            patch.dict("sys.modules", {"scylla.nats": None}),
        ):
            result = cmd_subscribe(args)

        assert result == 1

    def test_missing_nats_attribute_returns_1(self, tmp_path: Path) -> None:
        """Returns 1 when DefaultsConfig has no .nats attribute."""
        from manage_experiment import cmd_subscribe

        mock_defaults = MagicMock(spec=[])  # empty spec — no attributes

        mock_loader = MagicMock()
        mock_loader.load_defaults.return_value = mock_defaults

        parser = build_parser()
        args = parser.parse_args(["subscribe", "--config-dir", str(tmp_path)])

        with patch("scylla.config.ConfigLoader", return_value=mock_loader):
            result = cmd_subscribe(args)

        assert result == 1


# ---------------------------------------------------------------------------
# cmd_subscribe — happy path
# ---------------------------------------------------------------------------


class TestCmdSubscribeStartStop:
    """Tests for cmd_subscribe() subscriber lifecycle."""

    def test_subscriber_started_and_stopped(self, tmp_path: Path) -> None:
        """Subscriber is started and cleanly stopped on shutdown signal."""
        from manage_experiment import cmd_subscribe

        mock_defaults = MagicMock()
        mock_defaults.nats.enabled = True
        mock_defaults.nats.url = "nats://localhost:4222"
        mock_defaults.nats.stream = "TASKS"
        mock_defaults.logging.level = "INFO"
        mock_defaults.logging.format = "%(message)s"

        mock_loader = MagicMock()
        mock_loader.load_defaults.return_value = mock_defaults

        mock_subscriber = MagicMock()
        mock_router = MagicMock()

        # Make the subscriber thread module mock
        mock_nats_module = MagicMock()
        mock_nats_module.NATSSubscriberThread.return_value = mock_subscriber
        mock_nats_module.create_default_router.return_value = mock_router

        parser = build_parser()
        args = parser.parse_args(["subscribe", "--config-dir", str(tmp_path)])

        original_signal = signal.getsignal(signal.SIGINT)

        # Simulate: after subscriber.start(), immediately fire the stop event
        def _start_side_effect() -> None:
            # Find the signal handler that was registered and invoke it
            # to simulate Ctrl+C
            handler = signal.getsignal(signal.SIGINT)
            if callable(handler):
                handler(signal.SIGINT, None)

        mock_subscriber.start.side_effect = _start_side_effect

        try:
            with (
                patch("scylla.config.ConfigLoader", return_value=mock_loader),
                patch.dict("sys.modules", {"scylla.nats": mock_nats_module}),
            ):
                result = cmd_subscribe(args)
        finally:
            signal.signal(signal.SIGINT, original_signal)

        assert result == 0
        mock_nats_module.NATSSubscriberThread.assert_called_once_with(
            config=mock_defaults.nats,
            handler=mock_router.dispatch,
        )
        mock_subscriber.start.assert_called_once()
        mock_subscriber.stop.assert_called_once()
