"""Tests for scylla.nats.events module."""

import pytest

from scylla.nats.events import NATSEvent, SubjectParts, parse_subject


class TestNATSEvent:
    """Test NATSEvent Pydantic model validation."""

    def test_valid_event(self) -> None:
        """Valid event fields are stored correctly."""
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.created",
            data={"test_id": "001"},
            timestamp="2026-03-25T10:00:00Z",
            sequence=42,
        )
        assert event.subject == "hi.tasks.scylla.task-001.created"
        assert event.data == {"test_id": "001"}
        assert event.timestamp == "2026-03-25T10:00:00Z"
        assert event.sequence == 42

    def test_empty_data_dict(self) -> None:
        """Empty data dict is accepted."""
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.created",
            data={},
            timestamp="",
            sequence=0,
        )
        assert event.data == {}

    def test_negative_sequence_rejected(self) -> None:
        """Negative sequence number is rejected by validation."""
        with pytest.raises(Exception):  # noqa: B017
            NATSEvent(
                subject="test",
                data={},
                timestamp="",
                sequence=-1,
            )

    def test_model_serialization_roundtrip(self) -> None:
        """Model can be serialized and deserialized without loss."""
        event = NATSEvent(
            subject="hi.tasks.scylla.task-001.created",
            data={"key": "value"},
            timestamp="2026-03-25T10:00:00Z",
            sequence=1,
        )
        data = event.model_dump()
        restored = NATSEvent(**data)
        assert restored == event


class TestSubjectParts:
    """Test SubjectParts NamedTuple."""

    def test_fields(self) -> None:
        """Named fields are accessible."""
        parts = SubjectParts(team="scylla", task_id="task-001", verb="created")
        assert parts.team == "scylla"
        assert parts.task_id == "task-001"
        assert parts.verb == "created"


class TestParseSubject:
    """Test parse_subject() with valid and invalid subjects."""

    def test_valid_subject(self) -> None:
        """Valid 5-part subject is parsed correctly."""
        parts = parse_subject("hi.tasks.scylla.task-001.created")
        assert parts.team == "scylla"
        assert parts.task_id == "task-001"
        assert parts.verb == "created"

    def test_different_verbs(self) -> None:
        """Different verbs in the subject are extracted correctly."""
        for verb in ("created", "updated", "completed", "failed"):
            parts = parse_subject(f"hi.tasks.hermes.job-42.{verb}")
            assert parts.verb == verb
            assert parts.team == "hermes"
            assert parts.task_id == "job-42"

    def test_too_few_parts(self) -> None:
        """Subjects with fewer than 5 parts raise ValueError."""
        with pytest.raises(ValueError, match="5 parts"):
            parse_subject("hi.tasks.scylla")

    def test_too_many_parts(self) -> None:
        """Subjects with more than 5 parts raise ValueError."""
        with pytest.raises(ValueError, match="5 parts"):
            parse_subject("hi.tasks.scylla.task-001.created.extra")

    def test_single_part(self) -> None:
        """Single-part subject raises ValueError."""
        with pytest.raises(ValueError, match="5 parts"):
            parse_subject("invalid")

    def test_empty_string(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="5 parts"):
            parse_subject("")

    @pytest.mark.parametrize(
        "subject,team,task_id,verb",
        [
            ("hi.tasks.odyssey.eval-1.started", "odyssey", "eval-1", "started"),
            ("hi.tasks.keystone.msg-99.delivered", "keystone", "msg-99", "delivered"),
            ("hi.tasks.scylla.bench-007.completed", "scylla", "bench-007", "completed"),
        ],
    )
    def test_parametrized_subjects(self, subject: str, team: str, task_id: str, verb: str) -> None:
        """Parametrized subjects are parsed into the correct components."""
        parts = parse_subject(subject)
        assert parts.team == team
        assert parts.task_id == task_id
        assert parts.verb == verb
