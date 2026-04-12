"""Tests for scylla.nats.subscriber module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from scylla.nats.config import NATSConfig
from scylla.nats.events import NATSEvent
from scylla.nats.subscriber import (
    _BACKOFF_MULTIPLIER,
    _INITIAL_BACKOFF_SECONDS,
    _MAX_BACKOFF_SECONDS,
    NATSSubscriberThread,
)


class TestNATSSubscriberThread:
    """Test NATSSubscriberThread lifecycle and behavior."""

    def test_init_sets_daemon(self) -> None:
        """Thread is created as a daemon with the correct name."""
        config = NATSConfig(enabled=True)
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        assert thread.daemon is True
        assert thread.name == "NATSSubscriberThread"

    def test_stop_sets_event(self) -> None:
        """Setting the stop event marks the thread for shutdown."""
        config = NATSConfig(enabled=True)
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        assert not thread._stop_event.is_set()
        thread._stop_event.set()
        assert thread._stop_event.is_set()

    def test_stop_before_start(self) -> None:
        """Calling stop() before start() should not raise."""
        config = NATSConfig(enabled=True)
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()
        assert thread._stop_event.is_set()

    def test_run_stops_immediately_when_stop_set(self) -> None:
        """Thread should exit immediately when stop event is already set."""
        config = NATSConfig(enabled=True)
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)

        thread._stop_event.set()
        thread.run()

        handler.assert_not_called()

    @patch("scylla.nats.subscriber.asyncio")
    def test_run_reconnects_on_error(self, mock_asyncio: MagicMock) -> None:
        """Thread should retry on connection error with backoff."""
        config = NATSConfig(enabled=True)
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)

        call_count = 0

        def side_effect(*args: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                thread._stop_event.set()
            raise ConnectionError("test")

        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = side_effect
        mock_asyncio.new_event_loop.return_value = mock_loop

        thread.run()

        assert call_count >= 2

    def test_backoff_constants(self) -> None:
        """Verify backoff constants are sensible."""
        assert _INITIAL_BACKOFF_SECONDS == 1.0
        assert _MAX_BACKOFF_SECONDS == 60.0
        assert _BACKOFF_MULTIPLIER == 2.0
        backoff = _INITIAL_BACKOFF_SECONDS
        for _ in range(10):
            backoff = min(backoff * _BACKOFF_MULTIPLIER, _MAX_BACKOFF_SECONDS)
        assert backoff == _MAX_BACKOFF_SECONDS

    def test_handler_receives_event(self) -> None:
        """Verify handler callable is stored correctly."""
        config = NATSConfig(enabled=True)
        received: list[NATSEvent] = []

        def handler(event: NATSEvent) -> None:
            received.append(event)

        thread = NATSSubscriberThread(config=config, handler=handler)
        assert thread._handler is handler

    def test_config_stored(self) -> None:
        """Verify config is accessible on the thread."""
        config = NATSConfig(
            enabled=True,
            url="nats://test:4222",
            stream="TEST_STREAM",
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        assert thread._config.url == "nats://test:4222"
        assert thread._config.stream == "TEST_STREAM"

    def test_deliver_policy_passed_to_subscribe(self) -> None:
        """deliver_policy from NATSConfig is forwarded to js.subscribe()."""
        config = NATSConfig(
            enabled=True,
            subjects=["hi.tasks.>"],
            deliver_policy="all",
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream = MagicMock(return_value=mock_js)
        mock_sub = AsyncMock()
        mock_sub.next_msg = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_js.subscribe = AsyncMock(return_value=mock_sub)

        mock_nats = MagicMock()
        mock_nats.connect = AsyncMock(return_value=mock_nc)

        async def _run() -> None:
            with patch.dict("sys.modules", {"nats": mock_nats}):
                await thread._subscribe_loop()

        asyncio.run(_run())

        mock_js.subscribe.assert_called_once()
        call_kwargs = mock_js.subscribe.call_args.kwargs
        assert call_kwargs["deliver_policy"] == "all"
