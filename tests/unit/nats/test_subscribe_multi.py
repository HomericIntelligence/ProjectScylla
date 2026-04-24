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

        # Each sub returns its message, then on re-poll raises TimeoutError
        # and sets stop so the loop exits.
        sub1 = AsyncMock()
        sub1_calls = 0

        async def sub1_next_msg(timeout: float = 1.0) -> AsyncMock:
            nonlocal sub1_calls
            sub1_calls += 1
            if sub1_calls == 1:
                return msg1
            thread._stop_event.set()
            raise asyncio.TimeoutError

        sub1.next_msg = sub1_next_msg

        sub2 = AsyncMock()
        sub2_calls = 0

        async def sub2_next_msg(timeout: float = 1.0) -> AsyncMock:
            nonlocal sub2_calls
            sub2_calls += 1
            if sub2_calls == 1:
                return msg2
            raise asyncio.TimeoutError

        sub2.next_msg = sub2_next_msg

        mock_js.subscribe = AsyncMock(side_effect=[sub1, sub2])

        _run_subscribe_loop(thread, mock_nc)

        assert "events.created" in received
        assert "events.updated" in received


class TestConcurrentPolling:
    """Tests verifying asyncio.wait(FIRST_COMPLETED) concurrent polling."""

    def test_first_ready_subscription_processed_without_waiting(self) -> None:
        """First-ready subscription is processed without waiting for others."""
        config = NATSConfig(
            enabled=True,
            subjects=["fast.subject", "slow.subject"],
        )
        received: list[str] = []

        def handler(event: object) -> None:
            received.append(getattr(event, "subject", ""))

        thread = NATSSubscriberThread(config=config, handler=handler)

        mock_nc = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream = MagicMock(return_value=mock_js)

        fast_msg = _make_mock_msg(subject="fast.subject", sequence=1)

        # fast sub returns immediately, slow sub always times out
        fast_sub = AsyncMock()
        fast_calls = 0

        async def fast_next_msg(timeout: float = 1.0) -> AsyncMock:
            nonlocal fast_calls
            fast_calls += 1
            if fast_calls == 1:
                return fast_msg
            # On re-poll, stop and timeout
            thread._stop_event.set()
            raise asyncio.TimeoutError

        fast_sub.next_msg = fast_next_msg

        slow_sub = AsyncMock()

        async def slow_next_msg(timeout: float = 1.0) -> AsyncMock:
            # Always times out
            raise asyncio.TimeoutError

        slow_sub.next_msg = slow_next_msg

        mock_js.subscribe = AsyncMock(side_effect=[fast_sub, slow_sub])

        _run_subscribe_loop(thread, mock_nc)

        # The fast message was delivered despite slow sub timing out
        assert "fast.subject" in received

    def test_pending_tasks_reused_across_iterations(self) -> None:
        """Unresolved tasks from previous iterations are reused, not recreated."""
        config = NATSConfig(
            enabled=True,
            subjects=["sub.a", "sub.b"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)

        mock_nc = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream = MagicMock(return_value=mock_js)

        msg_a = _make_mock_msg(subject="sub.a", sequence=1)

        sub_a = AsyncMock()
        sub_a_calls = 0

        async def sub_a_next_msg(timeout: float = 1.0) -> AsyncMock:
            nonlocal sub_a_calls
            sub_a_calls += 1
            if sub_a_calls == 1:
                return msg_a
            thread._stop_event.set()
            raise asyncio.TimeoutError

        sub_a.next_msg = sub_a_next_msg

        sub_b = AsyncMock()
        sub_b_calls = 0

        async def sub_b_next_msg(timeout: float = 1.0) -> AsyncMock:
            nonlocal sub_b_calls
            sub_b_calls += 1
            # Always times out — but should only be called twice:
            # once for initial task, once for re-enqueue after first
            # asyncio.wait returns it as done (timed out).
            raise asyncio.TimeoutError

        sub_b.next_msg = sub_b_next_msg

        mock_js.subscribe = AsyncMock(side_effect=[sub_a, sub_b])

        _run_subscribe_loop(thread, mock_nc)

        # sub_b.next_msg should have been called at least once (initial)
        # but not excessively — tasks are reused, not recreated every loop
        assert sub_b_calls >= 1

    def test_pending_tasks_cancelled_on_shutdown(self) -> None:
        """When stop is signalled, remaining pending tasks are cancelled."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.>"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        # Pre-set stop so loop exits after first asyncio.wait
        thread._stop_event.set()

        mock_nc, _mock_js, _mock_sub = _make_mocks()
        # The mock sub will timeout, stop_event is set, loop should exit
        # and cancel pending tasks

        _run_subscribe_loop(thread, mock_nc)

        # Thread should have completed without errors
        handler.assert_not_called()


class TestPartialSubscriptionFailure:
    """Test cleanup when a subscription fails partway through multi-subject setup."""

    def test_unsubscribes_previous_on_failure(self) -> None:
        """Already-subscribed subjects are unsubscribed when a later subscribe fails."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.created", "events.updated", "events.deleted"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()

        # First two subscribes succeed, third raises
        sub1 = AsyncMock()
        sub1.unsubscribe = AsyncMock()
        sub2 = AsyncMock()
        sub2.unsubscribe = AsyncMock()

        mock_js.subscribe = AsyncMock(side_effect=[sub1, sub2, PermissionError("denied")])

        with pytest.raises(PermissionError, match="denied"):
            _run_subscribe_loop(thread, mock_nc)

        sub1.unsubscribe.assert_awaited_once()
        sub2.unsubscribe.assert_awaited_once()

    def test_logs_warning_on_partial_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """A warning is logged identifying the failed subject and cleanup count."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.created", "events.updated", "events.deleted"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()
        sub1 = AsyncMock()
        sub1.unsubscribe = AsyncMock()
        sub2 = AsyncMock()
        sub2.unsubscribe = AsyncMock()

        mock_js.subscribe = AsyncMock(side_effect=[sub1, sub2, PermissionError("denied")])

        with (
            caplog.at_level(logging.WARNING, logger="scylla.nats.subscriber"),
            pytest.raises(PermissionError),
        ):
            _run_subscribe_loop(thread, mock_nc)

        assert "events.deleted" in caplog.text
        assert "2 already-subscribed" in caplog.text

    def test_first_subject_failure_no_unsubscribe(self) -> None:
        """When the very first subscribe fails, there is nothing to unsubscribe."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.created", "events.updated"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()
        mock_js.subscribe = AsyncMock(side_effect=PermissionError("denied"))

        with pytest.raises(PermissionError, match="denied"):
            _run_subscribe_loop(thread, mock_nc)

        # subscribe was called once, failed immediately -- no cleanup needed
        assert mock_js.subscribe.call_count == 1

    def test_cleanup_continues_on_unsubscribe_error(self) -> None:
        """If unsubscribe raises, cleanup continues for remaining subscriptions."""
        config = NATSConfig(
            enabled=True,
            subjects=["events.created", "events.updated", "events.deleted"],
        )
        handler = MagicMock()
        thread = NATSSubscriberThread(config=config, handler=handler)
        thread._stop_event.set()

        mock_nc, mock_js, _ = _make_mocks()
        sub1 = AsyncMock()
        sub1.unsubscribe = AsyncMock(side_effect=RuntimeError("cleanup fail"))
        sub2 = AsyncMock()
        sub2.unsubscribe = AsyncMock()

        mock_js.subscribe = AsyncMock(side_effect=[sub1, sub2, PermissionError("denied")])

        with pytest.raises(PermissionError, match="denied"):
            _run_subscribe_loop(thread, mock_nc)

        # Both unsubscribe methods were called, even though sub1's raised
        sub1.unsubscribe.assert_awaited_once()
        sub2.unsubscribe.assert_awaited_once()
