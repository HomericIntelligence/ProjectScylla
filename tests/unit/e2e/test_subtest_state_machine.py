"""Unit tests for the subtest state machine module.

Tests cover:
- Subtest transition registry completeness and ordering
- SubtestStateMachine.advance() happy path
- SubtestStateMachine.advance_to_completion() full subtest run
- Terminal state detection
- Invalid subtest transition rejection
- Checkpoint persistence after each transition
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint
from scylla.e2e.models import SubtestState
from scylla.e2e.subtest_state_machine import (
    SUBTEST_TRANSITION_REGISTRY,
    SubtestStateMachine,
    get_next_subtest_transition,
    is_subtest_terminal_state,
    validate_subtest_transition,
)

TIER_ID = "T0"
SUBTEST_ID = "00"


@pytest.fixture
def checkpoint(tmp_path: Path) -> E2ECheckpoint:
    """Create a minimal checkpoint for testing."""
    return E2ECheckpoint(
        experiment_id="test-subtest-sm",
        experiment_dir=str(tmp_path),
        config_hash="abc123",
        started_at=datetime.now(timezone.utc).isoformat(),
        last_updated_at=datetime.now(timezone.utc).isoformat(),
        status="running",
    )


@pytest.fixture
def checkpoint_path(tmp_path: Path, checkpoint: E2ECheckpoint) -> Path:
    """Create checkpoint file and return path."""
    path = tmp_path / "checkpoint.json"
    save_checkpoint(checkpoint, path)
    return path


@pytest.fixture
def ssm(checkpoint: E2ECheckpoint, checkpoint_path: Path) -> SubtestStateMachine:
    """Create a SubtestStateMachine for testing."""
    return SubtestStateMachine(checkpoint=checkpoint, checkpoint_path=checkpoint_path)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestSubtestTransitionRegistry:
    """Tests for the SUBTEST_TRANSITION_REGISTRY completeness."""

    def test_registry_covers_all_non_terminal_states(self) -> None:
        """Every non-terminal SubtestState has a registry entry."""
        registered_from = {t.from_state for t in SUBTEST_TRANSITION_REGISTRY}
        for state in SubtestState:
            if not is_subtest_terminal_state(state):
                assert state in registered_from, (
                    f"SubtestState {state.value} has no transition (not terminal, not in registry)"
                )

    def test_registry_no_duplicate_from_states(self) -> None:
        """Each from_state appears at most once in the registry."""
        from_states = [t.from_state for t in SUBTEST_TRANSITION_REGISTRY]
        assert len(from_states) == len(set(from_states))

    def test_all_transitions_have_descriptions(self) -> None:
        """All transitions have non-empty descriptions."""
        for t in SUBTEST_TRANSITION_REGISTRY:
            assert t.description, f"Transition {t.from_state.value} has empty description"

    def test_sequence_terminates_at_aggregated(self) -> None:
        """The last transition in the registry leads to AGGREGATED."""
        last = SUBTEST_TRANSITION_REGISTRY[-1]
        assert last.to_state == SubtestState.AGGREGATED

    def test_registry_has_three_transitions(self) -> None:
        """Registry contains exactly 3 transitions for the 4-state sequence."""
        assert len(SUBTEST_TRANSITION_REGISTRY) == 3

    def test_first_transition_from_pending(self) -> None:
        """First transition starts from PENDING."""
        assert SUBTEST_TRANSITION_REGISTRY[0].from_state == SubtestState.PENDING

    def test_first_transition_to_runs_in_progress(self) -> None:
        """First transition leads to RUNS_IN_PROGRESS."""
        assert SUBTEST_TRANSITION_REGISTRY[0].to_state == SubtestState.RUNS_IN_PROGRESS


# ---------------------------------------------------------------------------
# is_subtest_terminal_state tests
# ---------------------------------------------------------------------------


class TestIsSubtestTerminalState:
    """Tests for is_subtest_terminal_state() function."""

    def test_aggregated_is_terminal(self) -> None:
        """AGGREGATED is a terminal subtest state."""
        assert is_subtest_terminal_state(SubtestState.AGGREGATED)

    def test_failed_is_terminal(self) -> None:
        """FAILED is a terminal subtest state."""
        assert is_subtest_terminal_state(SubtestState.FAILED)

    def test_pending_is_not_terminal(self) -> None:
        """PENDING is not terminal."""
        assert not is_subtest_terminal_state(SubtestState.PENDING)

    def test_runs_in_progress_is_not_terminal(self) -> None:
        """RUNS_IN_PROGRESS is not terminal."""
        assert not is_subtest_terminal_state(SubtestState.RUNS_IN_PROGRESS)

    def test_runs_complete_is_not_terminal(self) -> None:
        """RUNS_COMPLETE is not terminal."""
        assert not is_subtest_terminal_state(SubtestState.RUNS_COMPLETE)


# ---------------------------------------------------------------------------
# validate_subtest_transition tests
# ---------------------------------------------------------------------------


class TestValidateSubtestTransition:
    """Tests for validate_subtest_transition() function."""

    def test_valid_transition_pending_to_runs_in_progress(self) -> None:
        """PENDING -> RUNS_IN_PROGRESS is valid."""
        assert validate_subtest_transition(SubtestState.PENDING, SubtestState.RUNS_IN_PROGRESS)

    def test_valid_transition_runs_in_progress_to_runs_complete(self) -> None:
        """RUNS_IN_PROGRESS -> RUNS_COMPLETE is valid."""
        assert validate_subtest_transition(
            SubtestState.RUNS_IN_PROGRESS, SubtestState.RUNS_COMPLETE
        )

    def test_valid_transition_runs_complete_to_aggregated(self) -> None:
        """RUNS_COMPLETE -> AGGREGATED is valid."""
        assert validate_subtest_transition(SubtestState.RUNS_COMPLETE, SubtestState.AGGREGATED)

    def test_invalid_transition_skips_state(self) -> None:
        """Cannot skip from PENDING to RUNS_COMPLETE."""
        assert not validate_subtest_transition(SubtestState.PENDING, SubtestState.RUNS_COMPLETE)

    def test_invalid_transition_from_terminal(self) -> None:
        """Cannot transition from AGGREGATED."""
        assert not validate_subtest_transition(SubtestState.AGGREGATED, SubtestState.PENDING)

    def test_invalid_transition_backwards(self) -> None:
        """Backwards transitions are invalid."""
        assert not validate_subtest_transition(SubtestState.RUNS_COMPLETE, SubtestState.PENDING)


# ---------------------------------------------------------------------------
# get_next_subtest_transition tests
# ---------------------------------------------------------------------------


class TestGetNextSubtestTransition:
    """Tests for get_next_subtest_transition() function."""

    def test_returns_transition_for_pending(self) -> None:
        """PENDING returns RUNS_IN_PROGRESS as next state."""
        t = get_next_subtest_transition(SubtestState.PENDING)
        assert t is not None
        assert t.to_state == SubtestState.RUNS_IN_PROGRESS

    def test_returns_transition_for_runs_in_progress(self) -> None:
        """RUNS_IN_PROGRESS returns RUNS_COMPLETE as next state."""
        t = get_next_subtest_transition(SubtestState.RUNS_IN_PROGRESS)
        assert t is not None
        assert t.to_state == SubtestState.RUNS_COMPLETE

    def test_returns_none_for_aggregated(self) -> None:
        """AGGREGATED returns None (no further transitions)."""
        assert get_next_subtest_transition(SubtestState.AGGREGATED) is None


# ---------------------------------------------------------------------------
# SubtestStateMachine.get_state tests
# ---------------------------------------------------------------------------


class TestSubtestStateMachineGetState:
    """Tests for SubtestStateMachine.get_state() method."""

    def test_returns_pending_for_unknown_subtest(self, ssm: SubtestStateMachine) -> None:
        """Unknown subtest defaults to PENDING."""
        assert ssm.get_state(TIER_ID, SUBTEST_ID) == SubtestState.PENDING

    def test_returns_stored_state(
        self, ssm: SubtestStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """Returns stored SubtestState from checkpoint."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.RUNS_IN_PROGRESS.value)
        assert ssm.get_state(TIER_ID, SUBTEST_ID) == SubtestState.RUNS_IN_PROGRESS

    def test_handles_unknown_state_string(
        self, ssm: SubtestStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """Unknown state string defaults to PENDING."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, "future_unknown_state")
        assert ssm.get_state(TIER_ID, SUBTEST_ID) == SubtestState.PENDING


# ---------------------------------------------------------------------------
# SubtestStateMachine.is_complete tests
# ---------------------------------------------------------------------------


class TestSubtestStateMachineIsComplete:
    """Tests for SubtestStateMachine.is_complete() method."""

    def test_pending_is_not_complete(self, ssm: SubtestStateMachine) -> None:
        """PENDING subtest is not complete."""
        assert not ssm.is_complete(TIER_ID, SUBTEST_ID)

    def test_aggregated_is_complete(
        self, ssm: SubtestStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """AGGREGATED subtest is complete."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.AGGREGATED.value)
        assert ssm.is_complete(TIER_ID, SUBTEST_ID)

    def test_runs_complete_is_not_complete(
        self, ssm: SubtestStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """RUNS_COMPLETE is not the terminal state."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.RUNS_COMPLETE.value)
        assert not ssm.is_complete(TIER_ID, SUBTEST_ID)

    def test_failed_is_complete(self, ssm: SubtestStateMachine, checkpoint: E2ECheckpoint) -> None:
        """FAILED is a terminal state (complete)."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.FAILED.value)
        assert ssm.is_complete(TIER_ID, SUBTEST_ID)


# ---------------------------------------------------------------------------
# SubtestStateMachine.advance tests
# ---------------------------------------------------------------------------


class TestSubtestStateMachineAdvance:
    """Tests for SubtestStateMachine.advance() method."""

    def test_advance_from_pending_calls_action(
        self, ssm: SubtestStateMachine, checkpoint_path: Path
    ) -> None:
        """advance() calls the registered action and transitions state."""
        action = MagicMock()
        new_state = ssm.advance(TIER_ID, SUBTEST_ID, {SubtestState.PENDING: action})
        action.assert_called_once()
        assert new_state == SubtestState.RUNS_IN_PROGRESS

    def test_advance_without_action_transitions_state(
        self, ssm: SubtestStateMachine, checkpoint_path: Path
    ) -> None:
        """advance() without action still transitions state."""
        new_state = ssm.advance(TIER_ID, SUBTEST_ID, {})
        assert new_state == SubtestState.RUNS_IN_PROGRESS

    def test_advance_updates_checkpoint_state(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """advance() persists new state to checkpoint."""
        ssm.advance(TIER_ID, SUBTEST_ID, {})
        assert ssm.get_state(TIER_ID, SUBTEST_ID) == SubtestState.RUNS_IN_PROGRESS

        from scylla.e2e.checkpoint import load_checkpoint

        loaded = load_checkpoint(checkpoint_path)
        assert loaded.get_subtest_state(TIER_ID, SUBTEST_ID) == SubtestState.RUNS_IN_PROGRESS.value

    def test_advance_from_terminal_raises(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """advance() raises RuntimeError from terminal state."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.AGGREGATED.value)
        with pytest.raises(RuntimeError, match="terminal state"):
            ssm.advance(TIER_ID, SUBTEST_ID, {})

    def test_advance_action_exception_does_not_change_state(
        self, ssm: SubtestStateMachine, checkpoint_path: Path
    ) -> None:
        """If action raises, exception propagates without state change."""
        action = MagicMock(side_effect=ValueError("action failed"))
        with pytest.raises(ValueError, match="action failed"):
            ssm.advance(TIER_ID, SUBTEST_ID, {SubtestState.PENDING: action})

        # State should NOT have been advanced
        assert ssm.get_state(TIER_ID, SUBTEST_ID) == SubtestState.PENDING

    def test_advance_through_all_states(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """Advance through every non-terminal subtest state in sequence."""
        from scylla.e2e.subtest_state_machine import _SUBTEST_STATE_SEQUENCE

        expected_sequence = list(_SUBTEST_STATE_SEQUENCE[1:])  # skip PENDING (start)

        for expected_state in expected_sequence:
            if is_subtest_terminal_state(ssm.get_state(TIER_ID, SUBTEST_ID)):
                break
            new_state = ssm.advance(TIER_ID, SUBTEST_ID, {})
            assert new_state == expected_state


# ---------------------------------------------------------------------------
# SubtestStateMachine.advance_to_completion tests
# ---------------------------------------------------------------------------


class TestSubtestStateMachineAdvanceToCompletion:
    """Tests for SubtestStateMachine.advance_to_completion() method."""

    def test_runs_all_states_to_aggregated(
        self, ssm: SubtestStateMachine, checkpoint_path: Path
    ) -> None:
        """advance_to_completion runs through all states to AGGREGATED."""
        actions_called = []

        def make_action(state: SubtestState):
            def action():
                actions_called.append(state)

            return action

        actions = {
            state: make_action(state)
            for state in SubtestState
            if not is_subtest_terminal_state(state)
        }
        final = ssm.advance_to_completion(TIER_ID, SUBTEST_ID, actions)
        assert final == SubtestState.AGGREGATED

    def test_resumes_from_mid_state(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """advance_to_completion skips already-completed states on resume."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.RUNS_COMPLETE.value)

        actions_called = []

        def make_action(state: SubtestState):
            def action():
                actions_called.append(state)

            return action

        actions = {
            state: make_action(state)
            for state in SubtestState
            if not is_subtest_terminal_state(state)
        }
        final = ssm.advance_to_completion(TIER_ID, SUBTEST_ID, actions)
        assert final == SubtestState.AGGREGATED

        # Only RUNS_COMPLETE should have been called; PENDING and RUNS_IN_PROGRESS skipped
        assert SubtestState.PENDING not in actions_called
        assert SubtestState.RUNS_IN_PROGRESS not in actions_called
        assert SubtestState.RUNS_COMPLETE in actions_called

    def test_resumes_from_runs_in_progress(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """advance_to_completion skips PENDING when resuming from RUNS_IN_PROGRESS."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.RUNS_IN_PROGRESS.value)

        actions_called = []

        def make_action(state: SubtestState):
            def action():
                actions_called.append(state)

            return action

        actions = {
            state: make_action(state)
            for state in SubtestState
            if not is_subtest_terminal_state(state)
        }
        final = ssm.advance_to_completion(TIER_ID, SUBTEST_ID, actions)
        assert final == SubtestState.AGGREGATED

        assert SubtestState.PENDING not in actions_called
        assert SubtestState.RUNS_IN_PROGRESS in actions_called
        assert SubtestState.RUNS_COMPLETE in actions_called

    def test_already_aggregated_is_noop(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """If already AGGREGATED, advance_to_completion is a no-op."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.AGGREGATED.value)
        action = MagicMock()
        final = ssm.advance_to_completion(TIER_ID, SUBTEST_ID, {SubtestState.PENDING: action})
        action.assert_not_called()
        assert final == SubtestState.AGGREGATED

    def test_already_failed_is_noop(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """If already FAILED, advance_to_completion is a no-op."""
        checkpoint.set_subtest_state(TIER_ID, SUBTEST_ID, SubtestState.FAILED.value)
        action = MagicMock()
        final = ssm.advance_to_completion(TIER_ID, SUBTEST_ID, {SubtestState.PENDING: action})
        action.assert_not_called()
        assert final == SubtestState.FAILED

    def test_action_exception_marks_subtest_failed(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """advance_to_completion marks FAILED in checkpoint when action raises."""
        action = MagicMock(side_effect=RuntimeError("run error"))
        with pytest.raises(RuntimeError, match="run error"):
            ssm.advance_to_completion(TIER_ID, SUBTEST_ID, {SubtestState.PENDING: action})

        assert ssm.get_state(TIER_ID, SUBTEST_ID) == SubtestState.FAILED

        from scylla.e2e.checkpoint import load_checkpoint

        loaded = load_checkpoint(checkpoint_path)
        assert loaded.get_subtest_state(TIER_ID, SUBTEST_ID) == SubtestState.FAILED.value

    def test_failed_state_persisted_to_disk(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """FAILED state is atomically saved to checkpoint on disk."""
        action = MagicMock(side_effect=ValueError("disk write test"))
        with pytest.raises(ValueError):
            ssm.advance_to_completion(TIER_ID, SUBTEST_ID, {SubtestState.PENDING: action})

        from scylla.e2e.checkpoint import load_checkpoint

        on_disk = load_checkpoint(checkpoint_path)
        assert on_disk.get_subtest_state(TIER_ID, SUBTEST_ID) == SubtestState.FAILED.value

    def test_independent_subtests_do_not_interfere(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """Two subtests track state independently."""
        subtest_a = "00"
        subtest_b = "01"

        # Advance subtest A to AGGREGATED
        ssm.advance_to_completion(TIER_ID, subtest_a, {})
        assert ssm.is_complete(TIER_ID, subtest_a)

        # Subtest B should still be PENDING
        assert ssm.get_state(TIER_ID, subtest_b) == SubtestState.PENDING
        assert not ssm.is_complete(TIER_ID, subtest_b)


# ---------------------------------------------------------------------------
# SubtestStateMachine.advance_to_completion until_state tests
# ---------------------------------------------------------------------------


class TestSubtestStateMachineUntilState:
    """Tests for advance_to_completion() until_state early-stop behavior.

    Although until_state is not CLI-exposed at the subtest level, the
    SubtestStateMachine.advance_to_completion() accepts an until_state
    parameter for completeness and potential future use.
    """

    def test_stops_at_until_state_before_executing_action(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """advance_to_completion stops AT until_state without executing its action."""
        action_runs_in_progress = MagicMock()
        action_runs_complete = MagicMock()

        actions = {
            SubtestState.PENDING: MagicMock(),
            SubtestState.RUNS_IN_PROGRESS: action_runs_in_progress,
            SubtestState.RUNS_COMPLETE: action_runs_complete,
        }
        final = ssm.advance_to_completion(
            TIER_ID,
            SUBTEST_ID,
            actions,  # type: ignore[arg-type]
            until_state=SubtestState.RUNS_IN_PROGRESS,
        )

        # Stopped at RUNS_IN_PROGRESS — its action should NOT have been called
        assert final == SubtestState.RUNS_IN_PROGRESS
        action_runs_in_progress.assert_not_called()
        action_runs_complete.assert_not_called()

    def test_stops_at_until_state_preserves_state_for_resume(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """State after until_state stop is preserved in checkpoint (no FAILED set)."""
        ssm.advance_to_completion(
            TIER_ID, SUBTEST_ID, {}, until_state=SubtestState.RUNS_IN_PROGRESS
        )

        assert ssm.get_state(TIER_ID, SUBTEST_ID) == SubtestState.RUNS_IN_PROGRESS
        assert not ssm.is_complete(TIER_ID, SUBTEST_ID)

        from scylla.e2e.checkpoint import load_checkpoint

        on_disk = load_checkpoint(checkpoint_path)
        assert on_disk.get_subtest_state(TIER_ID, SUBTEST_ID) == SubtestState.RUNS_IN_PROGRESS.value

    def test_resume_after_until_state_stop_continues_from_saved_state(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """After an until_state stop, resuming without until_state completes the subtest."""
        # First pass: stop at RUNS_IN_PROGRESS
        ssm.advance_to_completion(
            TIER_ID, SUBTEST_ID, {}, until_state=SubtestState.RUNS_IN_PROGRESS
        )
        assert ssm.get_state(TIER_ID, SUBTEST_ID) == SubtestState.RUNS_IN_PROGRESS

        # Second pass: resume to completion
        final = ssm.advance_to_completion(TIER_ID, SUBTEST_ID, {})
        assert final == SubtestState.AGGREGATED

    def test_until_state_at_current_state_stops_immediately(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """If until_state equals the current state, no transitions are executed."""
        action = MagicMock()
        final = ssm.advance_to_completion(
            TIER_ID, SUBTEST_ID, {SubtestState.PENDING: action}, until_state=SubtestState.PENDING
        )

        assert final == SubtestState.PENDING
        action.assert_not_called()

    def test_until_state_does_not_mark_failed(
        self,
        ssm: SubtestStateMachine,
        checkpoint: E2ECheckpoint,
        checkpoint_path: Path,
    ) -> None:
        """Stopping at until_state does not mark the subtest as FAILED."""
        ssm.advance_to_completion(TIER_ID, SUBTEST_ID, {}, until_state=SubtestState.RUNS_COMPLETE)
        assert ssm.get_state(TIER_ID, SUBTEST_ID) != SubtestState.FAILED
