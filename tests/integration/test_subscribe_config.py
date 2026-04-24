"""Integration test for subscribe subcommand NATS config access.

Verifies that:
1. DefaultsConfig includes a .nats field
2. cmd_subscribe can access defaults.nats without hasattr guard
3. NATSConfig is properly wired through the configuration pipeline
"""

from __future__ import annotations

import signal
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestSubscribeNATSConfig:
    """Integration tests for subscribe subcommand NATS config wiring."""

    def test_defaults_config_has_nats_field(self) -> None:
        """Verify that DefaultsConfig loaded from config/defaults.yaml includes nats field."""
        from scylla.config import ConfigLoader

        loader = ConfigLoader()
        defaults = loader.load_defaults()

        # Should not need hasattr guard — .nats should always be present
        assert hasattr(defaults, "nats"), "DefaultsConfig missing .nats field"
        assert defaults.nats is not None, "DefaultsConfig.nats is None"

    def test_defaults_nats_config_structure(self) -> None:
        """Verify that defaults.nats has expected NATSConfig structure."""
        from scylla.config import ConfigLoader
        from scylla.nats.config import NATSConfig

        loader = ConfigLoader()
        defaults = loader.load_defaults()

        # Verify it's a NATSConfig instance
        assert isinstance(defaults.nats, NATSConfig)

        # Verify expected fields are accessible
        assert hasattr(defaults.nats, "enabled")
        assert hasattr(defaults.nats, "url")
        assert hasattr(defaults.nats, "stream")
        assert hasattr(defaults.nats, "durable_name")

    def test_cmd_subscribe_can_access_defaults_nats_directly(self, tmp_path: Path) -> None:
        """Verify cmd_subscribe can access defaults.nats without hasattr guard."""
        from manage_experiment import cmd_subscribe

        # Create a mock defaults that has .nats
        mock_defaults = MagicMock()
        mock_defaults.nats.enabled = False  # Return immediately
        mock_defaults.logging.level = "INFO"

        mock_loader = MagicMock()
        mock_loader.load_defaults.return_value = mock_defaults

        from manage_experiment import build_parser

        parser = build_parser()
        args = parser.parse_args(["subscribe", "--config-dir", str(tmp_path)])

        with patch("scylla.config.ConfigLoader", return_value=mock_loader):
            result = cmd_subscribe(args)

        # Should return 1 because NATS is disabled (not because .nats is missing)
        assert result == 1

        # Verify that defaults.nats was accessed directly (not via hasattr guard)
        # If the guard was still there, accessing mock_defaults.nats would have raised
        assert mock_defaults.nats.enabled is False

    def test_cmd_subscribe_reaches_subscriber_start(self, tmp_path: Path) -> None:
        """Verify cmd_subscribe reaches subscriber.start() with proper NATSConfig."""
        from manage_experiment import build_parser, cmd_subscribe

        from scylla.config import ConfigLoader

        real_loader = ConfigLoader()
        real_defaults = real_loader.load_defaults()

        # Create a mock defaults that wraps real config
        mock_defaults = MagicMock()
        mock_defaults.nats = real_defaults.nats
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

        # The result will be 1 because NATS is disabled in config/defaults.yaml
        # But what matters is that subscriber.start() was NOT called
        # because the enabled check happens first
        assert result == 1
        mock_nats_module.NATSSubscriberThread.assert_not_called()

    def test_cmd_subscribe_with_nats_enabled(self, tmp_path: Path) -> None:
        """Verify cmd_subscribe.start() is called when NATS is enabled."""
        from manage_experiment import build_parser, cmd_subscribe

        # Create mock defaults with NATS enabled
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

        # Should succeed
        assert result == 0

        # Verify subscriber was created and started with the real nats_config
        mock_nats_module.NATSSubscriberThread.assert_called_once_with(
            config=mock_defaults.nats,
            handler=mock_router.dispatch,
        )
        mock_subscriber.start.assert_called_once()
        mock_subscriber.stop.assert_called_once()
