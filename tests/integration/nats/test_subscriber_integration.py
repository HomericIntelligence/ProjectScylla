"""Integration tests for NATSSubscriberThread with a real nats-server.

Exercises the full path: connect -> subscribe -> receive message -> parse
event -> dispatch to handler -> graceful shutdown.

Requires ``nats-server`` in PATH. Tests are skipped otherwise.
"""

from __future__ import annotations

import shutil
import threading
import time
import uuid

import pytest

from scylla.nats.config import NATSConfig
from scylla.nats.events import NATSEvent
from scylla.nats.subscriber import NATSSubscriberThread

from .conftest import NATSPublisher

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("nats-server") is None,
        reason="nats-server not in PATH",
    ),
]


def _make_config(nats_url: str) -> NATSConfig:
    """Build a NATSConfig pointed at the test server with a unique durable name."""
    return NATSConfig(
        enabled=True,
        url=nats_url,
        stream="TASKS",
        subjects=["hi.tasks.>"],
        durable_name=f"test-{uuid.uuid4().hex[:8]}",
    )


class TestNATSSubscriberIntegration:
    """Integration tests for NATSSubscriberThread with a real nats-server."""

    def test_connect_receive_dispatch(self, nats_url: str, publisher: NATSPublisher) -> None:
        """Full happy path: start -> receive message -> handler gets NATSEvent."""
        received = threading.Event()
        events: list[NATSEvent] = []

        def handler(event: NATSEvent) -> None:
            events.append(event)
            received.set()

        config = _make_config(nats_url)
        subscriber = NATSSubscriberThread(config=config, handler=handler)
        subscriber.start()

        try:
            # Give the subscriber time to connect and subscribe
            time.sleep(1.0)

            payload = {"task_id": "abc-123", "status": "created"}
            publisher.publish_json("hi.tasks.scylla.abc-123.created", payload)

            assert received.wait(timeout=10.0), "Handler not called within 10s"
            assert len(events) == 1
            assert events[0].subject == "hi.tasks.scylla.abc-123.created"
            assert events[0].data == payload
            assert events[0].sequence > 0
        finally:
            subscriber.stop()

    def test_graceful_shutdown(self, nats_url: str, publisher: NATSPublisher) -> None:
        """stop() cleanly stops the thread within 5s."""
        config = _make_config(nats_url)
        subscriber = NATSSubscriberThread(
            config=config,
            handler=lambda _: None,
        )
        subscriber.start()

        # Ensure it's actually running
        time.sleep(0.5)
        assert subscriber.is_alive()

        subscriber.stop()
        assert not subscriber.is_alive(), "Thread still alive after stop()"

    def test_malformed_message_acked(self, nats_url: str, publisher: NATSPublisher) -> None:
        """Non-JSON message is acked without crashing; handler is NOT called."""
        handler_called = threading.Event()

        def handler(event: NATSEvent) -> None:
            handler_called.set()

        config = _make_config(nats_url)
        subscriber = NATSSubscriberThread(config=config, handler=handler)
        subscriber.start()

        try:
            time.sleep(1.0)

            # Publish raw non-JSON bytes
            publisher.publish_raw("hi.tasks.scylla.bad-1.created", b"not-json{{{")

            # Handler should NOT be called - wait a bit to confirm
            assert not handler_called.wait(timeout=3.0), "Handler was called for malformed message"
            # Subscriber should still be alive (not crashed)
            assert subscriber.is_alive()
        finally:
            subscriber.stop()

    def test_handler_called_with_parsed_event(
        self, nats_url: str, publisher: NATSPublisher
    ) -> None:
        """Verify NATSEvent.data matches published JSON and subject is correct."""
        received = threading.Event()
        events: list[NATSEvent] = []

        def handler(event: NATSEvent) -> None:
            events.append(event)
            received.set()

        config = _make_config(nats_url)
        subscriber = NATSSubscriberThread(config=config, handler=handler)
        subscriber.start()

        try:
            time.sleep(1.0)

            payload = {"key": "value", "nested": {"a": 1}, "list": [1, 2, 3]}
            subject = "hi.tasks.team1.task-42.updated"
            publisher.publish_json(subject, payload)

            assert received.wait(timeout=10.0), "Handler not called within 10s"
            event = events[0]
            assert event.subject == subject
            assert event.data == payload
            assert isinstance(event.sequence, int)
            assert event.sequence > 0
        finally:
            subscriber.stop()

    def test_multiple_messages(self, nats_url: str, publisher: NATSPublisher) -> None:
        """Publish 3 messages; handler receives all 3 in order."""
        all_received = threading.Event()
        events: list[NATSEvent] = []
        lock = threading.Lock()

        def handler(event: NATSEvent) -> None:
            with lock:
                events.append(event)
                if len(events) >= 3:
                    all_received.set()

        config = _make_config(nats_url)
        subscriber = NATSSubscriberThread(config=config, handler=handler)
        subscriber.start()

        try:
            time.sleep(1.0)

            for i in range(3):
                publisher.publish_json(
                    f"hi.tasks.scylla.multi-{i}.created",
                    {"index": i},
                )

            assert all_received.wait(timeout=10.0), "Did not receive all 3 messages within 10s"

            with lock:
                assert len(events) == 3
                for i, event in enumerate(events):
                    assert event.data["index"] == i
                    assert event.subject == f"hi.tasks.scylla.multi-{i}.created"
        finally:
            subscriber.stop()
