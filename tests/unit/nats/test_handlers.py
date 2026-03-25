"""Tests for scylla.nats.handlers module."""

import logging
from unittest.mock import MagicMock

import pytest

from scylla.nats.events import NATSEvent
from scylla.nats.handlers import (
    EventRouter,
    create_default_router,
    handle_task_completed,
    handle_task_created,
    handle_task_updated,
)


def _make_event(
    subject: str = "hi.tasks.scylla.task-001.created",
    sequence: int = 1,
) -> NATSEvent:
    """Create a test NATSEvent."""
    return NATSEvent(
        subject=subject,
        data={"test_id": "001"},
        timestamp="2026-03-25T10:00:00Z",
        sequence=sequence,
    )


class TestEventRouter:
    """Test EventRouter registration and dispatch."""

    def test_register_and_dispatch(self) -> None:
        """Registered handler is called with the event."""
        router = EventRouter()
        handler = MagicMock()
        router.register("created", handler)

        event = _make_event()
        router.dispatch(event)

        handler.assert_called_once_with(event)

    def test_dispatch_unknown_verb(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown verb logs a debug message but does not raise."""
        router = EventRouter()
        event = _make_event(subject="hi.tasks.scylla.task-001.unknown")

        with caplog.at_level(logging.DEBUG):
            router.dispatch(event)

        assert "No handler registered for verb" in caplog.text

    def test_dispatch_unparseable_subject(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unparseable subject logs a warning but does not raise."""
        router = EventRouter()
        event = _make_event(subject="bad.subject")

        with caplog.at_level(logging.WARNING):
            router.dispatch(event)

        assert "Unparseable subject" in caplog.text

    def test_handler_exception_isolation(self, caplog: pytest.LogCaptureFixture) -> None:
        """One handler raising should not crash the router."""
        router = EventRouter()

        def failing_handler(event: NATSEvent) -> None:
            raise RuntimeError("handler exploded")

        router.register("created", failing_handler)
        event = _make_event()

        with caplog.at_level(logging.ERROR):
            router.dispatch(event)

        assert "raised an exception" in caplog.text

    def test_multiple_verbs(self) -> None:
        """Different verbs dispatch to their respective handlers."""
        router = EventRouter()
        created_handler = MagicMock()
        updated_handler = MagicMock()

        router.register("created", created_handler)
        router.register("updated", updated_handler)

        event_created = _make_event(subject="hi.tasks.scylla.task-001.created")
        event_updated = _make_event(subject="hi.tasks.scylla.task-001.updated")

        router.dispatch(event_created)
        router.dispatch(event_updated)

        created_handler.assert_called_once_with(event_created)
        updated_handler.assert_called_once_with(event_updated)

    def test_register_overwrites_previous(self) -> None:
        """Re-registering a verb replaces the previous handler."""
        router = EventRouter()
        first = MagicMock()
        second = MagicMock()

        router.register("created", first)
        router.register("created", second)

        event = _make_event()
        router.dispatch(event)

        first.assert_not_called()
        second.assert_called_once_with(event)


class TestDefaultHandlers:
    """Test default stub handlers log without errors."""

    def test_handle_task_created(self, caplog: pytest.LogCaptureFixture) -> None:
        """Task created handler logs the event."""
        with caplog.at_level(logging.INFO):
            handle_task_created(_make_event())
        assert "Task created" in caplog.text

    def test_handle_task_updated(self, caplog: pytest.LogCaptureFixture) -> None:
        """Task updated handler logs the event."""
        event = _make_event(subject="hi.tasks.scylla.task-001.updated")
        with caplog.at_level(logging.INFO):
            handle_task_updated(event)
        assert "Task updated" in caplog.text

    def test_handle_task_completed(self, caplog: pytest.LogCaptureFixture) -> None:
        """Task completed handler logs the event."""
        event = _make_event(subject="hi.tasks.scylla.task-001.completed")
        with caplog.at_level(logging.INFO):
            handle_task_completed(event)
        assert "Task completed" in caplog.text


class TestCreateDefaultRouter:
    """Test create_default_router factory."""

    def test_has_all_verbs(self) -> None:
        """Default router handles created, updated, and completed verbs."""
        router = create_default_router()
        for verb in ("created", "updated", "completed"):
            event = _make_event(subject=f"hi.tasks.scylla.task-001.{verb}")
            router.dispatch(event)
