"""Tests for scylla.nats.handlers module."""

import logging
from unittest.mock import MagicMock

import pytest

from scylla.nats.events import NATSEvent
from scylla.nats.handlers import (
    EventRouter,
    OrchestratorHandlers,
    create_default_router,
    create_orchestrator_router,
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


# ---------------------------------------------------------------------------
# OrchestratorHandlers tests
# ---------------------------------------------------------------------------


def _make_mock_orchestrator() -> MagicMock:
    """Create a mock EvalOrchestrator with expected methods."""
    mock = MagicMock()
    mock.run_single = MagicMock()
    return mock


class TestOrchestratorHandlersCreated:
    """Test OrchestratorHandlers.handle_task_created."""

    def test_calls_run_single_with_defaults(self) -> None:
        """Created event with test_id and model_id triggers run_single."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.created",
            data={"test_id": "001-justfile", "model_id": "claude-sonnet"},
            timestamp="2026-04-23T10:00:00Z",
            sequence=42,
        )

        handlers.handle_task_created(event)

        orch.run_single.assert_called_once_with(
            test_id="001-justfile",
            model_id="claude-sonnet",
            tier_id="T0",
            run_number=1,
        )

    def test_passes_optional_tier_and_run(self) -> None:
        """Created event with tier_id and run_number uses those values."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.created",
            data={
                "test_id": "002-makefile",
                "model_id": "claude-opus",
                "tier_id": "T3",
                "run_number": 5,
            },
            timestamp="2026-04-23T10:00:00Z",
            sequence=43,
        )

        handlers.handle_task_created(event)

        orch.run_single.assert_called_once_with(
            test_id="002-makefile",
            model_id="claude-opus",
            tier_id="T3",
            run_number=5,
        )

    def test_skips_when_test_id_missing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Missing test_id skips the event with a warning."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.created",
            data={"model_id": "claude-sonnet"},
            timestamp="2026-04-23T10:00:00Z",
            sequence=44,
        )

        with caplog.at_level(logging.WARNING):
            handlers.handle_task_created(event)

        orch.run_single.assert_not_called()
        assert "missing keys" in caplog.text
        assert "test_id" in caplog.text

    def test_skips_when_model_id_missing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Missing model_id skips the event with a warning."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.created",
            data={"test_id": "001"},
            timestamp="2026-04-23T10:00:00Z",
            sequence=45,
        )

        with caplog.at_level(logging.WARNING):
            handlers.handle_task_created(event)

        orch.run_single.assert_not_called()
        assert "missing keys" in caplog.text
        assert "model_id" in caplog.text


class TestOrchestratorHandlersUpdated:
    """Test OrchestratorHandlers.handle_task_updated."""

    def test_logs_status(self, caplog: pytest.LogCaptureFixture) -> None:
        """Updated event logs the task status."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.updated",
            data={"status": "running"},
            timestamp="2026-04-23T10:00:00Z",
            sequence=50,
        )

        with caplog.at_level(logging.INFO):
            handlers.handle_task_updated(event)

        assert "task-001" in caplog.text
        assert "running" in caplog.text

    def test_logs_unknown_status(self, caplog: pytest.LogCaptureFixture) -> None:
        """Updated event without status logs 'unknown'."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.updated",
            data={},
            timestamp="2026-04-23T10:00:00Z",
            sequence=51,
        )

        with caplog.at_level(logging.INFO):
            handlers.handle_task_updated(event)

        assert "unknown" in caplog.text


class TestOrchestratorHandlersCompleted:
    """Test OrchestratorHandlers.handle_task_completed."""

    def test_logs_completion(self, caplog: pytest.LogCaptureFixture) -> None:
        """Completed event logs passed status and cost."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.completed",
            data={"passed": True, "cost_usd": 0.05},
            timestamp="2026-04-23T10:00:00Z",
            sequence=60,
        )

        with caplog.at_level(logging.INFO):
            handlers.handle_task_completed(event)

        assert "task-001" in caplog.text
        assert "True" in caplog.text
        assert "0.05" in caplog.text

    def test_logs_without_result_data(self, caplog: pytest.LogCaptureFixture) -> None:
        """Completed event without result data uses None values."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.completed",
            data={},
            timestamp="2026-04-23T10:00:00Z",
            sequence=61,
        )

        with caplog.at_level(logging.INFO):
            handlers.handle_task_completed(event)

        assert "task-001" in caplog.text
        assert "None" in caplog.text


class TestCreateOrchestratorRouter:
    """Test create_orchestrator_router factory."""

    def test_dispatches_created_to_orchestrator(self) -> None:
        """Created event dispatched via router calls run_single."""
        orch = _make_mock_orchestrator()
        router = create_orchestrator_router(orch)
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.created",
            data={"test_id": "001", "model_id": "claude-sonnet"},
            timestamp="2026-04-23T10:00:00Z",
            sequence=70,
        )

        router.dispatch(event)

        orch.run_single.assert_called_once()

    def test_dispatches_all_verbs(self) -> None:
        """Router has handlers for created, updated, and completed."""
        orch = _make_mock_orchestrator()
        router = create_orchestrator_router(orch)

        for verb in ("created", "updated", "completed"):
            event = NATSEvent(
                subject=f"hi.tasks.scylla.task-001.{verb}",
                data={"test_id": "001", "model_id": "claude-sonnet"},
                timestamp="2026-04-23T10:00:00Z",
                sequence=71,
            )
            # Should not raise
            router.dispatch(event)

    def test_orchestrator_is_injected_not_constructed(self) -> None:
        """The OrchestratorHandlers use the injected instance."""
        orch = _make_mock_orchestrator()
        handlers = OrchestratorHandlers(orch)
        assert handlers._orchestrator is orch
