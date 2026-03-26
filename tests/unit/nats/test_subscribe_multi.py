"""Tests for multi-subject subscription in NATSSubscriberThread."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scylla.nats.config import NATSConfig
from scylla.nats.subscriber import NATSSubscriberThread


def _make_mock_msg(
    subject: str = "hi.tasks.scylla.task1.created",
    data: dict[str, object] | None = None,
    sequence: int = 1,
) -> AsyncMock:
    """Create a mock NATS message with the given attributes."""
    msg = AsyncMock()
    payload = data or {"task_id": "task1"}
    msg.data = json.dumps(payload).encode()
    msg.subject = subject
    msg.headers = {"Nats-Time-Stamp": "2024-01-01T00:00:00Z"}
    msg.metadata = MagicMock()
    msg.metadata.sequence.stream = sequence
    msg.ack = AsyncMock()
    return msg


def _make_mocks() -> tuple[AsyncMock, MagicMock, AsyncMock]:
    """Create mock NATS connection, JetStream context, and subscription."""
    mock_nc = AsyncMock()
    mock_js = MagicMock()
    mock_nc.jetstream = MagicMock(return_value=mock_js)

    mock_sub = AsyncMock()
    mock_sub.next_msg = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_js.subscribe = AsyncMock(return_value=mock_sub)

    return mock_nc, mock_js, mock_sub


def _run_subscribe_loop(thread: NATSSubscriberThread, mock_nc: AsyncMock) -> None:
    """Run _subscribe_loop in a new event loop with the nats module mocked."""
    mock_nats = MagicMock()
    mock_nats.connect = AsyncMock(return_value=mock_nc)

    async def _run() -> None:
        with patch.dict("sys.modules", {"nats": mock_nats}):
            await thread._subscribe_loop()

    asyncio.run(_run())


class TestMultiSubjectSubscription:
    """Test that _subscribe_loop subscribes to all configured subjects."""

    def test_subscribes_to_all_subjects(self) -> None:
        """js.subscribe is called once per subject in the config."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.created", "events.updated", "events.deleted"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()
        _run_subscribe_loop(thread, mock_nc)

        assert mock_js.subscribe.call_count == 3
        subscribed_subjects = [c.kwargs["subject"] for c in mock_js.subscribe.call_args_list]
        assert subscribed_subjects == [
            "events.created",
            "events.updated",
            "events.deleted",
        ]

    def test_single_subject(self) -> None:
        """Single subject should call js.subscribe exactly once."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.>"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()
        _run_subscribe_loop(thread, mock_nc)

        assert mock_js.subscribe.call_count == 1
        assert mock_js.subscribe.call_args.kwargs["subject"] == "events.>"

    def test_empty_subjects_falls_back_to_default(self) -> None:
        """Empty subjects list falls back to 'hi.tasks.>'."""
        config = NATSConfig(enabled=True, subjects=[])
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()
        _run_subscribe_loop(thread, mock_nc)

        assert mock_js.subscribe.call_count == 1
        assert mock_js.subscribe.call_args.kwargs["subject"] == "hi.tasks.>"

    def test_durable_names_unique_per_subject(self) -> None:
        """Each subscription gets a unique durable name when multiple subjects."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.created", "events.updated", "events.deleted"],
            durable_name="scylla-subscriber",
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()
        _run_subscribe_loop(thread, mock_nc)

        durable_names = [c.kwargs["durable"] for c in mock_js.subscribe.call_args_list]
        assert durable_names == [
            "scylla-subscriber-0",
            "scylla-subscriber-1",
            "scylla-subscriber-2",
        ]
        # All unique
        assert len(set(durable_names)) == len(durable_names)

    def test_single_subject_uses_unmodified_durable_name(self) -> None:
        """Single subject preserves the original durable name (backward compat)."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.>"],
            durable_name="scylla-subscriber",
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()
        _run_subscribe_loop(thread, mock_nc)

        assert mock_js.subscribe.call_args.kwargs["durable"] == "scylla-subscriber"

    def test_logs_all_subjects(self, caplog: pytest.LogCaptureFixture) -> None:
        """Log message at startup includes all subscribed subjects."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.created", "events.updated"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, _mock_js, _ = _make_mocks()

        with caplog.at_level(logging.INFO, logger="scylla.nats.subscriber"):
            _run_subscribe_loop(thread, mock_nc)

        log_text = caplog.text
        assert "2 NATS JetStream subject(s)" in log_text
        assert "events.created" in log_text
        assert "events.updated" in log_text

    def test_messages_from_all_subscriptions_dispatched(self) -> None:
        """Messages from different subscriptions are all dispatched to handler."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.created", "events.updated"],
        )
        received: list[str] = []

        def handler(event: object) -> None:
            received.append(getattr(event, "subject", ""))

        thread = NATSSubscriberThread(config=config, handler=handler)

        mock_nc = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream = MagicMock(return_value=mock_js)

        msg1 = _make_mock_msg(subject="events.created", sequence=1)
        msg2 = _make_mock_msg(subject="events.updated", sequence=2)

        # First sub returns msg1 then sets stop; second sub returns msg2
        sub1 = AsyncMock()

        async def sub1_next_msg(timeout: float = 0.5) -> AsyncMock:
            return msg1

        sub1.next_msg = sub1_next_msg

        sub2 = AsyncMock()

        async def sub2_next_msg(timeout: float = 0.5) -> AsyncMock:
            # After delivering msg2, signal stop
            thread._stop_event.set()
            return msg2

        sub2.next_msg = sub2_next_msg

        mock_js.subscribe = AsyncMock(side_effect=[sub1, sub2])

        _run_subscribe_loop(thread, mock_nc)

        assert "events.created" in received
        assert "events.updated" in received
